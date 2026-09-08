# Imatges de l'informe: tot el que queda pendent

**Escrit:** 2026-09-07 (nit), a petició del Josep, en acabar la peça 3 del pas 3.
**Actualitzat:** 2026-09-08, en acabar les peces **4**, **6** i **5** i el pendent 2 (DECISION-LOG 2026-09-08, (2),
(3) i (4)). **Només queda la peça 7.**
**Estat de partida:** run de referència `2026-09-08-m341-peca5`. **31 M · 4 C · 12 X · 9 ND → 74 %** de les 56 figures
i fotos que l'Eva posa als 7 informes signats. Font de la veritat: `docs/imatges/veritat/<slug>/index.json` (pas 1).
**Com es mesura:** `docs/wizard-headless/mesures/imatges_font.py` dins M341 (peça 0): M = la mateixa imatge (phash ≤ 10),
C = la mateixa font amb un altre retall, X = una altra font, ND = no posem res.

## 0. Descobriments que valen per a les peces que queden

Recollits el 2026-09-08 en fer les peces 4 i 6. **Tots són mesurats**, no vistos a ull.

1. **Els rols de FIGURA de SmartScan no són de fiar.** Sis casos verificats: `figure_correlation` → un dibuix diferent
   (Rubí), `figure_geological_map` → `M1.png` (Castellar) i una imatge minada d'un correu (Linyola), `situation_plan`
   → el PDF de l'arrel en 4 de 7, `architect_plan` sense rol a Castellar i Vilanova, `photo_site_overview` → una
   màquina (Castellar). **Una regla determinista pel nom o per l'estructura del fitxer ha guanyat el rol 3 de 3
   vegades.** Abans de deixar que un rol mani sobre un forat d'imatge, mesura'l contra la veritat; si és l'única font,
   posa'l d'últim recurs. *(Val per a `figure_situation_map` a la peça 5: a Rubí apunta a `F1 UBI.png`, que **sí** és
   la figura del signat, però no s'hi arriba perquè `fig_cadastre_image` s'omple abans.)*
2. **Els fulls d'annex de l'Eva són A3 VERTICAL girats 270°.** `get_images`, `get_drawings` i `get_text` donen
   coordenades **sense girar**; `page.rect` les dona girades. Fes la geometria amb `page.mediabox` i passa el
   rectangle final per `page.rotation_matrix`. Els `tall.pdf` NO van girats (per això la peça 3 no ho notava).
3. **El `pl situ.pdf` de l'arrel no serveix per retallar-ne res**: és l'export «imprimible» del FreeHand amb el raster
   tallat en centenars de tires (Vilanova: 1.119 imatges, la més gran de 739×51). El de `PDF/ANNEXES/` porta cada
   imatge sencera. Filtra per àrea (≥ 15 % de la pàgina) i el descartaràs sol.
4. **Els PNG d'`ALTRES` no tenen marge blanc** (2-6 %) i **retallar-los empitjora**: `m7.png`, `F1 UBI.png` i
   `F1 SIT.png` són MATCH amb **phash 0 crus** i phash 2 retallats. No escriguis cap retall de blanc.
5. **La recepta ICGC aprovada per l'Eva no es toca, i moure-la no guanyaria res:** cap buffer de 150 a 1.000 m acosta
   Linyola, Bell-lloc ni Alcoletge al que ella va enganxar (NCC 0,31-0,52 a tot arreu). La diferència **no és el
   zoom** sinó la vista del visor. Pregunta 34.
6. **Una ranura de plantilla només pot servir UNA figura de l'Eva.** A Vilanova el mateix dibuix li fa de Figura 2
   (emplaçament, retall ample) i de Figura 3 (assaigs, retall estret); amb un sol forat només se n'omple una. És el
   motiu de fons de la peça 7.

## 1. On som, ranura per ranura

| ranura de l'Eva | M | C | X | ND | estat |
|---|--:|--:|--:|--:|---|
| `foto_materials` | 7 | 0 | 0 | 2 | ✅ peça 2 |
| `fig_tall` | 3 | 4 | 0 | 0 | ✅ peça 3 + precedència de rol (2026-09-08) |
| `foto_sondeig` | 2 | 0 | 1 | 0 | ✅ peça 2 (1 empat) |
| `foto_vista` | 2 | 0 | 1 | 1 | ✅ peça 2 (1 empat) |
| `foto_dpsh` | 3 | 0 | 4 | 0 | ✅ peça 2 (4 empats) |
| `fig_assaigs` | 4 | 0 | 0 | 2 | ✅ peça 4 (2 ND: la ranura única se n'ha anat a `fig_projecte`) |
| `fig_projecte` | 2 | 0 | 1 | 2 | ⏳ **peça 7** (peu i partició de la ranura) |
| `fig_geologic` | 3 | 0 | 3 | 1 | ✅ peça 6 (3 X = la vista ICGC de l'Eva, pregunta 34; 1 ND = Anciles, Aragó) |
| `fig_situacio` | 5 | 0 | 2 | 1 | ✅ peça 5 (2 X = Linyola i Bell-lloc; 1 ND = la 2a de Bell-lloc, ranura única) |

**Només queda la peça 7**: el peu de cada figura, la partició de les ranures i la numeració variable. Les fotos, el
dibuix amb punts, el mapa geològic i la situació ja estan.

## 2. Les peces que queden

### Peça 4 — Figura dels assaigs (el dibuix amb els punts) — ✅ FETA (2026-09-08)

- **Què fa l'Eva:** 6 dels 7 signats porten al capítol 2.2 el plànol de l'arquitecte (Linyola, Alcoletge, Vilanova,
  Anciles) o l'ortofoto ampliada (Castellar, Rubí) **amb els punts d'assaig que ella hi dibuixa**. Bell-lloc no en
  porta cap.
- **Què s'ha fet:** `detect_plan_region` / `crop_plan` (`automation/imatges/retall.py`) retallen el dibuix del seu full
  «plànol de situació»: nucli = la imatge incrustada més gran, i creixement fins al blanc per agafar-hi les cotes i les
  etiquetes «P-n» que ella dibuixa a fora. `_situation_plan_candidates` tria el full (carpeta d'annexos abans que
  l'arrel: el `pl situ.pdf` de l'arrel porta el raster en tires i no té nucli).
- **Resultat:** `fig_assaigs` 0 % → **100 %** (4 M) i `fig_projecte` 0 % → **67 %** (2 M, Bell-lloc i Vilanova, que
  fan servir el mateix dibuix per a la figura del projecte). Total imatges 47 % → **58 %**. Cap altra cel·la moguda.
- **Què queda d'aquesta ranura** (tot a la peça 7): el **peu** encara diu «Ubicació de l'habitatge a l'interior de la
  parcel·la. Font: Projecte» (correcte a Bell-lloc i Vilanova, no als quatre d'assaigs; i a Castellar i Rubí la imatge
  és una ortofoto, no «Projecte»); **Linyola**, on l'Eva va fer servir la planta del projecte i no el seu annex; i
  **Vilanova**, on amb una sola ranura només se'n pot omplir una de les dues.
- **Obert amb l'Eva:** pregunta 31 (vol sempre els punts? quin fons prefereix quan té orto i planta?) — ja no bloqueja.

### Peça 5 — Figura de situació — ✅ FETA (2026-09-08)

- **Què fa l'Eva:** 7/7, sempre dos mapes de costat (topogràfic ICGC del municipi + ortofoto o topogràfic ampliat) amb
  la zona en taronja. Excepcions: Bell-lloc (dos retalls del plànol de l'arquitecte, «Font: Projecte») i Anciles (Sede
  del Catastro, perquè és Aragó).
- **Què s'ha fet:** els dos mapes són els que ja hi ha a dalt del seu full «plànol de situació», sobre el dibuix de la
  peça 4. `detect_situation_maps` / `compose_situation` els retallen amb el mateix creixement fins al blanc i els posen
  de costat a la mateixa alçada. Si SmartScan té `figure_situation_map` i la imatge és **ampla** (relació ≥ 1,5), es fa
  servir la seva sencera: encerta 2 de 2 amb phash 0. `_render_situation_plan_left` (el retall del 38 % esquerre) ha
  desaparegut, amb un test que li barra la tornada.
- **L'ordre dels dos mapes es decideix ABANS de créixer.** Amb els rectangles ja crescuts, Castellar cau de phash 10 a
  36 i Rubí de 6 a 32: el creixement d'un mapa li pot moure la vora per davant de l'altre i els inverteix.
- **Resultat:** `fig_situacio` 0 % → **71 %** (5 M). Total imatges 64 % → **74 %**. Castellar 86 %, Rubí 83 %,
  Vilanova 86 %, Anciles 83 %, Alcoletge 67 %. Cap altra cel·la moguda.
- **Què queda:** **Linyola** (phash 18: la mateixa figura amb un pèl més de marge vertical; provat, cap marge fix
  serveix per als tres alhora) i **Bell-lloc**, que hi posa dos retalls del plànol de l'arquitecte i **dues** figures
  on la plantilla només té una ranura → peça 7.

### Peça 6 — Mapa geològic — ✅ FETA (2026-09-08)

- **Què fa l'Eva:** 7/7, retall del mapa geològic ICGC 1:50.000 (1:25.000 a Castellar); amb llegenda composta a
  Castellar, Rubí i Vilanova (PNG `*MGEOL*`), sense llegenda i amb punt vermell a Linyola, Bell-lloc i Alcoletge;
  IGME 1:1.000.000 a Anciles (Aragó).
- **Què s'ha fet:** `_find_composed_geological_map()` — un fitxer d'imatge amb «geol» al nom — va **abans** de la
  recepta ICGC. Als 7 projectes dona exactament un candidat als tres que en tenen i cap als altres quatre. El rol
  `figure_geological_map` de SmartScan **no** serveix: encerta a Rubí i Vilanova, però a Castellar apunta a `M1.png` i
  a Linyola a una imatge extreta d'un correu.
- **Resultat:** `fig_geologic` 0 % → **50 %** (3 M, phash 0). Total imatges 60 % → **64 %**. Rubí i Vilanova es queden
  sense cap forat d'imatge pendent. Cap altra cel·la moguda.
- **Què queda:** **Linyola, Bell-lloc i Alcoletge en X** — tenim el tipus de figura i les coordenades correctes, però
  no la vista del visor que ella fa servir. Mesurat: **cap buffer de 150 a 1.000 m els acosta** (NCC 0,31-0,52 a tot
  arreu), o sigui que la diferència **no és el zoom** i no hi ha res a provar per codi. Ho desbloqueja la **pregunta
  34** a l'Eva. **Anciles** és ND honest: Aragó (IGME), i sense UTM.
- **No tocar:** els paràmetres de `get_geological_map_with_terrain` (base topogràfica + `unitats-geologiques-50000` al
  0,65 amb `alpha_composite`, buffer 700 m, 800×600, EPSG:25831, punt vermell r=10) — és la imatge que l'Eva va aprovar.

### Peça 7 — Figures del projecte, peu i bloc de figures variable — *M*

- **Què fa l'Eva:** 0-2 figures «Font: Projecte» tretes del projecte de l'arquitecte (secció a Linyola, emplaçament
  sense punts a Bell-lloc i Vilanova, topogràfic i tipologies a Anciles), sempre **retallades al dibuix**, sense
  caixetí. No hi ha regla fixa: depèn del que l'arquitecte enviï.
- **Què cal fer:** que Claude triï la pàgina (és el cas més clar de «mira i tria») i la retalli; i **que la plantilla
  imprimeixi el nombre de figures que toca** (situació 1-2 + assaigs 0-1 + projecte 0-2 + geològic + tall).
- **Hereta de la peça 4** (2026-09-08): partir `fig_main_plan_image` en dues ranures amb **peus propis** — avui la
  ranura única imprimeix el peu de Bell-lloc sobre la figura d'assaigs de quatre projectes — i triar, a Linyola, entre
  la planta del projecte (la que l'Eva va fer servir) i el seu propi annex.
- **Per què importa més del que sembla:** és **l'única peça que mou el grup `fix` de la numeració** (avui 74 M · 25 X;
  10 d'aquelles X són «nombre de figures del projecte»). Les peces 1-6 no el mouen.
- **Obert amb l'Eva:** pregunta 32 (quan hi afegeix figures del projecte).

## 3. Pendents que no són cap de les quatre peces

| # | Pendent | Detall | Esforç |
|---|---|---|---|
| 1 | **Foto de materials per punt** | L'Eva en posa una per sondeig/punt quan n'hi ha diversos (Vilanova P-3 i P-1, Anciles S-1 i S-2). El lector ja escriu `materials_per_punt` a `photo_selection.json`, però **la plantilla no ho imprimeix**: 2 forats ND. | S |
| 2 | ~~**Retall de PNG**~~ | ❌ **TANCAT 2026-09-08: no calia** (DECISION-LOG 2026-09-08 (2)). Mesurat: els PNG d'`ALTRES` tenen 2-6 % de marge i el retall no canvia cap veredicte; `m7.png`, `F1 UBI.png` i `F1 SIT.png` ja són MATCH **phash 0 crus** (retallats, ph 2: pitjor). I el tall de Rubí no era un marge — `F5 TALL.png` és un **dibuix diferent** del signat; la causa era que el rol `figure_correlation` passava davant del `tall.pdf`. Arreglat: `fig_tall` 86 → **100 %** (0 X). | — |
| 3 | **Descripció textual dels exemplars** | La llibreria `docs/imatges/veritat/` té les imatges i el peu, però no la descripció per exemplar que el pas 2 va decidir (què s'hi veu, com està compost). El lector de fotos ja funciona sense, però les figures compostes la necessitaran. | S |
| 4 | **Text fix de Rubí a la plantilla** | Dins el bucle de nivells s'imprimeix a TOTS els projectes: «Aquest materials s'associa als materials de la unitat **NMgo**, amb un tram superficial alterat…». És la mateixa família de risc que el pastís de granulometria (ja tret): text d'un projecte imprès a tots. No és una imatge, però va sortir mirant-les. | S |
| 5 | **Barra d'escala al tall** | L'Eva la inclou a 2 dels 7 signats i el nostre retall la inclou sempre. Diferència petita, no s'hi toca fins que hi hagi criteri. | — |
| 6 | **`fig_cadastre_num` a la veritat** | A Castellar i Rubí l'extractor de numeració no aparella el peu de la situació (ratio < 0,5 per la cua entre parèntesis amb la font). Límit de l'extractor del bloc 4, no de les imatges. | S |

## 4. Bloqueigs de fons

1. **UTM a la via A per a Rubí, Vilanova i Anciles.** Sense coordenades no es poden baixar les capes ICGC: avui són 3
   dels 5 forats «pendents» (geològic) i limiten l'opció B de la situació. És un problema de lectura, no d'imatges.
2. **Rols de SmartScan.** ~~A Rubí el rol `figure_correlation` apunta a un PNG que evita el retall de la peça 3~~
   (arreglat el 2026-09-08: el rol es prova al final, no al principi). Queda el mateix patró a la situació: a Rubí
   `figure_situation_map` apunta a `F1 UBI.png`, que ÉS la figura del signat, i no s'hi arriba. `fig_main_plan` ja no
   depèn de cap rol des de la peça 4. Els rols manen sobre els PDF i de vegades
   s'equivoquen (a Castellar, `photo_site_overview` és una màquina).
3. **Claude Code a l'ordinador de l'Eva.** El lector de fotos (peça 2) i el que triï figures (peces 4 i 7) el
   necessiten. Sense ell, el sistema cau a la cau antiga i als patrons de nom. És la decisió «via A» del 2026-08-23 i
   encara no s'ha instal·lat.
4. **`soffice` a producció.** Els annexos FreeHand (`.FH11`) es converteixen amb LibreOffice. Les peces 4 i 5 en
   depenen quan no hi ha PDF.

## 5. Preguntes obertes a l'Eva (registre `docs/PREGUNTES-EVA-PENDENTS.md`)

| # | Tema | Què desbloqueja |
|---|---|---|
| 30 | Composició de la figura de situació | peça 5 |
| 31 | Punts a la figura d'assaigs | peça 4 |
| 32 | Quan posa figures del projecte | peça 7 |
| 33 | Una foto de materials o una per punt | pendent 1 |
| 34 | Llegenda al mapa geològic; **quina vista del visor ICGC fa servir**; font a l'Aragó | els 3 X que queden de `fig_geologic` (Linyola, Bell-lloc, Alcoletge) |
| 36 | Deixa sempre els PNG a `ANNEXES/ALTRES`? | peces 4, 5 i 6 (canvia la primera opció de totes tres) |
| 37 | Quina foto de la DPSH quan n'hi ha una per punt | 4 X de `foto_dpsh` |
| 38 | Quina vista general, i quantes | 1 X de `foto_vista` |
| 19a | Vistes generals (ampliada amb l'evidència) | `foto_vista` |
| ~~39~~ | ~~Objecte de color a les fotos de màquina~~ | **TANCADA**: caixa blava de mocadors = sondeig |

## 6. Ordre recomanat

1. ~~**Peça 4** (assaigs)~~ — ✅ feta el 2026-09-08.
2. ~~**Pendent 2** (retall de PNG)~~ — ❌ tancat el 2026-09-08: no calia (vegeu §3).
3. ~~**Peça 6** (geològic)~~ — ✅ feta el 2026-09-08 (3 M; els 3 restants depenen de la pregunta 34).
4. ~~**Peça 5** (situació)~~ — ✅ feta el 2026-09-08 (5 M de 8).
5. **Peça 7** (projecte + peu + bloc variable): **l'única que queda**, i l'única que mou la numeració.
6. **Pendent 1** (materials per punt) i **pendent 4** (text fix de Rubí), quan toqui plantilla.

Cada peça: baseline amb el codi quiet, canvi, mesura contra `2026-09-08-m341-peca6`, entrada al DECISION-LOG i, si
perd alguna cel·la, al `REGISTRE-PERDUES-MESURA.md`.
