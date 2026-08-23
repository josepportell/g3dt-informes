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
