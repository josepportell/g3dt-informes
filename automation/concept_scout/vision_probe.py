"""Lightweight Claude vision probe for concept identification in image files.

Sends the first page of a file to Claude and asks: "which report concepts
are present?" — NOT full value extraction, just content classification.

Cost: ~$0.01-0.02 per probe. Results cached per file.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from .models import ConceptSource

logger = logging.getLogger(__name__)

# Concepts that vision can realistically identify in documents
_VISION_DETECTABLE_CONCEPTS = {
    'architect_name', 'architect_company',
    'client_name', 'contact_name', 'client_nif',
    'street_address', 'municipality', 'province',
    'building_type', 'num_floors', 'building_height_m',
    'superficie_construida_m2', 'superficie_parcela_m2',
    'has_basement', 'has_retaining_walls',
    'expedient',
    'num_soil_levels', 'cota_referencia', 'field_date',
    'sulfate_mg_kg',
    # Visual observations from site photos / aerial views — inputs to
    # site_description + site_condition + is_anthropized synthesis
    # (Phase B, 2026-04-19).
    'site_vegetation_visual',
    'site_slope_visual',
    'is_anthropized_visual',
    'building_to_demolish_visual',
    'access_road_visual',
    'surrounding_context_visual',
}

_PROBE_PROMPT = """Look at this document image and identify which of these report data concepts are present.

ABSTENTION RULE (applies to every concept below):
If you cannot distinguish the document's subject from incidental content
(text visible at frame edges, footer metadata, legends, neighbor town
labels on maps, watermarks), OMIT that concept from concepts_found.
Abstain rather than guess. High confidence requires clear evidence, not
plausibility — return concepts_found = [] if the document is ambiguous.

MAP-SUBJECT SCOPING (applies when document_type = "map"):
Identify the municipality and province that are the SUBJECT of the map —
the area highlighted by a polygon outline, marker, title block, or a
label near the image center. Do NOT return names of neighbouring towns
visible at the frame edges; those are context, not subject. If the
subject is not clearly indicated, omit municipality/province entirely.

For each concept found, provide:
- concept_id: the exact ID from the list below
- confidence: 0.0-1.0 (how certain you are)
- signal_preview: brief text snippet showing the value (max 60 chars)
- page: which page number (1-based) the concept appears on

CONCEPTS TO LOOK FOR:
- architect_name: Name of the architect
- architect_company: Architect's firm name
- client_name: Client/promotor name
- contact_name: Contact person name
- client_nif: Tax ID (NIF/CIF)
- street_address: Project site address
- municipality: Town/city name
- province: Province name
- building_type: Type of building (habitatge, nau, etc.)
- num_floors: Number of floors (Pb+1Pp, etc.)
- building_height_m: Building height in meters
- superficie_construida_m2: Built area in m²
- superficie_parcela_m2: Plot area in m²
- has_basement: Whether building has basement
- has_retaining_walls: Whether it has retaining walls
- expedient: Project reference number
- num_soil_levels: Number of geological levels
- cota_referencia: Reference elevation
- field_date: Date of field work
- sulfate_mg_kg: Sulfate content

VISUAL OBSERVATIONS (site photos, aerial views, field imagery — MULTI-LABEL,
multiple may apply to a single image):
- site_vegetation_visual: vegetation visible on the site. Write a brief
  Catalan phrase — e.g. "vegetació rasa", "matollar dispers",
  "arbres aïllats", "sense vegetació".
- site_slope_visual: terrain slope visible. Write a brief Catalan phrase —
  e.g. "pla", "pendent suau", "pendent moderada cap a sud".
- is_anthropized_visual: bool-like signal. Write "si" if the photo shows
  human modification (existing construction, fill, leveling, retaining
  walls, terraces); "no" if the site looks natural/undisturbed.
- building_to_demolish_visual: existing structure on the parcel — describe
  height/use/state in a brief Catalan phrase (e.g. "edifici PB+1 buit",
  "caseta agrícola en ruïna").
- access_road_visual: visible access — e.g. "carrer pavimentat",
  "pista sense pavimentar", "camí de terra".
- surrounding_context_visual: context of the surroundings — e.g.
  "parcel·les buides al voltant", "zona residencial consolidada",
  "vista aèria del barri".

Also classify the document type:
- document_type: one of "architect_plan", "field_sheet", "site_photo", "catalog", "budget", "lab_report", "map", "email", "other"
- document_description: brief description of what the document shows (max 100 chars)

Return ONLY valid JSON:
{
  "document_type": "...",
  "document_description": "...",
  "concepts_found": [
    {"concept_id": "...", "confidence": 0.9, "signal_preview": "...", "page": 1},
    ...
  ]
}

If no report concepts are found (e.g., it's just a site photo), return an empty concepts_found list."""

_PROBE_SYSTEM = "You are a document classifier for geotechnical engineering reports. Identify data concepts present in the document. Be precise — only report concepts you can actually see, not infer."


# --- Widened gate for text-extractable vector PDFs -----------------------
# Some architect-plan / CAD-exported PDFs classify as "text-extractable"
# (PyMuPDF returns >50 chars of text on page 1) but the text is only
# coordinate strings, dimension labels, and isolated tokens — nothing the
# regex / Groq miners can label. Probe these anyway when:
#   - the aggregator found zero mapped concepts for this file, AND
#   - page-1 text is short (<= `_LAYOUT_MAX_TEXT_LEN` chars).
# The length cap excludes prose-heavy PDFs (informes, pressupostos, lab
# reports) where probing would be wasteful.

# Threshold grounding (measured across 7 reference projects, 2026-04-19):
# - Vilanova `1.0.pdf` (architect title block) has page-1 text ~500 chars.
# - Architect plans / cadastre extracts / situation plans: 100–1500 chars.
# - Real prose PDFs (informes, pressupostos, articles): >4000 chars.
# 2000 is the loosest cap that still excludes every informe/pressupost PDF
# we inspected; it adds ~11 extra probes per full-corpus sweep (estimated
# by enumerating `concept_map.json` file inventories and counting
# pdf_vector files with empty concepts_detected and page-1 text ≤ 2000).
_LAYOUT_MAX_TEXT_LEN = 2000
_LAYOUT_MIN_TEXT_LEN = 20  # below this we already consider it "no text" → probe

# Legacy Eva-output directories (we emit these ourselves on prior runs).
# Kept at module scope so callers can reuse the set; matching is
# case-insensitive (see `_in_legacy_output`). Deliberately diverges from
# `automation/fileminer/__init__.py`, which lacks the `'PDF V0'` variant
# (with a space): we include all four spellings here because probe cost
# is higher than a miner skip and we cannot afford to probe our own
# historical outputs.
_LEGACY_OUTPUT_DIRS = {'PDF', 'PDF-V0', 'PDF_V0', 'PDF V0'}
_LEGACY_OUTPUT_DIRS_CF = {d.casefold() for d in _LEGACY_OUTPUT_DIRS}


def _extract_page1_text(file_path: Path) -> str | None:
    """Return page-1 text for a PDF, or None on failure."""
    try:
        import fitz
        doc = fitz.open(str(file_path))
        try:
            if doc.page_count == 0:
                return ""
            return doc[0].get_text() or ""
        finally:
            doc.close()
    except Exception:
        return None


def _should_probe_text_pdf(file_path: Path, concepts_detected: list[str]) -> bool:
    """Decide whether a text-extractable PDF still merits a vision probe.

    Probe when the file has no concepts detected AND page-1 text is short
    (layout-heavy title blocks, dimension labels, CAD exports, cadastre
    extracts). Caller is responsible for excluding legacy Eva-output
    directories before consulting this helper.

    Gate: both conditions must hold.
      - `concepts_detected == []` — text miners found nothing mappable.
      - page-1 text length <= `_LAYOUT_MAX_TEXT_LEN` — excludes prose-heavy
        PDFs (informes, pressupostos, articles) where probing would be
        wasteful.
    """
    if concepts_detected:
        return False
    text = _extract_page1_text(file_path)
    if text is None:
        return False
    n = len(text)
    if n <= _LAYOUT_MIN_TEXT_LEN:
        return True
    if n > _LAYOUT_MAX_TEXT_LEN:
        return False
    # Page-1 text is modest-length (<=2000 chars) AND no concepts detected —
    # this matches architect plans (thin title blocks), cadastre extracts,
    # situation-plan PDFs, CAD exports. Probe them.
    return True


def _cache_key(file_path: Path) -> str:
    """Generate cache key from file path + modification time."""
    stat = file_path.stat()
    raw = f"{file_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _load_cached(cache_dir: Path, key: str) -> dict | None:
    """Load cached raw probe result."""
    cache_file = cache_dir / f"{key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding='utf-8'))
        except Exception:
            pass
    return None


def _save_cache(cache_dir: Path, key: str, result: dict) -> None:
    """Save raw probe result to cache."""
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{key}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8',
        )
    except Exception:
        logger.warning("Failed to save probe cache for %s", key)


def _run_probe(file_path: Path) -> dict | None:
    """Run a single vision probe. Tries Groq first (cheaper), Claude as fallback."""
    try:
        from web.vision_groq import (
            _file_to_images, _call_groq_vision, _call_openai_vision, _call_anthropic_vision,
        )
    except ImportError:
        logger.warning("Vision probe: web.vision_groq not available")
        return None

    try:
        images = _file_to_images(file_path, dpi=200, max_pages=50)
    except Exception as e:
        logger.warning("Vision probe: cannot render %s: %s", file_path.name, e)
        return None

    if not images:
        return None

    # Fallback chain from config
    from automation import config
    _PROBE_CALL_MAP = {
        "groq": _call_groq_vision,
        "openai": _call_openai_vision,
        "anthropic": _call_anthropic_vision,
    }

    result = None
    for backend in config.PROBE_FALLBACK_ORDER:
        if not config.has_provider(backend):
            continue
        call_fn = _PROBE_CALL_MAP.get(backend)
        if call_fn:
            try:
                result = call_fn(_PROBE_PROMPT, images, _PROBE_SYSTEM)
                if result is not None:
                    break
            except Exception as e:
                logger.debug("Vision probe %s failed for %s: %s", backend, file_path.name, e)

    if result:
        logger.info(
            "Vision probe %s: type=%s, %d concepts",
            file_path.name,
            result.get('document_type', '?'),
            len(result.get('concepts_found', [])),
        )
    return result


def _parse_probe_result(
    result: dict, rel_path: str,
) -> tuple[list[str], dict[str, float], str, dict[str, ConceptSource]]:
    """Parse a raw probe result into concepts_detected, confidence, notes, and sources."""
    doc_type = result.get('document_type', 'other')
    doc_desc = result.get('document_description', '')
    notes = f"{doc_type}: {doc_desc}"

    concepts_detected: list[str] = []
    concept_confidence: dict[str, float] = {}
    sources_by_concept: dict[str, ConceptSource] = {}

    for entry in result.get('concepts_found', []):
        cid = entry.get('concept_id', '')
        if cid not in _VISION_DETECTABLE_CONCEPTS:
            continue
        confidence = min(1.0, max(0.0, float(entry.get('confidence', 0.5))))
        preview = str(entry.get('signal_preview', ''))[:60]

        concepts_detected.append(cid)
        concept_confidence[cid] = confidence
        page = entry.get('page')
        if page is not None:
            try:
                page = int(page)
            except (ValueError, TypeError):
                page = None

        sources_by_concept[cid] = ConceptSource(
            file=rel_path,
            confidence=confidence,
            signal_preview=preview,
            extraction_method=f"vision_probe:{doc_type}",
            page=page,
        )

    return concepts_detected, concept_confidence, notes, sources_by_concept


def probe_unreadable_files(
    file_entries: list,
    project_path: Path,
    *,
    on_progress: Any = None,
) -> dict[str, list[ConceptSource]]:
    """Probe all non-text-extractable files for concept presence.

    Returns {concept_id: [ConceptSource, ...]} to merge into concept_sources.
    Also updates FileEntry.concepts_detected and .notes in place.
    """
    # Skip FOTOGRAFIES dirs (site photos, never contain report concepts)
    # and inline email images (image001.jpg, image005.png etc.)
    _SKIP_PHOTO_DIRS = {'FOTOGRAFIES', 'FOTOS DE CAMP', 'FOTOS DE CAMP + PLANOL PUNTS'}
    _INLINE_IMAGE_RE = __import__('re').compile(r'^image\d+\.\w+$', __import__('re').IGNORECASE)

    def _in_photo_dir(rel_path: str) -> bool:
        return any(part in _SKIP_PHOTO_DIRS for part in Path(rel_path).parts[:-1])

    def _in_legacy_output(rel_path: str) -> bool:
        # Case-insensitive — clients have been observed to use lower-case
        # `pdf/` on disk, and `file_scanner.py` already applies `(?i)` to
        # at least the `PDF-V0` variant. Folding here keeps the gate
        # robust across all four spellings regardless of OS casing.
        return any(
            part.casefold() in _LEGACY_OUTPUT_DIRS_CF
            for part in Path(rel_path).parts[:-1]
        )

    def _is_inline_email_image(rel_path: str) -> bool:
        return bool(_INLINE_IMAGE_RE.match(Path(rel_path).name))

    to_probe: list = []
    for fe in file_entries:
        if _in_photo_dir(fe.path) or _is_inline_email_image(fe.path):
            continue

        # Skip legacy Eva-produced outputs regardless of gate path — we never
        # want to probe our own historical reports (classic or widened gate).
        if _in_legacy_output(fe.path):
            continue

        # Classic gate: images + scanned PDFs always probed.
        if not fe.text_extractable and fe.type in ('image', 'pdf_scanned'):
            to_probe.append(fe)
            continue

        # Widened gate (knob #2): text-extractable vector PDFs with no
        # mapped concepts and only modest page-1 text. Catches architect
        # plans, cadastre extracts, situation-plan PDFs — files whose text
        # is CAD labels / coordinates that regex miners cannot parse.
        if fe.text_extractable and fe.type == 'pdf_vector':
            abs_path = project_path / fe.path
            if abs_path.exists() and _should_probe_text_pdf(
                abs_path, fe.concepts_detected,
            ):
                to_probe.append(fe)
                logger.info(
                    "Vision probe: gating text-extractable vector PDF %s", fe.path,
                )
                continue

    if not to_probe:
        return {}

    logger.info("Vision probe: %d files to probe", len(to_probe))
    cache_dir = project_path / 'validation' / 'concept_probes'
    concept_sources: dict[str, list[ConceptSource]] = {}

    for i, fe in enumerate(to_probe):
        file_path = project_path / fe.path
        if not file_path.exists():
            continue

        if on_progress:
            on_progress('vision_probe', {
                'file': fe.path,
                'index': i + 1,
                'total': len(to_probe),
            })

        # Check cache first
        key = _cache_key(file_path)
        result = _load_cached(cache_dir, key)
        if result is None:
            result = _run_probe(file_path)
            if result:
                _save_cache(cache_dir, key, result)

        if not result:
            continue

        rel_path = str(file_path.relative_to(project_path))
        detected, confidence, notes, sources = _parse_probe_result(result, rel_path)

        # Update FileEntry in place
        fe.concepts_detected = detected
        fe.concept_confidence = confidence
        fe.notes = notes

        # Merge into concept_sources
        for cid, src in sources.items():
            concept_sources.setdefault(cid, []).append(src)

    return concept_sources
