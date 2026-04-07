"""Transform FileMiner signals into concept-to-file mapping."""

from __future__ import annotations

import logging
from collections import defaultdict

from automation.fileminer.label_map import get_priority
from automation.fileminer.models import Signal

from .models import ConceptSource, FileEntry

logger = logging.getLogger(__name__)


def aggregate_signals(
    signals: list[Signal],
    file_entries: list[FileEntry],
    all_concept_ids: set[str],
) -> tuple[list[FileEntry], dict[str, list[ConceptSource]]]:
    """Aggregate FileMiner signals into concept sources per file.

    Returns:
        Tuple of (updated file_entries, concept_sources dict).
    """
    # Build lookup: relative_path -> FileEntry
    entry_by_path: dict[str, FileEntry] = {e.path: e for e in file_entries}

    # Group signals by concept_id (skip unmapped signals)
    by_concept: dict[str, list[Signal]] = defaultdict(list)
    for sig in signals:
        if sig.concept_id is not None:
            by_concept[sig.concept_id].append(sig)

    concept_sources: dict[str, list[ConceptSource]] = {}

    for concept_id, sigs in by_concept.items():
        # Deduplicate by file: keep the highest-confidence signal per file
        best_per_file: dict[str, Signal] = {}
        for sig in sigs:
            existing = best_per_file.get(sig.source_file)
            if existing is None or sig.confidence > existing.confidence:
                best_per_file[sig.source_file] = sig

        # Build ConceptSource list sorted by priority (lower = better)
        sources: list[ConceptSource] = []
        for rel_path, sig in best_per_file.items():
            preview = str(sig.value)[:80] if sig.value is not None else ""
            sources.append(ConceptSource(
                file=rel_path,
                confidence=sig.confidence,
                signal_preview=preview,
                extraction_method=sig.extraction_method or sig.source_type,
            ))

        sources.sort(key=lambda s: get_priority(
            best_per_file[s.file].source_type
        ))

        concept_sources[concept_id] = sources

        # Update FileEntry metadata
        for rel_path, sig in best_per_file.items():
            entry = entry_by_path.get(rel_path)
            if entry is not None:
                if concept_id not in entry.concepts_detected:
                    entry.concepts_detected.append(concept_id)
                entry.concept_confidence[concept_id] = sig.confidence

    logger.info(
        "ConceptScout aggregator: %d concepts mapped from %d signals",
        len(concept_sources), len(signals),
    )
    return file_entries, concept_sources
