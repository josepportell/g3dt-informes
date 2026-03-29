# Plan: Tier B Remaining Improvements

Created: 2026-03-29
Status: Improvements 1, 5, 2 DONE. Improvements 3, 4 deferred.

## Context

Tier B measures 8 site-observation variables per project (55 total across 7 projects). After P4 Steps 0-2, we resolved the correct parcel for 6/7 projects via direct Callejero. But Tier B is still at 3.6% exact / 7.3% semantic because:

1. **Adjacents descriptions are too generic** — "parcel·la amb construcció" vs Eva's "parcel·la construïda amb piscina, amb herbes altes i arbres"
2. **location_sentence template doesn't match Eva's phrasing** — ours says "entre X i Y", Eva says "L'edificació que es preveu construir es situarà al Carrer X, 18 de Y"
3. **site_condition is a single word** ("antropitzat") — Eva writes "sense construccions ni pavimentacions, desbroçat"
4. **access_description uses wrong direction** or truncated text
5. **Benchmark comparison is too strict** — "Carrer dels Arbrells" vs "carrer Arbrells" = MISMATCH

## Risk assessment

| File | Risk | Why |
|------|------|-----|
| `scripts/compare_benchmarks.py` | **ZERO** | Standalone dev script, no production impact |
| `automation/site_text_generator.py` | **HIGH** | Core report text; Catalan grammar; no tests; called by auto_extractor |
| `web/wizard_service.py` | **VERY HIGH** | Critical merge point; enriched text integration; must respect user edits |
| `automation/auto_extractor.py` | **CRITICAL** | Orchestrates all phases; naming convention critical; silent failure handling |

**Key risk**: `site_text_generator.py` and `wizard_service.py` generate the same fields via different codepaths (ortho enrichment path vs fallback path). Improvements must specify which path to modify.

**No tests exist** for any of the text generation, merging, or benchmark comparison functions.

## Approach: 5 improvements, ordered by impact and risk

---

### Improvement 1: LLM-as-judge benchmark comparison (zero risk, unlocks measurement) -- DONE

**Problem:** `compare_benchmarks.py` uses substring matching only. "Carrer dels Arbrells" doesn't match "carrer Arbrells" because neither is a substring of the other. Word-overlap scoring would help but is a blunt tool for Tier B variables that are inherently "human judgment" text — synonyms, structural differences, and Catalan/Spanish variations defeat word counting.

**Fix:** For Tier B text variables, send each (benchmark, pipeline) pair to Claude for semantic comparison. Claude can judge:
- "parcel·la buida" ≈ "solar buit" (synonyms)
- "entre el Carrer Arbrells i el Carrer dels Arbrells" ≈ "al Carrer dels Arbrells, 18" (same location)
- "antropitzat" ≈ "sense construccions ni pavimentacions, desbroçat" (same site condition from different perspectives)

**Implementation in `scripts/compare_benchmarks.py`:**
- New function `compare_text_llm(variable_name, benchmark, pipeline) -> (score_1_5, status, explanation)`
- Prompt template: rate 1-5 with one-line explanation
- Map: 5→MATCH, 3-4→CLOSE, 1-2→MISMATCH
- Only for Tier B text variables; Tier A/C keep current comparison
- Fallback to current substring matching if API call fails
- Cache results to avoid re-scoring identical pairs

**Cost:** ~55 Tier B variables × ~200 tokens each = ~11K tokens per run. Negligible.

**Advantages over word-overlap:**
- No need to build/maintain article stripping, accent normalization, synonym lists
- Works for Catalan AND Spanish variables
- Handles structurally different but semantically equivalent descriptions
- Provides "why" explanations that guide which improvements to prioritize next

**Expected impact:** Several current MISMATCHes become CLOSE — and we get explanations for each, guiding future work.

---

### Improvement 5: Boilerplate sentences (low risk, easy win) -- DONE

**Problem:** Eva's access_description and site_description use fixed boilerplate that our pipeline doesn't include.

Eva's access_description always starts with:
- CAT: "El dia dels treballs de camp es realitza l'entrada a la zona d'estudi a través del {street} existent al {direction}."
- ES: "El día de los trabajos de campo se realiza la entrada a la zona de estudio a través del {path} situado en el {direction}."

Eva's site_description always ends with these two IDENTICAL sentences (across all 7 reports):
```
"En solars propers existeixen construccions de característiques similars a la obra projectada que el dia dels treballs de camp no presentaven patologies aparents a les seves parets exteriors visibles."
"Destacar que no es poden veure aflorar els materials que conformen el subsòl del solar ni en la parcel·la ni en zones properes."
```

**Fix — two parts:**

**5a. access_description boilerplate** — in `automation/site_text_generator.py` `_generate_access_description()`:
- Use Eva's exact prefix: "El dia dels treballs de camp es realitza l'entrada a la zona d'estudi a través"
- Verify the current implementation already uses this (it does, lines 222-243). Check for phrasing differences ("existent al" vs "situat al").

**5b. site_description boilerplate** — in `automation/site_text_generator.py` `_generate_site_description()`:
- Append Eva's two fixed sentences at the end of every site_description
- These are observational boilerplate (no nearby building pathologies, no subsoil visible) — safe to always include

**File ownership:** Only modify `site_text_generator.py` (the ortho enrichment path). Do NOT modify `wizard_service.py` fallback path — it generates inferior descriptions anyway, and enriched versions override it.

**Safety:** Current outputs only get longer (appended text). No existing text is removed or restructured.

**Expected impact:** access_description: 0/7 → ~3-5/7 CLOSE. site_description: 0/7 → ~3-5/7 CLOSE.

---

### Improvement 2: location_sentence template rewrite (medium risk) -- DONE

**Problem:** Current template in `site_text_generator.py:251-284`:
```
"L'edificació que es preveu construir es situarà {loc}, al municipi de {municipality}."
```

**Eva's patterns** (from 7 reports):
- Single-street: `"{Building_desc} es situarà al {Street} {nº} de {Municipality}."`
- Two-street corner: `"{Building_desc} es situarà entre el {Street1} i el {Street2} de {Municipality}."`
- Spanish variant: `"La nueva {building_type} proyectada se situará en {street} del municipio de {municipality}."`

**Key differences from current:**
1. Eva puts municipality at end with "de {Municipality}" not "al municipi de {Municipality}"
2. Eva includes building type: "habitatge unifamiliar", "ampliació", "edificació"
3. Eva uses street with number directly, not reconstructed from adjacents

**Fix in `automation/site_text_generator.py`** — `_generate_location_sentence()`:
- Change "al municipi de {municipality}" → "de {municipality}" (Eva's pattern)
- Use street_address directly (already does this)
- Keep the existing Catalan article handling (al/a l'/a la) — it works correctly
- Do NOT touch `wizard_service.py` fallback — it's overridden by enriched version anyway

**Risks to watch:**
- Catalan article logic (al/a l'/a la) is delicate and already works — minimal changes
- "entre X i Y" pattern exists in wizard_service.py fallback (line 225-261), NOT in site_text_generator. Plan originally conflated these two codepaths. Leave wizard_service alone.

**Safety net:** Run benchmark comparison before and after to verify no regressions on non-Tier-B fields.

**Expected impact:** Correct phrasing structure for 5/7 projects → several CLOSE matches.

---

### Improvement 4: site_condition from ortho vision (DEFERRED — medium-high risk)

**Status:** Deferred until after Improvements 1, 5, 2 are validated.

**Problem:** Currently outputs "antropitzat" (single word). Eva writes multi-part descriptions.

**Risk:** Currently `site_condition` is derived from boolean `is_anthropized` in `report_generator.py:878`. Changing from a single word to a structured multi-part string means modifying:
- `report_generator.py` — how it builds `context['site_condition']`
- The Jinja template — how it renders the field
- Potentially `wizard_service.py` — if site_condition is editable in wizard

Must verify that no conditional logic depends on "antropitzat" being a specific value.

**Approach when we resume:**
1. First: grep for all uses of `site_condition` and `is_anthropized` across codebase
2. Write snapshot tests for current outputs
3. Then implement structured generation

---

### Improvement 3: Adjacents description enrichment (DEFERRED — high risk)

**Status:** Deferred until after Improvements 1, 5, 2 are validated.

**Problem:** `_describe_neighbor()` generates generic descriptions from Cadastre data only. Ortho vision data (vegetation, surface, pools) exists but is NOT merged into adjacents descriptions.

**Risk:** This is the most interconnected change:
- Touches `auto_extractor.py` (CRITICAL risk file)
- The `_enriched` suffix convention must match `wizard_service.py` expectations exactly
- No tests exist for the enrichment pipeline
- Silent failure handling in Phase 3.5 could mask bugs

**Approach when we resume:**
1. First: write snapshot tests capturing current Phase 3.5 outputs for all 7 projects
2. Map the exact data flow: ortho_vision → site_text_generator → auto_extractor → wizard_service
3. Add enrichment as a new step AFTER existing `_generate_adjacent_text()`, not replacing it
4. Test with a single project before running all 7

---

## Execution order

```
Improvement 1 (LLM-as-judge)            ✅ DONE — Tier B: 4 MATCH, 13 CLOSE (was 2/2)
         ↓
Improvement 5 (boilerplate sentences)   ✅ DONE — Eva's 2 fixed sentences + access phrasing
         ↓
Improvement 2 (location_sentence)       ✅ DONE — "de {municipality}" + Catalan elision
         ↓
     *** PAUSED — need pipeline re-run with ortho to measure 5+2 impact ***
         ↓
Improvement 4 (site_condition)          ← DEFERRED: needs snapshot tests first
         ↓
Improvement 3 (adjacents enrichment)    ← DEFERRED: most complex, needs tests first
```

## Files to modify

| File | Improvement | Changes |
|------|-------------|---------|
| `scripts/compare_benchmarks.py` | 1 | LLM-as-judge for Tier B text variables |
| `automation/site_text_generator.py` | 5 | Append boilerplate sentences to site_description |
| `automation/site_text_generator.py` | 2 | location_sentence "de {municipality}" pattern |
| `automation/site_text_generator.py` | 4 (deferred) | Structured site_condition from ortho vision |
| `automation/auto_extractor.py` | 3 (deferred) | Wire ortho enrichment to adjacents descriptions |

**NOT modifying** (intentionally):
- `web/wizard_service.py` — fallback path is overridden by enriched versions; touching it adds risk for no benefit
- `automation/report_generator.py` — only for Improvement 4 (deferred)

## Verification

After each improvement:
```bash
# Run benchmark comparison (no cache clear needed for Improvement 1)
.venv/bin/python scripts/compare_benchmarks.py

# For Improvements 2, 5: regenerate prefills then compare
rm -f ~/.g3dt/cache/cadastre_adjacents/*.json ~/.g3dt/cache/ortho_enrichment/*.json
.venv/bin/python scripts/collect_readiness.py --skip-vision --output-dir docs/validation-latest
.venv/bin/python scripts/compare_benchmarks.py
```

**Target after Improvements 1, 5, 2:**
- Tier B: several MISMATCHes → CLOSE (with LLM-as-judge providing explanations)
- Better measurement of actual quality vs Eva's reports

**Target after all 5 (future):**
- Tier B exact: 2/55 → 6-10/55 (11-18%)
- Tier B CLOSE: 2/55 → 15-25/55 (27-45%)
- Overall: 36.8% → 40-44%

Note: `--skip-vision` means ortho enrichment (Improvement 3) won't fire — needs full run or `G3DT_ORTHO_ENRICHMENT=1` flag. Improvements 1, 2, 5 work without vision.
