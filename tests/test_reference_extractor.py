"""Tests for automation.reference_extractor post-processing guards."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.reference_extractor import (
    ExtractedVariable,
    ExtractionResult,
    _flatten_loop_table_concepts,
    _guard_architect_client_conflation,
    _is_table_header_row,
    _is_table_header_value,
    _merge_with_prior,
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


def _ev_list(value: list) -> ExtractedVariable:
    return ExtractedVariable(
        value=value,
        position="t12",
        position_description="Loop table",
        confidence=0.85,
        extraction_method="loop_table",
    )


def test_is_table_header_value_recognizes_common_phrases():
    assert _is_table_header_value("Nº assaig")
    assert _is_table_header_value("nº assaig")
    assert _is_table_header_value("Punt")
    assert _is_table_header_value("Prof. Extracció (m)")
    assert _is_table_header_value("Litologia")
    assert _is_table_header_value("N30")
    # Real values must NOT be flagged as headers.
    assert not _is_table_header_value("P-1")
    assert not _is_table_header_value("S-2")
    assert not _is_table_header_value("+188.20")
    assert not _is_table_header_value("")
    # Non-string passes through safely.
    assert not _is_table_header_value(None)
    assert not _is_table_header_value(42)


def test_flatten_geotech_rows_top_stratum():
    res = _make_result()
    res.variables["geotech_rows"] = _ev_list([
        {
            "name": "1er nivell. Graves",
            "nb": "25-R",
            "n": "54",
            "density": "2.0",
            "cohesion": "0.05",
            "phi": "39º",
            "E": "450",
        },
    ])

    _flatten_loop_table_concepts(res)

    assert res.variables["geomech_E"].value == "450"
    assert res.variables["geomech_E"].extraction_method == "table_flatten"
    # phi must lose the degree symbol.
    assert res.variables["geomech_phi"].value == "39"
    assert res.variables["geomech_cohesion"].value == "0.05"
    # density column maps to geomech_gamma concept (synonyms in geotech).
    assert res.variables["geomech_gamma"].value == "2.0"


def test_flatten_dpsh_first_cota_to_cota_referencia():
    res = _make_result()
    res.variables["dpsh_tests"] = ExtractedVariable(
        value=[
            {"test_id": "P-1", "cota": "+188.20", "depth": "-1.60",
             "refusal": "Si", "water": "-1.00"},
            {"test_id": "P-2", "cota": "+188.20", "depth": "-1.30",
             "refusal": "Si", "water": "-1.00"},
        ],
        position="t4",
        position_description="Loop table",
        confidence=0.85,
        extraction_method="loop_table",
    )

    _flatten_loop_table_concepts(res)

    assert "cota_referencia" in res.variables
    assert res.variables["cota_referencia"].value == "+188.20"
    assert res.variables["cota_referencia"].extraction_method == "table_flatten"


def test_header_row_contamination_filtered():
    """A row whose values are header phrases must be detected as a header."""
    header_row = {
        "test_id": "Nº assaig",
        "cota": "Punt",
        "depth": "Prof. Extracció (m)",
        "spt_ma": "N30",
        "water": "Litologia",
    }
    real_row = {
        "test_id": "SPT-1",
        "cota": "P-3",
        "depth": "-0.80 a -1.40",
        "spt_ma": "20",
        "water": "Llims compactes",
    }
    assert _is_table_header_row(header_row)
    assert not _is_table_header_row(real_row)


def test_flatten_does_not_overwrite_existing_flat_key():
    res = _make_result()
    res.variables["geomech_E"] = ExtractedVariable(
        value="650",
        position="p123",
        position_description="From positional",
        confidence=0.9,
        extraction_method="paragraph_single",
    )
    res.variables["geotech_rows"] = _ev_list([
        {"name": "x", "density": "2.0", "cohesion": "0.0",
         "phi": "38º", "E": "450"},
    ])

    _flatten_loop_table_concepts(res)

    # Positional value wins; flatten is fallback.
    assert res.variables["geomech_E"].value == "650"
    assert res.variables["geomech_E"].extraction_method == "paragraph_single"
    # But other flatten targets that didn't exist are filled.
    assert res.variables["geomech_phi"].value == "38"


def test_flatten_skips_when_first_row_is_header_contamination():
    """If somehow the first row IS a header, flatten must not poison concepts."""
    res = _make_result()
    res.variables["geotech_rows"] = _ev_list([
        {"name": "name", "density": "density", "cohesion": "cohesion",
         "phi": "phi", "E": "E"},
    ])

    _flatten_loop_table_concepts(res)

    assert "geomech_E" not in res.variables
    assert "geomech_phi" not in res.variables


def test_flatten_picks_bearing_stratum_for_multi_layer():
    """For multi-layer tables, flatten must pick the LAST row (bearing
    stratum), not the first. See docs/INVESTIGACIO-GEOMECH-STRATUM.md.
    """
    res = _make_result()
    # Alcoletge-like profile: top = weak fill, bearing = competent lutites.
    res.variables["geotech_rows"] = _ev_list([
        {
            "name": "1er nivell. Sorres argiloses de rebliment",
            "nb": "5-0",
            "n": "--",
            "density": "1.80",
            "cohesion": "0.00",
            "phi": "28º",
            "E": "50",
        },
        {
            "name": "2n nivell. Lutites alterades",
            "nb": "R",
            "n": "20",
            "density": "2.00",
            "cohesion": "1.00",
            "phi": "30º",
            "E": "400",
        },
    ])

    _flatten_loop_table_concepts(res)

    # Bearing stratum (row 1) wins, NOT row 0.
    assert res.variables["geomech_E"].value == "400"
    assert res.variables["geomech_phi"].value == "30"
    assert res.variables["geomech_cohesion"].value == "1.00"
    assert res.variables["geomech_gamma"].value == "2.00"


def test_flatten_unchanged_for_single_layer():
    """For single-layer tables, flatten still picks row 0 (which is also
    the bearing stratum). Confirms the bearing-row change doesn't regress
    single-layer projects (Bell-Lloc, Castellar, Rubí, Anciles).
    """
    res = _make_result()
    res.variables["geotech_rows"] = _ev_list([
        {
            "name": "1er nivell. Graves",
            "nb": "25-R",
            "n": "54",
            "density": "2.0",
            "cohesion": "0.0",
            "phi": "38º",
            "E": "650",
        },
    ])

    _flatten_loop_table_concepts(res)

    assert res.variables["geomech_E"].value == "650"
    assert res.variables["geomech_phi"].value == "38"
    assert res.variables["geomech_cohesion"].value == "0.0"
    assert res.variables["geomech_gamma"].value == "2.0"


def test_flatten_position_records_bearing_idx():
    """The `position` and `position_description` fields must record which
    row was picked, so downstream tools can trace bearing-stratum selection.
    """
    res = _make_result()
    res.variables["geotech_rows"] = _ev_list([
        {"name": "top", "density": "1.80", "cohesion": "0.0",
         "phi": "28", "E": "50"},
        {"name": "mid", "density": "1.95", "cohesion": "0.5",
         "phi": "29", "E": "200"},
        {"name": "bearing", "density": "2.20", "cohesion": "1.0",
         "phi": "35", "E": "500"},
    ])

    _flatten_loop_table_concepts(res)

    # Bearing index = 2 (last of 3 rows).
    assert res.variables["geomech_E"].value == "500"
    assert "row2" in res.variables["geomech_E"].position
    assert "row2" in res.variables["geomech_phi"].position
    assert "bearing stratum" in res.variables["geomech_E"].position_description


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


# ---------------------------------------------------------------------------
# _merge_with_prior tests
# ---------------------------------------------------------------------------

def _write_prior(path: Path, variables: dict) -> None:
    payload = {
        "project": "test",
        "source_file": "x.docx",
        "extraction_date": "2026-04-01",
        "template_file": "g3dt-jinja-template.docx",
        "extractor_version": "1.0",
        "statistics": {},
        "variables": variables,
        "warnings": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def _ia_entry(value: str) -> dict:
    return {
        "value": value,
        "position": "ia",
        "position_description": "External LLM extraction",
        "confidence": 0.85,
        "extraction_method": "intelligent_analysis",
        "template_text": "",
        "reference_text": "",
    }


def test_merge_preserves_external_extraction_methods(tmp_path):
    """Prior `intelligent_analysis` entries must survive re-extraction."""
    prior = tmp_path / "eva_reference_values.json"
    _write_prior(prior, {
        "client": _ia_entry("Acme SL"),
        "site_description": _ia_entry("La parcel·la es troba ..."),
    })

    res = _make_result()
    res.variables["building_height_m"] = _ev("9.50")  # new positional value

    _merge_with_prior(res, prior)

    assert "client" in res.variables
    assert res.variables["client"].value == "Acme SL"
    assert res.variables["client"].extraction_method == "intelligent_analysis"
    assert res.variables["site_description"].value.startswith("La parcel")
    # New value untouched.
    assert res.variables["building_height_m"].value == "9.50"


def test_merge_does_not_resurrect_own_methods(tmp_path):
    """Prior entries with our own extraction_method are dropped — absence
    in the new run is deliberate."""
    prior = tmp_path / "eva_reference_values.json"
    _write_prior(prior, {
        "obsolete_field": {
            "value": "stale",
            "position": "p1",
            "position_description": "old",
            "confidence": 0.9,
            "extraction_method": "paragraph_single",
            "template_text": "",
            "reference_text": "",
        },
    })

    res = _make_result()
    _merge_with_prior(res, prior)

    assert "obsolete_field" not in res.variables


def test_merge_does_not_overwrite_new_extraction(tmp_path):
    """When both prior and new emit the same key, NEW wins."""
    prior = tmp_path / "eva_reference_values.json"
    _write_prior(prior, {
        "client_name": _ia_entry("OLD VALUE"),
    })

    res = _make_result()
    res.variables["client_name"] = _ev("NEW VALUE")

    _merge_with_prior(res, prior)

    assert res.variables["client_name"].value == "NEW VALUE"
    assert res.variables["client_name"].extraction_method == "exact"


def test_merge_handles_missing_prior_file(tmp_path, caplog):
    """No prior file = clean no-op, no warnings."""
    prior = tmp_path / "does_not_exist.json"
    res = _make_result()

    with caplog.at_level(logging.WARNING):
        _merge_with_prior(res, prior)

    assert len(res.variables) == 0
    assert not any(
        "Could not load prior" in rec.message for rec in caplog.records
    )


def test_merge_handles_corrupt_prior_json(tmp_path, caplog):
    """Malformed prior JSON: log a warning and proceed without crashing."""
    prior = tmp_path / "eva_reference_values.json"
    prior.write_text("{ this is not valid json", encoding="utf-8")

    res = _make_result()
    res.variables["building_height_m"] = _ev("9.50")

    with caplog.at_level(logging.WARNING):
        _merge_with_prior(res, prior)

    assert any(
        "Could not load prior" in rec.message for rec in caplog.records
    )
    # Existing new entries untouched.
    assert res.variables["building_height_m"].value == "9.50"


def test_merge_is_idempotent(tmp_path):
    """Merging the same prior twice yields the same result as once."""
    prior = tmp_path / "eva_reference_values.json"
    _write_prior(prior, {
        "client": _ia_entry("Acme SL"),
    })

    res = _make_result()
    res.variables["building_height_m"] = _ev("9.50")
    _merge_with_prior(res, prior)
    snapshot_keys = sorted(res.variables.keys())
    snapshot_value = res.variables["client"].value

    _merge_with_prior(res, prior)
    assert sorted(res.variables.keys()) == snapshot_keys
    assert res.variables["client"].value == snapshot_value
