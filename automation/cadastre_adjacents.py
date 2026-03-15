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
    'get_parcel_geometry_utm',
    'get_cadastral_reference',
    'CadastreError',
    'CadastreConnectionError',
    'CadastreParseError',
    'CadastreNoDataError',
]


# === Configuration ===

CADASTRE_URL = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCoordenadas.asmx"
CADASTRE_DATA_URL = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx"
CADASTRE_WFS_URL = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
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

CASTILIAN_TO_CATALAN_NAMES: dict[str, str] = {
    'ANTONIO': 'Antoni', 'FRANCISCO': 'Francesc', 'JOSE': 'Josep',
    'JUAN': 'Joan', 'PEDRO': 'Pere', 'MIGUEL': 'Miquel',
    'JAIME': 'Jaume', 'JORGE': 'Jordi', 'LUIS': 'Lluís',
    'ANDRES': 'Andreu', 'RAMON': 'Ramon', 'CARLOS': 'Carles',
    'ALBERTO': 'Albert', 'FERNANDO': 'Ferran', 'PABLO': 'Pau',
    'SANTIAGO': 'Jaume', 'TERESA': 'Teresa', 'MARIA': 'Maria',
}

CASTILIAN_TO_CATALAN_WORDS: dict[str, str] = {
    'MAYOR': 'Major', 'NUEVA': 'Nova', 'NUEVO': 'Nou',
    'IGLESIA': 'Església', 'FUENTE': 'Font',
}

CATALAN_LOWERCASE_MIDWORDS: set[str] = {'I', 'De', 'Del', 'La', 'El', 'Les', 'Els', 'Dels'}

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


# === Neighbor Parcel Description (DNPRC) ===

def _query_building_data(ref: str) -> dict | None:
    """
    Query building data for a cadastral reference via Consulta_DNPRC.

    Args:
        ref: Cadastral reference string (14+ chars)

    Returns:
        Dict with building info or None if query fails:
        {
            'num_floors_above': int,
            'num_floors_below': int,
            'total_built_m2': float,
            'primary_use': str,  # 'RESIDENCIAL', 'INDUSTRIAL', etc.
            'has_building': bool,
        }
    """
    try:
        url = (
            f"{CADASTRE_DATA_URL}/Consulta_DNPRC"
            f"?Provincia=&Municipio=&RC={ref}"
        )
        logger.debug(f"Querying Cadastre DNPRC: {url}")

        response_text = _fetch_xml(url)
        root = ET.fromstring(response_text)

        # Extract construction elements
        lcons_elems = _find_all_elements(root, "lcons")

        if not lcons_elems:
            return {
                'num_floors_above': 0,
                'num_floors_below': 0,
                'total_built_m2': 0.0,
                'primary_use': '',
                'has_building': False,
            }

        seen_above: set[str] = set()
        seen_below: set[str] = set()
        total_m2 = 0.0
        primary_use = ''

        for lcons in lcons_elems:
            # Floor type — deduplicate by stl value to avoid overcounting
            # multi-unit buildings (multiple lcons with same floor identifier)
            stl_elems = _find_all_elements(lcons, "stl")
            stl = stl_elems[0].text.strip().upper() if stl_elems and stl_elems[0].text else ''

            if 'SOTANO' in stl or 'SÓTANO' in stl:
                seen_below.add(stl)
            elif 'PLANTA' in stl or 'SUELO' in stl:
                seen_above.add(stl)

            # Surface
            sfc_elems = _find_all_elements(lcons, "sfc")
            if sfc_elems and sfc_elems[0].text:
                try:
                    total_m2 += float(sfc_elems[0].text.strip())
                except ValueError:
                    pass

            # Primary use (first occurrence)
            if not primary_use:
                luso_elems = _find_all_elements(lcons, "luso")
                if luso_elems and luso_elems[0].text:
                    primary_use = luso_elems[0].text.strip()

        return {
            'num_floors_above': len(seen_above),
            'num_floors_below': len(seen_below),
            'total_built_m2': total_m2,
            'primary_use': primary_use,
            'has_building': True,
        }

    except Exception as e:
        logger.debug(f"DNPRC query failed for {ref}: {e}")
        return None


_CATALAN_NUMBERS = {
    1: 'una', 2: 'dos', 3: 'tres', 4: 'quatre', 5: 'cinc',
    6: 'sis', 7: 'set', 8: 'vuit', 9: 'nou', 10: 'deu',
}


def _num_to_catalan(n: int) -> str:
    """Convert small integer to Catalan word."""
    return _CATALAN_NUMBERS.get(n, str(n))


def _describe_neighbor(ref: str) -> str:
    """
    Generate a Catalan description of a neighbor parcel based on Cadastre data.

    Queries building data via DNPRC and generates descriptions matching
    Eva's vocabulary in geotechnical reports.

    Args:
        ref: Cadastral reference of the neighbor parcel

    Returns:
        Description string, e.g. "parcel·la buida",
        "parcel·la amb construccio aillada de fins a dos plantes sobre rasant"
    """
    try:
        data = _query_building_data(ref)
    except Exception:
        return "parcel·la veïna"

    if data is None:
        return "parcel·la veïna"

    if not data['has_building']:
        return "parcel·la buida"

    # Special use types
    use = data['primary_use'].upper() if data['primary_use'] else ''
    if 'INDUSTRIAL' in use:
        return "nau industrial"
    if 'AGRARIO' in use or 'AGRÍCOLA' in use:
        return "terreny agrícola"
    if 'ALMACEN' in use or 'ALMACÉN' in use:
        return "magatzem"

    # Residential/generic building description
    floors = data['num_floors_above']
    if floors <= 0:
        return "parcel·la amb construcció"

    basement = data['num_floors_below'] > 0

    if floors == 1:
        desc = "parcel·la amb construcció aïllada d'una planta sobre rasant"
    elif floors == 2:
        desc = "parcel·la amb construcció aïllada de fins a dos plantes sobre rasant"
    else:
        desc = (
            f"parcel·la amb construcció aïllada de fins a "
            f"{_num_to_catalan(floors)} plantes sobre rasant"
        )

    if basement:
        desc += " i soterrani"

    return desc


# === Street Name Translation ===

def _translate_street_name(raw_address: str, municipality: str | None = None) -> str:
    """
    Translate a raw address string from Castilian to Catalan.

    Handles formats like:
    - "CALLE ANTONIO BELLET Y PEREZ 0005 BELL-LLOC D'URGELL (LLEIDA)"
    - "CL MESTRE RAMON ORTIZ"
    - "AVENIDA CATALUNYA"

    Applies:
    - Street type translation (CALLE → Carrer, etc.)
    - Province and municipality stripping
    - Spanish "Y" → "i" conjunction
    - Castilian first name translation (ANTONIO → Antoni)
    - Double surname shortening (truncate at " i " conjunction)
    - Catalan mid-word lowercasing (De, Del, La, etc.)

    Args:
        raw_address: Raw LDT or address string from Cadastre API
        municipality: Optional municipality name to strip from the end

    Returns:
        Translated and cleaned street name, e.g. "Carrer Antoni Bellet".
    """
    if not raw_address:
        return ""

    text = raw_address.strip()

    # Remove "(PROVINCE)" suffix at the end
    text = re.sub(r'\s*\(.*\)\s*$', '', text)

    # Strip municipality from the end (case-insensitive) if provided
    if municipality:
        muni_pattern = re.escape(municipality)
        text = re.sub(r'\s+' + muni_pattern + r'\s*$', '', text, flags=re.IGNORECASE)

    # Remove house number + municipality: "0005 BELL-LLOC D'URGELL", "41 Rubi"
    # Pattern: digits followed by any word starting with uppercase letter (including accented)
    text = re.sub(r'\s+\d{1,5}\s+[A-ZÀÁÈÉÍÏÒÓÚÜ].*$', '', text)

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
        if rest:
            # Replace standalone "Y" or "I" conjunction with "i"
            # Cadastre uses "Y" (Spanish) or "I" (Catalan) between surnames
            rest = re.sub(r'\b[YI]\b', 'i', rest)

            # Translate Castilian first names (position 0 only)
            rest_words = rest.split()
            has_personal_name = False
            if rest_words and rest_words[0].upper() in CASTILIAN_TO_CATALAN_NAMES:
                rest_words[0] = CASTILIAN_TO_CATALAN_NAMES[rest_words[0].upper()]
                has_personal_name = True

            # Translate common Castilian words only for non-personal-name streets
            # (avoids turning surname "Mayor" into "Major")
            if not has_personal_name:
                rest_words = [
                    CASTILIAN_TO_CATALAN_WORDS.get(w.upper(), w)
                    for w in rest_words
                ]
            rest = ' '.join(rest_words)

            # Shorten double surnames: truncate at " i " (the conjunction)
            # Only when a personal name was detected, to avoid cutting
            # legitimate names like "Indústria i Comerç"
            if has_personal_name:
                i_pos = rest.find(' i ')
                if i_pos != -1:
                    rest = rest[:i_pos]

            # Title-case the name
            name = rest.title()

            # Lowercase mid-words (articles/prepositions in Catalan)
            name_words = name.split()
            for idx in range(len(name_words)):
                if name_words[idx] in CATALAN_LOWERCASE_MIDWORDS:
                    name_words[idx] = name_words[idx].lower()
                # Handle D' prefix: "D'Almenar" → "d'Almenar"
                elif name_words[idx].startswith("D'") or name_words[idx].startswith("D\u2019"):
                    name_words[idx] = "d'" + name_words[idx][2:]
            name = ' '.join(name_words)

            return f"{translated_type} {name}".strip()
        return translated_type

    # No translation found; return as title case
    return text.title()


# === Probe Logic ===

def _compute_polygon_centroid(polygon: list[tuple[float, float]]) -> tuple[float, float]:
    """Compute centroid of a polygon using the shoelace formula."""
    n = len(polygon)
    # If closed ring, skip the duplicate last point
    if n > 1 and polygon[0] == polygon[-1]:
        n -= 1

    if n == 0:
        return (0.0, 0.0)

    signed_area = 0.0
    cx = 0.0
    cy = 0.0

    for i in range(n):
        j = (i + 1) % n
        x0, y0 = polygon[i]
        x1, y1 = polygon[j]
        cross = x0 * y1 - x1 * y0
        signed_area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross

    area6 = 3.0 * signed_area  # 6A / 2 = 3A (signed_area is 2A)
    if abs(area6) < 1e-10:
        # Degenerate polygon — fallback to simple average
        return (
            sum(polygon[i][0] for i in range(n)) / n,
            sum(polygon[i][1] for i in range(n)) / n,
        )

    return (cx / area6, cy / area6)


def _classify_edges_by_direction(
    polygon: list[tuple[float, float]],
) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """
    Classify polygon edges by cardinal direction based on outward normal.

    For each cardinal direction (north, south, east, west), finds the most
    representative edge (longest projection) and returns its midpoint and
    outward unit normal vector.

    Returns:
        Dict mapping direction name to (midpoint, normal_unit_vector).
        midpoint and normal are both (x, y) tuples.
    """
    centroid = _compute_polygon_centroid(polygon)
    n = len(polygon)
    # Handle closed ring
    closed = n > 1 and polygon[0] == polygon[-1]
    num_edges = (n - 1) if closed else n

    # Track best edge per direction: {direction: (projection, midpoint, normal)}
    best: dict[str, tuple[float, tuple[float, float], tuple[float, float]]] = {}

    for i in range(num_edges):
        j = (i + 1) % n
        x1, y1 = polygon[i]
        x2, y2 = polygon[j]

        dx = x2 - x1
        dy = y2 - y1
        edge_len = math.sqrt(dx * dx + dy * dy)
        if edge_len < 0.01:
            continue

        # Edge midpoint
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0

        # Two possible perpendiculars: (-dy, dx) and (dy, -dx)
        # Pick the one pointing away from centroid
        to_centroid_x = centroid[0] - mx
        to_centroid_y = centroid[1] - my

        nx_a, ny_a = -dy, dx
        dot = nx_a * to_centroid_x + ny_a * to_centroid_y
        if dot > 0:
            # This normal points toward centroid, use the other one
            nx_a, ny_a = dy, -dx

        # Normalize
        nx_a /= edge_len
        ny_a /= edge_len

        # Classify by dominant component
        if abs(ny_a) > abs(nx_a):
            direction = 'north' if ny_a > 0 else 'south'
            projection = edge_len * abs(ny_a)
        else:
            direction = 'east' if nx_a > 0 else 'west'
            projection = edge_len * abs(nx_a)

        if direction not in best or projection > best[direction][0]:
            best[direction] = (projection, (mx, my), (nx_a, ny_a))

    return {d: (mid, nrm) for d, (_, mid, nrm) in best.items()}


def _probe_from_edge(
    midpoint: tuple[float, float],
    normal: tuple[float, float],
    our_ref: str,
    municipality: str | None = None,
    max_distance: float = 30.0,
    step: float = 2.0,
) -> str:
    """
    Probe outward from a polygon edge midpoint to find what is adjacent.

    Similar to _probe_direction but starts from the actual edge midpoint
    and follows the outward normal vector, giving much better accuracy
    for irregular parcels.
    """
    crossed_street = False

    # Start just outside the parcel boundary (1m along the normal)
    start_offset = 1.0
    num_probes = int((max_distance - start_offset) / step) + 1

    for i in range(num_probes):
        distance = start_offset + i * step
        probe_x = midpoint[0] + normal[0] * distance
        probe_y = midpoint[1] + normal[1] * distance

        logger.debug(
            f"Edge probe at distance {distance:.1f}m -> "
            f"({probe_x:.2f}, {probe_y:.2f})"
        )

        try:
            ref, ldt = _query_ref_by_coords(probe_x, probe_y)
        except CadastreError as e:
            logger.warning(f"Edge probe failed at ({probe_x}, {probe_y}): {e}")
            return "desconegut"

        if ref is None:
            logger.debug(f"Street detected at distance {distance:.1f}m")
            crossed_street = True
            continue

        if ref[:14] == our_ref[:14]:
            logger.debug(f"Still on our parcel at distance {distance:.1f}m")
            continue

        # Found a different parcel
        if crossed_street:
            if ldt:
                street = _translate_street_name(ldt, municipality=municipality)
                if street:
                    logger.debug(f"Street name from neighbor LDT: {street}")
                    return street
            return "via pública"

        return _describe_neighbor(ref)

    if crossed_street:
        return "via pública"

    logger.warning(
        f"Could not exit parcel after {num_probes} edge probes"
    )
    return "desconegut"


def _probe_direction(
    utm_x: float,
    utm_y: float,
    our_ref: str,
    dx: int,
    dy: int,
    superficie: float,
    municipality: str | None = None,
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
        municipality: Optional municipality name for street name cleaning

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
                street = _translate_street_name(ldt, municipality=municipality)
                if street:
                    logger.debug(f"Street name from neighbor LDT: {street}")
                    return street
            return "via pública"

        # Direct neighbor (no street in between)
        return _describe_neighbor(ref)

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
    municipality: str | None = None,
    rc14: str | None = None,
) -> dict[str, str]:
    """
    Detect adjacent parcels and streets around a cadastral parcel.

    Args:
        utm_x: Parcel centroid UTM X (EPSG:25831)
        utm_y: Parcel centroid UTM Y (EPSG:25831)
        superficie: Parcel area in m2 (used to calculate probe distance)
        use_cache: Whether to use cached results (default True)
        municipality: Optional municipality name for street name cleaning
        rc14: Optional cadastral reference (14 chars) for geometry-based probing

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

    # Fase 1: Try geometry-based probing if rc14 is available
    polygon = None
    if rc14:
        try:
            polygon = get_parcel_geometry_utm(rc14[:14])
            if polygon and len(polygon) >= 3:
                logger.info(
                    f"Using geometry-based probing ({len(polygon)} vertices)"
                )
            else:
                logger.warning(
                    f"Polygon too small ({len(polygon) if polygon else 0} vertices), "
                    "falling back to centroid-based probing"
                )
                polygon = None
        except CadastreError as e:
            logger.warning(
                f"Could not get parcel geometry for {rc14[:14]}: {e}. "
                "Falling back to centroid-based probing"
            )
            polygon = None

    result: dict[str, str] = {}

    if polygon:
        # Geometry-based probing: use actual edge midpoints and outward normals
        edge_info = _classify_edges_by_direction(polygon)
        for direction in ('north', 'south', 'east', 'west'):
            if direction in edge_info:
                midpoint, normal = edge_info[direction]
                logger.info(
                    f"Probing {direction} from edge midpoint "
                    f"({midpoint[0]:.1f}, {midpoint[1]:.1f})..."
                )
                result[direction] = _probe_from_edge(
                    midpoint, normal, our_ref, municipality=municipality,
                )
            else:
                logger.warning(
                    f"No edge found for {direction}, using centroid fallback"
                )
                dx, dy = DIRECTIONS[direction]
                result[direction] = _probe_direction(
                    utm_x, utm_y, our_ref, dx, dy, superficie,
                    municipality=municipality,
                )
            logger.info(f"  {direction}: {result[direction]}")
    else:
        # Centroid-based probing (original method)
        logger.info("Using centroid-based probing")
        for direction, (dx, dy) in DIRECTIONS.items():
            logger.info(f"Probing {direction}...")
            result[direction] = _probe_direction(
                utm_x, utm_y, our_ref, dx, dy, superficie,
                municipality=municipality,
            )
            logger.info(f"  {direction}: {result[direction]}")

    # Cache the result
    if use_cache:
        _save_to_cache(utm_x, utm_y, result)

    return result


# === Caching Functions ===

def _get_cache_key(utm_x: float, utm_y: float) -> str:
    """Generate cache key from coordinates."""
    key_str = f"v2_adj_{round(utm_x)}_{round(utm_y)}"
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


# === Public Wrappers ===

def get_cadastral_reference(utm_x: float, utm_y: float) -> tuple[str | None, str | None]:
    """
    Get cadastral reference at given UTM coordinates.

    Args:
        utm_x: UTM X coordinate (EPSG:25831)
        utm_y: UTM Y coordinate (EPSG:25831)

    Returns:
        Tuple of (cadastral_reference, ldt_address).
        cadastral_reference is None if the point falls on a street or error.
    """
    return _query_ref_by_coords(utm_x, utm_y)


# === Parcel Geometry via INSPIRE WFS ===

def get_parcel_geometry_utm(rc14: str) -> list[tuple[float, float]]:
    """
    Get parcel polygon geometry in EPSG:25831 from Cadastre INSPIRE WFS.

    Args:
        rc14: First 14 characters of cadastral reference

    Returns:
        List of (x, y) UTM coordinate tuples forming the parcel polygon

    Raises:
        CadastreConnectionError: If WFS request fails
        CadastreParseError: If geometry cannot be parsed
        CadastreNoDataError: If no geometry found for the reference
    """
    url = (
        f"{CADASTRE_WFS_URL}"
        f"?service=WFS&version=2.0.0&request=GetFeature"
        f"&StoredQuery_id=GetParcel&REFCAT={rc14}&srsname=EPSG:25831"
    )

    logger.debug(f"Querying Cadastre WFS for parcel geometry: {url}")

    response_text = _fetch_xml(url)

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as e:
        raise CadastreParseError(f"Invalid XML from Cadastre WFS: {e}")

    # Find posList element (contains space-separated coordinate pairs)
    pos_list_elems = _find_all_elements(root, "posList")
    if not pos_list_elems:
        raise CadastreNoDataError(f"No geometry found for parcel {rc14}")

    pos_text = pos_list_elems[0].text
    if not pos_text or not pos_text.strip():
        raise CadastreNoDataError(f"Empty geometry for parcel {rc14}")

    # Parse space-separated values as (x, y) pairs
    values = pos_text.strip().split()
    if len(values) < 4 or len(values) % 2 != 0:
        raise CadastreParseError(
            f"Invalid posList format for parcel {rc14}: {len(values)} values"
        )

    polygon: list[tuple[float, float]] = []
    for i in range(0, len(values), 2):
        try:
            x = float(values[i])
            y = float(values[i + 1])
            # INSPIRE WFS 2.0 with EPSG:25831 may return (northing, easting)
            # Detect and swap if needed
            if x > 1_000_000 and y < 1_000_000:
                x, y = y, x
            polygon.append((x, y))
        except ValueError as e:
            raise CadastreParseError(f"Invalid coordinate value in posList: {e}")

    logger.info(f"Parcel {rc14} geometry: {len(polygon)} vertices")
    return polygon


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
