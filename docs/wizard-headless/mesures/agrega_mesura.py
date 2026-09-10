#!/usr/bin/env python3
"""Agregat MECANIC de la mesura dels 8 (2026-09-03): suma els `TOTALS:` dels `_compare_escalars.txt` /
`_compare_taules.txt` de `runs/2026-09-03-mesura-8/{slug}/` i els mapa a les columnes de `_AGREGAT-8.md`.

`ledger.py` no serveix aqui: espera `runs/<label>/meta.json` + `escalars.txt`/`taules.txt` (un run = una carpeta);
la mesura dels 8 son 8 subcarpetes d'un sol run, sense `meta.json`.

Mapa veredicte → columna:  OK + FORA → OK · CAUTELA → CAND · BUIT → Blanc · ERR → ERR · ALERTA → ALERTA (a part:
prod mes confiat que l'or; es resol a ma contra el signat, `{slug}/_NOTES.md`) · NOU, ABSENT, NOMES_OR, VIOLACIO →
exclosos del denominador (es llisten). Tulipa no te veritat (or per casa): s'omet si no hi ha `TOTALS:`.

Us:  python3 docs/wizard-headless/mesures/agrega_mesura.py            # taula markdown a stdout
     python3 docs/wizard-headless/mesures/agrega_mesura.py --dir RUTA # una altra carpeta amb la mateixa estructura
     python3 docs/wizard-headless/mesures/agrega_mesura.py --sub _reconsolida-2026-09-05   # `{slug}/{sub}/_compare_*.txt`
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT = HERE / "runs" / "2026-09-03-mesura-8"
ORDER = ["castellar", "bell-lloc", "rubi", "linyola", "alcoletge", "vilanova", "anciles", "tulipa"]
COLS = ["OK", "CAND", "ALERTA", "Blanc", "ERR"]


def totals(path: Path) -> dict | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("TOTALS:"):
            try:
                return ast.literal_eval(line.split(":", 1)[1].strip())
            except Exception:
                return None
    return None


def mapped(t: dict) -> tuple[dict, dict]:
    m = {"OK": t.get("OK", 0) + t.get("FORA", 0), "CAND": t.get("CAUTELA", 0), "ALERTA": t.get("ALERTA", 0),
         "Blanc": t.get("BUIT", 0), "ERR": t.get("ERR", 0)}
    excl = {k: v for k, v in t.items() if k in ("NOU", "ABSENT", "NOMES_OR", "VIOLACIO")}
    return m, excl


def table(kind: str, root: Path, sub: str = "") -> list[str]:
    rows, tot = [], {c: 0 for c in COLS}
    for slug in ORDER:
        t = totals(root / slug / sub / f"_compare_{kind}.txt")
        if not t:
            rows.append(f"| {slug} | — | — | — | — | — | (sense TOTALS: sense veritat comparable) | — |")
            continue
        m, excl = mapped(t)
        n = sum(m.values())
        for c in COLS:
            tot[c] += m[c]
        pct = f"{100 * m['OK'] / n:.0f} %" if n else "—"
        ex = ", ".join(f"{k} {v}" for k, v in sorted(excl.items())) or "—"
        rows.append(f"| {slug} | {m['OK']} | {m['CAND']} | {m['ALERTA']} | {m['Blanc']} | **{m['ERR']}** | {ex} | {pct} |")
    n = sum(tot.values())
    rows.append(f"| **Total** | **{tot['OK']}** | **{tot['CAND']}** | **{tot['ALERTA']}** | **{tot['Blanc']}** | **{tot['ERR']}** | "
                f"| **{100 * tot['OK'] / n:.0f} %** ({n} cel·les) |")
    head = [f"**{kind.capitalize()}** (OK = OK + FORA · CAND = CAUTELA · Blanc = BUIT · exclosos: NOU, ABSENT, NOMES_OR, VIOLACIO):", "",
            "| Projecte | OK | CAND | ALERTA | Blanc | ERR | exclosos | OK % |", "|---|--:|--:|--:|--:|--:|---|--:|"]
    return head + rows + [""]


def main(argv: list[str]) -> int:
    root = Path(argv[argv.index("--dir") + 1]) if "--dir" in argv else DEFAULT
    sub = argv[argv.index("--sub") + 1] if "--sub" in argv else ""
    print(f"# Agregat mecànic — `{root.name}`" + (f" / `{sub}`" if sub else "") + "\n")
    for kind in ("escalars", "taules"):
        print("\n".join(table(kind, root, sub)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
