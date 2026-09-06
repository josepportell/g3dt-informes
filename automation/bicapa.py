"""Bicapa (two-layer) bearing-capacity methods.

Source: **J. M. Rodríguez Ortiz, "Curso aplicado de cimentaciones"**,
Capítulo 2 §6.1, Figs. 2.9–2.18, pp. 49–54. Full PDF archived at
`docs/research/books/Rodriguez-Ortiz-Curso-aplicado-de-cimentaciones.pdf`.

Eva's reports (e.g. Alcoletge) explicitly cite this book as the reference
for bearing-capacity calculations on heterogeneous (bicapa) profiles. See
`docs/METODOLOGIA-EVA.md` §1.2, §6.2.

**Scope of this module** (2026-04-17):

1. `select_bearing_layer(layers)` — Eva's "skip-soft-top" rule. When the
   surface layer is weak enough to be excavated/anivellat, she discards it
   and computes Qa on the competent layer alone. This is her most common
   real-world simplification.

2. `bicapa_qh_fig29(q_h1, q_h2, t, B, case)` — Fig. 2.9 interpolation for
   the case where both layers contribute to the failure surface. Two
   variant formulas (case "a" and "b") published in the book.

3. `two_clay_layers_nm(c2_c1, B_H, shape)` — Vesic (1970) Cuadro 2.4 for
   the soft-over-stiff clay case (§6.1.a Case I).

4. `two_clay_layers_qh_case2(c1, c2, B, L, H)` — Brown & Meyerhof (1969)
   for the stiff-over-soft clay case (§6.1.a Case II).

5. `sand_over_soft_clay_qh(q_hc, phi1, B, H)` — Tcheng (1957) / Vesic (1970)
   for sand over soft clay (§6.1.c).

**Not implemented yet** (requires chart digitization):
- §6.1.b Hanna 1981 for two granular layers — K_s chart (Fig. 2.12).
- §6.1.c Mandel & Salençon N'γ chart (Fig. 2.14).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Competent-layer selection (Eva's skip-soft-top pattern)
# ---------------------------------------------------------------------------

@dataclass
class SoilLayer:
    """A single soil stratum for bicapa analysis.

    Attributes are the minimum set Eva uses in her informes:
        depth_top, depth_bottom: metres below ground surface
        soil_type:  'granular' | 'cohesive' | 'rock' (used for classifier routing)
        nspt:       SPT N or Nb (pass what you have; caller's responsibility)
        gamma:      unit weight in gr/cm³
        cohesion:   c in kg/cm² (effective c' for long-term analysis)
        phi:        φ in degrees
        E:          E in kg/cm²
        description:free-text lithology (used for "rellim/rebliment" detection)
    """
    depth_top: float
    depth_bottom: float
    soil_type: str
    nspt: float | None = None
    gamma: float = 2.0
    cohesion: float = 0.0
    phi: float = 30.0
    E: float = 200.0
    description: str = ""

    @property
    def thickness(self) -> float:
        return self.depth_bottom - self.depth_top


# Keyword markers Eva uses for soft surface layers she discards.
_WEAK_TOP_KEYWORDS = (
    "rebliment", "relleno", "rebliments", "rellenos",
    "terra vegetal", "tierra vegetal", "terreny vegetal", "sòl vegetal", "sòls vegetals",
    "suelo vegetal", "capa vegetal", "sòls superficials", "suelos superficiales",
    "alterat superficial", "alterado superficial",
    "sòl natural feble", "suelo natural débil",
)


def select_bearing_layer(
    layers: list[SoilLayer],
    *,
    foundation_depth: float = 0.8,
    weak_layer_nspt_threshold: float = 5,
    weak_layer_phi_threshold: float = 25.0,
) -> tuple[SoilLayer, int]:
    """Pick the competent bearing layer following Eva's rule.

    Eva's practice (from `METODOLOGIA-EVA.md` §5.9 + Alcoletge informe):
    when the surface layer is either (a) explicitly labelled as fill /
    rebliment / tierra vegetal, or (b) has very low strength (low N or low
    φ), she assumes it will be sanejada/excavada down to the next competent
    layer and computes Qa on THAT layer alone. Single-layer Terzaghi on
    the competent stratum then matches the bicapa-average within noise.

    Args:
        layers: list of soil layers, ordered from shallowest to deepest.
        foundation_depth: Df in metres. Layers ending above this depth are
            definitively out of the failure zone.
        weak_layer_nspt_threshold: treat a layer as weak if its nspt is
            strictly less than this (and not None).
        weak_layer_phi_threshold: treat a layer as weak if its phi is
            strictly less than this.

    Returns:
        (bearing_layer, index). Index is 0-based within the input list.

    Raises:
        ValueError: if no competent layer is found.
    """
    if not layers:
        raise ValueError("no layers provided")

    for idx, layer in enumerate(layers):
        # Skip if the whole layer is above foundation depth — it doesn't
        # carry any load regardless of its properties.
        if layer.depth_bottom <= foundation_depth:
            continue

        # Skip if the layer is explicitly labelled as fill / topsoil.
        desc = (layer.description or "").lower()
        if any(kw in desc for kw in _WEAK_TOP_KEYWORDS):
            continue

        # Skip if the layer is too weak (low N AND low phi AND low cohesion).
        too_weak_nspt = (
            layer.nspt is not None and layer.nspt < weak_layer_nspt_threshold
        )
        too_weak_phi = layer.phi < weak_layer_phi_threshold
        too_weak_cohesion = layer.cohesion < 0.05
        if too_weak_nspt and too_weak_phi and too_weak_cohesion:
            continue

        return layer, idx

    raise ValueError(
        "no competent bearing layer found — all layers are weak or above Df"
    )


# ---------------------------------------------------------------------------
# Fig. 2.9 general interpolation (two published variants, "a" and "b")
# ---------------------------------------------------------------------------

def bicapa_qh_fig29(
    q_h1: float,
    q_h2: float,
    t: float,
    B: float,
    case: Literal["a", "b"] = "a",
) -> float:
    """General bicapa q_h per Rodríguez Ortiz Fig. 2.9.

    Both variants assume q_h1 > q_h2 (top stronger, bottom weaker — the
    common Eva case: competent bearing layer over soft material, or
    sanejat / fill scenarios). If the inputs violate this assumption the
    formula is still applied but the result is less meaningful; caller
    should check.

    Case "a" (more conservative — preferred for design-level Qa):
        t/B > 0.7:  q_h = q_h2
        t/B ≤ 0.7:  q_h = q_h1 − (q_h1 − q_h2) / 0.7 × t/B

    Case "b" (less conservative):
        t/B ≤ 0.2:        q_h = q_h2
        0.2 < t/B < 1.0:  q_h = q_h2 − (q_h1 − q_h2) / 0.8 × (t/B − 0.2)
        t/B ≥ 1.0:        q_h = q_h1

    Args:
        q_h1: Hipothetical q_h if the entire terrain were the upper (stronger) layer.
        q_h2: Hipothetical q_h if the entire terrain were the lower (weaker) layer.
        t: thickness of the upper layer below the footing (metres).
        B: footing width (metres).
        case: "a" (Rodríguez Ortiz preferred) or "b" (alternate interpolation).

    Returns:
        Combined q_h in the same units as q_h1, q_h2 (typically kg/cm²).
    """
    if B <= 0:
        raise ValueError("B must be > 0")
    if t < 0:
        raise ValueError("t must be >= 0")

    ratio = t / B

    if case == "a":
        if ratio > 0.7:
            return q_h2
        return q_h1 - (q_h1 - q_h2) / 0.7 * ratio

    if case == "b":
        if ratio <= 0.2:
            return q_h2
        if ratio < 1.0:
            return q_h2 - (q_h1 - q_h2) / 0.8 * (ratio - 0.2)
        return q_h1

    raise ValueError(f"unknown case {case!r}; use 'a' or 'b'")


# ---------------------------------------------------------------------------
# §6.1.a Case I — soft clay over stiff clay (Vesic 1970 Cuadro 2.4)
# ---------------------------------------------------------------------------

# Vesic (1970) N_m factor, Cuadro 2.4 of Rodríguez Ortiz.
# Rows: c2/c1 (stiffness ratio), Columns: B/H (geometry).
# Values are published in the book. Homogeneous clay (c2/c1 = 1.0) gives
# 5.14 / 6.17 (plane strain / circular), matching the classical solution.

# Rectangular footing, L/B ≤ 5  (Cuadro 2.4.a)
_VESIC_NM_RECT: dict[float, dict[float, float]] = {
    #  B/H:   2      4      6      8     10     20    ∞
    1.0:   {2: 5.14, 4: 5.14, 6: 5.14, 8: 5.14, 10: 5.14, 20: 5.14, float('inf'): 5.14},
    1.5:   {2: 5.14, 4: 5.31, 6: 5.45, 8: 5.59, 10: 5.70, 20: 6.14, float('inf'): 7.71},
    2.0:   {2: 5.14, 4: 5.43, 6: 5.69, 8: 5.92, 10: 6.13, 20: 6.95, float('inf'): 10.28},
    3.0:   {2: 5.14, 4: 5.59, 6: 6.00, 8: 6.38, 10: 6.74, 20: 8.16, float('inf'): 15.42},
    4.0:   {2: 5.14, 4: 5.69, 6: 6.21, 8: 6.69, 10: 7.14, 20: 9.02, float('inf'): 20.56},
    5.0:   {2: 5.14, 4: 5.76, 6: 6.35, 8: 6.90, 10: 7.42, 20: 9.66, float('inf'): 25.70},
    10.0:  {2: 5.14, 4: 5.93, 6: 6.69, 8: 7.43, 10: 8.14, 20: 11.40, float('inf'): 51.40},
    float('inf'): {2: 5.14, 4: 6.14, 6: 7.14, 8: 8.14, 10: 9.14, 20: 14.14, float('inf'): float('inf')},
}

# Square or circular footing, L/B = 1  (Cuadro 2.4.b)
_VESIC_NM_SQUARE: dict[float, dict[float, float]] = {
    #  B/H:    4      8     12     16     20     40    ∞
    1.0:   {4: 6.17, 8: 6.17, 12: 6.17, 16: 6.17, 20: 6.17, 40: 6.17, float('inf'): 6.17},
    1.5:   {4: 6.17, 8: 6.34, 12: 6.49, 16: 6.63, 20: 6.76, 40: 7.25, float('inf'): 9.25},
    2.0:   {4: 6.17, 8: 6.46, 12: 6.73, 16: 6.98, 20: 7.20, 40: 8.10, float('inf'): 12.34},
    3.0:   {4: 6.17, 8: 6.63, 12: 7.05, 16: 7.45, 20: 7.82, 40: 9.36, float('inf'): 18.51},
    4.0:   {4: 6.17, 8: 6.73, 12: 7.26, 16: 7.75, 20: 8.23, 40: 10.24, float('inf'): 24.68},
    5.0:   {4: 6.17, 8: 6.80, 12: 7.40, 16: 7.97, 20: 8.51, 40: 10.88, float('inf'): 30.85},
    10.0:  {4: 6.17, 8: 6.96, 12: 7.74, 16: 8.49, 20: 9.22, 40: 12.58, float('inf'): 61.70},
    float('inf'): {4: 6.17, 8: 7.17, 12: 8.17, 16: 9.17, 20: 10.17, 40: 15.17, float('inf'): float('inf')},
}


def _bilinear_lookup(
    table: dict[float, dict[float, float]],
    c2_c1: float,
    B_H: float,
) -> float:
    """Bilinear interpolation over Cuadro 2.4 lookups. Clamps to table edges."""
    row_keys = sorted(table.keys())
    col_keys = sorted(next(iter(table.values())).keys())

    # Clamp
    c2_c1 = max(row_keys[0], min(c2_c1, row_keys[-1]))
    B_H = max(col_keys[0], min(B_H, col_keys[-1]))

    # Find bracketing rows
    r_lo = max(r for r in row_keys if r <= c2_c1)
    r_hi = min(r for r in row_keys if r >= c2_c1)
    c_lo = max(c for c in col_keys if c <= B_H)
    c_hi = min(c for c in col_keys if c >= B_H)

    q11 = table[r_lo][c_lo]
    q12 = table[r_lo][c_hi]
    q21 = table[r_hi][c_lo]
    q22 = table[r_hi][c_hi]

    # Handle inf in B/H column gracefully
    if math.isinf(c_lo) or math.isinf(c_hi) or math.isinf(r_lo) or math.isinf(r_hi):
        # If any corner is inf, pick the nearest non-inf corner
        candidates = [v for v in (q11, q12, q21, q22) if math.isfinite(v)]
        return max(candidates) if candidates else 5.14

    # Linear in c2_c1
    if r_lo == r_hi:
        v_lo, v_hi = q11, q12
    else:
        t = (c2_c1 - r_lo) / (r_hi - r_lo)
        v_lo = q11 + t * (q21 - q11)
        v_hi = q12 + t * (q22 - q12)

    # Linear in B/H
    if c_lo == c_hi:
        return v_lo
    s = (B_H - c_lo) / (c_hi - c_lo)
    return v_lo + s * (v_hi - v_lo)


def two_clay_layers_nm_soft_over_stiff(
    c1: float,
    c2: float,
    B: float,
    L: float,
    H: float,
) -> float:
    """Vesic (1970) modified bearing-capacity factor N_m for the soft-over-stiff
    clay bicapa case (Rodríguez Ortiz §6.1.a Case I).

    Args:
        c1: undrained cohesion of the upper (softer) clay layer, kg/cm².
        c2: undrained cohesion of the lower (stiffer) clay layer, kg/cm².
        B: footing width (metres). For rectangular, shorter side.
        L: footing length (metres). Use L=B for square, or a large value for strip.
        H: thickness of the upper (softer) layer below the footing, metres.

    Returns:
        N_m (dimensionless). Use as q_h = c1 · N_m + q.
    """
    if c1 <= 0 or B <= 0 or H <= 0:
        raise ValueError("c1, B, H must be > 0")

    c2_c1 = c2 / c1
    B_H = B / H

    # Square/circular if L/B ≤ ~1.05, else rectangular
    L_B = L / B
    table = _VESIC_NM_SQUARE if L_B <= 1.05 else _VESIC_NM_RECT

    return _bilinear_lookup(table, c2_c1, B_H)


def two_clay_layers_qh_soft_over_stiff(
    c1: float,
    c2: float,
    B: float,
    L: float,
    H: float,
    q_surcharge: float = 0.0,
) -> float:
    """q_h for soft-over-stiff clay (Case I of §6.1.a).

    q_h = c1 · N_m + q
    """
    N_m = two_clay_layers_nm_soft_over_stiff(c1, c2, B, L, H)
    return c1 * N_m + q_surcharge


# ---------------------------------------------------------------------------
# §6.1.a Case II — stiff clay over soft clay (Brown & Meyerhof 1969)
# ---------------------------------------------------------------------------

def two_clay_layers_qh_stiff_over_soft(
    c1: float,
    c2: float,
    B: float,
    L: float,
    H: float,
    N_c: float = 5.14,
    s_c: float = 1.0,
    q_surcharge: float = 0.0,
) -> float:
    """q_h for stiff-over-soft clay (Case II of §6.1.a), Brown & Meyerhof (1969):

        N_m = 2·(B+L)·H / (B·L)  +  (c2/c1) · s_c · N_c
        q_h = c1 · N_m + q

    Args:
        c1: upper (stiffer) clay c, kg/cm².
        c2: lower (softer) clay c, kg/cm².
        B, L: footing width and length (metres).
        H: thickness of the upper stratum below footing, metres.
        N_c: Terzaghi N_c for φ=0 (5.14 for faja, 6.17 for circular — pass per shape).
        s_c: shape factor (1.0 for strip, ~1.2-1.3 for square; caller's choice).
        q_surcharge: surcharge at footing level, kg/cm² (0 if Df=0).
    """
    if c1 <= 0 or B <= 0 or L <= 0 or H <= 0:
        raise ValueError("c1, B, L, H must be > 0")
    N_m = 2 * (B + L) * H / (B * L) + (c2 / c1) * s_c * N_c
    return c1 * N_m + q_surcharge


# ---------------------------------------------------------------------------
# §6.1.c — sand over soft clay (Tcheng 1957 / Vesic 1970)
# ---------------------------------------------------------------------------

def sand_over_soft_clay_qh_tcheng(
    q_hc: float,
    phi_deg: float,
    B: float,
    H: float,
) -> float:
    """Tcheng (1957) closed-form for a layer of sand over soft clay.

    Formula (Rodríguez Ortiz §6.1.c, p.53):

        q_h = q_hc / [ 1 - (2H/B) · sin(φ) / tan(45° + φ/2) · exp(-(π/2 - φ)·tan(φ)) ]

    Valid for H ≤ 1.5B. For H ≥ 3.5B the soft substrate's influence can
    be ignored (use single-layer sand q_h directly). Interpolate analytically
    for 1.5B < H < 3.5B — caller's responsibility.

    Args:
        q_hc: q_h of the soft lower stratum alone, kg/cm².
        phi_deg: φ of the upper sand layer, degrees.
        B: footing width (metres).
        H: thickness of upper sand below footing, metres.
    """
    if q_hc <= 0 or B <= 0 or H <= 0:
        raise ValueError("q_hc, B, H must be > 0")
    if H > 1.5 * B:
        logger.warning(
            "sand_over_soft_clay_qh_tcheng: H=%.2f > 1.5·B=%.2f — "
            "formula is strictly valid only for H ≤ 1.5·B; result may "
            "under-report strength.", H, 1.5 * B,
        )
    phi = math.radians(phi_deg)
    denom = 1 - (2 * H / B) * math.sin(phi) / math.tan(math.radians(45) + phi / 2) * math.exp(-(math.pi / 2 - phi) * math.tan(phi))
    if denom <= 0:
        # Degenerate case — return q_hc (worst case) with a warning.
        logger.warning(
            "sand_over_soft_clay_qh_tcheng: denominator non-positive "
            "(phi=%.1f, H/B=%.2f); returning q_hc as lower bound.",
            phi_deg, H / B,
        )
        return q_hc
    return q_hc / denom
