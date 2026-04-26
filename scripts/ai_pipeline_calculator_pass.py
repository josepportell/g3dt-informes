#!/usr/bin/env python3
"""AI pipeline Stage 4.5 — engineering calculator pass CLI.

Usage:
    python scripts/ai_pipeline_calculator_pass.py --project 4001670
    python scripts/ai_pipeline_calculator_pass.py --project 4001670 --save
    python scripts/ai_pipeline_calculator_pass.py --project 4001670 --force --save

Notes:
- Reads validation/ai_analysis.json (Stage 4) and user_data.json (foundation
  geometry). No LLM calls are made.
- Output goes to validation/ai_calculations.json when --save is passed.
- Phase 1 scope: qa_value + settlement_cm only.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_dotenv() -> None:
    """Load .env from project root if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

from automation.ai_pipeline.calculator_pass import (
    run_calculator_pass,
    save_calculations,
)


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
            f"Ambiguous --project {project!r}; matches:\n"
            + "\n".join(f"  - {d.name}" for d in matches)
        )
    raise SystemExit(f"No project matches {project!r} under {REFERENCE_ROOT}")


def _print_human(analysis, project_root: Path) -> None:
    print(f"Project:  {project_root.name}")
    print(f"Computed: {analysis.analyzed_at}")
    print()
    for line in analysis.eva_summary:
        print(line)
    print()
    if not analysis.sources:
        print("(no synthetic calculator source emitted)")
        return
    src = analysis.sources[0]
    print(f"Calculator source: {src.source_path}")
    print(f"Elapsed: {src.elapsed_ms} ms")
    print()
    if not src.candidates:
        print("No candidates emitted (calculator inputs were missing or invalid).")
        return
    print(f"Candidates ({len(src.candidates)}):")
    for c in src.candidates:
        print(f"  • {c.concept_id}: {c.value}")
        if c.reasoning:
            print(f"      reasoning: {c.reasoning}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--project", help="Project name or ID prefix (under reference-material/)")
    g.add_argument("--project-path", help="Absolute or relative path to project folder")
    ap.add_argument(
        "--save", action="store_true",
        help="Write manifest to {project}/validation/ai_calculations.json",
    )
    ap.add_argument(
        "--json", action="store_true", help="Print full analysis as JSON",
    )
    ap.add_argument(
        "--force", action="store_true",
        help="Bypass cache (recompute even if ai_calculations.json exists)",
    )
    args = ap.parse_args()

    project_root = _resolve_project(args.project, args.project_path)
    analysis = run_calculator_pass(project_root, force=args.force)

    if args.json:
        print(analysis.model_dump_json(indent=2))
    else:
        _print_human(analysis, project_root)

    if args.save:
        out = save_calculations(analysis, project_root)
        if not args.json:
            print(f"\nSaved: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
