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

