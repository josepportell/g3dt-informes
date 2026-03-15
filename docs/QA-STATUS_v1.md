# G3DT Report QA Status

Last updated: 2026-03-15
Element IDs: from Bell-Lloc audit visual (4001612_generated_AUDIT_VISUAL)

## 1. Sample Projects Profile

Each sample project tests different scenarios. **Not all are "complete" projects** — understanding what each one covers prevents false expectations.

| Project | Expedient | What it tests | Has sondeig | Has A.01.pdf | Has user_data | Has COORDENADES.txt | Special characteristics |
|---------|-----------|---------------|:-----------:|:------------:|:-------------:|:-------------------:|------------------------|
| **Bell-Lloc** | 4001612 | Base reference (complete) | ✅ | ✅ | ✅ (full) | ✅ | Carbonated soils (E=650 override), 1 geological level despite 2 materials, formatted annex |
| **Rubí** | 3001631 | DPSH-only project | ❌ | ❌ | ✅ (partial) | ❌ | No sondeig → sections 2.4.2, taula 4 omitted. Settlement back-engineering reference. N20=40, Nb=47-R |
| **Linyola** | 4001607 | Non-standard naming | ✅ | ❌ | ❌ | ❌ | Files named differently (e.g. `Punts de Sondeig_Silvia_Jaume.pdf`). Missing standard inputs |
| **Castellar** | 3001621 | Combined field sheets | ✅ | ❌ | ❌ | ❌ | `PENETROS + SONDEIG.pdf` combined. Multiple test runs. Multiple photos |

**Implications:**
- Only Bell-Lloc can validate plànol vision extraction (only one with A.01.pdf)
- Only Bell-Lloc + Rubí have user_data → others show raw auto-extract quality
- Rubí is the reference for "no sondeig" conditional sections
- Linyola tests FileScanner robustness with non-standard naming
- Castellar tests combined PDF parsing

---

## 2. Report Items — Source Chain & Status

Items ordered by appearance in the generated report. Element IDs from the Bell-Lloc audit (`pNNN` = paragraph, `tN_rN_cN` = table cell).

### 2.1 Portada & Índex

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 1 | Index (TOC) | p002-p033 | Auto (Word TOC) | Template static + section numbering | Section headers generate TOC entries | — | ✅ OK | TOC updates on Word open | |
| 2 | Annexes list | p035-p041 | Template | Static template text | Fixed annex list | — | ✅ OK | |

### 2.2 Presentació (Secció 1)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 3 | Section 1 header | p043 | Template | Static | — | — | ✅ OK | |
| 4 | Client name | p047 | Acceptació / DTE | user_data > content_discovery > planol_vision > DADES CLIENT.txt | First non-empty. Auto uppercases, SL→S.L. | `""` | ✅ OK | |
| 5 | Intro paragraph | p049 | Template | Static boilerplate | — | — | ✅ OK | |
| 6 | Section 1.1 header | p052 | Template | Static | — | — | ✅ OK | |
| 7 | Antecedents paragraph | p054 | Plànol caixetí + DTE | user_data > planol_vision > content_discovery | Contains: architect_name, architect_company, client, building_type | `""` | ⚠️ | Multiple variables in one paragraph. Only testable with Bell-Lloc A.01.pdf | |
| 8 | Building description intro | p056 | Template | Static | — | — | ✅ OK | |
| 9 | Num floors | t0_r0_c1 | Plànol caixetí | user_data > planol_vision → `format_floor_notation()` | Vision reads, formatted as "PB+P1" | `""` | ✅ OK | |
| 10 | Sup. parcel·la (cadastral) | t0_r1_c1 | Cadastre / Plànol | user_data > auto(Cadastre WFS geometry) > planol_vision | Cadastral preferred over plan measurement | `""` | ✅ OK | |
| 11 | Sup. construïda | t0_r2_c1 | Plànol cotes | user_data > planol_vision(floor_surfaces aggregation) | Complex: groups sub-zones by floor prefix, sums. Handles "PB+PP" splits | `""` | ⚠️ | Most complex extraction. Combined labels fixed (commit 8045b18) | |
| 12 | Taula 1 caption | p058 | Template | Static | — | — | ✅ OK | |
| 13 | Location paragraph | p060 | Plànol / DTE / Cadastre | user_data > auto(adjacent_south_street) | "es situarà entre el ... i el {adjacent_south_street} de {municipality}" | `""` | ⚠️ | Depends on adjacent_south_street extraction | Fix: municipality is not placed at the end. One of the streets is empty. |
| 14 | Fig 1+2 image | t1_r0_c0 | Plànol situació + ICGC | situation_plan left crop + ICGC orthophoto | PyMuPDF crop 38% left. ICGC WMS + parcel overlay | — | ✅ OK | Confirmed by Eva | |
| 15 | Fig 1+2 caption | p062 | Template | Static + fig numbering | — | — | ✅ OK | |
| 16 | Fig 3 caption | p064 | Template | Static + fig numbering | — | — | ✅ OK | |
| 17 | Section 1.2 header | p067 | Template | Static | — | — | ✅ OK | |
| 18 | CTE intro paragraph | p069 | Template | Static boilerplate | — | — | ✅ OK | |
| 19 | CTE building class | t2_r0_c1 | CTE table | `classify_building(area, floors, basement)` | CTE lookup. Missing inputs → C-1 safe default | `"C-1"` | ✅ OK | |
| 20 | CTE soil class | t2_r1_c1 | CTE table from N20 | `_determine_soil_class(avg_n20)` | <10→T-3, 10-30→T-2, ≥30→T-1 | `"T-1"` | ✅ OK | |
| 21 | Taula 2 caption | p071 | Template | Static | — | — | ✅ OK | |
| 22 | Section 1.3 header | p074 | Template | Static | — | — | ✅ OK | |
| 23 | Objectius intro | p076 | Template | Static | — | — | ✅ OK | |
| 24 | Objectius bullet list | p078-p083 | Template | Static boilerplate (6 items) | — | — | ✅ OK | |

### 2.3 Treballs de Camp (Secció 2)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 25 | Section 2 header | p087 | Template | Static | — | — | ✅ OK | |
| 26 | Field work dates | p089 | PENETROS.pdf dates | user_data > auto(extract_field_dates from PDFs) | Regex DD/MM/YYYY from PENETROS + lab PDFs. Formatted as Catalan text | `""` | ⚠️ | Handwritten dates hard to parse with regex | Fix: data al PDF (InformeId)_DPSH.pdf a ANNEXES |
| 27 | Field work bullet list | p090-p093 | Template | Static (4 items) | — | — | ✅ OK | |
| 28 | Section 2.1 header | p096 | Template | Static | — | — | ✅ OK | |
| 29 | Section 2.1.1 header | p098 | Template | Static | — | — | ✅ OK | |
| 30 | Adjacents intro | p100 | Municipality + parcel shape | user_data > auto(municipality) | "La parcel·la ... es situa al {direction} del municipi de {municipality}" | `""` | ✅ OK | |
| 31 | Adjacent north | p102 | Cadastre visor / camp | user_data > auto(Cadastre WFS) > adjacents_visor.json | WFS query from UTM. Formatted with Catalan articles | `""` | ⚠️ | API sometimes returns generic descriptions |Eva: "Es pot treure del visor del ICGC, o bé de les observacions de la ubicació de la parcel·la en el google maps, o google earth" |
| 32 | Adjacent south | p103 | Cadastre visor / camp | Same as north | Same | `""` | ⚠️ | | Eva: "Es pot treure del visor del ICGC, o bé de les observacions de la ubicació de la parcel·la en el google maps, o google earth" |
| 33 | Adjacent east | p104 | Cadastre visor / camp | Same as north | Same | `""` | ⚠️ | | Eva: "Es pot treure del visor del ICGC, o bé de les observacions de la ubicació de la parcel·la en el google maps, o google earth"|
| 34 | Adjacent west | p105 | Cadastre visor / camp | Same as north | Same | `""` | ⚠️ | | Eva: "Es pot treure del visor del ICGC, o bé de les observacions de la ubicació de la parcel·la en el google maps, o google earth"|
| 35 | Section 2.1.2 header | p107 | Template | Static | — | — | ✅ OK | |
| 36 | Access description | p109 | Eva's field notes | user_data > auto(content_discovery ACCES field) | Searches field prep documents | `""` | ⚠️ | Rarely auto-detected | |
| 37 | Site description | p111 | Eva's field notes | user_data (manual entry) | No auto-detection | `""` | ❌ Manual | Could parse from DTE.txt? | Eva: "Es pot treure o bé del PDF de la carpeta de fotografies o bé de la carpeta fotografies de la carpeta o bé de les observacions de la ubicació de la parcel·la en el google maps, o google earth (amb visió “frontal” amb nino)."|
| 38 | No pathologies paragraph | p113 | Template | Static boilerplate | — | — | ✅ OK | |
| 39 | No outcrops paragraph | p115 | Template | Static boilerplate | — | — | ✅ OK | |
| 40 | Photo 1 caption | p117 | Auto-numbered | `photo_site_text` from `_build_numbering_context()` | "Fotografia 1" or "Fotografia 1 i Fotografia 2" | — | ✅ OK | |
| 41 | Section 2.2 header | p120 | Template | Static | — | — | ✅ OK | |
| 42 | Campaign description | p122 | Field work dates | `data_camp_text` | Same date as #26 | — | ✅ OK | | Veure data a (InfRef)_sondeig.pdf i si no coincideix amb data a (InfRef)_DPSH.pdf, afegir les dues |
| 43 | DPSH test count | p124 | Excel | `num_dpsh_tests` from DPSHExtractor | "2 assaigs de penetració dinàmica tipus DPSH" | `0` | ✅ OK | Llistat dinàmic segons descripció a (carpeta_numèrica)/Pressupost*.pdf ->   |
| 44 | Sondeig + SPT count | p125 | Field campaign | `has_sondeig` + sondeig test count | "1 sondeig a rotació ... i 1 assaig SPT" | — | ✅ OK | Conditional: omitted if no sondeig | |
| 45 | Field observations bullet | p126 | Template | Static | — | — | ✅ OK | |
| 46 | Photography bullet | p127 | Template | Static | — | — | ✅ OK | |
| 47 | Lab company paragraph | p129 | Acceptació | user_data (manual entry) | `lab_field_company` + `lab_field_description` | `""` | ❌ Manual | Always manual. Default: "TPS PROSPECCIÓ DEL SUBSÒL SL" | |
| 48 | Section 2.3 header | p131 | Template | Static | — | — | ✅ OK | |
| 49 | CTE compliance text | p133 | Template | Static boilerplate | — | — | ✅ OK | |
| 50 | SPT interchange note | p135 | Template | Static boilerplate | — | — | ✅ OK | |
| 51 | Section 2.4 header | p138 | Template | Static | — | — | ✅ OK | |
| 52 | Section 2.4.1 header | p140 | Template | Static | — | — | ✅ OK | |
| 53 | DPSH method description | p142-p151 | Template | Static boilerplate (multi-paragraph) | Machine specs, methodology | — | ✅ OK | |
| 54 | DPSH machine name | p153 | Template | Static ("Rolatec ML-76A") | — | — | ✅ OK | |
| 55 | Photo 2 caption (DPSH) | p156 | Auto-numbered | `photo_dpsh_num` | — | — | ✅ OK | |
| 56 | Section 2.4.2 header (sondeig) | p160 | Template | Static. **Conditional: only if has_sondeig** | — | — | ✅ OK | |
| 57 | Sondeig method description | p162-p166 | Template | Static boilerplate (3 paragraphs) | — | — | ✅ OK | |
| 58 | Photo 3 caption (sondeig) | p168 | Auto-numbered | `photo_sondeig_num` | — | — | ✅ OK | |
| 59 | Section 2.4.3 header (SPT) | p170 | Template | Static. Section number shifts if no sondeig | — | — | ✅ OK | |
| 60 | SPT method description | p172 | Template | Static boilerplate | — | — | ✅ OK | |
| 61 | SPT figure caption | p174 | Template | Static + `fig_spt_cullera_num` ("Figura 4") | — | — | ✅ OK | |
| 62 | SPT sample recovery | p176 | Template | Static boilerplate | — | — | ✅ OK | |
| 63 | Section 2.4.4 header (resum) | p178 | Template | Static. Section number dynamic | — | — | ✅ OK | |
| 64 | Resum intro | p180 | Template | Static | — | — | ✅ OK | |

### 2.4 Taules de Resum d'Assaigs (Secció 2 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 65 | DPSH summary table | t4_r0-rN | Excel + ICGC elevation | `dpsh_tests` from DPSHExtractor + `cota_referencia` | Columns: Punt, Cota inici, Prof. assolida, Rebuig, N.F. | — | ✅ OK | |
| 66 | DPSH test point ID | t4_rN_c0 | Excel columns | DPSHExtractor column headers | "P-1", "P-2", ... | — | ✅ OK | |
| 67 | DPSH cota inici | t4_rN_c1 | ICGC MDT elevation | `cota_referencia` formatted as "+199.00" | — | — | ✅ OK | |
| 68 | DPSH profunditat | t4_rN_c2 | Excel (max depth) | DPSHExtractor `max_depth` per test | — | — | ✅ OK | |
| 69 | DPSH rebuig | t4_rN_c3 | Excel | DPSHExtractor refusal detection | "Si" / "No" | — | ✅ OK | |
| 70 | DPSH nivell freàtic | t4_rN_c4 | Excel / field notes | DPSHExtractor water level | "No detectat" or depth | — | ✅ OK | |
| 71 | Sondeig summary table | t5_r0-rN | Field + sondeig_extracted | `sondeig_tests` list | **Conditional: only if has_sondeig** | — | ✅ OK | |
| 72 | SPT/MA table | t6_r0-rN | SONDEIG.pdf | sondeig_extracted.json SPT data | Columns: Nº assaig, Punt, Prof, N30, Litologia | — | ⚠️ | N30 sometimes missing in audit | |
| 73 | SPT litologia cell | t6_r2_c4 | SONDEIG.pdf | Vision extraction → deepest layer description | Full material description for SPT depth | — | ⚠️ | Verbose vs Eva's concise wording | |
| 74 | Taula 3,4,5 caption | p183 | Template | Static + `table_dpsh_range` | "Taula 3, 4 i 5" (dynamic numbering) | — | ✅ OK | |
| 75 | Cotes reference note | p185 | Template | Static boilerplate | ICGC topographic reference note | — | ✅ OK | |

### 2.5 Assaigs de Laboratori (Secció 2 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 76 | Section 2.5 header | p188 | Template | Static | — | — | ✅ OK | |
| 77 | Lab company (testing) | p190 | Acceptació | user_data (manual) | `lab_testing_company` + `lab_testing_description` | `""` | ❌ Manual | Same issue as #47 | |
| 78 | Lab tests intro | p192 | Template | Static | — | — | ✅ OK | |
| 79 | Lab sample table | t7_r0-r1 | Lab PDF | `lab_sample_id`, `lab_location`, `lab_depth` via `lab_extractor.py` (PyMuPDF + regex) | Mostra: SPT-1, Punt: S-1, Profunditat: -1.0 a -1.6 | — | ✅ OK | Auto-extracted from digital lab PDF. Only 1st test used (`lab_tests[0]`) | |
| 80 | Lab test type | t7_r1_c1 | Lab PDF | `lab_tests_text` via `_extract_test_type()` keyword match | e.g. "Contingut en sulfats solubles UNE 83963:2008" | `"Assaig de laboratori"` | ⚠️ | Keyword-matched (not hardcoded). Only 1 test per report; multiple tests not supported yet | |
| 81 | Taula 6 caption | p194 | Template | Static + `table_lab_num` | — | — | ✅ OK | |

### 2.6 Marc Geològic (Secció 3)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 82 | Section 3 header | p196 | Template | Static | — | — | ✅ OK | |
| 83 | Section 3.1 header | p198 | Template | Static | — | — | ✅ OK | |
| 84 | Cartography intro | p200 | Template | Static boilerplate | — | — | ✅ OK | |
| 85 | Geology paragraphs (for-loop) | p202-p207 | Eva's .docx templates + ICGC | `geology_paragraphs` list from `historia_geologica.lookup_municipality()` + ICGC data | For-loop renders N paragraphs. Bell-Lloc: 6 paragraphs (Depressió Ebre history + ICGC unit) | — | ⚠️ | Fixed: was truncated to 6 fixed slots. Now dynamic for-loop. Wording sometimes differs from Eva's | |
| 86 | ICGC unit specific paragraph | p207 | ICGC 1:50k map | auto(ICGC WMS query) > user_data(expert override) | "afloren els materials de la unitat {icgc_unit_code}, corresponents a {icgc_unit_description}" | `""` | ✅ OK | Last paragraph of geology for-loop | |
| 87 | Geological map figure caption | p226 | Template | Static + `fig_geological_num` ("Figura 5") | — | — | ✅ OK | |

### 2.7 Caracterització dels Materials (Secció 3 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 88 | Section 3.2 header | p229 | Template | Static | — | — | ✅ OK | |
| 89 | Materials intro | p231 | Professional text | `materials_intro` auto-generated | "s'han identificat {N} nivell geotecnic fins a la fondaria investigada" | — | ⚠️ | Wording differs from Eva's ("un sòl nivell de materials des del punt de vista geològic-geotècnic") | |
| 90 | Materials level table | t8_r0_cN | Sondeig + professional | `soil_level_rows` | Nivell + material description (shortened) | — | ⚠️ | `_shorten_material_desc()` for table cells | |
| 91 | Section 3.2.1 header | p239 | Template | Static + level number ("1er Nivell") | — | — | ✅ OK | |
| 92 | Litologia description header | p241 | Template | Static ("Descripció litològica") | — | — | ✅ OK | |
| 93 | Level 1 full description | p243 | Professional judgement | `conclusions_level_1` auto-generated | Multi-paragraph: litho + ICGC unit + depth/thickness + N20 avg + geomech character | — | ⚠️ | Eva's wording notably different. Category C: needs vocabulary file | |
| 94 | Photo materials caption | p246 | Auto-numbered | `photo_materials_num` ("Fotografia 4") | — | — | ✅ OK | Audit notes ref says "Fotografia 5" (different numbering in reference) | |
| 95 | Characterization method note | p248 | Template | Static boilerplate | — | — | ✅ OK | |
| 96 | ICGC unit association | p250 | ICGC + professional | auto(ICGC unit code + description) | "s'associa als materials de la unitat {icgc_unit_code}" | — | ⚠️ | Sometimes mismatches Eva's manual association | |
| 97 | Localització header | p253 | Template | Static ("Localització") | — | — | ✅ OK | |
| 98 | Level depth/thickness | p255 | DPSH + sondeig | auto(DPSHExtractor depth range) | "es detecta superficialment i fins a {depth} m" | — | ✅ OK | |
| 99 | Resistència header | p257 | Template | Static ("Resistència") | — | — | ✅ OK | |
| 100 | Geomech resistance text | p259 | Professional text | auto-generated from soil_type + avg_Nb | "materials de caràcter granular, amb densitat i capacitat portant elevada. Nb mig de {Nb} cops" | — | ⚠️ | Static text diverges from template (36% match in audit) | |

### 2.8 Hidrologia & Permeabilitat (Secció 3 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 101 | Section 3.3 header | p263 | Template | Static | — | — | ✅ OK | |
| 102 | Hidrogeologia superficial | p265-p269 | Template | Static boilerplate (anthropized default) | — | — | ✅ OK | |
| 103 | Hidrogeologia subterrània | p271-p273 | Field observation | Static boilerplate (no water table detected default) | — | — | ✅ OK | Should be conditional on water level | |
| 104 | Section 3.3.3 header | p275 | Template | Static | — | — | ✅ OK | |
| 105 | Permeability intro | p277 | Template | Static | — | — | ✅ OK | |
| 106 | Permeability table | t9_r0-rN | Professional + soil type | `perm_rows` from soil_type lookup | K (m/s) by material type | — | ✅ OK | |
| 107 | Taula 7 caption | p279 | Template | Static + `table_permeability_num` | — | — | ✅ OK | |

### 2.9 Agressivitat (Secció 3 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 108 | Section 3.4 header | p281 | Template | Static | — | — | ✅ OK | |
| 109 | Aggressivity intro | p283-p285 | Template | Static boilerplate (CE-21 reference) | — | — | ✅ OK | |
| 110 | Sulfate value | t10_r1_c1 | Lab PDF (mg/kg) | user_data > auto(lab_extractor via PyMuPDF) | Regex for mg/kg value from lab PDF | `None` | ✅ OK | |
| 111 | Baumann-Gully | t10_r1_c2 | Lab PDF | auto-derived. "---" if sulfate < threshold | — | `"---"` | ✅ OK | |
| 112 | Aggressivity classification | t10_r1_c3 | RD 470/2021 | auto-computed from sulfate_value | "No Agressius" / "Agressius" | — | ✅ OK | |
| 113 | Taula 8 caption | p287 | Template | Static + `table_lab_values_num` | — | — | ✅ OK | |
| 114 | CE-21 footnotes | p289-p291 | Template | Static boilerplate | — | — | ✅ OK | |

### 2.10 Excavabilitat (Secció 3 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 115 | Section 3.5 header | p294 | Template | Static | — | — | ✅ OK | |
| 116 | Excavability paragraph | p296-p298 | Professional text + building_type | auto-generated | "es preveu la construcció d'una estructura en {building_structure_desc}" | — | ⚠️ | Text quality depends on building type detection | |

### 2.11 Sísmica (Secció 3 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 117 | Section 3.6 header | p303 | Template | Static (section number dynamic) | — | — | ✅ OK | |
| 118 | Seismic intro paragraphs | p305-p307 | Template | Static boilerplate (NCSE-02 reference) | — | — | ✅ OK | |
| 119 | Municipality + Ab value | p309-p311 | NCSE-02 municipality lookup | auto-computed from municipality | "en el municipi de {municipality}, Ab < 0,04g" | — | ✅ OK | |
| 120 | Seismic exemption note | — | NCSE-02 | **NOT IMPLEMENTED** | Should add: "no és obligatòria quan Ac < 0,08g" | — | ❌ Missing | Flagged in audit as [FALTA A L'INFORME GENERAT] | |
| 121 | Ac formula paragraphs | p315-p329 | Template | Static boilerplate (formulas) | — | — | ✅ OK | |
| 122 | Seismic coefficient table | t11_r0-rN | Soil levels + CTE | `seismic_rows` auto-computed | Columns: Nivells, Tipus terreny, Gruix, Coef. C | — | ✅ OK | |
| 123 | Taula 9 caption | p336-p337 | Template | Static + footnote | — | — | ✅ OK | |
| 124 | Seismic closing note | p339 | Template | Static boilerplate | — | — | ✅ OK | |

### 2.12 Radó (Secció 3 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 125 | Section 3.7 header | p342 | Template | Static (section number dynamic) | — | — | ✅ OK | |
| 126 | Radon intro/legal | p344-p352 | Template | Static boilerplate (DB HS-6 reference) | — | — | ✅ OK | |
| 127 | Radon reference level | p354 | Template | Static ("300 Bq/m³") | — | — | ✅ OK | |
| 128 | Radon solutions (zona 1/2) | p358-p372 | Template | Static boilerplate | — | — | ✅ OK | |
| 129 | Municipality radon zone | p376 | CSN map + municipality | auto from municipality lookup | "pertany a la ZONA {radon_zone}{radon_zone_description}" | — | ✅ OK | |
| 130 | CSN radon potential | p377 | CSN cartography | auto from UTM coordinates | "potencial de radó de {range} Bq/m³ (risc {level})" | — | ⚠️ | New feature. Differs from reference (37% match, expected for new data) | |

### 2.13 Conclusions (Secció 4)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 131 | Section 4 header | p379 | Template | Static | — | — | ✅ OK | |
| 132 | Conclusions intro | p381 | Template | Static boilerplate | — | — | ✅ OK | |
| 133 | Section 4.1 header | p383 | Template | Static ("GEOLOGIA") | — | — | ✅ OK | |
| 134 | Geology conclusions intro | p385 | Auto-generated | `conclusions_levels_detected` | "Es detecta un sol nivell de materials..." | — | ✅ OK | |
| 135 | Level 1 conclusion text | p387 | Professional text | `conclusions_level_1` (same as #93) | Full level description repeated in conclusions | — | ⚠️ | Same wording issues as #93 | |
| 136 | Correlation figure caption | p391 | Template | Static + `fig_correlation_num` ("Figura 6") | — | — | ✅ OK | |
| 137 | Geotechnical table intro | p393 | Template | Static boilerplate | — | — | ✅ OK | |

### 2.14 Taula 10 — Paràmetres Geotècnics

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 138 | Level name (table) | t12_r1_c0 | Sondeig + professional | `_shorten_material_desc()` from sondeig layers | "1er nivell. {shortened_description}" | — | ⚠️ | Shortened vs Eva's manual wording | |
| 139 | Nb (table) | t12_r1_c1 | DPSH + calc | user_override > auto(N20/0.83, formatted "12-R" if refusal) | Formatted with refusal marker | — | ⚠️ | Bell-Lloc: auto="12-R" vs ref="25-R" (Eva override) | |
| 140 | N (table) | t12_r1_c2 | DPSH avg | user_override > auto(avg_N20) | Bell-Lloc: 36 (auto) vs ref: 54 (ambiguous — SPT or N20?) | — | ⚠️ | Bell-Lloc N=54 ambiguity unresolved | |
| 141 | gamma (densitat) | t12_r1_c3 | CTE D.27 | user_override > `nspt_to_gamma_g_cm3(N20, soil_type)` | CTE D.27 lookup. Fixed: 2.0 gran, 1.90 cohes, 2.20 rock | `0.0` | ✅ OK | 0% deviation all projects | |
| 142 | Cohesion | t12_r1_c4 | Hunt (Cu=qu/2) | user_override > rock_detected→1.0 > default 0.0 | Rock if avg_n20≥50 + keywords. Granular default 0.0 | `0.0` | ✅ OK | |
| 143 | phi (angle fricció) | t12_r1_c5 | Schmertmann (1970) | user_override > `nspt_to_phi(Nb, soil_type)` | **Uses Nb = N20/0.83**. Factor n by grain size | `0.0` | ✅ OK | +0.5% to +4% deviation | |
| 144 | E (mòdul deformació) | t12_r1_c6 | CTE + Eva's judgement | user_override > `nspt_to_E_kg_cm2(N20)` | **Uses N20 directly** (not Nb). Multiple formulas | `0.0` | ⚠️ | -28% Bell-Lloc (E=650 carbonatades vs auto ~469) | |
| 145 | Nb conversion | — | Dapena, Lacasa & García (2000) | `N20 / 0.83` | Applied for phi (Schmertmann). E uses N20 directly | — | ✅ OK | |
| 146 | Taula 10 caption | p400 | Template | Static + `table_soil_chars_num` | — | — | ✅ OK | |
| 147 | Taula 10 footnotes | p402-p405 | Template | Static boilerplate (units, methodology notes) | — | — | ✅ OK | |

### 2.15 Hidrogeologia & Agressivitat Conclusions (Secció 4 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 148 | Section 4.2 header | p408 | Template | Static | — | — | ✅ OK | |
| 149 | Water conclusion paragraphs | p410-p414 | Template + field obs | Static boilerplate (same as §3.3) | Repeated from hydrology section | — | ✅ OK | |
| 150 | Aggressivity conclusion | p416 | Lab results + RD 470/2021 | `conclusions_aggressivity_statement` | "El contingut en sulfats del terreny es de {sulfate} mg/kg. El terreny es classifica com a {class}" | — | ✅ OK | Differs from reference wording (41% match) but data correct | |

### 2.16 Fonamentació (Secció 4 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments | To do |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------------|------|
| 151 | Section 4.3 header | p419 | Template | Static | — | — | ✅ OK | |
| 152 | Foundation intro | p421 | Template + building_type | auto-generated | "es preveu la construcció d'una estructura en {building_structure_desc}" | — | ✅ OK | |
| 153 | Foundation type recommendation | p423 | Professional judgement | auto-generated from soil_levels + geomech | "fonamentació superficial mitjançant sabates ... en els materials del primer nivell" | — | ⚠️ | Text mentions "primer i segon nivell" even with 1 level | |
| 154 | Foundation depth note | p425 | Professional + DPSH | auto-generated | "encastada entre 30-40 cm en els materials del {level} sanejat" | — | ✅ OK | |
| 155 | Qa value | p427 | Terzaghi-Peck (Nb/12) + cap | `terzaghi_calculator.py` | Nb/12 with width correction + depth Fd. Cap: 3.0 soil, 4.5-5.0 rock | `0.0` | ⚠️ | Bell-Lloc: 2.54 (-0.2%). Rubí: 3.50 in ref > cap 3.0 | |
| 156 | Settlement | p429 | Schmertmann method | `Es = 2.5 × Nb` (square), `3.5 × Nb` (strip) | Es_override from wizard takes precedence | `0.0` | ✅ OK | Bell-Lloc: 1.18 cm (+2.3%) | |
| 157 | K30 (balast) | p431 | E/75 or E/60 | auto-computed from E and soil_type | "K30= {k30_value} kg/cm³" | `0.0` | ✅ OK | +4.2% deviation (within tolerance) | |
| 158 | Disclaimer paragraph | p432 | Template | Static boilerplate | G3DT contact info | — | ✅ OK | |
| 159 | Expedient number | p435 | Folder convention | `expedient` from folder_name parsing | — | — | ✅ OK | |
| 160 | Signature date | p438 | Manual (Eva signs) | `data_signatura_text` from user_data or today | "Els Omells de Na Gaia, {date}" | today | ✅ OK | |
| 161 | Signatory block | t13_r1_c0 | Template | Static ("Eva Vázquez Marcet, Geòloga col 4302") | — | — | ✅ OK | |
| 162 | Es_settlement | — | Professional judgement | user_override > auto(2.5 × Nb) | Wizard expert override field. Auto-prefilled | — | ✅ OK | Back-engineered: ~125 ≈ 2.5×Nb | |
| 163 | Ka / Kp (empentes) | — | Rankine / Coulomb | Computed from phi | **Conditional: only if has_basement OR has_retaining_walls**. Not in Bell-Lloc | — | ⚠️ | Not tested (no project has basement) | |

---

## 3. Per-Project Status Matrix

Rows = key items from §2 (excluding static template). Status: ✅ = matches reference, ⚠️ = minor deviation, ❌ = wrong/missing, ➖ = N/A, `?` = not tested.

| # | Item | Elem ID | Bell-Lloc | Rubí | Linyola | Castellar |
|---|------|---------|:---------:|:----:|:-------:|:---------:|
| 4 | Client name | p047 | ✅ | ✅ | ? | ? |
| 7 | Antecedents (arch+client+type) | p054 | ✅ | ? | ? | ? |
| 9 | Num floors | t0_r0_c1 | ✅ | ? | ? | ? |
| 10 | Sup. parcel·la | t0_r1_c1 | ✅ | ? | ? | ? |
| 11 | Sup. construïda | t0_r2_c1 | ⚠️ "296.88" | ? | ? | ? |
| 13 | Location paragraph | p060 | ⚠️ | ? | ? | ? |
| 14 | Fig 1+2 image | t1_r0_c0 | ✅ | ? | ? | ? |
| 19 | CTE building class | t2_r0_c1 | ✅ | ✅ | ? | ? |
| 20 | CTE soil class | t2_r1_c1 | ✅ | ✅ | ? | ? |
| 26 | Field work dates | p089 | ✅ | ? | ? | ? |
| 31 | Adjacent north | p102 | ⚠️ | ? | ? | ? |
| 32 | Adjacent south | p103 | ⚠️ | ? | ? | ? |
| 33 | Adjacent east | p104 | ⚠️ | ? | ? | ? |
| 34 | Adjacent west | p105 | ⚠️ | ? | ? | ? |
| 36 | Access description | p109 | ⚠️ | ? | ? | ? |
| 37 | Site description | p111 | ❌ manual | ❌ manual | ❌ manual | ❌ manual |
| 40 | Photo 1 caption | p117 | ✅ | ? | ? | ? |
| 43 | DPSH test count | p124 | ✅ | ✅ | ✅ | ✅ |
| 47 | Lab company | p129 | ❌ manual | ❌ manual | ❌ manual | ❌ manual |
| 65 | DPSH summary table | t4 | ✅ | ✅ | ✅ | ✅ |
| 71 | Sondeig summary table | t5 | ✅ | ➖ | ? | ? |
| 72 | SPT/MA table | t6 | ⚠️ | ➖ | ? | ? |
| 85 | Geology paragraphs | p202-p207 | ⚠️ wording | ? | ? | ? |
| 86 | ICGC unit paragraph | p207 | ✅ | ? | ? | ? |
| 89 | Materials intro | p231 | ⚠️ wording | ? | ? | ? |
| 90 | Materials level table | t8 | ⚠️ | ? | ? | ? |
| 93 | Level 1 description | p243 | ⚠️ wording | ? | ? | ? |
| 100 | Geomech resistance text | p259 | ⚠️ 36% | ? | ? | ? |
| 106 | Permeability table | t9 | ✅ | ? | ? | ? |
| 110 | Sulfate value | t10_r1_c1 | ✅ | ? | ? | ? |
| 112 | Aggressivity class | t10_r1_c3 | ✅ | ? | ? | ? |
| 119 | Municipality + Ab | p309-p311 | ✅ | ? | ? | ? |
| 120 | Seismic exemption | — | ❌ Missing | ? | ? | ? |
| 122 | Seismic coeff table | t11 | ✅ | ? | ? | ? |
| 129 | Radon zone | p376 | ✅ | ? | ? | ? |
| 130 | CSN radon potential | p377 | ⚠️ new | ? | ? | ? |
| 134 | Geology conclusions | p385 | ✅ | ? | ? | ? |
| 135 | Level 1 conclusion | p387 | ⚠️ wording | ? | ? | ? |
| 138 | Level name (table 10) | t12_r1_c0 | ⚠️ | ? | ? | ? |
| 139 | Nb (table 10) | t12_r1_c1 | ⚠️ "12-R" vs "25-R" | ? | ? | ? |
| 140 | N (table 10) | t12_r1_c2 | ⚠️ 36 vs 54 | ? | ? | ? |
| 141 | gamma | t12_r1_c3 | ✅ 0% | ✅ 0% | ✅ 0% | ✅ 0% |
| 142 | Cohesion | t12_r1_c4 | ✅ | ✅ | ✅ | ✅ |
| 143 | phi | t12_r1_c5 | ✅ +1.5% | ✅ +0.5% | ⚠️ +4% | ✅ 0% |
| 144 | E | t12_r1_c6 | ❌ -28% (469 vs 650) | ✅ +4.2% | ⚠️ +14.2% | ✅ 0% |
| 150 | Aggressivity conclusion | p416 | ✅ | ? | ? | ? |
| 155 | Qa | p427 | ✅ -0.2% | ⚠️ -14.3% | ✅ +3.1% | ✅ 0% |
| 156 | Settlement | p429 | ✅ +2.3% | ? | ➖ | ➖ |
| 157 | K30 | p431 | ✅ +4.2% | ✅ +4.2% | ➖ | ✅ +4.1% |
| 159 | Expedient | p435 | ✅ | ✅ | ✅ | ✅ |
| 160 | Signature date | p438 | ✅ | ✅ | ✅ | ✅ |

**Legend:**
- `?` = Not tested — project lacks user_data.json or hasn't gone through full pipeline
- `➖` = Not applicable for this project type (e.g., no sondeig in Rubí)
- Deviation %: from `docs/ANALISI-SETTLEMENT-BACK-ENGINEERING.md` and MEMORY.md

---

## 4. Change Log — Key Modifications

Most recent first. Only changes that directly affected how an item is retrieved or calculated.

| Date | Commit | Items affected | What changed | Why |
|------|--------|---------------|-------------|-----|
| 2026-03-14 | `8045b18` | #13 location (p060), #11 sup. construïda (t0_r2_c1) | Split combined floor_surfaces labels ("PB+PP"), fix municipality priority chain | Combined labels caused wrong area distribution; municipality fell through to folder name |
| 2026-03-14 | `6f4be97` | #11 sup. construïda (t0_r2_c1) | Added floor_surfaces to PLANOL_EXTRACTION_PROMPT | Vision wasn't extracting per-floor areas |
| 2026-03-14 | `8af5e90` | #14 Fig 1+2 (t1_r0_c0) | Figure 1 from situation plan left crop (cadastral maps) | Was using full page; Eva confirmed left 38% has the cadastral maps |
| 2026-03-13 | — | #89 materials intro (p231), #93 level desc (p243) | Sondeig annex priority over field sheet; dedicated prompt | Eva: levels come from "Unitat litològica" column in formatted annex, not from material count |
| 2026-03-02 | — | #85 geology (p202-p207), #93 level desc (p243), #90 materials table (t8) | Fixed 3 critical bugs: for-loop truncation, layer filter guard, deepest layer for material | 73% of templates were truncated by fixed 6-slot geology. See ANALISI-ERRORS-AUDIT-2026-03-02.md |
| 2026-02-26 | — | #141-#144 all geomech (t12), #155 Qa (p427), #156-#157 settlement/K30 (p429,p431) | Implemented Eva's confirmed methodology: Schmertmann phi, Nb/0.83, Es=2.5×Nb, K30=E/75 | Eva's email answers. See RESPOSTA-EVA-PREGUNTES-CALCULS.md |
| 2026-02-26 | — | #144 E (t12_r1_c6) | E uses N20 directly (not Nb) for CTE D.23 lookup | Rubí fix: avoids bracket-crossing when N20=40 |
| 2026-02-26 | — | #156 settlement (p429), #162 Es_settlement | Schmertmann Es = 2.5×Nb (square), 3.5×Nb (strip) replaces Robertson qc path | Back-engineering: Es_implied ≈ 125 ≈ 2.5×Nb consistent across projects |

---

## 5. Open Issues & Next Steps

### Items requiring Eva's standardized input

These items can't be reliably automated and need Eva to provide data in a consistent format/location:

| Item | Elem ID | What Eva needs to provide | Suggested standardization |
|------|---------|--------------------------|--------------------------|
| Lab company (#47/#77) | p129, p190 | Company name + alias | Field in DADES CLIENT.txt or standardized lab header |
| Site description (#37) | p111 | "Solar urbanitzat..." text | DTE.txt with structured fields, or wizard-only |
| Access description (#36) | p109 | "Des del carrer..." text | DTE.txt ACCES field (already partially used) |
| E override (#144) | t12_r1_c6 | When carbonated or special soil | Wizard expert override (already exists). Needs Eva training |
| Material wording (#93) | p243 | Professional vocabulary | Build vocabulary file from 10+ signed reports |

### Items requiring code work

| Priority | Item | Elem ID | What's needed |
|----------|------|---------|-------------|
| HIGH | Seismic exemption (#120) | after p311 | Add exemption paragraph for low-seismicity municipalities |
| HIGH | Rubí Qa > cap (#155) | p427 | Investigate why Eva's reference has Qa=3.50 > cap 3.0 |
| MEDIUM | Bell-Lloc N=54 (#140) | t12_r1_c2 | Clarify with Eva: is this SPT (borehole) or N20? |
| MEDIUM | E for carbonated soils (#144) | t12_r1_c6 | Rule for when to push E above CTE base |
| MEDIUM | Resistance text (#100) | p259 | Only 36% template match. Review auto-generated wording |
| LOW | Slope stability (#163) | — | Hoek & Bray abacs implementation |
| LOW | Lab auto-detection (#47) | p129 | Parse lab company from PDF header |

### Testing gaps

| What | Why untested | How to fix |
|------|-------------|-----------|
| Linyola full pipeline | No user_data.json | Run full wizard pipeline, save user_data |
| Castellar full pipeline | No user_data.json | Run full wizard pipeline, save user_data |
| Plànol vision (non-Bell-Lloc) | Only Bell-Lloc has A.01.pdf | Get sample A.01.pdf for at least one more project |
| Multi-photo numbering | Castellar has 4+ photos | Test with Castellar after creating user_data |
| Earth pressure sections | No project has basement/retaining walls | Create synthetic test case or find real project |

---

## References

- `docs/ANALISI-AUDIT-BELLLLOC-POST-FIXES.md` — Full Bell-Lloc audit analysis
- `docs/ANALISI-ERRORS-AUDIT-2026-03-02.md` — Root cause of 3 critical bugs
- `docs/ANALISI-SETTLEMENT-BACK-ENGINEERING.md` — Settlement Es analysis
- `docs/RESPOSTA-EVA-PREGUNTES-CALCULS.md` — Eva's methodology answers
- `docs/PLA-SONDEIG-ANNEX-PRIORITAT.md` — Sondeig annex priority plan
- `.claude/projects/.../memory/MEMORY.md` — Deviation matrix, Eva's values
