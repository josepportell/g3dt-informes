"""Tests for geocoding robustness fixes.

Fix 1 — street-type word stripping in `_consulta_via`:
    Cadastre's fuzzy matcher treats full words like "Carrer" as part of the
    street name, returning wildly wrong parcels (e.g. CARRERADA PD instead of
    SANTA GEMMA CL). Stripping these tokens before the API call fixes that.

Fix 2 — Cadastre/Nominatim reconciliation in `geocode_project`:
    Run both in parallel; if Cadastre returns a parcel whose adjacents don't
    mention the project street, trust Nominatim and re-query Cadastre by
    coordinate.

All tests are hermetic — no real HTTP calls.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from automation import geocode_coordinates as gc


# ────────────────────────────────────────────────────────────────────────────
# Fix 1: _strip_street_type_word
# ────────────────────────────────────────────────────────────────────────────

class TestStreetTypeWordStripping:
    """Fix 1 — the hint sent to Cadastre must not include a street-type word."""

    def test_hint_carrer_prefix_stripped(self):
        """'Carrer Santa Gemma' → 'Santa Gemma'. This is the Vilanova bug."""
        assert gc._strip_street_type_word("Carrer Santa Gemma") == "Santa Gemma"

    def test_hint_calle_prefix_stripped(self):
        """'Calle Mayor' → 'Mayor'."""
        assert gc._strip_street_type_word("Calle Mayor") == "Mayor"

    def test_hint_complex_prefix_stripped(self):
        """'Carrer de la Pau' → 'Pau' (street-type word AND intervening
        preposition article both removed)."""
        assert gc._strip_street_type_word("Carrer de la Pau") == "Pau"

    def test_hint_carrer_dels_stripped(self):
        """'Camí dels Rectors' → 'Rectors' (connector 'dels' stripped)."""
        assert gc._strip_street_type_word("Camí dels Rectors") == "Rectors"

    def test_hint_paseo_de_la_stripped(self):
        """'Paseo de la Castellana' → 'Castellana' (Spanish connectors)."""
        assert gc._strip_street_type_word("Paseo de la Castellana") == "Castellana"

    def test_hint_avinguda_stripped(self):
        """Catalan 'Avinguda Catalunya' → 'Catalunya'."""
        assert gc._strip_street_type_word("Avinguda Catalunya") == "Catalunya"

    def test_hint_placa_with_accent(self):
        """'Plaça Major' (with cedilla) → 'Major'."""
        assert gc._strip_street_type_word("Plaça Major") == "Major"

    def test_hint_without_prefix_unchanged(self):
        """Hint without a street-type prefix passes through unchanged."""
        assert gc._strip_street_type_word("Santa Gemma") == "Santa Gemma"

    def test_hint_short_prefix_untouched(self):
        """Short abbreviations ('C.', 'Avda.') are handled by _parse_address,
        NOT by the street-type-word stripper. They must remain untouched
        here so existing behavior isn't regressed."""
        assert gc._strip_street_type_word("C. Santa Gemma") == "C. Santa Gemma"
        assert gc._strip_street_type_word("Avda. Aragón") == "Avda. Aragón"

    def test_hint_empty_string_safe(self):
        """Empty input returns empty string without crashing."""
        assert gc._strip_street_type_word("") == ""

    def test_case_insensitive(self):
        """Matching is case-insensitive."""
        assert gc._strip_street_type_word("CARRER SANTA GEMMA") == "SANTA GEMMA"
        assert gc._strip_street_type_word("calle mayor") == "mayor"


class TestConsultaViaIntegratesStripping:
    """Fix 1 end-to-end — `_consulta_via` sends the stripped hint to the API,
    NOT the original hint that triggered the Vilanova bug."""

    def test_carrer_santa_gemma_not_sent_to_api(self):
        """When the user passes 'Carrer Santa Gemma', the hint that actually
        reaches `_consulta_via_single` (and therefore the Cadastre API) is
        'Santa Gemma' — not 'Carrer Santa Gemma'.
        """
        api_calls: list[str] = []

        def fake_single(province, municipality, hint):
            api_calls.append(hint)
            # Return a plausible match the first time
            return ("SANTA GEMMA", "CL", "109")

        with patch.object(gc, "_consulta_via_single", side_effect=fake_single):
            result = gc._consulta_via(
                "BARCELONA", "VILANOVA I LA GELTRU", "Carrer Santa Gemma"
            )

        assert result == ("SANTA GEMMA", "CL", "109")
        assert api_calls, "Expected at least one call to _consulta_via_single"
        # First hint sent must not contain the word 'Carrer'
        assert "carrer" not in api_calls[0].lower(), (
            f"First hint sent to Cadastre still contains 'Carrer': {api_calls[0]!r}. "
            "The Vilanova bug is not fixed."
        )
        assert api_calls[0].strip().lower().startswith("santa gemma")

    def test_vilanova_would_resolve_to_santa_gemma(self):
        """Integration: given the wrong-match behavior of Cadastre on
        'Carrer Santa Gemma' (returns CARRERADA when prefix present),
        simulate the API so that only the stripped hint 'Santa Gemma'
        returns the correct street. Verify our code routes there.
        """

        def fake_single(province, municipality, hint):
            h = hint.strip().lower()
            # Simulate Cadastre's actual behaviour:
            #   "Carrer Santa Gemma" → wrong street
            #   "Santa Gemma"        → right street
            if "carrer" in h:
                return ("CARRERADA", "PD", "83")
            if "santa gemma" in h:
                return ("SANTA GEMMA", "CL", "109")
            return None

        with patch.object(gc, "_consulta_via_single", side_effect=fake_single):
            result = gc._consulta_via(
                "BARCELONA", "VILANOVA I LA GELTRU", "Carrer Santa Gemma"
            )

        assert result == ("SANTA GEMMA", "CL", "109"), (
            f"Expected ('SANTA GEMMA', 'CL', '109') after stripping 'Carrer'; "
            f"got {result!r}"
        )

    def test_sta_abbreviation_still_expanded(self):
        """Regression guard: existing 'Sta.' → 'Santa' abbreviation expansion
        must still work after the prefix stripping is added."""
        api_calls: list[str] = []

        def fake_single(province, municipality, hint):
            api_calls.append(hint)
            if "santa" in hint.lower():
                return ("SANTA GEMMA", "CL", "109")
            return None

        with patch.object(gc, "_consulta_via_single", side_effect=fake_single):
            result = gc._consulta_via(
                "BARCELONA", "VILANOVA I LA GELTRU", "Carrer de Sta. Gemma"
            )

        assert result == ("SANTA GEMMA", "CL", "109")
        # Somewhere in the attempts the expanded form must appear
        assert any("Santa Gemma" in c for c in api_calls), api_calls


# ────────────────────────────────────────────────────────────────────────────
# Fix 2: Cadastre/Nominatim reconciliation
# ────────────────────────────────────────────────────────────────────────────

class TestStreetMatchesCadastre:
    """Fix 2 — `_project_street_matches_cadastre` returns True only when
    the project street is one of the parcel's 4 adjacents."""

    def test_adjacent_matches_project_street(self):
        fake_adj = {
            "north": "Carrer Santa Gemma",
            "south": "parcel·la veïna",
            "east":  "Carrer Santa Marta",
            "west":  "parcel·la veïna",
        }
        with patch(
            "automation.cadastre_adjacents.get_adjacent_parcels",
            return_value=fake_adj,
        ):
            ok = gc._project_street_matches_cadastre(
                project_street_hint="Santa Gemma",
                rc="08307A000000010000XX",
                utm_x=383000.0, utm_y=4569000.0,
                municipality="Vilanova i la Geltrú",
            )
        assert ok is True

    def test_no_adjacent_matches_returns_false(self):
        """Wrong-parcel scenario: project on Santa Gemma, but Cadastre
        returned CARRERADA's adjacents — none of them contain Santa Gemma."""
        fake_adj = {
            "north": "Camí del Fondo",
            "south": "Partida Carrerada",
            "east":  "parcel·la veïna",
            "west":  "parcel·la veïna",
        }
        with patch(
            "automation.cadastre_adjacents.get_adjacent_parcels",
            return_value=fake_adj,
        ):
            ok = gc._project_street_matches_cadastre(
                project_street_hint="Santa Gemma",
                rc="08307A000000010000XX",
                utm_x=383000.0, utm_y=4569000.0,
                municipality="Vilanova i la Geltrú",
            )
        assert ok is False

    def test_adjacents_exception_returns_false(self):
        """If the adjacents call throws, we conservatively return False so
        the Nominatim fallback path kicks in."""
        with patch(
            "automation.cadastre_adjacents.get_adjacent_parcels",
            side_effect=RuntimeError("boom"),
        ):
            ok = gc._project_street_matches_cadastre(
                project_street_hint="Santa Gemma",
                rc="08307A000000010000XX",
                utm_x=383000.0, utm_y=4569000.0,
            )
        assert ok is False

    def test_hint_prefix_stripped_before_match(self):
        """Match logic must strip the street-type word from the hint so
        'Carrer Santa Gemma' still matches an adjacent named 'Carrer Santa Gemma'."""
        fake_adj = {
            "north": "Carrer Santa Gemma",
            "south": "", "east": "", "west": "",
        }
        with patch(
            "automation.cadastre_adjacents.get_adjacent_parcels",
            return_value=fake_adj,
        ):
            ok = gc._project_street_matches_cadastre(
                project_street_hint="Carrer Santa Gemma",
                rc="08307A000000010000XX",
                utm_x=383000.0, utm_y=4569000.0,
            )
        assert ok is True


# ────────────────────────────────────────────────────────────────────────────
# Fix 2 end-to-end: geocode_project reconciliation paths
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def _stub_common(tmp_path, monkeypatch):
    """Bypass caches, ICGC elevations, and polygon fetches for speed."""
    monkeypatch.setattr(gc, "_load_from_cache", lambda a, m: None)
    monkeypatch.setattr(gc, "_save_to_cache", lambda a, m, r: None)
    monkeypatch.setattr(gc, "get_parcel_geometry_utm", lambda rc14: [])

    # Disable ICGC elevation lookup (we test orchestration, not altimetry).
    def _no_icgc(*a, **k):  # pragma: no cover - defensive
        raise ImportError("icgc_geology disabled for test")
    monkeypatch.setattr(
        "automation.geocode_coordinates.cadastre_address_lookup",
        lambda *a, **k: None,  # force the parallel path to be authoritative
    )

    # Make cadastre_find_parcel a no-op (only invoked on pure-Nominatim fallback)
    monkeypatch.setattr(gc, "cadastre_find_parcel", lambda lat, lon, addr: None)

    # Short-circuit the final Nominatim structured/free retry fallback so tests
    # that *don't* mock these directly don't hang.
    monkeypatch.setattr(gc, "nominatim_geocode_structured", lambda *a, **k: None)
    monkeypatch.setattr(gc, "nominatim_geocode", lambda *a, **k: None)

    yield tmp_path


def test_cadastre_adjacents_contain_project_street_trusted(_stub_common, monkeypatch):
    """Cadastre returns a parcel whose adjacents include the project street
    → reconciliation trusts Cadastre; Nominatim is NOT used to override."""
    fake_cadastre = {"rc": "0836603CF8603N0001XK", "xcen": None, "ycen": None}
    fake_nominatim = (41.2237, 1.7245)  # arbitrary WGS84 near Vilanova
    fake_adj = {
        "north": "Carrer Santa Gemma",
        "south": "parcel·la veïna",
        "east":  "parcel·la veïna",
        "west":  "parcel·la veïna",
    }

    monkeypatch.setattr(
        gc, "_run_cadastre_and_nominatim_parallel",
        lambda **kw: (fake_cadastre, fake_nominatim),
    )
    monkeypatch.setattr(gc, "cadastre_rc_to_utm", lambda rc: (383123.0, 4569456.0))
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_adjacent_parcels",
        lambda *a, **kw: fake_adj,
    )

    # The RCCOOR re-query must NOT be called on the happy path
    rccoor_called = {"flag": False}

    def _boom(*a, **kw):
        rccoor_called["flag"] = True
        return (None, None)

    monkeypatch.setattr("automation.cadastre_adjacents.get_cadastral_reference", _boom)

    result = gc.geocode_project(
        "Carrer Santa Gemma, 109",
        "Vilanova i la Geltrú",
        ["P-1"],
        province="Barcelona",
    )

    assert result is not None
    assert result["rc"] == "0836603CF8603N0001XK"
    assert result["utm_x"] == 383123.0
    assert result["utm_y"] == 4569456.0
    assert "reconciled" not in result["source"], (
        "Expected no reconciliation when Cadastre's parcel borders the project street"
    )
    assert rccoor_called["flag"] is False


def test_cadastre_adjacents_missing_project_street_fallback(_stub_common, monkeypatch):
    """Cadastre returned a wrong parcel (adjacents don't mention the project
    street) and Nominatim returned a coord → reconciliation switches to
    Nominatim's UTM and re-queries Cadastre by coord."""
    fake_cadastre = {"rc": "WRONG0000000000000XX", "xcen": None, "ycen": None}
    fake_nominatim = (41.2237, 1.7245)
    wrong_adj = {
        "north": "Partida Carrerada",
        "south": "Camí del Fondo",
        "east":  "parcel·la veïna",
        "west":  "parcel·la veïna",
    }

    monkeypatch.setattr(
        gc, "_run_cadastre_and_nominatim_parallel",
        lambda **kw: (fake_cadastre, fake_nominatim),
    )
    # Stub CartoCiudad to None — this test validates the Nominatim fallback
    # path, where CartoCiudad did not return a usable candidate.
    monkeypatch.setattr(gc, "cartociudad_geocode", lambda *a, **kw: None)
    monkeypatch.setattr(gc, "cadastre_rc_to_utm", lambda rc: (300000.0, 4570000.0))
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_adjacent_parcels",
        lambda *a, **kw: wrong_adj,
    )

    rccoor_called = {"args": None}

    def _rccoor(x, y):
        rccoor_called["args"] = (x, y)
        return ("CORRECT00000000000XX", None)

    monkeypatch.setattr("automation.cadastre_adjacents.get_cadastral_reference", _rccoor)

    result = gc.geocode_project(
        "Carrer Santa Gemma, 109",
        "Vilanova i la Geltrú",
        ["P-1"],
        province="Barcelona",
    )

    assert result is not None, "Expected Nominatim-based result, got None"
    # RC should now be the coord-based one
    assert result["rc"] == "CORRECT00000000000XX"
    # Source should mark reconciliation
    assert "reconciled" in result["source"], result["source"]
    # RCCOOR was invoked with the Nominatim-derived UTM
    assert rccoor_called["args"] is not None


def test_both_cadastre_and_nominatim_fail(_stub_common, monkeypatch):
    """Neither branch returns anything → function returns None gracefully."""
    monkeypatch.setattr(
        gc, "_run_cadastre_and_nominatim_parallel",
        lambda **kw: (None, None),
    )

    result = gc.geocode_project(
        "Carrer Inexistent, 999",
        "Nowheresville",
        ["P-1"],
        province="Barcelona",
    )
    assert result is None


def test_nominatim_and_cadastre_agree_cadastre_wins(_stub_common, monkeypatch):
    """Both succeed AND Cadastre's parcel borders the project street:
    Cadastre's result (which includes the exact RC + adjacents) is used."""
    fake_cadastre = {"rc": "0836603CF8603N0001XK", "xcen": None, "ycen": None}
    fake_nominatim = (41.2237, 1.7245)
    fake_adj = {
        "north": "Carrer Santa Gemma",
        "south": "parcel·la veïna",
        "east":  "parcel·la veïna",
        "west":  "parcel·la veïna",
    }

    monkeypatch.setattr(
        gc, "_run_cadastre_and_nominatim_parallel",
        lambda **kw: (fake_cadastre, fake_nominatim),
    )
    monkeypatch.setattr(gc, "cadastre_rc_to_utm", lambda rc: (383123.0, 4569456.0))
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_adjacent_parcels",
        lambda *a, **kw: fake_adj,
    )

    result = gc.geocode_project(
        "Carrer Santa Gemma, 109",
        "Vilanova i la Geltrú",
        ["P-1"],
        province="Barcelona",
    )

    assert result is not None
    # Cadastre's exact RC is retained — not overridden by a coord-based lookup
    assert result["rc"] == "0836603CF8603N0001XK"
    assert result["source"].startswith("geocode:cadastre")
