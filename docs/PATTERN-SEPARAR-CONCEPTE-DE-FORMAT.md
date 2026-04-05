# Patró arquitectònic: Separar Concepte de Format
**Creat:** 2026-04-04
**Autor:** Josep Portell
**Origen:** Disseny del Servei 4 de RV4.eu (Editor IA de Documents de Construcció)
**Objectiu:** Explicar el patró i com aplicar-lo al projecte G3DT

---

## 1. EL PROBLEMA QUE RESOL

Quan un sistema ha de processar documents tècnics amb formats variables, hi ha una temptació natural: mapejar directament les "etiquetes" que trobem als documents a les "variables" que volem informar.

```
Document:  "ADREÇA OBRA: Carrer Major 12"  →  variable: street_address = "Carrer Major 12"
```

Això funciona amb 10 documents. Amb 100, comença a fallar. Amb 1000, és insostenible.

**Per què?** Perquè estem barrejant dos coses que haurien d'estar separades:
- **El significat** (què és "adreça de l'obra"? → un concepte tècnic)
- **On el trobem** (a la línia 3 del plànol, o al camp "Dirección" del pressupost, o al cos del correu) → format del document

Quan un nou arquitecte envia els plànols en un format diferent, o un ajuntament canvia el formulari, o una normativa afegeix un camp nou, tot el sistema es trenca perquè el mapeig etiqueta→variable era fràgil.

---

## 2. LA SOLUCIÓ: DOS SCHEMAS INDEPENDENTS

### Schema de Conceptes (el domini tècnic)

Defineix **què significa cada dada**, independentment del document on aparegui.

```yaml
concepte: "adreca_obra"
  domini: identificació_projecte
  descripció: "Adreça postal completa de la ubicació de l'obra"
  tipus: text
  validació: ha de contenir nom de carrer + número
  fonts_possibles: [plànol, pressupost, email, comanda_lab]
  prioritat_fonts: plànol > pressupost > email > comanda_lab
  calculable: no  # Sempre ve d'un document, no es calcula
```

```yaml
concepte: "angle_friccio_phi"
  domini: geotècnia_paràmetres
  descripció: "Angle de fricció interna del sòl (graus)"
  tipus: number
  unitat: graus
  normativa: CTE DB-SE-C, Schmertmann 1970
  fonts_possibles: [sondeig_annex, spt_correlacions, criteri_eva]
  prioritat_fonts: criteri_eva > sondeig_annex > spt_correlacions
  càlcul: Schmertmann(Nb, granulometria, factor_n)
  dependències: [Nb, granulometria]
  semàfor: yellow  # Calculable, però l'enginyera revisa sempre
```

**Característiques:**
- Mapejat al domini tècnic (geotècnia, normativa), no a cap document
- Sap com es calcula, de què depèn, qui el determina
- Un concepte existeix independentment de si apareix en 1 document o en 50
- **Finit i estable**: les variables geotècniques que necessitem són les que són

### Schema de Format (el document concret)

Defineix **on es troba cada concepte dins d'un tipus de document específic**.

```yaml
format: "planol_tipus_A"  # Plànols de l'estil de l'arquitecte X
  descripció: "Plànol amb casella de dades a la cantonada inferior dreta"
  camps:
    - posició: { zona: "casella_dades", fila: 1 }
      text_patró: "PROJECTE:|PROYECTO:"
      concepte: "nom_projecte"
    - posició: { zona: "casella_dades", fila: 3 }
      text_patró: "ADREÇA|DIRECCIÓN"
      concepte: "adreca_obra"
    - posició: { zona: "casella_dades", fila: 5 }
      text_patró: "ARQUITECTE|ARQUITECTO"
      concepte: "nom_arquitecte"
```

```yaml
format: "pressupost_email"  # Pressupost enviat per email
  descripció: "Email amb pressupost adjunt, dades al cos del correu"
  camps:
    - posició: { zona: "cos_email" }
      text_patró: "Ref\\.|Expedient"
      concepte: "expedient"
    - posició: { zona: "adjunt_pdf", pàgina: 1 }
      text_patró: "PRESSUPOST.*ESTUDI GEOTECNIC"
      concepte: "nom_projecte"
```

**Característiques:**
- Específic d'un tipus/estil de document
- Mapeja posicions/patrons a conceptes del schema tècnic
- **Infinit i variable**: cada nou arquitecte pot enviar un format diferent
- Creix amb l'experiència (cada document processat pot generar un nou format schema)

---

## 3. IL·LUSTRACIÓ: COM HEM APLICAT AIXÒ A RV4

### Cas RV4: Un document, molts formats

Al projecte RV4 (Servei 4), el problema és omplir fitxes CTE justificatives. El mateix tipus de document (fitxa DB-HR de protecció acústica) existeix en desenes de formats:
- El del Col·legi d'Arquitectes de Cadis
- El de l'OCT del COAC (Catalunya)
- El de Navarra
- El de Castella i Lleó
- ...

Tots demanen la **mateixa informació** (massa superficial, índex d'aïllament, etc.) però en **formats completament diferents** (taules amb columnes diferents, posicions diferents, idiomes diferents).

```
FORMAT CADIS:        taula[0].cel·la[3][2]  ─┐
FORMAT OCT:          taula[2].cel·la[1][4]  ─┼─► concepte: massa_superficial_tabiqueria
FORMAT NAVARRA:      cel·la[B7] (Excel)     ─┘
FORMAT CASTELLA-LLEÓ: paràgraf 23           ─┘
```

**El schema de conceptes (acustica.yaml)** defineix: "massa superficial de la tabiqueria" existeix, es mesura en kg/m², el CTE exigeix ≥70, es pot obtenir de CYPE o d'un catàleg de materials.

**Cada format schema** (un per cada variant de fitxa) diu: "en aquest document concret, la massa superficial es troba a taula[0].cel·la[3][2]".

El motor de càlculs treballa amb **conceptes**. El document filler treballa amb **posicions de format**. Mai es creuen.

### Cas RV4: El flux

```
Usuari puja fitxa de Cadis
  → Backend parseja el .docx
  → Concept recognizer: "taula[0].cel·la[3][2] = massa_superficial_tabiqueria" (genera format schema)
  → Motor de càlculs: massa_superficial = lookup(envà_ceràmic_7cm) = 82 kg/m²
  → Renderer-json: { field: "t0_r3_c2", concept: "massa_superficial", value: 82, required: 70, color: "green" }
  → Frontend renderitza formulari
  → Usuari revisa/confirma
  → Backend omple taula[0].cel·la[3][2] = "82" al document original
  → Retorna fitxa omplerta (taca de pernil: format idèntic a l'original)
```

---

## 4. COM APLICAR-HO A G3DT

### Cas G3DT: Molts documents, un conjunt fix de variables

A G3DT el problema és l'invers: no omplim un document, sinó que **busquem dades en molts documents diferents** per informar un conjunt fix de ~80 variables d'un informe geotècnic.

Els documents d'entrada són:
- Plànols (cada arquitecte en un format diferent)
- Sondeigs (PDF vectorial o manuscrit)
- Penetròmetres DPSH (Excel o PDF)
- Pressupostos (email, PDF)
- Comandes de laboratori
- Resultats de laboratori
- Fotos de camp
- Dades d'APIs (ICGC, Cadastre)

**L'avantatge:** El nombre de variables a trobar és **reduït i estable** (~80 camps d'informe + ~20 paràmetres geotècnics). Sabem exactament què busquem.

**El problema actual:** El `label_map.py` amb 150+ mappings barreja concepte i format:

```python
# Actual label_map.py — barreja concepte i format
LABEL_MAP = {
    "ADREÇA OBRA": "street_address",           # patró textual (format) → variable (concepte)
    "DIRECCIÓN OBRA": "street_address",         # variant castellà
    "ADREÇA DE L'OBRA": "street_address",       # variant amb article
    "EMPLAZAMIENTO": "street_address",          # variant genèrica
    # ... 150+ entrades
}
```

Això és **format schema barrejat amb concept schema**. Cada nova variant textual requereix una nova entrada al diccionari. I quan dos documents contenen la mateixa variable amb etiquetes diferents, cal afegir-les manualment.

### La transformació proposada

#### Pas 1: Schema de conceptes G3DT

Definir **totes les variables** que necessitem, amb el seu significat, càlcul, i dependències:

```yaml
# schemas/concepts/identificacio.yaml
conceptes:
  adreca_obra:
    descripció: "Adreça postal completa de la ubicació de l'obra"
    tipus: text
    requerit: true
    calculable: false
    fonts_possibles: [plànol, pressupost, email, comanda_lab, cadastre]
    prioritat_fonts:
      1: user        # Eva sempre guanya
      2: plànol      # Dada primària (visible al document oficial)
      3: pressupost  # Dada secundària
      4: email       # Dada terciària
      5: cadastre    # Fallback API

  nom_arquitecte:
    descripció: "Nom complet de l'arquitecte del projecte"
    tipus: text
    requerit: true
    calculable: false
    fonts_possibles: [plànol, pressupost, email]
    prioritat_fonts:
      1: user
      2: plànol
      3: pressupost
```

```yaml
# schemas/concepts/geotecnia.yaml
conceptes:
  angle_friccio_phi:
    descripció: "Angle de fricció interna del sòl"
    tipus: number
    unitat: graus
    normativa: "CTE DB-SE-C, Schmertmann 1970"
    requerit: true
    calculable: true
    càlcul:
      mètode: schmertmann_1970
      inputs: [Nb, granulometria_factor_n]
      fórmula: "phi = asin(Nb / (12.2 + 20.3 * (sigma_v / 100))) * 180 / pi"
      fallback: "Eva's Spt-correlacions.doc table"
    dependències: [Nb, granulometria]
    fonts_possibles: [càlcul_automàtic, criteri_eva]
    prioritat_fonts:
      1: user          # Eva override
      2: càlcul        # Schmertmann
    semàfor: yellow    # Sempre revisió d'Eva

  Nb:
    descripció: "Nombre de cops normalitzat (N20/0.83 per DPSH)"
    tipus: number
    unitat: cops
    normativa: "Dapena, Lacasa & García (2000)"
    requerit: true
    calculable: true
    càlcul:
      mètode: conversió_dpsh
      inputs: [N20]
      fórmula: "Nb = N20 / 0.83"
    dependències: [N20]
    fonts_possibles: [dpsh_excel, dpsh_pdf]
    prioritat_fonts:
      1: user
      2: dpsh_excel    # Més fiable (numèric)
      3: dpsh_pdf      # Extracció visual
```

**Nota:** Les `prioritat_fonts` del concept schema substitueixen el `SOURCE_PRIORITY` actual del `label_map.py`. Però ara estan lligades al **concepte**, no a una font genèrica. Cada concepte pot tenir prioritats diferents.

#### Pas 2: Format schemas G3DT

Per a cada tipus/estil de document, definir on trobem cada concepte:

```yaml
# schemas/formats/planol_casella_dreta.yaml
format: "planol_casella_dreta"
  descripció: "Plànol d'arquitecte amb casella de dades a cantonada inferior dreta"
  identificació:
    patró: "casella rectangular amb línies horitzontals a cantonada inferior dreta"
    confiança: 0.85
  camps:
    - patró_text: ["ADREÇA", "DIRECCIÓN", "EMPLAZAMIENTO", "EMPLAÇAMENT"]
      concepte: adreca_obra
      confiança: 0.90
    - patró_text: ["ARQUITECTE", "ARQUITECTO"]
      concepte: nom_arquitecte
      confiança: 0.90
    - patró_text: ["PROMOTOR", "PROPIETARI"]
      concepte: nom_promotor
      confiança: 0.85
```

```yaml
# schemas/formats/dpsh_excel_standard.yaml
format: "dpsh_excel_standard"
  descripció: "Fitxa DPSH en Excel amb columnes profunditat/N20"
  identificació:
    patró: "Excel amb columnes Prof/N20 o Depth/Blows"
    confiança: 0.95
  camps:
    - posició: { columna: "A", des_de_fila: 2 }
      concepte: dpsh_profunditat
      confiança: 0.95
    - posició: { columna: "B", des_de_fila: 2 }
      concepte: N20
      confiança: 0.95
    - posició: { cel·la: "B1" }
      patró_text: ["DATA", "FECHA"]
      concepte: data_camp
      confiança: 0.80
```

**Nota:** Els `patró_text` dels format schemas absorbeixen el que ara fa `label_map.py`, però estan associats a un format concret, no són globals. Això vol dir que el patró "EMPLAZAMIENTO" pot significar `adreca_obra` en un plànol, però `ubicació_obra` en un pressupost, si calgués.

#### Pas 3: El Concept Recognizer a G3DT

Aquí és on les coses es posen interessants per a G3DT. A diferència de RV4 (on processem 1 document), a G3DT processem N documents per trobar M variables.

```
Documents d'entrada (N)          Schema conceptes (M)           Informe (sortida)
┌─────────────┐                  ┌──────────────────┐          ┌──────────────┐
│ Plànol A    │──┐               │ adreca_obra      │──┐       │              │
│ Plànol B    │──┤               │ nom_arquitecte   │  │       │  INFORME     │
│ Pressupost  │──┤  CONCEPT      │ phi              │  │       │  GEOTÈCNIC   │
│ Sondeig PDF │──┼─ RECOGNIZER ─►│ Nb               │──┼──────►│  (80+ vars   │
│ DPSH Excel  │──┤               │ E                │  │       │   omplertes) │
│ Email       │──┤               │ Qa               │  │       │              │
│ Lab results │──┤               │ ...              │──┘       └──────────────┘
│ ICGC API    │──┘               └──────────────────┘
└─────────────┘

Per a cada document:
  1. Identificar quin format és (SmartScan → format schema)
  2. Extreure dades segons el format schema
  3. Mapejar cada dada al concept_id
  4. Afegir al pool de candidats amb font + confiança

Després:
  5. Per a cada concepte: escollir el millor candidat (prioritat + confiança)
  6. Calcular conceptes derivats (phi des de Nb, Qa des de Nb+cohesion, etc.)
  7. Generar l'informe
```

---

## 5. COM CANVIA EL CODI ACTUAL DE G3DT

### El que canvia

| Component actual | Problema | Nou component |
|---|---|---|
| `label_map.py` (150+ mappings globals) | Barreja format i concepte. Fràgil. | `schemas/concepts/*.yaml` + `schemas/formats/*.yaml` |
| `SOURCE_PRIORITY` (prioritats fixes per font) | Mateixa prioritat per a totes les variables | Prioritats per concepte al concept schema |
| `competition.py` (resolució per prioritat+confiança) | Funciona, però sense context semàntic | Mateixa lògica, però informada pel concept schema |
| `fileminer/*.py` (miners per format) | Cada miner extreu de forma independent | Miners informen amb `concept_id`, no amb `variable_name` |
| `vision_extractor.py` (prompts ad hoc) | Prompts genèrics que demanen dades | Prompts informats pel concept schema: "busca la massa superficial" |
| Càlculs dispersos (terzaghi, schmertmann...) | Funcionen, però no estan lligats a conceptes | `calculations/engine.py` treballa amb concept_ids |

### El que NO canvia

- SmartScan (classificació de documents) → segueix funcionant, però ara identifica el `format_id`
- La pipeline de fases (0.1, 0.3, 0.4, 1, 2, 3) → segueix, però cada fase informa amb concept_ids
- El wizard → segueix, però ara mostra conceptes amb el seu semàfor
- El report generator → segueix, però llegeix del concept schema
- competition.py → segueix, però les prioritats venen del concept schema

### Migració incremental

No cal reescriure tot de cop. Es pot migrar progressivament:

1. **Crear els concept schemas** (YAML) per als ~80 camps de l'informe
2. **Afegir `concept_id`** als signals que ja genera fileminer (al costat de `variable_name`)
3. **Migrar `label_map.py`** a format schemas (un schema per tipus de document)
4. **Migrar `SOURCE_PRIORITY`** a prioritats per concepte
5. **Connectar el motor de càlculs** als concept_ids

---

## 6. DIFERÈNCIES ENTRE RV4 I G3DT

| Aspecte | RV4 (Servei 4) | G3DT |
|---|---|---|
| **Objectiu** | Omplir 1 document | Extreure dades de N documents |
| **Entrada** | 1 document (fitxa/memòria) | 5-15 documents (plànols, sondeigs, emails...) |
| **Sortida** | El mateix document omplert | Un informe nou generat |
| **Conceptes** | CTE (acústica, incendis, energia...) | Geotècnia + identificació projecte |
| **Nombre de conceptes** | Alt (~100+ per DB) | Moderat (~80-100 total) |
| **Variabilitat de formats** | Alta (cada ajuntament, cada col·legi) | Alta (cada arquitecte, cada lab) |
| **Càlcul** | Comparació simple (valor ≥ exigit) | Fórmules complexes (Schmertmann, Terzaghi-Peck...) |
| **Confiança** | Binary (el camp està o no) | Gradual (0.0-1.0, múltiples candidats) |
| **Qui revisa** | L'enginyer (Xavier) | L'enginyera (Eva) |
| **"Taca de pernil"** | Sí (retorna el document original) | No aplica (genera un informe nou) |

### El que comparteixen

- **L'arquitectura de dos schemas** és idèntica
- **El concept recognizer** fa la mateixa feina: mapejar dades de documents a conceptes
- **La independència format↔concepte** és igualment crítica en ambdós casos
- **El motor de càlculs** treballa amb conceptes, no amb formats, en ambdós

---

## 7. BENEFICIS ESPERATS PER A G3DT

| Benefici | Impacte |
|---|---|
| **Nou format d'arquitecte** | Afegir un format schema. Zero canvis al codi. |
| **Nova variable a l'informe** | Afegir un concepte al schema. Els format schemas existents no canvien. |
| **Canvi de normativa** | Actualitzar la fórmula al concept schema. Els formats segueixen funcionant. |
| **Millor explicabilitat** | "Phi=38° ve de Schmertmann(Nb=25)" en lloc de "phi extret de dpsh_excel" |
| **Menys manteniment de label_map** | Els patrons de text viuen als format schemas, no en un diccionari global |
| **Eva entén millor** | El wizard pot mostrar: concepte, d'on ve la dada, com s'ha calculat, amb quina confiança |
| **Auditabilitat** | Per a cada variable de l'informe: concept_id + source + confidence + calculation |

---

## 8. PLA DE MIGRACIÓ SUGGERIT

### Fase 1: Crear els schemas (sense tocar codi)
1. Definir l'estructura formal d'un concepte G3DT
2. Crear `schemas/concepts/identificacio.yaml` (~20 conceptes: nom, adreça, arquitecte...)
3. Crear `schemas/concepts/geotecnia.yaml` (~30 conceptes: phi, Nb, E, Qa, gamma...)
4. Crear `schemas/concepts/treball_camp.yaml` (~15 conceptes: dates, profunditats, proves...)
5. Crear `schemas/concepts/laboratori.yaml` (~15 conceptes: sulfats, classificació, humitat...)
6. Validar contra `report_data.py`: tots els camps de l'informe tenen un concepte?

### Fase 2: Afegir concept_ids als signals (canvi mínim al codi)
1. Afegir camp `concept_id` a la classe Signal (o equivalent)
2. Modificar fileminer per assignar concept_id a cada signal extret (via label_map → concept_id)
3. Modificar competition.py per usar prioritats del concept schema
4. Tests: mateixos resultats que abans, però amb concept_ids informats

### Fase 3: Migrar label_map a format schemas (canvi major)
1. Convertir cada grup de patrons de label_map a un format schema
2. SmartScan identifica el format → carrega el format schema corresponent
3. El format schema informa quin concepte buscar i on
4. Retirar label_map.py gradual

### Fase 4: Connectar motor de càlculs als conceptes
1. Registrar cada calculador (terzaghi, schmertmann...) al concept_id que informa
2. El motor calcula per concepte, no per variable_name
3. Les dependències entre conceptes (Nb→phi→Qa) estan documentades al schema

---

*Document de referència. Creat a partir del disseny del Servei 4 de RV4.eu (veure `DISSENY-APP-TACA-DE-PERNIL.md` al projecte RV4 per l'arquitectura completa).*
