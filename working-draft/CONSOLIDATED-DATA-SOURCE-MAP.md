# G3DT Report Automation: Consolidated Data Source Map
## Complete Variable-to-Source Reference

**Date:** 2026-02-02
**Based on:** Section 1, 2, 4 detailed mappings + EXPLICACIÓ DETALLS.docx analysis
**Sample:** 4001612 Bell-Lloc d'Urgell

---

## Executive Summary

| Category | Sources | Variables | Automation |
|----------|---------|-----------|------------|
| Project ID | Folder name | 2 | ✅ Easy |
| Client data | DADES CLIENT.txt | 5 | ✅ Easy |
| Test data | DPSH.xls | 12+ | ✅ Easy |
| Lab data | comanda laboratori.xls, LAB-SIG.pdf | 8 | ✅ Medium |
| Calculations | Base de càlcul formulas | 6 | ✅ Medium |
| Location | ICGC viewer, Cadastre | 4 | ⚠️ Manual/API |
| Observations | Field notes, Google | 10+ | ❌ Manual |
| Geology text | Zone templates (server) | Variable | ⚠️ Need templates |
| Photos | FOTOGRAFIES/ folder | Variable | ✅ Easy |

**Bottom line:** ~60% of variables can be automated from files. ~25% need a data entry form. ~15% require zone-specific templates from client's server.

---

## 1. Primary Data Sources

### 1.1 Project Folder Structure

```
{expedient} {POBLACIO}/
├── ACCEPTACIO/
│   └── DADES CLIENT.txt          ← Client info
├── ANNEXES/
│   └── {expedient}_DPSH.xls      ← Test data (CRITICAL)
├── FOTOGRAFIES/
│   ├── DPSH/                     ← Test photos
│   └── SONDEIG/                  ← Drilling photos
├── PDF/ANNEXES/
│   └── LAB-SIG.pdf               ← Lab results
├── {year}.{num}/
│   └── DADES PER ANAR A CAMP.xlsx ← Field planning
└── comanda laboratori_{exp}_{pop}.xls ← Lab request
```

### 1.2 Source Priority Matrix

| Source | Reliability | Access | Variables |
|--------|-------------|--------|-----------|
| **DPSH.xls** | ✅ High | ✅ Direct | N₂₀, depths, water level |
| **DADES CLIENT.txt** | ✅ High | ✅ Direct | Client name, NIF, contact |
| **Folder name** | ✅ High | ✅ Direct | Expedient, municipality |
| **comanda laboratori.xls** | ✅ High | ✅ Direct | Lab tests requested |
| **LAB-SIG.pdf** | ✅ High | ⚠️ Parse PDF | Sulfates, Lambe, granulometry |
| **ICGC viewer** | ✅ High | ⚠️ Manual/API | Coordinates, geology map |
| **Budget email** | ⚠️ Medium | ❌ Manual | Architect, building specs |
| **Field observation** | ⚠️ Medium | ❌ Manual | Site description |
| **Zone templates** | ✅ High | ❓ Need access | Geological text |

---

## 2. Complete Variable Inventory

### 2.1 Project Identification (2 vars)

| Variable | Example | Source | Extraction |
|----------|---------|--------|------------|
| `expedient` | `4001612` | Folder name | Split on space, take first |
| `municipality` | `Bell-Lloc d'Urgell` | Folder name | Split on space, take rest |

```python
# Extraction
folder = "4001612 BELL-LLOC"
expedient = folder.split()[0]  # "4001612"
municipality = " ".join(folder.split()[1:])  # "BELL-LLOC"
```

### 2.2 Client Data (5 vars)

| Variable | Example | Source | Line |
|----------|---------|--------|------|
| `client_name` | `RAMON MITJANA SL` | DADES CLIENT.txt | 4 |
| `client_nif` | `B25771726` | DADES CLIENT.txt | 4 (after name) |
| `client_representative` | `RAMON MITJANA GRÍFOL` | DADES CLIENT.txt | 6 |
| `client_address` | `Carrer Doctor Torrebadella 8, 25220 BELL-LLOC` | DADES CLIENT.txt | 7-8 |
| `client_phone` | `696 990 400` | DADES CLIENT.txt | 9 |
| `client_email` | `mangelspenella@gmail.com` | DADES CLIENT.txt | 10 |

```python
# DADES CLIENT.txt format:
# Line 4: COMPANY NAME       NIF
# Line 6: Representative name
# Line 7-8: Address
# Line 9: T. phone
# Line 10: E. email
```

### 2.3 Building Data (8 vars) - FROM DATA ENTRY

| Variable | Example | Source | Notes |
|----------|---------|--------|-------|
| `architect_name` | `JORDI BOSCH NOVELL` | Budget email | Manual entry |
| `architect_company` | `ARQUITECTURA BOSCH NOVELL` | Budget email | Manual entry |
| `building_type` | `Habitatge aïllat` | Budget email | Manual entry |
| `num_floors` | `Pb + 1Pp` | Budget email | Manual entry |
| `superficie_parcela` | `500 m²` | Budget/Cadastre | Manual entry |
| `superficie_construida` | `200 m²` | Budget/Plans | Manual entry |
| `has_basement` | `false` | Budget/Plans | Boolean |
| `foundation_type` | `Fonaments superficials` | Usually standard | Default |

**CTE Classification (calculated):**
```python
def calculate_cte_class(area_m2, floors):
    if area_m2 < 300 and floors < 4:
        return "C-0"
    elif floors < 4:
        return "C-1"
    else:
        return "C-2"
```

### 2.4 Location Data (4 vars) - MANUAL/ICGC

| Variable | Example | Source | Method |
|----------|---------|--------|--------|
| `street_address` | `Carrer Antoni Bellet / Carrer Mestre Ramon Ortiz` | Budget email | Manual |
| `utm_x` | `307689` | ICGC viewer | Manual or API |
| `utm_y` | `4617890` | ICGC viewer | Manual or API |
| `cadastral_ref` | `4613172CG1141S` | Cadastre | Manual |

### 2.5 DPSH Test Data (12+ vars) - FROM EXCEL

| Variable | Example | Source | Extraction |
|----------|---------|--------|------------|
| `num_dpsh` | `2` | DPSH.xls | Count sheets |
| `dpsh_ids[]` | `['P-1', 'P-2']` | DPSH.xls | Sheet names |
| `dpsh_depths[]` | `[1.40, 2.60]` | DPSH.xls | Max depth with data per sheet |
| `dpsh_refusal[]` | `[true, true]` | DPSH.xls | N₂₀ = 100 check |
| `dpsh_water_level[]` | `[null, null]` | DPSH.xls | Column F (N.F.) |
| `dpsh_n20_data[][]` | `[[20,27,16,...], [...]]` | DPSH.xls | Column C per sheet |
| `dpsh_correction` | `0.83` | DPSH.xls | Cell D14 |
| `dpsh_date` | `2025-10-01` | DPSH PDF header | Parse |

**Calculated from DPSH:**
| Variable | Formula |
|----------|---------|
| `dpsh_average_per_level` | `AVERAGE(N₂₀ for depth range)` |
| `dpsh_nb_values` | `N₂₀ / 0.83` |

```python
# DPSH.xls extraction
import xlrd
wb = xlrd.open_workbook('DPSH.xls')

dpsh_data = {}
for sheet_name in wb.sheet_names():
    sheet = wb.sheet_by_name(sheet_name)
    depths, n20_values = [], []
    for row in range(16, sheet.nrows):
        depth = sheet.cell(row, 1).value
        n20 = sheet.cell(row, 2).value
        if isinstance(n20, (int, float)) and n20 > 0:
            depths.append(depth)
            n20_values.append(int(n20))
    dpsh_data[sheet_name] = {
        'max_depth': min(depths) if depths else 0,  # negative values
        'n20_values': n20_values,
        'refusal': 100 in n20_values,
        'average_n20': sum(n20_values) / len(n20_values) if n20_values else 0
    }
```

### 2.6 Sondeig/SPT Data (6 vars) - CONDITIONAL

| Variable | Example | Source | Notes |
|----------|---------|--------|-------|
| `has_sondeig` | `true` | Check file exists | Boolean |
| `sondeig_depth` | `6.00` | Sondeig PDF | Parse |
| `has_spt` | `true` | Sondeig records | Boolean |
| `spt_depths[]` | `[1.50-1.95]` | Sondeig PDF | Parse |
| `spt_n_values[]` | `[54]` | Sondeig PDF | N₃₀ values |
| `sondeig_date` | `2025-10-06` | Sondeig PDF | May differ from DPSH |

### 2.7 Lab Data (8 vars) - FROM LAB REPORTS

| Variable | Example | Source | Section Used |
|----------|---------|--------|--------------|
| `lab_tests_requested[]` | `[granulo, atterberg, sulfats]` | comanda laboratori.xls | 2.5 |
| `sulfate_mg_kg` | `89.8` | LAB-SIG.pdf | 4.2 |
| `aggressivity_class` | `No agressiu` | Calculated | 4.2 |
| `lambe_result` | `null` or `Marginal` | LAB-SIG.pdf | 4.3 (conditional) |
| `swelling_pressure` | `0.82` | LAB-SIG.pdf | 4.3 (conditional) |
| `liquid_limit` | `32` | LAB-SIG.pdf | Section 3 |
| `plastic_limit` | `18` | LAB-SIG.pdf | Section 3 |
| `granulometry` | `{graves: 45%, sorres: 40%, fins: 15%}` | LAB-SIG.pdf | Section 3 |

**Aggressivity calculation:**
```python
def classify_aggressivity(sulfate_mg_kg):
    if sulfate_mg_kg < 2000:
        return "No agressiu"
    elif sulfate_mg_kg < 3000:
        return "Dèbilment agressiu (Qa)"
    elif sulfate_mg_kg < 12000:
        return "Moderadament agressiu (Qb)"
    else:
        return "Fortament agressiu (Qc)"
```

### 2.8 Calculated Geotechnical Parameters (6 vars)

| Variable | Formula | Inputs | Section |
|----------|---------|--------|---------|
| `friction_angle` | N→φ correlation | `dpsh_average` | 4.1 Table 10 |
| `cohesion` | 0 for granular, calculated for clay | Material type | 4.1 Table 10 |
| `density` | Material lookup | Material type | 4.1 Table 10 |
| `deformation_modulus` | E = f(N) | `dpsh_average` | 4.1 Table 10 |
| `Qa` | Terzaghi formula | γ, c, φ, B, Df | 4.3 |
| `settlement` | Elastic formula | Qa, E, B | 4.3 |

**Standard correlations (from geotechnical literature):**
```python
def n_to_phi(n20):
    """N₂₀ to friction angle (degrees) - granular soils"""
    if n20 < 4: return 28
    elif n20 < 10: return 30
    elif n20 < 30: return 35
    elif n20 < 50: return 38
    else: return 40

def n_to_E(n20):
    """N₂₀ to deformation modulus (kg/cm²) - approximation"""
    return n20 * 10  # Simplified; actual formula in Base de càlcul
```

### 2.9 Observation-Based Data (10+ vars) - MANUAL

| Variable | Example | Source | Section |
|----------|---------|--------|---------|
| `site_position` | `oest del municipi` | ICGC/Google | 2.1.1 |
| `parcel_shape` | `rectangular` | Cadastre/observation | 2.1.1 |
| `adjacent_north` | `parcel·la buida` | Field/Google | 2.1.1 |
| `adjacent_south` | `Carrer Antoni Bellet` | Field/Google | 2.1.1 |
| `adjacent_east` | `Carrer Mestre Ramon Ortiz` | Field/Google | 2.1.1 |
| `adjacent_west` | `construcció aïllada de fins a dos plantes` | Field/Google | 2.1.1 |
| `site_access` | `Carrer existent al sud` | Field observation | 2.1.2 |
| `site_level` | `anivellada a la rasant del carrer` | Field observation | 2.1.2 |
| `is_urban` | `true` | Observation | Multiple |
| `nearby_watercourse` | `false` | ICGC check | 4.2 |
| `is_sloped` | `false` | Topography | Conditional |

### 2.10 Zone-Specific Templates - FROM SERVER

| Variable | Example | Source | Section |
|----------|---------|--------|---------|
| `geological_region_text` | `[multi-paragraph]` | Server: zone templates | 3.1 |
| `material_description_level1` | `graves en matriu sorrenca carbonatades` | Server: zone templates | 3.2, 4.1 |
| `hydrogeology_context` | `[paragraph about regional aquifer]` | Server: zone templates | 3.3 |

**⚠️ CRITICAL:** These templates are stored on G3DT's server. Need to request access/copies.

---

## 3. Section-to-Source Matrix

### Section 1: PRESENTACIÓ DE L'ESTUDI

| Subsection | Variables | Primary Source |
|------------|-----------|----------------|
| 1.1 Antecedents | client_name, architect_*, building_*, location | DADES CLIENT.txt + Data Entry |
| Taula 1 | building specs | Data Entry |
| Figures 1-2 | location maps | ICGC (manual screenshot) |
| 1.2 CTE | cte_class | Calculated |
| 1.3 Objectius | (none) | 100% Static |

### Section 2: TREBALLS DE CAMP

| Subsection | Variables | Primary Source |
|------------|-----------|----------------|
| Intro | dpsh_date | DPSH PDF |
| 2.1.1 Adjacent | adjacent_* | Observation/Google |
| 2.1.2 Site | site_* | Observation |
| 2.2 Tests | num_dpsh, has_sondeig, has_spt | File counts |
| 2.3 CTE | (none) | 100% Static |
| 2.4.1-3 Descriptions | (none) | 100% Static |
| Tables 3-5 | dpsh_*, spt_* | DPSH.xls, Sondeig |
| 2.5 Lab | lab_tests | comanda laboratori.xls |

### Section 3: DESCRIPCIÓ GEOLÒGICA (not fully mapped)

| Subsection | Variables | Primary Source |
|------------|-----------|----------------|
| 3.1 Marc geològic | geological_region_text | Zone templates (server) |
| 3.2 Materials | material_description_* | Zone templates + DPSH |
| 3.3 Hydrogeology | nearby_watercourse, is_urban | Observation + templates |
| 3.4 Aggressivity | sulfate_mg_kg, aggressivity_class | Lab results |
| 3.5 Excavability | (standard text) | Mostly static |
| 3.6 Seismic | (formulas) | Static + municipality lookup |
| 3.7 Radon | radon_zone | Municipality lookup |

### Section 4: CONCLUSIONS

| Subsection | Variables | Primary Source |
|------------|-----------|----------------|
| 4.1 Geologia | num_levels, dpsh_average, Table 10 params | DPSH.xls + Calculations |
| 4.2 Hidrogeologia | water_level, aggressivity_class | DPSH.xls + Lab |
| 4.3 Expansivitat | lambe_result, swelling_pressure | Lab (conditional) |
| 4.X Fonamentació | Qa, settlement | Calculated |
| 4.X Empentes | Ka, Kp | Calculated (conditional) |
| 4.X Estabilitat | slope_factor | Calculated (conditional) |

---

## 4. Data Entry Form Proposal

Based on the analysis, a data entry form should capture what can't be extracted automatically:

### Form Fields

```yaml
# PROJECT IDENTIFICATION (auto-filled from folder)
expedient: "4001612"  # Auto
municipality: "Bell-Lloc d'Urgell"  # Auto

# CLIENT (auto-filled from DADES CLIENT.txt)
client_name: "RAMON MITJANA SL"  # Auto
client_nif: "B25771726"  # Auto

# ARCHITECT & PROJECT (manual entry)
architect_name: ""  # Required
architect_company: ""  # Required
project_description: ""  # Required

# BUILDING SPECS (manual entry)
building_type: "Habitatge aïllat"  # Dropdown
num_floors: "Pb + 1Pp"  # Text
superficie_parcela_m2: 500  # Number
superficie_construida_m2: 200  # Number
has_basement: false  # Boolean
has_retaining_walls: false  # Boolean

# LOCATION (manual or ICGC lookup)
street_address: ""  # Required
utm_x: 0  # Number
utm_y: 0  # Number
cadastral_ref: ""  # Optional

# SITE OBSERVATIONS (manual)
site_position_in_municipality: "oest"  # Dropdown: nord/sud/est/oest/centre
parcel_shape: "rectangular"  # Dropdown
adjacent_north: ""  # Text
adjacent_south: ""  # Text
adjacent_east: ""  # Text
adjacent_west: ""  # Text
is_urban: true  # Boolean
is_sloped: false  # Boolean
nearby_watercourse: false  # Boolean

# GEOLOGICAL (dropdown from zone templates)
geological_zone: ""  # Dropdown linked to server templates
num_soil_levels: 1  # Number
level_1_material: ""  # Dropdown from zone vocabulary
level_1_depth_range: "0-2.60"  # Text
```

---

## 5. Automation Roadmap

### Phase 1: File Extraction (Easy)
- [x] Parse folder name → expedient, municipality
- [x] Parse DADES CLIENT.txt → client info
- [x] Read DPSH.xls → test data, depths, N-values
- [ ] Count ANNEXES files → test types
- [ ] Read comanda laboratori.xls → lab tests

### Phase 2: Calculations (Medium)
- [ ] Implement N→φ, N→E correlations
- [ ] Implement Terzaghi Qa formula
- [ ] Implement settlement formula
- [ ] Implement aggressivity classification
- [ ] Implement CTE classification

### Phase 3: Data Entry Form (Medium)
- [ ] Design form with fields above
- [ ] Auto-populate from file extractions
- [ ] Validate required fields
- [ ] Save to JSON for template engine

### Phase 4: Zone Templates (Needs Client)
- [ ] **Request zone template folder from G3DT**
- [ ] Index templates by zone/municipality
- [ ] Implement template selection in form
- [ ] Merge zone text into report

### Phase 5: Full Report Generation
- [ ] Integrate all sources into Jinja template
- [ ] Handle conditional sections
- [ ] Generate tables with calculated values
- [ ] Insert photos from FOTOGRAFIES/
- [ ] Output final .docx

---

## 6. Outstanding Questions for Client

1. **Zone templates location:** Where on the server are the geological zone templates stored?

2. **Base de càlcul formulas:** Can we get the Excel with the Terzaghi/settlement calculations to ensure exact match?

3. **Coordinate lookup:** Do they have a preferred method for getting UTM coordinates, or always manual from ICGC?

4. **Photo selection:** Who decides which photos go in the report? Is there a naming convention?

5. **Lab results timing:** Reports are sometimes written before lab results arrive. How to handle?

6. **Multi-level soils:** When there are 2+ soil levels, how are the depth ranges determined?

---

## 7. Files Created This Session

```
clients/g3dt/
├── reference-material/
│   ├── 4001612_informe.doc
│   └── 4001612-bell-lloc/           # Complete project folder
├── working-draft/
│   ├── SESSION-2026-02-02-data-sources-analysis.md
│   ├── PROOF-OF-CONCEPT-section1-mapping.md
│   ├── PROOF-OF-CONCEPT-section2-mapping.md
│   ├── PROOF-OF-CONCEPT-section4-mapping.md
│   └── CONSOLIDATED-DATA-SOURCE-MAP.md  ← THIS FILE
```

---

## Summary

**What we now know:**
- Every variable in the report traced to a source
- ~60% automatable from existing files
- ~25% needs data entry form
- ~15% needs zone templates from server

**Critical dependencies:**
1. DPSH.xls - the foundation of all calculations
2. Zone templates - for geological descriptions
3. Lab results - for aggressivity and expansivity

**Next steps:**
1. Request zone templates from client
2. Build DPSH extraction module
3. Create data entry form prototype
4. Implement calculation formulas

---

*Consolidated from Section 1, 2, 4 mappings. Section 3 partially covered (needs zone templates for full mapping).*
