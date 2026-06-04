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
