# Pla: Refinament Pipeline vs Eva
**Data:** 2026-04-06
**Objectiu:** Portar el pipeline del 23% match+close actual al maxim possible

---

## Objectiu 1: Analitzar cada MISMATCH i afinar schemas

### 1.1 Diagnostic log per concepte

Crear un script/command que per a cada concepte del schema:
- Llisti TOTES les fonts de la seva `source_priority`
- Per a cada font: mostri si va extreure un valor, quin, amb quina confianca
- Mostri el guanyador de la competicio i per que va guanyar
- Compari amb el valor d'Eva

Exemple de sortida esperada:
```
=== client (4001612 BELL-LLOC) ===
  Eva: "RAMON MITJANA S.L."
  Candidats del pipeline:
    pressupost_pdf (pri=30):  "ARQUITECTURA BOSCH NOVELL" (conf=0.85) ← WINNER (no es el client!)
    content_email (pri=43):   "Jordi Bosch" (conf=0.70)
    dades_camp_excel (pri=35): [no signal]
    planol_vision (pri=20):   [no signal - vision no executada]
  Diagnostic: La font guanyadora (pressupost) extreu l'arquitecte, no el promotor.
              El promotor real NO apareix a cap font del pipeline actual.
              Solucio: el planol hauria de tenir-lo (caixeti: "PROMOTOR: RAMON MITJANA")
```

### 1.2 Analisi per variable amb MISMATCH

| Variable | Causa | Solucio proposada |
|----------|-------|-------------------|
| **building_type** (7/7) | `comanda_lab_excel` abrevia: "CONSTR HAB UNIF" | Necessita font amb text complet: planol (vision) o pressupost. Crear format schema especific per pressupost que extregui "OBRA:" |
| **client** (5/7) | DADES CAMP i pressupost tenen l'arquitecte, no el promotor | El promotor apareix al planol (caixeti "PROMOTOR:") i a l'ACCEPTACIO. Afinar prioritat: planol_vision > pressupost per a client |
| **adjacents** (18/7) | Cadastre API dona "parcel·la buida/construida" vs Eva descriu amb context | Dos nivells: (a) la dada basica del Cadastre es correcta, (b) la frase descriptiva es template. Generar frases a partir de dades Cadastre |
| **expedient** (1/7) | Linyola confon ref. interna amb expedient | Afinar regex: expedient G3 es sempre 7 digits (4xxxxxx o 3xxxxxx) |
| **plantes** (1/7) | Anciles: "C-1" vs pipeline "SOTANO, PLANTA BAJA..." | Valor Eva incorrecte? C-1 es classificacio CTE, no plantes. Revisar |

### 1.3 Revisio i afinament de format schemas

**Estat actual: 8 formats, possiblement insuficients.**

Auditoria necessaria:
1. Per a cada fitxer de cada projecte: quin format schema el processa?
2. Quins fitxers NO coincideixen amb cap format? (cauen al catch-all `generic_document_v1`)
3. Per als que cauen al catch-all: creen schemas nous o ampliem els existents?

Nous formats candidats:
- `dades_camp_xlsx_v1.yaml` — DADES PER ANAR A CAMP_v1.xlsx (diferent de l'Excel DPSH)
- `pressupost_msg_v1.yaml` — Pressupostos enviats per email (.msg amb adjunts)
- `acceptacio_v1.yaml` — Documents d'acceptacio (ACCEPTACIO/) amb promotor clar
- `comanda_lab_xls_v1.yaml` — Comanda de laboratori (format abreujat, saber que NO es fiable per building_type)

### 1.4 Log de format matching

Crear log que mostri per a cada fitxer processat:
```
4001612 BELL-LLOC:
  25.0647/Pressupost...msg        → format: email_content_v1 (3 labels matched)
  comanda laboratori_4001612.xls  → format: dades_camp_excel_v1 (8 labels matched)
  DADES PER ANAR A CAMP_v1.xlsx  → format: generic_document_v1 (catch-all, 2 labels)
                                    ← CANDIDAT per nou format!
  ANNEXES/4001612_DPSH.xls       → format: dades_camp_excel_v1 (DPSH detected)
```

---

## Objectiu 2: Pipeline complet (vision + calculs)

### 2.1 Executar vision extraction

Per a cada projecte, executar les 3 extraccions vision:
- Planol (A.01.pdf) → architect_name, client, superficies, plantes, building_type
- Sondeig (SONDEIG.pdf) → capes, SPT
- Penetros (PENETROS.pdf) → N20 validacio

Aixo requereix API key d'Anthropic. Verificar que `.env` te `ANTHROPIC_API_KEY`.

Els resultats es guarden a `validation/planol_extracted.json`, `sondeig_extracted.json`, `dpsh_extracted.json`.

### 2.2 Integrar vision al comparison script

Ampliar `compare_eva_vs_pipeline.py` per:
1. Carregar `validation/*_extracted.json` (si existeixen)
2. Mapejar camps de vision → concept_ids
3. Incloure'ls com a candidats addicionals a la comparacio

### 2.3 Executar calculs

Despres d'auto_extract + vision:
- Terzaghi → qa_value, settlement
- CTE → cte_edificacio, cte_sol
- Sismica → seismic_ab_text
- K30 → k30_value

Aixo requereix que el pipeline complet (fins a `build_report_data()`) s'executi.

### 2.4 Ampliar comparison a pipeline complet

L'objectiu final: el comparison script executa TOT el pipeline (auto_extract + vision + calculs) i compara els ~50 variables contra Eva. Aixo donara la foto real de "quant a prop estem".

---

## Ordre d'execucio suggerit

```
1. Crear diagnostic log (1.1)           ← primer, per entendre el problema
2. Auditoria format schemas (1.3-1.4)   ← veure quins fitxers cauen al catch-all
3. Crear nous format schemas (1.3)       ← per als fitxers sense format adequat
4. Afinar prioritats (1.2)              ← canvis al YAML de conceptes
5. Executar vision (2.1)                ← requereix API key
6. Ampliar comparison (2.2-2.4)         ← pipeline complet
7. Re-executar /g3dt-dev-eva-vs-pipeline ← nova foto
```

---

## Metriques objectiu

| Metrica | Avui | Objectiu |
|---------|------|----------|
| Variables comparades | 43/281 | 200+/281 |
| Match exact | 7% | 50%+ |
| Match+Close | 23% | 80%+ |
| NO_DATA | 238 | <50 |
| MISMATCH building_type | 7/7 | 0/7 |
| MISMATCH client | 5/7 | 1/7 |
| MISMATCH adjacents | 18/20 | 5/20 |
