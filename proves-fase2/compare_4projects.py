#!/usr/bin/env python3
"""
4-Project Geotechnical Parameter Comparison
Computes gamma, phi, E, Qa, settlement, K30 using our CTE functions
and compares against Eva's reference values.

Projects: Bell-Lloc, Castellar, Rubi, Linyola
"""

import sys
sys.path.insert(0, "/home/josep/projects/claudecode-job/clients/g3dt")

from automation.cte_geomech import (
    nspt_to_phi,
    nspt_to_E_kg_cm2,
    nspt_to_gamma_g_cm3,
    is_rock,
    rock_params_default,
)
from automation.terzaghi_calculator import TerzaghiCalculator, FootingShape


# ── Project definitions ──────────────────────────────────────────────

PROJECTS = [
    {
        "name": "Bell-Lloc (4001612)",
        "description": "Flat terrain, granular (graves i sorres)",
        "layers": [
            {
                "label": "Graves i sorres",
                "n20": 40,
                "soil_type": "granular",
                "cohesion": 0.0,
                "is_foundation": True,
                "is_rock": False,
                "eva": {
                    "gamma": 2.0,
                    "phi": 38,
                    "cohesion": 0.0,
                    "E": 650,
                    "Qa": 3.0,
                    "settlement_cm": 1.20,
                    "K30": 6.0,
                },
            }
        ],
    },
    {
        "name": "Castellar (3001621)",
        "description": "Sloped terrain, 2 levels",
        "layers": [
            {
                "label": "Llims argilosos (soil level)",
                "n20": 12,
                "soil_type": "limo",
                "cohesion": 0.0,
                "is_foundation": False,
                "is_rock": False,
                "eva": {
                    "gamma": 1.90,
                    "phi": 28,
                    "cohesion": None,
                    "E": None,
                    "Qa": None,
                    "settlement_cm": None,
                    "K30": None,
                },
            },
            {
                "label": "Roca fracturada (foundation level)",
                "n20": 100,
                "soil_type": "granular",  # overridden by is_rock
                "cohesion": 1.0,
                "is_foundation": True,
                "is_rock": True,
                "eva": {
                    "gamma": 2.20,
                    "phi": 35,
                    "cohesion": 1.0,
                    "E": 500,
                    "Qa": 5.0,
                    "settlement_cm": None,
                    "K30": 8.0,
                },
            },
        ],
    },
    {
        "name": "Rubi (3001631)",
        "description": "Flat terrain, granular (graves i sorres)",
        "layers": [
            {
                "label": "Graves i sorres",
                "n20": 40,  # corrected from PDF (was 43)
                "soil_type": "granular",
                "cohesion": 0.05,
                "is_foundation": True,
                "is_rock": False,
                "eva": {
                    "gamma": 2.0,
                    "phi": 39,
                    "cohesion": 0.05,
                    "E": 450,
                    "Qa": 3.50,
                    "settlement_cm": 1.50,
                    "K30": 6.0,
                },
            }
        ],
    },
    {
        "name": "Linyola (4001607)",
        "description": "Flat terrain, 2 levels",
        "layers": [
            {
                "label": "Llims argilosos (foundation level)",
                "n20": 13,
                "soil_type": "limo",
                "cohesion": 0.05,
                "is_foundation": True,
                "is_rock": False,
                "eva": {
                    "gamma": 1.90,
                    "phi": 28,
                    "cohesion": 0.05,
                    "E": 100,
                    "Qa": 2.0,
                    "settlement_cm": None,
                    "K30": None,
                },
            },
            {
                "label": "Graves (deeper level)",
                "n20": 40,
                "soil_type": "granular",
                "cohesion": 0.0,
                "is_foundation": False,
                "is_rock": False,
                "eva": {
                    "gamma": 2.0,
                    "phi": 38,
                    "cohesion": None,
                    "E": None,
                    "Qa": None,
                    "settlement_cm": None,
                    "K30": None,
                },
            },
        ],
    },
]


# ── Compute our values ───────────────────────────────────────────────

def compute_layer(layer: dict) -> dict:
    """Compute geotechnical parameters for one layer."""
    n20 = layer["n20"]
    nb = n20 / 0.83  # Eva: "imprescindible, DPSH → Nb dividint per 0.83"
    soil_type = layer["soil_type"]
    cohesion = layer["cohesion"]
    is_foundation = layer["is_foundation"]

    # --- gamma ---
    if layer["is_rock"]:
        rock = rock_params_default()
        gamma = rock["gamma"]
    else:
        gamma = nspt_to_gamma_g_cm3(n20, soil_type)

    # --- phi (uses Nb + Schmertmann soil_type correction) ---
    if layer["is_rock"]:
        phi = rock_params_default()["phi"]
    else:
        phi = nspt_to_phi(nb, soil_type)

    # --- E (uses Nb) ---
    if layer["is_rock"]:
        E = rock_params_default()["E"]
    else:
        E = nspt_to_E_kg_cm2(n20, conservative=True)

    # --- K30: E/75 for granular, E/60 for rock (with cohesion) ---
    if layer["is_rock"]:
        K30 = round(E / 60, 2)
    elif soil_type == "granular":
        K30 = round(E / 75, 2)
    else:
        K30 = None  # not computed for cohesive in general

    # --- Qa and settlement (only for foundation layer) ---
    Qa = None
    settlement_cm = None
    qu = None
    if is_foundation:
        calc = TerzaghiCalculator(
            phi=phi,
            cohesion=cohesion,
            gamma=gamma,
            safety_factor=3,
        )
        result = calc.calculate_qa(
            B=1.2,
            Df=0.6,
            shape=FootingShape.SQUARE,
            E=E,
            nspt=nb,
            is_granular=(soil_type not in ('limo', 'arcilla', 'cohesive')),
            soil_type=soil_type,
        )
        Qa = result.Qa
        settlement_cm = result.settlement_cm
        qu = result.qu

    return {
        "gamma": gamma,
        "phi": phi,
        "E": E,
        "Qa": Qa,
        "settlement_cm": settlement_cm,
        "qu": qu,
        "K30": K30,
    }


def pct_dev(ours, eva):
    """Percent deviation: (ours - eva) / eva * 100."""
    if eva is None or ours is None:
        return None
    if eva == 0:
        return None
    return (ours - eva) / eva * 100


def fmt_val(val, decimals=2):
    """Format a value or return '-' if None."""
    if val is None:
        return "-"
    return f"{val:.{decimals}f}"


def fmt_dev(dev):
    """Format deviation with sign or '-'."""
    if dev is None:
        return "-"
    sign = "+" if dev >= 0 else ""
    return f"{sign}{dev:.1f}%"


# ── Main ─────────────────────────────────────────────────────────────

def main():
    sep = "=" * 120
    thin = "-" * 120

    print()
    print(sep)
    print("  4-PROJECT GEOTECHNICAL PARAMETER COMPARISON")
    print("  Our CTE functions vs Eva's reference values")
    print("  Foundation params: B=1.2m, Df=0.6m, SQUARE, F=3")
    print(sep)

    for proj in PROJECTS:
        print(f"\n{thin}")
        print(f"  PROJECT: {proj['name']}")
        print(f"  {proj['description']}")
        print(thin)

        # Header
        print(
            f"  {'Layer':<35} {'Param':<10} {'Our Value':>10} {'Eva Value':>10} {'Deviation':>10}   Notes"
        )
        print(f"  {'-'*35} {'-'*10} {'-'*10} {'-'*10} {'-'*10}   {'-'*20}")

        for layer in proj["layers"]:
            ours = compute_layer(layer)
            eva = layer["eva"]
            label = layer["label"]

            params = [
                ("gamma", "g/cm3", 2),
                ("phi", "deg", 1),
                ("E", "kg/cm2", 0),
                ("Qa", "kg/cm2", 2),
                ("settlement_cm", "cm", 2),
                ("K30", "MN/m3", 2),
            ]

            for i, (key, unit, dec) in enumerate(params):
                our_val = ours[key]
                eva_val = eva.get(key)
                dev = pct_dev(our_val, eva_val)

                lbl = label if i == 0 else ""
                param_str = f"{key} ({unit})"

                # Notes for significant deviations
                note = ""
                if dev is not None and abs(dev) > 5:
                    note = "<-- MISMATCH"
                elif dev is not None and abs(dev) <= 1:
                    note = "OK"
                elif dev is not None:
                    note = "~close"

                print(
                    f"  {lbl:<35} {param_str:<16} {fmt_val(our_val, dec):>10} {fmt_val(eva_val, dec):>10} {fmt_dev(dev):>10}   {note}"
                )

            # Print Terzaghi detail for foundation layers
            if layer["is_foundation"] and ours["Qa"] is not None:
                print(f"  {'':35} {'qu (kg/cm2)':<16} {fmt_val(ours['qu'], 2):>10}")

            print()

    # ── Summary table ────────────────────────────────────────────
    print(sep)
    print("  SUMMARY: Foundation-level comparison (only foundation layers)")
    print(sep)
    print(
        f"  {'Project':<25} {'gamma':>8} {'phi':>8} {'E':>8} {'Qa':>8} {'settl':>8} {'K30':>8}"
    )
    print(
        f"  {'':25} {'dev%':>8} {'dev%':>8} {'dev%':>8} {'dev%':>8} {'dev%':>8} {'dev%':>8}"
    )
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for proj in PROJECTS:
        for layer in proj["layers"]:
            if not layer["is_foundation"]:
                continue
            ours = compute_layer(layer)
            eva = layer["eva"]

            devs = {}
            for key in ["gamma", "phi", "E", "Qa", "settlement_cm", "K30"]:
                devs[key] = pct_dev(ours[key], eva.get(key))

            name = proj["name"][:25]
            print(
                f"  {name:<25}"
                f" {fmt_dev(devs['gamma']):>8}"
                f" {fmt_dev(devs['phi']):>8}"
                f" {fmt_dev(devs['E']):>8}"
                f" {fmt_dev(devs['Qa']):>8}"
                f" {fmt_dev(devs['settlement_cm']):>8}"
                f" {fmt_dev(devs['K30']):>8}"
            )

    print(f"\n{sep}")
    print("  NOTES:")
    print("  - gamma uses fixed CTE D.27 values by soil type (not N20 interpolation)")
    print("  - phi uses Nb (N20/0.83) + Schmertmann (1970) soil_type correction + CTE 4.1")
    print("  - E uses N20 (not Nb) + CTE Table D.23 conservative (min + 10% of range)")
    print("  - Rock params use rock_params_default() (gamma=2.20, phi=35, E=500, c=1.0)")
    print("  - K30 = E/75 (granular) or E/60 (rock)")
    print("  - Qa via Terzaghi: qu = c*Nc*sc + gamma*Df*Nq*sq + 0.5*gamma*B*Ngamma*sgamma")
    print(f"{sep}\n")


if __name__ == "__main__":
    main()
