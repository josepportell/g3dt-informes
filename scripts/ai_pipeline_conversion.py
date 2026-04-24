#!/usr/bin/env python3
"""AI pipeline Stage 3 — conversion to LLM-ready artifacts CLI.

Usage:
    python scripts/ai_pipeline_conversion.py --project 4001670
    python scripts/ai_pipeline_conversion.py --project 4001670 --save
    python scripts/ai_pipeline_conversion.py --project 4001670 --json
    python scripts/ai_pipeline_conversion.py --project 4001670 --strategy pdf_to_markdown
    python scripts/ai_pipeline_conversion.py --project-path "reference-material/4001670 ALCOLETGE"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.ai_pipeline.conversion import convert_project, save_conversion


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


def _print_human(conv, project_root: Path) -> None:
    print(f"Project: {project_root.name}")
    print(f"Converted: {conv.converted_at}")
    print()
    for line in conv.eva_summary:
        print(line)
    print()
    print(f"Total artifacts: {len(conv.artifacts)}")
    print(f"Bytes on disk:   {conv.total_bytes:,}")
    if conv.warnings:
        print()
        print("Advertències:")
        for w in conv.warnings:
            print(f"  ! {w}")
    skipped = [a for a in conv.artifacts if a.skipped]
    if skipped:
        print()
        print(f"Saltats ({len(skipped)}):")
        for a in skipped:
            print(f"  [{a.strategy_used}] {a.source_path} — {a.skip_reason}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--project", help="Project name or ID prefix (under reference-material/)")
    g.add_argument("--project-path", help="Absolute or relative path to project folder")
    ap.add_argument("--save", action="store_true",
                    help="Write manifest to {project}/validation/ai_conversion.json")
    ap.add_argument("--json", action="store_true",
                    help="Print the full conversion manifest as JSON")
    ap.add_argument("--strategy", action="append",
                    help="Filter to one conversion_strategy (repeatable). "
                         "Useful for dev: --strategy pdf_to_markdown")
    args = ap.parse_args()

    project_root = _resolve_project(args.project, args.project_path)
    strategies = set(args.strategy) if args.strategy else None
    conv = convert_project(project_root, strategies=strategies)

    if args.json:
        print(conv.model_dump_json(indent=2))
    else:
        _print_human(conv, project_root)

    if args.save:
        out = save_conversion(conv, project_root)
        if not args.json:
            print(f"\nSaved: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
