"""Tests per al contracte del schema v1 de `_decisions.json` (Fase 1).

Vegeu `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` §4 i §9-Fase-1.

Dues famílies de tests:

1. Fixtures REALS (`docs/golden-read*`, read-only): `adapt_legacy` +
   `validate_decisions` ha de donar `[]` (net) per als 4 projectes triats
   pel disseny (2 escalars + 2 taules).
2. Negatius sintètics: cadascuna de les regles dures del contracte, violada
   deliberadament, ha de produir almenys un error.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.lectura.contract import adapt_legacy, validate_decisions

GOLDEN_READ = PROJECT_ROOT / "docs" / "golden-read"
GOLDEN_READ_TAULES = PROJECT_ROOT / "docs" / "golden-read-taules"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Fixtures reals (docs/golden-read*) — adaptats han de validar net
# ---------------------------------------------------------------------------

GOLDEN_SCALAR_FIXTURES = [
    GOLDEN_READ / "4001612 BELL-LLOC" / "_decisions.json",
    GOLDEN_READ / "3001631 RUBI" / "_decisions.json",
]

GOLDEN_TABLE_FIXTURES = [
    GOLDEN_READ_TAULES / "4001612 BELL-LLOC" / "_tables_decisions.json",
    GOLDEN_READ_TAULES / "4001679 ANCILES" / "_tables_decisions.json",
]


@pytest.mark.parametrize("fixture_path", GOLDEN_SCALAR_FIXTURES, ids=lambda p: p.parent.name)
def test_golden_scalar_fixture_adapts_clean(fixture_path: Path):
    assert fixture_path.exists(), f"fixture no trobat: {fixture_path}"
    legacy = _load(fixture_path)

    adapted = adapt_legacy(legacy)
    errors = validate_decisions(adapted)

    assert errors == [], f"{fixture_path.parent.name}: {errors}"
    # sanity: l'adaptació ha produït els 21 camps esperats (22 - architect_company,
    # absent als fixtures d'or), no un dict buit per error silenciós.
    assert len(adapted["fields"]) >= 15


@pytest.mark.parametrize("fixture_path", GOLDEN_TABLE_FIXTURES, ids=lambda p: p.parent.name)
def test_golden_table_fixture_adapts_clean(fixture_path: Path):
    assert fixture_path.exists(), f"fixture no trobat: {fixture_path}"
    legacy = _load(fixture_path)

    adapted = adapt_legacy(legacy)
    errors = validate_decisions(adapted)

    assert errors == [], f"{fixture_path.parent.name}: {errors}"
    # sanity: com a mínim dpsh_tests i soil_levels han de portar files reals.
    assert adapted["tables"]["dpsh_tests"]["rows"]
    assert adapted["tables"]["soil_levels"]["rows"]


def test_golden_fixtures_are_not_mutated_by_adapt_legacy():
    """adapt_legacy no ha de tocar el fixture original (read-only, evidència tancada)."""
    fixture_path = GOLDEN_SCALAR_FIXTURES[0]
    before = _load(fixture_path)
    snapshot = copy.deepcopy(before)

    adapt_legacy(before)

    assert before == snapshot


# ---------------------------------------------------------------------------
# 2. Negatius sintètics
# ---------------------------------------------------------------------------


def _minimal_valid_doc() -> dict:
    """Un `_decisions.json` v1 mínim però vàlid, per mutar-lo als tests negatius."""
    return {
        "schema_version": 1,
        "project": "TEST",
        "generated": "2026-08-24T00:00:00",
        "fields": {
            "expedient": {
                "estat": "segur",
                "value": "1234567",
                "candidates": [
                    {"value": "1234567", "font": "comanda", "quote": "1234567"},
                ],
                "rule": "test",
                "sources_checked": ["comanda"],
                "note": None,
            },
        },
        "tables": {
            "spt_ma_tests": {
                "estat_bloc": "candidats",
                "rows": [
                    {
                        "id_assaig": "SPT-1",
                        "estat": "candidats",
                        "n30": {
                            "estat": "candidats",
                            "value": "40",
                            "candidates": [
                                {"value": "40", "font": "tall", "quote": "N=40"},
                            ],
                            "registre": ["10", "20", "20", "10"],
                            "rule": "test",
                        },
                    }
                ],
            },
            "soil_levels": {
                "estat_bloc": "candidats",
                "rows": [
                    {
                        "nom": "1er nivell",
                        "estat": "candidats",
                        "litologia": {
                            "estat": "candidats",
                            "value": "Graves",
                            "candidates": [
                                {"value": "Graves", "font": "tall", "quote": "Graves"},
                            ],
                            "rule": "test",
                        },
                    }
                ],
            },
            "dpsh_tests": {
                "estat_bloc": "segur",
                "rows": [
                    {
                        "punt": "P-1",
                        "estat": "segur",
                        "nivell_freatic": {
                            "estat": "segur",
                            "value": "No detectat",
                            "candidates": [
                                {"value": "No detectat", "font": "excel", "quote": "(buit)"},
                            ],
                            "matis": None,
                            "rule": "test",
                        },
                    }
                ],
            },
        },
        "sources_read": [],
        "notes_estructurals": [],
    }


def test_minimal_valid_doc_has_no_errors():
    """El fixture sintètic base ha de validar net (control dels negatius)."""
    assert validate_decisions(_minimal_valid_doc()) == []


def test_n30_segur_is_rejected():
    doc = _minimal_valid_doc()
    doc["tables"]["spt_ma_tests"]["rows"][0]["n30"]["estat"] = "segur"

    errors = validate_decisions(doc)

    assert any("n30" in e and "segur" in e for e in errors)


def test_litologia_segur_is_rejected():
    doc = _minimal_valid_doc()
    doc["tables"]["soil_levels"]["rows"][0]["litologia"]["estat"] = "segur"

    errors = validate_decisions(doc)

    assert any("litologia" in e and "segur" in e for e in errors)


def test_candidats_without_candidates_is_rejected():
    doc = _minimal_valid_doc()
    doc["fields"]["expedient"]["estat"] = "candidats"
    doc["fields"]["expedient"]["candidates"] = []

    errors = validate_decisions(doc)

    assert any("fields.expedient.candidates" in e for e in errors)


def test_unknown_estat_is_rejected():
    doc = _minimal_valid_doc()
    doc["fields"]["expedient"]["estat"] = "probable"

    errors = validate_decisions(doc)

    assert any("fields.expedient.estat" in e for e in errors)


def test_unknown_field_key_is_rejected():
    doc = _minimal_valid_doc()
    doc["fields"]["camp_inventat"] = copy.deepcopy(doc["fields"]["expedient"])

    errors = validate_decisions(doc)

    assert any("camp_inventat" in e and "desconeguda" in e for e in errors)


def test_old_dialect_status_key_is_rejected():
    doc = _minimal_valid_doc()
    doc["fields"]["expedient"]["status"] = doc["fields"]["expedient"].pop("estat")

    errors = validate_decisions(doc)

    assert any("status" in e and "dialecte antic" in e for e in errors)


def test_old_dialect_source_key_is_rejected():
    doc = _minimal_valid_doc()
    doc["fields"]["expedient"]["candidates"][0]["source"] = doc["fields"]["expedient"]["candidates"][0].pop("font")

    errors = validate_decisions(doc)

    assert any("source" in e and "dialecte antic" in e for e in errors)


def test_no_trobat_with_empty_sources_checked_is_rejected():
    doc = _minimal_valid_doc()
    doc["fields"]["expedient"] = {
        "estat": "no_trobat",
        "value": None,
        "candidates": [],
        "rule": "test",
        "sources_checked": [],
        "note": None,
    }

    errors = validate_decisions(doc)

    assert any("fields.expedient.sources_checked" in e for e in errors)


def test_invalid_matis_is_rejected():
    doc = _minimal_valid_doc()
    doc["tables"]["dpsh_tests"]["rows"][0]["nivell_freatic"]["matis"] = "molla"

    errors = validate_decisions(doc)

    assert any("matis" in e for e in errors)


def test_candidats_value_mismatch_is_rejected():
    doc = _minimal_valid_doc()
    doc["fields"]["expedient"]["estat"] = "candidats"
    doc["fields"]["expedient"]["value"] = "9999999"

    errors = validate_decisions(doc)

    assert any("fields.expedient.value" in e for e in errors)


def test_missing_schema_version_is_rejected():
    doc = _minimal_valid_doc()
    del doc["schema_version"]

    errors = validate_decisions(doc)

    assert any("schema_version" in e for e in errors)
