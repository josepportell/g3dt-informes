# Linyola — diagnòstic de tot el que no és OK contra el signat

**Data:** 2026-09-04 · **Mètode:** JSON del run, `_g3_templates.json`, `_eva_truth/linyola.json`, ors, `consolidate.py`.
Cap re-run. Taxonomia: `../_DIAGNOSTICS-INDEX.md`.

## D2 — bug del consolidador a les dates (l'ERR de `field_date`)

Cadena exacta (`automation/lectura/consolidate.py`):

1. `keys_compatible()` (l. 266): per a `('date', y, m, d)`, «`a[3] is None or b[3] is None or a[3] == b[3]`». Una data
   **sense dia** («Octubre 2025», caixetí del plànol, conf 0,2-0,3) és compatible amb **tots** els dies del mes.
2. `cluster_signals()` (l. 331) usa union-find: la compatibilitat és **transitiva** → 01/10 (fitxa F38 A 0,95, annex
   DPSH A 0,80, PENETROS, comanda, GTL, correu) i 10/10 (lab-sig 0,35, en realitat la data de sol·licitud del lab,
   `comanda!AH23` = 2025-10-10, aparellada a l'etiqueta equivocada pel text en columnes) acaben al **mateix cluster**.
   Sense cluster rival → «1 font A sense contradicció» → **segur**.
3. Clau representant (l. 364): `max(..., key=(té dia, len(str(k))))` → `"('date', 2025, 10, 10)"` té un caràcter més
   que `"('date', 2025, 10, 1)"` → guanya el dia 10 **per longitud de cadena**.
4. `decide()` (l. 502-506): si `segur`, `candidates[0]["value"] = _iso_date(top.key)` → el candidat de la fitxa
   F38 (font i cita `datetime(2025, 10, 1)`) surt amb valor **2025-10-10**.

Fix (després de la mesura): (a) les claus sense dia **no** uneixen clusters de dies diferents (compatibles amb un
cluster, no pont entre dos: tractar-les com a corroboració, no com a aresta); (b) representant = clau amb dia de la
font de més autoritat, mai per longitud; (c) l'ISO només si la clau del candidat 0 té el mateix dia. Test de
regressió amb aquests 3 senyals. **Bell-lloc no ho va patir perquè no tenia cap senyal «Octubre 2025»**; Castellar i
Rubí tampoc. Amb un plànol datat per mes (habitual), qualsevol misread de dia es converteix en «segur».

## Escalars — 10 cel·les no-OK (de 22)

| Camp | Cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `field_date` | ERR → **ERR** | Vegeu D2. Veritat 2025-10-01 (or: 7 fonts). | **D2** |
| `building_type` | CAUTELA → CAND | «Habitatge unifamiliar aïllat» (caixetí A 0,85 + annexos) bloquejat per `EG HAB UNIF LINYOLA` (PLAN_COST, 0,60). **4/4.** | **R1** |
| `architect_name` | CAUTELA → CAND | «Josep Bunyesc Palacín» (caixetí A) vs «BUNYESC ARQUITECTURA EFICIENT, SLP» (pressupost CLIENT, 0,55: despatx) i «Laia Alarcón» (correu, 0,65). Persona/despatx = R1. **El signat escriu el despatx** («Bunyesc Arquitectura Eficient»); l'or diu la persona → or discrepant del signat; la regla «persona si es pot» del skill no és la pràctica d'Eva aquí. | R1 + **G** + pregunta Eva |
| `cota_referencia` | CAUTELA → CAND | Annex DPSH «+245 msnm segons ICGC (−0,15 carrer)» (A 0,8) bloquejat per la z GPS 244,9 (COORDENADES.txt, 0,50). Signat +245,0. Idèntic a Bell-lloc. | **R2** |
| `lab_depth` | CAUTELA → CAND | GTL «1,0-1,15» (A) bloquejat per DPSH.xls «1,0 a 1,5» (0,50) i PENETROS SPT «1,00 a 1,75» (0,55): el full de camp anota el tram previst, el lab la mostra real (rebuig als 15 cm). Signat -1,00 a -1,15. El skill diu «GTL mana». | **F1** (+R2) |
| `lab_location` | CAUTELA → CAND | «P-3» (GTL A) vs «SPT1 P3» (lab-sig 0,75): mateixa cosa, forma composta. | **R1** |
| `referencia_catastral` | CAUTELA → CAND | Una sola font (projecte de l'arquitecte p.1, `5098344CG2159N0000US`), conf < 0,8; l'or l'accepta com a A («el projecte mana»). Sense contradicció. Un creuament amb el Cadastre (adreça → mateixa RC) la confirmaria; el Cadastre no s'ha cridat perquè no era forat (**D1**, l'altra cara). | **R5** (+D1) |
| `superficie_parcela` | CAUTELA → CAND | Mateixa font única, «571 m²»; signat 571 («segons informació aportada»). | **R5** |
| `street_address` | ALERTA → CAND (correcte) | Formes A: «C/ Clot de la Llacuna, 16, Linyola (25240)», «Clot de la Llacuna, 16, Linyola (CP 25240)», «C. Clot de la Llacuna, 16» → «formes diferents entre fonts A» (mateix portal 16, sufixos de municipi/CP). El comparador no les iguala amb l'or (el CP 25240 compta com a portal; «C.» no és via reconeguda). | **R1** + **C** |
| `architect_company` | NOU | Sense or. | — |

**Sobre el signat: 13 OK / 7 CAND / 1 ERR** (21 amb or; el CAND d'`architect_name` conté el despatx del signat).

## Taules — 9 cel·les no-OK (de 25)

| Cel·la | Cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `soil_levels[0].de` / `[0].a` / `[1].de` | ALERTA/CAUTELA → CAND | Prod expressa els contactes en **msnm** llegits de l'escala del tall («≈243,6 msnm a P-1/P-3; ≈244,6-244,7 a P-2»); or i informe en **fondària** («~-1,4 m a P-1; ~-0,2/-0,25 a P-2»). 245 − 1,4 = 243,6: mateixos valors, sistema diferent. La cel·la de l'informe és fondària → cal convertir amb la cota d'inici. | **R2** (sistema de referència) + **C** |
| `soil_levels[0].litologia` | CAUTELA → CAND | «Llims argil**soso** i sorrencs» és l'errata del tall d'Eva (2 lectors la transcriuen igual); signat «argilosos». | **F1** (lleu) + C |
| `spt_ma_tests[0].n30` | BUIT | Or: «R (rebuig; 50 cops al primer tram de 15 cm)» del full SPT manuscrit (PENETROS p.3); cap lector emet `n30` d'aquest full (lab-sig/GTL/annex DPSH no el porten). Signat N30 = R. Blanc honest, però és un forat de lector. | **L1** (lector) |
| `spt_ma_tests[0].id` | CAUTELA → CAND | «SPT1 P3» / «SPT1» / «SPT-1»: formes. | R1 |
| `soil_levels[1].a`, `mostra_del_nivell` ×2 | BUIT | Derivats («fins al fons d'investigació»; mostra ↔ nivell pel material): el consolidador no els deriva. Blancs honestos. | conegut |

**Sobre el signat: 16 OK / 0 ERR / 4 blancs / 3-4 CAND.**

## Què aporta Linyola al quadre dels 8

1. **Primer ERR de codi** (D2): un bug de clustering de dates que converteix una lectura de conf 0,35 en «segur» quan
   hi ha un plànol datat només per mes. Afecta potencialment qualsevol projecte amb caixetí «Mes Any»; cal test.
2. **R1 4/4, R2 (z GPS) 2/2 dels projectes amb COORDENADES.txt i annex, R5 «una sola font A del proveïdor»**: la
   regla de l'or «el projecte de l'arquitecte mana» no existeix al consolidador (Bell-lloc també: `num_soil_levels`).
3. **Persona vs despatx a `architect_name`**: el signat de Linyola escriu el despatx; el skill diu «persona si es pot».
   Pregunta a Eva abans de tocar R1 en aquest camp.
4. **Sistema de referència als nivells**: quan el tall porta escala en msnm, el lector la copia; l'informe vol
   fondàries. Conversió determinista amb `cota_inici` (ja segura al mateix `_decisions.json`).
5. **L1**: el full SPT manuscrit no aporta `n30`. Amb «n30 mai segur» (VIOLACIO), un candidat «R (50 cops)» amb
   font seria millor que el blanc.
