# Plan: Complete Catalunya Municipal Data Extraction

**Objective:** Extract authoritative seismic (ab) and radon zone data for all 947 Catalunya municipalities with full source tracking.

**Value:** One-time effort → hundreds of reports with accurate, citable data.

---

## Data Requirements

### 1. Radon Zones (CTE DB HS6)

| Field | Description | Source |
|-------|-------------|--------|
| `municipality` | Official municipality name | INE |
| `province` | Barcelona, Girona, Lleida, Tarragona | INE |
| `radon_zone` | 0, 1, or 2 | CTE DB HS6 Apéndice B |
| `source` | "CTE DB HS6 Apéndice B (RD 732/2019)" | - |
| `source_date` | "2019-12-27" | BOE publication date |

**Zone definitions:**
- Zone 0: Not listed in Apéndice B (< 300 Bq/m³, no protection required)
- Zone 1: Listed, moderate risk (300-600 Bq/m³, basic protection)
- Zone 2: Listed, high risk (> 600 Bq/m³, enhanced protection required)

### 2. Seismic Acceleration (NCSE-02)

| Field | Description | Source |
|-------|-------------|--------|
| `municipality` | Official municipality name | INE |
| `province` | Barcelona, Girona, Lleida, Tarragona | INE |
| `ab` | Basic seismic acceleration (g) | NCSE-02 Annex 1 |
| `K` | Contribution coefficient | NCSE-02 Annex 1 |
| `source` | "NCSE-02 Annex 1" | - |
| `source_date` | "2002-10-11" | BOE publication date |

**Note:** NCSE-02 only lists municipalities with ab ≥ 0.04g. Unlisted municipalities default to 0.04g.

---

## Source Documents

### Primary Sources

1. **CTE DB HS6 Apéndice B** (Radon)
   - Legal: RD 732/2019, de 20 de diciembre
   - BOE: BOE-A-2019-18528
   - URL: https://www.boe.es/eli/es/rd/2019/12/20/732
   - Format: PDF (two-column layout by province)
   - Location: Downloaded to `/tmp/cte_municipios.pdf`

2. **NCSE-02 Annex 1** (Seismic)
   - Legal: RD 997/2002, de 27 de septiembre
   - BOE: BOE-A-2002-19687
   - URL: https://www.boe.es/eli/es/rd/2002/09/27/997
   - Format: PDF (tabular by autonomous community)
   - Status: Need to download

### Reference Sources

3. **INE Municipality Codes** (Official names)
   - URL: https://www.ine.es/daco/daco42/codmun/codmun.htm
   - Format: Excel/CSV
   - Purpose: Canonical municipality names and codes

4. **CSN Radon Potential Map** (Verification)
   - URL: https://www.csn.es/mapa-del-potencial-de-radon-en-espana
   - Format: FileGeoDatabase (downloaded)
   - Purpose: Cross-reference for quality assurance

---

## Extraction Plan

### Step 1: Get Canonical Municipality List (Foundation)

**Goal:** Official list of all 947 Catalunya municipalities with INE codes.

**Source:** INE (Instituto Nacional de Estadística)

**Actions:**
1. Download INE municipality list
2. Filter for Catalunya (provinces 08, 17, 25, 43)
3. Create master list with: INE code, name, province

**Output:** `data/municipalities_catalunya_ine.json`

```json
{
  "metadata": {
    "source": "INE - Relación de municipios y códigos por provincias",
    "url": "https://www.ine.es/daco/daco42/codmun/codmun.htm",
    "extracted_date": "2026-02-04",
    "total_municipalities": 947
  },
  "municipalities": [
    {"ine_code": "08001", "name": "Abrera", "province": "Barcelona"},
    ...
  ]
}
```

---

### Step 2: Extract Radon Zones from CTE PDF

**Goal:** Parse CTE DB HS6 Apéndice B to get Zone 1 and Zone 2 municipalities.

**Challenge:** Two-column PDF layout (Zone 1 left, Zone 2 right)

**Strategy:**
1. Use pdfplumber with table extraction mode
2. Process page by page, identifying Catalunya sections
3. Separate left column (Zone 1) from right column (Zone 2)
4. Match extracted names against INE canonical list

**Quality Assurance:**
- Cross-reference with rado.cat list (175 Zone 2, 325 Zone 1 for Catalunya)
- Verify counts match official statistics
- Flag any unmatched names for manual review

**Output:** `data/radon_zones_catalunya.json`

```json
{
  "metadata": {
    "source": "CTE DB HS6 Apéndice B",
    "legal_reference": "RD 732/2019",
    "boe": "BOE-A-2019-18528",
    "source_date": "2019-12-27",
    "extracted_date": "2026-02-04",
    "zone_1_count": 325,
    "zone_2_count": 175
  },
  "zone_1": ["Abrera", "Aiguafreda", ...],
  "zone_2": ["Alella", "Arenys de Mar", ...]
}
```

---

### Step 3: Download and Extract NCSE-02 Seismic Data

**Goal:** Get ab values for Catalunya municipalities from NCSE-02 Annex 1.

**Actions:**
1. Download NCSE-02 PDF from BOE
2. Locate Catalunya section (Cataluña / Catalunya)
3. Extract: Municipality, ab (g), K coefficient
4. Match against INE canonical list

**Note:** Most Catalunya municipalities have ab = 0.04g (minimum). Higher values in:
- Pyrenees (Girona, Lleida): up to 0.07g
- Terres de l'Ebre: up to 0.06g

**Output:** `data/seismic_ab_catalunya.json`

```json
{
  "metadata": {
    "source": "NCSE-02 Annex 1",
    "legal_reference": "RD 997/2002",
    "boe": "BOE-A-2002-19687",
    "source_date": "2002-10-11",
    "extracted_date": "2026-02-04",
    "default_ab": 0.04,
    "note": "Municipalities not listed default to ab = 0.04g"
  },
  "municipalities": {
    "Olot": {"ab": 0.07, "K": 1.0},
    "Ripoll": {"ab": 0.07, "K": 1.0},
    "Figueres": {"ab": 0.06, "K": 1.0},
    ...
  }
}
```

---

### Step 4: Merge and Create Final Lookup Table

**Goal:** Single consolidated file with all data for each municipality.

**Actions:**
1. Start with INE canonical list (947 municipalities)
2. Add radon zone (0 if not in Zone 1/2 lists)
3. Add seismic ab (0.04 if not listed in NCSE-02)
4. Add all source tracking metadata

**Output:** `automation/data/catalunya_municipal_data.json`

```json
{
  "metadata": {
    "description": "Municipal regulatory data for G3DT geotechnical reports",
    "coverage": "Catalunya (947 municipalities)",
    "created_date": "2026-02-04",
    "sources": {
      "municipalities": {
        "source": "INE",
        "date": "2026"
      },
      "radon": {
        "source": "CTE DB HS6 Apéndice B (RD 732/2019)",
        "date": "2019-12-27"
      },
      "seismic": {
        "source": "NCSE-02 Annex 1 (RD 997/2002)",
        "date": "2002-10-11"
      }
    }
  },
  "municipalities": {
    "Abrera": {
      "ine_code": "08001",
      "province": "Barcelona",
      "radon_zone": 1,
      "seismic_ab": 0.04,
      "seismic_K": 1.0
    },
    ...
  }
}
```

---

### Step 5: Update Code to Use New Data File

**Goal:** Replace hardcoded dictionaries with JSON file lookup.

**Actions:**
1. Create `automation/data/` directory
2. Move JSON file there
3. Update `municipal_data.py` to load from JSON
4. Update source citation in report generators
5. Add data file versioning

**Code changes:**
```python
# municipal_data.py
import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "catalunya_municipal_data.json"

def _load_data():
    with open(DATA_FILE) as f:
        return json.load(f)

_DATA = None

def get_data():
    global _DATA
    if _DATA is None:
        _DATA = _load_data()
    return _DATA
```

---

### Step 6: Quality Assurance

**Goal:** Verify extracted data is accurate.

**Checks:**
1. **Count verification:**
   - Total municipalities = 947
   - Radon Zone 1 ≈ 325
   - Radon Zone 2 ≈ 175
   - Radon Zone 0 ≈ 447

2. **Spot checks:**
   - Verify known municipalities (Bell-Lloc, Rubí, Olot) match expected values
   - Cross-reference with CSN interactive map for 10 random municipalities

3. **Name matching:**
   - Identify any INE names not matched to CTE/NCSE-02
   - Flag spelling variations for manual review

4. **Edge cases:**
   - Municipalities with accents (Rubí vs Rubi)
   - Compound names (Sant Cugat del Vallès)
   - Name changes since 2002

---

## Execution Order

| Step | Description | Estimated Effort | Dependencies |
|------|-------------|------------------|--------------|
| 1 | Download INE municipality list | 30 min | None |
| 2 | Extract radon zones from CTE PDF | 2-3 hours | Step 1 |
| 3 | Download and extract NCSE-02 seismic | 1-2 hours | Step 1 |
| 4 | Merge into final lookup table | 1 hour | Steps 2, 3 |
| 5 | Update code to use new data | 1 hour | Step 4 |
| 6 | Quality assurance | 1-2 hours | Step 5 |

**Total estimated effort:** 6-10 hours

---

## Risk Mitigation

1. **PDF parsing fails:** Fall back to manual transcription for affected sections
2. **Name mismatches:** Create alias mapping for common variations
3. **Missing data:** Document gaps and use conservative defaults
4. **Future updates:**
   - Radon: CTE updates are rare (major code revisions)
   - Seismic: New norm expected (NCSE-24?) - will require full update

---

## Deliverables

1. `data/municipalities_catalunya_ine.json` - Canonical municipality list
2. `data/radon_zones_catalunya.json` - Raw radon extraction
3. `data/seismic_ab_catalunya.json` - Raw seismic extraction
4. `automation/data/catalunya_municipal_data.json` - Final merged lookup
5. `automation/municipal_data.py` - Updated code
6. `docs/DATA-SOURCES.md` - Documentation of all sources

---

## Notes

- All data will be stored in the G3DT project under version control
- Source PDFs should be archived for reference
- Update process should be documented for future maintainers
- Consider adding automated tests for data integrity

---

*Plan created: 2026-02-04*
*Status: Ready for execution*
