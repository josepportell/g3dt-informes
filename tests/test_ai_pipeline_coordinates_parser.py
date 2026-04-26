"""Tests for automation.ai_pipeline.coordinates_parser."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.coordinates_parser import (
    candidates_from_coordenades,
    parse_coordenades_txt,
)


# ---------------------------------------------------------------------------
# parse_coordenades_txt
# ---------------------------------------------------------------------------


_ALCOLETGE_CONTENT = (
    "Coordenades UTM (X);(Y);(Z);\n"
    "P-1\n"
    "308781,86 ; 4613950.63 ; 198.9\n"
)


def test_parse_coordenades_alcoletge_format(tmp_path):
    p = tmp_path / "COORDENADES.txt"
    p.write_text(_ALCOLETGE_CONTENT, encoding="utf-8")
    rows = parse_coordenades_txt(p)
    assert rows == [{
        "test_point_id": "P-1",
        "utm_x": 308781.86,
        "utm_y": 4613950.63,
        "utm_z": 198.9,
    }]


def test_parse_coordenades_real_alcoletge_file():
    """Use the actual reference-material file (skip if not present)."""
    real = (
        Path(__file__).resolve().parent.parent
        / "reference-material"
        / "4001670 ALCOLETGE"
        / "ANNEXES"
        / "COORDENADES.txt"
    )
    if not real.is_file():
        import pytest

        pytest.skip("real Alcoletge COORDENADES.txt not present in working tree")
    rows = parse_coordenades_txt(real)
    assert rows == [{
        "test_point_id": "P-1",
        "utm_x": 308781.86,
        "utm_y": 4613950.63,
        "utm_z": 198.9,
    }]


def test_parse_coordenades_handles_comma_decimals(tmp_path):
    p = tmp_path / "COORDENADES.txt"
    p.write_text(
        "Coordenades UTM (X);(Y);(Z);\n"
        "P-1\n"
        "308781,86 ; 4613950,63 ; 198,9\n",
        encoding="utf-8",
    )
    rows = parse_coordenades_txt(p)
    assert rows is not None and len(rows) == 1
    assert rows[0]["utm_x"] == 308781.86
    assert rows[0]["utm_y"] == 4613950.63
    assert rows[0]["utm_z"] == 198.9


def test_parse_coordenades_handles_missing_z(tmp_path):
    p = tmp_path / "COORDENADES.txt"
    p.write_text(
        "Coordenades UTM (X);(Y);\n"
        "P-1\n"
        "308781.86 ; 4613950.63\n",
        encoding="utf-8",
    )
    rows = parse_coordenades_txt(p)
    assert rows is not None and len(rows) == 1
    assert rows[0]["utm_z"] is None


def test_parse_coordenades_returns_none_on_garbage(tmp_path):
    p = tmp_path / "COORDENADES.txt"
    p.write_text("not a header\nnot a row either\nplain prose only\n", encoding="utf-8")
    assert parse_coordenades_txt(p) is None


def test_parse_coordenades_handles_multiple_rows(tmp_path):
    p = tmp_path / "COORDENADES.txt"
    p.write_text(
        "Coordenades UTM (X);(Y);(Z);\n"
        "P-1\n"
        "308781,86 ; 4613950.63 ; 198.9\n"
        "P-2\n"
        "308782,11 ; 4613951.04 ; 198.7\n",
        encoding="utf-8",
    )
    rows = parse_coordenades_txt(p)
    assert rows is not None and len(rows) == 2
    assert rows[0]["test_point_id"] == "P-1"
    assert rows[1]["test_point_id"] == "P-2"
    assert rows[1]["utm_x"] == 308782.11


def test_parse_coordenades_handles_bom(tmp_path):
    p = tmp_path / "COORDENADES.txt"
    p.write_bytes(("﻿" + _ALCOLETGE_CONTENT).encode("utf-8"))
    rows = parse_coordenades_txt(p)
    assert rows is not None and len(rows) == 1


def test_parse_coordenades_returns_none_on_missing_file(tmp_path):
    assert parse_coordenades_txt(tmp_path / "missing.txt") is None


# ---------------------------------------------------------------------------
# candidates_from_coordenades
# ---------------------------------------------------------------------------


def test_candidates_from_coordenades_emits_xyz():
    rows = [{
        "test_point_id": "P-1",
        "utm_x": 308781.86,
        "utm_y": 4613950.63,
        "utm_z": 198.9,
    }]
    cands = candidates_from_coordenades(rows, source_path="ANNEXES/COORDENADES.txt")
    by_concept = {c.concept_id: c for c in cands}
    assert set(by_concept) == {"utm_x", "utm_y", "utm_z"}
    assert by_concept["utm_x"].value == 308781.86
    assert by_concept["utm_x"].confidence == 1.0
    assert by_concept["utm_x"].extractor == "coordinates_parser"
    assert by_concept["utm_x"].source_path == "ANNEXES/COORDENADES.txt"


def test_candidates_from_coordenades_skips_missing_z():
    rows = [{
        "test_point_id": "P-1",
        "utm_x": 308781.86,
        "utm_y": 4613950.63,
        "utm_z": None,
    }]
    cands = candidates_from_coordenades(rows, source_path="ANNEXES/COORDENADES.txt")
    by_concept = {c.concept_id: c for c in cands}
    assert "utm_z" not in by_concept
    assert {"utm_x", "utm_y"} <= set(by_concept)


def test_candidates_from_coordenades_uses_first_row_only():
    rows = [
        {"test_point_id": "P-1", "utm_x": 1.0, "utm_y": 2.0, "utm_z": 3.0},
        {"test_point_id": "P-2", "utm_x": 99.0, "utm_y": 99.0, "utm_z": 99.0},
    ]
    cands = candidates_from_coordenades(rows, source_path="x.txt")
    by_concept = {c.concept_id: c for c in cands}
    assert by_concept["utm_x"].value == 1.0
    assert by_concept["utm_y"].value == 2.0
    assert by_concept["utm_z"].value == 3.0


def test_candidates_from_coordenades_empty_rows():
    assert candidates_from_coordenades([], source_path="x.txt") == []
