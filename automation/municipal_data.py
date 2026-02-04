#!/usr/bin/env python3
"""
Municipal Data Lookups for G3DT Reports

Provides lookup tables for municipality-specific parameters required
in geotechnical reports:
- Seismic acceleration (ab) from NCSE-02
- Radon zone classification from CSN/CTE DB HS6

Data is loaded from JSON file containing all 947 Catalunya municipalities.

Data sources:
- NCSE-02 Annex 1: Acceleracio sismica basica per municipis
- RD 732/2019 Apendix B: Classificacio de municipis per potencial de rado
- INE municipal codes for Catalunya

Author: Eficients.cat
Date: 2026-02-04
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# === Data Loading ===

DATA_FILE = Path(__file__).parent / "data" / "catalunya_municipal_data.json"

_MUNICIPAL_DATA: dict | None = None


def _load_municipal_data() -> dict:
    """Load municipal data from JSON file."""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_data() -> dict:
    """Get municipal data, loading if needed."""
    global _MUNICIPAL_DATA
    if _MUNICIPAL_DATA is None:
        _MUNICIPAL_DATA = _load_municipal_data()
    return _MUNICIPAL_DATA


def _normalize_key(municipality: str) -> str:
    """
    Normalize municipality name for lookup.

    The JSON uses lowercase keys like "bell-lloc d'urgell".
    """
    return municipality.lower().strip()


# === Source Information ===

def get_seismic_source() -> str:
    """Get the source citation for seismic data."""
    data = _get_data()
    return data["metadata"]["sources"]["seismic"]["source"]


def get_radon_source() -> str:
    """Get the source citation for radon data."""
    data = _get_data()
    return data["metadata"]["sources"]["radon"]["source"]


def get_seismic_legal_reference() -> str:
    """Get the legal reference for seismic data."""
    data = _get_data()
    source = data["metadata"]["sources"]["seismic"]
    return f"{source['source']} ({source['legal_reference']})"


def get_radon_legal_reference() -> str:
    """Get the legal reference for radon data."""
    data = _get_data()
    source = data["metadata"]["sources"]["radon"]
    return f"{source['source']} ({source['legal_reference']})"


def get_data_statistics() -> dict:
    """Get statistics about the municipal data coverage."""
    data = _get_data()
    return data["metadata"]["statistics"]


# === Seismic Data (NCSE-02) ===

# Default value for municipalities not in the lookup table
SEISMIC_AB_DEFAULT = 0.04


@dataclass
class SeismicLookupResult:
    """Result of seismic ab lookup."""
    ab: float
    found: bool  # True if municipality was in lookup table


def get_seismic_ab(municipality: str) -> float:
    """
    Get basic seismic acceleration (ab) for a municipality.

    Args:
        municipality: Municipality name (case-insensitive)

    Returns:
        ab value in units of g (gravity)
    """
    return get_seismic_ab_with_status(municipality).ab


def get_seismic_ab_with_status(municipality: str) -> SeismicLookupResult:
    """
    Get basic seismic acceleration (ab) for a municipality with lookup status.

    Args:
        municipality: Municipality name (case-insensitive)

    Returns:
        SeismicLookupResult with ab value and whether municipality was found
    """
    if not municipality:
        return SeismicLookupResult(ab=SEISMIC_AB_DEFAULT, found=False)

    data = _get_data()
    municipalities = data["municipalities"]
    key = _normalize_key(municipality)

    # Try exact match
    if key in municipalities:
        muni_data = municipalities[key]
        return SeismicLookupResult(ab=muni_data["seismic_ab"], found=True)

    # Try partial match (municipality name contained in key or vice versa)
    for muni_key, muni_data in municipalities.items():
        if muni_key in key or key in muni_key:
            return SeismicLookupResult(ab=muni_data["seismic_ab"], found=True)

    return SeismicLookupResult(ab=SEISMIC_AB_DEFAULT, found=False)


def is_seismic_norm_required(ab: float) -> bool:
    """
    Check if NCSE-02 application is mandatory.

    Per NCSE-02: Not mandatory for normal importance buildings
    when seismic calculation acceleration < 0.08g

    Args:
        ab: Basic seismic acceleration in g

    Returns:
        True if seismic norm application is mandatory
    """
    # For normal importance buildings (rho = 1.0), ac = S * rho * ab
    # With S = 1.0 (worst case for T-1 soils), ac = ab
    # Norm is mandatory when ac >= 0.08g
    return ab >= 0.08


# === Radon Data (CSN / CTE DB HS6) ===

# Radon zone classification
# Source: RD 732/2019 Apendix B (Codigo Tecnico de la Edificacion DB HS6)
# Zone 0: Low potential (<300 Bq/m3)
# Zone 1: Medium potential (300-600 Bq/m3) - basic protection required
# Zone 2: High potential (>600 Bq/m3) - enhanced protection required

RadonZone = Literal[0, 1, 2]

# Default zone for municipalities not in the lookup table
RADON_ZONE_DEFAULT: RadonZone = 0


@dataclass
class RadonInfo:
    """Radon zone information for a municipality."""
    zone: RadonZone
    level: str  # "baix", "mitja", "alt"
    requires_protection: bool
    recommendation: str

    @classmethod
    def from_zone(cls, zone: RadonZone) -> "RadonInfo":
        """Create RadonInfo from zone number."""
        if zone == 0:
            return cls(
                zone=0,
                level="baix",
                requires_protection=False,
                recommendation=(
                    "No es requereixen mesures especifiques de proteccio "
                    "contra el rado."
                ),
            )
        elif zone == 1:
            return cls(
                zone=1,
                level="mitja",
                requires_protection=True,
                recommendation=(
                    "Es recomana considerar mesures basiques de ventilacio "
                    "en soterranis i plantes en contacte amb el terreny, "
                    "d'acord amb el CTE DB HS6."
                ),
            )
        else:  # zone == 2
            return cls(
                zone=2,
                level="alt",
                requires_protection=True,
                recommendation=(
                    "Es requereixen mesures de proteccio contra el rado "
                    "segons el CTE DB HS6, incloent barrera anti-rado i "
                    "sistema de ventilacio o despressuritzacio del terreny."
                ),
            )


@dataclass
class RadonLookupResult:
    """Result of radon zone lookup."""
    zone: RadonZone
    found: bool  # True if municipality was in lookup table


def get_radon_zone(municipality: str) -> RadonZone:
    """
    Get radon zone classification for a municipality.

    Args:
        municipality: Municipality name (case-insensitive)

    Returns:
        Radon zone (0, 1, or 2)
    """
    return get_radon_zone_with_status(municipality).zone


def get_radon_zone_with_status(municipality: str) -> RadonLookupResult:
    """
    Get radon zone classification for a municipality with lookup status.

    Args:
        municipality: Municipality name (case-insensitive)

    Returns:
        RadonLookupResult with zone and whether municipality was found
    """
    if not municipality:
        return RadonLookupResult(zone=RADON_ZONE_DEFAULT, found=False)

    data = _get_data()
    municipalities = data["municipalities"]
    key = _normalize_key(municipality)

    # Try exact match
    if key in municipalities:
        muni_data = municipalities[key]
        return RadonLookupResult(zone=muni_data["radon_zone"], found=True)

    # Try partial match
    for muni_key, muni_data in municipalities.items():
        if muni_key in key or key in muni_key:
            return RadonLookupResult(zone=muni_data["radon_zone"], found=True)

    return RadonLookupResult(zone=RADON_ZONE_DEFAULT, found=False)


@dataclass
class RadonInfoWithStatus:
    """Complete radon info with lookup status."""
    info: RadonInfo
    found: bool  # True if municipality was in lookup table


def get_radon_info(municipality: str) -> RadonInfo:
    """
    Get complete radon information for a municipality.

    Args:
        municipality: Municipality name (case-insensitive)

    Returns:
        RadonInfo with zone, level, and recommendations
    """
    return get_radon_info_with_status(municipality).info


def get_radon_info_with_status(municipality: str) -> RadonInfoWithStatus:
    """
    Get complete radon information for a municipality with lookup status.

    Args:
        municipality: Municipality name (case-insensitive)

    Returns:
        RadonInfoWithStatus with radon info and whether municipality was found
    """
    result = get_radon_zone_with_status(municipality)
    info = RadonInfo.from_zone(result.zone)
    return RadonInfoWithStatus(info=info, found=result.found)


# === CLI for testing ===

if __name__ == "__main__":
    print("=" * 60)
    print("Municipal Data Lookups - Test")
    print("=" * 60)

    # Show data source info
    print("\n--- Data Sources ---")
    print(f"  Seismic: {get_seismic_legal_reference()}")
    print(f"  Radon: {get_radon_legal_reference()}")

    stats = get_data_statistics()
    print(f"\n--- Coverage Statistics ---")
    print(f"  Total municipalities: {stats['total_municipalities']}")
    print(f"  Radon Zone 0: {stats['radon_zone_0']}")
    print(f"  Radon Zone 1: {stats['radon_zone_1']}")
    print(f"  Radon Zone 2: {stats['radon_zone_2']}")
    print(f"  Seismic listed: {stats['seismic_listed']}")
    print(f"  Seismic default: {stats['seismic_default']}")

    test_municipalities = [
        "Bell-Lloc d'Urgell",
        "Linyola",
        "Rubi",
        "Castellar del Valles",
        "Olot",
        "Sort",
        "Unknown Municipality",
    ]

    print("\n--- Seismic Data (NCSE-02) ---")
    for muni in test_municipalities:
        result = get_seismic_ab_with_status(muni)
        required = is_seismic_norm_required(result.ab)
        found_str = "found" if result.found else "NOT FOUND (default)"
        print(f"  {muni}: ab = {result.ab}g, norm required = {required} [{found_str}]")

    print("\n--- Radon Data (CTE DB HS6) ---")
    for muni in test_municipalities:
        result = get_radon_info_with_status(muni)
        found_str = "found" if result.found else "NOT FOUND (default)"
        print(f"  {muni}: Zone {result.info.zone} ({result.info.level}) [{found_str}]")
        print(f"    Protection required: {result.info.requires_protection}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
