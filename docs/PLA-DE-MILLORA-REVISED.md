# Pla de Millora del Pipeline — Revisat

**Data:** 2026-04-06
**Base:** `BASELINE-I-PLA-DE-TREBALL-2026-04-06.md` (29.3% match+close)
**Referencia tecnica:** `GUIA-SISTEMA-EXTRACCIO.md`

---

## 0. Critica del Pla Original

El pla original (BASELINE) te bona intuicio sobre els problemes pero presenta 3 debilitats:

### 0.1 Diagnostica sense veure

El diagnostic actual (`diagnostic_trace.py`) mostra QUE falla, pero no PER QUE. Veiem "client_name = MISMATCH" pero no:
- Quines fases es van executar realment?
- Quins signals es van generar per a cada concepte?
- Quins inputs va rebre el calculador de Terzaghi?
- La vision va extreure correctament pero el merge va triar un altre valor?

**Implicacio:** El pla original proposa "arreglar adjacents" o "arreglar qa_value" sense entendre completament per que fallen. Primer hem de poder **veure** que passa.

### 0.2 Ignora el gap arquitectonic principal

El sistema te prioritats per-concepte definides al YAML (`report_variables.yaml`) pero **no les utilitza**. La competicio usa prioritats globals. Activar les prioritats per-concepte resoldria molts MISMATCH sense tocar extracccions.

### 0.3 Barreja problemes de diferent naturalesa

El pla barreja:
- Problemes de **FORMAT de sortida** (adjacents: dada correcta, frase incorrecta)
- Problemes de **PRIORITAT** (client_name: dada correcta al signal #4 que perd)
- Problemes de **CALCUL** (qa_value: inputs incorrectes)
- Problemes d'**EXTRACCIO** (num_floors: vision no va extreure)
- Problemes de **NO IMPLEMENTAT** (CTE, seismic, radon)

Cada tipus de problema necessita una estrategia diferent.

---

## 1. Filosofia Revisada

### Principi 1: Primer veure, despres arreglar

No tocar cap extraccio fins que el diagnostic mostri **exactament** que passa a cada pas. Si no podem mesurar, no podem millorar.

### Principi 2: Activar el que ja tenim

Les prioritats per-concepte estan definides. Format schemas estan creats. Signal competition te el `concept_id`. Activar-ho tot abans de crear res nou.

### Principi 3: Un canvi, una mesura

Cada canvi es mesura immediatament contra els 7 projectes. Si la metrica no millora, revertir. Cada bloc acaba amb un `diagnostic_trace.py --all` que confirma la millora.

### Principi 4: Classificar per tipus de problema

| Tipus | Que cal fer | Exemple |
|-------|------------|---------|
| FORMAT | Transformar sortida (dada ja correcta) | Adjacents |
| PRIORITAT | Canviar quina font guanya | client_name |
| CALCUL | Corregir inputs/formula | qa_value |
| EXTRACCIO | Millorar com es troba la dada | architect_name |
| MAPPING | Connectar dada existent al prefill | spt_*, sulfate_classification |
| LOOKUP | Implementar taula/API | CTE, seismic, radon |
| NARRATIVA | Eva l'escriu, no es pot automatitzar | site_description |

---

## 2. Bloc 0: Instrumentacio del Diagnostic (PREREQUISIT)

**Objectiu:** Poder respondre, per a QUALSEVOL variable de QUALSEVOL projecte:
1. Quines fases es van executar?
2. Quins signals es van generar per a aquest concepte? (de quins fitxers, amb quina prioritat, amb quina confianca)
3. Quin signal va guanyar la competicio i per que?
4. Si la vision va extreure un valor, es va usar o es va descartar?
5. Si es un valor calculat, quins inputs es van usar?

### 0.1 Afegir logging de fases executades

**Fitxer:** `automation/auto_extractor.py`

Al `auto_extract()`, registrar quines fases es van executar i quines es van saltar:

```python
# A AutoExtractionResult, afegir:
phases_executed: list[str] = []   # ["0.1_scanner", "0.3_fileminer", "1.0_dpsh", ...]
phases_skipped: dict[str, str] = {}  # {"3.0_geology": "no UTM coordinates"}
```

**Al diagnostic_trace.py:** Imprimir a la capsalera de cada projecte:
```
Phases: 0.1✓ 0.3✓ 0.4✓ 1.0✓ 1.1✓ 2.0✓ 2.5✗(no COORDENADES.txt) 3.0✓ 3.3✓
```

### 0.2 Afegir trace de signals per variable (incloent vision)

Ampliar el diagnostic per mostrar:
- **Tots** els signals, no nomes els de FileMiner (incloure vision, API, calculs)
- Per a cada signal: `{font, fitxer, valor, prioritat, confianca, [fase_que_el_va_generar]}`
- Marcar quin signal coincideix amb Eva (si algun)

### 0.3 Afegir trace de calculs geotecnics

Per a `qa_value`, `settlement`, `k30_value`: imprimir els inputs:
```
qa_value = 1.36  (Nb=25.3, B=1.0[DEFAULT], Df=0.8[DEFAULT], cohesion=0.0, cap=3.0)
```

Aixi veurem immediatament: "B i Df son defaults, per aixo qa divergeix".

### 0.4 Afegir columna "correcte existeix?"

Per a cada MISMATCH, comprovar si algun signal (no el guanyador) coincideix amb Eva:
```
client_name  MISMATCH  Pipeline: "GRUP ALMA"  Eva: "WOOD COMFORT"
  → Correcte existeix? NO — cap signal te el valor d'Eva
```
vs
```
client_name  MISMATCH  Pipeline: "ARQUITECCTURA BOSCH NOVELL"  Eva: "RAMON MITJANA S.L."
  → Correcte existeix? SI — signal #4 (PDF V0, pri=45)
  → Solucio: canviar prioritats per a client_name
```

Aixo classifica automaticament cada MISMATCH en "dada correcta existeix, cal canviar prioritats" vs "dada no existeix, cal millorar extraccio".

### Mesura de sortida

Re-executar diagnostic amb la nova instrumentacio. Classificar TOTS els 70 MISMATCH en:
- **PRIORITAT:** Valor correcte existeix com a signal alternatiu → 0.2 canviar prioritat
- **FORMAT:** Valor cru correcte, format incorrecte → transformar sortida
- **CALCUL:** Inputs identificables amb defaults erronis → corregir inputs
- **EXTRACCIO:** Valor no existeix a cap signal → millorar extractor o afegir nova font
- **NARRATIVA:** Eva l'escriu manualment → acceptar o implementar template millor

**Temps estimat:** 2-3 hores
**Impacte directe:** 0 (no canvia cap valor), pero ens dona el mapa complet per a tots els blocs seguents.

---

## 3. Bloc 1: Activar Prioritats Per-Concepte

**Objectiu:** Que `competition.py` usi les prioritats del concept schema, no les globals.

### 1.1 Canvi a competition.py

Actualment:
```python
# competition.py — usa SOURCE_PRIORITY global
priority = get_priority(signal.source_type)  # label_map.SOURCE_PRIORITY
```

Ha de ser:
```python
# competition.py — usa prioritat per-concepte
from automation.schemas import concept_registry
priority = concept_registry.get_priority(signal.concept_id, signal.source_type)
```

`ConceptRegistry.get_priority()` ja existeix (loader.py). Nomes cal cridar-lo.

### 1.2 Ajustar prioritats al YAML

Revisar i ajustar les `source_priority` de cada concepte al YAML. Casos clau:

**client_name:** El pressupost i DADES CAMP tenen l'arquitecte/contacte, NO el promotor.
```yaml
client_name:
  source_priority:
    user: 10
    planol_vision: 20       # Caixeti "PROMOTOR"
    pressupost_pdf: 50       # ↓ Baixar: te l'arquitecte, no el promotor
    dades_camp_excel: 50     # ↓ Baixar: te el contacte, no el promotor
    content_pdf: 35          # ↑ Pujar: PDF V0 te el client real
    groq_llm: 42
    content_email: 43
```

**architect_name:** El planol es la font mes fiable.
```yaml
architect_name:
  source_priority:
    user: 10
    planol_vision: 15        # ↑ Pujar: planol es la font definitiva
    pressupost_pdf: 40       # ↓ Baixar: sovint te "A/A" que es l'empresa
    groq_llm: 45             # ↓ Baixar: Groq extreu qualsevol nom
```

### 1.3 Verificacio

```bash
.venv/bin/python scripts/diagnostic_trace.py --all
```

**Mesura esperada:** client_name hauria de millorar a 3-5/7 projectes (els que tenen el valor correcte a signals alternatius). Podria empitjorar si les noves prioritats desequilibren altres variables → per aixo mesurem TOT.

**Temps estimat:** 1-2 hores
**Impacte esperat:** 5-10 MISMATCH → MATCH/CLOSE (client_name + potser architect_name + expedient)

---

## 4. Bloc 2: Format de Sortida dels Adjacents

**Objectiu:** 28 MISMATCH → 0 (o CLOSE)

### Analisi del problema

El pipeline extreu dades crues del Cadastre:
- `"parcel·la buida"`, `"parcel·la amb construcció"`, `"Carrer X"`

Eva escriu frases:
- `"Per la part sud amb el Carrer Antoni Bellet."`
- `"I finalment, per la part oest, amb una parcel·la amb una construcció."`

**Tipus:** FORMAT (dada correcta, presentacio incorrecta)

### Solucio

A `_merge_prefills()` o a `_generate_template_prefills_from_merged()`, transformar:

```python
ADJACENT_TEMPLATES = {
    "north": "Per la part nord amb {desc}.",
    "south": "Per la part sud amb {desc}.",
    "east": "Per la part est amb {desc}.",
    "west": "I finalment, per la part oest, amb {desc}.",
}
# desc: "el Carrer X" (si carrer) o "una parcel·la buida/amb construcció" (si parcel·la)
```

Regles de transformacio:
- Si comenca per nom de carrer → `"el Carrer {nom}"`
- Si es `"parcel·la buida"` → `"una parcel·la buida"`
- Si es `"parcel·la amb construcció"` → `"una parcel·la amb una construcció"`
- Direccio `"west"` porta prefix "I finalment, " (convencio d'Eva)

### Consideracions per idioma

- Projectes catalans: "Per la part nord amb..."
- Projectes castella (Vilanova, Anciles): "Por la parte norte con..."
- Detectar idioma via municipality (Arago → castella)

### Verificacio

Re-executar diagnostic. Adjacents han de ser CLOSE o MATCH.

**Temps estimat:** 1-2 hores
**Impacte esperat:** 28 MISMATCH → ~24 CLOSE + ~4 MATCH

---

## 5. Bloc 3: Calculs Geotecnics (qa_value, settlement)

**Objectiu:** qa dins 10% d'Eva per projectes amb dades completes

### 5.1 Diagnosticar amb instrumentacio

Gracies al Bloc 0, tindrem:
```
qa_value = 1.36  (Nb=25.3, B=1.0[DEFAULT], Df=0.8[DEFAULT], cohesion=0.0, cap=3.0)
```

### 5.2 Carregar user_data.json si existeix

Per a projectes que ja han passat pel wizard, hi ha `user_data.json` amb B i Df reals. Carregar-los al diagnostic:

```python
user_data_path = project_path / "user_data.json"
if user_data_path.exists():
    user_data = json.loads(user_data_path.read_text())
    B = user_data.get("B", 1.0)
    Df = user_data.get("foundation_depth_m", 0.8)
```

### 5.3 Verificar el cap professional

Eva aplica:
- Sol granular: cap 3.0 kg/cm2
- Roca (cohesion >= 0.5): cap 4.5-5.0 kg/cm2

El calculador actual: cap 3.0 o 5.0 segons cohesion. Verificar que cohesion es detecta correctament per a cada projecte.

### 5.4 Settlement Es

Implementat: `Es = 2.5 × Nb` (square). Eva ajusta en revisions. El diagnostic ha de mostrar quin Es s'usa.

### Verificacio

Re-executar per cada projecte. qa_value dins 10% per a 4-5/7 projectes.

**Temps estimat:** 2-3 hores
**Impacte esperat:** 14 MISMATCH → ~8 MATCH + ~4 CLOSE + ~2 MISMATCH (projectes sense user_data)

---

## 6. Bloc 4: Variables de Mapping (connectar dades existents)

**Objectiu:** Variables que la dada existeix (a vision JSONs, a calculs) pero no arriba al prefill.

### 4.1 SPT des de sondeig_extracted.json

El vision de sondeig extreu `spt_results` pero no es mapeja a:
- `spt_test_id` → `spt_results[0].test_id`
- `spt_n30` → `spt_results[0].blows`
- `spt_depth_range` → format des de profunditats
- `spt_lithology` → de la capa on es fa l'SPT
- `spt_location` → `spt_results[0].location`

### 4.2 Sulfats derivats

`sulfate_mg_kg` ja s'extreu. Derivar:
- `sulfate_classification`: <2000 → "No Agressius", 2000-3000 → "Dèbilment agressius", etc. (RD 470/2021)
- `sulfate_baumann`: "--" si <2000, calcul de Baumann si >=2000
- `sulfate_level_name`: "1er nivell" / "2on nivell" segons posicio a sondeig

### 4.3 Num_floors des de vision

`planol_extracted.json` te `num_floors` pero no arriba per a 4/7 projectes (NOT_EXTRACTED). Investigar per que:
- Vision no ho va extreure? → Millorar prompt
- Vision ho va extreure pero merge no ho va agafar? → Corregir mapping

### Verificacio

5 spt_* + 3 sulfate_* + 1 num_floors = 9 variables x projectes afectats.

**Temps estimat:** 2-3 hores
**Impacte esperat:** ~30-40 NOT_EXTRACTED → MATCH

---

## 7. Bloc 5: Lookups (CTE, seismic, radon)

**Objectiu:** Implementar taules de referencia per variables que depenen del municipi.

### 5.1 CTE (cte_edificacio, cte_sol)

Classificacio CTE basada en:
- `building_type` + `num_floors` → C-0, C-1, C-2, C-3, C-4
- `municipality` → zona sismica → T-1, T-2, T-3

Necessita: una taula de classificacio (relativament simple).

### 5.2 Seismic (seismic_ab_text)

Lookup per municipi dins el mapa sismic d'Espanya (NCSE-02):
- Lleida/Tarragona: generalment ab=0.04g
- Arago (Huesca): pot ser 0.05g
- Taula: ~100 municipis de la zona d'operacio de G3

### 5.3 Radon (radon_zone)

Mapa de zones de rado del CSN per municipi. Taula similar.

### Verificacio

6 cte_* + 7 seismic + 7 radon = ~20 NOT_EXTRACTED → MATCH

**Temps estimat:** 2-3 hores
**Impacte esperat:** ~20 NOT_EXTRACTED → MATCH

---

## 8. Bloc 6: Extraccio Format-Aware (building_type, architect_name + variants de format)

**Objectiu:** Millorar extraccions adaptant-se a les variacions reals de cada document.

### Resultats de l'Audit (2026-04-06)

L'audit de cobertura ha revelat que el problema principal NO es la qualitat del prompt de visio
(que es prou bo), sino tres problemes mes fonamentals:

**Problema 1: SmartScan no arriba als planols reals.**
Molts planols d'arquitecte estan a subcarpetes numeriques (25.0493/, 24.0807/) que SmartScan
no escaneja. Projectes afectats: Alcoletge, Vilanova, Anciles (tots amb planols GAP).

**Problema 2: El planol assignat no es el planol de l'arquitecte.**
A Castellar i Rubi, SmartScan assigna `architect_plan` al planol de SITUACIO de G3 (que mostra
la ubicacio del sondeig), no al planol de l'edifici de l'arquitecte.

**Problema 3: Vision caches potencialment obsolets.**
Les extraccions de visio cached poden tenir setmanes/mesos. Cal refrescar despres de cada
millora de prompts.

**Evidencia de l'audit:**
- Bell-Lloc (unic amb planol real + cache fresc): 66.7% match+close
- Projectes sense vision cache: 21-27% match+close
- 5 variables depenen del planol: architect_name, building_type, num_floors, superficie_*, building_height
- Cascada: planol falla → building_type falla → cte_edificacio falla

### 6.0 FIX: SmartScan escaneja subcarpetes numeriques (PREREQUISIT)

**Problema:** SmartScan ignora fitxers dins de carpetes amb noms com `25.0493/`, `24.0807/`,
`26.0049/`. Aquests contenen planols d'arquitecte (A01_TIPOL.pdf, planol-1.pdf, 1.0.pdf),
emails amb adjunts, i pressupostos.

**Fix:** Modificar el FileScanner/SmartScan per incloure subcarpetes numeriques al scan.
Actualment `_SKIP_DIRS` filtra certes carpetes. Cal assegurar que les carpetes numeriques
del projecte NO es filtren.

**Fitxers afectats:**
- `automation/file_scanner.py` o `automation/smartscan/classifier.py`
- Verificar que `_SKIP_DIRS` no exclou carpetes numeriques

**Projectes que es beneficien:**
- Castellar: 25.0493/ te PRESSUPOST, DADES, .msg amb adjunts
- Anciles: 24.0807/ te A01_TIPOL.pdf (planol complet de l'arquitecte!)
- Alcoletge: 26.0049/ te A.01.pdf (duplicat), planol-1/2/3.pdf, .msg
- Linyola: 25.0616/ te Punts_Sondeig.pdf, 2_02B_DG.pdf

### 6.1 Refrescar vision caches per als 7 projectes

Despres del fix de SmartScan, executar la visio per a TOTS els projectes per obtenir
`planol_extracted.json`, `sondeig_extracted.json` i `dpsh_extracted.json` actualitzats.

**Accio:** Executar wizard pipeline per cada projecte, o script dedicat de refresh.

### 6.2 Re-executar diagnostic i analitzar resultats

Amb els nous caches, tornar a mesurar. Ara podrem veure:
- Quants planols nous s'han trobat (SmartScan fix)
- Quines variables ha extret la visio dels nous planols
- On la visio encara falla → candidats per a format variants

### 6.3 Format variants (SI NECESSARI despres de 6.2)

Nomes si l'audit post-refresh mostra que la visio falla per a certs planols amb el
prompt actual. En aquell cas:

**Discriminadors estructurals al format schema:**
```yaml
format_id: planol_vision_v2_no_caixeti
discriminators:
  has_caixeti: false
  structural_cues: ["text labels scattered", "no title block"]
document_roles: [architect_plan]
source_type: planol_vision
```

**Sub-classificacio (Tier 2.5):** Despres que SmartScan assigni el rol, seleccionar
el format variant basant-se en fingerprint_data.

**Prompts adaptats:** Un prompt base + addicions per format variant.

**NOTA (revisar):** SmartScan Tier 3 (visio) nomes envia pagina 1. Per a planols
multi-pagina on el caixeti es a l'ultima pagina, cal revisar aquest criteri.

### 6.4 Building type: quantitat + articles

Eva escriu: "un habitatge unifamiliar", "3 habitatges unifamiliars adossats"
Pipeline extreu: "habitatge unifamiliar aillat"

**Accions:**
1. Comanda_lab: "CONSTR 3 HAB UNIF" → extreure quantitat (3)
2. Vision del planol amb el prompt adaptat → tipus i quantitat
3. Post-processament: article ("un/una/l'"), quantitat si >1, pluralitzar

### 6.5 Architect name: font correcta

Amb SmartScan trobant els planols reals, el prompt actual ja busca architect/company.
Groq baixa prioritat (ja fet al Bloc 1). Document ACCEPTACIO com a font alternativa.

### 6.6 Municipality: normalitzacio

- "CASTELLAR DEL VALLES" → "Castellar del Valles" (title case)
- "RUBI" → "Rubi (Barcelona)" → strip provincia

### 6.7 Lab report extraction (9 variables "never extracted")

L'audit mostra 9 variables lab_* que cap projecte extreu. Font: GTL report PDF.

**Variables:** lab_depth, lab_field_company, lab_field_description, lab_location,
lab_sample_id, lab_testing_company, lab_testing_description, lab_tests_text, access_street

**Accio:** Crear extractor dedicat per a informes GTL (portada + resultats).
Possiblement 2 formats: TPS (Lleida) i altres labs.

### 6.8 Futur: Format Learning v2 (DIFERIT)

Millorar el sistema d'aprenentatge per a formats de visio:
- Snapshots visuals per mostrar a Eva ("aquest planol es com aquest?")
- Auto-deteccio de noves variants a partir d'extraccions fallides
- Eva confirma quines pistes visuals distingeixen un format d'un altre

**Accio ara:** Diferir. Primer fer funcionar SmartScan + refresh.

### Verificacio

4 building_type + 5 architect_name + 1 municipality = ~10 millores directes.
Millora indirecta: extraccions mes fiables per a projectes futurs amb planols atipics.

**Temps estimat:** 4-6 hores (mes que l'original per l'analisi de variacions)
**Impacte esperat:** ~10 MISMATCH → CLOSE/MATCH + infraestructura per a futurs projectes

---

## 9. Bloc 7: Variables Narratives i Report Generator

**Objectiu:** Acceptar limitacions, millorar templates, preparar futur.

### 7.1 site_description (7 MISMATCH)

El pipeline genera text generic. Eva escriu descripcio real del camp.

**Realitat:** No es realista que el pipeline generi la descripcio exacta d'Eva. Pero podem millorar el template:
- Usar adjacents (carrers) per context
- Usar `is_sloped`, `is_anthropized` de ICGC
- Futur: vision de fotos de camp

**Accio ara:** Acceptar com a MISMATCH esperat (Tier B). No invertir temps.

### 7.2 lab_* variables (49 NOT_EXTRACTED)

Moltes variables lab_* es generen al report_generator (Fase 3), no al diagnostic. Investigar si:
- Algunes ja es generen i nomes falta exposar-les al diagnostic
- Algunes necessiten extraccio de nous documents (resultats lab PDF)

### 7.3 location_sentence, access_street (14 NOT_EXTRACTED)

Templates narratius que Eva compon. Millorar amb:
- `street_address` + adjacents → `location_sentence`
- `street_address` + Google Maps URL → `access_street`

---

## 10. Objectius per Fita i Mesura

### Mesura: `diagnostic_trace.py --all` despres de cada bloc

| Fita | Accions | MATCH+CLOSE esperat | MISMATCH restant | NOT_EXTRACTED restant |
|------|---------|---------------------|-------------------|-----------------------|
| **Baseline** | (actual) | 29/99 (29.3%) | 70 | 182 |
| **Bloc 0** | Instrumentacio | 29/99 (sense canvi) | 70 | 182 |
| **Bloc 1** | Prioritats per-concepte | ~39/99 (~39%) | ~60 | 182 |
| **Bloc 2** | Adjacents format | ~63/99 (~64%) | ~36 | 182 |
| **Bloc 3** | qa/settlement | ~73/99 (~74%) | ~26 | 182 |
| **Bloc 4** | Mappings (SPT, sulfats) | ~73/99 + ~30 NOT→MATCH | ~26 | ~152 |
| **Bloc 5** | Lookups (CTE, seismic) | + ~20 NOT→MATCH | ~26 | ~132 |
| **Bloc 6** | Format-aware extraction | ~83/99 (~84%) | ~16 | ~132 |
| **Bloc 7** | Narratives + report gen | + ~10-20 NOT→MATCH | ~16 | ~112 |

### Objectiu final realistic

- **MATCH+CLOSE dels comparats:** 80-85% (de ~84 a ~89 de 99)
- **NOT_EXTRACTED:** reduir de 182 a ~110 (les que queden son narratives o Fase 3 del report)
- **MISMATCH irreductibles:** ~15 (site_description, field_work_dates format, casos especials)

---

## 11. Ordre d'Execucio

```
PREREQUISIT                    CORE                          EXPANSIO
──────────────                ─────                         ─────────
Bloc 0: Instrumentacio   →   Bloc 1: Prioritats       →   Bloc 4: Mappings
(2-3h, 0 impacte directe)    (1-2h, +10 MATCH)            (2-3h, -30 NOT_EXT)
                              Bloc 2: Adjacents        →   Bloc 5: Lookups
                              (1-2h, +24 CLOSE)            (2-3h, -20 NOT_EXT)
                              Bloc 3: Calculs          →   Bloc 6: Format-aware
                              (2-3h, +10 MATCH)            (4-6h, +10 MATCH)
                                                      →   Bloc 7: Narratives
                                                           (2-3h, -10 NOT_EXT)
```

**Bloc 0 es obligatori primer.** Sense instrumentacio, els blocs 1-7 son proves a cegues.

**Blocs 1-3 son el core.** Representen el 80% de la millora amb el 40% de l'esforc.

**Blocs 4-7 son expansio.** Cada un es independent i es pot fer en qualsevol ordre.

---

## 12. Protocol per Cada Bloc

```
1. BASELINE: Executar diagnostic, anotar metriques actuals
2. ANALITZAR: Amb la instrumentacio, entendre exactament per que falla
3. CLASSIFICAR: Es FORMAT, PRIORITAT, CALCUL, EXTRACCIO, MAPPING, o LOOKUP?
4. IMPLEMENTAR: El canvi minim que resol el problema
5. MESURAR: Re-executar diagnostic, comparar amb baseline
   - Si millora: commit + continuar
   - Si empitjora: revertir, analitzar per que
   - Si sense canvi: el diagnostic mostrara per que (gracies Bloc 0)
6. DOCUMENTAR: Actualitzar la taula d'objectius amb metriques reals
```

---

## 13. Riscos i Mitigacions

| Risc | Probabilitat | Mitigacio |
|------|-------------|-----------|
| Canviar prioritats per-concepte desestabilitza variables que funcionen | ALTA | Tests de regressio (197 tests + 4 snapshots). Mesurar TOT despres de cada canvi. |
| Adjacents en castella (Vilanova, Anciles) tenen templates diferents | MITJANA | Detectar idioma per municipi. Templates bilingues. |
| user_data.json no existeix per a tots els projectes (qa_value) | ALTA | Acceptar que sense wizard, qa usa defaults. Documentar com a limitacio. |
| Vision no extreu per a tots els projectes (num_floors, superficie) | MITJANA | Verificar si vision es va executar. Si no: es un problema de cache, no de codi. |
| Format learning genera schemas que interfereixen | BAIXA | learned/ schemas tenen confianca alta (0.95) pero nomes per al rol/fitxer concret. |

---

*Document de treball. Actualitzar les metriques despres de cada bloc.*
