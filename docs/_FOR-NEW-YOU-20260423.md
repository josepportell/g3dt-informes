# For new-you — session handoff 2026-04-23

You are continuing a multi-day thread on the G3DT geotechnical-report-automation project.
Yesterday (2026-04-22) shipped 11 merges and a full re-sweep. Today's job is to execute
the ranked action plan with full awareness of the structural assumptions now in place.

**Read this doc BEFORE touching any code or the action plan.** It captures operational
and interpretive context that isn't in the code itself and won't be obvious from
`STATUS.md` alone.

---

## What to read, in order

1. **This doc** (you're here).
2. `STATUS.md` — "Last Diagnostic Status" section has the per-project table + failure-mode classification.
3. `docs/PLA-PROXIMES-ACCIONS-POST-SWEEP-2026-04-22.md` — the blueprint. 5 actions ranked by leverage with scope, effort, expected impact, fix approach, acceptance criteria.
4. Your auto-memory `MEMORY.md` — Eva's methodology, feedback, project-specific quirks. Three new entries were added yesterday about the sweep: judge noise band, CartoCiudad accent footgun, DNS contamination risk.

After those, you have enough to pick up any of Actions 1-5 without re-deriving yesterday's analysis.

---

## Critical interpretive rule — judge noise band

The sweep benchmark is **noisy within ±1.5pp of its own midpoint**. Apr 19 ran the SAME code three times and got 62.4% / 64.3% / 65.2% — a 2.8pp spread. Today's 64.1% is inside that band.

**Consequences:**
- A re-sweep at e.g. 66% is not proof of improvement — it may be noise.
- A re-sweep at e.g. 63% is not proof of regression — also noise.
- **Judge real improvements by comparing the MISMATCH SET, not just the headline.** Did a specific variable flip MISMATCH→MATCH? That's durable. Did the total rate move +1pp? That's noise.
- For decisive evidence: run the sweep 2-3 times and look at the band, or compare specific variable outcomes per-project against the snapshot in `docs/diagnostics/2026-04-22_*.json`.

---

## Load-bearing structural assumptions (don't accidentally undo these)

Yesterday's work depends on these invariants. Any prompt-tuning, extractor change, or refactor should preserve them:

1. **Vision signals compete in FileMiner.** `automation/concept_scout/__init__.py:concept_sources_to_signals` converts ConceptScout vision probes into FileMiner Signals with source_type mapped to YAML keys (`vision_probe:architect_plan` → `planol_vision`, priority 20). `_phase045_concept_scout` in `auto_extractor.py` re-runs `resolve_competition` on the combined pool. **If you add vision probe concepts, make sure they exist in `schemas/concepts/report_variables.yaml` with a `source_priority` chain** — there's a regression test (`test_all_vision_detectable_concepts_exist_in_registry`) that will catch drift.

2. **G3 internal-address filter lives in TWO places and this is deliberate.**
   - `automation/fileminer/competition.py` pre-filters G3 signals from the competition pool for `{street_address, site_address, client_address}`.
   - `automation/auto_extractor.py:_phase25_geocode` and `_phase3_cadastre_adjacents` also apply `_is_g3_internal_address()` as belt-and-suspenders.
   - **Don't remove either.** User explicitly asked for both layers ("we have had issues with g3 address getting preference in the past").

3. **CartoCiudad `municipio_filter` is deliberately NOT sent.** Server-side accent-strict bug (`Vilanova+de+Segria` returns 0 candidates, `Vilanova+de+Segrià` returns 4). Client-side `_cartociudad_muni_matches` handles muni filtering instead. A commented-out `_CADASTRE_REST_URL_BROKEN_SERVER_SIDE` constant in `cadastre_adjacents.py` marks Step 7 #4's blocked state. **Don't reintroduce either.**

4. **Callejero fast-path in `auto_extractor.py` was removed.** `geocode_project` is now the sole entry point for project-address→UTM. Callejero is still used INSIDE `geocode_project` via `cadastre_progressive_lookup`. Don't re-add the upstream shortcut.

5. **Address vision signals have a confidence floor of 0.9 + field_sheet drop.** Applied in `concept_sources_to_signals` for `{street_address, site_address}`. ConceptSource still appears in `concept_map.json` for audit — only the Signal is suppressed. If you widen this to more concepts, update the tests in `tests/test_vision_signal_merge.py`.

6. **Hedged vision previews are dropped.** Markers in `_HEDGED_PREVIEW_MARKERS` ("appears to", "seems to", "probably", etc.). Prevents Rubí-style `"appears to be 2-3 levels"` from winning competition. **Extending this list is fine**; reducing it needs a good reason.

---

## Re-sweep operational checklist

If you run a fresh 7-project sweep, do this:

```bash
# 1. Clear project-local concept_map caches (forces fresh vision probe + signal competition)
for p in "4001612 BELL-LLOC" "3001621 CASTELLAR DEL VALLES" "3001631 RUBI" \
         "4001607 LINYOLA" "4001670 ALCOLETGE" "4001671 VILANOVA DE SEGRIA" \
         "4001679 ANCILES"; do
  rm -f "reference-material/$p/validation/concept_map.json"
done

# 2. Clear CartoCiudad + geocode caches (cheap, ensures fresh HTTP)
rm -f ~/.g3dt/cache/cartociudad/*.json ~/.g3dt/cache/geocode/*.json

# 3. Run the sweep (~15 min wall-clock with cold caches)
.venv/bin/python scripts/diagnostic_trace.py --save --components --ne-trace

# 4. The CROSS snapshot gets saved to docs/diagnostics/YYYY-MM-DD_CROSS_<run_id>.json
#    Per-project snapshots to docs/diagnostics/YYYY-MM-DD_<project>_<run_id>.json
```

**Network caveat:** DNS failures on CartoCiudad/Nominatim/Groq/OpenAI can silently contaminate a sweep. Yesterday's Anciles run had 13 network errors mid-sweep; its 38.1% is unreliable. Before trusting a new number, grep the log for `"Temporary failure in name resolution"` or `"Connection error"`:

```bash
grep -c "name resolution\|Connection error" /tmp/claude-*/tasks/*.output
```

If hits exist on a specific project, re-run that project alone with `--project <expedient>`.

**Do NOT leave adjacents cache dirty:** `~/.g3dt/cache/cadastre_adjacents/` is UTM-keyed. Old entries from previous wrong-UTM runs remain until TTL. They don't corrupt new runs (different UTM → different key) but they do accumulate. Weekly cleanup is fine.

---

## Comparing snapshots (the useful scripts)

I wrote these yesterday; they're not in the repo as scripts but the patterns work inline:

### Per-project rate across dates
```python
# One-liner to compute per-project match+close across available snapshots
import glob, json
for p in ["4001612_BELL-LLOC", "3001621_CASTELLAR_DEL_VALLES", ...]:
    for date in ("2026-04-21", "2026-04-22", "2026-04-23"):
        f = sorted(glob.glob(f'docs/diagnostics/{date}_{p}_*.json'))
        if f:
            d = json.load(open(f[-1]))
            print(date, p, d['summary']['match_close_pct'])
```

### Status-flip diff between two snapshots
```python
old = json.load(open(old_snapshot))
new = json.load(open(new_snapshot))
for n in sorted(set(old['variables']) | set(new['variables'])):
    o = old['variables'].get(n) or {}
    u = new['variables'].get(n) or {}
    if o.get('status') != u.get('status'):
        print(n, o.get('status'), '->', u.get('status'))
```

This is how I'd verify Action 1 (schema gaps) actually moved the NE count without regressing MATCHes.

---

## Suggested opening sequence for today

1. `git log --oneline experiment/cc-only-extraction | head -15` — refresh on the 11-commit arc.
2. `git status --short` — confirm clean working tree (previous session left STATUS + plan committed).
3. Read `STATUS.md` + this doc + the action plan — ~10 minutes.
4. Pick **Action 1 (schema gaps)** — lowest risk, highest NE recovery. Open `schemas/concepts/report_variables.yaml` and `docs/PLA-PROXIMES-ACCIONS-POST-SWEEP-2026-04-22.md#action-1-schema-gaps-highest-leverage` side-by-side.
5. Dispatch a `code-implementer` with a tight prompt referencing the action plan section.
6. Review → tester → merge → re-sweep to measure impact.
7. Then Action 2 (CTE threshold) — needs Eva's methodology verification first (`docs/RESPOSTA-EVA-PREGUNTES-CALCULS.md` + `MEMORY.md` entries on Schmertmann/Terzaghi-Peck).
8. Then Action 3 (settlement wrap) — biggest single pp gain.

After 1-3 land and a clean re-sweep: the projected headline is ~77-80%. If it lands at 75-76%, that's within noise of the projection (don't over-interpret).

---

## What NOT to do

- **Don't optimize for the headline rate alone.** Today's session proved the headline can stay flat while the pipeline gets qualitatively better (-7 NE, +8pp on Vilanova). The failure-mode frontier is what to optimize.
- **Don't dispatch three implementers in parallel across Actions 1/2/3.** They touch overlapping surfaces (CTE touches `report_data.py`, settlement touches `report_generator.py`, schema touches `schemas/` but has knock-on effects on the vision probe). Sequential with re-sweep between is safer.
- **Don't run the sweep with a warm cache without documenting it.** Warm cache produces faster, but the results aren't reproducible.
- **Don't change the judge prompt.** It was tuned in Step 3b (Apr 21). Any change shifts the noise band and invalidates comparability with the Apr 19 / 2026-04-22 baselines.

---

## Open tasks in the tracker (as of end-of-session 2026-04-22)

- **#13** — Action 1: schema gaps (blocks nothing; start here)
- **#14** — Action 2: CTE threshold bug (blocked by #13)
- **#15** — Action 3: settlement wrap (blocked by #14)
- **#16** — Action 4: identity synthesis (no block; medium effort)
- **#17** — Action 5: adjacent narrative (no block; large effort, deprioritized)
- **#5** — Step 7 #4 (REST/JSON): server-blocked, deferred
- **#7** — Step 7 #6 (INSPIRE WFS-CP): optional, deferred

Full context in `TaskList` and the PLA doc.

---

## One last thing

Yesterday's session had 11 merges, 0 regressions, and full end-to-end proof of the Step 7
chain on Vilanova. The foundations are sound. Your job today is the ground-game execution of
actions 1-3 — small, scoped, well-understood fixes. Don't second-guess the structural work;
build on it.

If in doubt, read the commits from 2026-04-22 in chronological order (`git log --oneline --reverse --since=2026-04-22 --until=2026-04-23`). Each commit message is a small essay explaining what the fix was and why.

Good luck.
