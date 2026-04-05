#!/usr/bin/env python3
"""Compare Eva's reference values against the FULL pipeline (auto_extract).

For each variable:
1. What value did Eva use in her real report?
2. What value does our pipeline produce? From which source?
3. Do they match?
4. If NOT: which pipeline CANDIDATE matches Eva's value? (reveals source preference)

Usage:
    python scripts/compare_eva_vs_pipeline.py
    python scripts/compare_eva_vs_pipeline.py --project 4001612
    python scripts/compare_eva_vs_pipeline.py --verbose
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Import comparison helpers from sibling script
sys.path.insert(0, str(Path(__file__).parent))
from compare_benchmarks import (
    TEXT_NORMALIZERS,
    compare_numeric,
    compare_text,
    parse_numeric,
)

# Import pipeline
sys.path.insert(0, str(Path(__file__).parent.parent))

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

# Eva template variable name -> pipeline prefill key
EVA_TO_PREFILL = {
    "architect_name_upper": "architect_name",
    "building_type_lower": "building_type",
    "plantes": "num_floors",
    "client": "client_name",
    "adjacent_east_fmt": "adjacent_east",
    "adjacent_south_fmt": "adjacent_south",
    "adjacent_north_fmt": "adjacent_north",
    "adjacent_west_fmt": "adjacent_west",
    "superficie_parcela": "superficie_parcela_m2",
    "superficie_construida": "superficie_construida_m2",
}

# Variables to skip (long narrative text, calculated sections, or not comparable)
SKIP_VARS = {
    # Long narrative (template-generated, not extracted)
    "geo_p", "materials_intro", "conclusions_levels_detected",
    "conclusions_water_statement", "conclusions_aggressivity_statement",
    "csn_radon_text", "radon_zone_description",
    "empentes_paragraph", "estabilitat_paragraph",
    "photo_site_text",
    # Formatted dates (always correct by design)
    "data_signatura_text",
    # Loop table data (compare sub-fields individually instead)
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

def _status_colored(status: str) -> str:
    if status == "MATCH": return _green(status)
    if status == "CLOSE": return _yellow(status)
    if status == "NO_DATA": return _dim(status)
    return _red(status)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

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


def run_full_pipeline(project_path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Run auto_extract (full pipeline), return (prefills, sources).

    prefills: {field_name: value}
    sources: {field_name: source_type}
    """
    from automation.auto_extractor import auto_extract
    result = auto_extract(project_path)

    prefills: dict[str, Any] = {}
    sources: dict[str, str] = {}

    for key, value in result.prefills.items():
        if key.startswith("_"):
            continue
        prefills[key] = value
        sources[key] = result.sources.get(key, "auto")

    return prefills, sources


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def _values_match(eva_value: Any, pipeline_value: Any, var_name: str,
                  tolerance: float = 5.0) -> str:
    """Compare one value pair. Returns MATCH, CLOSE, or MISMATCH."""
    eva_str = str(eva_value).strip()
    pipe_str = str(pipeline_value).strip()

    if not eva_str or not pipe_str:
        return "NO_DATA"

    # Numeric comparison
    if var_name in NUMERIC_VARS:
        eva_num = parse_numeric(eva_str)
        pipe_num = parse_numeric(pipe_str)
        if eva_num is not None and pipe_num is not None:
            _, status = compare_numeric(eva_num, pipe_num, tolerance)
            return status

    # Text comparison with normalizers
    normalizer = TEXT_NORMALIZERS.get(var_name)
    if normalizer:
        return compare_text(normalizer(eva_str), normalizer(pipe_str))
    return compare_text(eva_str, pipe_str)


def compare_project(
    eva_vars: dict[str, Any],
    prefills: dict[str, Any],
    sources: dict[str, str],
    tolerance: float = 5.0,
) -> list[dict[str, Any]]:
    """Compare Eva's values against pipeline prefills."""
    results = []

    for eva_name in sorted(eva_vars.keys()):
        if eva_name in SKIP_VARS:
            continue

        eva_value = eva_vars[eva_name]

        # Map Eva variable name to pipeline prefill key
        prefill_key = EVA_TO_PREFILL.get(eva_name, eva_name)

        pipe_value = prefills.get(prefill_key)
        pipe_source = sources.get(prefill_key, "")

        if pipe_value is None or str(pipe_value).strip() == "":
            results.append({
                "eva_name": eva_name,
                "prefill_key": prefill_key,
                "eva_value": eva_value,
                "pipeline_value": None,
                "pipeline_source": None,
                "status": "NO_DATA",
            })
            continue

        status = _values_match(eva_value, pipe_value, eva_name, tolerance)

        results.append({
            "eva_name": eva_name,
            "prefill_key": prefill_key,
            "eva_value": eva_value,
            "pipeline_value": pipe_value,
            "pipeline_source": pipe_source,
            "status": status,
        })

    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _truncate(s: Any, maxlen: int = 35) -> str:
    s = str(s).replace("\n", " ")
    return s[:maxlen - 2] + ".." if len(s) > maxlen else s


def print_project_table(project_name: str, results: list[dict]) -> None:
    """Print comparison table for one project."""
    counts = defaultdict(int)
    for r in results:
        counts[r["status"]] += 1
    total = len(results)

    print(f"\n{'=' * 90}")
    print(f"  {project_name}")
    n_m, n_c, n_x, n_nd = counts["MATCH"], counts["CLOSE"], counts["MISMATCH"], counts["NO_DATA"]
    print(
        f"  {_green(f'{n_m} match')}  "
        f"{_yellow(f'{n_c} close')}  "
        f"{_red(f'{n_x} mismatch')}  "
        f"{_dim(f'{n_nd} no_data')}  "
        f"/ {total} vars"
    )
    print(f"{'=' * 90}")

    print(
        f"  {'Variable':<28} {'Eva':<30} {'Pipeline':<30} "
        f"{'Source':<20} {'Status'}"
    )
    print(f"  {'-' * 28} {'-' * 30} {'-' * 30} {'-' * 20} {'-' * 9}")

    for r in sorted(results, key=lambda x: (x["status"] != "MISMATCH", x["status"] != "CLOSE", x["eva_name"])):
        eva_str = _truncate(r["eva_value"], 30)
        status = r["status"]
        status_str = _status_colored(f"{status:<9}")

        if status == "NO_DATA":
            print(
                f"  {r['eva_name']:<28} {eva_str:<30} {'--':<30} "
                f"{'--':<20} {status_str}"
            )
        else:
            pipe_str = _truncate(r["pipeline_value"], 30)
            source_str = _truncate(r["pipeline_source"] or "", 20)
            print(
                f"  {r['eva_name']:<28} {eva_str:<30} {pipe_str:<30} "
                f"{source_str:<20} {status_str}"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import logging
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Compare Eva's reference values against full pipeline",
    )
    parser.add_argument(
        "--project", type=str, default=None,
        help="Filter by expedient number (e.g. 4001612)",
    )
    parser.add_argument(
        "--tolerance", type=float, default=5.0,
        help="Numeric tolerance %% for MATCH (default: 5)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show all variables including MATCH and NO_DATA",
    )
    args = parser.parse_args()

    projects = PROJECTS
    if args.project:
        projects = [p for p in projects if p.startswith(args.project)]

    print("Eva vs Full Pipeline Comparison")
    print(f"Tolerance: {args.tolerance}%")
    print(f"Running auto_extract() per project (Python phases, no vision API)...\n")

    all_results: dict[str, list[dict]] = {}
    global_counts: dict[str, int] = defaultdict(int)

    for project_name in projects:
        project_path = REFERENCE_DIR / project_name
        if not project_path.is_dir():
            continue

        eva_vars = load_eva_reference(project_path)
        if not eva_vars:
            print(f"  {project_name}: no eva_reference_values.json, skipping")
            continue

        print(f"  Processing {project_name}...", end=" ", flush=True)
        prefills, sources = run_full_pipeline(project_path)
        print(f"({len(prefills)} prefills)")

        results = compare_project(eva_vars, prefills, sources, args.tolerance)
        if not results:
            continue

        all_results[project_name] = results

        if not args.verbose:
            # Only show MISMATCH and CLOSE
            filtered = [r for r in results if r["status"] in ("MISMATCH", "CLOSE")]
            if filtered:
                print_project_table(project_name, filtered)
            else:
                counts = defaultdict(int)
                for r in results:
                    counts[r["status"]] += 1
                n_match = counts["MATCH"]
                n_nodata = counts["NO_DATA"]
                print(f"  -> {_green(f'{n_match} match')}, "
                      f"{_dim(f'{n_nodata} no_data')} (all good!)")
        else:
            print_project_table(project_name, results)

        for r in results:
            global_counts[r["status"]] += 1

    # Global summary
    total_compared = global_counts["MATCH"] + global_counts["CLOSE"] + global_counts["MISMATCH"]
    total_all = total_compared + global_counts["NO_DATA"]

    print(f"\n{'=' * 90}")
    print("  GLOBAL SUMMARY")
    print(f"{'=' * 90}")
    print(f"  Projects: {len(all_results)}")
    print(f"  Variables: {total_all} total, {total_compared} compared, {global_counts['NO_DATA']} no pipeline data")
    gm, gc, gx = global_counts["MATCH"], global_counts["CLOSE"], global_counts["MISMATCH"]
    print(
        f"  {_green(f'Match: {gm}')}  "
        f"{_yellow(f'Close: {gc}')}  "
        f"{_red(f'Mismatch: {gx}')}"
    )
    if total_compared > 0:
        pct = round(global_counts["MATCH"] / total_compared * 100, 1)
        pct_ok = round((global_counts["MATCH"] + global_counts["CLOSE"]) / total_compared * 100, 1)
        print(f"  Exact match rate: {pct}%")
        print(f"  Match+Close rate: {pct_ok}%")

    # Mismatch analysis
    print(f"\n  {'MISMATCH DETAILS':}")
    mismatch_by_var: dict[str, list] = defaultdict(list)
    for proj, results in all_results.items():
        for r in results:
            if r["status"] == "MISMATCH":
                mismatch_by_var[r["eva_name"]].append({
                    "project": proj.split()[0],
                    "eva": _truncate(r["eva_value"], 25),
                    "pipeline": _truncate(r["pipeline_value"], 25),
                    "source": r.get("pipeline_source", "?"),
                })

    if mismatch_by_var:
        for var_name in sorted(mismatch_by_var):
            entries = mismatch_by_var[var_name]
            print(f"\n  {_red(var_name)} ({len(entries)}/{len(all_results)} projects):")
            for e in entries:
                print(f"    {e['project']}: Eva={e['eva']!r}  Pipeline={e['pipeline']!r}  src={e['source']}")
    else:
        print("  None!")


if __name__ == "__main__":
    main()
