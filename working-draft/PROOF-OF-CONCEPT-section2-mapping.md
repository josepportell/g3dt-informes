# Section 2 Data Source Mapping
## Section: 2. TREBALLS DE CAMP

**Sample:** 4001612_informe.docx (Bell-Lloc d'Urgell)

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 🟢 | **STATIC** - Fixed text, same in every report |
| 🟡 | **VARIABLE** - Changes per project |
| 🔵 | **CONDITIONAL** - Included only in certain cases |
| 📊 | **TABLE** - Data table |
| 🖼️ | **FIGURE/PHOTO** - Image |

---

## 2. TREBALLS DE CAMP

### Section Intro

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P097 | 🟢 | `2. TREBALLS DE CAMP` | Static header |
| P099 | 🟡 | `El dia 1 d'octubre de 2025, es va visitar l'obra per tal de:` | |
| | | - Date: `1 d'octubre de 2025` | DPSH PDF date OR `DADES PER ANAR A CAMP.xlsx` |
| P100-103 | 🟢 | Bullet list of visit objectives | Static (same in every report) |

**Visit objectives (always the same):**
- Realitzar una inspecció geològica de la zona
- Dissenyar la campanya de camp
- Comprovar l'accessibilitat de maquinària
- Localitzar els punts on es realitzaran els assaigs

---

### 2.1. DESCRIPCIÓ DE LA ZONA D'ESTUDI

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P106 | 🟢 | `2.1. DESCRIPCIÓ DE LA ZONA D'ESTUDI` | Static header |

#### 2.1.1. Descripció de les parcel·les adjacents

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P108 | 🟢 | `2.1.1. Descripció de les parcel·les adjacents` | Static header |
| P110 | 🟡 | `La parcel·la objecte d'estudi es situa al oest del municipi de Bell-Lloc d'Urgell, pren una morfologia rectangular i limita:` | |
| | | - Position in municipality: `oest` | ICGC viewer / Google Maps |
| | | - Municipality: `Bell-Lloc d'Urgell` | Folder name |
| | | - Parcel shape: `rectangular` | Visual observation / cadastre |
| P112-115 | 🟡 | Adjacent parcels (N/S/E/W) | **Field observation + Google Maps/Earth** |

**Adjacent parcels template:**
```
Per la part est amb {descripció_est}
Per la part sud amb {descripció_sud}
Per la part nord amb {descripció_nord}
I finalment, per la part oest, amb {descripció_oest}
```

**Typical descriptions:**
- `el Carrer [nom]` (street)
- `una parcel·la buida` (empty lot)
- `una parcel·la amb una construcció aïllada de fins a X plantes` (building)
- `terrenys de conreu` (farmland)
- `un edifici plurifamiliar` (apartment building)

| Data Source | Method |
|-------------|--------|
| Google Maps Street View | Visual inspection of N/S/E/W |
| Google Earth | Aerial view for context |
| Field notes | Observations from visit |
| ICGC viewer | Cadastral boundaries |

#### 2.1.2. Descripció del solar

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P117 | 🟢 | `2.1.2. Descripció del solar` | Static header |
| P119 | 🟡 | `El dia dels treballs de camp es realitza l'entrada a la zona d'estudi a través de la del Carrer existent al sud.` | Field observation |
| P121 | 🟡 | Site condition description (level, vegetation, etc.) | Field observation |
| P123 | 🟡 | Nearby constructions observation | Field observation |
| P125 | 🟡 | Soil visibility comment | Field observation |

**Note from `EXPLICACIÓ DETALLS`:** This section varies based on:
- Urban vs. rural setting (different standard paragraphs)
- Whether materials are visible at surface
- Presence of nearby rivers/streams (different hydrogeology comment)

| P128 | 🖼️ | `Fotografia 1 i Fotografia 2. Vistes generals de la zona d'estudi.` | `FOTOGRAFIES/` folder (WhatsApp images) |

---

### 2.2. RECONEIXEMENT DEL TERRENY

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P131 | 🟢 | `2.2. RECONEIXEMENT DEL TERRENY` | Static header |
| P133 | 🟡 | `La campanya de camp, que s'ha realitzat el dia 1 i 6 d'octubre de 2025, ha consistit en la realització de:` | |
| | | - Date(s): `1 i 6 d'octubre de 2025` | DPSH PDF + Sondeig PDF dates |
| | | | **Note:** If DPSH and Sondeig on different days, list both |

#### Test List (Variable based on what was performed)

| P135-139 | 🟡 | List of tests performed | **Count from ANNEXES folder** |

**Template:**
```
{num_dpsh} assaigs de penetració dinàmica tipus DPSH (veure annex "Registre assaigs mecànics").
{num_sondeig} sondeig a rotació amb bateria continua (veure annex "Registre assaigs mecànics"). [CONDITIONAL]
{num_spt} assaig SPT amb recuperació de mostra (veure annex "Registre assaigs mecànics"). [CONDITIONAL]
Observacions de camp realitzades pel tècnic de l'empresa desplaçat a l'obra.
Reportatge fotogràfic (veure annex "Fotografies").
```

| Variable | Data Source |
|----------|-------------|
| `num_dpsh` | Count sheets in `ANNEXES/{expedient}_DPSH.xls` (P-1, P-2, etc.) |
| `num_sondeig` | Check if `{expedient}_sondeig.FH11` exists |
| `num_spt` | Check Sondeig PDF for SPT markers |

| P141 | 🟢 | Lab company accreditation text | Static (TPS PROSPECCIÓ DEL SUBSÒL SL info) |

---

### 2.3. JUSTIFICACIÓ DE COMPLIMENT DE CTE

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P144 | 🟢 | `2.3. JUSTIFICACIÓ DE COMPLIMENT DE CTE` | Static header |
| P146 | 🟢 | CTE compliance statement | **100% STATIC** |

---

### 2.4. DESCRIPCIÓ DELS ASSAIGS IN SITU

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P149 | 🟢 | `2.4. DESCRIPCIÓ DELS ASSAIGS IN SITU` | Static header |

#### 2.4.1. Assaigs de penetració tipus "DPSH" (ALWAYS PRESENT)

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P151 | 🟢 | `2.4.1. Assaigs de penetració tipus "DPSH"` | Static header |
| P153 | 🟢 | DPSH method description | **100% STATIC** (technical explanation) |
| P155 | 🟢 | Refusal criteria | **100% STATIC** |
| P157-162 | 🟢 | Test characteristics list | **100% STATIC** |
| P165 | 🖼️ | `Fotografia 3. Vista de la màquina...` | `FOTOGRAFIES/DPSH/` folder |

**DPSH characteristics (always the same):**
- Alçada de caiguda del Pes: 75 cm
- Diàmetre de la punta de penetració: 51 mm
- Interval de penetració: 20 cm
- Pes: 63.5 Kg

#### 2.4.2. Sondeig a rotació amb bateria continua (🔵 CONDITIONAL)

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P171 | 🔵🟢 | `2.4.2. Sondeig a rotació...` | Static header (if sondeig performed) |
| P173-177 | 🔵🟢 | Sondeig method description | **100% STATIC** |
| P180 | 🔵🖼️ | `Fotografia 4. Vista de la màquina...` | `FOTOGRAFIES/SONDEIG/` folder |

**Inclusion rule:** Only include if sondeig was performed (check for `{expedient}_sondeig.FH11` or `.pdf`)

#### 2.4.3. Assaig tipus S.P.T. (🔵 CONDITIONAL)

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P182 | 🔵🟢 | `2.4.3. Assaig tipus S.P.T...` | Static header (if SPT performed) |
| P184-187 | 🔵🟢 | SPT method description | **100% STATIC** |
| P185 | 🔵🖼️ | `Figura 4. Cullera normalitzada.` | **STATIC** asset (always same image) |

**Inclusion rule:** Only include if SPT was performed (check sondeig records)

#### 2.4.X. Resum dels assaigs in-situ realitzats (ALWAYS PRESENT)

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P190 | 🟢 | `2.4.X. Resum dels assaigs...` | Static header (number varies) |
| P192 | 🟢 | Intro text | Static |

##### 📊 Taula 3: DPSH Summary

| Field | Example | Data Source |
|-------|---------|-------------|
| Assaig | P-1, P-2, ... | Sheet names in `DPSH.xls` |
| Coordenades UTM X | 307689 | ICGC viewer / field GPS |
| Coordenades UTM Y | 4617890 | ICGC viewer / field GPS |
| Cota inici (msnm) | 222.5 | Topographic map / field measurement |
| Profunditat (m) | 1.40 | `DPSH.xls` → max depth with data |
| NF (m) | - or 2.5 | `DPSH.xls` → N.F. column |
| Observacions | Rebuig a graves | Field notes / interpretation |

##### 📊 Taula 4: Sondeig Summary (🔵 CONDITIONAL)

| Field | Example | Data Source |
|-------|---------|-------------|
| Assaig | S-1 | Sondeig records |
| Coordenades UTM | ... | Same as DPSH |
| Cota inici | ... | Topographic |
| Profunditat | 6.00 | Sondeig log |
| NF | - | Sondeig observations |
| Observacions | Amb SPT | Notes |

##### 📊 Taula 5: SPT Summary (🔵 CONDITIONAL)

| Field | Example | Data Source |
|-------|---------|-------------|
| Assaig | SPT-1 | Sondeig records |
| Profunditat | 1.50-1.95 | SPT depth range |
| N | 54 | SPT blow count (N₃₀) |
| Observacions | Mostra recuperada | Notes |

| P200 | 🟢 | Table caption | Static |
| P202 | 🟢 | Elevation reference note | Static |

---

### 2.5. ASSAIGS DE LABORATORI

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P205 | 🟢 | `2.5. ASSAIGS DE LABORATORI` | Static header |
| P207 | 🟢 | Lab company accreditation | Static |
| P209 | 🟢 | `Donada la naturalesa dels materials s'han sol·licitat els següents assaigs:` | Static |

##### 📊 Taula 6: Lab Tests Summary

| Field | Example | Data Source |
|-------|---------|-------------|
| Mostra | M-1 (SPT-1) | Sample ID from field |
| Profunditat | 1.50-1.95 | Sample depth |
| Granulometria | ✓ | `comanda laboratori.xls` or lab report |
| Límits Atterberg | ✓ | Same |
| Sulfats | ✓ | Same |
| Humitat natural | ✓ | Same |
| Lambe | ✓ or - | Same (only for clays) |

**Data Sources:**
- `comanda laboratori_{expedient}_{poblacio}.xls` → Lab request (what was ordered)
- `PDF/ANNEXES/LAB-SIG.pdf` → Signed lab results (when available)

---

## Summary: Section 2 Variables

### High-Value Variables (from files)

| Variable | Data Source | Extraction Method |
|----------|-------------|-------------------|
| `data_camp` | DPSH PDF date | Parse header |
| `data_sondeig` | Sondeig PDF date | Parse header (may differ) |
| `num_dpsh` | DPSH.xls | Count sheets |
| `dpsh_depths[]` | DPSH.xls | Max depth per sheet |
| `dpsh_coords[]` | Field data / ICGC | UTM coordinates |
| `has_sondeig` | Check file exists | Boolean |
| `has_spt` | Check sondeig records | Boolean |
| `spt_n_values[]` | Sondeig PDF | N₃₀ blow counts |
| `lab_tests[]` | comanda laboratori.xls | Test types per sample |

### Semi-Manual Variables

| Variable | Data Source | Notes |
|----------|-------------|-------|
| `adjacent_parcels` | Field observation / Google | N/S/E/W descriptions |
| `site_description` | Field observation | Free text |
| `urban_or_rural` | Observation | Affects template text |
| `elevations[]` | Topographic map | msnm values |

### Photos Required

| Photo | Source | Naming Convention |
|-------|--------|-------------------|
| Foto 1-2: Site views | `FOTOGRAFIES/` | WhatsApp images |
| Foto 3: DPSH machine | `FOTOGRAFIES/DPSH/` | P1.jpg, P2.jpg |
| Foto 4: Sondeig machine | `FOTOGRAFIES/SONDEIG/` | (if applicable) |

---

## Section Structure Decision Tree

```
Section 2.4 Structure depends on tests performed:

DPSH only (simplest):
  2.4.1 DPSH
  2.4.2 Resum

DPSH + SPT:
  2.4.1 DPSH
  2.4.2 SPT
  2.4.3 Resum

DPSH + Sondeig + SPT (most complete):
  2.4.1 DPSH
  2.4.2 Sondeig
  2.4.3 SPT
  2.4.4 Resum
```

---

## Automation Assessment

### Easy to Automate
| Item | Method |
|------|--------|
| Field work date | Parse DPSH PDF header |
| Number of DPSH tests | Count Excel sheets |
| DPSH depths | Read max depth from each sheet |
| Section structure | Check which files exist in ANNEXES |
| Static text | Already in template |

### Medium Difficulty
| Item | Challenge |
|------|-----------|
| UTM coordinates | Need ICGC lookup or data entry |
| Elevation (msnm) | Need topographic map or data entry |
| SPT values | Parse from Sondeig PDF (structured) |
| Lab test matrix | Parse from comanda laboratori.xls |

### Manual Input Needed
| Item | Reason |
|------|--------|
| Adjacent parcels | Requires human observation/judgment |
| Site description | Requires human observation |
| Urban vs. rural | Affects multiple template sections |
| Photo selection | Which photos to include |

---

## Key Insight: DPSH Excel as Primary Data Source

The `ANNEXES/{expedient}_DPSH.xls` file is central to Section 2:

```python
# Data we can extract from DPSH.xls
from_dpsh_excel = {
    'num_tests': len(sheet_names),        # e.g., 2
    'test_ids': sheet_names,              # ['P-1', 'P-2']
    'depths': [max_depth_per_sheet],      # [1.40, 2.60]
    'water_level': [nf_if_found],         # [None, None]
    'correction_factor': 0.83,            # From cell D14
}
```

This makes DPSH data extraction a **high-priority automation target**.

---

## Next: Section 3 Preview

Section 3 (DESCRIPCIÓ GEOLÒGICA I GEOTÈCNICA) will have:
- Geological maps from ICGC (screenshots)
- Material descriptions per level (zone-specific templates)
- Hydrogeology (partly static, partly observation)
- Lab result interpretation
- Seismic parameters (mostly static formulas)
- Radon zone classification

More complex because geological descriptions are **zone-specific** (templates stored on their server).
