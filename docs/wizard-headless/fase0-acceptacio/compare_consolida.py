"""Acceptació Fase 0/12: compara `_decisions.json` produïts (agents `--consolida` o `consolidate.py`) vs l'or.

Ús: python3 compare_consolida.py escalars|taules [PATH_decisions.json] [CARPETA_PROJECTE_OR]
Veredictes per camp: OK (mateix estat, o candidats que solapen), CAUTELA (or segur -> produït candidats amb el bo dins;
o candidats -> produït candidats sense solapar, "candidats disjunts"; o no_trobat amb `fora_carpeta` que no coincideix),
ALERTA (produït més confiat que l'or, valor segur != or, o or/prod discrepants sense cap explicació), BUIT (or amb valor,
produït no_trobat: un forat honest, no un error), FORA (or no_trobat amb `fora_carpeta` que coincideix amb el candidat
produït: un valor correcte mesurat fora dels documents del projecte), NOU (clau v1 sense or), ERR (valor segur discrepant),
ABSENT (cel·la d'or sense cel·la produïda), VIOLACIO (regla dura: n30 / litologia mai segur).

v2 (2026-08-25, normalitzadors): `close(a, b, field)` és conscient del camp i del tipus de valor, en aquest ordre:
  1. adreces (`street_address`): `C/ARBRELLS 18A-18B-20` = `Carrer Arbrells, 18A, 18B i 20`; el conjunt de números de
     portal ha de coincidir — una lectura parcial (`Carrer Arbrells 18A`, o `C/ Arbrells` sense portal) NO és el mateix valor.
     Sense portals als dos costats: igualtat sense anotacions, mai contenció. Decisiu.
  2. `spt_ma` per comptes: `1/0` = `1/0/0` = `{n_spt:1, n_tp:0, n_ma:0}`; `--` = 0. Decisiu.
  3. dates senceres (ISO, D/M/A, `Octubre 2025`, `24 d'octubre de 2025`): mateix any/mes; dia igual o absent. Decisiu.
  4. nombres i intervals: `-4 m` = `-4,0 m`; `570.90 msnm` = `570,90`; fondàries en valor absolut (`ABS_FIELDS`):
     `1,0 - 1,2 m` = `-1,00 a -1,20 m`. Un guió entre dos dígits és separador d'interval, no signe. Decisiu.
  5. `num_floors`: `PB+PP` = `PB+1` = `Pb + p1`; anotacions fora; però `amb soterrani` ≠ `sense soterrani` (es llegeix a tota la cadena).
  6. `building_type`: conjunt de tokens (singular, abreviatures `hab`/`unif` esteses, articles i "construcció" fora);
     un conjunt inclòs a l'altre = CLOSE (memòria `feedback_building_type_close_match`: treure/afegir «aïllat» o un article és CLOSE;
     per tant una lectura parcial `habitatge unifamiliar` també passa com a CLOSE d'`… entre mitgeres` — decisió, no descuit; la regla més laxa del fitxer).
  7. text: la regla històrica (cadena normalitzada igual o continguda) i, si no, igualtat després de treure les
     anotacions `(...)` i ` -- nota` (doble guió; ` - text` és contingut).
Revisió adversària (Sonnet code-reviewer, 2026-08-25): 7 troballes → 6 corregides aquí (capa vegetal vs «Nivell N - Reblert», soterrani
a `num_floors`, milers `1.655,01`, guió simple, adreces sense via reconeguda / sense portal, `_expand_de_a`); la del `building_type` és decisió.

v3 (2026-08-31, Fix F del `PLA-PENDENTS-0B-0C-0D`): `verdict()` tenia dos forats que impedien mesurar els fixos D i E.
(1) `candidats` vs `candidats` donava sempre OK sense mirar els valors — ara compara els conjunts de candidats i, si no
solapen, `CAUTELA candidats disjunts`. (2) qualsevol combinació d'estats no prevista queia a `ALERTA` — un `no_trobat`
de producció contra un or amb valor és ara `BUIT` (rang 1, "no hem trobat res" ≠ "hem trobat un valor equivocat"), i un
`no_trobat` de l'or contra un `candidats` de producció és `FORA` (rang 0) quan l'or porta una anotació `fora_carpeta`
(un valor mesurat fora dels documents del projecte, p. ex. una consulta HTTP) que coincideix amb el primer candidat, o
`CAUTELA "fora, no coincideix"` si no hi coincideix; sense `fora_carpeta` es manté `ALERTA` (igual que abans).
v4 (2026-09-05, codi C de `mesures/runs/2026-09-03-mesura-8/_DIAGNOSTICS-INDEX.md`): 18 falsos ERR/ALERTA/CAUTELA
als 7 comparables de la mesura dels 8, tots de format del comparador, cap del sistema. (1) `parse_address`: el nom de
la via son NOMES els tokens abans del primer portal (el municipi/CP/urbanitzacio que ve despres no forma part de la
via: «C/ Clot de la Llacuna, 16, Linyola (25240)» = «Carrer Clot de la Llacuna, 16»; «Carrer Girasols, Nº7,
Urbanització el Roser» = «Carrer Girasols, 7 (Urb. El Roser)»), «C.» es reconeix com a tipus de via (el `\b` darrere
del punt no casava mai), el tipus de via es opcional si hi ha nom i portal, un numero de 5 xifres no es un portal
(CP) i `sta`/`st` = `santa`/`sant`. (2) `parse_numbers`: una unitat enganxada al numero («0,80-1,40m») i una nota
darrere d'una coma («+212,50 msnm, segons plànol en el ICGC») ja no trenquen la lectura numerica. (3) `close()` text:
contencio tambe despres de treure anotacions (≥ 3 caracters: `TPS (coneixement previ)` ⊂ `TPS, Prospecció del
Subsòl, SL`); les particules NO s'ignoren («Vilanova del Segrià» ≠ «Vilanova de Segrià» es un ERR real, D3). (4) `nivell_freatic`: un valor numeric = un text llarg
de humitat/aigua si la PRIMERA fondaria del text es aquell valor. (5) `num_floors`: porxo/porxada no es una planta;
«1 (planta baixa)» = «PB». (6) `building_type`: castella → catala (adosada/aislada/viviendas…), `unitat(s)` fora.
(7) `architect_name`/`client_name`: conjunt de noms, sense num. de col·legiat, telefon, honorific ni sufix « — despatx»
(igualtat estricta del conjunt: persona ≠ despatx continua sent diferent). (8) `flat_gold_scalars`: els candidats
compartits del camp niuat `cte` es reparteixen per subclau (C→`cte_edificacio`, T→`cte_sol`; els del `lab` es queden
sencers), i un or `candidats` sense valor ni candidats per a la subclau es `CAUTELA or sense valor`.
(9) `spt_ma_tests` s'alineen per `punt` quan es unic als dos costats (Vilanova: dos «SPT-1» a P-1 i P-3 creuats per
index). (10) Les columnes d'una taula que l'or te i prod NO emet a cap fila (`lab`, `id_estat`, `nom` pla…) es
llisten un cop com a `NOMES-OR` i no compten (abans, ABSENT per cel·la). `TOTALS` conserva les claus de sempre.
v5 (2026-09-06, STATUS §Pendents 2): `mostra_del_nivell` es compara com a booleà: el text de l'or «No (…)» / «Si …» =
False / True del consolidador (abans, «candidats disjunts» per format entre booleans i text).
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
PERSON_FIELDS = frozenset({"architect_name", "client_name"})
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
_NOTE_RE = re.compile(r"\s+--\s+(?=[A-Za-z])")


def strip_annot(s) -> str:
    """Treu anotacions: `(...)` i una nota final ` -- text` (doble guió; un sol guió és contingut: `Refús - trencament`)."""
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
_THOUSANDS_RE = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+,\d+(?![\d.,])")
_TRAILING_NOTE_RE = re.compile(r",\s+(?=[a-z])")   # `+212,50 msnm, segons plànol en el ICGC` → la nota no es valor
_GLUED_UNIT_RE = re.compile(r"(?<=\d)(?=[a-z])")    # `1,40m` → `1,40 m` (abans `_NUM_RE` hi llegia «1»)


def parse_numbers(s, absolute: bool = False) -> tuple | None:
    """Tupla de nombres si el valor és 'numèric' (comença per un nombre i la resta són unitats/partícules)."""
    t = _ascii(strip_annot(s)).lower()
    t = _TRAILING_NOTE_RE.split(t, maxsplit=1)[0]
    t = _GLUED_UNIT_RE.sub(" ", t)
    t = _THOUSANDS_RE.sub(lambda m: m.group(0).replace(".", ""), t)   # `1.655,01` → `1655,01`
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
_STREET_TYPES = (r"carrer|calle|cl|av|avinguda|avda|avenida|pl|placa|plaza|ctra|carretera|cami|camino|passeig|pg|paseo|"
                 r"ronda|rda|travessera|trav|rambla|poligon(?:\s+industrial)?|pol\.?\s*ind|partida|paratge|"
                 r"urbanitzacio|urbanizacion|urb|nau")
# «c.» i «c/» no acaben en lletra: el `\b` que hi havia darrere del punt no casava mai («C. Clot de la Llacuna»)
_STREET_RE = re.compile(r"^\s*(?:situat\s+(?:a|al)\s+)?(?:(?:" + _STREET_TYPES + r")(?![a-z])\.?/?|c/|c\.)?\s*(.*)$")
_ADDR_STOP = frozenset({"de", "del", "dels", "d", "l", "la", "el", "els", "les", "i", "y", "e"})
_ADDR_ABBR = {"sta": "santa", "st": "sant"}
_NUM_PORTAL_RE = re.compile(r"(?<!\d)\d{1,4}(?:\s?[a-z](?![a-z]))?(?!\d)")   # 5 xifres = codi postal, no portal


def parse_address(s) -> tuple | None:
    """(tokens del nom del carrer, conjunt de portals) si sembla '[tipus de via] nom + números'; si no, None.

    El nom de la via son els tokens ABANS del primer portal: el que ve despres (municipi, CP, urbanitzacio, pis)
    no forma part de la via i abans feia «vies diferents» de la mateixa adreca (Linyola, Alcoletge)."""
    t = _ascii(strip_annot(s)).lower()
    t = re.sub(r"\bn(?:[o°]|um(?:ero)?)?\.?\s*(?=\d)", " ", t)   # nº / num. / n. davant del número
    t = re.sub(r"^\s*c/", "carrer ", t)
    m = _STREET_RE.match(t)
    if not m:
        return None
    rest = m.group(1)
    first = _NUM_PORTAL_RE.search(rest)
    if not first:
        return None
    portals = frozenset(re.sub(r"\s", "", x) for x in _NUM_PORTAL_RE.findall(rest))
    name = tuple(_ADDR_ABBR.get(w, w) for w in re.findall(r"[a-z]+", rest[:first.start()]) if w not in _ADDR_STOP)
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
_BASEMENT_RE = re.compile(r"soterr|sotan|semisot|\bpsot\b|\bps\b|altell|entresol")
_NO_BASEMENT_RE = re.compile(r"(sense|sin|no)\s+(soterr|sotan|semisot|altell|entresol)")


def norm_floors(s) -> tuple[str, str | None]:
    """(nucli de plantes, indicador de soterrani/altell: 'amb' | 'sense' | None). El nucli és el que hi ha abans de la
    primera coma i fora d'anotacions; l'indicador es llegeix a TOTA la cadena (`PB+2, amb soterrani` ≠ `PB+2 (sense soterrani)`)."""
    full = _ascii(s).lower()
    core = re.sub(r"[^a-z0-9]+", "", _ascii(strip_annot(s)).lower().split(",", 1)[0])
    core = re.sub(r"porx(?:o|os|ada|ades)|porche", "", core)   # un porxo no es una planta (Rubí «PB + porxada»)
    core = core.replace("plantabaixa", "pb").replace("pbpp", "pb1").replace("pbp1", "pb1")
    core = re.sub(r"pp$", "1", core)
    if core == "1" and re.search(r"planta\s*baixa|planta\s*baja|\bpb\b", full):
        core = "pb"   # «1 (planta baixa)» = una planta = PB
    flag = "sense" if _NO_BASEMENT_RE.search(full) else ("amb" if _BASEMENT_RE.search(full) else None)
    return core, flag


_BT_STOP = frozenset({"de", "del", "dels", "d", "l", "la", "el", "els", "les", "un", "una", "uns", "unes", "i", "y",
                      "amb", "per", "a", "en", "the", "construccio", "constr", "edificacio", "edificio", "vivienda",
                      "unitat", "unitats", "unidad", "unidades"})
_BT_ABBR = {"hab": "habitatge", "habit": "habitatge", "vivienda": "habitatge", "viviendas": "habitatge",
            "unif": "unifamiliar", "unifam": "unifamiliar", "aill": "aillat", "plurif": "plurifamiliar",
            # castella → catala (Vilanova, Anciles: informes en castella)
            "adosada": "adossat", "adosado": "adossat", "adosadas": "adossat", "adosados": "adossat",
            "adossada": "adossat", "adossades": "adossat", "adossats": "adossat",
            "aislada": "aillat", "aislado": "aillat", "aisladas": "aillat", "aislados": "aillat",
            "aillada": "aillat", "aillades": "aillat", "aillats": "aillat",
            "unifamiliares": "unifamiliar", "plurifamiliares": "plurifamiliar",
            "pareada": "aparellat", "pareado": "aparellat", "aparellada": "aparellat",
            "medianeras": "mitgera", "mitgeres": "mitgera"}


def building_tokens(s) -> frozenset:
    out = set()
    for w in re.findall(r"[a-z0-9]+", _ascii(s).lower().replace("'", " ")):
        w = _BT_ABBR.get(w, w)
        if w.endswith("s") and len(w) > 4 and not w.endswith("ss"):
            w = w[:-1]
        if w not in _BT_STOP:
            out.add(w)
    return frozenset(out)


# --- persones (architect_name, client_name) -----------------------------------------------------------------------
_HONORIFICS = frozenset({"sr", "sra", "srta", "sres", "d", "dna", "don", "dona", "mr", "mrs", "ms"})
_COLLEGIATE_RE = re.compile(r"\bn(?:o|um\.?)?\s*\.?\s*col(?:\.|legiat|legiada|legiado)?\s*[\d.]+")   # nºCol. 6.408
_PHONE_RE = re.compile(r"(?<!\d)\d{9}(?!\d)")
_DASH_SUFFIX_RE = re.compile(r"\s-\s")   # « — A+M Arquitectura» (els guions llargs ja son «-» despres de `_ascii`)


def person_tokens(s) -> frozenset:
    """Conjunt de noms d'una persona o llista de persones: sense anotacions, num. de col·legiat, telefon,
    honorifics, particules ni el sufix « — despatx». Igualtat ESTRICTA del conjunt (persona ≠ despatx)."""
    t = _DASH_SUFFIX_RE.split(_ascii(strip_annot(s)).lower(), maxsplit=1)[0]
    t = _PHONE_RE.sub(" ", _COLLEGIATE_RE.sub(" ", t))
    return frozenset(w for w in re.findall(r"[a-z]+", t) if w not in _HONORIFICS and w not in _ADDR_STOP)


# --- nivell freatic -------------------------------------------------------------------------------------------------
_WATER_RE = re.compile(r"humit|humid|aigua|agua|freatic|nivell|nivel|\bn\.?f\b")


def first_depth(s) -> float | None:
    """Primera fondaria (valor absolut) dins d'un text llarg de nivell freatic; None si no n'hi ha cap."""
    t = _GLUED_UNIT_RE.sub(" ", _ascii(strip_annot(s)).lower())
    m = _NUM_RE.search(t)
    return abs(float(m.group(0).replace(",", "."))) if m else None


_YESNO_RE = re.compile(r"^(si|yes|true|no|false)(?![a-z])")


def yes_no(v) -> bool | None:
    """Booleà d'una cel·la `mostra_del_nivell`: True/False, o un text que comença per Sí/Si/No (sense anotacions):
    «No (la mostra s'assigna al 2on nivell pel material)» → False; «Si per interval estricte (…)» → True. Altrament None."""
    if isinstance(v, bool):
        return v
    m = _YESNO_RE.match(_ascii(strip_annot(v)).lower().strip())
    if not m:
        return None
    return m.group(1) in ("si", "yes", "true")


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
        if pa or pb:
            return False   # un costat amb portals i l'altre sense (`C/ Arbrells` vs `C/ Arbrells 18A-18B-20`) = lectura parcial
        sa, sb = norm(strip_annot(A)), norm(strip_annot(B))
        return bool(sa) and sa == sb   # cap contenció per a adreces (`Polígon X` vs `Polígon X, Nau 5`)
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
    if f == "nivell_freatic" and (na is None) != (nb is None):
        # «-1,00 m (humitat)» = «Humitat (…) — fondària de primera aparició -1,00 m; abast pintat fins a -1,40 m»
        num, txt = (na, B) if na is not None else (nb, A)
        if len(num) == 1 and _WATER_RE.search(_ascii(txt).lower()) and first_depth(txt) == num[0]:
            return True
    if f == "num_floors":
        (ca, ga), (cb, gb) = norm_floors(A), norm_floors(B)
        return bool(ca) and ca == cb and (ga == gb or ga is None or gb is None)
    if f == "building_type":
        ta, tb = building_tokens(A), building_tokens(B)
        return bool(ta and tb) and (ta <= tb or tb <= ta)
    if f == "mostra_del_nivell":
        ya, yb = yes_no(a), yes_no(b)
        if ya is not None and yb is not None:
            return ya == yb   # v5: «No (pel material)» de l'or = False del consolidador
    la, lb = norm(A), norm(B)
    if la == lb or (la and lb and (la in lb or lb in la)):
        return True
    sa, sb = norm(strip_annot(A)), norm(strip_annot(B))
    if sa and sa == sb:
        return True
    if len(sa) >= 3 and len(sb) >= 3 and (sa in sb or sb in sa):
        return True   # `TPS (coneixement previ)` ⊂ `TPS, Prospecció del Subsòl, SL`
    if f in PERSON_FIELDS:
        ta, tb = person_tokens(A), person_tokens(B)
        return bool(ta) and ta == tb
    return False


# --- or -----------------------------------------------------------------------------------------------------------
_CTE_SUBKEY_RE = {"cte_edificacio": re.compile(r"(?<![a-z0-9])c-?\d", re.I), "cte_sol": re.compile(r"(?<![a-z0-9])t-?\d", re.I)}


def subkey_candidates(field: str, sk: str, cands: list) -> list:
    """Reparteix la llista de candidats compartida d'un camp niuat entre les subclaus. Nomes `cte` (C→`cte_edificacio`,
    T→`cte_sol`): abans `cte_sol` de Castellar heretava el candidat «C0 (…)» i sortia «candidats disjunts». La del `lab`
    es queda sencera: les seves formes («MA (S-2) 2,8-3,0», «TPS (coneixement previ)») son lectures del mateix bloc del
    document i repartir-les pel valor de la subclau feia perdre solapaments legitims (`lab_sample_id` d'Anciles)."""
    if field != "cte":
        return cands
    rx = _CTE_SUBKEY_RE.get(sk)
    return [c for c in cands if rx is None or rx.search(str(c.get("value", "")))]


def flat_gold_scalars(proj: str) -> dict:
    d = json.load(open(REPO / "docs/golden-read" / proj / "_decisions.json", encoding="utf-8"))["decisions"]
    out = {}
    for k, v in d.items():
        st = v.get("status") or v.get("estat")
        if k in ("lab", "cte") and isinstance(v.get("value"), dict):
            # candidats no van per subclau al fixture (una sola llista per al camp niuat sencer): es reparteixen
            # per subclau (v4); `contract._flatten_nested_field` els copia sencers, aqui es filtren.
            for sk, sv in v["value"].items():
                out[sk] = {"estat": st, "value": sv}
                if isinstance(v.get("candidates"), list):
                    out[sk]["candidates"] = subkey_candidates(k, sk, v["candidates"])
        elif k == "utm_x_utm_y":
            m = re.search(r"X\s*([\d.]+)\s*;\s*Y\s*([\d.]+)", str(v.get("value", "")))
            out["utm_x"] = {"estat": st, "value": m.group(1) if m else v.get("value")}
            out["utm_y"] = {"estat": st, "value": m.group(2) if m else v.get("value")}
            if isinstance(v.get("candidates"), list):
                out["utm_x"]["candidates"] = out["utm_y"]["candidates"] = v["candidates"]
        else:
            out[k] = {"estat": st, "value": v.get("value")}
            if isinstance(v.get("candidates"), list):
                out[k]["candidates"] = v["candidates"]
            if isinstance(v.get("fora_carpeta"), dict):
                out[k]["fora_carpeta"] = v["fora_carpeta"]
    return out


def _expand_de_a(row: dict) -> dict:
    """Dialecte del fixture de Castellar: `de`/`a` plans + cel·la `de_a_estat` → cel·les `de` i `a` amb aquell estat."""
    cell = row.get("de_a_estat")
    if not isinstance(cell, dict) or "estat" not in cell:
        return row
    row = dict(row)
    row.pop("de_a_estat")
    de, a = row.get("de"), row.get("a")
    if (de is None or a is None) and isinstance(cell.get("value"), str):
        parts = re.split(r"(?<=[\d,.])\s+a\s+(?=[-+]?\d)", cell["value"], maxsplit=1)
        if len(parts) == 2:
            de, a = [x.strip() for x in parts]
    for k, v in (("de", de), ("a", a)):
        if not isinstance(v, dict) and v is not None:
            row[k] = {"estat": cell["estat"], "value": v, "candidates": [{"value": v, "font": "(de_a_estat del fixture)"}]}
    return row


_COVER_STRONG_RE = re.compile(r"vegetal|capa superior|no numerad|sense num|no numerat")
_COVER_WEAK_RE = re.compile(r"cobertura|reblert|relleno")   # només si no hi ha número de nivell (`Nivell 2 - Reblert` és n2)
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
        if _COVER_STRONG_RE.search(t):
            return "cover"
        m = _LEVEL_RE.search(t)
        if m:
            return f"n{m.group(1) or m.group(2)}"
        if _COVER_WEAK_RE.search(t):
            return "cover"
        return None
    if block == "spt_ma_tests":
        # per punt quan es unic als dos costats (Vilanova: dos «SPT-1», a P-1 i a P-3, creuats per index);
        # les etiquetes SPT-1/MA1 son massa variables per alinear-hi
        v = _plain(row.get("punt"))
        return norm(v) or None
    return None


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
        if ge == "candidats":
            gc = cand_values(gold) or ([gv] if gv is not None else [])
            pc = cand_values(prod) or ([pv] if pv is not None else [])
            if not gc:
                return "CAUTELA", f"or sense valor ni candidats per a la subclau; prod={pc!r}"
            if not (gc and pc and any(close(g, p, field) for g in gc for p in pc)):
                return "CAUTELA", f"candidats disjunts: or={gc!r} prod={pc!r}"
        return "OK", ""
    if ge == "segur" and pe == "candidats":
        if any(close(gv, c, field) for c in cand_values(prod)) or close(gv, pv, field):
            return "CAUTELA", f"or segur, prod candidats (bo dins): {gv!r}"
        return "ALERTA", f"or segur {gv!r} NO entre candidats {cand_values(prod)!r}"
    if ge == "candidats" and pe == "segur":
        ok = any(close(pv, c, field) for c in cand_values(gold)) or close(gv, pv, field)
        return "ALERTA", f"prod puja a segur ({pv!r}); or candidats" + ("" if ok else " i valor fora dels candidats d'or!")
    if pe == "no_trobat" and ge in ("segur", "candidats"):
        return "BUIT", f"(or={ge} {gv!r}; prod no_trobat)"
    if ge == "no_trobat" and pe == "candidats":
        fc = gold.get("fora_carpeta")
        if isinstance(fc, dict):
            fcv = fc.get("value")
            pcands = cand_values(prod)
            pc0 = pcands[0] if pcands else pv
            if close(fcv, pc0, field):
                return "FORA", f"fora de la carpeta: {fcv!r} ({fc.get('font', '')})"
            return "CAUTELA", f"fora de la carpeta, no coincideix: or={fcv!r} prod={pcands or [pv]!r}"
        return "ALERTA", f"estat or={ge} prod={pe} (or value={gv!r})"
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
        grows_x = [_expand_de_a(r) if block == "soil_levels" else r for r in grows]
        # columnes que l'or te com a cel·la i prod no emet a CAP fila (dialecte del fixture: `lab`, `id_estat`,
        # `nom` pla…): no es mesuren; es llisten un cop. Una fila sencera que falta continua sent ABSENT.
        prod_cols = {c for r in prows for c, v in r.items() if isinstance(v, dict) and "estat" in v}
        only_gold = sorted({c for r in grows_x for c, v in r.items() if isinstance(v, dict) and "estat" in v} - prod_cols) if prows else []
        if only_gold:
            n_only = sum(1 for r in grows_x for c in only_gold if isinstance(r.get(c), dict))
            lines.append(f"NOMES-OR {block}: {', '.join(only_gold)} ({n_only} cel·les de l'or que prod no emet a cap fila: no compten)")
            counts["NOMES_OR"] = counts.get("NOMES_OR", 0) + n_only
        for i, (gr, pr) in enumerate(pairs):
            gr = _expand_de_a(gr) if block == "soil_levels" else gr
            for cell, gv in gr.items():
                if not isinstance(gv, dict) or "estat" not in gv or cell in only_gold:
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
