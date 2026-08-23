# /g3dt-llegir-projecte

Llegeix TOTS els documents d'una carpeta de projecte G3 com ho faria un geòleg que l'obre per primer cop, i escriu per a cada
document un JSON amb els candidats del **nivell A** (15 camps d'identitat de l'informe) amb ubicació i cita literal. Al final
escriu `_decisions.json` amb tres estats per camp: `segur` / `candidats` / `no_trobat`. **Mai un camp buit, mai falsa confiança.**

<command-name>g3dt-llegir-projecte</command-name>

Versió 0.7 (2026-08-23 nit) — Pas 3b: regles d'or per a les TAULES de l'informe (dades per fila/nivell), derivades de comparar les taules dels 7 informes signats amb els documents del corpus; verificades per mostreig (Castellar, Bell-lloc, Alcoletge), pendents de lectura d'or completa de taules.
v0.6: DWG llegibles via LibreDWG `dwg2dxf` + `scripts/dwg_text_dump.py` (verificat amb els 4 DWG de Tulipa; `docs/DWG-CONVERSOR-2026-08-23.md`).
v0.5: clarificacions del hold-out headless (3 projectes, ERR = 0; feedback dels executors a `docs/holdout-headless/_RESULTATS.md` §6).
v0.4: derivat de la lectura d'or dels 8 projectes (`docs/golden-read/`; resultats: ANALISI §11 — 80 OK / 17 CAND / 10 NT / 2 ERR, tots dos convertits en regla aquí).
v0.2: Pas 0 (context del document abans de llegir-lo; reflexió del Josep) + bloc `context` al JSON + lliçons de Tulipa.

## Arguments

`$ARGUMENTS` = path de la carpeta del projecte (requerit) `[--out DIR]` `[--only FITXER]`

- `--out DIR`: on escriure els JSON (defecte: `{projecte}/validation/lectura/`; en dry-run: `docs/golden-read/{expedient}/`).
- `--only FITXER`: llegeix només aquest document i escriu el seu JSON (una crida per document = forma headless de producció).

Exemples:
```
/g3dt-llegir-projecte /mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC --out "docs/golden-read/4001612 BELL-LLOC"
/g3dt-llegir-projecte /mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC --only "25.0647/PRESSUPOST GEOTEC.BELL-LLOC.pdf"
```

Entorn: `.venv/bin/python` del repo té `fitz` (PyMuPDF), `openpyxl`, `xlrd`, `extract_msg`, `python-docx`, `PIL`. Sense `unzip` (usa `zipfile`).
Mode headless: no facis cap pregunta; si dubtes, baixa d'estat (`segur` → `candidats` → `no_trobat`) i anota-ho a `note`.

## Els 15 camps del nivell A

`expedient`, `client_name`, `street_address`, `municipality`, `architect_name`, `building_type`, `num_floors`,
`superficie_parcela`, `field_date`, `cota_referencia`, `num_soil_levels`, `num_dpsh_tests`, `utm_x_utm_y` + `referencia_catastral`,
`lab` (`lab_testing_company`, `lab_sample_id`, `lab_depth`, `lab_location`), `cte` (`cte_edificacio`, `cte_sol`).

**Nivell A ampliat — taules (v0.7):** a més dels 15 escalars, les files de les taules de l'informe que són LECTURA de documents:
`dpsh_tests[]` (per punt), `sondeig_tests[]` (per sondeig), `spt_ma_tests[]` (per assaig), `soil_levels[]` (per nivell, amb
litologia i fondàries de transició), `superficie_construida`. Regles al Pas 3b; sortida al bloc `tables` del Pas 4.

Fora d'abast (es fa després, Python/criteri Eva amb override): paràmetres geotècnics per nivell (γ, c, φ, E — Crespo/judici),
K de permeabilitat (taula de valors típics de l'Eva per material), Tipus de terreny NCSE + Coef. C, Qa, assentaments, narrativa.
El skill LLEGEIX les dades que aquestes derivacions necessiten (Nb/N de l'Excel, fondàries de nivell, litologies); no deriva.

## Pas 0 — Abans de llegir cap dada: posa el document en context

Un humà no extreu dades d'un document fins que sap **què és, qui l'ha fet, per a qui, per resoldre què, i quines dades hi
espera trobar**. Fes-ho explícit per a cada fitxer, ABANS de buscar-hi res, i escriu-ho al bloc `context` del JSON:

- `who_made_it` / `for_whom` / `why`: p. ex. *"TPS (subcontractista de sondeigs) fa aquest albarà per a G3, que li ha encarregat
  els penetròmetres d'aquest projecte"*. Conseqüència: **les caselles 'client' d'aquest document es refereixen a la relació
  TPS→G3, no al projecte**. La casella `CLIENT: G3` és correcta dins del document i irrellevant per a `client_name` de l'informe.
  Mateix raonament: GTL (`DADES DEL CLIENT` = G3, client del laboratori), comanda (`SOL·LICITANT` = G3), pressupost G3
  (`CLIENT` = qui demana el geotècnic, sovint l'arquitecte), plànol de l'arquitecte (`Promotor` = qui paga l'obra = el client real).
- `expected_fields` / `not_expected`: un plànol de situació porta carrers, parcel·la, cotes, punts d'assaig — no porta la data de
  camp; una fitxa de camp porta contacte, previsió i data — no porta plantes; un GTL porta mostra, cota i resultats — no porta
  el promotor. Un valor trobat on **no s'espera** (municipi en una foto, client en un albarà) té confiança baixa per construcció.
- `relation_to_others`: un full de camp manuscrit de TPS té versió digital a l'Excel DPSH **revisada per l'Eva** → l'Excel mana
  per als valors, el manuscrit es llegeix per si porta alguna cosa que l'Excel no té (punt 0, N.F., croquis, data). Un annex
  FreeHand i el seu `Print To PDF` són el mateix dibuix. Un pressupost `-2CASES` amb `modDate` posterior substitueix el primer.
  Un `RE:`/`RV:` només aporta el text nou i els adjunts nous.
- `authority_for`: per a quins camps del nivell A aquest document és autoritat (p. ex. comanda → expedient, municipi, mostra;
  fitxa → data de camp, contacte; annex sondeig → cota i nivells; caixetí del plànol → promotor, arquitecte, plantes, superfície).

Mapa "casella del document → rol al projecte" (els casos que han fet fallar les tres arquitectures anteriors):

| Document | Casella | Qui hi surt de veritat | Rol al projecte |
|---|---|---|---|
| Albarà / full de camp TPS | `DADES CLIENT: Empresa / Responsable` | G3 / Eva | cap (client del subcontractista) |
| GTL laboratori | `DADES DEL CLIENT` / `SOL.LICITANT` | G3 (B25364589) | cap (client del laboratori); l'emissor (banda TPS B64803075) és `lab_testing_company` |
| Comanda laboratori | `DADES DEL SOL.LICITANT` | G3 | cap; el bloc `DADES DE L'OBRA` sí que és del projecte |
| Pressupost G3 / fitxa / correu d'encàrrec / annex sondeig | `CLIENT:` | qui demana el geotècnic (sovint l'arquitecte) | `architect_name` si conté ARQUITECT; `client_name` només si no hi ha promotor enlloc (candidat) |
| Pressupost signat p.5 (`DADES QUE HAN DE CONSTAR EN LA FACTURA I EN L'INFORME`) | NOM I COGNOMS + NIF | el client de l'informe | `client_name` (autoritat A) |
| `ACCEPTACIO/DADES CLIENT.txt` | nom + NIF | el client de l'informe | `client_name` (autoritat A); la seva adreça és la del client, no de l'obra |
| Plànol / projecte de l'arquitecte | `Promotor` / `Propietat` ; `Arquitecte` | promotor ; arquitecte | `client_name` ; `architect_name` (autoritat A) |
| Etiqueta manuscrita de caixa de mostres | `Client:` | G3-Eva | cap |

## Pas 1 — Inventari

1. Llista recursiva de tot. **Exclou** (sortides de l'Eva o nostres): `*_informe*`, `*_generated*`, `*PORTADA*`, `PDF/LLETRA/`,
   `PDF-V0/`, `PDF V0/`, `*.FH11`, `validation/`, `_validation/`, `Thumbs.db`, `*EXPLICACI*.docx` (meta-document).
   **Inclou** `PDF/ANNEXES/*.pdf`, `tall.pdf`, `pl. situaci*.pdf`: l'Eva dibuixa els annexos abans d'obrir el wizard; són fonts vàlides.
2. `.msg`: extreu cos + adjunts amb `extract_msg` a un directori temporal. Dedup d'adjunts per md5 contra la carpeta (sovint ja hi són solts).
   En cadenes `RE:`/`FW:`, només el text per sobre del primer `De:`/`From:` és nou. Imatges ≤ 25 KB o de 783×3 px = signatura, ignora.
3. `.zip`: obre amb `zipfile`. `.dwg`: si hi ha `dwg2dxf` (LibreDWG, `~/.local/bin` o PATH), extreu el text amb
   `.venv/bin/python scripts/dwg_text_dump.py FITXER.dwg` i llegeix-lo com un plànol més; si no, marca `no llegible: DWG`.
4. Classifica cada fitxer en una classe i llegeix-los **en aquest ordre**:
   1. plantilles G3 (pressupost, fitxa de camp, comanda de laboratori, PLAN_COST, Excel DPSH) → 2. `ACCEPTACIO/` (pressupost signat,
   `DADES CLIENT.txt`) → 3. annexos de l'Eva → 4. laboratori (GTL) → 5. documents del proveïdor (plànols, projecte, Cadastre) →
   6. correus → 7. fulls de camp manuscrits (albarans TPS) → 8. fotos (només per a data pel nom de fitxer i per corroborar).

## Pas 2 — Identificació determinista de les plantilles G3 (on mira l'Eva)

| Document | Com reconèixer-lo | Cel·les / posicions del nivell A |
|---|---|---|
| **Pressupost** `PRESSUPOST GEOTEC.*.pdf` (7 p.) | PDF `creator == "G3 DESENVOLUPAMENT TERRITORIAL, S.L."`, `title == "m4PRO ERP · Informes del Proyecto"` | p.1 bloc `CLIENT:` (nom / [carrer] / CP / Tel) = **sol·licitant**; bloc `OBRA:` (encàrrec / adreça / municipi); p.2 `Tipus d’edifici: C1`, `Tipus de Terreny : T1`, `N assaigs de penetració dinàmica DPSH`, `N Sondeig`; codi `25·NNNN P#` = codi comercial, NO expedient. **Ordena els blocs per (y, x)**: l'ordre natural barreja CLIENT i OBRA. |
| **Fitxa de camp** `DADES PER ANAR A CAMP*.xlsx` | `fitxa!B2 == "DADES PER ANAR A CAMP"` | C6 client (= sol·licitant), C7 `ADREÇA OBRA` (adreça + municipi a la mateixa cel·la), C8/F8 contacte + tel., C13/F13 previsió (`2 (P)`, `5P+2S`), C38 empresa (`TPS ERUGA`), **F38 data de camp** (tipus data; etiqueta E38 `dies de camp`). Pot ser buida. Imatges incrustades = fotos. |
| **Comanda laboratori** `comanda laboratori_*.xls` | `Hoja1!C3 == "PETICIÓ D'ASSAIGS DE LABORATORI"` | Dos blocs amb les MATEIXES etiquetes: files 11-15 `DADES DEL SOL.LICITANT` = G3 (NIF B25364589) → ignora; files 18-23 `DADES DE L'OBRA`: N18 tipus obra, **N19 expedient** (float), N20 adreça, N21 municipi, N23 `DATA DE PRESA` (= dia de la mostra/sondeig, no primer dia), AH23 sol·licitud; fila 35+ mostres (C id, J/L cotes). |
| **PLAN_COST** `PLAN_COST_*.xlsx` | `'Plan Cost'!B2 == "PLAN COST  |  G3 DT"` | E9 `DESCRIPCIÓ TITÒL` (`EG HAB UNIF {MUNICIPI}`), E21 tècnic, `OFERTA!B21` unitats DPSH, `B6` ml sondeig, `B14` SPT. **Tota la resta és plantilla** (`SOIL-ASSAIG`, `TPS`, `LLEIDA`, preus): mai senyal. |
| **Excel DPSH** `ANNEXES/{exp}_DPSH.xls` | fulls `P-1`, `P-2`…; capçalera fila 16 | `num_dpsh_tests` = fulls amb dades a la columna C (executats). Cap metadada de projecte dins. Peu B80 cota de rebuig. |

Annexos de l'Eva (FreeHand → PDF via Distiller/`PScript5.dll`): **el text és brossa** (fonts sense ToUnicode) → renderitza
(`page.get_pixmap(dpi=100)`) i llegeix visualment. Si hi ha còpia `Microsoft: Print To PDF` del mateix (`tall.pdf`, `pl. situaci.pdf`),
el text és net. `PDF/ANNEXES/{exp}_DPSH.pdf` (des d'Excel) sí que té text: capçalera `Cota inici: +NNN.NN msnm …`, `OBRA:`, `POBLACIÓ:`,
`DATA:`, `NÚMERO D´INFORME:`.

Altres reconeixements: GTL del laboratori = text `INFORME DE RESULTATS D'ASSAIGS DE LABORATORI` + banda `TPS, PROSPECCIÓ DEL SUBSÒL, SL B64803075`;
Cadastre = `title` que comença per `Certificación Descriptiva y Gráfica Catastral`; albarans/fulls de camp TPS = escanejats, logo `tps`, 0 text → visió;
plànols AutoCAD = text vectorial al caixetí i cotes, però **taules de planejament i retalls són imatges** → `clip` + 120 dpi.

## Pas 3 — Regles semàntiques (les que fan que un humà no s'equivoqui)

- **`client_name` = promotor/propietari de l'obra**, no qui demana el pressupost. Prioritat: caixetí del plànol amb etiqueta
  `Promotor`/`Propietat` > `ACCEPTACIO/DADES CLIENT.txt` (nom + NIF) > formulari p.5 del pressupost signat si està omplert > correus
  que diguin "propietari". El `CLIENT:` del pressupost, de la fitxa, del correu d'encàrrec i de l'annex de sondeig és el **sol·licitant**
  (sovint l'arquitecte): candidat amb nota, mai segur si el nom conté `ARQUITECT`. Totes aquestes aparicions deriven de l'encàrrec:
  **no són fonts independents** entre elles.
- **G3 mai és client**: `G3`, `G 3`, `G3 DESENVOLUPAMENT TERRITORIAL`, NIF `B25364589`, `G3 - Eva`. Apareix com a "client" a la comanda
  (sol·licitant), al GTL (`DADES DEL CLIENT` del laboratori) i als albarans TPS (`DADES CLIENT: Empresa G3 / Responsable Eva`). Descarta'l.
- **`architect_name`**: caixetí `Arquitecte` > signatura digital del pressupost acceptat (`/Sig /Name`, p. ex. `JORDI BOSCH NOVELL / num:37655-8`)
  > signatura de correu amb núm. de col·legiat (`arquitecte col·legiat 74829-3`) > nom del despatx al pressupost/correu. Persona, no despatx,
  si és possible. Si client i arquitecte són la mateixa persona (arquitecte autopromotor), no descartis el nom pel fet de ser el sol·licitant.
- **`lab_sample_id`**: l'etiqueta de la mostra a l'informe és la de l'ANNEX de l'Eva (Castellar: annex "SPT-1", GTL "MA1" → informe SPT-1;
  Anciles: comanda/annex "MA" → informe MA-1). Annex de l'Eva > GTL > comanda per a l'etiqueta; GTL > Excel > full de camp per a la PROFUNDITAT.
  Si annex i GTL discrepen d'etiqueta → candidats (annex primer), mai segur.
- **`architect_name` amb persona I despatx**: l'Eva escriu de vegades la persona (Bell-lloc: Jordi Bosch Novell) i de vegades el despatx
  (Linyola: BUNYESC ARQUITECTURA EFICIENT) → quan existeixen totes dues formes, candidats [persona | despatx], MAI segur.
  Pot també no ser enlloc de la carpeta (Vilanova: l'informe diu un nom que cap document conté) → candidats + "no consta a la carpeta".
- **`architect_name` absent** (casa modular, particular que encarrega directament): l'Eva escriu el CLIENT al camp arquitecte de
  l'informe (Rubí, Alcoletge, Vilanova, Anciles). → `candidats` amb el client com a candidat etiquetat "(pràctica Eva: client)",
  mai `segur`. Un fabricant de cases modulars (segell al catàleg) NO és l'arquitecte.
- **`street_address`**: només de blocs etiquetats `OBRA`, `ADREÇA OBRA`, `Situació`, `Localización`, `Adreça de l'obra`. Mai l'adreça
  del client (`DADES CLIENT.txt`) ni del sol·licitant. **Poden existir dues adreces verdaderes** (cantonada): no competeixen →
  `candidats`. Si els annexos de l'Eva diuen "entre el carrer X i el carrer Y", aquesta frase és la redacció de l'informe → candidat 1.
  Grafies manuscrites (`Ballet`/`Bellet`) → normalitza cap a la del document imprès. La regla de cantonada demana DUES adreces
  documentades: carrers veïns visibles als dibuixos sense cap document que els doni com a adreça de l'obra → nota, no candidats.
- **`municipality`**: comanda N21 + pressupost p.1 + PLAN_COST E9 ("sempre" 3 fonts). Forma oficial llarga (Cadastre, GTL, plànol:
  `Bell-lloc d'Urgell`) > forma curta de G3 (`BELL-LLOC`) > manuscrits (`BELL-LLOCH`). Mai la població del sol·licitant (Els Omells de
  Na Gaia) ni del client. Mai una foto.
- **`expedient`**: nom de la carpeta (`NNNNNNN MUNICIPI`) = comanda N19 = annex DPSH `NÚMERO D´INFORME` = GTL `Obra / Projecte`.
  NO són l'expedient: `25·0647` (codi comercial), `EXP25.34/SET.25` (arquitecte), `4677-GTL-25` / `GTL-8205-25` (laboratori), i els
  caixetins dels annexos de l'Eva poden tenir typos (`4001621`).
- **`field_date` = primer dia de camp** (normalment els DPSH): fitxa F38 > annex DPSH `DATA:` > albarà TPS > noms de fotos WhatsApp
  (`Imagen de WhatsApp YYYY-MM-DD …`; EXIF no hi és). La comanda `DATA DE PRESA`, l'annex de sondeig i el GTL donen el dia del
  sondeig (pot ser un altre dia): candidat 2 amb nota "sondeig". Mai la data del pressupost, de l'acceptació ni del GTL.
- **`num_dpsh_tests`**: Excel DPSH (executats) > albarà TPS `Nº de penetròmetres realitzats` > pressupost p.2 (previstos) > fitxa `N (P)`.
  Si previstos ≠ executats, mana l'Excel i anota-ho.
- **`cota_referencia`**: annex DPSH `Cota inici: +NNN.NN msnm segons …` = annex sondeig `z:` (criteri de l'Eva, sovint ICGC −0,15 carrer)
  > `COORDENADES.txt` z (GPS; l'Eva no l'usa: ~0,6 m de diferència) > ICGC. Cota relativa (p. ex. −4,0) pot ser intencionada.
- **`num_soil_levels`**: columna `Unitat litològica` de l'annex de sondeig (`NIVELL 1`, `NIVELL 2`…) > llegenda del tall (`1er nivell`, `2n nivell`).
  Els trams de material del full de camp NO són nivells. Sense annex → `candidats` amb el nombre de trams i nota "confirmar".
- **`superficie_parcela`**: taula de planejament del projecte/plànol (`Parcel·la … Projecte`) > suma de les parcel·les cadastrals de la
  carpeta > una parcel·la sola. Amb 2+ consultes cadastrals i "parcel·les contigües" al correu: `candidats` (projecte, suma, cadascuna).
  Única font (el projecte) sense contradicció → segur admès, amb nota "única font".
- **`num_floors`**: taula de planejament (`N. plantes PB+PP`) > correu d'encàrrec (`Pb de 280m + p1 de 86` → PB+1) > projecte. Cap plantilla G3 ho té.
  Si la descripció només cobreix 1 de N unitats de l'obra → `candidats`, no segur. Sense taula ni correu, si TOT el programa del projecte és
  d'una planta (plantes + alçats coherents) → segur amb confiança ≤ 0,8 i nota "derivat del programa".
- **`building_type`**: títol del projecte/plànol > PLAN_COST `HAB UNIF` (expandir) > comanda `CONSTR HABITATGE` > correu. L'informe redacta
  ("un habitatge unifamiliar"): comparació CLOSE. Instrucció del client POSTERIOR als annexos (correu que dicta el títol de l'informe) >
  redacció dels annexos anteriors → candidat 1 amb nota.
- **`referencia_catastral`**: consultes del Cadastre a la carpeta (`title`/nom `NNNNNNNCGNNNNS0001XX`) o als adjunts dels `.msg` (els noms
  dels adjunts ja la porten). Dues parcel·les → `candidats` amb les dues. Mai inferir-la d'una adreça. Impresa al plànol/projecte de
  l'arquitecte = font vàlida però única → `candidats`, mai segur sense consulta del Cadastre.
- **`utm_x_utm_y`**: `ANNEXES/ALTRES/COORDENADES.txt` (`X ; Y ; Z` per punt) > caselles x/y de l'annex de sondeig > res (no geocodificar aquí).
- **`lab`**: laboratori = emissor del GTL (banda amb registre mercantil; TPS B64803075), mai el "client" del GTL. Mostra/cota: comanda
  fila 35 (`SPT 1 (S1)`, J/L) = GTL `Mostra:` / `Cota d'extracció` = annex sondeig. Sense GTL (arriba setmanes després): la comanda basta.
  `lab_location` = el punt d'assaig d'on surt la mostra (S-1, P-3): el parèntesi de la comanda fila 35 (`SPT 1 (S1)`) = GTL `Mostra: SPT1 P3` = annex.
- **`cte`**: pressupost p.2 `Tipus d’edifici: C1` / `Tipus de Terreny : T1`; el correu d'encàrrec sol dir "És un C1". Definició de l'Eva:
  C0 < 300 m² i < 4 plantes; C1 > 300 m² i < 4 plantes; C2 ≥ 4 plantes.

### Situacions estructurals (apreses a Tulipa)

- **Un expedient, N informes**: subcarpetes `CASA 1…`, `CASA 2…` amb Excel DPSH i annexos propis; pressupost `-2CASES` amb nota "DOS
  INFORMES … UN A NOM DE CADA CLIENT"; comanda "CONSTR DOS NOUS HAB". → escriu un bloc de decisions PER CASA (`casa_1_…`, `casa_2_…`),
  `num_dpsh_tests` per casa, `street_address`/`client_name`/`architect_name` per casa (poden ser diferents: Tulipa 3 / VUA vs Tosca 16 /
  Factoria). Un sondeig compartit → `num_soil_levels` de la casa sense sondeig = `candidats` + "confirmar"; el bloc `lab` de la casa
  sense sondeig es replica en `candidats` amb nota "S-1 a la parcel·la de casa X". Línia CTE única del pressupost cobrint N cases:
  deriva per casa amb la superfície de CADA encàrrec; per a les cases de superfície desconeguda → `candidats`.
- **Dos pressupostos, mateix codi**: el de `modDate` posterior mana (quantitats). PLAN_COST no s'actualitza: és l'última font per a quantitats.
- **Acceptació escanejada** (Adobe Scan): el formulari p.5 `DADES QUE HAN DE CONSTAR EN LA FACTURA I EN L'INFORME` pot estar omplert a mà
  → clip de la zona (30-62 % de l'alçada) a ≥ 170 dpi i visió. L'OCR incrustat no serveix per al manuscrit. És autoritat A per a `client_name`.
- **Fitxa sense data** (F38 buit): `field_date` des d'annex sondeig / comanda DATA DE PRESA / albarà TPS / noms de fotos / correu "demà".
- **Plànols en DWG** (dins `.zip`): amb `dwg2dxf` disponible, llegibles (`scripts/dwg_text_dump.py`). Què hi ha de veritat (Tulipa):
  el caixetí del TOPOGRÀFIC porta RC (sovint 2 parcel·les → `referencia_catastral` candidats), promotor i adreça; el DWG de
  paràmetres urbanístics porta superfícies de PLANEJAMENT (divisió proposada ≠ parcel·la cadastral: candidats etiquetats, no
  competeixen amb el Cadastre); la `superficie_parcela` cadastral (la que usa l'Eva) NO hi és — és derivació Python (RC → WFS
  INSPIRE `areaValue`), no lectura. Camps AutoCAD surten `######` (no llegibles); els blocs poden portar restes de plantilla
  d'ALTRES projectes (caixetí sencer inclòs) → Pas 0 abans d'usar cap text. Sense conversor: `superficie_parcela`, `num_floors`
  depenen del correu de l'arquitecte (superfícies per planta → `num_floors` segur amb nota) i queden `no_trobat` amb proposta.
- **Metadades PDF com a indici**: el `title` d'un plànol pot portar la ruta del despatx (`…\408 REPARCEL·LACIO JORDI GENE TOSCA 16\…`)
  → candidat feble (≤ 0,3), mai segur.
- **Annexos d'Eva amb errors de còpia**: caixetí sense actualitzar (plànol de situació casa 2 dient "Tulipà nº3"), typo d'expedient
  (`4001621`), cota diferent entre annex DPSH (198) i annex sondeig (199,0) → mai "segur" amb una sola còpia; creuar.
- **`client_name` amb promotors que canvien**: el formulari p.5 ('que han de constar en la factura i en l'informe') mana fins i tot
  sobre el 'Promotor' del projecte VIGENT (Anciles: p.5 = Alba Barrau; IV_PLANOS = PICO DE OLA S.L.) i sobre versions velles del
  pressupost (Castellar: GRUP ALMA → WOOD COMFORT al MODF). La fitxa de camp pot conservar el client vell: no és autoritat.
  Amb 2 promotors al projecte (Linyola), l'informe va a nom de qui signa l'acceptació.
- **`num_soil_levels` quan tall i log discrepen**: el TALL (síntesi de l'Eva) mana (Anciles: tall 2, log 1 → informe 2) → candidat 1 = tall.
- **`cota_referencia`, ordre de candidats**: annex DPSH primer (4/4: Bell-lloc, Castellar −4 relatiu, Vilanova, Anciles P-1);
  l'origen pot ser ICGC, ICGC −0,15 carrer, o el topogràfic del CLIENT ('según el topográfico proporcionado'). UTM de l'informe = P-1 de COORDENADES.txt.
  Si l'annex dona cotes PER PUNT i cap cota única (parcel·la en pendent): `candidats` per punt + la cota d'implantació del projecte si
  existeix; mai triar-ne una com a `segur`.
- **Derivacions quan el pressupost no porta la línia CTE** (Castellar, Linyola, Anciles): C segons superfície construïda TOTAL de
  l'encàrrec (< 300 m² i < 4 plantes → C0; > 300 → C1) + T-1 com a candidat per defecte (valor de tots els pressupostos que la porten). Sempre candidats, mai segur.
- **Esborranys de l'Eva a la carpeta**: `ANNEXES/Altres/*.png` (figures del cos de l'informe) poden ser versions ANTERIORS dels
  annexos (Rubí: F5 TALL.png amb 2 nivells i cotes 211,9 vs annex PDF amb 1 nivell i 212,5). Prioritat: `PDF/ANNEXES/*.pdf` >
  `tall.pdf`/`pl situ.pdf` (Print To PDF) > `ANNEXES/Altres/*.png`. Si discrepen, `candidats` amb el PDF primer.
- **Plànols de catàleg** (fabricant de cases modulars, foto WhatsApp): `num_floors` = PB (+ Porxo si n'hi ha), superfície = construïda
  (mai parcel·la), cap promotor/arquitecte. `superficie_parcela` i UTM poden no ser a cap fitxer (l'Eva: Cadastre / visor ICGC) → `no_trobat` + proposta.
- **Comanda amb cota de mostra mal transcrita** (0,6-1,4 vs GTL/Excel 0,6-1,2): GTL > Excel DPSH/annex sondeig > comanda per a `lab_depth`.
- **Albarà TPS amb "Assaigs SPT: No" però SPT documentat al GTL/annex**: el GTL/annex mana (probable criteri de facturació del
  sondista); anota el matís, no és contradicció.
- **Sense GTL** (arriba setmanes després): la comanda és l'única font de lab; el NOM del laboratori no hi consta → `lab_testing_company`
  és `candidats` (coneixement previ: G3 treballa amb TPS), no lectura.

## Pas 3b — Regles d'or de les TAULES de l'informe (v0.7)

Derivades de comparar les taules dels 7 informes signats amb els documents de les carpetes (2026-08-23; evidència a
`docs/audit/taules-llista/`). Verificades per mostreig on s'indica; la resta són el mateix patró aplicat — davant del dubte, candidats.

**Taula "Penetròmetres dinàmics DPSH" — una fila per punt P-i (`dpsh_tests[]`):**
- `cota_inici`: capçalera de CADA pàgina de `PDF/ANNEXES/{exp}_DPSH.pdf` ("Cota inici: +NNN.NN msnm segons…" o
  "P-2 cota inici: -4,2 m (respecte el carrer)"). **Pot ser diferent per punt i pot ser RELATIVA intencionada** (verificat
  Castellar: -4,0 / -4,2 / -4,0 / -4,0 respecte el carrer = exactament l'informe). Si l'annex només dona una cota, val per a tots.
- `profunditat_assolida`: peu B80 de l'Excel DPSH **"Rebuig a -X,XX m"** = fondària EXACTA del rebuig (verificat Castellar:
  -1,08/-0,48/-0,76/-1,55 = l'informe). L'última fila amb cops de la columna C és l'interval de 20 cm, NO la fondària assolida:
  usar-la només si B80 no hi és, i anotar-ho. Signe sempre negatiu a l'informe.
- `rebuig` (Si/No): B80 present → Si. Sense B80 i última lectura sense R → No (aturada per potència).
- `nivell_freatic`: columna `N.F.` de l'Excel DPSH (capçalera fila 16; una marca a la fondària on surt aigua — verificat
  Alcoletge: -1,00 a l'informe i "No detectat" al pipeline vell que la ignorava) > manuscrit PENETROS. "No detectat" NOMÉS si
  la columna és buida a tots els fulls.

**Taula "Sondeig a rotació" — una fila per S-x (`sondeig_tests[]`):** cota (annex sondeig `z:` — mateixes regles que
`cota_referencia`), profunditat assolida (annex sondeig), `spt_ma` en format "N_SPT/N_MA" (comptar del GTL + comanda fila 35 +
annex; l'Eva escriu "1/0" o "1/--"), nivell freàtic (annex sondeig). L'albarà TPS "Assaigs SPT: No" no mana (regla existent).

**Taula "Assaigs SPT / MA" — una fila per assaig (`spt_ma_tests[]`):** id i punt i fondària = regles `lab` existents (annex de
l'Eva mana per l'etiqueta). `n30`: annex de sondeig manuscrit (lectura VISUAL, xifra al costat de l'assaig; R = rebuig) creuat amb
el GTL si hi és; discrepància de lectura (54 vs 58 al pipeline vell per manuscrit dubtós) → candidats amb les dues lectures.
`litologia` = la del nivell d'on surt la mostra (vegeu `soil_levels`).

**Nivells del sòl (`soil_levels[]`) — alimenta 5 taules (nivells, permeabilitat, sulfats, sísmica, geotècnica):**
- `nom` ("1er nivell", "2on nivell") i ordre: regla `num_soil_levels` existent (tall > log; el TALL mana).
- `litologia`: llegenda del tall ("1er nivell: Graves amb sorres") + columna `Unitat litològica` de l'annex sondeig. **L'Eva
  re-redacta a l'informe** (tall "Graves amb sorres" → informe "Graves en matriu sorrenca carbonatades"; verificat Bell-lloc,
  Alcoletge): la redacció exacta és sempre `candidats` (tall primer, annex sondeig segon), MAI segur per a la cadena literal.
- `de` / `a` (fondàries de transició): cotes del tall + marques `Nivell N` de l'Excel DPSH (columna al costat del peu, B79) +
  annex sondeig. Són el que la sísmica usa com a gruix i la geotècnica com a rang de Nb: si els documents discrepen (esborrany
  PNG vs annex PDF — regla d'esborranys existent), candidats.
- `mostra_del_nivell`: el nivell que conté `lab_depth` — la fila de sulfats de l'informe porta AQUEST nivell, no sempre el 1r
  (Linyola: mostra al 2on nivell). Lectura + interval, no judici.

**Taula de plantes/superfícies:** `num_floors` i `superficie_parcela` són els escalars existents; s'hi afegeix
`superficie_construida` (correu d'encàrrec "Pb de 280m + p1 de 86" → l'Eva escriu "280+86"; taula de planejament; pressupost).
**L'etiqueta de la fila de parcel·la segueix la FONT del valor**: "segons plànols cadastrals" / "segons cadastre" / "segons
informació aportada" / "segons projecte" — emet la font amb el valor perquè el generador triï l'etiqueta. Ampliacions
(Alcoletge): l'Eva escriu "Superfície construïda ampliació" — si l'encàrrec és una ampliació, anota-ho.

**Què NO llegeix el skill (Tier B, no ho intentis):** K (m/s), Tipus de terreny sísmic + Coef. C, γ/c/φ/E, qualificació
d'agressivitat. Sí que en llegeixes els INPUTS (Nb mitjans de l'Excel per rang de fondària els pot derivar Python; tu dona
fondàries i litologies bones).

## Pas 4 — Sortida: un JSON per document

```json
{"source_path": "relatiu a la carpeta", "document_type": "pressupost_g3|fitxa_camp_g3|comanda_lab_g3|plan_cost_g3|dpsh_excel|annex_sondeig|annex_tall|annex_planol_situacio|annex_dpsh|annex_fotografies|informe_laboratori|consulta_cadastre|planol|projecte_arquitecte|correu|foto|full_camp_manuscrit|coordenades_gps|altre",
 "what_it_is": "1 frase", "issuer": "qui l'ha fet", "date": "...", "pages_or_sheets": "...",
 "context": {"who_made_it": "...", "for_whom": "...", "why": "...", "expected_fields": ["..."], "not_expected": ["..."],
             "relation_to_others": "duplicat de / versió revisada de / substitueix / complementa …", "authority_for": ["concept_id", "..."]},
 "tier_a": [{"concept_id": "...", "value": "...", "location": "p.1 bloc OBRA / Hoja1!N19 / caixetí / nom del fitxer", "quote": "text literal", "confidence": 0.0, "note": "ambigüitat, conflicte, duplicat, grafia"}],
 "tables": {"dpsh_tests": [{"punt": "P-1", "cota_inici": "...", "profunditat_assolida": "...", "rebuig": "Si|No", "nivell_freatic": "...", "location": "...", "quote": "..."}],
            "sondeig_tests": [], "spt_ma_tests": [], "soil_levels": [{"nom": "1er nivell", "litologia_candidats": ["..."], "de": "...", "a": "...", "mostra_del_nivell": false}],
            "__nota": "només si el document aporta files de taula (Pas 3b); ometre si buit"},
 "not_present": ["camps del nivell A buscats i absents"],
 "reading_notes": "què ha calgut fer (ordenar blocs, renderitzar, rotar, clip, llegir /Sig)"}
```

Escriu cada JSON **immediatament** després de llegir el document (el disc és la memòria). Els duplicats (mateix md5, mateix número
d'informe, "X amb punts") s'anoten com a tals i **no** compten com a fonts independents. Les entrades `NOT_client_name` serveixen per
deixar constància explícita del que s'ha descartat i per què.

## Pas 5 — `_decisions.json`

Per a cada un dels 15 camps (i, des de v0.7, un bloc `tables` amb `dpsh_tests`/`sondeig_tests`/`spt_ma_tests`/`soil_levels`
consolidats amb els mateixos 3 estats per fila — una fila amb totes les cel·les de 2+ fonts coincidents és `segur`; una
litologia re-redactable o un N30 manuscrit dubtós és `candidats`):
- `segur`: ≥ 2 fonts **independents** d'autoritat A coincideixen, o 1 font A sense cap contradicció. Sempre amb `candidates[]` (valor,
  font, cita) perquè la UI mostri d'on surt.
- `candidats`: llista ordenada ≤ 3 amb font i cita. També quan hi ha multiplicitat real (cantonada, dues parcel·les).
- `no_trobat`: amb `sources_checked[]` (on s'ha buscat).
- `rule`: la regla del Pas 3 aplicada, en una frase.

Criteri únic: **ERR-amb-confiança = 0**. Davant del dubte, baixa d'estat. No ompliu "perquè segur que és això".

## Pas 6 (només dry-run) — Comparació amb l'informe de l'Eva

Només DESPRÉS d'escriure `_decisions.json`: obre `validation/eva_reference_values.json` i `{exp}_informe.docx`, classifica cada camp
OK / CAND / NT / ERR, afegeix `comparison_with_eva` al `_decisions.json` i cada ERR com a regla nova en aquest skill i a
`docs/golden-read/_LESSONS.md`.
