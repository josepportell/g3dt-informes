# Rubí — diagnòstic de tot el que no és OK (escalars + taules) contra el signat

**Data:** 2026-09-04 · **Mètode:** lectura dels JSON del run (`tier_a` per doc, `_g3_templates.json`, `_decisions.json`),
`_eva_truth/rubi.json` (signat), or de lectura i de taules, i `consolidate.py`. Cap re-run. Taxonomia: la de
Bell-lloc (`../bell-lloc/_DIAGNOSTIC-INFRACONFIANCA.md`, R1-R5) + codis nous **F** (font d'Eva inconsistent),
**D** (defecte de codi fora del consolidador), **C** (comparador), **G** (or). Índex dels 8: `../_DIAGNOSTICS-INDEX.md`.

## Escalars — 11 cel·les no-OK (de 22)

| Camp | Veredicte cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `building_type` | CAUTELA → CAND | 3 docs «habitatge unifamiliar aïllat» (annex pl. situació A 0,80) bloquejats per les abreviatures G3 `CONSTR HABITATGE UNI` (comanda, 0,70) i `EG HAB UNIF RUBI` (PLAN_COST, 0,60), més «casa modular» (correu, 0,55). **Mateixa causa que Castellar i Bell-lloc: 3/3.** | **R1** |
| `cte_edificacio` / `cte_sol` | CAUTELA → CAND | Pressupost p.2 imprimeix «C0 / T1» (0,80); signat C-0 / T-1. `_NEVER_SEGUR_FIELDS`. | **R4** |
| `lab_depth` | CAUTELA → CAND | GTL ×2 (A 0,90) + PENETROS (0,85) + annex DPSH (0,75) diuen **0,6-1,2**; la **comanda de laboratori** (J35/L35) diu `INICIAL 0.6 / FINAL 1.4` (0,70) i bloqueja. Signat: -0,60 a -1,20. La comanda és d'Eva → **inconsistència interna**; el propi senyal G3 porta la nota «el GTL mana si discrepa» i el consolidador no la llegeix (mateix patró que R2). | **F1** (+R2) |
| `client_name` | CAUTELA → CAND | Única A possible és la foto WhatsApp del formulari d'acceptació signat (0,75 < 0,80); el pressupost G3 el marca «sol·licitant, no autoritat» (0,30); correus 0,3-0,5. Sense `DADES CLIENT.txt`. Lector humil davant d'una imatge: CAND legítim. | **R5** |
| `num_floors` | CAUTELA «disjunts» → CAND | Una sola font (plànol de catàleg adjunt al correu, 0,40, «derivat estructuralment»): CAND legítim. El «candidats disjunts» és del comparador: or «1 (planta baixa)» vs prod «PB + porxada» — el signat diu «PB + Porxo» → `norm_floors` no entén porxada/porxo. | **C** |
| `street_address` | CAUTELA → CAND | Formes A: «Carrer de la Miranda, 39» (0,80), «C/ DE LA MIRANDA» (0,80), «Carrer de la Miranda» (0,80) + «Moranda» (albarà cursiva, 0,30). «Formes diferents entre fonts A»: amb/sense portal no és la mateixa lectura (regla del comparador també). El Cadastre l'ha resolt bé (39 → 951 m² = signat). CAND per disseny. | R1 (eix via, correcte) |
| `architect_name` | ALERTA → CAND | Or: no_trobat («casa modular sense arquitecte»). Prod: [client «Joana Martínez» (pràctica Eva, 0,25-0,30), «Albert Coll» (receptor de l'informe, 0,20)]. Candidats derivats, mai segur. Què escriu el signat? `eva_reference_values` no ho té → **pregunta a Eva** (el skill diu que a Rubí hi escriu el client). | — |
| `referencia_catastral` | ALERTA → CAND | Prod: «Polígon 6, Parcel·la 105-B» ×3 formes (plànol situació, tall), que la pròpia nota qualifica de «no la RC de 20 caràcters». La **RC real 8259027DF1985N el sistema la té** (font de `superficie_parcela`) i no l'ofereix: `consolidate.py` ~1788 només crida el Cadastre «als forats» (`if not sigs`), i un valor del tipus equivocat tapa el forat. Fix: gate per «cap senyal amb format de RC vàlid» (14/20 caràcters), no per «cap senyal». | **D1** |
| `superficie_parcela` | ALERTA → **OK fora** | Prod 951 (Cadastre 39 = 8259027DF1985N). Signat: 951. L'or és no_trobat **sense** `fora_carpeta` (Castellar sí que en porta) → el comparador no pot dir FORA. Corregir l'or. | **G** |
| `num_soil_levels` | ALERTA → **OK** | Prod segur 1 (annex tall, A). Signat: 1 nivell. L'or tenia candidats [1, 2] per l'esborrany `ANNEXES/Altres/F5 TALL.png` (N2 gresos). Prod no ha llegit l'esborrany com a font → encerta. | G (or més cautelós que el signat) |
| `architect_company` | NOU | Sense or. | — |

**Tall sobre el signat: 12 OK / 9 CAND / 0 ERR** (21 amb or).

## Taules — 9 cel·les no-OK (de 23)

| Cel·la | Veredicte cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `dpsh_tests[P-2].cota_inici` | ALERTA → **ERR** | Prod segur «+212 msnm, segons el plànol del ICGC» = literal de l'annex DPSH **p.2**. Signat: **+212,50** als 3 punts (p.1 i p.3 de l'annex també +212,50). Annex d'Eva inconsistent amb el seu informe. El sistema ha estat fidel al document i s'ha equivocat respecte al signat. Regla candidata (consolidador, taules): cotes d'inici diferents entre punts del mateix document, diferència < 1 m i superfície uniforme al tall → candidats [pròpia, la dels altres punts]. | **F1** |
| `dpsh_tests[P-1/P-3].cota_inici` | ALERTA → OK | Prod segur +212,50 = signat. L'or era candidats per l'esborrany F5 (+211,90 / +211,40). El «valor fora dels candidats d'or» de P-3 és un **fals negatiu de `close()`** («segons plànol en el ICGC» vs «segons plànol de l'ICGC»: `parse_numbers` retorna None per les paraules, i la via de text no iguala «en el» / «de l'»). | **C** |
| `soil_levels[cobertura].de` | ALERTA → OK | Prod segur «0,00» = or «0 (superfície)». Més confiat, mateix valor. | — |
| `soil_levels[2on nivell]` (2 cel·les) | ABSENT → OK | Fila només a l'esborrany F5; el signat té 1 nivell. Prod fa bé de no crear-la. | G |
| `soil_levels[1er].de/.a`, `[cobertura].a` | BUIT ×3 → blanc | El tall és gràfic (or: «lectura gràfica ~-0,3»); sense sondeig, el sistema no llegeix fondàries del dibuix. Blanc honest. Cas obert de la capa vegetal (`project_soil_levels_gold_vs_pas3b_open`). | conegut |

**Tall sobre el signat: 17 OK / 1 ERR / 3 blancs.** L'ERR és de causa **font** (F1), no de lectura ni de política.

## Què aporta Rubí al quadre dels 8

1. **R1 és sistemàtic (3/3)** i sempre pel mateix parell de cel·les G3 (`comanda!N18`, `PLAN_COST!E9`): expandir
   `EG HAB UNIF` / `CONSTR HABITATGE (UNI)` a tokens de `building_type` tanca el cas als 3 projectes.
2. **F1, nou:** Eva és inconsistent amb ella mateixa dins la carpeta (comanda 1,4 vs 1,2; annex p.2 +212 vs +212,50).
   Quan la discrepància és entre un document «de tràmit» (comanda) i el d'autoritat (GTL), el skill ja diu qui mana i
   n'hi ha prou que el consolidador ho apliqui. Quan és dins del mateix annex (cota P-2), cal una regla de
   coherència entre files. Cap de les dues es pot aplicar sense mirar els altres 5 projectes.
3. **D1, nou:** el Cadastre com a «font de forat» falla quan el forat és ple d'un valor del tipus equivocat.
4. **Or:** Rubí té 2 cel·les on l'or és més cautelós que el signat (esborrany F5) i 1 sense `fora_carpeta`.
   Cap error de l'or, però cal contrastar sempre amb `_eva_truth` abans de comptar ALERTA com a ERR.
