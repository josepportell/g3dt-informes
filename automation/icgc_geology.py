#!/usr/bin/env python3
"""
ICGC Geology Integration Module

Queries the Institut Cartogràfic i Geològic de Catalunya (ICGC) WMS service
to retrieve authoritative geological unit information for a given location.

The ICGC provides official geological mapping for Catalunya at various scales.
This module uses the 1:250,000 geological units layer which covers all of Catalunya.

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
]


# === Configuration ===

ICGC_WMS_URL = "https://geoserveis.icgc.cat/servei/catalunya/geologia-territorial/wms"
ICGC_LAYER = "unitats-geologiques-250000"
ICGC_CRS = "EPSG:25831"  # ETRS89 / UTM zone 31N
ICGC_INFO_FORMAT = "text/plain"

# Cache settings
CACHE_DIR = Path.home() / ".g3dt" / "cache" / "icgc_units"
CACHE_TTL_DAYS = 30
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


def get_geological_unit(
    utm_x: float,
    utm_y: float,
    use_cache: bool = True,
) -> GeologicalUnit:
    """
    Query ICGC WMS for geological unit at given UTM coordinates.

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
        ICGCNoDataError: If no geological data found for location
    """
    # Validate coordinates
    _validate_coordinates(utm_x, utm_y)

    # Check cache first
    if use_cache:
        cached = _load_from_cache(utm_x, utm_y)
        if cached:
            logger.debug(f"Cache hit for ({utm_x}, {utm_y})")
            return cached

    # Build WMS GetFeatureInfo request
    url = _build_wms_url(utm_x, utm_y)
    logger.debug(f"Querying ICGC: {url}")

    # Execute request with retry logic for transient connection errors
    max_attempts = 3
    last_error: ICGCConnectionError | None = None

    for attempt in range(max_attempts):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                response_text = response.read().decode('utf-8')
            break  # Success, exit retry loop
        except urllib.error.URLError as e:
            last_error = ICGCConnectionError(f"Failed to connect to ICGC: {e}")
        except (TimeoutError, socket.timeout) as e:
            last_error = ICGCConnectionError(f"ICGC request timed out: {e}")

        # Retry with exponential backoff (1s, 2s, 4s)
        if attempt < max_attempts - 1:
            delay = 2 ** attempt
            logger.debug(f"ICGC request attempt {attempt + 1} failed, retrying in {delay}s...")
            time.sleep(delay)
    else:
        # All attempts failed
        raise last_error  # type: ignore[misc]

    # Parse response
    unit = _parse_response(response_text)

    # Save to cache
    if use_cache:
        _save_to_cache(utm_x, utm_y, unit)

    return unit


def _build_wms_url(utm_x: float, utm_y: float) -> str:
    """
    Build WMS GetFeatureInfo URL for given coordinates.

    Uses a small bounding box centered on the point and queries
    the center pixel of the resulting image.
    """
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
        f"LAYERS={ICGC_LAYER}",
        f"QUERY_LAYERS={ICGC_LAYER}",
        f"CRS={ICGC_CRS}",
        f"BBOX={min_x},{min_y},{max_x},{max_y}",
        f"WIDTH={width}",
        f"HEIGHT={height}",
        f"I={i}",
        f"J={j}",
        f"INFO_FORMAT={ICGC_INFO_FORMAT}",
    ]

    return f"{ICGC_WMS_URL}?{'&'.join(params)}"


def _parse_response(response_text: str) -> GeologicalUnit:
    """
    Parse ICGC GetFeatureInfo plain text response.

    The ICGC WMS returns a single line with headers and data separated by space:
        @unitats-geologiques-250000 OBJECTID;Codi;...;Descripcio_protolit; 231;Q3D;...;Null;

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

    # Remove layer prefix (@unitats-geologiques-250000 )
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

    logger.debug(f"Parsed ICGC data: {data_dict}")

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

    Returns None if not cached or expired.
    """
    cache_path = _get_cache_path(utm_x, utm_y)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check expiration
        cached_at = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
        if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
            logger.debug(f"Cache expired for ({utm_x}, {utm_y})")
            cache_path.unlink()  # Delete expired cache
            return None

        return GeologicalUnit.from_dict(data['unit'])

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Invalid cache file {cache_path}: {e}")
        cache_path.unlink()  # Delete corrupted cache
        return None


def _save_to_cache(utm_x: float, utm_y: float, unit: GeologicalUnit) -> None:
    """Save geological unit to cache using atomic write."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _get_cache_path(utm_x, utm_y)

    data = {
        'cached_at': datetime.now().isoformat(),
        'coordinates': {'utm_x': utm_x, 'utm_y': utm_y},
        'unit': unit.to_dict(),
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
        municipality_lower = municipality.lower()
        for region, criteria in REGION_MAPPING.items():
            for muni in criteria.get('municipalities', []):
                if muni.lower() in municipality_lower or municipality_lower in muni.lower():
                    return region

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


# === CLI for Testing ===

if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.DEBUG)

    print("=" * 60)
    print("ICGC Geology Integration - Test")
    print("=" * 60)

    # Test coordinates (Bell-Lloc d'Urgell area)
    test_coords = [
        (307500.0, 4615500.0, "Bell-Lloc d'Urgell"),
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

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
