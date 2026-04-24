#!/usr/bin/env python3
"""AI pipeline Stage 4 — per-source LLM analysis CLI.

Usage:
    python scripts/ai_pipeline_analysis.py --project 4001670
    python scripts/ai_pipeline_analysis.py --project 4001670 --save
    python scripts/ai_pipeline_analysis.py --project 4001670 --source PENETROS
    python scripts/ai_pipeline_analysis.py --project 4001670 --model claude-opus-4-7

Notes:
- Requires ANTHROPIC_API_KEY in the environment.
- Uses cache at validation/ai_pipeline/analysis/{stem}/_cache.json; re-runs are free
  unless --force is passed or artifact content changed.
- --source is a substring filter over source paths (dev tool).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_dotenv() -> None:
    """Load .env from project root if it exists (matches compare_benchmarks pattern)."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

from automation.ai_pipeline.analysis import analyze_project, save_analysis


REFERENCE_ROOT = Path(__file__).parent.parent / "reference-material"


def _resolve_project(project: str | None, project_path: str | None) -> Path:
    if project_path:
        p = Path(project_path)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if not p.is_dir():
            raise SystemExit(f"Project path does not exist: {p}")
        return p
    if not project:
        raise SystemExit("Must provide --project or --project-path")
    candidate = REFERENCE_ROOT / project
    if candidate.is_dir():
        return candidate
    matches = [d for d in REFERENCE_ROOT.iterdir() if d.is_dir() and d.name.startswith(project)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(
            f"Ambiguous --project {project!r}; matches:\n" + "\n".join(f"  - {d.name}" for d in matches)
        )
    raise SystemExit(f"No project matches {project!r} under {REFERENCE_ROOT}")


def _print_human(analysis, project_root: Path) -> None:
    print(f"Project:  {project_root.name}")
    print(f"Analyzed: {analysis.analyzed_at}")
    print()
    if analysis.systemic_failure:
        print(f"⚠ SYSTEMIC FAILURE: {analysis.systemic_failure.error_type}")
        print(f"  {analysis.systemic_failure.message}")
        return
    for line in analysis.eva_summary:
        print(line)
    print()
    print(f"Sources analyzed: {len(analysis.sources)}")
    if analysis.failures:
        print(f"Per-source failures: {len(analysis.failures)}")
        for f in analysis.failures:
            print(f"  [{f.error_type}] {f.source_path}: {f.last_error[:120]}")
    print(f"Tokens: {analysis.total_input_tokens:,} in / {analysis.total_output_tokens:,} out")
    print(f"Est. cost: ${analysis.estimated_cost_usd:.4f}")
    if analysis.cache_hits:
        print(f"Cache hits: {analysis.cache_hits}")
    print()
    print(f"Concepts covered: {len(analysis.candidates_by_concept)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--project", help="Project name or ID prefix (under reference-material/)")
    g.add_argument("--project-path", help="Absolute or relative path to project folder")
    ap.add_argument("--save", action="store_true",
                    help="Write manifest to {project}/validation/ai_analysis.json")
    ap.add_argument("--json", action="store_true",
                    help="Print full analysis as JSON")
    sg = ap.add_mutually_exclusive_group()
    sg.add_argument("--source",
                    help="Only analyze sources whose path contains this substring (case-insensitive)")
    sg.add_argument("--source-exact",
                    help="Only analyze the source whose path equals this value exactly (case-sensitive)")
    sg.add_argument("--source-regex",
                    help="Only analyze sources whose path matches this Python regex (case-sensitive re.search)")
    ap.add_argument("--model", help="Override default model (e.g. claude-opus-4-7)")
    args = ap.parse_args()

    project_root = _resolve_project(args.project, args.project_path)
    analysis = analyze_project(
        project_root,
        model=args.model,
        source_filter=args.source,
        source_exact=args.source_exact,
        source_regex=args.source_regex,
    )

    if args.json:
        print(analysis.model_dump_json(indent=2))
    else:
        _print_human(analysis, project_root)

    if args.save:
        out = save_analysis(analysis, project_root)
        if not args.json:
            print(f"\nSaved: {out}")

    # Exit nonzero on systemic failure so scripts can chain
    return 2 if analysis.systemic_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
