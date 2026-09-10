"""Tests de `automation/lectura/cadastre_reader.py` (Fix D, `PLA-PENDENTS-0B-0C-0D-2026-08-26.md` §7).

Tot amb `monkeypatch`, 0 xarxa. Els fixtures JSON/XML de `tests/fixtures/cadastre_castellar/`
son respostes REALS del Cadastre (Callejero DNPLOC + WFS INSPIRE), capturades 2026-08-31 per als
tres portals de Carrer Arbrells 18A/18B/20 (Castellar del Valles): 441+423+420 = 1.284, igual que
l'informe signat de l'Eva (`reference-material/.../eva_reference_values.json`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.lectura import cadastre_reader as R  # noqa: E402

FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "cadastre_castellar"


def _wfs_fixture_polygon(name: str) -> tuple[int, list[tuple[float, float]]]:
    text = (FIXTURES / name).read_text(encoding="ISO-8859-1")
    parsed = R._parse_wfs(text)
    assert parsed is not None
    return parsed


# ---------------------------------------------------------------------------
# (a) portals_from_address — els 8 exemples de §7.2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("address,expected", [
    ("Carrer Arbrells, 18A, 18B i 20", ("Arbrells", [("18", "A"), ("18", "B"), ("20", "")])),
    ("C/ Mestre Ramon Ortiz 15", ("Mestre Ramon Ortiz", [("15", "")])),
    ("Carrer Girasols, 7 (Urb. El Roser)", ("Girasols", [("7", "")])),
    ("18-20", ("", [("18", ""), ("20", "")])),
    ("entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz", ("", [])),
    ("Carrer Tal, s/n", ("", [])),
    ("Polígon Industrial X, Nau 5", ("", [])),
    ("Carrer Clot de la Llacuna, 16", ("Clot de la Llacuna", [("16", "")])),
])
def test_portals_from_address(address: str, expected: tuple[str, list[tuple[str, str]]]) -> None:
    assert R.portals_from_address(address) == expected


def test_portals_from_address_empty() -> None:
    assert R.portals_from_address("") == ("", [])
    assert R.portals_from_address(None) == ("", [])  # type: ignore[arg-type]


@pytest.mark.parametrize("address,expected", [
    # La conjuncio NO es la lletra del portal: amb `[("18","I")]`, `resolve_portal` filtrava
    # per una lletra que cap portal real no te i el 18 desapareixia EN SILENCI (nomes el 20
    # arribava a la superficie i a l'RC).
    ("Carrer Arbrells, 18 i 20", ("Arbrells", [("18", ""), ("20", "")])),
    ("Calle Mayor, 5 y 7", ("Mayor", [("5", ""), ("7", "")])),
    ("Carrer Arbrells, 18A, 18B i 20", ("Arbrells", [("18", "A"), ("18", "B"), ("20", "")])),
    # "bis" i "núm" tampoc son lletra de portal.
    ("Carrer Major, 12 bis", ("Major", [("12", "")])),
    ("Carrer Major, núm 12", ("Major", [("12", "")])),
    ("Carrer Major nº 12", ("Major", [("12", "")])),
    # Nom de carrer amb xifres: el tall es per la coma que obre els portals, no pel primer digit.
    ("Carrer 11 de Setembre, 5", ("11 de Setembre", [("5", "")])),
    ("Avinguda 11 de Setembre, 5A", ("11 de Setembre", [("5", "A")])),
])
def test_portals_from_address_boundary_words_and_numeric_street_names(
    address: str, expected: tuple[str, list[tuple[str, str]]]
) -> None:
    assert R.portals_from_address(address) == expected


def test_portals_from_address_keeps_i_inside_street_name() -> None:
    """La paraula-frontera nomes es frontera ENTRE portals: "Sant Pere i Sant Pau" no es parteix."""
    assert R.portals_from_address("Carrer Sant Pere i Sant Pau, 3") == ("Sant Pere i Sant Pau", [("3", "")])


@pytest.mark.parametrize("address,expected", [
    # La coma del pis NO obre la llista de portals: el cap ja acaba en numero. Amb el tall
    # per aquesta coma, el 24 —l'unic portal bo— se n'anava al nom del carrer.
    ("Avinguda Catalunya, 24, 3r 2a", ("Catalunya", [("24", "")])),
    ("Carrer Major 12, 2n 1a", ("Major", [("12", "")])),
    # La primera coma SI que obre la llista (el cap no acaba en numero): el carrer no canvia,
    # i el pis/porta ja no compta com a portal.
    ("Carrer Major, 12, 2n 1a", ("Major", [("12", "")])),
    ("Calle Mayor 3, 2º", ("Mayor", [("3", "")])),
    ("C/ Nou, 5è 1a", ("Nou", [])),
])
def test_portals_from_address_floor_and_door_are_not_portals(
    address: str, expected: tuple[str, list[tuple[str, str]]]
) -> None:
    """Pis i porta ("3r 2a") tenen forma de portal i `resolve_portal` pot trobar un 3 i un 2
    de debo al carrer: la superficie sortiria sumada d'unes parcel·les alienes amb la
    confiança d'una consulta oficial."""
    assert R.portals_from_address(address) == expected


def test_portals_from_address_keeps_the_letter_of_a_real_portal() -> None:
    """El tall del pis no es pot menjar "18A"/"12E": la lletra del portal va sola."""
    assert R.portals_from_address("Carrer Arbrells, 18A") == ("Arbrells", [("18", "A")])
    assert R.portals_from_address("Carrer Arbrells, 12E") == ("Arbrells", [("12", "E")])
    assert R.portals_from_address("Carrer Arbrells, 18 A") == ("Arbrells", [("18", "A")])


@pytest.mark.parametrize("address,expected_street", [
    # El cas de la regressio: `av\.?` casava DINS de "Avda" i el carrer sortia com a
    # `'da. Catalunya'` -> cap via del Callejero -> superficie en blanc, per una llista
    # d'abreviatures incompleta.
    ("Avda. Catalunya 24", "Catalunya"),
    ("Avda Catalunya 24", "Catalunya"),
    ("Avgda. Catalunya 24", "Catalunya"),
    ("Av. Catalunya 24", "Catalunya"),
    ("Avinguda Catalunya, 24", "Catalunya"),
    # Mateix patro: `cam[ií]` es menjava la "i" de "Camino" i en deixava `'no Viejo'`.
    ("Camino Viejo 5", "Viejo"),
    ("Camí Ral 5", "Ral"),
])
def test_portals_from_address_short_abbreviations_do_not_eat_the_street(
    address: str, expected_street: str
) -> None:
    assert R.portals_from_address(address)[0] == expected_street


def test_an_abbreviation_still_missing_leaves_the_address_whole() -> None:
    """"Pge." no es a la llista (i cap llista no sera completa). El lookahead fa que en
    quedi l'adreça sencera —que un huma reconeix i el fuzzy encara pot salvar— en comptes
    de `'e. Mercè'`, mig nom de carrer amb tota la pinta de bo."""
    assert R.portals_from_address("Pge. Mercè 3") == ("Pge. Mercè", [("3", "")])


@pytest.mark.parametrize("address,expected_street", [
    ("Carrer Arbrells, 18A, 18B i 20", "Arbrells"),
    ("Carrer Girasols, 7", "Girasols"),
    ("C/ Girassols, 7", "Girassols"),
    ("Carrer Tulipa, 3", "Tulipa"),
    ("Carrer Clot de la Llacuna, 16", "Clot de la Llacuna"),
    ("C. Clot de la Llacuna, 16", "C. Clot de la Llacuna"),
    ("C/ General Ferraz, 20", "General Ferraz"),
    ("C/ Mestre Ramon Ortiz 15", "Mestre Ramon Ortiz"),
    ("C/ Santa Gemma, 4", "Santa Gemma"),
    ("Carrer de la Miranda, 39", "Miranda"),
])
def test_portals_from_address_keeps_the_real_project_streets(
    address: str, expected_street: str
) -> None:
    """Les adreces dels 8 projectes (annex A de `PLA-PENDENTS-0B-0C-0D-2026-08-26.md`):
    completar la llista d'abreviatures no en pot moure cap."""
    assert R.portals_from_address(address)[0] == expected_street


@pytest.mark.parametrize("hint,official,expected", [
    ("Arbrells", "ARBRELLS DELS", True),      # el Callejero afegeix l'article
    ("Girassols", "GIRASOLS DELS", True),     # variant ortografica (fuzzy 0,94)
    ("Clot de la Llacuna", "CLOT DE LA LLACUNA", True),
    ("Carrer", "CARRERADA PD", False),        # `_consulta_via` puntua 60 per "conte" (fuzzy 0,80)
    ("Font", "FONTANELLA", False),
    # Hint d'UNA paraula: la regla de subconjunt reproduia el "conte" de `_consulta_via` i
    # acceptava un carrer que nomes comparteix la primera paraula (n'hi ha dos de diferents).
    ("Major", "MAJOR DE BALAFIA", False),
    ("Nou", "NOU DE SANT FRANCESC", False),
    ("Major", "MAJOR", True),
    ("Major", "MAJOR DEL", True),             # article del Callejero: no es paraula de mes
    ("Carrerada", "CARRERADA PD", True),      # abreviatura del Callejero (partida), tampoc
])
def test_via_name_matches(hint: str, official: str, expected: bool) -> None:
    assert R._via_name_matches(hint, official) is expected


# ---------------------------------------------------------------------------
# (b) resolve_portal — fixture JSON real de Castellar
# ---------------------------------------------------------------------------


def _fake_fetch_dnploc(url: str) -> str:
    if "Numero=18" in url:
        return (FIXTURES / "dnploc_portal_18.json").read_text(encoding="utf-8")
    if "Numero=20" in url:
        return (FIXTURES / "dnploc_portal_20.json").read_text(encoding="utf-8")
    if "Numero=999" in url:
        return (FIXTURES / "dnploc_error_43.json").read_text(encoding="utf-8")
    raise AssertionError(f"URL inesperada: {url}")


def test_resolve_portal_with_letter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_fetch", _fake_fetch_dnploc)

    hits_a = R.resolve_portal("BARCELONA", "CASTELLAR DEL VALLES", "ARBRELLS DELS", "18", "A")
    assert [h.rc for h in hits_a] == ["3298012DG2039N"]
    assert not hits_a[0].ambiguous

    hits_b = R.resolve_portal("BARCELONA", "CASTELLAR DEL VALLES", "ARBRELLS DELS", "18", "B")
    assert [h.rc for h in hits_b] == ["3298013DG2039N"]


def test_resolve_portal_no_letter_but_only_lettered_entries_is_ambiguous(tmp_path: Path, monkeypatch) -> None:
    """18/'' amb nomes 18A i 18B a la resposta -> AMBIGU, es tornen totes marcades (no se sumen)."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_fetch", _fake_fetch_dnploc)

    hits = R.resolve_portal("BARCELONA", "CASTELLAR DEL VALLES", "ARBRELLS DELS", "18", "")
    assert {h.rc for h in hits} == {"3298012DG2039N", "3298013DG2039N"}
    assert all(h.ambiguous for h in hits)


def test_resolve_portal_single_hit_no_letter(tmp_path: Path, monkeypatch) -> None:
    """Portal 20 (resposta `bico.bi`, no `lrcdnp.rcdnp[]`): un sol hit, no ambigu."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_fetch", _fake_fetch_dnploc)

    hits = R.resolve_portal("BARCELONA", "CASTELLAR DEL VALLES", "ARBRELLS DELS", "20", "")
    assert [h.rc for h in hits] == ["3298014DG2039N"]
    assert not hits[0].ambiguous


def test_resolve_portal_unknown_letter_returns_empty(tmp_path: Path, monkeypatch) -> None:
    """(c) portal amb lletra inexistent -> []."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_fetch", _fake_fetch_dnploc)

    hits = R.resolve_portal("BARCELONA", "CASTELLAR DEL VALLES", "ARBRELLS DELS", "18", "Z")
    assert hits == []


def test_resolve_portal_error_43_returns_empty(tmp_path: Path, monkeypatch) -> None:
    """Numero inexistent (error 43 del Cadastre) -> [], mai un fallback al mes proper."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_fetch", _fake_fetch_dnploc)

    hits = R.resolve_portal("BARCELONA", "CASTELLAR DEL VALLES", "ARBRELLS DELS", "999", "")
    assert hits == []


def test_resolve_portal_network_exception_returns_empty(tmp_path: Path, monkeypatch, caplog) -> None:
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")

    def boom(url: str) -> str:
        raise RuntimeError("xarxa caiguda")
    monkeypatch.setattr(R, "_fetch", boom)

    with caplog.at_level("WARNING"):
        hits = R.resolve_portal("BARCELONA", "CASTELLAR DEL VALLES", "ARBRELLS DELS", "18", "A")
    assert hits == []
    assert any("DNPLOC failed" in rec.message for rec in caplog.records)


def test_resolve_portal_uses_cache_on_second_call(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    calls = {"n": 0}

    def counting_fetch(url: str) -> str:
        calls["n"] += 1
        return _fake_fetch_dnploc(url)
    monkeypatch.setattr(R, "_fetch", counting_fetch)

    R.resolve_portal("BARCELONA", "CASTELLAR DEL VALLES", "ARBRELLS DELS", "18", "A")
    R.resolve_portal("BARCELONA", "CASTELLAR DEL VALLES", "ARBRELLS DELS", "18", "B")  # mateix Numero=18: cache hit
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# parcel_area_and_polygon — fixtures WFS reals
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# `_cached_consulta_municipio`/`_cached_consulta_via` — embolcall de cache sobre la via B
# (que no en te de propia): sense aixo, cada consolidacio resol municipi+via DOS cops
# (un per `referencia_catastral`, un per `superficie_parcela`).
# ---------------------------------------------------------------------------


def test_cached_consulta_municipio_hits_cache_on_second_call(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    calls = {"n": 0}

    def fake(province, hint, _retry_normalized=True):
        calls["n"] += 1
        return ("CASTELLAR DEL VALLES", "08", "51")
    monkeypatch.setattr(R, "_consulta_municipio", fake)

    r1 = R._cached_consulta_municipio("BARCELONA", "Castellar")
    r2 = R._cached_consulta_municipio("BARCELONA", "Castellar")
    assert r1 == r2 == ("CASTELLAR DEL VALLES", "08", "51")
    assert calls["n"] == 1


def test_cached_consulta_municipio_caches_negative_result_too(tmp_path: Path, monkeypatch) -> None:
    """Rubí (Annex A): el Callejero no resol la via -> `None`. Cal cachejar el `None`
    tambe, o cada consolidacio tornaria a fer la crida lenta que ja sabem que falla."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    calls = {"n": 0}

    def fake(province, hint, _retry_normalized=True):
        calls["n"] += 1
        return None
    monkeypatch.setattr(R, "_consulta_municipio", fake)

    assert R._cached_consulta_municipio("BARCELONA", "Municipi Inexistent") is None
    assert R._cached_consulta_municipio("BARCELONA", "Municipi Inexistent") is None
    assert calls["n"] == 1


def test_cached_consulta_via_hits_cache_on_second_call(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    calls = {"n": 0}

    def fake(province, muni, hint, full_address_context=""):
        calls["n"] += 1
        return ("ARBRELLS DELS", "CL", "372")
    monkeypatch.setattr(R, "_consulta_via", fake)

    r1 = R._cached_consulta_via("BARCELONA", "CASTELLAR DEL VALLES", "Arbrells")
    r2 = R._cached_consulta_via("BARCELONA", "CASTELLAR DEL VALLES", "Arbrells")
    assert r1 == r2 == ("ARBRELLS DELS", "CL", "372")
    assert calls["n"] == 1


def test_parcel_area_and_polygon_from_fixtures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    mapping = {
        "3298012DG2039N": "wfs_3298012DG2039N.xml",
        "3298013DG2039N": "wfs_3298013DG2039N.xml",
        "3298014DG2039N": "wfs_3298014DG2039N.xml",
    }

    def fake_fetch(url: str) -> str:
        for rc, filename in mapping.items():
            if rc in url:
                return (FIXTURES / filename).read_text(encoding="ISO-8859-1")
        raise AssertionError(url)
    monkeypatch.setattr(R, "_fetch", fake_fetch)

    area_12, poly_12 = R.parcel_area_and_polygon("3298012DG2039N")
    area_13, _ = R.parcel_area_and_polygon("3298013DG2039N")
    area_14, _ = R.parcel_area_and_polygon("3298014DG2039N")
    assert (area_12, area_13, area_14) == (441, 423, 420)
    assert area_12 + area_13 + area_14 == 1284, "l'area OFICIAL (WFS areaValue) suma exacte; shapely arrodoneix"
    assert len(poly_12) >= 3


def test_parcel_area_and_polygon_exception_report_is_no_parcel(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_fetch", lambda url: (FIXTURES / "wfs_exception_report.xml").read_text(encoding="ISO-8859-1"))

    assert R.parcel_area_and_polygon("3298099DG2039N") is None


# ---------------------------------------------------------------------------
# (d)-(f) cadastre_portal_signals — resolve_portal/parcel_area_and_polygon falsejats
# ---------------------------------------------------------------------------


def _fake_muni(province: str, hint: str, _retry_normalized: bool = True):
    if province == "BARCELONA" and "castellar" in hint.lower():
        return ("CASTELLAR DEL VALLES", "08", "51")
    if province == "LLEIDA" and "muni" in hint.lower():
        return ("MUNI", "25", "01")
    return None


def _fake_via(province: str, muni: str, hint: str, full_address_context: str = ""):
    if "arbrells" in hint.lower():
        return ("ARBRELLS DELS", "CL", "372")
    if "carrer x" in hint.lower() or hint.lower() == "x":
        # `nv` del Callejero = NOMES el nom ("ARBRELLS DELS"); el tipus de via va a part
        # (`tv`), no dins del nom.
        return ("X", "CL", "1")
    return None


def test_cadastre_portal_signals_contiguous_sums(tmp_path: Path, monkeypatch) -> None:
    """(a) 3 portals contigus -> 1 senyal superficie_parcela = '1284' + 1 senyal RC amb 3 refs."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_consulta_municipio", _fake_muni)
    monkeypatch.setattr(R, "_consulta_via", _fake_via)

    def fake_resolve(province, muni, via, number, letter, *, tipo_via="CL"):
        table = {
            ("18", "A"): [R.ParcelHit(rc="3298012DG2039N", pnp="18", plp="A")],
            ("18", "B"): [R.ParcelHit(rc="3298013DG2039N", pnp="18", plp="B")],
            ("20", ""): [R.ParcelHit(rc="3298014DG2039N", pnp="20", plp="")],
        }
        return table.get((number, letter), [])
    monkeypatch.setattr(R, "resolve_portal", fake_resolve)

    fixtures = {
        "3298012DG2039N": _wfs_fixture_polygon("wfs_3298012DG2039N.xml"),
        "3298013DG2039N": _wfs_fixture_polygon("wfs_3298013DG2039N.xml"),
        "3298014DG2039N": _wfs_fixture_polygon("wfs_3298014DG2039N.xml"),
    }
    monkeypatch.setattr(R, "parcel_area_and_polygon", lambda rc: fixtures[rc])

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer Arbrells, 18A, 18B i 20"},
        "municipality": {"estat": "segur", "value": "Castellar del Valles"},
    }
    sigs = R.cadastre_portal_signals("superficie_parcela", decided, tmp_path)
    assert len(sigs) == 1
    assert sigs[0].value == "1284"
    assert "3/3 parcel·les contigues" in sigs[0].note
    assert sigs[0].origin == "python"
    assert sigs[0].is_a is False

    sigs_rc = R.cadastre_portal_signals("referencia_catastral", decided, tmp_path)
    assert len(sigs_rc) == 1
    assert sigs_rc[0].value == "3298012DG2039N+3298013DG2039N+3298014DG2039N"


def test_cadastre_portal_signals_conjunction_keeps_both_portals(tmp_path: Path, monkeypatch) -> None:
    """«18 i 20»: els DOS portals es consulten i se sumen (abans, la "i" es llegia com a
    lletra del 18, `resolve_portal` no en trobava cap i la superficie era nomes la del 20)."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_consulta_municipio", _fake_muni)
    monkeypatch.setattr(R, "_consulta_via", _fake_via)

    asked: list[tuple[str, str]] = []

    def fake_resolve(province, muni, via, number, letter, *, tipo_via="CL"):
        asked.append((number, letter))
        table = {
            ("18", ""): [R.ParcelHit(rc="AAAA1111AA0001", pnp="18", plp="")],
            ("20", ""): [R.ParcelHit(rc="BBBB2222BB0002", pnp="20", plp="")],
        }
        return table.get((number, letter), [])
    monkeypatch.setattr(R, "resolve_portal", fake_resolve)

    left = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    right = [(10.0, 0.0), (20.0, 0.0), (20.0, 10.0), (10.0, 10.0)]
    areas = {"AAAA1111AA0001": (441, left), "BBBB2222BB0002": (420, right)}
    monkeypatch.setattr(R, "parcel_area_and_polygon", lambda rc: areas[rc])

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer Arbrells, 18 i 20"},
        "municipality": {"estat": "segur", "value": "Castellar del Valles"},
    }
    sigs = R.cadastre_portal_signals("superficie_parcela", decided, tmp_path)
    assert asked == [("18", ""), ("20", "")]
    assert [s.value for s in sigs] == ["861"]

    sigs_rc = R.cadastre_portal_signals("referencia_catastral", decided, tmp_path)
    assert sigs_rc[0].value == "AAAA1111AA0001+BBBB2222BB0002"


def test_cadastre_portal_signals_rejects_wrong_street_name(tmp_path: Path, monkeypatch, caplog) -> None:
    """El Callejero torna un carrer que nomes CONTE el text cercat -> cap senyal.
    Millor un blanc honest que la parcel·la d'un altre carrer amb confiança de font oficial.

    Des de la peça 1 del disseny d'adreces (`resolve_via`, 2026-09-01) el rebuig de via B ja no
    acaba la historia: es reintenta sobre la llista sencera del municipi. La intencio del test
    no canvia —cap parcel·la d'un altre carrer— pero ara cobreix les DUES portes: `FONTANELLA`
    tampoc no passa la tria del conjunt tancat (`FONT` vs `FONTANELLA` = 0,57, per sota de 0,85).
    """
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_consulta_municipio", _fake_muni)
    monkeypatch.setattr(R, "_consulta_via", lambda *a, **k: ("FONTANELLA", "CL", "9"))
    monkeypatch.setattr(R, "_consulta_via_all_streets", lambda p, m: [("FONTANELLA", "CL", "9")])

    def boom(*a, **k):
        raise AssertionError("no s'ha de consultar cap portal d'un carrer que no encaixa")
    monkeypatch.setattr(R, "resolve_portal", boom)

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer Font, 5"},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    with caplog.at_level("WARNING"):
        assert R.cadastre_portal_signals("superficie_parcela", decided, tmp_path) == []
    assert any("cap carrer del Callejero correspon" in rec.message for rec in caplog.records)


def test_cadastre_portal_signals_noncontiguous_no_sum(tmp_path: Path, monkeypatch) -> None:
    """(b) 2 portals no contigus -> 2 candidats individuals, cap suma."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_consulta_municipio", _fake_muni)
    monkeypatch.setattr(R, "_consulta_via", _fake_via)

    def fake_resolve(province, muni, via, number, letter, *, tipo_via="CL"):
        table = {
            ("1", ""): [R.ParcelHit(rc="AAAA1111AA0001", pnp="1", plp="")],
            ("50", ""): [R.ParcelHit(rc="BBBB2222BB0002", pnp="50", plp="")],
        }
        return table.get((number, letter), [])
    monkeypatch.setattr(R, "resolve_portal", fake_resolve)

    square_a = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    square_b = [(1000.0, 1000.0), (1010.0, 1000.0), (1010.0, 1010.0), (1000.0, 1010.0)]
    areas = {"AAAA1111AA0001": (100, square_a), "BBBB2222BB0002": (100, square_b)}
    monkeypatch.setattr(R, "parcel_area_and_polygon", lambda rc: areas[rc])

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer X, 1-50"},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    sigs = R.cadastre_portal_signals("superficie_parcela", decided, tmp_path)
    assert len(sigs) == 2
    assert {s.value for s in sigs} == {"100"}
    assert all("no contigues" in (s.note or "") for s in sigs)

    # referencia_catastral es SEMPRE un sol senyal, contigu o no.
    sigs_rc = R.cadastre_portal_signals("referencia_catastral", decided, tmp_path)
    assert len(sigs_rc) == 1
    assert sigs_rc[0].value == "AAAA1111AA0001+BBBB2222BB0002"


def test_cadastre_portal_signals_unknown_letter_returns_empty(tmp_path: Path, monkeypatch) -> None:
    """(c) portal amb lletra inexistent -> []."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_consulta_municipio", _fake_muni)
    monkeypatch.setattr(R, "_consulta_via", _fake_via)
    monkeypatch.setattr(R, "resolve_portal", lambda *a, **k: [])

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer X, 18Z"},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    assert R.cadastre_portal_signals("superficie_parcela", decided, tmp_path) == []


def test_cadastre_portal_signals_no_project_path_calls_nothing(monkeypatch) -> None:
    """Sense `project_path` (p. ex. tests sintetics de `consolidate_python(out, None, ...)`) ->
    [] sense cap crida: mateix contracte que `http_field_signals`."""
    def boom(*a, **k):
        raise AssertionError("no s'hauria de cridar sense project_path")
    monkeypatch.setattr(R, "_consulta_municipio", boom)

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer X, 5"},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    assert R.cadastre_portal_signals("superficie_parcela", decided, None) == []


def test_cadastre_portal_signals_street_address_no_trobat_calls_nothing(tmp_path: Path, monkeypatch) -> None:
    """(d) `street_address` `no_trobat` -> [] sense cap crida."""
    def boom(*a, **k):
        raise AssertionError("no s'hauria de cridar amb street_address no_trobat")
    monkeypatch.setattr(R, "_consulta_municipio", boom)
    monkeypatch.setattr(R, "_consulta_via", boom)
    monkeypatch.setattr(R, "resolve_portal", boom)

    decided = {
        "street_address": {"estat": "no_trobat", "value": None},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    assert R.cadastre_portal_signals("superficie_parcela", decided, tmp_path) == []
    assert R.cadastre_portal_signals("referencia_catastral", decided, tmp_path) == []


def test_cadastre_portal_signals_municipality_no_trobat_calls_nothing(tmp_path: Path, monkeypatch) -> None:
    def boom(*a, **k):
        raise AssertionError("no s'hauria de cridar amb municipality no_trobat")
    monkeypatch.setattr(R, "_consulta_municipio", boom)

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer X, 5"},
        "municipality": {"estat": "no_trobat", "value": None},
    }
    assert R.cadastre_portal_signals("superficie_parcela", decided, tmp_path) == []


def test_cadastre_portal_signals_no_portal_number_calls_nothing(tmp_path: Path, monkeypatch) -> None:
    def boom(*a, **k):
        raise AssertionError("no s'hauria de cridar sense numero de portal")
    monkeypatch.setattr(R, "_consulta_municipio", boom)

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer X, s/n"},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    assert R.cadastre_portal_signals("superficie_parcela", decided, tmp_path) == []


def test_cadastre_portal_signals_unknown_key_returns_empty() -> None:
    assert R.cadastre_portal_signals("architect_name", {}, None) == []


def test_cadastre_portal_signals_network_exception_swallowed(tmp_path: Path, monkeypatch, caplog) -> None:
    """(e) excepcio de xarxa -> [] i warning. La consolidacio mai no pot fallar per aquest lector."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")

    def boom(*a, **k):
        raise RuntimeError("xarxa caiguda")
    monkeypatch.setattr(R, "_consulta_municipio", boom)

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer X, 5"},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    with caplog.at_level("WARNING"):
        result = R.cadastre_portal_signals("superficie_parcela", decided, tmp_path)
    assert result == []
    assert any("unexpected failure" in rec.message for rec in caplog.records)


def test_cadastre_portal_signals_points_note_all_inside(tmp_path: Path, monkeypatch) -> None:
    """(f) COORDENADES.txt amb 5 punts dins -> nota '5/5'."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_consulta_municipio", _fake_muni)
    monkeypatch.setattr(R, "_consulta_via", _fake_via)

    def fake_resolve(province, muni, via, number, letter, *, tipo_via="CL"):
        return [R.ParcelHit(rc="AAAA1111AA0001", pnp="1", plp="")] if number == "1" else []
    monkeypatch.setattr(R, "resolve_portal", fake_resolve)

    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    monkeypatch.setattr(R, "parcel_area_and_polygon", lambda rc: (100, square))

    proj = tmp_path / "3001621 CASTELLAR"
    proj.mkdir()
    (proj / "COORDENADES.txt").write_text(
        "P-1\n5;5;100\nP-2\n5;6;100\nP-3\n5;4;100\nP-4\n4;5;100\nP-5\n6;5;100\n", encoding="utf-8")

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer X, 1"},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    sigs = R.cadastre_portal_signals("superficie_parcela", decided, proj)
    assert len(sigs) == 1
    assert "5/5 punts d'assaig dins de la unio" in sigs[0].note


def test_cadastre_portal_signals_points_note_point_outside(tmp_path: Path, monkeypatch) -> None:
    """(f) 1 punt fora -> el valor NO s'omple, i el motiu queda escrit.

    Fins a la peça 5 del disseny d'adreces (2026-09-01) això només era una nota informativa i
    la superfície sortia igualment. Ara la comprovació **veta**: cap punt dins i el més proper
    a molt més de 10 m vol dir que la parcel·la no és la del projecte, i val més un blanc amb
    el motiu que un número d'una altra parcel·la. Vegeu `tests/test_lectura_points_veto.py`
    per als límits (algun punt dins, deriva petita, sense fitxer de coordenades).
    """
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_consulta_municipio", _fake_muni)
    monkeypatch.setattr(R, "_consulta_via", _fake_via)

    def fake_resolve(province, muni, via, number, letter, *, tipo_via="CL"):
        return [R.ParcelHit(rc="AAAA1111AA0001", pnp="1", plp="")] if number == "1" else []
    monkeypatch.setattr(R, "resolve_portal", fake_resolve)

    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    monkeypatch.setattr(R, "parcel_area_and_polygon", lambda rc: (100, square))

    proj = tmp_path / "3001621 CASTELLAR"
    proj.mkdir()
    (proj / "COORDENADES.txt").write_text("P-1\n500;500;100\n", encoding="utf-8")

    decided = {
        "street_address": {"estat": "segur", "value": "Carrer X, 1"},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    sigs = R.cadastre_portal_signals("superficie_parcela", decided, proj)
    assert len(sigs) == 1
    assert sigs[0].value is None
    assert "0/1 dins" in sigs[0].note and "FORA" in sigs[0].note
    assert "COORDENADES.txt" in sigs[0].note


def test_cadastre_portal_signals_max_six_portals(tmp_path: Path, monkeypatch) -> None:
    """Maxim 6 portals per crida (§7.2 punt 3): el 7e no es consulta."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cadastre_cache")
    monkeypatch.setattr(R, "_consulta_municipio", _fake_muni)
    monkeypatch.setattr(R, "_consulta_via", _fake_via)

    seen_numbers: list[str] = []

    def fake_resolve(province, muni, via, number, letter, *, tipo_via="CL"):
        seen_numbers.append(number)
        return []
    monkeypatch.setattr(R, "resolve_portal", fake_resolve)

    address = "Carrer X, " + ", ".join(str(n) for n in range(1, 9))  # 8 portals
    decided = {
        "street_address": {"estat": "segur", "value": address},
        "municipality": {"estat": "segur", "value": "Muni"},
    }
    R.cadastre_portal_signals("superficie_parcela", decided, tmp_path)
    assert len(seen_numbers) <= 6
