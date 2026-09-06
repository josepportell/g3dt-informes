# /g3dt-llegir-projecte

Llegeix TOTS els documents d'una carpeta de projecte G3 com ho faria un geòleg que l'obre per primer cop, i escriu per a cada
document un JSON amb els candidats del **nivell A** (15 camps d'identitat de l'informe) amb ubicació i cita literal. Al final
escriu `_decisions.json` amb tres estats per camp: `segur` / `candidats` / `no_trobat`. **Mai un camp buit, mai falsa confiança.**

<command-name>g3dt-llegir-projecte</command-name>

v1.9 (2026-09-05, nit): un N30 IMPRÈS («R» o un número) sense registre de cops és una lectura, no una inferència: candidat amb nota «sense registre». Linyola: la «R» era a 3 documents (annex DPSH p.3 «SPT-1 / 1,0 a 1,5 / R», tall «N=R» al contacte de P-3, full manuscrit «50» al primer tram) i el lector 1.6 va deixar el valor buit per «sempre registre».
v1.8 (2026-09-05, L1): el «Full d'assaig SPT/MI/Mostra alterada» del manuscrit TPS (PENETROS p.3) emet SEMPRE una fila `spt_ma_tests` amb `n30.registre` (les 4 caselles de Colpeig 15/30/45/60); és l'únic registre de cops quan no hi ha annex de sondeig. Linyola: el lector 1.6 va llegir la cota i l'etiqueta de la mostra d'aquest full però no la fila de l'assaig (n30 en blanc; l'or i el signat diuen R).
v1.7 (2026-09-05): `referencia_catastral` completa declarada pel proveïdor → `segur` (Pas 3; abans «mai segur sense consulta del Cadastre»). Cap canvi de lectura: el consolidador (R5, `_FIELD_AUTHORITY`) honora `context.authority_for` a conf ≥ 0,5 per a RC, superfície, plantes, nivells (tall + annex) i client (formulari p.5).
v1.6 (2026-08-31): fila de cobertura des de la llegenda del tall / annex de sondeig, sense fondàries si no estan impreses (Pas 3b, bloc «Nivells del sòl»).
Versió 1.5 (2026-08-25, Fase 12) — consolidació Python-first: en producció el runner consolida SEMPRE amb Python (`automation/lectura/consolidate.py`: cada `tier_a` esdevé candidat, `_g3_templates.json` = autoritat A, guards del contracte, sistema de cotes, cap candidat inventat) i NOMÉS crida aquest skill amb `--consolida --only-fields a,b` per als camps en conflicte real (dues fonts A que discrepen). Mode nou al Pas 5b. Vocabulari: `nivell_freatic` absent → `No detectat` (Pas 3b).
Versió 1.3 (2026-08-24) — claus CANÒNIQUES de les files de `tables` (E2E Castellar: el productor va escriure `prof_extraccio`, `punt`/`cota_inici` al sondeig… i l'or `profunditat`, `sondeig`/`cota`; la UI i el generador necessiten un sol nom). Llista al Pas 5.
v1.4: pre-extracció determinista (2026-08-25): en mode --only el runner deixa text/PNG per pàgina, cel·les i colors d'Excel, cos de correu a validation/lectura/_preext/ (inventari clau preext); el skill llegeix aquests fitxers, fa zoom amb scripts/render_clip.py i escriu amb scripts/write_doc_json.py. Sense pre-extracció (preext absent/error) → procediment v1.3.
v1.2: nom canònic del JSON per document en mode `--only` (coincideix amb `safe_doc_name` del runner, que és qui el llegeix): path RELATIU sencer, sense extensió, tota seqüència no alfanumèrica → `_`, sense `_` inicial/final, minúscules. Ex.: `25.0647/PRESSUPOST GEOTEC.BELL-LLOC.pdf` → `25_0647_pressupost_geotec_bell_lloc.json`.
v1.1: el `registre` de l'SPT va DINS de la cel·la `n30` (subcel·la amb la seva pròpia font), no com a germà: el validador de contracte exigeix `n30.registre` i la UI el mostra al popup de l'n30 (creuament de l'acceptació Fase 0).
v1.0: contracte v1 per al wizard headless (`docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md`): dialecte únic `estat`/`font`, 22 claus planes a `fields`, arguments nous `--inventory` i `--consolida` (Pas 5b), escriptura atòmica, i capçalera `source_md5`/`skill_version`/`schema_version` a cada JSON.
v0.9: lliçons de la lectura d'or de TAULES (8 agents cecs, 7 projectes comparats amb informes: 1 ERR → regla del sistema de cotes; B80→zona B79-B82; N.F./Nivells per COLOR de cel·la; n30 mai segur; micro-regles de format). Evidència: `docs/golden-read-taules/`.
v0.8: anatomia de l'ANNEX DE SONDEIG (la matriu que l'Eva usa com a font de nivells i litologies; assenyalada pel Josep, verificada a Bell-lloc) + litologia: annex sondeig «Descripció dels materials» passa PRIMER, tall segon.
v0.7: Pas 3b: regles d'or per a les TAULES de l'informe (dades per fila/nivell), derivades de comparar les taules dels 7 informes signats amb els documents del corpus; verificades per mostreig (Castellar, Bell-lloc, Alcoletge), pendents de lectura d'or completa de taules.
v0.6: DWG llegibles via LibreDWG `dwg2dxf` + `scripts/dwg_text_dump.py` (verificat amb els 4 DWG de Tulipa; `docs/DWG-CONVERSOR-2026-08-23.md`).
v0.5: clarificacions del hold-out headless (3 projectes, ERR = 0; feedback dels executors a `docs/holdout-headless/_RESULTATS.md` §6).
v0.4: derivat de la lectura d'or dels 8 projectes (`docs/golden-read/`; resultats: ANALISI §11 — 80 OK / 17 CAND / 10 NT / 2 ERR, tots dos convertits en regla aquí).
v0.2: Pas 0 (context del document abans de llegir-lo; reflexió del Josep) + bloc `context` al JSON + lliçons de Tulipa.

## Arguments

`$ARGUMENTS` = path de la carpeta del projecte (requerit) `[--out DIR]` `[--only FITXER]` `[--inventory FILE]` `[--consolida]` `[--only-fields a,b,…]`

- `--out DIR`: on escriure els JSON (defecte: `{projecte}/validation/lectura/`; en dry-run: `docs/golden-read/{expedient}/`).
- `--only FITXER`: llegeix només aquest document i escriu el seu JSON (una crida per document = forma headless de producció).
- `--inventory FILE`: JSON d'inventari escrit pel wizard (llista completa de fitxers del projecte amb md5, duplicats i route).
  En mode `--only` és el teu context creuat: llegeix-lo ABANS del document per aplicar el Pas 0 (saber què més hi ha a la
  carpeta, detectar duplicats i versions) sense obrir els altres fitxers. Si no es passa o no existeix, continua sense i anota-ho.

### Pre-extracció (mode --only)

1. L'inventari porta, per a cada document amb route `claude`, una clau `preext` amb `dir`, `kind`, `files` (paths absoluts) i `meta`. **Abans d'obrir res**, llegeix `_inventory.json` (Pas 0, context creuat) i localitza l'entrada del teu `--only`.
2. **No executis `fitz`, `xlrd`, `openpyxl`, `extract_msg`, `PIL`, `ls`, `find` ni `md5sum`.** El text de cada pàgina és a `page-N.txt` (si `meta.text_ok[N]` és false, és brossa o escaneig: no t'hi refiïs). La pàgina sencera és a `page-N.png` (150 dpi). Les meitats (`page-N-left/right.png` o `-top/bottom.png`, 220 dpi) **només existeixen per a les pàgines sense text llegible** (`meta.halves_pages`). Excel: `sheet-i.cells.txt` (`REF<TAB>valor`, per citar `Full!REF`), `sheet-i.csv`, i **`sheet-i.colors.txt`** (una línia per cel·la amb fons o font de color: `REF<TAB>bg=#RRGGBB<TAB>font=…<TAB>valor`; **fitxer buit = cap cel·la de color al full**, és la comprovació de color del Pas 3b, ja feta). Correu: `body.txt` + `attachments/` (amb `already_in_folder` al meta si l'adjunt ja és solt a la carpeta: no el llegeixis dos cops). Imatge: `image.png`. El md5 del document és `source_md5` del meta / `md5` de l'inventari.
3. **Llegeix amb economia, com ho faries amb el document a la mà:** primer el `.txt` de les pàgines (barat); després la sencera de les pàgines que aporten dades del nivell A (caixetí, blocs CLIENT/OBRA, taules, signatures) — no de les de condicions generals. Mira les meitats només si existeixen i la sencera no es llegeix. Si necessites més resolució en una zona concreta (caixetí, etiquetes petites, manuscrit), usa `.venv/bin/python scripts/render_clip.py PDF --page N --clip x0,y0,x1,y1 --dpi 300-500 --out /tmp/clip.png` (fraccions 0-1) i `Read` del resultat. **Aquest és l'únic codi que executes per mirar.** Si `preext.error` no és null o falta `preext`, torna al procediment normal (fitz) i anota-ho a `reading_notes`.
4. Si `kind == "unsupported"` (DWG…), aplica el Pas 1.3 (dwg_text_dump) o marca `no llegible`.
- `--consolida`: NO llegeixis cap document del projecte. Llegeix els JSON per-document ja escrits a `--out` i aplica el
  Pas 5 per escriure `_decisions.json`. Vegeu el Pas 5b.
- `--consolida --only-fields a,b,…` (v1.5, la forma de PRODUCCIÓ): el runner ja ha escrit `_decisions.json` amb Python; tu
  decideixes NOMÉS les cel·les llistades i escrius `_consolida_only.json`. Vegeu el Pas 5b, mode `--only-fields`.

Exemples:
```
/g3dt-llegir-projecte /mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC --out "docs/golden-read/4001612 BELL-LLOC"
/g3dt-llegir-projecte /mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC --only "25.0647/PRESSUPOST GEOTEC.BELL-LLOC.pdf" --inventory "…/validation/lectura/_inventory.json"
/g3dt-llegir-projecte /mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC --consolida --out "…/validation/lectura"
```

Entorn: `.venv/bin/python` del repo té `fitz` (PyMuPDF), `openpyxl`, `xlrd`, `extract_msg`, `python-docx`, `PIL`. Sense `unzip` (usa `zipfile`).
Mode headless: no facis cap pregunta; si dubtes, baixa d'estat (`segur` → `candidats` → `no_trobat`) i anota-ho a `note`.
Escriu SEMPRE de forma atòmica: fitxer temporal al mateix directori + `os.replace` (el wizard llegeix els JSON tan bon punt apareixen). En aquest skill, això ho fa `scripts/write_doc_json.py`.

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
  per als valors, el manuscrit es llegeix per si porta alguna cosa que l'Excel no té (punt 0, N.F., croquis, data **i el full
  d'assaig SPT/MI/MA de la p.3: el colpeig per trams NO és a l'Excel, vegeu la taula «Assaigs SPT / MA»**). Un annex
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
- **`street_address_struct`** (concepte EXTRA, no és cap dels 15 camps): quan un document et doni l'adreça de l'obra,
  emet TAMBÉ una entrada `tier_a` amb `concept_id: "street_address_struct"` i com a `value` aquest objecte. Serveix
  perquè el Cadastre és estrictíssim amb com s'escriu una adreça i la mateixa obra apareix escrita de maneres
  diferents dins d'un mateix projecte. **Va a `extra_concepts`; no toca cap variable de l'informe.**
  ```json
  {"tipus_via": "carrer|plaça|avinguda|carretera|passeig|camí|travessia|rambla",
   "nom_via": "el nom SENSE el tipus de via, tal com el diu aquest document",
   "nom_via_alternatives": ["altres grafies del MATEIX carrer"],
   "portals": ["18A", "18B", "20"],
   "municipi": "forma oficial llarga si la saps",
   "municipi_alternatives": ["formes curtes o variants que surtin als documents"]}
  ```
  **Les alternatives són grafies del mateix lloc, mai llocs diferents.** Hi van: xifres ↔ lletres
  (`11 de Setembre` ↔ `Onze de Setembre`), català ↔ castellà (`Telègrafs` ↔ `Telégrafos`), accents i dobles lletres
  (`Girassols` ↔ `Girasols`), abreviatures (`Mn.` ↔ `Mossèn`), articles (`Arbrells` ↔ `Arbrells, dels`). **NO** hi va
  un carrer veí, ni el carrer de l'altra cantonada, ni una endevinalla.
  Exemples reals del corpus:
  ```json
  {"tipus_via": "carrer", "nom_via": "Arbrells", "nom_via_alternatives": ["Arbrells dels"],
   "portals": ["18A", "18B", "20"], "municipi": "Castellar del Vallès", "municipi_alternatives": ["CASTELLAR DEL VALLES"]}
  {"tipus_via": "carrer", "nom_via": "Clot de la Llacuna", "nom_via_alternatives": ["Clot de Llacuna"],
   "portals": ["16"], "municipi": "Linyola", "municipi_alternatives": []}
  {"tipus_via": "plaça", "nom_via": "Onze de Setembre", "nom_via_alternatives": ["11 de Setembre"],
   "portals": ["5"], "municipi": "Bell-lloc d'Urgell", "municipi_alternatives": ["BELL-LLOC"]}
  ```
  Regles dures: **`nom_via` i `municipi` són obligatoris** (sense un dels dos, val més no emetre l'objecte); màxim 8
  alternatives per llista i 6 portals; els portals són `\d{1,4}` amb una lletra opcional (`18A`), mai pisos ni portes.
  Python ho valida (`automation/lectura/address_struct.py`) i **descarta l'objecte sencer si no encaixa**, tornant al
  text lliure: un objecte mal format no fa cap mal, però tampoc no ajuda.

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
  l'arquitecte o escrita al correu d'encàrrec, COMPLETA (14/20 caràcters) i sense contradicció → `segur` amb nota «única font del
  proveïdor» (or: Linyola, Alcoletge, Anciles; consolidador R5 2026-09-05). Fragments de mapa («98417») o «Polígon 6, Parcel·la 105-B»
  no són referències → mai segur.
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
- `profunditat_assolida`: peu **"Rebuig a -X,XX m"** de l'Excel DPSH = fondària EXACTA del rebuig (verificat Castellar:
  -1,08/-0,48/-0,76/-1,55 = l'informe). **La cel·la NO és fixa: cerca "Rebuig a" a la zona B79-B82** (B80 a la majoria, B81 a
  Alcoletge i Tulipa). L'última fila amb cops de la columna C és l'interval de 20 cm, NO la fondària assolida: usar-la només
  si el peu no hi és, i anotar-ho. Signe sempre negatiu a l'informe.
- `rebuig` (Si/No): peu "Rebuig a" present → Si. Sense peu i última lectura sense R → No (aturada per potència).
- `nivell_freatic`: columna `N.F.` de l'Excel DPSH (capçalera fila 16) > manuscrit PENETROS. **La marca pot ser un COLOR de
  cel·la, no text** (Alcoletge: llegenda de colors a les files 79-80 — Nivell 1 / Nivell 2 / Humitat; cal `xlrd`
  `formatting_info=True`). Compte: la llegenda "Nivell 1|2" de les files 79-80 pot ser NOMÉS plantilla (Tulipa: idèntica als
  4 fulls, cap marca real) — una llegenda no és una transició. "No detectat" NOMÉS si la columna és buida (text I color) a
  tots els fulls — i anota a `reading_notes` que has comprovat els colors (`formatting_info=True`), perquè el
  consolidador cec ho pugui verificar. **Vocabulari (v1.5): l'absència s'escriu sempre `No detectat`** (mai `No indicat`,
  `no consta`, `cap marca`, `null` sense nota): és el que l'Eva escriu a la taula i el que el comparador d'or espera; el
  consolidador Python ho canonicalitza igualment, però el valor literal ha de ser aquest. **"Humitat" ≠ aigua franca però SÍ que va a la taula**: l'Eva titula la columna "Humitat (m)" i hi escriu
  la fondària (-1,00 a Alcoletge, d'humitat, no de nivell freàtic) — llegeix el valor i emet el matís (humitat|aigua).

**Taula "Sondeig a rotació" — una fila per S-x (`sondeig_tests[]`):** cota, profunditat assolida (annex sondeig), `spt_ma`
(comptar del GTL + comanda fila 35 + annex), nivell freàtic (annex sondeig). L'albarà TPS "Assaigs SPT: No" no mana (regla existent).
- **⚠ REGLA DE L'ERR de la lectura d'or de taules (Castellar): la cota del sondeig A LA TAULA segueix el SISTEMA de cotes del
  projecte.** Si les cotes DPSH són relatives ("respecte el carrer": -4,0/-4,2), la del sondeig també és relativa (Eva: -4,20),
  NO l'absoluta del `z:` de l'annex (570,90) encara que 2 fonts la confirmin — el z absolut és `cota_referencia`, no la cel·la
  de la taula. Amb sistema mixt (DPSH relatiu + z absolut) → `candidats` [relativa-del-sistema primer | absoluta], MAI segur
  l'absoluta. Amb tot el projecte en absolut (Bell-lloc, Anciles), l'absoluta és correcta i pot ser `segur`.
- `spt_ma`: emet els COMPTES (n_spt, n_tp, n_ma), no la cadena: el format de l'Eva és inestable ("1/--" Bell-lloc, "1/0"
  Castellar, "1/0/0" triple SPT/TP/MA a Anciles). El generador formata.

**Taula "Assaigs SPT / MA" — una fila per assaig (`spt_ma_tests[]`):** id i punt i fondària = regles `lab` existents (annex de
l'Eva mana per l'etiqueta). `litologia` = la del nivell d'on surt la mostra (vegeu `soil_levels`); si l'interval cau a cavall
d'una transició (Bell-lloc SPT a -1,00/-1,60 amb límit a -1,10; Alcoletge material recuperat del N2 amb interval al N1) →
candidats amb els dos nivells. Per a MA (mostra alterada) sense colpeig, `n30` = no_trobat amb nota (l'Eva escriu "--").
- **El «Full d'assaig SPT/MI/Mostra alterada» del manuscrit TPS (PENETROS p.3, un bloc per assaig) emet SEMPRE una fila** amb `id`
  (`Assaig de referència`), `punt`, `profunditat` (`de la cota de / fins a la cota`), `litologia` (`Descripció dels materials`) i
  `n30.registre` = les 4 caselles `Colpeig 15/30/45/60` tal com són (buides = null). Sense annex de sondeig és l'ÚNIC registre de
  cops del projecte (Linyola, Alcoletge, Rubí, Vilanova): que l'Excel DPSH mani per als N20 no vol dir que aquest full no aporti
  res. Una sola casella amb ≥ 50 i la resta buides = rebuig al primer tram → `n30` candidats «R» amb nota «50 cops al primer
  tram de 15 cm» (Linyola: signat N30 = R). Si la mostra és MA, vegeu la regla anterior (`--`).
- **`n30` MAI segur — sempre `registre` (segur, els cops per tram de 15 cm) + candidats de la suma.** El criteri de suma de
  l'Eva NO és estable: Rubí (16/20/20/24→40), Alcoletge (5/9/11/33→20) i Anciles (2/3/3/3→6) usen els 2 trams centrals, però
  l'informe de Bell-lloc diu 54 amb registre 24/34/28/30 (centrals=62; el TALL de la mateixa Eva diu 58) — incoherència
  interna d'Eva, PREGUNTA OBERTA. Candidats: [suma trams centrals | el N imprès al tall si hi és | R si rebuig]. Un R al
  primer tram (colpeig 50) → n30 = "R" pot ser segur (Castellar, Linyola).
- **«Sempre registre» NO vol dir «sense registre, sense valor».** Si el document imprimeix directament l'N30 —una «R» o un
  número— sense el colpeig per trams (annex DPSH, columna «Mesura de par»: «SPT-1 / 1,0 a 1,5 / R»; tall: «N=R» al contacte;
  GTL o comanda amb un N escrit), **escriu-lo com a candidat de `n30` amb la nota «sense registre»**: és una lectura literal,
  no una inferència, i el consolidador la necessita per no deixar la cel·la en blanc. Linyola (2026-09-05): la «R» era a tres
  documents i el lector la va posar només a la cita, amb el valor buit; la fila va quedar en blanc fins a re-llegir el manuscrit.

**L'ANNEX DE SONDEIG — anatomia (la font principal de nivells i litologies quan existeix):** plantilla G3 «Sondeig a rotació
amb batería contínua» — `PDF/ANNEXES/{exp}_sondeig.pdf` (o `ANEJOS/{exp}_sondeos.pdf` en castellà). FreeHand → **text brossa:
SEMPRE lectura visual** (render ≥ 110 dpi). Present NOMÉS als projectes amb sondeig a rotació (4/8 al corpus: Bell-lloc,
Castellar, Anciles, Tulipa ×2 cases); sense sondeig, nivells = tall i SPT/mostres = comanda + GTL. És una matriu, un full per
sondeig; columnes i què alimenta cadascuna (verificat Bell-lloc):
- capçalera: `Sondeig nº` (S-1), `Obra` (frase completa — la redacció "entre el carrer X i el carrer Y" de l'informe),
  `Client` (= sol·licitant, p. ex. "ARQ BOSCH NOVELL"), `Data d'inici/fi` (dia del sondeig, candidat 2 de `field_date`),
  `Coordenades UTM x/y/z` (**z = `cota_referencia`**), `Empresa` (TPS), `Tècnic` (Eva).
- `Unitat litològica` (NIVELL 1, NIVELL 2…) → `num_soil_levels` i fondàries de transició (on canvia el NIVELL).
- `Descripció dels materials` → **la redacció de litologia de l'informe surt d'aquí** (annex: "Graves incloses en matriu
  sorrenca d'aspectes carbonatats" → informe: "Graves en matriu sorrenca carbonatades").
- `Columna litològica` (gràfica) + `Nivell freàtic` (marca) → NF de la taula de sondeig.
- Bloc `Muestras y ensayos in situ`: `Tipus de mostra` (SPT-1), `Prof. de extracció` (-1,00 a -1,60 → `lab_depth`),
  **`Registre`** (cops per tram de 15 cm, p. ex. 24/34/28/30 → l'N30 de l'informe se'n deriva; llegeix els 4 valors i
  proposa'ls com a candidats amb la suma dels trams centrals, no en triïs un de sol).
- `Testimoni recuperat`, `R.Q.D.`, columnes de laboratori: no alimenten cap taula de l'informe (no les transcriguis).

**Nivells del sòl (`soil_levels[]`) — alimenta 5 taules (nivells, permeabilitat, sulfats, sísmica, geotècnica):**
- `nom` ("1er nivell", "2on nivell") i ordre: regla `num_soil_levels` existent (el TALL mana per al NOMBRE — Anciles: tall 2,
  log 1 → informe 2).
- **Capa de cobertura sense número.** Si la llegenda del tall (`annex_tall`) o la «Descripció dels materials» de l'annex de
  sondeig anomena una capa superficial **sense número de nivell** («Terreny vegetal», «Sòls vegetals», «Reblert», «Relleno»,
  «Cobertura»), EMET una fila pròpia **abans** del nivell 1: `nom = "<nom de la llegenda> (cobertura, sense número)"`,
  `litologia` = text de la llegenda, `de` = `"0,00"` només si el document ho imprimeix (si no, `null`), `a` = la xifra impresa
  si n'hi ha, si no `null`. **No mesuris píxels ni estimis gruixos gràfics.** La cobertura NO compta a `num_soil_levels`
  (regla existent). Castellar ja ho fa («Terreny Vegetal (sense número a la llegenda)»); Bell-lloc no ho feia.
- `litologia`: **`Descripció dels materials` de l'annex de sondeig primer** (és la que l'Eva condensa a l'informe; verificat
  Bell-lloc), llegenda del tall segon ("1er nivell: Graves amb sorres"). **L'Eva re-redacta a l'informe**: la redacció exacta
  és sempre `candidats`, MAI segur per a la cadena literal. Sense annex de sondeig: tall únic candidat.
- `de` / `a` (fondàries de transició): cotes del tall + marques `Nivell N` de l'Excel DPSH (columna al costat del peu, B79) +
  annex sondeig. Són el que la sísmica usa com a gruix i la geotècnica com a rang de Nb: si els documents discrepen (esborrany
  PNG vs annex PDF — regla d'esborranys existent), candidats.
- `mostra_del_nivell`: el nivell que conté `lab_depth` — la fila de sulfats de l'informe porta AQUEST nivell, no sempre el 1r
  (Linyola: mostra al 2on nivell). Lectura + interval, no judici.

**Taula de plantes/superfícies:** `num_floors` i `superficie_parcela` són els escalars existents; s'hi afegeix
`superficie_construida` (correu d'encàrrec "Pb de 280m + p1 de 86" → l'Eva escriu "280+86"; taula de planejament; pressupost).
Emet COMPONENTS i TOTAL: l'Eva de vegades escriu la suma (Rubí: "72+20 porxada" → informe "92") i de vegades els sumands
(Bell-lloc: "280+86"). Multi-habitatge: l'Eva pot posar el valor PER CASA (Castellar: "120 m2" d'1 de 3) → candidats.
**L'etiqueta de la fila de parcel·la segueix la FONT del valor**: "segons plànols cadastrals" / "segons cadastre" / "segons
informació aportada" / "segons projecte" — emet la font amb el valor perquè el generador triï l'etiqueta. Ampliacions
(Alcoletge): l'Eva escriu "Superfície construïda ampliació" — si l'encàrrec és una ampliació, anota-ho.

**Què NO llegeix el skill (Tier B, no ho intentis):** K (m/s), Tipus de terreny sísmic + Coef. C, γ/c/φ/E, qualificació
d'agressivitat. Sí que en llegeixes els INPUTS (Nb mitjans de l'Excel per rang de fondària els pot derivar Python; tu dona
fondàries i litologies bones).

## Pas 4 — Sortida: un JSON per document

```json
{"source_path": "relatiu a la carpeta", "source_md5": "md5 del fitxer font", "skill_version": "1.0", "schema_version": 1,
 "document_type": "pressupost_g3|fitxa_camp_g3|comanda_lab_g3|plan_cost_g3|dpsh_excel|annex_sondeig|annex_tall|annex_planol_situacio|annex_dpsh|annex_fotografies|informe_laboratori|consulta_cadastre|planol|projecte_arquitecte|correu|foto|full_camp_manuscrit|coordenades_gps|altre",
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

Escriu cada JSON **immediatament** després de llegir el document (el disc és la memòria) amb **una sola ordre**: `.venv/bin/python scripts/write_doc_json.py --out OUT_DIR --expect-source-path "REL" --expect-md5 MD5 <<'EOF'
{...payload...}
EOF`. El script valida el payload, tria el nom canònic i escriu de forma atòmica; NO facis tmp+os.replace a mà, NO rellegeixis el fitxer després (si el script diu OK, està escrit). Si diu ERROR, corregeix el payload i torna-ho a executar.
**Nom del fitxer en mode `--only` (canònic, el runner l'espera):** el path RELATIU sencer del document, sense extensió,
substituint tota seqüència de caràcters no alfanumèrics per `_`, sense `_` inicial/final, en minúscules, + `.json`
(`25.0647/PRESSUPOST GEOTEC.BELL-LLOC.pdf` → `25_0647_pressupost_geotec_bell_lloc.json`). En dry-run (lectura d'or) el
nom és lliure.
**Tot camp que llistis a `context.authority_for` ha de tenir la seva entrada a `tier_a` amb `quote`** (o constar a
`not_present` amb motiu): el consolidador (Pas 5b) és cec — un senyal que només viu al bloc `context` no pot pujar mai
a `segur` (lliçó de l'acceptació Fase 0: el promotor del caixetí d'A.01 anotat a `for_whom` sense entrada tier_a). Els duplicats (mateix md5, mateix número
d'informe, "X amb punts") s'anoten com a tals i **no** compten com a fonts independents. Les entrades `NOT_client_name` serveixen per
deixar constància explícita del que s'ha descartat i per què.

## Pas 5 — `_decisions.json` (schema v1)

Estructura de nivell alt (contracte v1 del wizard; el validador Python és `automation/lectura/contract.py`):

```json
{"schema_version": 1, "project": "…", "generated": "…", "skill_version": "1.0",
 "fields": {"<clau plana>": {"estat": "segur|candidats|no_trobat", "value": "…|null",
            "candidates": [{"value": "…", "font": "document + posició", "quote": "text literal"}],
            "rule": "…", "sources_checked": ["…"], "note": null}},
 "tables": {"dpsh_tests": {"estat_bloc": "…", "rows": []}, "sondeig_tests": {}, "spt_ma_tests": {}, "soil_levels": {},
            "superficie_construida": {}},
 "__forma_bloc_buit": {"estat_bloc": "no_trobat", "rows": [], "sources_checked": ["…"]},
 "sources_read": ["…"], "notes_estructurals": ["…"]}
```

Les **22 claus planes** de `fields` (els 15 camps aplanats — `lab`/`cte`/`utm` desglossats, mai niuats):
`expedient, client_name, street_address, municipality, architect_name, architect_company, building_type, num_floors,
superficie_parcela, field_date, cota_referencia, num_soil_levels, num_dpsh_tests, utm_x, utm_y, referencia_catastral,
lab_testing_company, lab_sample_id, lab_depth, lab_location, cte_edificacio, cte_sol`.
(`superficie_construida` i la resta de dades per fila viuen a `tables`, Pas 3b.)
Un bloc de `tables` sense cap font que l'alimenti s'emet SEMPRE amb la forma canònica del bloc buit
(`estat_bloc: "no_trobat"`, `rows: []`, `sources_checked` amb on s'ha buscat) — mai `{}` ni absent.

Dialecte ÚNIC de claus (v1.0; a les lectures d'or hi convivien `status`/`source` i `estat`/`font` — ja no):
**`estat`** (mai `status`), **`font`** (mai `source`), `quote`, `value`, `candidates`, `rule`, `sources_checked`, `note`.

Per a cada clau de `fields` (i cada cel·la de `tables`, amb els mateixos 3 estats per fila — una fila amb totes les
cel·les de 2+ fonts coincidents és `segur`; una litologia re-redactable o un N30 manuscrit dubtós és `candidats`):
- `segur`: ≥ 2 fonts **independents** d'autoritat A coincideixen, o 1 font A sense cap contradicció. Sempre amb `candidates[]`
  (value, font, quote) perquè la UI mostri d'on surt.
- `candidats`: llista ordenada ≤ 3 amb font i cita; `value` = `candidates[0].value` (el que la UI pre-omple en ambre).
  També quan hi ha multiplicitat real (cantonada, dues parcel·les).
- `no_trobat`: `value` = null, amb `sources_checked[]` (on s'ha buscat) no buit.
- `rule`: la regla del Pas 3 aplicada, en una frase.

Restriccions dures del contracte (el validador les REBUTJA — no són estil, són el criteri d'or codificat):
- `n30` mai `estat: segur`; la `litologia` de `soil_levels` mai `segur` per a la cadena literal (Pas 3b).
- **Claus canòniques de cada fila de `tables` (exactes, cap sinònim):**
  `dpsh_tests`: `punt, cota_inici, profunditat_assolida, rebuig, nivell_freatic` ·
  `sondeig_tests`: `sondeig, cota, profunditat_assolida, spt_ma, nivell_freatic` ·
  `spt_ma_tests`: `id, punt, profunditat, litologia, n30` ·
  `soil_levels`: `nom, litologia, de, a, mostra_del_nivell` ·
  `superficie_construida`: `components, total, etiqueta_font`.
  Dades extres útils (empresa, sondista, registre N20 per fondària…) van a `extra` dins la fila, mai com a cel·les noves.
- El `registre` (cops per tram de 15 cm) va DINS de la cel·la `n30` (`n30.registre`, subcel·la amb estat/font/quote
  propis), mai com a cel·la germana de la fila.
- `segur` i `candidats` porten sempre `candidates[]` no buit (≤ 3).
- `nivell_freatic` porta `matis` ∈ {null, "humitat", "aigua"}.
- `spt_ma` emet comptes (`n_spt`, `n_tp`, `n_ma`), mai cadena formatada; `n30` emet `registre` (segur) + candidats de la
  suma; `superficie_construida` emet `components[]` + `total` + `etiqueta_font`. El lector emet dades; el generador formata.

Criteri únic: **ERR-amb-confiança = 0**. Davant del dubte, baixa d'estat. No ompliu "perquè segur que és això".

## Pas 5b — Mode `--consolida` (la crida final del pipeline headless)

En producció la lectura és una crida per document (`--only`); la consolidació del Pas 5 es fa en una crida FINAL separada
amb `--consolida`. En aquest mode:

1. **NO obris cap document del projecte.** La teva única entrada són els JSON del directori `--out`:
   - `{doc}.json` per document llegit (Pas 4);
   - `_g3_templates.json` — senyals deterministes de les 5 plantilles G3 (cel·la exacta + cita): tracta'ls com una font
     d'autoritat A més;
   - `_inventory.json` — md5, duplicats i llista completa de fitxers (si falta, continua i anota-ho).
2. Aplica les regles del Pas 0/3/3b/5 sobre aquests senyals: independència de fonts (les aparicions derivades del mateix
   encàrrec NO són independents), autoritat per camp, duplicats per md5 (no compten dos cops), versions (`modDate` posterior mana).
3. Un document previst a l'inventari sense `{doc}.json` (timeout o error de lectura): els camps que només ell podia donar
   queden `no_trobat` amb `"lectura fallida: {doc}"` dins de `sources_checked`.
4. Normalització d'entrada: els `{doc}.json` del Pas 4 NO parlen el dialecte de sortida — porten `tier_a[]` amb
   `location`/`quote`/`confidence`. La conversió canònica és: cada entrada de `tier_a` esdevé un candidat
   `{value, font: "{source_path} {location}", quote}` del seu `concept_id`; la `confidence` i el `context` del document
   pesen en l'ORDRE i l'estat final, però no surten al `_decisions.json`. Si un JSON arriba en dialecte antic
   (`status`/`source`), normalitza'l en llegir-lo — la sortida és sempre v1.
5. Escriu `_decisions.json` (schema v1 del Pas 5) de forma atòmica a `--out`.

És la crida barata del pipeline: cap lectura de documents, només JSONs.

### Mode `--only-fields` (v1.5, Fase 12 — l'única forma de `--consolida` que el runner crida en producció)

El runner ha consolidat amb Python (`automation/lectura/consolidate.py`) i ha escrit `_decisions.json` (schema v1). Hi ha
trobat **conflictes reals** — cel·les on dues fonts d'autoritat A de documents diferents discrepen — i te les passa amb
`--only-fields`, separades per comes, com a paths: `fields.<clau>` (una de les 22 claus planes) o
`tables.<bloc>[<id de fila>].<cel·la>` (p. ex. `tables.sondeig_tests[S-1].cota`, `tables.dpsh_tests[P-2].nivell_freatic`).

1. **NO obris cap document del projecte.** Llegeix `_decisions.json` (la cel·la Python porta `candidates`, `altres` amb TOTS
   els senyals, `conflicts` amb els clusters en conflicte i `rule`), els `{doc}.json` implicats (per `context`, `note` i
   `reading_notes`), `_g3_templates.json` i `_inventory.json`.
2. Per a CADA path demanat, i només per a aquests, aplica les regles del Pas 0/3/3b/5 (independència de fonts, versions
   `modDate`, sol·licitant ≠ promotor, sistema de cotes, instrucció del client posterior…) i decideix la cel·la en dialecte
   v1: `{estat, value, candidates[≤3] (value, font, quote), rule, note}`. **Mai un valor que no sigui a cap candidat/altres
   de la cel·la Python ni a cap `{doc}.json`** (cap candidat inventat: el cas `-4,20 m` derivat sense font és l'error que
   aquesta fase elimina). Si no pots resoldre el conflicte amb els documents, deixa `candidats` amb l'ordre que creguis i
   explica-ho a `note` — el runner conserva la versió Python si la teva no passa el contracte.
3. Escriu de forma atòmica `_consolida_only.json` a `--out` amb NOMÉS les cel·les demanades:
   ```json
   {"schema_version": 1, "fields": {"<clau>": {…cel·la v1…}},
    "tables": {"<bloc>": {"rows": [{"<id de fila>": "S-1", "<cel·la>": {…cel·la v1…}}]}},
    "notes": ["…"]}
   ```
   (per a `tables`, la fila porta només l'identificador — `punt`/`sondeig`/`id`+`punt`/`nom` — i la cel·la decidida).
   No reescriguis `_decisions.json`: el runner fusiona les cel·les vàlides (`merge_only_fields`) i manté les guards
   (`n30`/`litologia`/`cte` mai `segur`).

Cost objectiu: < 3 min. Sense `--only-fields` (mode `--consolida` sencer) només s'usa amb `G3DT_LECTURA_CONSOLIDA=llm`
(mesures, pla B).

## Pas 6 (només dry-run) — Comparació amb l'informe de l'Eva

Només DESPRÉS d'escriure `_decisions.json`: obre `validation/eva_reference_values.json` i `{exp}_informe.docx`, classifica cada camp
OK / CAND / NT / ERR, afegeix `comparison_with_eva` al `_decisions.json` i cada ERR com a regla nova en aquest skill i a
`docs/golden-read/_LESSONS.md`.
