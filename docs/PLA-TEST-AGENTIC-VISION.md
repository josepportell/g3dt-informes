# Test Plan: CC-Only Pipeline + Agentic Vision

## Context

**Problem:** The current G3DT pipeline has 7 stages (FileScanner → FileMiner → Groq → ConceptScout → auto_extract → Claude vision → wizard). At ~55% Tier A accuracy, it works but is complex. The question: can Claude Code itself, acting as an autonomous agent reading project files directly, match or exceed this — especially with "agentic vision" (iterative zoom/crop)?

**Why now:** The pipeline is stable on `feature/concept-format-separation` with 197 tests passing. Good moment to test an alternative approach before adding more complexity.

**Goal:** Measure how many of the 58 ground-truth variables (Bell-Lloc) Claude Code can extract from raw project files, with and without agentic vision. Compare to current pipeline baseline.

## Key Answers to Your Questions

### Can we test agentic vision?
**YES, no deep research needed.** All tools available:
- Claude Code's `Read` tool reads PDFs natively (vision)
- PyMuPDF (fitz) is installed — can crop pages, render at custom DPI
- Pillow available for image manipulation
- The "agentic" part is Claude Code's own reasoning loop: read → notice unclear area → crop with Python → re-read crop → iterate

### Should we test with and without?
**YES — two runs to measure the delta:**
1. **CC-only**: Single-pass read of each file, extract everything visible
2. **CC + agentic**: Same, but iterative zoom/crop on low-confidence PDF areas

### What can CC-only realistically extract?

Of the 58 Eva ground-truth variables, categorized by source:

| Tier | Source | Variables | CC-Only Can? |
|------|--------|-----------|-------------|
| A | From PDFs (planol, DPSH, sondeig, lab) | ~22 | YES — this is the main test |
| A | From Excel (DPSH.xls) | ~3 | YES — via Python xlrd |
| A | From folder name | 1 | YES — trivial |
| B | Need computation (Terzaghi, CTE tables) | ~8 | NO — needs calculator |
| B | Need external APIs (ICGC, Cadastre, CSN) | ~8 | NO — needs HTTP calls |
| C | Narrative synthesis (conclusions, descriptions) | ~10 | PARTIAL — CC can generate but may not match Eva's wording |
| - | From Eva's .doc reference report | ~6 | SKIP — that's the answer, not the source |

**Expected CC-only yield: 25-30 of 58 variables** (the "from files" tier).
**This is a meaningful test** because these same variables are where the current pipeline struggles most with vision accuracy.

## Test Design

### Isolation Strategy
- **Branch**: `experiment/cc-only-extraction` from current `feature/concept-format-separation`
- **All test artifacts** in `tests/cc_only/` — no changes to existing pipeline code
- **Revert**: `git checkout feature/concept-format-separation && git branch -D experiment/cc-only-extraction`

### How the Test Works

**Run 1: CC-only (single pass)**
Claude Code reads every file in Bell-Lloc project folder, one by one:
1. List all files in `reference-material/4001612 BELL-LLOC/`
2. Read each file (PDFs via Read tool = native vision; Excel via Python)
3. For each file, extract all recognizable concepts → JSON
4. Merge results across files (highest confidence wins)
5. Save to `tests/cc_only/results/4001612_cc_only.json`

**Run 2: CC + agentic vision (iterative)**
Same as Run 1, but for PDFs where first pass has low-confidence areas:
1. First pass: Read full PDF page
2. Identify: "N20 column P-2 is hard to read" / "caixeti text too small"
3. Use Python+PyMuPDF to crop that region at 300 DPI → save as temp PNG
4. Read the cropped PNG (high-res detail)
5. Update extraction with refined values
6. Max 2 iterations per unclear area, max 3 crops per file
7. Save to `tests/cc_only/results/4001612_cc_agentic.json`

**Run 3: Comparison**
Use existing `scripts/diagnostic_trace.py` methodology to compare:
- CC-only vs Eva ground truth
- CC+agentic vs Eva ground truth  
- Current pipeline vs Eva ground truth (from existing diagnostic snapshots)

### Output Format
Results JSON compatible with `eva_reference_values.json` structure:
```json
{
  "client": {"value": "RAMON MITJANA S.L", "confidence": 0.95, "source_file": "A.01.pdf"},
  "sulfate_value": {"value": "89.8", "confidence": 0.90, "source_file": "4677-GTL-25...pdf"},
  ...
}
```

### Comparison Script
Small script `tests/cc_only/compare_cc_results.py` that:
- Loads CC result JSON + eva_reference_values.json
- Reuses comparison functions from `scripts/compare_benchmarks.py` (text normalizers, numeric tolerance)
- Outputs side-by-side table: variable, Eva value, CC value, status (MATCH/CLOSE/MISMATCH/NOT_EXTRACTED)
- Summary: counts per tier, accuracy percentage

### Files to Create
1. `tests/cc_only/compare_cc_results.py` — Comparison script (~100 lines)
2. `tests/cc_only/results/` — Directory for output JSONs
3. That's it — the extraction itself is Claude Code acting interactively, not a script

### Files to Read (not modify)
- `reference-material/4001612 BELL-LLOC/` — All project files
- `reference-material/4001612 BELL-LLOC/validation/eva_reference_values.json` — Ground truth
- `schemas/concepts/report_variables.yaml` — Concept definitions (to know what to extract)
- `scripts/compare_benchmarks.py` — Reuse comparison logic

## Execution Sequence

### Phase 1: Setup (~2 min)
1. Create branch `experiment/cc-only-extraction`
2. Create `tests/cc_only/` directory + comparison script
3. Verify Bell-Lloc files are accessible

### Phase 2: CC-Only Extraction (~15 min)
1. Read concept schema to know all 65 variable definitions
2. List all files in Bell-Lloc project
3. Read each file systematically, extract concepts
4. Save results JSON

### Phase 3: CC + Agentic Vision (~20 min)
1. Start from CC-only results
2. For variables with confidence < 0.8, identify source PDF + page region
3. Crop unclear regions with PyMuPDF at 300 DPI
4. Re-read crops, update extractions
5. Save results JSON

### Phase 4: Compare (~5 min)
1. Run comparison script: CC-only vs Eva
2. Run comparison script: CC+agentic vs Eva
3. Pull current pipeline accuracy from latest diagnostic snapshot
4. Side-by-side summary table

### Phase 5: Decision
Based on results:
- **If CC >= current pipeline on "from files" vars**: Worth exploring CC as replacement for Phases 0.3-1
- **If CC < current pipeline**: Agentic vision is additive (improves specific reads) but pipeline stays
- **If agentic vision adds < 2 vars over CC-only**: Zoom/crop not worth the complexity

## What "Agentic Vision" Specifically Targets

| Document | Known Issue | Agentic Fix |
|----------|------------|-------------|
| PENETROS.pdf | Handwritten N20: smudged digits, narrow columns | Crop each test column at 300 DPI |
| SONDEIG.pdf | Faint handwriting on layer descriptions | Crop depth + description columns |
| A.01.pdf | Small caixeti text at 150 DPI | Crop title block at 300 DPI |
| Lab PDF | Small-font result tables | Crop results table |

**Expected delta: 3-6 additional correct variables** (mainly DPSH readings, soil descriptions, caixeti fields).

## Cost & Risk

- **Cost**: ~$0.50-1.00 total for both runs (CC reads ~14 files × ~$0.02-0.03 per vision call, plus crops)
- **Time**: ~40 min interactive Claude Code time
- **Risk**: Zero — all output goes to `tests/cc_only/results/`, no production code touched
- **Revert**: Delete branch, done

## Diagnostic System Integration

The existing diagnostic system (`scripts/diagnostic_trace.py`) already measures:
- Per-variable accuracy across 7 projects
- Per-component attribution (which extraction source produced what)
- Tiered analysis (A=auto, B=manual, C=judgment)
- Signal competition traces

Our CC-only test plugs in by producing results in the same format, enabling direct comparison with the latest diagnostic snapshot (2026-04-11). The comparison script reuses the same text normalizers and numeric tolerance from `scripts/compare_benchmarks.py`.
