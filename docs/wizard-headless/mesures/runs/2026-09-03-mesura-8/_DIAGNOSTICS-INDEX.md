# Mesura dels 8 — índex de diagnòstics per projecte (per contrastar-los quan els 8 estiguin fets)

Criteris: `../../CRITERIS-MESURA-2026-09-03.md`. Cada projecte té `_NOTES.md` (números i veredicte) i, quan s'ha fet,
un diagnòstic de causes arrel de tot el que no és OK. **Sempre contrastar els ALERTA/CAUTELA amb el signat**
(`docs/golden-read-taules/_eva_truth/{slug}.json`) abans de comptar-los: l'or de lectura pot ser més cautelós
(esborranys) o menys anotat (`fora_carpeta`) que la veritat.

## Taxonomia de causes (creix amb cada projecte)

| Codi | Causa | On es corregeix |
|---|---|---|
| **R1** | Mateixa entitat, formes diferents, tractades com a contradicció (abreviatures G3, persona/despatx, raó social curta/llarga, grafies de municipi) | `consolidate.value_key` / `cluster_signals` |
| **R2** | Un concepte veí entra com a bloquejador (data del sondeig a `field_date`, datum relatiu / z GPS a `cota_referencia`) | `decide()` per camp; les notes del lector ja ho diuen |
| **R3** | Guard `"1 de"` de `num_floors` per substring («P1 de 86 m2») | `_guard_for_field.num_floors` (regex) |
| **R4** | `_NEVER_SEGUR_FIELDS` (`cte_*`) aplicat també quan el pressupost imprimeix la línia CTE | `consolidate.py:82` + pregunta a Eva (T del pressupost = T de l'informe?) |
| **R5** | Convergència inassolible amb lectors humils (5 docs coincidents, cap ≥ 0,8, 2 ≥ 0,6) | llindars `CONV_*` / autoritat del tall per nivells |
| **F1** | Font d'Eva inconsistent amb ella mateixa (comanda 1,4 vs GTL 1,2; annex p.2 +212 vs +212,50) | regla «qui mana» del skill al consolidador; coherència entre files |
| **D1** | Cadastre només «als forats»: un valor del tipus equivocat (Polígon/Parcel·la) tapa el forat de la RC; i a l'inrevés, una RC declarada d'una sola font no es creua amb el Cadastre | `consolidate.py` ~1788 (gate per format de RC) |
| **D2** | **Bug de dates al consolidador**: una data sense dia («Octubre 2025») fa de pont transitiu entre dies diferents (`keys_compatible` + union-find), el representant es tria per `len(str(k))` i `_iso_date` sobreescriu el valor del candidat 0 → una lectura de conf 0,35 surt «segur» (Linyola `field_date` 10/10 per 01/10) | `consolidate.py` l. 266-275, 364, 502-506 |
| **R6** | Taules: l'absència als docs A (columna N.F. buida → «No detectat») guanya l'evidència positiva d'un doc no-A (tall «Aigua», full de camp «Humit») perquè a les cel·les de taula només bloquegen els A (Vilanova P-3, ERR) | `decide(table_cell=True)`: senyal positiu de `nivell_freatic` bloqueja |
| **D3** | **Forma visible del municipi triada per `len(v)`** (`_prefer_form`) en lloc de la grafia oficial del padró que `municipis.lookup` ja retorna: «Vilanova **del** Segrià» segur (Vilanova, ERR). Família de D2 | `consolidate._prefer_form` / `decide` per a `municipality` |
| **D4** | Runner: 3 docs perduts (rc=1 als 2 intents, tall de xarxa) i consolida amb 11/14 → `degraded=False`, `decisions=OK`. El flag només mira la consolidació LLM | `runner.py` (`degraded` / `docs_failed`) |
| **I1** | Inventari: `PDF_V0/` s'exclou com a «versió anterior» encara que sigui l'ÚNICA carpeta d'annexos (Anciles: sense `PDF/`, `.FH11` il·legible) → 9 cotes en blanc | `inventory.py` l. 12-17/150 (llegir `PDF_V0` si no hi ha `PDF/`) |
| **D5** | Derivació CTE amb la superfície d'UNA tipologia (186 m²) en lloc del total de N unitats (1.264 m²) → «C0» per «C1» (Anciles) | `derived_field_signals` / `_superficie_construida` (factor N unitats) |
| **D6** | Runner: `X.dwg` i `X.pdf` (mateix stem) → mateix JSON; una lectura sobreescriu l'altra (Tulipa, 317 s + 1,25 USD; «lectura fallida») | `runner.py` l. 112 (nom amb extensió) |
| **T2** | Latència: passada LLM de consolidació de 523 s (28 % del run) per 6 conflictes A-vs-A, 3 aplicats (Tulipa) | `consolidate` (abast de `llm_only_fields`) |
| **S1** | Estructura: expedient multi-casa (Tulipa) consolidat com UN projecte; la casa 2 queda en contradiccions; 2 de 4 DPSH | disseny (or per casa ja existeix) |
| **L1** | Forat de lector: el full SPT manuscrit (PENETROS p.3) no emet `n30` | skill / lector de PENETROS |
| **L3** | Brossa dins del valor: telèfon enganxat a `client_name` (fitxa C6), N30 «2» en una MA (signat «--») | skill / normalitzadors |
| **L2** | Manuscrit il·legible → candidat honest «[il·legible] marró» (comportament desitjat; falta el derivat «litologia del nivell de la mostra») | derivats del consolidador |
| **T1** | Operació: `claude -p` penjat sense cap stdout fins al timeout de 600 s (PENETROS, Alcoletge); reintent OK. PENETROS és el doc més lent (382-511 s) | `runner.py` (detecció de penjada / topall per doc) |
| **C** | Comparador: `close()` text («en el» vs «de l'»), `norm_floors` (porxada/porxo), candidats de `cte` compartits entre subclaus, **`parse_address`: CP com a portal, «C.» no reconegut, sufix d'urbanització dins la via (3 falsos ERR/ALERTA d'adreça a Linyola i Alcoletge)**, textos llargs de `nivell_freatic` | `compare_consolida.py` — **arreglar abans d'agregar** |
| **G** | Or: sense `fora_carpeta` (Rubí superfície), utm S-1 en lloc de P-1 (Castellar, corregit), candidats per esborranys (Rubí) | `docs/golden-read*/` |

## Projectes

| # | Projecte | Notes | Diagnòstic | ERR sistema | Causes vistes |
|---|---|---|---|---|---|
| 1 | Castellar | `castellar/_NOTES.md` | — (14/5/2/1; els 5 CAUTELA classificats només per la `rule`, sense doc propi) | 0 | R1 ×2 (`building_type` abreviatures G3; `street_address` formes amb/sense municipi, mateixos portals), R5 (`num_floors`: 1 sola font, pressupost), F1 (`lab_sample_id`: annex «SPT-1» vs GTL «MA1 S1»; or = MA-1), C (`cte_sol`: or nul, candidats compartits), G (utm S-1→P-1, corregit) |
| 2 | Bell-lloc | `bell-lloc/_NOTES.md` | `bell-lloc/_DIAGNOSTIC-INFRACONFIANCA.md` | 0 | R1 ×4, R2 ×2, R3, R4 ×2, R5 |
| 3 | Rubí | `rubi/_NOTES.md` | `rubi/_DIAGNOSTIC.md` | **1** (cota P-2, F1) | R1, R4 ×2, R5, F1 ×2, D1, C ×2, G ×2 |
| 4 | Linyola | `linyola/_NOTES.md` | `linyola/_DIAGNOSTIC.md` | **1** (`field_date`, **D2 bug**) | D2, R1 ×4 (`building_type`, `architect_name` persona/despatx, `lab_location`, `street_address`), R2 ×2 (z GPS a cota; msnm vs fondària als nivells), R5 ×2 (RC i superfície del projecte de l'arquitecte, font única), F1 ×2 (`lab_depth` camp vs lab; errata «argilsoso»), C ×3, G (or persona vs signat despatx), L1 (`n30`) |
| 5 | Alcoletge | `alcoletge/_NOTES.md` | `alcoletge/_DIAGNOSTIC.md` | 0 (l'ERR cru d'adreça és C: Cadastre 1167 = signat) | R1 (`building_type`), R2 ×2 (z GPS anòmala 198,9; msnm vs fondària), R4 ×2, R5 (RC del correu, font única; Cadastre la confirma i no es creua), G (`fora_carpeta`), C ×3 (adreça, `nivell_freatic`, nivells), L2, T1 (timeout 600 s PENETROS) |
| 6 | Vilanova | `vilanova/_NOTES.md` | `vilanova/_DIAGNOSTIC.md` | **2** (`municipality` **D3**; `nivell_freatic` P-3 **R6**) | D3, R6, D4 (11/14 docs i `degraded=False`), R1 ×2 (client, adreça), R4 ×2, R5, F1 ×2 (**SPT P-1/P-3 creuats al signat vs annex+tall**; litologia N2 re-redactada), G (`fora_carpeta` 406), C ×4 (SPT alineació per índex, `profunditat` sense espais, `lab`/`nom` dialecte). Entra al titular des d'avui (signat `.docx` trobat, castellà) |
| 7 | Anciles | `anciles/_NOTES.md` | `anciles/_DIAGNOSTIC.md` | 0 | **I1 (9 cotes en blanc)**, D5 (CTE C0 per C1), R1 (`building_type`, 7/7), R5 ×12 (projecte de l'arquitecte ×3; sondeigs/SPT manuscrits ×9), L3 ×2, C ×5 (ca/es, formats, `lab` compartit, 7 columnes del fixture) |
| 8 | Tulipa | `tulipa/_NOTES.md` | `tulipa/_DIAGNOSTIC.md` | n/a (sense veritat) | executable (43,5 min, 0 reintents), **S1** multi-casa no modelat, **T2** LLM 12 min, **D6** dwg/pdf col·lisió, R1 (8/8), R4 |

## Recompte transversal (actualitzar a cada projecte)

| Causa | Castellar | Bell-lloc | Rubí | Linyola | Alcoletge | Vilanova | Anciles | Total |
|---|---|---|---|---|---|---|---|---|
| R1 | 2 | 4 | 1 (+1 eix via, per disseny) | 4 | 1 | 2 | 1 | 15 |
| R2 | 0 | 2 | 0 | 2 | 2 | 0 | 0 | 6 |
| R3 | 0 (legítim) | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| R4 | 0 (derivat) | 2 | 2 | 0 (sense línia CTE) | 2 | 2 | 1 (derivat) | 9 |
| R5 | 1 | 1 | 1 | 2 | 1 | 1 | 12 | 19 |
| R6 | 0 | 0 | 0 | 0 | 0 | **1 (ERR)** | 0 | 1 |
| F1 | 1 | 0 | 2 | 2 | 0 | 2 (SPT creuat!) | 0 | 7 |
| D1 | 0 | 0 | 1 | (1, cara inversa) | (1, cara inversa) | 0 | 0 | 1 (+2) |
| D2 | 0 | 0 | 0 | **1 (ERR)** | 0 | 0 | 0 | 1 |
| D3 | 0 | 0 | 0 | 0 | 0 | **1 (ERR)** | 0 | 1 |
| D4 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| D5 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| I1 (blancs) | 0 | 0 | 0 | 0 | 0 | 0 | **9** | 9 |
| L1/L2/L3 | 0 | 0 | 0 | 1 | 1 | 0 | 2 | 4 |
| C (falsos ERR/ALERTA) | 1 | 0 | 2 | 3 | 3 | 4 | 5 | 18 |
| G | 1 | 0 | 2 | 1 | 1 | 1 | 0 | 6 |
| T1 | 0 | 0 | 0 | 0 | 1 | 0 (tall de xarxa, no timeout) | 0 | 1 |

**ERR de sistema FINAL (8/8; 7 comparables): 4** (Anciles 0; Tulipa n/a). **Agregat: `_AGREGAT-8.md`.** — Rubí cota P-2 (F1, font d'Eva), Linyola `field_date` (D2, bug), Vilanova
`municipality` (D3, bug) i `nivell_freatic` P-3 (R6, política). **3 dels 4 són el mateix patró: un desempat mecànic
(`len(str)`, «només A bloqueja») decideix contra informació que el propi `_decisions.json` ja té.** Els ERR crus
d'Alcoletge (adreça) i Vilanova (SPT ×4) són del comparador (C).

## Estat dels fixes (2026-09-05)

| Codi | Estat | On | Evidència |
|---|---|---|---|
| **C** | ✅ v4 | `fase0-acceptacio/compare_consolida.py` (docstring v4: 10 canvis) + 30 casos nous a `tests/test_compare_consolida.py` | `{slug}/_compare_*.txt` regenerats sobre els `_decisions.json` originals: 18 falsos fora, cap de nou; `_AGREGAT-8.md` §Agregat mecànic |
| **D2** | ✅ | `consolidate.cluster_signals` (claus sense dia no uneixen; representant per autoritat), `_distinct_candidates.ordered_forms` (formes amb dia primer), `decide` (ISO del propi candidat 0) | Linyola `field_date` → 2025-10-01; 3 tests `test_D2_*` |
| **D3** | ✅ | `consolidate._canonical_municipality` (padró `name_ine` si totes les formes resolen al mateix INE), cridat a `consolidate_python` per a `municipality` | Vilanova → «Vilanova de Segrià»; 2 tests `test_D3_*` |
| **R3** | ✅ | `consolidate._UNIT_OF_N_RE` (`(?<![a-z0-9])1\s+de(?:ls?)?\s+(les|els)?\s*N`, N ≥ 2) + «unitat» | Bell-lloc `num_floors` → segur PB+PP; Castellar («unitats») continua sota guard; `test_R3_*` |
| G, R6, I1, R1, D5, D4, D6, T1, T2, S1 | ⏳ | — | pendents de prioritzar (Josep) |

Reconsolidació dels 7 amb el codi nou (sense re-run, lectures cachejades): `{slug}/_reconsolida-2026-09-05/`
(`_decisions.json` + `_compare_*.txt`). Agregador: `mesures/agrega_mesura.py [--sub _reconsolida-2026-09-05]`.

### Estat dels fixes — tarda (2026-09-05, resta de la fila 0b)

| Codi | Estat | On | Evidència |
|---|---|---|---|
| **G** | ✅ | `docs/golden-read/{Rubí,Alcoletge,Vilanova}/_decisions.json` `superficie_parcela.fora_carpeta` | 3 ALERTA → FORA (= signat) |
| **R6** | ✅ | `consolidate._nf_positive_over_absence` (post-`decide` a `consolidate_tables`) + `test_R6_*` | reconsolidació: 1 cel·la canvia (Vilanova P-3 → candidats, Aigua primer), cap altra |
| **I1** | ✅ (mesurat; + regla «V0 mai autoritat») | `inventory.has_current_pdf_dir` + `_V0_DIRS` (V0 llegida només si no hi ha `PDF/`), variants ES dels annexos (`ANEJOS`, `_sondeos`, `corte de correlación`) + 3 tests | run parcial `runs/2026-09-05-i1-anciles/` (5 PDF nous), vegeu `_AGREGAT-8.md` §I1 |
| **R1** | ✅ (4 de 5 equivalències) | `consolidate.value_key` (`btset` building_type, `addr` via+portals, sufix jurídic, punt de lab) + `_attach_only`/`_more_complete` a `cluster_signals` + `test_R1_*` ×5 | 7 cel·les → segur (totes = or/signat), 0 regressions. Persona/despatx (`architect_name`): NO, pregunta a Eva |
| **D5** | ✅ | `consolidate._cte_surface` (adossat/plurifamiliar = un edifici → total; aïllat = per unitat) + `test_D5_*` | Anciles C0 → C1 (= or), cap altra cel·la |
| **D4** | ✅ | `runner.LecturaResult.docs_failed`, `degraded |= docs_failed` | `test_timeout_then_retry_doc_failed_rest_continues` |
| **D6** | ✅ | `runner.assign_doc_names` + `os.replace` del JSON al nom esperat | `test_D6_*` ×2 (unitari + integració dwg/pdf amb cache) |
| **T1** | ✅ parcial | `runner.doc_timeout` (`G3DT_LECTURA_TIMEOUT_SLOW`=900 per a fulls de camp), `timeout_s` a telemetria | `test_T1_*`; la penjada segueix costant el topall (el CLI no escriu res fins al final) |
| **T2** | ✅ parcial | `runner.llm_conflict_paths` (només `fields.*`; topall `G3DT_LECTURA_LLM_MAX_CONFLICTS`=8) | `test_T2_*`; observació: 200-290 s per passada fins i tot amb 1 conflicte → decidir si es manté |
| **S1** | 📝 disseny | — | `_AGREGAT-8.md` §Runner i operació |

### Estat dels fixes — nit (2026-09-05, bloc 1 del handoff: lectura i decisió)

| Codi | Estat | On | Evidència |
|---|---|---|---|
| **R5** | ✅ (8 de 19 cel·les; +Anciles `client_name`) | `consolidate._FIELD_AUTHORITY` + `Signal.declares` (de `context.authority_for`) + `decide` (`field_auth`) + guards `cadastre` (forma completa, `_RC_RE`) i `parcela` (`_rc_parcels`); skill v1.7 (Pas 3 RC); `test_R5_*` ×7 | `_reconsolida-2026-09-05-r5/`: 8 cel·les CAND → OK, cap altra es mou; escalars 104 → 112 OK / 29 CAND (20 %); taules idèntiques. Queden: `num_floors` Castellar/Vilanova (conf 0,3-0,4, a posta) i 9 taules d'Anciles (manuscrit únic + V0) |
| **R2** | ✅ (6 escalars: 4 → OK, Castellar mateix estat amb regla nova; taules: Linyola `[0].a` → OK, 4 més convertides a fondària) | `consolidate._FIELD_BLOCKER_DOC_TYPES` + `_LEADING_COTA_RE` (clau numèrica de la cota) + `_is_other_field_day` (`field_date`, `extra.dies_de_camp`) + post-processos `_cota_relative_system` (Castellar) i `_depths_from_msnm` (per punt); `test_R2_*` ×4 | `_reconsolida-2026-09-05-vei/`: 9 cel·les canvien, cap altra; escalars 116/25/5/1/0; taules 138/21/7/31/0. Queden CAND pel format per punt (comparador) i el «mateix contacte» (1.4) |
| **F1** | ✅ (3 de 7: `lab_depth` Rubí i Linyola → OK; Rubí cota P-2 ALERTA → OK, l'ERR real sobre el signat cau) | `consolidate._FIELD_PRECEDENCE` + `_precedence_tier` (GTL > annex > comanda), `_dpsh_cota_header_coherence`; `test_F1_*` ×2 | `_reconsolida-2026-09-05-f1/`: 3 cel·les, cap altra; escalars 118/23/5/1/0 (OK 80 % ✅); taules 139/21/6/31/0. Queden (criteri/Eva): Castellar `lab_sample_id`, Linyola errata, Vilanova SPT ×2 + litologia |
| **1.4 derivats** | ✅ (13 cel·les: +4 OK, +7 CAND des de blanc, 1 CAND → OK; 1 ALERTA formal per l'or d'Alcoletge `[1].a`) | `consolidate._derive_soil_levels` (D1 `_derive_first_level_top`, D2 `_derive_level_tops`, D3 `_derive_last_level_base`, D4 `_level_membership` + `_derive_sample_level`, D5 `_derive_sample_lithology`), cridat a `consolidate_python` rere `_depths_from_msnm`; `test_D14_*` ×6 | `_reconsolida-2026-09-05-d14/`: taules 139 → 143 OK / 27 CAND / 7 ALERTA / **20 blancs** (31); escalars idèntics; conflictes idèntics. Queden 9 blancs d'altres peces (I1, L1) i 11 de lectura gràfica del tall no emesa |
| L1/L3, T2 (decisió), R4 + persona/despatx (Eva) | ⏳ | — | ordre del handoff §Bloc 1 |
