#!/usr/bin/env python3
"""
G3DT Site Text Generator

Converts structured micro-fields from ortho vision analysis into Catalan text
for the geotechnical report. Takes a SiteAnalysis (from ortho_vision.py) plus
existing project data and generates enriched values for adjacents, site
description, access description, and location sentence.

Usage:
    from automation.site_text_generator import generate_enriched_texts
    from automation.ortho_vision import SiteAnalysis

    texts = generate_enriched_texts(
        analysis=site_analysis,
        cadastre_adjacents={"north": "Carrer X", "south": "parcella veina", ...},
        street_address="Carrer Major 5",
        municipality="Bell-lloc d'Urgell",
        building_type="habitatge unifamiliar ailat",
    )

Author: Eficients.cat
Date: 2026-03-28
"""

from __future__ import annotations

import logging
from typing import Any

from .ortho_vision import SiteAnalysis, BoundaryAnalysis

logger = logging.getLogger(__name__)

__all__ = ["generate_enriched_texts"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FLOOR_NAMES = {
    1: "una planta",
    2: "dues plantes",
    3: "tres plantes",
    4: "quatre plantes",
    5: "cinc plantes",
}

DIRECTION_CAT = {
    "north": "nord",
    "south": "sud",
    "east": "est",
    "west": "oest",
}

DIRECTION_PREPOSITIONS = {
    "carrer": "del",
    "avinguda": "de l'",
    "placa": "de la",
    "ronda": "de la",
    "cami": "del",
    "passatge": "del",
    "passeig": "del",
    "travessia": "de la",
    "partida": "de la",
}

_ENCLOSURE_TEXT = {
    "wall": "murs",
    "fence": "tanques metàl·liques",
    "hedge": "bardissa vegetal",
    "curb": "vorada",
    "none": None,
    "uncertain": None,
}

_SURFACE_TEXT = {
    "paved": "pavimentat",
    "unpaved": "sense pavimentar",
    "gravel": "amb grava",
    "vegetation": "sense pavimentar",
    "bare_soil": "sense pavimentar",
    "mixed": "parcialment pavimentat",
}

_VEGETATION_TEXT = {
    "low_herbaceous": "vegetació de petita alçada",
    "trees_shrubs": "vegetació arbustiva",
    "dense": "vegetació densa",
    "sparse": "vegetació dispersa",
    "none": "escassa cobertura vegetal",
}

_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _floors_text(n: int | None) -> str:
    if n is None:
        return ""
    return _FLOOR_NAMES.get(n, f"{n} plantes")


def _confidence_ge(confidence: str, threshold: str) -> bool:
    return _CONFIDENCE_ORDER.get(confidence, 0) >= _CONFIDENCE_ORDER.get(threshold, 1)


# ---------------------------------------------------------------------------
# Adjacent text
# ---------------------------------------------------------------------------


def _generate_adjacent_text(ba: BoundaryAnalysis, cadastre_label: str) -> str:
    # Low confidence non-street: fall back to cadastre
    if ba.confidence == "low" and ba.adjacency_type != "street":
        return cadastre_label

    if ba.adjacency_type == "street":
        return cadastre_label

    if not ba.building_presence:
        return "parcel\u00b7la buida"

    # building_presence == True
    if ba.building_detached is True:
        floors = _floors_text(ba.estimated_visible_floors)
        if floors:
            return (
                f"parcel\u00b7la amb una construcci\u00f3 a\u00efllada "
                f"de fins a {floors} sobre rasant"
            )
        return "parcel\u00b7la amb una construcci\u00f3 a\u00efllada"

    if ba.building_detached is False:
        return "parcel\u00b7la amb edificaci\u00f3 entre mitgeres"

    # building_detached is None
    return "parcel\u00b7la amb construcci\u00f3"


# ---------------------------------------------------------------------------
# Site description
# ---------------------------------------------------------------------------


def _generate_site_description(
    analysis: SiteAnalysis,
    access_direction: str | None,
) -> str:
    sentences: list[str] = []

    # 1. Access
    if access_direction:
        dir_cat = DIRECTION_CAT.get(access_direction, access_direction)
        sentences.append(
            f"L'entrada a la zona d'estudi es realitza a trav\u00e9s "
            f"del carrer existent al {dir_cat}."
        )

    # 2. Delimitation (from boundary enclosures)
    enclosure_texts: list[str] = []
    for ba in analysis.boundary_analyses.values():
        enc = ba.enclosure_visible
        if enc and enc not in ("uncertain", "none"):
            text = _ENCLOSURE_TEXT.get(enc)
            if text and text not in enclosure_texts:
                enclosure_texts.append(text)
    if enclosure_texts:
        desc = ", ".join(enclosure_texts)
        sentences.append(f"La parcel\u00b7la es troba delimitada per {desc}.")

    # 3. Surface + vegetation
    surface_state = analysis.parcel_surface_state
    # Pick dominant vegetation from boundary analyses
    veg_counts: dict[str, int] = {}
    for ba in analysis.boundary_analyses.values():
        veg_counts[ba.vegetation_state] = veg_counts.get(ba.vegetation_state, 0) + 1
    vegetation = max(veg_counts, key=veg_counts.get) if veg_counts else None
    if surface_state and _confidence_ge(analysis.confidence, "medium"):
        surface_txt = _SURFACE_TEXT.get(surface_state, surface_state)
        veg_txt = _VEGETATION_TEXT.get(vegetation, "") if vegetation else ""
        if veg_txt:
            sentences.append(
                f"El solar es presenta {surface_txt} i amb {veg_txt}."
            )
        else:
            sentences.append(f"El solar es presenta {surface_txt}.")

    # 4. Surroundings
    pattern = analysis.nearby_building_pattern
    if pattern and pattern != "none" and _confidence_ge(analysis.confidence, "medium"):
        sentences.append(
            "En solars propers s'observen construccions de "
            "caracter\u00edstiques similars a l'obra projectada."
        )

    # 5. Subsoil
    subsoil = analysis.subsoil_visible
    if subsoil is False and _confidence_ge(analysis.confidence, "medium"):
        sentences.append(
            "No s'observen afloraments dels materials del subs\u00f2l "
            "ni a la parcel\u00b7la ni a l'entorn proper."
        )

    return " ".join(sentences)


# ---------------------------------------------------------------------------
# Access description
# ---------------------------------------------------------------------------


def _is_street_label(label: str) -> bool:
    """Check if a Cadastre label looks like a street name (not a parcel description)."""
    lower = label.lower()
    return any(lower.startswith(kw) for kw in DIRECTION_PREPOSITIONS)


def _generate_access_description(
    analysis: SiteAnalysis,
    cadastre_adjacents: dict[str, str],
) -> str:
    for direction in ("south", "north", "east", "west"):
        ba = analysis.boundary_analyses.get(direction)
        street_name = cadastre_adjacents.get(direction, "")
        if not street_name or not _is_street_label(street_name):
            continue
        # Street confirmed by Cadastre label (vision may over-classify as street)
        street_lower = street_name.lower()
        prep = "del"
        for keyword, p in DIRECTION_PREPOSITIONS.items():
            if street_lower.startswith(keyword):
                prep = p
                break
        dir_cat = DIRECTION_CAT[direction]
        return (
            f"El dia dels treballs de camp es realitza l'entrada a la zona "
            f"d'estudi a trav\u00e9s {prep} {street_name} existent al {dir_cat}."
        )
    return ""


# ---------------------------------------------------------------------------
# Location sentence
# ---------------------------------------------------------------------------


def _generate_location_sentence(
    street_address: str,
    municipality: str,
    building_type: str,
) -> str:
    if not street_address and not municipality:
        return ""

    # Build location part with Catalan article
    if street_address:
        street_lower = street_address.lower()
        if any(street_lower.startswith(w) for w in ("avinguda", "autopista")):
            loc = f"a l'{street_address}"
        elif any(
            street_lower.startswith(w)
            for w in ("placa", "ronda", "travessia", "partida")
        ):
            loc = f"a la {street_address}"
        else:
            loc = f"al {street_address}"
    else:
        loc = f"al terme municipal de {municipality}"

    if building_type and municipality and street_address:
        return (
            f"L'edificaci\u00f3 que es preveu construir, consistent en "
            f"{building_type}, es situar\u00e0 {loc}, al municipi de {municipality}."
        )
    if municipality and street_address:
        return (
            f"L'edificaci\u00f3 que es preveu construir es situar\u00e0 "
            f"{loc}, al municipi de {municipality}."
        )
    return f"L'edificaci\u00f3 que es preveu construir es situar\u00e0 {loc}."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_enriched_texts(
    analysis: SiteAnalysis,
    cadastre_adjacents: dict[str, str],
    street_address: str = "",
    municipality: str = "",
    building_type: str = "",
) -> dict[str, str]:
    """Generate enriched Catalan text from vision analysis.

    Takes structured micro-fields from ortho vision and converts them to
    report-ready Catalan prose.

    Args:
        analysis: SiteAnalysis from ortho_vision module.
        cadastre_adjacents: Cadastre labels per direction
            (e.g. {"north": "Carrer X", "south": "parcella veina"}).
        street_address: Project street address.
        municipality: Municipality name.
        building_type: Building type description (e.g. "habitatge unifamiliar").

    Returns:
        Dict with keys: adjacent_north, adjacent_south, adjacent_east,
        adjacent_west, site_description, is_anthropized, access_description,
        location_sentence.
    """
    result: dict[str, Any] = {}

    # Adjacents
    for direction in ("north", "south", "east", "west"):
        ba = analysis.boundary_analyses.get(direction)
        cadastre_label = cadastre_adjacents.get(direction, "")
        if ba:
            result[f"adjacent_{direction}"] = _generate_adjacent_text(
                ba, cadastre_label
            )
        else:
            result[f"adjacent_{direction}"] = cadastre_label

    # Find access direction (first street-facing boundary confirmed by Cadastre)
    access_dir: str | None = None
    for d in ("south", "north", "east", "west"):
        label = cadastre_adjacents.get(d, "")
        if label and _is_street_label(label):
            access_dir = d
            break

    # Site description
    result["site_description"] = _generate_site_description(analysis, access_dir)

    # Site condition
    result["is_anthropized"] = analysis.is_anthropized

    # Access description
    result["access_description"] = _generate_access_description(
        analysis, cadastre_adjacents
    )

    # Location sentence
    result["location_sentence"] = _generate_location_sentence(
        street_address, municipality, building_type
    )

    logger.debug(
        "Generated enriched texts: %d keys, site_description=%d chars",
        len(result),
        len(result.get("site_description", "")),
    )

    return result
