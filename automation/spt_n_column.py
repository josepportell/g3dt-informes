"""Columna «N» de la taula de característiques geotècniques: l'N30 de l'SPT del nivell.

Criteri de l'Eva, 7/7 informes signats (`docs/RECERCA-CRITERIS-DESCRITS-ALS-INFORMES-2026-09-03.md`
§«Bonus P1»; peça P0 de `docs/PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md`): la columna «N» ve
SEMPRE de l'assaig SPT del sondeig — «--» si al nivell no n'hi ha, «R» si l'SPT rebutja. MAI la
mitjana N20 del DPSH (aquesta és la columna «Nb», N20/0,83, que no es toca aquí).

Evidència (columna N de la taula signada, per nivell):
  Bell-lloc 54 · Rubí 40 (SPT-1 a P-3) · Castellar R · Linyola --/R · Alcoletge --/20 ·
  Anciles 6/-- (la MA-1 no té N30) · Vilanova 10/24 — dos SPT a la MATEIXA fondària (-0,80 a
  -1,40) a P-1 i P-3, assignats a nivells diferents per la litologia de la mostra.

Assignació d'un SPT a un nivell, en aquest ordre:
  1. litologia de la mostra contra la descripció de cada nivell (arrels de 5 lletres dels mots
     de 4 o més lletres, sense accents): el màxim ÚNIC guanya — és l'únic criteri que reprodueix
     Vilanova;
  2. fondària: l'únic nivell que conté el punt mig de «Prof. Extracció»;
  3. un sol nivell a l'informe: l'SPT hi va;
  4. si no: sense assignar → la cel·la queda «--» i s'anota l'avís. Mai s'inventa.
Les mostres sense N30 (MA, «--», buit) no són SPT i no compten. Diversos SPT al mateix nivell:
s'imprimeix el primer; si els valors difereixen, s'anota (Anciles en té dos iguals, 6 i 6).

Entrada: les files de la taula SPT/MA TAL COM S'IMPRIMEIXEN a l'informe (`context['spt_ma_tests']`:
lectura de la via A si n'hi ha, si no la fila única de la via B), de manera que la columna N i la
taula SPT/MA del mateix informe diuen sempre el mateix número.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

NO_SPT = "--"

_N30_RE = re.compile(r"^\s*(R|\d{1,3})\b", re.IGNORECASE)
_NUM_RE = re.compile(r"[+-]?\d+(?:[.,]\d+)?")
_WORD_RE = re.compile(r"[a-z]+")
# Arrels (5 lletres) massa genèriques per decidir un nivell: apareixen a qualsevol descripció.
_STOP_STEMS = frozenset({"nivel", "matri", "inter", "color", "algun", "punt", "trams", "amb"})


def n30_display(value: Any) -> str | None:
    """N30 imprimible («40», «R») o None si la fila NO és un SPT amb resultat.

    Accepta l'anotació del lector enganxada («R (rebuig)», «40 (suma dels trams
    centrals)»): a la cel·la hi va només el davanter. «--», buit, None o «MA» → None.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == NO_SPT:
        return None
    m = _N30_RE.match(text)
    if not m:
        return None
    token = m.group(1)
    return token.upper() if token.upper() == "R" else str(int(token))


def parse_depth_range(text: Any) -> tuple[float, float] | None:
    """«-1.00 a -1.20» → (1.0, 1.2), en valor absolut i ordenat; None si no hi ha cap número."""
    if text is None:
        return None
    nums = [abs(float(n.replace(",", "."))) for n in _NUM_RE.findall(str(text))]
    if not nums:
        return None
    if len(nums) == 1:
        return (nums[0], nums[0])
    a, b = nums[0], nums[1]
    return (min(a, b), max(a, b))


def _stems(text: Any) -> set[str]:
    if not text:
        return set()
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    out = set()
    for w in _WORD_RE.findall(s):
        if len(w) < 4:
            continue
        stem = w[:5]
        if stem not in _STOP_STEMS:
            out.add(stem)
    return out


def lithology_overlap(sample_lithology: Any, level_description: Any) -> int:
    """Nombre d'arrels compartides entre la litologia de la mostra i la del nivell."""
    return len(_stems(sample_lithology) & _stems(level_description))


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _row_depth_mid(row: dict) -> float | None:
    d_from, d_to = _get(row, "depth_from_m"), _get(row, "depth_to_m")
    if isinstance(d_from, (int, float)) and isinstance(d_to, (int, float)):
        return (abs(d_from) + abs(d_to)) / 2
    rng = parse_depth_range(_get(row, "depth_range"))
    if rng is None:
        return None
    return (rng[0] + rng[1]) / 2


def assign_spt_n30(spt_rows: Iterable[dict], levels: Iterable[Any]) -> tuple[dict[int, str], list[str]]:
    """Assigna l'N30 de cada SPT al seu nivell.

    `spt_rows`: files de la taula SPT/MA (claus `test_id`, `location`, `depth_range`
    o `depth_from_m`/`depth_to_m`, `n30`, `lithology`). `levels`: objectes o dicts
    amb `level_number`, `description`, `depth_from_m`, `depth_to_m` (None = obert).

    Retorna (`{level_number: «N»}`, avisos). Un nivell absent del dict no té SPT → «--».
    """
    lv = list(levels)
    if not lv:
        return {}, []
    numbers = [int(_get(l, "level_number", i + 1) or i + 1) for i, l in enumerate(lv)]
    descs = [_get(l, "description", "") or "" for l in lv]
    bounds: list[tuple[float, float]] = []
    for l in lv:
        d_from = _get(l, "depth_from_m", 0.0)
        d_to = _get(l, "depth_to_m", None)
        bounds.append((abs(float(d_from or 0.0)), float("inf") if d_to is None else abs(float(d_to))))

    assigned: dict[int, list[tuple[str, str]]] = {}
    notes: list[str] = []
    for row in spt_rows or []:
        if not isinstance(row, dict):
            continue
        n = n30_display(row.get("n30"))
        if n is None:
            continue  # MA o fila buida: no és un SPT amb resultat
        label = f"{row.get('test_id') or 'SPT'} ({row.get('location') or '?'})"
        target: int | None = None

        scores = [lithology_overlap(row.get("lithology"), d) for d in descs]
        best = max(scores) if scores else 0
        if best > 0 and scores.count(best) == 1:
            target = numbers[scores.index(best)]
        else:
            mid = _row_depth_mid(row)
            if mid is not None:
                containing = [numbers[i] for i, (lo, hi) in enumerate(bounds) if lo <= mid <= hi]
                if len(containing) == 1:
                    target = containing[0]
            if target is None and len(lv) == 1:
                target = numbers[0]

        if target is None:
            notes.append(f"SPT {label} sense nivell assignable (ni litologia ni fondària decideixen): "
                         f"N30 {n} no s'imprimeix a la columna N")
            continue
        assigned.setdefault(target, []).append((n, label))

    out: dict[int, str] = {}
    for num, items in assigned.items():
        out[num] = items[0][0]
        others = [f"{lab}: {val}" for val, lab in items[1:] if val != items[0][0]]
        if others:
            notes.append(f"Nivell {num}: diversos SPT amb N30 diferent ({items[0][1]}: {items[0][0]} imprès; "
                         + "; ".join(others) + ")")
    return out, notes
