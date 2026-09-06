# Anàlisi de la qualitat de la NARRATIVA de l'informe — 2026-09-06 (nit)

**Punt de partida:** M341 v1 (`docs/wizard-headless/mesures/runs/2026-09-06-m341`, variant `viaA`, 7 projectes generats només amb la
lectura + via B + Df del signat): grup narrativa **8 M · 18 C · 61 X · 22 ND → 30 %** (el % és (M+C)/(M+C+X), els ND no compten),
contra 69 % de la lectura i 66 % del càlcul. Aquest document respon a la pregunta del handoff `_FOR-NEW-YOU-20260907-1810.md`:
*per què* la narrativa puntua 30 %, *què* diu l'Eva de veritat a cada frase, *quina font* tenim per a cada forat, i *per on començar*.
No s'ha tocat codi ni plantilla.

**Regla d'or aplicada (2026-09-02):** els textos de l'Eva no són redacció lliure: són **fórmules fixes amb un o dos forats**, i el forat es
decideix per **criteri** (estat del solar, plantes/soterrani, nombre de nivells, zona de radó, sulfats). Es modelen igual que l'assentament
(`automation/settlement_criteria.py`): frase per criteri + candidats amb procedència, mai un LLM escrivint prosa.

---

## 0. Resum executiu (el que canvia la manera de mirar el 30 %)

El 30 % barreja **quatre coses diferents**, i només dues són «qualitat de la narrativa»:

| # | Causa | Cel·les (de 109) | Què és |
|---|---|--:|---|
| A | **Artefacte de mesura**: 5 variables viuen dins d'una frase FIXA de la plantilla (`site_condition`, `building_structure_desc`, `radon_zone_description`, `access_street`, `photo_site_text`); el comparador confronta el valor del context (p. ex. «pla») amb el PARÀGRAF sencer del signat → X segur. I `csn_radon_text` compara contra un paràgraf que a la plantilla ja és text fix (el generador l'AFEGEIX per segon cop). | ≈ 30 | mesura, no text |
| B | **Fórmula de l'Eva no codificada**: `materials_intro`, `conclusions_aggressivity_statement`, `radon_zone_description`, la capçalera de `site_condition`, la cua de `building_structure_desc`, `empentes_paragraph`. Textos idèntics als 5 signats en català (modul el forat). | ≈ 30 | text: fórmula + criteri |
| C | **Dada que no arriba o arriba malament**: adjacents (parcel·la equivocada a Bell-lloc, plantes del veí mai comptades per un bug, 3 projectes sense UTM → 0 adjacents), `access_street` (buit per cablejat), `lab_tests_text` (només sulfats), `site_description` (buit sense síntesi d'ortofoto). | ≈ 40 | dades + cablejat |
| D | **Idioma**: Vilanova i Anciles estan signats en **castellà**; la plantilla és només en català. 30 cel·les de narrativa (0 M · 2 C · 20 X · 8 ND) que cap fórmula catalana pot encertar. | 30 | decisió de producte |

**Conseqüència:** el sostre real d'aquesta línia amb la plantilla actual és el subconjunt català (79 cel·les: 8 M · 16 C · 41 X · 14 ND → **37 %** de 65 mesurables; recompte per projecte sobre els `_compare_341.json`).
L'ordre correcte és **arreglar la mesura → fórmules → dades**, i decidir a part què fem amb el castellà. Sense la peça de mesura, qualsevol
millora de text es puntuaria igual que ara (X) i no sabríem si hem avançat (memòria `feedback_measure_baseline_before_coding`).

---

## 1. Mètode i fonts

- **Números per variable:** `runs/2026-09-06-m341/_AGREGAT-341.md` §«Per VARIABLE»; cel·les gen ↔ eva a `<slug>/viaA/_compare_341.txt`
  (7 fitxers) i el context sencer a `_context_usat.json`.
- **Veritat:** `reference-material/<projecte>/validation/eva_reference_values.json` (`variables[X].value`, `position`, `confidence`) i els
  `.docx` signats (`~/g3dt-e2e/projectes/<projecte>/*_informe*.docx`; Anciles convertit del `.doc` de `/mnt/c/claude/g3dt/AI-pipeline/reference-material/4001679 ANCILES/`).
- **Plantilla:** paràgrafs amb `{{ }}` extrets de `templates/g3dt-jinja-template.docx` (numeració `pNNN` de la plantilla, no del signat).
- **Generació:** `automation/report_generator.py` (L660-680 fotos, L815-826 estructura, L950-1026 ubicació/adjacents/accés/estat del solar,
  L1185-1275 materials/radó/CSN, L1310-1315 nivells), `automation/sections/section3_geologia.py::generate_materials_intro`,
  `automation/sections/section4_conclusions.py` (aigua, agressivitat, empentes), `automation/adjacent_formatter.py`,
  `automation/cadastre_adjacents.py`, `web/wizard_service.py` (L280 `_fill_missing_adjacents`, L520-610 `site_description`/`site_condition`,
  L1036-1061 `building_structure_desc`, L1470-1545 síntesi LLM d'adjacents), `automation/site_text_generator.py`.
- **Comparador:** `scripts/compare_prefills_vs_eva.py::status_for` — narrativa per similitud (`SequenceMatcher`: ≥ 0,92 MATCH, ≥ 0,6 CLOSE).
- **Extractor de referència:** `automation/reference_extractor.py` L520-585 (alineació plantilla ↔ signat per similitud de l'esquelet) i
  L275-311 (`_extract_single_var`: si el prefix fix de la plantilla NO és al paràgraf del signat, retorna el **paràgraf sencer amb confiança 0,3**).
- **Verificacions en viu (avui):** una crida al Cadastre per Bell-lloc (parcel·la que resol l'UTM de la lectura + resposta DNPRC crua).

---

## 2. Diagnòstic transversal

### 2.1 La plantilla porta text fix al voltant de 5 variables (artefacte A)

| Variable | Paràgraf de la plantilla (fix + forat) | Valor del context avui | Què compara M341 |
|---|---|---|---|
| `site_condition` | p342/p559: «Degut a que es tracta d'un solar **{{ site_condition }}**, no s'han detectat marques i/o indicis de processos d'erosió…» | «pla» | «pla» ↔ «Com que es tracta d'un solar pla, no s'han detectat…» (frase sencera) → X 7/7 |
| `building_structure_desc` | p404/p570: «Segons el projecte executiu es preveu la construcció d'una estructura **{{ … }}**, i per tant, no es preveu cap excavació important, únicament l'excavació pel sanejament, anivellació, i per a la implantació de la fonamentació.» | «en planta baixa» | «en planta baixa» ↔ «en planta baixa, i per tant, no es preveu cap excavació…» (l'extractor deixa la cua perquè el sufix difereix: «dels elements de fonamentació») → X 7/7 |
| `radon_zone_description` | p497: «…pertany a la ZONA **{{ radon_zone }}{{ radon_zone_description }}**» | «, municipi amb concentracions mitjanes de gas radó en edificis tancats. Es recomana la implementació de mesures bàsiques de protecció.» | cua ↔ frase sencera → X 7/7 |
| `access_street` | p122: «El dia dels treballs de camp es realitza l'entrada a la zona d'estudi a través del **{{ access_street }}**.» | «» | ND 6/7 (i quan hi hagi valor: «carrer de la Miranda» ↔ frase sencera) |
| `photo_site_text` | p130: «**{{ photo_site_text }}**. Vistes generals de la zona d'estudi.» | «Fotografia 1 i Fotografia 2» | tros ↔ peu de foto sencer |
| `csn_radon_text` | p498: `{% if csn_radon_text %}{{ csn_radon_text }}{% endif %}` — però el paràgraf de l'Eva («En l'apèndix inclou un llistat de termes municipals…») **ja és text fix a p474** | text de cartografia CSN per coordenades (mai a cap signat) | el generador l'imprimeix DUES vegades (p474 fix + p498 afegit); M341 compta 4 X + 3 ND |

Signatura de l'artefacte a la veritat: **confiança 0,15-0,30** a `eva_reference_values.json` = «prefix de la plantilla no trobat: t'he donat el
paràgraf sencer» (`_extract_single_var` L292-294). Passa a `site_condition` (0,27-0,29 als 5 CA), `location_sentence` (0,19-0,21 als 7),
`access_street` (0,15-0,27), `building_structure_desc` (Castellar 0,21, Vilanova 0,24).

### 2.2 Tres «veritats» són paràgrafs equivocats (l'extractor tria per similitud, no per prefix)

| Variable | Veritat a `eva_reference_values.json` | Paràgraf real del signat |
|---|---|---|
| `location_sentence` (7/7) | «L'edificació que es preveu construir presentarà les següents característiques:» (p066) | Bell-lloc p037: «L'edificació que es preveu construir **es situarà entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell**.» L'esquelet «L'edificació que es preveu construir es situarà .» s'assembla més al paràgraf «…presentarà les següents…» i l'extractor s'hi queda. |
| `access_street` (Linyola) | «El dia 1 d'octubre de 2025, es va visitar l'obra per tal de:» | la primera frase de `site_description`: «…a través del carrer adjacent situat al oest.» |
| `conclusions_water_statement` (Castellar) | la frase de l'estat del solar + «Tampoc s'ha localitzat cap curs d'aigua…» | a les conclusions del signat de Castellar **no hi ha** frase del freàtic (és a 3.3, p260: «…fins la cota assajada, no es va detectar presència de nivell freàtic en cap dels assaigs realitzats.»): absència real, no error del generador |

### 2.3 El comparador per similitud és massa tou per a forats dins de frase fixa

Si comparéssim la frase RENDERITZADA («Degut a que es tracta d'un solar pla, no s'han detectat…») amb la de l'Eva («Com que es tracta d'un solar
**antropitzat**, no s'han detectat…»), la similitud surt > 0,92 (la cua fixa és llarga) → MATCH fals. Per a aquestes 5 variables cal comparar
**forat contra forat**: treure el text comú a extrems (a nivell de paraula) a totes dues frases i puntuar els residus (gen «Degut a que es tracta
d'un solar pla» ↔ eva «Com que es tracta d'un solar pla» → CLOSE; ↔ «Degut a que es tracta d'un solar antropitzat» → X). Això és el que
mesura de veritat «hem escrit el que escriu l'Eva».

### 2.4 Idioma

Vilanova de Segrià (municipi català) i Anciles (Osca) estan signats en castellà. El wizard ja detecta l'idioma (`_get_project_language`, per municipi
ES conegut o marcadors «vivienda/ensayo/calle/sótano») i té frases ES per a 4 variables (adjacents, `site_condition`, `building_structure_desc`,
`num_dpsh_tests`), però **la plantilla és en català**: un informe ES avui surt barrejat. És una decisió de producte (plantilla ES paral·lela o
no), no una peça de narrativa. Aquí es tracta a part (§6) i **les estimacions de sota són sobre les 79 cel·les catalanes**.

---

## 3. Grup 1 — adjacents i descripcions de solar

### 3.1 `adjacent_{north,south,east,west}_fmt` (viaA: N 0·4·3 · S 1·2·4 · E 0·2·5 · O 0·4·3; plantilla p116-p119, una frase per costat)

**Què escriu l'Eva (7 signats, literal):** o UN CARRER (nom real) o UNA PARCEL·LA (buida / amb construcció, amb el detall de la visita), i **ajunta
els costats iguals** en una frase. Vocabulari tancat:

| Tipus | Fórmules catalanes (signats) | Castellà |
|---|---|---|
| Carrer | «Per la part est amb el Carrer Mestre Ramon Ortiz.» · «Per la part sud, amb el carrer de la Miranda» · «Per la part nord amb el camí d'accés.» · «I finalment, per la part oest, amb el carrer per on es realitza l'entrada.» | «Y finalmente, Por la parte oeste con la calle STA. GEMMA.» |
| Buida | «amb una parcel·la buida.» · «amb un solar buit.» · «Per la part est i pel sud amb parcel·les buides.» · «amb parcel·les sense construir, amb herbes altes i arbres» · «amb parcel·les sense edificacions i amb vegetació de petita alçada i arbres.» | «con una parcela, sin edificaciones, alguna pavimentación, vegetación herbácea de pequeña altura y algún árbol.» · «con un campo de conreo herbáceo.» · «con un jardín.» · «con una zona yerma con vegetación.» |
| Construïda | «amb una parcel·la amb una construcció aïllada de fins a dos plantes sobre rasant.» · «amb una parcel·la ocupada per una habitatge unifamiliar.» · «amb una parcel·la on existeix un edifici aïllat en planta baixa.» · «amb tres parcel·les ocupades per edificis aïllats de fins a dos plantes sobre rasant i una amb soterrani i piscina.» · «amb una parcel·la construïda amb piscina.» · «Finalment, Per la part est i oest, amb construccions de característiques similars.» | «con parcelas de similares características a las proyectadas» · «con un edificio de hasta 4 plantas sobre rasante.» |

Ordre: N, S, E, O amb «I finalment» a l'últim (Bell-lloc va E, S, N, O: carrers primer). Anciles usa intercardinals (nord-est…): parcel·la girada 45°.
Frase d'introducció (no mesurada per M341, no és variable de plantilla; la genera `section2_treballs.py` L196): «La parcel·la objecte d'estudi es situa
al **nord/oest** del municipi de X, pren una morfologia **rectangular / quasi rectangular** i limita:» — posició i forma són derivables (centroide vs
municipi; polígon WFS).

**Què tenim avui (context `viaA`) i com s'assembla al signat (tipus per costat):**

| Projecte | Cadastre (N / S / E / O) | Eva (N / S / E / O) | Encerts de tipus |
|---|---|---|---|
| Castellar | buida / Carrer dels Arbrells / buida / construcció | sense construir + una PB+1 / carrer Arbrells / construïda amb piscina / sense construir | 1,5 / 4 |
| Bell-lloc | **Carrer Antoni Bellet Pérez** / construcció / construcció / construcció | buida / **Carrer Antoni Bellet** / **Carrer Mestre Ramon Ortiz** / construcció 2 plantes | 1 / 4 (parcel·la equivocada, vegeu sota) |
| Linyola | buida / buida / buida / Carrer Clot de la Llacuna | habitatge unifamiliar / buida / buida / «el carrer per on es realitza l'entrada» | 3 / 4 |
| Alcoletge | construcció / construcció / construcció / buida | camí d'accés / edifici PB / tres parcel·les 2 plantes + soterrani i piscina / solar buit | 3 / 4 |
| Rubí, Vilanova, Anciles | «sense informació» ×4 | — | 0 / 12 |

**Tres causes arrel trobades avui (verificables, no judici de l'Eva):**

1. **Parcel·la equivocada a Bell-lloc.** L'UTM que porta la lectura (314418,9 / 4611117,6, de `COORDENADES.txt` = punt de màquina) resol al
   Cadastre com a **«CL VIA FERREA 57»**, no la parcel·la entre Antoni Bellet i Mestre Ramon Ortiz. `_phase3_adjacents` prefereix geocodificar
   l'adreça llegida, però «Situat entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz» no és un portal → cau als UTM del DPSH.
   El lector de Cadastre de la via A (`automation/lectura/cadastre_reader.py`, portals exactes + polígon WFS, ON des del 2026-08-31) ja resol
   la parcel·la del projecte quan hi ha portal; `get_adjacent_parcels` accepta `rc14` però ningú li passa la referència resolta per la via A.
2. **Les plantes del veí no es compten mai (bug).** `_query_building_data` (`cadastre_adjacents.py` L541-548) llegeix `<stl>` esperant-hi
   «PLANTA»/«SUELO»; a la resposta DNPRC real `<stl>` és la **superfície** (15, 162, 23…) i la planta és `<pt>` («00», «01», «-1», «SM»…).
   Resultat: `num_floors_above = 0` sempre → «parcel·la amb construcció» genèric, mai «de fins a dos plantes sobre rasant» (que és la frase
   de l'Eva a Bell-lloc i Alcoletge). A més `<lcd>` porta «DEPORTIVO» (piscina), «ALMACEN», «VIVIENDA»: dona «amb soterrani i piscina».
3. **Sense UTM no hi ha adjacents.** Rubí, Vilanova i Anciles no tenen `utm_x/utm_y` a la lectura; el generador no geocodifica l'adreça
   llegida per als adjacents (això només ho fa el wizard a `_fill_missing_adjacents`, fora del camí de M341 i del `generate()`). Rubí té portal
   («Carrer de la Miranda, 39») i Vilanova també («C. Santa Gemma, 4»): resolubles amb el lector de la via A.

**Què és judici de l'Eva (no derivable):** «amb herbes altes i arbres», «vegetació de petita alçada», «construïda amb piscina» quan el Cadastre no
ho diu, «construccions de característiques similars». Amb el Cadastre ben cablejat el TIPUS (carrer / buida / construïda + plantes + soterrani +
piscina) és determinista; el detall vegetal és de la visita (fotografies: vision opcional, mai obligatori).

**Proposta (criteri, no LLM):**
- Font de la parcel·la: referència cadastral del lector via A (portal exacte) → polígon → sondeig per costat (el que ja fa `get_adjacent_parcels`
  amb `rc14`); si no hi ha portal, UTM de COORDENADES només si el punt cau DINS d'un polígon coherent amb l'adreça (avís visible si no).
- Plantes: `pt` en comptes de `stl`; `lcd` DEPORTIVO → «piscina»; soterrani per `pt` negatiu / «SM».
- Redacció: `adjacent_formatter` amb el vocabulari de la taula (tancat), **agrupació de costats amb el mateix contingut** («Per la part est i pel sud
  amb parcel·les buides.»), «I finalment» a l'última frase que quedi, article correcte del carrer.
- `access_street` (§3.3) surt del mateix càlcul: el costat que és carrer.
- Mesura: forat-contra-forat no cal (frase sencera); sí que cal tolerar l'agrupació (dos costats → una frase idèntica: ja ho fa la veritat).

**Esforç:** M (3 causes de cablejat + vocabulari + agrupació). **Guany estimat (CA):** 16 cel·les avui 1 M + 8 C → 8-10 M+C de 16 (el detall
vegetal quedarà CLOSE). No és una mesura: és estimació.

### 3.2 `site_description` (0·0·0·7; plantilla p124, paràgraf sol)

**Estructura real del bloc de l'Eva (p082-p087 dels signats):**
1. Frase d'entrada — **ja és p122 de la plantilla** amb el forat `access_street`.
2. **Estat del solar** (1-3 frases, judici de la visita): Castellar «El solar es localitza sense construccions ni pavimentacions, s'ha realitzat un
   desbroç de la zona de treball… Topogràficament, el solar presenta pendent, amb una plataforma de treball… situada aproximadament 4.0 metres
   respecte el carrer.»; Rubí «El solar es localitza sense construccions i pavimentacions. Topogràficament, fa una lleugera baixada, de sudoest a
   nord-est… 13.20 metres…»; Linyola «La parcel·la es troba uns 15 cm per sota del nivell del carrer, es localitza explanada, sense pavimentar, i
   amb vegetació puntual de petita alçada.»; Bell-lloc «La parcel·la, que es troba delimitada tanques de parcel·les veïnes, està anivellada a la
   rasant del carrer, només uns 15 cm per sota, sense pavimentar, i amb vegetació de petita alçada.»; Alcoletge «El solar està actualment ocupat per
   una zona explanada i un edifici en planta baixa a la meitat nord. L'ampliació… part posterior…».
3. «En solars propers existeixen construccions de característiques similars…» — **ja és p126 fix** (5/5 CA).
4. «Destacar que no es poden veure aflorar els materials…» — **ja és p127 fix** (5/5 CA).

Per tant `site_description` = **només l'estat del solar** (bloc 2). Avís: `site_text_generator._generate_site_description` (síntesi d'ortofoto)
torna a incloure la frase d'entrada i les dues fixes → si mai s'activa, el `.docx` les duplica (comprovar abans d'encendre-la). La veritat de
l'extractor conté tot el bloc (1+2+3+4): la mesura ha de comparar bloc renderitzat (p122+p124+p126+p127) contra bloc, o retallar la veritat.

**Vocabulari de l'estat del solar (tancat, 5 signats):** {sense construccions ni pavimentacions | explanada, sense pavimentar | ocupat per <edifici
existent>} + {amb vegetació (puntual) de petita alçada | herbes altes} + {anivellada a la rasant del carrer (±15 cm) | presenta pendent (+ desnivell
X m)} + {desbroç / plataforma de treball}. **Fonts:** parcel·la pròpia al Cadastre (té construcció? → Alcoletge sí), pendent ICGC MDT
(`slope_percent`: Castellar 33,6 %, Bell-lloc 3,3 %, Linyola 0,4 %, Alcoletge 4,5 %), diferència de cota carrer/parcel·la (MDT 2 m: no arriba a
15 cm), fotografies de `FOTOGRAFIES/` (vision opcional: pavimentació, vegetació, tanques). **Proposta:** frase per criteri com a **defecte
editable** al wizard («El solar es localitza sense construccions ni pavimentacions, i amb vegetació de petita alçada.» / «…presenta pendent…»),
amb els fets del Cadastre i l'ICGC; la resta és de l'Eva. **Esforç:** M. **Guany:** CLOSE a 4-5 de 5 CA, MATCH improbable.

### 3.3 `access_street` (0·0·0·6; plantilla p122 «…a través del {{ access_street }}.»)

**Forats de l'Eva:** «carrer adjacent situat al **sud**» (Castellar), «carrer de la **Miranda**» (Rubí), «la del Carrer existent al **sud**»
(Bell-lloc, amb la seva errata), «carrer adjacent situat al **oest**» (Linyola), «Carrer existent al **nord**» (Alcoletge), «camino de accesos situado
en el norte» (Anciles). Dues formes: **nom del carrer** o **«carrer existent/adjacent situat al <costat>»**. Avui `access_street` es deriva d'un
`access_description` que a la via A no existeix → buit (cablejat). **Font:** el costat carrer dels adjacents (§3.1) i el nom de la via de l'adreça
llegida. **Proposta:** candidats «carrer <Nom>» (si l'adreça té via) i «carrer existent al <costat>» (si un únic costat és carrer); Linyola mostra que
l'Eva pot preferir la forma per costat encara que conegui el nom. **Esforç:** S (un cop els adjacents són bons). **Guany:** 4-5 de 5 CA (MATCH/CLOSE).

---

## 4. Grup 2 — la resta

| Variable | viaA M·C·X·ND | Fórmula de l'Eva (literal, signats CA) | Gen avui | Causa | Font | Esforç | Guany est. (CA) |
|---|---|---|---|---|---|---|---|
| `materials_intro` (p295, paràgraf sol) | 0·0·7·0 | «A partir dels assaigs in situ realitzats, s'ha establert **un sòl nivell / dos nivells** de materials des del punt de vista geològic - geotècnic: (veure annex "Registre assaigs mecànics"):» — 5/5 idèntica (Castellar «nivel», errata) | «A partir dels resultats dels assaigs de penetracio dinamica realitzats, s'han identificat N nivells geotecnics fins a la fondaria investigada.» | fórmula pròpia en comptes de la de l'Eva («in situ» inclou el sondeig) | nombre de nivells (ja el tenim) | S | +5 |
| `conclusions_aggressivity_statement` (p565) | 0·0·6·0 | «A partir dels resultats dels assaigs de laboratori realitzats, els materials del subsòl on es preveu armar la fonamentació, **a priori,** es presenten **NO AGRESSIUS** al formigó.» (4/5; «a priori» 3/5; majúscules/minúscules varien; Bell-lloc «xxxx» = forat que l'Eva no va omplir; Anciles ES «…los materiales del 2do nivel descrito se presentan, a priori xxxxxxx al hormigón.») | «El contingut en sulfats del terreny es de 90 mg/kg. El terreny es classifica com a NO AGRESSIU al formigó segons el Codi Estructural (CE-21).» | fórmula pròpia; a més Alcoletge/Vilanova/Anciles diuen «No s'han realitzat assaigs» perquè `sulfate_value` no arriba (cablejat del laboratori: els tres tenen sulfats al GTL) | classe d'agressivitat (ja la tenim on el laboratori arriba) | S text; cablejat lab a part | +4 ara, +1 amb lab |
| `radon_zone_description` (p497, cua després de «pertany a la ZONA {{ radon_zone }}») | 0·0·7·0 | zona 1: «pertany a la ZONA 1.» (Castellar, Bell-lloc, Alcoletge) o «…ZONA 1, municipi amb concentracions **inadequades** de gas radó en edificis tancats.» (Rubí); **zona 0** (Linyola): «**no pertany a cap municipi** amb concentracions inadequades de gas radó en edificis tancats.»; zona 2 (Anciles): «pertenece a ZONA 2.». Municipi en MAJÚSCULES i amb apòstrof: «d'ALCOLETGE», «de BELL-LLOC D'URGELL» | «, municipi amb concentracions mitjanes de gas radó en edificis tancats. Es recomana la implementació de mesures bàsiques de protecció.» (frase que l'Eva no escriu mai) | fórmula pròpia; el «pertany a la ZONA» fix de la plantilla no serveix per a la zona 0; `{{ municipality }}` en comptes de majúscules + «de/d'» | zona (7/7 correcta a `municipal_data`: Linyola 0, Anciles 2) | S (mou «pertany a la ZONA N» dins la variable; `de_municipality_upper`) | +5 |
| `csn_radon_text` (p498) | 0·0·4·3 | paràgraf fix 7/7 — **ja és p474 fix de la plantilla** | text de cartografia CSN per coordenades (dues vegades al `.docx`) | afegit que l'Eva no fa | — | S: `csn_radon_text = ''` i **treure la variable de M341** | 7 cel·les fora del denominador |
| `building_structure_desc` (p404/p570) | 0·0·7·0 | **(a)** «en planta baixa[ i porxo], i per tant, no es preveu cap excavació important, únicament l'excavació pel sanejament, anivellació, i per a la implantació **dels elements** de fonamentació.» (Rubí PB+porxo, Bell-lloc Pb+1Pp) · **(b)** «sense nivell de soterrani, i per tant, únicament es preveu el sanejament, anivellació, i l'excavació fins a la cota de fonamentació.» (Castellar Pb+1 «d'estructures», Linyola PB, Alcoletge ampliació) · **(c)** soterrani (Anciles ES, text lliure: «un semisótano en dos de las siete viviendas previstas, con lo que se prevé… una excavación de unos 2-3 m en la zona de S-1/P-6 y S-2/P-5.») | «en planta baixa» + cua fixa de la plantilla = (a) sense «dels elements»; Alcoletge imprimeix el `building_type` («Tancament de porxo en casa unifamiliar…») dins la frase (L826) | dues implementacions que discrepen (wizard L1036-1061: PB sol → «en planta baixa», altrament «sense nivell de soterrani»; generador L815-826: `num_floors` que comenci per PB/PS, si no `building_type`); l'Eva NO tria (a)/(b) per plantes (Linyola PB → (b); Bell-lloc Pb+1Pp → (a)) | plantes/soterrani llegits | S-M (variable = clàusula sencera; 2 candidats; una sola implementació) | +3 amb defecte, +5 com a candidats |
| `site_condition` (p342/p559) | 0·0·7·0 | capçalera: «**Com que es tracta d'un solar pla**» (Linyola, Alcoletge) · «**Tot i no ser un solar pla**» (Castellar, pendent 33 %) · «**Degut a que es tracta d'un solar antropitzat**» (Bell-lloc) · «**Es tracta d'un solar no antropitzat**» (Rubí, 13 m de desnivell però zona de treball plana); cua fixa idèntica 5/5; ES: «En la zona de estudio no se han detectado marcas de inicios de procesos de erosión relacionados con la escorrentía hídrica superficial.» (2/2) | «pla» dins «Degut a que es tracta d'un solar {{ }}» → «Degut a que es tracta d'un solar pla» (combinació que l'Eva no escriu) | la plantilla espera un qualificatiu; el wizard (L553-610) ja calcula la FRASE SENCERA amb el criteri correcte (pendent > 10 % / antropitzat) però el generador la ignora i emet «pla / antropitzat / no antropitzat» | pendent ICGC (`slope_percent`), antropitzat (parcel·la pròpia construïda al Cadastre; fotografies) | S (variable = capçalera sencera, com `settlement_sentence`; criteri del wizard com a única implementació + candidats) | +3-4 (Bell-lloc «antropitzat» i Rubí sense UTM queden com a candidat) |
| `conclusions_water_statement` (p563) | 2·3·2·0 | «En data de la realització dels treballs de camp, i fins la cota **estudiada / assajada**[,] no es va detectar presència de nivell freàtic en **cap dels punts estudiats / tots els assaigs realitzats / cap dels assaigs realitzats**.» + opcional humitat (Alcoletge «Cal destacar però, que es detecta humitat en els materials del subsòl a partir de la cota de -1.00 m…»; Vilanova ES humitat a P-1 -1,00) | igual que la variant «estudiada / cap dels punts estudiats» | ja bé; Castellar veritat equivocada (§2.2); humitat = observació de camp (full DPSH) | fitxa de camp | S (variants com a candidats; humitat = pregunta de lectura) | +1-2 |
| `conclusions_levels_detected` (p506) | 5·0·2·0 | «Es detecta un sòl nivell / dos nivells de materials des del punt de vista geològic/geotècnic en el subsòl del solar en estudi.» | idèntic | els 2 X són ES («A partir de los ensayos realizados se puede describir en el solar en estudio dos niveles…») | — | — | 0 |
| `location_sentence` (grup A, p070 «…es situarà {{ }}.») | 0·0·7·0 | Bell-lloc: «entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell» — **els altres 6 no els sabem** (veritat equivocada, §2.2) | Bell-lloc «entre el **Situat entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz** i el Carrer Antoni Bellet Pérez de…» (l'adreça llegida ja és «entre X i Y» i el generador la torna a embolcallar); Castellar/Linyola «entre el Carrer Arbrells i el Carrer **dels** Arbrells» (el mateix carrer dues vegades: nom llegit vs nom del Cadastre) | veritat mal extreta + 2 bugs del generador | adreça llegida, carrers dels adjacents | S extractor (prefix «es situarà» primer) → mesurar → S generador (dedupe per nom normalitzat; adreça «entre…» tal qual) | desconegut fins a tenir les 7 veritats |
| `lab_tests_text` (p265, cel·la de taula) | 0·2·2·3 | llista d'assaigs del GTL, una línia per assaig: «1 assaig de contingut en sulfats UNE 83963 : 2008» · «Assaig de Límits d'Atterberg UNE 103103/94 – 104/93» · «Assaig d'expansivitat Lambe UNE 103500/94» · «Anàlisi granulomètrica d'un sòl per tamissat UNE 103101/95» · «Contingut en sulfats solubles dels sòl UNE 83963/08» (Alcoletge: nom del GTL) | sempre «Contingut en sulfats solubles UNE 83963:2008» (o buit) | cablejat: la lectura del GTL no passa la llista d'assaigs | GTL (ja es llegeix) | S-M (vocabulari tancat de 4-5 assaigs + norma) | +3-4 |
| `photo_site_text` (p130 «{{ }}. Vistes generals de la zona d'estudi.») | 0·1·2·0 (+4 absents) | Bell-lloc «Fotografia 1 i Fotografia 2. Vistes generals de la zona d'estudi.» (= plantilla); Rubí «Fotografia 1. **Vista general** de la zona d'estudi (Google Earth, Agost 2024).»; **Castellar, Linyola, Alcoletge, Anciles: el bloc no existeix** (la Fotografia 1 és la màquina) | «Fotografia 1 i Fotografia 2» (el generador assumeix que l'Eva SEMPRE posa dues vistes; L671: fals a 4/7) | bloc condicional tractat com a fix; numeració de fotos en cascada | `FOTOGRAFIES/vista_general_*` (existència) | M (bloc condicional + renumeració) | +1-2 |
| `empentes_paragraph` (p583, secció condicional) | 0·0·0·2 | «Pel dimensionament del murs que es projectin i pel càlcul de les empentes de terres caldrà tenir en compte els paràmetres geomecànics dels materials del **1er** nivell que es considera el més desfavorables. Cal tenir en compte que en el trasdors del mur, caldrà instal·lar un correcte drenatge per a evitar que s'acumuli aigua i es produeixi un sobrecàrrega en el seu trasdors.» (Castellar; Anciles ES idèntic) | Ka/Kp de Rankine (l'Eva no ho fa) | fórmula pròpia; disparador `include_earth_pressure` | nivell més desfavorable (criteri: el de menys φ/c) ; disparador = soterrani o pendent | S | +1-2 |
| `estabilitat_paragraph` (p587) | 0·0·0·1 | Castellar: text d'enginyeria (Hoek & Bray, FS 1,8 / > 3,5, pendent 20-25º) | — | judici + càlcul | — | fora d'abast (camp lliure del wizard) | 0 |

**No mesurat per M341 però narratiu:** la frase d'introducció dels adjacents (§3.1); «Tampoc es detecta cap curs d'aigua superficial…» (fix p344/p561,
= 4/5 CA; Castellar hi afegeix «Amb tot, donada la pendent de la zona, es recomana dimensionar una correcta xarxa de recollida d'aigües…», que el
generador ja escriu però a la frase del freàtic, no a la del curs d'aigua; Anciles cita el riu Ésera a 400 m).

---

## 5. Mesura: què s'ha de canviar ABANS de tocar cap text (peça 0)

1. **Forat contra forat** per a `site_condition`, `building_structure_desc`, `radon_zone_description`, `access_street`, `photo_site_text`: renderitzar
   el paràgraf de la plantilla amb el context, treure a totes dues bandes el text comú a extrems (paraules), puntuar els residus (exacte → MATCH;
   similitud ≥ 0,6 → CLOSE). Per a `site_description`: bloc p122+p124+p126+p127 contra el bloc de la veritat.
2. **Treure `csn_radon_text`** del grup narrativa (paràgraf fix de la plantilla): 7 cel·les fora.
3. **Extractor de referència: prefix primer.** Quan la plantilla té prefix fix, buscar PRIMER el paràgraf del signat que el conté («es situarà»,
   «a través del», «es tracta d'un solar», «construcció d'una estructura») i només si no n'hi ha cap, la similitud. Recupera les 7 veritats de
   `location_sentence`, `access_street` de Linyola i deixa `conclusions_water_statement` de Castellar com a absent.
4. **Etiqueta d'idioma per projecte** al resum: narrativa CA i ES per separat (ES = sostre, no error).
5. Re-executar M341 (`2026-09-0X-m341-mesura-narr`) i `diff` dels `_compare_341.txt` contra `2026-09-06-m341`: aquest és el **baseline real** de la
   narrativa. Estimació (no mesura): els artefactes sols mouen 4-6 cel·les i el denominador baixa 7.

---

## 6. Castellà (decisió, no peça)

2 dels 7 signats són en castellà (Vilanova és municipi català: l'idioma el tria el client, no el municipi). El sistema ja té la detecció i 4 frases ES;
la plantilla és CA. Opcions: **(i)** plantilla ES completa paral·lela (les fórmules d'aquest document tenen equivalent ES literal als 2 signats:
`materials_intro`, radó, CSN, estat del solar, freàtic, empentes); **(ii)** només CA i l'Eva tradueix. Pregunta a l'Eva: quants encàrrecs en castellà
l'any? Fins que no es decideixi, les 30 cel·les ES no compten com a error de narrativa.

---

## 7. Ordre proposat i GO demanat

| Peça | Contingut | Esforç | Guany estimat (narrativa CA, 65 mesurables) |
|---|---|---|---|
| **0. Mesura** | §5 (comparador forat-contra-forat, `csn` fora, extractor prefix-primer, etiqueta ES) + re-run | S | baseline real (37 % → ≈ 40-45 %) |
| **1. Fórmules per criteri** | `automation/narrative_criteria.py` (com `settlement_criteria.py`): `materials_intro`, agressivitat, radó (zona 0/1/2, «de/d'», majúscules), capçalera de `site_condition` (criteri del wizard com a única implementació + candidats), `building_structure_desc` (clàusula sencera, 2 candidats, soterrani), `empentes`, `csn = ''`. Plantilla: 3 variables passen a clàusula sencera (regla 2026-09-05: grep del signat fet aquí) | S-M | +20-25 cel·les (→ ≈ 70 %) |
| **2. Adjacents + accés (grup 1)** | §3.1 (RC de la via A → `rc14`; `pt` en comptes de `stl`; geocodificar l'adreça llegida quan no hi ha UTM; vocabulari + agrupació + «I finalment»); §3.3 `access_street` del costat carrer | M | +8-12 (→ ≈ 80 %) |
| **3. Estat del solar + laboratori + fotos** | §3.2 defecte per criteri editable; `lab_tests_text` del GTL; bloc de fotos condicional | M | +6-8 |
| **4. Castellà** | §6, decisió del Josep/Eva | L | 30 cel·les |

**Recomanació:** GO a **0 + 1** junts (cost baix, tot fórmula i mesura, zero dependència de xarxa), després **2**. Cada peça: `mesura_341.py` +
`mesura_informe.py` (les 11 taules no es mouen) + `diff` per cel·la, com fins ara.

---

## 8. Preguntes a l'Eva que surten d'aquesta anàlisi (a `PREGUNTES-EVA-PENDENTS.md`, files 16-19)

16. **Adjacents:** el nord/sud/est/oest és el del plànol de situació o el geogràfic? Quan un costat és carrer, sempre en dius el nom? «De fins a dos
    plantes» ho treus del Cadastre o de la visita? Quan agrupes costats («est i sud amb parcel·les buides»)?
17. **Estat del solar:** quan un solar és «antropitzat» (Bell-lloc: anivellat, tanques) i quan «no antropitzat» (Rubí, 13 m de desnivell)? És la
    pendent el que fa «Tot i no ser un solar pla»?
18. **Estructura:** «en planta baixa, i per tant, no es preveu cap excavació important…» i «sense nivell de soterrani, i per tant, únicament es preveu
    el sanejament…» les fas servir indistintament o hi ha un criteri (plantes? ampliació?)? Què escrius quan hi ha soterrani (en català)?
19. **Fotografies «vistes generals»:** quan hi són (Bell-lloc, Rubí) i quan no (Castellar, Linyola, Alcoletge)? I **castellà**: quants informes l'any?

---

*Fi anàlisi narrativa 2026-09-06 (nit). Artefacte de mesura + fórmules de l'Eva + dades mal cablejades + idioma; ordre 0 → 1 → 2 → 3; GO pendent.*

---

## 9. Fet (mateixa nit, GO del Josep a 0 + 1 i després 2) — resultats

| Run (`viaA`, 7) | narrativa M · C · X · ND → % | CA | ES | total escalars+narr | taules |
|---|---|---|---|---|---|
| `2026-09-06-m341` (comparador antic) | 8 · 18 · 61 · 22 → 30 % | — | — | 58 % | 78 % |
| `-mesura` (peça 0) | 3 · 16 · 64 · 19 → **23 %** | 30 % | 5 % | 58 % | 78 % |
| `-narr1` (peça 1) | 22 · 22 · 38 · 20 → **54 %** | 57 % | 43 % | 66 % | 78 % |
| `-narr2c` (peça 2) | 29 · 29 · 36 · 15 → **62 %** | **65 %** | 52 % | **68 %** | 78 % |

Les estimacions de §7 (peça 1 → ≈ 70 %, peça 2 → ≈ 80 % CA) eren optimistes: el comparador forat-contra-forat és més estricte que
l'antic (un detall de la visita al veí → MISMATCH, no CLOSE) i el recompte de nivells de Rubí i Linyola (P5) frena `materials_intro`
i `conclusions_levels_detected`. Detall complet, limitacions i següents passos: DECISION-LOG 2026-09-06 (nit). Troballes de pas:
la plantilla (també la de producció) imprimia dos adjacents sobrers i li faltaven la capçalera 2.1 i la frase d'introducció; el
generador ignorava `site_condition` i `building_structure_desc` del `user_data` de l'Eva; el DNPRC llegia la superfície com a planta.

*Fi §9. Peces 0-2 fetes; peça 3 i castellà a la cua.*
