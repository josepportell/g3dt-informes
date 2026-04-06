# Investigation Report: P1-P4 Root Cause Analysis

**Data:** 2026-04-06
**Branca:** `feature/concept-format-separation`
**Objectiu:** Diagnòstic precís abans d'implementar fixes

---

## P1: building_type (6 MISMATCH + 4 cascading cte_edificacio)

### Eva vs Pipeline — All 7 Projects

| Project | Eva's building_type | Pipeline building_type | Source | Status |
|---------|--------------------|-----------------------|--------|--------|
| BELL-LLOC | "un habitatge unifamiliar" | "habitatge unifamiliar aïllat" | planol_vision | MISMATCH |
| CASTELLAR | "3 habitatges unifamiliars d'estructura lleugera, fusta" | "habitatge unifamiliar aïllat" | planol_vision | MISMATCH |
| RUBI | "un habitatge unifamiliar aïllat modular" | "habitatge unifamiliar aïllat" | planol_vision | CLOSE |
| LINYOLA | "un nou habitatge unifamiliar" | "habitatge unifamiliar" | planol_vision | CLOSE |
| ALCOLETGE | "l'ampliació d'un edifici en planta baixa" | "habitatge unifamiliar" | planol_vision | MISMATCH |
| VILANOVA | "una vivienda unifamiliar aislada" | "vivienda unifamiliar" | planol_vision | CLOSE |
| ANCILES | "7 viviendas unifamiliares adosadas" | "viviendas adosadas" | planol_vision | MISMATCH |

### cte_edificacio Cascade

| Project | Eva's cte_edificacio | Pipeline | Status |
|---------|---------------------|----------|--------|
| RUBI | C-0 | NOT_EXTRACTED | — |
| BELL-LLOC | C-1 | NOT_EXTRACTED | — |
| CASTELLAR | C-1 | NOT_EXTRACTED | — |
| ANCILES | C-1 | NOT_EXTRACTED | — |

### Root Causes Identified

1. **Missing articles**: Pipeline strips "un/una/l'" — Eva always includes them
2. **Missing quantities**: Pipeline ignores "3", "7" — Eva includes count from comanda_lab ("CONSTR 3 HAB UNIF")
3. **Missing adjectives**: Pipeline drops "nou/modular/aïllat/aislada" — Eva includes descriptors
4. **Structural details lost**: Pipeline omits "d'estructura lleugera, fusta" — Eva captures material info
5. **Building purpose wrong**: Alcoletge is "ampliació" (extension), not new construction — pipeline defaults to "habitatge"
6. **Language**: Mixed CA/ES not handled consistently

### Source Priority Chain

```
user (priority 10) → planol_vision (20) → pressupost_pdf (30) → groq_llm (42) → content_email (43)
```

Pipeline currently gets value from planol_vision (priority 20) which produces minimal stripped-down descriptions.

### comanda_lab Patterns Found

The lab order files contain richer data: "CONSTR HABITATGE", "CONSTR 3 HAB UNIF", "CONSTR GRUPO DE VIVIENDAS" — these have quantity + type but are NOT being used for building_type.

### Code Path

- `web/wizard_service.py` lines ~485-489: `cte_edif = lookup_cte_edificacio(building_type or 'habitatge', num_floors or '1')`
- cte_edificacio depends on building_type being correct first

### Fix Requirements

NOT a simple post-processing — need multiple data sources:
- Vision extraction for base type
- comanda_lab for quantity
- Article/pluralization rules (CA/ES)
- Special cases: "ampliació", structural descriptors

---

## P2: planol wiring — architect_name (5 MISMATCH) + client_name (4 MISMATCH)

### Data Availability in planol_extracted.json

| Project | Planol File | architect | architect_company | client/promotor |
|---------|------------|-----------|------------------|-----------------|
| CASTELLAR | plà.pdf | null | G3 | null |
| RUBI | IMG-20251104 | null | null | null |
| LINYOLA | Sondeig.pdf | JOSEP BUNYESC PALACÍN | BUNYESC ARQUITECTURA EFICIENT, S.L.P | SÍLVIA EROLES BALAGUERÓ |
| BELL-LLOC | A.01.pdf | Jordi Bosch Novell | ARQUITECTURA BOSCH NOVELL | RAMON MITJANA SL |
| ALCOLETGE | A.01.pdf | DAVID GRAUS ROBINAT | 2 GRAUS | ALBERT SANS BONVEHI |
| VILANOVA | 1.0.pdf | Jordi Carner Rocar | ROCAR arquitectura i enginyeria | Grupo CUENCA GUERRERO |
| ANCILES | A01_TIPOL.pdf | ALBA BARRAU, MIRIAM CASTEL | null | ANDRÉS AMAT y ENRIQUE M. GARDETA |

### Eva vs Pipeline — Detailed Matrix

| Project | Field | Eva | Planol JSON | Pipeline Used | Source | Issue |
|---------|-------|-----|-------------|--------------|--------|-------|
| BELL-LLOC | architect_name | JORDI BOSCH NOVELL | Jordi Bosch Novell | JORDI BOSCH NOVELL | groq_llm | MATCH (case) |
| BELL-LLOC | client_name | RAMON MITJANA S.L | RAMON MITJANA SL | RAMON MITJANA S.L | docs_extracted | OK |
| LINYOLA | architect_name | SÍLVIA EROLES BALAGUERÓ | JOSEP BUNYESC PALACÍN | SR. | groq_llm | **planol has WRONG person** |
| LINYOLA | client_name | SRA. SÍLVIA EROLES BALAGUERÓ | SÍLVIA EROLES BALAGUERÓ | BUNYESC ARQUIT... | docs_extracted | **planol has correct value but unused** |
| ALCOLETGE | architect_name | ALBERT SANS BONVEHI | DAVID GRAUS ROBINAT | David Graus Robinet | planol | **planol architect ≠ Eva's architect** |
| ALCOLETGE | client_name | SR. ALBERT SANS BONVEHI | ALBERT SANS BONVEHI | ALBERT SANS... tel. | fileminer | planol correct but unused |
| VILANOVA | architect_name | JUAN JOSÉ TORRES POVEDANO | Jordi Carner Rocar | jordi carner | groq_llm | **planol architect ≠ Eva's** |
| VILANOVA | client_name | GRUPO CUENCA GUERRERO, S.L | Grupo CUENCA GUERRERO | NOT_EXTRACTED | — | planol has it, not wired |
| ANCILES | architect_name | ALBA MARIA BARRAU CASTÁN | ALBA BARRAU, MIRIAM CASTEL | ANDRÉS AMAT... | groq_llm | **planol has 2 names** |
| ANCILES | client_name | SRA. ALBA MARIA BARRAU... | ANDRÉS AMAT y ENRIQUE M... | MARIA ALBA BARRAU... | docs_extracted | **planol has promotor, not client** |

### Root Causes (NOT what the briefing assumed)

**The wiring IS implemented** in `automation/wizard.py::_load_planol()` (lines 265-371). The code correctly maps architect, architect_company, client_name/promotor.

**The real problems are:**

1. **Source priority override**: Higher-priority sources (groq_llm=42, fileminer=43, docs_extracted=30-35) OVERRIDE planol values even when planol is more accurate
2. **Planol data quality**: 2 projects (Castellar, Rubi) have NULL architect/client in planol — WhatsApp image and poor-quality planol
3. **Role confusion in planol**: Some plans list architect ≠ Eva's expected architect:
   - Linyola: planol says BUNYESC (the architect firm), Eva says EROLES (the client who is also the promotor)
   - Alcoletge: planol says GRAUS (firm), Eva says SANS (actually the promotor)
   - Vilanova: planol says CARNER (firm), Eva says TORRES POVEDANO (different person entirely)
4. **No confidence-weighted merging**: When groq_llm extracts garbage like "SR." with low confidence, it still overrides planol

### Key Insight

**This is NOT a simple "wire planol → pipeline" fix.** The planol architect ≠ Eva's expected value in 3/7 cases. Eva sometimes uses the promotor as architect_name, or uses a different person than what's on the plan. This needs Eva's clarification on naming conventions.

---

## P3: Lab Extraction (63 NOT_EXTRACTED)

### GTL PDF Locations

| Project | Report # | GTL PDF File | Status |
|---------|----------|-------------|--------|
| BELL-LLOC | 4677-GTL-25 | 4677-GTL-25 Bell-Lloc d'Urgell.pdf | EXISTS |
| CASTELLAR | 4687-GTL-25 | 4687-GTL-25 Castellar del Vallés.pdf | EXISTS |
| RUBI | 4703-GTL-25 | 4703-GTL-25 Rubí.pdf | EXISTS |
| LINYOLA | 4672-GTL-25 | 4672-GTL-25 Linyola.pdf | EXISTS |
| ALCOLETGE | — | PRESSUPOST GEOTEC.ALCOLETGE.pdf | EXISTS (pressupost, not GTL) |
| VILANOVA | — | PRESUPUESTO GEOTEC.VILANOVA DE SEGRIA.pdf | EXISTS (pressupost, not GTL) |
| ANCILES | — | NOT MAPPED | MISSING |

### GTL PDF Structure (Consistent Across All — Soilassaig Lab)

```
PAGE 1: Header + Client Info
  - Lab report number (e.g., 4677-GTL-25)
  - CLIENT = G3 Desenvolupament Territorial, SL (always the same)
  - MATERIAL TO TEST: sample type, location

PAGE 2: Sample Description
  - Mostra (Sample ID): e.g., "SPT1 S1"        → lab_sample_id
  - Cota d'extracció (m): e.g., "1,0 - 1,6"    → lab_depth
  - Obra/Projecte: location + project number
  - ASSAIGS REALITZATS (Tests Performed)         → lab_tests_text

PAGE 3: Chemical Test Results
  - Results table (e.g., Sulfate content: 89.8 mg/kg)
```

### Eva's Exact Values — All 9 Variables

| Variable | Bell-Lloc | Castellar | Rubi | Linyola | Alcoletge | Vilanova | Anciles |
|----------|-----------|-----------|------|---------|-----------|----------|---------|
| lab_field_company | TPS PROSPECCIÓ DEL SUBSÒL SL | TPS PROSPECCIÓ DEL SUBSÒL, S.L | TPS PROSPECCIÓ DEL SUBSÒL SL | TPS PROSPECCIÓ DEL SUBSÒL, S.L | TPS PROSPECCIÓ DEL SUBSÒL SL | TPS PROSPECCIÓ DEL SUBSÒL SL | TPS PROSPECCIÓ DEL SUBSÒL SL |
| lab_testing_company | TPS PROSPECCIÓ DEL SUBSÒL SL | (same) | (same) | (same) | (same) | (same) | (same) |
| lab_field_description | laboratori d'assaigs per al control de qualitat de l'edificació | (same) | (same) | (same) | (same) | laboratorio de ensayos para el control de calidad de la edificación | laboratorio de ensayos... |
| lab_testing_description | (same as field) | (same) | (same) | (same) | (same) | (ES version) | (ES version) |
| lab_location | Punt: S-1 | Punt: S-1 | Punt: P-3 | Punt: P-3 | Punt: P-3 | Punto: P-3 | Punto: S-2 |
| lab_sample_id | Mostra : SPT-1 | Mostra : SPT-1 | Mostra : SPT-1 | Mostra : SPT-1 | Mostra : SPT-1 | Muestra: SPT-1 | Muestra: MA-1 |
| lab_depth | Profunditat: -1.0 a -1.60 m | -1.00 a -1.20 m | -0.60 a -1.20 m | -1.00 a -1.15 m | -0.80 a -1.40 m | -1.00 a -1.60 m | -2.80 a -3.00 m |
| lab_tests_text | 1 assaig contingut sulfats UNE 83963 | (same) | Granulometria UNE 103101... | Límits Atterberg UNE 103103... | Límits Atterberg... | Sulfatos UNE 83963... | Sulfatos UNE 83963... |
| access_street | ...entrada...Carrer existent al sud | ...carrer adjacent al sud | ...carrer de la Miranda | ...es va visitar l'obra... | ...carrer adjacent | NOT FOUND | ...trabajos de campo... |

### Key Findings

1. **lab_field_company and lab_testing_company are IDENTICAL across ALL projects** — always "TPS PROSPECCIÓ DEL SUBSÒL SL" (minor punctuation variants). Could be hardcoded or extracted once.

2. **lab_field_description and lab_testing_description are IDENTICAL** — fixed Catalan or Spanish text depending on language. Should be templated, not extracted.

3. **lab_location, lab_sample_id, lab_depth** come from PAGE 2 of GTL PDF — structured fields, regex-extractable.

4. **lab_tests_text** comes from PAGE 2 "ASSAIGS REALITZATS" section — text field, may span lines.

5. **access_street is NOT from GTL PDF** — it's a narrative sentence from the main report body. Different extraction strategy needed.

### Current Code Status

**`automation/lab_extractor.py` ALREADY extracts some data but DOESN'T output it:**
- ✅ sulfate_mg_kg: Extracted and used (WORKING)
- ✅ sample_info: Extracted via regex BUT NOT PASSED to output
- ✅ test_type: Identified BUT NOT PASSED to output
- ❌ lab_field_company: Not attempted
- ❌ lab_testing_company: Not attempted
- ❌ lab_field_description: Not attempted (should be template)
- ❌ lab_testing_description: Not attempted (should be template)

### Schema Status

**The 9 lab_* variables are NOT defined in `schemas/concepts/report_variables.yaml`** — the pipeline doesn't know these variables exist. This is a prerequisite blocker.

### PyMuPDF Extraction Feasibility

| Data | Location | Difficulty | PyMuPDF? |
|------|----------|-----------|----------|
| lab_field_company | Page 1 header | TRIVIAL | ✅ Hardcode "TPS PROSPECCIÓ DEL SUBSÒL SL" |
| lab_testing_company | Page 1 footer | TRIVIAL | ✅ Same as above |
| lab_field_description | Implicit | TRIVIAL | ✅ Template by language |
| lab_testing_description | Implicit | TRIVIAL | ✅ Template by language |
| lab_location | Page 2 "Situació:" | EASY | ✅ Regex after label |
| lab_sample_id | Page 2 "Mostra:" | EASY | ✅ Regex SPT/MA pattern |
| lab_depth | Page 2 "Cota d'extracció" | EASY | ✅ Numeric range pattern |
| lab_tests_text | Page 2 "ASSAIGS REALITZATS" | MEDIUM | ✅ Multi-line text field |
| access_street | NOT in GTL | N/A | ❌ Needs different source |

### Bilingual Patterns

- Catalan: "Profunditat", "Mostra", "Punt"
- Spanish: "Profundidad", "Muestra", "Punto"
- All PDFs from Soilassaig lab (bilingual company)
- Depth format: "1,0 - 1,6" (European) vs "1.00 a 1.60" (mixed)

---

## P4: Narrative Templates (28 NOT_EXTRACTED)

### 1. building_structure_desc (7 NOT_EXTRACTED)

| Project | Eva's Value | Pattern | Input Data |
|---------|------------|---------|------------|
| RUBI | "en planta baixa" | Ground floor | num_floors=PB+Porxo |
| BELL-LLOC | "en planta baixa" | Ground floor | num_floors=Pb+1Pp |
| ANCILES | "un semisótano en dos de las siete viviendas previstas" | Conditional basement | has_basement=true |
| CASTELLAR | "sense nivell de soterrani" | No basement | num_floors=Pb+1Pp |
| LINYOLA | "sense nivell de soterrani" | No basement | num_floors=Pb |
| ALCOLETGE | "sense nivell de soterrani" | No basement | num_floors=Pb |
| VILANOVA | "sin nivel de sótano" | No basement (ES) | num_floors=Pb |

**Template logic:**
- "en planta baixa" when only ground floor
- "sense nivell de soterrani" / "sin nivel de sótano" when no basement
- Conditional for Anciles (complex: semisótano in 2 of 7 houses)

**Status: CAN_TEMPLATE** (except Anciles edge case)

### 2. location_sentence (7 NOT_EXTRACTED)

| Project | Eva's Value | Format |
|---------|------------|--------|
| RUBI | "a una parcel·la ubicada al carrer de la Miranda nº 39, (PARC. 6-105) Rubí, Barcelona" | Address + parcel ref |
| BELL-LLOC | "entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell" | Between 2 streets |
| ANCILES | "en la calle Gral Ferraz nº20 en el municipio de Anciles, Benasque" | Address + municipality |
| CASTELLAR | "en el Carrer dels Arbrells, 18 de Castellar del Vallès" | Simple address |
| LINYOLA | "al Carrer Clot de la Llacuna nº16 de Linyola" | Address + municipality |
| ALCOLETGE | "a una parcel·la ubicada al Carrer Girasols nº7, Urbanització El Roser d'Alcoletge" | Address + urbanization |
| VILANOVA | "en la Calle STA. GEMMA nº 4, URB. LA SERRA del municipio de VILANOVA DE SEGRIÀ" | Address + urbanization |

**3 format variants identified:**
- Format 1: Simple address + municipality (Castellar, Linyola, Anciles)
- Format 2: "entre X i Y" — between two streets (Bell-Lloc)
- Format 3: Address + urbanization name (Alcoletge, Vilanova)

**Status: PARTIALLY_TEMPLATABLE** — needs heuristic for format selection

### 3. num_dpsh_tests (7 NOT_EXTRACTED)

| Project | Eva's Value | Count | Language |
|---------|------------|-------|----------|
| RUBI | "3 assaigs de penetració dinàmica tipus DPSH..." | 3 | CA |
| BELL-LLOC | "2 assaigs de penetració dinàmica tipus DPSH..." | 2 | CA |
| ANCILES | "2 ensayos SPT con recuperación de muestra..." | 2* | ES |
| CASTELLAR | "4 assaigs de penetració dinàmica tipus DPSH..." | 4 | CA |
| LINYOLA | "3 assaigs de penetració dinàmica tipus DPSH..." | 3 | CA |
| ALCOLETGE | "3 assaigs de penetració dinàmica tipus DPSH..." | 3 | CA |
| VILANOVA | "3 ensayos de penetración dinámica DPSH..." | 3 | ES |

**Template:**
- CA: `"{N} assaigs de penetració dinàmica tipus DPSH (veure annex \"Registre assaigs mecànics\")."`
- ES: `"{N} ensayos de penetración dinámica DPSH (ver registro de los ensayos mecánicos)."`
- *Anciles anomaly: text says "2 ensayos SPT" but has 6 tests — may be manual override

**Status: FULLY TEMPLATABLE** — count from dpsh_extracted.json

### 4. site_condition (7 NOT_EXTRACTED)

| Project | Eva's Value | Slope | Anthropized |
|---------|------------|-------|-------------|
| RUBI | "no antropitzat, no s'han detectat marques..." | Flat | No |
| BELL-LLOC | "antropitzat, no s'han detectat marques..." | Flat | Yes |
| ANCILES | "En la zona de estudio no se han detectado marcas..." | Unknown | — |
| CASTELLAR | "Tot i no ser un solar pla, no s'han detectat marques..." | Sloped | — |
| LINYOLA | "Com que es tracta d'un solar pla, no s'han detectat marques..." | Flat | — |
| ALCOLETGE | "Com que es tracta d'un solar pla, no s'han detectat marques..." | Flat | — |
| VILANOVA | "En la zona de estudio no se han detectado marcas..." | Unknown | — |

**Slope descriptors found:** "no antropitzat", "antropitzat", "solar pla", "Tot i no ser un solar pla"

**Status: PARTIALLY_TEMPLATABLE** — needs `is_sloped` input (from ICGC?) and `is_anthropized` (unclear source)

### 5. table_dpsh_range (7 NOT_EXTRACTED)

| Project | Eva's Value | Pattern |
|---------|------------|---------|
| RUBI | "3 i 4" | Numbers only (CA) |
| BELL-LLOC | "3, 4 i 5" | Numbers only (CA) |
| ANCILES | "Tabla 3, 4 y 5. Resumen de los ensayos in situ realizados." | Full sentence (ES) |
| CASTELLAR | "3, 4 i 5" | Numbers only (CA) |
| LINYOLA | "3, 4 i 5" | Numbers only (CA) |
| ALCOLETGE | "3 i 4" | Numbers only (CA) |
| VILANOVA | "Tabla 3 y 4. Resumen de los ensayos in situ realizados." | Full sentence (ES) |

**Fixed convention:** Tables 3-5 based on DPSH count. CA = numbers only, ES = full sentence.

**Status: FULLY TEMPLATABLE**

### Summary: Templating Feasibility

| Variable | Templatable | Complexity | Blockers |
|----------|------------|-----------|----------|
| num_dpsh_tests | ✅ FULL | Low | None |
| table_dpsh_range | ✅ FULL | Low | None |
| building_structure_desc | ✅ MOSTLY | Low-Med | Need basement flag |
| location_sentence | ⚠️ PARTIAL | Medium | Format detection heuristic, urbanization data |
| site_condition | ⚠️ PARTIAL | Medium | is_sloped missing, is_anthropized unclear |

**Quick wins:** num_dpsh_tests + table_dpsh_range = 14 NOT_EXTRACTED fixable immediately.

---

## Cross-Cutting Findings

### 1. Language Determination is Critical
All 4 priorities need CA vs ES logic. Projects:
- **Catalan (CA):** Rubi, Bell-Lloc, Castellar, Linyola, Alcoletge
- **Spanish (ES):** Vilanova, Anciles

### 2. The Briefing Assumptions Were Partially Wrong

| Assumption | Reality |
|-----------|---------|
| P1: "Just add article + quantity" | More complex: ampliació vs new, structural descriptors, comanda_lab not used |
| P2: "planol data not wired" | Code IS wired. Problem is priority override + planol has wrong person in 3/7 cases |
| P3: "Need new extractor" | lab_extractor.py already extracts some data but doesn't output it. Schema gap is the blocker |
| P4: "Simple templates" | 2/5 are simple; 3/5 need missing input data (slope, basement, urbanization) |

### 3. Missing Schema Definitions
- 9 lab_* variables NOT in report_variables.yaml
- access_street extraction needs different source (main report, not GTL)

### 4. Questions for Eva
- P2: Why does architect_name sometimes = promotor? (Alcoletge, Linyola)
- P1: Where does "ampliació" vs "nou" come from? (Alcoletge)
- P4: How does Eva determine `is_sloped` and `is_anthropized`?
- P4: How does Eva choose between location_sentence formats?

---

*Document generat per investigació diagnòstica. Referència per a implementació posterior.*
