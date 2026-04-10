# Traça completa: `building_type` a través del pipeline

**Data:** 2026-04-10
**Projectes traçats:** Bell-Lloc (4001612, CLOSE), Linyola (4001607, MISMATCH)
**Objectiu:** Seguir una dada des del fitxer original fins al wizard, validant cada etapa

---

## 0. Troballes sistèmiques (abans d'entrar a la variable)

### 0.1 LLM Judge existeix pero el diagnostic no l'usa

El `compare_benchmarks.py` (lines 308-417) implementa un `_llm_judge_text()` que:
- Usa Claude Haiku per avaluar similitud semàntica 1-5
- Té cache persistent a `_llm_judge_cache.json`
- Converteix score >=5 → MATCH, >=3 → CLOSE, <3 → MISMATCH
- Coneix vocabulari de domini (solar buit = parcella buida, etc.)

**PROBLEMA:** `diagnostic_trace.py` usa `compare_text()` (string matching pur), **no** el LLM judge.
Això significa que el diagnostic classifica com MISMATCH coses que semànticament són CLOSE o MATCH.

**Impacte estimat:** Les 129 MISMATCH del run actual inclouen un nombre desconegut de falsos
positius. Variables com `building_type` ("un habitatge unifamiliar aïllat" vs "un habitatge
unifamiliar") i totes les narratives (`site_description`, `building_structure_desc`,
`location_sentence`) probablement millorarien amb LLM judge.

**Acció:** Integrar `_llm_judge_text()` al `diagnostic_trace.py` per a variables Tier B (text).

### 0.2 Mapping concepte-format: 74% dels conceptes NO tenen mapping

```
Total conceptes definits:           65
Conceptes AMB mapping de format:    17  (26%)
Conceptes SENSE cap mapping:        48  (74%)
```

**Això és un problema greu?** Depèn. Revisem:

Els 48 conceptes sense mapping es divideixen en:

| Categoria | Count | Mapping necessari? |
|---|---|---|
| Computed (qa, settlement, k30, structure_desc, num_dpsh_tests, table_dpsh_range) | 6 | NO — es calculen, no s'extreuen de text |
| API/HTTP (ICGC, cadastre, geocode, UTM) | 13 | NO — venen d'APIs, no de fitxers |
| User-only (geomech_*, foundation_depth, Es_settlement, site_description, access_description) | 10 | NO — Eva els omple manualment |
| Lab (lab_depth, lab_field_*, lab_testing_*, lab_tests_text, lab_sample_id, lab_location) | 8 | **SÍ** — s'haurien d'extreure dels informes GTL |
| Adjacents (adjacent_N/S/E/W) | 4 | **SÍ** — venen de cadastre + planol + groq |
| Building (has_basement, has_retaining, building_height, superficie_cadastral) | 4 | **SÍ** — s'haurien d'extreure del planol |
| Parcel (parcel_shape, site_position, is_anthropized, is_sloped, is_urban) | 5 | Parcial — alguns venen d'API, altres de vision |
| Narrative (location_sentence) | 1 | NO — ve de llm_synthesis |
| Field work (cota_referencia, field_work_dates, field_work_dates_text) | 3 | **SÍ** — dades_camp_excel o vision |

**Conceptes que NECESSITEN mapping i no el tenen: ~19 (29%)**

Dels 19 que necessiten mapping, els més impactants (REQUIRED o alta freqüència de MISMATCH):
1. `adjacent_*` (4 conceptes, REQUIRED, 5-6 MISMATCH cadascun)
2. `lab_*` (8 conceptes, 4 MISMATCH cadascun)
3. `building_height_m`, `has_basement`, `has_retaining_walls` (building group)
4. `field_work_dates*`, `cota_referencia` (field work group)

**Acció:** Crear format schemas per als grups `lab` (format GTL) i `building` (completar planol).
Els adjacents venen principalment d'API (cadastre), no de format mapping.

### 0.3 Format schemas existents: cobertura per fitxer

| Schema | Mappings | Cobertura |
|---|---|---|
| generic_document_v1.yaml | 17 | El més complet (catch-all) |
| dades_camp_excel_v1.yaml | 15 | Dades de camp Excel |
| planol_vision_v1.yaml | 9 | Planol (hauria de tenir-ne més) |
| groq_extraction_v1.yaml | 7 | Extracció Groq LLM |
| pressupost_pdf_v1.yaml | 5 | Pressupost |
| email_content_v1.yaml | 4 | Contingut email |
| learned_architect_plan*.yaml | 5 | Apres (auto-generat) |
| learned_dpsh_excel*.yaml | 2 | Apres (auto-generat) |
| dpsh_vision_v1.yaml | **0** | Buit! |
| sondeig_vision_v1.yaml | **0** | Buit! |

**PROBLEMA:** `dpsh_vision_v1.yaml` i `sondeig_vision_v1.yaml` existeixen com a fitxers
però tenen **0 mappings**. Això vol dir que les dades extretes per vision de DPSH i sondeig
no passen pel sistema concepte-format — van per una via paral·lela (directa a JSON).

**Acció:** Decidir si els vision schemas haurien de tenir mappings (probablement no —
la visió extreu directament amb prompt dedicat, no etiquetes), o documentar explícitament
que vision bypassa el sistema de formats.

---

## 1. Fitxers originals — Existeix la dada?

### Bell-Lloc
| Font | Dada present? | Valor | Qualitat |
|---|---|---|---|
| A.01.pdf (plànol) | SÍ, al caixetí | "HABITATGE UNIFAMILIAR" | Bona — és la font primària |
| comanda laboratori .xls | SÍ, genèric | "CONSTR HABITATGE" | Massa genèric |
| Pressupost C1 .msg | SÍ, però barrejat | "Bell-lloc - CL MESTRE RAMO..." | No és building_type, és adreça+context |
| PDF V0 (informe anterior) | SÍ, però és l'informe | "Estudi geològic/geotècnic..." | No és building_type, és el títol del projecte |

### Linyola
| Font | Dada present? | Valor | Qualitat |
|---|---|---|---|
| Plànol | ? | No sabem — el fitxer és "Punts de Sondeig_Silvia_Jaume.pdf" | SmartScan pot haver classificat malament |
| comanda laboratori .xls | SÍ, genèric | "CONSTR HABITATGE" | Massa genèric |

### Diagnòstic etapa 1

**Coverage del plànol: 20% a Bell-Lloc, 0% a Linyola.**

Això NO és acceptable. El plànol és la font primària per `building_type` (prioritat 20).
Format learning detecta 20% de cobertura → vol dir que l'extracció vision del plànol
extreu molt poc del que hauria.

**Per què passa?** Possibles causes a investigar:
1. El prompt de vision per planol (`PLANOL_EXTRACTION_PROMPT`) no demana building_type?
2. El plànol s'extrau bé però les claus no mapegen al concepte? (normalitzador)
3. El format del plànol és inusual i el vision no el reconeix?
4. A Linyola, "Punts de Sondeig_Silvia_Jaume.pdf" no és un plànol real — SmartScan error?

**Acció immediata:** Revisar `planol_extracted.json` de Bell-Lloc per veure què extreu realment el vision,
i comparar amb el que hi ha al PDF.

---

## 2. FileMiner — Senyals extretes

### Bell-Lloc (6 senyals)
| # | Font | Mètode | Valor | Pri | Conf | Match Eva? |
|---|---|---|---|---|---|---|
| 1 | Pressupost C1 | label_value | "Bell-lloc - CL MESTRE RAMO..." | 30 | 0.80 | MISMATCH |
| 2 | RE: Pressupost C1 | label_value | "Bell-lloc - CL MESTRE RAMO..." | 30 | 0.80 | MISMATCH |
| 3 | informe_v0.pdf | label_value | "Estudi geològic/geotècnic..." | 45 | 0.80 | MISMATCH |
| 4 | DPSH.pdf | label_value | "C7 MESTRE RAMON ORTIZ 15..." | 45 | 0.80 | MISMATCH |
| 5 | PORTADA_.pdf | label_value | "Estudi geològic/geotècnic..." | 45 | 0.80 | MISMATCH |
| 6 | comanda laboratori .xls | label_adjacent | "CONSTR HABITATGE" | 50 | 0.90 | MISMATCH |

### Linyola (1 senyal)
| # | Font | Mètode | Valor | Pri | Conf | Match Eva? |
|---|---|---|---|---|---|---|
| 1 | comanda laboratori .xls | label_adjacent | "CONSTR HABITATGE" | 50 | 0.90 | MISMATCH |

### Diagnòstic etapa 2

**Cap de les 7 senyals (6+1) coincideix amb Eva.** Per què?

1. **Senyals #1-2 (pressupost):** FileMiner extreu l'adreça completa del pressupost
   com a building_type. Això és un **error de regex**: l'etiqueta del pressupost
   que coincideix amb building_type labels ("OBRA") captura l'adreça del projecte,
   no el tipus d'obra.

2. **Senyals #3-5 (informe/portada):** Extreuen el títol del document
   ("Estudi geològic/geotècnic..."), no el building_type. Altre error de regex/etiqueta.

3. **Senyal #6 (comanda lab):** "CONSTR HABITATGE" és correcte parcialment
   (és construcció d'habitatge), però massa genèric. El mètode `label_adjacent`
   indica que no és un match directe sinó el valor adjacent a l'etiqueta — potser
   el regex agafa el camp proper però no el correcte.

4. **El valor real ("un habitatge unifamiliar") no existeix literalment a cap fitxer.**
   Eva sintetitza aquest text a partir del context del plànol i els documents.
   Per tant, o bé necessitem:
   - Millor extracció del plànol (que SÍ diu "HABITATGE UNIFAMILIAR")
   - LLM synthesis que transformi "CONSTR HABITATGE" → "un habitatge unifamiliar"

**El valor al plànol existeix** ("HABITATGE UNIFAMILIAR" al caixetí), però
no arriba com a senyal de FileMiner perquè el plànol és un PDF imatge (escanejat),
no text. FileMiner no pot extreure text de PDFs escanejats → depèn del vision.

---

## 3. ConceptScout — Mapa concepte-fitxer

`building_type` **no té entrada** a `concept_map.json` ni a Bell-Lloc ni a Linyola.

### Diagnòstic etapa 3

ConceptScout agrega senyals de FileMiner per concepte. Si cap senyal de FileMiner
mapeja correctament a `building_type` (que hem vist a l'etapa 2 que no), llavors
ConceptScout no pot crear l'entrada.

Pregunta: les 6 senyals de Bell-Lloc, **mapegen a `building_type` al concept_map?**
Si l'aggregator rep senyals amb `concept_id=building_type` però cap és bona,
hauria d'aparèixer al concept_map (amb contingut dolent, però aparèixer).
Si no apareix, és que les senyals no tenen `concept_id=building_type` assignat.

**Acció:** Verificar si les senyals de FileMiner per als pressupostos i informe_v0
realment es mapegen a `building_type` o a un altre concepte. Si es mapegen bé al
concepte però el valor és dolent, el problema és d'extracció. Si no es mapegen,
el problema és de format mapping.

---

## 4. Format Schema — Mapping etiqueta → concepte

Per a `building_type`, els schemas defineixen:
- **groq_extraction_v1.yaml:** labels = ["TIPUS EDIFICACIÓ", "TIPO EDIFICACIÓN", "OBRA"]
- **planol_vision_v1.yaml:** labels = ["TIPUS EDIFICACIÓ", "TIPO EDIFICACIÓN", "OBRA"]
- **generic_document_v1.yaml:** labels = ["TIPUS EDIFICACIÓ", "TIPO EDIFICACIÓN", "TIPUS D'OBRA", "TIPO DE OBRA", "OBRA"]
- **pressupost_pdf_v1.yaml:** labels = ["TIPUS EDIFICACIÓ", "TIPO EDIFICACIÓN", "OBRA"]
- **dades_camp_excel_v1.yaml:** labels = ["TIPUS EDIFICACIÓ", "TIPO EDIFICACIÓN", "TIPUS D'OBRA", "TIPO DE OBRA", "OBRA"]

### Diagnòstic etapa 4

L'etiqueta "OBRA" és massa àmplia. Al pressupost, "OBRA" fa referència al nom del projecte/adreça,
no al tipus d'edificació. Per això FileMiner captura "Bell-lloc - CL MESTRE RAMON ORTIZ..."
com a building_type — l'etiqueta "OBRA" al pressupost conté l'adreça.

**Problema concret:** El label "OBRA" en un pressupost vol dir "Descripció de l'obra" (adreça + localitat).
En un plànol vol dir "Tipus d'obra" (habitatge unifamiliar). Mateixa etiqueta, diferent significat
segons el format del document.

**Acció:** O bé:
- Eliminar "OBRA" de `pressupost_pdf_v1.yaml` (massa ambigua en pressupostos)
- O afegir un `context_filter` que requereixi que el valor contingui paraules tipus
  ("habitatge", "vivienda", "nau", "edifici") per validar que és realment un building_type

---

## 5. LLM Synthesis — Qui guanya?

El valor final ve de `llm_synthesis` (wizard_service.py lines ~700-900):
- Claude rep totes les fonts com a context
- Té 7 exemples d'Eva hardcoded al prompt (few-shot)
- Sintetitza: "un habitatge unifamiliar aïllat"

### Bell-Lloc
- Eva: "un habitatge unifamiliar"
- Pipeline: "un habitatge unifamiliar **aïllat**"
- Status: CLOSE (la paraula "aïllat" és afegida pel model sense evidència)

### Linyola
- Eva: "un **nou** habitatge unifamiliar"
- Pipeline: "un habitatge unifamiliar **aïllat**"
- Status: MISMATCH (falta "nou", sobra "aïllat")

### Diagnòstic etapa 5

L'LLM synthesis fa bé la feina de convertir "CONSTR HABITATGE" → "un habitatge unifamiliar",
però **afegeix qualificadors inventats** ("aïllat") i **no detecta qualificadors presents**
("nou" a Linyola).

**Per què "aïllat"?** Perquè el prompt conté l'exemple de Rubí: "un habitatge unifamiliar
aillat modular", i el model generalitza "aïllat" com a qualificador per defecte.

**Per què falta "nou"?** Perquè cap font envia el qualificador "nou" al prompt.
Eva el posa perquè sap del context (és construcció nova, no reforma), però el pipeline
no envia suficient context per deduir-ho.

**Accions:**
1. Afegir al prompt la instrucció: "NO afegeixis qualificadors que no surtin de les fonts"
2. El plànol de Bell-Lloc probablement diu "HABITATGE UNIFAMILIAR" (sense "aïllat") —
   si el vision l'extragués correctament, llm_synthesis tindria la font correcta
3. A Linyola, "nou" probablement surt del caixetí del plànol ("nou habitatge") —
   sense vision del plànol, el pipeline no ho pot saber

---

## 6. Comparació final — El diagnostic és just?

### Bell-Lloc: CLOSE (correcte semànticament)
"un habitatge unifamiliar aïllat" vs "un habitatge unifamiliar"
→ Un LLM judge donaria score 4-5 (mateixa essència, qualificador extra)
→ `compare_text()` diu CLOSE perquè hi ha un substring match parcial

### Linyola: MISMATCH (hauria de ser CLOSE)
"un habitatge unifamiliar aïllat" vs "un nou habitatge unifamiliar"
→ Un LLM judge donaria score 3-4 (mateixa essència, canvi de qualificador)
→ `compare_text()` diu MISMATCH perquè les paraules són massa diferents

### Diagnòstic etapa 6

**El diagnostic sobrevalora els MISMATCH per falta d'LLM judge.**
La comparació actual és string-based. Per a text de domini com building_type,
"un habitatge unifamiliar aïllat" i "un nou habitatge unifamiliar" són
essencialment el mateix concepte amb matisos diferents.

**Acció:** Integrar LLM judge al diagnostic per a variables Tier B (text lliure).

---

## 7. Resum d'accions per prioritat

### Alta prioritat (impacte directe en accuracy mesurada)
1. **Integrar LLM judge a diagnostic_trace.py** — reduirà falsos MISMATCH
2. **Millorar extracció vision del plànol** — building_type, building_height, etc.
3. **Refinar label "OBRA" als formats** — eliminar de pressupost o afegir context_filter

### Mitja prioritat (cobertura del sistema)
4. **Crear format schemas per lab** — 8 conceptes lab sense mapping
5. **Completar planol_vision_v1.yaml** — de 9 a ~15 mappings
6. **Documentar que vision bypassa formats** — dpsh/sondeig vision no usen format mapping

### Baixa prioritat (millores incrementals)
7. **Afinar prompt LLM synthesis** — no afegir qualificadors sense evidència
8. **Investigar coverage 20% plànol Bell-Lloc** — per què s'extreu tan poc?
9. **Verificar SmartScan Linyola** — el fitxer classificat com a plànol és correcte?

---

## 8. Respostes a les preguntes obertes (verificades)

### 8.1 Les senyals SÍ mapegen a building_type — el mapping és correcte, el VALOR és dolent

Les 6 senyals de FileMiner per Bell-Lloc tenen `concept_id=building_type` correctament.
El problema NO és de mapping sinó de **qualitat del valor extret**:
- Senyals 1-2: L'etiqueta "OBRA" al pressupost captura l'adreça, no el tipus
- Senyals 3-5: L'etiqueta captura el títol de l'estudi, no el tipus d'obra
- Senyal 6: "CONSTR HABITATGE" — genèric però correcte

**Conclusió:** El label "OBRA" és massa ampli i captura dades incorrectes.
El mapping funciona (l'etiqueta es resol al concepte correcte), però el
valor associat a l'etiqueta és dolent en determinats formats de document.

### 8.2 El plànol SÍ extreu building_type — amb "aïllat" inclòs!

`planol_extracted.json` de Bell-Lloc conté:
```json
{
  "building_type": "habitatge unifamiliar aïllat",
  "project_name": "HABITATGE UNIFAMILIAR AÏLLAT"
}
```

**TROBALLA CLAU:** El plànol A.01.pdf diu **"HABITATGE UNIFAMILIAR AÏLLAT"** al caixetí.
El vision l'extreu correctament. Per tant:
- "aïllat" NO és inventat per l'LLM synthesis — surt realment del plànol
- Eva escriu "un habitatge unifamiliar" (SENSE "aïllat") — Eva omet "aïllat" deliberadament
- El pipeline és **més fidel al document original** que Eva en aquest cas

Això canvia la diagnosi: el CLOSE a Bell-Lloc no és un error del pipeline.
Eva simplifica, el pipeline és literal. Ambdós són correctes; la diferència
és d'estil, no de contingut.

### 8.3 Però llavors, per què el vision no arriba com a senyal guanyadora?

El `source_priority` per `building_type` diu:
```yaml
planol_vision: 20  (hauria de guanyar)
pressupost_pdf: 30
groq_llm: 42
```

Però el valor final ve de `llm_synthesis`, no de `planol_vision`.
La cadena és: vision extreu → `planol_extracted.json` → normalitzador →
wizard_service merge → llm_synthesis sobreescriu.

**PROBLEMA IDENTIFICAT:** L'LLM synthesis s'executa DESPRÉS del merge de
prefills i **sobreescriu** el valor del planol vision. El valor correcte
("habitatge unifamiliar aïllat" de vision, prioritat 20) existeix, però
l'LLM synthesis (que no té prioritat al schema) el reemplaça amb la seva
pròpia síntesi ("un habitatge unifamiliar aïllat" — afegeix l'article).

En aquest cas concret el resultat és equivalent, però el mecanisme és
preocupant: **l'LLM synthesis ignora el sistema de prioritats.**

### 8.4 Per què el format learning diu 20% coverage al plànol?

Si el vision extreu building_type, architect, client_name, municipality, etc.,
com pot ser que el format learning digui 20%?

**Hipòtesi:** El format learning mesura la cobertura del **format schema**
(planol_vision_v1.yaml amb 9 mappings), no de l'extracció vision real.
El plànol extreu moltes dades via prompt dedicat, però només 9 conceptes
tenen mapping al format schema → els altres no compten per la cobertura.

**Acció:** Verificar com es calcula el 20% i si el format learning
hauria de considerar les extraccions vision (que van per via directa).

---

## 9. Diagrama del problema central

```
                       ┌─────────────────────────────┐
                       │ A.01.pdf (PLÀNOL)            │
                       │ "HABITATGE UNIFAMILIAR AÏLLAT"│
                       └──────────┬──────────────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
           FileMiner         Vision          ConceptScout
           (text PDF)       (imatge)          (agrega)
                  │               │               │
            NO TEXT!        ✅ Extreu        No entry
         (PDF escanejat)   building_type:    (depèn FM)
                           "habitatge         
                            unifamiliar       
                            aïllat"           
                                  │
                                  ▼
                          planol_extracted.json
                          (source: planol, pri=20)
                                  │
                                  ▼
                          ┌──────────────┐
                          │ Merge prefills│ ← valor correcte arriba aquí
                          └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────────┐
                          │ LLM Synthesis     │ ← SOBREESCRIU amb llm_synthesis
                          │ (Claude API call) │    "un habitatge unifamiliar aïllat"
                          └──────┬───────────┘
                                 │
                                 ▼
                          Valor final al wizard
                          source: "llm_synthesis"
                          (priority del schema ignorada)
```

**Conclusió principal:** El pipeline FUNCIONA per la via correcta (vision → planol_extracted),
però l'LLM synthesis sobreescriu el resultat ignorant el sistema de prioritats.
El valor és equivalent en aquest cas, però el mecanisme viola el disseny del sistema.

---

## 10. Accions revisades (post-verificació)

### Urgent
1. **LLM synthesis no hauria de sobreescriure valors amb prioritat millor.**
   Si building_type ja ve de `planol_vision` (pri=20), llm_synthesis (pri no definida)
   no l'hauria de tocar. Fix: comprovar source priority abans de sobreescriure.

2. **Integrar LLM judge a diagnostic_trace.py** per a variables text (Tier B).
   Reduirà falsos MISMATCH i donarà una imatge més precisa de l'accuracy real.

### Important
3. **Eliminar "OBRA" de pressupost_pdf_v1.yaml** — captura adreces, no building_type.
4. **Completar format schemas** — els 19 conceptes que necessiten mapping.
5. **Investigar Linyola** — SmartScan classifica correctament el plànol?

### Aprenentatge
6. **"aïllat" NO és inventat** — Eva simplifica, el pipeline és literal.
   El diagnostic hauria de tractar això com CLOSE (que ja ho fa), no com error.
7. **El 20% coverage del format learning** pot ser enganyós perquè vision
   bypassa els format schemas — investigar com es calcula.
