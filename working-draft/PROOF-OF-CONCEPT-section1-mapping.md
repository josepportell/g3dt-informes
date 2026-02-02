# Proof-of-Concept: Section 1 Data Source Mapping
## Section: 1. PRESENTACIÓ DE L'ESTUDI

**Sample:** 4001612_informe.docx (Bell-Lloc d'Urgell)
**Purpose:** Map each paragraph/element to its data source

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 🟢 | **STATIC** - Fixed text, same in every report |
| 🟡 | **VARIABLE** - Changes per project |
| 🔵 | **CONDITIONAL** - Included only in certain cases |
| 📊 | **TABLE** - Data table |
| 🖼️ | **FIGURE** - Image/map |

---

## 1. PRESENTACIÓ DE L'ESTUDI

### Section Header
| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P052 | 🟢 | `1. PRESENTACIÓ DE L'ESTUDI` | Static header |

### Intro Paragraph
| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P054-058 | 🟡 | `A petició de: RAMON MITJANA S.L., G3 DT, S.L. ha realitzat...` | |
| | | - Client name: `RAMON MITJANA S.L.` | `ACCEPTACIO/DADES CLIENT.txt` → line 4 (company name) |
| | | - Rest of paragraph | Static template text |

---

### 1.1. ANTECEDENTS

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P061 | 🟢 | `1.1. ANTECEDENTS` | Static header |
| P063 | 🟡 | `Segons ens indica el sol·licitant, el SR. JORDI BOSCH NOVELL, de l'ARQUITECTURA BOSCH NOVELL, en nom de RAMON MITJANA S.L...` | |
| | | - Architect name: `JORDI BOSCH NOVELL` | Budget request email / PRESSUPOST folder |
| | | - Architect company: `ARQUITECTURA BOSCH NOVELL` | Budget request email |
| | | - Client name: `RAMON MITJANA S.L.` | `ACCEPTACIO/DADES CLIENT.txt` |
| | | - Project description | Budget request / architect plans |

| P065 | 🟢 | `L'edificació que es preveu construir presentarà les següents característiques:` | Static intro to table |

#### 📊 Taula 1: Dades principals edificació

| Field | Example Value | Data Source |
|-------|---------------|-------------|
| Tipus de construcció | `Habitatge aïllat` | Budget request (project type) |
| Nº de plantes | `Pb + 1Pp` | Budget request (floors) |
| Superfície parcel·la | `XXX m²` | Budget request / cadastre |
| Superfície construïda | `XXX m²` | Budget request / architect plans |
| Tipus fonamentació | `Fonaments superficials` | Usually standard for residential |
| Soterranis | `Cap` or `1 soterrani` | Budget request / architect plans |

| P069 | 🟡 | `L'edificació que es preveu construir es situarà entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell...` | |
| | | - Street names | Budget request / ICGC viewer |
| | | - Municipality: `Bell-Lloc d'Urgell` | Folder name (2nd part) |
| | | - Coordinates (UTM) | ICGC viewer → click on parcel |

#### 🖼️ Figura 1-2: Location maps
| Figure | Content | Data Source |
|--------|---------|-------------|
| Figura 1 | Topographic map with location | ICGC viewer screenshot (Mapa Topogràfic layer) |
| Figura 2 | Orthophoto with location | ICGC viewer screenshot (Ortofoto layer) |
| Caption | `Font: Projecte` or `Font: ICGC, modificat` | Depends on source |

#### 🖼️ Figura 3: Site plan (CONDITIONAL)
| Figure | Content | Data Source |
|--------|---------|-------------|
| Figura 3 | Building footprint on parcel | Architect's plans (if provided) |
| | 🔵 Only included if architect provides plans | `EXPLICACIÓ DETALLS`: "AQUESTA FIGURA NOMÉS LA POSO SI TENIM ELS PLÀNOLS DE L'ARQUITECTE" |

---

### 1.2. CLASSIFICACIÓ DE L'OBRA SEGONS EL CTE

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P078 | 🟢 | `1.2. CLASSIFICACIÓ DE L'OBRA SEGONS EL CTE` | Static header |
| P080 | 🟡 | `A partir de les dades exposades pel client, tant tipus d'edificació com localització de l'obra...` | |
| | | - Building classification | Calculated from building data |

#### 📊 Taula 2: CTE Classification

| Field | Example Value | Data Source / Rule |
|-------|---------------|-------------------|
| Tipus edificació segons CTE | `C-1` | **CALCULATED:** |
| | | C-0: <300m² AND <4 floors |
| | | C-1: ≥300m² OR ≥4 floors (up to 10) |
| | | C-2: ≥4 floors (≥10 floors) |
| Tipus de sòl considerat | `T-1` | Usually T-1 (standard), T-2/T-3 for complex soils |

---

### 1.3. OBJECTIUS

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P085 | 🟢 | `1.3. OBJECTIUS` | Static header |
| P087 | 🟢 | `Per la realització del present estudi, s'ha dut a terme una campanya de camp tenint en compte que els objectius de l'estudi són els següents:` | Static intro |
| P089-094 | 🟢 | Bullet list of objectives | **100% STATIC** - same in every report |

**Objectives list (always the same):**
1. Estudi de l'entorn geològic de l'obra.
2. Reconeixement, caracterització i potència dels materials del subsòl...
3. Cota del nivell freàtic, quan es detecti...
4. Determinació de les càrregues admissibles...
5. Estimació dels assentaments...
6. Recomanacions sobre condicionants geològics i geotècnics...

---

## Summary: Section 1 Variables

| Variable | Data Source | Priority |
|----------|-------------|----------|
| `client_name` | `ACCEPTACIO/DADES CLIENT.txt` line 4 | HIGH |
| `architect_name` | Budget request email | MEDIUM |
| `architect_company` | Budget request email | MEDIUM |
| `street_1` | Budget request / ICGC | HIGH |
| `street_2` | Budget request / ICGC | MEDIUM (if corner lot) |
| `municipality` | Folder name | HIGH |
| `utm_x`, `utm_y` | ICGC viewer | HIGH |
| `superficie_parcela` | Budget / cadastre | HIGH |
| `superficie_construida` | Budget / architect | HIGH |
| `num_plantes` | Budget request | HIGH |
| `soterranis` | Budget request | HIGH |
| `cte_edificacio` | CALCULATED from floors + area | HIGH |
| `cte_sol` | Usually T-1 | LOW |
| `has_architect_plans` | Check if plans provided | CONDITIONAL |

### Figures Required
| Figure | Source | Automation Potential |
|--------|--------|---------------------|
| Fig 1-2: Location maps | ICGC viewer | ⚠️ Manual screenshot or API? |
| Fig 3: Site plan | Architect | ⚠️ Only if provided |

---

## Observations

### High Automation Potential
- Client name extraction from `DADES CLIENT.txt` - **EASY**
- Municipality from folder name - **EASY**
- CTE classification calculation - **EASY** (simple rules)
- Static text sections - **ALREADY DONE**

### Medium Automation Potential
- Architect info from email/pressupost - **MEDIUM** (text parsing)
- UTM coordinates from ICGC - **MEDIUM** (could use ICGC API or manual entry)

### Manual/Semi-Manual
- Figure 1-2 location maps - **MANUAL** (ICGC screenshot) unless we build ICGC integration
- Figure 3 site plan - **MANUAL** (depends on architect)
- Street names - **MANUAL** entry or parse from email

---

## Next Section Preview

Section 2 (TREBALLS DE CAMP) will have:
- Field work date(s) → DPSH PDF or Excel
- Number/type of tests → Count from ANNEXES folder
- Test point locations → From field notes or DPSH data
- Photos → From `FOTOGRAFIES/` folder

The pattern is consistent: **identify what changes, find where it comes from, determine automation potential.**
