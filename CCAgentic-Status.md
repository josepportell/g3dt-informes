# CC-Agentic Vision Experiment — Status

**Branch:** `experiment/cc-only-extraction`  
**Started:** 2026-04-16  
**Last updated:** 2026-04-16  

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

| Test | Insertion Point | Purpose | Status |
|------|----------------|---------|--------|
| **T1: Post-Discovery** | After Phase 0.3 (FileMiner) | CC as full extractor after file discovery | Run on all 7 projects |
| **T2: Gap-Filler** | After full pipeline | CC fills NOT_EXTRACTED variables | Not yet run |
| **T3: Parallel Validation** | After Phase 0.3, in parallel | CC as QA layer (catch pipeline errors) | Not yet run |
| **T4: Planol-Only** | After Phase 0.3, planols only | CC replaces vision for planols specifically | Not yet run |

### T1 Results (CC after file discovery)

| Project | Round 1 (raw files) | T1 (file discovery) | T1 + LLM judge | Pipeline |
|---------|-------------------|---------------------|----------------|----------|
| Bell-Lloc | 53.4% | **failed** (image>8000px) | - | 65% |
| Castellar | 22.4% | 13.8% | pending | 65% |
| Rubí | 22.6% | 17.0% | pending | 51% |
| Linyola | 11.5% | 21.2% | pending | 67% |
| Alcoletge | 7.8% | 17.6% | pending | 43% |
| Vilanova | 3.8% | 5.8% | pending | 41% |
| Anciles | 3.8% | 15.4% | **23.1%** | 33% |

**Note:** T1 automated accuracy is LOWER than Round 1 manual for some projects. See "Known Issues" below.

### Why T2, T3, T4 Should Improve Results

**T2 (Gap-Filler):** The pipeline leaves ~5-15% of variables as NOT_EXTRACTED. CC reading the source files for just those gaps could recover 3-8 additional variables per project at minimal cost (targeted reads, not full extraction).

**T3 (Parallel Validation):** CC and pipeline extract from the same files independently. Where they disagree, we can pick the better value. Even a 2-3% improvement in catching pipeline errors is valuable because it's free quality.

**T4 (Planol-Only):** CC reading planols with agentic crops (zoom into caixeti, aerial photos) was the strongest result in Round 1. Bell-Lloc's planol extraction matched Eva on architect, client, building type, floors, areas — all from one PDF. Replacing just the pipeline's planol vision with CC could improve the ~15 variables that come from planols.

**Combined ceiling:** If T1 provides the base extraction, T2 fills gaps, T3 catches errors, and T4 improves planol reading — the combined approach uses CC where it's strongest and the pipeline where it's strongest. This is the hybrid approach.

## Known Issues (must fix before trusting numbers)

### 1. Variable name mapping is incomplete
Eva's ground truth uses template variable names (`architect_name_upper`, `plantes`, `data_camp_text`). CC extracts to concept schema names (`architect_name`, `num_floors`, `field_work_dates_text`). The mapping in `compare_results.py` covers only 6 aliases. Many correct extractions score as NOT_EXTRACTED because the names don't match.

**Impact:** T1 accuracy is understated by ~5-10%.  
**Fix:** Complete the `_CONCEPT_TO_EVA` mapping in `compare_results.py`. Compare Eva variable list with concept schema to find all aliases.

### 2. JSON parsing failures from API
~20-30% of Anthropic API vision calls return narrative text instead of JSON, despite the prompt requesting "ONLY a JSON object." These responses get discarded (logged as warnings).

**Impact:** Variables that CC could extract are lost.  
**Fix options:** (a) Add `response_format: {"type": "json_object"}` if Anthropic supports it, (b) try extracting JSON from markdown fences more aggressively, (c) use a two-pass approach (extract narrative → parse to JSON), (d) try different prompt structures.

### 3. Bell-Lloc T1 fails on image size
A.01.pdf for Bell-Lloc renders to >8000px at 200 DPI (it's a large A1-size architectural drawing). The Anthropic API rejects images over 8000px on any dimension.

**Impact:** Best reference project can't run T1.  
**Fix:** Cap rendered image dimensions to 8000px in `_render_pdf_pages()`. Already handled for >4MB file size but not for pixel dimensions.

### 4. LLM judge comparison not run on most projects
Only Anciles has the `--llm-judge` comparison. The basic comparison penalizes CC for format differences (e.g., CC extracts "19 de febrer de 2026" but Eva has "El día 19 de febrero de 2026, se visitó..."). The LLM judge + template fill recovers these as CLOSE/MATCH.

**Impact:** All T1 scores except Anciles are understated.  
**Fix:** Run `compare_results.py --llm-judge` on all T1 results. This requires API calls but results are cached.

### 5. Junk files waste API calls
Despite filtering, some small images and irrelevant documents still get sent to the API. Linyola used 34 API calls (many on duplicate email attachment images).

**Impact:** Higher cost, slower runs, no accuracy benefit.  
**Fix:** Smarter file deduplication (hash-based), better role-based filtering using file_mapping.json.

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

## Decision Framework

After all tests complete, the decision matrix:

| Question | Data needed | Decision |
|----------|------------|----------|
| Replace Phase 1 vision with CC? | T4 planol accuracy vs current vision | If CC planol > current by >5%, yes |
| Add CC as QA layer? | T3 disagreements where CC is right | If CC catches >3 errors/project, yes |
| Add CC as gap-filler? | T2 variables recovered vs cost | If >2 vars/project at <$0.10, yes |
| Full CC-Agentic replaces pipeline? | T1 accuracy vs pipeline | Very unlikely — pipeline's computation/APIs are irreplaceable |
| Hybrid CC + pipeline? | All tests combined | Most likely outcome — CC for vision, pipeline for everything else |

## Next Steps (priority order)

1. **Fix the 5 known issues** above (variable mapping, JSON parsing, image size, LLM judge, junk filter)
2. **Re-run T1** with fixes, including LLM judge on all projects
3. **Run T4 (planol-only)** — highest expected value, tests the surgical replacement hypothesis
4. **Run T3 (parallel validation)** — tests the QA layer hypothesis
5. **Run T2 (gap-filler)** — tests incremental improvement hypothesis
6. **Write final conclusions** with cost-benefit analysis

## For Fresh Sessions

Read this file first. Then:
- For the experiment plan: `docs/PLA-TEST-CC-AGENTIC-INSERTION-POINTS.md`
- For Round 1 detailed results: `tests/cc_only/results/SUMMARY.md`
- For the concept schema (what variables we extract): `schemas/concepts/report_variables.yaml`
- For Eva's ground truth format: `reference-material/4001612 BELL-LLOC/validation/eva_reference_values.json`
- For pipeline architecture: `CLAUDE.md` (Pipeline de Generació d'Informes section)
- For the test harness code: `tests/cc_agentic/harness.py` (start here, it imports cc_extractor and compare_results)
