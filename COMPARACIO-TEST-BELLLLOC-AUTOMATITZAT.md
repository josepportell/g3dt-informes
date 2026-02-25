# Comparació: Informe Automatitzat vs Referència
## Projecte: 4001612 Bell-Lloc d'Urgell

**Data execució:** 2026-02-05
**Informe referència:** `reference-material/4001612-bell-lloc/4001612_informe.doc`
**Informe generat:** `samples/test_belllloc_automatitzat.docx`
**Comanda:** `uv run --with xlrd,docxtpl,pydantic,requests,shapely python3 -m automation.report_generator reference-material/4001612-bell-lloc --user-data reference-material/4001612-bell-lloc/user_data.json --output samples/test_belllloc_automatitzat.docx`

---

### Resum Executiu

| Mètrica | Valor |
|---------|-------|
| Seccions comparades | 4 (Presentació, Treballs, Geologia, Conclusions) |
| Errors durant generació | 0 (warning: shapely absent, resolt afegint-la) |
| Warnings | 1 (coordenades UTM afegides manualment, cal verificar) |

**Troballa principal: El template .docx conté dades hardcoded d'un projecte diferent (zona Vallès-Penedès) que NO es sobreescriuen per l'automatització.** Això afecta taules, textos geològics i dades numèriques.

**Diferències CRÍTIQUES trobades:**

| # | Diferència | Referència | Generat | Causa |
|---|-----------|-----------|---------|-------|
| 1 | **Geologia regional** | Depressió de l'Ebre, Qvpu (Plistocè) | Fossa Vallès-Penedès, NMgo (Miocè) | Template hardcoded + coordenades UTM incorrectes |
| 2 | **Nombre assaigs DPSH** | 2 (P-1, P-2) | 3 (P-1, P-2, P-3) a taules | Taules template no sobreescrites (dades altre projecte) |
| 3 | **Cota inici assaigs** | +199.50 msnm | +212.50 msnm a taules | Taules template hardcoded |
| 4 | **Profunditats DPSH** | P-1: -1.35m, P-2: -2.45m | P-1: -4.55m, P-2: -3.58m, P-3: -3.13m | Taules template hardcoded |
| 5 | **Valor SPT N30** | 54 (a S-1, -1.00 a -1.60m) | 40 (a P-3, -0.60 a -1.20m) | Taules template hardcoded |
| 6 | **Sulfats** | 89.8 mg/kg | 632.3 mg/kg (a taula) | Taula template hardcoded |
| 7 | **Qa fonamentació** | 3.0 Kg/cm² | 3.50 Kg/cm² | Càlcul Terzaghi amb dades DPSH reals vs referència |
| 8 | **Assentaments** | <1.20 cm | ≤1.50 cm | Idem |
| 9 | **Data treballs** | 1 i 6 d'octubre de 2025 | Buida ("El dia ,") | No extreta |
| 10 | **Adreça** | Carrer Antoni Bellet / Carrer Mestre Ramon Ortiz | Carrer de la Miranda nº 39, (PARC. 6-105) | Template hardcoded |

---

## ANÀLISI DETALLADA

### Problema #1: Template amb dades d'un altre projecte

**Impacte: CRÍTIC**

El template `g3dt-jinja-template.docx` conté text i taules estàtiques d'un projecte real anterior (aparentment zona Vallès-Penedès, amb 3 DPSH, cota +212.50). L'automatització genera variables Jinja correctament, però les seccions del template que NO tenen placeholders Jinja mantenen les dades originals del projecte base.

**Evidència:**
- Taula 3 (DPSH): Mostra P-1/P-2/P-3 a +212.50 → No correspon a l'Excel 4001612 (2 tests, +199.50)
- Taula 4 (SPT): SPT-1 a P-3, N30=40 → Excel 4001612 té SPT-1 a S-1, N30=54
- Taula 7 (Permeabilitat): K=10⁻¹⁰⁻¹ → Referència té K=10⁻¹⁰⁻²
- Taula 8 (Sulfats): 632.3 mg/kg → Referència té 89.8 mg/kg
- Taula 10 (Geotècnics): Nb=47-R, N=40, φ=39°, E=450 → Referència Nb=25-R, N=54, φ=38°, E=650
- Text cos secció 3.1: Descriu Fossa Vallès-Penedès (Miocè, IGME Hoja 392 Sabadell) → Bell-Lloc és Depressió de l'Ebre

**Seccions afectades:**
| Secció | Element | Dada template | Dada correcta (referència) |
|--------|---------|---------------|---------------------------|
| 1.1 | Adreça | Carrer de la Miranda nº 39 | Carrer Antoni Bellet / Mestre Ramon Ortiz |
| 1.1 | Tipus edifici | "habitatge unifamiliar aïllat modular" | "habitatge unifamiliar" |
| 2.2 | Nombre DPSH | 3 | 2 |
| 2.4 | Taula DPSH | 3 tests, +212.50, -4.55/-3.58/-3.13 | 2 tests, +199.50, -1.35/-2.45 |
| 2.4 | Taula SPT | P-3, N30=40 | S-1, N30=54 |
| 2.5 | Taula lab | Granulometria + Atterberg + Sulfats | Només sulfats |
| 3.1 | Text geològic | Vallès-Penedès, NMgo, Miocè | Depressió Ebre, Qvpu, Plistocè |
| 3.4 | Taula sulfats | 632.3 mg/kg | 89.8 mg/kg |
| 3.6 | Taula sísmica C | Gruix 4.55m | Gruix 2.45m |
| 4.1 | Taula geotècnica | Nb=47-R, N=40, φ=39°, E=450 | Nb=25-R, N=54, φ=38°, E=650 |
| 4.3 | Qa | 3.50 Kg/cm² | 3.0 Kg/cm² |

**Acció requerida:** Convertir TOTES les taules i textos dinàmics a variables Jinja al template. Eliminar qualsevol dada hardcoded d'un projecte específic.

---

### Problema #2: Coordenades UTM

**Impacte: ALT**

Les coordenades UTM no estaven al `user_data.json` (eren `null`). S'han afegit manualment (315006.52, 4611117.49) basant-se en geocodificació de l'adreça, però l'ICGC retorna unitat **P8G** (Eocè-Oligocè) per aquestes coordenades, quan la referència diu **Qvpu** (Plistocè).

**Verificació realitzada:**
| Coordenades | Unitat ICGC | Descripció | Regió |
|-------------|-------------|------------|-------|
| 315006, 4611117 (afegides) | P8G | Gresos i lutites (Eocè-Oligocè) | depressio_ebre |
| 307500, 4615500 (test code) | Q3D | Graves, sorres i llims (Holocè) | depressio_ebre |
| (referència espera) | Qvpu | Graves en matriu lutítica (Plistocè) | depressio_ebre |

**Nota:** Cap de les coordenades provades retorna Qvpu. Les coordenades exactes del solar són necessàries per obtenir la unitat ICGC correcta. Les coordenades (307500, 4615500) s'aproximen més (material quaternari) però tampoc coincideixen exactament.

**Acció requerida:**
1. Obtenir coordenades UTM exactes del projecte (del plànol topogràfic o Google Maps)
2. O bé: permetre entrada manual de la unitat ICGC a `user_data.json`

---

## COMPARACIÓ SECCIÓ PER SECCIÓ

### SECCIÓ 1: PRESENTACIÓ DE L'ESTUDI

| Element | Referència | Generat | Match | Nota |
|---------|-----------|---------|-------|------|
| Títol secció | `1 . PRESENTACIÓ DE L'ESTUDI` | Idèntic | ✅ | — |
| Client | `RAMON MITJANA S.L.,` | `RAMON MITJANA SL` | ⚠️ | Falta punt a "S.L." i coma |
| Text intro G3DT | Idèntic | Idèntic | ✅ | Text fix template |
| Paràgraf antecedents | "el SR. JORDI BOSCH NOVELL, de l'ARQUITECTURA BOSCH NOVELL, en nom de RAMON MITJANA S.L" | "la RAMON MITJANA SL" | ❌ | No inclou arquitecte ni "en nom de". Template massa simplificat |
| Tipus edifici | "habitatge unifamiliar" | "habitatge unifamiliar aïllat modular" | ❌ | **Template hardcoded** ("aïllat modular" és d'un altre projecte) |
| Taula 1 dades | Pb+1Pp, 995m², 280+86m² | Taula buida (sense valors) | ❌ | Valors Jinja no injectats a taula |
| Ubicació | "entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell" | "carrer de la Miranda nº 39, (PARC. 6-105) Carrer Mestre Ramon Ortiz, 25220 Bell-Lloc d'Urgell (Lleida), Bell Lloc" | ❌ | **Template hardcoded** + `street_address` del user_data |
| Figures 1-2 ubicació | Figures del projecte arquitecte | Figura 1 ICGC mapa | ⚠️ | Figures arquitecte no disponibles, usa ICGC |
| Classificació CTE | C-1, T-1 | C-1, T-1 | ✅ | Càlcul automàtic correcte |
| Objectius (6 punts) | Idèntics | Idèntics | ✅ | Text fix |

**Resum Secció 1:** ✅ 5 | ⚠️ 2 | ❌ 4

---

### SECCIÓ 2: TREBALLS DE CAMP

| Element | Referència | Generat | Match | Nota |
|---------|-----------|---------|-------|------|
| Data visita | "1 d'octubre de 2025" | Buida ("El dia ,") | ❌ | Data no extreta de cap font |
| Inspeccions (4 punts) | Idèntiques | Idèntiques | ✅ | Text fix |
| **Parcel·les adjacents** | | | | |
| Posició | "al oest del municipi" | "al sud-oest del municipi" | ⚠️ | Diferent orientació |
| Nord | "parcel·la buida" | "parcel·les sense edificacions i amb vegetació" | ⚠️ | Més genèric |
| Sud | "Carrer Antoni Bellet" | "carrer de la Miranda" | ❌ | **Template hardcoded** |
| Est | "Carrer Mestre Ramon Ortiz" | "construccions similars" | ❌ | **Template hardcoded** |
| Oest | "construcció aïllada 2 plantes" | "construccions similars" | ❌ | **Template hardcoded** |
| **Descripció solar** | | | | |
| Accés | "Carrer existent al sud" | "carrer de la Miranda" | ❌ | **Template hardcoded** |
| Topografia | "anivellada, 15cm sota rasant" | "lleugera baixada, 13.20m desnivell" | ❌ | **Template hardcoded** (topografia d'un altre projecte!) |
| Construccions properes | Idèntic | Idèntic | ✅ | Text fix |
| Afloraments | Idèntic | Idèntic | ✅ | Text fix |
| **Reconeixement** | | | | |
| Data campanya | "1 i 6 d'octubre de 2025" | Buida | ❌ | No extreta |
| Llista assaigs | "2 DPSH + 1 sondeig + 1 SPT" | "3 DPSH + 1 SPT" | ❌ | **Template hardcoded** (3 DPSH d'altre projecte) |
| Lab TPS | Idèntic | Idèntic | ✅ | Text fix |
| **DPSH descripció** | Idèntica | Idèntica | ✅ | Text fix (procediment estàndard) |
| **Sondeig descripció** | 3 paràgrafs descriptius | 3 paràgrafs descriptius | ✅ | Text fix condicional (has_sondeig=true) |
| **SPT descripció** | Idèntica | Idèntica | ✅ | Text fix |
| **Taula 3 DPSH** | P-1(+199.50,-1.35) P-2(+199.50,-2.45) | P-1(+212.50,-4.55) P-2(+212.50,-3.58) P-3(+212.50,-3.13) | ❌❌ | **Template hardcoded** — Dades completament d'un altre projecte |
| **Sondeig taula** | S-1(+199.50,-1.80) | Absent | ❌ | Taula sondeig no generada |
| **Taula SPT** | SPT-1, S-1, -1.00 a -1.60, N30=54 | SPT-1, P-3, -0.60 a -1.20, N30=40 | ❌❌ | **Template hardcoded** |
| Nota cotes | Idèntica | Idèntica | ✅ | Text fix |
| **Taula 6 laboratori** | 1 assaig sulfats | Granulometria + Atterberg + Sulfats | ❌ | **Template hardcoded** (més assaigs que el projecte real) |

**Resum Secció 2:** ✅ 10 | ⚠️ 2 | ❌ 13

---

### SECCIÓ 3: DESCRIPCIÓ GEOLÒGICA I GEOTÈCNICA

| Element | Referència | Generat | Match | Nota |
|---------|-----------|---------|-------|------|
| **3.1 Marc geològic** | | | | |
| Paràgraf 1 (context) | "Depressió de l'Ebre, extrem oriental, Depressió Central Catalana" | "Hoja 392 Sabadell, Fossa Vallès-Penedès" | ❌❌ | **CRÍTIC: Template hardcoded**. Text geològic pertany a zona Vallès-Penedès, no a Bell-Lloc |
| Paràgraf 2 (tectònica) | "orogen pirinenc, placa Ibèrica/Europea" | "rifting Miocè, creació conca marina" | ❌❌ | Evolució tectònica diferent (Pirineu vs Mediterrani) |
| Paràgraf 3 (Eocè) | "connectada amb Atlàntic, làmines encavalcants" | "enfonsament materials paleozoics, sèrie miocena" | ❌❌ | Història geològica diferent |
| Paràgraf 4 (Oligocè) | "conca endorreica, sedimentació continental" | "lutites, guixos, margues, ventalls litorals" | ❌❌ | Sedimentació diferent |
| Paràgraf 5 (actualitat) | "erosió, terrasses fluvials, Quaternari" | "dipòsits Pliocens, nòduls carbonàtics" | ❌❌ | Geomorfologia diferent |
| Paràgraf 6 (ICGC) | "unitat Qvpu, graves matriu lutítica, Plistocè" | "unitat NMgo, gresos amb lutites, Miocè" | ❌❌ | **CRÍTIC: Unitat ICGC incorrecta** |
| Mapa geològic | Figura 5 | Figura 4 | ⚠️ | Numeració diferent (acceptabl) |
| **3.2 Materials** | | | | |
| Intro | "un sòl nivell de materials" | "un sòl nivell de materials" | ✅ | — |
| Subtítol | "3.2.1. 1er Nivell" | "3.2.1. Nivell 1" | ⚠️ | Format ordinal diferent |
| Litologia | "graves en matriu sorrenca carbonatades, coloracions clars" | "graves i sorres, coloracions marró clar" | ⚠️ | Descripció similar però menys específica |
| Sòl vegetal | "30 cm" | "40-60 cm" | ❌ | **Template hardcoded** |
| Unitat ICGC | "materials plistocens, unitat Qvpu" | "unitat NMgo" | ❌ | Unitat incorrecta (problema coordenades) |
| Localització | "superficialment fins cota finalització, mínim 2.45m" | "potència màxima 4.55m" | ❌ | **Template hardcoded** (4.55m és d'un altre projecte) |
| Resistència | "capacitat portant elevada, Nb mig 25 fins rebuig, SPT N=54" | "capacitat portant mitja, Nb mig 48 fins rebuig" | ❌ | **Template hardcoded** (Nb=48 i "mitja" d'altre projecte) |
| **3.3 Hidrogeologia** | | | | |
| Superficial | "solar antropitzat, no marques erosió" | "no marques erosió, no curs d'aigua" | ✅ | Equivalent semàntic |
| Freàtic | "no detectat" | "no detectat" | ✅ | DPSH Excel confirma |
| Permeabilitat taula | K=10⁻¹⁰⁻², graves matriu sorrenca | K=10⁻¹⁰⁻¹, graves i sorres | ⚠️ | **Template hardcoded** valor K lleugerament diferent |
| **3.4 Agressivitat** | | | | |
| Text intro | Idèntic | Idèntic | ✅ | Text fix |
| Taula sulfats | 89.8 mg/kg, No agressius | 632.3 mg/kg, No agressius | ❌ | **Template hardcoded** (632.3 d'altre projecte) |
| Notes CE-21 | Idèntiques | Idèntiques | ✅ | Text fix |
| **3.5 Excavabilitat** | | | | |
| Context | "estructura en planta baixa" | "estructura en planta baixa i porxo" | ⚠️ | **Template hardcoded** ("+porxo" d'altre projecte) |
| Detall | "primers 1-1,5m sense problemes, profunditat martell pneumàtic" | "tram inicial sense problemes, carbonatat martell pneumàtic" | ✅ | Equivalent semàntic |
| **3.6 Sísmica** | | | | |
| Text normatiu | Idèntic | Idèntic | ✅ | Text fix |
| Valor ab | "AB < 0,04 g" | "AB = 0,08 g" | ❌ | **Error lookup municipal_data.py** |
| Exempció norma | "no obligatòria" | No present (perquè ab=0,08≥0,08) | ❌ | Conseqüència de l'error ab |
| Fórmules AC,S,C,ρ | Idèntiques | Idèntiques | ✅ | Text fix |
| Taula 9 C | Gruix 2.45m, C=1.30 | Gruix 4.55m, C=1.3 | ❌ | **Template hardcoded** gruix |
| **3.7 Radó** | | | | |
| Text normatiu | Idèntic | Idèntic | ✅ | Text fix (18 paràgrafs) |
| Zona classificació | "BELL-LLOC D'URGELL, ZONA 1" | "Bell Lloc, ZONA 1" | ✅ | Zona correcta |
| Detall classificació | "pertany a la ZONA 1" | "ZONA 1, concentracions inadequades" | ⚠️ | Generat afegeix text descriptiu (diferent del "original") |

**Resum Secció 3:** ✅ 12 | ⚠️ 6 | ❌ 15

---

### SECCIÓ 4: CONCLUSIONS

| Element | Referència | Generat | Match | Nota |
|---------|-----------|---------|-------|------|
| Intro | Idèntic | Idèntic | ✅ | Text fix |
| **4.1 Geologia** | | | | |
| Nivells | "un sòl nivell" | "un sòl nivell" | ✅ | — |
| Descripció nivell | "graves matriu sorrenca carbonatades, clars, 30cm sòl vegetal, Qvpu, 2.45m, portant elevada" | "graves i sorres, marró clar, 40-60cm sòl vegetal, NMgo, 4.55m, portant mitja" | ❌ | Múltiples diferències (template + coordenades) |
| Tall correlació | "Figura 6" | "Figura 5" | ⚠️ | Numeració diferent (acceptable) |
| Taula 10 geotècnica | Nb=25-R, N=54, γ=2.0, c=0.0, φ=38°, E=650 | Nb=47-R, N=40, γ=2.0, c=0.05, φ=39°, E=450 | ❌❌ | **Template hardcoded** — Tots els valors d'un altre projecte |
| Notes paràmetres | Idèntiques | Idèntiques | ✅ | Text fix |
| **4.2 Hidrogeologia** | | | | |
| Solar | "solar antropitzat" | "solar no antropitzat" | ❌ | **Invertit!** L'original diu "antropitzat", generat diu "no antropitzat" |
| Freàtic | "no detectat" | "no detectat" | ✅ | — |
| Agressivitat | "xxxx al formigó" (placeholder!) | "no agressius al formigó" | ✅ | Generat millor que l'original (original tenia placeholder) |
| **4.3 Fonamentació** | | | | |
| Context excavació | "estructura en planta baixa" | "estructura en planta baixa" | ✅ | — |
| Valoració | "fonamentació superficial sabates/llosa sobre primer nivell" | "fonamentació sabates/llosa encastada 30-40cm" | ⚠️ | Terminologia lleugerament diferent |
| **Qa** | **3.0 Kg/cm²** (F=3) | **3.50 Kg/cm²** (F=3) | ❌ | Càlcul Terzaghi amb dades DPSH reals vs template |
| Assentaments | "<1.20 cm" | "≤1.50 cm" | ❌ | Valors calculats diferent |
| K30 balast | No present | "K30= 6.0 kg/cm³" | ⚠️ | Generat afegeix valor no present a referència |
| Tancament G3DT | Idèntic | Idèntic | ✅ | Text fix |
| Expedient | "4001612" | "4001612" | ✅ | — |
| Data/lloc | "Els Omells de Na Gaia, 27 d'octubre de 2025" | "Els Omells de Na Gaia, 05 de February de 2026" | ⚠️ | Mes en anglès (bug locale). Data = dia generació (correcte) |
| Signatura | Eva Vázquez Marcet, Geòloga col 4302 | Idèntic | ✅ | — |

**Resum Secció 4:** ✅ 9 | ⚠️ 4 | ❌ 5

---

## RESUM GLOBAL

| Secció | Total elements | ✅ Correcte | ⚠️ Diferència menor | ❌ Diferència significativa |
|--------|---------------|------------|---------------------|---------------------------|
| 1. Presentació | 11 | 5 (45%) | 2 (18%) | 4 (36%) |
| 2. Treballs de Camp | 25 | 10 (40%) | 2 (8%) | 13 (52%) |
| 3. Geologia | 33 | 12 (36%) | 6 (18%) | 15 (45%) |
| 4. Conclusions | 18 | 9 (50%) | 4 (22%) | 5 (28%) |
| **TOTAL** | **87** | **36 (41%)** | **14 (16%)** | **37 (43%)** |

---

## CLASSIFICACIÓ D'ERRORS PER CAUSA ARREL

### 1. CRÍTIC: Template hardcoded amb dades d'un altre projecte (25 elements afectats)

**Causa:** El template `g3dt-jinja-template.docx` va ser creat a partir d'un informe real d'un projecte a la zona del Vallès-Penedès (3 DPSH, cota +212.50, NMgo Miocè). Les taules i alguns textos del cos NO tenen placeholders Jinja i conserven les dades originals.

**Elements afectats:**
- Taula 3 (DPSH): 3 tests a +212.50 en lloc de 2 a +199.50
- Taula 4 (SPT): P-3, N30=40 en lloc de S-1, N30=54
- Taula 5 (Laboratori): 3 assaigs en lloc d'1
- Taula 7 (Permeabilitat): Valor K diferent
- Taula 8 (Sulfats): 632.3 en lloc de 89.8 mg/kg
- Taula 9 (Sísmica): Gruix 4.55 en lloc de 2.45m
- Taula 10 (Geotècnica): Tots els valors incorrectes
- Secció 3.1: Text geològic Vallès-Penedès complet
- Secció 3.2: Potència 4.55m, sòl vegetal 40-60cm
- Secció 2.1: Parcel·les adjacents, topografia, adreça
- Secció 1.1: Tipus edifici "aïllat modular", adreça "Miranda"

**Acció requerida:** Substituir TOTES les dades estàtiques del template per variables Jinja. Cada cel·la de cada taula ha de ser dinàmica. Cada text que menciona dades específiques del projecte ha de tenir placeholder.

**Prioritat:** MÀXIMA — Sense això, l'automatització NO funciona per cap projecte diferent del que va servir de base per al template.

### 2. ALT: Coordenades UTM incorrectes/absents (6 elements afectats)

**Causa:** `user_data.json` tenia utm_x/utm_y a `null`. S'han afegit manualment coordenades aproximades (315006.52, 4611117.49) que no corresponen al solar exacte. L'ICGC retorna unitat P8G (Eocè-Oligocè) en lloc de Qvpu (Plistocè quaternari).

**Elements afectats:**
- Secció 3.1: Unitat geològica incorrecta
- Secció 3.2: Unitat ICGC incorrecta al text de materials
- Secció 4.1: Unitat repetida a conclusions

**Nota:** Fins i tot amb coordenades (307500, 4615500) del test code, l'ICGC retorna Q3D (Holocè), no Qvpu (Plistocè). Les coordenades exactes del solar són crítiques.

**Acció requerida:**
1. Obtenir coordenades UTM precises del plànol topogràfic
2. O permetre entrada manual de la unitat ICGC com a override a `user_data.json`

### 3. ALT: Valor sísmic ab incorrecte (3 elements afectats)

**Causa:** `municipal_data.py` → `get_seismic_ab_with_status()` retorna ab=0.08 per Bell-Lloc d'Urgell. L'informe de referència indica ab < 0.04g.

**Elements afectats:**
- Valor ab mostrat
- Paràgraf d'exempció NCSE-02 (no generat perquè ab≥0.08)
- Taula sísmica C

**Acció requerida:** Verificar/corregir l'entrada "Bell-Lloc d'Urgell" a la base de dades municipal_data.

### 4. MITJÀ: Dates de treball no extretes (2 elements afectats)

**Causa:** La data dels treballs de camp no s'extreu de cap font automàtica.

**Acció requerida:** Afegir camp `field_work_dates` a `user_data.json`.

### 5. MITJÀ: Inversió "antropitzat/no antropitzat" (1 element afectat)

**Causa:** Secció 4.2 diu "solar no antropitzat" quan la referència diu "solar antropitzat". Possible error al template o lògica condicional invertida.

**Acció requerida:** Verificar la condició `is_urban` al generador de conclusions.

### 6. BAIX: Format i locale (4 elements afectats)

**Causa:** Diferències menors de format.
- "S.L.," → "SL" (format empresa)
- "1er Nivell" → "Nivell 1" (format ordinal)
- Data en anglès "February" (locale no configurat)
- Numeració figures diferent (acceptable)

**Acció requerida:** Ajustos menors al template i configuració locale.

---

## DADES DPSH: EXCEL vs REFERÈNCIA

L'Excel `4001612_DPSH.xls` conté dades **consistents amb la referència**:

| Font | Tests | P-1 profunditat | P-2 profunditat |
|------|-------|-----------------|-----------------|
| Excel DPSH | 2 | -1.40m (6 readings) | -2.60m (12 readings) |
| Referència .doc | 2 | -1.35m | -2.45m |
| Generat (taula) | 3 | -4.55m | -3.58m |

**Conclusió:** L'Excel és correcte. Les dades a les taules del generat venen del template hardcoded, NO de l'extracció automàtica.

**Nota:** Petites diferències entre Excel i referència (-1.40 vs -1.35, -2.60 vs -2.45) poden ser degudes a arrodoniment o ajust manual per G3DT (la referència utilitza la profunditat de l'últim valor vàlid, no del rebuig).

---

## CONCLUSIONS I PRIORITATS

### Ordre d'actuació recomanat

1. **[CRÍTIC] Netejar template .docx** — Substituir TOTES les dades hardcoded per variables Jinja. Sense això, l'automatització no és funcional per projectes nous.

2. **[ALT] Coordenades UTM** — Implementar obtenció de coordenades del plànol topogràfic o geocodificació fiable. Permetre override manual.

3. **[ALT] Valor sísmic ab** — Verificar i corregir base de dades municipal per Bell-Lloc d'Urgell.

4. **[MITJÀ] Dates i camps manuals** — Afegir `field_work_dates`, `site_description`, `adjacent_details` a `user_data.json`.

5. **[BAIX] Format i locale** — Ajustar format empresa, ordinals i locale data.

### Què funciona bé

- Text estàndard fix (procediments, normativa, objectius): **100% correcte**
- Lògica condicional (sondeig, SPT, soterrani): **Funciona**
- Classificació CTE: **Correcta**
- Detecció freàtic: **Correcta**
- Zona radó: **Correcta (ZONA 1)**
- Signatura i tancament: **Correcte**
- Extracció DPSH Excel: **Correcta** (2 tests, valors correctes)
- Càlcul Terzaghi: **Funcional** (valors diferents perquè usa dades reals Excel, no les del template)

### Valoració global

L'automatització **extreu i calcula correctament** les dades del projecte (DPSH, CTE, freàtic, radó). El problema principal és que el **template .docx no està completament parametritzat** — conté dades estàtiques d'un altre projecte que es mostren al document final. Un cop resolt el template, l'automatització hauria de produir informes molt més propers a la referència.

---

*Document generat automàticament per comparació paral·lela dels textos extrets de tots dos informes.*
