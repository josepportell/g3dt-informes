# PLA — Què queda després de les dades A, B i la narrativa (2026-09-07)

**Pregunta del Josep (2026-09-07):** «hem treballat molt les dades de tipus A, tipus B i ara narrativa. Queda algun altre tipus pendent?»
**Resposta curta:** no hi ha cap tipus nou; queden (1) la cua dels grups ja mesurats (A i càlcul tenen més cel·les vermelles que la
narrativa en valor absolut), (2) les taules dels tres projectes fluixos, (3) un bloc que **mai s'ha mesurat** (figures, imatges,
numeració) i (4) el castellà. Aquest document ho posa tot en un mapa, amb l'ordre recomanat i el que desbloqueja cada peça.
Base: run `2026-09-07-m341-peca3` (M341, via A, 7 projectes) i `2026-09-07-informe-peca3` (11 taules, 3 projectes × 4 variants).
Vegeu DECISION-LOG 2026-09-06 (nit, 2) i `docs/ANALISI-NARRATIVA-2026-09-06.md` §10.

## 0. El mapa (què és cada «tipus» i com està)

| Grup (M341) | Què conté | M · C · X · ND | % | Cel·les vermelles (X) | Sostre real |
|---|---|---|---|---|---|
| **A** (lectura) | 29 escalars llegits dels documents (noms, adreça, superfícies, plantes, dates, mostra de laboratori, SPT, UTM…) | 81 · 11 · 33 · 16 | 74 % | **33** | alt: la majoria són FORMAT o veritat mal extreta, no lectura |
| **calc** («B») | 21 escalars de càlcul i regles (Qa, assentament, K30, γ/c/φ/E, CTE, sísmica, radó, rang de taules, sulfats, seccions condicionals) | 57 · 5 · 32 · 2 | 66 % | **32** | alt: 4 projectes sense sondeig van amb geometria del segmentador (P5) i classificador de sòl equivocat (P6) |
| **narr** | 22 frases | 32 · 30 · 39 · 8 | 61 % | 39 | mitjà: 13 cel·les ES (sostre), 6 d'estat del solar (judici), la resta preguntes 16-21 |
| **taula** | 11 taules (DPSH, sondeig, SPT/MA, laboratori, nivells, permeabilitat, sulfats, sísmica, geotècnica, plantes, CTE) | 267 · 97 · 99 | 79 % | 99 | Vilanova 64 %, Alcoletge 73 %, Anciles 74 %; Castellar-Rubí-Bell-lloc-Linyola 82-91 % |
| **resta** | 4 variables que no són ni A ni B | 11 · 4 · 8 · 7 | 65 % | 8 | `data_signatura_text` 0/7 (no és a cap document) |
| **fix** (NO mesurat) | ~25 números de figura, foto, taula i secció (`fig_*_num`, `photo_*_num`, `table_*_num`, `section_*_num`) | — | — | — | derivats; ningú els ha comptat contra els signats |
| **imatges** (NO mesurat) | plànol de situació, ortofoto, mapa geològic, tall de correlació, fotos (5-7 per informe) | — | — | — | només a ull; `/g3dt-audit-informe` compara text, no imatges |
| **castellà** | 2 de 7 signats | — | — | — | sostre de TOTS els grups mentre no hi hagi plantilla ES |

Univers: la plantilla té 56 noms escalars + 8 llistes de taula (M341 en puntua 100 noms); la «veritat» de l'extractor en treu 56-65 per
projecte; les 341 variables del títol són escalars + cel·les de taula. **Tot el que hi ha a l'informe és a la taula de dalt: cap tipus
nou.**

## 1. Blocs de feina, en l'ordre recomanat

### Bloc 1 — Càlcul i taules dels 4 projectes sense sondeig (P5, P6, CTE, rang de taules) — *M, 1-2 dies, mou calc I taules*

> **Estat 2026-09-07 (matí): FET i mesurat** (DECISION-LOG 2026-09-07 (bloc 1); runs `2026-09-07-m341-bloc1b`, `2026-09-07-informe-bloc1b`). calc 66 → **76 %**, resta 65 → 87 %, total 67 → **71 %**, taules 79 → **81 %**; Linyola 72 → 78 (taules 88 → 91), Alcoletge 61 → 66 (73 → 75), Vilanova 53 → 60 (64 → 69), Castellar 76 → 81, Rubí 73 → 76, Bell-lloc 78 → 81. Queden: Alcoletge C-0 (pregunta 22), Linyola «3, 4 i 5» (23), Rubí assentament amb Qa 3,5 (24), Alcoletge Qa 3,5 i SPT al 2n nivell (25); Vilanova/Anciles sense contacte al tall (segmentador).

Les 4 cel·les de cada projecte (Linyola, Alcoletge, Vilanova, Anciles) que fan baixar calc de 78 % (t2) a 66 % (viaA) surten de dues
causes conegudes (DECISION-LOG 2026-09-06 (vespre), troballes 1-3):

| Peça | Què | Evidència (run peca3) | Fitxers | Esforç |
|---|---|---|---|---|
| **P5** geometria de nivells des de la lectura quan no hi ha sondeig | avui `sondeig_layers` surt del segmentador DPSH i col·lapsa (Linyola un sol «Llims» 0-3,0 → grava φ 38 c 0 E 450 on el signat calcula lutites 30 / 1,0 / >800) | `geomech_phi` Linyola 38↔30, Alcoletge 38↔28, Vilanova 29↔25; `geomech_cohesion` Linyola 0↔1,0, Vilanova 0↔0,10; `sismica` gruixos 0,80↔2,20 (Vilanova), 1,00↔1,40 (Alcoletge), 2,20↔4,00 (Anciles); `sulfate_level_name` 1er↔2on (3 projectes, però vegeu pregunta 13) | `report_generator.py` (bloc `sondeig_layers` / `_bearing_soil_type`), `lectura/tables_report.build_report_tables` (`soil_levels` de/a) | M |
| **P6** un sol classificador de sòl | `cte_geomech.detect_soil_type` diu «grava» a «Arcilla limosa y arenosa con algunas gravas» i «granular» a «Rebliment antròpic»; `geotech_criteria._classify` ho fa bé; el topall 3,5 només dispara amb `'granular'` literal | `qa_value` Rubí 3,00↔3,50, Alcoletge 3,00↔3,50, Vilanova 1,00↔2,50; `geotecnica` Vilanova 9 X, Anciles 5 X | `cte_geomech.py`, `geotech_criteria.py` (`GRANULAR_TYPES`), `terzaghi_calculator.calculate_qa` | S-M |
| **CTE sòl** | `cte_classifier.classify_soil` posa T-2 quan N20 mitjà < 20 i T-3 amb rebliment; **l'Eva escriu T-1 a 6/6** | `cte_sol` 1 · 0 · 5; taula `cte_edificacio` fila 1 a Castellar, Alcoletge, Vilanova | `cte_classifier.py`, `wizard_service._compute_lookup_prefills` | S (regla: T-1 per defecte; T-2/T-3 només si l'Eva ho canvia) |
| **CTE edificació** | C-0 / C-1 per plantes: Castellar C-0↔C-1 (Pb+1Pp llegit com «Pb+1»), Alcoletge C-1↔C-0 (plantes buides → defecte C-1) | `cte_edificacio` 4 · 0 · 2 | `cte_classifier.classify_building`, `parse_floor_count` | S |
| **Rang de taules in situ** | el generador compta tests (3 DPSH → «3, 4 i 5»); **l'Eva compta TAULES**: DPSH (1) + sondeig (1 si n'hi ha) + SPT (1) → «3 i 4» sense sondeig, «3, 4 i 5» amb sondeig (7/7 signats) | `table_dpsh_range` Rubí, Alcoletge, Vilanova, Anciles X | `report_generator._compute_numbering` (`total_insitu_tables`) | S (10 línies) |
| **Data de signatura** | el generador posa avui; és la data que l'Eva signa: camp del wizard amb el dia d'avui per defecte | `data_signatura_text` 0 · 0 · 7 | `wizard.py` (`WIZARD_FIELDS`), `review.html`, `report_generator` | S |
| **Assentament** (variant) | Bell-lloc «inferiors a» vs «iguals o inferiors a»; ES | `settlement` 4 · 0 · 3 | `settlement_criteria.py` (candidat) | S |

**Guany esperat:** calc de 66 % cap a ≈ 75 % i les taules `geotecnica`, `sismica` i `cte_edificacio` dels 4 projectes; Vilanova i
Alcoletge pugen de 64 / 73 % (és on són les X). **Dependències:** cap de l'Eva per a P5/P6/CTE/rang; `sulfate_level_name` i P4
(N20 global o del tram) esperen les preguntes 13 i 6.

### Bloc 2 — La cua del grup A: format i veritats, no lectura — *S-M, ½-1 dia, 33 X de les quals ≈ 20 són format*

> **Estat 2026-09-07 (migdia): FET i mesurat** (DECISION-LOG 2026-09-07 (bloc 2); runs `2026-09-07-m341-bloc2b`, `2026-09-07-informe-bloc2b`). A 74 → **77 %** (81·11·33·16 → 89·7·29·16), total 71 → **73 %**, taules 81 → **82 %**; calc, narrativa i resta intactes; cap pèrdua. Fet: `plantes` (5/6 M), `client` (honorífic), `building_type_lower` (article; plantilla «la construcció {{ building_type_de }}»), `superficie_parcela` («1.284» + comparadors llegint milers), `cota_referencia` («+188.20»), `spt_test_id` («SPT-1»), `municipality` (padró + «en el municipi {{ municipality_de }}»), `architect_company_de` («, de 2 Graus» en lloc de «de l'2 Graus»). **No fet i per què:** `spt_lithology` (la forma curta de l'Eva no és derivable: «Limolites i bretxes» ← «Bretxes amb intercalacions de lutites…»; 0 cel·les), cota d'Anciles (els annexos són a `PDF_V0/ANEJOS/`, exclosos per la regla I1: lectura, no format), `architect_name_upper` (1.7), N30/cota relativa/superfícies de Vilanova (preguntes 1, 2, 9), veritats-frase d'Alcoletge/Vilanova/Anciles (bloc 3). Queden 29 X d'A: 9 castellà/extractor (bloc 3 i 5), 8 esperen l'Eva, 5 laboratori sense GTL (bloc 6), 4 arquitecte (1.7), 3 tipografia del signat (accents en majúscules, «(Barcelona)»).
> **Pendent futur (decisió del Josep 2026-09-07):** la frase dels antecedents té tres formes als signats (arquitecte en nom del client / client mateix / empresa) i el sistema només en sap una. Es pot mirar d'inferir del contingut dels correus (cossos) i dels pressupostos (qui demana, qui signa, en nom de qui): feina d'LLM, poques probabilitats d'encert sols, **més endavant**. Pregunta 26 mentrestant.

| Variable | X | Què passa realment | Arranjament |
|---|---|---|---|
| `architect_name_upper` | 5 | l'Eva escriu el DESPATX (Linyola «BUNYESC ARQUITECTURA EFICIENT») o un altre arquitecte (Alcoletge, Vilanova: el que signa el projecte, no el del caixetí?) o el nom sense col·legiat | pregunta 1.7 «persona/despatx» a l'Eva; mentrestant candidats (persona / despatx / nom net sense «NºCOL.») |
| `building_type_lower` | 5 | l'Eva hi posa l'ARTICLE i el projecte tal com el pressupost el descriu («un habitatge unifamiliar», «3 habitatges unifamiliars d'estructura lleugera, fusta», «l'ampliació d'un edifici en planta baixa») | article per gènere/nombre (S) + tipus del pressupost/comanda com a candidat (ja es llegeix) |
| `client` | 3 | «SRA.» / «SR.» davant del nom (4/4 signats) | honorífic per nom de pila (taula curta, candidat quan dubte) — S |
| `plantes` | 2 (+3 CLOSE) | notació: l'Eva «Pb», «PB + Porxo», «Pb+1Pp»; nosaltres «PB (planta baixa, 1 nivell)», «PB (planta baixa)+porxada, sense pis superior» | `format_floor_notation` sobre el text llegit abans d'imprimir (ja existeix, no s'aplica a la lectura) — S |
| `superficie_parcela` | 3 | Castellar «1284.0» ↔ «1.284» (separador de milers); Vilanova 406↔100 (pregunta 9: intercanviades); Anciles «T-1» = veritat MAL extreta | format «1.284» — S; la resta preguntes/extractor |
| `municipality` | 3 (+2 CLOSE) | Alcoletge, Vilanova, Anciles: la VERITAT és la frase sencera de la sísmica (extractor); Rubí «(Barcelona)», Bell-lloc grafia «BELL.LLOC» | bloc 3 (extractor) + `municipality_proper` del padró a la impressió — S |
| `data_camp_text` | 3 | Bell-lloc: l'Eva escriu només el primer dia també a la segona ranura («1 d'octubre»); Vilanova/Anciles veritat = frase sencera | revisar la regla de la data doble (2026-09-05) amb l'Eva; extractor |
| `spt_lithology` | 3 + 1 ND | l'Eva escriu la forma CURTA del material a la taula SPT («Graves en matriu sorrenca», «Limolites i bretxes»); nosaltres la descripció llarga llegida | vocabulari curt: primer sintagma nominal de la litologia del nivell — S-M |
| `spt_n30` | 2 | Bell-lloc 62↔54 (pregunta 1), Vilanova 24↔10 | preguntes 1 i 7 |
| `cota_referencia` | 1 + 1 ND | Castellar +570,90 ↔ −4,0 (cotes relatives al carrer: pregunta 2); Anciles sense cota (fora de Catalunya: sense MDT ICGC) | pregunta 2; Anciles: cota de l'annex DPSH llegit («+1106.40» hi és) — S |
| `superficie_construida` | 1 | Vilanova 100↔406 (pregunta 9) | pregunta 9 |

### Bloc 3 — Deriva de l'extractor de referència (veritats fora de la narrativa) — *S-M, ½ dia*

> **Estat 2026-09-07 (tarda): FET i mesurat** (DECISION-LOG 2026-09-07 (tarda); runs `2026-09-07-m341-bloc3-veritats` (només veritats) i `2026-09-07-m341-bloc3b` (+ `bearing_layer_idx`, Df Vilanova 1,1)). Extractor arreglat per clau abans d'aplicar: taula SPT com a bucle (+ `spt_*` de la 1a fila; Rubí/Linyola/Alcoletge la tenien i t5 «sondeig» se l'enduia), fila portant pel que DIU el signat (`bearing_row_from_text` → `bearing_layer_idx`, 6/7 M), taules per etiqueta i assignació global (Anciles «T-1»/«C-1» → 1655,01 / plantes reals, `cte_*`), capçaleres ES, notacions «15-R»/«38º»/«>350», àncora sobre «Qa= {{ qa_value }} …» (`settlement_sentence` 7/7). Veritats re-extretes a TOTES les claus (`--keys all`). **Total 73 → 74 %, A 77 → 78 %, calc 76 → 77 %, taules 82 % intactes; Alcoletge 66 → 75 (registre #3 resolt), Bell-lloc 84 → 87 (`data_camp_text` era la 1a ranura), Vilanova 60 → 55 (honest: la veritat d'abril tenia la fila 1; el signat recolza al 2n nivell amb pous).** No fet: p60 multi-forat (`*_de` no s'extreuen; pregunta 26), castellà (bloc 5). Preguntes 27 (Vilanova SPT P-1/P-3; Anciles construïda total).

`refresh_eva_narrativa.py --all-keys` ja diu què mouria una re-extracció sencera: `spt_*` cauen a None, les dates canvien de clau
(segona variable de data), `geomech_*` d'Alcoletge/Vilanova canvien de fila, `settlement` → `settlement_sentence`, `num_dpsh_tests`
(número sol). A més, veritats equivocades vistes al run: `municipality` (3 projectes: paràgraf de la sísmica), `superficie_parcela`
d'Anciles («T-1»), `plantes` d'Anciles («C-1»), `data_camp_text` ES (frase sencera). **Mètode:** arreglar l'extractor per clau,
re-extreure els grups A i calc amb la mateixa disciplina que la narrativa (llista blanca + `diff` per clau), mesurar abans/després.
Sense això, una part del 26 % vermell d'A és soroll de la mesura, no del sistema.

### Bloc 4 — El que mai s'ha mesurat: numeració i imatges — *S per numerar, M per a les imatges*

> **Estat 2026-09-07 (vespre): FET i mesurat** (DECISION-LOG 2026-09-07 (vespre); runs `2026-09-07-m341-bloc4-num` (99 veritats `*_num`, generador intacte) i `2026-09-07-m341-bloc4b` (cau d'imatges per contingut; `_IMATGES.md` + 7 fulls de control)). Numeració: extractor propi per tipus (Figura/Fotografia/Taula/capçalera) i un-a-un, llindars mesurats (capçaleres 0,70; peus ratio 0,5 + contenció 0,6), empat = blanc; ES només capçaleres. Grup `fix` **74 M · 25 X → 75 %**; **cap X és un error de comptar**: 10 nombre de figures del projecte (plantilla fixa 3; signats 2/3/4), 5 taules de Linyola (pregunta 23), 5 expansivitat (pregunta 28), 2 vistes generals de Rubí, 1 empentes d'Anciles (pregunta 29), 2 incoherències del signat. Total 74 %, cap altra cel·la moguda, informes idèntics. Imatges: test de presència a M341 (53 present · 8 pendents = 6 sense UTM + 2 sense rol `architect_plan` · 16 absents) i full de control visual 7 × 11: **la cau d'imatges (clau pel nom del PDF) donava el tall de correlació de Bell-lloc a 5 projectes més**, el plànol A.01 de Bell-lloc a Alcoletge i el retall de situació de Linyola a Anciles → `_cache_name` per contingut, 0 duplicats (**producció té el mateix bug**). Queden: 4 imatges de tria/pàgina errònies, 1 retall (Linyola), foto de materials repetida per nivell (plantilla), UTM/rol per als 8 pendents.

- **Numeració** (`fig_*_num`, `photo_*_num`, `table_*_num`, `section_*_num`): la peça 3 ha arreglat el +2 de les fotos, però cap
  número s'ha comptat contra els 7 signats. Afegir-los a M341 com a grup `fix` puntuable: l'extractor de referència ja llegeix els peus
  («Fotografia 3. Vista de la màquina…», «Taula 6. Resum dels assaigs de laboratori…»); cal capturar-ne el número. Esforç S; guany:
  saber si la numeració és bona (avui és una creença).
- **Imatges**: cinc figures per informe (plànol de situació, ortofoto, mapa geològic, tall de correlació, cullera SPT) més 3-4 fotos.
  No hi ha veritat comparable per text. Proposta mínima: un full de control visual (7 projectes × 5 figures: hi és / és la correcta /
  retall i mida) fet UNA vegada a mà a partir dels `.docx` de `~/g3dt-e2e/informes-mesura/`; després, un test de presència (la
  imatge existeix, no és el `PLACEHOLDER`) a M341. Esforç M la primera vegada, S després.

### Bloc 4-bis — Imatges figura a figura — *pas 1 i pas 2 FETS; pas 3 = 8 peces mesurables*

> **Estat 2026-09-07 (tarda-3).** Pas 1 (`7163f7b`): veritat des dels 7 signats, inventari de 291 candidats (FH11), aparellament, 7 fulls
> (`docs/imatges/INVENTARI-I-VERITAT-2026-09-07.md`). Pas 2 (DECISION-LOG 2026-09-07 (tarda-3), D0-D14): la font és el que l'Eva ja té al projecte
> (PNG d'ALTRES, annexos FH11/PDF, pàgines del projecte), el lector és Claude Code, B (ICGC per UTM) només de reserva, mai dibuixem punts; plantilla
> amb figures variables (1-2 situació, 0-1 assaigs, 0-2 projecte, geològic, tall), `fig_aerea` fora, materials una vegada; `_cache_name` a producció
> (`123b4f2`). Pastís de Rubí: fora (gràfic per dades del projecte quan el GTL doni percentatges). Preguntes 30-34 i 36 (35 dins la 19a).

> **Peça 0 FETA (tarda-4)** (DECISION-LOG 2026-09-07 (tarda-4)): M341 mesura ara cada figura del signat contra la nostra (M · C · X · ND, un a un,
> sobrants; `imatges_font.py`, `--remeasure`). **Referència per a les peces 1-7: `2026-09-07-m341-peca0b`** = 12 M · 5 C · 26 X · 13 ND → 40 %
> (situació 0/8, assaigs 0/6, projecte 0/5, geològic 0/7, tall 5 C + 2 X, fotos DPSH 4/7, sondeig 1/3, materials 6/9, vista 1/4); escalars 74 %,
> taules 82 % i presència idèntics a `-bloc4b`.

**Inventari complet del que queda d'imatges: `docs/imatges/PENDENTS-IMATGES.md`** (estat per ranura, les 4 peces que queden amb el que
necessita cadascuna, 6 pendents que no són cap peça, 4 bloqueigs de fons, 9 preguntes obertes i l'ordre recomanat).

Peces del pas 3, en ordre, cada una amb baseline (`peca0b`) i mesura a M341:
0. ✅ mesura per figura «mateixa font que l'Eva» (phash/NCC contra `veritat/`) — S
1. ✅ plantilla petita: aèria fora, materials una vegada, pastís i media morts fora — S (tarda-5: `fix` net 0 com previst, imatges intactes,
   sobrants 0, informes −8,5 MB; **referència ara `2026-09-07-m341-peca1b`**; la numeració la mou la peça 7)
2. ✅ fotos amb el lector d'imatges (skill `g3dt-llegir-fotos` + exemplars leave-one-out + annex de fotografies) — M (vespre: imatges
   40 → 44 %, materials 7/9 sense cap X, sondeig 2/3, vistes 2/4; DPSH 3/7 i vista de Vilanova = empats sense criteri, preguntes 37-38;
   **referència ara `2026-09-07-m341-peca2`**)
3. ✅ tall retallat (`automation/imatges/retall.py`, geometria del PDF; no cal l'MCP plànols) — S (nit: `fig_tall` 0 → 3 exactes,
   86 %; imatges 44 → 47 %; **referència ara `2026-09-07-m341-peca3`**)
4. assaigs: retall del dibuix amb punts — M
5. situació: PNG → annex recompost → insets → ICGC — M
6. geològic: PNG → ICGC → IGME — S
7. projecte 0-2 + bloc variable a la plantilla — M

### Bloc 5 — Castellà — *L, 2-3 dies; decisió del Josep: sí, més endavant*

Vilanova i Anciles són el sostre de tots els grups (narrativa ES 50 %, taules 64-74 % amb «Tipus IV»↔«Tipo IV» com a CLOSE).
Què cal: (1) plantilla `.docx` en castellà (489 paràgrafs; les fórmules ES ja existeixen a `narrative_criteria` i
`adjacent_formatter`), (2) camp «Idioma de l'informe» al wizard (`report_language` ja és a `user_data` i `ReportData`), (3) taules
i peus en castellà (capçaleres «Tipo de edificación considerada», «Tabla 3 y 4»), (4) mesura amb els 2 signats ES i les veritats
refrescades. Pregunta 19b a l'Eva (quants informes fa en castellà l'any) decideix si val la pena.

### Bloc 6 — Cablejats petits que esperen l'Eva

`lab_tests_text` dels 3 projectes sense GTL (pregunta 20c), `access_street` d'Alcoletge (camí privat, pregunta 16), `sulfate_level_name`
(pregunta 13), `seismic_ab_text` de Rubí (la base NCSE-02 diu 0,04 g; l'Eva escriu 0,08 g: pregunta nova) i Anciles (Aragó, fora de
la base: 0,05 g), P4 (N20 global o del tram, pregunta 6).

### Bloc 7 — Producció (decisió, no feina)

`production/g3dt-eva-v1` té `c46bc69` (plantilla 2.1.1) sense pujar. Les peces 1-3 de la narrativa, els adjacents per RC i els
criteris de càlcul viuen a `experiment/nivell-a-2026-08`. Quan i com arriben a l'Eva és decisió del Josep (mai pull/merge proposat a
l'Eva).

## 2. Per què aquest ordre

1. **Bloc 1 primer** perquè és l'únic que mou dos grups alhora (calc i taules) als quatre projectes fluixos, no depèn de cap resposta
   de l'Eva (excepte `sulfate_level_name`) i les causes ja estan diagnosticades.
2. **Bloc 2 després** perquè són guanys barats de format (milers, plantes, honorífic, article, litologia curta) i cada un tanca 3-5
   cel·les; les que depenen de l'Eva (arquitecte, N30, cota) esperen la reunió.
3. **Bloc 3 abans de creure cap número d'A**: si la veritat és el paràgraf equivocat, la cel·la és vermella faci el que faci el sistema.
4. **Bloc 4** quan els grups mesurats estiguin estables: primer saber què mesurem, després mesurar el que falta.
5. **Bloc 5 (castellà)** quan el Josep digui; és el més llarg i no toca cap criteri.

## 3. Preguntes a l'Eva que desbloquegen cel·les (ja registrades a `docs/PREGUNTES-EVA-PENDENTS.md`)

1 (N30 Bell-lloc), 2 (cotes relatives), 6 (P4 N20), 7 (SPT/MA), 9 (Vilanova superfícies), 13 (nivell de la mostra), 16-19 (adjacents,
estat del solar, estructura, fotos i castellà), 20-21 (assaigs, estat del solar). Noves d'aquest pla: persona/despatx de l'arquitecte
(1.7), sísmica de Rubí (0,04 / 0,08), data doble de camp a Bell-lloc.

## 4. Com es mesura cada bloc

Les cel·les que un bloc fa PERDRE a consciència s'anoten a `docs/REGISTRE-PERDUES-MESURA.md` (append-only: per què, com es reobre,
estat), perquè es puguin revisar més endavant.

Sempre igual: `mesura_341.py <run>` + `diff` dels `_compare_341.txt` per projecte contra `2026-09-07-m341-peca3`, i
`mesura_informe.py <run>` contra `2026-09-07-informe-peca3` (les 11 taules han de quedar idèntiques o millorar cel·la a cel·la).
Mai titulars: cel·les. Bloc 3 canvia la veritat: mesurar amb el codi SENSE tocar abans i després del refresc, per aïllar-ne l'efecte.
