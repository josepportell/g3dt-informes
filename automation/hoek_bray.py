#!/usr/bin/env python3
"""
G3DT Hoek & Bray Circular Failure Chart Calculator

Implements the Hoek & Bray (1977/1981) stability charts for circular
failure in homogeneous slopes. Based on Taylor (1937) stability numbers
and the Bishop simplified method.

Charts available:
    Chart 1: Fully drained slope (saturation 0%)
    Charts 2-5: Future — partial saturation (25%, 50%, 75%, 100%)

Method:
    For a given (c, phi, gamma, H, beta), solve for FS such that:
        c / (gamma * H * FS) = Ns(beta, phi_mob)
    where phi_mob = atan(tan(phi) / FS) is the mobilized friction angle.

    The stability number Ns(beta, phi) comes from Taylor's charts for
    circular failure surfaces (toe circles).

Reference:
    - Hoek, E. & Bray, J. (1977/1981). Rock Slope Engineering.
    - Taylor, D.W. (1937). Stability of Earth Slopes. J. Boston Soc. Civ. Eng.
    - Wyllie, D.C. & Mah, C.W. (2004). Rock Slope Engineering, 4th ed.
    - Das, B.M. (2016). Principles of Geotechnical Engineering, 9th ed.

Author: Eficients.cat
Date: 2026-02-25
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class HoekBrayResult:
    """Result of Hoek & Bray circular failure analysis."""
    safety_factor: float         # FS calculated
    slope_angle_deg: float       # beta in degrees
    slope_percent: float         # Original slope in %
    phi_deg: float               # phi (full, not mobilized)
    cohesion_kg_cm2: float       # c
    gamma_g_cm3: float           # gamma
    slope_height_m: float        # H
    saturation_pct: int          # 0, 25, 50, 75, 100
    chart_number: int            # 1-5
    method: str                  # Description string
    fs_required: float           # CTE minimum
    compliant: bool              # FS >= fs_required
    water_detected: bool         # Water in DPSH
    slope_direction: str | None  # Dominant direction


# =============================================================================
# Taylor Stability Numbers for Circular Failure (Toe Circles)
# =============================================================================
#
# Ns = c_d / (gamma * H) where c_d = c / FS
#
# These values are from Taylor (1937), verified against Das (2016),
# Coduto et al. (2011), and Wyllie & Mah (2004).
#
# For phi >= beta, the slope is stable on friction alone (Ns -> 0).
#
# Grid: beta (rows) x phi_mobilized (columns)
# beta in degrees, phi in degrees, Ns dimensionless

_TAYLOR_BETA = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90]

_TAYLOR_PHI = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45]

# Ns(beta, phi) — stability number for circular failure
# Each row is a beta angle, each column is a phi angle
# Values from published geotechnical tables (Taylor 1937, Das 2016)
_TAYLOR_NS: list[list[float]] = [
    # phi:  0      5      10     15     20     25     30     35     40     45
    [0.160, 0.080, 0.030, 0.008, 0.001, 0.000, 0.000, 0.000, 0.000, 0.000],  # beta=15
    [0.162, 0.092, 0.042, 0.015, 0.004, 0.001, 0.000, 0.000, 0.000, 0.000],  # beta=20
    [0.164, 0.100, 0.052, 0.023, 0.008, 0.002, 0.000, 0.000, 0.000, 0.000],  # beta=25
    [0.164, 0.105, 0.060, 0.030, 0.013, 0.003, 0.000, 0.000, 0.000, 0.000],  # beta=30
    [0.168, 0.114, 0.070, 0.040, 0.020, 0.008, 0.002, 0.000, 0.000, 0.000],  # beta=35
    [0.174, 0.124, 0.082, 0.052, 0.030, 0.015, 0.005, 0.001, 0.000, 0.000],  # beta=40
    [0.170, 0.133, 0.098, 0.068, 0.045, 0.027, 0.012, 0.004, 0.001, 0.000],  # beta=45
    [0.178, 0.143, 0.110, 0.082, 0.058, 0.039, 0.022, 0.010, 0.003, 0.000],  # beta=50
    [0.184, 0.153, 0.122, 0.095, 0.072, 0.052, 0.035, 0.020, 0.009, 0.002],  # beta=55
    [0.191, 0.162, 0.133, 0.108, 0.086, 0.067, 0.050, 0.036, 0.023, 0.013],  # beta=60
    [0.199, 0.172, 0.145, 0.121, 0.099, 0.080, 0.062, 0.047, 0.034, 0.022],  # beta=65
    [0.208, 0.182, 0.157, 0.134, 0.113, 0.094, 0.077, 0.061, 0.047, 0.035],  # beta=70
    [0.219, 0.195, 0.170, 0.147, 0.128, 0.110, 0.093, 0.078, 0.064, 0.051],  # beta=75
    [0.232, 0.210, 0.186, 0.164, 0.144, 0.126, 0.110, 0.095, 0.081, 0.068],  # beta=80
    [0.247, 0.225, 0.203, 0.182, 0.163, 0.145, 0.128, 0.113, 0.099, 0.086],  # beta=85
    [0.261, 0.239, 0.218, 0.199, 0.182, 0.166, 0.150, 0.136, 0.122, 0.110],  # beta=90
]


def _interp1d(x: float, xs: list[float], ys: list[float]) -> float:
    """Linear interpolation with clamping at boundaries."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i])
    return ys[-1]


def taylor_ns(beta_deg: float, phi_deg: float) -> float:
    """
    Look up Taylor stability number Ns for circular failure.

    Uses bilinear interpolation on the Taylor chart grid.

    Args:
        beta_deg: Slope face angle in degrees
        phi_deg: Friction angle (mobilized) in degrees

    Returns:
        Stability number Ns (dimensionless). Returns 0 when phi >= beta
        (slope stable on friction alone).
    """
    if phi_deg >= beta_deg:
        return 0.0

    # Clamp to table range
    beta_deg = max(min(beta_deg, 90.0), 15.0)
    phi_deg = max(min(phi_deg, 45.0), 0.0)

    # Interpolate along phi for each beta row, then interpolate between betas
    ns_at_betas = []
    for row in _TAYLOR_NS:
        ns_at_betas.append(_interp1d(phi_deg, _TAYLOR_PHI, row))

    return max(0.0, _interp1d(beta_deg, _TAYLOR_BETA, ns_at_betas))


def hoek_bray_fs(
    cohesion_kg_cm2: float,
    phi_deg: float,
    gamma_g_cm3: float,
    slope_height_m: float,
    slope_angle_deg: float,
    saturation_pct: int = 0,
    max_fs: float = 50.0,
    tol: float = 0.001,
    max_iter: int = 100,
) -> float:
    """
    Calculate safety factor for circular failure using Taylor/Hoek & Bray method.

    Solves: c / (gamma * H * FS) = Ns(beta, atan(tan(phi) / FS))

    For c = 0 (granular), returns tan(phi) / tan(beta) directly.

    Args:
        cohesion_kg_cm2: Cohesion in kg/cm2
        phi_deg: Friction angle in degrees
        gamma_g_cm3: Density in g/cm3 (= t/m3)
        slope_height_m: Slope height in meters
        slope_angle_deg: Slope face angle in degrees
        saturation_pct: Groundwater saturation (0 = dry, only 0 supported now)
        max_fs: Upper bound for FS search
        tol: Convergence tolerance
        max_iter: Maximum iterations

    Returns:
        Safety factor (capped at max_fs)

    Raises:
        ValueError: If inputs are invalid
    """
    if slope_angle_deg <= 0 or slope_angle_deg >= 90:
        raise ValueError(f"slope_angle_deg must be 0-90, got {slope_angle_deg}")
    if phi_deg < 0:
        raise ValueError(f"phi_deg must be >= 0, got {phi_deg}")
    if gamma_g_cm3 <= 0:
        raise ValueError(f"gamma_g_cm3 must be > 0, got {gamma_g_cm3}")
    if slope_height_m <= 0:
        raise ValueError(f"slope_height_m must be > 0, got {slope_height_m}")

    beta = slope_angle_deg

    # For c = 0 (granular), circular FS ~ infinite slope FS
    if cohesion_kg_cm2 <= 0:
        tan_beta = math.tan(math.radians(beta))
        if tan_beta <= 0:
            return max_fs
        fs = math.tan(math.radians(phi_deg)) / tan_beta
        return min(round(fs, 3), max_fs)

    # Convert units: c kg/cm2 -> t/m2 (multiply by 10)
    c_t_m2 = cohesion_kg_cm2 * 10.0
    gamma_t_m3 = gamma_g_cm3  # g/cm3 = t/m3 numerically
    H = slope_height_m

    # LHS(FS) = c / (gamma * H * FS) — decreasing function of FS
    # RHS(FS) = Ns(beta, atan(tan(phi)/FS)) — increasing function of FS
    # Find FS where LHS = RHS by bisection

    def residual(fs: float) -> float:
        """LHS - RHS: positive means FS too low, negative means FS too high."""
        lhs = c_t_m2 / (gamma_t_m3 * H * fs)
        phi_mob = math.degrees(math.atan(math.tan(math.radians(phi_deg)) / fs))
        rhs = taylor_ns(beta, phi_mob)
        return lhs - rhs

    # Check bounds
    r_low = residual(1.0)
    if r_low < 0:
        # Even at FS=1, cohesion contribution is less than needed -> unstable
        # FS < 1 case: search between 0.1 and 1.0
        fs_lo, fs_hi = 0.1, 1.0
        if residual(0.1) < 0:
            return round(0.1, 2)  # Very unstable
    else:
        fs_lo, fs_hi = 1.0, max_fs

    r_hi = residual(fs_hi)
    if r_hi > 0:
        # Even at max_fs, LHS > RHS -> very stable, cap at max_fs
        return max_fs

    # Bisection
    for _ in range(max_iter):
        fs_mid = (fs_lo + fs_hi) / 2.0
        r_mid = residual(fs_mid)

        if abs(r_mid) < tol:
            return round(fs_mid, 2)

        if r_mid > 0:
            fs_lo = fs_mid  # FS too low
        else:
            fs_hi = fs_mid  # FS too high

    return round((fs_lo + fs_hi) / 2.0, 2)


def calculate_hoek_bray(
    cohesion_kg_cm2: float,
    phi_deg: float,
    gamma_g_cm3: float,
    slope_height_m: float,
    slope_percent: float,
    saturation_pct: int = 0,
    water_detected: bool = False,
    slope_direction: str | None = None,
    fs_required: float = 1.5,
) -> HoekBrayResult:
    """
    Full Hoek & Bray circular failure analysis.

    Args:
        cohesion_kg_cm2: Cohesion in kg/cm2
        phi_deg: Friction angle in degrees
        gamma_g_cm3: Density in g/cm3
        slope_height_m: Slope height in meters
        slope_percent: Slope gradient in % (converted to angle internally)
        saturation_pct: Groundwater saturation (0=dry, only 0 supported)
        water_detected: Whether water was detected in DPSH
        slope_direction: Dominant slope direction
        fs_required: Required safety factor (CTE DB SE-C)

    Returns:
        HoekBrayResult with all parameters and calculated FS
    """
    if slope_percent <= 0:
        raise ValueError(f"slope_percent must be > 0, got {slope_percent}")

    beta_deg = math.degrees(math.atan(slope_percent / 100.0))
    chart_number = {0: 1, 25: 2, 50: 3, 75: 4, 100: 5}.get(saturation_pct, 1)

    fs = hoek_bray_fs(
        cohesion_kg_cm2=cohesion_kg_cm2,
        phi_deg=phi_deg,
        gamma_g_cm3=gamma_g_cm3,
        slope_height_m=slope_height_m,
        slope_angle_deg=beta_deg,
        saturation_pct=saturation_pct,
    )

    method = f"Hoek & Bray (1977), abac n{chart_number} (talus {'sec' if saturation_pct == 0 else f'{saturation_pct}% saturacio'})"

    return HoekBrayResult(
        safety_factor=fs,
        slope_angle_deg=round(beta_deg, 1),
        slope_percent=slope_percent,
        phi_deg=phi_deg,
        cohesion_kg_cm2=cohesion_kg_cm2,
        gamma_g_cm3=gamma_g_cm3,
        slope_height_m=slope_height_m,
        saturation_pct=saturation_pct,
        chart_number=chart_number,
        method=method,
        fs_required=fs_required,
        compliant=fs >= fs_required,
        water_detected=water_detected,
        slope_direction=slope_direction,
    )


# =============================================================================
# CLI / Self-test
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("G3DT Hoek & Bray Circular Failure Calculator")
    print("=" * 60)

    # Test 1: Castellar del Valles (rock, c=1.0, phi=35, H=4m, slope~36%)
    print("\nTest 1: Castellar (rock: c=1.0, phi=35, gamma=2.20, H=4m, slope=36%)")
    r1 = calculate_hoek_bray(
        cohesion_kg_cm2=1.0,
        phi_deg=35.0,
        gamma_g_cm3=2.20,
        slope_height_m=4.0,
        slope_percent=36.0,
    )
    print(f"  beta = {r1.slope_angle_deg} deg")
    print(f"  FS = {r1.safety_factor}")
    print(f"  FS >= {r1.fs_required}? {r1.compliant}")
    print(f"  Method: {r1.method}")
    assert r1.safety_factor > 3.5, f"Expected FS > 3.5, got {r1.safety_factor}"
    print("  PASS: FS > 3.5")

    # Test 2: Granular soil (c=0, phi=38, slope=36%)
    print("\nTest 2: Granular (c=0, phi=38, slope=36%)")
    r2 = calculate_hoek_bray(
        cohesion_kg_cm2=0.0,
        phi_deg=38.0,
        gamma_g_cm3=2.10,
        slope_height_m=5.0,
        slope_percent=36.0,
    )
    print(f"  beta = {r2.slope_angle_deg} deg")
    print(f"  FS = {r2.safety_factor}")
    # For c=0, should approximate tan(phi)/tan(beta)
    expected_fs = math.tan(math.radians(38)) / math.tan(math.radians(r2.slope_angle_deg))
    print(f"  Expected (infinite slope): {expected_fs:.3f}")
    assert abs(r2.safety_factor - round(expected_fs, 3)) < 0.01, "c=0 should match infinite slope"
    print("  PASS: matches infinite slope for c=0")

    # Test 3: Steep rock slope (c=0.5, phi=30, H=10m, slope=100% = 45deg)
    print("\nTest 3: Steep rock (c=0.5, phi=30, gamma=2.10, H=10m, slope=100%)")
    r3 = calculate_hoek_bray(
        cohesion_kg_cm2=0.5,
        phi_deg=30.0,
        gamma_g_cm3=2.10,
        slope_height_m=10.0,
        slope_percent=100.0,
    )
    print(f"  beta = {r3.slope_angle_deg} deg")
    print(f"  FS = {r3.safety_factor}")
    print(f"  Compliant? {r3.compliant}")
    print(f"  Method: {r3.method}")

    # Test 4: Taylor Ns lookup validation
    print("\nTest 4: Taylor Ns lookup validation")
    ns_90_0 = taylor_ns(90, 0)
    print(f"  Ns(beta=90, phi=0) = {ns_90_0:.3f} (expected ~0.261)")
    assert abs(ns_90_0 - 0.261) < 0.005, f"Expected 0.261, got {ns_90_0}"

    ns_60_10 = taylor_ns(60, 10)
    print(f"  Ns(beta=60, phi=10) = {ns_60_10:.3f} (expected ~0.133)")
    assert abs(ns_60_10 - 0.133) < 0.005, f"Expected 0.133, got {ns_60_10}"

    ns_45_25 = taylor_ns(45, 25)
    print(f"  Ns(beta=45, phi=25) = {ns_45_25:.3f} (expected ~0.027)")
    assert abs(ns_45_25 - 0.027) < 0.005, f"Expected 0.027, got {ns_45_25}"

    # phi >= beta -> stable (Ns = 0)
    ns_30_35 = taylor_ns(30, 35)
    print(f"  Ns(beta=30, phi=35) = {ns_30_35:.3f} (expected 0.000)")
    assert ns_30_35 == 0.0, f"Expected 0.0, got {ns_30_35}"
    print("  PASS: all Ns lookups correct")

    # Test 5: Gentle slope with rock (should give very high FS)
    print("\nTest 5: Gentle slope with rock (c=1.0, phi=35, H=3m, slope=15%)")
    r5 = calculate_hoek_bray(
        cohesion_kg_cm2=1.0,
        phi_deg=35.0,
        gamma_g_cm3=2.20,
        slope_height_m=3.0,
        slope_percent=15.0,
    )
    print(f"  beta = {r5.slope_angle_deg} deg")
    print(f"  FS = {r5.safety_factor}")
    print(f"  Compliant? {r5.compliant}")
    assert r5.safety_factor > 5.0, f"Expected FS > 5 for gentle rock slope, got {r5.safety_factor}"
    print("  PASS: FS > 5 for gentle rock slope")

    print("\n" + "=" * 60)
    print("All Hoek & Bray tests passed!")
    print("=" * 60)
