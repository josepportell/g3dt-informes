#!/usr/bin/env python3
"""Acceptació Fase 12: consolidació Python-first sobre perdoc ja llegits, contra l'or.

Per a cada joc de `{doc}.json` (runs del llibre + workspaces E2E) executa
`consolidate_python`, valida el contracte, passa `compare_consolida.py`
(escalars + taules) i compara cel·la a cel·la amb el veredicte de la
consolidació LLM de referència del mateix joc (`escalars.txt`/`taules.txt`
del run): una cel·la "per sota" = veredicte pitjor (OK > CAUTELA > resta).

Ús:  .venv/bin/python docs/wizard-headless/fase12-consolida/harness.py [--write DIR] [--only LABEL]
Cap crida LLM. Sortida: resum per joc + cel·les per sota; amb --write desa els
`_decisions.json` i els .txt del comparador a DIR/<label>/.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from automation.lectura.consolidate import consolidate_python  # noqa: E402
from automation.lectura.contract import validate_decisions  # noqa: E402

RUNS = REPO / "docs/wizard-headless/mesures/runs"
E2E = Path.home() / "g3dt-e2e/projectes"
COMPARE = REPO / "docs/wizard-headless/fase0-acceptacio/compare_consolida.py"
CASTELLAR = "3001621 CASTELLAR DEL VALLES"
BELLLOC = "4001612 BELL-LLOC"

SETS = [
    # label, perdoc dir, project folder (for COORDENADES/expedient), gold project, reference verdict files dir
    ("sonnet-v2-c3", RUNS / "2026-08-25-preext-v2-c3/perdoc", E2E / CASTELLAR, CASTELLAR, RUNS / "2026-08-25-preext-v2-c3/consolida2"),
    ("fable-v2-c3", RUNS / "2026-08-25-fable-preext-v2-c3/perdoc", E2E / CASTELLAR, CASTELLAR, RUNS / "2026-08-25-fable-preext-v2-c3"),
    ("opus48-v2-c3", RUNS / "2026-08-25-opus48-high-preext-v2-c3/perdoc", E2E / CASTELLAR, CASTELLAR, RUNS / "2026-08-25-opus48-high-preext-v2-c3"),
    ("sonnet-c3-v13", RUNS / "2026-08-24-sonnet-c3/perdoc", E2E / CASTELLAR, CASTELLAR, RUNS / "2026-08-24-sonnet-c3"),
    ("belloc-ws-v12", E2E / BELLLOC / "validation/lectura", E2E / BELLLOC, BELLLOC, None),
]

RANK = {"OK": 0, "CAUTELA": 1, "ALERTA": 2, "ERR": 2, "ABSENT": 2, "NOU": 0, "VIOLACIO": 3, "BUIT": 1, "FORA": 0}
_LINE = re.compile(r"^(OK|CAUTELA|ALERTA|ERR|ABSENT|NOU|VIOLACIO|BUIT|FORA)\s+(\S+)")


def parse_verdicts(text: str) -> dict[str, tuple[str, str]]:
    out = {}
    for line in text.splitlines():
        m = _LINE.match(line)
        if m:
            out[m.group(2)] = (m.group(1), line[m.end():].strip())
    return out


def run_compare(kind: str, decisions: Path, gold_proj: str) -> str:
    r = subprocess.run([sys.executable, str(COMPARE), kind, str(decisions), gold_proj], capture_output=True, text=True)
    return r.stdout + r.stderr


def totals(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith("TOTALS:"):
            return eval(line.split(":", 1)[1].strip())  # noqa: S307 — literal dict del comparador
    return {}


def main() -> int:
    write_dir = None
    only = None
    args = sys.argv[1:]
    if "--write" in args:
        write_dir = Path(args[args.index("--write") + 1])
    if "--only" in args:
        only = args[args.index("--only") + 1]
    for label, perdoc, proj, gold_proj, ref in SETS:
        if only and only != label:
            continue
        if not perdoc.exists():
            print(f"== {label}: perdoc absent ({perdoc})")
            continue
        tmp = Path(tempfile.mkdtemp(prefix=f"f12-{label}-"))
        for p in perdoc.glob("*.json"):
            if p.name in ("_decisions.json", "_job.json", "_consolida_only.json"):
                continue
            shutil.copy(p, tmp / p.name)
        dec = consolidate_python(tmp, proj if proj.exists() else None, project_name=gold_proj)
        errors = validate_decisions(dec)
        out = tmp / "_decisions.json"
        out.write_text(json.dumps(dec, ensure_ascii=False, indent=1), encoding="utf-8")
        esc = run_compare("escalars", out, gold_proj)
        tau = run_compare("taules", out, gold_proj)
        print(f"\n===== {label}  ({len(dec['sources_read'])} fonts, {dec['consolidation']['elapsed_s']} s, "
              f"{dec['consolidation']['n_conflicts']} conflictes, contracte: {'NET' if not errors else errors[:3]})")
        print("ESCALARS", totals(esc))
        print("TAULES  ", totals(tau))
        mine = parse_verdicts(esc) | parse_verdicts(tau)
        for path, (v, msg) in sorted(mine.items()):
            if v != "OK":
                print(f"  {v:8s} {path:40s} {msg[:110]}")
        if dec["conflicts"]:
            print("  CONFLICTES:", [c["path"] for c in dec["conflicts"]])
        if ref and ref.exists():
            ref_v = parse_verdicts((ref / "escalars.txt").read_text()) | parse_verdicts((ref / "taules.txt").read_text())
            below = []
            above = []
            for path, (v, _) in mine.items():
                rv = ref_v.get(path, ("OK", ""))[0]
                if RANK[v] > RANK[rv]:
                    below.append((path, rv, v))
                elif RANK[v] < RANK[rv]:
                    above.append((path, rv, v))
            for path, (rv, _) in ref_v.items():
                if path not in mine and rv != "OK":
                    above.append((path, rv, "OK"))
            print(f"  vs referència {ref.name}: {len(below)} per sota, {len(above)} per sobre")
            for b in below:
                print(f"    PER SOTA  {b[0]:40s} ref={b[1]} python={b[2]}")
            for a in above:
                print(f"    per sobre {a[0]:40s} ref={a[1]} python={a[2]}")
        if write_dir:
            d = write_dir / label
            d.mkdir(parents=True, exist_ok=True)
            shutil.copy(out, d / "_decisions.json")
            (d / "escalars.txt").write_text(esc, encoding="utf-8")
            (d / "taules.txt").write_text(tau, encoding="utf-8")
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
