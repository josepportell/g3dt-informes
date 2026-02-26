#!/usr/bin/env python3
"""
G3DT Terzaghi Bearing Capacity Calculator

Calculates allowable bearing capacity (Qa) and settlements for shallow
foundations using Terzaghi's bearing capacity theory.

This is a critical module - the Qa value is the main engineering output
of the geotechnical report (Section 4.3 Fonamentació).

Formulas:
    Terzaghi (1943) bearing capacity:
    qu = c·Nc·sc + γ·Df·Nq·sq + 0.5·γ·B·Nγ·sγ

    Where:
    - qu = ultimate bearing capacity (kg/cm² or kPa)
    - c = cohesion (kg/cm² or kPa)
    - γ = unit weight of soil (g/cm³ or kN/m³)
    - Df = foundation depth (m)
    - B = foundation width (m)
    - Nc, Nq, Nγ = bearing capacity factors (from φ)
    - sc, sq, sγ = shape factors

    Allowable bearing capacity:
    Qa = qu / F (F = safety factor, typically 3)

Usage:
    uv run terzaghi_calculator.py --phi 38 --gamma 2.1 --B 1.0 --Df 0.8

    Or as a module:
    from terzaghi_calculator import TerzaghiCalculator
    calc = TerzaghiCalculator(phi=38, cohesion=0, gamma=2.1)
    result = calc.calculate_qa(B=1.0, Df=0.8)

Author: Eficients.cat
Date: 2026-02-02

References:
- Terzaghi, K. (1943). Theoretical Soil Mechanics. John Wiley & Sons.
- Jiménez Salas, J.A. et al. "Geotecnia y Cimientos" (referenced in G3DT reports)
"""

import math
import sys
from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum


class FootingShape(Enum):
    """Foundation shape types."""
    STRIP = "strip"           # Zapata corrida (L >> B)
    SQUARE = "square"         # Zapata cuadrada (L = B)
    CIRCULAR = "circular"     # Zapata circular
    RECTANGULAR = "rectangular"  # Zapata rectangular (L > B)


@dataclass
class BearingCapacityFactors:
    """Terzaghi bearing capacity factors for a given friction angle."""
    phi: float  # Friction angle in degrees
    Nc: float   # Cohesion factor
    Nq: float   # Surcharge factor
    Ngamma: float  # Unit weight factor (Nγ)

    def __str__(self):
        return f"φ={self.phi}° → Nc={self.Nc:.2f}, Nq={self.Nq:.2f}, Nγ={self.Ngamma:.2f}"


@dataclass
class BearingCapacityResult:
    """Results of bearing capacity calculation."""
    # Input parameters
    phi: float              # Friction angle (degrees)
    cohesion: float         # Cohesion (kg/cm²)
    gamma: float            # Unit weight (g/cm³)
    B: float                # Foundation width (m)
    Df: float               # Foundation depth (m)
    L: Optional[float]      # Foundation length (m), None for square/circular
    shape: FootingShape

    # Bearing capacity factors
    Nc: float
    Nq: float
    Ngamma: float

    # Shape factors
    sc: float
    sq: float
    sgamma: float

    # Results
    qu: float               # Ultimate bearing capacity (kg/cm²)
    safety_factor: float    # Applied safety factor
    Qa: float               # Allowable bearing capacity (kg/cm²)

    # Settlement (if calculated)
    settlement_cm: Optional[float] = None
    settlement_type: str = "immediat"  # or "diferit" for clays

    # Terzaghi-Peck empirical check
    qa_terzaghi_peck: Optional[float] = None  # T-P empirical Qa (kg/cm²), if computed
    qa_governs: str = "terzaghi"  # Which method governs: "terzaghi" or "terzaghi_peck"

    def to_dict(self) -> dict:
        return {
            'inputs': {
                'phi_deg': self.phi,
                'cohesion_kg_cm2': self.cohesion,
                'gamma_g_cm3': self.gamma,
                'B_m': self.B,
                'Df_m': self.Df,
                'L_m': self.L,
                'shape': self.shape.value,
            },
            'factors': {
                'Nc': round(self.Nc, 2),
                'Nq': round(self.Nq, 2),
                'Ngamma': round(self.Ngamma, 2),
                'sc': round(self.sc, 3),
                'sq': round(self.sq, 3),
                'sgamma': round(self.sgamma, 3),
            },
            'results': {
                'qu_kg_cm2': round(self.qu, 3),
                'safety_factor': self.safety_factor,
                'Qa_kg_cm2': round(self.Qa, 2),
                'settlement_cm': round(self.settlement_cm, 2) if self.settlement_cm else None,
                'settlement_type': self.settlement_type,
                'qa_terzaghi_peck_kg_cm2': round(self.qa_terzaghi_peck, 2) if self.qa_terzaghi_peck else None,
                'qa_governs': self.qa_governs,
            }
        }

    def format_for_report(self) -> str:
        """Format result as it appears in G3DT reports."""
        return f"Qa= {self.Qa:.1f} Kg/cm²  amb un factor de seguretat inclòs de F={int(self.safety_factor)}"

    def format_settlement_for_report(self) -> str:
        """Format settlement as it appears in G3DT reports."""
        if self.settlement_cm is None:
            return ""
        return (
            f"Els assentaments màxims previstos per la càrrega recomanada "
            f"anteriorment seran inferiors a {self.settlement_cm:.2f} cm, "
            f"{self.settlement_type}s en el temps"
        )


class TerzaghiCalculator:
    """
    Calculator for Terzaghi bearing capacity.

    Implements the classical Terzaghi (1943) bearing capacity theory
    with shape factors for different foundation types.
    """

    # Precomputed bearing capacity factors for common friction angles
    # Source: Terzaghi (1943), various geotechnical references
    BEARING_FACTORS_TABLE = {
        0:  BearingCapacityFactors(0, 5.70, 1.00, 0.00),
        5:  BearingCapacityFactors(5, 7.30, 1.60, 0.50),
        10: BearingCapacityFactors(10, 9.60, 2.70, 1.20),
        15: BearingCapacityFactors(15, 12.90, 4.40, 2.50),
        20: BearingCapacityFactors(20, 17.70, 7.40, 5.00),
        25: BearingCapacityFactors(25, 25.10, 12.70, 9.70),
        26: BearingCapacityFactors(26, 27.10, 14.20, 11.00),
        28: BearingCapacityFactors(28, 31.60, 17.80, 14.60),
        30: BearingCapacityFactors(30, 37.20, 22.50, 19.70),
        32: BearingCapacityFactors(32, 44.00, 28.50, 27.00),
        34: BearingCapacityFactors(34, 52.60, 36.50, 36.00),
        35: BearingCapacityFactors(35, 57.80, 41.40, 42.40),
        36: BearingCapacityFactors(36, 63.50, 47.20, 49.00),
        38: BearingCapacityFactors(38, 77.50, 61.50, 67.40),
        40: BearingCapacityFactors(40, 95.70, 81.30, 100.40),
        42: BearingCapacityFactors(42, 119.70, 108.80, 155.60),
        44: BearingCapacityFactors(44, 151.90, 147.70, 244.60),
        45: BearingCapacityFactors(45, 172.30, 173.30, 297.50),
    }

    def __init__(
        self,
        phi: float,
        cohesion: float = 0.0,
        gamma: float = 2.0,
        safety_factor: float = 3.0,
    ):
        """
        Initialize calculator with soil parameters.

        Args:
            phi: Friction angle in degrees
            cohesion: Cohesion in kg/cm² (0 for granular soils)
            gamma: Unit weight in g/cm³ (equivalent to t/m³)
            safety_factor: Safety factor for Qa calculation (default 3)
        """
        self.phi = phi
        self.cohesion = cohesion
        self.gamma = gamma
        self.safety_factor = safety_factor

        # Get bearing capacity factors
        self.factors = self._get_bearing_factors(phi)

    def _get_bearing_factors(self, phi: float) -> BearingCapacityFactors:
        """
        Get bearing capacity factors for given friction angle.
        Interpolates between table values if needed.
        """
        # Exact match in table
        if phi in self.BEARING_FACTORS_TABLE:
            return self.BEARING_FACTORS_TABLE[phi]

        # Find surrounding values for interpolation
        phi_values = sorted(self.BEARING_FACTORS_TABLE.keys())

        # Handle out of range
        if phi < phi_values[0]:
            return self.BEARING_FACTORS_TABLE[phi_values[0]]
        if phi > phi_values[-1]:
            return self.BEARING_FACTORS_TABLE[phi_values[-1]]

        # Find bracketing values
        phi_low = max(p for p in phi_values if p <= phi)
        phi_high = min(p for p in phi_values if p >= phi)

        if phi_low == phi_high:
            return self.BEARING_FACTORS_TABLE[phi_low]

        # Linear interpolation
        f_low = self.BEARING_FACTORS_TABLE[phi_low]
        f_high = self.BEARING_FACTORS_TABLE[phi_high]
        t = (phi - phi_low) / (phi_high - phi_low)

        return BearingCapacityFactors(
            phi=phi,
            Nc=f_low.Nc + t * (f_high.Nc - f_low.Nc),
            Nq=f_low.Nq + t * (f_high.Nq - f_low.Nq),
            Ngamma=f_low.Ngamma + t * (f_high.Ngamma - f_low.Ngamma),
        )

    @staticmethod
    def _calculate_shape_factors(
        shape: FootingShape,
        B: float,
        L: Optional[float] = None,
        phi: float = 30.0
    ) -> tuple[float, float, float]:
        """
        Calculate shape factors (sc, sq, sγ) for Terzaghi formula.

        Different sources use slightly different shape factors.
        These are based on Terzaghi's original recommendations.

        Returns:
            Tuple of (sc, sq, sgamma)
        """
        if shape == FootingShape.STRIP:
            # Strip footing: no shape correction
            return 1.0, 1.0, 1.0

        elif shape == FootingShape.SQUARE:
            # Square footing
            return 1.3, 1.0, 0.8

        elif shape == FootingShape.CIRCULAR:
            # Circular footing
            return 1.3, 1.0, 0.6

        elif shape == FootingShape.RECTANGULAR:
            # Rectangular: interpolate based on B/L ratio
            if L is None or L <= B:
                # Treat as square if L not given or L <= B
                return 1.3, 1.0, 0.8

            ratio = B / L
            # Interpolate between strip (ratio→0) and square (ratio=1)
            sc = 1.0 + 0.3 * ratio
            sq = 1.0
            sgamma = 1.0 - 0.2 * ratio
            return sc, sq, sgamma

        else:
            # Default to strip
            return 1.0, 1.0, 1.0

    def calculate_qu(
        self,
        B: float,
        Df: float = 0.5,
        L: Optional[float] = None,
        shape: FootingShape = FootingShape.STRIP,
    ) -> float:
        """
        Calculate ultimate bearing capacity qu.

        Args:
            B: Foundation width in meters
            Df: Foundation depth in meters
            L: Foundation length in meters (for rectangular)
            shape: Foundation shape

        Returns:
            Ultimate bearing capacity in kg/cm²
        """
        # Get shape factors
        sc, sq, sgamma = self._calculate_shape_factors(shape, B, L, self.phi)

        # Terzaghi formula
        # qu = c·Nc·sc + γ·Df·Nq·sq + 0.5·γ·B·Nγ·sγ

        # Convert units: B and Df are in meters, gamma in g/cm³
        # To get qu in kg/cm²:
        # - gamma (g/cm³) = gamma (t/m³)
        # - Df (m) * 100 = Df (cm)
        # - B (m) * 100 = B (cm)
        # - Result needs to be in kg/cm²

        # Term 1: Cohesion term (c is already in kg/cm²)
        term1 = self.cohesion * self.factors.Nc * sc

        # Term 2: Surcharge term
        # γ (g/cm³) × Df (m) × 100 (cm/m) = kg/cm² × 0.01
        # Actually: γ (t/m³) × Df (m) × 10 (kN to kgf conversion roughly)
        # Simplified: γ (g/cm³) × Df (m) gives ~correct magnitude
        term2 = self.gamma * (Df * 100 / 1000) * self.factors.Nq * sq  # Df in m converted

        # Let's use a cleaner approach:
        # Work in consistent units: kg/cm²
        # γ in g/cm³ = t/m³, Df in m, convert to kg/cm²
        # 1 t/m³ × 1 m = 1 t/m² = 0.1 kg/cm²
        gamma_kgcm2_per_m = self.gamma * 0.1  # kg/cm² per meter depth

        term2 = gamma_kgcm2_per_m * Df * self.factors.Nq * sq

        # Term 3: Width term
        # 0.5 × γ × B × Nγ
        term3 = 0.5 * gamma_kgcm2_per_m * B * self.factors.Ngamma * sgamma

        qu = term1 + term2 + term3
        return qu

    def calculate_qa(
        self,
        B: float,
        Df: float = 0.5,
        L: Optional[float] = None,
        shape: FootingShape = FootingShape.STRIP,
        calculate_settlement: bool = True,
        E: Optional[float] = None,
        nspt: Optional[float] = None,
        is_granular: bool = True,
    ) -> BearingCapacityResult:
        """
        Calculate allowable bearing capacity Qa with full results.

        Args:
            B: Foundation width in meters
            Df: Foundation depth in meters
            L: Foundation length in meters (for rectangular)
            shape: Foundation shape
            calculate_settlement: Whether to estimate settlement
            E: Deformation modulus in kg/cm² (for settlement calculation)
            nspt: SPT/DPSH N value for Terzaghi-Peck empirical check (optional)
            is_granular: Whether soil is granular (T-P only applies to granular)

        Returns:
            BearingCapacityResult with all calculation details
        """
        # Get shape factors
        sc, sq, sgamma = self._calculate_shape_factors(shape, B, L, self.phi)

        # Calculate ultimate bearing capacity
        qu = self.calculate_qu(B, Df, L, shape)

        # Calculate allowable bearing capacity
        Qa = qu / self.safety_factor

        # Terzaghi-Peck empirical check (Eva's practice: take the lower)
        # Only for granular soils (cohesion ≈ 0) — T-P is not valid for
        # cohesive soils or rock.
        qa_tp = None
        qa_governs = "terzaghi"
        if nspt is not None and nspt < 100 and is_granular:
            qa_tp = terzaghi_peck_qa(nspt, B, Df)
            if qa_tp < Qa:
                Qa = qa_tp
                qa_governs = "terzaghi_peck"

        # Professional practice cap (confirmed by Eva 2026-02-26):
        # Soil: max 3.0 kg/cm², clear rock: max 4.5 kg/cm²
        QA_CAP_SOIL = 3.0
        QA_CAP_ROCK = 4.5
        qa_cap = QA_CAP_ROCK if not is_granular and self.cohesion >= 0.5 else QA_CAP_SOIL
        if Qa > qa_cap:
            Qa = qa_cap
            if qa_governs == "terzaghi":
                qa_governs = "cap"

        # Calculate settlement if requested
        settlement = None
        settlement_type = "immediat"

        if calculate_settlement:
            # Use provided E or estimate from N correlation
            if E is None:
                # Rough estimate: E ≈ 10 × N (kg/cm²) for granular soils
                # We don't have N directly, but can back-calculate from phi
                # For phi=38°, N≈35-50, so E≈350-500 kg/cm²
                # Use a conservative estimate based on phi
                if self.phi < 30:
                    E = 200
                elif self.phi < 35:
                    E = 300
                elif self.phi < 40:
                    E = 400
                else:
                    E = 500

            settlement = self._calculate_settlement(Qa, B, E)

            # Settlement type depends on soil
            if self.cohesion > 0.1:  # Cohesive soil
                settlement_type = "diferit"  # Delayed (consolidation)
            else:
                settlement_type = "immediat"  # Immediate (elastic)

        return BearingCapacityResult(
            phi=self.phi,
            cohesion=self.cohesion,
            gamma=self.gamma,
            B=B,
            Df=Df,
            L=L,
            shape=shape,
            Nc=self.factors.Nc,
            Nq=self.factors.Nq,
            Ngamma=self.factors.Ngamma,
            sc=sc,
            sq=sq,
            sgamma=sgamma,
            qu=qu,
            safety_factor=self.safety_factor,
            Qa=Qa,
            settlement_cm=settlement,
            settlement_type=settlement_type,
            qa_terzaghi_peck=qa_tp,
            qa_governs=qa_governs,
        )

    def _calculate_settlement(
        self,
        q: float,
        B: float,
        E: float,
        nu: float = 0.3,
    ) -> float:
        """
        Calculate elastic settlement using Boussinesq theory.

        Simplified formula for flexible footing on elastic half-space:
        s = q × B × (1 - ν²) × Iw / E

        Where:
        - s = settlement
        - q = applied pressure (Qa)
        - B = foundation width
        - ν = Poisson's ratio (typically 0.3 for soils)
        - Iw = influence factor (≈1.0 for square, ≈0.88 for strip)
        - E = deformation modulus

        Args:
            q: Applied pressure in kg/cm²
            B: Foundation width in meters
            E: Deformation modulus in kg/cm²
            nu: Poisson's ratio

        Returns:
            Settlement in cm
        """
        # Influence factor (simplified)
        Iw = 1.0  # Conservative for flexible footing

        # Convert B to cm
        B_cm = B * 100

        # Settlement formula
        # s = q × B × (1 - ν²) × Iw / E
        settlement_cm = q * B_cm * (1 - nu**2) * Iw / E

        return settlement_cm


def terzaghi_peck_qa(
    nspt: float,
    B: float,
    Df: float = 0.0,
    S_cm: float = 2.54,
) -> float:
    """
    Terzaghi-Peck empirical bearing capacity for granular soils.

    Formula from Eva's reports (Rodríguez Ortiz / Terzaghi & Peck):
        Qadm = N/12 × S / ((B + 0.3) / B)² × Fd

    With depth correction (Bowles, Coduto):
        Fd = 1 + 0.33 × (Df / B), max 1.33

    Only valid for granular soils (sands, gravels). NOT for cohesive
    soils or rock.

    Args:
        nspt: SPT/DPSH N value (N20)
        B: Foundation width in meters
        Df: Foundation depth in meters (for depth correction)
        S_cm: Allowable settlement in cm (default 1 inch = 2.54 cm)

    Returns:
        Allowable bearing capacity in kg/cm²
    """
    correction = ((B + 0.3) / B) ** 2
    Fd = min(1 + 0.33 * (Df / B), 1.33) if B > 0 and Df > 0 else 1.0
    qa = (nspt / 12.0) * (S_cm / 2.54) / correction * Fd
    return qa


def calculate_from_dpsh(
    average_n20: float,
    B: float = 1.0,
    Df: float = 0.5,
    shape: FootingShape = FootingShape.STRIP,
    safety_factor: float = 3.0,
    soil_type: str = 'granular',
) -> BearingCapacityResult:
    """
    Convenience function to calculate Qa directly from DPSH N₂₀ average.

    This combines the correlation functions with Terzaghi calculation
    for a complete workflow from test data to Qa.

    Args:
        average_n20: Average N₂₀ value from DPSH tests
        B: Foundation width in meters
        Df: Foundation depth in meters
        shape: Foundation shape
        safety_factor: Safety factor (default 3)
        soil_type: 'granular' or 'cohesive'

    Returns:
        BearingCapacityResult with calculated Qa
    """
    from dpsh_extractor import GeotechCorrelations

    # Get soil parameters from correlations
    phi = GeotechCorrelations.n_to_friction_angle(average_n20, soil_type)
    gamma = GeotechCorrelations.n_to_density(average_n20, soil_type)
    E = GeotechCorrelations.n_to_deformation_modulus(average_n20, soil_type)

    # Cohesion
    if soil_type == 'granular':
        cohesion = 0.0
    else:
        # For cohesive soils, estimate cohesion from N
        # cu ≈ N/10 to N/8 (kg/cm²) approximately
        cohesion = average_n20 / 10

    # Calculate
    calc = TerzaghiCalculator(
        phi=phi,
        cohesion=cohesion,
        gamma=gamma,
        safety_factor=safety_factor,
    )

    return calc.calculate_qa(B=B, Df=Df, shape=shape, E=E)


def main():
    """Command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Calculate Terzaghi bearing capacity (Qa)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From soil parameters
  %(prog)s --phi 38 --gamma 2.1 --B 1.0 --Df 0.8

  # From DPSH average N20
  %(prog)s --n20 36 --B 1.0 --Df 0.5

  # Square footing
  %(prog)s --phi 35 --gamma 1.95 --B 1.5 --Df 0.6 --shape square

  # With cohesion (clay)
  %(prog)s --phi 25 --cohesion 0.5 --gamma 1.8 --B 1.0 --Df 0.8
        """
    )

    # Input options (either phi or n20)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--phi', type=float, help='Friction angle in degrees')
    input_group.add_argument('--n20', type=float, help='Average N20 from DPSH (will derive phi)')

    # Soil parameters
    parser.add_argument('--cohesion', type=float, default=0.0,
                        help='Cohesion in kg/cm² (default: 0 for granular)')
    parser.add_argument('--gamma', type=float, default=2.0,
                        help='Unit weight in g/cm³ (default: 2.0)')

    # Foundation parameters
    parser.add_argument('--B', type=float, required=True,
                        help='Foundation width in meters')
    parser.add_argument('--Df', type=float, default=0.5,
                        help='Foundation depth in meters (default: 0.5)')
    parser.add_argument('--L', type=float,
                        help='Foundation length in meters (for rectangular)')
    parser.add_argument('--shape', choices=['strip', 'square', 'circular', 'rectangular'],
                        default='strip', help='Foundation shape (default: strip)')

    # Calculation options
    parser.add_argument('--F', type=float, default=3.0,
                        help='Safety factor (default: 3)')
    parser.add_argument('--E', type=float,
                        help='Deformation modulus in kg/cm² (for settlement)')

    # Output options
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format')

    args = parser.parse_args()

    # Determine calculation method
    if args.n20:
        # Calculate from DPSH N20
        result = calculate_from_dpsh(
            average_n20=args.n20,
            B=args.B,
            Df=args.Df,
            shape=FootingShape(args.shape),
            safety_factor=args.F,
        )
    else:
        # Calculate from direct parameters
        calc = TerzaghiCalculator(
            phi=args.phi,
            cohesion=args.cohesion,
            gamma=args.gamma,
            safety_factor=args.F,
        )
        result = calc.calculate_qa(
            B=args.B,
            Df=args.Df,
            L=args.L,
            shape=FootingShape(args.shape),
            E=args.E,
        )

    if args.json:
        import json
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        # Human-readable output
        print(f"\n{'='*60}")
        print("TERZAGHI BEARING CAPACITY CALCULATION")
        print(f"{'='*60}")

        print(f"\n📐 INPUT PARAMETERS")
        print(f"  Friction angle (φ): {result.phi:.1f}°")
        print(f"  Cohesion (c): {result.cohesion:.2f} kg/cm²")
        print(f"  Unit weight (γ): {result.gamma:.2f} g/cm³")
        print(f"  Foundation width (B): {result.B:.2f} m")
        print(f"  Foundation depth (Df): {result.Df:.2f} m")
        print(f"  Shape: {result.shape.value}")

        print(f"\n📊 BEARING CAPACITY FACTORS")
        print(f"  Nc = {result.Nc:.2f}")
        print(f"  Nq = {result.Nq:.2f}")
        print(f"  Nγ = {result.Ngamma:.2f}")

        print(f"\n📏 SHAPE FACTORS")
        print(f"  sc = {result.sc:.3f}")
        print(f"  sq = {result.sq:.3f}")
        print(f"  sγ = {result.sgamma:.3f}")

        print(f"\n✅ RESULTS")
        print(f"  Ultimate capacity (qu): {result.qu:.2f} kg/cm²")
        print(f"  Safety factor (F): {result.safety_factor:.0f}")
        print(f"  ┌────────────────────────────────────────┐")
        print(f"  │  Qa = {result.Qa:.2f} kg/cm²                    │")
        print(f"  └────────────────────────────────────────┘")

        if result.settlement_cm:
            print(f"\n📉 SETTLEMENT")
            print(f"  Estimated: {result.settlement_cm:.2f} cm ({result.settlement_type})")

        print(f"\n📝 FOR REPORT")
        print(f"  {result.format_for_report()}")
        if result.settlement_cm:
            print(f"  {result.format_settlement_for_report()}")

        print(f"\n{'='*60}")


if __name__ == '__main__':
    main()
