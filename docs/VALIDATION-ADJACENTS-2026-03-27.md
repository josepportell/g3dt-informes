# Adjacents Geocoding Validation — 2026-03-27

All 7 projects tested after implementing the 5-layer geocoding pipeline.
Results to be compared against Eva's signed reports for accuracy validation.

## Summary

| Project | Adjacents | Resolution Layer | UTM Source | Readiness |
|---------|-----------|-----------------|------------|-----------|
| Alcoletge | 4/4 | LLM street picker (Layer 3) | geocode | 90% |
| Rubí | 4/4 | DPSH coords (existing) | COORDENADES.txt | 90% |
| Linyola | 4/4 | DPSH coords (existing) | COORDENADES.txt | 90% |
| Vilanova de Segrià | 4/4 | Nominatim structured (Layer 4) | geocode | 57.5% |
| Anciles | 4/4 | DPSH coords (existing) | geocode | 58.5% |
| Castellar del Vallès | 4/4 | DPSH coords + geocode override | COORDENADES.txt | 92.7% |
| Bell-Lloc | 4/4 | difflib fuzzy (Layer 2) | geocode | 100% |

**Result: 7/7 projects with all 4 adjacents filled (28/28 fields).**

## Per-Project Detail

### 1. Alcoletge (4001670)

**Address input:** `Carrer Girassols #7` (vision OCR — double 's')
**Municipality:** Alcoletge
**Province:** Lleida
**UTM:** (308778, 4613954) via geocode

**Resolution path:**
- Layer 1 (exact): FAIL — street "Girassols" not in ALCOLETGE
- Layer 2 (difflib): FAIL — "GIRASSOLS" vs "DELS GIRASOLS" ratio=0.73 < 0.8
- Layer 3 (LLM): SUCCESS — Groq matched "Girassols" → "DELS GIRASOLS"
- Cadastre found RC → UTM → polygon → probe

**Adjacents:**
| Direction | Value |
|-----------|-------|
| North | via pública |
| South | parcel·la amb construcció |
| East | parcel·la amb construcció |
| West | parcel·la buida |

**Notes:**
- Key test case for the LLM street picker
- The Cadastre stores street as "DELS GIRASOLS" (with article)
- client_address from Groq had correct spelling "Girasols" but street_address (from vision) had "Girassols"
- Also got cota_referencia from ICGC MDT: +188.50
- Also got slope: 4.5% toward W

---

### 2. Rubí (3001631)

**Address input:** `Carrer de la Miranda` (from planol vision)
**Municipality:** Rubí
**Province:** Barcelona
**UTM:** (419176.57, 4593889.83) from COORDENADES.txt

**Resolution path:**
- Has DPSH coords from COORDENADES.txt
- Adjacents geocode attempted with `site_address` but got garbage: "PERSONA DE CONTACTE" (an email template field leaked through)
- Fell back to DPSH coords successfully

**Adjacents:**
| Direction | Value |
|-----------|-------|
| North | parcel·la amb construcció |
| South | Passeig Francesc Macia |
| East | parcel·la amb construcció |
| West | Carrer Rafael Casanova |

**Notes:**
- The "PERSONA DE CONTACTE" leak is a data quality bug in signal extraction — not a geocoding issue
- Despite the garbage address, adjacents succeeded via DPSH coords fallback
- Slope: 5.2% toward W

---

### 3. Linyola (4001607)

**Address input:** `Carrer Clot de la Llacuna, 16` (multiple sources agree)
**Municipality:** Linyola
**Province:** Lleida
**UTM:** (324942.67, 4619562.0) from COORDENADES.txt, override to (324926, 4619491) via geocode

**Resolution path:**
- Has DPSH coords from COORDENADES.txt
- Adjacents geocode attempted with `site_address` but got garbage (same email template leak)
- ConsultaVia returned HTTP 500 (Cadastre server error) — not our bug
- client_address "Carrer Clot de la Llacuna nº16" from Groq successfully geocoded via Nominatim structured
- Used geocoded coords instead of DPSH (geocode was ~70m away from DPSH)

**Adjacents:**
| Direction | Value |
|-----------|-------|
| North | parcel·la amb construcció |
| South | Polígono |
| East | parcel·la buida |
| West | Camí Arcs,Dels |

**Notes:**
- "adjacent_south: Polígono" and "adjacent_west: Camí Arcs,Dels" — translation not fully cleaned
- Nominatim structured query (P1b) worked: `street='Clot de la Llacuna 16', city='Linyola'`
- Sulfate extracted: 0.0 mg/kg
- Slope: 0.7% toward S

---

### 4. Vilanova de Segrià (4001671)

**Address input:** `Calle Santa Gemma Nº4` (from tall.pdf)
**Municipality:** Vilanova de Segrià
**Province:** Lleida
**UTM:** (298603, 4620373) via geocode

**Resolution path:**
- No COORDENADES.txt
- Layer 1 (exact): FAIL — municipality "Vilanova de Segrià" not found in LLEIDA or neighbors
- Layer 4 (Nominatim structured): SUCCESS — `street='Santa Gemma 4', city='Vilanova de Segrià'`
- Cadastre grid search found matching parcel: 8606708CG9280N
- Geometry-based probing (10 vertices)

**Adjacents:**
| Direction | Value |
|-----------|-------|
| North | parcel·la buida |
| South | parcel·la amb construcció |
| East | parcel·la amb construcció |
| West | Carrer Santa Gemma Anterior 25313A00700066 |

**Notes:**
- "adjacent_west: Carrer Santa Gemma Anterior 25313A00700066" — RC leaked into street name, needs cleaning
- Municipality not in Cadastre callejero (possibly too small or indexed differently)
- Nominatim structured (P1b) was the hero here
- Slope: 20.2% toward E — auto-set is_sloped=True
- Low readiness (57.5%) because no DPSH data yet

---

### 5. Anciles (4001679)

**Address input:** `Calle Gral Ferraz nº20` (from tall.pdf)
**Municipality:** Benasque (Anciles is a village within Benasque)
**Province:** Huesca (Aragón — not Catalunya!)
**UTM:** (295686, 4718417) via geocode

**Resolution path:**
- Has COORDENADES.txt
- Groq correctly extracted province="HUESCA" from plànol docs
- Geocode used existing DPSH coords (geocoded address matched exactly)
- Street "Gral Ferraz" → "General Ferraz" via abbreviation expansion

**Adjacents:**
| Direction | Value |
|-----------|-------|
| North | parcel·la amb construcció |
| South | via pública |
| East | parcel·la buida |
| West | parcel·la buida |

**Notes:**
- Cross-province (P3) not needed because Groq extracted correct province "Huesca"
- P3 would have been needed if province was wrong/missing
- Anciles is in Aragón, not Catalunya — ICGC geological unit set manually
- Low readiness (58.5%) because no DPSH data processed yet

---

### 6. Castellar del Vallès (3001621)

**Address input:** `Carrer Arbrells, 18A, 08211 Castellar del Vallès, Barcelona`
**Municipality:** Castellar del Vallès
**Province:** Barcelona
**UTM:** (423181.4, 4609622.18) from COORDENADES.txt, override to (423233, 4609621) via geocode

**Resolution path:**
- Has DPSH coords from COORDENADES.txt
- Geocode found parcel at slightly different location (+52m east)
- Used geocoded coords for adjacents (more accurate for the project parcel)

**Adjacents:**
| Direction | Value |
|-----------|-------|
| North | Carrer Arbrells dels |
| South | parcel·la amb construcció |
| East | Carrer Alzina de L' |
| West | parcel·la amb construcció |

**Notes:**
- "Carrer Arbrells dels" and "Carrer Alzina de L'" — translation truncation artifact
- High readiness (92.7%)
- Slope: 36.4% toward NW — steep site
- Sulfate: 0.0 mg/kg

---

### 7. Bell-Lloc (4001612)

**Address input:** `C/ MESTRE RAMON ORTIZ 15 BELL-LLOC` (from Cadastre PDF)
**Municipality:** Bell-Lloc d'Urgell
**Province:** Lleida
**UTM:** (314418.9, 4611117.6) from COORDENADES.txt, override to (314499, 4611198) via geocode

**Resolution path:**
- Has DPSH coords from COORDENADES.txt
- First 4 geocode attempts failed (address contained municipality "BELL-LLOC" which confused parsers)
- 5th attempt: client_address="CL MESTRE RAMON ORTIZ 15" → difflib fuzzy matched at ratio=0.92
  - "CL MESTRE RAMON ORTIZ" fuzzy matched → "MESTRE RAMON ORTIZ" (the "CL" prefix lowered ratio)
- Cadastre found RC 4613172CG1141S → UTM (314508.7, 4611192.9)
- Geometry-based probing (9 vertices)

**Adjacents:**
| Direction | Value |
|-----------|-------|
| North | Carrer Antoni Bellet i Perez |
| South | parcel·la amb construcció |
| East | parcel·la amb construcció |
| West | parcel·la amb construcció |

**Notes:**
- Bell-Lloc is the reference project (100% readiness)
- Note: Bell-Lloc wizard shows different adjacents from these geocoded ones
  (user_data.json has Eva's manual values). These geocoded values are from the live pipeline.
- cota_referencia=+199.50 from sondeig elevation_z (overrides ICGC)
- Sulfate: 89.8 mg/kg
- Slope: 3.3% toward W
- Municipality cleaned from adjacent_north: removed "Bell-Lloc d'Urgell" suffix

## Known Issues to Fix

1. **Street name translation artifacts:**
   - "Carrer Arbrells dels" (Castellar) — article left dangling
   - "Carrer Alzina de L'" (Castellar) — apostrophe truncation
   - "Camí Arcs,Dels" (Linyola) — comma+article not cleaned
   - "Polígono" (Linyola) — should be "Polígon" (Catalan) or descriptive text

2. **RC leaking into street names:**
   - "Carrer Santa Gemma Anterior 25313A00700066" (Vilanova) — RC should be stripped

3. **Data quality (not geocoding):**
   - "PERSONA DE CONTACTE" as site_address (Rubí, Linyola) — email template field leak
   - Multiple failed geocode attempts before success (Bell-Lloc) — address "C/ MESTRE RAMON ORTIZ 15 BELL-LLOC" includes municipality name which confuses _parse_address

## Layers That Fired

| Layer | Projects where it was the resolver |
|-------|-----------------------------------|
| Layer 1: Cadastre exact | Castellar (for geocode override) |
| Layer 2: difflib fuzzy | Bell-Lloc (ratio=0.92, CL prefix) |
| Layer 3: LLM street picker | Alcoletge (GIRASSOLS → DELS GIRASOLS) |
| Layer 4: Nominatim structured | Vilanova de Segrià |
| Layer 5: Cross-province | Not needed (Groq got Huesca right for Anciles) |
| DPSH fallback | Rubí, Linyola (primary), Anciles, Castellar, Bell-Lloc |
