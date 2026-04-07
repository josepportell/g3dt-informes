# Diagnostic Complet: Wizard Prefills vs Eva — 7 Projectes
**Data:** 2026-04-07
**Branca:** `feature/concept-format-separation`
**Context:** Post-ConceptScout, Claude vision (cached), planol normalizer
**Nota:** Anthropic credits esgotats — LLM synthesis no disponible per aquesta execucio

---

## Resum Global

| Projecte | MATCH | CLOSE | MISMATCH | NOT_EXT | Total | Score |
|----------|:-----:|:-----:|:--------:|:-------:|:-----:|:-----:|
| Bell-Lloc | 4 | 3 | 4 | 0 | 11 | **50%** |
| Linyola | 4 | 3 | 3 | 1 | 11 | **50%** |
| Alcoletge | 3 | 2 | 3 | 2 | 10 | **40%** |
| Castellar | 3 | 0 | 3 | 3 | 9 | **33%** |
| Rubi | 2 | 2 | 4 | 2 | 10 | **30%** |
| Vilanova | 1 | 2 | 6 | 1 | 10 | **20%** |
| Anciles | 1 | 1 | 6 | 1 | 9 | **17%** |
| **TOTAL** | **18** | **13** | **29** | **10** | **70** | **35%** |

**Score = (MATCH + 0.5*CLOSE) / TOTAL**

### Comparacio amb diagnostic anterior (nomes auto_extract, sense visio)

| | Sense visio | **Amb visio** | Millora |
|---|---|---|---|
| MATCH | 13 | **18** | +5 |
| CLOSE | 2 | **13** | +11 |
| NOT_EXT | 40 | **10** | **-30** |
| Score | 18% | **35%** | **+17pp** |

La visio (Phase 1) elimina 30 NOT_EXTRACTED i converteix molts en CLOSE o MATCH.

---

## Per Projecte

### 4001612 BELL-LLOC (50%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MATCH | JORDI BOSCH NOVELL | Jordi Bosch Novell | groq_llm:A.01.pdf |
| architect_company | MATCH | ARQUITECTURA BOSCH NOVELL | ARQUITECTURA BOSCH NOVELL | planol A.01.pdf |
| client | CLOSE | RAMON MITJANA S.L | RAMON MITJANA S.L. | fileminer:PDF V0 |
| building_type | CLOSE | un habitatge unifamiliar | habitatge unifamiliar aïllat | planol A.01.pdf |
| plantes | MATCH | Pb+1Pp | Pb+1Pp | planol A.01.pdf |
| superficie_parcela | MATCH | 995 | 995.0 | planol A.01.pdf |
| superficie_construida | MISMATCH | 280+86 | 297 | planol A.01.pdf |
| municipality | CLOSE | Bell-lloc d'Urgell | BELL-LLOC | fileminer:comanda lab |
| expedient | MISMATCH | 4001612 | 4001612_v0 | fileminer:PDF V0 |
| data_camp_text | MISMATCH | 1 d'octubre de 2025 | 1 i 6 d'octubre de 2025 | DPSH/Lab |
| qa_value | MISMATCH | 3.0 | 1.64 | Terzaghi-Peck |

**Observacions:**
- Millor projecte en termes absoluts (te A.01.pdf complet)
- superficie_construida: 297 vs 280+86 — planol extreu total, Eva separa per planta
- qa: Eva posa cap 3.0, pipeline calcula T-P = 1.64 (cal aplicar cap)
- data_camp: pipeline inclou data sondeig (6 oct) + DPSH (1 oct)

---

### 4001607 LINYOLA (50%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | SÍLVIA EROLES BALAGUERÓ | JOSEP BUNYESC PALACÍN | planol Punts de Sondeig |
| architect_company | CLOSE | BUNYESC ARQUITECTURA EFICIENT | BUNYESC ARQUITECTURA EFICIENT, S.L.P | planol |
| client | CLOSE | SRA. SÍLVIA EROLES BALAGUERÓ | SÍLVIA EROLES BALAGUERÓ | planol |
| building_type | CLOSE | un nou habitatge unifamiliar | habitatge unifamiliar aïllat | planol |
| plantes | MATCH | Pb | Pb | planol |
| superficie_parcela | MATCH | 571 | 569.0 | planol |
| superficie_construida | NOT_EXT | 250.91 | — | — |
| municipality | MATCH | Linyola | LINYOLA | fileminer:comanda lab |
| expedient | MISMATCH | 4001607 | 13/52/04 | fileminer (referencia cadastral) |
| data_camp_text | MATCH | 1 d'octubre de 2025 | 1 d'octubre de 2025 | DPSH/Lab |
| qa_value | MISMATCH | 3.0 | 1.30 | Terzaghi-Peck |

**Observacions:**
- architect: Eva diu Sílvia Eroles (client), pipeline diu Josep Bunyesc (arquitecte real?)
- superficie_parcela: 569 vs 571 — excel·lent (0.4% desviacio)
- expedient: agafa referencia cadastral en comptes del numero d'expedient
- qa: mateix problema de cap que Bell-Lloc

---

### 4001670 ALCOLETGE (40%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | ALBERT SANS BONVEHI | DAVID GRAUS ROBINAT | planol A.01.pdf |
| client | CLOSE | SR. ALBERT SANS BONVEHI | ALBERT SANS BONVEHÍ | planol A.01.pdf |
| building_type | MISMATCH | l'ampliació d'un edifici en PB | habitatge unifamiliar | planol A.01.pdf |
| plantes | MATCH | Pb | Pb | planol A.01.pdf |
| superficie_parcela | NOT_EXT | 1167 | — | — |
| superficie_construida | NOT_EXT | 100 | — | — |
| municipality | CLOSE | ...el municipi d'Alcoletge... | ALCOLETGE | fileminer:comanda lab |
| expedient | MATCH | 4001670 | 4001670 | groq_llm:tall.pdf |
| data_camp_text | MATCH | 16 de febrer de 2026 | 16 de febrer de 2026 | DPSH/Lab |
| qa_value | MISMATCH | 3.50 | 0.51 | Terzaghi-Peck |

**Observacions:**
- architect: DAVID GRAUS del caixeti (pot ser correcte — Eva potser posa el client com a nom)
- building_type: "ampliacio" vs "habitatge" — tipologia molt diferent
- qa: 0.51 vs 3.50 — valor T-P molt baix, Eva posa cap professional

---

### 3001621 CASTELLAR DEL VALLES (33%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| client | MISMATCH | WOOD COMFORT PROMOCIONS SLU | GRUP ALMA | fileminer:DADES |
| building_type | MISMATCH | 3 hab. unifamiliars estructura lleugera | habitatge unifamiliar aïllat | planol plà.pdf |
| plantes | NOT_EXT | Pb+1Pp | — | — |
| superficie_parcela | NOT_EXT | 1.284 | — | — |
| superficie_construida | NOT_EXT | 120 m2 | — | — |
| municipality | MATCH | Castellar del Vallès | CASTELLAR DEL VALLÈS | fileminer:comanda lab |
| expedient | MATCH | 3001621 | 3001621 | groq_llm:tall.pdf |
| data_camp_text | MATCH | 24 de octubre de 2025 | 24 d'octubre de 2025 | DPSH/Lab |
| qa_value | MISMATCH | 3.0 | 5.00 | Terzaghi-Peck |

**Observacions:**
- NO te planol d'arquitecte complet → plantes, superficies impossibles
- qa: 5.00 vs 3.0 — pipeline detecta roca i aplica cap roca (4-5), Eva posa 3.0 (sol)

---

### 3001631 RUBI (30%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | JOANA MARTINEZ | SR. | groq_llm:test_validation.docx |
| client | NOT_EXT | SRA. JOANA MARTINEZ | — | — |
| building_type | CLOSE | hab. unifamiliar aïllat modular | habitatge unifamiliar | planol IMG WhatsApp |
| plantes | CLOSE | PB + Porxo | Pb | planol IMG WhatsApp |
| superficie_parcela | NOT_EXT | 951 | — | — |
| superficie_construida | MISMATCH | 92 | 64 | planol IMG WhatsApp |
| municipality | MISMATCH | Rubí (Barcelona) | RUBI | fileminer:comanda lab |
| expedient | MATCH | 3001631 | 3001631 | groq_llm:tall.pdf |
| data_camp_text | MATCH | 14 de novembre de 2025 | 14 de novembre de 2025 | DPSH/Lab |
| qa_value | MISMATCH | 3.50 | 5.00 | Terzaghi-Peck |

**Observacions:**
- architect: "SR." de test_validation.docx (fitxer nostre generat!)
- building_type i plantes extrets de foto WhatsApp cataleg — impressionant
- qa: 5.00 vs 3.50 — pipeline detecta roca

---

### 4001671 VILANOVA DE SEGRIA (20%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | JUAN JOSÉ TORRES POVEDANO | Jordi Carner Rocar | planol 1.0.pdf |
| client | CLOSE | GRUPO CUENCA GUERRERO, S.L | Grupo CUENCA GUERRERO | planol 1.0.pdf |
| building_type | MISMATCH | vivienda unifamiliar aislada | habitatge unifamiliar aïllat | planol 1.0.pdf |
| plantes | MATCH | Pb | Pb | planol 1.0.pdf |
| superficie_parcela | MISMATCH | 100 | 430.0 | planol 1.0.pdf |
| superficie_construida | MISMATCH | 406 | 137 | planol 1.0.pdf |
| municipality | CLOSE | ...Vilanova de Segria... | VILANOVA DE SEGRIÀ | fileminer:comanda lab |
| expedient | MISMATCH | Expediente Núm.: 4001671 | 4001671 | groq_llm:pl situacio |
| data_camp_text | NOT_EXT | El dia 19 de febrero de 2026... | — | — |
| qa_value | MISMATCH | 2.50 Kg/cm2... | 0.88 | Terzaghi-Peck |

**Observacions:**
- Projecte en castella
- building_type: "aislada" (es) vs "aïllat" (ca) — traduccio automatica?
- superficie_parcela: Eva=100, pipeline=430 — Eva te un valor sospitosament baix

---

### 4001679 ANCILES (17%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | ALBA MARIA BARRAU CASTÁN | ALBA BARRAU, MIRIAM CASTEL | planol A01_TIPOL.pdf |
| client | MISMATCH | SRA. ALBA MARIA BARRAU CASTÁN | ANDRÉS AMAT y ENRIQUE M. GARDETA | planol A01_TIPOL.pdf |
| building_type | MATCH | 7 viviendas unifamiliares adosadas | 7 viviendas adosadas | planol A01_TIPOL.pdf |
| plantes | MISMATCH | C-1 | Ps+Pb+Pbc+1Pp | planol A01_TIPOL.pdf |
| superficie_parcela | MISMATCH | T-1 | 1655.01 | groq_llm:IV_PLANOS.pdf |
| municipality | CLOSE | ...Anciles... | ANCILES | fileminer:comanda lab |
| expedient | MISMATCH | Expediente Núm.: 4001679_v0 | 4001679 | groq_llm:pl situ.pdf |
| data_camp_text | NOT_EXT | El dia 19 de febrero de 2026... | — | — |
| qa_value | MISMATCH | 2.0 Kg/cm2... | 1.16 | Terzaghi-Peck |

**Observacions:**
- Projecte en castella
- Eva: plantes="C-1", superficie="T-1" — son CODIS CTE, no valors reals!
- architect/client invertits al planol
- building_type: MATCH (7 viviendas adosadas)

---

## Problemes Recurrents (actualitzats)

### 1. qa_value MISMATCH (7/7 projectes)
**Causa:** Eva aplica un CAP professional (3.0 sol, 4-5 roca). Pipeline calcula Terzaghi-Peck pur sense cap.
**Nota:** El wizard ja mostra "Rang Eva" per comparacio. El cap s'aplica en generacio d'informe.
**Impacte real:** Baix — el cap ja existeix al sistema, es una questio de QUAN s'aplica.

### 2. architect_name = "SR." (2 projectes: Rubi, Linyola)
**Causa:** Groq extreu de `*_test_validation.docx` (documents generats per nosaltres).
**Fix:** Excloure `*_test_validation.docx`, `*_generated.docx` de Groq mining.

### 3. client/architect invertits (Linyola, Alcoletge, Anciles)
**Causa:** El caixeti del planol pot posar client o arquitecte en posicions no estandarditzades.
**Fix:** Validacio creuada + context del nom (empreses vs persones fisiques).

### 4. building_type format curt vs narratiu
**Causa:** Eva: "un habitatge unifamiliar", Pipeline: "habitatge unifamiliar aïllat".
**Nota:** Son CLOSE, no MISMATCH — el significat es correcte, la forma no coincideix exactament.

### 5. expedient: agafa referencies errònies (Linyola)
**Causa:** FileMiner agafa referencia cadastral "13/52/04" d'un PDF de l'arquitecte.
**Fix:** Prioritzar fonts especifiques (tall.pdf, folder_name) sobre contingut generic.

### 6. Projectes en castella (Vilanova, Anciles)
**Causa:** Eva referencies son text narratiu en castella, pipeline extreu valors curts en catala.
**Nota:** Anciles Eva te codis CTE (C-1, T-1) com a "plantes" i "superficie" — error de referencia.

---

## Proxims Passos

| Prioritat | Accio | Impacte esperat |
|:---------:|-------|-----------------|
| 1 | Excloure fitxers generats de Groq mining | +2 MATCH (architect) |
| 2 | Millorar comparacio building_type (CLOSE→MATCH amb fuzzy) | +3-4 MATCH |
| 3 | Aplicar qa cap al diagnostic (ja existeix al report_generator) | +5-7 MATCH |
| 4 | Validacio creuada client/architect | +2-3 MATCH |
| 5 | Prioritzar expedient de tall.pdf/folder_name | +2 MATCH |
| 6 | Suport castella (patrons bilingues) | +3-4 MATCH (Vilanova+Anciles) |
