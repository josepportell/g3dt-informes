#!/usr/bin/env python3
"""
G3DT Vision JSON Normalizer

Normalizes non-deterministic key names from Claude vision extraction
into canonical schemas. Handles variant key names for SPT data in both
dpsh_extracted.json and sondeig_extracted.json.

Usage:
    from automation.vision_normalizer import load_dpsh_json, load_sondeig_json

    dpsh = load_dpsh_json(Path('validation/dpsh_extracted.json'))
    sondeig = load_sondeig_json(Path('validation/sondeig_extracted.json'))

Author: Eficients.cat
Date: 2026-03-15
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DPSH normalization
# ---------------------------------------------------------------------------

def _normalize_dpsh_spt_fields(spt: dict) -> dict:
    """Normalize SPT field names within a DPSH SPT entry to canonical form.

    Canonical keys: test_id, location, depth_from_m, depth_to_m, blows, n_spt, confidence
    """
    normalized: dict[str, Any] = {}

    # test_id
    normalized['test_id'] = (
        spt.get('test_id')
        or spt.get('test_name')
        or 'SPT-1'
    )

    # location (which DPSH point the SPT was done at)
    normalized['location'] = (
        spt.get('location')
        or spt.get('reference')
        or spt.get('test_point')
        or ''
    )

    # depth_from_m
    normalized['depth_from_m'] = (
        spt.get('depth_from_m')
        if spt.get('depth_from_m') is not None
        else spt.get('cota_from')
    )

    # depth_to_m
    normalized['depth_to_m'] = (
        spt.get('depth_to_m')
        if spt.get('depth_to_m') is not None
        else spt.get('cota_to')
    )

    # blows array
    normalized['blows'] = (
        spt.get('blows')
        or spt.get('blows_15_30_45_60')
        or spt.get('blow_counts')
        or []
    )

    # n_spt: compute from blows[1]+blows[2] if missing
    n_spt = spt.get('n_spt') or spt.get('n30')
    if not n_spt and len(normalized['blows']) >= 3:
        n_spt = normalized['blows'][1] + normalized['blows'][2]
    normalized['n_spt'] = n_spt

    # confidence
    normalized['confidence'] = spt.get('confidence', 0.85)

    return normalized


def _find_and_normalize_dpsh_spt(data: dict) -> dict | None:
    """Find SPT data anywhere in dpsh_extracted.json and normalize it.

    Checks known variant locations where Claude vision places SPT data:
    - data['spt_in_dpsh'] (canonical — already correct)
    - data['spt_data'] (variant)
    - data['spt_test'] (variant)
    - data['document_metadata']['spt_test'] (variant)
    """
    # Check canonical key first
    spt = data.get('spt_in_dpsh')
    if spt and isinstance(spt, dict):
        return _normalize_dpsh_spt_fields(spt)

    # Check variant locations
    for candidate in [
        data.get('spt_data'),
        data.get('spt_test'),
        data.get('document_metadata', {}).get('spt_test'),
    ]:
        if candidate and isinstance(candidate, dict):
            return _normalize_dpsh_spt_fields(candidate)

    return None


def normalize_dpsh(data: dict) -> dict:
    """Normalize a dpsh_extracted.json dict in place.

    Moves SPT data to canonical 'spt_in_dpsh' key and normalizes field names.
    """
    spt = _find_and_normalize_dpsh_spt(data)

    # Remove variant keys
    for key in ('spt_data', 'spt_test'):
        data.pop(key, None)
    if 'document_metadata' in data and isinstance(data['document_metadata'], dict):
        data['document_metadata'].pop('spt_test', None)

    # Set canonical key
    data['spt_in_dpsh'] = spt
    return data


def load_dpsh_json(path: Path | str) -> dict:
    """Load and normalize dpsh_extracted.json.

    Returns normalized dict with canonical key names.
    Raises FileNotFoundError if path doesn't exist.
    """
    path = Path(path)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return normalize_dpsh(data)


# ---------------------------------------------------------------------------
# Sondeig normalization
# ---------------------------------------------------------------------------

def _normalize_sondeig_spt_fields(spt: dict) -> dict:
    """Normalize SPT field names within a sondeig SPT entry to canonical form.

    Canonical keys: test_id, depth_from_m, depth_to_m, blows, n_spt, confidence
    """
    normalized: dict[str, Any] = {}

    # test_id
    normalized['test_id'] = (
        spt.get('test_id')
        or spt.get('test_name')
        or 'SPT-1'
    )

    # depth_from_m
    normalized['depth_from_m'] = (
        spt.get('depth_from_m')
        if spt.get('depth_from_m') is not None
        else spt.get('cota_from')
    )

    # depth_to_m
    normalized['depth_to_m'] = (
        spt.get('depth_to_m')
        if spt.get('depth_to_m') is not None
        else spt.get('cota_to')
    )

    # blows array
    normalized['blows'] = (
        spt.get('blows')
        or spt.get('blow_counts')
        or spt.get('blows_15_30_45_60')
        or []
    )

    # n_spt: compute from blows[1]+blows[2] if missing
    n_spt = spt.get('n_spt') or spt.get('n30')
    if not n_spt and len(normalized['blows']) >= 3:
        n_spt = normalized['blows'][1] + normalized['blows'][2]
    normalized['n_spt'] = n_spt

    # confidence
    normalized['confidence'] = spt.get('confidence', 0.85)

    # Preserve extra fields (blows_note, n_spt_note, etc.)
    for key in ('blows_note', 'n_spt_note'):
        if key in spt:
            normalized[key] = spt[key]

    return normalized


def normalize_sondeig(data: dict) -> dict:
    """Normalize a sondeig_extracted.json dict in place.

    For each sondeig test:
    - Renames 'spt_tests' to 'spt_results' (canonical key)
    - Normalizes SPT field names within each entry
    """
    for test in data.get('sondeig_tests', []):
        # Move spt_tests → spt_results if needed
        spt_list = test.get('spt_results') or test.get('spt_tests', [])
        test.pop('spt_tests', None)  # Remove variant key

        # Normalize each SPT entry
        test['spt_results'] = [
            _normalize_sondeig_spt_fields(spt)
            for spt in spt_list
        ]

    return data


def load_sondeig_json(path: Path | str) -> dict:
    """Load and normalize sondeig_extracted.json.

    Returns normalized dict with canonical key names.
    Raises FileNotFoundError if path doesn't exist.
    """
    path = Path(path)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return normalize_sondeig(data)
