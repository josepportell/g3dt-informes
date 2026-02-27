#!/usr/bin/env python3
"""
UTM Coordinate Geocoding Fallback

When a project has no COORDENADES.txt (no GPS from fieldwork), derives
approximate UTM coordinates from the project street address using:
1. Nominatim (OpenStreetMap) for address -> lat/lon
2. Spanish Cadastre OVC API for parcel identification
3. Cadastre INSPIRE WFS for parcel geometry in EPSG:25831
4. ICGC MDT for elevations

Author: Eficients.cat
Date: 2026-02-27
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

__all__ = ['geocode_project', 'GeocodeError']


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

# Cadastre API endpoints
CADASTRE_URL = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCoordenadas.asmx"
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

def _wgs84_to_utm31n(lat: float, lon: float) -> tuple[float, float]:
    """
    Convert WGS84 lat/lon to UTM zone 31N (EPSG:25831).

    Standard UTM projection (Snyder series to 4th order), sub-meter accuracy
    for the coordinate conversion itself. Overall geocoding accuracy depends
    on the input lat/lon source (Nominatim: ~50-200m typical).

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees

    Returns:
        Tuple of (utm_x, utm_y)
    """
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lon0 = math.radians(3.0)  # Central meridian for zone 31

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


# === Nominatim Geocoding ===

def nominatim_geocode(address: str, municipality: str) -> tuple[float, float] | None:
    """
    Geocode an address using Nominatim (OpenStreetMap).

    Args:
        address: Street address
        municipality: Municipality name

    Returns:
        Tuple of (lat, lon) or None if not found
    """
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
) -> dict | None:
    """
    Geocode a project address to UTM coordinates.

    Orchestrates the full pipeline:
    1. Check cache
    2. Nominatim geocode address -> lat/lon
    3. Cadastre parcel lookup -> cadastral reference
    4. Cadastre WFS -> parcel geometry in EPSG:25831
    5. Distribute investigation points within parcel
    6. Get elevations from ICGC MDT
    7. Generate COORDENADES.txt if output_dir provided
    8. Cache result

    Falls back gracefully at each step. If geometry is unavailable but
    lat/lon is available, converts to UTM and places all points at centroid.

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

    # 2. Nominatim geocode
    coords = nominatim_geocode(address, municipality)
    if coords is None:
        logger.warning(f"Geocoding failed for '{address}, {municipality}'")
        return None

    lat, lon = coords

    # 3. Cadastre parcel lookup
    parcel = cadastre_find_parcel(lat, lon, address)
    rc = parcel["rc"] if parcel else None

    # 4. Get parcel geometry
    polygon: list[tuple[float, float]] | None = None
    if rc and len(rc) >= 14:
        try:
            polygon = get_parcel_geometry_utm(rc[:14])
        except GeocodeError as e:
            logger.warning(f"Could not get parcel geometry for {rc[:14]}: {e}")

    # 5. Distribute points and compute centroid UTM
    if polygon and len(polygon) >= 3:
        # Centroid from polygon
        n = len(polygon)
        centroid_x = sum(p[0] for p in polygon) / n
        centroid_y = sum(p[1] for p in polygon) / n
        points = distribute_points(polygon, point_ids)
    else:
        # Fallback: convert Nominatim lat/lon to UTM
        centroid_x, centroid_y = _wgs84_to_utm31n(lat, lon)
        # Place all points at centroid
        points = {pid: {"x": centroid_x, "y": centroid_y} for pid in point_ids}

    # 6. Validate centroid within Catalonia bounds
    if not (CATALUNYA_UTM_X_MIN <= centroid_x <= CATALUNYA_UTM_X_MAX):
        logger.warning(f"Centroid UTM X {centroid_x} outside Catalonia bounds")
        return None
    if not (CATALUNYA_UTM_Y_MIN <= centroid_y <= CATALUNYA_UTM_Y_MAX):
        logger.warning(f"Centroid UTM Y {centroid_y} outside Catalonia bounds")
        return None

    # 7. Get elevations for each point
    elevations: dict[str, float] = {}
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
        "source": "geocode:nominatim+cadastre",
    }

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
