# Guia del Sistema d'Extracció G3DT

**Data:** 2026-04-06
**Objectiu:** Document de referència tècnica complet del pipeline d'extracció, des de fitxers crus fins a valors finals comparats amb Eva.

---

## 1. Visió General

El sistema G3DT extreu dades de projectes de construcció (PDFs, Excels, emails, APIs) per generar informes geotècnics. El pipeline te 3 capes principals:

```
CAPA 1: EXTRACCIÓ          CAPA 2: COMPETICIÓ + MERGE       CAPA 3: COMPARACIÓ
────────────────────       ────────────────────────────      ─────────────────────
Fase 0: FileScanner   ─┐
Fase 0.3: FileMiner    │   resolve_competition()
Fase 0.4: Groq LLM    ├── (guanyador per variable)  ─┐
Fase 1: DPSH Excel     │                              │     diagnostic_trace.py
Fase 1.1: Dates camp   │                              ├──   (vs eva_reference_values)
Fase 2: Lab PDF        ├── auto_extract() prefills     │
Fase 2.5: Geocode      │                              │
Fase 3: HTTP APIs      │   _merge_prefills()           │
Fase 3.5: Ortofoto     │   (vision + wizard + calc)  ─┘
                       │
Vision: planol/sondeig/dpsh ─┘
```

**Punt clau:** El diagnostic_trace.py crida `get_prefills()` que executa **tot** el pipeline. Però la visibilitat del que passa internament és limitada.

---

## 2. Arquitectura Concepte-Format

### 2.1 Dos schemas independents

**Conceptes** (`schemas/concepts/report_variables.yaml`): 53 variables amb significat, tipus, i prioritats de font **per variable**.

```yaml
client_name:
  type: text
  group: client
  required: true
  source_priority:
    user: 10           # Eva sempre guanya
    planol_vision: 20  # Claude vision del plànol
    pressupost_pdf: 30
    dades_camp_excel: 35
    groq_llm: 42
    content_email: 43
    content_pdf: 45
    folder_name: 60
```

**Formats** (`schemas/formats/*.yaml`): 8 schemas de sistema que mapegen etiquetes de documents → concept_ids.

```yaml
# dades_camp_excel_v1.yaml
label_mappings:
  - labels: ["CLIENT", "CLIENTE", "PROMOTOR"]
    concept_id: client_name
    confidence: 0.95
```

### 2.2 Com interactuen

```
Document: "PROMOTOR: Ramon Mitjana SL"
    ↓ Format schema identifica etiqueta "PROMOTOR"
    ↓ Mapping: "PROMOTOR" → concept_id "client_name"
    ↓ Confiança: 0.95 (del format)
    ↓ Prioritat: 30 (del source_priority del concepte per "pressupost_pdf")
    ↓
Signal(label="PROMOTOR", value="Ramon Mitjana SL",
       concept_id="client_name", priority=30, confidence=0.95)
```

### 2.3 Pont backward-compat

`automation/fileminer/label_map.py` (71 línies, era 193) carrega tot des de YAML:
- `LABEL_TO_VARIABLE` = tots els label→concept_id de tots els formats
- `SOURCE_PRIORITY` = prioritats globals (mínim per font entre tots els conceptes)
- `get_priority(source_type)` = lookup ràpid

**Important:** La competició actual utilitza `SOURCE_PRIORITY` **global**, no les prioritats **per concepte** del YAML. Les prioritats per concepte estan definides però **no s'apliquen** a la competició de signals. Això és un gap significatiu.

### 2.4 Format Learning

Quan un document té format desconegut (<60% camps esperats):
1. Wizard mostra banner ambar
2. Eva omple camps manualment
3. Al desar, el sistema genera YAML a `schemas/formats/learned/`
4. Propers projectes amb el mateix format → reconeixement automàtic

---

## 3. Fases del Pipeline en Detall

### Fase 0.1: FileScanner / SmartScan

**Fitxer:** `automation/auto_extractor.py:420-476`

Classifica tots els fitxers del projecte per rol:
- `dpsh_excel` → DADES PER ANAR A CAMP.xlsx
- `architect_plan` → A.01.pdf
- `sondeig_field_sheet` → SONDEIG.pdf
- `dpsh_field_sheet` → PENETROS.pdf
- `pressupost_pdf` → Pressupost*.pdf/msg
- etc.

SmartScan (3 tiers): Tier 1 = filename heurístics, Tier 2 = fingerprinting (.xlsx structure), Tier 3 = Groq vision (imatges).

**Output:** `file_mapping.json` amb `{fitxer: {role, confidence, ...}}`

### Fase 0.3: FileMiner

**Fitxer:** `automation/fileminer/__init__.py:130-285`, `auto_extractor.py:478-560`

**Què fa:**
1. Recorre tots els fitxers del projecte recursivament
2. Per a cada fitxer: determina `source_type` (via SmartScan role o heurístics de nom)
3. Instancia el miner adequat (ExcelMiner, TextMiner, PdfTextMiner, DocxMiner, MsgMiner)
4. Cada miner busca etiquetes (labels) al document i crea Signals

**Documents que SALTA:**
- Directoris: `PDF`, `validation`, `.git`, `__pycache__`
- Extensions: `.png`, `.jpg`, `.psd`, `.db`, `.tmp` (vision handled separately)
- Fitxers propis: `file_mapping.json`, `user_data.json`, `~$*`
- Informes de referència: `^\d+_informe.*\.docx?$`

**Miners disponibles:**

| Miner | Extensions | Mètode |
|-------|-----------|--------|
| ExcelMiner | .xls, .xlsx | Cel·la adjacent (etiqueta a una cel·la, valor a la del costat) |
| PdfTextMiner | .pdf | Regex sobre text extret amb PyMuPDF |
| DocxMiner | .docx | Regex sobre paràgrafs |
| MsgMiner | .msg | Cos + adjunts de l'email Outlook |
| TextMiner | .txt | Regex sobre contingut |

**Cada miner genera Signals:**

```python
Signal(
    type: SignalType,          # TEXT, NUMERIC, DATE, IMAGE, COORDS
    label: str,                # "ADREÇA OBRA", "CLIENT", etc.
    value: Any,                # Valor extret
    maps_to: str | None,       # "street_address" (via LABEL_TO_VARIABLE)
    concept_id: str | None,    # = maps_to (nou, per futura separació)
    source_file: str,          # Path relatiu dins projecte
    extraction_method: str,    # "cell_adjacent", "regex", "embedded_image"
    confidence: float,         # 0.0-1.0
    priority: int,             # De SOURCE_PRIORITY[source_type]
)
```

**Segona passada:** Mina fitxers dins `validation/msg_attachments/` (adjunts extrets d'emails .msg).

### Competició de Signals

**Fitxer:** `automation/fileminer/competition.py:64-110`

```python
def resolve_competition(signals, *, use_concept_id=True):
    # 1. Agrupa per concept_id (o maps_to)
    # 2. Per cada grup, ordena per (priority ASC, confidence DESC)
    # 3. El primer és el guanyador
    # 4. Retorna ResolvedValue(winner, alternatives=[...])
```

**Punt crític:** La prioritat ve de `SOURCE_PRIORITY[source_type]` — la mateixa per a TOTES les variables. Les prioritats per-concepte del YAML conceptual **no s'utilitzen** aquí.

Exemple real del diagnostic:
```
client_name a Bell-Lloc:
  #1 pri=30 conf=0.80 'ARQUITECTURA BOSCH NOVELL'  ← GUANYA (pressupost_pdf pri=30)
  #2 pri=30 conf=0.80 'ARQUITECTURA BOSCH NOVELL'  (RE_ pressupost)
  #3 pri=35 conf=0.90 'ARQUITECCTURA BOSCH NOVELL'  (DADES CAMP xlsx pri=35)
  #4 pri=45 conf=0.80 'RAMON MITJANA S.L.'  (informe_v0.pdf pri=45)
  Eva espera: RAMON MITJANA S.L. ← Està al signal #4 però perd per prioritat
```

### Fase 0.4: Groq Deep Mine

**Fitxer:** `auto_extractor.py:562-687`

S'executa NOMÉS si:
- `GROQ_API_KEY` està configurat
- Hi ha variables crítiques encara sense valor
- Fitxers "high-value" (emails, pressupostos, DPSH data) amb <3 signals

Envia el contingut del fitxer a Groq LLM amb un prompt d'extracció. Respostes arriben com a Signals amb `source_type=groq_llm`, `priority=42`.

### Fase 1.0: DPSH Excel

**Fitxer:** `auto_extractor.py:861-910`, `automation/dpsh_extractor.py`

Extreu de `DPSH.xls`:
- Valors N20 per profunditat
- Profunditat de refús
- `foundation_depth_m` derivat del refús
- `Es_settlement` = 2.5 × Nb (Nb = N20/0.83)

### Fase 1.1: Dates de Camp

**Fitxer:** `auto_extractor.py:912-935`

Extreu dates de fitxers DPSH/Lab via regex sobre text PDF:
- `field_work_dates` (llista ISO)
- `field_work_dates_text` (text formatat: "1 i 6 d'octubre de 2025")

### Fase 2.0: Laboratori PDF

**Fitxer:** `auto_extractor.py:941-969`, `automation/lab_extractor.py`

Extreu `sulfate_mg_kg` del PDF de la comanda de laboratori via PyMuPDF regex.

### Fase 2.5: Geocodificació

**Fitxer:** `auto_extractor.py:975-1125`

**Condició:** Només si NO hi ha COORDENADES.txt (GPS de camp).

Pipeline: Nominatim → Cadastre OVC → WFS INSPIRE → UTM ETRS89.

**Important:** Necessita `street_address` + `municipality` de fases anteriors.

### Fase 3: HTTP APIs (requereix UTM)

**Condició:** TOT el Fase 3 es SALTA si no hi ha coordenades UTM.

| Sub-fase | Font | Variables | Fitxer:línia |
|----------|------|-----------|-------------|
| 3.0 | ICGC WMS geologia | icgc_unit_code, description, epoch | auto_extractor.py:1131 |
| 3.1 | ICGC MDT elevació | cota_referencia | auto_extractor.py:1151 |
| 3.2 | ICGC MDT pendent | slope_percent, slope_direction | auto_extractor.py:1166 |
| 3.3 | Cadastre adjacents | adjacent_north/south/east/west | auto_extractor.py:1190 |
| 3.4 | WFS àrea parcel·la | superficie_cadastral | auto_extractor.py:1349 |

**Fase 3.3 (adjacents)** usa "geocode-first": busca la parcel·la per adreça (no per UTM DPSH), després consulta adjacents al Cadastre. Retorna dades crues: "parcel·la buida", "parcel·la amb construcció", "Carrer X".

### Fase 3.5: Ortofoto (experimental)

**Fitxer:** `auto_extractor.py:1373-1402`

Guardat per `G3DT_ORTHO_ENRICHMENT=1`. Descarrega ortofoto ICGC + analitza amb vision.

---

## 4. Vision: Extracció de PDFs amb Claude

**Fitxer:** `automation/vision_extractor.py`

### 4.1 Tipus de vision

| Tipus | Fitxer font | JSON cache | Variables clau |
|-------|------------|-----------|----------------|
| planol | A.01.pdf | planol_extracted.json | architect, building_type, num_floors, superficies |
| sondeig | SONDEIG.pdf | sondeig_extracted.json | capes sòl, SPT, profunditats, elevation_z |
| dpsh | PENETROS.pdf | dpsh_extracted.json | N20 per profunditat, refús, nivell freàtic |
| sondeig_annex | ANNEXES/*_sondeig.pdf | sondeig_extracted.json | unitat litològica, nivells geològics |

### 4.2 Com funciona

1. Troba el PDF via `file_mapping.json` (role → fitxer)
2. Renderitza pàgines a PNG @ 150 DPI
3. Envia imatges + prompt d'extracció a Claude Sonnet
4. Parseja resposta JSON
5. **Cache** a `validation/{type}_extracted.json` (invalidat si PDF canvia)

### 4.3 Com s'integra al pipeline

**En producció:** `wizard_service._merge_prefills()` crida `_run_vision_phase()` que executa la visió en subprocess.

**En diagnostic:** `get_prefills(force_refresh=True)` executa el pipeline complet incloent visió (si no està cached).

**Merge de vision:** `UserDataWizard.load_prefills()` llegeix els JSONs cached i genera camps per al wizard. Aquests es fusionen amb els prefills de `auto_extract()` a `_merge_prefills()`.

### 4.4 Normalització de vision

**Fitxer:** `automation/vision_normalizer.py`

Claude vision retorna JSON amb claus no-deterministes. El normalitzador canonicalitza:
- `spt_data`/`spt_test` → `spt_in_dpsh`
- `spt_tests` → `spt_results`; `test_name` → `test_id`
- `refusal_exact_m`/`refusal_notation` → `refusal_depth_m`

---

## 5. Merge Final: wizard_service.py

**Fitxer:** `web/wizard_service.py:456-620`

### 5.1 get_prefills() — Punt d'entrada

```python
def get_prefills(project_name, force_refresh=False):
    auto_result = auto_extract(project_path)      # Fases 0-3
    return _merge_prefills(project_name, project_path, auto_result)
```

### 5.2 _merge_prefills() — Lògica de fusió

Ordre d'operacions:

1. **Executa fase de visió** (`_run_vision_phase`)
2. **Carrega wizard prefills** (`UserDataWizard.load_prefills`) — llegeix vision JSONs + genera defaults
3. **Fusiona auto_extract + wizard:**
   - Prefills d'auto_extract s'afegeixen primer
   - Wizard prefills es fusionen respectant fonts: wizard "default standard" NO sobreescriu dades reals
4. **Millora adreça** — usa `site_address` de vision per millorar `street_address`
5. **Cota referència** — cadena de prioritat: user > sondeig elevation_z > ICGC MDT
6. **Fallback adjacents** — si Fase 3 es va saltar, geocodifica des d'adreça plànol
7. **Generació de templates** — `access_description`, `site_description` (genèrics)
8. **Càlculs geotècnics** — densitat, cohesió, phi des de tipus de sòl
9. **Terzaghi-Peck** — qa_value, settlement amb defaults (B=1.0, Df=0.8)
10. **Format learning** — detecta formats nous

### 5.3 Càlculs geotècnics (Terzaghi)

**Fitxer:** `automation/terzaghi_calculator.py`

```
Inputs: Nb (N20/0.83), B (amplada fonament), Df (profunditat), cohesion
  ↓
Terzaghi-Peck: qa = Nb/12 × width_correction × Fd
  ↓
Cap professional: min(qa, 3.0) si sòl, min(qa, 5.0) si roca (cohesion >= 0.5)
  ↓
Settlement (Schmertmann): Es = 2.5×Nb (square), 3.5×Nb (strip)
```

**Problema actual:** En mode diagnòstic, no hi ha `user_data.json` → B=1.0, Df=0.8 (defaults). Eva usa valors reals del projecte. Això explica la divergència sistemàtica de qa_value.

---

## 6. Sistema de Diagnòstic

### 6.1 diagnostic_trace.py

**Fitxer:** `scripts/diagnostic_trace.py`

**Què fa:**
1. Carrega `eva_reference_values.json` per al projecte
2. Executa `get_prefills(force_refresh=True)` — pipeline complet
3. Compara cada variable: MATCH, CLOSE, MISMATCH, NOT_EXTRACTED
4. Per a MISMATCH: mostra els 5 millors signals competidors

**Què mostra bé:**
- Valor final del pipeline vs valor d'Eva
- Font del valor guanyador
- Signals competidors per FileMiner (priority, confidence, valor, fitxer)

### 6.2 El que el diagnòstic NO mostra

**Gaps crítics de visibilitat:**

| Informació que falta | Per què importa |
|---------------------|-----------------|
| Quines fases es van executar realment | Si Fase 3 no va córrer, adjacents són de cache anterior? |
| Què va extreure vision vs què es va usar | Vision pot extreure correctament però merge pot triar altra font |
| Com es van derivar valors calculats | qa_value: quins inputs (Nb, B, Df, cohesion)? |
| Per què un signal va ser rebutjat | FileMiner rebutja adreces G3 internes, etc. |
| Quins fitxers es van processar | Si un fitxer no es va processar, els seus signals no existeixen |
| Cobertura de formats | Quants label_mappings van coincidir per document? |
| HTTP API responses | Adjacents del Cadastre — resposta crua? |

### 6.3 Tipus de comparació

**Fitxer:** `scripts/compare_benchmarks.py`

| Mode | Quan s'usa | Criteri |
|------|-----------|---------|
| Numèric | Variables a `NUMERIC_VARS` | ≤5% → MATCH, ≤15% → CLOSE |
| Text | Per defecte | Idèntic → MATCH, substring → CLOSE |
| Normalitzat | Variables amb normalitzador | Normalitza primer, després compara |

**Normalitzadors disponibles:**
- `municipality` → elimina provincia ("Rubí (Barcelona)" → "Rubí")
- `street_address` → expandeix abreviatures, elimina codi postal
- `radon_zone` → "Zona I" → "1"
- `seismic_ab_text` → extreu valor numèric

### 6.4 Tiers de variables (compare_benchmarks.py)

| Tier | Descripció | Exemples | Target |
|------|-----------|----------|--------|
| A | Auto-extractable | municipality, street_address, sulfate_mg_kg, dates | 95% OK |
| B | Manual/camp | adjacents, site_description, access_description | Amb templates |
| C | Judici professional | qa_value, settlement, k30_value | Dins 10% |

---

## 7. Flux Complet d'una Variable: Exemple client_name

Per il·lustrar com tot encaixa, tracem `client_name` per Bell-Lloc:

### Pas 1: Definició (concepte)
```yaml
# schemas/concepts/report_variables.yaml
client_name:
  source_priority:
    user: 10, planol_vision: 20, pressupost_pdf: 30,
    dades_camp_excel: 35, groq_llm: 42, content_email: 43
```

### Pas 2: Extracció (FileMiner)
FileMiner recorre documents. Troba "CLIENT" a DADES CAMP xlsx:
```
Signal(label="CLIENT", value="ARQUITECCTURA BOSCH NOVELL",
       concept_id="client_name", source_type="dades_camp_excel",
       priority=35, confidence=0.90)
```
Troba "A/A" a Pressupost:
```
Signal(label="A/A", value="ARQUITECTURA BOSCH NOVELL -Jordi Bosch",
       concept_id="client_name", source_type="pressupost_pdf",
       priority=30, confidence=0.80)
```
Troba al PDF V0 (informe anterior):
```
Signal(label="CLIENT", value="RAMON MITJANA S.L.",
       concept_id="client_name", source_type="content_pdf",
       priority=45, confidence=0.80)
```

### Pas 3: Competició
```
Ordenats per (priority ASC, confidence DESC):
  #1 pri=30: "ARQUITECTURA BOSCH NOVELL" (pressupost)  ← GUANYA
  #2 pri=35: "ARQUITECCTURA BOSCH NOVELL" (dades camp)
  #3 pri=45: "RAMON MITJANA S.L." (PDF V0)              ← Eva espera aquest
```

### Pas 4: Merge
`_merge_prefills()` agafa el guanyador de `auto_extract.prefills["client_name"]`.
Vision (planol) no extreu client_name per Bell-Lloc.
Resultat final: "ARQUITECCTURA BOSCH NOVELL"

### Pas 5: Comparació
```
Eva: "RAMON MITJANA S.L."
Pipeline: "ARQUITECCTURA BOSCH NOVELL"
→ MISMATCH
```

### Diagnosi
El valor CORRECTE existeix al signal #3 (PDF V0, priority 45), però perd contra el pressupost (priority 30). El problema NO és que no trobem la dada — és que la **prioritat** afavoreix una font que conté l'ARQUITECTE, no el PROMOTOR.

---

## 8. Mapa de Variables per Fase

Quina fase genera cada variable:

| Variable | Fase | Font | Tipus |
|----------|------|------|-------|
| street_address | 0.3 FileMiner | Documents diversos | Pattern matching |
| municipality | 0.3 FileMiner | comanda_lab, dades_camp | Pattern matching |
| client_name | 0.3 FileMiner | pressupost, dades_camp | Pattern matching |
| architect_name | 0.3/0.4 | FileMiner + Groq LLM | Pattern + LLM |
| building_type | 0.3/Vision | FileMiner + plànol vision | Pattern + Vision |
| expedient | 0.3/0.4 | FileMiner + Groq | Pattern + LLM |
| num_floors | Vision | planol_extracted.json | Vision |
| superficie_parcela | Vision | planol_extracted.json | Vision |
| superficie_construida | Vision | planol_extracted.json | Vision |
| architect_company | Vision | planol_extracted.json | Vision |
| field_work_dates_text | 1.1 | DPSH/Lab PDF regex | Pattern matching |
| sulfate_mg_kg | 2.0 | Lab PDF via PyMuPDF | Pattern matching |
| adjacent_N/S/E/W | 3.3 | Cadastre API | HTTP API |
| cota_referencia | 3.1/Vision | ICGC MDT / sondeig | API + Vision |
| icgc_unit_* | 3.0 | ICGC WMS | HTTP API |
| utm_x, utm_y | 2.5 | COORDENADES.txt / geocode | File + API |
| qa_value | Merge | Terzaghi calculator | Càlcul |
| settlement | Merge | Schmertmann calculator | Càlcul |
| k30_value | Merge | E/75 o E/60 | Càlcul |
| site_description | Merge | Template genèric | Template |
| cte_edificacio | — | No implementat | — |
| seismic_ab_text | — | No implementat | — |
| radon_zone | — | No implementat | — |
| spt_* | — | sondeig_extracted.json existeix però no mapejat | — |
| sulfate_classification | — | Derivable de sulfate_mg_kg, no implementat | — |
| lab_* | — | Report generator (Fase 3), no al diagnostic | — |

---

## 9. Limitacions Actuals del Sistema

### 9.1 Prioritats globals vs per-concepte

El YAML defineix prioritats per-concepte, però `competition.py` usa `SOURCE_PRIORITY` global. Això significa que `pressupost_pdf` guanya per a `client_name` (priority 30) encara que el pressupost conté l'ARQUITECTE, no el PROMOTOR.

### 9.2 No hi ha logging estructurat

No existeix un log que digui: "Per a client_name, vaig trobar 5 signals, el #1 va guanyar perquè priority 30 < 35". El diagnostic_trace.py reconstrueix això a posteriori, però no es registra durant l'execució.

### 9.3 Variables calculades sense traçabilitat d'inputs

`qa_value = 1.36` — però amb quins inputs? Nb=?, B=?, Df=?, cohesion=? No es registren els inputs del càlcul, només el resultat.

### 9.4 Vision sense traçabilitat al merge

Si vision extreu `num_floors = "Pb+1Pp"` però el merge tria un altre valor, no hi ha log que expliqui per què.

### 9.5 Fases condicionals silencioses

Si Fase 3 es salta (per falta d'UTM), els adjacents poden ser buits o de cache, i no hi ha indicador clar al diagnostic.

### 9.6 Variables NOT_EXTRACTED: 65% del total

182 de 281 comparacions són NOT_EXTRACTED. Moltes d'aquestes:
- Es generen a la Fase 3 del report_generator (no al diagnostic)
- Necessiten lookups no implementats (CTE, sísmic, radó)
- Necessiten mapping de vision JSONs al prefill (SPT, lab details)
- Són narratives que Eva escriu manualment

---

## 10. Glossari

| Terme | Significat |
|-------|-----------|
| **Signal** | Una dada extreta d'un document: label + valor + font + prioritat + confiança |
| **Concepte** | Una variable semàntica de l'informe (53 definides) amb prioritats de font |
| **Format** | Com trobar conceptes dins un tipus de document (8 schemas sistema) |
| **concept_id** | Identificador únic de variable (= maps_to en el codi actual) |
| **source_type** | Tipus de font: dades_camp_excel, pressupost_pdf, planol_vision, groq_llm... |
| **Competició** | Quan múltiples signals donen valor per al mateix concepte, guanya el de menor prioritat |
| **Prefill** | Valor final per a un camp del wizard, després de competició + merge |
| **NOT_EXTRACTED** | Eva té valor, el pipeline no (o el diagnostic no l'exposa) |
| **MISMATCH** | Ambdós tenen valor, però són diferents |
| **CLOSE** | Gairebé iguals (substring, ≤15% numèric, o diferència menor de format) |

---

## 11. Alineació amb el Patró Concepte-Format (PATTERN-SEPARAR-CONCEPTE-DE-FORMAT.md)

El document `docs/PATTERN-SEPARAR-CONCEPTE-DE-FORMAT.md` descriu la **visió arquitectònica** del sistema. Aquí comparem què es va implementar vs què queda pendent:

### 11.1 Què s'ha implementat

| Element del patró | Estat | Detalls |
|-------------------|-------|---------|
| Schema de conceptes (YAML) | **Implementat** | 53 conceptes a `schemas/concepts/report_variables.yaml` |
| Prioritats per-concepte | **Definit, NO usat** | El YAML les té, però `competition.py` usa globals |
| Format schemas (YAML) | **Implementat** | 8 formats sistema a `schemas/formats/` |
| label_mappings als formats | **Implementat** | Etiquetes mapegen a concept_ids |
| concept_id als Signals | **Implementat** | `concept_id = maps_to` a cada Signal |
| Pont backward-compat | **Implementat** | `label_map.py` carrega des de YAML, 71 línies |
| Format Learning | **Implementat** | Detecció <60%, banner ambar, auto-save YAML |
| Tests de regressió | **Implementat** | 197 tests, snapshots de 4 projectes |

### 11.2 Què falta per completar el patró

| Element del patró | Estat | Impacte |
|-------------------|-------|---------|
| **Prioritats per-concepte a la competició** | NO implementat | `competition.py` usa `SOURCE_PRIORITY` global. Les prioritats per-concepte del YAML s'ignoren. Això és la causa principal del problema client_name (pressupost guanya sobre informe_v0 per a TOTES les variables) |
| **Dependències entre conceptes** | NO implementat | El patró proposa `dependències: [Nb, granulometria]` per a phi. No existeix al YAML actual ni al codi |
| **Motor de càlculs connectat a conceptes** | NO implementat | Terzaghi/Schmertmann s'executen al merge, no estan registrats com a "calculadors" de concept_ids |
| **Semàfor per variable** | NO implementat | El patró proposa `semàfor: yellow` per variables que Eva sempre revisa. No existeix |
| **Camps calculable/càlcul** | NO implementat | El patró proposa `calculable: true, càlcul: {mètode, inputs, fórmula}`. No existeix al YAML |
| **Validació per concepte** | NO implementat | El patró proposa `validació: ha de contenir nom de carrer + número`. No existeix |
| **SmartScan → format_id** | Parcial | SmartScan identifica roles però no carrega format schemas específics durant extracció |

### 11.3 Impacte dels gaps

**El gap més crític:** Les prioritats per-concepte estan definides al YAML però no s'apliquen. Això significa que el sistema es comporta com si totes les variables tinguessin les mateixes prioritats de font. Per exemple:

- `client_name` al YAML: `planol_vision: 20, pressupost_pdf: 30, dades_camp_excel: 35`
- Però a la competició real: `pressupost_pdf` guanya amb priority=30 global per a QUALSEVOL variable que trobi

Si la competició usés les prioritats per-concepte, podríem definir:
```yaml
client_name:
  source_priority:
    acceptacio_docs: 15    # Documents ACCEPTACIO tenen el promotor real
    planol_vision: 20      # Plànol pot tenir "PROMOTOR" al caixetí
    informe_anterior: 25   # PDF V0 té el client correcte
    pressupost_pdf: 50     # Pressupost té l'arquitecte, NO el promotor
    dades_camp_excel: 50   # DADES CAMP té el contacte, NO el promotor
```

Això resoldria el 70% dels MISMATCH de client_name sense tocar cap codi d'extracció.

---

*Document de referència per al refinament iteratiu del pipeline. Actualitzar quan la lògica canviï.*
