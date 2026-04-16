#!/usr/bin/env python3
"""Compare Claude Code extraction results against Eva's ground truth.

Usage:
    python tests/cc_only/compare_cc_results.py tests/cc_only/results/4001612_cc_only.json --project "4001612 BELL-LLOC"
    python tests/cc_only/compare_cc_results.py results.json --project "3001631 RUBI" --save-json out.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path so we can import from scripts/
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.compare_benchmarks import (
    TEXT_NORMALIZERS,
    VARIABLE_TIER,
    compare_numeric,
    compare_text,
    parse_numeric,
)

# ANSI colors (tty only)
_USE_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def _status_colored(status: str) -> str:
    if status == "MATCH":
        return _c(status, "32")
    if status == "CLOSE":
        return _c(status, "33")
    return _c(status, "31")


def load_cc_results(path: Path) -> dict:
    data = json.loads(path.read_text())
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def load_eva_ground_truth(project: str) -> dict:
    ref_dir = _PROJECT_ROOT / "reference-material" / project / "validation"
    eva_path = ref_dir / "eva_reference_values.json"
    if not eva_path.exists():
        sys.exit(f"Eva ground truth not found: {eva_path}")
    data = json.loads(eva_path.read_text())
    return data.get("variables", {})


def compare_variable(var: str, eva_val: str, cc_val: str) -> str:
    """Return MATCH, CLOSE, or MISMATCH using the same logic as compare_benchmarks."""
    # Apply normalizers if available
    normalizer = TEXT_NORMALIZERS.get(var)
    if normalizer:
        eva_val = normalizer(eva_val)
        cc_val = normalizer(cc_val)

    # Try numeric comparison first
    eva_num = parse_numeric(eva_val)
    cc_num = parse_numeric(cc_val)
    if eva_num is not None and cc_num is not None:
        _, status = compare_numeric(eva_num, cc_num, tolerance=5.0)
        return status

    # Fallback to text comparison
    return compare_text(eva_val, cc_val)


def main():
    parser = argparse.ArgumentParser(description="Compare CC results vs Eva ground truth")
    parser.add_argument("cc_json", type=Path, help="Path to CC results JSON")
    parser.add_argument("--project", required=True, help='Project folder name (e.g. "4001612 BELL-LLOC")')
    parser.add_argument("--save-json", type=Path, help="Save comparison results to JSON")
    args = parser.parse_args()

    cc_results = load_cc_results(args.cc_json)
    eva_vars = load_eva_ground_truth(args.project)

    # Collect all variable names from Eva (ground truth drives comparison)
    all_vars = sorted(eva_vars.keys())

    results = []
    counts = {"MATCH": 0, "CLOSE": 0, "MISMATCH": 0, "NOT_EXTRACTED": 0}

    # Header
    hdr = f"{'Variable':<30} {'Eva value':<30} {'CC value':<30} {'Status':<16} {'Conf':>5}"
    print(f"\n{_c(args.project, '1')}")
    print("-" * len(hdr))
    print(hdr)
    print("-" * len(hdr))

    for var in all_vars:
        eva_entry = eva_vars[var]
        eva_val = str(eva_entry.get("value", ""))

        cc_entry = cc_results.get(var)
        if cc_entry is None or cc_entry.get("value") in (None, ""):
            status = "NOT_EXTRACTED"
            cc_val = ""
            conf = ""
        else:
            cc_val = str(cc_entry["value"])
            conf_num = cc_entry.get("confidence")
            conf = f"{conf_num:.2f}" if conf_num is not None else ""
            status = compare_variable(var, eva_val, cc_val)

        counts[status] += 1
        tier = VARIABLE_TIER.get(var, "-")
        results.append({"variable": var, "tier": tier, "eva": eva_val, "cc": cc_val, "status": status})

        # Truncate display values
        eva_disp = (eva_val[:27] + "...") if len(eva_val) > 30 else eva_val
        cc_disp = (cc_val[:27] + "...") if len(cc_val) > 30 else cc_val

        print(f"{var:<30} {eva_disp:<30} {cc_disp:<30} {_status_colored(status):<16} {conf:>5}")

    # Summary
    total = len(all_vars)
    ok = counts["MATCH"] + counts["CLOSE"]
    pct = (ok / total * 100) if total else 0
    print("-" * len(hdr))
    m, cl, mm, ne = counts["MATCH"], counts["CLOSE"], counts["MISMATCH"], counts["NOT_EXTRACTED"]
    print(
        f"Total: {total}  "
        f"{_c('MATCH: ' + str(m), '32')}  "
        f"{_c('CLOSE: ' + str(cl), '33')}  "
        f"{_c('MISMATCH: ' + str(mm), '31')}  "
        f"NOT_EXTRACTED: {ne}  "
        f"Accuracy: {_c(f'{pct:.1f}%', '1')}"
    )

    if args.save_json:
        args.save_json.write_text(json.dumps({"project": args.project, "counts": counts, "results": results}, indent=2))
        print(f"\nSaved to {args.save_json}")


if __name__ == "__main__":
    main()
