# Section 4 Data Source Mapping
## Section: 4. CONCLUSIONS

**Sample:** 4001612_informe.docx (Bell-Lloc d'Urgell)
**Comparison:** 4001607 (Linyola - expansivity), 3001621 (Castellar - slope stability)

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 🟢 | **STATIC** - Fixed text, same in every report |
| 🟡 | **VARIABLE** - Changes per project |
| 🔵 | **CONDITIONAL** - Included only in certain cases |
| 📊 | **TABLE** - Data table |
| 🖼️ | **FIGURE** - Image |
| 🔢 | **CALCULATED** - Derived from formulas/data |

---

## Section 4 Structure Variants

The structure of Section 4 changes based on project conditions:

```
SIMPLE (flat site, granular soil):
  4.1 Geologia
  4.2 Hidrogeologia i Agressivitat
  4.3 Fonamentació
  → END

WITH EXPANSIVE SOILS (clay-rich):
  4.1 Geologia
  4.2 Hidrogeologia i Agressivitat
  4.3 Expansivitat dels materials    ← EXTRA
  4.4 Fonamentació
  → END

WITH RETAINING WALLS:
  4.1 Geologia
  4.2 Hidrogeologia i Agressivitat
  4.3 Fonamentació
  4.4 Empentes de terres            ← EXTRA
  → END

MOST COMPLETE (slope + walls):
  4.1 Geologia
  4.2 Hidrogeologia i Agressivitat
  4.3 Fonamentació
  4.4 Empentes de terres
  4.5 Estabilitat del vessant       ← EXTRA
  → END
```

**Decision triggers:**
| Condition | Extra Section |
|-----------|---------------|
| Lambe test shows "Marginal" or higher | 4.X Expansivitat |
| Project has basement or retaining walls | 4.X Empentes de terres |
| Site is on a slope | 4.X Estabilitat del vessant |

---

## 4. CONCLUSIONS

### Section Intro

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P383 | 🟢 | `4. CONCLUSIONS` | Static header |
| P385 | 🟢 | `Les recomanacions es donen en funció dels resultats obtinguts de la campanya de camp realitzada...` | Static intro |

---

### 4.1. GEOLOGIA

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P387 | 🟢 | `4.1. GEOLOGIA` | Static header |
| P389 | 🟡 | `Es detecta un sòl nivell de materials...` | |
| | | - Number of levels: `un` / `dos` / `tres` | **Count from Section 3.2** |
| P391 | 🟡 | Level description | |
| | | - `El 1er nivell està format per graves en matriu sorrenca carbonatades, de coloracions clars...` | **Zone-specific template + field observations** |

**Level description pattern:**
```
El {ordinal} nivell està format per {material_description}, de coloracions {colors}.
Destacar que existeix un primer tram superficial de {thickness} cm format per {topsoil_description}.
```

| Variable | Data Source |
|----------|-------------|
| `num_levels` | Section 3.2 analysis / DPSH interpretation |
| `material_description` | **Zone-specific templates on server** |
| `colors` | Field observation |
| `topsoil_thickness` | DPSH/Sondeig observations |

| P393 | 🟢 | `La distribució espaial dels materials al llarg de la parcel·la estudiada es recull en següent tall de correlació:` | Static |

#### 🖼️ Figura 6: Cross-section

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P395 | 🖼️ | Tall de correlació | `ANNEXES/{expedient}_tall de correlació.FH11` → PDF |
| Caption | 🟢 | `Figura 6. Detall del tall de correlació que s'adjunta als annexes.` | Static |

| P397 | 🟢 | `Finalment, a partir de les litologies observades, s'ha associat al nivell descrit unes característiques geològiques i geotècniques...` | Static intro to table |

#### 📊 Taula 10: Geotechnical Parameters

**THIS IS THE KEY TABLE - Calculated from test data**

| Parameter | Symbol | Units | Example | Data Source |
|-----------|--------|-------|---------|-------------|
| Nivell | - | - | 1er Nivell | Section 3.2 |
| Descripció | - | - | Graves carbonatades | Zone template |
| Gruix | - | m | >2.60 | Max DPSH depth |
| Densitat | γ | gr/cm³ | 2.1 | 🔢 Estimated from material type |
| Cohesió | c | Kg/cm² | 0 | 🔢 From correlations (granular=0) |
| Angle fregament | φ | º | 38 | 🔢 From N-value correlations |
| Mòdul deformació | E | Kg/cm² | 450 | 🔢 From N-value correlations |
| DPSH mitjà | N₂₀ | cops | 45 | 🔢 Average from `DPSH.xls` per level |
| SPT mitjà | N₃₀ | cops | 54 | From Sondeig SPT records |

**Calculation sources:**
- Density: Material type lookup table
- Cohesion: 0 for granular, calculated for clays
- Friction angle: Correlation with N-values (see Base de càlcul annex)
- Deformation modulus: E = f(N) correlation
- Average N₂₀: `=AVERAGE(DPSH values for level depth range)` from Excel

| P401-404 | 🟢 | Footnotes explaining parameters | Static |

---

### 4.2. HIDROGEOLOGIA I AGRESSIVITAT

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P407 | 🟢 | `4.2. HIDROGEOLOGIA I AGRESSIVITAT` | Static header |
| P409 | 🟡 | Surface hydrology comment | |
| | | Urban site: `Degut a que es tracta d'un solar antropitzat, no s'han detectat marques i/o indicis de processos d'erosió...` | **Template: urban vs. rural** |
| | | Near river/stream: Different text about proximity to water | **Check ICGC for nearby streams** |
| P411 | 🟡 | Water level statement | |
| | | No water: `En data de la realització dels treballs de camp, i fins la cota estudiada, no es va detectar presència de nivell freàtic...` | `DPSH.xls` N.F. column |
| | | Water found: `Es va detectar nivell freàtic a la cota de {depth} m...` | `DPSH.xls` N.F. column |
| P413 | 🟡 | Aggressivity classification | |
| | | `...els materials del subsòl on es preveu armar la fonamentació, es presenten {aggressivity_class} segons la instrucció EHE...` | Lab results: Sulfate content → classification |

**Aggressivity classification (from sulfate mg/kg SO₄):**

| Sulfate (mg/kg) | Class | Text |
|-----------------|-------|------|
| < 2000 | Non-aggressive | `no agressius` |
| 2000-3000 | Weak | `dèbilment agressius (Qa)` |
| 3000-12000 | Medium | `moderadament agressius (Qb)` |
| > 12000 | Strong | `fortament agressius (Qc)` |

| Data Source | Location |
|-------------|----------|
| Sulfate value | `PDF/ANNEXES/LAB-SIG.pdf` or `comanda laboratori.xls` |
| Water level | `DPSH.xls` column F (N.F.) |
| Urban/rural | Field observation |
| Nearby streams | ICGC viewer |

---

### 4.3. FONAMENTACIÓ (or 4.4 if Expansivitat present)

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P416 | 🟢 | `4.3. FONAMENTACIÓ` | Static header (number may vary) |
| P418 | 🟡 | Project excavation context | |
| | | `Segons el projecte executiu es preveu la construcció d'una estructura en planta baixa, i per tant, no es preveu cap excavació important...` | **From Section 1 building data** |
| P420 | 🟡 | Post-excavation material statement | |
| | | `Un cop realitzada l'excavació aflorarà superficialment els materials del {level} nivell descrit...` | Section 3.2 / 4.1 |
| P422 | 🟢 | Foundation type recommendation | Mostly static template |

#### Key Calculated Values

| P424 | 🔢🟡 | **Qa (Tensió admissible)** | |
```
Qa= 3.0 Kg/cm²  amb un factor de seguretat inclòs de F=3
```

| Variable | Formula/Source |
|----------|----------------|
| `Qa` | 🔢 **Calculated in Base de càlcul annex** |
| | Terzaghi formula using: B (footing width), γ (density), c (cohesion), φ (friction angle), Nq, Nc, Nγ factors |
| | Typical values: 2.0 - 4.0 Kg/cm² |
| `F` | Always 3 (safety factor) |

| P426 | 🔢🟡 | **Assentaments (Settlements)** | |
```
Els assentaments màxims previstos per la càrrega recomanada anteriorment seran inferiors a 1.20 cm, immediats en el temps donat el comportament granular...
```

| Variable | Formula/Source |
|----------|----------------|
| `settlement_max` | 🔢 **Calculated in Base de càlcul annex** |
| | Settlement = f(Qa, E, B) |
| | Typical values: 0.5 - 2.0 cm |
| `settlement_type` | Based on material: |
| | Granular → `immediats en el temps` |
| | Clayey → `diferits en el temps` |

---

### 4.3. EXPANSIVITAT DELS MATERIALS (🔵 CONDITIONAL)

**Only included when clay soils with Lambe test showing Marginal or higher**

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| Header | 🔵 | `4.3. EXPANSIVITAT DELS MATERIALS` | Conditional |
| Content | 🔵🟡 | Lambe test results interpretation | Lab report |

| Variable | Data Source |
|----------|-------------|
| `lambe_classification` | Lab report (Lambe test) |
| `swelling_pressure` | Lab report: Pressió d'inflament (Kg/cm²) |
| `recommendations` | Template based on classification |

**Lambe classification:**

| Classification | Swelling Pressure | Action |
|----------------|-------------------|--------|
| No crític | < 0.25 Kg/cm² | Standard foundations |
| Marginal | 0.25-1.0 Kg/cm² | Precautions needed |
| Crític | 1.0-2.5 Kg/cm² | Special foundations |
| Molt crític | > 2.5 Kg/cm² | Major engineering |

---

### 4.4. EMPENTES DE TERRES (🔵 CONDITIONAL)

**Only included when project has retaining walls or basement**

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| Header | 🔵 | `4.4. EMPENTES DE TERRES` | Conditional |
| Content | 🔵🟡 | Earth pressure calculations | |

| Variable | Formula/Source |
|----------|----------------|
| `Ka` (active pressure coef) | 🔢 Ka = tan²(45° - φ/2) |
| `Kp` (passive pressure coef) | 🔢 Kp = tan²(45° + φ/2) |
| `K0` (at-rest pressure coef) | 🔢 K0 = 1 - sin(φ) |
| `earth_pressure` | 🔢 σh = Ka × γ × z |

---

### 4.5. ESTABILITAT DEL VESSANT (🔵 CONDITIONAL)

**Only included when site is on a slope**

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| Header | 🔵 | `4.5. ESTABILITAT DEL VESSANT` | Conditional |
| Content | 🔵🟡 | Slope stability analysis | |

| Variable | Data Source |
|----------|-------------|
| `slope_angle` | Topographic survey |
| `safety_factor` | 🔢 Hoek & Bray method |
| `stability_charts` | Standard Hoek & Bray figures |

---

### Signature Block

| Element | Type | Content | Data Source |
|---------|------|---------|-------------|
| P428+ | 🟢 | `G3 D T S.L. sol·licita que si es detectessin anomalies...` | Static disclaimer |
| | 🟡 | Expedient number | Folder name |
| | 🟡 | Location, date | Municipality + report date |
| | 🟢 | Company stamp | Static asset |
| | 🟡 | Signatures | Signing geologist(s) |

---

## Summary: Section 4 Variables

### Calculated Values (from test data)

| Variable | Input Data | Calculation |
|----------|------------|-------------|
| `num_levels` | DPSH/Sondeig interpretation | Count distinct layers |
| `dpsh_average` | `DPSH.xls` per level | `=AVERAGE(N20 for depth range)` |
| `spt_average` | Sondeig records | From SPT N values |
| `density` | Material type | Lookup table |
| `cohesion` | Material + N values | Correlation (0 for granular) |
| `friction_angle` | N values | Correlation tables |
| `deformation_modulus` | N values | E = f(N) |
| **`Qa`** | All above | **Terzaghi formula** |
| **`settlement`** | Qa, E, B | Settlement formula |
| `aggressivity` | Sulfate mg/kg | Classification table |

### Conditional Sections

| Section | Trigger | Data Needed |
|---------|---------|-------------|
| Expansivitat | Lambe test ≥ Marginal | Lambe results, swelling pressure |
| Empentes | Has basement/walls | φ, γ from Table 10 |
| Estabilitat | Slope site | Slope angle, soil parameters |

### Zone-Specific Content

| Element | Source |
|---------|--------|
| Material descriptions | **Server folder with zone templates** |
| Geological context | Zone-specific Word files |

---

## Automation Assessment

### High Automation (from DPSH Excel)

```python
# Can be calculated automatically
from_dpsh = {
    'dpsh_average_per_level': calculate_average(dpsh_data, level_depths),
    'max_depth': max(depths),
    'water_level': check_nf_column(dpsh_data),
}

# Correlations (lookup tables)
from_correlations = {
    'friction_angle': n_to_phi(dpsh_average),  # Standard correlation
    'deformation_modulus': n_to_E(dpsh_average),
    'density': material_to_density(material_type),
}
```

### Medium Automation (formulas in Base de càlcul)

```python
# Terzaghi bearing capacity (already in their Excel?)
def calculate_Qa(B, gamma, c, phi, Df):
    Nc, Nq, Ngamma = terzaghi_factors(phi)
    qult = c*Nc + gamma*Df*Nq + 0.5*gamma*B*Ngamma
    Qa = qult / 3  # F=3
    return Qa

# Settlement
def calculate_settlement(Qa, E, B):
    # Simplified elastic settlement
    return (Qa * B * (1 - nu**2)) / E
```

### Manual Input Required

| Item | Reason |
|------|--------|
| Number of levels | Requires geological interpretation |
| Level depth ranges | Requires geological interpretation |
| Material descriptions | Zone-specific templates |
| Urban/rural classification | Observation |
| Conditional sections | Project requirements |

---

## Key Insight: Base de Càlcul Annex

The **Base de càlcul** annex contains the actual formulas used to calculate Qa and settlements. This is critical because:

1. Their calculations must match the annex (legal/professional requirement)
2. The formulas are standardized (Terzaghi, elastic settlement)
3. Input parameters come from Table 10

**Recommendation:** Extract the calculation logic from their existing Excel/annex to ensure our automation produces identical results.

---

## Data Flow Summary

```
DPSH.xls → Average N values → Correlations → Table 10 parameters
                                    ↓
                            Base de càlcul formulas
                                    ↓
                              Qa, Settlements
                                    ↓
                         Section 4.3 Fonamentació text

Lab results → Sulfate → Aggressivity class → Section 4.2 text
           → Lambe → Expansivity → Section 4.3 (conditional)
```

This makes the DPSH Excel + Lab results the **primary data drivers** for Section 4.
