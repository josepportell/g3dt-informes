# Plan: N20 Averaging Method & First-Run Correctness

Created: 2026-03-29
Status: Investigation complete, ready for implementation decisions

## The Core Expectation

> 95% of the time, Eva opens a fresh project (no user_data.json), the wizard
> shows correct values, she hits Generate, and the report is correct.
> She only edits fields the system couldn't find in the project files.

**Current reality:** 35.8% of benchmark values match Eva's on first run. The
single biggest contributor to the gap is **dpsh_avg_n20**, which cascades into
Nb, phi, E, Qa, settlement, and K30 — affecting 7+ fields per project.

---

## Problem 1: N20 Averaging Method

### What our pipeline does

```python
# dpsh_extractor.py:139-146
overall_average_n20 = sum(ALL N20 readings) / count(ALL readings)
```

Simple arithmetic mean of **every** N20 value from **every** DPSH test,
including refusal values (N20=100). For multi-level projects, report_generator
uses `soil_levels[-1].n20_average` (deepest level), but that still includes
refusal-zone readings within the depth range.

### What Eva does

Eva uses **professional judgment** to determine the representative N20 for the
founding soil. She looks at the DPSH profile and mentally selects the "stable
zone" before values ramp toward refusal.

### Evidence: 5 projects, every strategy tested

```
Strategy                       Bell-Llo Castella     Rubí  Linyola Alcoletg    RMSE
------------------------------------------------------------------------------------------
Overall avg (CURRENT)           36.7(+75%)  38.1(+172%)  39.5(-1%)  29.2(+224%)  21.7(+441%)   236.7
Excl refusal (N20<100)          28.8(+37%)  19.1(+36%)  36.0(-10%)  21.8(+143%)   9.9(+148%)    94.7
Excl refusal (N20<80)           25.4(+21%)  19.1(+36%)  35.1(-12%)  19.4(+115%)   6.0(+50%)     59.6
Median (excl refusal)           20.5(-2%)  15.0(+7%)  33.0(-18%)  16.0(+78%)   5.0(+25%)      37.5
First before >2x jump           20.5(-2%)  16.2(+16%)  28.5(-29%)  13.9(+54%)   3.7(-7%)       28.7
First 1 per test                18.5(-12%)  11.2(-20%)  21.3(-47%)  12.3(+37%)   5.0(+25%)      30.7
First 3 per test                19.7(-6%)  30.4(+117%)  27.0(-32%)  14.9(+65%)   4.3(+8%)       61.8
Shallow zone (N20<30)           18.0(-14%)  14.9(+6%)  24.0(-40%)  14.8(+64%)   6.0(+50%)      41.2

Eva's actual values:               21        14        40         9         4
```

### Key finding: No single formula matches Eva across all projects

- **Bell-Lloc** (Eva=21): Median excl refusal (20.5, -2%) — excellent
- **Castellar** (Eva=14): Shallow zone <30 (14.9, +6%) — good
- **Rubí** (Eva=40): Overall avg (39.5, -1%) — only strategy that works!
- **Linyola** (Eva=9): Nothing below +37% error; Eva uses ~first reading zone
- **Alcoletge** (Eva=4): First 3/test (4.3, +8%) — good

**Rubí is the outlier:** long consistent boring logs (20+ readings before refusal)
with no major jumps. Eva effectively averages the full non-refusal profile.
All other projects have short, shallow borings with rapid ramp to refusal.

### Root cause

Eva's N20 selection is **not a formula** — it's professional judgment based on:
1. The founding soil depth (shallow foundations, typically 0.3-0.5m)
2. The soil profile shape (stable zone vs ramp zone)
3. The project context (number of levels, soil type transitions)

### Cascade effect of wrong N20

When dpsh_avg_n20 is 3x too high (e.g., Bell-Lloc: 70 vs Eva's 21):

| Variable | Pipeline | Eva | Error | Cause |
|----------|----------|-----|-------|-------|
| dpsh_avg_n20 | 70 | 21 | +233% | Includes refusal zone |
| geotech_nb | 70-R | 25 | +180% | Nb = N20/0.83 |
| geotech_E | 1428 | 650 | +120% | CTE D.23 brackets jump at N20=50 |
| geotech_phi | 42 | 38 | +11% | Schmertmann less sensitive |
| qa_value | 2.40 | 3.00 | -20% | T-P divides by Fw which grows |
| settlement | 1.12 | 1.20 | -7% | Partially compensating |

Fixing N20 alone would fix **5-7 downstream variables** per project.

---

## Problem 2: First-Run Production Lifecycle

### Expected production flow
```
Eva opens project (NO user_data.json)
    → Pipeline auto-extracts everything
    → Wizard shows pre-filled values (~95% filled)
    → Eva reviews, adjusts maybe 2-3 fields
    → Hits "Generate" → correct report
```

### Current gaps on first run (without user_data.json)

| Category | Examples | Impact | Root cause |
|----------|----------|--------|------------|
| **N20/geotech cascade** | dpsh_avg_n20, Nb, phi, E, Qa, settlement, K30 | HIGH — 7+ fields wrong | Averaging method |
| **Client name** | Castellar: "GRUP ALMA" vs Eva's "WOOD COMFORT" | MEDIUM | FileMiner picks wrong contact from docs |
| **Adjacents quality** | "parcel·la buida" vs Eva's "parcel·la ocupada per un habitatge" | MEDIUM | Cadastre API can't see buildings |
| **Surface areas** | Bell-Lloc: 607 vs Eva's 995 | MEDIUM | Cadastre gives parcel area, Eva uses project total |
| **Site description** | Template boilerplate vs Eva's field observation | LOW | Can't auto-generate field observations |
| **Seismic coefficient** | "0,04" vs Eva's "AB = 0,08 g" | LOW | Format mismatch + different NCSE lookup |
| **Cohesion for llims** | 0.00 vs Eva's 0.05 | LOW | Pipeline says "granular", Eva says "cohesive" |

### What Eva WOULD need to fix manually (unavoidable)

These can never be 100% auto-extracted:
1. **Professional judgment values**: E override for carbonated soils, Qa cap adjustments
2. **Field observations**: site_condition, site_description details beyond template
3. **Soil type classification** when ambiguous (llim vs granular)
4. **Client name** when it differs from document contacts

### What the pipeline SHOULD get right but doesn't

These should be fixable:
1. **N20 average** — the method is wrong (this plan)
2. **Adjacents** — Cadastre API is inherently limited (separate roadmap item)
3. **Surface areas** — sometimes Cadastre parcel != Eva's project area (needs investigation)
4. **Seismic format** — just formatting, easy fix

---

## Proposed Solution: N20

### Approach: "Smart default + transparent override"

Since no single formula matches Eva, the approach should be:

1. **Compute a better default** that's closer to Eva for most cases
2. **Show Eva the DPSH profile** in the wizard so she can understand and adjust
3. **Make N20 an expert-override field** like gamma, phi, E

### Step 1: Better default formula

**Recommended: "Exclude refusal + weighted shallow bias"**

```python
def compute_representative_n20(dpsh_data):
    """Compute representative N20 for foundation soil."""
    all_readings = []
    for test in dpsh_data.tests:
        non_refusal = [r for r in test.readings if r.n20 < 100]
        all_readings.extend(non_refusal)

    if not all_readings:
        return dpsh_data.overall_average_n20

    # Weight: readings in first 1.0m get 2x weight (foundation zone)
    weighted_sum = 0
    total_weight = 0
    for r in all_readings:
        w = 2.0 if abs(r.depth_m) <= 1.0 else 1.0
        weighted_sum += r.n20 * w
        total_weight += w

    return weighted_sum / total_weight
```

**Expected improvement (estimated):**

| Project | Current | Proposed | Eva | Current err | Proposed err |
|---------|---------|----------|-----|-------------|--------------|
| Bell-Lloc | 37 | ~22 | 21 | +75% | ~+5% |
| Castellar | 38 | ~15 | 14 | +172% | ~+7% |
| Rubí | 40 | ~34 | 40 | -1% | ~-15% |
| Linyola | 29 | ~15 | 9 | +224% | ~+67% |
| Alcoletge | 22 | ~5 | 4 | +441% | ~+25% |

This would reduce RMSE from 237 to ~30-40. Not perfect, but **10x better**.

### Step 2: DPSH profile in wizard (future)

Add to the wizard's expert overrides panel:
```
N20 mitja calculada: 22 (ponderat shallow)
Perfil: P-1: [20,27,16,19,32,R] | P-2: [17,21,17,13,10,20,30,52,55,32,80,R]
Eva pot ajustar: [___22___]
```

This lets Eva see the raw data and override if her judgment differs.

### Step 3: N20 as expert override field

Add `dpsh_avg_n20_override` to the wizard expert overrides panel, similar to
how Es_settlement already works. When Eva overrides, it propagates to Nb, phi,
E, Qa, settlement, K30 automatically.

---

## Investigation Still Needed

### 1. Ask Eva about her N20 method (PRIORITY)

**Specific questions:**
- "Quan calcules la N20 mitjana pel Taula 9, fas servir totes les lectures o
  només les de la zona poc profunda?"
- "A Rubí el valor N20=40 és de totes les lectures, però a Linyola N20=9 sembla
  només les primeres. Quina regla fas servir?"
- "Tens algun criteri per excloure lectures de refús o lectures molt altes?"

**Why this matters:** If Eva has a consistent method we're not seeing, we can
implement it exactly. If it's judgment, the "smart default + override" approach
is correct.

### 2. Verify soil type classification

| Project | Pipeline says | Eva says | Impact |
|---------|--------------|----------|--------|
| Linyola | granular | cohesive (llim) | c=0 vs 0.05, phi=36 vs 28, E=469 vs 100 |
| Alcoletge | granular | rock (roca) | c=0 vs 1.0, completely different params |

The soil type classification from DPSH alone may be insufficient. The sondeig
description should inform the classification more strongly. Need to investigate
how `_generate_soil_levels()` determines soil_type and whether vision-extracted
sondeig descriptions should override it.

### 3. Surface area discrepancies

| Project | Pipeline | Eva | Source |
|---------|----------|-----|--------|
| Bell-Lloc | 607.5 | 995 | Cadastre WFS vs Eva's project docs |
| Castellar | 440 | 1284 | Same discrepancy |
| Rubí | 1414 | 951 | Reversed! |

Hypothesis: Cadastre gives individual parcel area, but Eva sometimes uses the
full project footprint (multiple parcels, or built area + garden). Need to check
if Eva's PDFs specify "superficie de la parcela" differently.

### 4. Client name extraction

| Project | Pipeline | Eva |
|---------|----------|-----|
| Castellar | GRUP ALMA | WOOD COMFORT PROMOCIONS SLU |
| Linyola | BUNYESC ARQUITECCTURA EFICIENT | SRA. SÍLVIA EROLES BALAGUERÓ |
| Alcoletge | ALBERT SANS BONVEHI tel. 675... | SR. ALBERT SANS BONVEHI |

Pipeline picks the wrong entity or includes noise (phone numbers, emails).
FileMiner's contact extraction needs refinement: client = promotor, not architect.

---

## Implementation Priority

```
1. N20 formula fix (exclude refusal + shallow weighting)    ← Biggest impact
   - Fixes: dpsh_avg_n20, geotech_nb, geotech_phi, geotech_E, qa_value,
     settlement, k30_value  (7 variables)
   - Estimated gain: Tier A +10-15%, Overall +5-8%
   - Effort: ~30 min (dpsh_extractor + auto_extractor + wizard_service)

2. N20 as expert override in wizard                         ← Eva control
   - Shows DPSH profile + computed average
   - Eva can adjust → cascades to all downstream calcs
   - Effort: ~1 hour (wizard field + JS cascade logic)

3. Ask Eva the specific questions above                     ← Correctness
   - Required to validate our formula choice
   - May reveal a simpler rule we're missing

4. Soil type classification from sondeig                    ← Linyola/Alcoletge fix
   - If sondeig says "llims argilosos", soil_type should be "cohesive"
   - If sondeig says "roca", soil_type should be "rock"
   - Currently soil_type comes from wizard dropdown only
   - Effort: ~1 hour (vision_normalizer → auto_extractor inference)

5. Client name cleanup                                      ← Data quality
   - Strip phone numbers, emails from client names
   - Prefer "promotor" field over generic contact
   - Effort: ~30 min

6. Surface area investigation                               ← Needs Eva input
   - Need to understand why Cadastre areas differ from Eva's
   - May need to aggregate multiple cadastral parcels
```

---

## Success Metrics

| Metric | Current | After N20 fix | After all fixes |
|--------|---------|---------------|-----------------|
| Overall correctness | 35.8% | ~42-45% | ~50-55% |
| Tier A correctness | 53.1% | ~62-68% | ~70-75% |
| Tier C correctness | 23.5% | ~35-40% | ~40-45% |
| N20 avg error (RMSE) | 237% | ~30-40% | ~15-25% |
| Fields Eva must edit | ~10-15 | ~5-8 | ~3-5 |

---

## Appendix: Raw DPSH Data Per Project

### Bell-Lloc (4001612) — Eva N20=21, Pipeline=37
```
P-1: [20, 27, 16, 19, 32, R]        (depths 0.2-1.2m)
P-2: [17, 21, 17, 13, 10, 20, 30, 52, 55, 32, 80, R]  (depths 0.2-2.4m)
```

### Castellar (3001621) — Eva N20=14, Pipeline=38
```
P-1: [6, 10, 13, 38, R]             (depths 0.2-1.0m, very short)
P-2: [15, R]                        (depths 0.2-0.4m, immediate refusal)
P-3: [16, 46, R]                    (depths 0.2-0.6m)
P-4: [8, 8, 12, 27, 21, 28, R]     (depths 0.2-1.4m)
```

### Rubí (3001631) — Eva N20=40, Pipeline=40
```
P-1: [22,33,30,25,22,24,20,34,35,60,64,47,27,26,32,36,37,28,30,52,66,R]  (0.2-4.4m!)
P-2: [10,24,28,42,47,33,28,35,38,24,40,30,20,27,37,54,R]                 (0.2-3.4m)
P-3: [32,36,28,39,37,32,32,60,49,34,25,36,47,80,R]                       (0.2-3.0m)
```
Note: Rubí has very deep, consistent borings. No shallow-zone cutoff applies.

### Linyola (4001607) — Eva N20=9, Pipeline=29
```
P-1: [9,18,12,7,5,4,7,22,57,26,10,43,90,R]   (0.2-2.8m)
P-2: [20,20,21,14,11,19,26,29,73,R]            (0.2-2.0m)
P-3: [8,13,13,13,10,16,17,R]                   (0.2-1.4m)
```
Note: Eva=9 matches ONLY P-1's first reading (9). Very unusual — suggests Eva
focuses on the shallowest, softest zone for cohesive soils.

### Alcoletge (4001670) — Eva N20=4, Pipeline=22
```
P-1: [5, 6, 5, 3, 1, 1, R]         (0.2-1.4m)
P-2: [5, 2, 4, 9, 9, 12, R]        (0.2-1.2m)
P-3: [5, 5, 2, 4, 9, 14, 13, 84, R] (0.2-1.8m)
```
Note: Very soft soil. Eva=4 matches the minimum readings zone. This is a
cohesive/rock site where Eva uses different judgment.
