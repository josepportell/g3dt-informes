# Anàlisi de les discrepàncies d'imatges — per què l'Eva hi posa el que hi posa i per què nosaltres no ho obtenim

**Data:** 2026-09-09. **Petició del Josep:** raonar cada discrepància (sobretot les X, però també les ND i les C), saber
si tenim la imatge, d'on la treu l'Eva, si triem una de diferent o la retallem diferent, i trobar si hi ha manera de
resoldre-ho més vegades, al cost que sigui (temps d'anàlisi, tokens, llibreries, FH11, catàleg d'imatges…).
**Base:** run `2026-09-09-m341-peca7b` (skill neutre), inventari del pas 1 (`INVENTARI-I-VERITAT-2026-09-07.md` §4:
291 candidats per hash i lectura visual, FH11 inclosos), i les seleccions dels lectors de fotos i figures.

## 0. Resum

56 figures i fotos als 7 signats: **29 M · 4 C · 15 X · 8 ND**. Les **27 discrepàncies** (C + X + ND), per on és la
font de l'Eva:

| on és la font de l'Eva | n | què passa | es pot arreglar? |
|---|--:|---|---|
| **A. La imatge EXACTA és a la carpeta** (phash ≤ 2) i no la posem | 9 | triem una altra d'equivalent (5), el lector no la mira (1), la plantilla només n'imprimeix una (2), l'Eva la retalla (1) | **sí, en bona part**: wizard (tria entre equivalents), plantilla (una foto per punt), ampliar l'abast del lector (ALTRES) |
| **B. La mateixa font és a la carpeta i el retall o la tria és diferent** | 13 | tall (4 C), retalls de situació/assaigs (3), figures del projecte (4), classificació de ranura (2) | **parcialment**: estudiar el retall del tall (4 C → M possibles), candidats al wizard, preguntes 30-32 |
| **C. La font NO és a la carpeta** (visor ICGC/IGME o dibuix seu no desat) | 5 | mapa geològic ×4 (retall del visor no desat), assaigs de Linyola (planta acolorida amb icones dibuixades per ella) | **només amb l'Eva**: que desi el retall a `ALTRES` (ja ho fa a 3 de 7 amb el geològic i les encertem totes) o pregunta 34 per reproduir la vista |

**22 de 27 discrepàncies tenen la font a la carpeta.** El coll d'ampolla no és trobar imatges: és (1) empats entre
fotos equivalents que l'Eva resol sense cap regla, (2) la plantilla que imprimeix una foto on ella en posa dues, (3)
el retall, i (4) el judici sobre quina figura del projecte. Només 5 casos necessiten alguna cosa que no tenim.

## 1. Per projecte, figura per figura

Columnes: **Eva** = la figura del signat i d'on surt (inventari pas 1, phash contra tots els fitxers de la carpeta,
FH11 convertits inclosos); **nosaltres** = el que imprimim; **causa** (A/B/C del resum); **remei** i cost.

### 1.1 Castellar (5 M · 1 C · 1 X · 0 ND → 86 %)

| figura | Eva | nosaltres | estat | causa | remei |
|---|---|---|---|---|---|
| Fig 1 situació | `ALTRES/m7.png` (composició seva) | el mateix PNG | M | | |
| Fig 2 assaigs | `ALTRES/m8.png` (orto amb punts) | retall del full de situació = m8 | M | | |
| Foto 1 DPSH | `P4.jpg` (= `DPSH/maquina_dpsh_3.jpg`), l'ÚLTIMA de l'annex de fotografies | `P1.jpg` (la primera de l'annex) | **X** | A: empat entre 4 fotos equivalents de la màquina, una per punt; l'annex en porta 4 | pregunta 37; **wizard: tria en un clic entre les fotos de l'annex** (totes vàlides) |
| Foto 2 sondeig | `maquina_sondeig` | igual | M | | |
| Fig 4 geològic | `ALTRES/m12 mgeol.png` | el mateix PNG | M | | |
| Foto 4 materials | caixa S-1 | igual | M | | |
| Fig 5 tall | retall de `tall.pdf`, **la nostra dins la seva** (ncc 0,96) | retall del dibuix | **C** | B: ella inclou una mica més que nosaltres (marc/cotes fora del farciment) | estudiar els 4 C del tall junts (§2.4) |

### 1.2 Rubí (4 M · 1 C · 1 X · 1 ND → 83 %)

| figura | Eva | nosaltres | estat | causa | remei |
|---|---|---|---|---|---|
| Fig 1 situació | `Altres/F1 UBI.png` | el mateix PNG (rol + guard de forma) | M | | |
| Foto 1 vista | **`Altres/F3 VG.png`: captura de Google Earth** (vista de carrer), a la carpeta però NO a `FOTOGRAFIES/` | cap | **ND** | A: el lector de fotos només mira la carpeta de fotos; SmartScan ja li dona el rol `photo_site_overview` | **ampliar els candidats del lector de fotos als PNG d'`ALTRES`/`OTROS`** (una línia a `list_candidates`) |
| Fig 2 assaigs | `Altres/F2 UBI PUNTS.png` | retall del full = el mateix dibuix (ph 6) | M | | |
| Foto 2 DPSH | `P3.jpg` (l'última de l'annex, 3 fotos) | `P1.jpg` (la primera) | **X** | A: empat | wizard / pregunta 37 |
| Fig 4 geològic | `Altres/F4 MGEOL.png` | el mateix | M | | |
| Foto 3 materials | cullera | igual | M | | |
| Fig 5 tall | retall de `tall.pdf` (= `F5 TALL.png`, ncc 0,91), la nostra dins la seva | retall del dibuix | **C** | B: retall | §2.4 |

### 1.3 Bell-lloc (6 M · 0 C · 2 X · 2 ND → 75 %, 1 sobrant)

| figura | Eva | nosaltres | estat | causa | remei |
|---|---|---|---|---|---|
| Fig 1 situació (inset cadastral) | retall de l'**inset cadastral de l'`A.01.pdf` de l'arquitecte** (ncc 0,79, escala 0,19) | els dos mapes del seu full d'annex, de costat | **ND** | B: tria de font: el plànol de l'arquitecte en lloc del seu propi full (1 de 7; a Alcoletge, amb els mateixos insets, va fer el contrari) | pregunta 30; **wizard: oferir els insets del plànol com a alternativa** (el retall existeix: el lector el va treure amb C 0,85 i X 0,38 per la franja del títol) |
| Fig 2 situació (inset orto) | inset ortofoto del mateix `A.01.pdf` | (la mateixa composició nostra, puntuada contra aquesta) | **X** | B: idem | idem |
| Fig 3 projecte «Ubicació de l'habitatge…» | el dibuix del seu full de situació **amb els punts** (ph 8 contra el nostre retall) | el mateix retall, però imprès al 2.2 com a figura d'ASSAIGS (sobrant) | **ND** + sobrant | B: classificació de ranura: ella el posa a l'1.1 com a projecte i no fa figura d'assaigs; el mateix dibuix, un altre peu i capítol | pregunta 31 (té `A.01 amb punts.pdf` i no l'usa); **wizard: canviar la ranura del retall** |
| Fotos 1-2 vistes | fotos de camp (annex) | iguals | M M | | |
| Foto 3 DPSH, Foto 4 sondeig | annex | iguals | M M | | |
| Fig 5 geològic | **retall del visor ICGC amb punt vermell, no desat enlloc** | ICGC WMS per UTM (mateix tipus, enquadrament i estil diferents; cap buffer de 150-1.000 m s'hi acosta) | **X** | C: font fora de la carpeta | §2.5: pregunta 34 (quina vista del visor) o **que desi el retall a `ALTRES`** com fa a Castellar/Rubí/Vilanova |
| Foto 5 materials, Fig 6 tall | | iguals | M M | | |

### 1.4 Linyola (1 M · 1 C · 5 X · 0 ND → 29 %)

| figura | Eva | nosaltres | estat | causa | remei |
|---|---|---|---|---|---|
| Fig 1 situació | els dos mapes del seu full d'annex, amb **un pèl més de marge vertical** (phash 18; a ull idèntica) | els dos mapes del mateix full | **X** | B: retall (marge). Mesurat: cap marge fix serveix per als tres projectes que hi cauen | acceptar (a ull és la mateixa) o retallar pel MARC dibuixat del mapa en lloc del blanc (§2.4) |
| Fig 2 assaigs «…i els assaigs realitzats» | **la planta ACOLORIDA p3 del projecte de l'arquitecte (`2_02B_DG` p3) amb tres icones de sondeig dibuixades per ella**; ni el PDF «Punts de Sondeig» de l'arquitecte ni el seu propi full (monocrom amb P-1/P-2/P-3) són el signat | el retall del seu full (monocrom amb punts) | **X** | C: composició seva no desada (la base p3 la tenim; les icones no) | irreproduïble sense dibuixar punts (D3). Que desi la figura a `ALTRES` (workflow). Alternativa: **el lector pot oferir la p3 com a base** i el wizard deixar-hi posar els punts: fora d'abast avui |
| Fig 3 projecte «Detall del perfil…» | **secció de la p11** del projecte (meitat inferior), ncc 0,81 | el lector (skill neutre) va triar l'emplaçament de la p2; en una passada anterior va triar la secció (C 0,79) | **X** | B: judici + variància del lector | pregunta 32; **wizard amb els 2-3 candidats del lector**; §2.6 (variància) |
| Foto 1 DPSH | `P2.jpg` (la 2a de 3 a l'annex) | `P1.jpg` | **X** | A: empat | wizard / 37 |
| Fig 5 geològic | retall del visor ICGC, no desat | ICGC WMS per UTM | **X** | C | §2.5 |
| Foto 2 materials | | igual | M | | |
| Fig 6 tall | retall de les dues seccions de l'annex (ncc 0,64-0,93), **la seva dins la nostra** | retall del dibuix, més ample | **C** | B: retall | §2.4 |

### 1.5 Alcoletge (4 M · 0 C · 2 X · 0 ND → 67 %)

| figura | Eva | nosaltres | estat | causa | remei |
|---|---|---|---|---|---|
| Fig 1 situació, Fig 2 assaigs | full d'annex | iguals (ph 4, 8) | M M | | |
| Foto 1 DPSH | `P3 - ALCOLETGE.jpeg` (l'última de 3 a l'annex) | `P1` | **X** | A: empat | wizard / 37 |
| Fig 4 geològic | retall del visor ICGC («Zona d'estudi» taronja), no desat | ICGC WMS per UTM | **X** | C | §2.5 |
| Foto 2 materials, Fig 5 tall | | iguals | M M | | |

### 1.6 Vilanova (4 M · 1 C · 2 X · 2 ND → 71 %, 1 sobrant)

| figura | Eva | nosaltres | estat | causa | remei |
|---|---|---|---|---|---|
| Fig 1 situació | `OTROS/F1 SIT.png` | el mateix | M | | |
| Fig 2 projecte «emplazamiento» | **el dibuix del seu full de situació, retall AMPLE** (ph 6 contra el nostre retall) | el mateix retall, imprès com a assaigs | **ND** | B: el mateix dibuix li fa de dues figures (ample = projecte, estret = assaigs); amb el skill neutre el lector no ho endevina | pregunta 32; **wizard: «afegeix aquest retall també com a figura del projecte»** |
| Foto 1 vista | `FOTOGRAFIES/DES DEL CARRER.jpeg` (**retallada**; NO és a l'annex, que porta `DES DE DARRERA` i `INTERIOR`) | `DES DE DARRERA.jpeg` (la de l'annex) | **X** | A: tria contra el seu propi annex | pregunta 38; wizard |
| Fig 3 assaigs | **retall ESTRET** del mateix dibuix (ncc 0,683, llindar 0,70) | el retall sencer | **X** | B: retall | com la Fig 2: dues ranures del mateix dibuix, al wizard |
| Foto 1 DPSH, Fig 5 geològic | | iguals | M M | | |
| Foto 2 materials (SPT P-3) | `SPT A P3.jpeg` (retall vertical), a la carpeta | cap: la plantilla imprimeix UNA foto de materials | **ND** | A: plantilla | **plantilla: una foto per punt** (pendent §3 #1 de PENDENTS; el lector ja escriu `materials_per_punt`) |
| Foto 3 materials (SPT P-1) | | igual | M | | |
| Fig 6 tall | retall de l'annex, la seva dins la nostra | | **C** | B | §2.4 |
| (sobrant) 2a vista | l'Eva en posa una | n'imprimim dues (`INTERIOR`) | sobrant | A: empat/nombre | wizard |

### 1.7 Anciles (5 M · 0 C · 2 X · 3 ND → 71 %)

| figura | Eva | nosaltres | estat | causa | remei |
|---|---|---|---|---|---|
| Fig 1 situació | composició seva des de la Sede del Catastro | els dos mapes del seu full (ph 10) | M | | |
| Fig 2 projecte «plano topográfico» | `IV_PLANOS.pdf` **p5**, retall ajustat a la parcel·la (ncc 0,90 a l'inventari) | el lector neutre va triar la secció longitudinal p25; amb el skill amb fuites havia triat la p5 (X 0,65: retall més ample que el seu) | **X** | B: judici | pregunta 32; wizard amb candidats |
| Fig 3 projecte «viviendas previstas» | el full de tipologies **sencer amb caixetí**, de la versió «PROYECTO BÁSICO REVISADO» (dins `IV_PLANOS`, ≈ p9), no `A01_TIPOL.pdf` | cap (sobrietat: una figura) | **ND** | B: judici + nombre; a més contradiu «mai el caixetí» | idem |
| Fig 4 assaigs | full d'annex (planta amb punts S vermell, P blau) | igual (ph 6) | M | | |
| Foto 1 DPSH | | igual | M | | |
| Foto 2 sondeig | `EMPL S2.jpeg` (cap de les dues és a l'annex, que només porta P1-P4) | `EMPL S1.jpeg` | **X** | A: empat entre dos sondeigs | wizard / 37 |
| Fig 6 geològic | **IGME 1:1.000.000** (Aragó), no desat; l'ICGC no hi arriba | cap (pendent honest) | **ND** | C | que desi el retall a `OTROS`; o WMS de l'IGME (`mapas.igme.es`, GEODE 1:50.000 / 1:1.000.000) amb UTM, que tampoc tenim (Anciles sense UTM: `_FOR-NEW-YOU-20260907-2000` §4.1) |
| Foto 3 materials (S-1) | caixa S1 | igual | M | | |
| Foto 4 materials (S-2) | `S2_0-3.jpeg`, a la carpeta | cap (una sola foto) | **ND** | A: plantilla | una foto per punt |
| Fig 7 tall | | igual (ph 4) | M | | |

## 2. Per causa: què és, quantes, i com es podria resoldre més vegades

### 2.1 Empats entre fotos equivalents (6: DPSH ×4, sondeig Anciles, vista Vilanova)

**Què fa l'Eva:** té una foto de la màquina per punt (P1…Pn) i en posa UNA. Als 7 signats: la primera de l'annex a
3 (Bell-lloc, Vilanova, Anciles), l'última a 3 (Castellar, Rubí, Alcoletge), la del mig a 1 (Linyola). Al sondeig
d'Anciles, S2 en lloc de S1. A la vista de Vilanova, una foto que no és a l'annex, retallada. **No hi ha regla
observable**, i és molt probable que no en tingui (pregunta 37 i 38, obertes).
**Tenim la imatge?** Sí, sempre (ph 0), i a l'annex de fotografies en 5 de 6.
**Remeis:** (a) *pregunta 37/38* a l'Eva: si diu «la més neta» o «la del punt X», el lector ho pot aplicar; (b)
*wizard*: mostrar les 3-4 fotos de la màquina de l'annex i deixar-la triar en un clic — cost S (la pestanya de fotos
ja existeix), guany fins a 6 X → M si ella hi intervé; (c) *més tokens al lector* no serveix: no hi ha res a veure
que decideixi.

### 2.2 La plantilla imprimeix una foto on l'Eva en posa dues (2: materials Vilanova P-3, Anciles S-2)

**Tenim la imatge?** Sí (ph 0-2), i el lector de fotos ja escriu `materials_per_punt`.
**Remei:** plantilla, «una foto de materials per sondeig/punt quan n'hi ha diversos» (pendent §3 #1; pregunta 33 per
confirmar). Cost S-M (bucle a la plantilla + numeració de fotos per presència, com les figures). Guany: 2 ND → M.

### 2.3 El lector no mira on és la imatge (1: vista de Rubí, `ALTRES/F3 VG.png`)

**Què fa l'Eva:** una captura de Google Earth desada a `ALTRES`, no una foto de camp. SmartScan ja la marca
`photo_site_overview`.
**Remei:** afegir els PNG/JPG d'`ALTRES`/`OTROS` als candidats del lector de fotos (marcats «PNG de l'Eva»). Cost XS.
Guany: 1 ND → M. Risc: cap (el lector els veu com a candidats més).

### 2.4 Retall diferent de la mateixa font (7: tall ×4 C, situació Linyola, assaigs Vilanova, topo Anciles)

**Tall (4 C):** la font és `tall.pdf` als 7 i el nostre retall (peça 3) ja és el dibuix; la diferència és el marge:
a Castellar i Rubí la seva figura és **més gran** que la nostra (nostra dins la seva: ella agafa més cotes/marc), a
Linyola i Vilanova **més petita** (seva dins la nostra: ella deixa fora una part). Val la pena una passada dedicada:
mesurar, als 7, quin rectangle del `tall.pdf` correspon a la seva figura (ja tenim la correlació NCC amb la posició)
i mirar si el que inclou/exclou té nom (barra d'escala, llegenda, cotes de referència, títol de la secció). Si surt un
criteri, són 4 C → M i el tall queda al 100 % en M. Cost M (mig dia), 0 tokens.
**Situació Linyola (phash 18):** a ull idèntica; el seu retall té més marge vertical. Provat el marge fix i no serveix
per als tres alhora. Opció: retallar pel MARC dibuixat de cada mapa (línia del requadre) en lloc del blanc. Cost S.
Guany incert (1).
**Assaigs Vilanova (0,683 vs 0,70) i topo Anciles (0,65):** retalls més ajustats que els nostres. Al lector: instrucció
«retall ajustat al dibuix útil»; o afinar `trim_white` amb un pas de detecció del marc. Cost S, guany 1-2 X → C.

### 2.5 Font fora de la carpeta (5: geològic Linyola, Bell-lloc, Alcoletge, Anciles; assaigs Linyola)

**Geològic (4):** a Castellar, Rubí i Vilanova l'Eva desa el retall a `ALTRES` (`m12 mgeol`, `F4 MGEOL`) i els
encertem tots tres bit a bit. A Linyola, Bell-lloc i Alcoletge el retall del visor ICGC **no és a cap fitxer** (ni al
FH11 «6_mapa Geologic», que només existeix als tres primers); a Anciles és l'IGME, tampoc desat. La nostra recepta
ICGC (la que l'Eva va aprovar) dona el mateix tipus de mapa amb un altre enquadrament i estil; mesurat que el zoom no
és la diferència.
**Remeis, per ordre:** (a) *workflow*: demanar-li que desi el retall a `ALTRES` sempre, com ja fa a 3 de 7 — cost 0,
guany fins a 4; (b) *pregunta 34*: quina vista del visor fa servir (capa, escala, llegenda, punt/zona taronja); amb
la resposta, reproduir-la per WMS (cost S) o, si és el visor web, amb Playwright (com `/g3dt-adjacents-visor`; cost M,
fràgil) — guany 3; (c) *IGME* per a fora de Catalunya: WMS de l'IGME (`GEODE`) per UTM — cost S, però Anciles no té UTM
(cal la referència cadastral → UTM del `_FOR-NEW-YOU-20260907-2000` §4.1).
**Assaigs Linyola (1):** la base (p3 del projecte) la tenim; les icones de sondeig les va dibuixar ella sobre la planta
acolorida, i no ho va desar. Irreproduïble sense dibuixar punts (D3). Remei: workflow (`ALTRES`) o, més endavant, un
editor mínim al wizard per posar-hi els punts; fora d'abast.

### 2.6 Judici: quina figura del projecte, i quantes (4: Linyola secció, Anciles topo + tipologies, Vilanova emplaçament)

**Què fa l'Eva:** 0-2 figures «Font: Projecte», sense regla escrita: secció (Linyola), topogràfic + tipologies
sencer amb caixetí (Anciles), emplaçament ample del mateix dibuix dels assaigs (Vilanova, Bell-lloc); cap a
Castellar, Rubí, Alcoletge. Els criteris genèrics del skill neutre tenen sentit però no reprodueixen la seva tria:
el lector va agafar l'emplaçament a Linyola i la secció a Anciles (just a l'inrevés).
**Tenim les imatges?** Sí, totes (p11 de Linyola, p5 i ≈p9 d'Anciles, el retall de Vilanova).
**Remeis:** (a) *pregunta 32* (quan i quines); (b) *wizard*: el lector proposa 2-3 candidats per ranura amb la raó, i
l'Eva tria o descarta — cost M (pestanya de figures amb `figure_selection.json`, `source: user`); (c) *més tokens /
model més gran*: el problema no és veure-hi millor sinó saber què vol ella; una passada amb `opus` es pot provar
(cost 3× per crida) però sense la 32 no hi ha veritat a encertar; (d) *variància del lector*: entre passades canvia
la figura i el retall (Linyola: secció C → emplaçament X). Es pot reduir demanant-li 2-3 candidats ordenats en lloc
d'un (i que el wizard mostri els tres): la tria de l'Eva és la que mana.

### 2.7 Classificació de ranura (2: Bell-lloc projecte/assaigs; Vilanova ample/estret)

Mateix dibuix, un altre peu i capítol. Sense regla (preguntes 31 i 32). Remei: wizard, «aquest retall va a
assaigs / projecte / totes dues» — cost S sobre la pestanya de figures.

### 2.8 Mesura (transversal)

El phash i la NCC castiguen els dibuixos de línia fina (Linyola secció C 0,79 en una passada, X 0,66 en una altra
pel retall; Anciles topo 0,65-0,90 segons el retall). Per no confondre «no tenim la font» amb «el retall és un 5 %
diferent», afegir a la veritat (`docs/imatges/veritat/<slug>/index.json`) un veredicte manual «mateixa font a ull»
per figura, i que l'agregat el mostri al costat del hash. Cost S. No canvia el producte, canvia el que llegim.

## 3. Què faria, per ordre de rendiment per cost

| # | acció | causa | cost | guany potencial (in-sample) | depèn de l'Eva? |
|---|---|---|---|---|---|
| 1 | PNG d'`ALTRES` com a candidats del lector de fotos — ✅ **FETA 2026-09-09** (DECISION-LOG 2026-09-09 (2): +1 vista de Rubí; de pas, aparellament amb l'annex invariant a la rotació) | 2.3 | XS | +1 (Rubí vista) | no |
| 2 | Plantilla: una foto de materials per punt | 2.2 | S-M | +2 ND → M | confirmar (33) |
| 3 | Estudi del retall del tall als 7 (rectangle de l'Eva vs el nostre) — ✅ **FETA 2026-09-09** (DECISION-LOG 2026-09-09 (3): 2 C eren defecte nostre → M; 2 C són el marge blanc de l'Eva, es queden; Bell-lloc M → C per «(msnm)» sencer) | 2.4 | M, 0 tokens | fins a +4 C → M | no |
| 4 | Wizard: pestanya de figures i fotos amb els candidats del lector (2-3 per ranura), ranura canviable, «cap font» — ✅ **FETA 2026-09-09** (DECISION-LOG 2026-09-09 (4): zona fixa amb hover; el guany depèn que l'Eva la faci servir) | 2.1, 2.6, 2.7 | M-L | fins a +10 si ella clica | sí (és ella qui tria) |
| 5 | Workflow amb l'Eva: desar a `ALTRES` el geològic i qualsevol figura composta (com ja fa a 3 de 7) | 2.5 | 0 | +4-5 | sí |
| 6 | Preguntes 30-34, 37-38 amb el Josep | 2.1, 2.5, 2.6, 2.7 | 0 | desbloqueja regles o confirma que no n'hi ha | sí |
| 7 | Retall pel marc dibuixat (situació) i retall ajustat (lector) | 2.4 | S | +1-3 X → C/M | no |
| 8 | Veredicte manual «mateixa font a ull» a la veritat | 2.8 | S | cap al producte; lectura honesta | no |
| 9 | IGME WMS + UTM per referència cadastral (fora de Catalunya) | 2.5 | S+M | +1 (Anciles) | no |
| 10 | Editor de punts al wizard (dibuixar icones sobre la planta) | 2.5 | L | +1 (Linyola) i valor per a projectes nous sense full de punts | sí |

**El que NO ajudaria:** més tokens o un model més gran al lector (les discrepàncies no són de percepció sinó de
criteri de l'Eva i de retall), llegir més FH11 (els 4 que hi ha per projecte ja es fan servir: situació, fotos, tall;
el «6_mapa Geologic» només existeix on ja tenim el PNG), catalogar més imatges (l'inventari del pas 1 ja va mirar les
291 candidates amb hash: sabem exactament quines tenim i quines no).

**Sostre realista sense l'Eva (accions 1, 2, 3, 7):** de 29 M · 4 C · 15 X · 8 ND a uns 36 M · 1 C · 12 X · 6 ND (≈
75 %). **Amb l'Eva** (4, 5, 6): la majoria de la resta, perquè 22 de les 27 discrepàncies tenen la font a la carpeta.
