# Pla: Visió Exhaustiva de Tots els Fitxers del Projecte

Data: 2026-04-11
Revisat: 2026-04-11 (post-anàlisi metadades, SmartScan audit, ConceptScout review)
Origen: Sessió d'anàlisi que va descobrir que el projecte complet de l'arquitecte (11 pàgines amb superfícies, alçada, normativa) NO s'envia a visió perquè SmartScan tria un plànol d'1 pàgina com a primari.

## La Troballa

### Cas Linyola (el més clar)
- **PRIMARY** architect_plan: `Punts de Sondeig_Silvia.pdf` (1 pàgina, ubicació punts)
- **IGNORAT**: `2_02B_DG_Silvia_Jaume.pdf` (11 pàgines, projecte complet arquitecte)
- El document ignorat conté: sup. construïda (250.91 m²), sup. parcela (571 m²), alçada (3.44m), num_floors (PB), taula normativa urbanística completa, ref cadastral
- FileMiner n'extreu: telèfon, email, data, expedient (5 senyals de text)
- Vision extraction: NO el processa — només processa el primari

### Patrons per projecte

| Projecte | PRIMARY (1 pàg) | DOCUMENT RIC ignorat | Pàg |
|---|---|---|---|
| **Linyola** | Punts de Sondeig (ubicació) | 2_02B_DG (projecte complet) | 11 |
| **Anciles** | A01_TIPOL (tipologies) | IV_PLANOS (projecte complet) | 35 |
| **Castellar** | _(cap assignat)_ | PRESSUPOST GEOTEC (7p) | 7 |
| **Rubí** | IMG WhatsApp (foto plànol) | PRESSUPOST GEOTEC (7p) | 7 |
| **Bell-Lloc** | A.01.pdf ← CORRECTE | _(ja funciona bé)_ | — |
| **Alcoletge** | A.01.pdf | _(no hi ha projecte complet)_ | — |
| **Vilanova** | 1.0.pdf (avantprojecte) | _(no hi ha projecte complet)_ | — |

### Impacte al diagnòstic

| Variable | Errors actuals | Dada al document ignorat? |
|---|---|---|
| superficie_construida_m2 | 3 MISMATCH + 3 missing | **SÍ** (taula pàg 3/5) |
| building_height_m | 7/7 missing | **SÍ** (normativa pàg 1) |
| superficie_parcela_m2 | 2 MISMATCH + 3 missing | **SÍ** (normativa pàg 1-2) |
| num_floors | 2 MISMATCH + 1 missing | **SÍ** (normativa pàg 1) |

**~21 errors/missing potencialment recuperables.**

## Troballes Addicionals (post-anàlisi)

### SmartScan: Accuracy 42.9% per architect_plan

Auditoria dels 7 projectes:

| Projecte | Detectat | Real | Resultat | Tier |
|---|---|---|---|---|
| Bell-Lloc | A.01.pdf | A.01.pdf | CORRECTE | filename |
| Castellar | (absent) | (absent) | CORRECTE | — |
| Alcoletge | A.01.pdf | A.01.pdf | CORRECTE | filename |
| Rubí | IMG WhatsApp | (absent) | **FALS POSITIU** | vision |
| Linyola | Punts de Sondeig | (absent) | **FALS POSITIU** | fingerprint |
| Vilanova | 1.0.pdf | (absent) | **FALS POSITIU** | fingerprint |
| Anciles | A01_TIPOL.pdf | (absent) | **FALS POSITIU** | fingerprint |

**Causes arrel:**
- Tier 1: només busca a l'arrel del projecte (`scopes: ['']`), ignora subcarpetes
- Tier 2: threshold 0.15 massa permissiu — keywords genèrics ("escala", "cota") triggeregen falsos positius
- `role_files`: feature existent al codi però **BUIDA en tots 7 projectes** — mai es pobla
- ~40% dels fitxers queden sense classificar

**Conclusió**: SmartScan no és prou fiable per decidir què processar. Cal processar tot el que sigui visual.

### Metadades PDF: Sorpresa positiva

| Camp | Cobertura | Utilitat |
|---|---|---|
| **CREATOR** | 89.4% | AutoCAD → plànol arquitecte, Word → informes, NAPS2 → escanejats |
| **AUTHOR** | 66% | "G3 DESENVOLUPAMENT TERRITORIAL" → docs oficials G3, noms consultors |
| **PRODUCER** | 100% | Qualitat PDF (Acrobat Distiller = alta qualitat) |
| **Creation date** | **0%** | No disponible en cap PDF. Cal mtime del filesystem |

**Exemple**: `2_02B_DG_Silvia_Jaume.pdf` → creator: AutoCAD 2022, 11 pàg, 6.49 MB vs `Punts de Sondeig` → AutoCAD, 1 pàg, 0.14 MB. La combinació **creator + page_count + file_size** ja discrimina molt bé.

### ConceptScout vs Vision Extractor: Complementaris

| | ConceptScout (Fase 0.45) | Vision Extractor (Fase 1) |
|---|---|---|
| **Pregunta** | "ON és la dada?" | "QUIN és el valor?" |
| **Pàgines** | Només pàgina 1 | Totes |
| **Cost** | ~$0.01/fitxer | ~$0.10-0.50/fitxer |
| **Output** | Presència + preview | Valors estructurats complets |
| **Model** | Groq (barat) | Claude (precís) |

No es dupliquen. ConceptScout és l'explorador barat, Vision Extractor és l'extractor de precisió. La cadena natural: ConceptScout identifica fitxers rics → Vision Extractor extreu valors.

## Preguntes Resoltes

### 1. Altres tipus de fitxer amb el mateix problema?

**DOC/DOCX**: Portades, tests, explicacions. FileMiner ja els processa per text. No requereixen visió addicional.

**XLSX**: PLAN_COST (costos interns G3, poc útil), DADES PER ANAR A CAMP (preparació camp). FileMiner ja recorre TOTES les pestanyes de cada Excel. No requereixen visió.

**Conclusió**: El problema és principalment amb PDFs multi-pàgina (projectes d'arquitecte, pressupostos signats).

### 2. Costos de visió per pàgines

| Model | 35 pàg (cas extrem) | 15 pàg (típic) | Nota |
|---|---|---|---|
| **gpt-4.1-mini** | $0.087 | $0.039 | Actual, millor value |
| llama-4-scout (Groq) | $0.011 | $0.005 | Molt barat, qualitat menor |
| claude-sonnet-4-6 | $0.200 | $0.104 | Més car, més fiable |
| gpt-4.1 | $0.437 | $0.197 | Qualitat premium |

**Conclusió**: Enviar TOTES les pàgines amb gpt-4.1-mini costa $0.04-0.09 per document. Negligible. No val la pena optimitzar quan perdem dades crítiques.

### 3. Processar TOTS els fitxers, no només el primari

**Decisió**: Sí. Fins que no els veiem, no sabem si tenen informació rellevant. L'estalvi de no enviar-los és de cèntims; el cost de no tenir les dades és setmanes de debugging.

**Reforçat per l'auditoria SmartScan**: Amb accuracy del 42.9% per architect_plan, confiar en la classificació per decidir què processar és inacceptable. Cal processar tot el que sigui visual (PDF no-text, imatges), independentment de la classificació SmartScan.

### 4. Límits de pàgines

| Component | Límit actual | Nou límit |
|---|---|---|
| Vision extraction (planol/sondeig) | **5 pàgines** | **50 pàgines** (amb warning al log si es talla) |
| SmartScan Tier 3 | 10 pàgines | OK |
| ConceptScout vision_probe | 50 pàgines (1a pàg real) | OK |
| Terrain observation | 1 pàg/imatge | OK |

### 5. Conceptes — Estat actual

65 conceptes definits a `schemas/concepts/report_variables.yaml`.

**Problemes detectats**:
- `superficie_construida`: type="text" hauria de ser "numeric". Sense sources ni description.
- `superficie_parcela`: idem
- `qa_value`, `k30_value`: **NO tenen concepte definit** (són calculats)
- `settlement`: Només `Es_settlement` (paràmetre de càlcul, no el resultat final)
- Molts conceptes tenen `sources: []` i `description: ?` (buits)

### 6. Resolució de conflictes entre fitxers

**Estratègies analitzades** (de sistemes solvents: MDM, RAG, document processing):

| Estratègia | Ja la tenim? | Valor per G3DT |
|---|---|---|
| **Priority chain** (font fixa per variable) | Sí (`report_variables.yaml`) | Base sòlida |
| **Confidence-weighted** (puntuació per extracció) | Parcial (FileMiner signals) | Alta — gestiona OCR brut |
| **Provenance tagging + arbitratge Eva** | No | **Millor addició** |
| Quorum/acord | Sí (DPSH penetros vs Excel) | Limitat |
| Recència temporal | No | Poc útil en geotècnia |

**Decisió**: Híbrid de 3 nivells:
1. **Python decideix** quan hi ha regla clara (priority chain + confidence > threshold)
2. **Eva arbitra** quan hi ha conflicte real: wizard mostra valors competidors amb badges de font, Eva tria
3. **LLM-judge** (existent) valida coherència global al final — no resol conflictes puntuals

No cal un LLM Synthesis dedicat per resoldre conflictes. L'actual Groq miner segueix omplint buits (un fitxer a la vegada); els conflictes es resolen per regles o per Eva.

### 7. Optimització de costos (idees per explorar)

- **4-en-1 thumbnail**: Renderitzar 4 pàgines en 1 imatge (quadrants), enviar a LLM econòmic per identificar quines pàgines tenen conceptes rellevants, després enviar només les pàgines útils al model de qualitat
- **Text pre-filter**: Si el PDF té text extractable, buscar keywords ("SUPERFÍCIES", "ALÇADA", "PLANTES") per pàgina i enviar a visió només les pàgines amb keywords
- **Cascada**: Groq primer (molt barat) → si detecta conceptes, re-enviar a gpt-4.1-mini per extracció precisa

## Pla d'Implementació

### Fase 1: Experiment (validació ràpida)

**Objectiu**: Confirmar que processar documents "ignorats" recupera dades crítiques, i descartar falsos positius.

**Tests positius** (esperem trobar dades):
- Enviar `2_02B_DG_Silvia_Jaume.pdf` (Linyola, 11p) a gpt-4.1-mini TOTES les pàgines
- Prompt: llista de conceptes a buscar (superfícies, alçada, plantes, arquitecte, promotor, ref cadastral, adreça)
- Comparar resultats amb valors Eva
- Repetir amb Anciles `IV_PLANOS.pdf` (35p)

**Test negatiu** (esperem NO trobar dades rellevants):
- Enviar `PRESSUPOST GEOTEC.CASTELLAR.pdf` (7p) — document de pressupost, no hauria de generar camps de plànol
- Confirmar que no genera falsos positius (superfícies inventades, etc.)

**Mesurar**:
- Cost real per document
- Temps d'execució per document (impacte en latència wizard)
- Qualitat extracció vs valors Eva

**Explorar metadades**:
- Extreure CREATOR, AUTHOR, page_count dels PDFs de test
- Avaluar si la combinació `creator + page_count + file_size` discrimina bé el tipus de document

### Fase 2: Pipeline integration

**Canvi fonamental**: Processar **tots els PDFs visuals** del projecte (no-text o amb pàgines escaneejades), independentment de la classificació SmartScan.

**Nou prompt de visió**: `projecte_arquitecte`
- Dedicat a projectes d'arquitecte multi-pàgina
- Busca: superfícies (construïda, parcela), alçada, plantes, normativa urbanística, ref cadastral, arquitecte, promotor
- Diferent del prompt `planol` (que busca caixetí + cotes)

**Resolució de conflictes**:
- Priority chain (existent a `report_variables.yaml`) → Python decideix automàticament
- Confidence-weighted: si dues fonts donen el mateix concepte, la de més confiança guanya
- Si conflicte no resoluble: provenance tagging al wizard — Eva veu els valors competidors amb badge de font i tria
- Elecció d'Eva es guarda per futur aprenentatge

**Límits**:
- max_pages = 50 amb warning al log si es talla
- Barra de progrés o indicador de temps estimat si el total de pàgines > 20

### Fase 3: Metadades + SmartScan millores

**Metadades PDF** (nou):
- Incorporar `CREATOR`, `AUTHOR`, `page_count`, `file_size` a SmartScan Tier 2
- Regla: `creator=AutoCAD + pages>3` → alta probabilitat de plànol d'arquitecte ric
- Regla: `creator=NAPS2` → document escanejat (camp), necessita visió segur

**SmartScan fixes**:
- Poblar `role_files` (feature existent però buida en tots 7 projectes)
- Threshold fingerprint: 0.15 → 0.25 (reduir falsos positius)
- Tier 1 scopes: afegir subcarpetes (`['', '*/', '*/*/']`)
- Afegir patrons espanyols: `PLANOS`, `PLANO`, `PROYECTO`

**Nota**: Fase 3 és independent de Fase 2 — es pot fer en paral·lel o posposar. Processar tot (Fase 2) fa que la qualitat de SmartScan sigui menys crítica, però millorar SmartScan segueix sent útil per: selecció intel·ligent de prompt, priorització de fonts, i diagnòstics.

### Fase 4: Completar definicions de conceptes

- Afegir sources a cada concepte (d'on s'espera trobar-lo)
- Corregir types (superficie → numeric)
- Afegir conceptes que falten (qa_value, k30_value, settlement)

## Fitxers Clau a Modificar

| Fitxer | Fase | Canvi |
|---|---|---|
| `web/vision_groq.py` | 2 | Processar tots els PDFs visuals, no només primari. Límit 50 pàg. |
| `automation/validation/prompts.py` | 2 | Nou prompt `PROJECTE_ARQUITECTE_EXTRACTION_PROMPT` |
| `automation/vision_extractor.py` | 2 | Suport multi-fitxer per rol + nou vision_type |
| `web/wizard_service.py` | 2 | Provenance tagging per conflictes (mostrar fonts competidores) |
| `templates/validation/review.html` | 2 | UI per mostrar valors competidors amb badges de font |
| `automation/smartscan/tier2_fingerprint.py` | 3 | Metadades PDF + threshold 0.25 |
| `automation/smartscan/tier1_filename.py` | 3 | Scopes subcarpetes + patrons espanyols |
| `automation/smartscan/models.py` | 3 | Poblar role_files |
| `schemas/concepts/report_variables.yaml` | 4 | Completar definicions |

## Referència: Fitxers del Projecte Linyola (per l'experiment)

```
# Projecte complet arquitecte (11p) — LA FONT PRINCIPAL
reference-material/4001607 LINYOLA/25.0616/2_02B_DG_Silvia_Jaume.pdf

# Plànol punts (1p) — l'actual primari (pobre)
reference-material/4001607 LINYOLA/25.0616/Punts de Sondeig_Silvia_Jaume.pdf

# Valors Eva per comparar
reference-material/4001607 LINYOLA/validation/eva_reference_values.json
```

## Referència: Metadades PDF rellevants

```
# Document ric Linyola
2_02B_DG_Silvia_Jaume.pdf → creator: AutoCAD 2022, 11 pàg, 6.49 MB

# Document pobre Linyola
Punts de Sondeig_Silvia_Jaume.pdf → creator: AutoCAD 2022, 1 pàg, 0.14 MB

# Plànol correcte Bell-Lloc
A.01.pdf → creator: AutoCAD 2021, 1 pàg, 1.25 MB

# Documents escanejats
PENETROS.pdf → creator: NAPS2, 2-3 pàg (documents de camp)
```
