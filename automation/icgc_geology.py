#!/usr/bin/env python3
"""
ICGC Geology Integration Module

Queries the Institut Cartogràfic i Geològic de Catalunya (ICGC) WMS service
to retrieve authoritative geological unit information for a given location.

The ICGC provides official geological mapping for Catalunya at various scales.
This module queries the 1:50,000 geological units layer (higher resolution) with
automatic fallback to the 1:250,000 layer when the 50k layer has no data.

API Documentation:
    https://www.icgc.cat/ca/Administracio-i-empresa/Serveis/Geoserveis-en-linia-Inspire

Usage:
    from icgc_geology import get_geological_unit, GeologicalUnit

    # Query by UTM coordinates (ETRS89 zone 31N / EPSG:25831)
    unit = get_geological_unit(307500.0, 4615500.0)
    print(unit.code)        # e.g., "Q3D"
    print(unit.description) # e.g., "Graves, sorres i llims..."
    print(unit.epoch)       # e.g., "Holocè"

Author: Eficients.cat
Date: 2026-02-04
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import socket
import tempfile
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import time
import unicodedata

logger = logging.getLogger(__name__)

__all__ = [
    'GeologicalUnit',
    'get_geological_unit',
    'determine_region',
    'clear_cache',
    'ICGCError',
    'ICGCConnectionError',
    'ICGCParseError',
    'ICGCNoDataError',
    'ICGCCoordinateError',
    'ICGCElevationError',
    'get_elevation',
    'format_cota_referencia',
    'get_slope',
    'get_orthophoto_image',
    'get_orthophoto_with_parcel',
    'get_geological_map_image',
]


# === Configuration ===

ICGC_WMS_URL = "https://geoserveis.icgc.cat/servei/catalunya/geologia-territorial/wms"
ICGC_LAYER_50K = "unitats-geologiques-50000"
ICGC_LAYER_250K = "unitats-geologiques-250000"
ICGC_LAYER = ICGC_LAYER_50K  # Default: higher resolution
ICGC_CRS = "EPSG:25831"  # ETRS89 / UTM zone 31N
ICGC_INFO_FORMAT = "text/plain"

# Cache settings
CACHE_DIR = Path.home() / ".g3dt" / "cache" / "icgc_units"
CACHE_TTL_DAYS = 30
CACHE_TTL_FALLBACK_DAYS = 3  # Shorter TTL for 250k fallback results
COORDINATE_PRECISION = 100  # Round to nearest 100m for cache key

# Request settings
REQUEST_TIMEOUT_SECONDS = 10
BBOX_BUFFER_M = 1000  # Buffer around point for WMS query
USER_AGENT = "G3DT-Automation/1.0 (Eficients.cat; geotechnical report generation)"

# Catalunya UTM coordinate bounds (EPSG:25831)
CATALUNYA_UTM_X_MIN = 260000
CATALUNYA_UTM_X_MAX = 530000
CATALUNYA_UTM_Y_MIN = 4480000
CATALUNYA_UTM_Y_MAX = 4750000


@dataclass
class GeologicalUnit:
    """
    Geological unit information from ICGC.

    Attributes:
        code: ICGC unit code (e.g., "Q3D", "OMca")
        description: Full description in Catalan
        era: Geological era (e.g., "Cenozoic", "Mesozoic")
        period: Geological period (e.g., "Quaternari", "Neogen")
        epoch: Geological epoch (e.g., "Holocè", "Pliocè")
        raw_response: Original response text for debugging
    """
    code: str
    description: str
    era: str
    period: str
    epoch: str
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeologicalUnit:
        """Create from dictionary."""
        return cls(**data)

    def format_for_report(self) -> str:
        """
        Format geological unit info for report paragraph.

        Returns paragraph text like:
        "En concret, i segons l'ICGC, afloren els materials de la unitat Q3D,
        corresponents a graves, sorres i llims (terrasses fluvials baixes...)
        del Holocè."
        """
        desc_lower = self.description.lower() if self.description else ""

        return (
            f"En concret, i segons l'Institut Cartogràfic i Geològic de Catalunya (ICGC), "
            f"afloren els materials de la unitat {self.code}, corresponents a "
            f"{desc_lower} del {self.epoch}."
        )


class ICGCError(Exception):
    """Base exception for ICGC-related errors."""
    pass


class ICGCConnectionError(ICGCError):
    """Failed to connect to ICGC service."""
    pass


class ICGCParseError(ICGCError):
    """Failed to parse ICGC response."""
    pass


class ICGCNoDataError(ICGCError):
    """No geological data found for the given location."""
    pass


class ICGCCoordinateError(ICGCError):
    """Coordinates are outside Catalunya bounds."""
    pass


class ICGCElevationError(ICGCError):
    """Failed to get elevation from ICGC MDT."""
    pass


def _validate_coordinates(utm_x: float, utm_y: float) -> None:
    """
    Validate that coordinates are within Catalunya bounds.

    Raises:
        ICGCCoordinateError: If coordinates are outside Catalunya
    """
    if not (CATALUNYA_UTM_X_MIN <= utm_x <= CATALUNYA_UTM_X_MAX):
        raise ICGCCoordinateError(
            f"UTM X coordinate {utm_x} outside Catalunya bounds "
            f"({CATALUNYA_UTM_X_MIN}-{CATALUNYA_UTM_X_MAX})"
        )
    if not (CATALUNYA_UTM_Y_MIN <= utm_y <= CATALUNYA_UTM_Y_MAX):
        raise ICGCCoordinateError(
            f"UTM Y coordinate {utm_y} outside Catalunya bounds "
            f"({CATALUNYA_UTM_Y_MIN}-{CATALUNYA_UTM_Y_MAX})"
        )


def _fetch_wms(url: str) -> str:
    """
    Fetch WMS response with retry logic for transient connection errors.

    Args:
        url: Full WMS GetFeatureInfo URL

    Returns:
        Response text (UTF-8 decoded)

    Raises:
        ICGCConnectionError: If all retry attempts fail
    """
    max_attempts = 3
    last_error: ICGCConnectionError | None = None

    for attempt in range(max_attempts):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read().decode('utf-8')
        except urllib.error.URLError as e:
            last_error = ICGCConnectionError(f"Failed to connect to ICGC: {e}")
        except (TimeoutError, socket.timeout) as e:
            last_error = ICGCConnectionError(f"ICGC request timed out: {e}")

        # Retry with exponential backoff (1s, 2s, 4s)
        if attempt < max_attempts - 1:
            delay = 2 ** attempt
            logger.debug(f"ICGC request attempt {attempt + 1} failed, retrying in {delay}s...")
            time.sleep(delay)

    # All attempts failed
    raise last_error  # type: ignore[misc]


def get_geological_unit(
    utm_x: float,
    utm_y: float,
    use_cache: bool = True,
) -> GeologicalUnit:
    """
    Query ICGC WMS for geological unit at given UTM coordinates.

    Tries the 1:50,000 layer first (higher resolution), then falls back
    to the 1:250,000 layer if no data is found at 50k.

    Args:
        utm_x: UTM X coordinate (ETRS89 zone 31N / EPSG:25831)
        utm_y: UTM Y coordinate (ETRS89 zone 31N / EPSG:25831)
        use_cache: Whether to use cached responses (default True)

    Returns:
        GeologicalUnit with code, description, era, period, epoch

    Raises:
        ICGCCoordinateError: If coordinates are outside Catalunya bounds
        ICGCConnectionError: If connection to ICGC fails
        ICGCParseError: If response cannot be parsed
        ICGCNoDataError: If no geological data found at either scale
    """
    # Validate coordinates
    _validate_coordinates(utm_x, utm_y)

    # Check cache first
    if use_cache:
        cached = _load_from_cache(utm_x, utm_y)
        if cached:
            logger.debug(f"Cache hit for ({utm_x}, {utm_y})")
            return cached

    # Try 50k first, then fallback to 250k
    layers_to_try = [ICGC_LAYER_50K, ICGC_LAYER_250K]

    for layer in layers_to_try:
        url = _build_wms_url(utm_x, utm_y, layer=layer)
        logger.debug(f"Querying ICGC layer {layer}: {url}")

        response_text = _fetch_wms(url)

        try:
            unit = _parse_response(response_text, layer=layer)
            if use_cache:
                _save_to_cache(utm_x, utm_y, unit, source_layer=layer)
            return unit
        except ICGCNoDataError:
            if layer == ICGC_LAYER_50K:
                logger.info(
                    "1:50k layer returned no data for (%.1f, %.1f), falling back to 1:250k",
                    utm_x, utm_y,
                )
                continue
            raise

    raise ICGCNoDataError("No geological data found at 50k or 250k scale")


def _build_wms_url(utm_x: float, utm_y: float, layer: str | None = None) -> str:
    """
    Build WMS GetFeatureInfo URL for given coordinates.

    Uses a small bounding box centered on the point and queries
    the center pixel of the resulting image.
    """
    if layer is None:
        layer = ICGC_LAYER

    # Create bbox around point
    min_x = utm_x - BBOX_BUFFER_M
    min_y = utm_y - BBOX_BUFFER_M
    max_x = utm_x + BBOX_BUFFER_M
    max_y = utm_y + BBOX_BUFFER_M

    # Image size and query point (center pixel)
    width = 200
    height = 200
    i = width // 2
    j = height // 2

    params = [
        f"SERVICE=WMS",
        f"VERSION=1.3.0",
        f"REQUEST=GetFeatureInfo",
        f"LAYERS={layer}",
        f"QUERY_LAYERS={layer}",
        f"CRS={ICGC_CRS}",
        f"BBOX={min_x},{min_y},{max_x},{max_y}",
        f"WIDTH={width}",
        f"HEIGHT={height}",
        f"I={i}",
        f"J={j}",
        f"INFO_FORMAT={ICGC_INFO_FORMAT}",
    ]

    return f"{ICGC_WMS_URL}?{'&'.join(params)}"


def _parse_response(response_text: str, layer: str | None = None) -> GeologicalUnit:
    """
    Parse ICGC GetFeatureInfo plain text response.

    The ICGC WMS returns a single line with headers and data separated by space:
        @unitats-geologiques-50000 OBJECTID;Codi;...;Descripcio_protolit; 231;Q3D;...;Null;

    Format: @layer_name HEADERS... DATA_VALUES...
    - Headers end with "; " (semicolon followed by space before numeric ID)
    - Data values follow in same semicolon-delimited format
    """
    if not response_text or not response_text.strip():
        raise ICGCNoDataError("Empty response from ICGC")

    # Check for "no features" or empty result
    text_lower = response_text.lower()
    if "no features" in text_lower or "0 features" in text_lower:
        raise ICGCNoDataError("No geological features found at this location")

    # The format is: @layer_name HEADER1;HEADER2;...; VALUE1;VALUE2;...;
    # Split by "; " followed by digit to separate headers from data
    # The pattern is: headers end with "; " then first value is a number (OBJECTID)

    # Find the layer prefix end
    response = response_text.strip()
    if not response.startswith('@'):
        raise ICGCParseError("Unexpected response format (missing @ prefix)")

    # Remove layer prefix (@unitats-geologiques-50000 or @unitats-geologiques-250000)
    space_idx = response.find(' ')
    if space_idx < 0:
        raise ICGCParseError("Unexpected response format (no space after layer name)")

    content = response[space_idx + 1:]

    # Split all fields by semicolon
    all_fields = [f.strip() for f in content.split(';')]

    # Find where headers end and data begins
    # Headers are text, data starts with OBJECTID (a number)
    header_count = 0
    for i, field in enumerate(all_fields):
        if field and field[0].isdigit():
            header_count = i
            break

    if header_count == 0:
        raise ICGCNoDataError("No geological data returned for this location")

    headers = all_fields[:header_count]
    values = all_fields[header_count:]

    # Build dict mapping header -> value
    data_dict: dict[str, str] = {}
    for i, header in enumerate(headers):
        if header and i < len(values):
            data_dict[header.lower()] = values[i]

    layer_info = f" (layer: {layer})" if layer else ""
    logger.debug(f"Parsed ICGC data{layer_info}: {data_dict}")

    # Extract required fields
    code = data_dict.get('codi', '')
    description = data_dict.get('descripcio', '')
    era = data_dict.get('era', '')
    period = data_dict.get('periode', '')
    epoch = data_dict.get('epoca', '')

    # Handle "Null" values from ICGC
    if not epoch or epoch.lower() == 'null':
        epoch = data_dict.get('edat', '')  # Try 'Edat' as fallback
        if not epoch or epoch.lower() == 'null':
            epoch = period  # Use period as fallback

    # Validate we got at least the code
    if not code:
        logger.warning(f"Could not parse ICGC response: {response_text[:300]}")
        raise ICGCParseError("Could not extract geological unit code from response")

    return GeologicalUnit(
        code=code,
        description=description,
        era=era,
        period=period,
        epoch=epoch,
        raw_response=response_text,
    )


# === Caching Functions ===

def _get_cache_key(utm_x: float, utm_y: float) -> str:
    """
    Generate cache key from coordinates.

    Rounds coordinates to COORDINATE_PRECISION to increase cache hits
    for nearby locations.
    """
    x_rounded = round(utm_x / COORDINATE_PRECISION) * COORDINATE_PRECISION
    y_rounded = round(utm_y / COORDINATE_PRECISION) * COORDINATE_PRECISION
    key_str = f"{x_rounded}_{y_rounded}"
    return hashlib.sha256(key_str.encode()).hexdigest()[:12]


def _get_cache_path(utm_x: float, utm_y: float) -> Path:
    """Get path to cache file for given coordinates."""
    cache_key = _get_cache_key(utm_x, utm_y)
    return CACHE_DIR / f"{cache_key}.json"


def _load_from_cache(utm_x: float, utm_y: float) -> GeologicalUnit | None:
    """
    Load geological unit from cache if available and not expired.

    Uses a shorter TTL for 250k fallback results so that when the 50k layer
    becomes available again, we re-query and get the higher-resolution data.

    Returns None if not cached or expired.
    """
    cache_path = _get_cache_path(utm_x, utm_y)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check expiration (shorter TTL for 250k fallback results)
        cached_at = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
        source_layer = data.get('source_layer', ICGC_LAYER_50K)
        ttl = CACHE_TTL_FALLBACK_DAYS if source_layer == ICGC_LAYER_250K else CACHE_TTL_DAYS
        if datetime.now() - cached_at > timedelta(days=ttl):
            logger.debug(f"Cache expired for ({utm_x}, {utm_y}), source_layer={source_layer}, ttl={ttl}d")
            cache_path.unlink()  # Delete expired cache
            return None

        return GeologicalUnit.from_dict(data['unit'])

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Invalid cache file {cache_path}: {e}")
        cache_path.unlink()  # Delete corrupted cache
        return None


def _save_to_cache(utm_x: float, utm_y: float, unit: GeologicalUnit, source_layer: str = ICGC_LAYER_50K) -> None:
    """Save geological unit to cache using atomic write."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _get_cache_path(utm_x, utm_y)

    data = {
        'cached_at': datetime.now().isoformat(),
        'coordinates': {'utm_x': utm_x, 'utm_y': utm_y},
        'unit': unit.to_dict(),
        'source_layer': source_layer,
    }

    try:
        # Atomic write: write to temp file then rename
        fd, temp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Path(temp_path).rename(cache_path)
            logger.debug(f"Cached ICGC response at {cache_path}")
        except Exception:
            # Clean up temp file on failure
            Path(temp_path).unlink(missing_ok=True)
            raise
    except OSError as e:
        logger.warning(f"Failed to cache ICGC response: {e}")


def clear_cache() -> int:
    """
    Clear all cached ICGC responses.

    Returns:
        Number of cache files deleted
    """
    if not CACHE_DIR.exists():
        return 0

    count = 0
    for cache_file in CACHE_DIR.glob("*.json"):
        cache_file.unlink()
        count += 1

    return count


# === Regional Template Support ===

# Mapping of ICGC unit codes/areas to regional template names
REGION_MAPPING = {
    # Depressió de l'Ebre covers most of western Catalunya plain
    'depressio_ebre': {
        'municipalities': [
            'Balaguer', 'Bell-lloc d\'Urgell', 'Bellpuig', 'Mollerussa',
            'Tàrrega', 'Lleida', 'Alcarràs', 'Agramunt', 'Cervera',
            'Les Borges Blanques', 'Almacelles', 'Alpicat', 'Artesa de Segre',
            'Linyola', 'Golmés', 'El Palau d\'Anglesola', 'Fondarella',
        ],
        # Quaternary alluvial codes typically found in the plain
        'unit_codes': ['Q3D', 'Q1D', 'Qt', 'Qa', 'Qvpu'],
    },
    # Vallès-Penedès graben (prelitoral depression)
    'valles_penedes': {
        'municipalities': [
            'Rubí', 'Castellar del Vallès', 'Terrassa', 'Sabadell',
            'Sant Cugat del Vallès', 'Cerdanyola del Vallès', 'Barberà del Vallès',
            'Vilafranca del Penedès', 'Martorell', 'Sant Sadurní d\'Anoia',
            'Olesa de Montserrat', 'Esparreguera', 'Abrera', 'Sant Andreu de la Barca',
            'Molins de Rei', 'Sant Feliu de Llobregat', 'Pallejà',
        ],
        # Quaternary codes typical of Vallès-Penedès
        'unit_codes': ['Q2A', 'Q2F', 'Q2C', 'Q1A', 'NMmc', 'NMcg'],
    },
    # Add more regions as needed
    # 'serralada_litoral': {...},
}


def _strip_accents(s: str) -> str:
    """Remove accents/diacritics for fuzzy comparison (e.g., 'Vallès' → 'Valles')."""
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()


def determine_region(
    unit: GeologicalUnit,
    municipality: str | None = None
) -> str:
    """
    Determine the geological region based on unit and municipality.

    Args:
        unit: GeologicalUnit from ICGC
        municipality: Municipality name (optional but helps accuracy)

    Returns:
        Region template name (e.g., 'depressio_ebre')
    """
    # First try municipality match (most accurate)
    if municipality:
        municipality_norm = _strip_accents(municipality).lower()
        for region, criteria in REGION_MAPPING.items():
            for muni in criteria.get('municipalities', []):
                muni_norm = _strip_accents(muni).lower()
                if muni_norm in municipality_norm or municipality_norm in muni_norm:
                    return region

    # If no unit (e.g. missing UTM coords), default after municipality check
    if unit is None:
        return 'depressio_ebre'

    # Then try unit code match
    for region, criteria in REGION_MAPPING.items():
        if unit.code in criteria.get('unit_codes', []):
            return region

    # Finally try period match
    for region, criteria in REGION_MAPPING.items():
        if unit.period in criteria.get('periods', []):
            return region

    # Default to most common region in project area
    return 'depressio_ebre'


# === MDT Elevation Support ===

ICGC_MDT_WMS_URL = "https://geoserveis.icgc.cat/icgc_mdt2m/wms/service"
ICGC_MDT_LAYER = "MET2m"
MDT_CACHE_DIR = Path.home() / ".g3dt" / "cache" / "icgc_elevation"


def get_elevation(
    utm_x: float,
    utm_y: float,
    use_cache: bool = True,
) -> float:
    """
    Query ICGC MDT 2m for elevation at given UTM coordinates.

    Uses WMS GetFeatureInfo on the MET2m layer (2m resolution LiDAR-derived MDT).

    Args:
        utm_x: UTM X coordinate (ETRS89 zone 31N / EPSG:25831)
        utm_y: UTM Y coordinate (ETRS89 zone 31N / EPSG:25831)
        use_cache: Whether to use cached responses (default True)

    Returns:
        Elevation in meters above sea level

    Raises:
        ICGCCoordinateError: If coordinates are outside Catalunya bounds
        ICGCConnectionError: If connection to ICGC fails
        ICGCElevationError: If elevation cannot be parsed from response
    """
    _validate_coordinates(utm_x, utm_y)

    # Check cache
    if use_cache:
        cached = _load_elevation_from_cache(utm_x, utm_y)
        if cached is not None:
            logger.debug(f"Elevation cache hit for ({utm_x}, {utm_y}): {cached}m")
            return cached

    # Build WMS GetFeatureInfo URL for MDT
    delta = 1.0  # 1m buffer around point
    url = (
        f"{ICGC_MDT_WMS_URL}"
        f"?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo"
        f"&LAYERS={ICGC_MDT_LAYER}&QUERY_LAYERS={ICGC_MDT_LAYER}"
        f"&CRS={ICGC_CRS}"
        f"&BBOX={utm_x - delta},{utm_y - delta},{utm_x + delta},{utm_y + delta}"
        f"&WIDTH=2&HEIGHT=2&I=1&J=1"
        f"&INFO_FORMAT=text/plain"
    )

    logger.debug(f"Querying ICGC MDT: {url}")

    response_text = _fetch_wms(url)

    # Parse response: "@MET2m Stretch.Pixel Value; 199.320007;"
    match = re.search(r'Pixel Value;\s*(-?\d+\.?\d*)', response_text)
    if not match:
        raise ICGCElevationError(
            f"Could not parse elevation from ICGC MDT response: {response_text[:200]}"
        )

    try:
        elevation = float(match.group(1))
    except ValueError:
        raise ICGCElevationError(
            f"Invalid elevation value '{match.group(1)}' from ICGC MDT response"
        )

    # Validate reasonable range for Catalunya (0-3143m, Pica d'Estats)
    if elevation < -10 or elevation > 3200:
        raise ICGCElevationError(
            f"Elevation {elevation}m outside reasonable range for Catalunya"
        )

    # Cache
    if use_cache:
        _save_elevation_to_cache(utm_x, utm_y, elevation)

    return elevation


def format_cota_referencia(elevation: float) -> str:
    """
    Format elevation as cota de referencia for the report.

    Rounds to nearest 0.50m and formats as "+XXX.XX".

    Args:
        elevation: Elevation in meters

    Returns:
        Formatted cota string, e.g., "+199.50"
    """
    # Round to nearest 0.50m
    rounded = round(elevation * 2) / 2
    sign = "+" if rounded >= 0 else ""
    return f"{sign}{rounded:.2f}"


def get_slope(
    utm_x: float,
    utm_y: float,
    offset_m: float = 10.0,
    use_cache: bool = True,
) -> tuple[float, str]:
    """
    Calculate terrain slope at given coordinates using ICGC MDT 2m.

    Queries 5 points (center + 4 cardinal at offset_m distance) and
    calculates the maximum gradient.

    Args:
        utm_x: UTM X coordinate (ETRS89 zone 31N / EPSG:25831)
        utm_y: UTM Y coordinate
        offset_m: Distance from center for cardinal points (default 10m)
        use_cache: Whether to use cached elevation responses

    Returns:
        Tuple of (slope_percent, dominant_direction)
        - slope_percent: Slope as percentage (e.g., 5.0 means 5%)
        - dominant_direction: Cardinal direction of max slope ('N','S','E','W','NE','NW','SE','SW')

    Raises:
        ICGCElevationError: If elevation queries fail
    """
    # Query 5 points
    z_center = get_elevation(utm_x, utm_y, use_cache=use_cache)
    z_north = get_elevation(utm_x, utm_y + offset_m, use_cache=use_cache)
    z_south = get_elevation(utm_x, utm_y - offset_m, use_cache=use_cache)
    z_east = get_elevation(utm_x + offset_m, utm_y, use_cache=use_cache)
    z_west = get_elevation(utm_x - offset_m, utm_y, use_cache=use_cache)

    # Calculate gradients
    dz_ns = (z_north - z_south) / (2 * offset_m)  # positive = slopes up northward
    dz_ew = (z_east - z_west) / (2 * offset_m)    # positive = slopes up eastward

    # Max slope
    slope_ratio = math.sqrt(dz_ns**2 + dz_ew**2)
    slope_percent = slope_ratio * 100

    # Determine dominant direction (direction slope descends toward)
    angle_rad = math.atan2(-dz_ns, -dz_ew)  # negative because we want downhill direction
    angle_deg = math.degrees(angle_rad)

    # Map angle to cardinal direction
    if angle_deg < 0:
        angle_deg += 360

    directions = ['E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE']
    idx = round(angle_deg / 45) % 8
    direction = directions[idx]

    logger.info(f"Slope at ({utm_x}, {utm_y}): {slope_percent:.1f}% toward {direction}")

    return slope_percent, direction


# === MDT Elevation Cache ===

def _elevation_cache_key(utm_x: float, utm_y: float) -> str:
    """Generate cache key for elevation query."""
    x_rounded = round(utm_x / 10) * 10  # Round to nearest 10m
    y_rounded = round(utm_y / 10) * 10
    key_str = f"elev_{x_rounded}_{y_rounded}"
    return hashlib.sha256(key_str.encode()).hexdigest()[:12]


def _load_elevation_from_cache(utm_x: float, utm_y: float) -> float | None:
    """Load elevation from cache if available and not expired."""
    cache_path = MDT_CACHE_DIR / f"{_elevation_cache_key(utm_x, utm_y)}.json"
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cached_at = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
        if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
            cache_path.unlink()
            return None

        return data.get('elevation')
    except (json.JSONDecodeError, KeyError, ValueError):
        cache_path.unlink(missing_ok=True)
        return None


def _save_elevation_to_cache(utm_x: float, utm_y: float, elevation: float) -> None:
    """Save elevation to cache."""
    MDT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = MDT_CACHE_DIR / f"{_elevation_cache_key(utm_x, utm_y)}.json"

    data = {
        'cached_at': datetime.now().isoformat(),
        'coordinates': {'utm_x': utm_x, 'utm_y': utm_y},
        'elevation': elevation,
    }

    try:
        fd, temp_path = tempfile.mkstemp(dir=MDT_CACHE_DIR, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Path(temp_path).rename(cache_path)
        except Exception:
            Path(temp_path).unlink(missing_ok=True)
            raise
    except OSError as e:
        logger.warning(f"Failed to cache elevation: {e}")


# === WMS GetMap Image Downloads ===

ICGC_ORTHO_WMS_URL = "https://geoserveis.icgc.cat/servei/catalunya/orto-territorial/wms"
ICGC_ORTHO_LAYER = "ortofoto_color_vigent"


def get_orthophoto_image(
    utm_x: float,
    utm_y: float,
    output_path: str | Path,
    buffer_m: float = 200.0,
    width: int = 800,
    height: int = 600,
) -> Path:
    """
    Download ICGC orthophoto image centered on given UTM coordinates.

    Uses the ICGC multibase WMS service (free, official orthophoto).

    Args:
        utm_x: UTM X coordinate (ETRS89 zone 31N / EPSG:25831)
        utm_y: UTM Y coordinate
        output_path: Where to save the JPEG image
        buffer_m: Buffer around point in meters (default 200m)
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Path to saved image

    Raises:
        ICGCCoordinateError: If coordinates are outside Catalunya
        ICGCConnectionError: If download fails
    """
    _validate_coordinates(utm_x, utm_y)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    x_min = utm_x - buffer_m
    y_min = utm_y - buffer_m
    x_max = utm_x + buffer_m
    y_max = utm_y + buffer_m

    url = (
        f"{ICGC_ORTHO_WMS_URL}"
        f"?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
        f"&LAYERS={ICGC_ORTHO_LAYER}"
        f"&STYLES=&SRS=EPSG:25831"
        f"&BBOX={x_min},{y_min},{x_max},{y_max}"
        f"&WIDTH={width}&HEIGHT={height}"
        f"&FORMAT=image/jpeg"
    )

    logger.debug(f"Downloading orthophoto: {url}")

    try:
        urllib.request.urlretrieve(url, str(output_path))
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as e:
        raise ICGCConnectionError(f"Failed to download orthophoto: {e}")

    # Validate response is actually JPEG, not XML error
    with open(output_path, 'rb') as f:
        header = f.read(4)
    if header[:2] != b'\xff\xd8':
        output_path.unlink(missing_ok=True)
        raise ICGCConnectionError("Orthophoto download returned non-JPEG response (likely WMS error)")

    logger.info(f"Orthophoto saved to {output_path}")
    return output_path


def get_geological_map_image(
    utm_x: float,
    utm_y: float,
    output_path: str | Path,
    buffer_m: float = 1000.0,
    width: int = 800,
    height: int = 600,
) -> Path:
    """
    Download ICGC geological map image centered on given UTM coordinates.

    Uses the same WMS URL already configured as ICGC_WMS_URL in this module.
    Wider buffer (1000m) than orthophoto for geological context.

    Args:
        utm_x: UTM X coordinate (ETRS89 zone 31N / EPSG:25831)
        utm_y: UTM Y coordinate
        output_path: Where to save the JPEG image
        buffer_m: Buffer around point in meters (default 1000m)
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Path to saved image

    Raises:
        ICGCCoordinateError: If coordinates are outside Catalunya
        ICGCConnectionError: If download fails
    """
    _validate_coordinates(utm_x, utm_y)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    x_min = utm_x - buffer_m
    y_min = utm_y - buffer_m
    x_max = utm_x + buffer_m
    y_max = utm_y + buffer_m

    url = (
        f"{ICGC_WMS_URL}"
        f"?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
        f"&LAYERS=unitats-geologiques-50000"
        f"&STYLES=&SRS=EPSG:25831"
        f"&BBOX={x_min},{y_min},{x_max},{y_max}"
        f"&WIDTH={width}&HEIGHT={height}"
        f"&FORMAT=image/jpeg"
    )

    logger.debug(f"Downloading geological map: {url}")

    try:
        urllib.request.urlretrieve(url, str(output_path))
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as e:
        raise ICGCConnectionError(f"Failed to download geological map: {e}")

    # Validate response is actually JPEG, not XML error
    with open(output_path, 'rb') as f:
        header = f.read(4)
    if header[:2] != b'\xff\xd8':
        output_path.unlink(missing_ok=True)
        raise ICGCConnectionError("Geological map download returned non-JPEG response (likely WMS error)")

    logger.info(f"Geological map saved to {output_path}")
    return output_path


# === Orthophoto with Parcel Outline ===

def get_orthophoto_with_parcel(
    utm_x: float,
    utm_y: float,
    polygon_utm: list[tuple[float, float]],
    output_path: str | Path,
    buffer_m: float = 200.0,
    width: int = 800,
    height: int = 600,
) -> Path:
    """
    Download ICGC orthophoto and overlay a red parcel polygon outline.

    Combines the ICGC WMS orthophoto with a Cadastre parcel polygon
    drawn as a red outline, similar to Eva's reference "Foto Emplaçament".

    Args:
        utm_x: UTM X coordinate (EPSG:25831) for centering
        utm_y: UTM Y coordinate
        polygon_utm: List of (x, y) UTM coordinate tuples forming the parcel polygon
        output_path: Where to save the PNG image
        buffer_m: Buffer around center point in meters (default 200m)
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Path to saved image

    Raises:
        ICGCCoordinateError: If coordinates are outside Catalunya
        ICGCConnectionError: If orthophoto download fails
    """
    from PIL import Image, ImageDraw

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Compute WMS bbox with aspect-ratio correction
    # buffer_m defines the vertical extent; horizontal is scaled to image aspect ratio
    aspect = width / height
    buffer_x = buffer_m * aspect
    buffer_y = buffer_m
    x_min = utm_x - buffer_x
    y_min = utm_y - buffer_y
    x_max = utm_x + buffer_x
    y_max = utm_y + buffer_y

    # Download base orthophoto to a temp file using corrected bbox
    temp_ortho = output_path.with_suffix('.ortho.jpg')
    try:
        _validate_coordinates(utm_x, utm_y)

        url = (
            f"{ICGC_ORTHO_WMS_URL}"
            f"?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
            f"&LAYERS={ICGC_ORTHO_LAYER}"
            f"&STYLES=&SRS=EPSG:25831"
            f"&BBOX={x_min},{y_min},{x_max},{y_max}"
            f"&WIDTH={width}&HEIGHT={height}"
            f"&FORMAT=image/jpeg"
        )

        try:
            urllib.request.urlretrieve(url, str(temp_ortho))
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as e:
            raise ICGCConnectionError(f"Failed to download orthophoto: {e}")

        with open(temp_ortho, 'rb') as f:
            header = f.read(4)
        if header[:2] != b'\xff\xd8':
            temp_ortho.unlink(missing_ok=True)
            raise ICGCConnectionError("Orthophoto download returned non-JPEG response")

        # Open and convert to RGBA for drawing
        img = Image.open(str(temp_ortho)).convert("RGBA")
        img_w, img_h = img.size

        # Convert polygon UTM coords to pixel coords using actual image dimensions
        pixel_coords = []
        for vx, vy in polygon_utm:
            px = (vx - x_min) / (x_max - x_min) * img_w
            py = img_h - (vy - y_min) / (y_max - y_min) * img_h  # Y inverted
            pixel_coords.append((px, py))

        if len(pixel_coords) >= 3:
            # Draw semi-transparent red fill
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            draw_overlay.polygon(pixel_coords, fill=(255, 0, 0, 40))
            img = Image.alpha_composite(img, overlay)

            # Draw red outline on top (multiple passes for thickness)
            draw = ImageDraw.Draw(img)
            draw.polygon(pixel_coords, outline='red')
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                shifted = [(x + dx, y + dy) for x, y in pixel_coords]
                draw.polygon(shifted, outline='red')

        # Save as PNG
        img.convert("RGB").save(str(output_path), "PNG")
        logger.info(f"Orthophoto with parcel outline saved to {output_path}")
        return output_path

    finally:
        temp_ortho.unlink(missing_ok=True)


# === CLI for Testing ===

if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.DEBUG)

    print("=" * 60)
    print("ICGC Geology Integration - Test")
    print("=" * 60)

    # Test coordinates
    test_coords = [
        (314508.67, 4611192.86, "Bell-Lloc d'Urgell"),  # Should return Qvpu at 50k
        (307500.0, 4615500.0, "West of Bell-Lloc"),
        (297500.0, 4618000.0, "Balaguer area"),
    ]

    for utm_x, utm_y, name in test_coords:
        print(f"\n--- {name} ({utm_x}, {utm_y}) ---")
        try:
            unit = get_geological_unit(utm_x, utm_y, use_cache=False)
            print(f"Code: {unit.code}")
            print(f"Description: {unit.description}")
            print(f"Era: {unit.era}")
            print(f"Period: {unit.period}")
            print(f"Epoch: {unit.epoch}")
            print(f"\nReport format:")
            print(unit.format_for_report())
            print(f"\nRegion: {determine_region(unit, name)}")
        except ICGCError as e:
            print(f"Error: {e}")

    # Test elevation
    print("\n--- Elevation Test ---")
    try:
        elevation = get_elevation(314508.67, 4611192.86, use_cache=False)
        cota = format_cota_referencia(elevation)
        print(f"Elevation: {elevation:.2f} m")
        print(f"Cota referencia: {cota}")
    except ICGCError as e:
        print(f"Elevation error: {e}")

    # Test slope
    print("\n--- Slope Test ---")
    try:
        slope_pct, slope_dir = get_slope(314508.67, 4611192.86, use_cache=False)
        print(f"Slope: {slope_pct:.1f}% toward {slope_dir}")
        print(f"Is sloped (>15%): {slope_pct > 15.0}")
    except ICGCError as e:
        print(f"Slope error: {e}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
