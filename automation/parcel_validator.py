"""
Cadastre WMS map download and optional Groq vision validation for parcel
resolution decisions (merges, wrong-parcel fixes).

Downloads a Cadastre WMS image centered on the resolved parcel, optionally
overlays the parcel polygon, and can compare against the architect's plan
via Groq Llama 4 Scout vision.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
import urllib.request
import urllib.error
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

CADASTRE_WMS_URL = "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx"

GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

CACHE_DIR = Path.home() / ".g3dt" / "cache" / "cadastre_maps"
CACHE_TTL_DAYS = 30

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class ParcelValidation:
    parcels_match: bool | None  # Does Cadastre match the planol?
    suggested_merge: list[str] = field(default_factory=list)  # Cadastral refs to merge
    streets_by_direction: dict[str, str] = field(default_factory=dict)  # {north: "...", ...}
    confidence: str = "low"  # high | medium | low


# ---------------------------------------------------------------------------
# Env loader (same pattern as ortho_vision.py)
# ---------------------------------------------------------------------------


def _load_env() -> None:
    """Load .env file from project root if not already loaded."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


# ---------------------------------------------------------------------------
# Groq Vision call (duplicated pattern from ortho_vision.py)
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are an expert cadastral map analyst specializing in Spanish Cadastre "
    "(Catastro) maps for municipalities in Catalunya. You identify parcel "
    "boundaries, street names, building footprints, and parcel numbers.\n"
    "Always respond with valid JSON only."
)


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

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.warning("parcel_validator: no GROQ_API_KEY set")
        return None

    content: list[dict] = [{"type": "text", "text": prompt}]
    for b64_img in images_b64:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_img}"},
            }
        )

    payload = {
        "model": GROQ_VISION_MODEL,
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
                    "parcel_validator: rate limited (attempt %d/%d)",
                    attempt,
                    max_retries,
                )
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                return None

            if resp.status_code != 200:
                logger.warning(
                    "parcel_validator: HTTP %d %s (attempt %d/%d)",
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
                "parcel_validator: Groq ok in %dms (%d in + %d out tokens)",
                elapsed_ms,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            return result

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning(
                "parcel_validator: %s (attempt %d/%d)", exc, attempt, max_retries
            )
            if attempt < max_retries:
                time.sleep(2)
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def _encode_image(path: Path) -> str | None:
    """Read an image file and return base64-encoded string, or None."""
    try:
        return base64.b64encode(path.read_bytes()).decode()
    except OSError as exc:
        logger.warning("parcel_validator: cannot read %s: %s", path, exc)
        return None


def _cache_path_for(utm_x: float, utm_y: float, buffer_m: float) -> Path:
    """Deterministic cache path based on coordinates and buffer."""
    key = f"{utm_x:.2f}_{utm_y:.2f}_{buffer_m:.1f}"
    sha = hashlib.sha256(key.encode()).hexdigest()
    return CACHE_DIR / f"{sha}.png"


def _is_cache_valid(path: Path) -> bool:
    """Check if a cached file exists and is within TTL."""
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return datetime.now() - mtime < timedelta(days=CACHE_TTL_DAYS)


# ---------------------------------------------------------------------------
# Cadastre WMS download
# ---------------------------------------------------------------------------


def download_cadastre_map(
    utm_x: float,
    utm_y: float,
    output_path: Path,
    buffer_m: float = 80.0,
    width: int = 800,
    height: int = 800,
) -> Path | None:
    """Download Cadastre WMS map centered on UTM coords. Returns path or None."""
    xmin = utm_x - buffer_m
    ymin = utm_y - buffer_m
    xmax = utm_x + buffer_m
    ymax = utm_y + buffer_m

    url = (
        f"{CADASTRE_WMS_URL}"
        f"?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
        f"&LAYERS=Catastro"
        f"&SRS=EPSG:25831"
        f"&BBOX={xmin},{ymin},{xmax},{ymax}"
        f"&WIDTH={width}&HEIGHT={height}"
        f"&FORMAT=image/png"
        f"&TRANSPARENT=false"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        urllib.request.urlretrieve(url, str(output_path))
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        logger.warning("parcel_validator: WMS download failed: %s", exc)
        output_path.unlink(missing_ok=True)
        return None

    # Validate PNG header
    try:
        with open(output_path, "rb") as f:
            header = f.read(4)
        if header[:4] != b"\x89PNG":
            logger.warning("parcel_validator: WMS response is not PNG (likely error XML)")
            output_path.unlink(missing_ok=True)
            return None
    except OSError as exc:
        logger.warning("parcel_validator: cannot read downloaded file: %s", exc)
        return None

    logger.info("parcel_validator: Cadastre map saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def _draw_red_dot(img_path: Path, utm_x: float, utm_y: float, bbox: tuple[float, float, float, float]) -> None:
    """Draw a red dot at the center point on an existing image."""
    from PIL import Image, ImageDraw

    img = Image.open(str(img_path)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    xmin, ymin, xmax, ymax = bbox
    img_w, img_h = img.size
    px = (utm_x - xmin) / (xmax - xmin) * img_w
    py = img_h - (utm_y - ymin) / (ymax - ymin) * img_h
    r = 8
    draw.ellipse(
        [px - r, py - r, px + r, py + r],
        fill="red",
        outline="darkred",
        width=2,
    )
    img.convert("RGB").save(str(img_path), "PNG")


def _draw_polygon_overlay(
    img_path: Path,
    polygon_utm: list[tuple[float, float]],
    bbox: tuple[float, float, float, float],
) -> None:
    """Draw a red parcel polygon outline on an existing image."""
    from PIL import Image, ImageDraw

    if len(polygon_utm) < 3:
        return

    xmin, ymin, xmax, ymax = bbox
    img = Image.open(str(img_path)).convert("RGBA")
    img_w, img_h = img.size

    pixel_coords = []
    for vx, vy in polygon_utm:
        px = (vx - xmin) / (xmax - xmin) * img_w
        py = img_h - (vy - ymin) / (ymax - ymin) * img_h
        pixel_coords.append((px, py))

    # Semi-transparent red fill
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.polygon(pixel_coords, fill=(255, 0, 0, 40))
    img = Image.alpha_composite(img, overlay)

    # Red outline (multiple passes for thickness)
    draw = ImageDraw.Draw(img)
    draw.polygon(pixel_coords, outline="red")
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = [(x + dx, y + dy) for x, y in pixel_coords]
        draw.polygon(shifted, outline="red")

    img.convert("RGB").save(str(img_path), "PNG")


# ---------------------------------------------------------------------------
# Vision prompt
# ---------------------------------------------------------------------------


_PARCEL_VISION_PROMPT = """\
You are analyzing a cadastral map from the Spanish Cadastre (Catastro) showing \
parcel boundaries, building footprints, and street names in a municipality in \
Catalunya.

The red dot marks the center of the project parcel. The known cadastral \
reference is {rc14}.

{merge_context}

Analyze the map and return JSON:
{{
  "streets_visible": {{
    "north": "<street name visible on the north side, or empty>",
    "south": "<street name visible on the south side, or empty>",
    "east": "<street name visible on the east side, or empty>",
    "west": "<street name visible on the west side, or empty>"
  }},
  "building_footprints_visible": true | false,
  "parcel_appears_subdivided": true | false,
  "adjacent_parcel_numbers": ["<any visible parcel numbers near the project>"],
  "confidence": "high" | "medium" | "low"
}}"""


def _build_merge_context(
    polygon_utm: list[tuple[float, float]] | None,
    merged_refs: list[str] | None,
    planol_image_path: Path | None,
) -> str:
    """Build the merge_context portion of the vision prompt."""
    parts: list[str] = []
    if polygon_utm:
        parts.append("The project parcel polygon is outlined in red.")
    if merged_refs:
        parts.append(
            f"The parcel was merged from {', '.join(merged_refs)}. "
            "Verify this makes sense geographically."
        )
    if planol_image_path:
        parts.append(
            "A second image shows the architect's plan. "
            "Compare the building footprint."
        )
    return " ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_parcel(
    utm_x: float,
    utm_y: float,
    polygon_utm: list[tuple[float, float]] | None = None,
    planol_image_path: Path | None = None,
    cadastre_adjacents: dict[str, str] | None = None,
    rc14: str = "",
    merged_refs: list[str] | None = None,
    buffer_m: float = 80.0,
) -> ParcelValidation | None:
    """Validate parcel resolution using Cadastre WMS + optional LLM vision.

    If planol_image_path is provided AND GROQ_API_KEY is set, runs LLM
    comparison. Otherwise, just downloads the Cadastre map for evidence.

    Parameters
    ----------
    utm_x, utm_y : float
        Center coordinates in EPSG:25831.
    polygon_utm : list of (x, y) tuples or None
        Parcel polygon vertices for overlay drawing.
    planol_image_path : Path or None
        Architect's plan image for vision comparison.
    cadastre_adjacents : dict or None
        Known adjacents per direction from Cadastre API.
    rc14 : str
        14-character cadastral reference.
    merged_refs : list of str or None
        Cadastral references that were merged.
    buffer_m : float
        Buffer around center point in meters for WMS request.

    Returns
    -------
    ParcelValidation or None
        Validation result, or None on complete failure.
    """
    _load_env()

    # --- Download Cadastre map (cached) ------------------------------------
    cache_path = _cache_path_for(utm_x, utm_y, buffer_m)
    bbox = (utm_x - buffer_m, utm_y - buffer_m, utm_x + buffer_m, utm_y + buffer_m)

    if _is_cache_valid(cache_path):
        logger.info("parcel_validator: cache hit %s", cache_path)
        map_path = cache_path
    else:
        map_path = download_cadastre_map(utm_x, utm_y, cache_path, buffer_m=buffer_m)

    if map_path is None:
        logger.warning("parcel_validator: could not obtain Cadastre map")
        return None

    # --- Draw overlay on a working copy ------------------------------------
    working_path = map_path.with_suffix(".annotated.png")
    try:
        import shutil
        shutil.copy2(map_path, working_path)
    except OSError as exc:
        logger.warning("parcel_validator: copy failed: %s", exc)
        return None

    if polygon_utm:
        _draw_polygon_overlay(working_path, polygon_utm, bbox)
    else:
        _draw_red_dot(working_path, utm_x, utm_y, bbox)

    # --- Vision validation (optional) --------------------------------------
    api_key = os.environ.get("GROQ_API_KEY")
    has_vision = api_key and (planol_image_path or polygon_utm or rc14)

    if not has_vision:
        logger.info("parcel_validator: map downloaded, no vision analysis requested")
        return ParcelValidation(
            parcels_match=None,
            streets_by_direction=cadastre_adjacents or {},
            confidence="low",
        )

    # Encode images
    images_b64: list[str] = []
    map_b64 = _encode_image(working_path)
    if map_b64 is None:
        return ParcelValidation(
            parcels_match=None,
            streets_by_direction=cadastre_adjacents or {},
            confidence="low",
        )
    images_b64.append(map_b64)

    if planol_image_path is not None:
        planol_b64 = _encode_image(planol_image_path)
        if planol_b64:
            images_b64.append(planol_b64)

    merge_context = _build_merge_context(polygon_utm, merged_refs, planol_image_path)
    prompt = _PARCEL_VISION_PROMPT.format(rc14=rc14, merge_context=merge_context)

    raw = _call_groq_vision(prompt, images_b64, _SYSTEM_PROMPT)
    if raw is None:
        logger.warning("parcel_validator: vision call failed, returning map-only result")
        return ParcelValidation(
            parcels_match=None,
            streets_by_direction=cadastre_adjacents or {},
            confidence="low",
        )

    # --- Parse vision result -----------------------------------------------
    streets = raw.get("streets_visible", {})
    streets_by_dir: dict[str, str] = {}
    for direction in ("north", "south", "east", "west"):
        val = streets.get(direction, "")
        if isinstance(val, str) and val.strip():
            streets_by_dir[direction] = val.strip()

    subdivided = raw.get("parcel_appears_subdivided", False)
    adjacent_nums = raw.get("adjacent_parcel_numbers", [])

    # Determine match: if planol was provided, check building_footprints_visible
    parcels_match: bool | None = None
    if planol_image_path is not None and len(images_b64) > 1:
        footprints = raw.get("building_footprints_visible", False)
        parcels_match = bool(footprints) and not subdivided

    suggested_merge: list[str] = []
    if subdivided and isinstance(adjacent_nums, list):
        suggested_merge = [str(n) for n in adjacent_nums if n]

    confidence = raw.get("confidence", "low")
    if confidence not in ("high", "medium", "low"):
        confidence = "low"

    return ParcelValidation(
        parcels_match=parcels_match,
        suggested_merge=suggested_merge,
        streets_by_direction=streets_by_dir,
        confidence=confidence,
    )
