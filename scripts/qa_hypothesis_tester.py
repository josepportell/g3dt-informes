#!/usr/bin/env python3
"""
Qa Hypothesis Tester: systematic reverse-engineering of Eva's calculations.

For each project, tests multiple combinations of:
- N value (N20, Nb, SPT N30)
- Qa method (Terzaghi-Peck Nb/12, full Terzaghi formula, direct cap)
- Parameters (phi, E, Es, footing width, depth)

Compares against Eva's known Qa values to identify the criteria she uses.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.terzaghi_calculator import TerzaghiCalculator, FootingShape

# Eva's reference values (from eva_reference_values.json)
EVA_QA = {
    "4001612 BELL-LLOC": 3.0,
    "3001621 CASTELLAR DEL VALLES": 3.0,
    "3001631 RUBI": 3.50,
    "4001607 LINYOLA": 3.0,
    "4001670 ALCOLETGE": 3.50,
    "4001671 VILANOVA DE SEGRIA": 2.50,
    "4001679 ANCILES": 2.0,
}

# Eva's typical parameters (from MEMORY)
EVA_PARAMS = {
    "4001612 BELL-LLOC": {
        "soil": "graves_carbonatades",
        "N20_avg": 40,  # From DPSH Excel
        "gamma": 2.0,
        "phi": 38,
        "c": 0.0,
        "E": 650,  # Eva's override (carbonatades)
    },
    "3001621 CASTELLAR DEL VALLES": {
        "soil": "roca_bretxes",
        "N20_avg": 28,  # refusal early
        "gamma": 2.20,
        "phi": 35,
        "c": 1.0,
        "E": 800,
    },
    "3001631 RUBI": {
        "soil": "graves_denses",
        "N20_avg": 40,
        "gamma": 2.0,
        "phi": 39,
        "c": 0.0,
        "E": 450,
    },
    "4001607 LINYOLA": {
        "soil": "graves_sorrenques",
        "N20_avg": 20,
        "gamma": 2.0,
        "phi": 36,
        "c": 0.0,
        "E": 350,
    },
    "4001670 ALCOLETGE": {
        "soil": "graves_carbonatades",
        "N20_avg": 30,
        "gamma": 2.0,
        "phi": 37,
        "c": 0.05,
        "E": 500,
    },
    "4001671 VILANOVA DE SEGRIA": {
        "soil": "llims_argilosos",
        "N20_avg": 15,
        "gamma": 1.90,
        "phi": 28,
        "c": 0.05,
        "E": 100,
    },
    "4001679 ANCILES": {
        "soil": "argila_sorrenca",
        "N20_avg": 12,
        "gamma": 1.90,
        "phi": 25,
        "c": 0.05,
        "E": 80,
    },
}

# Footing defaults
B_DEFAULT = 1.0   # Foundation width (m)
DF_DEFAULT = 0.8  # Foundation depth (m)
F_SAFETY = 3.0    # Safety factor


def terzaghi_peck_qa(Nb: float, B: float = 1.0, Df: float = 0.8) -> float:
    """Simple Terzaghi-Peck: Qa = Nb/12 × Fw × Fd

    Fw = width correction = 1.0 for B≤1.2m, (B+0.3)/(2B) for B>1.2m
    Fd = depth factor = 1 + D/(3B)
    """
    if Nb <= 0:
        return 0
    qa_base = Nb / 12  # kg/cm²

    # Width correction
    if B > 1.2:
        fw = (B + 0.3) / (2 * B)
    else:
        fw = 1.0

    # Depth factor
    fd = 1 + Df / (3 * B)

    return round(qa_base * fw * fd, 2)


def full_terzaghi_qa(phi, c, gamma, B=1.0, Df=0.8, shape='square') -> float:
    """Full Terzaghi formula: qu = c·Nc·sc + γ·Df·Nq·sq + 0.5·γ·B·Nγ·sγ
    Then Qa = qu / F
    """
    calc = TerzaghiCalculator(phi=phi, cohesion=c, gamma=gamma)
    result = calc.calculate_qa(B=B, Df=Df, shape=FootingShape.SQUARE)
    return result.Qa


def main():
    print("=" * 100)
    print("QA HYPOTHESIS TESTER — Reverse-Engineering Eva's Criteria")
    print("=" * 100)

    for proj, eva_qa in sorted(EVA_QA.items()):
        params = EVA_PARAMS.get(proj, {})
        if not params:
            continue

        N20 = params['N20_avg']
        Nb = round(N20 / 0.83, 1)
        phi = params['phi']
        c = params['c']
        gamma = params['gamma']
        E = params['E']
        soil = params['soil']

        print(f"\n{'─' * 100}")
        print(f"  {proj}")
        print(f"  Soil: {soil}, N20={N20}, Nb={Nb}, phi={phi}°, c={c}, gamma={gamma}, E={E}")
        print(f"  EVA Qa = {eva_qa} kg/cm²")
        print(f"{'─' * 100}")

        # Cap values
        cap_soil = 3.0
        cap_rock_soft = 4.0
        cap_rock_hard = 4.5
        cap_rock_max = 5.0
        is_rock = c >= 0.5

        hypotheses = []

        # H1: Simple Terzaghi-Peck with Nb
        qa_tp = terzaghi_peck_qa(Nb)
        hypotheses.append(("H1: T-P Nb/12", qa_tp, f"Nb={Nb}, Fw=1, Fd=1.27"))

        # H2: T-P with Nb, capped at 3.0
        qa_tp_cap = min(qa_tp, cap_soil)
        hypotheses.append(("H2: T-P Nb/12 cap 3.0", qa_tp_cap, f"min({qa_tp}, 3.0)"))

        # H3: T-P with N20 directly (not Nb)
        qa_tp_n20 = terzaghi_peck_qa(N20)
        hypotheses.append(("H3: T-P N20/12", qa_tp_n20, f"N20={N20}"))

        # H4: T-P N20 capped 3.0
        qa_tp_n20_cap = min(qa_tp_n20, cap_soil)
        hypotheses.append(("H4: T-P N20/12 cap 3.0", qa_tp_n20_cap, f"min({qa_tp_n20}, 3.0)"))

        # H5: Full Terzaghi formula (no T-P override)
        qa_full = full_terzaghi_qa(phi, c, gamma)
        hypotheses.append(("H5: Full Terzaghi/F=3", qa_full, f"phi={phi}, c={c}"))

        # H6: Full Terzaghi capped
        cap = cap_rock_hard if is_rock else cap_soil
        qa_full_cap = min(qa_full, cap)
        hypotheses.append(("H6: Full Terzaghi cap", qa_full_cap, f"cap={cap}"))

        # H7: Eva just uses the cap directly
        hypotheses.append(("H7: Direct cap (soil=3.0)", cap_soil, "always 3.0"))

        # H8: T-P Nb, cap depends on rock/soil
        if is_rock:
            hypotheses.append(("H8: T-P Nb cap rock", min(qa_tp, cap_rock_hard), f"rock cap {cap_rock_hard}"))

        # H9: T-P Nb/12 without Fd (no depth correction)
        qa_tp_nofd = Nb / 12
        hypotheses.append(("H9: T-P Nb/12 (no Fd)", round(qa_tp_nofd, 2), "pure Nb/12"))

        # H10: T-P Nb/12 (no Fd), cap 3.0
        hypotheses.append(("H10: T-P Nb/12 noFd cap3", min(round(qa_tp_nofd, 2), cap_soil), f"min({round(qa_tp_nofd, 2)}, 3.0)"))

        # H11: N20/12 without Fd, cap 3.0
        qa_n20_nofd = N20 / 12
        hypotheses.append(("H11: N20/12 noFd cap3", min(round(qa_n20_nofd, 2), cap_soil), f"min({round(qa_n20_nofd, 2)}, 3.0)"))

        # Print results
        print(f"\n  {'Hypothesis':<28} {'Qa calc':>8} {'Eva Qa':>8} {'Dev%':>8} {'Match?':>8}")
        print(f"  {'-'*28} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

        for name, qa_calc, detail in hypotheses:
            if eva_qa != 0:
                dev = round((qa_calc - eva_qa) / eva_qa * 100, 1)
            else:
                dev = 0
            match = "MATCH" if abs(dev) <= 5 else ("CLOSE" if abs(dev) <= 15 else "")
            print(f"  {name:<28} {qa_calc:>8.2f} {eva_qa:>8.2f} {dev:>+7.1f}% {match:>8}")


if __name__ == '__main__':
    main()
