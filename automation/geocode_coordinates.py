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
import difflib
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
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ['geocode_project', 'GeocodeError', 'cadastre_address_lookup', 'cadastre_rc_to_utm']


# === Configuration ===

CACHE_DIR = Path.home() / ".g3dt" / "cache" / "geocode"
CARTOCIUDAD_CACHE_DIR = Path.home() / ".g3dt" / "cache" / "cartociudad"
CACHE_TTL_DAYS = 90
CARTOCIUDAD_CACHE_TTL_DAYS = 365  # addresses don't change often
REQUEST_TIMEOUT_SECONDS = 15
USER_AGENT = "G3DT-Automation/1.0 (Eficients.cat; geotechnical report generation)"
CARTOCIUDAD_USER_AGENT = "g3dt/1.0"  # CartoCiudad rejects requests without UA

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


def _strip_accents(s: str) -> str:
    """Strip accent marks for accent-insensitive comparison."""
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


# Catalan/Spanish contracted preposition variants that should compare equal.
# Each key is a multi-word pattern; value is the canonical replacement.
# Applied after accent-stripping + upper-casing, with word boundaries.
# Scope is deliberately Catalan/Spanish only: Portuguese/Galician tokens
# (da, das, do, dos) collide with legitimate Spanish municipality name
# roots (e.g. "Dos Hermanas") and must not be normalized here.
_PREPOSITION_CANONICAL: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bDELS\b"), "DE"),
    (re.compile(r"\bDEL\b"), "DE"),
    (re.compile(r"\bDE LAS\b"), "DE"),
    (re.compile(r"\bDE LES\b"), "DE"),
    (re.compile(r"\bDE LOS\b"), "DE"),
    (re.compile(r"\bDE LA\b"), "DE"),
    (re.compile(r"\bD'"), "DE "),
]


def _normalize_muni_name(s: str) -> str:
    """Normalize a municipality name for tolerant matching.

    Steps:
    1. Strip accents (accent-insensitive).
    2. Upper-case and collapse whitespace.
    3. Collapse Catalan/Spanish contracted prepositions (del, dels, de la,
       de les, de los, d') to a single canonical ``DE`` token. This makes
       "Vilanova del Segrià" compare equal to "Vilanova de Segrià".

    Used as a fallback when exact (accent-stripped) matching fails.
    """
    out = _strip_accents(s).upper().strip()
    for pattern, replacement in _PREPOSITION_CANONICAL:
        out = pattern.sub(replacement, out)
    # Collapse any extra whitespace introduced by the substitutions
    out = re.sub(r"\s+", " ", out).strip()
    return out


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


# Full-word street-type tokens that must be stripped from a hint before
# querying Cadastre ConsultaVia. The short-prefix list above (_STREET_TYPE_MAP)
# only covers abbreviations ("C.", "AV.", etc.); Cadastre's fuzzy matcher
# treats the full word "Carrer" as part of the street name, returning the
# wrong street (e.g. "Carrer Santa Gemma" → CARRERADA PD, instead of
# SANTA GEMMA CL). These are stripped case-insensitively from the start
# of the hint. Longer variants first so "Carrer de la" matches before "Carrer".
_STREET_TYPE_WORDS = [
    # Catalan
    "carrer", "camí", "cami", "passeig", "avinguda", "plaça", "placa",
    "rambla", "travessia", "travessera", "passatge",
    # Spanish
    "calle", "camino", "paseo", "avenida", "avda", "plaza", "travesía",
    "travesia", "carretera", "ronda",
]

# Prepositions/articles that may follow a street-type word and should also
# be stripped (case-insensitive, accent-insensitive).
_STREET_TYPE_CONNECTORS = [
    "de la", "de les", "de las", "de los", "dels", "del", "de",
]

_STREET_TYPE_WORD_RE = re.compile(
    r"^\s*(?:" + "|".join(sorted(_STREET_TYPE_WORDS, key=len, reverse=True)) + r")\b"
    r"(?:\s+(?:" + "|".join(_STREET_TYPE_CONNECTORS) + r"))*"
    r"\s+",
    re.IGNORECASE,
)


def _strip_street_type_word(hint: str) -> str:
    """Strip leading street-type words (Carrer, Calle, Plaça, etc.) + any
    following connector prepositions (de, del, de la, dels, ...) from a
    street-name hint.

    Examples:
        "Carrer Santa Gemma"    -> "Santa Gemma"
        "Calle Mayor"           -> "Mayor"
        "Carrer de la Pau"      -> "Pau"
        "Plaça de l'Església"   -> "l'Església"    (d' is not in connectors)
        "Santa Gemma"           -> "Santa Gemma"   (no prefix, unchanged)
        "C. Santa Gemma"        -> "C. Santa Gemma" (short abbreviation
                                    handled elsewhere, by ``_parse_address``)

    The regex anchors at the start and requires a word boundary, so street
    names that legitimately begin with these tokens as a substring (e.g.
    "Rambla dels Parcers" → would strip "Rambla dels ", leaving "Parcers")
    are acceptable: Cadastre's fuzzy matcher handles partial name lookup.
    """
    if not hint:
        return hint
    stripped = _STREET_TYPE_WORD_RE.sub("", hint, count=1)
    # Only return the stripped version if something was actually removed AND
    # a non-empty remainder exists. Never return an empty string.
    if stripped and stripped != hint:
        return stripped.strip()
    return hint


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
    # Handles: "18A", "#7", "nº7", "núm. 5", "num 3", "Nº 12"
    numero = ""
    addr_part = address.strip()
    m = re.search(r',\s*(?:(?:#|nº|n[uú]m\.?)\s*)?(\d+[A-Za-z]?)\s*$', addr_part, re.IGNORECASE)
    if m:
        numero = m.group(1)
        addr_part = addr_part[:m.start()].strip()
    else:
        m = re.search(r'\s+(?:(?:#|nº|n[uú]m\.?)\s*)?(\d+[A-Za-z]?)\s*$', addr_part, re.IGNORECASE)
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

def _retry_with_normalized_hint(
    province: str,
    municipality_hint: str,
    retry_allowed: bool,
) -> tuple[str, str, str] | None:
    """Retry ConsultaMunicipio once with a preposition-normalized hint.

    Converts Catalan/Spanish contracted prepositions to canonical form
    (``del`` → ``de``, ``d'`` → ``de``, etc.) and re-queries. Only runs
    when the normalized hint actually differs from the original and the
    caller hasn't already retried.
    """
    if not retry_allowed:
        return None
    normalized = _normalize_muni_name(municipality_hint)
    original = _strip_accents(municipality_hint).upper().strip()
    original = re.sub(r"\s+", " ", original)
    if normalized == original or not normalized:
        return None
    logger.info(
        f"ConsultaMunicipio: exact hint '{municipality_hint}' failed; "
        f"retrying with preposition-normalized hint '{normalized}'"
    )
    return _consulta_municipio(province, normalized, _retry_normalized=False)


def _consulta_municipio(
    province: str,
    municipality_hint: str,
    _retry_normalized: bool = True,
) -> tuple[str, str, str] | None:
    """
    Fuzzy-resolve a municipality name via Cadastre ConsultaMunicipio.

    Args:
        province: Province name (e.g., "LLEIDA", "HUESCA")
        municipality_hint: Partial or approximate municipality name
        _retry_normalized: Internal flag. When True (default) and the first
            lookup fails, retry once with a preposition-normalized hint
            (e.g., "Vilanova del Segrià" → "Vilanova de Segrià").

    Returns:
        Tuple of (official_name, cp, cm) or None if not found.
        cp = INE province code, cm = INE municipality code.
    """
    # Strip accents before API call — Cadastre rejects accented chars
    # (e.g. "Castellar del Vallès" → no results, "Castellar del Valles" → OK)
    hint_clean = _strip_accents(municipality_hint)
    url = (
        f"{CADASTRE_CALLEJERO_URL}/ConsultaMunicipio"
        f"?Provincia={urllib.parse.quote(_strip_accents(province))}"
        f"&Municipio={urllib.parse.quote(hint_clean)}"
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
        return _retry_with_normalized_hint(province, municipality_hint, _retry_normalized)

    hint_norm = _strip_accents(municipality_hint.upper().strip())
    hint_words = set(hint_norm.split())
    hint_tolerant = _normalize_muni_name(municipality_hint)
    candidates: list[tuple[int, int, str, str, str]] = []
    tolerant_match: tuple[str, str, str, str] | None = None  # (official, cp, cm, name_tolerant)

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
                # Remember a preposition-normalized exact match as a last-resort
                # fallback (e.g. "Vilanova del Segrià" ~ "Vilanova de Segrià").
                if tolerant_match is None:
                    name_tolerant = _normalize_muni_name(official_name)
                    if name_tolerant == hint_tolerant:
                        tolerant_match = (official_name, cp, cm, name_tolerant)
                continue

        # Store: (-score for desc sort, len for asc tiebreak, name, cp, cm)
        candidates.append((-score, len(official_name), official_name, cp, cm))

    if not candidates:
        if tolerant_match is not None:
            official_name, cp, cm, name_tolerant = tolerant_match
            logger.info(
                f"ConsultaMunicipio: exact match failed, matched after name "
                f"normalization: '{municipality_hint}' ~ '{official_name}' "
                f"(normalized: '{name_tolerant}')"
            )
            return official_name, cp, cm
        logger.debug(f"ConsultaMunicipio: no match for '{municipality_hint}' in '{province}'")
        return _retry_with_normalized_hint(province, municipality_hint, _retry_normalized)

    candidates.sort()
    best = candidates[0]
    return best[2], best[3], best[4]


def _consulta_via(
    province: str, municipality: str, street_hint: str,
    full_address_context: str = "",
) -> tuple[str, str, str] | None:
    """
    Fuzzy-resolve a street name via Cadastre ConsultaVia.

    Uses a 3-layer approach:
    1. Progressive exact matching (substring shortening)
    2. difflib fuzzy matching (Levenshtein + article stripping)
    3. LLM street picker (Groq) — semantic matching as last resort

    Args:
        province: Province name
        municipality: Official municipality name (from _consulta_municipio)
        street_hint: Partial street name (e.g., "Ferraz", "Mestre Ramon").
            Must be name-only (no type prefix) for fuzzy/LLM matching.
        full_address_context: Optional full address string for LLM context
            (e.g., "Carrer Girassols nº7, Urbanització El Roser")

    Returns:
        Tuple of (official_street_name, tipo_via, cv) or None.
        tipo_via = street type code (CL, AV, etc.), cv = street code.
    """
    # Strip full-word street-type prefixes (Carrer, Calle, Plaça, ...) BEFORE
    # anything else. Cadastre's fuzzy matcher will otherwise treat these as
    # part of the street name and return a wildly wrong match (e.g.
    # "Carrer Santa Gemma" → CARRERADA PD instead of SANTA GEMMA CL).
    cleaned_hint = _strip_street_type_word(street_hint.strip())
    if cleaned_hint != street_hint.strip():
        logger.debug(
            f"ConsultaVia: stripped street-type prefix from hint "
            f"'{street_hint}' -> '{cleaned_hint}'"
        )

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
    for w in cleaned_hint.split():
        expanded_words.append(_ABBREVIATIONS.get(w.lower(), w))
    expanded_hint = " ".join(expanded_words)

    # Try progressively shorter hints if no results
    hint_words = expanded_hint.split()
    attempts = [expanded_hint]
    # Only prepend the original hint if abbreviation expansion changed it —
    # NOT if only the street-type-word stripping changed it. Trying the
    # original with "Carrer"/"Calle" prefix would re-introduce the exact
    # Cadastre fuzzy-match bug this fix is for.
    if expanded_hint != cleaned_hint:
        attempts.insert(0, cleaned_hint)  # try pre-abbreviation form first
    for i in range(len(hint_words) - 1, 0, -1):
        attempts.append(" ".join(hint_words[:i]))

    for current_hint in attempts:
        try:
            result = _consulta_via_single(province, municipality, current_hint)
        except GeocodeConnectionError:
            # Server is down — abort immediately, don't try more hints
            logger.warning("ConsultaVia server unreachable, aborting street lookup")
            return None
        if result is not None:
            return result

    # All progressive hints failed — try fuzzy matching against full street list
    # Only for manageable municipality sizes (skip large cities)
    all_streets = _consulta_via_all_streets(province, municipality)
    if all_streets and len(all_streets) <= 500:
        hint_clean = _strip_accents(cleaned_hint.upper())
        if len(hint_clean) < 4:
            return None  # Too short for reliable fuzzy matching
        street_names_upper = [_strip_accents(s[0].upper()) for s in all_streets]

        # Phase 1: Full-string fuzzy match (e.g., "GIRASOLS" vs "GIRASOLS")
        matches = difflib.get_close_matches(
            hint_clean, street_names_upper, n=1, cutoff=0.8
        )
        if matches:
            idx = street_names_upper.index(matches[0])
            matched = all_streets[idx]
            ratio = difflib.SequenceMatcher(None, hint_clean, matches[0]).ratio()
            logger.info(
                f"Progressive cadastre: fuzzy match '{street_hint}' -> "
                f"'{matched[0]}' (ratio={ratio:.2f})"
            )
            return matched

        # Phase 2: Word-level match for multi-word street names
        # Cadastre often prefixes articles: "DELS GIRASOLS", "DE LA FONT"
        # Our hint "GIRASSOLS" won't match full string at 0.8 but will match
        # the significant word "GIRASOLS" at 0.94
        _ARTICLES = {'DE', 'DEL', 'DELS', 'DE LA', 'DE LES', 'DE LOS',
                      'EL', 'LA', 'LES', 'ELS', 'LOS', 'LAS', 'D'}
        best_ratio = 0.0
        best_idx = -1
        for i, full_name in enumerate(street_names_upper):
            words = full_name.split()
            if len(words) < 2:
                continue
            # Strip leading articles to get the significant part
            significant = full_name
            for art in sorted(_ARTICLES, key=len, reverse=True):
                if full_name.startswith(art + ' '):
                    significant = full_name[len(art) + 1:]
                    break
            if significant == full_name:
                continue  # No article stripped, already tried in Phase 1
            ratio = difflib.SequenceMatcher(None, hint_clean, significant).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i

        if best_ratio >= 0.8 and best_idx >= 0:
            matched = all_streets[best_idx]
            logger.info(
                f"Progressive cadastre: fuzzy word match '{street_hint}' -> "
                f"'{matched[0]}' (ratio={best_ratio:.2f}, stripped article)"
            )
            return matched

        # Phase 3: LLM street picker — semantic matching via Groq
        # Handles cases difflib can't: OCR errors + articles, urbanitzacions,
        # Catalan/Spanish variants, abbreviations, etc.
        llm_match = _llm_pick_street(
            street_hint, municipality, all_streets,
            full_address_context=full_address_context,
        )
        if llm_match is not None:
            return llm_match

    return None


def _consulta_via_all_streets(
    province: str, municipality: str
) -> list[tuple[str, str, str]]:
    """
    Fetch ALL streets in a municipality via ConsultaVia with empty NombreVia.

    Returns list of (street_name, tipo_via, cv) tuples.
    Used as fallback for fuzzy matching when exact hint matching fails.
    """
    url = (
        f"{CADASTRE_CALLEJERO_URL}/ConsultaVia"
        f"?Provincia={urllib.parse.quote(province)}"
        f"&Municipio={urllib.parse.quote(municipality)}"
        f"&TipoVia=&NombreVia="
    )
    logger.debug(f"ConsultaVia (all streets) URL: {url}")

    try:
        response_text = _fetch_url(url)
    except GeocodeConnectionError as e:
        logger.warning(f"ConsultaVia all-streets connection failed: {e}")
        return []
    finally:
        time.sleep(0.3)

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError:
        return []

    # Check for errors
    for err_elem in _find_all_elements(root, "err"):
        des_elem = _find_element(err_elem, "des")
        if des_elem is not None and des_elem.text:
            logger.debug(f"ConsultaVia all-streets error: {des_elem.text}")
            return []

    streets: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for tag in ("dir", "calle"):
        for elem in _find_all_elements(root, tag):
            nv_elem = _find_element(elem, "nv")
            tv_elem = _find_element(elem, "tv")
            cv_elem = _find_element(elem, "cv")
            if nv_elem is not None and nv_elem.text:
                street_name = nv_elem.text.strip()
                if street_name in seen:
                    continue
                seen.add(street_name)
                tipo_via = tv_elem.text.strip() if tv_elem is not None and tv_elem.text else ""
                cv = cv_elem.text.strip() if cv_elem is not None and cv_elem.text else ""
                streets.append((street_name, tipo_via, cv))

    return streets


# === LLM Street Picker (Layer 3) ===

_LLM_STREET_PICKER_PROMPT = """\
You are matching a project address to an official Spanish Cadastre street list.

**Address hint:** "{hint}"
**Municipality:** {municipality}
{context_line}
**Official streets in {municipality} (from Cadastre):**
{street_list}

Which official street BEST matches the address hint? Consider:
- OCR typos: doubled/missing letters (ss↔s, rr↔r, ll↔l)
- Catalan/Spanish articles the Cadastre may prepend: del, dels, de la, de les, el, la, d'
- Street type differences: Carrer/Calle, Plaça/Plaza, Avinguda/Avenida
- Urbanització/Polígon names that may appear differently in the Cadastre
- Abbreviations: Sta.→Santa, Dr.→Doctor, Mn.→Mossen

Reply with ONLY the exact official street name from the list above.
If no street matches, reply with exactly: NONE"""


def _llm_pick_street(
    street_hint: str,
    municipality: str,
    all_streets: list[tuple[str, str, str]],
    full_address_context: str = "",
) -> tuple[str, str, str] | None:
    """
    Use an LLM (Groq) to semantically match a street hint against the
    official Cadastre street list. Last-resort fallback after difflib fails.

    Only active when GROQ_API_KEY is set. Returns None silently if not.

    Args:
        street_hint: Parsed street name (no type prefix)
        municipality: Official municipality name
        all_streets: Full street list from _consulta_via_all_streets()
        full_address_context: Optional full address for extra context

    Returns:
        Tuple of (street_name, tipo_via, cv) or None if no match.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.debug("LLM street picker: skipped (no GROQ_API_KEY)")
        return None

    # Build compact street list for the prompt (name + type abbreviation)
    street_lines = []
    for name, tv, cv in all_streets:
        street_lines.append(f"- {name} ({tv})" if tv else f"- {name}")
    street_list_text = "\n".join(street_lines)

    context_line = ""
    if full_address_context and full_address_context.strip() != street_hint:
        context_line = f'**Full address from project documents:** "{full_address_context}"'

    prompt = _LLM_STREET_PICKER_PROMPT.format(
        hint=street_hint,
        municipality=municipality,
        context_line=context_line,
        street_list=street_list_text,
    )

    model = os.environ.get("GROQ_MODEL", "qwen/qwen3-32b")

    # Qwen3: disable thinking mode for clean output
    if "qwen3" in model.lower():
        messages = [
            {"role": "user", "content": prompt + "\n\n/no_think"},
        ]
    else:
        messages = [
            {"role": "user", "content": prompt},
        ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 60,
    }

    logger.info(
        f"LLM street picker: matching '{street_hint}' against "
        f"{len(all_streets)} streets in {municipality}"
    )

    try:
        import httpx
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code != 200:
            logger.warning(f"LLM street picker: Groq HTTP {resp.status_code}")
            return None

        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Strip Qwen3 <think>...</think> tags
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        # Strip any markdown/quotes the LLM might add
        content = content.strip('"\'`* \n')

        # Strip type suffix the LLM may copy from prompt: "DELS GIRASOLS (CL)" → "DELS GIRASOLS"
        content = re.sub(r'\s*\([A-Z]{1,3}\)\s*$', '', content).strip()

        if not content or content.upper() == "NONE":
            logger.info(f"LLM street picker: no match for '{street_hint}'")
            return None

        # Validate: the response MUST be an exact street name from our list
        content_upper = content.upper()
        for name, tv, cv in all_streets:
            if name.upper() == content_upper:
                logger.info(
                    f"LLM street picker: '{street_hint}' -> '{name}' ({tv}) "
                    f"in {municipality}"
                )
                return (name, tv, cv)

        # LLM returned something not in the list — reject it
        logger.warning(
            f"LLM street picker: response '{content}' not in street list, ignoring"
        )
        return None

    except Exception as e:
        logger.warning(f"LLM street picker failed: {e}")
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
        raise  # Let caller decide whether to retry with different hint
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
        # Strip trailing letter suffix: "18A" → 18, "39B" → 39
        num_digits = re.sub(r'[A-Za-z]+$', '', house_number.strip()) if house_number else ''
        target = int(num_digits) if num_digits else 1
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
    full_address: str = "",
) -> dict | None:
    """
    Progressive Cadastre resolution: fuzzy municipality -> fuzzy street -> DNPLOC.

    More robust than direct Consulta_DNPLOC because it uses Cadastre's own
    fuzzy search to resolve municipality and street names before lookup.

    Args:
        street_name: Parsed street name (no type prefix)
        house_number: House number
        municipality_hint: Approximate municipality name
        province: Province name
        full_address: Full original address string for LLM context

    Returns: {"rc": str, "xcen": float|None, "ycen": float|None} or None.
    """
    # Step 1: Resolve municipality
    muni_result = _consulta_municipio(province, municipality_hint)
    effective_province = province
    if muni_result is None:
        # P3: Try border provinces before giving up
        border_provs = _BORDER_PROVINCES.get(province.upper(), [])
        for neighbor_prov in border_provs:
            muni_result = _consulta_municipio(neighbor_prov, municipality_hint)
            if muni_result is not None:
                effective_province = neighbor_prov
                logger.info(
                    f"Progressive cadastre: cross-province '{municipality_hint}' "
                    f"found in {neighbor_prov} (was {province})"
                )
                break
    if muni_result is None:
        # Try village→municipality mapping (e.g., Anciles → Benasque)
        village_entry = _VILLAGE_TO_MUNICIPALITY.get(
            _strip_accents(municipality_hint).upper().strip()
        )
        if village_entry:
            parent_muni, parent_prov = village_entry
            logger.info(
                f"Progressive cadastre: trying village mapping "
                f"'{municipality_hint}' → '{parent_muni}' ({parent_prov})"
            )
            muni_result = _consulta_municipio(parent_prov, parent_muni)
            if muni_result:
                effective_province = parent_prov
    if muni_result is None:
        logger.warning(f"Progressive cadastre: municipality '{municipality_hint}' not found in {province} or neighbors")
        return None
    official_muni, cp, cm = muni_result
    logger.info(f"Progressive cadastre: municipality '{municipality_hint}' -> '{official_muni}'")

    # Step 2: Resolve street
    via_result = _consulta_via(
        effective_province, official_muni, street_name,
        full_address_context=full_address,
    )
    if via_result is None:
        logger.warning(f"Progressive cadastre: street '{street_name}' not found in {official_muni}")
        return None
    official_street, tipo_via, cv = via_result
    logger.info(f"Progressive cadastre: street '{street_name}' -> '{official_street}' ({tipo_via})")

    # Step 3: DNPLOC with resolved names
    # Strip letter suffix from house number — API only accepts digits
    # (error 42: "EL NÚMERO DEBE SER UNA SECUENCIA DE HASTA 4 DÍGITOS")
    clean_number = re.sub(r'[A-Za-z]+$', '', house_number.strip()) if house_number else house_number
    params = (
        f"?Provincia={urllib.parse.quote(effective_province)}"
        f"&Municipio={urllib.parse.quote(official_muni)}"
        f"&Sigla={urllib.parse.quote(tipo_via)}"
        f"&Calle={urllib.parse.quote(official_street)}"
        f"&Numero={urllib.parse.quote(clean_number)}"
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

        # If number has a letter suffix (e.g. "18A"), retry with just the digits
        num_digits = re.sub(r'[A-Za-z]+$', '', house_number.strip())
        if num_digits and num_digits != house_number.strip():
            logger.info(f"Progressive cadastre: retrying with number '{num_digits}' (was '{house_number}')")
            time.sleep(0.3)
            retry_params = (
                f"?Provincia={urllib.parse.quote(effective_province)}"
                f"&Municipio={urllib.parse.quote(official_muni)}"
                f"&Sigla={urllib.parse.quote(tipo_via)}"
                f"&Calle={urllib.parse.quote(official_street)}"
                f"&Numero={urllib.parse.quote(num_digits)}"
                f"&Bloque=&Escalera=&Planta=&Puerta="
            )
            retry_url = f"{CADASTRE_CALLEJERO_URL}/Consulta_DNPLOC{retry_params}"
            try:
                retry_text = _fetch_url(retry_url)
                retry_root = ET.fromstring(retry_text)
                # Check for errors in retry
                retry_errs = {
                    (_find_element(e, "cod").text.strip() if _find_element(e, "cod") is not None and _find_element(e, "cod").text else "")
                    for e in _find_all_elements(retry_root, "err")
                }
                if not retry_errs:
                    # Direct hit — extract RC
                    pc1_r = _find_all_elements(retry_root, "pc1")
                    pc2_r = _find_all_elements(retry_root, "pc2")
                    if pc1_r and pc1_r[0].text:
                        rc = pc1_r[0].text.strip() + (pc2_r[0].text.strip() if pc2_r and pc2_r[0].text else "")
                        logger.info(f"Progressive cadastre: stripped-number hit -> RC {rc}")
                        xcen2: float | None = None
                        ycen2: float | None = None
                        utm_c = cadastre_rc_to_utm(rc)
                        if utm_c:
                            xcen2, ycen2 = utm_c
                        return {"rc": rc, "xcen": xcen2, "ycen": ycen2}
                elif "43" in retry_errs:
                    # Still not found — try nearest from retry response
                    rc = _pick_nearest_rc_from_numerero(retry_root, num_digits)
                    if rc:
                        logger.info(f"Progressive cadastre: stripped-number nearest -> RC {rc}")
                        xcen3: float | None = None
                        ycen3: float | None = None
                        utm_c2 = cadastre_rc_to_utm(rc)
                        if utm_c2:
                            xcen3, ycen3 = utm_c2
                        return {"rc": rc, "xcen": xcen3, "ycen": ycen3}
            except Exception as e:
                logger.debug(f"Progressive cadastre: stripped-number retry failed: {e}")

        logger.warning("Progressive cadastre: number not found and no nearby numbers")
        return None

    if "41" in error_codes and not house_number.strip():
        # Empty house number — retry DNPLOC with "1" as fallback
        logger.info("Progressive cadastre: empty number, retrying DNPLOC with '1'")
        time.sleep(0.3)
        retry_params = (
            f"?Provincia={urllib.parse.quote(effective_province)}"
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


def callejero_address_to_rc(
    street_address: str,
    municipality: str,
    province: str = "",
) -> dict | None:
    """
    Resolve a street address to cadastral reference via direct Callejero lookup.

    This is the fast, precise path: address → (fuzzy muni + fuzzy street + DNPLOC)
    → RC → polygon → UTM centroid.  Bypasses Nominatim and grid search entirely.

    Args:
        street_address: Full street address (e.g. "Carrer Arbrells, 18")
        municipality: Municipality name (may have accents)
        province: Province name.  If empty, tries all 4 Catalan provinces.

    Returns:
        Dict with keys: rc, utm_x, utm_y, parcel_area, polygon.  Or None.
    """
    sigla, calle, numero = _parse_address(street_address)
    if not calle:
        logger.debug("callejero_address_to_rc: no street name parsed from %r", street_address)
        return None

    # Determine provinces to try
    if province:
        provinces = [province.upper()]
    else:
        provinces = list(_CATALAN_PROVINCES)

    # Try progressive lookup (fuzzy muni + fuzzy street + DNPLOC with error recovery)
    for prov in provinces:
        result = cadastre_progressive_lookup(
            street_name=calle,
            house_number=numero,
            municipality_hint=municipality,
            province=prov,
            full_address=street_address,
        )
        if result and result.get("rc"):
            rc = result["rc"]
            logger.info(f"callejero_address_to_rc: RC {rc} from progressive lookup ({prov})")

            # Get polygon + centroid for precise UTM
            utm_x: float | None = None
            utm_y: float | None = None
            parcel_area: float | None = None
            polygon: list[tuple[float, float]] = []

            try:
                polygon = get_parcel_geometry_utm(rc[:14])
                if polygon:
                    xs = [p[0] for p in polygon]
                    ys = [p[1] for p in polygon]
                    utm_x = sum(xs) / len(xs)
                    utm_y = sum(ys) / len(ys)
                    # Approximate area via Shoelace formula
                    n = len(polygon)
                    area = 0.0
                    for i in range(n):
                        j = (i + 1) % n
                        area += polygon[i][0] * polygon[j][1]
                        area -= polygon[j][0] * polygon[i][1]
                    parcel_area = abs(area) / 2.0
            except Exception as e:
                logger.debug(f"callejero_address_to_rc: polygon fetch failed for {rc[:14]}: {e}")
                # Fall back to DNPLOC-provided coordinates
                utm_x = result.get("xcen")
                utm_y = result.get("ycen")

            if utm_x and utm_y:
                return {
                    "rc": rc,
                    "utm_x": utm_x,
                    "utm_y": utm_y,
                    "parcel_area": parcel_area,
                    "polygon": polygon,
                    "source": f"Callejero ({prov})",
                }

    return None


_CATALAN_PROVINCES = ["LLEIDA", "BARCELONA", "GIRONA", "TARRAGONA"]

_BORDER_PROVINCES: dict[str, list[str]] = {
    "LLEIDA": ["HUESCA", "BARCELONA", "TARRAGONA"],
    "BARCELONA": ["LLEIDA", "GIRONA", "TARRAGONA"],
    "GIRONA": ["BARCELONA"],
    "TARRAGONA": ["LLEIDA", "BARCELONA"],
    "HUESCA": ["LLEIDA"],
    "ZARAGOZA": ["LLEIDA", "TARRAGONA"],
}

# Village → parent municipality mapping for villages that are not
# municipalities themselves (Cadastre API needs the municipality name).
_VILLAGE_TO_MUNICIPALITY: dict[str, tuple[str, str]] = {
    # (village_upper → (municipality, province))
    "ANCILES": ("BENASQUE", "HUESCA"),
    "CERLER": ("BENASQUE", "HUESCA"),
    "ERISTE": ("SAHUN", "HUESCA"),
    "BENAS": ("BENASQUE", "HUESCA"),
}


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
        # API requires uppercase municipality/province and all address fields.
        # Strip accents: Cadastre Callejero rejects accented chars
        # (e.g. "CASTELLAR DEL VALLÈS" → NOT FOUND, "CASTELLAR DEL VALLES" → OK)
        muni_clean = _strip_accents(municipality.upper())
        params = (
            f"?Provincia={urllib.parse.quote(_strip_accents(prov))}"
            f"&Municipio={urllib.parse.quote(muni_clean)}"
            f"&Sigla={urllib.parse.quote(sigla)}"
            f"&Calle={urllib.parse.quote(_strip_accents(calle.upper()))}"
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
    # Clean house number prefixes that confuse Nominatim: "#7" → "7", "nº7" → "7"
    clean_addr = re.sub(r'(?:#|nº|Nº|n[úu]m\.?)\s*(?=\d)', '', address)
    if province:
        query = f"{clean_addr}, {municipality}, {province}, Spain"
    else:
        query = f"{clean_addr}, {municipality}, Catalunya, Spain"
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


def nominatim_geocode_structured(
    address: str, municipality: str, province: str = ""
) -> tuple[float, float] | None:
    """
    Geocode using Nominatim structured query (separate street/city/state params).

    Better than free-text for small towns where Nominatim's parser may fail.
    Used as first fallback before the free-text nominatim_geocode().

    Args:
        address: Street address (e.g. "Carrer Girasols 7")
        municipality: Municipality name
        province: Province name (optional)

    Returns:
        Tuple of (lat, lon) or None if not found
    """
    # Parse address into street components
    sigla, street_name, number = _parse_address(address)
    # Reconstruct street param: "street_name number" (no type prefix for Nominatim)
    street_param = street_name
    if number:
        street_param = f"{street_name} {number}"

    # Clean house number prefixes that confuse Nominatim
    street_param = re.sub(r'(?:#|nº|Nº|n[úu]m\.?)\s*(?=\d)', '', street_param)

    state = province if province else "Catalunya"
    params = urllib.parse.urlencode({
        'street': street_param,
        'city': municipality,
        'state': state,
        'country': 'Spain',
        'format': 'json',
        'limit': '1',
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"

    logger.info(f"Nominatim structured query: street='{street_param}', city='{municipality}'")

    try:
        response_text = _fetch_url(url, expect_json=True)
    except GeocodeConnectionError as e:
        logger.warning(f"Nominatim structured connection failed: {e}")
        return None

    try:
        results = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Nominatim structured JSON parse error: {e}")
        return None

    if not results:
        logger.debug(f"Nominatim structured returned no results for: street='{street_param}', city='{municipality}'")
        return None

    try:
        lat = float(results[0]['lat'])
        lon = float(results[0]['lon'])
    except (KeyError, ValueError, IndexError) as e:
        logger.warning(f"Nominatim structured response missing lat/lon: {e}")
        return None

    logger.info(f"Nominatim structured geocoded -> ({lat:.6f}, {lon:.6f})")

    # Rate limit: Nominatim requires max 1 request per second
    time.sleep(1.5)

    return lat, lon


# === CartoCiudad (IGN Spain) Geocoding ===

CARTOCIUDAD_URL = (
    "https://www.cartociudad.es/geocoder/api/geocoder/candidatesJsonp"
)

# `no_process` tells CartoCiudad to skip lower-precision candidate types
# (toponym, municipality, autonomous community, population). What remains
# are the precise types we actually want: callejero (street) and portal
# (street entrance).
_CARTOCIUDAD_NO_PROCESS = "toponimo,municipio,comunidad autonoma,poblacion"

# Trailing apartment / complex / urbanization suffix tokens that CartoCiudad
# cannot parse as part of a street segment. When present, the geocoder
# returns zero candidates even though the street + number alone resolve
# cleanly (e.g. "C. Santa Gemma, 4 Urb. La Serra" → fails; stripped → OK).
# Matched case-insensitively; consumes from the token to end of string
# (suffixes commonly contain their own inner commas, e.g. "Urb. X, Casa 2").
_CARTOCIUDAD_SUFFIX_TOKENS = (
    "Urbanització",
    "Urbanizacion",
    "Urbanización",
    "Urb.",
    "Urb",
    "Apartament",
    "Apartamento",
    "Apt.",
    "Edifici",
    "Edificio",
    "Ed.",
    "Bloque",
    "Bloc",
    "Bq.",
    "Escala",
    "Esc.",
    "Esc",
    "Piso",
    "Pis",
    "Porta",
    "Puerta",
    "Pta.",
    "Pta",
)

# Build once. Longest tokens first so "Urb." wins over bare "Urb", etc.
_CARTOCIUDAD_SUFFIX_RE = re.compile(
    r"[\s,]+(?:" + "|".join(
        re.escape(t) for t in sorted(_CARTOCIUDAD_SUFFIX_TOKENS, key=len, reverse=True)
    ) + r")\b.*$",
    re.IGNORECASE,
)


def _strip_address_suffix_tokens(street: str) -> str:
    """Strip trailing apartment/complex/urbanization suffixes from a street.

    Returns the street with any match of `_CARTOCIUDAD_SUFFIX_RE` removed.
    Preserves the street name and house number untouched. Safe to call
    repeatedly (idempotent).
    """
    if not street:
        return street
    cleaned = _CARTOCIUDAD_SUFFIX_RE.sub("", street)
    return cleaned.rstrip(" ,").strip()


@dataclass(frozen=True)
class CartoCiudadResult:
    """Result of a CartoCiudad geocoding call.

    `rc` is the 14-char cadastral reference exposed by portal candidates;
    it is None for callejero candidates or when the field is absent.
    """

    lat: float
    lng: float
    rc: str | None
    type: str
    portal_number: int | None


def _cartociudad_cache_key(address: str, municipality: str, province: str) -> str:
    """Hash key for CartoCiudad cache."""
    key_str = (
        f"cartociudad_{address.lower().strip()}_"
        f"{municipality.lower().strip()}_{province.lower().strip()}"
    )
    return hashlib.sha256(key_str.encode()).hexdigest()[:12]


def _cartociudad_cache_load(
    address: str, municipality: str, province: str
) -> CartoCiudadResult | None | str:
    """Load cached CartoCiudad result.

    Returns:
        A CartoCiudadResult if cached; the sentinel string "__MISS__" if
        a prior lookup cached a negative result; None if not cached / expired.

    Backwards-compat: older cache payloads stored only {lat, lng}. Those are
    loaded cleanly with rc=None and type/portal_number defaulted.
    """
    if os.environ.get("G3DT_NO_CACHE") == "1":
        return None
    key = _cartociudad_cache_key(address, municipality, province)
    path = CARTOCIUDAD_CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        if datetime.now() - cached_at > timedelta(days=CARTOCIUDAD_CACHE_TTL_DAYS):
            path.unlink()
            return None
        result = data.get("result")
        if result is None:
            return "__MISS__"
        pn_raw = result.get("portal_number")
        try:
            pn = int(pn_raw) if pn_raw is not None else None
        except (TypeError, ValueError):
            pn = None
        return CartoCiudadResult(
            lat=float(result["lat"]),
            lng=float(result["lng"]),
            rc=result.get("rc"),
            type=str(result.get("type") or ""),
            portal_number=pn,
        )
    except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
        logger.warning(f"Invalid CartoCiudad cache file {path}: {e}")
        try:
            path.unlink()
        except OSError:
            pass
        return None


def _cartociudad_cache_save(
    address: str,
    municipality: str,
    province: str,
    result: CartoCiudadResult | None,
) -> None:
    """Persist CartoCiudad result (or a negative-result marker) atomically."""
    try:
        CARTOCIUDAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"Cannot create CartoCiudad cache dir: {e}")
        return
    key = _cartociudad_cache_key(address, municipality, province)
    path = CARTOCIUDAD_CACHE_DIR / f"{key}.json"
    payload: dict[str, Any] = {
        "cached_at": datetime.now().isoformat(),
        "query": {
            "address": address,
            "municipality": municipality,
            "province": province,
        },
        "result": (
            None if result is None
            else {
                "lat": result.lat,
                "lng": result.lng,
                "rc": result.rc,
                "type": result.type,
                "portal_number": result.portal_number,
            }
        ),
    }
    try:
        fd, temp_path = tempfile.mkstemp(dir=CARTOCIUDAD_CACHE_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            Path(temp_path).rename(path)
        except Exception:
            Path(temp_path).unlink(missing_ok=True)
            raise
    except OSError as e:
        logger.warning(f"Failed to cache CartoCiudad result: {e}")


def _parse_cartociudad_body(body: str) -> list[dict] | None:
    """Parse CartoCiudad response body.

    The endpoint is JSONP-ish: sometimes wrapped as `callback(...)` or
    similar, sometimes a raw JSON array. Return the parsed list, or None
    if the body can't be decoded.
    """
    if not body:
        return None
    text = body.strip()
    # Strip JSONP wrapper if present: `name(...);?`
    # Accept any identifier followed by `(`, ending with `)` or `);`.
    m = re.match(r"^[A-Za-z_$][\w$]*\s*\((.*)\)\s*;?\s*$", text, flags=re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"CartoCiudad JSON parse error: {e}")
        return None
    if data is None:
        return []
    if isinstance(data, dict):
        # Defensive: some JSONP-like endpoints wrap in {"results": [...]}
        for key in ("results", "candidates", "data"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return []
    if isinstance(data, list):
        return data
    return []


def _cartociudad_muni_matches(candidate_muni: str, query_muni: str) -> bool:
    """Accent/case-insensitive municipality match.

    Allows trailing suffixes in the candidate (e.g. "Benasque (Benás)").
    Returns True if either name is contained in the other after
    accent-stripping and upper-casing.
    """
    if not candidate_muni or not query_muni:
        return False
    c = _strip_accents(candidate_muni).upper().strip()
    q = _strip_accents(query_muni).upper().strip()
    if not c or not q:
        return False
    # Remove any parenthetical suffix from candidate: "Benasque (Benás)" → "BENASQUE"
    c_base = re.sub(r"\s*\(.*?\)\s*$", "", c).strip()
    return q in c_base or c_base in q or q in c or c in q


def _extract_house_number(address: str) -> int | None:
    """Parse the house number from an address string.

    Looks for the last standalone integer in the address (ignoring fractional
    suffixes like "4B" or "2 BIS"). Returns None if no number is found.

    Examples:
        "Santa Gemma 4" -> 4
        "Clot de la Llacuna 16" -> 16
        "Mestre Ramon Ortiz" -> None
        "Carrer X, 2" -> 2
    """
    if not address:
        return None
    # Find all integer runs; take the last one (house numbers trail street name).
    matches = re.findall(r"\b(\d+)\b", address)
    if not matches:
        return None
    try:
        return int(matches[-1])
    except ValueError:
        return None


def _pick_cartociudad_candidate(
    candidates: list[dict],
    municipality: str,
    wanted_number: int | None,
) -> dict | None:
    """Filter + rank CartoCiudad candidates and return the best match.

    Rules:
      - Drop candidates with (0,0) coords or mismatched municipality.
      - Prefer `portal` candidates over `callejero`.
      - When `wanted_number` is set, prefer a portal whose `portalNumber`
        matches exactly; otherwise fall back to the first portal.
    """
    portals: list[dict] = []
    callejeros: list[dict] = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        try:
            lat = float(c.get("lat") or 0.0)
            lng = float(c.get("lng") or 0.0)
        except (TypeError, ValueError):
            continue
        if lat == 0.0 and lng == 0.0:
            continue
        muni = str(c.get("muni") or "")
        if not _cartociudad_muni_matches(muni, municipality):
            continue
        ctype = str(c.get("type") or "").lower()
        if ctype == "portal":
            portals.append(c)
        elif ctype == "callejero":
            callejeros.append(c)

    if portals:
        if wanted_number is not None:
            for c in portals:
                pn = c.get("portalNumber")
                try:
                    if pn is not None and int(pn) == wanted_number:
                        return c
                except (TypeError, ValueError):
                    continue
        return portals[0]
    if callejeros:
        return callejeros[0]
    return None


def _cartociudad_fetch_candidates(
    query: str,
    municipality: str | None = None,
    limit: int = 5,
) -> list[dict] | None:
    """Fetch + parse CartoCiudad candidates for a query string.

    Applies server-side filters when available:
      - `municipio_filter=<name>` restricts candidates to a given municipality
        (human-readable name, not muniCode). Collapses noisy multi-town
        responses down to the target town's portals.
      - `no_process=<types>` skips lower-precision candidate types.
      - `limit=<N>` caps the candidate count.

    Returns the parsed candidate list (possibly empty) or None on HTTP/parse
    failure that should be treated as a hard error (not a negative result).
    """
    params = [("q", query)]
    if municipality:
        params.append(("municipio_filter", municipality))
    params.append(("no_process", _CARTOCIUDAD_NO_PROCESS))
    params.append(("limit", str(limit)))
    url = f"{CARTOCIUDAD_URL}?{urllib.parse.urlencode(params)}"
    logger.debug(f"CartoCiudad URL: {url}")

    headers = {
        "User-Agent": CARTOCIUDAD_USER_AGENT,
        "Accept": "application/json, text/javascript, */*",
    }
    request = urllib.request.Request(url, headers=headers)
    body: str | None = None
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT_SECONDS
            ) as response:
                body = response.read().decode("utf-8")
            break
        except urllib.error.HTTPError as e:
            logger.warning(f"CartoCiudad HTTP error {e.code}: {e}")
            return None
        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
                continue
            logger.warning(f"CartoCiudad connection failed: {e}")
            return None

    return _parse_cartociudad_body(body or "")


def cartociudad_geocode(
    address: str, municipality: str, province: str = ""
) -> CartoCiudadResult | None:
    """Geocode using CartoCiudad (IGN Spain) — entrance-level precision.

    Tends to outperform Nominatim for Catalan small towns, returning
    `portal` (entrance) coordinates rather than street-centerline. Portal
    candidates also carry a 14-char cadastral reference (`refCatastral`)
    which flows through as `CartoCiudadResult.rc`.

    Robustness notes:
      - CartoCiudad is sensitive to extra trailing tokens in the query
        (e.g. a province name as a third comma-separated segment makes
        some small-town addresses return zero candidates). If the first
        attempt produces nothing usable, we retry without the province.
      - When the input address contains a house number, we prefer the
        candidate whose ``portalNumber`` matches exactly rather than
        trusting the server's default order.

    Args:
        address: Street address (e.g. "Santa Gemma 4").
        municipality: Municipality name (e.g. "Vilanova de Segrià").
        province: Province name (optional; passed through to the query).

    Returns:
        CartoCiudadResult or None if no acceptable candidate.
    """
    if not address or not municipality:
        return None

    cached = _cartociudad_cache_load(address, municipality, province)
    if cached == "__MISS__":
        logger.debug(
            f"CartoCiudad cache negative-hit for '{address}, {municipality}'"
        )
        return None
    if cached is not None:
        assert isinstance(cached, CartoCiudadResult)
        logger.debug(
            f"CartoCiudad cache hit for '{address}, {municipality}' "
            f"-> ({cached.lat:.6f}, {cached.lng:.6f}) rc={cached.rc!r}"
        )
        return cached

    wanted_number = _extract_house_number(address)

    # Some inputs carry trailing apartment/complex/urbanization suffixes
    # (e.g. "C. Santa Gemma, 4 Urb. La Serra") that CartoCiudad cannot
    # parse — the query returns zero candidates even though the street +
    # number alone would resolve. We retry with the suffix stripped.
    stripped_address = _strip_address_suffix_tokens(address)
    if stripped_address != address:
        logger.debug(
            f"CartoCiudad suffix-strip: {address!r} -> {stripped_address!r}"
        )

    # Build queries most-specific → least. De-dupe so an already-clean
    # input doesn't cause identical retries.
    queries: list[str] = []
    seen: set[str] = set()

    def _enqueue(q: str) -> None:
        if q and q not in seen:
            queries.append(q)
            seen.add(q)

    if province:
        _enqueue(", ".join([address, municipality, province]))
    _enqueue(", ".join([address, municipality]))
    if stripped_address and stripped_address != address:
        if province:
            _enqueue(", ".join([stripped_address, municipality, province]))
        _enqueue(", ".join([stripped_address, municipality]))

    if not queries:
        return None

    picked: dict | None = None
    used_query: str = queries[0]
    total_raw = 0
    # Walk queries from most-specific to least. We retry a less-specific
    # query when the current one either:
    #   (a) returns zero candidates (province-segment rejection — Bug #1), or
    #   (b) returns candidates but none with an exact portalNumber match
    #       and we have a house number to pin — CartoCiudad's default order
    #       ranks by street-name similarity, not by street-number closeness,
    #       so a looser query sometimes surfaces the exact # (Bug #2).
    fallback: dict | None = None
    fallback_query: str = queries[0]
    for idx, query in enumerate(queries):
        candidates = _cartociudad_fetch_candidates(query, municipality=municipality)
        if candidates is None:
            # Hard HTTP/parse error: bail out (do not cache).
            return None
        total_raw += len(candidates)
        if not candidates:
            continue
        cand = _pick_cartociudad_candidate(candidates, municipality, wanted_number)
        if cand is None:
            continue
        # Exact-number match → done.
        if wanted_number is not None:
            pn_raw = cand.get("portalNumber")
            pn_int: int | None
            try:
                pn_int = int(pn_raw) if pn_raw is not None else None
            except (TypeError, ValueError):
                pn_int = None
            if pn_int == wanted_number:
                picked = cand
                used_query = query
                break
            # Only keep probing if this candidate exposes a (wrong) numeric
            # portalNumber AND a broader query remains to try. If the
            # candidate has no portalNumber field we can't do better by
            # retrying, so accept it.
            if pn_int is not None and idx < len(queries) - 1:
                if fallback is None:
                    fallback = cand
                    fallback_query = query
                continue
        # No house number to pin, or we've exhausted queries — accept.
        picked = cand
        used_query = query
        break
    if picked is None and fallback is not None:
        picked = fallback
        used_query = fallback_query

    if picked is None:
        logger.info(
            f"CartoCiudad: no acceptable candidate for '{queries[0]}' "
            f"(had {total_raw} raw results across {len(queries)} attempts)"
        )
        _cartociudad_cache_save(address, municipality, province, None)
        return None

    lat = float(picked["lat"])
    lng = float(picked["lng"])
    result_tag = str(picked.get("type") or "").lower()
    pn_raw = picked.get("portalNumber")
    try:
        pn_int = int(pn_raw) if pn_raw is not None else None
    except (TypeError, ValueError):
        pn_int = None
    rc_raw = picked.get("refCatastral")
    rc_val: str | None = None
    if isinstance(rc_raw, str):
        rc_stripped = rc_raw.strip()
        if rc_stripped:
            rc_val = rc_stripped
    result = CartoCiudadResult(
        lat=lat,
        lng=lng,
        rc=rc_val,
        type=result_tag,
        portal_number=pn_int,
    )
    logger.info(
        f"CartoCiudad geocoded '{used_query}' -> ({lat:.6f}, {lng:.6f}) "
        f"[type={result_tag}, muni={picked.get('muni')!r}, "
        f"portal={pn_int!r}, rc={rc_val!r}]"
    )
    _cartociudad_cache_save(address, municipality, province, result)
    return result


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


# === Cadastre/Nominatim Reconciliation ===

def _project_street_matches_cadastre(
    project_street_hint: str,
    rc: str,
    utm_x: float,
    utm_y: float,
    municipality: str | None = None,
    parcel_area: float | None = None,
) -> bool:
    """Check whether a Cadastre-resolved parcel actually lies on the expected
    project street.

    Uses the parcel's adjacents (from the Cadastre adjacents module) and
    checks whether any of the 4 adjacents contains the project's street
    name (accent-insensitive substring match, after prefix stripping).

    Returns True if at least one adjacent matches. Returns False on any
    error (conservative: if we can't verify, treat as wrong-parcel so the
    Nominatim fallback takes over).

    This is a best-effort guard; false negatives just trigger an extra
    Nominatim-based re-query which is still correct.
    """
    if not project_street_hint or not rc or not utm_x or not utm_y:
        return False

    # Strip street-type prefix from project hint for matching
    hint = _strip_street_type_word(project_street_hint.strip())
    hint_norm = _strip_accents(hint.upper()).strip()
    if not hint_norm:
        return False

    try:
        from .cadastre_adjacents import get_adjacent_parcels
    except ImportError:
        logger.debug("cadastre_adjacents not available; skipping street-match check")
        return False

    try:
        adjacents = get_adjacent_parcels(
            utm_x, utm_y,
            superficie=float(parcel_area) if parcel_area else 500.0,
            municipality=municipality,
            rc14=rc[:14] if len(rc) >= 14 else None,
        )
    except Exception as e:
        logger.debug(f"Street-match check: get_adjacent_parcels failed: {e}")
        return False

    for direction in ("north", "south", "east", "west"):
        adj = adjacents.get(direction) or ""
        adj_norm = _strip_accents(adj.upper())
        if hint_norm and hint_norm in adj_norm:
            logger.info(
                f"Street-match OK: project street '{hint}' found in "
                f"{direction} adjacent '{adj}'"
            )
            return True

    logger.warning(
        f"Street-match FAIL: project street '{hint}' not found in any adjacent "
        f"of RC {rc[:14]} ({list(adjacents.values())})"
    )
    return False


def _run_cadastre_and_nominatim_parallel(
    address: str,
    municipality: str,
    province: str,
    parsed_street: str,
    parsed_number: str,
) -> tuple[dict | None, tuple[float, float] | None]:
    """Run Cadastre progressive lookup and Nominatim geocoding concurrently.

    Returns (cadastre_result, nominatim_latlon). Either or both may be None.
    The two calls are independent HTTP requests — running them in parallel
    halves wall time without changing behavior.

    CartoCiudad is fired separately from the orchestrator so tests that
    monkeypatch this function keep working unchanged.
    """
    import concurrent.futures as _cf

    def _cadastre() -> dict | None:
        try:
            return cadastre_progressive_lookup(
                street_name=parsed_street,
                house_number=parsed_number,
                municipality_hint=municipality,
                province=province,
                full_address=address,
            )
        except Exception as e:
            logger.debug(f"Parallel cadastre branch failed: {e}")
            return None

    def _nominatim() -> tuple[float, float] | None:
        try:
            coords = nominatim_geocode_structured(
                address, municipality, province=province,
            )
            if coords is None:
                coords = nominatim_geocode(
                    address, municipality, province=province,
                )
            return coords
        except Exception as e:
            logger.debug(f"Parallel nominatim branch failed: {e}")
            return None

    with _cf.ThreadPoolExecutor(max_workers=2) as ex:
        fut_cad = ex.submit(_cadastre)
        fut_nom = ex.submit(_nominatim)
        return fut_cad.result(), fut_nom.result()


def _run_cadastre_and_alternates_parallel(
    address: str,
    municipality: str,
    province: str,
    parsed_street: str,
    parsed_number: str,
) -> tuple[dict | None, tuple[float, float] | None, CartoCiudadResult | None]:
    """Run Cadastre + Nominatim + CartoCiudad concurrently.

    Wraps `_run_cadastre_and_nominatim_parallel` (kept as a stable
    monkeypatch surface for existing tests) and adds CartoCiudad on its own
    worker.

    Returns (cadastre_result, nominatim_latlon, cartociudad_result).
    """
    import concurrent.futures as _cf

    def _cartociudad() -> CartoCiudadResult | None:
        try:
            return cartociudad_geocode(address, municipality, province=province)
        except Exception as e:
            logger.debug(f"Parallel cartociudad branch failed: {e}")
            return None

    with _cf.ThreadPoolExecutor(max_workers=2) as ex:
        fut_cc = ex.submit(_cartociudad)
        # Cadastre + Nominatim share their own internal 2-worker pool; we
        # kick them off in the main thread so test monkeypatches on
        # `_run_cadastre_and_nominatim_parallel` remain effective.
        cad, nom = _run_cadastre_and_nominatim_parallel(
            address=address,
            municipality=municipality,
            province=province,
            parsed_street=parsed_street,
            parsed_number=parsed_number,
        )
        cc = fut_cc.result()
    return cad, nom, cc


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

    # 2. PRIMARY PATH: Run Cadastre progressive lookup + Nominatim IN PARALLEL,
    #    then reconcile. Cadastre is the preferred source (gives exact RC),
    #    but its street fuzzy-matcher can return a wrong-parcel result on
    #    ambiguous street names. We verify by checking adjacents.
    rc: str | None = None
    centroid_x: float | None = None
    centroid_y: float | None = None
    utm_zone: int = 31  # default; overwritten by _wgs84_to_utm if conversion happens
    source = "geocode:cadastre_progressive"
    # Lat/lng of the reconciled candidate (if any), used to query ICGC API
    # Territorial as a one-call fast path for the parcel polygon + municipis
    # metadata on Catalan projects. See step 4 below.
    reconciled_latlng: tuple[float, float] | None = None

    # Extract components from address for progressive lookup
    sigla, parsed_street, parsed_number = _parse_address(address)

    cadastre_result, nominatim_coords, cartociudad_result = (
        _run_cadastre_and_alternates_parallel(
            address=address,
            municipality=municipality,
            province=province,
            parsed_street=parsed_street,
            parsed_number=parsed_number,
        )
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

    # 2a. RECONCILIATION: verify Cadastre's parcel actually lies on the
    #     expected street. If not, prefer Nominatim and re-query Cadastre
    #     by coordinate (RCCOOR) for the right parcel + adjacents.
    if (
        cadastre_result
        and rc is not None
        and centroid_x is not None
        and centroid_y is not None
        and parsed_street
    ):
        matches = _project_street_matches_cadastre(
            project_street_hint=parsed_street,
            rc=rc,
            utm_x=centroid_x,
            utm_y=centroid_y,
            municipality=municipality,
        )
        if not matches and (
            cartociudad_result is not None or nominatim_coords is not None
        ):
            # Prefer CartoCiudad (portal-level, IGN Spain) over Nominatim —
            # empirically higher precision for Catalan small towns.
            cc_rc_direct: str | None = None
            if cartociudad_result is not None:
                alt_source_tag = "cartociudad"
                alt_lat, alt_lon = cartociudad_result.lat, cartociudad_result.lng
                cc_rc_direct = cartociudad_result.rc
            else:
                alt_source_tag = "nominatim"
                assert nominatim_coords is not None  # for type checker
                alt_lat, alt_lon = nominatim_coords
            nx, ny, nz = _wgs84_to_utm(alt_lat, alt_lon)
            # If CartoCiudad already returned a 14-char RC (portal match),
            # use it directly and skip the RCCOOR re-query entirely. For
            # callejero candidates and Nominatim fallback, RC is unavailable
            # and we still need RCCOOR.
            new_rc: str | None = None
            if cc_rc_direct and len(cc_rc_direct) >= 14:
                new_rc = cc_rc_direct
                logger.warning(
                    f"Cadastre parcel {rc[:14]} does not border project street "
                    f"'{parsed_street}'. Using CartoCiudad portal UTM "
                    f"({nx:.0f}, {ny:.0f}) and RC {cc_rc_direct} directly."
                )
            else:
                logger.warning(
                    f"Cadastre parcel {rc[:14]} does not border project street "
                    f"'{parsed_street}'. Falling back to {alt_source_tag} UTM "
                    f"({nx:.0f}, {ny:.0f}) and re-querying Cadastre by coord."
                )
                try:
                    from .cadastre_adjacents import get_cadastral_reference
                    alt_rc, _ = get_cadastral_reference(nx, ny)
                    if alt_rc:
                        new_rc = alt_rc
                except Exception as e:
                    logger.debug(f"Reconciliation: RCCOOR re-query failed: {e}")
            centroid_x, centroid_y, utm_zone = nx, ny, nz
            rc = new_rc  # may be None — downstream handles that gracefully
            reconciled_latlng = (alt_lat, alt_lon)
            source = f"geocode:{alt_source_tag}+cadastre(reconciled)"

    # 3. FALLBACK: Nominatim + grid search (only if primary failed)
    if centroid_x is None:
        source = "geocode:nominatim_structured+cadastre"
        logger.info("Primary cadastre address lookup failed, falling back to Nominatim")
        # Reuse the parallel-fetched Nominatim result if available
        coords = nominatim_coords
        if coords is None:
            # Parallel branch didn't get anything — try once more sequentially
            # (belt-and-suspenders; network may have been flaky on the parallel run)
            coords = nominatim_geocode_structured(address, municipality, province=province)
            if coords is None:
                source = "geocode:nominatim+cadastre"
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

    # 4. Get parcel geometry (for point distribution).
    #    Fast path: on Catalan projects where we have a CartoCiudad lat/lng,
    #    call the ICGC API Territorial (one HTTP call returns the parcel
    #    polygon + municipis + sigpac + qualificacions-muc). Cross-verify
    #    its ``refcadp`` against CartoCiudad's RC and log a WARNING on
    #    disagreement. Fall back to the Cadastre WFS path on any failure.
    polygon: list[tuple[float, float]] | None = None
    _catalan_provs_for_icgc = {p.upper() for p in _CATALAN_PROVINCES}
    is_catalan_for_icgc = (
        province.upper() in _catalan_provs_for_icgc if province else True
    )
    # Only fire ICGC on the reconciliation branch — i.e., when the pipeline
    # has adopted CartoCiudad (or Nominatim) over Cadastre's parcel. On the
    # vanilla Cadastre happy path we trust the Cadastre WFS polygon to stay
    # consistent with the RC it just returned.
    icgc_latlng: tuple[float, float] | None = reconciled_latlng

    if is_catalan_for_icgc and icgc_latlng is not None:
        try:
            from . import icgc_territorial as _icgc_t
            icgc_response = _icgc_t.query_territorial(
                icgc_latlng[0], icgc_latlng[1]
            )
        except Exception as e:
            logger.debug(f"ICGC Territorial unavailable, will fall back: {e}")
            icgc_response = None

        if icgc_response:
            rc_icgc = _icgc_t.extract_refcadp(icgc_response)
            # Cross-verify against CartoCiudad's RC (not against the final
            # ``rc`` variable, which may have been overwritten by Cadastre).
            rc_cc = cartociudad_result.rc if cartociudad_result else None
            if rc_cc and rc_icgc and rc_cc[:14] != rc_icgc[:14]:
                logger.warning(
                    f"RC disagreement at ({icgc_latlng[0]:.5f},"
                    f"{icgc_latlng[1]:.5f}): CartoCiudad={rc_cc}, "
                    f"ICGC={rc_icgc}. Proceeding with CartoCiudad."
                )
            icgc_polygon = _icgc_t.extract_parcel_polygon_utm(icgc_response)
            if icgc_polygon and len(icgc_polygon) >= 3:
                polygon = icgc_polygon
                # Annotate the source tag so downstream diagnostics can tell
                # which path produced the polygon.
                if "icgc_territorial" not in source:
                    source = f"{source}+icgc_territorial"
            else:
                logger.debug(
                    "ICGC Territorial returned no parcel polygon; "
                    "falling back to Cadastre WFS."
                )

    if polygon is None and rc and len(rc) >= 14:
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
