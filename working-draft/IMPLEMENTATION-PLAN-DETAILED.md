# G3DT Report Automation: Detailed Implementation Plan
## Full Section-by-Section Implementation Guide

**Date:** 2026-02-02
**Status:** Planning
**Estimated Effort:** 3-4 weeks for core automation

---

## Executive Summary

This plan outlines the implementation of automated report generation for G3DT geotechnical reports. Based on our analysis, we can automate approximately **70-80%** of report content, with the remaining requiring either data entry or zone-specific templates from the client.

### Current State

| Module | Status | Description |
|--------|--------|-------------|
| `dpsh_extractor.py` | ✅ Complete | Extracts DPSH test data from Excel |
| `project_extractor.py` | ✅ Complete | Extracts all project folder data |
| `terzaghi_calculator.py` | ✅ Complete | Calculates Qa and settlements |
| Data source mapping | ✅ Complete | All variables traced to sources |
| Template system | 🔶 Partial | Basic Jinja2 exists, needs integration |
| Section generators | ❌ Not started | Per-section content generators |
| Data entry form | ❌ Not started | UI for manual inputs |

### Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                            │
├──────────────┬──────────────┬───────────────┬──────────────────┤
│  DPSH Excel  │ DADES CLIENT │  Folder Name  │  Data Entry Form │
│     ✅       │      ✅      │      ✅       │       ❌         │
└──────┬───────┴──────┬───────┴───────┬───────┴────────┬─────────┘
       │              │               │                │
       ▼              ▼               ▼                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    PROJECT DATA STRUCTURE                        │
│                         (JSON/Dict)                              │
│                            ✅                                    │
└──────────────────────────────┬───────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
       ▼                       ▼                       ▼
┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Terzaghi    │     │   Section       │     │   Template      │
│  Calculator  │     │   Generators    │     │   Engine        │
│      ✅      │     │      ❌         │     │      🔶         │
└──────┬───────┘     └────────┬────────┘     └────────┬────────┘
       │                      │                       │
       └──────────────────────┴───────────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │   DOCX Output    │
                    │       🔶         │
                    └──────────────────┘
```

---

## Phase 1: Core Infrastructure (Week 1)

### 1.1 Data Entry Form Schema

**Purpose:** Capture data that cannot be extracted automatically

**File:** `automation/data_schema.py`

```python
# Fields needed from user input
DATA_ENTRY_SCHEMA = {
    # Architect info (from budget email)
    'architect_name': {'type': 'str', 'required': True},
    'architect_company': {'type': 'str', 'required': True},

    # Building specifications
    'building_type': {'type': 'choice', 'options': [
        'Habitatge aïllat',
        'Habitatge plurifamiliar',
        'Nau industrial',
        'Edifici comercial'
    ]},
    'num_floors': {'type': 'str', 'example': 'Pb + 1Pp'},
    'superficie_parcela_m2': {'type': 'float'},
    'superficie_construida_m2': {'type': 'float'},
    'has_basement': {'type': 'bool', 'default': False},
    'has_retaining_walls': {'type': 'bool', 'default': False},

    # Location (can be from ICGC lookup)
    'street_address': {'type': 'str', 'required': True},
    'utm_x': {'type': 'float'},
    'utm_y': {'type': 'float'},

    # Site observations
    'site_position': {'type': 'choice', 'options': ['nord', 'sud', 'est', 'oest', 'centre']},
    'parcel_shape': {'type': 'choice', 'options': ['rectangular', 'quadrada', 'irregular']},
    'adjacent_north': {'type': 'str'},
    'adjacent_south': {'type': 'str'},
    'adjacent_east': {'type': 'str'},
    'adjacent_west': {'type': 'str'},
    'is_urban': {'type': 'bool', 'default': True},
    'is_sloped': {'type': 'bool', 'default': False},

    # Geological zone (links to templates)
    'geological_zone': {'type': 'choice', 'options': []},  # Populated from server
    'num_soil_levels': {'type': 'int', 'default': 1},
}
```

**Tasks:**
- [ ] Create `data_schema.py` with validation
- [ ] Create JSON schema for data entry
- [ ] Build simple CLI data entry tool
- [ ] (Future) Build web form interface

**Effort:** 2-3 hours

---

### 1.2 Report Data Model

**Purpose:** Unified data structure combining all sources

**File:** `automation/report_data.py`

```python
@dataclass
class ReportData:
    """Complete data needed to generate a report."""

    # Project identification
    expedient: str
    municipality: str
    report_date: date

    # Client
    client: ClientData

    # Architect/Project
    architect_name: str
    architect_company: str
    building_type: str
    num_floors: str
    superficie_parcela: float
    superficie_construida: float
    has_basement: bool
    has_retaining_walls: bool

    # Location
    street_address: str
    utm_x: float
    utm_y: float

    # Site observations
    adjacent_parcels: dict  # {north, south, east, west}
    site_description: str
    is_urban: bool
    is_sloped: bool

    # Test data
    dpsh: DPSHData
    has_sondeig: bool
    has_spt: bool
    spt_data: Optional[SPTData]

    # Lab data
    lab_tests: list
    sulfate_mg_kg: Optional[float]
    aggressivity_class: str
    lambe_result: Optional[str]

    # Calculated values
    cte_classification: str  # C-0, C-1, C-2
    soil_levels: list[SoilLevel]
    geotechnical_params: GeotechnicalParams
    qa_result: BearingCapacityResult

    # Conditional sections
    include_expansivity: bool
    include_earth_pressure: bool
    include_slope_stability: bool
```

**Tasks:**
- [ ] Create `report_data.py` with full data model
- [ ] Create factory method to build from project + data entry
- [ ] Add validation for required fields
- [ ] Add JSON serialization

**Effort:** 3-4 hours

---

### 1.3 CTE Classification Calculator

**Purpose:** Calculate CTE building/soil classification

**File:** `automation/cte_classifier.py`

```python
def classify_building(area_m2: float, floors: int, has_basement: bool) -> str:
    """
    Classify building per CTE DB SE-C.

    C-0: < 300 m² AND < 4 floors (including basement)
    C-1: ≥ 300 m² OR ≥ 4 floors (< 10 floors)
    C-2: ≥ 10 floors
    """
    total_floors = floors + (1 if has_basement else 0)

    if total_floors >= 10:
        return "C-2"
    elif area_m2 >= 300 or total_floors >= 4:
        return "C-1"
    else:
        return "C-0"

def classify_soil(dpsh_data: DPSHData, has_fill: bool = False) -> str:
    """
    Classify soil per CTE DB SE-C.

    T-1: Favorable (uniform, no fill, good bearing)
    T-2: Intermediate
    T-3: Unfavorable (heterogeneous, fill, poor bearing)
    """
    # Usually T-1 for natural granular soils
    if has_fill:
        return "T-3"

    avg_n = dpsh_data.overall_average_n20
    if avg_n < 10:
        return "T-2"

    return "T-1"
```

**Tasks:**
- [ ] Create `cte_classifier.py`
- [ ] Implement building classification
- [ ] Implement soil classification
- [ ] Add tests with known examples

**Effort:** 1-2 hours

---

## Phase 2: Section Generators (Week 2)

Each section generator produces structured content (paragraphs, tables, figures) that the template engine assembles.

### 2.1 Section 1 Generator: PRESENTACIÓ DE L'ESTUDI

**File:** `automation/sections/section1_presentacio.py`

**Subsections:**

#### 1.1 ANTECEDENTS

| Element | Source | Implementation |
|---------|--------|----------------|
| Client intro paragraph | Template + `client.company_name` | String format |
| Architect paragraph | Template + `architect_*` | String format |
| Taula 1 (building data) | Data entry fields | Table generator |
| Location paragraph | Template + `street_address`, `municipality` | String format |
| Figures 1-2 | ICGC screenshots (manual) | Placeholder/path |
| Figure 3 | Architect plans (optional) | Conditional include |

**Tasks:**
- [ ] Create `section1_presentacio.py`
- [ ] Implement `generate_antecedents()` function
- [ ] Implement `generate_taula1()` table builder
- [ ] Implement `generate_location_paragraph()`
- [ ] Handle conditional Figure 3

**Code structure:**
```python
class Section1Generator:
    def __init__(self, data: ReportData):
        self.data = data

    def generate_intro_paragraph(self) -> str:
        return f"A petició de:\n\n{self.data.client.company_name},"

    def generate_antecedents_paragraph(self) -> str:
        return (
            f"Segons ens indica el sol·licitant, el SR. {self.data.architect_name}, "
            f"de {self.data.architect_company}, en nom de {self.data.client.company_name}, "
            f"es preveu la construcció de..."
        )

    def generate_taula1(self) -> dict:
        return {
            'Tipus de construcció': self.data.building_type,
            'Nº de plantes': self.data.num_floors,
            'Superfície parcel·la': f"{self.data.superficie_parcela} m²",
            'Superfície construïda': f"{self.data.superficie_construida} m²",
            'Tipus fonamentació': 'Fonaments superficials',
            'Soterranis': 'Cap' if not self.data.has_basement else '1 soterrani',
        }

    def generate_all(self) -> dict:
        return {
            'intro': self.generate_intro_paragraph(),
            'antecedents': self.generate_antecedents_paragraph(),
            'taula1': self.generate_taula1(),
            'location': self.generate_location_paragraph(),
            'figures': self.get_figure_paths(),
        }
```

**Effort:** 3-4 hours

#### 1.2 CLASSIFICACIÓ CTE

| Element | Source | Implementation |
|---------|--------|----------------|
| Intro paragraph | Static template | Constant |
| Taula 2 | `cte_classifier.py` output | Table generator |

**Tasks:**
- [ ] Implement `generate_classificacio_cte()`
- [ ] Implement `generate_taula2()`

**Effort:** 1 hour

#### 1.3 OBJECTIUS

| Element | Source | Implementation |
|---------|--------|----------------|
| All content | 100% static | Constant text |

**Tasks:**
- [ ] Store as constant in template

**Effort:** 15 minutes

---

### 2.2 Section 2 Generator: TREBALLS DE CAMP

**File:** `automation/sections/section2_treballs.py`

#### Intro + 2.1 DESCRIPCIÓ ZONA

| Element | Source | Implementation |
|---------|--------|----------------|
| Field date paragraph | DPSH PDF date | String format |
| Visit objectives | Static | Constant |
| 2.1.1 Adjacent parcels | Data entry | Template with N/S/E/W |
| 2.1.2 Site description | Data entry | Free text |
| Photos 1-2 | File paths from inventory | Image references |

**Tasks:**
- [ ] Create `section2_treballs.py`
- [ ] Implement `generate_intro()`
- [ ] Implement `generate_adjacent_parcels()`
- [ ] Implement `generate_site_description()`

**Code structure:**
```python
class Section2Generator:
    def __init__(self, data: ReportData):
        self.data = data

    def generate_intro(self) -> str:
        date_str = self.data.dpsh.tests[0].date  # Need to add date extraction
        return f"El dia {date_str}, es va visitar l'obra per tal de:"

    def generate_adjacent_parcels(self) -> str:
        adj = self.data.adjacent_parcels
        return (
            f"La parcel·la objecte d'estudi es situa al {self.data.site_position} "
            f"del municipi de {self.data.municipality}, "
            f"pren una morfologia {self.data.parcel_shape} i limita:\n\n"
            f"Per la part est amb {adj['east']}.\n"
            f"Per la part sud amb {adj['south']}.\n"
            f"Per la part nord amb {adj['north']}.\n"
            f"I finalment, per la part oest, amb {adj['west']}."
        )
```

**Effort:** 2-3 hours

#### 2.2 RECONEIXEMENT DEL TERRENY

| Element | Source | Implementation |
|---------|--------|----------------|
| Date(s) paragraph | DPSH + Sondeig dates | String with date logic |
| Test list | File inventory counts | Bullet list generator |
| Lab accreditation | Static | Constant |

**Tasks:**
- [ ] Implement `generate_test_list()`
- [ ] Handle multiple dates (DPSH vs Sondeig)

**Effort:** 1-2 hours

#### 2.3 JUSTIFICACIÓ CTE

| Element | Source | Implementation |
|---------|--------|----------------|
| All content | 100% static | Constant |

**Effort:** 15 minutes

#### 2.4 ASSAIGS IN SITU

| Element | Source | Implementation |
|---------|--------|----------------|
| 2.4.1 DPSH description | Static | Constant |
| 2.4.2 Sondeig (conditional) | Static | Conditional include |
| 2.4.3 SPT (conditional) | Static | Conditional include |
| Tables 3-5 | DPSH + Sondeig data | Table generators |

**Tasks:**
- [ ] Implement conditional subsection logic
- [ ] Implement `generate_taula3_dpsh()`
- [ ] Implement `generate_taula4_sondeig()` (conditional)
- [ ] Implement `generate_taula5_spt()` (conditional)

**Code for DPSH table:**
```python
def generate_taula3_dpsh(self) -> list[dict]:
    """Generate DPSH summary table (Taula 3)."""
    rows = []
    for test in self.data.dpsh.tests:
        rows.append({
            'Assaig': test.test_id,
            'UTM X': self.data.utm_x,  # Same for all tests
            'UTM Y': self.data.utm_y,
            'Cota inici (msnm)': self.data.elevation,  # Need to add
            'Profunditat (m)': f"{test.depth_reached:.2f}",
            'NF (m)': '-' if not test.water_detected else f"{test.water_depth:.2f}",
            'Observacions': 'Rebuig' if test.refusal_reached else '',
        })
    return rows
```

**Effort:** 3-4 hours

#### 2.5 ASSAIGS LABORATORI

| Element | Source | Implementation |
|---------|--------|----------------|
| Intro | Static | Constant |
| Taula 6 | Lab request file | Table generator |

**Tasks:**
- [ ] Implement lab request parser (or data entry)
- [ ] Implement `generate_taula6_lab()`

**Effort:** 2 hours

---

### 2.3 Section 3 Generator: DESCRIPCIÓ GEOLÒGICA (Partial)

**File:** `automation/sections/section3_geologia.py`

**⚠️ BLOCKER:** This section requires zone-specific templates from G3DT's server.

#### 3.1 MARC GEOLÒGIC

| Element | Source | Implementation |
|---------|--------|----------------|
| Regional geology text | **Zone templates (server)** | Template selection |
| Geological map | ICGC screenshot (manual) | Image reference |

**Tasks:**
- [ ] Create placeholder structure
- [ ] Request zone templates from client
- [ ] Implement zone template loading
- [ ] Implement template selection by municipality

**Effort:** 2-3 hours (structure) + depends on templates

#### 3.2 MATERIALS

| Element | Source | Implementation |
|---------|--------|----------------|
| Level count intro | DPSH interpretation | Calculated |
| Level descriptions | **Zone templates** | Template + DPSH data |
| Sample photos | File paths | Image references |

**Tasks:**
- [ ] Implement level detection from DPSH
- [ ] Create placeholder for zone template integration

**Effort:** 2-3 hours

#### 3.3 HIDROGEOLOGIA

| Element | Source | Implementation |
|---------|--------|----------------|
| Surface hydrology | Urban/rural template | Conditional text |
| Groundwater | DPSH water level | Template + data |
| Permeability table | Material type lookup | Table generator |

**Tasks:**
- [ ] Implement `generate_hidrogeologia()`
- [ ] Implement urban vs rural text selection
- [ ] Implement permeability table

**Effort:** 2 hours

#### 3.4 AGRESSIVITAT

| Element | Source | Implementation |
|---------|--------|----------------|
| Sulfate paragraph | Lab results | Template + classification |
| Classification | `sulfate_mg_kg` → class | Lookup table |

**Tasks:**
- [ ] Implement `classify_aggressivity(sulfate_mg_kg)`
- [ ] Generate paragraph with classification

**Code:**
```python
def classify_aggressivity(sulfate_mg_kg: float) -> tuple[str, str]:
    """Returns (class_code, class_text)"""
    if sulfate_mg_kg < 2000:
        return ('', 'no agressius')
    elif sulfate_mg_kg < 3000:
        return ('Qa', 'dèbilment agressius')
    elif sulfate_mg_kg < 12000:
        return ('Qb', 'moderadament agressius')
    else:
        return ('Qc', 'fortament agressius')
```

**Effort:** 1 hour

#### 3.5-3.7 (Mostly Static)

| Subsection | Implementation |
|------------|----------------|
| 3.5 Excavabilitat | Static with material type |
| 3.6 Sísmica | Static formulas + municipality lookup for ab |
| 3.7 Radó | Municipality lookup for zone |

**Tasks:**
- [ ] Implement seismic parameter lookup (municipality → ab)
- [ ] Implement radon zone lookup (municipality → ZONA 1/2)
- [ ] Static text templates

**Effort:** 2-3 hours

---

### 2.4 Section 4 Generator: CONCLUSIONS

**File:** `automation/sections/section4_conclusions.py`

#### 4.1 GEOLOGIA

| Element | Source | Implementation |
|---------|--------|----------------|
| Level summary | Section 3 data | Paragraph generator |
| Figura 6 (cross-section) | FreeHand file → PDF | File reference |
| Taula 10 (parameters) | Terzaghi calculator | Table generator |

**Tasks:**
- [ ] Implement `generate_geology_summary()`
- [ ] Implement `generate_taula10()` using calculated params

**Code for Table 10:**
```python
def generate_taula10(self) -> list[dict]:
    """Generate geotechnical parameters table."""
    params = self.data.geotechnical_params
    return [{
        'Nivell': '1er Nivell',
        'Descripció': self.data.soil_levels[0].description,
        'Gruix (m)': f">{self.data.dpsh.tests[0].depth_reached:.2f}",
        'γ (g/cm³)': f"{params.gamma:.2f}",
        'c (kg/cm²)': f"{params.cohesion:.2f}",
        'φ (°)': f"{params.phi:.0f}",
        'E (kg/cm²)': f"{params.E:.0f}",
        'N₂₀ mitjà': f"{self.data.dpsh.overall_average_n20:.0f}",
    }]
```

**Effort:** 2-3 hours

#### 4.2 HIDROGEOLOGIA I AGRESSIVITAT

| Element | Source | Implementation |
|---------|--------|----------------|
| Water level statement | DPSH data | Conditional template |
| Aggressivity statement | Lab results | Template + classification |

**Tasks:**
- [ ] Implement water level conditional text
- [ ] Implement aggressivity statement

**Effort:** 1-2 hours

#### 4.3 FONAMENTACIÓ (or EXPANSIVITAT)

| Element | Source | Implementation |
|---------|--------|----------------|
| Excavation context | Building data | Template |
| Qa recommendation | Terzaghi calculator | **Already implemented** ✅ |
| Settlement estimate | Terzaghi calculator | **Already implemented** ✅ |

**Tasks:**
- [ ] Implement `generate_fonamentacio()` using Terzaghi results
- [ ] Format output for report text

**Code:**
```python
def generate_fonamentacio(self) -> dict:
    qa_result = self.data.qa_result
    return {
        'excavation_paragraph': self.generate_excavation_context(),
        'qa_paragraph': qa_result.format_for_report(),
        'settlement_paragraph': qa_result.format_settlement_for_report(),
    }
```

**Effort:** 2 hours

#### 4.X CONDITIONAL SECTIONS

| Section | Trigger | Implementation |
|---------|---------|----------------|
| Expansivitat | Lambe ≥ Marginal | Template with swelling pressure |
| Empentes de terres | has_retaining_walls | Ka, Kp calculations |
| Estabilitat vessant | is_sloped | Hoek & Bray (complex) |

**Tasks:**
- [ ] Implement `generate_expansivitat()` (conditional)
- [ ] Implement `generate_empentes()` with pressure calculations
- [ ] Implement `generate_estabilitat()` (complex, may defer)

**Effort:** 4-6 hours

---

## Phase 3: Template Engine Integration (Week 3)

### 3.1 Template Structure

**File:** `templates/g3dt-report-template.docx`

The Jinja2-enabled docx template with placeholders:

```jinja2
{{ section1.intro }}

1.1. ANTECEDENTS

{{ section1.antecedents }}

{% for row in section1.taula1 %}
| {{ row.key }} | {{ row.value }} |
{% endfor %}

{# ... etc ... #}
```

**Tasks:**
- [ ] Refactor existing `g3dt-jinja-template.docx`
- [ ] Add all placeholder variables
- [ ] Add conditional sections with `{% if %}`
- [ ] Add table loops with `{% for %}`
- [ ] Test with docxtpl library

**Effort:** 4-6 hours

---

### 3.2 Report Generator

**File:** `automation/report_generator.py`

**Main orchestrator that:**
1. Loads project data (from extractor)
2. Loads user input data (from form/JSON)
3. Runs all section generators
4. Merges into template
5. Outputs final .docx

```python
class ReportGenerator:
    def __init__(self, project_path: str, user_data_path: str):
        self.project_data = ProjectExtractor(project_path).extract_all()
        self.user_data = self.load_user_data(user_data_path)
        self.report_data = self.build_report_data()

    def generate(self, output_path: str):
        # Generate all sections
        section1 = Section1Generator(self.report_data).generate_all()
        section2 = Section2Generator(self.report_data).generate_all()
        section3 = Section3Generator(self.report_data).generate_all()
        section4 = Section4Generator(self.report_data).generate_all()

        # Load template
        doc = DocxTemplate('templates/g3dt-report-template.docx')

        # Render
        context = {
            'section1': section1,
            'section2': section2,
            'section3': section3,
            'section4': section4,
            'project': self.report_data,
        }
        doc.render(context)
        doc.save(output_path)
```

**Tasks:**
- [ ] Create `report_generator.py`
- [ ] Implement data merging logic
- [ ] Implement template rendering
- [ ] Add image insertion
- [ ] Add table generation
- [ ] Test end-to-end

**Effort:** 6-8 hours

---

## Phase 4: Testing & Validation (Week 4)

### 4.1 Test with Known Report

Using 4001612 Bell-Lloc as reference:

| Check | Expected | Method |
|-------|----------|--------|
| Client name | RAMON MITJANA SL | Compare |
| Expedient | 4001612 | Compare |
| DPSH tests | 2 (P-1, P-2) | Compare |
| DPSH depths | 1.40m, 2.60m | Compare |
| Qa value | ~3.0 kg/cm² | Compare (may need calibration) |
| Settlement | <1.20 cm | Compare |
| Sections present | 1-4.3 | Compare |

**Tasks:**
- [ ] Generate report from 4001612 data
- [ ] Compare with original report
- [ ] Document differences
- [ ] Calibrate calculations if needed
- [ ] Fix formatting issues

**Effort:** 4-6 hours

### 4.2 Test with Other Samples

| Sample | Special Features | Test Focus |
|--------|------------------|------------|
| 3001631 Rubí | Simple (DPSH only) | Minimal test case |
| 4001607 Linyola | Expansivity section | Conditional section |
| 3001621 Castellar | Slope + earth pressure | Complex conditionals |

**Tasks:**
- [ ] Test each sample
- [ ] Verify conditional sections
- [ ] Document edge cases

**Effort:** 4-6 hours

---

## Blockers & Dependencies

### From Client (G3DT)

| Item | Priority | Status |
|------|----------|--------|
| Zone geological templates | **HIGH** | ❌ Not received |
| Base de càlcul Excel | MEDIUM | ❌ Not received |
| Seismic parameters by municipality | MEDIUM | Can lookup online |
| Radon zones by municipality | LOW | Can lookup online |

### Technical

| Item | Priority | Notes |
|------|----------|-------|
| DPSH date extraction | HIGH | Need to parse from PDF header |
| Lab results parser | MEDIUM | PDF parsing or data entry |
| Image insertion | HIGH | docxtpl supports this |
| Table styling | HIGH | docxtpl table features |

---

## Effort Summary

| Phase | Tasks | Est. Hours |
|-------|-------|------------|
| Phase 1: Infrastructure | Data schema, report model, CTE | 8-10 |
| Phase 2: Section generators | All 4 sections | 25-35 |
| Phase 3: Template integration | Template + generator | 10-14 |
| Phase 4: Testing | Validation with samples | 8-12 |
| **Total** | | **51-71 hours** |

**Timeline:** ~2-3 weeks of focused work, or ~4 weeks part-time

---

## Implementation Order (Recommended)

```
Week 1:
├── Day 1-2: Data schema + Report data model
├── Day 3: CTE classifier
├── Day 4-5: Section 1 generator (easiest, good template)

Week 2:
├── Day 1-2: Section 2 generator (DPSH-heavy)
├── Day 3-4: Section 4 generator (uses Terzaghi)
├── Day 5: Section 3 generator (placeholder for zone templates)

Week 3:
├── Day 1-2: Template integration
├── Day 3-4: Report generator orchestrator
├── Day 5: Image and table handling

Week 4:
├── Day 1-2: Testing with Bell-Lloc
├── Day 3-4: Testing with other samples
├── Day 5: Bug fixes and documentation
```

---

## Files to Create

```
automation/
├── __init__.py              ✅ Exists
├── dpsh_extractor.py        ✅ Exists
├── project_extractor.py     ✅ Exists
├── terzaghi_calculator.py   ✅ Exists
├── data_schema.py           ❌ To create
├── report_data.py           ❌ To create
├── cte_classifier.py        ❌ To create
├── aggressivity.py          ❌ To create
├── sections/
│   ├── __init__.py          ❌ To create
│   ├── section1_presentacio.py  ❌ To create
│   ├── section2_treballs.py     ❌ To create
│   ├── section3_geologia.py     ❌ To create
│   └── section4_conclusions.py  ❌ To create
├── report_generator.py      ❌ To create
└── README.md                ✅ Exists (update)

templates/
├── g3dt-report-template.docx    🔶 Exists (needs refactor)
├── assets/                      ✅ Exists
└── zone_templates/              ❌ To create (from client)
```

---

## Next Immediate Steps

1. **Request zone templates from client** (blocker for Section 3)
2. Create `data_schema.py` with validation
3. Create `report_data.py` unified model
4. Start with Section 1 generator (simplest)
5. Progress through sections in order

---

*Detailed implementation plan - G3DT Report Automation*
*Last updated: 2026-02-02*
