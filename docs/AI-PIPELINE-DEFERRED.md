# AI Pipeline — Deferred tasks and known issues

**Last updated:** 2026-04-24
**Branch:** `experiment/ai-pipeline`
**Purpose:** Running log of limitations, bugs, and ideas surfaced during the MVP. Each entry has severity + pointer to the stage it belongs to + suggested fix direction.

---

## High priority (cost / quality affecting)

### D18. Fase 5 prompt caching is a silent no-op — principles block too small

**Surfaced:** 2026-04-24 Alcoletge run (72 sources, 71 Pass-A + 13 Pass-B + 38 Pass-C calls, $4.63 actual).
**Stage:** 5.
**Severity:** High (cost).

Pass A/B/C attach `cache_control: {"type": "ephemeral"}` to the authority-principles block. Anthropic's ephemeral cache requires ≥1024 tokens per block (Sonnet). Our principles file is ~300 tokens → block silently ignored. Result: `cache_creation_input_tokens` and `cache_read_input_tokens` are always 0 across all 122 calls on Alcoletge, and the full 300-token principles + ~2k concept-adjacent static context is paid at full price 122 times.

Confirmed with a smoke test: a 6000-char block caches correctly (`cache_creation=18004`, subsequent call `cache_read=18004`); our 1188-char principles block does not.

**Fix direction:** bundle the full `report_variables.yaml` (88 concepts × ~40 tokens = ~3.5k tokens) into the cached block alongside the principles, mirroring Stage 4's pattern. Combined block would be ~3.8k tokens — well above the 1024-token threshold. Estimated savings: ~$0.75/run on an Alcoletge-sized project.

Implementation: extend `_build_concept_user_content` / `_build_group_user_content` / the group-factor variant to include `_load_concept_yaml()` inside the cached text block. Single-file change in `automation/ai_pipeline/ranking.py`. Existing Pass A / Pass B / Pass C cache keys already hash the concept_def per-concept, so changing the prompt shape invalidates cleanly. Add a test that monkeypatches the Anthropic response usage with `cache_creation_input_tokens>0` and asserts cost formula picks it up (already wired — D16 fix).

### D19. Fase 5 top-1 accuracy below 80% gate on Alcoletge initial run

**Surfaced:** 2026-04-24 Alcoletge validation run.
**Stage:** 5.
**Severity:** High (quality).

Initial measurement against `eva_reference_values.json` on the 18 concepts with ground truth: ~45% headline (3 exact + 5 substring + 10 mismatch). After filtering ground-truth-shape mismatches (Eva's reference captures full narrative paragraphs where Fase 5 correctly extracts the underlying value) and known-hard engineering-judgment cases (`qa_value` on Alcoletge → MEMORY: "Plan 1 ceiling"), realistic top-1 is ~60-70%. Below the ≥80% adoption gate in §11 of the design doc.

Observed genuine ranker failures (3 of 10 mismatches):
- `expedient`: picked lab-report ID `26.0049` over project ID `4001670`. Eva's value ranks 4 of 23.
- `lab_testing_company`: picked `SOIL-ASSAIG` over `TPS PROSPECCIÓ`. Eva's value ranks 2.
- Smaller: formatting differences on `lab_depth`, `lab_tests_text` (punctuation only).

**Fix direction:**
1. Strengthen `schemas/ai_pipeline/authority_principles.md` with explicit rules for identification concepts (`expedient`, `lab_testing_company`, `architect_name` etc.): prefer signed project documents, prefer the company named in the plànol caixetí.
2. Consider adding per-concept glossary entries for the ambiguous-by-design cases.
3. Re-run on Alcoletge (post-budget-top-up) and measure deltas before iterating again.

Until then, Fase 5 is "feature-complete but not adoption-ready." Fase 6 can proceed for UI work but shouldn't be promoted to the default pipeline.

### D15. "API usage limits" HTTP 400 not classified as systemic (Anthropic)

**Surfaced:** 2026-04-24 full Alcoletge run (real error, real credit cap).
**Stage:** 4.
**Severity:** High.

When an Anthropic key hits its configured usage limit, the API returns:
- HTTP 400 (not 402)
- `invalid_request_error` type (not `permission_error`)
- Message: *"You have reached your specified API usage limits. You will regain access on YYYY-MM-DD at 00:00 UTC."*

Our classifier doesn't match any of these. Consequence: the circuit breaker tripped after 3 consecutive failures (our designed safety net) instead of failing fast on call #1. Net result: 3 wasted API calls with a 400 response.

**Fix direction:** extend `_classify_error` to treat `(400 AND ("usage limit" OR "usage limits" OR "regain access"))` as systemic with `error_type="usage_limit"`. Test with a mock that matches this exact error message. Add an action hint to the message: *"Action: increase your Anthropic API usage limit or wait until YYYY-MM-DD to retry"*.

### D16. Prompt caching on concept YAML + glossary would cut cost ~5x on static context

**Surfaced:** 2026-04-24 full Alcoletge run ($4.06 actual vs $1-2 estimated).
**Stage:** 4.
**Severity:** High (cost).

Every per-source call currently ships the full `report_variables.yaml` (~2 k tokens) + `concept_glossary.yaml` (~1.5 k tokens) = ~3.5 k tokens of IDENTICAL context per call. For a 72-source run that's ~250 k tokens of duplicated input (~$0.75 at Sonnet pricing).

Anthropic supports `cache_control: {"type": "ephemeral"}` on content blocks; cache hits charge 10% of normal input cost for the cached portion, and cache lives 5 minutes. Our per-source loop typically runs all calls within 5 min, so the cache should stick.

**Fix direction:** in `_build_user_content`, mark the concept YAML + glossary text blocks with `cache_control`. Measure before/after on the same project. Expected savings: 20-40% on input tokens. Needs verification that our SDK version supports the `cache_control` parameter on content blocks (it should; introduced in late 2024).

### D17. Stage 4 processes `.doc`/`.docx` of Eva's own prior reports

**Surfaced:** 2026-04-24 full Alcoletge run.
**Stage:** 2 (dev-only detection is too narrow).
**Severity:** Medium (cost + noise).

Alcoletge has `4001670_informe.doc`, `4001670_portada.doc`, `4001670_generated (1).docx`, `4001670_generated_utms.docx` at project root. Today's dev-only detection flags only the `PDF/`, `PDF V0/`, `PDF-V0/` top-level folders. These loose `.doc`/`.docx` slip through and become Stage 4 sources — each an LLM call.

**Fix direction:** extend `DEV_ONLY_FILENAME_PATTERNS` in `typology.py` to include:
- `*_informe*.doc` / `*_informe*.pdf` (Eva's signed reports by convention; `*` after `informe` to cover versioned outputs like `_informe_v1.doc`, `_informe v2.doc`)
- `*_generated*.docx` (our own output, already excluded by concept_scout but not by typology)
- `*_portada*.doc` (cover-page drafts)
- `*AUDIT_VISUAL*.docx` (our audit output)

Add tests. Reduces Alcoletge Stage 4 source count by 4.

### D1. Extracted images become their own Stage 4 sources — each pays an LLM call

**Surfaced:** 2026-04-24 live test on Alcoletge.
**Stage:** 4 (and upstream Stage 2/3).
**Severity:** High (cost).

Stage 2 extracts images from PDF/Excel/DOCX into `validation/ai_pipeline/extracted/{stem}/` and registers each as its own `FileClass` with `conversion_strategy=image_passthrough`. Stage 3 emits a per-image `ConvertedArtifact` with `source_path = the_image_path`. Stage 4 groups by `source_path` → each extracted image gets its own LLM call.

On Alcoletge: 54 extracted images → 54 additional analysis calls (most are G3DT logos). Approx cost: $0.20–0.30 of logo-only calls, which produce 0 useful candidates.

**Fix directions:**
1. ~~**v1.1 logo filter** (already parked in §5.6 of arch doc). Discard `.png`/`.jpg` whose perceptual hash matches a reference G3DT logo library.~~ **Shipped (2026-04-25)** — 4 reference logos seeded at `schemas/ai_pipeline/logo_references/`, threshold Hamming ≤ 6, `category="logo_image"` on match. Validated on Alcoletge: 11/11 logos caught, 0 false positives, Hamming 7–21 band empty (clean decision boundary). Design + experiment data: `docs/PLA-D1-LOGO-FILTER.md`.
2. ~~**Stage 4 source grouping change**: group extracted images *with their parent source* so one call sees the parent document + its embedded images together.~~ **Shipped (2026-04-25)** — extracted-image passthroughs now inherit the parent's `source_path` in Stage 3, so Stage 4 groups them alongside the parent's text artifacts. Stage 4 sort order puts text before images. `_SCHEMA_VERSION` bumped to `1.2`.
3. ~~**Stage 2 exclusion flag**: skip extraction from documents whose `document_type` is clearly admin (budgets, invoices) where images are almost always signatures/logos.~~ **Rejected (2026-04-25, Josep)** — Stage 2 is technical-typology only; `document_type` is Stage 4's responsibility. Leaking that decision upstream would couple the two stages and violate the arch-doc separation (§5.1). Admin documents occasionally do carry useful visual content (signed floor plans, stamped lab photos) — a blanket Stage 2 exclusion would lose those.

D1 is fully resolved. D2 (skip-before-calling logos) is now automatically handled: logos are filtered in Stage 2 so they never reach Stage 4 at all.

### D2. ~~Logos identified by Stage 4 still cost full LLM calls before being recognized~~ — Shipped (2026-04-25) via D1#1 logo filter

Resolved by D1#1: Stage 2 now detects logos via perceptual hash against the reference library and sets `useful=False, category="logo_image", conversion_strategy="skip"`. Those images never reach Stage 3 or Stage 4. Design: `docs/PLA-D1-LOGO-FILTER.md`.

---

## Medium priority (UX / correctness)

### D3. Source-filter semantics on CLI are substring-based; no way to pick exactly-one-source

**Surfaced:** 2026-04-24.
**Stage:** 4.
**Severity:** Low.

`--source "re_ geotèc"` expected to match one `.msg` but matched 7 sources because many extracted images inherit the email's path fragment. This is correct per the filter spec but surprising.

**Fix direction:** add `--source-exact <path>` for exact match, or `--source-regex` for regex mode. Or keep as-is and document that substring matches include derived passthroughs.

### D4. `archit_name` candidate "David Graus" inferred from email sender — correct, but worth a Stage 5 rule

**Surfaced:** 2026-04-24.
**Stage:** 5 (designing).
**Severity:** Informative.

On Alcoletge, the LLM correctly inferred the architect from the email sender's domain (`david@davidgraus.com`). This is a lovely signal but Stage 5 should consider that email-sender-as-architect is NOT authoritative if the plànol caixetí says otherwise. Rule: `planol caixetí > email sender domain > filename`.

**Fix direction:** encode in Stage 5 authority rules (coming soon).

### D5. No retry-with-trimmed-prompt on schema validation fallback

**Surfaced:** review of design vs. code.
**Stage:** 4.
**Severity:** Low.

The arch doc (§7.6) said the retry should use a **trimmed** prompt (strip glossary). The current code retries with the SAME prompt. In practice Sonnet rarely fails twice with identical prompt on the same input, so this hasn't bitten us, but worth aligning.

**Fix direction:** when `attempts>=2`, rebuild user_content without the glossary block. Simple change in `_build_user_content`. Add test.

---

## Low priority / nice-to-have

### D6. Token counting doesn't separate prompt-cached tokens (Anthropic prompt caching)

**Surfaced:** code review.
**Stage:** 4.
**Severity:** Low (cost optimization).

If we enabled Anthropic's `cache_control` on the static parts of our prompt (concept YAML + glossary), repeated calls within 5 min would pay 10% of input cost for cached blocks. Could drop Alcoletge cost by 20-40%.

**Fix direction:** add `cache_control: {"type": "ephemeral"}` to the concept schema and glossary text blocks. Requires checking Anthropic SDK support and measuring before/after.

### D7. No wall-clock limit per source

**Surfaced:** code review.
**Stage:** 4.
**Severity:** Low.

Anthropic API default timeout is generous (~10 min). A pathological source (massive PDF with many images) could block the project for minutes. We have retry limits but no per-call deadline.

**Fix direction:** pass `timeout=60` or similar to the SDK. Classify timeout as transient (already classified), which means retry logic already handles it if it fires.

### D8. Wizard doesn't show LLM cost to Eva in a persistent way

**Surfaced:** UI review.
**Stage:** 4.
**Severity:** Low.

Cost appears in `eva_summary` as a line but is lost in the blue banner. For a paying client we should surface running cost in a header badge like `$0.37 this session / $2.84 total`.

**Fix direction:** add a cost-tracker widget to the wizard top bar that accumulates Stage 4 costs across project loads.

### D9. Some concept_ids in glossary use language tokens the YAML keys don't (e.g., "Nb", "N20")

**Surfaced:** schema review.
**Stage:** 4 (glossary).
**Severity:** Low.

The glossary has entries for `"Nb"` and `"N20"` but those aren't literal concept IDs in `report_variables.yaml`. They're field-reference terms. The LLM will read them fine, but the entries don't correspond to concept_ids.

**Fix direction:** either rename glossary keys to match actual concept_ids (e.g., `dpsh_avg_n20`), or add a top-level `aliases` section in the glossary for purely-informational terms.

### D14. Cache folder name collision for generic image stems (`img_000`, `img_001`)

**Surfaced:** 2026-04-24 during full Alcoletge run.
**Stage:** 4.
**Severity:** Medium (re-run correctness).

`_cache_path()` uses `Path(source_path).stem` to build the cache folder. When extracted images are named `img_000.png`, `img_001.png` inside multiple parent extraction folders (which is our Stage 2 convention), they collapse to the same cache folder across parents. The FIRST run works (each source writes its own cache, the final manifest has correct info); the SECOND run has cache misses for all but the last-written image per colliding stem → burns tokens re-analyzing.

**Fix direction:** include a hash of the parent folder in the slug. E.g., `_slugify(parent_dir) + "_" + _slugify(stem)` → `PLAN_COST_ALCOLETGE_img_000` vs `A.01_img_000`. Simple change; add regression test.

### D10. `.msg` YAML frontmatter could leak trailing newlines / special chars

**Surfaced:** code review.
**Stage:** 3.
**Severity:** Very low.

`_convert_msg` writes `from: {value}` without escaping colons or newlines. Emails with multi-line senders (rare) would produce invalid YAML frontmatter. Pandoc and the LLM parse it fine either way, so: cosmetic.

**Fix direction:** use `yaml.safe_dump({...})` for frontmatter instead of manual formatting.

---

## Out-of-scope ideas (Stage 5+)

### D11. Authority-rule DSL for Stage 5

Eva's rules like *"plànol caixetí beats email body for plot dimensions"* should be codifiable in a YAML file (`schemas/ai_pipeline/authority_rules.yaml`) — per-concept ordered list of document_type preferences. Stage 5 reads this + SourceInsights to produce rankings.

### D12. "Propose a Stage 6 value" endpoint for prototyping before the full pipeline

Before Stages 5 and 6 are implemented, a temporary endpoint could pick the top-confidence candidate per concept and display it as "proposed value" — would let Eva click-test Stage 4 output in the wizard without waiting for full pipeline. Pure prototype, not production.

### D13. Benchmark Stage 4 vs existing pipeline's extracted values

For every reference project, Stage 4 emits candidates. Eva's signed reports have the ground truth. A comparison tool could score Stage 4 coverage and accuracy against the existing pipeline — does it reach parity on the 53 core variables? That's the merge-to-main gate.

---

## How to use this file

- Add entries as you observe them during use. Keep severity tag + stage + fix direction.
- Move entries to the arch doc's v1.1 section once chosen for upcoming work.
- Remove entries that are resolved (reference the commit that fixed them in the removal message).
- Dev-in-a-box principle: if it doesn't block Stage 5+ design, it can live here indefinitely.
