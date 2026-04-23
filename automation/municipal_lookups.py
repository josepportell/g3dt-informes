"""
Municipal Lookup Facade for G3DT Wizard Prefills

Thin wrapper around existing modules (cte_classifier, municipal_data)
providing the four lookup functions consumed by wizard_service.py:

- lookup_cte_edificacio: CTE building class from type + floors
- lookup_cte_sol: CTE soil class (delegates to cte_classifier.classify_soil)
- lookup_seismic_ab: NCSE-02 ab by municipality
- lookup_radon_zone: CSN/CTE radon zone by municipality

Municipality name normalization handles uppercase, accents, and
province suffixes like "Rubi (Barcelona)".

Author: Eficients.cat
Date: 2026-04-06
"""

from __future__ import annotations

import re
from typing import Optional

from .cte_classifier import classify_building, classify_soil, parse_floor_count
from .municipal_data import (
    get_seismic_ab_with_status,
    get_radon_zone_with_status,
    SEISMIC_AB_DEFAULT,
    RADON_ZONE_DEFAULT,
)


def _normalize_municipality(name: str) -> str:
    """Normalize municipality name for lookup.

    Strips province suffix and lowercases. Preserves accents because
    the downstream municipal_data JSON uses accented keys (e.g. "rubí").

    Examples:
        "BELL-LLOC"                -> "bell-lloc"
        "Rubí (Barcelona)"        -> "rubí"
        "Bell-Lloc d'Urgell"      -> "bell-lloc d'urgell"
        "CASTELLAR DEL VALLES"    -> "castellar del valles"
    """
    if not name:
        return ""
    # Strip province suffix in parentheses: "Rubí (Barcelona)" -> "Rubí"
    name = re.sub(r'\s*\(.*?\)\s*$', '', name)
    # Lowercase and strip
    return name.lower().strip()


def lookup_cte_edificacio(building_type: str, num_floors: int | str) -> str:
    """Classify building per CTE DB SE-C using existing cte_classifier.

    Args:
        building_type: E.g. "Habitatge unifamiliar", "Bloc plurifamiliar"
        num_floors: Floor count or Catalan notation ("Pb + 1Pp")

    Returns:
        "C-0", "C-1", or "C-2"
    """
    floor_count = parse_floor_count(num_floors)
    # area ignored by classify_building (kept for signature compatibility)
    return classify_building(area_m2=0, floors=floor_count)


def lookup_cte_sol(average_n20: Optional[float] = None) -> str:
    """Classify soil per CTE DB SE-C.

    All 7 Eva reference projects use T-1 (favorable terrain, no fill).
    Delegates to cte_classifier.classify_soil for correctness.

    Args:
        average_n20: Average N20 from DPSH (optional)

    Returns:
        "T-1", "T-2", or "T-3"
    """
    return classify_soil(average_n20=average_n20)


def lookup_seismic_ab(municipality: str) -> float:
    """Look up NCSE-02 basic seismic acceleration for a municipality.

    Args:
        municipality: Municipality name (any casing, accents OK)

    Returns:
        ab value in g (e.g. 0.04, 0.08). Falls back to 0.04.
    """
    if not municipality:
        return SEISMIC_AB_DEFAULT
    normalized = _normalize_municipality(municipality)
    result = get_seismic_ab_with_status(normalized)
    return result.ab


def lookup_radon_zone(municipality: str) -> int:
    """Look up CSN/CTE radon zone for a municipality.

    Args:
        municipality: Municipality name (any casing, accents OK)

    Returns:
        Radon zone: 0 (low), 1 (medium), or 2 (high). Falls back to 0.
    """
    if not municipality:
        return RADON_ZONE_DEFAULT
    normalized = _normalize_municipality(municipality)
    result = get_radon_zone_with_status(normalized)
    return result.zone


def format_seismic_ab_text(ab: float) -> str:
    """Format seismic ab for Eva's report style (comma decimal separator).

    Args:
        ab: Seismic acceleration in g (e.g. 0.04)

    Returns:
        Formatted string like "0,04"
    """
    return f"{ab:.2f}".replace('.', ',')
