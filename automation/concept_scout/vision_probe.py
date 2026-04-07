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
}

_PROBE_PROMPT = """Look at this document image and identify which of these report data concepts are present.

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
    """Run a single vision probe and return raw JSON result."""
    try:
        from web.vision_groq import _file_to_images, _call_anthropic_vision
    except ImportError:
        logger.warning("Vision probe: web.vision_groq not available")
        return None

    try:
        images = _file_to_images(file_path, dpi=200)
    except Exception as e:
        logger.warning("Vision probe: cannot render %s: %s", file_path.name, e)
        return None

    if not images:
        return None

    try:
        result = _call_anthropic_vision(_PROBE_PROMPT, images[:1], _PROBE_SYSTEM)
    except Exception as e:
        logger.warning("Vision probe API failed for %s: %s", file_path.name, e)
        return None

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
    to_probe = [
        fe for fe in file_entries
        if not fe.text_extractable and fe.type in ('image', 'pdf_scanned')
    ]

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
