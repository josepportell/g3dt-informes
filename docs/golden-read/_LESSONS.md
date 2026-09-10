# Lectura d'or — registre de lliçons (append-only)

Format: una lliçó per línia o bloc, amb projecte i font. Serveix per escriure el skill `g3dt-llegir-projecte`; no és l'anàlisi.

## Regles en paraules d'Eva (`4001612 BELL-LLOC/EXPLICACIÓ DETALLS.docx`, gener 2026 — citat, no interpretat)

- Expedient: «Es treu de la numeració de la carpeta que identifica cada informe / el nom de la carpeta porta el nº expedient i la població de l'informe».
- Client: «De la carpeta d'acceptació. (5ena pàgina del document), però pot estar en el mail...etc...».
- Adreça / municipi / arquitecte / tipus d'edifici: «Es treu del mail de petició del pressupost CARPETA PRESSUPOST de dins de la carpeta de l'arxiu» (×4 paràgrafs), «escrit pel client/comercial, però pot estar en plànols adjunts».
- Parcel·la / situació: «SI no el tenim ho consulto a través de la direcció detallada dins de la visor del icgc … Cal posar direcció en aquest format: Antoni Bellet (carrer), Bell-lloc (població) … en aquest cas no teníem el nº, només que era la cantonada entre dos carrers … cada cop més, tenim la referencia cadastral (punt taronja)».
- Figura del plànol: «AQUESTA FIGURA NOMÉS LA POSO SI TENIM ELS PLÀNOLS DE L'ARQUITECTE, SINO NO ES POSEN».
- CTE: «C0: edificacions de menys de 300 m2 totals construïts i menys de 4 plantes inclosos soterranis. C1: edificacions de més de 300 m2 totals construïts i menys de 4 plantes… C2: … igual o més de 4 plantes». «Es treu de les principals dades de la sol·licitud de pressupost».
- **Data de camp: «Es treu del dia dels treballs de camp, es pot treure del PDF dels assaigs DPSH, que estaran a la carpeta d'annexes» i «comprovar si la data del sondeig, en cas que n'hi hagi, si no és igual posar els dos dies».** → a Bell-lloc, 1 i 6 d'octubre: dos dies.
- Nombre d'assaigs: «està també a la carpeta de pressupost, en el pressupost fet, pàgina 2».
- Nivells: «En cas que hi hagi sondeig cal comprovar que coincideix amb el nº de nivells descrits en l'annex de sondeigs».
- Cota / profunditat / N.F.: «Totes aquestes dades es treuen de les dades exposades en el sondeig i en l'assaig DPSH, veure cota d'inici, profunditat, si es marca o no nivell freàtic».
- Laboratori: «si es tenen les actes … primera pàgina de les actes, però normalment ho fem abans de tenir les actes, i llavors les principals dades es poden extreure d'un arxiu excel de sol·licitud» (= la comanda).
- Geologia regional: «Aquesta historia canvia segons la zona de treball … jo tinc una carpeta de diferents words de les diferents zones de treball. Aquesta carpeta està al servidor» (nivell B; no està a la carpeta del projecte).

## 4001612 BELL-LLOC (2026-08-23)

### Identificació determinista de plantilles G3
- Pressupost: PDF metadata `creator == "G3 DESENVOLUPAMENT TERRITORIAL, S.L."` + `title == "m4PRO ERP · Informes del Proyecto"`; p.1 blocs `CLIENT:` / `OBRA:`; p.2 `Tipus d'edifici: C1` / `Tipus de Terreny : T1` / campanya; p.4 valoració; p.5 acceptació. El text en ordre natural barreja els blocs de la p.1 → ordenar per (y, x).
- Fitxa de camp: `fitxa!B2 == "DADES PER ANAR A CAMP"`; C6 client, C7 adreça obra (+ municipi a la mateixa cel·la), C8/F8 contacte, C13/F13 previsió ("2 (P)"), C38 empresa, **F38 data (cel·la de tipus data, etiqueta E38 "dies de camp")**.
- Comanda lab: `Hoja1!C3 == "PETICIÓ D'ASSAIGS DE LABORATORI"`; dos blocs amb etiquetes iguals (ADREÇA/POBLACIÓ): files 11-15 = sol·licitant (G3), files 18-23 = obra. N19 expedient (float), N18 tipus obra, N20 adreça, N21 població, N23 data de presa, fila 35 mostra.
- PLAN_COST: `'Plan Cost'!B2 == "PLAN COST  |  G3 DT"`; E9 títol ("EG HAB UNIF BELL-LLOC"), E21 tècnic, OFERTA!B21 unitats DPSH. La resta són preus de plantilla: `SOIL-ASSAIG`, `TPS`, `LLEIDA` surten a tots els projectes → mai senyal.
- Excel DPSH: un full per penetro; capçalera fila 16; cap metadada de projecte. `num_dpsh_tests` = fulls amb dades a la columna C.

### Trampes semàntiques vistes
- "CLIENT" apareix 5 vegades per al despatx d'arquitectura (correu, pressupost p.1, pressupost signat p.5, fitxa C6, annex sondeig) — **totes deriven de l'encàrrec, no són independents**. El promotor només és al caixetí A.01 (`Promotor`) i a `ACCEPTACIO/DADES CLIENT.txt` (amb NIF). Regla: client = etiqueta `Promotor`/`Propietat`/`DADES CLIENT`+NIF > "CLIENT" de documents G3.
- "DADES DEL CLIENT" del GTL i "SOL·LICITANT" de la comanda = G3 (B25364589). Mai client.
- El pressupost signat té el formulari de facturació **buit**; el que diu qui és el client real és `DADES CLIENT.txt` (i l'Eva ho confirma: «De la carpeta d'acceptació … però pot estar en el mail»).
- Adreça del client (`DADES CLIENT.txt`: Doctor Torrebadella 8) ≠ adreça de l'obra. Només blocs `OBRA` / `ADREÇA OBRA` / `Situació` / `Localización`.
- Dues adreces verdaderes: Mestre Ramon Ortiz 15 (pressupost, fitxa, Cadastre 15 i 13) i Antoni Bellet (comanda "BALLET", GTL, annexos). Els annexos d'Eva diuen "entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz". Mai competició: candidats o frase composta.
- Codis que semblen expedients i no ho són: `25·0647` (codi comercial del pressupost), `EXP25.34/SET.25` (expedient de l'arquitecte), `4677-GTL-25` / `GTL-8205-25` (laboratori), `4001621` (typo d'Eva als caixetins dels annexos plànol de situació). L'expedient bo: nom de carpeta = comanda N19 = annex DPSH "NÚMERO D'INFORME".
- Superfície de parcel·la: 995 m² (projecte, taula com a IMATGE dins A.01) vs 518 + 494 = 1012 m² (2 consultes cadastrals). Tres candidats legítims.
- Cota: annex DPSH «+199.50 msnm segons el plànol topogràfic ICGC (-0,15 carrer)» = annex sondeig z 199.50; `COORDENADES.txt` z = 198.9 (GPS). Eva usa ICGC, no GPS.
- Data de camp: DPSH 01/10 (fitxa F38, annex DPSH, noms de fotos WhatsApp `2025-10-01`), sondeig 06/10 (annex sondeig, comanda DATA DE PRESA, GTL). Regla d'Eva: si no coincideixen, els dos dies.

### Lectura tècnica
- FreeHand → PDF (Distiller, `PScript5.dll`): text amb fonts sense ToUnicode → brossa. Cal renderitzar (100 dpi n'hi ha prou per capçaleres). Si hi ha còpia "Microsoft: Print To PDF" del mateix FH11 (`tall.pdf`, `pl. situaci.pdf`), té text net.
- A.01 (A1): la taula JUSTIFICACIÓ PLANEJAMENT és un PNG incrustat → clip + 120 dpi. Caixetí i cotes sí que són text.
- Signatura digital del pressupost acceptat: `widget /V → /Name` = "JORDI BOSCH NOVELL / num:37655-8", `/M` = data. No és al text layer.
- `.msg`: `extract_msg`; en cadenes RE:, només el text per sobre del primer "De:" és nou; adjunts per md5 contra la carpeta (els 2 PDF Cadastre i el PLAN_COST ja hi eren solts).
- Cadastre PDFs: diuen "contiene anexos con las coordenadas" però `embfile_count == 0`.
- `Thumbs.db`: ignorar.
- Correcció de biaix: l'exemple del skill `g3dt-extreure-planol.md` (598 m², Pb+P1, 8,38 m) NO coincideix amb A.01 (995 m², PB+PP, 6,50 m).

### Resultat Bell-lloc vs informe d'Eva: 12 OK / 2 CAND / 1 N/A / 0 ERR
- CAND: `street_address` (el bo era la frase "entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz" dels annexos d'Eva) i `superficie_parcela` (el bo era 995, el del projecte; Eva no usa el Cadastre si el projecte ho declara).
- N/A: `referencia_catastral` no apareix a l'informe.
- Eva no ha escrit els dos dies de camp tot i la seva regla: l'informe diu «1 d'octubre de 2025» (dia dels DPSH).
- **El truth-map té falsos positius per substring**: "995" casa amb el telèfon 620199571 a 4 documents. El §3.2 de l'anàlisi («sup. parcel·la: A.01 + fitxa + PLAN_COST + pressupost») és fals per a Bell-lloc: 995 només és a la imatge de la taula de planejament d'A.01. Corregir `scripts/tier_a_truth_map.py` amb `\b` abans de reutilitzar-lo.

## Reflexió del Josep (2026-08-23, durant Tulipa) → Pas 0 del skill
- Un humà posa el document en context abans de llegir-hi res: qui el fa, per a qui, per a què, quines dades hi espera i quines no,
  com es relaciona amb els altres (manuscrit TPS vs Excel revisat per l'Eva). Per això no confon `client = G3`: "G3 ha demanat
  *aquest document* a TPS, per al projecte P del client C2". El skill v0.2 ho fa explícit (bloc `context` al JSON + mapa casella→rol).
- Això és feina del lector que raona (Claude Code amb el skill), no d'un extractor Python: Python treu cel·les, el context el posa el lector.
- Els 26 JSON de Bell-lloc són anteriors al bloc `context` (hi és implícit a `what_it_is`/`issuer`); els de Tulipa ja el porten.

## 3001706 C.TULIPA CERDANYOLA (2026-08-23) — lliçons parcials (abans de decisions)
- **Multi-informe**: subcarpetes `CASA 1- TULIPA/` i `CASA 2_ CARRER TOSCA/` amb Excel DPSH i annexos propis; pressupost `-2CASES`
  amb nota «DOS INFORMES GEOTÈCNICS, UN A NOM DE CADA CLIENT»; comanda «CONSTR DOS NOUS HAB AÏLLATS». Un expedient (3001706),
  un sondeig (S-1), 4 DPSH (P-1.1, P-1.2 | P-2.1, P-2.2). El nivell A s'ha de calcular PER CASA; `num_dpsh_tests` = 2 per informe.
- **Client = arquitecte** (casa 1): Aleix Subirà Felip és alhora VUA (arquitecte col·legiat 74829-3) i qui consta al formulari p.5
  del pressupost acceptat (NIF 47235352-E). La regla "client ≠ sol·licitant" no és absoluta: la font d'autoritat és el formulari p.5
  / DADES CLIENT / Promotor, sigui qui sigui.
- **Formulari p.5 omplert a mà** en un escaneig Adobe Scan: l'OCR incrustat el destrossa; cal clip + visió. És la "5ena pàgina" que l'Eva cita.
- **Dos pressupostos, mateix codi** (26·0254): el de `modDate` posterior mana per a quantitats (2 → 4 DPSH). PLAN_COST no s'actualitza.
- **Fitxa sense data** (F38 buit): la data de camp surt de l'annex sondeig (07/05/2026), la comanda (DATA DE PRESA 07/05), el correu de
  Tosca ("demà", 06/05) i els noms de fotos WhatsApp 2026-05-07. Sense fitxa, 4 fonts igualment.
- **Capçalera de l'annex DPSH no estable**: aquí sense DATA ni NÚMERO D'INFORME; amb cota per punt (casa 2: 201,25 / 202,85).
- **Conflicte de cota entre annexos d'Eva** (casa 1): annex DPSH 198 msnm vs annex sondeig +199,0 → candidats, mai segur.
- **DWG dins zip** (3 fitxers, 23 MB el de planta): sense `dwg2dxf`/`ezdxf` a l'entorn → no llegible; superfície i plantes de la
  casa 1 depenen del correu (PSOT+PB+P1, 308 m² construïts) i del que digui la referència.
- **Sense GTL** (sol·licitud de lab 01/06, carpeta copiada abans): la comanda és l'única font de lab (com l'Eva diu que passa normalment).
- **`_user_data_prev.json`, `.g3dt_network_path`, `DTE.txt`**: fitxers nostres/administratius; excloure els dos primers, DTE sense nivell A.

### Resultat Tulipa (casa 1) vs referència: 7 OK / 2 CAND / 3 NT / 4 N/A / 0 ERR (1 ERR condicional: 564 m² dins d'un DWG)
- **No hi ha informe de l'Eva a Tulipa**: `3001706_TULIPA_INFORME_FIX.docx` és generat (pipeline) i `eva_reference_values.json` n'està extret.
  La referència útil és `_user_data_prev.json` (`_sources == 'user'`): client, adreça, S+Pb+Pp, 564 m², 3 nivells, UTM 423000/4594347;
  `cota_referencia` l'Eva la va deixar BUIDA; municipi i despatx són prefills erronis acceptats. El truth-map del 23-08 per a Tulipa
  s'ha de rellegir amb això al cap.
- CAND: `num_floors` (correu: PSOT+PB+P1 → regla nova: segur amb nota) i `cota` (198 vs 199,0 entre annexos d'Eva; ella no va triar).
- NT: `superficie_parcela` (564 només pot ser al DWG → conversor), `utm` (l'Eva ho treu del visor ICGC, cap document), `ref. cadastral`.
- L'informe generat deia **1 nivell** i "Depressió de l'Ebre" a Cerdanyola: errors de producció visibles per a l'Eva (nivell A/B), no d'aquesta lectura.

## 3001631 RUBI (2026-08-23) — 9 OK / 3 CAND / 3 NT / 0 ERR (lectura per 2 subagents amb el skill v0.2; decisions meves)
- El skill és executable per algú altre: els subagents han produït 19 JSON amb `context`, cites i `NOT_client_name` sense cap ERR.
- **Casa modular sense arquitecte**: l'Eva posa el **client** al camp arquitecte de l'informe ('JOANA MARTINEZ'). El truth-map diu
  "arquitecte = client" també a Alcoletge, Vilanova i Anciles → regla: sense arquitecte, candidat = client (mai segur).
- El pressupost de Rubí NO porta adreça d'obra (bloc OBRA = encàrrec + municipi); l'adreça ve de la comanda ('C/ MIRANDA') i el
  número (39) només dels caixetins dels annexos de l'Eva. Fitxa de camp buida.
- Acceptació = FOTO WhatsApp del full 'Pàg. 2 de 2' amb formulari manuscrit (nom + NIF) → font A del client, només amb visió.
- `ANNEXES/Altres/F5 TALL.png` és una versió ANTERIOR del tall (2 nivells, cotes 211,9) que l'annex PDF (1 nivell, 212,5) supera:
  prioritat PDF/ANNEXES > tall.pdf > Altres/*.png. L'Eva conserva esborranys a la carpeta.
- 951 m² i UTM 418215/4595648 no són a cap fitxer: l'Eva els treu del Cadastre/visor → NT honest + proposta.
- Plànols de catàleg fotografiats (fabricant de cases modulars): PB (+ porxo), 72 m² construïts: mai parcel·la.
- Comanda amb cota de mostra mal transcrita (0,6-1,4); GTL i Excel (0,6-1,2) manen.

## 3001621 CASTELLAR DEL VALLES (2026-08-23) — 10 OK / 1 CAND / 1 NT / 1 N/A / **1 ERR** / 1 CAND−
- **Primer ERR-amb-confiança de la lectura d'or**: `lab_sample_id` = "MA-1" (GTL) marcat segur; l'Eva escriu "SPT-1" (etiqueta del
  seu annex de sondeig). Lliçó: per a etiquetes que l'Eva decideix (id de mostra), el seu annex mana sobre el laboratori; si discrepen → candidats.
- **CAND−** (candidats sense el correcte): `cte_edificacio` C0 derivat de 120 m²/casa; l'Eva posa C-1 (3 × 120 = 360 m² totals). La
  definició és sobre el TOTAL construït de l'encàrrec. `cte_sol` T-1 és el valor de 4/4 pressupostos que porten la línia → candidat per defecte.
- Cota: annex DPSH (−4,0 relatiu al carrer) ≠ annex sondeig (+570,90 ICGC); l'informe diu −4,0 → l'annex DPSH mana (2 de 2 casos resolts).
- UTM de l'informe = P-1 de COORDENADES.txt (no el sondeig).
- Client canvia de versió a versió del pressupost (GRUP ALMA juny → WOOD COMFORT PROMOCIONS SLU octubre): la versió MODF + acceptació manen;
  la fitxa de camp conserva el client vell (C6) → la fitxa NO és autoritat per al client.
- El pressupost de Castellar no porta la línia CTE (1/8); les 2 fotos WhatsApp de 25.0493 són del solar (no d'un plànol): el handoff
  s'equivocava ("foto d'un plànol pot ser l'única font de plantes/superfície a Castellar"). 1.284 m² no és enlloc.
- Referència = informe v0: la redacció definitiva (títol amb 18A, 18B i 20) va venir per correu del client el 18/11 → el lector ha de
  mirar també els correus POSTERIORS a l'informe quan existeixin (nivell B: redacció del títol).

## 4001670 ALCOLETGE (2026-08-23) — 10 OK / 2 CAND / 3 NT / 1 N/A / 0 ERR
- Ampliació (no obra nova): building_type de l'encàrrec 2026 mana sobre el caixetí del projecte VELL (2022, "tancament de porxo").
- z GPS de COORDENADES.txt anòmala (+10,7 m vs ICGC): l'annex DPSH (+188,20 ICGC) mana. Validar sempre z GPS ≈ ICGC ±2 m.
- Ref. cadastral al COS del correu del tècnic (8841701CG0184S0001HH): els correus porten dades úniques.
- Arquitecte tècnic (aparellador) ≠ arquitecte: l'Eva posa el client al camp arquitecte igualment → client candidat 1.
- 'Pb' derivable d'"ampliació a la part posterior" → candidat.

## 4001607 LINYOLA (2026-08-23) — 13 OK / 1 CAND / **1 ERR**
- **ERR #2**: arquitecte segur com a PERSONA (caixetí: Josep Bunyesc Palacín); l'Eva escriu el DESPATX (pressupost: BUNYESC
  ARQUITECTURA EFICIENT). A Bell-lloc va fer el contrari (persona). → persona vs despatx: candidats, mai segur.
- Quan hi ha projecte d'arquitecte a la carpeta, el nivell A queda gairebé complet (571 m², PB, ref. cadastral, arquitecte): 14 segurs.
- Client amb 2 promotors al projecte: l'informe va a nom de qui accepta (Sílvia sola).
- L'annex de situació d'Eva etiquetava el carrer com a "CARRER FONT" (heretat d'un altre projecte): el creuament (ortofoto + projecte +
  etiqueta de mostra) el descarta — exemple de per què cap annex sol no és 'segur'.
- Derivacions de CTE (C0 per superfície total; T-1 per defecte) encerten. Regla GTL>Excel>camp per a lab_depth confirmada (1,15 vs 1,5 vs 1,75).
- Projecte amb errors propis: "720 m" d'altitud (plantilla) i "ANDAL" per NADAL: el projecte tampoc no és infal·lible fora del seu àmbit.

## 4001671 VILANOVA DE SEGRIA (2026-08-23) — 11 OK / 1 CAND⚠ / 2 NT / 1 N/A / 0 ERR
- L'arquitecte de l'informe (JUAN JOSÉ TORRES POVEDANO) NO és en cap document de la carpeta (predit per l'anàlisi): el lector ha de dir
  'no consta' + candidats (Jordi Carner/ROCAR signa l'avantprojecte) i deixar escriure. Cap lectura el pot treure.
- El client aquí SÍ que és el sol·licitant (promotora SL que encarrega directament): la regla és 'formulari p.5 / Promotor', no 'mai el sol·licitant'.
- lab_depth: referència (1,00-1,60) vs carpeta unànime (0,8-1,4) — pendent de verificar amb el .docx real (absent a Windows); marcat ⚠.
- La còpia de Windows no té el .docx de l'informe → les referències d'aquest projecte s'han de llegir amb PDF (imatge) + prudència.
- MULTICA_61.xls (13,7 MB) és el full de càlcul bicapa de l'Eva: corrobora 2 nivells; nivell B altrament.

## 4001679 ANCILES (2026-08-23) — 7 OK / 4 CAND / 4 N/A (referència desalineada) / 0 ERR
- Client = qui signa el p.5 (Alba Barrau, arquitecta) encara que el projecte vigent digui un ALTRE promotor (PICO DE OLA S.L.):
  p.5 > Promotor del plànol. Tres "promotors" segons l'època del document: el més nou NO guanya; guanya el p.5.
- 6 DPSH executats (2 dins dels sondeigs, P-5/P-6 comencen en fondària) vs 5 previstos: com es compten és decisió de l'Eva → candidats.
- Nivells: tall (2) mana sobre columna del log (1) — invers del que semblava a Bell-lloc (allà coincidien).
- Pressupost castellà amb casella CTE BUIDA (2n cas); derivació C-1 per superfície TOTAL + T-1 defecte encerta.
- Cota del "topográfico proporcionado" (client), no ICGC: l'origen de la cota varia per projecte.
- Referència V0 desalineada (plantes='C-1', superfície='T-1', dpsh=frase SPT): 4 camps N/A pendents del .doc real.

---

## Post-lectura (2026-08-23 nit) — Conversor DWG: el 564 de Tulipa NO era al DWG

- **LibreDWG `dwg2dxf` + ezdxf llegeixen els 4 DWG de Tulipa** (AC1032 i AC1027): `scripts/dwg_text_dump.py`,
  detall a `docs/DWG-CONVERSOR-2026-08-23.md`.
- **La hipòtesi "PARAMETRES URBANISTICS.dwg porta els 564 m²" era FALSA.** El DWG porta superfícies de PLANEJAMENT
  (PARCEL·LA 1 = 358,75 / PARCEL·LA 2 = 491,24, divisió proposada). El 564 de l'Eva és la superfície gràfica del
  Cadastre: WFS INSPIRE `areaValue` de la RC 3445105DF2934E0001GG (C/ Tulipa 3), llegida ara automàticament del
  caixetí del TOP.dwg (que també porta la RC de Tulipa 1 = 506 m², el promotor i l'adreça). El NT* "ERR condicional"
  de `superficie_parcela` de Tulipa queda rebaixat a NT genuí: el valor no és a cap fitxer de la carpeta.
- **Regla nova (skill v0.6)**: DWG llegibles si hi ha `dwg2dxf`; superfícies de planejament = candidats etiquetats
  (no competeixen amb el Cadastre); RC del caixetí del topogràfic = font de `referencia_catastral` (candidats).
- **Confirmació del Pas 0 des d'una font nova**: el TOP.dwg arrossega un bloc de plantilla amb el caixetí SENCER
  d'un altre projecte (Òrrius 2023, un altre promotor i una altra RC) — llegir valors sense context hauria estat
  un ERR de manual.

---

## Post-lectura (2026-08-23 nit, 2) — n/a de Vilanova i Anciles tancats amb els PDF dels informes

- **Els PDF dels informes (`PDF/4001671_informe.pdf`, `PDF_V0/4001679_informe_V0.pdf`) tenen capa de text** (Word→PDF):
  la premissa "el PDF és imatge" només val per a les pàgines d'annex. Per a verificar valors de la narrativa i la Tabla 1,
  el PDF basta — no calen els .docx.
- **Vilanova `lab_depth` ⚠ RESOLT**: l'informe real diu "SPT1 0,80-1,40m" (p.7) i "SPT-1 0.80-1,40m" (p.9). La carpeta
  (comanda, Excel, full TPS: 0,8-1,4) tenia raó; el "-1,00 a -1,60" d'`eva_reference_values.json` era un slot desalineat
  de l'extractor de referències, no un valor de l'Eva. Lliçó: **davant d'un conflicte carpeta-unànime vs referència,
  sospita primer de la referència** (2n cas després de Tulipa).
- **Anciles**: Tabla 1 (p.4) porta "Superficie de la parcela (m2) 1655.01" (= decisió segur; Cadastre WFS 1656) i
  "5 viviendas con Pb + 1Pp + Bc / 2 viviendas con Ss + Pb + 1Pp + Bc"; p.8: "6 ensayos DPSH (P-1 a P-6)… P-5 y P-6
  a continuación de los sondeos S-2 y S-1" — el candidat 1 de la lectura d'or, literal. També "Superficie construida
  total (m2) 1273.79" (útil per a CTE: > 300 → C-1).
- **Regeneració de referències**: no es regeneren (no hi ha .docx reals accessibles; no s'escriu a les còpies de
  Windows). El registre correcte són els `comparison_addendum_2026-08-23` dels `_decisions.json` i l'ANALISI §11.1.
