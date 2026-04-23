# For new-you — session handoff 2026-04-24

**Written:** 2026-04-23 (end of session)
**Target:** fresh session to continue Acció 2 + decide Plan 2 (LLM reasoner) via spike experiment
**Session one-liner:** Action 1 shipped (9 concept registry entries) + Action 2 Fix #1 shipped (CTE building class floor-only) + Action 2 Fix α shipped and fully wired (DPSH auto-segmentation for projects without sondeig). Plan 1 vs Plan 2 bifurcation documented. Plan 1 ceiling reached on Alcoletge (qa 1.00 → 1.50, not 3.50). Next: LLM spike to decide Plan 2.

---

## Reading order (before touching code)

1. **This doc** (you're here).
2. `STATUS.md` — project state. Note "Metodologia d'Eva" section at bottom points to §3 below.
3. `docs/PLA-ACCIO-2-BIFURCACIO-2026-04-23.md` — full plan for Action 2, including Plan 1 (deterministic) + Plan 2 (LLM reasoner) + the spike experiment (§4) — this is the next concrete thing to execute.
4. `docs/METODOLOGIA-EVA.md` — Eva's methodology with textual citations from her 7 signed reports (Crespo Villalaz / Rodríguez Ortiz / Schmertmann / Terzaghi-Peck). The Ortiz Cap. 2 PDF is at `docs/research/books/`. **99% confidence source** — Eva writes these methods in her final signed reports. Any calc change should cite this doc.
5. `MEMORY.md` (auto-memory) — Eva's values, feedback rules, recent project entries. Read for feedback items especially (no skip stages, pytest 10min timeout, trust planol over Eva's overrides, etc.).
6. `docs/_FOR-NEW-YOU-20260423.md` — previous session's handoff. Context on the 2026-04-22 sweep that motivated this whole arc.

After those you have everything for the spike.

---

## Current state — what's where

**Branch:** `feature/action-2-deterministic`
**Parent:** `experiment/cc-only-extraction` (stable baseline)
**Main:** `main`

**Commits on this branch since parent divergence (newest first):**
- `6371716` — Fix α cont. wired into `web/wizard_service.py`
- `59e9f1f` — Fix α review findings (W1+W2+S1+S2)
- `c7d6417` — Fix α initial landing
- `0e97a3f` — Plan doc + METODOLOGIA-EVA refs from STATUS/CLAUDE
- `6b7b7d1` — Fix #1 CTE building class (floor count only)
- `66bd52d` — Action 1 — 9 new concepts in registry

Test state: `679 passed, 1 skipped, 2 deselected` on this branch (baseline was 660; +19 from this session).

**Uncommitted noise:** `docs/benchmarks/_llm_judge_cache.json` + `reference-material/*/file_mapping.json` + `concept_map.json` + deleted `mined_images/*`. These are pipeline artifacts, NOT our work. Don't commit. Safe to `git checkout --` if they're in your way.

---

## Critical interpretive rules

### 1. Judge noise band (unchanged from yesterday's handoff)
Sweep headline varies **±1.5pp** across identical re-runs. Apr 19 band: 62.4%-65.2%. Today's 64.1% is inside. **Compare MISMATCH-set flips, not headline deltas.** A re-sweep at 68% vs 64% is ~3.5σ of noise — visible but not decisive.

### 2. Two parallel Qa computation paths
The pipeline computes `qa_value` at TWO independent sites:
- `automation/report_data.py:build_report_data` → used by `automation/report_generator.py` for producing Eva's .docx
- `web/wizard_service.py:_compute_geotech_prefills` → used by `scripts/diagnostic_trace.py` AND by Eva's live wizard prefills

**They duplicate logic** for loading `sondeig_layers`, selecting bearing layer, computing avg_n20, calling `calculate_qa`. **Any calc-related fix must touch BOTH or results diverge between "what Eva sees in wizard" and "what gets rendered in the .docx"**. Fix α initially missed `wizard_service.py` and the diagnostic showed zero improvement despite the fix being in `report_data.py`. Took one extra commit (6371716) to close the gap.

Consider DRY-ing this at some point. Not this session — too much surface.

### 3. Alcoletge is the judgment-ceiling test case
Alcoletge has no sondeig file. Even with DPSH auto-segmentation picking the right bearing layer (idx=1, Nb=21.5), the resulting qa=1.50 vs Eva's 3.50 because:
- Boundary detected at 1.00m (largest N20 step), Eva uses 1.20m (lithological judgment)
- Nb=21.5 is below `QA_CAP_DENSE_GRANULAR` threshold (25) so cap stays at soil 3.0
- Eva applies dense_granular_3.5 knowing the bearing is "lutites alterades" — this is professional judgment we can't encode as a keyword+threshold rule

**This is the exact case the LLM spike (Plan 2) is designed to test.** If the LLM reads "bearing material = lutites alterades" + N20=21 and outputs `cap_tier="dense_granular_3.5"`, we have the Plan 2 go signal.

### 4. calc_trace `Nb=?, c=?, phi=?` is a cosmetic trace bug
All projects show `Nb=?` in `calc_trace` — Bell-Lloc (MATCH!) too. Don't chase it as the real bug. The values ARE flowing into `calculate_qa`; they just aren't being captured in the trace string at `scripts/diagnostic_trace.py:527-541`. Cosmetic. Don't prioritize.

### 5. Linyola's sondeig extraction is broken-but-gated
Linyola has `sondeig_annex_extracted.json` but `sondeig_tests` array is empty (handwritten field sheets, no formal borehole log → extractor produced nothing structured). Fix α segmenter kicks in because `sondeig_layers` ends up empty. DPSH is too heterogeneous for a clear step → returns single-layer wrap → no improvement over baseline for qa_value. Accept this — Plan 1 can't fix Linyola's lack of lithology data.

---

## Load-bearing structural assumptions

### 1. Gating of DPSH segmenter is strict
`web/wizard_service.py:~605` and `automation/report_data.py:~438` both check `if not sondeig_layers` before calling `segment_by_n20_step`. This means projects with real sondeig (Bell-Lloc, Castellar, Rubí, Vilanova, Anciles) are NEVER touched. If you refactor this, keep the gating. Regression test `test_segmenter_does_not_fire_when_user_data_has_sondeig_layers` catches any inversion.

### 2. Synthesized layer descriptions are empty strings
`automation/dpsh_segmenter.py` sets `description=''` for all synthesized layers (not diagnostic prose). Diagnostic info lives in `logger.info(...)` calls. Reason: description propagates to Eva's .docx via Jinja; a diagnostic string like `"auto-segmented from DPSH (N20 step at 1.00 m)"` would appear in the report. Don't re-introduce prose descriptions without routing them through a separate `source` field.

### 3. CTE building class discriminator is floor count ONLY
`automation/cte_classifier.py:187` condition is `elif total_floors >= 2:` — NOT `or area_m2 >= 100`. Per CTE DB SE-C. `area_m2` stays in the signature for API stability but is unused. `automation/municipal_lookups.py:lookup_cte_edificacio` passes `area_m2=0` deliberately. Don't "helpfully" reintroduce area as a discriminator.

### 4. Existing bicapa invariants (from previous session)
- Vision signals compete in FileMiner (see `automation/concept_scout/__init__.py:concept_sources_to_signals`).
- G3 internal-address filter lives in TWO places (competition pool + phase25/phase3) deliberately.
- CartoCiudad `municipio_filter` deliberately NOT sent (accent-strict server bug).
- Callejero fast-path removed from `auto_extractor.py`.
- Address vision signals have confidence floor of 0.9 + field_sheet drop.
- Hedged vision previews are filtered out (`_HEDGED_PREVIEW_MARKERS`).

Yesterday's handoff `docs/_FOR-NEW-YOU-20260423.md` has full detail for each.

---

## Operational procedures

### Quick single-project diagnostic (under 2 min)
```bash
# Clear concept_map cache for the target project, then run
rm -f "reference-material/4001670 ALCOLETGE/validation/concept_map.json"
.venv/bin/python scripts/diagnostic_trace.py --project 4001670 --concept qa_value --classify
```

Swap project number + concept as needed. Add `--save` to write snapshot JSON to `docs/diagnostics/`.

### Full 7-project sweep (~15 min)
Follow `docs/_FOR-NEW-YOU-20260423.md` §"Re-sweep operational checklist" — clear concept_map caches + CartoCiudad/geocode caches + run `scripts/diagnostic_trace.py --save --components --ne-trace`. Check for DNS contamination with `grep -c "name resolution\|Connection error" /tmp/claude-*/tasks/*.output`.

### Tests
```bash
.venv/bin/python -m pytest tests/ --deselect tests/test_bearing_stratum_n20_regression.py --timeout=600
```

Expected: 679 pass on this branch. `test_bearing_stratum_n20_regression` is a pre-existing failure (vision non-determinism on handwritten sondeig), deselect until it's fixed upstream.

Tests take ~3 min. Use `--timeout=600` (10 min) per MEMORY feedback.

### Cache clearing before re-runs
```bash
# Per-project concept_map
rm -f "reference-material/{project}/validation/concept_map.json"

# Global caches (rarely needed)
rm -f ~/.g3dt/cache/cartociudad/*.json ~/.g3dt/cache/geocode/*.json
```

Do NOT delete `~/.g3dt/cache/cadastre_adjacents/` — they're UTM-keyed and don't corrupt new runs.

---

## Suggested opening sequence

1. `git status --short && git branch --show-current && git log --oneline -10` — confirm you're on `feature/action-2-deterministic` with 6 commits since `experiment/cc-only-extraction`.
2. Read this doc + `STATUS.md` + `docs/PLA-ACCIO-2-BIFURCACIO-2026-04-23.md` §4 (the spike spec).
3. `TaskList` — see what's in progress / pending.
4. **Create new branch for the spike:** `git checkout -b experiment/llm-spike-cap-tier experiment/cc-only-extraction` (branch from parent, NOT from `feature/action-2-deterministic` — keep the spike isolated from Plan 1 work).
5. Read `automation/bicapa.py` + `automation/cte_geomech.py:is_rock, detect_soil_type, soil_type_to_cohesion, COHESION_BY_TYPE` — the current deterministic classification logic the spike is replacing.
6. For each of the 7 projects, load `reference-material/{p}/validation/sondeig_annex_extracted.json` (if exists) + `eva_reference_values.json` to see the bearing-layer description + Eva's cap tier (derivable from `cohesion` field).
7. Start building the spike per `docs/PLA-ACCIO-2-BIFURCACIO-2026-04-23.md` §4.3: new `automation/experimental/cap_tier_reasoner.py` + `cap_tier_calculator.py` + `scripts/run_cap_tier_spike.py`. No live pipeline wiring.

Spike timeline: 2-3 days to go/no-go decision per §4.5.

---

## What NOT to do

1. **Don't tune `QA_CAP_DENSE_GRANULAR` threshold (25) or relax it to match Alcoletge.** That's hand-tuning to match one project and will regress others. The right move is the LLM spike.

2. **Don't refactor the two Qa computation paths into one during the spike.** It's tempting but risky — two-site surface is stable, a refactor would touch Fix α's wiring and invite regressions. Bundle the DRY later when both calc paths are stable.

3. **Don't commit pipeline artifacts** (`docs/benchmarks/_llm_judge_cache.json`, `reference-material/*/file_mapping.json`, `concept_map.json`, `mined_images/*`). They re-generate on next pipeline run. Stage specific files only.

4. **Don't amend published commits.** We have 6 clean commits on `feature/action-2-deterministic`. If you need to fix something, make a new commit.

5. **Don't merge `feature/action-2-deterministic` into `main` yet.** It's not re-sweep-verified end-to-end. The doc and code are stable but the whole Action 2 arc needs a sweep before merging.

6. **Don't switch models mid-spike.** The spike uses `claude-opus-4-7` (most capable) per METODOLOGIA + MEMORY feedback `feedback_no_volume_reasoning` (Eva is only user). Don't downgrade "for testing" — cheaper models may make different classification calls and you'd be measuring the wrong thing.

7. **Don't run the spike with temperature > 0.** Must be deterministic for regression snapshotting.

8. **Don't skip the regression-guard test when adding features.** `test_segmenter_does_not_fire_when_user_data_has_sondeig_layers` pattern catches gating inversions. Every LLM-related feature should have an "LLM fallback to rules when confidence low" analog.

---

## Open tasks (task tracker snapshot)

- **#14 [pending]** LLM spike experiment: cap_tier classification ← **START HERE**
- **#15 [pending]** Plan 1 Fase 1b: Draft Eva email Q5 (rock vs dense_granular) — 15min task, do in parallel with spike
- **#16 [pending]** Plan 1 Fase 1c: Rock classification refinement — blocked by Eva Q5 + spike outcome
- **#3 [pending]** Action 1: re-sweep to measure NE recovery — deferred until after spike decision
- **#5 [pending]** Action 3: settlement narrative wrap
- **#6 [pending]** Action 4: identity narrative synthesis
- **#7 [pending]** Action 5: adjacent narrative synthesis (deprioritized)

Completed this session: #1, #2, #4, #8, #9, #10, #11, #12, #13 (all marked done in TaskList).

---

## Hidden wins this session

1. **Full diagnostic infrastructure is now calc_trace-literate.** Yesterday we had to spelunk; today the `calc_trace` field in snapshot JSONs is enough to reason about 5 projects' Qa issues without running any new code. Use this capability — it's fast and accurate.

2. **Plan 1 ceiling empirically validated on Alcoletge.** We now know Plan 1 alone can't close Alcoletge's qa gap. That's not a failure — that's a cheaper way to justify investing in Plan 2. If the spike succeeds and we adopt Plan 2, we have a concrete case study to motivate it.

3. **The spike scope is perfectly aimed.** cap_tier classification is:
   - A discrete decision (4 values) with unambiguous ground truth
   - The exact decision Plan 1 couldn't make on Alcoletge
   - Reusable for Plan 2 full rollout if successful

4. **Two duplicate Qa paths are now known and documented.** Future calc work won't accidentally half-land fixes.

---

## Methodology reminders (auto-memory candidates — consider adding)

These are cross-session learnings that deserve auto-memory entries in `MEMORY.md`, not just this handoff:

- **"Qa computation duplicated at report_data.py + wizard_service.py"** — structural knowledge; would save a future session 30min of confusion.
- **"DPSH segmenter boundary depth is lower than Eva's lithological boundary — expected behavior, not a bug"** — interpretive knowledge.
- **"calc_trace `Nb=?` is cosmetic, not a real input gap"** — avoids chasing red herrings.

I'll flag these to you — decide whether to persist.

---

Good luck. The spike is well-scoped and the plan doc has everything. Start with fresh eyes, verify branch + state, then go.
