#!/usr/bin/env python3
"""CC-Agentic test harness: run insertion-point tests and compare to Eva.

Usage:
    python tests/cc_agentic/harness.py --test T1 --project "4001612 BELL-LLOC"
    python tests/cc_agentic/harness.py --test T1 --all
    python tests/cc_agentic/harness.py --test T1,T4 --all --compare
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parents[1]
_RESULTS_DIR = _THIS_DIR / 'results'
_REF_DIR = _PROJECT_ROOT / 'reference-material'
_SCHEMA_PATH = _PROJECT_ROOT / 'schemas' / 'concepts' / 'report_variables.yaml'

sys.path.insert(0, str(_PROJECT_ROOT))

from tests.cc_agentic.cc_extractor import extract_from_files, load_concept_schema

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project discovery
# ---------------------------------------------------------------------------

_PROJECTS_WITH_EVA = [
    '3001621 CASTELLAR DEL VALLES',
    '3001631 RUBI',
    '4001607 LINYOLA',  # NOTE: not LINYOLA2 sibling
    '4001612 BELL-LLOC',
    '4001670 ALCOLETGE',
    '4001671 VILANOVA DE SEGRIA',
    '4001679 ANCILES',
]


def _list_projects(project_filter: str | None) -> list[str]:
    """Return list of project folder names to test."""
    if project_filter:
        return [project_filter]
    return [p for p in _PROJECTS_WITH_EVA if (_REF_DIR / p / 'validation' / 'eva_reference_values.json').exists()]


def _load_eva(project: str) -> dict:
    """Load Eva ground truth for a project. Returns {var: {value, ...}}."""
    eva_path = _REF_DIR / project / 'validation' / 'eva_reference_values.json'
    if not eva_path.exists():
        return {}
    data = json.loads(eva_path.read_text(encoding='utf-8'))
    return data.get('variables', {})


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def _discover_project_files(project_path: Path) -> list[dict]:
    """Discover all project files using FileScanner + msg_attachments.

    Returns list of {path, role, origin}.
    """
    from automation.file_scanner import FileScanner
    from automation.fileminer import mine_project

    scanner = FileScanner(project_path)
    mapping = scanner.scan()
    scanner.save(mapping)

    # Load saved JSON for FileMiner (FileMapping has no to_dict method)
    fm_json = project_path / 'file_mapping.json'
    fm_dict = json.loads(fm_json.read_text(encoding='utf-8')) if fm_json.exists() else None
    mine_project(project_path, file_mapping=fm_dict)

    files: list[dict] = []
    seen_paths: set[str] = set()

    # Classified roles
    for role_name, role in mapping.roles.items():
        fpath = project_path / role.path
        if fpath.exists() and str(fpath) not in seen_paths:
            files.append({'path': str(fpath), 'role': role_name, 'origin': 'project'})
            seen_paths.add(str(fpath))

    # Unassigned files
    for rel in mapping.unassigned:
        fpath = project_path / rel
        if fpath.exists() and str(fpath) not in seen_paths:
            files.append({'path': str(fpath), 'role': 'unassigned', 'origin': 'project'})
            seen_paths.add(str(fpath))

    # Email attachments
    msg_dir = project_path / 'validation' / 'msg_attachments'
    if msg_dir.is_dir():
        for f in sorted(msg_dir.rglob('*')):
            if f.is_file() and str(f) not in seen_paths:
                files.append({'path': str(f), 'role': 'email_attachment', 'origin': 'email'})
                seen_paths.add(str(f))

    return files


# ---------------------------------------------------------------------------
# Comparison helper
# ---------------------------------------------------------------------------

def _compare_vs_eva(
    cc_vars: dict[str, dict],
    eva_vars: dict[str, dict],
) -> dict[str, Any]:
    """Compare CC extraction against Eva ground truth."""
    from scripts.compare_benchmarks import (
        TEXT_NORMALIZERS,
        VARIABLE_TIER,
        compare_numeric,
        compare_text,
        parse_numeric,
    )

    counts = {'MATCH': 0, 'CLOSE': 0, 'MISMATCH': 0, 'NOT_EXTRACTED': 0}
    details: list[dict] = []

    for var, eva_entry in sorted(eva_vars.items()):
        eva_val = str(eva_entry.get('value', ''))
        cc_entry = cc_vars.get(var)

        if cc_entry is None or cc_entry.get('value') in (None, ''):
            counts['NOT_EXTRACTED'] += 1
            details.append({'variable': var, 'tier': VARIABLE_TIER.get(var, '-'),
                            'eva': eva_val, 'cc': '', 'status': 'NOT_EXTRACTED'})
            continue

        cc_val = str(cc_entry['value'])

        # Apply normalizers
        normalizer = TEXT_NORMALIZERS.get(var)
        eva_cmp = normalizer(eva_val) if normalizer else eva_val
        cc_cmp = normalizer(cc_val) if normalizer else cc_val

        # Try numeric first
        eva_num = parse_numeric(eva_cmp)
        cc_num = parse_numeric(cc_cmp)
        if eva_num is not None and cc_num is not None:
            _, status = compare_numeric(eva_num, cc_num, tolerance=5.0)
        else:
            status = compare_text(eva_cmp, cc_cmp)

        counts[status] += 1
        details.append({
            'variable': var,
            'tier': VARIABLE_TIER.get(var, '-'),
            'eva': eva_val,
            'cc': cc_val,
            'confidence': cc_entry.get('confidence'),
            'status': status,
        })

    total = len(eva_vars)
    ok = counts['MATCH'] + counts['CLOSE']
    accuracy = (ok / total * 100) if total else 0.0

    return {
        'total_eva_vars': total,
        'counts': counts,
        'accuracy_pct': round(accuracy, 1),
        'details': details,
    }


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _build_result(
    test_id: str,
    project: str,
    files: list[dict],
    cc_vars: dict[str, dict],
    trace: list[dict],
    comparison: dict,
    duration_s: float,
) -> dict:
    """Build the result JSON structure."""
    files_from_email = sum(1 for f in files if f.get('origin') == 'email')
    usage_entry = next((t for t in trace if t.get('type') == 'summary'), {})
    total_usage = usage_entry.get('total_usage', {})

    return {
        'metadata': {
            'test_id': test_id,
            'project': project,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'files_available': len(files),
            'files_read': sum(1 for t in trace if t.get('type') == 'file_extraction'),
            'files_from_email': files_from_email,
            'duration_s': round(duration_s, 1),
            'api_calls': total_usage.get('api_calls', 0),
            'input_tokens': total_usage.get('input_tokens', 0),
            'output_tokens': total_usage.get('output_tokens', 0),
        },
        'files_inventory': [
            {'path': f['path'], 'role': f['role'], 'origin': f['origin']}
            for f in files
        ],
        'variables': cc_vars,
        'comparison': {'vs_eva': comparison},
        'trace': trace,
    }


# ---------------------------------------------------------------------------
# Test implementations
# ---------------------------------------------------------------------------

def run_t1(project: str) -> dict:
    """T1 (post_discovery): FileScanner + FileMiner, then CC-Agentic extracts all."""
    project_path = _REF_DIR / project
    t0 = time.monotonic()

    files = _discover_project_files(project_path)
    cc_vars, trace = extract_from_files(files, _SCHEMA_PATH)
    eva_vars = _load_eva(project)
    comparison = _compare_vs_eva(cc_vars, eva_vars) if eva_vars else {}

    return _build_result('T1', project, files, cc_vars, trace, comparison, time.monotonic() - t0)


def run_t2(project: str) -> dict:
    """T2 (gap_filler): run pipeline first, then CC-Agentic fills gaps."""
    from automation.auto_extractor import auto_extract

    project_path = _REF_DIR / project
    t0 = time.monotonic()

    # Phase 1: run full pipeline
    ae_result = auto_extract(str(project_path))
    pipeline_prefills = ae_result.prefills

    # Phase 2: find gaps
    gap_vars: set[str] = set()
    concepts = load_concept_schema(_SCHEMA_PATH)
    for cid in concepts:
        val = pipeline_prefills.get(cid)
        if val is None or val == '':
            gap_vars.add(cid)

    # Phase 3: discover files and extract only gaps
    files = _discover_project_files(project_path)
    if gap_vars:
        cc_vars, trace = extract_from_files(files, _SCHEMA_PATH, agentic_crops=True)
        # Only keep gap variables from CC
        cc_gap_vars = {k: v for k, v in cc_vars.items() if k in gap_vars}
    else:
        cc_gap_vars = {}
        trace = []

    # Phase 4: merge pipeline + CC gap fills
    merged: dict[str, dict] = {}
    for cid in concepts:
        pipe_val = pipeline_prefills.get(cid)
        if pipe_val is not None and pipe_val != '':
            merged[cid] = {
                'value': pipe_val,
                'confidence': 0.8,
                'source_file': 'pipeline',
                'source_origin': 'pipeline',
                'extraction_method': 'auto_extract',
            }
        elif cid in cc_gap_vars:
            merged[cid] = cc_gap_vars[cid]

    eva_vars = _load_eva(project)
    comparison = _compare_vs_eva(merged, eva_vars) if eva_vars else {}

    result = _build_result('T2', project, files, merged, trace, comparison, time.monotonic() - t0)
    result['metadata']['gaps_found'] = len(gap_vars)
    result['metadata']['gaps_filled_by_cc'] = len(cc_gap_vars)
    return result


def run_t3(project: str) -> dict:
    """T3 (parallel_validation): run both pipeline and CC, compare."""
    from automation.auto_extractor import auto_extract

    project_path = _REF_DIR / project
    t0 = time.monotonic()

    # Run pipeline
    ae_result = auto_extract(str(project_path))
    pipeline_prefills = ae_result.prefills

    # Run CC-Agentic
    files = _discover_project_files(project_path)
    cc_vars, trace = extract_from_files(files, _SCHEMA_PATH)

    # Compare both to Eva
    eva_vars = _load_eva(project)
    cc_comparison = _compare_vs_eva(cc_vars, eva_vars) if eva_vars else {}

    # Build pipeline vars in same format for comparison
    concepts = load_concept_schema(_SCHEMA_PATH)
    pipe_as_vars: dict[str, dict] = {}
    for cid in concepts:
        val = pipeline_prefills.get(cid)
        if val is not None and val != '':
            pipe_as_vars[cid] = {'value': val, 'confidence': 0.8}
    pipe_comparison = _compare_vs_eva(pipe_as_vars, eva_vars) if eva_vars else {}

    # Disagreement analysis
    disagreements: list[dict] = []
    for var in eva_vars:
        cc_entry = cc_vars.get(var, {})
        pipe_val = pipeline_prefills.get(var)
        cc_val = cc_entry.get('value')
        if cc_val is not None and pipe_val is not None and str(cc_val) != str(pipe_val):
            eva_val = str(eva_vars[var].get('value', ''))
            disagreements.append({
                'variable': var,
                'cc_value': str(cc_val),
                'pipeline_value': str(pipe_val),
                'eva_value': eva_val,
            })

    result = _build_result('T3', project, files, cc_vars, trace, cc_comparison, time.monotonic() - t0)
    result['comparison']['vs_pipeline'] = {
        'pipeline_accuracy': pipe_comparison.get('accuracy_pct', 0),
        'cc_accuracy': cc_comparison.get('accuracy_pct', 0),
        'disagreements': disagreements,
        'disagreement_count': len(disagreements),
    }
    return result


def run_t4(project: str) -> dict:
    """T4 (planol_only): extract only from planol/projecte files."""
    project_path = _REF_DIR / project
    t0 = time.monotonic()

    files = _discover_project_files(project_path)

    # Filter to architect-planol roles (real FileScanner role names)
    planol_roles = {'architect_plan', 'architect_plan_with_points',
                    'planol', 'projecte_arquitecte', 'planol_combined'}
    planol_files = [f for f in files if f.get('role') in planol_roles]

    if not planol_files:
        # Fallback: filename heuristics. A01/A.01 prefix, or "planol"/"plànol"/"tipol" anywhere.
        def _is_planol_name(path: str) -> bool:
            n = Path(path).name.upper()
            if n.startswith('A.01') or n.startswith('A01'):
                return True
            low = n.lower()
            return 'planol' in low or 'plànol' in low or 'tipol' in low
        planol_files = [f for f in files if _is_planol_name(f['path'])]

    cc_vars, trace = extract_from_files(planol_files, _SCHEMA_PATH, agentic_crops=True)

    # Only compare planol-relevant variables
    planol_groups = {'client', 'architect', 'location', 'building', 'parcel'}
    concepts = load_concept_schema(_SCHEMA_PATH)
    planol_concept_ids = {
        cid for cid, cdef in concepts.items()
        if cdef.get('group') in planol_groups
    }

    eva_vars = _load_eva(project)
    eva_filtered = {k: v for k, v in eva_vars.items() if k in planol_concept_ids}
    comparison = _compare_vs_eva(cc_vars, eva_filtered) if eva_filtered else {}

    result = _build_result('T4', project, planol_files, cc_vars, trace, comparison, time.monotonic() - t0)
    result['metadata']['planol_vars_targeted'] = len(planol_concept_ids)
    return result


_TEST_RUNNERS = {
    'T1': run_t1,
    'T2': run_t2,
    'T3': run_t3,
    'T4': run_t4,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

    parser = argparse.ArgumentParser(description='CC-Agentic test harness')
    parser.add_argument('--test', required=True, help='Test ID(s), comma-separated: T1,T2,T3,T4')
    parser.add_argument('--project', help='Project folder name (e.g. "4001612 BELL-LLOC")')
    parser.add_argument('--all', action='store_true', help='Run all projects with Eva ground truth')
    parser.add_argument('--compare', action='store_true', help='Print comparison table after run')
    args = parser.parse_args()

    if not args.project and not args.all:
        parser.error('Specify --project or --all')

    test_ids = [t.strip().upper() for t in args.test.split(',')]
    for tid in test_ids:
        if tid not in _TEST_RUNNERS:
            parser.error(f'Unknown test: {tid}. Valid: {", ".join(_TEST_RUNNERS)}')

    projects = _list_projects(args.project if not args.all else None)
    if not projects:
        print('No projects found with Eva ground truth.')
        sys.exit(1)

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results: list[dict] = []
    for tid in test_ids:
        runner = _TEST_RUNNERS[tid]
        for project in projects:
            exp = project.split()[0]
            print(f"\n{'='*60}")
            print(f"Running {tid} on {project}...")
            print(f"{'='*60}")

            try:
                result = runner(project)
                out_path = _RESULTS_DIR / f'{tid}_{exp}.json'
                out_path.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False),
                    encoding='utf-8',
                )
                all_results.append(result)
                acc = result.get('comparison', {}).get('vs_eva', {}).get('accuracy_pct', '?')
                dur = result['metadata']['duration_s']
                calls = result['metadata']['api_calls']
                print(f"  -> Accuracy: {acc}%  Duration: {dur}s  API calls: {calls}")
                print(f"  -> Saved: {out_path}")
            except Exception as exc:
                logger.exception("Failed %s on %s", tid, project)
                print(f"  -> FAILED: {exc}")

    if args.compare and all_results:
        _print_comparison_table(all_results)


def _print_comparison_table(results: list[dict]) -> None:
    """Print a summary comparison table across all results."""
    _USE_COLOR = sys.stdout.isatty()

    def _c(text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

    print(f"\n{'='*70}")
    print("COMPARISON SUMMARY")
    print(f"{'='*70}")
    hdr = f"{'Test':<6} {'Project':<25} {'Accuracy':>10} {'Dur(s)':>8} {'API':>5}"
    print(hdr)
    print('-' * 70)

    for r in results:
        meta = r['metadata']
        acc = r.get('comparison', {}).get('vs_eva', {}).get('accuracy_pct', 0)
        acc_str = f"{acc}%"
        if acc >= 80:
            acc_str = _c(acc_str, '32')
        elif acc >= 50:
            acc_str = _c(acc_str, '33')
        else:
            acc_str = _c(acc_str, '31')
        print(f"{meta['test_id']:<6} {meta['project']:<25} {acc_str:>10} {meta['duration_s']:>8.1f} {meta['api_calls']:>5}")

    print('-' * 70)


if __name__ == '__main__':
    main()
