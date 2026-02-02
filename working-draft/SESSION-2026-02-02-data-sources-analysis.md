# G3DT Data Sources Analysis
## Session: 2026-02-02

**Source Document:** `EXPLICACIÓ DETALLS.docx` from client (34 images with annotations)
**Example Project:** 4001612 Bell-Lloc

---

## 1. Project Folder Structure (Documented)

```
{expedient} {POBLACIO}/
├── {expedient}_informe.doc              # Clean final report
├── {expedient}_informe_DETALLAT.doc     # Annotated version (for training)
├── {expedient}_PORTADA_25.doc           # Cover page
├── ACCEPTACIO/
│   ├── DADES CLIENT.txt                 # Client data (name, NIF, address, phone, email)
│   └── PRESSUPOST GEOTEC.{poblacio}.pdf # Signed quote/budget
├── ANNEXES/
│   ├── {expedient}_DPSH.xls             # DPSH test results (Excel with formulas)
│   ├── {expedient}_fotografies.FH11     # Photos (FreeHand vector)
│   ├── {expedient}_plànol de situació.FH11
│   ├── {expedient}_sondeig.FH11         # Drilling log (FreeHand)
│   └── {expedient}_tall de correlació.FH11
├── FOTOGRAFIES/
│   ├── DPSH/                            # Penetration test photos (P1.jpg, P2.jpg, etc.)
│   ├── SONDEIG/                         # Drilling photos
│   └── WhatsApp images                  # Field photos
├── PDF/
│   ├── {expedient}_informe.pdf          # Final report PDF
│   ├── ANNEXES/
│   │   ├── {expedient}_DPSH.pdf
│   │   ├── {expedient}_sondeig.pdf
│   │   ├── {expedient}_fotografies.pdf
│   │   ├── {expedient}_plànol de situació.pdf
│   │   ├── {expedient}_tall de correlació.pdf
│   │   └── LAB-SIG.pdf                  # Signed lab results
│   └── LLETRA/                          # ?
├── PDF V0/                              # Draft PDFs
├── {any}.{num}/                         # Field data folder (e.g., 25.0647)
│   ├── DADES PER ANAR A CAMP_v1.xlsx    # Field data planning
│   ├── PLAN_COST_{poblacio}.xlsx        # Cost planning
│   └── Cadastral PDFs
└── Various PDFs (maps, sections, penetration results, drilling logs)
```

---

## 2. Data Source Mapping

Based on `EXPLICACIÓ DETALLS.docx`, here's where each data field comes from:

### 2.1 Project Identification
| Field | Source | Notes |
|-------|--------|-------|
| Expedient number | Folder name | First part of folder name |
| Població | Folder name | Second part of folder name |

### 2.2 Client Data
| Field | Source | Notes |
|-------|--------|-------|
| Client name | `ACCEPTACIO/DADES CLIENT.txt` or email | Also in PRESSUPOST |
| Client NIF | `ACCEPTACIO/DADES CLIENT.txt` | |
| Client address | `ACCEPTACIO/DADES CLIENT.txt` | |
| Client phone | `ACCEPTACIO/DADES CLIENT.txt` | |
| Client email | `ACCEPTACIO/DADES CLIENT.txt` | |

### 2.3 Location & Site Data
| Field | Source | Notes |
|-------|--------|-------|
| Carrer/Direcció | Budget request email | Sometimes in attached plans |
| Referència cadastral | ICGC viewer or Cadastre | Unique parcel identifier |
| UTM Coordinates | ICGC viewer | From parcel location |
| Site description | Visual observation | Google Maps/Earth Street View |
| Adjacent parcels | Visual observation | N/S/E/W descriptions |

**ICGC Viewer:** https://visors.icgc.cat/vissir/
- Format for search: `{carrer}, {població}`
- Click on parcel to get coordinates
- Link to Cadastre for parcel details

### 2.4 Building Classification
| Field | Source | Criteria |
|-------|--------|----------|
| CTE Classification | Budget request | C0: <300m² and <4 floors |
| | | C1: >300m² and <4 floors |
| | | C2: ≥4 floors (up to 10) |
| Superfície parcel·la | Budget request / plans | |
| Superfície construïda | Budget request / plans | |
| Número plantes | Budget request | Including basements |

### 2.5 Field Work Data
| Field | Source | Notes |
|-------|--------|-------|
| Data treballs camp | DPSH PDF in ANNEXES | Date on test sheet |
| Sondeig date | May differ from DPSH | Check both, report both if different |

### 2.6 Geological Data
| Field | Source | Notes |
|-------|--------|-------|
| Geologia regional | ICGC viewer (layers) | Screenshot from viewer |
| Descripció visual | Field observations | From photos, Google Earth |
| Nivells del terreny | DPSH/Sondeig results | Depth, color, material type |

### 2.7 Test Results
| Field | Source | Notes |
|-------|--------|-------|
| DPSH N20 values | `ANNEXES/{expedient}_DPSH.xls` | Per depth interval |
| SPT N values | Sondeig records | From drilling log |
| Profunditat assaigs | DPSH/Sondeig PDFs | Max depth reached |
| Nivell freàtic | DPSH/Sondeig PDFs | Water level if encountered |

### 2.8 Lab Results
| Field | Source | Notes |
|-------|--------|-------|
| Granulometria | Lab reports or `comanda laboratori.xls` | If reports not ready, use request Excel |
| Límits Atterberg | Lab reports | |
| Sulfats | Lab reports | For aggressivity |
| Lambe (expansivity) | Lab reports | If clay soils |

### 2.9 Photos
| Field | Source | Notes |
|-------|--------|-------|
| Site photos | `FOTOGRAFIES/` folder | Or PDF in ANNEXES |
| DPSH photos | `FOTOGRAFIES/DPSH/` | P1.jpg, P2.jpg, etc. |
| Sondeig photos | `FOTOGRAFIES/SONDEIG/` | Sample box photos |
| Core samples | Various naming | Matched to depth in description |

---

## 3. Zone-Specific Templates

The client mentioned having zone-specific Word files for geological descriptions stored on their server. These contain:
- Regional geology text per zone
- Typical soil descriptions
- Local references

**Location:** Server (path unknown - need to request)

---

## 4. Color Coding in EXPLICACIÓ DETALLS

- **Green (BRIGHT_GREEN):** Fixed text that doesn't change between reports
- **Yellow:** Variable text that changes per project
- **Gray:** Notes and instructions

---

## 5. Client's Proposed Simplification

The client suggested creating a **Word/Excel file with principal data** to simplify input:
- Client name, NIF, address, phone, email
- Location details
- Building classification data
- Field work dates

This would centralize data entry instead of searching multiple sources.

---

## 6. DPSH Excel Analysis

### Structure
- **File:** `ANNEXES/{expedient}_DPSH.xls`
- **Format:** One sheet per test point (P-1, P-2, etc.)
- **Rows:** 80 per sheet, data every 0.2m depth

### Columns
| Col | Name | Description |
|-----|------|-------------|
| A | (empty) | Labels area |
| B | Profunditat de penetròmetre | Depth in meters (negative = below surface) |
| C | Colpeig DPSH | Raw N20 blow count (blows per 20cm) |
| D | Colpeig NB | Normalized blow count |
| E | MESURA DE PAR | Torque measurement (rarely used) |
| F | N.F. | Nivell Freàtic (water level if encountered) |
| G | Nivells | Soil layer designation |

### Key Data
- **Correction factor:** Cell D14 = 0.83 (energy correction)
- **Formula:** NB = N20 / 0.83
- **Refusal:** N20 = 100 indicates test stop (hard layer reached)

### Example Data (4001612)
```
P-1: Refusal at 1.40m depth (N20=100)
P-2: Refusal at 2.60m depth (N20=100)
No water level encountered in either test.
```

### Data Used in Report
- Max penetration depth → Section 2.4 summary tables
- N20/NB values per depth → DPSH annex graphs
- Average N20 per soil level → Section 4.1 geotechnical parameters
- Water level (if present) → Section 4.2 hydrogeology

---

## 7. Gaps / Questions to Resolve

### Still Unknown
1. **Server path** for zone-specific geological templates
2. **Excel formula details** - need to analyze DPSH.xls structure
3. **FreeHand files** - can we generate equivalent PDFs programmatically?
4. **Lab report integration** - how to handle pending vs. received reports?

### Complexity Flags (Client's Notes)
- Cadastre lookup when no street number: "Complicat, caldrà estudiar"
- Geological descriptions by zone: "Se'm fa difícil de comentar"
- Water level comments: Depends on DPSH/Sondeig observations
- Urban vs. rural site descriptions: Different standard paragraphs

---

## 7. Files in Reference Material

```
reference-material/
├── 4001612_informe.doc                  # Sample report (clean)
└── 4001612-bell-lloc/
    ├── EXPLICACIÓ DETALLS.docx          # KEY: Instructions with 34 annotated screenshots
    ├── 4001612_informe.doc              # Same as above
    ├── 4001612_informe_DETALLAT.doc     # Annotated version
    ├── 4001612_PORTADA_25.doc           # Cover
    ├── ACCEPTACIO/
    │   ├── DADES CLIENT.txt             # Client data
    │   └── PRESSUPOST...pdf
    ├── ANNEXES/
    │   ├── 4001612_DPSH.xls             # Test data Excel
    │   └── *.FH11 files                 # FreeHand graphics
    ├── FOTOGRAFIES/
    │   ├── DPSH/
    │   └── SONDEIG/
    ├── PDF/
    │   ├── 4001612_informe.pdf
    │   └── ANNEXES/ (all annex PDFs)
    └── 25.0647/                         # Field data
        ├── DADES PER ANAR A CAMP_v1.xlsx
        └── PLAN_COST_BELL-LLOC.xlsx
```

---

## 8. Next Actions

### Immediate
1. [ ] Analyze DPSH Excel structure (formulas, data layout)
2. [ ] Create data input template (Word/Excel) based on client suggestion
3. [ ] Map each report section to specific data sources
4. [ ] Test extraction from DADES CLIENT.txt format

### Short-term
5. [ ] Request zone-specific geological templates from client
6. [ ] Understand FreeHand → PDF workflow (can we replicate?)
7. [ ] Build prototype that reads from project folder structure

### Questions for Client
- Path to server folder with zone geological templates?
- Can they share the Excel with main data they mentioned creating?
- FreeHand workflow: do they need us to generate these, or just PDFs?

---

*Session notes: Successfully analyzed client's detailed instructions. Clear data source mapping now available. Key insight: most data has defined sources, but some geological descriptions require zone-specific templates stored on their server.*
