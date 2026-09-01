"""Tests de `resolve_via` — tria de carrer sobre conjunt tancat (peça 1 del disseny d'adreces).

Vegeu `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` §5. Motiu de la peça:
`geocode_coordinates._consulta_via` (via B, intocable) només activa fuzzy i picker LLM si el
municipi té <= 500 carrers, i Rubí (835) i Cerdanyola (577) en queden fora.

Tot amb `monkeypatch`, 0 xarxa. Les llistes de carrers són EXTRETES DE LES REALS del Callejero
(capturades 2026-09-01): els duplicats català/castellà, els noms truncats pel Cadastre i els
articles enganxats al final són tal com els torna el servei, no inventats.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.lectura import cadastre_reader as R  # noqa: E402

#: Subconjunt real de Bell-lloc d'Urgell (112 carrers al Callejero, 2026-09-01).
BELL_LLOC = [
    ("ARBRELLS DELS", "CL", "1"),
    ("ANTONI BELLET I PEREZ", "CL", "131"),
    ("MESTRE RAMON ORTIZ", "CL", "2"),
    ("ONZE DE SETEMBRE", "PZ", "126"),
    ("MAJOR", "PZ", "3"),
    ("TELEGRAFOS", "TR", "4"),
    ("TELEGRAFS", "TR", "5"),
    ("SANT JORDI", "CL", "6"),
    ("SANT JOSEP", "CL", "7"),
    ("GIRASOLS DELS", "CL", "8"),
    ("NOU", "CL", "9"),
]


@pytest.fixture
def offline(monkeypatch, tmp_path):
    """Cache pròpia i cap crida de xarxa; retorna un comptador de descàrregues."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    calls = {"n": 0}

    def _fake(province: str, municipality: str):
        calls["n"] += 1
        return list(BELL_LLOC)

    monkeypatch.setattr(R, "_consulta_via_all_streets", _fake)
    return calls


# --------------------------------------------------------------------- nombres


@pytest.mark.parametrize(
    "tokens,expected",
    [
        (["ONZE", "SETEMBRE"], ["11", "SETEMBRE"]),
        (["11", "SETEMBRE"], ["11", "SETEMBRE"]),
        (["VINT", "I", "CINC", "SETEMBRE"], ["25", "SETEMBRE"]),  # frase llarga abans que curta
        (["ONCE", "SEPTIEMBRE"], ["11", "SEPTIEMBRE"]),
        (["ARBRELLS"], ["ARBRELLS"]),
        ([], []),
    ],
)
def test_numeral_canon(tokens: list[str], expected: list[str]) -> None:
    assert R._numeral_canon(tokens) == expected


def test_numeral_canon_no_desmunta_vint_i_cinc() -> None:
    """`VINT I CINC` ha de ser 25, mai `20, 1, 5`."""
    assert R._numeral_canon(["VINT", "I", "CINC"]) == ["25"]


# ------------------------------------------------------------------ resolve_via


def test_exacte_amb_article_del_callejero(offline) -> None:
    """`Arbrells` -> `ARBRELLS DELS`: l'article no compta com a paraula."""
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Arbrells") == ("ARBRELLS DELS", "CL", "1")


def test_conte_amb_diverses_paraules(offline) -> None:
    """`Antoni Bellet` -> `ANTONI BELLET I PEREZ` (hint de més d'una paraula: n'hi ha prou)."""
    got = R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Antoni Bellet")
    assert got == ("ANTONI BELLET I PEREZ", "CL", "131")


def test_capa_de_nombres_i_tipus_de_via(offline) -> None:
    """El cas del Josep: `11 de Setembre` -> `ONZE DE SETEMBRE`, i és una PLAÇA, no un carrer."""
    got = R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "11 de Setembre")
    assert got == ("ONZE DE SETEMBRE", "PZ", "126")


def test_una_paraula_amb_extra_significatiu_no_casa(offline, monkeypatch) -> None:
    """`Major` no pot casar amb `MAJOR DE BALAFIA`: és un altre carrer."""
    monkeypatch.setattr(R, "_consulta_via_all_streets", lambda p, m: [("MAJOR DE BALAFIA", "CL", "1")])
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Major") is None


def test_una_paraula_exacta_si_casa(offline) -> None:
    """...però `Major` sí que casa amb el `MAJOR` literal, que existeix de debò."""
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Major") == ("MAJOR", "PZ", "3")


def test_setembre_sol_no_casa_amb_onze_de_setembre(offline) -> None:
    """Regressió: el token de nombre ha de comptar com a paraula significativa.

    `_numeral_canon` converteix `ONZE DE SETEMBRE` en `["11","SETEMBRE"]`, i `"11"` té 2
    caràcters — la mateixa longitud que les abreviatures del Callejero (`PD`, `DS`). Sense
    l'excepció de `_tokens_cover`, el hint `Setembre` es menjava el `11` com si fos una
    abreviatura i retornava el carrer equivocat amb cara de bo.
    """
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Setembre") is None


def test_empat_a_la_capa_difusa_dona_blanc(offline) -> None:
    """`Telegraf` s'assembla prou a TELEGRAFS (0,94) i a TELEGRAFOS (0,89): no es tria."""
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Telegraf") is None


def test_difusa_accepta_quan_es_unica(offline) -> None:
    """`Girassols` -> `GIRASOLS DELS`: variant ortogràfica sense competidora."""
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Girassols") == ("GIRASOLS DELS", "CL", "8")


def test_carrer_inexistent_dona_blanc(offline) -> None:
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Inexistent Absolut") is None


def test_no_inventa_un_sant_que_no_hi_es(offline) -> None:
    """Hi ha SANT JORDI i SANT JOSEP; `Sant Pere` no pot caure en cap dels dos."""
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Sant Pere") is None


def test_hint_buit(offline) -> None:
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "   ") is None


def test_llista_buida_dona_blanc_i_no_es_cacheja(monkeypatch, tmp_path) -> None:
    """Una llista buida és un error transitori del servei, no un municipi sense carrers:
    si es cachegés, el municipi quedaria mort 90 dies."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(R, "_consulta_via_all_streets", lambda p, m: [])
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Arbrells") is None

    monkeypatch.setattr(R, "_consulta_via_all_streets", lambda p, m: list(BELL_LLOC))
    assert R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Arbrells") == ("ARBRELLS DELS", "CL", "1")


def test_la_llista_es_cacheja(offline) -> None:
    R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Arbrells")
    R.resolve_via("LLEIDA", "BELL-LLOC D'URGELL", "Major")
    assert offline["n"] == 1


def test_sense_llindar_de_mida(monkeypatch, tmp_path) -> None:
    """LA raó de ser de la peça: `_consulta_via` es planta a 500 carrers i Rubí en té 835."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    big = [(f"CARRER FICTICI {i:04d}", "CL", str(i)) for i in range(900)]
    big.append(("ONZE DE SETEMBRE", "PZ", "126"))
    monkeypatch.setattr(R, "_consulta_via_all_streets", lambda p, m: big)
    assert R.resolve_via("BARCELONA", "RUBI", "11 de Setembre") == ("ONZE DE SETEMBRE", "PZ", "126")


# ------------------------------------------------------- cablejat amb la cadena


def _decided() -> dict[str, dict]:
    return {
        "street_address": {"estat": "segur", "value": "Carrer Arbrells, 18A"},
        "municipality": {"estat": "segur", "value": "Bell-lloc d'Urgell"},
    }


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Municipi i portals resolts; només queda la tria de carrer per exercitar."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(R, "_consulta_municipio", lambda prov, hint: ("BELL-LLOC D'URGELL", "25", "48"))
    monkeypatch.setattr(R, "_consulta_via_all_streets", lambda p, m: list(BELL_LLOC))
    seen: dict[str, str] = {}

    def _resolve_portal(province, muni, via, number, letter, *, tipo_via="CL"):
        seen["via"] = via
        seen["tipo_via"] = tipo_via
        return []

    monkeypatch.setattr(R, "resolve_portal", _resolve_portal)
    return seen


def test_recupera_quan_via_b_no_troba_res(monkeypatch, wired) -> None:
    monkeypatch.setattr(R, "_consulta_via", lambda *a, **k: None)
    R.cadastre_portal_signals("superficie_parcela", _decided(), Path("/no/existeix"))
    assert wired["via"] == "ARBRELLS DELS"


def test_recupera_quan_via_b_torna_un_carrer_que_no_es(monkeypatch, wired) -> None:
    """El cas mesurat a Castellar: via B tornava `POL 011 FABRICA NOVA` per `11 de Setembre`."""
    monkeypatch.setattr(R, "_consulta_via", lambda *a, **k: ("POL 011 FABRICA NOVA", "CL", "99"))
    R.cadastre_portal_signals("superficie_parcela", _decided(), Path("/no/existeix"))
    assert wired["via"] == "ARBRELLS DELS"


def test_no_toca_el_cami_que_ja_funcionava(monkeypatch, wired) -> None:
    """Additiu: si via B encerta, la seva resposta mana i no es consulta la llista."""
    def _boom(p, m):  # pragma: no cover - no s'ha d'arribar a cridar
        raise AssertionError("no s'havia de baixar la llista sencera")

    monkeypatch.setattr(R, "_consulta_via", lambda *a, **k: ("ARBRELLS DELS", "CL", "1"))
    monkeypatch.setattr(R, "_consulta_via_all_streets", _boom)
    R.cadastre_portal_signals("superficie_parcela", _decided(), Path("/no/existeix"))
    assert wired["via"] == "ARBRELLS DELS"


def test_blanc_quan_ni_via_b_ni_la_llista_troben_res(monkeypatch, wired) -> None:
    decided = _decided()
    decided["street_address"]["value"] = "Carrer Inexistent Absolut, 5"
    monkeypatch.setattr(R, "_consulta_via", lambda *a, **k: None)
    assert R.cadastre_portal_signals("superficie_parcela", decided, Path("/no/existeix")) == []
    assert "via" not in wired
