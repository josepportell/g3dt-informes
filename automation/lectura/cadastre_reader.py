"""Fase 12 (via A) — lector Cadastre multi-portal de l'adreça llegida.

Vegeu `docs/PLA-PENDENTS-0B-0C-0D-2026-08-26.md` §7 (Fix D). Substitueix el vell mecanisme
`_HTTP_FIELD_SOURCES["referencia_catastral"/"superficie_parcela"]` (que llegia
`validation/_auto_result.json`, l'adreça de la via B) per un lector propi de la via A:
adreça LLEGIDA (`decided["street_address"]`) -> portals (amb lletra) -> RC per portal
(Callejero DNPLOC) -> area oficial + poligon per RC (WFS INSPIRE) -> suma nomes si els
portals son contigus.

Diagnostic 2026-08-26: el Cadastre no falla — per «Carrer Arbrells 18A» torna la parcel·la
correcta (3298012, 441 m2). L'Eva escriu 1.284 perque l'encarrec abasta TRES portals
(18A+18B+20 = 441+423+420) i suma les tres parcel·les. El vell mecanisme nomes en consultava
un (el de `geocode_coordinates`, que a mes agafa el portal MES PROPER quan hi ha lletra —
vegeu `_pick_nearest_rc_from_numerero`, no es pot reutilitzar aqui: cal filtrar `(pnp, plp)`
exactes, no el mes proper).

Nomes importa de la via A el necessari per resoldre municipi/via (`_consulta_municipio`,
`_consulta_via`, `_CATALAN_PROVINCES` de `geocode_coordinates`) i `config.cache_dir`. `Signal`
i `parse_coordenades` s'importen de forma tardana (dins de funcio) per evitar un cicle
d'importacio amb `consolidate.py` (que importa aquest modul de la mateixa manera).

Sense LLM. Qualsevol excepcio de xarxa/parseig es queda aqui (`logger.warning` + `[]`): la
consolidacio mai no pot fallar per aquest lector.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from automation import config, municipis
from automation.lectura import address_struct
from automation.geocode_coordinates import (
    _CATALAN_PROVINCES,
    _consulta_municipio,
    _consulta_via,
    _consulta_via_all_streets,
    _strip_accents,
)

logger = logging.getLogger(__name__)

_DNPLOC_URL = "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/Consulta_DNPLOC"
_WFS_URL = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
_USER_AGENT = "G3DT-Automation/1.0 (Eficients.cat; geotechnical report generation)"
_REQUEST_TIMEOUT_SECONDS = 10
_CACHE_TTL_DAYS = 90
_MAX_PORTALS = 6

#: Modul-level (no dins de `_cache_path`) perque els tests el puguin `monkeypatch.setattr`,
#: mateix patró que `geocode_coordinates.CACHE_DIR` / `icgc_territorial.CACHE_DIR`.
CACHE_DIR = config.cache_dir("cadastre_portals")


# ---------------------------------------------------------------------------
# `portals_from_address`
# ---------------------------------------------------------------------------

_PAREN_RE = re.compile(r"\([^)]*\)")
_NO_PORTAL_RE = re.compile(r"\bentre\s+el\s+carrer\b|\bs\s*/\s*n\b|\bpol[ií]gon\b", re.IGNORECASE)
_STOP_WORD_RE = re.compile(r"\b(?:nau|km|pk|bloc|esc|pis|porta|cp)\b", re.IGNORECASE)
_POSTAL_CODE_RE = re.compile(r"\b\d{5}\b")
_RANGE_RE = re.compile(r"^(\d+)\s*-\s*(\d+)$")
#: `(?![A-Za-z])`: la lletra del portal es UNA lletra solta ("18A", "18 A"), mai la
#: primera d'una paraula ("11 de Setembre" -> `11`, no `11D`).
_PORTAL_TOKEN_RE = re.compile(r"(\d+)\s*([A-Za-z])?(?![A-Za-z])")
#: Paraules-frontera entre portals: mai poden ser la lletra d'un portal. Sense aixo,
#: "18 i 20" es llegia `[("18","I"), ("20","")]` i `resolve_portal` filtrava per una lletra
#: `I` que cap portal real no te -> el 18 tornava [] EN SILENCI (superficie i RC nomes del 20).
_PORTAL_BOUNDARY_RE = re.compile(r"\b(?:i|y|bis|n[uú]m(?:ero)?)\b\.?|n[º°]\.?", re.IGNORECASE)
_TRAILING_BOUNDARY_RE = re.compile(r"[\s,]*(?:\b(?:bis|n[uú]m(?:ero)?)\b\.?|n[º°]\.?)\s*$", re.IGNORECASE)

#: L'alternança agafa la PRIMERA que casa, i les abreviatures curtes son prefix de les
#: llargues: `av\.?` casava dins de "Avda. Catalunya 24" i en deixava el carrer com a
#: `'da. Catalunya'`, que no casa amb cap via del Callejero -> superficie en blanc. Dues
#: mesures, perque la llista d'abreviatures mai no sera completa:
#:   1. les formes llargues van SEMPRE abans que les curtes (`avda` abans d'`av`,
#:      `camino` abans de `cam[ií]`);
#:   2. `(?![^\W\d_])` exigeix que darrere el prefix no hi vagi una altra lletra, de manera
#:      que una abreviatura que encara falti ("Pge.") deixa l'adreça SENCERA —recuperable—
#:      en comptes de mig nom de carrer amb pinta de bo.
#: `c\.?/` queda fora del lookahead: "C/Girassols" (sense espai) es una adreça real.
_STREET_PREFIX_RE = re.compile(
    r"^\s*(?:c\.?/|(?:carrer|calle|avinguda|avenida|avgda\.?|avda\.?|av\.?|pla[cç]a|plaza|pl\.?|"
    r"passeig|paseo|pg\.?|carretera|ctra\.?|camino|cam[ií]|rambla|travessia|travesía)"
    r"(?![^\W\d_]))"
    r"\s*(?:de\s+la\s+|de\s+les\s+|de\s+los\s+|dels\s+|del\s+|de\s+|d')?",
    re.IGNORECASE,
)


def _strip_street_prefix(s: str) -> str:
    stripped = _STREET_PREFIX_RE.sub("", s, count=1).strip()
    return stripped or s.strip()


_PORTAL_ONLY_TOKEN_RE = re.compile(r"\d+[A-Za-z]?")
#: El cap ja acaba en portal ("Avda. Catalunya 24"): aquesta coma no obre la llista, obre
#: el pis. Vegeu `_split_street_and_numbers`.
_HEAD_ENDS_IN_PORTAL_RE = re.compile(r"\d+\s*[A-Za-z]?$")
#: Pis/porta escrits com a ordinal ("3r", "2n", "4t", "5è", "1er", "3º"): mai son portals.
#: Definit a `address_struct` (vocabulari d'adreces, una sola definicio per a tot el projecte);
#: aqui es on es fa servir per tallar "24, 3r 2a" al primer ordinal.
_FLOOR_ORDINAL_RE = address_struct.FLOOR_ORDINAL_RE


def _is_portals_tail(tail: str) -> bool:
    """La cua d'una coma es NOMES portals (`"18A, 18B i 20"`, `"5"`, `"1-50"`)?"""
    cleaned = _PORTAL_BOUNDARY_RE.sub(" ", tail)
    cleaned = re.sub(r"[,;/\-]", " ", cleaned)
    tokens = cleaned.split()
    return bool(tokens) and all(_PORTAL_ONLY_TOKEN_RE.fullmatch(t) for t in tokens)


def _split_street_and_numbers(addr: str) -> tuple[str, str] | None:
    """Separa `"Carrer 11 de Setembre, 5"` en `("Carrer 11 de Setembre", "5")`.

    Talla per la coma que obre la llista de portals — la PRIMERA la cua de la qual ja es
    nomes portals — i no pel primer digit: "Carrer 11 de Setembre" o "Avinguda 11 de
    Setembre" tenen xifres DINS del nom i el tall pel primer digit els destrossava
    (carrer `"Carrer"`, portals `[("11","D"), ("5","")]`).

    Una coma amb el cap ACABAT en numero no obre portals, obre el pis: a
    `"Avda. Catalunya 24, 3r 2a"` la cua "3r 2a" te forma de portals i el tall se'n duia el
    24 al nom del carrer (`"da. Catalunya 24"`), perdent l'unic portal bo. Si el numero ja
    es al cap, el tall bo es el de sempre (primer digit).

    NO es la darrera coma: `"Carrer Arbrells, 18A, 18B i 20"` te comes ENTRE portals, i la
    darrera deixaria el carrer com a `"Arbrells, 18A"`. `None` si cap coma obre una llista
    de portals (llavors el cridant recorre al tall pel primer digit, comportament de sempre).
    """
    for m in re.finditer(",", addr):
        head = addr[: m.start()].strip(" ,")
        if _HEAD_ENDS_IN_PORTAL_RE.search(head):
            continue
        tail = addr[m.end() :]
        if _is_portals_tail(tail):
            return head, tail.strip(" ,")
    return None


def portals_from_address(address: str) -> tuple[str, list[tuple[str, str]]]:
    """`"Carrer Arbrells, 18A, 18B i 20"` -> `("Arbrells", [("18","A"),("18","B"),("20","")])`.

    Retorna `(nom_de_carrer, [(numero, lletra), ...])`. Cap portal (s/n, "entre carrer X i Y",
    Poligon/Nau) -> `([], "")`... be, `(str, [])`: llista de portals buida. Ignora parentesis
    ("(Urb. ...)") i qualsevol cosa despres de nau|km|pk|bloc|esc|pis|porta|cp o un codi postal
    de 5 digits (no son portals). Un guio entre digits ("18-20") es un interval: els dos extrems.
    """
    if not address or not address.strip():
        return "", []
    addr = _PAREN_RE.sub(" ", address).strip()
    addr = re.sub(r"\s+", " ", addr)
    if _NO_PORTAL_RE.search(addr):
        return "", []

    cut = len(addr)
    m_stop = _STOP_WORD_RE.search(addr)
    if m_stop:
        cut = min(cut, m_stop.start())
    m_cp = _POSTAL_CODE_RE.search(addr)
    if m_cp:
        cut = min(cut, m_cp.start())
    addr = addr[:cut].strip(" ,")

    split = _split_street_and_numbers(addr)
    if split is None:
        m_num = re.search(r"\d", addr)
        if not m_num:
            return _strip_street_prefix(addr), []
        # sense coma que obri portals: tall pel primer digit (comportament de sempre), pero
        # sense arrossegar la paraula-frontera FINAL al nom del carrer ("Carrer Major nº 12").
        # Nomes la final: "Carrer Sant Pere i Sant Pau" ha de conservar la seva "i".
        head = _TRAILING_BOUNDARY_RE.sub("", addr[: m_num.start()]).strip(" ,")
        split = (head, addr[m_num.start() :].strip(" ,"))
    street_part, numbers_part = split
    street = _strip_street_prefix(street_part)

    # A partir del primer ordinal ja no hi ha portals, hi ha pis i porta ("24, 3r 2a" ->
    # "24"): tokenitzar-ho tot donava `[("24",""),("3","R"),("2","A")]` i `resolve_portal`
    # pot trobar un 3 i un 2 de debo al carrer -> superficie sumada d'unes parcel·les que
    # no hi tenen res a veure, amb la confiança d'una consulta oficial.
    m_floor = _FLOOR_ORDINAL_RE.search(numbers_part)
    if m_floor:
        numbers_part = numbers_part[: m_floor.start()].strip(" ,;")

    range_m = _RANGE_RE.match(numbers_part)
    if range_m:
        return street, [(range_m.group(1), ""), (range_m.group(2), "")]

    portals: list[tuple[str, str]] = []
    # Les paraules-frontera fora ABANS de tokenitzar (i substituides per una coma, que separa):
    # "18 i 20" -> "18 , 20" (dos portals sense lletra), "12 bis" -> "12 ," (portal 12, cap 'B').
    numbers_part = _PORTAL_BOUNDARY_RE.sub(",", numbers_part)
    for tok in _PORTAL_TOKEN_RE.finditer(numbers_part):
        num, letter = tok.group(1), (tok.group(2) or "").upper()
        portals.append((num, letter))
    return street, portals


# ---------------------------------------------------------------------------
# `resolve_portal` — Callejero DNPLOC (JSON)
# ---------------------------------------------------------------------------


@dataclass
class ParcelHit:
    rc: str
    pnp: str
    plp: str
    ambiguous: bool = False


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def _cache_key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _cache_path(kind: str, key: str) -> Path:
    return CACHE_DIR / f"{kind}_{key}.json"


def _cache_load(kind: str, *parts: str) -> Any | None:
    path = _cache_path(kind, _cache_key(*parts))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    cached_at = payload.get("cached_at")
    try:
        if cached_at and datetime.now() - datetime.fromisoformat(cached_at) > timedelta(days=_CACHE_TTL_DAYS):
            return None
    except ValueError:
        return None
    return payload.get("data")


def _cache_save(kind: str, *parts: str, data: Any) -> None:
    path = _cache_path(kind, _cache_key(*parts))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cached_at": datetime.now().isoformat(timespec="seconds"), "data": data}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _cached_consulta_municipio(province: str, hint: str) -> tuple[str, str, str] | None:
    """Embolcall de cache sobre `geocode_coordinates._consulta_municipio` (via B, sense cache
    propia). `referencia_catastral` i `superficie_parcela` hi criden per separat: sense aquest
    embolcall, cada consolidacio fa DOS cops la resolucio de municipi+via."""
    cached = _cache_load("muni", province, hint)
    if cached is not None:
        return tuple(cached["value"]) if cached.get("found") else None  # type: ignore[return-value]
    result = _consulta_municipio(province, hint)
    _cache_save("muni", province, hint, data={"found": result is not None, "value": list(result) if result else None})
    return result


def _cached_consulta_via(province: str, muni: str, hint: str, full_address_context: str = "") -> tuple[str, str, str] | None:
    cached = _cache_load("via", province, muni, hint)
    if cached is not None:
        return tuple(cached["value"]) if cached.get("found") else None  # type: ignore[return-value]
    result = _consulta_via(province, muni, hint, full_address_context=full_address_context)
    _cache_save("via", province, muni, hint, data={"found": result is not None, "value": list(result) if result else None})
    return result


#: Articles que el Callejero afegeix al nom oficial ("ARBRELLS DELS", "FONT DE LA").
_VIA_ARTICLES = frozenset({"DE", "DEL", "DELS", "DES", "D", "LA", "LES", "EL", "ELS", "LOS", "LAS", "L"})
#: Llindar de semblança per acceptar un nom oficial que NO conte totes les paraules del
#: llegit ("GIRASSOLS" -> "GIRASOLS DELS", 0,94). 0,85 i no 0,80: "CARRER"/"CARRERADA"
#: dona exactament 0,80 i es justament el fals positiu que volem tallar.
_VIA_FUZZY_CUTOFF = 0.85
#: Amb un hint d'una sola paraula (vegeu `_via_name_matches`), les paraules de mes del nom
#: oficial de fins aqui son abreviatures del Callejero ("CARRERADA PD" = partida, "DS" =
#: diseminat), no pas el que distingeix dos carrers ("MAJOR" vs "MAJOR DE BALAFIA").
_VIA_ABBREV_MAX_LEN = 2


def _via_tokens(name: str) -> list[str]:
    text = _strip_accents(str(name or "").upper())
    return [t for t in re.split(r"[^0-9A-Z]+", text) if t and t not in _VIA_ARTICLES]


def _via_name_matches(hint: str, official: str) -> bool:
    """El nom oficial retornat correspon de debo al carrer llegit?

    `geocode_coordinates._consulta_via` puntua 60 qualsevol nom que simplement CONTINGUI el
    text cercat («CARRER» casa amb «CARRERADA»), i tambe accepta un fuzzy de 0,80 — amb
    aixo, un portal es pot resoldre al carrer equivocat i la parcel·la resultant seria d'una
    altra adreça, amb la confiança d'una consulta oficial. `_consulta_via` es codi de la via
    B (produccio de l'Eva): NO es pot tocar, aixi que la comprovacio es fa aqui, al costat
    del lector, descartant el resultat quan no encaixa (blanc honest, mai una parcel·la d'un
    altre carrer).

    Encaixa si totes les paraules significatives del llegit son al nom oficial (l'ordre i
    els articles no compten) o si els dos noms s'assemblen prou (>= 0,85, variants
    ortografiques com GIRASSOLS/GIRASOLS).

    Excepcio: amb un hint d'UNA sola paraula, "totes les paraules hi son" es exactament la
    semantica "conte" de `_consulta_via` que aquesta funcio existeix per tallar — "Major"
    acceptaria "MAJOR DE BALAFIA", que es un altre carrer. Llavors s'exigeix que l'oficial
    no tingui cap paraula sencera de mes: "ARBRELLS DELS" si (article) i "CARRERADA PD" si
    (abreviatura del Callejero, "partida"), pero "MAJOR DE BALAFIA" no.
    """
    hint_tokens = _via_tokens(hint)
    official_tokens = _via_tokens(official)
    if not hint_tokens or not official_tokens:
        return False
    if set(hint_tokens).issubset(set(official_tokens)):
        extra = {t for t in official_tokens if t not in set(hint_tokens) and len(t) > _VIA_ABBREV_MAX_LEN}
        if len(set(hint_tokens)) > 1 or not extra:
            return True
    ratio = difflib.SequenceMatcher(None, " ".join(hint_tokens), " ".join(official_tokens)).ratio()
    return ratio >= _VIA_FUZZY_CUTOFF


# ---------------------------------------------------------------------------
# `resolve_via` — tria de carrer sobre CONJUNT TANCAT (via A)
# ---------------------------------------------------------------------------
#
# Vegeu `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` §5 (peça 1).
#
# `geocode_coordinates._consulta_via` (via B) nomes activa el seu fuzzy i el seu picker LLM
# si el municipi te <= 500 carrers. Rubi (835) i Cerdanyola/Tulipa (577) en queden fora: si
# l'adreca no casa EXACTAMENT al servidor, torna None sense cap intent de recuperacio. Son 2
# dels 8 projectes del corpus. `_consulta_via` es via B de produccio i no es pot tocar, aixi
# que la recuperacio es fa aqui, sense llindar de mida.
#
# Mesurat el 2026-09-01 sobre les llistes reals, la recuperacio de via B tampoc no era
# innocent: a Castellar (481, per sota del llindar) «11 de Setembre» li tornava
# `POL 011 FABRICA NOVA`, i nomes la guarda de 0,85 ho aturava. Per aixo aqui NO es fa fuzzy
# lliure: es compara contra la llista real del municipi i, si hi ha empat, es torna None
# (blanc honest) en comptes de triar.

#: Nombres escrits en lletres -> digits, catala i castella, 1-31 (els noms de carrer que en
#: porten son dates: «Onze de Setembre», «Dos de Maig», «Primer de Maig»). Nomes s'aplica com
#: a SEGONA passada, quan la comparacio literal ja ha fallat: aixi «Carrer Nou» (carrer nou)
#: casa primer amb `NOU` literal i no es converteix en un 9 sense necessitat.
_NUMERAL_PHRASES: dict[str, str] = {
    # catala
    "U": "1", "UN": "1", "PRIMER": "1", "PRIMERA": "1",
    "DOS": "2", "DUES": "2", "TRES": "3", "QUATRE": "4", "CINC": "5", "SIS": "6",
    "SET": "7", "VUIT": "8", "HUIT": "8", "NOU": "9", "DEU": "10", "ONZE": "11",
    "DOTZE": "12", "TRETZE": "13", "CATORZE": "14", "QUINZE": "15", "SETZE": "16",
    "DISSET": "17", "DIVUIT": "18", "DINOU": "19", "VINT": "20", "TRENTA": "30",
    "VINT I U": "21", "VINT I UN": "21", "VINT I DOS": "22", "VINT I TRES": "23",
    "VINT I QUATRE": "24", "VINT I CINC": "25", "VINT I SIS": "26", "VINT I SET": "27",
    "VINT I VUIT": "28", "VINT I NOU": "29", "TRENTA I U": "31", "TRENTA U": "31",
    # castella
    "UNO": "1", "PRIMERO": "1", "CUATRO": "4", "CINCO": "5", "SEIS": "6", "SIETE": "7",
    "OCHO": "8", "NUEVE": "9", "DIEZ": "10", "ONCE": "11", "DOCE": "12", "TRECE": "13",
    "CATORCE": "14", "QUINCE": "15", "DIECISEIS": "16", "DIECISIETE": "17",
    "DIECIOCHO": "18", "DIECINUEVE": "19", "VEINTE": "20", "VEINTIUNO": "21",
    "VEINTIDOS": "22", "VEINTITRES": "23", "VEINTICUATRO": "24", "VEINTICINCO": "25",
    "VEINTISEIS": "26", "VEINTISIETE": "27", "VEINTIOCHO": "28", "VEINTINUEVE": "29",
    "TREINTA": "30", "TREINTA Y UNO": "31",
}
_NUMERAL_MAX_WORDS = max(len(p.split()) for p in _NUMERAL_PHRASES)


def _numeral_canon(tokens: list[str]) -> list[str]:
    """`["ONZE","SETEMBRE"]` i `["11","SETEMBRE"]` -> tots dos `["11","SETEMBRE"]`.

    Consumeix per l'esquerra i prova primer les frases mes llargues, perque
    `"VINT I CINC"` (25) no es llegeixi com a `20, 1, 5`.
    """
    out: list[str] = []
    i = 0
    while i < len(tokens):
        for size in range(min(_NUMERAL_MAX_WORDS, len(tokens) - i), 0, -1):
            phrase = " ".join(tokens[i : i + size])
            if phrase in _NUMERAL_PHRASES:
                out.append(_NUMERAL_PHRASES[phrase])
                i += size
                break
        else:
            out.append(tokens[i])
            i += 1
    return out


def _cached_street_list(province: str, municipality_official: str) -> list[tuple[str, str, str]]:
    """Llista SENCERA de carrers del municipi (`ConsultaVia` amb `NombreVia` buit), cacheada.

    Una crida, <= 1 s (mesurat: Bell-lloc 112 carrers 0,5 s; Rubi 835 carrers 0,8 s). Sense
    llindar de mida: aquest es justament el problema que la funcio existeix per resoldre.
    """
    cached = _cache_load("vies", province, municipality_official)
    if cached is not None:
        return [(str(n), str(t), str(c)) for n, t, c in cached]
    streets = _consulta_via_all_streets(province, municipality_official)
    if streets:  # una llista buida es un error transitori, no un municipi sense carrers
        _cache_save("vies", province, municipality_official, data=[list(s) for s in streets])
    return streets


def _tokens_cover(hint_tokens: list[str], official_tokens: list[str]) -> bool:
    """Mateixa semantica de `_via_name_matches` sense la part difusa: totes les paraules del
    llegit son a l'oficial i, si el llegit es d'UNA sola paraula, l'oficial no en te cap de
    significativa de mes (`"Major"` no pot casar amb `"MAJOR DE BALAFIA"`).

    Un token de NOMBRE sempre compta com a significatiu, encara que sigui curt: despres de
    `_numeral_canon`, `"ONZE DE SETEMBRE"` es `["11","SETEMBRE"]`, i sense aquesta excepcio el
    `"11"` passava per abreviatura del Callejero -> el hint `"Setembre"` casava amb el carrer
    `"Onze de Setembre"`. Mesurat: era el fals positiu que introduia la capa de nombres.
    """
    if not hint_tokens or not official_tokens:
        return False
    if not set(hint_tokens).issubset(set(official_tokens)):
        return False
    if len(set(hint_tokens)) > 1:
        return True
    extra = {
        t for t in official_tokens
        if t not in set(hint_tokens) and (t.isdigit() or len(t) > _VIA_ABBREV_MAX_LEN)
    }
    return not extra


def _unique(matches: list[tuple[str, str, str]], hint: str, layer: str) -> tuple[str, str, str] | None:
    """Un sol candidat -> aquell. Cap o empat -> None (mai triar-ne un a l'atzar)."""
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        logger.warning(
            f"cadastre_reader: '{hint}' casa amb {len(matches)} carrers a la capa {layer} "
            f"({', '.join(m[0] for m in matches[:4])}): millor blanc que triar-ne un"
        )
    return None


def resolve_via(
    province: str, municipality_official: str, street_hint: str,
) -> tuple[str, str, str] | None:
    """Tria el carrer oficial d'entre els REALS del municipi. `(nom, tipus_via, cv)` o `None`.

    Mateixa forma de retorn que `geocode_coordinates._consulta_via`, pero sobre un conjunt
    tancat i sense llindar de mida. Capes, en ordre, i sempre exigint un sol guanyador:

      1. literal: mateixes paraules significatives (ordre i articles no compten);
      2. literal: les del llegit son totes a l'oficial (regla d'una sola paraula, `_tokens_cover`);
      3. igual que 1 i 2 amb els nombres canonicalitzats (`ONZE` == `11`);
      4. difusa >= 0,85 (variants ortografiques: GIRASSOLS/GIRASOLS), i NOMES si cap altre
         carrer del municipi arriba tambe al llindar.

    El nom retornat surt SEMPRE de la llista: un carrer que no existeixi al municipi no pot
    sortir d'aqui per construccio.
    """
    streets = _cached_street_list(province, municipality_official)
    if not streets:
        return None

    hint_plain = _via_tokens(street_hint)
    if not hint_plain:
        return None
    tokens = {name: _via_tokens(name) for name, _tv, _cv in streets}

    for keyed in (lambda t: t, _numeral_canon):
        hint_key = keyed(hint_plain)
        exact = [s for s in streets if keyed(tokens[s[0]]) == hint_key]
        if exact:
            return _unique(exact, street_hint, "literal" if keyed is not _numeral_canon else "nombres")
        cover = [s for s in streets if _tokens_cover(hint_key, keyed(tokens[s[0]]))]
        if cover:
            return _unique(cover, street_hint, "conte" if keyed is not _numeral_canon else "conte+nombres")

    hint_joined = " ".join(hint_plain)
    scored = sorted(
        ((difflib.SequenceMatcher(None, hint_joined, " ".join(tokens[s[0]])).ratio(), s) for s in streets),
        key=lambda pair: pair[0],
        reverse=True,
    )
    best_ratio, best = scored[0]
    if best_ratio < _VIA_FUZZY_CUTOFF:
        return None
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    if runner_up >= _VIA_FUZZY_CUTOFF:
        # Dos carrers s'assemblen prou al llegit: no es tria, es deixa en blanc. Cas real de
        # Bell-lloc: "Telegraf" dona TELEGRAFS (0,94) i TELEGRAFOS (0,89), les dues grafies
        # del mateix carrer amb `cv` diferent. Un marge numeric aqui seria arbitrari; que cap
        # segon arribi al llindar es una regla explicable.
        logger.warning(
            f"cadastre_reader: '{street_hint}' empata a la capa difusa "
            f"({best[0]} {best_ratio:.2f} vs {scored[1][1][0]} {runner_up:.2f}): blanc"
        )
        return None
    logger.info(f"cadastre_reader: '{street_hint}' -> '{best[0]}' (difusa {best_ratio:.2f}, llista del municipi)")
    return best


def _dir_block(container: dict) -> dict:
    lourb = (((container.get("dt") or {}).get("locs") or {}).get("lous") or {}).get("lourb") or {}
    return lourb.get("dir") or {}


def _hit_from(rc_block: dict | None, dir_block: dict) -> ParcelHit | None:
    pc1 = str((rc_block or {}).get("pc1") or "").strip()
    pc2 = str((rc_block or {}).get("pc2") or "").strip()
    if not pc1:
        return None
    pnp = str(dir_block.get("pnp") or "").strip()
    plp = str(dir_block.get("plp") or "").strip().upper()
    return ParcelHit(rc=pc1 + pc2, pnp=pnp, plp=plp)


def _extract_hits(data: dict) -> list[ParcelHit]:
    """Dues formes de resposta observades (2026-08-31): `lrcdnp.rcdnp[]` quan hi ha mes
    d'un portal amb el mateix numero (lletres), `bico.bi` quan nomes n'hi ha un."""
    result = (data or {}).get("consulta_dnplocResult") or {}
    if result.get("lerr"):
        return []
    hits: list[ParcelHit] = []
    lrcdnp = result.get("lrcdnp")
    if lrcdnp:
        rcdnp = lrcdnp.get("rcdnp") or []
        if isinstance(rcdnp, dict):
            rcdnp = [rcdnp]
        for entry in rcdnp:
            hit = _hit_from(entry.get("rc"), _dir_block(entry))
            if hit:
                hits.append(hit)
        return hits
    bico = result.get("bico")
    if bico:
        bi = bico.get("bi") or {}
        hit = _hit_from((bi.get("idbi") or {}).get("rc"), _dir_block(bi))
        if hit:
            hits.append(hit)
    return hits


def resolve_portal(
    province: str, municipality_official: str, via_official: str, number: str, letter: str, *, tipo_via: str = "CL",
) -> list[ParcelHit]:
    """RC per a un portal EXACTE (`(pnp, plp)`). Mai delega en el mes proper (a diferencia de
    `geocode_coordinates._pick_nearest_rc_from_numerero`, usat per la via B): amb lletra buida
    i nomes entrades amb lletra a la resposta, marca `ambiguous=True` en comptes de triar-ne una."""
    parts = (province, municipality_official, via_official, number)
    data = _cache_load("dnploc", *parts)
    if data is None:
        url = (
            f"{_DNPLOC_URL}?Provincia={urllib.parse.quote(province)}"
            f"&Municipio={urllib.parse.quote(municipality_official)}"
            f"&Sigla={urllib.parse.quote(tipo_via)}&Calle={urllib.parse.quote(via_official)}"
            f"&Numero={urllib.parse.quote(number)}"
        )
        try:
            data = json.loads(_fetch(url))
        except Exception as e:
            logger.warning(f"cadastre_reader: DNPLOC failed for {via_official} {number}: {e}")
            return []
        _cache_save("dnploc", *parts, data=data)

    all_hits = _extract_hits(data)
    num_digits = re.sub(r"[A-Za-z]+$", "", number.strip())
    same_number = [h for h in all_hits if h.pnp in (num_digits, number.strip())]
    letter_norm = (letter or "").strip().upper()
    if letter_norm:
        return [h for h in same_number if h.plp == letter_norm]
    no_letter = [h for h in same_number if not h.plp]
    if no_letter:
        return no_letter
    if same_number:
        return [ParcelHit(rc=h.rc, pnp=h.pnp, plp=h.plp, ambiguous=True) for h in same_number]
    return []


# ---------------------------------------------------------------------------
# `parcel_area_and_polygon` — WFS INSPIRE (XML)
# ---------------------------------------------------------------------------


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _parse_wfs(text: str) -> tuple[int, list[tuple[float, float]]] | None:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    if _strip_ns(root.tag) == "ExceptionReport":
        return None
    area_el = next((el for el in root.iter() if _strip_ns(el.tag) == "areaValue"), None)
    pos_el = next((el for el in root.iter() if _strip_ns(el.tag) == "posList"), None)
    if area_el is None or not (area_el.text or "").strip() or pos_el is None or not (pos_el.text or "").strip():
        return None
    try:
        area = int(round(float(area_el.text.strip())))
    except ValueError:
        return None
    values = pos_el.text.strip().split()
    if len(values) < 6 or len(values) % 2 != 0:
        return None
    polygon: list[tuple[float, float]] = []
    for i in range(0, len(values), 2):
        try:
            x, y = float(values[i]), float(values[i + 1])
        except ValueError:
            return None
        if x > 1_000_000 and y < 1_000_000:  # INSPIRE WFS 2.0 pot tornar (northing, easting)
            x, y = y, x
        polygon.append((x, y))
    return area, polygon


def parcel_area_and_polygon(rc14: str) -> tuple[int, list[tuple[float, float]]] | None:
    """Area oficial (`cp:areaValue`, enter) + poligon UTM (EPSG:25831) per a un RC de 14 caracters.

    L'area es SEMPRE l'oficial del WFS, mai `shapely`: la mesurada (441+423+420 = 1284 exacte)
    difereix de la calculada per `shapely.Polygon.area` (440,75... arrodoneix malament)."""
    cached = _cache_load("wfs", rc14)
    if cached is not None:
        polygon = cached.get("polygon")
        area = cached.get("area_m2")
        if isinstance(area, int) and isinstance(polygon, list):
            return area, [tuple(p) for p in polygon]

    url = f"{_WFS_URL}?service=wfs&version=2.0.0&request=GetFeature&STOREDQUERIE_ID=GetParcel&refcat={rc14}&srsname=EPSG::25831"
    try:
        text = _fetch(url)
    except Exception as e:
        logger.warning(f"cadastre_reader: WFS failed for {rc14}: {e}")
        return None
    parsed = _parse_wfs(text)
    if parsed is None:
        return None
    area, polygon = parsed
    _cache_save("wfs", rc14, data={"area_m2": area, "polygon": [list(p) for p in polygon]})
    return area, polygon


# ---------------------------------------------------------------------------
# `cadastre_portal_signals` — cablejat a `consolidate.py`
# ---------------------------------------------------------------------------


#: Deriva tolerada entre un punt de camp i el limit de la parcel·la abans de considerar que la
#: parcel·la no es la del projecte. El GPS de camp mostra ~0,6 m de diferencia contra l'ICGC
#: (memoria `cota_referencia`), i el limit cadastral tampoc no es exacte; 10 m dona marge de
#: sobra a totes dues coses i queda molt per sota de la distancia a una parcel·la equivocada
#: (una de veina d'uns 441 m2 ja es a ~20 m). Es un criteri de judici: revisar-lo amb dades
#: reals quan n'hi hagi de mes projectes.
_MAX_POINT_DRIFT_M = 10.0


@dataclass(frozen=True)
class PointsCheck:
    """Quants punts d'assaig (`COORDENADES*.txt`) cauen dins de la unio de parcel·les."""

    inside: int
    total: int
    farthest_m: float

    @property
    def vetoes(self) -> bool:
        """CAP punt dins i el mes proper clarament fora: no es la parcel·la del projecte.

        Amb algun punt dins no es veta —la parcel·la es com a minim en part correcta i un punt
        solt fora sol ser deriva de GPS o un assaig al carrer—, pero l'avis hi queda igualment.
        """
        return self.total > 0 and self.inside == 0 and self.farthest_m > _MAX_POINT_DRIFT_M

    @property
    def note(self) -> str:
        if self.inside == self.total:
            return f"{self.inside}/{self.total} punts d'assaig dins de la unio"
        return (f"{self.inside}/{self.total} punts d'assaig dins de la unio "
                f"({self.total - self.inside} fora, fins a {self.farthest_m:.0f} m)")


def _points_check(project_path: Path | None, geom: Any) -> PointsCheck | None:
    """`None` si no hi ha projecte, geometria o cap punt: llavors la comprovacio calla."""
    if project_path is None or geom is None:
        return None
    from shapely.geometry import Point

    from automation.lectura.consolidate import parse_coordenades

    total = 0
    inside = 0
    farthest = 0.0
    try:
        coord_files = sorted(Path(project_path).rglob("COORDENADES*.txt"))
    except OSError:
        return None
    for coord_file in coord_files:
        try:
            points = parse_coordenades(coord_file.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for p in points:
            try:
                x = float(str(p["x"]).replace(",", "."))
                y = float(str(p["y"]).replace(",", "."))
            except (KeyError, ValueError):
                continue
            total += 1
            pt = Point(x, y)
            if geom.contains(pt) or geom.touches(pt):
                inside += 1
            else:
                farthest = max(farthest, pt.distance(geom))
    if total == 0:
        return None
    return PointsCheck(inside=inside, total=total, farthest_m=farthest)


def _veto_signal(key: str, check: PointsCheck, portals_desc: str) -> list["Any"]:
    """Senyal amb valor BUIT i el motiu escrit per a l'Eva.

    `decide()` recull el `note` dels senyals sense valor a la cel·la `no_trobat` (vegeu
    `consolidate.decide`), i el popup del wizard el pinta. Aixi el camp queda en blanc —mai un
    numero d'una altra parcel·la— pero l'Eva sap per que.

    El text diu explicitament que la sospita ve de les COORDENADES perque l'Eva ja ha dit que
    no considera les UTM del tot fiables: si el veto li amaga un valor i no sap d'on ve, la
    conclusio que en traura sera sobre el sistema, no sobre les coordenades.
    """
    from automation.lectura.consolidate import _HTTP_CONF, _HTTP_DOC, Signal

    quin = "la superfície" if key == "superficie_parcela" else "la referència cadastral"
    note = (
        f"No s'ha omplert {quin}: els punts d'assaig del projecte cauen FORA de la parcel·la "
        f"que correspon a l'adreça llegida (portals {portals_desc}; {check.inside}/{check.total} "
        f"dins, el més llunyà a {check.farthest_m:.0f} m). Comprova l'adreça del projecte o les "
        f"coordenades de ANNEXES/…/COORDENADES.txt."
    )
    return [Signal(key, None, "(Cadastre: descartat pels punts d'assaig)", "", _HTTP_CONF,
                   _HTTP_DOC, "consulta_http", "python", note)]


def _build_signals(
    key: str,
    entries: list[tuple[str, str, bool]],
    parcels: dict[str, tuple[int, list[tuple[float, float]]]],
    contiguous: bool,
    ambiguous_any: bool,
    points_note: str | None,
) -> list["Any"]:
    from automation.lectura.consolidate import _HTTP_CONF, _HTTP_DOC, _HTTP_NOTES, Signal

    base_note = _HTTP_NOTES.get("cadastre", "")
    portals_desc = "+".join(label for _rc, label, _amb in entries)
    rcs_desc = "+".join(rc for rc, _l, _a in entries)

    if key == "referencia_catastral":
        note = "; ".join(p for p in (base_note, points_note) if p) or None
        font = f"(Cadastre: {portals_desc} = {rcs_desc})"
        return [Signal("referencia_catastral", rcs_desc, font, "", _HTTP_CONF, _HTTP_DOC, "consulta_http", "python", note)]

    # superficie_parcela
    if contiguous:
        total_area = sum(parcels[rc][0] for rc, _l, _a in entries)
        areas_desc = "+".join(str(parcels[rc][0]) for rc, _l, _a in entries)
        contig_note = f"{len(entries)}/{len(entries)} parcel·les contigues" if len(entries) > 1 else None
        note = "; ".join(p for p in (base_note, contig_note, points_note) if p) or None
        font = f"(Cadastre: {portals_desc} = {rcs_desc}, {areas_desc} m²)"
        return [Signal("superficie_parcela", str(total_area), font, "", _HTTP_CONF, _HTTP_DOC, "consulta_http", "python", note)]

    sigs = []
    for rc, label, amb in entries:
        area = parcels[rc][0]
        why = "portal ambigu" if amb else "parcel·les no contigues"
        font = f"(Cadastre: portal {label} = {rc}, {area} m²; {why})"
        note = "; ".join(p for p in (base_note, why, points_note) if p) or None
        sigs.append(Signal("superficie_parcela", str(area), font, "", _HTTP_CONF, _HTTP_DOC, "consulta_http", "python", note))
    return sigs


def cadastre_portal_signals(
    key: str, decided: dict[str, dict], project_path: Path | None, extra_concepts: dict | None = None,
) -> list["Any"]:
    """Senyals `superficie_parcela`/`referencia_catastral` a partir dels portals de l'adreça
    LLEGIDA (`decided["street_address"]`), no de la via B. Mai `segur` (conf 0,5 < CONV_CONF).

    `extra_concepts` (opcional) porta el `street_address_struct` que hagi emes el skill: nomes
    s'hi busquen GRAFIES ALTERNATIVES de via i municipi per reintentar. Sense ell tot funciona
    com abans amb el text lliure.

    Qualsevol excepcio -> `[]`: la consolidacio mai no pot fallar per aquest lector."""
    if key not in ("referencia_catastral", "superficie_parcela"):
        return []
    if project_path is None:  # mateix contracte que `http_field_signals`: sense projecte, cap crida.
        return []
    try:
        return _cadastre_portal_signals_impl(key, decided, project_path, extra_concepts)
    except Exception as e:
        logger.warning(f"cadastre_reader: unexpected failure for {key}: {e}")
        return []


def _dedup_hints(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = " ".join(str(v).split()).casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(" ".join(str(v).split()))
    return out


def _resolve_municipality(hints: list[str]) -> tuple[str, str] | None:
    """`(provincia, nom oficial del Cadastre)` provant les grafies en ordre.

    Padro local per a totes (determinista, cost 0) i, nomes si cap no hi es, el bucle en linia
    —fora de Catalunya (Anciles es de Benasc, Osca, confirmat pel Josep 2026-09-01) o noms que
    el padro no pot decidir."""
    for hint in hints:
        padro = municipis.lookup(hint)
        if padro is not None:
            return padro.province_cadastre, padro.name_cadastre
    for hint in hints:
        for province in [*list(_CATALAN_PROVINCES), "HUESCA"]:
            muni_result = _cached_consulta_municipio(province, hint)
            if muni_result:
                return province, muni_result[0]
    return None


def _resolve_street(
    province: str, official_muni: str, street_name: str, address: str, alternatives: list[str],
) -> tuple[str, str, str] | None:
    """Via B (barata, exacta) -> conjunt tancat -> conjunt tancat amb les grafies alternatives.

    Les alternatives NOMES son intents de consulta: el nom que s'accepta surt sempre de la
    llista real del municipi (`resolve_via`), mai del model."""
    via_result = _cached_consulta_via(province, official_muni, street_name, full_address_context=address)
    if via_result is not None and _via_name_matches(street_name, via_result[0]):
        return via_result
    if via_result is not None:
        logger.info(
            f"cadastre_reader: '{via_result[0]}' no correspon a '{street_name}' ({official_muni}); "
            f"provant amb la llista sencera del municipi"
        )
    for hint in [street_name, *alternatives]:
        found = resolve_via(province, official_muni, hint)
        if found is not None:
            if hint != street_name:
                logger.info(f"cadastre_reader: '{street_name}' resolt per la grafia alternativa '{hint}' -> '{found[0]}'")
            return found
    return None


def _cadastre_portal_signals_impl(
    key: str, decided: dict[str, dict], project_path: Path | None, extra_concepts: dict | None = None,
) -> list["Any"]:
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.ops import unary_union

    addr_cell = decided.get("street_address") or {}
    muni_cell = decided.get("municipality") or {}
    if addr_cell.get("estat") not in ("segur", "candidats") or muni_cell.get("estat") not in ("segur", "candidats"):
        return []
    address = addr_cell.get("value")
    municipality_hint = muni_cell.get("value")
    if not address or not municipality_hint:
        return []

    # Si street_address te diversos candidats, `value` ja es `candidates[0]` (l'overlay
    # escriu el primer): no cal triar-lo aqui.
    street_name, portal_specs = portals_from_address(str(address))
    if not portal_specs:
        return []
    portal_specs = portal_specs[:_MAX_PORTALS]

    # Grafies alternatives que hagi emes el skill (nomes eix via/municipi; els portals segueixen
    # sortint de `portals_from_address`, vegeu `address_struct`).
    struct, struct_problems = address_struct.from_extra_concepts(extra_concepts)
    for problem in struct_problems:
        logger.info(f"cadastre_reader: {problem}")

    muni_hints = [str(municipality_hint)]
    via_alternatives: list[str] = []
    if struct is not None:
        muni_hints = _dedup_hints([str(municipality_hint), *struct.municipi_hints()])
        via_alternatives = [h for h in struct.via_hints() if h.casefold() != street_name.casefold()]

    resolved_muni = _resolve_municipality(muni_hints)
    if resolved_muni is None:
        return []
    effective_province, official_muni = resolved_muni

    via_result = _resolve_street(effective_province, official_muni, street_name, str(address), via_alternatives)
    if via_result is None:
        logger.warning(
            f"cadastre_reader: cap carrer del Callejero correspon a '{street_name}' "
            f"({official_muni}): millor cap parcel·la que la d'un altre carrer"
        )
        return []
    official_street, tipo_via, _cv = via_result

    entries: list[tuple[str, str, bool]] = []  # (rc, portal_label, ambiguous)
    seen_rcs: set[str] = set()
    for number, letter in portal_specs:
        for hit in resolve_portal(effective_province, official_muni, official_street, number, letter, tipo_via=tipo_via):
            if hit.rc in seen_rcs:
                continue
            seen_rcs.add(hit.rc)
            label = f"{hit.pnp}{hit.plp}" if hit.plp else hit.pnp
            entries.append((hit.rc, label, hit.ambiguous))
    if not entries:
        return []

    parcels: dict[str, tuple[int, list[tuple[float, float]]]] = {}
    for rc, _label, _amb in entries:
        result = parcel_area_and_polygon(rc)
        if result is not None:
            parcels[rc] = result
    entries = [e for e in entries if e[0] in parcels]
    if not entries:
        return []

    ambiguous_any = any(amb for _rc, _label, amb in entries)
    contiguous = False
    merged_geom = None
    if not ambiguous_any:
        if len(entries) == 1:
            contiguous = True
            poly = parcels[entries[0][0]][1]
            if len(poly) >= 3:
                merged_geom = ShapelyPolygon(poly)
        else:
            polys = [ShapelyPolygon(parcels[rc][1]) for rc, _l, _a in entries if len(parcels[rc][1]) >= 3]
            if len(polys) == len(entries):
                try:
                    candidate = unary_union(polys)
                    if candidate.geom_type == "Polygon":
                        contiguous = True
                        merged_geom = candidate
                except Exception:
                    contiguous = False

    # Veto pels punts de camp: es comprova SEMPRE sobre la unio de totes les parcel·les
    # resoltes (encara que no siguin contigues o hi hagi un portal ambigu), perque la pregunta
    # «son aquestes les parcel·les del projecte?» no depen de si es poden sumar.
    check_polys = [ShapelyPolygon(parcels[rc][1]) for rc, _l, _a in entries if len(parcels[rc][1]) >= 3]
    check_geom = None
    if check_polys:
        try:
            check_geom = unary_union(check_polys)
        except Exception:
            check_geom = None
    check = _points_check(project_path, check_geom)
    if check is not None and check.vetoes:
        portals_desc = "+".join(label for _rc, label, _amb in entries)
        logger.warning(
            f"cadastre_reader: {key} descartat, {check.inside}/{check.total} punts d'assaig dins de "
            f"les parcel·les {portals_desc} (el mes llunya a {check.farthest_m:.0f} m)"
        )
        return _veto_signal(key, check, portals_desc)

    points_note = check.note if (contiguous and check is not None) else None

    return _build_signals(key, entries, parcels, contiguous, ambiguous_any, points_note)
