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
