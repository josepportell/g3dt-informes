# P4 Next: Debug Geocode Flow + Move the Needle on Tier B

Created: 2026-03-29
Status: Ready to start

## The Problem

Tier B is stuck at 3.6% exact (2/55) because adjacents are wrong for 5/7 projects. The root cause is **geocoding resolves to the wrong parcel**. Even when the Cadastre Callejero API finds the correct parcel, `geocode_project()` returns a different (wrong) result.

## Concrete Example: Castellar del Vallès

```
Callejero API directly:  "Arbrells 18, Castellar del Valles" → RC 3298012 (CORRECT)
geocode_project():       "Carrer Arbrells 18, Castellar del Vallès" → RC 3298002 (#16, WRONG)
```

The Callejero finds the right answer but geocode_project() returns something else. Why?

## Debug Plan

### Step 1: Trace geocode_project() for Castellar

Run with DEBUG logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
from automation.geocode_coordinates import geocode_project
r = geocode_project('Carrer Arbrells 18', 'Castellar del Vallès', ['centre'], output_dir=None, province='Barcelona')
```

Look for:
- Does it attempt Consulta_DNPLOC? If not, why?
- Does Consulta_DNPLOC succeed but get overridden by a later step?
- Does it fall through to Nominatim? If so, Nominatim returns ~50m imprecise coords
- Is there a cache returning a stale result?

Key functions to trace in `automation/geocode_coordinates.py`:
- `geocode_project()` (main entry, line ~1755)
- `_cadastre_address_lookup()` (Callejero path, line ~1030)
- `_parse_address()` (address parsing, line ~263)
- `_resolve_municipality()` (municipality matching, line ~340)

### Step 2: Compare Callejero vs geocode_project for all 7 projects

```python
# Direct Callejero (correct)
callejero('Barcelona', 'CASTELLAR DEL VALLES', 'CL', 'ARBRELLS', '18') → 3298012

# geocode_project (may be wrong)
geocode_project('Carrer Arbrells 18', 'Castellar del Vallès', ...) → 3298002
```

Run both for all 7 projects. Document where they agree and disagree.

### Step 3: Fix the divergence

Likely causes:
1. `_parse_address()` doesn't extract the house number correctly for certain formats
2. `_resolve_municipality()` fails on accented names → skips Callejero → falls to Nominatim
3. Callejero succeeds but returns coords that fall on a neighbor parcel (coord precision)
4. A caching layer returns a stale result from a previous run

Possible fixes:
- **Add direct Callejero path in parcel_resolver.py**: bypass geocode_project entirely for address→RC lookup. Call ConsultaNumero directly with stripped accents. This is the cleanest approach — we already proved it works in our manual tests.
- **Fix _resolve_municipality()**: ensure accent stripping propagates to all Callejero calls
- **Fix _parse_address()**: ensure house numbers are correctly extracted for all formats

### Step 4: After geocoding is fixed, re-evaluate P4b sequencing

The P4b sequencing change (merge BEFORE adjacents) broke Bell-Lloc because:
- Bell-Lloc's geocode resolves to parcel 4613172 (single parcel, 500 m²)
- P4b merges 4613172 + 4613173 → merged polygon (1012 m²)
- But the merge changed the centroid → adjacents probe ran from wrong position
- The issue: `_phase3_adjacents()` re-geocodes internally → may get a different parcel

Fix: when P4b produces a merged polygon, pass it directly to `get_adjacent_parcels()` as a `polygon_override` parameter, bypassing the internal parcel lookup. This requires modifying `get_adjacent_parcels()` to accept an optional polygon.

### Step 5: Validate with benchmarks

After each fix, run:
```bash
rm -rf ~/.g3dt/cache/cadastre_adjacents/*.json ~/.g3dt/cache/nominatim_streets/ ~/.g3dt/cache/ortho_enrichment/ ~/.g3dt/cache/geocode/
G3DT_ORTHO_ENRICHMENT=1 .venv/bin/python scripts/collect_readiness.py --skip-vision --output-dir docs/validation-latest
.venv/bin/python scripts/compare_benchmarks.py
```

Target: Tier B > 10% exact, > 50% semantic.

## What NOT to change

- ICGC geology/elevation/slope still use DPSH coords (regional data, correct)
- Don't change the adjacents probe logic (edge classification, Nominatim streets — these work)
- Don't change the ortho enrichment pipeline (site_description is a success)
- Don't touch the Jinja template or report_generator for Tier B

## Project test matrix

| Project | Blocker | Expected fix |
|---------|---------|--------------|
| Bell-Lloc | Working! Keep as regression test | P4b polygon_override for merged adjacents |
| Castellar | geocode → #16 not #18 | Direct Callejero path |
| Rubí | geocode → wrong street | Direct Callejero path |
| Linyola | geocode → same street, different RC | Direct Callejero / area merge |
| Alcoletge | geocode fails (Nominatim) | Street name variant ("Girasols" vs "Gira-sols") |
| Vilanova | accent issue (Segrià) | Accent stripping already fixed |
| Anciles | No COORDENADES, Benasque not found | Special case — Aragón, not Catalunya |

## Recommended approach

**Simplest path to biggest impact: add a direct Callejero lookup in parcel_resolver.py.**

Instead of relying on geocode_project() (complex, many fallbacks, imprecise), call the Cadastre Callejero API directly with:
1. Street type + name + number (from `_parse_address()`)
2. Municipality (stripped accents)
3. Province

This gives us the EXACT cadastral reference from the official address database. We already proved this works for 5/7 projects in our manual tests.

Then use that RC to get the polygon via `get_parcel_geometry_utm()` and proceed with adjacents.
