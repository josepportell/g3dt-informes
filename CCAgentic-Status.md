# CC-Agentic Vision Experiment — Status

**Branch:** `experiment/cc-only-extraction`
**Started:** 2026-04-16
**Last updated:** 2026-04-17 (all 4 tests complete + HITL drawer shipped)

> ✅ **Experiment complete.** T1, T2, T3, T4 all run on 7 projects via OpenRouter + Claude Sonnet 4.6. Data-driven verdict below. Main product outcome: **HITL wizard drawer** — Eva-facing UI that lets her point at missing/low-confidence source documents and get them extracted on demand. Shipped and tested (213 passing tests, 10 new). Remaining open items: pipeline calc-input plumbing bug (G.1), template-aware narrative prompting (F.5), hard-fixture benchmark vs Opus 4.7 (F.4).

## What This Is

An experiment testing whether Claude's vision API ("CC-Agentic") can read G3DT project files (PDFs, Excel, emails) and extract geotechnical variables — either replacing or enhancing parts of the current multi-stage pipeline.

**The current pipeline** has 7+ stages: FileScanner → FileMiner → Groq LLM → ConceptScout → auto_extract → Claude vision → wizard. It scores ~52% average accuracy across 7 reference projects.

**The hypothesis:** CC-Agentic, reading files with iterative reasoning (zoom/crop when unsure), might match or improve the pipeline's extraction — especially for vision-heavy tasks like reading planols and field sheets.

## Key Findings So Far

### Finding 1: CC reads files well, but file availability is the bottleneck
When CC has access to the right documents, it extracts data correctly. The quality of vision reading is comparable to the pipeline's Phase 1. The problem is that many key documents (planols, presuposts) are buried inside email attachments (.msg files) that CC only sees after the pipeline's file discovery phase.

### Finding 2: The pipeline's real value is computation + APIs, not vision
~40% of Eva's ground truth variables require Terzaghi calculations, CTE tables, ICGC geology, Cadastre data, CSN radon lookup, or narrative generation. CC alone cannot produce these. The pipeline's vision extraction (Phase 1) accounts for ~15-20% of variables.

### Finding 3: Agentic vision (crop/zoom) provides marginal improvement
In Round 1 testing, iterative crop/zoom of low-confidence areas improved only ~1 variable per project. The handwritten field sheets are either clearly readable at normal resolution or inherently ambiguous (zoom doesn't help smudged ink).

### Finding 4: File discovery unlocks email-attached documents
Projects like Anciles had `A01_TIPOL.pdf` (a full planol!) inside an email attachment. After file discovery, Anciles jumped from 3.8% to 23.1%. Alcoletge had 3 additional planols in emails. This is the biggest single improvement.

## Tests Defined

| Test | Insertion Point | Purpose | Status | Verdict |
|------|----------------|---------|--------|---------|
| **T1: Post-Discovery** | After Phase 0.3 (FileMiner) | CC as full extractor after file discovery | ✅ All 7 projects | 34.6% with LLM judge vs pipeline ~52% — CC alone doesn't replace pipeline |
| **T2: Gap-Filler** | After full pipeline | CC fills NOT_EXTRACTED variables | ✅ All 7 projects | 57% gap coverage, 48% hit rate — too risky for silent auto-fill, **perfect for HITL drawer** |
| **T3: Parallel Validation** | After Phase 0.3, in parallel | CC as QA layer (catch pipeline errors) | ✅ All 7 projects | 33 disagreements total; CC right 4 / pipeline right 7 — **net negative QA layer** |
| **T4: Planol-Only** | After Phase 0.3, planols only | CC replaces vision for planols specifically | ✅ 3 testable / 4 untestable | 83% on Bell-Lloc clean planol — viable for planol identity subset |

### T1 Results (CC after file discovery)

Post-fix (A.1 image cap + A.2 variable mapping + A.3 JSON parsing) re-run on 2026-04-16:

| Project | Round 1 (raw files) | T1 pre-fix | T1 post-fix | T1 + LLM judge | Pipeline |
|---------|-------------------|------------|-------------|----------------|----------|
| Bell-Lloc | 53.4% | **failed** (image>8000px) | 26% | **38%** | 65% |
| Castellar | 22.4% | 13.8% | 24% | **38%** | 65% |
| Rubí | 22.6% | 17.0% | 34% | **42%** | 51% |
| Linyola | 11.5% | 21.2% | 35% | **44%** | 67% |
| Alcoletge | 7.8% | 17.6% | 28% | **43%** | 43% |
| Vilanova | 3.8% | 5.8% | 8% | **12%** | 41% |
| Anciles | 3.8% | 15.4% | 17% | **25%** | 33% |
| **Average** | — | 13.2% | **24.5%** | **34.6%** | ~52% |

**What the numbers say:**
- A.1 unlocked Bell-Lloc (was blocked by 8000px API limit).
- A.2 variable mapping is where the real uplift came from (~+11pp average).
- A.3 JSON parsing fix had no visible impact — the "20-30% parse failure" estimate was overstated. Defensive code still worth keeping.
- LLM judge adds a further ~+10pp by recovering format/phrasing differences as CLOSE.
- CC-Agentic T1 matches or beats pipeline on its weaker projects (Alcoletge 43=43, Vilanova 12 < 41 — CC still loses) but trails significantly on pipeline strongholds (Linyola 44 vs 67).
- The remaining gap is structural: ~40% of Eva's variables require Terzaghi / CTE / ICGC / Cadastre computations that CC cannot produce from files alone. See Finding 2.

### How T2, T3, T4 actually played out (vs pre-test expectations)

| Test | Pre-test expectation | What actually happened |
|------|----------------------|------------------------|
| T2 | "CC recovers 3-8 additional variables per project at minimal cost" | 57% gap coverage (20/project), but 52% of recovered values are wrong. Silent auto-fill would harm Eva's reports; HITL review is essential. |
| T3 | "Even a 2-3% improvement in catching pipeline errors is valuable — it's free quality" | Not free — CC disagrees with pipeline 33 times across 7 projects and is wrong more often than pipeline (7 vs 4). Net-negative QA layer. |
| T4 | "Bell-Lloc's planol extraction matched Eva on architect, client, building type, floors, areas" | Confirmed: 83% on Bell-Lloc. **But 3 of 7 projects have no architect planol anywhere** — so the surgical replacement only applies when the planol exists in the project folder or email attachments. File availability, not vision quality, is the binding constraint (Finding 1). |

**Real combined outcome:** the hybrid *isn't* "T1 base + T2 gap-fill + T3 QA + T4 planol replacement." It's: keep the pipeline as-is, build a **human-in-the-loop UI** that exposes CC's capabilities to Eva on demand for missing or low-confidence fields. That's the HITL drawer, and it's live.

## Fixes Applied (2026-04-16)

### 1. Variable name mapping — DONE
`_CONCEPT_TO_EVA` in `tests/cc_agentic/compare_results.py` expanded from 6 → 11 entries (added `adjacent_{north,south,east,west}` → `*_fmt` and `settlement_cm` → `settlement`). Agent was deliberately conservative; many concepts simply have no Eva equivalent.

**Impact:** ~+11pp average lift on T1 re-score (Rubí +17, Linyola +14, Castellar +10).

### 2. JSON parsing robustness — DONE
Refactored both parse sites in `tests/cc_agentic/cc_extractor.py` to share a new `_parse_llm_json()` helper with 4-tier fallback: plain parse → fenced block anywhere → balanced-brace walker (string-literal aware) → log + empty dict.

**Impact:** 0 parse failures across 94 API calls in the post-fix T1 sweep. The prior "20-30% failure" estimate was overstated; fix is defensive but not the bottleneck.

### 3. Bell-Lloc image size — DONE
`_render_pdf_pages` now caps output at 8000px on any dimension, proportional rescale with INFO log on trigger. Preserves the existing 4MB fallback.

**Impact:** Bell-Lloc T1 now runs end-to-end (26% accuracy, 38% with LLM judge).

### 4. LLM judge across all projects — DONE
Ran `compare_results.py --llm-judge --update` on all 7 T1 result JSONs. Template-fill cache persists in `_template_fill_cache.json`.

**Impact:** +10pp average lift on top of post-fix numbers (Castellar +14, Alcoletge +15, Bell-Lloc +12).

### 5. Junk files waste API calls — DEFERRED
Linyola used 37 API calls in the post-fix run; cost is noticeable but not blocking. Will revisit if T4 shows it matters.

## File Map

```
tests/cc_agentic/                    # Round 2 test infrastructure
├── cc_extractor.py                  # Anthropic API extraction (vision + text)
├── harness.py                       # Test runner (T1/T2/T3/T4)
├── compare_results.py               # Enhanced comparison + LLM judge
└── results/                         # Output JSONs per test per project
    ├── T1_{expedient}.json          # T1 results
    └── _template_fill_cache.json    # LLM judge cache

tests/cc_only/                       # Round 1 (manual CC extraction)
├── compare_cc_results.py            # Basic comparison script
└── results/
    ├── {expedient}_cc_only.json     # Single-pass extraction
    ├── {expedient}_cc_agentic.json  # With crop/zoom
    ├── 4001612_cc_agentic_trace.json # Action trace (crops, iterations)
    └── SUMMARY.md                   # Round 1 cross-project summary

docs/
├── PLA-TEST-AGENTIC-VISION.md      # Round 1 test plan
└── PLA-TEST-CC-AGENTIC-INSERTION-POINTS.md  # Round 2 test plan (4 tests)

schemas/concepts/report_variables.yaml  # 65 concept definitions (extraction targets)
```

## Decision Framework — resolved

| Question | Data | Verdict |
|----------|------|---------|
| Replace Phase 1 vision with CC? | T4: 83% on Bell-Lloc planol identity, but 3 of 7 projects have no planol available | **Partial yes** — for the planol-identity subset, Sonnet 4.6 matches or exceeds existing vision. But pipeline still needs to handle projects where Eva's planol isn't in the folder (file-availability is the real bottleneck, Finding 1). |
| Add CC as automatic QA layer? | T3: 33 disagreements across 7 projects; CC right 16%, pipeline right 28%, both wrong 56% | **No.** CC would overturn 7 correct pipeline answers to save 4 wrong ones — net loss of quality. |
| Add CC as automatic gap-filler? | T2: 48% correctness on fills | **No** — not as a silent auto-fill. 52% wrong rate is unacceptable for Eva's signed reports. |
| Add CC as **human-in-the-loop** gap-filler? | T2's 48% hit rate becomes deterministically-correct when Eva reviews each fill | **Yes.** This is the HITL drawer, shipped. |
| Full CC-Agentic replaces pipeline? | T1: 34.6% vs pipeline ~52% | **No.** Pipeline's Terzaghi / CTE / ICGC / Cadastre / radon computations are structural — CC can't produce them from files alone (Finding 2). |
| Hybrid CC + pipeline? | All tests combined | **Yes, but narrowly:** CC acts as Eva's on-demand assistant for missing identity fields via the HITL drawer. Pipeline remains the computation + narrative engine. No automatic CC-in-the-loop for Eva's silent-output path. |

## T4 Results (2026-04-16)

Surgical replacement test: run CC on the architect planol only (A.01.pdf / A01_TIPOL.pdf), compare against Eva's planol-scoped variables (29 concepts + mapped Eva aliases like `architect_name_upper`, `plantes`, `adjacent_*_fmt`).

### Filter fix required

The original T4 runner filtered on role names `{planol, projecte_arquitecte, planol_combined}` that don't exist in the real FileScanner output. Actual roles are `architect_plan` and `architect_plan_with_points`. Also expanded the filename fallback to match `A01` (no period) so Anciles's `A01_TIPOL.pdf` is picked up. See `tests/cc_agentic/harness.py` `run_t4`.

### Results

| Project | Vars extracted | T4 analysis |
|---------|----------------|-------------|
| Bell-Lloc | **10/12 (83%)** | All identity fields correct; 2 adjacent narrative fields missed |
| Alcoletge | 4/11 (36%) | Core identity only; wrong architect name (extracted client as architect) |
| Anciles | 5/10 (50%) | Identity fields; superficie + all adjacents missed |

### Three projects untestable

Castellar, Rubí, Linyola have **no architect planol anywhere** (not in project folder, not in email attachments) — just `situation_plan` (location map). Eva must have received these via a channel not saved to disk. Not a code issue.

Vilanova has one unknown PDF (`1.0.pdf`) in email attachments; filter doesn't match it; content unverified.

### Pattern across tested projects

- **Strong:** municipality, client, architect name/company, superficie_parcela, plantes, building_type — extracted with minor format diffs (case, phrasing).
- **Weak:** `adjacent_*_fmt` fields — CC extracts the raw street/parcel info but can't reconstruct Eva's narrative wrapper ("Per la part nord amb..."). These misses consistently drag T4 down.
- **Cost:** 1-2 API calls per project (vs 20-40 for T1). T4 is much cheaper.

### Implication for the surgical replacement hypothesis

T4 is a viable surgical replacement for the **planol identity subset** (architect/client/municipality/superficie/plantes/building_type) — 80%+ correct on Bell-Lloc, cheaply. It is **not** a replacement for full planol parsing because adjacents require narrative reconstruction the pipeline already does. The hybrid play: use CC for planol identity fields, keep the pipeline's narrative assembly for adjacents and templates.

## T2 Results (2026-04-17) — gap-filler

Run via OpenRouter + Claude Sonnet 4.6. T2 = pipeline runs first → identify NOT_EXTRACTED concepts → CC extracts just those from the project files.

| Project | Pipeline gaps | CC filled | w/ Eva truth | ✓Match | ≈Close | ✗Miss |
|---------|--------------:|----------:|-------------:|-------:|-------:|------:|
| Castellar | 30 | 20 | 11 | 2 | 3 | 6 |
| Rubí | 30 | 18 | 9 | 4 | 1 | 4 |
| Linyola | 29 | 21 | 9 | 5 | 3 | **1** |
| Bell-Lloc | 24 | 16 | 7 | 2 | 1 | 4 |
| Alcoletge | 37 | 25 | 14 | 4 | 3 | 7 |
| Vilanova | 54 | 13 | 9 | 0 | 2 | 7 |
| Anciles | 42 | 26 | 14 | 1 | 4 | 9 |
| **TOTAL** | **246** | **139** | **73** | **18** | **17** | **38** |

**Headline numbers:**
- Coverage: CC filled **57% of pipeline gaps** (139 of 246).
- Correctness: of the 73 fills with Eva ground truth, **48% are right** (18+17), **52% are wrong**.
- Cost: ~112 API calls across 7 projects, roughly **$0.60 total** on Sonnet 4.6.

**Which concepts CC wins at (≥66% hit rate, ≥3 scored):**
`num_floors` 4/4, `lab_field_company` 3/3, `lab_sample_id` 3/3, `superficie_construida` 80%, `num_dpsh_tests` 71%, `superficie_parcela` 67%. All narrow-scope facts.

**Which concepts CC loses at (≤33% hit rate, ≥3 scored):**
`building_structure_desc` 0/4, `location_sentence` 1/7, `site_description` 1/6. All narrative sentences — the same pattern surfaced in T4. CC extracts the right facts, doesn't reconstruct Eva's prose wrapper.

Example failure:
- Eva: *"a una parcel·la ubicada al carrer de la Miranda nº 39"*
- CC: *"L'obra es situa al carrer de la Miranda nº 39"*

Same facts, different wrapper. With template-aware prompting (task F.5), Sonnet 4.6 should be able to adapt the phrasing — the data suggests ~10pp lift is plausible.

**Source-file patterns:**
- Reference reports (.doc of Eva's prior report): 36–100% per project — the source-of-truth data is already there.
- `PENETROS.pdf` (handwritten DPSH): 20% — CC struggles with handwriting, as expected.
- `pl situació.pdf` (situation plan): 0/3 — role/content mismatch, not extraction failure.

**Verdict:** Silent automated gap-fill is a no-go for Eva's signed reports — a 52% miss rate would inject wrong values half the time. But the same 48% hit rate **is exactly the right raw material for the HITL drawer**: Eva reviews each candidate with confidence + snippet, accepts or types. CC's probabilistic fills become deterministically-correct output through her review loop.

## T3 Results (2026-04-17) — parallel validation

Run via OpenRouter + Claude Sonnet 4.6. T3 = pipeline and CC run independently on the same project files; disagreements are arbitrated against Eva ground truth.

| Project | Disagr | CC right | Pipeline right | Both wrong |
|---------|-------:|---------:|---------------:|-----------:|
| Castellar | 8 | 1 | 1 | 4 |
| Rubí | 5 | 1 | 1 | 2 |
| Linyola | 9 | 2 | 1 | 4 |
| Bell-Lloc | 8 | 0 | 3 | 4 |
| Alcoletge | 1 | 0 | 0 | 0 |
| Vilanova | 1 | 0 | 0 | 0 |
| Anciles | 1 | 0 | 1 | 0 |
| **TOTAL** | **33** | **4 (16%)** | **7 (28%)** | **14 (56%)** |

**Headline findings:**
- **Only 33 disagreements across 7 projects.** Pipeline and CC agree most of the time — CC-as-QA has a very narrow operating window.
- **When they disagree, pipeline is right more often than CC** (28% vs 16%). Using CC to override pipeline values would *reduce* quality on net.
- **Both wrong 56% of the time** they disagree — usually narrative fields or cross-source inferences where neither has Eva's ground truth available at all.

**Verdict: T3's "CC as QA layer over the pipeline" hypothesis doesn't hold up.** CC would overturn 7 correct pipeline answers to save 4 wrong ones — a net loss. The ≈0.6 CC-corrections-per-project doesn't justify the double API cost, and Eva's trust in the output would suffer from a system that silently overrides correct values.

Cost: ~126 API calls across 7 projects, roughly **$1.60 total**.

*Note: the harness's in-file "CC accuracy" and "Pipeline accuracy" numbers are confounded (harness doesn't apply `_CONCEPT_TO_EVA` mapping, so pipeline's real ~52% accuracy reads as 3–12% in that view). The **disagreement analysis above is the valid T3 signal** — it compares CC's value directly to pipeline's value, same naming conventions on both sides.*

## HITL Wizard Drawer (2026-04-17) — main product outcome

The experiment proved CC-Agentic doesn't *replace* the pipeline but can *complement* Eva at review time. The HITL drawer is where those findings landed as a usable feature.

### What it does

When Eva opens a project in the wizard, the system:
1. Runs the full pipeline normally.
2. Enriches each field with `missing_reason` (`no_source_file`, `file_had_no_match`, `extracted_low_confidence`).
3. Adds a subtle amber dashed border to each missing or low-confidence input.
4. Shows a top banner: *"N camps sense font fiable (K grups)"*.

Eva clicks **Resoldre ▾** → drawer opens with two distinct sections:

**Section 1 — "Camps buits"** (empty fields)
Grouped by expected source file (e.g. *Plànol arquitecte: 5 camps*). Per group: drag-drop upload zone. One upload fills many concepts via targeted extraction.

**Section 2 — "Revisar baixa confiança"**
Flat list ordered by ascending confidence (most suspicious first). Each row: concept label · current value · confidence bar · source badge. Three actions: `[Confirmar]` · `[Corregir]` · `[Pujar una altra font]`. The last option re-runs extraction on a different source document and renders the new candidate inline with `[Acceptar el nou]`.

### Components shipped

| Piece | File | Role |
|-------|------|------|
| Expected-source map | `web/expected_sources.py` | concept → (group_label, role_hints); keeps schema-level churn out of `report_variables.yaml` |
| Prefills enrichment | `web/wizard_service.py::_enrich_prefills_with_missing_summary` | adds `confidence`, `missing_reason`, `expected_source_label` per field; builds `_missing_summary` |
| Targeted extraction dispatcher | `automation/targeted_extraction.py` | hybrid: fileminer regex first (free), cc_extractor vision fallback (Sonnet 4.6 subset-schema) |
| Upload endpoint | `POST /api/upload-evidence/{project}` | multipart; allowlist + 25 MB cap + filename sanitizer |
| Extract endpoint | `POST /api/extract-targeted/{project}` | takes upload_id + concept_ids; path-traversal guard; returns per-concept `{value, confidence, page?, snippet?, needs_confirmation}` |
| Drawer UI | `templates/validation/review.html` | amber cue, top banner, split drawer, live wizard update on accept, auto-save suspension while open |
| Tests | `tests/test_targeted_extraction.py` + `tests/test_wizard_evidence_api.py` | 10 new unit/integration tests; path traversal, ext allowlist, oversize cap, fallback-to-vision mocked |

**Test suite status:** 213 tests pass (0 regressions).

**Unused data pattern:** the backend's `missing_reason` classification was there before the drawer even split by it. E.8 (drawer split) turned that dormant field into actual UX value.

## Calculation pipeline — deeper look (G.1, 2026-04-17)

Initial diagnosis from `docs/diagnostics/2026-04-11_*_*.json` showed every MISS project with `calc_trace: Nb=?, c=?, phi=?, B=1.0[DEF], Df=0.8[DEF]`, suggesting inputs weren't reaching the calculator. Investigation found this was a **stale diagnostic**. Today's state is more nuanced.

### What's actually happening (DPSH Excel projects)

Simulated current pipeline with real DPSH extraction on 5 projects (Vilanova + Anciles have no DPSH Excel):

| Project | Nb (current method) | Eva Qa | Pipeline Qa | Status |
|---------|--------------------:|-------:|------------:|--------|
| Castellar | 22.6 | 3.0 | **3.00** | ✅ MATCH (rock cap, c=1.0) |
| Rubí | 41.8 | 3.50 | **3.50** | ✅ MATCH (dense-granular cap) |
| Linyola | 22.6 | 3.0 | 2.50 | MISS −17% (cohesive; phi underestimated by CTE 4.1) |
| Bell-Lloc | 30.3 | 3.0 | **3.00** | ✅ MATCH (formula 3.15 → rounds to 3.0) |
| Alcoletge | 9.4 | 3.50 | 1.50 | MISS −57% (Nb averaging misses dense bearing stratum) |

**3 of 5 projects MATCH.** The calculator's caps + formulas work when inputs are reasonable. Two remaining MISS cases have different root causes:

1. **Linyola (−17%)** — cohesive soil. `nspt_to_phi('cohesive', Nb)` uses CTE 4.1 formula which over-reports phi for granulars but under-reports for llims. Eva uses Crespo Villalaz tables. **Fix belongs to task G.2** (P4 in research doc).

2. **Alcoletge (−57%)** — `DPSHData.overall_average_n20` weights shallow readings 2× and excludes refusal values. For Alcoletge: shallow-zone is very soft (1-5 N20), bearing zone hits refusal at ~1.4 m. Weighted avg 7.8 reflects the soft top, not the bearing stratum where Eva places the foundation. This is a **Nb-selection methodology question that needs Eva's input before we retune** — changing averaging fixes Alcoletge but overshoots Bell-Lloc (see analysis below).

### What was fixed today

**Qa cap classification is now soil-type aware.** Previously the cap logic used only cohesion and Nb:

```
if cohesion >= 0.5:          cap = 3.0 (rock)
elif Nb >= 25:               cap = 3.5 (dense granular)  ← false-fires on cohesives
else:                        cap = 3.0
```

This would incorrectly apply the 3.5 dense-granular cap to cohesive soils whose cohesion happened to be low (e.g. Linyola llims at c=0.05, Nb>25). Fixed to explicitly require `soil_type == 'granular'` for the dense cap. Safer in all cases; doesn't regress any of the 5 MATCH projects. 5 new tests pin the behaviour (`tests/test_terzaghi_caps.py`). Total suite: **218 passing, 0 regressions**.

### What remains open

| Issue | Project(s) affected | Blocker |
|-------|---------------------|---------|
| Cohesive phi correlation | Linyola | G.2 — needs Crespo Villalaz table |
| Nb averaging method for bearing-stratum profiles with soft top + refusal bottom | Alcoletge | Needs Eva's input on which Nb she actually uses (deep-half, last-3-before-refusal, etc.) — changing the default regresses Bell-Lloc |
| DPSH-from-PDF plumbing | Vilanova, Anciles | Neither project has DPSH Excel; handwritten field sheets are CC-readable but aren't wired into `calculate_qa()` |
| Bell-Lloc cemented-gravel classification | Bell-Lloc | Edge case: Eva treats "carbonate matrix cemented" as rock-like (c=1.0) → soft cap 3.0; our pipeline classifies as granular + low-c. Currently matches Eva by coincidence (Qa_uncapped=3.15 rounds to 3.0) but a method change could break it |

Actionable next step: draft an email to Eva with the Nb-selection question and the Bell-Lloc classification question. With her answers, these become small code changes rather than judgment calls.

### G.2 Crespo + Schmertmann helpers — shipped (2026-04-17)

Two rounds of research landed as library code without changing the pipeline's outputs yet:

- **G.2a — Crespo Villalaz + Hunt tables** (`automation/cte_geomech.py`):
  `crespo_phi_cohesive`, `crespo_phi_range`, `crespo_consistency` (with es/ca labels),
  `hunt_cohesion_from_nspt`, `hunt_cohesion_from_qu`. 36 tests pin every row of both
  tables + Spanish/Catalan label localisation. Source: Crespo Villalaz 5ª ed. Cap. 20.
- **G.2c — Meyerhof 1957 + Schmertmann-n dispatcher** (`automation/cte_geomech.py`):
  `peck_hanson_thornburn_phi`, `meyerhof_phi_clean_sand`, `meyerhof_phi_silty_sand`,
  `schmertmann_n_phi(nspt, n_factor)`. Curves digitized from a published Italian
  reproduction (`docs/research/schmertmann-1975/meyerhof-1957-italian-reproduction.png`).
  35 tests including a Linyola regression pin (28° ± 1°).

**Key finding from reading the original 1975 Schmertmann paper** (figures archived in
`docs/research/schmertmann-1975/`): Eva's "n = 2.5 / 2.0 / 1.25" is **a Spanish-engineering
shorthand, not a single chart from the paper.** The formal 1975 method is two steps
(Fig. 2 N→Dr, then Fig. 3 Dr→φ via "coarse-angular" or "fine-rounded" curves). Running
the literal 2-step procedure for Linyola gives φ≈34°, farther from Eva's 28° than our
Meyerhof-based shortcut (which lands at 28°). So **keep the shortcut** — it matches Eva's
practice empirically, even if her doc's "Schmertmann 1970" attribution is historical
shorthand rather than a literal source. Full analysis: `docs/DESIGN-SCHMERTMANN-N.md` §10.

### How many mismatches does the calc chain drive across 7 projects?

Eva's template surfaces 3 calc-chain outputs (the underlying geomech_{phi,E,gamma,cohesion}
are internal expert-overrides she doesn't publish). 2026-04-11 diagnostic status on the
three visible calc variables:

| Concept | MATCH | CLOSE | MISMATCH | N/A |
|---|---:|---:|---:|---:|
| `qa_value` | 1 (Castellar) | 1 (Rubí) | **5** | 0 |
| `k30_value` | 0 | 0 | **2** | 5 (Eva doesn't publish for most) |
| `settlement` | 1 (Rubí) | 0 | **6** | 0 |
| **Total on 7 projects** | **2** | **1** | **13** | 12 |

Per-project visible calc-chain mismatches (MISMATCH=1, CLOSE=0.5):

| Project | Count | Notes |
|---|---:|---|
| Castellar | 2 | K30, settlement |
| Rubí | 1.5 | K30 (MISMATCH), Qa (CLOSE) |
| Linyola | 2 | Qa, settlement — the clear Schmertmann-n target |
| Bell-Lloc | 2 | Qa, settlement — partially fixed by G.1 cap tuning |
| Alcoletge | 2 | Qa, settlement — Nb-averaging issue (G.3) |
| Vilanova | 2 | Qa, settlement — no DPSH Excel (G.4) |
| Anciles | 2 | Qa, settlement — no DPSH Excel (G.4) |
| **Total** | **13.5** | |

**Fan-out effect:** a single wrong φ on one project typically moves 3 downstream
variables (Qa, K30, settlement) because they all feed off the geomech params. So
fixing Linyola's φ via G.2c wiring (when unblocked by G.3) could clear ~3 mismatches
on one project in one change. Fixing Nb-averaging (G.3) could move Alcoletge's
~2 mismatches. Fixing DPSH-from-PDF (G.4) could move 4 mismatches (Vilanova +
Anciles). **Rough upper bound on what the geotech-correctness backlog can clear if
all three tasks land: ~9-10 of the 13 current mismatches.** The rest are driven by
non-calc factors (Eva's professional overrides, narrative formatting, etc.) and
need separate attention.

Note: Figures and tables analyzed during G.2 research are archived in
`docs/research/schmertmann-1975/` (7 PDF screenshots from the 1975 paper +
2 reproductions) with per-file relevance notes in `docs/DESIGN-SCHMERTMANN-N.md` §9.

### Eva's methodology — confirmed by reading the signed informes (2026-04-17 evening)

Deep-reading the 7 signed reports surfaced three big methodology clarifications.
Full consolidation in `docs/METODOLOGIA-EVA.md`. The headlines:

1. **Eva's φ and c come from Crespo Villalaz tables** — every informe contains
   the same citation: *"els paràmetres de cohesió i angle de fregament intern,
   s'han obtingut de les relacions que s'estableixen en el llibre «Mecànica de
   suelos y cimentaciones» de l'autor Carlos Crespo Villalaz"*. **G.2a already
   ships these tables as helpers.** The remaining question (G.3) is which
   Crespo sub-table she uses for llims argilosos — pure-clay Crespo gives 15-20°,
   Eva has 28° for Linyola.

2. **Eva's n-factor is for SPT→qc conversion, not for φ** — the report text
   explicitly reads *"E = mòdul de deformació definit per Schmertmann, que
   s'obté de multiplicar 2.5 (aïllades) o 3.5 (corregudes) pel colpeig del
   penetròmetre estàtic, que s'obté de N (SPT) amb factors de conversió per
   tipus de material"*. The 2.5 / 3.5 are **footing-shape factors**, not
   grain-size factors; the n-factor (2.5 / 2.0 / 1.25) is the **qc/N ratio**.
   **Our G.2c helpers have been rescoped today** to match this — `nspt_to_qc`,
   `schmertmann_E_from_qc`, `schmertmann_E_from_nspt` are the real-semantics
   helpers; the old `schmertmann_n_phi` has been renamed to
   `phi_from_nspt_silty_empirical` and kept as a deprecated alias with a
   prominent note in its docstring.

3. **Eva's bearing-capacity method on heterogeneous profiles uses a bicapa
   criterion from Rodríguez Ortiz**, not the single-layer Terzaghi our
   pipeline applies. Alcoletge's informe cites *"el mètode que proposa el
   llibre de «Curso aplicado de cimentaciones», en el seu capítol 2, de
   J. Maria Rodríguez Ortiz [...] criteris de trencament dels terrenys
   bicapa"*. Eva reduces the profile to 2 layers via weighted average
   under the failure surface, then applies corrections based on the
   resistance ratio between the two layers. **This is a methodology gap**
   — our pipeline doesn't do layer reduction at all. Task G.5 (new) tracks
   the implementation; blocked on obtaining the chapter OR Eva's formula.

**Test suite after G.2c rescoping**: 320 passing, 0 regressions (up from 293).

Research-confirmed consensus items status (from `docs/RECERCA-PRACTICA-GEOTECNICA-ESPANYA.md` section 8):

| # | Item | Status |
|---|------|--------|
| 1 | gamma fixed by lithology (2.0 / 1.90 / 2.20) | ✅ implemented |
| 2 | Qa = min(Terzaghi, T-P) + professional cap | ✅ implemented (but starved of inputs — G.1) |
| 3 | Schmertmann settlement (Es = 2.5×Nb / 3.5×Nb) | ✅ implemented |
| 4 | phi for cohesives via Crespo Villalaz | ❌ not implemented — still CTE 4.1 (Linyola over-reports phi by +28%) — task G.2 |
| 5 | E criterion refinement | ⚠️ partial |
| 6 | K permeability fixed range | ❓ unchecked |

## LLM Routing & Model Selection (2026-04-17)

The CC-Agentic code path and the new HITL wizard drawer both go through a single client factory at `automation/llm_client.py`. Provider and model are env-driven:

```
G3DT_LLM_PROVIDER = openrouter          # or "anthropic" for direct
OPENROUTER_API_KEY = sk-or-...
G3DT_CC_MODEL      = anthropic/claude-sonnet-4.6
G3DT_JUDGE_MODEL   = anthropic/claude-sonnet-4.6    # same model as extraction
```

**On the judge-model choice:** earlier draft had this set to Haiku 4.5 with "cost matters at volume" reasoning. That reasoning doesn't apply here — Eva is the only user of G3DT, there is no volume. Swapped to Sonnet 4.6 so the comparator has the same intelligence as the extractor. Memory-pinned as durable feedback so this argument doesn't get reintroduced on future model decisions.

These live in `clients/g3dt/.env` and are auto-loaded on import. OpenRouter exposes Anthropic's Messages API at `https://openrouter.ai/api` — the Anthropic Python SDK (v0.84) works against it unchanged with `base_url` override; only model slugs differ (`anthropic/claude-sonnet-4.6` vs `claude-sonnet-4-6`).

### Model choices (data-driven)

For **document extraction** (cc_extractor + HITL drawer's `extract_targeted`):

| Model | Price in/out | Context | Role in our stack |
|-------|--------------|---------|-------------------|
| **anthropic/claude-sonnet-4.6** | $3 / $15 | 1M | **Primary.** Anthropic explicitly positions Sonnet 4.6 for "polished document creation". 1M context for multi-page PDFs. |
| anthropic/claude-opus-4.7 | $5 / $25 | 1M | Escalation only. No measurable quality gain on clean planols (benchmark below); worth paying only for confirmed-hard retries. |
| anthropic/claude-haiku-4.5 | $1 / $5 | **200k** | **Not in active use.** Older base (Oct 2025) + smaller context; kept on the table only as an emergency cost fallback. |

For **LLM judge** (`compare_results.py` semantic comparison — short text, no images):
- **anthropic/claude-sonnet-4.6** — same model as extraction. Eva is the only user of the app; no volume pressure justifies trading intelligence for cost on comparisons. Keeping one model across the stack also means extraction quality and judging quality are matched, so the judge isn't downgrading borderline-correct values.

### Budget sanity

| Item | Approx cost (OpenRouter Sonnet 4.6) |
|------|-------------------------------------|
| T1 re-run (7 projects, post-fix) | ~$2.50 (already on Anthropic direct, pre-switch) |
| T4 planol-only (3 testable projects + filter fix retry) | ~$0.20 |
| T2 gap-filler (7 projects, 112 calls) | ~$0.60 |
| T3 parallel validation (7 projects, 126 calls + retries) | ~$1.60 |
| Benchmark harness (2 fixtures × 3 models) | ~$0.13 |
| Smoke tests + HITL drawer validation | <$0.10 |
| F.5 narrative-pattern live validation (2 projects) | ~$0.05 |
| F.4 Sonnet 4.6 vs Opus 4.7 on PENETROS.pdf | ~$0.03 |
| **Total OpenRouter spend this session** | **~$2.70** |

Eva's day-to-day HITL drawer usage should cost pennies — one A.01.pdf upload extracting ~10 identity fields is ~$0.02.

### Benchmark evidence (2 fixtures, 2026-04-17)

Script: `tests/cc_agentic/benchmark_models.py`. Runs vision-only extraction over planol-scope concepts, compares to Eva's ground truth, measures token usage + cost + wall time.

| Fixture | Opus 4.7 | Sonnet 4.6 ↓default | Haiku 4.5 |
|---------|----------|---------------------|-----------|
| Bell-Lloc A.01.pdf | $0.037 / 15.5s | **$0.022 / 15.1s** | $0.007 / 14.2s |
| Alcoletge A.01.pdf | $0.031 / 8.3s  | **$0.019 / 6.7s**  | $0.006 / 7.0s |

**On clean vector planols, all three models return byte-identical output** (same token counts, same extracted strings). Opus is pure overspend on this class of document. Haiku matched them on these fixtures but we don't trust it for "at-all-costs" correctness outside the clean-planol comfort zone: smaller context + older base + positioning that explicitly references *Sonnet 4* (the older one) as its quality ceiling.

**Caveats:**
- Only tested 2 clean architectural planols. Scanned/handwritten docs or complex pressupostos haven't been evaluated yet.
- The benchmark's naive scorer under-reports accuracy (unicode quotes, punctuation). Real semantic correctness on Bell-Lloc ≈ 75% for all three models; Alcoletge ≈ 35% (fewer fields are in the caixetí).
- Rerun the benchmark when we encounter a genuinely hard document — that's when models may diverge and escalation to Opus might earn its keep.

### F.4: Sonnet 4.6 vs Opus 4.7 on a hard fixture (2026-04-17)

Benchmarked Opus 4.7 against Sonnet 4.6 on **Bell-Lloc's handwritten `PENETROS.pdf`** — exactly the scan/handwriting use case Anthropic's 4.7 marketing targets (3× image resolution, 80.6% vs 57.1% OfficeQA Pro). 6 target concepts: `field_work_dates_text`, `expedient`, `client_name`, `street_address`, `num_dpsh_tests`, `field_date`.

| Metric | Sonnet 4.6 | Opus 4.7 | Δ |
|--------|------------|----------|---|
| Tokens in+out | 3362+163 | 3362+142 | same |
| Cost | **$0.0125** | $0.0204 | +63% |
| Wall time | 10.5s | 10.0s | tied |
| Factual extraction | identical values | identical values | 0 diff |
| Catalan register | `2 penetròmetres dinàmics (P1 i P2)` | `2 assaigs de penetròmetre dinàmic` | Opus slightly closer to Eva's "assaigs" |

**Verdict:** Opus 4.7 is **not worth the 63% premium** on G3DT's single-shot extraction workload. Anthropic's headline Opus gains are for multi-step agentic workflows with tool use — not for "read this PDF and return JSON." Keep Sonnet 4.6 as the default across the stack; skip the low-confidence → Opus escalation path.

Budget: ~$0.033 spent on this benchmark.

### F.5 live validation (2026-04-17)

Ran `extract_targeted` on pressupostos for Rubí and Castellar, requesting all 8 narrative concepts with template patterns applied. Findings:

- `location_sentence`: **patterns work as designed.** Rubí → *"a una parcel·la ubicada a Rubí"* (matches Eva's template shape, just shorter because pressupost lacks street+number). Castellar → *"al Carrer Arbrells 18A, Castellar del Vallès"* vs Eva *"en el Carrer dels Arbrells, 18 de Castellar del Vallès"* (same facts, preposition diff).
- `site_description`, `adjacent_*_fmt`, `building_structure_desc`: all returned empty. **Root cause is source-file choice, not F.5** — the pressupost is a budget document, it doesn't contain adjacency prose or site-condition narratives. Those come from field visits / photos / the planol.

**Conclusion on F.5:** Code is correct, patterns reach the model, and the model does adapt output shape when the source carries the needed content. Real-world lift depends on whether Eva uploads the right source for the right concept — which is the HITL drawer's whole design premise. Cost: ~$0.05.

## Next Steps

The experiment phase is closed. Remaining work is productization.

### Done this session

- ✅ **G.1** — investigated; Qa caps are correct, plumbing works on 5/7 projects with DPSH Excel. Shipped defensive fix: dense-granular cap requires `soil_type == 'granular'` (not just `c < 0.5`) to prevent false-fire on cohesives. 5 new tests.
- ✅ **F.5** — template-aware prompting shipped for 8 narrative concepts (`location_sentence`, `site_description`, `building_structure_desc`, `adjacent_{north,south,east,west}_fmt`, `access_street`). Patterns curated from `templates/g3dt-jinja-template.docx`. Threaded end-to-end: `automation/concept_templates.py` → `cc_extractor._build_variable_prompt` (inline TEMPLATE hints) → forwarded to vision and text extractors → auto-pulled by `targeted_extraction._vision_extract`. 4 new tests. **Empirical lift still to be measured** — next time we run T2 or the HITL drawer on a real narrative concept, compare CC's output to Eva's.

### Next up

1. **G.3 — Email Eva with two narrow questions.** (a) Which Nb does she actually use on soft-top + refusal-bottom profiles (Alcoletge)? (b) How does she classify cemented/carbonate gravels — rock (c=1.0) or dense granular? Answers unblock 2 currently-MISS projects.
2. **G.4 — Wire DPSH-from-PDF vision into `calculate_qa()`.** Vilanova + Anciles have no DPSH Excel; their handwritten field sheets (role `dpsh_field_sheet`) are CC-readable but not plumbed into the calc.
3. **F.4 — Benchmark Sonnet 4.6 vs Opus 4.7 on a hard fixture.** Per Anthropic's 4.7 marketing (98.5% vs 54.5% computer-use, 80.6% vs 57.1% OfficeQA Pro, 3× image resolution), Opus *might* earn its keep on scans / handwritten / multi-page docs where the 2-fixture planol benchmark showed it as pure overspend. Cost: ~$0.20 on one hard fixture (PENETROS.pdf or pressupost). Decides whether to add a low-confidence → Opus escalation path.
4. **G.2 — Crespo Villalaz for cohesive phi.** P4 from the research doc. CTE 4.1 over-reports phi for cohesives by ~+28% (Linyola). Needs the book reference or a digitized table. Medium effort.
5. **F.5 empirical validation** — re-run the 4 cohesive-narrative misses from T2 (location_sentence Castellar/Rubí, site_description Castellar/Rubí) with patterns applied. Expected ~10pp lift. Cost: <$0.10.

### Lower priority

6. **E.8 follow-up (future)** — if Eva reports the drawer feels noisy, add a collapsible "all-resolved" summary at bottom so she can see what was auto-filled without expanding each group.
7. **Junk-file deduplication (deferred from T1 fix list #5)** — some small images still get sent to vision API. Not blocking; address if costs start to matter at Eva's usage volume.

## For Fresh Sessions

Read this file first. Then:
- For the experiment plan: `docs/PLA-TEST-CC-AGENTIC-INSERTION-POINTS.md`
- For Round 1 detailed results: `tests/cc_only/results/SUMMARY.md`
- For the concept schema (what variables we extract): `schemas/concepts/report_variables.yaml`
- For Eva's ground truth format: `reference-material/4001612 BELL-LLOC/validation/eva_reference_values.json`
- For pipeline architecture: `CLAUDE.md` (Pipeline de Generació d'Informes section)
- For the test harness code: `tests/cc_agentic/harness.py` (start here, it imports cc_extractor and compare_results)
