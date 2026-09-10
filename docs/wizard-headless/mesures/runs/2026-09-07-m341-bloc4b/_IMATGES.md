# Full de control visual de les imatges — run `2026-09-07-m341-bloc4b` (bloc 4, 2026-09-07)

Fet UNA vegada a mà (PLA §Bloc 4) sobre els 7 `.docx` de `~/g3dt-e2e/informes-mesura/2026-09-07-m341-bloc4b/` (variant `viaA`).
Els fulls (`imatges/<projecte>.jpg`) posen cada imatge del `.docx` al costat del peu que la segueix, en ordre de document; els
requadres vermells «(sense imatge davant)» als peus de TAULA són normals (les taules no porten imatge). Script: temporal de la sessió
(`sheet.py`: `document.xml` → `a:blip r:embed` → `word/media/*`, peu = següent paràgraf «Figura/Fotografia/Taula N.»).

Tres columnes per forat: **hi és** (test de presència de M341: present / pendent / absent), **és la correcta** (a ull, contra el que
l'Eva posa als signats i la memòria `report_figure_sources`), **retall i mida**.

## Abans i després de la cau per contingut (mateixa sessió)

La cau global d'imatges (`~/.g3dt/cache/images/`, `G3DT_CACHE_DIR`) tenia la clau pel NOM del PDF (`tall_tall.jpg`,
`planol_A.01.jpg`, `cadastre_sitplan_pl situ.jpg`). Al run `-bloc4-num` (abans d'arreglar-ho), per md5 dels `word/media/*`:

| Imatge compartida | Projectes que la duien | Amo real |
|---|---|---|
| Tall de correlació (`tall.pdf` → `tall_tall.jpg`) | Castellar, Linyola, Alcoletge, Vilanova, Anciles **i** Bell-lloc (6 de 7; Rubí no té `tall.pdf`) | Bell-lloc (el primer que el va renderitzar) |
| Plànol A.01 (`planol_A.01.jpg`) | Alcoletge i Bell-lloc | Bell-lloc |
| Retall de situació (`cadastre_sitplan_pl situ.jpg`) | Anciles i Linyola | Linyola |

Al run `-bloc4b` (clau `<prefix>_<nom>_<md5 del PDF>.jpg`): **cap duplicat entre projectes**; els escalars, la narrativa i les 11
taules són idèntics cel·la a cel·la a `-bloc4-num`. `production/g3dt-eva-v1` porta el MATEIX codi (6 punts amb `.stem`): a
l'ordinador de l'Eva, dos projectes amb `tall.pdf` o `A.01.pdf` (noms habituals seus) comparteixen imatge fins que s'hi porti
l'arranjament.

## Per projecte (després de l'arranjament)

Llegenda: ✅ present i correcta · ⚠️ present però NO és la que toca · ✂️ present, retall/mida dolents · ⏳ pendent · — absent (no
s'imprimeix: vistes generals no triades, sondeig que no hi ha).

| Forat | Castellar | Rubí | Bell-lloc | Linyola | Alcoletge | Vilanova | Anciles |
|---|---|---|---|---|---|---|---|
| `fig_cadastre_image` (retall esquerre del plànol de situació) | ✅ | ✅ | ✅ | ✂️ tira de 629×2339 px, il·legible | ✅ | ✅ | ✅ (abans era la de Linyola) |
| `fig_aerea_image` (ortofoto ICGC + parcel·la) | ✅ | ⏳ sense UTM | ✅ | ✅ | ✅ | ⏳ sense UTM | ⏳ sense UTM |
| `fig_main_plan_image` (plànol de l'arquitecte) | ⏳ sense rol `architect_plan` | ⚠️ foto d'un plànol imprès damunt una taula (`IMG-…-WA0015.jpg`) | ✅ A.01 pàgina sencera | ✅ | ✅ (abans era l'A.01 de Bell-lloc) | ⏳ sense rol | ⚠️ portada «IV. DOCUMENTACIÓN GRÁFICA» d'`IV_PLANOS.pdf` (pàgina 1, no la del plànol) |
| `fig_spt_cullera_image` (estàtica) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `fig_geological_image` (ICGC) | ✅ | ⏳ sense UTM | ✅ | ✅ | ✅ | ⏳ sense UTM (té `F4 MGEOL.png` al projecte, no s'usa) | ⏳ sense UTM |
| `fig_correlation_image` (`tall.pdf`) | ✅ (abans el de Bell-lloc) | ✅ (propi, png) | ✅ | ✅ (abans el de Bell-lloc) | ✅ (abans el de Bell-lloc) | ✅ (abans el de Bell-lloc) | ✅ (abans el de Bell-lloc) |
| `photo_site_image_1/2` (vistes generals) | — | — (el signat en té 1: Google Earth) | ✅ ✅ | — | — | — | — |
| `photo_dpsh_image` (màquina DPSH) | ✅ | ✅ | ✅ | ✅ | ⚠️ foto del FULL DE CAMP manuscrit, no de la màquina | ✅ | ✅ |
| `photo_sondeig_image` (màquina del sondeig) | ✅ | — | ✅ | — | — | — | ⚠️ caixes de testimonis (això és «materials»), no la màquina |
| `photo_materials_image` (materials del nivell) | ✅ (1 nivell) | ✅ ×2 | ✅ (1 nivell) | ✅ ×2 | ✅ ×2 | ✅ ×2 | ✅ ×2 (mostra en bossa) |

**×2 = la MATEIXA foto amb el MATEIX número dues vegades**: la plantilla imprimeix `{{ photo_materials_image }}` + «Fotografia
{{ photo_materials_num }}. Detall dels materials del {{ level.ordinal }} nivell.» dins de `{%p for level in soil_levels %}` (p254-262);
amb 2 nivells surten dues «Fotografia 2» idèntiques. Als signats: una sola foto de materials (Rubí, Bell-lloc, Linyola, Alcoletge,
Castellar), o una per SONDEIG (Anciles: Fotografía 3 S-1, Fotografía 4 S-2), mai una per nivell. Decisió del Josep (plantilla).

## Test de presència (M341, taula «Imatges» de `_AGREGAT-341.md`)

| projecte | present | pendent | absent | pendents |
|---|--:|--:|--:|---|
| castellar | 8 | 1 | 2 | `fig_main_plan_image` |
| rubi | 6 | 2 | 3 | `fig_aerea_image`, `fig_geological_image` |
| bell-lloc | 11 | 0 | 0 | — |
| linyola | 8 | 0 | 3 | — |
| alcoletge | 8 | 0 | 3 | — |
| vilanova | 5 | 3 | 3 | `fig_aerea_image`, `fig_main_plan_image`, `fig_geological_image` |
| anciles | 7 | 2 | 2 | `fig_aerea_image`, `fig_geological_image` |

Els 8 pendents tenen dues causes, totes d'ENTRADA: 6 = `image_manager._download_icgc_images` sense `utm_x/utm_y` a `user_data`
(Rubí, Vilanova, Anciles: la via A no els porta), 2 = cap rol `architect_plan` a `file_mapping.json` (Castellar, Vilanova).

## Què queda obert (no són cel·les de M341)

1. Retall del plànol de situació a Linyola: `_render_situation_plan_left` talla el 38 % esquerre pensant en l'A3 apaïsat de la
   plantilla FreeHand (1191×842 pt: Castellar, Bell-lloc); el de Linyola és A4 apaïsat (842×595 pt) amb una altra maquetació i el
   retall surt una tira de 629×2339 px.
2. Tria de fotos: Alcoletge «màquina DPSH» = full de camp; Anciles «màquina del sondeig» = caixes de testimonis; Rubí «plànol» =
   foto d'un paper. Tot surt de la classificació de `image_manager` (Groq/Claude/heurística de nom).
3. Pàgina del plànol: Anciles `IV_PLANOS.pdf` és multipàgina i es renderitza la 1 (portada); cal la pàgina del plànol (la lectura la sap).
4. Foto de materials per nivell amb el mateix número (plantilla).
5. UTM a la via A per a Rubí/Vilanova/Anciles (ortofoto + geològic) i rol `architect_plan` a Castellar/Vilanova.
