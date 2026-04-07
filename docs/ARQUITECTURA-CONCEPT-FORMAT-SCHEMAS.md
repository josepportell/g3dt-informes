# Arquitectura: Separacio Concepte-Format

**Data:** 2026-04-05
**Branca:** `feature/concept-format-separation`
**Autor:** Josep Portell + Claude Code

---

## 1. Resum executiu

El sistema G3DT extreu dades de documents de projectes (planols, fitxes de camp, Excel, emails, APIs) per generar informes geotecnics. Anteriorment, `label_map.py` barrejava dos conceptes en un sol diccionari: **que significa cada dada** (concepte) i **on la trobem** (format del document).

Amb la nova arquitectura:

- **Schema de Conceptes** (YAML): defineix les ~53 variables de l'informe amb el seu significat, tipus, grup, i prioritats de font
- **Schemas de Format** (YAML): defineix com trobar cada concepte dins d'un tipus de document concret (etiquetes, posicions, patrons)
- **Format Learning**: quan Eva troba un document amb un format nou, el sistema detecta la manca de cobertura, presenta els camps que falten, i quan Eva els omple i desa, el sistema genera automaticament un nou schema de format per a futures extraccions

**Res es trenca**: les 4 referencies de projecte produeixen resultats identics. 197 tests passen.

---

## 2. El problema que resolem

### Abans (label_map.py monolitic)

```python
# 84 entrades barrejant format (etiqueta) i concepte (variable)
LABEL_TO_VARIABLE = {
    "ADREÇA OBRA": "street_address",      # format catala
    "DIRECCIÓN OBRA": "street_address",    # format castella
    "EMPLAÇAMENT": "street_address",       # format tecnic
    "EMPLAZAMIENTO": "street_address",     # format tecnic castella
    ...  # 84 entrades
}

# Prioritats globals per font, iguals per a TOTES les variables
SOURCE_PRIORITY = {
    "user": 10,
    "planol_vision": 20,
    ...
}
```

**Problemes:**
- Cada nou arquitecte amb etiquetes diferents requereix afegir entrades manualment
- Totes les variables tenen les mateixes prioritats de font (pero `utm_x` nomes ve de GPS/ICGC, no d'emails)
- No hi ha metadata sobre que significa cada variable, com es calcula, o de quines fonts pot venir
- Sense mecanisme per aprendre formats nous automaticament

### Ara (dos schemas independents)

```
Document:  "PROMOTOR: Ramon Mitjana SL"
             ↓ Format schema (planol_vision_v1)
             ↓ label "PROMOTOR" → concept_id "client_name"
             ↓
Concepte:  client_name
             ↓ Concept schema (report_variables.yaml)
             ↓ type: text, group: client, required: true
             ↓ source_priority: {user: 10, planol_vision: 20, groq_llm: 42, ...}
             ↓
Informe:   camp "client_name" = "Ramon Mitjana SL"
```

---

## 3. Estructura de fitxers

```
g3dt/
├── schemas/
│   ├── concepts/
│   │   └── report_variables.yaml          # 53 conceptes, 658 linies
│   └── formats/
│       ├── dades_camp_excel_v1.yaml        # DADES.xls
│       ├── pressupost_pdf_v1.yaml          # Pressupostos
│       ├── email_content_v1.yaml           # Emails .msg
│       ├── generic_document_v1.yaml        # Catch-all (84 etiquetes)
│       ├── planol_vision_v1.yaml           # Planols A.01.pdf
│       ├── sondeig_vision_v1.yaml          # Sondeigs (nomes vision)
│       ├── dpsh_vision_v1.yaml             # DPSH (nomes vision)
│       ├── groq_extraction_v1.yaml         # Extraccio LLM Groq
│       └── learned/                        # Formats apresos per Eva
│           └── {role}/
│               └── learned_{role}_{hash}.yaml
├── automation/
│   ├── schemas/
│   │   ├── __init__.py                     # Exporta registres singleton
│   │   ├── models.py                       # Pydantic: ConceptDefinition, FormatSchema, LabelMapping
│   │   ├── loader.py                       # ConceptRegistry + FormatRegistry
│   │   └── format_writer.py               # Serialitza formats apresos a YAML
│   ├── format_learner.py                   # FormatLearner: deteccio + aprenentatge
│   └── fileminer/
│       ├── label_map.py                    # Pont backward-compat (71 linies, era 193)
│       ├── models.py                       # Signal amb concept_id, MiningResult amb format_detections
│       └── competition.py                  # resolve_competition(use_concept_id=True)
├── web/
│   ├── wizard_service.py                   # _merge_prefills + _save_learned_formats
│   └── api.py                              # GET /api/document-pages/{project}
├── templates/validation/
│   └── review.html                         # Banner ambar + camps destacats + toast
└── tests/
    ├── benchmark/
    │   ├── snapshot_baseline.py             # Regressio contra referencies
    │   └── snapshots/*.json                # 4 projectes congelats
    ├── test_schema_loader.py               # 16 tests de schemas
    └── test_format_learner.py              # 17 tests del format learner
```

---

## 4. Schema de Conceptes

### Fitxer: `schemas/concepts/report_variables.yaml`

Defineix **53 conceptes** en **11 grups**:

| Grup | Conceptes | Exemples |
|------|-----------|----------|
| client | 5 | client_name, client_nif, client_phone, client_email, contact_name |
| architect | 2 | architect_name, architect_company |
| location | 3 | street_address, municipality, province |
| building | 8 | building_type, num_floors, superficie_parcela, superficie_construida, building_height_m, has_basement, has_retaining_walls, superficie_cadastral |
| project | 3 | expedient, field_date, access_url |
| field_work | 5 | field_work_dates, field_work_dates_text, site_description, access_description, cota_referencia |
| parcel | 11 | adjacent_north/south/east/west, site_position, parcel_shape, is_urban, is_sloped, slope_percent, slope_direction, is_anthropized |
| geotechnical | 8 | num_soil_levels, foundation_depth_m, geomech_gamma/cohesion/phi/E, Es_settlement, historia_geologica_template |
| lab | 2 | sulfate_mg_kg, lab_tests |
| geology | 3 | icgc_unit_code, icgc_unit_description, icgc_unit_epoch |
| coordinates | 3 | utm_x, utm_y, referencia_catastral |

### Estructura d'un concepte

```yaml
street_address:
  type: text                    # text | numeric | date | boolean | list | integer | url | coords
  group: location
  required: true
  description_ca: "Adreca postal de l'obra"
  source_priority:              # per concepte, no global
    user: 10                    # Eva sempre guanya
    planol_vision: 20           # Claude vision del planol
    pressupost_pdf: 30
    dades_camp_excel: 35
    groq_llm: 42
    content_email: 43
    content_pdf: 45
    folder_name: 60
  wizard_field: street_address  # si el camp del wizard te nom diferent
```

### Prioritats de font (19 fonts)

| Prioritat | Font | Descripcio |
|-----------|------|-----------|
| 10 | user | Edicio manual d'Eva |
| 20 | planol_vision | Claude vision del planol |
| 20 | sondeig_vision | Claude vision del sondeig |
| 20 | dpsh_vision | Claude vision del penetros |
| 25 | coordenades_txt | GPS de camp |
| 30 | pressupost_pdf | Pressupost de G3 |
| 30 | icgc_api | API ICGC (geologia, elevacio) |
| 30 | cadastre_api | API Cadastre |
| 35 | dades_camp_excel | Fitxa Excel de camp |
| 35 | comanda_lab_excel | Comanda de laboratori |
| 40 | geocode_nominatim | Geocodificacio OpenStreetMap |
| 42 | groq_llm | Extraccio LLM Groq |
| 43 | content_email | Cos d'email |
| 44 | content_email_attachment | Adjunt d'email |
| 45 | content_pdf | PDF generic |
| 45 | content_docx | Word generic |
| 45 | content_excel | Excel generic |
| 45 | content_text | Text generic |
| 60 | folder_name | Nom de carpeta (ultim recurs) |

**Diferencia clau vs. el sistema antic**: ara cada concepte pot tenir prioritats **diferents**. Per exemple, `utm_x` nomes accepta fonts de coordenades (user, coordenades_txt, icgc_api, cadastre_api, geocode_nominatim), mentre que `client_name` pot venir de qualsevol document.

---

## 5. Schemas de Format

### Fitxers: `schemas/formats/*.yaml`

Cada format schema defineix com trobar conceptes dins d'un tipus concret de document.

### Estructura d'un format

```yaml
format_id: dades_camp_excel_v1
name: "DADES CAMP Excel Standard (G3)"
description: "Fitxa Excel estàndard de camp de G3"
document_roles: [dpsh_excel]         # Rols SmartScan que usen aquest format
source_type: dades_camp_excel        # Clau de SOURCE_PRIORITY
created_by: system                   # "system" o "eva" (apres)
label_mappings:
  - labels: ["CLIENT", "CLIENTE", "PROMOTOR", "PROPIETARI", "PROMOTOR/PROPIETARI", "NOM CLIENT", "NOMBRE CLIENTE"]
    concept_id: client_name
    confidence: 0.95
  - labels: ["ADREÇA OBRA", "DIRECCIÓN OBRA", "ADREÇA", "DIRECCIÓ", "DIRECCIÓN", "EMPLAÇAMENT", "EMPLAZAMIENTO", "UBICACIÓ", "UBICACIÓN"]
    concept_id: street_address
    confidence: 0.90
  # ... mes mappings
```

### 8 formats del sistema

| Format | Rol SmartScan | Font | Etiquetes | Confianca |
|--------|---------------|------|-----------|-----------|
| dades_camp_excel_v1 | dpsh_excel | dades_camp_excel | 15 grups | 0.85-0.95 |
| pressupost_pdf_v1 | pressupost_pdf | pressupost_pdf | 5 grups | 0.85-0.90 |
| email_content_v1 | — | content_email | 5 grups | 0.80-0.85 |
| generic_document_v1 | — | content_pdf | 17 grups (catch-all) | 0.75-0.80 |
| planol_vision_v1 | architect_plan | planol_vision | 9 grups | 0.80-0.85 |
| sondeig_vision_v1 | sondeig_field_sheet | sondeig_vision | 0 (vision-only) | — |
| dpsh_vision_v1 | dpsh_field_sheet | dpsh_vision | 0 (vision-only) | — |
| groq_extraction_v1 | — | groq_llm | 9 grups | 0.80-0.85 |

**generic_document_v1** es el catch-all: conte TOTES les 84 etiquetes originals de `LABEL_TO_VARIABLE` amb confianca mes baixa (0.75-0.80). Aixo garanteix que cap etiqueta es perd.

**sondeig_vision_v1** i **dpsh_vision_v1** no tenen label_mappings perque la visio de Claude utilitza prompts estructurats, no coincidencia d'etiquetes.

---

## 6. Infraestructura Python

### Models Pydantic (`automation/schemas/models.py`)

```python
class ConceptDefinition(BaseModel):
    concept_id: str                         # "street_address"
    type: str                               # text, numeric, date, boolean, list, integer, url, coords
    group: str                              # client, location, building, ...
    required: bool = False
    description_ca: str = ""
    source_priority: dict[str, int] = {}    # {font: prioritat}
    wizard_field: str | None = None         # nom alternatiu al wizard
    default: Any = None

class LabelMapping(BaseModel):
    labels: list[str]                       # ["CLIENT", "CLIENTE", ...]
    concept_id: str                         # "client_name"
    confidence: float = 0.90

class FormatSchema(BaseModel):
    format_id: str                          # "dades_camp_excel_v1"
    name: str
    description: str = ""
    document_roles: list[str] = []          # rols SmartScan
    source_type: str = ""                   # clau SOURCE_PRIORITY
    created_by: str = "system"              # "system" o "eva"
    label_mappings: list[LabelMapping] = []
```

### Registres (`automation/schemas/loader.py`)

Dos singletons lazy-loaded que carreguen YAML a demanda:

#### ConceptRegistry

```python
class ConceptRegistry:
    def get_concept(concept_id: str) -> ConceptDefinition | None
    def get_priority(concept_id: str, source_type: str) -> int  # 50 si no trobat
    def all_concept_ids() -> set[str]
    def get_default_priority(source_type: str) -> int  # minim entre tots els conceptes
```

- Carrega: `schemas/concepts/report_variables.yaml`
- Cache en memoria al primer acces

#### FormatRegistry

```python
class FormatRegistry:
    def get_format(format_id: str) -> FormatSchema | None
    def formats_for_role(role: str) -> list[FormatSchema]
    def label_to_concept(label: str, format_id: str | None = None) -> str | None
    def build_label_map() -> dict[str, str]  # pont backward-compat
```

- Carrega: `schemas/formats/*.yaml` + `schemas/formats/learned/**/*.yaml`
- `build_label_map()` produeix un diccionari identic al antic `LABEL_TO_VARIABLE`
- `label_to_concept()` busca primer al format especific, despres a tots

### Pont backward-compat (`automation/fileminer/label_map.py`)

```python
# 71 linies (era 193). Nomes carrega des de YAML.
LABEL_TO_VARIABLE: dict[str, str] = _load_label_map()           # FormatRegistry.build_label_map()
SOURCE_PRIORITY: dict[str, int] = _load_source_priority()       # ConceptRegistry.get_default_priority()

def get_priority(source_type: str) -> int:
    return SOURCE_PRIORITY.get(source_type, 50)
```

Tot el codi existent que importa `LABEL_TO_VARIABLE` o `SOURCE_PRIORITY` funciona sense canvis.

---

## 7. Signal amb concept_id

### Abans

```python
class Signal(BaseModel):
    maps_to: str | None = None    # "street_address"
```

### Ara

```python
class Signal(BaseModel):
    maps_to: str | None = None      # "street_address" (legacy)
    concept_id: str | None = None   # "street_address" (nou, mateix valor)
```

Tots els miners (`_detection.py`, `excel_miner.py`) estableixen `concept_id = maps_to` per a cada Signal extret. La competicio ara agrupa per `concept_id` per defecte:

```python
def resolve_competition(signals, *, use_concept_id=True):
    for s in signals:
        key = (s.concept_id or s.maps_to) if use_concept_id else s.maps_to
        # ... resta identic
```

El fallback `or s.maps_to` garanteix que Signals antics (sense concept_id) segueixen funcionant.

---

## 8. Format Learning: deteccio i aprenentatge

### Flux complet

```
Eva selecciona projecte al wizard
        ↓
auto_extract() → MiningResult amb Signals
        ↓
_merge_prefills() executa FormatLearner.detect_format()
per a cada fitxer amb rol SmartScan
        ↓
Per a cada fitxer:
  1. Busca camps esperats per al rol (EXPECTED_FIELDS)
  2. Compta quants concept_ids extrets coincideixen
  3. Si cobertura < 60% → is_new = True
        ↓
Si hi ha deteccions noves:
  merged["_format_learning"] = {
      "value": {"active": True, "detections": [...]},
      "source": "system"
  }
        ↓
Wizard mostra banner ambar:
  "Format nou detectat: A.01.pdf"
  "S'han extret 4 de 10 camps esperats (40%)"
  Camps que falten → vora taronja + badge "revisar"
        ↓
Eva omple els camps que falten manualment
        ↓
Eva prem "Desar"
        ↓
save_wizard() detecta que _format_learning era actiu
        ↓
_save_learned_formats():
  Per a cada camp que faltava i Eva va omplir:
    → confirmed_mapping = {label: "FIELD_NAME", concept_id: "field_name"}
        ↓
FormatLearner.confirm_mappings() → format_writer.write_learned_format()
        ↓
Escriu YAML a schemas/formats/learned/{rol}/{format_id}.yaml
        ↓
Toast verd: "Format desat. Proper cop s'extrauran automaticament."
        ↓
Proper projecte amb el mateix format:
  FormatRegistry carrega el YAML apres
  → Etiquetes reconegudes automaticament
  → No apareix banner
```

### Camps esperats per rol

```python
EXPECTED_FIELDS = {
    "architect_plan": [
        "architect_name", "architect_company", "client_name",
        "street_address", "municipality", "building_type",
        "num_floors", "superficie_parcela", "superficie_construida",
        "building_height_m",
    ],                                          # 10 camps
    "dpsh_excel": [
        "client_name", "street_address", "municipality",
        "architect_name", "field_date", "expedient",
    ],                                          # 6 camps
    "pressupost_pdf": [
        "client_name", "street_address", "municipality",
        "architect_name", "building_type",
    ],                                          # 5 camps
}
```

### Llindar de deteccio

- **LEARNING_THRESHOLD = 0.6** (60%)
- Si menys del 60% dels camps esperats s'han extret → format nou
- Exemple: un planol d'un arquitecte desconegut que nomes extreu 4 de 10 camps (40%) → trigger

### Format apres (YAML generat)

```yaml
format_id: learned_architect_plan_a1b2c3d4
name: "Learned format: architect_plan (A.01.pdf)"
description: "Auto-generated from Eva's confirmation on A.01.pdf"
document_roles: [architect_plan]
source_type: planol_vision
created_by: eva
created_at: "2026-04-05T14:32:00+00:00"
source_project_file: A.01.pdf
label_mappings:
  - labels: ["ARCHITECT NAME"]
    concept_id: architect_name
    confidence: 0.95
  - labels: ["CLIENT NAME"]
    concept_id: client_name
    confidence: 0.95
```

- **Confianca 0.95**: els mappings confirmats per Eva son molt fiables
- **Ubicacio**: `schemas/formats/learned/{rol}/{format_id}.yaml`
- **Format ID**: `learned_{rol}_{sha256_primer_8_chars}`

---

## 9. Interficie del wizard

### Banner ambar

Apareix a la pestanya Wizard quan hi ha formats nous detectats:

```
+--------------------------------------------------------------+
| (!) Format nou detectat: A.01.pdf                            |
|     S'han extret 4 de 10 camps esperats (40%).               |
|     Revisa els camps marcats en taronja.                     |
|                                           [Amagar]           |
+--------------------------------------------------------------+
```

### Camps destacats

Camps que falten reben:
- **Vora taronja** (CSS `.format-learning-field`): `border: 2px solid #f59e0b`
- **Fons ambar clar**: `background-color: #fffbeb`
- **Badge "revisar"** (CSS `.source-badge.format-learning`): fons `#fef3c7`, text `#92400e`

### Toast de confirmacio

Despres de desar amb format learning actiu:
- **Toast verd** a la cantonada inferior dreta
- Text: "Format desat. Proper cop s'extrauran automaticament."
- Desapareix despres de 3 segons

### Comportament

- **>80% cobertura**: no apareix banner, flux normal
- **40-80% cobertura**: banner ambar, camps destacats, Eva revisa
- **<40% cobertura**: banner prominent, tots els camps marcats

---

## 10. API endpoint nou

### `GET /api/document-pages/{project_name}?file={path}`

Retorna metadata d'un document per al drawer del format learning:

```json
{
    "file": "A.01.pdf",
    "pages": 3,
    "role": "",
    "size_bytes": 1234567
}
```

Utilitza PyMuPDF per comptar pagines de PDF.

---

## 11. Tests

### Suite de regressio (12 tests)

`tests/benchmark/snapshot_baseline.py` — compara l'output actual dels 4 projectes de referencia contra snapshots congelats:

- **test_snapshot_exists**: verifica que existeix snapshot per a cada projecte
- **test_resolved_values_match**: valors resolts identics (variable, valor, font)
- **test_signal_counts_stable**: comptatge de senyals estable (tolerancia 5%)

### Tests de schemas (16 tests)

`tests/test_schema_loader.py`:

- YAML carrega sense errors
- Comptatge de conceptes >= 40
- Conceptes core existeixen (client_name, street_address, etc.)
- Prioritats de font coincideixen amb l'antic `SOURCE_PRIORITY`
- `user` sempre te prioritat 10
- `build_label_map()` produeix diccionari identic a l'antic `LABEL_TO_VARIABLE`
- Tots els concept_ids referenciats als formats existeixen als conceptes

### Tests del format learner (17 tests)

`tests/test_format_learner.py`:

- Deteccio es dispara quan cobertura < 60%
- Deteccio NO es dispara quan cobertura >= 60%
- Rols sense EXPECTED_FIELDS → no deteccio
- confirm_mappings genera YAML valid
- Serialitzacio/deserialitzacio correcta

### Total: 197 tests passen

---

## 12. Migrar a la nova arquitectura (guia)

### Afegir un nou concepte

1. Editar `schemas/concepts/report_variables.yaml`
2. Afegir l'entrada amb type, group, description_ca, source_priority
3. Si el concepte es pot extreure de documents: afegir etiquetes als format schemas corresponents
4. Executar `pytest tests/test_schema_loader.py` per verificar

### Afegir un nou format (manual)

1. Crear `schemas/formats/{format_id}.yaml`
2. Definir format_id, name, document_roles, source_type
3. Afegir label_mappings amb etiquetes → concept_ids
4. El FormatRegistry el carregara automaticament al proper reinici

### Afegir un nou format (automatic via Eva)

1. Eva processa un projecte amb documents d'un format nou
2. El wizard mostra el banner ambar
3. Eva omple els camps que falten
4. Eva desa → el sistema genera el YAML automaticament
5. Propers projectes amb el mateix format → reconeixement automatic

### Afegir una nova font de dades

1. Afegir la font als `source_priority` dels conceptes rellevants a `report_variables.yaml`
2. El `get_default_priority()` calculara automaticament la prioritat global

---

## 13. Decisions de disseny

### Per que YAML i no una base de dades?

- Els schemas canvien poc (els conceptes son estables, els formats creixen lentament)
- YAML es llegible per humans i versionable amb git
- No cal un servidor de BD per un sistema que s'executa al portatil d'Eva
- Carregar ~15KB de YAML a memoria es instantani

### Per que concept_id = maps_to (per ara)?

La separacio conceptual es important per al futur (calculs basats en conceptes, prioritats per concepte), pero el canvi de nom hauria trencat massa codi. Amb `concept_id = maps_to`, tenim la infraestructura preparada sense trencar res.

### Per que el llindar del 60%?

- Massa alt (80%): molts documents normals activarien format learning innecessariament
- Massa baix (40%): formats realment nous podrien passar desapercebuts
- 60% es un bon equilibri: 4 de 10 camps extrets = clarament un format diferent

### Per que el catch-all generic_document_v1?

Sense un catch-all, qualsevol PDF/docx/text no classificat perdria totes les coincidencies d'etiquetes. El catch-all amb confianca baixa (0.75-0.80) assegura que les etiquetes es troben, pero amb menys pes que fonts mes fiables.

---

## 14. ConceptScout: descobriment concepte→fitxer

**Data:** 2026-04-07
**Branca:** `feature/concept-format-separation`

### El problema

SmartScan classifica fitxers per TIPUS (architect_plan, dpsh_excel, etc.) pero no sap quins fitxers contenen quins CONCEPTES. Quan SmartScan classifica malament o el fitxer esperat no existeix, el pipeline no pot extreure dades encara que estiguin en un altre fitxer.

### Arquitectura de dues capes

```
ConceptScout  → concept_map.json  → "ON es cada concepte?" (routing a nivell de fitxer)
SmartScan     → file_mapping.json → "QUIN TIPUS es aquest fitxer?" (seleccio d'extractor)
Extractors    → vision/FileMiner  → "Extreu el valor" (schemas concepte-format)
Normalitzador → claus canoniques   → "Estandarditza la sortida"
```

### Modul: `automation/concept_scout/`

- `scanner.py`: enumera TOTS els fitxers (inclou PDF/, FOTOGRAFIES/, msg_attachments/)
- `aggregator.py`: agrupa senyals FileMiner per concepte, ordena per prioritat
- `vision_probe.py`: classificacio visual lleugera per fitxers no-text (Groq primer, Claude fallback)
- `models.py`: ConceptMap, FileEntry, ConceptSource (amb camp `page` per estalviar tokens)

### Sortida: `concept_map.json`

Per cada concepte, llista ordenada de fitxers on es pot trobar:
```json
{
  "concept_sources": {
    "architect_name": [
      {"file": "A.01.pdf", "confidence": 0.95, "extraction_method": "planol_vision", "page": 1},
      {"file": "PRESSUPOST.pdf", "confidence": 0.7, "extraction_method": "content_pdf"}
    ]
  },
  "file_inventory": [...],
  "_unresolved": ["foundation_depth_m", ...],
  "_warnings": [...]
}
```

### Integracio al pipeline

- **Fase 0.45**: `scout_project()` s'executa despres de FileMiner + Groq (consumeix senyals enriquits)
- **Fallback visio**: `_supplement_from_concept_map()` a `vision_groq.py` — quan SmartScan no assigna fitxer a un vision_type, concept_map proporciona el millor candidat
- **Wizard**: banner "N conceptes detectats en fitxers del projecte"

### Resultats audit (2026-04-07, 7 projectes)

| Concepte | Cobertura text | Necessita visio |
|----------|:-:|:-:|
| building_type, street_address, municipality, field_date | 7/7 | No |
| client_name | 5/7 | Parcial |
| architect_name, architect_company | 0/7 | Si (planol) |
| num_floors, building_height_m | 0-1/7 | Si (planol) |
| superficie_construida_m2, superficie_parcela_m2 | 0/7 | Si (planol) |
| num_soil_levels, cota_referencia | 0/7 | Si (sondeig) |

---

*Document de referencia tecnica. Per a preguntes: `grep -r "concept_id\|format_learning\|ConceptRegistry\|concept_scout" automation/ web/`*
