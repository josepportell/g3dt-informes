#!/usr/bin/env python3
"""
UTM Coordinate Geocoding Fallback

When a project has no COORDENADES.txt (no GPS from fieldwork), derives
approximate UTM coordinates from the project street address using:
1. Cadastre Callejero address lookup (primary — 2 API calls, fast)
2. Nominatim + Cadastre grid search (fallback — slow, 290+ probes)
3. Cadastre INSPIRE WFS for parcel geometry in EPSG:25831
4. ICGC MDT for elevations

Author: Eficients.cat
Date: 2026-02-27
"""

from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
import math
import os
import re
import socket
import tempfile
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ['geocode_project', 'GeocodeError', 'cadastre_address_lookup', 'cadastre_rc_to_utm']


# === Configuration ===

CACHE_DIR = Path.home() / ".g3dt" / "cache" / "geocode"
CACHE_TTL_DAYS = 90
REQUEST_TIMEOUT_SECONDS = 15
USER_AGENT = "G3DT-Automation/1.0 (Eficients.cat; geotechnical report generation)"

# Catalunya UTM coordinate bounds (EPSG:25831)
CATALUNYA_UTM_X_MIN = 260000
CATALUNYA_UTM_X_MAX = 530000
CATALUNYA_UTM_Y_MIN = 4480000
CATALUNYA_UTM_Y_MAX = 4750000

# Spanish peninsular UTM bounds (zones 29-31, covers all mainland Spain)
SPAIN_UTM_X_MIN = 100000
SPAIN_UTM_X_MAX = 800000
SPAIN_UTM_Y_MIN = 4050000
SPAIN_UTM_Y_MAX = 4850000


# Cadastre API endpoints
CADASTRE_URL = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCoordenadas.asmx"
CADASTRE_CALLEJERO_URL = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx"
CADASTRE_WFS_URL = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"


# === Exception Hierarchy ===

class GeocodeError(Exception):
    """Base exception for geocoding errors."""
    pass


class GeocodeConnectionError(GeocodeError):
    """Failed to connect to geocoding service."""
    pass


class GeocodeParseError(GeocodeError):
    """Failed to parse geocoding response."""
    pass


class GeocodeNoDataError(GeocodeError):
    """No geocoding data found."""
    pass


# === HTTP Fetch with Retry ===

def _fetch_url(url: str, expect_json: bool = False) -> str:
    """
    Fetch URL response with retry logic.

    Args:
        url: Full URL
        expect_json: If True, sets Accept header for JSON

    Returns:
        Response text (UTF-8 decoded)

    Raises:
        GeocodeConnectionError: If all retry attempts fail
    """
    max_attempts = 3
    last_error: GeocodeConnectionError | None = None

    for attempt in range(max_attempts):
        try:
            headers = {'User-Agent': USER_AGENT}
            if expect_json:
                headers['Accept'] = 'application/json'
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read().decode('utf-8')
        except urllib.error.URLError as e:
            last_error = GeocodeConnectionError(f"Failed to connect: {e}")
        except (TimeoutError, socket.timeout) as e:
            last_error = GeocodeConnectionError(f"Request timed out: {e}")

        if attempt < max_attempts - 1:
            delay = 2 ** attempt
            logger.debug(f"Request attempt {attempt + 1} failed, retrying in {delay}s...")
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


# === WGS84 to UTM Zone 31N Conversion ===

def _wgs84_to_utm(lat: float, lon: float) -> tuple[float, float, int]:
    """
    Convert WGS84 lat/lon to UTM, auto-detecting zone 30 or 31.

    Zone 30: lon < 0 (western Spain: Huesca, Madrid, etc.) — EPSG:25830
    Zone 31: lon >= 0 (eastern Spain: Catalunya, etc.) — EPSG:25831

    Returns:
        Tuple of (utm_x, utm_y, zone)
    """
    zone = 31 if lon >= 0 else 30
    lon0_deg = 3.0 if zone == 31 else -3.0
    x, y = _wgs84_to_utm_zone(lat, lon, lon0_deg)
    return x, y, zone


def _wgs84_to_utm31n(lat: float, lon: float) -> tuple[float, float]:
    """
    Convert WGS84 lat/lon to UTM zone 31N (EPSG:25831).
    Kept for backward compatibility. Use _wgs84_to_utm() for multi-zone support.
    """
    x, y = _wgs84_to_utm_zone(lat, lon, 3.0)
    return x, y


def _wgs84_to_utm_zone(lat: float, lon: float, lon0_deg: float) -> tuple[float, float]:
    """
    Convert WGS84 lat/lon to UTM using a given central meridian.

    Standard UTM projection (Snyder series to 4th order), sub-meter accuracy
    for the coordinate conversion itself. Overall geocoding accuracy depends
    on the input lat/lon source (Nominatim: ~50-200m typical).

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees
        lon0_deg: Central meridian in degrees (3.0 for zone 31, -3.0 for zone 30)

    Returns:
        Tuple of (utm_x, utm_y)
    """
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lon0 = math.radians(lon0_deg)

    a = 6378137.0  # WGS84 semi-major
    f = 1 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1 - e2)

    N = a / math.sqrt(1 - e2 * math.sin(lat_rad) ** 2)
    T = math.tan(lat_rad) ** 2
    C = e_prime2 * math.cos(lat_rad) ** 2
    A = (lon_rad - lon0) * math.cos(lat_rad)

    M = a * (
        (1 - e2 / 4 - 3 * e2 ** 2 / 64) * lat_rad
        - (3 * e2 / 8 + 3 * e2 ** 2 / 32) * math.sin(2 * lat_rad)
        + (15 * e2 ** 2 / 256) * math.sin(4 * lat_rad)
    )

    x = 500000 + 0.9996 * N * (A + (1 - T + C) * A ** 3 / 6)
    y = 0.9996 * (M + N * math.tan(lat_rad) * (A ** 2 / 2 + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24))

    return x, y


# === Cadastre Address Lookup (Primary Path) ===

_STREET_TYPE_MAP = {
    'carrer': 'CL', 'calle': 'CL', 'c/': 'CL', 'c.': 'CL',
    'avinguda': 'AV', 'avenida': 'AV', 'av.': 'AV', 'av': 'AV',
    'plaça': 'PZ', 'plaza': 'PZ', 'pl.': 'PZ', 'pl': 'PZ',
    'passeig': 'PS', 'paseo': 'PS', 'pg.': 'PS', 'pg': 'PS',
    'carretera': 'CR', 'ctra.': 'CR', 'ctra': 'CR',
    'travessia': 'TR', 'travesía': 'TR',
    'camí': 'CM', 'camino': 'CM',
    'ronda': 'RD',
    'rambla': 'RB',
    'partida': 'PD',
}

# Pre-sorted: longer prefixes first so "ctra." matches before "c."
_STREET_TYPE_PREFIXES = sorted(_STREET_TYPE_MAP.keys(), key=len, reverse=True)


def _parse_address(address: str) -> tuple[str, str, str]:
    """
    Parse a street address into components for the Cadastre Callejero API.

    Examples:
        "Carrer Mestre Ramon Ortiz, 5" -> ("CL", "Mestre Ramon Ortiz", "5")
        "Av. Catalunya, 12"            -> ("AV", "Catalunya", "12")
        "Partida Fontanals"            -> ("PD", "Fontanals", "")

    Args:
        address: Street address string

    Returns:
        Tuple of (sigla, calle, numero)
    """
    # Extract house number: look for comma + number or trailing number
    numero = ""
    addr_part = address.strip()
    m = re.search(r',\s*(\d+[A-Za-z]?)\s*$', addr_part)
    if m:
        numero = m.group(1)
        addr_part = addr_part[:m.start()].strip()
    else:
        m = re.search(r'\s+(\d+[A-Za-z]?)\s*$', addr_part)
        if m:
            numero = m.group(1)
            addr_part = addr_part[:m.start()].strip()

    # Match street type at the beginning
    sigla = ""
    calle = addr_part
    addr_lower = addr_part.lower()

    for prefix in _STREET_TYPE_PREFIXES:
        if addr_lower.startswith(prefix):
            # Check that prefix is followed by a word boundary (space or end)
            rest = addr_part[len(prefix):]
            if rest == "" or rest[0] in (' ', '.', '/'):
                sigla = _STREET_TYPE_MAP[prefix]
                calle = rest.lstrip(' ./')
                break

    return sigla, calle, numero


# === Progressive Cadastre Resolution (fuzzy municipality + street) ===

def _consulta_municipio(province: str, municipality_hint: str) -> tuple[str, str, str] | None:
    """
    Fuzzy-resolve a municipality name via Cadastre ConsultaMunicipio.

    Args:
        province: Province name (e.g., "LLEIDA", "HUESCA")
        municipality_hint: Partial or approximate municipality name

    Returns:
        Tuple of (official_name, cp, cm) or None if not found.
        cp = INE province code, cm = INE municipality code.
    """
    url = (
        f"{CADASTRE_CALLEJERO_URL}/ConsultaMunicipio"
        f"?Provincia={urllib.parse.quote(province)}"
        f"&Municipio={urllib.parse.quote(municipality_hint)}"
    )
    logger.debug(f"ConsultaMunicipio URL: {url}")

    try:
        response_text = _fetch_url(url)
    except GeocodeConnectionError as e:
        logger.warning(f"ConsultaMunicipio connection failed: {e}")
        return None
    finally:
        time.sleep(0.3)

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as e:
        logger.warning(f"ConsultaMunicipio XML parse error: {e}")
        return None

    # Find all <muni> elements
    muni_elems = _find_all_elements(root, "muni")
    if not muni_elems:
        logger.debug(f"ConsultaMunicipio: no muni elements for '{municipality_hint}' in '{province}'")
        return None

    def _strip_accents(s: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

    hint_norm = _strip_accents(municipality_hint.upper().strip())
    hint_words = set(hint_norm.split())
    candidates: list[tuple[int, int, str, str, str]] = []

    for muni_elem in muni_elems:
        nm_elem = _find_element(muni_elem, "nm")
        if nm_elem is None or not nm_elem.text:
            continue
        official_name = nm_elem.text.strip()

        # Extract loine/cp and loine/cm
        cp_elem = _find_element(muni_elem, "loine/cp")
        cm_elem = _find_element(muni_elem, "loine/cm")
        cp = cp_elem.text.strip() if cp_elem is not None and cp_elem.text else ""
        cm = cm_elem.text.strip() if cm_elem is not None and cm_elem.text else ""

        name_norm = _strip_accents(official_name.upper())

        # Score candidates (accent-insensitive comparison)
        if name_norm == hint_norm:
            score = 100
        elif name_norm.startswith(hint_norm):
            score = 80
        else:
            candidate_words = set(name_norm.split())
            if hint_words and hint_words.issubset(candidate_words):
                score = 60
            elif hint_words & candidate_words:
                score = 40
            else:
                continue

        # Store: (-score for desc sort, len for asc tiebreak, name, cp, cm)
        candidates.append((-score, len(official_name), official_name, cp, cm))

    if not candidates:
        logger.debug(f"ConsultaMunicipio: no match for '{municipality_hint}' in '{province}'")
        return None

    candidates.sort()
    best = candidates[0]
    return best[2], best[3], best[4]


def _consulta_via(province: str, municipality: str, street_hint: str) -> tuple[str, str, str] | None:
    """
    Fuzzy-resolve a street name via Cadastre ConsultaVia.

    Args:
        province: Province name
        municipality: Official municipality name (from _consulta_municipio)
        street_hint: Partial street name (e.g., "Ferraz", "Mestre Ramon")

    Returns:
        Tuple of (official_street_name, tipo_via, cv) or None.
        tipo_via = street type code (CL, AV, etc.), cv = street code.
    """
    # Expand common Spanish abbreviations before searching
    _ABBREVIATIONS = {
        "sta.": "Santa", "sta": "Santa", "sto.": "Santo", "sto": "Santo",
        "gral.": "General", "gral": "General",
        "dr.": "Doctor", "dr": "Doctor",
        "av.": "Avenida", "avda.": "Avenida",
        "ctra.": "Carretera",
        "mn.": "Mossen", "mn": "Mossen",
    }
    expanded_words = []
    for w in street_hint.strip().split():
        expanded_words.append(_ABBREVIATIONS.get(w.lower(), w))
    expanded_hint = " ".join(expanded_words)

    # Try progressively shorter hints if no results
    hint_words = expanded_hint.split()
    attempts = [expanded_hint]
    if expanded_hint != street_hint.strip():
        attempts.insert(0, street_hint.strip())  # try original first
    for i in range(len(hint_words) - 1, 0, -1):
        attempts.append(" ".join(hint_words[:i]))

    for current_hint in attempts:
        result = _consulta_via_single(province, municipality, current_hint)
        if result is not None:
            return result

    return None


def _consulta_via_single(
    province: str, municipality: str, street_hint: str
) -> tuple[str, str, str] | None:
    """Single ConsultaVia API call with fuzzy matching."""
    url = (
        f"{CADASTRE_CALLEJERO_URL}/ConsultaVia"
        f"?Provincia={urllib.parse.quote(province)}"
        f"&Municipio={urllib.parse.quote(municipality)}"
        f"&TipoVia="
        f"&NombreVia={urllib.parse.quote(street_hint)}"
    )
    logger.debug(f"ConsultaVia URL: {url}")

    try:
        response_text = _fetch_url(url)
    except GeocodeConnectionError as e:
        logger.warning(f"ConsultaVia connection failed: {e}")
        return None
    finally:
        time.sleep(0.3)

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as e:
        logger.warning(f"ConsultaVia XML parse error: {e}")
        return None

    # Check for errors
    for err_elem in _find_all_elements(root, "err"):
        des_elem = _find_element(err_elem, "des")
        if des_elem is not None and des_elem.text:
            logger.debug(f"ConsultaVia error: {des_elem.text}")
            return None

    # Find street candidates — look for <dir> or <calle> elements
    def _strip_accents(s: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

    hint_norm = _strip_accents(street_hint.upper().strip())
    hint_words = set(hint_norm.split())
    # Filter out short/common words for overlap scoring
    significant_words = {w for w in hint_words if len(w) > 2}

    candidates: list[tuple[int, int, str, str, str]] = []

    # Try multiple element structures the API might return
    for tag in ("dir", "calle"):
        for elem in _find_all_elements(root, tag):
            nv_elem = _find_element(elem, "nv")
            tv_elem = _find_element(elem, "tv")
            cv_elem = _find_element(elem, "cv")

            if nv_elem is None or not nv_elem.text:
                continue

            street_name = nv_elem.text.strip()
            tipo_via = tv_elem.text.strip() if tv_elem is not None and tv_elem.text else ""
            cv = cv_elem.text.strip() if cv_elem is not None and cv_elem.text else ""

            name_norm = _strip_accents(street_name.upper())
            candidate_words = set(name_norm.split())
            significant_candidate = {w for w in candidate_words if len(w) > 2}

            # Score (accent-insensitive)
            if hint_words and hint_words.issubset(candidate_words):
                score = 80
            elif hint_norm in name_norm:
                score = 60
            elif significant_words and significant_words & significant_candidate:
                score = 40
            else:
                continue

            candidates.append((-score, len(street_name), street_name, tipo_via, cv))

    if not candidates:
        logger.debug(f"ConsultaVia: no match for '{street_hint}' in {municipality}")
        return None

    candidates.sort()
    best = candidates[0]
    return best[2], best[3], best[4]


def _pick_nearest_rc_from_numerero(root: ET.Element, house_number: str) -> str | None:
    """Extract RC from the nearest house number in a DNPLOC <numerero> block.

    When the Cadastre API returns error 43 (number doesn't exist), it may
    include a <numerero> block with nearby house numbers and their RCs.
    This picks the one closest to the requested number.

    Note: <nump> structure is <nump> -> <pc> -> <pc1>,<pc2> and <nump> -> <num> -> <pnp>,
    so we use _find_element with path notation (e.g. "pc/pc1") for nested children.
    """
    nump_elems = _find_all_elements(root, "nump")
    if not nump_elems:
        return None
    try:
        target = int(house_number) if house_number else 1
    except ValueError:
        target = 1
    best_rc = None
    best_dist = float("inf")
    for nump in nump_elems:
        pnp_elem = _find_element(nump, "num/pnp")
        pc1_elem = _find_element(nump, "pc/pc1")
        pc2_elem = _find_element(nump, "pc/pc2")
        if pnp_elem is not None and pnp_elem.text and pc1_elem is not None and pc1_elem.text:
            try:
                num_val = int(pnp_elem.text.strip())
            except ValueError:
                continue
            dist = abs(num_val - target)
            if dist < best_dist:
                best_dist = dist
                pc1 = pc1_elem.text.strip()
                pc2 = pc2_elem.text.strip() if pc2_elem is not None and pc2_elem.text else ""
                best_rc = pc1 + pc2
    return best_rc


def cadastre_progressive_lookup(
    street_name: str,
    house_number: str,
    municipality_hint: str,
    province: str,
) -> dict | None:
    """
    Progressive Cadastre resolution: fuzzy municipality -> fuzzy street -> DNPLOC.

    More robust than direct Consulta_DNPLOC because it uses Cadastre's own
    fuzzy search to resolve municipality and street names before lookup.

    Returns: {"rc": str, "xcen": float|None, "ycen": float|None} or None.
    """
    # Step 1: Resolve municipality
    muni_result = _consulta_municipio(province, municipality_hint)
    if muni_result is None:
        logger.warning(f"Progressive cadastre: municipality '{municipality_hint}' not found in {province}")
        return None
    official_muni, cp, cm = muni_result
    logger.info(f"Progressive cadastre: municipality '{municipality_hint}' -> '{official_muni}'")

    # Step 2: Resolve street
    via_result = _consulta_via(province, official_muni, street_name)
    if via_result is None:
        logger.warning(f"Progressive cadastre: street '{street_name}' not found in {official_muni}")
        return None
    official_street, tipo_via, cv = via_result
    logger.info(f"Progressive cadastre: street '{street_name}' -> '{official_street}' ({tipo_via})")

    # Step 3: DNPLOC with resolved names
    params = (
        f"?Provincia={urllib.parse.quote(province)}"
        f"&Municipio={urllib.parse.quote(official_muni)}"
        f"&Sigla={urllib.parse.quote(tipo_via)}"
        f"&Calle={urllib.parse.quote(official_street)}"
        f"&Numero={urllib.parse.quote(house_number)}"
        f"&Bloque=&Escalera=&Planta=&Puerta="
    )
    url = f"{CADASTRE_CALLEJERO_URL}/Consulta_DNPLOC{params}"
    logger.debug(f"Progressive DNPLOC URL: {url}")

    try:
        response_text = _fetch_url(url)
    except GeocodeConnectionError as e:
        logger.warning(f"Progressive DNPLOC connection failed: {e}")
        return None

    time.sleep(0.3)

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as e:
        logger.warning(f"Progressive DNPLOC XML parse error: {e}")
        return None

    # Check for errors — but try to recover from common ones
    error_codes = set()
    for err_elem in _find_all_elements(root, "err"):
        cod_elem = _find_element(err_elem, "cod")
        des_elem = _find_element(err_elem, "des")
        cod = cod_elem.text.strip() if cod_elem is not None and cod_elem.text else ""
        des = des_elem.text.strip() if des_elem is not None and des_elem.text else ""
        error_codes.add(cod)
        logger.debug(f"Progressive DNPLOC error {cod}: {des}")

    # Error 43 = "number doesn't exist" — API may return nearby numbers in <numerero>
    # Error 41 = "number is required" — empty house_number
    if "43" in error_codes:
        # Try to pick nearest house number from <numerero> block
        rc = _pick_nearest_rc_from_numerero(root, house_number)
        if rc:
            logger.info(f"Progressive cadastre: nearest number fallback -> RC {rc}")
            xcen: float | None = None
            ycen: float | None = None
            utm_coords = cadastre_rc_to_utm(rc)
            if utm_coords:
                xcen, ycen = utm_coords
            return {"rc": rc, "xcen": xcen, "ycen": ycen}
        logger.warning("Progressive cadastre: number not found and no nearby numbers")
        return None

    if "41" in error_codes and not house_number.strip():
        # Empty house number — retry DNPLOC with "1" as fallback
        logger.info("Progressive cadastre: empty number, retrying DNPLOC with '1'")
        time.sleep(0.3)
        retry_params = (
            f"?Provincia={urllib.parse.quote(province)}"
            f"&Municipio={urllib.parse.quote(official_muni)}"
            f"&Sigla={urllib.parse.quote(tipo_via)}"
            f"&Calle={urllib.parse.quote(official_street)}"
            f"&Numero=1"
            f"&Bloque=&Escalera=&Planta=&Puerta="
        )
        retry_url = f"{CADASTRE_CALLEJERO_URL}/Consulta_DNPLOC{retry_params}"
        try:
            retry_text = _fetch_url(retry_url)
        except GeocodeConnectionError as e:
            logger.warning(f"Progressive DNPLOC retry connection failed: {e}")
            return None
        try:
            retry_root = ET.fromstring(retry_text)
        except ET.ParseError:
            return None
        # On retry, accept either a direct hit or pick from nearby numbers
        retry_err_codes = set()
        for err_elem in _find_all_elements(retry_root, "err"):
            cod_elem = _find_element(err_elem, "cod")
            if cod_elem is not None and cod_elem.text:
                retry_err_codes.add(cod_elem.text.strip())
        if "43" in retry_err_codes:
            # Number 1 doesn't exist — pick first available from nearby
            rc = _pick_nearest_rc_from_numerero(retry_root, "1")
            if rc:
                logger.info(f"Progressive cadastre: retry nearest number -> RC {rc}")
                xcen_r: float | None = None
                ycen_r: float | None = None
                utm_coords = cadastre_rc_to_utm(rc)
                if utm_coords:
                    xcen_r, ycen_r = utm_coords
                return {"rc": rc, "xcen": xcen_r, "ycen": ycen_r}
            return None
        if not retry_err_codes:
            # Direct hit with number=1 — use retry response for RC extraction
            root = retry_root
            error_codes = set()  # Clear errors so we fall through to RC extraction
        else:
            return None

    if error_codes:
        logger.warning(f"Progressive cadastre: unrecoverable errors {error_codes}")
        return None

    # Extract RC (pc1 + pc2)
    pc1_elems = _find_all_elements(root, "pc1")
    pc2_elems = _find_all_elements(root, "pc2")
    if not pc1_elems or not pc1_elems[0].text:
        logger.warning("Progressive cadastre: no pc1 in DNPLOC response")
        return None

    pc1 = pc1_elems[0].text.strip()
    pc2 = pc2_elems[0].text.strip() if pc2_elems and pc2_elems[0].text else ""
    rc = pc1 + pc2
    logger.info(f"Progressive cadastre: found RC {rc}")

    # Step 4: Get UTM coordinates via existing helper
    xcen: float | None = None
    ycen: float | None = None
    utm_coords = cadastre_rc_to_utm(rc)
    if utm_coords:
        xcen, ycen = utm_coords

    return {"rc": rc, "xcen": xcen, "ycen": ycen}


_CATALAN_PROVINCES = ["LLEIDA", "BARCELONA", "GIRONA", "TARRAGONA"]


def cadastre_address_lookup(
    address: str,
    municipality: str,
    province: str = "",
) -> dict | None:
    """
    Look up a cadastral reference by street address using the Cadastre
    Callejero API (Consulta_DNPLOC).

    This is the fast path: 1-4 API calls to get the cadastral reference
    directly from the street address, vs 290+ grid probes.

    If province is not provided, tries all 4 Catalan provinces.

    Args:
        address: Street address (e.g. "Carrer Mestre Ramon Ortiz, 5")
        municipality: Municipality name (e.g. "Bell-Lloc d'Urgell")
        province: Province name (e.g. "LLEIDA"). If empty, auto-detected.

    Returns:
        Dict with keys: rc, xcen, ycen. Or None if lookup fails.
    """
    sigla, calle, numero = _parse_address(address)
    logger.debug(
        f"Cadastre address lookup: sigla={sigla!r} calle={calle!r} "
        f"numero={numero!r} municipality={municipality!r}"
    )

    # Province is required by the API; try provided, then Catalan, then all Spanish
    if province:
        provinces = [province.upper()]
    else:
        provinces = list(_CATALAN_PROVINCES)

    def _query_dnploc(prov: str, num: str) -> dict | None:
        # API requires uppercase municipality/province and all address fields
        params = (
            f"?Provincia={urllib.parse.quote(prov)}"
            f"&Municipio={urllib.parse.quote(municipality.upper())}"
            f"&Sigla={urllib.parse.quote(sigla)}"
            f"&Calle={urllib.parse.quote(calle.upper())}"
            f"&Numero={urllib.parse.quote(num)}"
            f"&Bloque=&Escalera=&Planta=&Puerta="
        )
        url = f"{CADASTRE_CALLEJERO_URL}/Consulta_DNPLOC{params}"
        logger.debug(f"Consulta_DNPLOC URL: {url}")

        try:
            response_text = _fetch_url(url)
        except GeocodeConnectionError as e:
            logger.warning(f"Cadastre Callejero connection failed: {e}")
            return None

        try:
            root = ET.fromstring(response_text)
        except ET.ParseError as e:
            logger.warning(f"Cadastre Callejero XML parse error: {e}")
            return None

        # Check for error responses — any error means lookup failed
        for err_elem in _find_all_elements(root, "err"):
            err_text = ""
            des_elem = _find_element(err_elem, "des")
            if des_elem is not None and des_elem.text:
                err_text = des_elem.text
            elif err_elem.text:
                err_text = err_elem.text
            if err_text:
                logger.debug(f"Cadastre Callejero error: {err_text}")
                return None

        for lerr_elem in _find_all_elements(root, "lerr"):
            for err_child in _find_all_elements(lerr_elem, "err"):
                des_elem = _find_element(err_child, "des")
                err_text = ""
                if des_elem is not None and des_elem.text:
                    err_text = des_elem.text
                elif err_child.text:
                    err_text = err_child.text
                if err_text:
                    logger.debug(f"Cadastre Callejero error: {err_text}")
                    return None

        # Extract cadastral reference from first bi element
        bi_elems = _find_all_elements(root, "bi")
        if not bi_elems:
            # Try finding pc1/pc2 directly
            pc1_elems = _find_all_elements(root, "pc1")
            pc2_elems = _find_all_elements(root, "pc2")
            if pc1_elems and pc1_elems[0].text:
                pc1 = pc1_elems[0].text.strip()
                pc2 = pc2_elems[0].text.strip() if pc2_elems and pc2_elems[0].text else ""
                rc = pc1 + pc2
            else:
                logger.debug("Cadastre Callejero: no bi/pc elements found")
                return None
        else:
            bi = bi_elems[0]
            pc1_elem = _find_element(bi, "idbi/rc/pc1")
            if pc1_elem is None:
                pc1_elems = _find_all_elements(bi, "pc1")
                pc1_elem = pc1_elems[0] if pc1_elems else None
            pc2_elem = _find_element(bi, "idbi/rc/pc2")
            if pc2_elem is None:
                pc2_elems = _find_all_elements(bi, "pc2")
                pc2_elem = pc2_elems[0] if pc2_elems else None

            if pc1_elem is None or not pc1_elem.text:
                logger.debug("Cadastre Callejero: no pc1 in bi element")
                return None

            pc1 = pc1_elem.text.strip()
            pc2 = pc2_elem.text.strip() if pc2_elem is not None and pc2_elem.text else ""
            rc = pc1 + pc2

        # Extract coordinates if available
        xcen = ycen = None
        xcen_elems = _find_all_elements(root, "xcen")
        ycen_elems = _find_all_elements(root, "ycen")
        if xcen_elems and xcen_elems[0].text:
            try:
                xcen = float(xcen_elems[0].text.strip())
            except ValueError:
                pass
        if ycen_elems and ycen_elems[0].text:
            try:
                ycen = float(ycen_elems[0].text.strip())
            except ValueError:
                pass

        logger.info(f"Cadastre Callejero found RC={rc} (xcen={xcen}, ycen={ycen})")
        return {"rc": rc, "xcen": xcen, "ycen": ycen}

    # Try each province until we get a result
    for prov in provinces:
        # Try with house number first
        result = _query_dnploc(prov, numero)
        if result is not None:
            return result

        # If number didn't work and we had one, retry without it
        if numero:
            logger.debug(f"Retrying Cadastre Callejero without house number (prov={prov})")
            time.sleep(0.3)
            result = _query_dnploc(prov, "")
            if result is not None:
                return result

        time.sleep(0.2)

    return None


def cadastre_rc_to_utm(rc: str) -> tuple[float, float] | None:
    """
    Get UTM centroid for a cadastral reference using Consulta_CPMRC.

    Args:
        rc: Full cadastral reference

    Returns:
        Tuple of (utm_x, utm_y) in EPSG:25831, or None if lookup fails.
    """
    params = (
        f"?Provincia=&Municipio=&SRS=EPSG:25831"
        f"&RC={urllib.parse.quote(rc)}"
    )
    url = f"{CADASTRE_URL}/Consulta_CPMRC{params}"
    logger.debug(f"Consulta_CPMRC URL: {url}")

    try:
        response_text = _fetch_url(url)
    except GeocodeConnectionError as e:
        logger.warning(f"Cadastre CPMRC connection failed: {e}")
        return None

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as e:
        logger.warning(f"Cadastre CPMRC XML parse error: {e}")
        return None

    # Look for xcen/ycen under coord elements
    xcen_elem = None
    ycen_elem = None
    coord_elems = _find_all_elements(root, "coord")
    if coord_elems:
        for coord in coord_elems:
            xc = _find_element(coord, "xcen")
            yc = _find_element(coord, "ycen")
            if xc is not None and xc.text and yc is not None and yc.text:
                xcen_elem = xc
                ycen_elem = yc
                break

    # Fallback: find xcen/ycen anywhere
    if xcen_elem is None:
        xcen_elems = _find_all_elements(root, "xcen")
        ycen_elems = _find_all_elements(root, "ycen")
        if xcen_elems and xcen_elems[0].text:
            xcen_elem = xcen_elems[0]
        if ycen_elems and ycen_elems[0].text:
            ycen_elem = ycen_elems[0]

    if xcen_elem is None or ycen_elem is None:
        logger.warning(f"Cadastre CPMRC: no coordinates found for RC={rc}")
        return None

    try:
        utm_x = float(xcen_elem.text.strip())
        utm_y = float(ycen_elem.text.strip())
    except ValueError as e:
        logger.warning(f"Cadastre CPMRC: invalid coordinate values: {e}")
        return None

    logger.info(f"Cadastre CPMRC: RC={rc} -> UTM ({utm_x:.1f}, {utm_y:.1f})")
    time.sleep(0.3)
    return utm_x, utm_y


# === Nominatim Geocoding ===

def nominatim_geocode(address: str, municipality: str, province: str = "") -> tuple[float, float] | None:
    """
    Geocode an address using Nominatim (OpenStreetMap).

    Args:
        address: Street address
        municipality: Municipality name
        province: Province name (e.g. "Huesca"). If empty, uses "Spain" directly.

    Returns:
        Tuple of (lat, lon) or None if not found
    """
    if province:
        query = f"{address}, {municipality}, {province}, Spain"
    else:
        query = f"{address}, {municipality}, Catalunya, Spain"
    encoded_query = urllib.request.quote(query)
    url = (
        f"https://nominatim.openstreetmap.org/search"
        f"?q={encoded_query}&format=json&limit=1"
    )

    logger.debug(f"Nominatim query: {query}")

    try:
        response_text = _fetch_url(url, expect_json=True)
    except GeocodeConnectionError as e:
        logger.warning(f"Nominatim connection failed: {e}")
        return None

    try:
        results = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Nominatim JSON parse error: {e}")
        return None

    if not results:
        logger.warning(f"Nominatim returned no results for: {query}")
        return None

    try:
        lat = float(results[0]['lat'])
        lon = float(results[0]['lon'])
    except (KeyError, ValueError, IndexError) as e:
        logger.warning(f"Nominatim response missing lat/lon: {e}")
        return None

    logger.info(f"Nominatim geocoded '{query}' -> ({lat:.6f}, {lon:.6f})")

    # Rate limit: Nominatim requires max 1 request per second
    time.sleep(1.5)

    return lat, lon


# === Cadastre Parcel Finder ===

def cadastre_find_parcel(
    lat: float,
    lon: float,
    target_address: str,
) -> dict | None:
    """
    Find a cadastral parcel near given coordinates that matches the target address.

    Uses Cadastre RCCOOR API with EPSG:4326 and a grid search to find
    the best-matching parcel.

    Args:
        lat: Latitude (WGS84)
        lon: Longitude (WGS84)
        target_address: Target street address for matching

    Returns:
        Dict with keys: rc, address, lat, lon. Or None if not found.
    """
    target_words = set(re.findall(r'\w+', target_address.lower()))

    # Spiral search: center outward for faster match
    offsets = []
    for r in range(9):  # radius 0 to 8
        if r == 0:
            offsets.append((0, 0))
        else:
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r:  # Only the border of this ring
                        offsets.append((dx, dy))

    fallback: dict | None = None

    for dx, dy in offsets:
        probe_lon = lon + dx * 0.0002
        probe_lat = lat + dy * 0.0002

        # Cadastre API: for EPSG:4326, Coordenada_X=lon, Coordenada_Y=lat
        url = (
            f"{CADASTRE_URL}/Consulta_RCCOOR"
            f"?SRS=EPSG:4326"
            f"&Coordenada_X={probe_lon}&Coordenada_Y={probe_lat}"
        )

        try:
            response_text = _fetch_url(url)
        except GeocodeConnectionError as e:
            logger.debug(f"Cadastre probe failed at ({probe_lat}, {probe_lon}): {e}")
            time.sleep(0.05)
            continue

        try:
            root = ET.fromstring(response_text)
        except ET.ParseError:
            time.sleep(0.05)
            continue

        # Extract pc1, pc2, ldt
        pc1_elem = _find_element(root, "coordenadas/coord/pc/pc1")
        if pc1_elem is None:
            pc1_elems = _find_all_elements(root, "pc1")
            pc1_elem = pc1_elems[0] if pc1_elems else None

        if pc1_elem is None or not pc1_elem.text:
            time.sleep(0.05)
            continue

        pc2_elem = _find_element(root, "coordenadas/coord/pc/pc2")
        if pc2_elem is None:
            pc2_elems = _find_all_elements(root, "pc2")
            pc2_elem = pc2_elems[0] if pc2_elems else None

        ldt_elem = _find_element(root, "coordenadas/coord/ldt")
        if ldt_elem is None:
            ldt_elems = _find_all_elements(root, "ldt")
            ldt_elem = ldt_elems[0] if ldt_elems else None

        pc1 = pc1_elem.text.strip()
        pc2 = pc2_elem.text.strip() if pc2_elem is not None and pc2_elem.text else ""
        ldt = ldt_elem.text.strip() if ldt_elem is not None and ldt_elem.text else ""
        rc = pc1 + pc2

        result = {
            "rc": rc,
            "address": ldt,
            "lat": probe_lat,
            "lon": probe_lon,
        }

        # Store first valid RC as fallback
        if fallback is None:
            fallback = result

        # Check address match
        if ldt and target_words:
            ldt_words = set(re.findall(r'\w+', ldt.lower()))
            if ldt_words:
                overlap = len(target_words & ldt_words) / len(target_words)
                if overlap > 0.3:
                    logger.info(f"Cadastre match (score={overlap:.2f}): {rc} -> {ldt}")
                    return result

        time.sleep(0.05)

    if fallback is not None:
        logger.info(f"Cadastre fallback (no address match): {fallback['rc']} -> {fallback['address']}")
        return fallback

    logger.warning("No cadastral parcel found in grid search")
    return None


# === Cadastre Parcel Geometry ===

def get_parcel_geometry_utm(rc14: str) -> list[tuple[float, float]]:
    """
    Get parcel geometry in EPSG:25831 from Cadastre INSPIRE WFS.

    Args:
        rc14: First 14 characters of cadastral reference

    Returns:
        List of (x, y) tuples in EPSG:25831

    Raises:
        GeocodeConnectionError: If WFS request fails
        GeocodeParseError: If geometry cannot be parsed
        GeocodeNoDataError: If no geometry found
    """
    url = (
        f"{CADASTRE_WFS_URL}"
        f"?service=WFS&version=2.0.0&request=GetFeature"
        f"&StoredQuery_id=GetParcel&REFCAT={rc14}&srsname=EPSG:25831"
    )

    logger.debug(f"Querying Cadastre WFS for parcel geometry: {url}")

    response_text = _fetch_url(url)

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as e:
        raise GeocodeParseError(f"Invalid XML from Cadastre WFS: {e}")

    # Find posList element (contains space-separated coordinate pairs)
    pos_list_elems = _find_all_elements(root, "posList")
    if not pos_list_elems:
        raise GeocodeNoDataError(f"No geometry found for parcel {rc14}")

    pos_text = pos_list_elems[0].text
    if not pos_text or not pos_text.strip():
        raise GeocodeNoDataError(f"Empty geometry for parcel {rc14}")

    # Parse space-separated values as (x, y) pairs
    values = pos_text.strip().split()
    if len(values) < 4 or len(values) % 2 != 0:
        raise GeocodeParseError(
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
            raise GeocodeParseError(f"Invalid coordinate value in posList: {e}")

    logger.info(f"Parcel {rc14} geometry: {len(polygon)} vertices")
    return polygon


# === Point Distribution ===

def distribute_points(
    polygon: list[tuple[float, float]],
    point_ids: list[str],
) -> dict[str, dict[str, float]]:
    """
    Distribute investigation points within a parcel polygon.

    If 1 point: place at centroid.
    If multiple: distribute along major axis with 7-12m spacing.

    Args:
        polygon: List of (x, y) vertices in EPSG:25831
        point_ids: List of point IDs (e.g., ["P-1", "P-2", "S-1"])

    Returns:
        Dict mapping point_id to {"x": utm_x, "y": utm_y}
    """
    if not polygon or not point_ids:
        return {}

    # Calculate centroid
    n = len(polygon)
    cx = sum(p[0] for p in polygon) / n
    cy = sum(p[1] for p in polygon) / n

    if len(point_ids) == 1:
        return {point_ids[0]: {"x": cx, "y": cy}}

    # Calculate bounding box
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # Determine major axis
    dx = x_max - x_min
    dy = y_max - y_min
    inset = 2.0  # meters from edge

    num_points = len(point_ids)
    spacing = min(12.0, max(7.0, (max(dx, dy) - 2 * inset) / max(num_points - 1, 1)))

    result: dict[str, dict[str, float]] = {}
    total_span = spacing * (num_points - 1)
    start_offset = -total_span / 2

    for i, pid in enumerate(point_ids):
        offset = start_offset + i * spacing
        if dx >= dy:
            # Major axis is X
            px = cx + offset
            py = cy
            px = max(x_min + inset, min(x_max - inset, px))
        else:
            # Major axis is Y
            px = cx
            py = cy + offset
            py = max(y_min + inset, min(y_max - inset, py))
        result[pid] = {"x": px, "y": py}

    return result


# === COORDENADES.txt Generation ===

def generate_coordenades_txt(
    points: dict[str, dict],
    elevations: dict[str, float],
    output_path: Path,
) -> None:
    """
    Write COORDENADES.txt matching exact format from existing files.

    Format:
        Coordenades UTM (X);(Y);(Z);
        P-1
        314487.0 ; 4611157.0 ; 199.2

        P-2
        314497.0 ; 4611158.0 ; 199.3

    Args:
        points: Dict mapping point_id to {"x": ..., "y": ...}
        elevations: Dict mapping point_id to elevation in meters
        output_path: Where to write the file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort: P-1, P-2, ..., S-1, S-2, ...
    def sort_key(pid: str) -> tuple[str, int]:
        parts = pid.split('-', 1)
        prefix = parts[0]
        try:
            num = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            num = 0
        return (prefix, num)

    sorted_ids = sorted(points.keys(), key=sort_key)

    lines = ["Coordenades UTM (X);(Y);(Z);"]
    for pid in sorted_ids:
        pt = points[pid]
        z = elevations.get(pid, 0.0)
        lines.append(pid)
        lines.append(f"{pt['x']:.1f} ; {pt['y']:.1f} ; {z:.1f}")
        lines.append("")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    logger.info(f"Generated COORDENADES.txt at {output_path}")


# === Caching Functions ===

def _get_cache_key(address: str, municipality: str) -> str:
    """Generate cache key from address and municipality."""
    key_str = f"geocode_{address.lower().strip()}_{municipality.lower().strip()}"
    return hashlib.sha256(key_str.encode()).hexdigest()[:12]


def _get_cache_path(address: str, municipality: str) -> Path:
    """Get path to cache file."""
    cache_key = _get_cache_key(address, municipality)
    return CACHE_DIR / f"{cache_key}.json"


def _load_from_cache(address: str, municipality: str) -> dict | None:
    """
    Load geocode result from cache if available and not expired.

    Returns None if not cached or expired.
    """
    if os.environ.get("G3DT_NO_CACHE") == "1":
        return None

    cache_path = _get_cache_path(address, municipality)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cached_at = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
        if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
            logger.debug(f"Cache expired for geocode '{address}, {municipality}'")
            cache_path.unlink()
            return None

        return data['result']

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Invalid cache file {cache_path}: {e}")
        cache_path.unlink()
        return None


def _save_to_cache(address: str, municipality: str, result: dict) -> None:
    """Save geocode result to cache using atomic write."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _get_cache_path(address, municipality)

    data = {
        'cached_at': datetime.now().isoformat(),
        'query': {'address': address, 'municipality': municipality},
        'result': result,
    }

    try:
        fd, temp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Path(temp_path).rename(cache_path)
            logger.debug(f"Cached geocode result at {cache_path}")
        except Exception:
            Path(temp_path).unlink(missing_ok=True)
            raise
    except OSError as e:
        logger.warning(f"Failed to cache geocode result: {e}")


# === Main Orchestrator ===

def geocode_project(
    address: str,
    municipality: str,
    point_ids: list[str],
    output_dir: Path | None = None,
    province: str = "",
) -> dict | None:
    """
    Geocode a project address to UTM coordinates.

    Orchestrates the full pipeline:
    1. Check cache
    2. PRIMARY: Cadastre Callejero address lookup (fast, 2 API calls)
    3. FALLBACK: Nominatim + Cadastre grid search (slow, 290+ probes)
    4. Cadastre WFS -> parcel geometry in EPSG:25831
    5. Distribute investigation points within parcel
    6. Get elevations from ICGC MDT
    7. Generate COORDENADES.txt if output_dir provided
    8. Cache result

    Falls back gracefully at each step. If geometry is unavailable but
    UTM centroid is available, places all points at centroid.

    Args:
        address: Street address of the project
        municipality: Municipality name
        point_ids: List of investigation point IDs (e.g., ["P-1", "P-2", "S-1"])
        output_dir: Project folder; if provided, writes COORDENADES.txt

    Returns:
        Dict with keys: utm_x, utm_y, points, rc, source. Or None if geocoding fails.
    """
    # 1. Check cache
    cached = _load_from_cache(address, municipality)
    if cached is not None:
        logger.debug(f"Cache hit for geocode '{address}, {municipality}'")
        return cached

    # 2. PRIMARY PATH: Progressive Cadastre resolution (fuzzy municipality + street)
    rc: str | None = None
    centroid_x: float | None = None
    centroid_y: float | None = None
    utm_zone: int = 31  # default; overwritten by _wgs84_to_utm if conversion happens
    source = "geocode:cadastre_progressive"

    # Extract components from address for progressive lookup
    sigla, parsed_street, parsed_number = _parse_address(address)

    cadastre_result = cadastre_progressive_lookup(
        street_name=parsed_street,
        house_number=parsed_number,
        municipality_hint=municipality,
        province=province,
    )

    if not cadastre_result:
        # Fall back to direct DNPLOC (previous approach)
        source = "geocode:cadastre_address"
        cadastre_result = cadastre_address_lookup(address, municipality, province=province)

    if cadastre_result:
        rc = cadastre_result["rc"]
        # Get UTM centroid via Consulta_CPMRC
        utm_coords = cadastre_rc_to_utm(rc)
        if utm_coords:
            centroid_x, centroid_y = utm_coords
        elif cadastre_result.get("xcen") and cadastre_result.get("ycen"):
            # Fallback: use DNPLOC xcen/ycen (may be geographic, convert if needed)
            xcen = cadastre_result["xcen"]
            ycen = cadastre_result["ycen"]
            if xcen < 1000 and ycen < 1000:
                # Geographic coordinates (lon, lat) — convert to UTM
                centroid_x, centroid_y, utm_zone = _wgs84_to_utm(ycen, xcen)
                source = "geocode:cadastre_address(dnploc_geo)"
            elif SPAIN_UTM_X_MIN <= xcen <= SPAIN_UTM_X_MAX:
                # Already UTM
                centroid_x, centroid_y = xcen, ycen
                source = "geocode:cadastre_address(dnploc_utm)"

    # 3. FALLBACK: Nominatim + grid search (only if primary failed)
    if centroid_x is None:
        source = "geocode:nominatim+cadastre"
        logger.info("Primary cadastre address lookup failed, falling back to Nominatim")
        coords = nominatim_geocode(address, municipality, province=province)
        if coords is None:
            logger.warning(f"Geocoding failed for '{address}, {municipality}'")
            return None
        lat, lon = coords

        # Cadastre parcel lookup via grid search (only override RC if not already set)
        parcel = cadastre_find_parcel(lat, lon, address)
        if parcel and rc is None:
            rc = parcel["rc"]

        # Convert to UTM (auto-detect zone from longitude)
        centroid_x, centroid_y, utm_zone = _wgs84_to_utm(lat, lon)

    # 4. Get parcel geometry (for point distribution) — try if we have RC
    polygon: list[tuple[float, float]] | None = None
    if rc and len(rc) >= 14:
        try:
            polygon = get_parcel_geometry_utm(rc[:14])
        except GeocodeError as e:
            logger.warning(f"Could not get parcel geometry for {rc[:14]}: {e}")

    # 5. Distribute points — if polygon available, use it; otherwise centroid
    parcel_area: float | None = None
    if polygon and len(polygon) >= 3:
        # Override centroid with polygon centroid (more precise)
        n = len(polygon)
        centroid_x = sum(p[0] for p in polygon) / n
        centroid_y = sum(p[1] for p in polygon) / n
        points = distribute_points(polygon, point_ids)
        # Compute cadastral area via Shoelace formula (UTM m2)
        parcel_area = abs(sum(
            polygon[i][0] * polygon[(i + 1) % n][1]
            - polygon[(i + 1) % n][0] * polygon[i][1]
            for i in range(n)
        )) / 2.0
        logger.info(f"Cadastral parcel area (Shoelace): {parcel_area:.0f} m2")
    else:
        # Place all points at centroid
        points = {pid: {"x": centroid_x, "y": centroid_y} for pid in point_ids}

    # 6. Validate centroid within Spanish peninsular bounds
    if not (SPAIN_UTM_X_MIN <= centroid_x <= SPAIN_UTM_X_MAX):
        logger.warning(f"Centroid UTM X {centroid_x} outside Spain bounds")
        return None
    if not (SPAIN_UTM_Y_MIN <= centroid_y <= SPAIN_UTM_Y_MAX):
        logger.warning(f"Centroid UTM Y {centroid_y} outside Spain bounds")
        return None

    # 7. Get elevations for each point (ICGC is Catalunya-only)
    _catalan_provs = {p.upper() for p in _CATALAN_PROVINCES}
    is_catalan = province.upper() in _catalan_provs if province else True  # default to trying
    elevations: dict[str, float] = {}
    if is_catalan:
        try:
            from .icgc_geology import get_elevation
            for pid, pt in points.items():
                try:
                    elevations[pid] = get_elevation(pt["x"], pt["y"])
                except Exception as e:
                    logger.warning(f"Could not get elevation for {pid}: {e}")
                    elevations[pid] = 0.0
        except ImportError:
            logger.warning("icgc_geology module not available, skipping elevations")
            for pid in points:
                elevations[pid] = 0.0
    else:
        logger.info(f"Skipping ICGC elevations (province={province!r} is outside Catalunya)")
        for pid in points:
            elevations[pid] = 0.0

    # Add elevation to points dict
    points_with_z: dict[str, dict[str, float]] = {}
    for pid, pt in points.items():
        points_with_z[pid] = {
            "x": pt["x"],
            "y": pt["y"],
            "z": elevations.get(pid, 0.0),
        }

    # 8. Generate COORDENADES.txt if output_dir provided
    if output_dir is not None:
        coord_path = output_dir / "ANNEXES" / "ALTRES" / "COORDENADES.txt"
        try:
            generate_coordenades_txt(points, elevations, coord_path)
        except OSError as e:
            logger.warning(f"Could not write COORDENADES.txt: {e}")

    # 9. Build result
    result = {
        "utm_x": centroid_x,
        "utm_y": centroid_y,
        "points": points_with_z,
        "rc": rc,
        "source": source,
    }
    if parcel_area is not None:
        result["parcel_area"] = round(parcel_area, 0)

    # 10. Cache result
    _save_to_cache(address, municipality, result)

    return result


# === CLI for Testing ===

if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.DEBUG)

    print("=" * 60)
    print("Geocode Coordinates - Test")
    print("=" * 60)

    # Bell-Lloc d'Urgell test case
    address = "Carrer Mestre Ramon Ortiz, 5"
    municipality = "Bell-Lloc d'Urgell"
    point_ids = ["P-1", "P-2", "S-1"]

    print(f"Address: {address}")
    print(f"Municipality: {municipality}")
    print(f"Points: {point_ids}")
    print()

    try:
        result = geocode_project(address, municipality, point_ids)
        if result:
            print(f"UTM X: {result['utm_x']:.1f}")
            print(f"UTM Y: {result['utm_y']:.1f}")
            print(f"RC: {result['rc']}")
            print(f"Source: {result['source']}")
            print()
            for pid, pt in sorted(result['points'].items()):
                print(f"  {pid}: ({pt['x']:.1f}, {pt['y']:.1f}, {pt['z']:.1f})")
        else:
            print("Geocoding returned no results.")
    except GeocodeError as e:
        print(f"Error: {e}")
