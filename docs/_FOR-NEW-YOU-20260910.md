# FOR NEW YOU — 2026-09-10 — IMATGES: accions 1, 3 i 4 FETES i commitejades; el wizard té la tria d'imatges amb alternatives (provat pel Josep amb Bell-lloc). Següent: preguntes a l'Eva, passada dels lectors amb `alternatives`, i el que quedi de l'ús real

**Escrit:** 2026-09-09 (nit), en tancar la sessió. **Per a:** la sessió del 2026-09-10 o la següent.
**Substitueix** `_FOR-NEW-YOU-20260909-1430.md` (les seves tres accions (1), (3) i (4) estan fetes; allà queden els «Què NO fer» i els procediments de mesura, que continuen vigents).
**Recap d'una frase:** de les tres accions decidides pel Josep sobre les 27 discrepàncies d'imatges, s'han fet les tres el mateix dia: (1) els PNG d'`ALTRES` són candidats del lector de fotos (Rubí vista ND → M), (3) el retall del tall mira la tinta dels traços i «blanc» són 5 mm (`fig_tall` 3 → 4 M), (4) el wizard mostra la tria de cada ranura d'imatge i les alternatives dels lectors en una finestra flotant que s'obre amb un clic; el Josep ho ha provat en local amb Bell-lloc i ha fet set correccions d'ús que ja hi són.

Branca `experiment/nivell-a-2026-08`, in-place a `g3dt-prod/`. `production/g3dt-eva-v1` @ `123b4f2` (sense push). Mai proposar pull ni merge a l'Eva. Commits d'avui (acció 4): `06d7541` (codi) · `9f9bc91` (mesura) · el de docs que tanca la sessió; els de les accions 1 i 3: `44c9106`·`aa72d41`·`c2af8a0`·`07cdc76` i `92bd384`·`04e9c52`·`949e12a`·`0a99324`.

## 1. Ordre de lectura

1. Aquest document.
2. `STATUS.md` (primer paràgraf: estat final d'avui) i `.claude/sessions/2026-09-09-session.md` («Tancament»).
3. DECISION-LOG `2026-09-09 (2)`, `(3)`, `(4)` amb la seva secció «Correcció del Josep (nit)», i `(5)` (stepper). Les correccions són set regles d'ús del wizard que NO s'han de desfer (§4).
4. `docs/imatges/PENDENTS-IMATGES.md` §0 #10-#13 (descobriments d'avui), §1 (estat per ranura), §3 #7-#9 (pendents nous).
5. `docs/imatges/ANALISI-DISCREPANCIES-2026-09-09.md` §3 (accions 1, 3 i 4 marcades FETES; queden 2, 5-10).
6. Memòries: `project_imatges_accio1_altres_2026-09-09`, `project_imatges_accio3_tall_2026-09-09`, `project_imatges_accio4_wizard_2026-09-09`, i `feedback_reference_projects_are_situations_not_targets`.
7. Preguntes a l'Eva: `docs/PREGUNTES-EVA-PENDENTS.md` (30-34, 36-38, 19a, 23, 28, 29). Mai enviar-les sense el Josep.

## 2. On som (mesura)

| run | què | imatges (M · C · X · ND) | `fix` | escalars |
|---|---|---|---|---|
| `2026-09-09-m341-peca7b` | baseline del matí | 29 · 4 · 15 · 8 (69 %) | 79 M | 313 M (74 %) |
| `2026-09-09-m341-altres-b` | acció 1 | 30 · 4 · 15 · 7 | 81 M | 315 M (75 %) |
| `2026-09-09-m341-tall` | acció 3 | 31 · 3 · 15 · 7 | 81 M | `adjacent_intro` ×2 contaminat (Cadastre caigut 15:15-19:00) |
| `2026-09-09-m341-accio4` | acció 4 (codi) | idèntic a `-tall` | idèntic | idèntic |
| **`2026-09-09-m341-nit`** | **REFERÈNCIA** (Cadastre viu) | 31 · 3 · 15 · 7 (69 %) | 81 M · 21 X (79 %) | 315 · 44 · 120 · 31 → 75 % (`adjacent_intro` torna a 2 M · 5 C) |

Taules 292 · 99 · 88 (82 %) a tots. Suite en tancar: 31 vermells amb els mateixos NOMS que `suite-vermells-esperats.txt` / 2534 verds / 5 omesos (182 s, Cadastre viu) (`docs/wizard-headless/mesures/suite-vermells-esperats.txt`
té els 31 noms esperats; els 21 de `test_cadastre_progressive` només fallen amb el Cadastre caigut).

Les 3 C de `fig_tall` que queden són estètiques i es queden (marge blanc de l'Eva a Castellar i Rubí; «(msnm)» sencer
a Bell-lloc, registre #14). `foto_dpsh` 4 X = empats (pregunta 37). `fig_projecte` i `fig_geologic` = judici de l'Eva.

## 3. Regles interpretatives (no surten del codi)

- **Els 7 signats són situacions, no objectius.** Cap nom de projecte a cap skill (`grep -c -i 'bell-lloc\|linyola\|vilanova\|anciles\|alcoletge\|castellar\|rub[ií]' .claude/commands/g3dt-llegir-*.md` = 0). Una regla amb un sol cas a favor és una pregunta a l'Eva o una opció al wizard.
- **Passades del lector: una per canvi de mecanisme, mai «fins que surti bé».** Avui: 3 passades de fotos (criteri de procedència → pel que s'hi veu → aparellament girat), cadascuna justificada; les runs `lector-fotos-altres`/`-b`/`-c` en són l'evidència. El lector resol els empats a l'atzar entre passades (materials de Rubí M → X → M): una pista determinista (l'annex girat) val més que repetir.
- **Un criteri per al lector ha de ser pel que S'HI VEU.** «Captura de visor» no es veu (una captura de Street View sembla una foto); «vista del solar sí, mapa no» sí.
- **Abans de citar escalars, `curl` al Cadastre** (`ConsultaMunicipio`): en avaria respon «problemas tecnicos» i mou `adjacent_intro` i 21 tests. Memòria `feedback_sweep_dns_contamination`.
- **Estètic = sempre igual.** Si una diferència amb l'Eva no té contingut ni regla (marge blanc), no es toca; si en té (llegenda dins el retall), és un defecte.
- El % de M341 és in-sample N=7; els 5 mm i 40 mm del retall del tall són distàncies de la plantilla de G3, no lleis.

## 4. Invariants que el treball d'avui necessita (no desfer)

- `automation/imatges/retall.py` `_ink_rects`: un traç del FreeHand amb tots els items `re` són tants objectes com rectangles (la caixa pot abastar mig full sense tinta). `GAP_MM = 5` absolut; `PAD_UP_MIN_MM = 40`. Cau `tall_crop2` a `image_manager.py` (els `tall_crop_*` antics de QUALSEVOL cau, la de l'Eva inclosa, no valen).
- `automation/imatges/lector_fotos.py`: `annex_images` guarda `phashes` per rotació 0/90/180/270 (l'Eva incrusta la foto vertical de l'SPT girada; 2 de 31 als 7); `list_eva_pngs` + `kind: eva_png`; dedupe md5 + phash ≤ 2 només foto ↔ PNG; `validate_alternatives`. `lector_figures.py` importa `EVA_PNG_DIRS` d'aquí.
- `web/api.py`: `list_alternatives` / `choose_alternative` (font PER RANURA via `_lector_selection`; `placed` i `cleared` a la resposta; `_entry_ok` no accepta cap camí fora del projecte o de la cau); `_figures_from_selection` (la selecció MANA també quan diu «cap»); `_project_cache_keys` (la cau d'imatges és GLOBAL: sense el filtre per hash/UTM el calaix ensenyava figures d'un altre projecte); `list_photos` amb `find_photos_dir` (`FOTOGRAFIA` singular).
- `templates/validation/review.html`: `#altZone` és filla directa de `<body>` (dins `#dataContent`, `display:none`, un `position:fixed` amida 0 × 0); s'obre amb `showSlotAlternatives` (NO `showAlternatives`: ja existeix per al «+N» dels camps de text) i es tanca amb `hideAltZone`; `imagesReadyFor` es posa a `onProjectChange` (triar el projecte = llançar el pipeline) i governa la pestanya «Imatges» i la secció «Imatges de l'informe» del Wizard; `loadPhotos` fa `await loadAlternatives()` (sense l'await el formulari es pintava amb dades antigues); `#tab-photos` ja NO és a la regla CSS de producció v1 que amaga pestanyes; `finishStepper` respecta `step-vision` actiu i `markVisionDone` tanca «Llest» des del sondeig.
- Les set correccions del Josep (DECISION-LOG (4) «Correcció»): res abans de llançar el pipeline; clic, no hover; aspa; pestanya visible; secció al Wizard; font per ranura; figures del projecte per ordre amb avís. Cap panell flotant que aparegui sol.

## 5. Procediments

```bash
R=/home/josep/projects/claudecode-job/clients/g3dt-prod; cd "$R"; git branch --show-current; git status --short; git log --oneline -5

# servidor del wizard per al Josep (SENSE G3DT_PROJECTS_DIR: el .env resol el flux de xarxa a ~/g3dt-prod-workspace)
(PYTHONPATH=$PWD setsid nohup .venv/bin/python -m web > /tmp/web.log 2>&1 < /dev/null &)   # http://localhost:8765/review.html
pgrep -f "[.]venv/bin/python -m web$" | xargs kill                                          # aturar (mai `pkill -f "python -m web"`: es mata a si mateix)

# lectors sobre un projecte concret (la còpia que fa servir el wizard és la de ~/g3dt-prod-workspace/<P>)
PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache .venv/bin/python -c "
from pathlib import Path; from automation.imatges import lector_fotos as LF, lector_figures as LG
p=Path('/home/josep/g3dt-prod-workspace/4001612 BELL-LLOC'); print(LF.run(p, exclude_slug='bell-lloc', has_sondeig=True)['selection']); print(LG.run(p, exclude_slug='bell-lloc')['selection'])"

# corpus (leave-one-out) i mesura: com al handoff 1430 §5; referència ara 2026-09-09-m341-nit
PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache .venv/bin/python docs/wizard-headless/mesures/mesura_341.py 2026-09-<dd>-m341-<motiu>
M=docs/wizard-headless/mesures/runs; A=2026-09-09-m341-nit; B=2026-09-<dd>-m341-<motiu>
for s in castellar rubi bell-lloc linyola alcoletge vilanova anciles; do diff <(grep '^- ' $M/$A/$s/viaA/_compare_341.txt | sed 's/ gen=.*//') <(grep '^- ' $M/$B/$s/viaA/_compare_341.txt | sed 's/ gen=.*//') | grep '^[<>]' | sed "s/^/$s: /"; done
diff <(sed -n '2,28p' $M/$A/_AGREGAT-341.md) <(sed -n '2,28p' $M/$B/_AGREGAT-341.md)
diff <(sed -n '/^## Imatges (viaA)/,$p' $M/$A/_AGREGAT-341.md) <(sed -n '/^## Imatges (viaA)/,$p' $M/$B/_AGREGAT-341.md)

# suite (10 min de timeout; ~4 min); esborra docs/diagnostics/ai_pipeline_demo-project_<data>.md abans de git add
PYTHONPATH=$PWD .venv/bin/python -m pytest tests -q --no-header -p no:cacheprovider > /tmp/suite.txt 2>&1
diff <(grep '^FAILED' /tmp/suite.txt | sed 's/ - .*//' | sort) <(grep -v '^#' docs/wizard-headless/mesures/suite-vermells-esperats.txt | sort)

# l'API d'alternatives, a mà
curl -s "http://localhost:8765/api/alternatives/4001612%20BELL-LLOC" | python3 -c "import json,sys; d=json.load(sys.stdin); print({k:(v['source'],len(v['alternatives'])) for k,v in d['slots'].items()})"
```

Caus: imatges `/home/josep/g3dt-prod-cache/images/` (`tall_crop2_*`, `figsel_*` amb tag `alt`/`assaigs`/`projecte1`/`situacio1`…);
lector de fotos `…/lector-fotos/` (FH11 → PDF). Projectes: corpus `reference-material/<P>` (4) i `~/g3dt-e2e/projectes/<P>` (3);
el wizard de xarxa treballa a `~/g3dt-prod-workspace/<P>` (sincronitzat de `/mnt/c/claude/g3dt/projectes`; `validation/` no es toca).
Tulipa (`~/g3dt-e2e/projectes/3001706…`) és un projecte de proves amb dues cases: el «Començar» el rebutja i el Josep no el té a Windows.

## 6. Seqüència d'obertura suggerida

1. `git branch --show-current` (ha de ser `experiment/nivell-a-2026-08`), `git status --short` (net), `git log --oneline -6`.
2. Llegir «Tancament» de la sessió del 09 i STATUS: confirmar que la referència és `2026-09-09-m341-nit` i que la suite era la esperada.
3. `curl` al Cadastre abans de qualsevol mesura d'escalars.
4. Si el Josep vol seguir amb el wizard: engegar el servidor (§5, sense `G3DT_PROJECTS_DIR`) i provar amb Bell-lloc (té alternatives reals a 6 ranures). Els 7 del corpus NO tenen `alternatives` a les seleccions (no s'ha repetit cap passada): a la finestra hi surt l'actual i «Cap alternativa del lector».
5. Si toca la passada dels lectors al corpus amb `alternatives`: és una passada nova (14 crides, ~10 min, ~4 $) que pot moure tries per variància; només amb el Josep, i mesurar després contra `-nit` amb els tres `diff`.
6. Preguntes a l'Eva (30-38, 19a, 23, 28, 29) amb el Josep: moltes discrepàncies restants són judici seu.

## 7. Què NO fer

- Cap nom de projecte ni excepció d'un sol cas a cap skill. Cap «repetir el lector fins que surti bé».
- No tocar `detect_section_region` sense baseline i els tres `diff`; no dibuixar punts; no tocar el mapa ICGC ni `geocode_coordinates.py`.
- No engegar el servidor de proves amb `G3DT_PROJECTS_DIR` si el Josep hi ha d'entrar pel flux de xarxa: l'API resoldria els projectes a un altre directori (avui ha passat).
- No afegir una funció global a `review.html` sense `grep "function <nom>("` (9.000 línies; `showAlternatives` ja existia).
- No fer aparèixer cap panell sol, ni mostrar res «de memòria» abans de llançar el pipeline (regles del Josep).
- No enviar cap pregunta a l'Eva sense el Josep. No proposar pull/merge a l'Eva.
- Captures de pantalla amb el Playwright MCP: el zoom del navegador s'espatlla en redimensionar (DPR 0,25-0,75) i les captures surten desquadrades; per ensenyar-ho al Josep, en viu.

## 8. Tasques obertes

- Passada dels lectors amb `alternatives` als 7 del corpus (quan toqui, no abans) → PENDENTS §3 #7.
- «Tornar a la tria del lector» a la finestra (restaurar `_lector_selection`) → §3 #8; `select_photos_ai` que pot reescriure la selecció del lector si tots els forats són `null` → §3 #9.
- Miniatura de la composició automàtica de situació a la finestra; «Restablir selecció IA» esborra `photo_selection.json` sencer.
- Acció 2 de l'anàlisi (una foto de materials per punt: pregunta 33), 5 (workflow `ALTRES` amb l'Eva), 7-10.
- Bloc 5 del PLA (castellà) i els pendents de plantilla (PENDENTS §3 #1, #4, #6).

## 9. Guanys que no es veuen als números

- El wizard ja té la tria d'imatges: secció «Imatges de l'informe» al formulari + pestanya «Imatges» (abans amagada per producció v1: l'Eva no hi hauria arribat mai) + finestra flotant amb les alternatives i la raó del lector. És la primera vegada que l'Eva pot triar entre coses vàlides sense buscar fitxers.
- Tres defectes de producció que cap mesura veia: el calaix ensenyava figures d'un altre projecte (cau global), `FOTOGRAFIA` en singular no llistava fotos, i «Llest» s'encenia amb la visió en marxa.
- L'aparellament amb l'annex invariant a la rotació treu una font de variància del lector (l'empat de materials).
