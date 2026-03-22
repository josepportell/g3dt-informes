# Plan: G3DT Post-Anciles Fixes

## Context

Testing with the Anciles project (4001679, Huesca/Aragón) revealed that the system was built with Catalunya-only assumptions. Groq vision and FileMiner work well but several data paths break for non-Catalunya projects, and variable name mismatches prevent extracted data from reaching the wizard. These 6 fixes address the issues found.

## Implementation Order: 5 → 4 → 1 → 3 → 2 → 6

---

### Change 1: Fix Variable Name Mapping (Groq → Wizard)

**Problem:** Groq extracts `superficie_parcela` and `superficie_construida`, but wizard expects `superficie_parcela_m2` and `superficie_construida_m2`. Also, `has_basement="true"` from Groq is overwritten by wizard default `has_basement=False` (source: `default estandard`).

**Root cause (has_basement):** `wizard_service.py:255-256` — wizard prefills overwrite auto_extract prefills unconditionally. Wizard defaults (line 153 of `wizard.py`) kill Groq values.

**Files to modify:**

1. **`automation/auto_extractor.py`** (lines 344-350)
   - Add `_GROQ_KEY_REMAP` dict to translate keys at merge time:
     ```
     superficie_parcela → superficie_parcela_m2
     superficie_construida → superficie_construida_m2
     ```
   - Convert boolean string fields (`has_basement`, `has_retaining_walls`) to Python `bool`

2. **`web/wizard_service.py`** (lines 255-256)
   - In the wizard merge loop, skip entries with source `'default estandard'` when auto_extract already has a value for that key:
     ```python
     for key, entry in wizard.prefills.items():
         source = entry.get('source', '') if isinstance(entry, dict) else ''
         if source == 'default estandard' and key in merged:
             continue  # don't overwrite real data with defaults
         merged[key] = entry
     ```

**Verification:** Run Anciles extraction → wizard shows `superficie_parcela_m2=1655.01`, `superficie_construida_m2=1273.79`, `has_basement=Sí`.

---

### Change 2: Fix Geocoding for Non-Catalunya Projects

**Problem:** Three hardcoded Catalunya restrictions:
- `_CATALAN_PROVINCES` fallback (line 266) — cadastre only tries 4 provinces
- `nominatim_geocode()` hardcodes `"Catalunya, Spain"` (line 499)
- UTM bounds check rejects non-Catalunya coords (lines 47-51)
- `_wgs84_to_utm31n()` always uses zone 31 — Huesca is zone 30
- ICGC elevation service is Catalunya-only

**Files to modify:**

1. **`automation/geocode_coordinates.py`**
   - Add `province` param to `geocode_project()` (line 905) and pass through to `cadastre_address_lookup()` (line 948)
   - Fix `nominatim_geocode()` (line 499): `region = province or "Spain"`, query = `f"{address}, {municipality}, {region}, Spain"`
   - Add `_wgs84_to_utm()` that auto-detects zone 30/31 based on longitude (lon >= 0 → zone 31, else zone 30)
   - Widen bounds validation to Spanish peninsular range, or use province to select bounds
   - Wrap ICGC elevation calls in try/except — gracefully skip for non-Catalunya (log warning, leave elevation empty for Eva to fill)

2. **`automation/auto_extractor.py`** (`_phase25_geocode()`, ~line 728)
   - Pass `province=result.prefills.get('province', '')` to `geocode_project()`

3. **`web/api.py`** (geocode endpoint)
   - Pass province from prefills to the geocode call

**Verification:** Anciles geocoding returns valid coordinates. Cadastre finds the parcel in Huesca. Nominatim query doesn't include "Catalunya". No crash from ICGC for out-of-region coordinates.

---

### Change 3: Add Cache Bypass Flag

**Problem:** 4 cache layers (Groq, geocode, vision JSON, in-memory prefills) obscure test results.

**Solution:** Single env var `G3DT_NO_CACHE=1` bypasses all caches.

**Files to modify:**

1. **`automation/fileminer/miners/groq_miner.py`** (`_load_cache()`, line 534)
   - Return `None` immediately if `G3DT_NO_CACHE=1`

2. **`automation/geocode_coordinates.py`** (`_load_from_cache()`, line 849)
   - Return `None` immediately if `G3DT_NO_CACHE=1`

3. **`web/wizard_service.py`** (`get_prefills()`, line 229)
   - Skip in-memory cache check if `G3DT_NO_CACHE=1`

4. **Vision Groq** (`web/vision_groq.py` — check for file-based cache)
   - Skip `*_extracted.json` existence check if `G3DT_NO_CACHE=1`

**Verification:** `G3DT_NO_CACHE=1 .venv/bin/python -m web` → load Anciles → logs show all "cache MISS", no "cache HIT". Groq API is called fresh.

---

### Change 4: Add .doc (Legacy Word) Support

**Problem:** `python-docx` only handles `.docx`. Legacy `.doc` files fail silently with "Package not found".

**Solution:** Try `python-docx` first; on failure for `.doc` files, fallback to `antiword` CLI, then `libreoffice --headless`.

**Files to modify:**

1. **`automation/fileminer/miners/docx_miner.py`** (`_extract_docx_text()`, line 84)
   - Add `_extract_doc_legacy()` static method: tries `antiword`, then `libreoffice --headless --convert-to txt`
   - On `python-docx` failure for `.doc` extension, call `_extract_doc_legacy()`

2. **`automation/fileminer/miners/groq_miner.py`** (`_extract_docx_text()`, line 318)
   - Same fallback: import and call `DocxMiner._extract_doc_legacy()` for `.doc` files

**Prerequisite:** `sudo apt install antiword` on Eva's machine (and dev machines).

**Verification:** `4001679_informe_V0.doc` produces text output. Groq receives content from `.doc` files (no more "text extraction failed" warnings).

---

### Change 5: Exclude Reference Reports from FileMiner

**Problem:** Root-level files like `*_informe_V0.doc` and `*_portada_V0.doc` are Eva's reference reports (for comparison only, won't exist in new projects). They contaminate extraction. Also, `_SKIP_DIRS` has `PDF-V0` (hyphen) but Anciles uses `PDF_V0` (underscore).

**Files to modify:**

1. **`automation/fileminer/__init__.py`**
   - Add `'PDF_V0'` to `_SKIP_DIRS` (line 34) — covers underscore variant
   - Add `_SKIP_FILENAME_PATTERNS` list after `_OUR_OUTPUTS` (line 47):
     ```python
     _SKIP_FILENAME_PATTERNS = [
         re.compile(r'^\d+_informe.*\.docx?$', re.IGNORECASE),
         re.compile(r'^\d+_portada.*\.docx?$', re.IGNORECASE),
     ]
     ```
   - Add pattern check in `mine_project()` and `mine_project_groq()` file walks

**Verification:** Anciles extraction logs show no signals from `4001679_informe_V0.doc` or `4001679_portada_V0.doc`. No "Groq: will mine 4001679_informe_V0.doc" in logs.

---

### Change 6: Conflict Resolution for Groq Signals

**Problem:** Multiple sources give contradictory values (architect_name ×4, report_date ×4, province gets "Cataluña" from cost spreadsheet).

**Approach:** Targeted exclusion rules (not a full authority system).

**Files to modify:**

1. **`automation/fileminer/miners/groq_miner.py`** (`_parse_extractions()`)
   - Exclude `province` and `municipality` from cost/budget documents (filename contains `PLAN_COST`, `PRESSUPOST`, `COMANDA`)
   - Exclude `architect_name` from cost documents (Eva Vázquez is G3's technician, not the project architect)

2. **`automation/fileminer/competition.py`** (`resolve_competition()`)
   - For `report_date`: among same-priority signals, prefer the most recent date (latest document reflects current project state)

**Verification:** Anciles `province` = "HUESCA" (not "Cataluña"). `architect_name` doesn't include "Eva Vázquez Marcet". `report_date` picks latest date.

---

## End-to-End Verification

After all 6 changes:

```bash
# Clear all caches
rm -rf ~/.g3dt/cache/groq/ ~/.g3dt/cache/geocode/
rm -f reference-material/4001679\ ANCILES/validation/*_extracted.json

# Run with no cache
G3DT_NO_CACHE=1 G3DT_USE_GROQ=1 .venv/bin/python -m web

# Open http://localhost:8765/review.html → select "4001679 ANCILES"
# Verify:
# 1. superficie_parcela_m2 = 1655.01 ✓
# 2. superficie_construida_m2 = 1273.79 ✓
# 3. has_basement = Sí ✓
# 4. province = HUESCA ✓
# 5. Geocoding returns UTM coords for Huesca ✓
# 6. No signals from *_informe_V0.doc or *_portada_V0.doc ✓
# 7. architect_name ≠ "Eva Vázquez Marcet" ✓
# 8. All Groq calls are fresh (no cache HIT in logs) ✓
```

Run existing tests: `cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -m pytest tests/ -v`
