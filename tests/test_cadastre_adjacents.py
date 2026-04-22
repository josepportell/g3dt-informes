"""Hermetic tests for automation.cadastre_adjacents RCCOOR + RCCOOR_Distancia flow.

No real network access: urlopen is monkeypatched to return canned XML bodies.
Covers Step 7 #4/#5:
  - RCCOOR returns expected (ref, ldt) on happy path
  - RCCOOR err=16 transparently falls back to RCCOOR_Distancia
  - Other RCCOOR error codes do NOT trigger the fallback
  - Network / parse errors still surface as CadastreConnectionError /
    CadastreParseError, never silently swallowed
  - Nearest-refs picks the closest candidate within max_distance_m
"""

from __future__ import annotations

import io
import socket
import urllib.error
from contextlib import contextmanager
from typing import Any

import pytest

from automation import cadastre_adjacents
from automation.cadastre_adjacents import (
    CADASTRE_ERR_NO_REFERENCE,
    CadastreConnectionError,
    CadastreParseError,
    _query_nearest_refs,
    _query_ref_by_coords,
    _query_ref_by_coords_raw,
    get_cadastral_reference,
)


# --- Canned XML responses ---

RCCOOR_OK_XML = """<?xml version="1.0" encoding="utf-8"?>
<consulta_coordenadas xmlns="http://www.catastro.meh.es/">
  <control><cucoor>1</cucoor><cuerr>0</cuerr></control>
  <coordenadas>
    <coord>
      <pc><pc1>8606709</pc1><pc2>CG9280N</pc2></pc>
      <geo><xcen>298581</xcen><ycen>4620387</ycen><srs>EPSG:25831</srs></geo>
      <ldt>CL SANTA GEMMA 4 VILANOVA DE SEGRIA (LLEIDA)</ldt>
    </coord>
  </coordenadas>
</consulta_coordenadas>"""

RCCOOR_ERR_16_XML = """<?xml version="1.0" encoding="utf-8"?>
<consulta_coordenadas xmlns="http://www.catastro.meh.es/">
  <control><cucoor>0</cucoor><cuerr>1</cuerr></control>
  <coordenadas>
    <coord>
      <geo><xcen>400000</xcen><ycen>4500000</ycen><srs>EPSG:25831</srs></geo>
      <err><cod>16</cod><des>PARA ESAS COORDENADAS NO HAY REFERENCIA DISPONIBLE</des></err>
    </coord>
  </coordenadas>
</consulta_coordenadas>"""

RCCOOR_ERR_3_XML = """<?xml version="1.0" encoding="utf-8"?>
<consulta_coordenadas xmlns="http://www.catastro.meh.es/">
  <control><cucoor>0</cucoor><cuerr>1</cuerr></control>
  <coordenadas>
    <coord>
      <err><cod>3</cod><des>SRS INVALIDO</des></err>
    </coord>
  </coordenadas>
</consulta_coordenadas>"""

# RCCOOR_Distancia: two candidates — one at 4m (accepted), one at 60m (rejected)
DISTANCIA_TWO_CANDIDATES_XML = """<?xml version="1.0" encoding="utf-8"?>
<consulta_coordenadas_distancias xmlns="http://www.catastro.meh.es/">
  <control><cucoor>1</cucoor><cuerr>0</cuerr></control>
  <coordenadas_distancias>
    <coordd>
      <geo><xcen>298583</xcen><ycen>4620386</ycen><srs>EPSG:25831</srs></geo>
      <lpcd>
        <pcd>
          <pc><pc1>1111111</pc1><pc2>AA0000A</pc2></pc>
          <ldt>CL FAR 60 FAKETOWN</ldt>
          <dis>60.50</dis>
        </pcd>
        <pcd>
          <pc><pc1>2222222</pc1><pc2>BB0000B</pc2></pc>
          <ldt>CL NEAR 4 FAKETOWN</ldt>
          <dis>4.00</dis>
        </pcd>
        <pcd>
          <pc><pc1>3333333</pc1><pc2>CC0000C</pc2></pc>
          <ldt>CL MID 12 FAKETOWN</ldt>
          <dis>12.34</dis>
        </pcd>
      </lpcd>
    </coordd>
  </coordenadas_distancias>
</consulta_coordenadas_distancias>"""

# RCCOOR_Distancia: all candidates too far
DISTANCIA_ALL_TOO_FAR_XML = """<?xml version="1.0" encoding="utf-8"?>
<consulta_coordenadas_distancias xmlns="http://www.catastro.meh.es/">
  <control><cucoor>1</cucoor><cuerr>0</cuerr></control>
  <coordenadas_distancias>
    <coordd>
      <geo><xcen>400000</xcen><ycen>4500000</ycen><srs>EPSG:25831</srs></geo>
      <lpcd>
        <pcd>
          <pc><pc1>9999999</pc1><pc2>ZZ0000Z</pc2></pc>
          <ldt>CL FAR 99 FAKETOWN</ldt>
          <dis>9999.00</dis>
        </pcd>
      </lpcd>
    </coordd>
  </coordenadas_distancias>
</consulta_coordenadas_distancias>"""

# RCCOOR_Distancia: empty lpcd list
DISTANCIA_EMPTY_XML = """<?xml version="1.0" encoding="utf-8"?>
<consulta_coordenadas_distancias xmlns="http://www.catastro.meh.es/">
  <control><cucoor>1</cucoor><cuerr>0</cuerr></control>
  <coordenadas_distancias>
    <coordd>
      <geo><xcen>0</xcen><ycen>0</ycen><srs>EPSG:25831</srs></geo>
      <lpcd></lpcd>
    </coordd>
  </coordenadas_distancias>
</consulta_coordenadas_distancias>"""


# --- Mock plumbing ---

class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


@contextmanager
def mock_urlopen(monkeypatch: pytest.MonkeyPatch, router):
    """router: callable(url) -> response body str, or raises an exception."""
    calls: list[str] = []

    def fake_urlopen(req, *args: Any, **kwargs: Any):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        calls.append(url)
        result = router(url)
        if isinstance(result, Exception):
            raise result
        return _FakeResponse(result)

    monkeypatch.setattr(cadastre_adjacents.urllib.request, "urlopen", fake_urlopen)
    # Also short-circuit retry sleeps so the test is fast
    monkeypatch.setattr(cadastre_adjacents.time, "sleep", lambda *_: None)
    yield calls


# --- Tests ---

class TestRccoorJsonHappyPath:
    def test_rccoor_rest_happy_path(self, monkeypatch):
        """Happy path: RCCOOR returns a parcel -> (ref, ldt, None)."""
        def router(url: str) -> str:
            assert "Consulta_RCCOOR?" in url
            assert "Coordenada_X=298581" in url
            assert "Coordenada_Y=4620387" in url
            return RCCOOR_OK_XML

        with mock_urlopen(monkeypatch, router) as calls:
            ref, ldt, err = _query_ref_by_coords_raw(298581, 4620387)

        assert ref == "8606709CG9280N"
        assert ldt == "CL SANTA GEMMA 4 VILANOVA DE SEGRIA (LLEIDA)"
        assert err is None
        assert len(calls) == 1


class TestErrCode16Fallback:
    def test_err_code_16_triggers_nearest_refs(self, monkeypatch):
        """get_cadastral_reference: err 16 -> falls back to RCCOOR_Distancia."""
        def router(url: str) -> str:
            if "Consulta_RCCOOR_Distancia" in url:
                return DISTANCIA_TWO_CANDIDATES_XML
            if "Consulta_RCCOOR" in url:
                return RCCOOR_ERR_16_XML
            raise AssertionError(f"unexpected url: {url}")

        with mock_urlopen(monkeypatch, router) as calls:
            ref, ldt = get_cadastral_reference(400000, 4500000)

        # Should pick the nearest candidate within 50m (4m), not the 60m one
        assert ref == "2222222BB0000B"
        assert ldt == "CL NEAR 4 FAKETOWN"
        # Both endpoints must have been hit exactly once each
        assert any("Consulta_RCCOOR?" in u for u in calls)
        assert any("Consulta_RCCOOR_Distancia" in u for u in calls)
        assert len(calls) == 2

    def test_err_16_but_nearest_all_too_far(self, monkeypatch):
        """err 16 + no candidate within 50m -> (None, None)."""
        def router(url: str) -> str:
            if "Consulta_RCCOOR_Distancia" in url:
                return DISTANCIA_ALL_TOO_FAR_XML
            return RCCOOR_ERR_16_XML

        with mock_urlopen(monkeypatch, router):
            ref, ldt = get_cadastral_reference(400000, 4500000)
        assert ref is None
        assert ldt is None

    def test_err_16_empty_nearest_response(self, monkeypatch):
        """err 16 + empty nearest list -> (None, None)."""
        def router(url: str) -> str:
            if "Consulta_RCCOOR_Distancia" in url:
                return DISTANCIA_EMPTY_XML
            return RCCOOR_ERR_16_XML

        with mock_urlopen(monkeypatch, router):
            ref, ldt = get_cadastral_reference(400000, 4500000)
        assert ref is None
        assert ldt is None


class TestNonErrCode16DoesNotFallback:
    def test_err_code_3_does_not_call_distancia(self, monkeypatch):
        """Non-16 errors must NOT trigger RCCOOR_Distancia."""
        def router(url: str) -> str:
            if "Consulta_RCCOOR_Distancia" in url:
                raise AssertionError(
                    "RCCOOR_Distancia should not be called for non-16 errors"
                )
            return RCCOOR_ERR_3_XML

        with mock_urlopen(monkeypatch, router) as calls:
            ref, ldt = get_cadastral_reference(1.0, 2.0)

        assert ref is None
        assert ldt is None
        # Only the first RCCOOR call; no fallback
        assert len(calls) == 1
        assert "Consulta_RCCOOR_Distancia" not in calls[0]


class TestErrorSurfacing:
    def test_network_error_raises_connection_error(self, monkeypatch):
        """URLError from urlopen must raise CadastreConnectionError."""
        def router(url: str):
            return urllib.error.URLError("host unreachable")

        with mock_urlopen(monkeypatch, router):
            with pytest.raises(CadastreConnectionError):
                get_cadastral_reference(298581, 4620387)

    def test_timeout_raises_connection_error(self, monkeypatch):
        def router(url: str):
            return socket.timeout("timed out")

        with mock_urlopen(monkeypatch, router):
            with pytest.raises(CadastreConnectionError):
                get_cadastral_reference(298581, 4620387)

    def test_parse_error_on_malformed_xml(self, monkeypatch):
        def router(url: str) -> str:
            return "<not-xml"

        with mock_urlopen(monkeypatch, router):
            with pytest.raises(CadastreParseError):
                _query_ref_by_coords_raw(1.0, 2.0)


class TestNearestRefsDirect:
    def test_picks_closest_within_radius(self, monkeypatch):
        """_query_nearest_refs picks the nearest candidate within radius."""
        def router(url: str) -> str:
            assert "Consulta_RCCOOR_Distancia" in url
            return DISTANCIA_TWO_CANDIDATES_XML

        with mock_urlopen(monkeypatch, router):
            ref, ldt = _query_nearest_refs(0, 0, max_distance_m=50.0)
        assert ref == "2222222BB0000B"
        assert ldt == "CL NEAR 4 FAKETOWN"

    def test_empty_response(self, monkeypatch):
        def router(url: str) -> str:
            return DISTANCIA_EMPTY_XML

        with mock_urlopen(monkeypatch, router):
            ref, ldt = _query_nearest_refs(0, 0)
        assert ref is None
        assert ldt is None

    def test_custom_radius_rejects_far_candidates(self, monkeypatch):
        """With radius=10, only the 4m candidate qualifies (12.34m excluded)."""
        def router(url: str) -> str:
            return DISTANCIA_TWO_CANDIDATES_XML

        with mock_urlopen(monkeypatch, router):
            ref, _ = _query_nearest_refs(0, 0, max_distance_m=10.0)
        assert ref == "2222222BB0000B"


class TestPublicSignatures:
    def test_get_cadastral_reference_returns_two_tuple(self, monkeypatch):
        """Callers unpack 2-tuple; the public contract must stay stable."""
        def router(url: str) -> str:
            return RCCOOR_OK_XML

        with mock_urlopen(monkeypatch, router):
            result = get_cadastral_reference(298581, 4620387)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_query_ref_by_coords_shim_returns_two_tuple(self, monkeypatch):
        """Internal _query_ref_by_coords shim must also stay 2-tuple."""
        def router(url: str) -> str:
            return RCCOOR_OK_XML

        with mock_urlopen(monkeypatch, router):
            result = _query_ref_by_coords(298581, 4620387)
        assert len(result) == 2
        assert result[0] == "8606709CG9280N"
