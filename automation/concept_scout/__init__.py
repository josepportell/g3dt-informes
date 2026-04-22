"""
ConceptScout -- discover which project files contain which report concepts.

Phase A: text-only aggregation of FileMiner signals into a concept map.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from automation.fileminer.models import MiningResult, Signal, SignalType
from automation.schemas.loader import concept_registry

from .aggregator import aggregate_signals
from .models import ConceptMap, ConceptSource, FileEntry
from .scanner import enumerate_project_files

__all__ = [
    'scout_project',
    'concept_sources_to_signals',
    'ConceptMap',
    'ConceptSource',
    'FileEntry',
]

logger = logging.getLogger(__name__)

# Map vision-probe doc_type suffixes to the canonical source_type keys used
# in schemas/concepts/report_variables.yaml source_priority tables.
# Any vision_probe:* doc_type not listed here falls back to "vision_probe_other"
# so it still participates in competition (at a low-but-defined priority).
_VISION_DOC_TYPE_TO_SOURCE_TYPE: dict[str, str] = {
    'architect_plan': 'planol_vision',
    'projecte': 'projecte_vision',
}
_VISION_PROBE_FALLBACK_SOURCE_TYPE = 'vision_probe_other'


def concept_sources_to_signals(
    concept_sources: dict[str, list[ConceptSource]],
) -> list[Signal]:
    """Convert ConceptScout vision-probe sources into FileMiner Signals.

    Vision probe results live in concept_sources and are not part of the
    FileMiner signal pool by default. This converter bridges them so they
    participate in resolve_competition() with a source_type that the
    ConceptRegistry knows how to prioritize (e.g. planol_vision=20 beats
    dades_camp_excel=35 for street_address).

    Only sources whose extraction_method starts with "vision_probe:" are
    converted. Text-aggregated sources are skipped because they derive from
    Signals that are already in the pool.
    """
    signals: list[Signal] = []
    for concept_id, sources in concept_sources.items():
        for source in sources:
            method = source.extraction_method or ''
            if not method.startswith('vision_probe:'):
                continue
            preview = (source.signal_preview or '').strip()
            if not preview:
                continue
            doc_type = method.split(':', 1)[1] if ':' in method else ''
            source_type = _VISION_DOC_TYPE_TO_SOURCE_TYPE.get(
                doc_type, _VISION_PROBE_FALLBACK_SOURCE_TYPE,
            )
            signals.append(Signal(
                type=SignalType.TEXT,
                label=f"vision probe ({doc_type or 'other'})",
                value=preview,
                raw_value=source.signal_preview or '',
                maps_to=concept_id,
                concept_id=concept_id,
                source_file=source.file,
                source_location=f"page {source.page}" if source.page else "",
                extraction_method=method,
                confidence=source.confidence,
                source_type=source_type,
            ))
    return signals

def scout_project(
    project_path: Path | str,
    *,
    mining_result: MiningResult | None = None,
    use_vision_probe: bool = False,  # Phase B will enable this
    force_refresh: bool = False,
    on_progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> ConceptMap:
    """Build a concept-to-file map for a project.

    Args:
        project_path: Path to the project directory.
        mining_result: Pre-computed FileMiner result (signals to aggregate).
        use_vision_probe: Reserved for Phase B (vision-based probing).
        force_refresh: If True, ignore cached concept_map.json.
        on_progress: Optional callback for progress updates.

    Returns:
        ConceptMap with file inventory, concept sources, and unresolved list.
    """
    t0 = time.monotonic()
    project_path = Path(project_path)

    # Cache check
    cache_path = project_path / 'validation' / 'concept_map.json'
    if not force_refresh and cache_path.exists():
        try:
            raw = json.loads(cache_path.read_text(encoding='utf-8'))
            cached = ConceptMap(**raw)
            logger.info("ConceptScout: loaded cached concept_map.json for %s", project_path.name)
            return cached
        except Exception:
            logger.warning("ConceptScout: failed to load cache, will rescan", exc_info=True)

    # Step 1: enumerate all files
    if on_progress:
        on_progress('scanning_files', {'project': project_path.name})
    file_entries = enumerate_project_files(project_path)

    # Step 2: aggregate signals if mining_result provided
    all_ids = concept_registry.all_concept_ids()
    if mining_result is not None:
        file_entries, concept_sources = aggregate_signals(
            mining_result.signals, file_entries, all_ids,
        )
    else:
        concept_sources = {}

    # Step 3: vision probe for non-text files (images, scanned PDFs)
    vision_probes_sent = 0
    if use_vision_probe:
        from .vision_probe import probe_unreadable_files
        probe_sources = probe_unreadable_files(
            file_entries, project_path, on_progress=on_progress,
        )
        vision_probes_sent = sum(1 for fe in file_entries if fe.notes)
        # Merge probe results into concept_sources
        for cid, sources in probe_sources.items():
            concept_sources.setdefault(cid, []).extend(sources)

    # Step 4: compute unresolved concepts
    unresolved = sorted(all_ids - set(concept_sources.keys()))

    # Step 5: generate warnings
    warnings = _generate_warnings(concept_sources, all_ids)

    # Step 6: build ConceptMap
    duration_ms = int((time.monotonic() - t0) * 1000)
    concept_map = ConceptMap(
        metadata={
            'project': project_path.name,
            'scanned_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'total_files': len(file_entries),
            'vision_probes_sent': vision_probes_sent,
            'total_concepts_found': len(concept_sources),
            'total_concepts_unresolved': len(unresolved),
            'duration_ms': duration_ms,
        },
        file_inventory=file_entries,
        concept_sources=concept_sources,
        unresolved=unresolved,
        warnings=warnings,
    )

    # Step 6: save to cache
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            concept_map.model_dump_json(indent=2),
            encoding='utf-8',
        )
    except Exception:
        logger.warning("ConceptScout: failed to save cache", exc_info=True)

    logger.info(
        "ConceptScout: %d concepts found, %d unresolved, %d files (%dms)",
        len(concept_sources), len(unresolved), len(file_entries), duration_ms,
    )
    return concept_map


def _generate_warnings(
    concept_sources: dict[str, list[ConceptSource]],
    all_ids: set[str],
) -> list[str]:
    """Generate warnings for missing concept groups."""
    warnings: list[str] = []

    # Check for planol-related concepts
    planol_concepts = {'architect_name', 'client_name', 'building_type', 'num_floors'}
    if not any(cid in concept_sources for cid in planol_concepts):
        warnings.append("No architect plan data found — planol may be missing or unreadable")

    # Check for field work concepts
    field_concepts = {'field_date', 'num_dpsh_tests', 'table_dpsh_range'}
    if not any(cid in concept_sources for cid in field_concepts):
        warnings.append("No field work data found — DPSH/sondeig files may be missing")

    # Check for location concepts
    location_concepts = {'street_address', 'municipality', 'province'}
    if not any(cid in concept_sources for cid in location_concepts):
        warnings.append("No location data found — address source may be missing")

    return warnings
