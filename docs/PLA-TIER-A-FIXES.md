# Plan: Tier A Remaining Fixes

Created: 2026-03-29
Status: Fixes 1-5 DONE (code changes). Need pipeline re-run to measure impact.

## Context

Tier A has 58/102 match (56.9%). 44 variables fail across 7 projects. Many are depressed by `--skip-vision` (no Claude/Groq PDF reading). Others have real code bugs.

**Key insight**: ~15-20 variables would fix themselves with a vision re-run (no code changes). The rest need targeted fixes.

## Risk assessment

| File | Risk | Why |
|------|------|-----|
| `scripts/compare_benchmarks.py` | **ZERO** | Dev-only script |
| `automation/validation/prompts.py` | **LOW** | Prompt text changes, only affects vision extraction |
| `automation/wizard.py` | **LOW** | Prefill assignment, well-isolated |
| `automation/report_data.py` | **MEDIUM** | Core data assembly, but bearing stratum fix already implemented |
| `automation/report_generator.py` | **MEDIUM** | Per-level geomech table, needs care |
| `automation/cte_geomech.py` | **LOW** | Pure calculation functions |
| `automation/auto_extractor.py` | **MEDIUM** | Address normalization, many consumers |

## Approach: 6 fixes, grouped by dependency

---

### Fix 0: Vision re-run baseline (no code changes, biggest impact)

**Problem:** Current benchmarks run `--skip-vision`, skipping Claude/Groq PDF reading. This means `client`, `architect_name`, `building_type`, `num_floors` are not extracted from plànol A.01.pdf.

**Action:** Run `collect_readiness.py` WITHOUT `--skip-vision` for all 7 projects. Then re-run benchmark comparison to see how many Tier A variables fix themselves.

**Expected impact:** +10-15 MATCH from plànol vision extraction alone (client, architect, building_type, num_floors, superficie_construida).

**No code changes needed.** Just a pipeline re-run.

**Files to check after re-run:**
- `building_type`: Does plànol prompt extract "habitatge unifamiliar" or project title?
- `client`: Does plànol "A petició de:" provide the client?
- If building_type still wrong → Fix 1. If client still wrong → Fix 2.

---

### Fix 1: building_type extraction from plànol (prompt fix)

**Problem:** `wizard.py:257` sets `building_type = arch.get('building_type') or arch.get('project_name')`. When vision runs, Claude sometimes returns the project title ("ESTUDI GEOLOGIC...") in `building_type` instead of the classification ("habitatge unifamiliar").

**Current prompt** (`automation/validation/prompts.py:310-314`) already asks for building_type as "a SHORT descriptive classification of what is being built" with example "habitatge unifamiliar ailat". The issue is that Claude sometimes ignores this and fills project_name there.

**Fix in `automation/validation/prompts.py`:**
- Strengthen the building_type instruction: "Building type is NOT the project title. Examples: habitatge unifamiliar, habitatge unifamiliar ailat, nau industrial, ampliació, vivienda unifamiliar aislada"
- Add negative example: "Do NOT return the study title (e.g. ESTUDI GEOLOGIC...) as building_type"

**Also fix `automation/wizard.py:257`:**
- Remove the `or arch.get('project_name')` fallback — project_name should NEVER be building_type
- If vision doesn't extract building_type, leave it blank for Eva to fill

**Risk:** LOW — prompt changes only affect vision extraction, wizard fallback removal prevents wrong data.

**Expected impact:** 3-5 building_type MATCHes (from 0/7).

---

### Fix 2: client extraction — plànol "A petició de:" field

**Problem:** 5/7 projects show wrong client. Pipeline picks up "INTECSON" (G3's lab company) or abbreviations from FileMiner. Eva's plànol always has "A petició de: {CLIENT}" in the caixetí.

**Current state:**
- Plànol vision prompt example JSON includes `promotor: "Ramon Mitjana SL"` but does NOT ask Claude to extract it in the rules
- Content discovery picks up G3/INTECSON NIFs from documents (wrong company)

**Fix in `automation/validation/prompts.py`:**
- Add `client_name` field to plànol JSON output schema
- Add extraction rule: "Look for 'A petició de:', 'Client:', 'Promotor:', 'Propietari:' in the caixetí (title block)"

**Fix in `automation/wizard.py`:**
- When plànol vision returns `client_name` or `promotor`, set it as `client_name` prefill with high confidence
- Priority: plànol vision > FileMiner > content_discovery (plànol is most reliable)

**Risk:** LOW — adds a field to vision extraction, doesn't change existing logic.

**Expected impact:** 3-5 client MATCHes (from 1/7).

---

### Fix 3: street_address format normalization

**Problem:** 6/7 projects have street_address mismatches. Root causes:
- "C/ MESTRE RAMON ORTIZ 15" vs Eva's "entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz"
- Postal codes appended: "Carrer Arbrells, 18A, 08211 Castellar"
- Abbreviations: "C/" vs "Carrer", "STA." vs "Santa"

**P4 Steps 0-2 already fixed** the major issues (G3 address, email body, municipality suffix). Remaining is format normalization.

**Fix in `automation/auto_extractor.py` or new `_normalize_street_address()`:**
- Strip postal codes (5-digit trailing): already done
- Expand abbreviations: `C/` → `Carrer`, `Av.` → `Avinguda`, `Pl.` → `Plaça`, `STA.` → `Santa`
- Strip trailing municipality (already done)
- Remove letter suffixes from house numbers for display: "18A" → "18" (already done for API, do it for display too)

**Also fix in `scripts/compare_benchmarks.py`:**
- Add `street_address` normalizer to `TEXT_NORMALIZERS` that applies the same abbreviation expansion before comparison

**Risk:** LOW-MEDIUM — normalization is additive, but must not break Callejero lookup (that uses the raw address).

**Expected impact:** 2-3 more MATCHes or CLOSE (from 1/7).

---

### Fix 4: dpsh_avg_n20 + geotech_nb benchmark alignment

**Problem:** 4/5 dpsh_avg_n20 and 4/5 geotech_nb MISMATCH. Two separate issues:

**4a. Bearing stratum filter (ALREADY IMPLEMENTED):**
- `report_data.py:430` now calls `_bearing_stratum_n20()` instead of `overall_average_n20`
- `report_data.py:935-963` implements the depth filter
- Needs re-run to verify impact

**4b. Benchmark stores Eva's Nb, pipeline computes N20:**
- Eva's reports state "Nb mig" (average Nb). Benchmark stores this as `dpsh_avg_n20`.
- Pipeline computes `avg_n20` (not Nb). These differ by factor 0.83.
- The benchmark JSONs may need correction: rename to `dpsh_avg_nb` or convert.

**Fix in `scripts/compare_benchmarks.py`:**
- For `dpsh_avg_n20`: add a normalizer that accounts for the N20 vs Nb difference
- OR: fix the benchmark JSONs to store actual N20 values (N20 = Nb × 0.83)

**Fix in `docs/benchmarks/*-benchmark.json`:**
- Audit each project's `dpsh_avg_n20`: is it N20 or Nb? If Nb, convert to N20 for fair comparison.
- Same for `geotech_nb`: is the benchmark value Nb or N20?

**Risk:** LOW — benchmark data correction + comparison adjustment.

**Expected impact:** 3-4 MATCHes if bearing stratum + metric alignment both correct.

---

### Fix 5: geotech_cohesion + geotech_phi (multi-level + soil type)

**Problem:** 3/5 cohesion and 3/5 phi MISMATCH. Two linked root causes:

**5a. No intermediate cohesion values:**
- Pipeline: rock → c=1.0, else → c=0.0 (hardcoded in `report_generator.py:1295`)
- Eva: assigns c=0.05 for slightly cohesive soils (llims, arenes limoses)
- Need a soil_type → cohesion lookup (from Eva's Spt-correlacions.doc)

**5b. Wrong soil_type for Schmertmann phi:**
- Linyola: pipeline gives phi=36° (granular n=2.0), Eva says 28° (limo factor n=1.25)
- The pipeline auto-detects soil_type from sondeig layer description but may classify wrong

**5c. Multi-level: global geomech_params applied to all levels:**
- `report_generator.py:1277-1282`: single dict applied to every level
- Alcoletge: pipeline uses L1 params (fill, c=0) for L2 (lutites, c=1.0)

**Fix in `automation/cte_geomech.py`:**
- Add `soil_type_to_cohesion(soil_type: str) -> float` lookup:
  - "granular"/"grava"/"arena": 0.0
  - "arena_limosa"/"limo": 0.05
  - "arcilla": 0.10
  - rock: 1.0
- Improve `detect_soil_type(description: str) -> str` for better classification of Catalan descriptions

**Fix in `automation/report_generator.py`:**
- Line 1295: use `soil_type_to_cohesion()` instead of hardcoded 0.0
- Line 1277-1282: support per-level geomech_params (dict keyed by level index)

**Risk:** MEDIUM — touches geotechnical calculation chain. Must verify against all 7 projects.

**Expected impact:** 2-3 cohesion + 1-2 phi MATCHes. Also improves Tier C (Qa, settlement depend on correct c/phi).

---

## Execution order

```
Fix 1 (building_type prompt)        ✅ DONE — prompt strengthened, project_name fallback removed
Fix 2 (client plànol extraction)    ✅ DONE — client_name field added to prompt, wired in wizard
Fix 3 (street_address normalize)    ✅ DONE — abbreviation expansion + benchmark normalizer
Fix 4 (dpsh/nb benchmark align)     ✅ DONE — 7 benchmark JSONs converted Nb→N20
Fix 5 (cohesion + phi multi-level)  ✅ DONE — soil_type_to_cohesion(), first-word detect_soil_type()
         ↓
Fix 0 (vision re-run)              ← NEXT: measure all fixes with full pipeline
         ↓
     Re-run benchmark with --llm-judge → measure improvement
```

Fixes 1, 2, 3 are independent and can be done in parallel.
Fix 4 depends on Fix 0 results (need to see bearing stratum impact first).
Fix 5 is the most complex and should be last.

## Files to modify

| File | Fix | Changes |
|------|-----|---------|
| `automation/validation/prompts.py` | 1, 2 | Strengthen building_type, add client_name to plànol prompt |
| `automation/wizard.py` | 1, 2 | Remove project_name fallback, add client from plànol |
| `automation/auto_extractor.py` | 3 | Street address abbreviation expansion |
| `scripts/compare_benchmarks.py` | 3, 4 | street_address normalizer, dpsh_avg metric alignment |
| `docs/benchmarks/*-benchmark.json` | 4 | Audit N20 vs Nb values |
| `automation/cte_geomech.py` | 5 | soil_type_to_cohesion(), improve detect_soil_type() |
| `automation/report_generator.py` | 5 | Use cohesion lookup, per-level geomech_params |

## Verification

After each fix:
```bash
# Re-run pipeline (with or without vision depending on fix)
.venv/bin/python scripts/collect_readiness.py --output-dir docs/validation-latest
# OR with vision:
.venv/bin/python scripts/collect_readiness.py --output-dir docs/validation-latest

# Compare benchmarks
.venv/bin/python scripts/compare_benchmarks.py --llm-judge
```

**Target after all 6 fixes:**
- Tier A: 56.9% → 75-85% (from 58/102 to ~77-87/102)
- Overall: 37.9% → 50-55%

## Dependencies on vision re-run

| Fix | Needs vision? | Why |
|-----|--------------|-----|
| 0 | YES | That's the point — measure vision baseline |
| 1 | YES | building_type comes from plànol vision |
| 2 | YES | client comes from plànol vision |
| 3 | NO | Address normalization works on existing data |
| 4 | NO | Benchmark data + comparison logic |
| 5 | NO | Geotechnical calculations from DPSH/sondeig data |

Fixes 3, 4, 5 can proceed WITHOUT vision re-run.
Fixes 1, 2 need vision re-run to verify, but prompt changes can be made now and tested later.
