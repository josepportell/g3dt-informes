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
import re
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


def _normalize_dpsh_test_refusal(test: dict) -> None:
    """Normalize refusal depth within a DPSH test entry.

    Prefers exact refusal annotation (from handwritten "R x.xx") over
    grid-rounded depth. Vision model may produce:
    - refusal_exact_m (Rubí variant)
    - refusal_notation (older variant)

    These are more accurate than refusal_depth_m which rounds to 0.20m grid.
    After normalization, refusal_depth_m contains the best available value.
    """
    exact = (
        test.get('refusal_exact_m')
        or test.get('refusal_notation')
    )
    if exact is not None:
        try:
            exact_val = float(exact)
            test['refusal_depth_m'] = exact_val
        except (ValueError, TypeError):
            pass
    # Clean up variant keys
    test.pop('refusal_exact_m', None)
    test.pop('refusal_notation', None)


def normalize_dpsh(data: dict) -> dict:
    """Normalize a dpsh_extracted.json dict in place.

    - Moves SPT data to canonical 'spt_in_dpsh' key
    - Normalizes refusal depths (prefer exact annotation over grid-rounded)
    """
    spt = _find_and_normalize_dpsh_spt(data)

    # Remove variant SPT keys
    for key in ('spt_data', 'spt_test'):
        data.pop(key, None)
    if 'document_metadata' in data and isinstance(data['document_metadata'], dict):
        data['document_metadata'].pop('spt_test', None)

    # Set canonical SPT key
    data['spt_in_dpsh'] = spt

    # Normalize refusal depths in each DPSH test
    for test in data.get('dpsh_tests', []):
        _normalize_dpsh_test_refusal(test)

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


def _extract_elevation_from_notes(text: str) -> float | None:
    """Extract elevation_z from free-text extraction_notes.

    Handles: "Cota z=199.50m", "cota z 199,50", "Cota Z=+199.50m.",
             "elevation z = 199.50 m", "elevation_z: 199.50"
    """
    for pattern in [
        r'[Cc]ota\s+[Zz]\s*=?\s*\+?([\d.,]+)\s*m?\b',
        r'[Ee]levation[\s_]+[Zz]\s*[=:]\s*\+?([\d.,]+)\s*m?\b',
    ]:
        match = re.search(pattern, text)
        if match:
            val_str = match.group(1).replace(',', '.')
            try:
                return float(val_str)
            except (ValueError, TypeError):
                pass
    return None


def _normalize_elevation_z(data: dict) -> None:
    """Extract elevation_z from any location and write to canonical data['elevation_z'].

    Search order (first non-None wins):
    1. data['metadata']['elevation_z'] or data['metadata']['cota_z']
    2. data['borehole_metadata']['elevation_z'] or ['cota_z']
    3. data['elevation_z'] or data['cota_z'] (top-level)
    4. data['sondeig_tests'][0]['elevation_z'] or ['cota_z']
    5. Regex on extraction_notes (per-test then top-level):
       Pattern: r'[Cc]ota\\s+[Zz]\\s*=?\\s*\\+?([\\d.,]+)\\s*m?'
    """
    elev_z = None

    # 1. metadata
    metadata = data.get('metadata')
    if isinstance(metadata, dict):
        elev_z = metadata.get('elevation_z')
        if elev_z is None:
            elev_z = metadata.get('cota_z')

    # 2. borehole_metadata
    if elev_z is None:
        bh_meta = data.get('borehole_metadata')
        if isinstance(bh_meta, dict):
            elev_z = bh_meta.get('elevation_z')
            if elev_z is None:
                elev_z = bh_meta.get('cota_z')

    # 3. top-level
    if elev_z is None:
        elev_z = data.get('elevation_z')
        if elev_z is None:
            elev_z = data.get('cota_z')

    # 4. first sondeig_test structured key
    if elev_z is None:
        tests = data.get('sondeig_tests', [])
        if tests and isinstance(tests, list):
            elev_z = tests[0].get('elevation_z')
            if elev_z is None:
                elev_z = tests[0].get('cota_z')

    # 5. regex on extraction_notes (per-test first, then top-level)
    if elev_z is None:
        for test in data.get('sondeig_tests', []):
            notes = test.get('extraction_notes', '')
            if notes and isinstance(notes, str):
                elev_z = _extract_elevation_from_notes(notes)
                if elev_z is not None:
                    break
    if elev_z is None:
        top_notes = data.get('extraction_notes', '')
        if top_notes and isinstance(top_notes, str):
            elev_z = _extract_elevation_from_notes(top_notes)

    # Write canonical key (None if not found anywhere)
    if elev_z is not None:
        try:
            data['elevation_z'] = float(str(elev_z).replace(',', '.'))
        except (ValueError, TypeError):
            pass


def normalize_sondeig(data: dict) -> dict:
    """Normalize a sondeig_extracted.json dict in place.

    For each sondeig test:
    - Renames 'spt_tests' to 'spt_results' (canonical key)
    - Normalizes SPT field names within each entry
    - Extracts elevation_z to canonical top-level key
    """
    _normalize_elevation_z(data)

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


def load_sondeig_merged(validation_dir: Path | str) -> dict:
    """Load sondeig data merging annex (priority) with field sheet.

    The sondeig annex (formatted PDF with 'Unitat litològica' column) is
    authoritative for num_geological_levels.  The field sheet provides
    layers, SPT, and other field data.  When both exist, annex-specific
    fields override field-sheet values.

    Returns normalized merged dict, or empty dict if neither file exists.
    """
    validation_dir = Path(validation_dir)
    field_sheet_path = validation_dir / 'sondeig_extracted.json'
    annex_path = validation_dir / 'sondeig_annex_extracted.json'

    result: dict = {}

    # Load field sheet as base (layers, SPT, elevation_z, etc.)
    if field_sheet_path.exists():
        try:
            result = load_sondeig_json(field_sheet_path)
        except Exception:
            pass

    # Overlay annex data — num_geological_levels is authoritative
    if annex_path.exists():
        try:
            annex = load_sondeig_json(annex_path)
            # If no field sheet, annex is the sole source
            if not result:
                return annex
            # Merge: annex num_geological_levels into each test
            annex_tests = annex.get('sondeig_tests', [])
            result_tests = result.get('sondeig_tests', [])
            for i, at in enumerate(annex_tests):
                geo_levels = at.get('num_geological_levels')
                if geo_levels is not None and i < len(result_tests):
                    result_tests[i]['num_geological_levels'] = geo_levels
                elif geo_levels is not None:
                    result_tests.append(at)
            # Also merge top-level keys the annex may provide
            for key in ('num_geological_levels', 'elevation_z', 'overall_confidence'):
                if annex.get(key) is not None:
                    result[key] = annex[key]
        except Exception:
            pass

    return result
