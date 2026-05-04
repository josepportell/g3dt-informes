"""
Mapillary street-level image fetcher and analyzer.

Fetches and scores Mapillary street-level images for street-facing parcel
boundaries, then runs Groq vision analysis on the best images.

Usage:
    from automation.mapillary_client import fetch_and_analyze_street_edges

    results = fetch_and_analyze_street_edges(
        boundary_edges={"south": ((314500.0, 4611200.0), (0.0, -1.0))},
        parcel_centroid_utm=(314508.67, 4611192.86),
    )

Author: Eficients.cat
Date: 2026-03-28
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from automation import config

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MAPILLARY_API_URL = "https://graph.mapillary.com/images"
MAPILLARY_FIELDS = "id,captured_at,computed_geometry,compass_angle,thumb_1024_url,sequence"

DEFAULT_CACHE_DIR = config.cache_dir("mapillary")
CACHE_MAX_AGE_DAYS = 30

# Scoring weights
W_DISTANCE = 0.4
W_FACING = 0.3
W_RECENCY = 0.2
W_COVERAGE = 0.1

# Search radius around edge midpoint (metres)
SEARCH_RADIUS_M = 50.0

TOP_IMAGES_PER_EDGE = 3


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MapillaryImage:
    image_id: str
    lat: float
    lon: float
    compass_angle: float
    captured_at: int  # Unix timestamp seconds
    thumb_url: str
    sequence_id: str
    score: float
    thumb_path: Path | None  # After download


@dataclass
class MapillaryAnalysis:
    side: str
    visible_floors: int | None
    fence_type: str  # metal | wall | hedge | chain_link | none | not_visible
    gate_present: bool | None
    level_vs_street: str  # at_grade | above | below | not_determinable
    visible_pathology: str  # none_apparent | minor_cracks | significant | not_assessable
    confidence: str  # high | medium | low
    images_used: int


# ---------------------------------------------------------------------------
# UTM EPSG:25831 → WGS84 converter
# ---------------------------------------------------------------------------

def _utm_to_wgs84(utm_x: float, utm_y: float, zone: int = 31) -> tuple[float, float]:
    """Convert UTM EPSG:25831 (zone 31N) to WGS84 lat/lon."""
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1 - e2)
    k0 = 0.9996

    x = utm_x - 500000.0  # Remove false easting
    y = utm_y  # Northern hemisphere, no false northing

    M = y / k0
    mu = M / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))

    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

    phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
    phi1 += (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
    phi1 += (151 * e1**3 / 96) * math.sin(6 * mu)

    N1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    T1 = math.tan(phi1) ** 2
    C1 = e_prime2 * math.cos(phi1) ** 2
    R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    D = x / (N1 * k0)

    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D**2 / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1**2 - 9 * e_prime2) * D**4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1**2 - 252 * e_prime2 - 3 * C1**2)
        * D**6
        / 720
    )

    lon0 = math.radians((zone - 1) * 6 - 180 + 3)  # Central meridian
    lon = lon0 + (
        D
        - (1 + 2 * T1 + C1) * D**3 / 6
        + (5 - 2 * C1 + 28 * T1 - 3 * C1**2 + 8 * e_prime2 + 24 * T1**2)
        * D**5
        / 120
    ) / math.cos(phi1)

    return math.degrees(lat), math.degrees(lon)


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in metres."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Groq Vision call
# ---------------------------------------------------------------------------

def _call_groq_vision(
    prompt: str,
    images_b64: list[str],
    system_prompt: str,
    max_retries: int = 3,
) -> dict | None:
    """Call Groq Vision API with images and extraction prompt.

    Returns parsed JSON dict or None on failure.
    """
    import httpx

    api_key = config.GROQ_API_KEY
    if not api_key:
        logger.warning("Mapillary vision: no GROQ_API_KEY")
        return None

    content: list[dict] = [{"type": "text", "text": prompt}]
    for b64_img in images_b64:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
            }
        )

    payload = {
        "model": config.VISION_MODEL_GROQ,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    for attempt in range(1, max_retries + 1):
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    GROQ_API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            if resp.status_code == 429:
                logger.warning(
                    "Mapillary vision: rate limited (attempt %d/%d)",
                    attempt,
                    max_retries,
                )
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                return None

            if resp.status_code != 200:
                logger.warning(
                    "Mapillary vision: HTTP %d %s (attempt %d/%d)",
                    resp.status_code,
                    resp.text[:200],
                    attempt,
                    max_retries,
                )
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None

            data = resp.json()
            content_str = data["choices"][0]["message"]["content"]
            result = json.loads(content_str)

            usage = data.get("usage", {})
            logger.info(
                "Mapillary vision: ok in %dms (%d in + %d out tokens)",
                elapsed_ms,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            return result

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning(
                "Mapillary vision: %s (attempt %d/%d)", exc, attempt, max_retries
            )
            if attempt < max_retries:
                time.sleep(2)
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Mapillary API
# ---------------------------------------------------------------------------

def _query_mapillary(bbox_wgs84: tuple[float, float, float, float]) -> list[dict]:
    """Query Mapillary API v4 for images within a bounding box.

    Parameters
    ----------
    bbox_wgs84 : (west, south, east, north) in WGS84 decimal degrees.

    Returns list of image dicts, or empty list on error.
    """
    token = os.environ.get("MAPILLARY_ACCESS_TOKEN")
    if not token:
        return []

    west, south, east, north = bbox_wgs84
    params = {
        "access_token": token,
        "bbox": f"{west},{south},{east},{north}",
        "fields": MAPILLARY_FIELDS,
        "limit": "50",
    }

    url = f"{MAPILLARY_API_URL}?{urllib.parse.urlencode(params, safe=',')}"

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("data", [])
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Mapillary API: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_distance(dist_m: float) -> float:
    """Distance score: 1.0 for 5-20m, linear drop to 0 at 0m and 50m."""
    if dist_m < 0:
        return 0.0
    if dist_m < 5:
        return dist_m / 5.0
    if dist_m <= 20:
        return 1.0
    if dist_m < 50:
        return 1.0 - (dist_m - 20) / 30.0
    return 0.0


def _score_facing(compass_angle: float, angle_to_centroid: float) -> float:
    """Facing score: 1.0 if camera points toward centroid (delta < 30deg)."""
    delta = abs(compass_angle - angle_to_centroid) % 360
    if delta > 180:
        delta = 360 - delta
    if delta < 30:
        return 1.0
    if delta < 90:
        return 1.0 - (delta - 30) / 60.0
    return 0.0


def _score_recency(captured_at_s: int) -> float:
    """Recency score: 1.0 if within 1 year, linear drop to 0 at 5 years."""
    age_years = (time.time() - captured_at_s) / (365.25 * 86400)
    if age_years < 0:
        return 1.0
    if age_years <= 1:
        return 1.0
    if age_years < 5:
        return 1.0 - (age_years - 1) / 4.0
    return 0.0


def _score_coverage(sequence_id: str, sequence_counts: dict[str, int]) -> float:
    """Coverage score: 1.0 if sequence has 2+ images in result set."""
    return 1.0 if sequence_counts.get(sequence_id, 0) >= 2 else 0.0


def _angle_from_to(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing from point 1 to point 2, in degrees 0-360."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    bearing = math.degrees(math.atan2(x, y))
    return bearing % 360


def _score_images(
    raw_images: list[dict],
    midpoint_wgs84: tuple[float, float],
    centroid_wgs84: tuple[float, float],
) -> list[MapillaryImage]:
    """Parse, score, and sort Mapillary images. Returns best-first."""
    mid_lat, mid_lon = midpoint_wgs84
    cen_lat, cen_lon = centroid_wgs84

    # Count sequences for coverage score
    sequence_counts: dict[str, int] = {}
    for img in raw_images:
        seq = img.get("sequence", "")
        sequence_counts[seq] = sequence_counts.get(seq, 0) + 1

    scored: list[MapillaryImage] = []
    for img in raw_images:
        geom = img.get("computed_geometry")
        if not geom or geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        img_lon, img_lat = coords[0], coords[1]
        compass = img.get("compass_angle", 0.0)
        captured_ms = img.get("captured_at", 0)
        captured_s = captured_ms // 1000
        thumb_url = img.get("thumb_1024_url", "")
        sequence_id = img.get("sequence", "")
        image_id = str(img.get("id", ""))

        if not thumb_url or not image_id:
            continue

        dist_m = _haversine_m(mid_lat, mid_lon, img_lat, img_lon)
        angle_to_centroid = _angle_from_to(img_lat, img_lon, cen_lat, cen_lon)

        score = (
            W_DISTANCE * _score_distance(dist_m)
            + W_FACING * _score_facing(compass, angle_to_centroid)
            + W_RECENCY * _score_recency(captured_s)
            + W_COVERAGE * _score_coverage(sequence_id, sequence_counts)
        )

        scored.append(
            MapillaryImage(
                image_id=image_id,
                lat=img_lat,
                lon=img_lon,
                compass_angle=compass,
                captured_at=captured_s,
                thumb_url=thumb_url,
                sequence_id=sequence_id,
                score=score,
                thumb_path=None,
            )
        )

    scored.sort(key=lambda m: m.score, reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Thumbnail download
# ---------------------------------------------------------------------------

def _download_thumbnails(
    images: list[MapillaryImage],
    cache_dir: Path,
) -> list[MapillaryImage]:
    """Download thumbnails for images that don't have them cached yet."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[MapillaryImage] = []

    for img in images:
        dest = cache_dir / f"{img.image_id}.jpg"
        if dest.exists() and dest.stat().st_size > 0:
            img.thumb_path = dest
            downloaded.append(img)
            continue
        try:
            urllib.request.urlretrieve(img.thumb_url, dest)
            img.thumb_path = dest
            downloaded.append(img)
        except (urllib.error.URLError, OSError) as exc:
            logger.warning("Mapillary download %s: %s", img.image_id, exc)

    return downloaded


# ---------------------------------------------------------------------------
# Vision analysis
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert street-level image analyst specializing in construction "
    "site parcels in Catalunya, Spain. You analyze Mapillary photographs to "
    "describe parcel boundaries as seen from the street.\n"
    "Always respond with valid JSON only."
)


def _build_street_prompt(direction: str, street_name: str, n_images: int) -> str:
    """Build the vision prompt for street-edge analysis."""
    return (
        f"You are analyzing street-level photographs near a construction parcel "
        f"in Catalunya.\n"
        f"These {n_images} images show the {direction} edge of the parcel from "
        f'the street "{street_name}".\n\n'
        f"Describe ONLY what is visible. Return JSON:\n"
        f'{{\n'
        f'  "visible_floors": <int or null>,\n'
        f'  "fence_type": "metal" | "wall" | "hedge" | "chain_link" | "none" | "not_visible",\n'
        f'  "gate_present": true | false | null,\n'
        f'  "level_vs_street": "at_grade" | "above" | "below" | "not_determinable",\n'
        f'  "visible_pathology": "none_apparent" | "minor_cracks" | "significant" | "not_assessable",\n'
        f'  "confidence": "high" | "medium" | "low"\n'
        f'}}\n'
        f"Do not infer hidden features."
    )


def _analyze_edge_images(
    images: list[MapillaryImage],
    direction: str,
    street_name: str,
) -> MapillaryAnalysis | None:
    """Run Groq vision on downloaded images for one edge."""
    b64_images: list[str] = []
    for img in images:
        if img.thumb_path and img.thumb_path.exists():
            try:
                b64_images.append(
                    base64.b64encode(img.thumb_path.read_bytes()).decode()
                )
            except OSError:
                continue

    if not b64_images:
        return None

    prompt = _build_street_prompt(direction, street_name, len(b64_images))
    raw = _call_groq_vision(prompt, b64_images, _SYSTEM_PROMPT)
    if raw is None:
        return None

    floors = raw.get("visible_floors")
    if floors is not None:
        try:
            floors = int(floors)
        except (ValueError, TypeError):
            floors = None

    gate = raw.get("gate_present")
    if gate is not None and not isinstance(gate, bool):
        gate = None

    return MapillaryAnalysis(
        side=direction,
        visible_floors=floors,
        fence_type=raw.get("fence_type", "not_visible"),
        gate_present=gate,
        level_vs_street=raw.get("level_vs_street", "not_determinable"),
        visible_pathology=raw.get("visible_pathology", "not_assessable"),
        confidence=raw.get("confidence", "low"),
        images_used=len(b64_images),
    )


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

def _cache_key(centroid_utm: tuple[float, float]) -> str:
    """Deterministic hash from centroid coordinates."""
    raw = f"{centroid_utm[0]:.2f},{centroid_utm[1]:.2f}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_cache(cache_dir: Path) -> dict[str, MapillaryAnalysis] | None:
    """Load cached analysis if fresh enough."""
    analysis_path = cache_dir / "analysis.json"
    if not analysis_path.exists():
        return None

    age_days = (time.time() - analysis_path.stat().st_mtime) / 86400
    if age_days > CACHE_MAX_AGE_DAYS:
        return None

    try:
        data = json.loads(analysis_path.read_text())
        results: dict[str, MapillaryAnalysis] = {}
        for direction, entry in data.items():
            results[direction] = MapillaryAnalysis(
                side=entry["side"],
                visible_floors=entry.get("visible_floors"),
                fence_type=entry.get("fence_type", "not_visible"),
                gate_present=entry.get("gate_present"),
                level_vs_street=entry.get("level_vs_street", "not_determinable"),
                visible_pathology=entry.get("visible_pathology", "not_assessable"),
                confidence=entry.get("confidence", "low"),
                images_used=entry.get("images_used", 0),
            )
        logger.info("Mapillary: loaded cached analysis (%d edges)", len(results))
        return results
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Mapillary: cache load failed: %s", exc)
        return None


def _save_cache(cache_dir: Path, results: dict[str, MapillaryAnalysis]) -> None:
    """Persist analysis results to cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, dict] = {}
    for direction, analysis in results.items():
        data[direction] = {
            "side": analysis.side,
            "visible_floors": analysis.visible_floors,
            "fence_type": analysis.fence_type,
            "gate_present": analysis.gate_present,
            "level_vs_street": analysis.level_vs_street,
            "visible_pathology": analysis.visible_pathology,
            "confidence": analysis.confidence,
            "images_used": analysis.images_used,
        }
    (cache_dir / "analysis.json").write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_and_analyze_street_edges(
    boundary_edges: dict[str, tuple[tuple[float, float], tuple[float, float]]],
    parcel_centroid_utm: tuple[float, float],
    cache_dir: Path | None = None,
    street_names: dict[str, str] | None = None,
) -> dict[str, MapillaryAnalysis]:
    """Fetch Mapillary images for street-facing edges and analyze them.

    Parameters
    ----------
    boundary_edges : dict
        ``{direction: (midpoint_utm, normal_utm)}`` -- only street-facing edges.
        Midpoint and normal are in EPSG:25831.
    parcel_centroid_utm : tuple
        ``(easting, northing)`` of the parcel centroid in EPSG:25831.
    cache_dir : Path | None
        Override cache directory. Defaults to ``~/.g3dt/cache/mapillary/{hash}``.
    street_names : dict | None
        Optional ``{direction: street_name}`` for richer vision prompts.

    Returns
    -------
    dict[str, MapillaryAnalysis]
        Keyed by direction (north/south/east/west).
        Returns empty dict if MAPILLARY_ACCESS_TOKEN not set or no coverage.
    """
    if not os.environ.get("MAPILLARY_ACCESS_TOKEN"):
        logger.info("Mapillary: MAPILLARY_ACCESS_TOKEN not set, skipping")
        return {}

    # Resolve cache directory
    key = _cache_key(parcel_centroid_utm)
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR / key
    else:
        cache_dir = cache_dir / key

    # Check cache
    cached = _load_cache(cache_dir)
    if cached is not None:
        return cached

    centroid_wgs84 = _utm_to_wgs84(parcel_centroid_utm[0], parcel_centroid_utm[1])
    street_names = street_names or {}

    results: dict[str, MapillaryAnalysis] = {}

    for direction, (midpoint_utm, _normal_utm) in boundary_edges.items():
        try:
            mid_lat, mid_lon = _utm_to_wgs84(midpoint_utm[0], midpoint_utm[1])

            # Build bbox: midpoint +/- ~50m in WGS84
            # Approximate: 1 degree lat ~ 111320m, 1 degree lon ~ 111320*cos(lat)m
            dlat = SEARCH_RADIUS_M / 111320.0
            dlon = SEARCH_RADIUS_M / (111320.0 * math.cos(math.radians(mid_lat)))
            bbox = (mid_lon - dlon, mid_lat - dlat, mid_lon + dlon, mid_lat + dlat)

            raw_images = _query_mapillary(bbox)
            if not raw_images:
                logger.info("Mapillary: sense cobertura al %s", direction)
                continue

            scored = _score_images(raw_images, (mid_lat, mid_lon), centroid_wgs84)
            top = scored[:TOP_IMAGES_PER_EDGE]
            logger.info(
                "Mapillary: %d images found for %s (top score %.2f)",
                len(raw_images),
                direction,
                top[0].score if top else 0.0,
            )

            downloaded = _download_thumbnails(top, cache_dir)
            if not downloaded:
                continue

            street_name = street_names.get(direction, "unknown")
            analysis = _analyze_edge_images(downloaded, direction, street_name)
            if analysis is not None:
                results[direction] = analysis

        except Exception:
            logger.warning("Mapillary: error processing %s edge", direction, exc_info=True)
            continue

    # Save cache if we got results
    if results:
        _save_cache(cache_dir, results)

    return results
