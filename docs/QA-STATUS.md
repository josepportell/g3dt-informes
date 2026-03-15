# G3DT Report QA Status

Last updated: 2026-03-15

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

Items ordered by appearance in the generated report. Element IDs from the audit system (`pNNN` = paragraph, `tN_rN_cN` = table cell).

### 2.1 Portada & Dades Generals

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 1 | Client name | p001-p003 | Acceptació / DTE | user_data > content_discovery > planol_vision > DADES CLIENT.txt | First non-empty. Auto uppercases, SL→S.L. | `""` | ✅ OK | |
| 2 | Expedient | p004 | Folder convention | folder_name parsing (`parse_folder_name()`) | Always from folder `NNNNNNN MUNICIPI` | `""` | ✅ OK | Never fails if folder named correctly |
| 3 | Street address | p005-p008 | Plànol caixetí / DTE | user_data > auto(site_address, adjacent_south) > planol_vision | Priority: street_address > site_address > adjacent_south | `""` | ⚠️ | Vision sometimes misreads abbreviated streets |
| 4 | Municipality | p009 | Plànol / folder | user_data > auto(site_address parsed, pressupost, folder) > planol_vision > folder_name | Folder is last resort. Auto parses after comma in address | `""` | ✅ OK | Fixed: municipality priority chain (commit 8045b18) |
| 5 | Report date | p010 | Manual (Eva signs) | `date.today()` or user_data | Eva enters in wizard | today | ✅ OK | |
| 6 | Architect name | p011 | Plànol caixetí | user_data > planol_vision | Vision reads from A.01.pdf title block | `""` | ⚠️ | Only testable with Bell-Lloc (only project with A.01.pdf) |
| 7 | Architect company | p012 | Plànol / Pressupost | user_data > auto(pressupost PDF) > planol_vision | Pressupost "OBRA:" field | `""` | ⚠️ | Pressupost not always available |

### 2.2 Presentació (Secció 1)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 8 | Building type | p015-p018 | Plànol caixetí | user_data > planol_vision (fuzzy→canonical mapping) | Maps "unifamiliar"→"Habitatge aïllat", etc. | `""` | ✅ OK | Canonical mapping covers common types |
| 9 | Num floors | p019 | Plànol caixetí | user_data > planol_vision → `format_floor_notation()` | Vision reads, formatted as "Pb+1Pp" | `""` | ✅ OK | |
| 10 | Building height | p020 | Plànol cotes | user_data > planol_vision (max_height_m) | Vision reads height cotes from plan | `None` | ⚠️ | Vision confidence varies by plan layout |
| 11 | Superfície parcel·la | p021 | Cadastre / Plànol | user_data > auto(Cadastre WFS geometry) > planol_vision | Cadastral preferred over plan measurement | `""` | ✅ OK | |
| 12 | Superfície construïda | p022 | Plànol cotes | user_data > planol_vision(floor_surfaces aggregation) | Complex: groups sub-zones by floor prefix, sums. Handles "PB+PP" splits | `""` | ⚠️ | Most complex extraction. Combined labels fixed (commit 8045b18) |
| 13 | CTE building class | p025 | CTE table | `classify_building(area, floors, basement)` | CTE lookup. Missing inputs → C-1 safe default | `"C-1"` | ✅ OK | |
| 14 | CTE soil class | p026 | CTE table from N20 | `_determine_soil_class(avg_n20)` | <10→T-3, 10-30→T-2, ≥30→T-1 | `"T-1"` | ✅ OK | |
| 15 | Adjacents (N/S/E/W) | p027-p030 | Cadastre visor / camp | user_data > auto(Cadastre WFS) > adjacents_visor.json | WFS query from UTM coords. Playwright visor as alternative | `""` | ⚠️ | Requires UTM coords. API sometimes returns generic descriptions |

### 2.3 Treballs de Camp (Secció 2)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 16 | Field work dates | p035-p037 | PENETROS.pdf dates | user_data > auto(extract_field_dates from PDFs) | Regex DD/MM/YYYY from PENETROS + lab PDFs | `""` | ⚠️ | Handwritten dates hard to parse with regex |
| 17 | Lab company | p038-p040 | Acceptació | user_data (manual entry) | Eva enters; no auto-detection | `""` | ❌ Manual | Always manual. Could auto-detect from lab PDF header? |
| 18 | Num DPSH tests | p042 | Excel | `DPSHExtractor` column count from DPSH.xls | Counts non-empty columns | `0` | ✅ OK | |
| 19 | DPSH test IDs | p043 | Excel | `DPSHExtractor` → "P-1, P-2, ..." | From Excel column headers | `""` | ✅ OK | |
| 20 | DPSH avg N20 | p044 | Excel + calc | `DPSHExtractor.overall_average_n20` | Arithmetic mean all readings all tests | `0` | ✅ OK | |
| 21 | DPSH table (taula 3+) | t2-t3 | Excel | `dpsh_tests` list from DPSHExtractor | One row per depth, columns per test point | — | ✅ OK | |
| 22 | DPSH validation vs PDF | — | PENETROS.pdf vs Excel | Claude vision reads PENETROS.pdf, compares to Excel | Discrepancy flagging in wizard DPSH tab | — | ✅ OK | |
| 23 | Sondeig presence | p045 | Field campaign | `has_sondeig` from file_mapping.json | FileScanner detects SONDEIG.pdf or *_sondeig.pdf | `False` | ✅ OK | Controls section 2.4.2 inclusion |
| 24 | Sondeig layers | p046-p050 | SONDEIG.pdf (camp) | user_data > sondeig_extracted.json (vision) | Vision reads field sheet or formatted annex. Annex prioritized (has geological levels column) | `[]` | ⚠️ | Low confidence on handwritten sheets. Annex much better |
| 25 | Num geological levels | p051 | Annex formatat column "Unitat litològica" | user_data > vision(sondeig_annex num_geological_levels) | **≠ num materials**. Eva determines by litho unit column. Fallback: 1 | `1` | ✅ OK | Fixed: annex priority over field sheet. See PLA-SONDEIG-ANNEX-PRIORITAT.md |
| 26 | SPT data | p052-p054 | SONDEIG.pdf | sondeig_extracted.json | Vision reads SPT blows from borehole log | — | ⚠️ | Only present if sondeig has SPT. Confidence varies |
| 27 | Foundation depth | — | Professional judgement | user_data > auto(DPSHExtractor refusal analysis) | <1.5m refusal→0.3, <3.0m→0.5, ≥3.0m→1.0 | `0.3` | ✅ OK | Eva often overrides |

### 2.4 Geologia (Secció 3)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 28 | ICGC geology description | p055-p060 | ICGC 1:50k map | user_data(expert override) > auto(ICGC WMS query) | WMS GetFeatureInfo at UTM coords. Returns unit code + description + epoch | `""` | ✅ OK | Requires UTM coords |
| 29 | Geological history | p061-p065 | Eva's .docx templates | auto(`historia_geologica.lookup_municipality()`) | Matches municipality to pre-written template. Tier scoring | `""` | ⚠️ | Coverage depends on template library. Not all municipalities covered |
| 30 | Geology paragraphs (×10) | p066-p075 | Professional text | `geology_paragraphs` list auto-generated | Combines ICGC data + sondeig layers + soil types | — | ⚠️ | Fixed: for-loop in template (was truncated to 6 fixed slots). Wording sometimes differs from Eva's |
| 31 | Elevation / slope | p076-p078 | ICGC MDT | auto(ICGC MDT query at UTM) | Elevation query + slope gradient + aspect | `""` | ✅ OK | |
| 32 | Site description | p079 | Eva's field notes | user_data (manual entry) | No auto-detection | `""` | ❌ Manual | Could parse from DTE.txt? |
| 33 | Access description | p080 | Eva's field notes | user_data > auto(content_discovery ACCES field) | Searches field prep documents | `""` | ⚠️ | Rarely auto-detected |

### 2.5 Materials (Secció 3 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 34 | Material descriptions | p082-p090 | Professional judgement | Auto-generated from sondeig_layers | Uses deepest layer (bearing stratum) for merged levels. `_shorten_material_desc()` for tables | — | ⚠️ | Eva's wording differs. Needs vocabulary file (Category C deferred) |
| 35 | Soil level table | t5-t6 | Sondeig + professional | `soil_level_rows` from build_report_data() | Combines vision layers + auto geomech params | — | ⚠️ | Formatting depends on num_soil_levels accuracy |

### 2.6 Paràmetres Geotècnics (Secció 3 cont.)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 36 | gamma (densitat) | t7_rN_c2 | CTE D.27 | user_override > `nspt_to_gamma_g_cm3(N20, soil_type)` | CTE D.27 lookup by soil type. Fixed: 2.0 gran, 1.90 cohes, 2.20 rock | `0.0` | ✅ OK | 0% deviation all projects |
| 37 | phi (angle fricció) | t7_rN_c3 | Schmertmann (1970) | user_override > `nspt_to_phi(Nb, soil_type)` | **Uses Nb = N20/0.83**. Schmertmann via CTE 4.1. Factor n by grain size | `0.0` | ✅ OK | +0.5% to +4% deviation (acceptable) |
| 38 | E (mòdul deformació) | t7_rN_c4 | CTE + Eva's judgement | user_override > `nspt_to_E_kg_cm2(N20)` | **Uses N20 directly** (not Nb) to avoid bracket-crossing. Multiple formulas | `0.0` | ⚠️ | -28% Bell-Lloc (E=650 for carbonatades, auto gives ~450). Eva always reviews |
| 39 | Cohesion | t7_rN_c5 | Hunt (Cu=qu/2) | user_override > rock_detected→1.0 > default 0.0 | Rock if avg_n20≥50 + keywords. Granular default 0.0 | `0.0` | ✅ OK | Rock detection triggers Qa cap correctly |
| 40 | Nb conversion | — | Dapena, Lacasa & García (2000) | `N20 / 0.83` | Applied for phi (Schmertmann). E uses N20 directly | — | ✅ OK | |
| 41 | K30 (balast) | t7_rN_c6 | E/75 or E/60 | `E/75` (granular), `E/60` (rock) | Based on E value and soil type | `0.0` | ✅ OK | +4.2% deviation (within tolerance) |

### 2.7 Capacitat Portant & Assentament (Secció 4)

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 42 | Qa (capacitat portant) | p095-p098 | Terzaghi-Peck (Nb/12) + cap | `terzaghi_calculator.py` | Nb/12 with width correction + depth factor Fd. Cap: 3.0 soil, 4.5-5.0 rock (cohesion≥0.5) | `0.0` | ⚠️ | Rubí Qa=3.50 in reference > cap 3.0 (unexplained). -0.2% to +3.1% others |
| 43 | Settlement | p099-p101 | Schmertmann method | `Es = 2.5 × Nb` (square), `3.5 × Nb` (strip) | Es_override from wizard takes precedence. Prefilled as 2.5×Nb | `0.0` | ✅ OK | +1% to +8% deviation. Eva adjusts Es in review |
| 44 | Es_settlement | — | Professional judgement | user_override > auto(2.5 × Nb) | Wizard expert override field. Auto-prefilled | — | ✅ OK | Back-engineered: ~125 ≈ 2.5×Nb consistent across projects |
| 45 | Ka / Kp (empentes) | p102-p104 | Rankine / Coulomb | Computed from phi | Only if `include_earth_pressure` (basement or retaining walls) | — | ⚠️ | Conditional section. Not tested with all projects |

### 2.8 Sísmica, Radó, Agressivitat

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 46 | Seismic params | p106-p108 | NCSE-02 | Auto-computed from municipality + soil class | Municipality lookup for ab. Seismic exemption paragraph: **not implemented** | — | ⚠️ | Missing: exemption text for low-seismicity zones |
| 47 | Radon zone | p110 | CSN map | Auto from municipality or UTM | CSN radon zone lookup | — | ⚠️ | Coverage depends on zone database |
| 48 | Sulfate (agressivitat) | p112-p114 | Lab PDF (mg/kg) | user_data > auto(lab_extractor from PDF via PyMuPDF) | Regex for mg/kg value. Baumann + classification auto-derived | `None` | ✅ OK | RD 470/2021 classification |

### 2.9 Figures & Fotos

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 49 | Figure 1 (cadastre) | fig_cadastre | Plànol de situació annex | Left ~38% crop of `situation_plan` PDF role | PyMuPDF render + crop. Works for A3 (1191×842pt) and A4 (842×595pt) | — | ✅ OK | Confirmed by Eva. FreeHand template consistent |
| 50 | Figure 2 (aerial) | fig_aerea | ICGC ortofoto + parcel | ICGC orthophoto WMS + parcel overlay | Fallback: clip_regions → ICGC parcel → plain orthophoto | — | ⚠️ | Requires UTM + parcel geometry |
| 51 | Figure 3 (plànol) | fig_main_plan | A.01.pdf full render | Full-page PyMuPDF render of `architect_plan` role | NOT the "amb punts" version | — | ✅ OK | |
| 52 | Photos numbering | photo_* | Eva's field photos | Auto-numbered from file_mapping photo roles | site, dpsh, sondeig, materials photos | — | ⚠️ | Castellar has 4+ photos, numbering logic needs testing |
| 53 | Figure/table numbering | fig_*_num, table_*_num | Sequential | `_build_numbering_context()` | Dynamic based on has_sondeig, conditionals | — | ✅ OK | Adjusts when sondeig absent |

### 2.10 Conditional Sections

| # | Item | Elem ID(s) | Eva's source | Our source(s) | Retrieval criteria | Default | Status | Comments |
|---|------|-----------|-------------|---------------|-------------------|---------|--------|----------|
| 54 | is_sloped | — | Field observation | user_data > auto(ICGC MDT slope > 15%) | ICGC gradient query at UTM | `False` | ✅ OK | |
| 55 | has_sondeig | — | Field campaign | FileScanner role detection | Detects SONDEIG.pdf or *_sondeig.pdf | `False` | ✅ OK | Controls section 2.4.2, taula 4, SPT, figure numbering |
| 56 | include_earth_pressure | — | has_basement OR retaining_walls | Computed from user_data booleans | Section 3.2 Empentes | `False` | ✅ OK | |
| 57 | include_slope_stability | — | is_sloped | From slope detection | Section 4.5 Estabilitat de talussos | `False` | ⚠️ | Hoek & Bray abacs — not fully implemented |
| 58 | Dynamic section numbers | section_*_num | N/A | `_build_numbering_context()` | Sections shift based on conditionals (sondeig, expansivity, slope, earth pressure) | — | ✅ OK | |

---

## 3. Per-Project Status Matrix

Rows = items from §2 above. Status: ✅ = matches reference or correct, ⚠️ = minor deviation or needs review, ❌ = wrong/missing, ➖ = N/A for this project, `?` = not tested (no user_data).

| # | Item | Bell-Lloc | Rubí | Linyola | Castellar |
|---|------|:---------:|:----:|:-------:|:---------:|
| 1 | Client name | ✅ | ✅ | ? | ? |
| 2 | Expedient | ✅ | ✅ | ✅ | ✅ |
| 3 | Street address | ✅ | ✅ | ? | ? |
| 4 | Municipality | ✅ | ✅ | ? | ? |
| 5 | Report date | ✅ | ✅ | ✅ | ✅ |
| 6 | Architect name | ✅ | ➖ no A.01 | ➖ no A.01 | ➖ no A.01 |
| 7 | Architect company | ✅ | ? | ? | ? |
| 8 | Building type | ✅ | ? | ? | ? |
| 9 | Num floors | ✅ | ? | ? | ? |
| 10 | Building height | ✅ | ➖ | ➖ | ➖ |
| 11 | Sup. parcel·la | ✅ | ? | ? | ? |
| 12 | Sup. construïda | ⚠️ "280+86" | ? | ? | ? |
| 13 | CTE building class | ✅ | ✅ | ? | ? |
| 14 | CTE soil class | ✅ | ✅ | ? | ? |
| 15 | Adjacents | ✅ | ? | ? | ? |
| 16 | Field work dates | ✅ | ? | ? | ? |
| 17 | Lab company | ❌ manual | ❌ manual | ❌ manual | ❌ manual |
| 18 | Num DPSH tests | ✅ | ✅ | ✅ | ✅ |
| 19 | DPSH test IDs | ✅ | ✅ | ✅ | ✅ |
| 20 | DPSH avg N20 | ✅ | ✅ | ✅ | ✅ |
| 21 | DPSH table | ✅ | ✅ | ✅ | ✅ |
| 22 | DPSH validation | ✅ | ✅ | ? | ✅ |
| 23 | has_sondeig | ✅ | ✅ (false) | ? | ✅ |
| 24 | Sondeig layers | ⚠️ wording | ➖ | ? | ? |
| 25 | Num geological levels | ✅ (1) | ➖ | ? | ? |
| 26 | SPT data | ⚠️ | ➖ | ? | ? |
| 27 | Foundation depth | ✅ | ✅ | ? | ? |
| 28 | ICGC geology | ✅ | ? | ? | ? |
| 29 | Geological history | ⚠️ | ? | ? | ? |
| 30 | Geology paragraphs | ⚠️ wording | ? | ? | ? |
| 31 | Elevation / slope | ✅ | ? | ? | ? |
| 32 | Site description | ❌ manual | ❌ manual | ❌ manual | ❌ manual |
| 33 | Access description | ⚠️ | ? | ? | ? |
| 34 | Material descriptions | ⚠️ wording | ? | ? | ? |
| 35 | Soil level table | ⚠️ | ? | ? | ? |
| 36 | gamma | ✅ 0% | ✅ 0% | ✅ 0% | ✅ 0% |
| 37 | phi | ✅ +1.5% | ✅ +0.5% | ⚠️ +4% | ✅ 0% |
| 38 | E | ❌ -28% | ✅ +4.2% | ⚠️ +14.2% | ✅ 0% |
| 39 | Cohesion | ✅ | ✅ | ✅ | ✅ |
| 40 | Nb conversion | ✅ | ✅ | ✅ | ✅ |
| 41 | K30 | ✅ +4.2% | ✅ +4.2% | ➖ | ✅ +4.1% |
| 42 | Qa | ✅ -0.2% | ⚠️ -14.3% | ✅ +3.1% | ✅ 0% |
| 43 | Settlement | ✅ +2.3% | ? | ➖ | ➖ |
| 44 | Es_settlement | ✅ | ? | ➖ | ➖ |
| 45 | Ka / Kp | ➖ | ➖ | ? | ? |
| 46 | Seismic params | ⚠️ no exemption | ? | ? | ? |
| 47 | Radon zone | ✅ | ? | ? | ? |
| 48 | Sulfate | ✅ | ? | ? | ? |
| 49 | Fig 1 (cadastre) | ✅ | ? | ? | ? |
| 50 | Fig 2 (aerial) | ⚠️ | ? | ? | ? |
| 51 | Fig 3 (plànol) | ✅ | ➖ | ➖ | ➖ |
| 52 | Photo numbering | ✅ | ? | ? | ⚠️ 4+ photos |
| 53 | Fig/table numbering | ✅ | ✅ | ? | ? |
| 54-58 | Conditionals | ✅ | ✅ | ? | ? |

**Legend:**
- `?` = Not tested — project lacks user_data.json or hasn't gone through full pipeline
- `➖` = Not applicable for this project type (e.g., no sondeig in Rubí)
- Deviation %: from `docs/ANALISI-SETTLEMENT-BACK-ENGINEERING.md` and MEMORY.md

---

## 4. Change Log — Key Modifications

Most recent first. Only changes that directly affected how an item is retrieved or calculated.

| Date | Commit | Items affected | What changed | Why |
|------|--------|---------------|-------------|-----|
| 2026-03-14 | `8045b18` | #4 municipality, #12 sup. construïda | Split combined floor_surfaces labels ("PB+PP"), fix municipality priority chain | Combined labels caused wrong area distribution; municipality fell through to folder name |
| 2026-03-14 | `6f4be97` | #12 sup. construïda | Added floor_surfaces to PLANOL_EXTRACTION_PROMPT | Vision wasn't extracting per-floor areas |
| 2026-03-14 | `8af5e90` | #49 Fig 1 | Figure 1 from situation plan left crop (cadastral maps) | Was using full page; Eva confirmed left 38% has the cadastral maps |
| 2026-03-13 | — | #25 num geological levels | Sondeig annex priority over field sheet; dedicated prompt | Eva: levels come from "Unitat litològica" column in formatted annex, not from material count |
| 2026-03-02 | — | #30 geology paragraphs, #24 sondeig layers, #34 materials | Fixed 3 critical bugs: for-loop truncation, layer filter guard, deepest layer for material | 73% of templates were truncated by fixed 6-slot geology. See ANALISI-ERRORS-AUDIT-2026-03-02.md |
| 2026-02-26 | — | #36-#44 all geomech | Implemented Eva's confirmed methodology: Schmertmann phi, Nb/0.83, Es=2.5×Nb, K30=E/75 | Eva's email answers. See RESPOSTA-EVA-PREGUNTES-CALCULS.md |
| 2026-02-26 | — | #38 E | E uses N20 directly (not Nb) for CTE D.23 lookup | Rubí fix: avoids bracket-crossing when N20=40 |
| 2026-02-26 | — | #43-#44 settlement | Schmertmann Es = 2.5×Nb (square), 3.5×Nb (strip) replaces Robertson qc path | Back-engineering: Es_implied ≈ 125 ≈ 2.5×Nb consistent across projects |

---

## 5. Open Issues & Next Steps

### Items requiring Eva's standardized input

These items can't be reliably automated and need Eva to provide data in a consistent format/location:

| Item | What Eva needs to provide | Suggested standardization |
|------|--------------------------|--------------------------|
| Lab company (#17) | Company name + alias | Field in DADES CLIENT.txt or standardized lab header |
| Site description (#32) | "Solar urbanitzat..." text | DTE.txt with structured fields, or wizard-only |
| Access description (#33) | "Des del carrer..." text | DTE.txt ACCES field (already partially used) |
| E override (#38) | When carbonated or special soil | Wizard expert override (already exists). Needs Eva training |
| Material wording (#34) | Professional vocabulary | Build vocabulary file from 10+ signed reports |

### Items requiring code work

| Priority | Item | What's needed |
|----------|------|-------------|
| HIGH | Seismic exemption (#46) | Add exemption paragraph for low-seismicity municipalities |
| HIGH | Rubí Qa > cap (#42) | Investigate why Eva's reference has Qa=3.50 > cap 3.0 |
| MEDIUM | Bell-Lloc N=54 (#26) | Clarify with Eva: is this SPT (borehole) or N20? |
| MEDIUM | E for carbonated soils (#38) | Rule for when to push E above CTE base |
| LOW | Slope stability (#57) | Hoek & Bray abacs implementation |
| LOW | Lab auto-detection (#17) | Parse lab company from PDF header |

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
