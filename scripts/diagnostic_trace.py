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
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from compare_benchmarks import TEXT_NORMALIZERS, compare_numeric, compare_text, parse_numeric

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
                  tolerance: float = 5.0) -> str:
    """Compare one value pair. Returns MATCH, CLOSE, or MISMATCH."""
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

    normalizer = TEXT_NORMALIZERS.get(var_name)
    if normalizer:
        return compare_text(normalizer(eva_str), normalizer(cand_str))
    return compare_text(eva_str, cand_str)


# ---------------------------------------------------------------------------
# Full pipeline execution
# ---------------------------------------------------------------------------

def run_full_pipeline(project_name: str) -> tuple[dict[str, Any], dict[str, str], Any]:
    """Run complete pipeline via get_prefills(). Returns (values, sources, auto_result).

    values: {field_name: value}
    sources: {field_name: source_string}
    auto_result: AutoExtractionResult (for signal trace access)
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
    return values, sources, auto_result


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
) -> dict[str, dict] | None:
    """Process one project. Returns {concept_id: {status, eva, pipeline, source}} or None."""
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
    values, sources, auto_result = run_full_pipeline(project_name)
    print(f"({len(values)} values)")

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
            status = _values_match(eva_value, pipe_value, eva_name, tolerance)

        results[prefill_key] = {
            'eva_name': eva_name,
            'eva_value': eva_value,
            'pipe_value': pipe_value,
            'pipe_source': pipe_source,
            'status': status,
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

    return results


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
    args = parser.parse_args()

    projects = PROJECTS
    if args.project:
        projects = [p for p in projects if p.startswith(args.project)]

    if not projects:
        print(f"No projects match filter '{args.project}'")
        sys.exit(1)

    print(_bold("Full Pipeline Diagnostic: Eva vs Pipeline"))
    print(f"Runs: auto_extract + vision + geotech calculations")
    print(f"Tolerance: {args.tolerance}%")
    if args.concept:
        print(f"Concept filter: {args.concept}")
    print()

    all_results: dict[str, dict[str, dict]] = {}

    for project_name in projects:
        results = process_project(
            project_name,
            concept_filter=args.concept,
            show_all=args.all,
            tolerance=args.tolerance,
        )
        if results is not None:
            all_results[project_name] = results

    if len(all_results) > 1:
        print_cross_project_summary(all_results, classify=args.classify)


if __name__ == "__main__":
    main()
