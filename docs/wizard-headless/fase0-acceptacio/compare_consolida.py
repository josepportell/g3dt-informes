"""Acceptació Fase 0/12: compara `_decisions.json` produïts (agents `--consolida` o `consolidate.py`) vs l'or.

Ús: python3 compare_consolida.py escalars|taules [PATH_decisions.json] [CARPETA_PROJECTE_OR]
Veredictes per camp: OK (mateix estat), CAUTELA (or segur -> produït candidats amb el bo dins),
ALERTA (produït més confiat que l'or, o valor segur != or), NOU (clau v1 sense or), ERR (valor segur discrepant),
ABSENT (cel·la d'or sense cel·la produïda), VIOLACIO (regla dura: n30 / litologia mai segur).

v2 (2026-08-25, normalitzadors): `close(a, b, field)` és conscient del camp i del tipus de valor, en aquest ordre:
  1. adreces (`street_address`): `C/ARBRELLS 18A-18B-20` = `Carrer Arbrells, 18A, 18B i 20`; el conjunt de números de
     portal ha de coincidir — una lectura parcial (`Carrer Arbrells 18A`) NO és el mateix valor. Decisiu.
  2. `spt_ma` per comptes: `1/0` = `1/0/0` = `{n_spt:1, n_tp:0, n_ma:0}`; `--` = 0. Decisiu.
  3. dates senceres (ISO, D/M/A, `Octubre 2025`, `24 d'octubre de 2025`): mateix any/mes; dia igual o absent. Decisiu.
  4. nombres i intervals: `-4 m` = `-4,0 m`; `570.90 msnm` = `570,90`; fondàries en valor absolut (`ABS_FIELDS`):
     `1,0 - 1,2 m` = `-1,00 a -1,20 m`. Un guió entre dos dígits és separador d'interval, no signe. Decisiu.
  5. `num_floors`: `PB+PP` = `PB+1` = `Pb + p1`; anotacions fora.
  6. `building_type`: conjunt de tokens (singular, abreviatures `hab`/`unif` esteses, articles i "construcció" fora);
     un conjunt inclòs a l'altre = CLOSE (memòria `feedback_building_type_close_match`).
  7. text: la regla històrica (cadena normalitzada igual o continguda) i, si no, igualtat després de treure les
     anotacions `(...)` i ` -- nota`.
Independent del consolidador (`automation/lectura/consolidate.py`): no en comparteix codi a posta — l'instrument
d'acceptació no ha d'heretar els errors de l'objecte que mesura. Sortida idèntica a la v1 (la llegeixen
`mesures/ledger.py` i `fase12-consolida/harness.py`).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

S = Path(__file__).resolve().parent
REPO = S.parents[2]
DEFAULT_PROJ = "4001612 BELL-LLOC"

ADDRESS_FIELDS = frozenset({"street_address"})
# fondàries: el signe és convenció d'escriptura (Eva: "-1.00 a -1.20"; GTL: "1,0 - 1,2"), no informació
ABS_FIELDS = frozenset({"lab_depth", "profunditat", "profunditat_assolida", "de", "a", "nivell_freatic"})
_UNITS = frozenset({"m", "ml", "msnm", "msn", "m2", "cm", "mm", "mts", "metres", "metros", "aprox", "ca", "a", "i",
                    "fins", "al", "de", "x", "y", "z", "e", "n", "so4", "mg", "kg"})
_DASHES = str.maketrans({"−": "-", "–": "-", "—": "-", "‐": "-", "‑": "-"})
_MONTHS = {"gener": 1, "enero": 1, "febrer": 2, "febrero": 2, "marc": 3, "marzo": 3, "abril": 4, "maig": 5, "mayo": 5,
           "juny": 6, "junio": 6, "juliol": 7, "julio": 7, "agost": 8, "agosto": 8, "setembre": 9, "septiembre": 9,
           "octubre": 10, "novembre": 11, "noviembre": 11, "desembre": 12, "diciembre": 12}


def _ascii(s) -> str:
    return unicodedata.normalize("NFKD", str(s).translate(_DASHES)).encode("ascii", "ignore").decode()


def norm(v) -> str:
    """Normalització històrica (v1): sense espais, puntuació ni signes; minúscules."""
    if v is None:
        return ""
    return re.sub(r"[\s.,;:+()\-']+", "", _ascii(v)).lower()


_ANNOT_RE = re.compile(r"\([^)]*\)")
_NOTE_RE = re.compile(r"\s+-{1,2}\s+(?=[A-Za-z])")


def strip_annot(s) -> str:
    """Treu anotacions: `(...)` i una nota final ` -- text` / ` - text` (un guió seguit de lletra)."""
    t = _ANNOT_RE.sub(" ", str(s).translate(_DASHES))
    t = _NOTE_RE.split(t, maxsplit=1)[0]
    return re.sub(r"\s+", " ", t).strip()


# --- dates -------------------------------------------------------------------------------------------------------
_ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?$")
_DMY_RE = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})$")
_MONTH_RE = re.compile(r"^(?:(\d{1,2})\s+(?:de\s+|d')?)?([a-z]+)\s+(?:de\s+|del\s+)?(\d{4})$")


def parse_date(s) -> tuple | None:
    """(any, mes, dia|None) si TOTA la cadena (sense anotacions) és una data; si no, None."""
    t = _ascii(strip_annot(s)).lower().strip()
    m = _ISO_RE.match(t)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), (int(m.group(3)) if m.group(3) else None)
    else:
        m = _DMY_RE.match(t)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
        else:
            m = _MONTH_RE.match(t)
            if not m or m.group(2) not in _MONTHS:
                return None
            d, mo, y = (int(m.group(1)) if m.group(1) else None), _MONTHS[m.group(2)], int(m.group(3))
    if not (1 <= mo <= 12) or (d is not None and not (1 <= d <= 31)) or not (1990 <= y <= 2100):
        return None
    return (y, mo, d)


def dates_compatible(a: tuple, b: tuple) -> bool:
    return a[0] == b[0] and a[1] == b[1] and (a[2] is None or b[2] is None or a[2] == b[2])


# --- nombres i intervals ------------------------------------------------------------------------------------------
_NUM_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:[.,]\d+)?(?![A-Za-z0-9])")
_RANGE_DASH_RE = re.compile(r"(?<=\d)\s*-\s*(?=\d)")


def parse_numbers(s, absolute: bool = False) -> tuple | None:
    """Tupla de nombres si el valor és 'numèric' (comença per un nombre i la resta són unitats/partícules)."""
    t = _ascii(strip_annot(s)).lower()
    t = _RANGE_DASH_RE.sub(" ", t)           # `1,0-1,2` / `1,0 - 1,2` → interval, no signe
    t = re.sub(r"^[\s~<>+]+", "", t)          # ≈ ≤ ≥ ja han caigut amb l'ASCII
    if not re.match(r"-?\d", t):
        return None
    nums = _NUM_RE.findall(t)
    if not nums:
        return None
    words = re.findall(r"[a-z]+", _NUM_RE.sub(" ", t))
    if not all(w in _UNITS or len(w) <= 2 for w in words):
        return None
    vals = tuple(round(float(x.replace(",", ".")), 3) for x in nums)
    return tuple(abs(v) for v in vals) if absolute else vals


# --- adreces ------------------------------------------------------------------------------------------------------
_STREET_RE = re.compile(
    r"^\s*(?:situat\s+(?:a|al)\s+)?(?:carrer|c/|c\.|cl\.?|calle|av\.?|avinguda|avda\.?|avenida|pl\.?|placa|plaza|"
    r"ctra\.?|carretera|cami|passeig|pg\.?|ronda|rda\.?|travessera|trav\.?|rambla)\b\.?/?\s*(.*)$")
_ADDR_STOP = frozenset({"de", "del", "dels", "d", "l", "la", "el", "els", "les", "i", "y", "e"})
_NUM_PORTAL_RE = re.compile(r"\d+(?:\s?[a-z](?![a-z]))?")


def parse_address(s) -> tuple | None:
    """(tokens del nom del carrer, conjunt de portals) si sembla 'tipus de via + nom + números'; si no, None."""
    t = _ascii(strip_annot(s)).lower()
    t = re.sub(r"\bn(?:[o°]|um(?:ero)?)?\.?\s*(?=\d)", " ", t)   # nº / num. / n. davant del número
    t = re.sub(r"^\s*c/", "carrer ", t)
    m = _STREET_RE.match(t)
    if not m:
        return None
    rest = m.group(1)
    portals = frozenset(re.sub(r"\s", "", x) for x in _NUM_PORTAL_RE.findall(rest))
    name = tuple(w for w in re.findall(r"[a-z]+", _NUM_PORTAL_RE.sub(" ", rest)) if w not in _ADDR_STOP)
    if not portals or not name:
        return None
    return (name, portals)


# --- spt_ma per comptes -------------------------------------------------------------------------------------------
_SPT_STR_RE = re.compile(r"^\s*(\d+|-+)\s*/\s*(\d+|-+)(?:\s*/\s*(\d+|-+))?\s*$")


def parse_spt_ma(v) -> tuple | None:
    """(n_spt, n_tp|None, n_ma): dict `{n_spt, n_tp, n_ma}` o cadena `SPT/MA` | `SPT/TP/MA`; `--` = 0."""
    if isinstance(v, dict):
        if not {"n_spt", "n_ma"} <= set(v):
            return None
        return (int(v.get("n_spt") or 0), (int(v["n_tp"]) if v.get("n_tp") is not None else None), int(v.get("n_ma") or 0))
    m = _SPT_STR_RE.match(strip_annot(v)) if isinstance(v, str) else None
    if not m:
        return None
    n = [0 if g is None or g.startswith("-") else int(g) for g in m.groups()]
    return (n[0], None, n[1]) if m.group(3) is None else (n[0], n[1], n[2])


def spt_compatible(a: tuple, b: tuple) -> bool:
    return a[0] == b[0] and a[2] == b[2] and (a[1] is None or b[1] is None or a[1] == b[1])


# --- num_floors, building_type ------------------------------------------------------------------------------------
def norm_floors(s) -> str:
    t = re.sub(r"[^a-z0-9]+", "", _ascii(strip_annot(s)).lower().split(",", 1)[0])
    t = t.replace("pbpp", "pb1").replace("pbp1", "pb1")
    return re.sub(r"pp$", "1", t)


_BT_STOP = frozenset({"de", "del", "dels", "d", "l", "la", "el", "els", "les", "un", "una", "uns", "unes", "i", "y",
                      "amb", "per", "a", "en", "the", "construccio", "constr", "edificacio", "edificio", "vivienda"})
_BT_ABBR = {"hab": "habitatge", "habit": "habitatge", "vivienda": "habitatge", "viviendas": "habitatge",
            "unif": "unifamiliar", "unifam": "unifamiliar", "aill": "aillat", "plurif": "plurifamiliar"}


def building_tokens(s) -> frozenset:
    out = set()
    for w in re.findall(r"[a-z0-9]+", _ascii(s).lower().replace("'", " ")):
        w = _BT_ABBR.get(w, w)
        if w.endswith("s") and len(w) > 4 and not w.endswith("ss"):
            w = w[:-1]
        if w not in _BT_STOP:
            out.add(w)
    return frozenset(out)


# --- close --------------------------------------------------------------------------------------------------------
def close(a, b, field: str | None = None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    f = (field or "").lower()
    A, B = str(a), str(b)
    if f in ADDRESS_FIELDS:
        pa, pb = parse_address(A), parse_address(B)
        if pa and pb:
            return pa == pb
    if f == "spt_ma":
        pa, pb = parse_spt_ma(a), parse_spt_ma(b)
        if pa and pb:
            return spt_compatible(pa, pb)
    da, db = parse_date(A), parse_date(B)
    if da and db:
        return dates_compatible(da, db)
    if da or db:
        return False
    na, nb = parse_numbers(A, absolute=f in ABS_FIELDS), parse_numbers(B, absolute=f in ABS_FIELDS)
    if na and nb:
        return na == nb
    if f == "num_floors":
        fa, fb = norm_floors(A), norm_floors(B)
        return bool(fa) and fa == fb
    if f == "building_type":
        ta, tb = building_tokens(A), building_tokens(B)
        return bool(ta and tb) and (ta <= tb or tb <= ta)
    la, lb = norm(A), norm(B)
    if la == lb or (la and lb and (la in lb or lb in la)):
        return True
    sa, sb = norm(strip_annot(A)), norm(strip_annot(B))
    return bool(sa) and sa == sb


# --- or -----------------------------------------------------------------------------------------------------------
def flat_gold_scalars(proj: str) -> dict:
    d = json.load(open(REPO / "docs/golden-read" / proj / "_decisions.json", encoding="utf-8"))["decisions"]
    out = {}
    for k, v in d.items():
        st = v.get("status") or v.get("estat")
        if k in ("lab", "cte") and isinstance(v.get("value"), dict):
            for sk, sv in v["value"].items():
                out[sk] = {"estat": st, "value": sv}
        elif k == "utm_x_utm_y":
            m = re.search(r"X\s*([\d.]+)\s*;\s*Y\s*([\d.]+)", str(v.get("value", "")))
            out["utm_x"] = {"estat": st, "value": m.group(1) if m else v.get("value")}
            out["utm_y"] = {"estat": st, "value": m.group(2) if m else v.get("value")}
        else:
            out[k] = {"estat": st, "value": v.get("value")}
    return out


def _expand_de_a(row: dict) -> dict:
    """Dialecte del fixture de Castellar: `de`/`a` plans + cel·la `de_a_estat` → cel·les `de` i `a` amb aquell estat."""
    cell = row.get("de_a_estat")
    if not isinstance(cell, dict) or "estat" not in cell:
        return row
    row = dict(row)
    row.pop("de_a_estat")
    de, a = row.get("de"), row.get("a")
    if (de is None or a is None) and isinstance(cell.get("value"), str) and " a " in cell["value"]:
        de, a = [x.strip() for x in cell["value"].split(" a ", 1)]
    for k, v in (("de", de), ("a", a)):
        if not isinstance(v, dict) and v is not None:
            row[k] = {"estat": cell["estat"], "value": v, "candidates": [{"value": v, "font": "(de_a_estat del fixture)"}]}
    return row


_COVER_RE = re.compile(r"vegetal|cobertura|reblert|relleno|capa superior|no numerad|sense num|no numerat")
_LEVEL_RE = re.compile(r"nivell\s*(\d+)|(\d+)\s*(?:er|on|r|n|e|a|o)?\s*nivell")


def _plain(v):
    """Valor pla d'una cel·la (value, o primer candidat) o el valor tal qual si ja és pla."""
    if isinstance(v, dict) and "estat" in v:
        return v.get("value") or (cand_values(v)[0] if cand_values(v) else None)
    return v


def row_key(block: str, row: dict) -> str | None:
    """Clau d'alineació d'una fila: punt (DPSH), sondeig (sondeig), capa/nivell N (soil_levels); None si no es pot."""
    if block == "dpsh_tests":
        v = _plain(row.get("punt"))
        return norm(v) or None
    if block == "sondeig_tests":
        v = _plain(row.get("sondeig")) or _plain(row.get("punt"))
        return norm(v) or None
    if block == "soil_levels":
        t = _ascii(_plain(row.get("nom")) or "").lower()
        if _COVER_RE.search(t):
            return "cover"
        m = _LEVEL_RE.search(t)
        if m:
            return f"n{m.group(1) or m.group(2)}"
        return None
    return None  # spt_ma_tests: per índex (etiquetes SPT-1/MA1 massa variables; l'or té una fila)


def align_rows(block: str, grows: list, prows: list) -> tuple[list[tuple[dict, dict]], bool]:
    """Parells (fila d'or, fila produïda o {}) alineats per clau si totes les claus són úniques als dos costats; si no, per índex."""
    gk = [row_key(block, r) for r in grows]
    pk = [row_key(block, r) for r in prows]
    if grows and prows and all(gk) and all(pk) and len(set(gk)) == len(gk) and len(set(pk)) == len(pk):
        pmap = dict(zip(pk, prows))
        return [(g, pmap.get(k, {})) for g, k in zip(grows, gk)], True
    return [(g, prows[i] if i < len(prows) else {}) for i, g in enumerate(grows)], False


def cand_values(f):
    return [c.get("value") for c in (f.get("candidates") or []) if isinstance(c, dict)]


def verdict(gold, prod, field: str | None = None):
    ge, pe = gold["estat"], prod.get("estat")
    gv, pv = gold.get("value"), prod.get("value")
    if gv is None and cand_values(gold):
        gv = cand_values(gold)[0]  # or segur sense value explícit (dialecte taules)
    if pv is None and cand_values(prod):
        pv = cand_values(prod)[0]
    if pe == ge:
        if ge == "segur" and not close(gv, pv, field):
            return "ERR", f"segur discrepant: or={gv!r} prod={pv!r}"
        return "OK", ""
    if ge == "segur" and pe == "candidats":
        if any(close(gv, c, field) for c in cand_values(prod)) or close(gv, pv, field):
            return "CAUTELA", f"or segur, prod candidats (bo dins): {gv!r}"
        return "ALERTA", f"or segur {gv!r} NO entre candidats {cand_values(prod)!r}"
    if ge == "candidats" and pe == "segur":
        ok = any(close(pv, c, field) for c in cand_values(gold)) or close(gv, pv, field)
        return "ALERTA", f"prod puja a segur ({pv!r}); or candidats" + ("" if ok else " i valor fora dels candidats d'or!")
    return "ALERTA", f"estat or={ge} prod={pe} (or value={gv!r})"


def compare_escalars(prod_path: Path, proj: str) -> tuple[list[str], dict]:
    gold = flat_gold_scalars(proj)
    prod = json.load(open(prod_path, encoding="utf-8"))
    assert prod.get("schema_version") == 1, "schema_version != 1"
    pf = prod["fields"]
    lines: list[str] = []
    bad_dialect = [k for k, v in pf.items() if "status" in v or any("source" in c for c in (v.get("candidates") or []) if isinstance(c, dict))]
    if bad_dialect:
        lines.append(f"DIALECTE ANTIC a: {bad_dialect}")
    counts: dict = {}
    for k in sorted(set(gold) | set(pf)):
        if k not in gold:
            lines.append(f"NOU      {k:22s} prod={pf[k].get('estat')}"); counts["NOU"] = counts.get("NOU", 0) + 1; continue
        if k not in pf:
            lines.append(f"ABSENT   {k:22s} (or={gold[k]['estat']})"); counts["ABSENT"] = counts.get("ABSENT", 0) + 1; continue
        v, msg = verdict(gold[k], pf[k], k)
        counts[v] = counts.get(v, 0) + 1
        if v != "OK":
            lines.append(f"{v:8s} {k:22s} {msg}")
    return lines, counts


def compare_taules(prod_path: Path, proj: str) -> tuple[list[str], dict]:
    sys.path.insert(0, str(REPO))
    from automation.lectura.contract import adapt_legacy
    gold = adapt_legacy(json.load(open(REPO / "docs/golden-read-taules" / proj / "_tables_decisions.json", encoding="utf-8")))["tables"]
    prod = json.load(open(prod_path, encoding="utf-8"))
    pt = prod["tables"]
    lines: list[str] = []
    counts: dict = {}
    for block in ("dpsh_tests", "sondeig_tests", "spt_ma_tests", "soil_levels"):
        g, p = gold.get(block) or {}, pt.get(block) or {}
        grows = g if isinstance(g, list) else (g.get("rows") or [])
        prows = p if isinstance(p, list) else (p.get("rows") or [])
        pairs, by_key = align_rows(block, grows, prows)
        lines.append(f"-- {block}: or {len(grows)} files / prod {len(prows)} files" + (" · alineades per clau" if by_key else ""))
        for i, (gr, pr) in enumerate(pairs):
            gr = _expand_de_a(gr) if block == "soil_levels" else gr
            for cell, gv in gr.items():
                if not isinstance(gv, dict) or "estat" not in gv:
                    continue
                pv = pr.get(cell)
                if not isinstance(pv, dict):
                    lines.append(f"ABSENT   {block}[{i}].{cell} (or={gv['estat']})"); counts["ABSENT"] = counts.get("ABSENT", 0) + 1; continue
                if cell == "n30" and pv.get("estat") == "segur":
                    lines.append(f"VIOLACIO {block}[{i}].n30 = segur (prohibit)"); counts["VIOLACIO"] = counts.get("VIOLACIO", 0) + 1
                v, msg = verdict(gv, pv, cell)
                counts[v] = counts.get(v, 0) + 1
                if v != "OK":
                    lines.append(f"{v:8s} {block}[{i}].{cell} {msg}")
    sl = (pt.get("soil_levels") or {}).get("rows") or []
    for i, r in enumerate(sl):
        lit = r.get("litologia") if isinstance(r.get("litologia"), dict) else None
        if lit and lit.get("estat") == "segur":
            lines.append(f"VIOLACIO soil_levels[{i}].litologia = segur (prohibit)"); counts["VIOLACIO"] = counts.get("VIOLACIO", 0) + 1
    return lines, counts


def main(argv: list[str]) -> int:
    kind = argv[1]
    prod = Path(argv[2]) if len(argv) > 2 else S / f"consolida-{kind}/_decisions.json"
    proj = argv[3] if len(argv) > 3 else DEFAULT_PROJ
    lines, counts = (compare_escalars if kind == "escalars" else compare_taules)(prod, proj)
    for line in lines:
        print(line)
    print("TOTALS:", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
