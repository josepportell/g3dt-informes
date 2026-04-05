"""
Snapshot baseline for concept-format separation refactor.

Runs mine_project() + resolve_competition() on reference projects and
compares against saved snapshots. Any deviation = regression.

Usage:
    # Generate snapshots (first time or to update baseline):
    python -m tests.benchmark.snapshot_baseline --generate

    # Run as pytest (compare against saved snapshots):
    pytest tests/benchmark/snapshot_baseline.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.fileminer import mine_project, resolve_competition
from automation.fileminer.models import Signal

REF_DIR = PROJECT_ROOT / "reference-material"
SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"

# The 4 canonical reference projects
PROJECTS = [
    "4001612 BELL-LLOC",
    "3001631 RUBI",
    "3001621 CASTELLAR DEL VALLES",
    "4001607 LINYOLA",
]


def _serialize_resolved(resolved: dict) -> dict:
    """Serialize resolved competition results to a JSON-safe dict."""
    out = {}
    for var_name, rv in sorted(resolved.items()):
        out[var_name] = {
            "value": str(rv.value) if rv.value is not None else None,
            "source_file": rv.signal.source_file,
            "source_type": rv.source,
            "confidence": rv.confidence,
            "priority": rv.signal.priority,
            "alternatives_count": len(rv.alternatives),
        }
    return out


def _serialize_signal_summary(signals: list[Signal]) -> dict:
    """Summarize signal counts per source_file and per maps_to."""
    by_file: dict[str, int] = {}
    by_variable: dict[str, int] = {}
    for s in signals:
        by_file[s.source_file] = by_file.get(s.source_file, 0) + 1
        if s.maps_to:
            by_variable[s.maps_to] = by_variable.get(s.maps_to, 0) + 1
    return {
        "total_signals": len(signals),
        "mapped_signals": sum(1 for s in signals if s.maps_to),
        "by_file": dict(sorted(by_file.items())),
        "by_variable": dict(sorted(by_variable.items())),
    }


def _run_project(project_name: str) -> dict:
    """Run FileMiner + competition on a project and return serializable snapshot."""
    project_path = REF_DIR / project_name

    # Load file_mapping.json if exists (SmartScan output)
    fm_path = project_path / "file_mapping.json"
    file_mapping = None
    if fm_path.exists():
        file_mapping = json.loads(fm_path.read_text())

    # Mine
    result = mine_project(project_path, file_mapping=file_mapping)

    # Resolve competition
    resolved = resolve_competition(result.signals)

    return {
        "project": project_name,
        "signal_summary": _serialize_signal_summary(result.signals),
        "resolved": _serialize_resolved(resolved),
        "files_mined": result.files_mined,
        "files_skipped": result.files_skipped,
        "errors": result.errors,
    }


def generate_snapshots():
    """Generate snapshot JSON files for all reference projects."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    for project_name in PROJECTS:
        project_path = REF_DIR / project_name
        if not project_path.is_dir():
            print(f"SKIP {project_name} (not found)")
            continue

        print(f"Generating snapshot for {project_name}...")
        snapshot = _run_project(project_name)

        # Use sanitized filename
        safe_name = project_name.replace(" ", "_").replace("/", "_")
        out_path = SNAPSHOT_DIR / f"{safe_name}.json"
        out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
        print(f"  -> {out_path.name}: {snapshot['signal_summary']['total_signals']} signals, "
              f"{len(snapshot['resolved'])} resolved variables")

    print("\nDone. Snapshots saved to tests/benchmark/snapshots/")


def _load_snapshot(project_name: str) -> dict | None:
    """Load a saved snapshot for comparison."""
    safe_name = project_name.replace(" ", "_").replace("/", "_")
    path = SNAPSHOT_DIR / f"{safe_name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


# ============================================================
# Pytest tests: compare current output against saved snapshots
# ============================================================

@pytest.fixture(params=PROJECTS)
def project_name(request):
    return request.param


def test_snapshot_exists(project_name):
    """Verify that a baseline snapshot exists for each project."""
    snapshot = _load_snapshot(project_name)
    assert snapshot is not None, (
        f"No snapshot for {project_name}. Run: "
        f"python -m tests.benchmark.snapshot_baseline --generate"
    )


def test_resolved_values_match(project_name):
    """Core regression test: resolved variable values must match snapshot exactly."""
    project_path = REF_DIR / project_name
    if not project_path.is_dir():
        pytest.skip(f"{project_name} not found in reference-material/")

    snapshot = _load_snapshot(project_name)
    if snapshot is None:
        pytest.skip("No snapshot. Generate first.")

    current = _run_project(project_name)

    # Compare resolved variables
    snap_resolved = snapshot["resolved"]
    curr_resolved = current["resolved"]

    # Same set of variables
    snap_vars = set(snap_resolved.keys())
    curr_vars = set(curr_resolved.keys())
    assert snap_vars == curr_vars, (
        f"Variable set changed!\n"
        f"  Added: {curr_vars - snap_vars}\n"
        f"  Removed: {snap_vars - curr_vars}"
    )

    # Same values for each variable
    mismatches = []
    for var in sorted(snap_vars):
        sv = snap_resolved[var]
        cv = curr_resolved[var]
        if sv["value"] != cv["value"]:
            mismatches.append(
                f"  {var}: snapshot={sv['value']!r} vs current={cv['value']!r}"
            )
        if sv["source_file"] != cv["source_file"]:
            mismatches.append(
                f"  {var} source: snapshot={sv['source_file']!r} vs current={cv['source_file']!r}"
            )

    assert not mismatches, (
        f"Resolved values changed for {project_name}:\n" + "\n".join(mismatches)
    )


def test_signal_counts_stable(project_name):
    """Signal counts should not change significantly."""
    project_path = REF_DIR / project_name
    if not project_path.is_dir():
        pytest.skip(f"{project_name} not found")

    snapshot = _load_snapshot(project_name)
    if snapshot is None:
        pytest.skip("No snapshot.")

    current = _run_project(project_name)

    snap_total = snapshot["signal_summary"]["total_signals"]
    curr_total = current["signal_summary"]["total_signals"]

    # Allow up to 5% variation (e.g., from minor miner improvements)
    # but flag large changes
    assert abs(curr_total - snap_total) <= max(3, snap_total * 0.05), (
        f"Signal count changed significantly: {snap_total} -> {curr_total}"
    )


# ============================================================
# CLI entry point
# ============================================================

if __name__ == "__main__":
    if "--generate" in sys.argv:
        generate_snapshots()
    else:
        print("Usage:")
        print("  python -m tests.benchmark.snapshot_baseline --generate  # Create snapshots")
        print("  pytest tests/benchmark/snapshot_baseline.py -v          # Run regression tests")
