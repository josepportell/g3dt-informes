#!/usr/bin/env python3
"""Diagnostic trace: full pipeline vs Eva's reference values.

Runs the COMPLETE pipeline (auto_extract + vision + geotech calculations)
via get_prefills(), then compares ALL variables against Eva.

For MISMATCH variables: shows signal competition trace to diagnose root cause.

Usage:
    python scripts/diagnostic_trace.py
    python scripts/diagnostic_trace.py --project 4001612
    python scripts/diagnostic_trace.py --project 4001612 --concept client_name
    python scripts/diagnostic_trace.py --all
    python scripts/diagnostic_trace.py --classify
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, NamedTuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from compare_benchmarks import (
    TEXT_NORMALIZERS, VARIABLE_TIER, compare_numeric, compare_text, parse_numeric,
    _load_env, _load_llm_cache, _save_llm_cache, compare_text_llm,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = _PROJECT_ROOT / "reference-material"

PROJECTS = [
    "4001612 BELL-LLOC",
    "3001621 CASTELLAR DEL VALLES",
    "3001631 RUBI",
    "4001607 LINYOLA",
    "4001670 ALCOLETGE",
    "4001671 VILANOVA DE SEGRIA",
    "4001679 ANCILES",
]

# Eva variable name -> pipeline prefill key
EVA_TO_PREFILL = {
    "architect_name_upper": "architect_name",
    "building_type_lower": "building_type",
    "plantes": "num_floors",
    "client": "client_name",
    "superficie_parcela": "superficie_parcela_m2",
    "superficie_construida": "superficie_construida_m2",
    "sulfate_value": "sulfate_mg_kg",
    "data_camp_text": "field_work_dates_text",
}

# Variables to skip (loop tables, long narrative blocks not comparable as single values)
SKIP_VARS = {
    "geo_p", "materials_intro", "conclusions_levels_detected",
    "conclusions_water_statement", "conclusions_aggressivity_statement",
    "csn_radon_text", "radon_zone_description",
    "empentes_paragraph", "estabilitat_paragraph",
    "photo_site_text", "data_signatura_text",
    "geotech_rows", "dpsh_tests", "sondeig_tests", "seismic_rows", "perm_rows",
    "soil_level_rows",
}

# Numeric variables (use tolerance-based comparison)
NUMERIC_VARS = {
    "superficie_parcela", "superficie_construida", "cota_referencia",
    "sulfate_value", "qa_value", "settlement", "k30_value",
}

# ---------------------------------------------------------------------------
# NE-trace: prefill-key → concept-id bridge (some wizard keys differ from schema)
# ---------------------------------------------------------------------------

PREFILL_TO_CONCEPT: dict[str, str] = {
    'superficie_parcela_m2': 'superficie_parcela',
    'superficie_construida_m2': 'superficie_construida',
}
CONCEPT_TO_PREFILL: dict[str, str] = {v: k for k, v in PREFILL_TO_CONCEPT.items()}

# Source-priority key → file_mapping role (best-effort inference when the
# HITL expected_sources map doesn't have a hint for this concept).
_SOURCE_TO_ROLE: dict[str, list[str]] = {
    'planol_vision': ['architect_plan', 'architect_plan_with_points'],
    'projecte_vision': ['projecte_arquitecte'],
    'sondeig_vision': ['sondeig_field_sheet', 'sondeig_annex'],
    'dpsh_vision': ['dpsh_field_sheet'],
    'gtl_report': ['gtl_report'],
    'pressupost_pdf': ['pressupost_pdf', 'project_email'],
    'dades_camp_excel': ['dades_camp_excel'],
    'coordenades_txt': ['coordenades_txt'],
    'cadastre_api': [],   # API, not a file
    'icgc_api': [],
    'geocode_nominatim': [],
    'folder_name': [],
}

# Sources that don't imply an automatic extractor (require user input or
# are computed from other values).
_NON_EXTRACTOR_SOURCES: set[str] = {'user', 'computed'}


def _load_concept_schema() -> dict[str, dict[str, Any]]:
    """Return {concept_id: {required, source_priority}} from the YAML schema.

    Cached at module import; loaded lazily on first call.
    """
    cache = getattr(_load_concept_schema, '_cache', None)
    if cache is not None:
        return cache
    import yaml
    path = _PROJECT_ROOT / 'schemas' / 'concepts' / 'report_variables.yaml'
    out: dict[str, dict[str, Any]] = {}
    if path.exists():
        try:
            raw = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
            for cid, fields in (raw.get('concepts') or {}).items():
                if not isinstance(fields, dict):
                    continue
                out[cid] = {
                    'required': bool(fields.get('required', False)),
                    'source_priority': dict(fields.get('source_priority') or {}),
                }
        except Exception:
            out = {}
    _load_concept_schema._cache = out  # type: ignore[attr-defined]
    return out


def _infer_expected_roles(concept_id: str, schema_entry: dict | None) -> list[str]:
    """Best-effort: map a concept's source_priority keys to file_mapping roles.

    First checks the HITL expected_sources map; falls back to inferring from
    the schema's source_priority (e.g. 'planol_vision' → 'architect_plan').
    """
    try:
        from web.expected_sources import expected_source_for
        hint = expected_source_for(concept_id)
    except Exception:
        hint = None
    if hint:
        _, role_hints = hint
        if role_hints:
            return list(role_hints)

    if not schema_entry:
        return []
    roles: list[str] = []
    for src_key in schema_entry.get('source_priority', {}):
        for role in _SOURCE_TO_ROLE.get(src_key, []):
            if role not in roles:
                roles.append(role)
    return roles


def _load_file_mapping_roles(project_path: Path) -> set[str]:
    """Return the set of roles present in file_mapping.json."""
    fm_path = project_path / 'file_mapping.json'
    if not fm_path.exists():
        return set()
    try:
        data = json.loads(fm_path.read_text(encoding='utf-8'))
    except Exception:
        return set()
    roles: set[str] = set()
    for role_name, role_data in (data.get('roles') or {}).items():
        if isinstance(role_data, dict) and role_data.get('path'):
            roles.add(role_name)
    return roles


def _load_concept_sources(project_path: Path) -> dict[str, list[dict]]:
    """Return concept_map.json's concept_sources dict, or {} if missing."""
    cm_path = project_path / 'validation' / 'concept_map.json'
    if not cm_path.exists():
        return {}
    try:
        data = json.loads(cm_path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    cs = data.get('concept_sources') or {}
    return cs if isinstance(cs, dict) else {}


def _load_deep_folder_files(project_path: Path) -> dict[str, dict]:
    """Return file_mapping.json's deep_folder_files dict, or {} if missing.

    Backward-compat: falls back to the legacy `email_attachments` key when
    the new key is absent (e.g. for older file_mapping.json snapshots).
    """
    fm_path = project_path / 'file_mapping.json'
    if not fm_path.exists():
        return {}
    try:
        data = json.loads(fm_path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    dff = data.get('deep_folder_files')
    if dff is None:
        dff = data.get('email_attachments') or {}
    return dff if isinstance(dff, dict) else {}


def _count_unclassified_deep_files(deep_folder_files: dict[str, dict]) -> int:
    """Count genuine unclassified entries.

    W3 fix (2026-04-19): predicate previously also counted vision-classified
    entries where the role was already filled (`role_candidate` set but not
    `role_assigned`). Those are NOT unclassified — they're candidates that
    lost to an earlier assignment. Count only explicit `unclassified`.
    """
    return sum(
        1 for v in deep_folder_files.values()
        if v.get('classifier_used') == 'unclassified'
    )


def _classify_ne_reason(
    concept_id: str,
    schema: dict[str, dict],
    fm_roles: set[str],
    concept_sources: dict[str, list[dict]],
    signals_count: int,
) -> tuple[str, str, list[str]]:
    """Classify why a variable was NOT_EXTRACTED.

    Returns (reason_key, suggested_fix, expected_roles).
    """
    schema_entry = schema.get(concept_id)

    # 1. schema_missing
    if schema_entry is None:
        return (
            'schema_missing',
            'Add concept to schemas/concepts/report_variables.yaml with an '
            'appropriate source_priority chain',
            [],
        )

    # 2. no_extractor (only user/computed sources configured)
    src_keys = set(schema_entry.get('source_priority', {}).keys())
    if src_keys and src_keys.issubset(_NON_EXTRACTOR_SOURCES):
        return (
            'no_extractor',
            'Add a fileminer/vision/extractor source for this concept; today '
            'only user input or computed values populate it',
            [],
        )

    expected_roles = _infer_expected_roles(concept_id, schema_entry)

    # 4. extracted_but_filtered (signals emitted but lost)
    if signals_count > 0:
        return (
            'extracted_but_filtered',
            f'{signals_count} signal(s) were emitted but filtered/lost. '
            'Check the signal competition or normalization step.',
            expected_roles,
        )

    cs_entries = concept_sources.get(concept_id, [])

    # 3. no_source_file (expected role absent from file_mapping)
    if expected_roles:
        have_any = any(role in fm_roles for role in expected_roles)
        if not have_any:
            return (
                'no_source_file',
                f'Project lacks a file with role={expected_roles}. If this '
                'is expected (e.g. project has no GTL lab report), confirm — '
                'otherwise the source file is missing.',
                expected_roles,
            )

    # 6. extracted_low_confidence (concept_map has entries, all below threshold)
    if cs_entries:
        try:
            from web.expected_sources import CONFIDENCE_THRESHOLD
        except Exception:
            CONFIDENCE_THRESHOLD = 0.7
        confs = [float(e.get('confidence', 0.0) or 0.0) for e in cs_entries]
        max_conf = max(confs) if confs else 0.0
        if max_conf < CONFIDENCE_THRESHOLD:
            return (
                'extracted_low_confidence',
                f'Value extracted with confidence {max_conf:.0%} — below '
                f'threshold {CONFIDENCE_THRESHOLD:.0%}. Either tighten '
                'extraction or accept lower confidence for this concept.',
                expected_roles,
            )

    # 5. file_had_no_match (file present, extractor ran, no signal)
    return (
        'file_had_no_match',
        'Source file is present but no extractor matched the value. '
        'Tighten the extraction prompt or miner regex for this concept.',
        expected_roles,
    )


# ---------------------------------------------------------------------------
# Component mapping: source string -> component name
# ---------------------------------------------------------------------------

_SOURCE_TO_COMPONENT: list[tuple[re.Pattern, str]] = [
    (re.compile(r'^user$'), 'user'),
    (re.compile(r'^fileminer:'), 'fileminer_regex'),
    (re.compile(r'^groq_llm:'), 'groq_llm'),
    (re.compile(r'^contingut:|^docs intel'), 'content_discovery'),
    (re.compile(r'^pressupost:'), 'fileminer_regex'),
    (re.compile(r'planol', re.IGNORECASE), 'vision_planol'),
    (re.compile(r'sondeig', re.IGNORECASE), 'vision_sondeig'),
    (re.compile(r'dpsh.*vision', re.IGNORECASE), 'vision_dpsh'),
    (re.compile(r'Cadastre|formatted from Cadastre', re.IGNORECASE), 'cadastre'),
    (re.compile(r'^ICGC'), 'icgc'),
    (re.compile(r'geocode', re.IGNORECASE), 'geocode'),
    (re.compile(r'^DPSH'), 'dpsh_extractor'),
    (re.compile(r'LAB|GTL|lab_extractor|sulfat|laboratori', re.IGNORECASE), 'lab_extractor'),
    (re.compile(r'Terzaghi|Schmertmann|Winkler|2\.5.*Nb|^computed\b|\bCTE\b|\bNCSE\b|\bRD 470\b|soil_type=', re.IGNORECASE), 'computed'),
    (re.compile(r'projecte_arquitecte', re.IGNORECASE), 'vision_projecte'),
    (re.compile(r'^cc_extractor_|^vision_pdf|^vision_image', re.IGNORECASE), 'vision_targeted'),
    (re.compile(r'^discovered:|concept_map_fallback', re.IGNORECASE), 'vision_concept_fallback'),
    (re.compile(r'^constant$|^default'), 'constant'),
    (re.compile(r'plantilla generada'), 'template_generated'),
    (re.compile(r'llm_synthesis|^llm'), 'llm_synthesis'),
    (re.compile(r'^system$|concept_scout|Eva template', re.IGNORECASE), 'system'),
]


def classify_source_component(source: str | None) -> str:
    """Map a pipeline source string to a component name."""
    if not source:
        return 'unknown'
    for pattern, component in _SOURCE_TO_COMPONENT:
        if pattern.search(source):
            return component
    return 'unknown'


def _classify_signal_component(sig) -> str:
    """Map a Signal's source_type to a component name."""
    st = getattr(sig, 'source_type', '') or ''
    if st.startswith('planol'):
        return 'vision_planol'
    if st.startswith('sondeig'):
        return 'vision_sondeig'
    if st.startswith('dpsh'):
        return 'vision_dpsh'
    if st == 'groq_llm':
        return 'groq_llm'
    if st:
        return 'fileminer_regex'
    return 'unknown'


# ---------------------------------------------------------------------------
# ProjectDiagResult
# ---------------------------------------------------------------------------

class ProjectDiagResult(NamedTuple):
    """Enriched return from process_project()."""
    results: dict[str, dict]
    auto_result: Any
    project_path: Path
    duration: float
    merged: dict[str, Any] | None
    values: dict[str, Any]
    sources: dict[str, str]
    eva_vars: dict[str, Any]


# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty()

def _color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

def _green(t: str) -> str: return _color(t, "32")
def _yellow(t: str) -> str: return _color(t, "33")
def _red(t: str) -> str: return _color(t, "31")
def _cyan(t: str) -> str: return _color(t, "36")
def _dim(t: str) -> str: return _color(t, "2")
def _bold(t: str) -> str: return _color(t, "1")

def _blue(t: str) -> str: return _color(t, "34")

def _truncate(s: Any, maxlen: int = 55) -> str:
    s = str(s).replace("\n", " ")
    return s[:maxlen - 2] + ".." if len(s) > maxlen else s


# ---------------------------------------------------------------------------
# Phase formatting
# ---------------------------------------------------------------------------

# Map step name prefixes to short labels
_PHASE_LABELS = [
    ("SmartScan", "scan"),
    ("FileScanner", "scan"),
    ("FileMiner", "mine"),
    ("ConceptScout", "scout"),
    ("Deep folder classify", "deep"),
    ("Re-mine promoted", "remine"),
    ("Groq Deep Mine", "groq"),
    ("Contingut", "content"),
    ("Pressupost PDF", "budget"),
    ("Historia geològica", "geo_hist"),
    ("DPSH", "dpsh"),
    ("Dates camp", "dates"),
    ("Lab", "lab"),
    ("Geocodificació", "geocode"),
    ("Elevació", "elev"),
    ("ICGC geologia", "icgc_geo"),
    ("ICGC pendent", "icgc_slope"),
    ("Cadastre", "cadastre"),
    ("Ortho enrichment", "ortho"),
]


def _format_phases(auto_result) -> str:
    """Build one-line phases summary from auto_result."""
    if not auto_result:
        return "Phases: (no auto_result)"

    completed_labels: set[str] = set()
    skipped_map: dict[str, str] = {}  # label -> reason

    for step_str in auto_result.steps_completed:
        for prefix, label in _PHASE_LABELS:
            if step_str.startswith(prefix):
                completed_labels.add(label)
                break

    for step_name, reason in auto_result.steps_skipped:
        for prefix, label in _PHASE_LABELS:
            if step_name.startswith(prefix):
                if label not in completed_labels:
                    # Truncate reason to keep line short
                    short_reason = reason[:20] + ".." if len(reason) > 20 else reason
                    skipped_map[label] = short_reason
                break

    # Build ordered output using _PHASE_LABELS order (deduplicated)
    seen: set[str] = set()
    parts: list[str] = []
    for _, label in _PHASE_LABELS:
        if label in seen:
            continue
        seen.add(label)
        if label in completed_labels:
            parts.append(_green(f"{label}+"))
        elif label in skipped_map:
            parts.append(_dim(f"{label}x({skipped_map[label]})"))

    return f"Phases: {' '.join(parts)}"


# ---------------------------------------------------------------------------
# MISMATCH classification
# ---------------------------------------------------------------------------

_CALC_VARS = {"qa_value", "settlement", "k30_value"}
_ADJACENT_VARS = {"adjacent_east", "adjacent_south", "adjacent_north", "adjacent_west"}
_NARRATIVE_VARS = {"site_description", "building_description", "materials_description"}


def _classify_mismatch(concept_id: str, correct_exists: bool) -> str:
    """Classify a MISMATCH variable into a category."""
    if concept_id in _CALC_VARS:
        return "CALC"
    if concept_id in _ADJACENT_VARS:
        return "FORMAT"
    if concept_id in _NARRATIVE_VARS:
        return "NARRATIVE"
    if correct_exists:
        return "PRIORITY"
    return "EXTRACTION"


def _check_correct_exists(
    concept_id: str,
    eva_name: str,
    eva_value: Any,
    signals_by_concept: dict[str, list],
    mining_alternatives: dict[str, list],
) -> tuple[bool, str]:
    """Check if any signal or alternative matches Eva's value.

    Returns (found, description).
    """
    # Check FileMiner signals
    for i, sig in enumerate(signals_by_concept.get(concept_id, []), 1):
        if _values_match(eva_value, sig.value, eva_name) in ("MATCH", "CLOSE"):
            return True, f"signal #{i} ({sig.source_file[:30]}, pri={sig.priority})"

    # Check mining alternatives
    for i, alt in enumerate(mining_alternatives.get(concept_id, []), 1):
        alt_value = alt.get('value') if isinstance(alt, dict) else getattr(alt, 'value', None)
        if alt_value and _values_match(eva_value, alt_value, eva_name) in ("MATCH", "CLOSE"):
            alt_src = (alt.get('source', '?') if isinstance(alt, dict)
                       else getattr(alt, 'source_file', '?'))
            return True, f"alt #{i} ({alt_src[:30]})"

    return False, "need better extraction"


def _format_calc_trace(concept_id: str, values: dict[str, Any]) -> str | None:
    """Build calc input trace for geotech variables. Returns line or None."""
    if concept_id == "qa_value":
        nb = values.get("dpsh_weighted_nb") or values.get("dpsh_avg_n20") or "?"
        b = values.get("foundation_width", "1.0[DEF]")
        df = values.get("foundation_depth", "0.8[DEF]")
        coh = values.get("cohesion", "?")
        phi = values.get("phi", "?")
        cap = values.get("qa_cap", "3.0")
        return (
            f"Nb={nb}, B={b}, Df={df}, c={coh}, phi={phi}, cap={cap}, "
            f"bearing_idx={values.get('_calc_bearing_idx', '?')}, "
            f"fine_fraction={values.get('_calc_fine_fraction', '?')}, "
            f"cap_reason={values.get('qa_cap_reason', '?')}"
        )
    if concept_id == "settlement":
        es = values.get("es_settlement") or values.get("Es_settlement") or "?"
        qa = values.get("qa_value", "?")
        return f"Es={es}, qa={qa}"
    if concept_id == "k30_value":
        e_val = values.get("young_modulus") or values.get("E") or "?"
        return f"E={e_val}"
    return None


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _values_match(eva_value: Any, candidate_value: Any, var_name: str,
                  tolerance: float = 5.0, llm_client: Any = None) -> str:
    """Compare one value pair. Returns MATCH, CLOSE, or MISMATCH.

    When *llm_client* is provided and the variable is not numeric, uses the
    LLM judge (``compare_text_llm``) for semantic comparison instead of plain
    string matching.
    """
    eva_str = str(eva_value).strip()
    cand_str = str(candidate_value).strip()

    if not eva_str or not cand_str:
        return "NO_DATA"

    if var_name in NUMERIC_VARS:
        eva_num = parse_numeric(eva_str)
        cand_num = parse_numeric(cand_str)
        if eva_num is not None and cand_num is not None:
            _, status = compare_numeric(eva_num, cand_num, tolerance)
            return status

    # LLM judge path (semantic comparison)
    if llm_client is not None:
        status, _score, _explanation = compare_text_llm(var_name, eva_str, cand_str, llm_client)
        return status

    normalizer = TEXT_NORMALIZERS.get(var_name)
    if normalizer:
        return compare_text(normalizer(eva_str), normalizer(cand_str))
    return compare_text(eva_str, cand_str)


# ---------------------------------------------------------------------------
# Full pipeline execution
# ---------------------------------------------------------------------------

def run_full_pipeline(project_name: str) -> tuple[dict[str, Any], dict[str, str], Any, dict[str, Any]]:
    """Run complete pipeline via get_prefills(). Returns (values, sources, auto_result, merged).

    values: {field_name: value}
    sources: {field_name: source_string}
    auto_result: AutoExtractionResult (for signal trace access)
    merged: raw prefills dict (for format_learning, vision_status, deep trace)
    """
    from web.wizard_service import get_prefills, _auto_result_cache

    merged = get_prefills(project_name, force_refresh=True)

    values: dict[str, Any] = {}
    sources: dict[str, str] = {}

    for key, entry in merged.items():
        if key.startswith('_') and not key.startswith('_calc_'):
            continue
        if isinstance(entry, dict):
            values[key] = entry.get('value')
            sources[key] = entry.get('source', '?')
        else:
            values[key] = entry
            sources[key] = '?'

    auto_result = _auto_result_cache.get(project_name)
    return values, sources, auto_result, merged


def load_eva_reference(project_path: Path) -> dict[str, Any]:
    """Load eva_reference_values.json, return {var_name: value}."""
    eva_path = project_path / "validation" / "eva_reference_values.json"
    if not eva_path.exists():
        return {}
    data = json.loads(eva_path.read_text(encoding="utf-8"))
    result = {}
    for var_name, var_info in data.get("variables", {}).items():
        val = var_info.get("value")
        if isinstance(val, (list, dict)):
            continue
        if val is not None:
            result[var_name] = val
    return result


# ---------------------------------------------------------------------------
# PASS detection (source data doesn't exist for project)
# ---------------------------------------------------------------------------

_LAB_PASS_VARS = {
    'lab_location', 'lab_sample_id', 'lab_depth',
    'lab_field_company', 'lab_field_description',
    'lab_testing_company', 'lab_testing_description',
    'lab_tests_text',
}

_SPT_PASS_VARS = {
    'spt_n30', 'spt_depth_range', 'spt_lithology',
    'spt_location', 'spt_test_id',
}


def _get_pass_variables(project_path: Path) -> set[str]:
    """Determine which variables should be PASS (source data doesn't exist)."""
    pass_vars: set[str] = set()

    fm_path = project_path / 'file_mapping.json'
    has_gtl = False
    has_sondeig = False
    if fm_path.exists():
        fm = json.loads(fm_path.read_text(encoding='utf-8'))
        roles = fm.get('roles', {})
        gtl_path = roles.get('gtl_report', {}).get('path', '')
        # Validate: the file must actually be a GTL (not a misclassified pressupost)
        if gtl_path and 'gtl' in gtl_path.lower():
            has_gtl = True
        has_sondeig = (
            bool(roles.get('sondeig_field_sheet', {}).get('path'))
            or bool(roles.get('sondeig_annex', {}).get('path'))
        )

    # Fallback: check for GTL file directly
    if not has_gtl:
        has_gtl = bool(list(project_path.glob('*GTL*'))) or bool(list(project_path.glob('*gtl*')))

    if not has_gtl:
        pass_vars.update(_LAB_PASS_VARS)

    if not has_sondeig:
        pass_vars.update(_SPT_PASS_VARS)

    return pass_vars


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_project(
    project_name: str,
    concept_filter: str | None = None,
    show_all: bool = False,
    tolerance: float = 5.0,
    llm_client: Any = None,
) -> ProjectDiagResult | None:
    """Process one project. Returns ProjectDiagResult or None."""
    project_path = REFERENCE_DIR / project_name

    if not project_path.is_dir():
        print(f"  {project_name}: directory not found, skipping")
        return None

    eva_vars = load_eva_reference(project_path)
    if not eva_vars:
        print(f"  {project_name}: no eva_reference_values.json, skipping")
        return None

    # Run FULL pipeline
    print(f"  Running full pipeline for {project_name}...", end=" ", flush=True)
    t0 = time.time()
    values, sources, auto_result, merged = run_full_pipeline(project_name)
    duration = time.time() - t0
    print(f"({len(values)} values, {duration:.1f}s)")

    # Get signal trace data for MISMATCH debugging
    signals_by_concept: dict[str, list] = defaultdict(list)
    if auto_result and auto_result.mining_result:
        for sig in auto_result.mining_result.signals:
            key = sig.concept_id or sig.maps_to
            if key:
                signals_by_concept[key].append(sig)
        for key in signals_by_concept:
            signals_by_concept[key].sort(key=lambda s: (s.priority, -s.confidence))

    # Check vision status
    val_dir = project_path / "validation"
    vision_files = {
        'planol': (val_dir / 'planol_extracted.json').exists(),
        'sondeig': (val_dir / 'sondeig_extracted.json').exists(),
        'dpsh': (val_dir / 'dpsh_extracted.json').exists(),
    }

    # Determine PASS variables (source data doesn't exist)
    pass_vars = _get_pass_variables(project_path)

    # Build comparison
    results: dict[str, dict] = {}

    for eva_name in sorted(eva_vars.keys()):
        if eva_name in SKIP_VARS:
            continue

        prefill_key = EVA_TO_PREFILL.get(eva_name, eva_name)

        if concept_filter and concept_filter not in prefill_key:
            continue

        eva_value = eva_vars[eva_name]
        pipe_value = values.get(prefill_key)
        pipe_source = sources.get(prefill_key)

        if pipe_value is None or str(pipe_value).strip() == "":
            if prefill_key in pass_vars:
                status = "PASS"
            else:
                status = "NOT_EXTRACTED"
        else:
            status = _values_match(eva_value, pipe_value, eva_name, tolerance, llm_client)

        results[prefill_key] = {
            'eva_name': eva_name,
            'eva_value': eva_value,
            'pipe_value': pipe_value,
            'pipe_source': pipe_source,
            'status': status,
            'component': classify_source_component(pipe_source),
        }

    # --- Print output ---
    print(f"\n{'=' * 90}")
    print(f"  {_bold(project_name)}  (vision: {', '.join(k for k, v in vision_files.items() if v) or 'none'})")
    print(f"  {_format_phases(auto_result)}")
    print(f"{'=' * 90}")

    counts: dict[str, int] = defaultdict(int)
    for r in results.values():
        counts[r['status']] += 1

    n_m, n_c, n_x, n_nd = counts["MATCH"], counts["CLOSE"], counts["MISMATCH"], counts["NOT_EXTRACTED"]
    n_p = counts["PASS"]
    n_total = len(results)
    n_compared = n_m + n_c + n_x
    parts = [
        f"  {_green(f'{n_m} match')}  ",
        f"{_yellow(f'{n_c} close')}  ",
        f"{_red(f'{n_x} mismatch')}  ",
        f"{_dim(f'{n_nd} not_extracted')}  ",
    ]
    if n_p > 0:
        parts.append(f"{_blue(f'{n_p} pass')}  ")
    parts.append(f"/ {n_total} vars")
    print("".join(parts))
    if n_compared > 0:
        pct_ok = round((n_m + n_c) / n_compared * 100, 1)
        print(f"  Match+Close rate: {_bold(f'{pct_ok}%')} (of {n_compared} compared)")

    # Table header
    print(f"\n  {'Variable':<28} {'Eva':<28} {'Pipeline':<28} {'Source':<25} {'Status'}")
    print(f"  {'-' * 28} {'-' * 28} {'-' * 28} {'-' * 25} {'-' * 12}")

    # Sort: MISMATCH first, then CLOSE, then NOT_EXTRACTED, then PASS, then MATCH
    _STATUS_ORDER = {"MISMATCH": 0, "CLOSE": 1, "NOT_EXTRACTED": 2, "PASS": 3, "MATCH": 4}

    for concept_id in sorted(results, key=lambda c: (_STATUS_ORDER.get(results[c]['status'], 9), c)):
        r = results[concept_id]
        status = r['status']

        # In default mode, only show MISMATCH and NOT_EXTRACTED
        if not show_all and status in ("MATCH", "CLOSE", "PASS"):
            continue

        eva_str = _truncate(r['eva_value'], 28)
        pipe_str = _truncate(r['pipe_value'] or '--', 28)
        src_str = _truncate(r['pipe_source'] or '--', 25)

        if status == "MATCH":
            status_str = _green(f"{status:<12}")
        elif status == "CLOSE":
            status_str = _yellow(f"{status:<12}")
        elif status == "NOT_EXTRACTED":
            status_str = _dim(f"{status:<12}")
        elif status == "PASS":
            status_str = _blue(f"{status:<12}")
        else:
            status_str = _red(f"{status:<12}")

        print(f"  {concept_id:<28} {eva_str:<28} {pipe_str:<28} {src_str:<25} {status_str}")

        # For MISMATCH: show signal competition trace + diagnostics
        if status == "MISMATCH":
            # Signal trace (existing)
            if concept_id in signals_by_concept:
                sigs = signals_by_concept[concept_id]
                for i, sig in enumerate(sigs[:5], 1):
                    sig_match = _values_match(r['eva_value'], sig.value, r['eva_name'])
                    if sig_match == "MATCH":
                        val_str = _green(repr(_truncate(sig.value, 35)))
                    elif sig_match == "CLOSE":
                        val_str = _yellow(repr(_truncate(sig.value, 35)))
                    else:
                        val_str = repr(_truncate(sig.value, 35))
                    marker = "  ->" if i == 1 else "   "
                    print(
                        f"  {marker} #{i} pri={sig.priority} conf={sig.confidence:.2f} "
                        f"{val_str}  "
                        f"{_dim(sig.source_file[:40])}"
                    )

            # "Correct exists?" check
            mining_alts = auto_result.mining_alternatives if auto_result else {}
            found, desc = _check_correct_exists(
                concept_id, r['eva_name'], r['eva_value'],
                signals_by_concept, mining_alts,
            )
            if found:
                print(f"    {_cyan('-> Correct exists?')} {_green('YES')} -- {desc}")
            else:
                print(f"    {_cyan('-> Correct exists?')} {_red('NO')} -- {desc}")

            # Calc trace for geotech variables
            calc_trace = _format_calc_trace(concept_id, values)
            if calc_trace:
                print(f"    {_cyan('-> Calc inputs:')} {calc_trace}")

            # Classify and store
            classification = _classify_mismatch(concept_id, found)
            results[concept_id]['classification'] = classification

    # Aggregated summary
    print(f"\n{'─' * 60}")
    print(f"  SUMMARY ({project_name}):")
    _SUMMARY_COLORS = {
        "MATCH": _green, "CLOSE": _yellow, "MISMATCH": _red,
        "NOT_EXTRACTED": _dim, "PASS": _blue,
    }
    for status_name in ["MATCH", "CLOSE", "MISMATCH", "NOT_EXTRACTED", "PASS"]:
        count = counts.get(status_name, 0)
        if count > 0:
            color_fn = _SUMMARY_COLORS.get(status_name, str)
            print(f"    {color_fn(f'{status_name:<16}')} {count:>3}")

    return ProjectDiagResult(
        results=results,
        auto_result=auto_result,
        project_path=project_path,
        duration=duration,
        merged=merged,
        values=values,
        sources=sources,
        eva_vars=eva_vars,
    )


# ---------------------------------------------------------------------------
# Component scorecard
# ---------------------------------------------------------------------------

def _print_component_scorecard(results: dict[str, dict]) -> dict[str, dict]:
    """Build and print per-component accuracy scorecard. Returns component_summary dict."""
    comp_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"match": 0, "close": 0, "mismatch": 0, "not_extracted": 0, "pass": 0})

    for r in results.values():
        comp = r.get('component', 'unknown')
        status = r['status'].lower()
        if status in comp_stats[comp]:
            comp_stats[comp][status] += 1

    print(f"\n  {'Component':<22} {'Produced':>8} {'Match':>7} {'Close':>7} {'Mismatch':>9} {'Accuracy':>9}")
    print(f"  {'-' * 22} {'-' * 8} {'-' * 7} {'-' * 7} {'-' * 9} {'-' * 9}")

    component_summary: dict[str, dict] = {}
    for comp in sorted(comp_stats.keys()):
        s = comp_stats[comp]
        produced = s['match'] + s['close'] + s['mismatch']
        if produced == 0:
            continue
        # Skip system/unknown with zero mismatches
        if comp in ('system', 'unknown') and s['mismatch'] == 0:
            continue
        accuracy = round((s['match'] + s['close']) / produced * 100, 1) if produced > 0 else 0.0
        acc_str = f"{accuracy}%" if produced > 0 else "N/A"
        if accuracy == 100.0:
            acc_str = _green(acc_str)
        elif accuracy >= 80.0:
            acc_str = _yellow(acc_str)
        else:
            acc_str = _red(acc_str)

        print(f"  {comp:<22} {produced:>8} {s['match']:>7} {s['close']:>7} {s['mismatch']:>9} {acc_str:>9}")
        component_summary[comp] = {
            "produced": produced,
            "match": s['match'],
            "close": s['close'],
            "mismatch": s['mismatch'],
            "not_extracted": s['not_extracted'],
            "accuracy_pct": accuracy,
        }

    return component_summary


# ---------------------------------------------------------------------------
# Snapshot functions
# ---------------------------------------------------------------------------

def _collect_metadata(
    auto_result,
    project_path: Path,
    tolerance: float,
    vision_status: dict[str, bool],
    duration: float,
    merged: dict[str, Any] | None = None,
    judge_enabled: bool = False,
) -> dict:
    """Collect operational metadata for snapshot."""
    from automation import config

    models = {
        "openai_vision": config.VISION_MODEL_OPENAI,
        "anthropic_text": config.TEXT_MODEL_ANTHROPIC,
        "groq_text": config.TEXT_MODEL_GROQ,
        "groq_vision": config.VISION_MODEL_GROQ,
    }
    fallback_order = {
        "vision": config.VISION_FALLBACK_ORDER,
        "probe": config.PROBE_FALLBACK_ORDER,
    }
    phases_completed = []
    phases_skipped = []
    if auto_result:
        phases_completed = list(auto_result.steps_completed)
        phases_skipped = [{"step": s, "reason": r} for s, r in auto_result.steps_skipped]

    # Judge model: literal id used (or None if --no-llm-judge)
    judge_model: str | None = None
    if judge_enabled:
        try:
            from automation.llm_client import get_judge_model
            judge_model = get_judge_model()
        except Exception:
            judge_model = None

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "run_id": uuid.uuid4().hex[:6],
        "project": project_path.name,
        "models": models,
        "fallback_order": fallback_order,
        "phases_completed": phases_completed,
        "phases_skipped": phases_skipped,
        "vision_status": vision_status,
        "duration_seconds": round(duration, 1),
        "tolerance_pct": tolerance,
        "judge_enabled": judge_enabled,
        "judge_model": judge_model,
    }


# ---------------------------------------------------------------------------
# v1.1 metadata builders
# ---------------------------------------------------------------------------

def _empty_provider_summary(model: str = "") -> dict:
    return {
        "model": model,
        "api_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "usd": 0.0,
    }


def _parse_groq_step(steps_completed: list[str]) -> dict | None:
    """Parse the Groq Deep Mine step line emitted at auto_extractor.py:719-724.

    Format: "Groq Deep Mine (model): N senyals, M nous prefills, K calls,
    H cache hits, T tokens (~$U)"
    Returns dict with model, api_calls, input_tokens (best-effort), output_tokens,
    or None if not present / parse failed.
    """
    for step in steps_completed:
        if not step.startswith("Groq Deep Mine"):
            continue
        try:
            model_match = re.search(r'Groq Deep Mine \(([^)]+)\)', step)
            calls_match = re.search(r'(\d+)\s+calls', step)
            tokens_match = re.search(r'(\d+)\s+tokens', step)
            return {
                "model": model_match.group(1) if model_match else "",
                "api_calls": int(calls_match.group(1)) if calls_match else 0,
                "total_tokens": int(tokens_match.group(1)) if tokens_match else 0,
            }
        except Exception:
            return None
    return None


def _build_cost_summary(auto_result) -> dict:
    """Cost summary across providers. Always returns {groq, anthropic, openai, total_usd}."""
    try:
        from automation.llm_pricing import estimate_cost
    except Exception:
        estimate_cost = lambda *a, **kw: 0.0  # noqa: E731

    groq = _empty_provider_summary()
    anthropic = _empty_provider_summary()
    openai = _empty_provider_summary()

    # --- Groq ---
    if auto_result is not None:
        try:
            from automation.fileminer.miners.groq_miner import GroqMiner
            usage = GroqMiner.get_usage_summary()
            groq = {
                "model": usage.get("model", ""),
                "api_calls": usage.get("api_calls", 0),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "usd": float(usage.get("estimated_cost_usd", 0.0)),
            }
        except Exception:
            parsed = _parse_groq_step(getattr(auto_result, 'steps_completed', []) or [])
            if parsed:
                groq["model"] = parsed["model"]
                groq["api_calls"] = parsed["api_calls"]

    # --- Anthropic (drain pop_traces + read auto_result.targeted_extraction_traces) ---
    try:
        from automation.targeted_extraction import pop_traces
        drained = pop_traces()
    except Exception:
        drained = []
    existing = list(getattr(auto_result, 'targeted_extraction_traces', None) or [])
    if drained and auto_result is not None:
        try:
            auto_result.targeted_extraction_traces.extend(drained)
        except Exception:
            pass
    all_traces = existing + drained

    if all_traces:
        import os as _os
        anth_model = _os.environ.get('CC_AGENTIC_MODEL', 'claude-sonnet-4-6')
        in_tok = sum((t.get('total_usage') or {}).get('input_tokens', 0) for t in all_traces)
        out_tok = sum((t.get('total_usage') or {}).get('output_tokens', 0) for t in all_traces)
        api_calls = sum((t.get('total_usage') or {}).get('api_calls', 0) for t in all_traces)
        anthropic = {
            "model": anth_model,
            "api_calls": api_calls,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "usd": round(estimate_cost("anthropic", anth_model, in_tok, out_tok), 6),
        }

    # --- OpenAI vision usage (drain accumulator from web.vision_groq) ---
    try:
        from web.vision_groq import pop_openai_usage
        oai = pop_openai_usage()
    except Exception:
        oai = None
    if oai and oai.get("api_calls", 0) > 0:
        oai_model = oai.get("model", "") or "gpt-4.1-mini"
        in_tok = oai.get("input_tokens", 0)
        out_tok = oai.get("output_tokens", 0)
        openai = {
            "model": oai_model,
            "api_calls": oai["api_calls"],
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "usd": round(estimate_cost("openai", oai_model, in_tok, out_tok), 6),
        }

    return {
        "groq": groq,
        "anthropic": anthropic,
        "openai": openai,
        "total_usd": round(groq["usd"] + anthropic["usd"] + openai["usd"], 6),
    }


def _build_concept_scout_summary(auto_result) -> dict:
    """Read concept_map.metadata if present; else return {}."""
    if auto_result is None:
        return {}
    cm = getattr(auto_result, 'concept_map', None)
    if cm is None:
        return {}
    meta = getattr(cm, 'metadata', None) or {}
    if not isinstance(meta, dict):
        return {}
    keys = ('total_files', 'vision_probes_sent', 'total_concepts_found',
            'total_concepts_unresolved', 'duration_ms')
    return {k: meta.get(k, 0) for k in keys}


def _build_missing_summary(merged: dict[str, Any] | None) -> dict:
    """Read _missing_summary from merged; aggregate by_reason across all groups."""
    by_reason = {
        "no_source_file": 0,
        "file_had_no_match": 0,
        "extracted_low_confidence": 0,
    }
    if not isinstance(merged, dict):
        return {"total_missing": 0, "total_groups": 0, "by_reason": by_reason}
    ms = merged.get('_missing_summary')
    if not isinstance(ms, dict):
        return {"total_missing": 0, "total_groups": 0, "by_reason": by_reason}
    val = ms.get('value') or {}
    if not isinstance(val, dict):
        return {"total_missing": 0, "total_groups": 0, "by_reason": by_reason}

    for grp in val.get('groups', []) or []:
        for reason in (grp.get('reasons') or {}).values():
            if reason in by_reason:
                by_reason[reason] += 1

    return {
        "total_missing": int(val.get('total_missing', 0) or 0),
        "total_groups": int(val.get('total_groups', 0) or 0),
        "by_reason": by_reason,
    }


def _build_targeted_extraction_summary(auto_result) -> dict:
    """Aggregate auto_result.targeted_extraction_traces.

    NOTE: assumes _build_cost_summary already drained pop_traces() into
    auto_result.targeted_extraction_traces. Callable independently — falls
    back to whatever is on auto_result if pop has not been invoked yet.
    """
    try:
        from automation.llm_pricing import estimate_cost
    except Exception:
        estimate_cost = lambda *a, **kw: 0.0  # noqa: E731

    traces = list(getattr(auto_result, 'targeted_extraction_traces', None) or [])
    in_tok = sum((t.get('total_usage') or {}).get('input_tokens', 0) for t in traces)
    out_tok = sum((t.get('total_usage') or {}).get('output_tokens', 0) for t in traces)
    api_calls = sum((t.get('total_usage') or {}).get('api_calls', 0) for t in traces)
    files = {t.get('file_path') for t in traces if t.get('file_path')}

    import os as _os
    anth_model = _os.environ.get('CC_AGENTIC_MODEL', 'claude-sonnet-4-6')
    usd = round(estimate_cost("anthropic", anth_model, in_tok, out_tok), 6)

    return {
        "calls": len(traces),
        "files_processed": len(files),
        "vision_calls": api_calls,
        "total_input_tokens": in_tok,
        "total_output_tokens": out_tok,
        "usd": usd,
    }


def _build_snapshot(
    project_name: str,
    results: dict[str, dict],
    auto_result,
    project_path: Path,
    metadata: dict,
    component_summary: dict[str, dict],
    merged: dict[str, Any] | None = None,
    values: dict[str, Any] | None = None,
) -> dict:
    """Build complete snapshot dict."""
    # Summary counts
    counts: dict[str, int] = defaultdict(int)
    for r in results.values():
        counts[r['status']] += 1
    n_m, n_c, n_x, n_nd = counts["MATCH"], counts["CLOSE"], counts["MISMATCH"], counts["NOT_EXTRACTED"]
    n_p = counts["PASS"]
    n_total = sum(counts.values())
    n_compared = n_m + n_c + n_x
    match_close_pct = round((n_m + n_c) / n_compared * 100, 1) if n_compared > 0 else 0.0

    # Tier summary
    _TIER_INIT = {"total": 0, "match": 0, "close": 0, "mismatch": 0, "not_extracted": 0, "pass": 0}
    tier_summary: dict[str, dict[str, int]] = {}
    for tier in ("A", "B", "C"):
        tier_summary[tier] = dict(_TIER_INIT)
    for concept_id, r in results.items():
        tier = VARIABLE_TIER.get(concept_id, VARIABLE_TIER.get(r.get('eva_name', ''), 'A'))
        status_key = r['status'].lower()
        if tier not in tier_summary:
            tier_summary[tier] = dict(_TIER_INIT)
        tier_summary[tier]["total"] += 1
        if status_key in tier_summary[tier]:
            tier_summary[tier][status_key] += 1

    # Build per-variable detail
    signals_by_concept: dict[str, list] = defaultdict(list)
    if auto_result and auto_result.mining_result:
        for sig in auto_result.mining_result.signals:
            key = sig.concept_id or sig.maps_to
            if key:
                signals_by_concept[key].append(sig)
        for key in signals_by_concept:
            signals_by_concept[key].sort(key=lambda s: (s.priority, -s.confidence))

    mining_alts = auto_result.mining_alternatives if auto_result else {}

    variables: dict[str, dict] = {}
    for concept_id, r in results.items():
        tier = VARIABLE_TIER.get(concept_id, VARIABLE_TIER.get(r.get('eva_name', ''), 'A'))
        correct_exists, correct_desc = _check_correct_exists(
            concept_id, r['eva_name'], r['eva_value'],
            signals_by_concept, mining_alts,
        )

        # Build signals list
        sig_list = []
        for i, sig in enumerate(signals_by_concept.get(concept_id, []), 1):
            sig_match = _values_match(r['eva_value'], sig.value, r['eva_name'])
            sig_list.append({
                "rank": i,
                "value": str(sig.value) if sig.value is not None else None,
                "source_file": sig.source_file,
                "source_type": getattr(sig, 'source_type', ''),
                "component": _classify_signal_component(sig),
                "extraction_method": getattr(sig, 'extraction_method', ''),
                "priority": sig.priority,
                "confidence": sig.confidence,
                "matches_eva": sig_match,
            })

        # Calc trace for computed variables
        calc_values = values or (auto_result.prefills if auto_result and hasattr(auto_result, 'prefills') else {})
        calc_trace = _format_calc_trace(concept_id, calc_values)

        # v1.1: surface extraction_method, missing_reason, confidence per variable
        merged_entry = merged.get(concept_id) if isinstance(merged, dict) else None
        sigs_for_concept = signals_by_concept.get(concept_id, [])
        winning_signal = sigs_for_concept[0] if sigs_for_concept else None
        if winning_signal is not None:
            extraction_method = getattr(winning_signal, 'extraction_method', None) or None
        else:
            extraction_method = (
                merged_entry.get('extraction_method')
                if isinstance(merged_entry, dict) else None
            )
        missing_reason = (
            merged_entry.get('missing_reason')
            if isinstance(merged_entry, dict) else None
        )
        confidence: float | None = None
        for sig in sigs_for_concept:
            c = getattr(sig, 'confidence', None)
            if isinstance(c, (int, float)):
                cf = float(c)
                confidence = cf if confidence is None else max(confidence, cf)
        if confidence is None and isinstance(merged_entry, dict):
            mc = merged_entry.get('confidence')
            if isinstance(mc, (int, float)):
                confidence = float(mc)

        variables[concept_id] = {
            "eva_name": r['eva_name'],
            "eva_value": str(r['eva_value']) if r['eva_value'] is not None else None,
            "pipeline_value": str(r['pipe_value']) if r['pipe_value'] is not None else None,
            "source": r['pipe_source'],
            "component": r.get('component', 'unknown'),
            "tier": tier,
            "status": r['status'],
            "classification": r.get('classification'),
            "correct_exists": correct_exists,
            "correct_alternative_desc": correct_desc if correct_exists else None,
            "signals": sig_list,
            "calc_trace": calc_trace,
            "extraction_method": extraction_method,
            "missing_reason": missing_reason,
            "confidence": confidence,
        }

    # Format learning
    format_learning = []
    if merged:
        fl = merged.get('_format_learning', {})
        if isinstance(fl, dict):
            fl_val = fl.get('value', {})
            if isinstance(fl_val, dict):
                for det in fl_val.get('detections', []):
                    format_learning.append(det)

    # v1.1: top-level summary blocks (siblings of metadata/summary/variables)
    cost_summary = _build_cost_summary(auto_result)
    concept_scout = _build_concept_scout_summary(auto_result)
    missing_summary = _build_missing_summary(merged)
    targeted_extraction_summary = _build_targeted_extraction_summary(auto_result)

    return {
        "schema_version": "1.2",
        "metadata": metadata,
        "summary": {
            "total_vars": n_total,
            "match": n_m,
            "close": n_c,
            "mismatch": n_x,
            "not_extracted": n_nd,
            "pass": n_p,
            "match_close_pct": match_close_pct,
        },
        "tier_summary": tier_summary,
        "component_summary": component_summary,
        "variables": variables,
        "format_learning": format_learning,
        "cost_summary": cost_summary,
        "concept_scout": concept_scout,
        "missing_summary": missing_summary,
        "targeted_extraction_summary": targeted_extraction_summary,
        "ne_trace": [],
    }


def _save_snapshot(snapshot: dict, output_dir: Path) -> Path:
    """Save snapshot JSON to docs/diagnostics/. Returns path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = snapshot.get("metadata", {})
    date = time.strftime("%Y-%m-%d")
    project = meta.get("project", "unknown").replace(" ", "_")
    run_id = meta.get("run_id", "000000")
    filename = f"{date}_{project}_{run_id}.json"
    path = output_dir / filename
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def _build_cross_summary(snapshots: list[dict]) -> dict:
    """Build cross-project summary from individual snapshots."""
    global_summary: dict[str, int] = {"total_vars": 0, "match": 0, "close": 0, "mismatch": 0, "not_extracted": 0, "pass": 0}
    global_tier: dict[str, dict[str, int]] = {}
    global_comp: dict[str, dict[str, float]] = {}
    cross_vars: dict[str, dict[str, str]] = {}  # var -> {project: status}
    classification_summary: dict[str, list[str]] = defaultdict(list)

    for snap in snapshots:
        proj = snap.get("metadata", {}).get("project", "?")
        summ = snap.get("summary", {})
        for key in ("total_vars", "match", "close", "mismatch", "not_extracted", "pass"):
            global_summary[key] += summ.get(key, 0)

        # Tier aggregation
        for tier, tier_data in snap.get("tier_summary", {}).items():
            if tier not in global_tier:
                global_tier[tier] = {"total": 0, "match": 0, "close": 0, "mismatch": 0, "not_extracted": 0, "pass": 0}
            for k in ("total", "match", "close", "mismatch", "not_extracted", "pass"):
                global_tier[tier][k] += tier_data.get(k, 0)

        # Component aggregation
        for comp, comp_data in snap.get("component_summary", {}).items():
            if comp not in global_comp:
                global_comp[comp] = {"produced": 0, "match": 0, "close": 0, "mismatch": 0, "not_extracted": 0, "pass": 0}
            for k in ("produced", "match", "close", "mismatch", "not_extracted", "pass"):
                global_comp[comp][k] += comp_data.get(k, 0)

        # Cross-variable matrix
        for var, var_data in snap.get("variables", {}).items():
            if var not in cross_vars:
                cross_vars[var] = {}
            cross_vars[var][proj] = var_data.get("status", "?")
            cls = var_data.get("classification")
            if cls:
                classification_summary[cls].append(f"{var}({proj.split()[0]})")

    # Compute accuracy for global components
    for comp in global_comp:
        produced = global_comp[comp]["produced"]
        if produced > 0:
            global_comp[comp]["accuracy_pct"] = round(
                (global_comp[comp]["match"] + global_comp[comp]["close"]) / produced * 100, 1
            )
        else:
            global_comp[comp]["accuracy_pct"] = 0.0

    n_compared = global_summary["match"] + global_summary["close"] + global_summary["mismatch"]
    global_summary["match_close_pct"] = (
        round((global_summary["match"] + global_summary["close"]) / n_compared * 100, 1)
        if n_compared > 0 else 0.0
    )

    # v1.1: aggregate cost + concept_scout across snapshots.
    global_cost_summary = {
        "groq": {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "usd": 0.0},
        "anthropic": {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "usd": 0.0},
        "total_usd": 0.0,
    }
    global_concept_scout = {
        "total_files": 0,
        "vision_probes_sent": 0,
        "total_concepts_found": 0,
        "total_concepts_unresolved": 0,
        "duration_ms": 0,
    }
    for snap in snapshots:
        meta = snap.get("metadata", {}) or {}
        # v1.1 keys live at top-level; fall back to metadata for legacy snapshots.
        cs = snap.get("cost_summary") or meta.get("cost_summary") or {}
        for prov in ("groq", "anthropic"):
            ps = cs.get(prov) or {}
            for k in ("input_tokens", "output_tokens", "api_calls"):
                global_cost_summary[prov][k] += int(ps.get(k, 0) or 0)
            global_cost_summary[prov]["usd"] = round(
                global_cost_summary[prov]["usd"] + float(ps.get("usd", 0.0) or 0.0), 6,
            )
        global_cost_summary["total_usd"] = round(
            global_cost_summary["total_usd"] + float(cs.get("total_usd", 0.0) or 0.0), 6,
        )

        sc = snap.get("concept_scout") or meta.get("concept_scout") or {}
        # max for total_files (one project at a time has its own file count)
        global_concept_scout["total_files"] = max(
            global_concept_scout["total_files"], int(sc.get("total_files", 0) or 0),
        )
        for k in ("vision_probes_sent", "total_concepts_found",
                  "total_concepts_unresolved", "duration_ms"):
            global_concept_scout[k] += int(sc.get(k, 0) or 0)

    return {
        "schema_version": "1.2",
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "run_id": uuid.uuid4().hex[:6],
            "num_projects": len(snapshots),
        },
        "global_summary": global_summary,
        "global_tier_summary": global_tier,
        "global_component_summary": global_comp,
        "cross_variable_matrix": cross_vars,
        "classification_summary": dict(classification_summary),
        "global_cost_summary": global_cost_summary,
        "global_concept_scout": global_concept_scout,
        "projects": [snap.get("metadata", {}).get("project", "?") for snap in snapshots],
    }


# ---------------------------------------------------------------------------
# Deep trace
# ---------------------------------------------------------------------------

def _deep_trace_variable(
    concept_id: str,
    result: dict,
    auto_result,
    eva_vars: dict,
    values: dict[str, Any],
    sources: dict[str, str],
    merged: dict[str, Any] | None = None,
    llm_client: Any = None,
) -> None:
    """Print full 6-section deep trace for a variable."""
    r = result
    eva_name = r['eva_name']
    eva_value = r['eva_value']
    tier = VARIABLE_TIER.get(concept_id, VARIABLE_TIER.get(eva_name, 'A'))

    print(f"\n{'=' * 80}")
    print(f"  === DEEP TRACE: {concept_id} (Tier {tier}) ===")
    print(f"{'=' * 80}")

    # Section 1: EVA REFERENCE
    print(f"\n  {_bold('1. EVA REFERENCE')}")
    print(f"     Eva key: \"{eva_name}\"")
    print(f"     Eva value: \"{eva_value}\"")

    # Section 2: DOCUMENT SOURCES (format learning detections)
    print(f"\n  {_bold('2. DOCUMENT SOURCES')}")
    if merged:
        fl = merged.get('_format_learning', {})
        if isinstance(fl, dict):
            fl_val = fl.get('value', {})
            if isinstance(fl_val, dict):
                detections = fl_val.get('detections', [])
                if detections:
                    for det in detections:
                        fp = det.get('file_path', '?')
                        role = det.get('role', '?')
                        coverage = det.get('extraction_coverage', 0)
                        missing = det.get('missing_fields', [])
                        relevant = concept_id in missing
                        marker = _red(" <-- MISSING") if relevant else ""
                        print(f"     {role} ({fp}): coverage {coverage:.0%} -- missing: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}{marker}")
                else:
                    print(f"     (no format learning detections)")
            else:
                print(f"     (no format learning data)")
        else:
            print(f"     (no format learning data)")
    else:
        print(f"     (no merged data available)")

    # Build signal data
    signals_by_concept: dict[str, list] = defaultdict(list)
    if auto_result and auto_result.mining_result:
        for sig in auto_result.mining_result.signals:
            key = sig.concept_id or sig.maps_to
            if key:
                signals_by_concept[key].append(sig)
        for key in signals_by_concept:
            signals_by_concept[key].sort(key=lambda s: (s.priority, -s.confidence))

    sigs = signals_by_concept.get(concept_id, [])
    is_computed = concept_id in _CALC_VARS

    # Section 3: ALL SIGNALS or CALC INPUTS
    if is_computed:
        print(f"\n  {_bold('3. CALC INPUTS')}")
        calc_trace = _format_calc_trace(concept_id, values)
        if calc_trace:
            for part in calc_trace.split(', '):
                print(f"     {part}")
        else:
            print(f"     (no calc inputs available)")
        if sigs:
            print(f"     ({len(sigs)} signals also present)")
    else:
        print(f"\n  {_bold(f'3. ALL SIGNALS ({len(sigs)} found)')}")
        if sigs:
            print(f"     {'#':<4} {'Component':<20} {'File':<30} {'Method':<16} {'Value':<30} {'Pri':>4} {'Conf':>5} Eva?")
            print(f"     {'-'*4} {'-'*20} {'-'*30} {'-'*16} {'-'*30} {'-'*4} {'-'*5} {'-'*10}")
            for i, sig in enumerate(sigs, 1):
                sig_match = _values_match(eva_value, sig.value, eva_name)
                comp = _classify_signal_component(sig)
                method = getattr(sig, 'extraction_method', '?')[:16]
                val_str = repr(_truncate(sig.value, 28))
                if sig_match == "MATCH":
                    match_str = _green("MATCH")
                elif sig_match == "CLOSE":
                    match_str = _yellow("CLOSE")
                else:
                    match_str = sig_match
                print(
                    f"     {i:<4} {comp:<20} {sig.source_file[:30]:<30} {method:<16} "
                    f"{val_str:<30} {sig.priority:>4} {sig.confidence:>5.2f} {match_str}"
                )
        else:
            print(f"     (no signals found for this concept)")

    # Section 4: COMPETITION RESOLUTION
    print(f"\n  {_bold('4. COMPETITION RESOLUTION')}")
    if len(sigs) >= 2:
        winner = sigs[0]
        runner = sigs[1]
        w_comp = _classify_signal_component(winner)
        r_comp = _classify_signal_component(runner)
        reason = f"priority {winner.priority} < {runner.priority}" if winner.priority != runner.priority else f"confidence {winner.confidence:.2f} > {runner.confidence:.2f}"
        print(f"     Winner: #1 ({w_comp}, pri={winner.priority}, conf={winner.confidence:.2f})")
        print(f"     Runner-up: #2 ({r_comp}, pri={runner.priority}, conf={runner.confidence:.2f})")
        print(f"     Reason: {reason}")
    elif len(sigs) == 1:
        w_comp = _classify_signal_component(sigs[0])
        print(f"     Single signal: ({w_comp}, pri={sigs[0].priority}, conf={sigs[0].confidence:.2f})")
    elif is_computed:
        print(f"     (computed variable, no signal competition)")
    else:
        pipe_source = r.get('pipe_source', '?')
        print(f"     (no mining signals; value from: {pipe_source})")

    # Section 5: FINAL COMPARISON
    print(f"\n  {_bold('5. FINAL COMPARISON')}")
    pipe_val = r['pipe_value']
    pipe_src = r['pipe_source'] or '?'
    print(f"     Pipeline: \"{pipe_val}\"  [source: {pipe_src}]")
    print(f"     Eva:      \"{eva_value}\"")
    status = r['status']
    if status == "MATCH":
        print(f"     Status:   {_green(status)}")
    elif status == "CLOSE":
        print(f"     Status:   {_yellow(status)}")
    elif status == "MISMATCH":
        print(f"     Status:   {_red(status)}")
    elif status == "PASS":
        print(f"     Status:   {_blue(status)}")
    else:
        print(f"     Status:   {_dim(status)}")
    # Numeric deviation
    if eva_name in NUMERIC_VARS and pipe_val is not None:
        eva_num = parse_numeric(str(eva_value))
        pipe_num = parse_numeric(str(pipe_val))
        if eva_num is not None and pipe_num is not None and eva_num != 0:
            dev = round((pipe_num - eva_num) / eva_num * 100, 1)
            print(f"     Deviation: {dev:+.1f}%")

    # Section 6: ROBUSTNESS
    print(f"\n  {_bold('6. ROBUSTNESS')}")
    if sigs:
        n_match_eva = sum(1 for s in sigs if _values_match(eva_value, s.value, eva_name) in ("MATCH", "CLOSE"))
        print(f"     Signals matching Eva (MATCH or CLOSE): {n_match_eva} of {len(sigs)} ({round(n_match_eva / len(sigs) * 100)}%)")
        if len(sigs) >= 2:
            next_match = None
            for i, s in enumerate(sigs[1:], 2):
                if _values_match(eva_value, s.value, eva_name) in ("MATCH", "CLOSE"):
                    next_match = (i, s)
                    break
            if next_match:
                print(f"     If winner removed -> next match at #{next_match[0]} (pri={next_match[1].priority}) -> still correct")
                print(f"     Assessment: {_green('ROBUST')} (multiple confirming sources)")
            else:
                print(f"     If winner removed -> no other signal matches Eva")
                print(f"     Assessment: {_yellow('FRAGILE')} (single confirming source)")
        else:
            print(f"     Assessment: {_yellow('FRAGILE')} (only 1 signal)")
    elif is_computed:
        print(f"     (computed variable, robustness depends on input signals)")
    else:
        print(f"     Assessment: {_red('NO SIGNALS')} (value from non-mining source)")


# ---------------------------------------------------------------------------
# Cross-run diff
# ---------------------------------------------------------------------------

def _diff_snapshots(path_a: Path, path_b: Path) -> None:
    """Load two snapshots, print status changes and component accuracy deltas."""
    snap_a = json.loads(path_a.read_text(encoding="utf-8"))
    snap_b = json.loads(path_b.read_text(encoding="utf-8"))

    meta_a = snap_a.get("metadata", {})
    meta_b = snap_b.get("metadata", {})

    print(f"\n{'=' * 80}")
    print(f"  === RUN DIFF ===")
    print(f"{'=' * 80}")
    print(f"  Run A: {path_a.name}")
    print(f"         project={meta_a.get('project', '?')}  groq={meta_a.get('models', {}).get('groq_text', '?')}")
    print(f"  Run B: {path_b.name}")
    print(f"         project={meta_b.get('project', '?')}  groq={meta_b.get('models', {}).get('groq_text', '?')}")
    sv_a = snap_a.get('schema_version', '1.0')
    sv_b = snap_b.get('schema_version', '1.0')
    print(f"  schema: {sv_a} -> {sv_b}")

    vars_a = snap_a.get("variables", {})
    vars_b = snap_b.get("variables", {})
    all_vars = sorted(set(vars_a.keys()) | set(vars_b.keys()))

    improvements = 0
    regressions = 0
    unchanged = 0

    _STATUS_RANK = {"MATCH": 0, "CLOSE": 1, "MISMATCH": 2, "PASS": 3, "NOT_EXTRACTED": 4}

    print(f"\n  {'Variable':<28} {'Run A':<16} {'Run B':<16} Change")
    print(f"  {'-' * 28} {'-' * 16} {'-' * 16} {'-' * 16}")

    value_changed = 0

    for var in all_vars:
        sa = vars_a.get(var, {}).get("status", "ABSENT")
        sb = vars_b.get(var, {}).get("status", "ABSENT")
        if sa == sb:
            # Same status — check if underlying value changed (relevant for CLOSE/MISMATCH)
            if sa in ("CLOSE", "MISMATCH"):
                va = vars_a.get(var, {}).get("pipeline_value", "")
                vb = vars_b.get(var, {}).get("pipeline_value", "")
                if str(va) != str(vb):
                    print(f"  {var:<28} {sa:<16} {sb:<16} = (value changed: {va} -> {vb})")
                    value_changed += 1
            unchanged += 1
            continue
        rank_a = _STATUS_RANK.get(sa, 9)
        rank_b = _STATUS_RANK.get(sb, 9)
        if rank_b < rank_a:
            change = _green("IMPROVEMENT")
            improvements += 1
        else:
            change = _red("REGRESSION")
            regressions += 1

        print(f"  {var:<28} {sa:<16} {sb:<16} {change}")

    vc_note = f", {value_changed} value-changed" if value_changed else ""
    print(f"\n  Summary: {_green(f'{improvements} improvements')}, {_red(f'{regressions} regressions')}, {unchanged} unchanged{vc_note}")

    # Component accuracy deltas
    comp_a = snap_a.get("component_summary", {})
    comp_b = snap_b.get("component_summary", {})
    all_comps = sorted(set(comp_a.keys()) | set(comp_b.keys()))

    if all_comps:
        print(f"\n  Component accuracy delta:")
        for comp in all_comps:
            acc_a = comp_a.get(comp, {}).get("accuracy_pct", 0.0)
            acc_b = comp_b.get(comp, {}).get("accuracy_pct", 0.0)
            delta = acc_b - acc_a
            if abs(delta) < 0.1:
                delta_str = "="
            elif delta > 0:
                delta_str = _green(f"+{delta:.1f}%")
            else:
                delta_str = _red(f"{delta:.1f}%")
            print(f"    {comp:<22}: {acc_a:.1f}% -> {acc_b:.1f}% ({delta_str})")

    # v1.1: cost-summary delta when both snapshots expose it.
    # Top-level in v1.1; fall back to metadata for legacy snapshots.
    cost_a = snap_a.get("cost_summary") or meta_a.get("cost_summary") or {}
    cost_b = snap_b.get("cost_summary") or meta_b.get("cost_summary") or {}
    if cost_a and cost_b:
        print(f"\n  Cost summary delta:")
        for prov in ("groq", "anthropic"):
            usd_a = float((cost_a.get(prov) or {}).get("usd", 0.0) or 0.0)
            usd_b = float((cost_b.get(prov) or {}).get("usd", 0.0) or 0.0)
            print(f"    {prov:<10} usd: ${usd_a:.4f} -> ${usd_b:.4f} ({usd_b - usd_a:+.4f})")
        tot_a = float(cost_a.get("total_usd", 0.0) or 0.0)
        tot_b = float(cost_b.get("total_usd", 0.0) or 0.0)
        print(f"    {'total':<10} usd: ${tot_a:.4f} -> ${tot_b:.4f} ({tot_b - tot_a:+.4f})")


def print_cross_project_summary(
    all_results: dict[str, dict[str, dict]],
    *,
    classify: bool = False,
) -> None:
    """Print cross-project comparison matrix."""
    # Aggregate per variable
    var_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for project_name, results in all_results.items():
        for concept_id, r in results.items():
            var_stats[concept_id][r['status']] += 1

    print(f"\n{'=' * 100}")
    print(f"  CROSS-PROJECT SUMMARY ({len(all_results)} projects)")
    print(f"{'=' * 100}")

    # Global counts
    g_counts: dict[str, int] = defaultdict(int)
    for results in all_results.values():
        for r in results.values():
            g_counts[r['status']] += 1
    g_total = sum(g_counts.values())
    g_compared = g_counts["MATCH"] + g_counts["CLOSE"] + g_counts["MISMATCH"]
    gm = g_counts["MATCH"]
    gc = g_counts["CLOSE"]
    gx = g_counts["MISMATCH"]
    gnd = g_counts["NOT_EXTRACTED"]
    gp = g_counts["PASS"]
    cross_parts = [
        f"  Total: {g_total} var-comparisons  |  ",
        f"{_green(f'{gm} match')}  ",
        f"{_yellow(f'{gc} close')}  ",
        f"{_red(f'{gx} mismatch')}  ",
        f"{_dim(f'{gnd} not_extracted')}",
    ]
    if gp > 0:
        cross_parts.append(f"  {_blue(f'{gp} pass')}")
    print("".join(cross_parts)
    )
    if g_compared > 0:
        pct = round((g_counts["MATCH"] + g_counts["CLOSE"]) / g_compared * 100, 1)
        print(f"  Match+Close rate: {_bold(f'{pct}%')} (of {g_compared} compared)")

    # Per-variable matrix
    header = f"\n  {'Variable':<28} | {'MATCH':^7} | {'CLOSE':^7} | {'MISMATCH':^8} | {'NO_DATA':^7} | {'PASS':^6} | Note"
    print(header)
    print(f"  {'-' * 28}-+-{'-' * 7}-+-{'-' * 7}-+-{'-' * 8}-+-{'-' * 7}-+-{'-' * 6}-+------")

    # Sort by most mismatches first
    sorted_vars = sorted(
        var_stats.keys(),
        key=lambda v: (-var_stats[v].get("MISMATCH", 0), -var_stats[v].get("NOT_EXTRACTED", 0), v),
    )

    n_proj = len(all_results)
    for var_name in sorted_vars:
        stats = var_stats[var_name]
        m = stats.get("MATCH", 0)
        c = stats.get("CLOSE", 0)
        x = stats.get("MISMATCH", 0)
        nd = stats.get("NOT_EXTRACTED", 0)
        p = stats.get("PASS", 0)

        # Note: quick diagnosis
        note = ""
        if x == n_proj:
            note = "ALL wrong"
        elif nd + p == n_proj:
            note = "never extracted" if nd == n_proj else "no source"
        elif m + c == n_proj:
            note = _green("OK")
        elif m + c + p == n_proj:
            note = _green("OK (some pass)")
        elif x > 0 and nd > 0:
            note = f"{x} wrong, {nd} missing"

        m_str = _green(str(m)) if m else _dim("-")
        c_str = _yellow(str(c)) if c else _dim("-")
        x_str = _red(str(x)) if x else _dim("-")
        nd_str = _dim(str(nd)) if nd else _dim("-")
        p_str = _blue(str(p)) if p else _dim("-")

        print(f"  {var_name:<28} | {m_str:^7} | {c_str:^7} | {x_str:^8} | {nd_str:^7} | {p_str:^6} | {note}")

    # Classification summary (only with --classify)
    if classify:
        class_counts: dict[str, list[str]] = defaultdict(list)
        for project_name, results in all_results.items():
            short_proj = project_name.split()[0]  # e.g. "4001612"
            for concept_id, r in results.items():
                cls = r.get('classification')
                if cls:
                    class_counts[cls].append(f"{concept_id}({short_proj})")

        print(f"\n{'=' * 80}")
        print(f"  MISMATCH CLASSIFICATION")
        print(f"{'=' * 80}")

        _CLS_COLORS = {
            "PRIORITY": _green,
            "FORMAT": _yellow,
            "CALC": _cyan,
            "EXTRACTION": _red,
            "NARRATIVE": _dim,
        }
        _CLS_DESC = {
            "PRIORITY": "Correct value exists as alternative signal",
            "FORMAT": "Adjacent/format-dependent variable",
            "CALC": "Geotech calculation (qa/settlement/k30)",
            "EXTRACTION": "No correct signal found",
            "NARRATIVE": "Narrative/description text",
        }

        for cls in ["PRIORITY", "FORMAT", "CALC", "EXTRACTION", "NARRATIVE"]:
            items = class_counts.get(cls, [])
            if not items:
                continue
            color_fn = _CLS_COLORS.get(cls, str)
            desc = _CLS_DESC.get(cls, "")
            print(f"\n  {color_fn(f'{cls:<12}')} ({len(items)}) -- {desc}")
            for item in sorted(items):
                print(f"    - {item}")


_TIER_WEIGHT = {"A": 3, "B": 2, "C": 1}


def _print_easy_wins(diag_results: list[ProjectDiagResult]) -> None:
    """Print Tier-A MISMATCHes where the correct value exists as an alt signal.

    These are actionable: the right answer is already in the signal pool, but
    lost the priority competition. Fixing them is a tuning task, not an
    extraction task.
    """
    rows: list[tuple[str, str, str, str, str]] = []
    for diag in diag_results:
        short_proj = diag.project_path.name.split()[0]
        signals_by_concept: dict[str, list] = defaultdict(list)
        if diag.auto_result and diag.auto_result.mining_result:
            for sig in diag.auto_result.mining_result.signals:
                key = sig.concept_id or sig.maps_to
                if key:
                    signals_by_concept[key].append(sig)
            for key in signals_by_concept:
                signals_by_concept[key].sort(key=lambda s: (s.priority, -s.confidence))
        mining_alts = diag.auto_result.mining_alternatives if diag.auto_result else {}

        for concept_id, r in diag.results.items():
            if r.get('status') != 'MISMATCH':
                continue
            if r.get('classification') != 'PRIORITY':
                continue
            tier = VARIABLE_TIER.get(concept_id, VARIABLE_TIER.get(r.get('eva_name', ''), 'A'))
            if tier != 'A':
                continue
            _, alt_desc = _check_correct_exists(
                concept_id, r['eva_name'], r['eva_value'],
                signals_by_concept, mining_alts,
            )
            winning_src = (r.get('pipe_source') or '?')[:40]
            rows.append((concept_id, short_proj, winning_src, alt_desc, tier))

    print(f"\n{'=' * 100}")
    print(f"  EASY WINS  --  Tier-A MISMATCHes where correct value exists as alt ({len(rows)} total)")
    print(f"{'=' * 100}")
    if not rows:
        print(f"  {_dim('(none -- no Tier-A PRIORITY classifications across the run)')}")
        return

    print(f"  {'Concept':<28} | {'Project':<10} | {'Winning source':<40} | {'Correct alternative':<35} | T")
    print(f"  {'-' * 28}-+-{'-' * 10}-+-{'-' * 40}-+-{'-' * 35}-+--")
    for concept_id, proj, winning_src, alt_desc, tier in sorted(rows):
        print(f"  {concept_id:<28} | {proj:<10} | {winning_src:<40} | {alt_desc[:35]:<35} | {tier}")


def _print_leverage(diag_results: list[ProjectDiagResult]) -> None:
    """Rank MISMATCH variables by impact: count_of_projects * tier_weight.

    Goal: surface the variables where one fix lifts many projects, vs. the
    long tail of single-project bugs.
    """
    var_proj_count: dict[str, set] = defaultdict(set)
    var_tier: dict[str, str] = {}
    for diag in diag_results:
        short_proj = diag.project_path.name.split()[0]
        for concept_id, r in diag.results.items():
            if r.get('status') != 'MISMATCH':
                continue
            tier = VARIABLE_TIER.get(concept_id, VARIABLE_TIER.get(r.get('eva_name', ''), 'A'))
            var_proj_count[concept_id].add(short_proj)
            var_tier[concept_id] = tier

    ranked: list[tuple[str, int, int, str]] = []
    for concept_id, projects in var_proj_count.items():
        tier = var_tier.get(concept_id, 'A')
        weight = _TIER_WEIGHT.get(tier, 1)
        score = len(projects) * weight
        ranked.append((concept_id, score, len(projects), tier))
    ranked.sort(key=lambda x: (-x[1], -x[2], x[0]))

    print(f"\n{'=' * 80}")
    print(f"  LEVERAGE RANKING  --  top MISMATCH variables by (projects x tier_weight)")
    print(f"{'=' * 80}")
    if not ranked:
        print(f"  {_dim('(no MISMATCHes across the run)')}")
        return
    print(f"  {'Rank':<5} | {'Concept':<28} | {'Score':<6} | {'Projects':<9} | {'Tier'}")
    print(f"  {'-' * 5}-+-{'-' * 28}-+-{'-' * 6}-+-{'-' * 9}-+------")
    for i, (concept_id, score, n_projects, tier) in enumerate(ranked[:15], 1):
        print(f"  {i:<5} | {concept_id:<28} | {score:<6} | {n_projects:<9} | {tier}")


# ---------------------------------------------------------------------------
# NE trace
# ---------------------------------------------------------------------------

_NE_REASON_ORDER = [
    'schema_missing',
    'no_extractor',
    'no_source_file',
    'file_had_no_match',
    'extracted_but_filtered',
    'extracted_low_confidence',
]

_NE_REASON_TITLE = {
    'schema_missing':
        'concept not declared in schemas/concepts/report_variables.yaml',
    'no_extractor':
        'concept exists but only user/computed sources allowed',
    'no_source_file':
        'expected source file (e.g. GTL lab report) not present in project',
    'file_had_no_match':
        'file present, extractor ran, no match',
    'extracted_but_filtered':
        'signals emitted but lost in competition',
    'extracted_low_confidence':
        'extracted below confidence threshold',
}


def _build_ne_trace(
    diag_results: list[ProjectDiagResult],
) -> list[dict]:
    """Build the cross-project NE-trace rows. One row per NE variable.

    Reuses the already-computed per-project results — no pipeline re-run.
    """
    schema = _load_concept_schema()

    # Gather, per prefill_key, the list of (project_name, result_dict).
    by_var: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    project_ctx: dict[str, dict] = {}  # project_name → {fm_roles, concept_sources, signals_by_concept}

    for diag in diag_results:
        pname = diag.project_path.name
        # Build signal count map from auto_result (NE signals usually 0, but
        # some pipelines emit signals that get filtered out — track those).
        signals_by_concept: dict[str, int] = defaultdict(int)
        ar = diag.auto_result
        if ar is not None and getattr(ar, 'mining_result', None) is not None:
            for sig in ar.mining_result.signals:
                key = getattr(sig, 'concept_id', None) or getattr(sig, 'maps_to', None)
                if key:
                    signals_by_concept[key] += 1
        project_ctx[pname] = {
            'fm_roles': _load_file_mapping_roles(diag.project_path),
            'concept_sources': _load_concept_sources(diag.project_path),
            'signals_by_concept': signals_by_concept,
            'deep_folder_files': _load_deep_folder_files(diag.project_path),
        }
        for prefill_key, r in diag.results.items():
            if r.get('status') != 'NOT_EXTRACTED':
                continue
            by_var[prefill_key].append((pname, r))

    rows: list[dict] = []
    for prefill_key, occurrences in by_var.items():
        concept_id = PREFILL_TO_CONCEPT.get(prefill_key, prefill_key)
        schema_entry = schema.get(concept_id)
        in_schema = schema_entry is not None
        schema_priority = (
            list(schema_entry.get('source_priority', {}).keys())
            if schema_entry else []
        )

        # HITL hint
        try:
            from web.expected_sources import expected_source_for
            hint = expected_source_for(concept_id)
        except Exception:
            hint = None
        hitl_hint = (
            {'group_label': hint[0], 'role_hints': list(hint[1])}
            if hint else None
        )

        # Tier + sample eva value from first occurrence
        first_r = occurrences[0][1]
        eva_name = first_r.get('eva_name') or concept_id
        tier = VARIABLE_TIER.get(prefill_key, VARIABLE_TIER.get(eva_name, 'A'))
        eva_sample = ''
        for _, r in occurrences:
            v = r.get('eva_value')
            if v is not None and str(v).strip():
                eva_sample = str(v).strip()
                break

        # Per-project details
        per_project: list[dict] = []
        reasons_seen: list[str] = []
        for pname, r in occurrences:
            ctx = project_ctx.get(pname, {})
            fm_roles: set[str] = ctx.get('fm_roles', set())
            cs_map: dict = ctx.get('concept_sources', {})
            sig_count_map: dict = ctx.get('signals_by_concept', {})
            signals_count = int(sig_count_map.get(concept_id, 0))
            reason, fix, expected_roles = _classify_ne_reason(
                concept_id, schema, fm_roles, cs_map, signals_count,
            )
            reasons_seen.append(reason)
            per_project.append({
                'project': pname,
                'expected_files_present': any(
                    role in fm_roles for role in expected_roles
                ) if expected_roles else None,
                'expected_role': expected_roles or None,
                'concept_scout_found': len(cs_map.get(concept_id, []) or []),
                'signals_produced': signals_count,
                'missing_reason': reason,
            })

        # Aggregate reason: pick the EARLIEST in _NE_REASON_ORDER that appears.
        aggregate_reason = None
        for candidate in _NE_REASON_ORDER:
            if candidate in reasons_seen:
                aggregate_reason = candidate
                break
        if aggregate_reason is None:
            aggregate_reason = reasons_seen[0] if reasons_seen else 'file_had_no_match'

        # Pick suggested_fix from a project that produced the aggregate reason.
        suggested_fix = ''
        for pname, _r in occurrences:
            ctx = project_ctx.get(pname, {})
            sig_count = int(ctx.get('signals_by_concept', {}).get(concept_id, 0))
            reason_p, fix_p, _roles_p = _classify_ne_reason(
                concept_id, schema,
                ctx.get('fm_roles', set()),
                ctx.get('concept_sources', {}),
                sig_count,
            )
            if reason_p == aggregate_reason:
                suggested_fix = fix_p
                break
        if not suggested_fix:
            # Fallback (shouldn't happen)
            suggested_fix = _NE_REASON_TITLE.get(aggregate_reason, '')

        # Annotate no_source_file rows with deep-folder hints.
        # Prefer specific role_candidate pointers when available; otherwise
        # fall back to the count of genuinely unclassified deep files.
        if aggregate_reason == 'no_source_file':
            expected_roles: list[str] = []
            if occurrences:
                first_pp = per_project[0] if per_project else {}
                expected_roles = list(first_pp.get('expected_role') or [])

            candidate_hits: list[tuple[str, str, str]] = []  # (project, path, role)
            total_unclass = 0
            for pname, _r in occurrences:
                dff = project_ctx.get(pname, {}).get('deep_folder_files', {}) or {}
                total_unclass += _count_unclassified_deep_files(dff)
                if expected_roles:
                    for rel_path, entry in dff.items():
                        cand = entry.get('role_candidate')
                        if cand and cand in expected_roles:
                            candidate_hits.append((pname, rel_path, cand))

            if candidate_hits:
                short_proj = candidate_hits[0][0].split()[0]
                short_path = Path(candidate_hits[0][1]).name
                extra = f" (+{len(candidate_hits) - 1} more)" if len(candidate_hits) > 1 else ""
                suggested_fix = (
                    f"{suggested_fix} — role_candidate found in deep folder: "
                    f"{short_proj}:{short_path}{extra}"
                )
            elif total_unclass > 0:
                role_hint = f" [{expected_roles[0]}]" if expected_roles else ''
                suggested_fix = (
                    f"{suggested_fix} — "
                    f"{total_unclass} unclassified deep-folder file(s){role_hint} "
                    f"might contain the missing source"
                )

        rows.append({
            'var': prefill_key,
            'concept_id': concept_id,
            'in_schema': in_schema,
            'tier': tier,
            'eva_value_sample': eva_sample,
            'projects': [p for p, _ in occurrences],
            'expected_sources': {
                'schema_priority': schema_priority,
                'hitl_hint': hitl_hint,
            },
            'per_project': per_project,
            'missing_reason': aggregate_reason,
            'suggested_fix': suggested_fix,
        })

    rows.sort(key=lambda row: (
        _NE_REASON_ORDER.index(row['missing_reason'])
        if row['missing_reason'] in _NE_REASON_ORDER else 99,
        row['var'],
    ))
    return rows


def _format_projects_list(projects: list[str]) -> str:
    """Return 'N projects (First, Second +K more)' short form."""
    n = len(projects)
    short = [p.split()[0] for p in projects]
    if n == 1:
        return f"1 project ({short[0]})"
    if n <= 2:
        return f"{n} projects ({', '.join(short)})"
    return f"{n} projects ({short[0]}, {short[1]} +{n - 2} more)"


def _print_ne_trace(rows: list[dict]) -> None:
    """Print the NE-trace section grouped by missing_reason."""
    total_vars = len(rows)
    total_occ = sum(len(row['projects']) for row in rows)
    print(f"\n{'=' * 80}")
    print(f"  === NOT_EXTRACTED TRACE — {total_vars} variables, "
          f"{total_occ} occurrences ===")
    print(f"{'=' * 80}")

    if not rows:
        print(f"  {_dim('(no NOT_EXTRACTED variables across the run)')}")
        return

    by_reason: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_reason[row['missing_reason']].append(row)

    for reason in _NE_REASON_ORDER:
        group = by_reason.get(reason)
        if not group:
            continue
        title = _NE_REASON_TITLE.get(reason, reason)
        print(f"\n[ {_bold(reason)} ] — {title} ({len(group)} vars)")
        for row in group:
            proj_str = _format_projects_list(row['projects'])
            sample = _truncate(row['eva_value_sample'] or '---', 50)
            sample_str = f"eva sample: {sample!r}" if row['eva_value_sample'] else "eva sample: ---"
            print(
                f"  {row['var']:<32}  {proj_str:<32}  tier {row['tier']}   {sample_str}"
            )
            print(f"    {_cyan('suggested fix:')} {row['suggested_fix']}")


def _print_unclassified_deep_files_report(
    diag_results: list[ProjectDiagResult],
) -> None:
    """Print a project-by-project report of deep-folder files never role-classified."""
    per_project: list[tuple[str, int, list[str]]] = []
    total_files = 0
    for diag in diag_results:
        pname = diag.project_path.name
        dff = _load_deep_folder_files(diag.project_path)
        if not dff:
            continue
        unclassified: list[str] = []
        for rel_path, info in dff.items():
            if info.get('classifier_used') == 'unclassified':
                suffix = Path(rel_path).suffix.lower() or '(no-ext)'
                unclassified.append(suffix)
        if unclassified:
            per_project.append((pname, len(unclassified), unclassified))
            total_files += len(unclassified)

    if not per_project:
        return

    n_projects = len(per_project)
    print(f"\n[ {_bold('unclassified_deep_files_report')} ] — "
          f"deep-folder files saved but never role-classified "
          f"({total_files} files across {n_projects} projects)")
    for pname, count, exts in per_project:
        short_name = pname.split()[0] if ' ' in pname else pname
        ext_summary = ', '.join(sorted(set(exts))[:5])
        print(
            f"  Project {short_name:<12} {count} unclassified ({ext_summary}) — "
            f"possible architect_plan / dpsh_sheet / sondeig_sheet / lab_cover candidates"
        )


def main() -> None:
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Full pipeline diagnostic: compare ALL pipeline values vs Eva",
    )
    parser.add_argument(
        "--project", type=str, default=None,
        help="Filter by expedient number (e.g. 4001612)",
    )
    parser.add_argument(
        "--concept", type=str, default=None,
        help="Filter to a single concept (substring match)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Show all variables including MATCH/CLOSE (default: mismatches only)",
    )
    parser.add_argument(
        "--tolerance", type=float, default=5.0,
        help="Numeric tolerance %% (default: 5)",
    )
    parser.add_argument(
        "--classify", action="store_true",
        help="Show MISMATCH classification summary at end",
    )
    parser.add_argument(
        "--components", action="store_true",
        help="Show per-component accuracy scorecard",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save JSON snapshots to docs/diagnostics/",
    )
    parser.add_argument(
        "--deep", action="store_true",
        help="Deep trace mode for a variable (requires --concept)",
    )
    parser.add_argument(
        "--diff", nargs=2, metavar="SNAPSHOT",
        help="Compare two snapshot JSON files",
    )
    parser.add_argument(
        "--llm-judge",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="LLM judge for semantic comparison (default: ON; --no-llm-judge to disable)",
    )
    parser.add_argument(
        "--easy-wins", action="store_true",
        help="Show actionable easy-win MISMATCHes (Tier A + correct alt exists)",
    )
    parser.add_argument(
        "--leverage", action="store_true",
        help="Rank MISMATCH variables by impact (count_of_projects * tier_weight)",
    )
    parser.add_argument(
        "--ne-trace", action="store_true",
        help="Explain each NOT_EXTRACTED variable: missing_reason + suggested fix",
    )
    args = parser.parse_args()

    # --diff mode: compare two snapshots and exit
    if args.diff:
        _diff_snapshots(Path(args.diff[0]), Path(args.diff[1]))
        return

    # Validate --deep requires --concept
    if args.deep and not args.concept:
        print("Error: --deep requires --concept")
        sys.exit(1)

    projects = PROJECTS
    if args.project:
        projects = [p for p in projects if p.startswith(args.project)]

    if not projects:
        print(f"No projects match filter '{args.project}'")
        sys.exit(1)

    # LLM judge setup
    llm_client = None
    if args.llm_judge:
        _load_env()
        from automation.llm_client import get_anthropic_client
        llm_client = get_anthropic_client()
        _load_llm_cache()

    print(_bold("Full Pipeline Diagnostic: Eva vs Pipeline"))
    print(f"Runs: auto_extract + vision + geotech calculations")
    print(f"Tolerance: {args.tolerance}%")
    if llm_client is not None:
        print(f"LLM judge: ON")
    else:
        print(f"LLM judge: OFF (semantic comparison disabled)")
    if args.concept:
        print(f"Concept filter: {args.concept}")
    print()

    all_results: dict[str, dict[str, dict]] = {}
    all_diag_results: list[ProjectDiagResult] = []
    snapshots: list[dict] = []
    output_dir = _PROJECT_ROOT / "docs" / "diagnostics"

    for project_name in projects:
        diag = process_project(
            project_name,
            concept_filter=args.concept,
            show_all=args.all or args.deep,
            tolerance=args.tolerance,
            llm_client=llm_client,
        )
        if diag is None:
            continue

        all_results[project_name] = diag.results
        all_diag_results.append(diag)

        # --deep: deep trace for the matched concept
        if args.deep and args.concept:
            matched = [cid for cid in diag.results if args.concept in cid]
            if matched:
                for cid in matched:
                    _deep_trace_variable(
                        cid, diag.results[cid], diag.auto_result,
                        diag.eva_vars, diag.values, diag.sources, diag.merged,
                        llm_client,
                    )
            else:
                print(f"\n  No variable matching '{args.concept}' found for deep trace")

        # --components: print scorecard
        comp_summary: dict[str, dict] = {}
        if args.components:
            comp_summary = _print_component_scorecard(diag.results)
        elif args.save:
            # Need component_summary for snapshot even without printing
            comp_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"match": 0, "close": 0, "mismatch": 0, "not_extracted": 0, "pass": 0})
            for r in diag.results.values():
                comp = r.get('component', 'unknown')
                status = r['status'].lower()
                if status in comp_stats[comp]:
                    comp_stats[comp][status] += 1
            for comp, s in comp_stats.items():
                produced = s['match'] + s['close'] + s['mismatch']
                accuracy = round((s['match'] + s['close']) / produced * 100, 1) if produced > 0 else 0.0
                comp_summary[comp] = {
                    "produced": produced, "match": s['match'], "close": s['close'],
                    "mismatch": s['mismatch'], "not_extracted": s['not_extracted'],
                    "pass": s['pass'], "accuracy_pct": accuracy,
                }

        # --save: build and save snapshot
        if args.save:
            val_dir = diag.project_path / "validation"
            vision_status = {
                'planol': (val_dir / 'planol_extracted.json').exists(),
                'sondeig': (val_dir / 'sondeig_extracted.json').exists(),
                'dpsh': (val_dir / 'dpsh_extracted.json').exists(),
            }
            metadata = _collect_metadata(
                diag.auto_result, diag.project_path, args.tolerance,
                vision_status, diag.duration, diag.merged,
                judge_enabled=(llm_client is not None),
            )
            snapshot = _build_snapshot(
                project_name, diag.results, diag.auto_result,
                diag.project_path, metadata, comp_summary, diag.merged,
                diag.values,
            )
            snap_path = _save_snapshot(snapshot, output_dir)
            snapshots.append(snapshot)
            print(f"\n  Snapshot saved: {snap_path}")

    if len(all_results) > 1:
        print_cross_project_summary(all_results, classify=args.classify)

    if args.easy_wins:
        _print_easy_wins(all_diag_results)
    if args.leverage:
        _print_leverage(all_diag_results)

    # --ne-trace: build global trace (also injected into snapshots)
    ne_rows: list[dict] = []
    if args.ne_trace or args.save:
        ne_rows = _build_ne_trace(all_diag_results)
    if args.ne_trace:
        _print_ne_trace(ne_rows)
        _print_unclassified_deep_files_report(all_diag_results)

    # Inject per-project ne_trace rows into already-built snapshots
    if args.save and ne_rows:
        ne_by_project: dict[str, list[dict]] = defaultdict(list)
        for row in ne_rows:
            for pp in row.get('per_project', []):
                pname = pp.get('project')
                if not pname:
                    continue
                ne_by_project[pname].append({
                    'var': row['var'],
                    'concept_id': row['concept_id'],
                    'in_schema': row['in_schema'],
                    'tier': row['tier'],
                    'eva_value_sample': row['eva_value_sample'],
                    'expected_sources': row['expected_sources'],
                    'expected_files_present': pp.get('expected_files_present'),
                    'expected_role': pp.get('expected_role'),
                    'concept_scout_found': pp.get('concept_scout_found', 0),
                    'signals_produced': pp.get('signals_produced', 0),
                    'missing_reason': pp.get('missing_reason'),
                    'suggested_fix': row['suggested_fix'],
                })
        for snap in snapshots:
            pname = snap.get('metadata', {}).get('project')
            snap['ne_trace'] = ne_by_project.get(pname, [])
            # Rewrite snapshot file with ne_trace added
            snap_path = _save_snapshot(snap, output_dir)

    # Save cross-project summary
    if args.save and len(snapshots) > 1:
        cross = _build_cross_summary(snapshots)
        if ne_rows:
            cross['global_ne_trace'] = ne_rows
        date = time.strftime("%Y-%m-%d")
        run_id = cross.get("metadata", {}).get("run_id", "000000")
        cross_path = output_dir / f"{date}_CROSS_{run_id}.json"
        cross_path.write_text(
            json.dumps(cross, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"\n  Cross-project summary saved: {cross_path}")

    # Persist LLM judge cache
    if llm_client is not None:
        _save_llm_cache()


if __name__ == "__main__":
    main()
