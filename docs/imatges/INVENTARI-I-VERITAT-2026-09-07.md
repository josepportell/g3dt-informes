# Imatges de l'informe — inventari, veritat des dels signats i aparellament (pas 1)

**Data:** 2026-09-07 (tarda). **Branca:** `experiment/nivell-a-2026-08` (in-place a `g3dt-prod/`). **Cap canvi a `automation/` ni a la plantilla.**
**Handoff d'origen:** `docs/_FOR-NEW-YOU-20260907-1130.md` (pla en 3 passos; aquest document és el pas 1 sencer i la preparació del pas 2).
**Encàrrec del Josep (2026-09-07):** «revisar de quines imatges disposem a la documentació dels projectes. I mappejar-ho amb les que aniran a
l'informe (versus les que són auxiliars per redactar-lo, no per mostrar-les a l'informe). […] cadascuna pot requerir un anàlisi amb cura.»

Dues indicacions del Josep durant el pas 1, que canvien el disseny (§8):
1. *«l'eix de la implementació […] és que aquest pipeline el controla Claude Code. […] tú pots obrir-les, veure-les, i interpretar-les, i fer-ho
   tenint en compte les imatges que voldrem a l'informe. I alhora, fa uns dies que tenim lectura sobre fitxers amb extensió FH11.»*
2. *«guardem una "llibreria" d'imatges de referència de projectes antics […] amb les que puguis comparar a cada projecte nou, de la mateixa manera que
   un prompt amb exemples sempre és millor que un prompt sense exemples. No es podrien insertar mai les de referència a l'informe dels nous projectes.»*
   I el MCP plànols pot tenir ja part de la funcionalitat de retall de plànols, per si cal.

## 0. Resum en deu línies

1. **Els 7 signats porten les imatges** (`word/media/`, amb el peu que les segueix): 75 imatges, 63 de projecte. Veritat extreta a
   `docs/imatges/veritat/<projecte>/index.json` (repo) + fitxers a mida real a `~/g3dt-e2e/imatges/veritat/<projecte>/` (fora del repo, 2-7 MB per projecte).
2. **La plantilla `g3dt-jinja-template.docx` ÉS el signat de Rubí**: les 11 imatges que porta són les de Rubí. Només 3 es referencien (logo de capçalera, segell
   de G3, i el **gràfic de pastís de granulometria de Rubí** dins `{%p if show_granulometric %}`). Les altres 8 (8,9 MB) són pes mort a cada informe generat.
3. **El «473×210 sense peu»** que tanca tots els signats és el **segell de G3** (no és una figura). El «752×452» de la plantilla és el pastís de Rubí.
4. **Estructura de figures de l'Eva** abans de la cullera: `situació` (1 o 2 imatges) + `projecte` (0-2: perfil, topogràfic, tipologies, emplaçament) + `assaigs`
   (plànol o ortofoto **amb els punts**) → 2 / 2 / 3 / 3 / 2 / 3 / 4 figures. La plantilla en té 3 fixes (cadastre, aèria, plànol) i no coincideix amb cap dels 7.
5. **La memòria `report_figure_sources` («plànol SENSE punts», Eva 2026-03-14) descriu Bell-lloc i només Bell-lloc.** Als altres 6 signats la figura del plànol
   porta els punts d'assaig dibuixats per l'Eva (i Vilanova i Anciles porten TOTES DUES: emplaçament sense punts + assaigs amb punts).
6. **L'ortofoto no és mai una figura a part**: va dins la figura de situació (topo + orto costat a costat: Castellar, Rubí, Alcoletge, Anciles) o dins la
   figura d'assaigs (orto amb punts: Castellar, Rubí). La ranura `fig_aerea_image` de la plantilla no existeix als signats.
7. **Procedència**: a Castellar, Rubí i Vilanova l'Eva deixa les figures ja compostes a `ANNEXES/ALTRES|OTROS/*.png` (`F1 UBI`, `F2 UBI PUNTS`, `F4 MGEOL`,
   `m7`, `m8`, `m12 mgeol`…, mides idèntiques a les del signat) i les peces (captures ICGC `M1…`). A la resta, les figures són **retalls** dels PDF del
   projecte (insets de l'`A.01.pdf` a Bell-lloc, planta i secció del projecte de l'arquitecte a Linyola, `IV_PLANOS.pdf` a Anciles) o **composicions pròpies**
   que només viuen dins els annexos FreeHand (`.FH11`, ara llegibles).
8. **Fonts externes** que NO són al projecte: captures ICGC (topo, orto, geològic), Google Earth (Rubí), Sede del Catastro (Anciles), IGME (Anciles), llibres.
9. **El que posem avui** (bloc 4b, per phash contra la veritat): fotos **idèntiques 12 de 23** (DPSH 4/7, sondeig 1/3, vistes 1/4, materials 6/9), 3 vàlides
   però diferents (DPSH Castellar i Linyola, materials Anciles), **4 errònies** (Bell-lloc vista 2 i sondeig = màquina DPSH; Alcoletge DPSH = full de camp;
   Anciles sondeig = caixa de testimonis), 6 que no triem (Google Earth, vistes, segones fotos de materials). Figures: **cap** de situació igual (0/7: retall
   vertical de l'annex vs composició), cap d'assaigs (0/6: mai dibuixem punts), plànol amb la mateixa base 2/5 (Linyola, Bell-lloc; Rubí foto d'un paper,
   Anciles portada), geològic mateix tipus 3/7 i 3 pendents, **tall 7/7 mateixa font i 0/7 mateix retall**. Detall per figura a §4.
10. **Pas 2**: 8 tipus de figura amb opcions A/B/C i preguntes a l'Eva (§7). **Pas 3** (disseny): Claude Code mira les imatges del projecte (fotos, PDFs,
    FH11) amb la llibreria d'exemplars i tria/retalla/compon; Python renderitza (§8).

## 1. Mètode

| Pas | Què | Eina | Sortida |
|---|---|---|---|
| Veritat | 7 signats (`RE.KNOWN_REPORTS`) → `.docx` (soffice, reaprofitats de la sessió del matí) → `document.xml` en ordre: `a:blip r:embed` / `v:imagedata r:id` → `word/media/*`; peu = següent paràgraf «Figura/Fotografia/Fotografía»; secció = darrera capçalera numerada; imatges sense peu abans d'una taula o capçalera es marquen «sense peu» | `truth_extract.py` (scratchpad) | `docs/imatges/veritat/<slug>/index.json` + `~/g3dt-e2e/imatges/veritat/<slug>/NN_<ranura>_<peu>.<ext>` |
| Estàtiques | phash ≤ 6 contra els media que la plantilla **referencia** (document + capçaleres). La cullera SPT NO és referenciada (la insereix el generador): es marca `fig_spt_cullera` i s'exclou de l'aparellament | idem | camp `static_of` |
| Ranura | classificador per paraules clau del peu (CA/ES) → `fig_situacio`, `fig_projecte`, `fig_assaigs`, `fig_geologic`, `fig_tall`, `foto_vista`, `foto_dpsh`, `foto_sondeig`, `foto_materials`, `fig_extra_*` | idem | camp `slot` |
| Inventari | tot fitxer d'imatge, PDF (pàgina a pàgina a 80 dpi, llevat informe/portada/pressupost/laboratori/GTL) i **FH11 → PDF** (soffice, 27 fitxers, 3-14 s cadascun) dels 7 projectes a `~/g3dt-e2e/projectes/`; rol de `file_mapping.json` quan n'hi ha (4 de 7) | `inventory.py` | 291 candidats renderitzats (53 · 31 · 38 · 38 · 23 · 35 · 73) |
| Aparellament | nivell 1: phash sencer (≤ 10 = mateixa imatge); nivell 2: correlació normalitzada (NCC) multiescala fina (sèrie geomètrica 0,12→1,0 + escala nativa 1:1), gris a 400 px, desenfocat σ 0,9, en les dues direccions (veritat dins candidat = retall; candidat dins veritat = peça d'una composició); pic ponderat per la seva singularitat (PSR) per descartar textures genèriques | `match.py` | `scratchpad/match/<slug>.json` (top 8 per figura) |
| Interpretació | **Claude mira** els fulls de contacte de veritat i de candidats (24 fulls) i les figures a mida real quan el detall decideix (punts d'assaig) | Read | §4 i `notes_visual.md` |
| Fulls | tres columnes: Eva · nosaltres (bloc 4b `viaA`) · 3 candidats amb hash | `build_sheets.py` | `docs/imatges/fulls/<slug>.jpg` |

**Calibratge de l'aparellament** (parelles conegudes de Castellar i Bell-lloc): idèntic (`m7.png` vs Fig 1) 1,00; retall real (Fig 2 dins l'annex de
situació) 0,90 amb PSR 21; tall (Fig 5 dins `tall.pdf`) 0,95/PSR 5; inset cadastral de Bell-lloc dins `A.01.pdf` 0,75/PSR 12; parelles no relacionades
0,34-0,47 (abans de la penalització PSR arribaven a 0,91 a escales petites). Llindars: **≥ 0,7 = retall/composició fort**, 0,5-0,7 = probable, < 0,5 = no trobat.
Limitació: la NCC tolera malament les figures **modificades** per l'Eva (capes taronges, llegendes): `M1.png` (topo) dins la Fig 1 de Castellar dona 0,56
amb PSR 32 (pic singularíssim però correlació mitjana). Per això la lectura visual mana sobre el número.

## 2. Estàtiques i plantilla (troballes col·laterals)

| Media de la plantilla | Què és | Referenciat? | Conseqüència |
|---|---|---|---|
| `image11.jpeg` 275×265 | logo (capçalera) | sí (`header2.xml`) | correcte |
| `image10.jpeg` 473×210 | **segell de G3** (Desenvolupament Territorial S.L., CIF, adreça) | sí (final del document) | correcte; als signats surt sense peu, no és figura |
| `image8.png` 752×452 | **gràfic de pastís de granulometria de RUBÍ** (graves 50,3 / sorres 31,5 / fins 18,2) | sí, dins `{%p if show_granulometric %}` amb peu «Gràfic 1. Distribució granulomètrica dels materials del {{ level.ordinal }} nivell.» | **risc de fabricació**: si `show_granulometric` s'activa, un altre projecte portaria la granulometria de Rubí. Al bloc 4b no s'activa. Cal treure'l o substituir-lo per una imatge generada de les dades del projecte |
| `image5.jpeg` 1552×641 | cullera SPT | no (la insereix el generador des de `templates/`) | correcte |
| `image1-4, 6, 7, 9` | Fig 1, Google Earth, Fig 2, foto DPSH, geològic, materials, tall **de Rubí** | no | 8,9 MB de pes mort a cada `.docx` generat (els generats pesen 8-13 MB) |

## 3. Els 7 signats: què hi ha i d'on surt

Taula per tipus (Claude mirant els fulls; nombre d'imatges per ranura i què són):

| tipus | Castellar | Rubí | Linyola | Bell-lloc | Alcoletge | Vilanova | Anciles |
|---|---|---|---|---|---|---|---|
| `fig_situacio` | 1: topo + orto ICGC costat a costat, zona en taronja | 1: topo + orto | 1: mapa del municipi + cadastral ampliat, línia vermella | **2 imatges**: cadastral + orto amb parcel·la vermella («Font: Projecte») | 1: topo + orto | 1: topo + topo ampliat | 1: topo + orto (Sede del Catastro) |
| `fig_projecte` (Font: Projecte) | 0 | 0 | 1: secció de l'habitatge | 1: planta d'emplaçament **sense punts** | 0 | 1: emplaçament de l'habitatge sense punts | 2: topogràfic de la parcel·la; plantes + tipologies |
| `fig_assaigs` (amb punts) | orto ampliada + parcel·la taronja + punts + llegenda | orto ampliada + punts | planta de l'arquitecte + punts | **cap** | planta + ampliació ratllada + punts | planta + punts + cotes | planta + punts (S vermell, P blau) + llegenda |
| `foto_vista` | 0 | 1: Google Earth (carrer) | 0 | 2: fotos de camp | 0 | 1: foto de camp de la parcel·la (retall) | 0 |
| `foto_dpsh` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `foto_sondeig` | 1 | — | — | 1 | — | — | 1 |
| `fig_geologic` | ICGC 1:25.000 amb llegenda | ICGC 1:50.000 amb llegenda | ICGC retall sense llegenda, punt vermell | ICGC retall, punt vermell | ICGC retall, «Zona d'estudi» taronja | ICGC amb llegenda | IGME 1:1.000.000 retall |
| `foto_materials` | 1: caixa de testimonis S-1 | 1: cullera SPT | 1: cullera SPT | 1: caixa | 1: cullera SPT | **2**: SPT P-3 i SPT P-1 (la 1a duplicada al docx) | **2**: caixa S-1, caixa S-2 |
| `fig_tall` | retall del tall (sense llegenda ni caixetí) | idem | idem, 2 seccions | idem | idem | idem | idem |
| extra | Fig 6 i 7: estabilitat de vessant (Hoek & Bray, del llibre) | pastís de granulometria | — | — | — | — | signatura manuscrita (693×535, «sense peu») |

Figures «del projecte» abans de la cullera: **Castellar 2 · Rubí 2 · Linyola 3 · Bell-lloc 3 · Alcoletge 2 · Vilanova 3 · Anciles 4** (les 10 X de numeració del bloc 4).

## 4. Per projecte: figura del signat · procedència (hash + lectura visual) · el que posem avui

Columnes: **procedència per hash** = millor candidat del projecte (ph = distància phash, 0 = idèntica; ncc = correlació ponderada pel PSR; escala = amplada de la figura respecte al candidat; «cand. dins veritat» = el candidat és una PEÇA de la composició); **veredicte hash** (IGUAL / fort / probable / no trobat); **lectura visual (Claude)** = què és i d'on surt, mirant-ho; **nosaltres** = imatge del bloc 4b amb la seva font per phash i si és la mateixa que la de l'Eva. Fulls: `docs/imatges/fulls/<projecte>.jpg`.

### 4.1 castellar — `3001621_informe_v0`

11 imatges: 8 de projecte, 2 de llibre (estabilitat de vessant) i el segell. **Les 4 figures surten de PNG que l'Eva deixa a `ANNEXES/ALTRES`** (`m7`, `m8`, `m12 mgeol`; el tall de `tall.pdf`), les 3 fotos de `FOTOGRAFIES/`. Nosaltres: 2 fotos iguals (sondeig, materials), DPSH vàlida però diferent, cap figura igual, plànol pendent. Les còpies renombrades de `FOTOGRAFIES/` (`maquina_dpsh*`, `detall_materials*`, `vista_general_1`, `maquina_sondeig`) són duplicats nostres del març, no de l'Eva; `M1.png` porta el rol `figure_geological_map` erroni (és el topogràfic).

| # | Figura del signat (peu) | ranura | mides | procedència per hash (top) | veredicte hash | nosaltres (bloc 4b) | lectura visual (Claude) |
|---|---|---|---|---|---|---|---|
| 1 | Figura 1. Situació de la zona d’estudi, amb color taronja. (mapes topo | fig_situacio | 1430×714 | `ANNEXES/ALTRES/m7.png` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `ANNEXES/ALTRES/M1.png` (0.767), `ANNEXES/ALTRES/M4.png` (0.563) | IGUAL (sencera) | 1258×2339 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | = `m7.png` (idèntica). Peces: `M1.png` topo + `M4.png` topo ampliat amb rectangle taronja. Composició de l'Eva. |
| 2 | Figura 2. Emplaçament de l’habitatge projecte i els assaigs realitzats | fig_assaigs | 812×800 | `ANNEXES/ALTRES/m8.png` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `ANNEXES/ALTRES/m6.png` (0.818), `3001621_plànol de situació.pdf` p1 (0.972) | IGUAL (sencera) | PENDENT | = `m8.png` (idèntica); base `m6.png` (orto). És la meitat dreta de l'annex de situació (0,97). |
| 3 | Fotografia 1. Vista de la màquina utilitzada en un dels assaigs de pen | foto_dpsh | 1920×1080 | `FOTOGRAFIES/DPSH/maquina_dpsh_3.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FOTOGRAFIES/P4.jpg` (1.0), `OGRAFIES/DPSH/maquina_dpsh.jpg` (0.624) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/DPSH/maquina_dpsh.jpg` ≠ Eva | = `P4.jpg` (còpia `DPSH/maquina_dpsh_3.jpg`). Nosaltres `maquina_dpsh.jpg` (= P1): una altra vista, vàlida. |
| 4 | Fotografia 2. Vista de la màquina utilitzada per a la realització del  | foto_sondeig | 1920×1080 | `FOTOGRAFIES/S1/Imagen de WhatsApp 2025-10-24 a las 11.10.37_0d0237fe.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `ES/SONDEIG/maquina_sondeig.jpg` (1.0), `FOTOGRAFIES/P2.jpg` (0.666) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/S1/Imagen de WhatsApp 2025-10-24 a las 11.10.37_0d0237fe.jpg` **= Eva** | = `S1/…11.10.37` (còpia `SONDEIG/maquina_sondeig.jpg`). Igual. |
| 5 | Figura 3. Cullera normalitzada. Gràfic extret de “Geotécnia y cimiento | fig_spt_cullera | 1552×641 | (estàtica, la posa el generador) | — | igual | estàtica |
| 6 | Figura 4. Mapa geològic a escala 1:25.000 de la zona en estudi (ICGC,  | fig_geologic | 1470×806 | `ANNEXES/ALTRES/m12 mgeol.png` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `V0/ANNEXES/3001621_sondeig.pdf` p2 (0.871), `DF/ANNEXES/3001621_sondeig.pdf` p2 (0.871) | IGUAL (sencera) | 800×600 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | = `m12 mgeol.png` (idèntica: retall ICGC 1:25.000 + llegenda composta). Nosaltres: ICGC per UTM sense llegenda. |
| 7 | Fotografia 4. Detall dels materials recuperats durant la realització d | foto_materials | 1920×1080 | `FOTOGRAFIES/S1/Imagen de WhatsApp 2025-10-24 a las 11.10.01_287d2efa.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `TOGRAFIES/detall_materials.jpg` (1.0), `24 a las 11.10.14_4f05eb48.jpg` (0.65) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/S1/Imagen de WhatsApp 2025-10-24 a las 11.10.01_287d2efa.jpg` **= Eva** | = `S1/…11.10.01` (còpia `detall_materials.jpg`). Igual. |
| 8 | Figura 5. Tall de correlació. | fig_tall | 977×293 | `tall.pdf` p1 — ph=28, ncc=0.883, psr=5.4, escala 0.79 (veritat dins cand.); també `3001621_tall de correlació.pdf` p1 (0.852), `3001621_tall de correlació.pdf` p1 (0.848) | RETALL/COMPOSICIÓ (fort) | 2481×1754 ← `tall.pdf` p1 ≠ Eva | retall de la secció de `tall.pdf`. Nosaltres: pàgina sencera. |
| 9 | Figura 6 i Figura 7. Líneas de saturació possibles, es marca la que s’ | fig_extra_estabilitat | 267×398 | `PDF-V0/ANNEXES/3001621_sondeig.pdf` p1 — ph=36, ncc=0.704, psr=7.2, escala 0.12 (veritat dins cand.); també `DF/ANNEXES/3001621_sondeig.pdf` p1 (0.704) | RETALL/COMPOSICIÓ (fort) | absent (cap ranura) | figura de llibre (Hoek & Bray, `.wmf`): no és al projecte. El 0,70 a escala 0,12 és soroll. |
| 10 | Figura 6 i Figura 7. Líneas de saturació possibles, es marca la que s’ | fig_extra_estabilitat | 678×672 | `ANNEXES/ALTRES/M4.png` — ph=28, ncc=0.462, psr=4.8, escala 0.12 (veritat dins cand.) | no trobat per hash | absent (cap ranura) | idem (àbac de Hoek & Bray): no és al projecte. |

### 4.2 rubi — `3001631_informe (la plantilla)`

10 imatges: 7 de projecte, el pastís de granulometria i el segell. **5 figures/fotos són PNG d'`ANNEXES/Altres`** (`F1 UBI`, `F3 VG` Google Earth, `F2 UBI PUNTS`, `F4 MGEOL`, `F5 TALL`). No hi ha plànol de l'arquitecte en PDF (dues fotos d'un paper) i l'Eva no el fa servir. Nosaltres: DPSH i materials iguals; plànol = la foto del paper; aèria i geològic pendents (sense UTM) tot i que `F4 MGEOL.png` és al projecte.

| # | Figura del signat (peu) | ranura | mides | procedència per hash (top) | veredicte hash | nosaltres (bloc 4b) | lectura visual (Claude) |
|---|---|---|---|---|---|---|---|
| 1 | Figura 1. Situació de la zona d’estudi, amb color taronja. (mapes topo | fig_situacio | 1595×795 | `ANNEXES/Altres/F1 UBI.png` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `ANNEXES/Altres/m3.png` (0.908), `ANNEXES/Altres/m2.png` (0.887) | IGUAL (sencera) | 1258×2339 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | = `F1 UBI.png` (idèntica). Peces `m2.png`/`m3.png` (orto) + topo. Nosaltres: retall vertical de l'annex. |
| 2 | Fotografia 1. Vista general de la zona d’estudi (Google Earth, Agost 2 | foto_vista | 1393×1035 | `ANNEXES/Altres/F3 VG.png` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.) | IGUAL (sencera) | absent (cap ranura) | = `F3 VG.png`: captura de Google Earth (vista de carrer), no és foto de camp. Nosaltres: cap. |
| 3 | Figura 2. Situació de l’estructura projectada i els assaigs realitzats | fig_assaigs | 847×838 | `ANNEXES/Altres/F2 UBI PUNTS.png` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `3001631_plànol de situació.pdf` p1 (0.902), `3001631_plànol de situació.pdf` p1 (0.898) | IGUAL (sencera) | 2400×3188 ← `25.0794/IMG-20251104-WA0015.jpg` ≠ Eva | = `F2 UBI PUNTS.png` (idèntica): orto ampliada + punts. L'annex de situació la conté (0,90). Nosaltres: foto d'un plànol imprès (`IMG-…WA0015.jpg`). |
| 4 | Fotografia 2. Vista de la màquina utilitzada en un dels assaigs de pen | foto_dpsh | 1920×1080 | `FOTOGRAFIES/P3.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FH11→3001631_fotografies.pdf` p1 (0.62) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/P3.jpg` **= Eva** | = `P3.jpg`. Igual. |
| 5 | Figura 3. Cullera normalitzada. Gràfic extret de “Geotécnia y cimiento | fig_spt_cullera | 1552×641 | (estàtica, la posa el generador) | — | igual | estàtica |
| 6 | Figura 4. Mapa geològic a escala 1:50.000 de la zona en estudi, (Font: | fig_geologic | 1578×805 | `ANNEXES/Altres/F4 MGEOL.png` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `ANNEXES/Altres/m5.png` (0.723), `6_mapa Geol_CAT_ - CAST_VS.pdf` p1 (0.625) | IGUAL (sencera) | PENDENT | = `F4 MGEOL.png` (idèntica); peça `m5.png`. Nosaltres: PENDENT (sense UTM) tot i tenir el PNG al projecte. |
| 7 | Fotografia 3. Detall dels materials del primer nivell. | foto_materials | 1920×1080 | `FOTOGRAFIES/SPT1.jpg` — ph=30, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `NNEXES/3001631_fotografies.pdf` p2 (0.779), `FH11→3001631_fotografies.pdf` p1 (0.734) | RETALL/COMPOSICIÓ (fort) | 1080×1920 ← `FOTOGRAFIES/SPT1.jpg` **= Eva** | = `SPT1.jpg` (NCC 1,0; phash 30 per orientació EXIF). Igual (×2 per nivell). |
| 9 | Figura 5. Detall del tall de correlació que s’adjunta als annexes. | fig_tall | 777×343 | `tall.pdf` p1 — ph=34, ncc=0.912, psr=9.0, escala 0.675 (veritat dins cand.); també `3001631_tall de correlació.pdf` p1 (0.91), `3001631_tall de correlació.pdf` p1 (0.905) | RETALL/COMPOSICIÓ (fort) | 1625×757 ← `ANNEXES/Altres/F5 TALL.png` ≠ Eva | retall de la secció de `tall.pdf` (= `F5 TALL.png`). Nosaltres: `F5 TALL.png` sencer amb llegenda. |

### 4.3 linyola — `4001607_informe`

9 imatges: 7 de projecte + cullera + segell. Les 3 figures del projecte vénen del **projecte de l'arquitecte** (`2_02B_DG_Silvia_Jaume.pdf`: p1 situació, p3 planta, p11 secció) i de l'annex de situació A4 on l'Eva hi posa els punts. Els dibuixos de línia fina fan el hash feble (0,48-0,72) tot i que a ull la font és inequívoca. Nosaltres: materials igual; DPSH vàlida diferent; situació il·legible (tira); planta sense punts; cap perfil.

| # | Figura del signat (peu) | ranura | mides | procedència per hash (top) | veredicte hash | nosaltres (bloc 4b) | lectura visual (Claude) |
|---|---|---|---|---|---|---|---|
| 1 | Figura 1. Ubicació de la parcel·la en estudi. | fig_situacio | 1628×570 | `FH11→4001607_plànol de situació.pdf` p1 — ph=40, ncc=0.719, psr=5.7, escala 0.493 (veritat dins cand.); també `4001607_plànol de situació.pdf` p1 (0.696) | RETALL/COMPOSICIÓ (fort) | 629×2339 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | inset (dos mapes) de l'annex de situació A4 (0,72 sobre el render FH11). Peces: p1 del projecte de l'arquitecte o ICGC. Nosaltres: tira 629×2339 il·legible del mateix annex. |
| 2 | Figura 2. Detall de l’edificació projectada i els assaigs realitzats. | fig_assaigs | 1337×688 | `25.0616/Punts de Sondeig_Silvia_Jaume.pdf` p1 — ph=24, ncc=0.483, psr=11.1, escala 0.924 (veritat dins cand.) | no trobat per hash | 2482×1755 ← `25.0616/Punts de Sondeig_Silvia_Jaume.pdf` p1 ≠ Eva | planta p03 del projecte (`Punts de Sondeig_Silvia_Jaume.pdf` = `2_02B_DG` p3) amb icones de punt petites afegides per l'Eva. Hash feble (0,48, PSR 11): línia fina. `_REDIBUIX.pdf` (punts vermells grossos) NO és la font. Nosaltres: la mateixa planta sencera, sense punts. |
| 3 | Figura 3. Detall del perfil de l’habitatge projectat. | fig_projecte | 1281×402 | `25.0616/2_02B_DG_Silvia_Jaume.pdf` p4 — ph=24, ncc=0.606, psr=5.7, escala 0.36 (veritat dins cand.); també `ts de Sondeig_Silvia_Jaume.pdf` p1 (0.603), `e Sondeig_Silvia_Jaume (1).pdf` p1 (0.603) | retall probable | absent (cap ranura) | secció de la p11 del projecte de l'arquitecte (NCC 0,81; PSR baix perquè la pàgina té dues seccions). Nosaltres: cap ranura. |
| 4 | Fotografia 1. Vista de la màquina utilitzada en un dels assaigs de pen | foto_dpsh | 1512×1080 | `FOTOGRAFIES/P2.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FH11→4001607_fotografies.pdf` p1 (0.767), `NNEXES/4001607_fotografies.pdf` p1 (0.592) | IGUAL (sencera) | 1512×1080 ← `FOTOGRAFIES/P1.jpg` ≠ Eva | = `P2.jpg`. Nosaltres: `P1.jpg` (una altra vista, vàlida). |
| 5 | Figura 4. Cullera normalitzada. Gràfic extret de “Geotécnia y cimiento | fig_spt_cullera | 1552×641 | (estàtica, la posa el generador) | — | igual | estàtica |
| 6 | Figura 5. Mapa geològic a escala 1:50.000 de la zona en estudi (Font:  | fig_geologic | 1043×692 | `25.0616/2_02B_DG_Silvia_Jaume.pdf` p6 — ph=38, ncc=0.397, psr=5.5, escala 0.164 (veritat dins cand.) | no trobat per hash | 800×600 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | retall ICGC amb punt vermell: cap font al projecte. Nosaltres: mateix tipus (ICGC per UTM), enquadrament diferent. |
| 7 | Fotografia 2. Detall dels materials recuperats durant la realització d | foto_materials | 1620×1080 | `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.05.09_8fc7585f.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FH11→4001607_fotografies.pdf` p1 (0.825), `NNEXES/4001607_fotografies.pdf` p2 (0.703) | IGUAL (sencera) | 1620×1080 ← `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.05.09_8fc7585f.jpg` **= Eva** | = `…12.05.09.jpg`. Igual (×2 per nivell). |
| 8 | Figura 6. Tall de correlació. | fig_tall | 1003×271 | `PDF/ANNEXES/4001607_tall de correlació.pdf` p1 — ph=28, ncc=0.644, psr=4.6, escala 0.924 (veritat dins cand.); també `tall.pdf` p1 (0.628), `4001607_tall de correlació.pdf` p1 (0.619) | retall probable | 1754×1241 ← `tall.pdf` p1 ≠ Eva | retall de les dues seccions de l'annex de tall (0,64 a escala 0,92). Nosaltres: pàgina sencera. |

### 4.4 bell-lloc — `4001612_informe`

12 imatges: 10 de projecte + cullera + segell. **Les 3 figures «Font: Projecte» són retalls de l'`A.01.pdf`** (dos insets + planta); és l'únic signat sense figura d'assaigs ni punts (la memòria `report_figure_sources` ve d'aquí). Nosaltres: vista 1, DPSH i materials iguals; **vista 2 i sondeig errònies** (totes dues són la màquina DPSH); situació i aèria d'una altra font; plànol = A.01 sencer.

| # | Figura del signat (peu) | ranura | mides | procedència per hash (top) | veredicte hash | nosaltres (bloc 4b) | lectura visual (Claude) |
|---|---|---|---|---|---|---|---|
| 1 | Figura 1 i Figura 2. Detall de la ubicació de la parcel·la en estudi.  | fig_situacio | 730×673 | `25.0647/A.01.pdf` p1 — ph=36, ncc=0.787, psr=11.9, escala 0.192 (veritat dins cand.); també `A.01 amb punts.pdf` p1 (0.787), `A.01.pdf` p1 (0.787) | RETALL/COMPOSICIÓ (fort) | 1257×2339 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | inset cadastral de l'`A.01.pdf` de l'arquitecte (0,79, PSR 12, escala 0,19). Els PDF del Cadastre (`25.0647/4613172…`) NO són la font (0,16). Nosaltres: retall vertical de l'annex. |
| 2 | Figura 1 i Figura 2. Detall de la ubicació de la parcel·la en estudi.  | fig_situacio | 736×670 | `25.0647/A.01.pdf` p1 — ph=32, ncc=0.786, psr=7.8, escala 0.192 (veritat dins cand.); també `A.01 amb punts.pdf` p1 (0.786), `A.01.pdf` p1 (0.786) | RETALL/COMPOSICIÓ (fort) | 800×600 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | inset ortofoto amb parcel·la vermella del mateix `A.01.pdf` (0,79, PSR 7,8). Nosaltres: orto ICGC per UTM (mateix tipus, font diferent). |
| 3 | Figura 3. Ubicació de l’habitatge a l’interior de la parcel·la. Font:  | fig_projecte | 562×640 | `FOTOGRAFIES/DPSH/Imagen de WhatsApp 2025-10-01 a las 14.16.23_e62682b9.jpg` — ph=36, ncc=0.601, psr=5.1, escala 0.12 (cand. dins veritat); també `pl. situaci.pdf` p1 (0.548), `4001612_plànol de situació.pdf` p1 (0.545) | retall probable | 4967×3509 ← `25.0647/A.01.pdf` p1 ≠ Eva | planta d'emplaçament de l'`A.01.pdf` retallada al dibuix, SENSE punts (a ull; hash feble 0,46-0,63 per línia fina; també dins l'annex de situació 0,55). `A.01 amb punts.pdf` existeix i no s'usa. Nosaltres: `A.01.pdf` pàgina sencera. |
| 4 | Fotografia 1 i Fotografia 2. Vistes generals de la zona d’estudi. | foto_vista | 1920×1080 | `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.55.21_2f75bf2a.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FH11→4001612_fotografies.pdf` p1 (0.867), `NNEXES/4001612_fotografies.pdf` p2 (0.701) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.55.21_2f75bf2a.jpg` **= Eva** | = `…12.55.21.jpg`. Igual. |
| 5 | Fotografia 1 i Fotografia 2. Vistes generals de la zona d’estudi. | foto_vista | 1920×1080 | `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.54.41_ccbf024a.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FH11→4001612_fotografies.pdf` p1 (0.577), `NNEXES/4001612_fotografies.pdf` p2 (0.558) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.54.57_83d08c82.jpg` ≠ Eva | = `…12.54.41.jpg`. Nosaltres: `…12.54.57.jpg` = foto de la màquina DPSH (error de tria). |
| 6 | Fotografia 3. Vista de la màquina utilitzada en un dels assaigs de pen | foto_dpsh | 1920×1080 | `FOTOGRAFIES/DPSH/P1.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FH11→4001612_fotografies.pdf` p1 (0.51) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/DPSH/P1.jpg` **= Eva** | = `DPSH/P1.jpg`. Igual. |
| 7 | Fotografia 4. Vista de la màquina utilitzada per a la realització del  | foto_sondeig | 1512×1080 | `FOTOGRAFIES/SONDEIG/Imagen de WhatsApp 2025-10-01 a las 12.54.57_83d08c82.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `V0/ANNEXES/4001612_sondeig.pdf` p2 (0.928), `DF/ANNEXES/4001612_sondeig.pdf` p2 (0.928) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/DPSH/P2.jpg` ≠ Eva | = `SONDEIG/…12.54.57.jpg` (també a l'annex de sondeig p2, 0,93). Nosaltres: `DPSH/P2.jpg` = màquina DPSH (error). |
| 8 | Figura 4. Cullera normalitzada. Gràfic extret de “Geotécnia y cimiento | fig_spt_cullera | 1552×641 | (estàtica, la posa el generador) | — | igual | estàtica |
| 9 | Figura 5. Mapa geològic a escala 1:50.000 de la zona en estudi (Font:  | fig_geologic | 811×601 | `pl. situaci.pdf` p1 — ph=34, ncc=0.497, psr=6.4, escala 0.263 (veritat dins cand.) | no trobat per hash | 800×600 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | retall ICGC amb punt vermell: cap font. Nosaltres: mateix tipus. |
| 10 | Fotografia 5. Detall dels materials recuperats en el sondeig a rotació | foto_materials | 1620×1080 | `FOTOGRAFIES/SONDEIG/Imagen de WhatsApp 2025-10-06 a las 12.53.10_6b9bc5f4.jpg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `V0/ANNEXES/4001612_sondeig.pdf` p2 (0.71), `DF/ANNEXES/4001612_sondeig.pdf` p2 (0.71) | IGUAL (sencera) | 1620×1080 ← `FOTOGRAFIES/SONDEIG/Imagen de WhatsApp 2025-10-06 a las 12.53.10_6b9bc5f4.jpg` **= Eva** | = `SONDEIG/…12.53.10.jpg` (caixa). Igual. |
| 11 | Figura 6. Detall del tall de correlació que s’adjunta als annexes. | fig_tall | 1014×310 | `PDF V0/ANNEXES/4001612_tall de correlació.pdf` p1 — ph=28, ncc=0.976, psr=7.9, escala 0.79 (veritat dins cand.); també `4001612_tall de correlació.pdf` p1 (0.976), `4001612_tall de correlació.pdf` p1 (0.963) | RETALL/COMPOSICIÓ (fort) | 2481×1754 ← `tall.pdf` p1 ≠ Eva | retall de l'annex de tall (0,98). Nosaltres: pàgina sencera. |

### 4.5 alcoletge — `4001670_informe`

8 imatges: 6 de projecte + cullera + segell. La situació és una **composició pròpia** (no hi ha PNG ni retall); la figura d'assaigs és un **retall de l'annex de situació** de l'Eva (planta + ampliació + punts). Nosaltres: materials igual; **DPSH errònia** (full de camp `PENETROS.jpeg`); plànol = `A.01.pdf` sencer sense ampliació ni punts.

| # | Figura del signat (peu) | ranura | mides | procedència per hash (top) | veredicte hash | nosaltres (bloc 4b) | lectura visual (Claude) |
|---|---|---|---|---|---|---|---|
| 1 | Figura 1. Situació de la zona d’estudi. | fig_situacio | 1561×682 | `PDF/ANNEXES/4001670_tall de correlació.pdf` p1 — ph=32, ncc=0.595, psr=4.8, escala 0.263 (veritat dins cand.); també `tall.pdf` p1 (0.576), `4001670_tall de correlació.pdf` p1 (0.571) | retall probable | 1258×2339 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | composició pròpia topo + orto costat a costat. Dins l'annex de situació van apilats (0,67 però PSR 2,9): no és un retall. Peces ICGC no al projecte. Nosaltres: retall vertical de l'annex. |
| 2 | Figura 2. Situació de l’estructura projectada i els assaigs realitzats | fig_assaigs | 710×610 | `PDF/ANNEXES/4001670_tall de correlació.pdf` p1 — ph=30, ncc=0.79, psr=9.3, escala 0.263 (veritat dins cand.); també `tall.pdf` p1 (0.789), `4001670_tall de correlació.pdf` p1 (0.767) | RETALL/COMPOSICIÓ (fort) | 2482×1755 ← `26.0049/A.01.pdf` p1 ≠ Eva | retall de l'annex de situació: planta + ampliació taronja ratllada + punts + llegenda + nord (0,72, PSR 12; l'inset de l'annex de tall 0,79). `ampliació habitatge v2.png` és un altre dibuix del mateix contingut (0,32-0,39), no la font. Nosaltres: `A.01.pdf` sencer. |
| 3 | Fotografia 1. Vista de la màquina utilitzada en un dels assaigs de pen | foto_dpsh | 1600×739 | `FOTOS DE CAMP + PLANOL PUNTS/P3 - ALCOLETGE.jpeg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FH11→4001670_fotografies.pdf` p1 (0.943), `NNEXES/4001670_fotografies.pdf` p2 (0.782) | IGUAL (sencera) | 739×1600 ← `FOTOS DE CAMP + PLANOL PUNTS/PENETROS.jpeg` ≠ Eva | = `P3 - ALCOLETGE.jpeg` (màquina sota el porxo). Nosaltres: `PENETROS.jpeg` = foto del full de camp (error). |
| 4 | Figura 3. Cullera normalitzada. Gràfic extret de “Geotécnia y cimiento | fig_spt_cullera | 1552×641 | (estàtica, la posa el generador) | — | igual | estàtica |
| 5 | Figura 4. Mapa geològic a escala 1:50.000 de la zona en estudi (Font:  | fig_geologic | 669×454 | `FOTOS DE CAMP + PLANOL PUNTS/P2 - ALCOLETGE.jpeg` — ph=30, ncc=0.525, psr=8.0, escala 0.225 (cand. dins veritat) | retall probable | 800×600 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | retall ICGC («Zona d'estudi» taronja): cap font. Nosaltres: mateix tipus, amb punt. |
| 6 | Fotografia 2. Detall dels materials recuperats en l’assaig SPT-1. | foto_materials | 1600×739 | `FOTOS DE CAMP + PLANOL PUNTS/spt alcoletge.png` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FH11→4001670_fotografies.pdf` p1 (0.752), `NNEXES/4001670_fotografies.pdf` p2 (0.658) | IGUAL (sencera) | 1600×739 ← `FOTOS DE CAMP + PLANOL PUNTS/spt alcoletge.png` **= Eva** | = `spt alcoletge.png`. Igual (×2). |
| 7 | Figura 5. Detall del tall de correlació que s’adjunta als annexes. | fig_tall | 952×276 | `PDF/ANNEXES/4001670_tall de correlació.pdf` p1 — ph=18, ncc=0.806, psr=4.9, escala 0.79 (veritat dins cand.); també `tall.pdf` p1 (0.806), `4001670_tall de correlació.pdf` p1 (0.778) | RETALL/COMPOSICIÓ (fort) | 1754×1241 ← `tall.pdf` p1 ≠ Eva | retall de `tall.pdf` (0,81). Nosaltres: pàgina sencera. |

### 4.6 vilanova — `4001671_informe (castellà)`

12 imatges: 10 de projecte (una duplicada) + cullera + segell. **3 PNG d'`ANEXOS/OTROS`** (`F1 SIT`, `F4 MGEOL`; `F2 PUNTS` NO s'usa: el signat porta la planta amb punts de l'annex), planta de l'arquitecte `1.0.pdf` (adjunt de correu sense rol) i 2 fotos de materials. Nosaltres: DPSH igual, materials = la Foto 3; plànol, aèria i geològic pendents (sense rol ni UTM) tot i tenir `1.0.pdf` i `F4 MGEOL.png` al projecte.

| # | Figura del signat (peu) | ranura | mides | procedència per hash (top) | veredicte hash | nosaltres (bloc 4b) | lectura visual (Claude) |
|---|---|---|---|---|---|---|---|
| 1 | Figura 1. Situación de la parcela en estudio. Fuente: ICGC, modificado | fig_situacio | 1178×532 | `ANEXOS/OTROS/F1 SIT.png` — ph=0, ncc=0.999, psr=99.0, escala 1.0 (veritat dins cand.); també `ANEXOS/OTROS/M1.png` (0.717), `ANEXOS/OTROS/M22.png` (0.61) | IGUAL (sencera) | 1257×2339 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | = `OTROS/F1 SIT.png` (idèntica). Peces `M1.png` (0,72, PSR 36) + `M22.png` (topo ampliat). Nosaltres: retall vertical de l'annex. |
| 2 | Figura 2. Situación del emplazamiento de la vivienda proyectada. Fuent | fig_projecte | 771×669 | `pl situació.pdf` p1 — ph=32, ncc=0.945, psr=12.1, escala 0.577 (veritat dins cand.); també `26.0050/1.0.pdf` p1 (0.934), `4001671_plano de situación.pdf` p1 (0.926) | RETALL/COMPOSICIÓ (fort) | PENDENT | planta d'emplaçament de l'arquitecte: `26.0050/1.0.pdf` (0,93, PSR 11; adjunt de correu sense rol) i dins l'annex de situació (0,94). Nosaltres: PENDENT (cap rol `architect_plan`). |
| 3 | Fotografía 1. Detalle de la parcela de estudio. | foto_vista | 816×459 | `FOTOGRAFIES/DES DEL CARRER.jpeg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.) | IGUAL (sencera) | absent (cap ranura) | = `DES DEL CARRER.jpeg` (retall). Nosaltres: cap. |
| 4 | Figura 3. Situación de los ensayos realizados. | fig_assaigs | 711×568 | `pl situació.pdf` p1 — ph=32, ncc=0.978, psr=9.8, escala 0.493 (veritat dins cand.); també `4001671_plano de situación.pdf` p1 (0.97), `4001671_plano de situación.pdf` p1 (0.949) | RETALL/COMPOSICIÓ (fort) | absent (cap ranura) | planta amb punts de l'annex `pl situació.pdf` (0,98, PSR 10). `F2 PUNTS.png` (orto amb punts) NO és la del signat: l'Eva va canviar de suport. Nosaltres: cap. |
| 5 | Fotografía 1. Detalle del emplazamiento de la máquina realizando uno d | foto_dpsh | 794×446 | `FOTOGRAFIES/P1.jpeg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FOTOGRAFIES/P2.jpeg` (0.659), `FOTOGRAFIES/P3.jpeg` (0.588) | IGUAL (sencera) | 1599×899 ← `FOTOGRAFIES/P1.jpeg` **= Eva** | = `P1.jpeg`. Igual. |
| 6 | Figura 4. Cuchara normalizada. Gráfico extraído de “Geotécnia y cimien | fig_spt_cullera | 1552×641 | (estàtica, la posa el generador) | — | igual | estàtica |
| 7 | Figura 5. Mapa geológico a escala 1:50.000 de la zona de estudio. (ICG | fig_geologic | 1576×783 | `ANEXOS/OTROS/F4 MGEOL.png` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `ANEXOS/OTROS/m4.png` (0.666), `11→6_mapa Geol_CAT_ - CAST.pdf` p1 (0.62) | IGUAL (sencera) | PENDENT | = `F4 MGEOL.png` (idèntica; peça `m4.png`). Nosaltres: PENDENT tot i tenir el PNG. |
| 8 | Fotografía 2. Detalle de los materiales recuperados del ensayo SPT-1 e | foto_materials | 430×765 | `FOTOGRAFIES/SPT A P3.jpeg` — ph=2, ncc=0.234, psr=2.6, escala 0.12 (veritat dins cand.) | IGUAL (sencera) | 1599×899 ← `FOTOGRAFIES/SPT 1 P-1.jpeg` (= Eva 10) | = `SPT A P3.jpeg` (phash 2; retall vertical). Nosaltres: cap (una sola foto de materials). |
| 9 | Fotografía 2. Detalle de los materiales recuperados del ensayo SPT-1 e | foto_materials | 430×765 | `FOTOGRAFIES/SPT A P3.jpeg` — ph=2, ncc=0.234, psr=2.6, escala 0.12 (veritat dins cand.) | IGUAL (sencera) | 1599×899 ← `FOTOGRAFIES/SPT 1 P-1.jpeg` (= Eva 10) | duplicat de la 8 dins el docx (mateix rId). |
| 10 | Fotografía 3. Detalle de los materiales recuperados del ensayo SPT-1,  | foto_materials | 745×419 | `FOTOGRAFIES/SPT 1 P-1.jpeg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `ANEJOS/4001671_fotografías.pdf` p3 (0.639), `01671_corte de correlación.pdf` p1 (0.504) | IGUAL (sencera) | absent (cap ranura) | = `SPT 1 P-1.jpeg`. Nosaltres: la mateixa. |
| 11 | Figura 6. Corte de correlación de los materiales descritos en el estud | fig_tall | 1021×312 | `PDF/ANEJOS/4001671_corte de correlación.pdf` p1 — ph=30, ncc=0.793, psr=5.1, escala 0.79 (veritat dins cand.); també `tall.pdf` p1 (0.792), `01671_corte de correlación.pdf` p1 (0.76) | RETALL/COMPOSICIÓ (fort) | 1754×1241 ← `tall.pdf` p1 ≠ Eva | retall de l'annex corte (0,79). Nosaltres: pàgina sencera. |

### 4.7 anciles — `4001679_informe_V0 (castellà, Aragó)`

13 imatges: 10 de projecte + cullera + segell + signatura. 4 figures del projecte: situació (composició pròpia des de la Sede del Catastro), topogràfic (`IV_PLANOS.pdf` p5, 0,90), tipologies (`A01_TIPOL.pdf`, a ull), assaigs (annex `pl situ.pdf`). Geològic IGME sense font. Nosaltres: DPSH igual; **plànol = portada d'`IV_PLANOS.pdf`** i **sondeig = caixa de testimonis** (errors); materials vàlida però diferent; aèria i geològic pendents.

| # | Figura del signat (peu) | ranura | mides | procedència per hash (top) | veredicte hash | nosaltres (bloc 4b) | lectura visual (Claude) |
|---|---|---|---|---|---|---|---|
| 1 | Figura 1. Vista de la zona en estudio. Fuente: Sede electrónica del ca | fig_situacio | 1371×577 | `FH11→4001679_corte de correlación.pdf` p1 — ph=32, ncc=0.599, psr=4.6, escala 0.36 (veritat dins cand.); també `24.0807/IV_PLANOS.pdf` p6 (0.591), `01679_corte de correlación.pdf` p1 (0.585) | retall probable | 1257×2339 ← (font no identificada per phash: composició/retall nostre) ≠ Eva | composició pròpia topo + orto de la Sede del Catastro; dins l'annex de situació apilats (0,73 però PSR 2,4). Cap font retallable. Nosaltres: retall vertical de l'annex. |
| 2 | Figura 2. Detalle del plano topográfico del emplazamiento facilitado.  | fig_projecte | 730×721 | `24.0807/IV_PLANOS.pdf` p5 — ph=28, ncc=0.902, psr=40.6, escala 0.675 (veritat dins cand.); també `tall.pdf` p1 (0.652), `01679_corte de correlación.pdf` p1 (0.639) | RETALL/COMPOSICIÓ (fort) | 1241×1754 ← `24.0807/IV_PLANOS.pdf` p1 ≠ Eva | = `IV_PLANOS.pdf` p5 (topogràfic de la parcel·la; 0,90, PSR 41). Nosaltres: `IV_PLANOS.pdf` p1 = portada (error). |
| 3 | Figura 3. Detalle de las viviendas prevista. Fuente: Proyecto. | fig_projecte | 1021×705 | `24.0807/IV_PLANOS.pdf` p22 — ph=32, ncc=0.391, psr=8.2, escala 0.225 (veritat dins cand.) | no trobat per hash | absent (cap ranura) | = `A01_TIPOL.pdf` (= `IV_PLANOS.pdf` p9: plantes + tipologies), a ull; hash feble (0,30-0,39, línia fina). Nosaltres: cap ranura. |
| 4 | Figura 4. Situación de los ensayos realizados. | fig_assaigs | 638×677 | `tall.pdf` p1 — ph=34, ncc=0.884, psr=8.6, escala 0.14 (veritat dins cand.); també `01679_corte de correlación.pdf` p1 (0.869), `01679_corte de correlación.pdf` p1 (0.804) | RETALL/COMPOSICIÓ (fort) | absent (cap ranura) | planta amb punts (S vermell, P blau) de l'annex `pl situ.pdf` (0,70, PSR 6,4; inset de l'annex de tall 0,88). Nosaltres: cap. |
| 5 | Fotografía 1. Detalle del emplazamiento de la máquina realizando uno d | foto_dpsh | 1920×1080 | `FOTOGRAFIES/P1.jpeg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `FH11→4001679_fotografías.pdf` p1 (0.705), `ANEJOS/4001679_fotografías.pdf` p1 (0.696) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/P1.jpeg` **= Eva** | = `P1.jpeg`. Igual. |
| 6 | Fotografía 2. Detalle del emplazamiento de la máquina realizando uno d | foto_sondeig | 1920×1080 | `FOTOGRAFIES/EMPL S2.jpeg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `24.0807/IV_PLANOS.pdf` p24 (0.508) | IGUAL (sencera) | 1920×1080 ← `FOTOGRAFIES/S1.jpeg` (= Eva 9) | = `EMPL S2.jpeg`. Nosaltres: `S1.jpeg` = caixa de testimonis (error: és la Foto 3 de l'Eva). |
| 7 | Figura 5. Cuchara normalizada. Gráfico extraído de “Geotécnia y cimien | fig_spt_cullera | 1552×641 | (estàtica, la posa el generador) | — | igual | estàtica |
| 8 | Figura 6. Mapa geológico a escala 1:1.000.000 de la zona de estudio: F | fig_geologic | 540×398 | `FOTOGRAFIES/P4.jpeg` — ph=40, ncc=0.415, psr=4.9, escala 0.493 (cand. dins veritat) | no trobat per hash | PENDENT | IGME 1:1.000.000 (Aragó): cap font al projecte ni a l'ICGC. Nosaltres: PENDENT (i l'ICGC no hi arriba). |
| 9 | Fotografía 3. Detalle de los materiales recuperados durante la realiza | foto_materials | 1920×1080 | `FOTOGRAFIES/S1.jpeg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `_V0/ANEJOS/4001679_sondeos.pdf` p2 (0.536) | IGUAL (sencera) | 1080×1920 ← `FOTOGRAFIES/DETALL SPT1 S1.jpeg` ≠ Eva | = `S1.jpeg` (caixa S-1). Nosaltres: `DETALL SPT1 S1.jpeg` (detall de la cullera: vàlida, diferent). |
| 10 | Fotografía 4. Detalle de los materiales recuperados durante la realiza | foto_materials | 1920×1080 | `FOTOGRAFIES/S2_0-3.jpeg` — ph=0, ncc=1.0, psr=99.0, escala 1.0 (veritat dins cand.); també `_V0/ANEJOS/4001679_sondeos.pdf` p4 (0.611) | IGUAL (sencera) | 1080×1920 ← `FOTOGRAFIES/DETALL SPT1 S1.jpeg` ≠ Eva | = `S2_0-3.jpeg` (caixa S-2). Nosaltres: cap (una sola). |
| 11 | Figura 7. Corte de correlación de los materiales descritos en el estud | fig_tall | 895×402 | `FH11→4001679_corte de correlación.pdf` p1 — ph=36, ncc=0.922, psr=7.2, escala 0.676 (veritat dins cand.); també `tall.pdf` p1 (0.921), `01679_corte de correlación.pdf` p1 (0.918) | RETALL/COMPOSICIÓ (fort) | 2481×1754 ← `PDF_V0/ANEJOS/4001679_corte de correlación.pdf` p1 ≠ Eva | retall de `tall.pdf` (0,92). Nosaltres: pàgina de `PDF_V0/…corte` sencera. |
| 13 | (sense peu; secció 4.4. EMPUJE DE TIERRAS) | fig_extra_empentes | 693×535 | `24.0807/IV_PLANOS.pdf` p1 — ph=38, ncc=0.427, psr=14.9, escala 0.263 (veritat dins cand.) | no trobat per hash | absent (cap ranura) | signatura manuscrita: no és figura, cap font. |


## 5. Mapa per fitxer: va a l'informe / auxiliar / no s'usa

Lectura per fitxer (visual + hash; §4 té els números). **INFORME** = font directa d'una figura o foto del signat (sencera o retallada); «annex de l'Eva» = el dibuixa ella abans del wizard i conté la figura (font retallable); «peça» = captura que ella compon; «auxiliar» = serveix per redactar, no es mostra; «no usada» = present al projecte i absent del signat. Els `PDF V0` són versions antigues dels annexos; els `.FH11` els originals FreeHand (renderitzats a `FH11→*.pdf`).

### 5.1 castellar

| fitxer | tipus | rol (file_mapping) | ús segons el signat |
|---|---|---|---|
| `25.0493/PRESSUPOST GEOTEC.CASTELLAR DEL VALLES.pdf` | pdf_skip 7 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `25.0493/PRESSUPOST GEOTEC.MODF.CASTELLAR DEL VALLES.pdf` | pdf_skip 7 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `25.0493/WhatsApp Image 2025-10-20 at 13.00.25 (1).jpeg` | img | photo_site_overview | foto del solar enviada pel client: no usada al signat |
| `25.0493/WhatsApp Image 2025-10-20 at 13.00.25.jpeg` | img | — | foto del solar enviada pel client: no usada al signat |
| `4687-GTL-25 Castellar del Vallés.pdf` | pdf_skip 5 pàg | gtl_report | auxiliar (informe/pressupost/laboratori: text) |
| `ACCEPTACIO/PRESSUPOST GEOTEC CASTELLAR DEL.....pdf` | pdf_skip 7 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `ANNEXES/3001621_fotografies.FH11` | fh11 | — | original FreeHand de l'annex |
| `ANNEXES/3001621_plànol de situació.FH11` | fh11 | — | original FreeHand de l'annex |
| `ANNEXES/3001621_sondeig.FH11` | fh11 | — | original FreeHand de l'annex |
| `ANNEXES/3001621_tall de correlació.FH11` | fh11 | — | original FreeHand de l'annex |
| `ANNEXES/ALTRES/6_mapa Geologic_CAT_VS.FH11` | fh11 | — | original FreeHand del geològic (= m12) |
| `ANNEXES/ALTRES/M1.png` | png_annex_altres | figure_geological_map | peça de la Fig 1 (topo ICGC; rol `figure_geological_map` ERRONI) |
| `ANNEXES/ALTRES/M10.png` | png_annex_altres | — | peça del geològic (sense llegenda) |
| `ANNEXES/ALTRES/M11.png` | png_annex_altres | — | peça del geològic (sense llegenda) |
| `ANNEXES/ALTRES/M2.png` | png_annex_altres | — | peça (orto ampliada): variant no usada |
| `ANNEXES/ALTRES/M3.png` | png_annex_altres | — | peça (topo ampliat sense rectangle): no usada |
| `ANNEXES/ALTRES/M4.png` | png_annex_altres | — | peça de la Fig 1 (topo ampliat amb rectangle) |
| `ANNEXES/ALTRES/m12 mgeol.png` | png_annex_altres | — | **INFORME: Fig 4** (geològic + llegenda, idèntica) |
| `ANNEXES/ALTRES/m5.png` | png_annex_altres | — | auxiliar: croquis manuscrit dels punts (per dibuixar-los) |
| `ANNEXES/ALTRES/m6.png` | png_annex_altres | — | peça base de la Fig 2 (orto) |
| `ANNEXES/ALTRES/m7.png` | png_annex_altres | — | **INFORME: Fig 1** (composició de l'Eva, idèntica) |
| `ANNEXES/ALTRES/m8.png` | png_annex_altres | — | **INFORME: Fig 2** (orto + punts, idèntica) |
| `ANNEXES/ALTRES/m9.png` | png_annex_altres | — | base del tall amb llegenda (la Fig 5 és un retall del tall) |
| `FOTOGRAFIES/DPSH/maquina_dpsh.jpg` | foto | photo_dpsh_equipment | còpia nostra de P1 (no usada; és la que posem nosaltres) |
| `FOTOGRAFIES/DPSH/maquina_dpsh_2.jpg` | foto | — | còpia nostra de P3 (no usada) |
| `FOTOGRAFIES/DPSH/maquina_dpsh_3.jpg` | foto | — | còpia nostra de P4 (= Foto 1) |
| `FOTOGRAFIES/Imagen de WhatsApp 2025-10-24 a las 09.37.01_63bb48b8.jpg` | foto | field_photo | auxiliar: foto del full de camp |
| `FOTOGRAFIES/Imagen de WhatsApp 2025-10-24 a las 10.02.53_404bc72b.jpg` | foto | — | auxiliar: foto del full de camp |
| `FOTOGRAFIES/P1.jpg` | foto | photo_test_point | foto de màquina no usada |
| `FOTOGRAFIES/P2.jpg` | foto | — | foto de màquina no usada |
| `FOTOGRAFIES/P3.jpg` | foto | — | foto de màquina no usada |
| `FOTOGRAFIES/P4.jpg` | foto | — | **INFORME: Foto 1** (màquina DPSH) |
| `FOTOGRAFIES/S1/Imagen de WhatsApp 2025-10-24 a las 11.10.01_287d2efa.jpg` | foto | — | **INFORME: Foto 4** (caixa de testimonis) |
| `FOTOGRAFIES/S1/Imagen de WhatsApp 2025-10-24 a las 11.10.14_4f05eb48.jpg` | foto | — | foto de caixa no usada |
| `FOTOGRAFIES/S1/Imagen de WhatsApp 2025-10-24 a las 11.10.37_0d0237fe.jpg` | foto | — | **INFORME: Foto 2** (màquina de sondeig) |
| `FOTOGRAFIES/SONDEIG/maquina_sondeig.jpg` | foto | photo_sondeig_equipment | còpia nostra de S1/11.10.37 (= Foto 2) |
| `FOTOGRAFIES/detall_materials.jpg` | foto | photo_spt_sample | còpia nostra de S1/11.10.01 (= Foto 4) |
| `FOTOGRAFIES/detall_materials_2.jpg` | foto | — | còpia nostra (no usada) |
| `FOTOGRAFIES/vista_general_1.jpg` | foto | — | còpia nostra de P2 (no usada) |
| `PDF-V0/3001621_informe_v0.pdf` | pdf_skip 43 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF-V0/ANNEXES/3001621_DPSH.pdf` | pdf_aux 4 pàg | — | auxiliar: annex DPSH (taules) |
| `PDF-V0/ANNEXES/3001621_fotografies.pdf` | pdf_v0 2 pàg | — | annex de l'Eva: la seva selecció de fotos (font indirecta) |
| `PDF-V0/ANNEXES/3001621_plànol de situació.pdf` | pdf_v0 1 pàg | — | annex de l'Eva: conté la Fig 2 (meitat dreta) i els mapes de la Fig 1 apilats |
| `PDF-V0/ANNEXES/3001621_sondeig.pdf` | pdf_v0 2 pàg | — | annex de l'Eva: registre + fotos de màquina i caixa (font indirecta) |
| `PDF-V0/ANNEXES/3001621_tall de correlació.pdf` | pdf_v0 1 pàg | — | annex de l'Eva: la Fig 5 n'és el retall |
| `PDF-V0/LLETRA/3001621_PORTADA_25_v0.pdf` | pdf_skip 1 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF-V0/LLETRA/3001621_informe_v0.pdf` | pdf_skip 24 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/3001621_informe.pdf` | pdf_skip 49 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/ANNEXES/3001621_DPSH.pdf` | pdf_aux 4 pàg | — | auxiliar: annex DPSH (taules) |
| `PDF/ANNEXES/3001621_fotografies.pdf` | pdf_annex 2 pàg | — | annex de l'Eva: la seva selecció de fotos (font indirecta) |
| `PDF/ANNEXES/3001621_plànol de situació.pdf` | pdf_annex 1 pàg | — | annex de l'Eva: conté la Fig 2 (meitat dreta) i els mapes de la Fig 1 apilats |
| `PDF/ANNEXES/3001621_sondeig.pdf` | pdf_annex 2 pàg | sondeig_annex | annex de l'Eva: registre + fotos de màquina i caixa (font indirecta) |
| `PDF/ANNEXES/3001621_tall de correlació.pdf` | pdf_annex 1 pàg | — | annex de l'Eva: la Fig 5 n'és el retall |
| `PDF/ANNEXES/LAB-SIG.pdf` | pdf_skip 5 pàg | lab_results_pdf | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/LLETRA/3001621_PORTADA_25.pdf` | pdf_skip 1 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/LLETRA/3001621_informe_v0.pdf` | pdf_skip 24 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PENETROS + SONDEIG.pdf` | pdf 5 pàg | dpsh_field_sheet, sondeig_field_sheet | auxiliar: fotos dels fulls de camp |
| `tall.pdf` | pdf 1 pàg | correlation_section | **INFORME: Fig 5** (retall de la secció) |
| `FH11→3001621_fotografies.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: la seva selecció de fotos (font indirecta) |
| `FH11→3001621_plànol de situació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: conté la Fig 2 (meitat dreta) i els mapes de la Fig 1 apilats |
| `FH11→3001621_sondeig.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: registre + fotos de màquina i caixa (font indirecta) |
| `FH11→3001621_tall de correlació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: la Fig 5 n'és el retall |
| `FH11→6_mapa Geologic_CAT_VS.pdf` | fh11_pdf 1 pàg | — | render FH11: original FreeHand del geològic (= m12) |

### 5.2 rubi

| fitxer | tipus | rol (file_mapping) | ús segons el signat |
|---|---|---|---|
| `25.0794/IMG-20251104-WA0015.jpg` | img | — | foto d'un plànol imprès (planta): l'Eva NO l'usa; nosaltres sí (error) |
| `25.0794/IMG-20251104-WA0016.jpg` | img | — | foto d'un plànol imprès (fonamentació): no usada |
| `25.0794/PRESSUPOST GEOTEC.RUBI.pdf` | pdf_skip 7 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `3001631 - PENETROS.pdf` | pdf 3 pàg | — | auxiliar: fotos dels fulls de camp |
| `4703-GTL-25 Rubí.pdf` | pdf_skip 8 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `ACCEPTACIO/WhatsApp Image 2025-11-13 at 11.55.57.jpeg` | img | — | auxiliar: pressupost signat (foto) |
| `ANNEXES/3001631_fotografies.FH11` | fh11 | — | annex de l'Eva: la seva selecció de fotos |
| `ANNEXES/3001631_plànol de situació.FH11` | fh11 | — | annex de l'Eva: conté la Fig 2 i els mapes de la Fig 1 |
| `ANNEXES/3001631_tall de correlació.FH11` | fh11 | — | annex: la Fig 5 n'és el retall |
| `ANNEXES/Altres/6_mapa Geol_CAT_ - CAST_VS.FH11` | fh11 | — | original FreeHand del geològic (= F4; el render libfreehand surt desordenat) |
| `ANNEXES/Altres/F1 UBI.png` | png_annex_altres | — | **INFORME: Fig 1** (idèntica) |
| `ANNEXES/Altres/F2 UBI PUNTS.png` | png_annex_altres | — | **INFORME: Fig 2** (idèntica) |
| `ANNEXES/Altres/F3 VG.png` | png_annex_altres | — | **INFORME: Foto 1** (Google Earth) |
| `ANNEXES/Altres/F4 MGEOL.png` | png_annex_altres | — | **INFORME: Fig 4** (idèntica) |
| `ANNEXES/Altres/F5 TALL.png` | png_annex_altres | — | base del tall amb llegenda (la Fig 5 n'és el retall) |
| `ANNEXES/Altres/m1.png` | png_annex_altres | — | peça de la Fig 1 (topo) |
| `ANNEXES/Altres/m2.png` | png_annex_altres | — | peça de la Fig 1 (orto) |
| `ANNEXES/Altres/m3.png` | png_annex_altres | — | peça (orto ampliada) |
| `ANNEXES/Altres/m4.png` | png_annex_altres | — | auxiliar: croquis manuscrit dels punts |
| `ANNEXES/Altres/m5.png` | png_annex_altres | — | peça de la Fig 4 (geològic sense llegenda) |
| `FOTOGRAFIES/Imatge de WhatsApp 2025-11-14 a les 11.17.54_936f3908.jpg` | foto | — | auxiliar: foto del full de camp |
| `FOTOGRAFIES/Imatge de WhatsApp 2025-11-14 a les 11.49.21_a3e04224.jpg` | foto | — | foto de la cullera (variant) no usada |
| `FOTOGRAFIES/P1.jpg` | foto | — | foto de màquina no usada |
| `FOTOGRAFIES/P2.jpg` | foto | — | foto de màquina no usada |
| `FOTOGRAFIES/P3.jpg` | foto | — | **INFORME: Foto 2** (màquina DPSH) |
| `FOTOGRAFIES/SPT1.jpg` | foto | — | **INFORME: Foto 3** (cullera SPT) |
| `PDF/3001631_informe.pdf` | pdf_skip 46 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/ANNEXES/3001631_DPSH.pdf` | pdf_aux 3 pàg | — | auxiliar: annex DPSH (taules) |
| `PDF/ANNEXES/3001631_fotografies.pdf` | pdf_annex 2 pàg | — | annex de l'Eva: la seva selecció de fotos |
| `PDF/ANNEXES/3001631_plànol de situació.pdf` | pdf_annex 1 pàg | — | annex de l'Eva: conté la Fig 2 i els mapes de la Fig 1 |
| `PDF/ANNEXES/3001631_tall de correlació.pdf` | pdf_annex 1 pàg | — | annex: la Fig 5 n'és el retall |
| `PDF/ANNEXES/LAB-SIG.pdf` | pdf_skip 8 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/LLETRA/3001631_PORTADA_25.pdf` | pdf_skip 1 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/LLETRA/3001631_informe.pdf` | pdf_skip 21 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `tall.pdf` | pdf 1 pàg | — | **INFORME: Fig 5** (retall de la secció) |
| `FH11→3001631_fotografies.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: la seva selecció de fotos |
| `FH11→3001631_plànol de situació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: conté la Fig 2 i els mapes de la Fig 1 |
| `FH11→3001631_tall de correlació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex: la Fig 5 n'és el retall |
| `FH11→6_mapa Geol_CAT_ - CAST_VS.pdf` | fh11_pdf 1 pàg | — | render FH11: original FreeHand del geològic (= F4; el render libfreehand surt desordenat) |

### 5.3 linyola

| fitxer | tipus | rol (file_mapping) | ús segons el signat |
|---|---|---|---|
| `25.0616/25·0616.pdf` | pdf 3 pàg | — | auxiliar: pressupost (no imatge) |
| `25.0616/2_02B_DG_Silvia_Jaume.pdf` | pdf 11 pàg | — | projecte de l'arquitecte (11 pàg): **p1 = mapes de la Fig 1 (peces), p3 = base de la Fig 2 (planta), p11 = Fig 3 (secció)**; la resta no s'usa |
| `25.0616/Punts de Sondeig_Silvia_Jaume.pdf` | pdf 1 pàg | — | planta p03 de l'arquitecte: base de la Fig 2 (l'Eva hi afegeix icones de punt) |
| `4672-GTL-25 Linyola.pdf` | pdf_skip 7 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `ACCEPTACIO/G3DT_Silvia_Jaume signat.pdf` | pdf 3 pàg | — | auxiliar: pressupost signat |
| `ANNEXES/4001607_fotografies.FH11` | fh11 | — | annex de l'Eva: la seva selecció de fotos |
| `ANNEXES/4001607_plànol de situació.FH11` | fh11 | — | annex de l'Eva: idem |
| `ANNEXES/4001607_tall de correlació.FH11` | fh11 | — | annex: la Fig 6 n'és el retall (2 seccions) |
| `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 11.11.17_3f18c893.jpg` | foto | — | auxiliar: foto del full de camp |
| `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.04.53_99ada7ae.jpg` | foto | — | auxiliar: foto de l'etiqueta de la mostra |
| `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.05.09_8fc7585f.jpg` | foto | — | **INFORME: Foto 2** (cullera SPT) |
| `FOTOGRAFIES/P1.jpg` | foto | — | foto de màquina no usada (la que posem nosaltres) |
| `FOTOGRAFIES/P2.jpg` | foto | — | **INFORME: Foto 1** (màquina DPSH) |
| `FOTOGRAFIES/P3.jpg` | foto | — | foto de màquina no usada |
| `PDF/4001607_informe.pdf` | pdf_skip 48 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/ANNEXES/4001607_DPSH.pdf` | pdf_aux 3 pàg | — | auxiliar: annex DPSH (taules) |
| `PDF/ANNEXES/4001607_fotografies.pdf` | pdf_annex 2 pàg | — | annex de l'Eva: la seva selecció de fotos |
| `PDF/ANNEXES/4001607_plànol de situació.pdf` | pdf_annex 1 pàg | — | annex de l'Eva: idem |
| `PDF/ANNEXES/4001607_tall de correlació.pdf` | pdf_annex 1 pàg | — | annex: la Fig 6 n'és el retall (2 seccions) |
| `PDF/ANNEXES/lab-sig.pdf` | pdf_skip 7 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/LLETRA/4001607_PORTADA_25.pdf` | pdf_skip 1 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/LLETRA/4001607_informe.pdf` | pdf_skip 24 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PENETROS.pdf` | pdf 3 pàg | — | auxiliar: fulls de camp escanejats |
| `Punts de Sondeig_Silvia_Jaume (1).pdf` | pdf 1 pàg | — | planta p03 de l'arquitecte: base de la Fig 2 (l'Eva hi afegeix icones de punt) |
| `Punts de Sondeig_Silvia_Jaume (1)_REDIBUIX.pdf` | pdf 1 pàg | — | planta redibuixada amb punts vermells grossos (Eva/arquitecte): NO és la font de la Fig 2 |
| `pl situ.pdf` | pdf 1 pàg | — | annex de l'Eva (A4): inset = Fig 1, planta amb punts = Fig 2 (retalls) |
| `tall.pdf` | pdf 1 pàg | — | **INFORME: Fig 6** (retall) |
| `FH11→4001607_fotografies.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: la seva selecció de fotos |
| `FH11→4001607_plànol de situació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: idem |
| `FH11→4001607_tall de correlació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex: la Fig 6 n'és el retall (2 seccions) |

### 5.4 bell-lloc

| fitxer | tipus | rol (file_mapping) | ús segons el signat |
|---|---|---|---|
| `25.0647/4613172CG1141S0001SU-15.pdf` | pdf 1 pàg | — | consulta cadastral (Sede del Catastro): NO és la font de la Fig 1 (0,16); auxiliar (RC, superfície) |
| `25.0647/4613173CG1141S0001ZU-13.pdf` | pdf 1 pàg | — | idem, segona parcel·la |
| `25.0647/A.01.pdf` | pdf 1 pàg | — | **INFORME: Fig 1 i 2 (insets cadastral + orto) i Fig 3 (planta d'emplaçament)**, retalls |
| `25.0647/PRESSUPOST GEOTEC.BELL-LLOC.pdf` | pdf_skip 7 pàg | — | auxiliar: pressupost |
| `4677-GTL-25 Bell-Lloc d'Urgell.pdf` | pdf_skip 5 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `A.01 amb punts.pdf` | pdf 1 pàg | — | plànol de l'arquitecte AMB punts (dibuixats): existeix i el signat NO l'usa |
| `A.01.pdf` | pdf 1 pàg | — | **INFORME: Fig 1 i 2 (insets cadastral + orto) i Fig 3 (planta d'emplaçament)**, retalls |
| `ACCEPTACIO/PRESSUPOST GEOTEC.BELL-LLOCsgtJBN.pdf` | pdf_skip 7 pàg | — | auxiliar: pressupost |
| `ANNEXES/4001612_fotografies.FH11` | fh11 | — | annex de l'Eva: la seva selecció de fotos (vistes 3 i 4 = Fotos 1 i 2) |
| `ANNEXES/4001612_plànol de situació.FH11` | fh11 | — | annex de l'Eva: idem |
| `ANNEXES/4001612_sondeig.FH11` | fh11 | — | original FreeHand de l'annex |
| `ANNEXES/4001612_tall de correlació.FH11` | fh11 | — | annex: la Fig 6 n'és el retall |
| `FOTOGRAFIES/DPSH/Imagen de WhatsApp 2025-10-01 a las 14.16.23_e62682b9.jpg` | foto | — | auxiliar: foto del full de camp |
| `FOTOGRAFIES/DPSH/P1.jpg` | foto | — | **INFORME: Foto 3** (màquina DPSH) |
| `FOTOGRAFIES/DPSH/P2.jpg` | foto | — | foto de màquina DPSH no usada (nosaltres la posem com a sondeig: error) |
| `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.54.41_ccbf024a.jpg` | foto | — | **INFORME: Foto 2** (vista general) |
| `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.54.57_83d08c82.jpg` | foto | — | foto de la màquina DPSH (duplicada a SONDEIG/ amb un altre retall): no usada (nosaltres la posem com a vista 2: error) |
| `FOTOGRAFIES/Imagen de WhatsApp 2025-10-01 a las 12.55.21_2f75bf2a.jpg` | foto | — | **INFORME: Foto 1** (vista general) |
| `FOTOGRAFIES/SONDEIG/Imagen de WhatsApp 2025-10-01 a las 12.54.57_83d08c82.jpg` | foto | — | **INFORME: Foto 4** (màquina de sondeig) |
| `FOTOGRAFIES/SONDEIG/Imagen de WhatsApp 2025-10-06 a las 12.03.25_47ce45a0.jpg` | foto | — | foto de la cullera no usada |
| `FOTOGRAFIES/SONDEIG/Imagen de WhatsApp 2025-10-06 a las 12.03.36_f091c815.jpg` | foto | — | foto de l'etiqueta no usada |
| `FOTOGRAFIES/SONDEIG/Imagen de WhatsApp 2025-10-06 a las 12.53.10_6b9bc5f4.jpg` | foto | — | **INFORME: Foto 5** (caixa de testimonis) |
| `PDF V0/4001612_informe_v0.pdf` | pdf_skip 39 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF V0/ANNEXES/4001612_DPSH.pdf` | pdf_aux 2 pàg | — | auxiliar: annex DPSH (taules) |
| `PDF V0/ANNEXES/4001612_fotografies.pdf` | pdf_v0 2 pàg | — | annex de l'Eva: la seva selecció de fotos (vistes 3 i 4 = Fotos 1 i 2) |
| `PDF V0/ANNEXES/4001612_plànol de situació.pdf` | pdf_v0 1 pàg | — | annex de l'Eva: idem |
| `PDF V0/ANNEXES/4001612_sondeig.pdf` | pdf_v0 2 pàg | — | annex de l'Eva: registre + fotos (màquina, caixes) (font indirecta) |
| `PDF V0/ANNEXES/4001612_tall de correlació.pdf` | pdf_v0 1 pàg | — | annex: la Fig 6 n'és el retall |
| `PDF V0/LLETRA/4001612_PORTADA_25_v0.pdf` | pdf_skip 1 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF V0/LLETRA/4001612_informe_v0.pdf` | pdf_skip 22 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/4001612_informe.pdf` | pdf_skip 45 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/ANNEXES/4001612_DPSH.pdf` | pdf_aux 2 pàg | — | auxiliar: annex DPSH (taules) |
| `PDF/ANNEXES/4001612_fotografies.pdf` | pdf_annex 2 pàg | — | annex de l'Eva: la seva selecció de fotos (vistes 3 i 4 = Fotos 1 i 2) |
| `PDF/ANNEXES/4001612_plànol de situació.pdf` | pdf_annex 1 pàg | — | annex de l'Eva: idem |
| `PDF/ANNEXES/4001612_sondeig.pdf` | pdf_annex 2 pàg | — | annex de l'Eva: registre + fotos (màquina, caixes) (font indirecta) |
| `PDF/ANNEXES/4001612_tall de correlació.pdf` | pdf_annex 1 pàg | — | annex: la Fig 6 n'és el retall |
| `PDF/ANNEXES/LAB-SIG.pdf` | pdf_skip 5 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/LLETRA/4001612_PORTADA_25.pdf` | pdf_skip 1 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/LLETRA/4001612_informe.pdf` | pdf_skip 22 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PENETROS.pdf` | pdf 2 pàg | — | auxiliar: fulls de camp |
| `SONDEIG.pdf` | pdf 3 pàg | — | auxiliar: fulls de camp + croquis |
| `pl. situaci.pdf` | pdf 1 pàg | — | annex de l'Eva: planta amb punts (el signat no la usa) + mapa |
| `tall.pdf` | pdf 1 pàg | — | **INFORME: Fig 6** (retall) |
| `FH11→4001612_fotografies.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: la seva selecció de fotos (vistes 3 i 4 = Fotos 1 i 2) |
| `FH11→4001612_plànol de situació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: idem |
| `FH11→4001612_sondeig.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: registre + fotos (màquina, caixes) (font indirecta) |
| `FH11→4001612_tall de correlació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex: la Fig 6 n'és el retall |

### 5.5 alcoletge

| fitxer | tipus | rol (file_mapping) | ús segons el signat |
|---|---|---|---|
| `26.0049/A.01.pdf` | pdf 1 pàg | — | plànol de l'arquitecte (estat actual): base de la planta; el signat usa la versió amb ampliació i punts de l'annex |
| `26.0049/PLANO 2.pdf` | pdf 1 pàg | — | plànol de l'arquitecte: no usat |
| `26.0049/PRESSUPOST GEOTEC.ALCOLETGE.pdf` | pdf_skip 7 pàg | — | auxiliar: pressupost |
| `26.0049/planol 3.pdf` | pdf 1 pàg | — | plànol amb l'ampliació ratllada: base del dibuix de la Fig 2 (no usat directament) |
| `26.0049/planol-1.pdf` | pdf 1 pàg | — | situació cadastral + orto de l'arquitecte: no usat (l'Eva compon la seva) |
| `A.01.pdf` | pdf 1 pàg | architect_plan | idem (còpia a l'arrel; rol `architect_plan`; nosaltres la posem sencera) |
| `ACCEPTACIO/PRESSUPOST GEOTEC.ALCOLETGE SIGNAT-SCAN.pdf` | pdf_skip 7 pàg | — | auxiliar: pressupost |
| `ANNEXES/4001670_fotografies.FH11` | fh11 | — | annex de l'Eva: la seva selecció de fotos |
| `ANNEXES/4001670_plànol de situació.FH11` | fh11 | — | annex de l'Eva: **Fig 2 n'és el retall** (planta + ampliació + punts); els mapes de la Fig 1 hi són apilats |
| `ANNEXES/4001670_tall de correlació.FH11` | fh11 | — | annex: la Fig 5 n'és el retall |
| `FOTOS DE CAMP + PLANOL PUNTS/CROQUIS.jpeg` | foto | field_croquis | auxiliar: croquis dels punts |
| `FOTOS DE CAMP + PLANOL PUNTS/P1 - ALCOLETGE.jpeg` | foto | photo_test_point | foto de màquina no usada |
| `FOTOS DE CAMP + PLANOL PUNTS/P2 - ALCOLETGE.jpeg` | foto | — | foto de màquina no usada (el hash la confon amb el geològic: fals positiu) |
| `FOTOS DE CAMP + PLANOL PUNTS/P3 - ALCOLETGE.jpeg` | foto | — | **INFORME: Foto 1** (màquina DPSH sota el porxo) |
| `FOTOS DE CAMP + PLANOL PUNTS/PENETROS.jpeg` | foto | — | auxiliar: foto del full de camp (nosaltres la posem com a màquina DPSH: error) |
| `FOTOS DE CAMP + PLANOL PUNTS/ampliació habitatge v2.png` | foto | — | planta amb ampliació i punts p1-p3 (PNG): NO és la font de la Fig 2 (dibuix diferent, mateix contingut) |
| `FOTOS DE CAMP + PLANOL PUNTS/spt alcoletge.png` | foto | photo_spt_sample | **INFORME: Foto 2** (cullera SPT) |
| `PDF/4001670_informe.pdf` | pdf_skip 17 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/ANNEXES/4001670_DPSH.pdf` | pdf_aux 3 pàg | — | auxiliar: annex DPSH (taules) |
| `PDF/ANNEXES/4001670_fotografies.pdf` | pdf_annex 2 pàg | — | annex de l'Eva: la seva selecció de fotos |
| `PDF/ANNEXES/4001670_plànol de situació.pdf` | pdf_annex 1 pàg | — | annex de l'Eva: **Fig 2 n'és el retall** (planta + ampliació + punts); els mapes de la Fig 1 hi són apilats |
| `PDF/ANNEXES/4001670_tall de correlació.pdf` | pdf_annex 1 pàg | — | annex: la Fig 5 n'és el retall |
| `PDF/LLETRA/4001670_portada.pdf` | pdf_skip 1 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PENETROS.pdf` | pdf 3 pàg | dpsh_field_sheet | auxiliar: fulls de camp |
| `tall.pdf` | pdf 1 pàg | correlation_section | **INFORME: Fig 5** (retall) |
| `FH11→4001670_fotografies.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: la seva selecció de fotos |
| `FH11→4001670_plànol de situació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: **Fig 2 n'és el retall** (planta + ampliació + punts); els mapes de la Fig 1 hi són apilats |
| `FH11→4001670_tall de correlació.pdf` | fh11_pdf 1 pàg | — | render FH11: annex: la Fig 5 n'és el retall |

### 5.6 vilanova

| fitxer | tipus | rol (file_mapping) | ús segons el signat |
|---|---|---|---|
| `26.0050/1.0.pdf` | pdf 1 pàg | — | **INFORME: Fig 2** (planta d'emplaçament de l'arquitecte, retall); adjunt de correu sense rol |
| `26.0050/PRESUPUESTO GEOTEC.VILANOVA DE SEGRIA.pdf` | pdf_skip 7 pàg | — | auxiliar: pressupost |
| `ACEPTACION CASTELLANO/PRESUPUESTO GEOTEC.VILANOVA DE SEGRIA Signed.pdf` | pdf_skip 7 pàg | — | auxiliar: pressupost |
| `ANEXOS/4001671_corte de correlación.FH11` | fh11 | — | annex: la Fig 6 n'és el retall |
| `ANEXOS/4001671_fotografías.FH11` | fh11 | — | annex de l'Eva: la seva selecció de fotos (4 pàg) |
| `ANEXOS/4001671_plano de situación.FH11` | fh11 | — | annex de l'Eva: idem |
| `ANEXOS/OTROS/6_mapa Geol_CAT_ - CAST.FH11` | fh11 | — | original FreeHand del geològic (= F4) |
| `ANEXOS/OTROS/F1 SIT.png` | png_annex_altres | figure_situation_map | **INFORME: Fig 1** (idèntica) |
| `ANEXOS/OTROS/F2 PUNTS.png` | png_annex_altres | figure_test_points | orto amb punts: NO usada al signat (l'Eva hi posa la planta amb punts) |
| `ANEXOS/OTROS/F4 MGEOL.png` | png_annex_altres | figure_geological_map | **INFORME: Fig 5** (idèntica) |
| `ANEXOS/OTROS/M1.png` | png_annex_altres | — | peça de la Fig 1 (topo) |
| `ANEXOS/OTROS/M2.png` | png_annex_altres | — | peça (topo urbà): no usada |
| `ANEXOS/OTROS/M22.png` | png_annex_altres | — | peça de la Fig 1 (topo ampliat) |
| `ANEXOS/OTROS/M3.png` | png_annex_altres | — | peça (orto ampliada): base de F2 PUNTS, no usada |
| `ANEXOS/OTROS/m4.png` | png_annex_altres | — | peça de la Fig 5 (geològic sense llegenda) |
| `FOTOGRAFIES/DES DE DARRERA.jpeg` | foto | photo_site_overview | foto del solar no usada |
| `FOTOGRAFIES/DES DEL CARRER.jpeg` | foto | — | **INFORME: Foto 1 (parcel·la)**, retallada |
| `FOTOGRAFIES/INTERIOR.jpeg` | foto | — | foto del solar no usada |
| `FOTOGRAFIES/P1.jpeg` | foto | photo_test_point | **INFORME: Foto 1** (màquina DPSH) |
| `FOTOGRAFIES/P2.jpeg` | foto | — | foto de màquina no usada |
| `FOTOGRAFIES/P3.jpeg` | foto | — | foto de màquina no usada |
| `FOTOGRAFIES/SPT 1 P-1.jpeg` | foto | photo_spt_sample | **INFORME: Foto 3** (SPT P-1) |
| `FOTOGRAFIES/SPT A P3.jpeg` | foto | — | **INFORME: Foto 2** (SPT P-3, retall vertical) |
| `FOTOGRAFIES/WhatsApp Image 2026-02-19 at 10.28.45.jpeg` | foto | field_photo | auxiliar: foto del full de camp |
| `FOTOGRAFIES/ZONA P3.jpeg` | foto | — | foto del solar no usada |
| `MULTICA_61.pdf` | pdf 1 pàg | — | auxiliar: taula de càlcul (no imatge) |
| `PDF/4001671_informe.pdf` | pdf_skip 19 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF/ANEJOS/4001671_DPSH.pdf` | pdf_aux 3 pàg | — | auxiliar: annex DPSH (taules) |
| `PDF/ANEJOS/4001671_corte de correlación.pdf` | pdf_annex 1 pàg | — | annex: la Fig 6 n'és el retall |
| `PDF/ANEJOS/4001671_fotografías.pdf` | pdf_annex 4 pàg | — | annex de l'Eva: la seva selecció de fotos (4 pàg) |
| `PDF/ANEJOS/4001671_plano de situación.pdf` | pdf_annex 1 pàg | — | annex de l'Eva: idem |
| `PDF/LETRA/4001671_portada.pdf` | pdf_skip 1 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PENETROS.pdf` | pdf 3 pàg | dpsh_field_sheet | auxiliar: fulls de camp |
| `pl situació.pdf` | pdf 1 pàg | situation_plan | annex de l'Eva: **Fig 3 n'és el retall** (planta amb punts) i conté la Fig 2 |
| `tall.pdf` | pdf 1 pàg | correlation_section | **INFORME: Fig 6** (retall) |
| `FH11→4001671_corte de correlación.pdf` | fh11_pdf 1 pàg | — | render FH11: annex: la Fig 6 n'és el retall |
| `FH11→4001671_fotografías.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: la seva selecció de fotos (4 pàg) |
| `FH11→4001671_plano de situación.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: idem |
| `FH11→6_mapa Geol_CAT_ - CAST.pdf` | fh11_pdf 1 pàg | — | render FH11: original FreeHand del geològic (= F4) |

### 5.7 anciles

| fitxer | tipus | rol (file_mapping) | ús segons el signat |
|---|---|---|---|
| `24.0807/A01_TIPOL.pdf` | pdf 1 pàg | — | **INFORME: Fig 3** (plantes + tipologies), a ull |
| `24.0807/IV_PLANOS.pdf` | pdf 35 pàg | architect_plan | projecte de l'arquitecte (35 pàg): **p5 = Fig 2 (topogràfic)**, p9 = Fig 3 (= A01_TIPOL); p1 = portada (la que posem nosaltres: error); p28-35 fotos/renders no usats |
| `24.0807/PRESUPUESTO GEOTEC.ANCILES.pdf` | pdf_skip 7 pàg | — | auxiliar: pressupost |
| `24.0807/SITE_prop A.pdf` | pdf 1 pàg | — | plànol de situació de l'arquitecte (parcel·la vermella): no usat directament |
| `ACCEPTACIO/PRESUPUESTO G3.ANCILES.pdf` | pdf_skip 7 pàg | — | auxiliar: pressupost |
| `ANEJOS/4001679_corte de correlación.FH11` | fh11 | — | annex: la Fig 7 n'és el retall |
| `ANEJOS/4001679_fotografías.FH11` | fh11 | — | annex de l'Eva: la seva selecció de fotos |
| `ANEJOS/4001679_plano de situación.FH11` | fh11 | — | annex de l'Eva: idem (versió V0) |
| `ANEJOS/4001679_sondeos.FH11` | fh11 | — | annex de l'Eva: registre + fotos (font indirecta); l'únic PDF és V0 |
| `FOTOGRAFIES/DETALL SPT1 S1.jpeg` | foto | photo_spt_sample | detall de cullera no usat (el posem nosaltres com a materials) |
| `FOTOGRAFIES/DETALL SPT1 S2.jpeg` | foto | — | detall de cullera no usat |
| `FOTOGRAFIES/EMPL S1.jpeg` | foto | photo_sondeig_equipment | foto de màquina de sondeig no usada |
| `FOTOGRAFIES/EMPL S2.jpeg` | foto | — | **INFORME: Foto 2** (màquina de sondeig) |
| `FOTOGRAFIES/P1.jpeg` | foto | photo_test_point | **INFORME: Foto 1** (màquina DPSH) |
| `FOTOGRAFIES/P2.jpeg` | foto | — | foto de màquina no usada |
| `FOTOGRAFIES/P3.jpeg` | foto | — | foto de màquina no usada |
| `FOTOGRAFIES/P4.jpeg` | foto | — | foto de màquina no usada |
| `FOTOGRAFIES/S1.jpeg` | foto | — | **INFORME: Foto 3** (caixa S-1); nosaltres la posem com a màquina de sondeig (error) |
| `FOTOGRAFIES/S2.jpeg` | foto | — | caixa S-2 (variant) no usada |
| `FOTOGRAFIES/S2_0-3.jpeg` | foto | — | **INFORME: Foto 4** (caixa S-2) |
| `FOTOGRAFIES/SPT1 S1.jpeg` | foto | — | cullera S-1 no usada |
| `FOTOGRAFIES/SPT1 S2.jpeg` | foto | — | cullera S-2 no usada |
| `FOTOGRAFIES/WhatsApp Image 2026-02-19 at 12.16.31.jpeg` | foto | field_photo | auxiliar: foto del full de camp |
| `FOTOGRAFIES/WhatsApp Image 2026-02-19 at 16.35.43.jpeg` | foto | — | auxiliar: foto del full de camp |
| `PDF_V0/4001679_informe_V0.pdf` | pdf_skip 49 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF_V0/ANEJOS/4001679_DPSH.pdf` | pdf_aux 6 pàg | — | auxiliar: annex DPSH (taules) |
| `PDF_V0/ANEJOS/4001679_corte de correlación.pdf` | pdf_v0 1 pàg | — | annex: la Fig 7 n'és el retall |
| `PDF_V0/ANEJOS/4001679_fotografías.pdf` | pdf_v0 2 pàg | — | annex de l'Eva: la seva selecció de fotos |
| `PDF_V0/ANEJOS/4001679_plano de situación.pdf` | pdf_v0 1 pàg | — | annex de l'Eva: idem (versió V0) |
| `PDF_V0/ANEJOS/4001679_sondeos.pdf` | pdf_v0 4 pàg | sondeig_annex | annex de l'Eva: registre + fotos (font indirecta); l'únic PDF és V0 |
| `PDF_V0/LETRA/4001679_informe_V0.pdf` | pdf_skip 26 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PDF_V0/LETRA/4001679_portada_V0.pdf` | pdf_skip 1 pàg | — | auxiliar (informe/pressupost/laboratori: text) |
| `PENETROS + SONDEIGS.pdf` | pdf 7 pàg | dpsh_field_sheet, sondeig_field_sheet | auxiliar: fotos dels fulls de camp + croquis |
| `pl situ.pdf` | pdf 1 pàg | situation_plan | annex de l'Eva: **Fig 4 n'és el retall** (planta amb punts); mapes de la Fig 1 apilats |
| `tall.pdf` | pdf 1 pàg | correlation_section | **INFORME: Fig 7** (retall) |
| `FH11→4001679_corte de correlación.pdf` | fh11_pdf 1 pàg | — | render FH11: annex: la Fig 7 n'és el retall |
| `FH11→4001679_fotografías.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: la seva selecció de fotos |
| `FH11→4001679_plano de situación.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: idem (versió V0) |
| `FH11→4001679_sondeos.pdf` | fh11_pdf 1 pàg | — | render FH11: annex de l'Eva: registre + fotos (font indirecta); l'únic PDF és V0 |

## 6. Resum per tipus de figura: què hem après als 7

Per a cada tipus: què fa l'Eva (evidència als 7), on és la font dins el projecte, què posem avui (bloc 4b) i el forat.

### 6.1 `fig_situacio` — «Situació de la zona d'estudi» (7/7)

- **Eva**: sempre una composició de DOS mapes costat a costat: topogràfic ICGC del municipi (zona en taronja o punt) + ortofoto o topogràfic ampliat amb
  el rectangle de la parcel·la. Excepcions: Bell-lloc (dues imatges separades, cadastral + orto, retallades dels insets de l'`A.01.pdf` de l'arquitecte,
  «Font: Projecte»); Anciles (Aragó: la font és la Sede del Catastro, no l'ICGC); Linyola (mapa del municipi + cadastral ampliat, línia vermella).
- **Font al projecte**: PNG ja compost a `ANNEXES/ALTRES|OTROS` (Castellar `m7.png`, Rubí `F1 UBI.png`, Vilanova `F1 SIT.png`: hash idèntic 1,00);
  peces ICGC (`M1…M4.png`); insets del plànol de l'arquitecte (Bell-lloc, NCC 0,75 amb pic singular); inset de l'annex «plànol de situació» (Linyola,
  0,82 sobre el render del FH11). A Alcoletge i Anciles no en queda cap PNG: la figura només viu dins el FH11 de l'annex (allà els dos mapes van apilats,
  no costat a costat: la figura de l'informe és una segona composició).
- **Avui**: retall del 38 % esquerre de l'annex de situació (`_render_situation_plan_left`). A l'A3 dona la columna de dos mapes apilats (no la composició
  de l'Eva); a l'A4 (Linyola) una tira il·legible. Mai coincideix amb el signat.
- **Forat**: no tenim ni les peces (captures ICGC per UTM les sabem baixar: `_download_icgc_images`) ni la regla de composició (dos mapes costat a costat,
  llegenda «Zona d'estudi», taronja). L'annex FH11 de situació és la font més estable (existeix abans del wizard) però cal RETALLAR-ne els dos mapes i
  recompondre'ls en horitzontal.

### 6.2 `fig_aerea` — la ranura de la plantilla que no existeix

- **Eva**: cap dels 7 signats té una figura «ortofoto» a part. L'ortofoto va dins la de situació (§6.1) o dins la d'assaigs (§6.3).
- **Avui**: `fig_aerea_image` = ortofoto ICGC + polígon cadastral, per UTM (pendent a Rubí, Vilanova, Anciles sense UTM a la via A). Imprimeix una figura
  que l'Eva no posa, i la numeració se'n ressent (bloc 4: 10 X).
- **Forat**: és una decisió de plantilla (pas 2): eliminar la ranura o reutilitzar-la com a segona imatge de la composició de situació (com Bell-lloc).

### 6.3 `fig_assaigs` — «…i els assaigs realitzats» (6/7; Bell-lloc no)

- **Eva**: la figura clau del capítol 2.2: el plànol de l'arquitecte (Linyola, Alcoletge, Vilanova, Anciles) o l'ortofoto ampliada (Castellar, Rubí) amb
  els punts d'assaig dibuixats per ella (DPSH en blau, sondeig en vermell, llegenda i escala). Linyola els porta com a icones petites sense etiqueta.
  Bell-lloc no en té cap (només l'emplaçament sense punts, i això és el que la memòria `report_figure_sources` va generalitzar).
- **Font al projecte**: el mateix dibuix és el plànol de l'annex «plànol de situació» (`pl situ.pdf` / `PDF/ANNEXES/*plànol de situació.pdf` / FH11):
  Alcoletge NCC 0,88 amb l'annex; els PNG compostos a Castellar (`m8.png`, 1,00) i Rubí (`F2 UBI PUNTS.png`). Vilanova té `F2 PUNTS.png` (orto amb punts)
  però el signat porta la PLANTA amb punts: l'Eva va canviar de suport. Bell-lloc té `A.01 amb punts.pdf` i no el fa servir a l'informe.
- **Avui**: `fig_main_plan_image` = pàgina sencera de l'`A.01.pdf` (rol `architect_plan`) sense punts; a Rubí una foto d'un plànol imprès; a Anciles la
  portada d'`IV_PLANOS.pdf`; pendent a Castellar i Vilanova (cap rol).
- **Forat**: l'única font amb punts és l'annex de l'Eva (o els seus PNG). Els punts els dibuixa ella al FreeHand; nosaltres podríem (a) retallar el plànol
  amb punts de l'annex (existeix abans del wizard: memòria `eva_workflow_annexes_before_wizard`), o (b) dibuixar-los sobre el plànol de l'arquitecte
  amb els UTM (georeferència del plànol: difícil, i l'MCP plànols hi pot ajudar).

### 6.4 `fig_projecte` — «Font: Projecte» (0-2 per informe)

- **Eva**: figures opcionals tretes del projecte de l'arquitecte: secció/perfil (Linyola), planta d'emplaçament sense punts (Bell-lloc, Vilanova),
  topogràfic de la parcel·la i plantes+tipologies (Anciles). No hi ha regla fixa: depèn del que l'arquitecte hagi enviat i de què ajudi a entendre l'obra.
- **Font**: pàgines concretes del projecte (`2_02B_DG_Silvia_Jaume.pdf` p9-11 a Linyola; `1.0.pdf` a Vilanova; `IV_PLANOS.pdf` p5 i `A01_TIPOL.pdf` a
  Anciles; `A.01.pdf` a Bell-lloc), retallades al dibuix (sense caixetí).
- **Avui**: no existeix com a ranura pròpia (la nostra Figura 3 és l'`A.01` sencer). El nombre de figures del projecte (2/3/4) depèn d'això.
- **Forat**: és el cas més clar de «Claude mira i tria»: cal reconèixer quina pàgina és la secció, quina la planta d'emplaçament, i retallar-la.

### 6.5 `foto_vista` — vistes generals (0-2)

- **Eva**: 0 a Castellar, Linyola, Alcoletge, Anciles; 1 a Rubí (Google Earth, vista de carrer) i Vilanova (foto de camp retallada); 2 a Bell-lloc (fotos
  de camp). Font: fotos de camp de `FOTOGRAFIES/` o Google Earth (fora del projecte).
- **Avui**: només via `photo_selection.json` amb `source=user` (Bell-lloc); la via A no en tria.
- **Forat**: criteri (pregunta 19a oberta) i tria: quan hi ha fotos del solar sense màquina, l'Eva en posa 1-2; l'annex de fotografies FH11 és la seva
  selecció (Bell-lloc: «Fotografies 3 i 4: vista general de la parcel·la»).

### 6.6 `foto_dpsh`, `foto_sondeig` — la màquina (7/7 i 3/7)

- **Eva**: una foto de la màquina DPSH sempre; del sondeig quan n'hi ha (Castellar, Bell-lloc, Anciles). Són fotos de `FOTOGRAFIES/` (P1-P4, S1/…).
- **Font**: l'annex de fotografies (`*_fotografies.pdf` / `.FH11`) porta les mateixes fotos amb peu: és la seva selecció, i existeix abans del wizard.
- **Avui**: tria heurística+LLM (`select_photos_ai`): encerta 5/7 al DPSH; falla a Alcoletge (full de camp `PENETROS.jpeg` com a màquina) i Anciles
  (caixes de testimonis com a màquina de sondeig).
- **Forat**: amb Claude mirant les fotos (i l'annex de fotografies com a pista), la tria és trivial.

### 6.7 `foto_materials` — materials (1 per informe, 2 a Vilanova/Anciles)

- **Eva**: UNA foto de materials (cullera SPT oberta o caixa de testimonis), o una per sondeig/punt quan n'hi ha diversos (Anciles S-1/S-2; Vilanova
  SPT P-3 i P-1). Mai una per nivell.
- **Avui**: la plantilla repeteix la mateixa foto per nivell amb el mateix número (p254-262); fotos correctes quan la tria ho és.
- **Forat**: plantilla (decisió del Josep pendent del bloc 4) + tria per punt quan hi ha diverses mostres.

### 6.8 `fig_geologic` — mapa geològic (7/7)

- **Eva**: retall del mapa geològic ICGC 1:50.000 (1:25.000 a Castellar) centrat a la parcel·la; amb llegenda composta a Castellar, Rubí, Vilanova
  (PNG `m12 mgeol`, `F4 MGEOL`), sense llegenda i amb punt vermell / «Zona d'estudi» a Linyola, Bell-lloc, Alcoletge; IGME 1:1.000.000 a Anciles (Aragó).
- **Font**: PNG a ALTRES quan hi és; si no, només dins el FH11 «6_mapa Geologic» (Castellar, Rubí, Vilanova) o enlloc (retall fet i no desat).
- **Avui**: ICGC WMS per UTM amb punt vermell: el mateix tipus de figura que l'Eva a Linyola/Bell-lloc/Alcoletge; pendent sense UTM (Rubí, Vilanova, Anciles).
- **Forat**: preferir el PNG de l'Eva si existeix (`F4 MGEOL.png` a Vilanova surt pendent avui); fora de Catalunya cal l'IGME (o el seu PNG); llegenda.

### 6.9 `fig_tall` — tall de correlació (7/7)

- **Eva**: retall del tall (només la secció amb cotes i punts, sense llegenda ni caixetí) de l'annex `tall.pdf`. 7/7 igual.
- **Avui**: pàgina sencera de `tall.pdf` (cau per contingut arreglada al bloc 4). Mateixa font, retall diferent (hash: Castellar 0,95 a escala 0,82).
- **Forat**: retallar la secció (l'MCP plànols o una detecció del rectangle del dibuix); el número de figura depèn de les anteriors.

### 6.10 Extres que no són ranures

- Castellar: Fig 6 i 7 d'estabilitat de vessant (Hoek & Bray, escanejat d'un llibre, `.wmf`) al capítol 4.5: només quan hi ha vessant.
- Rubí: gràfic de granulometria (pastís) quan hi ha assaig granulomètric (§2: risc a la plantilla).
- Anciles: signatura manuscrita a «4.4 Empuje de tierras» (és una signatura, no una figura; el bloc 4 la comptava com a «empentes»).
- Cullera SPT: estàtica, 7/7, la posa el generador.

## 7. Preparació del pas 2: opcions A/B/C per tipus i preguntes candidates a l'Eva

> **Pas 2 fet (2026-09-07, tarda-3, amb el Josep):** decisions D0-D14 al DECISION-LOG `2026-09-07 (tarda-3)`; les preguntes 30-34 i 36 són al registre `PREGUNTES-EVA-PENDENTS.md` (la 35 dins la 19a). Aquesta secció queda com a evidència de partida.

Opcions per tipus: **(A)** reutilitzar el que l'Eva ja fa abans del wizard (annexos FH11/PDF, PNG d'ALTRES); **(B)** compondre nosaltres (ICGC/Cadastre
per UTM + retalls del projecte + punts); **(C)** demanar-ho a l'Eva (criteri o fitxer). La recomanació és la que surt de l'evidència del pas 1; la decisió
és del Josep i de l'Eva.

| tipus | A (annexos / PNG de l'Eva) | B (compondre) | C (Eva) | recomanació |
|---|---|---|---|---|
| `fig_situacio` | retallar els dos mapes de l'annex de situació (FH11 → PDF; existeix sempre) i posar-los costat a costat; si hi ha PNG a ALTRES, usar-lo tal qual | ICGC topo + orto per UTM amb rectangle taronja i llegenda «Zona d'estudi» (ja baixem les dues capes) | quina composició vol per defecte (topo+orto? cadastral?) i per a Aragó | **A amb B de reserva** (sense UTM a la via A, A és l'única) |
| `fig_aerea` | — | — | confirmar que no vol figura d'ortofoto a part | **eliminar la ranura** o fer-la la 2a imatge de situació |
| `fig_assaigs` | retallar el plànol amb punts de l'annex de situació (el dibuixa ella abans del wizard) | plànol de l'arquitecte + punts per UTM (georeferència: difícil; MCP plànols?) | confirmar que la figura del capítol 2.2 ha de dur els punts (6/7 sí) i si vol el suport orto o planta | **A** (B només si l'annex no hi és) |
| `fig_projecte` | pàgina del projecte de l'arquitecte retallada al dibuix (secció, emplaçament, tipologies) | — | quin criteri: quan posa secció/tipologies? | **Claude tria** (mira les pàgines) amb el criteri de l'Eva |
| `foto_vista` | l'annex de fotografies com a selecció | tria entre `FOTOGRAFIES/` | criteri (pregunta 19a) | **A + Claude** |
| `foto_dpsh` / `foto_sondeig` | annex de fotografies (peu «màquina…») | tria visual | — | **Claude mira** (tria trivial) |
| `foto_materials` | annex de fotografies / annex de sondeig (fotos de caixes) | una per informe, o una per sondeig/punt | quan en posa dues (Vilanova P-3 i P-1) | **plantilla: una** (decisió Josep) + Claude |
| `fig_geologic` | PNG `*MGEOL*.png` si hi és; FH11 «6_mapa Geologic» | ICGC WMS per UTM (ja fet) + llegenda; IGME fora de Catalunya | llegenda sí/no; Aragó | **B amb A prioritari si hi ha PNG** |
| `fig_tall` | retall de la secció de `tall.pdf` | — | — | **A** (retall) |

**Preguntes candidates a l'Eva** (per afegir a `docs/PREGUNTES-EVA-PENDENTS.md` després de la revisió del pas 2; l'última és la 29):

- **30 (situació):** «A la Figura 1 poses dos mapes costat a costat (topogràfic ICGC + ortofoto o topogràfic ampliat) amb la zona en taronja. És sempre
  així? Quan uses el cadastral (Bell-lloc) o la Sede del Catastro (Anciles) és perquè no tens ICGC o per un altre motiu?» Evidència: 7 signats, `m7.png`,
  `F1 UBI.png`, `F1 SIT.png`.
- **31 (assaigs):** «La figura del capítol 2.2 porta els punts d'assaig dibuixats (6 de 7). A Bell-lloc no (i tens `A.01 amb punts.pdf`). Vols sempre els
  punts? Prefereixes el plànol de l'arquitecte o l'ortofoto com a fons?» Evidència: Castellar/Rubí orto, Linyola/Alcoletge/Vilanova/Anciles planta.
- **32 (projecte):** «Quan afegeixes figures del projecte (secció a Linyola, topogràfic i tipologies a Anciles, emplaçament a Bell-lloc/Vilanova)? Hi ha
  regla o depèn del que envia l'arquitecte?»
- **33 (materials):** «Una foto de materials per informe, o una per sondeig/punt (Anciles S-1/S-2, Vilanova P-3 i P-1)? Mai per nivell?»
- **34 (geològic):** «Llegenda al mapa geològic: sí (Castellar, Rubí, Vilanova) o no (Linyola, Bell-lloc, Alcoletge)? Fora de Catalunya, IGME 1:1.000.000?»
- **35 (vistes generals):** reprèn la 19a amb l'evidència (0/1/2 fotos; Google Earth a Rubí).
- **36 (PNG d'ALTRES):** «A Castellar, Rubí i Vilanova deixes les figures a `ANNEXES/ALTRES` (`F1 UBI.png`…). Ho fas sempre? Si ho fessis sempre, les podríem
  agafar tal qual.» (La resposta canvia A per a 3 tipus.)

## 8. Direcció del pas 3 (només disseny; res implementat)

**Principi (Josep, 2026-09-07):** el pipeline el controla Claude Code, que pot obrir, mirar i interpretar les imatges tenint al cap les que volem a l'informe.
Per tant el pas 3 NO és una heurística nova a `image_manager.py`: és un lector d'imatges (skill) + eines deterministes de render/retall/composició.

1. **Lector d'imatges (Claude Code, skill G3DT)**. Entrada: l'inventari del projecte (fotos, pàgines de PDF, FH11 renderitzats, PNG d'ALTRES) com a fulls de
   contacte + les pàgines a mida real quan cal. Sortida: per a cada ranura de l'informe, la font triada (fitxer, pàgina, rectangle de retall en coordenades
   de la pàgina, o «composició de X i Y») amb la raó en una frase i una confiança; o «no hi ha font al projecte» (mai inventar). Format: JSON per ranura,
   igual que els candidats del nivell A (font + cita).
2. **Llibreria d'exemplars** (proposta del Josep): `docs/imatges/veritat/` ja és aquesta llibreria: per ranura, les 7 figures de l'Eva amb peu, mides i
   procedència. Cal afegir-hi una **descripció textual** per exemplar (què s'hi veu, què hi ha marcat, com està compost) i el criteri quan es conegui (pas 2).
   Al lector se li passen els exemplars de la ranura (imatge + text) com a exemples: «tria/retalla com aquests». **Mai** s'insereixen a l'informe d'un
   projecte nou. **Test:** leave-one-out, la llibreria va indexada per projecte i el lector rep `--exclude <projecte>`; 7 plecs amb els 7 signats. Tulipa
   (8è projecte, sense signat als 7) no serveix de veritat però sí de prova a ull. Cautela: depurar els exemplars amb el criteri de l'Eva perquè no
   ensenyin excepcions com a regla (Bell-lloc sense punts; fotos renombrades de Castellar, que són artefacte nostre).
3. **Eines deterministes (Python)**: renderitzar pàgina (fitz), retallar un rectangle, compondre dues imatges costat a costat amb llegenda, baixar capes ICGC
   per UTM (ja existeix), dibuixar punts sobre un plànol georeferenciat (**MCP plànols**: comprovar si ja retalla/extreu de plànols abans de fer res nou).
   El `.FH11` es converteix amb soffice (3-14 s) i es cacheja per md5 com les imatges (`_cache_name`).
4. **Mesura per figura** a M341: «mateixa font que l'Eva» (phash ≤ 10 o NCC ≥ 0,7 contra la veritat), no només presència; numeració que segueix les figures
   presents; `photo_materials` una vegada. Mesurar abans i després amb el codi quiet (`feedback_measure_baseline_before_coding`); pèrdues al
   `REGISTRE-PERDUES-MESURA.md`; DECISION-LOG per bloc.
5. **Ordre proposat** (cada peça mesurable sola): (i) fotos (DPSH/sondeig/materials/vistes) amb el lector + annex de fotografies com a pista → tanca 4 X
   d'imatges errònies i les vistes generals; (ii) tall retallat; (iii) assaigs des de l'annex de situació (retall del plànol amb punts); (iv) situació:
   PNG d'ALTRES → retall+composició de l'annex → ICGC per UTM; (v) geològic: PNG → ICGC → IGME; (vi) projecte (secció/emplaçament) i nombre de figures
   variable a la plantilla; (vii) treure `fig_aerea` i el pastís de Rubí de la plantilla.
6. **Cost**: el lector mira 25-75 imatges per projecte (fulls de contacte de 20 a ~100 KB cadascun + 3-6 pàgines a mida real) = una crida de visió per
   projecte, no per fitxer. Tot el render és local.

## 9. Fitxers produïts i com reproduir

| Què | On | Al repo? |
|---|---|---|
| Veritat: índex per projecte (ordre, media, md5, mides, phash, ranura, peu, secció, `static_of`) | `docs/imatges/veritat/<slug>/index.json` (7) | sí |
| Veritat: imatges a mida real (63 de projecte + estàtiques; el `.wmf` de Castellar també en `.png`) | `~/g3dt-e2e/imatges/veritat/<slug>/NN_<ranura>_<peu>.<ext>` | no (2-7 MB per projecte; es regenera amb el script) |
| Fulls a tres columnes (Eva · nosaltres · candidats amb hash) | `docs/imatges/fulls/<slug>.jpg` (7) | sí |
| Notes visuals de Claude (esborrany) | `docs/imatges/notes-visuals-2026-09-07.md` | sí |
| Signats convertits a `.docx`, renders de candidats (291 PNG a 80 dpi), FH11→PDF (27), aparellament (`match/<slug>.json`), nostres (bloc 4b) | scratchpad de la sessió (`/tmp/claude-1000/…/a25f4f53…/scratchpad/`): `signats-docx/`, `cands/`, `fh11/`, `match/`, `nostres/`, `view/` | no |
| Scripts: `truth_extract.py`, `inventory.py`, `match.py`, `ours_extract.py`, `sheets.py`, `build_sheets.py`, `build_tables.py` | `docs/imatges/scripts/` (copiats del scratchpad; camins absoluts del scratchpad a dins, a parametritzar si es reutilitzen) | sí |

Reproduir (ordre): signats → docx (`soffice --headless --convert-to docx`), `truth_extract.py <docx> <out_full> docs/imatges/veritat`, FH11 → PDF
(`fh11_convert.sh`), `inventory.py`, `match.py` (≈ 7 min, 7 processos), `ours_extract.py`, `build_sheets.py`, `build_tables.py` (taules base de §4 i §5).
La columna «lectura visual» de §4 i el mapa curat de §5 són text escrit a mà per Claude a partir dels fulls de contacte (no hi ha script: el document és
la font). Cap crida a cap API: tot determinista (hash, render) llevat de la lectura visual de Claude.

Fora d'abast d'aquest pas (no fet, a posta): cap canvi a `automation/`, a la plantilla ni a M341; cap pregunta enviada a l'Eva; `PREGUNTES-EVA-PENDENTS.md`
no tocat (les 30-36 són candidates a §7); cap commit.
