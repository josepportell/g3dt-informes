"""Tests del padró de municipis (`automation/municipis.py`) i dels seus dos consumidors.

Vegeu `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` §4 i §9 (peça 2). Dades reals:
`automation/data/municipis_padro_cadastre.json`, 947 municipis baixats del Cadastre el
2026-09-01. Els casos d'aquest fitxer són els residus REALS dels 10 `PLAN_COST*.xlsx` del
corpus i els noms reals del padró, no exemples inventats.

0 xarxa: `municipis` no en fa mai, i el consumidor de `cadastre_reader` es talla amb un
monkeypatch que peta si algú consulta el municipi en línia.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation import g3_templates, municipis  # noqa: E402
from automation.lectura import cadastre_reader as R  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_index():
    """Els índexs són globals i mandrosos: buidar-los abans i després de cada test."""
    municipis.reset_cache()
    yield
    municipis.reset_cache()


# ------------------------------------------------------------------- el padró


def test_el_padro_te_els_947_i_els_camps_del_cadastre() -> None:
    rows = municipis._load()
    assert len(rows) == 947
    row = next(r for r in rows if r["ine_code"] == "25048")
    assert row["name_ine"] == "Bell-lloc d'Urgell"
    assert row["name_cadastre"] == "BELL-LLOC D'URGELL"
    assert (row["cp"], row["cm"]) == ("25", "48")
    assert row["province_cadastre"] == "LLEIDA"


def test_ine_code_es_la_parella_cp_cm() -> None:
    """La clau d'aparellament del padró: `25048` == cp 25 / cm 48. Si això es trenca, el
    fitxer s'ha regenerat malament."""
    for row in municipis._load():
        assert row["ine_code"] == f"{int(row['cp']):02d}{int(row['cm']):03d}"


@pytest.mark.parametrize(
    "hint,expected,layer",
    [
        # residus reals dels PLAN_COST del corpus
        ("CASTELLAR DEL VALLÈS", "Castellar del Vallès", "exacte"),
        ("RUBI", "Rubí", "exacte"),
        ("LINYOLA", "Linyola", "exacte"),
        ("ALCOLETGE", "Alcoletge", "exacte"),
        ("CERDANYOLA", "Cerdanyola del Vallès", "forma curta"),
        ("BELL-LLOC", "Bell-lloc d'Urgell", "forma curta"),
        ("VILANOVA SEGRIÀ", "Vilanova de Segrià", "preposicions"),
        # l'article canvia de banda entre INE i Cadastre (136 municipis)
        ("L'Ametlla del Vallès", "Ametlla del Vallès, L'", "exacte"),
        ("Ametlla del Vallès", "Ametlla del Vallès, L'", "exacte"),
        ("AMETLLA DEL VALLES", "Ametlla del Vallès, L'", "exacte"),
        ("Els Omells de na Gaia", "Omells de na Gaia, Els", "exacte"),
        # el municipi ve amb la província entre parèntesis
        ("Rubí (Barcelona)", "Rubí", "exacte"),
    ],
)
def test_lookup_troba(hint: str, expected: str, layer: str) -> None:
    got = municipis.lookup(hint)
    assert got is not None and got.name_ine == expected
    assert got.match_layer == layer


@pytest.mark.parametrize(
    "hint,per_que",
    [
        ("ANCILES", "llogaret de Benasc (Osca): no és un municipi català"),
        ("CASTELLAR", "encaixa amb 4 municipis: no es pot decidir"),
        ("VILANOVA", "encaixa amb més de 10: no es pot decidir"),
        ("CATELLAR DEL VALLÈS", "errata real d'un fitxer del corpus: sense capa difusa a posta"),
        ("", "buit"),
        ("   ", "només espais"),
    ],
)
def test_lookup_no_endevina(hint: str, per_que: str) -> None:
    assert municipis.lookup(hint) is None, per_que


def test_padro_illegible_no_peta(monkeypatch, tmp_path) -> None:
    """Si el fitxer falta o és corrupte, `lookup` torna None: mai ha de tombar un lector."""
    monkeypatch.setattr(municipis, "PADRO_FILE", tmp_path / "no-hi-es.json")
    municipis.reset_cache()
    assert municipis.lookup("Linyola") is None


def test_padro_corromput_no_peta(monkeypatch, tmp_path) -> None:
    bad = tmp_path / "padro.json"
    bad.write_text("{ no és json", encoding="utf-8")
    monkeypatch.setattr(municipis, "PADRO_FILE", bad)
    municipis.reset_cache()
    assert municipis.lookup("Linyola") is None


def test_padro_a_mida(monkeypatch, tmp_path) -> None:
    """`PADRO_FILE` és substituïble: la resta de tests no depèn del fitxer real."""
    fake = tmp_path / "padro.json"
    fake.write_text(json.dumps({"municipalities": [{
        "ine_code": "25001", "name_ine": "Vila Fictícia", "name_cadastre": "VILA FICTICIA",
        "province": "Lleida", "province_cadastre": "LLEIDA", "cp": "25", "cm": "1",
    }]}), encoding="utf-8")
    monkeypatch.setattr(municipis, "PADRO_FILE", fake)
    municipis.reset_cache()
    assert municipis.lookup("Vila Ficticia").name_cadastre == "VILA FICTICIA"
    assert municipis.lookup("Linyola") is None


# ------------------------------------------- consumidor 1: residu de PLAN_COST


def test_plan_cost_confirmat_manté_la_confiança_de_sempre() -> None:
    """El padró només afegeix dubte: un residu que ja es corroborava NO puja de 0,6.

    És deliberat (vegeu `_plan_cost_municipi_confianca`): pujar confiances mouria decisions
    correctes als 9 corpus, que són la prova de no-regressió del projecte.
    """
    conf, nota = g3_templates._plan_cost_municipi_confianca(
        "CASTELLAR DEL VALLÈS", True, "PLAN_COST 3001621 CASTELLAR DEL VALLES")
    assert (conf, nota) == (0.6, None)


def test_plan_cost_forma_curta_diu_la_forma_oficial() -> None:
    conf, nota = g3_templates._plan_cost_municipi_confianca(
        "BELL-LLOC", True, "PLAN_COST_BELL-LLOC 4001612 BELL-LLOC")
    assert conf == 0.6
    assert "és la forma curta de «Bell-lloc d'Urgell»" in nota


def test_plan_cost_preposicions_diu_la_forma_oficial() -> None:
    conf, nota = g3_templates._plan_cost_municipi_confianca(
        "VILANOVA SEGRIÀ", True, "PLAN_COST 4001671 VILANOVA DE SEGRIA")
    assert conf == 0.6
    assert "sense les preposicions, «Vilanova de Segrià»" in nota


def test_el_padro_no_rescata_una_contradiccio_amb_la_carpeta() -> None:
    """Guardes INDEPENDENTS, i mana la del context.

    Que «Bell-lloc» sigui un municipi de debò no vol dir que sigui el d'AQUEST projecte: un
    PLAN_COST de Bell-lloc dins d'una carpeta de Torregrossa ha de seguir valent 0,4. És
    l'error de disseny que va destapar `test_g3_templates.py::
    test_plan_cost_municipi_sense_corroborar_baixa_de_confianca` en cablejar la peça 2.
    """
    conf, nota = g3_templates._plan_cost_municipi_confianca("BELL-LLOC", True, "9999999 TORREGROSSA")
    assert conf == 0.4
    assert "no surt ni al nom del fitxer" in nota
    assert "podria ser el d'un altre projecte" in nota


def test_plan_cost_fora_del_padro_baixa_i_ho_diu() -> None:
    """Cas real: `EG 7 VIVIENDAS ANCILES`. Anciles és un llogaret de Benasc, no un municipi."""
    conf, nota = g3_templates._plan_cost_municipi_confianca("ANCILES", True, "4001679 ANCILES")
    assert conf == 0.5
    assert "no consta al padró" in nota and "de fora de Catalunya" in nota


def test_plan_cost_ni_padro_ni_context_es_el_dubte_mes_fort() -> None:
    conf, nota = g3_templates._plan_cost_municipi_confianca("NAU LLEIDA", True, "ctx sense res")
    assert conf == 0.4
    assert "no surt ni al nom del fitxer" in nota


def test_plan_cost_no_versemblant_no_consulta_el_padro(monkeypatch) -> None:
    def boom(_hint):  # pragma: no cover - no s'ha d'arribar a cridar
        raise AssertionError("amb un residu no versemblant no cal mirar el padró")

    monkeypatch.setattr(municipis, "lookup", boom)
    conf, nota = g3_templates._plan_cost_municipi_confianca("XX/12 3", False, "ctx")
    assert conf == 0.4 and "no sembla un municipi" in nota


# --------------------------------------- consumidor 2: municipi sense xarxa


@pytest.fixture
def sense_xarxa_de_municipi(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")

    def boom(*a, **k):
        raise AssertionError("no s'ha de consultar el municipi en línia: és al padró")

    monkeypatch.setattr(R, "_consulta_municipio", boom)
    monkeypatch.setattr(R, "_consulta_via", lambda *a, **k: ("ARBRELLS DELS", "CL", "372"))
    seen: dict[str, str] = {}

    def _resolve_portal(province, muni, via, number, letter, *, tipo_via="CL"):
        seen["province"], seen["muni"] = province, muni
        return []

    monkeypatch.setattr(R, "resolve_portal", _resolve_portal)
    return seen


def test_municipi_del_padro_evita_la_consulta_en_linia(sense_xarxa_de_municipi) -> None:
    decided = {
        "street_address": {"estat": "segur", "value": "Carrer Arbrells, 18A"},
        "municipality": {"estat": "segur", "value": "Castellar del Vallès"},
    }
    R.cadastre_portal_signals("superficie_parcela", decided, Path("/no/existeix"))
    assert sense_xarxa_de_municipi["province"] == "BARCELONA"
    assert sense_xarxa_de_municipi["muni"] == "CASTELLAR DEL VALLES"


def test_forma_curta_de_g3_tambe_resol_sense_xarxa(sense_xarxa_de_municipi) -> None:
    """`BELL-LLOC` és com ho escriu G3; el padró hi arriba per la capa de forma curta."""
    decided = {
        "street_address": {"estat": "segur", "value": "Carrer Arbrells, 18A"},
        "municipality": {"estat": "segur", "value": "BELL-LLOC"},
    }
    R.cadastre_portal_signals("superficie_parcela", decided, Path("/no/existeix"))
    assert sense_xarxa_de_municipi["province"] == "LLEIDA"
    assert sense_xarxa_de_municipi["muni"] == "BELL-LLOC D'URGELL"


def test_fora_del_padro_torna_al_bucle_en_linia(monkeypatch, tmp_path) -> None:
    """Anciles no és al padró: la cadena ha de seguir funcionant amb `ConsultaMunicipio`."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    provincies: list[str] = []

    def _muni(province, hint):
        provincies.append(province)
        return ("BENASQUE", "22", "59") if province == "HUESCA" else None

    monkeypatch.setattr(R, "_consulta_municipio", _muni)
    monkeypatch.setattr(R, "_consulta_via", lambda *a, **k: ("ANCILES", "CL", "1"))
    seen: dict[str, str] = {}

    def _resolve_portal(province, muni, via, number, letter, *, tipo_via="CL"):
        seen["province"], seen["muni"] = province, muni
        return []

    monkeypatch.setattr(R, "resolve_portal", _resolve_portal)
    decided = {
        "street_address": {"estat": "segur", "value": "Carrer Anciles, 5"},
        "municipality": {"estat": "segur", "value": "Anciles"},
    }
    R.cadastre_portal_signals("superficie_parcela", decided, Path("/no/existeix"))
    assert provincies[-1] == "HUESCA"
    assert seen["muni"] == "BENASQUE"
