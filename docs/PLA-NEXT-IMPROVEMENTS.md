# Plan: Next Improvements (Post-Tier A/B Fixes)

Created: 2026-03-29
Status: Item 1 DONE, ready for Item 2

## Context

After Tier A Fixes 1-5 and Tier B Improvements 1/5/2, current metrics:
- Overall: 62 MATCH + 31 CLOSE / 168 vars (36.9% exact, 55.4% exact+CLOSE)
- Tier A: 56/101 (55.4%) — will improve after re-run with Taula 9 fix
- Tier B: 4/47 exact, 17/47 CLOSE (LLM-as-judge)
- Tier C: 2/20 (10.0%)

## Items in priority order

---

### Item 1: Taula 9 deepest-level display fix -- DONE

**Problem:** `report_generator.py:1316-1324` used `geotech_rows[0]` for display vars. For multi-level projects (Castellar: 2 levels), this showed level 1 (shallow soil) instead of level 2 (rock = bearing stratum).

**Fix:** Changed `[0]` to `[-1]` in 4 places. Now uses deepest level (bearing stratum) for:
- Terzaghi soil_type selection
- dpsh_avg_n20 display
- geotech backward-compat display vars (density, cohesion, phi, E)
- Calc transparency reference

**Verified:** Castellar now shows rock params (density=2.20, cohesion=1.00, phi=35, E=500).

**Expected impact on re-run:** Castellar recovers ~4 MATCHes (density, cohesion close, phi close, settlement close).

---

### Item 2: Full pipeline re-run (measure all fixes)

**Action:** Re-run `collect_readiness.py` (without `--skip-vision`) for all 7 projects, then `compare_benchmarks.py --llm-judge`.

**What it measures:**
- Taula 9 fix (Item 1) — Castellar recovery
- Tier B Improvements 5+2 (boilerplate + location_sentence) — site_description/location_sentence
- Tier A Fix 5 (cohesion soil_type) — Linyola, Rubí cohesion
- street_address abbreviation expansion — minor gains
- All vision-dependent fixes (building_type prompt, client prompt)

**Command:**
```bash
rm -f ~/.g3dt/cache/cadastre_adjacents/*.json ~/.g3dt/cache/ortho_enrichment/*.json
G3DT_ORTHO_ENRICHMENT=1 .venv/bin/python scripts/collect_readiness.py --output-dir docs/validation-latest
.venv/bin/python scripts/compare_benchmarks.py --llm-judge
```

**Expected target:** Tier A 55% → 65-70%, Overall 37% → 45-50%.

---

### Item 3: Image management — photo picker popup

**Problem:** Eva has no way to choose which photos go in the report. The pipeline auto-selects via AI (Phase 7) or filename patterns. If the wrong photo is placed, Eva must edit the .docx manually.

**Current image flow:**
```
FOTOGRAFIES/          ← Eva's field photos (unstructured)
    ↓
SmartScan roles       ← Phase 6: file_mapping.json assigns photo roles
    ↓
AI photo curator      ← Phase 7: Claude/Groq sees thumbnail grid, picks best
    ↓ (cached in validation/photo_selection.json)
image_manager.py      ← Builds InlineImage objects for docxtpl
    ↓
report_generator.py   ← Inserts into .docx template
```

**Image slots in report:**
| Slot | Description | Display |
|------|-------------|---------|
| `photo_site_1` + `photo_site_2` | Site overview | Side-by-side, 70mm each |
| `photo_dpsh` | DPSH equipment | 120mm single |
| `photo_sondeig` | Sondeig/borehole | 120mm single (conditional) |
| `photo_materials` | Soil samples | 120mm single |

**Figure slots (auto-generated, less need for picker):**
| Slot | Source | Generation |
|------|--------|------------|
| `fig_cadastre` | Situation plan PDF, left 38% crop | Auto |
| `fig_aerea` | ICGC orthophoto + parcel overlay | Auto |
| `fig_main_plan` | A.01.pdf render | Auto |
| `fig_geological` | ICGC geology map download | Auto |
| `fig_correlation` | tall.pdf render | Auto |
| `fig_spt_cullera` | Static template image | Fixed |

**Proposed UX — Photo picker in wizard:**

Add a "Fotografies" tab (or section within wizard tab) showing:
```
┌──────────────────────────────────────────────────┐
│  Fotografies del camp                             │
│                                                   │
│  Vista general (2 fotos):                         │
│  [thumb1] [thumb2] [thumb3] [thumb4] [thumb5]    │
│   ●         ●                                     │
│  Selected: thumb1 + thumb2                        │
│                                                   │
│  DPSH:                                           │
│  [thumb6] [thumb7] [thumb8]                      │
│   ●                                               │
│  Selected: thumb6                                │
│                                                   │
│  Sondeig:                                        │
│  [thumb9] [thumb10]                              │
│   ●                                               │
│  Selected: thumb9                                │
│                                                   │
│  Materials:                                      │
│  [thumb11] [thumb12]                             │
│   ●                                               │
│  Selected: thumb11                               │
│                                                   │
│  [Restablir selecció IA]                          │
└──────────────────────────────────────────────────┘
```

**Implementation:**

**Backend (3 new endpoints in `web/api.py`):**
1. `GET /api/photos/{project}` — List all photos in FOTOGRAFIES/ with thumbnails. Returns: `[{path, thumbnail_url, slot_suggestion, selected}]`
2. `POST /api/photos/{project}/select` — Save user photo selection. Body: `{site_1: "path", site_2: "path", dpsh: "path", ...}`. Writes to `validation/photo_selection.json` (same format Phase 7 uses).
3. `POST /api/photos/{project}/reset` — Delete photo_selection.json, re-run AI selection.

**Frontend (in review.html wizard tab):**
- Photo grid with clickable thumbnails per slot
- Pre-selected from Phase 7 AI picks (or user's previous selection)
- Click to change selection — highlights with border
- "Restablir selecció IA" button to reset

**Integration with image_manager.py:**
- Add `_load_user_photo_selection()` check BEFORE `select_photos_ai()`
- User selection priority: user_saved > AI_cached > pattern_matching
- Same `photo_selection.json` format — AI and user are interchangeable

**Risk:** MEDIUM — touches frontend + backend + image_manager integration.
**Effort:** ~2-3 hours. Backend is straightforward (3 endpoints + JSON save). Frontend is the main work (thumbnail grid, click handling).

**Files to modify:**
| File | Changes |
|------|---------|
| `web/api.py` | 3 new endpoints (photos list, select, reset) |
| `automation/image_manager.py` | Load user selection before AI selection |
| `templates/validation/review.html` | Photo picker UI in wizard tab |

---

### Item 4: Tier C transparency improvements

**Problem:** Tier C variables (E, Qa, settlement, K30) are professional judgment — Eva adjusts them. The goal is NOT convergence but transparency: show Eva what the formula produces and let her override.

**Current state:** Formula explanations already exist in wizard expert overrides panel (`_calc_gamma`, `_calc_phi`, `_calc_E`, `_calc_qa`, etc.). But they're text-only — no visual comparison.

**Proposed improvements:**

**4a. Eva's typical ranges as reference:**
In the expert overrides panel, show Eva's typical value ranges next to the formula result:
```
E calculat = 469 (CTE D.23, N20=38)
Rang típic Eva: 450-650 (graves carbonatades)
[___469___]  ← editable field
```

Source: Eva's reference table from MEMORY.md:
| Material | gamma | c | phi | E | Qa cap |
|----------|-------|---|-----|---|--------|
| Graves/sorres | 2.0 | 0.0-0.05 | 38-39 | 450-650 | 3.0 |
| Llims argilosos | 1.90 | 0.05 | 28 | 100 | 3.0 |
| Roca | 2.20 | 1.0 | 30-35 | >500-800 | 4.0-4.5 |

**4b. Qa breakdown in wizard:**
Show the Terzaghi-Peck calculation steps:
```
Qa = Nb/12 × Fw × Fd = 38/12 × 0.92 × 1.05 = 3.06
Cap aplicat: 3.0 (sòl granular)
Eva pot ajustar: [___3.0___]
```

**4c. Settlement sensitivity:**
Show how Es affects settlement:
```
Assentament = 1.12 cm (Schmertmann, Es=95, B=1.0m)
Si Es=125: 0.85 cm  |  Si Es=75: 1.42 cm
```

**Risk:** LOW — purely additive UI changes in wizard panel.
**Effort:** ~1 hour. All data already computed; just formatting for display.

**Files to modify:**
| File | Changes |
|------|---------|
| `automation/report_generator.py` | Add Eva's typical ranges to `_calc_*` notes |
| `templates/validation/review.html` | Display ranges in expert panel |

---

### Item 5: building_type remaining failures (investigation)

**Current state:** 3 CLOSE, 4 MISMATCH across 7 projects.

| Project | Value | Source | Issue |
|---------|-------|--------|-------|
| Castellar | "CONSTR 3 HAB UNIF" | FileMiner (pressupost) | No plànol → FileMiner fallback |
| Rubí | "Habitatge aïllat" | planol vision | Missing "unifamiliar" — acceptable |
| Linyola | "habitatge unifamiliar aïllat" | planol vision | CLOSE — adds "aïllat" |
| Bell-Lloc | "Habitatge aïllat" | user_data | Missing "unifamiliar" — acceptable |
| Alcoletge | "PROJECTE DE TANCAMENT..." | user_data (Eva manual) | Eva entered project title |
| Vilanova | "vivienda unifamiliar" | planol vision | CLOSE — missing "aislada" |
| Anciles | "viviendas adosadas" | planol vision | CLOSE — missing "unifamiliares" |

**Analysis:**
- 3 projects work fine (Linyola, Vilanova, Anciles — CLOSE or acceptable)
- Rubí/Bell-Lloc: "Habitatge aïllat" is acceptable (user agreed)
- Castellar: no plànol available, can't fix
- Alcoletge: Eva's own input, not a pipeline issue

**Verdict:** Low priority. Most failures are data gaps or acceptable approximations. No code fix needed.

---

## Execution order

```
Item 1 (Taula 9 fix)               ✅ DONE — committed
         ↓
Item 2 (pipeline re-run)           ← NEXT: measure all fixes
         ↓
Item 3 (photo picker)              ← Main new feature: Eva UX improvement
         ↓
Item 4 (Tier C transparency)       ← Additive UI: Eva's typical ranges
         ↓
Item 5 (building_type)             ← Low priority: mostly acceptable
```

Items 3 and 4 are independent and could be parallelized.
Item 5 is informational — no action unless new plànols appear.

## Success metrics

| Item | Metric | Target |
|------|--------|--------|
| 1 | Castellar geotech match | +3-4 MATCH |
| 2 | Overall correctness | 45-50% (from 37%) |
| 3 | Eva time per photo selection | < 10 seconds (vs manual .docx edit) |
| 4 | Eva confidence in overrides | Qualitative (sees formula + typical range) |
| 5 | building_type match rate | 3/7 CLOSE is acceptable |
