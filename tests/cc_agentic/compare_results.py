#!/usr/bin/env python3
"""Compare CC-Agentic results against Eva ground truth (and optionally pipeline).

Enhanced comparison with per-tier and per-origin breakdowns.

Usage:
    python tests/cc_agentic/compare_results.py results/T1_4001612.json --project "4001612 BELL-LLOC"
    python tests/cc_agentic/compare_results.py results/T1_*.json --cross-project
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parents[1]
_REF_DIR = _PROJECT_ROOT / 'reference-material'

sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.compare_benchmarks import (
    TEXT_NORMALIZERS,
    VARIABLE_TIER,
    compare_numeric,
    compare_text,
    compare_text_llm,
    parse_numeric,
)

# ANSI colors
_USE_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def _status_colored(status: str) -> str:
    if status == 'MATCH':
        return _c(status, '32')
    if status == 'CLOSE':
        return _c(status, '33')
    if status == 'NOT_EXTRACTED':
        return _c(status, '90')
    return _c(status, '31')


# ---------------------------------------------------------------------------
# Eva loader
# ---------------------------------------------------------------------------

# Map concept schema names → Eva template variable names (and vice versa)
_CONCEPT_TO_EVA = {
    'client_name': 'client',
    'architect_name': 'architect_name_upper',
    'building_type': 'building_type_lower',
    'num_floors': 'plantes',

    'adjacent_north': 'adjacent_north_fmt',
    'adjacent_south': 'adjacent_south_fmt',
    'adjacent_east': 'adjacent_east_fmt',
    'adjacent_west': 'adjacent_west_fmt',

    'field_work_dates_text': 'data_camp_text',

    'sulfate_mg_kg': 'sulfate_value',

    'settlement_cm': 'settlement',
}
_EVA_TO_CONCEPT = {v: k for k, v in _CONCEPT_TO_EVA.items()}


def _load_eva(project: str) -> tuple[dict, dict]:
    """Load Eva ground truth. Returns (variables, template_texts)."""
    eva_path = _REF_DIR / project / 'validation' / 'eva_reference_values.json'
    if not eva_path.exists():
        return {}, {}
    data = json.loads(eva_path.read_text(encoding='utf-8'))
    variables = data.get('variables', {})
    templates: dict[str, str] = {}
    for var, entry in variables.items():
        if 'template_text' in entry:
            templates[var] = entry['template_text']
    return variables, templates


# ---------------------------------------------------------------------------
# Template fill + LLM judge cache
# ---------------------------------------------------------------------------

_TEMPLATE_CACHE_PATH = _THIS_DIR / 'results' / '_template_fill_cache.json'
_TEMPLATE_CACHE: dict[str, dict] = {}


def _load_template_cache() -> None:
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE_PATH.exists():
        try:
            _TEMPLATE_CACHE = json.loads(
                _TEMPLATE_CACHE_PATH.read_text(encoding='utf-8')
            )
        except (json.JSONDecodeError, OSError):
            _TEMPLATE_CACHE = {}


def _save_template_cache() -> None:
    _TEMPLATE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TEMPLATE_CACHE_PATH.write_text(
        json.dumps(_TEMPLATE_CACHE, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


def _template_cache_key(var_name: str, raw_value: str, template_text: str) -> str:
    raw = f"{var_name}|{raw_value}|{template_text}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def _fill_template(var_name: str, raw_value: str, template_text: str) -> str:
    """Ask LLM to generate the proper text that should replace the placeholder."""
    if not template_text or not raw_value:
        return raw_value

    ck = _template_cache_key(var_name, raw_value, template_text)
    if ck in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[ck].get('filled', raw_value)

    try:
        from automation.llm_client import get_anthropic_client, get_judge_model
        client = get_anthropic_client()
        response = client.messages.create(
            model=get_judge_model(),
            max_tokens=256,
            messages=[{'role': 'user', 'content':
                f"Given this report template: \"{template_text}\"\n"
                f"And this extracted value: \"{raw_value}\"\n"
                f"Generate ONLY the text that should replace the {{{{ {var_name} }}}} placeholder. "
                f"Match the language and style of the template. Return ONLY the replacement text, nothing else."
            }],
            timeout=30.0,
        )
        filled = response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Template fill failed for %s: %s", var_name, exc)
        filled = raw_value

    _TEMPLATE_CACHE[ck] = {'filled': filled, 'raw': raw_value, 'template': template_text}
    return filled


def _load_env() -> None:
    """Load .env from project root if present."""
    env_path = _PROJECT_ROOT / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())


# ---------------------------------------------------------------------------
# Variable comparison
# ---------------------------------------------------------------------------

def _compare_variable(var: str, eva_val: str, cc_val: str) -> str:
    """Compare one variable. Returns MATCH, CLOSE, or MISMATCH."""
    normalizer = TEXT_NORMALIZERS.get(var)
    if normalizer:
        eva_val = normalizer(eva_val)
        cc_val = normalizer(cc_val)

    eva_num = parse_numeric(eva_val)
    cc_num = parse_numeric(cc_val)
    if eva_num is not None and cc_num is not None:
        _, status = compare_numeric(eva_num, cc_num, tolerance=5.0)
        return status

    return compare_text(eva_val, cc_val)


# ---------------------------------------------------------------------------
# Single-file comparison
# ---------------------------------------------------------------------------

def compare_single(
    result_path: Path,
    project: str | None,
    *,
    update: bool = False,
    llm_judge: bool = False,
) -> dict:
    """Compare a single result JSON against Eva. Returns comparison dict.

    Args:
        result_path: Path to the CC-Agentic result JSON.
        project: Project folder name (overrides metadata).
        update: If True, write comparison back into the result JSON file.
        llm_judge: If True, use template fill + LLM judge for MISMATCH variables.
    """
    result = json.loads(result_path.read_text(encoding='utf-8'))
    cc_vars = result.get('variables', {})
    meta = result.get('metadata', {})

    if not project:
        project = meta.get('project', '')
    if not project:
        sys.exit(f"Cannot determine project for {result_path.name}. Use --project.")

    eva_vars, templates = _load_eva(project)
    if not eva_vars:
        sys.exit(f"No Eva ground truth for project: {project}")

    # Lazy-init Anthropic client for LLM judge
    _anthropic_client = None
    if llm_judge:
        _load_env()
        _load_template_cache()
        try:
            import anthropic
            _anthropic_client = anthropic.Anthropic()
        except Exception as exc:
            logger.warning("Cannot init Anthropic client for LLM judge: %s", exc)
            llm_judge = False

    counts = {'MATCH': 0, 'CLOSE': 0, 'MISMATCH': 0, 'NOT_EXTRACTED': 0}
    tier_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    origin_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    details: list[dict] = []

    for var in sorted(eva_vars.keys()):
        eva_entry = eva_vars[var]
        eva_val = str(eva_entry.get('value', ''))
        tier = VARIABLE_TIER.get(var, '-')

        # Try direct name first, then concept<->Eva alias
        cc_entry = cc_vars.get(var)
        if (cc_entry is None or cc_entry.get('value') in (None, '')) and var in _EVA_TO_CONCEPT:
            cc_entry = cc_vars.get(_EVA_TO_CONCEPT[var])
        if (cc_entry is None or cc_entry.get('value') in (None, '')) and var in _CONCEPT_TO_EVA:
            cc_entry = cc_vars.get(_CONCEPT_TO_EVA[var])
        if cc_entry is None or cc_entry.get('value') in (None, ''):
            status = 'NOT_EXTRACTED'
            cc_val = ''
            conf = None
            origin = ''
        else:
            cc_val = str(cc_entry['value'])
            conf = cc_entry.get('confidence')
            origin = cc_entry.get('source_origin', '')
            status = _compare_variable(var, eva_val, cc_val)

        # LLM judge: for MISMATCH text variables, try template fill + semantic comparison
        llm_detail: dict = {}
        if llm_judge and status == 'MISMATCH' and _anthropic_client and cc_val:
            template_text = templates.get(var, '')
            if template_text:
                filled = _fill_template(var, cc_val, template_text)
                llm_status, llm_score, llm_explanation = compare_text_llm(
                    var, eva_val, filled, _anthropic_client,
                )
                if llm_status in ('MATCH', 'CLOSE'):
                    status = llm_status
                llm_detail = {
                    'llm_filled': filled,
                    'llm_score': llm_score,
                    'llm_explanation': llm_explanation,
                }
            else:
                # No template, try direct LLM judge
                llm_status, llm_score, llm_explanation = compare_text_llm(
                    var, eva_val, cc_val, _anthropic_client,
                )
                if llm_status in ('MATCH', 'CLOSE'):
                    status = llm_status
                llm_detail = {
                    'llm_score': llm_score,
                    'llm_explanation': llm_explanation,
                }

        counts[status] += 1
        tier_counts[tier][status] += 1
        if origin:
            origin_counts[origin][status] += 1

        detail_entry = {
            'variable': var, 'tier': tier, 'eva': eva_val,
            'cc': cc_val, 'confidence': conf, 'status': status,
            'source_file': cc_entry.get('source_file', '') if cc_entry else '',
            'origin': origin,
        }
        if llm_detail:
            detail_entry['llm_judge'] = llm_detail
        details.append(detail_entry)

    # Persist caches if LLM judge was used
    if llm_judge:
        _save_template_cache()

    total = len(eva_vars)
    ok = counts['MATCH'] + counts['CLOSE']
    accuracy = (ok / total * 100) if total else 0.0

    comparison = {
        'project': project,
        'test_id': meta.get('test_id', '?'),
        'total_eva_vars': total,
        'counts': counts,
        'accuracy_pct': round(accuracy, 1),
        'tier_breakdown': {t: dict(c) for t, c in tier_counts.items()},
        'origin_breakdown': {o: dict(c) for o, c in origin_counts.items()},
        'details': details,
    }

    if update:
        result['comparison'] = result.get('comparison', {})
        result['comparison']['vs_eva'] = comparison
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')

    return comparison


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _print_detail_table(comparison: dict) -> None:
    """Print the per-variable detail table."""
    project = comparison['project']
    details = comparison['details']
    counts = comparison['counts']
    accuracy = comparison['accuracy_pct']

    hdr = f"{'Variable':<30} {'Tier':>4} {'Eva':<28} {'CC':<28} {'Status':<16} {'Conf':>5}"
    print(f"\n{_c(project, '1')} [{comparison.get('test_id', '?')}]")
    print('-' * len(hdr))
    print(hdr)
    print('-' * len(hdr))

    for d in details:
        eva_disp = (d['eva'][:25] + '...') if len(d['eva']) > 28 else d['eva']
        cc_disp = (d['cc'][:25] + '...') if len(d['cc']) > 28 else d['cc']
        conf_str = f"{d['confidence']:.2f}" if d['confidence'] is not None else ''
        print(f"{d['variable']:<30} {d['tier']:>4} {eva_disp:<28} {cc_disp:<28} {_status_colored(d['status']):<16} {conf_str:>5}")

    print('-' * len(hdr))
    m, cl, mm, ne = counts['MATCH'], counts['CLOSE'], counts['MISMATCH'], counts['NOT_EXTRACTED']
    total = comparison['total_eva_vars']
    print(
        f"Total: {total}  "
        f"{_c('MATCH: ' + str(m), '32')}  "
        f"{_c('CLOSE: ' + str(cl), '33')}  "
        f"{_c('MISMATCH: ' + str(mm), '31')}  "
        f"NOT_EXTRACTED: {ne}  "
        f"Accuracy: {_c(f'{accuracy:.1f}%', '1')}"
    )


def _print_tier_breakdown(comparison: dict) -> None:
    """Print per-tier accuracy breakdown."""
    print(f"\n{_c('Tier Breakdown:', '1')}")
    for tier in ('A', 'B', 'C', '-'):
        tc = comparison.get('tier_breakdown', {}).get(tier, {})
        total = sum(tc.values())
        if total == 0:
            continue
        ok = tc.get('MATCH', 0) + tc.get('CLOSE', 0)
        acc = (ok / total * 100) if total else 0
        print(f"  Tier {tier}: {ok}/{total} = {acc:.0f}%  "
              f"(M:{tc.get('MATCH',0)} C:{tc.get('CLOSE',0)} "
              f"X:{tc.get('MISMATCH',0)} NE:{tc.get('NOT_EXTRACTED',0)})")


def _print_origin_breakdown(comparison: dict) -> None:
    """Print per-origin accuracy breakdown."""
    origins = comparison.get('origin_breakdown', {})
    if not origins:
        return
    print(f"\n{_c('Origin Breakdown:', '1')}")
    for origin, oc in sorted(origins.items()):
        total = sum(oc.values())
        ok = oc.get('MATCH', 0) + oc.get('CLOSE', 0)
        acc = (ok / total * 100) if total else 0
        print(f"  {origin}: {ok}/{total} = {acc:.0f}%")


# ---------------------------------------------------------------------------
# Cross-project summary
# ---------------------------------------------------------------------------

def _print_cross_project(comparisons: list[dict]) -> None:
    """Print cross-project summary table."""
    print(f"\n{'='*60}")
    print(_c('CROSS-PROJECT SUMMARY', '1'))
    print(f"{'='*60}")
    hdr = f"{'Test':<6} {'Project':<28} {'Acc':>6} {'M':>4} {'C':>4} {'X':>4} {'NE':>4}"
    print(hdr)
    print('-' * 60)

    total_ok = 0
    total_vars = 0
    for comp in comparisons:
        c = comp['counts']
        ok = c['MATCH'] + c['CLOSE']
        total = comp['total_eva_vars']
        total_ok += ok
        total_vars += total
        acc_str = f"{comp['accuracy_pct']:.0f}%"
        print(f"{comp.get('test_id','?'):<6} {comp['project']:<28} {acc_str:>6} "
              f"{c['MATCH']:>4} {c['CLOSE']:>4} {c['MISMATCH']:>4} {c['NOT_EXTRACTED']:>4}")

    if total_vars > 0:
        overall = total_ok / total_vars * 100
        print('-' * 60)
        print(f"{'OVERALL':<35} {_c(f'{overall:.1f}%', '1'):>6}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description='Compare CC-Agentic results vs Eva')
    parser.add_argument('result_files', nargs='+', help='Result JSON file(s) or glob pattern')
    parser.add_argument('--project', help='Project folder name (overrides metadata)')
    parser.add_argument('--cross-project', action='store_true', help='Show cross-project summary')
    parser.add_argument('--no-details', action='store_true', help='Skip per-variable table')
    parser.add_argument('--update', action='store_true', help='Write comparison back into result JSON')
    parser.add_argument('--llm-judge', action='store_true',
                        help='Use template fill + LLM judge for MISMATCH variables (costs API calls)')
    args = parser.parse_args()

    # Expand globs
    paths: list[Path] = []
    for pattern in args.result_files:
        expanded = glob.glob(pattern)
        if expanded:
            paths.extend(Path(p) for p in expanded)
        else:
            paths.append(Path(pattern))

    comparisons: list[dict] = []
    for p in sorted(paths):
        if not p.exists():
            print(f"File not found: {p}", file=sys.stderr)
            continue

        comp = compare_single(p, args.project, update=args.update, llm_judge=args.llm_judge)
        comparisons.append(comp)

        if not args.no_details:
            _print_detail_table(comp)
        _print_tier_breakdown(comp)
        _print_origin_breakdown(comp)

    if args.cross_project and len(comparisons) > 1:
        _print_cross_project(comparisons)


if __name__ == '__main__':
    main()
