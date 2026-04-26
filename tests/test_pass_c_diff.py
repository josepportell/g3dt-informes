"""Tests for scripts/ai_pipeline_pass_c_diff.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load the script as a module via importlib (it has a hyphen-free name).
_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "scripts" / "ai_pipeline_pass_c_diff.py"
)
_spec = importlib.util.spec_from_file_location("pass_c_diff", _SCRIPT)
pass_c_diff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pass_c_diff)  # type: ignore[union-attr]


from automation.ai_pipeline.ranking import (
    ConceptRanking,
    ProjectRanking,
    RankedCandidate,
    save_ranking,
)


# ─── Helpers ────────────────────────────────────────────────────────────


def _rc(value: str, source: str = "src.pdf") -> RankedCandidate:
    return RankedCandidate(
        candidate_id=f"{source}::x::0",
        source_path=source,
        value=value,
        confidence=0.9,
        rationale="r",
    )


def _make_project(
    tmp_path: Path,
    *,
    concept_id: str,
    revised_top1: str,
    original_top1: str,
    eva_value: str | None,
) -> Path:
    """Build a minimal project with ai_ranking.json + Pass A cache + eva ref."""
    pp = tmp_path / "project"
    pp.mkdir()
    (pp / "validation").mkdir()
    (pp / "validation" / "ai_pipeline" / "ranking").mkdir(parents=True)

    # Current (revised) ranking — written via save_ranking.
    revised_cr = ConceptRanking(
        concept_id=concept_id,
        status="ranked",
        ranked=[_rc(revised_top1, "revised.pdf")],
        revised_by_group_pass=True,
    )
    project_ranking = ProjectRanking(
        project_path=str(pp),
        ranked_at="2026-04-25T00:00:00+00:00",
        concepts={concept_id: revised_cr},
    )
    save_ranking(project_ranking, pp)

    # Original Pass A cache file — different top-1.
    original_cr = ConceptRanking(
        concept_id=concept_id,
        status="ranked",
        ranked=[_rc(original_top1, "original.pdf")],
    )
    cache_file = (
        pp / "validation" / "ai_pipeline" / "ranking"
        / f"{pass_c_diff._slugify(concept_id)}_cache.json"
    )
    cache_file.write_text(
        json.dumps(
            {"key": "fake", "ranking": original_cr.model_dump()},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Eva reference values (or skip if None).
    if eva_value is not None:
        eva = {
            "variables": {
                concept_id: {
                    "value": eva_value,
                    "position": "body[1]",
                    "position_description": "",
                    "confidence": 1.0,
                    "extraction_method": "exact",
                }
            }
        }
        (pp / "validation" / "eva_reference_values.json").write_text(
            json.dumps(eva), encoding="utf-8"
        )
    return pp


# ─── Verdict tests ──────────────────────────────────────────────────────


def test_verdict_better_when_revised_matches_eva():
    assert pass_c_diff.verdict_for(
        original_top1="26.0049",
        revised_top1="4001670",
        eva_value="4001670",
    ) == "better"


def test_verdict_worse_when_revised_loses_match():
    assert pass_c_diff.verdict_for(
        original_top1="4001670",
        revised_top1="26.0049",
        eva_value="4001670",
    ) == "worse"


def test_verdict_neutral_when_neither_matches_eva():
    assert pass_c_diff.verdict_for(
        original_top1="aaa",
        revised_top1="bbb",
        eva_value="ccc",
    ) == "neutral"


def test_verdict_no_eva_ref_when_eva_missing():
    assert pass_c_diff.verdict_for(
        original_top1="aaa",
        revised_top1="bbb",
        eva_value=None,
    ) == "no_eva_ref"


def test_verdict_neutral_when_both_match_eva_loose():
    # Eva's narrative includes the underlying value; both candidates match.
    eva = "El expedient és 4001670 i s'ha tramitat..."
    assert pass_c_diff.verdict_for(
        original_top1="4001670",
        revised_top1="4001670",
        eva_value=eva,
    ) == "neutral"


# ─── Project diff tests ─────────────────────────────────────────────────


def test_diff_project_better_case(tmp_path):
    pp = _make_project(
        tmp_path,
        concept_id="expedient",
        revised_top1="4001670",
        original_top1="26.0049",
        eva_value="4001670",
    )
    diff = pass_c_diff.diff_project(pp)
    assert len(diff["rows"]) == 1
    assert diff["rows"][0]["verdict"] == "better"
    assert diff["counts"]["better"] == 1
    assert diff["counts"]["worse"] == 0


def test_diff_project_worse_case(tmp_path):
    pp = _make_project(
        tmp_path,
        concept_id="expedient",
        revised_top1="26.0049",
        original_top1="4001670",
        eva_value="4001670",
    )
    diff = pass_c_diff.diff_project(pp)
    assert len(diff["rows"]) == 1
    assert diff["rows"][0]["verdict"] == "worse"
    assert diff["counts"]["worse"] == 1


def test_diff_project_no_eva_ref(tmp_path):
    pp = _make_project(
        tmp_path,
        concept_id="architect_company",
        revised_top1="2 GRAUS PROJECTES",
        original_top1="2 GRAUS",
        eva_value=None,
    )
    diff = pass_c_diff.diff_project(pp)
    assert len(diff["rows"]) == 1
    assert diff["rows"][0]["verdict"] == "no_eva_ref"


def test_render_markdown_contains_verdict_table(tmp_path):
    pp = _make_project(
        tmp_path,
        concept_id="expedient",
        revised_top1="4001670",
        original_top1="26.0049",
        eva_value="4001670",
    )
    diff = pass_c_diff.diff_project(pp)
    md = pass_c_diff.render_markdown(diff)
    assert "expedient" in md
    assert "**better**" in md
    assert "Summary:" in md


# ─── Missing-cache + no-change-guardrail tests ──────────────────────────


def test_diff_handles_missing_pass_a_cache(tmp_path):
    """W4: concept marked revised_by_group_pass=True but Pass A cache file
    absent → diff drops the row gracefully (no crash, no spurious entry)."""
    pp = tmp_path / "project"
    pp.mkdir()
    (pp / "validation").mkdir()
    (pp / "validation" / "ai_pipeline" / "ranking").mkdir(parents=True)

    # Ranking marks the concept as revised; do NOT write the Pass A cache.
    revised_cr = ConceptRanking(
        concept_id="expedient",
        status="ranked",
        ranked=[_rc("4001670", "revised.pdf")],
        revised_by_group_pass=True,
    )
    project_ranking = ProjectRanking(
        project_path=str(pp),
        ranked_at="2026-04-25T00:00:00+00:00",
        concepts={"expedient": revised_cr},
    )
    save_ranking(project_ranking, pp)

    # Sanity: no cache file present.
    cache_file = (
        pp / "validation" / "ai_pipeline" / "ranking"
        / f"{pass_c_diff._slugify('expedient')}_cache.json"
    )
    assert not cache_file.exists()

    diff = pass_c_diff.diff_project(pp)
    # Concept counts as revised but has no comparable original — row absent.
    assert diff["rows"] == []
    assert diff["counts"] == {"better": 0, "worse": 0, "neutral": 0, "no_eva_ref": 0}
    assert diff["total_revised_concepts"] == 1


def test_diff_skips_concept_when_pass_c_kept_same_top1(tmp_path):
    """W4: Pass C reordered the tail but kept the same top-1 candidate value
    → concept is not in the diff rows (no behavioural change)."""
    pp = _make_project(
        tmp_path,
        concept_id="expedient",
        revised_top1="4001670",
        original_top1="4001670",  # same top-1 value
        eva_value="4001670",
    )
    diff = pass_c_diff.diff_project(pp)
    assert diff["rows"] == []
    assert diff["counts"] == {"better": 0, "worse": 0, "neutral": 0, "no_eva_ref": 0}
    # Still flagged as a Pass-C reordering at the project-level counter.
    assert diff["total_revised_concepts"] == 1


def test_pass_c_diff_uses_aliases(tmp_path, monkeypatch):
    """When Eva keys her reference under a template placeholder
    (e.g. `client` instead of canonical `client_name`), the diff must look
    up via the alias map rather than returning `no_eva_ref`."""
    concept_id = "client_name"
    pp = tmp_path / "project"
    pp.mkdir()
    (pp / "validation").mkdir()
    (pp / "validation" / "ai_pipeline" / "ranking").mkdir(parents=True)

    revised_cr = ConceptRanking(
        concept_id=concept_id,
        status="ranked",
        ranked=[_rc("SR. ALBERT SANS BONVEHI", "revised.pdf")],
        revised_by_group_pass=True,
    )
    project_ranking = ProjectRanking(
        project_path=str(pp),
        ranked_at="2026-04-25T00:00:00+00:00",
        concepts={concept_id: revised_cr},
    )
    save_ranking(project_ranking, pp)

    original_cr = ConceptRanking(
        concept_id=concept_id,
        status="ranked",
        ranked=[_rc("OTHER CLIENT", "original.pdf")],
    )
    cache_file = (
        pp / "validation" / "ai_pipeline" / "ranking"
        / f"{pass_c_diff._slugify(concept_id)}_cache.json"
    )
    cache_file.write_text(
        json.dumps(
            {"key": "fake", "ranking": original_cr.model_dump()},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Eva keys the value under the template placeholder `client`, NOT
    # under the canonical concept_id `client_name`.
    eva_payload = {
        "variables": {
            "client": {
                "value": "SR. ALBERT SANS BONVEHI",
                "position": "p023",
                "position_description": "Body paragraph 23",
                "confidence": 0.95,
                "extraction_method": "intelligent_analysis",
            }
        }
    }
    (pp / "validation" / "eva_reference_values.json").write_text(
        json.dumps(eva_payload), encoding="utf-8"
    )

    # Stub the alias loader so the test is independent of the on-disk YAML.
    monkeypatch.setattr(
        pass_c_diff,
        "_load_template_aliases",
        lambda: {"client_name": ["client", "client_name"]},
    )

    diff = pass_c_diff.diff_project(pp)
    assert len(diff["rows"]) == 1
    row = diff["rows"][0]
    assert row["concept_id"] == "client_name"
    # With the alias map active, Eva is found and verdict is "better"
    # (revised matches Eva, original did not). Without the alias, this would
    # have been "no_eva_ref".
    assert row["eva"] == "SR. ALBERT SANS BONVEHI"
    assert row["verdict"] == "better"
    assert diff["counts"]["better"] == 1
    assert diff["counts"]["no_eva_ref"] == 0
