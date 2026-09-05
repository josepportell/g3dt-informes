# DECISION-LOG — G3DT (production/g3dt-eva-v1)

Registre append-only de decisions arquitectòniques i estratègiques de la branca
de producció. Cada entrada datada. Per revisar una decisió passada, s'escriu una
NOVA entrada que la supera (amb enllaç a l'antiga).

---

## 2026-06-04 — Fix: fitxers no-imatge en rols de foto trenquen el render de l'informe

### Context
Eva va reportar un informe que fallava amb `Template rendering failed:` amb el
missatge **BUIT**. Projecte: `3001706 C.TULIPA CERDANYOLA` (2 cases, 4 DPSH +
1 sondeig). Pista crítica del Josep (punt 4): a G3DT havien esborrat el PDF de
l'annex que sospitàvem que causava l'error i **es reproduïa idèntic** → calia
diagnòstic empíric, sense suposicions.

### Decisions arquitectòniques clau
1. **Reproduir en local abans de tocar codi.** Worktree `debug/tulipa-render-error`
   des de `production/g3dt-eva-v1`, còpia neta del projecte a la carpeta de
   projectes, run de zero.
   **Why:** el log de producció NO captura el render crash (no es registra cap
   traça). Calia reproduir per obtenir la causa exacta. Paritat de versió
   confirmada fent coincidir els números de línia del `g3dt.log.txt` de G3DT amb
   el codi font del worktree.
   **Alternativa rebutjada:** parchejar a cegues segons la hipòtesi inicial (el
   PDF com a foto "site") — refutada pel punt 4.
2. **Filtrar per extensió a la via de rols, no només defensa al render.**
   **Why:** la causa arrel és que `discover_photos()` no filtrava extensions a la
   via de rols de SmartScan (la via slug sí ho feia). Atacar només el símptoma al
   render deixaria el fitxer no-imatge entrant al pipeline. Es fan ambdues coses:
   filtre a l'origen (Fix 1) + validació defensiva al moment de crear la imatge
   (Fix 2).
3. **Validar amb el mateix mecanisme que python-docx** (`docx.image.image.Image.from_file`)
   dins `_safe_inline_image`.
   **Why:** valida EXACTAMENT el que farà `doc.render()` → cap fals positiu/negatiu.
   **Alternativa (PIL):** menys fidel al que python-docx accepta de debò.
4. **Reconèixer `FOTOGRAFIA` (singular)** a `_find_photos_dir`.
   **Why:** així les fotos reals (jpegs) s'usen com a foto "site" en lloc de caure
   a placeholder. Trade-off acceptat: petit augment d'abast, validat end-to-end.

### Implementació
- `automation/image_manager.py`: constant `PHOTO_IMAGE_EXTS`; filtre a Priority 1
  + 1b de `discover_photos`; helper `_safe_inline_image` aplicat als **17** llocs
  de creació d'`InlineImage` de `build_context`; `_find_photos_dir` reconeix
  `FOTOGRAFIA` + glob `FOTOGRAF*`.
- `automation/report_generator.py`: el missatge d'error del render inclou
  `type(e).__name__` + `logger.exception(...)` (mai més un missatge buit).
- `tests/test_image_manager_safe.py`: 6 tests (filtre rol Priority 1 i 1b,
  `_safe_inline_image` OK/None, FOTOGRAFIA singular).
- ~259 insercions / 62 supressions. Commit `03f589f`, merge `d4675c6`.

### Validació empírica
- Bug **reproduït de zero**: `success=False`, `errors=["Template rendering failed: "]` (buit).
- Causa **aïllada per sonda per-imatge**: dels 17 `InlineImage`, només
  `photo_site_image_1` (el PDF) petava amb `UnrecognizedImageError` (`str(e)` buit).
  Traça completa capturada (`_ImageHeaderFactory` → `raise UnrecognizedImageError`).
- **Punt 4 explicat i provat:** és un projecte de 2 cases → 2 PDFs de fotografies
  (`_CASA 1.pdf`, `_CASA 2.pdf`). En esborrar el de CASA 1, SmartScan agafa el de
  CASA 2 com a `field_photo` → mateix crash. Per això esborrar "el PDF" a G3DT no
  servia de res.
- **Post-fix:** informe generat correctament (`success=True`, docx 11.8 MB).

### Tests
- 6 tests nous. Suite: 967 passed (base 962 + 5 nous executats; +1 afegit després).
- 31 fallades + 13 errors **pre-existents** (fixtures absents a `reference-material/`),
  IDÈNTIQUES amb i sense el canvi (comparació via `git stash` al mateix worktree) →
  **0 regressions**.

### Limitacions conegudes
- SmartScan SEGUEIX classificant el PDF d'àlbum de fotos com a `field_photo`. El fix
  evita el **crash**, no la mala classificació. Millora futura: ensenyar SmartScan a
  no rotular PDFs d'àlbum com a `field_photo`, o convertir-ne la 1a pàgina a imatge.
- Les 31 fallades de fixtures de `reference-material/` queden pendents (entorn de
  test local, no afecta producció).

### GO/NO-GO
- ✅ Bug reproduït i causa exacta localitzada (sense dubtes)
- ✅ Fix implementat → revisat (APPROVE, 0 critical / 0 warning) → testejat
- ✅ 0 regressions vs base; end-to-end verificat
- ✅ Merged a `production/g3dt-eva-v1` (`d4675c6`)
- ⏳ Desplegament a l'ordinador d'Eva (acció del Josep)

### Següents passos
- Josep: desplegar a la instal·lació d'Eva (`git pull` a la màquina de prod).
- (Opcional) Millorar SmartScan perquè no rotuli PDFs d'àlbum com a `field_photo`.

*Fi entrada 2026-06-04. Fix render crash per fitxer no-imatge en rol de foto (Tulipa).*

---

## 2026-06-05 — Fix: cop d'SPT a rebuig ("50R") col·lapsa els nivells geològics a 1

### Context
Eva reporta que l'automatització detecta **menys nivells geològics** dels reals
("1 quan n'hi ha 2/3") i que passa **a tots els projectes, sempre**. Josep aporta
la carpeta de debug de `3001706 C.TULIPA CERDANYOLA` (2 cases) copiada de la
màquina d'Eva. Veritat-terreny: el **tall de correlació** llista 3 nivells
(Nivell 1 sorres llimoses; Nivell 2 llims argilosos; Nivell 3 substrat alterat).
Criteri d'Eva (confirmat 2026-03-13): els nivells surten de la columna "Unitat
litològica" de l'**annex formatat**, no del nombre de materials.

### Decisions arquitectòniques clau
1. **Diagnòstic empíric abans de tocar codi.** Còpia neta a `projectes-debug/`,
   reproducció amb dades reals. Traça: `load_sondeig_merged` retornava 0 assaigs
   → `num_soil_levels=1`; sanejant el cop "50R" es recuperaven els 3 nivells.
   **Why:** la cache ja tenia l'annex amb `num_geological_levels:3` correcte → el
   bloquejant era el normalitzador, no la visió. Causalitat aïllada sense dubtes.
2. **Protegir la suma de cops contra rebuig, NO fabricar N.** Helper
   `coerce_blow_int()`: enter si el cop és numèric net, `None` si és rebuig
   ("50R","R",...). Si algun increment no és numèric, `n_spt` queda None.
   **Why:** el recompte de nivells és independent de `n_spt`; protegir la suma
   restaura els nivells sense inventar cap N a rebuig.
   **Alternativa rebutjada:** extreure "50R"→50 i sumar — fabricaria un N de
   rebuig, i la **regla canònica de Nb a rebuig és pregunta oberta a Eva**
   (blocker STATUS). **Trade-off:** a rebuig la cel·la N queda buida (igual que el
   `n_spt:null` que ja dóna la visió).
3. **`logger.warning` enlloc de `except Exception: pass`** a `load_sondeig_merged`.
   **Why:** el swallow silenciós és exactament per què el bug va passar
   desapercebut. Un fitxer dolent no ha de matar el wizard, però SÍ registrar-se.
4. **Protegir les 3 sumes, no només la del normalitzador.** El reviewer va trobar
   un duplicat a `wizard_service._compute_mapping_prefills` que petava igual i
   deixava caure 4 prefills SPT (`spt_n30`/`depth_range`/`lithology`/`location`)
   en silenci. **Why:** sense això el fix no és complet end-to-end.

### Implementació
- `automation/vision_normalizer.py`: helper públic `coerce_blow_int()`; guard a
  `_normalize_sondeig_spt_fields` i `_normalize_dpsh_spt_fields`; 2 `except: pass`
  → `logger.warning`.
- `web/wizard_service.py`: mateix guard al N30 duplicat (~línia 1782).
- `tests/test_vision_normalizer.py`: 6 tests (rebuig a index 1 i 2, numèric intacte,
  fitxer malformat → warning sense raise). ~202 ins / 12 supr.
- Commit `7be711f` (FF damunt `acf3621`). Mateix fix a dev `experiment/ai-pipeline`
  (`af3b2f4`; wizard_service.py divergeix → guard a línia diferent).

### Validació empírica
- BEFORE: `load_sondeig_merged(Tulipa)` → 0 assaigs → `num_soil_levels=1`.
- AFTER (cop sanejat): S-1 `num_geological_levels=3`, 5 capes → `num_soil_levels=3`.

### Tests
- 6 tests nous. Suite sobre base prod: **974 passed**, 31 fallades **pre-existents**
  (9 ai-pipeline 404, 18 smartscan fixtures absents, 3 fileminer, 1 bearing),
  idèntiques amb/sense el canvi (`git stash`) → **0 regressions**.

### Limitacions conegudes
- **Regla canònica de Nb a rebuig** pendent d'Eva (blocker STATUS). El fix deixa
  `n_spt=None` a rebuig.
- **Misclassificació del full de sondeig de camp**: a Tulipa el classificador va
  triar l'Albarà en lloc del full real. Important per a projectes SENSE annex
  formatat. Separat.
- **Merge descarta assaigs de l'annex quan `num_geological_levels` és None** (cas
  Linyola). Gap d'extracció separat.

### GO/NO-GO
- ✅ Bug reproduït i causa exacta aïllada (crash empassat → annex descartat)
- ✅ Fix implementat → revisat (APPROVE) → testejat (0 regressions) → re-aplicat
   sobre la base de prod amb el seu propi loop
- ✅ Merged a `production/g3dt-eva-v1` (`7be711f`) i pujat a origin
- ⏳ Desplegament a Eva (`git pull` dilluns 2026-06-08, junt amb el render-fix)

### Següents passos
- El fix viatja amb el pull de dilluns 2026-06-08.
- Reconciliar amb Eva si són 2 o 3 nivells (els documents diuen 3); no canvia el fix.
- (Futur) Tancar els 2 gaps separats: misclassificació full de camp + annex amb
  `num_geological_levels` None.

*Fi entrada 2026-06-05. Fix: cop d'SPT a rebuig col·lapsa els nivells geològics a 1.*

---

## 2026-06-06 — Addendum: el report encara col·lapsa els nivells (bug #2, descobert generant el .docx)

### Context
Generant l'informe de Tulipa amb el fix de rebuig (`7be711f`) aplicat, el `.docx`
**encara narra "1 nivell geotècnic"** i només descriu el ferm (lutites). Supera
parcialment l'entrada 2026-06-05: aquell fix corregeix el **prefill del wizard**
(`num_soil_levels` 1→3) i el crash, però NO el text del report.

### Causa #2
`automation/report_data.py::_generate_soil_levels` (~línia 1137):
`if num_levels < len(sondeig_layers): → un sol nivell fusionat`. Per Tulipa
`num_soil_levels=3 < len(capes)=5` → col·lapsa a 1. Ignora el camp `geological_level`
de cada capa (annex: `1,1,2,3,3` → 3 grups). El comptador del report és
`len(soil_levels)` (`section3_geologia.py:704`, `section4_conclusions.py:126`,
`report_generator.py:1155`), NO `num_soil_levels`. El flag `merge_to_single_level`
(`report_data.py:521`) era la via PREVISTA per fusionar a 1; la branca 1137 és el bug.

### Fix proposat (NO implementat — decisió ajornada pel Josep)
Agrupar `sondeig_layers` per `geological_level` → produir `num_geological_levels`
SoilLevels (fusionant les capes de cada grup); fallback a la lògica actual quan no
hi ha el camp. **Risc:** canvia `soil_levels` per a TOTS els projectes → validar
contra els 7 de referència (Bell-Lloc ha de seguir = 1: 2 capes totes `gl=1` → 1 grup).

### Estat
- ⏳ Bug conegut, documentat. Implementació ajornada.
- Pregunta de mètode per l'Eva: el report ha de descriure 3 nivells geològics (el
  tall de correlació en dibuixa 3) o col·lapsar al ferm per al càlcul?
- LLIÇÓ: generar el `.docx` (prova end-to-end real) ABANS de donar per tancat un
  fix de nivells; el prefill correcte no garanteix el report correcte.

*Fi entrada 2026-06-06. Addendum: report-narrative encara col·lapsa nivells (bug #2, _generate_soil_levels).*

---

## 2026-06-06 — Resolució bug #2: agrupar `sondeig_layers` per `geological_level`

### Context
Resol el bug #2 documentat a l'addendum anterior i al dossier
`docs/BUG-NIVELLS-GEOLOGICS-ANALISI.md`. El fix del rebuig (`7be711f`) corregia el
**prefill** del wizard (`num_soil_levels` 1→3), però el `.docx` de Tulipa **encara
narrava "1 nivell geotècnic"** i només descrivia el ferm. Abans de tocar codi es va
fer arqueologia completa del *per què* (a petició del Josep).

### Diagnòstic (per què el codi era així)
`_generate_soil_levels` (`report_data.py`) va néixer amb l'assumpció heretada
**«1 SoilLevel = 1 material del sondeig»**: tota la lògica gira sobre
`len(sondeig_layers)` (materials) i `num_soil_levels` només és un **interruptor
binari** (≥ → un nivell per material; < → col·lapse a EXACTAMENT 1). La branca de
col·lapse (`num_levels < len(sondeig_layers)`) es va afegir al commit `57c9bd3`
(2026-03-03) per arreglar Bell-Lloc (2 materials → 1 nivell). **Va "funcionar" per
coincidència del cas degenerat** (Bell-Lloc volia 1, i col·lapsar sempre dona 1). El
camp `geological_level` (columna "Unitat litològica", criteri canònic d'Eva) viatja
a cada capa però la funció **mai el llegia** (`git log -S geological_level --
report_data.py` = buit). Tulipa: 5 materials amb `geological_level=[1,1,2,3,3]` → 3
grups, però `3 < 5` disparava el col·lapse-a-1.

### Decisions arquitectòniques clau
1. **Agrupar per `geological_level`, no per nombre de materials** (Opció A,
   confirmada pel Josep). `geological_level` és la veritat-terreny del recompte;
   `num_soil_levels` només override **a la baixa**.
   **Why:** en el pipeline normal `num_soil_levels` ja s'omple de
   `num_geological_levels` (mateixa columna de l'annex que dona els `geological_level`
   per capa) → el recompte correcte JA hi és; l'únic error era comparar contra els
   materials. **Alternatives rebutjades:** B (num_soil_levels com a objectiu exacte
   amb fusió/divisió de grups arbitraris — ambigu) i C (ignorar num_soil_levels al
   recompte — Eva perdria l'override de col·lapsar).
2. **Single-sourcing de la lògica de col·lapse.** El cos de col·lapse antic es va
   refactoritzar a una closure `_collapse_to_single()` cridada des de DUES branques
   (el nou `n_groups==1`/override i el fallback llegat `num_levels < len(...)`).
   **Why:** garanteix que el cas 1-grup (Bell-Lloc i similars) doni sortida
   **byte-idèntica** a abans → zero regressió. Verificat per reviewer amb `git show`.
3. **Fallback intacte quan no hi ha `geological_level`.** El helper retorna `None`
   si qualsevol capa no té el camp (sondeig sintetitzat per `dpsh_segmenter`, o full
   de camp sense columna) → cau a la lògica per-material actual, sense canvis.

### Implementació
- `automation/report_data.py`: nou `_group_layers_by_geological_level()` (runs
  consecutius de `geological_level` → llistes d'índexs globals, o `None`); dins
  `_generate_soil_levels`, branca d'agrupació (1 SoilLevel per grup; N20 al sub-rang
  de ferm del grup, límit superior tret per a l'últim grup) + closure
  `_collapse_to_single()`.
- `tests/test_soil_levels_grouping.py`: NOU, 7 tests.
- `docs/BUG-NIVELLS-GEOLOGICS-ANALISI.md`: dossier complet (anàlisi + disseny).

### Validació empírica
- **Tulipa end-to-end** (`.docx` regenerat des de la còpia de debug): narra
  **"s'han identificat 3 nivells geotècnics"** + genera les 3 subseccions
  (3.2.1 1er / 3.2.2 2n / 3.2.3 3r Nivell). Abans: 1.
- Annex Tulipa: `geological_level=[1,1,2,3,3]`, `num_geological_levels=3`.
- **Bell-Lloc**: `[1,1]` → 1 grup → ruta `_collapse_to_single()` → sortida idèntica.

### Tests
- 7 nous. Suite completa: **981 passed** (974 base + 7). Failure sets **byte-idèntics**
  amb/sense el canvi (`git stash` + comparació) → **0 regressions**. 31 fallades +
  13 errors pre-existents (ai-pipeline 404, smartscan fixtures absents, fileminer,
  bell-lloc bearing, collection errors) inalterats.

### GO/NO-GO
- ✅ Diagnòstic arqueològic complet (commit d'origen + per què identificats)
- ✅ Implementer → reviewer (APPROVE, 0 critical/0 warning) → tester (0 regressions)
- ✅ Gate end-to-end verd (Tulipa 3 nivells; Bell-Lloc idèntic)
- ⏳ Desplegament: viatja amb el `git pull` d'Eva de dilluns 2026-06-08 (junt amb
  bug#1 refusal-fix + render-fix)

### Limitacions conegudes
- Misclassificació del full de sondeig de camp (Albarà vs full real) — gap separat.
- Annex amb `num_geological_levels` None (Linyola) → `groups=None` → fallback actual.
- Regla canònica de Nb a rebuig — blocker obert amb Eva, independent del recompte.

### Següents passos
- Pull d'Eva dilluns 2026-06-08; reiniciar el wizard.
- Reconciliar amb Eva si Tulipa són 2 o 3 nivells (els docs diuen 3) — no canvia el fix.
- 2 hardenings de seguretat (guard `depth_to_m` None + comentari d'ordenació) en
  commit de seguiment.

*Fi entrada 2026-06-06. Resolució bug #2: agrupació de nivells per geological_level.*

## 2026-06-23 — Champion-challenger: Via A (OBRA parser) vs Via B2 (visió pressupost)

### Context
`fix/pipeline-routing`: primera implementació del pipeline de site_address via documents pressupost.
Via A (extracció determinista Python) i Via B2 (visió Claude dedicada al pressupost) es van executar
en paral·lel sobre els 7 projectes de referència accessibles (Linyola exclòs: fitxer sense nom estàndard).
Les comparacions guien la decisió de quins camps reconnectar a consumidors existents.

Commits:
- `b11043c` — Via A: OBRA parser + glob widening (`PRESSUPOST*|PRESUPUESTO*`) + num_dpsh_tests regex
- `3c87cc6` — Via B2: `PRESSUPOST_EXTRACTION_PROMPT` + `_find_pressupost_pdf()` + injecció a `_run_vision_fast`

### Resultats (7 projectes; GT = ground truth de ANALISI §4.3)

**Via A (docs_extracted.json — extracció Python OBRA parser):**

| Projecte | site_address | num_planned_dpsh | client/architect | building_category |
|----------|-------------|-----------------|-----------------|-------------------|
| VACARISSES | ✅ `C/DE LA BARCELONETA 23, VACARISSES` | ✅ 3 | ✅ MARC VIDAL | ❌ None |
| CASTELLAR  | ❌ `C/ARBRELLS 18A-18B-20, …` (GT: 18A) | ✅ 4 | ⚠ WOOD COMFORT (promotor, no client) | ❌ None |
| RUBI       | ✅ None | ✅ 3 | ✅ JOANA MARTINEZ | ❌ None |
| BELL-LLOC  | ✅ `C/MESTRE RAMON ORTIZ 15, BELL-LLOC` | ✅ 2 | ✅ ARQ. BOSCH NOVELL | ❌ None |
| ALCOLETGE  | ✅ `C/GIRASOLS 7, URB.EL ROSER, ALCOLETGE` | ✅ 3 | ✅ SANS BONVEHI | ❌ None |
| VILANOVA   | ✅ `C/ STA. GEMMA 4, URB.LA SERRA, VILANOVA DE SEGRIA` | ❌ None (regex CA falla ES) | ❌ `C/ STA. GEMMA 4, …` (captura l'adreça en lloc del client) | ❌ None |
| ANCILES    | ✅ `C/GENERAL FERRAZ 20, ANCILES (HUESCA)` | ❌ None (regex CA falla ES) | ❌ `ESTUDIO GEOTECNICO` (captura nom projecte) | ❌ None |

Correctesa: site_address 6/7 (Castellar té "18A-18B-20" al pressupost, potser correcte), num_planned_dpsh 5/7, client 4/7, building_category 0/7.
Problemes Via A: regex DPSH no cobreix text ES; regex `num_planned_sondeig` massa laxa (3 espuri a Castellar i Bell-lloc); `architect_company` en PDFs ES captura línies errònies (adreça, nom projecte).

**Via B2 (pressupost_extracted.json — Claude vision):**

| Projecte | site_address (B2) | municipality | num_planned_dpsh | client_name | building_category |
|----------|------------------|-------------|-----------------|-------------|------------------|
| VACARISSES | ✅ `C/DE LA BARCELONETA 23` | ✅ VACARISSES | ✅ 3 | ✅ MARC VIDAL | ✅ C0 |
| CASTELLAR  | ✅ `C/ARBRELLS 18A` | ✅ CASTELLAR DEL VALLES | ✅ 4 | ✅ GRUP ALMA CONSTRUCCIONS | ❌ None (no C0-C3 al doc) |
| RUBI       | ✅ None | ✅ RUBI | ✅ 3 | ✅ JOANA MARTINEZ | ✅ C0 |
| BELL-LLOC  | ✅ `C/MESTRE RAMON ORTIZ 15` | ✅ BELL-LLOC | ✅ 2 | ✅ ARQ. BOSCH NOVELL | ✅ C1 |
| ALCOLETGE  | ✅ `C/GIRASOLS 7, URB.EL ROSER` | ✅ ALCOLETGE | ✅ 3 | ✅ SANS BONVEHI | ✅ C0 |
| VILANOVA   | ✅ `C/ STA. GEMMA 4, URB.LA SERRA` | ✅ VILANOVA DE SEGRIA | ✅ 3 | ✅ GRUPO CUENCA GUERRERO SL. | ✅ C0 |
| ANCILES    | ✅ `C/GENERAL FERRAZ 20` | ✅ ANCILES (HUESCA) | ✅ 5 | ✅ RETRATERIA, ALBA BARRAU CASTAN | ❌ None (no C0-C3 al doc) |

Correctesa: site_address 7/7, municipality 7/7, num_planned_dpsh 7/7, client_name 7/7, building_category 5/7 (2 docs no la contenen).

**Diferència clau B2 vs A per a site_address:** B2 separa street (site_address) de municipality com a camps independents. A combina "STREET, MUNICIPALITY" en un sol valor (input per a `_split_address`). B2 val correctament "18A" per a Castellar on A extreu el literal "18A-18B-20" del text PyMuPDF.

### Decisions arquitectòniques clau

**1. `site_address` → Via A guanya (format compatible amb consumers existents)**
- **Why:** Via A produeix "STREET, MUNICIPALITY" directament consumible per `wizard_service.py:2001-2020` via `_split_address()`. B2 separa en dos camps nous; reconnectar-ho requeriria canviar la capa de merge o crear un nou concepte. El guany és marginal (6/7 vs 7/7; la diferència de Castellar és `18A` vs `18A-18B-20` — ambdues vàlides des del pressupost).
- **Trade-off:** Castellar: B2 és lleument més net, però no justifica el canvi de consumers.
- **Limitació Via A:** si la parcel·la té múltiples números ("18A-18B-20"), A transmet el literal i B2 simplifica. Decisió: acceptable — la geocodificació posterior tolera els dos formats.

**2. `municipality` → Via B2 guanya (camp nou, no produït per A)**
- **Why:** Via A no emet `municipality` mai (embarcat dins site_address). B2 el dóna net (7/7). Útil per a fallback de geocodificació quan no hi ha adreça de carrer (Rubí). A reconnectar via `pressupost_extracted.json → wizard_service`.
- ⏳ **Pendent:** connexió al consumer (fora de scope d'aquesta fase).

**3. `num_planned_dpsh` → Via A suficient per CA, Via B2 per ES**
- **Why:** Via A regex funciona 5/5 en PDFs CA; falla 0/2 en PDFs ES (Vilanova, Anciles). B2 és 7/7.
- **Opció A:** afegir regex ES a `_extract_docs_python` (`ensayos de penetración dinámica`). Cost baix, fiable, no depèn de visió.
- **Opció B:** reconnectar `num_planned_dpsh` de `pressupost_extracted.json` com a fallback quan A és None.
- **Decisió:** Via A + parxear regex ES (independent d'aquesta fase). Anotat com a millora pendent.

**4. `client_name` → Via B2 guanya (labeling correcte + ES fiable)**
- **Why:** Via A captura `architect_company` del bloc OBRA (primer camp post-OBRA) — és un nom de client o promotor, no arquitecte. Per a PDFs ES, la classificació falla completament (Vilanova: captura l'adreça; Anciles: captura "ESTUDIO GEOTECNICO"). B2 identifica el bloc CLIENT i extreu el camp correctament en ambdues llengues.
- **Decisió:** `client_name` prové de `pressupost_extracted.json`. A reconnectar via wizard_service quan s'implementi la fase de consumers.
- **Nota:** `architect_company` del bloc OBRA és una entitat diferent (promotor/client, no arquitecte); la label és errònia. Tasca independent: "entity confusion fix".

**5. `building_category` → Via B2 guanya (Via A 0/7 per problema amb apostrofes)**
- **Why:** Via A té regex `r"Tipus\s*(?:d[\'e]\s*)?edifici\s*[:\s]*\s*(C[0-3])"` però PyMuPDF extreu l'apostrofació com a `'` (Unicode) no `'` (ASCII), evitant el match. B2 llegeix visualment i extreu 5/7 (2 docs no contenen building_category).
- **Decisió:** Si cal building_category, usar `pressupost_extracted.json`. Parxar regex Via A (substituir `\'` per `[''']`) com a millora pendent — no bloqueja.

**6. `num_planned_sondeig` i `num_planned_spt` → Via B2 guanya**
- Via A `num_planned_sondeig` té falsos positius (3 espuri a Castellar i Bell-lloc — el "3" prové del num de plantes o d'un altre context). B2 és 7/7 correcte. SPT Via A: no implementat. B2: 5/7 (2 cases: SPT inclòs dins sondeig sense count separat).

### Implementació
- `docs/PLA-SITE-ADDRESS-I-VISIO-PRESSUPOST.md` — pla vigent
- `automation/validation/prompts.py:492-621` — PRESSUPOST_EXTRACTION_PROMPT
- `web/vision_fast.py:119-136` — Step 2b injection; `488-521` — `_find_pressupost_pdf()`
- JSON output: `{project}/validation/pressupost_extracted.json` (7 projectes generats)

### Validació empírica
- Via B2: 7/7 execucions OK, ~41-95s per projecte (visió Claude)
- Via A (OBRA parser): 6/7 site_address (Castellar: "18A-18B-20" vs GT "18A")
- Regressió: 32 failed / 981 passed — sense canvis

### Limitacions conegudes
- **Linyola (8è projecte):** sense `PRESSUPOST*` ni `PRESUPUESTO*` al nom del fitxer — no descobert per cap via. Limitació coneguda, documentada.
- **Castellar 18A vs 18A-18B-20:** PyMuPDF extreu el literal del PDF. B2 interpreta el "primer número" com a adreça principal. Cal verificar el doc original.
- **Client vs promotor:** el camp `architect_company` de Via A és en realitat el promotor/client — el nom és enganyós. Tasca separada ("entity confusion") per corregir la label i el concepte.
- **`num_planned_dpsh` Via A per ES:** fix pendent (afegir regex `ensayos de penetración dinámica`).
- **`building_category` Via A:** fix pendent (apostrofació Unicode).

### GO/NO-GO
- ✅ Via B2 implementada i validada (7/7)
- ✅ Via A OBRA parser implementada i validada (6/7; Castellar diferència acceptable)
- ✅ Decisions per camp documentades
- ⏳ Consumers no reconnectats (scope d'una fase posterior)
- ⏳ Millores pendent: regex ES per DPSH, apostrofació building_category

### Següents passos
1. Actualitzar ANALISI §4.5 (site_address diagnosis post-fix)
2. Opcionalment: parxar regex ES de `num_planned_dpsh` a Via A (baix cost)
3. Fase consumers: reconnectar `municipality` i `client_name` de pressupost_extracted → wizard_service

*Fi entrada 2026-06-23. Champion-challenger Via A vs Via B2: 7 projectes comparats, decisions per camp.*

---

## 2026-06-24 — `signals_emitted: 0` desmentit + fix acotat de NIFs de proveïdor

### Context
Revisant les anotacions del Josep a `ANALISI-PIPELINE-DEBUG-VACARISSES.md` (§2.2),
dues preguntes obertes: (1) per què `signals_emitted: 0` al concept_map si la
carpeta `ACCEPTACIO/` conté bones dades, i (2) si A2 ("desactivar la regla
ignorar ACCEPTACIO") les recuperaria. La hipòtesi de l'anàlisi era: *la pipeline
perd les dades d'ACCEPTACIO, s'ignoren*.

### Decisions arquitectòniques clau

**1. La hipòtesi és falsa — ACCEPTACIO NO s'ignora per al flux de dades.**
Verificat empíricament (auto_extract sobre Vacarisses):
- `signals_emitted: 0` és un **literal hardcoded** a `deep_folder_classifier.py:325`.
  Mai es calcula, i **cap codi el llegeix** (només apareix al JSON). No és evidència
  de pèrdua; ens va enganyar a nosaltres llegint el fitxer.
- `file_scanner.py` marca `^ACCEPTACIO/?$` com a `acceptance_dir`, però això **només
  reté l'assignació d'un rol especialitzat** — NO treu la carpeta del mining ni del probing.
- FileMiner recorre ACCEPTACIO (no és a `_SKIP_DIRS`); ConceptScout li fa vision-probe
  (24 sources `vision_probe:budget`, conf fins 1.0); `concept_sources_to_signals` +
  `_merge_vision_signals_into_competition` els injecten a la competició.
- **Prova:** `street_address = 'C/DE LA BARCELONETA 23'` té font literal
  `vision_probe:ACCEPTACIO\Presupost Geotecnic.pdf`. Les dades arriben.
- **Conseqüència:** A2 tal com estava proposada és un **no-fix** (no canviaria el flux).
  No s'implementa. *Why:* cap fabricació — corregir un no-bug enmascara el bug real.

**2. El bug real és la competició (entity confusion), no l'exclusió.**
`vision_probe:budget` → source_type `vision_probe_other`, absent dels mapes de
prioritat → default 50 (`loader.py:88`). Per `client_nif`, el CIF de G3DT del PDF
vectorial (`pressupost_pdf`=30) guanya el NIF real del client (vision=50).

**3. Fix triat: blocklist de NIFs de proveïdor (NO retunejar prioritats).**
*Why no prioritats:* el Josep ho confirma per experiència — "guanyem unes variables
i en perdem d'altres segons quines parts del pipeline les extreguin bé; ja ho vam
intentar, és laboriós i arriscat". Pujar `vision_probe:budget` arreglaria client_nif/
client_name però arrossegaria `architect_company=G3DT` (incorrecte, §3.3 Error 4).
*Alternativa rebutjada:* re-pesar prioritats per concepte → massa efectes creuats.
*Trade-off acceptat:* el blocklist és quirúrgic però només cobreix client_nif; les
altres confusions d'entitat (architect_company, client_name messy) queden obertes.

### Implementació
- `automation/internal_addresses.py` (+44 LOC): `NON_CLIENT_NIFS = {B25461443 (G3),
  B64803075 (lab TPS)}` + `is_non_client_nif()`. Mirall de l'existent `is_g3_internal_address`
  (mateix mòdul canònic, mateixa filosofia "provider data leaking into client docs").
- `automation/fileminer/competition.py` (+24 LOC): pre-filtre a `resolve_competition`
  que elimina candidats client_nif amb NIF de proveïdor abans del rànquing (mirall del
  guard d'adreça de les línies 101-122). Si tots ho són → s'omet la variable.
- 14 tests nous (`test_internal_addresses.py` +8, `test_competition_g3_filter.py` +6).

### Validació empírica
NIFs verificats a través dels 7 projectes (escaneig de concept_maps):
`B25461443` ×16 (sempre a `PRESSUPOST GEOTEC.*.pdf` = emissor G3) i `B64803075` ×9
(sempre a `*-GTL-*.pdf` = laboratori). Constants → mai client.

Before/after (auto_extract, `client_nif`):
| Projecte | ABANS | DESPRÉS |
|----------|-------|---------|
| Vacarisses | B25461443 (G3) | 38112117J (Marc Vidal) |
| Castellar | B25461443 (G3) | B19935212 (Grup Alma) |
| Rubí | B25461443 (G3) | 38540020 |
| Bell-lloc | B25461443 (G3) | 78058457E |
| Alcoletge | B25461443 (G3) | 47690689M |
| Linyola / Vilanova / Anciles | ja correcte | sense canvi |

**5/8 projectes tenien el CIF de G3DT com a NIF del client ABANS → 0/8 DESPRÉS.**

### Tests
+14 nous. Suite completa: **32 failed / 995 passed** (baseline 32/981 inalterat, 0 regressions).

### Limitacions conegudes (NO cobertes per aquest fix)
- **Alcoletge**: `client_nif = "N.I.F./C.I.F.: 47690689M"` — valor correcte però la
  preview de visió arrossega l'etiqueta. Tasca separada de neteja (label-stripping).
  Quedava emmascarat abans perquè guanyava el CIF de G3.
- **`architect_company = "G3 DESENVOLUPAMENT..."`** segueix incorrecte (§3.3 Error 4):
  el concepte mapeja "empresa al pressupost" → arquitecte, però és el prestador G3.
  Requereix mapatge d'entitats (A4), substancial — validar amb l'Eva.
- **`client_name` messy** (Vacarisses "Marc Vidal - marc@...") segueix guanyant des
  del .msg sobre la visió neta. Mateixa família de competició/entitat.
- **Retuneig de prioritats**: deliberadament NO fet (vegeu decisió 3).

### GO/NO-GO
- ✅ Hipòtesi `signals_emitted:0` desmentida amb evidència
- ✅ Fix acotat de NIF implementat, validat 7 projectes, 0 regressions
- ⏳ Confusions d'entitat restants (architect_company, client_name) → validar amb Eva
- ⏳ Label-stripping de previews de visió → tasca separada

### Següents passos
1. Annotar la correcció de §2.2 a `ANALISI-PIPELINE-DEBUG-VACARISSES.md` (fet en aquest commit)
2. Preguntar a l'Eva sobre el mapatge architect_company vs client (A4) abans de tocar-ho
3. (Opcional) label-stripping de NIF/adreça a les previews de `concept_sources_to_signals`

*Fi entrada 2026-06-24. `signals_emitted:0` era un stub hardcoded (no pèrdua de dades); el bug real és competició; fix acotat de NIFs de proveïdor exclou el CIF de G3 i del laboratori de client_nif (5/8→0/8).*

---

## 2026-06-25 — Llacunes Via A tancades (DPSH ES, building_category, sondeig) + refactor testejable

### Context
Continuació de la sessió 2026-06-23 (champion-challenger Via A vs B2). El §4.5 de
`ANALISI-PIPELINE-DEBUG-VACARISSES.md` deixava tres llacunes del parser Python de
pressupostos (`_extract_docs_python`): `num_planned_dpsh` fallava en castellà (5/7),
`building_category` no s'extreia mai (0/7) i `num_planned_sondeig` produïa falsos
positius (Castellar/Bell-lloc). A2 ("desactivar ignorar ACCEPTACIO") es va descartar:
la seva premissa ja havia quedat desmentida el 2026-06-24 (ACCEPTACIO no s'ignora;
és un no-op). Mètode: ancorar cada regex en text **real** dels 7 pressupostos de
`/mnt/c/claude/g3dt/projectes/` abans de tocar codi (no endevinar patrons).

### Decisions arquitectòniques clau

**1. Extreure un helper pur `_parse_docs_fields(combined_text) -> dict`.**
Why: la lògica de regex vivia incrustada dins una funció amb IO (obre PDFs, escriu
JSON), impossible d'unit-testar. El helper pur separa parsing de IO → 17 tests
deterministes sense fitxers. Trade-off: una funció més; comportament idèntic
(architect_company i site_address es mouen verbatim).

**2. `num_planned_dpsh` — afegir la forma castellana a l'àncora de campanya.**
`(\d+)\s+(?:assaigs?|ensayos?)\s+de\s+penetraci[oó]n?\s+din[aàá]mica`. Cobreix CA
"assaigs de penetració dinàmica" i ES "ensayos de penetración dinámica". 5/7 → 7/7.

**3. `building_category` — apòstrof Unicode + plantilla ES.**
La plantilla CA escriu "Tipus d'edifici:" amb U+2019 (no l'ASCII `'` que la regex
antiga `d[\'e]` esperava); la ES escriu "Tipo de Edificio." amb separador punt. Nou:
classe d'apòstrof `['’‘]` + alternativa `Tip(?:us|o) … edifici[o]?` + separador
`[:.\s]+`. 0/7 → 5/7 (Castellar/Anciles no en tenen → cap valor, correcte).

**4. `num_planned_sondeig` — guard per CONTINGUT, no per distància (decisió clau).**
El problema: la capçalera de la taula de pressupost ("SONDEIG A ROTACIO…") és
**indistingible per regex** de la prosa de campanya ("1Sondeig a rotació…") — totes
dues donen un comptatge. La primera temptativa acotava una finestra de N caràcters
després del trigger de campanya, confiant que la taula queda ~900 car. avall. El
code-review ho va marcar: això funciona **per sort de maquetació**, i aquest codi té
historial de regressions en projectes nous (preocupació de la Sílvia). Decisió:
després d'ancorar la finestra, **tallar-la al primer header de secció de pressupost**
(`UNITATS D'ASSAIG…` / `UNIDADES DE ENSAYO…`), que sempre precedeix la fila SONDEIG
de la taula. La finestra de 600 car. queda com a backstop, no com a guard primari.
Alternativa rebutjada (finestra fixa sola): re-introdueix el fals positiu si el
preàmbul és curt. Principi: "cap valor és millor que un de fals".

### Implementació
- `web/vision_fast.py`: nou `_parse_docs_fields()` (~110 línies, mou + corregeix);
  `_extract_docs_python()` ara hi delega. Suggeriments del review aplicats: classe
  d'apòstrof al trigger de campanya, simplificació `\s*[:.\s]+\s*`→`[:.\s]+`.
- `tests/test_docs_fields_parser.py`: 17 tests nous (CA/ES DPSH, apòstrof Unicode,
  separador ES, sondeig present/absent, **content-cut en les dues direccions**,
  boilerplate de la clàusula d'aigua, regressions de site_address/architect_company).

### Validació empírica
7/7 contra els pressupostos reals: DPSH {Castellar 4, Rubí 3, Bell-lloc 2, Alcoletge 3,
Vilanova 3, Anciles 5}; category {Rubí/Vilanova/Alcoletge C0, Bell-lloc C1; Castellar/
Anciles absents}; sondeig {Castellar 1, Bell-lloc 1, Anciles 2; resta absent}.

### Tests
17 nous a `test_docs_fields_parser.py`. Suite completa: **32 failed / 1012 passed**
(baseline 32-failed inalterat; +14 nous respecte els 14 de la sessió NIF; passats de
995→1012 amb aquests 17 menys solapaments — tots verds). Re-review: CLEAN.

### Limitacions conegudes
- A2 descartat (no-op). El problema real d'ACCEPTACIO és la competició/entitat (§3.3),
  no l'exclusió.
- `architect_company` segueix etiquetant client/promotor com a arquitecte (A4/entity
  confusion) — no tocat aquí; requereix lògica més intel·ligent que regex (§4.3).
- Linyola: `_find_pressupost_pdf` no descobreix el PDF de nom no-estàndard.

### GO/NO-GO
✅ GO — fixes validats 7/7, tests verds, re-review net, zero regressions.

### Següents passos
1. **A1** — validació de rol amb `doc_type` del concept_map (plano topogràfic
   classificat com a `architect_plan` → dimensions fabricades). Error 1, alt risc
   (fabricació). Arrossega Error 2 (sondeig_annex rep el mateix fitxer).
2. **A3** — extractor positiu de GTL: `lab_testing_company`/`lab_location` (Eva ho
   demana: "no identifica el laboratori"). El fix de NIF de 2026-06-24 era la meitat
   negativa; falta la positiva.
3. **A4/entity confusion** — architect_company vs client_name (consultar Eva abans).

*Fi entrada 2026-06-25. Tres llacunes Via A tancades (DPSH ES 7/7, category 5/7, sondeig sense espuris); guard de sondeig per contingut, no per distància; parser refactoritzat a helper pur amb 17 tests.*

---

## 2026-06-25 (B) — A3: GTL com a font de primer ordre per al laboratori (early-return fix + registre NIF→lab)

### Context
A3, prioritat de la sessió (vegeu `_FOR-NEW-YOU-20260625-0900.md`). Queixa d'Eva:
"no identifica el laboratori". L'anàlisi (§7/§9 i Error 5) i el handoff plantejaven A3
com "no hi ha extractor de GTL; cal afegir un miner que extregui `lab_testing_company`",
i el handoff §3 afirmava que **hi havia 2-3 laboratoris diferents** i que el hardcode
"TPS PROSPECCIÓ DEL SUBSÒL SL" era **incorrecte** per Castellar/Rubí.

### Decisions arquitectòniques clau

**1. La premissa "múltiples labs" del handoff §3 és FALSA — corregida amb dades.**
Dump real dels 5 GTL (pàg. 1) + valors signats d'Eva als 7 informes de referència:
- El laboratori és **sempre `TPS, PROSPECCIÓ DEL SUBSÒL, SL`, NIF `B64803075`** (footer
  de TOTES les pàgines de tots els GTL; email `laboratorio@tps-perforaciones.com`).
- Eva escriu literalment "TPS PROSPECCIÓ DEL SUBSÒL SL" a `lab_testing_company` i
  `lab_field_company` als **7/7** informes. **El hardcode és CORRECTE** (i casa amb
  l'ortografia d'Eva *sense comes*, millor que el footer del GTL que en duu).
- El §3 va confondre el NIF `B25364589` amb el lab. Aquell NIF és del bloc **DADES DEL
  CLIENT / SOL·LICITANT del GTL = G3** (adreça "C/ Vallbona 22 - Els Omells de Na Gaia"),
  NO el laboratori. *Why important:* construir A3 sobre la premissa errònia hauria fet
  parsejar i "corregir" un nom que ja era correcte, i potencialment triar el NIF de G3.

**2. El bug REAL és un early-return, no l'absència d'extractor.**
`extract_lab_results()` retornava `LabResults()` BUIT quan `_find_lab_pdf()` no trobava
`LAB*.pdf`, **abans de mirar el GTL**. Els helpers (`_extract_sulfate`,
`_extract_sample_info`, `_extract_tests_text`) JA funcionen sobre text GTL — mai
s'invocaven per projectes GTL-only. Confirmat executant l'extractor:
- Castellar (té `LAB-SIG.pdf`) → OK, lab="TPS...".
- Vacarisses (només GTL) → TOT buit (`lab_testing_company=''`) → "no identifica el lab".

**3. Estratègia triada (decisió del Josep): hardcode + registre NIF→lab defensiu.**
*Why:* el lab és constant avui, però volem robustesa si G3 canvia de lab sense
re-introduir risc de fabricació ni trencar l'ortografia exacta d'Eva.
- `LAB_REGISTRY = {'B64803075': 'TPS PROSPECCIÓ DEL SUBSÒL SL'}` a `internal_addresses.py`
  (mòdul canònic d'identitat de proveïdor; `B64803075` ja hi vivia a `NON_CLIENT_NIFS`).
- NIF conegut → ortografia canònica del registre (autoritativa). NIF desconegut → nom
  parsejat del footer + `logger.warning` (flag lleuger; Eva ho revisa al wizard). Sense
  footer → fallback al hardcode. **Cap fabricació en cap branca.**
- *Alternativa rebutjada (Opció C, parse-only):* produeix "TPS, PROSPECCIÓ DEL SUBSÒL, SL"
  amb comes ≠ ortografia d'Eva → pitjor match. El registre dona el millor de tot.
- Desambiguació clau: `_LAB_FOOTER_RE` s'ancora al marcador `Ins. Reg` (mercantil), que
  NOMÉS apareix a la banda del footer del lab → mai captura el bloc client (`B25364589`).

**4. `lab_location` NO és l'adreça del lab (correcció de §9).** És el punt de mostreig
("Punt: S-1"); la plantilla ja posa el prefix "Punt:". No hi ha camp d'adreça de lab.
L'extractor dona valors nus; cap canvi de format.

### Implementació
- `automation/internal_addresses.py` (+56): logger, `LAB_REGISTRY`, `_LAB_FOOTER_RE`
  (`^[ \t]*(?P<name>[^\n]+?)\s+(?P<nif>B\d{8})\s+Ins\.?\s*Reg`, IGNORECASE|MULTILINE),
  i `resolve_lab_company(text) -> (name, nif)` (pura, mirall de `is_non_client_nif`).
- `automation/lab_extractor.py` (+165/-75): split IO/lògica → `_read_pdf_text` +
  `_build_lab_results(lab_text, gtl_text, lab_path, gtl_path)` (pura). `extract_lab_results`
  descobreix lab PDF *i* GTL; retorna buit només si NO hi ha cap; sulfats = `lab_text or
  gtl_text` (primacia del lab PDF → projectes amb lab PDF byte-idèntics); metadades =
  `gtl_text or lab_text`; lab company via `resolve_lab_company` + fallback hardcode a
  `lab_field_company` i `lab_testing_company`; descripcions CA/ES inalterades.
- `tests/test_lab_extractor.py` (nou): 11 tests, fixtures de capçalera GTL reals com a
  constants inline (CI-safe, sense IO de PDF).

### Validació empírica
Smoke (abans → després):
| Projecte | lab_testing_company ABANS | DESPRÉS | sulfats |
|----------|---------------------------|---------|---------|
| Castellar (té LAB-SIG.pdf) | 'TPS...' | 'TPS...' (idèntic) | 0.0 (idèntic) |
| Vacarisses (GTL-only) | **''** | **'TPS PROSPECCIÓ DEL SUBSÒL SL'** | 204.7 |
`resolve_lab_company` sobre els 4 GTL reals → sempre `('TPS PROSPECCIÓ DEL SUBSÒL SL',
'B64803075')`, mai `B25364589`.

### Tests
+11 (`test_lab_extractor.py`) + endurits els de proveïdor. La regressió de l'early-return
està **bloquejada al límit de routing** (`extract_lab_results` amb monkeypatch dels seams
IO): re-review va injectar el bug → `test_extract_routes_to_gtl_when_no_lab_pdf` FALLA →
revertit → verd. Suite completa: **32 failed / 1023 passed** (baseline 32-failed inalterat;
+11 passats; 0 regressions). Re-review focalitzada: CLEAN.

### Latència / cost
Cap. Tot és text PyMuPDF + regex deterministes; cap crida LLM nova.

### Limitacions conegudes
- Lab desconegut amb etiqueta a la MATEIXA línia abans del nom (p.ex. "NIF: B... Ins.Reg")
  podria absorbir l'etiqueta. Cap GTL real ho exhibeix; el path TPS (NIF conegut) no
  s'hi veu afectat (resol pel registre).
- `sulfate_mg_kg = 0.0` a Castellar des de `LAB-SIG.pdf` és preexistent (no és regressió;
  el path del lab PDF queda intacte). Possible neteja futura separada.
- `lab_location`/`lab_sample_id`/`lab_tests_text` poden necessitar polit fi per casar
  amb l'estil exacte d'Eva (la plantilla ja afegeix prefixos); fora d'abast d'A3.

### GO/NO-GO
- ✅ Premissa §3 corregida amb evidència (5 GTL + 7 referències)
- ✅ Bug real (early-return) arreglat; GTL-only ara identifica el lab
- ✅ Registre defensiu NIF→lab; cap fabricació; ortografia d'Eva preservada
- ✅ Castellar byte-idèntic; 0 regressions; W1 lock provat per mutació
- ✅ GO

### Següents passos
1. **A1** — validació de rol amb `doc_type` (plano topogràfic → `architect_plan` →
   dimensions fabricades). Alt risc; arrossega Error 2.
2. **A4 / entity confusion** — `architect_company` etiqueta client/promotor; consultar Eva.
3. (Opcional) Pregunta a Eva: confirmar que TPS és l'únic lab; si n'apareixen d'altres,
   afegir-los a `LAB_REGISTRY`.

*Fi entrada 2026-06-25 (B). A3: el bug no era "falta extractor" sinó un early-return que saltava el GTL; lab sempre TPS (B64803075), hardcode correcte; GTL ara font de primer ordre + registre NIF→lab defensiu; premissa "múltiples labs" del handoff §3 desmentida.*

---

## 2026-06-25 (C) — A1: confusió de rol `architect_plan` → SUPERAT pel codi actual (verificat end-to-end, sense fix)

### Context
A1 (alt risc de fabricació): l'anàlisi (`ANALISI-PIPELINE-DEBUG-VACARISSES.md` §5.3, §9 A1,
Error 1/2) deia que `plano.pdf` (mapa topogràfic) s'assignava a `architect_plan` i el model
fabricava dimensions de parcel·la `425.4 × 426.0 m` llegint cotes topogràfiques (424/426
m.s.n.m.). Proposta original: validar el rol contra el `doc_type` del concept_map (prefix
`notes` "map:"/"plan:") i invalidar-lo en cas de contradicció.

### Decisions arquitectòniques clau

**1. La premissa d'A1 és STALE — verificat empíricament als 8 projectes (codi actual).**
Igual que A3 §3, els artefactes que motivaven A1 (`file_mapping.json` amb
`architect_plan=plano.pdf` i `sondeig_annex=plano.pdf`) són de **codi vell (2026-06-12)**.
Re-executant `FileScanner.scan()` amb el codi de `fix/pipeline-routing`:
- `plano.pdf` queda **unassigned** — els patrons d'`architect_plan` (`^A\.\d+\.pdf$`) no hi
  casen. **Cap projecte (0/8) assigna un mapa topogràfic a `architect_plan`.**
- El slot de visió `planol` l'omple ara el rol propi `situation_plan` (7/8 projectes);
  només Bell-lloc/Alcoletge tenen `A.01` real.
- **0 contradiccions rol-vs-doc_type** a tots els projectes. A més, el senyal que A1 faria
  servir (doc_type del concept_map) és **absent on caldria**: els plànols de situació
  (FreeHand) donen doc_type `∅`, i 5/8 projectes no tenen concept_map a temps d'scan.
  → un guard doc_type dispararia **0 cops** i es recolzaria en un senyal sovint inexistent.

**2. Verificació end-to-end (decisió del Josep): cap dimensió fabricada arriba a l'informe.**
Execució del pipeline de visió de PRODUCCIÓ real (`web/vision_fast.py` → `claude -p`, força
refresc, 418s) sobre Vacarisses. El run va fer servir el `file_mapping.json` STALE (perquè
`scanner.load()` retorna el cache si existeix), de manera que va alimentar el **pitjor cas**:
el topogràfic `plano.pdf` a l'extractor `planol`. Resultat de l'extracció (Claude actual):
- `dimensions: null` — **zero fabricació** (el bug vell donava 425×426).
- `extraction_notes`: *"This PDF is a topographic site survey... NOT an architectural plan...
  contour lines with elevation labels (423.00...427.00 m)"* — reconeix les cotes com a
  **elevacions, no dimensions**.
- Només `street_address: "Carrer la Barceloneta"` (real, legítim).
- `sondeig_annex_extracted.json` NO regenerat → `vision_fast` no té el fallback
  concept_map→plano. **Error 2 viu només al llegat `vision_groq`, no a producció.**

**3. Dues proteccions independents → no cal fix.**
(a) Nivell de rol: `scan()` actual deixa `plano.pdf` sense rol. (b) Nivell de visió: encara
que un rol stale l'alimenti, el prompt+model retorna `dimensions=null` i etiqueta el doc_type.
Construir el guard doc_type seria un **no-op** (0/8) sobre un senyal absent → no s'implementa
(mateix criteri que A2 descartat: no arreglar un no-bug; risc d'over-invalidation, p.ex.
Linyola on `situation_plan` té doc_type `architect_plan`, un match positiu que un guard
matusser podria descartar).

### Implementació
Cap canvi de codi. Només verificació + documentació.

### Validació empírica
- `FileScanner.scan()` sobre 8 projectes: `plano.pdf` unassigned; 0 contradiccions rol/doc_type.
- `vision_fast` real sobre Vacarisses (pitjor cas, plano.pdf→planol): `dimensions=null`,
  doc_type correctament identificat com a topogràfic.

### Tests
Cap test nou (no hi ha canvi de codi). Suite inalterada: 32 failed / 1023 passed.

### Limitacions conegudes / observacions
- **Cache de `file_mapping.json`**: `scanner.load()` reutilitza un `file_mapping.json` vell si
  existeix. Si a la màquina d'Eva un projecte té el mapping cachejat de codi vell (rol dolent),
  persisteix — però la protecció de visió (dimensions=null) es manté igualment. Tangencial a A1.
- La protecció de nivell de visió és conductual (no determinista). Les dues capes juntes fan
  improbable la fabricació; un guard determinista addicional té ROI baix avui.

### GO/NO-GO
- ✅ Premissa A1 desmentida amb evidència (8/8)
- ✅ Verificació end-to-end: cap dimensió fabricada a l'informe (pitjor cas inclòs)
- ✅ A1 SUPERAT pel codi actual — NO-FIX (com A2)
- ⏳ Error 2 (sondeig→plano) only-legacy `vision_groq`; no afecta producció `vision_fast`

### Següents passos
1. **A4 / entity confusion** — `architect_company` etiqueta client/promotor; consultar Eva.
2. **StreetView adjacents** (Eva ho ha demanat).
3. **A7 — Wizard UX**: entrada manual de nivells de sòl sense sondeig_annex.

*Fi entrada 2026-06-25 (C). A1 superat pel codi actual: plano.pdf ja no és architect_plan (8/8) i, fins i tot en el pitjor cas, el prompt+Claude actuals retornen dimensions=null sobre el topogràfic (verificat amb vision_fast real, 418s). NO-FIX.*

## 2026-08-22 — Fixes F1-F4e post-auditoria prod (branca `review/prod-audit-2026-08`)

### Context
`docs/audit/AUDIT-PROD-2026-08.md` (14 dies de logs reals de l'Eva): crash Unicode cp1252 (Can Mir Rubí 0/4),
visió DPSH trencada (Anthropic 92 % FAIL per parser, OpenAI 43 % per `max_tokens`), espera mediana 7,1 min tota
LLM. Pla d'execució: `docs/PLA-FIXES-PROD-2026-08.md`. Guardarails: prod intacte, in-place, sense refactors de fases,
un commit per fix amb test, baseline 32 failed / 1023 passed inalterable.

### Decisions arquitectòniques clau

**1. F1 — `encoding="utf-8"` explícit + helper `_read_file_mapping()` que mai llança.**
Why: `Path.read_text()` sense encoding = cp1252 a Windows; `file_scanner` escriu UTF-8. Alternativa rebutjada:
`errors="replace"` a tot arreu — amaga corrupció de dades; només s'aplica als dos lectors de `.env` (un `.env`
escrit amb Notepad pot ser cp1252 i no ha de petar l'arrencada). El helper canvia un detall de comportament: un
`file_mapping.json` corrupte ja no deixa el wizard buit (abans, excepció no capturada a la 2a lectura).
Guard estàtic: `test_no_bare_read_text_or_write_text_in_prod_code` (escaneja `automation/` + `web/`).

**2. F2 — JSON-only al system prompt + `_parse_json_response()` compartit; SENSE prefill d'assistant.**
Why: el pla proposava prefill `"{"`; la referència de l'API confirma que **retorna HTTP 400 a tota la família
claude-*-4-6** (i 5). Alternativa `output_config.format` (structured outputs): és el camí correcte a llarg termini
però exigeix un JSON Schema per tipus i canvia el contracte de les 3 crides — fora del "fix acotat". El parser
(strip → blocs ``` → text sencer → `{…}`) llança `JSONDecodeError` amb els 200 primers caràcters: **el log per fi
diu què ha respost el model** (3 mesos sense saber-ho).

**3. F3 — pressupost per tipus + detecció de truncament + la cadena S'ATURA en truncament.**
`MAX_TOKENS_BY_TYPE = {dpsh: 16384, projecte_arquitecte: 8192}`, clamp per proveïdor (`PROVIDER_MAX_OUTPUT_TOKENS`,
verificat: gpt-4.1-mini 32.768 docs OpenAI; qwen3.6-27b 16.384 `GET /models`; sonnet-4-6 128k). Evidència que
calia: Tulipa 6.651 i Rubí 4.159 tokens de sortida reals per al DPSH. Alternativa rebutjada: reintentar amb ×2 al
mateix proveïdor — Groq ja és al seu màxim (16k), un DPSH > 16k tokens és un document fora d'escala i el DPSH és
només validació (l'Excel ja té els N20); regla "mai 3 × 150 s pel mateix error" > rescatar un cas extrem.
`_call_backend_chain()` extret perquè el comportament sigui testejable amb backends falsos.

**4. F4 + F4b-e — Groq: el problema no era (només) el rate-limit, era el model.**
El pla preveia ≤5 imatges + backoff + pressupost de 429 (fet: `Retry-After`, 2-4-8 s + jitter, `GROQ_PROBE_429_BUDGET=10`,
fitxers marcats `unprobed`). V ha destapat que el canvi del 23 jul a `qwen/qwen3.6-27b` (no verificat) empitjorava
tot: és un model de raonament que gasta el `max_tokens` pensant → HTTP 400 `json_validate_failed`, reintentat 3 ×.
Decisions successives, cada una motivada per una mesura:
- **F4b** `reasoning_effort="none"` (documentat per Groq per a Qwen 3.6 27B; experiment: 1.600 → 250 tokens, JSON OK),
  `GROQ_MAX_IMAGES=3` (el model ho diu al 400), 4xx sense reintent. Desviació del pla: paràmetre nou a la crida; kill-switch
  `GROQ_REASONING_EFFORT=""`.
- **F4c** els camins `smartscan/tier3_vision` i `groq_miner` tenen la seva pròpia crida httpx; `TEXT_MODEL_GROQ`
  `qwen/qwen3-32b` **retirat** (404). Successor: `qwen/qwen3.6-27b` — únic Qwen3 viu; el codi ja té la branca "qwen3".
- **F4d** `RETIRED_GROQ_MODELS` → `live_groq_model()`. Why: el `.env` (gitignored, escrit 2026-05-04) fixa el model i té
  prioritat sobre `config`; canviar el default no arregla l'ordinador de l'Eva. Un `.env` antic ha de degradar a "funciona".
  Dos tests existents usaven ids retirats com a "models diferents" → actualitzats (un id retirat comparteix cache amb el
  successor, a propòsit).
- **F4e** inventari: **9 fitxers** amb la mateixa crida; helper únic `config.groq_payload_extras(model)` + test estàtic.
  Alternativa rebutjada: centralitzar la crida httpx en un client Groq únic — és el refactor correcte, però 7 fitxers i
  fora del guardarail 5; queda anotat.

**5. Verificació amb OpenRouter per a la via "anthropic".** La clau del `.env` de dev no té crèdit (HTTP 400). Per no
deixar F2 sense verificar amb Claude real: `G3DT_LLM_PROVIDER=openrouter` (mateix `claude-sonnet-4-6`, SDK Anthropic
amb `base_url`). Els `stop_reason`/`usage` arriben igual; el parser F2 s'ha exercit sobre respostes reals (3/3 OK).

### Implementació
F1: 7 fitxers, 15 línies + helper (21 LOC). F2: `prompts.py` (+3), `vision_groq.py` (+45/−25). F3: `vision_groq.py`
(+110/−45). F4-F4e: `vision_groq.py`, `concept_scout/vision_probe.py`, `config.py`, `groq_miner.py`, `tier3_vision.py`,
`ortho_vision.py`, `parcel_validator.py`, `mapillary_client.py`, `image_manager.py`, `geocode_coordinates.py`. Cap
dependència nova. 8 commits `89f34b5` … `6a6f780`.

### Validació empírica
Taula completa a `docs/audit/VERIFICACIO-FIXES-2026-08.md`. Tulipa: 708 → 504 → **273 s**; Rubí 266 s; Bell-lloc
322 → 282 s. DPSH via Anthropic **3/3 OK** (abans 8 %). 0 tracebacks, 0 truncaments, 0 rate-limits, 0 × 404, 0 × 400
Groq (run 1: 31). Informes generats 3/3. Criteri "< 3 min" **no assolit**: el que queda és latència seqüencial de
models (visió 145 s + probes 52 s), no errors.

### Tests
Nous: `test_utf8_read_text.py` (6), `test_vision_json_parse.py` (17), `test_vision_truncation.py` (13),
`test_groq_vision_limits.py` (20) = **56**. Suite: **32 failed / 1079 passed** (baseline 32 / 1023; conjunt de fallades
idèntic, verificat per diff). `pytest-timeout` no és instal·lat: el `--timeout` del pla és el de la crida, no de pytest.

### Latència / cost
Groq amb `reasoning_effort=none`: ~6 × menys tokens de sortida per probe (1.600 → 250) i 2 × més ràpid. Anthropic DPSH:
50-78 s per crida (4-7k tokens de sortida) — és el cost real de llegir 2-5 pàgines manuscrites; abans es pagava i es
llençava.

### Limitacions conegudes
- Prefills encara 4,5 min en projectes reals: estructural (fases en sèrie). Següent palanca: paral·lelitzar els 5 tipus de
  visió i les probes, i mostrar prefills bàsics abans de la visió (AUDIT §3.2). Decisió del Josep.
- Qualitat d'extracció no és objecte d'aquest pla; Rubí mostra `vision_probe` imposant adreça/municipi erronis d'una foto
  WhatsApp (narrativa en castellà). Preexistent.
- `web/api.py` (picker de models Groq) encara llista `qwen/qwen3-32b` i llama-3.x com a opcions (només UI).
- F5 (estat de l'ordinador de l'Eva) segueix sent del Josep; amb F4d, un `.env` antic ja no trenca res.

### GO/NO-GO
- ✅ F1-F4 del pla fets, amb test, un commit cada un, baseline intacte.
- ✅ V: DPSH Anthropic 3/3, 0 tracebacks, 3 informes generats.
- ❌ V: prefills < 3 min (4,5 min) — criteri no assolit, causa identificada i fora d'abast.
- ⏳ Fusió a `production/g3dt-eva-v1` + pull a l'ordinador de l'Eva: **decisió del Josep**.

### Següents passos
1. Josep: revisar els 8 commits; decidir fusió a prod i pull a `C:\g3dt-ia` (F5).
2. Decidir si s'ataca la latència estructural (paral·lelitzar visió/probes; prefills bàsics primer).
3. Avaluar substituir `gpt-4.1-mini` (OpenRouter: GPT-5.6 Luna és més barat — $0,20/$1,20 vs $0,40/$1,60 — amb 128k de
   sortida, però p50 4,1 s vs 0,67 s; és un model de raonament i caldria verificar `response_format` + latència al
   `deep_folder_classify`, que fa 5-14 crides en sèrie).

*Fi entrada 2026-08-22. Fixes F1-F4e post-auditoria: cp1252, parser JSON, max_tokens per tipus, Groq qwen3.6 (raonament, 3 imatges, models retirats, 9 camins).*

## 2026-08-23 — Fase 4a: lectors deterministes de les 5 plantilles G3 (`automation/g3_templates.py`)

### Context

Via A (branca `experiment/nivell-a-2026-08`): Claude Code serà el lector headless de documents, però les 5 plantilles
G3 (pressupost m4PRO, fitxa de camp, comanda de laboratori, PLAN_COST, Excel DPSH) tenen cel·les fixes conegudes —
gastar-hi LLM és lent, car i menys fiable. ANALISI §7.3 les defineix com a etapa "4a: 0 $, sempre". Les posicions
exactes venen de la lectura d'or dels 8 projectes (`docs/golden-read/*/g3_0*.json`) i són al Pas 2 del skill.

### Decisions arquitectòniques clau

1. **Mòdul nou i independent** (`automation/g3_templates.py`, sense tocar `auto_extractor.py` ni `ai_pipeline/` —
   prohibits en aquesta línia). **Why**: la via A necessita poder-se desplegar sense re-auditar el pipeline vell;
   un mòdul sense dependències internes es pot cridar des del wizard futur o des del skill indistintament.
   Alternativa rebutjada: estendre FileMiner (arrossega la seva arquitectura de Signal i el pipeline de fases).
2. **Detecció per CONTINGUT, mai per nom de fitxer**: pressupost = PDF amb `creator` G3 (m4PRO); fitxa = `fitxa!B2`;
   comanda = `Hoja1!C3`; PLAN_COST = `'Plan Cost'!B2`; DPSH = fulls `P-*`. **Why**: els noms varien
   (`25·0616.pdf`, `G3DT_Silvia_Jaume signat.pdf` són pressupostos) i SmartScan ja va demostrar el cost d'encertar-ho
   pel nom. Dedup per md5 (adjunts de .msg solts a la carpeta).
3. **Els `CLIENT:` de pressupost/fitxa s'emeten amb confiança 0,3 i nota "sol·licitant"**; el bloc G3 de la comanda
   s'emet com a `NOT_client_name`. **Why**: la cadena de l'error històric "client = G3" es talla a la font — el
   consumidor rep el senyal ja etiquetat amb el seu rol, no un valor nu.
4. **Agregació amb prioritat per concepte** (comanda N19 per expedient, fitxa F38 per data, Excel DPSH executats per
   sobre de previstos, modDate més nou entre pressupostos MODF). Ordenació multi-pas estable.
5. **3 formes reals del bloc OBRA del pressupost** (descobertes en validar): [encàrrec/adreça/municipi],
   [adreça+CP+municipi en 1 línia] (Linyola), [sense adreça] (Rubí) → classificador per línia amb guard
   "address-like"; CTE en castellà amb punt ("Tipo de Edificio. C0", Vilanova).

### Validació empírica

8/8 projectes (còpies Windows): 5-8 plantilles detectades per projecte, 0 errors de lector. Contrastat amb la lectura
d'or: expedient 8/8, field_date 8/8 (fitxa o comanda), municipality 8/8, num_dpsh executats 8/8, CTE correcte on el
pressupost porta la línia (Bell-lloc C1/T1, Rubí C0/T1, Alcoletge C0/T1, Vilanova C0/T1, Tulipa C1/T1) i
correctament absent on no hi és (Castellar, Linyola, Anciles → derivació, feina del skill), lab_sample/depth de la
comanda 8/8 (amb nota "el GTL mana si discrepa").

### Tests

`tests/test_g3_templates.py`: 9 tests (fixtures reference-material Bell-lloc) — detecció de les 5, cel·les exactes
per plantilla, prioritats d'agregació, rebuig de fitxers aliens, exclusió de validation/generats. Suite completa:
33→32 failed — el guard estàtic F1 (`test_no_bare_read_text`) va caçar un `write_text()` sense encoding al mòdul nou
(exactament el bug cp1252 de Can Mir Rubí): arreglat aquí i a `scripts/dwg_text_dump.py`. Final: 32 failed (línia
base coneguda, idèntiques) / 1088 passed / 3 skipped.

### Limitacions conegudes

- Camp `C7` de la fitxa porta adreça+municipi junts: s'emet cru amb nota (separar-ho és feina del skill).
- Multi-casa (Tulipa): s'emeten els 2 Excel DPSH i els 2 pressupostos; l'atribució per casa és del nivell de decisions.
- El PLAN_COST `E9` es parseja amb regex `EG {tipus} {municipi}` (confiança 0,6): pot fallar en títols no estàndard.
- No escriu mai a la carpeta del projecte; CLI amb `--out`.

### GO/NO-GO

✅ GO — llest per ser cridat pel wizard (SSE: camps segurs < 5 s abans de la visió) i pel skill com a substitut del
Pas 2 manual. Següent: disseny de la crida headless des del wizard + UI de candidats.

*Fi entrada 2026-08-23. Fase 4a: lectors deterministes G3 amb cel·la i cita, validats contra la lectura d'or.*

## 2026-08-24 — Taules de l'informe: regles d'or de lectura (skill v0.7→v0.9) + lectura d'or de TAULES 8/8

### Context
El Josep va reenquadrar la feina a mitja sessió del 23 nit: l'objectiu no és mesurar com el pipeline determinista vell
treia les taules, sinó que l'AGENT de la via A (skill `g3dt-llegir-projecte`) les llegeixi bé. Les taules-llista eren
l'espai no mesurat més gros de l'informe (DIAGNOSTIC §3.4). Sessions: 23 nit (v0.7/v0.8) + 24 (lectura d'or, v0.9).

### Decisions arquitectòniques clau
1. **Separació lectura/derivació per taula** (Pas 3b del skill): l'agent llegeix `dpsh_tests[]`, `sondeig_tests[]`,
   `spt_ma_tests[]`, `soil_levels[]`, `superficie_construida`; el Tier B (K, coef. C sísmic, γ/c/φ/E) queda EXPLÍCITAMENT
   fora — Python/criteri Eva amb override. **Why**: els 41 MISMATCH de càlcul del diagnòstic són judici d'Eva, no lectura;
   barrejar-ho faria segurs valors de criteri. Alternativa rebutjada: fer que l'agent derivi també — trenca la frontera
   lectura (skill) / derivació (Python) que sosté tota la via A.
2. **Comparador de taules com a arnès permanent** (`scripts/compare_tables_vs_eva.py` + `docs/golden-read-taules/_eva_truth/`):
   alineació de taules per empremta de capçalera (els índexs no coincideixen: l'informe d'Eva té 11-14 taules), files per
   clau (P-i, S-x, SPT-i, ordinals de nivell), criteris MATCH/CLOSE consistents amb el comparador escalar. **Why**: la
   mateixa eina serveix per minerar la veritat d'Eva (regles d'or) i per validar la sortida futura del wizard.
3. **Lectura d'or de taules amb agents cecs** (patró del hold-out): 1 agent/projecte, skill com a únic playbook,
   prohibicions explícites (informes, generated, validation/, golden-read, memòria); comparació DESPRÉS per la sessió
   principal. **Why**: manté la lectura cega; la comparació centralitzada aplica criteris uniformes.
4. **El document font principal de nivells/litologies és l'ANNEX DE SONDEIG** (matriu G3 "Sondeig a rotació amb batería
   contínua", assenyalat pel Josep): columna «Unitat litològica» (nivells), «Descripció dels materials» (la redacció que
   l'Eva condensa a l'informe), Registre SPT (cops/15 cm), NF, z. FreeHand → text brossa → SEMPRE visual. Present 4/8.

### Validació empírica (lectura d'or de taules, 2026-08-24)
8 agents (~150-190k tokens cadascun, subscripció, 0 $ API), 6 projectes comparables amb informe signat:
**113 OK (75 %) / 35 CAND amb el bo entre candidats / 1 ERR (0,7 %) sobre 150 cel·les; OK+CAND-encertat 98,7 %.**
23/23 profunditats DPSH exactes (regla del peu "Rebuig a"); cotes per punt/relatives exactes (Anciles 6 cotes diferents).
Vilanova n/a (el seu PDF d'informe no té cos de taules) i Tulipa n/a (sense informe d'Eva) — consistència 100 %.
Detall: `docs/golden-read-taules/_RESULTATS.md` + `_comparison.json` per projecte.

### L'ERR i regles noves (v0.9)
- **ERR únic (Castellar)**: cota del sondeig marcada segura amb l'absoluta (570,90, z de l'annex) quan l'Eva escriu la
  relativa (-4,20) coherent amb el sistema dels DPSH → regla: la cota de la taula segueix el SISTEMA de cotes del projecte;
  sistema mixt → candidats. Re-execució esperada: ERR = 0.
- Peu "Rebuig a -X,XX m": zona B79-B82, no cel·la fixa (B81 a Alcoletge i Tulipa).
- N.F./Nivells de l'Excel poden ser COLORS de cel·la (llegenda files 79-80; `xlrd formatting_info=True`); una llegenda
  idèntica a tots els fulls és plantilla, no transició (Tulipa).
- **n30 MAI segur**: registre (segur) + candidats de la suma. Criteri d'Eva INESTABLE: Rubí/Alcoletge/Anciles = trams
  centrals; Bell-lloc informe 54 ≠ tall 58 ≠ centrals 62 → pregunta oberta a l'Eva.
- Micro-regles de format: emetre comptes SPT/TP/MA (format "1/--"/"1/0"/"1/0/0" inestable), components+total de
  superficie_construida ("72+20"→"92"), capçaleres adaptatives ("Humitat (m)", "(m*)" vs "(msnm*)", etiqueta de parcel·la
  segons font — 3a variant: "segons informació aportada").

### Limitacions conegudes
- Leakage: com als escalars, valida executabilitat i re-execució, NO generalització (el skill anomena projectes del corpus).
- Veritat d'Anciles = V0 esborrany (placeholder "xxxxxxx", sulfats il·legibles); Vilanova sense veritat de cos.
- Taules NO cobertes pel skill (per disseny): permeabilitat/sísmica/geotècnica/sulfats-qualificació = Tier B pendent.
- No mesurat: fidelitat de la taula DPSH detallada per intervals (l'annex la porta; l'informe només resum).

### GO/NO-GO
GO per als dos següents trams: (1) Tier B per nivell amb `_eva_truth/` com a dataset de validació; (2) disseny crida
headless + UI de candidats (ara amb el bloc `tables` inclòs). ✅ mètrica ERR complerta amb 1 excepció convertida en regla.

### Següents passos
Vegeu `docs/_FOR-NEW-YOU-20260824-1500.md`.

*Fi entrada 2026-08-24. Lectura d'or de taules: 113/35/1, skill v0.9, arnès de validació permanent.*

## 2026-08-24 (tarda) — Wizard headless + UI de candidats (Pendent B via A): disseny, Fases 0-8

### Context
Últim tram tècnic de la via A (handoff 24/15:00 §2B). Josep confirma D1-D3/D5 del disseny i demana construir-ho amb Sonnet 5.
Disseny: `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md`.

### Decisions arquitectòniques clau
- **Crida per document + consolidació separada** (D1) en lloc de la crida única validada per la lectura d'or. Why: SSE
  incremental, timeout per document, fallada aïllada, cache per md5. Trade-off: el Pas 5b (`--consolida`) no estava
  validat → acceptació Fase 0 amb 2 agents cecs (escalars 19/22, taules 20/21, 0 ERR) i E2E real (2 projectes, 0 ERR).
  Mode `projecte` de reserva implementat.
- **Contracte v1 amb validador Python** que codifica el criteri d'or (n30/litologia mai segurs, claus canòniques de fila).
  Why: el productor cec desvia en FORMA, no en fons (5 desviacions a la Fase 0, 3 a l'E2E) → normalització suau
  determinista (a) value:=candidates[0], (b) font/quote solts → candidates, (c) àlies de claus → canòniques; després, degradat.
- **Claude només llegeix el que Python no llegeix** (inventari amb routes). Trade-off descobert a l'E2E: les fonts Python
  fora de g3_templates (COORDENADES.txt, Cadastre) són invisibles al consolidador → forat 1 (pendent).
- **Autenticació aïllada del fill** (`G3DT_LECTURA_AUTH=login`): el `.env` de la via B porta una clau sense crèdit que el
  CLI prefereix a la sessió. Descobert en viu; hauria passat igual a casa l'Eva.
- **Via B intacta**: 3 edicions quirúrgiques (flag, guard 404 + endpoint, `skip_vision` keyword); suite 32 failed idèntics.
- **Sonnet 5 per a les fases de codi** (D4): 7 agents, 1 encallat (llegir 9.000 línies) → mètode grep+rangs. Judici (skill,
  acceptacions, E2E) a la sessió principal.

### Implementació
`automation/lectura/{contract,inventory,runner,normalize}.py`, `web/lectura_service.py`, `GET /api/lectura-stream`,
`review.html` (+999), skill v1.0→v1.3. Commits `a31c3d4` … `b8c6986`.

### Validació empírica
Fase 0 cega: 0 ERR. E2E real: Bell-lloc 17 docs 0 err (18/18 escalars i taules OK vs or), Castellar 13 docs 0 err (15/17 OK,
resta format/prudència); wizard sencer amb badges i 0 errors de consola. Temps: mediana 264-279 s/doc, consolidació 562-585 s,
paret 37-58 min (2 projectes solapats). Detall: `docs/wizard-headless/fase8-e2e/_RESULTATS.md`.

### Tests
+70 (contracte 20, inventari 20, runner 14, servei 13 + normalize dins runner). Suite: 32 failed (línia base) / 1152 passed.

### Limitacions conegudes
Latència del primer open (35-60 min) lluny de l'estimació (5-12); Windows no provat; forat 1 (fonts Python fora de
g3_templates); seleccions de taula de la UI sense backend (8b); leakage (corpus conegut pel skill).

### GO/NO-GO
✅ GO tècnic (funciona de cap a cua, 0 erroni-amb-confiança) · ⏳ NO-GO de latència fins a aplicar palanques (concurrència,
prompt prim, menys documents, consolidació Python-first) i remesurar.

### Següents passos
Palanques de temps → remesura amb 1 projecte sol; forat 1; Fase 8b (seleccions → user_data/generador); prova Windows;
projecte NOU de l'Eva (generalització).

*Fi entrada 2026-08-24 tarda. Wizard headless construït i validat E2E; latència com a bloquejant.*

## 2026-08-24 (nit) — Fase 9: latència mesurada de veritat, tres botons dissenyats, llibre de mesures

### Context
L'E2E de la tarda (entrada anterior) deixava el wizard headless en "GO tècnic, NO-GO de latència" (37-58 min, dos projectes solapats) amb
quatre palanques sense mesurar. Aquesta nit: diagnòstic de la latència amb dades, disseny del que fa la latència irrellevant per a l'Eva,
instrumentació del runner i remesura amb un projecte sol. Conversa amb el Josep: qualitat primer; només subscripció; ≤ 1 projecte/dia.

### Decisions arquitectòniques clau
1. **No escurçar la lectura; treure-la del camí crític.** Micro-benchmark (`claude -p "ok" --output-format json`, 5 variants): arrencada del CLI +
   1 volta = 4-14 s. Els ~110 s "fixos" per document són el protocol del skill amb Sonnet 5 (≈ 21 turns/doc, estable entre runs: 269 i 268).
   Alternativa rebutjada: "prompt prim" (sense CLAUDE.md/MCPs) — val 5-10 s i higiene de cost, no latència. Alternativa rebutjada: retallar Pas 0/3
   del skill — és d'on surt el 0 erroni-amb-confiança.
2. **Tres botons + registre de jobs a disc + taula d'estat + notificacions** (`docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md`,
   Fases 9-17). "Preparar per demà" desatès; "Enllestir" ≈ 30 s si res ha canviat (3a) o 6-9 min amb K documents canviats (3b, amb consolidació
   Python-first). Per què: amb carpetes de xarxa que toca gent cada dia, el cas 3b és el normal; la consolidació (474-677 s) és l'impost de cada canvi.
3. **Correu via SMTP d'Eficients (Brevo, remitent dedicat) com a canal provisional**, telemetria a Eficients **explícita (no BCC), mínima i escrita
   al document de servei**; toast Windows + taula com a canals primaris; encàrrec de tractament art. 28 a revisar amb G3.
4. **Runner: `--model` fixat (`G3DT_LECTURA_MODEL`, defecte `sonnet`) i `--output-format json`** → telemetria amb turns/api_ms/cost/tokens/models.
   Per què: a l'ordinador de l'Eva el defecte del CLI pot ser un altre; i sense turns "on va el temps" era deducció. Sidecar de stdout (no PIPE)
   per no tocar el bucle de cancel·lació.
5. **Llibre de mesures** (`docs/wizard-headless/mesures/`, `ledger.py` → `LEDGER.md`, `runs/<etiqueta>/` amb artefactes crus i `meta.json` amb el
   judici ERR per ERR). Per què: el Josep vol la taula abans/després per a l'Eva; cada palanca és una fila comparable.
6. **Fable com a defecte només si la qualitat ho demana** — no ho demana (0 erroni-amb-confiança de fons a 3 runs amb Sonnet 5); queda com a fila
   mesurable (`G3DT_LECTURA_MODEL=fable`).

### Implementació
`automation/lectura/runner.py` (+85 LOC: `_parse_cli_output`, sidecar, model a cfg), `tests/test_lectura_runner.py` (+93 LOC, 3 tests; mock amb
`MOCK_CLAUDE_JSON`/`MOCK_CLAUDE_ARGVLOG`), `docs/wizard-headless/mesures/` (ledger + 3 runs + sonda), addendum a `fase8-e2e/_RESULTATS.md`,
annex de disseny. Via B intacta. Nit menor: si `claude` no existeix, el sidecar `.out` buit queda a `/tmp` (handles tancats).

### Validació empírica (Castellar sol, Sonnet 5, login)
- Run 1 (conc. 2): 13/13 OK, suma 70 min, mediana 290 s, 269 turns, 342k tokens de sortida, consolidació 474 s; paret invàlida (tall de connexió).
- Run 2 (conc. 3, net): **paret real 33 min** (reconstrucció per planificació de llista: 32 → el model prediu), suma 61 min, 268 turns, 306k tokens,
  consolidació 677 s / 72k tokens.
- Qualitat: **0 erroni-amb-confiança de fons als 3 runs**. Reproduïble (2/2): `cota_referencia` puja a `segur` amb 1 font (valor = preferit de l'or)
  → guard determinista a la Fase 12. Conflicte skill vs or a `sondeig_tests[0].cota` (cel·la relativa vs absoluta) → decisió Josep/Eva.
- Sonda `stream-json` (`tall.pdf`): 20 turns, 25,8k tokens de sortida, ~75 % raonament; 5/15 usos d'eina són construir-se l'eina (`fitz`), 2
  redundants, 2 cerimònia d'escriptura → palanca de pre-extracció determinista (−35-45 % estimat, sense tocar què mira el model).

### Tests
+3 (runner: argv, telemetria amb JSON, sense JSON). Suite de lectura 73 passed. Suite completa no re-executada aquesta nit (canvis limitats a runner + tests).

### Latència / cost
Cost equivalent per projecte $15-18 (subscripció: no facturat; és el pes). 2 projectes + sonda en una nit sense cap error de límit de la subscripció.

### Limitacions conegudes
Tot és re-execució de Castellar (leakage). Windows no provat. Conc. 4 no mesurada (reconstruïda ≈ 26 min). `fotografies.pdf` i GTL del run 1
contaminats pel tall. El conflicte skill/or de la cel·la `cota` del sondeig pot amagar un criteri de l'Eva que no coneixem.

### GO/NO-GO
✅ Instrumentació verificada amb el CLI real. ✅ Paret a conc. 3 = 33 min, predictible. ✅ Qualitat estable (0 fons). ⏳ Latència segueix sent
NO-GO per a "esperar a la pantalla" → els tres botons. ⏳ Guard de confiança (Fase 12). ⏳ Pre-extracció: a mesurar.

### Següents passos
Fase 10 (registre de jobs + lock + `GET /api/jobs`), Fase 11 (delta-sync). Experiment barat abans de la 12: pre-extracció determinista +
`write_doc_json.py` en una còpia del skill, fila nova al llibre (`preext-c3`) i comparador d'or.

*Fi entrada 2026-08-24 nit. Fase 9: la latència és generació (≈ 21 turns/doc), 33 min reals a conc. 3, 0 erroni-amb-confiança; tres botons dissenyats.*

## 2026-08-25 — Experiment de pre-extracció (v1: −24 %/doc, no adoptat) + Fase 10 (registre de jobs) en paral·lel

### Context
Handoff `docs/_FOR-NEW-YOU-20260825.md` §6.3: la sonda de turns mostrava 9/15 usos d'eina que no són llegir ni escriure (fabricar-se
`fitz`, `ls`/`md5sum`, cerimònia d'escriptura). Palanca admissible (no toca *què mira* el model). El Josep decideix: pre-extracció
primer, Fase 10 després; i, com que l'experiment és llarg, la Fase 10 es construeix en paral·lel amb frontera de fitxers explícita.
També fixa l'**objectiu real**: l'informe complet (341 variables), no només el nivell A (STATUS «🎯 Objectiu real»).

### Decisions arquitectòniques clau
- **Pre-extracció darrere d'un flag, com a skill-còpia, no com a canvi del skill de producció.** `G3DT_LECTURA_PREEXT` (defecte off →
  prompt byte-idèntic) + `G3DT_LECTURA_SKILL`. Alternativa rebutjada: editar `g3dt-llegir-projecte.md` directament — hauria barrejat
  la mesura amb el protocol validat (0 erroni-amb-confiança en 3 runs). La còpia difereix en 4 blocs (diff de 23 línies).
- **Zoom sota demanda en lloc de pre-renderitzar-ho tot a alta resolució**: `render_clip.py` (clip fraccional, dpi, graella). Pre-renderitzar
  a 400-600 dpi totes les zones és impossible; el model ha de poder triar on mirar, però sense escriure codi.
- **Escriptura en una ordre** (`write_doc_json.py`: validació + nom canònic + atòmic): elimina 2 turns de cerimònia i centralitza el contracte.
- **Fase 10: job en fil propi + subscriptor amb replay**, no "SSE que executa". `_job.json` s'escriu a disc ABANS de notificar els
  subscriptors (decisió de l'implementador, trobada per un test que fallava). **`interrupted` = `pid ≠ os.getpid()`**, mai `os.kill(pid, 0)`
  — a Windows `os.kill` amb un senyal arbitrari **mata** el procés; el wizard és un sol procés, qualsevol pid anterior és mort per definició.
- **`list_jobs` escaneja només el primer nivell** de `_REF_DIR`: verificat que en mode xarxa el workspace aplana cada projecte al nom fulla
  (`sync_workspace.workspace_project_path`) i `_REF_DIR = G3DT_LOCAL_WORKSPACE`.

### Implementació
Commit `0dfff32` (experiment): `automation/lectura/preext.py` (529 LOC), `scripts/write_doc_json.py` (169), `scripts/render_clip.py` (151),
skill-còpia, `runner.py` +26/−7, `tests/test_lectura_preext.py` (19+1 skip) + 3 tests al runner. Commit `8d3b0ce` (Fase 10):
`automation/lectura/jobs.py` (528), `web/lectura_service.py` +161/−38, `web/api.py` +73, `tests/test_lectura_jobs.py` (23) + 9 al servei.
Tots dos amb Sonnet 5 (code-implementer), judici a la sessió. **Incident**: tots dos agents han usat `git stash` per comparar la línia base
malgrat la prohibició; sense dany (untracked no afectats, `runner.py` ja importat pel run viu) — al proper brief, prohibició explícita amb el motiu.

### Validació empírica
Fila `2026-08-25-preext-c3` del llibre: mediana/doc 292 → 221 s (−24 %), turns 20,6 → 17,3, tokens sortida −22 %, paret 33 → **28 min**;
0 erroni-amb-confiança de fons; **5 cel·les `nivell_freatic` baixen de `segur` a `no_trobat`** (color de cel·la d'Excel no exportat) →
criteri d'adopció no complert. Detall: `fase8-e2e/_RESULTATS.md` addendum 2026-08-25.

### Tests
Suite de lectura **123 passed / 1 skipped** (73 → 123). Suite completa: **32 failed** (línia base per recompte; cap a `lectura`/`preext`/`jobs`).

### Latència / cost
Run: 55,7 min de suma `claude` + 539 s de consolidació = 28 min de paret a conc. 3; cost equiv. 13,6 $ (subscripció). Pre-extracció: 13 s, 72 MB/projecte.

### Limitacions conegudes
- v1 no exporta colors d'Excel (nivell freàtic/nivells per color) ni distingeix text brossa Distiller (`text_ok` per recompte alfanumèric).
- Multipàgina: el model mira sencer + meitats de totes les pàgines (més turns que abans en 7 p).
- Fase 10: `estimate_s` només es recalcula a `lectura_doc`; `claude_version`/`network_delta` null; detecció d'interromputs lazy (a `list_jobs`), no a l'arrencada.
- 72 MB per projecte a `validation/lectura/_preext/`: cal política de neteja abans d'anar a l'ordinador de l'Eva.

### GO/NO-GO
- ✅ Fase 10 (jobs): codi, tests, API.
- ⏳ Pre-extracció: NO adoptada; v2 (colors + meitats selectives + `text_ok` per producer) i remesura `preext-v2-c3`.
- ✅ Objectiu 341 variables apuntat a STATUS i memòria.

### Següents passos
v2 de la pre-extracció → si adoptada, `G3DT_LECTURA_PREEXT` per defecte + skill de producció; Fase 11 (delta-sync); Fase 12 (guards + Python-first).

*Fi entrada 2026-08-25. Pre-extracció v1 −24 %/doc i 28 min de paret però 5 cel·les perdudes pel color d'Excel → v2; Fase 10 feta.*

## 2026-08-25 (vespre) — Pre-extracció v2 adoptable, effort heretat descobert i fixat, tres models mesurats (Fable / Opus 4.8 / Sonnet)

### Context
Continuació de l'entrada del matí. El Josep demana la v2 de la pre-extracció, pregunta per Fable i per l'effort, i vol Opus 4.8 @high perquè
és el que donen les subscripcions Anthropic econòmiques (decideix el pla de l'Eva). Set runs al llibre en 2 dies.

### Decisions arquitectòniques clau
- **El runner fixa `--effort`** (`G3DT_LECTURA_EFFORT`, defecte `xhigh`) i treu `CLAUDE_EFFORT` de l'entorn del fill. **Why:** els 5 runs previs
  corrien a xhigh heretat de `CLAUDE_EFFORT`/`effortLevel` del Josep; a l'Eva correria al defecte del CLI (desconegut). Sense fixar-lo, cap mesura
  és reproduïble ni transferible. Defecte xhigh perquè el llibre segueixi comparable; nivells inferiors = files noves amb comparador d'or.
- **Pre-extracció v2** (colors d'Excel, meitats només per `text_ok=false`, `text_ok` per ràtio ≥ 0,75; producer Distiller només informatiu perquè
  el mateix producer dona text net i brossa). **Why:** la v1 perdia 5 cel·les de nivell freàtic (Pas 3b exigeix el color) i feia llegir totes les
  meitats. Resultat: regressió resolta, −37 %/doc, 26,2 min. Proposada com a adoptable; flipar el defecte és decisió del Josep.
- **Comparar models a effort igual i sobre el mateix pipeline** (v2, conc. 3). Fable i Sonnet a xhigh; Opus 4.8 a high perquè és la condició real
  de la subscripció econòmica (dos canvis alhora, volgut i documentat al `meta.json`).
- **La consolidació LLM és el punt feble comú** (8 consolidacions: 1 dialecte pla, 2 amb senyals emesos perduts, 1 candidat derivat sense font).
  Reafirma la Fase 12 Python-first: cap `tier_a` emès es pot perdre; embolcall determinista de cel·les planes; guard 1 font → candidats;
  candidats derivats només amb font documental.

### Validació empírica (Castellar sol, 13 docs, conc. 3)
| model | paret | mediana/doc | turns | erroni fons | taules OK/ERR | pèrdues consolidador |
|---|--:|--:|--:|--:|--:|--:|
| Sonnet 5 @xhigh (v2) | 26,2 min | 184 s | 14,8 | 0 | 15/5 format | 1 (1a consolidació) |
| Fable 5 @xhigh (v2) | **20,5 min** | 152 s | 10,1 | 0 | **23/0** | 0 |
| Opus 4.8 @high (v2) | 23,6 min | 171 s | 10,7 | 0 | 22/1 format | 2 + 1 candidat derivat |
Detall i lectura per tipus de document: `fase8-e2e/_RESULTATS.md` addendum nit; `mesures/LEDGER.md` (7 runs).

### Tests
Suite de lectura **131 passed / 2 skipped** (+4 effort, +4 v2). Completa: 32 failed (línia base, cap a les àrees tocades).

### Limitacions conegudes
n=1 per model; la variància del consolidador entre runs és de la mida de les diferències entre models als escalars. Sostre de la subscripció
desconegut (Fable ×3,7 de pes). 72 MB de `_preext/` per projecte sense política de neteja. `text_ok` heurístic.

### GO/NO-GO
- ✅ Pre-extracció v2: adoptable (0 erroni de fons, regressió v1 resolta, −21 % paret). ⏳ Flip del defecte: Josep.
- ✅ Effort fixat al runner. ✅ 3 files de models al llibre.
- ⏳ Elecció de model/pla: Josep (criteri: comparable → Sonnet; més eficaç/fiable/ràpid → Fable; Opus 4.8 viable amb Fase 12).

### Següents passos
Fase 12 (Python-first + guards) abans que Fase 11: és el que tanca les pèrdues del consolidador a qualsevol model. Després: flip v2, Fase 11, 13-15.

*Fi entrada 2026-08-25 vespre. v2 adoptable (26 min), effort fixat, Fable 20,5 min / Opus 4.8 23,6 / Sonnet 26,2 amb 0 erroni de fons als tres; consolidador = punt feble comú.*

## 2026-08-25 (nit) — Fase 12: consolidació Python-first amb guards; el LLM només per als conflictes reals (`--only-fields`)

### Context
Handoff `_FOR-NEW-YOU-20260825-2025.md` §3: el consolidador LLM (`--consolida`) era el punt feble comú als tres models (8 consolidacions
en 2 dies: 1 dialecte pla → 23 ABSENT, 2 amb senyals emesos perduts — `num_floors`, `cte_edificacio` —, 1 candidat inventat `-4,20 m`
sense font). Annex §7.2 / §10 fila 12: "Python consolida sempre; només els conflictes reals van a `--consolida --only-fields`". El Josep
demana arrencar la Fase 12 abans que la 11. Decisió d'execució: el consolidador l'escriu la sessió principal (Fable), no un implementer
Sonnet — la peça és semàntica (Pas 3/3b codificats) i s'itera contra l'or en segons; els implementers queden per a peces mecàniques.

### Decisions arquitectòniques clau
- **Consolidació determinista com a via principal** (`automation/lectura/consolidate.py`, ~1.000 LOC, sense LLM). **Why:** les tres
  pèrdues observades són *estructurals* d'un productor cec (dialecte, oblit, invenció); un consolidador que enumera tots els senyals no pot
  perdre'n cap ni inventar-ne. Alternativa rebutjada: "prompt més estricte" al skill — no elimina la classe d'error, només en baixa la
  freqüència, i costa 8-10 min per run. Trade-off acceptat: les regles semàntiques no codificades (instrucció del client posterior,
  redacció de l'informe) queden com a `candidats` amb totes les formes en lloc de `segur`.
- **`segur` = 1 font d'autoritat A sense contradicció** (Pas 5 literal) **o convergència de ≥ 3 documents independents** (conf ≥ 0,6).
  A = confiança ≥ 0,8 (claude) / ≥ 0,9 (`_g3_templates`) / font Python. **Why:** la confiança que el skill assigna ja codifica la
  posició al document (sol·licitant 0,3, bloc OBRA 0,85…); una taula d'autoritat per tipus de document duplicaria el Pas 3 i
  divergiria. La convergència cobreix `lab_location` (GTL + comanda + annex a 0,6-0,75) sense abaixar el llindar A.
- **Contradicció asimètrica camps/taules:** als camps, qualsevol senyal ≥ 0,4 bloqueja (`client_name` 0,6: el formulari p.5 mana);
  a les cel·les de taula només els documents d'autoritat A de la cel·la (Pas 3b) — el tall gràfic i el manuscrit són corroboració.
  **Why:** amb 0,6 per defecte a les files no-A, Fable i Opus quedaven 13-16 cel·les per sota de la seva pròpia consolidació LLM.
- **Compatibilitat de valors abans de comparar:** dates parcials, numèrics (fondàries amb `abs`), text amb prefix/sufix (lectura
  parcial) però **mai contenció interior** ("entre el carrer X i el carrer Y" no fusiona X amb Y: cantonada de Bell-lloc → `candidats`,
  com l'or). Formes A diferents dins un cluster → `candidats` amb totes les formes (l'adreça de Castellar: 3 formes, cap ERR).
- **Guards codificats del Pas 3/3b** (n30/litologia/spt_ma/cte mai segur; arquitecte persona+despatx o = client; G3/ARQUITECT mai
  client; RC sense Cadastre; nivells sense annex; parcel·la amb 2 RC; "1 de N unitats"; `a` de l'últim nivell; sistema de cotes
  relatiu al sondeig — relativa primer, absoluta segona, mai segur). **Why:** són exactament els llocs on l'or diu `candidats`.
- **Derivats només els que el skill sanciona, etiquetats i mai segur:** `(practica Eva: client al camp arquitecte)`, `(derivat: regla
  Eva C0/C1)`, `(coneixement previ: T-1 / TPS)`. **Why:** el `-4,20 m` d'Opus era un derivat *sense etiqueta ni font*; el problema no
  és derivar, és presentar-ho com a lectura. `cte_sol` T-1 i TPS sense GTL es mantenen perquè el Pas 3 els prescriu i l'Eva els escriu.
- **Fonts Python al consolidador (forat 1, parcial):** nom de la carpeta → `expedient` (A); `COORDENADES.txt` → `utm_x/y` (A, P-1
  segons regla; tots els punts a `extra`) i z → `cota_referencia` (0,5, "l'Eva no l'usa"). Cadastre/ICGC queden fora (Fase 13).
- **Conflicte real = A-vs-A de documents diferents** → `conflicts[]` amb paths → crida `--consolida --only-fields a,b` (skill v1.5)
  que escriu `_consolida_only.json`; `merge_only_fields` aplica només les cel·les demanades que passen el contracte i manté les guards.
  Dues alternatives del mateix document (annex: 1,80 / 8,0) NO són conflicte. **Why:** el LLM ha de jutjar només on hi ha judici a fer;
  Castellar amb els tres models: 0 conflictes → 0 crides.
- **Runner:** `G3DT_LECTURA_CONSOLIDA=auto` (defecte) | `python` (mai LLM) | `llm` (via de les Fases 3-11, per mesurar/pla B). El runner
  escriu `_decisions.json` (atòmic) en tots els casos, també en degradat (abans no s'escrivia). `merge_degradat` → `consolidate_python`,
  amb `_merge_minimal` (Fase 4) d'últim recurs.
- **Reparació (d) del contracte:** `normalize.wrap_flat_cells` embolcalla cel·les planes `{estat: estat_bloc, value, candidates:
  [{value, font: "(adaptat)"}]}` — el forat que va deixar passar el dialecte pla (23 ABSENT) — només a la via LLM.
- **`nivell_freatic` absent → `No detectat`** al consolidador (canonicalització) i al skill v1.5 (vocabulari).

### Implementació
`automation/lectura/consolidate.py` (nou), `runner.py` (+`_consolidate_python_first`, config), `normalize.py` (+`wrap_flat_cells`),
skill v1.5 (Pas 5b mode `--only-fields`, Pas 3b vocabulari), `tests/test_lectura_consolidate.py` (nou, 55), `tests/test_lectura_runner.py`
(+8, mock amb `--only-fields` i valors per document), `docs/wizard-headless/fase12-consolida/{harness.py,_RESULTATS.md,out/}`,
`mesures/ledger.py` (modes `consolida_python`/`consolida_only`). Commit `879bf7b`.

### Validació empírica (`fase12-consolida/_RESULTATS.md`)
Harness sobre 5 jocs de perdoc ja llegits (cap crida LLM), cel·la a cel·la contra la consolidació LLM del mateix joc:
| joc | escalars OK/CAUT/ALERTA/ERR | taules OK/CAUT/ALERTA/ERR/ABSENT | per sota de la ref. | conflictes |
|---|---|---|--:|--:|
| Sonnet v2 (ref `consolida2`) | 14/5/2/0 | 20/1/1/3/2 | **0** (5 per sobre) | 0 |
| Fable v2 | 15/5/1/0 | 23/2/0/0/2 | **0** (1 per sobre) | 0 |
| Opus 4.8 v2 | 14/5/2/0 | 22/1/1/1/2 | **0** (2 per sobre) | 0 |
| Sonnet v1.3 (24-08) | 14/5/2/0 | 20/2/0/3/2 | 4 (CAUTELA amb el bo dins) | 2 (utm) |
| Bell-lloc v1.2 | 12/9/0/0 | 16/3/0/0/2 | — | 1 (`street_address`) |
**0 erroni-amb-confiança de fons als 5**; els ERR que queden són de format (`-4 m`/`-4,0 m`, `1,0 - 1,2 m`/`-1,00 a -1,20 m`).
Runner in situ (Castellar, docs en cache): 5,4 s de paret, consolidació **0,04 s** (Opus LLM: 480 s), fila del llibre
`2026-08-25-opus48-docs-python-consolida`. Crida real `--only-fields` a Bell-lloc (1 conflicte, `street_address` cantonada): 228 s / 18 turns / 20k tokens (Sonnet @xhigh); el skill
v1.5 ha escrit la cel·la en dialecte v1 amb 3 candidats tots documentats (cap invenció), Python l'ha fusionada, comparador idèntic (or
`candidats`; el LLM confirma l'ordre de Python). Funciona i és segura; n=1, no aporta qualitat en aquest cas (3,8 min).

### Tests
+63 (55 consolidate + 8 runner). Suite de lectura **193 passed / 2 skipped**; completa 32 failed (línia base `test_smartscan`, cap a
lectura) / 1275 passed.

### Latència / cost
Consolidació: 8-10 min i 20-37 turns → 0,04 s i 0 turns quan no hi ha conflictes (Castellar, 3 models). Botó 3b (re-consolidació amb
documents en cache): < 6 s. Un run complet de Castellar passaria de 20,5-26 min a ~12-18 min segons model (documents intactes).

### Limitacions conegudes
Regles = Pas 3/3b d'avui (una regla nova demana codi). Comparador d'or per cadenes: ERR/ALERTA de format pendents dels normalitzadors
(tasca següent) i 2 fixtures a revisar (`sondeig cota` Castellar anterior a la regla del sistema de cotes; `de_a_estat`). Cadastre/ICGC
no són fonts del consolidador. Jocs antics (v1.2/v1.3) donen més `candidats`. n=1 per a la crida `--only-fields` real: si a 2-3 projectes
més el LLM només confirma Python, el defecte candidat és `python` (0 crides) i la crida es reserva per a conflictes d'identitat.

### GO/NO-GO
- ✅ 0 erroni-amb-confiança de fons a Castellar (3 models) i Bell-lloc. ✅ Cap cel·la per sota de `consolida2`/Fable. ✅ < 60 s (0,04 s).
- ✅ Contracte net a tots els jocs; cap senyal perdut (test automàtic sobre 7 jocs). ✅ Defecte `auto` al runner.
- ⏳ Normalitzadors del comparador (dates/signes/formes) i revisió dels 2 fixtures. ⏳ Fase 11 (delta-sync).

### Següents passos
Fase 11 (delta-sync) → 13 (`auto_result` + fonts Cadastre/ICGC al consolidador) → 14-15. Files d'effort/Bell-lloc al llibre ara
costen només la lectura. Decisions Josep: pla de subscripció; política de neteja `_preext/`.

*Fi entrada 2026-08-25 nit. Fase 12: consolidació Python-first (0,04 s, 0 erroni de fons, 0 pèrdues) amb `--only-fields` només per als conflictes reals.*

## 2026-08-25 (nit, 2) — Comparador d'or v2: normalitzadors de format i files de taula per clau; l'instrument deixa de fer soroll i destapa dos errors de fons que amagava

### Context
Handoff `_FOR-NEW-YOU-20260825-2200.md` §7.1: tots els ERR/ALERTA que quedaven al llibre eren de format (dates `2025-10-24` vs `24/10/2025`,
`-4 m` vs `-4,0 m`, `1,0 - 1,2 m` vs `-1,00 a -1,20 m`, formes de la mateixa adreça, `spt_ma` dict vs `1/0`, `PB+1 (…)`) o de fixture
(`sondeig cota` de Castellar anterior a la regla del sistema de cotes; `de_a_estat`). El Josep: «arrenca el punt 1; decideix si Sonnet pot fer-ne
part; no comencis les Fases 11/13-17». Decisió d'execució: els normalitzadors i les revisions de fixtures són judici sobre la veritat d'or → sessió
principal; a Sonnet només una **revisió adversària** (code-reviewer, encàrrec: trobar parells de valors realment diferents que `close()` ara donaria
per iguals — el risc d'aquesta tasca és afluixar l'instrument). Línia base comprovada abans de tocar res: els `.txt` desats eren idèntics al que
produïa el comparador v1 (cap deriva prèvia; tot canvi és atribuïble a v2).

### Decisions arquitectòniques clau
- **El comparador NO reutilitza `consolidate.value_key`.** Why: l'instrument d'acceptació no pot heretar els errors de l'objecte que mesura —
  si el consolidador fusionés malament dos valors, un comparador amb la mateixa clau ho donaria per OK. Alternativa rebutjada: importar
  `value_key` (menys codi); trade-off acceptat: dues implementacions de la mateixa idea (~150 LOC), alineades en intenció, no en codi.
- **`close(a, b, field)` per tipus, en ordre decisiu**: adreça (`street_address`: mateix nom de via i **mateix conjunt de portals** — una lectura
  parcial `18A` no és el mateix valor que `18A, 18B i 20`) → `spt_ma` per comptes → data (només si TOTA la cadena és una data: evita que
  `1,5-1,75` sigui una data) → nombres/intervals (guió entre dígits = separador d'interval; `abs` només a `ABS_FIELDS` = fondàries) →
  `num_floors` → `building_type` (subconjunt de tokens, memòria `feedback_building_type_close_match`) → text (regla històrica de contenció
  com a última xarxa + igualtat sense anotacions). Why: cada tipus té la seva noció d'igualtat; un sol `norm()` no pot ser alhora prou fi per
  a `-4` vs `-4,20` i prou tolerant per a `-4` vs `-4,0`. Els normalitzadors numèrics són també **més estrictes** que v1 (`1` ja no és "dins"
  de `12`). `No indicat` vs `No detectat` es manté ERR a posta: és vocabulari (resolt al skill v1.5), no format.
- **Files de taula alineades per clau** (`punt`, `sondeig`, capa vegetal / `nivell N`), índex com a fallback si les claus no són úniques als
  dos costats; `spt_ma_tests` per índex (etiquetes SPT-1/MA1 massa variables, l'or té una fila). Why: l'or de `soil_levels` té la capa vegetal
  com a fila pròpia + nivell 1; els runs amb una sola fila es comparaven creuats i sortien "OK" cel·les que no eren la mateixa capa.
- **Fixture Castellar `sondeig_tests[0].cota`: `segur 570,90` → `candidats` [`-4 m (respecte el carrer)` \| `570,90 msnm` \| `570,9`]**, cel·la
  amb clau `revisio`. Why: era l'ERR documentat de la lectura d'or de taules (informe signat de l'Eva: S-1 a −4,20 relatiu; regla v0.9/3b) i
  ningú l'havia corregit. `-4,20` **no** entra al fixture: cap document de la carpeta ho diu per a S-1 (cita real del manuscrit: `C/Arbrells -4 m`);
  posar-hi −4,20 legitimaria la invenció anotada al run `opus48-high`. Pregunta oberta a l'Eva registrada a `golden-read-taules/_RESULTATS.md`.
  `de_a_estat` NO es toca: el comparador l'expandeix (`_expand_de_a`), el fixture queda com es va llegir.
- **Traçabilitat dels totals**: cada `meta.json` porta `comparator_revision` (totals v1 i v2); `ledger.py` els mostra a «Condicions». El judici
  `erroni_amb_confianca_fons` es canvia 0 → 1 a dos runs del 24-08 (l'original queda a `erroni_amb_confianca_fons_v1`, amb nota). Why: la
  definició del llibre és mecànica (valor `segur` ≠ or) i el v2 hi troba una cel·la que el v1 no veia; deixar el 0 amb un ERR a la mateixa fila
  seria incoherent. Cap `.txt` ni `LEDGER.md` editat a mà.

### Implementació
`docs/wizard-headless/fase0-acceptacio/compare_consolida.py` (v1 100 LOC → v2 ~330 LOC; mateixa CLI, mateixes línies `OK|CAUTELA|ALERTA|ERR|ABSENT|NOU|VIOLACIO`
i `TOTALS:` que llegeixen `ledger.py` i `harness.py`; `main(argv)` en lloc de `sys.argv` a nivell de mòdul perquè sigui importable);
`tests/test_compare_consolida.py` (nou, 79 tests: 64 parells reals de `close()` + simetria + parsers + `row_key`/`align_rows`/`_expand_de_a` +
2 integracions sobre runs versionats); `docs/wizard-headless/mesures/ledger.py` (+8 LOC); fixture `golden-read-taules/3001621…/_tables_decisions.json`
(1 cel·la); `.txt` regenerats a 8 runs + `consolida2` + `fase12-consolida/out/` (5 jocs; `_decisions.json` idèntics, restaurats);
`meta.json` ×8 (`comparator_revision`, notes); `LEDGER.md` regenerat; `_RESULTATS.md` de fase0, fase12 (§7) i golden-read-taules (revisions).

### Validació empírica
Totals per run, comparador v1 → v2 (font: `meta.json` → `comparator_revision`):

| run | escalars OK / CAUT / ALERTA / ERR (v1 → v2) | taules OK / CAUT / ALERTA / ERR / ABSENT (v1 → v2) | fons |
|---|---|---|--:|
| `2026-08-24-e2e-tarda-c2-solapat` | 15 / 4 / 1 / 1 → **16 / 5 / 0 / 0** | 16 / 1 / 1 / 3 / 6 → **20 / 1 / 1 / 1 / 6** | 0 → **1** |
| `2026-08-24-sonnet-c2` | 14 / 4 / 2 / 1 → **15 / 5 / 1 / 0** | 20 / 1 / 2 / 1 / 3 → **24 / 1 / 1 / 0 / 3** | 0 |
| `2026-08-24-sonnet-c3` | 17 / 1 / 3 / 0 → **17 / 3 / 1 / 0** | 17 / 1 / 2 / 3 / 4 → **22 / 1 / 1 / 1 / 4** | 0 → **1** |
| `2026-08-25-fable-preext-v2-c3` | 14 / 5 / 1 / 1 → **15 / 6 / 0 / 0** | 23 / 2 / 0 / 0 / 2 → **24 / 3 / 0 / 0 / 2** | 0 |
| `2026-08-25-opus48-docs-python-consolida` | 14 / 5 / 2 / 0 → **14 / 7 / 0 / 0** | 22 / 1 / 1 / 1 / 2 → **27 / 2 / 0 / 0 / 0** | 0 |
| `2026-08-25-opus48-high-preext-v2-c3` | 13 / 4 / 3 / 1 → **14 / 5 / 2 / 0** | 22 / 1 / 1 / 1 / 2 → **28 / 1 / 0 / 0 / 0** | 0 |
| `2026-08-25-preext-c3` | 14 / 2 / 4 / 1 → **15 / 5 / 1 / 0** | 14 / 2 / 5 / 4 / 2 → **20 / 2 / 5 / 0 / 2** | 0 |
| `2026-08-25-preext-v2-c3` | 13 / 4 / 3 / 1 → **14 / 5 / 2 / 0** | 1 / 1 / 2 / 0 / 23 → **2 / 1 / 1 / 0 / 25** | 0 |

Tots els ERR de format han desaparegut. Els 3 ERR que queden són reals o de vocabulari: `soil_levels[1].de` `segur 0.00` vs or `-0,50` a
`e2e-tarda-c2-solapat` i `sonnet-c3` (capa vegetal absorbida al nivell 1; verificat mirant l'annex renderitzat: l'etiqueta «NIVELL 1» va al
costat de tota la columna però la descripció separa 0,00-0,50 vegetal / 0,50-1,20 substrat, i l'informe de l'Eva diu «1er nivell: Bretxes…
Substrat rocós»), i `nivell_freatic` `No indicat` a `consolida2`. `preext-v2-c3` puja d'ABSENT 23 → 25 perquè ara també compten `de`/`a`
(dialecte pla, ja anotat). Harness Fase 12 sota v2: taula i lectura a `fase12-consolida/_RESULTATS.md` §7 — 0 erroni de fons als 3 jocs v2;
el joc v1.3 en té 1 (heretat de la lectura, la referència LLM el té igual); forat nou: Python deixa `no_trobat` les fondàries de la capa vegetal
al joc Sonnet v2 quan la consolidació LLM les tenia.

### Tests
+95 (`tests/test_compare_consolida.py`; 79 abans de la revisió Sonnet). Suite de lectura + comparador: **283 passed / 2 skipped**.

### Limitacions conegudes
- Separadors de milers (`1.284` vs `1284`) no es normalitzen (cap cas als runs); `building_type` accepta subconjunt de tokens (una lectura parcial
  «habitatge unifamiliar» passa com a CLOSE d'«habitatge unifamiliar aïllat» — volgut per la memòria del Josep, però és la regla més laxa del fitxer);
  `spt_ma_tests` continua per índex; l'or només existeix per a Castellar i Bell-lloc.
- **Revisió adversària Sonnet (code-reviewer, 33 usos d'eina, 11 min):** 7 troballes, totes verificades executant `close()`. Corregides 6 (`dcda24f` → commit de tancament): (1) `row_key` posava «Nivell 2 - Reblert» com a capa vegetal → aparellament silenciós erroni (ara: senyal fort «vegetal/no numerat» abans del número de nivell, «reblert/relleno/cobertura» només després); (3) `num_floors` descartava tot després de la coma (`PB+2, amb soterrani` = `PB+2 (sense soterrani)`) → nucli + indicador amb/sense soterrani llegit a tota la cadena; (4) `1.655,01 m²` (fixture real d'Anciles) es llegia com dos nombres → milers a l'espanyola normalitzats; (5) un sol guió ` - ` es tractava com a nota (col·lapsava causes diferents) → només `--`; (6) adreces: tipus de via `polígon/nau/partida/urb.` afegits, un costat amb portals i l'altre sense = no close, i sense portals als dos costats mai contenció (`Polígon X` ≠ `Polígon X, Nau 5`); (7) `_expand_de_a` només separa ` a ` entre nombres. **No corregida, decisió:** (2) `building_type` — `habitatge unifamiliar` ⊂ `… entre mitgeres` és CLOSE per la regla del Josep (memòria `feedback_building_type_close_match`); documentat com la regla més laxa. Format de sortida: confirmat idèntic pel revisor. Cap veredicte dels 9 jocs ni del harness canvia amb les correccions (0 `.txt`/`meta.json`/`LEDGER.md` modificats). Tests 79 → 95.
- Descobert i NO fet (fora d'abast, "cap regla a ull"): (1) regla del Pas 3b per al `de` del nivell 1 (base de la capa vegetal); (2) el consolidador
  perd les fondàries de la capa vegetal al joc Sonnet v2; (3) `consolidate.value_key` pot llegir `1,5-1,75` com a data `2075-01-05` (latent: la
  comprovació `len(nums) ≤ 3` no ho evita; cap cas real als 7 jocs).

### GO/NO-GO
✅ Cap ERR de format als 9 jocs · ✅ Diferències d'ESTAT conservades (tests d'integració: `cota_referencia` puja a segur, `spt_ma` puja a segur) ·
✅ Format de sortida idèntic (ledger i harness funcionen sense canvis) · ✅ Fixture revisat amb evidència (informe Eva) i sense invenció ·
✅ Revisió adversària Sonnet (7 troballes: 6 corregides, 1 decisió; cap veredicte canvia) · ⏳ Pregunta a l'Eva (−4,20 de S-1; criteri de nivells).

### Següents passos
Fase 11 (delta-sync) → 13 → 14 → 15-17 (ordre del handoff 22:00). Abans o durant: mirar el forat de la capa vegetal a `consolidate.py`
i la regla del `de` del nivell 1 al skill (amb la resposta de l'Eva). Bell-lloc complet al llibre i files d'effort ara es llegeixen amb un
comparador que no fa soroll.

*Fi entrada 2026-08-25 nit (2). Comparador d'or v2: 0 ERR de format als 9 jocs, 2 erroni de fons amagats destapats, fixture `sondeig cota` revisat amb l'informe de l'Eva.*

---

## 2026-08-26 — Fase 8b: les taules llegides arriben al `.docx` (tram 1, peça 1)

### Context
Últim forat obert de la Fase 8 (`docs/wizard-headless/fase8-e2e/_RESULTATS.md`, punt 6): la via A llegia
`tables.{dpsh_tests, sondeig_tests, spt_ma_tests, soil_levels, superficie_construida}` amb candidats, font i cita,
l'Eva hi triava a la UI (`lecturaState.selections`) — i res d'això sortia del navegador. L'informe es generava amb
les taules de la via B (Excel + `sondeig_extracted.json`). Dit d'una altra manera: llegíem molt bé i imprimíem el
que llegíem abans. És la primera peça del **tram 1** de la proposta de priorització
(`docs/_TAULA-FASES-VS-EVA-2026-08-25.md`, §Proposta), triada perquè és petita i tanca la cadena lectura→informe.

Baseline mesurat abans de tocar res (Castellar generat avui vs informe signat): **54 %** de cel·les de taula
iguals o properes, amb la taula SPT/MA **buida sencera** i la cota de la taula DPSH repetida a totes les files.

### Decisions arquitectòniques clau

**1. Un mòdul de traducció pur, separat del consolidador i del generador** — `automation/lectura/tables_report.py`.
*Why:* el contracte (§4.3, regles 7-8) ja diu que **el lector emet dades i el generador formata**; barrejar el
format de l'informe dins de `consolidate.py` embrutaria l'actiu validat per la lectura d'or, i posar-lo dins de
`report_generator.py` el faria intestable sense generar un `.docx`. *Alternatives:* (a) formatar al skill — es
perdria la font per a la UI i caldria re-validar la lectura d'or sencera; (b) formatar a la UI en JavaScript — el
`.docx` deixaria de ser reproduïble fora del navegador (i l'acceptació d'aquesta fase és justament generar des d'un
`_decisions.json`). *Trade-off:* una capa més; a canvi, 49 tests sense docx ni servidor.

**2. El bloc es CONGELA a `user_data.json` en desar, no es recalcula en generar.**
*Why:* el que l'Eva ha vist i validat al wizard ha de ser el que surt a l'informe. Si es recalculés en generar, una
re-lectura posterior (Fase 11, delta-sync) li canviaria l'informe sota els peus sense avisar. *Trade-off:* el bloc
pot quedar desfasat respecte d'un `_decisions.json` nou; es refresca quan ella torna a desar, que és exactament el
moment en què l'ha tornat a mirar. *Fallback deliberat:* si `user_data` no en té, el generador llegeix
`validation/lectura/_decisions.json` directament — així un informe generat per CLI o per un arnès també surt amb
les taules llegides, sense passar pel wizard.

**3. Substitució EN BLOC, no cel·la a cel·la.** Quan la lectura porta files d'un bloc, aquell bloc de la taula es
substitueix sencer. *Why:* barrejar files de l'Excel amb files llegides produiria taules incoherents (files amb
sistemes de cotes diferents) i cap manera honesta d'explicar-ne l'origen a l'Eva. Els blocs que la lectura no ha
trobat es queden com estaven.

**4. Els nivells s'alineen per NÚMERO, no per índex.** `levels_by_number()` reutilitza el criteri del comparador v2
(senyal fort de capa vegetal abans del número de nivell). *Why:* l'or pot portar una capa vegetal sense numerar que
l'informe no té com a nivell propi; alinear per índex donaria la litologia de la capa vegetal al nivell 1 — el
mateix error que el comparador v2 va destapar el 25 (vegeu l'entrada «2026-08-25 (nit, 2)»).

**5. La litologia llegida NO s'escurça** (`SoilLevel.description_verbatim` + `_level_material`). *Why:*
`_shorten_material_desc` talla pel primer punt, pensat per a descripcions automàtiques de sondeig; aplicat a la
redacció que Eva ha triat entre candidats, «Substrat rocós. Bretxes amb intercalacions…» quedaria en «Substrat
rocós». La descripció llegida també substitueix `level.description`, així que la narrativa de la secció 3 i les
taules de permeabilitat i geotècnia parlen del mateix material amb les mateixes paraules.

**6. Les fondàries `de`/`a` viatgen però NO toquen els càlculs.** *Why:* `depth_from_m`/`thickness_m` alimenten
gruixos i taula sísmica; canviar-los és una decisió de càlcul (tram 3), no de taula. Frontera explícita al docstring
del mòdul perquè no s'esborri per descuit.

**7. La taula SPT/MA de la plantilla passa a ser un bucle** (`scripts/template_spt_ma_loop.py`, idempotent).
*Why:* tenia una fila fixa d'escalars i Anciles en necessita 3 (2 sondeigs, 3 mostres): amb la lectura omplint
`spt_ma_tests[]`, la fila única perdia dades reals **en silenci**. *Compatibilitat:* el generador emet sempre
`spt_ma_tests` — una fila construïda amb els mateixos escalars d'abans quan no hi ha lectura, fins i tot si és
buida — de manera que la sortida de la via B no canvia.

### Implementació
Nou: `automation/lectura/tables_report.py` (~390 LOC, stdlib pur excepte `load_project_tables`),
`scripts/template_spt_ma_loop.py`, `tests/test_lectura_tables_report.py` (49 tests),
`docs/wizard-headless/fase8b-taules/_RESULTATS.md`.
Tocats: `report_generator.py` (`lectura_tables`, `_apply_lectura_tables`, `_apply_lectura_soil_levels`,
`_level_material`), `report_data.py` (`SoilLevel.description_verbatim`), `wizard.py` (`save_wizard_data(extra=)`),
`web/api.py` + `web/wizard_service.py` (`lectura_selections` → `_build_lectura_block`),
`templates/validation/review.html`, `templates/g3dt-jinja-template.docx`.

### Validació empírica
Informe generat vs informe signat de l'Eva (`scripts/compare_tables_vs_eva.py`, 11 taules, cel·la a cel·la), mateix
`user_data` als dos costats i com a única diferència el bloc de la lectura d'or de taules:

| projecte | via B | + 8b |
|---|---|---|
| CASTELLAR | 54 % | **78 %** |
| RUBÍ | 64 % | **82 %** |
| BELL-LLOC | 76 % | 75 % |

Taula DPSH de Castellar: 12 M / 8 X → **20 M / 0 X**. Taula SPT/MA: buida sencera → 5 cel·les. El −1 pp de
Bell-lloc és **una** cel·la de format (`1/0` vs `1/--`) i ha generat la pregunta 7 a l'Eva. Via B verificada sense
regressió: Castellar abans i després = 26 M · 9 C · 30 X idèntic.

### Tests
49 nous (`tests/test_lectura_tables_report.py`). Suite sencera: 1411 passed / 32 failed — els 32 de la línia base
coneguda (SmartScan, ai_pipeline, fileminer Anciles), cap a lectura, wizard ni generador.

### Limitacions conegudes
- Només 3 dels 7 projectes tenen `user_data` reutilitzable a `reference-material/`: la mesura és sobre aquests tres.
- Les anotacions que el lector enganxa dins de `litologia` («… (NIVELL 1, 0.50-1.20)») encara arriben a la cel·la.
  Es corregeix al skill/consolidador: el generador no ha d'endevinar quin parèntesi és contingut i quin no. Sí que
  s'escapcen les de `n30` i `superficie_construida`, on el que queda davant és verificablement una xifra.
- El format de la columna SPT/MA no té regla derivable (4 informes, 4 formes) → pregunta 7.
- El bloc congelat no es refresca sol si `_decisions.json` canvia sense que l'Eva torni a desar (decisió 2).

### GO/NO-GO
✅ Les taules llegides surten al `.docx`. ✅ Les tries de l'Eva hi arriben. ✅ Via B sense regressió (verificat).
✅ Multi-fila SPT/MA provada al render. ⏳ Sense provar amb el wizard viu (Playwright) — el camí UI→backend està
cobert per tests unitaris, no E2E. **GO** per continuar amb la Fase 13.

### Següents passos
Tram 1, peça 2: **Fase 13** (`auto_result` a disc + Cadastre/ICGC al consolidador + residus Groq) — tanca el forat 1
de la Fase 8 i els MISMATCH d'escalars (superfície de parcel·la, UTM, RC) que aquesta mesura deixa a la vista.

*Fi entrada 2026-08-26. Fase 8b: la cadena lectura → informe queda tancada per a les taules de camp.*

---

## 2026-08-26 (tarda) — Fase 13: `auto_result` a disc i fonts HTTP al consolidador

### Context
Fila 13 del pla de l'annex (`DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` §10), en dues meitats:
§7.1 (persistir `AutoExtractionResult`) i el que quedava del forat 1 de `wizard-headless/fase8-e2e/_RESULTATS.md`
(les fonts Python — Cadastre, ICGC, geocodificació — no arribaven mai al consolidador). Continua l'entrada del matí
(Fase 8b). Commits `65786a1` i `89b8df2`.

### Decisions arquitectòniques clau

**1. La cache viu fora de la via B, en un mòdul propi, i els cridadors l'envolten.**
`automation/auto_result_cache.py` + `wizard_service._auto_extract_cached()`. `auto_extractor.py` no es toca (§9).
*Per què:* la via B és codi de producció que l'Eva fa servir cada dia i que aquesta branca no ha de moure. Un embolcall
també permet apagar la cache sencera amb una variable d'entorn sense tocar cap camí de dades.
*Alternativa descartada:* cachejar dins d'`auto_extract` (prohibit per §9, i barrejaria dues responsabilitats).

**2. L'empremta és el md5 del CONTINGUT, no `mida+mtime`.**
*Per què:* el delta-sync de la Fase 11 copiarà fitxers de la xarxa al workspace local; una còpia canvia l'mtime sense
canviar res, i amb `mtime` la cache no encertaria mai just després d'un sync — que és exactament quan interessa.
*Trade-off acceptat:* 0,46 s per als 56 MB de Castellar, contra els 40-141 s que estalvia. Mesurades les dues opcions
abans de triar (0,001 s vs 0,46 s).

**3. Les exclusions de l'empremta es van determinar mesurant, no llegint codi.**
Snapshot md5 de les 173 entrades de Castellar abans i després d'un `auto_extract` → l'únic fitxer que canvia fora de
`validation/` és `file_mapping.json`. La llista queda curta a posta: **excloure de menys costa una re-execució;
excloure de més serveix dades velles**.
*Conseqüència no òbvia:* `file_mapping.json` i `concept_map.json` són fora de l'empremta però `_merge_prefills` els
rellegeix del disc. Es desa quines d'aquestes sortides existien i es comprova que hi segueixin sent (barrera 4).

**4. TTL de 30 dies, i no només empremta.**
*Per què:* `inputs_md5` no veu els camps que vénen d'ICGC/Cadastre per HTTP — la parcel·la pot canviar sense que cap
fitxer del projecte es mogui.

**5. Les fonts HTTP entren al consolidador per la porta dels derivats: només forats.**
`http_field_signals()` es crida al mateix `if` que `derived_field_signals()` (només quan CAP document de la carpeta ha
dit res del camp).
*Per què:* és la traducció literal de la regla del disseny — cap font Python pot *guanyar* un camp contra la lectura.
*Alternativa descartada:* afinar la confiança perquè el senyal no bloquegi `segur` (conf < 0,4). Funciona, però depèn
d'un número màgic per sota de dos llindars; si algú abaixa `CONTRADICTION_CONF`, les consultes HTTP comencen a bloquejar
lectures correctes. La porta és estructural i no es pot desafinar.

**6. El valor HTTP surt de `validation/_auto_result.json` llegit amb `auto_result_cache.load()`, no d'una crida nova.**
*Per què:* manté el consolidador sense xarxa, i la validació d'empremta garanteix que no se serveixi una consulta feta
sobre una altra versió de la carpeta. L'ordre funciona sol: TEMPS 1 acaba en minuts i la consolidació arriba al final de
TEMPS 2, que triga desenes de minuts. **13(a) va resultar ser l'habilitador de 13(b)**, cosa que no estava prevista.

**7. El Cadastre queda implementat i apagat per defecte.**
*Per què, amb números:* a Castellar l'or de lectura diu `no_trobat` per a `referencia_catastral` i `superficie_parcela`
(els documents no els contenen), el Cadastre respon **441 m²** i l'informe signat de l'Eva diu **1.284** (verificat a
`eva_reference_values.json`). Encendre'l passa `compare_consolida.py` de 14 OK / 7 CAUTELA a 12 OK / 7 CAUTELA /
**2 ALERTA** als quatre jocs de Castellar. Concorda amb el diagnòstic 2026-08-23 (parcel·la equivocada a 4/8).
*Per què no esborrar-ho:* als projectes on el Cadastre encerta és l'única font d'aquests dos camps. Encendre'l — potser
per projecte, lligat a la validació visual de parcel·la (P4) — és decisió del Josep, no d'aquest mòdul.
`G3DT_LECTURA_HTTP_SOURCES` controla les tres fonts.

**8. §8 (residus Groq a TEMPS 1): mantenir-los tots tres.** Decisió del Josep, presa amb l'evidència d'aquesta sessió.
*Per què:* 13(a) elimina la palanca que els condemnava (ja no es paguen a cada obertura, sinó una vegada per projecte);
són l'única font de ~15 camps de grup B; i els valors dolents es tapen amb **precedència**, no esborrant la font.

### Implementació
- `automation/auto_result_cache.py` (nou, ~380 línies): empremta, serialització genèrica dataclass/pydantic, quatre
  barreres, escriptura atòmica, replay d'events de progrés.
- `web/wizard_service.py`: `_auto_extract_cached()` + 2 punts de crida. `web/lectura_service.py`: 1 punt.
- `automation/lectura/consolidate.py`: `http_field_signals()`, `_auto_result_prefills()` (memoritzat per mtime+mida),
  `_http_enabled_sources()`, i la crida dins de `consolidate_python`.
- `.gitignore`: `**/validation/_auto_result.json`.

### Validació empírica
- `get_prefills` sencer a Castellar: **40,4 s → 5,6 s**, 121/121 claus iguals. L'única diferència,
  `terrain_observation`, varia igual entre dues execucions sense cache (comprovat) — és una crida de visió sobre fotos
  dins de `_merge_prefills`, fora d'`auto_extract`.
- Segona càrrega amb `auto_extract` substituït per una excepció: passa. Cap crida de xarxa ni de Groq a TEMPS 1.
- Round-trip exacte sobre dades reals: 69 prefills, 84 signals, 18 rols, `serialize(load()) == desat`.
- Comparador d'or amb el defecte: idèntic a la base als 5 jocs, verdicte a verdicte.

### Tests
36 nous (28 `tests/test_auto_result_cache.py`, 8 a `tests/test_lectura_consolidate.py`).
Suite: **1456 passed / 32 failed** (els 32 coneguts: SmartScan, ai_pipeline, fileminer Anciles).

### Limitacions conegudes
- La mesura de (b) és d'**un sol projecte** (Castellar); Bell-lloc no es mou perquè allà els documents ja diuen els dos
  camps. Els altres sis no tenen or de lectura consolidat amb què comparar.
- Dos valors Groq erronis segueixen sense tapar: `superficie_parcela_m2=32980` (la lectura diu `no_trobat` i
  `_apply_lectura_overlay` no escriu res amb `no_trobat`) i `lab_company='Lab. Valdemoro'` (no és a
  `MAPPING_DECISIONS_WIZARD`; el lab sempre és TPS).
- `ANTHROPIC_API_KEY` del `.env` sense saldo: `_synthesize_with_llm` falla en silenci a cada execució de la via B.
- El primer open d'un projecte que no ha passat mai pel wizard segueix pagant TEMPS 1 sencer, per disseny.

### GO/NO-GO
- ✅ 2a càrrega sense xarxa ni Groq → prefills iguals (121/121, l'excepció justificada i verificada).
- ✅ Invalidació per `inputs_md5` (i per TTL, versió i sortides acompanyants).
- ✅ Comparador d'or sense moure's amb la configuració per defecte.
- ✅ Via B intacta; suite a la línia base.
- ⏳ Encendre el Cadastre: decisió del Josep, amb la mesura sobre la taula.

### Següents passos
Tram 1, peça 3: forat de la capa vegetal a `consolidate.py`. Després 14a (botons + taula d'estat) i 15 (notificacions).

*Fi entrada 2026-08-26 (tarda). Fase 13: TEMPS 1 deixa de repetir-se, el consolidador ja veu l'ICGC i la geocodificació, i el Cadastre queda mesurat i apagat.*

---

## 2026-08-26 (vespre i nit) — Tram 1 tancat: capa vegetal, delta-sync, tres botons i avisos

### Context
Continuació directa de les dues entrades d'avui (Fase 8b al matí, Fase 13 a la tarda). Aquí hi caben les quatre peces
que tanquen el tram 1: l'arranjament de la capa vegetal (`cef49ba`), les Fases 14a (`ea82efe`), 15 (`da53e17`), 11
(`4e4146b`) i 14b (`3a4e382`). Pla: `DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` §10.

### Decisions arquitectòniques clau

**1. La capa vegetal recupera fondàries per posició, no per numeració.**
La fila de la capa vegetal no té fondàries a cap font primària (el `tall.pdf` la dibuixa sense), i les reals només són
al full de camp, que les numera amb la SEVA numeració — que `level_key()` ignora a posta. Regla nova: si la capa vegetal
no té fondàries de ningú, l'única fila que li'n pot donar és la que arrenca a la superfície (≤ 5 cm).
*Per què posicional:* no depèn de la regla del Pas 3b sobre el `de` del nivell 1, que espera la pregunta 3 de l'Eva.
*Efecte mesurat:* `sonnet-v2-c3` TAULES 26 OK / 1 CAUTELA / **2 ALERTA** → 25 OK / **4 CAUTELA / 0 ALERTA**.
*Efecte secundari que NO és una regressió:* en desaparèixer la fila espúria, NIVELL 1 passa a ser l'últim nivell i
s'hi aplica una regla del Pas 3b que ja existia i que `sonnet-c3-v13` ja tenia. Els dos jocs de Castellar coincideixen.
*Deixat obert amb motiu:* l'ALERTA de Bell-lloc (`de = 0.00 segur`) **no és del consolidador** — cap document d'aquella
lectura reporta la capa vegetal; l'or la parteix llegint la transició gràfica del log. És un forat de lectura.

**2. El text de la taula d'estat es redacta en Python, no en JavaScript.**
`automation/lectura/job_text.py`; `GET /api/jobs` hi adjunta una clau `eva` **afegida**, mai substituint el snapshot.
*Per què:* `review.html` fa 10.000 línies i no té cap test; el projecte en té 1.569 en pytest. Les regles de §3.3 són
regles (arrodonir, dir «restants», que «Interromput» no soni a error), no decoració.
*Trade-off acceptat:* una anada i tornada més de dades a l'API a canvi de cobertura real.

**3. L'arrodoniment del disseny es matisa amb el seu propi exemple.**
§3.3 diu «a 5 min», però l'exemple de §3.3 per al delta de xarxa és «Enllestir ≈ 8 min». Arrodonir 8 a 10 és un 25 % de
més justament on la xifra importa. Regla: segons mai, minut exacte fins a 10 min, múltiples de 5 a partir d'allà. Els
dos exemples del disseny surten exactes.

**4. «Preparar» no obre cap SSE.**
El disseny deia obrir l'stream «només per pintar progrés». *Per què no:* ningú espera, el refresc de 5 s de la taula ja
ensenya el progrés real, i §6.1 ja diu que la taula és la veritat. Així tancar la pestanya no costa literalment res —
que és el sentit del botó.

**5. Sonda `GET /api/lectura/enabled` en lloc de llegir un 404.**
La resta d'endpoints del pipeline fan 404 amb el flag apagat, i està bé per a una API. Però `fetch()` d'un 404 deixa una
línia vermella a la consola encara que el codi el gestioni, i el criteri de la fase és **0 errors de consola també amb
el flag apagat**, on la UI d'avui no ha de canviar en res.

**6. El sanejament del log del CLI s'inverteix a llista blanca.**
§6.4 deia substituir els noms de fitxer per `doc_{i}`. *Per què no n'hi ha prou:* el test amb un projecte sintètic ple
de noms de persona va ensenyar que el log porta **valors de camps** («client detectat: …»); cap substitució ho pot
cobrir, perquè el que hi surt és el que el model hagi llegit del document, i la regla del mateix §6.4 és «mai valors de
camps ni cites». Ara només sobreviuen les línies que contenen vocabulari tècnic conegut, i de la resta se'n diu el
recompte.
*Excepció documentada i provada:* el missatge d'`error_event` l'escriu el nostre propi codi Python — se'n controla la
forma — i passa per la substitució però no per la llista blanca.

**7. El delta-sync compara mida+mtime i només fa md5 quan difereixen.**
*Per què:* llegir totes les fotografies per SMB per demostrar que no han canviat costa més que la còpia sencera.
Tolerància d'mtime de 2 s perquè FAT/SMB arrodoneixen i `copy2` hi perd precisió — sense això tot sortiria canviat
després de cada còpia. *Trade-off acceptat i escrit al disseny:* un fitxer amb la mateixa mida i el mateix mtime que hagi
canviat de contingut passaria per igual.

**8. El que desapareix de la xarxa es MOU, mai s'esborra; i el que produeix el pipeline no es pot moure.**
Llista explícita (`file_mapping.json`, `user_data.json`, `*_generated.docx`…). *Per què explícita:* errar aquí seria
apartar l'informe de l'Eva a `_esborrats/` com si l'haguessin esborrat de la xarxa. I encara que s'erri, es mou.

**9. `network_delta` es calcula en mode `check`, cachejat 1 minut i amb sostre de 5 projectes per crida.**
Recórrer una carpeta compartida són centenars de `stat` per SMB (§13). Quan es retalla, es diu al log: cap sostre
silenciós. Si la xarxa no es pot llegir, `network_delta` queda a `None` i la fila **no diu res** sobre la xarxa — millor
que afirmar «res ha canviat» sense haver mirat.

### Implementació
- `automation/lectura/consolidate.py`: `_cover_lacks_depths()` + regla de superfície a `_group_soil_levels`.
- `automation/lectura/job_text.py` (nou), `automation/lectura/notify.py` (nou).
- `automation/lectura/jobs.py`: `telemetry_medians()` + `estimate_for_documents()` extrets d'`estimate_remaining`.
- `automation/sync_workspace.py`: `sync_delta()`, `sync_delta_for_leaf()`, `network_path_for_leaf()`. `sync_to_workspace` intacte.
- `web/lectura_service.py`: clau `eva`, `network_delta` cachejat, `_notify_finished`, `list_jobs(refresh=)`.
- `web/api.py`: `GET /api/lectura/enabled`, delta-sync al `POST /api/jobs`, `refresh` al `GET /api/jobs`.
- `templates/validation/review.html`: bloc autocontingut (CSS + `#jobsPanel` + JS). `nbSetState` **embolcallada**, no
  editada. Únic canvi a codi existent: `openLecturaStream(project, {attach})`.
- `.env.example`: 9 variables `G3DT_NOTIFY_*`.

### Validació empírica
- Comparador d'or: `sonnet-v2-c3` de 2 ALERTA a **0**; els altres 4 jocs sense moure's.
- Navegador (Playwright, servidor real): flag ON → panell, files amb el text de §3.3, comptador en negreta, el 9/17
  arriba sol; flag OFF → panell ocult i botó d'avui intacte; «Actualitzar» → «res no ha canviat» → «1 document nou →
  Enllestir ≈ 15 min» → «2 documents nous», amb el workspace sense tocar. **0 errors de consola als dos casos.**
- Fuita real destapada pel test de notificacions (valors de camps al log del CLI), i tapada.

### Tests
109 nous en total (4 capa vegetal + 42 de 14a + 34 de 15 + 29 de 11/14b).
Suite: **1569 passed / 32 failed** (els 32 coneguts: SmartScan, ai_pipeline, fileminer Anciles).

### Limitacions conegudes
- El toast no s'ha vist mai en una màquina Windows real: dues estratègies implementades a cegues (Fase 17).
- L'SMTP no s'ha provat contra cap servidor real, només contra un de casa (Brevo vs bústia: decisió §12.6).
- La mesura del delta-sync és sobre arbres temporals locals, no sobre SMB: el risc de `stat` lent amb carpetes de
  fotografies (§13) segueix sense mesurar.
- L'ALERTA de Bell-lloc i la CAUTELA de Castellar segueixen obertes (STATUS open item 0d, pregunta 8 a l'Eva).

### GO/NO-GO
- ✅ Comparador d'or sense ALERTA a Castellar; els altres jocs sense moure's.
- ✅ 0 errors de consola amb el flag encès i apagat; UI d'avui intacta amb el flag apagat.
- ✅ Cap avís pot fer caure un job; cap valor de camp surt per correu.
- ✅ `sync_to_workspace` i la via B intactes; suite a la línia base.
- ⏳ Fase 16 (mesurar els tres botons de veritat) i Fase 17 (Windows presencial).

### Següents passos
Fase 16: E2E dels tres botons sobre Castellar sol, amb «xarxa» simulada, per omplir la taula de temps de §2 amb xifres
reals. Fase 17: presencial a l'ordinador de l'Eva.

*Fi entrada 2026-08-26 (vespre i nit). Tram 1 tancat: la lectura surt del camí crític de l'Eva i la taula li ho explica.*

## 2026-08-31 — `PLA-PENDENTS-0B-0C-0D-2026-08-26.md` tancat: comparador v3, `value_key`, Castellar dialecte v2, residus Groq a l'origen, Cadastre multi-portal, Bell-lloc via mínima

### Context
Sessió d'anàlisi del 2026-08-31 (nit) va re-mesurar en viu els tres pendents que el 26/08 havien quedat oberts com a
"per analitzar-ho posteriorment" (STATUS.md 0b/0c/0d) i va escriure `docs/PLA-PENDENTS-0B-0C-0D-2026-08-26.md` amb el
resultat: **cap dels tres pendents era el que semblava**. 0b (Cadastre): no falla — l'Eva suma tres portals, no un.
0c (Groq): els dos valors erronis venen de fonts que mai s'havien mirat de prop (una cel·la de pressupost, un número
de bloc cadastral imprès en un mapa). 0d (Bell-lloc): l'ALERTA és un forat de lectura, no del consolidador, i té una
via mínima sense inventar cap xifra. El pla també va destapar un forat de comparador (verdictes `OK`/`ALERTA` massa
grollers per mesurar D i E) i un forat de `value_key` (dates que capturaven massa, guions llegits com a signe). El
mateix dia es van implementar els 6 fixos + aquest tancament de docs, en dues sessions (F/A/B/C al vespre, D/E/docs a
la nit), commits `3694694`→`2486a53`. Handoffs intermedis: `docs/_FOR-NEW-YOU-20260831-2018.md` (F/A/B/C),
`docs/_FOR-NEW-YOU-20260831-2145.md` (D).

### Decisions arquitectòniques clau

**1. Comparador d'or: tres verdictes nous en comptes d'ampliar `ALERTA`.** (`compare_consolida.py::verdict()`, commit
`3694694`). *Per què:* abans, `candidats` vs `candidats` sortia `OK` sense mirar valors, i qualsevol `no_trobat` de
prod contra un or amb contingut sortia `ALERTA` — tant si era un blanc honest com un candidat correcte de fora de la
carpeta. Sense distingir-los, D i E no es podien mesurar (el Cadastre és per definició `no_trobat`→`candidats` amb
font externa). `BUIT` (or amb valor, prod `no_trobat`: honest, tolerat), `CAUTELA candidats disjunts` (cap candidat
coincideix: visible, no silenciat com a `OK`), `FORA` (or `no_trobat` + `fora_carpeta` que sí coincideix amb el
candidat de prod: font externa correcta). *Alternativa descartada:* ampliar `ALERTA` amb sub-missatges — calia que
`BUIT`/`FORA` puntuessin diferent a `harness.RANK` (1 i 0, no 2), si no la mètrica agregada els seguiria tractant com
un fracàs.
*Efecte secundari trobat mesurant, no al pla:* `flat_gold_scalars` no propagava `candidates` ni `fora_carpeta` dels
fixtures d'escalars — calia perquè `candidats` vs `candidats` ara mira valors (si no, `architect_name`, que sí té 2
candidats reals a l'or, hauria sortit `CAUTELA disjunts` fals amb `or=[]`).

**2. `value_key` ancorat amb `fullmatch`, guió entre dígits = interval.** (`consolidate.py::_parse_date`/`_numbers`,
commit `d6aa855`). *Per què:* `_DATE_DMY_RE.search("1.5-1.75")` trobava "5-1.75" com a data (`2075-01-05`) perquè
`search` no exigeix que TOTA la cadena sigui data; i `_numbers` llegia el guió d'un interval com a signe negatiu
(`"0,50-1,20"` → `(0.5, -1.2)` en comptes de `(0.5, 1.2)`), fent que el mateix interval amb espais diferents
(`"0,50 - 1,20"`) NO clusteritzés amb l'equivalent sense espais. Cap cas real als 5 jocs (forat latent, 0 verdictes
canvien) — però la mateixa regla ("data només si TOTA la cadena ho és") ja l'aplicava el comparador v2 des del
25/08; aquest fix l'alinea al costat que genera els valors.

**3. Or de Castellar `soil_levels[1].a`: dialecte v2, no un canvi de valor.** (`docs/golden-read-taules/.../
_tables_decisions.json`, commit `e8d1cc8`). *Per què:* l'or ja deia literalment «≥ -1,20 (fins al final del
reconeixement; el tall el dibuixa fins a la base)» — el mateix hedge que la regla del Pas 3b (`consolidate.py:1291-
1295`, la base de l'últim nivell sempre baixa a `candidats`) — però una cadena plana s'adaptava com a `segur`
(`wrap_flat_cells` hereta l'`estat` de la fila). Regla i or ja coincidien; només calia escriure la cel·la com a dict
v2 perquè el comparador ho veiés. *Per què NO era un error de mesura ni un canvi de criteri:* el valor `-1,20` no es
toca, només l'`estat`.

**4. Residus Groq: filtrats a l'origen, no esborrats per `no_trobat` de la lectura.** (`groq_miner.py`,
`vision_probe.py`, `concept_scout/__init__.py`, commit `a423f6a`). *Per què `lab_company` fora de `TARGET_VARIABLES`:*
el laboratori es resol determinísticament pel NIF (`gtl_lab_identity`); Groq només hi podia aportar soroll (una línia
de cost «Lab. Valdemoro» del pressupost, mai llegida com a laboratori per cap altra font). *Per què cap probe de
`map`/`site_photo` pot emetre `superficie_*`:* el 32980 de Castellar és el número de **bloc** cadastral imprès en un
mapa (`ANNEXES/ALTRES/m8.png`), no una àrea — un mapa mostra identificadors, no mides. Dos punts de tall (parse de la
probe nova + `concept_sources_to_signals` per a `concept_map.json` ja cachejat), perquè hi ha dos camins d'entrada al
pool de senyals. *Per què NO "un `no_trobat` de la lectura esborra el valor de la via B":* trenca la regla 4 del
contracte (`_apply_lectura_overlay`) i converteix un forat de lectura en un blanc a l'informe — decisió explícita de
NO fer-ho (§6.3 del pla), documentada perquè no es torni a proposar.

**5. Lector Cadastre a la via A (`automation/lectura/cadastre_reader.py`, nou), no arreglar la via B.** (commit
`349ecca`). *Diagnòstic corregit primer:* el Cadastre no falla — per «Carrer Arbrells 18A» torna la parcel·la
correcta (441 m²); l'Eva escriu **1.284 = 441+423+420**, la suma dels **tres portals** que els documents anomenen
(«18A, 18B i 20»). El «4 dels 8 projectes amb la parcel·la equivocada» del diagnòstic 23/08 era el *matcher* de la
via B (`geocode_coordinates._pick_nearest_rc_from_numerero`, agafa el portal MÉS PROPER quan hi ha lletra) acceptant
un portal diferent del que demanava l'adreça (Tulipa 3→11) — un bug diferent, no del Cadastre. *Per què un mòdul nou
i no arreglar `_pick_nearest_rc_from_numerero`:* la via B és codi de producció que l'Eva fa servir cada dia (marc
fixat §1 del pla: es pot importar, no modificar); i el bug de "portal més proper" és un comportament volgut en un
altre context (geocodificació aproximada), no un bug aïllable sense risc. *Per què sempre `candidats`, mai `segur`:*
és una consulta HTTP, no una lectura d'un document de la carpeta (mateix patró que ICGC/geocodificació, `_HTTP_CONF
= 0,5 < CONV_CONF`). *Per què `cp:areaValue` del WFS i no `shapely.Polygon.area`:* shapely arrodoneix 441→440,75…;
l'oficial suma exacte a 1.284. *Per què filtrar `(pnp, plp)` exactes i no delegar a `callejero_address_to_rc`:*
aquesta funció ja pateix el bug del punt 4 (18B→18A, el més proper) — delegar-hi hauria reproduït el mateix error que
es documenta. *Per què `_HTTP_SOURCES_DEFAULT` s'encén a la MATEIXA commit:* el Josep ja ho havia autoritzat abans de
la implementació (memòria `project_pla_0b0c0d_not_implemented_decisions_2026-08-31`); el pla original deia "deixa'l
apagat" quan encara no hi havia decisió — ara sí que n'hi havia.
*Verificat EN VIU, no només per lectura de fixtures:* Castellar 18A+18B+20 → 441+423+420 = 1.284, exacte amb
l'informe signat; 6 dels 7 projectes de referència resolubles coincideixen amb l'adreça de la lectura (Rubí no
resol via `ConsultaVia`: blanc honest, no un error).

**6. Bell-lloc: via mínima de la llegenda del tall, mai mesurar píxels.** (skill v1.6 + `consolidate.py` E2/E2b,
commit `2486a53`). *Diagnòstic:* l'ALERTA (`soil_levels[1].de` puja a `segur 0,00` fora dels candidats de l'or) no és
del consolidador — cap document de la lectura reportava la capa de cobertura («Sòls vegetals») com a fila pròpia;
l'annex de sondeig emet una sola fila 0,00-1,80 amb la litologia dels dos trams junts, i l'or la parteix llegint la
transició GRÀFICA del tall (píxels, −0,30 m ±0,05). *Per què el skill no mesura píxels per igualar l'or:* trencaria
"mai falsa confiança" amb una precisió que ni el propi skill pot citar (regla existent del Pas 3b, reforçada aquí).
*E2b — la cobertura sense fondàries arrenca a `segur "0,00"` (decisió del Josep, no `candidats`):* és una regla
geomètrica (tota cobertura comença a la superfície, per definició), no una lectura ambigua d'un document — diferent
de `de`/`a` normals, que SÍ depenen del que hi hagi imprès. *E2 — el nivell 1 baixa a `candidats` només si la
cobertura NO té base documentada I el nivell 1 arrenca a ≤0,05:* aquesta doble condició evita disparar sobre files
que ja tenen una base coneguda (Castellar, amb el full de camp) o sobre files profundes sense relació amb la
superfície (test `test_a_deep_row_never_lands_on_the_cover_layer`).
*Verificat amb una re-lectura real* (no només amb un corpus sintètic): 1 crida `claude -p` sobre el tall de Bell-lloc
amb el skill v1.6, `source_md5` idèntic (confirma que és la mateixa versió del document, no un altre fitxer), 2m24s.
L'ALERTA desapareix de l'harness.

**7. Decisions que queden per al Josep, recollides en un sol lloc (pla §11):** totes resoltes durant aquesta feina —
(a) encendre `cadastre` per defecte: **sí** (punt 5); (b) E2b `segur` vs `candidats`: **segur** (punt 6, decidit
2026-08-31 en aquesta sessió); (c) crida LLM de §8.4: **autoritzada**, model per defecte del runner (`sonnet`).
Pendent real: enviar a l'Eva les preguntes 3+8 (juntes, són la mateixa) i les noves 9 (Vilanova: parcel·la/construïda
intercanviades?) i 10 (Castellar: la suma de tres portals és el criteri habitual?) — vegeu
`docs/PREGUNTES-EVA-PENDENTS.md`.

### Implementació
- Nou: `automation/lectura/cadastre_reader.py` (~230 línies: `portals_from_address`, `resolve_portal`,
  `parcel_area_and_polygon`, `cadastre_portal_signals`), `tests/test_lectura_cadastre_reader.py` (29 tests, fixtures
  reals a `tests/fixtures/cadastre_castellar/`).
- Modificats: `docs/wizard-headless/fase0-acceptacio/compare_consolida.py` (`verdict()` + 3 verdictes),
  `docs/wizard-headless/fase12-consolida/harness.py` (`RANK`/`_LINE` amb `BUIT`/`FORA`), `automation/lectura/
  consolidate.py` (`_parse_date`/`_numbers` ancorats; `_COVER_RE` ampliat; bloc E2/E2b de `soil_levels`; `order`
  amb `referencia_catastral`/`superficie_parcela` al final; `_HTTP_FIELD_SOURCES` sense les entrades `cadastre`;
  `_HTTP_SOURCES_DEFAULT` encès), `automation/fileminer/miners/groq_miner.py` (`TARGET_VARIABLES` sense
  `lab_company` + guarda de variables no demanades), `automation/concept_scout/vision_probe.py` +
  `concept_scout/__init__.py` (guarda `map`/`site_photo` no emet `superficie_*`), `.claude/commands/
  g3dt-llegir-projecte.md` (v1.6, bloc «Nivells del sòl»).
- Or: `docs/golden-read-taules/3001621 CASTELLAR DEL VALLES/_tables_decisions.json` (dialecte v2),
  `docs/golden-read/3001621 CASTELLAR DEL VALLES/_decisions.json` (`fora_carpeta` a `referencia_catastral`/
  `superficie_parcela`, anotació, no canvi de veredicte).
- Commits: `3694694` (F), `d6aa855` (A), `e8d1cc8` (B), `a423f6a` (C), `349ecca` (D), `2486a53` (E).

### Validació empírica
- **F:** 0 línies `OK`→`ALERTA` als 5 jocs (acceptació complerta); diferències explicables (`cte_sol` `CAUTELA
  disjunts` per un buit del fixture, no una regressió).
- **A:** 0 verdictes canvien als 5 jocs (forat latent, cap cas real al corpus mesurat).
- **B:** `sonnet-v2-c3` TAULES `OK 25→26, CAUTELA 4→3`; la `CAUTELA soil_levels[1].a` desapareix als 4 jocs de
  Castellar; cap ALERTA nova.
- **C:** harness idèntic (Groq no passa per la consolidació de lectura); efecte confirmat aigües avall (`.docx` de
  l'E2E ja deia TPS abans, la guarda evita que torni a passar).
- **D:** dues passades (OFF/ON). OFF idèntic al post-F baseline. ON: Castellar ×4 → `referencia_catastral`/
  `superficie_parcela` `no_trobat`→`FORA` (2 cadascun), 0 ALERTA nova; Bell-lloc 0 diferències (porta tancada).
  Taula completa: `docs/wizard-headless/fase12-consolida/_RESULTATS.md` §8.3.
- **E:** Bell-lloc `TAULES {OK 15→16, CAUTELA 3→4, ABSENT 2→BUIT 1, ALERTA 1→0}` — **l'ALERTA desapareix**. Efecte
  lateral a `sonnet-c3-v13` (lectura antiga): `BUIT 2→1` (millora), `ERR 1`→`ALERTA 1` (mateixa severitat al harness,
  `RANK["ERR"]==RANK["ALERTA"]==2`; arrel al perdoc antic, no al consolidador). Taula completa: mateix fitxer §8.4.
- Suite completa final: **1640 passed / 32 failed** (els mateixos 32 coneguts: SmartScan, ai_pipeline, fileminer
  Anciles, `test_groq_miner::TestCache::test_cache_hit`).

### Tests
9 nous a `tests/test_compare_consolida.py` (matriu de verdictes), ~9 a `tests/test_lectura_consolidate.py` (Fix A),
tests de Fix B dins dels fixtures d'or (sense test nou de codi), tests a `tests/test_groq_miner.py` +
`tests/test_vision_probe_gate_and_prompt.py` (Fix C), 29 a `tests/test_lectura_cadastre_reader.py` + 3 reescrits a
`tests/test_lectura_consolidate.py` (Fix D), 9 a `tests/test_lectura_consolidate.py` (`_belloc_soil_corpus`, Fix E,
incl. 1 test pre-existent (`test_a_deep_row_never_lands_on_the_cover_layer`) actualitzat perquè assumia el
comportament pre-E2b). Total: **1640 passed / 32 failed**, de 1569 a l'inici del dia.

### Latència / cost
- Fix D: cache nova (`config.cache_dir("cadastre_portals")`, TTL 90 dies) evita repetir Callejero/WFS; sense ella,
  cada consolidació d'un projecte nou faria 4 crides HTTP lentes (2 camps × municipi+via) a més de DNPLOC/WFS.
  `_cached_consulta_municipio`/`_cached_consulta_via` (guany no previst al pla, trobat mentre es mesurava): la
  consolidació baixa de ~6s (fred) a ~0,2s (calent).
- Fix E: 1 crida `claude -p --model sonnet --effort xhigh` sobre 1 document, **2m24s** (dins l'estimat 2-4 min del
  pla).

### Limitacions conegudes
- Fix D només mesurat amb dades reals a Castellar (l'únic amb or `fora_carpeta`); Vilanova (pregunta 9) i Rubí (blanc
  honest) queden com a annex del pla, no com a test automatitzat.
- Fix E resol Bell-lloc; la pregunta 3/8 a l'Eva (etiqueta de la transició cobertura/nivell 1) segueix oberta —
  `soil_levels[1].de` de Bell-lloc queda `candidats`, no `segur`, fins que respongui.
- `sonnet-c3-v13` (lectura de 2026-08-24) segueix tenint un `ALERTA` real (relabelat d'`ERR`): aquell perdoc concret
  mai va separar la capa vegetal del substrat en dues files. Fora d'abast d'aquest pla (és un forat de lectura d'un
  run antic, no reproduïble amb el skill v1.6 sense una re-lectura completa que no s'ha demanat).
- Fase 16 (E2E dels tres botons amb temps remesurats) encara no s'ha tornat a mesurar amb Cadastre ON per defecte:
  la primera consolidació de cada projecte farà ara crides HTTP noves (DNPLOC+WFS) que no hi eren al Fase 13.

### GO/NO-GO
- ✅ Comparador mesura D i E sense soroll (`BUIT`/`CAUTELA disjunts`/`FORA` separats d'`ALERTA`).
- ✅ Castellar `FORA` ×2 amb Cadastre ON, 0 ALERTA nova, Bell-lloc intacte.
- ✅ Bell-lloc: l'ALERTA de `soil_levels[1].de` desapareix, verificat amb una re-lectura real (no només un test
  sintètic).
- ✅ Via B intacta (`git diff --stat` buit als 7 fitxers protegits).
- ✅ Suite: 1640 passed / 32 failed (els mateixos 32 de sempre).
- ⏳ Docs restants d'aquesta mateixa entrada: STATUS.md, `PREGUNTES-EVA-PENDENTS.md`, session log, handoff, memòria
  (es tanquen al mateix commit que aquesta entrada).
- ⏳ Fase 16 (E2E remesurat amb Cadastre ON) i Fase 17 (Windows presencial): properes sessions.

### Següents passos
Enviar a l'Eva les preguntes 3+8+9+10. Fase 16 (E2E dels tres botons, ara amb Cadastre ON per defecte — anotar les
crides HTTP noves de la primera consolidació de cada projecte). Fase 17 (Windows presencial), sense canvis.
Objectiu de fons sense tocar en aquest pla: grup B i la resta de les 341 variables (memòria
`feedback_full_report_341_variables_goal`).

*Fi entrada 2026-08-31. Pla 0b/0c/0d tancat: sis fixos (F/A/B/C/D/E) mesurats abans/després, dues re-verificacions en
viu (Cadastre real, re-lectura del tall de Bell-lloc), zero regressions a la suite.*

## 2026-09-01 (nit) — Adreça i municipi: de regex a padró + conjunt tancat + veto geomètric

### Context

La sessió es va obrir expressament per **analitzar** la proposta del Josep del matí
(`docs/PROPOSTA-JOSEP-ADRECES-I-MUNICIPI-2026-09-01.md`, anotada literalment i deixada sense analitzar a posta):
interpretar l'adreça amb intel·ligència en comptes de regex, amb un JSON normalitzat i reintents amb grafies
alternatives. L'anàlisi va acabar en vuit decisions i cinc peces implementades el mateix vespre. Disseny complet:
`docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md`.

El punt de partida mesurat: la guarda de 0,85 que havíem estrenat el mateix dia descartava
`11 de Setembre` → `ONZE DE SETEMBRE` (ràtio 0,750) i deixava el camp en blanc. És a dir, el cas que el Josep
posava d'exemple el resolíem **renunciant**.

### Decisions arquitectòniques clau

**1. Qui interpreta: el skill de lectura, no una capa nova.** És l'únic lloc que veu totes les grafies de la
mateixa adreça dins d'un projecte (comanda N20, pressupost bloc OBRA, fitxa C7, plànol, correus) i ja té el
municipi de tres fonts. *Alternativa rebutjada:* una capa dedicada que rellegís text — rellegiria sense el
context que el skill ja té, i pagaríem dues passades.

**2. Alternatives sí a l'eix via/municipi, mai a l'eix portal.** És la resposta a l'objecció que el propi
document de la proposta plantejava (§2: com evitar ressuscitar el bug 18B→18A). Les variants de via i municipi
són **ortogràfiques** i designen el mateix objecte del món; les de portal són **edificis diferents amb
propietaris diferents**. `resolve_portal` segueix filtrant `(pnp, plp)` exactes. *Trade-off acceptat:* els
portals que el model llegeix no s'usen mai per consultar, ni quan són correctes.

**3. Conjunt tancat en comptes de generació lliure.** El model (o les capes deterministes) tria d'una llista
**real** de carrers del municipi i Python verifica la pertinença. Així una al·lucinació és estructuralment
impossible: un carrer inventat no és a la llista. *Alternativa rebutjada:* que el model proposi variants a
cegues i les provem — no dona el `tipus_via`, i a Bell-lloc «Onze de Setembre» és una **plaça**, no un carrer.

**4. Padró local per al municipi.** Un fitxer de dades al repo compleix el contracte de `g3_templates.py`
(«determinista, cost 0, sense xarxa»): el contracte prohibeix **xarxa**, no **dades**. *Descoberta:* el padró
INE ja hi era des del febrer i el seu `ine_code` **és** la parella `(cp, cm)` del Cadastre — l'aparellament va
sortir 947/947 sense un sol orfe.

**5. El padró només afegeix dubte, mai en treu.** Cap confiança puja. *Per què:* `_decisions.json` dels 9 corpus
és la prova de no-regressió del projecte i pujar confiances hi mouria decisions que avui són correctes.

**6. El padró i la corroboració pel context són guardes independents, i mana la del context.** Que «X» sigui un
municipi de debò no vol dir que sigui el d'aquest projecte. *Aquesta decisió va néixer d'un error:* el primer
cablejat posava el padró primer i un PLAN_COST de Bell-lloc dins d'una carpeta de Torregrossa tornava a pujar a
0,6, tapant la contradicció. Ho va enxampar un test existent.

**7. Sense bucle de re-pregunta per a l'objecte estructurat.** `claude -p` no dona sortida estructurada (per
això A1: esquema + exemples al prompt, validació a Python). Un objecte invàlid es **descarta sencer** i la
cadena continua amb el text lliure: es perd la millora, mai s'hi guanya un error. Una degradació ja segura no
justifica una segona crida. *Alternativa rebutjada:* anar per API per tenir sortida estructurada — desfaria la
decisió de la via A del 2026-08-23.

**8. Veto geomètric pels punts de camp, i que es vegi.** La comprovació més forta disponible ja es calculava i
només s'escrivia com a nota. Formulació: cap punt dins **i** el més proper a > 10 m → el valor no s'omple.
*Trade-off:* la regla només pot **vetar**, mai **exigir** — 4 dels 8 projectes no tenen fitxer de coordenades.
*Requisit explícit del Josep:* el motiu ha de ser visible amb la distància, perquè l'Eva ja ha dit que no
considera les UTM del tot fiables i un blanc sense explicació el llegiria com un error del sistema.

### Implementació

| Fitxer | Novetat |
|---|---|
| `automation/data/municipis_padro_cadastre.json` | **nou** — 947 municipis, INE + Cadastre + `(cp, cm)` |
| `automation/municipis.py` | **nou** — `lookup()` en 3 capes, un sol guanyador, sense capa difusa |
| `automation/lectura/address_struct.py` | **nou** — validació de `street_address_struct`, `FLOOR_ORDINAL_RE` |
| `automation/lectura/cadastre_reader.py` | `resolve_via`, `_numeral_canon`, `_cached_street_list`, `_resolve_municipality`, `_resolve_street`, `PointsCheck`, `_veto_signal` |
| `automation/g3_templates.py` | `_plan_cost_municipi_confianca` |
| `automation/lectura/consolidate.py` | passa `extra_concepts` al lector del Cadastre |
| `templates/validation/review.html` | el popup `no_trobat` pinta `cell.note` |
| `.claude/commands/g3dt-llegir-projecte.md` | esquema + 3 exemples del corpus per a `street_address_struct` |

### Validació empírica

- **Tria de via, 9 casos reals: 7/9 → 9/9.** Els dos guanyats són «11 de Setembre» a Rubí (que el llindar de 500
  deixava sense recuperació) i a Castellar (on la recuperació de via B tornava `POL 011 FABRICA NOVA`).
- **Bateria negativa 10/10**: cap carrer inventat, cap empat resolt a l'atzar.
- **Padró: 947/947** aparellats, 0 orfes als dos costats. 4 crides, 2,1 s.
- **PLAN_COST, 10 fitxers reals**: `ANCILES` 0,6 → 0,5 amb el motiu escrit (Anciles és un llogaret de Benasc,
  Osca — **confirmat pel Josep**, no és un municipi); `BELL-LLOC`/`CERDANYOLA`/`VILANOVA SEGRIÀ` guanyen nota amb
  la forma oficial. La resta, igual que abans.
- **Veto**: Castellar real 5/5 dins → 1.284 m²; amb les coordenades desplaçades 500 m → blanc + motiu amb «0/5
  dins, el més llunyà a 703 m».
- **Cadena sencera sense regressió**: 1.284 m², 3/3 contigües, i sense una sola crida `ConsultaMunicipio`.

### Tests

+102 tests nous en 4 fitxers (`test_lectura_via_resolver.py` 25, `test_municipis_padro.py` 33,
`test_lectura_address_struct.py` 30, `test_lectura_points_veto.py` 14). Suite: **1897 → 1999 passed**, amb les
**mateixes 32 fallades** preexistents de sempre.

Cinc tests existents van canviar d'expectativa, tots per canvis volguts i tots documentats al lloc:
`test_cadastre_portal_signals_rejects_wrong_street_name` (missatge nou + havia començat a sortir a la xarxa en
un fitxer «0 xarxa»), els dos de `test_g3_templates.py` sobre el municipi de PLAN_COST (nota nova; l'altre va
ser qui va destapar la decisió 6), els dos stubs de `test_lectura_consolidate.py` (signatura de 3 arguments) i
`test_cadastre_portal_signals_points_note_point_outside` (la nota informativa passa a ser veto).

### Limitacions conegudes

- El padró **només cobreix Catalunya**, i el corpus ja té un projecte de fora (Anciles). Avui cau al bucle en
  línia i funciona; afegir-hi Osca seria una crida més i ~200 municipis. Decisió pendent del Josep.
- La forma oficial llarga del municipi va **a la nota**, no com a candidat competidor. És un canvi de valor i
  mereix mesura pròpia sobre els corpus.
- El llindar de 10 m del veto és un criteri de judici; cal revisar-lo amb dades de més projectes.
- Quants exemples calen al prompt perquè el skill emeti `street_address_struct` de forma estable **no s'ha
  mesurat**: avui n'hi ha tres.
- El veto no s'ha decidit si ha d'aplicar-se també a altres camps derivats de la parcel·la.

### GO/NO-GO

✅ Suite sense regressions (32 fallades, les de sempre) · ✅ mesures abans/després a cada peça · ✅ ERR = 0
preservat (cap valor nou pot venir de fora d'una llista real) · ✅ documentació al dia (disseny, STATUS,
CLAUDE.md, skill) · ⏳ mesura de qualitat dels 8 projectes, que és el següent pas.

### Següents passos

Desbloqueja la **mesura de qualitat** dels 8 projectes sobre codi ja reparat: % camps bé / % popup / % blanc /
erronis-amb-confiança (objectiu 0) / minuts per projecte, i `compare_tables_vs_eva` contra els informes signats.
Llindars pactats: OK ≥ 80 %, candidats ≤ 20 %, ERR = 0.

*Fi entrada 2026-09-01. Adreces i municipi: anàlisi, vuit decisions i cinc peces — padró offline, tria per
conjunt tancat sense llindar, objecte estructurat validat a Python i veto geomètric amb el motiu visible.*

---

## 2026-09-03 — N20 i E: el test vermell és deriva de fixture, el marc «criteris, no fórmules» es persisteix, i els retocs queden planificats (P0–P4)

### Context

Tasca 0 del handoff (`_FOR-NEW-YOU-20260902.md` §8): el test
`test_bell_lloc_bearing_idx_and_n20` (N20=34,3 vs ≈49,8), posat per davant de la mesura perquè si el càlcul
s'havia mogut, la mesura naixeria caducada. El Josep va ampliar-ho a una anàlisi completa de N20 i E
(sessió 2026-09-02 tarda → 09-03), i després va fer rellegir la família de documents de pràctica geotècnica
que la primera versió de l'anàlisi no havia trobat.

### Decisions clau

1. **El test es queda VERMELL** (Josep, 2026-09-02). **Why:** la fallada no és cap regressió de càlcul —
   és el fixture (`validation/sondeig_extracted.json`, regenerable per visió) que va moure el límit de capa
   d'1,6 a 1,0 m entre lectures de confiança 0,6. Re-fixar 49,8→34,3 re-ancoraria una segona lectura
   igualment infundada; ancorar-lo bé depèn de la regla N20 global/ferm (P4), que necessita Eva o decisió.
   Alternativa rebutjada: congelar geometria ara — prematura mentre P4 sigui obert.
2. **El forat de l'E només s'apunta** (Josep): l'apunt és `ANALISI-CALCUL-N20-E-2026-09-02.md` §5. La mesura
   dels 8 el destaparà a tots els projectes alhora — millor base per decidir que un cas.
3. **Regla d'or persistida a 4 capes** (Josep: «com podem fer per no oblidar aquests criteris?»): CLAUDE.md
   (punter — la capa que va fallar: la v1 de l'anàlisi es va escriure sense trobar els documents, que eren
   a la branca des de sempre), `METODOLOGIA-EVA.md` §0 (el marc sencer, al doc que la instrucció existent
   ja mana consultar), memòria `project_geotech_criteria_not_formulas` (sobreviu worktrees), i aquesta
   entrada. **Why 4 capes:** el que va fallar era la descobribilitat, no l'emmagatzematge.
4. **Retocs de codi: planificats, cap d'implementat, i DESPRÉS de la mesura**
   (`PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md`): P0 columna N=SPT N30; P1 cel·la Nb sense /0,83 (OK Josep
   pendent); P2 estrat = on recolza la sabata (arregla Rubí-vestit-de-roca; P2b necessita fondària real);
   P3 E per criteris i candidats; P4 regla N20 + re-ancorar test. **Why després:** el diagnòstic confirma
   que el càlcul no s'ha mogut → la línia base és vàlida; P0–P2 canvien cel·les que el comparador puntua
   (`feedback_measure_baseline_before_coding`).

### Validació empírica

- Mateix codi, fixture antic (d70030c) → **49,8**; fixture actual → **34,3**: la fórmula no s'ha mogut.
- Geometria real (1 capa 0–1,8 m, annex + informe signats) → codi retorna **25,1** ≈ Nb signat «25-R».
- φ vs signat 38°: 34,3→37,0° (−1,0°); 49,8→40,6° (+2,6°, costat insegur). Qa: 3,00 als dos (topall).
- Nb signat vs N20: Castellar 17≈18,7 global; Bell-lloc 25≈25,1 global (exacte); Rubí 47≈43,3 ferm — cap
  regla única (judici), però el N20 CRU guanya el N20/0,83 del display als 3 casos.
- E vs 9 nivells signats: fluixos −84/−91 % (Eva 50–90, fins per sobre del rang CTE; nosaltres 8); mitjos
  +4/+14 %; carbonatades −28 %; roca fixa 500 vs «>350…>800». La cadena Qa: 6/7 MATCH (ja se sabia; ara re-lligat).
- Rubí amb col·lapse a 1 nivell: roca (φ35/E500/γ2,2/c1,0) vs signat granular (39/450/2,0/0,05) — 6 cel·les
  d'un sol cop d'origen (descripció de la capa més profunda).

### Implementació (només documentació)

`ANALISI-CALCUL-N20-E-2026-09-02.md` (v2, reescrit amb el marc), `PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md`
(nou), `METODOLOGIA-EVA.md` §0 (nou), CLAUDE.md § Metodologia (taula de família), memòria nova + MEMORY.md,
STATUS.md. Cap línia de codi de càlcul ni de test tocada.

### Limitacions conegudes

- La lectura «Nb d'Eva = N20 cru» té 3/3 d'evidència però cap confirmació d'Eva; P1 no s'executa sense OK.
- La fila «Alcoletge 1: graves carbonatades» de `CRITERIS-CALCUL-EVA.md` §5 no quadra amb `_eva_truth`
  (lapsus probable d'aquell doc); mana `_eva_truth`.
- Anciles/Alcoletge/Linyola/Vilanova sense fixtures locals: les seves files d'E són a nivell de fórmula
  (input = Nb signat reconvertit), no de pipeline sencer.

### GO/NO-GO

✅ diagnòstic tasca 0 tancat (càlcul intacte → la mesura no neix caducada) · ✅ marc persistit a 4 capes ·
✅ pla P0–P4 escrit i seqüenciat · ⏳ mesura dels 8 (següent) · ⏳ OK Josep a P1 · ⏳ preguntes E + N20 a Eva.

### Següents passos

La MESURA dels 8 projectes (tasca 1 del handoff, criteris primer), llegida amb l'anàlisi al costat: les
cel·les Nb, N, E (i γ/c/φ a Rubí) tenen causes de MISMATCH conegudes. Després, P0 → P1 → P2a per ordre.

*Fi entrada 2026-09-03. N20: càlcul sa, entrada fràgil; E: criteri per modelar; el marc «criteris, no
fórmules» ja no depèn de la memòria de ningú.*

## 2026-09-04 — Mesura dels 8 (línia base pre-P0-P4) tancada: 4 ERR (3 de consolidador), 64 % OK, la confiança es perd després de llegir

### Context
Tasca 1 del handoff del 09-02/03: mesurar la lectura de nivell A i les 11 taules als 8 projectes amb el codi intacte,
criteris escrits abans (`docs/wizard-headless/mesures/CRITERIS-MESURA-2026-09-03.md`), un projecte per run, veritat =
informe signat. Executada 2026-09-03 (Castellar) i 2026-09-04 (els 7 restants). Resultats i diagnòstics per projecte a
`docs/wizard-headless/mesures/runs/2026-09-03-mesura-8/` (`{slug}/_NOTES.md`, `_DIAGNOSTIC.md`, `_DIAGNOSTICS-INDEX.md`,
`_AGREGAT-8.md`).

### Decisions clau
1. **Els veredictes del comparador es contrasten cel·la a cel·la amb el signat abans de comptar-los.** Why: 18 falsos
   ERR/ALERTA del comparador (adreces amb CP/urbanització, ids duplicats «SPT-1», ca/es, columnes de fixture) haurien
   inflat el titular; i l'or de lectura és de vegades més cautelós que el signat (esborranys) o menys anotat
   (`fora_carpeta`). Alternativa rebutjada: agregat mecànic ara — s'ajorna fins a arreglar `compare_consolida.py`.
2. **Vilanova entra al titular** (esmena datada als criteris): el Josep troba el `.docx` signat original (castellà);
   `_eva_truth/vilanova.json` transcrit del cos. 7 comparables, no 6. Why: l'stub anterior era circular (annexos).
3. **Runs desacoblats de la sessió** (`setsid nohup` + Monitor) i **represa per cache md5** quan un run mor (Bell-lloc,
   Vilanova): lectura íntegra, temps marcat com a compost. Why: dos talls de connexió en dos dies; un run del harness
   mor amb la sessió.
4. **Cap fix durant la mesura.** Tots els defectes trobats (D2-D6, R6, I1, S1, T1-T2) queden a la fila 0b del PLA,
   pendents de prioritzar. Why: la línia base només val si el codi no es mou.

### Validació empírica (7 comparables, sobre el signat)
- Escalars (147 cel·les): **94 OK (64 %) / 50 CAND (34 %) / 1 blanc / 2 ERR**. Taules (199): **133 OK (67 %) / 33 CAND /
  31 blancs / 2 ERR**. Llindars pactats (OK ≥ 80 %, CAND ≤ 20 %, ERR 0): **cap complert.**
- **ERR 4:** Rubí cota P-2 (F1, annex d'Eva ≠ informe); Linyola `field_date` (D2, bug de clustering de dates); Vilanova
  `municipality` (D3, forma visible per `len(v)` en lloc del padró) i `nivell_freatic` P-3 (R6, columna buida A tapa
  evidència positiva no-A). **Cap ERR de lectura per document: els 4 són decisions del consolidador o de la font.**
- On es perd la confiança: R5 font única 19 cel·les, R1 formes de la mateixa entitat 15 (abreviatures G3 a
  `building_type` 8/8), R4 CTE 9, R2 concepte veí 6, F1 fonts d'Eva inconsistents 7 (SPT P-1/P-3 creuats a Vilanova).
- Cobertura: I1 (Anciles, `PDF_V0/` exclosa → 9 cotes en blanc); alternativa provada: `.FH11` via libfreehand.
- Temps net 26-43 min/projecte (Linyola 42,9 vs base 41,9: +2 %); cost API 121,75 USD als 8.

### Limitacions conegudes
Agregat mecànic pendent del comparador; Tulipa sense veritat (multi-casa no modelat, S1); 2 temps compostos;
`eva_reference_values` de Vilanova/Anciles en castellà (extractor desalineat en alguns camps); or amb 3 `fora_carpeta`
absents; les preguntes a Eva (E, N20, T pressupost, persona/despatx, SPT Vilanova) no enviades.

### GO/NO-GO
- ✅ Línia base vàlida i reproduïble (criteris, driver versionat, runs desacoblats, diagnòstics per projecte).
- ✅ Diagnòstic complet: cada cel·la no-OK té causa i codi; 3 dels 4 ERR comparteixen patró («desempat mecànic contra
  informació que `_decisions.json` ja té»).
- ⏳ Llindars: no assolits amb codi intacte. Estimació sense tocar criteris d'Eva: R1+R3+D3 → ~75 % OK; +R5+R2 → ~85 %.
- ⏳ Fila 0b del PLA (fixes) i comparador: pendent de prioritzar (Josep).

### Següents passos
Prioritzar 0b; arreglar comparador i regenerar l'agregat mecànic; corregir l'or (`fora_carpeta`); paquet de preguntes
a Eva; després, P0/P2a → M341 (pla). Vegeu `PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md` §Ordre.

*Fi entrada 2026-09-04. Mesura dels 8: el sistema llegeix bé i decideix malament; els 4 ERR i les 50 CAND tenen nom.*

## 2026-09-05 — Fila 0b, primer paquet: comparador v4 (C) + D2 dates, D3 padró, R3 guard «1 de N» — ERR de codi 3 → 0 sense re-run

### Context
Decisió del Josep (2026-09-05, després de llegir el handoff del 09-04 i la traducció dels codis): «endavant amb C, D2, D3,
R3». Els tres bugs de consolidador tenien línia de codi al diagnòstic (`_DIAGNOSTICS-INDEX.md`, `linyola/_DIAGNOSTIC.md`
§D2, `vilanova/_DIAGNOSTIC.md` §D3, `bell-lloc/_DIAGNOSTIC-INFRACONFIANCA.md` fila 7); el comparador tenia 18 falsos
veredictes catalogats. Ordre executat: línia base (comparador intacte regenera els 14 `_compare_*.txt` idèntics; suite
31 vermells / 2001 verds) → comparador → bugs, un test cadascun → reconsolidació dels 7 → agregat mecànic.

### Decisions arquitectòniques clau
1. **El comparador no ignora partícules.** La primera versió del v4 igualava «Vilanova del Segrià» amb «Vilanova de
   Segrià» (regla «sense partícules» pensada per a «plànol en el ICGC» / «plànol de l'ICGC») i feia desaparèixer el D3 del
   propi comparador. Why: l'instrument no pot perdonar l'error que ha de mesurar. El cas de Rubí es resol per la via
   numèrica (nota darrere de coma = anotació), no per la textual. Alternativa rebutjada: mantenir-la i afegir excepcions
   per camp.
2. **Els candidats compartits d'un camp niuat es reparteixen només a `cte`** (C→`cte_edificacio`, T→`cte_sol`, regex).
   Repartir també els del `lab` pel valor de la subclau creava una CAUTELA nova a Anciles (`lab_sample_id`: «MA (S-2)
   2,8-3,0» s'assignava a `lab_location` per contenció de «S-2»). Why: les formes del `lab` són lectures del mateix bloc
   del document; la contenció ≥ 3 caràcters després de treure anotacions ja resol «TPS (coneixement previ)».
3. **D2 en tres peces, cap de sola.** (a) Una data sense dia no és aresta del union-find: s'adjunta després al cluster
   amb dia més fort compatible, o fa cluster propi. (b) Representant d'un cluster de dates = clau amb dia del senyal de
   més autoritat (`is_a`, `confidence`), mai `len(str(k))`. (c) La ISO es calcula de la clau del PROPI candidat 0 i només
   si és compatible amb la del cluster: un candidat «Octubre 2025» no es reescriu amb un dia que la seva cita no diu.
   També: dins d'un cluster, les formes amb dia van abans que les sense dia. Why: amb només (a), «Octubre 2025» A i un
   dia no-A haurien deixat el candidat 0 sense dia; amb només (b), la cita continuaria dient una cosa i el valor una
   altra.
4. **D3 com a post-procés, no dins de `decide`.** `_canonical_municipality(cell)` després de decidir: si TOTES les formes
   candidates resolen al mateix `ine_code` del padró, valor i candidat 0 = `name_ine`, la forma del document queda a la
   cita (mateix patró que la ISO). Si alguna no resol (Anciles) o resolen a municipis diferents, no es toca res. Why:
   `decide` és genèric per camp; el padró és coneixement de `municipality`, com `_promote_entre_carrers` ho és
   d'`street_address`.
5. **R3: límit de paraula i N ≥ 2**, «1 de / del / dels [les|els] N»; «unitat» es manté. Why: «P1 de 86 m2» no és «una
   unitat de N»; «1 dels 3 habitatges» sí. (Primera versió amb `dels?` només casava «del/dels»: el test ho ha caçat.)
6. **Agregador propi (`agrega_mesura.py`)** en lloc d'adaptar `ledger.py`. Why: el llibre espera un run per carpeta
   amb `meta.json`; la mesura són 8 subcarpetes d'un run. Mapa explícit veredicte → columna; ALERTA a part.
7. **Reconsolidació en lloc de re-run.** El consolidador és determinista sobre les lectures cachejades del run; la
   passada LLM existent (`_consolida_only.json`) es fusiona amb `merge_only_fields` sobre els mateixos conflictes.
   Why: mesura l'efecte dels tres fixes a cost 0 i sense soroll de lector; un re-run de Linyola i Vilanova (~30 USD,
   ~75 min) només afegiria variància de lectura, no informació sobre el consolidador. Els artefactes queden a
   `{slug}/_reconsolida-2026-09-05/` sense tocar els `_decisions.json` originals de la mesura.

### Implementació
- `docs/wizard-headless/fase0-acceptacio/compare_consolida.py` v4 (+~90 LOC): `parse_address` (via = tokens abans del
  primer portal, «C.», tipus opcional, CP no és portal, sta/st), `parse_numbers` (unitat enganxada, nota darrere de
  coma), `close` (contenció post-anotacions ≥ 3, persones per conjunt de noms, `nivell_freatic` primera fondària),
  `norm_floors` (porxo, «1 (planta baixa)» = PB), `building_tokens` (es→ca, `unitat` fora), `subkey_candidates`,
  `verdict` («or sense valor»), `row_key` spt per `punt`, `NOMES-OR` a `compare_taules`.
- `automation/lectura/consolidate.py` (+~70 LOC): `_dayless`, `cluster_signals` en dues passades, `ordered_forms`,
  `decide` (ISO), `_UNIT_OF_N_RE` + guard `num_floors`, `_canonical_municipality` + crida; import de `municipis.lookup`.
- `docs/wizard-headless/mesures/agrega_mesura.py` (nou, ~80 LOC). Cap dependència nova.
- Docs: `_AGREGAT-8.md` §Agregat mecànic, `_DIAGNOSTICS-INDEX.md` §Estat dels fixes, PLA fila 0b, STATUS, sessió.

### Validació empírica
- Comparador v4 sobre els `_decisions.json` ORIGINALS (aïlla C): escalars 86 → 90 OK, ALERTA 11 → 8, ERR 3 → 2; taules
  127 → 136 OK, CAND 26 → 21, ERR 4 → 0. Les 18 cel·les que canvien són exactament les catalogades com a C; cap altra
  línia es mou (diff complet a la sessió).
- Consolidador nou (reconsolidació dels 7): **3 cel·les escalars canvien, 0 de taula**: Linyola `field_date`
  2025-10-10 → 2025-10-01 (segur), Vilanova `municipality` → «Vilanova de Segrià» (segur), Bell-lloc `num_floors`
  candidats → segur «PB+PP». Escalars: **93 OK / 45 CAND / 8 ALERTA / 1 blanc / 0 ERR**; taules 136 / 21 / 9 / 31 / 0.
- Contra el titular del 09-04 (94/50/1/2 sobre el signat): amb G (3 `fora_carpeta`) l'agregat mecànic seria 96/50/1/0.
  Els 2 ERR de veritat que queden viuen a la columna ALERTA de taules (Rubí P-2 F1, Vilanova P-3 R6).

### Tests
- Comparador: +30 casos a `CLOSE_CASES` (parells reals dels `_compare_*.txt`), +5 assercions a `test_parsers`,
  +5 tests (subclaus `cte`, Castellar `cte_sol`, alineació spt per punt, integracions Vilanova i Alcoletge sobre el run
  versionat). `test_row_key_other_blocks` actualitzat (spt per punt).
- Consolidador: +6 tests (`test_D2_*` ×3, `test_R3_*`, `test_D3_*` ×2). Els dos mòduls: 270 verds.
- Suite sencera: vegeu la sessió (abans 31 vermells / 2001 verds; després, mateixos noms vermells esperats: SmartScan
  sense dades locals + `test_bell_lloc_bearing_idx_and_n20` a posta).

### Latència / cost
Cap crida LLM nova: comparador i reconsolidació són locals (HTTP cachejat a `G3DT_CACHE_DIR`). 0 USD.

### Limitacions conegudes
- El comparador continua mesurant contra l'or de lectura, no contra el signat: les cel·les on prod és més confiat que
  l'or surten ALERTA i s'han de llegir a mà (2 de 9 són ERR reals a taules). L'or necessita G (`fora_carpeta`).
- CAND de taules: or i prod tots dos `candidats` i solapant = OK per al comparador; el recompte manual del 09-04 ho
  comptava CAND quan el signat té valor únic. Dues preguntes diferents; cap de les dues és falsa.
- D3 no toca les formes de `street_address` (R1) ni les de `client_name`; només `municipality`.
- Vilanova `litologia[0]` queda CAUTELA per «llimosa» / «limosa» (ca/es de litologia): no s'ha afegit un diccionari de
  litologies al comparador (fora de C).
- `classify_table` castellà a `compare_tables_vs_eva.py` (harness d'informe, no de lectura): no tocat.

### GO/NO-GO
- ✅ 18 falsos veredictes fora, cap de nou (6 cel·les de Vilanova/Anciles contrastades una per una).
- ✅ ERR de codi 3 → 0 a la reconsolidació; 3 cel·les canvien, totes cap a la veritat.
- ✅ Cada fix amb test; els dos mòduls verds; agregat reproduïble amb un script.
- ⏳ G, R6, I1, R1, D5, D4/D6, T1/T2, S1: sense decisió.
- ⏳ Re-run real de Linyola/Vilanova: no cal per validar el consolidador; només si es vol soroll de lector.

### Següents passos
Prioritzar la resta de 0b (proposta: G → R6 → I1 → R1). Paquet de preguntes a Eva sense enviar. Després, seqüència
pactada del 09-03 (R → P0/P1/P2a → M341).

*Fi entrada 2026-09-05. Comparador v4 + D2/D3/R3: el sistema ja no decideix contra el que sap; els dos ERR que queden són de font (Rubí) i de política (R6).*

## 2026-09-05 (tarda) — Fila 0b, resta: G, R6, I1, R1, D5, D4, D6, T1, T2 (S1 en disseny) — escalars 86 → 104 OK sobre l'or, ERR de codi 0

### Context
Josep (2026-09-05, després del commit `386a8a5`): «commit i push; seguim amb la resta de la fila 0b, amb la teva proposta
d'ordre tal qual» (G → R6 → I1 → R1, després D5, D4/D6, T1/T2, S1). Mateix mètode que al matí: cada fix amb test i
mesurat reconsolidant els 7 comparables a cost 0 (`mesures/reconsolida_mesura.py`, nou, versionat), llistant TOTES les
cel·les que canvien. Excepció: I1 canvia l'inventari (documents nous) → run parcial real d'Anciles (5 PDF).

### Decisions arquitectòniques clau
1. **G a l'or, no al comparador.** `fora_carpeta` per a `superficie_parcela` de Rubí (951), Alcoletge (1167) i Vilanova
   (406), amb font Cadastre i nota «signat: …». Why: el valor és correcte i mesurat fora dels documents; el comparador ja
   té el veredicte FORA per a aquest cas (v3). No s'ha tocat `referencia_catastral` de Rubí/Vilanova: no consta que el
   signat la imprimeixi (zero fabrication).
2. **R6 com a post-decisió de cel·la, no com a canvi de `decide(table_cell=True)`.** `_nf_positive_over_absence`: si el
   candidat 1 és l'absència («No detectat», `absent_literal`) i hi ha cap senyal positiu, candidats amb el positiu primer
   (tall > full de camp > resta per confiança) i «No detectat» després. Why: la regla «només els A contradiuen» de les
   taules és bona en general (Pas 3b); el que és específic del nivell freàtic és que una columna buida és absència
   d'anotació, no una mesura. Alternativa rebutjada: fer que els positius no-A siguin bloquejadors genèrics (mouria
   totes les cel·les de taula). Mesura: 1 sola cel·la canvia als 7 (Vilanova P-3).
3. **I1: la V0 només si no hi ha `PDF/` vigent**, i marcada (`"version": "V0"` a l'inventari). Why: a Bell-lloc/Linyola
   la V0 és versió anterior de debò; a Anciles és l'única còpia llegible (els vigents són `.FH11`). També: variants en
   castellà dels annexos (`ANEJOS/`, `_sondeos.pdf`, `corte de correlación.pdf`) per al `doc_type_hint` (prioritat de
   cua; el tipus real el decideix el lector). Vilanova ja llegia `PDF/ANEJOS/*_DPSH.pdf` com a «altre» per això.
4. **R1: equivalències PER CAMP dins de `value_key`, i clustering sense ponts.** (a) `building_type` → conjunt de
   paraules (`btset`: abreviatures G3, es→ca, municipi final fora via padró, xifres i mots buits fora) i compatibilitat
   per inclusió; (b) `street_address` → `("addr", via, {portals})` via `cadastre_reader.portals_from_address` (mateixa
   via i mateixos portals = mateixa clau; sense portal = lectura parcial, compatible només si la via coincideix);
   (c) `client_name`/`architect_company`/`lab_testing_company` → sufix de forma jurídica fora; (d) `lab_location` →
   clau de punt (`_point_key`) i forma visible canònica «P-3». Why «sense ponts»: un subconjunt (`HAB UNIF`) o una
   lectura sense portal («C/ DE LA MIRANDA») és compatible amb DUES alternatives reals («aïllat»/«entre mitgeres»;
   portal 39/41) i el union-find les fusionaria; s'apliquen com les dates sense dia del D2 (`_attach_only`: s'adjunten
   al cluster compatible més fort, la clau del cluster es manté com la més completa). Alternativa rebutjada:
   equivalències al comparador (mesurarien millor sense decidir millor). **Persona/despatx NO es toca** (pregunta a Eva).
5. **R1 té una regla que NO aplica als conjunts:** «formes diferents entre fonts A → candidats» es manté per a
   adreces (amb/sense portal) però s'exceptua per a `btset`: un subconjunt d'un tipus d'edifici és el mateix tipus
   menys un adjectiu (memòria `feedback_building_type_close_match`).
6. **D5: el CTE es classifica per edifici.** Adossat/plurifamiliar → superfície TOTAL de l'encàrrec (el màxim dels
   candidats de la taula; si cap total, N unitats × tipologia); aïllat → per unitat (com fins ara). Why: és el que fan
   l'or i el signat als dos casos que tenim (Anciles 7 adossats 1.264 m² → C-1; Castellar 3 aïllats de 120 m² → C0).
   Continua sent candidats (R4).
7. **T2 sense heurística de «multi-expedient».** La primera versió ometia la passada LLM quan hi havia conflicte a
   `fields.expedient`; a Tulipa els dos valors comparteixen el número (`3001706` / `3001706_CASA 1`) i el test
   sintètic de conflicte també usa `expedient`. Substituït per: només `fields.*` (cap `tables.*` s'ha aplicat mai als
   7 runs) + topall de conflictes. **Observació que demana decisió:** la passada costa 200-290 s i 14-23 torns fins i
   tot amb un sol conflicte.
8. **T1 honest:** el CLI no escriu res a stdout ni stderr fins al final (`--output-format json`; comprovat en viu al
   run d'Anciles: logs de 0 bytes durant 6 min); una penjada no es pot distingir d'una lectura lenta. Es fa l'únic que
   es pot fer sense canviar de format: topall propi per als fulls de camp (900 s) i `timeout_s` a la telemetria.

### Implementació
- `automation/lectura/consolidate.py` (+~200 LOC): `_nf_positive_over_absence`, `_attach_only`, `_more_complete`,
  `_building_type_tokens`, `_address_key`, `_cte_surface`, constants R1 (`_BT_MAP`, `_BT_STOP`, `_VIA_ABBR`,
  `_LEGAL_SUFFIX_*`), `value_key`/`keys_compatible`/`cluster_signals`/`decide` ampliats; `derived_field_signals(key,
  decided, sc)` (signatura nova).
- `automation/lectura/inventory.py`: `has_current_pdf_dir`, `_V0_DIRS`, `version: V0`, regexos ES.
- `automation/lectura/runner.py`: `LecturaResult.docs_failed`, `assign_doc_names`, `doc_timeout`, `llm_conflict_paths`,
  config `timeout_slow`/`llm_max_conflicts`, `os.replace` del JSON trobat al nom esperat.
- `docs/golden-read/{3 projectes}/_decisions.json`: `fora_carpeta`.
- `docs/wizard-headless/mesures/reconsolida_mesura.py` (nou). Cap dependència nova.

### Validació empírica (reconsolidació dels 7, cost 0; agregat mecànic sobre l'or)
- Escalars: 93 (matí) → **104 OK / 37 CAND / 5 ALERTA / 1 blanc / 0 ERR** (71 %). Cel·les mogudes: G 3, R1 7, D5 1;
  totes cap a l'or/signat; 0 regressions. Taules: 136 → **137 OK / 21 / 8 ALERTA / 31 / 0 ERR**; R6 mou 1 cel·la.
- Sobre el signat: escalars 104 OK (71 %) / 42 CAND (29 %) / 1 blanc / **0 ERR**; taules: **1 ERR real** (Rubí cota
  P-2, font d'Eva). Dels 4 ERR del 09-04 en queda 1, de font.
- Runner: 202 tests verds als tres mòduls tocats (runner 43, consolidador 135, inventari 24). Suite sencera: vegeu la
  sessió.
- **I1 — resultat** (run parcial d'Anciles, 5 PDF de `PDF_V0`, 20,3 min, 5,87 USD, un timeout de 600 s a `sondeos.pdf`
  = T1 en viu): primera passada amb la V0 com a font A → 30 cel·les canvien i **1 ERR nou** (`mostra_del_nivell` del
  nivell 1 segur `True`: a la V0 les graves eren NIVEL 1; al signat són el 2n nivell). Regla afegida: **un document V0
  proposa i corrobora, mai és autoritat ni contradiu** (`_is_v0_source`, `is_a=False`, confiança < 0,4, nota). Resultat:
  21 cel·les canvien, **0 ERR**: les 9 cotes en blanc surten com a candidats amb el valor del signat primer, la mostra del
  nivell 1 queda en ALERTA (dubte honest). Els 7 restants: 0 cel·les. Agregat amb I1: escalars 105/37/5/0/0, taules
  137/37/9/20/0 (Anciles blancs 14 → 3). Vegeu `_AGREGAT-8.md` §I1.

### Tests
+2 D5, +1 R6, +5 R1 (consolidador); +3 I1 (inventari); +4 (D6 ×2, T1, T2) i D4 dins del test de timeout (runner).

### Latència / cost
Reconsolidacions: 0 USD. Run parcial I1 d'Anciles: 5 lectures Claude (sonnet, xhigh, c2): 20,3 min, 5,87 USD (1,28 +
1,07 + 0,63 + 1,48 + 1,40; el timeout del 1r intent de `sondeos.pdf` no factura).

### Limitacions conegudes
- R1 no cobreix persona/despatx (`architect_name`, Linyola: el signat escriu el despatx) ni les grafies de
  `client_name` que no són forma jurídica; R5/R4/R2 continuen sent la massa del CAND (37).
- El comparador continua contra l'or: els ALERTA (5 + 8) s'han llegit a mà una vegada més.
- T1 no detecta penjades; T2 no elimina el cost fix de la passada LLM.
- S1 no implementat (disseny a `_AGREGAT-8.md`).

### GO/NO-GO
- ✅ Fila 0b tancada (S1 en disseny). ✅ 0 ERR de codi (I1 inclòs, amb la regla V0). ✅ 0 regressions mesurades.
  ⏳ OK 71 % (< 80), CAND 29 % (> 20): el que queda és R5/R4/R2/F1 i les preguntes a Eva.

### Següents passos
Paquet de preguntes a Eva (R4, persona/despatx, SPT Vilanova, cota Rubí); decidir si la passada LLM es manté (T2);
R5 («el projecte de l'arquitecte mana») i R2 (z GPS, msnm→fondària) són els següents guanys sense tocar criteris; S1
quan hi hagi un segon multi-casa. Després, la seqüència pactada (R → P0/P1/P2a → M341).

*Fi entrada 2026-09-05 (tarda). Fila 0b: del «decideix malament» al «decideix bé i dubta del que ha de dubtar».*

## 2026-09-05 (nit) — Bloc 1.1, R5 «font única del proveïdor»: autoritat de camp al consolidador — escalars 104 → 112 OK sobre l'or, CAND 29 % → 20 %

### Context
Handoff del vespre (`_FOR-NEW-YOU-20260905.md` §Decisions del Josep al tancament): bloc 1 = lectura i decisió, peça 1.1 =
**R5** (19 cel·les en CAND: el projecte de l'arquitecte o el correu del tècnic declaren la RC, la superfície o les plantes i
cap lector sol arriba a 0,8; a Bell-lloc 5 documents diuen «1 nivell» i cap passa de 0,75; el formulari p.5 llegit a 0,75
en una foto). Mateix mètode del dia: línia base reproduïda ABANS de tocar codi (agregat r2 = 104/37/5/1/0), test per
regla, reconsolidació dels 7 a cost 0 (`mesures/reconsolida_mesura.py _reconsolida-2026-09-05-r5 _reconsolida-2026-09-05-r2`)
i llista de TOTES les cel·les que canvien.

### Decisions arquitectòniques clau
1. **Autoritat DE CAMP (`_FIELD_AUTHORITY`), no un llindar d'A més baix.** Per a cada camp, el skill (Pas 3) diu quin TIPUS de
   document el declara: RC / superfície / plantes → correu d'encàrrec, projecte de l'arquitecte, caixetí del plànol (l'Eva
   ho copia «segons informació aportada»); nivells → annex de sondeig + tall (dues síntesis de l'Eva); client → formulari
   p.5 del pressupost signat. Un senyal d'aquest tipus, que el propi lector ha llistat a `context.authority_for`, amb
   confiança ≥ 0,5 i sense cap contradicció, fa `segur`; els nivells demanen DOS tipus coincidents (tall + sondeig). Why:
   la confiança del lector és humilitat per document («creuar amb els altres»), no l'autoritat del camp; qui veu tot el
   corpus és el consolidador. Alternatives rebutjades: (a) abaixar `A_CONF_CLAUDE` a 0,6 → tots els correus i caixetins
   de `client_name` a 0,6-0,7 serien A i Linyola (4 correus + 2 plànols amb dues persones) passaria de segur a conflicte
   A-vs-A; (b) regla genèrica «`authority_for` + conf ≥ 0,5 → A a qualsevol camp» → mateix problema (Anciles: promotor
   d'IV_PLANOS 0,5 contra el p.5); (c) «≥ 4 documents de ≥ 3 tipus amb conf ≥ 0,5» (proposta del diagnòstic de Bell-lloc)
   → a Bell-lloc només 3 documents passen de 0,5, i comptar documents premia el mateix dibuix imprès dues vegades
   (`tall.pdf` + `PDF/ANNEXES/…tall`). Es compta per TIPUS.
2. **Llindar 0,5 i no 0,3: el dubte del lector es respecta.** Castellar `num_floors` 0,4 («pot no representar les 3 unitats
   finals»), Vilanova 0,3-0,35 («informació verbal de segona mà»), Rubí 0,4 («derivat estructuralment» d'una foto de
   catàleg, i l'or el vol candidats). Amb 0,3, Rubí pujaria a segur contra l'or; amb 0,5, Castellar i Vilanova queden CAND
   (2 cel·les que l'or té segur «amb nota»). Trade-off acceptat: un `segur` fals costa un informe; un CAND, dos segons.
3. **La RC completa declarada pel proveïdor és segura; el skill s'alinea amb l'or.** El skill deia «impresa al projecte →
   candidats, mai segur sense consulta del Cadastre»; l'or (Linyola «el projecte mana», Alcoletge i Anciles «regla
   Alcoletge») la dona segura, i és el que l'Eva copia. S'edita el skill (Pas 3 + capçalera v1.7) sense cost: la cache de
   lectures va per md5 del document, no pel text del skill. Gate de forma: `_RC_RE` (urbana 7+2+4+1, rústica 5+1+8,
   càrrec opcional): «Polígon 6, Parcel·la 105-B» (Rubí) i «98417» (Alcoletge) queden fora encara que vinguin d'una font A.
   El guard `parcela` compta PARCEL·LES (14 caràcters) i no cadenes: el fragment «61845» d'un mapa (Anciles) ja no fa de
   segona parcel·la; «…N+…N+…N» del Cadastre (Castellar) continua comptant com a tres.
4. **Client: només el formulari p.5, identificat per la font.** `_P5_FORM_RE` («han de constar | factura») sobre `font`;
   el bloc CLIENT de la p.1 és el sol·licitant (Pas 3) i no declara. La forma del document que declara va primera dins
   del clúster (`ordered_forms`, mateix criteri que «representant per autoritat» del D2): Anciles mostra «Maria Alba
   Barrau Castán» i no «… 616523792» (L3 continua pendent, però ja no és el valor visible).
5. **Cap conflicte A-vs-A nou.** L'autoritat de camp és una propietat del clúster dins de `decide`, no un `is_a` del
   senyal: una declaració a 0,6 no dispara la passada LLM (Bell-lloc: dues RC al mateix correu → candidats i
   `conflicts == []`). Conflictes per projecte idèntics a r2. Why: T2 (200-290 s per passada) no es pot pagar per una
   regla de confiança.
6. **Els documents V0 no declaren mai** (`declares=False`), coherent amb I1 («proposa, mai autoritat»).

### Implementació
- `automation/lectura/consolidate.py` (+~75 LOC): `FIELD_AUTHORITY_CONF`, `_FIELD_AUTHORITY`, `_P5_FORM_RE`, `_RC_RE`;
  `Signal.declares`; `_declares_field`, `_field_authority_types`, `_rc_parcels`; `decide` (`field_auth`, raó «autoritat
  de camp (R5)»); `_distinct_candidates.ordered_forms`; `collect_field_signals` (`context.authority_for` → `declares`);
  guards `cadastre` i `parcela`. Cap dependència nova.
- `.claude/commands/g3dt-llegir-projecte.md`: Pas 3 `referencia_catastral` + línia v1.7 (cap canvi de lectura).
- `tests/test_lectura_consolidate.py`: `_doc(authority_for=)`, helper `_decl`, 7 tests `test_R5_*`.
- Artefactes: `runs/2026-09-03-mesura-8/{slug}/_reconsolida-2026-09-05-r5/`.

### Validació empírica (reconsolidació dels 7, cost 0; comparador v4 sobre l'or)
- **8 cel·les canvien, totes de candidats a segur amb el valor de l'or; cap altra cel·la, escalar ni de taula, es mou;
  0 regressions.** Bell-lloc `num_soil_levels` 1 (tall + annex sondeig); Rubí `client_name` (formulari p.5, foto WhatsApp
  0,75); Linyola RC i superfície (projecte 0,6 / 0,75); Alcoletge RC (correu 0,75; és la mateixa que el Cadastre calcula
  per al portal 7); Anciles `client_name` (p.5 0,75, forma sense telèfon), RC (correu 0,85, ja A: el guard la bloquejava)
  i superfície (IV_PLANOS 0,8, ja A: el fragment «61845» comptava com a segona parcel·la).
- Escalars: **104 → 112 OK (76 %) / 37 → 29 CAND (20 %) / 5 ALERTA / 1 blanc / 0 ERR**. Taules 137 / 21 / 8 / 31 / 0
  (idèntic). Conflictes A-vs-A per projecte: idèntics a r2.
- Contrast amb el signat (notes per projecte): Linyola superfície 571 («segons informació aportada»), Anciles client
  «SRA. ALBA MARIA BARRAU CASTÁN» i Bell-lloc 1 nivell coincideixen; les altres 5 són el valor de l'or (el signat no s'ha
  tornat a mirar per a les RC ni per a Rubí).
- Llindars: ERR 0 ✅ · **CAND 20 % ✅ (primer cop)** · OK 76 % ⏳ (80).
- R5 restant (11 de 19): Castellar i Vilanova `num_floors` (decisió 2) i les 9 cel·les de taula d'Anciles (font única
  manuscrita + V0 no-autoritat per I1: CAND honest; en producció l'Eva dibuixa l'annex abans d'obrir el wizard).

### Tests
+7 `test_R5_*`; consolidador 137 → 144 verds (el test sintètic conserva `referencia_catastral` en candidats: 0,6 sense
`authority_for`). Suite sencera: vegeu la sessió.

### Latència / cost
0 USD: reconsolidació i comparador locals, cap lectura nova.

### Limitacions conegudes
- `authority_for` depèn del lector: si no llista el camp, no hi ha autoritat de camp encara que el tipus de document sigui
  el bo (per disseny: el lector és qui veu si és declaració o inferència).
- D1 (creuar la RC declarada amb la que el Cadastre calcula per portal) no fet: seria corroboració, no canvia cap estat.
- L3 (telèfon enganxat a la fitxa C6) segueix pendent: ara és candidat 2, no el valor.
- Els 2 `num_floors` a 0,3-0,4 i les 9 cel·les de taula d'Anciles queden CAND a posta.

### GO/NO-GO
- ✅ 8 cel·les cap a l'or, 0 regressions, test per regla, conflictes idèntics, skill alineat.
- ✅ CAND ≤ 20 % assolit. ⏳ OK ≥ 80 %: 1.2 R2 (6 cel·les + 3 de taula), 1.3 F1 (7), 1.4 derivats (~8 blancs).

### Següents passos
1.2 R2 (z GPS bloqueja la cota de l'annex; data del sondeig bloqueja la de camp; msnm → fondària als nivells), després
1.3 F1 i 1.4 derivats, segons l'ordre pactat del vespre.

*Fi entrada 2026-09-05 (nit). R5: el consolidador honora la declaració del proveïdor que el lector ja havia marcat; CAND baixa al 20 %.*

## 2026-09-05 (nit, 2) — Bloc 1.2, R2 «concepte veí»: cota, data de camp i nivells en msnm — escalars 112 → 116 OK (79 %), CAND 17 %

### Context
Segona peça del bloc 1 (handoff §Decisions del Josep al tancament): **R2**, «un concepte veí entra com a bloquejador».
Tres cares, totes a la mesura dels 8: (a) la z GPS de `COORDENADES.txt` (0,5) i el datum relatiu del full de camp
(«±0,00 respecte el carrer», 0,6) bloquejaven la cota de l'annex a Bell-lloc, Linyola i Alcoletge (a Alcoletge la GPS
té 10,7 m d'anomalia); a Bell-lloc, a més, «+199,50 msnm segons el plànol topogràfic ICGC» i «199,50 m» eren dos
clústers; (b) a Bell-lloc la data del sondeig (6/10: comanda DATA DE PRESA 0,7, annex sondeig 0,5, full manuscrit
0,55) bloquejava la de camp (1/10, fitxa F38 = A); (c) a Linyola i Alcoletge el lector copia l'escala msnm del tall als
nivells i al freàtic i l'informe vol fondàries. Mateix mètode: línia base = r5 (112/29/5/1/0), test per regla,
reconsolidació dels 7 a cost 0 (`_reconsolida-2026-09-05-vei` vs `-r5`), llista de totes les cel·les que canvien.

### Decisions arquitectòniques clau
1. **Cota: només els annexos de l'Eva contradiuen** (`_FIELD_BLOCKER_DOC_TYPES["cota_referencia"]` = annex DPSH,
   sondeig, tall). La z GPS, el datum relatiu del full de camp i l'ICGC són conceptes veïns: corroboren o fan de
   recanvi, van a `altres`. Why: el skill (Pas 3) ja diu «annex DPSH = annex sondeig z > COORDENADES z (l'Eva no l'usa)
   > ICGC»; el que faltava era que la prioritat no fos un bloqueig. Alternativa rebutjada: abaixar la confiança de la z
   GPS a 0,3 → Alcoletge (anomalia de 10,7 m) hauria continuat sortint com a candidat de la mateixa mida; i no resol
   el datum relatiu (0,6, lector Claude). **Rubí no canvia** (F1): les dues capçaleres de l'annex DPSH (+212,50 / +212)
   són del tipus que sí que contradiu.
2. **La clau de `cota_referencia` és el nombre** (`_LEADING_COTA_RE`: «+199,50 msnm segons…» = «199,50 m»). Why: R1
   per a cotes; sense això la forma llarga de l'annex DPSH feia de contradicció de la curta del sondeig (Bell-lloc).
3. **Castellar: sistema relatiu → candidats, com a post-procés** (`_cota_relative_system`). Amb (1) sola, Castellar
   pujava a segur (570,90) i l'or el vol candidats perquè l'annex DPSH treballa «respecte el carrer» (−4,0) i el signat
   va usar la relativa (`_LESSONS`). Es demota després de consolidar les taules, quan la cel·la `cota_inici` (segura,
   annex DPSH) és relativa: candidats [absoluta, relativa (annex DPSH, sistema relatiu)]. Why post-procés: el
   consolidador de camps no veu les taules; és el mateix patró que `_decide_sondeig_cota` (Pas 3b) al revés.
4. **Data de camp: el dia del sondeig és un altre dia, no una contradicció** (`_is_other_field_day`): data completa,
   a ≤ 30 dies de la guanyadora, amb tots els senyals forts (≥ 0,4 o A) de documents de la campanya (sondeig, presa de
   mostra, laboratori, fitxa, DPSH). Valor = primer dia (segur), l'altre dia com a candidat anotat («altre dia de camp;
   regla d'Eva: posar els dos dies») i `extra.dies_de_camp`. Why aquesta forma i no «1 i 6 d'octubre» com a valor: és
   exactament el que fa l'or de Bell-lloc (segur 2025-10-01, candidat «2025-10-06 (sondeig)») i el skill («dia del
   sondeig, candidat 2 de field_date»); el text de l'informe és feina del generador (M341), que ara té els dos dies.
   **El Josep pot capgirar-ho** (era «decisió Josep» al handoff): és un canvi d'una línia. Una data d'un plànol o d'un
   tall, o a més de 30 dies, continua bloquejant (test).
5. **msnm → fondària: conversió determinista amb la cota SEGURA del mateix `_decisions.json`, un candidat per punt**
   (`_depths_from_msnm`, `_depth_candidates`): «≈243,6 msnm a P-1/P-3; ≈244,6-244,7 msnm a P-2» → «≈-1,4 m a P-1
   (contacte ≈243,6 msnm)», «≈-1,4 m a P-3 (…)», «≈-0,4/-0,3 m a P-2 (…)»; sense punts, conversió en el lloc + «(cota …
   msnm)». Font «(derivat: fondària = cota +245 − 243,6 msnm) ← tall», lectura original a la nota. Why per punt: és la
   granularitat de l'or («candidats per punt, mai un únic valor segur») i el que l'Eva tria. Cap candidat nou: els
   mateixos, en el sistema de l'informe. Només amb cota segura i absoluta (Castellar, candidats, no converteix;
   Bell-lloc, ja en fondàries, no es toca). Cel·les: `soil_levels.de/a`, `dpsh_tests/sondeig_tests.nivell_freatic`.
6. **Primera versió de la superfície descartada en calent:** «0,0 m / +245 msnm» (les dues escales) igualava el
   candidat de l'or però no el seu VALOR («0,0 m (superfície, cota +245 msnm)») i deixava la cel·la en ALERTA; la forma
   en el lloc («0,0 m (superfície, escala del tall) (cota 245 msnm)») és més simple i és la que mesura bé.

### Implementació
- `automation/lectura/consolidate.py` (+~190 LOC): constants R2 (`_FIELD_BLOCKER_DOC_TYPES`, `_LEADING_COTA_RE`,
  `_CAMPAIGN_DOC_TYPES`, `CAMPAIGN_WINDOW_DAYS`, `_MSNM_POINT_RE`, `_MSNM_NUM_RE`, `_MSNM_CELLS`); `value_key`
  (cota); `decide` (blockers per tipus, `other_days`, candidat anotat, `extra`); `_is_other_field_day`;
  post-processos `_cota_relative_system`, `_depths_from_msnm` (+ `_is_rel_cota`, `_fmt_depth`, `_decimals`,
  `_msnm_scale`, `_depth_candidates`) cridats a `consolidate_python` després de `consolidate_tables`.
- `tests/test_lectura_consolidate.py`: +4 `test_R2_*`; el test sintètic passa de «GPS contradiu → candidats» a «GPS a
  `altres` → segur» (era la regla vella codificada).
- Skill: cap canvi (Pas 3 ja ho deia així). Artefactes: `{slug}/_reconsolida-2026-09-05-vei/`.

### Validació empírica (reconsolidació dels 7, cost 0; comparador v4 sobre l'or)
- **9 cel·les canvien de valor o estat, cap altra; 0 regressions; conflictes A-vs-A idèntics.** Bell-lloc
  `cota_referencia` 199,50 → segur i `field_date` 2025-10-01 → segur (candidat «2025-10-06» anotat, `extra.dies_de_camp`);
  Linyola i Alcoletge `cota_referencia` → segur; Linyola `soil_levels[0].de` «0,0 m (…)», `[0].a` un candidat per punt
  (P-1 −1,4 = or), `[1].de` en el lloc; Alcoletge `[0].a` per punt, `[1].de` en el lloc. A més, els 3 `nivell_freatic`
  d'Alcoletge tenen el candidat del tall en fondària («~-1,0 m (matís: humitat…)»; ja eren OK pel comparador v4).
  Castellar: mateix estat (candidats) amb la regla nova i la relativa com a candidat 2.
- Escalars: **112 → 116 OK (79 %) / 29 → 25 CAND (17 %) / 5 ALERTA / 1 blanc / 0 ERR.** Taules: **137 → 138 OK / 21 CAND /
  8 → 7 ALERTA / 31 blanc / 0 ERR** (Linyola `[0].a` CAUTELA → OK; `[0].de` ALERTA → CAUTELA «bo dins»).
- Contrast amb el signat (diagnòstics): Linyola +245,0 i Alcoletge +188,20 = signat; Bell-lloc 199,50 = or.
- Llindars: ERR 0 ✅ · CAND 17 % ✅ · OK 79 % ⏳ (80: a una cel·la).

### Tests
+4 `test_R2_*` i 1 actualitzat; consolidador 148 verds. Suite sencera: vegeu la sessió.

### Latència / cost
0 USD.

### Limitacions conegudes
- Alcoletge `soil_levels[0].a`/`[1].de` i Linyola `[1].de` queden CAND: el contingut és correcte (−1,4 / −1,2) però l'or
  d'Alcoletge agrupa punts per fondària («-1,4 m (P-1 i P-3) / -1,2 m (P-2)») i el comparador compara tuples de nombres
  (els «P-1» inclosos): és una limitació del comparador amb cel·les per punt (C), no de la lectura. Linyola `[1].de`
  («mateix contacte que 'a' del nivell 1») és el derivat 1.4 (`de` del nivell N = `a` del nivell N−1).
- `_is_other_field_day` depèn del tipus de document: una data del sondeig llegida en un `correu` bloquejaria.
- El text «1 i 6 d'octubre» a l'informe no existeix encara: el generador té `extra.dies_de_camp` (M341).

### GO/NO-GO
- ✅ 9 cel·les cap a l'or, 0 regressions, 4 tests, conflictes idèntics, Castellar intacte. ✅ CAND ≤ 20 %.
- ⏳ OK ≥ 80 % (79): 1.3 F1 (7 cel·les), 1.4 derivats (~8 blancs de taula + Linyola `[1].de`).

### Següents passos
1.3 F1 («qui mana» per parella de documents: GTL > comanda; capçalera coherent entre pàgines; SPT creuats de Vilanova
amb pregunta a Eva), després 1.4 derivats.

*Fi entrada 2026-09-05 (nit, 2). R2: els veïns corroboren, no bloquegen; els nivells parlen en el sistema de l'informe.*

## 2026-09-05 (nit, 3) — Bloc 1.3, F1 «fonts d'Eva inconsistents»: precedència GTL > annex > comanda i capçalera coherent de l'annex DPSH — escalars 116 → 118 OK (80 %), l'últim ERR real sobre el signat cau; data doble de la campanya a l'informe (decisió del Josep)

### Context
Tercera peça del bloc 1: **F1**, l'Eva discrepa d'ella mateixa dins de la carpeta. Set cel·les al diagnòstic: `lab_depth`
de Rubí (comanda 0,6-1,4 vs GTL 0,6-1,2; signat 0,6-1,2) i de Linyola (Excel DPSH 1,0-1,5 i full de camp 1,00-1,75 vs GTL
1,0-1,15; signat 1,0-1,15); la cota P-2 de l'annex DPSH de Rubí (p.2 «+212» vs p.1/p.3 «+212,50»; signat +212,50: l'únic
ERR real que quedava sobre el signat); i quatre que no es poden resoldre amb documents (Castellar `lab_sample_id` MA-1 vs
SPT-1; Linyola errata «argilsoso» del tall; Vilanova SPT P-1/P-3 creuats al signat ×2 i litologia re-redactada). Línia
base = vei (116/25/5/1/0). A mig camí, el Josep decideix la data doble (vegeu decisió 4).

### Decisions arquitectòniques clau
1. **`_FIELD_BLOCKER_DOC_TYPES` (R2) es generalitza a `_FIELD_PRECEDENCE`: nivells de «qui mana» per camp.** Un clúster
   només contradiu el guanyador si el seu millor document és del mateix nivell o d'un de superior; fora de la llista =
   veí, mai bloqueja. `cota_referencia`: (annexos); `lab_depth`: (GTL) > (annex de sondeig) > (comanda). Why: el skill
   ja diu «el GTL mana si discrepa» i el propi senyal de la comanda ho anota; el full de camp i l'Excel DPSH escriuen el
   tram PREVIST i el laboratori la mostra real. Un GTL sí que contradiu un altre GTL (test). Alternativa rebutjada:
   llegir la nota del senyal («el GTL mana») → depèn del text del lector; la precedència és del skill.
2. **Capçalera de l'annex DPSH sense decimals entre germanes amb decimals = truncament d'impressió → candidats
   [coherent, literal], mai segur** (`_dpsh_cota_header_coherence`, post-files de `dpsh_tests`). Condicions: mateix
   document, mateixa part entera, |diferència| < 1 m, ≥ 2 germanes amb el mateix valor decimal. Why aquesta forma i no
   «diferència < 1 m entre punts»: les cotes per punt discrepen legítimament en terreny inclinat (Anciles +1106,40/30/
   42/65; Castellar −4,0/−4,2 amb decimals explícits); només el literal sense decimals és sospitós. La coherent va
   primera perquè és el que l'Eva va signar i el que diuen dues pàgines de tres; el literal queda visible; la pregunta a
   l'Eva continua al paquet. Marxa enrere en calent: la primera regex feia «+212,50» ↔ «+21» per retrocés i no
   disparava; cal `(?![0-9.,])`.
3. **Castellar `lab_sample_id` (or MA-1, skill «annex de l'Eva mana per l'etiqueta» → candidats SPT-1) NO es toca:** or i
   skill discrepen sobre un criteri (la mostra analitzada és la MA del GTL, l'etiqueta de l'annex és l'SPT) → pregunta
   a l'Eva, no una regla. Vilanova ×3 i l'errata de Linyola: fonts del signat / de l'Eva; el sistema fa bé de dubtar.
4. **Data doble de la campanya a l'informe (Josep, 2026-09-05):** la plantilla tenia les dues ranures amb la mateixa
   variable (`data_camp_text`); els signats diuen «El dia 1 d'octubre de 2025, es va visitar l'obra» i «la campanya de
   camp, que s'ha realitzat el dia 1 i 6 d'octubre de 2025». Nova variable **`data_camp_inici_text`** (primer dia) a la
   primera ranura; `data_camp_text` (tots els dies) a la segona. `first_field_day_text(dates, text)` al generador: de la
   llista ISO si n'hi ha, si no del text ja formatat («1 i 6 d'octubre de 2025» → «1 d'octubre de 2025»; un sol dia,
   intacte). I la lectura ALIMENTA les dates del wizard: `fields.field_date` segur → `merged.field_work_dates`
   (`extra.dies_de_camp` o el dia sol) + `field_work_dates_text` (`_overlay_field_dates`); en candidats no toca res (la
   via B ja llegeix les dates dels PDF); Eva mana sempre. `field_date` continua sent el primer dia (or; R2): és el que
   demanava el Josep un cop vist que hi ha dues ranures («si cal crear una variable específica, fem-ho»).

### Implementació
- `automation/lectura/consolidate.py` (+~60 LOC): `_FIELD_PRECEDENCE` + `_precedence_tier` (substitueix
  `_FIELD_BLOCKER_DOC_TYPES`), `_INT_COTA_RE`, `_dpsh_cota_header_coherence` (cridat a `consolidate_tables`).
- `automation/dpsh_extractor.py`: `first_field_day_text`. `automation/report_generator.py`: `context['data_camp_inici_text']`.
  `web/lectura_service.py`: `_overlay_field_dates`. `templates/g3dt-jinja-template.docx`: primera ranura →
  `{{ data_camp_inici_text }}` (render comprovat: «El dia 1 d'octubre de 2025» / «el dia 1 i 6 d'octubre de 2025»).
- Tests: `test_F1_*` ×2 (consolidador), `test_overlay_field_date_segur_writes_dates_list_and_catalan_text`
  (`test_lectura_service.py`), `tests/test_field_dates_text.py` (nou: helper ×7, formatador, plantilla).
- Artefactes: `{slug}/_reconsolida-2026-09-05-f1/`.

### Validació empírica (reconsolidació dels 7, cost 0; comparador v4 sobre l'or)
- **3 cel·les canvien, cap altra; conflictes A-vs-A idèntics.** Rubí i Linyola `lab_depth` → segur (= or i signat); Rubí
  `dpsh_tests[P-2].cota_inici` segur «+212» → candidats «+212,50» primer (= signat; ALERTA → OK).
- Escalars: **116 → 118 OK (80 %) / 25 → 23 CAND (16 %) / 5 ALERTA / 1 blanc / 0 ERR.** Taules: **138 → 139 OK / 21 /
  7 → 6 ALERTA / 31 / 0.** Sobre el signat: **0 ERR també a les taules** (l'últim, Rubí P-2, era aquest).
- Llindars: **ERR 0 ✅ · CAND 16 % ✅ · OK 80 % ✅** — els tres per primer cop (escalars sobre l'or).
- Suite: consolidador 150, lectura_service i field_dates: 204 verds als tres mòduls; suite sencera a la sessió.

### Latència / cost
0 USD.

### Limitacions conegudes
- F1 que queda: Castellar `lab_sample_id` (criteri, pregunta a l'Eva), Linyola «argilsoso» (errata del tall; litologia
  sempre candidats), Vilanova SPT creuats ×2 i litologia re-redactada (signat).
- `_dpsh_cota_header_coherence` només mira la cel·la `cota_inici` de l'annex DPSH; la mateixa forma en un altre bloc no
  hi és (no s'ha vist).
- La data doble: el generador ja té les dues ranures; el wizard no mostra encara la llista de dies (només la frase).

### GO/NO-GO
- ✅ 3 cel·les cap a l'or/signat, 0 regressions, tests, conflictes idèntics. ✅ Tres llindars assolits (escalars).
- ⏳ Taules: OK 71 % (31 blancs: 1.4 derivats), 6 ALERTA (5 OK per veritat + Linyola msnm R2 resolt? vegeu agregat).

### Següents passos
1.4 derivats del consolidador (`a` de l'últim nivell, `mostra_del_nivell`, litologia del nivell de la mostra, «mateix
contacte» → `de` del nivell N = `a` del N−1), després 1.5 L1/L3 i 1.6 T2.

*Fi entrada 2026-09-05 (nit, 3). F1: qui mana, mana; i l'informe diu «El dia 1» i «el dia 1 i 6».*
