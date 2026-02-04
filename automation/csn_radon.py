"""
CSN Radon Potential Query Module

Queries the Consell de Seguretat Nuclear (CSN) radon potential data
to get site-specific radon levels based on UTM coordinates.

This provides more granular data than CTE municipal zones:
- CTE DB HS6: Municipality-wide Zone 0/1/2
- CSN Potential: Geographic polygons with Bq/m³ ranges

Data source: CSN Mapa del Potencial de Radó d'Espanya (2017)
https://www.csn.es/mapa-del-potencial-de-radon-en-espana
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json

# Lazy load shapely for point-in-polygon queries
_shapely_loaded = False
_Point = None
_shape = None


def _ensure_shapely():
    """Lazy load shapely to avoid import overhead when not needed."""
    global _shapely_loaded, _Point, _shape
    if not _shapely_loaded:
        from shapely.geometry import Point, shape
        _Point = Point
        _shape = shape
        _shapely_loaded = True


# Data file location
DATA_FILE = Path(__file__).parent / "data" / "csn_radon_catalunya.geojson"

# Cached GeoJSON data
_GEODATA: Optional[dict] = None


@dataclass
class RadonPotential:
    """Radon potential at a specific location."""

    category: str
    """CSN category string: "< 100", "101 - 200", "201 - 300", "301 - 400", "> 400" """

    bq_m3_min: int
    """Minimum Bq/m³ for this category."""

    bq_m3_max: Optional[int]
    """Maximum Bq/m³ for this category (None for "> 400")."""

    risk_level: str
    """Risk level in Catalan: "molt baix", "baix", "moderat", "alt", "molt alt" """

    found: bool
    """True if coordinates fall within a CSN polygon."""

    source: str = "CSN Cartografia del Potencial de Radó (2017)"
    """Data source citation."""


# Category mappings
CATEGORY_INFO = {
    "< 100": {
        "bq_m3_min": 0,
        "bq_m3_max": 100,
        "risk_level": "molt baix",
    },
    "101 - 200": {
        "bq_m3_min": 101,
        "bq_m3_max": 200,
        "risk_level": "baix",
    },
    "201 - 300": {
        "bq_m3_min": 201,
        "bq_m3_max": 300,
        "risk_level": "moderat",
    },
    "301 - 400": {
        "bq_m3_min": 301,
        "bq_m3_max": 400,
        "risk_level": "alt",
    },
    "> 400": {
        "bq_m3_min": 401,
        "bq_m3_max": None,
        "risk_level": "molt alt",
    },
}


def _load_geodata() -> dict:
    """Load and cache the GeoJSON data."""
    global _GEODATA
    if _GEODATA is None:
        if not DATA_FILE.exists():
            raise FileNotFoundError(
                f"CSN radon data file not found: {DATA_FILE}\n"
                "Run the conversion script to generate it."
            )
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            _GEODATA = json.load(f)
    return _GEODATA


def get_radon_potential(utm_x: float, utm_y: float) -> RadonPotential:
    """
    Query CSN radon potential at specific UTM coordinates.

    Args:
        utm_x: UTM X coordinate (ETRS89 Zone 31N, EPSG:25831)
        utm_y: UTM Y coordinate (ETRS89 Zone 31N, EPSG:25831)

    Returns:
        RadonPotential with category and risk level.
        If coordinates don't fall within any polygon, returns a default
        "not found" result.

    Example:
        >>> result = get_radon_potential(307500.0, 4615500.0)  # Bell-Lloc
        >>> print(f"Risk: {result.risk_level}, Range: {result.bq_m3_min}-{result.bq_m3_max} Bq/m³")
    """
    _ensure_shapely()

    point = _Point(utm_x, utm_y)
    geodata = _load_geodata()

    for feature in geodata.get("features", []):
        geometry = _shape(feature["geometry"])
        if geometry.contains(point):
            category = feature["properties"].get("cat_radon", "")
            if category in CATEGORY_INFO:
                info = CATEGORY_INFO[category]
                return RadonPotential(
                    category=category,
                    bq_m3_min=info["bq_m3_min"],
                    bq_m3_max=info["bq_m3_max"],
                    risk_level=info["risk_level"],
                    found=True,
                )

    # Not found - coordinates outside Catalunya or in uncovered area
    return RadonPotential(
        category="",
        bq_m3_min=0,
        bq_m3_max=None,
        risk_level="desconegut",
        found=False,
    )


def get_radon_potential_text(utm_x: float, utm_y: float) -> Optional[str]:
    """
    Get formatted text for radon potential at coordinates.

    Returns None if coordinates don't fall within any CSN polygon.

    Args:
        utm_x: UTM X coordinate (ETRS89 Zone 31N)
        utm_y: UTM Y coordinate (ETRS89 Zone 31N)

    Returns:
        Formatted paragraph in Catalan, or None if no data.
    """
    result = get_radon_potential(utm_x, utm_y)

    if not result.found:
        return None

    # Format Bq/m³ range
    if result.bq_m3_max is None:
        bq_range = f"superior a {result.bq_m3_min} Bq/m³"
    else:
        bq_range = f"{result.bq_m3_min}-{result.bq_m3_max} Bq/m³"

    return (
        f"Addicionalment, segons la cartografia del potencial de radó del "
        f"Consell de Seguretat Nuclear (CSN, 2017), les coordenades específiques "
        f"del projecte (X: {utm_x:.0f}, Y: {utm_y:.0f}) es troben en una zona amb "
        f"potencial de radó de {bq_range} (risc {result.risk_level})."
    )


# Convenience function for testing
def test_locations():
    """Test with known Catalunya locations."""
    test_coords = [
        ("Bell-Lloc d'Urgell", 307500.0, 4615500.0),
        ("Balaguer", 320000.0, 4633000.0),
        ("Rubí", 419500.0, 4596000.0),
        ("Castellar del Vallès", 424500.0, 4610000.0),
        ("Barcelona", 431000.0, 4582000.0),
    ]

    print("CSN Radon Potential Test Results")
    print("=" * 60)

    for name, x, y in test_coords:
        result = get_radon_potential(x, y)
        if result.found:
            bq_max = result.bq_m3_max or "+"
            print(f"{name}: {result.category} ({result.bq_m3_min}-{bq_max} Bq/m³) - Risc {result.risk_level}")
        else:
            print(f"{name}: No data found")


if __name__ == "__main__":
    test_locations()
