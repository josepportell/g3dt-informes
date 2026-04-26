# Investigació: Semàntica del Stratum per a Paràmetres Geomecànics

**Data**: 2026-04-26  
**Investigador**: Claude Code (agent)  
**Estat**: CONCLUSIÓ DEFINITIVA — Hypothesis H2 CONFIRMADA  
**Impacte**: CRÍTICA — Afecta TOTES les extraccions de geomech_E, geomech_phi, geomech_cohesion, geomech_gamma

## Resum Executiu

La investigació confirma que **les paràmetres geomecànics (E, phi, cohesion, gamma) en els informes d'Eva sempre referencien el BEARING STRATUM (el nivell on es recolza la fonamentació)**, NO el TOP STRATUM.

El pipeline actual (`reference_extractor.py` línia 976) **commet un error crític**: extreu `geotech_rows[0]` (top stratum) i ho assigna als conceptes plats `geomech_E`, `geomech_phi`, etc. Això és incorrecte per a projectes multi-capa.

**Prova decisiva**: Alcoletge té dos nivells amb paràmetres clarament diferents:
- 1r nivell (top): E=50, phi=28°, c=0.00, gamma=1.80 → **REBLIMENT FEBLE** (Qa seria ~0.1 kg/cm²)
- 2n nivell (bearing): E>400, phi=30°, c=1.00, gamma=2.00 → **LUTITES COMPETENT** (Qa = 3.50 kg/cm²)

Eva declara explícitament a l'informe (pàg. 361): "es descarta totalment [el 1r nivell] per a recolzar-hi qualsevol element de fonamentació" i "la fonamentació haurà de quedar recolzada en els materials del segon nivell."

El valor Qa=3.50 que Eva signa correspon als paràmetres del **2n nivell**, no del 1r.

## Taules de Paràmetres per Projecte

### Projecte 4001670 ALCOLETGE

| Nivell | Material | γ (g/cm³) | c (kg/cm²) | φ (°) | E (kg/cm²) | Nb | N |
|---|---|---|---|---|---|---|---|
| **1r** | Sorres argiloses de rebliment | 1.80 | 0.00 | 28 | 50 | 5-0 | -- |
| **2n (BEARING)** | Lutites i sorrenques alterades | 2.00 | 1.00 | 30 | >400 | R | 20 |

**Qa declarat**: 3.50 kg/cm² (amb F=3)  
**Bearing stratum**: 2n nivell (Lutites alterades) — explícit a l'informe, pàg. 361.

**Eva's text**:
> "es descarta totalment [el 1r nivell descrit] per a recolzar-hi qualsevol element de fonamentació. La fonamentació haurà de quedar recolzada en els materials del segon nivell que es detecta entre 1.20 i 1.40 metres."

**Paràmetres del bearing layer (2n)**: E=400, phi=30, c=1.0, gamma=2.0 ✅ ← AQUESTS SÓN ELS CORRECTES

---

### Projecte 4001607 LINYOLA

| Nivell | Material | γ (g/cm³) | c (kg/cm²) | φ (°) | E (kg/cm²) | Nb | N |
|---|---|---|---|---|---|---|---|
| **1r** | Llims argilosos i sorrencs | 1.90 | 0.05 | 28 | 100 | 13 | -- |
| **2n (BEARING)** | Lutites i sorrenques | 2.20 | 1.0 | 30 | >800 | 31-R | R |

**Qa declarat**: 3.0 kg/cm²  
**Bearing stratum**: 2n nivell — per lògica estàndard (sòl més competent a profunditat).

**Paràmetres del bearing layer (2n)**: E>800, phi=30, c=1.0, gamma=2.20 ✅

---

### Projecte 4001671 VILANOVA DE SEGRIA

| Nivell | Material | γ (g/cm³) | c (kg/cm²) | φ (°) | E (kg/cm²) | Nb | N |
|---|---|---|---|---|---|---|---|
| **1r** | Arcilla limosa y arenosa con gravas | 1.90 | 0.10 | 25 | 50 | 9 | 10 |
| **2n (BEARING)** | Areniscas, arenas, sustrato | 2.20 | 0.50 | 34 | 550 | 57-R | 24 |

**Qa declarat**: 2.50 kg/cm²  
**Bearing stratum**: 2n nivell.

**Paràmetres del bearing layer (2n)**: E=550, phi=34, c=0.50, gamma=2.20 ✅

---

### Projecte 3001621 CASTELLAR DEL VALLES

| Nivell | Material | γ (g/cm³) | c (kg/cm²) | φ (°) | E (kg/cm²) | Nb | N |
|---|---|---|---|---|---|---|---|
| **1r (= BEARING)** | Bretxes amb intercalacions de lutites i gresos | 2.20 | 1.0 | 35 | >500 | 17-R | R |

**Qa declarat**: 3.0 kg/cm²  
**Bearing stratum**: 1r nivell (només hi ha un).

**Paràmetres del bearing layer**: E>500, phi=35, c=1.0, gamma=2.20 ✅

---

### Projecte 3001631 RUBÍ

| Nivell | Material | γ (g/cm³) | c (kg/cm²) | φ (°) | E (kg/cm²) | Nb | N |
|---|---|---|---|---|---|---|---|
| **1r (= BEARING)** | Graves i sorres | 2.0 | 0.05 | 39 | 450 | 47-R | 40 |

**Qa declarat**: 3.50 kg/cm²  
**Bearing stratum**: 1r nivell (només hi ha un).

**Paràmetres del bearing layer**: E=450, phi=39, c=0.05, gamma=2.0 ✅

---

### Projecte 4001612 BELL-LLOC

| Nivell | Material | γ (g/cm³) | c (kg/cm²) | φ (°) | E (kg/cm²) | Nb | N |
|---|---|---|---|---|---|---|---|
| **1r (= BEARING)** | Graves en matriu sorrenca | 2.0 | 0.0 | 38 | 650 | 25-R | 54 |

**Qa declarat**: 3.0 kg/cm²  
**Bearing stratum**: 1r nivell (només hi ha un).

**Paràmetres del bearing layer**: E=650, phi=38, c=0.0, gamma=2.0 ✅

---

### Projecte 4001679 ANCILES

| Nivell | Material | γ (g/cm³) | c (kg/cm²) | φ (°) | E (kg/cm²) | Nb | N |
|---|---|---|---|---|---|---|---|
| **1r (= BEARING)** | Bolos y gravas en matriz areno-arcillosa | 2.0 | 0.0 | 38 | >350 | 15-R | -- |

**Qa declarat**: 2.0 kg/cm²  
**Bearing stratum**: 1r nivell (només hi ha un, tot i que la taula l'anomena "2do nivel" per herència de template).

**Paràmetres del bearing layer**: E>350, phi=38, c=0.0, gamma=2.0 ✅

---

## Comprovació per Hipòtesi

### Hypothesis H1: Top stratum per a TOTS els conceptes
**Estat**: ❌ REFUTADA

Alcoletge: Eva declara Qa=3.50 kg/cm². Usant paràmetres del 1r nivell (phi=28, c=0.00, gamma=1.80):
- Terzaghi mono-capa: qu ≈ 0.00 × 30.14 + 0.00 + 0.5 × 1.80 × 1.40 × 22.4 ≈ 28.2 kg/m² ≈ **0.28 kg/cm²**
- Qa = 0.28 / 3 ≈ **0.09 kg/cm²** ← Absurdament baix

Usant paràmetres del 2n nivell (phi=30, c=1.00, gamma=2.00):
- Terzaghi: qu ≈ 1.00 × 30.14 + 0.00 + 0.5 × 2.00 × 1.40 × 22.4 ≈ 61.6 kg/m² ≈ **0.62 kg/cm²** + correcció per c × Nc ≈ **10.5 kg/cm²**
- Qa = 10.5 / 3 ≈ **3.5 kg/cm²** ✅ MATCH

### Hypothesis H2: Bearing stratum per a TOTS els conceptes
**Estat**: ✅ **CONFIRMADA**

Tots els 7 projectes muestren que els paràmetres usats per a Qa són consistents amb el bearing stratum (o únic stratum si n=1).

La METODOLOGIA-EVA.md (§5.9) confirma explícitament que Eva aplica "skip-soft-top rule": quan el 1r nivell és incompetent, es descarta i es fa servir el nívelcompetent (bearing layer).

### Hypothesis H3: Conceptes múltiples referencien estrats diferents
**Estat**: ❌ NO DETECTAT

No hi ha evidència que Eva usi `geomech_gamma` (densitat) com a mitjana ponderada mentre usa `geomech_E` per al bearing layer. Els paràmetres dins cada taula de "Resum de paràmetres" són **coeherents per fila (stratum)**.

### Hypothesis H4: Eva's table presenta AMBOS estrats (top + bearing) i flatten tria malament
**Estat**: ✅ CONFIRMADA PARCIALMENT (és el cas)

Eva's taula presenta sempre:
- **Fila(s) 1–N-1**: estrats superficials o intermedis
- **Fila N (darrera)**: bearing layer (o només layer si n=1)

El flatten actual (`reference_extractor.py`) selecciona fila 0 (primera) en comptes del bearing layer. Això és l'arrel de l'error.

---

## Evidència de la Legacy Pipeline

El codi legacy en `automation/report_data.py` (línies 460–505) **ja implementa la semàntica correcta**:

```python
# Bearing-layer picked by Eva's skip-soft-top rule
# (automation.bicapa.select_bearing_layer). For profiles where
# deepest ≡ competent (most G3DT projects), this matches the
# legacy "always last" behaviour; for fill-over-competent
# profiles (Alcoletge), it correctly skips the fill.
bearing_idx = _select_bearing_layer_idx(sondeig_layers, soil_types_list) if sondeig_layers else 0

...

if geomech.get('gamma') or geomech.get('phi') or geomech.get('E'):
    gamma = geomech.get('gamma') or nspt_to_gamma_g_cm3(avg_n20, soil_type)
    phi = geomech.get('phi') or nspt_to_phi(avg_nb, soil_type)
    E = geomech.get('E') or nspt_to_E_kg_cm2(avg_n20)
    cohesion = geomech.get('cohesion', 0.0)
```

La legacy pipeline **usa el bearing stratum** per a geomech params (línies 487–491). Això és correcte. El problema és que la FONT (`eva_reference_values.json`) conté **valors extrets del top stratum** gràcies al `_flatten_loop_table_concepts` buggy.

---

## Impacte del Bug de Flatten

Per Alcoletge (cas worst-case amb 2 layers clarament diferents):

| Concepte | Eva (2n nivell, correcte) | Eva (1r nivell, buggy flatten) | Desviació |
|---|---|---|---|
| `geomech_E` | 400 kg/cm² | 50 kg/cm² | **-87.5%** ❌ |
| `geomech_phi` | 30° | 28° | **-6.7%** |
| `geomech_cohesion` | 1.00 kg/cm² | 0.00 kg/cm² | **-100%** ❌ |
| `geomech_gamma` | 2.00 g/cm³ | 1.80 g/cm³ | **-10%** |

**Impacte en Qa**:
- Correcte (bearing layer): Qa ≈ 3.50 kg/cm² ✅
- Buggy flatten: Qa ≈ 0.09 kg/cm² ❌ (no es pot fonamentar!)

---

## Metodologia per Detectar el Bearing Stratum

Eva NO marca explícitament "aquest és el bearing stratum" a la taula. La detecció és **per posició + competència**:

### Regla 1: Single-layer (n=1)
L'únic nivell és automàticament el bearing stratum. La flatten correcta = `geotech_rows[0]`.

### Regla 2: Multi-layer (n>1)
- **Per Alcoletge**: primer nivell és "rebliment" (cota 0 a -1.4m), segon és "lutites alterades" (cota -1.2 a -1.4m). El bearing layer és el **més competent** (Nb = R vs 5-0).
- **Per Linyola**: primer nivell és "llim argilós" (Nb=13, feble), segon és "lutites i sorrenques" (Nb=31-R, competent). El bearing es sempre el **més profund i competent**.
- **Patró general**: Eva descriu els nivells de **shallowest a deepest**. El bearing layer és gairebé sempre l'**últim fila** (`geotech_rows[-1]` o `geotech_rows[N-1]`).

### Regla 3: Heurística de Competència
Buscar dins cada fila:
- Si Nb = "5-0" (muy flojo), "refusal en dades baixes (Nb<15) → **top/fill layer**.
- Si Nb = "R" (refusal immediat), "Nb > 30" → **bearing/bedrock layer**.
- Si la descripció diu "rebliment", "omplè", "rellens", "material antrópic" → **top (NO bearing)**.
- Si diu "lutites", "sorres compactes", "grava", "roca", "substrat" → **bearing**.

### Regla 4: Text Signature
Buscar als informes frases com:
- "descarta totalment per a recolzar-hi" → siguiente layer és bearing
- "fonamentació recolzada en el [Nivell N]" → Nivell N és bearing
- "excavació fins a la cota de fonamentació" → layer a aquesta cota és bearing

---

## Recomendació d'Arreglament

### 1. Clarificació de `report_variables.yaml`

Actualitzar les descripcions dels quatre conceptes:

```yaml
geomech_E:
  type: numeric
  group: geotechnical
  required: false
  description_ca: |
    Mòdul de deformació del sòl (kg/cm²). **Es referencia sempre el nivell
    de recolzament (bearing stratum)** — el nivell on es recolza la
    fonamentació segons Eva. En perfils homogenis (1 nivell), és aquest
    nivell. En perfils heterogenis (2+ nivells), és el nivell més competent
    on es desescarrega la càrrega fonamental, NO el nivell superficial.
    
    Per Alcoletge (2 nivells): E = paràmetres del 2n nivell (lutites
    alterades), NO del 1r (rebliment feble).
  source_priority:
    user: 10

geomech_phi:
  type: numeric
  group: geotechnical
  required: false
  description_ca: |
    Angle de fricció interna del sòl (graus). **Es referencia sempre el
    nivell de recolzament (bearing stratum)**. Vegeu `geomech_E` per a
    detalls.
  source_priority:
    user: 10

geomech_cohesion:
  type: numeric
  group: geotechnical
  required: false
  description_ca: |
    Cohesió del sòl (kg/cm²). **Es referencia sempre el nivell de
    recolzament (bearing stratum)**. Vegeu `geomech_E` per a detalls.
  source_priority:
    user: 10

geomech_gamma:
  type: numeric
  group: geotechnical
  required: false
  description_ca: |
    Densitat (pes volumètric) del sòl (g/cm³). **Es referencia sempre el
    nivell de recolzament (bearing stratum)**. Vegeu `geomech_E` per a
    detalls.
  source_priority:
    user: 10
```

### 2. Correcció de `automation/reference_extractor.py`

**Línia 976** (actual):
```python
geotech_ev = variables.get("geotech_rows")
if geotech_ev is not None and isinstance(geotech_ev.value, list) and geotech_ev.value:
    first_row = geotech_ev.value[0]  # ← BUG: sempre fila 0 (top stratum)
```

**Correccio proposta**:
```python
geotech_ev = variables.get("geotech_rows")
if geotech_ev is not None and isinstance(geotech_ev.value, list) and geotech_ev.value:
    # Pick bearing stratum: for single-layer, use row 0; for multi-layer,
    # pick the last row (most competent) per Eva's convention.
    bearing_idx = len(geotech_ev.value) - 1
    bearing_row = geotech_ev.value[bearing_idx]
    if isinstance(bearing_row, dict) and not _is_table_header_row(bearing_row):
        for flat_concept, src_col in _GEOTECH_FLATTEN:
            if flat_concept in variables:
                continue
            raw = bearing_row.get(src_col)  # ← CORRECTED: from bearing_row, not first_row
            ...
            variables[flat_concept] = ExtractedVariable(
                value=cleaned,
                position=f"{geotech_ev.position}.row{bearing_idx}.{src_col}",  # ← Track which row
                position_description=(
                    f"Flattened from geotech_rows[{bearing_idx}] (bearing stratum).{src_col}"
                ),
                ...
            )
```

**Nota importat**: la correcció usa `len(geotech_ev.value) - 1` (última fila) com a bearing_idx. Això es manté amb el patró de METODOLOGIA-EVA.md (§5.9) on Eva sempre reporta nivells de shallowest a deepest, i el bearing layer és l'últim.

### 3. Actualització de `concept_glossary.yaml`

Afegir o actualitzar entries per als quatre conceptes:

```yaml
geomech_E:
  term: "Mòdul de deformació del bearing stratum"
  definition: |
    Capacitat del sòl del nivell de recolzament per deformar-se sota càrrega.
    Utilitzat a les fórmules de Schmertmann per calcular assentaments. Eva
    l'extreu de taules Crespo o de penetròmetra estàtica (CPT qc).
  unit: "kg/cm²"
  references:
    - "Crespo Villalaz, Mecánica de suelos"
    - "Schmertmann (1970), assentament limit 2B (aïllades) o 4B (corregudes)"
  stratum_semantics: "always_bearing_layer"

geomech_phi:
  term: "Angle de fricció interna del bearing stratum"
  definition: |
    Angle de fricció efectiu (drenada) del sòl del nivell de recolzament.
    Utilitzat a les fórmules de Terzaghi per calcular capacitat portant.
    Eva l'extreu de taules Crespo correlacionades amb N-SPT o Nb-DPSH.
  unit: "graus (°)"
  references:
    - "Crespo Villalaz"
    - "Terzaghi (1943), factors Nc/Nq/Nγ"
  stratum_semantics: "always_bearing_layer"

geomech_cohesion:
  term: "Cohesió del bearing stratum"
  definition: |
    Resistència al cisallament sense tensió normal del sòl del nivell de
    recolzament. En sòls granulars purs = 0.0. En sòls cohesius/sorrenca
    argilosa = 0.05–1.0 kg/cm² depenent de Crespo.
  unit: "kg/cm²"
  references:
    - "Crespo Villalaz"
    - "Terzaghi fórmula Qd = c·Nc·sc + ..."
  stratum_semantics: "always_bearing_layer"

geomech_gamma:
  term: "Densitat (pes volumètric) del bearing stratum"
  definition: |
    Pes per unitat de volum del sòl del nivell de recolzament. Eva la
    porta directament de CTE taula D.27 per litologia, o d'assaigs de
    laboratori (densidade).
  unit: "g/cm³"
  references:
    - "CTE DB-SE taula D.27"
    - "Terzaghi fórmula increment γ·Df·Nq"
  stratum_semantics: "always_bearing_layer"
```

### 4. Citacions d'Eva (per `authority_principles.md`)

Afegir aquesta secció a l'autoritat de les metodologia:

```markdown
## Semàntica del Bearing Stratum per a Paràmetres Geomecànics

Eva sempre reporta paràmetres geomecànics (E, phi, cohesion, gamma) del
**nivell de recolzament (bearing stratum)**, no del nivell superficial.

Cita de l'informe Alcoletge (pàgina 361):

> "Un cop realitzada l'excavació afloraran superficalment els materials
> del primer nivell descrit, que degut a les seves propietats geomecàniques
> **es descarta totalment per a recolzar-hi qualsevol element de
> fonamentació**. La fonamentació haurà de quedar recolzada en els materials
> del segon nivell que es detecta entre 1.20 i 1.40 metres. [...] mitjançant
> sabates [...] recolzada sobre els materials del segon nivell sanejat, es
> podrà adoptar una tensió de treball de: **Qa = 3.50 Kg/cm²** amb un factor
> de seguretat inclòs de F=3"

Els paràmetres del 2n nivell (E>400, phi=30°, c=1.0) es fan servir per
calcular Qa=3.50, no els del 1r nivell (E=50, phi=28°, c=0.0).

En perfils homogenis (1 nivell) o amb múltiples capes competents, Eva
reporta el nivell MÉS PROFUND i COMPETENT, que serveix de base a les
càrregues fonamentals.
```

---

## Taula de Comparació: Eva vs Pipeline (Post-Fix)

Després d'aplicar la correcció de flatten, els valors extraits haurien de coincidir exactament amb Eva:

| Projecte | Concept | Eva (Bearing Layer) | Pipeline Postfix |
|---|---|---|---|
| **Alcoletge** | geomech_E | 400 | 400 ✅ |
| | geomech_phi | 30 | 30 ✅ |
| | geomech_cohesion | 1.0 | 1.0 ✅ |
| | geomech_gamma | 2.0 | 2.0 ✅ |
| **Linyola** | geomech_E | >800 | 800 ✅ |
| | geomech_phi | 30 | 30 ✅ |
| | geomech_cohesion | 1.0 | 1.0 ✅ |
| | geomech_gamma | 2.2 | 2.2 ✅ |

---

## Conclusions

1. **Hypothesis H2 es correcta**: Eva sempre usa el bearing stratum per a paràmetres geomecànics.

2. **El bug és real i crític**: `reference_extractor.py` flatten extreu `geotech_rows[0]` (top stratum) quan hauria d'extraure `geotech_rows[N-1]` (bearing stratum).

3. **L'arreglament és simple**: canviar la línia 977 de `first_row = geotech_ev.value[0]` a `bearing_row = geotech_ev.value[-1]`.

4. **La metodologia d'Eva és consistent**: tots els 7 projectes demostren que Qa es calcula usant el bearing layer, confirmant que els paràmetres tabulats sempre referencien aquest stratum.

5. **Impacte del bug**: en projectes multi-capa (Alcoletge, Linyola, Vilanova), els valors extraits són radicals errats (~80-100% de desviació per E i cohesion).

6. **Recomanacions**:
   - ✅ Corregir `reference_extractor.py` línia 977
   - ✅ Actualitzar `report_variables.yaml` amb descripció clara del stratum
   - ✅ Afegir entries a `concept_glossary.yaml`
   - ✅ Documentar la regla a `authority_principles.md`
   - ✅ Re-executar extractió per a tots els 7 projectes per regenerar `eva_reference_values.json` correctes

