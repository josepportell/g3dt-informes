# Anàlisi Diagnòstica: Pipeline G3DT — Projecte Vacarisses (3001722)

Data: 2026-06-20  
Branca de treball: `fix/pipeline-routing` (base: `production/g3dt-eva-v1`)  
Context: Eva va reportar qualitat insuficient en diversos projectes al voltant del 12 de juny. Vacarisses és el cas de referència per a l'anàlisi.

---

## 1. Estructura dels fitxers de diagnòstic disponibles

El pipeline genera els següents fitxers a `validation/`:

| Fitxer | Conté | Notes |
|--------|-------|-------|
| `file_mapping.json` | Decisions de classificació per a CADA fitxer del projecte | Veritat sobre el que el scanner decideix fer |
| `concept_map.json` | Mapa de concepte→font (quins fitxers contenen quines variables) | Generada per ConceptScout (Fase 0.45) |
| `docs_extracted.json` | Extracció Python regex sobre PDFs vectorials | Limitada a un sol pas específic |
| `dpsh_extracted.json` | Resultat de visió Claude sobre PENETROS.pdf | |
| `planol_extracted.json` | Resultat de visió sobre el fitxer `architect_plan` | |
| `sondeig_annex_extracted.json` | Resultat de visió sobre el fitxer `sondeig_annex` | |
| `projecte_extracted.json` | Resultat de visió sobre el document pressupost (visió chunked) | |
| `user_data.json` | Estat final dels camps que arriben al wizard i al generador | Inclou `_sources` per cada camp |

---

## 2. Anàlisi de `file_mapping.json` — Decisions per fitxer

### 2.1 Rols assignats (correctes/incorrectes)

| Fitxer | Rol assignat | Mètode detecció | Correcte? |
|--------|-------------|-----------------|-----------|
| `26.0332/PRESSUU GEO C0 Vacarisses Marc.msg` | `project_email` | filename_pattern | ✅ |
| `4849-GTL-26 Vacarisses.pdf` | `gtl_report` | filename_pattern | ✅ (és l'informe GTL de TPS Perforaciones) |
| `ANNEXES/3001722_DPSH.xls` | `dpsh_excel` | filename_pattern | ✅ |
| `comanda laboratori_3001722_VACARISSES.xls` | `lab_order` | filename_pattern | ✅ |
| `FOTOGRAFIES/P1.jpeg` | `photo_test_point` | filename_pattern | ✅ |
| `FOTOGRAFIES/SPT1.jpeg` | `photo_spt_sample` | filename_pattern | ✅ |
| `PENETROS.pdf` | `dpsh_field_sheet`, vision_type=dpsh | filename_pattern | ✅ |
| **`plano.pdf`** | **`architect_plan`**, vision_type=planol | **filename_pattern** | **❌ INCORRECTE** |

**Problema central de file_mapping**: `plano.pdf` s'assigna com a `architect_plan` perquè el nom conté "plano". Però és un plànol topogràfic (corbes de nivell, UTM), no un plànol arquitectònic amb caixetí. El file_scanner usa patrons de nom de fitxer sense validar el contingut.

### 2.2 Fitxers ignorats que contenen informació útil

**`ACCEPTACIO/` — ignorada com a "acceptance_dir"** \
<Josep_edit> \
Ben trobat. Cal que ho corregim. \
Qui ignora `ACCEPTACIO/` com a acceptance_dir? El file_scanner? Perquè ja dius que concept_map.json sí que l'escaneja i en guarda informació. \
</Josep_edit>

El `concept_map.json` va escanejar igualment `ACCEPTACIO/Presupost Geotecnic.pdf` (PDF escanejat, 2.4MB) i va trobar:

```
client_name: 1.0      ("CLIENT: MARC VIDAL")
street_address: 1.0   ("C/DE LA BARCELONETA 23")
municipality: 1.0     ("VACARISSES")
expedient: 0.95       ("26·0332")
field_date: 0.95      ("DATA: 29/04/26")
architect_company: 1.0 ("G3 DESENVOLUPAMENT TERRITORIAL, S.L.")  ← problema: veure §3
client_nif: 0.9       ("38112117J")
contact_name: 0.9     ("MARC VIDAL BERTOSSI")
```

Confiança màxima, PDF escanejat (no text selectible), 8 conceptes identificats, **signals_emitted: 0**. Tot ignorat.
\
<Josep_edit> \
Ben trobat. Cal que ho corregim. \
Sabem per què signals_emitted: 0 ? \
</Josep_edit>

La carpeta `ACCEPTACIO` conté el pressupost **signat pel client** — és la font amb la informació de contacte i identificació més fiable. Ignorar-la per defecte és una decisió de disseny que elimina la millor font d'identitat del projecte.
\
<Josep_edit> \
Ben trobat. Cal que ho corregim. \
Quan corregim aquesta exclusió, obtindrem correctament les dades del pressupost? \
</Josep_edit> \

**`PDF/ANNEXES/` — ignorada com a "exported_pdf_dir"**

Conté:
- `3001722_PLANOL SITUACIÓ.pdf` — 2MB, vector PDF (FreeHand → PDF)
- `3001722_TALL CORRELACIÓ.pdf` — 500KB, secció geotècnica
- `3001722_DPSH.pdf` — copia del DPSH
- `3001722_FOTOGRAFIES.pdf` — còpia de fotos

El raonament per ignorar-los era: "si existeix la font (FH11), no cal el PDF exportat". Però els FH11 **també estan ignorats** (`freehand_file`). Resultat: ambdós (font i exportació) ignorats.

\
<Josep_edit> \
Ben trobat. Cal que ho corregim. \
Qui ignora `PDF/ANNEXES/` com a exported_pdf_dir? El file_scanner? \
Mai tindrem accés a fitxers .FH11, així que aquest tipus de fitxers no podrà ser mai una font de dades per nosaltres.\
</Josep_edit>


El `3001722_PLANOL SITUACIÓ.pdf` té el títol del projecte: *"ESTUDI GEOLÒGIC I GEOTÈCNIC PER A LA CONSTRUCCIÓ D'UNA HABITATGE UNIFAMILIAR AL CARRER BARCELONETA Nº23 DE VACARISSES"* — conté adreça, municipi, tipus d'obra. Però:
- `concept_map.json` el va escanejar: `concepts_detected: []` — el text és dibuixat com a corbes vectorials (FreeHand export), no com a caràcters reals. Text mining no funciona.
- Una vision probe podria llegir-lo, però el sistema mai no li arriba.
\
<Josep_edit> \
Estàs segur de què el text és vectorial? Jo l'he seleccionat i copiat; diria que és text normal, llegible per LLM. El problema és que text_mining és python i no pot llegir-lo? Hi hauria alguna manera de resoldre-ho? \
</Josep_edit>

> **⚠️ CORRECCIÓ EMPÍRICA (2026-06-24) — la premissa "Tot ignorat" és FALSA.**
> Resposta a les tres preguntes del Josep de §2.2, verificada executant `auto_extract` sobre Vacarisses:
>
> 1. **Qui ignora ACCEPTACIO?** `file_scanner.py:179` la marca `acceptance_dir`, **però això
>    només reté l'assignació d'un *rol* especialitzat** — NO la treu del mining ni del probing.
>    FileMiner la recorre (no és a `_SKIP_DIRS`) i ConceptScout li fa vision-probe.
> 2. **Per què `signals_emitted: 0`?** És un **literal hardcoded** a `deep_folder_classifier.py:325`.
>    Mai es calcula i **cap codi el llegeix**. NO és evidència de pèrdua de dades — és un camp de
>    diagnòstic sense connectar que ens va enganyar a nosaltres llegint el JSON.
> 3. **En corregir l'exclusió obtindríem les dades?** Ja les obtenim. **Prova:** el prefill
>    `street_address = 'C/DE LA BARCELONETA 23'` té font literal `vision_probe:ACCEPTACIO\Presupost
>    Geotecnic.pdf`. Les 24 sources `vision_probe:budget` d'ACCEPTACIO entren a la competició via
>    `concept_sources_to_signals` + `_merge_vision_signals_into_competition`.
>
> **El problema real NO és l'exclusió, és la competició** (entity confusion, §3.3): `vision_probe:budget`
> → source_type `vision_probe_other`, absent dels mapes de prioritat → default 50 → perd contra el text.
> Per `client_nif` això feia guanyar el CIF de G3DT. **Fix acotat aplicat 2026-06-24** (blocklist de NIFs
> de proveïdor): 5/8 projectes tenien el CIF de G3 com a client_nif → 0/8. Detall complet i per què NO
> retunejem prioritats: `DECISION-LOG.md` entrada 2026-06-24. La pregunta del text vectorial (FreeHand)
> queda oberta com a tasca A6 separada.

### 2.3 Rol `sondeig_annex` no assignat

No hi ha cap fitxer amb rol `sondeig_annex` en el file_mapping. Motiu: no existeix cap `SONDEIG.pdf` en aquest projecte. La secció geotècnica (correlació) viu en `ANNEXES/3001722_tall de correlació.FH11` (format FreeHand, llegit com a binari, inaccessible).

Quan el pipeline necessita executar la visió de `sondeig_annex`, agafa el **mateix fitxer que `architect_plan`** (`plano.pdf`). Ambdues crides de visió reben el plànol topogràfic.

\
<Josep_edit> \
És força habitual que no hi hagi sondeig; alguns projectes no en necessiten, o no els hi demanen. No hauria de ser una dada obligatòria. \
És ok que busquem la informació de sondeig amb visió, mentre no sapiguem amb seguretat si el projecte ha de tenir sondeig o no. \
A vegades tenim informació dels informes que inclou el projecte al pressupost. \
A "ACCEPTACIO/Pressupost Geotècnic.pdf" (i igualment a "26.0332/PRESSUPOST GEOTEC.VACARISSES.pdf") tenim: 
```
Sota aquestes premisses, s'ha previst la realització de la següent campanya de
camp:
3 assaigs de penetració dinàmica DPSH
1 assaig SPT, amb recuperació de mostra
Assaigs de laboratori
Redacció de l'estudi geològic/geotècnic 
```
A "26.0332/PLAN_COST_VACARISSES.xlsx" tenim: \
```
PRESSUPOSTOS GEOTÈCCNICS C0-C1				
CONCEPTE	UNITATS	PREU UNIT	TOTAL	
ESTUDIS C0-C1				
Desplaçament màquina de penetració		100,00 €	0,00 €	
unitat de penetració dinàmica DPSH	3	90,00 €	270,00 €	
ml previ a l'assaig SPT	1	28,00 €	28,00 €	
SPT	1	28,00 €	28,00 €	
            326,00 €	
SONDEIG A ROTAC IÓ				
Sondeig a rotació, inclòs desplaçament i SPT'S		400,00 €	0,00 €	
obertura de paviment		45,00 €	0,00 €	
    Subtotal (2)		0,00 €	
ASSAIGS DE LABORATORI				
PA ASSAIG C0-C1	1	60,00 €	60,00 €	
PA ASSAIGS PATOLOGIES		120,00 €	0,00 €	
    Subtotal (3)		60,00 €	
INFORMES				
Direcció, redacció i supervisisó de  l'Estudi Geotècnic	1	309,00 €	309,00 €	
Supervisió de treballs de camp	1	90,00 €	90,00 €	
    Subtotal (4)		399,00 €	
    TOTAL (SIN I.V.A.)		785,00 €	840,00 €

```
on a la línia sobre sondeig, columna "unitats", apareix la cel·la sense unitat (null), és a dir, zero sondetjos encomanats.\
Aquesta informació a vegades està disponible; altres potser no.\
Podem analitzar aquests fitxers? Ja ho fem? Tenim aquestes dades a algun fitxer json? A "projecte_extracted.json" no la tenim, seria el lloc correcte? Costaria molt afegir-la? Penso que és important per determinar com serà l'informe final.
</Josep_edit>

### 2.4 Fitxers "unassigned" notables

```
"26.0332/DADES PER ANAR A CAMP_v1.xlsx"  → no assignat, no mined
"ACCEPTACIO/Presupost Geotecnic.pdf"       → no assignat, però concept_map el llegeix
"DTE.txt"                                  → no assignat (buit, 0KB)
"8000605_TOPOGRÀFIC.dwg"                  → no assignat (format CAD, no llegible)
```

El `DADES PER ANAR A CAMP_v1.xlsx` no té rol, però `concept_map` hi va trobar `client_phone` (confiança 0.9, valor "A OBRA" — **és l'etiqueta de la cel·la, no el valor**). Detecció falsa positiva.

<Josep_edit> \
Read this research on reading DWG and FH11 files, maybe we can have some data if any of these libraries works:\
 "mnt/c/claude/g3dt/dades-eva/_DEBUG PRODUCCIO/Research-on-reading-DWG-FH11-files.md" \
</Josep_edit>


---

## 3. Anàlisi de `concept_map.json` — 69 conceptes no resolts
<Josep_edit> \
total_concepts_unresolved_unlocated = 69 - (17+8+7+6+5) = 26 \
total_concepts_unresolved_that_should = 26+6 = 32, not 6.

Els 17 concepts del grup A ens suggereixen que, si no hi ha plànol d'arquitecte (edifici a construir o ja existent), no deu tenir sentit buscar variables com building_structure_desc, o building_height_m, o num_floors, o superficie_construida, o building_to_demolish_visual. \
Però parcel_shape sí, is_urban sí, slope_percent sí, ... \
commercial_code no ho sé. \
Les que sí hem de mantenir, d'on les extraiem? \
Quan escrivim l'informe, haurem de decidir què hem de fer amb els paràgrafs que contenen les variables sobre un hipotètic edifici. Si no hi ha edifici, potser no hauríem d'escriure aquests paràgrafs, no trobes? Què fem actualment? Hem d'anar amb compte a l'hora de prendre una decisió com aquesta (mostrar/treure paràgrafs de l'informe). No prenguem una decisió ara, tan sols analitzem-ho, i annotem-ho al DECISION_LOG.md. Penso que hauríem de validar què fer amb l'Eva.


Quines altres variables (conceptes) queden? \
</Josep_edit>
### 3.1 Estadístiques generals

```
total_files: 42
vision_probes_sent: 16
total_concepts_found: 20
total_concepts_unresolved: 69
```

El nombre 69 sembla alarmant però s'ha de contextualitzar.

### 3.2 Classificació dels 69 no resolts

**Grup A — Inherentment no disponibles en projectes geotècnics sense plànol arquitectònic (≈17):**
`superficie_construida`, `num_floors`, `building_height_m`, `parcel_shape`, `building_structure_desc`, `building_to_demolish_visual`, `is_urban`, `is_sloped`, `slope_direction`, `slope_percent`, `commercial_code`...

→ Aquests no existeixen perquè G3DT treballa ABANS que hi hagi projecte arquitectònic. No s'haurien d'esperar. **El pipeline els comptabilitza com "no resolts" quan en realitat són "no aplicables" per a la majoria de projectes de G3DT.**

**Grup B — Provenen d'APIs externes, no de fitxers del projecte (≈8):**
`referencia_catastral`, `icgc_unit_code/description/epoch`, `superficie_parcela`, `utm_x`, `utm_y`, `adjacent_*`

→ S'obtenen via Cadastre/ICGC HTTP. No apareixeran mai al concept_map. Que siguin "no resolts" aquí no significa que el pipeline no els trobi — estan en `user_data.json` (geocodificació va funcionar per Vacarisses).

<Josep_edit>
Quan, més endavant al pipeline, fem les peticions a les API, i obtenim la informació que necessitem, seria bò actualitzar aquests fitxers JSON. Si no ho fem, no podem tracejar si aquestes altres variables les obtenim correctament o no (a través d'API).
</Josep_edit>

**Grup C — Computats a partir de DPSH + fórmules (≈7):**
`geomech_E/gamma/cohesion/phi`, `qa_value`, `k30_value`, `settlement_cm`

→ No existeixen en cap fitxer, es calculen. Normal.


<Josep_edit>
Seria convenient anotar els resultats dels càlculs a algun json? Crear-ne un de nou? 
I si prenem decisions durant els càlculs, també hauríem d'anotar-ho.
Amb el temps això ens permetrà tracejar la qualitat d'aquesta part del pipeline; mentres no ho tinguem només podem suposar que funciona a les mil meravelles, quan, si funcionés fatal, no ens asseventaríem.
</Josep_edit>


**Grup D — HAURIEN de trobar-se però no es troben (≈6, PRIORITARI):**
- `lab_testing_company`, `lab_location` — l'email `laboratorio@tps-perforaciones.com` a `4849-GTL-26 Vacarisses.pdf` **identifica el laboratori** (TPS Perforaciones), però la detecció ho classifica com a `client_email` (patró regex: qualsevol email → `client_email`)
- `field_work_dates` — PENETROS.pdf ha `field_date: "15-5-2026"` (confiança 1.0 al concept_map) però `field_work_dates` segueix no resolt
- `num_dpsh_tests` — 3 assaigs (P-1, P-2, P-3) estan al DPSH excel però el concept_map no compta fitxes
- `spt_*` — hi ha SPT-1 a `dpsh_extracted.json` però concept_map no recull dades d'SPT


<Josep_edit>
Sembla raonable que necessitem afinar els nostres algoritmes; pel que descrivim a l'apartat D, estem molt a prop de processar bé aquestes dades però per petits detalls perdem la informació. Hem d'afinar-ho.
</Josep_edit>


**Grup E — Síntesi LLM (≈5, no automàtic):**
`location_sentence`, `site_description`, `site_condition`, `access_description`, `historia_geologica_template`

→ Es generen per síntesi, no per extracció.

<Josep_edit>
Seria bò actualitzar el concept_map.json després del procés de síntesi, per incloure el detall de quants concepts s'han resolt a síntesi (i el detall dels altres grups que hem discutit aquí), per a què total_concepts_unresolved tingui un valor correcte al final del pipeline.

Ara mateix, 20 resolts i 69 unresolved dóna una eficàcia menor al 30%. Aquesta és la dada de la que queda constància als nostres fitxes json. Ens convé que sigui més acurada.
</Josep_edit>


**Conclusió sobre els 69:** Realment "no resolts i problemàtics" → Grup D (≈6). La resta és confusió de nomenclatura (grup A = no aplicables, grup B = APIs, grup C = computats).

### 3.3 Problemes en els conceptes SÍ resolts

Els 20 conceptes "resolts" no signifiquen tots correctes:

**`client_nif`** — 3 valors candidats:
- `B25461443` de pressupost (NIF de G3DT → **INCORRECTE per a client**)
- `B64803075` de GTL report (NIF de TPS Perforaciones → **INCORRECTE**)
- `38112117J` de budget signat (NIF de Marc Vidal → **CORRECTE**)

El sistema no sap quina empresa és qui. Tot el que sembla un NIF es mapeja a `client_nif`.

<Josep_edit>
Si a la nostra pipeline li convindria excloure NIFs més fàcilment identificables (NIF del proveïdor X, NIF de G3DT (podríem tenir-lo definit com a constant), ...) per poder obtenir amb més confiança el NIF del client comparant amb menys candidats, podríem fer-ho. Trobo que seria una millora.
</Josep_edit>

**`architect_company`** — Valor: `"G3 DESENVOLUPAMENT TERRITORIAL, S.L."`  
→ **ÉS EVA'S COMPANY**. En el pressupost geotècnic (pàg. 4), G3DT apareix com a prestadora de servei. El sistema interpreta "empresa al pressupost" = "empresa de l'arquitecte". La confusió ve del concepte: en el context G3DT, **l'arquitecte és el client que encarrega l'estudi**, no la firma que signa el pressupost.

**`architect_name`** — `"jj.adelantado@coac.net"` (des de pàg. 5 del budget signat)  
→ L'email d'un arquitecte membre del COAC. Probablement correcte com a "contacte arquitecte" però extret com a nom, no email.

**`street_address`** — 5 candidats barrejats:
- `"C/ Vallbona, 22"` del lab_order → **adreça del laboratori, no del solar**
- `"C/DE LA BARCELONETA 23"` del budget → ✅ correcte (solar)
- `"C/de la Barceloneta"` del PENETROS → ✅ correcte (solar)
- `"Carrer La Barceloneta"` del plano (mapa) → ✅ ok
- `"Passeig Blanc, 78"` de img4 del pressupost → **adreça particular del client**, no del solar

El sistema agrupa totes les adreces trobades sense distingir: adreça del solar / adreça del client / adreça del laboratori.

**`building_type`** — 3 candidats:
- `"CONSTR HAB UNIF"` del lab_order → ✅ correcte (abreviatura)
- `"Carrer de La Barceloneta, 23..."` de les msg → **ÉS UNA ADREÇA, no un tipus d'edifici**
- `"Tipus d'edifici: C0"` del budget → ✅ (C0 = categoría CTE de risc baix)

**Conclusió**: Les dades extres en el `client_email` concept inclouen l'email del laboratori. El pipeline no distingeix per entitat.


<Josep_edit>
És obvi que hem d'afinar la lògica de la nostra pipeline; aquestes dades les hauríem de trobar i classificar correctament el 100% de les vegades, i podem fer-ho. És qüestió de fer-ho amb cura, sense córrer.
</Josep_edit>



---

## 4. Anàlisi de `docs_extracted.json`

### 4.1 Estat actual: 3 camps, 1 fitxer, tots problemàtics

```json
architect_company: "MARC VIDAL"        ← client, no arquitecte
num_planned_dpsh: 1                     ← MAL EXTRET pel regex; el pressupost en diu 3 (CORREGIT, veure §4.4)
site_address: "DE LA MAQUINA DE PENETRACIO,"  ← fragment de text, no adreça
```

### 4.2 Per què és tan poc?

`docs_extracted.json` és la sortida d'un pas específic: l'extracció Python regex sobre el PDF **vectorial** del pressupost a `26.0332/PRESSUPOST GEOTEC.VACARISSES.pdf`. No és l'agregació de totes les fonts — les extraccions de FileMiner van a `_sources` de `user_data.json` per camins separats.

El disseny és correcte (docs_extracted = un pas específic). El problema és que el pas produeix 3 camps, i tots tres han de ser eliminats o corregits:

- `architect_company` regex: busca "OBRA:" i agafa el valor → en el pressupost, "OBRA:" conté el client (Marc Vidal), no l'arquitecte
- `num_planned_dpsh` regex: **mal extret** — el patró ampli agafa un `1,00` d'una altra línia del pressupost i el lliga a la capçalera "ASSAIGS DPSH" (diagnòstic empíric + correcció a §4.4)
- `site_address` regex: capta text que conté "C/" → "DE LA MAQUINA DE PENETRACIO," és part de la descripció de l'assaig DPSH, no una adreça

### 4.3 Si s'esperava un fitxer gran?

No, és correcte que sigui petit. Les dades riques venen del concept_map (ConceptScout) i del FileMiner. docs_extracted era dissenyat per cas específic on el PDF vectorial té text selectible. Per a Vacarisses el PDF vectorial del pressupost és la font menys rica.

<Josep_edit>
1. Si aquest pas és un anàlisi d'un únic fitxer, no és acceptable que falli 3/3. 
2. architect_company: 
2.1. Sobre el fet que estem extraient el nom del client i assignant-lo a la variable architect_company enlloc d'assignar-lo a una variable (que no sé si existeix) que contingui el nom del client (client_name, o una variable anomenada de forma similar), com hauríem de fer: al projecte Bell-lloc, sobre el que vem dissenyar el nostre pipeline, el nom del client apareix com "ARQUITECTURA BOSCH NOVELL". El client era una empresa d'arquitectura. Però el projecte Vacarisses ens ensenya que el client pot no ser una empresa sino un particular, i que pot no ser un arquitecte; els valors observats als pressupostos d'altres projectes normalment sí són arquitectes, però per rigor els pressupostos ens informen del nom del client. 2.2. Hem de revisar aquesta part. A l'informe final tenim dos variables a la mateixa frase, que per exemple al projecte de Linyola composen aquesta frase final: 
````
Segons ens indica el sol·licitant, BUNYESC ARQUITECTURA EFICIENT, en nom de la SRA. SÍLVIA EROLES BALAGUERÓ, es vol valorar les característiques geològiques i geotècniques dels materials del subsòl on es preveu construir (...)
````
En el cas de Linyola el pressupost mostra: 
````
CLIENT
BUNYESC ARQUITECTURA EFICIENT, SLP
C/ ARBORETUM, 17
25199 LLEIDA
Tel: 973157519
````
I hem extret del pressupost "BUNYESC ARQUITECTURA EFICIENT, SLP". No sé de quin document hem extret "SÍLVIA EROLES BALAGUERÓ". 
Quins són els noms de les variables que fem servir per generar aquesta frase? 'architect_name' i 'architect_company'?
Necessitem algo més intel·ligent que un patró regex per assignar valors a aquestes variables, que pugui tenir en compte la variabilitat en el tipus de client i el seu nom. Normalment serà un arquitecte, però si només tenim un nom, hem de prendre les decisions adequades.

3. Per què hem obtingut num_planned_dpsh = 1, si el document diu a dos llocs que són 3: 


A la pàgina 2 diu:
```` 
Sota aquestes premisses, s’ha previst la realització de la següent campanya de camp:
3 assaigs de penetració dinàmica DPSH
1 assaig SPT, amb recuperació de mostra
Assaigs de laboratori
Redacció de l’estudi geològic/geotècnic 
```` 
I a la pàgina 4 diu:
````
ASSAIGS DPSH'S:
001.001 UNITATS D'ASSAIG DE PENETRACIO DINAMICA DPSH  3,00
001.002 ASSAIGS SPT 1,00
001.003 ML.PREVIS A L'ASSAIG SPT 1,00

````


Sobre site_address: 
Sembla que site_address s'ha agafat d'aquesta frase: 
````
NOTA:
SI S'HAGUÉS DE LLOGAR UN CAMIO PLOMA PER
EMPLAÇAMENT DE LA MAQUINA DE PENETRACIO,
AQUEST TINDRIA UN SOBRECOST DE 375€ A 475€,
SEGONS PROVEIDOR
````
És l'únic lloc del document on apareix el valor que ha agafat.
Sembla que la paraula "emplaçament" li ha fet pensar que el text que ve a continuació és l'adreça del lloc. Això és òbviament incorrecte. 
Hem de revisar aquesta part del codi. Si és lògica regex serà senzill modificar la lògica. El lloc d'aquest document d'on hem d'extreure site_address ha de ser aquesta secció "OBRA" de la primera pàgina:
````
OBRA:

ESTUDI GEOTECNIC
C/DE LA BARCELONETA 23
VACARISSES
````
Notes:
Per Bell-lloc, el contingut d'aquesta secció del pressupost és: 
````
OBRA:

ESTUDI GEOTECNIC
C/MESTRE RAMON ORTIZ 15
BELL-LLOC
````
Per Castellar, és: 
````
OBRA:

ESTUDI GEOTECNIC 3HAB.
C/ARBRELLS 18A
CASTELLAR DEL VALLES
````
Per Rubí (no tindríem l'adreça completa, només "RUBI"): 
````
OBRA:

ESTUDI GEOTECNIC
RUBI
````
Per Linyola: 
````
OBRA:

Clot de la Llacuna, 16 -25240- Linyola
````

Per Alcoletge: 
````
OBRA:

ESTUDI GEOTECNIC
C/GIRASOLS 7, URB.EL ROSER
ALCOLETGE
````
Per Vilanova de Segrià: 
````
OBRA:

ESTUDI GEOTECNIC
C/ STA. GEMMA 4, URB.LA SERRA
VILANOVA DE SEGRIA
````

I per Ancilles: 
````
OBRA:

ESTUDIO GEOTECNICO
C/GENERAL FERRAZ 20
ANCILES (HUESCA)
````

</Josep_edit>

### 4.4 `num_dpsh_tests` vs `num_planned_dpsh` — diagnòstic empíric, correcció i validació (2026-06-22)

**Primer: són DUES variables diferents, i només una estava trencada.**

| Variable | Significat | Font | Valor (Vacarisses) | Estat |
|----------|-----------|------|:---:|-------|
| `num_dpsh_tests` | assaigs DPSH **executats** | `len(DPSHData.tests)` de l'Excel `ANNEXES/*_DPSH.xls` | **3** (P-1/P-2/P-3) | ✅ **correcte** — és el valor que **l'informe** imprimeix |
| `num_planned_dpsh` | assaigs DPSH **previstos** | regex sobre el PDF del pressupost → `docs_extracted.json` | **1** | ❌ **mal extret** (el pressupost en diu 3) |

Verificat amb el codi de producció: `DPSHExtractor.extract_all()` sobre l'Excel de Vacarisses retorna `num_tests = 3` (`['P-1','P-2','P-3']`). I un `grep` confirma que **cap** codi (ni `report_data`, ni la plantilla Jinja, ni el wizard) **llegeix** `num_planned_dpsh`. Per tant:

> **L'informe que veu l'Eva ja mostra el recompte DPSH correcte (3).** El bug `=1` viu només a la capa d'intel·ligència (`docs_extracted.json`). Corregir-lo millora la traçabilitat i alimenta el senyal de "campanya prevista" (§2.3/§6), però **no canvia la sortida de l'informe d'avui**.

**Resposta directa a la pregunta del punt 3 ("per què 1 si el document diu 3 a dos llocs?"):**
El nostre regex no llegia **cap** dels dos "3". Empíricament, el patró ampli antic
(`(\d+)[,.]?\d*\s*(?:UNITATS?...|assaigs?\s*DPSH|DPSH|...)`) feia *match* amb la
cadena literal `'1,00\nASSAIGS DPSH'`: el `1,00` pertany a **una altra línia**
del pressupost (la fila d'SPT / "ML previs", totes dues `1,00`) que en el text
extret cau just abans de la capçalera `ASSAIGS DPSH'S`. Per què no la taula de la
pàg. 4 (`...DPSH 3,00`)? Perquè **l'extracció de text del PDF desordena les columnes
de la taula**: el `3,00` queda separat de la seva etiqueta i un `1,00` veí hi
queda enganxat. Ho vaig provar: un regex sobre la taula també retornava 1. L'única
àncora fiable és la **frase de campanya** ("N assaigs de penetració dinàmica DPSH"),
que és una línia contigua en ordre de lectura.

**Correcció aplicada** (`web/vision_fast.py`, funció `_extract_docs_python`):
substituït el patró ampli per l'àncora de la frase de campanya:
```python
r"(\d+)\s+assaigs?\s+de\s+penetraci[oó]\s+din[aà]mica"
```
Si la frase no hi és → no emetem cap valor (millor cap valor que un de fals — Zero Fabrication). Beneficia tant el camí *fast* com el de Groq (tots dos importen aquesta funció).

**Validació de generalització** (no és un pegat per a un sol projecte — requisit explícit). Regex antic vs. nou, sobre TOTS els pressupostos disponibles, a través del codi real pegat:

| Projecte | Regex antic | Regex nou | Cert |
|----------|:---:|:---:|---|
| Vacarisses | **1** ❌ | **3** ✅ | "3 assaigs de penetració dinàmica DPSH" |
| Castellar | **2** ❌ | **4** ✅ | "4 assaigs de penetració dinàmica DPSH" |
| Rubí | 3 ✅(atzar) | 3 ✅ | "3 assaigs..." |
| Bell-lloc | 2 ✅(atzar) | 2 ✅ | "2 assaigs..." |
| Alcoletge | 3 ✅(atzar) | 3 ✅ | "3 assaigs..." |

El regex antic fallava en **2 de 5** (encertava 3 per coincidència). El nou: **5/5**. Castellar (projecte de referència) també estava malament → bug recurrent, no exclusiu de Vacarisses.

**Tests** (sense regressió): suite completa amb i sense el canvi → **idèntica** (32 failed, 981 passed, 3 skipped). Els 32 *fails* són preexistents a `production/g3dt-eva-v1` (SmartScan ground-truth, AI-pipeline ranking/trace, groq cache — res a veure amb l'extracció de docs). Cap test referencia `num_planned_dpsh`.

**Límits d'abast d'aquesta correcció (deliberats):**
- **No** s'ha tocat `num_planned_sondeig` ni `num_planned_spt` — comparteixen la mateixa família de regex amb el mateix bug latent, però pertanyen a la tasca de *sondeig* (i a la pregunta del §2.3 sobre la campanya prevista: 3 DPSH / 1 SPT / **0 sondeig**). Marcat per a aquella tasca.
- **A8 (§9) queda superada** per aquest diagnòstic: la seva premissa ("`num_dpsh_tests` hauria de venir de l'Excel, no del pressupost") era parcialment errònia — `num_dpsh_tests` **ja** ve de l'Excel i **ja** és correcte; el bug era a `num_planned_dpsh`. (No edito §9 en aquesta tasca.)

**Estat:** ✅ Corregit i validat a `fix/pipeline-routing`. Pendent: decisió de l'Eva sobre si el recompte *previst* (intel) s'ha d'aprofitar per a un control creuat previst-vs-executat (lligat a §2.3/§6).

---

## 5. Anàlisi de `planol_extracted.json` i `sondeig_annex_extracted.json`

### 5.1 El fitxer enviat

Ambdues extraccions van rebre **el mateix fitxer: `plano.pdf`** (15KB, PDF escanejat).

### 5.2 Sobre la fiabilitat de `data_sources_found`

Josep planteja una pregunta clau: `data_sources_found: ["Site plan drawing"]` és una cadena generada pel model (no estructurada). **No s'hauria d'usar com a senyal de detecció**.

Els senyals estructurats fiables que sí tenim:
- `overall_confidence: 0.5` → float Python, fiable
- `architect_data.architect: null` → camp estructurat, fiable
- `architect_data.project_name: null` → camp estructurat, fiable
- `dimensions.parcel_area_m2: null` → camp estructurat, fiable

Addicionalment, el `concept_map.json` assigna al plano.pdf: `notes: "map: Topographic map with contour lines and elevation points"`. El prefix `"map:"` abans dels dos punts és el `doc_type` estructurat que el ConceptScout genera. **Això és un senyal fiable**: si `concept_map.notes` per al fitxer assignat a `architect_plan` comença per "map:" o "field_sheet:" en lloc de "plan:" o "budget:" o "other:", tenim evidència estructurada de confusió de rol.

### 5.3 Els valors extrets: 425.4m × 426.0m

El model va retornar `plot_length_m: 425.4` i `plot_width_m: 426.0`. Aquests valors corresponen a cotes topogràfiques (424.00, 426.00 m.s.n.m.) que l'LLM va llegir del mapa i va intentar assignar a "dimensions de parcel·la". Resultat plausible però completament fals.

### 5.4 `sondeig_annex_extracted.json`

Resultat: `sondeig_tests: []`, `overall_confidence: 0.0`. El model (Claude Anthropic backend) va identificar correctament que era un plànol topogràfic i ho va indicar a `extraction_notes`. Zero dades geotècniques extrets, però el pipeline va **acceptar silenciosament** aquest resultat buit.

---

## 6. Sobre la manca de plànol arquitectònic — observació estructural

Eva treballa en estudis geotècnics previs a la fase de projecte. En molts casos **no existeix plànol arquitectònic** perquè:
- El client sol·licita l'estudi geotècnic ABANS de contractar un arquitecte
- O l'arquitecte existeix però no ha compartit el plànol amb G3DT

El pipeline actual **assumeix que `architect_plan` existeix**. Quan no existeix (cas Vacarisses), el file_scanner agafa el primer fitxer que "sembla un plànol" per nom, en aquest cas el topogràfic.

**Implicació**: les dades que normalment s'extrauen del plànol arquitectònic (tipus d'obra, superfície construïda, número de plantes, nom de l'arquitecte) han de poder arribar des d'altres fonts:
- **Pressupost signat** (`ACCEPTACIO/Presupost Geotecnic.pdf`): conté `client_name`, `street_address`, email de l'arquitecte, tipus de terreny (T1/T2/T3), i a vegades el tipus d'obra
- **Lab order** (`comanda laboratori_*.xls`): conté `building_type` abreviat, adreça, municipi
- **Correu** (`.msg`): pot contenir la descripció de l'encàrrec
- **PENETROS.pdf**: encapçalament del full de camp conté adreça, data de camp

Actualment la no-troballa de plànol arquitectònic deixa camps buits que Eva ha d'omplir manualment. Alguns d'ells SÍ estan en altres documents però no s'extreuen perquè el sistema "delegava" en el plànol.

---

## 7. El GTL report: `4849-GTL-26 Vacarisses.pdf`

El concept_map troba en aquest fitxer:
- `client_nif: "B64803075"` → **NIF del laboratori (TPS Perforaciones), no del client**
- `client_email: "laboratorio@tps-perforaciones.com"` → **email del laboratori**
- `field_date: "2026.06.11"` → **data del resultat del laboratori, no de camp**

El fitxer té rol `gtl_report` (correcte) però el pipeline no extreu d'ell les dades que hauria d'extreure: `lab_testing_company`, `lab_location`, `lab_tests` (resultats reals). En lloc d'això, els senyals que genera van a bucket `client_nif` i `client_email` per patrons de regex genèrics.

Eva diu "no identifica el laboratori". El laboratori és TPS Perforaciones i el seu nom s'obté trivialment de l'email o del nom del fitxer GTL — però el pipeline no té un extractor de `lab_testing_company` basat en GTL reports.

---

## 8. Accés a `PDF/ANNEXES/3001722_PLANOL SITUACIÓ.pdf`

**Situació actual**: Ignorat per `exported_pdf_dir`.

**El que conté**: Títol del projecte G3DT amb adreça exacta del solar, croquis de situació dels punts d'assaig, símbol topogràfic de la parcel·la.

**Per què `concept_map` no troba res**: El PDF és una exportació de FreeHand. El text (títol, etiquetes) està dibuixat com a corbes vectorials (outlines), no com a caràcters reals. `text_extractable: true` significa que PyMuPDF pot obrir el fitxer, però no que pugui extraure text. `concepts_detected: []` és la conseqüència.

**Solució possible**: vision probe sobre aquest PDF. Però primer cal no ignorar-lo.

---

## 9. Accions proposades (sense implementar)

### A1 — Validació de rol amb doc_type del concept_map

**Problema**: file_scanner assigna `architect_plan` per nom ("plano" → plànol), sense validar contingut.  
**Proposta**: Un cop creat el `concept_map.json`, comparar el `doc_type` (prefix de `notes`) de cada fitxer assignat a un rol crític (`architect_plan`, `sondeig_annex`, `dpsh_field_sheet`) contra el rol esperat. Si hi ha contradicció → rol invàlid → buscar alternatius. Senyals d'invalidació: `overall_confidence < 0.5` (estructurat), `architect_data` tots null (estructurat). NO usar la prosa de `extraction_notes`.

### A2 — Desactivar la regla "ignorar ACCEPTACIO"

**Problema**: La carpeta `ACCEPTACIO` conté el pressupost signat que és la font de metadades de projecte més rica i fiable. S'ignora per defecte.  
**Proposta**: Eliminar `acceptance_dir` de la llista de carpetes ignorades, o convertir-la en "llegible per concept_map però sense rol d'extracció especialitzat". Les seves dades entren al concept_map (ja passa parcialment) i al circuit de `_sources`.

### A3 — Extractor específic per a GTL reports

**Problema**: El `gtl_report` role no té extractor. Les dades del laboratori (nom, data, resultats) no s'obtenen.  
**Proposta**: Afegir un miner específic per a fitxers amb rol `gtl_report` que extregui: `lab_testing_company` (nom del laboratori), `lab_location` (adreça), `lab_results` (sulfats, classificació). El nom del laboratori normalment apareix al capçalera del PDF.

### A4 — Millora d'entitat en extracció d'emails i NIFs

**Problema**: `client_email` recull qualsevol email trobat a qualsevol fitxer. `client_nif` recull qualsevol NIF. Resultat: barreja de NIFs del client, G3DT i laboratori; emails del client, G3DT i lab.  
**Proposta**: Associar cada email/NIF a l'entitat on apareix (capçalera del pressupost = proveïdor G3DT; pàgina de signatura = client; GTL report = laboratori). Implementació via context de pàgina o etiqueta adjacent ("NIF/CIF del client:", "Empresa prestadora:").

### A5 — Adreça del solar vs. adreces d'altres entitats

**Problema**: `street_address` agrega totes les adreces trobades: solar, client, laboratori.  
**Proposta**: Prioritzar fonts d'adreça del solar: PENETROS (capçalera "EMPLAÇAMENT"), pressupost signat (camp "EMPLAÇAMENT" o "C/"), lab_order (camp dedicat al solar). Descartar adreces trobades en zones de signatura o identificació de laboratori.

### A6 — Vision probe sobre `PDF/ANNEXES/3001722_PLANOL SITUACIÓ.pdf`

**Problema**: El plànol de situació G3DT conté el títol del projecte però es tracta com a "exported_pdf_copy" ignorable. El text és en corbes (FreeHand export), per tant no llegible per text mining.  
**Proposta**: Per PDFs del tipus "plànol de situació" (detectable per nom `*PLANOL SITUACIO*`), executar vision probe per extreure títol del projecte → `street_address`, `municipality`, tipus d'obra. Eliminar de la regla de "ignore exported_pdf_dir" per a aquest subtipus.

### A7 — Wizard UX: desbloquejar entrada manual quan no hi ha sondeig_annex

**Problema**: Eva entra `num_soil_levels = 2` però el wizard no li permet introduir les dades de cada nivell manualment.  
**Proposta**: Si `sondeig_annex_extracted.json` té `sondeig_tests: []` o no existeix el fitxer, el wizard ha de desbloquejar el formulari manual de nivells de sòl sense requerir dades prèvies del sondeig. (Separable del rest — és un canvi de lògica de wizard, no de pipeline).

### A8 — `num_dpsh_tests` des del DPSH excel, no del pressupost

**Problema**: `num_planned_dpsh: 1` del pressupost (oferta inicial) però el camp real és l'Excel amb 3 assaigs (P-1, P-2, P-3).  
**Proposta**: `num_dpsh_tests` s'hauria de calcular a partir del `dpsh_extracted.json` (longitud de la llista `dpsh_tests`), no del pressupost. El pressupost dóna el nombre planificat, no l'executat.

---

## 10. Diagnòstic resumit

**Error 1 — Plànol equivocat com a `architect_plan`**  
Causa: nom "plano.pdf" → filename pattern → rol assignat sense validació de contingut.  
Efecte: dades de l'arquitecte totes null, dimensions inventades (cotes topogràfiques confoses amb mides de parcel·la).

**Error 2 — `architect_plan` i `sondeig_annex` reben el MATEIX fitxer equivocat**  
Causa: quan `sondeig_annex` no té fitxer assignat, usa el fitxer de `architect_plan` com a fallback.  
Efecte: extracció de nivells geotècnics → resultat buit, Eva no pot modificar-ho.

**Error 3 — `ACCEPTACIO/` ignorada, font més rica silenciada**  
Causa: regla `acceptance_dir` elimina la carpeta del flux d'extracció.  
Efecte: metadades del projecte (client, adreça, NIF, contacte arquitecte) no arriben al pipeline.

**Error 4 — Entitat desconeguda: G3DT confosa amb arquitecte**  
Causa: el pressupost és un document G3DT → client; el camp "empresa" que s'extreu és G3DT, no l'arquitecte del projecte.  
Efecte: `architect_company = "G3 DESENVOLUPAMENT TERRITORIAL, S.L."` al concept_map (completament incorrecte).

**Error 5 — `lab_testing_company` no extret del GTL report**  
Causa: no hi ha extractor específic per a GTL reports; el NIF i email del laboratori acaben a `client_nif` / `client_email`.  
Efecte: Eva ha d'introduir el laboratori manualment cada vegada.

**Error 6 — Regex de docs_extracted productora de 3 falsos positius**  
Causa: patrons regex genèrics que no distingeixen context de la pàgina.  
Efecte: `architect_company` = client, `site_address` = descripció tècnica de l'assaig.

---

*Fi de l'anàlisi diagnòstica. Branca de treball per a les correccions: `fix/pipeline-routing`. Les accions proposades (§9) no estan implementades.*

---

### 4.5 `site_address` — diagnòstic post-fix i resultat (2026-06-23)

**Causa del problema original (§6 Error 6):** la regex de `_extract_docs_python` ancorava en `EMPLAÇAMENT|SITUACIO|Adreça`. El text PyMuPDF del pressupost conté la frase "emplaçament de la màquina de penetracio" (descripció tècnica de l'assaig DPSH) → la regex capturava aquesta línia en lloc de l'adreça del projecte.

**Solució implementada (commit `b11043c`, 2026-06-23):** substitució per un parser de bloc OBRA:

```
OBRA:
  [client/promotor]
  ESTUDI[O] GEO...       ← marcador del tipus de projecte
  [carrer?]              ← present si hi ha adreça de carrer
  [municipi]             ← última línia no-buida abans de CLIENT:/CP I POBLACIÓ:
CLIENT:
```

La línia post-ESTUDI és el carrer (si n'hi ha); l'última és el municipi. Si no hi ha carrer (cas Rubí), no s'emet res — "cap valor és millor que un valor incorrecte".

**Amplada del glob (mateix commit):** la funció només buscava `PRESSUPOST*.pdf` (català). Dos dels 8 projectes (Vilanova, Anciles) anomenen el pressupost `PRESUPUESTO*.pdf` (castellà). El glob s'ha ampliat per cobrir els dos.

**Via B2 (commit `3c87cc6`, 2026-06-23):** visió Claude dedicada al pressupost (`vision_type=pressupost`), injectada com a Step 2b de `_run_vision_fast`. Escriu `pressupost_extracted.json` sense modificar cap consumer (champion-challenger).

**Resultats (7 projectes):**

| Camp | Via A OBRA parser | Via B2 (Claude vision) |
|------|:-----------------:|:---------------------:|
| `site_address` | 6/7 ✅ | 7/7 ✅ |
| `municipality` | 0/7 (no emès) | 7/7 ✅ |
| `num_planned_dpsh` | 5/7 ✅ (falla ES) | 7/7 ✅ |
| `client_name` | 4/7 ✅ (ES falla) | 7/7 ✅ |
| `building_category` | 0/7 (apostrofació) | 5/7 ✅ |

Decisions per camp: veure `DECISION-LOG.md` entrada `2026-06-23`.

**Lacunes Via A pendents:**
- ✅ `num_planned_dpsh` per a PDFs en castellà — RESOLT 2026-06-25 (afegit `ensayos de penetración dinámica`; 5/7→7/7).
- ⏳ `architect_company` label errònia — és client/promotor, no arquitecte (tasca "entity confusion" A4; requereix lògica > regex).
- ✅ `building_category` apostrofació Unicode — RESOLT 2026-06-25 (classe `['’‘]` + plantilla ES "Tipo de Edificio."; 0/7→5/7).
- ✅ `num_planned_sondeig` espuris — RESOLT 2026-06-25 (guard per contingut: talla la finestra de campanya al header `UNITATS D'ASSAIG`/`UNIDADES DE ENSAYO` abans de la fila SONDEIG de la taula).

*Detall: `DECISION-LOG.md` entrada 2026-06-25.*
