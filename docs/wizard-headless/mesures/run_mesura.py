#!/usr/bin/env python3
"""Driver de la mesura dels 8 (2026-09-03). Vegeu CRITERIS-MESURA-2026-09-03.md.

Ús (des de l'arrel del worktree g3dt-prod, .venv, G3DT_CACHE_DIR exportat):
    .venv/bin/python docs/wizard-headless/mesures/run_mesura.py "3001621 CASTELLAR DEL VALLES" castellar

El driver d'una sessió anterior vivia al scratchpad i es va perdre; aquest queda versionat.
"""
import json
import sys
import time
from pathlib import Path

from automation.lectura.runner import run_lectura

RUNS = Path(__file__).resolve().parent / "runs" / "2026-09-03-mesura-8"
PROJECTES = Path.home() / "g3dt-e2e" / "projectes"


def main() -> None:
    name = sys.argv[1]
    slug = sys.argv[2] if len(sys.argv) > 2 else name.split()[-1].lower()
    project = PROJECTES / name
    if not project.is_dir():
        sys.exit(f"projecte no trobat: {project}")
    out = RUNS / slug
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def ev(kind: str, data: dict) -> None:
        flat = {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool, type(None)))}
        print(json.dumps({"t": round(time.time() - t0, 1), "ev": kind, **flat}, ensure_ascii=False), flush=True)

    res = run_lectura(project, out_dir=out, on_event=ev)
    mins = (time.time() - t0) / 60
    summary = (
        f"DONE {name}: {mins:.1f} min, degraded={res.degraded}, mode={res.mode}, "
        f"decisions={'OK' if res.decisions else 'NONE'}, docs={len(res.per_doc)}"
    )
    print(summary, flush=True)
    (out / "_elapsed.txt").write_text(summary + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
