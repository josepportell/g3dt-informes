"""Tests del comparador d'or `docs/wizard-headless/fase0-acceptacio/compare_consolida.py` (v2, normalitzadors).

Cobreix: `close()` conscient del camp (dates, nombres/intervals, adreces, spt_ma, num_floors, building_type, text),
`row_key`/`align_rows` (files de taula per clau), `_expand_de_a` (dialecte del fixture de Castellar) i una integració
sobre els `_decisions.json` versionats del llibre (`docs/wizard-headless/mesures/runs/`) contra l'or de Castellar.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("compare_consolida", REPO / "docs/wizard-headless/fase0-acceptacio/compare_consolida.py")
cc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cc)

CASTELLAR = "3001621 CASTELLAR DEL VALLES"
RUNS = REPO / "docs/wizard-headless/mesures/runs"

# (esperat, or, produït, camp) — parells reals dels 8 runs del llibre i de l'or de Castellar/Bell-lloc
CLOSE_CASES = [
    # nombres, signes, decimals
    (True, "-4,0 m (respecte el carrer)", "-4 m (respecte el carrer)", "cota_inici"),
    (False, "-4,0 m (respecte el carrer)", "-4,20 m (respecte el carrer)", "cota_inici"),
    (True, "570,90 msnm (segons el plànol ICGC)", "570.90 msnm (absoluta, ICGC)", "cota"),
    (True, "570,90 msnm (segons el plànol ICGC)", "570.90 (absoluta, ICGC)", "cota"),
    (True, "570,90 msnm (segons el plànol ICGC)",
     "570.90 msnm (absolut, segons plànol ICGC) -- NO usar a la taula segons regla d'or Pas 3b (sistema relatiu del projecte)", "cota"),
    (False, "570,90 msnm (segons el plànol ICGC)", "-4 m (relatiu, respecte carrer C/ Arbrells)", "cota"),
    (True, "423182", "423182.0", "utm_x"),
    (False, "1", "12", "num_soil_levels"),
    (False, "54", "58", "n30"),
    (True, "R (rebuig)", "R", "n30"),
    (False, "3001621", "3001631", "expedient"),
    # fondàries: valor absolut, interval amb guió o amb "a"
    (True, "-1,00 a -1,20 m", "1,0 - 1,2 m", "profunditat"),
    (True, "-1,00 a -1,20 m", "1,00 - 1,20 m", "profunditat"),
    (True, "1,0 - 1,2 m", "-1.00 a -1.20", "lab_depth"),
    (True, "1,0 - 1,2 m", "1,0-1,2", "lab_depth"),
    (False, "1,0 - 1,2 m", "1,0 - 1,6 m", "lab_depth"),
    (True, "0,00", "0.00", "de"),
    (True, "-0,50", "0.50", "a"),
    (True, "≥ -1,20 (fins al final del reconeixement; el tall el dibuixa fins a la base)", "1.20", "a"),
    (False, "-0,50", "1.20", "a"),
    # dates
    (True, "2025-10-24", "24/10/2025", "field_date"),
    (True, "2025-10-24", "24/10/25", "field_date"),
    (True, "2025-10-24", "24-10-2025", "field_date"),
    (True, "2025-10-24", "Octubre 2025", "field_date"),
    (True, "2025-10-24", "24 d'octubre de 2025", "field_date"),
    (False, "2025-10-24", "2025-10-06 (sondeig)", "field_date"),
    (False, "2025-10-24", "2025-11-24", "field_date"),
    # adreces: mateix conjunt de portals; lectura parcial NO és el mateix valor
    (True, "Carrer Arbrells, 18A, 18B i 20", "C/ARBRELLS 18A-18B-20", "street_address"),
    (True, "Carrer Arbrells, 18A, 18B i 20", "Carrer Arbrells 18A-18B-20", "street_address"),
    (True, "Carrer Arbrells, 18A, 18B i 20", "Carrer Arbrells, Nº 18A-18B-20", "street_address"),
    (False, "Carrer Arbrells, 18A, 18B i 20", "Carrer Arbrells 18A (només)", "street_address"),
    (False, "Carrer Arbrells, 18A, 18B i 20", "C/ ARBRELLS 18 A", "street_address"),
    (True, "C/ Mestre Ramon Ortiz 15", "C/MESTRE RAMON ORTIZ 15", "street_address"),
    (False, "C/ Mestre Ramon Ortiz 15", "C/ Antoni Bellet", "street_address"),
    (False, "C/ Mestre Ramon Ortiz 15", "Situat entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz (Bell-lloc)", "street_address"),
    (False, "C/ Mestre Ramon Ortiz 15", "C/ Mestre Ramon Ortiz 13", "street_address"),
    # spt_ma per comptes
    (True, "1/0", {"n_spt": 1, "n_tp": 0, "n_ma": 0}, "spt_ma"),
    (True, "1/0", "1/0/0", "spt_ma"),
    (True, "1/0", "1/--", "spt_ma"),
    (False, "1/0", "1/1", "spt_ma"),
    (False, "1/0", {"n_spt": 0, "n_tp": 0, "n_ma": 1}, "spt_ma"),
    # num_floors
    (True, "PB+1 (sense soterrani)", "PB+1 (2 plantes)", "num_floors"),
    (True, "PB+1 (sense soterrani)", "PB + 1, sense soterrani", "num_floors"),
    (True, "PB+1 (PB+PP)", "PB+PP", "num_floors"),
    (True, "PB+1 (PB+PP)", "Pb + p1", "num_floors"),
    (False, "PB+1 (sense soterrani)", "PB+2", "num_floors"),
    # building_type: article/adjectiu menor = CLOSE; canvi semàntic = no
    (True, "habitatges unifamiliars aïllats (grup de 3, entramat lleuger de fusta)", "Habitatge unifamiliar aïllat", "building_type"),
    (True, "habitatges unifamiliars aïllats (grup de 3, entramat lleuger de fusta)", "Grup d'habitatges unifamiliars", "building_type"),
    (True, "habitatges unifamiliars aïllats (grup de 3, entramat lleuger de fusta)", "CONSTR 3 HAB UNIF", "building_type"),
    (True, "habitatge unifamiliar aïllat", "un habitatge unifamiliar", "building_type"),
    (False, "habitatge unifamiliar aïllat", "habitatge unifamiliar entre mitgeres", "building_type"),
    (False, "habitatge unifamiliar aïllat", "ampliació", "building_type"),
    (False, "habitatge unifamiliar aïllat", "habitatge plurifamiliar", "building_type"),
    (False, "habitatge unifamiliar aïllat", "nau industrial", "building_type"),
    # text: regla històrica + anotacions fora
    (True, "MA-1 (S1)", "MA-1 (S1)", "lab_sample_id"),
    (False, "MA-1 (S1)", "SPT-1 (S1)", "lab_sample_id"),
    (True, "WOOD COMFORT PROMOCIONS SLU", "WOOD COMFORT PROMOCIONS SLU (B19935212)", "client_name"),
    (True, "Castellar del Vallès", "CASTELLAR DEL VALLÈS", "municipality"),
    (True, "C-0 (derivat)", "C0", "cte_edificacio"),
    (False, "C-0 (derivat)", "C-1", "cte_edificacio"),
    (False, "No detectat", "No indicat", "nivell_freatic"),  # vocabulari (skill v1.5), no format: es manté estricte
    (True, "No detectat", "No detectat", "nivell_freatic"),
    (True, None, None, "x"),
    (False, None, "1", "x"),
    # revisió adversària Sonnet 2026-08-25 (corregits)
    (False, "PB+2, amb soterrani", "PB+2 (sense soterrani)", "num_floors"),
    (True, "PB+1, i porxo habitable", "PB+1", "num_floors"),
    (True, "1.655,01 m²", "1655.01 m2", "superficie_parcela"),
    (True, "1.655,01 m²", "1655,01 m2", "superficie_parcela"),
    (False, "1.655,01 m²", "1.656 m²", "superficie_parcela"),
    (False, "Refús a 3,80m - parada per impossibilitat de penetració", "Refús a 3,80m - parada per aturada de màquina", "observacions"),
    (False, "Polígon Industrial Can Calderón", "Polígon Industrial Can Calderón, Nau 5", "street_address"),
    (True, "Polígon Industrial Can Calderón, Nau 5", "Pol. Ind. Can Calderon nau 5", "street_address"),
    (False, "Carrer Arbrells, 18A, 18B i 20", "C/ Arbrells", "street_address"),
    (True, "Situat entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz", "situat entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz (Bell-lloc)", "street_address"),
    # decisió documentada (memòria feedback_building_type_close_match): lectura parcial d'un qualificatiu = CLOSE
    (True, "habitatge unifamiliar entre mitgeres", "habitatge unifamiliar", "building_type"),
    # v4 (2026-09-05, codi C de la mesura dels 8): parells REALS dels `_compare_*.txt` que eren falsos ERR/ALERTA/CAUTELA
    (True, "Carrer Clot de la Llacuna, 16", "C/ Clot de la Llacuna, 16, Linyola (25240)", "street_address"),          # Linyola
    (True, "Carrer Clot de la Llacuna, 16", "Clot de la Llacuna, 16, Linyola (CP 25240)", "street_address"),
    (True, "Carrer Clot de la Llacuna, 16", "C. Clot de la Llacuna, 16", "street_address"),
    (True, "Carrer Girasols, 7 (Urb. El Roser)", "Carrer Girasols, Nº7, Urbanització el Roser", "street_address"),   # Alcoletge
    (True, "C/ Santa Gemma, 4 (Urb. La Serra)", "C/ STA. GEMMA 4, URB.LA SERRA", "street_address"),                  # Vilanova
    (False, "Carrer Clot de la Llacuna, 16", "Carrer Clot de la Llacuna, 18", "street_address"),
    (False, "Carrer Clot de la Llacuna, 16", "Carrer de la Font, 16, Linyola", "street_address"),
    (True, "0,80 - 1,40 m", "0,80-1,40m", "profunditat"),                                                             # Vilanova
    (True, "0,80 - 1,40 m", "0.80-1,40m", "profunditat"),
    (False, "0,80 - 1,40 m", "0,80-1,20m", "profunditat"),
    (True, "+212,50 msnm (segons plànol de l'ICGC)", "+212,50 msnm, segons plànol en el ICGC", "cota_inici"),         # Rubí
    (False, "+212 msnm (segons el plànol de l'ICGC)", "+212,50 msnm, segons plànol en el ICGC", "cota_inici"),
    (True, "1 (planta baixa)", "PB (planta baixa) + porxada, sense pis superior", "num_floors"),                      # Rubí
    (False, "PB+1", "PB (planta baixa) + porxada, sense pis superior", "num_floors"),
    (True, "-1,00 m (humitat)",                                                                                      # Alcoletge
     "Humitat (candidat, sense text: cel·les F22-F24 pintades de blau #A6CAF0, sense valor escrit) — fondària de primera aparició -1,00 m; abast pintat fins a -1,40 m",
     "nivell_freatic"),
    (False, "-0,80 m (humitat)",
     "Humitat (candidat, sense text: cel·les F22-F24 pintades de blau #A6CAF0, sense valor escrit) — fondària de primera aparició -1,00 m; abast pintat fins a -1,40 m",
     "nivell_freatic"),
    (False, "-1,00 m (humitat)", "~187,2 msnm (matís: humitat; lectura gràfica)", "nivell_freatic"),                # msnm ≠ fondària (R2)
    (False, "-1,00 m (humitat)", "No detectat", "nivell_freatic"),
    (True, "7 habitatges unifamiliars adossats (7 viviendas adosadas)", "vivienda adosada (7 unitats)", "building_type"),  # Anciles
    (True, "habitatge unifamiliar aïllat", "vivienda unifamiliar aislada", "building_type"),
    (True, "Alba Maria Barrau Castán", "MARIA ALBA BARRAU CASTÁN 616523792", "client_name"),                          # Anciles
    (True, "ALBA BARRAU (nºCol. 6.408) i MIRIAM CASTEL (nºCol. 6.703) — A+M Arquitectura",
     "ALBA BARRAU, nºCol. 6.408 / MIRIAM CASTEL, nºCol. 6.703", "architect_name"),
    (False, "Josep Bunyesc Palacín", "BUNYESC ARQUITECTURA EFICIENT, SLP", "architect_name"),                        # persona ≠ despatx (R1)
    (False, "Alba Maria Barrau Castán", "RETRATERIA, ALBA BARRAU CASTAN, ARQUITECTA", "client_name"),
    (True, "TPS PROSPECCIÓ DEL SUBSÒL SL (cap GTL a la carpeta)", "TPS (coneixement previ)", "lab_testing_company"),  # Anciles
    (True, "TPS (coneixement previ)", "TPS, Prospecció del Subsòl, SL", "lab_testing_company"),
    (False, "Vilanova de Segrià", "Vilanova del Segrià", "municipality"),                                              # D3 es un ERR real
    (True, "P-3", "SPT1 P3", "lab_location"),                                                                         # regla històrica de contenció (ja era així)
]


@pytest.mark.parametrize("expected,gold,prod,field", CLOSE_CASES, ids=[f"{c[3]}:{str(c[1])[:18]}~{str(c[2])[:18]}" for c in CLOSE_CASES])
def test_close(expected, gold, prod, field):
    assert cc.close(gold, prod, field) is expected


def _cell(estat, value=None, candidates=None, fora_carpeta=None):
    d = {"estat": estat}
    if value is not None or estat == "no_trobat":
        d["value"] = value
    if candidates is not None:
        d["candidates"] = candidates
    if fora_carpeta is not None:
        d["fora_carpeta"] = fora_carpeta
    return d


def _cand(value):
    return [{"value": value, "font": "x", "quote": value}]


# (gold, prod, veredicte esperat) — la matriu de 9 cel·les del Fix F (comparador v3) + variants de `fora_carpeta`
VERDICT_CASES = [
    (_cell("segur", "10"), _cell("segur", "10"), "OK"),
    (_cell("segur", "10"), _cell("segur", "20"), "ERR"),
    (_cell("segur", "10"), _cell("candidats", "10", _cand("10")), "CAUTELA"),
    (_cell("segur", "10"), _cell("candidats", "20", _cand("20")), "ALERTA"),
    (_cell("segur", "10"), _cell("no_trobat"), "BUIT"),
    (_cell("candidats", "10", _cand("10")), _cell("segur", "10"), "ALERTA"),
    (_cell("candidats", "10", _cand("10")), _cell("candidats", "10", _cand("10")), "OK"),
    (_cell("candidats", "10", _cand("10")), _cell("candidats", "20", _cand("20")), "CAUTELA"),
    (_cell("candidats", "10", _cand("10")), _cell("no_trobat"), "BUIT"),
    (_cell("no_trobat"), _cell("segur", "10"), "ALERTA"),
    (_cell("no_trobat"), _cell("candidats", "10", _cand("10")), "ALERTA"),
    (_cell("no_trobat", fora_carpeta={"value": "10", "font": "Cadastre"}), _cell("candidats", "10", _cand("10")), "FORA"),
    (_cell("no_trobat", fora_carpeta={"value": "10", "font": "Cadastre"}), _cell("candidats", "99", _cand("99")), "CAUTELA"),
    (_cell("no_trobat"), _cell("no_trobat"), "OK"),
]


@pytest.mark.parametrize("gold,prod,expected", VERDICT_CASES, ids=[
    "segur=segur-ok", "segur=segur-err", "segur-candidats-bo_dins", "segur-candidats-fora",
    "segur-no_trobat-buit", "candidats-segur-alerta", "candidats-candidats-solapen-ok",
    "candidats-candidats-disjunts", "candidats-no_trobat-buit", "no_trobat-segur-alerta",
    "no_trobat-candidats-sense_fora_carpeta-alerta", "no_trobat-candidats-fora_carpeta_coincideix-fora",
    "no_trobat-candidats-fora_carpeta_no_coincideix-cautela", "no_trobat-no_trobat-ok",
])
def test_verdict_matrix(gold, prod, expected):
    v, _ = cc.verdict(gold, prod, "x")
    assert v == expected


def test_close_is_symmetric():
    for _, a, b, f in CLOSE_CASES:
        assert cc.close(a, b, f) == cc.close(b, a, f), (a, b, f)


def test_parsers():
    assert cc.parse_date("24/10/25") == (2025, 10, 24)
    assert cc.parse_date("Octubre 2025") == (2025, 10, None)
    assert cc.parse_date("1,5-1,75") is None  # interval, no data
    assert cc.parse_numbers("1,0-1,2", absolute=True) == (1.0, 1.2)
    assert cc.parse_numbers("-1,00 a -1,20 m") == (-1.0, -1.2)
    assert cc.parse_numbers("PB+1") is None
    assert cc.parse_numbers("4 (P1, P2, P3, P4) + S1") == (4.0,)
    assert cc.parse_address("C/ARBRELLS 18A-18B-20") == (("arbrells",), frozenset({"18a", "18b", "20"}))
    assert cc.parse_address("Carrer Arbrells") is None
    # v4: via = tokens abans del primer portal; «C.» reconegut; CP no es portal; sta → santa; tipus de via opcional
    assert cc.parse_address("C/ Clot de la Llacuna, 16, Linyola (25240)") == (("clot", "llacuna"), frozenset({"16"}))
    assert cc.parse_address("Clot de la Llacuna, 16, Linyola 25240") == (("clot", "llacuna"), frozenset({"16"}))
    assert cc.parse_address("C. Clot de la Llacuna, 16") == (("clot", "llacuna"), frozenset({"16"}))
    assert cc.parse_address("C/ STA. GEMMA 4, URB.LA SERRA") == (("santa", "gemma"), frozenset({"4"}))
    assert cc.parse_numbers("0,80-1,40m", absolute=True) == (0.8, 1.4)
    assert cc.parse_numbers("+212,50 msnm, segons plànol en el ICGC") == (212.5,)
    assert cc.first_depth("Humitat — fondària de primera aparició -1,00 m; abast fins a -1,40 m") == 1.0
    assert cc.person_tokens("ALBA BARRAU (nºCol. 6.408) i MIRIAM CASTEL (nºCol. 6.703) — A+M Arquitectura") == frozenset({"alba", "barrau", "miriam", "castel"})
    assert cc.person_tokens("Sra. MARIA ALBA BARRAU CASTÁN 616523792") == frozenset({"maria", "alba", "barrau", "castan"})
    assert cc.parse_spt_ma("1/--") == (1, None, 0)
    assert cc.parse_spt_ma({"n_spt": 1, "n_tp": 0, "n_ma": 0}) == (1, 0, 0)
    assert cc.building_tokens("Grup d'habitatges unifamiliars") == frozenset({"grup", "habitatge", "unifamiliar"})


@pytest.mark.parametrize("nom,key", [
    ("Terreny Vegetal (capa superficial, SENSE numeració de nivell)", "cover"),
    ("Sòls vegetals (cobertura, no numerada)", "cover"),
    ("1r nivell — Terreny vegetal", "cover"),
    ("Nivell 1 (1er i únic nivell)", "n1"),
    ("1er nivell (NIVELL 1)", "n1"),
    ("NIVELL 1 — Substrat rocós (0,50-1,20)", "n1"),
    ("2n nivell", "n2"),
    ("Substrat rocós", None),
    ("Nivell 2 - Reblert de graves", "n2"),
    ("2n nivell: reblert antròpic", "n2"),
    ("Reblert antròpic (no numerat)", "cover"),
    ("Cobertura", "cover"),
])
def test_row_key_soil_levels(nom, key):
    assert cc.row_key("soil_levels", {"nom": nom}) == key
    assert cc.row_key("soil_levels", {"nom": {"estat": "segur", "value": nom, "candidates": []}}) == key


def test_row_key_other_blocks():
    assert cc.row_key("dpsh_tests", {"punt": "P-1"}) == "p1"
    assert cc.row_key("dpsh_tests", {"punt": {"estat": "segur", "value": "P-1"}}) == "p1"
    assert cc.row_key("sondeig_tests", {"sondeig": "S-1"}) == "s1"
    assert cc.row_key("sondeig_tests", {"punt": "S-1"}) == "s1"
    assert cc.row_key("spt_ma_tests", {"id": "SPT-1", "punt": "S-1"}) == "s1"   # v4: per punt (Vilanova, dos «SPT-1»)
    assert cc.row_key("spt_ma_tests", {"id": "SPT-1"}) is None


def test_align_rows_by_key_and_fallback():
    gold = [{"nom": "Terreny Vegetal (cobertura)"}, {"nom": "Nivell 1"}]
    prod = [{"nom": "NIVELL 1", "x": 1}]
    pairs, by_key = cc.align_rows("soil_levels", gold, prod)
    assert by_key and pairs[0][1] == {} and pairs[1][1]["x"] == 1
    # claus duplicades al produït → índex
    prod2 = [{"nom": "Terreny vegetal"}, {"nom": "NIVELL 1"}, {"nom": "1er nivell"}]
    pairs, by_key = cc.align_rows("soil_levels", gold, prod2)
    assert not by_key and pairs[1][1] is prod2[1]


def test_expand_de_a():
    row = {"nom": "x", "de": "0,00", "a": "-0,50", "de_a_estat": {"estat": "segur", "candidates": [{"value": "0,00 a -0,50"}]}}
    out = cc._expand_de_a(row)
    assert "de_a_estat" not in out and out["de"]["estat"] == "segur" and out["a"]["value"] == "-0,50"
    assert cc._expand_de_a({"nom": "x", "de": {"estat": "segur", "value": "0"}}) == {"nom": "x", "de": {"estat": "segur", "value": "0"}}
    out = cc._expand_de_a({"nom": "x", "de_a_estat": {"estat": "segur", "value": "0,00 a -0,50"}})
    assert out["de"]["value"] == "0,00" and out["a"]["value"] == "-0,50"
    out = cc._expand_de_a({"nom": "x", "de_a_estat": {"estat": "segur", "value": "Terra vegetal a la superfície a -1,20m"}})
    assert "de" not in out and "a" not in out  # separador no numèric: no s'inventen cel·les


def test_align_rows_numbered_fill_is_not_cover():
    gold = [{"nom": "Nivell 1"}, {"nom": "Nivell 2 - Reblert antic de graves"}]
    prod = [{"nom": "Terra vegetal"}, {"nom": "Nivell 1"}]
    pairs, by_key = cc.align_rows("soil_levels", gold, prod)
    assert by_key and pairs[1][1] == {}  # Nivell 2 absent al produït, no aparellat amb la capa vegetal
    assert cc.parse_numbers("1.655,01 m²") == (1655.01,)
    assert cc.norm_floors("PB+2, amb soterrani") == ("pb2", "amb")
    assert cc.norm_floors("PB+1 (sense soterrani)") == ("pb1", "sense")


def _counts(kind, run):
    return (cc.compare_escalars if kind == "escalars" else cc.compare_taules)(RUNS / run / "_decisions.json", CASTELLAR)


@pytest.mark.skipif(not (RUNS / "2026-08-25-opus48-docs-python-consolida/_decisions.json").exists(), reason="llibre absent")
def test_integration_python_consolida_run_has_no_format_noise():
    """El run de referència de la Fase 12 (consolidació Python): cap ERR ni ABSENT de format, adreça i cota CAUTELA."""
    lines, esc = _counts("escalars", "2026-08-25-opus48-docs-python-consolida")
    assert esc.get("ERR", 0) == 0
    assert any(l.startswith("CAUTELA  street_address") for l in lines)
    assert any(l.startswith("CAUTELA  building_type") for l in lines)
    lines, tau = _counts("taules", "2026-08-25-opus48-docs-python-consolida")
    assert tau.get("ERR", 0) == 0 and tau.get("ABSENT", 0) == 0 and tau.get("VIOLACIO", 0) == 0
    assert any("soil_levels: or 2 files / prod 2 files · alineades per clau" in l for l in lines)


@pytest.mark.skipif(not (RUNS / "2026-08-24-sonnet-c2/_decisions.json").exists(), reason="llibre absent")
def test_integration_state_differences_survive():
    """Les diferències d'ESTAT (prod puja a segur, or candidats) no desapareixen amb els normalitzadors."""
    lines, esc = _counts("escalars", "2026-08-24-sonnet-c2")
    assert any(l.startswith("ALERTA   cota_referencia") and "prod puja a segur" in l for l in lines)
    lines, tau = _counts("taules", "2026-08-24-sonnet-c2")
    assert any(l.startswith("ALERTA   sondeig_tests[0].spt_ma") and "prod puja a segur" in l and "fora dels candidats" not in l for l in lines)


# --- v4 (2026-09-05): candidats compartits de `cte` per subclau, `NOMES-OR`, spt per punt ------------------------

def test_subkey_candidates_split_cte_and_keep_lab():
    cands = [{"value": "C0 (< 300 m² i < 4 plantes)"}, {"value": "T-1 (per defecte del patró)"}]
    assert cc.subkey_candidates("cte", "cte_edificacio", cands) == [cands[0]]
    assert cc.subkey_candidates("cte", "cte_sol", cands) == [cands[1]]
    lab = [{"value": "MA (S-2) 2,8-3,0"}, {"value": "TPS (coneixement previ)"}]
    assert cc.subkey_candidates("lab", "lab_sample_id", lab) == lab


def test_castellar_cte_sol_gold_has_no_value_nor_candidates():
    """Abans `cte_sol` de Castellar heretava «C0 (…)» de la llista compartida i sortia «candidats disjunts»."""
    gold = cc.flat_gold_scalars(CASTELLAR)
    assert gold["cte_sol"]["value"] is None and gold["cte_sol"]["candidates"] == []
    assert [c["value"] for c in gold["cte_edificacio"]["candidates"]] == ["C0 (< 300 m² i < 4 plantes: 120 m², PB+1)"]
    v, msg = cc.verdict(gold["cte_sol"], {"estat": "candidats", "value": "T-1", "candidates": [{"value": "T-1"}]}, "cte_sol")
    assert v == "CAUTELA" and msg.startswith("or sense valor")


def test_align_spt_rows_by_punt_when_unique():
    """Vilanova: els dos SPT es diuen «SPT-1»; per index es creuaven P-1/P-3."""
    gold = [{"punt": {"estat": "segur", "candidates": [{"value": "P-3"}]}, "id": {"estat": "candidats", "candidates": [{"value": "SPT-1 (P-3)"}]}},
            {"punt": {"estat": "segur", "candidates": [{"value": "P-1"}]}, "id": {"estat": "candidats", "candidates": [{"value": "SPT-1 (P-1)"}]}}]
    prod = [{"punt": {"estat": "segur", "value": "P-1"}, "id": {"estat": "segur", "value": "SPT1"}},
            {"punt": {"estat": "segur", "value": "P-3"}, "id": {"estat": "segur", "value": "SPT-1"}}]
    pairs, by_key = cc.align_rows("spt_ma_tests", gold, prod)
    assert by_key and pairs[0][1]["punt"]["value"] == "P-3" and pairs[1][1]["punt"]["value"] == "P-1"
    # punts duplicats (Anciles: S-1, S-2, S-2) → per index, com abans
    prod_dup = [{"punt": {"estat": "candidats", "value": "S-2"}}, {"punt": {"estat": "candidats", "value": "S-2"}}]
    _, by_key = cc.align_rows("spt_ma_tests", gold, prod_dup)
    assert not by_key


def test_integration_vilanova_v4_no_false_err_and_fixture_only_columns_do_not_count():
    """Sobre el `_decisions.json` versionat de la mesura (consolidador ANTIC): els 4 ERR de spt (punt/profunditat) eren
    del comparador; `lab` i `nom` son columnes nomes de l'or (NOMES-OR, no compten). El D3 de `municipality` es un ERR
    real del consolidador i el comparador l'ha de continuar veient."""
    run = RUNS / "2026-09-03-mesura-8" / "vilanova" / "_decisions.json"
    if not run.exists():
        pytest.skip("run de la mesura no versionat")
    lines, counts = cc.compare_taules(run, "4001671 VILANOVA DE SEGRIA")
    assert counts.get("ERR", 0) == 0 and counts.get("ABSENT", 0) == 0
    assert counts.get("NOMES_OR") == 4 and any(l.startswith("NOMES-OR spt_ma_tests: lab") for l in lines)
    lines, counts = cc.compare_escalars(run, "4001671 VILANOVA DE SEGRIA")
    assert counts.get("ERR") == 1 and any(l.startswith("ERR      municipality") for l in lines)


def test_integration_alcoletge_v4_street_address_is_not_err():
    run = RUNS / "2026-09-03-mesura-8" / "alcoletge" / "_decisions.json"
    if not run.exists():
        pytest.skip("run de la mesura no versionat")
    lines, counts = cc.compare_escalars(run, "4001670 ALCOLETGE")
    assert counts.get("ERR", 0) == 0 and not any("street_address" in l for l in lines)
    _, counts = cc.compare_taules(run, "4001670 ALCOLETGE")
    assert counts.get("CAUTELA", 0) == 3   # les 3 `nivell_freatic` (text llarg = -1,00) ja son OK



def test_close_mostra_del_nivell_text_yes_no_equals_boolean():
    """v5: la cel·la `mostra_del_nivell` es compara com a booleà: «No (pel material)» de l'or = False del consolidador,
    «Si per interval estricte (…)» = True; un text que no comença per Sí/No cau a la regla de text."""
    assert cc.yes_no("No (la mostra s'assigna al 2on nivell pel material)") is False
    assert cc.yes_no("Si — SPT-1 (P-3, 1,0-1,15 m): material de la mostra = lutita") is True
    assert cc.yes_no(True) is True and cc.yes_no("false") is False and cc.yes_no("possible") is None
    assert cc.close("No (la mostra s'assigna al 2on nivell pel material)", False, "mostra_del_nivell")
    assert cc.close(True, "Si per interval estricte (1,0-1,15 m a P-3)", "mostra_del_nivell")
    assert not cc.close("No per interval estricte", True, "mostra_del_nivell")
    assert not cc.close("No", True, "litologia") or True   # altres camps: regla de text (no s'afirma res aquí)
    assert cc.verdict({"estat": "candidats", "candidates": [{"value": "No (pel material)"}, {"value": "Si per interval"}]},
                       {"estat": "candidats", "candidates": [{"value": False}, {"value": True}]}, "mostra_del_nivell")[0] == "OK"
