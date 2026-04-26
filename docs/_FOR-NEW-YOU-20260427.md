# For new-you — session handoff 2026-04-27

**Written:** 2026-04-26 (end of session)
**Target:** fresh session ready to execute the live re-run on Alcoletge or continue offline iterations.
**Session one-liner:** Five offline iterations on the AI Pipeline (no API spend) — 8 commits on `experiment/ai-pipeline`, 100 new tests (884 → 984 passing), full diagnostic tool stack shipped, plus Phase 1 calculator delegation and `G3DT_AI_SKIP_GROUPS` env-var. Alcoletge `top1_accuracy` rose 14.7% → 27.66% on a 30%-larger Eva-reference base.

---

## 1. Reading order (before touching code)

1. **This doc** (you're here).
2. **`docs/_RESUM-SESSIO-20260426.md`** — exhaustive summary of every offline change since the last live run (commits, files, metrics, env vars, decisions pending). Single source of truth for "what landed".
3. **`docs/PLA-FASE-5-AUTHORITY-RANKING.md`** — Phase 5 design (the LLM-based ranker that this session iterated on).
4. **`docs/AI-PIPELINE-DEFERRED.md`** — log of D-items. Most "high priority" entries from prior sessions are now resolved or have follow-up actions in this session's investigation docs.
5. **`schemas/ai_pipeline/authority_principles.md`** — re-read end-to-end. Now has TOC + 10 numbered sections; the LLM ranker uses this verbatim. §10 (calculator candidates) and §4 (UTM format) are the most consequential additions.
6. **The five investigation docs** (skim, deep-read whichever is relevant to your current task):
   - `docs/INVESTIGACIO-GEOMECH-STRATUM.md` (A1) — bearing-stratum bug + fix.
   - `docs/INVESTIGACIO-SILENT-SOURCES.md` (A3) — Stage 2 pre-skip rules.
   - `docs/INVESTIGACIO-ARCHITECT-NAME.md` (B2) — owner-built / firm-led conflation.
   - `docs/INVESTIGACIO-PASS-BC-EFFECTIVENESS.md` (B1) — Pass B/C audit, coordinates group net-negative.
   - `docs/INVESTIGACIO-ENGINEERING-DELEGATION.md` (B3) — Phase 1 MVP design.
7. **`MEMORY.md`** (auto-memory) — Eva's methodology + feedback rules. Worth re-reading if you'll touch Qa/geomech logic.

---

## 2. Critical interpretive rules

### 1. The remaining $5 budget is hard-capped

User explicitly said "$5 available, not a penny more". Live re-run is estimated $2.50–2.55. **Do not run two live experiments back-to-back.** The plan is one re-run, then iterate offline against the new manifests. Anything that needs a live-LLM check should batch into the single re-run.

### 2. Top-1 accuracy as currently measured is HONEST after this session

Pre-session 14.7% was inflated downward by:
- Naming mismatches (concept_id vs template-placeholder name) — fixed by alias map.
- Lost intelligent_analysis entries from a destructive re-extract — fixed by merge logic.
- Wrong-stratum geomech ground truth — fixed by bearing-row flatten.
- Missing UTM ground truth — added manually.

Current 27.66% is on a 30%-larger reference base. The improvement isn't 13pp — it's a more honest read of the same underlying pipeline output. **Don't optimize for headline accuracy; optimize for individual concept verdicts that actually matter to Eva.**

### 3. The Alcoletge live run on 2026-04-24 was incomplete

The original Stage 4 hit the API usage cap mid-run; circuit_breaker aborted with 17 sources skipped. The current `ai_analysis.json` reflects 72 sources, NOT the 89 the project has. When you re-run, you'll see ~17 more sources analyzed. Plus D17 will filter ~33 dev-only sources (`_informe.doc`, `_generated*.docx`, their extracted images). Net Stage 4 surface for the re-run: ~63 sources (down from 72).

### 4. Pass C corrupted UTM coordinates last run — protected by env var now

`utm_x: 308782 → 0.70348` and `utm_y: 4613951 → 41.654531` (UTM swapped for lat/lon decimals). The §4 UTM principle in `authority_principles.md` is the soft defense; `G3DT_AI_SKIP_GROUPS=coordinates` is the hard defense. **For the next live run, use the env var.** The principle alone may not be enough.

### 5. Calculator delegation produces 3.0 vs Eva's 3.50 on Alcoletge

This is documented as the qa_cap_rock gap (legacy code has 3.0; MEMORY documents Eva uses 4.0–4.5 for rock). The calculator's output WILL diverge from Eva on multi-layer rock projects until that gap is closed. If you turn `G3DT_ENABLE_CALCULATOR_DELEGATION=true`, expect a `worse` verdict for `qa_value` on Alcoletge — that's an INFORMATION-bearing signal, not a regression.

### 6. The eva_reference_extractor has been improved but still has limits

The `_guard_architect_client_conflation` catches the "Sr. X en nom propi" pattern (Alcoletge case) but does NOT catch the firm-led pattern (Linyola — `BUNYESC ARQUITECTURA EFICIENT, en nom de la SRA. X` correctly maps the firm to architect_company but the extracted `architect_name_upper` ends up being the client). Don't trust positional alignment for `architect_*` fields without sanity-checking against the plànol caixetí.

---

## 3. Load-bearing structural assumptions

### 1. `automation/ai_pipeline/__init__.py` stays empty

Concurrent-load race per commit `9ab1807`. **Don't add re-exports.** Import from submodules.

### 2. `_SCHEMA_VERSION = "1.1"` in `automation/ai_pipeline/ranking.py`

Bumped during D18 cache fix. Invalidates ALL pre-2026-04-26 ranking caches by design. The next live re-run will re-rank everything from scratch — that's expected.

### 3. `_OWN_EXTRACTION_METHODS` set in `automation/reference_extractor.py`

Enumerates which extraction methods the current code emits. Anything NOT in the set (specifically `intelligent_analysis`) gets PRESERVED on re-extraction by `_merge_with_prior`. **Do not add `intelligent_analysis` to the own-set** — that would silently destroy ~125 ground-truth entries across 7 projects.

### 4. `_TERZAGHI_EXTRACTORS` in `automation/ai_pipeline/calculator_pass.py`

Dispatch table for delegated concepts. Must stay in sync with YAML's `delegate_to_calculator: true` markers — guarded by `test_yaml_delegated_concepts_match_dispatch_table`. If you add a third concept, add it to BOTH the YAML and the dispatch.

### 5. The Stage 2 → Stage 4 pre-skips chain

`automation/ai_pipeline/typology.py` has 4 silent-source rules: `coordinates_text` (parse_deterministically), `accounting_memo` (skip), `text_stub` (skip on size+pattern), `pressupost_boilerplate` (skip on parent-stem + img_index). The conversion strategy `parse_deterministically` MUST early-continue in `automation/ai_pipeline/conversion.py` (line ~617) — otherwise Eva sees a misleading "no s'han pogut convertir" warning.

### 6. `geotech_rows[-1]` (NOT `[0]`) in `_flatten_loop_table_concepts`

Bearing stratum, not top stratum. Per Eva's methodology. Single-layer projects: `[-1] == [0]` so no behavioral change. Multi-layer projects: critical correction.

### 7. `G3DT_*` env vars are opt-in (default OFF)

- `G3DT_ENABLE_CALCULATOR_DELEGATION` — Phase 1 calculator pass.
- `G3DT_AI_SKIP_GROUPS` — comma-separated group names to skip in Pass B.

Both default to disabled/empty so existing test invariants don't change. Don't flip the defaults without an explicit user decision.

---

## 4. Operational procedures

### Quick state check (under 30 seconds)

```bash
git status --short | grep -v "reference-material"
git log --oneline -10
.venv/bin/python -m pytest tests/test_ai_pipeline_ranking.py tests/test_ai_pipeline_trace.py tests/test_reference_extractor.py -q
```

Expected: branch `experiment/ai-pipeline`, latest commit `82b45c8`, 184 targeted tests pass.

### Full test suite (~3:30)

```bash
.venv/bin/python -m pytest tests/ --deselect tests/test_bearing_stratum_n20_regression.py -q
```

Baseline 984 passing.

### Live re-run procedure (the moment Josep authorizes)

```bash
# 1. Invalidate Alcoletge AI pipeline caches
PROJ="reference-material/4001670 ALCOLETGE"
rm -f "$PROJ/validation/"{ai_typology,ai_conversion,ai_analysis,ai_ranking,ai_calculations,ai_pipeline_trace}.json
rm -rf "$PROJ/validation/ai_pipeline/"{converted,analysis,ranking,calculations}/
# Also remove extracted images from now-dev-only parents so a fresh Stage 2
# walk doesn't accidentally re-classify stale extractions:
rm -rf "$PROJ/validation/ai_pipeline/extracted/"{4001670_generated_1,4001670_generated_utms,4001670_informe,4001670_portada}/

# 2. Set env vars (Option A or B — see Resum §9 for the choice matrix)
export G3DT_AI_SKIP_GROUPS=coordinates
# Option B/C only:
export G3DT_ENABLE_CALCULATOR_DELEGATION=true

# 3. Run pipeline (Stage 1 is implicit in inventory; Stage 2 onwards explicit)
.venv/bin/python scripts/ai_pipeline_typology.py    --project 4001670 --save  # ~free
.venv/bin/python scripts/ai_pipeline_conversion.py  --project 4001670 --save  # ~free
.venv/bin/python scripts/ai_pipeline_analysis.py    --project 4001670 --save  # ~$2.30
# Optional (Phase 1):
.venv/bin/python scripts/ai_pipeline_calculator_pass.py --project 4001670 --save  # ~free, deterministic
.venv/bin/python scripts/ai_pipeline_ranking.py     --project 4001670 --save  # ~$0.20–0.40

# 4. Measure
.venv/bin/python scripts/ai_pipeline_trace.py --project 4001670 --save --report markdown
.venv/bin/python scripts/ai_pipeline_pass_c_diff.py --project 4001670 --save
```

The `analysis` and `ranking` CLIs both auto-load `.env` for `ANTHROPIC_API_KEY`. If you don't have a `.env` set, run `source .env` first or pass `--api-key`.

### Cache locations

- Stage 1: `validation/ai_inventory.json`
- Stage 2: `validation/ai_typology.json` + `validation/ai_pipeline/extracted/<stem>/`
- Stage 3: `validation/ai_conversion.json` + `validation/ai_pipeline/converted/<stem>/`
- Stage 4: `validation/ai_analysis.json` + `validation/ai_pipeline/analysis/<slug>/_cache.json`
- Stage 4.5 (optional): `validation/ai_calculations.json`
- Stage 5: `validation/ai_ranking.json` + `validation/ai_pipeline/ranking/{<slug>_cache,_group_<slug>_cache,<slug>_revised_cache}.json`
- Trace: `validation/ai_pipeline_trace.json`

### Network gotchas

- No DNS contamination observed this session.
- Anthropic API usage cap is the gating constraint — last live run hit it mid-Stage-4 and circuit_breaker aborted with 17 sources skipped. The cap had been raised to ~$5 for this session; treat that as the hard ceiling.

---

## 5. Suggested opening sequence

1. `git status --short | grep -v reference-material` — confirm clean tree.
2. `git log --oneline -10` — confirm `82b45c8` is HEAD; you should see 8 commits since `15c2263` (iteration 2).
3. `.venv/bin/python -m pytest tests/ --deselect tests/test_bearing_stratum_n20_regression.py -q` — confirm 984 passing.
4. Read `docs/_RESUM-SESSIO-20260426.md` end-to-end (it's the canonical "what landed" doc).
5. Read the most relevant investigation doc for the user's current ask.
6. **If the user asks for the live re-run**: confirm budget remaining ($5 ceiling, ~$2.50 expected spend), confirm option A/B/C, then execute the procedure in §4.
7. **If the user asks for more offline work**: there's still B-class material (e.g., extending reference_extractor to flatten more table-nested concepts, fixing the qa_cap_rock constant, exploring the firm-led extractor fix). All zero-API.

---

## 6. What NOT to do

1. **Don't run a live Stage 4 + Stage 5 without explicit user authorization.** The $5 ceiling is firm. Even a "small test" can blow $0.50.

2. **Don't add `intelligent_analysis` to `_OWN_EXTRACTION_METHODS`.** It would silently destroy ground-truth entries on next re-extract.

3. **Don't change `_TERZAGHI_EXTRACTORS` or YAML `delegate_to_calculator` markers without updating the matching half.** The dispatch-coverage test will catch most cases but it's slow feedback.

4. **Don't bump `_SCHEMA_VERSION` again unless you actually change the prompt shape.** Each bump invalidates all per-concept ranking caches → next live run re-pays for everything.

5. **Don't merge `experiment/ai-pipeline` to `main`.** This branch is experimental; adoption decision lives in `docs/ARQUITECTURA-AI-PIPELINE.md` §9 ("when AI pipeline demonstrates parity over 7 reference projects").

6. **Don't trust the `architect_name_upper` value extracted from `_informe*` files for owner-built or firm-led projects.** Eva's writing convention varies; the positional extractor mis-aligns. Two manual overrides (Alcoletge, Linyola) are in place — don't let a re-extract destroy them (the merge protects them, but verify after any reference_extractor change).

7. **Don't disable the `G3DT_AI_SKIP_GROUPS=coordinates` for the next live run** unless you're explicitly testing whether the §4 UTM principle alone is enough. The corruption is a known regression and the env var is the safety net.

8. **Don't treat the calculator's `qa_value=3.0` as "the calculator is broken".** The `QA_CAP_ROCK` constant gap is the cause; that's a legacy-code fix and an Eva-clarification question, not a Phase 1 calculator-pass bug.

---

## 7. Open tasks (TaskList snapshot)

```
#15  C1  principles consolidation                     COMPLETED
#16  D1  cache invalidation + re-run plan             PENDING (next major action)
#17  Apply A1 + A2 (bearing-stratum + UTM)            COMPLETED
#18  Phase 1 calculator delegation MVP                COMPLETED
#19  A3 silent-source rules                           COMPLETED
#20  G3DT_AI_SKIP_GROUPS env var                      COMPLETED

(A1, A2, A3, B1, B2, B3 investigations all completed earlier in session)
```

D1 is the only open task. The next session's first user prompt will likely be either "execute D1" or "do more offline work first".

---

## 8. Hidden wins

1. **The trace tool is now an irreplaceable measurement instrument.** Every offline iteration this session was driven by what the trace surfaced. Without it, we'd have spent live API credits to discover the bearing-stratum bug, the UTM corruption, the architect_name conflation, and the silent-source waste.

2. **The merge logic in `_merge_with_prior` accidentally became the project's data-preservation backbone.** The session-2 destructive re-extract that lost 125 entries was caught only because the trace tool surfaced the symptom (compared count dropped). The merge prevents that recurring AND lets us add manual ground truth (UTM, architect overrides) that survives every future re-extract. Keep it.

3. **The `delegate_to_calculator` YAML marker pattern scales to Phase 2/3.** Adding `geomech_E/phi/cohesion/gamma` to the calculator pass is now a 5-line change per concept (mark in YAML + add to `_TERZAGHI_EXTRACTORS` dispatch + the test enforces sync). The architectural cost was paid in Phase 1.

4. **The qa_cap_rock gap is now a documented Eva-clarification question rather than a mystery.** Before this session: "qa_value sometimes wrong on rock projects". After: "qa_value is wrong by exactly the rock-cap mismatch between 3.0 (legacy code) and 4.0–4.5 (Eva's docs); ask Eva which rule applies, then fix the constant."

---

## 9. Notes for the auto-memory

If the user lets you persist cross-session learnings, these are worth saving (each is a one-liner that future-you would want to know):

- **"Anthropic ephemeral cache requires ≥1024 tokens per cache_control'd block — small principles files alone are silently uncached."** D18 fix.
- **"Eva's `geomech_*` values are ALWAYS the bearing stratum (last row of geotech_rows), never the top stratum."** A1 finding.
- **"Pass C of the LLM ranker can corrupt structured numeric data (UTM swapped for lat/lon) when the per-group prompt lacks format constraints."** B1 finding + §4 UTM principle.
- **"Eva writes the project's architect in 4 different patterns depending on project type (standard / truncated / owner-built / firm-led); positional extraction works only for the standard pattern."** B2 finding.

These are project-specific enough that they probably belong in MEMORY.md (Claude-instance memory) rather than re-derived from this doc each session.

---

*Handoff doc — 2026-04-26.*
