"""Tests de Fase 4a — lectors deterministes de les 5 plantilles G3 (automation/g3_templates.py).

Fixtures: reference-material/4001612 BELL-LLOC (les cel·les esperades venen de la lectura
d'or, docs/golden-read/4001612 BELL-LLOC/g3_0*.json).
"""

import shutil
from pathlib import Path

import pytest

from automation.g3_templates import (
    _municipi_corroborat,
    _split_plan_cost_title,
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


# Les 8 formes reals d'E9 del corpus (els 10 PLAN_COST dels 8 projectes; Castellar
# i Cerdanyola tenen dos fitxers amb el mateix títol). El municipi és tot el que
# queda rere el tipus de projecte: ni l'última paraula ("VALLÈS", "SEGRIÀ") ni el
# residu mandrós de la descripció ("UNIF RUBI").
@pytest.mark.parametrize("e9, tipus, municipi", [
    ("EG 3 HAB UNIF CASTELLAR DEL VALLÈS", "EG 3 HAB UNIF", "CASTELLAR DEL VALLÈS"),
    ("EG HAB UNIF RUBI", "EG HAB UNIF", "RUBI"),
    ("EG HAB UNIF CERDANYOLA", "EG HAB UNIF", "CERDANYOLA"),
    ("EG HAB UNIF LINYOLA", "EG HAB UNIF", "LINYOLA"),
    ("EG HAB UNIF BELL-LLOC", "EG HAB UNIF", "BELL-LLOC"),
    ("EG AMPL ALCOLETGE", "EG AMPL", "ALCOLETGE"),
    ("EG VILANOVA SEGRIÀ", "EG", "VILANOVA SEGRIÀ"),
    ("EG 7 VIVIENDAS ANCILES", "EG 7 VIVIENDAS", "ANCILES"),
])
def test_plan_cost_titol_es_parteix_pel_tipus(e9, tipus, municipi):
    assert _split_plan_cost_title(e9) == (tipus, municipi)


def test_plan_cost_titol_desconegut_no_inventa_municipi():
    # Sense cap token de tipus per consumir no s'emet municipi (val més cap
    # candidat que un municipi inventat).
    assert _split_plan_cost_title("ESTUDI GEOTÈCNIC PER A LA NAU") == ("", "ESTUDI GEOTÈCNIC PER A LA NAU")
    assert _split_plan_cost_title("EG HAB UNIF") == ("EG HAB UNIF", "")


def test_plan_cost_nomes_ell_dona_municipi_net(tmp_path):
    """Camí PLAN_COST-only: sense comanda ni pressupost, `concepts['municipality'][0]`
    va directe a l'input `site_municipality` del wizard."""
    plan = BELL / "25.0647" / "PLAN_COST_BELL-LLOC.xlsx"
    shutil.copy2(plan, tmp_path / plan.name)
    result = read_project(tmp_path)
    muni = result["concepts"]["municipality"][0]
    assert muni["value"] == "BELL-LLOC"          # abans: "UNIF BELL-LLOC"
    assert muni["document_type"] == "plan_cost_g3"
    assert muni["confidence"] == 0.6
    # el senyal germà de la mateixa cel·la no canvia
    assert result["concepts"]["building_type"][0]["value"] == "EG HAB UNIF BELL-LLOC"


# `_PLAN_COST_TYPE_TOKENS` només té els descriptors ATESTATS: un títol amb un
# descriptor no llistat se'l queda dins del municipi ("EG REHAB NAU LLEIDA" ->
# "NAU LLEIDA") i sortiria amb la confiança d'un municipi de debò. Com que la
# forma "EG {MUNICIPI}" existeix (EG VILANOVA SEGRIÀ), no es pot distingir per
# estructura: es contrasta amb el nom del fitxer i el de la carpeta.
@pytest.mark.parametrize("municipi, context, corroborat", [
    ("CASTELLAR DEL VALLÈS", "PLAN_COST_CATELLAR DEL VALLÈS 3001621 CASTELLAR DEL VALLES", True),
    ("BELL-LLOC", "PLAN_COST_BELL-LLOC 4001612 BELL-LLOC", True),
    ("VILANOVA SEGRIÀ", "PLAN_COST 4001671 VILANOVA DE SEGRIA", True),
    ("RUBI", "PLAN_COST_RUBI 3001631 RUBI", True),
    ("ANCILES", "PLAN_COST 4001679 ANCILES", True),
    # el descriptor que s'escapa és sempre la PRIMERA paraula del residu
    ("NAU LLEIDA", "PLAN_COST_LLEIDA 3001700 LLEIDA", False),
    ("NAU INDUSTRIAL TÀRREGA", "PLAN_COST 4001700 TARREGA", False),
    ("MAGATZEM ALCOLETGE", "PLAN_COST 4001670 ALCOLETGE", False),
    ("BELL-LLOC", "", False),                 # sense res amb què contrastar, no es corrobora
])
def test_municipi_corroborat_amb_fitxer_i_carpeta(municipi, context, corroborat):
    assert _municipi_corroborat(municipi, context) is corroborat


def test_plan_cost_municipi_corroborat_per_la_carpeta(tmp_path):
    """Nom de fitxer que no diu res: qui corrobora és la carpeta del projecte.

    Des del cablejat del padró (peça 2, 2026-09-01) la confiança segueix sent 0,6 —el padró no
    en puja cap— però ara hi ha nota: «BELL-LLOC» és la forma curta de `Bell-lloc d'Urgell`, i
    la forma oficial llarga és la que mana per la regla de municipi.
    """
    plan = BELL / "25.0647" / "PLAN_COST_BELL-LLOC.xlsx"
    projecte = tmp_path / "4001612 BELL-LLOC"
    projecte.mkdir()
    shutil.copy2(plan, projecte / "PC.xlsx")

    muni = read_project(projecte)["concepts"]["municipality"][0]

    assert muni["value"] == "BELL-LLOC" and muni["confidence"] == 0.6
    assert "és la forma curta de «Bell-lloc d'Urgell»" in muni["note"]


def test_plan_cost_municipi_sense_corroborar_baixa_de_confianca(tmp_path):
    """Ni el fitxer ni la carpeta no diuen «BELL-LLOC»: el candidat s'emet igual
    (mai en blanc) però a 0,4 i amb la nota, que és el que veurà l'Eva.

    El padró NO ha de rescatar aquest cas: que «Bell-lloc» sigui un municipi de debò no vol dir
    que sigui el d'aquest projecte, i el que crida l'atenció és la contradicció amb la carpeta.
    """
    plan = BELL / "25.0647" / "PLAN_COST_BELL-LLOC.xlsx"
    projecte = tmp_path / "9999999 TORREGROSSA"
    projecte.mkdir()
    shutil.copy2(plan, projecte / "PC.xlsx")

    muni = read_project(projecte)["concepts"]["municipality"][0]

    assert muni["value"] == "BELL-LLOC" and muni["confidence"] == 0.4
    assert "verificar" in muni["note"]


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
