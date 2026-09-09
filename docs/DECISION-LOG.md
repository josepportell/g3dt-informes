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

## 2026-09-05 (nit, 4) — Bloc 1.4, derivats geomètrics de `soil_levels`: 0,00 del primer nivell, sostre = base de l'anterior, base de l'últim nivell = fons d'investigació, `mostra_del_nivell` per interval, litologia del nivell de la mostra — taules 139 → 143 OK, blancs 31 → 20, 13 cel·les mogudes, cap re-lectura

### Context
Quarta peça del bloc 1 (handoff `_FOR-NEW-YOU-20260906.md` §Peça 1.4). Línia base f1 reproduïda exactament abans de
tocar res (escalars 118/23/5/1/0; taules 139/21/6/31/0). Triage dels **31 blancs de taula** contra l'or (`_tables_decisions.json`,
camp `rule`) ABANS de codificar: **9 són d'altres peces** (8 cotes d'Anciles = I1, les lectures de `PDF_V0` no són a la
carpeta del run; `n30` de Linyola = L1); **12 no són derivables** amb el que hi ha al `_decisions.json` (la transició és
una lectura gràfica del tall que el lector no ha emès: Vilanova `[0].a`/`[1].de` i les dues `mostra`, Anciles `[0].a`/
`[1].de` i les dues `mostra`, la franja de sòls superficials de Rubí ×2, la base de la cobertura de Bell-lloc); **10 sí**.
El signat confirma la regla de la base de l'últim nivell: el gruix de la taula sísmica és sempre el rebuig DPSH més
profund (Bell-lloc 2,45 = P-2, no el −1,80 del log del sondeig; Rubí 4,55; Linyola 1,60 + 1,30 = 2,90; Alcoletge
1,40 + 0,29 = 1,69; Anciles «potencia máxima detectada 3,92» = 5,92 − 2,00).

### Decisions arquitectòniques clau
1. **Un sol post-procés `_derive_soil_levels(fields, tables)` a `consolidate_python`, DESPRÉS de `_cota_relative_system`
   i `_depths_from_msnm`.** Why: les regles necessiten les `a` en fondària i per punt, i això només existeix després de
   la conversió msnm → fondària (R2). Alternativa rebutjada: dins de `consolidate_tables` al costat de E2/E2b (Pas 3b) →
   allà Linyola encara diu «245 msnm» i cap derivat geomètric hi quadra. Ordre intern D1 → D2 → D3 → D4 → D5 perquè D4/D5
   consumeixen els sostres i bases que D1-D3 acaben de posar.
2. **D1 — el primer nivell sense capa de cobertura arrenca a 0,00, `segur`, font «(definició: …)».** És l'única excepció
   al «cap derivat puja a segur» (garantia 2), pel mateix motiu que E2b a la cobertura: és una definició geomètrica, no
   una lectura. Or: Alcoletge, Vilanova, Anciles `segur "0,00 m (…)"`. També PUJA a segur una lectura que ja diu 0,00
   (Linyola: el tall, conf < 0,8; la definició va primera, la lectura darrere com a corroboració). No toca res si la
   primera fila és cobertura (E2b/E2 manen: el 0,00 de l'annex sota una cobertura sense base NO és cap transició) ni si
   la lectura no és la superfície.
3. **D3 — la base de l'últim nivell no la dona cap document; el límit conegut és el fons d'investigació → `candidats`,
   mai segur.** Forma canònica = la frase de l'or de Linyola («fins al fons d'investigació (rebuig DPSH: −2,90/−2,15/−1,75 m
   per punt)»), amb «; sondeig S-1: −1,80 m» quan hi ha sondeigs i «profunditat assolida DPSH» si algun punt no arriba al
   rebuig. Omple el `no_trobat` (Linyola, Rubí, Vilanova, Anciles) i, si ja hi ha una base llegida (log del sondeig, Pas 3b
   la deixa en candidats) però el reconeixement arriba més avall, **afegeix** el fons com a candidat (Bell-lloc −1,80 vs
   −2,45; Castellar 1,20 vs 1,55). Why afegir: és el que l'Eva fa al signat (Bell-lloc 2,45). Font: «(derivat: la base de
   l'últim nivell és el fons d'investigació) ← fonts de `profunditat_assolida`» (fins a 3), cita del primer punt.
4. **D4 — `mostra_del_nivell` = el nivell que conté `lab_depth` al punt `lab_location`; interval, no judici de material.**
   Sostre = `de` propi o `a` de l'anterior; base = `a` pròpia, `de` del següent o, a l'últim nivell, el fons al punt. Es
   prefereixen les clàusules que anomenen el punt de la mostra (R2 les produeix; «~-1,4 m a P-1; ~-1,2 m a P-3» es parteix
   per «;»). Dins → `True`; fora → `False`; **a cavall del contacte → els dos candidats**, el de més part de l'interval
   primer (Alcoletge: 0,8-1,4 vs contacte ~1,2 a P-3 → 67 %/33 %; l'or: «possible» / «possible que no»). Valors booleans,
   com les lectures de l'annex (contracte i UI). Un derivat sí que pot dir `False` (els documents no-A no, `_cell_signals`).
   No deriva res si falta sostre o base al punt, si els candidats de `lab_depth` discrepen numèricament (Vilanova/Alcoletge
   tenen 3 formes del mateix tram → sí), o si la cel·la ja està llegida. Mai segur. **Límit acceptat:** Linyola: la
   mostra 1,0-1,15 cau dins del nivell 1 per interval (contacte ≈1,4 a P-3) però l'Eva l'assigna al 2n pel material
   (lutita); el derivat diu `True`/`False` en candidats i l'Eva decideix. Codificar «material vs interval» demana comparar
   litologies (LLM o tokens): fora de 1.4, apuntat.
5. **D5 — `spt_ma_tests[*].litologia` rep com a candidats la litologia dels nivells que el seu tram toca al seu punt**
   («Lutites, substrat (Nivell 2)»), font «(derivat: litologia del nivell que conté el tram de la mostra / el travessa
   (67 % dins), [sostre; base] a P-3) ← font del nivell». Mai segur (`_NEVER_SEGUR_CELLS`); no duplica una redacció que ja
   hi és (Castellar: l'annex ja escriu la litologia del nivell a la mostra); el 4t va a `altres`. Or d'Alcoletge:
   exactament aquests dos candidats → CAUTELA → OK.
6. **D2 — el sostre no llegit del nivell N és la base del N−1**, candidats amb font «(derivat: mateix contacte que 'a' del
   nivell anterior «…») ← …». Implementat i testat però **mou 0 cel·les al corpus**: allà on falta el `de` també falta
   l'`a` anterior (Vilanova, Anciles, Rubí). **Sense regla inversa** (`a` de N−1 des del `de` de N): Bell-lloc la faria
   fallar (el 0,00 que l'annex dona al nivell 1 no és la base de la cobertura, E2).
7. **Or d'Alcoletge `[1].a` = `no_trobat` («potència no determinada per cap document») vs Linyola `segur` i Vilanova/Rubí/
   Anciles `candidats` amb la mateixa frase «fins al fons».** Amb D3, Alcoletge surt candidats → el comparador marca
   **ALERTA formal** (or `no_trobat`, prod `candidats`). El contingut coincideix amb els altres quatre ors i amb el signat
   (0,29* = fins a −1,69). **No es toca l'or** (és la vara de mesurar; decisió del Josep: alinear l'or d'Alcoletge amb els
   altres quatre, o acceptar l'ALERTA com a coneguda). Tampoc s'afegeix cap excepció al codi: no hi ha criteri que separi
   Alcoletge de Linyola.
8. **Test R2 actualitzat** (1 assert): el `de` del nivell 1 de Linyola ja no és «0,0 m…» candidats sinó «0,00» segur amb
   la lectura convertida al 2n candidat (D1). Canvi d'expectativa, no de comportament de R2.

### Implementació
- `automation/lectura/consolidate.py` (+~330 LOC, 2578 → 2937): bloc «1.4» abans de `_canonical_municipality`:
  `_DEPTH_NUM_RE`/`_depth_nums` (cal decimal o «m»: «Nivell 1» no és una fondària; ≥ 50 = msnm, es descarta), `_cell_depths`
  (per punt, clàusules per «;»), `_interval_of`, `_single_point`, `_fons_rows`/`_fons_text`/`_fons_at`,
  `_derive_first_level_top` (D1), `_derive_level_tops` (D2), `_derive_last_level_base` (D3), `_level_membership` +
  `_derive_sample_level` (D4), `_same_lithology` + `_derive_sample_lithology` (D5), `_derive_soil_levels` (orquestra i
  recalcula `estat_bloc`). Crida a `consolidate_python` rere `_depths_from_msnm`.
- `tests/test_lectura_consolidate.py`: `_d14_corpus` (Linyola per defecte, parametritzable), `_alcoletge_like`; 6 tests
  `test_D14_*` (una regla per test + `_depth_nums`/`_fons_text`/`_cell_depths`); `test_R2_msnm_…` 1 assert.
- Artefactes: `{slug}/_reconsolida-2026-09-05-d14/` (7 projectes; el nom `-2026-09-06-d` del handoff no s'ha usat:
  encara és dia 5).

### Validació empírica (reconsolidació dels 7, cost 0; comparador v4 sobre l'or)
- **13 cel·les canvien d'estat/valor, cap altra; conflictes A-vs-A idèntics (4/1/0/1/1/0/0); contracte NET als 7.**
  - D1: Alcoletge/Vilanova/Anciles `[0].de` no_trobat → segur 0,00 (**BUIT → OK ×3**); Linyola `[0].de` candidats → segur
    (**CAND → OK**).
  - D3: Linyola `[1].a` (**BUIT → CAND**, «bo dins» de l'or segur), Rubí `[1].a` = or `[0].a`, Vilanova `[1].a`, Anciles
    `[1].a` (**BUIT → CAND** disjunts: mateixa cosa, frase de l'or diferent); Alcoletge `[1].a` (**OK → ALERTA formal**,
    decisió 7). Afegits sense canvi de veredicte: Bell-lloc i Castellar `[1].a`.
  - D4: Linyola `[0].mostra` True / `[1].mostra` False; Alcoletge `[0].mostra` [True, False] / `[1].mostra` [False, True]
    (**BUIT → CAND ×4**; l'or té textos «possible/probable», el comparador no els casa amb booleans).
  - D5: Alcoletge `spt_ma_tests[0].litologia` **CAUTELA → OK**; Linyola i Bell-lloc reben la litologia del nivell (sense
    canvi de veredicte).
- Escalars: **118 / 23 / 5 / 1 / 0 (idèntics).** Taules: **139 → 143 OK (73 %) / 21 → 27 CAND / 6 → 7 ALERTA / 31 → 20
  blancs / 0 ERR.** Dels 20 blancs: 9 d'altres peces, 11 lectura gràfica no emesa.
- Tests: consolidador 150 → 156 verds; els tres mòduls 210. Suite sencera: vegeu la sessió.

### Latència / cost
0 USD (cap crida LLM; reconsolidació ~1 min).

### Limitacions conegudes
- 11 blancs de taula són lectura gràfica del tall que el lector no emet (transicions inclinades, franges superficials):
  només un skill que llegeixi el tall calibrat (1.5 L3?) els omple.
- D4 és interval pur: Linyola (material ≠ interval) queda `True`/`False` en candidats amb la resposta de l'Eva a l'altre
  costat; el comparador dona CAND igualment. «Material vs interval» = feina futura (comparar litologies).
- D2 no mou res al corpus; l'or de Linyola `[1].de` ja el resolia R2 (el lector va escriure «mateix contacte…»).
- Or d'Alcoletge `[1].a` incoherent amb els altres quatre (decisió 7): 1 ALERTA formal fins que el Josep decideixi.
- `_fons_text` enumera els punts en l'ordre de les files (P-1, P-2, …); la font del candidat només cita 3 documents.

### GO/NO-GO
- ✅ 12 cel·les cap a l'or o sense canvi de veredicte; +4 OK, +7 CAND (de blanc), −1 CAND (→ OK); 0 regressions de
  contingut; tests; conflictes idèntics; contracte net.
- ⚠ 1 ALERTA formal (Alcoletge `[1].a`) per incoherència de l'or, no del sistema — decisió del Josep.
- ⏳ Suite sencera (diff de noms contra `suite-vermells-esperats.txt`): a la sessió.

### Següents passos
1.5 L1/L3 (skill + re-lectura parcial: cost real, dir-ho abans), 1.6 T2, 1.7 R4 + persona/despatx (Eva). Decisió del Josep
sobre l'or d'Alcoletge `[1].a`. Els 11 blancs gràfics només cauen amb lectura del tall calibrat.

*Fi entrada 2026-09-05 (nit, 4). Derivats: el que el perfil implica, amb font; el que el tall dibuixa, encara no.*

## 2026-09-05 (nit, 5) — Peça 1.5 (L1/L3), part 1: telèfon fora del nom del client i cap N30 a una mostra alterada (cost 0, 1 ALERTA cau); skill v1.8 per a l'SPT del full manuscrit, re-lectura d'UN document preparada i pendent del vist-i-plau (cost)

### Context
Cinquena peça del bloc 1 (handoff `_FOR-NEW-YOU-20260905.md` §Bloc 1, fila 1.5: «L1/L3 forats de lector», 4 cel·les,
«cal re-llegir els docs afectats»). Diagnòstic previ sobre els artefactes, no sobre el pressupòsit: **dos dels tres forats
no necessiten cap re-lectura** — són brossa dins d'un valor ja llegit (L3) i es resolen al consolidador; només el tercer
(L1) és una lectura que falta. El Josep pregunta si els 5-6 USD del handoff són per projecte: no, eren el run parcial
d'Anciles (5 PDF, 5,87 USD); vegeu decisió 4.

### Decisions arquitectòniques clau
1. **L3a — telèfon enganxat al nom (`fitxa!C6` de la fitxa de camp G3, «MARIA ALBA BARRAU CASTÁN 616523792»): el nom és el
   valor, el telèfon va a la nota, la cita conserva l'original.** Normalitzador `_strip_phone_tail` a `add_entry`
   (`collect_field_signals`), només per a `_PERSON_LIKE_FIELDS` (client, arquitecte, despatx, laboratori) i només si
   davant del telèfon queden ≥ 2 lletres (un telèfon sol, o «2025», no es toquen). Why aquí i no al lector de plantilles
   G3: és l'únic punt per on passen TOTS els senyals de camp (LLM, plantilles, Python), i el telèfon es un patró tancat
   (9 xifres, 6-9 davant, +34 opcional). Efecte: la forma de la fitxa cau al mateix clúster que el nom del formulari p.5.
2. **L3b — una mostra alterada (MA) no té N30: `n30` → `no_trobat` amb nota, el colpeig anotat es conserva al `registre`,
   la lectura va a `altres`** (`_ma_sample_has_no_n30`, post-fila de `spt_ma_tests`). Dispara NOMÉS si totes les etiquetes
   de la fila són MA: a Castellar l'annex diu «SPT-1» i el GTL «MA1» per a la mateixa mostra (pregunta 12 a l'Eva) i el seu
   «R» no es toca (test). Why `no_trobat` i no candidats «--»: és el que diu l'or d'Anciles i el que el contracte permet
   (el generador ja escriu «--» quan no hi ha valor); un candidat «--» seria un valor inventat.
3. **L1 — el lector 1.6 de Linyola va llegir del «Full d'assaig SPT/MI/Mostra alterada» (PENETROS p.3) la cota i l'etiqueta
   de la mostra (`lab_*`) però NO la fila de l'assaig** (`tables.spt_ma_tests` absent), mentre que els lectors d'Alcoletge,
   Rubí i Vilanova, amb el mateix skill, sí la van emetre amb `n30.registre`. Variança del lector sobre un text que deia
   «l'Excel mana per als valors, el manuscrit es llegeix per si porta alguna cosa que l'Excel no té». **Skill v1.8:** el
   full d'assaig SPT emet SEMPRE una fila amb el registre de les 4 caselles; sense annex de sondeig és l'únic registre de
   cops del projecte; una sola casella ≥ 50 = rebuig al primer tram → «R». Cap canvi al consolidador: la regla «n30 mai
   segur» ja hi és, i «R» amb 50 al primer tram ja era al Pas 3b.
4. **Cost i comptabilitat de les lectures.** El runner llança `claude -p` amb `G3DT_LECTURA_AUTH=login` per defecte: treu
   la clau API de l'entorn del fill i el fill fa servir la sessió de claude.ai (la clau del `.env` no té crèdit; E2E
   2026-08-24). El `cost_usd` del `_telemetry.jsonl` és el que el CLI reporta (`total_cost_usd`), no un càrrec a crèdits:
   consumeix quota de la subscripció. Ordre de magnitud (Sonnet 5, esforç xhigh): 0,6-0,7 USD un correu, 0,8-0,9 un PDF
   senzill, 1,2-1,5 un annex de diverses pàgines, **2,07 USD el PENETROS.pdf de Linyola al run mare** (480 s, 52 torns: el
   document més car del projecte). Un projecte sencer (19-22 documents) ≈ 18 USD; els 7 ≈ 125 USD. **1.5 necessita UNA
   lectura** (Linyola PENETROS.pdf, ≈ 2 USD, 8 min): la resta és Python a cost 0.
5. **No es llança cap lectura sense el vist-i-plau del Josep** (handoff: «si una peça necessita re-llegir documents … cal
   dir-ho abans»; el Josep ha preguntat pel cost). Preparat i documentat: `runs/2026-09-05-l1-linyola/` (còpia del run
   mare sense `penetros.json` → el runner només re-llegeix aquest document per md5) amb la comanda a `_NOTES.md`.

### Implementació
- `automation/lectura/consolidate.py`: `_PERSON_LIKE_FIELDS`, `_PHONE_TAIL_RE`, `_strip_phone_tail` (+ crida a `add_entry`);
  `_MA_ID_RE`, `_ma_sample_has_no_n30` (cridat a `consolidate_tables`, bloc `spt_ma_tests`).
- `.claude/commands/g3dt-llegir-projecte.md` v1.8: línia de versió, `relation_to_others` (el full d'assaig SPT p.3 sí que
  aporta), bloc «Taula Assaigs SPT / MA» (regla nova). La cache de lectures va per md5: editar el skill no invalida res.
- Tests: `test_L3_phone_glued_to_a_person_name_goes_to_the_note`, `test_L3_altered_sample_has_no_n30` (Anciles + Castellar
  intacte). Consolidador 158 verds; els tres mòduls 212.
- Artefactes: `{slug}/_reconsolida-2026-09-05-l3/` (7 projectes); `runs/2026-09-05-l1-linyola/` preparat (no llançat).

### Validació empírica (reconsolidació dels 7, cost 0; comparador v4 sobre l'or)
- **1 cel·la canvia d'estat, cap altra; conflictes idèntics.** Anciles `spt_ma_tests[2].n30` (MA-1) candidats «2» →
  `no_trobat` = or (**ALERTA → OK**; el signat escriu «--»). Anciles `client_name`: mateix estat i valor (segur «Maria Alba
  Barrau Castán»); la forma de la fitxa surt ara «MARIA ALBA BARRAU CASTÁN» amb «telèfon 616523792 separat del nom» a la
  nota (sense canvi de veredicte).
- Taules: **143 → 144 OK / 27 / 7 → 6 ALERTA / 20 / 0.** Escalars idèntics (118/23/5/1/0). Dels 6 ALERTA que queden: 5
  «OK per veritat» del handoff + Alcoletge `[1].a` (STATUS §Pendents de revisió, 1).

### Latència / cost
0 USD fins aquí. L1: ≈ 2 USD (subscripció), ≈ 8 min, pendent del Josep.

### Limitacions conegudes
- `_strip_phone_tail` només treu un telèfon AL FINAL del valor; un telèfon al mig («Alba 616523792 Barrau») no es toca (no
  s'ha vist).
- L3b no dispara si alguna etiqueta de la fila és SPT (Castellar): correcte mentre la pregunta 12 sigui oberta.
- L1 sense mesurar: la fila de Linyola surt del lector, i el lector és variable; si la re-lectura torna a no emetre la
  fila, caldrà el mode `--only` sobre la p.3 o un fallback Python (les 4 caselles són text? no: manuscrit → visió).

### GO/NO-GO
- ✅ L3: 1 cel·la cap a l'or, 0 regressions, tests, conflictes idèntics. ⏳ L1: skill v1.8 escrit, carpeta preparada,
  lectura pendent del vist-i-plau.

### Següents passos
Si el Josep diu que sí: llançar `runs/2026-09-05-l1-linyola/` (comanda a `_NOTES.md`), comparar `spt_ma_tests[0].n30` amb
l'or, copiar `penetros.json` al run mare si és bo i reconsolidar. Després 1.6 T2.

*Fi entrada 2026-09-05 (nit, 5). L3 sense cost; L1 costa un document i es diu abans.*

## 2026-09-05 (nit, 6) — Peça 1.5, part 2: re-lectura d'UN document (Linyola PENETROS.pdf, skill v1.8): el lector emet la fila SPT però amb un dialecte nou; el consolidador l'accepta i deriva «R» del registre — 1 cel·la, blanc → candidats = or i signat; 1,63 USD

### Context
Amb el permís del Josep («permís per consumir crèdits per llançar la re-lectura de PENETROS de Linyola») s'ha llançat el run
parcial preparat a (nit, 5): `runs/2026-09-05-l1-linyola/` = run mare sense `penetros.json` → el runner ha saltat 19
documents per md5 i n'ha llegit 1. Resultat de la lectura (skill 1.8): la fila `spt_ma_tests` HI ÉS («SPT1», P3, 1,00 a 1,75,
`registre` [50, null, null, null], candidat «R», nota «una sola casella amb 50 cops i la resta buides = rebuig al primer
tram»). Però el consolidador la deixava en blanc.

### Decisions arquitectòniques clau
1. **El lector és un productor cec també en les claus de `n30`:** ha escrit els candidats a `value_candidates`, i el
   consolidador només coneixia `candidats_suma` / `candidates_suma` / `candidates` / `candidats`. S'afegeixen
   `value_candidates`, `valor_candidats`, `candidats_valor`, `n30_candidats`. Why no «arreglar el lector»: el skill no fixa
   el nom d'aquesta clau (només `registre`); el consolidador ha de llegir per forma, com fa amb els sumands de superfície.
2. **Rebuig derivat del registre:** un `registre` amb un tram ≥ 50 cops i la resta buides feia petar la suma dels trams
   centrals (`int(None)`) i no deixava cap senyal. Ara, si cap candidat escrit, ≥ 50 en un tram → candidat «R» amb nota
   «(derivat: ≥ 50 cops en un tram de 15 cm = rebuig — Pas 3b)», el registre conservat. Mai segur (guard existent).
3. **La lectura nova substitueix la vella al run mare** (`runs/2026-09-03-mesura-8/linyola/penetros.json`, skill 1.8); la
   vella (skill 1.6, sense fila SPT) queda a `runs/2026-09-05-l1-linyola/_anterior-skill-1.6/penetros.json` (subcarpeta:
   `load_corpus` només mira els JSON del primer nivell). Why: és el que s'ha pactat amb el Josep («si surt bé copio la
   lectura al run mare i reconsolido») i evita la trampa d'Anciles/I1 (dues carpetes de run per al mateix projecte).
4. **Variança del lector, comprovada:** mateix document, mateix model i esforç; 1.6 no va emetre la fila, 1.8 sí. La
   litologia manuscrita ha sortit «Llim marró…» (l'or de taules llegí «Lutita marró…»): candidats, com sempre.

### Implementació
- `automation/lectura/consolidate.py` `_cell_signals` (branca `n30`): alies de claus de candidats; regla «≥ 50 → R».
- `tests/test_lectura_consolidate.py`: `test_L1_manuscript_spt_sheet_refusal_at_first_tram_and_reader_dialect` (dialecte
  del lector + derivat sense candidat escrit). Consolidador 159 verds; els tres mòduls 213.
- Artefactes: `runs/2026-09-05-l1-linyola/` (lectura, `_telemetry.jsonl` del run aïllat, `_reconsolida-2026-09-05-l1/` amb
  `_decisions.json` i `_compare_*.txt`, `_anterior-skill-1.6/`); `{slug}/_reconsolida-2026-09-05-l1/` (7 projectes).

### Validació empírica
- Run parcial: 8,6 min totals; **PENETROS.pdf 463 s, 45 torns, 1,63 USD** (run mare: 480 s, 52 torns, 2,07 USD); cap
  timeout; consolidació Python 0,06 s; 0 conflictes; contracte net.
- Reconsolidació dels 7 (l1 vs l3): **1 cel·la canvia, cap altra; conflictes idèntics.** Linyola `spt_ma_tests[0].n30`
  `no_trobat` → `candidats` «R» (or segur «R (rebuig; registre: 50 cops al primer tram de 15 cm)»; signat N30 = R): **BUIT
  → CAND** («bo dins»; n30 no pot ser segur per contracte). `registre` [50, null, null, null] conservat.
- Taules: **144 OK / 27 → 28 CAND / 6 ALERTA / 20 → 19 blancs / 0 ERR.** Escalars idèntics (118/23/5/1/0).
- **Peça 1.5 tancada:** de les 4 cel·les del handoff, 3 mogudes (L3 ×2 a Anciles, L1 a Linyola) i la quarta (telèfon)
  era la mateixa cel·la que L3a. Blancs de taula 31 → 19 al llarg de la nit (1.4 + 1.5).

### Latència / cost
1,63 USD (quota de subscripció, `login`), 8,6 min de rellotge.

### Limitacions conegudes
- La regla «≥ 50 → R» només s'aplica quan el lector no ha escrit cap candidat; si n'escriu un de diferent, mana el lector
  (candidats, mai segur).
- Els alies de claus són una llista tancada: un lector que n'estreni una altra tornarà a deixar la cel·la en blanc. El
  rastre de dialectes (`notes_estructurals`) només cobreix els sumands de superfície; caldria estendre'l a `n30`.
- Vilanova SPT creuats i litologies re-redactades (F1) continuen fora de 1.5: són del signat / de l'Eva.

### GO/NO-GO
- ✅ 1 cel·la cap a l'or i el signat, 0 regressions, test, conflictes idèntics, cost dit abans i autoritzat.
- ⏳ Suite sencera: a la sessió.

### Següents passos
1.6 T2 (decidir si la passada LLM de conflictes es manté: mesurar als 7 runs si els valors de `_consolida_only.json` són
millors que els candidats Python contra el signat), després 1.7 (amb l'Eva) i bloc 2.

*Fi entrada 2026-09-05 (nit, 6). Un document, 1,63 USD, una cel·la; i el consolidador que llegeix per forma, no per clau.*

## 2026-09-05 (nit, 7) — Esmena a (nit, 6) arran d'una pregunta del Josep: la «R» de l'N30 de Linyola NO s'infereix, era impresa a tres documents; el lector la va deixar al text de la cita per «sempre registre» — skill v1.9

### Context
El Josep, en llegir (nit, 6): «el valor R està sempre a algun document (fins i tot a més d'un, en diversos formats): per què,
o què, calculem?». Comprovat sobre les lectures del run mare de Linyola (`runs/2026-09-03-mesura-8/linyola/`): té raó.

### Decisions arquitectòniques clau
1. **On era la «R», literalment, abans de cap re-lectura:** (a) `pdf_annexes_4001607_dpsh.json` (annex DPSH p.3, columna
   «Mesura de par»): fila `spt_ma_tests` amb cita «SPT-1 / 1,0 a 1,5 / R» i **`n30: null`**, nota «"R" indica rebuig però no
   hi ha registre de cops»; (b) les dues lectures del tall: «N=R just al límit» a P-3, només a les notes del document, no a
   cap taula; (c) el full manuscrit: «50» a la primera casella del colpeig (= rebuig, per la pràctica de l'Eva ja recollida
   al Pas 3b). **La causa arrel no és de lectura sinó de redacció del skill:** «n30 MAI segur — sempre `registre` + candidats
   de la suma» es va entendre com «sense registre, no posis valor». Un N30 imprès és una lectura literal.
2. **Skill v1.9:** regla explícita al bloc «Taula Assaigs SPT / MA»: un N30 imprès («R» o número) sense registre s'escriu
   com a candidat amb la nota «sense registre». Cap re-lectura ara (la cel·la de Linyola ja diu «R» pel manuscrit); vigent
   per als projectes següents. La cache de lectures va per md5: editar el skill no invalida res.
3. **La regla «≥ 50 cops en un tram → R» del consolidador (nit, 6) es manté**, reetiquetada mentalment com el que és: una
   convenció de transcripció (la del propi full: 50 i la resta buides), no un càlcul, i només s'aplica quan el lector dona
   el registre sense cap valor. El Josep no ha demanat treure-la; queda dit que és una línia si un dia molesta.
4. **Les «R» de l'Excel DPSH i dels peus de l'annex («Rebuig a la cota de -1,75 m») són del penetròmetre**, no de l'SPT: la
   columna N30 de la taula d'assaigs no les ha de prendre. Coincideixen al mateix punt a Linyola però són dos assaigs.

### Implementació
- `.claude/commands/g3dt-llegir-projecte.md` v1.9 (línia de versió + regla nova al bloc SPT/MA). Cap canvi de codi ni de
  tests; cap mesura nova (no canvia cap `_decisions.json`).

### Limitacions conegudes
- La «N=R» del tall continua sense camí cap a `n30` (el lector la deixa a les notes): el skill ja preveu `n30_candidat_tall`
  per al N imprès al tall; caldria comprovar en el proper run si el lector l'omple quan el tall marca «N=R».

### Següents passos
Cap. Entrada d'esmena; (nit, 6) queda tal com és, amb aquesta lectura correcta al costat.

*Fi entrada 2026-09-05 (nit, 7). Llegir, no inferir: la R ja hi era.*

## 2026-09-05 (nit, 8) — Validació del skill v1.9 amb la re-lectura de l'annex DPSH de Linyola (1,09 USD): la «R» impresa surt com a valor; efecte col·lateral, el lector llegeix la columna de colors «Nivells» per punt i destapa dues febleses dels derivats (D3, D4), arreglades

### Context
El Josep pregunta si val la pena re-llegir el PENETROS per validar la v1.9; resposta: no (la v1.9 parla d'un N30 imprès
SENSE registre; el manuscrit en té). El document que la posa a prova és l'annex DPSH imprès (`PDF/ANNEXES/4001607_DPSH.pdf`),
on la lectura 1.6 va deixar `n30: null` amb la «R» a la cita. Permís del Josep («Sí, llança l'annex DPSH»). Run parcial
`runs/2026-09-05-v19-linyola-dpsh/` (còpia del run mare sense aquesta lectura): 5,3 min totals, el document 281 s, 16 torns,
**1,09 USD** (1.6: 0,97 USD, 261 s).

### Decisions arquitectòniques clau
1. **La v1.9 funciona a la primera:** `"n30": "R"` amb la nota «N30 imprès directament com a 'R' sense colpeig per trams de 15
   cm — sense registre (regla v1.9); candidat, mai segur». Al consolidat, «R» té ara dues fonts documentals (manuscrit i
   annex); la UI en mostra una (formes idèntiques es fusionen), és el comportament de sempre.
2. **Efecte col·lateral, legítim:** el lector 1.9 ha llegit també la **columna de colors «Nivells»** de l'annex DPSH (taronja =
   Nivell 1, groc = Nivell 2) i n'ha emès `soil_levels` PER PUNT (6 files, amb `punt`): P-1 0,00-1,60 / 1,80-2,90; P-2
   0,00-0,00 / 0,20-2,15; P-3 0,00-1,00 / 1,20-1,75. Són els colors de l'Eva: l'or d'Alcoletge usa exactament aquesta font
   des de l'Excel («columna G (Nivells), canvi color 29→43»). `_group_soil_levels` les fusiona per nom de nivell (última
   prioritat, `_SOIL_PRIMARY_ORDER`); les fondàries queden com a candidats darrere de les del tall (o a `altres`).
3. **Feblesa 1 (D3):** la base del nivell 2 passava de «fins al fons d'investigació (rebuig DPSH: -2,90/-2,15/-1,75 m per
   punt)» a «-2,90» perquè ara hi havia una base LLEGIDA (la banda de color acaba on acaba l'assaig) i D3 només omplia
   blancs o afegia el fons si era més profund. **Regla nova:** si TOTES les bases llegides de l'últim nivell coincideixen
   (±5 cm) amb fondàries de rebuig / del sondeig, no són transicions sinó el final del reconeixement → el text del fons
   va primer, les lectures darrere. Efecte també a Bell-lloc (-1,80 = sondeig S-1) i Castellar (1,20 = S-1): el fons
   primer, per punt; veredictes intactes (solapament amb l'or).
4. **Feblesa 2 (D4):** `mostra_del_nivell` del nivell 2 passava de «False» (derivat geomètric) a «True» perquè l'annex
   ho afirma («la mostra SPT-1 (interval 1,0 a 1,5) cavalca la transició»: amb el tram NOMINAL de l'annex, no el real del
   GTL 1,0-1,15) i D4 només omplia blancs. **Regla nova:** si una lectura no-A (candidats) afirma un booleà i la geometria
   (tram real del GTL al punt) diu el contrari, el derivat s'afegeix com a segon candidat; el llegit continua primer. Un
   `segur` (annex de sondeig) no es toca. L'Eva veu la discrepància en lloc d'una afirmació sola.
5. **La lectura 1.9 substitueix la 1.6 al run mare** (`linyola/pdf_annexes_4001607_dpsh.json`); la 1.6 a
   `runs/2026-09-05-v19-linyola-dpsh/_anterior-skill-1.6/`. Mateix criteri que (nit, 6).

### Implementació
- `automation/lectura/consolidate.py`: `_derive_last_level_base` (bases llegides = fons → text primer),
  `_derive_sample_level` (candidats no-A contradits per la geometria → derivat afegit).
- Tests: `test_D14_read_base_equal_to_refusal_depths_is_the_investigation_bottom`,
  `test_D14_sample_level_claimed_by_a_weak_document_gets_the_geometric_alternative`; 1 assert de
  `test_D14_last_level_base_is_the_investigation_depth` actualitzat (Bell-lloc: el fons primer). Consolidador 161 verds; els
  tres mòduls 215.
- Artefactes: `runs/2026-09-05-v19-linyola-dpsh/` (lectura, telemetria aïllada, `_decisions.json` del runner,
  `_anterior-skill-1.6/`); `{slug}/_reconsolida-2026-09-05-v19/` (7 projectes).

### Validació empírica (reconsolidació dels 7, v19 vs l1)
- **3 cel·les canvien de VALOR, cap d'estat; cap veredicte canvia; conflictes idèntics.** Castellar i Bell-lloc
  `soil_levels[1].a`: el fons primer (or candidats amb -1,20 / -1,80 i -2,45: solapament, OK com abans). Linyola
  `soil_levels[1].mostra_del_nivell`: [True (annex DPSH), False (derivat)] — CAND com abans (l'or té textos). Linyola
  `soil_levels[1].a` conserva el text del fons (regla 3). Linyola `[1].de` guanya candidats -1,80/-0,20 de l'annex (CAND igual).
- Taules **144 / 28 / 6 / 19 / 0**; escalars **118 / 23 / 5 / 1 / 0**: idèntics a l1.

### Latència / cost
1,09 USD (subscripció), 5,3 min de rellotge; 0 USD la resta.

### Limitacions conegudes
- Els nivells per punt de l'annex DPSH (banda de color) entren com a candidats de segona fila; no s'usen encara per a la
  `a` per punt del nivell 1 quan el tall no la dona (Vilanova no té aquesta columna llegida: caldria re-llegir el seu annex
  amb la v1.9 per saber si hi és). Possible peça futura: «banda de color de l'annex DPSH = transició per punt» com a font
  explícita (l'or d'Alcoletge ho fa).
- La «N=R» del tall continua a les notes del document (fil obert de (nit, 7)).

### GO/NO-GO
- ✅ v1.9 validada sobre el cas que la va motivar; ✅ 0 regressions de veredicte, 3 cel·les amb millor contingut; tests.
- ⏳ Suite sencera: a la sessió.

### Següents passos
1.6 T2. Referència per a la propera reconsolidació: `_reconsolida-2026-09-05-v19`.

*Fi entrada 2026-09-05 (nit, 8). Un document més (1,09 USD): la regla funciona i el lector veu colors que abans no mirava.*

## 2026-09-06 — Peça 1.6 T2: la passada LLM de conflictes s'apaga (defecte `python`) després de codificar en Python les dues regles que aplicava; escalars 118 → 119 OK, conflictes A-vs-A 7 → 3, cost 0

### Context
El handoff del 05 (23:15) deia que la passada `claude -p --consolida --only-fields` «no ha canviat cap valor» (9 de 9 cel·les
iguals) i demanava només decidir el defecte. En obrir la sessió s'ha repetit la comprovació de debò (consolidació Python
SENSE fusionar la `_consolida_only.json` cachejada, que la v19 ja portava dins: la comparació d'ahir era tautològica, la trampa
que el mateix handoff avisava): la passada SÍ que canviava l'estat de 3 cel·les d'escalars, totes de `candidats` a `segur` i
totes correctes contra l'or — Castellar `utm_x`/`utm_y` (423167/4609608) i Rubí `lab_sample_id` («SPT-1»). En mode `python`
el marcador queia a **115 OK (78 %) / 26 CAND**, sota el llindar del 80 %. Cost de la passada, de la telemetria: 205-264 s i
0,94-1,08 USD per projecte, Tulipa 523 s i 1,95 USD, un primer intent penjat (Vilanova, 292 s, rc=1). El Josep ha triat
l'opció 1: codificar primer les dues regles, després apagar la passada.

### Decisions arquitectòniques clau
1. **`utm_x`/`utm_y`: `COORDENADES.txt` mana (precedència per camp, `_FIELD_PRECEDENCE`, nivell únic `coordenades_gps`).**
   És la regla Pas 3 que el propi senyal Python ja declarava («UTM de l'informe = P-1 de COORDENADES.txt»). El caixetí de
   l'annex de sondeig de Castellar (423182/4609623) és exactament l'entrada S-1 del mateix fitxer: no contradiu P-1, és un
   altre punt. `_annotate_utm_other_points` ho anota a `altres` («= punt S-1 de COORDENADES.txt (…), no P-1: corroboració»,
   ±1 m sobre l'eix del camp). **Alternativa rebutjada:** descartar només els valors que coincideixin amb un altre punt (els
   dos eixos) — més codi per al mateix resultat, i el criteri és «el fitxer de camp mana», no «coincideix per casualitat»;
   la nota conserva l'explicació. Sense el fitxer, els lectors competeixen com sempre (test).
2. **`lab_sample_id`: GTL > annexos de l'Eva (sondeig, DPSH); comanda i full manuscrit fora de la llista.** Evidència als
   4 signats amb GTL: Castellar «MA-1 (S1)» = GTL «MA1 S1» (NO l'annex «SPT-1»), Bell-lloc «SPT1 S1» = GTL, Rubí i Linyola
   «SPT-1 (P3)» = GTL «SPT1 P3». La regla del skill (Pas 3: «l'annex de l'Eva mana per l'etiqueta») i la resposta de l'LLM
   (annex > GTL, candidats amb «SPT-1» primer a Castellar) contradiuen el signat de Castellar. El «P3» del manuscrit («Assaig
   de referència») és el PUNT, no l'etiqueta: fora de la llista, corrobora i no bloqueja (era l'únic bloquejador de Rubí).
   **Alternativa rebutjada:** la comanda com a tercer nivell, com a `lab_depth` (F1) — sense GTL ni annex (Alcoletge,
   Vilanova, Anciles) la cel·la pujaria a `segur` des de la comanda sola i els tres ors són `candidats`: el comparador ho
   marca ALERTA «prod puja a segur». Es queden en candidats, com l'or. **Pregunta 12 a l'Eva continua oberta** (tipus de
   mostra SPT/MA a Castellar): si l'annex ha de manar, s'inverteixen els dos nivells (una línia).
3. **Defecte del runner `G3DT_LECTURA_CONSOLIDA=python`** (`runner._load_config`; el mode invàlid també hi cau). `auto` i
   `llm` continuen disponibles per variable d'entorn per a mesures. Efecte per a l'Eva: 3-5 min menys per projecte i un
   punt de fallada menys; els conflictes que quedin es veuen com a `candidats` amb tots els candidats, que és exactament
   el que l'LLM tornava per a `street_address`.
4. **El script de mesura fa el mateix que el runner:** `reconsolida_mesura.py` ja NO fusiona la `_consolida_only.json`
   cachejada; `--amb-llm` ho fa (les mesures fins a `-v19` la porten dins, `llm_only_fields: True`).
5. **No fet, a posta:** reordenar els clústers per nivell de precedència (si dos caixetins coincidissin en S-1 i
   superessin en recompte el fitxer, P-1 no manaria). Cap cas al corpus; queda com a limitació apuntada, no com a codi.

### Implementació
- `automation/lectura/consolidate.py`: `_FIELD_PRECEDENCE` (+3 entrades amb el racional), `_annotate_utm_other_points`
  (cridada a la branca `segur` de `decide`). ~40 línies.
- `automation/lectura/runner.py`: defecte `python` + comentari (5 línies).
- `docs/wizard-headless/mesures/reconsolida_mesura.py`: `--amb-llm`, docstring.
- Tests: `test_T2_utm_coordenades_p1_wins_over_annex_caixeti_and_notes_the_other_point`,
  `test_T2_lab_sample_id_gtl_wins_over_eva_annex_and_manuscript_reference_test`; runner
  `test_default_consolida_mode_is_python_no_llm_pass` (nou) i `test_invalid_consolida_mode_falls_back_to_python` (rebatejat);
  2 assercions del test sintètic (`test_synthetic_project_contract_clean_and_fields`) codificaven la regla antiga
  («annex SPT-1 vs GTL MA1 S1 → candidats»; «P-1 vs S-1 → candidats») i s'han girat al comportament nou.

### Validació empírica (reconsolidació dels 7, `_reconsolida-2026-09-06-t2` vs `-v19`, SENSE fusió LLM)
- **2 cel·les canvien, cap regressió:** Castellar `lab_sample_id` candidats «SPT-1» → **segur «MA1 S1»** (CAND → OK; or
  «MA-1 (S1)»); Rubí `lab_sample_id` segur «SPT-1» (LLM) → segur «SPT1 P3» (GTL; OK igual). Castellar `utm_x`/`utm_y`
  conserven `segur` sense l'LLM.
- Escalars **118/23/5/1/0 → 119 OK (81 %) / 22 CAND (15 %) / 5 ALERTA / 1 blanc / 0 ERR**; taules **144/28/6/19/0**
  idèntiques. Sense les regles, en `python`: 115/26/5/1/0 (mesurat al scratch, no versionat).
- Conflictes A-vs-A: Castellar 4 → 1, Rubí 1 → 0, Bell-lloc 1, Vilanova 1 (els tres que queden són `street_address`);
  total 7 → 3. Ni tan sols en mode `auto` es cridaria l'LLM a Rubí.

### Tests
Consolidador 163 verds (+2); runner +1. Suite sencera: **31 vermells / 2094 verds / 5 omesos**, noms IDÈNTICS a
`suite-vermells-esperats.txt` (234 s).

### Latència / cost
0 USD (cap lectura). Per projecte nou de l'Eva: −205…−264 s (−523 s a Tulipa) i −1 USD de subscripció.

### Limitacions conegudes
- La precedència filtra qui bloqueja, no qui és primer: si el clúster de P-1 no fos el primer per recompte, no manaria
  (decisió 5). Cap cas al corpus.
- `_annotate_utm_other_points` compara un sol eix a ±1 m; el camp `utm_x` no sap si `utm_y` coincideix també.
- `street_address` amb dues fonts A discrepants (Castellar 18A vs 18A-18B-20; Bell-lloc dues vies de cantonada; Vilanova
  amb/sense número) es queda en `candidats`: l'LLM tampoc ho resolia (tornava candidats). És l'entrada de la via A
  d'adreces (`docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md`), no d'aquesta peça.
- Sense GTL ni annex, `lab_sample_id` es queda en candidats (Alcoletge, Vilanova, Anciles = or).

### GO/NO-GO
- ✅ Les dues regles reprodueixen (i milloren) el que feia la passada LLM: +1 OK, 0 regressions, taules intactes.
- ✅ Defecte `python`, tests del defecte i del mode invàlid; ✅ suite idèntica.
- ⏳ Commit (decisió del Josep). ⏳ Pregunta 12 (Eva) pot invertir els nivells de `lab_sample_id`.

### Següents passos
1.7 amb l'Eva (R4 CTE imprès, persona/despatx; preguntes 11-13) i bloc 2 (P0, P2a, P2b, M341 amb línia base abans de
codificar). Referència per a la propera reconsolidació: **`_reconsolida-2026-09-06-t2`**.

*Fi entrada 2026-09-06. T2: abans d'apagar una passada, mesurar-la de debò; les dues regles que valia la pena tenir ja són Python.*

## 2026-09-06 (tarda) — Bloc 2 obert: línia base de QUALITAT D'INFORME (3 projectes × 4 variants, cost 0) i peça P0 (columna «N» = N30 de l'SPT): 2 cel·les a MATCH, cap altra moguda

### Context
Bloc 1 tancat al matí (T2 = `676070b`). El pla del bloc 2 (`PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md`) exigeix la línia
base amb l'ALTRE harness abans de codificar: `scripts/compare_tables_vs_eva.py` (informe generat vs signat, 11 taules), no
el comparador de lectura (`compare_consolida.py`). L'única mesura d'informe existent era la de la Fase 8b (2026-08-26:
Castellar 78 %, Rubí 82 %, Bell-lloc 75 %) i la seva recepta no estava escrita enlloc en forma executable. S'ha reconstruït
(`_user_data_prev.json` + bloc `lectura_tables` de l'or de taules via `adapt_legacy` + `ReportGenerator.generate` +
comparador contra `_eva_truth/<slug>.json`) i s'ha guardat com a script: `docs/wizard-headless/mesures/mesura_informe.py`.
La rèplica quadra **exacta** (39·12·14 / 37·8·10 / 35·6·14): la recepta és la bona.

### Decisions arquitectòniques clau
1. **Quatre variants per informe, no una.** Els tres `_user_data_prev.json` porten `geomech_params` manuals (γ/c/φ/E de
   l'Eva, de l'abril): la mesura de la Fase 8b tenia les cel·les de càlcul TAPADES. Variants: `8b` (rèplica), `calc` (or de
   taules SENSE `geomech_params`: la columna que el bloc 2 ha de moure), `t2` (lectura real `_reconsolida-2026-09-06-t2`
   sense `geomech_params`: el que sortiria a producció amb la via A), `viab` (cap taula llegida: només Excel + visió + càlcul).
   **Alternativa rebutjada:** generar els 7 projectes via prefills del wizard (com `collect_readiness.py`): arrossega la via B
   sencera (Groq, xarxa, minuts) i és justament la unificació de semàntica que M341 ha de fer; avui, 3 projectes i prou.
2. **La línia base ja és la primera troballa del bloc 2:** P2a (Rubí «vestit de roca») **només es veu a `viab`** (7/7 cel·les
   de la taula geotècnica: nom «Gresos… (Nivell 2)», γ 2,20, c 1,00, φ 35°, E 500 contra 2,0/0,05/39°/450 signats). Amb
   lectura (`8b`/`calc`/`t2`), `_apply_lectura_soil_levels` posa la litologia llegida («Graves i sorres…») a
   `level.description` ABANS que el generador cridi `is_rock`, i els paràmetres surten de sòl granular: φ i γ coincideixen
   amb el signat i només queden Nb «52-R» (vs 47-R) i E 469 (vs 450). El pla deia «6 cel·les» sense dir amb quina font.
3. **P0: la font de la columna «N» són les files de la taula SPT/MA TAL COM S'IMPRIMEIXEN al mateix informe**
   (`context['spt_ma_tests']`: lectura via A si n'hi ha, fila única de la via B si no), no una lectura directa de
   `sondeig_extracted.json` com deia el pla. **Per què:** les dues taules del mateix informe han de dir el mateix número, i
   les files llegides són les que l'Eva ha validat al wizard. Amb la lectura directa, Bell-lloc imprimiria 58 a la taula
   SPT i 34 (DPSH) o el `n_spt` de la visió a la geotècnica.
4. **Assignació SPT → nivell: litologia primer, fondària després, un sol nivell, i si no «--» amb avís.** Evidència:
   Vilanova té dos SPT a la MATEIXA fondària (-0,80 a -1,40) a P-1 i P-3 que l'Eva posa a nivells diferents («Arcilla
   limosa…» → nivell 1 = 10; «Arena fina-media» → nivell 2 = 24): la fondària sola els posaria tots dos al nivell 1. Arrels de
   5 lletres dels mots de ≥ 4 (sense accents: `arcilla/arcillas`, `arenosa/arenosas`, `arena/arenas` coincideixen;
   `areniscas` no), llista curta d'arrels genèriques excloses (`nivel`, `matri`, `inter`, `color`…). Les mostres sense N30
   (MA, «--») no compten (Anciles: 6/--). Diversos SPT al mateix nivell: el primer, i avís si difereixen. `geomech_params.N`
   (override expert) continua manant. **Alternativa rebutjada:** fondària primer — reprodueix 6/7 signats però no Vilanova.
5. **La cel·la «Nb» no es toca** (P4: quines lectures entren a la mitjana; pregunta a l'Eva).

### Implementació
- `automation/spt_n_column.py` (nou, pur, 150 línies): `n30_display`, `parse_depth_range`, `lithology_overlap`,
  `assign_spt_n30(spt_rows, levels) -> ({level_number: «N»}, avisos)`.
- `automation/report_generator.py`: abans del bucle de la taula 9 es crida `assign_spt_n30(context['spt_ma_tests'],
  soil_levels)`; `n_display = geomech.get('N') or spt_n_by_level.get(level.level_number, NO_SPT)`. Els avisos van a
  `self.warnings` i al log. Res més del generador canvia.
- `docs/wizard-headless/mesures/mesura_informe.py` (nou, 290 línies): genera els `.docx` (a `~/g3dt-e2e/informes-mesura/<run>/`,
  fora del repositori: 7-10 MB cadascun), compara, i escriu `runs/<run>/<slug>/<variant>/_compare_informe.{txt,json}` +
  `_user_data_usat.json` + `_AGREGAT.md` (titulars, per taula, i la llista de cel·les no-MATCH de les taules del bloc 2).
- `tests/test_spt_n_column.py` (33 tests): els 7 signats com a fixtures (files SPT/MA → columna N esperada, amb les
  descripcions de la taula geotècnica I de la taula de nivells), més contorn (sense SPT → «--», empat de litologia →
  fondària, no assignable → avís i cap valor, valors diferents → primer + avís, fondàries numèriques de la via B, nivells
  com a objectes).

### Validació empírica
Línia base (codi intacte, `runs/2026-09-06-informe-bloc2-base`) → després de P0 (`runs/2026-09-06-informe-p0`), M · C · X → %:

| projecte | `8b` | `calc` | `t2` | `viab` |
|---|---|---|---|---|
| Castellar | 39·12·14 → 78 % ⇒ 40·12·13 → **80 %** | 42·13·10 → 85 % ⇒ 43·13·9 → **86 %** | 42·13·10 → 85 % ⇒ 43·13·9 → **86 %** | 29·10·26 → 60 % (igual) |
| Rubí | 37·8·10 → 82 % ⇒ 38·8·9 → **84 %** | 38·8·9 → 84 % ⇒ 39·8·8 → **85 %** | 39·7·9 → 84 % ⇒ 40·7·8 → **85 %** | 30·4·21 → 62 % (igual) |
| Bell-lloc | 35·6·14 → 75 % (igual) | 36·6·13 → 76 % (igual) | 35·6·14 → 75 % (igual) | 37·6·12 → 78 % (igual) |

Diff cel·la a cel·la dels 12 informes (`_compare_informe.txt` base vs p0): **només canvia la cel·la N de la taula geotècnica**,
cap altra taula ni cel·la:
- Castellar `8b`/`calc`/`t2`: «22» → «R» (MISMATCH → MATCH). `viab`: «22» → «--» (segueix MISMATCH: la via B no té cap SPT
  llegit a Castellar, `spt_results` buit; «--» és honest, «22» era el DPSH).
- Rubí `8b`/`calc`/`t2`: «43» → «40» (→ MATCH). `viab`: «43» → «36» (MISMATCH: el `spt_in_dpsh` de la visió suma 36 d'un
  registre 16/20/20/24; els dos trams centrals donen 40 = signat → criteri de suma de l'N30, pregunta 1 de
  `PREGUNTES-EVA-PENDENTS.md`, lectura, no P0).
- Bell-lloc totes: «34» → «58» (`t2`: «62»); signat **54**. Segueix MISMATCH però ara coincideix amb la fila SPT/MA del mateix
  informe (58 or / 62 lectura t2, també MISMATCH vs 54 des de la Fase 8b). El 54 no és cap suma del registre 24/34/28/30
  (pregunta 1, oberta des del 2026-08-24); 58 i 62 són dues sumes diferents del mateix registre (lectura).

### Tests
33 nous (`test_spt_n_column.py`), tots verds. Fitxers del generador (`test_adjacent_wiring`, `test_lectura_tables_report`):
77 verds. Suite sencera a fitxer: **31 vermells, noms idèntics a `suite-vermells-esperats.txt` / 2127 verds / 5 omesos**
(227 s). Cost de la sessió: 0 USD (cap lectura).

### Limitacions conegudes
- L'assignació multinivell (litologia → fondària) només està provada als tests: els 3 projectes generables són d'un sol
  nivell. Linyola, Alcoletge, Vilanova i Anciles no es poden generar fins a M341.
- Castellar `viab` queda «--» on el signat diu «R»: la via B no llegeix l'SPT del full manuscrit de Castellar. No és de P0.
- La narrativa (§3 de l'informe) no s'ha tocat; només la cel·la de la taula.
- Observació de pas (no tractada): Castellar sísmica «Tipus III / 1,60 / 1,6» vs «Tipus II / 1,15* / 1,3» — gruix i N20 del
  nivell únic (capa de 0,5 m + roca): territori de P2/P4.

### GO/NO-GO
- ✅ P0: la cel·la es mou només on toca, 0 regressions cel·la a cel·la als 12 informes, suite idèntica → GO.
- ✅ Línia base d'informe reproduïble amb un sol comandament; referència per al bloc 2: **`runs/2026-09-06-informe-p0`**.
- ⏳ P2a/P2b: NO-GO fins a decisió del Josep sobre la regla de tria d'estrat (vegeu Següents passos). Cap commit fet.

### Següents passos
1. **P2a + P2b com una sola peça** (la regla és la mateixa). Estat del codi: `foundation_depth_m` **ja és un camp del wizard**
   (`review.html:2766`, prefill 0,3 «default estandard») però NO arriba a `_select_bearing_layer_idx` (`report_data.py:468`
   hi passa el 0,8 fix), i la funció tria «el competent més profund» (itera del fons cap amunt): a Rubí, els gresos. Proposta
   a decidir: nivell portant = **el primer nivell competent que la sabata assoleix** a Df + encastament (0,2-0,4 m, la frase
   del Qa dels signats), mai més profund; Df del wizard, amb avís si és el prefill. Impacte: `bearing_idx` alimenta
   `_bearing_stratum_n20` → Nb → φ → Qa (cadena validada 6/7): cal mesurar Qa abans/després (no és a les 11 taules del
   comparador; `scripts/qa_hypothesis_tester.py` / `CRITERIS-CALCUL-EVA.md`).
2. M341 després (les 341 variables; desbloqueja els 4 projectes sense `_user_data_prev.json`).

*Fi entrada 2026-09-06 (tarda). Bloc 2: línia base d'informe amb les cel·les de càlcul destapades; P0 dona a la columna N l'SPT que li tocava.*

## 2026-09-06 (tarda, 2) — P2a+P2b implementades i MESURADES (Qa abans/després, 3 projectes × 4 variants): el nivell portant és el que la sabata assoleix a Df + 0,2 m; Rubí Qa 3,0 → 3,5 = signat, Castellar 3,0 = signat, Bell-lloc 2,5 → 1,5 (el forat és φ/E per criteri, P3, no la capa). Pendent de GO del Josep

### Context
Després de P0 (entrada anterior), el Josep ha demanat «mesurem Qa abans i després i analitzem». Qa no és a cap de les 11 taules
del comparador: s'ha afegit al script de mesura un bolcat de càlcul (`_calc.json` per variant: Df, nivell portant, N20/Nb del
nivell, γ/c/φ/E, Terzaghi complet) i una secció «Càlcul» a `_AGREGAT.md` amb el signat de `CRITERIS-CALCUL-EVA.md` §5. Abans
(referència `runs/2026-09-06-informe-p0`, codi de P0): Castellar Qa 3,00 (signat 3,0) amb roca; **Rubí 3,00 (signat 3,5)** amb
els gresos de 3,35 m com a portant (γ 2,2 / c 1,0 / φ 35 / E 500, topall roca); **Bell-lloc 2,50 (signat 3,0)** amb la capa
1,0-1,8 m (N20 34,3 → φ 37,0, c 0, uncapped 2,65).

### Decisions arquitectòniques clau
1. **Nivell portant = el primer competent que la sabata ASSOLEIX a Df + 0,2 m (encastament mínim), mai més profund.**
   `bicapa.select_bearing_layer` ja feia exactament això (de dalt a baix; salta les capes que acaben per sobre de Df, el
   rebliment i el massa fluix); `_select_bearing_layer_idx` la cridava amb les capes INVERTIDES («el competent més profund»)
   i un Df fix de 0,8. Ara: capes en ordre, `Df = foundation_depth_m` del wizard (`foundation_depth_from_user_data`: «1,0»,
   «0.3 m», 0 → defecte), llindar `round(Df + 0,2, 3)` (1,4 + 0,2 = 1,5999… trencava el ≤). Evidència: la frase del Qa dels 7
   signats — Bell-lloc, Rubí, Castellar i Vilanova al primer nivell («un cop sanejat el tram superficial»; Rubí «encastada entre
   30-40 cm»); Linyola i Anciles al segon amb POUS («encastats 20-40 cm en els materials del segon nivell sanejat»); Alcoletge al
   segon (rebliment). **Alternativa rebutjada:** «competent més profund» (el que hi havia): 5/7 per casualitat (Rubí i Vilanova
   malament), i a Bell-lloc encertava el Qa amb lectures de la zona de rebuig que no són les de la sabata.
2. **Quan la fonamentació baixa a un segon nivell (pous), és una decisió de l'Eva que entra pel wizard.** Amb el prefill 0,3,
   Linyola i Anciles es queden al primer nivell (test explícit): cap regla sense Df pot encertar els 7, perquè «sabates vs pous»
   no és a les dades de camp. `foundation_depth_m` JA és al wizard; ara arriba al càlcul (generador i prefills: mateix Df a
   `_bearing_stratum_n20`, `_select_bearing_layer_idx` i `_generate_soil_levels`). Sense Df: 0,8 (defecte històric de Terzaghi) i
   avís al log. Pendent (P2b, UI): fer visible al wizard «nivell portant triat: … amb Df = …» i avisar quan Df és el prefill.
3. **El col·lapse a un nivell pren el nivell portant, no la capa més profunda** (`_collapse_to_single`): descripció, tipus i N20
   (amb límit superior quan el portant no és l'última capa, mateix criteri que `_bearing_stratum_n20`). Rubí deixa d'anar
   «vestit de roca» també a la via B.
4. **Els `soil_types` del wizard són PER NIVELL DE L'INFORME, no per capa del sondeig** (`_bearing_soil_type`). Trobat a la
   primera mesura «després»: Bell-lloc té `soil_types = ["limo", "grava"]` (dos nivells de l'abril: cobertura + graves) i dues
   capes de sondeig (graves / graves); amb el portant a l'índex 0, `soil_types[0]` = «limo» s'aplicava a les graves i Qa queia a
   2,0. Ara la llista només s'aplica si té tants elements com nivells generats (llavors, el del nivell que conté el sostre de la
   capa portant); si no, detecció per la descripció. Els nivells es generen ABANS dels paràmetres per poder-ho fer.
   **Limitació apuntada:** la branca multigrup de `_generate_soil_levels` (`soil_types[idxs[-1]]`) encara indexa per capa.
5. **Paraules clau de cobertura en català** a `bicapa._WEAK_TOP_KEYWORDS` («terreny vegetal», «sòls superficials»…): la
   cobertura de Castellar (0-0,5) ja se saltava per fondària (0,3 + 0,2 = 0,5), les de l'or ara també pel nom.

### Implementació
- `automation/report_data.py`: `EMBEDMENT_MIN_M`, `DEFAULT_FOUNDATION_DEPTH_M`, `foundation_depth_from_user_data`,
  `_bearing_soil_type`; `_select_bearing_layer_idx` (ordre directe, llindar), `_bearing_stratum_n20` i `_generate_soil_levels`
  (paràmetre `foundation_depth`), `_collapse_to_single` (portant), `build_report_data` (Df, nivells abans dels paràmetres,
  camps nous a `ReportData`: `bearing_layer_idx`, `bearing_layer_description`, `foundation_depth_used_m`,
  `foundation_depth_is_default`; `to_dict`/`from_dict` no es toquen).
- `automation/report_generator.py` (Df a `_bearing_stratum_n20` de Terzaghi-Peck), `web/wizard_service.py` (Df dels prefills
  a les dues crides), `automation/bicapa.py` (paraules clau).
- `docs/wizard-headless/mesures/mesura_informe.py`: `_calc.json` + secció «Càlcul» (`SIGNAT_CALC`).
- Tests: `tests/test_bearing_layer_rule.py` (19: Df del wizard, els 7 signats amb la Df que cada informe implica, col·lapse,
  N20 del portant, defecte, tot per sobre de Df); adaptats 3 que fixaven «el més profund» (`test_bicapa_wire` ×2 amb el nou
  criteri i els dos Df, `test_soil_levels_grouping::test_generate_override_collapses_to_one` amb Df 4,5) i 1 (`…single_level…`).

### Validació empírica
Variant `calc` (or de taules, sense `geomech_params`), `runs/2026-09-06-informe-p0` → `runs/2026-09-06-informe-p2`:

| | Castellar (signat) | Rubí (signat) | Bell-lloc (signat) |
|---|---|---|---|
| nivell portant | roca 0,5-1,2 = | gresos 3,35-4,55 → **graves 0-3,35** | graves 1,0-1,8 → **graves carbonatades 0-1,0** |
| N20 → Nb | 22,6 → 27,2 = (17-R) | 43,3 → 52,2 ⇒ 34,8 → **41,9** (47-R) | 34,3 → 41,3 ⇒ 18,8 → **22,6** (25-R) |
| φ / γ / c / E | 35 / 2,2 / 1,0 / 500 = (35 / 2,2 / 1,0 / >500) | 35 / 2,2 / 1,0 / 500 ⇒ **37 / 2,0 / 0,0 / 469** (39 / 2,0 / 0,05 / 450) | 37 / 2,0 / 0,0 / 469 ⇒ **33 / 2,0 / 0,0 / 114** (38 / 2,0 / 0,0 / 650) |
| **Qa** | 3,00 = ✅ (3,0) | 3,00 ⇒ **3,50 ✅** (3,5; uncapped 5,30, topall granular dens) | 2,50 ⇒ **1,50 ❌** (3,0; uncapped 1,47, Terzaghi) |
| assentament | 2,80 = (<1,0) | 1,50 ⇒ 1,70 (1,50) | 1,70 ⇒ **1,00** (<1,20) |

Taules (M·C·X → %), p0 ⇒ p2, cel·la a cel·la: Castellar idèntic a les 4 variants. Rubí `calc` 39·8·8 (85 %) ⇒ 38·8·9 (84 %):
l'única cel·la que canvia d'estat és φ «39°» → «37°» (abans coincidia amb el signat per casualitat: era la correlació granular
aplicada a les lectures de la zona de roca, N20 43); Nb «52-R» → «42-R» (segueix X, més a prop de 47). Rubí `viab` 62 % ⇒
**69 %** (nom, γ, litologia de nivells i permeabilitat deixen de ser gresos). Bell-lloc totes les variants −2 pp: sísmica «Tipus
II / 1,3» → «Tipus III / 1,6» (N20 18,8 < 30) i φ/E canvien de valor però ja eren X (37→33 vs 38; 469→114 vs 650); Nb «41» →
«23» (X, però a 2 dels 25-R signats). Cap altra taula es mou.

**Anàlisi.** (1) Rubí: la regla fa exactament el que diu el signat i la cadena Qa (topalls) ho recull: 3,5. (2) Castellar:
insensible (la cobertura se salta per fondària i per nom). (3) Bell-lloc: la capa és la bona (l'Nb passa de 41 a 23 contra els
25-R signats, i l'assentament de 1,70 a 1,00 contra «<1,20»), però φ 33 i E 114 surten de les correlacions amb N20 18,8 on
l'Eva escriu 38° i 650 per **criteri litològic** (graves denses amb rebuig a 1,0-1,6 m; «carbonatades» → E amunt): és P3,
i els informes no ho descriuen (repàs R negatiu, pregunta a l'Eva imprescindible). El 2,5 d'abans era un artefacte: lectures de
la zona de rebuig (N20 34) inflaven φ a 37. (4) Comprovació P4 només per a l'anàlisi (sense tocar codi): comptar les lectures
des de la base de la sabata en lloc del sostre de la capa mou Rubí Nb 41,9 → 44,3 (P-3 sol: 51,6) i no mou Bell-lloc (22,6)
ni Castellar (27,2; el 17-R signat no es reprodueix amb cap subconjunt: P-1 20,3 / P-4 19,2 / P-3 46 amb una sola lectura).

### Tests
19 nous (`test_bearing_layer_rule.py`) + 4 adaptats; blocs dirigits (`test_bearing_layer_rule`, `test_bicapa`, `test_bicapa_wire`,
`test_soil_levels_grouping`, `test_spt_n_column`) 92 verds. Suite sencera a fitxer: **31 vermells, noms idèntics a
`suite-vermells-esperats.txt` / 2146 verds / 5 omesos** (229 s; `test_bell_lloc_bearing_idx_and_n20` ja hi era, deriva del fixture). Cost: 0 USD.

### Limitacions conegudes
- Linyola i Anciles només encerten el segon nivell si l'Eva posa la Df dels pous al wizard: sense UI que ho faci visible, el
  prefill 0,3 els deixa al primer nivell (abans, «el més profund» els encertava per casualitat i fallava Rubí i Vilanova).
- La branca multigrup de `_generate_soil_levels` encara indexa `soil_types` per capa (cap dels 3 generables hi passa).
- Bell-lloc: Qa 1,5 fins a P3 (φ/E per criteri) — el número que ara surt és el de les correlacions amb les lectures de la
  sabata, no el de l'Eva. Si el GO és «regla sí», cal dir-ho a l'Eva o prioritzar P3 de seguida.
- 3 projectes mesurables; Vilanova (el segon testimoni de la regla) només al test unitari.

### GO/NO-GO
- ✅ La regla reprodueix el nivell portant declarat als 7 signats quan Df és la de l'informe (tests) i Qa de Rubí i Castellar.
- ⏳ **Decisió del Josep:** (a) mantenir la regla i passar a P3 (φ/E per criteris, candidats amb procedència; Bell-lloc és el
  cas) — recomanat, perquè el 2,5 d'abans no era encert sinó soroll de lectures; o (b) desactivar-la fins a P3. Cap commit.

### Següents passos
P3 (E i φ per criteri: preguntes a l'Eva ja redactades a `CALCUL-E-MODUL-DEFORMACIO.md` §8 + pregunta 6); P2b UI (nivell
portant i Df visibles al wizard); M341. Referència viva d'informe: **`runs/2026-09-06-informe-p2`** (si GO) o `-p0` (si no).

*Fi entrada 2026-09-06 (tarda, 2). El nivell portant és on recolza la sabata; el que queda a Bell-lloc és criteri de φ/E, no de capa.*

## 2026-09-06 (tarda, 3) — GO del Josep a la regla del nivell portant; P3 FETA: γ/c/φ/E i tipus sísmic per CRITERI com a candidats amb procedència (`automation/geotech_criteria.py`); Qa dels 3 generables = signat (3,0 / 3,5 / 3,0); 35/44 cel·les signades exactes i les 9 restants com a candidat

### Context
El Josep ha donat el GO a la regla del nivell portant (entrada anterior) i ha demanat passar a P3. El pla deia: substituir
el punt únic «E_min + 10 %» pel criteri real dels nivells signats, i fer-ho **com a candidats amb procedència, no com a
fórmula nova**, perquè l'E és el paràmetre que l'Eva declara de judici i el repàs R no va trobar cap frase que el
justifiqués. La mesura d'avui (tarda, 2) havia deixat Bell-lloc a Qa 1,5 amb la capa bona: φ 33 / E 114 per correlació on
l'Eva signa 38 / 650. Amb les 11 files signades de la taula geotècnica (7 informes) i les fonts que ella declara (Crespo
per c/φ; CTE D.23 «agafa la taula, ja ho ajustarem» per E), el criteri es podia escriure sense preguntar-li res més que
els punts on els seus propis informes no coincideixen entre ells.

### Decisions arquitectòniques clau
1. **Un mòdul pur de criteris que retorna candidats ordenats, el primer és el defecte, cadascun amb la font**
   (`geotech_by_criteria(nb, n20, soil_type, description, refusal) → GeotechCriteria`). Els tres punts que abans
   calculaven γ/c/φ/E per separat (paràmetres de Qa a `report_data`, files de la taula al generador, prefills del wizard) ara
   criden el mateix mòdul; l'override expert (`geomech_params`) mana per camp. **Alternativa rebutjada:** la «v2» de
   febrer (escalar dins de la banda D.23): empitjora els fluixos (N=5 → 4) i no és un criteri sinó un refinament de fórmula.
2. **El règim el fixen Nb i el REBUIG, i el rebuig es mira al nivell de l'informe, no a la capa.** El «-R» de la cel·la Nb
   signada pertany al nivell («25-R» a Bell-lloc amb la sabata a 0,3 sobre graves 0-1,0 i el rebuig a 1,0-1,6, mateix nivell
   geològic). Amb el rebuig només dins de la capa portant, Bell-lloc quedava «mitjà» (φ 33, E 100, Qa 1,5). Rebuig en un
   nivell granular ⇒ compacitat densa encara que la mitjana pre-rebuig sigui baixa (`_level_has_refusal`,
   `_report_level_for_layer`; el generador usa el mateix rebuig per a la «-R» de la cel·la Nb: Bell-lloc «23» → «23-R»).
3. **φ per litologia amb Crespo com a font declarada (7/7 informes), no la correlació CTE 4.1 + Schmertmann.** Graves denses
   (rebuig o Nb ≥ 31) 38, 39 a la meitat alta de la banda (Nb ≥ 41): Bell-lloc 38 (25-R), Rubí 39 (47-R), Anciles 2 38
   (15-R); transicionals (llims, sorres/argiles amb l'altre component) 28 (àncora Tabla 11.2 «muy floja», memòria
   `project_crespo_tabla_11_2`); argila llimosa 25 (Vilanova 1; nota de Crespo −3°); roca 35 bretxes / 30 lutites / 34
   gresos. **11/11 φ signats exactes.** La correlació anterior queda com a candidat.
4. **E: taula D.23 banda baixa als trams mitjos, mínim 50, rebuig granular ⇒ banda «medios», roca «>500», arrodoniment a
   10/50.** L'ajust litològic ↑ per «carbonatades» (Bell-lloc 650) és **candidat, no defecte**: Rubí també és carbonatat i
   signa 450 (pregunta 6b, ja pendent). Els valors de roca per litologia (lutites >400 / >800, gresos 550, bolos >350)
   són candidats amb el projecte signat com a font: judici per projecte, com diu el pla. Cap valor s'inventa.
5. **Tipus de terreny sísmic pel règim, no pels llindars d'N20:** roca i granular dens → Tipus II (C 1,3), granular
   mitjà → III, cohesius/transicionals no densos i fluixos → IV (Linyola 1 amb Nb 13 signa IV). Castellar (roca, N20 22)
   sortia III. Mateix criteri de règim que φ i E: per això va dins de P3.
6. **c i γ com fins ara (9/11 cadascun)** amb candidats on l'Eva divergeix (c 0,05 granular carbonatat = Rubí; 0,50 roca
   tova = Vilanova 2; γ 2,00 roca alterada = Alcoletge 2; γ 1,80 rebliment ara defecte per la senyal «rebliment»).
7. **Els candidats arriben al wizard pel mecanisme que ja hi ha** (`_alternatives` → badge «+N» amb desplegable que
   aplica el valor): cap canvi d'UI. Les notes `_calc_*` porten règim, font del defecte i candidats.

### Implementació
- `automation/geotech_criteria.py` (nou, 330 línies): `lith_flags`, `round_E`, `regime_for`, `seismic_type_for`,
  `rock_kind`, `d23_band_E`, `geotech_by_criteria`, `alternatives_for_wizard`; dataclasses `Candidate`, `GeotechCriteria`.
- `automation/report_data.py`: `_report_level_for_layer`, `_level_has_refusal`, `_bearing_stratum_has_refusal`; el bloc de
  paràmetres crida el criteri; `ReportData.geotech_criteria` (dict) per traçabilitat.
- `automation/report_generator.py`: criteris per nivell calculats un cop (taula sísmica i geotècnica); cel·la E amb
  `E_display` («>500»); «-R» de la cel·la Nb pel mateix rebuig de nivell.
- `web/wizard_service.py`: prefills `geomech_*` del criteri amb la seva font; `_alternatives` per als candidats;
  notes `_calc_*` i `_calc_regime`.
- Tests: `tests/test_geotech_criteria.py` (66: les 11 files signades × 4 cel·les amb `KNOWN_MISSES` explícit —
  «o el defecte encerta, o el signat és candidat amb font»; règim; sísmica; arrodoniment; sòl mínim; rebuig ⇒ medios;
  «>» en roca; candidat carbonatades = punt 40 % de la banda; φ per litologia; senyals; alternatives del wizard).

### Validació empírica
Variant `calc`, `runs/2026-09-06-informe-p2` (després del nivell portant) ⇒ `runs/2026-09-06-informe-p3`:

| | Castellar (signat) | Rubí (signat) | Bell-lloc (signat) |
|---|---|---|---|
| φ / γ / c / E | 35 / 2,2 / 1,0 / «500» ⇒ 35 / 2,2 / 1,0 / **«>500»** (35 / 2,2 / 1,0 / >500) | 37 / 2,0 / 0,0 / 469 ⇒ **39** / 2,0 / 0,0 / **450** (39 / 2,0 / 0,05 / 450) | 33 / 2,0 / 0,0 / 114 ⇒ **38** / 2,0 / 0,0 / **450** (38 / 2,0 / 0,0 / 650) |
| Nb cel·la | 27-R (17-R) | 42-R (47-R) | 23 ⇒ **23-R** (25-R) |
| sísmica | III / 1,6 ⇒ **II / 1,3** (II / 1,3) | II / 1,3 = | III / 1,6 ⇒ **II / 1,3** (II / 1,3) |
| **Qa** | 3,00 = ✅ | 3,50 = ✅ (uncapped 7,00, topall) | 1,50 ⇒ **3,00 ✅** (uncapped 3,03, topall) |
| assentament | 2,80 (<1,0) | 1,70 (1,50) | 1,00 ⇒ 2,10 (<1,20) |

Titulars (M·C·X → %), p2 ⇒ p3: Castellar `calc` 43·13·9 (86 %) ⇒ **46·11·8 (88 %)**, `viab` 60 ⇒ 62 %; Rubí `calc` 38·8·9
(84 %) ⇒ **40·8·7 (87 %)**, `viab` 69 ⇒ 73 %; Bell-lloc `calc` 34·7·14 (75 %) ⇒ **37·6·12 (78 %)**, `viab` 76 ⇒ 80 %; `8b`
(amb els manuals de l'Eva) també puja per la sísmica i el «>». Cel·la a cel·la, només es mouen la taula geotècnica i la
sísmica: Castellar E «500»→«>500» (C→M), sísmica III→II i 1,6→1,3 (2 cel·les →M); Rubí φ 37→39 i E 469→450 (→M); Bell-lloc
φ 33→38 (→M), sísmica (2 →M), E 114→450 (X, més a prop de 650), Nb «23»→«23-R» (X, forma del signat). Cap altra cel·la.
Assentament de Bell-lloc: 1,00 ⇒ 2,10 perquè l'Es de Schmertmann segueix E (camí a part, «<1,20» signat): pendent.

Sobre les 11 files signades (test): **35/44 cel·les exactes** (φ 11/11, γ 10/11, c 9/11, E 5/11) i **les 9 restants tenen el
signat com a candidat amb font** (0 fora). Abans (correlacions): φ 3/11, E 1/11.

### Tests
66 nous (`test_geotech_criteria.py`); blocs dirigits (criteris, nivell portant, bicapa, grouping, columna N, Crespo, taules
de lectura, adjacents) **287 verds**. Suite sencera a fitxer: **31 vermells, noms idèntics a `suite-vermells-esperats.txt` /
2220 verds / 5 omesos** (266 s). Cost: 0 USD.

### Limitacions conegudes
- L'E de Bell-lloc (650) i els de roca per projecte (>400/>800/550/>350) són candidats, no defecte: l'Eva els tria al wizard
  («+N») o respon la pregunta 6b/14. El defecte imprimeix 450 / «>500».
- L'assentament (Schmertmann, Es=2,5×Nb) no s'ha tocat: Bell-lloc 2,10 vs «<1,20».
- El wizard no mostra encara `_calc_regime` (no hi ha element); els candidats sí (badge «+N» dels camps `geomech_*`).
- Només 3 projectes generables; Linyola, Alcoletge, Vilanova i Anciles queden al test unitari (M341).
- La cel·la Nb (P4: quines lectures) no es toca: Castellar 27-R vs 17-R, Rubí 42-R vs 47-R, Bell-lloc 23-R vs 25-R.

### GO/NO-GO
- ✅ P2a+P2b: GO del Josep (2026-09-06, tarda). ✅ P3: Qa 3/3 = signat, 0 regressions cel·la a cel·la, 287 verds dirigits.
- ⏳ GO del Josep sobre P3 i decisió de commit (tot el dia sense commit: P0, P2, P3, mesura).

### Següents passos
Pregunta 14 a l'Eva (criteris d'E per litologia: carbonatades, lutites, bolos, argiles; c granular carbonatat); P2b UI
(nivell portant i Df visibles); assentament vs E; M341. Referència viva d'informe: **`runs/2026-09-06-informe-p3`**.

*Fi entrada 2026-09-06 (tarda, 3). P3: els paràmetres per criteri, amb la font a la vista; el Qa dels tres signats, exacte.*
## 2026-09-06 (vespre) — Pendents de lectura TANCATS (or d'Alcoletge, D4b material-vs-interval), P2b UI, assentament per CRITERI (frase i Es amb candidats), i M341 v1: la mesura COMPLETA dels 7 projectes generats només amb la lectura

### Context

Diumenge, l'Eva descansa (cap pregunta fins dilluns). El Josep: «seguim amb la resta (2, 3 i 4 suggerits), i els dos pendents de
l'STATUS». Punt de partida: `a6eb0b8` (bloc 2 commitejat), reproductibilitat verificada (`runs/2026-09-06-informe-repro` = `-p3`
cel·la a cel·la, Qa 3,0 / 3,5 / 3,0). Cinc peces, totes a cost 0 (cap crida LLM), en aquest ordre: (A) or d'Alcoletge, (B) D4b,
(C) P2b UI, (D) assentament, (E) M341. Tot **sense commit** (partició proposada al final).

### Decisions arquitectòniques clau

1. **(A) L'or d'Alcoletge `[1].a` s'alinea amb els altres quatre ors i amb el signat** (`candidats` «fins al fons d'investigació
   (rebuig DPSH: -1,60/-1,30/-1,69 m per punt)», dialecte `valor/font/cita` del fitxer, `note` de revisió). **Why:** el signat usa
   el fons (gruix sísmic 0,29* → −1,69 = rebuig P-3), Linyola és `segur` amb la mateixa frase i Vilanova/Rubí/Anciles `candidats`;
   no hi havia cap criteri que separés Alcoletge (decisió 7 del 09-05). *Alternativa (b) rebutjada:* comptar l'ALERTA com a «OK per
   veritat» deixava una excepció permanent al comparador per un or incoherent. És l'única edició de l'or del dia i es fa sobre un
   fitxer que ja tenia la regla escrita en text («el substrat no es perfora»).

2. **(B) D4b — «material vs interval» al consolidador, els dos candidats i el del material PRIMER.** `_sample_lithology`
   (la fila de `spt_ma_tests` del mateix punt amb tram que solapa `lab_depth`: GTL «Lutita gresosa»), `_lith_class` (vocabulari
   de prefixos ca/es, NOMÉS la primera litologia del text: «Lutita gresosa» → lutita, «Llims argilosos i sorrencs» → llim; els
   adjectius no compten) i `_material_level` (l'únic nivell de la mateixa classe, i només si la geometria el dona «fora»). Al
   nivell del material: [Sí pel material, No per interval]; al de l'interval: [No pel material, Sí per interval]. **Why:** és
   exactament l'ordre de l'or de Linyola i el que l'Eva fa (sulfats al 2n nivell). *Alternatives rebutjades:* (i) «sempre els dos
   quan la mostra és a < 0,3 m del contacte»: afegeix candidats sense cap document que ho digui; (ii) comparar litologies per
   contenció de cadenes (`_same_lithology`): «Lutita» ⊄ «Lutites» — calia classe, no substring. Límits: dos nivells de la mateixa
   classe → ambigu → l'interval mana sol; sense geometria al punt no es deriva res (com D4); a cavall no es toca.
   **Comparador v5:** `mostra_del_nivell` es compara com a booleà (`yes_no`: «No (pel material)» = False). *Why:* els 2 CAUTELA de
   Linyola eren format (booleà vs text), no sistema (mateix cas que els 18 falsos de la v4).

3. **(C) P2b UI sense canviar l'arquitectura del wizard:** nova nota `_calc_bearing` (text de `wizard_service.bearing_note`)
   sota «Profunditat fonamentacio» («Nivell portant: 1/2 «Graves carbonatades» · Df = 0,30 m (primer competent que la sabata
   assoleix a Df + 0,2 m)»), en ambre amb «⚠ Df per defecte» quan la font del prefill és `default`/`estandard`; `_calc_regime`
   (que ja s'emetia i no es mostrava) apareix sota φ. **Why:** el mateix mecanisme de les notes `_calc_*` (cap element nou de
   formulari, cap canvi d'API); la Df és l'única entrada del càlcul que només l'Eva coneix (pous de Linyola/Anciles).

4. **(D) Assentament per CRITERI, no per fórmula (`automation/settlement_criteria.py`), mateix patró que `geotech_criteria`.**
   Els criteris que els 7 signats DESCRIUEN: (i) **frase per règim del nivell portant**: granular → valor («iguals o inferiors a
   1.50 cm, immediats… granular»), roca/cohesiu → genèrica «menyspreables o bé inferiors a 1.0 cm» (Castellar, Linyola L2,
   Alcoletge L2, Vilanova); (ii) **< 1,0 cm → genèrica**; (iii) arrodoniment a 0,1, dos decimals; (iv) topall de servei 2,54 cm
   → avís. (v) **Es**: l'Eva escriu «2,5 × colpeig estàtic, de l'Nspt» i diu que l'agafa «com a criteri»; cap fórmula reprodueix
   els tres signats (abril: 12 hipòtesis) → **defecte + candidats amb procedència**: 2,5×N SPT del nivell (columna «N» de P0) →
   2,5×Nb del nivell → E del criteri; «Es assentament» del wizard mana; badge «+N». **Why el defecte és l'SPT:** és l'N que el text
   signat anomena (Bell-lloc N 54 → 135 → 1,16 → «1,20» exacte); Rubí però encaixa amb Nb (47 → 1,52). Cap dels dos ordres encerta
   els dos: pregunta 15 a l'Eva. *Rebutjat:* fer que el defecte fos «el que encerta cada projecte» (max(N, Nb)): ad hoc, 2 punts.
   **La plantilla tenia la frase FIXA** («…iguals o inferiors a {{ settlement }} cm, immediats… granular»): ara imprimeix
   `{{ settlement_sentence }}` (un sol node `w:t`, reemplaçat amb `zipfile`; `feedback_check_signed_phrasing_before_template_change`:
   les tres formes signades es van citar abans, la forma «iguals o inferiors» és la de Rubí i la de la plantilla, Bell-lloc diu
   «inferiors»). El càlcul es fa al `build_context` (després de P0, perquè l'N SPT del nivell portant ve de `assign_spt_n30`) i
   sobreescriu el `settlement_cm`/`Es_used` del càlcul inicial (2,5×Nb global). `ReportData.bearing_level_number` nou (el nivell
   de l'INFORME que fa de portant) per no re-derivar-lo. Trobada: els `Es_settlement` dels `user_data` d'abril (76/104/56) són el
   2,5×Nb global desat pel wizard, no judici de l'Eva → el harness els treu a `calc`/`t2`/`viab`.

5. **(E) M341 v1 — la mesura completa, amb tres unificacions i cap veritat nova.** (i) **Veritat**: `eva_reference_values.json`
   (56-65 variables per projecte, nom de plantilla, extractor de referència sobre el signat: posicional + `intelligent_analysis`)
   per als escalars i la narrativa; `_eva_truth/<slug>.json` per a les 11 taules. (ii) **Camps**: el CONTEXT Jinja real
   (`_build_template_context`, capturat embolcallant `render_template`): `context[X]` vs la variable `X` del signat — sense
   re-extreure el `.docx` generat (l'extractor posicional només recupera ~35 de 65 i les 24 `intelligent_analysis` són d'una
   passada LLM d'un sol cop). (iii) **Semàntica**: `status_for` del comparador escalar (tolerància per variable) i el comparador
   de taules. **Variant `viaA`** = els 7 projectes generats NOMÉS amb la lectura (`_apply_lectura_overlay`, la mateixa
   superposició del wizard; `build_report_tables`; Excel DPSH; JSON de visió de `reference-material/` on n'hi ha) + **una
   assumpció**: la Df del signat (`DF_SIGNAT`: pous Linyola 1,7 / Anciles 2,9). **Why viaA i no el wizard headless:** és «el que
   el sistema faria sol» sense les correccions manuals de l'Eva; `t2` (3 projectes) mostra què aporten. Grups v1: A (lectura) /
   calc / narr / fix / resta per nom de variable (`GROUPS`).
   Correccions de mesura fetes pel camí: tipus numèrics dels UTM i la superfície (com fa el wizard en desar), la frase
   d'assentament comparada com a frase, apòstrof tipogràfic a `_norm_date`/`_norm_text` («1 d ‘octubre» = «1 d'octubre»),
   Fase 0 amb SmartScan nivell 1 (regex, cap LLM) als projectes sense `file_mapping.json` (Vilanova `ANEXOS/`, Anciles `ANEJOS/`:
   l'inventari antic només mira `ANNEXES/`). **Un bug real destapat i arreglat:** `_generate_soil_levels` (branca per capa)
   comparava `depth_to_m: None` (última capa oberta del segmentador DPSH) com a número → TypeError (Alcoletge); ara «fins al fons».

### Implementació

| Peça | Fitxers | Què |
|---|---|---|
| A | `docs/golden-read-taules/4001670 ALCOLETGE/_tables_decisions.json` | `rows[1].a`: `no_trobat` → `candidats` (1 candidat, `rule` reescrita, `note` de revisió, `sources_checked` intactes) |
| B | `automation/lectura/consolidate.py` (+~90 LOC: `_LITH_STEMS`, `_lith_class`, `_first_value`, `_sample_lithology`, `_material_level`, `_derive_sample_level` reescrita; capçalera D4b) · `docs/wizard-headless/fase0-acceptacio/compare_consolida.py` (`yes_no`, `close()` per `mostra_del_nivell`, docstring v5) | D4b + comparador v5 |
| C | `web/wizard_service.py` (`bearing_note`, `_calc_bearing`) · `templates/validation/review.html` (`calc-bearing`, `calc-regime`, `calcNoteKeys`) | P2b UI |
| D | `automation/settlement_criteria.py` (nou, ~150 LOC) · `automation/terzaghi_calculator.py` (5 camps nous a `BearingCapacityResult`, `format_settlement_for_report`) · `automation/report_data.py` (`bearing_level_number`) · `automation/report_generator.py` (bloc d'assentament al `build_context`, `settlement_sentence`, notes) · `web/wizard_service.py` (règim, N SPT del portant via `assign_spt_n30`, candidats `Es_settlement`, `_calc_settlement_regime`) · `templates/validation/review.html` (frase genèrica al recàlcul en viu, placeholder de l'Es) · `templates/g3dt-jinja-template.docx` (`{{ settlement_sentence }}`) · `docs/wizard-headless/mesures/mesura_informe.py` (`Es_settlement` fora a `calc`/`t2`/`viab`, columnes «imprès»/«Es», `_settle_cell`) · `docs/PREGUNTES-EVA-PENDENTS.md` (15) | assentament per criteri |
| E | `docs/wizard-headless/mesures/mesura_341.py` (nou, ~430 LOC) · `automation/report_data.py` (guarda `depth_to_m None`) · `automation/spt_n_column.py` (`_TALLY_RE`: «1/1/1/1» no és N30) · `scripts/compare_prefills_vs_eva.py` (apòstrof) | M341 v1 |

Cap dependència nova. `rtk proxy git diff --stat`: 19 fitxers, +437/−87 (sense els runs).

### Validació empírica

**Lectura (A+B), reconsolidació `_reconsolida-2026-09-06-pend` vs `-t2` (7 projectes, cost 0):** 1 cel·la canvia (Linyola
`soil_levels[0].mostra_del_nivell`: True → False primer), cap altra a cap projecte. Comparador sobre l'or: taules **144 → 147 OK /
28 → 26 CAND / 6 → 5 ALERTA / 19 blancs / 0 ERR** (Alcoletge ALERTA → OK; Linyola 2 CAUTELA → OK); escalars **idèntics 119 / 22 /
5 / 1 / 0 (81 %)**.

**Informe (D), `runs/2026-09-06-informe-assent` vs `-repro` (= `-p3`):** les 12 comparacions de les 11 taules **idèntiques cel·la a
cel·la**; el que canvia és la frase del §4 i el bolcat de càlcul:

| projecte | signat | `calc` abans | `calc` ara | Es ara |
|---|---|---|---|---|
| Castellar | «menyspreables o bé inferiors a 1.0 cm» | «inferiors a 2.80 cm, diferits» | **frase genèrica ✓** (roca) | 68 (2,5×Nb; sense SPT) |
| Rubí | «iguals o inferiors a 1.50 cm» | 1,70 | 1,80 (2,5×N SPT 40); Nb 47 → 1,52 | 100, 3 candidats |
| Bell-lloc | «inferiors a 1.20 cm» | 2,10 | 1,10 (`calc`, N 58) / 1,00 (`t2`, N 62); N 54 → 1,20 | 145 / 155 |

`runs/2026-09-06-informe-final` (després de TOTS els canvis, guarda inclosa) = `-assent` cel·la a cel·la i `_calc.json`.

**M341 v1, `runs/2026-09-06-m341` (7 projectes `viaA`, 3 `t2`; cost 0):**

| variant | escalars + narrativa (M · C · X · ND → %) | taules (M · C · X → %) |
|---|---|---|
| `viaA` (7) | **156 · 38 · 141 · 47 → 58 %** | **265 · 98 · 100 → 78 %** |
| `t2` (3) | 90 · 9 · 64 · 10 → 61 % | 123 · 24 · 28 → 84 % |

Per grup (`viaA`): **A (lectura) 69 %** (80/11/40/16), **calc 66 %** (57/5/32/2), **narrativa 30 %** (8/18/61/22), resta 65 %.
Per projecte (`viaA`, escalars / taules): Castellar 68 / 88, Rubí 60 / 89, Bell-lloc 68 / 82, Linyola 68 / 88, Alcoletge 52 / 73,
Vilanova 40 / 64, Anciles 40 / 74. Referència anterior: 59 % global del diagnòstic 2026-08-23 (prefills vs signat, 341 variables,
8 projectes) — no és la mateixa mètrica (prefills vs informe generat; 7 vs 8), però és el mateix ordre de magnitud: el que ha pujat
és la lectura (A 69 %) i les taules (78 %); la narrativa no s'ha tocat.

**Troballes de M341 (les que canvien el que fem després):**
1. **Sense sondeig, la geometria de nivells surt del segmentador DPSH, no de la taula de nivells llegida del tall.** Linyola
   (Df 1,7, pous): col·lapsa a UN nivell «Llims» 0-3,0 i el tracta per descripció buida → grava densa (φ 38, c 0, E 450) on el
   signat calcula amb les lutites (30 / 1,0 / >800). Alcoletge queia (bug de la capa oberta, arreglat). Vilanova: L1 «Arcilla
   limosa» detectada com a `grava` → c 0 → Qa 1,0 (signat 2,5 amb c 0,05, φ 28). La taula `soil_levels` de la via A (de/a per
   nivell, litologia) només s'usa per sobreescriure descripcions (Fase 8b). **→ P5: capes des de la lectura quan no hi ha sondeig.**
2. **`cte_geomech.detect_soil_type` classifica malament les litologies llegides:** «Rebliment antròpic» / «Lutites, substrat» →
   granular; «Arcillas limosas y arenosas con puntualmente gravitas» / «Arcilla limosa y arenosa con algunas gravas» → grava
   (per «grav»). És el que alimenta `soil_types` quan l'Eva no els escriu. `geotech_criteria._classify` ja ho fa bé (rebliment /
   argila / transicional): **→ P6: un sol classificador.**
3. **El topall 3,5 (granular dens) només dispara amb `soil_type == 'granular'` literal** (`terzaghi_calculator.calculate_qa`):
   Rubí `viaA` (tipus `grava` pel detector) es queda a 3,0 (signat 3,5); amb l'`['granular']` d'abril, 3,5. `GRANULAR_TYPES` de
   `geotech_criteria` inclou grava/arena: **→ mateixa peça P6.**
4. **La columna «N» (P0) prenia el recompte per tram d'una mostra alterada com a N30** (Anciles MA-1 «1/1/1/1» → N=1 → Es 2,5 →
   assentament 57 cm). Arreglat a `n30_display` (`_TALLY_RE`); Anciles ara 2,20 cm (Es 66 = 2,5×Nb 26,3).
5. **Narrativa al 30 %:** adjacents (`adjacent_*_fmt` X 3-5/7), `site_description`/`site_condition`/`building_structure_desc`/
   `materials_intro`/`radon_zone_description` (X 7/7): el text generat no és el de l'Eva (redacció lliure, cap font llegida). És
   el grup on hi ha més marge i on menys hem treballat. `data_signatura_text` X 7/7 = data de generació (esperat).
6. **NO_DATA 47 (`viaA`):** `location_sentence` (7), `architect_name_upper`/`building_type_lower` (5: la lectura no dona el
   camp o el generador el vol en una altra clau), `cte_sol` (5), `csn_radon_text` (4): forats de cablejat lectura → context, no
   de lectura. Llista completa per variable a l'`_AGREGAT-341.md` §«Per VARIABLE».

### Tests

Nous: `tests/test_settlement_criteria.py` (8), `tests/test_wizard_bearing_note.py` (3), `tests/test_soil_levels_open_bottom.py` (1),
`test_D14b_sample_level_by_material_contradicting_the_interval` (consolidador), `test_close_mostra_del_nivell_text_yes_no_equals_boolean`
(comparador), 2 casos a `test_n30_display`. Adaptats al criteri nou: `test_D14_sample_level_from_the_lab_depth_interval`,
`test_D14_sample_level_claimed_by_a_weak_document_gets_the_geometric_alternative`. Dirigits: 650 verds. Suite sencera: **31 vermells
amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2236 verds / 5 omesos** (164 s, segona passada amb el codi final; la primera, abans de la correcció del
recompte per tram, 2234).

### Latència / cost

Tot el dia a cost 0: cap crida LLM (reconsolidació des de lectures cachejades; generació local; SmartScan nivell 1 = regex).
Mesura d'informe ≈ 1 min; M341 ≈ 5 min (7 projectes + 3 variants `t2`); suite 2,8 min.

### Limitacions conegudes

- D4b depèn de la PRIMERA litologia del text i d'una classe única: «Sorres i graves» vs «Graves i sorres» són classes diferents
  (sorra / grava); dos nivells de la mateixa classe → ambigu → l'interval mana sol. Vocabulari `_LITH_STEMS` tancat (ca/es).
- L'Es de l'assentament té defecte SPT-del-nivell: Bell-lloc depèn de quin N (54 signat / 58 tall / 62 lectura: pregunta 1) i Rubí
  encaixa amb Nb, no amb l'SPT (pregunta 15). Cap ordre encerta els dos.
- El càlcul inicial de `generate()` continua fent Terzaghi-Peck amb l'N20 GLOBAL quan `user_data` no porta `sondeig_layers`
  (`nb_for_tp`); només l'assentament s'ha re-ancorat al nivell de l'informe. La cel·la Nb i la Qa del generable coincideixen amb
  el signat perquè el topall mana; a un projecte sense topall divergirien.
- M341 v1: `DF_SIGNAT` és una assumpció per projecte (l'única dada que només l'Eva posa); grups per nom de variable (v1); la
  narrativa es compara per similitud (≥ 0,92 MATCH, ≥ 0,6 CLOSE), no per contingut; `t2` només als 3 amb `_user_data_prev.json`.
- El wizard mostra el nivell portant i la Df però no re-tria el nivell en viu quan l'Eva canvia la Df (cal recarregar prefills).
- `_norm_date`/`_norm_text` del comparador escalar no tenen test propi (no hi havia fitxer de tests); cobert pel run.

### GO/NO-GO

- ✅ Pendents 1 i 2 de l'STATUS tancats (1 cel·la, 0 regressions, ALERTA 6 → 5).
- ✅ P2b UI: nota del nivell portant i Df visibles, avís en ambre.
- ✅ Assentament: criteri de frase 7/7 signats (forma), plantilla amb variable; Es com a candidats; Castellar ✓.
- ✅ M341 v1 reproduïble (`mesura_341.py`), 7 projectes, per grup; 2 bugs reals arreglats pel camí (capa oberta, N30 «1/1/1/1»).
- ⏳ GO del Josep per commitejar (partició proposada: (1) lectura A+B, (2) P2b UI, (3) assentament, (4) M341 + guardes;
  `wizard_service.py`, `review.html` i `report_data.py` porten hunks de dues peces → `git apply --cached` per hunk).
- ⏳ Preguntes 13, 14, 15 (i 1.7) a l'Eva dilluns.

### Següents passos

1. **P5 — geometria de nivells des de la lectura quan no hi ha sondeig** (`de`/`a` de `soil_levels` llegits → `sondeig_layers`;
   «fins al fons» = obert): desbloqueja Linyola, Alcoletge, Vilanova, Anciles al càlcul (nivell portant, roca, règim).
2. **P6 — un sol classificador de sòl** (`_classify` de `geotech_criteria` també per a `soil_types`/`detect_soil_type`) i el
   topall 3,5 per a tot `GRANULAR_TYPES`.
3. Cablejat lectura → context de les 6 variables NO_DATA sistemàtiques (`location_sentence`, `architect_name_upper`,
   `building_type_lower`, `cte_sol`, `csn_radon_text`, `superficie_construida`).
4. Narrativa (30 %): decidir amb el Josep si es modela (adjacents: la lectura ja té `street_address`; `site_description`).
5. Re-mesurar M341 després de cada peça (`mesura_341.py <run>`; diff de `_compare_341.txt` per projecte, no titulars).

*Fi entrada 2026-09-06 (vespre). Pendents de lectura tancats, P2b UI, assentament per criteri i M341 v1 (58 % / 78 %) amb P5 i P6 al davant.*

## 2026-09-06 (nit) — Narrativa per CRITERI: mesura forat-contra-forat (peça 0), fórmules de l'Eva i plantilla (peça 1), adjacents i accés des de la parcel·la del projecte (peça 2): narrativa 30 % → 23 % (mesura honesta) → 54 % → 62 % (català 65 %)

### Context

El handoff del vespre (`_FOR-NEW-YOU-20260907-1810.md`) fixava que la sessió següent comencés per l'ANÀLISI de la narrativa (30 % a
M341, el grup més fluix) i no per codi. L'anàlisi és `docs/ANALISI-NARRATIVA-2026-09-06.md`: el 30 % barreja quatre causes (artefacte
de mesura, fórmules de l'Eva no codificades, dades mal cablejades, idioma castellà de 2 signats). El Josep ha donat GO a les peces
0 (mesura) i 1 (fórmules) juntes i després a la 2 (adjacents i accés). Aquesta entrada documenta les tres. La peça 3 (estat del
solar, laboratori, fotos) i la decisió del castellà queden a la cua.

### Decisions arquitectòniques clau

**A. La narrativa es puntua FORAT CONTRA FORAT (`mesura_341.narr_status`), no per similitud global.** El comparador antic
confrontava el valor del context («pla») amb el paràgraf sencer del signat (X segur) i, si s'hagués renderitzat la frase, la cua
fixa llarga hauria donat MATCH falsos («solar pla» ≈ «solar antropitzat» a 0,93). Ara: es renderitza el paràgraf de la plantilla amb
el valor generat, es treu a les dues bandes el text comú als extrems (paraules, sense accents: «un sòl nivell» de l'Eva = «un sol
nivell») i es puntuen els residus (iguals → MATCH; un residu buit → CLOSE, «res del que escrivim és fals, però falta o sobra
text»; similitud ≥ 0,92 / ≥ 0,6 / MISMATCH). `csn_radon_text` fora de la mesura (el paràgraf del CSN ja és text fix de la plantilla,
p474: el generador l'imprimia DUES vegades). Idioma del signat per projecte a l'agregat (les cel·les ES són sostre, no error). Els
costats agrupats dels adjacents es comparen amb la frase agrupada, no NO_DATA. **Trade-off acceptat:** el número BAIXA abans de
tocar cap text (30 % → 23 %): és el baseline honest (memòria `feedback_measure_baseline_before_coding`). Limitació coneguda:
«Com que… pla» ↔ «Degut a que… antropitzat» encara surt CLOSE (comparteixen el mig «es tracta d'un solar»).

**B. L'extractor de referència alinea per PREFIX i per POSICIÓ, amb ÀNCORA per als paràgrafs que són només una variable; el
refresc de la veritat és QUIRÚRGIC.** (`automation/reference_extractor.py`) Abans triava el paràgraf del signat per similitud de
l'esquelet: «L'edificació que es preveu construir es situarà {{ }}.» s'alineava amb «…presentarà les següents característiques:»
(7/7) i deixava el paràgraf sencer amb confiança 0,2-0,3 (la signatura de l'artefacte). Ara: (1) mana el paràgraf que CONTÉ el
prefix fix (o el seu cap de 5 paraules: «d'estructures» ≠ «d'una estructura»), el que hi COMENÇA abans que el que només el
conté, i en empat el més proper en posició relativa (la frase de l'estructura surt a 3.5 i a 4.3); (2) apòstrofs tipogràfics
1:1; (3) sufix curt («.») = primera ocurrència (abans l'última: en un bloc de cinc frases el forat s'enduia les quatre següents);
(4) sense esquelet («{{ site_condition }}», «{{ radon_sentence }}») o sense cap semblant, ÀNCORA = el paràgraf fix immediatament
anterior de la plantilla localitzat al signat, veritat = el paràgraf següent si NO és capçalera; marcat `paragraph_anchor` i MAI
guanya a una veritat externa (`intelligent_analysis`, d'on ve la majoria de la narrativa del JSON); (5) `location_sentence`
queda ABSENT si el prefix no hi és (l'Eva omet la frase a 6/7) en comptes d'un paràgraf equivocat. **Per què quirúrgic:** una
re-extracció sencera mou coses que no són narrativa (`spt_*` cauen a None, dates canvien de clau per la segona variable de data,
`geomech_*` d'Alcoletge/Vilanova canvien de fila, `settlement` → `settlement_sentence`): `refresh_eva_narrativa.py` aplica només
la llista blanca (grup `narr` + `location_sentence`) i informa de la resta sense tocar-la. **Alternativa rebutjada:** àncora
general per a tot forat (primer intent): trepitjava veritats bones amb capçaleres («2.1. DESCRIPCIÓ…», «4.1. GEOLOGIA», «Qa=
3,50…») → acotada a àncora adjacent + filtre de capçalera + prioritat de l'extern.

**C. Les fórmules de l'Eva són CRITERIS en un mòdul pur (`automation/narrative_criteria.py`), la plantilla té la frase sencera
al forat, i l'única implementació la comparteixen generador i wizard.** Literals dels 5 signats CA (i ES on n'hi ha):
`materials_intro` («A partir dels assaigs in situ realitzats, s'ha establert {un sol nivell | dos nivells} de materials…»),
`conclusions_levels_detected`, `conclusions_aggressivity_statement` («…a priori, es presenten NO AGRESSIUS al formigó.»),
`radon_sentence` (zona 0 → «no pertany a cap municipi amb concentracions inadequades…» (Linyola); municipi del padró en
majúscules amb «de/d'»: «d'ALCOLETGE»; la variant de Rubí com a candidat), `site_condition` (frase SENCERA; criteri del wizard
2026-04: pendent > 10 % → «Tot i no ser un solar pla», antropitzat → «Degut a que…», pendent i explícitament no antropitzat →
«Es tracta d'un solar no antropitzat», si no «Com que es tracta d'un solar pla»; els altres tres caps com a candidats; nota
quan «antropitzat» no té font), `building_structure_desc` (CLÀUSULA sencera després de «…construcció d'una estructura »: (a)
«en planta baixa[ i porxo], i per tant, no es preveu cap excavació important, únicament l'excavació pel sanejament, anivellació,
i per a la implantació dels elements de fonamentació.» / (b) «sense nivell de soterrani, i per tant, únicament es preveu el
sanejament, anivellació, i l'excavació fins a la cota de fonamentació.» / (c) soterrani; defecte (a) si només PB, (b) si té pis,
(c) si soterrani; l'Eva NO tria per plantes (Linyola PB → b, Bell-lloc Pb+1Pp → a) → l'altra com a candidat, pregunta 18),
`empentes_paragraph` (el nivell més desfavorable: φ mínima; sense Ka/Kp, que l'Eva no escriu), `csn_radon_text = ''`. Plantilla:
`site_condition` (×2) i `radon_sentence` passen a paràgraf sol, `building_structure_desc` (×2) només conserva la capçalera fixa,
el paràgraf `csn_radon_text` desapareix (regla 2026-09-05: grep dels signats fet a l'anàlisi §4). **Troballa de pas:** el
generador NO llegia mai `site_condition` ni `building_structure_desc` del `user_data` (les edicions de l'Eva al wizard no
arribaven a l'informe; el generador tenia una segona implementació que discrepava del wizard i a Alcoletge imprimia el
`building_type` sencer dins la frase): ara `user_data` mana, els valors curts antics («en planta baixa», «pla») es mapegen a la
clàusula/frase, i el wizard delega al mateix mòdul (`candidates` al prefill). Idioma: `language_for_report` (municipi ES conegut,
marcadors castellans, o `report_language` explícit a `user_data`/`ReportData`; Vilanova no es detecta per les dades, el plànol
és català: decisió a part). **Errates de l'Eva no reproduïdes** («un sòl nivel», «del murs», «més desfavorables»). **Alternativa
rebutjada:** síntesi LLM de la prosa (`wizard_service` Fase B): les frases són fórmules; un LLM hi afegeix variància i cost sense
cap cel·la nova.

**D. Els adjacents es sondegen des de la PARCEL·LA DEL PROJECTE (referències llegides pel portal), les plantes del veí es
compten bé, i la redacció és el vocabulari tancat de l'Eva amb agrupació de costats.** (1) `web/lectura_service` mapa
`referencia_catastral` → `cadastral_refs` (abans `None`: «cap ocurrència»; 6/7 projectes en tenen: Castellar 3 portals,
Bell-lloc 1 de 20 caràcters, Rubí «Polígon 6, Parcel·la 105-B» no és RC). `parcel_context.parse_rc_list` → llista de 14;
`cadastre_adjacents.get_adjacent_parcels(rc14=llista)`: polígon UNIÓ (Shapely), sondeig des de les arestes de la unió, «la nostra
parcel·la» = conjunt de referències (`_is_ours`), UTM opcional (centroide), cache per referències. Bell-lloc: l'UTM de COORDENADES
resolia «CL VIA FERREA 57» (parcel·la equivocada, 1/4 costats); amb la referència llegida, 4/4 tipus i «Carrer Mestre Ramon Ortiz»
exacte. Rubí, Vilanova, Anciles (sense UTM) ja tenen adjacents (Vilanova/Anciles per RC). (2) `_query_building_data` llegia
`<stl>` (SUPERFÍCIE) esperant-hi «PLANTA»: mai comptava plantes → sempre «parcel·la amb construcció». La planta és `<pt>` («00»,
«01», «-1», «SM»); `<lcd>` DEPORTIVO/PISCINA → piscina. Verificat en viu (DNPRC de Bell-lloc). Ara: «parcel·la amb una construcció
aïllada de fins a dos plantes sobre rasant, amb soterrani i piscina» / «parcel·la on existeix un edifici aïllat en planta baixa»
(literals d'Alcoletge i Bell-lloc). (3) `adjacent_formatter` reescrit: ordre N, S, E, O; «I finalment, per la part X, amb …» a
l'ÚLTIMA frase; dos o més costats amb el mateix contingut (no carrer) en UNA frase en plural al forat del primer («Per la part
nord, sud i est amb parcel·les buides.»), l'altre forat buit; les frases de l'Eva/síntesi (fonts fiables) no s'agrupen i compten
per a «l'última»; castellà amb el vocabulari traduït («con la calle STA. GEMMA», «edificio de hasta 4 plantas»). (4)
`access_street_from_adjacents`: el costat que és carrer (el de la via de l'adreça; «entre X i Y» → X; si no, el primer en N, S, E,
O) → defecte «carrer adjacent situat al {costat}» (Castellar, Linyola) i candidats «Carrer existent al {costat}» (Alcoletge) i
«carrer {Nom}» (Rubí). (5) `location_sentence_from_streets`: «(Situat) entre X i Y» de la lectura tal qual (abans «entre el Situat
entre…»), carrers duplicats pel nom normalitzat fora («Carrer Arbrells» ≡ «Carrer dels Arbrells»), municipi del padró
(«Bell-lloc d'Urgell», «d'Alcoletge»). (6) `adjacent_intro` (7/7 signats, no era cap variable): «La parcel·la objecte d'estudi es
situa al {nord} del municipi de {Municipi}, pren una morfologia {quasi rectangular} i limita:» — posició per rosa de 8 vents des
del centre del municipi (Nominatim, cache 90 dies), forma per àrea / rectangle mínim del polígon (≥ 0,92 rectangular, ≥ 0,78
quasi), `site_position`/`parcel_shape` del wizard manen. Castellar: «nord» + «quasi rectangular» = signat. (7) **Defecte de
plantilla trobat i arreglat:** p111 i p114 eren forats sobrers (`adjacent_east_fmt` ABANS de la capçalera 2.1.1 i
`adjacent_south_fmt` just després): tots els informes generats des de l'abril duien dues frases repetides i els faltaven la
capçalera «2.1. DESCRIPCIÓ DE LA ZONA D'ESTUDI» i la frase d'introducció. **La plantilla instal·lada a l'Eva (`production/g3dt-eva-v1`)
té el mateix defecte.** Ara: capçalera (estil de la 2.2), `{{ adjacent_intro }}`, i els 4 forats dins de `{%p if %}` /
`{%p endif %}` en paràgrafs propis (docxtpl exigeix l'etiqueta sola al paràgraf: el primer intent en línia va fer fallar el
render de tots els projectes, `TemplateSyntaxError: unknown tag 'endif'`). **Alternatives rebutjades:** parcel·la rústica de
Rubí via `Consulta_DNPPP` (el Cadastre no troba «polígon 6, parcel·la 105»); geometria per intersecció de dos carrers per a
adreces sense portal (no cal: Bell-lloc porta la RC als documents).

### Implementació

| Peça | Fitxers | Notes |
|---|---|---|
| 0 | `docs/wizard-headless/mesures/mesura_341.py` (`narr_status`, `residues`, `template_slots`, `lang_of_eva`, `_grouped_adjacent`, `NARR_EXCLUDED`, `NARR_SLOT_EXTRA`, agregat per idioma), `docs/wizard-headless/mesures/refresh_eva_narrativa.py` (nou, 96 LOC), `automation/reference_extractor.py` (`_single_var_prefix`, `_anchor_paragraph`, `_looks_like_heading`, `_ap_lower`, `_ABSENT_IF_PREFIX_MISSING`, `paragraph_anchor` a `_OWN_EXTRACTION_METHODS`, prioritat de l'extern a `_merge_with_prior`), 7 × `reference-material/*/validation/eva_reference_values.json` (només claus narratives: `location_sentence` ×7, `access_street` ×5, `site_condition` ×7, `building_structure_desc` ×2, `radon_sentence` ×7, `adjacent_intro` ×7; `radon_zone_description` i `csn_radon_text` eliminades) | signats d'Alcoletge i Anciles copiats a `reference-material/` (ignorats pel git) |
| 1 | `automation/narrative_criteria.py` (nou, 441 LOC), `automation/report_generator.py` (estructura, estat del solar després de la pendent, radó, `csn = ''`, nivells detectats, `report_language`), `automation/sections/section3_geologia.py`, `automation/sections/section4_conclusions.py`, `web/wizard_service.py` (delega: −60 LOC), `automation/report_data.py` (`report_language`), `templates/g3dt-jinja-template.docx` (p342, p559 → `{{ site_condition }}`; p404, p570 → `…estructura {{ building_structure_desc }}`; p497 → `{{ radon_sentence }}`; p498 eliminat) | `mesura_341.GROUPS` narr + `radon_sentence` |
| 2 | `automation/parcel_context.py` (nou, 164 LOC), `automation/cadastre_adjacents.py` (`_is_ours`, `project_polygon`, rc list/unió/UTM opcional/cache per RC, `_query_building_data` `pt`+piscina, `_describe_neighbor`), `automation/adjacent_formatter.py` (reescrit, 305 LOC: agrupació, plural, ES, `access_street_from_adjacents`, `_norm_street`), `automation/report_generator.py` (bloc d'adjacents amb RC, `access_street`, `adjacent_intro`, `location_sentence_from_streets`), `automation/narrative_criteria.py` (`municipality_proper`, `location_sentence_from_streets`), `web/lectura_service.py` (`referencia_catastral` → `cadastral_refs`), `automation/auto_extractor.py` (`_phase3_adjacents` amb RC llegides), plantilla 2.1.1 (capçalera, `{{ adjacent_intro }}`, 4 × `{%p if %}`) | `mesura_341.GROUPS` narr + `adjacent_intro` |

`git diff --stat`: 22 fitxers, +1129 / −663, més 4 fitxers nous de codi/tests i el document d'anàlisi. Cap dependència nova (Shapely
ja hi era). `geocode_coordinates.py` (via B) només es llegeix (`nominatim_geocode`, `_wgs84_to_utm31n`).

### Validació empírica

Runs (`docs/wizard-headless/mesures/runs/`), variant `viaA`, 7 projectes, narrativa M · C · X · ND → % ((M+C)/(M+C+X)):

| Run | Què | narrativa | CA | ES | escalars+narr total | taules |
|---|---|---|---|---|---|---|
| `2026-09-06-m341` (ahir) | comparador antic | 8 · 18 · 61 · 22 → **30 %** | — | — | 156/38/141/47 → 58 % | 265/98/100 → 78 % |
| `2026-09-06-m341-mesura` | peça 0 (mesura, veritats refrescades, codi d'ahir) | 3 · 16 · 64 · 19 → **23 %** | 30 % | 5 % | 58 % | 78 % |
| `2026-09-06-m341-narr1` | + peça 1 (fórmules, plantilla) | 22 · 22 · 38 · 20 → **54 %** | 57 % | 43 % | 170/43/111/45 → 66 % | 78 % |
| `2026-09-06-m341-narr2c` | + peça 2 (adjacents, accés, ubicació, introducció) | 29 · 29 · 36 · 15 → **62 %** | **65 %** | 52 % | 178/49/109/40 → **68 %** | 78 % (t2 84 %) |

Per projecte (escalars+narrativa, ahir → avui): Castellar 68 → 77 %, Rubí 60 → 71 %, Bell-lloc 68 → 79 %, Linyola 68 → 72 %,
Alcoletge 52 → 62 %, Vilanova 40 → 53 %, Anciles 40 → 51 %. Grup A 69 → 74 % (la ubicació de Bell-lloc MATCH; les 6 «veritats»
inexistents fora). `mesura_informe.py` (`2026-09-06-informe-narr1`, `-narr2`): les 11 taules IDÈNTIQUES a `-final` als 3 projectes ×
4 variants (`diff` buit).

Per variable després de la peça 2 (M · C · X · ND de 7): `site_condition` 4·2·1·0 (Castellar «Tot i no ser…», Linyola i Alcoletge
«Com que…» MATCH; Bell-lloc «antropitzat» sense font i Rubí sense UTM + cinquè cap «Al solar,» = candidats), `radon_sentence`
4·3·0 (Rubí variant = candidat; ES), `materials_intro` 3·4·0 i `conclusions_levels_detected` 4·3·0 (els CLOSE són el recompte de
nivells de Rubí/Linyola = P5, i l'errata «nivel» de Castellar), `adjacent_intro` 2·5·0 (Castellar i Bell-lloc exactes; Rubí
sense polígon, Alcoletge «est» vs «nord-est»), `location_sentence` 1·0·0 (Bell-lloc exacte; 6 absents al signat),
`building_structure_desc` 2·1·3 (Bell-lloc i Linyola: l'Eva tria l'altra variant → candidat), `conclusions_aggressivity_statement`
2·1·3 (Bell-lloc «xxxx» de l'Eva; Alcoletge sense laboratori cablejat; Rubí sense «a priori»), `access_street` 2·0·3·2
(Castellar i Linyola exactes; Bell-lloc «de la del Carrer existent al sud» amb errata; Alcoletge «camí» privat invisible al
Cadastre), adjacents N 1·0·6 · S 1·2·4 · E 1·1·5 · O 0·2·5 pel comparador estricte (residus); per TIPUS de costat: Bell-lloc 4/4
(abans 1/4), Castellar 3/4 (piscina de l'est encertada), Linyola 3/4, Alcoletge 2/4 (camí privat i «solar buit» vs «parcel·la
buida»), Vilanova i Anciles amb valors (abans «sense informació»). Verificacions en viu: DNPRC (`pt` = planta, `stl` =
superfície), Bell-lloc RC 4613173CG1141S → E «Carrer Mestre Ramon Ortiz», O «construcció aïllada de fins a dos plantes» (signat);
Castellar 3 RC → posició «nord», forma «quasi rectangular» (signat). `.docx` de Bell-lloc renderitzat: capçalera 2.1, introducció,
4 costats, accés «carrer adjacent situat al sud».

### Tests

Nous: `tests/test_narrative_criteria.py` (10: fórmules vs literals signats, criteri de l'estat del solar 5/5 caps, estructura
i valors antics, radó zones 0/1/2 i «d'», idioma, plantilla), `tests/test_adjacents_narrative.py` (12: RC, unió/centroide/forma,
rosa de vents, introducció, DNPRC `pt` amb XML de mostra, `_is_ours`, agrupació i última frase, castellà, precedència de l'Eva,
accés, ubicació, plantilla 2.1.1). Adaptats: cap (els 2 vermells del primer intent d'agrupació eren la precedència de l'Eva:
`fixed_sides`). Dirigits: 689 verds (peça 1) i 38 (peça 2). Suite sencera: **31 vermells idèntics als esperats / 2258 verds / 5
omesos** (dues passades, la final després de l'últim retoc: idèntic).

### Latència / cost

Cost LLM 0 (tot determinista). Xarxa nova per informe: WFS del Cadastre per referència (memo per procés), DNPRC per veí (ja hi
era), Nominatim del centre del municipi (1 crida, cache 90 dies). M341 dels 7: ~5 min, com abans.

### Limitacions conegudes

- **Castellà:** Vilanova i Anciles (30 cel·les de narrativa) segueixen amb la plantilla catalana; `report_language` existeix
  (`user_data`/`ReportData`) però no hi ha plantilla ES ni camp al wizard. Decisió del Josep i de l'Eva (pregunta 19).
- **Rubí sense adjacents a `viaA`:** RC rústica no resoluble, sense UTM; al wizard `_fill_missing_adjacents` geocodifica l'adreça.
- **Judici de la visita:** «amb herbes altes i arbres», «construïda amb piscina», «camí d'accés» (via privada d'urbanització),
  «solar buit» vs «parcel·la buida»: el Cadastre dona el TIPUS; el detall és de l'Eva (wizard). Comparador estricte → CLOSE/X.
- **Antropitzat** sense font (Bell-lloc) i tria (a)/(b) de l'estructura: candidats; preguntes 17 i 18.
- **Veritats fora de la narrativa que l'extractor mou i NO s'han aplicat** (per aïllar): `spt_*` → None (deriva de la taula SPT),
  `data_camp_inici_text` (nova, correcta), `geomech_*` d'Alcoletge/Vilanova (canvien de fila), `settlement` → `settlement_sentence`,
  `num_dpsh_tests` (número sol). Pendent: arreglar l'extractor i re-extreure els grups A/calc amb la mateixa disciplina de diff.
- **Comparador:** «Com que… pla» ↔ «Degut a que… antropitzat» surt CLOSE (mig compartit); acceptat.
- **Producció:** la plantilla instal·lada a l'Eva té el defecte 2.1.1 (dues frases repetides, sense capçalera 2.1 ni introducció).
  Cap pull/merge proposat (memòria `feedback_no_pull_eva_success_criterion`); ho decideix el Josep.
- `reference-material/4001607 LINYOLA/validation/photo_selection.json`: artefacte del generador durant els runs (no versionar).
- Peça 3 NO feta: `site_description` (estat del solar per criteri), `lab_tests_text` (llista del GTL), bloc de fotos condicional.

### GO/NO-GO

- ✅ Peça 0: mesura honesta, veritats narratives refrescades (només llista blanca), extractor amb prefix/posició/àncora.
- ✅ Peça 1: 7 fórmules per criteri, 3 variables de plantilla a frase sencera, una sola implementació generador+wizard, el
  `user_data` de l'Eva torna a manar.
- ✅ Peça 2: adjacents des de la parcel·la del projecte, plantes del veí, vocabulari i agrupació, accés, ubicació, introducció,
  plantilla 2.1.1 arreglada.
- ✅ 11 taules intactes; suite amb els 31 vermells esperats.
- ⏳ Commit: decisió del Josep (partició suggerida: 0 mesura+extractor+veritats · 1 fórmules+plantilla · 2 adjacents+plantilla · docs).

### Següents passos

1. Peça 3 (§3.2 de l'anàlisi): `site_description` per criteri editable (Cadastre parcel·la pròpia + pendent ICGC + vocabulari
   tancat), `lab_tests_text` del GTL (vocabulari de 4-5 assaigs), bloc de fotos «vistes generals» condicional.
2. Wizard: mostrar els candidats («+N») de `site_condition`, `building_structure_desc`, `access_street` (ja són al prefill
   `candidates` i al context `_narr_*`); camp «Idioma de l'informe» si es decideix el castellà.
3. Preguntes 16-19 a l'Eva (dilluns) amb les 13-15.
4. P5/P6 (recompte de nivells: arregla `materials_intro`/`levels_detected` de Rubí i Linyola) i cablejat del laboratori
   (agressivitat d'Alcoletge, Vilanova, Anciles).
5. Extractor: deriva `spt_*` / dates / `geomech_*` / `settlement_sentence` → re-extracció controlada dels grups A i calc.
6. Producció: decidir quan i com arriba a l'Eva la plantilla arreglada (2.1.1 + frases senceres).

*Fi entrada 2026-09-06 (nit). Narrativa per criteri: mesura forat-contra-forat, fórmules de l'Eva, adjacents des de la parcel·la del projecte; 30 % → 62 % (català 65 %), taules intactes.*

## 2026-09-06 (nit, 2) — Peça 3 de la narrativa (estat del solar, assaigs del GTL, vistes generals condicionals), candidats «+N» al wizard i plantilla de PRODUCCIÓ arreglada: narrativa 62 → 61 % (honest: 8 NO_DATA entren, 6 com a X), MATCH 29 → 32, taules 78 → 79 %

### Context

Continuació de l'entrada 2026-09-06 (nit): el Josep demana (2026-09-07) seguir amb la peça 3 de `docs/ANALISI-NARRATIVA-2026-09-06.md`
§3.2 (estat del solar, assaigs de laboratori, fotos), després fer visibles al wizard els candidats narratius, i corregir la plantilla de
producció «tal com s'ha descobert que cal». Decisió del Josep sobre el castellà: **s'implementarà, però no avui** (molta feina; primer la
resta). Cap LLM: tot criteri i vocabulari tancat dels signats.

### Decisions arquitectòniques clau

**A. L'estat del solar es redacta NOMÉS amb el que sabem (Cadastre propi + pendent ICGC); la resta és candidat.**
(`narrative_criteria.site_description_sentence`) La veritat de l'extractor per a `site_description` és tot el bloc 2.1.2; la mesura ja
en treu les tres frases fixes (peça 0) i queda l'estat del solar: judici de la visita (§3.2). El criteri escriu (a) «El solar està
actualment ocupat per una zona explanada i un edifici en planta baixa.» si la parcel·la del projecte té edifici al DNPRC
(`parcel_context.own_parcel_buildings`: agregat de `_query_building_data` sobre les RC llegides, cache `dnprc/` 90 dies; Alcoletge:
1 planta, 89 m² → literal del signat); (b) «…sense construccions ni pavimentacions. Topogràficament, el solar presenta pendent.» si la
pendent ICGC > 10 % (Castellar 33,6 %); (c) «…, anivellat a la rasant del carrer.» si és plana (Bell-lloc, Linyola); (d) **sense UTM ni RC
(Rubí) cap afirmació topogràfica**: «El solar es localitza sense construccions ni pavimentacions.» + nota «sense font». Vegetació,
tanques, «15 cm per sota del carrer», desbroç i plataforma de treball: candidats amb la font (Bell-lloc, Linyola, Rubí, Castellar), mai al
defecte. El text de l'Eva al wizard mana (≥ 4 paraules) i el criteri baixa a candidat. **Trade-off acceptat:** contra el text de l'Eva
surt MISMATCH a 6/7 (el comparador de residus no sap que el nostre és un subconjunt factual del seu) i CLOSE a Alcoletge; abans era
NO_DATA (paràgraf buit a l'informe). Res fals abans que un número. **Alternativa rebutjada:** `site_text_generator` (síntesi
d'ortofoto, `G3DT_ORTHO_ENRICHMENT`): repeteix la frase d'accés i les dues fixes (duplicaria el bloc) i afirma vegetació/tanques per
visió; queda apagat. El wizard deixa de generar «parcel·la de forma rectangular amb superfície de 571 m2» («plantilla generada»).

**B. Els assaigs de laboratori surten del bloc «ASSAIGS REALITZATS:» del GTL amb el vocabulari de l'Eva, en ordre canònic.**
(`narrative_criteria.parse_gtl_tests` + `lab_tests_lines`; `lab_extractor._read_pdf_text(sort=True)`) El bloc ja s'extreia
(`_extract_tests_text`) però el generador imprimia el `type` del primer assaig («Contingut en sulfats solubles UNE 83963:2008», que
l'Eva no escriu mai) i a Linyola l'ordre intern del PDF posava dues de les quatre línies ABANS del títol del bloc (només se'n veien
dues): ara el GTL es llegeix també en ordre de lectura. Fórmules: sulfats sol → «1 assaig de contingut en sulfats UNE 83963 : 2008»
(Castellar, Bell-lloc: exacte); llista → granulometria («Anàlisi granulomètrica d'un sòl per tamissat UNE 103101/95»), Atterberg
(«Assaig de Límits d'Atterberg UNE 103103/94 – 104/93», Linyola; la forma de Rubí «Determinació de Límits d'Atterberg d'un sòl…» com a
candidat; els dos límits del GTL s'ajunten en una línia), Lambe («Assaig d'expansivitat Lambe UNE 103600/96»: Linyola signat diu
«UNE 103500/94», errata — la norma del Lambe és la que cita el GTL; no es reprodueix), sulfats. Castellà: la línia literal del GTL
(Vilanova, Anciles) o traducció si el GTL és català. Text sobreposat del peu («PROSPECCIÓ», «TPS,») fora. Sense bloc → buit (Alcoletge,
Vilanova, Anciles no tenen GTL a la carpeta: pregunta 20c).

**C. El bloc de vistes generals és CONDICIONAL i el seu defecte és el que l'Eva ha triat, no el que la IA troba.**
(`narrative_criteria.photo_site_caption`; plantilla p130 `{%p if photo_site_text %}` · p131 `{{ photo_site_text }}` peu SENCER · p132
`{%p endif %}`, la taula de dues fotos queda dins) 4/7 signats no porten el bloc (la Fotografia 1 és la màquina); Bell-lloc 2, Rubí 1
(Google Earth), Vilanova 1. El generador assumia «Eva always places 2 side-by-side photos» i la selecció IA de fotos sempre omple
`site_1`/`site_2`: tots els informes generats des de l'abril duien dues fotos i la numeració de la màquina i dels materials corria +2.
Ara `num_site_photos` = camp del wizard (0/1/2); defecte = fotos de vista general triades per l'Eva a la pestanya de fotos
(`photo_selection.json` amb `source=user`: Bell-lloc en té 2 = signat); sense tria explícita, 0. Les imatges que el peu no anuncia es
buiden al render (`_num_site_photos`). Peu 1 foto: «Fotografia 1. Vista general de la zona d'estudi.» (la cua «(Google Earth, Agost
2024)» és de l'Eva). Veritats: `refresh_eva_narrativa.py` informa 0 diferències (les de `photo_site_text` ja eren el paràgraf sencer).

**D. Els candidats narratius arriben al wizard pel mecanisme «+N» que ja existia, amb cinc camps nous.**
(`web/wizard_service._compute_narrative_prefills`, `automation/wizard.WIZARD_FIELDS`, `templates/validation/review.html` grup «Narrativa»)
`site_condition`, `building_structure_desc`, `access_street`, `lab_tests_text` i `num_site_photos` no tenien camp al wizard (els candidats
eren al prefill però l'Eva no els veia ni els podia canviar; `save_wizard_data` té llista blanca i els hauria descartat). Ara: camp
propi amb badge de font, candidats a `merged['_alternatives']` (el mateix que FileMiner i els geotècnics) amb la seva procedència
(«variant (b) dels signats», «nom de la via (Rubí)»…), desplegable ample per a frases senceres (abans 60 caràcters), i el generador
llegeix `user_data['access_street']` i `['lab_tests_text']` (abans només els derivava). `access_street` al wizard es calcula com al
generador (`access_street_from_adjacents`) i, sense cap costat carrer al Cadastre, cau al nom de la via llegida («carrer de la
Miranda» = Rubí signat; Alcoletge «carrer Girasols» contra «Carrer existent al nord»: el camí és privat i el Cadastre no el veu).
**Alternativa rebutjada:** camp «Idioma de l'informe» i plantilla ES — va amb la decisió del castellà, un altre dia.

**E. La plantilla de producció es corregeix a la seva branca, sense cap variable nova i sense push.**
(`production/g3dt-eva-v1`, commit `c46bc69`, fet en un worktree temporal) Defecte confirmat: la capçalera «2.1. DESCRIPCIÓ DE LA ZONA
D'ESTUDI» (Heading 2, p102) contenia `{{ adjacent_east_fmt }}` en comptes del seu text, i p106 era un `{{ adjacent_south_fmt }}`
repetit abans dels quatre forats: cada informe de l'Eva duia la frase de l'est com a títol de secció i la del sud dues vegades. Fix:
text de la capçalera restaurat (mateix estil), paràgraf sobrer eliminat; els 4 forats queden com estaven (sense `{%p if %}`: el
generador de producció no té `adjacent_intro` ni la peça 2, i un canvi més gran és una decisió de fusió, no de plantilla). Verificat:
render docxtpl amb N-S-E-O sota la capçalera; `tests/test_reference_extractor.py` 21/21 a la branca. **Cap push, cap pull proposat a
l'Eva** (memòria `feedback_no_pull_eva_success_criterion`): el Josep decideix quan.

### Implementació

| Peça | Fitxers | Notes |
|---|---|---|
| A | `automation/narrative_criteria.py` (`site_description_sentence`, taules CA/ES + variants), `automation/parcel_context.py` (`own_parcel_buildings`, cache `dnprc/`), `automation/report_generator.py` (bloc després de `site_condition`; `_own_parcel_building` al context), `web/wizard_service.py` (`_generate_template_prefills_from_merged`) | DNPRC en viu: Bell-lloc sense edifici, Castellar 3 RC sense, Alcoletge 1 planta 89 m² |
| B | `automation/narrative_criteria.py` (`parse_gtl_tests`, `lab_tests_lines`, `_une_short`), `automation/lab_extractor.py` (`_read_pdf_text(sort=)`, `gtl_text_sorted`), `automation/report_generator.py` (una sola `extract_lab_results`; `_narr_lab_tests`) | tolerant amb lectors substituïts als tests (`TypeError`) |
| C | `automation/narrative_criteria.py` (`photo_site_caption`), `automation/report_generator.py` (numeració, `_site_photos_from_user_selection`, buidat d'imatges al render), `templates/g3dt-jinja-template.docx` (p130-p132) | `mesura_341` ja compara `photo_site_text` forat contra forat (deixa de ser slot) |
| D | `web/wizard_service.py` (`_compute_narrative_prefills`: accés, laboratori, fotos, `_alternatives`), `automation/wizard.py` (`WIZARD_FIELDS` +5), `templates/validation/review.html` (grup «Narrativa», `renderWizardForm`, `collectWizardFields`, `showAlternatives`), `automation/adjacent_formatter.py` (`access_street_from_adjacents` sense costat carrer), `automation/report_generator.py` (`user_data['access_street']`) | |
| E | `production/g3dt-eva-v1`: `templates/g3dt-jinja-template.docx` (commit `c46bc69`) | worktree temporal esborrat després del commit |

`git diff --stat` (experiment): 10 fitxers modificats + `tests/test_narrative_wizard_prefills.py` nou. Cap dependència nova.

### Validació empírica

Runs `viaA` (7 projectes), narrativa M · C · X · ND → % ((M+C)/(M+C+X)):

| Run | narrativa | CA | ES | escalars+narr | taules |
|---|---|---|---|---|---|
| `2026-09-06-m341-narr2c` (peça 2) | 29 · 29 · 36 · 15 → 62 % | 65 % | 52 % | 178/49/109/40 → 68 % | 265/98/100 → 78 % |
| `2026-09-07-m341-peca3` (peça 3) | 32 · 30 · 39 · 8 → **61 %** | 65 % | 50 % | 181/50/112/33 → 67 % | 267/97/99 → **79 %** |

Per variable (7): `site_description` 0·0·0·7 → **0·1·6·0** (Alcoletge CLOSE: «…un edifici en planta baixa» contra «…a la meitat
nord»; la resta X: judici de la visita); `lab_tests_text` 0·2·2·3 → **2·2·0·3** (Castellar i Bell-lloc exactes; Rubí i Linyola CLOSE
per la forma d'Atterberg / la norma del Lambe; 3 sense GTL); `photo_site_text` 0·1·2·(4 absents) → **1·0·0·2** (Bell-lloc exacte;
Rubí i Vilanova sense tria = bloc absent); `access_street` 2·0·3·2 → **3·0·4·0** (Rubí «carrer de la Miranda» exacte; Alcoletge
«carrer Girasols» X). Cap altra variable es mou (`diff` dels `_compare_341.txt` amb `-narr2c`). `mesura_informe.py`
(`2026-09-07-informe-peca3` vs `-narr2`, 3 projectes × 4 variants): l'ÚNICA cel·la moguda a les 11 taules és «Assaigs realitzats» de
la taula del laboratori (Castellar i Bell-lloc CLOSE → MATCH, Rubí MISMATCH → CLOSE); tota la resta idèntica. `.docx` de Bell-lloc,
Castellar, Alcoletge i Rubí inspeccionats: bloc 2.1.2 amb accés + estat + les dues fixes; Bell-lloc amb el peu de dues fotos i la
màquina a la Fotografia 3, Castellar sense bloc i la màquina a la Fotografia 1 (com al signat).

### Tests

Nous: `tests/test_narrative_criteria.py` +4 (estat del solar 4 casos + text de l'Eva + ES; assaigs Rubí/Linyola/sol/ES; peu 0/1/2;
plantilla condicional), `tests/test_narrative_wizard_prefills.py` (3: llista blanca, candidats «+N» i precedència de l'Eva, fotos
triades → 1). Adaptats: cap. Dirigits: 83 verds. **Suite sencera: 31 vermells idèntics als esperats / 2265 verds / 5 omesos.**

### Latència / cost

Cost LLM 0. Xarxa nova per informe: DNPRC de les RC pròpies (1 crida per referència, cache 90 dies). M341 dels 7: ~2 min amb
caches calentes.

### Limitacions conegudes

- `site_description`: 6/7 MISMATCH és el resultat honest del criteri factual contra un text de visita; MATCH només amb l'Eva
  (pregunta 21). El wizard ho mostra amb els candidats de les 4 formes signades.
- `lab_tests_text`: Alcoletge, Vilanova i Anciles sense GTL a la carpeta (pregunta 20c); la forma d'Atterberg i la norma del Lambe
  (pregunta 20a-b).
- `photo_site_text`: sense tria de l'Eva el bloc no hi és (Rubí i Vilanova en tenien 1 al signat): és l'assumpció menys falsa,
  no una lectura.
- `access_street` d'Alcoletge («Carrer existent al nord»): el camí d'accés és privat i no és cap costat del Cadastre.
- Producció: la introducció 2.1.1 i les frases senceres (peça 1) NO són a `production/g3dt-eva-v1` (només la plantilla del 2.1.1);
  el commit `c46bc69` no està pujat.
- Castellà: pendent (decisió del Josep: sí, més endavant).
- `reference-material/4001607 LINYOLA/validation/photo_selection.json` (artefacte de la selecció IA durant els runs): no versionar.

### GO/NO-GO

- ✅ Peça 3: estat del solar, assaigs i vistes generals per criteri; generador i wizard amb una implementació.
- ✅ Candidats «+N» visibles i editables al wizard (5 camps nous, desats a `user_data`).
- ✅ Plantilla de producció corregida i commitejada a la seva branca (`c46bc69`); sense push.
- ✅ 11 taules: només la cel·la del laboratori mou, a millor; suite amb els 31 vermells esperats.
- ⏳ Commit a `experiment/nivell-a-2026-08`: decisió del Josep (partició suggerida: 3a estat del solar + accés · 3b laboratori ·
  3c fotos + plantilla · wizard «+N» · docs).
- ⏳ Push de `production/g3dt-eva-v1`: decisió del Josep.

### Següents passos

1. Preguntes 20-21 (i 16-19) a l'Eva.
2. Castellà (plantilla ES + camp «Idioma de l'informe»; `report_language` ja existeix).
3. P5/P6 (recompte de nivells) i cablejat del laboratori dels 3 projectes sense GTL.
4. Deriva de l'extractor fora de la narrativa (`spt_*`, dates, `geomech_*`).
5. Producció: decidir si i quan la peça 1 + 2 + 3 arriben a l'Eva.

*Fi entrada 2026-09-06 (nit, 2). Peça 3 de la narrativa, candidats al wizard i plantilla de producció; 61 % honest, taules 79 %.*

## 2026-09-07 — Bloc 1 del PLA: càlcul i taules dels projectes SENSE sondeig (P5 geometria des de la lectura, P6 un sol classificador de sòl, CTE T-1, rang de taules per TAULES, data de signatura, variant d'assentament): calc 66 → 76 %, total 67 → 71 %, taules 79 → 81 %

### Context

Primer bloc del `docs/PLA-QUE-QUEDA-DESPRES-DE-A-B-I-NARRATIVA-2026-09-07.md` (ordre acceptat pel Josep en demanar el handoff
`_FOR-NEW-YOU-20260907-2230.md`). Les troballes 1-3 de M341 (DECISION-LOG 2026-09-06 (vespre)) deien que els 4 projectes sense
sondeig (Linyola, Alcoletge, Vilanova, Anciles) calculaven sobre una geometria del segmentador DPSH i un classificador de sòl que
no llegia castellà ni lutites. Referència de mesura: `2026-09-07-m341-peca3` (M341) i `2026-09-07-informe-peca3` (11 taules).
Tot el dia a cost 0 (cap crida LLM).

### Decisions arquitectòniques clau

**A. P5 — sense sondeig, la geometria dels nivells surt del tall LLEGIT, no del segmentador.**
`automation/lectura/tables_report.sondeig_layers_from_levels` converteix les files `soil_levels` llegides (de/a per nivell, ja al
`user_data['lectura_tables']` des de la Fase 8b) en `sondeig_layers` (`depth_from_m`, `depth_to_m`, `description`, `source: lectura`).
Regles de la fila 1.4 (2026-09-05, nit 4): nivell 1 des de 0,00; sostre = base de l'anterior si falta; base de l'últim = `None`
(«fins al fons d'investigació» es reconeix abans de llegir cap número: el «-2,90» de dins NO és un contacte); un contacte interior
sense cap dels dos costats → `[]` (mai s'inventa: Vilanova i Anciles cauen al segmentador com abans). `report_data.lectura_sondeig_layers`
(precedència `tables` > `user_data['lectura_tables']` > `_decisions.json`) hi afegeix l'N20 mitjà del DPSH per capa (la regla de capa
fluixa de `bicapa` el necessita). Cablejat als TRES llocs que sintetitzaven capes: `build_report_data`, `ReportGenerator.build_report_data`
(a `user_data['sondeig_layers']` com les del sondeig, perquè Terzaghi-Peck i les files de la taula vegin la mateixa geometria) i
`wizard_service._compute_geotech_prefills`. **Why:** Linyola col·lapsava a un sol «Llims» 0-3,0 i calculava grava densa (φ 38 / c 0 /
E 450) on el signat calcula amb les lutites del 2n nivell (30 / 1,0 / >800). Alternativa rebutjada: millorar el segmentador (un
canvi de pendent de l'N20 no és el contacte que l'Eva dibuixa; el tall ja el diu).

**B. P5, gruix de l'últim nivell obert = fondària investigada − sostre, imprès amb asterisc.** `SoilLevel.thickness_open` (nou);
`_generate_soil_levels` posa `thickness = fons − sostre` a l'última capa sense base; la taula sísmica imprimeix «0.29*». La fondària
és la IMPRESA en aquest informe (files DPSH llegides «-1.69»; si no, l'anotació «R:» del full; l'Excel arrodoneix al tram de 0,20:
1,80) — `ReportGenerator._refresh_open_thickness` després del pegat de rebuig. **Evidència:** Linyola 1.30* = 2,90 − 1,60, Alcoletge
0.29* = 1,69 − 1,40, Vilanova 1.58* = 3,78 − 2,20 (3/4; Anciles 3.92* = 5,92 − 2,00 amb un 1r nivell «4.00» que no quadra: errata
del signat). Abans la cel·la era buida. Els nivells únics (Castellar 1.15*, Rubí 4.55, Bell-lloc 2.45, tres convencions diferents) no
es toquen.

**C. P6 — un sol classificador de sòl: `cte_geomech.detect_soil_type` delega a `geotech_criteria._classify`.** `lith_flags`
(ca/es sense accents) + `is_rock` + el primer material del text (`_first_material_stem`: l'ordre d'aparició mana) → classe del
criteri → vocabulari del wizard (`rock | grava | arena | arena_limosa | limo | arcilla | granular`). `is_rock` llegeix castellà
(`areniscas`, `sustrato`, `brecha`, `caliza`, `lutitas`, `margas`, `pizarra`) i exclou les margues toves. **Why:** «Arcilla limosa y
arenosa con algunas gravas» → `grava` (per «grav»), «Lutites, substrat» i «Rebliment antròpic» → `granular`, «Arcillas arenosas» →
`granular`: el detector antic només sabia català i sense accents normalitzats; alimentava `soil_types` (wizard i mesura), el nivell
portant, el topall de Qa i les files de la taula. Canvi de vocabulari deliberat: «Sorres argiloses» → `arena_limosa` (transicional,
l'àncora de 28°), no `arena` neta. **Topall 3,5 per a tot `GRANULAR_TYPES`** (`terzaghi_calculator.calculate_qa`): Rubí «Graves i
sorres» és `grava` i el topall no disparava (3,0; signat 3,5).

**D. P5b — les capes del segmentador prenen la litologia llegida quan hi ha tants nivells com capes.** Vilanova: descripció buida
→ cap senyal «llim» → φ 28 en lloc dels 25 de l'argila llimosa (la taula per nivell ja ho feia bé via Fase 8b; l'escalar del
portant no). `_annotate_layers_with_lectura_lithology` (només si totes les descripcions són buides i 1..N casa).

**E. La geometria usada pel càlcul també per a Terzaghi-Peck i les files (`ReportData.sondeig_layers_used`).** Tanca la «limitació
coneguda» del 2026-09-06 (vespre): sense `sondeig_layers` a `user_data`, el Qa imprès sortia amb l'N20 GLOBAL (Anciles amb pous a
2,9: Nb 17,6 en lloc dels 26,3 de les graves; ara 3,5 pel topall — el signat 2,0 és l'outlier de judici de `CRITERIS-CALCUL-EVA` §6).

**F. Un rebliment mai és «dens» per un rebuig.** Alcoletge: P-2 rebutja a 1,30 amb el contacte rebliment/lutites a 1,2-1,4 segons
el punt; amb la geometria nova (contacte 1,40) el rebuig queia dins del 1r nivell → règim «dens» → Tipus II i «7-R» (signat Tipus IV,
«5-0»). `geotech_by_criteria`: classe abans que règim; `klass == rebliment` anul·la el rebuig (nota) i la cel·la Nb no porta «-R».
`GeotechCriteria.klass` nou (traçabilitat).

**G. CTE sòl = T-1 per defecte; CTE edificació llegeix «PB+1»; rang de taules per TAULES; data de signatura del wizard; variant
d'assentament.** (1) `classify_soil` torna T-1 sempre (6/6 signats amb taula CTE, també amb rebliment i N20 < 10; la classe de
terreny és una decisió de reconeixement, no un resultat del DPSH); `_determine_soil_class` hi delega (abans dues còpies per N20:
`cte_sol` 1/6). T-2/T-3 requeriran un camp al wizard (avui `cte_sol` només és a la llista compacta de lectura). (2) `parse_floor_count`:
«Pb+1» = 2 plantes (Castellar: el plànol llegit diu «PB+1», l'Eva «Pb+1Pp», signat C-1). (3) `insitu_table_range` (compartit generador +
wizard): DPSH + sondeig si n'hi ha + SPT/MA (la plantilla la imprimeix sempre) → «3 i 4» / «3, 4 i 5»; abans comptava assaigs DPSH
(3 → «3, 4 i 5», 4/7 X). Verificat als `.doc` signats: Rubí, Alcoletge i Linyola tenen exactament DUES taules i tres DPSH; Rubí i
Alcoletge «3 i 4», **Linyola «3, 4 i 5» (incoherència del signat, pregunta 23)**. (4) `data_signatura` (ISO) a `WIZARD_FIELDS`,
`review.html` (input date, càrrega i desat), prefill «avui» a `wizard_service`; el generador la formata com la data de camp
(«29 d'octubre de 2025»: «d'» davant vocal, sense zero; abans «06 de setembre de 2026», 0/7). A M341 és la SEGONA assumpció
documentada (`_metadata.data_signatura_assumida`, del signat, com la Df). (5) `settlement_criteria.SENTENCE_GRANULAR_ALT`
(«inferiors a», Bell-lloc) com a `sentence_candidates[1]`; visible a `_calc_settlement`.

### Implementació

`automation/cte_geomech.py` (`is_rock` ca/es + margues toves; `detect_soil_type` reescrit, `_first_material_stem`),
`automation/geotech_criteria.py` (`klass`, rebliment sense rebuig), `automation/terzaghi_calculator.py` (topall `GRANULAR_TYPES`),
`automation/lectura/tables_report.py` (`depth_from_cell`, `sondeig_layers_from_levels`), `automation/report_data.py`
(`lectura_sondeig_layers`, `_fill_lectura_layer_n20`, `_annotate_layers_with_lectura_lithology`, `SoilLevel.thickness_open`,
`ReportData.sondeig_layers_used`, `_determine_soil_class` → `classify_soil`), `automation/report_generator.py` (autofill P5,
propagació de capes, `_refresh_open_thickness`, asterisc, `insitu_table_range`, `_signature_date`, Nb sense «-R» en rebliment),
`automation/sections/section3_geologia.py` (últim nivell obert amb gruix conegut: «com a mínim»), `automation/cte_classifier.py`,
`automation/settlement_criteria.py`, `automation/wizard.py`, `web/wizard_service.py` (P5 abans del segmentador, rang per taules,
`data_signatura` defecte), `templates/validation/review.html`, `docs/wizard-headless/mesures/mesura_341.py` (`signature_date_iso`).
~480 línies afegides / 180 tretes; cap dependència nova.

### Validació empírica

Dues mesures. **`bloc1a`** (primera passada) va destapar tres efectes secundaris que la mesura `bloc1b` tanca: (1) Secció 3 petava a
4/7 («unsupported format string passed to NoneType.__format__»: gruix conegut amb base `None`) i s'enduia permeabilitat, radó i
sísmica; (2) el gruix obert amb el fons de l'Excel (Alcoletge 0.40* per 0.29*); (3) el rebliment «dens» (F).

`viaA`, 7 projectes, `2026-09-07-m341-peca3` → `2026-09-07-m341-bloc1b` (diff de `_compare_341.txt` per projecte, no titulars):

| | peca3 | bloc1b |
|---|---|---|
| escalars+narrativa (M·C·X·ND) | 181 · 50 · 112 · 33 → 67 % | **200 · 45 · 98 · 33 → 71 %** |
| grup calc | 57 · 5 · 32 · 2 → 66 % | **69 · 2 · 23 · 2 → 76 %** |
| grup resta (`data_signatura_text`) | 11 · 4 · 8 · 7 → 65 % | 16 · 4 · 3 · 7 → 87 % |
| grups A i narr | 74 % / 61 % | 74 % / 61 % (intactes) |
| taules (7 projectes) | 267 · 97 · 99 → 79 % | **286 · 103 · 90 → 81 %** |

Per projecte (escalars / taules): Castellar 76 → 81 / 88 → 91, Rubí 73 → 76 / 91 = , Bell-lloc 78 → 81 / 82 → 84, Linyola 72 → 78 /
88 → 91, Alcoletge 61 → 66 / 73 → 75, Vilanova 53 → 60 / 64 → 69, Anciles 50 = / 74 → 75. `mesura_informe` (3 × 4 variants): només
`cte_edificacio` fila «sòl» mou (T-2 → T-1), a millor als 12 informes.

Cel·les que cauen a MATCH: `cte_sol` 5, `data_signatura_text` 5 (les 2 ES queden X: castellà), `table_dpsh_range` Rubí i Alcoletge,
`cte_edificacio` Castellar, `qa_value` Rubí (3,5), Linyola `geomech_phi` 30 / `geomech_cohesion` 1,0 / `geomech_gamma` 2,20,
Vilanova `geomech_cohesion` 0,10 / `geomech_gamma` 1,90 (φ 25 CLOSE contra «25º»), Anciles c 0,10; taules: sísmica Linyola 1 → 6
MATCH (files, tipus i C), Alcoletge 4 → 6, `geotecnica` Linyola 3 → 7, Vilanova 3 → 6.

**Cel·les que es perden (honestes; registre per revisar-les: `docs/REGISTRE-PERDUES-MESURA.md`, petició del Josep):** Rubí `settlement` 1,50 → 1,80 X (amb la Qa signada 3,5 el 2,5×Nb d'abril ja no dona 1,50:
la calibració d'abril era sobre la Qa equivocada, pregunta 24); Linyola `table_dpsh_range` («3, 4 i 5» amb dues taules: pregunta 23);
Alcoletge `geomech_*` escalars (la veritat de l'extractor és la fila 1, rebliment; el portant ara és la fila 2: bloc 3) i la columna N
(l'SPT-1 de 0,80-1,40 cau per fondària al rebliment amb el contacte a 1,40; l'Eva el posa a les lutites pel material: pregunta 25b).

### Tests

Nous: `tests/test_bloc1_calc_taules.py` (59: classificador 24 casos, `is_rock` ES, topall per tipus, `depth_from_cell`, geometria
Linyola/Vilanova/forats/contacte discrepant, N20 per capa i portant a Df 1,7, gruix obert, T-1, plantes, rang, data, variant, rebliment,
`_refresh_open_thickness`, litologia al segmentador, Secció 3 sense petar). Adaptat: `test_soil_levels_open_bottom` (gruix obert
conegut). Dirigits: 216 verds. Suite sencera: **31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2324 verds / 5
omesos** (244 s; abans 2265 verds).

### Latència / cost

Cost 0 (cap LLM). M341 ≈ 4 min; `mesura_informe` ≈ 1 min; suite ≈ 3 min.

### Limitacions conegudes

- Vilanova i Anciles: el tall llegit no dona el contacte (`de`/`a` buits) → segmentador (0,8 i 2,2 contra 2,20 i 4,00 de l'Eva);
  les potències i els Nb per nivell d'aquests dos continuen X. Només una re-lectura amb la cota del contacte ho mouria.
- Qa: Vilanova 1,5 (φ 25, c 0,10 → Terzaghi) contra 2,5; Anciles 3,5 (topall grava densa) contra 2,0; Alcoletge 3,0 (roca) contra
  3,5. Els tres són judici de l'Eva sobre la fórmula (pregunta 25a; `CRITERIS-CALCUL-EVA` §6).
- E de la roca: defecte «>500» (Linyola signat «>800», Alcoletge «>400» són candidats, no defecte). Tipus sísmic «I» d'Alcoletge i
  «IV» de les graves d'Anciles: judici; no modelat.
- Alcoletge C-0: sense plantes enlloc el defecte és C-1 (pregunta 22). T-2/T-3 sense camp al wizard.
- El castellà (dates «16 de marzo», «Tabla 3 y 4») continua sent el sostre de Vilanova i Anciles (bloc 5).
- El wizard mostra `data_signatura` com a input `date`; no s'ha provat en viu al navegador (cap servidor aixecat avui).

### GO/NO-GO

- ✅ P5 + P6 + CTE + rang + data + variant implementats amb una sola implementació per peça (generador i wizard).
- ✅ Mesurat cel·la a cel·la: 10 punts de calc, 4 de total, 2 de taules; A i narrativa intactes; cap crash.
- ✅ 59 tests nous, 216 dirigits verds.
- ✅ Suite sencera: 31 vermells idèntics / 2324 verds.
- ✅ Commitejat en 4 (GO del Josep 09:35, «anotem les pèrdues amb l'explicació»): `6d2d79b` (P5+P5b+E) · `eb1c2a4` (P6+topall+F) ·
  `375b7c9` (CTE+rang+data+variant+wizard) · docs, tests i runs (hunks partits amb `git apply --cached`; els tres commits de codi
  verificats en worktrees temporals amb els tests dirigits).

### Següents passos

1. Preguntes 22-25 a l'Eva (amb 13, 14, 15 i 1.7).
2. Bloc 2 del PLA (cua d'A: format de milers, plantes, honorífic, article, litologia curta de l'SPT).
3. Bloc 3 (extractor de referència: `geomech_*` d'Alcoletge/Vilanova per fila, municipi, superfícies).
4. Camp `cte_sol` editable al wizard (T-2/T-3) quan l'Eva ho demani.

*Fi entrada 2026-09-07. Bloc 1: P5/P6/CTE/rang/data; calc 76 %, total 71 %, taules 81 %.*

## 2026-09-07 (migdia) — Bloc 2 del PLA: la cua del grup A és FORMAT, no lectura (plantes, honorífic, article del tipus d'edificació, milers, cota, id SPT, municipi del padró; 4 forats de la plantilla amb la preposició dins el valor): A 74 → 77 %, total 71 → 73 %, taules 81 → 82 %, cap pèrdua

### Context

Segon bloc del `docs/PLA-QUE-QUEDA-DESPRES-DE-A-B-I-NARRATIVA-2026-09-07.md` (handoff `_FOR-NEW-YOU-20260907-0930.md`; Josep: «seguim
amb el bloc 2»). El PLA deia que de les 33 X del grup A ≈ 20 eren format (milers, plantes, honorífic, article, litologia curta) i cada
regla tancaria 3-5 cel·les. Referència de mesura: `2026-09-07-m341-bloc1b` (M341) i `2026-09-07-informe-bloc1b` (11 taules). Abans de
tocar cap forat de la plantilla, els 7 signats convertits a text (`soffice --headless --convert-to txt:Text`) i el text exacte al voltant
de cada forat verificat (memòria `feedback_check_signed_phrasing_before_template_change`). Tot el bloc a cost 0 (cap crida LLM).

### Decisions arquitectòniques clau

**Regla comuna: el wizard conserva el text LLEGIT; el generador imprimeix la forma de l'Eva.** Les funcions noves són idempotents (un
valor ja formatat surt igual) i mai inventen (un text que no es reconeix surt tal qual). **Why:** l'Eva ha de veure sencer el que s'ha
llegit («+245 msnm segons plànol topogràfic del ICGC (-0,15m carrer)») per jutjar-lo; l'informe ha de dir «+245.00». Alternativa
rebutjada: formatar al consolidador o a l'overlay del wizard (perdria la font i la nota que la lectura porta).

**A. Plantes: `format_floor_notation` entén el text llegit** (`automation/formatting.py`). Parèntesis = glossa («(planta baixa, 1
nivell)»), «sense …» = negació, número sol després de PB = plantes pis («PB+1» → «Pb+1Pp», Castellar signat), «porxo/porxada» → «Porxo»
(Rubí signat «PB + Porxo»), soterranis/semisòtans → «Ps» amb compte, castellà («SÓTANO, PLANTA BAJA y PLANTA 1» → «Ps+Pb+1Pp»). Ordre
Ps+Pb+NPp+Porxo. Sense cap component reconegut → tal qual («3», «1 (PB)»). `parse_floor_count` (CTE) no canvia: compta sobre el text del
wizard i dona el mateix sobre la forma impresa (test). **Why:** 5 cel·les CLOSE/X eren la mateixa dada amb la notació del lector.

**B. Honorífic del client (`automation/honorifics.py`, nou).** Portada «A petició de:» i frase dels antecedents: «SR./SRA.» davant d'una
persona (4/4 signats: Rubí, Linyola, Alcoletge, Anciles), res davant d'una empresa (3/3: Castellar, Bell-lloc, Vilanova). Empresa per
forma jurídica (S.L., SLU, S.A., SCP…), vocabulari (promocions, grupo, arquitectura, ajuntament…), xifres, «&» o dues persones «X i Y».
Gènere pel NOM DE PILA: llista de noms catalans i castellans (≈ 450) + terminació «-a» com a fallback; nom desconegut sense «-a» → **cap
honorífic** (val més el nom sol que un tractament equivocat en un informe signat). `de_party` fa el forat «en nom {{ client_de }}»:
«de la SRA. …» (Linyola signat), «del SR. …», «de RAMON MITJANA S.L.», ca «d'ABN …». **Why:** 3 cel·les CLOSE/X pel tractament; és una
regla de l'Eva sense excepció als 7. Alternativa rebutjada: LLM (el prompt `llm_synthesis` de la via B ja ho demanava: no determinista).

**C. Article del tipus d'edificació i forat `{{ building_type_de }}`.** Als signats el text després de «…es preveu la construcció » és
«d'un habitatge unifamiliar aïllat modular» (Rubí), «d'un habitatge unifamiliar» (Bell-lloc), «d'un nou habitatge unifamiliar» (Linyola),
«de 3 habitatges unifamiliars d'estructura lleugera, fusta» (Castellar), «de l'ampliació d'un edifici en planta baixa» (Alcoletge), ES
«de una vivienda…», «de 7 viviendas…». La plantilla tenia «d'un» FIX: l'Eva no podia escriure-hi «de 3 habitatges» ni «de l'ampliació»
sense tocar text fix. Ara `building_type_with_article` (gènere pel cap del sintagma: habitatge/edifici m, casa/nau/vivienda f; «-ció»
f; intervencions «ampliació/reforma/tancament…» amb article definit; número o article ja present → tal qual) i `de_building_type`
(«d'un», «d'una», «de l'», «del», «de 3»; ES «de un/una»). `building_type_lower` (mesurat) porta l'article; la plantilla imprimeix
`{{ building_type_de }}`. **Why:** la veritat de l'extractor inclou l'article (és el que hi ha després de «construcció »); sense la
plantilla nova, posar-hi l'article donava «d'un un habitatge».

**D. Superfícies «1.284» i comparadors que llegeixen milers.** `format_area`: milers amb punt, decimals amb coma, enters sense «.0»
(«1284.0» → «1.284» = Castellar signat; «250.91» → «250,91»; «280+86»/«120 m2» tal qual). L'Eva escriu «1.284» a Castellar i «1167» a
Alcoletge (1/2 amb separador): el format imprès és el català normatiu i la mesura ha de comparar NÚMEROS. Els dos comparadors llegien
«1.167» com a 1,167: el run `-bloc2` va guanyar Castellar i perdre Alcoletge (taules 3·2·1 → 2·2·2). `_norm_thousands` (escalars, només
`superficie_*`) i `_as_num` (taules, grups exactes de tres xifres) arreglats → `-bloc2b`. **Why:** un comparador que llegeix «1.284 m²»
com a 1,284 m² mesura una cosa que no existeix. Registrat a `REGISTRE-PERDUES-MESURA.md` (#5, resolta) perquè quedi la traça.

**E. Cota «+188.20».** `format_cota`: signe, punt decimal, dos decimals, primer número del text llegit («+188,20 msnm», «199,50 m»,
«+245 msnm segons … (-0,15m carrer)» → «+245.00»; «-4,0 m (respecte el carrer)» → «-4.00»). Abans Alcoletge, Linyola i Vilanova
imprimien el text sencer a la Taula 1 (MATCH numèric al comparador, però il·legible a l'informe). **Cota d'Anciles NO feta:** el PLA
deia «+1106.40 hi és», però `_NOTES.md` del run 8 documenta que **cap document llegit porta cap cota** (causa I1: els annexos són a
`PDF_V0/ANEJOS/` i la regla «PDF V0 = versió anterior → exclòs» els salta). És lectura (inventari), no format.

**F. Id SPT «SPT-1».** `format_spt_id` a `tables_report` (la lectura → files) i al context de la via B: «SPT1 S1» / «SPT1 P3» / «SPT1» →
«SPT-1», «MA1 S1» → «MA-1» (el punt té la seva columna). 4/4 signats amb SPT escriuen «SPT-1». **Why:** 1 escalar + 3 cel·les de taula.

**G. Municipi del padró i «en el municipi {{ municipality_de }}».** `context['municipality'] = municipality_proper(llegit)`
(«BELL.LLOC D'URGELL (Lleida)» → «Bell-lloc d'Urgell» = signat); el forat de la sísmica porta ara la preposició («d'Alcoletge» signat;
abans la plantilla imprimia «de Alcoletge»). Rubí «Rubí (Barcelona)» queda CLOSE (l'Eva hi posa la província a Rubí però no a Castellar).
**H. `{{ architect_company_de }}`** (mateix paràgraf): «, de l'ARQUITECTURA BOSCH NOVELL» (signat) / «, de 2 Graus» / «, d'ABN …» / res
si no hi ha despatx; abans «de l'{{ architect_company }}» fix imprimia «de l'2 Graus», «de l'BUNYESC …» i «de l', en nom» (Castellar,
Rubí). Fora d'aquest bloc: la frase sencera dels antecedents té tres formes als signats (arquitecte en nom del client / client mateix /
empresa; pregunta 26 i 1.7).

**Descartat amb motiu: `spt_lithology` (S-M al PLA).** La forma curta de l'Eva no és derivable del text llegit: «Limolites i bretxes» ←
«Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells»; «Graves en matriu sorrenca» ← «Grava amb matriu sorrenca»
(paraules seves); Vilanova imprimeix l'SPT de P-1 i l'Eva el de P-3 (pregunta 7); Anciles en castellà. Cap regla que no sigui un LLM:
0 cel·les. Es queda com a candidat futur del wizard.

### Implementació

- `automation/formatting.py` (+130 LOC): `format_floor_notation` reescrit (compatible amb els 5 exemples antics), `format_area`,
  `format_cota`, `format_spt_id`.
- `automation/honorifics.py` (nou, ≈ 150 LOC): `is_company`, `first_name_gender`, `honorific`, `with_honorific`, `de_party`.
- `automation/narrative_criteria.py` (+77): `municipality_de`, `building_type_with_article`, `de_building_type`, taules de caps femenins
  i d'intervencions.
- `automation/report_generator.py` (+30/−10): context `client`, `client_de`, `municipality` (padró), `municipality_de`,
  `building_type_lower` (article), `building_type_de`, `architect_company_de`, superfícies (`format_area`, també a
  `_apply_lectura_tables`), `cota_referencia` (`format_cota`), `spt_test_id` (`format_spt_id`, via A i via B); `_lang` es calcula al
  començament del bloc (abans a mig context).
- `automation/lectura/tables_report.py` (+2): id SPT formatat en construir les files.
- `templates/g3dt-jinja-template.docx` (plantilla del repo; **la de producció `c46bc69` no es toca**): p60 «el SR. {{ architect_name_upper
  }}{{ architect_company_de }}, en nom {{ client_de }}, … la construcció {{ building_type_de }}.»; p348 «en el municipi {{ municipality_de
  }},». Editada amb python-docx sobre els runs (p60 un sol run; p348 runs 0 i 1), verificada rellegint.
- `scripts/compare_prefills_vs_eva.py` (+12), `scripts/compare_tables_vs_eva.py` (+6): milers.
- `docs/wizard-headless/mesures/mesura_341.py`: grup A += `municipality_de`, `client_de`, `building_type_de`, `architect_company_de`.
- Cap dependència nova.

### Validació empírica

Runs `2026-09-07-m341-bloc2b` (M341, `viaA`, 7 projectes) i `2026-09-07-informe-bloc2b` (12 informes), contra `-bloc1b`:

| | bloc1b | bloc2b |
|---|---|---|
| A (M·C·X·ND) | 81 · 11 · 33 · 16 → 74 % | **89 · 7 · 29 · 16 → 77 %** |
| calc / narr / resta | 69·2·23·2 (76) / 34·28·39·8 (61) / 16·4·3·7 (87) | idèntics |
| total escalars+narrativa | 200 · 45 · 98 · 33 → 71 % | **208 · 41 · 94 · 33 → 73 %** |
| 11 taules (dins M341) | 286 · 103 · 90 → 81 % | **292 · 99 · 88 → 82 %** |
| 12 informes (`mesura_informe`) | 127 · 23 · 25 → 86 % | 128 · 22 · 25 → 86 % (Bell-lloc t2 SPT id C → M; Rubí «1414» → «1.414» X → X) |

Cel·la a cel·la (escalars, 10 moviments, tots a millor): Castellar `plantes` C → M, `superficie_parcela` X → M (A 80 → 85 %); Rubí
`plantes` X → M (81 → 88); Bell-lloc `building_type_lower` X → C, `municipality` C → M, `spt_test_id` X → M (80 → 88); Linyola `client`
C → M, `plantes` C → M (M 14 → 16); Vilanova `plantes` C → M. Taules: Castellar «plantes» 2·3·1 → 4·2·0, Rubí 4·1·1 → 4·2·0 («Pb+Porxo»
↔ «PB + Porxo» CLOSE pel comparador de text), Bell-lloc i Linyola SPT id C → M, Linyola i Vilanova «plantes» C → M. **Cap cel·la
perduda** (la provisional d'Alcoletge «1.167» resolta dins el bloc). Text imprès verificat als `.docx`: «A petició de: SR. ALBERT SANS
BONVEHÍ», «en nom de la SRA. SÍLVIA EROLES BALAGUERÓ», «en el municipi d'Alcoletge», «Pb+Porxo», «1.284», «250,91».

Què queda a A (29 X): 9 castellà o veritat-frase de l'extractor (Vilanova/Anciles `municipality`, `data_camp_text`, `expedient`,
`num_dpsh_tests`, `superficie_parcela`/`plantes` d'Anciles: blocs 3 i 5), 8 preguntes a l'Eva (N30 1, cota relativa 2, superfícies
9, data doble, «nou habitatge», «3 habitatges … fusta», tipus d'Alcoletge, `spt_lithology` 7), 5 laboratori sense GTL (bloc 6), 4
arquitecte (1.7 / 26), 3 tipografia del signat (MARTINEZ/BONVEHI sense accent, «(Barcelona)»).

### Tests

`tests/test_bloc2_format_a.py`: 91 (plantes 10 + 4 crus + CTE invariant; àrea 13; cota 10; comparadors ×2; SPT id 9 + `tables_report`;
honorífic 13 + empresa/gènere + `de_party` 7 + `architect_company_de` 4; article 9; municipi 6; plantilla). Dirigits verds: bloc 1
(190), narrativa/taules/consolidate (263), extractor/wizard/plantilles (101). Suite sencera: **31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2415 verds / 5 omesos (238 s)**.

### Latència / cost

0 crides LLM. M341 ≈ 3 min per run (7 projectes); dues passades (`bloc2`, `bloc2b`).

### Limitacions conegudes

- L'honorífic no cobreix noms fora de la llista que no acaben en «-a» (surt sense tractament, mai equivocat). «Andrea» es tracta
  com a femení (ús del país). El nom de la portada segueix l'ordre del document llegit (Anciles «Maria Alba» ↔ signat «Alba Maria»).
- La frase dels antecedents té tres formes als signats; el sistema n'imprimeix una (pregunta 26). «el SR.» de l'arquitecte és text fix.
- `municipality_proper` deixa tal qual un municipi fora del padró («ANCILES» → «d'ANCILES»).
- `format_cota` pren el PRIMER número del text: un text «cota 0 = carrer» donaria «+0.00».
- La plantilla de producció (`c46bc69`) no porta els 4 forats nous: el dia que es fusioni, el generador nou amb la plantilla vella
  imprimiria «d'un un habitatge» (el context porta l'article). Fusionar codi i plantilla junts.
- El bloc 3 (re-extracció) capturarà claus noves (`client_de`, `building_type_de`, `municipality_de`, `architect_company_de`) i
  deixarà de capturar `client` a la frase (la portada la conserva), `building_type_lower` i `municipality` en aquests forats.

### GO/NO-GO

- ✅ Cap cel·la perduda; calc, narrativa i resta idèntics; 12 informes idèntics o millor.
- ✅ Plantilla verificada contra els 7 signats abans i després; text imprès llegit als `.docx`.
- ⏳ GO del Josep al commit (partició suggerida: (1) formatting + honorifics + narrative_criteria + generador + tables_report + tests;
  (2) plantilla; (3) comparadors + M341 grup A; (4) docs i runs).

### Següents passos

Bloc 3 del PLA (deriva de l'extractor: veritats-frase de `municipality`/`data_camp_text` ES, `superficie_parcela` i `plantes`
d'Anciles, `geomech_*` per fila; re-extreure amb els forats `*_de`), preguntes 22-26 a l'Eva, bloc 4 (numeració), castellà quan el
Josep digui.

**Decisió del Josep (2026-09-07, 12:45) sobre la frase dels antecedents:** les tres formes (arquitecte en nom del client / client mateix / empresa) es poden mirar d'inferir del CONTINGUT dels correus (cossos) i dels documents de tipus pressupost (qui demana, qui signa, en nom de qui); serà feina d'LLM, amb poques probabilitats d'encertar-ho sols, i **es farà més endavant** (no ara). Mentrestant, pregunta 26 a l'Eva.

*Fi entrada 2026-09-07 (migdia). Bloc 2: format de la cua d'A, cap pèrdua, A 77 %.*

## 2026-09-07 (tarda) — Bloc 3 del PLA: deriva de l'extractor de referència (taula SPT com a bucle, fila portant pel que DIU el signat, taules per etiqueta i assignació global, capçaleres castellanes, àncora sobre paràgraf amb forat) i veritats re-extretes a TOTES les claus dels 7 signats: total 73 → 74 %, A 77 → 78 %, calc 76 → 77 %, Vilanova 60 → 55 % (honest)

### Context

Tercer bloc del `docs/PLA-QUE-QUEDA-DESPRES-DE-A-B-I-NARRATIVA-2026-09-07.md` (Josep, 12:45: «Seguim amb bloc 3»). Les veritats
(`reference-material/*/validation/eva_reference_values.json`) s'havien extret l'abril del 2026 amb una plantilla que ja no és la
d'avui: des de llavors la taula SPT/MA és un bucle (Fase 8b), la frase de l'assentament és `{{ settlement_sentence }}`, la data de
camp té dues variables i, des d'avui (bloc 2), quatre forats porten la preposició (`*_de`). El 2026-09-06 el refresc va ser
quirúrgic (només narrativa) precisament perquè una re-extracció sencera movia els grups A i calc sense que ningú n'hagués mirat el
perquè. Avui s'ha mirat: `refresh_eva_narrativa.py --all-keys` (65 diferències en 7 projectes) → cada clau que movia s'ha classificat
(plantilla nova / extractor equivocat / castellà) i l'extractor s'ha arreglat per clau abans d'aplicar res. Referència: `-bloc2b`.
Tot a cost 0 (cap crida LLM).

### Decisions arquitectòniques clau

**A. La taula SPT/MA és un bucle també per a l'extractor** (`LOOP_TABLES[6] = spt_ma_tests`, columnes test_id/location/depth_range/
n30/lithology) i la primera fila es projecta a `spt_test_id`, `spt_location`, `spt_depth_range`, `spt_n30`, `spt_lithology`
(`table_flatten`, com `geomech_*`). **Why:** les cel·les `{{ test.* }}` (punt al nom) es saltaven i els cinc `spt_*` queien a None
a la re-extracció (4 projectes × 5 cel·les). Efecte lateral trobat: a Rubí, Linyola i Alcoletge la taula SPT del signat NO era a la
veritat perquè t5 «sondeig» (que aquests projectes no tenen) se l'enduia (decisió C); ara hi són (+15 cel·les d'A).

**B. La fila portant és la que el signat DECLARA, no «l'última».** `bearing_row_from_text`: a la frase que acaba amb «…tensió de
treball/admissible de:» / «…tensión de trabajo de:» (7/7 signats), l'ÚLTIM ordinal de nivell mana («un cop superats els materials
del primer nivell … recolzada sobre els materials del segon nivell sanejat» → 2); sense ordinal, «substrat/sustrato» = última fila;
fora de rang → None (mai s'inventa). `geomech_*` = aquesta fila i **`bearing_layer_idx`** (0-based) entra a la veritat (mètode
`bearing_rule`, grup calc de M341, gen = `_calc.json`). Resultat: Rubí/Bell-lloc 0, Linyola/Alcoletge/Vilanova/Anciles 1: **6/7
MATCH** contra el generador (P2b); Castellar X perquè el signat té UNA fila (bretxes) i el sistema en modela dues. **Why:** la
veritat d'abril tenia la fila 1 (Alcoletge: rebliment; registre de pèrdues #3) i la regla del codi «row[-1]» encertava Alcoletge per
casualitat i hauria fallat a qualsevol projecte que recolzi al primer de dos. Descobert de passada: **Vilanova recolza al 2n nivell
amb pous** («apoyada en los materiales del 2do nivel saneado»), no al primer amb sabates (decisió F).

**C. Aparellament de taules per ETIQUETA i per puntuació global.** `_table_label_fingerprint` (primera cel·la de les tres primeres
files, sense Jinja) puntua a més de la primera fila sencera; l'assignació és global per puntuació descendent (no cobdiciosa en ordre
de plantilla) amb llindar 0,4 (era 0,3). **Why:** a Anciles la fila sencera «n.º de plantas previstas | 5 viviendas con pb + 1pp + bc
…» s'assemblava més a la taula CTE que a la Taula 1, i `superficie_parcela` valia «T-1» i `plantes` «C-1» (i `cte_*` es quedaven
sense); t5 «sondeig» prenia la SPT als tres projectes sense sondeig i la geotècnica a Vilanova. Verificat: els 7 mapes nous coincideixen
amb la simulació (Castellar i Bell-lloc idèntics; aparellaments bons ≥ 0,66, dolents ≤ 0,38).

**D. Capçaleres castellanes i notacions de l'Eva.** «Nº ensayo», «Punto», «Prof. extracción (m)», «Litología» són capçalera
(`_HEADER_ROW_PHRASES`/`_HEADER_CELL_PHRASES`); «N30» NO és un identificador d'assaig (`_detect_header_rows`: ids = P/S/SPT/MA/TP/MI
+ número); «15-R», «--», «38º», «>350» SÓN dades. **Why:** Vilanova/Anciles treien la capçalera com a primera fila SPT, i la
geotècnica d'Anciles perdia el 1er nivell (la fila «2do nivel | 15-R | -- | 2.00 | 0.00 | 38º | >350» comptava 2/7 numèrics).

**E. L'àncora pot ser un paràgraf AMB forat** si l'esquelet té ≥ 6 paraules i no sembla capçalera: «Qa= {{ qa_value }} Kg/cm2 amb un
factor de seguretat inclòs de F=3» ancora `{{ settlement_sentence }}` (queia a None: 7 cel·les de calc). Primer intent (≥ 3 paraules)
enganxava «{{ section_empentes_num }}. EMPENTES DE TERRES» i `empentes_paragraph` prenia la frase de la campanya: corregit abans
d'aplicar. `settlement_sentence` es puntua a M341 pel NÚMERO (com `settlement`): «inferiors a 1.80» i «1.50» s'assemblen un 97 % i
són una X (registre #1).

**F. Assumpció de M341 corregida: Df de Vilanova 0,3 → 1,1.** El signat recolza els pous al 2n nivell (B); com a Linyola/Anciles,
contacte del 2n nivell a la geometria del sistema (segmentador: 0,8; el signat, Tabla 6, dona 1,0/1,6/2,2 per punt) + 0,3. Efecte:
`geomech_phi` 25 → 38 contra 34 (CLOSE), Qa 1,5 → 3,0 contra 2,5 (X, més a prop), `settlement_sentence` M → X (el sistema tracta el
2n nivell com a granular «iguals o inferiors a X cm»; l'Eva «menospreciables o inferiores a 1.0»): registre de pèrdues #7.

**G. `refresh_eva_narrativa.py --keys all|k1,k2`**: la llista blanca s'amplia a totes les claus (o a les indicades); la nota del JSON
diu quines s'han re-extret. Aplicat a les 7 veritats (8/14/9/15/18/12/14 claus). Els forats nous del bloc 2 (`client_de`,
`building_type_de`, `architect_company_de`) NO s'extreuen: p60 és multi-forat amb dos forats adjacents (`{{ architect_name_upper
}}{{ architect_company_de }}`) i apòstrofs tipogràfics que `_extract_multi_vars` no normalitza; `client`, `architect_name_upper` i
`building_type_lower` es conserven de l'anàlisi externa (`intelligent_analysis`). Es deixa: només Bell-lloc té la frase amb l'esquema
de la plantilla (pregunta 26).

**Castellà (bloc 5), documentat i no tocat:** amb el prefix català absent, `municipality_de`, `data_camp_text`, `data_camp_inici_text`,
`num_dpsh_tests` i `expedient` de Vilanova/Anciles són el paràgraf sencer (X). Un diccionari de prefixos CA→ES a l'extractor és la
via quan es faci la plantilla ES.

### Implementació

- `automation/reference_extractor.py` (+171/−45): `LOOP_TABLES[6]`, `_table_label_fingerprint`, `match_tables` global,
  `_anchor_paragraph` (esquelet), `_detect_header_rows` (regex numèric + ids), capçaleres ES, `_flatten_loop_table_concepts(result,
  ref_paras)` (fila portant + `spt_*`), `bearing_row_from_text`, `_bearing_sentence`, `_TENSION_RE`, `_ORDINAL_LEVEL_RE`, mètode propi
  `bearing_rule`.
- `scripts/compare_prefills_vs_eva.py`: `data_camp_inici_text` per data; `bearing_layer_idx` numèric exacte.
- `docs/wizard-headless/mesures/mesura_341.py`: `bearing_layer_idx` al grup calc i a `_gen_value` (de `_calc.json`);
  `settlement_sentence` puntuada com `settlement`; `DF_SIGNAT["vilanova"] = 1.1` amb la cita del signat.
- `docs/wizard-headless/mesures/refresh_eva_narrativa.py`: `--keys`.
- 7 × `reference-material/*/validation/eva_reference_values.json` re-extrets (nota per fitxer amb les claus).
- `tests/test_bloc3_extractor.py` (16): fila portant als 7 signats + fora de rang, capçaleres Anciles/ES, bucle SPT, etiqueta,
  aparellament global (sondeig sense equivalent, Anciles per etiqueta), àncora amb forat i no capçalera, claus noves als comparadors.

### Validació empírica

Tres runs, cada un aïlla una causa (codi del generador INTACTE des de `-bloc2b`):

| run | què canvia | escalars (M·C·X·ND → %) | A | calc | taules |
|---|---|---|---|---|---|
| `2026-09-07-m341-bloc2b` | referència | 208 · 41 · 94 · 33 → 73 % | 89·7·29·16 → 77 % | 69·2·23·2 → 76 % | 292·99·88 → 82 % |
| `-bloc3-veritats` | només veritats | 229 · 42 · 97 · 40 → 74 % | 109·7·32·16 → 78 % | 70·3·23·9 → 76 % | idèntiques |
| `-bloc3b` | + `bearing_layer_idx` al gen, Df Vilanova 1,1 | **234 · 43 · 98 · 33 → 74 %** | **109·7·32·16 → 78 %** | **75·4·24·2 → 77 %** | idèntiques |

Per projecte (bloc2b → bloc3b): Castellar 83 → 82 (bearing X: el signat té 1 nivell), Rubí 78 → 79, Bell-lloc 84 → **87**
(`data_camp_text` X → M: la veritat era la 1a ranura; la 2a diu «1 i 6 d'octubre», com el sistema — el PLA s'equivocava), Linyola
78 → 79, Alcoletge 66 → **75** (`geomech_*` de la fila portant: c 1,00 M, φ 30 M, γ 2,20 C; registre #3 RESOLT), Vilanova 60 → **55**
(la veritat d'abril tenia la fila 1 i el sistema hi coincidia per un error compartit; ara la fila 2: E 450↔550, c 0↔0,50, γ C, φ C),
Anciles 50 → 53 (`superficie_parcela` 1655,01 M, `cte_edificacio`/`cte_sol` M, `superficie_construida` 186,18↔1273,79 X: pregunta 27).
Claus noves: `data_camp_inici_text` 5 M + 2 X (ES), `spt_*` de Rubí/Linyola/Alcoletge 12 M + 3 X (`spt_lithology`: «Sorres llimoses
amb graves (SUCS…)»↔«Graves i sorres», «Lutita gresosa»↔«Lutites», «[il·legible] marró»↔«Llims compactes, lutites alterades»),
`bearing_layer_idx` 6 M + 1 X, `municipality_de` (Alcoletge «d'Alcoletge» M; Rubí C; ES X), `settlement_sentence` (numèric:
Rubí/Bell-lloc X com abans, Vilanova M → X per la Df). 12 informes de `mesura_informe`: idèntics (no llegeixen les veritats).
Suite: Suite sencera: **31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2431 verds / 5 omesos (333 s, amb les mesures en paral·lel)**.

### Limitacions conegudes

- `bearing_row_from_text` llegeix la PRIMERA frase de tensió; un informe amb dues valoracions (sabates i llosa a nivells diferents)
  prendria la primera.
- La fila portant de la veritat i la del sistema es comparen per ÍNDEX: si el sistema modela més nivells que el signat (Castellar),
  la cel·la és X encara que els paràmetres coincideixin.
- p60 multi-forat no s'extreu (G). Castellà (bloc 5).
- Vilanova SPT: el signat diu P-1 = 10 / P-3 = 24 i la lectura el contrari (pregunta 27a); la Df 1,1 és una assumpció (com totes).

### GO/NO-GO

- ✅ Cada moviment de cel·la explicat per una de tres causes (plantilla nova, extractor arreglat, assumpció de Df); cap moviment
  sense causa. Pèrdues al registre (#6 Vilanova `geomech_*`, #7 Vilanova `settlement_sentence`).
- ✅ Taules intactes; 12 informes idèntics.
- ✅ Commitejat en 4 (GO del Josep): `229aef6` (extractor + tests) · `f3e977c` (comparadors + M341 + refresc) · `953eec4` (7 veritats) · docs i runs.

### Següents passos

Bloc 4 (numeració i imatges, mai mesurats), preguntes 22-27 a l'Eva, castellà (bloc 5: plantilla ES + prefixos ES a l'extractor).

*Fi entrada 2026-09-07 (tarda). Bloc 3: veritats re-extretes amb l'extractor arreglat; Alcoletge 66 → 75, Vilanova honest 55.*

## 2026-09-07 (vespre) — Bloc 4 del PLA: numeració i imatges, mesurats per primera vegada (99 veritats `*_num` als 7 signats → grup `fix` 74 M · 25 X → 75 %, cap X és un error de comptar; full de control visual de 7 × 11 imatges; la cau d'imatges compartia el tall de correlació de Bell-lloc amb 5 projectes → clau per contingut)

### Context

Quart bloc del `docs/PLA-QUE-QUEDA-DESPRES-DE-A-B-I-NARRATIVA-2026-09-07.md` (handoff `_FOR-NEW-YOU-20260907-1015.md`; Josep: «seguim
amb el bloc 4 (numeració i imatges)»). La plantilla té 22 forats de numeració (`fig_*_num`, `photo_*_num`, `table_*_num`,
`section_*_num`) que `reference_extractor.py` saltava des del principi (`SKIP_PREFIXES` / `SKIP_SUFFIXES`): cap número s'havia
comptat mai contra els 7 signats; la numeració era una creença. Les imatges: 11 forats, cap veritat comparable per text. Referència:
`2026-09-07-m341-bloc3b` (234 · 43 · 98 · 33 → 74 %; taules 82 %). Cost 0 (cap crida LLM; tot determinista).

### Decisions arquitectòniques clau

**A. La numeració s'extreu amb una funció pròpia, per TIPUS i un-a-un, no pel bucle genèric de paràgrafs.** Primer intent: deixar
de saltar `*_num` i tallar el valor amb `_extract_single_var`. A Bell-lloc, 22/22 correctes; però aparellaments FALSOS on el signat
NO té la secció o la foto: `section_empentes_num` = «2.2. RECONEIXEMENT DEL TERRENY» (similitud 0,65) a 5 projectes,
`section_estabilitat_num` = «3.3.3. Permeabilitat dels materials» (0,60) a 4, `photo_sondeig_num` = la foto de la màquina DPSH (0,59)
als 3 sense sondeig, i la via d'àncora («el paràgraf que segueix») amb confiança 0,15-0,27 a Vilanova i Anciles. Mesurades les
similituds de totes les parelles bones i falses als 7 signats: capçaleres bones ≥ 0,74 (la pitjor, ES «EMPUJE DE TIERRAS») i falses
≤ 0,65 → llindar 0,70 sobre el text SENSE número; als peus el ratio de caràcters no separa «màquina del sondeig» de «màquina DPSH»
(0,59-0,62 fals contra 0,52-0,56 de peus bons com «Detall dels materials recuperats durant la realització del sondeig S-1») → s'hi
afegeix la contenció de paraules de contingut ≥ 0,6 (el fals dona 0,50; els bons 0,67-1,0). Només s'aparellen paràgrafs del mateix
tipus (Figura ↔ Figura, Fotografia ↔ Fotografia, Taula ↔ Taula, capçalera ↔ capçalera), assignació global un-a-un per puntuació
descendent (la regla del bloc 3 per a les taules) i SENSE àncora ni prefix: un forat sense peu al signat queda en blanc. Alternativa
rebutjada: pujar el ratio a 0,7 (perdia «Figura 5. Tall de correlació.» 0,51 i les fotos de materials 0,52-0,56, totes bones).

**B. Empat = blanc, però només si els empatats porten números DIFERENTS.** A Vilanova i Anciles l'índex («2.4.2. Ensayo tipo
S.P.T.\t10») i la capçalera empaten amb el mateix número: no és cap ambigüitat. Amb la regla estricta Vilanova quedava a 2 veritats;
corregida, 7. L'empat real (les tres «Detalle de los materiales recuperados…» de Vilanova al mateix ratio) segueix en blanc.

**C. El valor és el primer token numèric del peu o de la capçalera** (`_numbering_token`: «Fotografia 3. Vista…» → «3»; «4.4.
EMPENTES DE TERRES\t45» → «4.4»; «3, 4 i 5» → None: això és `table_dpsh_range`, no un `_num`). El peu de dues figures («Figura X i
Figura Y») només s'omple si el signat també porta dos números: Castellar, Rubí i Alcoletge tenen UNA figura de situació (topogràfic
i ortofoto juntes) → en blanc, honest.

**D. A M341 la numeració és text EXACTE i el buit del generador amb veritat al signat és una X.** `compare_scalars`, grup `fix`:
«2.4.3» ≠ «2.4.4», «3» ≠ «4», cap CLOSE; `section_empentes_num` = '' amb signat «4.4» (Anciles) és X, no NO_DATA: és la secció que el
signat té i el generador decideix no imprimir.

**E. Test de presència d'imatges a M341** (`image_presence`: present / pendent «[Imatge pendent]» / absent), amb la foto del sondeig
sense sondeig i les vistes generals no triades com a absents (no s'imprimeixen). El primer intent feia `str()` d'un `InlineImage`
viu → docxtpl intenta inserir-lo fora de renderització → `AttributeError: 'Part' object has no attribute 'new_pic_inline'` (la
mesura `-bloc4b` va petar al primer projecte); es detecta pel nom de la classe.

**F. La cau d'imatges es clau pel CONTINGUT del PDF** (`ImageManager._cache_name`: `<prefix>_<nom>_<md5 del fitxer>.jpg`, als 7
punts que abans usaven només `.stem`). Descobert pel full de control visual, no per cap mesura: per md5 dels `word/media/*` dels 7
`.docx` de `-bloc4-num`, **6 dels 7 informes duien el tall de correlació de Bell-lloc** (el primer projecte que va renderitzar un
`tall.pdf` → `tall_tall.jpg`), Alcoletge duia el plànol `A.01.pdf` de Bell-lloc (`planol_A.01.jpg`) i Anciles el retall de situació
de Linyola (`cadastre_sitplan_pl situ.jpg`). `tall.pdf`, `A.01.pdf` i `pl situ.pdf` són noms habituals de l'Eva
(`reference-material/*` els té) i la cau és global (`~/.g3dt/cache/images/`): **`production/g3dt-eva-v1` porta el mateix codi (6
punts)** → a l'ordinador de l'Eva el segon projecte amb `tall.pdf` hereta el tall del primer. Alternativa considerada: clau per
expedient → no invalida quan l'Eva refà el PDF; el hash sí (i dos projectes amb el mateix PDF comparteixen imatge, que és correcte).

**G. Res del generador de numeració s'ha tocat, i la plantilla tampoc.** Les 25 X classificades una a una no són errors de comptar:
donada l'estructura que el generador imprimeix, el número és el que toca. Causes (registre de pèrdues, bloc 4): **10** nombre de
figures del projecte (la plantilla n'imprimeix sempre 3: cadastre + aèria + plànol; els signats en tenen 2 — Castellar, Rubí,
Alcoletge — o 4 — Anciles; `num_project_figures` només en pot afegir), **5** taules de Linyola (= registre #2, «Taula 3, 4 i 5» amb
dues taules; pregunta 23), **5** expansivitat (`include_expansivity` és sempre False — «Determinat per tipus de sol», mai derivat —
i Alcoletge la posa DESPRÉS de l'excavabilitat mentre Linyola i la plantilla la posen abans; pregunta 28), **2** vistes generals de
Rubí (1 foto Google Earth triada per l'Eva; la via A no en tria), **1** empentes d'Anciles (semisoterrani; `has_basement` és del
wizard; pregunta 29), **2** incoherències del signat (Castellar salta la Fotografia 3; Bell-lloc numera «2.4.3» dues vegades).
Regla del handoff respectada: cap número s'ha pujat tocant narrativa, criteris ni plantilla.

### Implementació

- `automation/reference_extractor.py`: `_should_skip_variable` deixa passar `*_num`; `_is_numbering`, `_numbering_token`,
  `_CAPTION_RE` (CA/ES, «i/y Figura N»), `_HEADING_NUM_RE` (accepta l'entrada de l'índex amb tabulador), `_content_tokens` /
  `_containment`, `_numbering_slot`, `_numbering_candidates`, `extract_numbering_variables` (pas 5b d'`extract_reference_values`);
  els bucles genèrics exclouen `_num`. ≈ 160 LOC.
- `docs/wizard-headless/mesures/mesura_341.py`: `_norm_numbering` + branca `fix` exacta a `compare_scalars`; `IMAGE_SLOTS`,
  `image_presence`, `entry["images"]`, taula «Imatges» a `_AGREGAT-341.md`.
- `docs/wizard-headless/mesures/refresh_eva_narrativa.py`: `--label` (nota del JSON per bloc).
- `automation/image_manager.py`: `_cache_name` + 7 substitucions (`{region}_`, `cadastre_sitplan_`, `main_plan_`,
  `main_plan_crop_`, `planol_` ×2, `tall_`).
- Veritats: els 7 `eva_reference_values.json` (+99 claus `_num`; nota «2026-09-07 (bloc 4, numeració)»).
- `tests/test_bloc4_numeracio.py` (20).
- Runs: `2026-09-07-m341-bloc4-num` (veritats noves, generador intacte), `2026-09-07-m341-bloc4b` (cau per contingut; referència
  nova; `_IMATGES.md` + `imatges/*.jpg`, 7 fulls de control), `2026-09-07-informe-bloc4b`.

### Validació empírica

- Dry-run `refresh_eva_narrativa.py --all-keys` abans d'aplicar: només mouen claus `_num` (Castellar 19, Rubí 15, Bell-lloc 20,
  Linyola 15, Alcoletge 15, Vilanova 7, Anciles 8 = 99); cap altra clau.
- Cel·la a cel·la: `-bloc3b` → `-bloc4-num` → `-bloc4b`: **0 moviments fora del grup `fix`**; taules 292 · 99 · 88 → 82 % intactes;
  els 12 informes de `-informe-bloc4b` idèntics a `-bloc2b`.
- Grup `fix` (viaA): **74 M · 0 C · 25 X · 0 ND → 75 %**; per projecte M/X: Castellar 15/4, Rubí 10/5, Bell-lloc 19/1, Linyola 7/8,
  Alcoletge 10/5, Vilanova 7/0, Anciles 6/2. Total viaA 308 · 43 · 123 · 33 → 74 % (el % no es mou: entren 74 M i 25 X).
- Castellà: capçaleres sí (Vilanova 5, Anciles 7 amb «EMPUJE DE TIERRAS» 0,74 i «Sondeo a rotación» 0,84); peus «Fotografía» /
  «Tabla» no (contenció CA/ES) → bloc 5.
- Imatges (presència): 53 present · 8 pendents · 16 absents; els 8 pendents = 6 ICGC sense `utm_x/utm_y` a `user_data` (Rubí,
  Vilanova, Anciles) + 2 sense rol `architect_plan` a `file_mapping.json` (Castellar, Vilanova). Duplicats entre projectes per
  md5: 3 → 0.
- Suite: 31 vermells amb els mateixos noms que `suite-vermells-esperats.txt` / 2449 verds (run abans dels 2 tests d'imatges;
  2451 esperats).

### Tests

`tests/test_bloc4_numeracio.py` (20): Rubí sense sondeig ni empentes → en blanc (no la foto DPSH ni «2.2»); Castellar amb sondeig,
empentes 4.4 / 4.5, Fotografia 4 i «Tall de correlació.»; peu de dues figures només amb dos números; índex + capçalera amb el
mateix número no és empat; empat amb números diferents és blanc; un-a-un; tipus no es barregen («Taula 3 i 4» no omple
`table_lab_num`); capçaleres ES passen i peus ES no; `_numbering_token` ×8; `_should_skip_variable`; mesura `fix` exacta i buit = X;
`_cache_name` (mateix nom, contingut diferent → claus diferents; PDF canviat → clau nova); `image_presence` amb `InlineImage` viu.

### Latència / cost

0 crides LLM. Extracció de numeració: < 0,1 s per signat (la conversió `.doc` → `.docx` amb soffice domina). Mesures: ≈ 3-4 min cada
una; suite ≈ 4 min.

### Limitacions conegudes

- Peus en castellà en blanc fins al bloc 5 (paraula del peu i contenció CA/ES).
- La mesura compara NÚMEROS: no veu que la foto de materials surti dues vegades amb el mateix número («Fotografia 2. … del 1er
  nivell.» / «… del 2n nivell.», mateixa imatge) als 5 projectes amb 2 nivells: la plantilla la té dins de `{%p for level in
  soil_levels %}` (p254-262). Els signats en porten una (o una per sondeig a Anciles). Decisió del Josep (plantilla).
- El full de control és manual i d'una vegada; el test de presència no jutja contingut ni retall. Obert: Linyola retall de situació
  en tira (PDF A4 apaïsat 842×595 amb una altra maquetació; el 38 % esquerre és per a l'A3 1191×842), Alcoletge «màquina DPSH» = foto
  del full de camp, Anciles «màquina del sondeig» = caixes de testimonis i «plànol» = portada d'`IV_PLANOS.pdf` (pàgina 1), Rubí
  «plànol» = foto d'un paper imprès.
- `num_project_figures` només afegeix; la plantilla imprimeix sempre 3 figures del projecte.
- La cau antiga (`tall_tall.jpg`, `planol_A.01.jpg`, …) queda al disc sense que cap codi hi apunti; es pot esborrar.

### GO/NO-GO

- ✅ Cada X de numeració té causa (7 causes, 25 cel·les); cap sense. Registre de pèrdues (bloc 4) i preguntes 28-29.
- ✅ Res es mou fora del grup `fix`; taules i 12 informes intactes.
- ✅ Bug de cau verificat per md5 (3 → 0 duplicats). **Afecta producció**: cal portar `_cache_name` a `production/g3dt-eva-v1`
  quan el Josep decideixi (mai pull a l'Eva).
- ⏳ Commit: GO del Josep, proposta en 4 (extractor + tests · mesura + refresc · veritats · cau d'imatges) + docs i runs.

### Següents passos

Preguntes 23, 28 i 29 a l'Eva (11 cel·les); decisió del Josep sobre el bloc de figures del projecte (10 cel·les) i la foto de
materials per nivell (plantilla); UTM a la via A per a Rubí/Vilanova/Anciles i rol `architect_plan` a Castellar/Vilanova (8 imatges
pendents); tria de fotos i pàgina del plànol (4 imatges errònies); bloc 5 (castellà: peus ES + plantilla ES).

*Fi entrada 2026-09-07 (vespre). Bloc 4: numeració mesurada (75 %, cap error de comptar) i imatges controlades; la cau compartia el tall de correlació de Bell-lloc amb 5 projectes.*

## 2026-09-07 (tarda-3) — Imatges, pas 2: decisions per tipus de figura sobre l'evidència dels 7 signats (A = el que l'Eva ja té al projecte, lector = Claude Code, B només amb UTM i de reserva, mai dibuixem punts), 4 decisions de plantilla del bloc 4 (figures variables, materials una vegada, pastís de Rubí fora, `_cache_name` a producció `123b4f2`); cap codi a experiment

### Context

- Pas 1 (tarda-2, `d041cd8` · `7163f7b`): veritat des dels 7 signats (63 figures/fotos amb peu i ranura), inventari de 291 candidats (FH11 inclosos),
  aparellament phash + NCC i 7 fulls Eva | nosaltres | candidats (`docs/imatges/INVENTARI-I-VERITAT-2026-09-07.md`). El §7 deixava per tipus les opcions
  A (reutilitzar el que l'Eva fa abans del wizard) / B (compondre nosaltres) / C (preguntar-li).
- Pas 2 = revisió amb el Josep, sense codi (handoff `_FOR-NEW-YOU-20260907-1330.md` §5). Feta sobre els 7 fulls i §6-§8. El Josep ha donat GO explícit
  a les decisions de plantilla (b), (c) i (d), ha decidit la (a) tot seguit (pastís fora, gràfic per dades quan n'hi hagi) i no ha esmenat cap fila del repàs per tipus.
- Marc: `feedback_tier_a_extraction_first` (mai en blanc, mai fals: candidats amb font), `feedback_no_pull_eva_success_criterion`, principi del Josep
  (2026-09-07): el pipeline el controla Claude Code, que mira i interpreta les imatges; Python renderitza, retalla i compon.

### Decisions arquitectòniques clau

**D0. Principi: la font és el que l'Eva ja té al projecte; el lector és Claude Code; nosaltres no inventem cap traç.**
Per què: als 7 signats, cada figura (llevat de les fonts externes: ICGC no desat, Google Earth, Sede del Catastro, IGME, llibres) surt d'un fitxer que ja
és a la carpeta abans d'obrir el wizard: PNG compostos a `ANNEXES/ALTRES|OTROS` (Castellar, Rubí, Vilanova: hash idèntic), annexos FH11/PDF (situació,
tall, fotografies) o pàgines del projecte de l'arquitecte. Els punts d'assaig els dibuixa ella sempre (6/7) abans del wizard (memòria
`eva_workflow_annexes_before_wizard`). Alternativa rebutjada: compondre-ho tot per UTM (B primer): 3/7 projectes de la via A no tenen UTM, cap composició
nostra reprodueix la seva (municipi + ampliat, taronja), i dibuixar punts nosaltres sobre un plànol sense georeferència és un risc de fabricació.
Trade-off: depenem del que l'Eva deixa a la carpeta; quan no hi és, «cap font» visible al wizard (mai un placeholder callat).

**D1. `fig_situacio` (7/7): A amb B de reserva; ranura d'1 o 2 imatges.** Ordre de preferència del lector: (1) PNG d'ALTRES amb els dos mapes (3/7
idèntics: `m7.png`, `F1 UBI.png`, `F1 SIT.png`); (2) els dos mapes retallats de l'annex «plànol de situació» (PDF o FH11 → PDF) recompostos en horitzontal
(Linyola 0,82; a Alcoletge i Anciles la figura només hi viu); (3) insets del plànol de l'arquitecte (Bell-lloc: dues imatges, 0,79); (4) B: ICGC
topogràfic + ortofoto per UTM amb rectangle taronja i llegenda «Zona d'estudi». Es retira `_render_situation_plan_left` (retall del 38 % esquerre: 0/7).

**D2. `fig_aerea`: la ranura s'elimina.** 0/7 signats; l'ortofoto va dins situació o dins assaigs. Alternativa «segona imatge de situació»: només
Bell-lloc, i ja ho cobreix D1 (1 o 2 imatges).

**D3. `fig_assaigs` (6/7): A. Retall del dibuix amb punts que l'Eva ja té; mai dibuixem punts.** Fonts vistes als fulls: `m8.png` / `F2 UBI PUNTS.png`
(1,00), Alcoletge `AMP + PLANOL PUNTS/ampliació habitatge v2.png` (planta amb P-1/P-3/P-2: hash feble per línia fina, a ull inequívoc), Linyola
`Punts de Sondeig_Silvia_Jaume.pdf`, Vilanova retall de `pl situació.pdf` (0,98), Anciles inset del corte (0,88). Si hi ha orto-amb-punts i
planta-amb-punts (Vilanova `F2 PUNTS.png` vs. la planta): planta (4/6 signats). Sense cap dibuix amb punts → cap figura (Bell-lloc; però hi té
`A.01 amb punts.pdf` sense usar: pregunta 31). B (punts per UTM sobre el plànol) rebutjada: el PDF no té georeferència i és feina que ella ja fa.

**D4. `fig_projecte` (0-2): Claude tria; retall al dibuix, mai la pàgina sencera.** Secció (Linyola p4 de `2_02B_DG…`), emplaçament sense punts
(Bell-lloc, Vilanova: mateix annex que D3), topogràfic i tipologies (Anciles `IV_PLANOS.pdf` p5, p19-22). Retall amb `detect_drawing_region` /
`crop_to_label` (MCP plànols). Sense candidat clar → 0 figures. Substitueix `fig_main_plan_image` (avui: `A.01.pdf` sencer amb caixetí, una foto d'un
paper a Rubí, la portada a Anciles). Cap regla fixa als 7: pregunta 32.

**D5. `foto_vista` (0-2): A + Claude.** Annex de fotografies (la selecció de l'Eva) → `FOTOGRAFIES/` → PNG d'ALTRES (Rubí: la «vista Google Earth» ÉS
`F3 VG.png`, dins el projecte). Bloc condicional ja existent (peça 3). Criteri: pregunta 19a ampliada.

**D6. `foto_dpsh` / `foto_sondeig`: Claude mira, amb l'annex de fotografies com a pista** (peu «màquina…», 7/7). Tanca les 4 errònies (Alcoletge full
de camp, Anciles caixa de testimonis, Bell-lloc ×2). Sense pregunta.

**D7. `foto_materials`: UNA per informe, fora del bucle de nivells (decisió (c), GO Josep); una per sondeig/punt quan n'hi ha diversos** (Anciles
S-1/S-2, Vilanova P-3 i P-1). Mai per nivell (la plantilla p254-262 avui la repeteix amb el mateix número). Pregunta 33.

**D8. `fig_geologic` (7/7): PNG `*MGEOL*` si hi és (3/7 idèntic) → ICGC WMS per UTM (ja fet; mateix tipus que Linyola/Bell-lloc/Alcoletge) → fora de
Catalunya IGME** (comprovar WMS al pas 3; si no n'hi ha, «cap font», no «pendent»). Llegenda: pregunta 34.

**D9. `fig_tall` (7/7): A, retall de la secció de `tall.pdf`** amb `detect_drawing_region` (mateixa font 7/7, retall 0/7).

**D10. Extres: fora de les ranures; pastís de Rubí FORA de la plantilla (decisió (a), GO Josep, mateixa tarda).** Estabilitat (Castellar,
llibre) només amb dades pròpies → avui cap. El bloc `{%p if show_granulometric %}` de la plantilla porta la IMATGE de Rubí (graves 50,3 / sorres
31,5 / fins 18,2) i també el TEXT de Rubí («NO PLÀSTICS», «tipus SM»): es treu la imatge estàtica i el bloc passa a ser per dades del projecte:
gràfic generat (matplotlib) dels percentatges llegits del GTL del projecte, text (plasticitat, classe SUCS) dels seus resultats, al mateix lloc
(dins la descripció del nivell, peu «Gràfic 1. Distribució granulomètrica…»). Fins que el lector del GTL no doni els percentatges, el bloc no
s'imprimeix mai (com avui). Els 8 media morts (8,9 MB per informe) també fora. Alternativa rebutjada: deixar la imatge i confiar que
`show_granulometric` no s'activi: és un risc de fabricació latent en un fitxer que l'Eva pot tocar.

**D11. Plantilla: nombre de figures variable (decisió (b), GO Josep).** Situació 1-2 + assaigs 0-1 + projecte 0-2 + geològic + tall; numeració per
presència (avui 3 fixes: cadastre, aèria, plànol; signats 2/2/3/3/2/3/4).

**D12. `_cache_name` a producció (decisió (d), GO Josep): FET, `production/g3dt-eva-v1` @ `123b4f2`, sense push.** Cherry-pick de `4afcc80` en un
worktree temporal; el codi ha aplicat net (7 punts `.stem` → `_cache_name`); el test anava dins `tests/test_bloc4_numeracio.py`, que no existeix a
producció → test propi `tests/test_image_cache_name.py`. Per què ara: la cau global per nom de fitxer podia posar el tall, el plànol o el retall de
situació d'un projecte anterior a l'informe de l'Eva (verificat per md5 al bloc 4). Arriba a l'ordinador de l'Eva a la propera instal·lació (mai pull).

**D13. Ordre del pas 3: plantilla petita abans de les fotos.** Esmena a §8.5 del document: `fig_aerea` fora + materials una vegada + numeració per
presència són canvis petits que tanquen X de numeració sols; van primer. Després fotos → tall → assaigs → situació → geològic → projecte + bloc variable.

**D14. Preguntes a l'Eva: 30-34 i 36 al registre; la 35 (vistes) fusionada dins la 19a.** No s'envia res sense el Josep.

### Implementació

- Experiment (`experiment/nivell-a-2026-08`): **cap canvi a `automation/` ni a la plantilla.** Només docs: aquesta entrada, PLA (bloc 4-bis),
  `PREGUNTES-EVA-PENDENTS.md` (30-36, 19a), nota a §7 del document, STATUS, sessió, handoff `_FOR-NEW-YOU-20260907-1450.md`.
- Producció: `123b4f2` (`automation/image_manager.py` +30/−7; `tests/test_image_cache_name.py` +17). Worktree temporal retirat.
- Eines per al pas 3 ja disponibles: MCP plànols (`clients/RV4.eu/tools/mcp-planols`, activat en aquesta sessió): `render_page(crop)`,
  `detect_drawing_region`, `list_pages_with_drawings`, `find_text`, `crop_to_label`, `extract_lines`, `extract_tables`, `read_title_block`.

### Validació empírica

Tot ve del pas 1 (cap mesura nova): situació PNG idèntic 3/7; assaigs amb punts 6/7 (orto 2, planta 4) i font al projecte 6/6; projecte 0-2 (5 figures
en 4 signats); vistes Rubí 1, Vilanova 1, Bell-lloc 2, resta 0; DPSH igual 4/7, sondeig 1/3, materials 6/9, 4 errònies; geològic PNG idèntic 3/7, mateix
tipus 3/7, IGME 1/7; tall mateixa font 7/7, retall 0/7; aèria 0/7. Producció: punts `.stem` a la cau 7 → 0 (l'únic que queda és dins `_cache_name`);
test 1/1 verd (0,5 s).

### Tests

- Producció: +1 (`tests/test_image_cache_name.py`). Experiment: sense canvi (bloc 4: 31 vermells esperats / 2451 verds).

### Limitacions conegudes

- D1-D9 són la proposta del repàs acceptada sense esmenes; les respostes de l'Eva (30-36) poden capgirar-ne alguna (sobretot D3 a Bell-lloc i D7):
  entrada nova que la substitueixi, no edició.
- Res del pas 3 està mesurat: baseline sobre `-bloc4b` amb el codi quiet abans de tocar res (`feedback_measure_baseline_before_coding`); la mesura per
  figura («mateixa font que l'Eva») encara no existeix a M341.
- Fonts externes (ICGC no desat, Google Earth fora d'ALTRES, Sede del Catastro, IGME, llibres): «cap font» al wizard; res no s'inventa.
- MCP plànols és una eina de RV4 (poppler + PIL): a l'ordinador de l'Eva (Windows natiu, sense Claude Code avui) caldria empaquetar-lo o portar les
  3 funcions que usem a `automation/`; decisió del pas 3, no d'aquest.
- FH11 → PDF via soffice (3-14 s per fitxer): a producció cal soffice o un render previ; cau per md5 com les imatges.

### GO/NO-GO

- ✅ Pas 2 tancat: D0-D14 (GO explícit del Josep a (b), (c), (d); files 1-10 sense esmenes).
- ✅ Producció `123b4f2` (test verd, sense push).
- ✅ (a) pastís de Rubí: fora de la plantilla; bloc granulomètric per dades del projecte (peça 1 del pas 3, part de la generació quan hi hagi percentatges llegits).
- ⏳ Preguntes 30-34 i 36: al registre, no enviades.
- ⏳ Pas 3: pendent de baseline i de la peça 0 (mesura per figura).

### Següents passos (pas 3, cada peça mesurable sola, baseline abans)

0. **Mesura per figura a M341**: cel·la «mateixa font que l'Eva» (phash ≤ 10 o NCC ≥ 0,7 contra `docs/imatges/veritat/`) en lloc de presència; reaprofitar
   `docs/imatges/scripts/match.py`; baseline sobre `2026-09-07-m341-bloc4b`.
1. **Plantilla petita** (D11, D7, D2, D10): `fig_aerea` fora, materials una vegada, numeració per presència, pastís i 8 media morts fora
   (el gràfic generat per dades i el text del bloc per resultats, quan el lector del GTL doni percentatges i plasticitat).
2. **Fotos** (D5, D6, D7): skill lector d'imatges + llibreria d'exemplars (`veritat/` + descripció textual + `--exclude` leave-one-out) + annex de
   fotografies com a pista.
3. **Tall** (D9): `detect_drawing_region` sobre `tall.pdf`.
4. **Assaigs** (D3): PNG `*PUNTS*` → planta amb punts → retall de l'annex/inset.
5. **Situació** (D1): PNG → dos mapes de l'annex → insets → ICGC per UTM; retirar `_render_situation_plan_left`.
6. **Geològic** (D8): PNG → ICGC → IGME (comprovar WMS).
7. **Projecte** (D4) + bloc de figures variable a la plantilla.
Handoff: `docs/_FOR-NEW-YOU-20260907-1450.md`.

*Fi entrada 2026-09-07 (tarda-3). Imatges pas 2: decisions per tipus (A = el que l'Eva ja té, lector = Claude Code), plantilla variable i materials una vegada, `_cache_name` a producció.*

## 2026-09-07 (tarda-4) — Imatges pas 3, peça 0: mesura per figura «MATEIXA FONT que l'Eva» a M341 (M · C · X · ND per figura del signat, assignació un a un, sobrants; EXIF i rotació; `--remeasure` sense regenerar) i baseline amb el codi de generació quiet: 12 M · 5 C · 26 X · 13 ND → 40 % (figures compostes 0 %, tall 71 % en C, fotos 57-86 %); escalars, taules i presència idèntics a `-bloc4b`

### Context

- Pas 2 (tarda-3, D13): la primera peça del pas 3 és la MESURA, amb el codi de generació quiet (`feedback_measure_baseline_before_coding`).
  Fins avui M341 només deia si el forat era present / pendent / absent (bloc 4: 53 · 8 · 16); «és la correcta» era un full de control a mà.
- El pas 1 ja tenia la veritat per figura (`docs/imatges/veritat/<slug>/index.json` + imatges a mida real a `~/g3dt-e2e/imatges/veritat/`) i un
  kit d'aparellament calibrat (`docs/imatges/scripts/match.py`: phash + NCC multiescala + PSR; idèntic 1,00, retall 0,90, no relacionat 0,34-0,47).

### Decisions arquitectòniques clau

**D1. La unitat de mesura és cada figura o foto que l'Eva posa al signat, no el forat de la plantilla.** 56 als 7 signats (63 menys les 7 culleres,
les 3 «extra» sense ranura (estabilitat de Castellar, signatura d'Anciles: D10 del pas 2) i la Fotografia 2 duplicada de Vilanova, mateix media).
Per què: la plantilla canviarà (D11: figures variables) i la mesura ha de sobreviure-hi; i mesura el que ella fa, no el que nosaltres imprimim.

**D2. Quatre estats amb la semàntica de M341.** M = la mateixa imatge sencera (phash ≤ 10, orientació EXIF aplicada abans); C = la mateixa font
amb un altre retall o composició (NCC · min(1, PSR/6) ≥ 0,7, veritat dins la nostra i, per a figures, la nostra dins la veritat, escala nativa
inclosa) o la mateixa foto girada 90/180/270; X = una altra font; ND = no posem res (forat absent o «[Imatge pendent]»): res fals imprès, com
als escalars. Percentatge (M + C) / (M + C + X) com `mesura_informe._pct`; l'ND es veu a la seva columna. Els llindars són els del pas 1 (no
s'abaixen: les parelles no relacionades donen 0,34-0,47).

**D3. Assignació un a un, la millor parella primer; les nostres imatges sense figura de l'Eva són «sobrants».** Una imatge nostra no pot
«valer» dues figures (Bell-lloc: dues de situació contra cadastre + aèria; Vilanova: dues fotos de materials contra una nostra → una puntuada, l'altra
ND). Els sobrants no penalitzen el %: s'informen (avui 3: `fig_aerea` a Castellar i Alcoletge, `fig_cadastre` a Linyola, on l'aèria s'ha
emportat l'assignació de situació) perquè són els que desquadren la numeració (bloc 4: 10 X).

**D4. Orientació EXIF abans del phash, i rotacions com a C «rotada».** La foto de materials de Rubí sortia C al primer run (i «RETALL/COMPOSICIÓ»
al pas 1) i és M amb phash 0 quan s'aplica l'orientació del fitxer de camp: era un artefacte d'orientació, no un retall. Una foto girada és la
mateixa font mal presentada: C, no X.

**D5. La mesura viu a M341 i es pot repetir sense regenerar.** Mòdul `docs/wizard-headless/mesures/imatges_font.py` carregat com
`mesura_informe`; per projecte `_compare_imatges.{json,txt}` amb els camins de les nostres imatges (`ours_paths`, trets de l'`InlineImage` viu
del context, mai `str()`); `imatges_font.py --remeasure <run>` re-puntua un run sencer (verificat: sortida idèntica). Per què: iterar el
mesurador costa segons, regenerar costa 10 min.

**D6. Els tres càlculs (`load_gray`, `ncc_max`, `best_scaled`) són còpia literal de `match.py`, no import.** El script del pas 1 porta camins
absoluts d'un scratchpad; el mòdul de mesura ha de viure sol al repo. Cap dels quatre punts calibrats es toca (penalització PSR, `psr = 99`,
escala nativa, `alpha_composite` sobre blanc).

**D7. Cap canvi a `automation/` ni a la plantilla.** Baseline = codi quiet: el run ha de ser idèntic a `-bloc4b` en tot menys la columna nova.

### Implementació

- `docs/wizard-headless/mesures/imatges_font.py` (nou, ≈ 230 línies): `truth_figures`, `our_images`, `score_pair`, `compare_images`,
  `compare_project`, `format_rows`, `agregat_section`, `remeasure_run`, CLI.
- `docs/wizard-headless/mesures/mesura_341.py` (+ 15): càrrega del mòdul, crida per projecte dins `if gen["success"]` (amb `try`: la veritat és
  fora del repo), línia «imatges» al terminal, secció «MATEIXA FONT» a `_AGREGAT-341.md` darrere de la de presència.
- `tests/test_peca0_imatges_font.py` (9 tests, fixtures amb estructura gran + soroll: reescalat → M, retall → C, font diferent → X, res → ND, un a un
  i sobrants, condicionals de `our_images` (`has_sondeig`, `photo_site_text`, pendent, fitxer absent), exclusions de la veritat, girada → C, EXIF
  Orientation=6 → M, i la veritat real de Castellar contra ella mateixa → tot M).
- Runs: `2026-09-07-m341-peca0` (primera passada: sense EXIF, rotació ni camins; conservat) i **`2026-09-07-m341-peca0b` = REFERÈNCIA per a les
  peces 1-7** (mòdul definitiu). Cost 0 LLM, ≈ 10 min per run (viaA + t2).

### Validació empírica

- **Identitat amb `-bloc4b`** (codi quiet): escalars viaA idèntics als 7 (diff buit), total 308 · 43 · 123 · 33 → 74 %, t2 76 %, taules 82 %
  idèntiques per projecte, presència idèntica (8 files), els mateixos 2 avisos.
- **Imatges (`peca0b`, viaA), per figura de l'Eva:**

| projecte | M | C | X | ND | % | sobrants |
|---|--:|--:|--:|--:|--:|--:|
| castellar | 2 | 1 | 3 | 1 | 50 % | 1 |
| rubi | 2 | 0 | 3 | 2 | 40 % | 0 |
| bell-lloc | 3 | 1 | 6 | 0 | 40 % | 0 |
| linyola | 1 | 0 | 5 | 1 | 17 % | 1 |
| alcoletge | 1 | 1 | 4 | 0 | 33 % | 1 |
| vilanova | 2 | 1 | 1 | 5 | 75 % | 0 |
| anciles | 1 | 1 | 4 | 4 | 33 % | 0 |
| **total** | **12** | **5** | **26** | **13** | **40 %** | 3 |

| ranura de l'Eva | M | C | X | ND | % |
|---|--:|--:|--:|--:|--:|
| `fig_situacio` | 0 | 0 | 8 | 0 | 0 % |
| `fig_assaigs` | 0 | 0 | 3 | 3 | 0 % |
| `fig_projecte` | 0 | 0 | 2 | 3 | 0 % |
| `fig_geologic` | 0 | 0 | 4 | 3 | 0 % |
| `fig_tall` | 0 | 5 | 2 | 0 | 71 % |
| `foto_dpsh` | 4 | 0 | 3 | 0 | 57 % |
| `foto_sondeig` | 1 | 0 | 2 | 0 | 33 % |
| `foto_materials` | 6 | 0 | 1 | 2 | 86 % |
| `foto_vista` | 1 | 0 | 1 | 2 | 50 % |

- **Coherència amb el pas 1** (§0.9 del document): fotos idèntiques 12/23 → 12 M de fotos (DPSH 4, materials 6, sondeig 1, vista 1); figures
  compostes cap (situació 0/8, assaigs 0/6, geològic 0/7, projecte 0/5); tall «7/7 mateixa font, 0/7 mateix retall» → 5 C + 2 X (Rubí 0,58 i
  Linyola 0,64 queden sota 0,7 per línia fina). Els 13 ND: 6 pendents (sense UTM: geològic de Rubí, Vilanova, Anciles; sense rol: assaigs de
  Castellar, Linyola, Vilanova), 5 sense ranura nostra (projecte a Vilanova i Anciles ×2, vista a Rubí i Vilanova), 2 segona foto de materials
  (Vilanova, Anciles).
- `peca0` → `peca0b`: una sola fila canvia (Rubí `foto_materials` C → M, D4). `--remeasure` sobre `peca0b`: idèntic.

### Tests

- +9 (`tests/test_peca0_imatges_font.py`, 17 s). Suite sencera: 31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2460 verds / 5 omesos (235 s, amb el run `peca0b` en paral·lel)

### Latència / cost

- Mesura d'imatges: segons per projecte (≤ 12 parelles a 360 px, 16 escales). Run M341 sencer ≈ 10 min (generació), 0 LLM.

### Limitacions conegudes

- **Línia fina (CAD)**: Linyola projecte 0,61 (PSR 6,2), Linyola tall 0,64, Rubí tall 0,58 són la mateixa font a ull i X per mesura. El llindar
  no s'abaixa; la peça 3 (retall de la secció) els ha de portar a M per phash, i això és la prova que la mesura val.
- **Mateix tipus, extensió diferent**: el geològic ICGC per UTM (Linyola, Bell-lloc, Alcoletge) és la mateixa capa que l'Eva amb un altre zoom →
  X (0,31-0,37). La mesura no té l'estat «mateix tipus»; és a posta (la figura de l'informe no és la de l'Eva).
- Cap rotació ni mirall al NCC (només al phash). Cap mesura de retall i mida dins la pàgina (això és al full de control).
- La cullera i les figures extra queden fora; la numeració continua al grup `fix`.
- Els sobrants no entren al %: si la peça 1 treu `fig_aerea`, el % d'imatges no es mou (ho farà el grup `fix`).

### GO/NO-GO

- ✅ Mesura operativa i coherent amb la lectura visual del pas 1.
- ✅ Baseline amb el codi quiet idèntic a `-bloc4b` (escalars, taules, presència).
- ⏳ Suite sencera (suite: 31 vermells esperats / 2460 verds).
- ⏳ Commit (GO del Josep): proposta en 2 — `imatges_font.py` + M341 + test · runs `peca0`/`peca0b` + docs.

### Següents passos

- **Peça 1 (plantilla petita, D2/D7/D10/D11 del pas 2)**: `fig_aerea` fora, materials una vegada fora del bucle, pastís de Rubí i 8 media morts
  fora, numeració per presència. Esperat contra `peca0b`: sobrants 3 → 1 (queda el `fig_cadastre` de Linyola fins a la peça 5), imatges M/C/X/ND
  intactes (la plantilla no canvia cap font), grup `fix` ↑ (les 10 X «nombre de figures» del bloc 4 haurien de baixar), pes dels `.docx` −8,9 MB.
  Abans: `feedback_check_signed_phrasing_before_template_change`.
- Peça 2 (fotos amb el lector): esperat `foto_dpsh` 4 → 7, `foto_sondeig` 1 → 3, `foto_vista` ↑.

*Fi entrada 2026-09-07 (tarda-4). Peça 0: mesura per figura «mateixa font que l'Eva» dins M341 i baseline quiet 12 · 5 · 26 · 13 → 40 %.*

## 2026-09-07 (tarda-5) — Imatges pas 3, peça 1: plantilla petita — `fig_aerea` fora (taula de situació d'una cel·la, peu «Situació de la zona d'estudi»), foto de materials UNA vegada dins el 1r nivell amb la font al peu, bloc granulomètric per dades del projecte (pastís de Rubí fora), 8 media morts fora (plantilla 7,4 MB → 119 KB, informes −8,5 MB); numeració sense l'aèria: grup `fix` 74 M · 25 X → 74 M · 25 X (+9 −9, net 0, com s'havia previst), total 74 % intacte, imatges idèntiques (X 26 → 25, ND 13 → 14), sobrants 3 → 0, pendents 8 → 5

### Context

- Pas 2: D2 (`fig_aerea` fora), D7 (materials una vegada), D10 (pastís fora, bloc per dades), D11 (figures variables: peça 7), D13 (plantilla petita abans
  de les fotos). Peça 0: referència `2026-09-07-m341-peca0b` (imatges 12 · 5 · 26 · 13, sobrants 3, fix 74 M · 25 X).
- `feedback_check_signed_phrasing_before_template_change`: peus de situació i de materials llegits als 7 signats (índexs del pas 1) i posició de la foto de
  materials verificada als signats convertits (Castellar, Bell-lloc: dins el 1r nivell, després de la descripció litològica; Vilanova: una per punt).

### Decisions arquitectòniques clau

**D1. La situació es queda com a TAULA d'una sola cel·la, no com a paràgraf.** Primer intent: taula → paràgraf. El refresc en sec de les veritats
(`refresh_eva_narrativa.py --all-keys`) donava 24-27 diferències per projecte als 7, TOTES de claus de taula (`dpsh_tests`, `spt_*`, `sulfate_*`,
`geomech_*`, `seismic_rows`, `perm_rows`, `cota_referencia`, `bearing_layer_idx`): l'extractor de referència aparella les taules de la plantilla amb les
del signat per ORDRE (`match_tables`), i treure la primera taula les desplaçava totes. Amb la cel·la única (segona cel·la i `gridCol` fora, la primera a
8504 dxa): 0 diferències fora de les 2 esperades. Regla per a la peça 7: no canviar el nombre de taules de la plantilla sense el refresc en sec.

**D2. Peu de situació: «Figura N. Situació de la zona d'estudi.»** Literal a 3/7 (Castellar, Rubí, Alcoletge); Linyola «Ubicació de la parcel·la en
estudi», Bell-lloc «Figura 1 i Figura 2. Detall de la ubicació… Font: Projecte», Vilanova/Anciles en castellà. La cua amb la font («(mapes topogràfic i
ortofoto, ICGC 2025, modificat)», «Fuente: Sede electrónica del Catastro») arriba amb la peça 5, quan la font sigui coneguda. Efecte a la veritat:
Alcoletge guanya `fig_cadastre_num` = 1; Castellar i Rubí no s'aparellen (ratio de text < 0,5 per la cua llarga entre parèntesis): límit de l'extractor
(bloc 4), no d'aquesta peça.

**D3. Foto de materials: `{%p if loop.first %}` … `{%p endif %}` al voltant de la imatge i el peu, DINS el bucle de nivells.** Per què no fora del bucle:
la posició de l'Eva és dins el 1r nivell, després de la litologia i abans d'«Aquests materials han estat caracteritzats…» (Castellar p234, Bell-lloc
p213). Peu: «Fotografia N. Detall dels materials recuperats durant la realització {{ photo_materials_source }}.» amb `photo_materials_source` =
«del sondeig» / «de l'assaig SPT» (ES «del sondeo» / «del ensayo SPT») del generador. Per què un forat i no un `{% if %}` inline: l'extractor de
numeració llegeix el peu de la plantilla sense forats per aparellar-lo amb el signat; el text fix «Detall dels materials recuperats durant la realització»
queda dins 6/7 peus de l'Eva (contenció ≥ 0,6). Una foto per punt/sondeig (Vilanova P-3 i P-1, Anciles S-1 i S-2): D7 del pas 2, a la peça de fotos.

**D4. Bloc granulomètric per dades del projecte.** Fora la imatge de Rubí (`image8.png`, VML `rId15`) i les frases de Rubí («NO PLÀSTICS», «tipus SM»);
ara `{{ level.granulometric_chart if level.granulometric_chart is defined }}` i `{{ level.granulometric_text … }}`. `show_granulometric` continua sent
`False` sempre (el wizard web no l'exposa): el bloc no s'imprimeix fins que el lector del GTL doni percentatges i plasticitat i el generador faci el gràfic.

**D5. 8 media morts i les seves relacions fora del docx.** Queden `image10.jpeg` (segell G3, final del document) i `image11.jpeg` (logo de capçalera).
Plantilla 7,4 MB → 119 KB; informes generats 11,4 → 3,0 MB (Castellar), 10,8 → 2,6 (Linyola), 9,9 → 2,7 (Anciles).

**D6. Numeració: `fig_aerea_num` fora del generador i de la veritat (`--drop`); les figures posteriors −1.** Predicció escrita ABANS del run, a partir de
les cel·les de `peca0b`: +3 M a Castellar, Rubí i Alcoletge (l'aèria hi sobrava), −3 a Linyola, −4 a Bell-lloc i −2 a Vilanova (l'aèria hi compensava la
figura del projecte que no posem), Anciles 0, més Alcoletge +1 (peu de situació) i Bell-lloc −1 (la veritat `fig_aerea_num` desapareix): **net 0**.
Resultat: exacte (18 cel·les mogudes, 74 M · 25 X → 74 M · 25 X). Lliçó: el grup `fix` no pot pujar fins que la plantilla imprimeixi el mateix NOMBRE de
figures que l'Eva (situació 1-2, assaigs 0-1, projecte 0-2): és la peça 7 (D11). La peça 1 treu les coincidències falses.

**D7. Amplada de la situació: 70 mm, com abans.** A 150 mm (provat al run `peca1`) el retall vertical del 38 % de l'annex omple una pàgina sencera. La
peça 5 la posa a tota amplada quan la font sigui la composició horitzontal. El run de referència (`peca1b`) porta els 70 mm; cap cel·la mesurada depèn de
l'amplada (la mesura d'imatges compara fitxers).

**D8. Wizard: `fig_aerea` fora de la vista prèvia** (`review.html` `REPORT_SLOTS`, `web/api.py` `_CACHE_PREFIX_TO_SLOT`); l'ortofoto amb parcel·la es
continua baixant a `_download_icgc_images` (cau; la peça 5 la reutilitza).

**D9. Edició del docx amb lxml, no amb expressions regulars.** El paràgraf del pastís porta un quadre de text VML amb paràgrafs a dins; el primer intent
(regex `<w:p…</w:p>`) va deixar l'XML trencat («Opening and ending tag mismatch»). Script d'un sol ús al scratchpad (no versionat); el resultat es verifica
amb python-docx, docxtpl (`get_undeclared_template_variables`) i 5 tests sobre l'estructura.

### Implementació

- `templates/g3dt-jinja-template.docx` (binari: taula de situació d'1 cel·la, peu, `loop.first` + peu de materials amb forat, bloc granulomètric, rels i
  media). `automation/report_generator.py` (+12: `fig_aerea_num` fora, `lang` una vegada, `photo_materials_source`). `automation/image_manager.py`
  (−22: entrada `aerea`, `setdefault`, bloc de reserva de l'ortofoto). `docs/wizard-headless/mesures/mesura_341.py` (`IMAGE_SLOTS` sense aèria).
  `templates/validation/review.html`, `web/api.py`. `tests/test_peca1_plantilla.py` (5), `tests/test_bloc4_numeracio.py` (1 asserció adaptada).
- Veritats: `refresh_eva_narrativa.py --apply --keys fig_cadastre_num --drop fig_aerea_num` → Bell-lloc (−`fig_aerea_num`), Alcoletge (+`fig_cadastre_num`).
- Runs: `2026-09-07-m341-peca1` (situació a 150 mm) i **`2026-09-07-m341-peca1b` (70 mm) = REFERÈNCIA per a les peces 2-7**.

### Validació empírica

- Refresc en sec: intent 1 (paràgraf) 25 · 25 · 25 · 26 · 27 · 24 · 24 diferències, totes de taules; definitiu 0 · 0 · 1 · 0 · 1 · 0 · 0 (les esperades).
- M341 `peca1` vs `peca0b`: 18 cel·les mogudes, TOTES del grup `fix` (cullera/geològic/tall ×3 a Castellar, Rubí, Alcoletge: X → M; a Linyola ×3,
  Bell-lloc ×4 (amb el plànol), Vilanova ×2: M → X). Total 308 · 43 · 123 · 33 → 74 % IDÈNTIC; A 78 %, calc 77 %, narr 61 %, resta 87 % idèntics;
  taules 292 · 99 · 88 → 82 % idèntiques; t2 156 · 14 · 55 · 11 → 157 · 14 · 53 · 11.

| numeració (gen/eva) | cadastre | plànol | cullera | geològic | tall |
|---|---|---|---|---|---|
| castellar | — | — | 4/3 X → **3/3 M** | 5/4 X → **4/4 M** | 6/5 X → **5/5 M** |
| rubi | — | — | X → **M** | X → **M** | X → **M** |
| alcoletge | — → **1/1 M** | — | X → **M** | X → **M** | X → **M** |
| linyola | — | — | 4/4 M → 3/4 X | 5/5 M → 4/5 X | 6/6 M → 5/6 X |
| bell-lloc | 1/1 M | 3/3 M → 2/3 X | M → 3/4 X | M → 4/5 X | M → 5/6 X |
| vilanova | — | — | M → 3/4 X | M → 4/5 X | — |
| anciles | — | — | 4/5 X → 3/5 X | — | — |

- Imatges: 12 M · 5 C · 26 X · 13 ND → **12 · 5 · 25 · 14** (l'única fila que canvia: la 2a figura de situació de Bell-lloc, abans X contra l'aèria, ara
  ND perquè només posem una imatge); **sobrants 3 → 0**; presència sobre 10 forats: 49 present · 5 pendents (`fig_main_plan` a Castellar i Vilanova,
  `fig_geological` a Rubí, Vilanova, Anciles) · 16 absents.
- Informes generats: peus de materials per informe 1-2 (segons nivells) → 1 als 7; render (Castellar p15, Linyola p15): una foto dins el 1r nivell,
  peu «…del sondeig.» / «…de l'assaig SPT.»; figures 1 situació · 2 plànol · 3 cullera · 4 geològic · 5 tall (= l'Eva a Castellar, Rubí, Alcoletge).

### Tests

- +5 (`tests/test_peca1_plantilla.py`), 1 adaptada. Suite sencera: 31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2465 verds / 5 omesos (187 s, amb el run `peca1` en paral·lel)

### Limitacions conegudes

- **La numeració no puja (net 0) fins a la peça 7**: cal el nombre de figures de l'Eva (situació 1-2, assaigs 0-1, projecte 0-2).
- Peu de situació sense la font; Castellar i Rubí sense `fig_cadastre_num` a la veritat (ratio de l'extractor < 0,5 amb la cua llarga).
- **Text fix de Rubí que encara s'imprimeix a tots els projectes** (vist al render): «Aquest materials s'associa als materials de la unitat NMgo, amb un
  tram superficial alterat…» (dins el bucle de nivells, p330) — Linyola diu «NMgo». Risc de fabricació de la mateixa família que el pastís: a tractar
  amb la geologia llegida (narrativa per criteri), fora d'aquesta peça.
- Materials: una per punt/sondeig (Vilanova, Anciles) no fet; `level.granulometric_*` no es generen (el bloc no s'imprimeix).
- La plantilla de producció (`production/g3dt-eva-v1`) no es toca.

### GO/NO-GO

- ✅ Predicció de numeració complerta cel·la a cel·la; total i taules intactes; imatges intactes; sobrants 0.
- ✅ Suite: 31 vermells esperats / 2465 verds.
- ✅ `peca1b` (70 mm) idèntic a `peca1` en tot el mesurat (escalars viaA i t2, imatges, taules, 7 projectes).
- ⏳ Commit (GO del Josep): proposta en 2 — plantilla + generador + image manager + wizard + M341 + tests + 2 veritats · runs + docs.

### Següents passos

- **Peça 2 (fotos amb el lector)**: skill lector d'imatges + llibreria d'exemplars (`docs/imatges/veritat/` + descripció textual, `--exclude`) + annex de
  fotografies com a pista. Esperat contra `peca1b`: `foto_dpsh` 4 → 7 M, `foto_sondeig` 1 → 3, `foto_materials` X d'Anciles → M i una per punt, vistes ↑.
- Peça 7 (bloc de figures variable) és la que mou el grup `fix`.

*Fi entrada 2026-09-07 (tarda-5). Peça 1: aèria fora, materials una vegada, pastís i media morts fora; numeració net 0 com s'havia previst; informes −8,5 MB.*

## 2026-09-07 (vespre) — Imatges pas 3, peça 2: el LECTOR DE FOTOS és Claude Code (skill `g3dt-llegir-fotos` + full de contacte + annex de fotografies de l'Eva + exemplars dels signats amb leave-one-out), amb precedència Eva > lector > cau IA > patrons: imatges 12 M · 5 C · 25 X · 14 ND → **14 · 5 · 24 · 13** (40 → 44 %); materials 6/9 → **7/9 sense cap X**, sondeig 1/3 → 2/3, vistes 1/4 → 2/4; DPSH 4/7 → 3/7 i la vista de Vilanova ND → X (empats sense criteri: preguntes 37 i 38)

### Context

- Pas 2, D5-D7 i D13: les fotos són la primera peça de contingut perquè el pas 1 hi va veure 4 imatges errònies (Alcoletge full de camp
  com a màquina, Anciles caixa com a màquina de sondeig, Bell-lloc vista 2 i sondeig) i perquè «la tria és trivial amb Claude mirant».
- Peça 1 (referència `2026-09-07-m341-peca1b`): imatges 12 M · 5 C · 25 X · 14 ND → 40 %; fotos DPSH 4/7, sondeig 1/3, materials 6/9, vistes 1/4.
- Avui la tria la fa `select_photos_ai` (graella de miniatures + `claude -p` des de `/tmp`, sense skill, fallback Groq) o, si no, patrons de
  noms de fitxer; la cau `photo_selection.json` sense `source` es reutilitza sense mirar res.

### Decisions arquitectòniques clau

**D1. El lector és un skill de Claude Code amb el runner de la lectura de text, no una crida solta.** `automation/imatges/lector_fotos.py`
crida `automation.lectura.runner._run_claude` (el mateix `claude -p --permission-mode bypassPermissions --model … --effort … --output-format
json`, amb timeout i kill de grup). Per què reutilitzar-lo: ja resol l'autenticació (`G3DT_LECTURA_AUTH`: la sessió de claude.ai o la clau),
l'esforç pinnat (memòria `reference_claude_p_inherits_effort_xhigh`), els zombis i el parseig de l'envolupant JSON. Alternativa rebutjada:
ampliar `select_photos_ai` (`subprocess.run` amb `cwd=/tmp`, sense skill ni exemplars): no té contracte, no es pot mesurar i el prompt viu
dins una constant de Python.

**D2. El contracte de sortida és el dels candidats del nivell A: font + raó + confiança, i «cap font» explícit.** El skill escriu un JSON per
ranura (`site_1`, `site_2`, `dpsh`, `sondeig`, `materials`, opcional `materials_per_punt`) amb `raons`, `confianca`, `cap_font` i `notes`.
Python valida contra l'inventari (índex o camí; una foto per ranura; el que no és candidat cau a `null` amb avís). Mai en blanc silenciós:
`cap_font` diu per què (Rubí: la vista general de l'Eva és una captura de Google Earth que no és a la carpeta de fotos → correctament ND).

**D3. Precedència: Eva (`user`) > lector (`lector`) > cau IA antiga > patrons.** `photo_selection.json` guanya un `source: "lector"` i tres
punts del codi l'accepten com a tria explícita (`ImageManager._load_user_photo_selection`, `ReportGenerator._site_photos_from_user_selection`,
`wizard_service`), de manera que **les vistes generals només s'imprimeixen si algú les ha triades** (peça 3 de la narrativa) i ara el lector
també compta. La tria de l'Eva al wizard continua manant sempre. La selecció anterior es desa a `photo_selection.abans-lector.json`.

**D4. Tres pistes, per ordre de força: l'annex de fotografies de l'Eva, els exemplars dels signats, els rols de SmartScan.** L'annex
(`*_fotografies.pdf`/`.FH11`, existeix abans del wizard: memòria `eva_workflow_annexes_before_wizard`) és la SEVA selecció amb peu; Python
n'extreu les fotos incrustades (logo de 138×138 fora), les aparella amb els candidats per phash i escriu «annex p2 foto #1» al costat de cada
candidat, i renderitza les pàgines perquè el lector en llegeixi els peus. Els exemplars són les fotos dels 7 signats per ranura
(`docs/imatges/veritat/`), **amb leave-one-out**: el projecte mesurat mai veu els seus. Els rols de SmartScan van al prompt marcats com a
orientatius (a Castellar, `photo_site_overview` és una màquina DPSH).

**D5. Un candidat per contingut (md5), i el canònic és el de la subcarpeta.** Castellar té 9 fitxers que són 4 imatges (còpies renombrades de
març: `maquina_dpsh.jpg` = `P1.jpg`…). A la primera passada el lector va gastar 22 torns i 234 s comprovant hashes amb Bash. Ara l'inventari
deduplica i el prompt diu «el mateix fitxer també com a …»; el canònic és el camí amb més carpetes (`FOTOGRAFIES/SONDEIG/x.jpg` abans que
`FOTOGRAFIES/x.jpg`) perquè **el nom de la carpeta és la pista que distingeix la màquina del sondeig de la DPSH** quan les dues són compactes
(Bell-lloc, Anciles). El skill diu explícitament: només Read i Write, no Bash. Castellar: 234 → 52 s.

**D6. `has_sondeig` entra al prompt.** Sense saber-ho, el lector deia «no hi ha cap torre de sondeig» a Bell-lloc i Anciles (les seves màquines
de sondeig són compactes i s'assemblen a la DPSH). El corpus el treu del context del run de referència; en producció, del `ReportData`.

**D7. Model `sonnet`, esforç `medium`, una crida per projecte.** 25-75 s i ≈ 0,3 $ per projecte. No es puja a `xhigh`: el pas 1 va mostrar que
la dificultat no és el raonament sinó tenir les pistes (annex, carpeta, `has_sondeig`); i l'Eva és l'única usuària
(memòria `feedback_no_volume_reasoning`), o sigui que el cost no és l'argument, la latència del wizard sí.

**D8. La mesura del lector és a part de M341.** `docs/wizard-headless/mesures/llegir_fotos_corpus.py` passa els 7 projectes i puntua cada
tria contra la veritat del pas 1 per phash (= Eva / ≠ Eva / ND / sobrant), sense generar cap informe; M341 mesura l'efecte a l'informe.
El runner accepta lots (`--projects`) i refà la taula des dels JSON del run: el segon pla talla als 10 minuts i els 7 projectes en són 8-9.

### Implementació

- `automation/imatges/` (nou, `__init__.py` buit com `ai_pipeline`) + `lector_fotos.py` (≈ 330 línies): inventari amb dedupe i EXIF, annex
  (FH11 → PDF amb soffice, cau per md5; fotos incrustades; render de pàgines), fulls de contacte, exemplars leave-one-out, prompt, crida,
  validació, escriptura amb còpia de seguretat.
- `.claude/commands/g3dt-llegir-fotos.md` (nou): rol, criteri per ranura amb el que diuen els 7 signats, què no va mai a l'informe, les tres
  pistes, procediment (només Read i Write) i el JSON de sortida.
- Precedència: `automation/image_manager.py`, `automation/report_generator.py`, `web/wizard_service.py` (una línia cadascun).
- `docs/wizard-headless/mesures/llegir_fotos_corpus.py` (nou). `.gitignore`: la carpeta de treball `validation/_lector_fotos/`.
- `tests/test_peca2_lector_fotos.py` (8): aparellament amb l'annex, full i prompt, validació (índex/camí/duplicat/repetit/inexistent),
  escriptura amb còpia, `ImageManager` accepta `lector` i rebutja la cau IA, vistes generals amb el lector, exemplars leave-one-out.

### Validació empírica

Run del lector `2026-09-07-lector-fotos-peca2c` (sonnet/medium, leave-one-out; `peca2` = primera passada, conservada):

| projecte | site_1 | site_2 | dpsh | sondeig | materials | s |
|---|---|---|---|---|---|--:|
| castellar | — | — | ≠ (ph 20) | **= Eva** | **= Eva** | 52 |
| rubi | ND | ND | ≠ (ph 28) | — | = Eva | 33 |
| bell-lloc | **= Eva** | **= Eva** | = Eva | **= Eva** | = Eva | 65 |
| linyola | — | — | ≠ (ph 32) | — | = Eva | 31 |
| alcoletge | — | — | ≠ (ph 32) | — | = Eva | 25 |
| vilanova | ≠ (ph 30) | ≠ (ph 32) | = Eva | — | = Eva | 48 |
| anciles | — | — | = Eva | ≠ (ph 30) | **= Eva** | 58 |

M341 `peca2` vs `peca1b`: **imatges 12 · 5 · 25 · 14 → 14 · 5 · 24 · 13 (40 → 44 %)**; per ranura `foto_materials` 6/9 → **7/9 i cap X**
(100 % dels forats amb foto), `foto_sondeig` 1/3 → 2/3, `foto_vista` 1/4 → 2/4, `foto_dpsh` 4/7 → 3/7. Escalars: **una sola cel·la es mou**
(`photo_site_text` de Vilanova, ND → X: ara imprimim dues vistes generals i el signat en porta una altra), total 74 % igual (308 · 43 · 124 · 32);
taules 82 % idèntiques; grup `fix` idèntic (74 M · 25 X); sobrants 0 (Vilanova en té 1: la 2a vista que l'Eva no posa).

Les 4 imatges errònies del pas 1: Alcoletge (full de camp com a màquina) i Anciles (caixa com a màquina de sondeig) resoltes pel lector;
Bell-lloc vista 2 i sondeig resoltes; queda la de Rubí, que no és de fotos (és el «plànol», peça 4).

### Tests

- +8 (`tests/test_peca2_lector_fotos.py`). Suite sencera: 31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2473 verds / 5 omesos (179 s)

### Latència / cost

- Lector: 25-65 s i 0,29-0,40 $ per projecte (sonnet, medium, 5-9 torns). Una crida per projecte, no per foto. La primera passada de Castellar
  (22 torns, 234 s, 0,80 $) era el lector comprovant md5 amb Bash: resolt amb el dedupe i la prohibició de Bash al skill.

### Limitacions conegudes

- **Empats sense criteri** (les dues pèrdues, al registre): quina foto de la DPSH quan n'hi ha una per punt (pregunta 37; el lector agafa la
  primera de l'annex, l'Eva 3 vegades la primera i 3 l'última) i quina vista general (pregunta 38; a Vilanova l'Eva en posa una que NO és a
  l'annex). Fins que l'Eva no respongui no s'hi toca res.
- Anciles `foto_sondeig`: el lector tria `EMPL S1`, el signat porta `EMPL S2` (el mateix equip a l'altre sondeig): mateix tipus d'empat.
- Rubí `foto_vista`: la de l'Eva és una captura de Google Earth desada a `ANNEXES/Altres/F3 VG.png`, fora de la carpeta de fotos. El lector
  només mira la carpeta de fotos: ampliar-lo als PNG d'ALTRES és feina de la peça 5 (situació), que ja els ha de llegir.
- `materials_per_punt` s'escriu però encara no s'imprimeix (una foto per punt: pregunta 33 i plantilla).
- El lector no retalla res (Vilanova retalla la seva vista; Rubí i Vilanova retallen la foto de materials): els retalls són les peces 3-5.
- A l'ordinador de l'Eva cal Claude Code instal·lat (via A, decisió del 2026-08-23); sense ell, el sistema cau a la cau IA i als patrons.

### GO/NO-GO

- ✅ 4 forats guanyats (materials d'Anciles i Castellar exacte, sondeig i vistes de Bell-lloc), 2 perduts i registrats, tots dos per empat.
- ✅ Escalars, taules i numeració intactes fora de la cel·la de Vilanova.
- ✅ Suite: 31 vermells esperats / 2473 verds.
- ⏳ Preguntes 37 i 38 a l'Eva (al registre, no enviades).
- ⏳ Commit (GO del Josep): proposta en 3 — lector + skill + precedència + tests · runner del corpus + `.gitignore` + seleccions del corpus ·
  runs i docs.

### Següents passos

- **Peça 3 (tall retallat)**: `detect_drawing_region` de l'MCP plànols sobre `tall.pdf`; esperat `fig_tall` 5 C + 2 X → M.
- Peça 4 (assaigs: retall del dibuix amb punts), peça 5 (situació), peça 6 (geològic), peça 7 (projecte + bloc variable, que mou el grup `fix`).
- Quan l'Eva respongui la 37 i la 38, revisar el desempat del lector (una línia del skill).

*Fi entrada 2026-09-07 (vespre). Peça 2: el lector de fotos de Claude Code amb l'annex de l'Eva i exemplars leave-one-out; imatges 40 → 44 %, materials 100 %.*

## 2026-09-07 (nit) — Imatges pas 3, peça 3: el TALL DE CORRELACIÓ es retalla (només el dibuix, sense caixetí, llegenda ni mapa), amb el contingut vectorial del PDF i un creixement que s'atura al blanc: `fig_tall` 0 M · 5 C · 2 X → **3 M · 3 C · 1 X (0 → 86 %)**, imatges 14 · 5 · 24 · 13 → **17 · 3 · 23 · 13 (44 → 47 %)**; cap altra cel·la moguda

### Context

- Pas 1: als 7 signats el tall és **mateixa font 7/7 i mateix retall 0/7** — posem la pàgina sencera de `tall.pdf` (amb el
  mapa de situació, la llegenda, la barra d'escala, el logo de G3 i el caixetí) i l'Eva hi posa només la secció.
- Pas 2 (D9) i D13: el tall és la peça següent perquè és una sola figura, la font ja és correcta i el guany és el retall.
- Referència: `2026-09-07-m341-peca2` (imatges 14 M · 5 C · 24 X · 13 ND → 44 %; `fig_tall` 0 M · 5 C · 2 X).

### Decisions arquitectòniques clau

**D1. El retall surt del CONTINGUT VECTORIAL del PDF, no de píxels ni de l'MCP plànols.** `automation/imatges/retall.py`
(`detect_section_region`): (1) **nucli** = els farciments amples (> 25 % de la pàgina) i de color (els estrats; el blanc
es descarta perquè és la caixa de la llegenda); (2) **finestra** = el nucli eixamplat (esquerra 25 % per a l'eix de
cotes, dreta 15 %, amunt 75 % de l'alçada per a les etiquetes «P-1»/«A'», avall 20 %); (3) **creixement fins al blanc**:
dins la finestra s'hi afegeix el que toca el que ja tenim, amb una tolerància del 5 % de l'alçada del nucli, fins que no
queda res contigu. Límits durs: la franja del caixetí (per sobre del primer «TÍTOL/TÍTULO/Data/Fecha/Exp/Pàgina») i les
imatges incrustades (mapa i logo). Per què no l'MCP plànols (`detect_drawing_region`, previst al pas 2): és un servidor
de RV4 amb poppler i PIL que caldria empaquetar per a l'ordinador de l'Eva, i la seva detecció és per llindar de píxels
foscos, més fràgil amb els estrats de color; aquí el PDF ja porta la geometria. Per què no un llindar de píxels: el marc
del full i les línies de guia són negres i sempre entrarien.

**D2. El creixement s'atura al blanc, i això és el que separa la secció de la llegenda.** Provades quatre regles i
mesurades contra els 7 signats: pàgina sencera (0 M, ph mitjà 27), finestra fixa amb tot el text (2 M, 16,6), creixement
sense finestra (2 M, 17,7) i **creixement dins la finestra (3 M, 14,6)**. Amb el creixement, les heurístiques per
detectar la llegenda (la paraula «LLEGENDA/LEYENDA», les files «Nivell N:») no canvien cap resultat i s'han tret: menys
codi i menys maneres de fallar.

**D3. Sense nucli, la pàgina sencera; mai un retall inventat.** `crop_drawing` retorna `None` i `image_manager` cau al
comportament d'abans. La cau porta un prefix propi (`tall_crop_…`) per no xocar amb les pàgines senceres ja guardades.

**D4. Els rectangles degenerats es tracten a mà.** Les línies verticals de les etiquetes «P-1» tenen amplada 0: a
PyMuPDF `box |= r` les **ignora** i `Rect.contains(r)` no s'hi comporta com esperaríem. Per això la unió, la contenció i
el contacte es fan amb coordenades (`_union`, `_inside`, `_touches`). Descobert per un test sintètic, no pels 7 signats
(on les línies tenen gruix): el test valia precisament per això.

### Implementació

- `automation/imatges/retall.py` (nou, ≈ 120 línies): `detect_section_region`, `crop_drawing`, i els tres ajudants de
  geometria. `automation/image_manager.py`: la branca del tall prova el retall i, si no n'hi ha, la pàgina sencera.
- `tests/test_peca3_retall_tall.py` (4): full sintètic amb mapa, llegenda, secció i caixetí (el retall els deixa fora i
  agafa les etiquetes «P-n»), pàgina sense estrats (`None`), escriptura de la imatge, full sense caixetí ni llegenda.
- Run: **`2026-09-07-m341-peca3`** (REFERÈNCIA per a les peces 4-7).

### Validació empírica

| projecte | abans | ara | phash |
|---|---|---|--:|
| bell-lloc | CLOSE | **MATCH** | 8 |
| alcoletge | CLOSE | **MATCH** | 10 |
| anciles | CLOSE | **MATCH** | 4 |
| linyola | MISMATCH | **CLOSE** | 30 |
| castellar | CLOSE | CLOSE | 12 |
| vilanova | CLOSE | CLOSE | 32 |
| rubi | MISMATCH | MISMATCH | 20 |

`fig_tall` **0 M · 5 C · 2 X → 3 M · 3 C · 1 X (0 → 86 %)**; total d'imatges 14 · 5 · 24 · 13 → **17 · 3 · 23 · 13
(44 → 47 %)**. **Cap altra cel·la es mou**: escalars idèntics als 7 (diff buit), total 308 · 43 · 124 · 32 → 74 %,
taules 82 % idèntiques, grup `fix` intacte, presència igual.

### Tests

- +4 (`tests/test_peca3_retall_tall.py`). Suite sencera: 31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2477 verds / 5 omesos (163 s)

### Latència / cost

- El retall és geometria del PDF: mil·lisegons, 0 LLM. La imatge es cacheja per contingut com la resta.

### Limitacions conegudes

- **Rubí no passa pel retall**: SmartScan li assigna el rol `figure_correlation` a `ANNEXES/Altres/F5 TALL.png` (un PNG
  que l'Eva ja va compondre) i el rol mana sobre el PDF. Aquell PNG és una versió més ampla que la del signat → X (ncc
  0,58). Retallar un PNG és una altra feina (bbox de píxels no blancs): queda per a la peça 5, que ja ha de llegir els
  PNG d'`ALTRES`.
- Castellar (ph 12) i Vilanova (ph 32) queden a CLOSE: el retall inclou la barra d'escala i, a Vilanova, una mica més de
  marge del que l'Eva deixa. No s'hi toca: l'Eva mateixa la inclou a 2 dels 7 signats.
- El mòdul només serveix per a plànols **vectorials**. Un `tall.pdf` escanejat no tindria nucli i cauria a la pàgina
  sencera (comportament d'avui, sense regressió).
- Els paràmetres (25 %, 15 %, 75 %, 20 %, 5 %) surten d'un escombrat sobre 7 documents del mateix estudi: són el format
  de G3, no una llei. Si l'Eva canvia de plantilla de plànol, s'han de tornar a mesurar.

### GO/NO-GO

- ✅ `fig_tall` 0 → 3 exactes i cap error nou; la resta de la mesura intacta.
- ✅ Suite: 31 vermells esperats / 2477 verds.
- ⏳ Commit (GO del Josep): proposta en 2 — mòdul + `image_manager` + tests · run i docs.

### Següents passos

- **Peça 4 (assaigs)**: retallar el dibuix amb els punts que l'Eva ja té (PNG `*PUNTS*` o l'annex de situació). El mateix
  `detect_section_region` no hi val (allà el nucli no són estrats): caldrà una variant per a plantes, o el lector.
- Peces 5 (situació), 6 (geològic) i 7 (projecte + bloc de figures variable, que mou el grup `fix`).

*Fi entrada 2026-09-07 (nit). Peça 3: el tall es retalla amb la geometria del PDF; 3 de 7 idèntics al de l'Eva, cap error nou.*

## 2026-09-07 (nit, 2) — Correcció de l'addenda de la peça 2: el senyal de la caixa blava NO és exclusiu de les fotos de sondeig, i **no hi ha cap objecte vermell o taronja col·locat** a cap de les 7 fotos de DPSH dels signats

### Context

L'addenda de la peça 2 (commit `f9d88c2`) afirmava que la caixa de testimonis blava «hi és a les 3 fotos de sondeig i a
cap de les 7 de DPSH». Ho havia mirat a ull sobre miniatures. El Josep va preguntar per l'altra meitat del que recordava
de l'Eva (un objecte **vermell o taronja** per a l'altra màquina), i la comprovació acurada desmenteix part de l'afirmació.

### Mesura

Fracció de píxels saturats per to, **només a la meitat inferior** de la imatge (a la meitat superior el blau és el cel i
contamina la mesura: la primera passada donava «7,4 % de blau» a la DPSH de Linyola, que és cel), més la lectura visual
de les 10 fotos retallades:

| foto | blau (terra) | vermell/taronja (terra) | què és |
|---|--:|--:|---|
| castellar DPSH | 5,14 % | 0,05 % | **objecte blanc i blau a terra** (paper o plàstic) |
| rubi DPSH | 0,00 % | 0,40 % | res |
| linyola DPSH | 0,07 % | 3,66 % | **la carrosseria vermella de la màquina**, i una furgoneta blava al fons |
| bell-lloc DPSH | 0,06 % | 0,34 % | res |
| alcoletge DPSH | 0,08 % | 1,77 % | **la carrosseria vermella de la màquina** |
| vilanova DPSH | 0,00 % | 0,54 % | res |
| anciles DPSH | 0,01 % | 0,06 % | **vareta amb la punta verda** a terra |
| castellar sondeig | 0,92 % | 0,73 % | caixa blava a terra |
| bell-lloc sondeig | 1,02 % | 0,37 % | caixa de testimonis blava a terra |
| anciles sondeig | 0,59 % | 0,09 % | caixa blava i blanca a terra |

### Conclusions

1. **Cap objecte vermell o taronja col·locat a cap de les 7 fotos de DPSH.** El vermell de Linyola i Alcoletge és la
   pintura de la màquina (totes dues són el mateix model vermell); les altres cinc són grogues o negres.
2. **La caixa blava a terra hi és a 3/3 sondeigs, però el blau no és exclusiu**: la DPSH de Castellar porta un objecte
   blanc i blau a terra i la d'Anciles una vareta de punta verda.
3. Per tant el senyal útil **no és el color sinó què és l'objecte** (una caixa de testimonis amb els nuclis i el cartell
   del sondeig). El skill ho diu així ara: «bona pista, no és una prova».

### Implementació

- `.claude/commands/g3dt-llegir-fotos.md`: el paràgraf del senyal, corregit i matisat amb els dos contraexemples.
- `docs/PREGUNTES-EVA-PENDENTS.md`: la pregunta 39 reescrita amb el que hem vist de veritat (i preguntant explícitament
  pel vermell/taronja, que no trobem). Totes dues coses ja commitejades a `e130c9b`.
- Cap canvi de codi ni de mesura: el re-run `-peca2d` ja havia mostrat que aquest senyal no movia cap tria.

### Limitacions conegudes

- L'anàlisi és sobre 10 fotos de 7 projectes. Si l'Eva confirma que sí que hi posa un objecte, caldrà mirar l'annex de
  fotografies sencer (hi ha més fotos de màquina que les que van a l'informe), no només les triades.
- La mesura per to és orientativa: el cel, la pintura de les màquines i les ombres la mouen. La lectura visual mana.

### GO/NO-GO

- ✅ Correcció aplicada al skill i a la pregunta; l'afirmació errònia queda documentada aquí.
- ⏳ Pregunta 39 a l'Eva.

*Fi entrada 2026-09-07 (nit, 2). Correcció: el blau no és exclusiu del sondeig i no hi ha cap objecte vermell o taronja col·locat.*

## 2026-09-07 (nit, 3) — Resposta de l'Eva a la pregunta 39: el senyal de la foto de la màquina de sondeig és una **caixa blava de mocadors** a terra; la del penetròmetre no en porta cap

L'Eva (via el Josep) confirma el que buscàvem a la correcció anterior: **hi posa a propòsit una caixa blava de mocadors
de paper dins l'enquadrament de la foto de la màquina de SONDEIG**, i la foto del penetròmetre **no porta cap objecte
identificatiu**. Això explica els números de l'entrada (nit, 2) i corregeix la meva lectura: el que jo llegia com a
«caixa de testimonis» a les fotos de màquina és aquesta caixa de mocadors (les caixes de testimonis són les safates
blaves grans i surten a les fotos de MATERIALS, no a les de màquina). També aclareix per què no trobàvem res vermell ni
taronja: no n'hi ha.

**Aplicat:** el paràgraf del senyal a `.claude/commands/g3dt-llegir-fotos.md` diu ara exactament què s'ha de buscar
(caixa blava petita i rectangular a terra) i que els altres objectes de color (el paper blanc i blau de la DPSH de
Castellar, la vareta de punta verda d'Anciles) no volen dir res. Pregunta 39 tancada al registre amb la resposta.

**Sense re-mesura:** el re-run `-peca2d` ja havia mostrat que aquest senyal no movia cap tria del lector (les úniques X
de fotos són empats entre punts, preguntes 37 i 38). Es tornarà a passar amb la peça següent que toqui el lector.

*Fi entrada 2026-09-07 (nit, 3). El senyal del sondeig és una caixa blava de mocadors; el penetròmetre no en porta cap.*

---

## 2026-09-08 — IMATGES pas 3, peça 4: la figura dels assaigs surt del full de situació de l'Eva, retallat pel dibuix (0 % → 100 %)

### Context

Quarta peça del pas 3 d'imatges (pla a `docs/imatges/PENDENTS-IMATGES.md` §2, ordre de §6; peces 0-3 als DECISION-LOG
de 2026-09-07 tarda-4, tarda-5, vespre i nit). De les quatre ranures que quedaven obertes, la dels **assaigs**
(`fig_assaigs`, la figura del capítol 2.2 «…i els assaigs realitzats») era la primera per tres raons: 6 dels 7 signats
en porten una, la font existeix als 7 projectes, i era 0 M · 0 C · 3 X · 3 ND — l'única ranura de figura amb forats a
tots els projectes que en tenen.

Baseline (codi quiet): run `2026-09-07-m341-peca3`, imatges 17 M · 3 C · 23 X · 13 ND → 47 %
(`feedback_measure_baseline_before_coding`).

### Decisions arquitectòniques clau

**1. La font és el full «plànol de situació» de l'Eva, no el plànol de l'arquitecte.** El pas 1 ja ho havia dit
(`INVENTARI-I-VERITAT-2026-09-07` §6.3) i D3 del pas 2 ho havia decidit; el que faltava era comprovar-ho amb la mesura.
Ho és: aquell full és l'únic document del projecte que porta els punts d'assaig, i l'Eva el dibuixa **abans** d'obrir el
wizard (memòria `eva_workflow_annexes_before_wizard`). El que hi havia fins ara a `fig_main_plan_image` — la pàgina
sencera de l'`A.01.pdf` amb caixetí, una foto d'un plànol imprès a Rubí, la portada d'`IV_PLANOS.pdf` a Anciles — no
era la figura de l'Eva a cap dels 7.
**Alternativa rebutjada (B de D3): dibuixar els punts nosaltres sobre el plànol de l'arquitecte per UTM.** El PDF no té
georeferència, i sobretot és feina que l'Eva ja fa i que ja tenim feta al projecte. D3 hi és explícit: mai dibuixem
punts.

**2. El nucli del retall és la imatge incrustada més gran, no els farciments.** `detect_section_region` (peça 3) busca
els farciments amples i de color: en un tall de correlació són els estrats, però en una planta no n'hi ha cap. Els
fulls de situació de l'Eva, en canvi, tenen sempre la mateixa estructura — dos mapes petits a dalt, **el dibuix gran a
sota** (36-47 % de la pàgina), la fletxa de nord, el logo i el caixetí — i el dibuix gran és sempre una imatge
incrustada. Per això `detect_plan_region` pren la imatge més gran com a nucli i hi aplica el **mateix creixement fins
al blanc** de la peça 3: hi entren les cotes vermelles i les etiquetes «P-1» que l'Eva dibuixa **a fora** de la imatge,
i en queden fora els mapes, el nord i el logo (zones excloses) i el caixetí (límit dur).
**Que el creixement hi sigui no és cosmètic:** sense créixer, Vilanova es queda a NCC 0,687 (per sota del llindar 0,70)
i amb creixement és **idèntica** al signat (phash 6). L'Eva retalla incloent-hi les cotes que ella mateixa hi ha posat.

**3. Tolerància del creixement 1 %, no 5 %.** A la peça 3 la tolerància és el 5 % de l'alçada del nucli, però allà el
nucli és una franja d'estrats; aquí és el dibuix sencer, i el mateix percentatge dona una tolerància molt més gran en
punts. Mesurat als 7 projectes: **0,5 %, 1 % i 2 % donen exactament el mateix resultat** (6 M); al 5 % el creixement
salta a la llegenda d'Anciles (M → X) i al 10 % també als mapes de Castellar i Rubí (M → X). L'1 % és el mig d'un
altiplà, no una vora.

**4. Ordre de candidats propi, amb la carpeta d'annexos abans que l'arrel.** `_find_situation_plan` (que serveix la
ranura de cadastre) prova l'arrel abans que `PDF/ANNEXES/`, i no s'ha tocat: la peça 5 la reescriurà sencera i
qualsevol canvi ara mouria `fig_situacio`. La peça 4 fa servir una llista pròpia (`_situation_plan_candidates`) amb
l'ordre invers, perquè el `pl situ.pdf` de l'arrel és l'export «imprimible» del FreeHand, **amb el raster tallat en
centenars de tires** (Vilanova: 1.119 imatges, la més gran de 739×51), mentre que el de `PDF/ANNEXES/` porta cada
imatge sencera. Amb el de l'arrel no hi ha nucli i `detect_plan_region` retorna `None`, de manera que el filtre d'àrea
(≥ 15 % de la pàgina) ja tria bé tot sol; l'ordre només estalvia feina. **A 4 dels 7, el rol `situation_plan` de
SmartScan apunta justament al fitxer de l'arrel**: passa al següent candidat sol, sense tocar SmartScan.

**5. Res de reader ni de patrons de nom.** La peça 2 va necessitar Claude Code perquè triar entre 30 fotos és un judici.
Aquí no: la regla «la imatge més gran del full de situació» és determinista i no falla enlloc. Els PNG compostos
d'`ALTRES` (Castellar `m8.png`, Rubí `F2 UBI PUNTS.png`) donen el mateix resultat però **no tenen cap patró de nom
comú** (`m8` no diu res) i a Vilanova el PNG equivalent (`F2 PUNTS.png`) és una ortofoto que l'Eva **no** va fer servir:
una regla per nom hi encertaria per sort a dos projectes i s'equivocaria al tercer. La pregunta 36 a l'Eva (deixa sempre
els PNG a `ALTRES`?) queda oberta però ja no bloqueja aquesta peça.

### Implementació

| Fitxer | Què |
|---|---|
| `automation/imatges/retall.py` | `detect_plan_region(page)` + `crop_plan(pdf, out)`, +105 línies. Comparteix `_touches`, `_inside`, `_union`, `_covered` i `TITLE_BLOCK_WORDS` amb la peça 3 |
| `automation/image_manager.py` | `_situation_plan_candidates(roles)` (llista ordenada) i bloc `3b-0` abans de la via antiga, que passa a `elif`. +50 línies |
| `tests/test_peca4_retall_planta.py` | 6 tests nous amb fulls sintètics |

**Gotcha nou i important: els fulls de l'Eva són A3 VERTICAL girats 270°.** `page.rect` els dona girats (1191×842) però
`get_images`, `get_drawings` i `get_text` donen coordenades **sense girar** (842×1191). Tota la geometria de
`detect_plan_region` es fa sense girar (amb `page.mediabox`) i el rectangle final es passa per `page.rotation_matrix`.
El primer intent, fet amb `page.rect` com fa la peça 3, retallava una franja qualsevol. `detect_section_region` **no
s'ha tocat**: els `tall.pdf` no van girats i qualsevol canvi allà mouria les 3 M · 3 C de `fig_tall`.

### Validació empírica

Run de referència: `2026-09-08-m341-peca4` (viaA, 7 projectes), contra `2026-09-07-m341-peca3`.

| ranura | abans | després |
|---|---|---|
| `fig_assaigs` | 0 M · 0 C · 3 X · 3 ND → **0 %** | **4 M** · 0 C · 0 X · 2 ND → **100 %** |
| `fig_projecte` | 0 M · 0 C · 2 X · 3 ND → **0 %** | **2 M** · 0 C · 1 X · 2 ND → **67 %** |
| **total imatges** | 17 M · 3 C · 23 X · 13 ND → **47 %** | **23 M** · 3 C · 19 X · 11 ND → **58 %** |

Per projecte: Castellar 50 → 57 %, Rubí 20 → 40 %, Bell-lloc 67 → 78 %, Alcoletge 33 → 50 %, Vilanova 60 → 67 %,
Anciles 50 → 67 %; Linyola 33 % sense moure's.

Els 6 encerts són **phash ≤ 10, la mateixa imatge**: Castellar, Rubí, Alcoletge i Anciles a `fig_assaigs`; Bell-lloc i
Vilanova a `fig_projecte`. Que dos vagin a `fig_projecte` no és cap accident de la mesura: Bell-lloc **no té** figura
d'assaigs (D3) i la seva Figura 3 és aquest mateix dibuix, i a Vilanova l'Eva fa servir dos retalls del mateix dibuix —
la Figura 2 «Situación del emplazamiento» (el retall ample, amb les cotes: el nostre) i la Figura 3 «Situación de los
ensayos» (un retall més estret). Amb una sola ranura a la plantilla només se'n pot omplir una.

**Cap altra cel·la s'ha mogut.** El `diff` dels escalars per projecte és buit als 7, i les 28 primeres línies de
l'agregat (escalars per projecte, per grup, taules, idioma) són idèntiques caràcter a caràcter llevat del nom del run:
escalars 74 %, taules 82 %, `fix` 74 M · 25 X sense canvi. La numeració no es mou perquè compta ranures, no contingut.

### Tests

6 nous (`tests/test_peca4_retall_planta.py`): el retall és el dibuix amb les cotes de l'Eva; els mapes, el nord i el
logo queden fora; **un full girat 270° dona el mateix rectangle que el mateix full dret, passat per la matriu**;
l'export amb el raster en tires no dona retall; sense imatges tampoc; `crop_plan` escriu la imatge.
Suite sencera: **2483 passats, 31 vermells amb exactament els mateixos noms** que
`docs/wizard-headless/mesures/suite-vermells-esperats.txt` (`feedback_compare_test_names_not_counts`).

### Latència / cost

0 LLM. El retall és PyMuPDF sobre una pàgina: mil·lisegons, i queda a la cau (`plan_crop_<nom>_<md5>.jpg`, prefix propi
perquè no xoqui amb el `cadastre_sitplan` del mateix PDF).

### Limitacions conegudes

1. **El peu de la figura encara és el de Bell-lloc.** La plantilla diu «Figura N. Ubicació de l'habitatge a l'interior
   de la parcel·la. Font: Projecte», que és exactament el peu del signat de Bell-lloc (i el de Vilanova traduït) però
   **no** el dels quatre on ara hi posem la figura d'assaigs («…i els assaigs realitzats»); a Castellar i Rubí, a més,
   la imatge és una ortofoto i «Font: Projecte» no hi escau. Amb una sola ranura no es pot arreglar sense trencar els
   dos on el peu SÍ que és correcte: **ho arregla la peça 7** (D11, nombre de figures variable), que és qui parteix la
   ranura en `assaigs` i `projecte`. Queda anotat a `PENDENTS-IMATGES.md`.
2. **Linyola.** L'Eva no va fer servir el seu propi annex sinó la planta del projecte de l'arquitecte
   (`Punts de Sondeig_Silvia_Jaume.pdf`) amb icones de punt petites. Els dos dibuixos existeixen al projecte i cap
   senyal determinista els distingeix; el que ara hi posem és la planta amb punts del seu annex — el contingut correcte,
   una altra font. Amb el llindar de la mesura és X (0,575). Candidat clar per al lector de la peça 7.
3. **`fig_assaigs` a Vilanova segueix ND** (2 ND de la ranura: Vilanova i Linyola): la nostra única imatge se n'ha anat
   a `fig_projecte`, que puntua més alt. Es resol amb la peça 7, no abans.
4. **Fulls només en `.FH11`.** Als 7 del corpus l'export PDF hi és sempre. Si a producció l'Eva no exporta el PDF, cal
   `soffice` (bloqueig de fons 4 de `PENDENTS-IMATGES.md`); avui es cau a la via antiga sense avisar.

### GO/NO-GO

- ✅ La font és la que l'Eva fa servir, verificada figura a figura contra els 7 signats (phash, no «a ull»).
- ✅ 6 de 7 projectes guanyen una figura idèntica; cap projecte en perd cap.
- ✅ Cap escalar, cap taula, cap cel·la de narrativa i cap número de figura s'han mogut.
- ✅ Suite amb els mateixos vermells esperats.
- ⏳ Peu de la figura i partició de la ranura: peça 7.
- ⏳ Linyola: lector, també a la peça 7.

### Següents passos

Segons l'ordre de `PENDENTS-IMATGES.md` §6: **retall de PNG** (pendent 2, petit, el necessiten la peça 5 i el tall de
Rubí) → **peça 6** (geològic; 3 dels 7 amb el PNG `*MGEOL*` sense tocar les UTM) → **peça 5** (situació) → **peça 7**
(figures del projecte, peu i numeració variable). Les UTM des de la referència cadastral
(`_FOR-NEW-YOU-20260907-2000` §4.1) continuen desbloquejant la 6 i part de la 5.

*Fi entrada 2026-09-08. La figura dels assaigs surt del full de situació de l'Eva, retallat pel dibuix: 0 % → 100 %.*

---

## 2026-09-08 (2) — El «retall de PNG» del pendent 2 no calia: els PNG ja vénen sense marge, i el forat de Rubí era una precedència de rol (`fig_tall` 86 % → 100 %)

### Context

`PENDENTS-IMATGES.md` §3 tenia com a pendent 2 un **retall de PNG** («bbox de píxels no blancs») amb la nota «el
necessiten la peça 5 i el tall de Rubí (`F5 TALL.png`, avui X)», i el `_FOR-NEW-YOU-20260907-2000` §3 el posava com a
segona tasca, just després de la peça 4. Abans d'escriure'l s'ha mesurat si feia falta
(`feedback_measure_baseline_before_coding`). **No fa falta, i el forat que havia de tapar tenia una altra causa.**

### Decisions arquitectòniques clau

**1. El retall de blanc dels PNG d'`ALTRES` NO s'escriu.** Els PNG d'`ALTRES` dels 7 projectes tenen entre el 2 i el
6 % de marge blanc, i el retall no canvia cap veredicte de la mesura. Les tres imatges que la peça 5 vol fer servir en
primer lloc — `m7.png` (Castellar), `F1 UBI.png` (Rubí), `F1 SIT.png` (Vilanova) — ja són **MATCH amb phash 0 tal com
són**, i retallades passen a phash 2 (segueixen MATCH, però una mica pitjor). Escriure l'eina hauria estat codi mort
que empitjora tres cel·les.
**Per què la nota deia el contrari:** el pas 2 va inferir el marge blanc mirant els fulls, sense mesurar-lo. Queda
corregit al document.

**2. El forat del tall de Rubí no era un marge: `F5 TALL.png` és un DIBUIX DIFERENT del signat.** Vist a ull i
confirmat per la mesura: el PNG té **dos nivells** (N1 graves i sorres / N2 gresos) amb llegenda i barra d'escala, de
204 a 212 m; el que l'Eva va signar té un **nivell únic marró amb la cota de fonamentació en vermell discontinu**, de
208 a 213 m, i valors de Nb diferents (P-2: Nb=48 al signat, Nb=46/57 al PNG). Cap retall de blanc pot convertir l'un
en l'altre.

**3. La causa real és la precedència de rols, i s'arregla invertint-la.** El bloc «SmartScan figure roles» corria
**abans** que el de correlació, i `ROLE_TO_FIGURE_VAR` hi tenia `figure_correlation → fig_correlation_image`. A Rubí
aquest rol apunta a `ANNEXES/Altres/F5 TALL.png` i per això el `tall.pdf` no s'arribava a retallar mai. Rubí és
**l'únic dels 7 amb aquest rol**; tots set tenen `correlation_section → tall.pdf`. Ara `figure_correlation` surt de
`ROLE_TO_FIGURE_VAR` i es prova **al final** del bloc de correlació, com a últim recurs quan no hi ha cap `tall.pdf`
per retallar: no es perd la capacitat, només l'ordre.
**Alternativa rebutjada: canviar SmartScan** perquè no assigni el rol. El rol no és fals — el PNG existeix i és un tall
de correlació; el que era fals era donar-li prioritat sobre el document que l'Eva retalla als 7 signats (peça 3, D9).
Tocar SmartScan hauria mogut `file_mapping.json` i els seus tests, i el problema no és seu.

### Implementació

`automation/image_manager.py`: `figure_correlation` fora de `ROLE_TO_FIGURE_VAR` (amb el perquè al costat) i provat
com a últim recurs dins el bloc de correlació (+10 línies). 1 test nou a `tests/test_peca4_retall_planta.py`.

### Validació empírica

Run `2026-09-08-m341-tall-rubi` contra `2026-09-08-m341-peca4` (peça 4):

| | abans | després |
|---|---|---|
| `fig_tall` | 3 M · 3 C · 1 X → 86 % | 3 M · **4 C** · **0 X** → **100 %** |
| rubi | 2 M · 0 C · 3 X · 2 ND → 40 % | 2 M · 1 C · 2 X · 2 ND → **60 %** |
| **total imatges** | 23 · 3 · 19 · 11 → 58 % | 23 · **4** · **18** · 11 → **60 %** |

Rubí: NCC 0,581 (X) → **0,913 (C)**. Cap altra cel·la moguda: `diff` dels escalars buit als 7, agregat idèntic llevat
del nom del run. `fig_tall` és la primera ranura sense cap X als 7 projectes.

Mesura del retall de blanc (probe, no s'ha desat codi): marges del 2-6 % als 12 PNG de Castellar, 10 de Rubí i 8 de
Vilanova; cap canvi de veredicte; `m7.png` / `F1 UBI.png` / `F1 SIT.png` MATCH ph=0 crus i ph=0-2 retallats.

### Tests

1 de nou (`figure_correlation` fora del mapa de rols, la resta del mapa intacta). Suite sencera: **2484 verds, 31
vermells amb els mateixos noms** que `suite-vermells-esperats.txt`.

### Limitacions conegudes

- El rol `figure_situation_map` de Rubí apunta a `F1 UBI.png`, que **és** la figura de situació del signat (phash 0),
  però avui no s'hi arriba perquè `fig_cadastre_image` ja està ple abans. És la peça 5, no aquesta entrada.
- Si algun dia un projecte no té `tall.pdf` i sí un PNG compost, s'imprimirà el PNG sense retallar: cap dels 7 hi cau.

### GO/NO-GO

- ✅ Mesurat que el pendent 2 no calia, abans d'escriure'l.
- ✅ La causa real trobada i arreglada; `fig_tall` queda a 100 % (0 X).
- ✅ Cap escalar, taula ni numeració moguts; suite amb els vermells esperats.

### Següents passos

`PENDENTS-IMATGES.md` §6 queda: **peça 6** (geològic) → **peça 5** (situació) → **peça 7** (projecte, peu i numeració).
El pendent 2 es tanca com a «no calia».

*Fi entrada 2026-09-08 (2). El retall de PNG no calia; el tall de Rubí era una precedència de rol: `fig_tall` 100 %.*

---

## 2026-09-08 (3) — IMATGES pas 3, peça 6: el mapa geològic que l'Eva ja ha compost va primer (0 % → 50 %); la recepta ICGC no es toca, i queda mesurat per què

### Context

Sisena peça del pas 3 (ordre de `PENDENTS-IMATGES.md` §6, ara que el pendent 2 s'ha tancat com a «no calia»,
DECISION-LOG 2026-09-08 (2)). `fig_geologic` era la ranura amb més forats de totes: 0 M · 0 C · 4 X · 3 ND → **0 %**,
i l'única figura que surt als 7 signats sense encertar-ne cap.

Baseline: `2026-09-08-m341-tall-rubi`, imatges 23 M · 4 C · 18 X · 11 ND → 60 %.

### Decisions arquitectòniques clau

**1. Si l'Eva ja té el mapa compost al projecte, és aquell.** A Castellar, Rubí i Vilanova desa el retall de l'ICGC
**amb la llegenda de les unitats** com a PNG al costat dels annexos (`m12 mgeol.png`, `F4 MGEOL.png`), i no s'assembla
al que ella va signar: **és el mateix, phash 0**. És la mateixa forma que ja tenien la peça 2 (l'annex de fotografies
és la seva selecció) i la peça 4 (el full de situació és el seu dibuix): D0 del pas 2, «la font és el que l'Eva ja té».

**2. La regla és el NOM del fitxer, no el rol de SmartScan.** Un fitxer d'imatge que porti «geol» (sense distingir
majúscules). Als 7 projectes dona **exactament un candidat als tres que en tenen i cap als altres quatre**; els `.FH11`
(la font FreeHand del mateix dibuix) no compten perquè no són inseribles.
**El rol `figure_geological_map` s'ha provat i NO serveix:** encerta a Rubí i Vilanova, però a Castellar apunta a
`M1.png` i a Linyola a una imatge extreta d'un correu (`validation/msg_attachments/…/2_02B_DG_Silvia_Jaume_img0.jpeg`)
— 2 errònies de 4, contra 3 de 3 bones pel nom. És el tercer cop en dos dies que un rol de figura de SmartScan porta
a una imatge que no és la del signat (vegeu `figure_correlation` a l'entrada 2026-09-08 (2)).

**3. Els paràmetres de la recepta ICGC NO es toquen, i ara se sap per què no serveix de res tocar-los.** El Josep va
demanar reproduir exactament `get_geological_map_with_terrain` (base topogràfica + `unitats-geologiques-50000` al 0,65
amb `alpha_composite`, buffer 700 m, 800×600, EPSG:25831, punt vermell de radi 10 px) perquè és la imatge que l'Eva va
aprovar. S'ha mesurat, només per saber-ho, què passaria movent el buffer als tres signats que fan servir aquest tipus
de figura — Linyola, Bell-lloc i Alcoletge:

| buffer | linyola | bell-lloc | alcoletge |
|---|--:|--:|--:|
| 150 m | 0,34 | 0,31 | 0,31 |
| 250 m | 0,39 | 0,39 | 0,38 |
| 350 m | 0,33 | 0,41 | 0,39 |
| 500 m | 0,33 | 0,48 | 0,33 |
| **700 m (avui)** | **0,37** | **0,31** | **0,52** |
| 1.000 m | 0,34 | 0,32 | 0,50 |

**Cap valor s'acosta al llindar de 0,70: la diferència no és el zoom.** El que ella hi va enganxar surt d'una vista
diferent del visor (a Linyola s'hi veuen les plantes dels edificis i les cotes puntuals de la base topogràfica
1:5.000). Tocar el buffer no guanyaria res i trencaria una figura que ella ja ha validat: **es queda com està**, i el
que cal per als altres tres és saber quina vista fa servir — pregunta a l'Eva, no codi.

**4. Correcció al handoff `_FOR-NEW-YOU-20260907-2000` §4.2.** Deia «el forat d'aquells 3 projectes [Linyola,
Bell-lloc, Alcoletge] no és la recepta, és que no tenim UTM». **Els tres sense UTM són Rubí, Vilanova i Anciles**;
Linyola, Bell-lloc i Alcoletge sí que en tenen i per això generen la imatge (i queden en X). La confusió no ha tingut
conseqüències perquè dos dels tres sense UTM (Rubí i Vilanova) es resolen precisament amb el PNG.

**5. Anciles es queda sense figura, i està bé.** És Aragó: l'Eva hi posa el mapa de l'IGME 1:1.000.000, l'ICGC no hi
arriba i tampoc no en tenim UTM. Sense font, cap figura (D8: mai inventar). Queda com l'únic ND de la ranura.

### Implementació

`automation/image_manager.py`: `_find_composed_geological_map()` (+22 línies amb el raonament) i el bloc del mapa
geològic passa a provar-lo abans de la recepta ICGC. Efecte lateral volgut: als tres projectes amb PNG ja no es crida
`_download_icgc_images()`, que avui baixa també l'ortofoto i consulta el Cadastre per a res (la ranura «aèria» va
desaparèixer a la peça 1) — menys espera al wizard. La peça 5 tornarà a necessitar les capes ICGC i les demanarà ella.
`tests/test_peca6_mapa_geologic.py`: 5 tests.

### Validació empírica

Run `2026-09-08-m341-peca6` contra `2026-09-08-m341-tall-rubi`:

| | abans | després |
|---|---|---|
| `fig_geologic` | 0 M · 0 C · 4 X · 3 ND → **0 %** | **3 M** · 0 C · 3 X · 1 ND → **50 %** |
| **total imatges** | 23 · 4 · 18 · 11 → 60 % | **26 M** · 4 C · 17 X · **9 ND** → **64 %** |

Castellar 57 → 71 %, Rubí 60 → 67 %, Vilanova 67 → 71 %. Els tres encerts són **phash 0**: la mateixa imatge, bit a
bit. Rubí i Vilanova es queden **sense cap forat d'imatge pendent** a la taula de presència.
Cap altra cel·la moguda: `diff` dels escalars buit als 7, agregat idèntic llevat del nom del run.

### Tests

5 nous: troba el PNG pel nom i no es queda amb `M1.png`; reconeix les variants de grafia i de carpeta (`ANEXOS/OTROS`);
sense cap fitxer «geol» no hi ha candidat (amb la imatge minada del correu de Linyola com a contraexemple); el `.FH11`
no compta; la carpeta «altres» mana sobre la resta. Suite sencera: **2489 verds, 31 vermells amb els mateixos noms**.

### Limitacions conegudes

1. **Linyola, Bell-lloc i Alcoletge segueixen en X.** Tenim el tipus de figura correcte i les coordenades correctes,
   però no la vista del visor que ella fa servir. **Pregunta 34 a l'Eva** (quina vista i si vol la llegenda) és el que
   ho desbloqueja; no hi ha res a provar per codi mentre no es respongui.
2. **Anciles: cap font.** Aragó (IGME) i sense UTM. Si algun dia es deriven les UTM de la referència cadastral
   (`_FOR-NEW-YOU-20260907-2000` §4.1), caldria comprovar si l'IGME té WMS; avui, ND honest.
3. **Només PNG/JPG.** Si l'Eva no exporta el PNG i només deixa el `.FH11`, es cau a la recepta ICGC sense avisar
   (bloqueig de fons 4: `soffice` a producció).

### GO/NO-GO

- ✅ 3 figures idèntiques (phash 0) amb una regla determinista d'una línia.
- ✅ La recepta ICGC aprovada per l'Eva es queda intacta, i ara està mesurat que moure-la no guanyaria res.
- ✅ Cap escalar, taula ni numeració moguts; suite amb els vermells esperats.
- ⏳ Pregunta 34 a l'Eva per als tres d'ICGC; Anciles bloquejat per les UTM.

### Següents passos

`PENDENTS-IMATGES.md` §6: **peça 5** (situació) → **peça 7** (figures del projecte, peu i numeració variable). A la
peça 5, mirar-hi la precedència del rol `figure_situation_map` (a Rubí apunta a `F1 UBI.png`, que ÉS la figura del
signat) i recordar que els tres PNG de situació ja són MATCH crus.

*Fi entrada 2026-09-08 (3). El mapa geològic compost de l'Eva va primer: 0 % → 50 %, i la recepta ICGC no es toca.*

---

## 2026-09-08 (4) — IMATGES pas 3, peça 5: la figura de situació són els dos mapes del full de l'Eva, de costat (0 % → 71 %)

### Context

Cinquena peça del pas 3 i la ranura amb més forats que quedava: `fig_situacio` era **0 M · 0 C · 7 X · 1 ND → 0 %**,
i és la Figura 1 de tots els informes. Baseline: `2026-09-08-m341-peca6`, imatges 26 M · 4 C · 17 X · 9 ND → 64 %.

### Decisions arquitectòniques clau

**1. Els dos mapes ja són al full que fa servir la peça 4.** L'Eva obre l'informe amb dos mapes de costat (topogràfic
del municipi amb el punt vermell + ortofoto o topogràfic ampliat amb la zona en taronja), i són exactament els dos
mapes petits que hi ha a dalt del seu full «plànol de situació», sobre el dibuix amb punts. Es retallen amb el mateix
mecanisme de la peça 4 —nucli = la imatge incrustada, creixement fins al blanc per agafar el marc i el que ella hi
dibuixa a sobre, les altres imatges com a zones excloses— i es posen de costat a la mateixa alçada sobre blanc, amb
una separació del 2 %.

**2. L'ordre es decideix amb els rectangles ORIGINALS, abans de créixer.** És l'única cosa d'aquesta peça que es va
haver de mesurar dues vegades. Ordenar els rectangles **ja crescuts** sembla equivalent i no ho és: el creixement d'un
mapa li pot moure la vora per davant de l'altre i els inverteix. Amb l'ordre pres abans de créixer, **4 projectes**
donen la imatge idèntica al signat; amb l'ordre pres després, **2** (Castellar cau de phash 10 a 36, Rubí de 6 a 32).
L'ordre és el de lectura del full: d'esquerra a dreta i, quan tots dos són a la mateixa columna, de dalt a baix — a
Castellar i Alcoletge queden l'un sobre l'altre al full i ella els posa de costat, el de dalt a l'esquerra.

**3. El PNG que l'Eva ja ha compost va primer, amb un guard de forma.** Quan SmartScan troba `figure_situation_map`,
es fa servir sencer **si la imatge és ampla (relació ≥ 1,5)**: una figura de situació són dos mapes de costat. Aquí el
rol encerta 2 de 2 (`F1 UBI.png` a Rubí i `F1 SIT.png` a Vilanova, tots dos **phash 0**) i és millor que la composició
(Rubí phash 6, Vilanova 30, perquè la seva composició de Vilanova no són aquests dos mapes). El guard hi és perquè
aquests rols han fallat tres vegades en dos dies (DECISION-LOG 2026-09-08 (2) i (3)) i la forma és la comprovació més
barata que descarta la família d'errors vista: un mapa quadrat o una foto.
**Alternativa rebutjada: trobar el PNG pel nom, com al geològic.** No hi ha cap patró: `m7.png` (Castellar),
`F1 UBI.png` (Rubí), `F1 SIT.png` (Vilanova). Provat també aparellar els PNG d'`ALTRES` contra la nostra pròpia
composició: escull el candidat equivocat a 2 de 3 (un mapa solt correlaciona molt bé dins d'una composició). El nom no
serveix aquí i la mesura ho diu.

**4. `_render_situation_plan_left` FORA.** El retall del 38 % esquerre del full no coincidia amb cap dels 7 signats
(7 X). Ja no el crida ningú i s'ha esborrat; hi ha un test que comprova que no torni.

**5. El filtre del «dibuix gran» també fa falta aquí.** Sense ell, la composició tirava endavant amb el `pl situ.pdf`
de l'arrel (l'export imprimible del FreeHand): algunes de les seves tires de raster passen del 3 % de la pàgina i es
feien passar per mapes (Bell-lloc i Anciles hi queien, phash 30). Exigint que la imatge més gran del full ocupi ≥ 15 %
de la pàgina —el mateix llindar de la peça 4— el full imprimible es descarta i es passa al candidat següent.

### Implementació

| Fitxer | Què |
|---|---|
| `automation/imatges/retall.py` | `detect_situation_maps(page)`, `compose_situation(pdf, out)` i `_grow_to_white()` compartit, +110 línies |
| `automation/image_manager.py` | bloc `3a-bis` (rol amb guard → composició), `_is_wide_image()`, i `_render_situation_plan_left` esborrat |
| `tests/test_peca5_situacio.py` | 7 tests nous |

### Validació empírica

Run `2026-09-08-m341-peca5` contra `2026-09-08-m341-peca6`:

| | abans | després |
|---|---|---|
| `fig_situacio` | 0 M · 0 C · 7 X · 1 ND → **0 %** | **5 M** · 0 C · 2 X · 1 ND → **71 %** |
| **total imatges** | 26 · 4 · 17 · 9 → 64 % | **31 M** · 4 C · **12 X** · 9 ND → **74 %** |

Per projecte: Castellar 71 → **86 %**, Rubí 67 → **83 %**, Vilanova 71 → **86 %**, Anciles 67 → **83 %**, Alcoletge
50 → **67 %**. Els cinc encerts són phash ≤ 10 (Rubí i Vilanova, phash 0). Cap altra cel·la moguda: `diff` dels
escalars buit als 7, agregat idèntic llevat del nom del run.

### Tests

7 nous: troba els dos mapes i deixa fora el dibuix, el nord i el logo; l'ordre és el de lectura del full un cop girat
(amb la geometria de Castellar, que els té a la mateixa columna); sense segon mapa no hi ha figura; sense dibuix gran
no és el full net; la composició queda apaïsada; `_is_wide_image` accepta `F1 UBI.png` i rebutja `F2 UBI PUNTS.png`;
i `_render_situation_plan_left` ja no existeix. Suite: **2496 verds, 31 vermells amb els mateixos noms**.

### Limitacions conegudes

1. **Linyola** queda a phash 18 (X). A ull és la mateixa figura —els mateixos dos mapes, la mateixa fletxa vermella
   entre ells— però els seus dos retalls porten un pèl més de marge vertical. Provat: un marge fix del 4 % la converteix
   en MATCH però trenca Alcoletge i Anciles (phash 4→38 i 10→38), fins i tot retallant el marge perquè no entri a cap
   altra imatge. No hi ha cap valor que serveixi per als tres: es deixa com està i s'anota.
2. **Bell-lloc** fa una altra cosa: la seva Figura 1 i Figura 2 són **dos retalls del plànol de l'arquitecte**
   («Font: Projecte»), no els mapes del full. A més són **dues** figures i la plantilla només té una ranura de
   situació — el mateix motiu de fons que a Vilanova amb la d'assaigs. Ho hereta la peça 7.
3. **El rol amb guard de forma** és una aposta calculada: si a un projecte nou `figure_situation_map` apuntés a una
   imatge ampla que no fos la figura de situació, l'imprimiríem. La composició del full és la xarxa de seguretat quan
   el rol no hi és, no quan és dolent.

### GO/NO-GO

- ✅ 5 de 8 figures de situació idèntiques al signat, amb la mateixa mecànica que les peces 3 i 4.
- ✅ El retall del 38 % que no coincidia amb res ha desaparegut, amb un test que li barra la tornada.
- ✅ Cap escalar, taula ni numeració moguts; suite amb els vermells esperats.
- ⏳ Linyola (marge) i Bell-lloc (dues figures del projecte, una sola ranura): peça 7.

### Següents passos

Queda la **peça 7**, l'última: partir la ranura única en `situació` / `assaigs` / `projecte` amb **peus propis**,
imprimir el nombre de figures que toca (D11) i triar les figures del projecte. És també l'única que mou el grup `fix`
de la numeració (avui 74 M · 25 X, 10 de les quals són «nombre de figures del projecte»), i la que recull els tres
casos que les peces 4 i 5 han deixat oberts: el peu de la figura d'assaigs, `fig_assaigs` de Vilanova i les dues
figures de situació de Bell-lloc.

*Fi entrada 2026-09-08 (4). La figura de situació són els dos mapes del full de l'Eva, de costat: 0 % → 71 %.*

## 2026-09-08 (5) — IMATGES pas 3, peça 7a: la ranura única de figura es parteix en tres blocs amb peu propi (situació 1-2 i projecte 0-2 a l'1.1, assaigs 0-1 al 2.2) i la numeració de les figures va per presència; `fix` 74 → 77 M, imatges 74 → 72 % (transitori, la 7b ho recupera)

### Context

Última peça del pas 3. Handoff `_FOR-NEW-YOU-20260908-2130` §3: «el premi és la numeració». Baseline amb el codi quiet
(`2026-09-08-m341-peca7-baseline`): idèntic a `2026-09-08-m341-peca5` als tres `diff` (escalars, agregat, imatges).
GO del Josep (2026-09-08, nit) al capítol **2.2** per a la figura d'assaigs i als **tres peus fixos**; la peça es fa en
dues subpeces mesurables: **7a** (plantilla + numeració, amb les imatges d'avui) i **7b** (lector de figures).

**Correcció al handoff.** Les 25 X del grup `fix`, classificades a mà (`grep '\[fix\].*MISMATCH'` als 7): **10** són
cascada de figures (Bell-lloc 4, Linyola 3, Vilanova 2, Anciles 1) i són l'única part que toca aquesta peça; **5** són
les taules de Linyola, cascada de `table_dpsh_range` («3 i 4» vs «3, 4 i 5», registre #2 i #83, pregunta 23), no de cap
figura; **7** són seccions (expansivitat P28, 2.4.3 duplicat a Bell-lloc, empentes d'Anciles); **3** són fotos
(Castellar salta la Fotografia 3 al signat; Rubí no tria la vista Google Earth `F3 VG.png`, D5). El sostre de la peça 7
sobre `fix` és **75 → 85 %** (84 M · 15 X), no el 93 % del handoff.

**Troballa nova: el capítol.** Als signats, la figura d'assaigs és al **2.2 Reconeixement del terreny** en 5 de 6
(Castellar, Rubí, Alcoletge, Vilanova, Anciles); Linyola la posa a l'1.1. Les figures del projecte van sempre a l'1.1,
després de la situació. La plantilla tenia les dues ranures a l'1.1. Seqüències: Bell-lloc sit×2 + proj; Linyola sit +
assaigs + proj; Vilanova sit + proj + assaigs; Anciles sit + proj×2 + assaigs; els altres tres sit + assaigs.

### Decisions arquitectòniques clau

**1. Tres blocs condicionals amb peu propi (D11 del pas 2), tot clonat de la plantilla.** `{%p if not fig_situacio_image_2 %}`
taula d'una cel·la + «Figura N. Situació de la zona d'estudi.» / `{%p if fig_situacio_image_2 %}` les dues imatges en
línia + «Figura N i Figura N+1. Detall de la ubicació de la parcel·la en estudi. Font: Projecte.» (Bell-lloc) /
`{%p if fig_projecte_image_n %}` imatge + «Figura N. {{ fig_projecte_caption_n }}» (0-2, el peu l'escriu el lector:
els de l'Eva varien a cada informe) / al 2.2, després del paràgraf del laboratori de camp (posició de Rubí, la
plantilla base): `{%p if fig_assaigs_image %}` imatge + «Figura N. Situació de l'estructura projectada i els assaigs
realitzats.» (Rubí i Alcoletge). Script reproduïble `docs/imatges/scripts/peca7_plantilla.py` (lxml, idempotent, cap
XML a mà).

**2. Cap taula nova a la plantilla: la situació doble va en un sol paràgraf amb les dues imatges en línia.** La primera
versió clonava la taula de dues cel·les de les vistes generals. Mesurat amb el refresc de veritats en sec contra les
dues plantilles: amb l'antiga **0** diferències als 7 projectes; amb la taula nova **23-28 claus per projecte** a la
deriva (`dpsh_tests`, `sondeig_tests`, `spt_*`, `geotech_rows`, `perm_rows`, `seismic_rows`, `lab_*`, `geomech_*`,
`sulfate_*`, `cota_referencia`, `bearing_layer_idx`): totes surten de taules, i l'extractor les aparella per ordre
(gotcha de la peça 1, ara amb la mesura que el quantifica). Sense la taula: només les claus de figura es mouen. Test
que fixa el nombre de taules (14).

**3. Numeració per presència, calculada DESPRÉS de les imatges.** `figure_numbers(n_situacio, n_projecte, has_assaigs)`
(ordre situació → projecte → assaigs → cullera → geològic → tall) i `figure_numbers_from_context` a `render_template`,
quan `ImageManager.build_context` ja ha dit quines imatges hi ha (abans la numeració es feia a `_build_template_context`,
molt abans de les imatges, a partir de `num_project_figures` del `user_data`, que ningú omplia). Buit = `''` i el bloc
no s'imprimeix. Linyola (projecte DESPRÉS d'assaigs) queda amb els dos números creuats: 1 de 7, s'accepta.
**Els noms de numeració han d'acabar en `_num`**: `_is_numbering` de l'extractor ho exigeix (`fig_situacio_num_2` no
hi entrava; ara `fig_situacio_2_num`, `fig_projecte_1_num`, `fig_projecte_2_num`).

**4. Ranures noves a `image_manager`, amb els noms antics com a àlies.** `fig_situacio_image_1` (cadena de la peça 5),
`fig_situacio_image_2` (buit: lector, 7b), `fig_assaigs_image` (el `plan_crop` de la peça 4), `fig_projecte_image_1/2`
+ `_caption_1/2` (buits: lector, 7b); `fig_cadastre_image`, `fig_main_plan_image`, `fig_location_image`,
`fig_building_image` segueixen com a àlies. **Fora (D4):** el retall `main_plan` del rol `architect_plan`, la caixa de
`planol_extracted.json` i el render de la pàgina sencera de l'`A.01.pdf`: cap dels 7 signats els porta, i sense
candidat clar ara no s'imprimeix cap figura (el bloc és condicional), mai una pàgina sencera amb caixetí.

**5. El retall del full de situació va a la ranura d'assaigs a tots els projectes, també a Bell-lloc (límit conegut).**
El full de Bell-lloc no té punts i l'Eva el fa servir com a figura del projecte. Buscat un senyal determinista i cap
serveix: les etiquetes «P-n» del FreeHand **no són text** (Castellar i Rubí en tenen i `get_text` no en dona cap) i
els farcits vectorials petits dins la regió no separen res (Castellar 1, Rubí 1, Linyola 6, Bell-lloc 3 de llegenda).
Ho classifica el lector de la 7b, que mira la imatge. Mentrestant la mesura ho diu honestament: Bell-lloc perd un M
(F3 projecte → ND) i té 1 sobrant.

**6. L'extractor admet dos PEUS amb el mateix forat.** Els dos peus de situació porten `fig_situacio_num`; abans el
segon es descartava (la regla era per a l'índex i la capçalera, que sí que han de comptar una sola vegada). Ara la
regla només val per a capçaleres, cada peu s'aparella pel seu text i, si dos peus trobessin peu al signat, mana el de
més puntuació (avís al registre). Bell-lloc dona (1, 2) pel peu doble; Alcoletge 1 pel simple.

**7. La mesura d'imatges és estricta per ranura.** `SLOT_MAP`: `fig_assaigs_image` només contra `fig_assaigs`,
`fig_projecte_image_n` només contra `fig_projecte` (abans `fig_main_plan_image` valia per a totes dues i amagava el peu
equivocat). `IMAGE_SLOTS` del test de presència inclou les 5 ranures condicionals (buit = absent).

### Implementació

| Fitxer | Què |
|---|---|
| `templates/g3dt-jinja-template.docx` | +20 paràgrafs (1.1: 4 blocs; 2.2: 1 bloc), 14 taules (sense canvi), 122 → 123 KB |
| `docs/imatges/scripts/peca7_plantilla.py` | nou, 130 línies: la transformació, idempotent, amb assert del nombre de taules |
| `automation/report_generator.py` | `figure_numbers`, `figure_numbers_from_context`, `_is_image`; `_build_numbering_context` −30/+5; `render_template` +2 |
| `automation/image_manager.py` | bloc 3 reescrit (−80/+60): ranures noves, àlies, fallbacks de l'`A.01` fora; `ROLE_TO_FIGURE_VAR` |
| `automation/reference_extractor.py` | peus poden repetir forat; el primer mana (+10) |
| `docs/wizard-headless/mesures/imatges_font.py`, `mesura_341.py` | `SLOT_MAP` i `IMAGE_SLOTS` amb les ranures noves |
| `web/api.py`, `templates/validation/review.html` | calaix de figures: prefixos `situacio_*` i `plan_crop_*`, etiquetes «Situació (1.1)» / «Assaigs (2.2)» |
| `reference-material/*/validation/eva_reference_values.json` | +6 claus (`fig_situacio_num` ×2, `fig_situacio_2_num`, `fig_assaigs_num` ×3), −3 (`fig_cadastre_num` ×2, `fig_main_plan_num`) via `refresh_eva_narrativa.py --keys … --drop …` |
| `tests/test_peca7_figures.py` | 14 tests nous; 4 fitxers de tests existents actualitzats als noms nous |

### Validació empírica

Run `2026-09-08-m341-peca7a` contra `2026-09-08-m341-peca5` (= baseline):

| | abans | després |
|---|---|---|
| grup `fix` | 74 M · 0 C · 25 X → 75 % | **77 M** · 0 C · 25 X → 75 % (veritats 99 → 102) |
| escalars totals | 308 · 43 · 124 · 32 → 74 % | **311** · 43 · 124 · 32 → 74 % (Rubí 80 → 81, Linyola 68 → 69) |
| taules | 292 · 99 · 88 → 82 % | idèntic |
| imatges | 31 M · 4 C · 12 X · 9 ND → 74 % | **29 M · 4 C · 13 X · 10 ND → 72 %** |
| `fig_assaigs` | 4 · 0 · 0 · 2 → 100 % | 4 · 0 · 2 · 0 → 67 % (Linyola i Vilanova: el nostre retall contra la SEVA figura d'assaigs) |
| `fig_projecte` | 2 · 0 · 1 · 2 → 67 % | 0 · 0 · 0 · 5 (cap figura del projecte fins a la 7b) |

L'únic escalar que canvia d'estat és Bell-lloc: `fig_main_plan_num` X (2 vs 3) → `fig_situacio_2_num` X ('' vs 2).
Els 3 M nous de `fix` són `fig_assaigs_num` (Rubí, Linyola, Alcoletge = 2). Els `.docx` generats: situació a l'1.1,
assaigs al 2.2 amb el seu peu, numeració contínua, cap resta de Jinja (comprovat a Bell-lloc, Rubí i Anciles).

### Tests

14 nous (`tests/test_peca7_figures.py`): estructura dels blocs i posició al 2.2, cap taula nova, numeració per
presència (els 7 signats + topalls), numeració des del context (buits i pendents), `render_template` renumera després
de les imatges, extractor amb dos peus del mateix forat (Bell-lloc, Alcoletge, empat, índex+capçalera), context de
`image_manager` (claus, àlies, retall → assaigs) amb la cau aïllada a `tmp_path`. Actualitzats: `test_peca1_plantilla`,
`test_peca4_retall_planta`, `test_peca0_imatges_font`, `test_bloc4_numeracio`. Suite sencera: **31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2510 verds / 5 omesos (203 s)**.

### Limitacions conegudes

1. **Imatges 74 → 72 % és transitori i volgut**: Bell-lloc (el retall sense punts imprès com a assaigs; F3 projecte ND
   + 1 sobrant) i Vilanova (el mateix dibuix li serveix per a F2 i F3; ara només es puntua contra F3, retall estret).
   Registre de pèrdues #8-#10, marcades «transitòria (7b)».
2. La numeració per presència només puja quan hi ha figures del projecte i la 2a de situació: **7b**.
3. Linyola: projecte després d'assaigs (1 de 7): els dos números quedaran creuats quan hi hagi figura del projecte.
4. El peu de les figures del projecte no té text fix → l'extractor no en pot treure veritat (`fig_projecte_n_num`
   sempre en blanc): la numeració es mesura per la cullera, el geològic i el tall, que sí que en tenen.
5. El calaix del wizard segueix amb les claus `fig_cadastre` / `fig_main_plan` (només etiquetes noves).

### GO/NO-GO

- ✅ Capítol 2.2 i tres peus fixos: GO del Josep.
- ✅ Cap taula nova; només les claus de figura es mouen a les veritats (mesurat contra les dues plantilles).
- ✅ Escalars: +3 M, cap altre canvi; taules intactes.
- ⏳ Imatges −2 M transitòries → 7b.

### Següents passos

**7b, el lector de figures**: skill nova com la de fotos, que mira les pàgines candidates i escriu `figure_selection.json`
(ranura, fitxer, pàgina, retall, peu) amb precedència Eva > lector > determinista. Cobreix Anciles (topogràfic p5 de
`IV_PLANOS.pdf` i tipologies `A01_TIPOL.pdf`), Linyola (secció del projecte i `Punts de Sondeig_Silvia_Jaume.pdf` com a
figura d'assaigs), Bell-lloc (dos insets de l'`A.01.pdf` i el retall com a projecte, no assaigs) i Vilanova (retall
estret del mateix dibuix per a la Figura 3). Guany potencial: fins a 7 imatges més en M i 10 X de `fix`.

*Fi entrada 2026-09-08 (5). Peça 7a: tres blocs de figura amb peu propi, assaigs al 2.2, numeració per presència; `fix` 74 → 77 M; cap taula nova.*

## 2026-09-09 — IMATGES pas 3, peça 7b: el LECTOR DE FIGURES és Claude Code (skill `g3dt-llegir-figures`, candidats amb quadrícula, exemplars leave-one-out), amb el skill NEUTRE (cap nom de projecte, cap excepció d'un sol cas) després que el Josep detectés que s'estava ajustant als 7 signats: `fix` 77 → 79 M (77 %), imatges 72 → 69 % (honest); el pas 3 d'imatges queda tancat

### Context

- Peça 7a (DECISION-LOG 2026-09-08 (5)): plantilla amb tres blocs de figura i numeració per presència; les ranures
  `fig_projecte_image_1/2` i la classificació del retall quedaven per al lector. Baseline: `2026-09-08-m341-peca7a`.
- GO del Josep (nit del 8): commit de la 7a en tres (`c95f2b0` · `c4c4763` · `f783ceb`) i començar la 7b.
- **Intervenció del Josep a mig camí (2026-09-09):** «Si només estem construint el codi perquè surti bé en aquests
  projectes de referència, tinc una mala notícia: l'Eva no correrà de nou aquests projectes.» Memòria
  `feedback_reference_projects_are_situations_not_targets`. Tot el que segueix es divideix en «abans» (skill amb fuites)
  i «després» (skill neutre); el número que val és el segon.

### Decisions arquitectòniques clau

**D1. Mateixa mecànica que el lector de fotos (peça 2), amb candidats que són PÀGINES i retalls en fraccions.**
`automation/imatges/lector_figures.py`: inventari de candidats = el retall determinista del full de l'Eva (`annex_crop`,
peça 4) + cada pàgina amb dibuix dels PDF del projecte de l'arquitecte + imatges de l'expedient + PNG d'`ALTRES`/`OTROS`;
cada candidat renderitzat amb una QUADRÍCULA de fraccions 0-1 i una franja «CANDIDAT N · fitxer · pàgina»; full de
contacte; exemplars de les tres ranures dels ALTRES signats (leave-one-out); prompt = skill + llista; `claude -p` pel
runner de la lectura (sonnet, medium, una crida); validació (índex, retalls dins [0,1] i ≥ 2 % d'àrea, ≤ 2 figures
del projecte amb peu, cap (candidat, retall) repetit); retall (PDF: `clip` en coordenades de `page.rect`, que és
l'espai girat; imatge: PIL) + marge blanc fora; `validation/figure_selection.json` amb `source: lector`.
**Els documents del projecte** són la carpeta d'expedient `NN.NNNN/` (només s'hi treuen pressupostos i informes de G3:
a Linyola «Punts de Sondeig_Silvia_Jaume.pdf» conté «Sondeig» i és de l'arquitecte) més els fitxers de l'arrel amb rol
d'arquitecte, deduplicats per md5; pàgines només de text fora; topall 40 pàgines per PDF i 60 candidats (Anciles: 38).

**D2. La franja amb l'índex a cada render.** A la primera passada el lector va descriure la secció de la p11 i va
escriure l'índex de la p3. Amb la franja i l'obligació de citar «candidat N (fitxer, pàgina)» a `raons`, no ha tornat
a passar en 14 crides.

**D3. La selecció MANA sobre les tres ranures, també quan diu «cap».** `apply_selection` retorna les cinc claus sempre
(buit = `''`): sense això, a Bell-lloc el lector deia «cap figura d'assaigs» i el camí determinista en posava una →
el mateix dibuix imprès dues vegades (1.1 com a projecte, 2.2 com a assaigs), i la cullera «encertava» per
casualitat. Test de regressió.

**D4. La ranura de situació NO la toca el lector.** Regla provada i retirada: «si el plànol de l'arquitecte porta els
dos mapes com a insets, l'Eva els fa servir» encerta a Bell-lloc (C + X) i falla a Alcoletge (hi són i ella va posar
la seva composició: una M substituïda per dues X). La situació doble només s'aplica si la tria l'Eva (`source: user`).

**D5. Skill NEUTRE: cap nom de projecte, cap excepció d'un sol cas (decisió del Josep).** Fora del skill: «excepció
Bell-lloc» (el lector veia el nom del projecte i reproduïa la inconsistència de l'Eva), «retall estret com a
Vilanova» (sense cap condició observable), «planta amb punts de l'arquitecte abans que l'annex, com a Linyola» (ni
tan sols és el que va fer l'Eva: hi va posar la planta acolorida del projecte amb icones dibuixades per ella), els
peus citats dels 7 signats (els exemplars leave-one-out ja els donen). Queden: la figura d'assaigs = el dibuix amb
punts, normalment l'`annex_crop` sencer; projecte 0-2 amb criteris genèrics (secció respecte del terreny, emplaçament
si la d'assaigs no mostra la parcel·la, topogràfic facilitat, tipologies de diversos habitatges) i regla de
sobrietat (per defecte ≤ 1); situació sempre `null`; `annex_crop` i `eva_png` sencers. Test barat: `grep -c` dels 7
noms sobre el skill = 0 (també aplicat al skill de fotos, que en citava 2 entre parèntesis).
Per què: els 7 signats són exemples de SITUACIONS que es tornaran a presentar; l'Eva mai tornarà a córrer aquests
projectes. Una regla que només un projecte dispara no és una regla: és una pregunta a l'Eva (30, 31, 32) o una opció
al wizard.

### Implementació

| Fitxer | Què |
|---|---|
| `automation/imatges/lector_figures.py` | nou, ≈ 430 línies: documents del projecte, inventari + quadrícula + franja, full de contacte, exemplars, prompt, validació, `render_entry` (clip/PIL + `trim_white`), `write_selection`, `load_selection`, `apply_selection` |
| `.claude/commands/g3dt-llegir-figures.md` | nou, 96 línies, neutre |
| `.claude/commands/g3dt-llegir-fotos.md` | 2 noms de projecte fora (cap selecció desada canvia) |
| `automation/image_manager.py` | bloc 7b: `apply_selection` després del camí determinista; buit = `''`; 70 mm per a la situació doble, 150 mm assaigs/projecte |
| `docs/wizard-headless/mesures/llegir_figures_corpus.py` | nou: 7 projectes, leave-one-out, puntuació amb `imatges_font.score_pair` |
| `tests/test_peca7b_lector_figures.py` | 8 tests: documents del projecte, inventari, validació, retall + marge, `apply_selection` (lector vs `user`), precedència a `ImageManager`, «cap» que buida |
| `.gitignore` | `validation/_lector_figures/` |

### Validació empírica

Lector (run `2026-09-09-lector-figures-p5`, skill neutre, sonnet/medium, leave-one-out, 37-80 s per projecte):

| projecte | assaigs | projecte | comentari |
|---|---|---|---|
| castellar | `annex_crop` → **M** (ph 6) | cap | = signat |
| rubi | `annex_crop` → **M** (ph 6) | cap | = signat |
| bell-lloc | `annex_crop` → sobrant | cap (l'Eva en posa 1) | l'Eva va posar aquest mateix dibuix com a figura del PROJECTE i cap al 2.2: pregunta 31 |
| linyola | `annex_crop` → X (ph 24) | p2 emplaçament → X | l'Eva: planta acolorida amb icones seves (irreproduïble, D3) i la secció de la p11 |
| alcoletge | `annex_crop` → **M** (ph 8) | cap | = signat |
| vilanova | `annex_crop` → X (ncc 0,683, llindar 0,70) | cap (l'Eva en posa 1) | el mateix dibuix li fa de F2 ample i F3 estret: pregunta 32 |
| anciles | `annex_crop` → **M** (ph 6) | secció p25 → X | l'Eva: topogràfic + tipologies (2 figures) |

M341 `2026-09-09-m341-peca7b` contra `2026-09-08-m341-peca7a`:

| | 7a | 7b (neutre) | 7b amb fuites (`-fuites`, no val) |
|---|---|---|---|
| `fix` | 77 M · 25 X → 75 % | **79 M · 23 X → 77 %** | 80 · 22 → 78 % |
| escalars | 311 · 43 · 124 · 32 → 74 % | 313 · 43 · 122 · 32 → 74 % | 314 |
| taules | 82 % | idèntic | idèntic |
| imatges | 29 · 4 · 13 · 10 → 72 % | **29 M · 4 C · 15 X · 8 ND → 69 %** | 30 · 4 · 16 · 6 → 68 % |
| `fig_projecte` | 0 · 0 · 0 · 5 | 0 · 0 · 2 · 3 | 1 · 0 · 3 · 1 |

L'únic escalar que es mou és Linyola: cullera, geològic i tall X → M (una figura del projecte, com al signat) i
`fig_assaigs_num` M → X (creuament conegut: l'Eva posa la del projecte després de la d'assaigs). Cap altre escalar,
cap taula. Les dues X noves d'imatges són figures del projecte que existeixen i que l'Eva no va triar; els `.docx`
(Linyola, Anciles, Bell-lloc): situació 1.1, projecte 1.1, assaigs 2.2, numeració contínua, cap Jinja.

### Tests

+8 (`tests/test_peca7b_lector_figures.py`). Suite sencera: **31 vermells amb els mateixos NOMS que
`suite-vermells-esperats.txt` / 2518 verds / 5 omesos (238 s)**.

### Latència / cost

- Lector: 37-95 s per projecte, una crida (sonnet, medium); Anciles amb 38 candidats, 61 s. 14 crides en total avui
  (3 passades senceres + 3 repeticions).
- **Variància entre passades**: el mateix projecte dona retalls diferents (Linyola: C amb 0,50-0,89, X amb
  0,48-0,93) i a vegades una figura de més. En producció l'Eva veurà la tria al wizard; no s'ha de «repetir fins que
  surti bé» per mesurar.

### Limitacions conegudes

1. **El % és in-sample amb N=7**: regles i skill s'han fet mirant aquests 7. El skill neutre és el que corre; el
   número del skill amb fuites (78 % / 68 %) queda al run `-fuites` només com a evidència del biaix.
2. `fig_projecte` 0 M: les figures del projecte són un judici (quan, quina, quin retall) i l'Eva no en té cap regla
   escrita (pregunta 32). El lector tria una figura defensable; a Linyola i Anciles no és la seva.
3. Bell-lloc (dibuix amb punts com a projecte i cap al 2.2) i Vilanova (ample + estret del mateix dibuix): sense regla,
   preguntes 31 i 32; al registre (#8-#10, ara obertes).
4. A Anciles l'Eva va enganxar el full de tipologies SENCER amb caixetí i d'una altra versió del document («PROYECTO
   BÁSICO REVISADO»): «mai el caixetí» tampoc és absolut.
5. El lector no és determinista (vegeu latència); i necessita Claude Code a l'ordinador de l'Eva (via A).
6. Escalars i taules de tots els blocs anteriors: intactes.

### GO/NO-GO

- ✅ El lector existeix, escriu un contracte amb font, raó i confiança, i el generador l'aplica amb precedència Eva > lector > determinista.
- ✅ Skill neutre (grep = 0), mesurat i publicat el número honest.
- ✅ Escalars +2 M, taules intactes, suite amb els noms esperats.
- ⏳ Pas 3 d'imatges TANCAT en el que és mecànica: el que queda és judici de l'Eva (preguntes 30-32, 34, 37, 38) i opcions al wizard.
- ⏳ Commit (GO del Josep): proposta en 3 — lector + skill + integració + tests · runner del corpus + seleccions + `.gitignore` · runs i docs.

### Següents passos

- **Preguntes a l'Eva** (amb el Josep): 30-32 (situació, punts, figures del projecte), 34 (vista ICGC), 37-38 (fotos), 19a.
- **Wizard**: mostrar la tria del lector (assaigs, projecte, peus) amb «cap font» explícit i deixar-la canviar
  (`source: user`), incloent la situació doble.
- **Bloc 5 del PLA (castellà)** i els pendents de plantilla del §3 de `PENDENTS-IMATGES.md`.

*Fi entrada 2026-09-09. Peça 7b: el lector de figures amb el skill neutre; `fix` 77 → 79 M, imatges 69 % honest; pas 3 d'imatges tancat.*

## 2026-09-09 (2) — IMATGES, acció 1 de l'anàlisi de discrepàncies: els PNG d'`ALTRES`/`OTROS` de l'Eva són candidats del lector de fotos (vista de Rubí ND → M, `fix` 79 → 81 M) i, de pas, l'aparellament amb l'annex és invariant a la rotació

### Context

- `docs/imatges/ANALISI-DISCREPANCIES-2026-09-09.md` §2.3 i §3 (acció 1, cost XS): a Rubí la «Fotografia 1» del signat
  és una captura de Street View que l'Eva desa a `ANNEXES/Altres/F3 VG.png`; el lector de fotos (peça 2) només mirava
  la carpeta de fotos i el forat quedava ND. SmartScan ja li dona el rol `photo_site_overview`.
- Decisió del Josep (tarda, handoff `_FOR-NEW-YOU-20260909-1430.md` §3): fer (1) abans que (3) i (4).
- Baseline: `2026-09-09-m341-peca7b` (imatges 29 M · 4 C · 15 X · 8 ND, `fix` 79 M · 23 X, escalars 313 M).

### Decisions arquitectòniques clau

**D1. Els PNG d'`ALTRES`/`OTROS` entren al full de contacte DESPRÉS de les fotos, marcats «PNG de l'Eva».**
`list_eva_pngs()` (qualsevol imatge dins una carpeta `ALTRES`/`OTROS`, a qualsevol nivell, `validation/` fora) i
`kind: foto | eva_png` a cada candidat. Els índexs de les fotos no es mouen (1..n com abans); els PNG van al final.
Dedupe: md5 (com abans) **i phash ≤ 2 només entre un PNG de l'Eva i una foto** (la mateixa foto re-desada com a
PNG seria dos candidats i podria anar a dos forats). Alternativa descartada: filtrar els PNG per rol o per nom
(«VG», «vista») — un rol de SmartScan no mana sobre un forat d'imatge sense mesura (PENDENTS §0 #1), i els noms
no tenen patró. El lector els veu tots i decideix; a Castellar (12 PNG) i Vilanova (8) els ignora tots, 3 de 3 passades.

**D2. El criteri del skill és pel que S'HI VEU, no per la procedència.** Primera redacció: «una vista del solar presa
d'un visor (Google Earth, Street View)». El lector va identificar `F3 VG.png` com a «vista» i la va descartar perquè
«no és una captura de visor» (una captura de Street View sembla una foto: la procedència no es veu), i va fer servir
l'absència a l'annex de fotografies com a prova en contra. Redacció final: si mostra el solar com una fotografia
(carrer, tanca, cases, cel) va a `site_1`; mapa, plànol, tall o ortofoto, mai; l'annex només recull fotos de camp, que
no hi sigui no diu res. Cap nom de projecte al skill (`grep` = 0). PENDENTS §0 #11.

**D3. L'aparellament foto ↔ annex prova 0/90/180/270°.** Per què: a la segona passada el lector va canviar `materials`
de `SPT1.jpg` (= Eva) a una foto de WhatsApp del mateix motiu (≠), amb els mateixos candidats: un empat visual
resolt a l'atzar. La pista determinista que l'hauria tancat («SPT1.jpg és l'annex F-4») no hi era perquè l'Eva
incrusta la foto vertical de la cullera girada 90° (436×775) i el phash no és invariant a la rotació. **Mesurat als 7
projectes abans de tocar res: 2 de 31 imatges d'annex només s'aparellen girades** (Rubí `SPT1.jpg` ph 24 → 4;
Vilanova `SPT A P3.jpeg` ph 26 → 0). Dos projectes, mateix motiu: mecanisme, no cas únic. `annex_images` desa
`phashes` per rotació; la pista al prompt diu «(hi és girada 90°)». PENDENTS §0 #10.

**D4. La pestanya de fotos del wizard veu els mateixos candidats.** `GET /api/photos/{p}` afegeix els PNG de l'Eva
amb `kind: eva_png` (etiqueta «PNG de l'Eva, ALTRES» al títol i a la foto triada); si no, la tria del lector d'un
fitxer d'`ALTRES` no sortiria a la pestanya i l'Eva no la podria veure ni canviar. Preparació mínima de l'acció 4.

**D5. Tres passades del lector, cadascuna després d'un canvi de mecanisme, no «fins que surti bé».** `altres`
(criteri de procedència: Rubí vista ND), `altres-b` (criteri corregit: vista M, materials M → X per variància),
`altres-c` (pista de l'annex girat: vista M, materials M). Les tres runs queden com a evidència. Si a la tercera el
lector hagués tornat a triar la foto de WhatsApp, quedava com a empat per al wizard (acció 4), sense més passades.

### Implementació

- `automation/imatges/lector_fotos.py`: `EVA_PNG_DIRS`, `is_eva_png`, `list_eva_pngs`, `PHASH_SAME`, `ROTATIONS`;
  `inventory` (dues fonts, `kind`, dedupe md5 + phash, rotació), `annex_images` (`phashes`), `contact_sheet` i
  `build_prompt` (marca i «girada»), `validate_selection` (el nom de fitxer sol només resol si és únic: `m1.png` pot
  ser a dues carpetes), `run` (`n_eva_png`). `lector_figures.py` importa `EVA_PNG_DIRS` d'aquí (una sola definició).
- `.claude/commands/g3dt-llegir-fotos.md`: `site_1`/`site_2`, «Mai van a l'informe», pista 5 «PNG de l'Eva».
- `web/api.py` `list_photos` (+ `kind`, PNG de l'Eva); `templates/validation/review.html` (etiqueta, 2 línies).
- Cap canvi a `image_manager.py` (`_load_user_photo_selection` ja resol camins relatius al projecte) ni al generador.

### Validació empírica

Run de referència **`2026-09-09-m341-altres-b`** (vs `2026-09-09-m341-peca7b`), 7 projectes via A:

| mesura | peca7b | altres-b |
|---|---|---|
| imatges (M · C · X · ND) | 29 · 4 · 15 · 8 → 69 % | **30 · 4 · 15 · 7 → 69 %** |
| `foto_vista` | 2 · 0 · 1 · 1 | **3 · 0 · 1 · 0** (Rubí ND → M, phash 0) |
| Rubí imatges | 4 · 1 · 1 · 1 → 83 % | 5 · 1 · 1 · 0 → 86 % |
| escalars+narrativa | 313 · 43 · 122 · 32 → 74 % | **315 · 44 · 120 · 31 → 75 %** |
| `fix` | 79 M · 23 X → 77 % | **81 M · 21 X → 79 %** (Rubí `photo_dpsh_num`, `photo_materials_num` X → M: la Fotografia 1 és la vista) |
| `narr` | 34 · 28 · 40 · 7 | 34 · 29 · 40 · 6 (Rubí `photo_site_text` ND → CLOSE) |
| taules | 292 · 99 · 88 → 82 % | idèntic |

**Cap altra cel·la moguda** als altres 6 projectes (els tres `diff` només toquen Rubí). Lector: Castellar i Vilanova
trien exactament el mateix a les 3 passades amb 12 i 8 mapes de més al full (cap regressió per soroll de candidats).
Runs del lector: `2026-09-09-lector-fotos-altres` · `-b` · `-c` (`_LECTOR-FOTOS.md`).

### Tests

5 nous: `tests/test_peca2_lector_fotos.py` (+3: inventari amb ALTRES/OTROS, ordre, `kind`, rol, dedupe md5 i phash,
prompt, validació i `ImageManager`; sense carpeta de fotos; nom de fitxer ambigu; +1: aparellament girat 90°),
`tests/test_photos_api_eva_png.py` (+1: l'endpoint). Suite: 31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2523 verds / 5 omesos (224 s).

### Latència / cost

Lector: Castellar 102 → 58 s, Rubí 36-59 s, Vilanova 51-66 s (sonnet/medium, 1 crida); 12 i 8 candidats més al full
no canvien la tria. 3 passades × 2-3 projectes ≈ 8 crides. M341: 0 LLM, ~4 min.

### Limitacions conegudes

- Guany in-sample N=7: +1 cel·la d'imatge, +2 de `fix`. Un sol projecte del corpus té una vista a `ALTRES`; el
  criteri (vista del solar sí, mapa no) és general però només s'ha provat contra aquest cas i contra 20 mapes que
  el lector ha ignorat bé.
- `foto_dpsh` de Rubí segueix X (empat entre P1/P2/P3, pregunta 37). El dedupe per phash ≤ 2 és només foto ↔ PNG.
- La pestanya de fotos mostra els PNG barrejats amb les fotos (només l'etiqueta els distingeix): l'acció 4 la refà.
- El full de contacte creix (21 cel·les a Castellar): per sobre de ~40 caldria paginar-lo; cap projecte del corpus hi arriba.

### GO/NO-GO

- ✅ Rubí `foto_vista` ND → M; `fix` +2; cap pèrdua a cap projecte; taules intactes.
- ✅ Skill neutre (`grep` dels 7 noms = 0); cap regla d'un sol cas (rotació: 2 projectes; PNG: el lector decideix).
- ✅ Suite amb els mateixos vermells. ✅ Commitejat `44c9106` (codi) · `aa72d41` (mesura) · `c2af8a0` (docs), GO del Josep.

### Següents passos

- Acció (3): estudi del retall del tall als 7 signats (0 tokens). Acció (4): wizard amb alternatives visibles
  (els lectors han d'escriure 2-3 candidats per ranura; ara `raons`/`confianca` n'hi ha un).
- Preguntes 30-34, 36-38 amb el Josep; workflow `ALTRES` amb l'Eva (geològic).

*Fi entrada 2026-09-09 (2). Acció 1: PNG d'ALTRES al lector de fotos; Rubí vista ND → M, `fix` 79 → 81 M; aparellament amb l'annex invariant a la rotació.*

## 2026-09-09 (3) — IMATGES, acció 3: estudi del retall del tall als 7 signats; dues diferències eren estètiques (marge blanc) i dues un defecte nostre (un traç multi-rectangle del FreeHand feia de pont amb la llegenda); `fig_tall` 3 M · 4 C → 4 M · 3 C, i l'eix de cotes ja no surt tallat

### Context

- Acció 3 de `docs/imatges/ANALISI-DISCREPANCIES-2026-09-09.md` §3 (cost M, 0 tokens): `fig_tall` és mateixa font 7/7 amb
  4 C; mesurar el rectangle de l'Eva dins `tall.pdf` i comparar-lo amb el nostre. Handoff 1430 §3 (3): no tocar
  `detect_section_region` sense baseline ni els tres `diff`.
- **Pregunta del Josep a mig camí:** «aquestes diferències són importants o només estètiques? Si només són estètiques,
  si nosaltres ho fem sempre igual ja estarà bé; si hi ha alguna raó per fer-ho diferent segons el cas, analitzem-la.»
- Baseline: `2026-09-09-m341-altres-b` (`fig_tall` 3 M · 4 C; imatges 30 · 4 · 15 · 7).

### Decisions arquitectòniques clau

**D1. Primer mesurar, amb nom per a cada mil·límetre.** Script d'estudi (scratchpad, 0 tokens): la figura de l'Eva es
localitza dins la pàgina renderitzada per NCC multiescala (0,956-0,997 als 7), es passa a mm de pàgina i es compara
costat a costat amb el nostre rectangle; les paraules i traços del PDF que cauen a cada franja de diferència diuen QUÈ
hi ha. Resultat (esquerra · dalt · dreta · baix, + = l'Eva agafa més):

| projecte | abans (mm) | què hi havia a la franja | estat |
|---|---|---|---|
| Castellar | +3,6 · **+10,5** · −0,6 · +0,9 | res: blanc | C (estètic) |
| Rubí | −1,4 · **+9,4** · +1,9 · −0,5 | res: blanc | C (estètic) |
| Linyola | −2,4 · **−49,1** · −0,7 · +0,1 | la llegenda i el plànol (nostres) | C (defecte) |
| Vilanova | −6,4 · **−73,3** · +1,0 · +1,6 | la llegenda i el plànol (nostres) | C (defecte) |
| Bell-lloc | **+13,0** · +6,0 · −0,4 · +3,1 | els números de l'eix i «(msnm)» (seus, nosaltres els tallàvem) | M però lleig |
| Alcoletge | +1,7 · +0,4 · −0,2 · −2,7 | — | M |
| Anciles | +0,4 · +1,9 · +1,4 · +2,0 | — | M |

**Resposta a la pregunta:** 2 de 4 són només estètiques (el marge blanc que l'Eva deixa sobre les etiquetes: 11-13 mm
a Castellar i Rubí, 3-9 als altres cinc, sense contingut ni regla; nosaltres 2,5 mm sempre) i 2 són un defecte
nostre (imprimíem la llegenda i el plànol, que l'Eva no posa mai, 7/7). Cap raó per fer-ho diferent segons el cas:
l'Eva és consistent en el contingut (llegenda fora 7/7, eix de cotes dins 7/7); només varia el marge, sense motiu.

**D2. Un traç són tants objectes com rectangles (`_ink_rects`).** El pont de Linyola i Vilanova no era cap tolerància:
el FreeHand exporta com a UN SOL traç un grup de línies separades (a Linyola la línia superior de la caixa de la
llegenda i la línia del terreny de la secció, 145 × 53 mm de caixa amb dues ratlles de 0,7 mm de tinta; a Vilanova les
dues línies de la caixa de la llegenda), i `d["rect"]` n'és la caixa englobant: ample, ple i negre, passava el filtre
d'«estrat» i entrava al nucli; després tot el que hi ha a sobre venia enganxat. Alcoletge en té un d'igual (llegenda →
terreny → caixetí) que no feia mal per sort. Regla general de geometria PDF, no de cap cas: si tots els items d'un
traç són rectangles, cada rectangle és un objecte (nucli i creixement); si no (polígons dels estrats), la caixa.
Alternatives descartades: excloure els farciments negres (el terreny de Rubí és un traç negre de dos rectangles que sí
que va a la figura); detectar la llegenda per paraules (ja provat a la peça 3: no canviava res, perquè el pont era
al nucli).

**D3. «Blanc» són 5 mm en absolut, no el 5 % de l'alçada del nucli.** Mesurat als 7: els números de l'eix de cotes són
a 0,4-3,7 mm de la barra (l'Eva els posa 7/7; a Bell-lloc, 3,7 mm, quedaven fora amb el 5 % = 2,1 mm i el retall
tallava «(msnm)» per la meitat) i la llegenda mai és a menys de 16 mm de la secció (22-102 mm, Rubí la més propera).
Un llindar relatiu a l'alçada del nucli no té sentit: la distància eix-barra i la distància llegenda-secció són
convencions del full, no de l'alçada del terreny.

**D4. La finestra puja com a mínim 40 mm.** Amb el nucli net (només estrats) Alcoletge va perdre «(msnm)» i «A»/«A'»
(T +14): la seva secció fa 30 mm i la finestra del 75 % (22 mm) no arribava a les etiquetes, que als 7 signats pengen
15-32 mm sobre els estrats. Abans hi arribava per casualitat (el traç multi-rectangle inflava el nucli). El mínim
absolut ve de la mesura; la llegenda no hi entra igualment, perquè la para la contigüitat de 5 mm (D3).

**D5. El marge blanc no es toca i «(msnm)» va sencer.** Les dues C que queden (Castellar, Rubí) són el marge de captura
de l'Eva; Bell-lloc passa de M a C perquè ara incloem «(msnm)» sencer (7,8 mm més a l'esquerra) i ella el talla —
ho fa a 3 de 7 (Bell-lloc, Linyola, Vilanova) i el deixa sencer a 4. «Sempre igual» (Josep): sencer, és la unitat de
l'eix. Registre de pèrdues #14. La barra d'escala: l'Eva la inclou només a Vilanova (B +6,7); nosaltres mai.

### Implementació

- `automation/imatges/retall.py`: `_ink_rects`, `GAP_MM = 5.0` (substitueix `GAP = 0.05`; `gap_mm` a la signatura),
  `PAD_UP_MIN_MM = 40.0`; docstring del mòdul amb les mesures. `automation/image_manager.py`: prefix de cau
  `tall_crop2` (els retalls `tall_crop_*` antics de qualsevol cau, la de l'Eva inclosa, no valen).
- `tests/test_peca3_retall_tall.py` (+3: traç de dos rectangles que uneix llegenda i terreny; números de l'eix a 3-5
  mm dins i «ESCALA» a 18 mm fora; secció curta amb les etiquetes 32 mm a sobre).
- Estudi: scratchpad (`estudi_tall.py`, superposicions PNG); no entra al repo. Runs: `2026-09-09-m341-tall`.

### Validació empírica

| projecte | ara (mm) | `fig_tall` abans → ara (phash) |
|---|---|---|
| Castellar | +3,6 · +10,5 · −0,6 · +0,9 | C 12 → C 12 (marge blanc) |
| Rubí | −1,4 · +9,4 · +1,9 · −0,5 | C 28 → C 28 (marge blanc) |
| Bell-lloc | −7,8 · +0,4 · −0,6 · +0,5 | M 8 → **C 12** («(msnm)» sencer; registre #14) |
| Linyola | −2,4 · +1,2 · −0,7 · +0,1 | C 30 → **M 6** |
| Alcoletge | +1,7 · +0,4 · −0,2 · −2,7 | M 10 → M 10 |
| Vilanova | −0,9 · +2,8 · +1,0 · +6,7 | C 32 → **M 4** |
| Anciles | +0,4 · +1,9 · +1,4 · +2,0 | M 4 → M 4 |

`fig_tall` **3 M · 4 C → 4 M · 3 C** (100 % mateixa font, com abans); imatges **30 · 4 · 15 · 7 → 31 M · 3 C · 15 X · 7 ND
(69 %)**. Escalars: l'únic moviment és `adjacent_intro` a Castellar (M → C) i Alcoletge (C → X), i és **contaminació
del Cadastre**: el servei `ConsultaMunicipio` respon «problemas tecnicos. Tiempo estimado desde las 15.15H hasta las 19.00H» (avaria anunciada, verificada amb
`curl` a les 17 h; a les 13:44, run `altres-b`, funcionava), els adjacents es resolen sense i la frase canvia. Les taules són
idèntiques (292 · 99 · 88). Per als escalars, la referència continua sent `altres-b` fins a una re-mesura amb el
Cadastre viu; per a les imatges, `2026-09-09-m341-tall`.

### Tests

+3 (`test_peca3_retall_tall.py`, 7 en total). Suite: 31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt`
**+ 21 de `test_cadastre_progressive.py`** (servei en viu, la mateixa avaria; els 7 municipis × 3 proves) / 2505 verds
/ 5 omesos (235 s). Repetits sols amb el Cadastre caigut: 21 vermells igual. Cal repetir-los quan el servei torni.

### Latència / cost

0 tokens en tota l'acció. Estudi ≈ 90 s per passada (NCC a 100 dpi, 7 projectes); retall, mil·lisegons.

### Limitacions conegudes

- Els 5 mm i els 40 mm surten dels 7 fulls del mateix estudi (in-sample): distàncies de la plantilla de G3 (eix,
  línies de les etiquetes), no una llei. Si l'Eva canvia de plantilla de plànol, tornar-ho a mesurar amb l'estudi.
- Un traç amb items barrejats (`re` + `l`) continua valorant-se per la caixa: cap dels 7 en té.
- El marge blanc superior (Castellar, Rubí) i «(msnm)» tallat (Bell-lloc) queden a C per decisió: sempre igual.
- `adjacent_intro` de Castellar i Alcoletge: pendent de confirmar amb el Cadastre viu que tornen a M i C.

### GO/NO-GO

- ✅ Linyola i Vilanova sense llegenda ni plànol; Bell-lloc amb l'eix sencer; Alcoletge recuperat (T +0,4).
- ✅ Cap altra cel·la d'imatge moguda; taules idèntiques; suite amb els mateixos vermells + els 21 del Cadastre caigut.
- ⏳ Commit pendent de GO del Josep. ⏳ Re-mesura d'escalars i els 21 tests quan el Cadastre torni.

### Següents passos

- Acció 4: wizard amb les alternatives visibles (els lectors escriuen 2-3 candidats per ranura).
- Preguntes 30-34, 36-38 amb el Josep; workflow `ALTRES` amb l'Eva.

*Fi entrada 2026-09-09 (3). Acció 3: estudi del retall del tall; `_ink_rects`, blanc = 5 mm, finestra ≥ 40 mm; `fig_tall` 3 → 4 M; dues C estètiques es queden.*
