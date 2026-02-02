# G3DT Report Template Specification
## Informe Geològic/Geotècnic

**Based on:** Sample 3001621_informe.pdf (49 pages), validated with 3001631_informe.pdf (46 pages), 4001607_informe.pdf (48 pages), 4001612_informe.pdf (45 pages)
**Language:** Catalan
**Report Type:** Estudi geològic/geotècnic per construcció
**Last Updated:** 2026-01-04

---

## 0. REGULATORY FRAMEWORK

### Primary Regulation: CTE DB SE-C

The **Código Técnico de la Edificación - Documento Básico Seguridad Estructural: Cimientos** ([PDF](https://www.codigotecnico.org/pdf/Documentos/SE/DBSE-C.pdf)) is the main regulation governing geotechnical studies in Spain.

- **Mandatory** for all buildings under LOE (Ley de Ordenación de la Edificación)
- Defines the **C-0/C-1/C-2** building classifications and **T-1/T-2/T-3** soil types
- Specifies minimum reconnaissance requirements based on building type + soil complexity
- Requires professional signature with "visat colegial" (professional body endorsement)

**When mandatory:** Single-family homes, residential buildings, industrial/commercial, public infrastructure, and any major renovation affecting foundations.

### Test Standards (UNE/ISO)

| Test | Standard | Description |
|------|----------|-------------|
| DPSH | **UNE-EN ISO 22476-2** (also UNE 103.801/94) | Dynamic probing: 63.5kg maza, 76cm drop, N20 counts |
| SPT | **UNE-EN ISO 22476-3/2006** | Standard penetration: N30 values, sample recovery |
| Sondeig | UNE-EN ISO 22475-1 | Rotary borehole with continuous core |
| Granulometry | UNE 103101/95 | Lab sieve analysis |
| Atterberg limits | UNE 103103/94, 103104/93 | Plasticity index, liquid limit |
| Lambe (expansivity) | UNE 103600 | Swelling pressure classification |

### Other Regulations Referenced in Reports

| Regulation | Section | Purpose |
|------------|---------|---------|
| **NCSE-02** | 3.6 | Seismic acceleration (ab, ac, S, C, ρ values) |
| **CTE HS-6** | 3.7 | Radon exposure zones (ZONA 1/2) |
| **EHE / CE-21** | 3.4 | Concrete aggressivity (sulfate content mg/kg SO₄) |

### Automation Implication

The report structure follows CTE requirements closely:
- Test selection → driven by CTE building/soil classification
- Depth of investigation → minimum depths per CTE
- Required parameters → all mandated by regulation
- Section structure → mirrors CTE checklist

This means the template is **highly standardized** - variations are predictable based on regulatory requirements, not arbitrary choices.

---

## 1. DOCUMENT STRUCTURE OVERVIEW

```
REPORT (18-25 pages, varies by project complexity)
├── Cover Page (1 page)
├── Índex + Annexes List (1-2 pages)
├── 1. Presentació de l'estudi
├── 2. Treballs de camp
├── 3. Descripció geològica i geotècnica
├── 4. Conclusions
└── Signature Page

ANNEXES (20-25 pages, varies by number of tests)
├── Base de càlcul
├── Registre d'assaigs mecànics
├── Esquema situació assaigs
├── Tall de correlació
├── Fotografies
└── Actes d'assaig de laboratori
```

**Validated Page Counts:**
| Sample | Report | Annexes | Total |
|--------|--------|---------|-------|
| 3001621 (Castellar) | ~25 | ~24 | 49 |
| 3001631 (Rubí) | ~21 | ~25 | 46 |
| 4001607 (Linyola) | ~24 | ~24 | 48 |
| 4001612 (Bell-Lloc) | ~22 | ~23 | 45 |

---

## 1B. DECISION TREE: WHY SECTIONS VARY

Understanding what project characteristics drive the inclusion of optional sections.

### Project Characteristics Summary

| Sample | Location | Building Type | CTE Class | Site Terrain | Soil Type | Has Basement/Walls? |
|--------|----------|---------------|-----------|--------------|-----------|---------------------|
| 3001621 | Castellar del Vallès | Multi-story | C-1 | **Sloped** | Mixed layers | Yes (retaining) |
| 3001631 | Rubí | Single-family | C-0 | Flat | Granular (graves) | No |
| 4001607 | Linyola | Single-family | C-0 | Flat | **Clay-rich (llims)** | No |
| 4001612 | Bell-Lloc | Single-family (Pb+1Pp) | C-1 | Flat | Granular (graves) | No |

### Decision Tree: Test Selection (Section 2.4)

```
START: What does CTE require?
│
├─ CTE C-0 (simple buildings) → Minimum: DPSH only
│   └─ Is soil clearly identifiable from DPSH?
│       ├─ YES → DPSH only (Sample 3001631)
│       └─ NO / Need samples → Add SPT (Sample 4001607)
│
└─ CTE C-1/C-2 (more complex) → Minimum: DPSH + complementary
    └─ Need continuous stratigraphy or samples?
        ├─ Full profile needed → Add Sondeig (borehole)
        └─ Just samples → Add SPT
        └─ Both → Sondeig + SPT (Samples 3001621, 4001612)
```

**Why Sondeig vs SPT?**
- **Sondeig a rotació**: Continuous core recovery, full stratigraphy, see all layers
- **SPT**: Specific depth samples for lab tests, N30 resistance values
- Both can be combined when full picture + lab samples needed

### Decision Tree: Conclusions Sections (Section 4)

```
4.1 GEOLOGIA ────────────────────────────────────────── ALWAYS PRESENT
    │
4.2 HIDROGEOLOGIA I AGRESSIVITAT ────────────────────── ALWAYS PRESENT
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ DECISION POINT: Is soil expansive (clay-rich, high plasticity)?    │
│                                                                     │
│ Check: Lambe test, Atterberg limits, visual soil classification    │
└─────────────────────────────────────────────────────────────────────┘
    │
    ├─ YES (llims argilosos, high IP) ──────► 4.3 EXPANSIVITAT DELS MATERIALS
    │                                              │
    │                                              ▼
    │                                         4.4 FONAMENTACIÓ
    │
    └─ NO (granular, low plasticity) ───────► 4.3 FONAMENTACIÓ
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ DECISION POINT: Will there be retaining walls or basement?         │
│                                                                     │
│ Check: Project drawings, excavation depth, neighboring structures  │
└─────────────────────────────────────────────────────────────────────┘
    │
    ├─ YES ──────────────────────────────────► 4.X EMPENTES DE TERRES
    │                                               │
    └─ NO                                           ▼
           │                  ┌─────────────────────────────────────────────┐
           │                  │ DECISION POINT: Is site on a slope?        │
           │                  │                                             │
           │                  │ Check: Topography, angle > threshold       │
           │                  └─────────────────────────────────────────────┘
           │                           │
           │                           ├─ YES ────► 4.X ESTABILITAT DEL VESSANT
           │                           │
           └───────────────────────────┴─ NO ─────► END (no more sections)
```

### Why Each Sample Has Its Structure

**Sample 3001621 (Castellar) - MOST COMPLETE**
```
Triggers:
├─ CTE C-1 (larger building) → Full test suite (DPSH + Sondeig + SPT)
├─ Granular soil → 4.3 = Fonamentació (not Expansivitat)
├─ Retaining walls needed → 4.4 Empentes de terres
└─ SLOPED SITE → 4.5 Estabilitat del vessant (Hoek & Bray analysis)

Result: 4.1 → 4.2 → 4.3 Fonamentació → 4.4 Empentes → 4.5 Estabilitat
```

**Sample 3001631 (Rubí) - SIMPLEST**
```
Triggers:
├─ CTE C-0 (simple house) → Minimum tests (DPSH only)
├─ Clear granular soil (graves) → No uncertainty, no extra tests
├─ Flat site → No slope analysis
└─ No basement → No earth pressure analysis

Result: 4.1 → 4.2 → 4.3 Fonamentació → END
```

**Sample 4001607 (Linyola) - EXPANSIVE SOILS**
```
Triggers:
├─ CTE C-0 but uncertain soil → Added SPT for samples
├─ CLAY-RICH SOIL (llims argilosos) → Lambe test showed "Marginal" expansivity
│   └─ Pressió inflament = 0.82 kg/cm² → Risk that needs addressing
├─ Flat site → No slope analysis
└─ No basement → No earth pressure analysis

Result: 4.1 → 4.2 → 4.3 EXPANSIVITAT → 4.4 Fonamentació → END
```

**Sample 4001612 (Bell-Lloc) - GOOD SOIL DESPITE EXTENSIVE TESTS**
```
Triggers:
├─ CTE C-1 (Pb+1Pp) → Full test suite (DPSH + Sondeig + SPT)
├─ BUT soil is excellent (graves carbonatades, N=54, high bearing)
├─ No expansivity concern → 4.3 = Fonamentació
├─ Flat site → No slope analysis
└─ No basement → No earth pressure analysis

Result: 4.1 → 4.2 → 4.3 Fonamentació → END
(More tests ≠ more conclusion sections; tests inform, soil conditions determine)
```

### Key Insight: Tests vs Conclusions

**Tests (Section 2.4)** are driven by:
- CTE regulatory requirements (building classification)
- Need for certainty (sample recovery, lab analysis)
- Client/architect request

**Conclusions (Section 4)** are driven by:
- Actual soil conditions found (not what tests were done)
- Project design requirements (basement, slopes, walls)
- Risk factors discovered (expansivity, water table, aggressivity)

> **Important:** A simple project can have extensive testing (4001612) but simple conclusions if soil is straightforward. Conversely, complex soil conditions will add conclusion sections regardless of test volume.

### Material Levels (Section 3.2)

| Sample | Nivells | Why? |
|--------|---------|------|
| 3001621 | 2+ | Complex stratigraphy, multiple distinct geological units |
| 3001631 | 1 | Uniform deposit (graves i sorres carbonatades) throughout |
| 4001607 | 2 | Surface layer (llims) over deeper layer (lutites) - different properties |
| 4001612 | 1 | Uniform deposit (graves en matriu sorrenca) with only thin topsoil |

**Rule:** Number of Nivells = number of geotechnically distinct units that affect foundation design, NOT number of geological formations visible.

---

## 2. PAGE LAYOUT

### 2.1 Page Setup (Word)
| Property | Value |
|----------|-------|
| Paper size | A4 (210 × 297 mm) |
| Orientation | Portrait |
| Top margin | 2.5 cm |
| Bottom margin | 2.0 cm |
| Left margin | 2.5 cm |
| Right margin | 2.5 cm |
| Header distance | 1.25 cm from edge |
| Footer distance | 1.0 cm from edge |
| Gutter | 0 cm |

### 2.2 Cover Page
- **G3 Logo**: Top-right corner, with "25 anys" anniversary badge
- **Watermark**: Large semi-transparent green "G3" bottom-right (~40% opacity)
- **Metadata Block** (bottom-left, ~8cm from bottom):
  ```
  CLIENT: [name or "------" if confidential]
  EXPEDIENT: [7-digit number starting with 3 or 4]
  DATA: [DD/MM/YY]
  OBRA: [PROJECT DESCRIPTION IN CAPS, multi-line allowed]
  ```
- **Metadata formatting:**
  - Labels (CLIENT:, EXPEDIENT:, etc.): Bold, 11pt
  - Values: Regular, 11pt
  - Line spacing: 1.5

### 2.3 Header (all internal pages)
```
[G3 Logo]    {expedient}/Estudi geològic – geotècnic_{LOCATION}    [Page#]
```

| Element | Position | Format |
|---------|----------|--------|
| G3 Logo | Left | ~1.5cm height |
| Document title | Center | 10pt Calibri, includes expedient number |
| Page number | Right | White text in green (#4A7C59) rounded square box |

### 2.4 Footer (all internal pages)
```
G3 DT, S.L.          www.g3dt.com          g3@g3dt.com
```

| Element | Position | Format |
|---------|----------|--------|
| Company name | Left | 9pt Calibri |
| Website | Center | 9pt Calibri, hyperlink blue |
| Email | Right | 9pt Calibri, hyperlink blue |

### 2.5 Section Breaks
- New major sections (1, 2, 3, 4) may start on new page
- Annexes always start on new page with divider page

---

## 3. TYPOGRAPHY

> **Production Note:** Reports created in MS Word. Graphics/diagrams in Freehand (vector).

### 3.1 Font Family
| Element | Font | Fallback |
|---------|------|----------|
| Body text | Calibri | Arial, sans-serif |
| Headers | Calibri | Arial, sans-serif |
| Tables | Calibri | Arial, sans-serif |
| Captions | Calibri | Arial, sans-serif |

### 3.2 Section Headers

| Level | Size | Weight | Color | Style | Case | Example |
|-------|------|--------|-------|-------|------|---------|
| H1 (Section) | 14pt | Bold | Green (#4A7C59) | Underlined | UPPERCASE | `1. PRESENTACIÓ DE L'ESTUDI` |
| H2 (Subsection) | 12pt | Bold | Green (#4A7C59) | Normal | Title Case | `1.1. ANTECEDENTS` |
| H3 (Sub-subsection) | 11pt | Normal | Black | Italic | Sentence case | `2.1.1. Descripció de les parcel·les adjacents` |

### 3.3 Body Text
| Property | Value |
|----------|-------|
| Font | Calibri |
| Size | 11pt |
| Color | Black (#000000) |
| Line spacing | 1.15 (single+) |
| Paragraph spacing | 6pt after |
| Alignment | Justified |
| First line indent | None (use spacing between paragraphs) |

### 3.4 Special Text Formatting
| Format | Usage | Example |
|--------|-------|---------|
| **Bold** | Key terms, parameter names, important values, technical specs | **tensió admissible**, **Qa= 3.50 Kg/cm²** |
| *Italic* | Scientific names, document titles, H3 headers, notes | *superficialment es detecta un tram de sòls vegetals* |
| Underline | H1 section headers only | Never in body text |
| Superscript | Units with exponents | kg/cm², m³, SO₄ |
| Subscript | Chemical formulas, indices | N₂₀, N₃₀, CO₂ |

### 3.5 Colors
| Usage | Color Name | Hex Code | RGB |
|-------|------------|----------|-----|
| Primary (headers, accents) | G3 Green | #4A7C59 | 74, 124, 89 |
| Secondary (table headers) | Light Green | #8FBC8F | 143, 188, 143 |
| Body text | Black | #000000 | 0, 0, 0 |
| Table alternating rows | Light Gray | #F5F5F5 | 245, 245, 245 |
| Page numbers box | G3 Green | #4A7C59 | 74, 124, 89 |

### 3.6 Bullet Points & Lists
| Type | Style | Indent |
|------|-------|--------|
| First level | Solid bullet (•) | 0.5 cm |
| Second level | Dash (-) | 1.0 cm |
| Numbered | 1., 2., 3. | 0.5 cm |

### 3.7 Paragraph Styles Summary (Word Style Names)
```
Normal          - 11pt Calibri, justified, 1.15 spacing
Heading 1       - 14pt Calibri Bold Green Underlined CAPS
Heading 2       - 12pt Calibri Bold Green
Heading 3       - 11pt Calibri Italic
Caption         - 10pt Calibri, centered below figure/table
Table Header    - 11pt Calibri Bold White on Green background
Table Body      - 10pt Calibri, left-aligned
Footer          - 9pt Calibri, centered
Header          - 10pt Calibri, with page number in green box
```

---

## 4. TABLES FORMAT

### 4.1 Table Styles

**Standard Data Table (most common)**
```
┌─────────────────────────────────────────────┐
│ Header Row (green background, white text)   │
├─────────────────┬───────────────────────────┤
│ Column 1        │ Column 2                  │
├─────────────────┼───────────────────────────┤
│ Data            │ Data                      │
└─────────────────┴───────────────────────────┘
```

**Simple Two-Column Table (parameters)**
```
┌─────────────────────────────────────┬───────┐
│ Parameter name (bold, left)         │ Value │
├─────────────────────────────────────┼───────┤
│ Parameter name                      │ Value │
└─────────────────────────────────────┴───────┘
```

### 4.2 Table Formatting Specifications

| Property | Header Row | Body Rows |
|----------|------------|-----------|
| Background | G3 Green (#4A7C59) | White / Alt: Light Gray (#F5F5F5) |
| Text color | White (#FFFFFF) | Black (#000000) |
| Font | Calibri Bold | Calibri Regular |
| Size | 10-11pt | 10pt |
| Alignment | Center | Left (text), Center (numbers) |
| Cell padding | 0.2 cm all sides | 0.1 cm all sides |
| Borders | 1pt solid gray | 0.5pt solid light gray |

### 4.3 Table Borders & Lines
| Element | Style | Width | Color |
|---------|-------|-------|-------|
| Outer border | Solid | 1pt | Dark gray (#666666) |
| Header separator | Solid | 1pt | Dark gray (#666666) |
| Row separators | Solid | 0.5pt | Light gray (#CCCCCC) |
| Column separators | Solid | 0.5pt | Light gray (#CCCCCC) |

### 4.4 Table Numbering & Captions
- Format: `Taula X. Description of table contents.`
- Position: **BELOW** the table
- "Taula X" in **bold**
- Description in normal text
- Font: 10pt Calibri
- Spacing: 6pt above caption

### 4.5 Common Tables in Report
| Table # | Content | Location | Type |
|---------|---------|----------|------|
| Taula 1 | Dades principals edificació | Section 1.1 | Simple 2-col |
| Taula 2 | Classificació CTE | Section 1.2 | Simple 2-col |
| Taula 3-5 | Resum assaigs in-situ | Section 2.4.X | Multi-col data |
| Taula 6 | Assaigs laboratori | Section 2.5 | Multi-col data |
| Taula 7 | Permeabilitat materials | Section 3.3.3 | 3-col data |
| Taula 8 | Agressivitat (sulfats) | Section 3.4 | Multi-col data |
| Taula 9 | Coeficient C sísmic | Section 3.6 | Multi-col data |
| Taula 10 | Característiques geotècniques | Section 4.1 | Multi-col data |

> **Note:** Table numbering is sequential. If some sections are omitted, table numbers adjust accordingly.

---

## 5. FIGURES FORMAT

### 5.1 Figure Types
| Type | Format | Source | Example |
|------|--------|--------|---------|
| Location maps | JPEG/PNG | ICGC, ortophoto | Figura 1 |
| Site plan | JPEG/PNG | Google Earth, aerial | Figura 2 |
| Technical diagrams | Vector (Freehand) | Internal | Cullera SPT |
| Geological maps | JPEG/PNG | ICGC, IGME | Figura 4 |
| Cross-sections | Vector (Freehand) | Internal | Tall correlació |
| Photos | JPEG | Field camera | Fotografies |
| Charts/Graphs | Excel/Vector | Internal | DPSH graphs |

### 5.2 Figure Formatting
| Property | Value |
|----------|-------|
| Alignment | Center |
| Max width | Page width minus margins (~16cm) |
| Resolution | Minimum 150 DPI |
| Border | None (or 0.5pt gray if needed) |
| Spacing before | 12pt |
| Spacing after | 6pt (before caption) |

### 5.3 Caption Format
- **Figures**: `Figura X. Description (source, year, modificat).`
- **Photos**: `Fotografia X. Description.`
- **Graphs**: `Gràfic X. Description.`
- Position: **BELOW** the figure
- "Figura X" / "Fotografia X" / "Gràfic X" in **bold**
- Font: 10pt Calibri
- Alignment: Centered or left-aligned (consistent within document)
- Attribution: Include source in parentheses when external

### 5.4 Photo Formatting (in-text)
| Property | Value |
|----------|-------|
| Size | ~8-10cm width typically |
| Border | Optional thin gray border |
| Caption | Below, "Fotografia X. Description." |

### 5.5 Common Figures
| Figure # | Content | Section | Source |
|----------|---------|---------|--------|
| Figura 1 | Situació zona d'estudi (2 maps) | 1.1 | ICGC |
| Figura 2 | Emplaçament assaigs | 2.2 | Google Earth / ortophoto |
| Figura 3 | Cullera normalitzada SPT | 2.4.X | Technical reference |
| Figura 4 | Mapa geològic | 3.1 | ICGC/IGME |
| Figura 5 | Tall de correlació | 4.1 | Internal (Freehand) |
| Figura 6-7 | Àbacs estabilitat | 4.5 | Hoek & Bray (optional) |

> **Note:** Figure numbering is sequential. Photos in annexes use F-1, F-2, etc.

### 5.6 Extracted Image Assets

From PDF analysis using [PDFCrowd Inspect](https://pdfcrowd.com/inspect-pdf/), the following reusable assets were extracted from sample 3001631 (Rubí):

| Asset | File | Description | Use in Template |
|-------|------|-------------|-----------------|
| **G3 Logo** | `g3-logo-circular.png` | Circular green logo with "G3" text | Header (1cm), cover |
| **25 anys Banner** | `25-anys-banner.png` | Horizontal banner with "Compromesos amb el teu projecte" tagline | Cover page (top, full width) |
| **G3 Watermark** | `g3-watermark.png` | Light green large "G3" text | Cover page background |
| **Company Stamp** | `company-stamp.png` | Round seal with company details | Signature page |
| **Signatures** | `signature-1/2/3.png` | Handwritten signatures | Signature page |
| **Cross-section** | `cross-section-example.png` | Geological correlation diagram (P-1, P-2, P-3) | Annex 4 (reference) |
| **Granulometry** | `granulometry-chart-example.png` | Pie chart (graves/sorres/fins) in green tones | Section 3 (reference) |
| **DPSH Diagram** | `dpsh-probe-diagram.png` | Technical schematic of probe cone | Section 2.4 |
| **Geological Map** | `geological-map-example.png` | Example with legend (Llegenda) | Figure 3-4 (reference) |
| **Soilassaig Logo** | `soilassaig-logo.png` | External testing lab logo | Lab certificates |

**Asset Location:** `templates/assets/`

**PDF Metadata (3001631):**
- PDF Version: 1.7
- Created with: Microsoft Word for Microsoft 365
- Fonts: 49 embedded (Arial, Calibri, Times New Roman variants)
- Font size: 505 KB (26% of file)
- Total images: 34

**Notes:**
- DPSH penetration graphs (N₂₀ vs depth) are vector graphics, not raster - need to be generated programmatically
- Cross-section diagrams are vector (created in Freehand) - template generator should create similar

---

## 6. MAIN REPORT SECTIONS

### 6.1 Section 1: PRESENTACIÓ DE L'ESTUDI

**1.1 ANTECEDENTS**
- Opening: "A petició de: [client]"
- Standard intro paragraph referencing CTE
- Building characteristics table
- Location maps (2 side-by-side: topographic + ortophoto)

**1.2 CLASSIFICACIÓ DE L'OBRA SEGONS EL CTE**
- Classification table with:
  - Tipus d'edificació considerada: C-0/C-1/C-2/etc
  - Tipus de sòl considerat: T-1/T-2/T-3

**1.3 OBJECTIUS**
- Bulleted list of study objectives (standard text)

### 6.2 Section 2: TREBALLS DE CAMP

**2.1 DESCRIPCIÓ DE LA ZONA D'ESTUDI**
- Date of field visit
- 2.1.1 Descripció parcel·les adjacents (N/S/E/W)
- 2.1.2 Descripció del solar

**2.2 RECONEIXEMENT DEL TERRENY**
- Bulleted list of tests performed
- Reference to annexes
- Location figure

**2.3 JUSTIFICACIÓ DE COMPLIMENT DE CTE**
- Standard compliance statement

**2.4 DESCRIPCIÓ DELS ASSAIGS IN SITU**
> **Note:** Subsections vary based on tests performed. Not all projects require all test types.

- 2.4.1 Assaigs de penetració tipus "DPSH" - **ALWAYS PRESENT** (with specs + photo)
- 2.4.2+ **VARIABLE** - One or more of the following:
  - Sondeig a rotació amb bateria continua - when detailed borehole performed
  - Assaig tipus S.P.T. (Standard Penetration Test) - when SPT performed
  - *Absent* - when only DPSH tests performed
  - **Note:** Sondeig and SPT can appear as SEPARATE subsections (2.4.2, 2.4.3) or combined
- 2.4.X Resum dels assaigs in-situ realitzats - **ALWAYS PRESENT** (tables for each test type)

**Test Combinations Observed:**
| Sample | DPSH | 2.4.2+ Content | Subsection numbering |
|--------|------|----------------|---------------------|
| 3001621 | ✅ | Sondeig rotació + SPT | 2.4.1, 2.4.2 (Sondeig), 2.4.3 (SPT), 2.4.4 (Resum) |
| 3001631 | ✅ | *(absent)* | 2.4.1 (DPSH), 2.4.2 (Resum) |
| 4001607 | ✅ | Assaig tipus S.P.T. | 2.4.1 (DPSH), 2.4.2 (SPT), 2.4.3 (Resum) |
| 4001612 | ✅ | Sondeig + SPT (separate) | 2.4.1 (DPSH), 2.4.2 (Sondeig), 2.4.3 (SPT), 2.4.3* (Resum) |

> **Note:** Sample 4001612 has a numbering error in the original - two sections labeled 2.4.3 (SPT and Resum). This should be 2.4.4 for Resum.

**2.5 ASSAIGS DE LABORATORI**
- Summary table of lab tests

### 6.3 Section 3: DESCRIPCIÓ GEOLÒGICA I GEOTÈCNICA

**3.1 MARC GEOLÒGIC**
- Regional geology description
- References to ICGC, IGME maps
- Geological map figure

**3.2 CARACTERITZACIÓ DELS MATERIALS**
> **Note:** Number of levels (Nivell 1, Nivell 2, etc.) varies by site geology. Simple sites may have only 1 level.

- Per-level description (3.2.1, 3.2.2, etc.):
  - Descripció litològica (with sample photo)
  - Localització
  - Resistència

**Levels Observed:**
| Sample | Nivells | Materials |
|--------|---------|-----------|
| 3001621 | 2+ | Multiple geological layers |
| 3001631 | 1 | Graves i sorres carbonatades |
| 4001607 | 2 | Llims argilosos + Lutites i sorrenques |
| 4001612 | 1 | Graves en matriu sorrenca carbonatades |

**3.3 HIDROLOGIA I HIDROGEOLOGIA**
- 3.3.1 Hidrogeologia superficial
- 3.3.2 Hidrogeologia subterrània (sometimes "Hidrogeologia subterrània i geotèrmia")
- 3.3.3 Permeabilitat (table with K values)

**3.4 AGRESSIVITAT DEL MEDI**
- Sulfate content table
- CE-21 classification

**3.5 EXCAVABILITAT**
- Equipment recommendations

**3.6 ACCELERACIÓ SISMICA DE REFERÈNCIA**
- NCSE-02 parameters
- Formulas: AB, AC, S, C, ρ
- Terrain coefficient table

**3.7 EXPOSICIÓ AL GAS RADÓ**
- CTE HS-6 requirements
- Zone classification

### 6.4 Section 4: CONCLUSIONS

> **Note:** Conclusions structure varies based on project-specific conditions. Sections are numbered sequentially, so if 4.3 is Expansivitat, Fonamentació becomes 4.4.

**4.1 GEOLOGIA** - **ALWAYS PRESENT**
- Summary of materials
- Correlation cross-section figure
- Geotechnical parameters table

**4.2 HIDROGEOLOGIA I AGRESSIVITAT** - **ALWAYS PRESENT**
- Water table findings
- Aggressivity classification

**4.3 VARIABLE** - One of:
- **FONAMENTACIÓ** (standard case) - Foundation recommendation, Qa, settlements
- **EXPANSIVITAT DELS MATERIALS** (when expansive soils present) - Summary of Lambe test, swelling pressure, recommendations

**4.4 VARIABLE** - One of:
- **FONAMENTACIÓ** (if 4.3 was Expansivitat)
- **EMPENTES DE TERRES** (if 4.3 was Fonamentació and retaining walls involved)
- *Absent* (simple projects)

**4.5 ESTABILITAT DEL VESSANT** - **OPTIONAL**
- Slope stability analysis
- Hoek & Bray method reference
- Safety factor
- Only included if site has significant slopes

**Conclusions Sections Observed:**
| Sample | 4.1 Geologia | 4.2 Hidrogeo | 4.3 | 4.4 | 4.5 | Project Type |
|--------|--------------|--------------|-----|-----|-----|--------------|
| 3001621 | ✅ | ✅ | Fonamentació | Empentes | Estabilitat | Multi-story with slope |
| 3001631 | ✅ | ✅ | Fonamentació | ❌ | ❌ | Simple single-family, flat |
| 4001607 | ✅ | ✅ | **Expansivitat** | Fonamentació | ❌ | Single-family, expansive soils |
| 4001612 | ✅ | ✅ | Fonamentació | ❌ | ❌ | Simple single-family, flat |

> **Note:** Section 4.3 can be EITHER "Fonamentació" (when no significant expansivity) OR "Expansivitat dels materials" (when expansivity is a concern). When 4.3 is Expansivitat, Fonamentació moves to 4.4.

### 6.5 Signature Page
```
G3 D T S.L. sol·licita que si es detectessin anomalies...

Informe geològic / geotècnic,
Expedient Núm.: [number]

[Location], [date in text format]

[Company stamp]

[Name]
[Title] col [number]
[Role]
```

---

## 7. ANNEXES STRUCTURE

### 7.1 Annex Dividers
- Full page with curved green design (bottom-right)
- Annex title in green (bottom-right area)

### 7.2 BASE DE CÀLCUL (~3 pages)
- Calculation methodology
- Terzaghi formulas
- Settlement calculation method

### 7.3 REGISTRE D'ASSAIGS MECÀNICS (3-6 pages, varies by number of tests)
**DPSH Test Sheets (1 per test point)** - **ALWAYS PRESENT**
- Header: Test ID, location, date
- Data table: Depth vs N20 vs NB
- Graph: Depth profile
- Legend with soil levels

**Sondeig Log Sheet** - **OPTIONAL** (only if full borehole performed)
- Complex multi-column format
- Borehole profile
- Sample locations
- SPT values

**Sample Photos Page** - **CONDITIONAL**
- Photos of machine and sample box/materials
- May be included in DPSH sheets or separately

### 7.4 ESQUEMA SITUACIÓ ASSAIGS (1 page)
- Combined layout:
  - Regional location maps (left)
  - Detailed site plan with test points (right)
- Legend with symbols
- Scale bar

### 7.5 TALL DE CORRELACIÓ (1 page)
- Cross-section diagram
- Soil layers with colors
- Test points marked
- Elevation scale
- Recommended foundation level (dashed line)

### 7.6 FOTOGRAFIES (~2 pages)
- 2 photos per page
- Photo number (F-1, F-2, etc.)
- Caption below

### 7.7 ACTES D'ASSAIG DE LABORATORI (~5 pages)
- External lab reports (Soilassaig format)
- Digital signatures
- Test results

---

## 8. VARIABLE DATA FIELDS

### 8.1 Project-Specific
| Field | Example | Source |
|-------|---------|--------|
| EXPEDIENT | 3001621 | Internal numbering |
| CLIENT | [name] | Client data |
| DATA | 21/11/25 | Report date |
| OBRA | Estudi geològic... | Project description |
| LOCATION | CASTELLAR DEL VALLÈS | Municipality |
| UTM | 423182.0 E / 4609623.0 N | Coordinates |

### 8.2 Technical Parameters
| Parameter | Units | Sample 1 | Sample 2 | Sample 3 | Sample 4 |
|-----------|-------|----------|----------|----------|----------|
| Qa (tensió admissible) | kg/cm² | 3.0 | 3.50 | 3.0 | 3.0 |
| Assentaments | cm | <1.0 | <1.50 | <1.0 | <1.20 |
| K30 (coef. balast) | kg/cm³ | 8.00 | 6.0 | - | - |
| AB (accel. sísmica) | g | 0.04 | 0.08 | <0.04 | <0.04 |
| Sulfats | mg/kg SO₄ | 0.0 | 632.3 | 0.0 | 89.8 |
| Radó zone | 1/2 | ZONA 1 | ZONA 1 | No (not listed) | ZONA 1 |
| CTE Edificació | C-0/C-1/C-2 | C-1 | C-0 | C-0 | C-1 |
| CTE Sòl | T-1/T-2/T-3 | T-1 | T-1 | T-1 | T-1 |
| Expansivitat (Lambe) | - | - | - | Marginal | - |
| Pressió inflament | kg/cm² | - | - | 0.82 | - |

### 8.3 Test Results
- DPSH: NB values per depth
- SPT: N30 values
- Sondeig: Depth, samples, water level

---

## 9. OUTPUT FORMAT REQUIREMENTS

### 9.1 File Naming
```
{expedient}_informe.pdf
```

### 9.2 Page Size
- A4 (210 × 297 mm)

### 9.3 Color Scheme
- Primary green: ~#4A7C59 (G3 brand)
- Secondary: Light green for backgrounds
- Tables: Green headers, gray alternating rows

### 9.4 Quality
- Images: Minimum 150 DPI
- Maps: Clear legends, scale bars
- Graphs: Labeled axes, units

---

## 10. AUTOMATION CONSIDERATIONS

### 10.1 Template Sections (mostly static)
- Cover page layout
- Header/footer
- Section headers and standard text
- Base de càlcul (formulas)
- Test descriptions (DPSH, SPT, Sondeig)

### 10.2 Variable Sections (require data input)
- Project metadata
- Location descriptions
- Test results tables
- Geological descriptions (site-specific)
- Parameter calculations
- Conclusions/recommendations

### 10.3 Generated Content
- Figures (maps from ICGC)
- Graphs (from test data)
- Cross-sections (from test locations)
- Lab reports (external documents)

---

## 11. VALIDATION LOG

| Version | Date | Samples Validated | Changes |
|---------|------|-------------------|---------|
| v1.0 | 2026-01-01 | 3001621 | Initial template extraction |
| v1.1 | 2026-01-01 | 3001631 | Added optional markers for 2.4.2 (Sondeig), 4.4 (Empentes), 4.5 (Estabilitat); variable material levels; page count ranges |
| v1.2 | 2026-01-01 | 4001607 | Section 2.4.2 can be SPT OR Sondeig; Section 4.3 can be Expansivitat (pushing Fonamentació to 4.4); added expansivity parameters to tech params |
| v1.3 | 2026-01-01 | 4001612 | New test combo: DPSH+Sondeig+SPT as separate subsections; noted numbering error (duplicate 2.4.3); 3.3.2 may include "geotèrmia"; confirmed simple project pattern (4.1-4.3 only) |
| v1.4 | 2026-01-01 | All 4 | Added Section 1B: Decision Tree analysis explaining WHY sections vary based on project characteristics (CTE class, soil type, terrain, design requirements) |
| v1.5 | 2026-01-01 | All 4 | Added Section 0: Regulatory Framework (CTE DB SE-C, UNE/ISO test standards, related regulations) |

---

*Template spec v1.5 - Validated with samples: 3001621_informe.pdf, 3001631_informe.pdf, 4001607_informe.pdf, 4001612_informe.pdf*
*Last Updated: 2026-01-01*
