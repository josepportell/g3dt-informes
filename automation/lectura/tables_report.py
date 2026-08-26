"""Fase 8b (via A) — de les taules llegides (`_decisions.json`) a les files de l'informe.

Tanca el forat 6 de `docs/wizard-headless/fase8-e2e/_RESULTATS.md`: la lectura
headless produeix `tables.{dpsh_tests,sondeig_tests,spt_ma_tests,soil_levels,
superficie_construida}` amb cel·les de 3 estats, l'Eva hi tria candidats a la
UI (`lecturaState.selections`), i fins ara res d'això arribava al generador —
l'informe sortia amb les taules de la via B (Excel + `sondeig_extracted.json`).

Aquest mòdul és la peça de traducció, i **només** això:

    decisions (contracte v1) + seleccions d'Eva  ->  files llestes per al .docx

Divisió de feina del contracte (§4.3, regles 7-8): **el lector emet dades, el
generador formata**. Per tant aquí viuen les regles de format de l'informe
(signe, decimals, "Si"/"No", "1/0" vs "1/0/0", rangs "-1,00 a -1,20"), deduïdes
dels 6 informes signats de l'Eva (`docs/golden-read-taules/_eva_truth/`).

**Fora d'abast deliberat** (no és format, és càlcul — tram 3): les fondàries
`de`/`a` de `soil_levels` viatgen al bloc però NO toquen `depth_from_m` /
`depth_to_m` / `thickness_m` de `ReportData`, que alimenten la taula sísmica i
els gruixos. Canviar-los és una decisió de càlcul, no de taula.

Stdlib pur excepte `load_project_tables()`, que és l'únic punt d'I/O.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "build_report_tables",
    "levels_by_number",
    "load_project_tables",
    "resolve_cell",
    "SELECTION_KEY_RE",
]

#: Claus de `lecturaState.selections` que la UI escriu per a cel·les de taula:
#: `"{bloc}.{index}.{cel·la}"` (p. ex. `soil_levels.0.litologia`,
#: `spt_ma_tests.0.n30`). Les claus sense punt són camps escalars.
SELECTION_KEY_RE = re.compile(r"^(?P<block>[a-z_]+)\.(?P<index>\d+)\.(?P<cell>[a-z0-9_]+)$")

_BLOCKS = ("dpsh_tests", "sondeig_tests", "spt_ma_tests", "soil_levels")

#: Text que un lector honest emet quan el document no diu res. No es
#: converteix en "No detectat": l'absència de dada NO és una absència d'aigua.
_ABSENT_MARKERS = ("no consta", "no indicat", "no indicado", "sense dada", "no trobat")


# --------------------------------------------------------------------------- cel·les


def resolve_cell(cell: Any) -> Any:
    """Valor pla d'una cel·la del contracte.

    Una cel·la pot ser (i totes quatre formes surten de fitxers reals):
      - un dict de 3 estats: `{"estat", "value", "candidates": [...]}`
      - un valor pla (els identificadors de fila — `punt`, `sondeig`, `nom` —
        són text pla per contracte)
      - un dict de comptes SPT/MA: `{"n_spt", "n_tp", "n_ma"}`
      - una LLISTA de candidats sense embolcall (dialecte d'alguns fixtures
        d'or: `litologia: [{"value": …, "font": …}, …]`). Sense aquesta
        branca, la llista sencera acabaria impresa a la cel·la del `.docx`.

    `no_trobat` retorna `None` (regla 4 del contracte: mai escriu valor).
    """
    if isinstance(cell, (list, tuple)):
        for item in cell:
            value = resolve_cell(item) if isinstance(item, (dict, list, tuple)) else item
            if value not in (None, ""):
                return value
        return None
    if not isinstance(cell, dict):
        return cell
    if "estat" in cell:
        estat = cell.get("estat")
        if estat == "no_trobat":
            return None
        value = cell.get("value")
        if value is None or value == "":
            candidates = cell.get("candidates") or []
            if candidates and isinstance(candidates[0], dict):
                value = candidates[0].get("value")
        if isinstance(value, dict):
            return resolve_cell(value)
        return value
    if any(k in cell for k in ("n_spt", "n_tp", "n_ma")):
        return cell
    if "value" in cell:
        return cell.get("value")
    return None


def _selected(selections: Mapping[str, Any] | None, block: str, index: int, cell: str) -> Any:
    """Tria explícita de l'Eva per a una cel·la, si n'hi ha (mai `''`)."""
    if not selections:
        return None
    value = selections.get(f"{block}.{index}.{cell}")
    return value if value not in (None, "") else None


def _cell(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    """Primera clau present de `names` (alies de contracte ja canonicalitzats,
    però els fixtures d'or porten variants)."""
    for name in names:
        if name in row:
            return row[name]
    return None


# --------------------------------------------------------------------------- format


_NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _num(value: Any) -> float | None:
    """Primer nombre d'un valor llegit, ignorant unitats i notes.

    `"-4 m (respecte el carrer)"` -> -4.0 · `"1,08 m"` -> 1.08 ·
    `"570.90 msnm"` -> 570.9 · `"Si"` -> None.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    match = _NUM_RE.search(value)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _nums(value: Any) -> list[float]:
    if not isinstance(value, str):
        n = _num(value)
        return [n] if n is not None else []
    out = []
    for m in _NUM_RE.finditer(value):
        try:
            out.append(float(m.group(0).replace(",", ".")))
        except ValueError:
            pass
    return out


def fmt_cota(value: Any) -> str:
    """Cota d'inici: signe explícit i 2 decimals (`+199.50`, `-4.00`).

    Els informes de l'Eva porten sempre el signe: absoluta `+199.50 msnm`,
    relativa al carrer `-4.20`. Es respecta el signe LLEGIT (el sistema de
    cotes del projecte és decisió del lector, regla d'or Pas 3b).
    """
    n = _num(value)
    if n is None:
        return "" if value is None else str(value)
    return f"{n:+.2f}"


def fmt_depth(value: Any) -> str:
    """Profunditat assolida: sempre negativa, 2 decimals (`-1.08`)."""
    n = _num(value)
    if n is None:
        return "" if value is None else str(value)
    return f"-{abs(n):.2f}"


def fmt_depth_range(value: Any) -> str:
    """Fondària d'extracció SPT/MA: `-1.00 a -1.20` (els dos extrems negatius)."""
    nums = _nums(value)
    if len(nums) >= 2:
        return f"-{abs(nums[0]):.2f} a -{abs(nums[1]):.2f}"
    if len(nums) == 1:
        return f"-{abs(nums[0]):.2f}"
    return "" if value is None else str(value)


def fmt_refusal(value: Any) -> str:
    """Rebuig: `Si` / `No` (l'Eva escriu `Si` sense accent als 6 informes)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Si" if value else "No"
    text = str(value).strip().lower()
    if text.startswith(("si", "sí", "sí", "yes")):
        return "Si"
    if text.startswith(("no",)):
        return "No"
    return str(value)


def fmt_water(value: Any) -> str:
    """Nivell freàtic: fondària negativa si és un nombre; si no, el text
    llegit amb la inicial en majúscula.

    `"no consta"` NO es converteix en `"No detectat"`: que el document no ho
    digui no vol dir que no hi hagi aigua (mai fals-segur).
    """
    if value is None:
        return ""
    if isinstance(value, str) and value.strip().lower() in _ABSENT_MARKERS:
        text = value.strip()
        return text[:1].upper() + text[1:]
    n = _num(value)
    if n is not None:
        return f"-{abs(n):.2f}"
    text = str(value).strip()
    return text[:1].upper() + text[1:] if text else ""


def fmt_spt_ma(value: Any) -> str:
    """Columna SPT/MA de la taula de sondeigs, a partir dels comptes.

    Regla 7 del contracte: el lector emet `{n_spt, n_tp, n_ma}`, el generador
    formata. L'Eva no és consistent entre projectes (`1/0`, `1/--`, `1/0/0`,
    `1/0/1`); la forma que encerta més files dels 6 informes signats és:
    **triple quan hi ha TP o MA, parella quan només hi ha SPT**.
    """
    if isinstance(value, dict) and any(k in value for k in ("n_spt", "n_tp", "n_ma")):
        n_spt = int(value.get("n_spt") or 0)
        n_tp = int(value.get("n_tp") or 0)
        n_ma = int(value.get("n_ma") or 0)
        if n_tp or n_ma:
            return f"{n_spt}/{n_tp}/{n_ma}"
        return f"{n_spt}/{n_ma}"
    if value is None:
        return ""
    return str(value)


_N30_ANNOT_RE = re.compile(r"^\s*(\d+|R|--)\s*\(.*\)\s*$", re.I)


def fmt_n30(value: Any) -> str:
    """N30: nombre, `R` (rebuig) o `--`.

    Els lectors hi afegeixen de vegades l'explicació entre parèntesis
    (`"R (rebuig)"`, `"40 (suma dels trams centrals 20+20)"`). A la cel·la hi
    va la xifra; el raonament ja viatja com a `font`/`quote` al popup. Nomes
    s'escapça quan el que queda davant és exactament un N30 vàlid.
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "/".join(str(v) for v in value)
    text = str(value).strip()
    match = _N30_ANNOT_RE.match(text)
    return match.group(1) if match else text


def fmt_text(value: Any) -> str:
    """Text d'una cel·la. Mai imprimeix una estructura crua.

    Xarxa de seguretat: si una forma nova de cel·la arriba fins aquí sense
    resoldre, val més una cel·la buida que `[{'value': …, 'font': …}]` dins
    de l'informe de l'Eva.
    """
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        resolved = resolve_cell(value)
        if isinstance(resolved, (dict, list, tuple)) or resolved is None:
            return ""
        return str(resolved).strip()
    return str(value).strip()


# --------------------------------------------------------------------------- blocs


def _n30_value(cell: Any) -> Any:
    """`n30` porta el registre (segur) i els candidats de la suma (mai segur).

    A la taula de l'informe hi va la decisió (`value`/candidat 1); el registre
    de 4 trams és evidència per al popup, no text de cel·la.
    """
    if isinstance(cell, dict):
        resolved = resolve_cell(cell)
        if resolved not in (None, ""):
            return resolved
        registre = cell.get("registre")
        if isinstance(registre, dict):
            return resolve_cell(registre)
        return registre
    return cell


def _rows(tables: Mapping[str, Any], block: str) -> list[dict]:
    blk = tables.get(block)
    if isinstance(blk, dict):
        rows = blk.get("rows")
    else:
        rows = blk
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _pick(row, selections, block, i, cell, names):
    chosen = _selected(selections, block, i, cell)
    if chosen is not None:
        return chosen
    return resolve_cell(_cell(row, names))


def build_report_tables(
    decisions: Mapping[str, Any] | None,
    selections: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Files llestes per al context del `.docx`, des de les decisions de lectura.

    Les claus de cada fila són les que ja fa servir la plantilla Jinja
    (`test.test_id`, `test.cota`, `test.depth`, `test.refusal`, `test.water`,
    `test.spt_ma`), de manera que el generador només ha de substituir la llista.

    Retorna `{}` si no hi ha cap taula llegida (i llavors el generador es
    comporta EXACTAMENT com avui: via B intacta).
    """
    if not isinstance(decisions, Mapping):
        return {}
    tables = decisions.get("tables")
    if not isinstance(tables, Mapping):
        return {}

    out: dict[str, Any] = {}

    dpsh = []
    for i, row in enumerate(_rows(tables, "dpsh_tests")):
        dpsh.append({
            "test_id": fmt_text(_pick(row, selections, "dpsh_tests", i, "punt", ("punt",))),
            "cota": fmt_cota(_pick(row, selections, "dpsh_tests", i, "cota_inici", ("cota_inici", "cota"))),
            "depth": fmt_depth(_pick(row, selections, "dpsh_tests", i, "profunditat_assolida",
                                     ("profunditat_assolida", "profunditat"))),
            "refusal": fmt_refusal(_pick(row, selections, "dpsh_tests", i, "rebuig", ("rebuig",))),
            "water": fmt_water(_pick(row, selections, "dpsh_tests", i, "nivell_freatic",
                                     ("nivell_freatic", "nf"))),
        })
    if dpsh:
        out["dpsh_tests"] = dpsh

    sondeig = []
    for i, row in enumerate(_rows(tables, "sondeig_tests")):
        sondeig.append({
            "test_id": fmt_text(_pick(row, selections, "sondeig_tests", i, "sondeig", ("sondeig", "punt"))),
            "cota": fmt_cota(_pick(row, selections, "sondeig_tests", i, "cota", ("cota", "cota_inici"))),
            "depth": fmt_depth(_pick(row, selections, "sondeig_tests", i, "profunditat_assolida",
                                     ("profunditat_assolida", "profunditat"))),
            "spt_ma": fmt_spt_ma(_pick(row, selections, "sondeig_tests", i, "spt_ma", ("spt_ma",))),
            "water": fmt_water(_pick(row, selections, "sondeig_tests", i, "nivell_freatic",
                                     ("nivell_freatic", "nf"))),
        })
    if sondeig:
        out["sondeig_tests"] = sondeig

    spt = []
    for i, row in enumerate(_rows(tables, "spt_ma_tests")):
        n30_chosen = _selected(selections, "spt_ma_tests", i, "n30")
        n30 = n30_chosen if n30_chosen is not None else _n30_value(_cell(row, ("n30",)))
        spt.append({
            "test_id": fmt_text(_pick(row, selections, "spt_ma_tests", i, "id", ("id", "mostra"))),
            "location": fmt_text(_pick(row, selections, "spt_ma_tests", i, "punt", ("punt", "sondeig"))),
            "depth_range": fmt_depth_range(_pick(row, selections, "spt_ma_tests", i, "profunditat",
                                                 ("profunditat", "fondaria", "prof_extraccio"))),
            "n30": fmt_n30(n30),
            "lithology": fmt_text(_pick(row, selections, "spt_ma_tests", i, "litologia",
                                        ("litologia", "litologia_candidats"))),
        })
    if spt:
        out["spt_ma_tests"] = spt

    levels = []
    for i, row in enumerate(_rows(tables, "soil_levels")):
        levels.append({
            "name": fmt_text(_pick(row, selections, "soil_levels", i, "nom", ("nom", "nivell"))),
            "litologia": fmt_text(_pick(row, selections, "soil_levels", i, "litologia",
                                        ("litologia", "litologia_candidats"))),
            # `de`/`a` viatgen com a evidència; NO toquen gruixos ni càlculs (vegeu docstring).
            "de": _pick(row, selections, "soil_levels", i, "de", ("de", "desde")),
            "a": _pick(row, selections, "soil_levels", i, "a", ("a", "fins")),
        })
    if levels:
        out["soil_levels"] = levels

    sc = _superficie(tables.get("superficie_construida"), selections)
    if sc:
        out["superficie_construida"] = sc

    lab = _lab(decisions.get("fields"), selections)
    if lab:
        out["lab"] = lab

    return out


def _superficie(block: Any, selections: Mapping[str, Any] | None) -> str:
    """Regla 8 del contracte: el lector emet `components[]` + `total`; el
    generador tria la forma. L'informe de l'Eva porta el TOTAL, en xifra.

    El `total` llegit pot arribar amb l'aclariment del lector enganxat
    (`"120 m² construïts (PB+1…) — PER HABITATGE; l'encàrrec són 3
    habitatges"`). A la cel·la hi va la xifra i prou: el matís viatja al
    popup com a font/cita, no dins d'una casella de superfície.
    """
    chosen = (selections or {}).get("superficie_construida")
    if chosen not in (None, ""):
        return str(chosen)
    if not isinstance(block, Mapping):
        return ""
    total = block.get("total")
    if total in (None, ""):
        total = resolve_cell(block)
    number = _num(total) if total not in (None, "") else None
    if number is None:
        components = block.get("components") or []
        nums = [n for c in components for n in _nums(c)[:1]]
        number = sum(nums) if nums else None
    return f"{number:g}" if number is not None else ""


_LAB_KEYS = (("lab_sample_id", "sample_id"), ("lab_location", "location"), ("lab_depth", "depth"))


def _lab(fields: Any, selections: Mapping[str, Any] | None) -> dict[str, str]:
    """Capçalera de la taula «Mostra : … / Punt: … / Profunditat: …».

    Són camps ESCALARS de la lectura que el wizard no té com a input (viuen a
    `LECTURA_EXTRA_KEYS` de la UI); sense aquest pont, mai arriben a l'informe.
    """
    if not isinstance(fields, Mapping):
        return {}
    out: dict[str, str] = {}
    for decision_key, out_key in _LAB_KEYS:
        chosen = (selections or {}).get(decision_key)
        value = chosen if chosen not in (None, "") else resolve_cell(fields.get(decision_key))
        if value not in (None, ""):
            out[out_key] = str(value).strip()
    return out


# --------------------------------------------------------------------------- alineació de nivells

#: Senyal fort de capa de cobertura SENSE número de nivell (mateixa regla que
#: `compare_consolida.row_key`, v2): la capa vegetal no és el nivell 1.
_COVER_RE = re.compile(r"vegetal|capa superior|no numerad|sense num|no numerat", re.I)
_LEVEL_RE = re.compile(r"nivell\s*(\d+)|(\d+)\s*(?:er|on|r|n|e|a|o)?\s*nivell", re.I)


def _level_number(name: Any) -> int | None:
    """Número de nivell d'un nom de fila (`"NIVELL 1"`, `"1er nivell"` -> 1).

    `None` per a la capa vegetal / files sense número: alinear-la amb el
    nivell 1 de l'informe seria exactament l'error que el comparador v2 va
    destapar (fondàries des de 0,00 quan la capa vegetal s'absorbeix).
    """
    text = str(name or "")
    match = _LEVEL_RE.search(text)
    if match:
        try:
            return int(match.group(1) or match.group(2))
        except (TypeError, ValueError):
            return None
    if _COVER_RE.search(text):
        return None
    return None


def levels_by_number(levels: list[Mapping[str, Any]] | None) -> dict[int, dict]:
    """`soil_levels` del bloc, indexats per número de nivell.

    Permet al generador casar cada `SoilLevel.level_number` amb la fila
    llegida sense dependre de l'ordre ni del nombre de files (l'or pot portar
    una capa vegetal que l'informe no numera).
    """
    out: dict[int, dict] = {}
    for row in levels or []:
        if not isinstance(row, Mapping):
            continue
        number = _level_number(row.get("name"))
        if number is not None and number not in out:
            out[number] = dict(row)
    return out


# --------------------------------------------------------------------------- I/O


def load_project_tables(
    project_path: str | Path,
    selections: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Llegeix `validation/lectura/_decisions.json` del projecte i el tradueix.

    Retorna `{}` si no existeix o no és llegible — a la via B aquest fitxer no
    hi és mai, i el generador es comporta com sempre.
    """
    path = Path(project_path) / "validation" / "lectura" / "_decisions.json"
    if not path.exists():
        return {}
    try:
        decisions = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(decisions, dict):
        return {}
    return build_report_tables(decisions, selections)


def _main(argv: list[str]) -> int:
    """CLI de desenvolupament: tradueix un `_decisions.json` a files d'informe.

        python -m automation.lectura.tables_report DECISIONS.json [SELECCIONS.json]
    """
    if not argv:
        print(_main.__doc__)
        return 1
    decisions = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    selections = json.loads(Path(argv[1]).read_text(encoding="utf-8")) if len(argv) > 1 else None
    print(json.dumps(build_report_tables(decisions, selections), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(_main(sys.argv[1:]))
