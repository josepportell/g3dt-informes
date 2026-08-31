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

from automation import config
from automation.geocode_coordinates import _CATALAN_PROVINCES, _consulta_municipio, _consulta_via

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
_PORTAL_TOKEN_RE = re.compile(r"(\d+)\s*([A-Za-z])?")

_STREET_PREFIX_RE = re.compile(
    r"^\s*(?:c\.?/|carrer|calle|avinguda|avenida|av\.?|pla[cç]a|plaza|pl\.?|passeig|paseo|pg\.?|"
    r"carretera|ctra\.?|cam[ií]|camino|rambla|travessia|travesía)"
    r"\s*(?:de\s+la\s+|de\s+les\s+|de\s+los\s+|dels\s+|del\s+|de\s+|d')?",
    re.IGNORECASE,
)


def _strip_street_prefix(s: str) -> str:
    stripped = _STREET_PREFIX_RE.sub("", s, count=1).strip()
    return stripped or s.strip()


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

    m_num = re.search(r"\d", addr)
    if not m_num:
        return _strip_street_prefix(addr), []

    street_part = addr[: m_num.start()].strip(" ,")
    numbers_part = addr[m_num.start() :].strip(" ,")
    street = _strip_street_prefix(street_part)

    range_m = _RANGE_RE.match(numbers_part)
    if range_m:
        return street, [(range_m.group(1), ""), (range_m.group(2), "")]

    portals: list[tuple[str, str]] = []
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


def _points_note(project_path: Path | None, geom: Any) -> str | None:
    """Quants punts d'assaig (`COORDENADES*.txt`) cauen dins de la unio de parcel·les.
    Nomes informatiu: mai bloqueja la suma."""
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
    if inside == total:
        return f"{inside}/{total} punts d'assaig dins de la unio"
    return f"{inside}/{total} punts d'assaig dins de la unio ({total - inside} fora, fins a {farthest:.0f} m)"


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


def cadastre_portal_signals(key: str, decided: dict[str, dict], project_path: Path | None) -> list["Any"]:
    """Senyals `superficie_parcela`/`referencia_catastral` a partir dels portals de l'adreça
    LLEGIDA (`decided["street_address"]`), no de la via B. Mai `segur` (conf 0,5 < CONV_CONF).
    Qualsevol excepcio -> `[]`: la consolidacio mai no pot fallar per aquest lector."""
    if key not in ("referencia_catastral", "superficie_parcela"):
        return []
    if project_path is None:  # mateix contracte que `http_field_signals`: sense projecte, cap crida.
        return []
    try:
        return _cadastre_portal_signals_impl(key, decided, project_path)
    except Exception as e:
        logger.warning(f"cadastre_reader: unexpected failure for {key}: {e}")
        return []


def _cadastre_portal_signals_impl(key: str, decided: dict[str, dict], project_path: Path | None) -> list["Any"]:
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

    effective_province = None
    muni_result = None
    for province in [*list(_CATALAN_PROVINCES), "HUESCA"]:
        muni_result = _cached_consulta_municipio(province, str(municipality_hint))
        if muni_result:
            effective_province = province
            break
    if muni_result is None or effective_province is None:
        return []
    official_muni, _cp, _cm = muni_result

    via_result = _cached_consulta_via(effective_province, official_muni, street_name, full_address_context=str(address))
    if via_result is None:
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

    points_note = _points_note(project_path, merged_geom) if contiguous else None

    return _build_signals(key, entries, parcels, contiguous, ambiguous_any, points_note)
