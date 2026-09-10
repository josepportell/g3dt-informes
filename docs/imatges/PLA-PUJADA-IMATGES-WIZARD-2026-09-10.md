# PLA — Pujar una imatge des de la finestreta d'alternatives del wizard (2026-09-10)

**Estat:** ✅ **IMPLEMENTAT el mateix dia** (DECISION-LOG 2026-09-10) amb el GO del Josep i quatre decisions seves que
modifiquen aquest pla: (1) geològic, tall i cullera entren al mateix lliurament (el §3 «v2» ja no és v2); (2) peu de la
figura del projecte pujada «Detall del projecte. Font: G3DT.» i el camp de peu/font queda com a pendent (PENDENTS §3
#10), no com a E5; (3) el nom del fitxer pujat és un ID (`YYYYMMDD-HHMMSS-<6 hex>`), el nom original va a `pujades.json`;
(4) normalització sí, `fig_situacio` sí. **Substitueix** el pla escrit en conversa el mateix matí (esmenes al §2).
**Context:** acció 4 d'imatges (DECISION-LOG 2026-09-09 (4) i (5)): la finestreta `#altZone` ensenya, per a cada ranura
d'imatge de l'informe, la tria actual i les alternatives del lector; l'Eva en tria una amb un clic (`source: user`).
**Petició del Josep:** si el pipeline no ha trobat la imatge que l'Eva vol (sigui a la carpeta o no), que la pugui
pujar des de la mateixa finestreta i que entri a la ranura amb la mateixa lògica que una alternativa.

## 0. Veredicte de la revisió

El pla del matí encerta el que importa: **la maquinària per posar una imatge qualsevol del projecte en una ranura ja
existeix i és genèrica**, i la pujada és només «fer arribar el fitxer al projecte i cridar-la». Això es manté. Canvien
cinc coses, totes per lectura del codi, no per gust:

1. **La pestanya «Imatges» contradiria el Wizard.** `renderPhotoSlots` resol la foto actual buscant-la a la llista de
   `list_photos` (`review.html:7787-7788`); una pujada fora de `FOTOGRAFIA/` i `ALTRES/` hi sortiria com a ranura
   buida mentre la secció del Wizard la mostraria plena. Cal que `list_photos` llisti les pujades. → §2 E1.
2. **Endpoint prim propi en lloc de `upload-evidence` + `choose` des del client.** La carpeta `validation/uploads/`
   és la de l'evidència HITL (PDF, XLS i fotos de documents): si la llistem com a fotos hi sortirien fulls de laboratori.
   I `upload-evidence` accepta `.pdf`, de manera que la comprovació «és una imatge» quedaria a l'altra banda, el client
   hauria de construir l'`entry` intern (`kind`) i hi hauria dues anades i tornades. → §2 E2.
3. **Normalitzar la imatge en pujar-la** (EXIF, mida): `InlineImage` incrusta els bytes tal qual
   (`image_manager.py:988-1001`) i `get_thumbnail` no aplica l'EXIF (`api.py:978`). Per a les fotos de la carpeta és
   l'estat actual; per a la pujada, que és nostra, no té sentit heretar-ho. → §2 E3.
4. **`fig_situacio` entra**, com a pas 1.1 del mateix lliurament i no com a «opció A per defecte»: el precedent que feia
   por (la «regla dels insets» retirada) era la *proposta del lector* aplicant-se sola; la *tria de l'Eva* ja mana avui.
   → §2 E8.
5. **El que la pujada NO cobreix queda dit:** geològic, tall i cullera no són a la finestreta ni tenen cap override
   d'usuari a `image_manager` (el de la línia 1228 és de rols SmartScan). És precisament on una pujada valdria més
   (pregunta 34, workflow `ALTRES`). → v2, §3.

Dues troballes col·laterals que cal tancar de passada (§2 E6, E7): `_entry_ok` no comprova l'extensió i
`_find_composed_geological_map` escombra `validation/` pel nom «geol».

## 1. El que ja hi ha (verificat, amb línia)

| Peça | On | Què fa que ens serveix |
|---|---|---|
| `POST /api/alternatives/{p}/choose` | `web/api.py:1500` | Desa UNA ranura amb `source: user`, conserva la resta i `_lector_selection`; fotos per `rel`, figures per `entry`; `placed`/`cleared` a la resposta |
| `_entry_ok` | `api.py:1344` | Accepta qualsevol `entry` amb `kind` i `rel` dins el projecte (o `src` dins projecte/cau) |
| `render_entry` | `lector_figures.py:448` | Tot `kind != "project_page"` és «obre la imatge i, si hi ha `crop`, retalla-la»; `crop` absent = sencera; `exif_transpose` inclòs |
| `apply_selection` | `lector_figures.py:500` | Renderitza la selecció a la cau `figsel_*` i la dona al generador; la SELECCIÓ mana també quan diu «cap» |
| `_load_user_photo_selection` | `image_manager.py:295` | `project / rel`, dins el projecte, `is_file()` → prou |
| `_fig_thumb_url` + `/api/figure-preview` | `api.py:1362`, `1199` | Miniatura de qualsevol `entry` renderitzable, servida des de la cau |
| `/api/thumbnail?file=rel` | `api.py:978` | Miniatura de qualsevol imatge dins el projecte |
| `_figures_from_selection` | `api.py:1092` | El calaix de figures llegeix la selecció aplicada (no el filtre de prefixos): una pujada hi surt sola |
| `upload_evidence` + `_safe_upload_filename` | `api.py:2489`, `2474` | Patró de pujada segur (nom sanejat NFKD, límit 25 MB, allowlist) → el copiem, no el reutilitzem (E2) |
| `_hitlPickFile` / `_hitlUploadAndExtract` | `review.html:6660`, `6676` | Idioma JS de la casa: `<input type=file>` dinàmic + `FormData` |
| `validation` a `_SKIP_DIRS` | `concept_scout/scanner.py:15`, `smartscan/classifier.py:121`, `fileminer` | Les pujades no entren als escàners del pipeline |
| `list_eva_pngs` | `lector_fotos.py:116` | Salta `validation/`: les pujades no es confonen amb PNG d'ALTRES |

Conseqüència: **cap canvi a la plantilla `.docx`, cap canvi al generador d'informes, cap canvi als lectors.**

## 2. Esmenes al pla del matí (cadascuna amb el motiu)

**E1 — Les pujades han de sortir a `list_photos`** (`api.py:1257`), amb `kind: "upload"` i etiqueta «pujada per l'Eva».
Sense això: la pestanya «Imatges» pinta la ranura buida (`review.html:7788`: `photos.find(...)` → `null`), i l'Eva no
pot reaprofitar una pujada per a una altra ranura. Amb això: els tres llocs (secció del Wizard, finestreta, pestanya)
diuen el mateix. Només es llisten les de la carpeta pròpia (E2), no l'evidència HITL.

**E2 — Un endpoint propi, prim: `POST /api/alternatives/{p}/upload`** (multipart: `file`, `slot`, `caption` opcional).
- Desa a **`validation/uploads/imatges/`** (subcarpeta pròpia; `extract-targeted` resol `validation/uploads/<upload_id>`
  a `api.py:2564`, no hi ha col·lisió).
- Valida que és una imatge **de debò** (PIL `open` + `verify`, no l'extensió), mida ≤ 25 MB, `slot` de la llista.
- Normalitza (E3) i crida **la mateixa lògica** que `/choose`: el cos actual de `choose_alternative` s'extreu a
  `_apply_alternative_choice(project_path, req: AlternativeChoice) -> dict` i el fan servir les dues rutes.
  Una sola petició; la resposta és la de `/choose` més `rel`. El client no sap què és un `kind`.
- Per què no `upload-evidence`: accepta `.pdf/.xls/.docx/.msg/.txt` (la comprovació d'imatge s'hauria de fer al
  `choose`), desa a la carpeta de l'evidència HITL (E1 la llistaria com a foto), i el JS hauria de saber l'esquema
  intern de `figure_selection.json`.

**E3 — Normalització en pujar:** `ImageOps.exif_transpose` → RGB → costat llarg ≤ 2.400 px → JPEG q=90 (PNG es queda
PNG: captures de visor amb text). Per què: `IMAGE_WIDTH_PHOTO = 120` mm i `IMAGE_WIDTH_LOCATION = 150` mm
(`image_manager.py:32-38`); 2.400 px a 150 mm són > 400 dpi. Un JPEG de mòbil de 8-12 MB entraria sencer al `.docx`
(`InlineImage` no recodifica), i una foto vertical de mòbil sense transposar surt girada a la miniatura del wizard.
Trade-off acceptat: el fitxer desat no és byte a byte l'original de l'Eva; és el nostre espai (`validation/`), no la
seva carpeta.

**E4 — L'`entry` d'una pujada porta `rel` i NO `src`.** `_entry_ok` rebutja un `src` que no existeixi; un camí absolut
no sobreviu a la còpia `~/g3dt-prod-workspace/<P>` ↔ Windows; `render_entry` ja cau a `project / rel`. Cost: el nom a la
cau porta `nohash` (`_out_name`, `lector_figures.py:479`); acceptable perquè el nom del fitxer ja és únic
(`YYYYMMDD-HHMMSS_<rand>_<nom>`). Forma: `{"kind": "upload", "rel": "validation/uploads/imatges/…jpg"[, "caption": …]}`.

**E5 — Peu de figura per a `fig_projecte_1/2`.** El defecte actual és «Detall del projecte. Font: Projecte.»
(`api.py:1541`); per a una imatge que l'Eva puja no sabem si la font és el projecte, un visor o una foto seva, i
imprimir-ho seria afirmar-ho. La finestreta mostra, només per a aquestes dues ranures, un camp «Peu de la figura»
prefixat amb «Detall del projecte.» (sense «Font:») que l'Eva pot completar; viatja com a `caption` (≤ 200 car.).
`fig_assaigs`, `fig_situacio` i les fotos tenen peu fix a la plantilla: res a demanar.

**E6 — `_entry_ok` sense extensió (`api.py:1344`).** Es manté l'esmena, però per a **tot `kind != "project_page"`**
(no només `upload`): el forat és de l'API `/choose` en general (avui una `entry` `{"kind":"img","rel":"x.pdf"}` passa,
`render_entry` falla en silenci i la miniatura surt buida). Comprovació: sufix ∈ `_IMAGE_EXTENSIONS`. Amb la pujada
normalitzada el fitxer sempre és una imatge; el tall és per a l'API. Els fixtures de `test_alternatives_api.py`
no en tenen cap que trenqui (l'únic `kind: "img"` apunta a `../x.png` i ja espera 400 per traversal).

**E7 — `_find_composed_geological_map` (`image_manager.py:755`)** fa `rglob('*')` **sense excloure `validation/`** i
tria «un fitxer d'imatge amb "geol" al nom». Una pujada (o una evidència HITL) que es digui «mapa geol.png» passaria
a ser el mapa geològic de l'informe sense que ningú l'hagi triat. Afegir `'validation' not in p.parts` ara. És
mesura-neutral: **0 fitxers «geol» dins `validation/`** al corpus, e2e i workspace (comprovat 2026-09-10). El canal
explícit per pujar el geològic és la v2 (§3).

**E8 — `fig_situacio`: dins, com a pas 1.1.** Amb el codi actual una `entry` sense `crops` posa `situacio = null` en
silenci (`api.py:1556`) i la pujada es perdria sense avís: o s'exclou el botó o s'implementa. S'implementa, perquè el
que es va retirar el 2026-09-09 va ser que la proposta *del lector* s'apliqués sola (Bell-lloc sí, Alcoletge no); la
tria *de l'Eva* (`source: user`) ja mana. Canvis: (a) `choose`, branca `fig_situacio`: acceptar `entry` sense `crops`
(guardar amb `crop: null`); (b) `apply_selection`: si `situacio` és `user` i no té `crops`, renderitzar-la sencera a
`fig_situacio_image_1` i posar `fig_situacio_image_2 = ""`; (c) `image_manager.py:1184`: 70 mm de costat només si hi
ha les dues; amb una sola, l'amplada que faci servir avui el camí determinista d'una sola imatge (comprovar-ho abans:
la línia 1110 fa servir 70 mm per al retall cadastral, el compost de la peça 5 pot ser diferent); (d) `list_alternatives`
ja ho pinta (`fig_item` sense `crops` → una miniatura). La plantilla ja té el cas d'una sola imatge
(`{%p if not fig_situacio_image_2 %}`, peça 7a). **Porta:** els tres `diff` de M341 contra `-nit` a zero (cap projecte
del corpus té `situacio` amb `source: user`).

**E9 — Fora d'abast, però dit:** `fig_geologic`, `fig_tall` (correlació) i `fig_cullera` no són a `altData.slots`
(«automàtics, sense tria») i `image_manager` no té cap punt on una tria de l'Eva els substitueixi. És on la pujada
valdria més: el geològic de l'Eva és una vista del visor que el codi no reprodueix (pregunta 34; peça 6) i el tall és un
dibuix seu. → **v2** (§3): claus `geologic` i `tall` a `figure_selection.json` honorades abans del camí determinista,
i les dues ranures a la finestreta. Anotar a PENDENTS §3.

**E10 — Pre-existent que hi topa (no ho arregla aquest pla):** «Guardar» de la pestanya «Imatges» (`select_photos`,
`api.py:1570`) reescriu `photo_selection.json` **sense** `_lector_selection` ni `alternatives`. Si l'Eva puja i
després desa des de la pestanya, la tria del lector deixa de tornar com a alternativa. Va amb PENDENTS §3 #8-#9;
anotar-ho perquè la pujada ho fa més probable (dues vies d'escriptura sobre el mateix fitxer).

**E11 — Opcional, barat:** arrossegar i deixar anar sobre `#altZone` (patró `.ms-drop-zone.dragging`,
`review.html:1511`). Mateixa funció que el botó. Si complica la finestreta (30 vw × 30 vh), fora.

## 3. Abast per fases

| Fase | Ranures | Toca | Porta |
|---|---|---|---|
| **v1** | `site_1`, `site_2`, `dpsh`, `sondeig`, `materials`, `fig_assaigs`, `fig_projecte_1`, `fig_projecte_2` | `web/api.py`, `review.html`, `image_manager.py` (només E7), tests | suite amb els mateixos vermells; M341 idèntic a `-nit` |
| **v1.1** | `fig_situacio` (una sola imatge, sencera) | `api.py` (branca situació), `lector_figures.apply_selection`, `image_manager.py:1184`, tests | 3 `diff` M341 = 0 |
| **v2** | `fig_geologic`, `fig_tall` | `image_manager` (override d'usuari abans del determinista), `figure_selection.json`, finestreta | disseny propi; pregunta 34 a l'Eva abans |

v1 i v1.1 es fan seguides al mateix lliurament (v1.1 és ~40 línies); v2 és una altra decisió.

## 4. Disseny

### 4.1 Flux (v1)

```
Eva obre la finestreta d'una ranura (clic a «Alternatives (n)»)           ← ja existeix
  └ botó «📁 Puja una imatge» (+ camp «Peu de la figura» a fig_projecte_*)   ← nou
       └ tria el fitxer → POST /api/alternatives/{p}/upload (file, slot[, caption])
            servidor: PIL verify → exif_transpose/RGB/≤2400 px → validation/uploads/imatges/<ts>_<rand>_<nom>.<ext>
                      → _apply_alternative_choice(slot, rel | entry{kind: upload, rel[, caption]})
                      → {status, slot, placed, cleared, rel}
       └ client: el mateix «després de desar» que chooseAlternative
                 (missatge placed/cleared · altData = null · loadPhotos() · renderWizardImages() · reobrir la ranura)
```

### 4.2 Contracte

```
POST /api/alternatives/{project_name}/upload      multipart/form-data
  file     imatge; sufix ∈ {.jpg .jpeg .png .gif .bmp .tif .tiff}; ≤ 25 MB; ha d'obrir-se amb PIL
  slot     site_1 | site_2 | dpsh | sondeig | materials | fig_assaigs | fig_projecte_1 | fig_projecte_2   (v1.1: fig_situacio)
  caption  opcional, només fig_projecte_*; ≤ 200 car.; defecte «Detall del projecte.»
200  {"status":"saved","slot":…,"placed":…,"cleared":[…],"rel":"validation/uploads/imatges/…"}
400  ranura desconeguda · no és una imatge · imatge massa gran en píxels (DecompressionBomb)
413  més de 25 MB          404  projecte
```

Resultat als JSON de `validation/` (exactament el que escriu `/choose` avui):

```json
photo_selection.json   {"source":"user", "materials":"validation/uploads/imatges/20260910-153012_a1b2c3_P3_materials.jpg", …, "_lector_selection":{…}}
figure_selection.json  {"source":"user", "projecte":[{"kind":"upload","rel":"validation/uploads/imatges/…png","caption":"Detall del projecte. Vista del carrer."}], …}
```

### 4.3 Finestreta

- El botó va a la fila d'accions de `showSlotAlternatives` (`review.html:~8003`), **sempre visible** (també amb 0
  alternatives: és el cas d'ús), al costat de «Cap imatge en aquesta ranura».
- Mentre puja: una línia d'estat a la mateixa fila («Pujant P3.jpg (4,1 MB)…»), sense esborrar la resta.
- En acabar: la finestreta es queda oberta a la mateixa ranura, «Actual» = la pujada, insígnia «Tria de l'Eva»
  (font per ranura, com ara), i a «Alternatives» hi torna la tria del lector (via `_lector_selection`), com quan es tria
  una alternativa qualsevol.
- Pestanya «Imatges» i secció del Wizard: la pujada apareix com a actual amb l'etiqueta «(pujada per l'Eva)».
- Comprovacions al client abans de pujar (només per estalviar el viatge; la seguretat és al servidor): tipus `image/*`,
  ≤ 25 MB.

### 4.4 Regles d'ús del wizard del Josep (memòria `feedback_wizard_ui_rules_josep`)

| Regla | Compliment |
|---|---|
| Res «de memòria» abans de llançar el pipeline | La finestreta només existeix amb `imagesReadyFor === selectedProject` |
| Cap panell que aparegui sol; clic + aspa | El botó és dins la finestreta que l'Eva ha obert; el diàleg de fitxer és del navegador |
| La tria es fa al camp del formulari | La secció «Imatges de l'informe» del Wizard obre la mateixa finestreta |
| Font per ranura | La ranura pujada passa a «Tria de l'Eva»; les altres no canvien |
| Llistes ordenades avisen | `fig_projecte_2` amb la 1 buida → `placed` = 1 i el mateix missatge d'avui |
| «Llest» només en acabar | Sense canvi |

## 5. Canvis, fitxer per fitxer

**`web/api.py`**
1. `_apply_alternative_choice(project_path, req) -> dict`: el cos actual de `choose_alternative` (línies 1500-1567), sense
   canvis de comportament. `choose_alternative` queda en 6 línies (resoldre projecte + cridar).
2. `_entry_ok`: si `kind != "project_page"`, el fitxer resolt ha de tenir sufix ∈ `_IMAGE_EXTENSIONS` (E6).
3. `_store_uploaded_image(project_path, data: bytes, raw_name: str) -> str` (retorna `rel` posix): PIL `verify` +
   reobrir, `exif_transpose`, RGB, `thumbnail((2400, 2400))` només si és més gran, JPEG q=90 o PNG, nom
   `<ts>_<rand>_<_safe_upload_filename(stem)>.<ext>` a `validation/uploads/imatges/`.
4. `POST /alternatives/{project_name:path}/upload` (E2): validar `slot`, límit de bytes, desar, construir
   `AlternativeChoice` (`rel` per a fotos; `entry {"kind":"upload","rel":…[,"caption":…]}` per a figures), cridar 1.
5. `list_photos`: afegir les imatges de `validation/uploads/imatges/` amb `kind: "upload"` (E1). Ordre: fotos de la
   carpeta, PNG d'ALTRES, pujades.
6. (v1.1) branca `fig_situacio` de 1: acceptar `entry` sense `crops` → `{"kind","rel","crop": null}` (E8a).

**`automation/imatges/lector_figures.py`** (només v1.1): `apply_selection`, cas `situacio` `user` sense `crops` →
`fig_situacio_image_1` sencera, `fig_situacio_image_2 = ""` (E8b).

**`automation/image_manager.py`**
- `_find_composed_geological_map`: excloure `validation` de l'`rglob` (E7).
- (v1.1) línia 1184: amplada de costat només amb dues imatges de situació (E8c).

**`templates/validation/review.html`** (noms comprovats lliures 2026-09-10: `pickUploadForSlot`, `uploadImageForSlot`,
`afterChoiceSaved`, `altUploadButton`, `altCaption`)
- `afterChoiceSaved(saved, target)`: el bloc «després de desar» de `chooseAlternative` (missatges `placed`/`cleared`,
  `altData = null`, `photosLoaded = false`, `loadPhotos()`, `renderWizardImages()`), cridat des de `chooseAlternative` i
  des de la pujada (un sol lloc).
- `altUploadButton(slotKey)` + camp `#altCaption` per a `fig_projecte_*` (E5), a la fila d'accions de
  `showSlotAlternatives`.
- `pickUploadForSlot(slotKey)`: `<input type="file" accept="image/*">` dinàmic (patró `_hitlPickFile`).
- `uploadImageForSlot(slotKey, file)`: comprovacions de client, `FormData`, `fetch`, estat en línia, `afterChoiceSaved`.
- `renderPhotoSlots` i `renderWizardImages`: etiqueta «(pujada per l'Eva)» quan `kind === 'upload'` / `rel` comença per
  `validation/uploads/imatges/`.
- (E11, opcional) `dragover`/`drop` sobre `#altZone` → `uploadImageForSlot(altSlotShown, file)`.

**`tests/test_alternatives_api.py`** (+ `tests/test_peca6_mapa_geologic.py` per E7) — §7.

**Docs en tancar:** entrada DECISION-LOG, PENDENTS §3 #10 (v2 geològic/tall), #11 (E10), STATUS, sessió.

## 6. Seguretat i límits

- Nom del fitxer: `_safe_upload_filename` (NFKD → ASCII, `[A-Za-z0-9._-]`, mai buit) + prefix `ts_rand`: cap traversal,
  cap col·lisió, cap caràcter que faci mal a Windows o al `.docx`.
- Contingut: PIL decideix si és una imatge; l'extensió és només l'allowlist d'entrada. `Image.MAX_IMAGE_PIXELS` per
  defecte (~89 Mpx) atura una bomba de descompressió → 400.
- Mida: 25 MB a l'entrada (com l'evidència HITL); després de normalitzar, una foto pesa 0,5-2 MB.
- Rutes: `slot` d'una llista tancada; `rel` sempre dins el projecte (`_entry_ok`, `choose` de fotos: ja comprovat).
- Sense recollida d'escombraries de `validation/uploads/imatges/`: igual que l'evidència HITL avui. Una pujada que
  l'Eva substitueix es queda al disc (i a la pestanya, com a candidata). Acceptat; si molesta, un pendent.

## 7. Tests (tots amb `TestClient`, fixtures del fitxer existent)

| # | Què | Comprova |
|---|---|---|
| T1 | Foto: PNG 64×48 a `site_1` | 200 amb `rel` dins `validation/uploads/imatges/`; `photo_selection.json` `source: user`, `site_1 == rel`, `_lector_selection` conservat; `/api/thumbnail?file=rel` 200; `/api/photos` la llista amb `kind: upload`; `ImageManager._load_user_photo_selection()["site"]` la retorna |
| T2 | Figura: `fig_projecte_1` amb `caption` | `figure_selection.json` `projecte[0] == {"kind":"upload","rel":…,"caption":…}` sense `src`; `apply_selection` retorna un fitxer real; `list_alternatives` dona `current.thumbnail_url` no buit; una segona pujada a `fig_projecte_2` → `placed == fig_projecte_2`; `fig_assaigs` idem |
| T3 | Normalització | JPEG 4000×3000 amb EXIF orientation 6 → desat amb costat llarg ≤ 2400 i alçada > amplada; PNG es queda PNG |
| T4 | Rebuigs | `.txt` renombrat `.jpg` → 400; `slot: fig_x` → 400; `.pdf` → 400; > 25 MB (monkeypatch del límit) → 413 |
| T5 | E6 | `/choose` amb `entry {"kind":"img","rel":"25.9999/PROJECTE.pdf"}` → 400 (abans: 200 i miniatura buida) |
| T6 | E7 | `validation/uploads/imatges/mapa_geol.png` present → `_find_composed_geological_map()` no el tria |
| T7 (v1.1) | Situació | pujada a `fig_situacio` → `situacio` sense `crops`; `apply_selection` dona `_image_1` i `_image_2 == ""`; `list_alternatives` `is_default == false` amb una miniatura; «Composició automàtica del full» la torna a `null` |
| T8 | Regressió | els 3 tests actuals de `choose` passen intactes després d'extreure `_apply_alternative_choice` |

## 8. Validació i mesura (procediment del projecte)

```bash
R=/home/josep/projects/claudecode-job/clients/g3dt-prod; cd "$R"
# 0. abans de tocar res: Cadastre viu? (mou adjacent_intro i 21 tests)
curl -s 'https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/ConsultaMunicipio?Provincia=LLEIDA&Municipio=' | head -c 300
# 1. suite: noms, no comptes
PYTHONPATH=$PWD .venv/bin/python -m pytest tests -q --no-header -p no:cacheprovider > /tmp/suite.txt 2>&1
diff <(grep '^FAILED' /tmp/suite.txt | sed 's/ - .*//' | sort) <(grep -v '^#' docs/wizard-headless/mesures/suite-vermells-esperats.txt | sort)
# 2. M341 (E7 i v1.1 toquen image_manager/apply_selection): esperat 0 diferències contra -nit
PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache .venv/bin/python docs/wizard-headless/mesures/mesura_341.py 2026-09-10-m341-pujada
M=docs/wizard-headless/mesures/runs; A=2026-09-09-m341-nit; B=2026-09-10-m341-pujada
for s in castellar rubi bell-lloc linyola alcoletge vilanova anciles; do diff <(grep '^- ' $M/$A/$s/viaA/_compare_341.txt | sed 's/ gen=.*//') <(grep '^- ' $M/$B/$s/viaA/_compare_341.txt | sed 's/ gen=.*//') | grep '^[<>]' | sed "s/^/$s: /"; done
diff <(sed -n '2,28p' $M/$A/_AGREGAT-341.md) <(sed -n '2,28p' $M/$B/_AGREGAT-341.md)
diff <(sed -n '/^## Imatges (viaA)/,$p' $M/$A/_AGREGAT-341.md) <(sed -n '/^## Imatges (viaA)/,$p' $M/$B/_AGREGAT-341.md)
# 3. a mà, amb el Josep (servidor SENSE G3DT_PROJECTS_DIR), Bell-lloc a ~/g3dt-prod-workspace:
#    pujar una foto de materials i una figura de projecte amb peu; Generar Informe; obrir el .docx:
#    la foto al seu lloc, el peu imprès, numeració de figures intacta; pestanya «Imatges» = secció del Wizard
```

## 9. Seqüència de treball

1. `git status` net a `experiment/nivell-a-2026-08`; `curl` al Cadastre.
2. Backend v1: `_apply_alternative_choice` (refactor pur) → T8 verd → `_entry_ok` (E6) + T5 → `_store_uploaded_image` +
   endpoint + `list_photos` → T1-T4 → E7 + T6.
3. Frontend v1: `afterChoiceSaved` (refactor pur; provar que triar una alternativa funciona igual) → botó, picker,
   pujada, etiquetes.
4. Prova a mà amb Bell-lloc (§8.3). Set correccions d'ús del Josep si cal, com el 09.
5. v1.1 (`fig_situacio`) + T7; mesura §8.2.
6. Suite sencera; docs (DECISION-LOG, PENDENTS #10-#11, STATUS, sessió); commits en tres (backend · frontend · docs).

Esforç estimat: v1 ~100 línies de backend, ~120 de JS, ~120 de tests; v1.1 ~40 + 30. Una sessió.

## 10. GO/NO-GO (per marcar en tancar)

- ⏳ T1-T8 verds; suite amb els mateixos 31 noms vermells
- ⏳ M341 `2026-09-10-m341-pujada` idèntic a `-nit` (escalars, taules, imatges)
- ⏳ Prova a mà: `.docx` amb la foto i la figura pujades, peu imprès, numeració intacta
- ⏳ Pestanya «Imatges», secció del Wizard i finestreta coincideixen després d'una pujada
- ⏳ `grep -c` dels 7 noms de projecte als skills = 0 (no en toquem cap, però és la porta de sempre)

## 11. Pendents que genera

- **PENDENTS §3 #10** — v2: pujada per a `fig_geologic` i `fig_tall` (override d'usuari a `image_manager` abans del camí
  determinista; claus a `figure_selection.json`; ranures a la finestreta). Lligat a la pregunta 34.
- **PENDENTS §3 #11** — `select_photos` (pestanya) esborra `_lector_selection` i `alternatives` (E10); unificar les dues
  vies d'escriptura sobre `photo_selection.json` amb `_apply_alternative_choice`.
- Neteja de `validation/uploads/imatges/` (pujades substituïdes) — només si molesta.

*Fi del pla. Pujada d'imatges des de la finestreta: v1 (fotos + assaigs + projecte) i v1.1 (situació) sobre la maquinària
de `/choose`; endpoint propi, normalització, pestanya coherent, dos forats tancats de passada; geològic i tall a v2.*
