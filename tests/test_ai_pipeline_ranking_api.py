"""API smoke tests for GET /api/ai-pipeline/ranking/{project}.

All tests use passthrough-only analyses so no LLM call is made and no
ANTHROPIC_API_KEY is required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.analysis import (
    Candidate,
    ProjectAnalysis,
    SourceAnalysis,
    SourceInsight,
)
from web import wizard_service
from web.server import app


# ─── Fixtures ──────────────────────────────────────────────────────────


def _make_passthrough_analysis() -> ProjectAnalysis:
    """Single source with one candidate for one concept — all others fall
    through as `no_candidates`. No concept hits ≥2 candidates.
    """
    sources = [
        SourceAnalysis(
            source_path="plans/A.01.pdf",
            insight=SourceInsight(
                source_path="plans/A.01.pdf",
                document_type="test",
                purpose="test",
            ),
            candidates=[
                Candidate(
                    concept_id="architect_name",
                    value="Test Architect",
                    confidence=0.9,
                    source_path="plans/A.01.pdf",
                )
            ],
        )
    ]
    return ProjectAnalysis(
        project_path="/tmp/fake",
        analyzed_at="2026-04-24T00:00:00+00:00",
        sources=sources,
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fake_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    """Create a tmp-path reference project with a passthrough-only analysis
    and point wizard_service._REF_DIR at the tmp parent.
    """
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    project_name = "demo-project"
    project = ref_dir / project_name
    (project / "validation").mkdir(parents=True)
    analysis = _make_passthrough_analysis()
    (project / "validation" / "ai_analysis.json").write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8"
    )

    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)
    return project_name, project


# ─── Tests ──────────────────────────────────────────────────────────────


def test_ranking_404_on_missing_project(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)

    r = client.get("/api/ai-pipeline/ranking/does-not-exist")
    assert r.status_code == 404


def test_ranking_passthrough_cache_miss_then_hit(
    client: TestClient, fake_project: tuple[str, Path]
) -> None:
    project_name, project = fake_project

    # First call → cache miss, computes, saves
    r1 = client.get(f"/api/ai-pipeline/ranking/{project_name}?no_group_pass=true")
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["cached"] is False
    assert "ranking" in body1
    assert body1["ranking"]["concepts"]["architect_name"]["status"] == "single"
    # Saved to disk
    assert (project / "validation" / "ai_ranking.json").is_file()

    # Second call → cache hit (no_group_pass isn't needed to re-derive because
    # the cache is read directly regardless of query params).
    r2 = client.get(f"/api/ai-pipeline/ranking/{project_name}?no_group_pass=true")
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["cached"] is True


def test_ranking_refresh_bypasses_cache(
    client: TestClient, fake_project: tuple[str, Path]
) -> None:
    project_name, _project = fake_project

    # Warm the cache
    r1 = client.get(f"/api/ai-pipeline/ranking/{project_name}?no_group_pass=true")
    assert r1.status_code == 200
    assert r1.json()["cached"] is False

    # refresh=true → recompute
    r2 = client.get(
        f"/api/ai-pipeline/ranking/{project_name}?no_group_pass=true&refresh=true"
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["cached"] is False


def test_ranking_no_group_pass_empty_groups(
    client: TestClient, fake_project: tuple[str, Path]
) -> None:
    project_name, _project = fake_project
    r = client.get(
        f"/api/ai-pipeline/ranking/{project_name}?no_group_pass=true&refresh=true"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ranking"]["groups"] == {}


def test_ranking_group_filter_parses_comma_separated(
    client: TestClient,
    fake_project: tuple[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """?group_filter=parcel,lab → rank_project called with set{"parcel","lab"}."""
    project_name, _project = fake_project

    captured: dict = {}

    import automation.ai_pipeline.ranking as ranking_mod
    from automation.ai_pipeline.ranking import (
        ProjectRanking,
        rank_project as real_rank_project,
    )
    from web import api as api_mod

    def fake_rank_project(project_path, **kwargs):
        captured["project_path"] = project_path
        captured.update(kwargs)
        return ProjectRanking(
            project_path=str(project_path),
            ranked_at="2026-04-24T00:00:00+00:00",
        )

    # The endpoint does `from automation.ai_pipeline.ranking import rank_project`
    # inside the function body — monkeypatch at the source module.
    monkeypatch.setattr(ranking_mod, "rank_project", fake_rank_project)

    r = client.get(
        f"/api/ai-pipeline/ranking/{project_name}"
        f"?group_filter=parcel,lab&refresh=true"
    )
    assert r.status_code == 200, r.text
    assert captured.get("group_filter") == {"parcel", "lab"}
    assert captured.get("no_group_pass") is False
    assert captured.get("force") is True


# ─── UI contract tests (Stage 5 wizard) ─────────────────────────────────
#
# These assert the fields the Stage 5 UI (`review.html`) reads from the API
# response. If a field is renamed at any layer (pydantic model, writer,
# loader, endpoint) the UI would silently fail — these tests catch that
# at the API surface.


def test_ranking_response_roundtrip_preserves_all_schema_fields(
    client: TestClient,
    fake_project: tuple[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build a realistic ranking payload (conflict, revised_by_group_pass,
    skipped_reason) and assert the JSON served by the endpoint preserves
    every field intact after save+load+serialize.
    """
    project_name, _project = fake_project

    import automation.ai_pipeline.ranking as ranking_mod
    from automation.ai_pipeline.ranking import (
        ConceptRanking,
        GroupAuditResult,
        ProjectRanking,
        RankedCandidate,
    )

    def fake_rank_project(project_path, **kwargs):
        return ProjectRanking(
            project_path=str(project_path),
            ranked_at="2026-04-24T00:00:00+00:00",
            concepts={
                "architect_name": ConceptRanking(
                    concept_id="architect_name",
                    status="ranked",
                    ranked=[
                        RankedCandidate(
                            candidate_id="plans/A.01.pdf::architect_name::0",
                            source_path="plans/A.01.pdf",
                            value="David Graus",
                            confidence=0.95,
                            rationale="Caixetí del plànol signat.",
                        ),
                        RankedCandidate(
                            candidate_id="email.msg::architect_name::0",
                            source_path="email.msg",
                            value="D. Graus",
                            confidence=0.7,
                            rationale="Remitent email; menys formal.",
                        ),
                    ],
                    has_conflict=True,
                    conflict_note="Nom complet vs abreviat.",
                    group_factor_considered="Factor cross-concept detectat.",
                    revised_by_group_pass=True,
                    attempts=1,
                    elapsed_ms=1234,
                    model="claude-sonnet-4-6",
                ),
                "Es_settlement": ConceptRanking(
                    concept_id="Es_settlement",
                    status="no_candidates",
                ),
                "access_description": ConceptRanking(
                    concept_id="access_description",
                    status="single",
                    ranked=[
                        RankedCandidate(
                            candidate_id="email.msg::access_description::15",
                            source_path="email.msg",
                            value="bon accés",
                            confidence=0.9,
                            rationale="única font disponible",
                        )
                    ],
                ),
                "pending_concept": ConceptRanking(
                    concept_id="pending_concept",
                    status="pending_fase5",
                    ranked=[],
                ),
            },
            groups={
                "architect": GroupAuditResult(
                    group="architect",
                    factors=[
                        {
                            "description": "Plànols duplicats amb valors divergents",
                            "affects": ["architect_name", "architect_company"],
                        }
                    ],
                    revisions=[
                        {
                            "concept_id": "architect_name",
                            "revise": True,
                            "reason": "Verificar caixetí canònic",
                        }
                    ],
                    attempts=1,
                    elapsed_ms=5678,
                    model="claude-sonnet-4-6",
                ),
                "tiny_group": GroupAuditResult(
                    group="tiny_group",
                    skipped_reason="group size < 2",
                ),
            },
            eva_summary=[
                "Rànquing de Fase 5: 1 concepte rankejat, 1 single, 1 sense candidats.",
                "• 1 conflicte detectat.",
            ],
            total_input_tokens=1000,
            total_output_tokens=500,
            estimated_cost_usd=0.0123,
            cache_hits=2,
            failures=[],
        )

    monkeypatch.setattr(ranking_mod, "rank_project", fake_rank_project)

    r = client.get(f"/api/ai-pipeline/ranking/{project_name}?refresh=true")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cached"] is False
    ranking = body["ranking"]

    # Concept with full feature set
    arch = ranking["concepts"]["architect_name"]
    assert arch["status"] == "ranked"
    assert arch["has_conflict"] is True
    assert arch["conflict_note"] == "Nom complet vs abreviat."
    assert arch["group_factor_considered"] == "Factor cross-concept detectat."
    assert arch["revised_by_group_pass"] is True
    assert len(arch["ranked"]) == 2
    top = arch["ranked"][0]
    assert top["candidate_id"] == "plans/A.01.pdf::architect_name::0"
    assert top["source_path"] == "plans/A.01.pdf"
    assert top["value"] == "David Graus"
    assert top["confidence"] == 0.95
    assert top["rationale"] == "Caixetí del plànol signat."

    # no_candidates preserved as explicit status
    assert ranking["concepts"]["Es_settlement"]["status"] == "no_candidates"
    assert ranking["concepts"]["Es_settlement"]["ranked"] == []

    # single
    assert ranking["concepts"]["access_description"]["status"] == "single"

    # pending_fase5 concept roundtrips intact with empty ranked list
    assert ranking["concepts"]["pending_concept"]["status"] == "pending_fase5"
    assert ranking["concepts"]["pending_concept"]["ranked"] == []

    # Groups: factors + revisions + skipped_reason
    arch_group = ranking["groups"]["architect"]
    assert arch_group["skipped_reason"] == ""
    assert arch_group["factors"][0]["description"].startswith("Plànols duplicats")
    assert arch_group["factors"][0]["affects"] == ["architect_name", "architect_company"]
    assert arch_group["revisions"][0]["concept_id"] == "architect_name"
    assert arch_group["revisions"][0]["revise"] is True
    assert arch_group["revisions"][0]["reason"] == "Verificar caixetí canònic"
    assert ranking["groups"]["tiny_group"]["skipped_reason"] == "group size < 2"

    # Summary + stats
    assert len(ranking["eva_summary"]) == 2
    assert ranking["estimated_cost_usd"] == 0.0123
    assert ranking["cache_hits"] == 2


def test_api_returns_schema_fields_needed_by_ui(
    client: TestClient, fake_project: tuple[str, Path]
) -> None:
    """Snapshot: every field the Stage 5 UI reads must exist in the JSON."""
    project_name, _project = fake_project
    r = client.get(f"/api/ai-pipeline/ranking/{project_name}?no_group_pass=true&refresh=true")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "ranking" in body and "cached" in body
    ranking = body["ranking"]

    # Top-level ProjectRanking fields
    for field in (
        "project_path",
        "ranked_at",
        "concepts",
        "groups",
        "eva_summary",
        "failures",
        "total_input_tokens",
        "total_output_tokens",
        "estimated_cost_usd",
        "cache_hits",
        "schema_version",
    ):
        assert field in ranking, f"missing top-level field: {field}"

    assert isinstance(ranking["concepts"], dict)
    assert isinstance(ranking["groups"], dict)
    assert isinstance(ranking["eva_summary"], list)
    assert isinstance(ranking["failures"], list)

    # At least one concept must be present (passthrough created architect_name)
    assert ranking["concepts"], "expected at least one concept in passthrough analysis"
    for cid, c in ranking["concepts"].items():
        for field in (
            "concept_id",
            "status",
            "ranked",
            "has_conflict",
            "conflict_note",
            "group_factor_considered",
            "revised_by_group_pass",
        ):
            assert field in c, f"concept {cid} missing field: {field}"
        # RankedCandidate fields (if any)
        for rc in c["ranked"]:
            for field in (
                "candidate_id",
                "source_path",
                "value",
                "confidence",
                "rationale",
            ):
                assert field in rc, f"ranked candidate in {cid} missing field: {field}"


def test_api_preserves_systemic_failure_shape(
    client: TestClient,
    fake_project: tuple[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Systemic failures use concept_id='*' sentinel; UI reads error_type and
    falls back from message to last_error. Ensure all keys roundtrip."""
    project_name, _project = fake_project

    import automation.ai_pipeline.ranking as ranking_mod
    from automation.ai_pipeline.ranking import ProjectRanking

    def fake_rank_project(project_path, **kwargs):
        return ProjectRanking(
            project_path=str(project_path),
            ranked_at="2026-04-24T00:00:00+00:00",
            failures=[
                {
                    "concept_id": "*",
                    "error_type": "rate_limit",
                    "message": "transient error",
                    "last_error": "connection reset",
                }
            ],
        )

    monkeypatch.setattr(ranking_mod, "rank_project", fake_rank_project)

    r = client.get(f"/api/ai-pipeline/ranking/{project_name}?refresh=true")
    assert r.status_code == 200, r.text
    body = r.json()
    ranking = body["ranking"]
    failures = ranking["failures"]
    assert len(failures) == 1
    assert failures[0]["concept_id"] == "*"
    assert failures[0]["error_type"] == "rate_limit"
    # UI falls back from message to last_error — both must be present
    assert "message" in failures[0]
    assert "last_error" in failures[0]
