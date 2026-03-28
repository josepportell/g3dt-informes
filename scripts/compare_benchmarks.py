#!/usr/bin/env python3
"""Compare Eva's benchmark values against pipeline values.

Reads benchmark JSONs (Eva's correct values from signed reports) and
validation-latest JSONs (our pipeline readiness data), compares each
variable, and outputs a structured comparison.

Usage:
    python scripts/compare_benchmarks.py
    python scripts/compare_benchmarks.py --tolerance 10
    python scripts/compare_benchmarks.py --project 4001612
    python scripts/compare_benchmarks.py --verbose
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

BENCHMARKS_DIR = _PROJECT_ROOT / "docs" / "benchmarks"
VALIDATION_DIR = _PROJECT_ROOT / "docs" / "validation-latest"

# ---------------------------------------------------------------------------
# Variable classification: type (numeric vs text) and tier (A/B/C)
# ---------------------------------------------------------------------------
#
# Tier A: Auto-extractable — pipeline should get these right. Target ~95%.
# Tier B: Manual/on-site — requires Eva's input or external data (Street View).
# Tier C: Professional judgment — Eva's expertise. Correct unless formula is wrong.
# Excluded: data_signatura_text (correct by design — always today's date).

NUMERIC_KEYS = {
    "geotech_density",
    "geotech_cohesion",
    "geotech_phi",
    "geotech_E",
    "geotech_nb",
    "qa_value",
    "settlement",
    "k30_value",
    "num_dpsh_tests",
    "dpsh_avg_n20",
    "sulfate_value",
    "superficie_construida",
    "superficie_parcela",
    "cota_referencia",
}

TEXT_KEYS = {
    "client",
    "architect_name",
    "architect_company",
    "street_address",
    "municipality",
    "building_type",
    "num_floors",
    "site_condition",
    "data_camp_text",
    "dpsh_test_ids",
    "location_sentence",
    "adjacent_north",
    "adjacent_south",
    "adjacent_east",
    "adjacent_west",
    "site_description",
    "access_description",
    "radon_zone",
    "seismic_ab_text",
}

# Excluded from comparison (correct by design)
EXCLUDED_KEYS = {"data_signatura_text"}

VARIABLE_TIER: dict[str, str] = {
    # Tier A: Auto-extractable
    "municipality": "A", "street_address": "A", "cota_referencia": "A",
    "num_dpsh_tests": "A", "dpsh_test_ids": "A", "dpsh_avg_n20": "A",
    "sulfate_value": "A", "radon_zone": "A", "seismic_ab_text": "A",
    "geotech_density": "A", "geotech_cohesion": "A", "geotech_phi": "A",
    "geotech_nb": "A", "data_camp_text": "A",
    "client": "A", "architect_name": "A", "architect_company": "A",
    "building_type": "A", "num_floors": "A",
    "superficie_construida": "A", "superficie_parcela": "A",
    # Tier B: Manual / on-site observation
    "adjacent_north": "B", "adjacent_south": "B",
    "adjacent_east": "B", "adjacent_west": "B",
    "site_condition": "B", "site_description": "B",
    "access_description": "B", "location_sentence": "B",
    # Tier C: Professional judgment
    "geotech_E": "C", "qa_value": "C", "settlement": "C", "k30_value": "C",
}

# ---------------------------------------------------------------------------
# ANSI colors (only when stdout is a tty)
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty()


def _color(text: str, code: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _green(text: str) -> str:
    return _color(text, "32")


def _yellow(text: str) -> str:
    return _color(text, "33")


def _red(text: str) -> str:
    return _color(text, "31")


def _status_colored(status: str) -> str:
    if status == "MATCH":
        return _green(status)
    if status == "CLOSE":
        return _yellow(status)
    return _red(status)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STRIP_RE = re.compile(r"[°%]|kg/cm[²2]|\bm2\b|\bcm\b|\bmm\b|\bm\b")
_SUM_RE = re.compile(r"^[\d.,]+\+[\d.,+]+$")
_RANGE_RE = re.compile(r"^([\d.,]+)\s*[-–]\s*([\d.,]+)$")

# Roman numeral mapping for radon zone
_ROMAN_TO_ARABIC = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "0": "0"}


def _normalize_radon_zone(s: str) -> str:
    """Normalize radon zone: 'ZONA 1', 'Zona I', '1' → '1'."""
    s = re.sub(r'^zona\s*', '', s.strip(), flags=re.IGNORECASE).strip()
    return _ROMAN_TO_ARABIC.get(s.lower(), s)


def _normalize_seismic_ab(s: str) -> str:
    """Normalize seismic ab: 'AB = 0,04 g' → '0.04', '0,04' → '0.04'."""
    s = s.strip().lower()
    # Strip 'ab' prefix, operators, 'g' suffix
    s = re.sub(r'^ab\s*', '', s)
    s = re.sub(r'^[=<>≤≥]\s*', '', s)
    s = re.sub(r'\s*g\s*$', '', s)
    return s.replace(',', '.').strip()


def _normalize_dpsh_test_ids(s: str) -> str:
    """Normalize DPSH test IDs: strip spaces around commas."""
    return re.sub(r'\s*,\s*', ',', s.strip())


def _normalize_municipality(s: str) -> str:
    """Strip province suffix: 'Castellar del Vallès, Barcelona' → 'Castellar del Vallès'."""
    return re.sub(
        r',\s*(Barcelona|Lleida|Tarragona|Girona|Huesca|Zaragoza|Teruel)\s*$',
        '', s.strip(), flags=re.IGNORECASE,
    )


# Map of variable keys to normalization functions applied before text comparison
TEXT_NORMALIZERS: dict[str, callable] = {
    "radon_zone": _normalize_radon_zone,
    "seismic_ab_text": _normalize_seismic_ab,
    "dpsh_test_ids": _normalize_dpsh_test_ids,
    "municipality": _normalize_municipality,
}


def parse_numeric(s: str) -> float | None:
    """Parse a string value to float, stripping units and formatting."""
    if s is None:
        return None
    text = str(s).strip()
    if not text:
        return None
    # Handle comma as decimal separator (early, before sum check)
    text = text.replace(",", ".")
    # Handle expressions like "297+110" before stripping (+ is meaningful here)
    if _SUM_RE.match(text):
        try:
            return sum(float(p) for p in text.split("+"))
        except ValueError:
            pass
    # Handle refusal notation like "12-R" — take the numeric part
    if "-R" in text.upper():
        text = text.upper().replace("-R", "").strip()
    # Strip common units and leading +
    text = _STRIP_RE.sub("", text).strip().lstrip("+")
    try:
        return float(text)
    except ValueError:
        return None


def classify_benchmark(value: Any) -> tuple[str, Any]:
    """Classify a benchmark value into a comparison type.

    Returns (type, parsed) where type is one of:
    - "threshold_min": value is ">X", parsed = X (float)
    - "refusal": value is "R" (DPSH refusal, Nb>100)
    - "range": value is "X-Y", parsed = (lo, hi)
    - "numeric": normal number, parsed = float
    - "text": fallback, parsed = str
    """
    s = str(value).strip()

    # ">X" — minimum threshold (e.g. ">500", ">350")
    if s.startswith(">"):
        num = parse_numeric(s[1:])
        if num is not None:
            return "threshold_min", num

    # "R" alone — refusal (Nb>100)
    if s.upper() == "R":
        return "refusal", None

    # "X-Y" range (e.g. "1106.30-1106.65") — but NOT "12-R" refusal
    m = _RANGE_RE.match(s)
    if m:
        lo = parse_numeric(m.group(1))
        hi = parse_numeric(m.group(2))
        if lo is not None and hi is not None:
            return "range", (min(lo, hi), max(lo, hi))

    # Normal numeric
    num = parse_numeric(s)
    if num is not None:
        return "numeric", num

    # Fallback: text
    return "text", s


def compare_text(benchmark: str, pipeline: str) -> str:
    """Compare two text values. Returns MATCH, CLOSE, or MISMATCH."""
    a = str(benchmark).strip().lower()
    b = str(pipeline).strip().lower()
    if a == b:
        return "MATCH"
    if a in b or b in a:
        return "CLOSE"
    return "MISMATCH"


def compare_numeric(
    benchmark: float, pipeline: float, tolerance: float,
) -> tuple[float, str]:
    """Compare two numeric values. Returns (deviation_pct, status)."""
    if benchmark == 0:
        if pipeline == 0:
            return 0.0, "MATCH"
        return 100.0, "MISMATCH"
    deviation = (pipeline - benchmark) / abs(benchmark) * 100
    abs_dev = abs(deviation)
    if abs_dev <= tolerance:
        status = "MATCH"
    elif abs_dev <= 15:
        status = "CLOSE"
    else:
        status = "MISMATCH"
    return round(deviation, 1), status


# ---------------------------------------------------------------------------
# Core comparison
# ---------------------------------------------------------------------------

def find_pipeline_json(expedient: str) -> Path | None:
    """Find the validation-latest JSON for an expedient.

    Matches files starting with the expedient number (e.g. "4001612")
    but excludes numbered variants like "4001612 BELL-LLOC2.json".
    Prefers the base name (no trailing digit before .json).
    """
    if not VALIDATION_DIR.is_dir():
        return None
    candidates = []
    for p in VALIDATION_DIR.glob(f"{expedient}*.json"):
        if p.name.startswith("_"):
            continue
        candidates.append(p)
    if not candidates:
        return None
    # Prefer the shortest name (base project, no variant suffix)
    candidates.sort(key=lambda p: len(p.name))
    return candidates[0]


def build_pipeline_lookup(pipeline_data: dict) -> dict[str, dict]:
    """Build a key->variable dict from validation-latest JSON."""
    lookup: dict[str, dict] = {}
    for cat in pipeline_data.get("categories", []):
        for var in cat.get("variables", []):
            lookup[var["key"]] = var
    return lookup


def compare_project(
    benchmark_path: Path, tolerance: float,
) -> dict[str, Any] | None:
    """Compare one benchmark project against its pipeline data."""
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    expedient = benchmark.get("expedient", "")
    municipality = benchmark.get("municipality", "")
    bench_vars = benchmark.get("variables", {})

    pipeline_path = find_pipeline_json(expedient)
    if pipeline_path is None:
        return None

    pipeline_data = json.loads(pipeline_path.read_text(encoding="utf-8"))
    pipe_lookup = build_pipeline_lookup(pipeline_data)

    results: list[dict[str, Any]] = []

    for key, bench_val in bench_vars.items():
        # Skip excluded keys (correct by design)
        if key in EXCLUDED_KEYS:
            continue
        # Skip arrays and nulls on benchmark side
        if bench_val is None or isinstance(bench_val, (list, dict)):
            continue

        pipe_var = pipe_lookup.get(key)
        if pipe_var is None:
            continue
        pipe_val = pipe_var.get("value")
        if pipe_val is None or pipe_val == "":
            continue
        # Skip array displays like "[2 items]"
        if isinstance(pipe_val, str) and pipe_val.startswith("[") and pipe_val.endswith("items]"):
            continue

        label = pipe_var.get("label", key)

        if key in NUMERIC_KEYS:
            btype, bparsed = classify_benchmark(bench_val)

            if btype == "threshold_min":
                # ">X": pipeline must be >= X
                pipe_num = parse_numeric(pipe_val)
                if pipe_num is None:
                    continue
                if pipe_num >= bparsed:
                    deviation = round((pipe_num - bparsed) / bparsed * 100, 1) if bparsed else 0.0
                    status = "MATCH"
                else:
                    deviation = round((pipe_num - bparsed) / bparsed * 100, 1)
                    status = "CLOSE" if abs(deviation) <= 15 else "MISMATCH"
                results.append({
                    "key": key, "label": label,
                    "benchmark": bench_val, "pipeline": pipe_val,
                    "pipeline_parsed": pipe_num,
                    "deviation_pct": deviation, "status": status,
                    "type": "threshold_min",
                })

            elif btype == "refusal":
                # "R": pipeline should also show refusal
                pipe_str = str(pipe_val).upper()
                has_refusal = "R" in pipe_str and parse_numeric(pipe_val) is None
                if not has_refusal:
                    pipe_num = parse_numeric(pipe_val)
                    has_refusal = pipe_num is not None and pipe_num >= 100
                status = "MATCH" if has_refusal else "MISMATCH"
                results.append({
                    "key": key, "label": label,
                    "benchmark": bench_val, "pipeline": pipe_val,
                    "pipeline_parsed": None,
                    "deviation_pct": None, "status": status,
                    "type": "refusal",
                })

            elif btype == "range":
                # "X-Y": pipeline must fall within range
                pipe_num = parse_numeric(pipe_val)
                if pipe_num is None:
                    continue
                lo, hi = bparsed
                if lo <= pipe_num <= hi:
                    status = "MATCH"
                    deviation = 0.0
                else:
                    mid = (lo + hi) / 2
                    deviation = round((pipe_num - mid) / mid * 100, 1) if mid else 0.0
                    status = "CLOSE" if abs(deviation) <= 15 else "MISMATCH"
                results.append({
                    "key": key, "label": label,
                    "benchmark": bench_val, "pipeline": pipe_val,
                    "pipeline_parsed": pipe_num,
                    "deviation_pct": deviation, "status": status,
                    "type": "range",
                })

            elif btype == "numeric":
                pipe_num = parse_numeric(pipe_val)
                if pipe_num is None:
                    continue
                deviation, status = compare_numeric(bparsed, pipe_num, tolerance)
                results.append({
                    "key": key, "label": label,
                    "benchmark": bench_val, "pipeline": pipe_val,
                    "pipeline_parsed": pipe_num,
                    "deviation_pct": deviation, "status": status,
                    "type": "numeric",
                })
            # btype == "text" for a NUMERIC_KEY: fall through to text comparison
            else:
                status = compare_text(str(bench_val), str(pipe_val))
                results.append({
                    "key": key, "label": label,
                    "benchmark": bench_val, "pipeline": pipe_val,
                    "pipeline_parsed": None,
                    "deviation_pct": None, "status": status,
                    "type": "text",
                })

        elif key in TEXT_KEYS:
            # Apply normalizer if one exists for this key
            normalizer = TEXT_NORMALIZERS.get(key)
            if normalizer:
                status = compare_text(
                    normalizer(str(bench_val)),
                    normalizer(str(pipe_val)),
                )
            else:
                status = compare_text(str(bench_val), str(pipe_val))
            results.append({
                "key": key,
                "label": label,
                "benchmark": bench_val,
                "pipeline": pipe_val,
                "pipeline_parsed": None,
                "deviation_pct": None,
                "status": status,
                "type": "text",
            })

    # Add tier to each result
    for r in results:
        r["tier"] = VARIABLE_TIER.get(r["key"], "A")

    total = len(results)
    match = sum(1 for r in results if r["status"] == "MATCH")
    close = sum(1 for r in results if r["status"] == "CLOSE")
    mismatch = sum(1 for r in results if r["status"] == "MISMATCH")
    # Count benchmark vars that had no pipeline counterpart
    compared_keys = {r["key"] for r in results}
    missing = sum(
        1 for k, v in bench_vars.items()
        if v is not None
        and not isinstance(v, (list, dict))
        and k not in EXCLUDED_KEYS
        and (k in NUMERIC_KEYS or k in TEXT_KEYS)
        and k not in compared_keys
    )
    correctness = round(match / total * 100, 1) if total else 0.0

    # Per-tier summary
    tier_summary = {}
    for tier in ("A", "B", "C"):
        tier_results = [r for r in results if r["tier"] == tier]
        t = len(tier_results)
        m = sum(1 for r in tier_results if r["status"] == "MATCH")
        c = sum(1 for r in tier_results if r["status"] == "CLOSE")
        x = sum(1 for r in tier_results if r["status"] == "MISMATCH")
        tier_summary[tier] = {
            "total": t, "match": m, "close": c, "mismatch": x,
            "correctness_pct": round(m / t * 100, 1) if t else 0.0,
        }

    return {
        "expedient": expedient,
        "municipality": municipality,
        "variables": results,
        "summary": {
            "total": total,
            "match": match,
            "close": close,
            "mismatch": mismatch,
            "missing": missing,
            "correctness_pct": correctness,
        },
        "tier_summary": tier_summary,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare G3DT benchmark values against pipeline values",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=5,
        help="Numeric tolerance in %% for MATCH status (default: 5)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Compare a single project by expedient number (e.g. 4001612)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all variables including MATCHes",
    )
    args = parser.parse_args()

    if not BENCHMARKS_DIR.is_dir():
        print(f"Benchmarks directory not found: {BENCHMARKS_DIR}")
        print("Run scripts/extract_benchmark_values.py first.")
        sys.exit(1)

    if not VALIDATION_DIR.is_dir():
        print(f"Validation directory not found: {VALIDATION_DIR}")
        print("Run scripts/collect_readiness.py first.")
        sys.exit(1)

    # Collect benchmark files
    benchmark_files = sorted(BENCHMARKS_DIR.glob("*-benchmark.json"))
    if args.project:
        benchmark_files = [
            f for f in benchmark_files if f.name.startswith(args.project)
        ]

    if not benchmark_files:
        print("No benchmark files found.")
        sys.exit(1)

    print(f"=== Benchmark Comparison ===")
    print()

    all_projects: list[dict[str, Any]] = []
    global_match = 0
    global_close = 0
    global_mismatch = 0
    global_missing = 0
    global_total = 0

    for bf in benchmark_files:
        result = compare_project(bf, args.tolerance)
        if result is None:
            exp = bf.stem.replace("-benchmark", "")
            print(f"{exp}  -- no pipeline data found, skipping")
            print()
            continue

        all_projects.append(result)
        s = result["summary"]
        global_match += s["match"]
        global_close += s["close"]
        global_mismatch += s["mismatch"]
        global_missing += s["missing"]
        global_total += s["total"]

        # Print project header
        header = (
            f"{result['expedient']} {result['municipality']}  "
            f"({s['match']}/{s['total']} match, {s['correctness_pct']}% correct)"
        )
        print(header)

        # Print variables (non-MATCH by default, all with --verbose)
        for var in result["variables"]:
            if var["status"] == "MATCH" and not args.verbose:
                continue
            status_str = _status_colored(f"{var['status']:<9}")
            key_str = f"{var['key']:<24}"
            if var["type"] == "numeric":
                bench_str = f"Eva: {var['benchmark']:<10}"
                pipe_str = f"Ours: {var['pipeline']:<10}"
                dev_str = f"Dev: {var['deviation_pct']:+.1f}%"
                print(f"  {status_str} {key_str} {bench_str} {pipe_str} {dev_str}")
            else:
                bench_short = str(var["benchmark"])[:30]
                pipe_short = str(var["pipeline"])[:30]
                print(f"  {status_str} {key_str} Eva: {bench_short:<32} Ours: {pipe_short}")
        print()

    # Global summary
    global_correctness = round(global_match / global_total * 100, 1) if global_total else 0.0

    # Per-tier global aggregation
    tier_global: dict[str, dict[str, int]] = {}
    for tier in ("A", "B", "C"):
        tier_global[tier] = {"total": 0, "match": 0, "close": 0, "mismatch": 0}
    for proj in all_projects:
        for tier, ts in proj.get("tier_summary", {}).items():
            for k in ("total", "match", "close", "mismatch"):
                tier_global[tier][k] += ts[k]

    print(f"=== Global Summary ===")
    print(
        f"Projects: {len(all_projects)} | "
        f"Vars compared: {global_total} | "
        f"Match: {global_match} | "
        f"Close: {global_close} | "
        f"Mismatch: {global_mismatch}"
    )
    print(f"Overall correctness: {global_correctness}%")
    print()
    print("Per-tier correctness:")
    tier_labels = {"A": "Auto-extractable", "B": "Manual/on-site", "C": "Professional judgment"}
    for tier in ("A", "B", "C"):
        tg = tier_global[tier]
        pct = round(tg["match"] / tg["total"] * 100, 1) if tg["total"] else 0.0
        label = tier_labels[tier]
        print(f"  Tier {tier} ({label}): {tg['match']}/{tg['total']} match ({pct}%)")
    print(f"  (Excluded: data_signatura_text — correct by design)")

    # Write comparison JSON
    comparison = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tolerance_pct": args.tolerance,
        "projects": all_projects,
        "global_summary": {
            "total_vars": global_total,
            "match": global_match,
            "close": global_close,
            "mismatch": global_mismatch,
            "missing": global_missing,
            "correctness_pct": global_correctness,
        },
    }

    BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BENCHMARKS_DIR / "_comparison.json"
    output_path.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nComparison saved to {output_path}")


if __name__ == "__main__":
    main()
