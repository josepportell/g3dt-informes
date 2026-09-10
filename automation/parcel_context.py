"""Context de la parcel·la del projecte per a la narrativa dels adjacents (peça 2, 2026-09-06 nit).

`docs/ANALISI-NARRATIVA-2026-09-06.md` §3.1: la parcel·la que es sondeja per als adjacents ha de ser la del PROJECTE
(la que la lectura resol pel portal: `referencia_catastral`, 6/7 projectes, Castellar = 3 portals), no la del punt de
màquina (Bell-lloc: l'UTM de COORDENADES resol «CL VIA FERREA 57»). Aquí hi ha les peces pures o cachejades:

- `parse_rc_list`: «3298012DG2039N+3298013DG2039N» / «4613173CG1141S0001ZU» → ['3298012DG2039N', …] (14 caràcters);
  «Polígon 6, Parcel·la 105-B» (rústica, Rubí) → [].
- `union_polygon` / `centroid`: polígon unió dels portals (Shapely) i el seu centroide (UTM 25831).
- `shape_word`: «rectangular» / «quasi rectangular» / «irregular» per la relació àrea / rectangle mínim (Eva: «pren una
  morfologia rectangular», «quasi rectangular», «bastant rectangular»).
- `municipality_centre_utm` (Nominatim, cache 90 dies) + `position_in_municipality`: «al nord / al sud-oest / al centre»
  del municipi (rosa de 8 vents des del centre del municipi; Eva: «es situa al nord del municipi de Castellar del Vallès»).
- `adjacent_intro`: «La parcel·la objecte d'estudi es situa al {posició} del municipi de {Municipi}, pren una morfologia
  {forma} i limita:» (7/7 signats; ES «La parcela objeto de estudio se sitúa en el norte del municipio de Anciles, tiene
  una morfología rectangular y limita:»).
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_RC14_RE = re.compile(r"\b(\d{7}[A-Z]{2}\d{4}[A-Z])(?:\d{4}[A-Z]{2})?\b")
_DIRS_CA = ["nord", "nord-est", "est", "sud-est", "sud", "sud-oest", "oest", "nord-oest"]
_DIRS_ES = ["norte", "noreste", "este", "sureste", "sur", "suroeste", "oeste", "noroeste"]
CENTRE_RADIUS_M = 150.0
CACHE_TTL_DAYS = 90


def parse_rc_list(value) -> list[str]:
    """Referències cadastrals de 14 caràcters d'un text («rc+rc», rc de 20) o d'una llista; sense duplicats, en ordre."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else re.split(r"[+;,\s]+", str(value))
    out: list[str] = []
    for it in items:
        for m in _RC14_RE.finditer(str(it).strip().upper()):
            rc = m.group(1)
            if rc not in out:
                out.append(rc)
    return out


def union_polygon(polygons: list[list[tuple[float, float]]]) -> list[tuple[float, float]]:
    """Contorn exterior de la unió (Shapely). Un sol polígon → tal qual; unió no contigua → el més gran."""
    polys = [p for p in polygons if p and len(p) >= 3]
    if not polys:
        return []
    if len(polys) == 1:
        return list(polys[0])
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        geom = unary_union([Polygon(p) for p in polys])
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda g: g.area)
        return [(float(x), float(y)) for x, y in geom.exterior.coords]
    except Exception as exc:  # shapely absent o geometria invàlida
        logger.warning("union_polygon: %s; es fa servir el primer polígon", exc)
        return list(polys[0])


def centroid(polygon: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not polygon:
        return None
    try:
        from shapely.geometry import Polygon
        c = Polygon(polygon).centroid
        return float(c.x), float(c.y)
    except Exception:
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        return sum(xs) / len(xs), sum(ys) / len(ys)


def shape_word(polygon: list[tuple[float, float]] | None, lang: str = "ca") -> str:
    """Relació àrea / rectangle mínim girat: ≥ 0,92 rectangular; ≥ 0,78 quasi rectangular; si no irregular."""
    default = "rectangular"
    if not polygon or len(polygon) < 3:
        return default
    try:
        from shapely.geometry import Polygon
        poly = Polygon(polygon)
        if poly.area <= 0:
            return default
        ratio = poly.area / poly.minimum_rotated_rectangle.area
    except Exception:
        return default
    if ratio >= 0.92:
        return "rectangular"
    if ratio >= 0.78:
        return "casi rectangular" if lang == "es" else "quasi rectangular"
    return "irregular"


def _cache_dir() -> Path:
    from . import config
    return config.cache_dir("municipi_centre")


def municipality_centre_utm(municipality: str | None, province: str = "") -> tuple[float, float] | None:
    """Centre del municipi (Nominatim, UTM 31N) amb cache de 90 dies; None si no es pot."""
    name = re.sub(r"\s*\(.*?\)\s*$", "", (municipality or "").strip())
    if not name:
        return None
    key = hashlib.sha256(f"{name.lower()}|{province.lower()}".encode()).hexdigest()[:12]
    cache = _cache_dir() / f"{key}.json"
    try:
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
            if datetime.now() - datetime.fromisoformat(data["cached_at"]) < timedelta(days=CACHE_TTL_DAYS):
                return (data["utm_x"], data["utm_y"]) if data.get("utm_x") is not None else None
    except Exception:
        pass
    try:
        from .geocode_coordinates import _wgs84_to_utm31n, nominatim_geocode
        latlon = nominatim_geocode(name, name, province)
        utm = _wgs84_to_utm31n(*latlon) if latlon else None
    except Exception as exc:
        logger.warning("municipality_centre_utm(%s): %s", name, exc)
        utm = None
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"cached_at": datetime.now().isoformat(), "municipality": name,
                                     "utm_x": utm[0] if utm else None, "utm_y": utm[1] if utm else None}),
                         encoding="utf-8")
    except Exception:
        pass
    return utm


def position_in_municipality(parcel_xy: tuple[float, float] | None, centre_xy: tuple[float, float] | None,
                             lang: str = "ca") -> str | None:
    """«nord», «sud-oest», … des del centre del municipi; «centre» si és a menys de 150 m; None sense dades."""
    if not parcel_xy or not centre_xy:
        return None
    dx, dy = parcel_xy[0] - centre_xy[0], parcel_xy[1] - centre_xy[1]
    if math.hypot(dx, dy) < CENTRE_RADIUS_M:
        return "centro" if lang == "es" else "centre"
    bearing = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0     # 0 = nord, 90 = est
    idx = int(((bearing + 22.5) % 360.0) // 45.0)
    return (_DIRS_ES if lang == "es" else _DIRS_CA)[idx]


def adjacent_intro(position: str | None, municipality_proper: str, shape: str = "rectangular", lang: str = "ca") -> str:
    """Frase d'introducció dels adjacents (2.1.1). Sense posició coneguda, la frase no en diu cap."""
    if lang == "es":
        pos = f"en el {position} del municipio" if position and position != "centro" else (
            "en el centro del municipio" if position == "centro" else "en el municipio")
        return f"La parcela objeto de estudio se sitúa {pos} de {municipality_proper}, tiene una morfología {shape} y limita:"
    if position == "centre":
        pos = "al centre del municipi"
    elif position:
        pos = f"al {position} del municipi"
    else:
        pos = "al municipi"
    return f"La parcel·la objecte d'estudi es situa {pos} de {municipality_proper}, pren una morfologia {shape} i limita:"


def _dnprc_cache_dir() -> Path:
    from . import config
    return config.cache_dir("dnprc")


def own_parcel_buildings(rc_list: list[str] | None) -> dict | None:
    """Construccions de la PARCEL·LA DEL PROJECTE (Cadastre DNPRC per referència, cache 90 dies; peça 3, 2026-09-07):
    {'has_building', 'num_floors_above', 'num_floors_below', 'has_pool', 'total_built_m2', 'refs'} agregat sobre les
    referències (màxim de plantes, qualsevol edifici). None si no hi ha referències o cap consulta ha respost
    («sense font», no «sense edifici»). És l'entrada de `narrative_criteria.site_description_sentence` (Alcoletge:
    «El solar està actualment ocupat per … un edifici en planta baixa»)."""
    rcs = parse_rc_list(rc_list)
    if not rcs:
        return None
    from .cadastre_adjacents import _query_building_data
    agg = {"has_building": False, "num_floors_above": 0, "num_floors_below": 0, "has_pool": False,
           "total_built_m2": 0.0, "refs": []}
    answered = False
    for rc in rcs:
        data = None
        cache = _dnprc_cache_dir() / f"{rc}.json"
        try:
            if cache.exists():
                raw = json.loads(cache.read_text(encoding="utf-8"))
                if datetime.now() - datetime.fromisoformat(raw["cached_at"]) < timedelta(days=CACHE_TTL_DAYS):
                    data = raw["data"]
        except Exception:
            data = None
        if data is None:
            try:
                data = _query_building_data(rc)
            except Exception as e:  # xarxa: sense font
                logger.debug("DNPRC %s: %s", rc, e)
                data = None
            if data is not None:
                try:
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_text(json.dumps({"cached_at": datetime.now().isoformat(), "rc": rc, "data": data}),
                                     encoding="utf-8")
                except Exception:
                    pass
        if data is None:
            continue
        answered = True
        agg["refs"].append(rc)
        agg["has_building"] = agg["has_building"] or bool(data.get("has_building"))
        agg["num_floors_above"] = max(agg["num_floors_above"], int(data.get("num_floors_above") or 0))
        agg["num_floors_below"] = max(agg["num_floors_below"], int(data.get("num_floors_below") or 0))
        agg["has_pool"] = agg["has_pool"] or bool(data.get("has_pool"))
        agg["total_built_m2"] += float(data.get("total_built_m2") or 0.0)
    return agg if answered else None
