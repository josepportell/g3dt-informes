#!/usr/bin/env python3
"""
Settlement Back-Engineering + E(Nb vs N20) Diagnostic — v2

CORRECTED reference values from Eva's actual signed PDF reports.
Previous version had wrong settlement and N20 values from MEMORY.md.

Tests all plausible Es hypotheses for Schmertmann settlement
and compares E from CTE D.23 using Nb vs N20.

Pure analysis — no production code changes.

Author: Eficients.cat
Date: 2026-02-26
"""

import sys
sys.path.insert(0, "/home/josef/projects/claudecode-job/clients/g3dt")
sys.path.insert(0, "/home/josep/projects/claudecode-job/clients/g3dt")

from automation.cte_geomech import nspt_to_E_kg_cm2, nb_to_qc, TABLE_D23
from automation.terzaghi_calculator import (
    schmertmann_settlement,
    terzaghi_peck_qa,
    FootingShape,
)


# ══════════════════════════════════════════════════════════════════════
# CORRECTED REFERENCE DATA (from Eva's signed PDF reports)
# ══════════════════════════════════════════════════════════════════════
#
# Source: PDF/LLETRA/{expedient}_informe.pdf — Section 4.1 geomech table
# + Section 4.3 Fonamentació (Qa, settlement text)
#
# IMPORTANT corrections vs MEMORY.md / compare_4projects.py:
#   Bell-Lloc: E=650 (not 450), s=1.20 (not 1.50), N=54 in table
#   Rubí:      s=1.50 (not 0.72), N=40 in table
#   Linyola:   foundation on level 2 (rock), s≤1.0 "menyspreables"

# Foundation geometry (all projects use same wording):
# "encastada entre 30-40 cm" → Df ≈ 0.35 m (midpoint)
# B not specified in reports → code default 1.0 m
Df = 0.35  # m (midpoint of 30-40 cm)
B = 1.0    # m (default, not specified in reports)

# ── Eva's signed reports — exact values ──────────────────────────────

PROJECTS = {
    "Bell-Lloc": {
        # PDF: "Nb=25-R, N=54, gamma=2.0, c=0.0, phi=38, E=650"
        # PDF: "Qa=3.0 ... assentaments inferiors a 1.20 cm, immediats"
        # Nb column shows range (25 to Refusal). N column = 54.
        # Interpretation: N20=54 at representative depth, OR Nb=54.
        # If N is N20: Nb=54/0.83=65.1, E_CTE[50+]=1428? Too high.
        # If N is Nb: N20=54×0.83=44.8, E_CTE[25-50]=469. Eva uses 650.
        # Eva's E=650 doesn't match CTE for either interpretation.
        # Eva: "L'agafo com a criteri" — professional judgement for E.
        "nb_range": "25-R",
        "n_table": 54,          # Value in "N" column of Eva's report
        "n20_likely": 40,       # From DPSH extraction (used in compare_4projects.py)
        "nb_likely": 48.2,      # 40/0.83
        "gamma": 2.0,
        "cohesion": 0.0,
        "phi": 38,
        "E_eva": 650,
        "Qa_eva": 3.0,
        "settlement_eva": 1.20,
        "K30_eva": 6.0,
        "soil_type": "granular",
        "foundation_text": "sabates aïllades/corregudes o llosa",
    },
    "Rubí": {
        # PDF: "Nb=47-R, N=40, gamma=2.0, c=0.05, phi=39, E=450"
        # PDF: "Qa=3.50 ... assentaments iguals o inferiors a 1.50 cm"
        "nb_range": "47-R",
        "n_table": 40,          # N20 = 40 (from N column)
        "n20_likely": 40,       # Consistent with N column
        "nb_likely": 48.2,      # 40/0.83
        "gamma": 2.0,
        "cohesion": 0.05,
        "phi": 39,
        "E_eva": 450,
        "Qa_eva": 3.50,
        "settlement_eva": 1.50,
        "K30_eva": 6.0,
        "soil_type": "granular",
        "foundation_text": "sabates aïllades/corregudes o llosa",
    },
    "Linyola": {
        # PDF: Level 1 "Nb=13, N=--, gamma=1.90, c=0.05, phi=28, E=100"
        #      Level 2 "Nb=31-R, N=R, gamma=2.20, c=1.0, phi=30, E=>800"
        # PDF: "Qa=3.0 ... assentaments menyspreables o inferiors a 1.0 cm"
        # Foundation: on Level 2 via "pous reomplerts de formigó pobre"
        "nb_range_L1": "13",
        "nb_range_L2": "31-R",
        "n20_likely": 13,       # Level 1 (used for comparison)
        "nb_likely": 15.7,
        "gamma": 1.90,
        "cohesion": 0.05,
        "phi": 28,
        "E_eva": 100,
        "Qa_eva": 3.0,          # on Level 2
        "settlement_eva": 1.0,  # "menyspreables o inferiors a 1.0"
        "K30_eva": None,
        "soil_type": "limo",
        "foundation_text": "sabates + pous (on Level 2 rock)",
        # Level 2 (rock): E>800, Qa=3.0 but founded on rock
        "L2_gamma": 2.20, "L2_c": 1.0, "L2_phi": 30, "L2_E": 800,
    },
    "Castellar": {
        # PDF: 2 levels. Rock foundation.
        # Level 2 (foundation): gamma=2.20, c=1.0, phi=35, E=500
        # Qa=5.0. No settlement reported.
        "n20_likely": 100,      # Refusal (rock)
        "nb_likely": 120.5,
        "gamma": 2.20,
        "cohesion": 1.0,
        "phi": 35,
        "E_eva": 500,
        "Qa_eva": 5.0,
        "settlement_eva": None,
        "K30_eva": 8.0,
        "soil_type": "granular",
        "foundation_text": "rock foundation",
    },
}


# ── Es hypothesis functions ──────────────────────────────────────────

def es_robertson_qc(nb, soil_type, shape):
    """A: Robertson (1983) qc → Es = factor × qc. Current production."""
    qc = nb_to_qc(nb, soil_type)
    factor = 3.5 if shape == FootingShape.STRIP else 2.5
    return factor * qc

def es_cte_d23(n20, shape):
    """B: CTE D.23 E directly as Es."""
    return nspt_to_E_kg_cm2(n20, conservative=True)

def es_eva_E_direct(E_eva, shape):
    """B2: Eva's reported E directly as Es."""
    return E_eva

def es_eva_E_half(E_eva, shape):
    """B3: Eva's E / 2 as Es (common conservative practice)."""
    return E_eva / 2.0

def es_beguemann(n, shape):
    """C: Beguemann from Spt-correlacions.doc."""
    if n > 15:
        return 40 + 12 * (n - 6)
    else:
        return 12 * (n + 6)

def es_bowles(n, shape):
    """D: Bowles from Spt-correlacions.doc."""
    return 10 * (7.5 + 0.5 * n)

def es_dapolonia_nc(n, shape):
    """E: D'Apolonia (NC sands) from Spt-correlacions.doc."""
    return 215 + 10.6 * n

def es_25_n20(n20, shape):
    """F: Es = 2.5 × N20 (or 3.5 for strip)."""
    factor = 3.5 if shape == FootingShape.STRIP else 2.5
    return factor * n20

def es_25_nb(nb, shape):
    """G: Es = 2.5 × Nb (or 3.5 for strip)."""
    factor = 3.5 if shape == FootingShape.STRIP else 2.5
    return factor * nb


# ── Helpers ──────────────────────────────────────────────────────────

def pct_dev(ours, ref):
    if ref is None or ref == 0 or ours is None:
        return None
    return (ours - ref) / ref * 100

def fmt_dev(dev):
    if dev is None:
        return "-"
    sign = "+" if dev >= 0 else ""
    return f"{sign}{dev:.0f}%"

def fmt_val(val, dec=2):
    if val is None:
        return "-"
    return f"{val:.{dec}f}"


# ══════════════════════════════════════════════════════════════════════
# PART 0: REFERENCE DATA MATRIX
# ══════════════════════════════════════════════════════════════════════

def part0_reference_matrix():
    sep = "=" * 120
    print()
    print(sep)
    print("  PART 0: CORRECTED REFERENCE DATA FROM EVA'S SIGNED PDFs")
    print("  Source: PDF/LLETRA/{exp}_informe.pdf — Sections 4.1 + 4.3")
    print(sep)

    print(f"\n  {'Project':<15} {'Nb(range)':>10} {'N(table)':>10} {'gamma':>6} {'c':>6}"
          f" {'phi':>5} {'E':>6} {'Qa':>5} {'s(cm)':>7} {'K30':>5}  Foundation")
    print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*6} {'-'*6}"
          f" {'-'*5} {'-'*6} {'-'*5} {'-'*7} {'-'*5}  {'-'*30}")

    for name, p in PROJECTS.items():
        nb_r = p.get("nb_range", p.get("nb_range_L1", "-"))
        n_t = p.get("n_table", "-")
        print(
            f"  {name:<15} {str(nb_r):>10} {str(n_t):>10} {p['gamma']:>6.2f} {p['cohesion']:>6.2f}"
            f" {p['phi']:>5} {p['E_eva']:>6} {p['Qa_eva']:>5.1f} {fmt_val(p['settlement_eva']):>7}"
            f" {fmt_val(p.get('K30_eva'), 1):>5}  {p['foundation_text']}"
        )

    print(f"\n  Foundation geometry: Df ≈ 0.35 m (30-40 cm), B ≈ 1.0 m (not specified)")
    print(f"  Shape: 'sabates aïllades' = SQUARE in Schmertmann")

    print(f"\n  KEY CORRECTIONS vs MEMORY.md / compare_4projects.py:")
    print(f"  - Bell-Lloc: E=650 (was 450), settlement=1.20 (was 1.50), N_table=54")
    print(f"  - Rubí: settlement=1.50 (was 0.72 — values were SWAPPED)")
    print(f"  - Linyola: settlement≤1.0 'menyspreables', founded on Level 2 rock")
    print()


# ══════════════════════════════════════════════════════════════════════
# PART 1: SETTLEMENT Es HYPOTHESES (Bell-Lloc + Rubí)
# ══════════════════════════════════════════════════════════════════════

def part1_settlement_hypotheses():
    sep = "=" * 140
    thin = "-" * 140

    print()
    print(sep)
    print("  PART 1: SETTLEMENT Es HYPOTHESES")
    print(f"  Foundation: B={B}m, Df={Df}m, SQUARE, gamma=2.0")
    print(f"  Testing each Es formula for Schmertmann (1978) settlement")
    print(sep)

    targets = [
        ("Bell-Lloc", PROJECTS["Bell-Lloc"]),
        ("Rubí", PROJECTS["Rubí"]),
    ]

    # Build hypothesis list: (label, Es_fn(proj, shape) -> float)
    hypotheses = [
        ("A: Robertson qc (current)",  lambda p, s: es_robertson_qc(p["nb_likely"], p["soil_type"], s)),
        ("B: CTE D.23(N20) direct",    lambda p, s: es_cte_d23(p["n20_likely"], s)),
        ("B2: Eva E direct as Es",      lambda p, s: es_eva_E_direct(p["E_eva"], s)),
        ("B3: Eva E/2 as Es",           lambda p, s: es_eva_E_half(p["E_eva"], s)),
        ("C: Beguemann(N20)",           lambda p, s: es_beguemann(p["n20_likely"], s)),
        ("C': Beguemann(Nb)",           lambda p, s: es_beguemann(p["nb_likely"], s)),
        ("D: Bowles(N20)",              lambda p, s: es_bowles(p["n20_likely"], s)),
        ("D': Bowles(Nb)",              lambda p, s: es_bowles(p["nb_likely"], s)),
        ("E: D'Apolonia NC(N20)",       lambda p, s: es_dapolonia_nc(p["n20_likely"], s)),
        ("F: 2.5×N20",                  lambda p, s: es_25_n20(p["n20_likely"], s)),
        ("G: 2.5×Nb",                   lambda p, s: es_25_nb(p["nb_likely"], s)),
    ]

    for name, proj in targets:
        Qa = proj["Qa_eva"]
        s_eva = proj["settlement_eva"]
        gamma = proj["gamma"]

        print(f"\n{thin}")
        print(f"  {name}: N20={proj['n20_likely']}, Nb={proj['nb_likely']:.1f}, "
              f"E(Eva)={proj['E_eva']}, Qa={Qa}, s(Eva)={s_eva} cm")
        print(thin)

        # Test both SQUARE and STRIP
        print(
            f"  {'Hypothesis':<30} {'Es(sq)':>8} {'s_sq':>7} {'dev_sq':>7}"
            f"  {'Es(str)':>8} {'s_str':>7} {'dev_str':>7}"
            f"   Match?"
        )
        print(f"  {'-'*30} {'-'*8} {'-'*7} {'-'*7}  {'-'*8} {'-'*7} {'-'*7}   {'-'*15}")

        best_name = None
        best_abs_dev = 999

        for label, es_fn in hypotheses:
            Es_sq = es_fn(proj, FootingShape.SQUARE)
            Es_str = es_fn(proj, FootingShape.STRIP)

            s_sq = schmertmann_settlement(
                q_net=Qa, B=B, Df=Df, Es=Es_sq, gamma=gamma, shape=FootingShape.SQUARE,
            )
            s_str = schmertmann_settlement(
                q_net=Qa, B=B, Df=Df, Es=Es_str, gamma=gamma, shape=FootingShape.STRIP,
            )

            dev_sq = pct_dev(s_sq, s_eva)
            dev_str = pct_dev(s_str, s_eva)

            # Track best
            for dv, sl in [(dev_sq, "sq"), (dev_str, "str")]:
                if dv is not None and abs(dv) < best_abs_dev:
                    best_abs_dev = abs(dv)
                    best_name = f"{label} ({sl})"

            flag = ""
            if dev_sq is not None and abs(dev_sq) <= 15:
                flag = f"*** CLOSE (sq)"
            elif dev_str is not None and abs(dev_str) <= 15:
                flag = f"*** CLOSE (str)"

            print(
                f"  {label:<30} {Es_sq:>8.0f} {s_sq:>7.3f} {fmt_dev(dev_sq):>7}"
                f"  {Es_str:>8.0f} {s_str:>7.3f} {fmt_dev(dev_str):>7}"
                f"   {flag}"
            )

        print(f"\n  >>> Best: {best_name} (dev={fmt_dev(best_abs_dev if best_abs_dev < 999 else None)})")

    print()


# ══════════════════════════════════════════════════════════════════════
# PART 2: E(Nb) vs E(N20) (all 4 projects)
# ══════════════════════════════════════════════════════════════════════

def part2_e_nb_vs_n20():
    sep = "=" * 110
    print()
    print(sep)
    print("  PART 2: E from CTE D.23 — Nb vs N20")
    print(sep)

    print(
        f"\n  {'Project':<15} {'N20':>5} {'Nb':>6} {'E(N20)':>8} {'E(Nb)':>8} {'E(Eva)':>8}"
        f" {'dev(N20)':>9} {'dev(Nb)':>9}   Winner"
    )
    print(
        f"  {'-'*15} {'-'*5} {'-'*6} {'-'*8} {'-'*8} {'-'*8}"
        f" {'-'*9} {'-'*9}   {'-'*10}"
    )

    for name, proj in PROJECTS.items():
        n20 = proj["n20_likely"]
        nb = proj["nb_likely"]
        eva_E = proj["E_eva"]

        if n20 >= 100:  # Rock
            print(f"  {name:<15} {n20:>5} {nb:>6.1f} {'(rock)':>8} {'(rock)':>8} {eva_E:>8}"
                  f" {'N/A':>9} {'N/A':>9}   rock=fixed")
            continue

        E_n20 = nspt_to_E_kg_cm2(n20, conservative=True)
        E_nb = nspt_to_E_kg_cm2(nb, conservative=True)

        dev_n20 = pct_dev(E_n20, eva_E)
        dev_nb = pct_dev(E_nb, eva_E)

        winner = "N20" if abs(dev_n20) < abs(dev_nb) else ("Nb" if abs(dev_nb) < abs(dev_n20) else "tie")

        print(
            f"  {name:<15} {n20:>5} {nb:>6.1f} {E_n20:>8.0f} {E_nb:>8.0f} {eva_E:>8}"
            f" {fmt_dev(dev_n20):>9} {fmt_dev(dev_nb):>9}   {winner}"
        )

    # CTE bracket detail
    print(f"\n  CTE D.23 bracket detail:")
    print(f"  {'Project':<15} {'N20':>5} {'bracket(N20)':<28} {'Nb':>6} {'bracket(Nb)':<28}")
    print(f"  {'-'*15} {'-'*5} {'-'*28} {'-'*6} {'-'*28}")

    for name, proj in PROJECTS.items():
        if proj["n20_likely"] >= 100:
            continue
        n20 = proj["n20_likely"]
        nb = proj["nb_likely"]
        br_n20 = next(
            (f"[{lo},{hi}) E={emin}-{emax} MN/m²"
             for lo, hi, _, _, _, emin, emax in TABLE_D23 if lo <= n20 < hi), "?")
        br_nb = next(
            (f"[{lo},{hi}) E={emin}-{emax} MN/m²"
             for lo, hi, _, _, _, emin, emax in TABLE_D23 if lo <= nb < hi), "?")
        print(f"  {name:<15} {n20:>5} {br_n20:<28} {nb:>6.1f} {br_nb:<28}")

    print()


# ══════════════════════════════════════════════════════════════════════
# PART 3: BACK-ENGINEERING (reverse solve for Es)
# ══════════════════════════════════════════════════════════════════════

def part3_back_engineering():
    sep = "=" * 120
    thin = "-" * 120

    print()
    print(sep)
    print("  PART 3: BACK-ENGINEERING — What Es does Eva actually use?")
    print(f"  Reverse-solve: Es = C1 × Qa × Iz_integral / target_settlement")
    print(f"  Foundation: B={B}m, Df={Df}m")
    print(sep)

    targets = [
        ("Bell-Lloc", PROJECTS["Bell-Lloc"]),
        ("Rubí", PROJECTS["Rubí"]),
    ]

    # Collect for cross-project comparison
    cross_data = []

    for name, proj in targets:
        s_target = proj["settlement_eva"]
        Qa = proj["Qa_eva"]
        gamma = proj["gamma"]
        n20 = proj["n20_likely"]
        nb = proj["nb_likely"]
        E_eva = proj["E_eva"]

        print(f"\n{thin}")
        print(f"  {name}: target s={s_target} cm, Qa={Qa}, N20={n20}, Nb={nb:.1f}, E(Eva)={E_eva}")
        print(thin)

        for shape_name, shape, Iz_factor in [
            ("SQUARE", FootingShape.SQUARE, 0.525),
            ("STRIP", FootingShape.STRIP, 1.10),
        ]:
            B_cm = B * 100
            sigma_v0 = gamma * Df * 0.1
            C1 = max(1.0 - 0.5 * sigma_v0 / Qa, 0.5)
            Iz_integral = Iz_factor * B_cm

            Es_implied = C1 * Qa * Iz_integral / s_target

            print(f"\n  {shape_name}: C1={C1:.4f}, Iz={Iz_integral:.1f}cm → Es_implied = {Es_implied:.1f} kg/cm²")

            # What each relationship implies
            print(f"    {'Formula':<30} {'Value':>25}   {'Plausible?'}")
            print(f"    {'-'*30} {'-'*25}   {'-'*20}")

            k_qc = 2.5 if shape == FootingShape.SQUARE else 3.5

            # qc/N ratios
            qc_impl = Es_implied / k_qc
            r_n20 = qc_impl / n20
            r_nb = qc_impl / nb
            print(f"    {'Es=k×qc, qc=r×N20':<30} {'qc/N20 = %.2f' % r_n20:>25}   {'YES (1-8)' if 1.0 <= r_n20 <= 8.0 else 'LOW' if r_n20 < 1.0 else 'HIGH'}")
            print(f"    {'Es=k×qc, qc=r×Nb':<30} {'qc/Nb = %.2f' % r_nb:>25}   {'YES (1-8)' if 1.0 <= r_nb <= 8.0 else 'LOW' if r_nb < 1.0 else 'HIGH'}")

            # vs Eva's E
            scale_E = Es_implied / E_eva
            print(f"    {'Es = scale × E(Eva)':<30} {'scale = %.3f' % scale_E:>25}   {'~E/2!' if 0.4 <= scale_E <= 0.6 else '~E/3!' if 0.28 <= scale_E <= 0.38 else '~E!' if 0.85 <= scale_E <= 1.15 else ''}")

            # vs CTE D.23
            E_cte = nspt_to_E_kg_cm2(n20, conservative=True)
            scale_cte = Es_implied / E_cte
            print(f"    {'Es = scale × E_CTE(N20)':<30} {'scale = %.3f' % scale_cte:>25}   {'~1.0!' if 0.85 <= scale_cte <= 1.15 else ''}")

            # vs Bowles
            bow = es_bowles(n20, shape)
            scale_bow = Es_implied / bow
            print(f"    {'Es/Bowles(N20)':<30} {'ratio = %.3f' % scale_bow:>25}   {'~1.0!' if 0.85 <= scale_bow <= 1.15 else ''}")

            # vs Beguemann
            beg = es_beguemann(n20, shape)
            scale_beg = Es_implied / beg
            print(f"    {'Es/Beguemann(N20)':<30} {'ratio = %.3f' % scale_beg:>25}   {'~1.0!' if 0.85 <= scale_beg <= 1.15 else ''}")

            # Simple k×N
            k_n20 = Es_implied / n20
            k_nb = Es_implied / nb
            print(f"    {'Es = k × N20':<30} {'k = %.2f' % k_n20:>25}")
            print(f"    {'Es = k × Nb':<30} {'k = %.2f' % k_nb:>25}")

            cross_data.append({
                "name": name, "shape": shape_name, "Es_impl": Es_implied,
                "n20": n20, "nb": nb, "E_eva": E_eva,
                "qc_over_n20": r_n20, "qc_over_nb": r_nb,
                "scale_E_eva": scale_E, "scale_cte": scale_cte,
                "k_n20": k_n20, "k_nb": k_nb,
            })

    # Cross-project consistency
    print(f"\n{'=' * 120}")
    print("  CROSS-PROJECT CONSISTENCY")
    print(f"{'=' * 120}")

    print(f"\n  {'Project':<12} {'Shape':<7} {'Es_impl':>8} {'E(Eva)':>7} {'Es/E_eva':>9}"
          f" {'qc/N20':>8} {'qc/Nb':>7} {'k(N20)':>7} {'k(Nb)':>7}")
    print(f"  {'-'*12} {'-'*7} {'-'*8} {'-'*7} {'-'*9} {'-'*8} {'-'*7} {'-'*7} {'-'*7}")

    for d in cross_data:
        print(
            f"  {d['name']:<12} {d['shape']:<7} {d['Es_impl']:>8.0f} {d['E_eva']:>7}"
            f" {d['scale_E_eva']:>9.3f} {d['qc_over_n20']:>8.2f} {d['qc_over_nb']:>7.2f}"
            f" {d['k_n20']:>7.2f} {d['k_nb']:>7.2f}"
        )

    print(f"\n  FINDING: Look at Es/E(Eva) column — is there a consistent ratio?")
    sq_data = [d for d in cross_data if d["shape"] == "SQUARE"]
    str_data = [d for d in cross_data if d["shape"] == "STRIP"]
    if len(sq_data) == 2:
        print(f"    SQUARE: Es/E_eva = {sq_data[0]['scale_E_eva']:.3f} (BL) vs {sq_data[1]['scale_E_eva']:.3f} (Rubí)")
        avg_sq = (sq_data[0]['scale_E_eva'] + sq_data[1]['scale_E_eva']) / 2
        print(f"    Average: {avg_sq:.3f} → Eva's Es ≈ {avg_sq:.2f} × E_report")
    if len(str_data) == 2:
        print(f"    STRIP:  Es/E_eva = {str_data[0]['scale_E_eva']:.3f} (BL) vs {str_data[1]['scale_E_eva']:.3f} (Rubí)")
        avg_str = (str_data[0]['scale_E_eva'] + str_data[1]['scale_E_eva']) / 2
        print(f"    Average: {avg_str:.3f} → Eva's Es ≈ {avg_str:.2f} × E_report")

    print()


# ══════════════════════════════════════════════════════════════════════
# PART 4: COMPREHENSIVE PROJECT MATRIX
# ══════════════════════════════════════════════════════════════════════

def part4_project_matrix():
    sep = "=" * 130
    print()
    print(sep)
    print("  PART 4: COMPREHENSIVE PROJECT MATRIX — For human analysis")
    print(sep)

    # Row per project, columns grouped by theme
    print(f"""
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                           COMPLETE DATA MATRIX — Eva's Reports vs Our Calculations                             │
  ├─────────────┬──────────┬──────┬──────┬─────┬──────┬──────┬──────┬──────┬──────┬─────────────────────────────────┤
  │ Project     │ Material │ N20  │  Nb  │gamma│  c   │ phi  │  E   │  Qa  │ s(cm)│ Notes                           │
  ├─────────────┼──────────┼──────┼──────┼─────┼──────┼──────┼──────┼──────┼──────┼─────────────────────────────────┤
  │ Bell-Lloc   │ Graves   │  40* │ 48.2 │ 2.0 │ 0.00 │  38  │  650 │ 3.0  │ 1.20 │ *N_table=54, Nb_range=25-R     │
  │ Rubí        │ Graves   │  40  │ 48.2 │ 2.0 │ 0.05 │  39  │  450 │ 3.50 │ 1.50 │ Qa>3.0 cap (c=0.05?)          │
  │ Linyola L1  │ Llims    │  13  │ 15.7 │1.90 │ 0.05 │  28  │  100 │  -   │  -   │ Not foundation level           │
  │ Linyola L2  │ Lutites  │  R   │ 31-R │2.20 │ 1.00 │  30  │ >800 │ 3.0  │ ≤1.0 │ Rock. "menyspreables"          │
  │ Castellar L1│ Llims    │  12  │ 14.5 │1.90 │ 0.00 │  28  │  -   │  -   │  -   │ Not foundation level           │
  │ Castellar L2│ Roca     │  R   │  R   │2.20 │ 1.00 │  35  │  500 │ 5.0  │  -   │ Rock. No settlement            │
  └─────────────┴──────────┴──────┴──────┴─────┴──────┴──────┴──────┴──────┴──────┴─────────────────────────────────┘""")

    print(f"""
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                        SETTLEMENT DEEP DIVE — Only projects with settlement data                               │
  ├──────────┬──────┬──────┬──────┬──────┬────────────────────────────────────────────────────────────────────────── │
  │          │      │      │      │ s_eva│ Es_implied (back-engineered from Eva's settlement)                       │
  │ Project  │ N20  │E(Eva)│Qa    │ (cm) │ SQUARE          │ STRIP           │ vs E(Eva)  │ vs E(Eva)              │
  │          │      │      │      │      │ Es    k(N20)    │ Es    k(N20)    │ sq         │ strip                  │
  ├──────────┼──────┼──────┼──────┼──────┼─────────────────┼─────────────────┼────────────┼────────────────────────┤""")

    for name in ["Bell-Lloc", "Rubí"]:
        p = PROJECTS[name]
        Qa = p["Qa_eva"]; s_eva = p["settlement_eva"]; n20 = p["n20_likely"]
        gamma = p["gamma"]; E_eva = p["E_eva"]

        sigma_v0 = gamma * Df * 0.1
        C1 = max(1.0 - 0.5 * sigma_v0 / Qa, 0.5)
        B_cm = B * 100

        Es_sq = C1 * Qa * (0.525 * B_cm) / s_eva
        Es_str = C1 * Qa * (1.10 * B_cm) / s_eva

        k_sq = Es_sq / n20
        k_str = Es_str / n20

        ratio_sq = Es_sq / E_eva
        ratio_str = Es_str / E_eva

        print(f"  │ {name:<8} │  {n20:>3} │ {E_eva:>4} │{Qa:>5.1f} │{s_eva:>5.2f} │"
              f" {Es_sq:>5.0f}  k={k_sq:>5.2f}   │ {Es_str:>5.0f}  k={k_str:>5.2f}   │"
              f" {ratio_sq:>10.3f} │ {ratio_str:>10.3f}              │")

    print(f"  └──────────┴──────┴──────┴──────┴──────┴─────────────────┴─────────────────┴────────────────────────────────┘")

    print(f"""
  KEY OBSERVATIONS:
  1. Bell-Lloc and Rubí have SAME N20=40 but DIFFERENT E (650 vs 450)
     → Eva adjusts E by professional judgement, not formula alone
  2. Es_implied/E(Eva) ratio:
     SQUARE: BL={PROJECTS["Bell-Lloc"]["settlement_eva"]}, Rubí={PROJECTS["Rubí"]["settlement_eva"]}
     → Check if ratio is consistent (would indicate Es = fraction × E_report)
  3. Rubí Qa=3.50 > soil cap 3.0
     → c=0.05 might push it, or Eva uses higher cap for dense gravels
  4. Linyola settlement "menyspreables" on ROCK → no real settlement calc needed
  5. Bell-Lloc "N=54" in Eva's table while we extract N20≈40 from DPSH
     → Ambiguity: is N_table the SPT value? Or a different representative N20?
""")

    print()


# ══════════════════════════════════════════════════════════════════════
# PART 5: PROFESSIONAL JUDGEMENT ANALYSIS
# ══════════════════════════════════════════════════════════════════════

def part5_professional_judgement():
    sep = "=" * 120
    print()
    print(sep)
    print("  PART 5: WHAT WOULD A QUALIFIED GEOTECHNICAL ENGINEER DO?")
    print(sep)

    print("""
  CONTEXT: Eva has ~20+ years experience. She said:
  - "L'agafo com a criteri després de molts estudis" (E is professional judgement)
  - "Agafa la taula, ja ho ajustarem" (start with table, she'll adjust)
  - Settlement is a SERVICEABILITY CHECK (must be < 2.54 cm / 1 inch)

  ANALYSIS OF WHAT DRIVES DIFFERENCES:

  ┌─────────────────────────────────────────────────────────────────────┐
  │ Factor           │ Bell-Lloc        │ Rubí             │ Impact    │
  ├──────────────────┼──────────────────┼──────────────────┼───────────┤
  │ Soil type        │ Graves (matriu   │ Graves i sorres  │ Similar   │
  │                  │ sorrenca carbon.)│                  │           │
  │ N20 (our extract)│ 40               │ 40               │ Same      │
  │ N (Eva's table)  │ 54               │ 40               │ DIFFERENT │
  │ E (Eva)          │ 650              │ 450              │ DIFFERENT │
  │ phi              │ 38               │ 39               │ Similar   │
  │ Qa               │ 3.0              │ 3.50             │ Different │
  │ c (cohesion)     │ 0.0              │ 0.05             │ Minor     │
  │ settlement       │ 1.20 cm          │ 1.50 cm          │ Different │
  │ geology          │ carbonated       │ standard         │ DIFFERENT │
  └─────────────────────────────────────────────────────────────────────┘

  KEY INSIGHT: Bell-Lloc has "graves en matriu sorrenca CARBONATADES"
  (carbonated gravel matrix). Carbonation = cementation = stiffer material.
  This explains why Eva gives it E=650 vs E=450 for Rubí's uncemented gravels.

  A QUALIFIED ENGINEER'S DECISION PROCESS:

  1. E SELECTION (deformation modulus):
     - Start with CTE D.23 bracket: N20=40 → [25,50) → E=40-100 MN/m²
     - Conservative CTE = 46 MN/m² = 469 kg/cm² ← Rubí's E=450 is close
     - Bell-Lloc: carbonated → stiffer → push toward upper bracket = 650
     - Eva's approach: CTE as starting point, then adjust UP for cementation
       and DOWN for disturbed/loose soils

  2. Qa SELECTION:
     - Terzaghi theoretical: typically gives Qa >> 3.0 for phi=38-39
     - Terzaghi-Peck empirical: N/12 with corrections
     - Cap at 3.0 for normal soil, higher for cemented/dense
     - Rubí Qa=3.50: maybe T-P gives exactly 3.5, or Eva raises cap

  3. SETTLEMENT CALCULATION:
     - Purpose: verify < 2.54 cm (1 inch standard limit)
     - Eva likely uses a SIMPLE formula with conservative Es
     - NOT trying to predict exact settlement — just confirm it's acceptable
     - Both 1.20 and 1.50 are safely below 2.54 cm limit

  4. THE PRACTICAL TRUTH:
     - Settlement precision beyond ±50% is illusory in geotechnics
     - What matters: "is it well below the limit?" → YES for both
     - The EXACT formula matters less than the order of magnitude
     - Eva's values are rounded (1.20, 1.50) = professionally presented

  RECOMMENDATION FOR AUTOMATION:
  → Don't try to reverse-engineer Eva's exact Es formula
  → Instead: use a REASONABLE Es that gives settlements in the right range
  → Flag for Eva's review if settlement > 1.5 cm
  → Let Eva adjust Es in the wizard if she wants different values
""")

    print()


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    part0_reference_matrix()
    part1_settlement_hypotheses()
    part2_e_nb_vs_n20()
    part3_back_engineering()
    part4_project_matrix()
    part5_professional_judgement()
