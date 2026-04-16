# Test Plan: CC-Agentic at Pipeline Insertion Points

## Context

**What we learned from Round 1:** CC-Agentic reading raw project folders scored 17.9% average across 7 projects vs pipeline's 52.2%. The bottleneck was NOT vision quality — it was **file availability**. Projects with planols in email attachments scored 3.8% because CC never saw those files.

**The insight:** Running CC-Agentic AFTER the pipeline's file discovery (Phase 0 + 0.3) gives it access to ALL files including email-extracted planols, presuposts, and project documents. This should dramatically improve accuracy on the 5 projects that scored < 25%.

**Goal:** Run 4 tests at different pipeline insertion points, capture structured data for each, and determine the optimal role for CC-Agentic in the pipeline.

## Tests Overview

| Test | Insertion Point | CC sees | Purpose |
|------|----------------|---------|---------|
| **T1: Post-Discovery** | After Phase 0.3 (FileMiner) | All files + email attachments | CC as Phase 1 replacement |
| **T2: Gap-Filler** | After full pipeline | Pipeline output + source files | CC fills NOT_EXTRACTED vars |
| **T3: Parallel Validation** | After Phase 0.3 (FileMiner) | Same as T1, runs in parallel | CC as QA layer (find pipeline errors) |
| **T4: Planol-Only** | After Phase 0.3, planol files only | Only planol/projecte PDFs | CC for highest-value document type |

## Unified Data Capture Schema

Every test produces a **test result bundle** with this structure:

```
tests/cc_agentic/
├── harness.py                    # Test runner (all 4 tests)
├── cc_extractor.py               # CC extraction logic (reusable)
├── results/
│   ├── {test}_{expedient}.json   # Per-project result
│   ├── {test}_{expedient}_trace.json  # Actions log
│   └── CROSS_{test}.json         # Cross-project summary
└── RESULTS.md                    # Human-readable comparison
```

### Result JSON schema (`{test}_{expedient}.json`)

```json
{
  "schema_version": "2.0",
  "metadata": {
    "test_id": "T1",
    "test_name": "post_discovery",
    "project": "4001612 BELL-LLOC",
    "expedient": "4001612",
    "extraction_date": "2026-04-16",
    "insertion_point": "after_phase_0.3",
    "files_available": 28,
    "files_read": 14,
    "files_from_email": 3,
    "pipeline_phases_run": ["0.1_filescan", "0.3_fileminer"],
    "duration_seconds": 45.2,
    "api_calls": 14,
    "crops_performed": 3,
    "estimated_cost_usd": 0.35
  },
  "files_inventory": [
    {
      "path": "A.01.pdf",
      "origin": "original",
      "role": "planol",
      "read_by_cc": true,
      "pages_read": [1],
      "crops": [{"region": "caixeti", "dpi": 300}],
      "variables_extracted": ["architect_name", "client", "building_type"]
    },
    {
      "path": "validation/msg_attachments/Pressupost.../A01_TIPOL.pdf",
      "origin": "email_attachment",
      "role": "planol",
      "read_by_cc": true,
      "pages_read": [1, 2],
      "crops": [],
      "variables_extracted": ["building_type", "num_floors"]
    }
  ],
  "variables": {
    "variable_name": {
      "value": "extracted value",
      "confidence": 0.90,
      "source_file": "A.01.pdf",
      "source_origin": "original|email_attachment|computed",
      "extraction_method": "vision|text|excel|crop",
      "tier": "A",
      "note": ""
    }
  },
  "comparison": {
    "vs_eva": {
      "match": 30, "close": 1, "mismatch": 4, "not_extracted": 23,
      "accuracy_pct": 53.4,
      "per_tier": {"A": {"match": 20, "close": 1, "mismatch": 2, "not_extracted": 10}},
      "per_origin": {
        "original_files": {"match": 25, "close": 1, "mismatch": 3},
        "email_attachments": {"match": 5, "close": 0, "mismatch": 1}
      }
    },
    "vs_pipeline": {
      "cc_better": ["adjacent_west_fmt"],
      "pipeline_better": ["qa_value", "settlement"],
      "both_match": ["municipality", "expedient"],
      "both_miss": ["materials_intro"],
      "cc_match_pipeline_miss": [],
      "pipeline_match_cc_miss": ["radon_zone"]
    }
  }
}
```

### Trace JSON schema (`{test}_{expedient}_trace.json`)

```json
{
  "metadata": {"test_id": "T1", "project": "4001612 BELL-LLOC"},
  "summary": {
    "total_actions": 12,
    "reads": 8,
    "crops": 3,
    "analysis": 1,
    "max_iterations": 2,
    "variables_from_original": 22,
    "variables_from_email": 5,
    "variables_from_crop": 1
  },
  "actions": [
    {
      "action_id": 1,
      "type": "read",
      "file": "A.01.pdf",
      "origin": "original",
      "pages": [1],
      "target_variables": ["architect_name", "client", "building_type", "num_floors"],
      "variables_found": {"architect_name": "JORDI BOSCH NOVELL", "client": "RAMON MITJANA SL"},
      "confidence_range": [0.85, 0.95],
      "duration_ms": 3200
    },
    {
      "action_id": 5,
      "type": "crop",
      "file": "A.01.pdf",
      "origin": "original",
      "page": 1,
      "region": "aerial west neighbor",
      "dpi": 500,
      "crop_rect": [1526, 640, 1907, 977],
      "trigger": "adjacent_west_fmt confidence < 0.5",
      "result": "IMPROVED",
      "variables_changed": [
        {"variable": "adjacent_west_fmt", "before": 0.35, "after": 0.75, "value_changed": true}
      ]
    }
  ]
}
```

### Cross-project summary (`CROSS_{test}.json`)

```json
{
  "test_id": "T1",
  "test_name": "post_discovery",
  "projects": ["4001612", "3001621", "3001631", ...],
  "global_summary": {
    "total_vars": 376,
    "match": 145, "close": 12, "mismatch": 45, "not_extracted": 174,
    "accuracy_pct": 41.8
  },
  "per_project": {
    "4001612": {"accuracy_pct": 53.4, "files_from_email": 0},
    "4001679": {"accuracy_pct": 28.5, "files_from_email": 2}
  },
  "email_attachment_impact": {
    "projects_improved": ["4001679", "4001670", "4001671"],
    "total_new_variables_from_email": 15,
    "accuracy_before_email": 17.9,
    "accuracy_after_email": 35.2
  },
  "vs_pipeline": {
    "cc_wins": 12,
    "pipeline_wins": 85,
    "ties": 120,
    "cc_unique_finds": ["adjacent_west_fmt@4001612"]
  }
}
```

## Test Implementations

### T1: CC-Agentic Post-Discovery

**Steps:**
1. Run `auto_extract()` through Phase 0.3 only (FileScanner + FileMiner)
   - This creates `file_mapping.json` and extracts `.msg` attachments to `validation/msg_attachments/`
2. Enumerate ALL files: original + email-extracted
3. CC reads each file (PDFs via vision, Excel via Python, text directly)
4. Apply agentic crops for low-confidence areas
5. Compare to Eva ground truth AND pipeline output

**Key code path:**
```python
from automation.auto_extractor import auto_extract
# Run only phases 0-0.3:
result = auto_extract(project_path, skip_phase3=True)
# result.file_mapping has all discovered files
# validation/msg_attachments/ has extracted email files
```

Wait — `skip_phase3` only skips HTTP APIs. We need a way to stop after Phase 0.3. Check if there's a more granular control.

**Actually:** We don't need to modify auto_extract. We just need:
1. Run FileScanner → get file_mapping.json
2. Run FileMiner → get mining_result (which also extracts .msg attachments)
3. List all files (original + email-extracted)
4. CC reads them

```python
from automation.fileminer import mine_project
from automation.file_scanner import FileScanner

scanner = FileScanner(project_path)
file_mapping = scanner.scan()
scanner.save()

mining_result = mine_project(project_path, file_mapping=file_mapping)
# .msg attachments now extracted to validation/msg_attachments/

# List all readable files
all_files = list_all_project_files(project_path)  # includes msg_attachments
```

**Expected improvement:** Projects with email planols (Anciles, Alcoletge, Linyola, Vilanova) should jump from 3-12% to 20-40%.

### T2: CC-Agentic Gap-Filler

**Steps:**
1. Run full pipeline `auto_extract()` + vision
2. Identify variables where pipeline returned NOT_EXTRACTED or low confidence
3. For each gap, identify which source file(s) MIGHT contain the data
4. CC reads those specific files targeting the missing variables
5. Merge CC findings into pipeline output
6. Compare merged result to Eva

**Key insight:** CC is NOT re-reading everything — only targeting gaps. This is efficient.

```python
result = auto_extract(project_path)
prefills = get_prefills(project_name)

gaps = [var for var, val in prefills.items() 
        if val.get("value") is None or val.get("confidence", 0) < 0.5]

# For each gap, find candidate files from concept_map or file_mapping
for var in gaps:
    candidates = result.concept_map.get_files_for_concept(var)
    # CC reads each candidate file targeting this specific variable
```

**Expected value:** Small accuracy boost (2-5%) but very low cost since only targeting gaps.

### T3: CC-Agentic Parallel Validation

**Steps:**
1. Run FileScanner + FileMiner (Phase 0 + 0.3) — same as T1
2. In parallel:
   - **Branch A:** Pipeline continues (Phase 0.4 → 0.5 → 1 → 2 → 3)
   - **Branch B:** CC reads all discovered files
3. Compare both outputs to Eva ground truth
4. Identify disagreements: where CC and pipeline give different values
5. For disagreements, determine which is correct (vs Eva)
6. Flag: "CC caught pipeline error" or "pipeline caught CC error"

**Key data to capture:**
```json
"disagreements": [
  {
    "variable": "client",
    "cc_value": "WOOD COMFORT PROM.",
    "pipeline_value": "GRUP ALMA",
    "eva_value": "WOOD COMFORT PROMOCIONS SLU",
    "cc_correct": true,
    "pipeline_correct": false,
    "source": "CC read sondeig annex, pipeline used email body"
  }
]
```

**Expected value:** Identifies which extraction source is more reliable per variable type.

### T4: CC-Agentic Planol-Only

**Steps:**
1. Run FileScanner + FileMiner (Phase 0 + 0.3)
2. From file_mapping, identify only planol/projecte files (including email-attached ones)
3. CC reads ONLY those planol PDFs (with agentic crops)
4. Extract planol-specific variables: architect, client, building_type, floors, areas, adjacents
5. Feed CC's planol extraction INTO the pipeline (replacing vision_extractor for planols)
6. Run rest of pipeline normally
7. Compare hybrid output to Eva

**Variables targeted (planol-only):**
- `architect_name`, `architect_company`
- `client` (promotor)
- `building_type`, `num_floors`, `building_height_m`
- `superficie_parcela`, `superficie_construida`
- `street_address`, `municipality`
- `adjacent_north/south/east/west`
- `referencia_catastral` (if visible in caixeti)

**Expected value:** If CC reads planols better than current single-shot vision, this is the surgical replacement that delivers most value.

## Implementation: Test Harness

### File: `tests/cc_agentic/harness.py`

```python
"""
CC-Agentic Test Harness.

Usage:
  python tests/cc_agentic/harness.py --test T1 --project "4001612 BELL-LLOC"
  python tests/cc_agentic/harness.py --test T1 --all
  python tests/cc_agentic/harness.py --test T1,T3 --all --compare
"""
```

Orchestrates:
1. Pipeline phase execution (up to the insertion point)
2. File inventory (what's available to CC)
3. CC extraction (delegates to `cc_extractor.py`)
4. Comparison (reuses `scripts/compare_benchmarks.py`)
5. Result + trace JSON generation
6. Cross-project summary

### File: `tests/cc_agentic/cc_extractor.py`

The core CC extraction logic, extracted from what we did manually:
1. Takes a list of files + target variables
2. For each file: reads (PDFs via vision/PyMuPDF, Excel via xlrd, text directly)
3. Maps extracted data to concept IDs
4. Applies agentic crops for low-confidence variables
5. Returns result dict + trace log

**Key design:** This module uses the Anthropic API (same as vision_extractor) — NOT Claude Code interactively. This makes it reproducible and automatable.

```python
def extract_from_files(
    files: list[FileInfo],
    target_variables: list[str] | None = None,  # None = all
    agentic_crops: bool = True,
    max_crops_per_file: int = 3,
    crop_confidence_threshold: float = 0.7,
) -> tuple[dict, list[Action]]:
    """Returns (variables_dict, actions_trace)"""
```

### File: `tests/cc_agentic/compare_results.py`

Enhanced comparison (extends existing `compare_cc_results.py`):
- Compare CC vs Eva (accuracy)
- Compare CC vs Pipeline (disagreements)
- Per-origin breakdown (original files vs email attachments)
- Per-tier breakdown
- Cross-project aggregation

## Execution Order

### Phase 1: Infrastructure (~30 min)
1. Create `tests/cc_agentic/` directory structure
2. Build `cc_extractor.py` — wraps Anthropic API for PDF/file reading
3. Build `harness.py` — orchestrates pipeline phases + CC extraction
4. Build `compare_results.py` — enhanced comparison with pipeline delta

### Phase 2: T1 Post-Discovery (highest priority, ~1 hour)
1. Run for all 7 projects
2. Focus on projects with email planols: Anciles, Alcoletge, Linyola, Vilanova
3. Measure email attachment impact
4. Generate CROSS_T1.json summary

### Phase 3: T4 Planol-Only (~30 min)
1. Run for projects with planols (Bell-Lloc, Alcoletge, + email-attached ones)
2. Compare CC planol reading vs pipeline vision_extractor
3. Measure: does CC read planols better than single-shot Groq/Claude vision?

### Phase 4: T3 Parallel Validation (~45 min)
1. Run for all 7 projects
2. Capture disagreements between CC and pipeline
3. Identify which source wins per variable type
4. Build "CC as QA" value case

### Phase 5: T2 Gap-Filler (~30 min)
1. Run for projects with most NOT_EXTRACTED gaps
2. Measure: can CC fill what the pipeline misses?
3. Compare cost vs benefit

### Phase 6: Decision Summary
Compile all test results into RESULTS.md with:
- Cross-test comparison matrix
- Recommendation per insertion point
- Cost-benefit analysis
- Implementation roadmap

## Files to Create

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `tests/cc_agentic/harness.py` | Test orchestrator | ~200 |
| `tests/cc_agentic/cc_extractor.py` | CC extraction via Anthropic API | ~250 |
| `tests/cc_agentic/compare_results.py` | Enhanced comparison | ~150 |
| `tests/cc_agentic/results/` | Output directory | - |

## Files to Read (not modify)

| File | Purpose |
|------|---------|
| `automation/file_scanner.py` | FileScanner.scan() API |
| `automation/fileminer/__init__.py` | mine_project() API |
| `automation/auto_extractor.py` | Phase execution flow |
| `scripts/compare_benchmarks.py` | Comparison functions to reuse |
| `scripts/diagnostic_trace.py` | Snapshot schema to align with |

## Verification

1. **T1 smoke test:** Run on Bell-Lloc (should match ~53% from Round 1)
2. **T1 email impact:** Run on Anciles (has `A01_TIPOL.pdf` in email → should jump from 3.8% to ~25%+)
3. **T3 disagreement check:** At least 1 project where CC finds a value pipeline missed
4. **Cross-test comparison:** T1 accuracy > Round 1 baseline (17.9%) for all projects with email attachments

## Key Decision Points

After all tests, we'll know:
1. **Is CC-Agentic Post-Discovery worth it?** (T1 accuracy vs pipeline accuracy vs cost)
2. **Should CC replace Phase 1 vision for planols?** (T4 planol accuracy vs current vision)
3. **Is CC useful as a QA layer?** (T3 disagreement analysis — does CC catch real errors?)
4. **Is gap-filling cost-effective?** (T2 improvement per dollar spent)
