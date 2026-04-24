#!/usr/bin/env python3
"""AI pipeline Stage 1 — project inventory CLI.

Usage:
    python scripts/ai_pipeline_inventory.py --project 4001612
    python scripts/ai_pipeline_inventory.py --project 4001612 --save
    python scripts/ai_pipeline_inventory.py --project "4001612 BELL-LLOC"
    python scripts/ai_pipeline_inventory.py --project-path "reference-material/4001612 BELL-LLOC"
    python scripts/ai_pipeline_inventory.py --project 4001612 --json       # machine-readable
    python scripts/ai_pipeline_inventory.py --project 4001612 --no-extract # skip .msg extraction
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.ai_pipeline.inventory import build_inventory, save_inventory


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

    # Exact match
    candidate = REFERENCE_ROOT / project
    if candidate.is_dir():
        return candidate

    # Prefix match (e.g. "4001612" → "4001612 BELL-LLOC")
    matches = [d for d in REFERENCE_ROOT.iterdir() if d.is_dir() and d.name.startswith(project)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(
            f"Ambiguous --project {project!r}; matches:\n" + "\n".join(f"  - {d.name}" for d in matches)
        )
    raise SystemExit(f"No project matches {project!r} under {REFERENCE_ROOT}")


def _print_human(inv, project_root: Path) -> None:
    print(f"Project: {project_root.name}")
    print(f"Scanned: {inv.scanned_at}")
    print(
        f"Total files: {inv.total_files}    "
        f".msg files: {inv.msg_count}    "
        f"extracted attachments: {inv.extracted_attachments}"
    )
    print()
    print(f"[root]  ({inv.root_file_count} files)")
    max_path_len = max((len(f.path) for f in inv.folders if f.path), default=0)
    for folder in inv.folders:
        if folder.path == "":
            continue
        print(f"  {folder.path.ljust(max_path_len)}  ({folder.file_count} files)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--project", help="Project name or ID prefix (relative to reference-material/)")
    g.add_argument("--project-path", help="Absolute or relative path to project folder")
    ap.add_argument("--save", action="store_true",
                    help="Write inventory JSON to {project}/validation/ai_inventory.json")
    ap.add_argument("--json", action="store_true",
                    help="Print full inventory as JSON to stdout (machine-readable)")
    ap.add_argument("--no-extract", action="store_true",
                    help="Skip .msg attachment extraction (faster re-runs when already materialized)")
    args = ap.parse_args()

    project_root = _resolve_project(args.project, args.project_path)

    inv = build_inventory(project_root, extract_attachments=not args.no_extract)

    if args.json:
        print(inv.model_dump_json(indent=2))
    else:
        _print_human(inv, project_root)

    if args.save:
        out = save_inventory(inv, project_root)
        if not args.json:
            print(f"\nSaved: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
