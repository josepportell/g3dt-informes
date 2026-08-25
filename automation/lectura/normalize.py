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


#: Reparacio (d), Fase 12: cel·les de DADES d'una fila de `tables` (mai els identificadors de fila
#: `punt`/`sondeig`/`nom`, que son text pla per contracte).
_ROW_DATA_CELLS: dict[str, tuple[str, ...]] = {
    "dpsh_tests": ("cota_inici", "profunditat_assolida", "rebuig", "nivell_freatic"),
    "sondeig_tests": ("cota", "profunditat_assolida", "spt_ma", "nivell_freatic"),
    "spt_ma_tests": ("id", "profunditat", "litologia", "n30"),
    "soil_levels": ("litologia", "de", "a", "mostra_del_nivell"),
}
_NEVER_SEGUR_CELLS = frozenset({("spt_ma_tests", "n30"), ("spt_ma_tests", "litologia"), ("soil_levels", "litologia")})


def wrap_flat_cells(d: dict) -> dict:
    """Reparacio (d), Fase 12 (lliso de la consolidacio `preext-v2-c3`, 23 ABSENT): una cel·la de dades
    PLANA (string/nombre/bool/null en lloc de `{estat, value, candidates}`) s'embolcalla de forma
    determinista amb `estat` = `estat_bloc` de la fila/bloc (o `candidats`), `value` = el valor pla i
    `candidates = [{value, font: "(adaptat)", quote: ""}]`; `null` → `no_trobat`. n30/litologia mai
    `segur`. No s'inventa cap dada: nomes es dona forma al que ja hi era. Copia, no mutacio."""
    out = copy.deepcopy(d)
    tables = out.get("tables") if isinstance(out, dict) else None
    if not isinstance(tables, dict):
        return out
    for block, cells in _ROW_DATA_CELLS.items():
        blk = tables.get(block)
        rows = blk.get("rows") if isinstance(blk, dict) else (blk if isinstance(blk, list) else None)
        if not isinstance(rows, list):
            continue
        estat_bloc = blk.get("estat_bloc") if isinstance(blk, dict) else None
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_estat = row.get("estat") if row.get("estat") in ("segur", "candidats", "no_trobat") else None
            base = row_estat or (estat_bloc if estat_bloc in ("segur", "candidats", "no_trobat") else "candidats")
            for cell in cells:
                if cell not in row:
                    continue
                val = row[cell]
                if isinstance(val, dict) and "estat" in val:
                    continue
                if isinstance(val, dict) and cell == "n30" and ("registre" in val or "value" in val):
                    v = val.get("value")
                    registre = val.get("registre")
                    if v is None and isinstance(registre, str) and registre.strip().upper().startswith("R"):
                        v = "R"
                    wrapped = _flat_to_cell(v, "candidats", block)
                    if registre is not None:
                        wrapped["registre"] = registre if isinstance(registre, dict) and "estat" in registre else \
                            _flat_to_cell(registre, "segur", block)
                    row[cell] = wrapped
                    continue
                estat = "candidats" if (block, cell) in _NEVER_SEGUR_CELLS else base
                row[cell] = _flat_to_cell(val, estat, block)
                if cell == "nivell_freatic" and "matis" in row and "matis" not in row[cell]:
                    row[cell]["matis"] = row.get("matis")
    return out


def _flat_to_cell(val: Any, estat: str, block: str) -> dict:
    if val is None or (isinstance(val, str) and not val.strip()):
        return {"estat": "no_trobat", "value": None, "sources_checked": ["(adaptat: cel·la plana buida)"]}
    if isinstance(val, list) and val and all(isinstance(x, dict) and "value" in x for x in val):
        cands = [{"value": x.get("value"), "font": x.get("font", "(adaptat)"), "quote": x.get("quote", "")} for x in val[:3]]
        return {"estat": "candidats", "value": cands[0]["value"], "candidates": cands, "rule": "(adaptat: llista de candidats plana)"}
    if isinstance(val, list):
        val = val[0] if len(val) == 1 else val
    if estat == "no_trobat":
        estat = "candidats"
    return {"estat": estat, "value": val,
            "candidates": [{"value": val, "font": "(adaptat)", "quote": val if isinstance(val, str) else ""}],
            "rule": "(adaptat: cel·la plana embolcallada de forma determinista, Fase 12)"}


def soft_normalize(d: dict) -> dict:
    """Reparacions (a)+(b), (c) alies de claus de fila (skill v1.3) i (d) cel·les planes (Fase 12). Copia, no mutacio."""
    return wrap_flat_cells(canonicalize_row_keys(_soft_normalize_ab(d)))
