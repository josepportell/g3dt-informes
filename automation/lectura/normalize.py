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


def _soft_normalize_ab(d: dict) -> dict:
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


# --- Reparacio (c): alies de claus de fila de `tables` -> claus canoniques (skill v1.3) ---
ROW_KEY_ALIASES: dict[str, dict[str, str]] = {
    "dpsh_tests": {"cota": "cota_inici", "profunditat": "profunditat_assolida", "nf": "nivell_freatic"},
    "sondeig_tests": {"punt": "sondeig", "cota_inici": "cota", "profunditat": "profunditat_assolida", "nf": "nivell_freatic"},
    "spt_ma_tests": {"prof_extraccio": "profunditat", "fondaria": "profunditat", "profunditat_extraccio": "profunditat",
                     "mostra": "id", "sondeig": "punt", "litologia_candidats": "litologia"},
    "soil_levels": {"litologia_candidats": "litologia", "nivell": "nom", "desde": "de", "fins": "a"},
}
ROW_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "dpsh_tests": ("punt", "cota_inici", "profunditat_assolida", "rebuig", "nivell_freatic"),
    "sondeig_tests": ("sondeig", "cota", "profunditat_assolida", "spt_ma", "nivell_freatic"),
    "spt_ma_tests": ("id", "punt", "profunditat", "n30"),  # litologia recomanada, no obligatoria (or Anciles no la porta)
    "soil_levels": ("nom", "litologia", "de", "a", "mostra_del_nivell"),
}


def canonicalize_row_keys(d: dict) -> dict:
    """Renombra alies coneguts de claus de fila cap a les claus canoniques (copia, no mutacio).

    Nomes renombra si la clau canonica NO existeix ja a la fila (mai sobreescriu).
    """
    import copy
    out = copy.deepcopy(d)
    tables = out.get("tables") if isinstance(out, dict) else None
    if not isinstance(tables, dict):
        return out
    for block, aliases in ROW_KEY_ALIASES.items():
        blk = tables.get(block)
        rows = blk.get("rows") if isinstance(blk, dict) else (blk if isinstance(blk, list) else None)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for alias, canon in aliases.items():
                if alias in row and canon not in row:
                    row[canon] = row.pop(alias)
    return out


def soft_normalize(d: dict) -> dict:
    """Reparacions (a)+(b) i despres (c) alies de claus de fila (skill v1.3). Copia, no mutacio."""
    return canonicalize_row_keys(_soft_normalize_ab(d))
