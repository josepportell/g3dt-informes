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

## Highest-leverage remaining work

Ranked by impact from the sweep analysis:

1. **Schema gaps** — 9 concepts `access_street` / `sulfate_*` / `spt_*` family account for ~20 NE var-comparisons across 7 projects. Add to `schemas/concepts/report_variables.yaml` with proper priority chains. Est. **+3-5pp** accuracy.
2. **CTE classification threshold** — `cte_sol` 4/7, `cte_edificacio` 4/7, `qa_value` 4/7 all show the SAME wrong-answer pattern (Eva: `C-0`/`T-1`/`qa=3.0`; pipeline: `C-1`/`T-2`/`qa=2.0`). Single bug, 12 var-comparisons affected. Est. **+4pp**.
3. **Settlement format** — 6/7 projects MISMATCH because pipeline returns `1.70` numeric, Eva writes narrative prose. Format-change only; values are correct. Est. **+6pp** if we wrap the number in Eva's standard sentence.
4. **Identity narrative synthesis** — `client_name` 4/7, `architect_name` 4/7. Vision picks vendor-not-person or co-author-not-lead. Multi-source disambiguation.
5. **Adjacent narrative** — `adjacent_*_fmt` 3-6/7. Eva's descriptions (visual observation) don't align with cadastre taxonomy. Hard problem; partial fix via visual-observations feed (already in Step 3 from prior session).

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
