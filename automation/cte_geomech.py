"""
CTE DB SE-C Geotechnical Parameter Tables

Lookup tables from "Documento Básico SE-C: Seguridad estructural - Cimientos"
(Código Técnico de la Edificación).

Source: https://www.codigotecnico.org/pdf/Documentos/SE/DBSE-C.pdf

Tables implemented:
    D.23 - NSPT vs qu and E
    D.27 - Soil type vs gamma and phi
    D.28 - Soil type vs permeability K
    4.1  - NSPT vs phi (granular soils)

Author: Eficients.cat
Date: 2026-02-24
"""

from __future__ import annotations


# === Table D.23: NSPT → qu (kN/m²) and E (MN/m²) ===

TABLE_D23 = [
    # (nspt_min, nspt_max, category, qu_min, qu_max, E_min_MN, E_max_MN)
    (0, 10, "muy_flojos_o_muy_blandos", 0, 80, 0, 8),
    (10, 25, "flojos_o_blandos", 80, 150, 8, 40),
    (25, 50, "medios", 150, 300, 40, 100),
    (50, 999, "compactos_o_duros", 300, 500, 100, 500),
    # Rock categories (NSPT = Rechazo/refusal)
    # These are identified by lithology, not NSPT
]

# Rock categories from D.23 (qu and E ranges)
ROCK_CATEGORIES = {
    "rocas_blandas": {"qu_kN_m2": (500, 5_000), "E_MN_m2": (500, 8_000)},
    "rocas_duras": {"qu_kN_m2": (5_000, 40_000), "E_MN_m2": (8_000, 15_000)},
    "rocas_muy_duras": {"qu_kN_m2": (40_000, None), "E_MN_m2": (15_000, None)},
}


# === Table D.27: Soil type → gamma (kN/m³) and phi (degrees) ===

TABLE_D27 = {
    "grava": {"gamma_kN_m3": (19, 22), "phi": (34, 45)},
    "arena": {"gamma_kN_m3": (17, 20), "phi": (30, 36)},
    "limo": {"gamma_kN_m3": (17, 20), "phi": (25, 32)},
    "arcilla": {"gamma_kN_m3": (15, 22), "phi": (16, 28)},
    "tierra_vegetal": {"gamma_kN_m3": (17, 17), "phi": (25, 25)},
}


# === Table D.28: Soil type → permeability K (m/s) ===

TABLE_D28 = {
    "grava_neta": {"K_m_s": (1e-2, 1)},
    "arena_neta_o_grava_arena": {"K_m_s": (1e-5, 1e-2)},
    "arena_fina_limo": {"K_m_s": (1e-9, 1e-5)},
    "arcilla": {"K_m_s": (0, 1e-9)},
}


# === Table 4.1: NSPT → phi for granular soils ===

TABLE_4_1_PHI = [
    # (nspt, phi_degrees)
    (10, 30),
    (15, 32),
    (22, 34),
    (30, 36),
    (36, 38),
    (45, 40),
    (55, 42),
]


# === Table D.29: Ballast coefficient K30 (MN/m³) ===

TABLE_D29_K30 = {
    "arcilla_blanda": (15, 30),
    "arcilla_media": (30, 60),
    "arcilla_dura": (60, 200),
    "limo": (15, 45),
    "arena_floja": (10, 30),
    "arena_media": (30, 90),
    "arena_compacta": (90, 200),
    "grava_arenosa_floja": (70, 120),
    "grava_arenosa_compacta": (120, 300),
    "rocas_algo_alteradas": (300, 5_000),
    "rocas_sanas": (5_000, 50_000),
}


# === Lookup functions ===

def nspt_to_phi(nspt: float) -> float:
    """
    Friction angle from NSPT using CTE Table 4.1 (linear interpolation).

    Args:
        nspt: SPT/DPSH N value

    Returns:
        Friction angle in degrees
    """
    if nspt <= TABLE_4_1_PHI[0][0]:
        return TABLE_4_1_PHI[0][1]
    if nspt >= TABLE_4_1_PHI[-1][0]:
        return TABLE_4_1_PHI[-1][1]

    for i in range(len(TABLE_4_1_PHI) - 1):
        n1, phi1 = TABLE_4_1_PHI[i]
        n2, phi2 = TABLE_4_1_PHI[i + 1]
        if n1 <= nspt <= n2:
            # Linear interpolation
            ratio = (nspt - n1) / (n2 - n1)
            return phi1 + ratio * (phi2 - phi1)

    return 35.0  # fallback


def nspt_to_E_kg_cm2(nspt: float) -> float:
    """
    Deformation modulus from NSPT using CTE Table D.23 (interpolation within range).

    Args:
        nspt: SPT/DPSH N value

    Returns:
        E in kg/cm² (1 MN/m² = 10.2 kg/cm²)
    """
    MN_TO_KG_CM2 = 10.197  # 1 MN/m² = 10.197 kg/cm²

    for nspt_min, nspt_max, _, _, _, E_min, E_max in TABLE_D23:
        if nspt_min <= nspt < nspt_max:
            # Interpolate within the range
            if nspt_max == 999:
                ratio = min((nspt - nspt_min) / 50, 1.0)
            else:
                ratio = (nspt - nspt_min) / (nspt_max - nspt_min)
            E_MN = E_min + ratio * (E_max - E_min)
            return E_MN * MN_TO_KG_CM2

    # Dense/rock: use upper range
    return 500 * MN_TO_KG_CM2


def nspt_to_gamma_g_cm3(nspt: float, soil_type: str = "granular") -> float:
    """
    Density from NSPT using CTE Table D.27 ranges.

    Maps NSPT compacity to position within the D.27 gamma range
    for the given soil type.

    Args:
        nspt: SPT/DPSH N value
        soil_type: 'granular', 'cohesive', 'grava', 'arena', 'limo', 'arcilla'

    Returns:
        Density in g/cm³ (= T/m³)
    """
    KN_TO_G_CM3 = 1 / 9.81  # kN/m³ to g/cm³ (≈ T/m³)

    # Map soil_type to D.27 key
    type_map = {
        "granular": "grava",
        "grava": "grava",
        "arena": "arena",
        "cohesive": "arcilla",
        "limo": "limo",
        "arcilla": "arcilla",
    }
    d27_key = type_map.get(soil_type, "arena")
    props = TABLE_D27.get(d27_key, TABLE_D27["arena"])

    gamma_min, gamma_max = props["gamma_kN_m3"]

    # Use NSPT to interpolate within the range (0-50 maps to min-max)
    ratio = min(nspt / 50.0, 1.0)
    gamma_kN = gamma_min + ratio * (gamma_max - gamma_min)

    return gamma_kN * KN_TO_G_CM3


def is_rock(nspt: float, description: str = "") -> bool:
    """
    Determine if the material is rock based on NSPT and/or description.

    Rock indicators:
    - NSPT >= 100 (refusal)
    - Description contains rock-related keywords

    Args:
        nspt: SPT/DPSH N value (100+ typically means refusal)
        description: Lithological description

    Returns:
        True if material is likely rock
    """
    # NSPT refusal
    if nspt >= 100:
        return True

    # Description keywords
    rock_keywords = [
        "roca", "bretxa", "bretxes", "calcària", "calcàries",
        "gres", "gresos", "substrat", "conglomerat",
        "lutita", "lutites", "margues", "pissarra",
    ]
    desc_lower = description.lower()
    return any(kw in desc_lower for kw in rock_keywords)


def rock_params_default() -> dict:
    """
    Default geotechnical parameters for soft rock (CTE D.23 + D.25).

    These are conservative values for 'rocas blandas' category.
    Should be overridden by user_data.geomech_params when available.

    Returns:
        Dict with gamma, cohesion, phi, E
    """
    return {
        "gamma": 2.20,      # g/cm³ — typical for sedimentary rock
        "cohesion": 1.0,     # kg/cm² — rock has cohesion
        "phi": 35.0,         # degrees — conservative for rock
        "E": 500,            # kg/cm² — lower bound 'rocas blandas' (500 MN/m² * 10.2 / 10)
    }


def permeability_from_type(soil_type: str) -> tuple[float, float]:
    """
    Permeability range from CTE Table D.28.

    Args:
        soil_type: Description or type keyword

    Returns:
        (K_min, K_max) in m/s
    """
    desc = soil_type.lower()

    if any(kw in desc for kw in ["grava neta", "grava limpia", "grava gruixuda"]):
        return TABLE_D28["grava_neta"]["K_m_s"]
    elif any(kw in desc for kw in ["arena", "grava", "sorr"]):
        return TABLE_D28["arena_neta_o_grava_arena"]["K_m_s"]
    elif any(kw in desc for kw in ["lim", "silt", "fi"]):
        return TABLE_D28["arena_fina_limo"]["K_m_s"]
    elif any(kw in desc for kw in ["argil", "clay"]):
        return TABLE_D28["arcilla"]["K_m_s"]

    # Default: sand/gravel mix
    return TABLE_D28["arena_neta_o_grava_arena"]["K_m_s"]
