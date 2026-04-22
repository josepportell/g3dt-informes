# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-04-22 (end of session)

## Current State

**Step 7 geocoding pipeline simplification + vision-into-competition chain shipped.** 9 merges today, +94 new tests, 0 regressions on any cycle, full suite now **660 pass**.

Today's 7-project re-sweep: **64.1% match+close** (217 compared). Apr 19 baseline for the same code path ran **62.4%–65.2% across three re-runs** (judge-noise band 2.8pp). Today is squarely inside the Apr 19 band, so the headline is **flat within noise**.

But the frontier did move:
- **NOT_EXTRACTED dropped 47 → 40** (-7 var-comparisons). Wider extraction net.
- **Vilanova +8pp (48.0% → 56.0%)** — the full Step 7 + #8 + #10 + #11 chain proven end-to-end. `adjacent_west_fmt` flipped from `"Carrer Santa Marta"` MISMATCH to `"Carrer Santa Gemma"` MATCH.
- **Alcoletge +2.3pp**.
- Bell-Lloc, Castellar, Linyola flat. Rubí -3.7pp (precision cost of wider extraction; not a real quality regression — `num_floors` became `"appears to be 2-3 levels"`, now filtered by the hedged-preview drop).

## Today's merges

| Merge | What it does |
|---|---|
| Step 7 #1+#2 | CartoCiudad native `refCatastral` + query filters |
| Step 7 #5 | Cadastre err-code-16 fallback via `RCCOOR_Distancia` |
| Step 7 #3 | ICGC API Territorial Catalan fast path |
| STATUS checkpoint | Rollback point |
| #8 | Vision signals → FileMiner competition + G3 filter earlier + planol geocode preference |
| #10 | Callejero fast-path removed in auto_extractor |
| #11 | CartoCiudad suffix stripping + drop accent-sensitive `municipio_filter` |
| #9 | `superficie_*_m2` → `superficie_*` vision concept-key alignment + registry guard |
| #12 | Address vision: house-number prompt + 0.9 confidence floor + drop handwritten sources |
| hedged-preview filter | Drop vision previews like "appears to…", "probably", "unclear", etc. |

Full Step 7 tracker: `docs/knob-fixes-2026-04-19/STATUS.md`.

## Per-project today

| Project | Rate | vs Apr 21 |
|---|---:|---:|
| Bell-Lloc | 72.1% | flat |
| Castellar | 77.4% | flat |
| Rubí | 63.9% | -3.7pp |
| Linyola | 73.7% | flat |
| Alcoletge | 47.8% | +2.3pp |
| **Vilanova** | **56.0%** | **+8.0pp** ✓ |
| Anciles | 38.1% | new baseline (DNS-contaminated; 13 network errors) |

CROSS snapshot: `docs/diagnostics/2026-04-22_CROSS_351d13.json`.

## Last Diagnostic Status (2026-04-22)

**Sweep:** `docs/diagnostics/2026-04-22_CROSS_351d13.json` — 64.1% match+close, 217 compared. Apr 19 judge-noise band: 62.4%-65.2% (three re-runs, same code). Today is inside the band.

**Failure-mode classification** — of 78 total MISMATCHes, 4 structural modes + 1 schema-gap class:

| Mode | Vars | Recoverable | Effort |
|---|---:|---:|---|
| A. Schema gaps (NE) | ~20 | +3-5pp | S |
| B. CTE threshold bug (1 cause, 12 vars) | 12 | +4pp | S |
| C. Settlement format wrap (values correct, narrative missing) | 6 | +6pp | S |
| D. Identity disambiguation (client/architect from multi-name docs) | 8 | +2-4pp | M |
| E. Adjacent/location narrative (Eva voice vs cadastre taxonomy) | 12+ | +2-5pp | L |

**Projected ceiling after A+B+C: ~77-80%.**

**Per-project rates today:**

| Project | Rate | vs Apr 21 |
|---|---:|---:|
| Bell-Lloc | 72.1% | flat |
| Castellar | 77.4% | flat |
| Rubí | 63.9% | -3.7pp (precision cost of wider extraction) |
| Linyola | 73.7% | flat |
| Alcoletge | 47.8% | +2.3pp |
| **Vilanova** | **56.0%** | **+8.0pp** ✓ |
| Anciles | 38.1% | DNS-contaminated (13 network errors mid-sweep) |

**Full action plan + fix approach for each mode:** `docs/PLA-PROXIMES-ACCIONS-POST-SWEEP-2026-04-22.md`.

## Suggested sequencing (next session)

1. Action 1 (schema gaps) — biggest NE recovery, lowest risk. Pure YAML edit.
2. Action 2 (CTE threshold) — single cause, bulk unlock. Verify against Eva's methodology first.
3. Action 3 (settlement wrap) — biggest single pp gain, format-only, low risk.
4. Re-sweep after 1-3 to measure real ceiling.
5. Actions 4-5 (identity + narrative) once the structural fixes land.

## Active Blockers

- Installation on Eva's machine pending.
- Email to Eva pending — v4 at `docs/CORREU-EVA-PREGUNTES-CALCULS-v4.md` (4 questions).
- **Step 7 #4 (ASMX→REST/JSON)** blocked server-side — Catastro's JSON endpoint returns `cod=76` regardless of param casing. Code structured for drop-in flip when fixed.
- 1 pre-existing test failure: `test_bell_lloc_bearing_idx_and_n20` (vision non-determinism).

## Deferred / Open Tasks

- **Step 7 #6** (INSPIRE WFS-CP for adjacents) — medium effort, modest accuracy gain, low priority. Documented analysis: better speed + cleaner code, but doesn't address the narrative mismatch that's the real adjacents problem.
- Step 5 "wrong-UTM non-_consulta_via code path" — root-cause-resolved via Step 6+7 (the problematic Callejero fast-path is removed as of #10).

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`.
