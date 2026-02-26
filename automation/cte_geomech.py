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
    # (nspt, phi_degrees) — CTE Table 4.1 for sands
    # Extended below N=10 for Schmertmann correction on fine-grained soils
    (0, 26),
    (5, 28),
    (10, 30),
    (15, 32),
    (22, 34),
    (30, 36),
    (36, 38),
    (45, 40),
    (55, 42),
]


# === Schmertmann (1970) grain-size correction factors ===
# Factor n adjusts the effective N before entering the phi table.
# Finer soils get lower effective N → lower phi for the same blow count.
# Reference: Eva's document Spt-correlacions.doc
SCHMERTMANN_N_FACTORS = {
    "granular": 2.0,       # Gravels, clean sands
    "grava": 2.0,
    "arena": 2.0,
    "arena_limosa": 1.6,   # Silty sands
    "cohesive": 1.25,      # Sandy silts, silty clays
    "limo": 1.25,
    "arcilla": 1.0,        # Clays
}
# Baseline: n=2.5 (from Schmertmann's original, for "slightly silty sands")
SCHMERTMANN_N_BASELINE = 2.5


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

def nspt_to_phi(nspt: float, soil_type: str = "granular") -> float:
    """
    Friction angle from N value using CTE Table 4.1 with Schmertmann (1970)
    grain-size correction.

    CTE Table 4.1 is calibrated for clean sands. Schmertmann's factor n
    adjusts the effective N for finer-grained soils, giving lower phi
    for the same blow count (fines reduce dilatancy).

    Args:
        nspt: SPT/DPSH N value (should be Nb, not raw N20)
        soil_type: Soil classification for Schmertmann correction.
            "granular"/"grava"/"arena" → n=2.0
            "arena_limosa" → n=1.6
            "cohesive"/"limo" → n=1.25
            "arcilla" → n=1.0

    Returns:
        Friction angle in degrees
    """
    # Apply Schmertmann grain-size correction
    n_factor = SCHMERTMANN_N_FACTORS.get(soil_type, 2.0)
    n_eff = nspt * (n_factor / SCHMERTMANN_N_BASELINE)

    if n_eff <= TABLE_4_1_PHI[0][0]:
        return TABLE_4_1_PHI[0][1]
    if n_eff >= TABLE_4_1_PHI[-1][0]:
        return TABLE_4_1_PHI[-1][1]

    for i in range(len(TABLE_4_1_PHI) - 1):
        n1, phi1 = TABLE_4_1_PHI[i]
        n2, phi2 = TABLE_4_1_PHI[i + 1]
        if n1 <= n_eff <= n2:
            ratio = (n_eff - n1) / (n2 - n1)
            return phi1 + ratio * (phi2 - phi1)

    return 35.0  # fallback


def nspt_to_E_kg_cm2(nspt: float, conservative: bool = True) -> float:
    """
    Deformation modulus from NSPT using CTE Table D.23.

    Args:
        nspt: SPT/DPSH N value
        conservative: If True (default), use lower portion of the CTE range
            (E_min + 10% of range). Matches G3DT professional practice where
            Eva consistently uses conservative E values for safety.
            If False, interpolate linearly across the full range.

    Returns:
        E in kg/cm² (1 MN/m² = 10.2 kg/cm²)
    """
    MN_TO_KG_CM2 = 10.197  # 1 MN/m² = 10.197 kg/cm²

    for nspt_min, nspt_max, _, _, _, E_min, E_max in TABLE_D23:
        if nspt_min <= nspt < nspt_max:
            if conservative:
                # Conservative: E_min + 10% of range (matches Eva's practice)
                E_MN = E_min + 0.1 * (E_max - E_min)
            else:
                # Full interpolation within the range
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
    Density from CTE Table D.27 "peso específico", fixed by soil type.

    Eva's practice: pick a representative value from D.27 by lithology,
    not interpolate with N20. Values confirmed from 4 reference projects.

    Args:
        nspt: SPT/DPSH N value (unused — kept for API compatibility)
        soil_type: 'granular', 'cohesive', 'grava', 'arena', 'limo', 'arcilla'

    Returns:
        Density in g/cm³ (= T/m³)
    """
    # Fixed values from D.27 "peso específico", matching Eva's practice:
    # - Granulars (graves, sorres): ~2.0 g/cm³ (mid-low of D.27 range 19-22 kN/m³)
    # - Llims/cohesive: ~1.90 g/cm³ (low of D.27 range 17-20 kN/m³)
    # - Argiles: ~1.90 g/cm³ (conservative within 15-22 kN/m³)
    # - Rock: handled separately by rock_params_default() → 2.20 g/cm³
    GAMMA_BY_TYPE = {
        "granular": 2.0,
        "grava": 2.0,
        "arena": 2.0,
        "cohesive": 1.90,
        "limo": 1.90,
        "arcilla": 1.90,
    }

    return GAMMA_BY_TYPE.get(soil_type, 2.0)


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


# === Soil type auto-detection from lithological description ===

SOIL_TYPE_KEYWORDS = {
    "arena_limosa": ["sorra limosa", "arena limosa", "sorr.*llim"],
    "grava": ["grav", "gravel"],
    "arena": ["sorr", "arena", "sand"],
    "limo": ["llim", "silt", "marga"],
    "arcilla": ["argil", "clay", "argila"],
}


def detect_soil_type(description: str) -> str:
    """Auto-detect soil type from lithological description.

    Checks most specific patterns first (arena_limosa before arena).

    Returns: 'grava', 'arena', 'arena_limosa', 'limo', 'arcilla', or 'granular'
    """
    import re
    desc = description.lower()
    for soil_type, keywords in SOIL_TYPE_KEYWORDS.items():
        for kw in keywords:
            if '.*' in kw:
                if re.search(kw, desc):
                    return soil_type
            elif kw in desc:
                return soil_type
    return "granular"


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
