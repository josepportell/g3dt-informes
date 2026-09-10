#!/usr/bin/env python3
"""
G3DT CTE Classification Calculator

Classifies buildings and soils per CTE DB SE-C (Codigo Tecnico de la Edificacion).

References:
- CTE DB SE-C: Seguridad Estructural - Cimientos (Documento Basico)
- Table 3.1: Building classification (C-0, C-1, C-2)
- Table 3.2: Soil classification (T-1, T-2, T-3)
- Table 3.3: Required investigation by building/soil combination

Author: Eficients.cat
Date: 2026-02-03
"""

import re
import sys
from dataclasses import dataclass, field
from typing import Optional

from .dpsh_extractor import DPSHData


@dataclass
class CTEClassification:
    """Result of CTE classification per DB SE-C."""
    building_class: str  # C-0, C-1, C-2
    soil_class: str  # T-1, T-2, T-3
    investigation_level: str  # Description of required investigation
    notes: list[str] = field(default_factory=list)


# Investigation level matrix per CTE Table 3.3
# Keys: (building_class, soil_class) -> investigation description
INVESTIGATION_MATRIX = {
    # C-0: Small buildings
    ("C-0", "T-1"): "Reconeixement superficial. Pot ser suficient amb inspeccio visual i consulta de dades existents.",
    ("C-0", "T-2"): "Reconeixement basic. Proves penetrometriques (DPSH) i/o cales.",
    ("C-0", "T-3"): "Reconeixement complet. Sondeigs mecanics i assaigs de laboratori.",

    # C-1: Medium buildings
    ("C-1", "T-1"): "Reconeixement basic. Proves penetrometriques (DPSH) i/o cales.",
    ("C-1", "T-2"): "Reconeixement complet. Sondeigs mecanics, DPSH i assaigs de laboratori.",
    ("C-1", "T-3"): "Reconeixement intensiu. Sondeigs mecanics, proves in situ i assaigs de laboratori extensos.",

    # C-2: Large buildings
    ("C-2", "T-1"): "Reconeixement complet. Sondeigs mecanics, DPSH i assaigs de laboratori.",
    ("C-2", "T-2"): "Reconeixement intensiu. Sondeigs mecanics, proves in situ i assaigs de laboratori extensos.",
    ("C-2", "T-3"): "Reconeixement molt intensiu. Campanyes geotecniques completes amb proves especials.",
}


def parse_floor_count(floors_str: str) -> int:
    """
    Parse floor string to integer count.

    Catalan building floor notation:
    - Pb = Planta baixa (ground floor) = 1 floor
    - Pp = Planta pis (upper floor)
    - Ps = Planta soterrani (basement)

    Examples:
        "Pb" -> 1
        "Pb + 1Pp" -> 2
        "Pb + 2Pp" -> 3
        "Pb + 3Pp + 1Ps" -> 5 (4 above ground + 1 basement)
        "3" -> 3
        3 -> 3

    Args:
        floors_str: Floor description string or integer

    Returns:
        Total number of floors (including basement if mentioned)

    Note:
        Basement floors ARE counted for CTE classification purposes.
        The has_basement parameter in classify_building handles additional
        basements not mentioned in the floor string.
    """
    # Handle already-integer input
    if isinstance(floors_str, int):
        return floors_str
    if isinstance(floors_str, float):
        return int(floors_str)

    floors_str = str(floors_str).strip()

    # Try direct integer conversion
    try:
        return int(floors_str)
    except ValueError:
        pass

    # Normalize string: lowercase, remove extra spaces
    normalized = floors_str.lower().replace(" ", "")

    total_floors = 0

    # Count ground floor (Pb = planta baixa)
    if "pb" in normalized:
        total_floors += 1

    # Count upper floors (Pp = planta pis)
    # Matches: "1pp", "2pp", "+1pp", "+2pp"
    pp_match = re.search(r"(\d+)pp", normalized)
    if pp_match:
        total_floors += int(pp_match.group(1))
    elif "pp" in normalized:
        # Just "Pp" without number means 1 upper floor
        total_floors += 1

    # Also match "p1", "p2" format (alternate notation for upper floors)
    # e.g., "pb+p1" = 1 upper floor, "pb+p2" = 2 upper floors
    if not pp_match and "pp" not in normalized:
        p_num_match = re.search(r'\+p(\d+)', normalized)
        if p_num_match:
            total_floors += int(p_num_match.group(1))
        else:
            # "Pb+1", "PB + 2": el número sol després del «+» són plantes pis (la lectura del
            # plànol de Castellar dona «PB+1» on l'Eva escriu «Pb+1Pp»; signat C-1). CTE 2026-09-07.
            plus_num = re.search(r'\+(\d+)(?![\d]*ps)', normalized)
            if plus_num and "pb" in normalized:
                total_floors += int(plus_num.group(1))

    # Count basement floors (Ps = planta soterrani)
    ps_match = re.search(r"(\d+)ps", normalized)
    if ps_match:
        total_floors += int(ps_match.group(1))
    elif "ps" in normalized:
        # Just "Ps" without number means 1 basement
        total_floors += 1

    # If we parsed nothing, try to extract any number
    if total_floors == 0:
        numbers = re.findall(r"\d+", floors_str)
        if numbers:
            total_floors = sum(int(n) for n in numbers)

    # Default to 1 if still nothing (at least ground floor)
    if total_floors == 0:
        total_floors = 1

    return total_floors


def classify_building(
    area_m2: float,
    floors: int | str,
    has_basement: bool = False
) -> str:
    """
    Classify building per CTE DB SE-C Table 3.1.

    Classification criteria (floor count is the sole C-0/C-1 discriminator
    per CTE DB SE-C; parcel/building area is NOT a discriminator):
    - C-0: 1 floor (minor importance, temporary/auxiliary)
    - C-1: 2-10 floors (standard constructions, default for most residential)
    - C-2: >= 11 floors (special constructions, critical infrastructure)

    Args:
        area_m2: Building footprint area in square meters (retained for API
            stability and notes; not used in classification).
        floors: Number of floors (int) or floor string (e.g., "Pb + 2Pp")
        has_basement: Whether building has basement(s) not counted in floors

    Returns:
        Building classification: "C-0", "C-1", or "C-2"

    Raises:
        ValueError: If area_m2 is negative

    Example:
        >>> classify_building(296.88, "PB+P1", has_basement=False)
        'C-1'
        >>> classify_building(50, 1)
        'C-0'
        >>> classify_building(200, 12)
        'C-2'
    """
    # Validate area
    if area_m2 < 0:
        raise ValueError(f"area_m2 cannot be negative: {area_m2}")
    _ = area_m2  # kept for API stability; not a classification input

    # Parse floor count
    floor_count = parse_floor_count(floors)

    # Add basement if not already counted
    total_floors = floor_count + (1 if has_basement else 0)

    # Apply classification rules per CTE DB SE-C (floor count only)
    if total_floors >= 11:
        return "C-2"
    elif total_floors >= 2:
        return "C-1"
    else:
        return "C-0"


def classify_soil(
    dpsh_data: Optional[DPSHData] = None,
    has_fill: bool = False,
    average_n20: Optional[float] = None
) -> str:
    """
    Classify soil per CTE DB SE-C Table 3.2.

    Classification criteria (CTE DB SE-C Table 3.2):
    - T-1 (Favorable): Uniform natural soil, no fill, good bearing capacity
    - T-2 (Intermediate): Some variability or moderate bearing capacity
    - T-3 (Unfavorable): Heterogeneous, fill present, poor bearing capacity

    Args:
        dpsh_data: DPSHData object from dpsh_extractor (kept for API; not a decider)
        has_fill: Whether fill material is present (kept for API; not a decider)
        average_n20: Direct N20 value (kept for API; not a decider)

    Returns:
        Soil classification: "T-1" (default; T-2/T-3 are the geologist's call)

    Note (criteri de l'Eva, 2026-09-07):
        L'Eva escriu **T-1 a 6/6 informes signats amb taula CTE** (Castellar, Rubí, Bell-lloc, Linyola,
        Alcoletge, Vilanova), també amb rebliment antròpic al primer nivell (Alcoletge) i amb N20 mitjà
        < 10 (Alcoletge 7,8). La classe de terreny del CTE és una decisió de reconeixement, no un
        resultat del DPSH: el defecte és T-1 i T-2/T-3 només si l'Eva ho canvia. Els arguments es
        conserven per compatibilitat i traçabilitat; no decideixen. Abans: T-2 per N20 < 20, T-3 amb
        rebliment (`cte_sol` 1/6 encerts a M341).
    """
    _ = (dpsh_data, has_fill, average_n20)  # conservats per API; el criteri no en depèn
    return "T-1"


def get_cte_classification(
    area_m2: float,
    floors: int | str,
    has_basement: bool = False,
    dpsh_data: Optional[DPSHData] = None,
    has_fill: bool = False,
    average_n20: Optional[float] = None,
) -> CTEClassification:
    """
    Get complete CTE classification for a building project.

    Combines building and soil classification to determine required
    investigation level per CTE DB SE-C Table 3.3.

    Args:
        area_m2: Building footprint area in square meters
        floors: Number of floors (int) or floor string (e.g., "Pb + 2Pp")
        has_basement: Whether building has basement(s)
        dpsh_data: DPSHData object from dpsh_extractor (optional)
        has_fill: Whether fill material is present
        average_n20: Direct N20 value (use if dpsh_data not available)

    Returns:
        CTEClassification with building_class, soil_class,
        investigation_level, and notes

    Example:
        >>> result = get_cte_classification(
        ...     area_m2=200,
        ...     floors="Pb + 1Pp",
        ...     has_basement=True,
        ...     has_fill=False,
        ...     average_n20=25.5
        ... )
        >>> print(result.building_class, result.soil_class)
        C-0 T-1
    """
    notes: list[str] = []

    # Get building classification
    building_class = classify_building(area_m2, floors, has_basement)

    # Parse floor count for notes
    floor_count = parse_floor_count(floors)
    total_floors = floor_count + (1 if has_basement else 0)
    notes.append(f"Plantes totals: {total_floors}")

    if has_basement:
        notes.append("Inclou soterrani")

    # Get soil classification
    soil_class = classify_soil(dpsh_data, has_fill, average_n20)

    # Add soil notes
    if has_fill:
        notes.append("Presencia de reblerts (T-3 automatic)")

    if dpsh_data is not None:
        notes.append(f"N20 mitja: {dpsh_data.overall_average_n20:.1f}")
        if dpsh_data.any_water_detected:
            notes.append("Nivell freatic detectat")
    elif average_n20 is not None:
        notes.append(f"N20 mitja proporcionat: {average_n20:.1f}")
    else:
        notes.append("Sense dades DPSH - classificacio conservadora")

    # Get investigation level from matrix
    investigation_level = INVESTIGATION_MATRIX.get(
        (building_class, soil_class),
        "Reconeixement segons criteri tecnic"
    )

    return CTEClassification(
        building_class=building_class,
        soil_class=soil_class,
        investigation_level=investigation_level,
        notes=notes,
    )


def main():
    """Command-line interface for testing CTE classification."""
    print("\n" + "=" * 60)
    print("CTE DB SE-C Classification Calculator")
    print("=" * 60)

    # Test cases
    test_cases = [
        # (area, floors, basement, fill, n20, description)
        (150, "Pb", False, False, 25.0, "Petit habitatge unifamiliar"),
        (250, "Pb + 1Pp", False, False, 30.0, "Habitatge 2 plantes"),
        (250, "Pb + 2Pp", True, False, 22.0, "Habitatge amb soterrani"),
        (350, "Pb + 1Pp", False, False, 35.0, "Habitatge gran (> 300m2)"),
        (200, "Pb + 3Pp", True, False, 28.0, "Edifici plurifamiliar 5 plantes"),
        (500, 8, False, False, 40.0, "Edifici comercial 8 plantes"),
        (800, 12, True, False, 50.0, "Torre 13 plantes"),
        (200, "Pb", False, True, 15.0, "Solar amb reblerts"),
        (150, 2, False, False, 8.0, "Terreny fluix"),
        (150, 2, False, False, None, "Sense dades DPSH"),
    ]

    for area, floors, basement, fill, n20, desc in test_cases:
        print(f"\n{'-'*50}")
        print(f"Cas: {desc}")
        print(f"  Area: {area} m2, Plantes: {floors}, Soterrani: {'Si' if basement else 'No'}")
        print(f"  Reblerts: {'Si' if fill else 'No'}, N20: {n20 if n20 else 'N/A'}")

        result = get_cte_classification(
            area_m2=area,
            floors=floors,
            has_basement=basement,
            has_fill=fill,
            average_n20=n20,
        )

        print(f"\n  Classificacio edifici: {result.building_class}")
        print(f"  Classificacio terreny: {result.soil_class}")
        print(f"  Nivell investigacio: {result.investigation_level}")
        print(f"  Notes:")
        for note in result.notes:
            print(f"    - {note}")

    # Test floor parsing
    print(f"\n{'='*60}")
    print("Test de parsing de plantes:")
    print("=" * 60)

    floor_tests = [
        "Pb",
        "Pb + 1Pp",
        "Pb + 2Pp",
        "Pb + 3Pp + 1Ps",
        "3",
        3,
        "PB + 2PP",  # uppercase
        "pb+1pp",    # no spaces
    ]

    for ft in floor_tests:
        count = parse_floor_count(ft)
        print(f"  '{ft}' -> {count} plantes")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
