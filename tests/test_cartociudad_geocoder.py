"""Tests for CartoCiudad (IGN Spain) geocoder integration.

CartoCiudad is the new secondary geocoder, preferred over Nominatim in the
Cadastre reconciliation flow because it delivers portal-level (entrance)
coordinates for Catalan small towns where Nominatim has sparse coverage.

All tests are hermetic — no real HTTP calls.
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from automation import geocode_coordinates as gc
from automation.geocode_coordinates import CartoCiudadResult


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
        a CartoCiudadResult with the correct coords + RC."""
        body = json.dumps([{
            "address": "Santa Gemma 4",
            "muni": "Vilanova de Segrià",
            "province": "Lleida",
            "type": "portal",
            "lat": 41.70978,
            "lng": 0.57897,
            "portalNumber": 4,
            "refCatastral": "8606709CG9280N",
        }])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode(
                "Santa Gemma 4", "Vilanova de Segrià", "Lleida"
            )
        assert isinstance(result, CartoCiudadResult)
        assert (result.lat, result.lng) == (41.70978, 0.57897)
        assert result.rc == "8606709CG9280N"
        assert result.type == "portal"
        assert result.portal_number == 4

    def test_portal_preferred_over_callejero(self):
        """When both types present, portal wins."""
        body = json.dumps([
            {"type": "callejero", "lat": 41.70000, "lng": 0.57000, "muni": "Vilanova"},
            {"type": "portal",    "lat": 41.70978, "lng": 0.57897, "muni": "Vilanova"},
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("Santa Gemma 4", "Vilanova")
        assert result is not None
        assert (result.lat, result.lng) == (41.70978, 0.57897)

    def test_zero_coords_rejected_only_portal_wins(self):
        """Callejero with (0,0) coords is skipped; real portal picked."""
        body = json.dumps([
            {"type": "callejero", "lat": 0, "lng": 0, "muni": "Vilanova"},
            {"type": "portal",    "lat": 41.70978, "lng": 0.57897, "muni": "Vilanova"},
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("X", "Vilanova")
        assert result is not None
        assert (result.lat, result.lng) == (41.70978, 0.57897)

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
        assert result is not None
        assert (result.lat, result.lng) == (41.70978, 0.57897)

    def test_plain_json_response(self):
        """Raw JSON list (no JSONP wrapper) is parsed correctly."""
        body = json.dumps([
            {"type": "portal", "lat": 41.70978, "lng": 0.57897, "muni": "V"},
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("X", "V")
        assert result is not None
        assert (result.lat, result.lng) == (41.70978, 0.57897)

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
        assert r1 is not None and r2 is not None
        assert (r1.lat, r1.lng) == (41.70978, 0.57897)
        assert (r2.lat, r2.lng) == (41.70978, 0.57897)
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

    def test_vilanova_muni_match_via_muni_field_not_address(self):
        """Bug #1 regression: when CartoCiudad's `address` field contains a
        parenthetical urbanization prefix (e.g. 'La Serra (Vilanova de Segrià)')
        but the `muni` field holds the canonical municipality, the match must
        succeed and the coordinates must be returned."""
        body = json.dumps([{
            "type": "portal",
            "muni": "Vilanova de Segrià",
            "address": "CALLE SANTA GEMMA 4, La Serra (Vilanova de Segrià)",
            "portalNumber": 4,
            "lat": 41.70978,
            "lng": 0.57897,
        }])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode(
                "Santa Gemma 4", "Vilanova de Segrià", "Lleida"
            )
        assert result is not None
        assert (result.lat, result.lng) == (41.70978, 0.57897)

    def test_province_retry_when_first_attempt_empty(self):
        """Bug #1 root cause: adding the province as a third query segment
        makes CartoCiudad return zero candidates for some small-town addresses.
        The function must retry without the province and succeed."""
        payload_with_number = json.dumps([{
            "type": "portal",
            "muni": "Vilanova de Segrià",
            "address": "CALLE SANTA GEMMA 4, La Serra (Vilanova de Segrià)",
            "portalNumber": 4,
            "lat": 41.70978,
            "lng": 0.57897,
        }])
        calls = {"n": 0, "queries": []}

        def _fake(req, timeout=None):  # noqa: ARG001
            calls["n"] += 1
            calls["queries"].append(req.full_url)
            # First call (with province) returns empty; second (without) succeeds.
            body = "[]" if calls["n"] == 1 else payload_with_number
            return _fake_http_response(body)

        with patch.object(gc.urllib.request, "urlopen", side_effect=_fake):
            result = gc.cartociudad_geocode(
                "Santa Gemma 4", "Vilanova de Segrià", "Lleida"
            )
        assert result is not None
        assert (result.lat, result.lng) == (41.70978, 0.57897)
        assert calls["n"] == 2, f"Expected 2 HTTP calls (retry), got {calls['n']}"
        assert "Lleida" in calls["queries"][0]
        assert "Lleida" not in calls["queries"][1]

    def test_candidate_selection_prefers_matching_portal_number(self):
        """Bug #2 regression: given multiple portal candidates for the same
        street, pick the one whose `portalNumber` matches the house number
        parsed from the input address."""
        body = json.dumps([
            {
                "type": "portal", "muni": "Linyola",
                "address": "CALLE CLOT DE LLACUNA 17, Linyola",
                "portalNumber": 17,
                "lat": 41.70925, "lng": 0.89592,
            },
            {
                "type": "portal", "muni": "Linyola",
                "address": "CALLE CLOT DE LLACUNA 16, Linyola",
                "portalNumber": 16,
                "lat": 41.70860, "lng": 0.89561,
            },
            {
                "type": "portal", "muni": "Linyola",
                "address": "CALLE CLOT DE LLACUNA 18, Linyola",
                "portalNumber": 18,
                "lat": 41.70873, "lng": 0.89565,
            },
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode(
                "Clot de la Llacuna 16", "Linyola", "Lleida"
            )
        # Must pick #16 even though #17 is listed first.
        assert result is not None
        assert (result.lat, result.lng) == (41.70860, 0.89561)

    def test_candidate_selection_no_house_number_in_query_falls_back_to_first(self):
        """Existing behaviour preserved: when the input has no house number,
        we fall back to the first portal candidate."""
        body = json.dumps([
            {
                "type": "portal", "muni": "Linyola",
                "address": "CALLE MESTRE RAMON 17, Linyola",
                "portalNumber": 17,
                "lat": 41.70001, "lng": 0.90001,
            },
            {
                "type": "portal", "muni": "Linyola",
                "address": "CALLE MESTRE RAMON 16, Linyola",
                "portalNumber": 16,
                "lat": 41.70002, "lng": 0.90002,
            },
        ])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode(
                "Mestre Ramon Ortiz", "Linyola", "Lleida"
            )
        # No number in input → first portal wins.
        assert result is not None
        assert (result.lat, result.lng) == (41.70001, 0.90001)


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
    Nominatim succeeded; reconciliation picks CartoCiudad (higher precision).
    When CartoCiudad has no RC (callejero), we still re-query Cadastre by coord."""
    fake_cadastre = {"rc": "WRONG0000000000000XX", "xcen": None, "ycen": None}
    # CartoCiudad portal coord → this is the Vilanova fix case.
    # Simulate a candidate with no refCatastral (e.g. callejero match) so the
    # reconciliation path still exercises the RCCOOR re-query fallback.
    fake_cc = CartoCiudadResult(
        lat=41.70978, lng=0.57897, rc=None, type="callejero", portal_number=None,
    )
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
    nx, ny, _ = gc._wgs84_to_utm(fake_cc.lat, fake_cc.lng)
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
    fake_cc = CartoCiudadResult(
        lat=41.70978, lng=0.57897, rc=None, type="portal", portal_number=4,
    )
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


# ────────────────────────────────────────────────────────────────────────────
# Step 7 — refCatastral capture + query filters
# ────────────────────────────────────────────────────────────────────────────

class TestRefCatastralCapture:
    def _patch_urlopen(self, body: str):
        return patch.object(
            gc.urllib.request,
            "urlopen",
            return_value=_fake_http_response(body),
        )

    def test_refcatastral_flows_through(self):
        """Portal candidate exposes `refCatastral` → result.rc captures it."""
        body = json.dumps([{
            "type": "portal",
            "muni": "Vilanova de Segrià",
            "address": "CALLE SANTA GEMMA 4",
            "portalNumber": 4,
            "lat": 41.70978,
            "lng": 0.57897,
            "refCatastral": "8606709CG9280N",
        }])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode(
                "Santa Gemma 4", "Vilanova de Segrià", "Lleida"
            )
        assert result is not None
        assert result.rc == "8606709CG9280N"

    def test_refcatastral_absent_leaves_rc_none(self):
        """Candidate without `refCatastral` → result.rc is None."""
        body = json.dumps([{
            "type": "portal",
            "muni": "Vilanova",
            "lat": 41.70978,
            "lng": 0.57897,
        }])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("Santa Gemma 4", "Vilanova")
        assert result is not None
        assert result.rc is None

    def test_refcatastral_empty_string_coerced_to_none(self):
        """Empty/whitespace refCatastral must be normalized to None."""
        body = json.dumps([{
            "type": "portal",
            "muni": "V",
            "lat": 41.7,
            "lng": 0.5,
            "refCatastral": "   ",
        }])
        with self._patch_urlopen(body):
            result = gc.cartociudad_geocode("X 1", "V")
        assert result is not None
        assert result.rc is None


class TestQueryFilters:
    def test_fetch_candidates_url_contains_filters(self):
        """The fetch helper must add `no_process` and `limit` to the URL,
        and MUST NOT send `municipio_filter` (accent-sensitive server-side —
        see _cartociudad_fetch_candidates docstring). Regression guard."""
        captured = {"url": None}

        def _fake(req, timeout=None):  # noqa: ARG001
            captured["url"] = req.full_url
            return _fake_http_response("[]")

        with patch.object(gc.urllib.request, "urlopen", side_effect=_fake):
            gc._cartociudad_fetch_candidates(
                "Santa Gemma 4, Vilanova de Segrià",
                limit=5,
            )

        url = captured["url"]
        assert url is not None
        # q=... must be present
        assert "q=" in url
        # municipio_filter must NOT be present (regression guard)
        assert "municipio_filter=" not in url
        assert "no_process=" in url
        # Core no_process types (urlencoded commas are %2C)
        assert "toponimo" in url
        assert "municipio" in url
        assert "limit=5" in url

    def test_fetch_candidates_no_municipality_omits_filter(self):
        """`municipio_filter` must NOT appear in the URL regardless of caller."""
        captured = {"url": None}

        def _fake(req, timeout=None):  # noqa: ARG001
            captured["url"] = req.full_url
            return _fake_http_response("[]")

        with patch.object(gc.urllib.request, "urlopen", side_effect=_fake):
            gc._cartociudad_fetch_candidates("Santa Gemma 4")

        url = captured["url"]
        assert url is not None
        assert "municipio_filter=" not in url
        # no_process and limit still present
        assert "no_process=" in url
        assert "limit=" in url

    def test_geocode_passes_municipality_filter_on_both_queries(self):
        """Both the province-included and province-stripped retries must
        OMIT `municipio_filter` (accent-sensitive footgun). Regression guard."""
        calls: list[str] = []

        def _fake(req, timeout=None):  # noqa: ARG001
            calls.append(req.full_url)
            return _fake_http_response("[]")

        with patch.object(gc.urllib.request, "urlopen", side_effect=_fake):
            gc.cartociudad_geocode(
                "Santa Gemma 4", "Vilanova de Segrià", "Lleida"
            )
        assert len(calls) == 2
        for url in calls:
            assert "municipio_filter=" not in url, url

    def test_cartociudad_unaccented_muni_still_finds_candidate(self):
        """Unaccented caller muni ("Vilanova de Segria") must still resolve
        when CartoCiudad returns candidates tagged with the accented form
        ("Vilanova de Segrià"). Protects against re-adding server-side
        `municipio_filter` (which is accent-strict)."""
        # Mock candidates as they'd come back from CartoCiudad with accented muni.
        candidates = [
            {
                "id": "OTHER1",
                "type": "portal",
                "muni": "Alfarràs",
                "portalNumber": 4,
                "lat": 41.8,
                "lng": 0.6,
                "refCatastral": "WRONG_RC_1",
            },
            {
                "id": "CORRECT",
                "type": "portal",
                "muni": "Vilanova de Segrià",
                "portalNumber": 4,
                "lat": 41.72,
                "lng": 0.55,
                "refCatastral": "CORRECT_RC_14",
            },
            {
                "id": "OTHER2",
                "type": "portal",
                "muni": "Vilanova de Segrià",
                "portalNumber": 6,
                "lat": 41.72,
                "lng": 0.55,
                "refCatastral": "WRONG_RC_2",
            },
            {
                "id": "OTHER3",
                "type": "callejero",
                "muni": "Torrefarrera",
                "lat": 41.7,
                "lng": 0.5,
                "refCatastral": "",
            },
        ]

        with patch.object(
            gc,
            "_cartociudad_fetch_candidates",
            return_value=candidates,
        ):
            # Caller passes unaccented muni — exactly what the G3DT pipeline
            # does when it derives muni from a folder name without diacritics.
            result = gc.cartociudad_geocode(
                "Santa Gemma 4", "Vilanova de Segria"
            )

        assert result is not None
        assert result.rc == "CORRECT_RC_14"
        assert result.portal_number == 4


# ────────────────────────────────────────────────────────────────────────────
# Cache backwards-compat
# ────────────────────────────────────────────────────────────────────────────

class TestCacheBackwardsCompat:
    def test_old_format_cache_loads_cleanly(self, tmp_path, monkeypatch):
        """An existing cache file written by the pre-Step-7 code (no `rc`
        field) must still load successfully, with rc=None."""
        # The autouse fixture already points CARTOCIUDAD_CACHE_DIR at tmp.
        cache_dir: Path = gc.CARTOCIUDAD_CACHE_DIR
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = gc._cartociudad_cache_key("Old Addr 1", "OldTown", "")
        path = cache_dir / f"{key}.json"
        legacy_payload = {
            "cached_at": datetime.now().isoformat(),
            "query": {
                "address": "Old Addr 1",
                "municipality": "OldTown",
                "province": "",
            },
            # Legacy schema: only lat + lng, no rc/type/portal_number
            "result": {"lat": 41.0, "lng": 0.5},
        }
        path.write_text(json.dumps(legacy_payload), encoding="utf-8")

        loaded = gc._cartociudad_cache_load("Old Addr 1", "OldTown", "")
        assert isinstance(loaded, CartoCiudadResult)
        assert (loaded.lat, loaded.lng) == (41.0, 0.5)
        assert loaded.rc is None
        assert loaded.portal_number is None


# ────────────────────────────────────────────────────────────────────────────
# Reconciliation uses CartoCiudad RC directly (skips RCCOOR)
# ────────────────────────────────────────────────────────────────────────────

def test_reconciliation_uses_cartociudad_rc_directly(_stub_common, monkeypatch):
    """When CartoCiudad returns a 14-char `refCatastral`, reconciliation
    must adopt that RC directly and NOT call RCCOOR."""
    fake_cadastre = {"rc": "WRONG0000000000000XX", "xcen": None, "ycen": None}
    fake_cc = CartoCiudadResult(
        lat=41.70978, lng=0.57897, rc="8606709CG9280N",
        type="portal", portal_number=4,
    )
    wrong_adj = {
        "north": "Partida Carrerada", "south": "Camí del Fondo",
        "east": "parcel·la veïna",   "west":  "parcel·la veïna",
    }

    monkeypatch.setattr(
        gc, "_run_cadastre_and_alternates_parallel",
        lambda **kw: (fake_cadastre, None, fake_cc),
    )
    monkeypatch.setattr(gc, "cadastre_rc_to_utm", lambda rc: (300000.0, 4570000.0))
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_adjacent_parcels",
        lambda *a, **kw: wrong_adj,
    )

    rccoor_called = {"flag": False}

    def _rccoor(x, y):
        rccoor_called["flag"] = True
        return ("FALLBACKRC0000000000", None)

    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_cadastral_reference", _rccoor
    )

    result = gc.geocode_project(
        "Santa Gemma, 4", "Vilanova de Segrià", ["P-1"], province="Lleida",
    )
    assert result is not None
    # Must adopt CartoCiudad's RC directly (not the RCCOOR fallback value)
    assert result["rc"] == "8606709CG9280N"
    assert "cartociudad" in result["source"]
    assert "reconciled" in result["source"]
    # RCCOOR must NOT have been called
    assert rccoor_called["flag"] is False


def test_reconciliation_rccoor_still_used_when_cartociudad_has_no_rc(
    _stub_common, monkeypatch,
):
    """If CartoCiudad returned a candidate but without `refCatastral`
    (e.g. callejero match), reconciliation must fall back to RCCOOR."""
    fake_cadastre = {"rc": "WRONG0000000000000XX", "xcen": None, "ycen": None}
    fake_cc = CartoCiudadResult(
        lat=41.70978, lng=0.57897, rc=None,
        type="callejero", portal_number=None,
    )
    wrong_adj = {
        "north": "Partida Carrerada", "south": "Camí del Fondo",
        "east": "parcel·la veïna",   "west":  "parcel·la veïna",
    }

    monkeypatch.setattr(
        gc, "_run_cadastre_and_alternates_parallel",
        lambda **kw: (fake_cadastre, None, fake_cc),
    )
    monkeypatch.setattr(gc, "cadastre_rc_to_utm", lambda rc: (300000.0, 4570000.0))
    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_adjacent_parcels",
        lambda *a, **kw: wrong_adj,
    )

    rccoor_called = {"flag": False}

    def _rccoor(x, y):
        rccoor_called["flag"] = True
        return ("RCCOORRC0000000000XX", None)

    monkeypatch.setattr(
        "automation.cadastre_adjacents.get_cadastral_reference", _rccoor
    )

    result = gc.geocode_project(
        "Some Addr, 1", "Town", ["P-1"], province="Prov",
    )
    assert result is not None
    assert rccoor_called["flag"] is True
    assert result["rc"] == "RCCOORRC0000000000XX"


# ────────────────────────────────────────────────────────────────────────────
# Address-suffix preprocessing (Urb./Edifici/Bloc/etc.)
# ────────────────────────────────────────────────────────────────────────────

class TestStripAddressSuffixTokens:
    def test_strip_suffix_removes_urb(self):
        assert gc._strip_address_suffix_tokens(
            "C. Santa Gemma, 4 Urb. La Serra"
        ) == "C. Santa Gemma, 4"

    def test_strip_suffix_case_insensitive(self):
        expected = "C. Santa Gemma, 4"
        assert gc._strip_address_suffix_tokens("C. Santa Gemma, 4 URB. LA SERRA") == expected
        assert gc._strip_address_suffix_tokens("C. Santa Gemma, 4 Urb. La Serra") == expected
        assert gc._strip_address_suffix_tokens("C. Santa Gemma, 4 urb. la serra") == expected

    def test_strip_suffix_handles_comma_prefix(self):
        assert gc._strip_address_suffix_tokens("10, Urb. X") == "10"

    def test_strip_suffix_idempotent(self):
        once = gc._strip_address_suffix_tokens("C. Santa Gemma, 4 Urb. La Serra")
        twice = gc._strip_address_suffix_tokens(once)
        assert once == twice == "C. Santa Gemma, 4"

    def test_strip_suffix_edifici_bloc_pis(self):
        assert gc._strip_address_suffix_tokens(
            "Carrer Major 10 Edifici Roure, Pis 2"
        ) == "Carrer Major 10"
        assert gc._strip_address_suffix_tokens(
            "Av Catalunya 5 Bloc B"
        ) == "Av Catalunya 5"
        assert gc._strip_address_suffix_tokens(
            "Carrer Llarg 7 Piso 3"
        ) == "Carrer Llarg 7"

    def test_strip_suffix_preserves_clean_address(self):
        assert gc._strip_address_suffix_tokens("Carrer Major 10") == "Carrer Major 10"


class TestCartociudadSuffixPreprocessing:
    def _portal_payload(self, number: int = 4) -> str:
        return json.dumps([{
            "type": "portal",
            "muni": "Vilanova de Segrià",
            "address": "CALLE SANTA GEMMA 4, La Serra (Vilanova de Segrià)",
            "portalNumber": number,
            "lat": 41.70978,
            "lng": 0.57897,
            "refCatastral": "8606709CG9280N",
        }])

    def test_cartociudad_uses_stripped_retry_when_first_fails(self):
        """Unstripped query returns zero candidates; stripped retry hits."""
        payload = self._portal_payload()
        calls = {"n": 0, "queries": []}

        def _fake(req, timeout=None):  # noqa: ARG001
            calls["n"] += 1
            calls["queries"].append(req.full_url)
            # Any query containing 'Urb' returns empty; stripped ones hit.
            body = "[]" if "Urb" in req.full_url else payload
            return _fake_http_response(body)

        with patch.object(gc.urllib.request, "urlopen", side_effect=_fake):
            result = gc.cartociudad_geocode(
                "C. Santa Gemma, 4 Urb. La Serra",
                "Vilanova de Segrià",
                "Lleida",
            )
        assert result is not None
        assert result.rc == "8606709CG9280N"
        assert calls["n"] >= 2, f"Expected retry after strip, got {calls['n']} calls"
        # Last successful query must be the stripped form.
        last_url = calls["queries"][-1]
        assert "Urb" not in last_url
        assert "Santa+Gemma" in last_url or "Santa%20Gemma" in last_url

    def test_cartociudad_skips_duplicate_queries_when_nothing_stripped(self):
        """Already-clean address should not re-issue identical queries."""
        body = self._portal_payload()
        calls = {"n": 0, "queries": []}

        def _fake(req, timeout=None):  # noqa: ARG001
            calls["n"] += 1
            calls["queries"].append(req.full_url)
            return _fake_http_response(body)

        with patch.object(gc.urllib.request, "urlopen", side_effect=_fake):
            result = gc.cartociudad_geocode(
                "Santa Gemma 4", "Vilanova de Segrià", "Lleida"
            )
        assert result is not None
        # First query (with province) hits → no retry needed.
        assert calls["n"] == 1
        # No duplicate URLs issued across the full ladder even under failure:
        assert len(calls["queries"]) == len(set(calls["queries"]))

    def test_cartociudad_vilanova_urb_suffix_integration(self):
        """End-to-end: Vilanova input with Urb. suffix → portal + RC returned."""
        payload = self._portal_payload(number=4)

        def _fake(req, timeout=None):  # noqa: ARG001
            # CartoCiudad chokes on the suffix; only stripped queries succeed.
            body = "[]" if "Urb" in req.full_url else payload
            return _fake_http_response(body)

        with patch.object(gc.urllib.request, "urlopen", side_effect=_fake):
            result = gc.cartociudad_geocode(
                "C. Santa Gemma, 4 Urb. La Serra",
                "Vilanova de Segrià",
                "Lleida",
            )
        assert result is not None
        assert (result.lat, result.lng) == (41.70978, 0.57897)
        assert result.rc == "8606709CG9280N"
        assert result.portal_number == 4
