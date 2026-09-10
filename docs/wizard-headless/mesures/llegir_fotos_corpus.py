#!/usr/bin/env python3
"""Peça 2 (2026-09-07): passa el lector de fotos (`automation/imatges/lector_fotos.py`) pels 7 projectes signats, amb
leave-one-out dels exemplars, sobre la MATEIXA carpeta que fa servir M341 (`_project_path`), i puntua cada tria contra
la veritat del pas 1 (phash ≤ 10 amb la foto de l'Eva del mateix forat). Desa la selecció anterior a
`validation/photo_selection.abans-lector.json` (M341 llegirà la del lector; l'Eva, `user`, sempre mana al generador).

Ús:
  PYTHONPATH=$PWD .venv/bin/python docs/wizard-headless/mesures/llegir_fotos_corpus.py <nom-run> [--projects a,b] [--model sonnet]
      [--effort medium] [--timeout 420] [--dry-run]
Sortida: `runs/<nom-run>/_LECTOR-FOTOS.md` + `<slug>.json` (resum per projecte). Cost: UNA crida `claude -p` per projecte.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import imagehash
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
spec = importlib.util.spec_from_file_location("mesura_341", HERE / "mesura_341.py")
M = importlib.util.module_from_spec(spec); sys.modules["mesura_341"] = M; spec.loader.exec_module(M)
from automation.imatges import lector_fotos as LF  # noqa: E402

TRUTH_SLOT = {"site_1": "foto_vista", "site_2": "foto_vista", "dpsh": "foto_dpsh", "sondeig": "foto_sondeig", "materials": "foto_materials"}


def _truth_photos(slug: str) -> dict[str, list[tuple[str, str]]]:
    """ranura → [(fitxer, phash)] de les fotos de l'Eva al signat."""
    out: dict[str, list] = {}
    idx = LF.TRUTH_IDX / slug / "index.json"
    if not idx.exists():
        return out
    for im in json.loads(idx.read_text(encoding="utf-8"))["images"]:
        if im.get("slot", "").startswith("foto_") and not im.get("static_of"):
            p = LF.TRUTH_IMG / slug / im["file"]
            if p.exists():
                ph = str(imagehash.phash(ImageOps.exif_transpose(Image.open(p)).convert("RGB")))
                out.setdefault(im["slot"], []).append((im["file"], ph))
    return out


def score(slug: str, project: Path, selection: dict) -> dict[str, str]:
    truth = _truth_photos(slug); res = {}
    for slot in LF.SLOTS:
        rel = selection.get(slot); tslot = TRUTH_SLOT[slot]
        if not rel:
            res[slot] = "—" if not truth.get(tslot) else "ND (l'Eva en posa)"
            continue
        try:
            ph = imagehash.phash(ImageOps.exif_transpose(Image.open(project / rel)).convert("RGB"))
        except Exception:
            res[slot] = "ERR"; continue
        ds = [ph - imagehash.hex_to_hash(t[1]) for t in truth.get(tslot, [])]
        if not ds:
            res[slot] = "sobrant (l'Eva no en posa)"
        elif min(ds) <= LF.PHASH_MAX:
            res[slot] = f"= Eva (ph {min(ds)})"
        else:
            res[slot] = f"≠ Eva (ph {min(ds)})"
    return res


def _write_table(run_dir: Path, a) -> None:
    """Taula del run des dels `<slug>.json` que hi hagi (l'execució pot anar per lots)."""
    L = [f"# Lector de fotos — run `{run_dir.name}` (model {a.model or 'sonnet'}, effort {a.effort}, leave-one-out)", "",
         "| projecte | s | site_1 | site_2 | dpsh | sondeig | materials | avisos |", "|---|--:|---|---|---|---|---|---|"]
    for slug in M.NAMES:
        f = run_dir / f"{slug}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8")); sel = d.get("selection") or {}; sc = d.get("score") or {}
        cells = [f"{Path(sel[s]).name if sel.get(s) else '—'} → {sc.get(s, '')}" if sel else (d.get("skipped") or d.get("error") or "?") for s in LF.SLOTS]
        L.append(f"| {slug} | {d.get('elapsed_s', '')} | " + " | ".join(cells) + f" | {'; '.join(d.get('warnings') or []) or '—'} |")
    (run_dir / "_LECTOR-FOTOS.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run"); ap.add_argument("--projects", default=",".join(M.NAMES)); ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="medium"); ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("--projectes-dir", default="~/g3dt-e2e/projectes"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ref-run", default="2026-09-07-m341-peca1b", help="run de M341 d'on treure `has_sondeig` del context (el que sap el wizard)")
    a = ap.parse_args()
    run_dir = HERE / "runs" / a.run; run_dir.mkdir(parents=True, exist_ok=True)
    projectes = Path(a.projectes_dir).expanduser()
    todo = [s.strip() for s in a.projects.split(",") if s.strip()]
    for slug in todo:                                   # es pot cridar per lots (el segon pla talla als 10 min): els JSON ja fets es reaprofiten
        f = run_dir / f"{slug}.json"
        if f.exists():
            f.unlink()
    for slug in todo:
        project = M._project_path(M.NAMES[slug], projectes)
        t0 = time.monotonic()
        has_sondeig = None
        ctx_path = HERE / "runs" / a.ref_run / slug / "viaA" / "_context_usat.json"
        if ctx_path.exists():
            has_sondeig = bool(json.loads(ctx_path.read_text(encoding="utf-8")).get("has_sondeig"))
        summ = LF.run(project, exclude_slug=slug, model=a.model, effort=a.effort, timeout=a.timeout, dry_run=a.dry_run,
                      has_sondeig=has_sondeig)
        summ["slug"] = slug; sel = summ.get("selection") or {}
        sc = score(slug, project, sel) if sel else {}
        summ["score"] = sc
        (run_dir / f"{slug}.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"{slug:10s} {summ.get('elapsed_s', '')!s:>6} s  " + "  ".join(f"{s}={sc.get(s, '')}" for s in LF.SLOTS) if sel else f"{slug:10s} {summ.get('skipped') or summ.get('error')}", flush=True)
    _write_table(run_dir, a)
    print(f"\n{run_dir / '_LECTOR-FOTOS.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
