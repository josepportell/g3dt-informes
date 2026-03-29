# P4 Next: Fix Address Extraction + Geocode Flow → Correct Parcel ID

Created: 2026-03-29
Updated: 2026-03-29
Status: Steps 0+1 DONE → Step 2 in progress

## The Problem

Tier B is stuck at 3.6% exact (2/55) because adjacents are wrong for 5/7 projects. The plan was "bypass geocode_project() and call Callejero directly" — but **the real root cause is upstream: the pipeline sends WRONG addresses to the geocoder**.

Even a perfect Callejero call will fail if the input is "administracion@g3dt.com" or "C/ Vallbona, 22" (G3's office).

## Three Failure Modes (from validation logs 2026-03-29)

### Mode 1: Wrong address inputs (3/7 projects) — HIGHEST IMPACT

| Project | Pipeline sends to geocoder | Eva's correct address |
|---------|--------------------------|----------------------|
| **Rubí** | `C/ Vallbona, 22` (G3's office!) | `carrer de la Miranda nº 39` |
| **Linyola** | `administracion@g3dt.com <mailto:...>` (email footer!) | `Carrer Clot de la Llacuna nº16` |
| **Bell-Lloc** | `C/ MESTRE RAMON ORTIZ 15 BELL-LLOC` (city in address) | `entre el C/ Antoni Bellet i el C/ Mestre Ramon Ortiz` |

Root causes:
- **Rubí**: `groq_miner.py` has `_G3_EXCLUSIONS` for "VALLBONA, 22" but the exclusion doesn't fire in all code paths. The field_prep/pressupost extraction picks up G3's address instead of the project site.
- **Linyola**: `msg_miner.py` runs `run_all_detectors()` on email body+footer. The email signature text gets misclassified as a street address.
- **Bell-Lloc**: Planol vision extraction includes "BELL-LLOC" in the address string. `user_data.json` has `"C/ MESTRE RAMON ORTIZ 15 BELL-LLOC"` — the municipality is embedded.

### Mode 2: Municipality matching fails (3/7 projects)

| Project | Log error | Root cause |
|---------|-----------|------------|
| **Castellar** | `'Castellar del Vallès' not found in Barcelona or neighbors` | Accent `è` not stripped in `_consulta_municipio()` |
| **Vilanova** | `'Vilanova de Segrià' not found in Lleida or neighbors` | Accent `à` not stripped |
| **Anciles** | `'Anciles' not found in Huesca or neighbors` | Anciles is a village; municipality is Benasque |

Despite commit `5da1237` (strip accents in Callejero), the accent stripping doesn't propagate to `cadastre_progressive_lookup()` → `_consulta_municipio()`.

### Mode 3: Street name variants (1/7 projects)

| Project | Issue |
|---------|-------|
| **Alcoletge** | Cadastre has `Gira-sols` (hyphenated), input is `Girasols` |

## Verification Table: Expected vs Actual

| Project | Eva's address | Expected RC | After Steps 0+1 |
|---------|-------------|-------------|-----------------|
| Castellar | Arbrells 18 | 3298012DG1039S | Municipality OK, error 42 (number) — Step 2 will fix |
| Rubí | Miranda 39 | TBD | G3 filter works, correct address reaches geocoder |
| Linyola | Clot Llacuna 16 | TBD | Email blocked, correct address reaches geocoder |
| Bell-Lloc | M. Ramon Ortiz 15 | 4613172YG1041S | OK (from COORDENADES.txt) |
| Alcoletge | Girasols 7 | TBD | G3 filter works, street variant remains |
| Vilanova | Sta Gemma 4 | TBD | G3 filter + accent fix, W≈Eva's semantically |
| Anciles | Gral Ferraz 20 | 5684607BH9158N | Village mapping added, DNS failure (untested) |

## Implementation Plan

### Step 0: Fix address extraction inputs — DONE (commit 448ed19)

**0a. Email body address block** — DONE
- `msg_miner.py`: address signals from email body/subject are now filtered out
- Linyola: no longer geocodes "administracion@g3dt.com..."

**0b. G3 internal address filter** — DONE
- `auto_extractor.py`: `_is_g3_internal_address()` requires both street+number match
- Applied at: FileMiner resolution, _phase25_geocode, _phase3_adjacents, geocode-first
- Confirmed working: Rubí, Alcoletge, Vilanova all reject "C/ Vallbona, 22"

**0c. Municipality stripping** — DONE
- `auto_extractor.py`: `_clean_street_address()` strips trailing municipality name
- Uses NFC normalization for safe index-based slicing

### Step 1: Fix municipality matching — DONE (commit 448ed19)

**1a. Accent stripping in ConsultaMunicipio URL** — DONE
- `geocode_coordinates.py`: `_consulta_municipio()` now strips accents from both province and municipality_hint before building the API URL
- Castellar: municipality now resolved (error 42 = house number, not municipality)
- Vilanova: municipality now resolved

**1b. Village→municipality mapping** — DONE
- `geocode_coordinates.py`: `_VILLAGE_TO_MUNICIPALITY` dict with Anciles→Benasque + 3 others
- Fallback chain: primary province → border provinces → village mapping → fail
- Untested due to DNS resolution failure during validation run

### Step 2: Direct Callejero path in _geocode_for_adjacents — IN PROGRESS

After Step 0+1, addresses are correct but `geocode_project()` still goes through a complex
fallback chain (progressive cadastre → direct cadastre → Nominatim → grid search). The
fallback chain can land on a neighbor parcel. Direct Callejero gives the exact RC.

**2a. New function: `callejero_address_to_rc(street_address, municipality, province)`**
Location: `automation/geocode_coordinates.py` (public, reusable)
- Use existing `_parse_address()` to get (sigla, calle, numero)
- Use existing `cadastre_progressive_lookup()` which already does fuzzy muni + street + DNPLOC
- But wrap it cleanly: address in → RC + polygon out
- Key: `cadastre_progressive_lookup()` already handles error 42 (nearest number fallback),
  error 41 (empty number retry), and fuzzy street matching via Groq. So the function is
  really a thin wrapper that provides the "address → RC + geometry" contract.

**2b. Integrate into `_geocode_for_adjacents()`**
In `auto_extractor.py`, `_geocode_for_adjacents()` currently loops through address candidates
and calls `geocode_project()` for each. Change to:
```python
# Try direct Callejero FIRST (exact RC from address database)
from .geocode_coordinates import callejero_address_to_rc, get_parcel_geometry_utm
result = callejero_address_to_rc(street_address, municipality, province)
if result and result.get('rc'):
    rc = result['rc']
    polygon = get_parcel_geometry_utm(rc[:14])
    # Return UTM centroid from polygon (more precise than DNPLOC xcen/ycen)
    ...
else:
    # Fall back to geocode_project() existing chain
    ...
```

**2c. Why still necessary after Step 0+1**
- Castellar: municipality resolved but error 42 (house number "18A" → "18" needed?)
  Direct Callejero with progressive_lookup handles error 42 by trying nearest number.
- Rubí: correct address but geocode_project → Nominatim → imprecise coords
- The existing `cadastre_progressive_lookup()` already has all the fuzzy matching we need.
  The gap is that `_geocode_for_adjacents()` calls `geocode_project()` which tries multiple
  fallback paths before reaching `cadastre_progressive_lookup()`.

**Files to modify:**
- `automation/geocode_coordinates.py` — new `callejero_address_to_rc()` wrapper
- `automation/auto_extractor.py` — `_geocode_for_adjacents()` tries Callejero first

### Step 3: Polygon override for merged parcels

Bell-Lloc works but P4b sequencing broke adjacents when merging:
- Bell-Lloc geocode → parcel 4613172 (500 m²)
- P4b merges 4613172 + 4613173 → merged polygon (1012 m²)
- Merged polygon has different centroid → adjacents probe from wrong position
- `_phase3_adjacents()` re-geocodes internally → may get different parcel

**Fix:** When parcel_resolver produces a merged polygon, pass it directly to `get_adjacent_parcels()` as `polygon_override`, bypassing the internal parcel lookup.

**Files to modify:**
- `automation/cadastre_adjacents.py` — `get_adjacent_parcels()` accept optional polygon
- `automation/auto_extractor.py` — pass merged polygon through

### Step 4: Validate per-project with expected RCs

After each step, run:
```bash
# Clear stale caches (selective, not all)
rm -f ~/.g3dt/cache/geocode/*.json
rm -f ~/.g3dt/cache/cadastre_adjacents/*.json

# Re-run pipeline
G3DT_ORTHO_ENRICHMENT=1 .venv/bin/python scripts/collect_readiness.py --skip-vision --output-dir docs/validation-latest

# Compare
.venv/bin/python scripts/compare_benchmarks.py
```

Check per-project:
1. Correct address reaches geocoder (from logs)
2. Correct RC returned (from validation JSON)
3. Adjacents directions match Eva's (N/S/E/W)

## Targets (phased)

**Phase 1 — Correct parcel RC** (Steps 0-2):
- Target: 6/7 projects get correct RC (Anciles may remain edge case)
- Metric: RC in validation JSON matches expected RC table above

**Phase 2 — Correct adjacents directions** (Step 3 + existing adjacents logic):
- Target: 4/4 adjacents correct for 4/7 projects
- Metric: adjacents in `_comparison.json` show MATCH for direction/street

**Phase 3 — Enriched adjacents descriptions** (future, not in this plan):
- Currently: "parcel·la amb construcció"
- Eva writes: "parcel·la construïda amb piscina", "parcel·les sense construir, amb herbes altes i arbres"
- This requires better ortho enrichment quality — separate work item

## Tier B scope reminder

Tier B has **8 variables per project** (56 total), not just adjacents:

| Variable | Current | Blocked by parcel? | Fix path |
|----------|---------|-------------------|----------|
| `location_sentence` | 0/7 match | Yes (wrong street names) | Fix address → auto-generates |
| `adjacent_N/S/E/W` | 2/28 match | Yes (wrong parcel) | Steps 0-3 |
| `site_condition` | 0/7 match | No (always "antropitzat") | Ortho enrichment quality |
| `site_description` | 0/7 match | No (template-driven) | Ortho enrichment quality |
| `access_description` | ~3/7 close | Partially | Minor template tweaks |

Steps 0-3 unblock **location_sentence + adjacents = 5 vars × 7 = 35 vars** (63% of Tier B).
The remaining `site_condition` + `site_description` (2 vars × 7 = 14 vars) need ortho enrichment improvements — separate plan.

## What NOT to change

- ICGC geology/elevation/slope still use DPSH coords (regional data, correct)
- Don't change the adjacents probe logic (edge classification, Nominatim streets — these work once on the right parcel)
- Don't change the ortho enrichment pipeline in THIS plan
- Don't touch the Jinja template or report_generator for Tier B

## Project test matrix (updated after Steps 0+1)

| Project | After Steps 0+1 | Remaining blocker | Next step |
|---------|----------------|-------------------|-----------|
| Bell-Lloc | OK (COORDENADES.txt) | Merged polygon adjacents drift | Step 3 |
| Castellar | Muni OK, error 42 | Number not found in Callejero | Step 2 (nearest number fallback) |
| Rubí | Correct address flows | geocode_project → Nominatim imprecision | Step 2 (direct Callejero) |
| Linyola | Correct address flows | geocode_project → Nominatim imprecision | Step 2 (direct Callejero) |
| Alcoletge | G3 filter OK | Street variant (Gira-sols) | Step 2 (fuzzy street in progressive) |
| Vilanova | Muni + G3 OK | W≈Eva semantically, directions TBD | Step 2 (exact RC) |
| Anciles | Village mapping added | DNS failure (untested) | Step 2 (retest) |

## Execution order

```
Step 0 (address extraction fixes)   ✅ DONE (commit 448ed19)
Step 1 (municipality matching)      ✅ DONE (commit 448ed19)
         ↓
Step 2 (direct Callejero path)      ← IN PROGRESS
         ↓
Step 3 (polygon override)
         ↓
Step 4 (validate all 7 projects)
```
