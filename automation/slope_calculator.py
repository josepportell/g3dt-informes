#!/usr/bin/env python3
"""
G3DT Slope Stability Calculator

Implements the infinite slope method (Hoek & Bray, 1977) for shallow
slope stability analysis, as used in G3DT geotechnical reports.

Formula:
    General:  FS = (c + gamma*H*cos^2(beta)*tan(phi)) / (gamma*H*sin(beta)*cos(beta))
    Granular: FS = tan(phi) / tan(beta)   [when c ~ 0]

Where:
    beta = slope angle (from slope_percent)
    phi  = internal friction angle (from CTE Table 4.1)
    gamma = soil density (from CTE Table D.27)
    c = cohesion (normally 0 for granular soils)
    H = slope height (estimated or user-provided)

Reference CTE: FS_required = 1.5 (CTE DB SE-C section 7.2.2.1, persistent situations)

Author: Eficients.cat
Date: 2026-02-25
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class SlopeStabilityResult:
    """Result of slope stability calculation."""
    slope_angle_deg: float       # beta in degrees (converted from %)
    slope_percent: float         # Original slope in %
    phi_deg: float               # phi from CTE
    gamma_g_cm3: float           # gamma from CTE
    cohesion_kg_cm2: float       # c (normally 0)
    slope_height_m: float | None  # H if used (cohesive formula)
    safety_factor: float         # FS calculated
    fs_required: float           # 1.5 (CTE DB SE-C section 7.2.2.1)
    compliant: bool              # FS >= fs_required
    water_detected: bool         # Water level detected in DPSH
    slope_direction: str | None  # Dominant direction
    method: str                  # Calculation method description


def calculate_slope_stability(
    slope_percent: float,
    phi_deg: float,
    gamma_g_cm3: float,
    cohesion_kg_cm2: float = 0.0,
    slope_height_m: float | None = None,
    water_detected: bool = False,
    slope_direction: str | None = None,
    fs_required: float = 1.5,
) -> SlopeStabilityResult:
    """
    Calculate slope stability using the infinite slope method.

    For granular soils (c ~ 0): FS = tan(phi) / tan(beta)
    For cohesive soils (c > 0): requires slope_height_m (H)

    Args:
        slope_percent: Slope gradient in % (e.g. 25 means 25%)
        phi_deg: Internal friction angle in degrees
        gamma_g_cm3: Soil density in g/cm3
        cohesion_kg_cm2: Cohesion in kg/cm2 (default 0 for granular)
        slope_height_m: Slope height in meters (required if c > 0)
        water_detected: Whether water level was detected in DPSH tests
        slope_direction: Dominant slope direction (N, NE, E, etc.)
        fs_required: Required safety factor (default 1.5, CTE DB SE-C)

    Returns:
        SlopeStabilityResult with all calculation parameters and FS

    Raises:
        ValueError: If slope_percent <= 0 or phi_deg <= 0
    """
    if slope_percent <= 0:
        raise ValueError(f"slope_percent must be > 0, got {slope_percent}")
    if phi_deg <= 0:
        raise ValueError(f"phi_deg must be > 0, got {phi_deg}")

    # Convert slope % to angle in radians
    beta_rad = math.atan(slope_percent / 100.0)
    beta_deg = math.degrees(beta_rad)

    phi_rad = math.radians(phi_deg)

    if cohesion_kg_cm2 > 0 and slope_height_m and slope_height_m > 0:
        # Full formula with cohesion
        # Convert units: cohesion kg/cm2 -> t/m2 (x10), gamma g/cm3 -> t/m3
        c_t_m2 = cohesion_kg_cm2 * 10.0  # kg/cm2 -> t/m2
        gamma_t_m3 = gamma_g_cm3  # g/cm3 = t/m3 numerically

        numerator = (
            c_t_m2
            + gamma_t_m3 * slope_height_m * math.cos(beta_rad)**2 * math.tan(phi_rad)
        )
        denominator = gamma_t_m3 * slope_height_m * math.sin(beta_rad) * math.cos(beta_rad)

        if denominator == 0:
            fs = float('inf')
        else:
            fs = numerator / denominator

        method = "Talus infinit (Hoek & Bray, 1977) amb cohesio"
    else:
        # Simplified formula for granular soils (c = 0)
        tan_beta = math.tan(beta_rad)
        if tan_beta == 0:
            fs = float('inf')
        else:
            fs = math.tan(phi_rad) / tan_beta

        method = "Talus infinit (Hoek & Bray, 1977)"

    return SlopeStabilityResult(
        slope_angle_deg=round(beta_deg, 1),
        slope_percent=slope_percent,
        phi_deg=phi_deg,
        gamma_g_cm3=gamma_g_cm3,
        cohesion_kg_cm2=cohesion_kg_cm2,
        slope_height_m=slope_height_m,
        safety_factor=round(fs, 2),
        fs_required=fs_required,
        compliant=fs >= fs_required,
        water_detected=water_detected,
        slope_direction=slope_direction,
        method=method,
    )


# CLI for testing
if __name__ == '__main__':
    print("=== G3DT Slope Stability Calculator ===\n")

    # Test case: Castellar del Valles (phi=34, slope~20%)
    print("Test 1: Castellar (phi=34, slope=36%)")
    r1 = calculate_slope_stability(
        slope_percent=36.0,
        phi_deg=34.0,
        gamma_g_cm3=2.10,
    )
    print(f"  beta = {r1.slope_angle_deg} deg")
    print(f"  FS = tan({r1.phi_deg}) / tan({r1.slope_angle_deg}) = {r1.safety_factor}")
    print(f"  FS >= {r1.fs_required}? {r1.compliant}")
    print(f"  Method: {r1.method}")

    # Test case: Steep slope
    print("\nTest 2: Steep slope (phi=30, slope=60%)")
    r2 = calculate_slope_stability(
        slope_percent=60.0,
        phi_deg=30.0,
        gamma_g_cm3=1.90,
    )
    print(f"  beta = {r2.slope_angle_deg} deg")
    print(f"  FS = {r2.safety_factor}")
    print(f"  Compliant? {r2.compliant}")

    # Test case: With cohesion
    print("\nTest 3: Cohesive soil (phi=25, c=0.5, slope=40%, H=5m)")
    r3 = calculate_slope_stability(
        slope_percent=40.0,
        phi_deg=25.0,
        gamma_g_cm3=2.00,
        cohesion_kg_cm2=0.5,
        slope_height_m=5.0,
    )
    print(f"  beta = {r3.slope_angle_deg} deg")
    print(f"  FS = {r3.safety_factor}")
    print(f"  Compliant? {r3.compliant}")
    print(f"  Method: {r3.method}")
