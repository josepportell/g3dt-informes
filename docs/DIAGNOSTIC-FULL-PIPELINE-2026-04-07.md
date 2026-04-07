# Diagnostic Complet: Pipeline vs Eva — 7 Projectes
**Data:** 2026-04-07
**Branca:** `feature/concept-format-separation`
**Context:** Post-ConceptScout (Phases A-D), Claude default vision, planol normalizer

---

## Resum Global

| Projecte | MATCH | CLOSE | MISMATCH | NOT_EXT | Total | Score |
|----------|:-----:|:-----:|:--------:|:-------:|:-----:|:-----:|
| Bell-Lloc | 4 | 1 | 4 | 3 | 12 | **38%** |
| Castellar | 3 | 0 | 1 | 6 | 10 | **30%** |
| Alcoletge | 3 | 0 | 3 | 5 | 11 | **27%** |
| Rubi | 2 | 0 | 2 | 7 | 11 | **18%** |
| Linyola | 1 | 0 | 4 | 7 | 12 | **8%** |
| Anciles | 0 | 1 | 5 | 4 | 10 | **5%** |
| Vilanova | 0 | 0 | 3 | 8 | 11 | **0%** |
| **TOTAL** | **13** | **2** | **22** | **40** | **77** | **18%** |

**Nota:** Aquesta comparacio nomes cobreix ~12 variables clau (no les 53 del sistema). qa_value, settlement, municipality falten sovint perque es calculen o son text narratiu.

---

## Per Projecte: Detall

### 4001612 BELL-LLOC (38% — millor projecte)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MATCH | JORDI BOSCH NOVELL | Jordi Bosch Novell | groq_llm:A.01.pdf |
| architect_company | MATCH | ARQUITECTURA BOSCH NOVELL | ARQUITECTURA BOSCH NOVELL | pressupost |
| client | CLOSE | RAMON MITJANA S.L | RAMON MITJANA S.L. | fileminer:PDF V0 |
| building_type | MISMATCH | un habitatge unifamiliar | Bell-lloc - CL MESTRE RAMON ORTIZ 15 | fileminer:Pressupost |
| plantes | MATCH | Pb+1Pp | Pb+1Pp | groq_llm:PDF V0 |
| superficie_parcela | MATCH | 995 | 995 | groq_llm:PDF V0 |
| superficie_construida | MISMATCH | 280+86 | 24.72 | groq_llm:A.01.pdf |
| municipality | NOT_EXT | Bell-lloc d'Urgell | — | — |
| expedient | MISMATCH | 4001612 | 4001612_v0 | fileminer:PDF V0 |
| data_camp_text | MISMATCH | 1 d'octubre de 2025 | 1 i 6 d'octubre de 2025 | DPSH/Lab |
| qa_value | NOT_EXT | 3.0 | — | — |
| settlement | NOT_EXT | (text narratiu) | — | — |

**Analisi:**
- Millor projecte perque te A.01.pdf complet (planol d'arquitecte amb caixeti + taula JUSTIFICACIO)
- building_type: FileMiner agafa adreça en comptes de tipologia (competicio de senyals errònia)
- superficie_construida: Groq extreu 24.72 (% ocupacio) en comptes de 280+86 (m2 per planta)
- data_camp_text: pipeline inclou data del sondeig (6 oct), Eva nomes la del DPSH (1 oct)
- municipality: no s'extreu del pipeline malgrat existir a la comanda lab

---

### 3001621 CASTELLAR DEL VALLES (30%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| client | MISMATCH | WOOD COMFORT PROMOCIONS SLU | GRUP ALMA | fileminer:DADES |
| building_type | MATCH | 3 habitatges unifamiliars... | CONSTR 3 HAB UNIF | fileminer:comanda |
| plantes | NOT_EXT | Pb+1Pp | — | — |
| superficie_parcela | NOT_EXT | 1.284 | — | — |
| superficie_construida | NOT_EXT | 120 m2 | — | — |
| municipality | NOT_EXT | Castellar del Vallès | — | — |
| expedient | MATCH | 3001621 | 3001621 | groq_llm:tall.pdf |
| data_camp_text | MATCH | 24 de octubre de 2025 | 24 d'octubre de 2025 | DPSH/Lab |
| qa_value | NOT_EXT | 3.0 | — | — |
| settlement | NOT_EXT | (text) | — | — |

**Analisi:**
- NO te planol d'arquitecte → plantes, superficies, alcada impossibles sense visio
- client: "GRUP ALMA" es un intermediari? Eva te "WOOD COMFORT PROMOCIONS SLU"
- municipality: existeix a la comanda lab pero no s'extreu com a prefill

---

### 3001631 RUBI (18%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | JOANA MARTINEZ | SR. | groq_llm:test_validation.docx |
| client | NOT_EXT | SRA. JOANA MARTINEZ | — | — |
| building_type | MISMATCH | un habitatge unifamiliar aïllat modular | CONSTR HABITATGE UNI | fileminer:comanda |
| plantes | NOT_EXT | PB + Porxo | — | — |
| superficie_parcela | NOT_EXT | 951 | — | — |
| superficie_construida | NOT_EXT | 92 | — | — |
| municipality | NOT_EXT | Rubí (Barcelona) | — | — |
| expedient | MATCH | 3001631 | 3001631 | groq_llm:tall.pdf |
| data_camp_text | MATCH | 14 de novembre de 2025 | 14 de novembre de 2025 | DPSH/Lab |
| qa_value | NOT_EXT | 3.50 | — | — |
| settlement | NOT_EXT | 1.50 | — | — |

**Analisi:**
- architect_name="SR." — Groq extreu del nostre test_validation.docx (generat, no real!)
- Planol es una foto WhatsApp de cataleg modular → sense caixeti ni taula
- En wizard (amb visio), va trobar building_type i plantes de la foto WhatsApp
- client = architect (Joana Martinez es ambdos)

---

### 4001607 LINYOLA (8%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | SÍLVIA EROLES BALAGUERÓ | SR. | groq_llm:test_validation |
| architect_company | NOT_EXT | BUNYESC ARQUITECTURA EFICIENT | — | — |
| client | MISMATCH | SRA. SÍLVIA EROLES BALAGUERÓ | BUNYESC ARQUITECTURA EFICIENT, SLP | fileminer:DADES |
| building_type | MISMATCH | un nou habitatge unifamiliar | CONSTR HABITATGE | fileminer:comanda |
| plantes | NOT_EXT | Pb | — | — |
| superficie_parcela | NOT_EXT | 571 | — | — |
| superficie_construida | NOT_EXT | 250.91 | — | — |
| municipality | NOT_EXT | Linyola | — | — |
| expedient | MISMATCH | 4001607 | 13/52/04 | fileminer:2_02B_DG |
| data_camp_text | MATCH | 1 d'octubre de 2025 | 1 d'octubre de 2025 | DPSH/Lab |
| qa_value | NOT_EXT | 3.0 | — | — |
| settlement | NOT_EXT | (text) | — | — |

**Analisi:**
- architect_name="SR." — mateix problema que Rubi (test_validation.docx)
- client/architect invertits: DADES PER ANAR A CAMP te l'empresa arq. al camp client
- En wizard (amb visio), va trobar architect, empresa, parcela, building_type correctes!
- expedient: FileMiner agafa referencia cadastral "13/52/04" d'un PDF de l'arquitecte

---

### 4001670 ALCOLETGE (27%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | ALBERT SANS BONVEHI | DAVID GRAUS ROBINAT | groq_llm:generated |
| client | MISMATCH | SR. ALBERT SANS BONVEHI | ALBERT SANS BONVEHI tel. 675639431 | fileminer:email |
| building_type | MISMATCH | l'ampliació d'un edifici en PB | CARRER GIRASOLS 7, URBANITZACIO... | fileminer:email |
| plantes | MATCH | Pb | PB | groq_llm:generated |
| superficie_parcela | NOT_EXT | 1167 | — | — |
| superficie_construida | NOT_EXT | 100 | — | — |
| municipality | NOT_EXT | Alcoletge | — | — |
| expedient | MATCH | 4001670 | 4001670 | groq_llm:tall.pdf |
| data_camp_text | MATCH | 16 de febrer de 2026 | 16 de febrer de 2026 | DPSH/Lab |
| qa_value | NOT_EXT | 3.50 | — | — |
| settlement | NOT_EXT | (text) | — | — |

**Analisi:**
- client/architect confusio: ALBERT SANS es el client (Eva), pero pipeline el confon amb arquitecte
- building_type: agafa adreça del email en comptes de tipologia
- Te A.01.pdf pero la visio anterior pot no ser optima (cached)

---

### 4001671 VILANOVA DE SEGRIA (0%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | JUAN JOSÉ TORRES POVEDANO | jordi carner | groq_llm:1.0.pdf |
| client | NOT_EXT | GRUPO CUENCA GUERRERO, S.L | — | — |
| building_type | MISMATCH | una vivienda unifamiliar aislada | CONSTR HAB UNIF | fileminer:comanda |
| plantes | NOT_EXT | Pb | — | — |
| superficie_parcela | NOT_EXT | 100 | — | — |
| superficie_construida | NOT_EXT | 406 | — | — |
| municipality | NOT_EXT | Vilanova de Segria | — | — |
| expedient | MISMATCH | 4001671 | 4001671 | groq_llm:pl situacio |
| data_camp_text | NOT_EXT | 19 de febrero de 2026 | — | — |
| qa_value | NOT_EXT | 2.50 Kg/cm2 | — | — |
| settlement | NOT_EXT | (text) | — | — |

**Analisi:**
- Projecte en castella (no catala) → molts patrons de text no coincideixen
- 1.0.pdf pot ser el planol d'arquitecte (no verificat — GAP al inventari)
- "jordi carner" com a arquitecte es incorrecte
- Necessita revisio manual del contingut de 1.0.pdf

---

### 4001679 ANCILES (5%)

| Variable | Status | Eva | Pipeline | Font |
|----------|:------:|-----|----------|------|
| architect_name | MISMATCH | ALBA MARIA BARRAU CASTÁN | ANDRÉS AMAT y ENRIQUE M. GARDETA | groq_llm:A01_TIPOL |
| client | CLOSE | SRA. ALBA MARIA BARRAU CASTÁN | MARIA ALBA BARRAU CASTÁN 616523792 | fileminer:DADES |
| building_type | MISMATCH | 7 viviendas unifamiliares adosadas | CONSTR GRUPO DE VIVIENDAS | fileminer:comanda |
| plantes | MISMATCH | C-1 | SÓTANO, PLANTA BAJA y PLANTA 1 | fileminer:Presupuesto |
| superficie_parcela | MISMATCH | T-1 | 1655.01 | groq_llm:IV_PLANOS |
| municipality | NOT_EXT | Anciles | — | — |
| expedient | MISMATCH | 4001679_v0 | 4001679 | groq_llm:pl situ |
| data_camp_text | NOT_EXT | 19 de febrero de 2026 | — | — |
| qa_value | NOT_EXT | 2.0 Kg/cm2 | — | — |
| settlement | NOT_EXT | (text) | — | — |

**Analisi:**
- Projecte en castella
- architect: ANDRÉS AMAT es l'arquitecte del planol (correcte?), Eva diu ALBA MARIA (client?)
- A01_TIPOL.pdf esta en subcarpeta 24.0807/ — SmartScan el va trobar via Groq Tier 3
- Eva: plantes="C-1" (codi CTE), pipeline: text descriptiu — formats incompatibles
- Eva: superficie_parcela="T-1" (codi CTE), pipeline: 1655.01 m2 — Eva te codi, no area

---

## Problemes Recurrents

### 1. architect_name = "SR." (3 projectes)
**Causa:** Groq extreu de `*_test_validation.docx` (documents generats per nosaltres amb placeholder "SR.").
**Fix:** Excloure `*_test_validation.docx`, `*_generated.docx` de Groq mining.

### 2. building_type agafa adreça o codi lab (5 projectes)
**Causa:** FileMiner extreu de comanda_laboratori un codi curt ("CONSTR HAB UNIF") que coincideix amb patrons de building_type pero es una descripcio de la comanda, no la tipologia real.
**Fix:** Baixar prioritat de `comanda_lab_excel` per a `building_type`, o filtrar codis curts.

### 3. municipality NOT_EXTRACTED (6 projectes)
**Causa:** `site_municipality` no es el mateix que `municipality` en la comparacio.
**Possible:** Error de mapping en el diagnostic, no error real del pipeline.

### 4. client/architect invertits (Linyola, Alcoletge)
**Causa:** DADES PER ANAR A CAMP.xlsx te el camp "client" que de vegades es l'empresa d'arquitectura.
**Fix:** Validacio creuada: si client_name conté "ARQUITECTURA", "SLP", "ENGINYERIA" → probablement es architect_company.

### 5. qa_value / settlement NOT_EXTRACTED (tots)
**Causa:** Són valors CALCULATS pel pipeline (Terzaghi, Schmertmann), no extrets de documents. El diagnostic no mesura valors calculats.
**Fix:** Afegir comparacio de valors calculats (qa, settlement, K30, phi, E) al diagnostic.

### 6. Projectes en castella (Vilanova, Anciles)
**Causa:** Molts patrons regex i prompts estan en catala. Documents en castella no coincideixen.
**Fix:** Ampliar patrons bilingues als miners i prompts de visio.

---

## Proxims Passos Prioritzats

1. **Excloure fitxers generats** de Groq mining (fix "SR." en 3 projectes)
2. **Afegir valors calculats** al diagnostic (qa, settlement, K30 — comparen formula, no text)
3. **Revisar mapping municipality** (possible error al diagnostic, no al pipeline)
4. **Millorar building_type** (filtrar codis lab, preferir visio/LLM sobre fileminer)
5. **Validacio creuada client/architect** (detectar empreses al camp client)
6. **Suport castella** (ampliar patrons bilingues — afecta Vilanova + Anciles)
