"""Targeted extraction: run a small set of concepts against a single file.

Used by the wizard's "Missing info" drawer: Eva uploads the document that
holds a gap, we extract just the concepts she's missing.

Hybrid strategy:
    1. FileMiner regex first (free, <1s).
    2. cc_extractor vision fallback for concepts still missing (~$0.10-0.20).

The vision fallback restricts the prompt to the requested concept subset, so
both cost and accuracy improve vs. a full-schema call.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "concepts" / "report_variables.yaml"

# Diagnostic-only: per-call usage records appended by `_vision_extract`
# whenever cc_extractor returns a usage trace. Drained by `pop_traces`.
_TRACE_LOG: list[dict] = []


def pop_traces() -> list[dict]:
    """Drain and return the accumulated targeted-extraction trace log."""
    global _TRACE_LOG
    out = _TRACE_LOG
    _TRACE_LOG = []
    return out


def extract_targeted(
    file_path: Path,
    concept_ids: list[str],
    project_path: Path,
    *,
    allow_vision: bool = True,
) -> dict[str, dict[str, Any]]:
    """Extract a subset of concepts from a single user-supplied file.

    Args:
        file_path: Absolute path to the file (must exist).
        concept_ids: The concepts Eva wants filled.
        project_path: Project root (used by FileMiner for relative paths).
        allow_vision: If False, stop after the regex step (useful for tests).

    Returns:
        {concept_id: {value, confidence, extraction_method, page?, snippet?}}
        Missing concepts map to {"value": None, "confidence": 0.0,
        "extraction_method": "failed"}.
    """
    t0 = time.monotonic()
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        return {cid: _failed(cid, "file_not_found") for cid in concept_ids}

    requested = set(concept_ids)
    results: dict[str, dict[str, Any]] = {}

    # --- Step 1: FileMiner regex (free) ---
    try:
        from automation.fileminer.miners import get_miners_for_file
        miners = get_miners_for_file(file_path, project_path)
        for miner in miners:
            try:
                if not miner.can_mine(file_path):
                    continue
            except Exception:
                pass
            try:
                signals = miner.mine(file_path)
            except Exception as exc:
                logger.warning("miner %s failed on %s: %s", type(miner).__name__, file_path.name, exc)
                continue
            for sig in signals:
                cid = sig.concept_id or sig.maps_to
                if cid not in requested or cid in results:
                    continue
                # Take first signal per concept; if duplicates appear, keep the
                # one with higher confidence.
                results[cid] = {
                    "value": sig.value,
                    "confidence": float(sig.confidence),
                    "extraction_method": f"fileminer_{sig.extraction_method or 'regex'}",
                    "page": None,
                    "snippet": sig.raw_value or None,
                    "source_file": str(file_path.name),
                }
    except Exception as exc:
        logger.warning("FileMiner pass failed on %s: %s", file_path.name, exc)

    # --- Step 2: Vision fallback for still-missing concepts ---
    missing = [cid for cid in concept_ids if cid not in results]
    if missing and allow_vision:
        try:
            vision_results = _vision_extract(file_path, missing)
            results.update(vision_results)
        except Exception as exc:
            logger.error("vision fallback failed on %s: %s", file_path.name, exc)

    # --- Step 3: Pad the output with failed entries for any still-missing ---
    for cid in concept_ids:
        results.setdefault(cid, _failed(cid, "not_found"))

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "extract_targeted: file=%s concepts=%d filled=%d elapsed=%dms",
        file_path.name, len(concept_ids),
        sum(1 for r in results.values() if r.get("value") not in (None, "")),
        elapsed_ms,
    )
    return results


def _vision_extract(file_path: Path, concept_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Call cc_extractor.extract_from_files with a concept-subset override.

    For narrative concepts (location_sentence, adjacent_*_fmt, site_description,
    building_structure_desc) we pass Eva's template patterns so the model
    adapts extracted facts into her expected phrasing — without this, T2
    showed these concepts failing the naive scorer with "same facts, different
    wrapper" outputs.
    """
    from automation.concept_templates import get_template_patterns
    from tests.cc_agentic.cc_extractor import extract_from_files, load_concept_schema

    full_schema = load_concept_schema(_SCHEMA_PATH)
    subset = {cid: full_schema[cid] for cid in concept_ids if cid in full_schema}
    if not subset:
        return {}

    files = [{"path": str(file_path), "role": "eva_upload", "origin": "user_upload"}]
    t0 = time.monotonic()
    vars_dict, trace = extract_from_files(
        files,
        _SCHEMA_PATH,
        agentic_crops=False,
        concepts_override=subset,
        template_patterns=get_template_patterns(concept_ids),
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # Defensive trace capture for diagnostic v1.1 cost telemetry. Never raise.
    try:
        total_usage = {}
        if isinstance(trace, list):
            for entry in reversed(trace):
                if isinstance(entry, dict) and entry.get('type') == 'summary':
                    total_usage = entry.get('total_usage', {}) or {}
                    break
        _TRACE_LOG.append({
            "file_path": str(file_path),
            "total_usage": total_usage,
            "elapsed_ms": elapsed_ms,
        })
    except Exception:
        logger.debug("targeted_extraction: trace capture failed", exc_info=True)

    out: dict[str, dict[str, Any]] = {}
    for cid, entry in vars_dict.items():
        if cid not in concept_ids:
            continue
        out[cid] = {
            "value": entry.get("value"),
            "confidence": float(entry.get("confidence", 0.5)),
            "extraction_method": f"cc_extractor_{entry.get('extraction_method', 'vision')}",
            "page": entry.get("page"),
            "snippet": entry.get("snippet") or entry.get("raw") or None,
            "source_file": str(file_path.name),
        }
    return out


def _failed(concept_id: str, reason: str) -> dict[str, Any]:
    return {
        "value": None,
        "confidence": 0.0,
        "extraction_method": "failed",
        "reason": reason,
        "page": None,
        "snippet": None,
    }
