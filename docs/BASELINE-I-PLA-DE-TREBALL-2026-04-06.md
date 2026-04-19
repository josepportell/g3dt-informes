# Baseline del Pipeline i Pla de Treball
**Data:** 2026-04-06
**Objectiu:** Document de referencia per al proces iteratiu de refinament format-per-format, variable-per-variable.

---

## 1. Baseline Global

| Metrica | Valor |
|---------|-------|
| **Projectes analitzats** | 7 |
| **Variables comparades (Eva vs Pipeline)** | 281 (total var-comparisons) |
| **Variables amb valor del pipeline** | 99 (35%) |
| **Variables sense valor** | 182 (65%) |
| **MATCH** | 17 |
| **CLOSE** | 12 |
| **MISMATCH** | 70 |
| **Match+Close rate (dels 99 comparats)** | **29.3%** |

### Per projecte

| Projecte | MATCH | CLOSE | MISMATCH | NOT_EXT | Total | Rate |
|----------|-------|-------|----------|---------|-------|------|
| 4001612 BELL-LLOC | 5 | 4 | 9 | 26 | 44 | **50.0%** |
| 3001621 CASTELLAR | 3 | 0 | 11 | 29 | 43 | **21.4%** |
| 3001631 RUBI | 4 | 1 | 9 | 25 | 39 | **35.7%** |
| 4001607 LINYOLA | 2 | 1 | 11 | 25 | 39 | **21.4%** |
| 4001670 ALCOLETGE | 3 | 1 | 10 | 24 | 38 | **28.6%** |
| 4001671 VILANOVA | 0 | 3 | 8 | 29 | 40 | **27.3%** |
| 4001679 ANCILES | 0 | 2 | 12 | 24 | 38 | **14.3%** |

**Notes:**
- Bell-Lloc es el millor (50%) perque te vision completa (planol+sondeig+dpsh) i el projecte mes instrumentat.
- Anciles es el pitjor (14.3%) perque es un projecte aragones (castella, no catala), amb estructura diferent.
- La visio (planol/sondeig/dpsh) esta cached per projectes on ja s'ha executat. No tots tenen les 3 visions.

---

## 2. Matriu Variable per Variable

### 2.1 Variables que FUNCIONEN (MATCH o CLOSE consistentment)

| Variable | M | C | X | ND | Font principal | Notes |
|----------|---|---|---|----|----|------|
| sulfate_mg_kg | 4 | 0 | 0 | 1 | Lab PDF (PyMuPDF) | Funciona be. 1 ND perque el projecte no te lab. |
| municipality | 2 | 4 | 1 | 0 | FileMiner: comanda_laboratori.xls | 6/7 OK. Nomes falla format (RUBI vs "Rubi (Barcelona)") |
| expedient | 3 | 3 | 1 | 0 | Groq LLM / FileMiner | 6/7 OK. Falla a Linyola (confon ref interna "13/52/04") |
| num_floors | 2 | 0 | 1 | 4 | Planol vision | Funciona quan vision s'executa. 4 ND = vision no ha extret. |
| superficie_parcela_m2 | 1 | 0 | 1 | 5 | Planol vision | Funciona quan vision s'executa. 5 ND = sense vision. |
| architect_company | 1 | 0 | 0 | 1 | Planol vision | Nomes 2 projectes tenen valor Eva. Funciona. |
| k30_value | 1 | 0 | 1 | 0 | Calcul Winkler | Rubi=6.0 OK, Castellar=8.3 vs Eva full sentence |
| field_work_dates_text | 2 | 0 | 3 | 2 | DPSH/Lab PDF | MATCH quan dates coincideixen. MISMATCH: format ("1 d'octubre" vs "1 i 6 d'octubre") o espai extra |

### 2.2 Variables MISMATCH sistematic (les que necessiten treball)

#### GRUP A: Adjacents (28 MISMATCH de 28 comparats)
**El problema mes gran en volum.**

| Variable | M | C | X | ND | Actual | Eva espera |
|----------|---|---|---|----|----|------|
| adjacent_south | 0 | 0 | 7 | 0 | "parcel·la buida" | "Per la part sud amb el Carrer Antoni Bellet." |
| adjacent_west | 0 | 0 | 7 | 0 | "parcel·la amb construccio" | "I finalment, per la part oest, amb una parcel·la amb una construccio." |
| adjacent_east | 0 | 1 | 6 | 0 | "Carrer Mestre Ramon Ortiz" | "Per la part est amb el Carrer Mestre Ramon Ortiz." |
| adjacent_north | 0 | 1 | 6 | 0 | "parcel·la buida" | "Per la part nord amb una parcel·la buida." |

**Analisi:** El pipeline extreu la DADA correcta del Cadastre (carrer, parcel·la buida/construida). Pero Eva escriu una FRASE completa amb un format especific: "Per la part {direccio} amb {descripció}.". El pipeline retorna la dada crua, no la frase.

**Solucio:** Generar la frase a partir de la dada crua. Es un problema de FORMAT DE SORTIDA, no d'EXTRACCIO. El valor cru del Cadastre es correcte en la majoria de casos.

**Complexitat:** BAIXA — es un template de frase aplicat sobre dades que ja tenim.

---

#### GRUP B: Calculs Geotecnics (14+ MISMATCH)

| Variable | M | C | X | ND | Pipeline | Eva |
|----------|---|---|---|----|----|------|
| qa_value | 0 | 0 | 7 | 0 | 0.42 a 5.00 | 2.0 a 3.50 |
| settlement | 0 | 0 | 7 | 0 | 0.89 a 4.66 | 1.20 a 1.50 (o frase completa) |

**Detall per projecte:**

| Projecte | qa Pipeline | qa Eva | settlement Pipeline | settlement Eva |
|----------|------------|--------|-------------------|----------------|
| Bell-Lloc | 1.36 | 3.0 | 0.92 | 1.20 |
| Castellar | 5.00 | 3.0 | 4.66 | ? (frase) |
| Rubi | 1.88 | 3.50 | 0.93 | 1.50 |
| Linyola | 1.08 | 3.0 | 0.95 | ? (frase) |
| Alcoletge | 0.42 | 3.50 | 0.89 | ? (frase) |
| Vilanova | 0.73 | 2.50 | 0.90 | ? (frase) |
| Anciles | 0.79 | 2.0 | 0.91 | ? (frase) |

**Analisi:** El calculador de Terzaghi s'executa pero amb valors per defecte (B=1.0, Df=0.8). Eva utilitza valors reals del projecte. A mes, Eva aplica un "cap" professional (3.0 sol granular, 4.5 roca) que el calculador potser no esta aplicant correctament en tots els casos.

**Solucio:** Dos problemes separats:
1. **Inputs:** B i Df provenen del wizard (Eva els confirma). En mode diagnostic no hi ha wizard → usa defaults. Necessitem carregar user_data.json si existeix.
2. **Logica del cap:** Ja esta implementat al calculador, pero pot fallar si `cohesion` no es detecta correctament (cohesion >= 0.5 → roca → cap 5.0).

**Complexitat:** MITJANA — requereix investigar el calculador amb dades reals.

---

#### GRUP C: Client/Promotor (5 MISMATCH + 2 ND)

| Projecte | Pipeline | Eva | Font pipeline |
|----------|----------|-----|------|
| Bell-Lloc | ARQUITECCTURA BOSCH NOVELL | RAMON MITJANA S.L | DADES CAMP.xlsx |
| Castellar | GRUP ALMA | WOOD COMFORT PROMOCIONS SLU | Pressupost.msg |
| Linyola | BUNYESC ARQUITECCTURA EFICIENT | SRA. SILVIA EROLES BALAGUERO | DADES CAMP.xlsx |
| Alcoletge | ALBERT SANS BONVEHI tel. 675... | SR. ALBERT SANS BONVEHI | Email |
| Anciles | MARIA ALBA BARRAU CASTAN 6... | SRA. ALBA MARIA BARRAU CASTAN | DADES CAMP.xlsx |

**Analisi:** Patrons clars:
- DADES PER ANAR A CAMP.xlsx te el CONTACTE (arquitecte o enginyer), no el PROMOTOR/CLIENT
- Pressupost.msg te "A/A:" que es l'arquitecte, no el client
- El PROMOTOR real esta a:
  - ACCEPTACIO/ (documents d'acceptacio)
  - El propi informe anterior (PDF V0)
  - De vegades al planol (caixeti "PROMOTOR:")
- En el cas d'Alcoletge, el nom es correcte pero amb telefon afegit

**Solucio:**
1. Canviar prioritat: `dades_camp_excel` no hauria de guanyar per `client_name` (dona contacte, no promotor)
2. Crear format `acceptacio_v1.yaml` que extregui de documents ACCEPTACIO/
3. Vision planol: forcar extraccion de "PROMOTOR" del caixeti

**Complexitat:** ALTA — necessita nous formats + prioritats + potser extracció de documents nous.

---

#### GRUP D: Tipus d'Edificacio (4 MISMATCH + 3 CLOSE)

| Projecte | Pipeline | Eva | Status |
|----------|----------|-----|--------|
| Bell-Lloc | habitatge unifamiliar aillat | un habitatge unifamiliar | MISMATCH |
| Castellar | habitatge unifamiliar aillat | 3 habitatges unifamiliars adossats | MISMATCH |
| Rubi | habitatge unifamiliar aillat | un habitatge unifamiliar aillat | CLOSE |
| Linyola | habitatge unifamiliar | un nou habitatge unifamiliar | CLOSE |
| Alcoletge | habitatge unifamiliar | l'ampliacio d'un edifici existent | MISMATCH |
| Vilanova | vivienda unifamiliar | una vivienda unifamiliar aillada | CLOSE |
| Anciles | viviendas adosadas | 7 viviendas unifamiliares adosadas | MISMATCH |

**Analisi:**
- Vision (planol) extreu el TIPUS pero no el NOMBRE ni articles/preposicions
- Eva escriu "un habitatge", "3 habitatges", "l'ampliacio de..." — una frase contextualitzada
- Alcoletge es un cas especial: no es construccio nova, es ampliacio

**Solucio:**
1. Vision ja extreu el tipus correcte en la majoria de casos
2. El que falta: quantitat (1, 3, 7), articles ("un", "una"), cas especial (ampliacio/reforma)
3. La comanda_laboratori.xls te "CONSTR 3 HAB UNIF" que SI te el numero → crear format que extregui quantitat
4. Text comparison hauria de ser mes flexible (ignorar articles, normalitzar singular/plural)

**Complexitat:** MITJANA

---

#### GRUP E: Nom Arquitecte (5 MISMATCH + 1 MATCH)

| Projecte | Pipeline | Eva |
|----------|----------|-----|
| Bell-Lloc | Jordi Bosch Novell | JORDI BOSCH NOVELL | MATCH (Groq) |
| Rubi | SR. | JOANA MARTINEZ | MISMATCH |
| Linyola | SR. | SILVIA EROLES BALAGUERO | MISMATCH |
| Alcoletge | David Graus Robinet | ALBERT SANS BONVEHI | MISMATCH |
| Vilanova | jordi carner | JUAN JOSE TORRES POVEDANO | MISMATCH |
| Anciles | ANDRES AMAT y ENRIQUE M. GARDETA | ALBA MARIA BARRAU CASTAN | MISMATCH |

**Analisi:** El pipeline extreu algun nom de persona dels documents, pero sovint no es l'arquitecte correcte. El problema es que:
- Groq extreu qualsevol nom que trobi
- L'arquitecte real no sempre apareix als documents de G3 (apareix al planol)
- A Alcoletge/Anciles extreu l'arquitecte del planol pero Eva vol l'arquitecte del PROJECTE (un altre)

**Solucio:** Planol vision hauria de ser la font prioritaria per architect_name.

**Complexitat:** MITJANA — millorar prompt de vision planol.

---

#### GRUP F: Descripció del solar / site_description (7 MISMATCH)

Tots els projectes: el pipeline genera "El terreny es presenta antropitzat..." pero Eva escriu una descripcio especifica del que va veure al camp.

**Analisi:** Aquesta variable es NARRATIVA — Eva l'escriu manualment basant-se en la seva visita de camp. El pipeline genera text generic a partir d'un template.

**Solucio:** Acceptar que aquesta variable sera sempre un "default" que Eva modifica al wizard. No es realista que el pipeline l'extregui automaticament. Pero podria millorar-se amb:
- Fotos del camp (futur: vision de fotos)
- Paraules clau de la fitxa de camp ("solar pla", "solar antropitzat", "desnivell...")

**Complexitat:** ALTA (futur), NO PRIORITARI ara.

---

### 2.3 Variables NOT_EXTRACTED (182 instancies)

Agrupades per categoria:

#### Narrative/Template (15 vars x ~7 proj = ~105 instancies)
Variables que Eva compon manualment o que surten de la generacio de seccions del report:
- `access_street`, `location_sentence`, `site_condition`, `building_structure_desc`
- `lab_field_company`, `lab_field_description`, `lab_testing_company`, `lab_testing_description`
- `lab_depth`, `lab_location`, `lab_sample_id`, `lab_tests_text`
- `num_dpsh_tests`, `table_dpsh_range`

**Accio:** Moltes d'aquestes es generen en la Fase 3 (report_generator) que el diagnostic NO executa encara. Algunes necessiten extracció de nous documents.

#### Calculades (4 vars x ~7 proj = ~28 instancies)
- `cte_edificacio`, `cte_sol` — CTE classifier (no s'executa al diagnostic)
- `seismic_ab_text` — Lookup per municipi (no implementat)
- `radon_zone` — Lookup per municipi (no implementat)

**Accio:** `cte_*` requereix integrar el CTE classifier al diagnostic. `seismic` i `radon` necessiten taula de lookup per municipi.

#### SPT/Sondeig (5 vars x ~4 proj = ~20 instancies)
- `spt_depth_range`, `spt_lithology`, `spt_location`, `spt_n30`, `spt_test_id`

**Accio:** Dades presents a sondeig_extracted.json (vision). Necessiten mapping al comparison.

#### Sulfats i Lab (3 vars x ~7 proj = ~21 instancies)
- `sulfate_baumann`, `sulfate_classification`, `sulfate_level_name`

**Accio:** `sulfate_mg_kg` ja s'extreu. `classification` i `baumann` es deriven del valor numeric. `level_name` es template.

#### Superficie (2 vars)
- `superficie_construida_m2` — 5 ND + 1 MISMATCH. Necessita vision planol.
- `superficie_parcela_m2` — 5 ND + 1 MATCH. Funciona amb vision.

---

## 3. Analisi dels Formats Actuals

### 3.1 Formats existents (8)

| Format | Fitxers que processa | Variables clau | Funciona? |
|--------|---------------------|----------------|-----------|
| dades_camp_excel_v1 | DADES PER ANAR A CAMP.xlsx | street_address, client_name, contact | Si, pero dona contacte no promotor |
| dpsh_vision_v1 | PENETROS.pdf (vision) | N20, refus | OK (validacio) |
| email_content_v1 | *.msg | client_name, building_type | Confon client amb destinatari |
| generic_document_v1 | Catch-all | varis | Massa generic, poc precis |
| groq_extraction_v1 | Targets per Groq | expedient, building_type | Variable, depent del LLM |
| planol_vision_v1 | A.01.pdf (vision) | architect, building_type, superficie | Funciona per dades del planol |
| pressupost_pdf_v1 | Pressupost*.pdf/msg | client_name, building_type | Confon client amb arquitecte |
| sondeig_vision_v1 | SONDEIG.pdf (vision) | capes, SPT | OK per dades del sondeig |

### 3.2 Formats que FALTEN

| Format proposat | Fitxer | Variables que podria extreure | Impacte |
|-----------------|--------|------------------------------|---------|
| `acceptacio_v1` | ACCEPTACIO/DADES CLIENT.txt, *.docx | client_name (PROMOTOR), client_nif, client_email | **ALT** — resol client_name per 5/7 proj |
| `comanda_lab_v1` | comanda_laboratori_*.xls | municipality, building_type (abreujat), expedient | MITJA — ja funciona amb dades_camp_excel |
| `dades_camp_v2` | DADES PER ANAR A CAMP.xlsx (revisio) | Separar CONTACTE de CLIENT | ALT — evita confondre contacte/promotor |
| `informe_anterior_v1` | PDF V0/*_informe_v0.pdf | client_name, tots els valors anteriors | ALT — te TOTS els valors correctes |

---

## 4. Pla de Treball

### Filosofia
Treballar variable per variable, projecte per projecte:
1. Escollir una variable amb MISMATCH
2. Analitzar en UN projecte: on es la dada correcta? Quin document? Quin camp/cel·la?
3. Crear o modificar el format schema YAML per extreure-la
4. Verificar que funciona per a aquell projecte
5. Provar amb un SEGON projecte — si funciona, be; si no, crear un altre format
6. Repetir fins que la variable estigui coberta per tots els projectes

### Ordre de treball (per impacte descendent)

#### Bloc 1: Adjacents — Format de sortida (28 MISMATCH → 0)
**Temps estimat:** 1-2 hores
**Que cal fer:** No es un problema d'extracció, es de formatat. Les dades del Cadastre son correctes. Cal generar la frase "Per la part {dir} amb {desc}." a `_generate_template_prefills_from_merged()`.
**Verificacio:** Re-executar diagnostic, adjacents han de passar a MATCH o CLOSE.

#### Bloc 2: Calculs Qa/Settlement (14 MISMATCH)
**Temps estimat:** 2-3 hores
**Que cal fer:**
1. Investigar perque qa_value divergeix tant (1.36 vs 3.0)
2. Carregar user_data.json al diagnostic per usar B/Df reals
3. Verificar que el cap professional (3.0/4.5) s'aplica correctament
**Verificacio:** qa_value dins 10% d'Eva per projectes amb user_data.

#### Bloc 3: Client/Promotor (5 MISMATCH + 2 ND)
**Temps estimat:** 3-4 hores
**Que cal fer:**
1. Crear format `acceptacio_v1.yaml` per documents ACCEPTACIO/
2. Baixar prioritat de `dades_camp_excel` per a `client_name`
3. Millorar extracció de planol vision per camp "PROMOTOR"
4. Verificar projecte per projecte
**Verificacio:** client_name MATCH per 5/7 projectes.

#### Bloc 4: Building Type normalitzacio (4 MISMATCH)
**Temps estimat:** 1-2 hores
**Que cal fer:**
1. Afegir quantitat des de comanda_lab ("CONSTR 3 HAB UNIF" → 3)
2. Millorar normalitzacio de text (ignorar articles "un/una/l'")
3. Casos especials (ampliacio, reforma)
**Verificacio:** building_type CLOSE o MATCH per 6/7 projectes.

#### Bloc 5: Architect Name (5 MISMATCH)
**Temps estimat:** 2-3 hores
**Que cal fer:**
1. Millorar vision prompt per planol: distingir PERSONA vs EMPRESA
2. Baixar prioritat de groq_llm per architect_name
3. Noves fonts: ACCEPTACIO pot tenir nom arquitecte
**Verificacio:** architect_name MATCH per 4/7 projectes.

#### Bloc 6: Variables calculades/lookup (CTE, seismic, radon)
**Temps estimat:** 2-3 hores
**Que cal fer:**
1. Integrar CTE classifier al full pipeline
2. Crear taula seismic per municipi
3. Crear taula radon per zona
**Verificacio:** cte_*, seismic, radon NOT_EXTRACTED → MATCH.

#### Bloc 7: Variables derivades de sondeig/lab (SPT, sulfats)
**Temps estimat:** 1-2 hores
**Que cal fer:**
1. Mapejar sondeig_extracted.json → spt_* variables al comparison
2. Derivar sulfate_classification del valor numeric
3. Generar sulfate_level_name des del template
**Verificacio:** spt_*, sulfate_classification passen a MATCH.

### Objectius per fita

| Fita | Accions | Match+Close esperat |
|------|---------|-------------------|
| Despres Bloc 1 | Adjacents formatats | ~43% (+28 CLOSE/MATCH de 99) |
| Despres Bloc 2 | Qa/Settlement corregits | ~57% (+14 MATCH) |
| Despres Bloc 3 | Client fixat | ~62% (+5 MATCH) |
| Despres Bloc 4 | Building type normalitzat | ~66% (+4 CLOSE) |
| Despres Bloc 5 | Architect name fixat | ~71% (+5 MATCH) |
| Despres Blocs 6-7 | Lookups + derivats | ~80%+ |

---

## 5. Metode iteratiu per formats

Per a cada variable d'un bloc:

```
1. ANALITZAR: Obrir el primer projecte (Bell-Lloc). Trobar el fitxer
   que conte la dada correcta. Anotar: quin fitxer, quina pestanya/pagina,
   quina cel·la/posicio, quin text l'envolta.

2. DEFINIR FORMAT: Escriure el format YAML amb label_mappings que
   descriguin com trobar la dada:
   - labels: ["PROMOTOR", "CLIENT", "PROPIETARI"]
     concept_id: client_name
     confidence: 0.95

3. TESTAR: Re-executar diagnostic per aquest projecte.
   ¿MATCH? → Passar al projecte 2.
   ¿MISMATCH? → Ajustar format.

4. EXPANDIR: Provar amb projecte 2 (Castellar).
   ¿MATCH? → El format es universal.
   ¿MISMATCH? → Analitzar diferencies.
     - Si el fitxer te la mateixa estructura pero etiquetes diferents:
       ampliar labels[] del format existent.
     - Si el fitxer te estructura completament diferent:
       crear un nou format (acceptacio_v2.yaml per exemple).

5. REPETIR fins a cobrir tots 7 projectes.
```

---

## 6. Referencia: Sortida completa del diagnostic

La sortida completa del diagnostic (511 linies) es a:
```bash
.venv/bin/python scripts/diagnostic_trace.py --all 2>&1 | grep -v "UserWarning\|warn(msg)"
```

Per re-executar un sol projecte amb detall:
```bash
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --all
```

Per filtrar una variable especifica:
```bash
.venv/bin/python scripts/diagnostic_trace.py --concept client_name --all
```
