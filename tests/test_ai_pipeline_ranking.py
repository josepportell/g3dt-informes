"""Tests for AI pipeline Stage 5 — ranking (chunk 1: models + passthrough).

No LLM calls are made in this chunk — these tests exercise the pydantic
models, the candidate-id helper, the YAML / principles loaders, and the
passthrough orchestrator for the 0/1-candidate paths.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pydantic
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.analysis import (
    Candidate,
    ProjectAnalysis,
    SourceAnalysis,
    SourceInsight,
)
from automation.ai_pipeline.ranking import (
    ConceptRanking,
    GroupAuditResult,
    ProjectRanking,
    RankedCandidate,
    _candidate_id,
    load_authority_principles,
    load_concept_definitions,
    load_ranking,
    rank_project_passthrough_only,
    save_ranking,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


def _make_analysis(
    sources: list[tuple[str, list[tuple[str, object, float]]]],
) -> ProjectAnalysis:
    """Build a minimal ProjectAnalysis.

    `sources` is a list of (source_path, [(concept_id, value, confidence), ...]).
    """
    src_analyses: list[SourceAnalysis] = []
    for source_path, cand_specs in sources:
        candidates = [
            Candidate(
                concept_id=cid,
                value=val,
                confidence=conf,
                source_path=source_path,
            )
            for cid, val, conf in cand_specs
        ]
        src_analyses.append(
            SourceAnalysis(
                source_path=source_path,
                insight=SourceInsight(
                    source_path=source_path,
                    document_type="test",
                    purpose="test",
                ),
                candidates=candidates,
            )
        )
    return ProjectAnalysis(
        project_path="/tmp/fake",
        analyzed_at="2026-04-24T00:00:00+00:00",
        sources=src_analyses,
    )


def _make_project_with_analysis(tmp_path: Path, analysis: ProjectAnalysis) -> Path:
    p = tmp_path / "demo"
    (p / "validation").mkdir(parents=True)
    (p / "validation" / "ai_analysis.json").write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    return p


# ─── Candidate-id helper ───────────────────────────────────────────────


def test_candidate_id_format():
    assert (
        _candidate_id("plans/A.01.pdf", "architect_name", 0)
        == "plans/A.01.pdf::architect_name::0"
    )
    assert (
        _candidate_id("", "x", 7) == "::x::7"
    )  # degenerate but well-defined


# ─── Pydantic models ───────────────────────────────────────────────────


def test_ranked_candidate_model():
    rc = RankedCandidate(
        candidate_id="plans/A.01.pdf::architect_name::0",
        source_path="plans/A.01.pdf",
        value="Joan Planes",
        confidence=0.9,
        rationale="caixetí del plànol",
    )
    assert rc.confidence == 0.9
    assert rc.value == "Joan Planes"


def test_concept_ranking_statuses():
    for status in ("ranked", "single", "no_candidates", "pending_fase5"):
        cr = ConceptRanking(concept_id="cid", status=status)
        assert cr.status == status


def test_concept_ranking_rejects_unknown_status():
    with pytest.raises(pydantic.ValidationError):
        ConceptRanking(concept_id="cid", status="weird_status")  # type: ignore[arg-type]


def test_project_ranking_ranking_of():
    cr = ConceptRanking(concept_id="client_name", status="single")
    pr = ProjectRanking(
        project_path="/tmp",
        ranked_at="2026-04-24T00:00:00+00:00",
        concepts={"client_name": cr},
    )
    assert pr.ranking_of("client_name") is cr
    assert pr.ranking_of("missing_concept") is None


def test_group_audit_result_defaults():
    g = GroupAuditResult(group="parcel")
    assert g.factors == []
    assert g.revisions == []
    assert g.skipped_reason == ""


# ─── Schema / principles loaders ───────────────────────────────────────


def test_load_concept_definitions_returns_many_concepts():
    defs = load_concept_definitions()
    # Sanity check — robust against small schema edits.
    assert len(defs) >= 80
    # Every entry should carry the keys Pass B (chunk 3) relies on.
    sample = next(iter(defs.values()))
    for k in ("id", "type", "group", "description_ca", "required"):
        assert k in sample


def test_load_authority_principles_exists():
    text = load_authority_principles()
    assert text  # non-empty
    assert ("Eva" in text) or ("autoritat" in text.lower())


# ─── Passthrough orchestrator ──────────────────────────────────────────


def test_passthrough_zero_candidates(tmp_path):
    # No sources at all → every concept ends up in no_candidates.
    analysis = _make_analysis(sources=[])
    project = _make_project_with_analysis(tmp_path, analysis)
    ranking = rank_project_passthrough_only(project, analysis=analysis)

    defs = load_concept_definitions()
    # Pick a concept we know exists in the real YAML.
    some_cid = next(iter(defs))
    cr = ranking.ranking_of(some_cid)
    assert cr is not None
    assert cr.status == "no_candidates"
    assert cr.ranked == []


def test_passthrough_single_candidate(tmp_path):
    # Use a concept that exists in the real YAML.
    defs = load_concept_definitions()
    cid = next(iter(defs))
    analysis = _make_analysis(
        sources=[("plans/A.01.pdf", [(cid, "Joan Planes", 0.9)])]
    )
    project = _make_project_with_analysis(tmp_path, analysis)

    ranking = rank_project_passthrough_only(project, analysis=analysis)
    cr = ranking.ranking_of(cid)
    assert cr is not None
    assert cr.status == "single"
    assert len(cr.ranked) == 1
    rc = cr.ranked[0]
    assert rc.value == "Joan Planes"
    assert rc.source_path == "plans/A.01.pdf"
    assert rc.rationale == "única font disponible"
    # Candidate id follows the documented shape.
    assert rc.candidate_id == f"plans/A.01.pdf::{cid}::0"
    # Chunks 2–3 will populate groups; for now passthrough must leave it empty.
    assert ranking.groups == {}


def test_passthrough_skips_multi_candidate_concepts(tmp_path):
    defs = load_concept_definitions()
    cid = next(iter(defs))
    analysis = _make_analysis(
        sources=[
            ("plans/A.01.pdf", [(cid, "Joan Planes", 0.9)]),
            ("emails/hello.msg", [(cid, "Marta Soler", 0.7)]),
        ]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    ranking = rank_project_passthrough_only(project, analysis=analysis)

    # Multi-candidate concept is intentionally omitted (later chunks fill it in).
    assert cid not in ranking.concepts
    # Exactly one concept has ≥2 candidates → summary must report "1 pendents".
    assert len(ranking.eva_summary) == 1
    assert "1 pendents de rànquing LLM" in ranking.eva_summary[0]


def test_passthrough_loads_from_disk_when_analysis_not_passed(tmp_path):
    defs = load_concept_definitions()
    cid = next(iter(defs))
    analysis = _make_analysis(
        sources=[("plans/A.01.pdf", [(cid, "Joan Planes", 0.9)])]
    )
    project = _make_project_with_analysis(tmp_path, analysis)

    # Do NOT pass analysis — function must load it from disk.
    ranking = rank_project_passthrough_only(project)
    cr = ranking.ranking_of(cid)
    assert cr is not None
    assert cr.status == "single"


def test_passthrough_raises_when_analysis_missing(tmp_path):
    project = tmp_path / "empty_project"
    project.mkdir()
    with pytest.raises(FileNotFoundError):
        rank_project_passthrough_only(project)


def test_save_and_load_ranking_roundtrip(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    pr = ProjectRanking(
        project_path=str(project),
        ranked_at="2026-04-24T00:00:00+00:00",
        concepts={
            "client_name": ConceptRanking(
                concept_id="client_name",
                status="single",
                ranked=[
                    RankedCandidate(
                        candidate_id="plans/A.01.pdf::client_name::0",
                        source_path="plans/A.01.pdf",
                        value="Joan Planes",
                        confidence=0.9,
                        rationale="única font disponible",
                    )
                ],
            )
        },
        eva_summary=["test"],
    )

    out = save_ranking(pr, project)
    assert out == project / "validation" / "ai_ranking.json"

    loaded = load_ranking(project)
    assert loaded is not None
    assert loaded.model_dump() == pr.model_dump()


def test_load_ranking_returns_none_when_absent(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    assert load_ranking(project) is None


def test_eva_summary_populated(tmp_path):
    analysis = _make_analysis(sources=[])
    project = _make_project_with_analysis(tmp_path, analysis)
    ranking = rank_project_passthrough_only(project, analysis=analysis)
    assert ranking.eva_summary
    assert any("Passthrough" in line for line in ranking.eva_summary)
