"""Fase 4 (via A, wizard headless) — normalitzacio suau abans de declarar invalid.

Vegeu `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` Fase 4 ("Normalitzacio
suau abans de declarar invalid", lliso del creuament de la Fase 0): la crida
`claude -p ... --consolida` es un productor cec — pot desviar-se en FORMA, no en
fons. `runner.py` (Fase 3) aplica aquestes DUES reparacions deterministes ABANS de
decidir si la sortida cau al mode degradat (`merge_degradat`, tambe a `runner.py`).
Cap altra reparacio: si despres d'aquestes dues `contract.validate_decisions`
encara dona errors, es degradat.

Aquest modul NO llegeix ni escriu cap fitxer (stdlib pur, sense I/O).
"""

from __future__ import annotations

import copy
from typing import Any


def soft_normalize(d: dict) -> dict:
    """Retorna una COPIA de `d` amb les dues reparacions suaus aplicades
    recursivament sobre `fields` i les rows/cel·les de `tables` (incloent
    cel·les niuades, p.ex. `n30.registre`).

    (a) Una cel·la amb `estat: "candidats"` on `value != candidates[0]["value"]`
        adopta `candidates[0]["value"]` com el seu `value` (es exactament el
        que la UI hauria de pre-omplir, Pas 5 del skill).
    (b) Una cel·la amb `estat` `segur` o `candidats`, `candidates` buit o
        absent, pero amb `font` i/o `quote` al nivell superior de la cel·la
        (el productor cec les hi ha deixat soltes en lloc d'embolcallar-les),
        s'embolcalla com `candidates = [{"value": ..., "font": ..., "quote": ...}]`.

    No es fa CAP altra reparacio (no s'inventa cap dada nova; nomes es
    reordena/embolcalla el que ja hi era a la cel·la). No muta `d`.
    """
    return _walk(copy.deepcopy(d))


def _walk(obj: Any) -> Any:
    if isinstance(obj, dict):
        if "estat" in obj:
            _repair_cell(obj)
        for key, value in list(obj.items()):
            obj[key] = _walk(value)
        return obj
    if isinstance(obj, list):
        return [_walk(item) for item in obj]
    return obj


def _repair_cell(cell: dict) -> None:
    """Aplica les reparacions (b) i (a), en aquest ordre, sobre una cel·la
    (`estat` + `value` + opcionalment `candidates`/`font`/`quote`)."""
    estat = cell.get("estat")
    if estat not in ("segur", "candidats"):
        return

    # (b) candidates buit/absent pero font/quote soltes al nivell superior.
    candidates = cell.get("candidates")
    if not candidates:
        font = cell.get("font")
        quote = cell.get("quote")
        if font is not None or quote is not None:
            candidates = [{"value": cell.get("value"), "font": font, "quote": quote}]
            cell["candidates"] = candidates

    # (a) candidats amb value que no coincideix amb candidates[0].value.
    if estat == "candidats" and candidates and isinstance(candidates[0], dict):
        first_value = candidates[0].get("value")
        if cell.get("value") != first_value:
            cell["value"] = first_value
