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

## Full Cascade Analysis: Every Strategy × Every Project × Every Variable

This table shows what EACH N20 strategy produces for ALL downstream variables,
compared to Eva's values. This is the critical data for choosing a strategy.

### Bell-Lloc (Eva: granular soil)

```
Strategy                    N20     Nb    phi      E     Qa    K30   |  N20%    Nb%   phi%      E%    Qa%
EVA (target)                 21     25     38    650    3.0    6.0   |
Overall avg (CURRENT)       36.7   44.2   38.1    400   3.00   5.3   |  +75%   +77%    +0%    -38%    +0%
Excl refusal (<100)         28.8   34.7   36.7    400   3.00   5.3   |  +37%   +39%    -3%    -38%    +0%
Excl refusal (<80)          25.4   30.6   36.1    400   2.93   5.3   |  +21%   +22%    -5%    -38%    -2%
Median (excl ref)           20.5   24.7   34.4    200   2.37   2.7   |   -2%    -1%    -9%    -69%   -21%
First before >2x            20.2   24.3   34.3    200   2.33   2.7   |   -4%    -3%   -10%    -69%   -22%
First 1/test                18.5   22.3   33.7    200   2.14   2.7   |  -12%   -11%   -11%    -69%   -29%
First 3/test                19.7   23.7   34.1    200   2.27   2.7   |   -6%    -5%   -10%    -69%   -24%
Shallow (<30)               18.0   21.7   33.5    200   2.08   2.7   |  -14%   -13%   -12%    -69%   -31%
```

**Insight:** Bell-Lloc N20 best match is Median (20.5≈21), but E drops to 200
(CTE bracket boundary at N20=25). Eva's E=650 is a **professional override**
for carbonated gravels — no N20 strategy can produce E=650 automatically.
The CTE D.23 table maxes at 400 for N20 25-40, 469 for N20 40-50.
Eva's E=650 is judgment, not formula.

### Castellar (Eva: rock, cohesion=1.0)

```
Strategy                    N20     Nb    phi      E     Qa    K30   |  N20%    Nb%   phi%      E%    Qa%
EVA (target)                 14     17     35    500    3.0    8.0   |
Overall avg (CURRENT)       38.1   45.9   38.4    400   4.40   6.7   | +172%  +170%   +10%    -20%   +47%
Excl refusal (<100)         19.1   23.0   33.9    200   2.20   3.3   |  +36%   +35%    -3%    -60%   -27%
Median (excl ref)           15.0   18.1   32.4    200   1.73   3.3   |   +7%    +6%    -7%    -60%   -42%
First before >2x            14.9   17.9   32.4    114   1.72   1.9   |   +6%    +6%    -7%    -77%   -43%
Shallow (<30)               14.9   18.0   32.4    114   1.72   1.9   |   +6%    +6%    -7%    -77%   -43%
```

**Insight:** Best N20 match (Median/Shallow ≈15) produces E=114-200, but Eva
uses E>500 (rock). Again, E is **professional judgment** for rock soils.
phi=32-34 vs Eva's 35 — close but not matching (Eva's comes from rock tables).
Qa=1.72 vs Eva's 3.0 — huge gap because rock Qa needs different calculation.

### Rubí (Eva: granular)

```
Strategy                    N20     Nb    phi      E     Qa    K30   |  N20%    Nb%   phi%      E%    Qa%
EVA (target)                 40     47     39    450    3.5    6.0   |
Overall avg (CURRENT)       39.5   47.6   38.6    400   3.00   5.3   |   -1%    +1%    -1%    -11%   -14%
Excl refusal (<100)         36.0   43.3   38.0    400   3.00   5.3   |  -10%    -8%    -3%    -11%   -14%
Median (excl ref)           33.0   39.8   37.5    400   3.00   5.3   |  -18%   -15%    -4%    -11%   -14%
First before >2x            31.8   38.3   37.2    400   3.00   5.3   |  -21%   -19%    -5%    -11%   -14%
First 3/test                27.0   32.5   36.4    400   3.00   5.3   |  -32%   -31%    -7%    -11%   -14%
```

**Insight:** Rubí is the ONLY project where "Overall avg" matches Eva. E stays
at 400 for all strategies (N20 25-40 band) — but Eva uses 450 (again, judgment).
Qa is capped at 3.0 for all strategies, but Eva uses 3.5 — suggesting Eva uses
a higher cap for dense granular soils. phi is stable across strategies (37-39).

### Linyola (Eva: cohesive, llims argilosos)

```
Strategy                    N20     Nb    phi      E     Qa    K30   |  N20%    Nb%   phi%      E%    Qa%
EVA (target)                  9     13     28    100    3.0      -   |
Overall avg (CURRENT)       29.2   35.1   36.8    400   3.00         | +224%  +170%   +31%   +300%    +0%
First 1/test                12.3   14.9   31.5    114   1.42         |  +37%   +14%   +12%    +14%   -53%
First before >2x            14.2   17.1   32.1    114   1.64         |  +58%   +31%   +15%    +14%   -45%
Shallow (<30)               14.8   17.8   32.3    114   1.71         |  +64%   +37%   +16%    +14%   -43%
```

**Insight:** CRITICAL — Linyola is a **cohesive soil** (llims argilosos).
Eva uses phi=28, E=100, which are the COHESIVE lookup values, NOT CTE D.23.
No N20-based strategy produces E=100 or phi=28 because our pipeline classifies
this as "granular" and uses the wrong lookup tables. The PRIMARY fix here is
**soil type classification**, not N20 averaging. Even with perfect N20=9,
CTE D.23 gives E=80 (close but different table) and Schmertmann gives phi≈29
(close because cohesive phi is flat).

### Alcoletge (Eva: rock, cohesion=1.0)

```
Strategy                    N20     Nb    phi      E     Qa    K30   |  N20%    Nb%   phi%      E%    Qa%
EVA (target)                  4      R     30   >400    3.5      -   |
Overall avg (CURRENT)       21.7   26.1   34.8    200   2.50         | +441%     -    +16%    -50%   -29%
First 3/test                 4.3    5.2   28.6     50   0.50         |   +8%     -     -5%    -88%   -86%
First before >2x             3.7    4.4   28.2     50   0.43         |   -8%     -     -6%    -88%   -88%
Excl refusal (<80)           6.0    7.2   29.6     80   0.69         |  +50%     -     -1%    -80%   -80%
```

**Insight:** CRITICAL — Alcoletge is **rock** (Eva c=1.0, phi=30, E>400).
Eva's Nb="R" (refusal = rock). Our pipeline treats it as granular.
Even with perfect N20=4, CTE D.23 gives E=50 vs Eva's >400 — because
**rock E cannot be derived from DPSH N20**. It's a different material entirely.
phi=28-30 is close, but Qa=0.50 vs Eva's 3.5 because T-P doesn't apply to rock.

---

## KEY REVELATION FROM CASCADE ANALYSIS

**Three distinct categories of error:**

### Category A: N20 averaging (fixable with better formula)
Projects: Bell-Lloc (partial), Rubí (partial)
- Fixing the averaging method improves N20/Nb/phi
- But E still limited by CTE D.23 bracket boundaries
- Qa improves because phi and Nb improve

### Category B: Soil type misclassification (fixable with sondeig data)
Projects: Linyola, Alcoletge
- Pipeline says "granular" → uses CTE D.23 for E, Schmertmann for phi
- Eva says "cohesive" (Linyola) or "rock" (Alcoletge) → uses different tables
- **FIX: sondeig description should drive soil type, not just DPSH hardness**
- Impact: changes E by 4-10x, phi by 5-15 degrees, Qa by 2-5x

### Category C: Professional judgment override (not auto-fixable)
Projects: ALL (for E), Rubí (for Qa cap), Castellar (for E)
- Eva's E is judgment: 650 for carbonated gravels, >400 for rock, 100 for llims
- CTE D.23 gives 114-469 for most N20 ranges — never matches Eva's overrides
- Eva's Qa cap: 3.0 for soil, 3.5 for dense granular, 4.0-5.0 for rock
- **These CANNOT be automated — they are the expert overrides panel's purpose**

### What this means for implementation priority:

```
1. Soil type classification from sondeig   ← HIGHEST IMPACT (Linyola, Alcoletge)
   Fixes: E, phi, cohesion, Qa, settlement for misclassified projects

2. N20 averaging method                    ← HIGH IMPACT (all projects)
   Fixes: N20, Nb, phi (partially), Qa (partially)

3. Expert override UX for E and Qa cap     ← Already done (Item 4 today)
   Eva sees ranges and formulas, adjusts as needed
```

The cascade analysis reveals that **soil type classification is MORE important
than N20 averaging** for overall correctness. Two projects (Linyola, Alcoletge)
are wrong in EVERY downstream variable because the soil type is wrong, not
because N20 is wrong.

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

## Implementation Priority (revised after cascade analysis)

The cascade analysis above reveals that **soil type classification is MORE
important than N20 averaging**. Two projects are wrong in every downstream
variable because the soil type is wrong.

```
1. Soil type classification from sondeig    ← HIGHEST IMPACT (revised up)
   - Fixes: E, phi, cohesion, Qa, settlement for Linyola + Alcoletge
   - Sondeig description → infer soil_type (cohesive/rock/granular)
   - "llims argilosos" → cohesive (E=100, phi=28, c=0.05)
   - "roca", "bretxes", "lutites compactes" → rock (E>500, phi=30-35, c=1.0)
   - Estimated gain: Tier A +5-8%, fixes 2 projects completely
   - Effort: ~1 hour (sondeig vision → auto_extractor soil_type inference)

2. N20 formula fix (exclude refusal + shallow weighting)    ← HIGH IMPACT
   - Fixes: dpsh_avg_n20, geotech_nb, geotech_phi partially
   - NOTE: Does NOT fix E (CTE bracket problem) or Qa (cap problem)
   - Best strategy: weighted shallow bias (see analysis above)
   - Estimated gain: Tier A +5-10%, reduces N20 RMSE from 237 to ~35
   - Effort: ~30 min (dpsh_extractor + auto_extractor + wizard_service)

3. Ask Eva the specific questions                           ← Validates 1+2
   - Required to confirm soil type inference rules
   - Required to validate N20 averaging choice
   - May reveal her Qa cap rules (3.0 vs 3.5 vs 4.5)

4. N20 as expert override in wizard                         ← Eva control
   - Shows DPSH profile + computed average
   - Eva can adjust → cascades to all downstream calcs
   - Effort: ~1 hour (wizard field + JS cascade logic)

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
