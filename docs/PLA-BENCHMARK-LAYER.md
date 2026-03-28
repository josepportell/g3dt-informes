# Plan: Benchmark Layer + Quality Fixes
Created: 2026-03-27

## Context

We now have **readiness** (is a field filled?) via `scripts/collect_readiness.py` + `/g3dt-dev-readiness-summary`. But readiness != correctness. A field can be filled with a wrong value.

**Goal**: Build a **benchmark layer** — extract Eva's correct values from her 7 signed reports, store them, and create a comparison tool. Then use that data to prioritize and validate fixes.

**Why benchmarks first**: Without benchmarks, we fix blind. We might get Vilanova to 90% readiness but with wrong values. With benchmarks, every fix is measurable.

## Available Reference Reports

Eva's signed .docx files in `/mnt/c/claude/g3dt/benchmarks/` — one folder per project, one .docx each.

| Folder | File |
|--------|------|
| 3001621 Castellar del Valles | 3001621_informe_v0.docx |
| 3001631 Rubi | 3001631_informe.docx |
| 4001607 Linyola | 4001607_informe.docx |
| 4001612 Bell-Lloc | 4001612_informe.docx |
| 4001670 Alcoletge | 4001670_informe.docx |
| 4001671 Vilanova de Segria | 4001671_informe.docx |
| 4001679 Anciles | 4001679_informe_V0.docx |

7 projects — covers all unique base projects.

## Phase 1: Benchmark Extraction (one-time, ~2h)

### Step 1.1: Extract text from Eva's .docx files

Create `scripts/extract_reference_text.py`:
- Scans `/mnt/c/claude/g3dt/benchmarks/` — one subfolder per project, one .docx inside
- Uses `python-docx` (already a dependency) to extract all paragraphs + table cells from each reference .docx
- Outputs structured text per project to `docs/benchmarks/{expedient}-text.txt`
- Tables preserved as TSV blocks (key for geotechnical parameter tables)

**Files**:
- Create: `scripts/extract_reference_text.py`
- Create: `docs/benchmarks/` folder

### Step 1.2: Extract structured values via Claude

Create `scripts/extract_benchmark_values.py`:
- Reads the extracted text from Step 1.1
- Uses a structured prompt to extract values matching READINESS_VARIABLES keys
- Outputs `docs/benchmarks/{expedient}-benchmark.json` per project

**JSON schema** — same keys as READINESS_VARIABLES + extras:
```json
{
  "expedient": "4001612",
  "municipality": "Bell-Lloc",
  "source": "4001612_informe.docx",
  "variables": {
    "client": "...",
    "architect_name": "...",
    "geotech_E": 650,
    "geotech_phi": 39,
    "qa_value": 2.98,
    "settlement": 1.20,
    ...
  }
}
```

**Recommendation**: Hybrid — script extracts text, then we manually verify/fill the JSON. For numeric geotechnical values (E, phi, c, Qa, settlement, K30), cross-reference with the deviation matrix already in MEMORY.md (some values already known from previous audit work).

### Step 1.3: Create benchmark index

Create `docs/benchmarks/_index.json`:
```json
{
  "timestamp": "2026-03-28T...",
  "projects": [
    {"expedient": "4001612", "municipality": "Bell-Lloc", "file": "4001612-benchmark.json"},
    ...
  ]
}
```

## Phase 2: Comparison Tool (~1h)

### Step 2.1: Comparison script

Create `scripts/compare_benchmarks.py`:
- Reads `docs/benchmarks/{expedient}-benchmark.json` (Eva's values)
- Reads `docs/validation-latest/{folder}.json` (our pipeline values — already has per-variable values)
- Compares each variable:
  - **Numeric**: relative deviation % (with configurable tolerance, default 5%)
  - **Text**: exact match or fuzzy ratio
  - **Boolean/presence**: match/mismatch
- Outputs `docs/benchmarks/_comparison.json` + stdout summary

### Step 2.2: Comparison subagent

Create `.claude/commands/g3dt-dev-benchmark-compare.md`:
- Reads comparison JSON
- Outputs formatted table: variable, Eva's value, our value, deviation, status
- Highlights mismatches
- Groups by category (same as readiness)

### Step 2.3: Unified dashboard

Update `/g3dt-dev-readiness-summary` to optionally include correctness data when benchmarks exist. Two dimensions:
- **Readiness**: is the field filled? (existing)
- **Correctness**: does our value match Eva's? (new)

## Phase 3: Fixes -- DEFERRED

Not in scope. Fixes will be informed by benchmark comparison results.

## Verification

After each phase:
1. Run `python scripts/collect_readiness.py` to refresh readiness data
2. Run `/g3dt-dev-readiness-summary` to see updated table
3. After Phase 2: run `python scripts/compare_benchmarks.py` to see correctness

## Critical Files

**Existing (read)**:
- `web/api.py:861-922` -- READINESS_VARIABLES definition
- `automation/intelligent_audit.py` -- Existing .docx parsing (reuse paragraph/table extraction)
- `automation/dpsh_extractor.py` -- DPSH Excel extraction (debug for Vilanova/Anciles)
- `automation/auto_extractor.py` -- Phase 0.5 orchestrator

**Create**:
- `scripts/extract_reference_text.py` -- Extract text from Eva's .docx
- `scripts/compare_benchmarks.py` -- Compare benchmark vs pipeline values
- `docs/benchmarks/{expedient}-benchmark.json` -- Per-project reference values
- `.claude/commands/g3dt-dev-benchmark-compare.md` -- Comparison subagent

**Modify**:
- `.claude/commands/g3dt-dev-readiness-summary.md` -- Add optional correctness column

## Known Reference Values (from MEMORY.md, already verified)

Some benchmark values are already known from previous audit work:

| Variable | Bell-Lloc | Rubi | Linyola | Castellar |
|----------|-----------|------|---------|-----------|
| geotech_density | 2.0 | 2.0 | 1.90 | - |
| geotech_E | **650** | 480 | 350 | - |
| qa_value | 2.98 | 3.50 | - | - |
| settlement | **1.20** | **1.50** | - | - |
| k30_value | ~8.7 | ~6.4 | - | - |

These save time -- we don't need to re-extract them from the .docx.
