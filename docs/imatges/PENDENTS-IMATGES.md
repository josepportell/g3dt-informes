# Imatges de l'informe: tot el que queda pendent

**Escrit:** 2026-09-07 (nit), a petició del Josep, en acabar la peça 3 del pas 3.
**Actualitzat:** 2026-09-08, en acabar la **peça 4** (DECISION-LOG 2026-09-08).
**Estat de partida:** run de referència `2026-09-08-m341-peca4`. **23 M · 3 C · 19 X · 11 ND → 58 %** de les 56 figures
i fotos que l'Eva posa als 7 informes signats. Font de la veritat: `docs/imatges/veritat/<slug>/index.json` (pas 1).
**Com es mesura:** `docs/wizard-headless/mesures/imatges_font.py` dins M341 (peça 0): M = la mateixa imatge (phash ≤ 10),
C = la mateixa font amb un altre retall, X = una altra font, ND = no posem res.

## 1. On som, ranura per ranura

| ranura de l'Eva | M | C | X | ND | estat |
|---|--:|--:|--:|--:|---|
| `foto_materials` | 7 | 0 | 0 | 2 | ✅ peça 2 |
| `fig_tall` | 3 | 3 | 1 | 0 | ✅ peça 3 |
| `foto_sondeig` | 2 | 0 | 1 | 0 | ✅ peça 2 (1 empat) |
| `foto_vista` | 2 | 0 | 1 | 1 | ✅ peça 2 (1 empat) |
| `foto_dpsh` | 3 | 0 | 4 | 0 | ✅ peça 2 (4 empats) |
| `fig_assaigs` | 4 | 0 | 0 | 2 | ✅ peça 4 (2 ND: la ranura única se n'ha anat a `fig_projecte`) |
| `fig_projecte` | 2 | 0 | 1 | 2 | ⏳ **peça 7** (peu i partició de la ranura) |
| `fig_situacio` | 0 | 0 | 7 | 1 | ⏳ **peça 5** |
| `fig_geologic` | 0 | 0 | 4 | 3 | ⏳ **peça 6** |

Les tres ranures pendents són **totes de figures compostes**; les fotos i el dibuix amb punts ja estan.

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

### Peça 5 — Figura de situació — *M*

- **Què fa l'Eva:** 7/7, sempre dos mapes costat a costat (topogràfic ICGC del municipi + ortofoto o topogràfic
  ampliat) amb la zona en taronja. Excepcions: Bell-lloc (dos insets del plànol de l'arquitecte, «Font: Projecte») i
  Anciles (Sede del Catastro, perquè és Aragó).
- **Ordre de fonts decidit (pas 2, D1):** PNG d'`ALTRES` si hi és (3/7 idèntic: `m7.png`, `F1 UBI.png`, `F1 SIT.png`) →
  retallar els dos mapes de l'annex de situació i **recompondre'ls en horitzontal** → insets del plànol → ICGC
  topogràfic + ortofoto per UTM amb rectangle taronja.
- **Què cal fer a més:** **retallar un PNG** (bbox de píxels no blancs) — la mateixa eina arregla el tall de Rubí, que
  avui agafa `F5 TALL.png` sense retallar; i **retirar `_render_situation_plan_left`** (el retall del 38 % esquerre,
  que no coincideix amb cap signat).
- **Guany esperat:** 8 forats (0/8). Bloquejat en part per les UTM (§4).
- **Obert amb l'Eva:** preguntes 30 (composició per defecte) i 36 (deixa sempre els PNG a `ALTRES`?).

### Peça 6 — Mapa geològic — *S*

- **Què fa l'Eva:** 7/7, retall del mapa geològic ICGC 1:50.000 (1:25.000 a Castellar); amb llegenda composta a
  Castellar, Rubí i Vilanova (PNG `*MGEOL*`), sense llegenda i amb punt vermell a Linyola, Bell-lloc i Alcoletge;
  IGME 1:1.000.000 a Anciles (Aragó).
- **Ordre decidit (pas 2, D8):** PNG `*MGEOL*` si hi és → ICGC WMS per UTM (ja el sabem baixar; és el mateix tipus de
  figura a 3/7) → fora de Catalunya, IGME (comprovar si té WMS; si no, «cap font», mai inventar).
- **Guany esperat:** 7 forats, dels quals 3 avui són «pendent» per manca d'UTM.
- **Obert amb l'Eva:** pregunta 34 (llegenda sí o no; font a l'Aragó).

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
| 2 | **Retall de PNG** | Bbox de píxels no blancs. El necessiten la peça 5 i el tall de Rubí (`F5 TALL.png`, avui X). | S |
| 3 | **Descripció textual dels exemplars** | La llibreria `docs/imatges/veritat/` té les imatges i el peu, però no la descripció per exemplar que el pas 2 va decidir (què s'hi veu, com està compost). El lector de fotos ja funciona sense, però les figures compostes la necessitaran. | S |
| 4 | **Text fix de Rubí a la plantilla** | Dins el bucle de nivells s'imprimeix a TOTS els projectes: «Aquest materials s'associa als materials de la unitat **NMgo**, amb un tram superficial alterat…». És la mateixa família de risc que el pastís de granulometria (ja tret): text d'un projecte imprès a tots. No és una imatge, però va sortir mirant-les. | S |
| 5 | **Barra d'escala al tall** | L'Eva la inclou a 2 dels 7 signats i el nostre retall la inclou sempre. Diferència petita, no s'hi toca fins que hi hagi criteri. | — |
| 6 | **`fig_cadastre_num` a la veritat** | A Castellar i Rubí l'extractor de numeració no aparella el peu de la situació (ratio < 0,5 per la cua entre parèntesis amb la font). Límit de l'extractor del bloc 4, no de les imatges. | S |

## 4. Bloqueigs de fons

1. **UTM a la via A per a Rubí, Vilanova i Anciles.** Sense coordenades no es poden baixar les capes ICGC: avui són 3
   dels 5 forats «pendents» (geològic) i limiten l'opció B de la situació. És un problema de lectura, no d'imatges.
2. **Rols de SmartScan.** `fig_main_plan` no té rol a Castellar ni a Vilanova (2 forats pendents), i a Rubí el rol
   `figure_correlation` apunta a un PNG que evita el retall de la peça 3. Els rols manen sobre els PDF i de vegades
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
| 34 | Llegenda al mapa geològic; font a l'Aragó | peça 6 |
| 36 | Deixa sempre els PNG a `ANNEXES/ALTRES`? | peces 4, 5 i 6 (canvia la primera opció de totes tres) |
| 37 | Quina foto de la DPSH quan n'hi ha una per punt | 4 X de `foto_dpsh` |
| 38 | Quina vista general, i quantes | 1 X de `foto_vista` |
| 19a | Vistes generals (ampliada amb l'evidència) | `foto_vista` |
| ~~39~~ | ~~Objecte de color a les fotos de màquina~~ | **TANCADA**: caixa blava de mocadors = sondeig |

## 6. Ordre recomanat

1. ~~**Peça 4** (assaigs)~~ — ✅ feta el 2026-09-08.
2. **Pendent 2** (retall de PNG): és petit i el necessiten la 5 i el tall de Rubí.
3. **Peça 6** (geològic): 3 forats es resolen amb el PNG sense tocar les UTM.
4. **Peça 5** (situació): 8 forats, la més llarga; depèn del retall de PNG i, en part, de les UTM.
5. **Peça 7** (projecte + peu + bloc variable): l'única que mou la numeració.
6. **Pendent 1** (materials per punt) i **pendent 4** (text fix de Rubí), quan toqui plantilla.

Cada peça: baseline amb el codi quiet, canvi, mesura contra `2026-09-08-m341-peca4`, entrada al DECISION-LOG i, si
perd alguna cel·la, al `REGISTRE-PERDUES-MESURA.md`.
