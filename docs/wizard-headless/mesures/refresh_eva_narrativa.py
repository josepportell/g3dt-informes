#!/usr/bin/env python3
"""Refresc QUIRÚRGIC de la veritat narrativa (`eva_reference_values.json`) dels 7 projectes.

Per què no una re-extracció sencera: l'extractor de referència (`automation/reference_extractor.py`) ha derivat
respecte de la plantilla en variables que NO són narrativa (2026-09-06: `spt_*` cauen a None a Bell-lloc, les dates
canvien de nom amb la segona variable de data del 2026-09-05). Re-escriure tot el JSON mouria els grups A i calc de
M341 i no podríem aïllar l'efecte de la peça de narrativa. Aquí es re-extreu en memòria i només s'apliquen les claus
de la llista blanca (grup `narr` de `mesura_341.py` + `location_sentence`): la resta del JSON queda com era.

Ús:
  PYTHONPATH=$PWD .venv/bin/python docs/wizard-headless/mesures/refresh_eva_narrativa.py            # només informa
  PYTHONPATH=$PWD .venv/bin/python docs/wizard-headless/mesures/refresh_eva_narrativa.py --apply    # escriu els JSON
  [--projects castellar,rubi] [--all-keys] [--drop clau1,clau2] [--keys all|clau1,clau2]
  (--all-keys: informa de TOTES les diferències, no n'aplica cap més; --drop: elimina claus que la plantilla ja no té;
   --keys: bloc 3 (2026-09-07) — amplia la llista blanca a TOTES les claus (`all`) o a les indicades: amb --apply
   s'escriuen també les claus dels grups A i calc; la nota del JSON diu quines)

Necessita el signat a `reference-material/<projecte>/` (Alcoletge i Anciles: copiats el 2026-09-06, ignorats pel git).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mesura_341 as M  # noqa: E402
from automation import reference_extractor as RE  # noqa: E402

ALLOW = set(M.GROUPS["narr"]) | M.NARR_SLOT_EXTRA


def _val(e):
    return e.get("value") if isinstance(e, dict) else e


def refresh(slug: str, apply: bool, all_keys: bool, drop: set[str],
            keys: set[str] | None = None, label: str = "") -> list[tuple[str, object, object, bool]]:
    allow_all = keys is not None and "all" in keys
    allow = ALLOW | (keys or set())
    project = REPO / "reference-material" / M.NAMES[slug]
    out_file = project / "validation" / "eva_reference_values.json"
    ref = RE.find_reference_report(project)
    if ref is None:
        print(f"{slug}: sense signat a {project}")
        return []
    res = RE.extract_reference_values(ref, project_name=project.name)
    RE._merge_with_prior(res, out_file)      # conserva les entrades externes (`intelligent_analysis`), com l'extractor
    new_vars = {k: RE.asdict(v) for k, v in res.variables.items()}
    old = json.loads(out_file.read_text(encoding="utf-8"))
    old_vars = old["variables"]
    diffs = []
    for k in sorted(set(old_vars) | set(new_vars)):
        a, b = _val(old_vars.get(k)), _val(new_vars.get(k))
        if a != b:
            diffs.append((k, a, b, allow_all or k in allow))
    for k in drop:
        if k in old_vars:
            diffs.append((k, _val(old_vars[k]), None, True))
    if apply:
        changed = 0
        for k, a, b, allowed in diffs:
            if not allowed:
                continue
            if k in new_vars and k not in drop:
                old_vars[k] = new_vars[k]
            else:
                old_vars.pop(k, None)
            changed += 1
        if changed:
            applied = sorted(k for k, _a, _b, ok in diffs if ok)
            old.setdefault("notes", []).append(
                (f"refresh_eva_narrativa.py {label} (--keys): {changed} claus re-extretes: {', '.join(applied)}"
                 if keys else f"refresh_eva_narrativa.py 2026-09-06: {changed} claus narratives re-extretes (prefix primer)")
                + (f"; eliminades {sorted(drop)}" if drop else ""))
            out_file.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return diffs if all_keys else [d for d in diffs if d[3]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all-keys", action="store_true")
    ap.add_argument("--projects", default=",".join(M.NAMES))
    ap.add_argument("--drop", default="", help="claus a eliminar del JSON (p. ex. les que la plantilla ja no té)")
    ap.add_argument("--keys", default="", help="amplia la llista blanca: `all` o claus separades per comes (bloc 3)")
    ap.add_argument("--label", default="2026-09-07 (bloc 3)", help="etiqueta de la nota al JSON quan s'aplica amb --keys")
    args = ap.parse_args()
    logging.basicConfig(level=logging.ERROR)
    for slug in [s.strip() for s in args.projects.split(",") if s.strip()]:
        diffs = refresh(slug, args.apply, args.all_keys, {k.strip() for k in args.drop.split(",") if k.strip()},
                        keys={k.strip() for k in args.keys.split(",") if k.strip()} or None, label=args.label)
        print(f"=== {slug}: {len(diffs)} diferència(es){' APLICADES (llista blanca)' if args.apply else ''}")
        for k, a, b, allowed in diffs:
            tag = "aplicable" if allowed else "ALTRES (no s'aplica)"
            print(f"  [{tag}] {k}:\n      abans: {str(a)[:110]!r}\n      ara:   {str(b)[:110]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
