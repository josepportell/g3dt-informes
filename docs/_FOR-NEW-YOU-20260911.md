# FOR NEW YOU — 2026-09-11 — PUJADA D'IMATGES des de la finestreta FETA per a qualsevol ranura (fotos, assaigs, projecte, situació, geològic, tall, cullera) + els tres pendents (peu editable, «Guardar» coherent, neteja); mesures idèntiques; el Josep ho ha provat («la millora és gran»)

**Escrit:** 2026-09-10 (tarda), en tancar la sessió. **Per a:** la sessió del 2026-09-11 o la següent.
**Substitueix** `_FOR-NEW-YOU-20260910.md` (les seves seccions 3, 4, 5 i 7 —regles, invariants de l'acció 4, procediments,
«què NO fer»— continuen vigents; aquest doc hi afegeix, no les repeteix).
**Recap d'una frase:** l'Eva pot pujar una imatge seva a qualsevol ranura de l'informe des de la finestreta d'alternatives
(`POST /api/alternatives/{p}/upload` → la mateixa lògica que `/choose`), escriure el peu de les figures del projecte, i el
sistema esborra les pujades que ja no són a cap ranura; cap mesura s'ha mogut (M341 `2026-09-10-m341-pujada` idèntic a
`2026-09-09-m341-nit`), la suite té els mateixos 31 vermells i 2545 verds.

Branca `experiment/nivell-a-2026-08`, in-place a `g3dt-prod/`, arbre net. `production/g3dt-eva-v1` @ `123b4f2` (sense push).
Mai proposar pull ni merge a l'Eva. Commits d'avui: `4e45857` (backend pujada) · `2832af7` (wizard) · `bad0cbc` (docs) ·
`3b0129a` (pendents #10-#12) · `eb87736` (docs) · el d'aquest handoff.

## 1. Ordre de lectura

1. Aquest document.
2. `STATUS.md` (els dos primers paràgrafs: tarda i matí d'avui) i `.claude/sessions/2026-09-10-session.md`.
3. DECISION-LOG `2026-09-10` (10 decisions: per què endpoint propi, per què nom = ID, per què `rel` sense `src`, per què
   les tres figures automàtiques s'apliquen DESPRÉS del camí determinista) i `2026-09-10 (2)` (peu, «Guardar», neteja,
   i l'incident de la neteja manual).
4. `docs/imatges/PLA-PUJADA-IMATGES-WIZARD-2026-09-10.md` §0-§2: la revisió del pla del matí contra el codi (cinc esmenes
   amb línia); el §3 «v2» ja no és v2 (el Josep ho va voler tot al mateix lliurament).
5. `docs/imatges/PENDENTS-IMATGES.md` §3: #10-#12 fets; oberts #8, #9, #1, #3, #4, #6.
6. Memòries: `project_imatges_pujada_wizard_2026-09-10`, `feedback_no_rm_test_state_you_did_not_create` (nova, llegir-la
   abans de tocar `~/g3dt-prod-workspace`), `feedback_wizard_ui_rules_josep`, `feedback_reference_projects_are_situations_not_targets`.
7. `docs/PREGUNTES-EVA-PENDENTS.md` (30-38, 19a, 23, 28, 29). Mai enviar-les sense el Josep.

## 2. On som (mesura)

| run | què | imatges (M · C · X · ND) | `fix` | escalars | taules |
|---|---|---|---|---|---|
| `2026-09-09-m341-nit` | REFERÈNCIA (acció 4) | 31 · 3 · 15 · 7 (69 %) | 81 M · 21 X | 315 · 44 · 120 · 31 → 75 % | 82 % |
| `2026-09-10-m341-pujada` | després de la pujada (E7 + situació + auto) | **idèntic** | idèntic | idèntic | idèntic |

Continua fent servir `-nit` com a nom de referència als `diff` (o `-pujada`: són el mateix). Suite: 31 vermells amb els
NOMS de `docs/wizard-headless/mesures/suite-vermells-esperats.txt` / 2545 verds / 5 omesos (289 s, Cadastre viu). Els 21
de `test_cadastre_progressive` només cauen amb el Cadastre en avaria.

## 3. Regles interpretatives noves (a més de les del handoff del 10)

- **Una pujada és una tria més.** Tot el que posi una imatge en una ranura ha de passar per `_apply_alternative_choice`
  (`web/api.py`): és qui guarda `_lector_selection` la primera vegada, aplica «una foto, un forat», reordena les figures
  del projecte i crida la neteja. No hi ha una segona manera d'escriure `photo_selection.json` / `figure_selection.json`
  des del wizard (des d'avui `select_photos` també hi passa en esperit: conserva la resta del fitxer).
- **Una pujada que no és a cap ranura no existeix.** `_sweep_unreferenced_uploads` recorre QUALSEVOL cadena de les dues
  seleccions: si una ranura nova guarda el `rel` d'una pujada dins d'aquests dos JSON, ja queda protegida; si el
  guardés en un altre lloc (p. ex. `user_data.json`), la neteja l'esborraria. Guardar-ho sempre a les seleccions.
- **El peu variable només existeix a les figures del projecte.** Els altres peus són text fix de la plantilla; el del
  geològic diu «(Font: ICGC, modificat)», que és el que són els mapes que l'Eva compon. Defectes: pujada →
  «Detall del projecte. Font: G3DT.» (decisió del Josep 2026-09-10), entrada del lector → «Detall del projecte. Font: Projecte.».
- **M341 només es repeteix si canvia el generador o `apply_selection`.** El peu, la neteja i `select_photos` són dades
  de la selecció: no mouen res del corpus (cap projecte del corpus té `source: user`).
- **La còpia de proves `~/g3dt-prod-workspace/<P>` és COMPARTIDA amb el Josep**, que hi entra pel wizard mentre tu
  treballes. El que hi hagi que no hagis creat tu és seu (incident del 10: `rm -rf validation/uploads` va esborrar dues
  pujades seves). Còpia de seguretat dels JSON UNA vegada al principi; esborrar només els fitxers concrets que has creat.
- **Els fitxers de `schemas/formats/learned/` que apareixen després d'una prova funcional al wizard NO es commitegen**
  (el format learner escriu quan es desa; el Josep: «no hi havia res a aprendre de les meves seleccions»). `git checkout`
  del modificat i esborrar el nou, com s'ha fet avui.

## 4. Invariants nous (no desfer)

- `web/api.py` `_store_uploaded_image`: nom `YYYYMMDD-HHMMSS-<6 hex>.ext` — només dígits, guions i `a-f`, perquè cap
  regla pel nom l'agafi (`_find_composed_geological_map` busca «geol»; `_project_cache_keys` `tall|situ|plànol|A.01`).
  El nom original va a `validation/uploads/imatges/pujades.json`. PIL `verify` abans de res; `exif_transpose`; RGB;
  costat llarg ≤ 2.400; PNG es queda PNG (RGBA si cal). No tornar a guardar l'original: un JPEG de mòbil de 10 MB
  entraria sencer al `.docx` (`InlineImage` no recodifica).
- `_entry_ok`: tot `kind != "project_page"` ha d'apuntar a un sufix de `_IMAGE_EXTENSIONS` (abans una `entry` cap a un
  PDF passava i la miniatura sortia buida). L'`entry` d'una pujada porta `rel` i NO `src` (un `src` absolut no sobreviu
  la còpia workspace ↔ Windows i `_entry_ok` el rebutjaria); el nom de la cau porta `nohash`, i el fitxer ja és únic.
- Tres llocs que han de dir el mateix per a geològic/tall/cullera: `_AUTO_FIGURE_SLOTS` (api: ranura → clau),
  `apply_selection` (lector_figures: clau → `fig_*_image`) i `_USER_AUTO_FIGURE_KEYS` (image_manager: clau del context →
  amplada). A `build_context` el PRIMER bucle de la selecció les salta i el bloc del final (després de
  `fig_correlation_image`) les aplica: el geològic s'assigna sense condició al mig, per això no poden anar abans.
- Situació d'una sola imatge: `apply_selection` posa `fig_situacio_image_1` i `fig_situacio_image_2 = ""`;
  `image_manager` només fa 70 mm de costat si hi ha les DUES; amb una, `IMAGE_WIDTH_MAIN_PLAN` (150).
- `_SELECTION_SLOTS` (api) inclou `fig_geological_image`/`fig_correlation_image`/`fig_spt_cullera_image`: el calaix de la
  pestanya diu «Tria de l'Eva» quan hi ha pujada i cau al prefix de la cau quan no.
- `list_photos` llista `validation/uploads/imatges/*` amb `kind: upload` i el nom original: sense això
  `renderPhotoSlots` (`review.html`) no troba l'actual a la llista i pinta la ranura BUIDA.
- `select_photos` carrega el fitxer, guarda `_lector_selection` un cop, `update` amb les 5 ranures, conserva la resta;
  `reset_photos` crida la neteja. `_apply_alternative_choice` crida la neteja a les DUES branques.
- `image_manager._find_composed_geological_map` exclou `validation/` (`'validation' not in p.relative_to(...).parts`).
- `review.html`: `afterChoiceSaved(saved, target, okMessage)` és l'únic «després de desar» (tria, pujada, peu);
  `renderWizardImages` fa `loadPhotos()` primer quan `lastPhotosData` és null (la vista prèvia de les automàtiques ve del
  calaix); `#altCaption` només a `fig_projecte_*`; `UPLOAD_PROJECT_CAPTION` (JS) = `_UPLOAD_PROJECT_CAPTION` (Python);
  `#altUploadStatus` viu dins la fila d'accions; `showAlternatives` continua sent el popup «+N» dels camps de text.
- Regles del Josep del 09 (finestreta): res abans del pipeline; s'obre amb clic; aspa; font per ranura; cap panell sol.
  El botó de pujada és DINS la finestreta i sempre visible; a les automàtiques el botó de la ranura diu «Canviar la imatge».

## 5. Procediments (a més del §5 del handoff del 10)

```bash
R=/home/josep/projects/claudecode-job/clients/g3dt-prod; cd "$R"; git branch --show-current; git status --short; git log --oneline -6
# servidor per al Josep (SENSE G3DT_PROJECTS_DIR); reiniciar després de tocar web/api.py (uvicorn sense reload)
pgrep -f "[.]venv/bin/python -m web$" | xargs -r kill; (PYTHONPATH=$PWD setsid nohup .venv/bin/python -m web > /tmp/web.log 2>&1 < /dev/null &)
# pujada a mà (el peu només compta a fig_projecte_*)
curl -s -X POST "http://localhost:8765/api/alternatives/4001612%20BELL-LLOC/upload" -F slot=fig_projecte_2 -F "caption=Façana. Font: G3DT." -F "file=@/cami/foto.jpg;type=image/jpeg"
curl -s "http://localhost:8765/api/alternatives/4001612%20BELL-LLOC" | python3 -c "import json,sys; d=json.load(sys.stdin); print({k:(v['source'],len(v['alternatives']),bool(v['current'])) for k,v in d['slots'].items()})"
# tests de la pujada (31, ~6 s) i suite (10 min de timeout; diff pels NOMS)
PYTHONPATH=$PWD .venv/bin/python -m pytest tests/test_alternatives_api.py tests/test_peca7b_lector_figures.py tests/test_peca6_mapa_geologic.py -q --no-header -p no:cacheprovider
PYTHONPATH=$PWD .venv/bin/python -m pytest tests -q --no-header -p no:cacheprovider > /tmp/suite.txt 2>&1
diff <(grep '^FAILED' /tmp/suite.txt | sed 's/ - .*//' | sort) <(grep -v '^#' docs/wizard-headless/mesures/suite-vermells-esperats.txt | sort)
rm -f docs/diagnostics/ai_pipeline_demo-project_$(date +%Y%m%d).md     # artefacte de la suite, abans de git add
# sintaxi del JS inline de review.html (9.000+ línies): node --check sobre el bloc <script>
# M341 (només si canvia el generador o apply_selection): com al handoff del 10 §5; referència -nit (= -pujada)
```

Caus: renders de la selecció a `/home/josep/g3dt-prod-cache/images/figsel_<tag>_<stem>_p0_<md5|nohash>_<crop>.jpg` (la
neteja esborra `figsel_*_<stem>_*` de les pujades que cauen). Pujades: `<projecte>/validation/uploads/imatges/`.
Playwright MCP: `browser_file_upload` només accepta fitxers dins del projecte o de `.playwright-mcp/` (crear-hi la
còpia, esborrar la carpeta al final; les captures surten desquadrades, però les comprovacions funcionals via
`browser_evaluate` van bé: `showSlotAlternatives('fig_geological')`, `altData.slots`, `lastPhotosData.figures`).

## 6. Seqüència d'obertura suggerida

1. `git branch --show-current` (= `experiment/nivell-a-2026-08`), `git status --short` (net), `git log --oneline -6`.
2. Llegir STATUS (dos paràgrafs) i la sessió del 10; confirmar que no ha aparegut cap `schemas/formats/learned/*` nou.
3. `curl` al Cadastre abans de qualsevol mesura d'escalars.
4. Si el Josep vol seguir amb el wizard: engegar el servidor (§5) i provar amb Bell-lloc. Recordar que la còpia és
   compartida: no netejar res que no hagis creat.
5. Si toca codi a la finestreta: `grep "function <nom>("` abans d'afegir cap funció; els noms nous d'avui són
   `afterChoiceSaved`, `isUploaded`, `autoFigurePreview`, `altUploadButton`, `pickUploadForSlot`, `uploadImageForSlot`,
   `saveCaption`, `UPLOAD_PROJECT_CAPTION`.
6. Preguntes a l'Eva (30-38, 19a, 23, 28, 29) amb el Josep: moltes discrepàncies restants són judici seu, i ara que pot
   pujar el que vulgui, algunes es resolen soles.

## 7. Què NO fer

- No fer `rm -rf` de cap carpeta de `~/g3dt-prod-workspace/<P>` (incident del 10). Esborrar només fitxers que aquesta
  sessió ha creat, i mirar les hores (`ls -la --time-style=+%H:%M`) abans.
- No commitejar `schemas/formats/learned/*` sortits de proves funcionals al wizard.
- No afegir una segona via d'escriptura de les seleccions fora de `_apply_alternative_choice` / `select_photos`.
- No posar paraules al nom dels fitxers pujats (ni el nom de la ranura: `fig_geologic` conté «geol»).
- No tornar a «Font: Projecte.» com a defecte d'una pujada; no inventar un camp «font» separat del peu (els signats
  tenen el peu com a frase lliure).
- No tocar `detect_section_region`, el mapa ICGC ni `geocode_coordinates.py`; no repetir el lector «fins que surti bé»;
  cap nom de projecte als skills (`grep` = 0).
- No engegar el servidor amb `G3DT_PROJECTS_DIR` si el Josep hi ha d'entrar pel flux de xarxa.
- No enviar cap pregunta a l'Eva sense el Josep. No proposar pull/merge a l'Eva.

## 8. Tasques obertes

- PENDENTS §3 **#8**: «Restablir selecció IA» esborra `photo_selection.json` sencer (alternatives incloses); un botó que
  restauri `_lector_selection` i torni a `source: lector`. **#9**: `select_photos_ai` pot reescriure la selecció del lector
  si tots els forats són `null`. **#1** foto de materials per punt (pregunta 33). **#3**, **#4**, **#6**.
- Passada dels lectors amb `alternatives` als 7 del corpus (quan toqui per un altre motiu: ~10 min, ~4 $, variància).
- `docs/imatges/ANALISI-DISCREPANCIES-2026-09-09.md` §3: accions 2, 5 (workflow `ALTRES` amb l'Eva), 7-10.
- Bloc 5 del PLA (castellà).
- Que l'Eva faci servir la pujada en un projecte seu (és el GO/NO-GO que queda a les dues entrades d'avui).
- Una passada del lector (`write_selection`) reescriu `figure_selection.json` amb les claus fixes i perd `geologic`/`tall`/
  `cullera` i qualsevol tria de l'Eva (pre-existent per a totes les tries; els lectors només es passen a mà). Si el lector
  entra mai al pipeline, cal resoldre-ho abans.

## 9. Guanys que no es veuen als números

- L'Eva ja pot posar QUALSEVOL imatge a QUALSEVOL lloc de l'informe sense buscar fitxers ni tocar carpetes, amb el peu que
  vulgui a les figures del projecte, i tornar enrere en un clic. El mapa geològic —la figura que el codi no pot reproduir
  (pregunta 34)— ja té sortida.
- Tres defectes que cap mesura veia: `_entry_ok` acceptava entrades cap a PDF (miniatura buida en silenci), el mapa
  geològic es podia triar per nom dins `validation/` (una evidència HITL «…geol…» hauria anat a l'informe), i «Guardar»
  de la pestanya esborrava la tria del lector.
- `_apply_alternative_choice` compartit: la finestreta, la pujada i (en esperit) la pestanya escriuen igual; la
  pròxima ranura costa tres línies.
