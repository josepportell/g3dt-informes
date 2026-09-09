#!/usr/bin/env python3
"""Peça 7b (2026-09-09): passa el lector de figures (`automation/imatges/lector_figures.py`) pels 7 projectes signats, amb
leave-one-out dels exemplars, sobre la MATEIXA carpeta que fa servir M341 (`_project_path`), i puntua cada tria contra la
veritat del pas 1 amb la mateixa mesura que M341 (`imatges_font.score_pair`: M phash ≤ 10 · C mateixa font · X). Desa la
selecció anterior a `validation/figure_selection.abans-lector.json` (M341 llegirà la del lector via `apply_selection`).

Ús:
  PYTHONPATH=$PWD .venv/bin/python docs/wizard-headless/mesures/llegir_figures_corpus.py <nom-run> [--projects a,b]
      [--model sonnet] [--effort medium] [--timeout 600] [--dry-run] [--ref-run 2026-09-08-m341-peca7a]
Sortida: `runs/<nom-run>/_LECTOR-FIGURES.md` + `<slug>.json`. Cost: UNA crida `claude -p` per projecte.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("mesura_341", HERE / "mesura_341.py")
M = importlib.util.module_from_spec(spec); sys.modules["mesura_341"] = M; spec.loader.exec_module(M)
import imatges_font as IF  # noqa: E402
from automation.imatges import lector_figures as LG  # noqa: E402

TRUTH_SLOT = {"assaigs": "fig_assaigs", "projecte": "fig_projecte", "situacio": "fig_situacio"}


def score(slug: str, project: Path, sel: dict, work: Path) -> dict[str, str]:
    """Per ranura: estat contra la millor figura de l'Eva de la mateixa ranura (M / C / X / sobrant / — )."""
    truths = [t for t in IF.truth_figures(slug) if t["slot"] in TRUTH_SLOT.values()]
    res: dict[str, str] = {}

    def best(slot_eva: str, img: Path) -> str:
        ts = [t for t in truths if t["slot"] == slot_eva]
        if not ts:
            return "sobrant (l'Eva no en posa)"
        rows = []
        for t in ts:
            r = IF.score_pair(t["path"], str(img), allow_reverse=True)
            rows.append((r["status"], r.get("phash_d"), r.get("ncc"), t["n"]))
        order = {"MATCH": 0, "CLOSE": 1, "MISMATCH": 2}
        rows.sort(key=lambda x: (order.get(x[0], 3), x[1] if x[1] is not None else 99))
        st, ph, ncc, n = rows[0]
        return {"MATCH": "M", "CLOSE": "C", "MISMATCH": "X"}.get(st, st) + f" (fig {n}, ph {ph}, ncc {ncc})"

    e = sel.get("assaigs")
    if e:
        p = work / "score_assaigs.jpg"
        res["assaigs"] = best("fig_assaigs", p) if LG.render_entry(project, e, p) else "ERR"
    else:
        res["assaigs"] = "—" if not any(t["slot"] == "fig_assaigs" for t in truths) else "ND (l'Eva en posa)"
    for k, e in enumerate(sel.get("projecte") or [], 1):
        p = work / f"score_projecte{k}.jpg"
        res[f"projecte{k}"] = best("fig_projecte", p) if LG.render_entry(project, e, p) else "ERR"
    n_proj = len([t for t in truths if t["slot"] == "fig_projecte"])
    if not sel.get("projecte"):
        res["projecte1"] = "—" if not n_proj else f"ND (l'Eva en posa {n_proj})"
    s = sel.get("situacio")
    if s:
        for k, crop in enumerate(s["crops"], 1):
            p = work / f"score_situacio{k}.jpg"
            res[f"situacio{k}"] = best("fig_situacio", p) if LG.render_entry(project, s, p, crop=crop) else "ERR"
    return res


def _write_table(run_dir: Path, a) -> None:
    L = [f"# Lector de figures — run `{run_dir.name}` (model {a.model or 'sonnet'}, effort {a.effort}, leave-one-out)", "",
         "| projecte | s | cand. | assaigs | projecte 1 | projecte 2 | situació | avisos |", "|---|--:|--:|---|---|---|---|---|"]
    for slug in M.NAMES:
        f = run_dir / f"{slug}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8")); sel = d.get("selection") or {}; sc = d.get("score") or {}

        def cell(e, key):
            if not e:
                return sc.get(key, "—")
            return f"{Path(e['rel']).name}{' p' + str(e['page']) if e.get('page') else ''} {'retall' if e.get('crop') or e.get('crops') else 'sencer'} → {sc.get(key, '')}"
        proj = sel.get("projecte") or []
        cells = [cell(sel.get("assaigs"), "assaigs"), cell(proj[0] if proj else None, "projecte1"),
                 cell(proj[1] if len(proj) > 1 else None, "projecte2"),
                 (cell(sel.get("situacio"), "situacio1") + " / " + sc.get("situacio2", "")) if sel.get("situacio") else "—"]
        if not sel:
            cells = [d.get("skipped") or d.get("error") or "?"] * 4
        L.append(f"| {slug} | {d.get('elapsed_s', '')} | {d.get('n_candidats', '')} | " + " | ".join(cells)
                 + f" | {'; '.join(d.get('warnings') or []) or '—'} |")
    (run_dir / "_LECTOR-FIGURES.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run"); ap.add_argument("--projects", default=",".join(M.NAMES)); ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="medium"); ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--projectes-dir", default="~/g3dt-e2e/projectes"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ref-run", default="2026-09-08-m341-peca7a", help="run de M341 d'on treure l'idioma de l'informe")
    a = ap.parse_args()
    run_dir = HERE / "runs" / a.run; run_dir.mkdir(parents=True, exist_ok=True)
    projectes = Path(a.projectes_dir).expanduser()
    todo = [s.strip() for s in a.projects.split(",") if s.strip()]
    for slug in todo:
        f = run_dir / f"{slug}.json"
        if f.exists():
            f.unlink()
    for slug in todo:
        project = M._project_path(M.NAMES[slug], projectes)
        lang = "ca"
        ctx_path = HERE / "runs" / a.ref_run / slug / "viaA" / "_context_usat.json"
        if ctx_path.exists():
            lang = json.loads(ctx_path.read_text(encoding="utf-8")).get("report_language") or "ca"
        summ = LG.run(project, exclude_slug=slug, model=a.model, effort=a.effort, timeout=a.timeout, dry_run=a.dry_run, lang=lang)
        summ["slug"] = slug; sel = summ.get("selection") or {}
        summ["score"] = score(slug, project, sel, project / "validation" / LG.SUBDIR) if sel else {}
        (run_dir / f"{slug}.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        sc = summ["score"]
        print(f"{slug:10s} {summ.get('elapsed_s', '')!s:>6} s  {summ.get('n_candidats')} cand.  "
              + "  ".join(f"{k}={v}" for k, v in sc.items()) if sel else f"{slug:10s} {summ.get('skipped') or summ.get('error')}", flush=True)
    _write_table(run_dir, a)
    print(f"\n{run_dir / '_LECTOR-FIGURES.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
