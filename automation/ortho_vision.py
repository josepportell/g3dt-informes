"""
Groq Llama 4 Scout vision analysis on ICGC orthophoto chips.

Extracts structured micro-fields about a construction site parcel
and its boundaries from aerial imagery.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from automation import config

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert aerial image analyst specializing in cadastral parcels "
    "in Catalunya, Spain. You analyze orthophotos to describe land use, "
    "buildings, vegetation, and parcel boundaries.\n"
    "Always respond with valid JSON only."
)

_WIDE_CHIP_PROMPT = """\
You are analyzing an aerial orthophoto context view of a construction site \
parcel (outlined in red) in Catalunya.
The red-outlined parcel is the subject site. Describe the parcel and its \
surroundings.

Return JSON:
{{
  "is_anthropized": true | false,
  "nearby_building_pattern": "residential_detached" | "residential_terraced" \
| "industrial" | "mixed" | "agricultural" | "none",
  "general_surface": "urban_paved" | "urban_mixed" | "periurban" | "rural" \
| "agricultural",
  "parcel_surface_state": "paved" | "unpaved" | "gravel" | "vegetation" \
| "bare_soil" | "mixed",
  "parcel_occupied": true | false,
  "subsoil_visible": true | false,
  "confidence": "high" | "medium" | "low"
}}"""

_BOUNDARY_STRIP_PROMPT = """\
You are analyzing an orthophoto of a parcel boundary in Catalunya.
The parcel is outlined in red. You are looking at the {direction} edge.
The Cadastre API reports this side as: "{cadastre_label}".

Describe ONLY what is visible in the image. Return JSON:
{{
  "adjacency_type": "street" | "neighboring_parcel" | "open_edge" \
| "uncertain",
  "building_presence": true | false,
  "building_detached": true | false | null,
  "estimated_visible_floors": <int or null>,
  "surface_state": "paved" | "unpaved" | "gravel" | "vegetation" | "mixed" \
| "uncertain",
  "enclosure_visible": "wall" | "fence" | "hedge" | "curb" | "none" \
| "uncertain",
  "vegetation_state": "low_herbaceous" | "trees_shrubs" | "dense" | "sparse" \
| "none",
  "access_visible": true | false,
  "confidence": "high" | "medium" | "low"
}}
Do not infer hidden features or legal land use."""

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

_EVIDENCE_ORTHO = "icgc_ortho"


@dataclass
class BoundaryAnalysis:
    side: str
    cadastre_label: str
    adjacency_type: str
    building_presence: bool
    building_detached: bool | None
    estimated_visible_floors: int | None
    surface_state: str
    enclosure_visible: str
    vegetation_state: str
    access_visible: bool
    confidence: str
    evidence_source: str = _EVIDENCE_ORTHO


@dataclass
class SiteAnalysis:
    is_anthropized: bool
    nearby_building_pattern: str
    general_surface: str
    parcel_surface_state: str
    parcel_occupied: bool
    subsoil_visible: bool
    confidence: str
    boundary_analyses: dict[str, BoundaryAnalysis] = field(default_factory=dict)


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
        logger.warning("Groq ortho vision: no API key")
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
                    "Groq ortho vision: rate limited (attempt %d/%d)",
                    attempt,
                    max_retries,
                )
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                return None

            if resp.status_code != 200:
                logger.warning(
                    "Groq ortho vision: HTTP %d %s (attempt %d/%d)",
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
                "Groq ortho vision: ok in %dms (%d in + %d out tokens)",
                elapsed_ms,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            return result

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning(
                "Groq ortho vision: %s (attempt %d/%d)", exc, attempt, max_retries
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
        logger.warning("ortho_vision: cannot read %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Cadastre label parsing (fallback when vision fails)
# ---------------------------------------------------------------------------

_STREET_KEYWORDS = (
    "carrer", "avinguda", "passeig", "placa", "plaça", "ronda", "camí",
    "cami", "travessia", "autopista", "carretera", "via", "calle", "avenida",
    "paseo", "plaza", "rda", "c/", "av.", "pg.", "ctra",
)


def _infer_adjacency_from_cadastre(label: str) -> str:
    """Best-effort adjacency type from Cadastre text."""
    low = label.lower()
    if any(kw in low for kw in _STREET_KEYWORDS):
        return "street"
    if "parcel" in low:
        return "neighboring_parcel"
    return "uncertain"


def _fallback_boundary(side: str, cadastre_label: str) -> BoundaryAnalysis:
    """Create a minimal BoundaryAnalysis from Cadastre label alone."""
    adj = _infer_adjacency_from_cadastre(cadastre_label)
    return BoundaryAnalysis(
        side=side,
        cadastre_label=cadastre_label,
        adjacency_type=adj,
        building_presence=False,
        building_detached=None,
        estimated_visible_floors=None,
        surface_state="uncertain",
        enclosure_visible="uncertain",
        vegetation_state="none",
        access_visible=(adj == "street"),
        confidence="low",
        evidence_source="cadastre_label_only",
    )


# ---------------------------------------------------------------------------
# Vision analysis helpers
# ---------------------------------------------------------------------------

def _analyze_wide_chip(b64: str) -> dict | None:
    """Run context-view analysis on the wide chip."""
    return _call_groq_vision(_WIDE_CHIP_PROMPT, [b64], _SYSTEM_PROMPT)


def _analyze_boundary_strip(direction: str, cadastre_label: str, b64: str) -> dict | None:
    """Run boundary analysis on a single edge strip."""
    prompt = _BOUNDARY_STRIP_PROMPT.format(
        direction=direction, cadastre_label=cadastre_label,
    )
    return _call_groq_vision(prompt, [b64], _SYSTEM_PROMPT)


def _parse_boundary_result(
    side: str,
    cadastre_label: str,
    raw: dict,
) -> BoundaryAnalysis:
    """Convert raw Groq JSON to BoundaryAnalysis with safe defaults."""
    floors = raw.get("estimated_visible_floors")
    if floors is not None:
        try:
            floors = int(floors)
        except (ValueError, TypeError):
            floors = None

    detached = raw.get("building_detached")
    if detached is not None and not isinstance(detached, bool):
        detached = None

    return BoundaryAnalysis(
        side=side,
        cadastre_label=cadastre_label,
        adjacency_type=raw.get("adjacency_type", "uncertain"),
        building_presence=bool(raw.get("building_presence", False)),
        building_detached=detached,
        estimated_visible_floors=floors,
        surface_state=raw.get("surface_state", "uncertain"),
        enclosure_visible=raw.get("enclosure_visible", "uncertain"),
        vegetation_state=raw.get("vegetation_state", "none"),
        access_visible=bool(raw.get("access_visible", False)),
        confidence=raw.get("confidence", "low"),
        evidence_source=_EVIDENCE_ORTHO,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_site(
    tight_chip_path: Path | None,
    wide_chip_path: Path | None,
    boundary_strip_paths: dict[str, Path],
    cadastre_adjacents: dict[str, str],
) -> SiteAnalysis | None:
    """Analyze a site from orthophoto chips via Groq Llama 4 Scout vision.

    Parameters
    ----------
    tight_chip_path : Path | None
        Close-up chip of the parcel (currently unused, reserved for future).
    wide_chip_path : Path | None
        Context-view chip showing parcel and surroundings.
    boundary_strip_paths : dict[str, Path]
        Mapping of direction (north/south/east/west) to strip image path.
    cadastre_adjacents : dict[str, str]
        Cadastre labels per direction (e.g. {"north": "via publica", ...}).

    Returns
    -------
    SiteAnalysis | None
        Structured analysis, or None if vision is completely unavailable.
    """
    # -- Wide chip analysis --------------------------------------------------
    wide_result: dict | None = None
    if wide_chip_path is not None:
        b64 = _encode_image(wide_chip_path)
        if b64:
            wide_result = _analyze_wide_chip(b64)

    # If no wide chip result and no boundary strips at all, nothing to do
    if wide_result is None and not boundary_strip_paths:
        if not cadastre_adjacents:
            logger.warning("ortho_vision: no images and no cadastre data")
            return None

    # Build SiteAnalysis from wide chip (or defaults)
    if wide_result is not None:
        site = SiteAnalysis(
            is_anthropized=bool(wide_result.get("is_anthropized", False)),
            nearby_building_pattern=wide_result.get(
                "nearby_building_pattern", "none"
            ),
            general_surface=wide_result.get("general_surface", "periurban"),
            parcel_surface_state=wide_result.get(
                "parcel_surface_state", "mixed"
            ),
            parcel_occupied=bool(wide_result.get("parcel_occupied", False)),
            subsoil_visible=bool(wide_result.get("subsoil_visible", False)),
            confidence=wide_result.get("confidence", "low"),
        )
    else:
        site = SiteAnalysis(
            is_anthropized=False,
            nearby_building_pattern="none",
            general_surface="periurban",
            parcel_surface_state="mixed",
            parcel_occupied=False,
            subsoil_visible=False,
            confidence="low",
        )

    # -- Boundary strip analysis ---------------------------------------------
    all_directions = set(boundary_strip_paths.keys()) | set(cadastre_adjacents.keys())

    for direction in sorted(all_directions):
        cadastre_label = cadastre_adjacents.get(direction, "")
        strip_path = boundary_strip_paths.get(direction)

        if strip_path is not None:
            b64 = _encode_image(strip_path)
            if b64:
                raw = _analyze_boundary_strip(direction, cadastre_label, b64)
                if raw is not None:
                    site.boundary_analyses[direction] = _parse_boundary_result(
                        direction, cadastre_label, raw,
                    )
                    continue

        # Fallback: no strip image or vision failed
        site.boundary_analyses[direction] = _fallback_boundary(
            direction, cadastre_label,
        )

    return site
