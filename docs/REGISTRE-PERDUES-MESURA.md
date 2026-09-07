# Registre de pèrdues de mesura acceptades (append-only)

Cel·les de M341 / `mesura_informe` que passen de MATCH (o CLOSE) a pitjor **a consciència**, amb l'explicació i la manera de
reobrir-les. Petició del Josep (2026-09-07): «anotem les pèrdues amb l'explicació, per poder-les revisar més endavant». Cada bloc
de feina hi afegeix les seves; mai s'esborra cap fila: quan una es resol, s'hi posa l'estat i el run que ho demostra.

Convenció: **abans → ara** són els valors impresos pel sistema (gen) i **signat** el de l'Eva. Estat: `oberta` · `resolta (run)` ·
`acceptada` (és el signat el que no és consistent).

## 2026-09-07 — Bloc 1 (P5 · P6 · CTE · rang · data) — runs `2026-09-07-m341-peca3` → `2026-09-07-m341-bloc1b`

| # | Projecte · variable | Abans → ara (signat) | Per què s'ha perdut | Com es reobre | Estat |
|---|---|---|---|---|---|
| 1 | Rubí · `settlement` | 1,50 MATCH → 1,80 X (signat 1,50) | La Qa ha passat de 3,0 a 3,5 (= signat) perquè el topall granular dens ara dispara amb `grava` (P6). Amb Qa 3,5, Es = 2,5×N SPT (40 → 100) dona 1,8 cm i 2,5×Nb (47 → 117) 1,7 cm; 1,50 només surt amb Qa 3,0. El back-engineering d'abril 2026 («2,5×Nb: Rubí 1,52 ≈ 1,50») estava calibrat sobre la Qa equivocada: el MATCH d'abans era la suma de dos errors. | Pregunta 24 a l'Eva (quina càrrega i quin Es). Si l'assentament es calcula amb la Qa recomanada, cal un Es ≈ 137 (3,5×Nb 39? 2,5×55?) o refer la font de `settlement_criteria` (candidat «2,5 × Nb» perd l'evidència de Rubí). | oberta |
| 2 | Linyola · `table_dpsh_range` | «3, 4 i 5» MATCH → «3 i 4» X (signat «3, 4 i 5») | Regla nova: l'Eva compta TAULES (DPSH + sondeig si n'hi ha + SPT/MA). Verificat al `.doc` signat (soffice → txt): Linyola té DUES taules in situ i tres DPSH, exactament com Rubí i Alcoletge, que signen «3 i 4». La regla encerta 6/7; el «3, 4 i 5» de Linyola és una incoherència del signat. | Pregunta 23 a l'Eva. Si diu que compta assaigs quan n'hi ha ≥ 3, Rubí i Alcoletge serien els incoherents i la regla canviaria. | acceptada (pendent de l'Eva) |
| 3 | Alcoletge · `geomech_gamma` / `geomech_cohesion` / `geomech_phi` (escalars) | 2,00 CLOSE / 0,00 MATCH / 38 X → 2,20 X / 1,00 X / 30 CLOSE (veritat 1,80 / 0,00 / 28) | La veritat de l'extractor de referència és la **fila 1** de la taula geotècnica (rebliment). El nivell portant real és la fila 2 (lutites, Df 1,0 sota el rebliment: frase del Qa del signat) i P5 ara hi calcula: la fila 2 de la taula dona c 1,00 i φ 30 MATCH contra el signat. És deriva de l'extractor (bloc 3 del PLA: `refresh_eva_narrativa.py --all-keys` ja avisa que `geomech_*` d'Alcoletge/Vilanova canvien de fila). | Bloc 3: l'extractor ha de prendre `geomech_*` de la fila del nivell portant (o guardar-los per fila). Es resol sense tocar el generador. | oberta (bloc 3) |
| 4 | Alcoletge · taula geotècnica, columna N (files 1 i 2) | «--» / «20» MATCH×2 → «20» / «--» X×2 (signat «--» / «20») | L'SPT-1 (0,80-1,40 m, N 20) cau per fondària dins del rebliment amb el contacte llegit a 1,40 (abans el segmentador posava el contacte a 1,0 i queia al 2n nivell per casualitat). L'Eva l'assigna a les lutites pel MATERIAL recuperat («Llims compactes, lutites alterades»). `assign_spt_n30` mira primer la litologia, però la litologia llegida de l'SPT és «[primera paraula il·legible] marró» → cau a la fondària mitjana (1,10) → nivell 1. | Pregunta 25b a l'Eva (material > fondària?). Tècnicament: re-lectura de la litologia de l'SPT del manuscrit o usar la descripció de la mostra del GTL/comanda; amb litologia llegible la regla actual ja el posaria al 2n nivell. | oberta |

### Moviments sense canvi d'estat (X → X) que convé revisar amb l'Eva

| Projecte · variable | Abans → ara (signat) | Per què s'ha mogut | On es reobre |
|---|---|---|---|
| Anciles · `qa_value` | 3,00 → 3,50 (signat 2,0) | El càlcul imprès usa ara la geometria del nivell portant (E): pous a 2,9 → graves Nb 26,3 ≥ 25 → topall granular dens 3,5. Abans l'N20 global (Nb 17,6) el deixava a 3,0. Numèricament més lluny del signat, però el 2,0 és l'outlier de judici (`CRITERIS-CALCUL-EVA.md` §6). | Pregunta 25a / §6 |
| Vilanova · `qa_value` | 1,00 → 1,50 (signat 2,5) | P6: L1 «Arcilla limosa» és argila (c 0,10, φ 25, γ 1,90 = fila signada) → Terzaghi 1,5. Els paràmetres coincideixen amb l'Eva; la Qa no: judici. | Pregunta 25a |
| Alcoletge · `qa_value` | 3,00 → 3,00 (signat 3,5) | Ara és roca (lutites, c 1,00) amb topall 3,0; el handoff esperava 3,5 via el topall granular, però les lutites NO són granulars (Linyola i Castellar signen 3,0 amb els mateixos paràmetres). | Pregunta 25a |
| Alcoletge · taula geotècnica, Nb fila 1 | «6» → «7» (signat «5-0») | Mitjana N20 de 0-1,40 en lloc de 0-1,0 (contacte llegit). El «5-0» del signat és estrany en si mateix. | — |

## 2026-09-07 — Bloc 2 (format de la cua d'A) — runs `2026-09-07-m341-bloc1b` → `2026-09-07-m341-bloc2b`

**Cap cel·la perduda** (escalars: 10 moviments, tots a millor; 11 taules dins M341: 6 M / −4 C / −2 X; els 12 informes de
`mesura_informe`: només Bell-lloc t2 SPT id C → M). Una pèrdua **provisional** detectada i resolta dins el mateix bloc:

| # | Projecte · variable | Abans → ara (signat) | Per què s'ha perdut | Com es reobre | Estat |
|---|---|---|---|---|---|
| 5 | Alcoletge · taula «plantes», superfície de la parcel·la | «1167.0» MATCH → «1.167» X (signat «1167») al run `-bloc2` | El comparador de taules llegia «1.167» com a 1,167 (decimal), no com a mil cent seixanta-set. L'Eva escriu «1.284» a Castellar i «1167» a Alcoletge: el format imprès és el català (milers amb punt) i el comparador ha de comparar NÚMEROS. | Arreglat al mateix bloc: `_as_num` de `compare_tables_vs_eva.py` i `_norm_thousands` de `compare_prefills_vs_eva.py` llegeixen els grups de tres xifres com a milers (tests `test_*_reads_thousands_as_thousands`). | resolta (`2026-09-07-m341-bloc2b`) |

### Moviments sense canvi d'estat (X → X)

| Projecte · variable | Abans → ara (signat) | Per què s'ha mogut | On es reobre |
|---|---|---|---|
| Rubí · `client` / Alcoletge · `client` | «JOANA MARTÍNEZ» → «SRA. JOANA MARTÍNEZ» (signat «SRA. JOANA MARTINEZ»); «ALBERT SANS BONVEHÍ» → «SR. ALBERT SANS BONVEHÍ» (signat «SR. ALBERT SANS BONVEHI») | L'honorífic ja hi és (com al signat); la cel·la segueix X només per l'ACCENT que l'Eva no escriu en majúscules (però sí a «SÍLVIA EROLES BALAGUERÓ»). El comparador d'escalars distingeix accents; el de narrativa no. No es toca: el nom llegit porta l'accent que té al document. | — (tipografia del signat) |
| Anciles · `client` | «MARIA ALBA BARRAU CASTÁN» → «SRA. MARIA ALBA BARRAU CASTÁN» (signat «SRA. ALBA MARIA BARRAU CASTÁN») | Ordre dels noms de pila: el pressupost signat diu «Maria Alba»; l'Eva escriu «Alba Maria» (com signa ella els correus). | Pregunta 26 (quin nom va a la portada). |
| Rubí · 12 informes (`8b`/`calc`/`t2`/`viab`), taula «plantes» | «1414» → «1.414» (signat «951») | Només format: el valor d'abril del wizard (1414, tres parcel·les) segueix sent el que és. | Pregunta 10 / user_data d'abril. |

## 2026-09-07 — Bloc 3 (veritats re-extretes) — runs `2026-09-07-m341-bloc2b` → `2026-09-07-m341-bloc3b`

Les cel·les que cauen aquí no les fa caure el sistema: cau la VERITAT antiga que l'afavoria, o l'assumpció de Df que la contradeia.

| # | Projecte · variable | Abans → ara (signat) | Per què s'ha perdut | Com es reobre | Estat |
|---|---|---|---|---|---|
| 6 | Vilanova · `geomech_E` / `geomech_cohesion` / `geomech_gamma` / `geomech_phi` | 50 / 0,10 / 1,90 / 25 MATCH×4 (veritat d'abril = fila 1) → 450 X / 0,0 X / 2,0 C / 38 C (veritat = fila 2: 550 / 0,50 / 2,20 / 34) | El signat recolza els pous al **2n nivell** («apoyada en los materiales del 2do nivel saneado»); la veritat d'abril tenia la fila 1 i el sistema (Df 0,3) hi coincidia per un error compartit. Ara la veritat és la fila portant declarada (`bearing_layer_idx` 1) i el sistema calcula al 2n nivell (Df 1,1): el classificador diu sorra (φ 38, c 0) on l'Eva escriu «areniscas, arenas, sustrato» (φ 34, c 0,50, E 550). | Pregunta 14/25a (criteris de roca tova / sorres cimentades); P6 amb «areniscas» com a roca tova. | oberta |
| 7 | Vilanova · `settlement_sentence` | «…menyspreables o bé inferiors a 1.0 cm» MATCH (numèric 1,0 = 1,0) → «iguals o inferiors a X cm» X (signat «menospreciables o inferiores a 1.0») | Amb Df 1,1 el nivell portant és el 2n (sorra → règim granular → valor de Schmertmann); l'Eva el tracta com a roca/cohesiu (frase genèrica). Mateixa arrel que #6. | Mateixa que #6. | oberta |

### Moviments sense canvi d'estat (X → X) o claus noves que entren en X

| Projecte · variable | Abans → ara (signat) | Per què | On es reobre |
|---|---|---|---|
| Vilanova · `qa_value` | 1,50 → 3,00 (signat 2,5) | Df 1,1: 2n nivell sorra densa → topall 3,5? no: Terzaghi 3,0 amb φ 38. Més a prop, encara X. | #6 |
| Castellar · `bearing_layer_idx` (nova) | — → 1 X (signat 0) | El signat té UNA fila geotècnica (bretxes); el sistema en modela dues (superficial + roca). Índex ≠ paràmetres: els de la roca coincideixen. | Recompte de nivells de Castellar (criteri «Unitat litològica»). |
| Rubí / Linyola / Alcoletge · `spt_lithology` (noves) | — → X | Vocabulari curt de l'Eva («Graves i sorres», «Lutites», «Llims compactes, lutites alterades») contra la lectura del full de camp. Mateix cas que el bloc 2 va descartar. | Candidat al wizard, no fórmula. |
| Anciles · `superficie_construida` (nova) | — → 186,18 X (signat 1273,79) | El signat porta el TOTAL de les 7 cases; la lectura, una casa. | Pregunta 27b. |
| Vilanova / Anciles · `data_camp_inici_text`, `municipality_de` (noves) | — → X | Castellà: el prefix català no hi és i la veritat és el paràgraf sencer. | Bloc 5 (plantilla ES + prefixos ES a l'extractor). |

## 2026-09-07 — Bloc 4 (numeració i imatges, mai mesurats) — runs `2026-09-07-m341-bloc3b` → `2026-09-07-m341-bloc4-num` (veritats de numeració) → `2026-09-07-m341-bloc4b` (cau d'imatges per contingut)

**Cap cel·la perduda**: els grups A, calc, narrativa, resta i les 11 taules són idèntics cel·la a cel·la a `-bloc3b`. Entren 99 veritats
noves de numeració (`*_num`, grup `fix`): **74 MATCH · 25 X → 75 %**. Cap X és un error de comptar del generador: donada l'estructura
que imprimeix, el número és el que toca. Les 25 X són, per causa:

### Claus noves de numeració que entren en X (25)

| Projecte · variable | Sistema (signat) | Per què | On es reobre | Estat |
|---|---|---|---|---|
| Castellar · `fig_spt_cullera_num` / `fig_geological_num` / `fig_correlation_num` | 4 / 5 / 6 (3 / 4 / 5) | El signat té **2** figures del projecte: Fig. 1 = situació amb topogràfic i ortofoto en UNA figura, Fig. 2 = emplaçament + assaigs. La plantilla n'imprimeix sempre **3** («Figura X i Figura Y» + plànol). `num_project_figures` només en pot AFEGIR. | Plantilla: bloc de figures del projecte variable (2 / 3 / 4). Decisió del Josep (bloc 7). | oberta |
| Rubí · idem (3) | 4 / 5 / 6 (3 / 4 / 5) | Mateixa causa (Fig. 1 situació, Fig. 2 estructura + assaigs). | idem | oberta |
| Alcoletge · idem (3) | 4 / 5 / 6 (3 / 4 / 5) | Mateixa causa. | idem | oberta |
| Anciles · `fig_spt_cullera_num` | 4 (5) | El signat té **4** figures del projecte (catastro, topográfico, viviendas, ensayos). Les altres dues figures ES no s'extreuen (bloc 5). | idem | oberta |
| Rubí · `photo_dpsh_num` / `photo_materials_num` | 1 / 2 (2 / 3) | El signat porta **1** foto de vista general («Google Earth, agost 2024») triada per l'Eva; la via A no en tria cap (`_num_site_photos` 0; Bell-lloc en té 2 perquè `photo_selection.json` porta `source=user`). | Pestanya de fotos del wizard (pregunta 19a). | oberta |
| Castellar · `photo_materials_num` | 3 (4) | El signat **salta la Fotografia 3** (1, 2, 4; comprovat al `.doc` i al `document.xml`). | — | acceptada |
| Bell-lloc · `section_resum_num` | 2.4.4 (2.4.3) | El signat numera **2.4.3 dues vegades** (S.P.T. i Resum). | — | acceptada |
| Linyola · `section_excavabilitat_num` / `section_sismica_num` / `section_rado_num` | 3.5 / 3.6 / 3.7 (3.6 / 3.7 / 3.8) | El signat té «3.5 EXPANSIVITAT DELS MATERIALS» (i «4.3 EXPANSIVITAT»); `include_expansivity` és sempre False (`report_data.py`: «Determinat per tipus de sol», mai derivat). Linyola té assaig Lambe al GTL. | Pregunta 28 (criteri). | oberta |
| Alcoletge · `section_sismica_num` / `section_rado_num` | 3.6 / 3.7 (3.7 / 3.8) | Idem, però el signat posa l'expansivitat a **3.6, després** de l'excavabilitat (Linyola: abans, com la plantilla). Amb `include_expansivity` la plantilla donaria 3.6 / 3.7 / 3.8 → l'excavabilitat (avui MATCH) passaria a X. Sense Lambe al GTL. | Pregunta 28 (posició). | oberta |
| Linyola · `table_lab_num` / `table_permeability_num` / `table_lab_values_num` / `table_seismic_num` / `table_soil_chars_num` | 5-9 (6-10) | Mateixa causa que el registre **#2** (`table_dpsh_range` «3, 4 i 5» amb dues taules): el signat compta una taula in situ de més i arrossega les cinc següents. | Pregunta 23. | oberta |
| Anciles · `section_empentes_num` | '' (4.4) | El signat té «4.4 EMPUJE DE TIERRAS» («muros del sótano»: semisoterrani a 2 dels 7 habitatges). `include_earth_pressure` només s'activa amb `has_basement` / `has_retaining_walls` (wizard) o amb pendent ICGC; la via A no ho omple. La lectura diu plantes «2Ps+Pb+1Pp». | Pregunta 29; prefill de `has_basement` des de les plantes (Ps/Ss). | oberta |

### Imatges (full de control visual `runs/2026-09-07-m341-bloc4b/_IMATGES.md`)

Sense veritat comparable per text; el que s'ha vist als 7 `.docx` generats abans i després d'arreglar la cau (detall a `_IMATGES.md`
i al DECISION-LOG 2026-09-07 (vespre)). Els defectes de contingut que queden oberts (tria de foto, pàgina del plànol, retall de
situació) no són cel·les de M341: el test de presència només diu «hi és / pendent / absent».

## 2026-09-07 — Pas 3 d'imatges, peces 1 i 2 — runs `2026-09-07-m341-peca1b` → `2026-09-07-m341-peca2`

Mesura nova d'aquest bloc: **imatges «mateixa font que l'Eva» per figura** (peça 0, `imatges_font.py`). La peça 1 (plantilla)
no mou cap cel·la fora del grup `fix` (+9 −9 = net 0, previst). La peça 2 (lector de fotos) mou 6 cel·les d'imatge i 1 de
narrativa; guanys i pèrdues per separat.

### Guanys (peça 2)

| Projecte · ranura | Abans → ara | Per què |
|---|---|---|
| Bell-lloc · `foto_sondeig` | X → **M** | La selecció `user` del corpus posava la DPSH P-2 com a màquina de sondeig; el lector tria la de `FOTOGRAFIES/SONDEIG/`. |
| Bell-lloc · `foto_vista` (2) | M + X → **M + M** | La selecció `user` posava la màquina del sondeig com a 2a vista general. |
| Anciles · `foto_materials` | X + ND → **M + ND** | El lector tria `S1.jpeg` (caixa de testimonis del sondeig S-1); abans, un detall de la mostra SPT. |
| Castellar · `foto_materials` | M → M (phash 12 → 0) | Mateixa caixa, ara exactament la del signat. |

### Pèrdues acceptades (peça 2)

| Projecte · variable | Sistema (signat) | Per què | On es reobre | Estat |
|---|---|---|---|---|
| Rubí · `foto_dpsh` | `P1.jpg` (`P3.jpg`) | L'annex de l'Eva porta una foto de la DPSH per punt (P-1…P-3) i el signat en porta una, sense criteri conegut: 3 signats agafen la primera de l'annex, 3 l'última, 1 la segona. El lector desempata amb «la primera de l'annex» (4/7). Abans, els patrons encertaven Rubí per casualitat (agafaven l'última). | pregunta 37 a l'Eva | oberta |
| Vilanova · `foto_vista` + `photo_site_text` | `DES DE DARRERA.jpeg` (`DES DEL CARRER.jpeg`); ND → X al peu | L'annex de fotografies de Vilanova porta DUES «vistas generales de la parcela» (des de darrere i interior) i el signat en porta UNA de diferent, des del carrer, que no és a l'annex. El lector segueix l'annex. Abans no s'imprimia cap vista (cap tria explícita) i la cel·la era ND. | pregunta 38 a l'Eva | oberta |

Les dues pèrdues són el mateix tipus: **empat sense criteri conegut** entre fotos equivalents. No s'inventa cap regla; van a
l'Eva. La segona canvia una cel·la de ND a X: el sistema ara diu una cosa (imprimeix dues vistes) on abans callava.
