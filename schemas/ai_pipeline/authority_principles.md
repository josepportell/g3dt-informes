# Principis d'autoritat — Eva G3 Geotècnia

## Principis generals
- Font signada per l'arquitecte (plànol, memòria) > correu informal.
- Plànol caixetí (secció de dades) > cotes interiors del dibuix per
  identificació de projecte, client, arquitecte.
- Dada manuscrita de camp > dada transcrita (Excel) en cas de discrepància
  numèrica: la manuscrita és primària.
- Informe previ d'Eva (`prior_report`) NO és autoritatiu — és un output, no
  una font.

## Per concepte
- `architect_name`: caixetí del plànol > domini del remitent de l'email > nom
  de fitxer.
- `num_floors`: plànol > memòria escrita > email.
- `utm_x`, `utm_y`: COORDENADES.txt de camp > plànol > geocodificació.
- `sulfates_mg_kg`: informe de laboratori > fitxa de camp > estimació.
- `municipality`: plànol caixetí > cadastre > adreça textual.

## Resolució de conflictes
- Entre dues versions de plànol, la més recent (`version_info` posterior o
  `date_info` més gran) guanya.
- Si un correu posterior contradiu un plànol anterior, pregunta: el correu
  anuncia un canvi? Si sí, correu guanya. Si no (és comentari), plànol guanya.

<!-- Editat per Eva amb Josep. Canvis aquí invaliden tota la cache de Fase 5. -->

## Identificació del projecte

- `expedient` (número numèric llarg, p.ex. 4001670): la font autoritativa
  és el caixetí de l'informe (`*_informe.doc/.docx/.pdf`), la portada
  (`*_portada.doc`), o el peu de pàgina dels documents tècnics signats.
  Els fitxers de pressupost porten el `commercial_code` (format YY.NNNN
  com 26.0049), que NO és l'expedient.
- `commercial_code` (format YY.NNNN, p.ex. 26.0049): font autoritativa el
  pressupost signat (PDF d'oferta) i correus inicials del client.
- Els dos identificadors poden aparèixer junts; cadascun té la seva
  pròpia variable. NO confondre.

## Identificació de persones

- `architect_name` (arquitecte / arquitecte tècnic / enginyer):
  - **Font autoritativa**: caixetí del plànol arquitectònic (zona
    inferior-dreta del PDF), o signatura tècnica del projecte.
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

## Semàntica del Bearing Stratum per a Paràmetres Geomecànics

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

## Documents prioritaris vs prior outputs

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

## Conflicts entre fonts

- Per a la mateixa variable, **prefereix el document signat** sobre el
  no-signat.
- **Prefereix la versió més recent** quan hi ha `version_info` o dates
  explícites.
- **Prefereix la font primària** sobre el resum o la transcripció.
- Si dues fonts del mateix nivell d'autoritat donen valors idèntics i una
  tercera divergeix, marca `has_conflict=true` i posa la divergent al
  final, però explica-ho a `conflict_note`.
