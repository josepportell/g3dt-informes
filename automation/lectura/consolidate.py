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
from automation.municipis import lookup as _municipi_lookup
from automation.lectura.normalize import (
    COMPONENT_VALUE_KEY,
    ROW_KEY_ALIASES,
    ROW_REQUIRED_KEYS,
    UNIT_M2_RE,
    canonicalize_superficie_construida,
)

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

#: L3 (1.5, 2026-09-05): telefon enganxat darrere d'un nom («MARIA ALBA BARRAU CASTÁN 616523792», fitxa!C6 de la fitxa de
#: camp G3): el nom es el valor, el telefon va a la nota. Nomes camps de persona/empresa; cal que quedin ≥ 2 lletres davant.
_PERSON_LIKE_FIELDS = frozenset({"client_name", "architect_name", "architect_company", "lab_testing_company"})
_PHONE_TAIL_RE = re.compile(r"[\s,;/·-]*(?:\(?\+?34\)?[\s.-]?)?([6-9](?:[\s.-]?\d){8})\s*$")


def _strip_phone_tail(value: Any) -> tuple[Any, str | None]:
    """`("MARIA ALBA BARRAU CASTÁN", "616523792")` per a «MARIA ALBA BARRAU CASTÁN 616523792»; `(value, None)` si no hi ha
    cap telefon al final o si sense ell no queda cap nom (≥ 2 lletres)."""
    if not isinstance(value, str):
        return value, None
    m = _PHONE_TAIL_RE.search(value)
    if not m:
        return value, None
    head = value[:m.start()].strip()
    if sum(ch.isalpha() for ch in head) < 2:
        return value, None
    return head, re.sub(r"[\s.-]", "", m.group(1))
_BLOCK_CONF_BY_FIELD = {"client_name": 0.6}

#: Camps que MAI son `segur` (Pas 3 / Pas 5).
_NEVER_SEGUR_FIELDS = frozenset({"cte_edificacio", "cte_sol"})

#: Camps numerics on el signe no compta (fondaries).
_ABS_FIELDS = frozenset({"lab_depth"})

# R5 (2026-09-05, mesura dels 8: «font unica del proveidor», 19 cel·les en CAND). AUTORITAT DE CAMP.
# El skill (Pas 3) diu, per a cada camp, quin tipus de document el DECLARA (la RC, la superficie i les plantes les
# declara el proveidor: correu d'encarrec, projecte de l'arquitecte, caixeti del planol — l'Eva les copia «segons
# informacio aportada»; el nombre de nivells el declaren les dues sintesis de l'Eva: annex de sondeig i tall; el
# client el declara el formulari p.5 del pressupost signat). Un lector sol rarament arriba a 0,8 en aquests camps
# perque se li demana humilitat («creuar amb els altres») i, sense 0,8, `decide` no en treia `segur` encara que cap
# document ho contradigues. El consolidador, que veu tot el corpus, honora la declaracio quan (1) el propi lector
# l'ha marcada a `context.authority_for`, (2) hi posa una confianca ≥ FIELD_AUTHORITY_CONF (per sota, el lector
# mateix dubta: «informacio verbal de segona ma», «derivat estructuralment» — es queda en candidats), (3) hi ha
# `min_types` TIPUS de document diferents que coincideixen, i (4) cap altre senyal la contradiu (blockers de sempre).
# Els documents V0 no declaren mai (I1). Cap altre camp s'hi acull: `client_name` de correus i caixetins a 0,5-0,7
# faria conflictes A-vs-A on avui hi ha `segur` (Linyola).
FIELD_AUTHORITY_CONF = 0.5
_PROVIDER_DOC_TYPES = frozenset({"correu", "projecte_arquitecte", "planol"})
_FIELD_AUTHORITY: dict[str, tuple[frozenset[str], int]] = {
    "referencia_catastral": (_PROVIDER_DOC_TYPES, 1),
    "superficie_parcela": (_PROVIDER_DOC_TYPES, 1),
    "num_floors": (_PROVIDER_DOC_TYPES, 1),
    "num_soil_levels": (frozenset({"annex_sondeig", "annex_tall"}), 2),
    "client_name": (frozenset({"pressupost_g3"}), 1),   # nomes el formulari p.5 (`_P5_FORM_RE` sobre la font)
}
#: «DADES QUE HAN DE CONSTAR EN LA FACTURA I EN L'INFORME» (p.5 del pressupost signat; tambe en castella).
_P5_FORM_RE = re.compile(r"han de constar|factura", re.IGNORECASE)
#: Referencia cadastral COMPLETA: parcel·la urbana (7 digits + 2 lletres + 4 digits + lletra) o rustica
#: (5 digits + lletra + 8 digits), amb o sense el carrec (4 digits + 2 lletres). Un fragment de mapa («98417»)
#: o «Poligon 6, Parcel·la 105-B» no ho son.
_RC_RE = re.compile(r"(?<![0-9A-Z])(\d{7}[A-Z]{2}\d{4}[A-Z]|\d{5}[A-Z]\d{8})(\d{4}[A-Z]{2})?(?![0-9A-Z])")

# R2 (2026-09-05, mesura dels 8: «un concepte vei entra com a bloquejador», 6 cel·les + 3 de taula).
#: PRECEDENCIA per camp («qui mana» per parella de documents, R2 + F1): nivells de tipus de document, del que mana al
#: que no. Un cluster nomes contradiu el guanyador si el seu millor document es del mateix nivell o d'un de superior;
#: els documents fora de la llista son conceptes veins o fonts de recanvi: corroboren, mai bloquegen.
#: - `cota_referencia` (R2): nomes els annexos de l'Eva. La z GPS de `COORDENADES.txt` («l'Eva no l'usa», ~0,6 m; a
#:   Alcoletge 10,7 m d'anomalia), el datum relatiu del full de camp i l'ICGC no bloquegen (Bell-lloc, Linyola, Alcoletge).
#: - `lab_depth` (F1): GTL > annex de sondeig > comanda de laboratori (skill Pas 3: «el GTL mana si discrepa»; el propi
#:   senyal de la comanda ho anota). El full de camp i l'Excel DPSH anoten el tram PREVIST; el laboratori, la mostra real
#:   (Rubi: comanda 0,6-1,4 vs GTL 0,6-1,2; Linyola: camp 1,0-1,75 vs GTL 1,0-1,15).
_FIELD_PRECEDENCE: dict[str, tuple[frozenset[str], ...]] = {
    "cota_referencia": (frozenset({"annex_dpsh", "annex_sondeig", "annex_tall"}),),
    "lab_depth": (frozenset({"informe_laboratori"}), frozenset({"annex_sondeig"}), frozenset({"comanda_lab_g3"})),
    # T2 (2026-09-06, peca 1.6): les dues regles que la passada LLM `--only-fields` aplicava a la mesura dels 8 (Castellar
    # utm_x/utm_y, Rubi lab_sample_id: 3 cel·les OK → CAND en mode `python`), codificades perque el defecte del runner
    # pugui ser `python` sense perdua.
    # - `utm_x` / `utm_y`: `COORDENADES.txt` (GPS de camp de l'Eva; P-1 per regla Pas 3) mana sobre qualsevol caixeti. El
    #   de l'annex de sondeig dona la UTM del punt S-1 (coincideix amb l'entrada S-1 del fitxer: `_annotate_utm_other_points`
    #   ho anota), no una contradiccio de P-1. Sense el fitxer, els lectors competeixen com sempre.
    # - `lab_sample_id`: GTL > annexos de l'Eva (sondeig, DPSH). Signats: Castellar «MA-1 (S1)» = GTL «MA1 S1» (no l'annex
    #   «SPT-1»); Rubi i Linyola «SPT-1 (P3)» = GTL «SPT1 P3»; Bell-lloc «SPT1 S1» = GTL. El full manuscrit («Assaig de
    #   referencia» = el PUNT: «P3», Rubi) i la comanda (etiqueta prevista) queden fora de la llista: corroboren, mai
    #   bloquegen. La comanda NO hi es a posta: sense GTL ni annex (Alcoletge, Vilanova, Anciles) la cel·la es queda en
    #   candidats, com l'or (el comparador marca ALERTA si prod puja a segur on l'or te candidats). Pregunta 12 a l'Eva
    #   (tipus de mostra SPT/MA a Castellar) continua oberta: si l'annex ha de manar, s'inverteixen els dos nivells.
    "utm_x": (frozenset({"coordenades_gps"}),),
    "utm_y": (frozenset({"coordenades_gps"}),),
    "lab_sample_id": (frozenset({"informe_laboratori"}), frozenset({"annex_sondeig", "annex_dpsh"})),
}
#: «+199,50 msnm segons el planol topografic ICGC (-0,15 carrer)» i «199,50 m» son el mateix valor: la clau es el nombre.
_LEADING_COTA_RE = re.compile(r"^\s*([+\-−]?\d{2,4}(?:[.,]\d+)?)\s*(?:m\b|msnm)", re.IGNORECASE)
#: `field_date`: documents que registren la campanya. Una segona data d'un d'aquests dins de la finestra es un ALTRE
#: DIA DE CAMP (sondeig, presa de mostra), no una contradiccio: regla d'Eva «si la data del sondeig no es igual, posar
#: els dos dies»; skill Pas 3: «dia del sondeig, candidat 2 de field_date». El valor continua sent el primer dia (or).
_CAMPAIGN_DOC_TYPES = frozenset({"annex_sondeig", "annex_dpsh", "dpsh_excel", "full_camp_manuscrit", "comanda_lab_g3",
                                 "informe_laboratori", "fitxa_camp_g3", "annex_fotografies"})
CAMPAIGN_WINDOW_DAYS = 30
#: Nivells i freatic en msnm (lectura de l'escala del tall) quan l'informe vol fondaria: es converteixen amb la cota
#: de referencia SEGURA del mateix `_decisions.json` (fondaria = cota − msnm). Un candidat per punt quan el text els
#: dona («≈243,6 msnm a P-1/P-3; ≈244,6-244,7 msnm a P-2»); la lectura original queda a la nota.
_MSNM_POINT_RE = re.compile(r"([≈~]?)\s*(\d{2,4}(?:[.,]\d+)?)(?:\s*[-–/]\s*[≈~]?(\d{2,4}(?:[.,]\d+)?))?\s*(?:msnm)?\s+a\s+"
                            r"((?:[PS]-?\d+)(?:\s*/\s*[PS]-?\d+)*)")
_MSNM_NUM_RE = re.compile(r"([≈~]?)\s*(?<![\d,.])(\d{2,4}(?:[.,]\d+)?)(?:\s*[-–]\s*[≈~]?(\d{2,4}(?:[.,]\d+)?))?(\s*msnm)?")
_MSNM_CELLS = (("soil_levels", "de"), ("soil_levels", "a"), ("dpsh_tests", "nivell_freatic"), ("sondeig_tests", "nivell_freatic"))

_STOPWORDS = frozenset({
    "de", "del", "dels", "la", "el", "els", "les", "i", "y", "a", "en", "al", "d", "l", "s", "n", "c", "cl", "cr",
    "carrer", "calle", "c/", "av", "avinguda", "avda", "num", "no", "nº", "n°", "numero", "número", "the",
})
_UNIT_TOKENS = frozenset({
    "m", "ml", "msnm", "m2", "cm", "mm", "mts", "metres", "metros", "aprox", "ca", "msn", "e", "x", "y", "n", "z",
})

# R1 (2026-09-05, mesura dels 8: «mateixa entitat, formes diferents, tractades com a contradiccio», 15 cel·les):
# equivalencies PER CAMP dins de `value_key`. Cap d'elles inventa res: nomes declaren que dues grafies son el mateix.
#: forma juridica al final del nom (client, despatx, laboratori): «TPS, S.L.» = «TPS, Prospeccio del Subsol, SL»
_LEGAL_SUFFIX_FIELDS = frozenset({"client_name", "architect_company", "lab_testing_company"})
_LEGAL_SUFFIX_TOKENS = frozenset({"sl", "sa", "slu", "slp", "scp", "sll", "sccl", "slne", "sau", "coop", "ltd", "inc", "llc", "gmbh"})
#: tipus d'edifici: abreviatures de les plantilles G3 (`EG HAB UNIF LINYOLA`, `CONSTR 3 HAB UNIF`) i castella → catala
_BT_MAP = {"hab": "habitatge", "habit": "habitatge", "habitatges": "habitatge", "vivienda": "habitatge", "viviendas": "habitatge",
           "casa": "habitatge", "cases": "habitatge", "casas": "habitatge",
           "unif": "unifamiliar", "uni": "unifamiliar", "unifam": "unifamiliar", "unifamiliars": "unifamiliar", "unifamiliares": "unifamiliar",
           "aill": "aillat", "aillats": "aillat", "aillada": "aillat", "aillades": "aillat", "aislada": "aillat", "aislado": "aillat",
           "aisladas": "aillat", "aislados": "aillat",
           "adosada": "adossat", "adosado": "adossat", "adosadas": "adossat", "adosados": "adossat", "adossada": "adossat",
           "adossades": "adossat", "adossats": "adossat",
           "plurif": "plurifamiliar", "plurifamiliars": "plurifamiliar", "plurifamiliares": "plurifamiliar",
           "pareada": "aparellat", "pareado": "aparellat", "aparellada": "aparellat", "medianeras": "mitgera", "mitgeres": "mitgera"}
_BT_STOP = frozenset({"constr", "construccio", "construcció", "eg", "estudi", "estudio", "geologic", "geotecnic", "geotecnico",
                      "per", "para", "un", "una", "uns", "unes", "grup", "grupo", "edificacio", "edificio", "d", "l", "de", "del",
                      "la", "el", "en", "amb", "con", "nou", "nova", "nueva", "nuevo", "projecte", "proyecto", "obra", "unitat",
                      "unitats", "unidad", "unidades"})
#: via: abreviatures habituals als caixetins i pressupostos
_VIA_ABBR = {"sta": "santa", "st": "sant", "gral": "general", "avda": "avinguda", "av": "avinguda", "ctra": "carretera",
             "pg": "passeig", "pl": "placa", "rda": "ronda"}
#: I1 (2026-09-05, Anciles): un document llegit d'una carpeta «versio 0» (`PDF_V0/`, nomes quan no hi ha `PDF/`
#: vigent llegible) es una versio ANTERIOR de l'Eva: a Anciles la V0 posava les graves dins del NIVEL 1 i el signat en
#: fa el 2n nivell. Els seus senyals proposen i corroboren, pero mai son autoritat A ni contradiuen (confianca per sota
#: del llindar de contradiccio): les 9 cotes que hi ha surten com a candidats amb el valor bo primer, no com a «segur».
_V0_DIR_PARTS = frozenset({"PDF-V0", "PDF V0", "PDF_V0"})
_V0_NOTE = "versio anterior (carpeta V0, cap annex vigent llegible): mai autoritat, mai contradiccio"
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
# identificador que es NOMES un numero ("3", "núm. 4", "nº 4"): l'unic cas on es pot
# posar-hi la lletra del bloc sense inventar-se el punt (vegeu `_point_key`)
_BARE_NUM_ID_RE = re.compile(r"(?:n[uú]m\.?|n[º°]\.?)?\s*(\d+)", re.IGNORECASE)
#: R3 (2026-09-05): «1 de 3 habitatges» (una unitat de N) si, «PB de 280 m2 + P1 de 86 m2» (Bell-lloc) no.
_UNIT_OF_N_RE = re.compile(r"(?<![a-z0-9])1\s+de(?:ls?)?\s+(?:les\s+|els\s+)?(\d+)")
_LEVEL_RE = re.compile(r"nivell\s*(\d+)|(\d+)\s*(?:er|on|n|r|è|a|º)?\s*nivell", re.IGNORECASE)
_COVER_RE = re.compile(r"vegetal|cobertura|reblert|relleno|terra vegetal|s[oò]ls?\s+vegetals?", re.IGNORECASE)
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
    #: R5: el lector ha llistat el concepte a `context.authority_for` del document (mai per a documents V0).
    declares: bool = False

    def as_candidate(self) -> dict:
        c = {"value": self.value, "font": self.font, "quote": self.quote or ""}
        if self.note:
            c["note"] = self.note
        if self.extra:
            c["extra"] = copy.deepcopy(self.extra)
        return c


def _is_v0_source(source_path: Any) -> bool:
    return any(part in _V0_DIR_PARTS for part in str(source_path or "").replace("\\", "/").split("/"))


def _v0_conf(confidence: float) -> float:
    return min(float(confidence), CONTRADICTION_CONF - 0.01)


def _is_a(origin: str, confidence: float, forced: bool | None = None) -> bool:
    if forced is not None:
        return forced
    if origin == "g3_templates":
        return confidence >= A_CONF_G3
    if origin == "claude":
        return confidence >= A_CONF_CLAUDE
    return False


def _declares_field(s: Signal, field_name: str | None) -> bool:
    """R5: el senyal es una DECLARACIO del camp per un document del tipus que el skill hi reconeix com a autoritat."""
    spec = _FIELD_AUTHORITY.get(field_name or "")
    if not spec or not s.declares or s.origin != "claude" or s.confidence < FIELD_AUTHORITY_CONF:
        return False
    if s.doc_type not in spec[0]:
        return False
    if field_name == "client_name" and not _P5_FORM_RE.search(s.font or ""):
        return False   # el bloc CLIENT de la p.1 es el sol·licitant (Pas 3); nomes el formulari p.5 declara el client
    return True


def _field_authority_types(signals: list, field_name: str | None) -> set[str]:
    return {s.doc_type for s in signals if _declares_field(s, field_name)}


def _rc_parcels(values: Any) -> set[str]:
    """Parcel·les (14 caracters) de les referencies cadastrals COMPLETES que hi ha dins d'un o mes textos."""
    out: set[str] = set()
    for v in values:
        for m in _RC_RE.finditer(str(v or "").upper()):
            out.add(m.group(1))
    return out


def _precedence_tier(c: "Cluster", field_name: str | None) -> int:
    """Nivell de precedencia del millor document del cluster per a `field_name` (0 = mana mes; fora de la llista =
    el darrer nivell, mai contradiu els de la llista)."""
    tiers = _FIELD_PRECEDENCE.get(field_name or "", ())
    best = len(tiers)
    for s in c.signals:
        for i, types in enumerate(tiers):
            if s.doc_type in types:
                best = min(best, i)
                break
    return best


def _annotate_utm_other_points(top: "Cluster", altres: list[dict], field_name: str | None) -> None:
    """T2: un valor UTM d'un altre document que coincideix (±1 m) amb un ALTRE punt de `COORDENADES.txt` es la coordenada
    d'aquell punt (Castellar: el caixeti de l'annex de sondeig dona S-1), no una contradiccio de P-1: s'anota a `altres`."""
    if field_name not in ("utm_x", "utm_y"):
        return
    axis = "x" if field_name == "utm_x" else "y"
    punts = next((s.extra.get("punts") for s in top.signals if s.doc_type == "coordenades_gps" and s.extra.get("punts")), None)
    if not punts:
        return
    first = next((p for p in punts if str(p.get("punt", "")).upper() in ("P-1", "P1")), punts[0])
    for c in altres:
        try:
            v = float(str(c.get("value", "")).replace(",", "."))
        except ValueError:
            continue
        for p in punts:
            if p is first:
                continue
            try:
                hit = abs(float(str(p.get(axis)).replace(",", ".")) - v) <= 1.0
            except (TypeError, ValueError):
                continue
            if hit:
                c["note"] = (f"= punt {p.get('punt')} de COORDENADES.txt ({p.get('x')}/{p.get('y')}), no P-1: corroboracio, "
                             f"no contradiccio (T2)" + (f"; {c['note']}" if c.get("note") else ""))
                break


def _is_other_field_day(c: "Cluster", top: "Cluster") -> bool:
    """R2 (`field_date`): un cluster amb data completa, a ≤ CAMPAIGN_WINDOW_DAYS del guanyador, els senyals forts del
    qual venen tots de documents de la campanya (sondeig, presa de mostra, laboratori, fitxa) es un altre dia de camp."""
    if top.key[0] != "date" or c.key[0] != "date" or top.key[3] is None or c.key[3] is None:
        return False
    try:
        delta = abs((datetime(top.key[1], top.key[2], top.key[3]) - datetime(c.key[1], c.key[2], c.key[3])).days)
    except ValueError:
        return False
    if delta == 0 or delta > CAMPAIGN_WINDOW_DAYS:
        return False
    strong = [s for s in c.signals if s.is_a or s.confidence >= CONTRADICTION_CONF]
    return bool(strong) and all(s.doc_type in _CAMPAIGN_DOC_TYPES for s in strong)


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


def _building_type_tokens(s: str) -> frozenset:
    """Conjunt de paraules d'un tipus d'edifici: sense anotacions, sense el municipi final (padro), sense les paraules
    de les plantilles G3 (`EG`, `CONSTR`, `HAB UNIF`…) ni xifres; castella → catala. `{}` si no en queda cap."""
    words = _strip_parens(s).split()
    for n in (3, 2, 1):
        if len(words) > n and _municipi_lookup(" ".join(words[-n:])) is not None:
            words = words[:-n]
            break
    out = set()
    for w in _text_tokens(" ".join(words)):
        w = _BT_MAP.get(w, w)
        if w in _BT_STOP or w.isdigit():
            continue
        out.add(w)
    return frozenset(out)


def _address_key(s: str) -> tuple | None:
    """`("addr", via, {portals})` si l'adreca porta via i almenys un portal; si no, None (clau de text de sempre).
    «C/ Clot de la Llacuna, 16, Linyola (25240)», «Clot de la Llacuna, 16, Linyola (CP 25240)» i «C. Clot de la
    Llacuna, 16» donen la mateixa clau: el municipi/CP/urbanitzacio despres del portal no forma part de la via."""
    from automation.lectura.cadastre_reader import portals_from_address
    street, portals = portals_from_address(s)
    if not portals:
        return None
    via = "".join(_VIA_ABBR.get(w, w) for w in _text_tokens(street))
    if not via:
        return None
    return ("addr", via, frozenset(f"{n}{l}".lower() for n, l in portals))


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
    # R1: equivalencies per camp (abans de dates/numeros: cap d'aquests camps es una data ni un nombre)
    if field_name == "building_type":
        toks = _building_type_tokens(s)
        if toks:
            return ("btset", toks)
    if field_name == "street_address":
        ak = _address_key(s)
        if ak:
            return ak
    if field_name == "lab_location":
        pk = _point_key(s, default_letter="")
        if pk:
            return ("text", pk.replace("-", "").lower())
    if field_name == "cota_referencia":
        m = _LEADING_COTA_RE.match(s)
        if m:
            return ("num", (round(float(m.group(1).replace("−", "-").replace(",", ".")), 3),))
    d = _parse_date(s)
    if d:
        return d
    if _is_numeric_like(s):
        nums = _numbers(s)
        if abs_numbers:
            nums = tuple(abs(n) for n in nums)
        return ("num", nums)
    toks = _text_tokens(s)
    if field_name in _LEGAL_SUFFIX_FIELDS:
        while len(toks) > 1 and toks[-1] in _LEGAL_SUFFIX_TOKENS:
            toks.pop()
    txt = "".join(toks)
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
    if a[0] == "btset" and b[0] == "btset":
        # un conjunt dins de l'altre = lectura parcial del mateix tipus («habitatge unifamiliar» ⊂ «… aillat»)
        return a[1] <= b[1] or b[1] <= a[1]
    if {a[0], b[0]} == {"addr", "text"}:
        # una lectura sense portal («C/ DE LA MIRANDA») es parcial de la que en porta, si la via coincideix
        addr, txt = (a, b) if a[0] == "addr" else (b, a)
        return txt[1] == addr[1]
    if a[0] != b[0]:
        return False
    if a[0] == "addr":
        return False   # mateixa via, portals diferents = adreces diferents (18A i 18B son edificis diferents)
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


def _dayless(k: tuple) -> bool:
    """Clau de data sense dia («Octubre 2025»): compatible amb qualsevol dia del mes."""
    return k[0] == "date" and k[3] is None


def _attach_only(k: tuple, field_name: str | None) -> bool:
    """Claus que NO fan d'aresta del union-find (s'adjunten despres al cluster compatible mes fort, sense
    transitivitat): dates sense dia (D2), conjunts de paraules de `building_type` (un subconjunt no ha d'unir
    «aillat» amb «entre mitgeres») i lectures d'adreca sense portal (R1)."""
    return _dayless(k) or k[0] == "btset" or (k[0] == "text" and field_name == "street_address")


def _more_complete(a: tuple, b: tuple) -> tuple:
    """La clau mes completa de dues compatibles: data amb dia, conjunt mes gran, adreca amb portal, text mes llarg."""
    if a[0] == "date" and b[0] == "date":
        return a if a[3] is not None else b
    if a[0] == "btset" and b[0] == "btset":
        return a if len(a[1]) >= len(b[1]) else b
    if a[0] == "addr" or b[0] == "addr":
        return a if a[0] == "addr" else b
    return a if len(str(a)) >= len(str(b)) else b


def cluster_signals(sigs: list[Signal], *, abs_numbers: bool = False, field_name: str | None = None) -> list[Cluster]:
    """Agrupa senyals per compatibilitat (union-find) i ordena els clusters per pes.

    D2 (2026-09-05, mesura dels 8, Linyola `field_date`): una data SENSE dia («Octubre 2025», caixeti del planol,
    conf 0,2-0,3) es compatible amb TOTS els dies del mes, i com que la compatibilitat del union-find es transitiva
    feia de pont entre dos dies diferents (01/10 de la fitxa A 0,95 i 10/10 d'un lab-sig 0,35): un sol cluster,
    «1 font A sense contradiccio», segur amb el dia equivocat. Ara les claus sense dia no uneixen res: s'adjunten
    DESPRES al cluster amb dia mes fort que hi sigui compatible (corroboracio, no aresta) o formen cluster propi.
    El representant d'un cluster de dates es la clau amb dia de la font de mes autoritat, mai la cadena mes llarga
    (`('date', 2025, 10, 10)` guanyava a `('date', 2025, 10, 1)` per un caracter)."""
    keys = [value_key(s.value, abs_numbers=abs_numbers, field_name=field_name) for s in sigs]
    parent = list(range(len(sigs)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(sigs)):
        if keys[i][0] == "none" or _attach_only(keys[i], field_name):
            continue
        for j in range(i + 1, len(sigs)):
            if keys[j][0] == "none" or _attach_only(keys[j], field_name):
                continue
            if keys_compatible(keys[i], keys[j]):
                parent[find(i)] = find(j)

    groups: dict[int, Cluster] = {}
    partial: dict[tuple, Cluster] = {}
    for i, s in enumerate(sigs):
        if keys[i][0] == "none":
            continue
        if _attach_only(keys[i], field_name):
            partial.setdefault(keys[i], Cluster(key=keys[i])).signals.append(s)
            continue
        r = find(i)
        if r not in groups:
            groups[r] = Cluster(key=keys[i])
        groups[r].signals.append(s)
    clusters = list(groups.values())
    family = field_name in _ENCARREC_FAMILY_FIELDS

    def weight(c: Cluster) -> tuple:
        return (c.has_a, c.n_docs(family), c.sum_conf, c.max_conf)

    # les claus «nomes adjuntar» s'adjunten per ordre de pes al cluster compatible mes fort ja col·locat (la clau
    # del cluster es va mantenint com la mes completa, perque un subconjunt col·locat primer no faci de pont)
    for pc in sorted(partial.values(), key=weight, reverse=True):
        targets = [c for c in clusters if keys_compatible(c.key, pc.key)]
        if targets:
            best = max(targets, key=weight)
            best.signals.extend(pc.signals)
            best.key = _more_complete(best.key, pc.key)
        else:
            clusters.append(pc)
    clusters.sort(key=weight, reverse=True)
    for c in clusters:
        ks = [(value_key(s.value, abs_numbers=abs_numbers, field_name=field_name), s) for s in c.signals]
        if c.key[0] == "date":
            with_day = [(k, s) for k, s in ks if k[3] is not None]
            if with_day:
                # totes les claus amb dia d'un cluster son identiques (nomes uneixen dies iguals); el representant
                # es declara per autoritat, no per longitud
                c.key = max(with_day, key=lambda ks_: (ks_[1].is_a, ks_[1].confidence))[0]
            continue
        if c.key[0] == "btset":
            c.key = max((k for k, _ in ks if k[0] == "btset"), key=lambda k: len(k[1]))
            continue
        if any(k[0] == "addr" for k, _ in ks):
            c.key = next(k for k, _ in ks if k[0] == "addr")
            continue
        # representant de la clau = la clau mes completa (text mes llarg: les curtes son lectures parcials)
        c.key = max((k for k, _ in ks), key=lambda k: len(str(k)))
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
        # R5: la forma del document que DECLARA el camp va abans que una forma mes llarga d'un document que no
        # (fitxa C6 «MARIA ALBA BARRAU CASTAN 616523792» vs formulari p.5 «Maria Alba Barrau Castan»)
        keys = sorted(by_key, key=lambda k: (any(s.is_a for s in by_key[k]),
                                             any(_declares_field(s, field_name) for s in by_key[k]),
                                             k[0] == "date" and k[3] is not None, len(str(k))), reverse=True)
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
    if not table_cell and field_name in _FIELD_PRECEDENCE:
        # R2/F1: nomes contradiu qui mana igual o mes que el guanyador; la resta corrobora o fa de recanvi
        top_tier = _precedence_tier(top, field_name)
        blockers = [c for c in blockers if _precedence_tier(c, field_name) <= top_tier]
    other_days: list[Cluster] = []
    if not table_cell and field_name == "field_date":
        other_days = [c for c in blockers if _is_other_field_day(c, top)]
        other_ids = {id(c) for c in other_days}
        blockers = [c for c in blockers if id(c) not in other_ids]
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
    elif len(a_keys) > 1 and top.key[0] != "btset":
        reasons.append("formes diferents entre fonts A (compatibles per prefix): candidats amb totes les formes")
    else:
        strong_docs = {s.doc for s in top.signals if s.confidence >= CONV_CONF or s.is_a}
        if family:
            strong_docs = {("(encarrec)" if s.doc_type in _ENCARREC_DOC_TYPES or s.origin == "g3_templates" else s.doc)
                           for s in top.signals if s.confidence >= CONV_CONF or s.is_a}
        converge = len(strong_docs) >= CONV_MIN_DOCS
        spec = None if table_cell else _FIELD_AUTHORITY.get(field_name or "")
        auth_types = _field_authority_types(top.signals, field_name) if spec else set()
        field_auth = bool(spec) and len(auth_types) >= spec[1]
        if top.has_a or converge or field_auth:
            guard = segur_requires(top) if segur_requires else True
            if guard is True or guard is None:
                estat = "segur"
                reasons.append("1 font A sense contradiccio" if top.has_a else
                               f"convergencia de {len(strong_docs)} documents independents (conf ≥ {CONV_CONF})" if converge else
                               f"autoritat de camp (R5): {' + '.join(sorted(auth_types))} declara el valor "
                               f"(conf ≥ {FIELD_AUTHORITY_CONF}) sense contradiccio")
            else:
                reasons.append(f"guard: {guard}" if isinstance(guard, str) else "guard de camp")
        else:
            reasons.append("cap font d'autoritat A (conf < 0,8) i sense convergencia de 3 documents")

    if a_conflict and conflicts is not None:
        conflicts.append({
            "path": path, "why": "dues fonts d'autoritat A discrepen",
            "clusters": [{"value": _short(c.signals[0].value), "fonts": [s.font for s in c.signals][:3]} for c in [top] + a_conflict],
        })

    other_ids = {id(c) for c in other_days}
    if estat == "segur":
        # segur: els candidats son les formes del cluster guanyador (d'on surt el valor); les alternatives
        # no bloquejants (conf < llindar) van a `altres`, perque la UI no mostri "segur" amb un valor diferent al costat
        candidates, altres = _distinct_candidates([top], abs_numbers=abs_numbers, field_name=field_name)
        for c in clusters[1:]:
            if id(c) in other_ids:
                continue
            altres.extend(s.as_candidate() for s in sorted(c.signals, key=_prefer_form, reverse=True))
        _annotate_utm_other_points(top, altres, field_name)
    else:
        candidates, altres = _distinct_candidates(clusters, abs_numbers=abs_numbers, field_name=field_name)
    extra_cell: dict | None = None
    if other_days and estat == "segur":
        # R2: els altres dies de camp queden VISIBLES (candidat anotat, com a l'or: «2025-10-06 (sondeig)») i a `extra`
        days = [_iso_date(top.key)] if _iso_date(top.key) else []
        for c in other_days:
            best = max(c.signals, key=_prefer_form)
            cand = best.as_candidate()
            cand["value"] = _iso_date(c.key) or cand["value"]
            cand["note"] = ("altre dia de camp (sondeig / presa de mostra); regla d'Eva: «si la data del sondeig no es "
                            "igual, posar els dos dies»" + (f"; {best.note}" if best.note else ""))
            candidates = (candidates + [cand]) if len(candidates) < MAX_CANDIDATES else candidates[:MAX_CANDIDATES - 1] + [cand]
            if _iso_date(c.key):
                days.append(_iso_date(c.key))
        days = sorted(dict.fromkeys(days))
        extra_cell = {"dies_de_camp": days}
        reasons.append(f"campanya de {len(days)} dies ({', '.join(days)}): la data del sondeig no contradiu la de camp (R2)")
    value = candidates[0]["value"]
    iso = None
    if estat == "segur":
        # canonicalitzacio de FORMAT (no de contingut): la data en ISO, la cita conserva la forma original.
        # D2: la ISO surt de la clau del PROPI candidat 0 (mai de `top.key`): un candidat «Octubre 2025» no es
        # reescriu amb un dia que la seva cita no diu, ni un 01/10 amb el 10/10 d'un altre senyal del cluster.
        k0 = value_key(value, abs_numbers=abs_numbers, field_name=field_name)
        if keys_compatible(k0, top.key):
            iso = _iso_date(k0)
    if iso:
        value = iso
        candidates[0]["value"] = iso
    if field_name == "lab_location" and estat == "segur":
        # R1: canonicalitzacio de FORMAT del punt («SPT1 P3», «P3» → «P-3», la forma del signat); la cita conserva
        # la forma original. Sense aixo, entre formes equivalents `_prefer_form` triava la mes llarga.
        pk = _point_key(value, default_letter="")
        if pk:
            value = pk
            candidates[0]["value"] = pk
    cell: dict[str, Any] = {"estat": estat, "value": value, "candidates": candidates}
    if estat == "candidats":
        cell["value"] = candidates[0]["value"]
    cell["rule"] = "; ".join(reasons)
    if extra_cell:
        cell["extra"] = extra_cell
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
    orfes: list[str] = field(default_factory=list)          # {doc}.json d'un fitxer que ja no hi es
    #: Claus de sumand de `superficie_construida` que `normalize` no coneix (rastre de
    #: dialectes nous del lector; vegeu `_superficie_construida` i les notes estructurals).
    component_dialects: list[str] = field(default_factory=list)


def _norm_src(path: Any) -> str:
    """Ruta comparable entre `_inventory.json` i el `source_path` d'un `{doc}.json`
    (separador, forma Unicode i caixa: l'inventari el pot haver escrit una altra maquina)."""
    return unicodedata.normalize("NFC", str(path or "").replace("\\", "/")).strip().lower()


def _inventory_paths(inv: Any, *, include_skipped: bool = False) -> set[str]:
    """Rutes de l'inventari que poden tenir un `{doc}.json` al costat.

    Les entrades `route == "skip"` en queden FORA. `build_inventory` posa a `files` TOTES
    les entrades, tambe la quarantena `_esborrats/` (`route="skip"`,
    `doc_type_hint="exclos_carpeta"`): comptant-les, el `{doc}.json` d'un document que
    l'Eva ha mogut a `_esborrats/` no era orfe i tornava a competir amb la versio viva
    (un `segur` passava a `candidats` amb el valor mort al costat).

    Es el mateix criteri que `runner.py::_consolida_fingerprint`. No pot descartar cap
    lectura legitima: `runner.py` nomes encua `route == "claude"`, o sigui que cap altre
    `route` no genera mai un `{doc}.json`.

    `include_skipped=True` torna TOTES les rutes de l'inventari (quarantena inclosa). Nomes
    serveix per distingir "ruta desconeguda per a l'inventari" de "ruta coneguda pero en
    quarantena": la segona es un orfe SABUT, no un indici d'inventari incomparable.
    """
    if not isinstance(inv, dict):
        return set()
    return {_norm_src(f.get("path")) for f in (inv.get("files") or [])
            if isinstance(f, dict) and f.get("path") and (include_skipped or f.get("route") != "skip")}


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
    # Els `{doc}.json` d'un fitxer que ja no es a l'inventari (reanomenat, esborrat) son
    # ORFES: sense aquest filtre segueixen competint amb els vius i, pel dedup md5 de sota,
    # l'orfe pot guanyar com a canonic i deixar el fitxer viu marcat de duplicat.
    inv_paths = _inventory_paths(inv)
    inv_known = _inventory_paths(inv, include_skipped=True)
    loaded: list[dict] = []
    for p in sorted(out_dir.glob("*.json")):
        if p.name in _RESERVED_JSON_NAMES or p.name.startswith("_"):
            continue
        d = _load_json(p)
        if not isinstance(d, dict):
            continue
        d.setdefault("source_path", p.stem)
        loaded.append(d)
    orfes = {d["source_path"] for d in loaded if inv_known and _norm_src(d["source_path"]) not in inv_paths}
    if orfes and not any(_norm_src(d["source_path"]) in inv_known for d in loaded):
        # Cap JSON casa amb CAP entrada de l'inventari (inventari d'un altre projecte, rutes
        # amb un altre format, directori sintetic d'un test): no es comparable -> comportament
        # de sempre. Es MANTE tot i que tapa un cas legitim ("l'Eva ho ha reanomenat tot i la
        # re-lectura ha fallat sencera", que aqui deixaria el corpus buit): des de les rutes no
        # es pot distingir d'un inventari incomparable, i buidar el corpus per un inventari que
        # no toca es un dany mes gran i mes silencios. Aquell cas ja es visible per una altra
        # via: `lectura_fallida` llista TOTS els fitxers `route == "claude"`.
        #
        # La comparacio va contra `inv_known` (quarantena INCLOSA), no contra `inv_paths`: si
        # tots els `{doc}.json` son de fitxers `_esborrats/` (`route="skip"`), l'inventari SI
        # que els coneix — son orfes SABUTS — i l'escapatoria no ha de disparar. Comparant-ho
        # amb `inv_paths` es desactivava el filtre sencer i un document mort decidia un camp a
        # `segur` (p. ex. `municipality` d'un projecte anterior).
        orfes = set()
    corpus.orfes = sorted(orfes)
    seen_md5: dict[str, str] = {}
    unknown_component_keys: set[str] = set()
    for d in loaded:
        if d["source_path"] in orfes:
            continue
        md5 = d.get("source_md5")
        if md5 and md5 in seen_md5:
            corpus.duplicates[d["source_path"]] = seen_md5[md5]
            continue
        if md5:
            seen_md5[md5] = d["source_path"]
        # Porta unica del dialecte dels sumands de `superficie_construida`: a partir d'aqui
        # la xifra viu sempre a `COMPONENT_VALUE_KEY` i cap consumidor no ha d'endevinar
        # noms de camp (`_component_m2`, `tables_report._component_number`).
        tables = d.get("tables")
        if isinstance(tables, dict) and "superficie_construida" in tables:
            tables["superficie_construida"] = canonicalize_superficie_construida(
                tables["superficie_construida"], unknown_component_keys)
        corpus.docs.append(d)
        corpus.docs_read.append(d["source_path"])
    corpus.component_dialects = sorted(unknown_component_keys)
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
                  origin: str, note: str | None, forced_a: bool | None = None, declares: bool = False) -> None:
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
                        add(k, Signal(k, v, font, quote, conf, doc, doc_type, origin, note, _is_a(origin, conf, forced_a),
                                      declares=declares))
                return
        if concept in ("lab", "cte") and isinstance(value, dict):
            for k in (_LAB_SUBKEYS if concept == "lab" else _CTE_SUBKEYS):
                if value.get(k) is not None:
                    add(k, Signal(k, value[k], font, quote, conf, doc, doc_type, origin, note, _is_a(origin, conf, forced_a),
                                  declares=declares))
            return
        if concept in _PERSON_LIKE_FIELDS:
            value, phone = _strip_phone_tail(value)
            if phone:
                # L3: la cita conserva la cadena original; el telefon queda visible a la nota
                quote = quote or f"{value} {phone}"
                note = f"telèfon {phone} separat del nom (L3)" + (f"; {note}" if note else "")
        add(concept, Signal(concept, value, font, quote, conf, doc, doc_type, origin, note, _is_a(origin, conf, forced_a),
                            declares=declares))

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
        v0 = _is_v0_source(src)
        ctx = d.get("context") if isinstance(d.get("context"), dict) else {}
        authority_for = {a for a in (ctx.get("authority_for") or []) if isinstance(a, str)}
        for e in d.get("tier_a") or []:
            if not isinstance(e, dict):
                continue
            conf = float(e.get("confidence") or 0.0)
            note = e.get("note")
            if v0:
                conf = _v0_conf(conf)
                note = f"{_V0_NOTE}; {note}" if note else _V0_NOTE
            add_entry(e.get("concept_id"), e.get("value"), f"{src} {e.get('location', '')}".strip(),
                      e.get("quote", "") or "", conf, src, dtype, "claude", note, False if v0 else None,
                      declares=(not v0) and e.get("concept_id") in authority_for)
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
        if any(s.doc_type == "consulta_cadastre" or "cadastr" in s.doc.lower() or "catastr" in s.doc.lower()
               for s in top.signals):
            return True
        # R5: una referencia COMPLETA declarada pel proveidor (correu d'encarrec, projecte de l'arquitecte) es la
        # que l'Eva copia (or: Linyola, Alcoletge, Anciles). Sense consulta a la carpeta, nomes val si TOTES les
        # formes del cluster tenen forma de RC sencera: «Poligon 6, Parcel·la 105-B» (Rubi) o el fragment «98417»
        # d'un mapa (Alcoletge) no ho son.
        if top.signals and all(_rc_parcels([s.value]) for s in top.signals):
            return True
        return "sense consulta del Cadastre a la carpeta i valor sense forma de referencia completa (Pas 3): mai segur"

    def soil_levels(top: Cluster) -> Any:
        if not any(s.doc_type in ("annex_sondeig", "annex_tall") for s in top.signals):
            return "sense annex de sondeig ni tall (Pas 3): candidats + confirmar"
        return True

    def num_floors(top: Cluster) -> Any:
        for s in top.signals:
            note = (s.note or "").lower()
            m = _UNIT_OF_N_RE.search(note)
            if (m and int(m.group(1)) >= 2) or "unitat" in note:
                return "descripcio d'una sola unitat de N (Pas 3)"
        return True

    def parcela(top: Cluster) -> Any:
        rc = decided.get("referencia_catastral", {})
        # R5: nomes compten les referencies COMPLETES (parcel·la de 14 caracters): el fragment «61845» d'un mapa al
        # costat de «6184504BH9158N0000SS» (Anciles) no es una segona parcel·la; «…N+…N+…N» del Cadastre en son tres.
        parcels = _rc_parcels(c.get("value") for c in (rc.get("candidates") or []) + (rc.get("altres") or []))
        if len(parcels) >= 2:
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
# un senyal HTTP tot sol tampoc no pot arribar a `segur`.
#
# **`referencia_catastral`/`superficie_parcela` NO passen per aqui** (2026-08-31, Fix D,
# `docs/PLA-PENDENTS-0B-0C-0D-2026-08-26.md` §7): el diagnostic 2026-08-23 ("parcel·la
# equivocada a 4 dels 8 projectes") era el *matcher* de la via B (`geocode_coordinates`,
# que agafa el portal MES PROPER quan hi ha lletra) acceptant un portal diferent del que
# demanava l'adreça — no el Cadastre. Aquests dos camps ara els omple
# `automation.lectura.cadastre_reader.cadastre_portal_signals`: suma els portals EXACTES
# (amb lletra) de l'adreça LLEGIDA, no la de `_auto_result.json`. Vegeu aquell modul.

#: camp del nivell A -> (clau de prefill d'`auto_extract`, etiqueta de font)
#: `referencia_catastral`/`superficie_parcela` NO hi son: les omple `cadastre_reader` (vegeu
#: el bloc de dalt), no `_auto_result.json`.
_HTTP_FIELD_SOURCES: dict[str, tuple[str, str]] = {
    "cota_referencia": ("cota_referencia", "ICGC"),
    # Nomes quan no hi ha `COORDENADES*.txt` (si n'hi ha, `python_signals` ja
    # ha omplert `utm_x`/`utm_y` amb conf 0,9 i la porta queda tancada).
    "utm_x": ("_resolved_utm_x", "geocodificacio"),
    "utm_y": ("_resolved_utm_y", "geocodificacio"),
}

_HTTP_NOTES = {
    "cadastre": ("suma de les parcel·les cadastrals dels portals de l'adreça llegida (consulta "
                 "HTTP, no lectura d'un document de la carpeta); la fila de l'informe diu "
                 '"segons plànols cadastrals"; confirmar si el projecte abasta més o menys '
                 "portals dels que diu l'adreça"),
    "ICGC": ("cota del model digital del terreny de l'ICGC, no llegida de cap annex: "
             "l'Eva fa servir la de l'annex de sondeig quan n'hi ha"),
    "geocodificacio": ("UTM derivades de l'adreca (Nominatim + Cadastre), no del GPS de camp: "
                       "aproximades, confirmar"),
}

#: < CONV_CONF (0,6) i sense `is_a`: un senyal HTTP tot sol mai no fa `segur`.
_HTTP_CONF = 0.5

#: Fonts actives per defecte (Fix D, 2026-08-31 — decisio del Josep, `PLA-PENDENTS-0B-0C-0D` §7.9/§11).
#:
#: `ICGC` i `geocodificacio` nomes disparen quan cap document diu res (vegeu dalt).
#:
#: `cadastre` (via `cadastre_reader.cadastre_portal_signals`, no aquest bloc) es va mesurar de
#: nou el 2026-08-26 amb l'adreça LLEGIDA (no la de `_auto_result.json`, que era el forat real):
#: suma els portals EXACTES que els documents anomenen ("18A, 18B i 20" -> 3 parcel·les, 441+423+420
#: = 1.284, igual que l'informe signat de l'Eva) nomes si son contigus. Amb aquesta adreça, el
#: Cadastre coincideix amb l'Eva a 6 dels 7 projectes de referencia resolubles (Rubí no resol via
#: `ConsultaVia`: blanc honest). El "parcel·la equivocada a 4 dels 8" del diagnostic 2026-08-23 era
#: el *matcher* de la via B (`geocode_coordinates._pick_nearest_rc_from_numerero`, agafa el portal
#: MES PROPER quan hi ha lletra), no el Cadastre en si — per aixo aquest lector no en delega el
#: portal. Mai `segur` (conf 0,5): nomes omple `no_trobat`. `G3DT_LECTURA_HTTP_SOURCES=""` ho apaga
#: tot; `"icgc,geocodificacio"` apaga nomes el Cadastre.
_HTTP_SOURCES_DEFAULT = ("icgc", "geocodificacio", "cadastre")


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


_ATTACHED_RE = re.compile(r"adossa|adosad|mitger|medianer|plurifam|pareja|apparell|aparell|bloc\b|bloque", re.IGNORECASE)
_UNITS_RE = re.compile(r"(\d+)\s*(?:hab|viv|cas|adosad|adossat|unitat|unidad|xalet|chalet)", re.IGNORECASE)


def _cte_surface(sc: dict | None, decided: dict[str, dict]) -> tuple[Any, str | None, str | None]:
    """Superficie sobre la qual es deriva el CTE (D5, 2026-09-05, Anciles): `(total, font, nota)`.

    El CTE (C0 < 300 m² i < 4 plantes) es classifica PER EDIFICI. Un grup d'habitatges adossats/plurifamiliar es un sol
    edifici → compta la superficie TOTAL de l'encarrec (Anciles: 7 adossats, 1.264 m² → C1; el candidat 1 de la taula era
    una tipologia de 186 m² → C0). Habitatges aillats son edificis separats → per unitat (Castellar: 3 aillats de 120 m²
    → C0, com l'Eva). Sense senyal d'adossament, es fa el de sempre: el candidat 1."""
    if not sc:
        return None, None, None
    cands = list(sc.get("candidates") or []) + list(sc.get("altres") or [])
    totals: list[tuple[float, str]] = []
    for c in cands:
        nums = _numbers(str(c.get("value"))) if c.get("value") is not None else ()
        if nums:
            totals.append((nums[0], str(c.get("font") or "")))
    if not totals:
        return None, None, None
    first_total, first_font = totals[0]
    bt = decided.get("building_type") or {}
    forms = " ".join(str(c.get("value")) for c in (bt.get("candidates") or []) if c.get("value")) + " " + str(bt.get("value") or "")
    if not _ATTACHED_RE.search(forms):
        return sc.get("value"), first_font, None
    best_total, best_font = max(totals)
    note = (f"D5: edificacio adossada/plurifamiliar = un sol edifici → superficie TOTAL de l'encarrec "
            f"({best_total} m², {best_font}); el candidat 1 de la taula ({first_total} m²) es per unitat/tipologia")
    m = _UNITS_RE.search(forms)
    n_units = int(m.group(1)) if m else None
    if best_total <= 300 and n_units and n_units >= 2 and n_units * first_total > 300:
        best_total, best_font = n_units * first_total, f"{n_units} unitats × {first_total} m² ({first_font})"
        note += f"; cap total del conjunt a la carpeta: {n_units} unitats × {first_total} = {best_total} m²"
    return best_total, best_font, note


def derived_field_signals(key: str, decided: dict[str, dict], sc: dict | None) -> list[Signal]:
    """Derivacions que el skill sanciona explicitament (Pas 3). Sempre `origin=derivat`, mai segur.
    `sc` es la cel·la `tables.superficie_construida` sencera (D5: la derivacio del CTE tria la superficie)."""
    out: list[Signal] = []
    sc_total, sc_font, sc_note = _cte_surface(sc, decided)
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
            note = "derivat de la superficie construida, no llegit (Pas 3): sempre candidats"
            if sc_note:
                note += "; " + sc_note
            out.append(Signal(key, val, f"(derivat: regla Eva C0 < 300 m² / C1 > 300 m² sobre superficie construida {sc_total} m²) ← {sc_font or ''}",
                              str(sc_total), 0.5, "(derivat)", "derivat", "derivat", note))
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
#: L3 (1.5): etiqueta de mostra alterada. Una MA no te N30 a l'informe (l'Eva escriu «--», Anciles MA-1 amb colpeig 1/1/1/1
#: anotat al full); el colpeig, si n'hi ha, queda al `registre`. Nomes si TOTES les etiquetes de la fila son MA (Castellar
#: «SPT-1» de l'annex vs «MA1» del GTL es una discrepancia d'etiqueta, pregunta 12 a l'Eva: no es toca).
_MA_ID_RE = re.compile(r"(?<![A-Za-z])M\.?\s?A(?![A-Za-z])|mostra\s+alterada|muestra\s+alterada", re.IGNORECASE)
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
    """`"P-1"`/`"p 1"` -> `"P-1"`; `"3"` -> `"{default_letter}-3"`.

    El recurs a `default_letter` no es cosmetic: els cridants li passen la lletra del bloc
    (`"P"` per a DPSH, `"S"` per a sondeigs/SPT) justament perque un identificador com ara
    `"3"` o `"núm. 3"` es agrupable. Sense ell, la guarda `if k:` de `consolidate_tables`
    DESCARTAVA la fila sencera (no arribava ni al `_decisions.json`) i les files SPT queien
    totes al cistell `"S-?"`.

    Pero el recurs nomes val si el text es NOMES el numero (amb `núm.`/`nº` opcional).
    Amb un `re.search(r"\\d+")` sobre tot el text, `"SPT-2"` (2n assaig) passava a `"S-2"`
    (sondeig 2), `"MA1"` (mostra 1) a `"S-1"`, `"03/09/2025"` a `"P-3"` i `"1,20 m"` a
    `"S-1"`: identificadors inventats amb aparenca de bons, i el cistell `"S-?"` dels
    inclassificables es quedava buit. El que no es llegeix ha de tornar `None`.

    Limit conegut: `"Sondeig 1"` (paraula sencera, sense la sigla) torna `None` i va al
    cistell. Cap dels 9 corpus reals fa servir aquesta forma; ampliar-hi el recurs
    tornaria a obrir la porta a `"Mostra 1"`.
    """
    if value is None:
        return None
    text = str(value)
    m = _POINT_RE.search(text)
    if m:
        return f"{m.group(1).upper()}-{int(m.group(2))}"
    letter = (default_letter or "").strip().upper()[:1]
    if not letter:
        return None
    m_num = _BARE_NUM_ID_RE.fullmatch(text.strip())
    return f"{letter}-{int(m_num.group(1))}" if m_num else None


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
    if _is_v0_source(src):
        is_a = False
        conf = _v0_conf(conf)
        note = f"{_V0_NOTE}; {note}" if note else _V0_NOTE
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
            # dialectes del lector (productor cec): `value_candidates` (Linyola, skill 1.8), `valor_candidats`…
            for k in ("candidats_suma", "candidates_suma", "candidates", "candidats", "value_candidates",
                      "valor_candidats", "candidats_valor", "n30_candidats"):
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
            if not out and isinstance(reg, list):
                # L1 (Pas 3b): un tram amb ≥ 50 cops es rebuig; les caselles seguents queden buides (Linyola: «50, -, -, -»)
                nums = [_numbers(str(x)) for x in reg if x not in (None, "", [])]
                if nums and any(n and n[0] >= 50 for n in nums):
                    out.append(mk("R", n="(derivat: ≥ 50 cops en un tram de 15 cm = rebuig; la resta de caselles buides — Pas 3b)",
                                  extra={"registre": reg}))
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


def _nf_positive_over_absence(cell_out: dict, sigs: list[Signal]) -> None:
    """R6 (2026-09-05, mesura dels 8, Vilanova P-3): a `nivell_freatic` una columna N.F. BUIDA als documents A (Excel
    DPSH, annex DPSH) es absencia d'anotacio, no una mesura de «no»; una marca al tall («Aigua») o al full de camp
    («Humit») es evidencia positiva encara que el document no sigui A de la cel·la. Com que a les cel·les de taula nomes
    els A contradiuen (Pas 3b), «No detectat» sortia segur amb el positiu a `altres` (signat: «P-3 Humedad -1.00»).
    Regla: si el candidat 1 es l'absencia i hi ha cap senyal positiu, la cel·la passa a candidats amb el positiu primer
    (el tall es sintesi de l'Eva; despres full de camp; despres la resta per confianca) i «No detectat» a continuacio.
    L'or de lectura ja ho feia aixi («tall primer»). No toca les cel·les on l'absencia es unanime."""
    cands = cell_out.get("candidates") or []
    if not cands or "absent_literal" not in (cands[0].get("extra") or {}):
        return
    positives = [s for s in sigs if s is not None and "absent_literal" not in s.extra and value_key(s.value)[0] != "none"]
    if not positives:
        return
    rank = {"annex_tall": 3, "camp_penetros": 2, "annex_sondeig": 2}
    positives.sort(key=lambda s: (rank.get(s.doc_type, 1), s.is_a, s.confidence), reverse=True)
    pos_ids = {id(s) for s in positives}
    absents = [s for s in sigs if s is not None and id(s) not in pos_ids]
    absents.sort(key=_prefer_form, reverse=True)
    chosen: list[Signal] = [positives[0]] + absents[:1] + positives[1:]
    seen: set[str] = set()
    ordered: list[Signal] = []
    for s in chosen + absents[1:]:
        k = str(s.value).strip().lower()
        if k in seen:
            continue
        seen.add(k)
        ordered.append(s)
    cell_out["estat"] = "candidats"
    cell_out["candidates"] = [s.as_candidate() for s in ordered[:MAX_CANDIDATES]]
    rest = [s.as_candidate() for s in ordered[MAX_CANDIDATES:]] + [s.as_candidate() for s in sigs if s is not None and s not in ordered]
    if rest:
        cell_out["altres"] = rest
    else:
        cell_out.pop("altres", None)
    cell_out["value"] = ordered[0].value
    cell_out["rule"] = (cell_out.get("rule") or "") + (
        f"; R6: columna N.F. buida als documents A = absencia d'anotacio; evidencia positiva a "
        f"{positives[0].doc} ({positives[0].doc_type}) → candidats, positiu primer, «No detectat» despres")


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


def consolidate_tables(corpus: Corpus, conflicts: list[dict], superficie: dict | None = None) -> dict[str, Any]:
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
                    _nf_positive_over_absence(cell_out, sigs)
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
            if block == "spt_ma_tests":
                _ma_sample_has_no_n30(row_out)
            extras = {}
            for doc, r in rows:
                if isinstance(r.get("extra"), dict):
                    extras[doc.get("source_path", "?")] = r["extra"]
            if extras:
                row_out["extra"] = extras
            rows_out.append(row_out)
        if block == "dpsh_tests":
            _dpsh_cota_header_coherence(rows_out)
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
            if keys and keys[0] == "cover":
                cover_de = rows_out[0].get("de")
                if isinstance(cover_de, dict) and cover_de.get("estat") == "no_trobat":
                    # E2b: la cobertura comença a la superficie per definicio (regla geometrica, no una lectura).
                    cover_de["estat"] = "segur"
                    cover_de["value"] = "0,00"
                    cover_de["candidates"] = [{"value": "0,00", "font": "(definició: la cobertura arrenca a la superfície)", "quote": ""}]
                    cover_de["rule"] = "Pas 3b: la capa de cobertura comença a 0,00 per definició"
                cover_a = rows_out[0].get("a")
                if (isinstance(cover_a, dict) and cover_a.get("estat") == "no_trobat" and len(rows_out) > 1):
                    first_de = rows_out[1].get("de")
                    first_nums = _numbers(str(first_de.get("value"))) if isinstance(first_de, dict) else ()
                    if (isinstance(first_de, dict) and first_de.get("estat") == "segur"
                            and first_nums and first_nums[0] <= _SURFACE_TOL):
                        # E2: sense fondaries de la cobertura, la transicio cobertura/nivell 1 no esta documentada.
                        first_de["estat"] = "candidats"
                        first_de["rule"] = ("Pas 3b: hi ha capa de cobertura (llegenda del tall) sense fondàries llegides i "
                                             "el nivell 1 arrenca a 0,00 → la transició cobertura/nivell 1 no està "
                                             "documentada numèricament: candidats (pregunta 3 a l'Eva)")
                        estat_bloc = "candidats"
        tables[block] = {"estat_bloc": estat_bloc, "rows": rows_out, "sources_checked": srcs}

    # La cel·la que mana es la que `consolidate_python` ja ha calculat (i ha fet servir per
    # als derivats): una sola decisio per consolidacio, no dues. Si no ens l'han passada
    # (crida directa des d'un test), es recalcula — la funcio es idempotent.
    tables["superficie_construida"] = superficie if superficie is not None else _superficie_construida(corpus)
    return tables


def _ma_sample_has_no_n30(row_out: dict) -> None:
    """L3 (1.5): si totes les etiquetes de la fila son de mostra alterada (MA), `n30` passa a `no_trobat` amb el motiu a la
    nota; els candidats llegits (un colpeig anotat al full) van a `altres` (garantia 1) i el `registre` es conserva."""
    idc = row_out.get("id")
    n30 = row_out.get("n30")
    if not isinstance(idc, dict) or not isinstance(n30, dict) or n30.get("estat") != "candidats":
        return
    labels = [c.get("value") for c in (idc.get("candidates") or [])] or [idc.get("value")]
    labels = [str(v) for v in labels if v is not None]
    if not labels or not all(_MA_ID_RE.search(v) for v in labels):
        return
    reg = n30.get("registre") if isinstance(n30.get("registre"), dict) else None
    colpeig = reg.get("value") if reg and reg.get("estat") != "no_trobat" else None
    old_cands = list(n30.get("candidates") or [])
    note = "mostra alterada (MA): sense N30 a l'informe (l'Eva escriu «--»)"
    if colpeig:
        note += f"; colpeig anotat al full ({'/'.join(str(x) for x in colpeig) if isinstance(colpeig, list) else colpeig}) conservat a `registre`"
    n30["estat"] = "no_trobat"
    n30["value"] = None
    n30.pop("candidates", None)
    n30["altres"] = old_cands + list(n30.get("altres") or [])
    n30["note"] = note
    n30["rule"] = "L3 (Pas 3b): per a MA, n30 = no_trobat amb nota; el generador escriu «--»"


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


_INT_COTA_RE = re.compile(r"^\s*[+\-−]?\d{2,4}(?![0-9.,])")   # «+212 msnm» si; «+212,50 msnm» no (sense retrocedir a «21»)


def _dpsh_cota_header_coherence(rows_out: list[dict]) -> None:
    """F1 (2026-09-05, Rubi): la capçalera de l'annex DPSH imprimeix la cota d'inici per pagina; la p.2 diu «+212 msnm»
    i la p.1/p.3 «+212,50 msnm» (el signat: +212,50 als tres punts). Un literal SENSE decimals entre germans del
    mateix document que comparteixen la part entera i porten decimals es un truncament d'impressio, no una altra
    mesura → candidats [cota coherent dels altres punts, literal propi], mai segur. No toca cotes amb decimals
    explicits (Castellar -4,0 / -4,2) ni fulls on tots els punts coincideixen (Linyola +245 ×3)."""
    cells = [(r, r.get("cota_inici")) for r in rows_out if isinstance(r.get("cota_inici"), dict)]
    decided = [(r, c) for r, c in cells if c.get("estat") == "segur" and isinstance(c.get("value"), str) and _numbers(c["value"])]
    for r, c in decided:
        v = c["value"]
        if not _INT_COTA_RE.match(v):
            continue
        n = _numbers(v)[0]
        font0 = str((c.get("candidates") or [{}])[0].get("font", ""))
        doc0 = font0.split(" p.")[0]
        siblings = [(r2, c2) for r2, c2 in decided if c2 is not c and not _INT_COTA_RE.match(c2["value"])
                    and int(_numbers(c2["value"])[0]) == int(n) and abs(_numbers(c2["value"])[0] - n) < 1
                    and str((c2.get("candidates") or [{}])[0].get("font", "")).split(" p.")[0] == doc0]
        if len(siblings) < 2:
            continue
        sib_vals = {c2["value"] for _, c2 in siblings}
        if len({round(_numbers(x)[0], 3) for x in sib_vals}) != 1:
            continue
        r2, c2 = siblings[0]
        pts = "/".join(str(x.get("punt", {}).get("value") if isinstance(x.get("punt"), dict) else x.get("punt")) for x, _ in siblings)
        coherent = {"value": c2["value"], "font": f"(capçalera coherent: {pts} del mateix annex) ← {(c2.get('candidates') or [{}])[0].get('font', '')}",
                    "quote": (c2.get("candidates") or [{}])[0].get("quote", ""),
                    "note": f"F1: la capçalera d'aquesta pagina imprimeix «{v}» sense decimals; les de {pts} diuen «{c2['value']}» → possible truncament, confirmar amb l'Eva"}
        c["estat"] = "candidats"
        c["candidates"] = ([coherent] + list(c.get("candidates") or []))[:MAX_CANDIDATES]
        c["value"] = coherent["value"]
        c["rule"] = (f"F1: capçalera de la pagina sense decimals («{v}») vs {pts} del mateix annex («{c2['value']}»): "
                     "possible truncament d'impressio → candidats, mai segur; " + str(c.get("rule") or ""))


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
            # NOMES `punt`: `id` es l'etiqueta de l'assaig ("SPT-2" = 2n assaig, "MA1" =
            # mostra 1), no el sondeig. Fer-lo servir com a font de la lletra enganxava
            # l'assaig al sondeig equivocat; sense identificador de punt va al cistell "S-?".
            punt = _point_key(r.get("punt"), "S") or "S-?"
            entries.append((d, r, punt, _spt_interval(r)))
    entries.sort(key=lambda e: (prio.get(e[0].get("document_type"), 9), e[3] is None))
    groups: list[dict] = []  # {punt, iv, rows}
    for d, r, punt, iv in entries:
        target = None
        for g in groups:
            # `"S-?"` (cap identificador llegible) es un cistell d'inclassificables, no un
            # comodi: fusionar-lo amb el primer grup d'interval compatible enganxava la fila
            # al sondeig equivocat. Nomes s'agrupa amb altres inclassificables.
            if g["punt"] != punt:
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


def _component_m2(c: Any) -> float | None:
    """Superficie d'UN sumand de `superficie_construida`, o `None` si no es llegible.

    Bessona de `tables_report._component_number` (i el total que surt d'aqui hi acaba,
    via `_sum_total`): en un dict la xifra ja ve aillada a la CLAU CANONICA
    (`normalize.COMPONENT_VALUE_KEY`, posada per `load_corpus`) i el primer numero es el bo;
    en un STRING el primer numero es el de l'etiqueta (`"P1: 85 m2"` -> 1), i nomes val la
    xifra ancorada a unitat o, si no n'hi ha cap, l'unic numero del text.

    Aqui NO hi ha cap llista de claus de dialecte: viu tota a `normalize`, i corre una sola
    vegada a l'entrada. Abans n'hi havia dues de divergents i el dialecte real de Linyola
    (`valor`) queia entre les dues.
    """
    if isinstance(c, dict):
        v = c.get(COMPONENT_VALUE_KEY)
        n = _numbers(str(v)) if v is not None else ()
        return n[0] if n else None
    if c is None:
        return None
    text = str(c)
    with_unit = UNIT_M2_RE.findall(text)
    if len(with_unit) == 1:
        n = _numbers(with_unit[0])
        return n[0] if n else None
    if with_unit:
        return None
    n = _numbers(text)
    return n[0] if len(n) == 1 else None


def _superficie_construida(corpus: Corpus) -> dict:
    """Cel·la `tables.superficie_construida` a partir de tots els documents del corpus.

    Funcio PURA i IDEMPOTENT sobre el corpus: `entries` es una COPIA de la llista del
    document. Abans n'era un alies i s'estenia mentre es recorria (`entries.extend(rows)`),
    de manera que la llista del corpus creixia a cada crida — i se'n fan dues sobre el
    mateix corpus en memoria (`consolidate_python` per als derivats, `consolidate_tables`
    per a la taula): la segona, la que s'envia, duplicava cada component i cada senyal, i
    els senyals identics duplicats podien inflar el consens de `decide()`.
    """
    srcs = _block_sources(corpus, "superficie_construida")
    sigs: list[Signal] = []
    components_all: list[Any] = []
    etiqueta: str | None = None
    for d in corpus.docs:
        tables = d.get("tables") or {}
        raw = tables.get("superficie_construida")
        entries = list(raw) if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
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
                nums = [_component_m2(c) for c in comps]
                # un sol sumand il·legible anul·la la suma sintetica: el total sortiria
                # incomplet i, a `tables_report._sum_total`, amb aparenca de xifra bona
                if nums and all(n is not None for n in nums):
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
    # ordre: client_name abans que architect_name (guard + derivat), num_floors abans que cte.
    # referencia_catastral/superficie_parcela al final: `cadastre_portal_signals` llegeix
    # `decided["street_address"]`/`["municipality"]`, que han d'estar ja decidits (Fix D).
    _CADASTRE_KEYS = ("referencia_catastral", "superficie_parcela")
    order = (
        ["client_name", "num_floors"]
        + [k for k in sorted(ALLOWED_FIELD_KEYS) if k not in ("client_name", "num_floors", *_CADASTRE_KEYS)]
        + list(_CADASTRE_KEYS)
    )
    sc = _superficie_construida(corpus)
    for key in order:
        sigs = list(by_key.get(key, []))
        if not sigs or all(value_key(s.value)[0] == "none" for s in sigs):
            # Nomes forats: primer el Cadastre per portal (nomes referencia_catastral/superficie_parcela,
            # font externa real de la via A), despres les altres consultes HTTP, despres les
            # derivacions/coneixement previ.
            if key in _CADASTRE_KEYS and "cadastre" in _http_enabled_sources():
                from automation.lectura.cadastre_reader import cadastre_portal_signals
                sigs += cadastre_portal_signals(key, fields, project_path, extra_concepts)
            sigs += http_field_signals(key, project_path)
            sigs += derived_field_signals(key, fields, sc)
        cell = decide(
            sigs, sources_checked=sources_for(key), field_name=key, abs_numbers=key in _ABS_FIELDS,
            never_segur=key in _NEVER_SEGUR_FIELDS, segur_requires=_guard_for_field(key, fields),
            conflicts=conflicts, path=f"fields.{key}",
        )
        if key == "street_address":
            _promote_entre_carrers(cell)
        if key == "municipality":
            _canonical_municipality(cell)
        if key in descartats:
            cell["descartats"] = descartats[key]
        fields[key] = cell
    fields = {k: fields[k] for k in sorted(fields)}

    tables = consolidate_tables(corpus, conflicts, superficie=sc)
    _cota_relative_system(fields, tables)
    _depths_from_msnm(fields, tables)
    _derive_soil_levels(fields, tables)

    notes = [
        f"_decisions.json generat per consolidacio Python-first (Fase 12, {CONSOLIDATOR_VERSION}): "
        f"{len(corpus.docs)} documents llegits, {len(corpus.g3.get('documents', [])) if corpus.g3 else 0} plantilles G3, "
        f"{len(conflicts)} conflictes A-vs-A",
    ]
    if corpus.duplicates:
        notes.append("duplicats per md5 (no compten dos cops): " + ", ".join(f"{a} = {b}" for a, b in corpus.duplicates.items()))
    if corpus.lectura_fallida:
        notes.append("lectura fallida (sense {doc}.json): " + ", ".join(corpus.lectura_fallida))
    if corpus.orfes:
        notes.append("lectures orfes descartades (el fitxer ja no es a l'inventari): " + ", ".join(corpus.orfes))
    if corpus.component_dialects:
        # RASTRE de dialectes: el lector es un productor cec i pot estrenar noms de camp a
        # qualsevol execucio. Va a `notes_estructurals` (i no a un log) perque viatja DINS del
        # `_decisions.json` de cada projecte, que es l'artefacte que conservem i comparem
        # execucio rere execucio: aixi, d'aqui a unes quantes, sabrem quins dialectes surten
        # de veritat en comptes de continuar endevinant-los. Es el mateix canal que ja porta
        # duplicats/orfes/lectures fallides.
        notes.append(
            "sumands de superficie_construida amb claus fora de normalize.COMPONENT_VALUE_ALIASES "
            f"({', '.join(corpus.component_dialects)}): llegits per forma (xifra ancorada a m²) o "
            "deixats en blanc; afegiu-les als alies si es repeteixen")
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


def _is_rel_cota(v: Any) -> bool:
    t = str(v or "").lower()
    n = _numbers(t)
    return "respecte" in t or "relati" in t or (bool(n) and abs(n[0]) < 50)


def _cota_relative_system(fields: dict[str, dict], tables: dict[str, Any]) -> None:
    """R2 / Pas 3b (Castellar): la cota de referencia absoluta (annex sondeig, z ICGC) es segura per si sola, pero si
    l'annex DPSH treballa en sistema RELATIU («-4,0 m respecte el carrer», cel·la `cota_inici` segura), l'Eva te dues
    sortides amb sistemes diferents i l'informe pot usar l'una o l'altra → candidats [absoluta, relativa] (or de
    Castellar; `_LESSONS`: l'informe signat de Castellar diu -4,0). No toca res quan l'annex DPSH ja es absolut."""
    cell = fields.get("cota_referencia") or {}
    if cell.get("estat") != "segur" or _is_rel_cota(cell.get("value")):
        return
    rows = ((tables.get("dpsh_tests") or {}).get("rows") or [])
    rel: dict | None = None
    for r in rows:
        c = r.get("cota_inici") if isinstance(r, dict) else None
        if isinstance(c, dict) and c.get("estat") == "segur" and _is_rel_cota(c.get("value")):
            rel = c
            break
    if rel is None:
        return
    c0 = (rel.get("candidates") or [{}])[0]
    cand = {"value": f"{rel.get('value')} (annex DPSH, sistema relatiu)", "font": c0.get("font", "annex DPSH cota_inici"),
            "quote": c0.get("quote", ""),
            "note": "l'annex DPSH treballa en cotes relatives al carrer; l'informe de Castellar les va usar (Pas 3b)"}
    cell["estat"] = "candidats"
    cell["candidates"] = ([cell["candidates"][0]] + [cand] + cell["candidates"][1:])[:MAX_CANDIDATES]
    cell["rule"] = ("Pas 3b: dues sortides de l'Eva amb sistemes diferents (annex sondeig absoluta vs annex DPSH relativa "
                    "'respecte el carrer'): l'informe pot usar l'una o l'altra → candidats (R2); " + str(cell.get("rule") or ""))


def _fmt_depth(cota: float, n: float, decimals: int) -> str:
    d = round(cota - n, decimals)
    if abs(d) < 10 ** (-decimals) / 2:
        return "0," + "0" * decimals
    txt = f"{abs(d):.{decimals}f}".replace(".", ",")
    return ("-" if d > 0 else "+") + txt


def _decimals(txt: str) -> int:
    return max(1, len(txt.split(",")[1]) if "," in txt else (len(txt.split(".")[1]) if "." in txt else 0))


def _msnm_scale(n: float, cota: float) -> bool:
    return n >= 100 and cota - 30 <= n <= cota + 5


def _depth_candidates(text: str, cota: float, cota_txt: str) -> list[tuple[str, str]]:
    """`[(valor en fondaria, cota original), …]`: un per punt quan el text els dona; si no, la conversio en el lloc.
    Buit si el text no porta cap nombre a l'escala de la cota."""
    per_point: list[tuple[str, str]] = []
    for m in _MSNM_POINT_RE.finditer(text):
        n1 = float(m.group(2).replace(",", "."))
        n2 = float(m.group(3).replace(",", ".")) if m.group(3) else None
        if not _msnm_scale(n1, cota) or (n2 is not None and not _msnm_scale(n2, cota)):
            continue
        dec = max(_decimals(m.group(2)), _decimals(m.group(3)) if m.group(3) else 1)
        depth = _fmt_depth(cota, n1, dec) + (("/" + _fmt_depth(cota, n2, dec)) if n2 is not None else "")
        orig = m.group(2) + (("-" + m.group(3)) if m.group(3) else "")
        for pt in re.split(r"\s*/\s*", m.group(4)):
            pk = _point_key(pt, default_letter="P") or pt
            per_point.append((f"{m.group(1)}{depth} m a {pk} (contacte {m.group(1)}{orig} msnm)", orig))
    if per_point:
        return per_point
    originals: list[str] = []

    def sub(m: "re.Match") -> str:
        n1 = float(m.group(2).replace(",", "."))
        n2 = float(m.group(3).replace(",", ".")) if m.group(3) else None
        if not _msnm_scale(n1, cota) or (n2 is not None and not _msnm_scale(n2, cota)):
            return m.group(0)
        dec = max(_decimals(m.group(2)), _decimals(m.group(3)) if m.group(3) else 1)
        originals.append(m.group(2) + (("-" + m.group(3)) if m.group(3) else ""))
        depth = _fmt_depth(cota, n1, dec) + (("/" + _fmt_depth(cota, n2, dec)) if n2 is not None else "")
        return f"{m.group(1)}{depth} m"

    out = _MSNM_NUM_RE.sub(sub, text)
    if not originals:
        return []
    return [(f"{out} (cota {', '.join(originals)} msnm)", ", ".join(originals))]


def _depths_from_msnm(fields: dict[str, dict], tables: dict[str, Any]) -> None:
    """R2 (Linyola, Alcoletge): el lector copia l'escala msnm del tall als nivells i al freatic; l'informe vol
    fondaries. Conversio determinista amb la cota de referencia SEGURA del mateix `_decisions.json`; cada candidat en
    msnm es reemplaça pel seu valor en fondaria (font «(derivat: fondaria = cota − msnm) ← …», la lectura original a
    la nota i a la cita). Cap candidat nou: els mateixos, en el sistema de l'informe."""
    cell = fields.get("cota_referencia") or {}
    m = _LEADING_COTA_RE.match(str(cell.get("value") or ""))
    if cell.get("estat") != "segur" or not m:
        return
    cota = float(m.group(1).replace("−", "-").replace(",", "."))
    if cota < 100:
        return
    cota_txt = m.group(1).replace("−", "-")
    for block, cellname in _MSNM_CELLS:
        for row in ((tables.get(block) or {}).get("rows") or []):
            c = row.get(cellname) if isinstance(row, dict) else None
            if not isinstance(c, dict) or c.get("estat") not in ("segur", "candidats"):
                continue
            new_cands: list[dict] = []
            changed = False
            for cand in c.get("candidates") or []:
                v = cand.get("value")
                conv = _depth_candidates(str(v), cota, cota_txt) if isinstance(v, str) and "msnm" in v.lower() or (
                    isinstance(v, str) and any(_msnm_scale(n, cota) for n in _numbers(v))) else []
                if not conv:
                    new_cands.append(cand)
                    continue
                changed = True
                for depth_txt, orig in conv:
                    d = dict(cand)
                    d["value"] = depth_txt
                    d["font"] = f"(derivat: fondaria = cota {cota_txt} − {orig} msnm) ← {cand.get('font', '')}"
                    d["note"] = f"R2: lectura original en msnm «{v}»" + (f"; {cand['note']}" if cand.get("note") else "")
                    new_cands.append(d)
            if not changed:
                continue
            c["candidates"] = new_cands[:MAX_CANDIDATES]
            if len(new_cands) > MAX_CANDIDATES:
                c["altres"] = new_cands[MAX_CANDIDATES:] + list(c.get("altres") or [])
            c["value"] = new_cands[0]["value"]
            c["rule"] = f"R2: convertit a fondaria amb la cota de referencia {cota_txt} msnm (sistema de l'informe); " + str(c.get("rule") or "")


# ---------------------------------------------------------------------------------------------------------------
# 1.4 (bloc 1, 2026-09-06): derivats geometrics de `soil_levels` — regles de l'or (`_tables_decisions.json`, camp
# `rule`) que cap lector emet perque no son lectures sino consequencies del perfil:
#   D1  el primer nivell (sense capa de cobertura) arrenca a 0,00 per definicio (E2b ja ho fa per a la cobertura);
#   D2  el sostre del nivell N es la base del nivell N-1 (mateixa transicio);
#   D3  la base de l'ultim nivell no la dona cap document (el substrat no es travessa): el limit conegut es el fons
#       d'investigacio (rebuig DPSH per punt, fondaria del sondeig). El signat l'usa com a gruix sismic (Bell-lloc
#       2,45 = rebuig P-2, no el -1,80 del log del sondeig; Rubi 4,55; Linyola 1,60 + 1,30 = 2,90);
#   D4  `mostra_del_nivell` = el nivell que conte la mostra de laboratori (`lab_depth`, al punt `lab_location`);
#   D5  la litologia de la mostra (`spt_ma_tests`) porta com a candidat la del nivell que la conte.
# Fonts sempre «(derivat: …) ← font original» (garantia 2); `segur` nomes D1 (definicio geometrica, com E2b).
# Cap re-lectura: tot surt del mateix `_decisions.json` (fase 12, cost 0).
# ---------------------------------------------------------------------------------------------------------------

#: Fondaria dins d'un text de cel·la: cal decimal («-1,4», «0,00») o «m» darrere («-4 m»); «Nivell 1» no ho es.
_DEPTH_NUM_RE = re.compile(r"(?<![\d,.\w])[-+−]?(?:\d+[,.]\d+|\d+(?=\s*m\b))")
_FONS_PREFIX = "fins al fons d'investigació"
#: Tolerancia (m) de les comparacions geometriques dels derivats (lectures a 5 cm).
_DERIV_TOL = 0.05


def _depth_nums(text: Any) -> list[float]:
    """Fondaries (valor absolut) d'un text de cel·la `de`/`a`/`profunditat`, fora dels parentesis d'observacio.
    Buit si no n'hi ha cap, si el text es un derivat D3 («fins al fons…») o si es en msnm (≥ 50 m)."""
    t = _strip_parens(str(text))
    if t.strip().lower().startswith(_FONS_PREFIX):
        return []
    nums = [abs(float(n.replace("−", "-").replace(",", "."))) for n in _DEPTH_NUM_RE.findall(t)]
    return [] if not nums or any(n >= 50 for n in nums) else nums


def _fmt_m(d: float) -> str:
    return f"-{d:.2f}".replace(".", ",")


def _fmt_iv(iv: tuple[float, float]) -> str:
    return f"{iv[0]:.2f}-{iv[1]:.2f}".replace(".", ",")


def _cell_depths(cell: Any, pt: str | None) -> tuple[float, float, bool] | None:
    """`(min, max, del_punt)` d'una cel·la `de`/`a`: prefereix les clausules que anomenen el punt `pt` («≈-1,4 m a
    P-3»); si no n'hi ha, les que no anomenen cap punt («-1,80»); None si cap candidat es una fondaria."""
    if not isinstance(cell, dict) or cell.get("estat") not in ("segur", "candidats"):
        return None
    at_pt: list[float] = []
    generic: list[float] = []
    for cand in cell.get("candidates") or []:
        v = cand.get("value")
        if v is None or isinstance(v, bool):
            continue
        # un candidat pot dur diversos punts separats per «;» («~-1,4 m a P-1; ~-1,2 m a P-3»): una clausula per punt
        for clause in _strip_parens(str(v)).split(";"):
            nums = _depth_nums(clause)
            if not nums:
                continue
            pk = _point_key(clause, default_letter="")
            if pk is None:
                generic.extend(nums)
            elif pt and pk == pt:
                at_pt.extend(nums)
    if at_pt:
        return (min(at_pt), max(at_pt), True)
    if generic:
        return (min(generic), max(generic), False)
    return None


def _best_bound(*opts: tuple[float, float, bool] | None) -> tuple[float, float, bool] | None:
    found = [o for o in opts if o is not None]
    return next((o for o in found if o[2]), found[0] if found else None)


def _interval_of(cell: Any) -> tuple[float, float] | None:
    """Interval (inici, fi) en fondaria absoluta d'una cel·la de tram («1,0 - 1,15», «-1,00 a -1,60 m»): el valor si es
    segur; si es candidats, nomes quan tots coincideixen numericament (formes diferents del mateix tram)."""
    if not isinstance(cell, dict) or cell.get("estat") not in ("segur", "candidats"):
        return None
    vals = [cell.get("value")] if cell["estat"] == "segur" else [c.get("value") for c in cell.get("candidates") or []]
    ivs = set()
    for v in vals:
        nums = _depth_nums(v)
        if len(nums) == 2:
            ivs.add((round(min(nums), 2), round(max(nums), 2)))
    return next(iter(ivs)) if len(ivs) == 1 else None


def _single_point(cell: Any, default_letter: str = "") -> str | None:
    if not isinstance(cell, dict) or cell.get("estat") not in ("segur", "candidats"):
        return None
    vals = [cell.get("value")] if cell["estat"] == "segur" else [c.get("value") for c in cell.get("candidates") or []]
    pks = {_point_key(str(v), default_letter=default_letter) for v in vals if v is not None} - {None}
    return pks.pop() if len(pks) == 1 else None


def _fons_rows(tables: dict[str, Any]) -> list[tuple[str, float, str | None, str, str]]:
    """`(id, fondaria, rebuig|None, font, quote)` de cada DPSH i sondeig amb `profunditat_assolida` llegida (DPSH primer,
    en l'ordre de les files; els sondeigs porten `rebuig=None`)."""
    out: list[tuple[str, float, str | None, str, str]] = []
    for block, idkey, letter in (("dpsh_tests", "punt", "P"), ("sondeig_tests", "sondeig", "S")):
        for r in (tables.get(block) or {}).get("rows") or []:
            c = r.get("profunditat_assolida") if isinstance(r, dict) else None
            if not isinstance(c, dict) or c.get("estat") not in ("segur", "candidats"):
                continue
            nums = _depth_nums(c.get("value"))
            if not nums:
                continue
            c0 = (c.get("candidates") or [{}])[0]
            reb = r.get("rebuig") if isinstance(r.get("rebuig"), dict) else None
            pk = _point_key(r.get(idkey), letter) or str(r.get(idkey))
            out.append((pk, nums[0], (str(reb.get("value") or "?") if block == "dpsh_tests" else None),
                        str(c0.get("font", "")), str(c0.get("quote", ""))))
    return out


def _fons_text(fons: list[tuple[str, float, str | None, str, str]]) -> str:
    dpsh = [f for f in fons if f[2] is not None]
    sond = [f for f in fons if f[2] is None]
    parts: list[str] = []
    if dpsh:
        label = "rebuig DPSH" if all(_YES_RE.match(f[2] or "") for f in dpsh) else "profunditat assolida DPSH"
        if len(dpsh) == 1:
            parts.append(f"{label}: {_fmt_m(dpsh[0][1])} m ({dpsh[0][0]})")
        else:
            parts.append(f"{label}: " + "/".join(_fmt_m(f[1]) for f in dpsh) + " m per punt")
    if sond:
        parts.append(("sondeig " if len(sond) == 1 else "sondeigs ") + ", ".join(f"{f[0]}: {_fmt_m(f[1])} m" for f in sond))
    return f"{_FONS_PREFIX} ({'; '.join(parts)})"


def _is_cover_row(row: dict) -> bool:
    return bool(_COVER_RE.search(str(row.get("nom") or "")))


def _derive_first_level_top(rows: list[dict]) -> None:
    """D1: sense capa de cobertura, el primer nivell arrenca a la superficie (0,00) per definicio geometrica — com la
    cobertura a E2b. Omple el `no_trobat`; puja a segur un `candidats` que ja diu 0,00 (Linyola: el tall, conf < 0,8).
    Si hi ha cobertura, el `de` del nivell 1 el resol D2 (base de la cobertura) o E2 (no documentada)."""
    if not rows or _is_cover_row(rows[0]):
        return
    de = rows[0].get("de")
    if not isinstance(de, dict):
        return
    definition = {"value": "0,00", "font": "(definició: el primer nivell arrenca a la superfície)", "quote": ""}
    if de.get("estat") == "no_trobat":
        de.update({"estat": "segur", "value": "0,00", "candidates": [definition],
                   "rule": "1.4/D1: sense capa de cobertura, el primer nivell comença a 0,00 per definició (precedent E2b)"})
    elif de.get("estat") == "candidats":
        nums = [_depth_nums(c.get("value")) for c in de.get("candidates") or []]
        if nums and all(n and max(n) <= _SURFACE_TOL for n in nums):
            rest = list(de["candidates"])
            de["candidates"] = ([definition] + rest)[:MAX_CANDIDATES]
            if len(rest) + 1 > MAX_CANDIDATES:
                de["altres"] = rest[MAX_CANDIDATES - 1:] + list(de.get("altres") or [])
            de["estat"] = "segur"
            de["value"] = "0,00"
            de["rule"] = "1.4/D1: la lectura (0,00) coincideix amb la definició geomètrica del primer nivell → segur; " + str(de.get("rule") or "")


def _derive_level_tops(rows: list[dict]) -> None:
    """D2: el sostre del nivell N es la base del nivell N-1 (mateixa transicio; l'or de Linyola: «mateix contacte que
    'a' del Nivell 1»). Nomes omple `no_trobat`; mai a l'inversa (la base de la cobertura NO es el 0,00 que l'annex
    dona al nivell 1, E2)."""
    for i in range(1, len(rows)):
        de, prev_a = rows[i].get("de"), rows[i - 1].get("a")
        if not (isinstance(de, dict) and de.get("estat") == "no_trobat"):
            continue
        if not (isinstance(prev_a, dict) and prev_a.get("estat") in ("segur", "candidats")):
            continue
        cands = [c for c in prev_a.get("candidates") or []
                 if not str(c.get("value") or "").lower().startswith(_FONS_PREFIX)]
        if not cands:
            continue
        prev_nom = rows[i - 1].get("nom")
        new = []
        for c in cands:
            d = dict(c)
            d["font"] = f"(derivat: mateix contacte que 'a' del nivell anterior «{prev_nom}») ← {c.get('font', '')}"
            d["note"] = "1.4/D2: el sostre d'un nivell és la base de l'anterior (mateixa transició)" + (f"; {c['note']}" if c.get("note") else "")
            new.append(d)
        de.update({"estat": "candidats", "value": new[0]["value"], "candidates": new[:MAX_CANDIDATES],
                   "rule": f"1.4/D2: `de` no llegit → la base del nivell anterior («{prev_nom}»), candidats (derivat, mai segur)"})
        if len(new) > MAX_CANDIDATES:
            de["altres"] = new[MAX_CANDIDATES:] + list(de.get("altres") or [])


def _derive_last_level_base(rows: list[dict], tables: dict[str, Any]) -> None:
    """D3: la base de l'ultim nivell es el fons d'investigacio. Omple el `no_trobat` (Linyola, Rubi, Vilanova, Anciles);
    si ja hi ha una base llegida (log del sondeig, Pas 3b la deixa en candidats) i el reconeixement arriba mes avall,
    afegeix el fons com a candidat (Bell-lloc: log -1,80 vs rebuig P-2 -2,45; el signat posa 2,45)."""
    fons = _fons_rows(tables)
    if not rows or not fons:
        return
    a = rows[-1].get("a")
    if not isinstance(a, dict):
        return
    fonts = list(dict.fromkeys(f[3] for f in fons if f[3]))
    cand = {"value": _fons_text(fons),
            "font": "(derivat: la base de l'últim nivell és el fons d'investigació) ← " + "; ".join(fonts[:3]) + (" …" if len(fonts) > 3 else ""),
            "quote": next((f[4] for f in fons if f[4]), ""),
            "note": "1.4/D3: cap document dona la base de l'últim nivell (el substrat no es travessa): el límit conegut és fins on arriba el reconeixement"}
    deepest = max(f[1] for f in fons)
    if a.get("estat") == "no_trobat":
        a.update({"estat": "candidats", "value": cand["value"], "candidates": [cand],
                  "rule": "1.4/D3: la base de l'últim nivell no la dona cap document → el fons d'investigació (rebuig DPSH per punt / fondària del sondeig), candidats, mai segur"})
        return
    if a.get("estat") != "candidats":
        return
    existing = a.get("candidates") or []
    if any(str(c.get("value") or "").lower().startswith(_FONS_PREFIX) for c in existing):
        return
    read = [n for c in existing for n in _depth_nums(c.get("value"))]
    depths = [f[1] for f in fons]
    if read and all(any(abs(r - d) <= _DERIV_TOL for d in depths) for r in read):
        # Les bases llegides SON les fondaries de rebuig / del sondeig (annex DPSH: la banda de color de l'ultim nivell
        # acaba on acaba l'assaig; log del sondeig): final del reconeixement, no una transicio → el fons, primer.
        cands = [cand] + existing
        a["candidates"] = cands[:MAX_CANDIDATES]
        if len(cands) > MAX_CANDIDATES:
            a["altres"] = cands[MAX_CANDIDATES:] + list(a.get("altres") or [])
        a["value"] = cand["value"]
        a["rule"] = str(a.get("rule") or "") + "; 1.4/D3: la base llegida coincideix amb el fons d'investigació (rebuig DPSH / fondària del sondeig): és el final del reconeixement, no una transició → el fons primer, per punt"
        return
    if read and deepest > max(read) + _DERIV_TOL:
        if len(existing) < MAX_CANDIDATES:
            existing.append(cand)
        else:
            a["altres"] = [cand] + list(a.get("altres") or [])
        a["rule"] = str(a.get("rule") or "") + "; 1.4/D3: el reconeixement (DPSH/sondeig) arriba més avall que la base llegida: el nivell continua com a mínim fins al fons d'investigació"


def _level_membership(rows: list[dict], iv: tuple[float, float], pt: str | None, fons_pt: float | None
                      ) -> list[tuple[int, str, float, tuple[float, float, float, float]]]:
    """Per a cada nivell amb sostre i base coneguts al punt `pt`: `(i, 'dins'|'fora'|'cavall', part de l'interval dins,
    (sostre_min, sostre_max, base_min, base_max))`. El sostre es el `de` propi o la `a` de l'anterior; la base es la `a`
    propia, el `de` del seguent o, a l'ultim nivell, el fons d'investigacio al punt. Un nivell de gruix nul (el 0,00 que
    l'annex dona al nivell 1 sota una cobertura sense base, E2) no es cap interval."""
    s0, s1 = iv
    n = len(rows)
    out = []
    for i, row in enumerate(rows):
        top = _best_bound(_cell_depths(row.get("de"), pt), _cell_depths(rows[i - 1].get("a"), pt) if i else None)
        bot = _best_bound(_cell_depths(row.get("a"), pt), _cell_depths(rows[i + 1].get("de"), pt) if i + 1 < n else None)
        if bot is None and i == n - 1 and fons_pt is not None:
            bot = (fons_pt, fons_pt, True)
        if top is None or bot is None or bot[1] <= top[0] + _DERIV_TOL:
            continue
        t_lo, t_hi, b_lo, b_hi = top[0], top[1], bot[0], bot[1]
        if s0 >= t_hi - _DERIV_TOL and s1 <= b_lo + _DERIV_TOL:
            out.append((i, "dins", 1.0, (t_lo, t_hi, b_lo, b_hi)))
        elif s1 <= t_lo + _DERIV_TOL or s0 >= b_hi - _DERIV_TOL:
            out.append((i, "fora", 0.0, (t_lo, t_hi, b_lo, b_hi)))
        else:
            t_mid, b_mid = (t_lo + t_hi) / 2, (b_lo + b_hi) / 2
            share = max(0.0, min(s1, b_mid) - max(s0, t_mid)) / max(s1 - s0, 0.01)
            out.append((i, "cavall", round(share, 2), (t_lo, t_hi, b_lo, b_hi)))
    return out


def _fmt_bounds(b: tuple[float, float, float, float]) -> str:
    top = _fmt_m(b[0]) if abs(b[0] - b[1]) < _DERIV_TOL else f"{_fmt_m(b[0])} a {_fmt_m(b[1])}"
    bot = _fmt_m(b[2]) if abs(b[2] - b[3]) < _DERIV_TOL else f"{_fmt_m(b[2])} a {_fmt_m(b[3])}"
    return f"[{top}; {bot}] m"


def _fons_at(fons: list[tuple[str, float, str | None, str, str]], pt: str | None) -> float | None:
    return next((f[1] for f in fons if pt and f[0] == pt), None)


def _derive_sample_level(rows: list[dict], fields: dict[str, dict], tables: dict[str, Any]) -> None:
    """D4: `mostra_del_nivell` = el nivell que conte `lab_depth` al punt `lab_location` (interval, no judici de
    material). Dins → True; fora → False; a cavall del contacte → els dos candidats (el de mes part de l'interval
    primer). Omple nomes `no_trobat`; els documents no-A no afirmen False (`_cell_signals`), el derivat si, amb la
    font «(derivat: … cau fora …)». Mai segur."""
    lab = fields.get("lab_depth") or {}
    iv = _interval_of(lab)
    if iv is None:
        return
    pt = _single_point(fields.get("lab_location"))
    fons_pt = _fons_at(_fons_rows(tables), pt)
    c0 = (lab.get("candidates") or [{}])[0]
    where = f"{_fmt_iv(iv)} m" + (f" a {pt}" if pt else "")
    for i, verdict, share, bounds in _level_membership(rows, iv, pt, fons_pt):
        cell = rows[i].get("mostra_del_nivell")
        if not isinstance(cell, dict) or cell.get("estat") not in ("no_trobat", "candidats"):
            continue
        if cell.get("estat") == "candidats":
            # Lectura d'un document no-A (annex DPSH: «la mostra cavalca la transició», amb el tram nominal 1,0-1,5): si la
            # geometria (tram real del GTL al punt) diu una altra cosa, el derivat s'hi afegeix; el llegit continua primer.
            have = {c.get("value") for c in cell.get("candidates") or []}
            derived = True if verdict == "dins" else False if verdict == "fora" else None
            if derived is None or derived in have or len(cell.get("candidates") or []) >= MAX_CANDIDATES:
                continue
            why = "cau dins" if derived else "cau fora"
            cell["candidates"].append({
                "value": derived,
                "font": f"(derivat: la mostra de laboratori {where} {why} del nivell {_fmt_bounds(bounds)}) ← {c0.get('font', '')}",
                "quote": str(c0.get("quote", "")),
                "note": "1.4/D4: la geometria (tram real de la mostra vs sostre/base al punt) no coincideix amb el que afirma el document"})
            cell["rule"] = str(cell.get("rule") or "") + "; 1.4/D4: afegit el derivat geomètric que contradiu la lectura (candidats, l'Eva decideix)"
            continue

        def mk(val: bool, why: str) -> dict:
            return {"value": val,
                    "font": f"(derivat: la mostra de laboratori {where} {why} del nivell {_fmt_bounds(bounds)}) ← {c0.get('font', '')}",
                    "quote": str(c0.get("quote", "")),
                    "note": "1.4/D4: interval de la mostra vs sostre/base del nivell al punt de la mostra; no jutja el material"}

        if verdict == "dins":
            cands = [mk(True, "cau dins")]
        elif verdict == "fora":
            cands = [mk(False, "cau fora")]
        else:
            pct_in = int(round(share * 100))
            first, second = (True, False) if share >= 0.5 else (False, True)
            cands = [mk(first, f"cau a cavall del contacte ({pct_in} % dins)"),
                     mk(second, f"cau a cavall del contacte ({100 - pct_in} % fora)")]
        cell.update({"estat": "candidats", "value": cands[0]["value"], "candidates": cands,
                     "rule": "1.4/D4: mostra_del_nivell = el nivell que conté lab_depth (interval al punt de la mostra); "
                             "a cavall del contacte → els dos candidats; derivat, mai segur"})


def _same_lithology(a: Any, b: Any) -> bool:
    x, y = _ascii(_strip_parens(str(a))).lower().strip(" ."), _ascii(_strip_parens(str(b))).lower().strip(" .")
    return bool(x and y) and (x == y or x in y or y in x)


def _derive_sample_lithology(rows: list[dict], tables: dict[str, Any]) -> None:
    """D5: la litologia de cada mostra/assaig (`spt_ma_tests[*].litologia`) porta com a candidat la litologia del
    nivell que conte el seu tram al seu punt (l'or d'Alcoletge: «Lutites (Nivell 2)», «Rebliment antròpic (Nivell 1)»).
    Sempre candidats (`_NEVER_SEGUR_CELLS`); no duplica una redaccio que ja hi es."""
    fons = _fons_rows(tables)
    for r in (tables.get("spt_ma_tests") or {}).get("rows") or []:
        if not isinstance(r, dict):
            continue
        iv = _interval_of(r.get("profunditat"))
        if iv is None:
            continue
        pt = _single_point(r.get("punt"))
        lit = r.get("litologia")
        if not isinstance(lit, dict) or lit.get("estat") not in ("no_trobat", "candidats"):
            continue
        members = [m for m in _level_membership(rows, iv, pt, _fons_at(fons, pt)) if m[1] != "fora"]
        members.sort(key=lambda m: -m[2])
        added = []
        for i, verdict, share, bounds in members:
            lvl = rows[i].get("litologia")
            if not isinstance(lvl, dict) or lvl.get("estat") not in ("segur", "candidats"):
                continue
            l0 = (lvl.get("candidates") or [{}])[0]
            value = f"{l0.get('value')} ({rows[i].get('nom')})"
            if any(_same_lithology(l0.get("value"), c.get("value")) for c in (lit.get("candidates") or []) + added):
                continue
            why = "conté el tram de la mostra" if verdict == "dins" else f"el tram de la mostra el travessa ({int(round(share * 100))} % dins)"
            added.append({"value": value,
                          "font": f"(derivat: litologia del nivell que {why}, {_fmt_bounds(bounds)} a {pt or '?'}) ← {l0.get('font', '')}",
                          "quote": str(l0.get("quote", "")),
                          "note": "1.4/D5: la litologia del nivell que conté la mostra per interval; l'Eva re-redacta"})
        if not added:
            continue
        cands = list(lit.get("candidates") or []) + added
        lit["candidates"] = cands[:MAX_CANDIDATES]
        if len(cands) > MAX_CANDIDATES:
            lit["altres"] = cands[MAX_CANDIDATES:] + list(lit.get("altres") or [])
        lit["estat"] = "candidats"
        lit["value"] = lit["candidates"][0]["value"]
        lit["rule"] = (str(lit.get("rule") or "") + "; " if lit.get("rule") else "") + "1.4/D5: + litologia del nivell que conté la mostra (derivat, candidats)"


def _derive_soil_levels(fields: dict[str, dict], tables: dict[str, Any]) -> None:
    """Post-proces 1.4 (despres de `_cota_relative_system` i `_depths_from_msnm`: cal tenir les `a` en fondaria).
    Ordre: D1 → D2 → D3 → D4 → D5 (D4/D5 necessiten sostres i bases)."""
    rows = [r for r in ((tables.get("soil_levels") or {}).get("rows") or []) if isinstance(r, dict)]
    if not rows:
        return
    _derive_first_level_top(rows)
    _derive_level_tops(rows)
    _derive_last_level_base(rows, tables)
    _derive_sample_level(rows, fields, tables)
    _derive_sample_lithology(rows, tables)
    blk = tables.get("soil_levels") or {}
    estats = [c.get("estat") for r in rows for c in r.values() if isinstance(c, dict) and "estat" in c]
    if estats and blk.get("estat_bloc") != "no_trobat":
        blk["estat_bloc"] = "segur" if all(e == "segur" for e in estats) else "candidats"



def _canonical_municipality(cell: dict) -> None:
    """D3 (2026-09-05, mesura dels 8, Vilanova): el valor visible del municipi es la grafia oficial del padro
    (`municipis.lookup().name_ine`) quan TOTES les formes candidates resolen al mateix registre; la forma del
    document queda a la cita (mateix patro que la ISO de les dates). Abans el desempat entre «Vilanova del Segria»
    i «Vilanova de Segria» (mateix cluster, tres fonts A a 0,90) el feia `_prefer_form` per longitud de la cadena.
    Si alguna forma no resol al padro (Anciles, fora de Catalunya) o resolen a municipis diferents, no es toca res."""
    if cell.get("estat") not in ("segur", "candidats"):
        return
    cands = cell.get("candidates") or []
    forms = [c["value"] for c in cands if isinstance(c.get("value"), str) and c["value"].strip()]
    if not forms:
        return
    hits = [_municipi_lookup(f) for f in forms]
    if any(h is None for h in hits) or len({h.ine_code for h in hits}) != 1:
        return
    official = hits[0].name_ine
    if cell.get("value") == official and cands[0].get("value") == official:
        return
    cell["value"] = official
    cands[0]["value"] = official
    cell["rule"] = (cell.get("rule") or "") + f"; D3: grafia oficial del padro (INE {hits[0].ine_code}); la forma del document, a la cita"


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
            # Les claus han de coincidir I ser llegibles: amb `_point_key(rid) !=
            # _point_key(row_key)`, dos `None` (identificador il·legible a totes dues
            # bandes, p. ex. una fila sense `punt` i el cistell "S-?") casaven, i la
            # cel·la de l'LLM queia a QUALSEVOL fila.
            rid_key, want_key = _point_key(rid), _point_key(row_key)
            if str(rid) != row_key and not (rid_key and rid_key == want_key):
                continue
            cell = r.get(cell_name)
            if not isinstance(cell, dict) or _validate_cell(cell, path):
                continue
            if (block, cell_name) in _NEVER_SEGUR_CELLS and cell.get("estat") == "segur":
                continue
            for tr in target_rows:
                trid = tr.get(_ROW_ID_KEY.get(block, "punt"))
                trid_key = _point_key(trid)
                if str(trid) == row_key or (trid_key and trid_key == want_key):
                    prev = tr.get(cell_name, {})
                    cell = dict(cell)
                    cell["llm_only_fields"] = True
                    for keep in ("registre", "matis", "counts", "altres"):
                        if keep in prev and keep not in cell:
                            cell[keep] = prev[keep]
                    tr[cell_name] = cell
                    applied.append(path)
    return out, applied
