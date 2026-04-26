# Principis d'autoritat — Eva G3 Geotècnia

> Aquest fitxer és l'única font d'autoritat que el ranker LLM rep com a
> instrucció. L'ordre de seccions reflecteix la prioritat: **regles
> generals primer**; **regles per concepte** quan diferences amb les
> generals; **patrons específics** com a guies operatives. Si dues
> seccions semblen contradir-se, la més específica guanya per al seu
> domini concret.

## Índex de seccions

1. Principis generals
2. Per concepte (regles ràpides; vegeu seccions específiques per a detalls)
3. Resolució de conflictes (regla unificada)
4. Coordenades UTM (`utm_x`, `utm_y`, `utm_z`)
5. Identificació del projecte (`expedient` vs `commercial_code`)
6. Identificació de persones (architect / client / promotor / firma)
7. Bearing stratum per a paràmetres geomecànics
8. Noms d'empreses, persones, productes — preferir forma completa
9. Documents prioritaris vs prior outputs
10. Candidats provinents de calculadors deterministes

## 1. Principis generals
- Font signada per l'arquitecte (plànol, memòria) > correu informal.
- Plànol caixetí (secció de dades) > cotes interiors del dibuix per
  identificació de projecte, client, arquitecte.
- Dada manuscrita de camp > dada transcrita (Excel) en cas de discrepància
  numèrica: la manuscrita és primària.
- Informe previ d'Eva (`prior_report`) NO és autoritatiu — és un output, no
  una font (vegeu §9 per a la regla matisada).
- Quan dubtis: **deixa l'ordenació de Pass A intacta**. Pass B/C només
  hauria de re-ordenar quan té un senyal CLAR i específic; soroll genèric
  no justifica revisió.

## 2. Per concepte (regles ràpides)
- `architect_name`: caixetí del plànol > domini del remitent de l'email
  > nom de fitxer. **Detall complet a §6**.
- `num_floors`: plànol > memòria escrita > email.
- `utm_x`, `utm_y`: COORDENADES.txt de camp > plànol > geocodificació.
  **Detall complet a §4** (incloent format estricte 6/7 dígits).
- `sulfates_mg_kg`: informe de laboratori > fitxa de camp > estimació.
- `municipality`: plànol caixetí > cadastre > adreça textual.
- `geomech_*` (E, phi, cohesion, gamma): valor del **bearing stratum**,
  no del nivell superficial. **Detall complet a §7**.
- `expedient` vs `commercial_code`: identificadors diferents, mai
  intercanviables. **Detall complet a §5**.

## 3. Resolució de conflictes (regla unificada)

Aquesta regla aplica a TOTS els conceptes. Les seccions específiques (§4–§9)
poden afegir matisos per al seu domini, però mai contradir aquesta regla:

1. **Document signat > document no signat** per al mateix camp.
2. **Versió més recent** quan hi ha `version_info` o `date_info` posterior.
3. **Font primària > resum o transcripció**.
4. **Correu posterior que ANUNCIA un canvi** sobreescriu el plànol; un
   correu que només COMENTA es queda darrere del plànol.
5. Si dues fonts del mateix nivell d'autoritat donen valors idèntics i
   una tercera divergeix → marca `has_conflict=true`, posa la divergent
   al final, i explica-ho breument a `conflict_note`.
6. Si la regla específica del concepte (§4–§10) entra en conflicte amb
   aquesta regla general, **la regla específica del concepte guanya**
   per al seu domini.

<!-- Editat per Eva amb Josep. Canvis aquí invaliden tota la cache de Fase 5. -->

## 4. Coordenades UTM (`utm_x`, `utm_y`, opcionalment `utm_z`)

Format autoritari: **EPSG:25831 / ETRS89 UTM Fus 31N** per a tota
Catalunya i Aragó (Pirineu inclòs). Les unitats són **metres**, no graus.

**Forma esperada del valor**:
- `utm_x`: enter de **6 dígits**, en el rang ~280.000–460.000 per
  Catalunya (Anciles al Pirineu pot arribar a ~330.000).
- `utm_y`: enter de **7 dígits**, en el rang ~4.500.000–4.750.000.
- `utm_z` (cota referència, msnm): número de 1–4 dígits + decimals
  opcionals, en el rang ~0–2500 (l'Anciles a +1106).

**MAI acceptar com a UTM**:
- Decimals petits (p.ex. `0.70348`, `41.654531`) — això és lat/lon
  WGS84, no UTM. Si veus un candidat amb aquesta forma a `utm_x`/
  `utm_y`, és un error del LLM o un canvi de sistema de coordenades.
  **Demota'l a l'última posició** i marca `has_conflict=true`.
- Strings amb `°` / `º` o que contenen "lat", "lon", "longitud",
  "latitud" — sistemes geogràfics, no projectats.

**Font autoritativa**:
1. `ANNEXES/COORDENADES.txt` (GPS de camp d'Eva, 1 línia per DPSH amb
   format `X ; Y ; Z`).
2. Plànol arquitectònic — caixetí o annex de coordenades.
3. Geocodificació automàtica (Cadastre WFS, ICGC) — només com a
   fallback quan no hi ha font primària.

**Avís per a Pass B/C (auditor de grup)**: el grup `coordinates` ha
estat històricament destructiu (Pass C va corrompre `utm_x`/`utm_y`
substituint UTM per lat/lon decimals a Alcoletge). **Si com a auditor
de grup detectes un factor que afectaria `utm_x` o `utm_y`, el factor
ha de ser explícitament sobre la font (no sobre el valor), i la
revisió només pot promoure candidats que respectin el format
esperat (6/7 dígits enters).** En cas de dubte, deixa l'ordenació de
Passada A intacta.

## 5. Identificació del projecte

- `expedient` (número numèric llarg, p.ex. 4001670): la font autoritativa
  és el caixetí de l'informe (`*_informe.doc/.docx/.pdf`), la portada
  (`*_portada.doc`), o el peu de pàgina dels documents tècnics signats.
  Els fitxers de pressupost porten el `commercial_code` (format YY.NNNN
  com 26.0049), que NO és l'expedient.
- `commercial_code` (format YY.NNNN, p.ex. 26.0049): font autoritativa el
  pressupost signat (PDF d'oferta) i correus inicials del client.
- Els dos identificadors poden aparèixer junts; cadascun té la seva
  pròpia variable. NO confondre.

## 6. Identificació de persones

- `architect_name` (arquitecte / arquitecte tècnic / enginyer / despatx):
  - **Font autoritativa**: caixetí del plànol arquitectònic (zona
    inferior-dreta del PDF), o signatura tècnica del projecte. En
    despatxos / firmes (no individus) el caixetí porta el nom de la
    firma; aquest valor va a `architect_name`.
  - **NO usar** com a `architect_name` el nom que apareix al cos de
    l'informe en frases com *"Segons ens indica el sol·licitant, el SR.
    X, en nom propi..."*: aquesta posició descriu el sol·licitant, NO
    l'arquitecte.
  - En projectes auto-promoguts (arquitecte == client), prefereix igualment
    el caixetí del plànol abans que el cos del informe.
- `client_name` (promotor / sol·licitant / propietari):
  - **Font autoritativa**: pressupost signat, contracte, correus inicials.
  - El cos de l'informe el cita habitualment com *"sol·licitant"* o
    *"promotor"*.

### Patrons de la frase del cos i com llegir-la

La frase típica del cos de l'informe Eva és:

> "Segons ens indica el sol·licitant, el SR. X, de l'Y, en nom de Z, ..."

amb tres slots: SR./SRA./despatx (X = arquitecte), `de l'` (Y = empresa),
`en nom de` (Z = client). Eva sovint trunca o reordena aquesta frase:

- **Patró estàndard** (Bell-Lloc): tres slots plens. X = `architect_name`,
  Y = `architect_company`, Z = `client_name`.
- **Patró truncat** (Alcoletge): només "el SR. X". X probablement és el
  client (auto-promoció) o un cas de "en nom propi" implícit. **NO
  assumir** que X és l'arquitecte; mira el caixetí del plànol.
- **Patró auto-promogut** (Rubí): "la SRA. X" sola, sense empresa ni
  separació entre arquitecte i client. X és simultàniament arquitecte
  i client. Tots dos valors són X.
- **Patró firm-led** (Linyola): "FIRMA, en nom de SR./SRA. Y". La FIRMA
  és l'arquitecte (`architect_name` = firma); Y és el client
  (`client_name`). **No** facis Y = `architect_name` només perquè
  porta el prefix "Sr./Sra.".

Si Stage 4 te dóna candidats per a `architect_name` extrets exclusivament
del cos de l'informe (no del caixetí), demota'ls quan vegis qualsevol
patró truncat o firm-led, perquè l'extractor posicional és susceptible a
mis-alinear la frase amb la plantilla.

## 7. Semàntica del Bearing Stratum per a Paràmetres Geomecànics

Eva sempre reporta paràmetres geomecànics (`geomech_E`, `geomech_phi`,
`geomech_cohesion`, `geomech_gamma`) del **nivell de recolzament (bearing
stratum)** — el nivell sobre el qual es recolza la fonamentació —, NO del
nivell superficial.

Cita textual de l'informe Alcoletge (pàgina 361):

> "Un cop realitzada l'excavació afloraran superficalment els materials
> del primer nivell descrit, que degut a les seves propietats geomecàniques
> **es descarta totalment per a recolzar-hi qualsevol element de
> fonamentació**. La fonamentació haurà de quedar recolzada en els materials
> del segon nivell..."

Conseqüència operativa per a la fase d'extracció:

- En la taula "Resum de paràmetres geomecànics" Eva descriu els nivells de
  shallowest a deepest. La **darrera fila** és sempre el bearing stratum
  (excepte en perfils homogenis on només hi ha una fila).
- El `reference_extractor.py` flatteja `geotech_rows[-1]` (no `[0]`) cap
  als conceptes plats `geomech_E/phi/cohesion/gamma`.
- En perfils mono-capa, `[-1] == [0]` i el comportament és idèntic al
  legacy.
- Els paràmetres del bearing layer són els que s'usen per calcular `Qa`
  via Terzaghi-Peck, no els del nivell superficial.

Exemple Alcoletge: el 2n nivell (E>400, φ=30°, c=1.0, γ=2.0) és el bearing
layer que justifica `Qa = 3.50 kg/cm²`. El 1r nivell (rebliment feble:
E=50, φ=28°, c=0.0, γ=1.80) és descartat per Eva i no s'ha de propagar
als conceptes geomecànics finals.

## 8. Noms d'empreses, persones, productes — preferir forma completa

Quan dos candidats ofereixen el mateix concepte amb formes diferents
(p.ex. *"TPS PROSPECCIÓ DEL SUBSÒL SL"* vs *"TPS"* o *"SOIL-ASSAIG"* vs
*"TPS PROSPECCIÓ DEL SUBSÒL SL (SOIL ASSAIG)"*), **prefereix la forma
completa registrada**. Criteris d'autoritat:

1. **Forma signada/registrada > forma curta**: el nom legal complet
   (amb `S.L.` / `S.A.` / `S.L.U.` / nom de persona col·legiat) és
   l'autoritatiu. Les formes curtes (acrònims, marques) són alies.
2. **Pressupost signat / contracte / albarà signat > correu informal**:
   els documents signats porten el nom registrat; els correus i marques
   tendeixen a la forma curta.
3. **Nom oficial > "trading as" / "comercialitzat com"**: si veus
   `"X SL (comercialitzat com Y)"`, el camp ha de contenir `X SL`, no
   `Y`.
4. **Persones**: nom + cognoms complets > inicials + cognom > només
   cognom.

Exemple del Alcoletge Pass C (2026-04-26): `lab_testing_company` va
ser revisat de `"TPS PROSPECCIÓ DEL SUBSÒL SL (SOIL ASSAIG)"` (forma
completa, correcte) cap a `"SOIL-ASSAIG"` (alies comercial). Aquest
canvi va ser **incorrecte** — la forma autoritativa és `TPS
PROSPECCIÓ DEL SUBSÒL SL`. Pass B no hauria de generar factors que
prefereixin alies sobre noms registrats.

## 9. Documents prioritaris vs prior outputs

- **Demote outputs intermedis del nostre propi pipeline**:
  `*_generated*.docx` (sortida de `ReportGenerator` no signada),
  `*AUDIT_VISUAL*.docx` (sortida de l'auditor) i qualsevol caché vell
  d'altres projectes que s'hagi colat per error han d'anar al **final**
  de qualsevol llista. Si el seu valor coincideix amb el d'una font
  primària, és perquè el van copiar; si divergeix, és perquè estan
  desactualitzats.
- **Els informes signats d'Eva** (`*_informe*.doc/.docx/.pdf`) i
  **portades** (`*_portada*.doc/.docx`) **del projecte actual** són
  autoritatius per als valors d'identificació que carreguen
  (`expedient`, signatura tècnica). NO són la primera autoritat per a
  valors derivats d'altres fonts (cota, dimensions, mesures de camp,
  etc.); per a aquests valors prefereix la font primària corresponent
  (plànol, fitxa de camp, lab) i tracta l'informe com a verificació.
- **Els correus, contractes i pressupostos signats** són autoritatius
  per als seus camps (client, comercial, dates, oferta).
- **Els plànols arquitectònics** són autoritatius (caixetí + cotes
  internes) per a tot el que apareix al plànol.

## 10. Candidats provinents de calculadors deterministes

Quan vegis una font amb `source_path` que comença amb `calculator:`
(p.ex. `calculator:legacy_geotech`, document_type
`deterministic_calculator`), aquests candidats provenen d'un càlcul
determinista que codifica la metodologia d'Eva — Terzaghi-Peck per `qa_value`,
Schmertmann per `settlement_cm`, Crespo/CTE D.23/D.27 per `geomech_*`, etc.

Regles d'autoritat per a aquests candidats:

1. **Per als conceptes que el calculador computa** (qa_value,
   settlement_cm, eventualment els geomech_*), el candidat del
   calculador és **autoritatiu sobre extraccions textuals** quan els
   inputs del calculador són correctes (Nb del bearing stratum,
   geometria de la fonamentació de l'usuari, soil_type).
2. **Excepció**: si una font primària documenta un valor explícit
   d'Eva (p.ex. el plànol caixetí indica "Qa = 3.50 kg/cm²" o l'informe
   signat porta el valor com a output final), aquest valor d'Eva guanya
   sobre el calculador. Eva pot aplicar professional judgement (caps,
   bicapa, factors empírics) que el calculador no captura encara.
3. Si el valor del calculador divergeix significativament d'altres
   candidats d'alta confiança, **marca `has_conflict=true`** i posa el
   calculador al davant; el `conflict_note` ha d'esmentar la divergència
   per a revisió d'Eva.
4. **No suprimir** candidats LLM tot i tenir un calculador disponible
   — l'usuari (Eva) ha de poder veure les alternatives al wizard.

> Nota tècnica: els candidats del calculador apareixen al ranking
> només quan `G3DT_ENABLE_CALCULATOR_DELEGATION=true` (feature flag,
> Phase 1 MVP). Quan està OFF, no s'emeten i aquesta secció no aplica.
