#!/usr/bin/env python3
"""AI pipeline Stage 2 — file typology + image extraction CLI.

Usage:
    python scripts/ai_pipeline_typology.py --project 4001612
    python scripts/ai_pipeline_typology.py --project 4001612 --save
    python scripts/ai_pipeline_typology.py --project 4001612 --json
    python scripts/ai_pipeline_typology.py --project 4001612 --no-extract
    python scripts/ai_pipeline_typology.py --project-path "reference-material/4001612 BELL-LLOC"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.ai_pipeline.typology import classify_project, save_typology


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


def _print_human(typ, project_root: Path) -> None:
    print(f"Project: {project_root.name}")
    print(f"Classified: {typ.classified_at}")
    print()
    for line in typ.eva_summary:
        print(line)
    print()
    print("Recompte per categoria:")
    cats = sorted(typ.counts_by_category.items(), key=lambda kv: (-kv[1], kv[0]))
    max_name = max((len(c) for c, _ in cats), default=0)
    for name, count in cats:
        print(f"  {name.ljust(max_name)}  {count}")
    if typ.warnings:
        print()
        print("Advertències:")
        for w in typ.warnings:
            print(f"  ! {w}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--project", help="Project name or ID prefix (under reference-material/)")
    g.add_argument("--project-path", help="Absolute or relative path to project folder")
    ap.add_argument("--save", action="store_true",
                    help="Write JSON to {project}/validation/ai_typology.json")
    ap.add_argument("--json", action="store_true",
                    help="Print full typology as JSON to stdout")
    ap.add_argument("--no-extract", action="store_true",
                    help="Skip embedded-image extraction (faster re-runs)")
    args = ap.parse_args()

    project_root = _resolve_project(args.project, args.project_path)
    typ = classify_project(project_root, extract_images=not args.no_extract)

    if args.json:
        print(typ.model_dump_json(indent=2))
    else:
        _print_human(typ, project_root)

    if args.save:
        out = save_typology(typ, project_root)
        if not args.json:
            print(f"\nSaved: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
