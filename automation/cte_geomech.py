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
    "rock": 2.0,           # Rock — N/A (handled by rock_params_default), but safe fallback
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

    Note: Callers should pass N20 (not Nb). The CTE D.23 brackets are
    calibrated for direct blow counts. Nb conversion is only needed for
    phi (CTE Table 4.1 / Schmertmann).

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
        "rock": 2.20,
    }

    return GAMMA_BY_TYPE.get(soil_type, 2.0)


def soil_type_to_cohesion(soil_type: str) -> float:
    """Cohesion (kg/cm²) by soil type, from Eva's Spt-correlacions.doc.

    Eva's practice (confirmed 2026-02-26):
    - Granular (graves, sorres): c = 0.0 (non-cohesive)
    - Slightly cohesive (llims, arenes limoses): c = 0.05 (Hunt table Cu=qu/2)
    - Clay: c = 0.10
    - Rock: handled by rock_params_default() → c = 1.0
    """
    COHESION_BY_TYPE = {
        "granular": 0.0,
        "grava": 0.0,
        "arena": 0.0,
        "arena_limosa": 0.05,
        "cohesive": 0.05,
        "limo": 0.05,
        "arcilla": 0.10,
        "rock": 1.0,
    }
    return COHESION_BY_TYPE.get(soil_type, 0.0)


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

    # Description keywords (ca + es; P6 2026-09-07: «Areniscas, sustrato», «brecha», «caliza» eren invisibles).
    # Les margues TOVES són cohesives, no roca (mateixa excepció que tenia `detect_soil_type`).
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in _SOFT_MARL_KEYWORDS):
        return False
    return any(kw in desc_lower for kw in _ROCK_KEYWORDS)


#: Roca per descripció (ca/es). «gres» també casa «gresos», «gresosa» (Linyola SPT «Lutita gresosa»).
_ROCK_KEYWORDS = (
    "roca", "bretxa", "bretxes", "brecha", "brechas", "calcària", "calcàries", "caliza", "calizas",
    "gres", "gresos", "arenisca", "areniscas", "substrat", "sustrato", "conglomerat", "conglomerado",
    "lutita", "lutites", "lutitas", "margues", "margas", "pissarra", "pizarra",
)
#: Margues toves: cohesiu (llim), mai roca.
_SOFT_MARL_KEYWORDS = ("marga tova", "margues toves", "marga blanda", "margas blandas")


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

#: Primer sintagma nominal → tipus (ca/es, text sense accents). L'ordre d'aparició al text mana:
#: «Arcilla limosa y arenosa con algunas gravas» → arcilla (no grava), «Bolos y gravas en matriz arenosa» → grava.
_TYPE_STEMS: tuple[tuple[str, str], ...] = (
    ("arena_limosa", r"\b(?:sorr\w*|aren\w*)\s+(?:llim|limos)"),
    ("limo", r"\bllim|\blimo|\bsilt|\bmarg"),
    ("arcilla", r"\bargil|\barcill|\bclay"),
    ("grava", r"\bgrav|\bbolo|\bblocs?\b|\bcodol"),
    ("arena", r"\bsorr|\baren|\bsand"),
)


def _first_material_stem(norm_desc: str) -> str | None:
    """Tipus del PRIMER material que apareix al text normalitzat (o None si no n'hi ha cap)."""
    import re
    best: tuple[int, str] | None = None
    for st, rx in _TYPE_STEMS:
        m = re.search(rx, norm_desc)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), st)
    return best[1] if best else None


def detect_soil_type(description: str) -> str:
    """Tipus de sòl d'una descripció litològica (ca/es) — UN SOL classificador (P6, 2026-09-07).

    Fins ara aquesta funció tenia el seu propi vocabulari (només català, sense accents normalitzats): «Arcilla limosa
    y arenosa con algunas gravas» sortia `grava` (per «grav»), «Rebliment antròpic» i «Lutites, substrat» sortien
    `granular`, «Arcillas arenosas» `granular`. Ara delega a `geotech_criteria._classify` (el criteri que ja decideix
    γ/c/φ/E i el tipus sísmic), amb `lith_flags` (senyals ca/es sense accents) i `is_rock`, i tradueix la classe al
    vocabulari del wizard: `rock | grava | arena | arena_limosa | limo | arcilla | granular`.

    Regles:
      - roca (`is_rock`: lutites, gresos/areniscas, substrat/sustrato, bretxes…; margues toves NO) → `rock`
      - argila (arcilla/argila com a material principal) → `arcilla`
      - transicional (llims; sorres/arenes argiloses o llimoses) → `limo` o `arena_limosa` segons el primer material
      - grava / bolos → `grava`; sorra / arena → `arena`
      - rebliment / terra vegetal → el material del rebliment si es diu («Sorres argiloses de rebliment» → `arena`),
        si no `granular` (la classe «rebliment» la posen els senyals, no el tipus)
      - descripció buida o sense cap material → `granular` (defecte de sempre)
    """
    from .geotech_criteria import _classify, _norm, lith_flags

    raw = description or ""
    norm = _norm(raw)
    if not norm.strip():
        return "granular"
    rock = is_rock(0, raw)
    flags = lith_flags(raw)
    guess = _first_material_stem(norm)
    klass = _classify(guess or "granular", flags, rock)
    if klass == "roca":
        return "rock"
    if klass == "argila":
        return "arcilla"
    if klass == "grava":
        return "grava"
    if klass == "sorra":
        return "arena"
    if klass == "transicional":
        if guess in ("limo", "arena_limosa"):
            return guess
        return "arena_limosa" if flags["sorra"] else "limo"
    # rebliment / vegetal
    return guess or "granular"


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


# === Robertson (1983) N → qc conversion ===

ROBERTSON_QC_RATIO = {
    "grava": 8.0,
    "arena": 4.5,
    "granular": 4.5,
    "arena_limosa": 3.5,
    "limo": 2.5,
    "cohesive": 2.5,
    "arcilla": 1.5,
}


def nb_to_qc(nb: float, soil_type: str = "granular") -> float:
    """
    Convert Nb (SPT blow count) to cone resistance qc (kg/cm²).

    Uses Robertson (1983) empirical ratios qc/N for different soil types.

    Args:
        nb: SPT/Borrows N value
        soil_type: Soil classification

    Returns:
        qc in kg/cm²
    """
    ratio = ROBERTSON_QC_RATIO.get(soil_type, 4.5)
    return nb * ratio


# ============================================================================
# Crespo Villalaz & Hunt correlations (cohesive soils)
#
# Source: Carlos Crespo Villalaz, "Mecánica de suelos y cimentaciones",
#         Limusa 5ª ed. (2004), Cap. 20 / Cap. 33.
# Research notes + cross-check with González de Vallejo, Jiménez Salas, Calavera:
#         docs/RECERCA-PRACTICA-GEOTECNICA-ESPANYA.md § 9 (apèndix).
#
# Status (2026-04-17): helpers only — NOT yet wired into pipeline. The current
# `nspt_to_phi()` uses CTE 4.1 which over-reports phi for cohesives by ~+28%
# (Linyola). Wiring is blocked on G.2b (Schmertmann-(n) design for silts/llims,
# which Eva actually uses) and G.2c (regression check on 7 reference projects).
# ============================================================================

# Consistency class labels. Keys are internal snake_case identifiers;
# values are (spanish, catalan) display names. Catalan uses feminine agreement
# because "consistència" is feminine; mirrors Eva's usage in G3DT reports.
CONSISTENCY_LABELS: dict[str, tuple[str, str]] = {
    "muy_blanda": ("muy blanda",  "molt tova"),
    "blanda":     ("blanda",      "tova"),
    "media":      ("media",       "mitjana"),
    "plastico":   ("plástico",    "plàstica"),
    "firme":      ("firme",       "ferma"),
    "muy_firme":  ("muy firme",   "molt ferma"),
    "dura":       ("dura",        "dura"),
}

# Crespo Villalaz main table (§9.1 of research doc) — COHESIVE SOILS.
# Rows: (N_min, N_max, consistency_key, qu_range_kgcm2, c_range_kgcm2, phi_range_deg)
# Consistency_key resolves through CONSISTENCY_LABELS for Spanish/Catalan display.
# N_max is exclusive at the top of each band (so N=2 hits "blanda", not "muy_blanda").
_CRESPO_COHESIVE_TABLE: list[tuple[float, float, str, tuple[float, float], tuple[float, float], tuple[float, float]]] = [
    (0.0,   2.0,  "muy_blanda", (0.00, 0.25), (0.000, 0.125), (0.0,  0.0)),
    (2.0,   4.0,  "blanda",     (0.25, 0.50), (0.125, 0.250), (0.0,  5.0)),
    (4.0,   8.0,  "media",      (0.50, 1.00), (0.250, 0.500), (5.0,  10.0)),
    (8.0,   15.0, "firme",      (1.00, 2.00), (0.500, 1.000), (10.0, 15.0)),
    (15.0,  30.0, "muy_firme",  (2.00, 4.00), (1.000, 2.000), (15.0, 20.0)),
    (30.0,  1e9,  "dura",       (4.00, 1e9),  (2.000, 1e9),   (20.0, 25.0)),
]

# Hunt's consistency table (§9.2 of research doc) — reproduced in Crespo.
# Rows: (qu_min_kgcm2, qu_max_kgcm2, consistency_key, c_range, phi_range_deg)
# Same consistency ladder as Crespo but derived from qu (unconfined compressive
# strength) rather than N. Used when a lab qu test is available.
_HUNT_CONSISTENCY_TABLE: list[tuple[float, float, str, tuple[float, float], tuple[float, float]]] = [
    (0.00, 0.25, "muy_blanda", (0.000, 0.125), (0.0,  0.0)),
    (0.25, 0.50, "blanda",     (0.125, 0.250), (0.0,  4.0)),
    (0.50, 1.00, "plastico",   (0.250, 0.500), (4.0,  8.0)),
    (1.00, 2.00, "firme",      (0.500, 1.000), (8.0,  12.0)),
    (2.00, 4.00, "muy_firme",  (1.000, 2.000), (12.0, 18.0)),
    (4.00, 1e9,  "dura",       (2.000, 1e9),   (18.0, 25.0)),
]


def consistency_label(key: str, lang: str = "ca") -> str:
    """Return the Spanish ("es") or Catalan ("ca", default) display name for a
    consistency key. Unknown keys round-trip as-is."""
    entry = CONSISTENCY_LABELS.get(key)
    if not entry:
        return key
    return entry[1] if lang == "ca" else entry[0]


def _lookup_crespo_row(nspt: float) -> tuple[float, float, str, tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Internal: find the Crespo row matching this N. Negative/zero N → muy_blanda."""
    n = max(0.0, float(nspt))
    for row in _CRESPO_COHESIVE_TABLE:
        n_lo, n_hi = row[0], row[1]
        # Inclusive on lower bound, exclusive on upper (so N=2 → blanda band).
        if n_lo <= n < n_hi:
            return row
    return _CRESPO_COHESIVE_TABLE[-1]  # dura (fallback)


def crespo_phi_cohesive(nspt: float) -> float:
    """Estimate friction angle φ (°) for a COHESIVE soil from SPT-N using Crespo
    Villalaz's table (§9.1 of the research doc).

    Returns the **midpoint** of the φ range for the matched consistency band.
    For pure clays; for arcilla limosa / llim, subtract 2-5° (Crespo's own note).
    Eva's practice for silts/silty-clays is Schmertmann-(n) — pending G.2b.

    Args:
        nspt: SPT N (blows/ft). Nb (DPSH-derived) can be passed directly since
              the table is published in SPT units and Nb ≈ N for the cohesive
              ranges where this table applies.

    Returns:
        Friction angle in degrees. Midpoint of the consistency band.
    """
    row = _lookup_crespo_row(nspt)
    phi_lo, phi_hi = row[5]
    return (phi_lo + phi_hi) / 2.0


def crespo_phi_range(nspt: float) -> tuple[float, float]:
    """Return the (low, high) φ range for the Crespo consistency band matching N."""
    return _lookup_crespo_row(nspt)[5]


def crespo_consistency(nspt: float, lang: str = "key") -> str:
    """Return the consistency class for N.

    Args:
        nspt: SPT N (blows/ft) or Nb (DPSH).
        lang: "key" (default) → internal snake_case ("muy_blanda", "blanda", ...).
              "es" → Spanish display ("muy blanda").
              "ca" → Catalan display ("molt tova").

    Keeping "key" as the default makes this function stable as a classifier
    (e.g. for unit tests / programmatic branching). UI callers should pass
    lang="ca" or "es" explicitly.
    """
    key = _lookup_crespo_row(nspt)[2]
    if lang == "key":
        return key
    return consistency_label(key, lang)


def hunt_cohesion_from_nspt(nspt: float) -> float:
    """Estimate cohesion c (kg/cm²) for a COHESIVE soil from SPT-N using the
    Crespo consistency table (§9.1, c = qu / 2).

    Returns the **midpoint** of the c range for the matched band. Use this
    for argiles (clays); llims typically sit on the lower half of each band.

    Args:
        nspt: SPT N (blows/ft) or Nb (DPSH).

    Returns:
        Cohesion in kg/cm². Midpoint of the band.
    """
    row = _lookup_crespo_row(nspt)
    c_lo, c_hi = row[4]
    # For the "dura" open-ended band we cap at 2.0 × 1.5 = 3.0 to avoid inf.
    if c_hi >= 1e8:
        return max(c_lo, 2.5)
    return (c_lo + c_hi) / 2.0


# =============================================================================
# Crespo Villalaz Tabla 11.2 — SPT→φ for GRANULAR soils (Finding #10 anchor)
# =============================================================================
#
# Source: Crespo Villalaz (2004), "Mecánica de suelos y cimentaciones", 5a ed.,
# Ch.11 "Esfuerzo de corte en los suelos", p.175, Tabla 11.2 "En arenas".
# Archived: docs/research/books/Crespo-Villalaz-Mecanica-de-suelos-y-cimentaciones.pdf
#
# This is the sub-table behind Eva's recurring φ=28° anchor for transitional
# materials (llim argilós, sorres argiloses) — it's the "muy floja" bottom-row
# value. Eva treats any weak/transitional silty-sandy material as muy-floja-sand
# behaviour and uses the 28° floor. Confirmed by the Spt-correlacions.doc she
# shared (2026-02-26), which bundles Crespo's correlations with Schmertmann.
#
# Rows: (N_min_inclusive, N_max_exclusive, density_key, Dr_range_%, phi_range_°, E_range_kgcm2)
# Footnote (Crespo p.174): +5° to φ if gravel/sand has <5% fine-sand-or-silt.
# Footnote (Crespo p.175): preliminary estimates without lab:
#   limo → φ=20°; arena húmeda → 10-15°; arena seca → 30-34°;
#   grava/arena cementadas (húmedas) → 34° with c=0.25 kg/cm².
#
_CRESPO_GRANULAR_TABLE: list[tuple[float, float, str, tuple[float, float], tuple[float, float], tuple[float, float]]] = [
    (0.0,   5.0,  "muy_floja",  ( 0.0, 15.0),  (28.0, 28.0),  ( 100.0,  100.0)),
    (5.0,   11.0, "floja",      (16.0, 35.0),  (28.0, 30.0),  ( 100.0,  250.0)),
    (11.0,  31.0, "media",      (36.0, 65.0),  (30.0, 36.0),  ( 250.0,  500.0)),
    (31.0,  51.0, "densa",      (66.0, 85.0),  (36.0, 41.0),  ( 500.0, 1000.0)),
    (51.0,  1e9,  "muy_densa",  (86.0, 100.0), (41.0, 45.0),  (1000.0, 2000.0)),
]

# Preliminary φ floors (Crespo p.175 bottom paragraph). Used when N is unknown
# or the material is labelled directly (field ID without DPSH/SPT).
CRESPO_PHI_ESTIMATES_NO_LAB: dict[str, float] = {
    "limo":            20.0,  # generic silt
    "arena_humeda":    12.5,  # wet sand, midpoint of 10-15
    "arena_seca":      32.0,  # dry sand, midpoint of 30-34
    "grava_cementada": 34.0,  # cemented gravel/sand (also → c=0.25 kg/cm²)
    "transicional":    28.0,  # Eva's anchor for llim argilós / sorres argiloses
}

# Cohesion for cemented gravel/sand per Crespo p.175 footnote
CRESPO_C_CEMENTED_GRAVEL_KGCM2: float = 0.25

# Accepted fine_fraction labels for `crespo_phi_granular`. Kept as a module-level
# frozenset so typos ("transitonal", "Clean") raise instead of silently falling
# through to the tabulated midpoint and masking Eva's 28° anchor rule.
_VALID_FINE_FRACTION = frozenset({"clean", "normal", "transitional"})


def _lookup_crespo_granular_row(nspt: float) -> tuple[float, float, str, tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Internal: find the Crespo Tabla 11.2 row matching this N.
    Negative/zero N → muy_floja (safest, most conservative for design)."""
    n = max(0.0, float(nspt))
    for row in _CRESPO_GRANULAR_TABLE:
        n_lo, n_hi = row[0], row[1]
        if n_lo <= n < n_hi:
            return row
    return _CRESPO_GRANULAR_TABLE[-1]  # muy_densa


def crespo_phi_granular(nspt: float, fine_fraction: str = "normal") -> float:
    """φ (°) for granular soils from Crespo Tabla 11.2 (p.175).

    Returns the midpoint of the matched density band. For N<5 (muy_floja),
    the band is collapsed to the single anchor 28° per Crespo's published value.

    Args:
        nspt: SPT N (blows/ft) corrected for depth. Pass Nb for DPSH-based calls.
        fine_fraction: "clean" (<5% fines, Crespo p.174 bonus +5°),
                       "normal" (default — use tabulated range),
                       "transitional" (clamp to 28° regardless of N —
                       Eva's rule for llim argilós / sorres argiloses).

    Returns:
        Friction angle in degrees.

    Raises:
        ValueError: if `fine_fraction` is not one of {"clean", "normal",
            "transitional"}. Silent fallthrough on typos (e.g. "transitonal",
            "Clean") would otherwise return the tabulated midpoint instead of
            Eva's 28° anchor for transitional materials.
    """
    if fine_fraction not in _VALID_FINE_FRACTION:
        raise ValueError(
            f"fine_fraction must be one of {sorted(_VALID_FINE_FRACTION)}, "
            f"got {fine_fraction!r}"
        )
    if fine_fraction == "transitional":
        return CRESPO_PHI_ESTIMATES_NO_LAB["transicional"]
    row = _lookup_crespo_granular_row(nspt)
    phi_lo, phi_hi = row[4]
    phi_mid = (phi_lo + phi_hi) / 2.0
    if fine_fraction == "clean":
        # Cap at 45° — physical upper bound for cohesionless soils, and the
        # conventional ceiling in CTE / Crespo practice. Without this, very
        # dense clean sands (N≥51, base φ=43°) would read 48° after the bonus.
        phi_mid = min(45.0, phi_mid + 5.0)
    return phi_mid


def crespo_phi_granular_range(nspt: float) -> tuple[float, float]:
    """Return the (low, high) φ range for the Crespo Tabla 11.2 band matching N."""
    return _lookup_crespo_granular_row(nspt)[4]


def crespo_density_label(nspt: float, lang: str = "key") -> str:
    """Return the relative-density class for N per Crespo Tabla 11.2.

    Args:
        nspt: SPT N (blows/ft) or Nb (DPSH).
        lang: "key" (internal snake_case) | "es" (Spanish) | "ca" (Catalan).
    """
    key = _lookup_crespo_granular_row(nspt)[2]
    if lang == "key":
        return key
    # Simple Spanish/Catalan display names — kept inline to avoid cross-module deps.
    display = {
        "muy_floja":  ("muy floja",  "molt fluixa"),
        "floja":      ("floja",      "fluixa"),
        "media":      ("media",      "mitjana"),
        "densa":      ("densa",      "densa"),
        "muy_densa":  ("muy densa",  "molt densa"),
    }
    entry = display.get(key)
    if not entry:
        return key
    return entry[1] if lang == "ca" else entry[0]


def _interp_table(n: float, table: list[tuple[float, float]]) -> float:
    """Linear interpolation over an ascending (N, φ) lookup. Edge-clamped."""
    if n <= table[0][0]:
        return table[0][1]
    if n >= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        n_lo, phi_lo = table[i]
        n_hi, phi_hi = table[i + 1]
        if n_lo <= n <= n_hi:
            frac = (n - n_lo) / (n_hi - n_lo)
            return phi_lo + frac * (phi_hi - phi_lo)
    return table[-1][1]


# Meyerhof (1957) curves — digitized from a published reproduction of the
# SPT-N↔φ chart (see image119 reference in docs/DESIGN-SCHMERTMANN-N.md).
# The chart shows three curves labeled:
#   1. Peck-Hanson-Thornburn (baseline)
#   2. Meyerhof <5% fine-sand + silt   (clean sand)
#   3. Meyerhof >5% fine-sand + silt   (silty sand)
# These map loosely to Eva's Schmertmann-1975 n-factors:
#   n=2.5 (sorres lleugerament llimoses)  ≈ Meyerhof <5%
#   n=2.0 (sorres llimoses)               ≈ Meyerhof >5%
#   n=1.25 (llims sorrencs)               → extrapolate: Meyerhof >5% minus ~3°
# Tabulated values are ±1° accurate reads from the published chart.

_PECK_HANSON_THORNBURN: list[tuple[float, float]] = [
    (5, 28.5), (10, 30.5), (15, 32.0), (20, 33.5), (25, 35.0),
    (30, 36.0), (40, 38.0), (50, 40.0), (60, 41.5),
]

_MEYERHOF_CLEAN_SAND: list[tuple[float, float]] = [   # <5% fines → ≈ n=2.5
    (5, 29.5), (10, 32.5), (15, 34.5), (20, 36.0), (25, 37.5),
    (30, 39.0), (40, 41.0), (50, 42.5), (60, 44.0),
]

_MEYERHOF_SILTY_SAND: list[tuple[float, float]] = [   # >5% fines → ≈ n=2.0
    (5, 26.5), (10, 29.0), (15, 30.0), (20, 31.0), (25, 32.0),
    (30, 33.0), (40, 35.0), (50, 37.0), (60, 38.0),
]


def peck_hanson_thornburn_phi(nspt: float) -> float:
    """φ (°) for granular soils via the Peck-Hanson-Thornburn curve.
    Close to but distinct from the Peck (1953) algebraic formula
    φ = 27.1 + 0.30N - 0.00054N² that CTE 4.1 uses; use this when the curve
    value rather than the formula is desired (e.g. for consistency with
    figures in published Spanish geotech practice)."""
    return _interp_table(nspt, _PECK_HANSON_THORNBURN)


def meyerhof_phi_clean_sand(nspt: float) -> float:
    """φ (°) for clean / slightly-silty sands (<5% fines by Meyerhof's class).
    Approximates Eva's Schmertmann-1975 n=2.5 case — "sorres lleugerament llimoses".
    Published curve; ±1° accurate."""
    return _interp_table(nspt, _MEYERHOF_CLEAN_SAND)


def meyerhof_phi_silty_sand(nspt: float) -> float:
    """φ (°) for silty sands (>5% fines by Meyerhof's class).
    Approximates Eva's Schmertmann-1975 n=2.0 case — "sorres llimoses".
    Published curve; ±1° accurate."""
    return _interp_table(nspt, _MEYERHOF_SILTY_SAND)


def phi_from_nspt_silty_empirical(nspt: float, n_factor: float) -> float:
    """φ (°) for sandy/silty soils — EMPIRICAL calibration, not a formal method.

    **Important semantic correction (2026-04-17):** originally named
    `schmertmann_n_phi` under the assumption that Eva's n-factor
    (2.5 / 2.0 / 1.25 from her Spt-correlacions.doc) was an SPT→φ correlation.
    After reading Eva's actual reports, we now know:
        - Eva's n is an **SPT→qc conversion factor** (use `nspt_to_qc` for that).
        - Eva gets φ from **Crespo Villalaz tables** (see `crespo_phi_cohesive`
          and the cite in every informe: *"que s'estableixen en el llibre
          «Mecànica de suelos y cimentaciones» de l'autor Carlos Crespo
          Villalaz, a partir de la resistència dels materials"*).

    This helper survives as an **empirical fit** — it maps Eva's n-factor
    labels onto published Meyerhof 1957 SPT-φ curves and happens to reproduce
    Eva's φ for Linyola (Nb=22.6, n=1.25 → 28°). The curves and calibration
    are real, the **attribution to Schmertmann is wrong**; keep this function
    only as long as it's useful, and prefer Crespo tables once we confirm
    which Crespo subtable Eva uses for llims argilosos (task G.3).

        n ≥ 2.5   → Meyerhof clean-sand curve (<5% fines)
        n = 2.0   → Meyerhof silty-sand curve (>5% fines)
        n = 1.25  → Meyerhof silty-sand curve minus 3° (extrapolation)
        1.25 < n < 2.5  → linear interpolation between the two nearest anchors

    Args:
        nspt: SPT N (blows/ft) or Nb (DPSH).
        n_factor: Eva's grain-size label — NOT used here as Schmertmann's
            formal qc/N ratio (that's `nspt_to_qc`), just as a curve selector.

    Returns:
        Friction angle in degrees.
    """
    # Clamp n to the useful range
    n = max(1.0, min(3.0, float(n_factor)))

    if n >= 2.5:
        return meyerhof_phi_clean_sand(nspt)
    if n >= 2.0:
        # Interpolate between clean (n=2.5) and silty (n=2.0)
        clean = meyerhof_phi_clean_sand(nspt)
        silty = meyerhof_phi_silty_sand(nspt)
        frac = (2.5 - n) / 0.5
        return silty + (1 - frac) * (clean - silty)
    if n >= 1.25:
        # Interpolate between silty (n=2.0) and sandy-silts (n=1.25, silty - 3°)
        silty = meyerhof_phi_silty_sand(nspt)
        sandy_silt = silty - 3.0
        frac = (2.0 - n) / 0.75
        return silty + frac * (sandy_silt - silty)
    # n < 1.25 — off-chart. Apply progressive reduction below sandy_silt.
    silty = meyerhof_phi_silty_sand(nspt)
    sandy_silt = silty - 3.0
    extra = (1.25 - n) * 4.0   # 4° per unit-n below 1.25
    return max(0.0, sandy_silt - extra)


def hunt_cohesion_from_qu(qu_kg_cm2: float) -> float:
    """Estimate cohesion c (kg/cm²) from unconfined compressive strength qu,
    using the Hunt table (§9.2). c = qu / 2 in the classical derivation, but
    this function returns the band-midpoint so bands and Crespo/Hunt stay
    consistent.

    Args:
        qu_kg_cm2: Unconfined compressive strength (kg/cm²).

    Returns:
        Cohesion in kg/cm². Midpoint of the band.
    """
    q = max(0.0, float(qu_kg_cm2))
    for row in _HUNT_CONSISTENCY_TABLE:
        q_lo, q_hi = row[0], row[1]
        if q_lo <= q < q_hi:
            c_lo, c_hi = row[3]
            if c_hi >= 1e8:
                return max(c_lo, 2.5)
            return (c_lo + c_hi) / 2.0
    # Shouldn't reach here (dura has open upper bound).
    row = _HUNT_CONSISTENCY_TABLE[-1]
    c_lo, _ = row[3]
    return max(c_lo, 2.5)


# ============================================================================
# Schmertmann N→qc→E chain (from Eva's report text, verified 2026-04-17)
#
# Every Eva informe contains this passage verbatim:
#   "E = mòdul de deformació definit per Schmertmann, que s'obté de multiplicar
#    2.5 en el cas de sabates aïllades i 3.5 en el cas de corregudes, pel colpeig
#    del penetròmetre estàtic. Aquest colpeig s'obté de la relació entre N (Nspt),
#    amb uns factors de conversió establerts per cada un dels diferents tipus de
#    material."
#
# Decoded into formulas:
#     qc = n_factor × N         (n from grain-size class, table in Spt-correlacions.doc)
#     E  = shape_factor × qc    (shape_factor: 2.5 isolated footing, 3.5 strip footing)
#
# The n-factor classes Eva uses:
#     n = 2.5   sorres lleugerament llimoses (slightly silty sands)
#     n = 2.0   sorres llimoses                (silty sands)
#     n = 1.25  llims sorrencs                 (sandy silts)
#
# Cross-checks with Schmertmann (1970) Fig. 5 "E_s ≈ 2·qc" band and the
# standard qc/N literature: typical qc/N ratios are ~4-5 for clean sands,
# ~2-3 for silty sands, ~1 for clays. Eva's n labels sit in the same range.
# ============================================================================


# Shape factor for Schmertmann's E = k · qc formula.
SCHMERTMANN_E_ISOLATED_FACTOR: float = 2.5   # sabata aïllada (square/circular)
SCHMERTMANN_E_STRIP_FACTOR: float = 3.5      # sabata correguda (strip footing)


def nspt_to_qc(nspt: float, n_factor: float) -> float:
    """SPT → static cone qc (kg/cm²) via Eva's grain-size conversion factor.

    `qc = n_factor × N`

    Args:
        nspt: SPT N (blows/ft) or Nb (DPSH) — Eva uses raw N (not N60/N1,60)
              in this correlation per her Spt-correlacions.doc.
        n_factor: Eva's conversion factor by soil class:
            2.5 for slightly silty sands,
            2.0 for silty sands,
            1.25 for sandy silts,
            intermediate values are acceptable (linear by construction).

    Returns:
        qc in kg/cm². (Eva's settlement workflow expects this unit.)
    """
    n = max(0.0, float(nspt))
    return n * float(n_factor)


def schmertmann_E_from_qc(qc_kg_cm2: float, footing_shape: str = "isolated") -> float:
    """Schmertmann E (kg/cm²) from static cone qc per Eva's report text.

        E = 2.5 × qc  for  footing_shape == "isolated" (sabata aïllada, square)
        E = 3.5 × qc  for  footing_shape == "strip"    (sabata correguda)

    Args:
        qc_kg_cm2: Static cone bearing from `nspt_to_qc` or direct CPT.
        footing_shape: "isolated" (default) or "strip". Unknown values fall
            back to "isolated" with a warning logged to stderr.

    Returns:
        E in kg/cm² suitable for Schmertmann settlement Iz integration.
    """
    shape = (footing_shape or "isolated").lower()
    if shape in ("strip", "corregudes", "corrida", "continuous"):
        factor = SCHMERTMANN_E_STRIP_FACTOR
    elif shape in ("isolated", "aillada", "aïllada", "aislada", "square", "circular"):
        factor = SCHMERTMANN_E_ISOLATED_FACTOR
    else:
        import sys
        print(f"[cte_geomech] Unknown footing_shape={footing_shape!r}; "
              f"using isolated factor {SCHMERTMANN_E_ISOLATED_FACTOR}",
              file=sys.stderr)
        factor = SCHMERTMANN_E_ISOLATED_FACTOR
    return max(0.0, float(qc_kg_cm2)) * factor


def schmertmann_E_from_nspt(
    nspt: float,
    n_factor: float,
    footing_shape: str = "isolated",
) -> float:
    """Convenience: N → qc → E, chaining `nspt_to_qc` + `schmertmann_E_from_qc`.

    This is the full Schmertmann E-from-SPT chain Eva's reports describe.
    """
    return schmertmann_E_from_qc(nspt_to_qc(nspt, n_factor), footing_shape)


# --- Deprecated alias (keeps old tests green while the ecosystem migrates) ---
def schmertmann_n_phi(nspt: float, n_factor: float) -> float:
    """Deprecated alias. See `phi_from_nspt_silty_empirical` for why this was
    renamed. Will be removed once all call sites are updated."""
    return phi_from_nspt_silty_empirical(nspt, n_factor)
