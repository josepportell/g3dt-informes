# Notes visuals (Claude mirant els fulls de contacte, 2026-09-07) — esborrany per al document

## Estàtiques i plantilla
- 473×210 «sense peu» al final de tots els signats = SEGELL de G3 (Desenvolupament Territorial S.L., CIF, adreça). No és figura.
- 752×452 (plantilla image8, referenciada): GRÀFIC DE PASTÍS de granulometria de RUBÍ (graves 50,3 / sorres 31,5 / fins 18,2). Només Rubí el té als signats; és a la plantilla perquè la plantilla ÉS el signat de Rubí. Comprovar si surt als generats (no surt a la seqüència dels generats: deu ser dins un bloc condicional o l'esborra el generador).
- Cullera SPT: la mateixa als 7 (bytes diferents, phash igual). El generador la insereix (no és referenciada a la plantilla).
- La plantilla arrossega 8 media de Rubí NO referenciats (imatges 1-4, 6, 7, 9 + cullera 5 = 8,9 MB): pes mort a cada informe generat.

## Tipus de figura als signats (7)
| tipus | Castellar | Rubí | Linyola | Bell-lloc | Alcoletge | Vilanova | Anciles |
|---|---|---|---|---|---|---|---|
| fig_situacio | 1 (topo+orto ICGC costat a costat, taronja) | 1 (topo+orto) | 1 (mapa municipi + cadastral zoom, vermell) | 2 imatges (cadastral + orto amb parcel·la vermella), «Font: Projecte» | 1 (topo+orto) | 1 (topo+topo zoom ICGC) | 1 (topo+orto, «Sede electrónica del catastro») |
| fig_projecte (Font: Projecte) | 0 | 0 | 1 (perfil/secció) | 1 (planta emplaçament, sense punts) | 0 | 1 (emplaçament habitatge, sense punts) | 2 (topogràfic parcel·la; plantes+tipologies) |
| fig_assaigs (amb punts) | 1 orto zoom + parcel·la taronja + punts + llegenda | 1 orto zoom + punts | 1 planta arquitecte + punts | 0 (!) | 1 planta arquitecte + ampliació ratllada + punts | 1 planta arquitecte + punts + cotes | 1 planta arquitecte + punts (S-1/S-2 vermell, P blau) |
| foto_vista | 0 | 1 (Google Earth carrer) | 0 | 2 (fotos de camp) | 0 | 1 (foto de camp de la parcel·la) | 0 |
| foto_dpsh | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| foto_sondeig | 1 | 0 | 0 | 1 | 0 | 0 | 1 |
| fig_geologic | ICGC 1:25.000 amb llegenda composta | ICGC 1:50.000 amb llegenda | ICGC (retall sense llegenda, punt vermell) | ICGC (retall sense llegenda, punt vermell) | ICGC (retall, «Zona d'estudi» taronja) | ICGC amb llegenda | IGME 1:1.000.000 (retall, «Zona en estudio») |
| foto_materials | 1 (caixa testimonis S-1) | 1 (SPT) | 1 (SPT) | 1 (caixa testimonis) | 1 (SPT) | 2 (SPT P-3, SPT P-1; la 1a repetida) | 2 (caixa S-1, caixa S-2) |
| fig_tall | retall del tall (sense llegenda ni caixetí) | idem | idem (2 seccions A-A' i B-B') | idem | idem | idem | idem |
| extra | Fig 6 i 7 estabilitat de vessant (llibre Hoek & Bray) | gràfic pastís granulometria | — | — | — | — | signatura manuscrita (693×535) a EMPUJE (no és figura) |

Nombre de figures «del projecte» abans de la cullera: Castellar 2, Rubí 2, Linyola 3, Bell-lloc 3 (1 i 2 compten com a dues), Alcoletge 2, Vilanova 3, Anciles 4.

## Procedència vista a ull (a confirmar amb el hash)
- Castellar: `ANNEXES/ALTRES/m7.png` = Fig 1 (mateixes mides 1430×714), `m8.png` = Fig 2 (812×800), `m12 mgeol.png` = Fig 4 (1470×806), `m9.png` → Fig 5 (retall). Peces: M1 topo, M2/m6 orto zoom, M3/M4 topo 1:5.000 (M4 amb rectangle taronja), M10/M11 geològic sense llegenda, m5 croquis manuscrit dels punts. `M1.png` porta el rol `figure_geological_map` (ERRONI: és el topogràfic). FOTOGRAFIES: còpies renombrades (maquina_dpsh*.jpg = P1/P3/P4, detall_materials* = S1/…, maquina_sondeig = S1/11.10.37, vista_general_1 = P2) — artefacte nostre, no de l'Eva. Fotos del signat: DPSH = P3.jpg?, sondeig = S1/11.10.37 (maquina_sondeig), materials = S1/11.10.01 (caixa). Extra: 2 WhatsApp del client a 25.0493 (fotos del solar) i 2 fotos del full de camp.
- Rubí: `Altres/F1 UBI.png` = Fig 1, `F2 UBI PUNTS.png` = Fig 2, `F3 VG.png` = Foto 1 (Google Earth), `F4 MGEOL.png` = Fig 4, `F5 TALL.png` → Fig 5 (retall del tall sense llegenda). Peces m1 topo, m2/m3 orto, m4 croquis, m5 geològic. El «plànol» del projecte són 2 FOTOS d'un plànol imprès (25.0794/IMG-…WA0015/16) — l'Eva NO els usa. SPT1.jpg = Foto 3 materials. P1-P3 = màquina.
- Linyola: Fig 1 = retall de l'annex «plànol de situació» (A4 apaïsat: dos mapes a dalt) o de p1 del projecte de l'arquitecte (2_02B_DG…pdf p1: situació + cadastral). Fig 2 = planta amb punts: annex (Eva dibuixa punts sobre `Punts de Sondeig_…_REDIBUIX.pdf`). Fig 3 = secció del projecte (2_02B_DG p9-11). Foto 2 materials = WhatsApp 12.05.09 (SPT).
- Bell-lloc: Fig 1 i 2 i Fig 3 = retalls d'`A.01.pdf` (insets cadastral + orto a dalt a la dreta; planta principal). Els PDF del Cadastre (25.0647/4613172…, 4613173…) contenen el mapa cadastral però l'estil de la Fig 1 (parcel·la vermella sobre cadastral) és el de l'inset de l'A.01. `A.01 amb punts.pdf` existeix però el signat NO el fa servir. Fotos vistes = WhatsApp 12.54.41 / 12.55.21; DPSH = DPSH/P1 o P2; sondeig = SONDEIG/12.54.57; materials = SONDEIG/12.53.10 (caixa).
- Alcoletge: Fig 1 = retall esquerre de l'annex plànol de situació (topo+orto apilats? no: al signat són costat a costat → composició pròpia, com Castellar). Fig 2 = `ampliació habitatge v2.png` (712×492 vs 710×610: quasi) — planta amb ampliació ratllada i punts p1-p3 (fet per l'Eva o l'arquitecte). Foto 1 DPSH = P3 - ALCOLETGE.jpeg (màquina sota porxo). Foto 2 materials = `spt alcoletge.png`. Fig 4 geològic = retall ICGC (no hi ha PNG al projecte). PENETROS.jpeg = foto del full de camp (el que el nostre pipeline va triar com a «màquina DPSH»).
- Vilanova: `OTROS/F1 SIT.png` = Fig 1, `F2 PUNTS.png` (orto amb punts) ≠ Fig 3 del signat (planta amb punts): l'Eva va canviar de criteri (orto→planta). Fig 2 = `26.0050/1.0.pdf` (planta arquitecte, retall). Fig 3 = planta amb punts (annex plano de situación). `F4 MGEOL.png` = Fig 5. Foto 1 parcel·la = DES DEL CARRER.jpeg (retall). DPSH = P1/P2. Materials = SPT 1 P-1 / SPT A P3 (retalls verticals).
- Anciles: Fig 1 (topo+orto Sede catastro) = composició pròpia (no hi ha PNG al projecte; FH11 plano de situación en té les peces). Fig 2 = `IV_PLANOS.pdf` p5 (topogràfic parcel·la, retall) — també `SITE_prop A.pdf`. Fig 3 = `A01_TIPOL.pdf` (= IV_PLANOS p9). Fig 4 = annex plano de situación (planta amb punts). Fotos: DPSH = P1-P4 (EMPL S1/S2 = màquina de sondeig), materials = S1.jpeg / S2.jpeg (caixes). IV_PLANOS p1 = portada (el que el pipeline posava com a plànol). Geològic IGME: no hi ha font al projecte.

## Fonts que no són al projecte (l'Eva les baixa)
- Captures ICGC topo/orto/geològic (M*.png a Castellar/Rubí/Vilanova; a la resta no queden les peces, només el resultat dins FH11/PNG).
- Google Earth (Rubí Foto 1). Sede del Catastro (Anciles Fig 1). IGME (Anciles Fig 6). Llibres (Castellar Fig 6-7, cullera).
