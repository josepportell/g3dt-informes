"""Tests for CartoCiudad (IGN Spain) geocoder integration.

CartoCiudad is the new secondary geocoder, preferred over Nominatim in the
Cadastre reconciliation flow because it delivers portal-level (entrance)
coordinates for Catalan small towns where Nominatim has sparse coverage.

All tests are hermetic — no real HTTP calls.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch, MagicMock

import pytest

from automation import geocode_coordinates as gc


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _fake_http_response(body: str, status: int = 200):
    """Build a context-manager-compatible fake response matching urlopen's API."""
    resp = MagicMock()
    resp.read.return_value = body.encode("utf-8")
    resp.status = status
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: None
    return resp


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Redirect CartoCiudad cache to a tmp dir + disable Nominatim rate-limit sleeps."""
    monkeypatch.setattr(gc, "CARTOCIUDAD_CACHE_DIR", tmp_path / "cc_cache")
    # Disable all time.sleep inside the module (nominatim rate-limiter etc.)
    monkeypatch.setattr(gc.time, "sleep", lambda _s: None)
    yield


# ────────────────────────────────────────────────────────────────────────────
# Helper-unit tests
# ────────────────────────────────────────────────────────────────────────────

class TestMunicipalityMatcher:
    def test_exact_match(self):
        assert gc._cartociudad_muni_matches("Vilanova de Segrià", "Vilanova de Segrià")

    def test_accent_insensitive(self):
        # Candidate has accent, query doesn't
        assert gc._cartociudad_muni_matches("Vilanova de Segrià", "Vilanova de Segria")
        assert gc._cartociudad_muni_matches("Vilanova de Segria", "Vilanova de Segrià")

    def test_case_insensitive(self):
        assert gc._cartociudad_muni_matches("VILANOVA DE SEGRIA", "vilanova de segria")

    def test_parenthetical_suffix_ok(self):
        """'Benasque (Benás)' should match 'Benasque'."""
        assert gc._cartociudad_muni_matches("Benasque (Benás)", "Benasque")

    def test_mismatch(self):
        assert not gc._cartociudad_muni_matches("Barcelona", "Vilanova de Segrià")

    def test_empty(self):
        assert not gc._cartociudad_muni_matches("", "Vilanova")
        assert not gc._cartociudad_muni_matches("Vilanova", "")


class TestParseBody:
    def test_jsonp_wrapper_stripped(self):
        body = 'callback([{"address":"X","lat":41.0,"lng":0.5,"muni":"V","type":"portal"}]);'
        out = gc._parse_cartociudad_body(body)
        assert isinstance(out, list) and len(out) == 1
        assert out[0]["type"] == "portal"

    def test_plain_json_list(self):
        body = '[{"lat":41.0,"lng":0.5,"muni":"V","type":"portal"}]'
        out = gc._parse_cartociudad_body(body)
        assert isinstance(out, list) and len(out) == 1

    def test_empty_list(self):
        assert gc._parse_cartociudad_body("[]") == []

    def test_dict_with_results_key(self):
        body = '{"results":[{"lat":1,"lng":2,"muni":"V","type":"portal"}]}'
        out = gc._parse_cartociudad_body(body)
        assert isinstance(out, list) and len(out) == 1

    def test_malformed_returns_none(self):
        out = gc._parse_cartociudad_body("not-json{")
        assert out is None

    def test_empty_string(self):
        assert gc._parse_cartociudad_body("") is None


# ────────────────────────────────────────────────────────────────────────────
# cartociudad_geocode — main function
# ────────────────────────────────────────────────────────────────────────────

class TestCartociudadGeocode:
    def _patch_urlopen(self, body: str):
        """Context helper: patch urllib.request.urlopen used by the module."""
        return patch.object(
            gc.urllib.request,
            "urlopen",
            return_value=_fake_http_response(body),
        )

    def test_portal_candidate_returned(self):
        """Mock CartoCiudad returning a portal candidate → function returns
        the correct (lat, lng)."""
        body = json.dumps([{
            "address": "Santa Gemma 4",
            "muni": "Vilanova de Segrià",
            "province": "Lleida",
            "type": "portal",
            "lat": 41.70978,
            "lng": 0.57897,
            "portalNumber": 4,
        }])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode(
                "Santa Gemma 4", "Vilanova de Segrià", "Lleida"
            )
        assert result == (41.70978, 0.57897)

    def test_portal_preferred_over_callejero(self):
        """When both types present, portal wins."""
        body = json.dumps([
            {"type": "callejero", "lat": 41.70000, "lng": 0.57000, "muni": "Vilanova"},
            {"type": "portal",    "lat": 41.70978, "lng": 0.57897, "muni": "Vilanova"},
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("Santa Gemma 4", "Vilanova")
        assert result == (41.70978, 0.57897)

    def test_zero_coords_rejected_only_portal_wins(self):
        """Callejero with (0,0) coords is skipped; real portal picked."""
        body = json.dumps([
            {"type": "callejero", "lat": 0, "lng": 0, "muni": "Vilanova"},
            {"type": "portal",    "lat": 41.70978, "lng": 0.57897, "muni": "Vilanova"},
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("X", "Vilanova")
        assert result == (41.70978, 0.57897)

    def test_all_zero_coords_returns_none(self):
        """If every candidate has (0,0) → None."""
        body = json.dumps([
            {"type": "callejero", "lat": 0, "lng": 0, "muni": "Vilanova"},
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("X", "Vilanova")
        assert result is None

    def test_wrong_muni_filtered(self):
        """Candidates from different muni than queried → None."""
        body = json.dumps([
            {"type": "portal", "lat": 40.4, "lng": -3.7, "muni": "Madrid"},
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("Alguna", "Vilanova de Segrià")
        assert result is None

    def test_callback_wrapper_stripped(self):
        """JSONP-wrapped body is parsed correctly."""
        payload = [{"type": "portal", "lat": 41.70978, "lng": 0.57897, "muni": "V"}]
        body = f"callback({json.dumps(payload)});"
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("X", "V")
        assert result == (41.70978, 0.57897)

    def test_plain_json_response(self):
        """Raw JSON list (no JSONP wrapper) is parsed correctly."""
        body = json.dumps([
            {"type": "portal", "lat": 41.70978, "lng": 0.57897, "muni": "V"},
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("X", "V")
        assert result == (41.70978, 0.57897)

    def test_empty_candidates_returns_none(self):
        with self._patch_urlopen("[]"):
            result = gc.cartociudad_geocode("X", "Y")
        assert result is None

    def test_http_error_returns_none(self):
        """HTTPError (e.g. 500) → returns None, logs warning."""
        import urllib.error as ue
        err = ue.HTTPError(
            url="http://cc", code=500, msg="boom",
            hdrs=None, fp=io.BytesIO(b""),  # type: ignore[arg-type]
        )
        with patch.object(gc.urllib.request, "urlopen", side_effect=err):
            result = gc.cartociudad_geocode("X", "Y")
        assert result is None

    def test_connection_refused_returns_none(self):
        import urllib.error as ue
        with patch.object(
            gc.urllib.request, "urlopen",
            side_effect=ue.URLError("connection refused"),
        ):
            result = gc.cartociudad_geocode("X", "Y")
        assert result is None

    def test_cache_hit_suppresses_http(self):
        """Second call with same args doesn't invoke urlopen."""
        body = json.dumps([{
            "type": "portal", "lat": 41.70978, "lng": 0.57897, "muni": "V",
        }])
        mock_urlopen = MagicMock(return_value=_fake_http_response(body))
        with patch.object(gc.urllib.request, "urlopen", mock_urlopen):
            r1 = gc.cartociudad_geocode("Santa Gemma 4", "V", "Lleida")
            r2 = gc.cartociudad_geocode("Santa Gemma 4", "V", "Lleida")
        assert r1 == r2 == (41.70978, 0.57897)
        assert mock_urlopen.call_count == 1, (
            f"Expected 1 HTTP call (cache hit on 2nd), got {mock_urlopen.call_count}"
        )

    def test_negative_cache_hit(self):
        """After a miss is cached, a second call also skips HTTP."""
        mock_urlopen = MagicMock(return_value=_fake_http_response("[]"))
        with patch.object(gc.urllib.request, "urlopen", mock_urlopen):
            assert gc.cartociudad_geocode("Nada", "Nada") is None
            assert gc.cartociudad_geocode("Nada", "Nada") is None
        assert mock_urlopen.call_count == 1


# ────────────────────────────────────────────────────────────────────────────
# Reconciliation integration — CartoCiudad wins over Nominatim
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def _stub_common(tmp_path, monkeypatch):
    """Bypass caches, ICGC elevations, and polygon fetches for speed."""
    monkeypatch.setattr(gc, "_load_from_cache", lambda a, m: None)
    monkeypatch.setattr(gc, "_save_to_cache", lambda a, m, r: None)
    monkeypatch.setattr(gc, "get_parcel_geometry_utm", lambda rc14: [])
    monkeypatch.setattr(
        "automation.geocode_coordinates.cadastre_address_lookup",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(gc, "cadastre_find_parcel", lambda lat, lon, addr: None)
    monkeypatch.setattr(gc, "nominatim_geocode_structured", lambda *a, **k: None)
    monkeypatch.setattr(gc, "nominatim_geocode", lambda *a, **k: None)
    yield tmp_path


def test_vilanova_cartociudad_wins_over_nominatim(_stub_common, monkeypatch):
    """End-to-end: Cadastre picks a wrong parcel; both CartoCiudad and
    Nominatim succeeded; reconciliation picks CartoCiudad (higher precision)
    and re-queries Cadastre by coord."""
    fake_cadastre = {"rc": "WRONG0000000000000XX", "xcen": None, "ycen": None}
    # CartoCiudad portal coord → this is the Vilanova fix case
    fake_cc = (41.70978, 0.57897)
    fake_nom = (41.71500, 0.58500)  # different, less-precise coord
    wrong_adj = {
        "north": "Partida Carrerada",
        "south": "Camí del Fondo",
        "east":  "parcel·la veïna",
        "west":  "parcel·la veïna",
    }

    monkeypatch.setattr(
        gc, "_run_cadastre_and_alternates_parallel",
        lambda **kw: (fake_cadastre, fake_nom, fake_cc),
    )
    monkeypatch.setattr(gc, "cadastre_rc_to_utm", lambda rc: (300000.0, 4570000.0))
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_adjacent_parcels",
        lambda *a, **kw: wrong_adj,
    )

    rccoor_called = {"args": None}

    def _rccoor(x, y):
        rccoor_called["args"] = (x, y)
        return ("8606709CG9280N0001XX", None)

    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_cadastral_reference", _rccoor
    )

    result = gc.geocode_project(
        "Santa Gemma, 4",
        "Vilanova de Segrià",
        ["P-1"],
        province="Lleida",
    )

    assert result is not None
    assert result["rc"] == "8606709CG9280N0001XX"
    # Source must indicate CartoCiudad specifically
    assert "cartociudad" in result["source"], result["source"]
    assert "reconciled" in result["source"], result["source"]
    # RCCOOR was invoked with the CartoCiudad-derived UTM (not Nominatim)
    nx, ny, _ = gc._wgs84_to_utm(*fake_cc)
    assert rccoor_called["args"] is not None
    rx, ry = rccoor_called["args"]
    assert abs(rx - nx) < 1.0 and abs(ry - ny) < 1.0, (
        f"Expected RCCOOR re-query to use CartoCiudad UTM ~({nx:.0f}, {ny:.0f}), "
        f"got ({rx:.0f}, {ry:.0f})"
    )


def test_nominatim_used_when_cartociudad_missing(_stub_common, monkeypatch):
    """If CartoCiudad returns nothing but Nominatim does, Nominatim is still
    used as the fallback (scope requirement — Nominatim stays as tertiary)."""
    fake_cadastre = {"rc": "WRONG0000000000000XX", "xcen": None, "ycen": None}
    fake_nom = (41.2237, 1.7245)
    wrong_adj = {"north": "Partida Carrerada", "south": "Camí del Fondo",
                 "east": "parcel·la veïna", "west": "parcel·la veïna"}

    monkeypatch.setattr(
        gc, "_run_cadastre_and_alternates_parallel",
        lambda **kw: (fake_cadastre, fake_nom, None),
    )
    monkeypatch.setattr(gc, "cadastre_rc_to_utm", lambda rc: (300000.0, 4570000.0))
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_adjacent_parcels",
        lambda *a, **kw: wrong_adj,
    )
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_cadastral_reference",
        lambda x, y: ("FALLBACKRC0000000XX", None),
    )

    result = gc.geocode_project(
        "Carrer X, 1", "Vilanova i la Geltrú", ["P-1"], province="Barcelona",
    )
    assert result is not None
    assert "nominatim" in result["source"], result["source"]
    assert "reconciled" in result["source"], result["source"]


def test_cadastre_street_match_skips_alternates(_stub_common, monkeypatch):
    """When Cadastre's adjacents include the project street, neither
    CartoCiudad nor Nominatim is used to override."""
    fake_cadastre = {"rc": "0836603CF8603N0001XK", "xcen": None, "ycen": None}
    fake_cc = (41.70978, 0.57897)
    fake_nom = (41.2237, 1.7245)
    good_adj = {
        "north": "Carrer Santa Gemma",
        "south": "parcel·la veïna",
        "east":  "parcel·la veïna",
        "west":  "parcel·la veïna",
    }

    monkeypatch.setattr(
        gc, "_run_cadastre_and_alternates_parallel",
        lambda **kw: (fake_cadastre, fake_nom, fake_cc),
    )
    monkeypatch.setattr(gc, "cadastre_rc_to_utm", lambda rc: (383123.0, 4569456.0))
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_adjacent_parcels",
        lambda *a, **kw: good_adj,
    )

    rccoor_called = {"flag": False}

    def _boom(*a, **kw):
        rccoor_called["flag"] = True
        return (None, None)
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_cadastral_reference", _boom
    )

    result = gc.geocode_project(
        "Carrer Santa Gemma, 109", "Vilanova i la Geltrú", ["P-1"],
        province="Barcelona",
    )
    assert result is not None
    assert result["rc"] == "0836603CF8603N0001XK"
    assert result["utm_x"] == 383123.0
    assert result["utm_y"] == 4569456.0
    assert "reconciled" not in result["source"]
    assert rccoor_called["flag"] is False
