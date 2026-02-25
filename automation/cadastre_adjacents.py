#!/usr/bin/env python3
"""
Cadastre Adjacent Parcels Detection Module

Auto-detects adjacent parcels and streets around a cadastral parcel using
the Spanish Cadastre XML API (OVC). Probes in four cardinal directions from
the parcel centroid to determine what lies on each side: another parcel
or a street (translated to Catalan).

API Documentation:
    http://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCoordenadas.asmx

Usage:
    from cadastre_adjacents import get_adjacent_parcels

    # Query by UTM coordinates (ETRS89 zone 31N / EPSG:25831)
    result = get_adjacent_parcels(314508.67, 4611192.86, superficie=600.0)
    print(result['north'])  # e.g., "Carrer Mestre Ramon Ortiz"
    print(result['south'])  # e.g., "parcel·la veïna"

Author: Eficients.cat
Date: 2026-02-06
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
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    'get_adjacent_parcels',
    'CadastreError',
    'CadastreConnectionError',
    'CadastreParseError',
    'CadastreNoDataError',
]


# === Configuration ===

CADASTRE_URL = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCoordenadas.asmx"
CADASTRE_DATA_URL = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx"
SRS = "EPSG:25831"  # UTM zone 31N (same as ICGC)
CACHE_DIR = Path.home() / ".g3dt" / "cache" / "cadastre_adjacents"
CACHE_TTL_DAYS = 90
REQUEST_TIMEOUT_SECONDS = 15
USER_AGENT = "G3DT-Automation/1.0 (Eficients.cat; geotechnical report generation)"

# Namespace used by the Cadastre API responses
CADASTRE_NS = {'ovc': 'http://www.catastro.meh.es/'}


# === Exception Hierarchy ===

class CadastreError(Exception):
    """Base exception for Cadastre-related errors."""
    pass


class CadastreConnectionError(CadastreError):
    """Failed to connect to Cadastre service."""
    pass


class CadastreParseError(CadastreError):
    """Failed to parse Cadastre response."""
    pass


class CadastreNoDataError(CadastreError):
    """No cadastral data found for the given location."""
    pass


# === Street Name Translation (castella -> catala) ===

STREET_TRANSLATIONS: dict[str, str] = {
    'CALLE': 'Carrer',
    'CL': 'Carrer',
    'AVENIDA': 'Avinguda',
    'AV': 'Avinguda',
    'PLAZA': 'Plaça',
    'PZ': 'Plaça',
    'PASEO': 'Passeig',
    'PS': 'Passeig',
    'CAMINO': 'Camí',
    'CM': 'Camí',
    'CARRETERA': 'Carretera',
    'CR': 'Carretera',
    'TRAVESIA': 'Travessia',
    'TR': 'Travessia',
    'RONDA': 'Ronda',
    'RD': 'Ronda',
    'PARTIDA': 'Partida',
    'PD': 'Partida',
}

# Cardinal directions: name -> (dx, dy)
DIRECTIONS: dict[str, tuple[int, int]] = {
    'north': (0, 1),
    'south': (0, -1),
    'east': (1, 0),
    'west': (-1, 0),
}


# === HTTP Fetch with Retry ===

def _fetch_xml(url: str) -> str:
    """
    Fetch XML response from Cadastre API with retry logic.

    Args:
        url: Full API URL

    Returns:
        Response text (UTF-8 decoded)

    Raises:
        CadastreConnectionError: If all retry attempts fail
    """
    max_attempts = 3
    last_error: CadastreConnectionError | None = None

    for attempt in range(max_attempts):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read().decode('utf-8')
        except urllib.error.URLError as e:
            last_error = CadastreConnectionError(f"Failed to connect to Cadastre: {e}")
        except (TimeoutError, socket.timeout) as e:
            last_error = CadastreConnectionError(f"Cadastre request timed out: {e}")

        if attempt < max_attempts - 1:
            delay = 2 ** attempt
            logger.debug(f"Cadastre request attempt {attempt + 1} failed, retrying in {delay}s...")
            time.sleep(delay)

    raise last_error  # type: ignore[misc]


# === XML Parsing Helpers ===

def _strip_ns(tag: str) -> str:
    """Strip XML namespace from a tag name."""
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def _find_element(root: ET.Element, path: str) -> ET.Element | None:
    """
    Find an element by local name path (namespace-agnostic).

    path is slash-separated local names, e.g. "coordenadas/coord/pc/pc1".
    """
    parts = path.split('/')
    current = root
    for part in parts:
        found = None
        for child in current:
            if _strip_ns(child.tag) == part:
                found = child
                break
        if found is None:
            return None
        current = found
    return current


def _find_all_elements(root: ET.Element, local_name: str) -> list[ET.Element]:
    """Find all descendant elements matching a local tag name."""
    results = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == local_name:
            results.append(elem)
    return results


# === Core Query Functions ===

def _query_ref_by_coords(utm_x: float, utm_y: float) -> tuple[str | None, str | None]:
    """
    Query cadastral reference at given UTM coordinates via Consulta_RCCOOR.

    Args:
        utm_x: UTM X coordinate (EPSG:25831)
        utm_y: UTM Y coordinate (EPSG:25831)

    Returns:
        Tuple of (cadastral_reference, ldt_address).
        cadastral_reference is None if the point falls on a street or error.
        ldt_address is the raw LDT string (may be available even for streets).

    Raises:
        CadastreConnectionError: If connection fails
        CadastreParseError: If XML cannot be parsed
    """
    url = (
        f"{CADASTRE_URL}/Consulta_RCCOOR"
        f"?SRS={SRS}&Coordenada_X={utm_x}&Coordenada_Y={utm_y}"
    )
    logger.debug(f"Querying Cadastre RCCOOR: {url}")

    response_text = _fetch_xml(url)

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as e:
        raise CadastreParseError(f"Invalid XML from Cadastre RCCOOR: {e}")

    # Check for error response
    err_elem = _find_element(root, "coordenadas/coord/err")
    if err_elem is None:
        err_elems = _find_all_elements(root, "err")
        if err_elems:
            err_elem = err_elems[0]

    if err_elem is not None:
        err_msg = ""
        cod_elem = _find_element(err_elem, "cod")
        des_elem = _find_element(err_elem, "des")
        if cod_elem is not None and cod_elem.text:
            err_msg += f"[{cod_elem.text}] "
        if des_elem is not None and des_elem.text:
            err_msg += des_elem.text
        logger.debug(f"Cadastre error at ({utm_x}, {utm_y}): {err_msg}")
        return None, None

    # Extract cadastral reference (pc1 + pc2)
    pc1_elem = _find_element(root, "coordenadas/coord/pc/pc1")
    pc2_elem = _find_element(root, "coordenadas/coord/pc/pc2")

    # Fallback: search anywhere in the tree
    if pc1_elem is None:
        pc1_elems = _find_all_elements(root, "pc1")
        pc1_elem = pc1_elems[0] if pc1_elems else None
    if pc2_elem is None:
        pc2_elems = _find_all_elements(root, "pc2")
        pc2_elem = pc2_elems[0] if pc2_elems else None

    # Extract LDT (address description)
    ldt_elem = _find_element(root, "coordenadas/coord/ldt")
    if ldt_elem is None:
        ldt_elems = _find_all_elements(root, "ldt")
        ldt_elem = ldt_elems[0] if ldt_elems else None

    ldt = ldt_elem.text.strip() if ldt_elem is not None and ldt_elem.text else None

    if pc1_elem is None or not pc1_elem.text:
        return None, ldt

    pc1 = pc1_elem.text.strip()
    pc2 = pc2_elem.text.strip() if pc2_elem is not None and pc2_elem.text else ""

    ref = pc1 + pc2
    logger.debug(f"Cadastre ref at ({utm_x}, {utm_y}): {ref}, ldt: {ldt}")
    return ref, ldt


def _query_address_by_ref(ref: str) -> str:
    """
    Query address for a cadastral reference via Consulta_CPMRC.

    NOTE: Currently unused. Reserved for future enhancement where
    adjacent parcel addresses are included in the report.

    Args:
        ref: Cadastral reference string

    Returns:
        Formatted address string

    Raises:
        CadastreConnectionError: If connection fails
        CadastreParseError: If XML cannot be parsed
    """
    url = (
        f"{CADASTRE_DATA_URL}/Consulta_CPMRC"
        f"?Provincia=&Municipio=&SRS={SRS}&RC={ref}"
    )
    logger.debug(f"Querying Cadastre CPMRC: {url}")

    response_text = _fetch_xml(url)

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as e:
        raise CadastreParseError(f"Invalid XML from Cadastre CPMRC: {e}")

    # Extract street type (tv) and name (nv) from <dir>
    tv_elem = _find_all_elements(root, "tv")
    nv_elem = _find_all_elements(root, "nv")

    street_type = tv_elem[0].text.strip() if tv_elem and tv_elem[0].text else ""
    street_name = nv_elem[0].text.strip() if nv_elem and nv_elem[0].text else ""

    if street_type or street_name:
        raw = f"{street_type} {street_name}".strip()
        return _translate_street_name(raw)

    return ""


# === Street Name Translation ===

def _translate_street_name(raw_address: str) -> str:
    """
    Translate a raw address string from Castilian to Catalan.

    Handles formats like:
    - "CALLE MESTRE RAMON ORTIZ 0005 BELL-LLOC D'URGELL (LLEIDA)"
    - "CL MESTRE RAMON ORTIZ"
    - "AVENIDA CATALUNYA"

    Returns translated and cleaned street name, e.g. "Carrer Mestre Ramon Ortiz".
    """
    if not raw_address:
        return ""

    text = raw_address.strip()

    # Remove "(PROVINCE)" suffix at the end
    text = re.sub(r'\s*\(.*\)\s*$', '', text)

    # Remove house number + municipality: "41 BELL-LLOC D'URGELL", "0005 BELL-LLOC"
    # Pattern: digits followed by a word starting with uppercase (municipality)
    text = re.sub(r'\s+\d+\s+[A-Z].*$', '', text)

    # Remove "PROVIENE DE ..." cadastre annotation
    text = re.sub(r'\s+PROVIENE DE\s+.*$', '', text, flags=re.IGNORECASE)

    # Remove any remaining trailing digits (house numbers)
    text = re.sub(r'\s+\d+\s*$', '', text)

    text = text.strip()
    if not text:
        return ""

    # Split into words and translate the first word (street type)
    words = text.split(None, 1)
    if not words:
        return ""

    first_word = words[0].upper()
    rest = words[1] if len(words) > 1 else ""

    translated_type = STREET_TRANSLATIONS.get(first_word, None)

    if translated_type:
        # Title-case the rest of the name
        name = rest.title() if rest else ""
        return f"{translated_type} {name}".strip()

    # No translation found; return as title case
    return text.title()


# === Probe Logic ===

def _probe_direction(
    utm_x: float,
    utm_y: float,
    our_ref: str,
    dx: int,
    dy: int,
    superficie: float,
) -> str:
    """
    Probe in one direction to find what is adjacent to our parcel.

    Algorithm — gradual scan from parcel edge:
    1. Start just outside the parcel edge (half-side + 1m)
    2. Increment by 2m, up to 8 probes
    3. Track what we find: our parcel, street (NULL), or neighbor parcel
    4. If we hit a street (NULL) at any point → return translated street name
    5. If we jump directly to a different parcel → "parcel·la veïna"

    This gradual approach detects narrow streets (6-8m) that a single
    large jump would overshoot.

    Args:
        utm_x: Parcel centroid UTM X
        utm_y: Parcel centroid UTM Y
        our_ref: Our parcel's cadastral reference
        dx: X direction multiplier (-1, 0, or 1)
        dy: Y direction multiplier (-1, 0, or 1)
        superficie: Parcel area in m2

    Returns:
        Description of what is adjacent: street name or "parcel·la veïna"
    """
    half_side = math.sqrt(superficie) / 2
    start_distance = half_side + 1  # Just outside the parcel edge
    step = 2  # 2m increments to catch narrow streets
    max_probes = 8

    crossed_street = False  # Track if we crossed a street (NULL zone)

    for i in range(max_probes):
        distance = start_distance + (i * step)
        probe_x = utm_x + dx * distance
        probe_y = utm_y + dy * distance

        logger.debug(
            f"Probing ({dx}, {dy}) at distance {distance:.1f}m -> "
            f"({probe_x:.2f}, {probe_y:.2f})"
        )

        try:
            ref, ldt = _query_ref_by_coords(probe_x, probe_y)
        except CadastreError as e:
            logger.warning(f"Probe failed at ({probe_x}, {probe_y}): {e}")
            return "desconegut"

        if ref is None:
            # No cadastral reference -> we're on a street
            logger.debug(f"Street detected at distance {distance:.1f}m")
            crossed_street = True
            continue

        # Compare first 14 chars (parcel+plot) to handle pc2 variations
        if ref[:14] == our_ref[:14]:
            # Still on our parcel, keep scanning
            logger.debug(f"Still on our parcel at distance {distance:.1f}m")
            continue

        # Found a different parcel
        if crossed_street:
            # We crossed a street to get here → adjacent is a street
            # Use the NEIGHBOR's LDT for the street name (error responses
            # don't include LDT, but addressed parcels always do)
            if ldt:
                street = _translate_street_name(ldt)
                if street:
                    logger.debug(f"Street name from neighbor LDT: {street}")
                    return street
            return "via pública"

        # Direct neighbor (no street in between)
        return "parcel·la veïna"

    # Exhausted probes without finding a neighbor
    if crossed_street:
        # We found a street but never reached the other side
        return "via pública"

    logger.warning(
        f"Could not exit parcel after {max_probes} probes in direction ({dx}, {dy})"
    )
    return "desconegut"


# === Main Entry Point ===

def get_adjacent_parcels(
    utm_x: float,
    utm_y: float,
    superficie: float,
    use_cache: bool = True,
) -> dict[str, str]:
    """
    Detect adjacent parcels and streets around a cadastral parcel.

    Args:
        utm_x: Parcel centroid UTM X (EPSG:25831)
        utm_y: Parcel centroid UTM Y (EPSG:25831)
        superficie: Parcel area in m2 (used to calculate probe distance)
        use_cache: Whether to use cached results (default True)

    Returns:
        Dict with keys: north, south, east, west.
        Each value is either a street name (e.g. "Carrer Mestre Ramon Ortiz")
        or "parcel·la veïna".

    Raises:
        CadastreConnectionError: If connection to Cadastre fails
        CadastreParseError: If response cannot be parsed
        CadastreNoDataError: If our own parcel cannot be identified
    """
    # Check cache first
    if use_cache:
        cached = _load_from_cache(utm_x, utm_y)
        if cached is not None:
            logger.debug(f"Cache hit for adjacents at ({utm_x}, {utm_y})")
            return cached

    # Query our own cadastral reference
    our_ref, our_ldt = _query_ref_by_coords(utm_x, utm_y)
    if our_ref is None:
        raise CadastreNoDataError(
            f"Could not determine cadastral reference at ({utm_x}, {utm_y})"
        )
    logger.info(f"Our cadastral ref: {our_ref} ({our_ldt})")

    # Probe all four directions
    result: dict[str, str] = {}
    for direction, (dx, dy) in DIRECTIONS.items():
        logger.info(f"Probing {direction}...")
        result[direction] = _probe_direction(utm_x, utm_y, our_ref, dx, dy, superficie)
        logger.info(f"  {direction}: {result[direction]}")

    # Cache the result
    if use_cache:
        _save_to_cache(utm_x, utm_y, result)

    return result


# === Caching Functions ===

def _get_cache_key(utm_x: float, utm_y: float) -> str:
    """Generate cache key from coordinates."""
    key_str = f"adj_{round(utm_x)}_{round(utm_y)}"
    return hashlib.sha256(key_str.encode()).hexdigest()[:12]


def _get_cache_path(utm_x: float, utm_y: float) -> Path:
    """Get path to cache file for given coordinates."""
    cache_key = _get_cache_key(utm_x, utm_y)
    return CACHE_DIR / f"{cache_key}.json"


def _load_from_cache(utm_x: float, utm_y: float) -> dict[str, str] | None:
    """
    Load adjacents result from cache if available and not expired.

    Returns None if not cached or expired.
    """
    cache_path = _get_cache_path(utm_x, utm_y)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cached_at = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
        if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
            logger.debug(f"Cache expired for adjacents at ({utm_x}, {utm_y})")
            cache_path.unlink()
            return None

        return data['adjacents']

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Invalid cache file {cache_path}: {e}")
        cache_path.unlink()
        return None


def _save_to_cache(utm_x: float, utm_y: float, adjacents: dict[str, str]) -> None:
    """Save adjacents result to cache using atomic write."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _get_cache_path(utm_x, utm_y)

    data = {
        'cached_at': datetime.now().isoformat(),
        'coordinates': {'utm_x': utm_x, 'utm_y': utm_y},
        'adjacents': adjacents,
    }

    try:
        fd, temp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Path(temp_path).rename(cache_path)
            logger.debug(f"Cached adjacents result at {cache_path}")
        except Exception:
            Path(temp_path).unlink(missing_ok=True)
            raise
    except OSError as e:
        logger.warning(f"Failed to cache adjacents result: {e}")


# === CLI for Testing ===

if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.DEBUG)

    # Bell-Lloc d'Urgell test case
    utm_x = 314508.67
    utm_y = 4611192.86
    superficie = 600.0  # approximate m2

    print("=" * 60)
    print("Cadastre Adjacents - Test")
    print("=" * 60)
    print(f"Coordinates: ({utm_x}, {utm_y})")
    print(f"Superficie: {superficie} m2")
    print()

    try:
        result = get_adjacent_parcels(utm_x, utm_y, superficie, use_cache=False)
        for direction, value in result.items():
            print(f"  {direction.capitalize():6s}: {value}")
    except CadastreError as e:
        print(f"Error: {e}")
