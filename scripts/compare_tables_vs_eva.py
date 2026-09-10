#!/usr/bin/env python3
"""Compara les taules-llista dels informes generats vs els informes signats d'Eva.

Cobreix l'espai NO mesurat pel comparador escalar (compare_prefills_vs_eva.py §3.4
del DIAGNOSTIC-PROD-2026-08-23): taules DPSH, sondeig, SPT/MA, mostra lab, nivells
de sòl, permeabilitat, sulfats, sísmica i característiques geotècniques.

Alineació de taules per empremta de capçalera (els índexs NO coincideixen entre
generat i Eva: l'informe d'Eva té 11-14 taules segons el projecte). Alineació de
files per clau (P-1, S-1, SPT-1, "1er nivell", …) quan n'hi ha.

Veritat d'Eva:
  - .docx directe (Bell-lloc, Castellar, Rubí, Linyola)
  - .doc convertit amb soffice (Alcoletge) — passar la ruta convertida
  - JSON transcrit a mà des del PDF amb capa de text (Vilanova, Anciles):
    {"tables": [{"type": "dpsh", "grid": [[...], ...]}, ...]}

Ús:
  compare_tables_vs_eva.py GENERATED.docx EVA.docx|EVA.json [--json OUT] [--tag NOM]

Només lectura sobre les dades; no toca res de /mnt/c.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from docx import Document

# ---------------------------------------------------------------- tipus de taula

# type -> (regex sobre la primera cel·la no buida, files de capçalera a saltar)
TABLE_TYPES = [
    ("plantes", re.compile(r"^Nº de plantes"), 0),
    ("cte_edificacio", re.compile(r"^Tipus d.edificació"), 0),
    ("dpsh", re.compile(r"^Penetròmetres dinàmics"), 2),
    ("sondeig", re.compile(r"^Sondeig a rotació"), 2),
    ("spt_ma", re.compile(r"^Assaigs SPT"), 2),
    ("mostra_lab", re.compile(r"^Mostra\s*:"), 0),
    ("soil_levels", re.compile(r"^1e?r nivell"), 0),
    ("permeabilitat", re.compile(r"^Nivell$"), 1),  # desambiguat per capçalera fila 0
    ("sulfats", re.compile(r"^Nivell$"), 1),
    ("sismica", re.compile(r"^Nivells$"), 1),
    ("geotecnica", re.compile(r"^Nivell$"), 1),
]


def _grid(table) -> list[list[str]]:
    return [[c.text.strip() for c in row.cells] for row in table.rows]


def classify_table(grid: list[list[str]]) -> str | None:
    first = next((c for row in grid for c in row if c), None)
    if first is None:
        return None
    if first == "Nivell" and grid:
        hdr = " ".join(grid[0])
        if "K (m/s)" in hdr:
            return "permeabilitat"
        if "sulfats" in hdr:
            return "sulfats"
        if "Nb" in hdr:
            return "geotecnica"
        return None
    for name, rx, _ in TABLE_TYPES:
        if rx.search(first):
            return name
    return None


HEADER_ROWS = {name: nh for name, _, nh in TABLE_TYPES}


def extract_tables(path: Path) -> dict[str, list[list[str]]]:
    """Retorna {tipus: grid} de la primera taula de cada tipus del document."""
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return {t["type"]: t["grid"] for t in data["tables"]}
    out: dict[str, list[list[str]]] = {}
    for table in Document(str(path)).tables:
        grid = _grid(table)
        kind = classify_table(grid)
        if kind and kind not in out:
            out[kind] = grid
    return out


# ---------------------------------------------------------------- normalització

_APOS = str.maketrans({"’": "'", "‘": "'", "º": "°", "–": "-", "—": "-", " ": " "})


def _norm(s: str) -> str:
    s = (s or "").translate(_APOS)
    s = re.sub(r"\s+", " ", s).strip()
    return s


_NUM_RX = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
#: «1.284» / «1.655,01» (Taula 1, superfícies): milers amb punt i decimals amb coma (bloc 2, 2026-09-07). Abans «1.167»
#: (imprès) contra «1167» (signat) es llegia 1,167 ≠ 1167 → MISMATCH. Només grups de tres xifres exactes.
_THOUSANDS_RX = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?$")


def _as_num(s: str):
    s = s.strip()
    if _THOUSANDS_RX.match(s):
        s = s.replace(".", "")
    s = s.replace(",", ".").replace("+", "").strip()
    if _NUM_RX.match(s):
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _num_seq(s: str) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"[+-]?\d+(?:[.,]\d+)?", s)]


def classify_cell(gen: str, eva: str) -> str:
    g, e = _norm(gen), _norm(eva)
    if g == e:
        return "MATCH"
    if not g and not e:
        return "MATCH"
    if not g or not e:
        return "MISMATCH"
    lg, le = g.lower(), e.lower()
    if lg == le or lg.replace("sí", "si") == le.replace("sí", "si"):
        return "MATCH"
    # números: iguals amb format diferent = MATCH; diferents = MISMATCH
    ng, ne = _as_num(g), _as_num(e)
    if ng is not None and ne is not None:
        return "MATCH" if abs(ng - ne) < 1e-9 else "MISMATCH"
    # seqüències numèriques (rangs "-1.0 a 1.60", "41-R", "10^-2 a 10^-4")
    sg, se = _num_seq(g), _num_seq(e)
    stripped_g = re.sub(r"[+-]?\d+(?:[.,]\d+)?", "#", lg)
    stripped_e = re.sub(r"[+-]?\d+(?:[.,]\d+)?", "#", le)
    if sg and se and (sg == se or [abs(x) for x in sg] == [abs(x) for x in se]):
        return "MATCH" if stripped_g == stripped_e else "CLOSE"
    if sg and se and stripped_g == stripped_e:
        return "MISMATCH"  # mateix text, números diferents (p. ex. «T-2» vs «T-1»)
    if lg in le or le in lg:
        return "CLOSE"
    r = difflib.SequenceMatcher(None, lg, le).ratio()
    return "MATCH" if r >= 0.92 else ("CLOSE" if r >= 0.6 else "MISMATCH")


# ---------------------------------------------------------------- alineació files

_KEY_RX = re.compile(r"^(P-\d+|S-\d+|SPT-\d+|MA-\d+|\d+|1e?r|2n|2on|3e?r|4t|5è)\b", re.I)


def _row_key(row: list[str]) -> str | None:
    m = _KEY_RX.match(_norm(row[0]))
    return m.group(1).lower().replace("2on", "2n").replace("3er", "3r").replace("1er", "1r") if m else None


def _dedupe(row: list[str]) -> list[str]:
    """Les files-títol fusionades repeteixen la mateixa cel·la; les col·lapsem."""
    out = [row[0]]
    for c in row[1:]:
        if c != out[-1] or c == "":
            out.append(c)
    return out


def compare_table(kind: str, gen: list[list[str]], eva: list[list[str]]):
    nh = HEADER_ROWS.get(kind, 0)
    g_rows, e_rows = gen[nh:], eva[nh:]
    cells: list[dict] = []
    counts: Counter = Counter()

    g_keyed = {k: r for r in g_rows if (k := _row_key(r))}
    e_keyed = {k: r for r in e_rows if (k := _row_key(r))}
    use_keys = len(g_keyed) == len(g_rows) and len(e_keyed) == len(e_rows) and g_keyed and e_keyed

    if use_keys:
        keys = list(dict.fromkeys(list(g_keyed) + list(e_keyed)))
        pairs = [(k, g_keyed.get(k), e_keyed.get(k)) for k in keys]
    else:
        n = max(len(g_rows), len(e_rows))
        pairs = [
            (f"fila{i}", g_rows[i] if i < len(g_rows) else None, e_rows[i] if i < len(e_rows) else None)
            for i in range(n)
        ]

    for key, gr, er in pairs:
        if gr is None:
            counts["ROW_MISSING"] += 1
            cells.append({"row": key, "col": "*", "estat": "ROW_MISSING", "eva": " | ".join(_dedupe(er))})
            continue
        if er is None:
            counts["ROW_EXTRA"] += 1
            cells.append({"row": key, "col": "*", "estat": "ROW_EXTRA", "gen": " | ".join(_dedupe(gr))})
            continue
        gd, ed = _dedupe(gr), _dedupe(er)
        for j in range(max(len(gd), len(ed))):
            gc = gd[j] if j < len(gd) else ""
            ec = ed[j] if j < len(ed) else ""
            if not _norm(gc) and not _norm(ec):
                continue
            estat = classify_cell(gc, ec)
            counts[estat] += 1
            if estat != "MATCH":
                cells.append({"row": key, "col": j, "estat": estat, "gen": gc, "eva": ec})
            else:
                cells.append({"row": key, "col": j, "estat": estat})
    return counts, cells


# ---------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__)
        return 1
    gen_path, eva_path = Path(args[0]), Path(args[1])
    tag = argv[argv.index("--tag") + 1] if "--tag" in argv else gen_path.stem
    out_json = Path(argv[argv.index("--json") + 1]) if "--json" in argv else None

    gen_tables = extract_tables(gen_path)
    eva_tables = extract_tables(eva_path)

    report = {"tag": tag, "generated": str(gen_path), "eva": str(eva_path), "tables": {}}
    total: Counter = Counter()
    print(f"\n## {tag}")
    print("| taula | MATCH | CLOSE | MISMATCH | files ±extra/−absents | detall no-MATCH |")
    print("|---|--:|--:|--:|---|---|")
    for kind, *_ in TABLE_TYPES:
        if kind in ("permeabilitat", "sulfats", "sismica", "geotecnica") and kind not in gen_tables and kind not in eva_tables:
            continue
        g, e = gen_tables.get(kind), eva_tables.get(kind)
        if g is None and e is None:
            continue
        if g is None or e is None:
            who = "generat" if g is None else "Eva"
            print(f"| {kind} | | | | **absent a {who}** | |")
            report["tables"][kind] = {"estat": f"ABSENT_{who}"}
            total["TABLE_ABSENT"] += 1
            continue
        counts, cells = compare_table(kind, g, e)
        total.update(counts)
        report["tables"][kind] = {"counts": dict(counts), "cells": cells}
        diffs = "; ".join(
            f"{c['row']}[{c['col']}] {c['estat'][:4]} «{c.get('gen','')}»↔«{c.get('eva','')}»"
            for c in cells if c["estat"] != "MATCH"
        )[:400]
        rows_note = []
        if counts["ROW_EXTRA"]:
            rows_note.append(f"+{counts['ROW_EXTRA']} extra")
        if counts["ROW_MISSING"]:
            rows_note.append(f"−{counts['ROW_MISSING']} absents")
        print(f"| {kind} | {counts['MATCH']} | {counts['CLOSE']} | {counts['MISMATCH']} | {', '.join(rows_note)} | {diffs} |")
    comp = total["MATCH"] + total["CLOSE"] + total["MISMATCH"]
    pct = 100 * (total["MATCH"] + total["CLOSE"]) / comp if comp else 0
    print(f"\n**{tag}: {total['MATCH']} MATCH · {total['CLOSE']} CLOSE · {total['MISMATCH']} MISMATCH · "
          f"{total['ROW_EXTRA']} files extra · {total['ROW_MISSING']} files absents → {pct:.0f} % (M+C)/comparables**")
    report["totals"] = dict(total)

    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
