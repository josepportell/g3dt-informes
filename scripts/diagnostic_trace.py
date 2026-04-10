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
    (re.compile(r'Terzaghi|Schmertmann|Winkler|2\.5.*Nb|^computed$|CTE|NCSE|RD 470|soil_type=', re.IGNORECASE), 'computed'),
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
        return f"Nb={nb}, B={b}, Df={df}, c={coh}, phi={phi}, cap={cap}"
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
        if key.startswith('_'):
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
    n_total = len(results)
    n_compared = n_m + n_c + n_x
    print(
        f"  {_green(f'{n_m} match')}  "
        f"{_yellow(f'{n_c} close')}  "
        f"{_red(f'{n_x} mismatch')}  "
        f"{_dim(f'{n_nd} not_extracted')}  "
        f"/ {n_total} vars"
    )
    if n_compared > 0:
        pct_ok = round((n_m + n_c) / n_compared * 100, 1)
        print(f"  Match+Close rate: {_bold(f'{pct_ok}%')} (of {n_compared} compared)")

    # Table header
    print(f"\n  {'Variable':<28} {'Eva':<28} {'Pipeline':<28} {'Source':<25} {'Status'}")
    print(f"  {'-' * 28} {'-' * 28} {'-' * 28} {'-' * 25} {'-' * 12}")

    # Sort: MISMATCH first, then CLOSE, then NOT_EXTRACTED, then MATCH
    _STATUS_ORDER = {"MISMATCH": 0, "CLOSE": 1, "NOT_EXTRACTED": 2, "MATCH": 3}

    for concept_id in sorted(results, key=lambda c: (_STATUS_ORDER.get(results[c]['status'], 9), c)):
        r = results[concept_id]
        status = r['status']

        # In default mode, only show MISMATCH and NOT_EXTRACTED
        if not show_all and status in ("MATCH", "CLOSE"):
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
    for status_name in ["MATCH", "CLOSE", "MISMATCH", "NOT_EXTRACTED"]:
        count = counts.get(status_name, 0)
        if count > 0:
            if status_name == "MATCH":
                print(f"    {_green(f'{status_name:<16}')} {count:>3}")
            elif status_name == "CLOSE":
                print(f"    {_yellow(f'{status_name:<16}')} {count:>3}")
            elif status_name == "MISMATCH":
                print(f"    {_red(f'{status_name:<16}')} {count:>3}")
            else:
                print(f"    {_dim(f'{status_name:<16}')} {count:>3}")

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
    comp_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"match": 0, "close": 0, "mismatch": 0, "not_extracted": 0})

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
    n_total = sum(counts.values())
    n_compared = n_m + n_c + n_x
    match_close_pct = round((n_m + n_c) / n_compared * 100, 1) if n_compared > 0 else 0.0

    # Tier summary
    tier_summary: dict[str, dict[str, int]] = {}
    for tier in ("A", "B", "C"):
        tier_summary[tier] = {"total": 0, "match": 0, "close": 0, "mismatch": 0, "not_extracted": 0}
    for concept_id, r in results.items():
        tier = VARIABLE_TIER.get(concept_id, VARIABLE_TIER.get(r.get('eva_name', ''), 'A'))
        status_key = r['status'].lower()
        if tier not in tier_summary:
            tier_summary[tier] = {"total": 0, "match": 0, "close": 0, "mismatch": 0, "not_extracted": 0}
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

    return {
        "schema_version": "1.0",
        "metadata": metadata,
        "summary": {
            "total_vars": n_total,
            "match": n_m,
            "close": n_c,
            "mismatch": n_x,
            "not_extracted": n_nd,
            "match_close_pct": match_close_pct,
        },
        "tier_summary": tier_summary,
        "component_summary": component_summary,
        "variables": variables,
        "format_learning": format_learning,
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
    global_summary: dict[str, int] = {"total_vars": 0, "match": 0, "close": 0, "mismatch": 0, "not_extracted": 0}
    global_tier: dict[str, dict[str, int]] = {}
    global_comp: dict[str, dict[str, float]] = {}
    cross_vars: dict[str, dict[str, str]] = {}  # var -> {project: status}
    classification_summary: dict[str, list[str]] = defaultdict(list)

    for snap in snapshots:
        proj = snap.get("metadata", {}).get("project", "?")
        summ = snap.get("summary", {})
        for key in ("total_vars", "match", "close", "mismatch", "not_extracted"):
            global_summary[key] += summ.get(key, 0)

        # Tier aggregation
        for tier, tier_data in snap.get("tier_summary", {}).items():
            if tier not in global_tier:
                global_tier[tier] = {"total": 0, "match": 0, "close": 0, "mismatch": 0, "not_extracted": 0}
            for k in ("total", "match", "close", "mismatch", "not_extracted"):
                global_tier[tier][k] += tier_data.get(k, 0)

        # Component aggregation
        for comp, comp_data in snap.get("component_summary", {}).items():
            if comp not in global_comp:
                global_comp[comp] = {"produced": 0, "match": 0, "close": 0, "mismatch": 0, "not_extracted": 0}
            for k in ("produced", "match", "close", "mismatch", "not_extracted"):
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

    return {
        "schema_version": "1.0",
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

    vars_a = snap_a.get("variables", {})
    vars_b = snap_b.get("variables", {})
    all_vars = sorted(set(vars_a.keys()) | set(vars_b.keys()))

    improvements = 0
    regressions = 0
    unchanged = 0

    _STATUS_RANK = {"MATCH": 0, "CLOSE": 1, "MISMATCH": 2, "NOT_EXTRACTED": 3}

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
    print(
        f"  Total: {g_total} var-comparisons  |  "
        f"{_green(f'{gm} match')}  "
        f"{_yellow(f'{gc} close')}  "
        f"{_red(f'{gx} mismatch')}  "
        f"{_dim(f'{gnd} not_extracted')}"
    )
    if g_compared > 0:
        pct = round((g_counts["MATCH"] + g_counts["CLOSE"]) / g_compared * 100, 1)
        print(f"  Match+Close rate: {_bold(f'{pct}%')} (of {g_compared} compared)")

    # Per-variable matrix
    header = f"\n  {'Variable':<28} | {'MATCH':^7} | {'CLOSE':^7} | {'MISMATCH':^8} | {'NO_DATA':^7} | Note"
    print(header)
    print(f"  {'-' * 28}-+-{'-' * 7}-+-{'-' * 7}-+-{'-' * 8}-+-{'-' * 7}-+------")

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

        # Note: quick diagnosis
        note = ""
        if x == n_proj:
            note = "ALL wrong"
        elif nd == n_proj:
            note = "never extracted"
        elif m + c == n_proj:
            note = _green("OK")
        elif x > 0 and nd > 0:
            note = f"{x} wrong, {nd} missing"

        m_str = _green(str(m)) if m else _dim("-")
        c_str = _yellow(str(c)) if c else _dim("-")
        x_str = _red(str(x)) if x else _dim("-")
        nd_str = _dim(str(nd)) if nd else _dim("-")

        print(f"  {var_name:<28} | {m_str:^7} | {c_str:^7} | {x_str:^8} | {nd_str:^7} | {note}")

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
        "--llm-judge", action="store_true",
        help="Use LLM judge (Claude Haiku) for semantic text comparison",
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
        import anthropic
        llm_client = anthropic.Anthropic()
        _load_llm_cache()

    print(_bold("Full Pipeline Diagnostic: Eva vs Pipeline"))
    print(f"Runs: auto_extract + vision + geotech calculations")
    print(f"Tolerance: {args.tolerance}%")
    if llm_client is not None:
        print(f"LLM judge: ON")
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
            comp_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"match": 0, "close": 0, "mismatch": 0, "not_extracted": 0})
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
                    "accuracy_pct": accuracy,
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
                vision_status, diag.duration,
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

    # Save cross-project summary
    if args.save and len(snapshots) > 1:
        cross = _build_cross_summary(snapshots)
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
