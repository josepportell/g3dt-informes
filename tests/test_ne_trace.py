"""Tests for the NE-trace classifier in scripts/diagnostic_trace.py.

Each test exercises one branch of `_classify_ne_reason` with a minimal
in-memory fixture (no pipeline runs, no filesystem reads beyond the schema).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from diagnostic_trace import (  # noqa: E402
    _classify_ne_reason,
    _load_concept_schema,
    _NON_EXTRACTOR_SOURCES,
)


@pytest.fixture(scope="module")
def schema() -> dict:
    return _load_concept_schema()


def test_classify_schema_missing(schema: dict) -> None:
    """Concept not in YAML schema → schema_missing."""
    reason, fix, roles = _classify_ne_reason(
        concept_id="access_street",
        schema=schema,
        fm_roles=set(),
        concept_sources={},
        signals_count=0,
    )
    assert reason == "schema_missing"
    assert "schemas/concepts/report_variables.yaml" in fix
    assert roles == []


def test_classify_no_extractor(schema: dict) -> None:
    """Concept with only user/computed sources → no_extractor."""
    # table_dpsh_range has source_priority {user: 10, computed: 20}
    # (building_structure_desc used to fit this; Phase B added llm_synthesis
    # to it, so this test picks a still-pure computed concept instead.)
    entry = schema.get("table_dpsh_range")
    assert entry is not None, "fixture concept missing from schema"
    assert set(entry["source_priority"].keys()).issubset(_NON_EXTRACTOR_SOURCES)

    reason, fix, _ = _classify_ne_reason(
        concept_id="table_dpsh_range",
        schema=schema,
        fm_roles=set(),
        concept_sources={},
        signals_count=0,
    )
    assert reason == "no_extractor"
    assert "fileminer" in fix or "vision" in fix or "extractor" in fix


def test_classify_no_source_file(schema: dict) -> None:
    """Concept needs architect_plan, project lacks it → no_source_file."""
    reason, fix, roles = _classify_ne_reason(
        concept_id="num_floors",
        schema=schema,
        fm_roles=set(),  # no architect_plan present
        concept_sources={},
        signals_count=0,
    )
    assert reason == "no_source_file"
    assert "architect_plan" in roles or "architect_plan_with_points" in roles
    assert "lacks" in fix.lower() or "missing" in fix.lower()


def test_classify_file_had_no_match(schema: dict) -> None:
    """Architect plan present, no concept_map sources, no signals → file_had_no_match."""
    reason, fix, roles = _classify_ne_reason(
        concept_id="num_floors",
        schema=schema,
        fm_roles={"architect_plan"},
        concept_sources={},  # ConceptScout found nothing
        signals_count=0,
    )
    assert reason == "file_had_no_match"
    assert "tighten" in fix.lower() or "extractor" in fix.lower()


def test_classify_extracted_but_filtered(schema: dict) -> None:
    """Signals were emitted but variable still NE → extracted_but_filtered."""
    reason, fix, _ = _classify_ne_reason(
        concept_id="num_floors",
        schema=schema,
        fm_roles={"architect_plan"},
        concept_sources={},
        signals_count=3,
    )
    assert reason == "extracted_but_filtered"
    assert "3" in fix
    assert "filtered" in fix or "competition" in fix or "lost" in fix


def test_classify_extracted_low_confidence(schema: dict) -> None:
    """concept_map has entries but all confidence below threshold → extracted_low_confidence."""
    reason, fix, _ = _classify_ne_reason(
        concept_id="num_floors",
        schema=schema,
        fm_roles={"architect_plan"},
        concept_sources={
            "num_floors": [
                {"file": "plan.pdf", "confidence": 0.3, "extraction_method": "vision_probe"},
                {"file": "plan2.pdf", "confidence": 0.5, "extraction_method": "vision_probe"},
            ],
        },
        signals_count=0,
    )
    assert reason == "extracted_low_confidence"
    assert "confidence" in fix.lower()


def test_priority_order_schema_missing_wins(schema: dict) -> None:
    """schema_missing trumps everything else (priority 1)."""
    reason, _, _ = _classify_ne_reason(
        concept_id="zzz_does_not_exist",
        schema=schema,
        fm_roles={"architect_plan"},
        concept_sources={
            "zzz_does_not_exist": [
                {"file": "plan.pdf", "confidence": 0.9},
            ],
        },
        signals_count=5,
    )
    assert reason == "schema_missing"
