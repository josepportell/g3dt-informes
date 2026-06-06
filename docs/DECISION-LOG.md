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
