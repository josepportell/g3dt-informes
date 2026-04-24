# For new-you — session handoff 2026-04-25

**Written:** 2026-04-24 (end of session)
**Target:** fresh session picking up the AI Pipeline work — 4 stages shipped, D15/D17/D14/D16 fixes queued next.
**Session one-liner:** Built the entire AI Pipeline feature end-to-end (Stages 1–4), validated it with a real full-project Stage 4 run on Alcoletge (72 sources, 620 candidates, 77 of 88 concepts covered at ≥0.8 confidence), captured 14 deferred issues. Hit Anthropic per-key usage cap mid-run; can't make more Anthropic calls until 2026-05-01.

---

## Reading order (before touching code)

1. **This doc** (you're here).
2. **`docs/ARQUITECTURA-AI-PIPELINE.md`** — 12-section architecture doc. It's the source of truth. Stages 1–4 marked "implementada", Stage 4 §7 documents the per-source LLM call shape, error classification rules, cache design, and Stage 5 reframing (authority ranking, not reduction) in §7.6 + the roadmap.
3. **`docs/AI-PIPELINE-DEFERRED.md`** — 14 entries (D1–D17, numbered non-contiguously after session-time surfacing). Each has severity tag + stage + fix direction. Your next work lives here.
4. **`docs/research/vision-llms-pricing.md`** — pricing reference for when you implement D1 (logo filter) and need to pick a cheap vision provider. Recommendation: use `gpt-4.1-mini` as v1 (already wired), Gemma 3 4B via OpenRouter as v2.
5. **`MEMORY.md`** (auto-memory) — Eva's methodology, feedback rules, Stage 4 is the ONLY NEW PIECE to auto-memory this session; everything else is in the arch doc.
6. **`reference-material/4001670 ALCOLETGE/validation/ai_analysis.json`** — real Stage 4 output on 72 sources. This is your unit-test data for Stage 5 design without any new LLM calls.
7. **`docs/_FOR-NEW-YOU-20260424.md`** — yesterday's handoff, which predates the AI Pipeline work. Context for the deterministic pipeline / Action 2 / spike experiment discussion that's been deferred while we built the AI Pipeline.

---

## Current state — what's where

**Branch:** `experiment/ai-pipeline`
**Parent:** `feature/action-2-deterministic`
**Main:** `main`

**Session commits (newest first):**
- `82c127d` docs: vision LLM pricing reference table
- `da1b802` docs: AI Pipeline deferred-issues log (14 entries)
- `9cab85e` **feat: AI Pipeline Stage 4 — per-source LLM analysis**
- `c98fb31` docs: Stage 4 design
- `dbbc080` docs: mark Stage 3 implemented
- `b491fd0` **feat: AI Pipeline Stage 3 — conversion**
- `102c19a` docs: Stage 3 design
- `df87401` feat: image preview modal
- `9ab1807` fix: empty `__init__.py` to avoid concurrent-load race
- `8a344ac` **feat: AI Pipeline Stage 2 — typology + image extraction**
- `224accd` docs: Stage 2 design
- `da414a5` **feat: AI Pipeline Stage 1 — inventory**

Test state: **767 passing, 1 skipped, 2 deselected** (same baseline as yesterday's 679 + 88 new AI-pipeline tests across 4 files).

**Uncommitted noise:** same pipeline artifacts as yesterday (`docs/benchmarks/_llm_judge_cache.json`, `reference-material/*/file_mapping.json`, `concept_map.json`, `mined_images/*`). Not our work. Safe to `git checkout --` if in the way.

---

## Critical interpretive rules

### 1. Anthropic usage cap bites until 2026-05-01 00:00 UTC
The Alcoletge full run hit an account-level "specified API usage limits" cap. Any `ANTHROPIC_API_KEY` call fails with **HTTP 400** (NOT 402) and the message *"You have reached your specified API usage limits. You will regain access on 2026-05-01 at 00:00 UTC."*. Cost before the cap: $4.06 over 72 successful sources. Plan your work to need **zero new Anthropic calls** until the reset — the existing Alcoletge manifest + caches + 767 tests give you plenty to work with.

### 2. Stage 4 error classifier misses this specific 400
Our classifier treats HTTP 400 as non-systemic (generic invalid_request_error). This is exactly D15. Result during the Alcoletge run: the circuit breaker tripped correctly after 3 consecutive 400s — we DIDN'T burn hundreds of calls — but we did waste 3. Fixing D15 is the first thing you should do.

### 3. The existing pipeline still uses Anthropic vision in Phase 1 (plànol/sondeig/penetros)
If you open the wizard and select a project, the regular pipeline's prefill chain may call Anthropic for the Phase-1 PDF extractions. Those WILL fail until the cap resets. The AI Pipeline tab reads from the saved `ai_analysis.json` manifest via cache hits (zero new API calls) — safe to inspect even during the cap.

### 4. Stage 5 is NOT a reduce — it's authority ranking per concept
Per Josep's reframe (captured in arch doc §7.2 and the Fase 5 roadmap entry): Stage 5 produces an ordered list of candidates per concept using SourceInsight metadata + Eva's authority rules. It does NOT pick final values — that's Stage 6. This split lets Eva correct rules once (*"plànol caixetí > email body for plot dimensions"*) instead of re-picking per project.

### 5. SourceInsight field is genuinely valuable
The Stage 4 LLM is asked to describe what each source IS before extracting values. On Alcoletge, it produced insights like *"Internal G3DT project briefing email forwarding a client request for a geotechnical study for a residential extension at Carrer Girasols 7"* with authors, dates, versions, related sources. Stage 5 eats this to rank candidates. Don't be tempted to strip SourceInsight to save tokens — it's load-bearing.

### 6. Test fixture gotcha: solid-color PNGs compress below 5 KB
Image-extraction tests need **noisy** PNGs (random pixels), not solid colors — solid colors compress to ~200 bytes which is below our `MIN_IMAGE_BYTES=5000` threshold. See `_noisy_png_bytes()` in `tests/test_ai_pipeline_typology.py`. Reuse, don't reinvent.

---

## Load-bearing structural assumptions

### 1. `automation/ai_pipeline/__init__.py` is intentionally empty
Commit `9ab1807` made it empty. Re-exporting symbols from both `inventory.py` and `typology.py` triggered a race under FastAPI's threadpool when two AI-pipeline endpoints fired concurrently. Callers **must** import from submodules directly (which is what api.py, the CLIs, and tests already do). If you find yourself wanting to add re-exports, don't.

### 2. Every Stage 4 FileClass / Candidate carries `source_chain`
`source_chain` is a list like `["email.msg", "attachment:budget.xlsx", "img:img_000.png"]` inherited from Stage 2 → 3 → 4. Stage 5 will need it to reason about provenance. Don't strip it to shorten outputs.

### 3. Passthrough entries in Stage 3 use the original file's path
`ConvertedArtifact(path=fc.path, format="passthrough", source_path=fc.path, ...)`. We don't copy images/text to the `converted/` folder — the manifest references the original location. Re-introducing a copy would double disk use and break cache dedup.

### 4. Stage 4 cache SHA256 includes `_SCHEMA_VERSION`
Bumping `_SCHEMA_VERSION = "1.0"` in `analysis.py` invalidates all cached analyses project-wide. Do this when you change `SourceInsight` or `Candidate` shape; skip otherwise.

### 5. Dev-only detection is hard-coded to `{PDF, PDF V0, PDF-V0}`
Any change to the dev-only rule goes in `automation/ai_pipeline/typology.py:DEV_ONLY_TOPLEVEL_DIRS`. **ACCEPTACIO is NOT dev-only** — it's the client's invoice signing folder (valid input, not Eva's prior deliverable). Tests lock this in (`test_acceptacio_is_not_dev_only`). D17 expands dev-only to also cover `*_informe.doc`, `*_generated*.docx`, `*_portada*.doc`, `*AUDIT_VISUAL*.docx` — via a separate `DEV_ONLY_FILENAME_PATTERNS` list (design decision already made in arch doc §5.7; implementation pending).

### 6. Logos already identified, ready for D1 reference library
Alcoletge extraction produced at least 4 G3DT logo variants at
`validation/ai_pipeline/extracted/PLAN_COST_ALCOLETGE/img_000.png`,
`.../RE_ geotècnic.../image001.jpg`,
`.../RE_ geotècnic.../image008.jpg`,
`.../RE_ geotècnic.../image012.png`. Use them as the reference set when implementing D1's logo filter.

---

## Operational procedures

### Running Stage 4 locally
Requires `ANTHROPIC_API_KEY` in the project's `.env` (already set but capped until May 1). The CLI auto-loads `.env`:
```bash
.venv/bin/python scripts/ai_pipeline_analysis.py --project 4001670 --save
.venv/bin/python scripts/ai_pipeline_analysis.py --project 4001670 --source "PENETROS" --save  # single-source dev
```

Cost reminder: ~$0.056/source on Sonnet average, ~$4 for all of Alcoletge without D16 caching.

### Running the full AI pipeline on a project
```bash
.venv/bin/python scripts/ai_pipeline_inventory.py   --project 4001670 --save  # Stage 1
.venv/bin/python scripts/ai_pipeline_typology.py    --project 4001670 --save  # Stage 2
.venv/bin/python scripts/ai_pipeline_conversion.py  --project 4001670 --save  # Stage 3
.venv/bin/python scripts/ai_pipeline_analysis.py    --project 4001670 --save  # Stage 4 (LLM calls)
```

Stages 1–3 are free; Stage 4 hits Anthropic.

### Tests
```bash
.venv/bin/python -m pytest tests/ --deselect tests/test_bearing_stratum_n20_regression.py
```
Expected: 767 pass. ~3 min runtime. No network/LLM needed — all Stage 4 tests mock the Anthropic client.

### Wizard server
```bash
.venv/bin/python -m web
# then http://localhost:8765/review.html
```
AI Pipeline tab at the right of the tab row. Works from cache even under the Anthropic cap.

### Cache locations
- Stage 1 cache: `{project}/validation/ai_inventory.json`
- Stage 2 cache: `{project}/validation/ai_typology.json` + `validation/ai_pipeline/extracted/{stem}/`
- Stage 3 cache: `{project}/validation/ai_conversion.json` + `validation/ai_pipeline/converted/{stem}/`
- Stage 4 cache: `{project}/validation/ai_analysis.json` + `validation/ai_pipeline/analysis/{stem}/_cache.json`

To fully re-run Stage 4 on a project, delete `{project}/validation/ai_pipeline/analysis/` and `ai_analysis.json`.

---

## Suggested opening sequence

1. `git status --short && git branch --show-current && git log --oneline -12` — confirm you're on `experiment/ai-pipeline` with the 12 commits since parent.
2. Read this doc → `docs/ARQUITECTURA-AI-PIPELINE.md` → `docs/AI-PIPELINE-DEFERRED.md`.
3. `TaskList` (will be empty on fresh session — that's fine; create tasks from D15/D17/D14/D16 as you start).
4. `.venv/bin/python -m pytest tests/ --deselect tests/test_bearing_stratum_n20_regression.py -q` — confirm baseline (767 pass).
5. **Start with D15** (highest-value fix, ~15 min work + test). Extend `_classify_error` in `automation/ai_pipeline/analysis.py` to treat `400 + "usage limit"/"regain access"` as systemic with `error_type="usage_limit"`. Add mock test. This makes the pipeline fail-fast on the exact failure mode we hit.
6. Then **D17** (~15 min): expand `DEV_ONLY_FILENAME_PATTERNS` in `typology.py`. Catches Eva's `*_informe.doc`, `*_generated*.docx`, `*_portada*.doc`, `*AUDIT_VISUAL*.docx`. Saves ~4 sources/project from Stage 4.
7. Then **D14** (~30 min): fix cache-folder slug collision. Include parent dir in the slug. Regression test.
8. Then **D16** (~45 min): add Anthropic `cache_control: {"type": "ephemeral"}` to the concept YAML + glossary content blocks. Can't measure savings until May 1, but low-risk to land and have ready.

After that, you're well-set for **Session 3 — Stage 5 design** which is the big one. Stage 5 is entirely deterministic-rule-driven (no LLM calls) so it's testable against the existing Alcoletge manifest from day one.

---

## What NOT to do

1. **Don't call Anthropic APIs before 2026-05-01 00:00 UTC** unless the user explicitly says they've raised the cap. The classifier fix (D15) means failures will be clean, but you'll still waste tokens getting to the abort.

2. **Don't re-export symbols in `automation/ai_pipeline/__init__.py`.** Commit `9ab1807` explains why; empty is correct.

3. **Don't copy passthrough artifacts to `converted/`.** Stage 3's `_passthrough` deliberately references original paths. Copying would inflate disk + break dedup.

4. **Don't lower `MIN_IMAGE_BYTES` or `MIN_IMAGE_DIM` thresholds** in `automation/ai_pipeline/typology.py`. They already filter tiny signatures / icons. Test fixtures use random-noise PNGs to exceed them.

5. **Don't silently switch models on failure.** Stage 4 design §7.6 is explicit: no automatic degradation. Env-var upgrade paths (`G3DT_AI_MODEL_GEOTECH`, `G3DT_AI_MODEL_VISION`) are opt-in only.

6. **Don't strip `SourceInsight` or `source_chain`.** They're Stage 5's raw material.

7. **Don't merge `experiment/ai-pipeline` to `main` or even `feature/action-2-deterministic`** without a full re-run on all 7 reference projects post-credit-reset. The branch is an experiment; adoption decision comes after full-parity measurement (arch doc §9).

8. **Don't edit `ai_analysis.json` manually** — it's the truth for Stage 5 testing. Back it up if you need to tinker.

---

## Open tasks (task tracker snapshot)

- **#23 [pending]** Document Stage 4 deferred tasks + issues — superseded by `docs/AI-PIPELINE-DEFERRED.md` (already committed); safe to mark completed on pickup.

Task list from fresh session should become:
- **New D15** — classify 400 "usage limit" as systemic
- **New D17** — expand dev-only filename patterns
- **New D14** — cache-folder slug collision
- **New D16** — Anthropic prompt caching
- **New D1** — logo filter pre-Stage 4 (biggest cost win; design decisions mostly done in deferred doc)
- **Stage 5 design + implementation** — can proceed in parallel; uses `ai_analysis.json` as test data

---

## Hidden wins this session

1. **Stage 4 LLM extraction quality is genuinely high** — 76 of 77 covered concepts at ≥0.8 confidence on Alcoletge. The `SourceInsight` + `Candidate` split with enforced JSON schema + YAML concept context + hand-tuned glossary is the winning formula. Future stages should preserve this output shape.

2. **Circuit breaker saved real money.** When the Anthropic cap hit, we had 3 failed calls instead of 17+. The "fail systemic on first call OR 3 consecutive non-systemic" safety net is a genuinely important design choice — don't weaken it.

3. **Stage 5 has 620 real candidates as test data.** Every future Stage 5 change can be rerun against the existing `ai_analysis.json` without a single new LLM call. Mock-test heaven.

4. **Provider plurality is already reachable.** `.env` already has `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`. D1 logo filter can use gpt-4.1-mini with zero integration work. Any Stage 5+ features needing cheap vision can reach those providers.

5. **Alfonso's framing is now encoded in the design doc** (§5.2, §7.2): "not an AI geotechnical engineer, an intelligent report-writing assistant." Every future design decision should pass this test.

---

## Methodology reminders (auto-memory candidates)

These are cross-session learnings that deserve auto-memory entries. Not urgent; flag if you want me to persist:

- **"Anthropic usage caps present as HTTP 400 with 'specified API usage limits' message, NOT 402 or 401."** — saves 10 minutes of classifier debugging next time.
- **"Solid-color PNGs compress below the 5 KB AI-pipeline image threshold."** — testing gotcha.
- **"`automation/ai_pipeline/__init__.py` must stay empty to avoid concurrent-load races under FastAPI."** — structural knowledge.

---

Good luck. The AI Pipeline is genuinely working and genuinely promising. Start with D15 for a quick win + immediate safety improvement, then let Stage 5 consume the Alcoletge manifest as its proving ground.
