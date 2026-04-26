"""Tests for automation.reference_extractor post-processing guards."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.reference_extractor import (
    ExtractedVariable,
    ExtractionResult,
    _guard_architect_client_conflation,
)


def _make_result() -> ExtractionResult:
    return ExtractionResult(
        project="test",
        source_file="x.docx",
        extraction_date="2026-04-25",
        template_file="g3dt-jinja-template.docx",
    )


def _ev(value: str, confidence: float = 0.9) -> ExtractedVariable:
    return ExtractedVariable(
        value=value,
        position="body[1]",
        position_description="",
        confidence=confidence,
        extraction_method="exact",
    )


def test_guard_flags_architect_equals_client():
    res = _make_result()
    res.variables["architect_name"] = _ev("Joan Planes")
    res.variables["client_name"] = _ev("Joan Planes")

    _guard_architect_client_conflation(res)

    assert any("architect_name == client_name" in w for w in res.warnings)
    # value preserved; confidence not zeroed for this heuristic.
    assert res.variables["architect_name"].value == "Joan Planes"
    assert res.variables["architect_name"].confidence == 0.9


def test_guard_flags_body_sentence_pattern():
    res = _make_result()
    res.variables["architect_name"] = _ev("Sr. Carles Vidal en nom propi")
    res.variables["client_name"] = _ev("Acme SL")

    _guard_architect_client_conflation(res)

    assert any("body-sentence pattern" in w for w in res.warnings)
    # Heuristic 2 lowers confidence to signal low trust.
    assert res.variables["architect_name"].confidence == 0.0


def test_guard_flags_architect_name_upper_too():
    res = _make_result()
    res.variables["architect_name_upper"] = _ev("JOAN PLANES")
    res.variables["client_name"] = _ev("Joan Planes")

    _guard_architect_client_conflation(res)

    assert any(
        "architect_name_upper == client_name" in w for w in res.warnings
    )


def test_guard_no_warning_when_distinct():
    res = _make_result()
    res.variables["architect_name"] = _ev("Joan Planes")
    res.variables["client_name"] = _ev("Acme SL")

    _guard_architect_client_conflation(res)

    assert not any(
        "architect_name == client_name" in w
        or "body-sentence pattern" in w
        for w in res.warnings
    )
    assert res.variables["architect_name"].confidence == 0.9


def test_guard_handles_missing_fields():
    res = _make_result()
    # Only architect_name present, no client_name — must not crash.
    res.variables["architect_name"] = _ev("Joan Planes")

    _guard_architect_client_conflation(res)

    # No equality warning possible without client_name.
    assert not any(
        "architect_name == client_name" in w for w in res.warnings
    )


def test_guard_catches_sra_and_d_variants():
    """S1: the body-sentence guard fires on `Sra. X`, `D. X`, `Dna. X` —
    not just `Sr. X`. All four are honorifics used in Eva's body sentences."""
    for raw in (
        "Sra. María García en nom propi",
        "D. Joan Planes",
        "Dna. Anna Soler en nom propi",
    ):
        res = _make_result()
        res.variables["architect_name"] = _ev(raw)
        res.variables["client_name"] = _ev("Acme SL")

        _guard_architect_client_conflation(res)

        assert any("body-sentence pattern" in w for w in res.warnings), (
            f"expected body-sentence guard to fire for {raw!r}"
        )
        assert res.variables["architect_name"].confidence == 0.0, (
            f"expected confidence zeroed for {raw!r}"
        )
