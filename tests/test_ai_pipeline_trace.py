"""Tests for the AI pipeline diagnostic trace tool."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.trace import (  # noqa: E402
    PipelineTrace,
    build_trace,
    diff_traces,
    load_trace,
    save_trace,
)


# ---------------------------------------------------------------------------
# Synthetic project builder
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_synthetic_project(
    tmp_path: Path,
    *,
    candidate_values: list[tuple[str, float, str]] | None = None,
    with_conflict: bool = False,
    eva_value=None,
    extras: dict | None = None,
) -> Path:
    """Create a minimal project with the five Stage manifests.

    `candidate_values`: list of (source_path, value, confidence_str) triples
        used as candidates for concept "demo_concept".
    `with_conflict`: when True, ranking has has_conflict=True.
    `eva_value`: when set, written into eva_reference_values.json.
    `extras`: optional dict to merge extra files/concepts/etc.
    """
    project = tmp_path / "demo-project"
    val_dir = project / "validation"
    val_dir.mkdir(parents=True)

    candidate_values = candidate_values or [
        ("file_a.pdf", "ACME Corp", 0.95),
        ("file_b.pdf", "ACME Corp", 0.85),
    ]

    # Inventory
    inv_files = []
    for src, _v, _c in candidate_values:
        inv_files.append({
            "path": src,
            "size_kb": 12,
            "type": "pdf_vector",
            "kind": "regular",
            "parent_msg": None,
        })
    inv = {
        "project_path": str(project.resolve()),
        "scanned_at": "2026-04-24T10:00:00+00:00",
        "total_files": len(inv_files),
        "root_file_count": len(inv_files),
        "folders": [{"path": "", "file_count": len(inv_files)}],
        "files": inv_files,
        "msg_count": 0,
        "extracted_attachments": 0,
    }
    _write_json(val_dir / "ai_inventory.json", inv)

    # Typology
    typ_files = []
    for src, _v, _c in candidate_values:
        typ_files.append({
            "path": src,
            "format": "pdf",
            "category": "pdf_text",
            "has_text": True,
            "has_images": False,
            "image_count": 0,
            "page_count": 1,
            "sheet_count": 0,
            "sheet_names": [],
            "source_chain": [],
            "is_attachment": False,
            "parent_path": None,
            "useful": True,
            "reason": "",
            "conversion_strategy": "pdf_to_markdown",
            "extracted_images_dir": None,
        })
    # Add extras
    extras = extras or {}
    for f in extras.get("typology_extras", []):
        typ_files.append(f)
    typ = {
        "project_path": str(project.resolve()),
        "classified_at": "2026-04-24T10:01:00+00:00",
        "files": typ_files,
        "folders": [
            {
                "path": "",
                "parent": None,
                "file_count": len(typ_files),
                "useful_count": sum(1 for f in typ_files if f["useful"]),
                "category_counts": {},
                "is_dev_only": False,
            }
        ],
        "counts_by_category": {"pdf_text": len(candidate_values)},
        "useful_count": sum(1 for f in typ_files if f["useful"]),
        "skipped_count": sum(1 for f in typ_files if not f["useful"]),
        "eva_summary": [],
        "warnings": [],
    }
    _write_json(val_dir / "ai_typology.json", typ)

    # Conversion
    artifacts = []
    for src, _v, _c in candidate_values:
        artifacts.append({
            "path": f"validation/ai_pipeline/converted/{Path(src).stem}/page_001.md",
            "format": "md",
            "source_path": src,
            "source_chain": [],
            "strategy_used": "pdf_to_markdown",
            "page": 1,
            "sheet": None,
            "bytes_written": 100,
            "skipped": False,
            "skip_reason": "",
        })
    for a in extras.get("conversion_extras", []):
        artifacts.append(a)
    conv = {
        "project_path": str(project.resolve()),
        "converted_at": "2026-04-24T10:02:00+00:00",
        "artifacts": artifacts,
        "per_source": {src: [a["path"] for a in artifacts if a["source_path"] == src]
                       for src, _v, _c in candidate_values},
        "total_bytes": 100 * len(artifacts),
        "warnings": [],
        "eva_summary": [],
    }
    _write_json(val_dir / "ai_conversion.json", conv)

    # Analysis
    sources = []
    for src, val, conf in candidate_values:
        sources.append({
            "source_path": src,
            "insight": {
                "source_path": src,
                "document_type": "test_doc",
                "purpose": "synthetic test",
                "author": "",
                "date_info": "",
                "version_info": "",
                "related_sources": [],
                "authority_hints": [],
                "confidence": 0.9,
                "notes": "",
            },
            "candidates": [
                {
                    "concept_id": "demo_concept",
                    "value": val,
                    "confidence": conf,
                    "quote": f"verbatim {val}",
                    "artifact_path": "",
                    "source_path": src,
                    "source_chain": [],
                    "extractor": "test",
                    "reasoning": "",
                }
            ],
            "attempts": 1,
            "elapsed_ms": 100,
            "model": "test",
            "input_tokens": 0,
            "output_tokens": 0,
        })
    for s in extras.get("analysis_sources", []):
        sources.append(s)
    failures = extras.get("analysis_failures", [])
    candidates_by_concept = {"demo_concept": [src for src, _v, _c in candidate_values]}
    candidates_by_concept.update(extras.get("candidates_by_concept_extras", {}))
    analysis = {
        "project_path": str(project.resolve()),
        "analyzed_at": "2026-04-24T10:03:00+00:00",
        "sources": sources,
        "failures": failures,
        "systemic_failure": None,
        "candidates_by_concept": candidates_by_concept,
        "eva_summary": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "cache_hits": 0,
        "schema_version": "1.2",
    }
    _write_json(val_dir / "ai_analysis.json", analysis)

    # Ranking
    ranked = []
    for i, (src, val, conf) in enumerate(candidate_values):
        ranked.append({
            "candidate_id": f"{src}::demo_concept::0",
            "source_path": src,
            "value": val,
            "confidence": conf,
            "rationale": f"r{i}",
        })
    concepts = {
        "demo_concept": {
            "concept_id": "demo_concept",
            "status": "ranked" if len(candidate_values) >= 2 else "single",
            "ranked": ranked,
            "has_conflict": with_conflict,
            "conflict_note": "synthetic conflict" if with_conflict else "",
            "group_factor_considered": "",
            "revised_by_group_pass": False,
            "attempts": 1,
            "elapsed_ms": 100,
            "model": "test",
        }
    }
    concepts.update(extras.get("ranking_concepts_extras", {}))
    ranking = {
        "project_path": str(project.resolve()),
        "ranked_at": "2026-04-24T10:04:00+00:00",
        "concepts": concepts,
        "groups": extras.get("ranking_groups", {}),
        "eva_summary": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_creation_tokens": 0,
        "total_cache_read_tokens": 0,
        "estimated_cost_usd": 0.0,
        "cache_hits": 0,
        "failures": [],
        "schema_version": "1.0",
    }
    _write_json(val_dir / "ai_ranking.json", ranking)

    # Eva reference
    if eva_value is not None:
        eva_ref = {
            "project": "demo",
            "variables": {
                "demo_concept": {
                    "value": eva_value,
                    "position": "p001",
                    "position_description": "test",
                    "confidence": 0.9,
                    "extraction_method": "test",
                    "reference_text": str(eva_value),
                }
            },
        }
        _write_json(val_dir / "eva_reference_values.json", eva_ref)

    return project


# ---------------------------------------------------------------------------
# Test 1 — trace builds and joins all five manifests
# ---------------------------------------------------------------------------


def test_build_trace_joins_all_five_manifests(tmp_path):
    project = _make_synthetic_project(tmp_path)
    trace = build_trace(project)

    assert isinstance(trace, PipelineTrace)
    assert trace.project_name == "demo-project"
    assert trace.stage1_summary["available"] is True
    assert trace.stage2_summary["available"] is True
    assert trace.stage3_summary["available"] is True
    assert trace.stage4_summary["available"] is True
    assert trace.stage5_summary["available"] is True
    # Source journey present for both files.
    assert "file_a.pdf" in trace.sources
    assert "file_b.pdf" in trace.sources
    # Source journey has artifacts + insight.
    sj = trace.sources["file_a.pdf"]
    assert len(sj.artifacts) == 1
    assert sj.insight is not None
    # Source contributed to ranking.
    assert any(c["concept_id"] == "demo_concept" for c in sj.rankings_contributed_to)


# ---------------------------------------------------------------------------
# Test 2 — unanimous concept → auto_accept
# ---------------------------------------------------------------------------


def test_concept_journey_for_unanimous_concept(tmp_path):
    candidates = [
        ("file_a.pdf", "ACME", 0.95),
        ("file_b.pdf", "ACME", 0.92),
        ("file_c.pdf", "ACME", 0.91),
    ]
    project = _make_synthetic_project(
        tmp_path,
        candidate_values=candidates,
        extras={
            "conversion_extras": [{
                "path": "validation/ai_pipeline/converted/file_c/page_001.md",
                "format": "md",
                "source_path": "file_c.pdf",
                "source_chain": [],
                "strategy_used": "pdf_to_markdown",
                "page": 1, "sheet": None, "bytes_written": 100,
                "skipped": False, "skip_reason": "",
            }],
            "typology_extras": [{
                "path": "file_c.pdf", "format": "pdf", "category": "pdf_text",
                "has_text": True, "has_images": False, "image_count": 0,
                "page_count": 1, "sheet_count": 0, "sheet_names": [],
                "source_chain": [], "is_attachment": False, "parent_path": None,
                "useful": True, "reason": "", "conversion_strategy": "pdf_to_markdown",
                "extracted_images_dir": None,
            }],
        },
    )
    trace = build_trace(project)
    j = trace.concepts["demo_concept"]
    assert j.source_agreement == "unanimous"
    assert j.picker_action == "auto_accept"


# ---------------------------------------------------------------------------
# Test 3 — split → eva_decides
# ---------------------------------------------------------------------------


def test_concept_journey_for_split_concept(tmp_path):
    candidates = [
        ("file_a.pdf", "ACME", 0.95),
        ("file_b.pdf", "Globex", 0.92),
    ]
    project = _make_synthetic_project(
        tmp_path, candidate_values=candidates, with_conflict=True,
    )
    trace = build_trace(project)
    j = trace.concepts["demo_concept"]
    assert j.source_agreement == "split"
    assert j.picker_action == "eva_decides"
    assert j.final_has_conflict is True


# ---------------------------------------------------------------------------
# Test 4 — outlier
# ---------------------------------------------------------------------------


def test_concept_journey_for_outlier_concept(tmp_path):
    # 1 candidate "Top" against 4 with "Other" — but ranking puts "Top" first.
    candidates = [
        ("file_a.pdf", "Top", 0.95),
        ("file_b.pdf", "Other", 0.85),
        ("file_c.pdf", "Other", 0.85),
        ("file_d.pdf", "Other", 0.85),
        ("file_e.pdf", "Other", 0.85),
    ]
    typo_extras = []
    conv_extras = []
    for src, _v, _c in candidates[2:]:
        typo_extras.append({
            "path": src, "format": "pdf", "category": "pdf_text",
            "has_text": True, "has_images": False, "image_count": 0,
            "page_count": 1, "sheet_count": 0, "sheet_names": [],
            "source_chain": [], "is_attachment": False, "parent_path": None,
            "useful": True, "reason": "", "conversion_strategy": "pdf_to_markdown",
            "extracted_images_dir": None,
        })
        conv_extras.append({
            "path": f"validation/ai_pipeline/converted/{Path(src).stem}/page_001.md",
            "format": "md", "source_path": src, "source_chain": [],
            "strategy_used": "pdf_to_markdown", "page": 1, "sheet": None,
            "bytes_written": 100, "skipped": False, "skip_reason": "",
        })
    project = _make_synthetic_project(
        tmp_path,
        candidate_values=candidates,
        extras={"typology_extras": typo_extras, "conversion_extras": conv_extras},
    )
    trace = build_trace(project)
    j = trace.concepts["demo_concept"]
    assert j.source_agreement == "outlier"


# ---------------------------------------------------------------------------
# Test 5 — recoverable mismatch (Eva at rank 2)
# ---------------------------------------------------------------------------


def test_concept_journey_marks_recoverable_mismatch(tmp_path):
    candidates = [
        ("file_a.pdf", "Top", 0.95),
        ("file_b.pdf", "Eva", 0.85),
    ]
    project = _make_synthetic_project(
        tmp_path, candidate_values=candidates, eva_value="Eva",
    )
    trace = build_trace(project)
    j = trace.concepts["demo_concept"]
    assert j.eva_top1_match == "mismatch"
    assert j.eva_rank_in_ranked == 2
    assert any(
        m["concept_id"] == "demo_concept"
        for m in trace.cross_stage.eva_recoverable_mismatches
    )


# ---------------------------------------------------------------------------
# Test 6 — unrecoverable mismatch
# ---------------------------------------------------------------------------


def test_concept_journey_marks_unrecoverable_mismatch(tmp_path):
    candidates = [
        ("file_a.pdf", "Top", 0.95),
        ("file_b.pdf", "Other", 0.85),
    ]
    project = _make_synthetic_project(
        tmp_path, candidate_values=candidates, eva_value="MissingValue",
    )
    trace = build_trace(project)
    j = trace.concepts["demo_concept"]
    assert j.eva_top1_match == "mismatch"
    assert j.eva_rank_in_ranked is None
    assert any(
        m["concept_id"] == "demo_concept"
        for m in trace.cross_stage.eva_unrecoverable_mismatches
    )


# ---------------------------------------------------------------------------
# Test 7 — source journey lists artifacts and candidates
# ---------------------------------------------------------------------------


def test_source_journey_lists_artifacts_and_candidates(tmp_path):
    project = _make_synthetic_project(tmp_path)
    val_dir = project / "validation"
    # Add 3 artifacts to file_a.pdf and 2 candidates emitted.
    conv = json.loads((val_dir / "ai_conversion.json").read_text(encoding="utf-8"))
    for i in range(2, 4):  # 2 more pages → 3 total
        conv["artifacts"].append({
            "path": f"validation/ai_pipeline/converted/file_a/page_{i:03d}.md",
            "format": "md", "source_path": "file_a.pdf", "source_chain": [],
            "strategy_used": "pdf_to_markdown", "page": i, "sheet": None,
            "bytes_written": 100, "skipped": False, "skip_reason": "",
        })
    (val_dir / "ai_conversion.json").write_text(json.dumps(conv), encoding="utf-8")

    analysis = json.loads((val_dir / "ai_analysis.json").read_text(encoding="utf-8"))
    # Append a second candidate to file_a.pdf.
    analysis["sources"][0]["candidates"].append({
        "concept_id": "another_concept",
        "value": "extra",
        "confidence": 0.8,
        "quote": "x",
        "artifact_path": "",
        "source_path": "file_a.pdf",
        "source_chain": [],
        "extractor": "test",
        "reasoning": "",
    })
    (val_dir / "ai_analysis.json").write_text(json.dumps(analysis), encoding="utf-8")

    trace = build_trace(project)
    sj = trace.sources["file_a.pdf"]
    assert len(sj.artifacts) == 3
    assert len(sj.candidates_emitted) == 2


# ---------------------------------------------------------------------------
# Test 8 — decision audit lists dev-only skips
# ---------------------------------------------------------------------------


def test_decision_audit_lists_dev_only_skips(tmp_path):
    extras = {
        "typology_extras": [{
            "path": "PDF/old_report.pdf", "format": "pdf",
            "category": "reference_output",
            "has_text": True, "has_images": False, "image_count": 0,
            "page_count": 1, "sheet_count": 0, "sheet_names": [],
            "source_chain": [], "is_attachment": False, "parent_path": None,
            "useful": False,
            "reason": "inside PDF/ — prior-run deliverables, absent in production",
            "conversion_strategy": "skip", "extracted_images_dir": None,
        }],
    }
    project = _make_synthetic_project(tmp_path, extras=extras)
    trace = build_trace(project)
    paths = [s["path"] for s in trace.decisions.stage2_dev_only_skips]
    assert "PDF/old_report.pdf" in paths
    assert any(
        "prior-run" in s["reason"]
        for s in trace.decisions.stage2_dev_only_skips
    )


# ---------------------------------------------------------------------------
# Test 9 — Pass C no-change guardrails
# ---------------------------------------------------------------------------


def test_decision_audit_flags_pass_c_no_change_guardrails(tmp_path):
    extras = {
        "ranking_concepts_extras": {
            "guarded_concept": {
                "concept_id": "guarded_concept",
                "status": "ranked",
                "ranked": [{
                    "candidate_id": "file_a.pdf::guarded_concept::0",
                    "source_path": "file_a.pdf",
                    "value": "x", "confidence": 0.9, "rationale": "",
                }],
                "has_conflict": False,
                "conflict_note": "",
                "group_factor_considered": "version_info conflict",
                "revised_by_group_pass": False,
                "attempts": 1,
                "elapsed_ms": 100,
                "model": "test",
            }
        }
    }
    project = _make_synthetic_project(tmp_path, extras=extras)
    trace = build_trace(project)
    assert "guarded_concept" in trace.decisions.stage5_pass_c_no_change_guardrails


# ---------------------------------------------------------------------------
# Test 10 — top issues ranked by signal strength
# ---------------------------------------------------------------------------


def test_top_issues_ranked_by_signal_strength(tmp_path):
    # Mix of: unrecoverable mismatch + low conf + zero-candidate source.
    candidates = [
        ("file_a.pdf", "Top", 0.50),  # low confidence top-1
        ("file_b.pdf", "Other", 0.45),
    ]
    extras = {
        "analysis_sources": [{
            "source_path": "noisy.pdf",
            "insight": {
                "source_path": "noisy.pdf", "document_type": "noise",
                "purpose": "tests zero-candidate path", "author": "", "date_info": "",
                "version_info": "", "related_sources": [], "authority_hints": [],
                "confidence": 0.5, "notes": "",
            },
            "candidates": [],
            "attempts": 1, "elapsed_ms": 50, "model": "test",
            "input_tokens": 0, "output_tokens": 0,
        }],
    }
    project = _make_synthetic_project(
        tmp_path, candidate_values=candidates,
        eva_value="MissingValue", extras=extras,
    )
    trace = build_trace(project)
    sigs = [it["signal_strength"] for it in trace.top_issues]
    assert sigs == sorted(sigs, reverse=True)
    # After W2 dedup, the primary kind for demo_concept wins (highest signal),
    # and the secondary kind is preserved in `also_flagged`.
    kinds_primary = [it["kind"] for it in trace.top_issues]
    kinds_all = set(kinds_primary)
    for it in trace.top_issues:
        kinds_all.update(it.get("also_flagged") or [])
    assert "eva_unrecoverable_mismatch" in kinds_all
    assert "low_confidence" in kinds_all
    assert "zero_candidate_source" in kinds_all


# ---------------------------------------------------------------------------
# Test 11 — top issues capped at 30
# ---------------------------------------------------------------------------


def test_top_issues_capped_at_30(tmp_path):
    # Build many concepts with mismatches.
    candidate_values = [("file_a.pdf", "Top", 0.95), ("file_b.pdf", "Other", 0.85)]
    project = _make_synthetic_project(tmp_path, candidate_values=candidate_values)
    val_dir = project / "validation"

    # Inject 50 ranking concepts with "mismatch" — Eva says "Other2" (not in ranked).
    ranking = json.loads((val_dir / "ai_ranking.json").read_text(encoding="utf-8"))
    eva_vars = {}
    for i in range(50):
        cid = f"c_{i}"
        ranking["concepts"][cid] = {
            "concept_id": cid, "status": "ranked",
            "ranked": [
                {"candidate_id": f"file_a.pdf::{cid}::0", "source_path": "file_a.pdf",
                 "value": "Top", "confidence": 0.9, "rationale": ""},
                {"candidate_id": f"file_b.pdf::{cid}::0", "source_path": "file_b.pdf",
                 "value": "Other", "confidence": 0.85, "rationale": ""},
            ],
            "has_conflict": False, "conflict_note": "",
            "group_factor_considered": "", "revised_by_group_pass": False,
            "attempts": 1, "elapsed_ms": 50, "model": "test",
        }
        eva_vars[cid] = {
            "value": "Other2", "position": f"p{i}", "position_description": "test",
            "confidence": 0.9, "extraction_method": "test", "reference_text": "Other2",
        }
    (val_dir / "ai_ranking.json").write_text(json.dumps(ranking), encoding="utf-8")
    _write_json(val_dir / "eva_reference_values.json", {"variables": eva_vars})

    trace = build_trace(project)
    assert len(trace.top_issues) == 30


# ---------------------------------------------------------------------------
# Test 12 — diff two traces
# ---------------------------------------------------------------------------


def test_diff_two_traces(tmp_path):
    project = _make_synthetic_project(tmp_path)
    trace_prior = build_trace(project)

    # Modify the ranking so top-1 changes and conflict flag flips.
    val_dir = project / "validation"
    ranking = json.loads((val_dir / "ai_ranking.json").read_text(encoding="utf-8"))
    ranking["concepts"]["demo_concept"]["ranked"] = list(
        reversed(ranking["concepts"]["demo_concept"]["ranked"])
    )
    # Force a value change: rename one of the values.
    ranking["concepts"]["demo_concept"]["ranked"][0]["value"] = "DIFFERENT"
    ranking["concepts"]["demo_concept"]["has_conflict"] = True
    (val_dir / "ai_ranking.json").write_text(json.dumps(ranking), encoding="utf-8")

    trace_current = build_trace(project)
    diff = diff_traces(trace_prior, trace_current)
    assert any(c["concept_id"] == "demo_concept" for c in diff["top1_changed"])
    assert any(c["concept_id"] == "demo_concept" for c in diff["conflicts_gained"])


# ---------------------------------------------------------------------------
# Test 13 — save/load roundtrip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path):
    project = _make_synthetic_project(tmp_path)
    trace = build_trace(project)
    save_trace(trace, project)
    loaded = load_trace(project)
    assert loaded is not None
    assert loaded.project_name == trace.project_name
    assert set(loaded.concepts.keys()) == set(trace.concepts.keys())
    assert len(loaded.top_issues) == len(trace.top_issues)


# ---------------------------------------------------------------------------
# Test 14 — CLI smoke (human output)
# ---------------------------------------------------------------------------


def _run_cli(*args: str, project_root: Path) -> subprocess.CompletedProcess:
    script = Path(__file__).resolve().parent.parent / "scripts" / "ai_pipeline_trace.py"
    return subprocess.run(
        [sys.executable, str(script), "--project-path", str(project_root), *args],
        capture_output=True, text=True, timeout=60,
    )


def test_cli_smoke_human_output(tmp_path):
    project = _make_synthetic_project(tmp_path)
    res = _run_cli("--all", project_root=project)
    assert res.returncode == 0, res.stderr
    out = res.stdout
    assert "Top issues" in out
    assert "Per-stage health" in out


# ---------------------------------------------------------------------------
# Test 15 — CLI --save --report markdown
# ---------------------------------------------------------------------------


def test_cli_save_writes_markdown_report(tmp_path):
    project = _make_synthetic_project(tmp_path)
    res = _run_cli("--save", "--report", "markdown", project_root=project)
    assert res.returncode == 0, res.stderr
    diag_dir = Path(__file__).resolve().parent.parent / "docs" / "diagnostics"
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    # Slug for "demo-project" → "demo": split('_')[0] of "demo-project" is "demo-project"
    # but our slugify uses re.sub for non-alnum -> "_"; "demo-project" → "demo-project" stays
    # Actually our slug uses [A-Za-z0-9._-] kept, so dashes stay. And then split('_')[0]
    # picks "demo-project". So the file is named like:
    candidates = list(diag_dir.glob(f"ai_pipeline_*_{date}.md"))
    assert candidates, f"No markdown report found in {diag_dir}; files={list(diag_dir.iterdir())}"


# ---------------------------------------------------------------------------
# Test 16 — End-to-end on real Alcoletge data
# ---------------------------------------------------------------------------


_ALCOLETGE_PATH = (
    Path(__file__).resolve().parent.parent
    / "reference-material"
    / "4001670 ALCOLETGE"
)


@pytest.mark.skipif(
    not _ALCOLETGE_PATH.is_dir(),
    reason="Alcoletge reference manifests not present",
)
def test_real_alcoletge_trace():
    trace = build_trace(_ALCOLETGE_PATH)
    assert isinstance(trace, PipelineTrace)
    # ≥17 concepts populated (Alcoletge has 88 concepts in ranking).
    assert len(trace.concepts) >= 17
    # expedient (type=text) must NOT trigger numeric magnitude divergence
    # post-W1 fix — its values look like floats but the concept is textual.
    assert not any(
        h["concept_id"] == "expedient"
        for h in trace.cross_stage.concept_definition_ambiguity_hints
    )
    # qa_value recoverable mismatch should fire (Eva's 3.50 sits at rank ≥2).
    qa_recoverable = [
        m for m in trace.cross_stage.eva_recoverable_mismatches
        if m["concept_id"] == "qa_value"
    ]
    assert qa_recoverable, "expected qa_value recoverable mismatch"
    assert qa_recoverable[0]["eva_rank_in_ranked"] is not None
    assert qa_recoverable[0]["eva_rank_in_ranked"] >= 2
    # Top issues non-empty.
    assert trace.top_issues


# ---------------------------------------------------------------------------
# Test 17 — Eva substring routes to shape, not unrecoverable
# ---------------------------------------------------------------------------


def test_eva_substring_match_routes_to_shape_not_unrecoverable(tmp_path):
    """Eva = full sentence containing the rank-2 ranked value as substring.

    Expected: ConceptJourney.eva_rank_match_kind == "substring", concept appears
    in cross_stage.eva_shape_mismatches (NOT eva_unrecoverable_mismatches), and
    the resulting top_issue has signal_strength ≤ 0.5.
    """
    candidates = [
        ("file_a.pdf", "Other Street", 0.95),
        ("file_b.pdf", "Carrer Major", 0.85),
    ]
    project = _make_synthetic_project(
        tmp_path,
        candidate_values=candidates,
        eva_value="El carrer és Carrer Major al nord.",
    )
    trace = build_trace(project)
    j = trace.concepts["demo_concept"]
    assert j.eva_rank_match_kind == "substring"
    assert any(
        m["concept_id"] == "demo_concept"
        for m in trace.cross_stage.eva_shape_mismatches
    )
    assert not any(
        m["concept_id"] == "demo_concept"
        for m in trace.cross_stage.eva_unrecoverable_mismatches
    )
    shape_issues = [
        it for it in trace.top_issues
        if it["kind"] == "eva_shape_mismatch"
        and it.get("concept_id") == "demo_concept"
    ]
    # The primary entry for demo_concept may be a different (higher signal) kind
    # — but if eva_shape_mismatch surfaces directly its signal must be ≤ 0.5.
    for it in shape_issues:
        assert it["signal_strength"] <= 0.5
    # Confirm that whichever issue does surface for demo_concept either is
    # eva_shape_mismatch with low signal, or has eva_shape_mismatch in
    # also_flagged.
    primary = next(
        (it for it in trace.top_issues if it.get("concept_id") == "demo_concept"),
        None,
    )
    assert primary is not None
    is_shape = primary["kind"] == "eva_shape_mismatch"
    has_in_also = "eva_shape_mismatch" in (primary.get("also_flagged") or [])
    assert is_shape or has_in_also


# ---------------------------------------------------------------------------
# Test 18 — Catalan stopword "cap" doesn't trigger domain flag
# ---------------------------------------------------------------------------


def test_cap_stopword_does_not_trigger_domain_flag(tmp_path):
    """A candidate quote with the Catalan stopword "cap" (no domain context)
    must NOT trigger the "cap professional / topall" domain flag. The positive
    case ("supera el cap màxim") must trigger it.
    """
    # Negative case: stopword "cap" alone.
    candidates = [
        ("file_a.pdf", "X", 0.95),
        ("file_b.pdf", "X", 0.85),
    ]
    project = _make_synthetic_project(tmp_path / "neg", candidate_values=candidates)
    val_dir = project / "validation"
    analysis = json.loads((val_dir / "ai_analysis.json").read_text(encoding="utf-8"))
    analysis["sources"][0]["candidates"][0]["quote"] = (
        "no hi ha cap planta soterrani"
    )
    (val_dir / "ai_analysis.json").write_text(json.dumps(analysis), encoding="utf-8")
    trace = build_trace(project)
    j = trace.concepts["demo_concept"]
    assert not any("cap professional" in f for f in j.domain_flags), (
        f"Stopword 'cap' should not trigger flag; got: {j.domain_flags}"
    )

    # Positive case: domain phrase "cap màxim".
    project2 = _make_synthetic_project(tmp_path / "pos", candidate_values=candidates)
    val_dir2 = project2 / "validation"
    analysis2 = json.loads((val_dir2 / "ai_analysis.json").read_text(encoding="utf-8"))
    analysis2["sources"][0]["candidates"][0]["quote"] = "supera el cap màxim"
    (val_dir2 / "ai_analysis.json").write_text(
        json.dumps(analysis2, ensure_ascii=False), encoding="utf-8"
    )
    trace2 = build_trace(project2)
    j2 = trace2.concepts["demo_concept"]
    assert any("cap professional" in f for f in j2.domain_flags), (
        f"Domain phrase 'cap màxim' should trigger flag; got: {j2.domain_flags}"
    )


# ---------------------------------------------------------------------------
# Test 19 — Definition ambiguity skipped for text concepts
# ---------------------------------------------------------------------------


def test_definition_ambiguity_skipped_for_text_concepts(tmp_path, monkeypatch):
    """A text-typed concept whose top-1 and rank-2 values look like floats but
    differ by an order of magnitude must NOT trip the magnitude divergence.
    The same values for a number-typed concept MUST trip it.
    """
    from automation.ai_pipeline import trace as trace_module

    candidates = [
        ("file_a.pdf", "26.0049", 0.95),
        ("file_b.pdf", "4001670", 0.95),
    ]

    # --- Text-typed concept: ambiguity must NOT fire ---
    monkeypatch.setattr(
        trace_module,
        "_load_concept_definitions",
        lambda: {
            "demo_concept": {
                "id": "demo_concept",
                "type": "text",
                "group": "",
                "description_ca": "",
                "required": False,
            }
        },
    )
    project = _make_synthetic_project(
        tmp_path / "text", candidate_values=candidates, with_conflict=True,
    )
    trace = build_trace(project)
    assert not any(
        h["concept_id"] == "demo_concept"
        for h in trace.cross_stage.concept_definition_ambiguity_hints
    ), "magnitude divergence must NOT fire for type=text concept"

    # --- Number-typed concept: ambiguity MUST fire ---
    monkeypatch.setattr(
        trace_module,
        "_load_concept_definitions",
        lambda: {
            "demo_concept": {
                "id": "demo_concept",
                "type": "number",
                "group": "",
                "description_ca": "",
                "required": False,
            }
        },
    )
    project2 = _make_synthetic_project(
        tmp_path / "num", candidate_values=candidates, with_conflict=True,
    )
    trace2 = build_trace(project2)
    assert any(
        h["concept_id"] == "demo_concept"
        for h in trace2.cross_stage.concept_definition_ambiguity_hints
    ), "magnitude divergence MUST fire for type=number concept"


# ---------------------------------------------------------------------------
# Test 20 — top_issues dedup collapses same concept
# ---------------------------------------------------------------------------


def test_top_issues_dedup_collapses_same_concept(tmp_path):
    """One concept that triggers BOTH eva_recoverable_mismatch AND
    pass_c_reorder must yield a single top_issues entry whose `also_flagged`
    lists the secondary kind.
    """
    # Build a concept with: Eva at rank 2 (mismatch + recoverable) AND
    # revised_by_group_pass = True (pass_c_reorder).
    candidates = [
        ("file_a.pdf", "Top", 0.95),
        ("file_b.pdf", "Eva", 0.85),
    ]
    extras = {
        "ranking_concepts_extras": {
            "demo_concept": {
                "concept_id": "demo_concept",
                "status": "ranked",
                "ranked": [
                    {
                        "candidate_id": "file_a.pdf::demo_concept::0",
                        "source_path": "file_a.pdf",
                        "value": "Top", "confidence": 0.95, "rationale": "",
                    },
                    {
                        "candidate_id": "file_b.pdf::demo_concept::0",
                        "source_path": "file_b.pdf",
                        "value": "Eva", "confidence": 0.85, "rationale": "",
                    },
                ],
                "has_conflict": False,
                "conflict_note": "",
                "group_factor_considered": "synthetic factor for pass C",
                "revised_by_group_pass": True,
                "attempts": 1,
                "elapsed_ms": 100,
                "model": "test",
            }
        }
    }
    project = _make_synthetic_project(
        tmp_path, candidate_values=candidates, eva_value="Eva", extras=extras,
    )
    trace = build_trace(project)
    demo_issues = [
        it for it in trace.top_issues
        if it.get("concept_id") == "demo_concept"
    ]
    assert len(demo_issues) == 1, (
        f"expected exactly 1 top_issue for demo_concept, got {len(demo_issues)}: "
        f"{[it['kind'] for it in demo_issues]}"
    )
    primary = demo_issues[0]
    kinds_present = {primary["kind"], *(primary.get("also_flagged") or [])}
    assert "eva_recoverable_mismatch" in kinds_present
    assert "pass_c_reorder" in kinds_present


# ---------------------------------------------------------------------------
# API tests (stage 5 endpoint smoke tests)
# ---------------------------------------------------------------------------


def test_api_trace_endpoint_404_for_missing_project(tmp_path, monkeypatch):
    """The /api/ai-pipeline/trace/ endpoint returns 404 for an unknown project."""
    from fastapi.testclient import TestClient

    # Point the wizard service at a temporary reference root with no projects.
    from web import wizard_service
    monkeypatch.setattr(wizard_service, "_REF_DIR", tmp_path)

    from web.server import app  # late import after monkeypatch
    client = TestClient(app)
    resp = client.get("/api/ai-pipeline/trace/nonexistent-project")
    assert resp.status_code == 404


def test_api_trace_endpoint_returns_cached_trace(tmp_path, monkeypatch):
    """When a trace JSON exists on disk, GET returns it with cached=true."""
    from fastapi.testclient import TestClient

    project = _make_synthetic_project(tmp_path)
    # Write the trace once so loading from cache is exercised.
    trace = build_trace(project)
    save_trace(trace, project)

    # Configure the wizard service to find this project.
    from web import wizard_service
    monkeypatch.setattr(wizard_service, "_REF_DIR", tmp_path)

    from web.server import app
    client = TestClient(app)
    resp = client.get(f"/api/ai-pipeline/trace/{project.name}")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["cached"] is True
    assert payload["trace"]["project_name"] == project.name
