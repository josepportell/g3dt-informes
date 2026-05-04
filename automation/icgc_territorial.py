#!/usr/bin/env python3
"""
ICGC API Territorial Integration (Catalonia)

Thin client for the ICGC "API Territorial" REST endpoint, which returns
several GeoJSON layers in a single HTTP call for a given point inside
Catalunya. Used by the geocoding pipeline as a fast path that replaces
the separate Cadastre ASMX + WFS-CP round-trips:

    - cadastre            -> parcel polygon + 14-char RC (``refcadp``)
    - municipis           -> municipality / comarca / provincia codes
    - sigpac              -> agricultural parcel codes
    - qualificacions-muc  -> urban zoning (MUC)

Coordinate-order FOOTGUN
------------------------
The URL path encodes coordinates as ``{lng},{lat}`` (longitude first).
Swapping the order does NOT raise an error — the server silently returns
an empty ``FeatureCollection``. This module exposes a caller-friendly
``query_territorial(lat, lng, ...)`` that internally builds the URL in
the correct order to hide the footgun.

We also perform a defensive sanity check: if the inputs look swapped for
Catalan use (``lat`` tiny + ``lng`` inside the latitude band), we emit a
WARNING but do NOT auto-swap — auto-correction would mask real bugs in
the caller.

Geography scope
---------------
The endpoint is Catalonia-only. Non-Catalan coordinates will typically
return empty feature lists. Callers are expected to gate on province.

API docs (inferred from live probing, 2026-04-22):
    https://api.icgc.cat/territorial/elements/{layers}/{lng},{lat}

    - Layers are comma-separated in the path segment.
    - Response is a flat GeoJSON FeatureCollection. Features from
      different layers must be distinguished by their ``properties``
      fingerprint (there is no per-feature layer tag).
    - No API key / authentication required as of this writing.
    - HTTP 200 is returned even when no features match; look at
      ``numberReturned``.

Author: Eficients.cat
Date: 2026-04-22
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

from . import config

logger = logging.getLogger(__name__)

__all__ = [
    "query_territorial",
    "extract_refcadp",
    "extract_parcel_polygon_utm",
    "clear_cache",
    "ICGCTerritorialError",
    "ICGCTerritorialConnectionError",
    "ICGCTerritorialParseError",
]


# === Configuration ===

BASE_URL = "https://api.icgc.cat/territorial/elements"
DEFAULT_LAYERS: tuple[str, ...] = (
    "cadastre",
    "municipis",
    "sigpac",
    "qualificacions-muc",
)

CACHE_DIR = config.cache_dir("icgc_territorial")
CACHE_TTL_DAYS = 90
COORDINATE_ROUND_DECIMALS = 5  # ~1 m precision at Catalan latitudes

REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
USER_AGENT = (
    "G3DT-Automation/1.0 (Eficients.cat; geotechnical report generation)"
)

# Catalan lat/lng envelope (approximate):
#   lat ≈ 40.5 .. 42.9   ;   lng ≈ 0.1 .. 3.4
# If the caller hands us (lat, lng) but lat is outside the band AND lng is
# inside the lat band, the inputs are almost certainly swapped.
_CATALAN_LAT_MIN = 40.0
_CATALAN_LAT_MAX = 43.5
_CATALAN_LNG_MIN = 0.0
_CATALAN_LNG_MAX = 4.0


# === Exceptions ===

class ICGCTerritorialError(Exception):
    """Base exception for ICGC API Territorial errors."""


class ICGCTerritorialConnectionError(ICGCTerritorialError):
    """Connection/network failure talking to the ICGC API."""


class ICGCTerritorialParseError(ICGCTerritorialError):
    """Response body could not be parsed as the expected schema."""


# === Public API ===

def query_territorial(
    lat: float,
    lng: float,
    layers: Sequence[str] | None = None,
    use_cache: bool = True,
) -> dict[str, list[dict[str, Any]]] | None:
    """Query ICGC API Territorial for a point inside Catalunya.

    Args:
        lat: Latitude (WGS84). Caller-friendly order — the module flips
            to ``{lng},{lat}`` internally.
        lng: Longitude (WGS84).
        layers: Sequence of ICGC layer names. Default: all four
            documented layers (cadastre, municipis, sigpac,
            qualificacions-muc).
        use_cache: Read/write the on-disk cache. Honors ``G3DT_NO_CACHE``.

    Returns:
        A dict mapping layer name -> list of GeoJSON feature dicts. Layer
        keys are always present even when their feature list is empty.
        Returns ``None`` on hard HTTP or JSON failure (distinguishable
        from "no data", which returns a dict with empty lists).
    """
    if layers is None:
        layers = DEFAULT_LAYERS
    # Canonicalize layer order so the cache key is stable.
    layers_tuple = tuple(sorted({str(x) for x in layers}))

    _warn_if_coords_look_swapped(lat, lng)

    if use_cache and not _cache_disabled():
        cached = _cache_load(lat, lng, layers_tuple)
        if cached is not None:
            logger.debug(
                "ICGC Territorial cache hit for (%.5f, %.5f) layers=%s",
                lat, lng, layers_tuple,
            )
            return cached

    url = _build_url(lat, lng, layers_tuple)
    try:
        body = _fetch_with_retries(url)
    except ICGCTerritorialConnectionError as exc:
        logger.info("ICGC Territorial request failed: %s", exc)
        raise

    try:
        payload = json.loads(body)
    except ValueError as exc:
        logger.warning(
            "ICGC Territorial returned unparseable JSON (schema drift?): %s", exc
        )
        raise ICGCTerritorialParseError(
            f"Invalid JSON from ICGC Territorial: {exc}"
        ) from exc

    result = _split_features_by_layer(payload, layers_tuple)

    if use_cache and not _cache_disabled():
        _cache_save(lat, lng, layers_tuple, result)

    return result


def extract_refcadp(
    territorial_response: dict[str, list[dict[str, Any]]] | None,
) -> str | None:
    """Return the 14-char cadastral reference from the ``cadastre`` layer.

    Returns the first feature's ``refcadp`` property, or ``None`` if the
    layer is absent/empty or the field isn't exactly 14 characters.
    """
    if not territorial_response:
        return None
    features = territorial_response.get("cadastre") or []
    if not features:
        return None
    props = features[0].get("properties") or {}
    rc = props.get("refcadp")
    if not isinstance(rc, str):
        return None
    rc = rc.strip()
    if len(rc) != 14:
        return None
    return rc


def extract_parcel_polygon_utm(
    territorial_response: dict[str, list[dict[str, Any]]] | None,
) -> list[tuple[float, float]] | None:
    """Extract the cadastre parcel polygon and reproject to EPSG:25831.

    ICGC returns GeoJSON in WGS84 (EPSG:4326). We reuse the geocoder's
    ``_wgs84_to_utm31n`` helper to project to UTM zone 31N, matching the
    convention used elsewhere in the pipeline.

    Handles both ``Polygon`` and ``MultiPolygon`` geometries; for a
    multi-polygon, returns the polygon with the largest vertex count
    (the outermost piece). Returns ``None`` if no usable geometry.
    """
    if not territorial_response:
        return None
    features = territorial_response.get("cadastre") or []
    if not features:
        return None

    geom = features[0].get("geometry") or {}
    geom_type = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None

    # Normalize to a list-of-rings; we take the first ring of the biggest
    # polygon (exterior ring, no holes).
    ring: list[list[float]] | None = None
    if geom_type == "Polygon":
        if isinstance(coords, list) and coords:
            ring = coords[0]
    elif geom_type == "MultiPolygon":
        if isinstance(coords, list) and coords:
            # Pick the polygon with the longest outer ring.
            best = max(coords, key=lambda poly: len(poly[0]) if poly else 0)
            if best:
                ring = best[0]
    else:
        return None

    if not ring or len(ring) < 3:
        return None

    # Lazy import to avoid circular-import risk between the two modules.
    from .geocode_coordinates import _wgs84_to_utm31n

    polygon: list[tuple[float, float]] = []
    for pair in ring:
        try:
            lon = float(pair[0])
            lat = float(pair[1])
        except (TypeError, ValueError, IndexError):
            continue
        x, y = _wgs84_to_utm31n(lat, lon)
        polygon.append((x, y))
    if len(polygon) < 3:
        return None
    return polygon


def clear_cache() -> int:
    """Remove all cached ICGC Territorial responses. Returns count removed."""
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for path in CACHE_DIR.glob("*.json"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


# === Internal helpers ===

def _build_url(lat: float, lng: float, layers: Sequence[str]) -> str:
    """Build the ICGC Territorial URL in the required ``{lng},{lat}`` order."""
    layer_seg = ",".join(layers)
    # The API requires lng,lat — NOT lat,lng. Wrong order silently returns
    # zero features. Encode with enough precision to hit the right parcel.
    return f"{BASE_URL}/{layer_seg}/{lng:.8f},{lat:.8f}"


def _warn_if_coords_look_swapped(lat: float, lng: float) -> None:
    """Emit a WARNING if (lat, lng) look like they were swapped.

    Heuristic: caller might have passed (lng, lat) by mistake. For
    Catalan use lat ≈ 40.5..42.9 and lng ≈ 0.1..3.4. If lat is below
    the latitude band AND lng is inside the latitude band, they're very
    likely swapped.

    We do NOT auto-swap — auto-correction would mask caller bugs and
    could corrupt data for the (rare) legitimate cases near lat=0.
    """
    suspicious = (
        lat < _CATALAN_LAT_MIN
        and _CATALAN_LAT_MIN <= lng <= _CATALAN_LAT_MAX
    )
    if suspicious:
        logger.warning(
            "ICGC Territorial: (lat=%.5f, lng=%.5f) look swapped for "
            "Catalan use; proceeding as given (no auto-swap).",
            lat, lng,
        )


def _split_features_by_layer(
    payload: Any,
    layers: Sequence[str],
) -> dict[str, list[dict[str, Any]]]:
    """Group the FeatureCollection's features by ICGC layer.

    ICGC returns a single flat list of features without a per-feature
    layer tag. We infer the layer from the properties fingerprint —
    each layer has a distinctive set of property keys.
    """
    result: dict[str, list[dict[str, Any]]] = {name: [] for name in layers}

    if not isinstance(payload, dict):
        raise ICGCTerritorialParseError("ICGC payload is not a JSON object")
    features = payload.get("features")
    if features is None:
        # Valid FeatureCollection may have empty list, but missing key is wrong.
        if payload.get("type") != "FeatureCollection":
            raise ICGCTerritorialParseError(
                "ICGC payload missing 'features' and not a FeatureCollection"
            )
        return result
    if not isinstance(features, list):
        raise ICGCTerritorialParseError("ICGC 'features' is not a list")

    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        layer_name = _guess_layer_for_properties(props)
        if layer_name is None:
            continue
        if layer_name in result:
            result[layer_name].append(feat)
    return result


def _guess_layer_for_properties(props: dict[str, Any]) -> str | None:
    """Infer the ICGC layer name from a feature's properties keys.

    The four documented layers each expose a distinctive property:
        cadastre           -> 'refcadp'
        municipis          -> 'CODIMUNI'
        sigpac             -> 'ID_REC' (or 'ID_PAR' with 'COMARCA')
        qualificacions-muc -> 'C_QUAL_MUC'
    """
    keys = set(props.keys())
    if "refcadp" in keys:
        return "cadastre"
    if "C_QUAL_MUC" in keys:
        return "qualificacions-muc"
    if "ID_REC" in keys or ("ID_PAR" in keys and "COMARCA" in keys):
        return "sigpac"
    if "CODIMUNI" in keys:
        return "municipis"
    return None


def _fetch_with_retries(url: str) -> str:
    """Fetch URL with exponential backoff on transient network errors.

    HTTP errors (4xx/5xx) bubble up immediately as
    ``ICGCTerritorialConnectionError`` — we do not retry them because
    ICGC typically returns 200 even for "no features", so a 4xx means
    the request itself is malformed.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT_SECONDS
            ) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ICGCTerritorialConnectionError(
                f"ICGC Territorial HTTP {exc.code}: {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            last_error = exc
        except (TimeoutError, socket.timeout) as exc:
            last_error = exc

        if attempt < MAX_RETRIES - 1:
            delay = 2 ** attempt
            logger.debug(
                "ICGC Territorial retry %d/%d after %ss: %s",
                attempt + 1, MAX_RETRIES, delay, last_error,
            )
            time.sleep(delay)

    raise ICGCTerritorialConnectionError(
        f"Failed to reach ICGC Territorial after {MAX_RETRIES} attempts: "
        f"{last_error}"
    )


# === Cache ===

def _cache_disabled() -> bool:
    """Return True when ``G3DT_NO_CACHE`` is truthy in the environment."""
    return os.environ.get("G3DT_NO_CACHE", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _cache_key(lat: float, lng: float, layers: Sequence[str]) -> str:
    lat_r = round(lat, COORDINATE_ROUND_DECIMALS)
    lng_r = round(lng, COORDINATE_ROUND_DECIMALS)
    raw = f"{lat_r:.{COORDINATE_ROUND_DECIMALS}f}_{lng_r:.{COORDINATE_ROUND_DECIMALS}f}_{','.join(layers)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _cache_path(lat: float, lng: float, layers: Sequence[str]) -> Path:
    return CACHE_DIR / f"{_cache_key(lat, lng, layers)}.json"


def _cache_load(
    lat: float,
    lng: float,
    layers: Sequence[str],
) -> dict[str, list[dict[str, Any]]] | None:
    path = _cache_path(lat, lng, layers)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            wrapper = json.load(f)
    except (OSError, ValueError) as exc:
        logger.debug("ICGC Territorial cache unreadable %s: %s", path, exc)
        return None

    cached_at_raw = wrapper.get("cached_at")
    if not isinstance(cached_at_raw, str):
        return None
    try:
        cached_at = datetime.fromisoformat(cached_at_raw)
    except ValueError:
        return None
    if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
        logger.debug("ICGC Territorial cache expired: %s", path)
        return None

    data = wrapper.get("data")
    if not isinstance(data, dict):
        return None
    # Re-shape: ensure all requested layers are keys (even if empty list).
    out: dict[str, list[dict[str, Any]]] = {name: [] for name in layers}
    for k, v in data.items():
        if isinstance(v, list) and k in out:
            out[k] = v
    return out


def _cache_save(
    lat: float,
    lng: float,
    layers: Sequence[str],
    data: dict[str, list[dict[str, Any]]],
) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create ICGC Territorial cache dir: %s", exc)
        return

    path = _cache_path(lat, lng, layers)
    wrapper = {
        "cached_at": datetime.now().isoformat(),
        "lat": lat,
        "lng": lng,
        "layers": list(layers),
        "data": data,
    }
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(CACHE_DIR),
            delete=False,
            suffix=".tmp",
        )
        with tmp as f:
            json.dump(wrapper, f, ensure_ascii=False)
        os.replace(tmp.name, path)
    except OSError as exc:
        logger.warning("Failed to cache ICGC Territorial response: %s", exc)
        # Best-effort cleanup
        if tmp is not None:
            try:
                Path(tmp.name).unlink(missing_ok=True)
            except OSError:
                pass
