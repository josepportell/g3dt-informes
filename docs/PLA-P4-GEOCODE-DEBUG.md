# P4 Next: Fix Address Extraction + Geocode Flow → Correct Parcel ID

Created: 2026-03-29
Updated: 2026-03-29
Status: Ready to start

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

| Project | Eva's address | Expected RC | Pipeline status |
|---------|-------------|-------------|-----------------|
| Castellar | Arbrells 18 | 3298012DG1039S | FAIL: municipality accent |
| Rubí | Miranda 39 | TBD (verify) | FAIL: wrong address (Vallbona) |
| Linyola | Clot Llacuna 16 | TBD (verify) | FAIL: garbage address (email) |
| Bell-Lloc | M. Ramon Ortiz 15 | 4613172YG1041S | OK (from COORDENADES.txt) |
| Alcoletge | Girasols 7 | TBD (verify) | PARTIAL: street variant |
| Vilanova | Sta Gemma 4 | TBD (verify) | FAIL: municipality accent |
| Anciles | Gral Ferraz 20 | 5684607BH9158N | PARTIAL: wrong municipality |

## Implementation Plan

### Step 0: Fix address extraction inputs

This is the highest-impact fix. 3/7 projects have completely wrong addresses reaching the geocoder.

**0a. Block email body/footer as address source**
- In `fileminer/miners/msg_miner.py`: do NOT run address detectors on email body text. Email bodies are for extracting project metadata (dates, names), not street addresses.
- Only extract addresses from msg ATTACHMENTS (PDFs, Excel), not the email text itself.

**0b. Strengthen G3 address exclusion**
- The `_G3_EXCLUSIONS` list in `groq_miner.py` only filters groq results. But other code paths (field_prep Excel, pressupost PDF) can still extract G3's own address.
- Add a centralized `is_g3_internal_address()` check that runs on ALL extracted `street_address` / `site_address` values before they enter prefills.
- Pattern: any address containing "Vallbona" + "22" + "Rubí" → reject.

**0c. Strip municipality/postal from planol-extracted addresses**
- Vision prompt already says "WITHOUT postal code or municipality" but extraction still includes it (Bell-Lloc: "MESTRE RAMON ORTIZ 15 BELL-LLOC").
- Add post-processing: strip known municipality name from the end of extracted `street_address`.
- Logic: if address ends with municipality name (fuzzy match), remove it.

**0d. Address source priority chain**
Formalize in `auto_extractor.py`:
```
1. COORDENADES.txt metadata (field-measured, highest trust)
2. planol_extracted.json → street_address (vision, cleaned)
3. field_prep Excel → ADREÇA OBRA (if not G3 internal)
4. NEVER: email body, email footer, email signature
```

**Files to modify:**
- `automation/fileminer/miners/msg_miner.py` — block address from email body
- `automation/auto_extractor.py` — centralized G3 filter + priority chain
- `automation/vision_extractor.py` or post-processing — strip municipality from address

### Step 1: Fix municipality matching

**1a. Verify accent stripping in `_consulta_municipio()`**
- Commit `5da1237` fixed Callejero calls but progressive_lookup may use a different path.
- Trace: `cadastre_progressive_lookup()` → `_consulta_municipio(province, municipality_hint)` — does it strip accents from `municipality_hint` BEFORE the API call?
- Fix: add `unicodedata.normalize('NFD', ...).encode('ascii', 'ignore').decode()` at the entry of `_consulta_municipio()`.

**1b. Add village→municipality mapping for Aragón**
- Anciles is a village within the municipality of Benasque (Huesca).
- The Cadastre API needs "Benasque", not "Anciles".
- Options:
  - Small lookup table for known villages (simplest, but doesn't scale)
  - If `_consulta_municipio(province, "Anciles")` fails, try Nominatim to resolve the municipality name, then retry Cadastre with the resolved name
  - This is an edge case (only 1 project). If a table with 5 entries solves it, do that.

**Files to modify:**
- `automation/geocode_coordinates.py` — `_consulta_municipio()` accent stripping
- `automation/geocode_coordinates.py` — village→municipality fallback

### Step 2: Direct Callejero path in parcel_resolver

Once address inputs are correct, add a direct Callejero lookup that bypasses the complex `geocode_project()` fallback chain.

**2a. New function: `_callejero_address_to_rc(street_address, municipality, province)`**
- Parse address → (street_type, street_name, number) using `_parse_address()`
- Strip accents from municipality
- Call `ConsultaNumero` directly: `Consulta_DNPLOC(Provincia, Municipio, TipoVia, NombreVia, Numero)`
- Return RC (14 chars) or None

**2b. Integrate into parcel resolution flow**
In `parcel_resolver.py` or `auto_extractor.py`:
```python
# Try direct Callejero FIRST (fast, precise)
rc = _callejero_address_to_rc(address, municipality, province)
if rc:
    polygon = get_parcel_geometry_utm(rc)
    # proceed with adjacents
else:
    # Fall back to geocode_project() existing chain
    ...
```

**2c. Why this is still necessary even after Step 0**
Even with correct addresses, `geocode_project()` can return a neighbor parcel because:
- Nominatim returns ~50-200m imprecise coords
- Grid search may land on adjacent parcel
- Direct Callejero gives EXACT cadastral reference from the official address database

**Files to modify:**
- `automation/geocode_coordinates.py` — new `_callejero_address_to_rc()`
- `automation/parcel_resolver.py` or `auto_extractor.py` — integration

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

## Project test matrix (updated)

| Project | Blocker | Step that fixes it |
|---------|---------|-------------------|
| Bell-Lloc | Working! Regression test | Step 3 (polygon override for merged) |
| Castellar | Municipality accent | Step 1a |
| Rubí | Wrong address (G3 office) | Step 0b |
| Linyola | Garbage address (email) | Step 0a |
| Alcoletge | Street variant (Gira-sols) | Step 2 (fuzzy street in Callejero) |
| Vilanova | Municipality accent | Step 1a |
| Anciles | Village ≠ municipality | Step 1b |

## Execution order

```
Step 0a (msg_miner email block)  ─┐
Step 0b (G3 address filter)      ─┼─ Can be done in parallel
Step 0c (strip municipality)     ─┘
         ↓
Step 1a (accent in _consulta_municipio)  ─┐
Step 1b (village→municipality mapping)    ─┘ Parallel
         ↓
Step 2 (direct Callejero path)
         ↓
Step 3 (polygon override)
         ↓
Step 4 (validate all 7 projects)
```

Estimated: Steps 0+1 fix 6/7 projects. Step 2 makes it robust. Step 3 fixes Bell-Lloc regression.
