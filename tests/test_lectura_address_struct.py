"""Tests de l'objecte estructurat de l'adreça (peces 3 i 4 del disseny d'adreces).

Vegeu `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` (D1, D2, D3b, A1). Dues meitats:

- `address_struct.parse` / `.from_extra_concepts` — la validació a Python que substitueix la
  sortida estructurada que `claude -p` no dona (A1);
- el cablejat a `cadastre_reader` — les alternatives són **intents de consulta**, i el nom
  acceptat surt sempre de la llista real del municipi.

0 xarxa.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.lectura import address_struct as A  # noqa: E402
from automation.lectura import cadastre_reader as R  # noqa: E402

BELL_LLOC = [
    ("ARBRELLS DELS", "CL", "1"),
    ("ONZE DE SETEMBRE", "PZ", "126"),
    ("TELEGRAFOS", "TR", "82"),
    ("TELEGRAFS", "TR", "72"),
    ("SANT JOSEP", "CL", "7"),
]


# ------------------------------------------------------------------- validació


def test_objecte_complet() -> None:
    struct, problems = A.parse({
        "tipus_via": "plaça", "nom_via": "Onze de Setembre",
        "nom_via_alternatives": ["11 de Setembre", "Once de Septiembre"],
        "portals": ["5"], "municipi": "Bell-lloc d'Urgell", "municipi_alternatives": ["BELL-LLOC"],
    })
    assert problems == []
    assert struct.via_hints() == ["Onze de Setembre", "11 de Setembre", "Once de Septiembre"]
    assert struct.municipi_hints() == ["Bell-lloc d'Urgell", "BELL-LLOC"]
    assert struct.portals == ("5",)


@pytest.mark.parametrize(
    "raw,per_que",
    [
        (None, "no és un objecte"),
        ("Carrer Arbrells 18A", "text pla, no objecte"),
        ([], "llista"),
        ({"municipi": "Linyola"}, "sense nom_via"),
        ({"nom_via": "Arbrells"}, "sense municipi"),
        ({"nom_via": "   ", "municipi": "Linyola"}, "nom_via buit"),
        ({"nom_via": "123", "municipi": "Linyola"}, "nom_via sense cap lletra"),
        ({"nom_via": "A" * 200, "municipi": "Linyola"}, "nom_via desbocat"),
    ],
)
def test_objecte_invalid_es_descarta_sencer(raw, per_que: str) -> None:
    """Descartar l'objecte fa tornar al text lliure: es perd la millora, mai s'hi guanya un
    error. Per això no hi ha bucle de re-pregunta."""
    struct, problems = A.parse(raw)
    assert struct is None, per_que
    assert problems


def test_alternativa_repetida_o_igual_a_la_principal_no_compta() -> None:
    struct, _ = A.parse({
        "nom_via": "Arbrells", "municipi": "Linyola",
        "nom_via_alternatives": ["ARBRELLS", "arbrells", "Arbrells dels", "Arbrells dels"],
    })
    assert struct.nom_via_alternatives == ("Arbrells dels",)


def test_alternatives_limitades() -> None:
    struct, problems = A.parse({
        "nom_via": "X carrer", "municipi": "Linyola",
        "nom_via_alternatives": [f"variant {i}" for i in range(20)],
    })
    assert len(struct.nom_via_alternatives) == A.MAX_ALTERNATIVES
    assert any("se'n conserven" in p for p in problems)


@pytest.mark.parametrize(
    "portals,esperat",
    [
        (["18A", "18B", "20"], ("18A", "18B", "20")),
        (["18 A"], ("18A",)),
        ([18, "20"], ("18", "20")),
        # "3r" és un pis (ordinal enganxat) i "baixos" no té dígits; "2a" es conserva a posta,
        # perquè "18A" és un portal de debò: val més deixar passar un pis que menjar-se un portal.
        (["3r", "2a", "baixos"], ("2A",)),
        (["1er", "5è", "3º", "2ª"], ()),
        (["18A", "18A"], ("18A",)),
        ("18A", ()),                            # no és una llista
    ],
)
def test_portals(portals, esperat) -> None:
    struct, _ = A.parse({"nom_via": "Arbrells", "municipi": "Linyola", "portals": portals})
    assert struct.portals == esperat


def test_una_sola_definicio_d_ordinals_de_pis() -> None:
    """`cadastre_reader` fa servir la MATEIXA regex, no una còpia: el projecte ja va pagar car
    tenir dues llistes ad-hoc divergents (vegeu `normalize.COMPONENT_VALUE_KEY`)."""
    assert R._FLOOR_ORDINAL_RE is A.FLOOR_ORDINAL_RE


def test_claus_desconegudes_no_tomben_l_objecte() -> None:
    struct, problems = A.parse({"nom_via": "Arbrells", "municipi": "Linyola", "codi_postal": "25240"})
    assert struct is not None
    assert any("claus ignorades" in p for p in problems)


# ---------------------------------------------------------------------- fusió


def test_fusiona_les_grafies_de_documents_diferents() -> None:
    """La variabilitat DINS d'un projecte és el material útil: la comanda escriu una grafia i
    el pressupost una altra."""
    extra = {A.STRUCT_CONCEPT: [
        {"value": {"nom_via": "ARBRELLS", "municipi": "CASTELLAR DEL VALLES"}, "font": "comanda N20"},
        {"value": {"nom_via": "Arbrells", "municipi": "Castellar del Vallès",
                   "nom_via_alternatives": ["Arbrells dels"]}, "font": "pressupost p.1"},
    ]}
    struct, _ = A.from_extra_concepts(extra)
    assert struct.nom_via == "ARBRELLS"
    assert struct.nom_via_alternatives == ("Arbrells dels",)
    assert struct.fonts == ("comanda N20", "pressupost p.1")


def test_fusio_ignora_els_objectes_invalids_i_es_queda_amb_el_bo() -> None:
    extra = {A.STRUCT_CONCEPT: [
        {"value": "no és un objecte", "font": "correu"},
        {"value": {"nom_via": "Arbrells", "municipi": "Linyola"}, "font": "pressupost"},
    ]}
    struct, problems = A.from_extra_concepts(extra)
    assert struct is not None and struct.nom_via == "Arbrells"
    assert problems


@pytest.mark.parametrize("extra", [None, {}, {"altre_concepte": []}, {A.STRUCT_CONCEPT: "no llista"}])
def test_sense_objecte_no_passa_res(extra) -> None:
    struct, problems = A.from_extra_concepts(extra)
    assert struct is None and problems == []


# ------------------------------------------------------- cablejat amb la cadena


@pytest.fixture
def wired(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(R, "_consulta_via_all_streets", lambda p, m: list(BELL_LLOC))
    monkeypatch.setattr(R, "_consulta_via", lambda *a, **k: None)  # via B no troba res
    seen: dict[str, str] = {}

    def _resolve_portal(province, muni, via, number, letter, *, tipo_via="CL"):
        seen["via"], seen["tipo_via"], seen["muni"] = via, tipo_via, muni
        return []

    monkeypatch.setattr(R, "resolve_portal", _resolve_portal)
    return seen


def _decided(address: str, municipi: str = "Bell-lloc d'Urgell") -> dict[str, dict]:
    return {
        "street_address": {"estat": "segur", "value": address},
        "municipality": {"estat": "segur", "value": municipi},
    }


def test_alternativa_rescata_un_empat(wired) -> None:
    """`Telegraf` empata entre TELEGRAFS (0,94) i TELEGRAFOS (0,89) i queda en blanc; amb la
    grafia que el lector ha vist al document, es resol — i el nom surt de la llista real."""
    extra = {A.STRUCT_CONCEPT: [{"value": {
        "nom_via": "Telegraf", "municipi": "Bell-lloc d'Urgell",
        "nom_via_alternatives": ["Telegrafs"],
    }}]}
    R.cadastre_portal_signals("superficie_parcela", _decided("Carrer Telegraf, 5"), Path("/no/hi/es"), extra)
    assert wired["via"] == "TELEGRAFS"
    assert wired["tipo_via"] == "TR"


def test_sense_objecte_l_empat_segueix_en_blanc(wired) -> None:
    assert R.cadastre_portal_signals(
        "superficie_parcela", _decided("Carrer Telegraf, 5"), Path("/no/hi/es")) == []
    assert "via" not in wired


def test_una_alternativa_inventada_no_pot_guanyar(wired) -> None:
    """Regla dura: el nom acceptat surt SEMPRE de la llista del municipi. Si el model es treu
    un carrer del barret, no hi és i no passa."""
    extra = {A.STRUCT_CONCEPT: [{"value": {
        "nom_via": "Telegraf", "municipi": "Bell-lloc d'Urgell",
        "nom_via_alternatives": ["Avinguda Imaginària dels Somnis"],
    }}]}
    assert R.cadastre_portal_signals(
        "superficie_parcela", _decided("Carrer Telegraf, 5"), Path("/no/hi/es"), extra) == []
    assert "via" not in wired


def test_alternativa_de_municipi_resol_la_provincia(wired) -> None:
    """El municipi llegit no es pot decidir («Castellar» encaixa amb quatre); una alternativa
    del lector el desempata pel padró, sense xarxa."""
    def boom(*a, **k):
        raise AssertionError("no calia consultar el municipi en línia")

    R._consulta_municipio = boom
    extra = {A.STRUCT_CONCEPT: [{"value": {
        "nom_via": "Arbrells", "municipi": "Castellar",
        "municipi_alternatives": ["Castellar del Vallès"],
    }}]}
    R.cadastre_portal_signals("superficie_parcela", _decided("Carrer Arbrells, 18A", "Castellar"),
                              Path("/no/hi/es"), extra)
    assert wired["muni"] == "CASTELLAR DEL VALLES"


def test_els_portals_no_surten_mai_de_l_objecte(wired) -> None:
    """Eix portal: 18A i 18B són dos edificis. Els portals els mana `portals_from_address`,
    encara que l'objecte en digui uns altres — si no, es ressuscita el bug 18B→18A."""
    vistos: list[tuple[str, str]] = []

    def _resolve_portal(province, muni, via, number, letter, *, tipo_via="CL"):
        vistos.append((number, letter))
        return []

    R.resolve_portal = _resolve_portal
    extra = {A.STRUCT_CONCEPT: [{"value": {
        "nom_via": "Arbrells", "municipi": "Bell-lloc d'Urgell", "portals": ["99", "100"],
    }}]}
    R.cadastre_portal_signals("superficie_parcela", _decided("Carrer Arbrells, 18A"), Path("/no/hi/es"), extra)
    assert vistos == [("18", "A")]
