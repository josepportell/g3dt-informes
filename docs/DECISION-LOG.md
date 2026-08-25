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
