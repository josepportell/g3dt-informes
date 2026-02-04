#!/usr/bin/env python3
"""
Municipal Data Lookups for G3DT Reports

Provides lookup tables for municipality-specific parameters required
in geotechnical reports:
- Seismic acceleration (ab) from NCSE-02
- Radon zone classification from CSN/CTE DB HS6

Data sources:
- NCSE-02 Annex 1: Acceleració sísmica bàsica per municipis
- RD 732/2019 Apèndix B: Classificació de municipis per potencial de radó

Author: Eficients.cat
Date: 2026-02-04
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# === Seismic Data (NCSE-02) ===

# Basic seismic acceleration (ab) in units of g (gravity)
# Source: Norma de Construcción Sismorresistente NCSE-02, Annex 1
# Format: municipality_name (lowercase, normalized) -> ab value

SEISMIC_AB_VALUES: dict[str, float] = {
    # Depressió de l'Ebre - Lleida province (low seismicity)
    "lleida": 0.04,
    "balaguer": 0.04,
    "tarrega": 0.04,
    "tàrrega": 0.04,
    "mollerussa": 0.04,
    "bell-lloc d'urgell": 0.04,
    "bell-lloc": 0.04,
    "bellpuig": 0.04,
    "linyola": 0.04,
    "agramunt": 0.04,
    "cervera": 0.04,
    "les borges blanques": 0.04,
    "almacelles": 0.04,
    "alcarras": 0.04,
    "alcarràs": 0.04,
    "alpicat": 0.04,
    "artesa de segre": 0.04,
    "golmes": 0.04,
    "golmés": 0.04,
    "el palau d'anglesola": 0.04,
    "fondarella": 0.04,
    "la seu d'urgell": 0.05,
    "tremp": 0.05,
    "sort": 0.06,
    "vielha": 0.05,

    # Vallès-Penedès - Barcelona province (moderate seismicity due to Vallès fault)
    "barcelona": 0.04,
    "rubi": 0.04,
    "rubí": 0.04,
    "terrassa": 0.04,
    "sabadell": 0.04,
    "sant cugat del valles": 0.04,
    "sant cugat del vallès": 0.04,
    "cerdanyola del valles": 0.04,
    "cerdanyola del vallès": 0.04,
    "barbera del valles": 0.04,
    "barberà del vallès": 0.04,
    "castellar del valles": 0.04,
    "castellar del vallès": 0.04,
    "vilafranca del penedes": 0.04,
    "vilafranca del penedès": 0.04,
    "martorell": 0.04,
    "sant sadurni d'anoia": 0.04,
    "sant sadurní d'anoia": 0.04,
    "olesa de montserrat": 0.04,
    "esparreguera": 0.04,
    "abrera": 0.04,
    "sant andreu de la barca": 0.04,
    "molins de rei": 0.04,
    "sant feliu de llobregat": 0.04,
    "palleja": 0.04,
    "pallejà": 0.04,
    "granollers": 0.04,
    "mataro": 0.04,
    "mataró": 0.04,

    # Girona province (higher seismicity in Pyrenees)
    "girona": 0.05,
    "figueres": 0.06,
    "olot": 0.07,
    "ripoll": 0.07,
    "puigcerda": 0.06,
    "puigcerdà": 0.06,

    # Tarragona province
    "tarragona": 0.04,
    "reus": 0.04,
    "tortosa": 0.05,
    "amposta": 0.06,
}

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

    # Normalize: lowercase, strip whitespace
    key = municipality.lower().strip()

    # Try exact match
    if key in SEISMIC_AB_VALUES:
        return SeismicLookupResult(ab=SEISMIC_AB_VALUES[key], found=True)

    # Try partial match (municipality name contained in key or vice versa)
    for muni_key, ab_value in SEISMIC_AB_VALUES.items():
        if muni_key in key or key in muni_key:
            return SeismicLookupResult(ab=ab_value, found=True)

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
# Source: RD 732/2019 Apèndix B (Código Técnico de la Edificación DB HS6)
# Zone 0: Low potential (<300 Bq/m³)
# Zone 1: Medium potential (300-600 Bq/m³) - basic protection required
# Zone 2: High potential (>600 Bq/m³) - enhanced protection required

RadonZone = Literal[0, 1, 2]

RADON_ZONES: dict[str, RadonZone] = {
    # Depressió de l'Ebre - Lleida province
    # Mostly Zone 0 (sedimentary basin, low radon)
    "lleida": 0,
    "balaguer": 0,
    "tarrega": 0,
    "tàrrega": 0,
    "mollerussa": 0,
    "bell-lloc d'urgell": 0,
    "bell-lloc": 0,
    "bellpuig": 0,
    "linyola": 0,
    "agramunt": 0,
    "cervera": 0,
    "les borges blanques": 0,
    "almacelles": 0,
    "alcarras": 0,
    "alcarràs": 0,
    "alpicat": 0,
    "artesa de segre": 0,
    "golmes": 0,
    "golmés": 0,
    "el palau d'anglesola": 0,
    "fondarella": 0,

    # Pyrenees - higher radon due to granitic rocks
    "la seu d'urgell": 1,
    "tremp": 1,
    "sort": 2,
    "vielha": 1,

    # Vallès-Penedès - Barcelona province
    # Variable: Zone 1 due to proximity to granitic Serralades
    "barcelona": 0,
    "rubi": 1,
    "rubí": 1,
    "terrassa": 1,
    "sabadell": 1,
    "sant cugat del valles": 1,
    "sant cugat del vallès": 1,
    "cerdanyola del valles": 1,
    "cerdanyola del vallès": 1,
    "barbera del valles": 1,
    "barberà del vallès": 1,
    "castellar del valles": 1,
    "castellar del vallès": 1,
    "vilafranca del penedes": 0,
    "vilafranca del penedès": 0,
    "martorell": 1,
    "sant sadurni d'anoia": 0,
    "sant sadurní d'anoia": 0,
    "olesa de montserrat": 1,
    "esparreguera": 1,
    "abrera": 1,
    "sant andreu de la barca": 1,
    "molins de rei": 1,
    "sant feliu de llobregat": 1,
    "palleja": 1,
    "pallejà": 1,
    "granollers": 1,
    "mataro": 0,
    "mataró": 0,

    # Girona province - variable
    "girona": 1,
    "figueres": 0,
    "olot": 1,
    "ripoll": 2,
    "puigcerda": 2,
    "puigcerdà": 2,

    # Tarragona province - mostly low
    "tarragona": 0,
    "reus": 0,
    "tortosa": 0,
    "amposta": 0,
}

# Default zone for municipalities not in the lookup table
RADON_ZONE_DEFAULT: RadonZone = 0


@dataclass
class RadonInfo:
    """Radon zone information for a municipality."""
    zone: RadonZone
    level: str  # "baix", "mitjà", "alt"
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
                    "No es requereixen mesures específiques de protecció "
                    "contra el radó."
                ),
            )
        elif zone == 1:
            return cls(
                zone=1,
                level="mitjà",
                requires_protection=True,
                recommendation=(
                    "Es recomana considerar mesures bàsiques de ventilació "
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
                    "Es requereixen mesures de protecció contra el radó "
                    "segons el CTE DB HS6, incloent barrera anti-radó i "
                    "sistema de ventilació o despressurització del terreny."
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

    # Normalize: lowercase, strip whitespace
    key = municipality.lower().strip()

    # Try exact match
    if key in RADON_ZONES:
        return RadonLookupResult(zone=RADON_ZONES[key], found=True)

    # Try partial match
    for muni_key, zone in RADON_ZONES.items():
        if muni_key in key or key in muni_key:
            return RadonLookupResult(zone=zone, found=True)

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

    test_municipalities = [
        "Bell-Lloc d'Urgell",
        "Linyola",
        "Rubí",
        "Castellar del Vallès",
        "Olot",
        "Sort",
        "Unknown Municipality",
    ]

    print("\n--- Seismic Data (NCSE-02) ---")
    for muni in test_municipalities:
        ab = get_seismic_ab(muni)
        required = is_seismic_norm_required(ab)
        print(f"  {muni}: ab = {ab}g, norm required = {required}")

    print("\n--- Radon Data (CTE DB HS6) ---")
    for muni in test_municipalities:
        info = get_radon_info(muni)
        print(f"  {muni}: Zone {info.zone} ({info.level})")
        print(f"    Protection required: {info.requires_protection}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
