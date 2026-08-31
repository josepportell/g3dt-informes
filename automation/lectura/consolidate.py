"""Fase 12 (via A, wizard headless) — consolidacio Python-first.

Vegeu `docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` §7.2 i
§10 (fila 12), i el Pas 3/3b/5/5b de `.claude/commands/g3dt-llegir-projecte.md`.

Substitueix la crida LLM `--consolida` sencera per una consolidacio determinista
sobre els `{doc}.json` (Pas 4), `_g3_templates.json`, `_inventory.json` i dues
fonts Python (nom de la carpeta, `COORDENADES.txt`) de `out_dir`, i deixa per a
una crida LLM curta (`--consolida --only-fields`, skill v1.5) NOMES els camps
amb conflicte real (dues fonts d'autoritat A que discrepen). Garanties:

1. **Cap senyal emes es perd**: cada entrada de `tier_a` (i cada cel·la de
   `tables`) esdeve candidat del seu `concept_id`/cel·la amb `font` + `quote`;
   si no cap als 3 candidats del contracte, queda a `altres` de la mateixa
   cel·la. Les entrades `NOT_*` queden a `descartats`. Els conceptes fora de
   les 22 claus queden a `extra_concepts` de l'arrel.
2. **Cap candidat inventat**: tot valor prove d'un senyal amb font documental.
   Les uniques derivacions son les que el skill sanciona explicitament (Pas 3)
   i porten sempre una `font` que comenca per `(derivat` o `(coneixement previ`
   o `(practica Eva`; mai pugen a `segur`.
3. **`segur` nomes** amb ≥ 1 font d'autoritat A sense cap contradiccio (Pas 5):
   A = senyal claude amb confianca ≥ 0,8, senyal `_g3_templates` amb confianca
   ≥ 0,9, o senyal Python determinista marcat com a tal; o be ≥ 3 documents
   independents amb confianca ≥ 0,6 que coincideixen. I cap guard de camp que
   ho prohibeixi (n30/litologia mai; derivats mai; `referencia_catastral`
   sense consulta del Cadastre mai; `num_soil_levels` sense annex mai; …).
4. La sortida passa `contract.validate_decisions` NETA.

Aquest modul llegeix fitxers (JSON de `out_dir`, `COORDENADES.txt` del
projecte) pero NO n'escriu cap: el runner escriu `_decisions.json`.
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from automation.lectura.contract import ALLOWED_FIELD_KEYS, TABLE_ROW_GROUPS, VALID_ESTATS
from automation.lectura.normalize import ROW_KEY_ALIASES, ROW_REQUIRED_KEYS

CONSOLIDATOR_VERSION = "python-1.0"

_RESERVED_JSON_NAMES = {
    "_inventory.json", "_g3_templates.json", "_decisions.json", "_job.json", "_consolida_only.json",
}

#: Llindars d'autoritat (docstring, punt 3).
A_CONF_CLAUDE = 0.8
A_CONF_G3 = 0.9
#: Un senyal d'un altre cluster amb confianca ≥ aquest valor es una contradiccio que bloqueja `segur`.
CONTRADICTION_CONF = 0.4
#: Convergencia: ≥ N documents independents amb confianca ≥ CONV_CONF i cap contradiccio → segur.
CONV_MIN_DOCS = 3
CONV_CONF = 0.6
MAX_CANDIDATES = 3

#: Camps on les aparicions "derivades de l'encarrec" NO son fonts independents entre elles (Pas 3, client_name).
_ENCARREC_FAMILY_FIELDS = frozenset({"client_name", "architect_name", "architect_company"})
_ENCARREC_DOC_TYPES = frozenset({
    "pressupost_g3", "fitxa_camp_g3", "comanda_lab_g3", "plan_cost_g3", "correu", "annex_sondeig", "annex_dpsh",
    "annex_tall", "annex_planol_situacio", "annex_fotografies", "informe_laboratori", "full_camp_manuscrit",
})

#: Llindar de contradiccio per camp (Pas 3: el formulari p.5 de l'acceptacio MANA sobre sol·licitants i versions velles).
_BLOCK_CONF_BY_FIELD = {"client_name": 0.6}

#: Camps que MAI son `segur` (Pas 3 / Pas 5).
_NEVER_SEGUR_FIELDS = frozenset({"cte_edificacio", "cte_sol"})

#: Camps numerics on el signe no compta (fondaries).
_ABS_FIELDS = frozenset({"lab_depth"})

_STOPWORDS = frozenset({
    "de", "del", "dels", "la", "el", "els", "les", "i", "y", "a", "en", "al", "d", "l", "s", "n", "c", "cl", "cr",
    "carrer", "calle", "c/", "av", "avinguda", "avda", "num", "no", "nº", "n°", "numero", "número", "the",
})
_UNIT_TOKENS = frozenset({
    "m", "ml", "msnm", "m2", "cm", "mm", "mts", "metres", "metros", "aprox", "ca", "msn", "e", "x", "y", "n", "z",
})

_NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
_PAREN_RE = re.compile(r"\([^)]*\)")
_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})(?:-(\d{1,2}))?\b")
_DATE_DMY_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_MONTHS = {
    "gener": 1, "enero": 1, "febrer": 2, "febrero": 2, "marc": 3, "març": 3, "marzo": 3, "abril": 4, "maig": 5,
    "mayo": 5, "juny": 6, "junio": 6, "juliol": 7, "julio": 7, "agost": 8, "agosto": 8, "setembre": 9,
    "septiembre": 9, "octubre": 10, "novembre": 11, "noviembre": 11, "desembre": 12, "diciembre": 12,
}
# dia opcional + mes + any, TOTA la cadena (fullmatch): "maig 2025" | "maig de 2025" | "7 de maig de 2025"
_DATE_MONTH_RE = re.compile(r"^(?:(\d{1,2})\s+(?:de\s+)?)?([a-zç]+)\s+(?:de\s+)?(\d{4})$", re.IGNORECASE)
# guio entre dos digits = separador d'interval ("1,5-1,75"), no signe ("-1,20", precedit d'espai o inici de cadena)
_RANGE_DASH_RE = re.compile(r"(?<=\d)\s*-\s*(?=\d)")

_EXPEDIENT_FOLDER_RE = re.compile(r"^\s*(\d{7})\b")
_POINT_RE = re.compile(r"([PS])\s*[-_. ]?\s*(\d+)", re.IGNORECASE)
_LEVEL_RE = re.compile(r"nivell\s*(\d+)|(\d+)\s*(?:er|on|n|r|è|a|º)?\s*nivell", re.IGNORECASE)
_COVER_RE = re.compile(r"vegetal|cobertura|reblert|relleno|terra vegetal", re.IGNORECASE)
_NF_ABSENT_RE = re.compile(
    r"^\s*(no\s*(detectat|detectad[oa]|indicat|indicad[oa]|consta|apareix|observat|s'ha detectat|hi ha|n'hi ha)?"
    r"|cap marca|cap|casella buida|columna buida|buit|buida|en blanc|sense marca|absent|-|—|n/?d|no)\s*\.?\s*$",
    re.IGNORECASE,
)
_YES_RE = re.compile(r"^\s*(si|sí|s|yes|true|rebuig)\b", re.IGNORECASE)
_NO_RE = re.compile(r"^\s*(no|n|false)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Senyals
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    concept: str
    value: Any
    font: str
    quote: str
    confidence: float
    doc: str
    doc_type: str
    origin: str  # "claude" | "g3_templates" | "python" | "derivat"
    note: str | None = None
    is_a: bool = False
    independent: bool = True
    extra: dict = field(default_factory=dict)

    def as_candidate(self) -> dict:
        c = {"value": self.value, "font": self.font, "quote": self.quote or ""}
        if self.note:
            c["note"] = self.note
        if self.extra:
            c["extra"] = copy.deepcopy(self.extra)
        return c


def _is_a(origin: str, confidence: float, forced: bool | None = None) -> bool:
    if forced is not None:
        return forced
    if origin == "g3_templates":
        return confidence >= A_CONF_G3
    if origin == "claude":
        return confidence >= A_CONF_CLAUDE
    return False


# ---------------------------------------------------------------------------
# Normalitzacio de valors (claus de compatibilitat)
# ---------------------------------------------------------------------------


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _strip_parens(s: str) -> str:
    """Treu els parentesis que son OBSERVACIONS (contenen espai o ≥ 5 caracters); conserva els curts
    que son part del valor ('MA-1 (S1)', '(P)')."""
    return _PAREN_RE.sub(lambda m: " " if (" " in m.group(0) or len(m.group(0)) >= 7) else m.group(0), s)


def _parse_date(s: str) -> tuple | None:
    """Retorna ("date", y, m, d|None) si TOTA la cadena (fora de parèntesis d'observació) es una data.

    `fullmatch`, no `search`: una cadena amb un nombre a més de la data ("1.5-1.75") no es data — abans
    `_DATE_DMY_RE.search` hi trobava "5-1.75" i la llegia com a 2075-01-05 (forat `value_key`, 2026-08-31)."""
    t = _strip_parens(s).strip()
    m = _DATE_ISO_RE.fullmatch(t)
    if m and len(_NUM_RE.findall(t)) <= 3:
        y, mo, d = int(m.group(1)), int(m.group(2)), (int(m.group(3)) if m.group(3) else None)
        if 1 <= mo <= 12 and (d is None or 1 <= d <= 31):
            return ("date", y, mo, d)
    m = _DATE_DMY_RE.fullmatch(t)
    if m and len(_NUM_RE.findall(t)) <= 3:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return ("date", y, mo, d)
    m = _DATE_MONTH_RE.fullmatch(_ascii(t).lower())
    if m and m.group(2) in {_ascii(k) for k in _MONTHS}:
        mo = next(v for k, v in _MONTHS.items() if _ascii(k) == m.group(2))
        d = int(m.group(1)) if m.group(1) else None
        return ("date", int(m.group(3)), mo, d)
    return None


def _numbers(s: str) -> tuple[float, ...]:
    t = _RANGE_DASH_RE.sub(" ", _strip_parens(s))
    return tuple(round(float(x.replace(",", ".")), 3) for x in _NUM_RE.findall(t))


def _text_tokens(s: str) -> list[str]:
    t = _ascii(_strip_parens(s)).lower()
    # guions/punts/guions baixos ENTRE alfanumerics enganxen ('S-1' → 's1', '18A-18B-20' → '18a18b20');
    # la resta de signes separen ('C/ARBRELLS' → 'c arbrells')
    t = re.sub(r"(?<=[a-z0-9])[-_.](?=[a-z0-9])", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return [w for w in t.split() if w and w not in _STOPWORDS]


def _is_numeric_like(s: str) -> bool:
    """Un valor 'numeric' comenca per un nombre (despres de signes/aprox.) i el text que el segueix son unitats/observacions."""
    t = _strip_parens(s).strip()
    t = re.sub(r"^[≈~<>≤≥+\-\s]+", "", t)
    if not re.match(r"\d", t):
        return False
    toks = _text_tokens(t)
    nums = [w for w in toks if re.fullmatch(r"\d+(?:[.,]\d+)?", w)]
    return bool(nums) and all(re.fullmatch(r"\d+(?:[.,]\d+)?", w) or w in _UNIT_TOKENS or len(w) <= 4 for w in toks)


def value_key(value: Any, *, abs_numbers: bool = False, field_name: str | None = None) -> tuple:
    """Clau de compatibilitat d'un valor: ("none",) | ("bool", b) | ("date", y, m, d) |
    ("num", (n, ...)) | ("text", "cadena")."""
    if value is None:
        return ("none",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        n = abs(float(value)) if abs_numbers else float(value)
        return ("num", (round(n, 3),))
    if isinstance(value, dict):
        return ("text", json.dumps(value, sort_keys=True, ensure_ascii=False))
    if isinstance(value, list):
        return ("text", "|".join(str(x) for x in value))
    s = str(value).strip()
    if not s:
        return ("none",)
    d = _parse_date(s)
    if d:
        return d
    if _is_numeric_like(s):
        nums = _numbers(s)
        if abs_numbers:
            nums = tuple(abs(n) for n in nums)
        return ("num", nums)
    txt = "".join(_text_tokens(s))
    if field_name == "num_floors":
        txt = txt.replace("pbpp", "pb1").replace("pp", "1")
    if field_name in ("rebuig",):
        if _YES_RE.match(s):
            return ("text", "si")
        if _NO_RE.match(s):
            return ("text", "no")
    return ("text", txt)


def keys_compatible(a: tuple, b: tuple) -> bool:
    if a == b:
        return True
    if a[0] != b[0]:
        return False
    if a[0] == "date":
        if a[1] != b[1] or a[2] != b[2]:
            return False
        return a[3] is None or b[3] is None or a[3] == b[3]
    if a[0] == "num":
        return a[1] == b[1]
    if a[0] == "text":
        x, y = a[1], b[1]
        if min(len(x), len(y)) < 3:
            return False
        # prefix o sufix (lectura parcial del mateix valor), NO contencio interior:
        # 'entre el carrer X i el carrer Y' no fusiona X amb Y
        return x.startswith(y) or y.startswith(x) or x.endswith(y) or y.endswith(x)
    return False


def _iso_date(key: tuple) -> str | None:
    if key[0] == "date" and key[3] is not None:
        return f"{key[1]:04d}-{key[2]:02d}-{key[3]:02d}"
    return None


# ---------------------------------------------------------------------------
# Clustering + decisio d'una cel·la
# ---------------------------------------------------------------------------


@dataclass
class Cluster:
    key: tuple
    signals: list[Signal] = field(default_factory=list)

    @property
    def has_a(self) -> bool:
        return any(s.is_a for s in self.signals)

    @property
    def max_conf(self) -> float:
        return max((s.confidence for s in self.signals), default=0.0)

    @property
    def sum_conf(self) -> float:
        return sum(s.confidence for s in self.signals)

    def n_docs(self, family_field: bool) -> int:
        docs: set[str] = set()
        for s in self.signals:
            if family_field and s.doc_type in _ENCARREC_DOC_TYPES and not s.is_a:
                docs.add("(encarrec)")
            elif s.origin == "g3_templates" and family_field:
                docs.add("(encarrec)")
            else:
                docs.add(s.doc)
        return len(docs)

    @property
    def is_derived_only(self) -> bool:
        return all(s.origin == "derivat" for s in self.signals)


def cluster_signals(sigs: list[Signal], *, abs_numbers: bool = False, field_name: str | None = None) -> list[Cluster]:
    """Agrupa senyals per compatibilitat (union-find) i ordena els clusters per pes."""
    keys = [value_key(s.value, abs_numbers=abs_numbers, field_name=field_name) for s in sigs]
    parent = list(range(len(sigs)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            if keys[i][0] != "none" and keys_compatible(keys[i], keys[j]):
                parent[find(i)] = find(j)

    groups: dict[int, Cluster] = {}
    for i, s in enumerate(sigs):
        if keys[i][0] == "none":
            continue
        r = find(i)
        if r not in groups:
            groups[r] = Cluster(key=keys[i])
        groups[r].signals.append(s)
    clusters = list(groups.values())
    family = field_name in _ENCARREC_FAMILY_FIELDS
    clusters.sort(key=lambda c: (c.has_a, c.n_docs(family), c.sum_conf, c.max_conf), reverse=True)
    for c in clusters:
        # representant de la clau = la clau mes completa (data amb dia, text mes llarg)
        best = max((value_key(s.value, abs_numbers=abs_numbers, field_name=field_name) for s in c.signals),
                   key=lambda k: (k[0] == "date" and k[3] is not None, len(str(k))))
        c.key = best
    return clusters


def _prefer_form(s: Signal) -> tuple:
    """Ordre de preferencia del text visible d'un candidat dins d'un cluster."""
    v = str(s.value) if not isinstance(s.value, (dict, list)) else json.dumps(s.value, ensure_ascii=False)
    all_caps = v.isupper()
    has_unit = bool(re.search(r"\d\s*(m|msnm|m2)\b", v))
    return (s.is_a, s.origin != "derivat", s.confidence, not all_caps, has_unit, s.origin == "claude", len(v))


def _distinct_candidates(cluster_order: list[Cluster], limit: int = MAX_CANDIDATES, *, abs_numbers: bool = False,
                         field_name: str | None = None) -> tuple[list[dict], list[dict]]:
    """Candidats (≤ limit) = formes distintes, primer una per cluster (ordre de pes),
    despres formes alternatives dins del primer cluster. La resta va a `altres`."""
    chosen: list[Signal] = []
    seen: set[str] = set()

    def push(s: Signal) -> None:
        k = json.dumps(s.value, ensure_ascii=False, sort_keys=True).lower() if isinstance(s.value, (dict, list)) \
            else str(s.value).strip().lower()
        if k in seen:
            return
        seen.add(k)
        chosen.append(s)

    def ordered_forms(c: Cluster) -> list[Signal]:
        # dins d'un cluster, primer les formes de la clau mes COMPLETA (les claus mes curtes son lectures parcials)
        by_key: dict[tuple, list[Signal]] = {}
        for s in c.signals:
            by_key.setdefault(value_key(s.value, abs_numbers=abs_numbers, field_name=field_name), []).append(s)
        keys = sorted(by_key, key=lambda k: (any(s.is_a for s in by_key[k]), len(str(k))), reverse=True)
        out: list[Signal] = []
        for k in keys:
            out.extend(sorted(by_key[k], key=_prefer_form, reverse=True))
        return out

    forms = {id(c): ordered_forms(c) for c in cluster_order}
    for c in cluster_order:
        push(forms[id(c)][0])
    for c in cluster_order:
        for s in forms[id(c)][1:]:
            push(s)
    candidates = [s.as_candidate() for s in chosen[:limit]]
    altres = [s.as_candidate() for s in chosen[limit:]]
    # senyals amb la mateixa forma que un candidat: es conserven a `altres` com a suport (font/quote)
    chosen_ids = {id(s) for s in chosen}
    for c in cluster_order:
        for s in c.signals:
            if id(s) not in chosen_ids:
                altres.append(s.as_candidate())
    return candidates, altres


def decide(
    sigs: list[Signal],
    *,
    sources_checked: list[str],
    field_name: str | None = None,
    abs_numbers: bool = False,
    never_segur: bool = False,
    segur_requires: Any = None,
    conflicts: list[dict] | None = None,
    path: str = "",
    table_cell: bool = False,
) -> dict:
    """Decideix una cel·la (camp de `fields` o cel·la de fila de `tables`) segons el Pas 5.

    `segur_requires(cluster) -> bool|str`: guard addicional; retorna False (o un motiu str) per prohibir `segur`.
    """
    sigs = [s for s in sigs if s is not None]
    if not sigs or all(value_key(s.value)[0] == "none" for s in sigs):
        cell = {"estat": "no_trobat", "value": None, "sources_checked": list(sources_checked) or ["cap font"]}
        notes = [s.note for s in sigs if s.note]
        if notes:
            cell["note"] = " | ".join(dict.fromkeys(notes))
        return cell

    clusters = cluster_signals(sigs, abs_numbers=abs_numbers, field_name=field_name)
    if not clusters:
        return {"estat": "no_trobat", "value": None, "sources_checked": list(sources_checked) or ["cap font"]}

    top = clusters[0]
    family = field_name in _ENCARREC_FAMILY_FIELDS
    # Camps: qualsevol senyal amb confianca ≥ 0,4 (la confianca del skill es semantica) contradiu.
    # Cel·les de taula: nomes els documents d'autoritat A de la cel·la (Pas 3b) contradiuen; la resta son corroboracio.
    if table_cell:
        blockers = [c for c in clusters[1:] if c.has_a and not c.is_derived_only]
    else:
        thr = _BLOCK_CONF_BY_FIELD.get(field_name or "", CONTRADICTION_CONF)
        blockers = [c for c in clusters[1:] if (c.has_a or c.max_conf >= thr) and not c.is_derived_only]
    # conflicte real = dues fonts A de DOCUMENTS DIFERENTS discrepen (dues alternatives del mateix document son una cautela del lector)
    top_a_docs = {s.doc for s in clusters[0].signals if s.is_a}
    a_conflict = [c for c in blockers if c.has_a and not ({s.doc for s in c.signals if s.is_a} & top_a_docs)]
    a_keys = {value_key(s.value, abs_numbers=abs_numbers, field_name=field_name) for s in top.signals if s.is_a}

    reasons: list[str] = []
    estat = "candidats"
    if never_segur:
        reasons.append("guard: mai segur per a aquesta cel·la")
    elif top.is_derived_only:
        reasons.append("nomes candidats derivats/coneixement previ")
    elif blockers:
        reasons.append("contradiccio: " + "; ".join(
            f"{_short(c.signals[0].value)} ({c.n_docs(family)} doc, conf max {c.max_conf:.2f})" for c in blockers[:3]))
    elif len(a_keys) > 1:
        reasons.append("formes diferents entre fonts A (compatibles per prefix): candidats amb totes les formes")
    else:
        strong_docs = {s.doc for s in top.signals if s.confidence >= CONV_CONF or s.is_a}
        if family:
            strong_docs = {("(encarrec)" if s.doc_type in _ENCARREC_DOC_TYPES or s.origin == "g3_templates" else s.doc)
                           for s in top.signals if s.confidence >= CONV_CONF or s.is_a}
        converge = len(strong_docs) >= CONV_MIN_DOCS
        if top.has_a or converge:
            guard = segur_requires(top) if segur_requires else True
            if guard is True or guard is None:
                estat = "segur"
                reasons.append("1 font A sense contradiccio" if top.has_a else
                               f"convergencia de {len(strong_docs)} documents independents (conf ≥ {CONV_CONF})")
            else:
                reasons.append(f"guard: {guard}" if isinstance(guard, str) else "guard de camp")
        else:
            reasons.append("cap font d'autoritat A (conf < 0,8) i sense convergencia de 3 documents")

    if a_conflict and conflicts is not None:
        conflicts.append({
            "path": path, "why": "dues fonts d'autoritat A discrepen",
            "clusters": [{"value": _short(c.signals[0].value), "fonts": [s.font for s in c.signals][:3]} for c in [top] + a_conflict],
        })

    if estat == "segur":
        # segur: els candidats son les formes del cluster guanyador (d'on surt el valor); les alternatives
        # no bloquejants (conf < llindar) van a `altres`, perque la UI no mostri "segur" amb un valor diferent al costat
        candidates, altres = _distinct_candidates([top], abs_numbers=abs_numbers, field_name=field_name)
        for c in clusters[1:]:
            altres.extend(s.as_candidate() for s in sorted(c.signals, key=_prefer_form, reverse=True))
    else:
        candidates, altres = _distinct_candidates(clusters, abs_numbers=abs_numbers, field_name=field_name)
    value = candidates[0]["value"]
    iso = _iso_date(top.key)
    if iso and estat == "segur":
        # canonicalitzacio de FORMAT (no de contingut): la data en ISO, la cita conserva la forma original
        value = iso
        candidates[0]["value"] = iso
    cell: dict[str, Any] = {"estat": estat, "value": value, "candidates": candidates}
    if estat == "candidats":
        cell["value"] = candidates[0]["value"]
    cell["rule"] = "; ".join(reasons)
    if altres:
        cell["altres"] = altres
    cell["sources_checked"] = list(sources_checked)
    notes = [s.note for s in top.signals if s.note]
    if notes:
        cell["note"] = notes[0]
    return cell


def _short(v: Any, n: int = 40) -> str:
    s = str(v) if not isinstance(v, (dict, list)) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Carrega dels JSON de `out_dir`
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


@dataclass
class Corpus:
    docs: list[dict] = field(default_factory=list)          # {doc}.json (Pas 4)
    g3: dict | None = None
    inventory: dict | None = None
    docs_read: list[str] = field(default_factory=list)
    lectura_fallida: list[str] = field(default_factory=list)
    duplicates: dict[str, str] = field(default_factory=dict)  # path -> path canonic (mateix md5)


def load_corpus(out_dir: Path) -> Corpus:
    out_dir = Path(out_dir)
    corpus = Corpus()
    g3 = _load_json(out_dir / "_g3_templates.json")
    if isinstance(g3, dict):
        corpus.g3 = g3
        corpus.docs_read.append("_g3_templates.json")
    inv = _load_json(out_dir / "_inventory.json")
    if isinstance(inv, dict):
        corpus.inventory = inv
    seen_md5: dict[str, str] = {}
    for p in sorted(out_dir.glob("*.json")):
        if p.name in _RESERVED_JSON_NAMES or p.name.startswith("_"):
            continue
        d = _load_json(p)
        if not isinstance(d, dict):
            continue
        d.setdefault("source_path", p.stem)
        md5 = d.get("source_md5")
        if md5 and md5 in seen_md5:
            corpus.duplicates[d["source_path"]] = seen_md5[md5]
            continue
        if md5:
            seen_md5[md5] = d["source_path"]
        corpus.docs.append(d)
        corpus.docs_read.append(d["source_path"])
    if corpus.inventory:
        have = {d.get("source_path") for d in corpus.docs}
        for f in corpus.inventory.get("files", []) or []:
            if f.get("route") == "claude" and f.get("path") not in have and f.get("path") not in corpus.duplicates:
                # duplicat per md5 dins l'inventari (el runner no el llegeix): no es una lectura fallida
                dup_of = _inventory_duplicate_of(corpus.inventory, f)
                if dup_of and dup_of in have:
                    corpus.duplicates[f["path"]] = dup_of
                    continue
                corpus.lectura_fallida.append(f.get("path", "?"))
    return corpus


def _inventory_duplicate_of(inv: dict, f: dict) -> str | None:
    md5 = f.get("md5")
    if not md5:
        return None
    for g in inv.get("files", []) or []:
        if g is not f and g.get("md5") == md5 and g.get("route") == "claude" and g.get("path") != f.get("path"):
            return g.get("path")
    dups = inv.get("duplicates")
    if isinstance(dups, dict):
        for canon, others in dups.items():
            if isinstance(others, list) and f.get("path") in others:
                return canon
    return None


# ---------------------------------------------------------------------------
# Senyals de camps (fields)
# ---------------------------------------------------------------------------

_LAB_SUBKEYS = ("lab_testing_company", "lab_sample_id", "lab_depth", "lab_location")
_CTE_SUBKEYS = ("cte_edificacio", "cte_sol")
_UTM_PAIR_RE = re.compile(r"(\d{6,7}(?:[.,]\d+)?)\D+(\d{7}(?:[.,]\d+)?)")


def _split_utm(value: Any) -> tuple[Any, Any] | None:
    if isinstance(value, dict):
        x = value.get("utm_x", value.get("x"))
        y = value.get("utm_y", value.get("y"))
        return (x, y) if x is not None or y is not None else None
    m = _UTM_PAIR_RE.search(str(value))
    if m:
        return m.group(1), m.group(2)
    return None


def collect_field_signals(corpus: Corpus, project_path: Path | None) -> tuple[dict[str, list[Signal]], dict, dict, dict]:
    """Retorna (senyals per clau plana, descartats NOT_*, extra_concepts, not_present per clau)."""
    by_key: dict[str, list[Signal]] = {k: [] for k in ALLOWED_FIELD_KEYS}
    descartats: dict[str, list[dict]] = {}
    extra: dict[str, list[dict]] = {}
    not_present: dict[str, list[str]] = {k: [] for k in ALLOWED_FIELD_KEYS}

    def add(concept: str, sig: Signal) -> None:
        if concept in by_key:
            by_key[concept].append(sig)
        else:
            extra.setdefault(concept, []).append(sig.as_candidate() | {"doc": sig.doc})

    def add_entry(concept: str, value: Any, font: str, quote: str, conf: float, doc: str, doc_type: str,
                  origin: str, note: str | None, forced_a: bool | None = None) -> None:
        if not concept:
            return
        if concept.startswith("NOT_"):
            descartats.setdefault(concept[4:], []).append({"value": value, "font": font, "quote": quote, "note": note})
            return
        if concept == "utm_x_utm_y" or concept == "utm":
            pair = _split_utm(value)
            if pair:
                for k, v in zip(("utm_x", "utm_y"), pair):
                    if v is not None:
                        add(k, Signal(k, v, font, quote, conf, doc, doc_type, origin, note, _is_a(origin, conf, forced_a)))
                return
        if concept in ("lab", "cte") and isinstance(value, dict):
            for k in (_LAB_SUBKEYS if concept == "lab" else _CTE_SUBKEYS):
                if value.get(k) is not None:
                    add(k, Signal(k, value[k], font, quote, conf, doc, doc_type, origin, note, _is_a(origin, conf, forced_a)))
            return
        add(concept, Signal(concept, value, font, quote, conf, doc, doc_type, origin, note, _is_a(origin, conf, forced_a)))

    # 1. _g3_templates.json
    if corpus.g3:
        for concept, cands in (corpus.g3.get("concepts") or {}).items():
            for c in cands if isinstance(cands, list) else []:
                if not isinstance(c, dict):
                    continue
                conf = float(c.get("confidence") or 0.0)
                src = c.get("source", "_g3_templates")
                add_entry(concept, c.get("value"), f"{src} {c.get('location', '')}".strip(), c.get("quote", ""),
                          conf, src, c.get("document_type", "g3"), "g3_templates", c.get("note"))

    # 2. {doc}.json (Pas 4)
    for d in corpus.docs:
        src = d.get("source_path", "?")
        dtype = d.get("document_type", "altre")
        for e in d.get("tier_a") or []:
            if not isinstance(e, dict):
                continue
            conf = float(e.get("confidence") or 0.0)
            add_entry(e.get("concept_id"), e.get("value"), f"{src} {e.get('location', '')}".strip(),
                      e.get("quote", "") or "", conf, src, dtype, "claude", e.get("note"))
        for k in d.get("not_present") or []:
            if isinstance(k, str) and k in not_present:
                not_present[k].append(src)

    # 3. fonts Python deterministes
    if project_path is not None:
        for sig in python_signals(Path(project_path)):
            add(sig.concept, sig)

    return by_key, descartats, extra, not_present


def python_signals(project_path: Path) -> list[Signal]:
    """Senyals deterministes que cap lector LLM ha d'emetre: nom de la carpeta (expedient) i COORDENADES.txt."""
    out: list[Signal] = []
    name = project_path.name
    m = _EXPEDIENT_FOLDER_RE.match(name)
    if m:
        out.append(Signal("expedient", m.group(1), "nom de la carpeta del projecte", name, 0.9, "(carpeta)",
                          "carpeta", "python", "regla Pas 3: nom de la carpeta = NNNNNNN MUNICIPI", is_a=True))
    for coord in sorted(project_path.rglob("COORDENADES*.txt")):
        try:
            rel = str(coord.relative_to(project_path))
            points = parse_coordenades(coord.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not points:
            continue
        first = next((p for p in points if p["punt"].upper() in ("P-1", "P1")), points[0])
        note_pts = ", ".join(f"{p['punt']} {p['x']}/{p['y']}" for p in points)
        out.append(Signal("utm_x", first["x"], f"{rel} ({first['punt']})", first["raw"], 0.9, rel, "coordenades_gps",
                          "python", f"regla Pas 3: UTM de l'informe = P-1 de COORDENADES.txt; punts: {note_pts}",
                          is_a=True, extra={"punts": points}))
        out.append(Signal("utm_y", first["y"], f"{rel} ({first['punt']})", first["raw"], 0.9, rel, "coordenades_gps",
                          "python", f"regla Pas 3: UTM de l'informe = P-1 de COORDENADES.txt; punts: {note_pts}",
                          is_a=True, extra={"punts": points}))
        if first.get("z") is not None:
            out.append(Signal("cota_referencia", first["z"], f"{rel} ({first['punt']} z)", first["raw"], 0.5, rel,
                              "coordenades_gps", "python",
                              "GPS de camp: l'Eva no l'usa com a cota de referencia (~0,6 m de diferencia amb l'ICGC)"))
        break
    return out


def parse_coordenades(text: str) -> list[dict]:
    """`Coordenades UTM (X);(Y);(Z);` + blocs `P-1` / `x ; y ; z`."""
    points: list[dict] = []
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"[PS]\s*-?\s*\d+", line, re.IGNORECASE):
            current = line.upper().replace(" ", "")
            if "-" not in current:
                current = current[0] + "-" + current[1:]
            continue
        nums = [x.strip() for x in re.split(r"[;\s]+", line) if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", x.strip())]
        if current and len(nums) >= 2:
            points.append({"punt": current, "x": nums[0], "y": nums[1], "z": nums[2] if len(nums) > 2 else None,
                           "raw": f"{current}: {line}"})
            current = None
    return points


# ---------------------------------------------------------------------------
# Guards de camp (Pas 3)
# ---------------------------------------------------------------------------


def _guard_for_field(key: str, decided: dict[str, dict]) -> Any:
    def architect(top: Cluster) -> Any:
        forms = {str(s.value).strip().lower() for s in top.signals}
        if len(forms) > 1 and any("arquitect" in f for f in forms) and any("arquitect" not in f for f in forms):
            return "persona i despatx a la vegada (Pas 3): mai segur"
        client = decided.get("client_name", {}).get("value")
        if client and any(keys_compatible(value_key(client), value_key(s.value)) for s in top.signals):
            return "coincideix amb client_name: practica Eva, mai segur"
        return True

    def client(top: Cluster) -> Any:
        if any("arquitect" in str(s.value).lower() for s in top.signals):
            return "el nom conte ARQUITECT (sol·licitant, Pas 3): mai segur"
        if any(re.search(r"\bG\s?3\b|B25364589", str(s.value), re.IGNORECASE) for s in top.signals):
            return "G3 mai es client"
        return True

    def cadastre(top: Cluster) -> Any:
        if not any(s.doc_type == "consulta_cadastre" or "cadastr" in s.doc.lower() or "catastr" in s.doc.lower()
                   for s in top.signals):
            return "sense consulta del Cadastre a la carpeta (Pas 3): mai segur"
        return True

    def soil_levels(top: Cluster) -> Any:
        if not any(s.doc_type in ("annex_sondeig", "annex_tall") for s in top.signals):
            return "sense annex de sondeig ni tall (Pas 3): candidats + confirmar"
        return True

    def num_floors(top: Cluster) -> Any:
        if any("1 de" in (s.note or "").lower() or "unitat" in (s.note or "").lower() for s in top.signals):
            return "descripcio d'una sola unitat de N (Pas 3)"
        return True

    def parcela(top: Cluster) -> Any:
        rc = decided.get("referencia_catastral", {})
        rc_vals = {str(c.get("value")) for c in (rc.get("candidates") or []) + (rc.get("altres") or []) if c.get("value")}
        if len(rc_vals) >= 2:
            return "2+ referencies cadastrals a la carpeta (parcel·les contigues, Pas 3): candidats"
        return True

    return {
        "architect_name": architect, "architect_company": architect, "client_name": client,
        "referencia_catastral": cadastre, "num_soil_levels": soil_levels, "num_floors": num_floors,
        "superficie_parcela": parcela,
    }.get(key)


# ---------------------------------------------------------------------------
# Fonts HTTP de la via B (Cadastre, ICGC, geocodificacio) — Fase 13(b)
# ---------------------------------------------------------------------------
#
# Forat 1 de `docs/wizard-headless/fase8-e2e/_RESULTATS.md`: `auto_extract` ja
# consulta el Cadastre i l'ICGC, pero el consolidador no ho veia mai, i camps
# com `referencia_catastral` o `superficie_parcela` sortien `no_trobat` a
# Castellar tot i tenir-ne resposta. La Fase 12 ja va tancar la meitat de
# `COORDENADES*.txt` (`python_signals`); aixo tanca la de les consultes HTTP.
#
# D'on surt el valor: `validation/_auto_result.json`, la persistencia de la Fase
# 13(a), llegida amb `auto_result_cache.load()` — o sigui NOMES si l'empremta
# dels fitxers del projecte encara quadra i l'entrada no ha caducat. Aixi el
# consolidador no fa cap crida de xarxa i no pot servir una consulta vella d'una
# altra versio de la carpeta. Quan encara no hi ha entrada (primera lectura d'un
# projecte que no ha passat mai pel wizard) simplement no hi ha senyals, com fins
# ara. A la practica hi es: TEMPS 1 acaba en minuts i la consolidacio arriba al
# final de TEMPS 2, que triga desenes de minuts.
#
# **Nomes omplen forats.** La crida viu darrere la mateixa porta que
# `derived_field_signals` (`consolidate_python`: nomes quan CAP document de la
# carpeta ha dit res del camp), que es la traduccio literal de la regla del
# disseny: cap font Python pot GUANYAR un camp contra la lectura. Per aixo no cal
# afinar la confianca perque "no bloquegi": mai coexisteix amb un senyal de
# document. La confianca es igualment < `CONV_CONF` i sense `is_a`, de manera que
# un senyal HTTP tot sol tampoc no pot arribar a `segur` (el diagnostic
# 2026-08-23 va trobar el Cadastre apuntant a la parcel·la equivocada a 4 dels 8
# projectes de referencia — a Castellar dona 441 m² i l'Eva escriu 1.284).

#: camp del nivell A -> (clau de prefill d'`auto_extract`, etiqueta de font)
_HTTP_FIELD_SOURCES: dict[str, tuple[str, str]] = {
    "referencia_catastral": ("cadastral_ref", "cadastre"),
    "superficie_parcela": ("superficie_cadastral_m2", "cadastre"),
    "cota_referencia": ("cota_referencia", "ICGC"),
    # Nomes quan no hi ha `COORDENADES*.txt` (si n'hi ha, `python_signals` ja
    # ha omplert `utm_x`/`utm_y` amb conf 0,9 i la porta queda tancada).
    "utm_x": ("_resolved_utm_x", "geocodificacio"),
    "utm_y": ("_resolved_utm_y", "geocodificacio"),
}

_HTTP_NOTES = {
    "cadastre": ("consulta HTTP al Cadastre, no lectura d'un document de la carpeta; "
                 "el diagnostic 2026-08-23 el va trobar a la parcel·la equivocada a 4 dels 8 "
                 "projectes de referencia: confirmar sempre"),
    "ICGC": ("cota del model digital del terreny de l'ICGC, no llegida de cap annex: "
             "l'Eva fa servir la de l'annex de sondeig quan n'hi ha"),
    "geocodificacio": ("UTM derivades de l'adreca (Nominatim + Cadastre), no del GPS de camp: "
                       "aproximades, confirmar"),
}

#: < CONV_CONF (0,6) i sense `is_a`: un senyal HTTP tot sol mai no fa `segur`.
_HTTP_CONF = 0.5

#: Fonts actives per defecte, i per que el Cadastre NO hi es (mesurat 2026-08-26).
#:
#: `ICGC` i `geocodificacio` nomes disparen quan cap document diu res: a Castellar
#: no disparen mai (`cota_referencia` surt de l'annex, `utm_x/y` de
#: `COORDENADES.txt`), i quan disparen son els ultims esglaons de cadenes que ja
#: son les de l'Eva — la cota de l'MDT quan no hi ha annex, i les UTM
#: geocodificades quan no hi ha GPS de camp. El comparador d'or no es mou.
#:
#: El Cadastre, en canvi, s'ha mesurat i EMPITJORA l'unic projecte on es pot
#: mesurar. A Castellar l'or de lectura diu `no_trobat` per a `referencia_catastral`
#: i `superficie_parcela` (els documents de la carpeta no els contenen) i el
#: Cadastre respon 441 m², mentre que l'informe signat de l'Eva diu **1.284**
#: (`reference-material/.../eva_reference_values.json`). Encendre'l canvia dos
#: camps de `no_trobat` a `candidats` amb un valor equivocat: `compare_consolida.py`
#: passa de 14 OK / 7 CAUTELA a 12 OK / 7 CAUTELA / **2 ALERTA** als quatre jocs
#: de Castellar (Bell-lloc no es mou: alli els documents ja ho diuen i la porta
#: queda tancada). Concorda amb el diagnostic 2026-08-23 (parcel·la equivocada a
#: 4 dels 8 projectes de referencia).
#:
#: Es queda implementat i apagat, no esborrat: als projectes on el Cadastre encerta
#: es l'unica font d'aquests dos camps, i la decisio d'encendre'l (potser per
#: projecte, quan hi hagi la validacio visual de parcel·la del treball P4) es del
#: Josep, no d'aquest modul. `G3DT_LECTURA_HTTP_SOURCES="ICGC,geocodificacio,cadastre"`
#: l'encen; `""` ho apaga tot.
_HTTP_SOURCES_DEFAULT = ("icgc", "geocodificacio")


def _http_enabled_sources() -> frozenset[str]:
    raw = os.getenv("G3DT_LECTURA_HTTP_SOURCES")
    if raw is None:
        return frozenset(_HTTP_SOURCES_DEFAULT)
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())

_HTTP_DOC = "(consulta HTTP, fora de la carpeta)"

#: Una sola entrada viva: es consolida un projecte cada vegada.
_auto_result_memo: dict[tuple, tuple[dict, dict]] = {}


def _auto_result_prefills(project_path: Path) -> tuple[dict, dict]:
    """`(prefills, sources)` de `validation/_auto_result.json`, o dos dicts buits.

    Memoritzat per (ruta, mtime, mida): `consolidate_python` recorre 22 camps i
    cinc en demanen, i validar l'empremta costa una passada de md5 pel projecte.
    """
    from automation import auto_result_cache

    path = auto_result_cache.cache_path(project_path)
    try:
        st = path.stat()
    except OSError:
        return {}, {}
    memo_key = (str(path), st.st_mtime_ns, st.st_size)
    hit = _auto_result_memo.get(memo_key)
    if hit is not None:
        return hit
    cached = auto_result_cache.load(project_path)
    out: tuple[dict, dict] = ((cached.result.prefills, cached.result.sources) if cached else ({}, {}))
    _auto_result_memo.clear()
    _auto_result_memo[memo_key] = out
    return out


def http_field_signals(key: str, project_path: Path | None) -> list[Signal]:
    """Senyals de Cadastre/ICGC/geocodificacio per a `key`, si n'hi ha.

    Nomes es crida quan el camp no te cap senyal de document (vegeu el bloc de
    dalt). Sempre `origin="python"`, mai `is_a`.
    """
    if project_path is None:
        return []
    entry = _HTTP_FIELD_SOURCES.get(key)
    if entry is None:
        return []
    prefill_key, label = entry
    if label.lower() not in _http_enabled_sources():
        return []
    prefills, sources = _auto_result_prefills(Path(project_path))
    value = prefills.get(prefill_key)
    if value is None or (isinstance(value, str) and not value.strip()):
        return []
    font = sources.get(prefill_key) or label
    return [Signal(key, value, f"({font})", "", _HTTP_CONF, _HTTP_DOC, "consulta_http", "python",
                   _HTTP_NOTES.get(label))]


def derived_field_signals(key: str, decided: dict[str, dict], sc_total: Any, sc_font: str | None) -> list[Signal]:
    """Derivacions que el skill sanciona explicitament (Pas 3). Sempre `origin=derivat`, mai segur."""
    out: list[Signal] = []
    if key == "architect_name":
        c = decided.get("client_name", {})
        if c.get("estat") in ("segur", "candidats") and c.get("value"):
            f0 = (c.get("candidates") or [{}])[0]
            out.append(Signal(key, c["value"], f"(practica Eva: client al camp arquitecte) ← {f0.get('font', '')}",
                              f0.get("quote", ""), 0.3, "(derivat)", "derivat", "derivat",
                              "arquitecte absent a la carpeta: l'Eva hi escriu el client (Rubi, Alcoletge, Vilanova, Anciles)"))
    elif key == "cte_edificacio":
        nums = _numbers(str(sc_total)) if sc_total is not None else ()
        floors = decided.get("num_floors", {}).get("value")
        fl_nums = _numbers(str(floors)) if floors else ()
        if nums:
            total = nums[0]
            many_floors = any(n >= 4 for n in fl_nums)
            val = "C2" if many_floors else ("C1" if total > 300 else "C0")
            out.append(Signal(key, val, f"(derivat: regla Eva C0 < 300 m² / C1 > 300 m² sobre superficie construida {sc_total} m²) ← {sc_font or ''}",
                              str(sc_total), 0.5, "(derivat)", "derivat", "derivat",
                              "derivat de la superficie construida, no llegit (Pas 3): sempre candidats"))
    elif key == "cte_sol":
        out.append(Signal(key, "T-1", "(coneixement previ: T-1 a tots els pressupostos G3 que porten la linia CTE)", "",
                          0.3, "(coneixement previ)", "derivat", "derivat", "cap document de la carpeta ho diu: confirmar"))
    elif key == "lab_testing_company":
        out.append(Signal(key, "TPS", "(coneixement previ: G3 treballa amb TPS; el GTL no es a la carpeta)", "",
                          0.3, "(coneixement previ)", "derivat", "derivat", "sense GTL: candidat de coneixement previ, no lectura"))
    return out


# ---------------------------------------------------------------------------
# Taules
# ---------------------------------------------------------------------------

_CELL_A_DOC_TYPES: dict[tuple[str, str], frozenset[str]] = {
    ("dpsh_tests", "cota_inici"): frozenset({"annex_dpsh"}),
    ("dpsh_tests", "profunditat_assolida"): frozenset({"dpsh_excel", "annex_dpsh"}),
    ("dpsh_tests", "rebuig"): frozenset({"dpsh_excel", "annex_dpsh"}),
    ("dpsh_tests", "nivell_freatic"): frozenset({"dpsh_excel", "annex_dpsh"}),
    ("sondeig_tests", "cota"): frozenset({"annex_sondeig", "annex_dpsh"}),
    ("sondeig_tests", "profunditat_assolida"): frozenset({"annex_sondeig"}),
    ("sondeig_tests", "spt_ma"): frozenset(),
    ("sondeig_tests", "nivell_freatic"): frozenset({"annex_sondeig"}),
    ("spt_ma_tests", "id"): frozenset({"annex_sondeig", "informe_laboratori", "comanda_lab_g3", "dpsh_excel"}),
    ("spt_ma_tests", "punt"): frozenset({"annex_sondeig", "informe_laboratori", "comanda_lab_g3", "dpsh_excel"}),
    ("spt_ma_tests", "profunditat"): frozenset({"informe_laboratori", "annex_sondeig", "dpsh_excel"}),
    ("spt_ma_tests", "litologia"): frozenset(),
    ("spt_ma_tests", "n30"): frozenset(),
    ("soil_levels", "litologia"): frozenset(),
    ("soil_levels", "de"): frozenset({"annex_sondeig"}),
    ("soil_levels", "a"): frozenset({"annex_sondeig"}),
    ("soil_levels", "mostra_del_nivell"): frozenset({"annex_sondeig"}),
}
#: Cel·les on la discrepancia entre fonts A es una regla CONEGUDA del skill (candidats, sense crida LLM).
_KNOWN_DISCREPANCY_CELLS = frozenset({("spt_ma_tests", "id")})
_NEVER_SEGUR_CELLS = frozenset({("spt_ma_tests", "n30"), ("spt_ma_tests", "litologia"), ("soil_levels", "litologia"),
                                ("sondeig_tests", "spt_ma")})
_ABS_CELLS = frozenset({("dpsh_tests", "profunditat_assolida"), ("sondeig_tests", "profunditat_assolida"),
                        ("spt_ma_tests", "profunditat"), ("soil_levels", "de"), ("soil_levels", "a")})
_ROW_ID_KEY = {"dpsh_tests": "punt", "sondeig_tests": "sondeig", "spt_ma_tests": "id", "soil_levels": "nom"}
_DATA_CELLS = {
    "dpsh_tests": ("cota_inici", "profunditat_assolida", "rebuig", "nivell_freatic"),
    "sondeig_tests": ("cota", "profunditat_assolida", "spt_ma", "nivell_freatic"),
    "spt_ma_tests": ("id", "punt", "profunditat", "litologia", "n30"),
    "soil_levels": ("litologia", "de", "a", "mostra_del_nivell"),
}
_ROW_META_KEYS = frozenset({"location", "quote", "note", "extra", "confidence", "rule", "matis", "estat"})
#: Prioritat de document per construir les files primaries de `soil_levels` (Pas 3b).
_SOIL_PRIMARY_ORDER = ("annex_sondeig", "annex_tall", "full_camp_manuscrit", "dpsh_excel", "annex_dpsh")


def _point_key(value: Any, default_letter: str = "P") -> str | None:
    if value is None:
        return None
    m = _POINT_RE.search(str(value))
    if not m:
        return None
    return f"{m.group(1).upper()}-{int(m.group(2))}"


def _iter_rows(doc: dict, block: str) -> list[dict]:
    tables = doc.get("tables") or {}
    rows = tables.get(block)
    if isinstance(rows, dict) and isinstance(rows.get("rows"), list):
        rows = rows["rows"]
    if not isinstance(rows, list):
        return []
    out = []
    aliases = ROW_KEY_ALIASES.get(block, {})
    for r in rows:
        if not isinstance(r, dict):
            continue
        r = dict(r)
        for alias, canon in aliases.items():
            if alias in r and canon not in r:
                r[canon] = r.pop(alias)
        out.append(r)
    return out


def _row_font(doc: dict, row: dict) -> str:
    return f"{doc.get('source_path', '?')} {row.get('location', '')}".strip()


def _row_conf(doc: dict, row: dict, block: str, cell: str) -> float:
    if isinstance(row.get("confidence"), (int, float)):
        return float(row["confidence"])
    return 0.8 if doc.get("document_type") in _CELL_A_DOC_TYPES.get((block, cell), ()) else 0.3


def _cell_signals(doc: dict, row: dict, block: str, cell: str) -> list[Signal]:
    """Converteix el valor d'una cel·la de fila (pla, dict amb estat/candidates, llista, dict de comptes) en senyals."""
    raw = row.get(cell)
    src = doc.get("source_path", "?")
    dtype = doc.get("document_type", "altre")
    font = _row_font(doc, row)
    quote = str(row.get("quote") or "")
    note = row.get("note") if isinstance(row.get("note"), str) else None
    conf = _row_conf(doc, row, block, cell)
    a_types = _CELL_A_DOC_TYPES.get((block, cell), frozenset())
    is_a = dtype in a_types
    sigs: list[Signal] = []

    def mk(value: Any, f: str = font, q: str = quote, c: float = conf, n: str | None = note, extra: dict | None = None) -> Signal:
        return Signal(cell, value, f, q, c, src, dtype, "claude", n, is_a and c >= 0.5, extra=extra or {})

    if cell == "nivell_freatic":
        matis = row.get("matis")
        if isinstance(raw, dict):
            matis = raw.get("matis", matis)
            if raw.get("detected") is False or (raw.get("value") is None and "detected" in raw):
                raw = "No detectat"
            else:
                raw = raw.get("value", raw.get("profunditat"))
        if raw is None or (isinstance(raw, str) and _nf_is_absent(raw)):
            # absencia: vocabulari canonic de l'Eva (regla v1.5); nomes segur si la font es A
            s = mk("No detectat", extra={"matis": None})
            s.extra["absent_literal"] = raw
            return [s]
        s = mk(raw, extra={"matis": matis if matis in (None, "humitat", "aigua") else None})
        return [s]

    if cell == "mostra_del_nivell":
        if isinstance(raw, dict):
            raw = raw.get("value")
        if isinstance(raw, str):
            raw = bool(_YES_RE.match(raw) or raw.strip().lower() == "true")
        if raw is None or (raw is False and not is_a):
            return []  # 'false' d'un document no-autoritat = "no ho se", no una afirmacio
        return [mk(bool(raw))]

    if cell == "rebuig":
        if isinstance(raw, bool):
            raw = "Si" if raw else "No"
        if isinstance(raw, str):
            if _YES_RE.match(raw):
                raw = "Si"
            elif _NO_RE.match(raw):
                raw = "No"
        return [mk(raw)] if raw is not None else []

    if cell == "spt_ma":
        if isinstance(raw, dict) and any(k in raw for k in ("n_spt", "n_ma", "n_tp")):
            n_spt, n_tp, n_ma = int(raw.get("n_spt") or 0), int(raw.get("n_tp") or 0), int(raw.get("n_ma") or 0)
            s = mk(f"{n_spt}/{n_ma}", extra={"counts": {"n_spt": n_spt, "n_tp": n_tp, "n_ma": n_ma}})
            return [s]
        if isinstance(raw, str) and raw.strip():
            return [mk(raw)]
        return []

    if cell == "n30":
        registre = row.get("registre")
        cands_suma: list = []
        if isinstance(raw, dict):
            registre = raw.get("registre", registre)
            for k in ("candidats_suma", "candidates_suma", "candidates", "candidats"):
                v = raw.get(k)
                if isinstance(v, list):
                    cands_suma = v
                    break
                if v is not None and not isinstance(v, (list, dict)):
                    cands_suma = [v]
                    break
            value = raw.get("value")
            if value is None and isinstance(registre, str) and registre.strip().upper().startswith("R"):
                value = "R"
        else:
            value = raw
        out: list[Signal] = []
        if value is not None:
            out.append(mk(value, extra={"registre": registre} if registre is not None else {}))
        for c in cands_suma:
            v = c.get("value") if isinstance(c, dict) else c
            rule = c.get("rule") if isinstance(c, dict) else None
            if v is not None:
                out.append(mk(v, n=rule or note, extra={"registre": registre} if registre is not None else {}))
        if not out and registre is not None:
            reg = registre
            if isinstance(reg, list) and len(reg) == 4:
                try:
                    vals = [int(str(x).strip()) for x in reg]
                    out.append(mk(vals[1] + vals[2], n="(derivat: suma dels 2 trams centrals del registre — criteri majoritari d'Eva, PREGUNTA OBERTA Bell-lloc)",
                                  extra={"registre": reg}))
                except (TypeError, ValueError):
                    pass
        if not out and isinstance(row.get("n30_candidat_tall"), (int, float, str)):
            out.append(mk(row["n30_candidat_tall"], n="valor N imprès al tall"))
        return out

    if cell == "litologia":
        vals: list[Any] = []
        if isinstance(raw, dict):
            if raw.get("value") is not None:
                vals.append(raw["value"])
            for c in raw.get("candidates") or []:
                v = c.get("value") if isinstance(c, dict) else c
                if v is not None and v not in vals:
                    vals.append(v)
        elif isinstance(raw, list):
            vals = [v.get("value") if isinstance(v, dict) else v for v in raw]
        elif raw is not None:
            vals = [raw]
        return [mk(v) for v in vals if v is not None]

    # cel·les generiques: pla, dict amb value/candidates, o llista `<cell>_candidats`
    vals: list[tuple[Any, str | None]] = []
    if isinstance(raw, dict):
        if raw.get("value") is not None:
            vals.append((raw["value"], None))
        for c in raw.get("candidates") or []:
            if isinstance(c, dict) and c.get("value") is not None:
                vals.append((c["value"], c.get("rule") or c.get("note")))
            elif c is not None and not isinstance(c, dict):
                vals.append((c, None))
    elif isinstance(raw, list):
        for c in raw:
            if isinstance(c, dict) and c.get("value") is not None:
                vals.append((c["value"], c.get("rule") or c.get("note")))
            elif c is not None and not isinstance(c, dict):
                vals.append((c, None))
    elif raw is not None:
        vals.append((raw, None))
    alt = row.get(f"{cell}_candidats") or row.get(f"{cell}_candidates")
    if isinstance(alt, list):
        for c in alt:
            if isinstance(c, dict) and c.get("value") is not None:
                vals.append((c["value"], c.get("rule") or c.get("note")))
            elif c is not None and not isinstance(c, dict):
                vals.append((c, None))
    return [mk(v, n=n or note) for v, n in vals]


def _nf_is_absent(raw: str) -> bool:
    """Un nivell freatic DETECTAT porta sempre una fondaria (digits); sense digits i amb vocabulari d'absencia = absent."""
    t = _ascii(_PAREN_RE.sub(" ", raw)).strip().lower()
    if re.search(r"\d", t):
        return False
    if not t or len(t) <= 3:
        return True
    return bool(_NF_ABSENT_RE.match(t) or re.search(r"\bno\b|buid|blanc|cap marca|sense|absent|n/?d\b|no detect", t))


def _sondeig_system_is_relative(dpsh_rows: dict[str, dict]) -> tuple[bool, list[Signal]]:
    """Regla d'or Pas 3b (Castellar): si les cotes DPSH son relatives ('respecte el carrer', |cota| < 50),
    la cota del sondeig a la taula segueix el sistema relatiu. Retorna (relatiu?, senyals de cota DPSH)."""
    rel = False
    sigs: list[Signal] = []
    for row in dpsh_rows.values():
        for s in row.get("cota_inici", []):
            sigs.append(s)
            if not s.is_a:
                continue  # el manuscrit dona cotes locals ('-0,15'): nomes l'annex DPSH defineix el sistema
            txt = str(s.value).lower()
            nums = _numbers(str(s.value))
            if "respecte" in txt or "relati" in txt or (nums and abs(nums[0]) < 50):
                rel = True
    return rel, sigs


def _block_sources(corpus: Corpus, block: str) -> list[str]:
    out = [d.get("source_path", "?") for d in corpus.docs if _iter_rows(d, block)]
    return out or [d.get("source_path", "?") for d in corpus.docs]


def _row_id_value(block: str, key: str, rows: list[tuple[dict, dict]]) -> Any:
    for doc, row in rows:
        v = row.get(_ROW_ID_KEY[block])
        if isinstance(v, dict):
            v = v.get("value")
        if v is not None and not (block == "spt_ma_tests"):
            return v
    return key


def consolidate_tables(corpus: Corpus, conflicts: list[dict]) -> dict[str, Any]:
    tables: dict[str, Any] = {}
    grouped: dict[str, dict[str, list[tuple[dict, dict]]]] = {b: {} for b in TABLE_ROW_GROUPS}

    # --- agrupacio de files per clau natural ---------------------------------
    for d in corpus.docs:
        for r in _iter_rows(d, "dpsh_tests"):
            k = _point_key(r.get("punt"), "P")
            if k:
                grouped["dpsh_tests"].setdefault(k, []).append((d, r))
        for r in _iter_rows(d, "sondeig_tests"):
            k = _point_key(r.get("sondeig") or r.get("punt"), "S")
            if k:
                grouped["sondeig_tests"].setdefault(k, []).append((d, r))
    grouped["spt_ma_tests"] = _group_spt_rows(corpus)

    # --- soil_levels: files primaries (annex sondeig > tall > manuscrit), fusio per numero de nivell / cobertura / interval
    soil = _group_soil_levels(corpus)
    grouped["soil_levels"] = soil

    # --- decisio cel·la a cel·la ------------------------------------------------
    dpsh_cells: dict[str, dict[str, list[Signal]]] = {}
    for block in TABLE_ROW_GROUPS:
        rows_out: list[dict] = []
        srcs = _block_sources(corpus, block)
        keys = sorted(grouped[block], key=_row_sort_key(block))
        for key in keys:
            rows = grouped[block][key]
            row_out: dict[str, Any] = {_ROW_ID_KEY[block]: _row_id_value(block, key, rows)}
            if block == "spt_ma_tests":
                row_out["punt"] = key.split("@")[0]
            cell_sigs: dict[str, list[Signal]] = {}
            for cell in _DATA_CELLS[block]:
                sigs: list[Signal] = []
                for doc, r in rows:
                    sigs.extend(_cell_signals(doc, r, block, cell))
                cell_sigs[cell] = sigs
            if block == "dpsh_tests":
                dpsh_cells[key] = cell_sigs
            for cell in _DATA_CELLS[block]:
                sigs = cell_sigs[cell]
                path = f"tables.{block}[{key}].{cell}"
                if block == "sondeig_tests" and cell == "cota":
                    row_out[cell] = _decide_sondeig_cota(sigs, dpsh_cells, srcs, conflicts, path)
                    continue
                if block == "spt_ma_tests" and cell == "punt":
                    if not sigs:
                        sigs = [Signal("punt", key.split("@")[0], "(clau de fila)", "", 0.8, "(fila)", "fila", "python", None, True)]
                cell_out = decide(
                    sigs, sources_checked=srcs, field_name=cell, abs_numbers=(block, cell) in _ABS_CELLS,
                    never_segur=(block, cell) in _NEVER_SEGUR_CELLS,
                    conflicts=None if (block, cell) in _KNOWN_DISCREPANCY_CELLS else conflicts, path=path,
                    table_cell=True,
                )
                if (block, cell) == ("spt_ma_tests", "id") and cell_out.get("estat") == "candidats":
                    cell_out["rule"] = "Pas 3: annex de l'Eva > GTL > comanda per a l'etiqueta; si discrepen, candidats (annex primer), mai segur"
                if cell == "nivell_freatic":
                    top = (cell_out.get("candidates") or [{}])[0]
                    cell_out["matis"] = (top.get("extra") or {}).get("matis")
                if cell == "n30":
                    regs = [s.extra.get("registre") for s in sigs if s.extra.get("registre") is not None]
                    cell_out["registre"] = _registre_cell(regs, sigs, srcs)
                if cell == "spt_ma":
                    counts = [s.extra.get("counts") for s in sigs if s.extra.get("counts")]
                    if counts:
                        cell_out["counts"] = counts[0]
                row_out[cell] = cell_out
            extras = {}
            for doc, r in rows:
                if isinstance(r.get("extra"), dict):
                    extras[doc.get("source_path", "?")] = r["extra"]
            if extras:
                row_out["extra"] = extras
            rows_out.append(row_out)
        estats = [c.get("estat") for r in rows_out for k, c in r.items() if isinstance(c, dict) and "estat" in c]
        if not rows_out:
            estat_bloc = "no_trobat"
        elif all(e == "segur" for e in estats):
            estat_bloc = "segur"
        else:
            estat_bloc = "candidats"
        if block == "soil_levels" and rows_out:
            last_a = rows_out[-1].get("a")
            if isinstance(last_a, dict) and last_a.get("estat") == "segur":
                last_a["estat"] = "candidats"
                last_a["rule"] = "Pas 3b: la base de l'ultim nivell es el final del reconeixement, no una transicio → candidats"
                estat_bloc = "candidats"
        tables[block] = {"estat_bloc": estat_bloc, "rows": rows_out, "sources_checked": srcs}

    tables["superficie_construida"] = _superficie_construida(corpus)
    return tables


def _registre_cell(regs: list, sigs: list[Signal], srcs: list[str]) -> dict:
    vals = [r for r in regs if r not in (None, [], "")]
    if not vals:
        return {"estat": "no_trobat", "value": None, "sources_checked": srcs}
    first = vals[0]
    fonts = [s.font for s in sigs if s.extra.get("registre") == first]
    quotes = [s.quote for s in sigs if s.extra.get("registre") == first]
    same = all(json.dumps(v, sort_keys=True) == json.dumps(first, sort_keys=True) for v in vals)
    cands = [{"value": first, "font": fonts[0] if fonts else "?", "quote": quotes[0] if quotes else ""}]
    for v in vals[1:]:
        if json.dumps(v, sort_keys=True) != json.dumps(first, sort_keys=True) and len(cands) < MAX_CANDIDATES:
            cands.append({"value": v, "font": next((s.font for s in sigs if s.extra.get("registre") == v), "?"), "quote": ""})
    estat = "segur" if same and any(s.is_a or s.doc_type == "annex_sondeig" for s in sigs) else "candidats"
    return {"estat": estat, "value": first, "candidates": cands, "sources_checked": srcs,
            "rule": "registre de cops per tram de 15 cm (Pas 3b)"}


def _decide_sondeig_cota(sigs: list[Signal], dpsh_cells: dict, srcs: list[str], conflicts: list[dict], path: str) -> dict:
    rel_system, dpsh_cota_sigs = _sondeig_system_is_relative(dpsh_cells)
    relative = [s for s in sigs if "respecte" in str(s.value).lower() or "relati" in str(s.value).lower()
                or (_numbers(str(s.value)) and abs(_numbers(str(s.value))[0]) < 50)]
    absolute = [s for s in sigs if s not in relative and _numbers(str(s.value))]
    if not rel_system:
        return decide(sigs, sources_checked=srcs, field_name="cota", conflicts=conflicts, path=path, table_cell=True)
    # sistema relatiu del projecte (Pas 3b): candidats [relativa documentada | cota DPSH del sistema | absoluta], mai segur l'absoluta
    ordered: list[Signal] = list(relative)
    if not ordered:
        for s in dpsh_cota_sigs:
            ordered.append(Signal("cota", s.value, f"(sistema relatiu del projecte: cota DPSH) ← {s.font}", s.quote, 0.5,
                                  s.doc, s.doc_type, "derivat",
                                  "cap cota relativa documentada per al sondeig: es proposa la del sistema DPSH (Pas 3b)"))
    ordered.extend(absolute)
    ordered = [s for s in ordered if s.is_a or s.origin == "derivat" or s in relative]
    cell = decide(ordered, sources_checked=srcs, field_name="cota", never_segur=True, path=path, table_cell=True)
    # decide() ordena per pes (l'absoluta es A): aqui mana la regla, no el pes → relativa primer
    pool = list(cell.get("candidates") or []) + list(cell.get("altres") or [])

    def _is_rel(c: dict) -> bool:
        v = str(c.get("value", ""))
        n = _numbers(v)
        return "respecte" in v.lower() or "relati" in v.lower() or (bool(n) and abs(n[0]) < 50)

    pool = [c for c in pool if _is_rel(c)] + [c for c in pool if not _is_rel(c)]
    if pool:
        cell["candidates"] = pool[:MAX_CANDIDATES]
        cell["altres"] = pool[MAX_CANDIDATES:]
        if not cell["altres"]:
            cell.pop("altres", None)
        cell["value"] = pool[0]["value"]
    cell["rule"] = "Pas 3b: sistema de cotes relatiu (DPSH 'respecte el carrer') → la cel·la del sondeig es relativa; l'absoluta (z de l'annex) es cota_referencia, no la cel·la; mai segur"
    if absolute and not relative:
        conflicts.append({"path": path, "why": "sistema de cotes mixt sense cota relativa documentada per al sondeig (relativa DPSH + z absoluta de l'annex)",
                          "clusters": [{"value": _short(s.value), "fonts": [s.font]} for s in (ordered[:1] + absolute[:1])]})
    return cell


def _spt_interval(r: dict) -> tuple[float, float] | None:
    raw = r.get("profunditat")
    if isinstance(raw, dict):
        raw = raw.get("value")
    nums = _numbers(str(raw or ""))
    if len(nums) >= 2:
        return (min(abs(nums[0]), abs(nums[1])), max(abs(nums[0]), abs(nums[1])))
    if len(nums) == 1:
        return (abs(nums[0]), abs(nums[0]))
    return None


def _group_spt_rows(corpus: Corpus) -> dict[str, list[tuple[dict, dict]]]:
    """Files SPT/MA: una per (punt, interval de fondaria). Files del mateix punt amb intervals que se solapen
    (annex '-1,00 a -1,20', GTL '1,0 - 1,2', tall '≈0,8 a 1,3' grafic) son la MATEIXA fila; la clau (interval)
    la posa el document de mes autoritat (annex sondeig > GTL > Excel > resta)."""
    prio = {"annex_sondeig": 0, "informe_laboratori": 1, "dpsh_excel": 2, "comanda_lab_g3": 3, "full_camp_manuscrit": 4}
    entries: list[tuple[dict, dict, str, tuple[float, float] | None]] = []
    for d in corpus.docs:
        for r in _iter_rows(d, "spt_ma_tests"):
            punt = _point_key(r.get("punt") or r.get("id"), "S") or "S-?"
            entries.append((d, r, punt, _spt_interval(r)))
    entries.sort(key=lambda e: (prio.get(e[0].get("document_type"), 9), e[3] is None))
    groups: list[dict] = []  # {punt, iv, rows}
    for d, r, punt, iv in entries:
        target = None
        for g in groups:
            if g["punt"] != punt and punt != "S-?" and g["punt"] != "S-?":
                continue
            if iv is None or g["iv"] is None:
                target = g
                break
            lo, hi = max(iv[0], g["iv"][0]), min(iv[1], g["iv"][1])
            if hi - lo >= -0.15:  # solapament (o distancia ≤ 15 cm)
                target = g
                break
        if target is None:
            groups.append({"punt": punt, "iv": iv, "rows": [(d, r)]})
        else:
            target["rows"].append((d, r))
            if target["punt"] == "S-?" and punt != "S-?":
                target["punt"] = punt
            if target["iv"] is None and iv is not None:
                target["iv"] = iv
    out: dict[str, list[tuple[dict, dict]]] = {}
    for g in groups:
        depth_key = f"{g['iv'][0]:.2f}-{g['iv'][1]:.2f}" if g["iv"] else "?"
        out[f"{g['punt']}@{depth_key}"] = g["rows"]
    return out


def _row_sort_key(block: str):
    def k(key: str):
        if block == "soil_levels":
            if key == "cover":
                return (0, 0, "")
            m = re.fullmatch(r"nivell(\d+)", key)
            if m:
                return (1, int(m.group(1)), "")
            m = re.fullmatch(r"de(-?[\d.]+)", key)
            if m:
                return (2, float(m.group(1)), "")
            return (3, 0, key)
        m = _POINT_RE.search(key)
        return (0, int(m.group(2)) if m else 0, key)
    return k


def _interval(row: dict) -> tuple[float, float] | None:
    de = _numbers(str(row.get("de") if not isinstance(row.get("de"), dict) else row["de"].get("value") or ""))
    a = _numbers(str(row.get("a") if not isinstance(row.get("a"), dict) else row["a"].get("value") or ""))
    if de and a:
        return (abs(de[0]), abs(a[0]))
    return None


#: Tolerancia (m) per considerar que una fila arrenca a la superficie.
_SURFACE_TOL = 0.05


def _cover_lacks_depths(groups: dict[str, list[tuple[dict, dict]]]) -> bool:
    """Hi ha fila de capa vegetal i cap document li ha donat fondaries."""
    rows = groups.get("cover")
    return bool(rows) and all(_interval(r) is None for _, r in rows)


def _group_soil_levels(corpus: Corpus) -> dict[str, list[tuple[dict, dict]]]:
    groups: dict[str, list[tuple[dict, dict]]] = {}
    docs_by_type: dict[str, list[dict]] = {}
    for d in corpus.docs:
        if _iter_rows(d, "soil_levels"):
            docs_by_type.setdefault(d.get("document_type", "altre"), []).append(d)
    primary_types = [t for t in _SOIL_PRIMARY_ORDER if t in docs_by_type]
    if not primary_types:
        primary_types = list(docs_by_type)

    def level_key(d: dict, r: dict) -> str | None:
        nom = r.get("nom") if not isinstance(r.get("nom"), dict) else r["nom"].get("value")
        nom = str(nom or "")
        if d.get("document_type") == "full_camp_manuscrit" or "tram" in nom.lower() or "full de camp" in nom.lower():
            return None  # numeracio del full de camp, no la de l'Eva
        if _COVER_RE.search(nom):
            return "cover"
        m = _LEVEL_RE.search(nom)
        if m:
            return f"nivell{int(m.group(1) or m.group(2))}"
        return None

    # 1. files primaries amb clau d'Eva (annexos i tall)
    for t in primary_types:
        for d in docs_by_type[t]:
            for r in _iter_rows(d, "soil_levels"):
                k = level_key(d, r)
                if k:
                    groups.setdefault(k, []).append((d, r))
    # 2. la resta: per solapament d'interval amb una fila primaria; sense interval → fila propia per `de`
    for t, docs in docs_by_type.items():
        for d in docs:
            for r in _iter_rows(d, "soil_levels"):
                if level_key(d, r) and (d, r) in [x for v in groups.values() for x in v]:
                    continue
                iv = _interval(r)
                target = None
                if iv:
                    best = 0.0
                    for k, rows in groups.items():
                        for pd, pr in rows:
                            piv = _interval(pr)
                            if not piv:
                                continue
                            ov = max(0.0, min(iv[1], piv[1]) - max(iv[0], piv[0]))
                            if ov > best and ov >= 0.5 * (iv[1] - iv[0] or 0.01):
                                best, target = ov, k
                if target is None:
                    k2 = level_key(d, r)
                    if k2 and k2 in groups:
                        target = k2
                # La capa vegetal es "sense numero a la llegenda": el tall la
                # dibuixa sense fondaries i el full de camp SI que les te, pero
                # amb la seva propia numeracio (compta la capa vegetal com a
                # "1er nivell"), que `level_key` ignora a posta. Resultat a
                # Castellar: la fila 0,00-0,50 acabava en una fila propia i la
                # capa vegetal sortia amb `de`/`a` `no_trobat` tot i tenir-les
                # llegides. Si la capa vegetal no te fondaries de ningu, l'unica
                # fila que li'n pot donar es la que arrenca a la superficie.
                # Nomes posicional: no depen de la regla del Pas 3b sobre el `de`
                # del nivell 1 (pregunta 3, pendent de l'Eva). No dispara si el
                # solapament ja ha trobat fila, ni si un document li dona un
                # nom de nivell explicit, ni si la capa vegetal ja te interval.
                if target is None and iv and iv[0] <= _SURFACE_TOL and _cover_lacks_depths(groups):
                    target = "cover"
                if target is None and not groups and iv:
                    target = f"de{iv[0]}"
                if target is None and iv and primary_types and d.get("document_type") in primary_types:
                    target = f"de{iv[0]}"
                if target is not None:
                    groups.setdefault(target, []).append((d, r))
                else:
                    groups.setdefault("altres", []).append((d, r))
    # les files "altres" (sense clau ni interval) no fan fila propia: s'afegeixen com a candidats de la primera fila
    if "altres" in groups:
        leftovers = groups.pop("altres")
        if groups:
            first = sorted(groups, key=_row_sort_key("soil_levels"))[0]
            groups[first].extend(leftovers)
        else:
            groups["de0.0"] = leftovers
    return groups


def _superficie_construida(corpus: Corpus) -> dict:
    srcs = _block_sources(corpus, "superficie_construida")
    sigs: list[Signal] = []
    components_all: list[Any] = []
    etiqueta: str | None = None
    for d in corpus.docs:
        tables = d.get("tables") or {}
        raw = tables.get("superficie_construida")
        entries = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
        for e in entries:
            if not isinstance(e, dict):
                continue
            if isinstance(e.get("rows"), list):
                entries.extend(x for x in e["rows"] if isinstance(x, dict))
                continue
            total = e.get("total", e.get("total_m2", e.get("value")))
            comps = e.get("components") or []
            font = f"{d.get('source_path', '?')} {e.get('location', '')}".strip()
            if total is None and comps:
                nums = []
                for c in comps:
                    v = c.get("value", c.get("superficie_m2")) if isinstance(c, dict) else c
                    n = _numbers(str(v)) if v is not None else ()
                    if n:
                        nums.append(n[0])
                if nums:
                    total = f"{'+'.join(str(int(n) if float(n).is_integer() else n) for n in nums)}"
            if total is not None:
                sigs.append(Signal("superficie_construida", total, font, str(e.get("quote") or ""), 0.6,
                                   d.get("source_path", "?"), d.get("document_type", "altre"), "claude",
                                   e.get("note") if isinstance(e.get("note"), str) else None, False,
                                   extra={"components": comps, "etiqueta_font": e.get("etiqueta_font")}))
                components_all.append({"doc": d.get("source_path"), "components": comps, "total": total})
                etiqueta = etiqueta or e.get("etiqueta_font")
        for t in d.get("tier_a") or []:
            if isinstance(t, dict) and t.get("concept_id") == "superficie_construida":
                sigs.append(Signal("superficie_construida", t.get("value"), f"{d.get('source_path', '?')} {t.get('location', '')}".strip(),
                                   t.get("quote", "") or "", float(t.get("confidence") or 0), d.get("source_path", "?"),
                                   d.get("document_type", "altre"), "claude", t.get("note"), False))
    cell = decide(sigs, sources_checked=srcs, field_name="superficie_construida", never_segur=True,
                  path="tables.superficie_construida", table_cell=True)
    cell["components"] = components_all
    cell["etiqueta_font"] = etiqueta
    cell["rule"] = "Pas 3b: l'Eva escriu de vegades la suma i de vegades els sumands; multi-habitatge pot ser per casa → sempre candidats"
    return cell


# ---------------------------------------------------------------------------
# Punt d'entrada
# ---------------------------------------------------------------------------


def consolidate_python(out_dir: Path, project_path: Path | None = None, *, project_name: str | None = None) -> dict:
    """Consolidacio determinista (Fase 12). Retorna un `_decisions.json` (schema v1) que passa el contracte.

    Claus extra (fora del contracte, ignorades pel validador i per la UI actual): `conflicts`
    (camps per a `--consolida --only-fields`), `consolidation` (metadades), `descartats`,
    `extra_concepts`, i `altres` dins de cada cel·la.
    """
    t0 = time.monotonic()
    out_dir = Path(out_dir)
    corpus = load_corpus(out_dir)
    if project_path is None:
        cand = out_dir.parent.parent if out_dir.name == "lectura" and out_dir.parent.name == "validation" else None
        project_path = cand if cand and cand.exists() else None
    if project_name is None:
        project_name = project_path.name if project_path else out_dir.name

    conflicts: list[dict] = []
    by_key, descartats, extra_concepts, not_present = collect_field_signals(corpus, project_path)

    def sources_for(key: str) -> list[str]:
        looked = list(dict.fromkeys(not_present.get(key, []) + [s.doc for s in by_key.get(key, [])]))
        if not looked:
            looked = list(corpus.docs_read)
        looked += [f"lectura fallida: {p}" for p in corpus.lectura_fallida]
        return looked

    fields: dict[str, dict] = {}
    # ordre: client_name abans que architect_name (guard + derivat), num_floors abans que cte
    order = ["client_name", "num_floors"] + [k for k in sorted(ALLOWED_FIELD_KEYS) if k not in ("client_name", "num_floors")]
    sc = _superficie_construida(corpus)
    for key in order:
        sigs = list(by_key.get(key, []))
        if not sigs or all(value_key(s.value)[0] == "none" for s in sigs):
            # Nomes forats: primer les consultes HTTP (font externa real),
            # despres les derivacions/coneixement previ.
            sigs += http_field_signals(key, project_path)
            sigs += derived_field_signals(key, fields, sc.get("value"), (sc.get("candidates") or [{}])[0].get("font"))
        cell = decide(
            sigs, sources_checked=sources_for(key), field_name=key, abs_numbers=key in _ABS_FIELDS,
            never_segur=key in _NEVER_SEGUR_FIELDS, segur_requires=_guard_for_field(key, fields),
            conflicts=conflicts, path=f"fields.{key}",
        )
        if key == "street_address":
            _promote_entre_carrers(cell)
        if key in descartats:
            cell["descartats"] = descartats[key]
        fields[key] = cell
    fields = {k: fields[k] for k in sorted(fields)}

    tables = consolidate_tables(corpus, conflicts)

    notes = [
        f"_decisions.json generat per consolidacio Python-first (Fase 12, {CONSOLIDATOR_VERSION}): "
        f"{len(corpus.docs)} documents llegits, {len(corpus.g3.get('documents', [])) if corpus.g3 else 0} plantilles G3, "
        f"{len(conflicts)} conflictes A-vs-A",
    ]
    if corpus.duplicates:
        notes.append("duplicats per md5 (no compten dos cops): " + ", ".join(f"{a} = {b}" for a, b in corpus.duplicates.items()))
    if corpus.lectura_fallida:
        notes.append("lectura fallida (sense {doc}.json): " + ", ".join(corpus.lectura_fallida))
    skill_versions = sorted({str(d.get("skill_version")) for d in corpus.docs if d.get("skill_version")})

    return {
        "schema_version": 1,
        "project": project_name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "skill_version": skill_versions[-1] if skill_versions else "?",
        "consolidation": {
            "consolidator": CONSOLIDATOR_VERSION, "elapsed_s": round(time.monotonic() - t0, 3),
            "n_docs": len(corpus.docs), "n_conflicts": len(conflicts),
            "docs_skill_versions": skill_versions, "llm_only_fields": None,
        },
        "fields": fields,
        "tables": tables,
        "conflicts": conflicts,
        "extra_concepts": extra_concepts,
        "sources_read": list(corpus.docs_read),
        "notes_estructurals": notes,
    }


_ENTRE_RE = re.compile(r"^\s*(situat\s+)?entre\s+el\s+carrer\b", re.IGNORECASE)


def _promote_entre_carrers(cell: dict) -> None:
    """Pas 3: si els annexos de l'Eva diuen 'entre el carrer X i el carrer Y', aquesta frase es la redaccio de l'informe → candidat 1."""
    if cell.get("estat") not in ("segur", "candidats"):
        return
    pool = list(cell.get("candidates") or []) + list(cell.get("altres") or [])
    hit = next((c for c in pool if isinstance(c.get("value"), str) and _ENTRE_RE.match(c["value"])
                and re.search(r"annex|situaci|sondeig|tall", str(c.get("font", "")), re.IGNORECASE)), None)
    if not hit:
        return
    rest = [c for c in pool if c is not hit]
    cell["candidates"] = [hit] + rest[: MAX_CANDIDATES - 1]
    cell["altres"] = rest[MAX_CANDIDATES - 1:]
    cell["value"] = hit["value"]
    cell["estat"] = "candidats"
    cell["rule"] = (cell.get("rule") or "") + "; Pas 3: frase 'entre el carrer X i el carrer Y' dels annexos = redaccio de l'informe → candidat 1"


# ---------------------------------------------------------------------------
# Fusio de la resposta LLM `--only-fields` (skill v1.5)
# ---------------------------------------------------------------------------

_CELL_PATH_RE = re.compile(r"^tables\.(\w+)\[([^\]]+)\]\.(\w+)$")


def conflict_paths(decisions: dict) -> list[str]:
    return [c["path"] for c in decisions.get("conflicts") or [] if isinstance(c, dict) and c.get("path")]


def merge_only_fields(decisions: dict, llm: dict, requested: list[str]) -> tuple[dict, list[str]]:
    """Substitueix a `decisions` NOMES les cel·les demanades (`requested`) amb la versio LLM si es valida.
    Retorna (decisions fusionades, llista de paths aplicats). Les guards de mai-segur es mantenen."""
    from automation.lectura.contract import _validate_cell  # regles b-e del contracte per cel·la

    out = copy.deepcopy(decisions)
    applied: list[str] = []
    llm_fields = llm.get("fields") if isinstance(llm.get("fields"), dict) else {}
    llm_tables = llm.get("tables") if isinstance(llm.get("tables"), dict) else {}
    for path in requested:
        if path.startswith("fields."):
            key = path[len("fields."):]
            cell = llm_fields.get(key)
            if key in ALLOWED_FIELD_KEYS and isinstance(cell, dict) and not _validate_cell(cell, path):
                if key in _NEVER_SEGUR_FIELDS and cell.get("estat") == "segur":
                    continue
                prev = out["fields"].get(key, {})
                cell = dict(cell)
                cell["llm_only_fields"] = True
                if prev.get("altres"):
                    cell.setdefault("altres", prev["altres"])
                out["fields"][key] = cell
                applied.append(path)
            continue
        m = _CELL_PATH_RE.match(path)
        if not m:
            continue
        block, row_key, cell_name = m.groups()
        blk = llm_tables.get(block)
        rows = blk.get("rows") if isinstance(blk, dict) else (blk if isinstance(blk, list) else [])
        target_rows = out["tables"].get(block, {}).get("rows", [])
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            rid = r.get(_ROW_ID_KEY.get(block, "punt"))
            if isinstance(rid, dict):
                rid = rid.get("value")
            if _point_key(rid) != _point_key(row_key) and str(rid) != row_key:
                continue
            cell = r.get(cell_name)
            if not isinstance(cell, dict) or _validate_cell(cell, path):
                continue
            if (block, cell_name) in _NEVER_SEGUR_CELLS and cell.get("estat") == "segur":
                continue
            for tr in target_rows:
                trid = tr.get(_ROW_ID_KEY.get(block, "punt"))
                if _point_key(trid) == _point_key(row_key) or str(trid) == row_key:
                    prev = tr.get(cell_name, {})
                    cell = dict(cell)
                    cell["llm_only_fields"] = True
                    for keep in ("registre", "matis", "counts", "altres"):
                        if keep in prev and keep not in cell:
                            cell[keep] = prev[keep]
                    tr[cell_name] = cell
                    applied.append(path)
    return out, applied
