"""Tests for the ICGC API Territorial client (Catalan fast-path).

All tests are hermetic — no real HTTP. The network layer (``urlopen``) is
monkey-patched to controlled fakes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from automation import icgc_territorial as icgc_t
from automation import geocode_coordinates as gc


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _fake_response(body: str, status: int = 200):
    """Context-manager-compatible fake urlopen response."""
    resp = MagicMock()
    resp.read.return_value = body.encode("utf-8")
    resp.status = status
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: None
    return resp


def _sample_feature_collection(
    refcadp: str = "8606709CG9280N0001XZ",
) -> dict:
    """Build a realistic 4-layer FeatureCollection."""
    return {
        "numberReturned": 4,
        "timeStamp": "2026-04-22T00:00:00+02:00",
        "type": "FeatureCollection",
        "code": 200,
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [0.57890, 41.70960],
                        [0.57920, 41.70960],
                        [0.57920, 41.70990],
                        [0.57890, 41.70990],
                        [0.57890, 41.70960],
                    ]],
                },
                "properties": {"refcadp": refcadp},
            },
            {
                "type": "Feature",
                "geometry": {"type": "MultiPolygon", "coordinates": []},
                "properties": {
                    "CODIMUNI": 252516,
                    "NOMMUNI": "Vilanova de Segrià",
                    "CODICOMAR": 33,
                    "NOMCOMAR": "Segrià",
                    "CODIPROV": 25,
                    "NOMPROV": "Lleida",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "MultiPolygon", "coordinates": []},
                "properties": {
                    "ID_REC": "25313:0:0:92:9000:1",
                    "ID_PAR": "25313:0:0:92:9000",
                    "COMARCA": "Segrià",
                    "MUNICIPI": "Vilanova de Segrià",
                    "US": "ZU",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": []},
                "properties": {
                    "C_QUAL_MUC": "R6",
                    "D_QUAL_MUC": "Residencial",
                },
            },
        ],
    }


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Redirect the ICGC Territorial cache dir + disable time.sleep."""
    monkeypatch.setattr(icgc_t, "CACHE_DIR", tmp_path / "icgc_t_cache")
    monkeypatch.setattr(icgc_t.time, "sleep", lambda _s: None)
    # Ensure G3DT_NO_CACHE is not leaking in from the test host.
    monkeypatch.delenv("G3DT_NO_CACHE", raising=False)
    yield


# ────────────────────────────────────────────────────────────────────────────
# Happy path + URL structure
# ────────────────────────────────────────────────────────────────────────────

class TestQueryTerritorialHappyPath:
    def test_query_territorial_happy_path(self):
        body = json.dumps(_sample_feature_collection())
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(body)
            result = icgc_t.query_territorial(41.70978, 0.57897)

        assert result is not None
        assert set(result.keys()) == {
            "cadastre", "municipis", "sigpac", "qualificacions-muc",
        }
        assert len(result["cadastre"]) == 1
        assert result["cadastre"][0]["properties"]["refcadp"] == (
            "8606709CG9280N0001XZ"
        )
        assert len(result["municipis"]) == 1
        assert len(result["sigpac"]) == 1
        assert len(result["qualificacions-muc"]) == 1

    def test_query_territorial_url_uses_lng_lat_order(self):
        """The request must be built with lng first — swapping silently
        yields zero features in production. Guard against regression."""
        body = json.dumps(_sample_feature_collection())
        captured: dict = {}

        def _capture(req, timeout=None):
            captured["url"] = req.full_url
            return _fake_response(body)

        with patch.object(icgc_t.urllib.request, "urlopen", side_effect=_capture):
            icgc_t.query_territorial(41.70978, 0.57897)

        assert "url" in captured
        # URL shape: .../elements/<layers>/<lng>,<lat>
        tail = captured["url"].rsplit("/", 1)[-1]
        lng_str, lat_str = tail.split(",")
        assert float(lng_str) == pytest.approx(0.57897, abs=1e-5)
        assert float(lat_str) == pytest.approx(41.70978, abs=1e-5)


# ────────────────────────────────────────────────────────────────────────────
# Coordinate-order footgun detection
# ────────────────────────────────────────────────────────────────────────────

class TestSwapDetection:
    def test_query_territorial_swapped_coords_warns(self, caplog):
        body = json.dumps(_sample_feature_collection())
        captured: dict = {}

        def _capture(req, timeout=None):
            captured["url"] = req.full_url
            return _fake_response(body)

        caplog.set_level(logging.WARNING, logger="automation.icgc_territorial")
        with patch.object(icgc_t.urllib.request, "urlopen", side_effect=_capture):
            # Caller swapped the args (lat should be ~41.7, lng ~0.57)
            icgc_t.query_territorial(0.57897, 41.70978)

        # Warning emitted
        swap_warnings = [
            r for r in caplog.records if "look swapped" in r.getMessage()
        ]
        assert len(swap_warnings) == 1
        # But the request still went out with whatever the caller provided
        # (no auto-swap).
        tail = captured["url"].rsplit("/", 1)[-1]
        lng_str, lat_str = tail.split(",")
        assert float(lng_str) == pytest.approx(41.70978, abs=1e-5)
        assert float(lat_str) == pytest.approx(0.57897, abs=1e-5)

    def test_query_territorial_non_catalan_coords_no_warning(self, caplog):
        body = json.dumps(_sample_feature_collection())
        caplog.set_level(logging.WARNING, logger="automation.icgc_territorial")
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(body)
            # Madrid coordinates — not Catalan, but also not swapped
            icgc_t.query_territorial(40.4168, -3.7038)

        swap_warnings = [
            r for r in caplog.records if "look swapped" in r.getMessage()
        ]
        assert swap_warnings == []


# ────────────────────────────────────────────────────────────────────────────
# Extract helpers
# ────────────────────────────────────────────────────────────────────────────

class TestExtractRefcadp:
    def test_extract_refcadp_parses_14_char_rc(self):
        body = json.dumps(_sample_feature_collection(refcadp="8606709CG9280N"))
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(body)
            result = icgc_t.query_territorial(41.70978, 0.57897)
        rc = icgc_t.extract_refcadp(result)
        assert rc == "8606709CG9280N"
        assert len(rc) == 14

    def test_extract_refcadp_rejects_wrong_length(self):
        # 20 chars — not the expected 14
        body = json.dumps(
            _sample_feature_collection(refcadp="8606709CG9280N0001XZ")
        )
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(body)
            result = icgc_t.query_territorial(41.70978, 0.57897)
        assert icgc_t.extract_refcadp(result) is None


class TestExtractPolygon:
    def test_extract_parcel_polygon_utm_projects_wgs84_to_25831(self):
        body = json.dumps(_sample_feature_collection())
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(body)
            result = icgc_t.query_territorial(41.70978, 0.57897)
        polygon = icgc_t.extract_parcel_polygon_utm(result)
        assert polygon is not None
        assert len(polygon) >= 3
        for x, y in polygon:
            # UTM 31N x for Catalonia: ~250-550 km (easting); y: ~4.5-4.8 Mm
            assert 200_000 < x < 1_000_000, f"x={x} out of UTM band"
            assert 4_000_000 < y < 5_000_000, f"y={y} out of UTM band"


# ────────────────────────────────────────────────────────────────────────────
# Cache behavior
# ────────────────────────────────────────────────────────────────────────────

class TestCache:
    def test_cache_hit_skips_http(self):
        body = json.dumps(_sample_feature_collection())
        # Warm the cache
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(body)
            first = icgc_t.query_territorial(41.70978, 0.57897)
        assert first is not None

        # Now second call must not touch the network
        def _explode(*a, **kw):
            raise AssertionError("urlopen was called despite cache hit")

        with patch.object(icgc_t.urllib.request, "urlopen", side_effect=_explode):
            second = icgc_t.query_territorial(41.70978, 0.57897)
        assert second is not None
        assert set(second.keys()) == set(first.keys())
        assert second["cadastre"][0]["properties"]["refcadp"] == (
            first["cadastre"][0]["properties"]["refcadp"]
        )

    def test_cache_ignores_stale_entries(self):
        body = json.dumps(_sample_feature_collection())
        # Warm
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(body)
            icgc_t.query_territorial(41.70978, 0.57897)

        # Rewrite the cache file with a very old cached_at
        lat, lng = 41.70978, 0.57897
        layers = tuple(sorted(set(icgc_t.DEFAULT_LAYERS)))
        path = icgc_t._cache_path(lat, lng, layers)
        assert path.exists()
        with open(path, "r", encoding="utf-8") as f:
            wrapper = json.load(f)
        wrapper["cached_at"] = (
            datetime.now() - timedelta(days=icgc_t.CACHE_TTL_DAYS + 1)
        ).isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wrapper, f)

        # Now the call should refetch
        fresh_body = json.dumps(
            _sample_feature_collection(refcadp="DIFFERENT1234X")
        )
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(fresh_body)
            result = icgc_t.query_territorial(lat, lng)
        assert result["cadastre"][0]["properties"]["refcadp"] == "DIFFERENT1234X"

    def test_g3dt_no_cache_env_var_bypasses_cache(self, monkeypatch):
        monkeypatch.setenv("G3DT_NO_CACHE", "1")
        body = json.dumps(_sample_feature_collection())
        # First call: fetch. Must NOT write the cache file.
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(body)
            icgc_t.query_territorial(41.70978, 0.57897)
        # Cache dir should be empty or not exist
        if icgc_t.CACHE_DIR.exists():
            assert not list(icgc_t.CACHE_DIR.glob("*.json"))

        # Second call: must hit the network again (no cache read)
        calls: list = []
        def _mock(req, timeout=None):
            calls.append(req.full_url)
            return _fake_response(body)
        with patch.object(icgc_t.urllib.request, "urlopen", side_effect=_mock):
            icgc_t.query_territorial(41.70978, 0.57897)
        assert len(calls) == 1


# ────────────────────────────────────────────────────────────────────────────
# Error paths
# ────────────────────────────────────────────────────────────────────────────

class TestErrors:
    def test_network_error_surfaces(self):
        import urllib.error
        err = urllib.error.URLError("connection refused")
        with patch.object(icgc_t.urllib.request, "urlopen", side_effect=err):
            with pytest.raises(icgc_t.ICGCTerritorialConnectionError):
                icgc_t.query_territorial(41.70978, 0.57897)

    def test_malformed_json_raises(self):
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response("{not valid json")
            with pytest.raises(icgc_t.ICGCTerritorialParseError):
                icgc_t.query_territorial(41.70978, 0.57897)


# ────────────────────────────────────────────────────────────────────────────
# Integration with geocode_project
# ────────────────────────────────────────────────────────────────────────────

def _patch_stub_geocode_upstream(monkeypatch, tmp_path, cc_rc: str | None):
    """Stub the Cadastre/Nominatim/CartoCiudad parallel fetch so we can
    exercise the ICGC integration in isolation."""
    # Redirect the geocode cache so previous runs don't bleed in.
    monkeypatch.setattr(gc, "CACHE_DIR", tmp_path / "geocode_cache")
    monkeypatch.setattr(gc.time, "sleep", lambda _s: None)

    # Stub the parallel fetch to force reconciliation onto CartoCiudad
    nominatim_coords = (41.70978, 0.57897)
    cc_result = gc.CartoCiudadResult(
        lat=41.70978,
        lng=0.57897,
        rc=cc_rc,
        type="portal",
        portal_number=4,
    )
    # cadastre_result has an RC that won't match the project street, forcing
    # the reconciliation branch.
    cadastre_result = {
        "rc": "0000000XX0000X0000XX",
        "address": "WRONG STREET",
        "xcen": None,
        "ycen": None,
    }

    monkeypatch.setattr(
        gc,
        "_run_cadastre_and_alternates_parallel",
        lambda **kw: (cadastre_result, nominatim_coords, cc_result),
    )
    monkeypatch.setattr(
        gc,
        "cadastre_rc_to_utm",
        lambda rc: (300000.0, 4620000.0),
    )
    monkeypatch.setattr(
        gc,
        "_project_street_matches_cadastre",
        lambda **kw: False,
    )

    # Stub elevation lookups so they don't hit the network.
    import automation.icgc_geology as icgc_geo
    monkeypatch.setattr(icgc_geo, "get_elevation", lambda x, y: 200.0)
    # Ensure centroid passes Spain bounds check (already within).


class TestIntegrationWithGeocodeProject:
    def test_rc_disagreement_logs_warning(self, monkeypatch, caplog, tmp_path):
        """CartoCiudad RC ≠ ICGC refcadp → WARNING logged, pipeline still
        succeeds with CartoCiudad's RC."""
        _patch_stub_geocode_upstream(monkeypatch, tmp_path, cc_rc="AAAA111BB2222C")
        # ICGC returns a DIFFERENT refcadp
        body = json.dumps(
            _sample_feature_collection(refcadp="ZZZZ999YY8888X")
        )
        monkeypatch.setattr(icgc_t, "CACHE_DIR", tmp_path / "icgc_cache")
        with patch.object(icgc_t.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = _fake_response(body)
            caplog.set_level(logging.WARNING)
            result = gc.geocode_project(
                "Santa Gemma 4",
                "Vilanova de Segrià",
                point_ids=["P-1"],
                province="LLEIDA",
            )

        disagreement_logs = [
            r for r in caplog.records
            if "RC disagreement" in r.getMessage()
        ]
        assert len(disagreement_logs) == 1
        assert result is not None
        # CartoCiudad's RC wins (not ICGC's).
        assert result["rc"] == "AAAA111BB2222C"

    def test_icgc_down_falls_back_to_cadastre_wfs(
        self, monkeypatch, tmp_path, caplog
    ):
        """When query_territorial returns None (simulated outage), the
        pipeline falls back to get_parcel_geometry_utm."""
        _patch_stub_geocode_upstream(monkeypatch, tmp_path, cc_rc="AAAA111BB2222C")

        # Make ICGC unavailable: simulate a ICGCTerritorialError bubbling up
        def _boom(*a, **kw):
            raise icgc_t.ICGCTerritorialConnectionError("icgc down")
        monkeypatch.setattr(icgc_t, "query_territorial", _boom)

        fallback_polygon_called: dict = {"v": False}
        def _wfs_stub(rc14):
            fallback_polygon_called["v"] = True
            # Return a triangle within Spain UTM bounds
            return [
                (300000.0, 4620000.0),
                (300100.0, 4620000.0),
                (300050.0, 4620100.0),
            ]
        monkeypatch.setattr(gc, "get_parcel_geometry_utm", _wfs_stub)

        result = gc.geocode_project(
            "Santa Gemma 4",
            "Vilanova de Segrià",
            point_ids=["P-1"],
            province="LLEIDA",
        )
        assert result is not None
        assert fallback_polygon_called["v"], (
            "Cadastre WFS fallback was not invoked"
        )

    def test_non_catalan_project_skips_icgc(self, monkeypatch, tmp_path):
        """province=MADRID must skip the ICGC call entirely."""
        _patch_stub_geocode_upstream(monkeypatch, tmp_path, cc_rc="AAAA111BB2222C")

        calls: list = []
        def _track(*a, **kw):
            calls.append(a)
            return None
        monkeypatch.setattr(icgc_t, "query_territorial", _track)

        monkeypatch.setattr(
            gc, "get_parcel_geometry_utm",
            lambda rc: [
                (300000.0, 4620000.0),
                (300100.0, 4620000.0),
                (300050.0, 4620100.0),
            ],
        )

        gc.geocode_project(
            "Calle Mayor 4",
            "Madrid",
            point_ids=["P-1"],
            province="MADRID",
        )
        assert calls == []
