#!/usr/bin/env python3
"""Reconsolida els 7 projectes comparables de la mesura dels 8 amb el consolidador ACTUAL, a partir de les lectures
cachejades del run (cap crida LLM nova), escriu `{slug}/<sub>/_decisions.json` + `_compare_*.txt` i llista les
cel·les que canvien respecte d'una subcarpeta de referència. És la manera de mesurar un canvi del consolidador a cost 0
(DECISION-LOG 2026-09-05, decisió 7).

Des de T2 (2026-09-06) el defecte del runner és `G3DT_LECTURA_CONSOLIDA=python` i aquest script fa el mateix: NO fusiona
la passada `_consolida_only.json` cachejada. `--amb-llm` la fusiona sobre els conflictes actuals (com feien les mesures
fins a `_reconsolida-2026-09-05-v19`, que la porten dins: `llm_only_fields: True`).

Ús (des de l'arrel del worktree, `PYTHONPATH=$PWD G3DT_CACHE_DIR=… .venv/bin/python …`):
    docs/wizard-headless/mesures/reconsolida_mesura.py <sub_nou> [<sub_referència>] [--amb-llm]
    docs/wizard-headless/mesures/reconsolida_mesura.py _reconsolida-2026-09-06-t2 _reconsolida-2026-09-05-v19
Sense referència, compara amb `{slug}/_decisions.json` (el run original).
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

logging.disable(logging.CRITICAL)
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from automation.lectura.consolidate import consolidate_python, merge_only_fields, conflict_paths  # noqa: E402

RUNS = HERE / "runs" / "2026-09-03-mesura-8"
PROJECTES = Path.home() / "g3dt-e2e" / "projectes"
COMPARE = REPO / "docs/wizard-headless/fase0-acceptacio/compare_consolida.py"
NAMES = {"castellar": "3001621 CASTELLAR DEL VALLES", "bell-lloc": "4001612 BELL-LLOC", "rubi": "3001631 RUBI",
         "linyola": "4001607 LINYOLA", "alcoletge": "4001670 ALCOLETGE", "vilanova": "4001671 VILANOVA DE SEGRIA",
         "anciles": "4001679 ANCILES"}
BLOCKS = ("dpsh_tests", "sondeig_tests", "spt_ma_tests", "soil_levels")


def _cells(d: dict) -> dict[str, tuple]:
    out = {}
    for k, c in d["fields"].items():
        out[f"fields.{k}"] = (c.get("estat"), str(c.get("value")))
    for block in BLOCKS:
        for i, r in enumerate((d["tables"].get(block) or {}).get("rows") or []):
            for k, c in r.items():
                if isinstance(c, dict) and "estat" in c:
                    out[f"tables.{block}[{i}].{k}"] = (c.get("estat"), str(c.get("value")))
    return out


def main(argv: list[str]) -> int:
    amb_llm = "--amb-llm" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    sub = args[0]
    ref = args[1] if len(args) > 1 else ""
    for slug, name in NAMES.items():
        run = RUNS / slug
        d = consolidate_python(run, project_path=PROJECTES / name, project_name=name)
        llm_p = run / "_consolida_only.json"
        if amb_llm and llm_p.exists():
            d, _ = merge_only_fields(d, json.loads(llm_p.read_text(encoding="utf-8")), conflict_paths(d))
        out = run / sub
        out.mkdir(exist_ok=True)
        (out / "_decisions.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        for kind in ("escalars", "taules"):
            res = subprocess.run([sys.executable, str(COMPARE), kind, str(out / "_decisions.json"), name],
                                 capture_output=True, text=True)
            (out / f"_compare_{kind}.txt").write_text(res.stdout + res.stderr, encoding="utf-8")
        before = _cells(json.loads((run / ref / "_decisions.json").read_text(encoding="utf-8")))
        after = _cells(d)
        diffs = [(k, before.get(k), after.get(k)) for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)]
        print(f"{slug}: {len(diffs)} cel·les canvien respecte de {ref or 'el run original'}")
        for k, b, a in diffs:
            print(f"    {k}: {b} → {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
