# CC-Agentic Vision Test Results — All 7 Projects

**Date:** 2026-04-16  
**Method:** Claude Code reads raw project files (PDFs via vision, Excel via Python, text files) + agentic crops for low-confidence areas.  
**Baseline:** Current pipeline diagnostics (2026-04-11)

## Cross-Project Comparison

| Project | Eva vars | CC-Agentic MATCH | CC-Agentic CLOSE | CC-Agentic Acc% | Pipeline Acc%* | Has Planol | Has Lab PDF | Has Sondeig Annex |
|---------|----------|-----------------|------------------|----------------|---------------|-----------|------------|------------------|
| **Bell-Lloc** | 58 | 30 | 1 | **53.4%** | 65.1% | YES (A.01) | YES | YES |
| **Castellar** | 58 | 11 | 2 | **22.4%** | 65.1% | NO | YES | YES |
| **Rubí** | 53 | 10 | 2 | **22.6%** | 51.3% | NO | YES | NO |
| **Linyola** | 52 | 5 | 1 | **11.5%** | 66.7% | NO | YES (partial) | NO |
| **Alcoletge** | 51 | 2 | 2 | **7.8%** | 43.3% | YES (basic) | NO lab PDF | NO |
| **Vilanova** | 52 | 0 | 2 | **3.8%** | 40.6% | NO | NO lab PDF | NO |
| **Anciles** | 52 | 0 | 2 | **3.8%** | 33.3% | NO | NO lab PDF | NO |
| **AVERAGE** | **53.7** | **8.3** | **1.7** | **17.9%** | **52.2%** | | | |

*Pipeline accuracy = best run from diagnostic snapshots (Match+Close / total evaluated)

## Why Bell-Lloc >> Other Projects

Bell-Lloc has the **richest source files**: A.01.pdf (planol with planejament table, aerial photos, cadastre), lab PDF, sondeig formatted annex, DADES CLIENT.txt. Most other projects lack one or more of these critical files:

| Source file | Bell-Lloc | Castellar | Rubí | Linyola | Alcoletge | Vilanova | Anciles |
|-------------|----------|-----------|------|---------|-----------|----------|---------|
| Planol (A.01.pdf) | Full | NO | NO | NO | Basic | NO | NO |
| Lab PDF (Soilassaig) | YES | YES | YES | YES | NO | NO | NO |
| Sondeig annex (formatted) | YES | YES | NO | NO | NO | NO | NO |
| COORDENADES.txt | YES | YES | YES | YES | YES | NO | NO |
| DADES CLIENT.txt | YES | NO | NO | NO | NO | NO | NO |
| DPSH Excel | YES | YES | YES | YES | YES | YES* | YES* |

*DPSH Excel at non-standard path (ANEXOS/ instead of ANNEXES/)

## What CC-Agentic Extracts Well vs Poorly

### Consistently good (when file exists):
- `expedient` — from folder name (100% across all projects)
- `municipality` — from field sheets (high accuracy when readable)
- `data_camp_text` — from field sheet dates
- `sulfate_value` — from lab PDF (when available)
- `dpsh_tests` — basic test count and refusal depths
- `lab_*` fields — from lab PDF (when available)
- `spt_*` fields — from sondeig annex (when available)

### Only from planol:
- `architect_name`, `architect_company` — ONLY from A.01.pdf title block
- `client` — from planol OR sondeig annex (if obra description includes client name)
- `building_type` — from planol OR sondeig annex obra description
- `superficie_*`, `plantes`, `building_height_m` — ONLY from planol planejament table
- `adjacent_*` — ONLY from planol aerial/cadastre views

### Never from CC alone:
- Computation: `qa_value`, `settlement`, `geotech_rows`, `cte_*`, `perm_rows`, `seismic_rows`
- External APIs: `radon_zone`, `seismic_ab_text`, `geo_p`
- Narrative: `conclusions_*`, `site_description`, `materials_intro`

## Agentic Vision Impact

Tested on Bell-Lloc (6 crops, 2 iterations max):
- **True vision improvement: +1 variable** (adjacent_west_fmt from 500 DPI aerial zoom)
- **Encoding fix: +2 variables** (Unicode apostrophe in data_camp_text, municipality)
- **Confirmed 4 variables** at higher confidence (no value change)

**Conclusion: Agentic vision (crop/zoom) provides marginal benefit** — ~1 variable per project. The main bottleneck is file availability, not vision resolution.

## Key Finding: File Availability Drives Everything

The CC-Agentic approach's accuracy is almost entirely determined by **which source files exist in the project folder**:

| Files present | Expected CC-Agentic range |
|--------------|--------------------------|
| Planol + Lab PDF + Sondeig annex + DADES | **40-55%** (Bell-Lloc) |
| Lab PDF + Sondeig annex (no planol) | **20-25%** (Castellar, Rubí) |
| Field sheets only + partial lab | **8-12%** (Linyola, Alcoletge) |
| Field sheets only | **3-5%** (Vilanova, Anciles) |

The current pipeline overcomes this through:
1. **FileMiner** — extracts from emails, docx, Excel files that CC doesn't read
2. **Groq LLM** — fills gaps from text that Python miners miss
3. **ConceptScout** — maps concepts to files across all subdirectories
4. **auto_extractor** — DPSH Excel, ICGC API, Cadastre API, geocoding
5. **Computation** — Terzaghi, CTE tables, seismic parameters

## Verdict

**CC-Agentic is NOT a replacement for the pipeline.** It reaches ~53% on the best-case project (Bell-Lloc) vs pipeline's 65%, and drops to 3-22% on projects with fewer source files.

**However, CC vision reads ARE comparable to the pipeline's Phase 1 vision** on the specific PDFs it reads (planol, DPSH field sheet, sondeig). The value of the multi-stage pipeline is in Phases 0.3-0.5 (text mining, LLM gap-filling, API calls, computation), not in vision quality.

**Recommendation:** Keep the current pipeline. Consider CC/agentic vision as a **fallback or validation layer** for specific low-confidence extractions (e.g., adjacents from aerial photos, ambiguous handwritten values).
