"""Tests de Fase 4a — lectors deterministes de les 5 plantilles G3 (automation/g3_templates.py).

Fixtures: reference-material/4001612 BELL-LLOC (les cel·les esperades venen de la lectura
d'or, docs/golden-read/4001612 BELL-LLOC/g3_0*.json).
"""

from pathlib import Path

import pytest

from automation.g3_templates import (
    read_comanda,
    read_dpsh_excel,
    read_fitxa_camp,
    read_plan_cost,
    read_pressupost_pdf,
    read_project,
)

ROOT = Path(__file__).resolve().parents[1]
BELL = ROOT / "reference-material" / "4001612 BELL-LLOC"

pytestmark = pytest.mark.skipif(not BELL.exists(), reason="fixtures reference-material absents")


@pytest.fixture(scope="module")
def bell():
    return read_project(BELL)


def _top(result, concept):
    cands = result["concepts"].get(concept, [])
    return cands[0] if cands else None


def test_detecta_les_cinc_plantilles(bell):
    tipus = {d["document_type"] for d in bell["documents"]}
    assert {"pressupost_g3", "fitxa_camp_g3", "comanda_lab_g3", "plan_cost_g3", "dpsh_excel"} <= tipus


def test_pressupost_cel_les(bell):
    doc = next(d for d in bell["documents"]
               if d["document_type"] == "pressupost_g3" and "25.0647" in d["source_path"])
    per_id = {}
    for s in doc["tier_a"]:
        per_id.setdefault(s["concept_id"], s)
    assert per_id["client_name"]["value"] == "ARQUITECTURA BOSCH NOVELL"
    assert per_id["client_name"]["confidence"] <= 0.5  # sol·licitant, mai autoritat
    assert per_id["street_address"]["value"] == "C/MESTRE RAMON ORTIZ 15"
    assert per_id["municipality"]["value"] == "BELL-LLOC"
    assert per_id["cte_edificacio"]["value"] == "C1"
    assert per_id["cte_sol"]["value"] == "T1"
    assert per_id["num_dpsh_tests"]["value"] == 2
    assert per_id["num_sondeigs"]["value"] == 1
    assert per_id["expedient_comercial"]["value"] == "25·0647"


def test_fitxa_camp_cel_les(bell):
    doc = next(d for d in bell["documents"] if d["document_type"] == "fitxa_camp_g3")
    per_id = {s["concept_id"]: s for s in doc["tier_a"]}
    assert per_id["field_date"]["value"] == "2025-10-01"
    assert "fitxa!F38" in per_id["field_date"]["location"]
    assert "MESTRE RAMON ORTIZ" in per_id["street_address"]["value"].upper()
    assert per_id["lab_field_company"]["value"] == "TPS ERUGA"


def test_comanda_cel_les(bell):
    doc = next(d for d in bell["documents"] if d["document_type"] == "comanda_lab_g3")
    per_id = {}
    for s in doc["tier_a"]:
        per_id.setdefault(s["concept_id"], s)
    assert per_id["expedient"]["value"] == "4001612"
    assert per_id["expedient"]["location"].startswith("Hoja1!N19")
    assert per_id["lab_sample_id"]["value"] == "SPT 1 (S1)"
    assert per_id["lab_depth"]["value"] == "1.0 - 1.6"
    assert per_id["lab_location"]["value"] == "S1"
    assert per_id["municipality"]["value"] == "BELL-LLOC"
    assert "G3" in per_id["NOT_client_name"]["value"]  # bloc sol·licitant descartat explícitament


def test_plan_cost_cel_les(bell):
    doc = next(d for d in bell["documents"] if d["document_type"] == "plan_cost_g3")
    per_id = {}
    for s in doc["tier_a"]:
        per_id.setdefault(s["concept_id"], s)
    assert per_id["building_type"]["value"] == "EG HAB UNIF BELL-LLOC"
    assert per_id["num_dpsh_tests"]["value"] == 2
    assert per_id["num_dpsh_tests"]["location"] == "OFERTA!B21"


def test_dpsh_excel_executats(bell):
    doc = next(d for d in bell["documents"] if d["document_type"] == "dpsh_excel")
    per_id = {s["concept_id"]: s for s in doc["tier_a"] if s["concept_id"] == "num_dpsh_tests"}
    assert per_id["num_dpsh_tests"]["value"] == 2
    assert "P-1" in per_id["num_dpsh_tests"]["quote"]


def test_agregacio_prioritats(bell):
    # expedient: comanda N19 primer; field_date: fitxa F38 primer; num_dpsh: executats de l'Excel
    assert _top(bell, "expedient")["document_type"] == "comanda_lab_g3"
    assert _top(bell, "field_date")["document_type"] == "fitxa_camp_g3"
    top_dpsh = _top(bell, "num_dpsh_tests")
    assert top_dpsh["document_type"] == "dpsh_excel"
    assert "EXECUTATS" in top_dpsh["note"]


def test_lectors_rebutgen_fitxers_aliens():
    # cada lector torna None per a un fitxer que no és la seva plantilla
    comanda = BELL / "comanda laboratori_4001612_BELL-LLOC.xls"
    dpsh = BELL / "ANNEXES" / "4001612_DPSH.xls"
    fitxa = BELL / "25.0647" / "DADES PER ANAR A CAMP_v1.xlsx"
    plan = BELL / "25.0647" / "PLAN_COST_BELL-LLOC.xlsx"
    pressupost = BELL / "25.0647" / "PRESSUPOST GEOTEC.BELL-LLOC.pdf"
    assert read_comanda(dpsh) is None
    assert read_dpsh_excel(comanda) is None
    assert read_fitxa_camp(plan) is None
    assert read_plan_cost(fitxa) is None
    assert read_pressupost_pdf(BELL / "25.0647" / "4613172CG1141S0001SU-15.pdf") is None
    assert read_pressupost_pdf(pressupost) is not None


def test_exclou_validation_i_generats(bell):
    for d in bell["documents"]:
        assert "validation" not in d["source_path"]
        assert "generated" not in d["source_path"].lower()
