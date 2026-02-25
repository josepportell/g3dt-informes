# Auditoria Automatització Informe Geotècnic
## Projecte referència: 4001612 Bell-Lloc d'Urgell

**Data:** 2026-02-05
**Basat en:** Comparació paràgraf a paràgraf (227 PARAs) entre informe original i generat

---

### Resum Executiu

*(Estadístiques finals al completar totes les seccions)*

| Mètrica | Valor |
|---------|-------|
| Total paràgrafs | 227 |
| ✅ Idèntics (>95%) | 173 (76.2%) |
| 🔶 Match alt (80-95%) | 16 (7.0%) |
| 🟡 Match mitjà (50-80%) | 17 (7.5%) |
| ❌ Match baix (<50%) | 21 (9.3%) |

**Principals desviacions trobades:**

1. **Municipi com a adreça** — On hauria de dir "Bell-Lloc d'Urgell" apareix "Carrer Antoni Bellet / Carrer Mestre Ramon Ortiz, Bell-Lloc d'Urgell". Afecta PARAs 49, 71, 77, 161, 200.
2. **Secció 3.1 Marc Geològic buida** — 6 paràgrafs de text geològic regional (PARAs 121-126) no generats. Requereix plantilles de zona del servidor G3DT.
3. **Secció Sondeig no implementada** — PARAs 102-106 (subsecció 2.4.2) falten completament. La secció condicional existeix al codi però no genera text descriptiu del sondeig.
4. **Valor sísmic incorrecte** — PARA 162: ab=0,08 en lloc de <0,04. Error en lookup municipal_data.
5. **Data de camp absent** — PARAs 64, 83: la data dels treballs no s'extreu del PDF/Excel.
6. **Paràgrafs descriptius de camp absents** — PARAs 78 (descripció solar), 157 (excavabilitat detallada), 220 (valoració fonamentació) requereixen observacions de camp manuals.

**Dependències pendents:**
- Plantilles de zona geològica (servidor G3DT) → Secció 3.1
- Observacions de camp (entrada manual) → Seccions 2.1.1, 2.1.2
- Data treballs de camp (DPSH PDF) → Secció 2.0, 2.2
- Descripció litològica detallada (plantilla zona) → Seccions 3.2, 4.1

---

## SECCIÓ 1: PRESENTACIÓ DE L'ESTUDI
### PARAs 041-062

#### 1.0 Introducció (PARAs 041-044)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 041 | `1 . PRESENTACIÓ DE L'ESTUDI` | Títol secció (fix) | Template Jinja estàtic | ✅ | — |
| 042 | `A petició de:` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 043 | `RAMON MITJANA S.L.,` | DADES CLIENT.txt línia 4 | `project_extractor.py` → `_read_client_data()` → `client.company_name` | ⚠️ | `S.L.,` → `SL` (format menor) |
| 044 | `G3 DT, S.L. ha realitzat el següent informe geotècnic segons les instruccions del DB SE-C Cimientos...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |

#### 1.1 Antecedents (PARAs 045-051)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 045 | `1.1. ANTECEDENTS` | Títol subsecció (fix) | Template Jinja estàtic | ✅ | — |
| 046 | `Segons ens indica el sol·licitant, el SR. JORDI BOSCH NOVELL, de l'ARQUITECTURA BOSCH NOVELL, en nom de RAMON MITJANA S.L, es vol valorar les característiques geològiques i geotècniques d'una zona on es preveu construir...` | Arquitecte: pressupost email. Client: DADES CLIENT.txt. Projecte: pressupost | `report_data.py` → `architect_name`, `architect_company`, `client.company_name`, `building_type` via `user_data.json` | ❌ | Paràgraf sencer no trobat al document generat (0% match). El template no inclou el paràgraf introductori amb arquitecte/projecte. Probable omissió al template Jinja |
| 047 | `L'edificació que es preveu construir presentarà les següents característiques:` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 048 | `Taula 1. Resum de les principals dades de l'edificació a construir.` | Capçalera taula (fix) | Template Jinja estàtic | ✅ | — |
| 049 | `L'edificació que es preveu construir es situarà entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell.` | Carrers: pressupost/ICGC. Municipi: nom carpeta | `report_data.py` → `street_address` + `municipality` | ⚠️ | "L'edificació" → "L'habitatge"; "entre el...i el" → "a.../..."; "de" → ","; Afegit "Bell Lloc" redundant al final |
| 050 | `Figura 1 i Figura 2. Detall de la ubicació de la parcel·la en estudi. Font: Projecte.` | ICGC viewer screenshots (topogràfic + ortofoto) | Template Jinja amb numeració dinàmica via `_build_numbering_context()` | ❌ | Figures 1-2 (ubicació plànol arquitecte) no generades. El generat té Figura 1=mapa ICGC. "Font: Projecte" → "Font: ICGC, modificat" |
| 051 | `Figura 3. Ubicació de l'habitatge a l'interior de la parcel·la. Font: Projecte.` | CONDICIONAL: "NOMÉS LA POSO SI TENIM ELS PLÀNOLS DE L'ARQUITECTE" | No implementat | ❌ | Figura condicional de plànol arquitecte no implementada |

#### 1.2 Classificació CTE (PARAs 052-054)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 052 | `1.2. CLASSIFICACIÓ DE L'OBRA SEGONS EL CTE` | Títol subsecció (fix) | Template Jinja estàtic | ✅ | — |
| 053 | `A partir de les dades exposades pel client, tant tipus d'edificació com localització de l'obra, un tècnic competent ha de redactar el pertinent estudi geotècnic...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 054 | `Taula 2. Classificació de la construcció segons DB-SE-C del CTE.` | Calculat: C-0/C-1/C-2 segons m² i plantes | `report_data.py` → `calculate_cte_class()`: C-0 (<300m², <4pl), C-1, C-2 | ✅ | — |

#### 1.3 Objectius (PARAs 055-062)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 055 | `1.3. OBJECTIUS` | Títol subsecció (fix) | Template Jinja estàtic | ✅ | — |
| 056 | `Per la realització del present estudi, s'ha dut a terme una campanya de camp tenint en compte que els objectius de l'estudi són els següents:` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 057 | `Estudi de l'entorn geològic de l'obra.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 058 | `Reconeixement, caracterització i potència dels materials del subsòl de la zona, des del punt de vista geotècnic.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 059 | `Cota del nivell freàtic, quan es detecti dins de les cotes assajades.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 060 | `Determinació de les càrregues admissibles dels materials sota diferents solucions de fonamentació.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 061 | `Estimació dels assentaments per a les càrregues admissibles exposades.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 062 | `Recomanacions sobre condicionants geològics i geotècnics que puguin afectar a l'obra.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |

**Resum Secció 1:** 22 paràgrafs — ✅ 17 | ⚠️ 2 | ❌ 3

---

## SECCIÓ 2: TREBALLS DE CAMP
### PARAs 063-118

#### 2.0 Introducció treballs de camp (PARAs 063-068)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 063 | `2. TREBALLS DE CAMP` | Títol secció (fix) | Template Jinja estàtic | ✅ | — |
| 064 | `El dia 1 d'octubre de 2025, es va visitar l'obra per tal de:` | Data: DPSH PDF header o DADES PER ANAR A CAMP.xlsx | Template Jinja amb placeholder buit per data | ⚠️ | Data "1 d'octubre de 2025" no extreta. Generat: `El dia , es va visitar...` (data buida) |
| 065 | `Realitzar una inspecció geològica de la zona, reconeixent el tipus de terreny.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 066 | `Dissenyar la campanya de camp.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 067 | `Comprovar l'accessibilitat de maquinària a l'interior del solar.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 068 | `Localitzar els punts on es realitzaran els assaigs.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |

#### 2.1.1 Descripció parcel·les adjacents (PARAs 069-075)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 069 | `2.1. DESCRIPCIÓ DE LA ZONA D'ESTUDI` | Títol subsecció (fix) | Template Jinja estàtic | ✅ | — |
| 070 | `2.1.1. Descripció de les parcel·les adjacents` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 071 | `La parcel·la objecte d'estudi es situa al oest del municipi de Bell-Lloc d'Urgell, pren una morfologia rectangular i limita:` | Posició (ICGC/Google); Municipi (carpeta); Forma (observació/cadastre) | `report_data.py` → `municipality`, `street_address` via `user_data.json` | ⚠️ | "oest" → "sud-oest"; Afegit adreça completa; Municipi OK. Orientació/forma requereixen entrada manual |
| 072 | `Per la part est amb el Carrer Mestre Ramon Ortiz.` | Observació camp + Google Maps/Earth | `user_data.json` → adjacents N/S/E/O | ⚠️ | "est" → "sud"; Falta article "el"; Carrers intercanviats (est↔sud) |
| 073 | `Per la part sud amb el Carrer Antoni Bellet.` | Observació camp + Google Maps/Earth | `user_data.json` → adjacents | ❌ | Generat: "Per la part sud, amb Carrer Mestre Ramon Ortiz" — Carrer incorrecte (hauria de ser Antoni Bellet) |
| 074 | `Per la part nord amb una parcel·la buida.` | Observació camp + Google Maps/Earth | `user_data.json` → adjacents | ⚠️ | "buida" → "veïna" (menys específic) |
| 075 | `I finalment, per la part oest, amb una parcel·la amb una construcció aïllada de fins a dos plantes sobre rasant.` | Observació camp + Google Maps/Earth | `user_data.json` → adjacents | ❌ | Generat: "Per la part est, amb parcel·la veïna." — Orientació incorrecta (oest→est) i descripció genèrica |

#### 2.1.2 Descripció del solar (PARAs 076-081)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 076 | `2.1.2. Descripció del solar` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 077 | `El dia dels treballs de camp es realitza l'entrada a la zona d'estudi a través de la del Carrer existent al sud.` | Observació camp (accés al solar) | Template amb `street_address` | ⚠️ | "la del Carrer existent al sud" → "Carrer Antoni Bellet / Carrer Mestre Ramon Ortiz, Bell-Lloc d'Urgell" — Usa adreça completa en lloc de referència genèrica |
| 078 | `La parcel·la, que es troba delimitada tanques de parcel·les veïnes, està anivellada a la rasant del carrer, només uns 15 cm per sota, sense pavimentar, i amb vegetació de petita alçada.` | Observació camp (estat solar) | No implementat | ❌ | Descripció detallada del solar requereix observació de camp manual. No hi ha template ni variable |
| 079 | `En solars propers existeixen construccions de característiques similars a la obra projectada que el client ens indica que no van presentar anomalies geotècniques importants durant la seva execució.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 080 | `Destacar que no es poden veure aflorar els materials que conformen el subsòl del solar ni en la parcel·la ni en les vores de les parcel·les pròximes.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 081 | `Fotografia 1 i Fotografia 2. Vistes generals de la zona d'estudi.` | FOTOGRAFIES/ folder (fotos camp) | Template Jinja amb `photo_count` | ⚠️ | "Fotografia 1 i Fotografia 2" → "Fotografia 1" (una sola foto); "Vistes generals" → "Vista general (Google Earth, Agost 2024)". Usa Google Earth en lloc de fotos camp |

#### 2.2 Reconeixement del terreny (PARAs 082-089)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 082 | `2.2. RECONEIXEMENT DEL TERRENY` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 083 | `La campanya de camp, que s'ha realitzat el dia 1 i 6 d'octubre de 2025, ha consistit en la realització de:` | Dates: DPSH PDF / Sondeig PDF | Template amb placeholder buit | ⚠️ | Dates "1 i 6 d'octubre de 2025" no extretes. Generat amb data buida |
| 084 | `2 assaigs de penetració dinàmica tipus DPSH (veure annex "Registre assaigs mecànics").` | Comptatge: DPSH.xls (nombre de fulls) | `report_data.py` → `num_dpsh` (comptar sheets Excel) | ✅ | — |
| 085 | `1 sondeig a rotació amb bateria continua (veure annex "Registre assaigs mecànics").` | CONDICIONAL: si `has_sondeig=true` | `report_generator.py` → secció condicional sondeig | ⚠️ | "sondeig a rotació amb bateria continua" → "assaig SPT amb recuperació de mostra" — Text diferent, descriu SPT en lloc de sondeig |
| 086 | `1 assaig SPT amb recuperació de mostra (veure annex "Registre assaigs mecànics").` | CONDICIONAL: si `has_spt=true` | `report_generator.py` → secció condicional SPT | ✅ | — |
| 087 | `Observacions de camp realitzades pel tècnic de l'empresa desplaçat a l'obra.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 088 | `Reportatge fotogràfic (veure annex "Fotografies").` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 089 | `Els assaigs in situ han estat realitzats per TPS PROSPECCIÓ DEL SUBSÒL SL, laboratori d'assaigs per a la edificació i l'obra civil acreditat...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |

#### 2.3 Justificació CTE (PARAs 090-091)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 090 | `2.3. JUSTIFICACIÓ DE COMPLIMENT DE CTE` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 091 | `A partir de la campanya realitzada i la classificació de l'obra que s'obté segons l'apartat 1.2 del present estudi, es valida la campanya de camp realitzada...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |

#### 2.4 Assaigs in situ (PARAs 092-114)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 092 | `2.4. DESCRIPCIÓ DELS ASSAIGS IN SITU` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 093 | `2.4.1. Assaigs de penetració tipus "DPSH"` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 094 | `L'assaig consisteix a clavar en el terreny una barnilla de secció circular mitjançant la caiguda d'una massa de 63.5 Kg...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 095 | `En el cas que el nombre de cops necessaris per travessar els 20 cm, sigui superior a 100...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 096 | `Característiques de l'assaig:` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 097 | `Alçada de caiguda del Pes: 75 cm` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 098 | `Diàmetre de la punta de penetració:51 mm` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 099 | `Interval de penetració: 20 cm` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 100 | `Pes : 63.5 Kg` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 101 | `Fotografia 3. Vista de la màquina utilitzada en un dels assaigs de penetració dinàmica DPSH.` | FOTOGRAFIES/DPSH/ | Template amb numeració dinàmica fotos | ✅ | — |
| 102 | `2.4.2. Sondeig a rotació amb bateria continua` | CONDICIONAL: si `has_sondeig=true` | `report_generator.py` → `has_sondeig` toggle | ❌ | Subsecció sencera no trobada al generat. La secció condicional al codi existeix però no genera el títol ni text descriptiu |
| 103 | `Els sondejos a rotació amb bateria contínua són perforacions de petit diàmetre que permeten reconèixer la naturalesa...` | Text fix condicional (verd si sondeig) | No implementat | ❌ | Text descriptiu del sondeig no inclòs al template |
| 104 | `Els sondejos amb bateria contínua consisteixen en la perforació mitjançant un mecanisme de rotació equipat d'una bateria...` | Text fix condicional | No implementat | ❌ | Idem |
| 105 | `Aquest tipus d'assaigs s'utilitzen en roques o en sòls durs, i els diàmetres habituals són entre 66 i 143mm...` | Text fix condicional | No implementat | ❌ | Idem |
| 106 | `Fotografia 4. Vista de la màquina utilitzada per a la realització del sondeig a rotació.` | FOTOGRAFIES/SONDEIG/ | No implementat | ❌ | Generat: "Fotografia 2. Vista de la màquina DPSH" — Foto sondeig no inclosa |
| 107 | `2.4.3. Assaig tipus S.P.T. ("Standard Penetration Test")` | CONDICIONAL: si `has_spt=true` | `report_generator.py` → secció SPT condicional | ✅ | Numeració adapta si no hi ha sondeig |
| 108-110 | Text descriptiu SPT + Figura cullera | Text fix condicional | Template Jinja estàtic (dins bloc SPT) | ✅ | — |
| 111 | `2.4.3. Resum dels assaigs in-situ realitzats` | Títol (fix) — numeració dinàmica | Template amb numeració `subsection_resum` | ✅ | — |
| 112 | `Els assaigs de camp realitzats es sintetitzen en el quadre que s'exposa a continuació:` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 113 | `Taula 3, 4 i 5. Resum dels assaigs in situ realitzat.` | Taules DPSH + Sondeig + SPT | Template amb numeració dinàmica taules | ⚠️ | "Taula 3, 4 i 5" → "Taula 3 i 4" (sense taula sondeig) |
| 114 | `Les cotes d'inici dels assaigs s'han referit a la superfície actual del solar segons les coordenades...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |

#### 2.5 Assaigs de laboratori (PARAs 115-118)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 115 | `2.5. ASSAIGS DE LABORATORI` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 116 | `Els assaigs de laboratori han estat realitzats per TPS PROSPECCIÓ DEL SUBSÒL SL (SOIL ASSAIG)...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 117 | `Donada la naturalesa dels materials s'han sol·licitat els següents assaigs:` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 118 | `Taula 6. Resum dels assaigs de laboratori realitzats.` | comanda laboratori.xls | Template amb dades laboratori | ✅ | — |

**Resum Secció 2:** 56 paràgrafs — ✅ 40 | ⚠️ 8 | ❌ 8

---

## SECCIÓ 3: DESCRIPCIÓ GEOLÒGICA I GEOTÈCNICA
### PARAs 119-200

#### 3.0 Títol (PARA 119)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 119 | `3. DESCRIPCIÓ GEOLÒGICA I GEOTÈCNICA` | Títol secció (fix) | Template Jinja estàtic | ✅ | — |

#### 3.1 Marc geològic (PARAs 120-127)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 120 | `3.1. MARC GEOLÒGIC` | Títol subsecció (fix) | Template Jinja estàtic | ✅ | — |
| 121 | `La zona que avarca aquest estudi es troba situada dins la Depressió de l'Ebre, en el seu extrem oriental, que rep el nom de Depressió Central Catalana...` | Plantilla zona: `depressio_ebre` (servidor G3DT) | `section3_geologia.py` → `_generate_marc_geologic()` → plantilles regionals a `REGIONAL_TEMPLATES` | ❌ | Text complet 0% match. El codi té plantilles per `depressio_ebre` i `valles_penedes` però el text generat no coincideix amb l'original. Les plantilles al codi són genèriques, les originals són detallades |
| 122 | `La conca de l'Ebre està relacionada amb l'evolució de l'orogen pirinenc...` | Plantilla zona | `section3_geologia.py` → `REGIONAL_TEMPLATES["depressio_ebre"]` | ❌ | Paràgraf geològic detallat no inclòs a la plantilla del codi |
| 123 | `Durant l'Eocè, la conca de l'Ebre estava connectada amb l'oceà Atlàntic per l'oest...` | Plantilla zona | Idem | ❌ | Idem — text geològic històric detallat no implementat |
| 124 | `A partir de finals de l'Eocè i durant tot l'Oligocè, la conca de l'Ebre actua com a conca endorreica...` | Plantilla zona | Idem | ❌ | Idem |
| 125 | `Des de finals de L'Oligocè fins a l'actualitat la depressió de l'Ebre ha deixat d'actuar com a conca sedimentària...` | Plantilla zona | Idem | ❌ | Idem |
| 126 | `En concret, i segons l'ICGC, afloren els materials de la unitat Qvpu, corresponents a graves en matriu lutítica i llantions sorrencs del Plistocè.` | ICGC WMS API (unitat geològica) | `icgc_geology.py` → `query_geology_wms()` → `GeologicalUnit.format_for_report()` | ❌ | Paràgraf d'unitat ICGC no generat. El codi obté la unitat via WMS però no la formata al text de 3.1 |
| 127 | `Figura 5. Mapa geològic a escala 1:50.000 de la zona en estudi (Font: ICGC).` | ICGC mapa geològic | Template amb numeració dinàmica figures | ⚠️ | "Figura 5" → "Figura 4" (numeració canvia sense Figures 1-2 arquitecte); "ICGC" → "ICGC, modificat" |

#### 3.2 Caracterització materials (PARAs 128-139)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 128 | `3.2. CARACTERITZACIÓ DELS MATERIALS` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 129 | `A partir dels assaigs in situ realitzats, s'ha establert un sòl nivell de materials des del punt de vista geotècnic...` | Comptatge nivells (anàlisi DPSH) | `report_data.py` → `soil_levels` (llista de SoilLevel) | ✅ | — |
| 130 | `3.2.1. 1er Nivell` | Ordinal (1er, 2n, 3r) | Template amb loop nivells | ⚠️ | "3.2.1. 1er Nivell" → "3.2.1.Nivell 1" — Canvi format ordinal ("1er" → "1"), falta espai després de punt |
| 131 | `Descripció litològica` | Subtítol (fix per nivell) | Template Jinja estàtic dins loop | ✅ | — |
| 132 | `El 1er nivell està format per graves en matriu sorrenca carbonatades, de coloracions clars. Destacar que existeix un primer tram superficial de sòls vegetals...` | Plantilla zona + observació camp | `section3_geologia.py` → `_generate_materials()` → plantilla regional materials | ⚠️ | 51% match. "graves en matriu sorrenca carbonatades" → "graves i sorres". "coloracions clars" → "marró clar". Text genèric vs. específic de camp |
| 133 | `Fotografia 5. Detall dels materials recuperats en el sondeig a rotació amb bateria continua.` | FOTOGRAFIES/SONDEIG/ | Template amb numeració fotos | ⚠️ | "Fotografia 5" → "Fotografia 3"; "recuperats en el sondeig" → "del primer nivell" |
| 134 | `Aquests materials han estat caracteritzats a partir de la interpretació de les dades dels assaigs de camp i de laboratori:` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 135 | `Aquest nivell s'ha identificat com a materials plistocens, unitat Qvpu segons l'ICGC.` | ICGC WMS (unitat geològica) | `icgc_geology.py` → unitat geològica | ❌ | No trobat al generat. La identificació ICGC no s'inclou a la descripció del nivell |
| 136 | `Localització` | Subtítol (fix per nivell) | Template Jinja dins loop | ✅ | — |
| 137 | `A partir dels assaigs realitzats, aquest nivell es detecta superficialment i fins a la cota de finalització de tots els assaigs, amb potencies estudiades de com a mínim 2.45 metres...` | DPSH.xls (profunditats) | `report_data.py` → `SoilLevel.depth_range` | ❌ | Paràgraf de localització/potència no generat. Les dades existeixen (depths al DPSH) però el text no es genera |
| 138 | `Resistència` | Subtítol (fix per nivell) | Template Jinja dins loop | ✅ | — |
| 139 | `Des del punt de vista geomecànic es tracta d'uns materials de caràcter granular, amb una densitat i una capacitat portant elevada...` | DPSH N₂₀ interpretació | `section3_geologia.py` → `_describe_resistance()` | ⚠️ | 69% match. "granular" → "generalment granulars"; "elevada" → "mitja"; N₂₀ min "25" → "48". Classificació resistència diferent |

#### 3.3 Hidrologia i Hidrogeologia (PARAs 140-148)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 140 | `3.3. HIDROLOGIA I HIDROGEOLOGIA` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 141 | `3.3.1. Hidrogeologia superficial` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 142 | `Degut a que es tracta d'un solar antropitzat, no s'han detectat marques i/o indicis de processos d'erosió...` | Observació camp (urbà/rural) | `section3_geologia.py` → `_generate_hydrology()` → condicional urbà/rural | ✅ | Match 95%. Diferència menor: "Degut a que es" → "Es" |
| 143 | `Tampoc es detecta cap curs d'aigua superficial que pugui afectar a la zona en estudi.` | Observació camp | `section3_geologia.py` → condicional presència aigua | ⚠️ | 61% match. "Tampoc es detecta cap curs d'aigua superficial" → "Per altra banda, no s'ha localitzat cap curs d'aigua i/o torrent". Equivalent semàntic, diferent redacció |
| 144 | `3.3.2. Hidrogeologia subterrània i geotèrmia` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 145 | `En data de la realització dels treballs de camp, i fins la cota estudiada, no es va detectar presència de nivell freàtic.` | DPSH.xls (col F: N.F.) | `report_data.py` → `water_level_detected` | ✅ | — |
| 146 | `3.3.3. Permeabilitat dels materials` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 147 | `A continuació s'exposen els valors del coeficient de permeabilitat (K) associats als materials al subsòl del solar:` | Text fix (verd) | Template Jinja estàtic | ✅ | Diferència mínima: +`detectats` |
| 148 | `Taula 7. Resum del coeficient de permeabilitat dels materials del subsòl.` | Taula calculada per nivell | Template amb taula permeabilitat | ✅ | — |

#### 3.4 Agressivitat (PARAs 149-154)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 149 | `3.4. AGRESSIVITAT DEL MEDI` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 150 | `D'una mostra dels materials del subsòl, on es preveu armar la fonamentació, s'ha realitzat els pertinents assaigs...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 151 | `Els resultats obtinguts s'exposen en la següent taula:` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 152 | `Taula 8. Valors obtinguts dels assaigs de laboratori.` | LAB-SIG.pdf (sulfats, EHE-08) | `section3_geologia.py` → `_generate_aggressivity()` | ✅ | — |
| 153 | `(1) Segons el Real decreto 470/2021...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 154 | `(*) Per a classificar el grau d'agressivitat dels materials front al formigó segons la taula de classificació...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |

#### 3.5 Excavabilitat (PARAs 155-157)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 155 | `3.5. EXCAVABILITAT` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 156 | `Segons el projecte executiu es preveu la construcció d'una estructura en planta baixa, i per tant, no es preveu la realització de grans excavacions...` | Text fix (verd) + dades edifici | `section3_geologia.py` → `_generate_excavability()` | ✅ | — |
| 157 | `Els materials del primer nivell en els primers 1-1,5 metres no presentaran problemes des del punt de vista de la seva ripabilitat, podent-se realitzar les excavacions amb maquinària convencional. En canvi...` | Observació camp + N₂₀ | No implementat completament | ❌ | Paràgraf detallat d'excavabilitat per estrats no generat. El codi genera text genèric basat en N₂₀ però no el text específic de profunditats |

#### 3.6 Sísmica (PARAs 158-180)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 158 | `3.6. ACCELERACIÓ SISMICA DE REFERÈNCIA` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 159 | `A efectes d'aplicació de la Norma de Construcción Sismoresistente NCSE-02...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 160 | `L'acceleració sísmica s'obté del Mapa de Perillositat Sísmica...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 161 | `A la zona d'estudi, en el municipi de Bell-lloc d'Urgell, s'estableix una acceleració sísmica bàsica de:` | Municipi: carpeta. ab: lookup municipal_data.json | `section3_geologia.py` → `_generate_seismic()` → `municipal_data.get_seismic_ab_with_status()` | ❌ | "Bell-lloc d'Urgell" → "Carrer Antoni Bellet / Carrer Mestre Ramon Ortiz, Bell-Lloc d'Urgell (Bell Lloc)". Usa `street_address` en lloc de `municipality` |
| 162 | `AB  < 0,04 g  (essent g el valor de la gravetat)` | Valor ab: NCSE-02 taula | `municipal_data.py` → `get_seismic_ab_with_status()` | ❌ | "< 0,04" → "=0,08". Valor incorrecte. Bell-Lloc hauria de ser <0,04g però el lookup retorna 0,08 |
| 163 | `Cal indicar que l'aplicació de la norma resistent no és obligatòria en el cas d'edificis d'importància normal quan l'acceleració sísmica de càlcul sigui inferior a 0,08 g.` | CONDICIONAL: si ab < 0,08 | `section3_geologia.py` → condicional `ab < 0.04` | ❌ | Paràgraf no generat. Com que ab=0,08 (incorrecte), la condició `ab < 0.04` no es compleix i el paràgraf d'exempció no s'inclou |
| 164-180 | Fórmules i taula NCSE-02 (AC, S, C, ρ, coeficients per nivell) | Text fix (verd) + Taula 9 calculada per nivell | `section3_geologia.py` → `_generate_seismic()` + Template Jinja | ✅ | — (17 paràgrafs tots 100%) |

#### 3.7 Radó (PARAs 181-200)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 181 | `3.7. EXPOSICIÓ AL GAS RADÓ` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 182-199 | Text normatiu radó DB HS-6 + zones + mesures | Text fix (verd) | Template Jinja estàtic (18 paràgrafs) | ✅ | — (tots 100%) |
| 200 | `La parcel·la concreta d'estudi es localitza al terme municipal de BELL-LLOC D'URGELL i, segons la taula existent a l'apèndix B del RD 732/2019, pertany a ZONA 1.` | Municipi: carpeta. Zona: municipal_data.json | `section3_geologia.py` → `_generate_radon()` + `municipal_data.get_radon_info_with_status()` + `csn_radon.get_radon_potential()` | ❌ | "BELL-LLOC D'URGELL" → "Carrer Antoni Bellet / Carrer Mestre Ramon Ortiz, Bell-Lloc d'Urgell". Mateixa errada municipi=adreça. Zona correcta (1) |

**Resum Secció 3:** 82 paràgrafs — ✅ 58 | ⚠️ 6 | ❌ 18

---

## SECCIÓ 4: CONCLUSIONS
### PARAs 201-227

#### 4.0 Introducció (PARAs 201-202)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 201 | `4. CONCLUSIONS` | Títol secció (fix) | Template Jinja estàtic | ✅ | — |
| 202 | `Les recomanacions es donen en funció dels resultats obtinguts de la campanya de camp realitzada, així com les característiques de l'estructura projectada.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |

#### 4.1 Geologia (PARAs 203-213)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 203 | `4.1. GEOLOGIA` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 204 | `Es detecta un sòl nivell de materials des del punt de vista geològic/geotècnic en el subsòl del solar.` | Comptatge nivells (Secció 3.2) | `report_data.py` → `soil_levels` count | ✅ | — |
| 205 | `El 1er nivell està format per graves en matriu sorrenca carbonatades, de coloracions clars. Destacar que existeix un primer tram superficial de sòls vegetals de fins a 30 cm de potència aproximadament.` | Plantilla zona + camp | `report_data.py` → `SoilLevel.description` | ❌ | 0% match. Descripció del nivell no generada a conclusions. Requereix la mateixa plantilla de zona que Secció 3.2 |
| 206 | `La distribució espaial dels materials al llarg de la parcel·la estudiada es recull en següent tall de correlació:` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 207 | `Figura 6. Detall del tall de correlació que s'adjunta als annexes.` | Figura dinàmica | Template amb numeració figures | ✅ | — |
| 208 | `Finalment, a partir de les litologies observades, s'ha associat al nivell descrit unes característiques geotècniques...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 209 | `Taula 10. Característiques geològiques i geotècnics dels materials del subsol.` | Calculat: Terzaghi + N₂₀ correlacions | `report_data.py` → `GeotechnicalParams` + `terzaghi_calculator.py` | ✅ | — |
| 210 | `Els paràmetres de cohesió i angle de fregament intern, s'han obtingut de les relacions que s'estableixen entre els resultats de penetració...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 211 | `(1)Densitat està donada en gr/cm3.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 212 | `(2 i 3)La cohesió està expressada en Kg/cm2...` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 213 | `(4)Mòdul de deformació, Kg/cm2` | Text fix (verd) | Template Jinja estàtic | ✅ | — |

#### 4.2 Hidrogeologia i Agressivitat (PARAs 214-217)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 214 | `4.2. HIDROGEOLOGIA I AGRESSIVITAT` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 215 | `Degut a que es tracta d'un solar antropitzat, no s'han detectat marques i/o indicis de processos d'erosió...` | Observació camp (urbà/rural) | `report_generator.py` → reutilitza text Secció 3.3 | ⚠️ | 77% match. "Degut a que es" → "Es"; "antropitzat" → "no antropitzat" (invertit!); falta frase cursos d'aigua. L'inversió "no antropitzat" és un error significatiu |
| 216 | `En data de la realització dels treballs de camp, i fins la cota estudiada, no es va detectar presència de nivell freàtic.` | DPSH.xls (N.F.) | `report_data.py` → `water_level_detected` | ✅ | — |
| 217 | `A partir dels resultats dels assaigs de laboratori realitzats, els materials del subsòl on es preveu armar la fonamentació, es presenten xxxx al formigó.` | LAB-SIG.pdf (sulfats) → classificació EHE-08 | `section3_geologia.py` → `aggressivity_class` | ✅ | "xxxx" → "no agressius". Original tenia placeholder; generat ompli correctament |

#### 4.3 Fonamentació (PARAs 218-223)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 218 | `4.3. FONAMENTACIÓ` | Títol (fix) | Template Jinja estàtic | ✅ | — |
| 219 | `Segons el projecte executiu es preveu la construcció d'una estructura en planta baixa, i per tant, no es preveu la realització de grans excavacions...` | Dades edifici | `report_data.py` → `building_type`, `num_floors` | ✅ | — |
| 220 | `Un cop realitzada l'excavació aflorarà superficialment els materials del primer nivell descrit. Donada les propietats geomecànica dels materials detectats es realitza una valoració per a la realització d'una fonamentació superficial.` | Anàlisi geotècnic | No implementat | ❌ | Paràgraf de valoració post-excavació no generat. Requereix text que connecta excavació amb fonamentació |
| 221 | `Per una fonamentació superficial mitjançant sabates, ja sigui aïllades com corregudes, o bé llosa, recolzada en els materials del primer nivell un cop sanejat el tram superficial...` | Tipus fonamentació + nivell recolzament | `report_data.py` → Terzaghi result | ⚠️ | 79% match. "superficial" eliminat; "ja sigui aïllades com corregudes" → simplificat; "recolzada" → "encastada entre 30-40 cm". Canvi de terminologia |
| 222 | `Qa= 3.0 Kg/cm2  amb un factor de seguretat inclòs de F=3` | Terzaghi calculator | `terzaghi_calculator.py` → `calculate()` → `qa_admissible` | ✅ | — |
| 223 | `Els assentaments màxims previstos per la càrrega recomanada anteriorment seran inferiors a 1.20 cm, immediats en el temps donat el comportament granular dels materials.` | Càlcul assentament | `report_data.py` → `settlement_max_cm` | ⚠️ | 97% match. "inferiors" → "iguals o inferiors"; "1.20" → "1.50". Valors assentament lleugerament diferents |

#### 4.4+ Seccions condicionals i tancament (PARAs 224-227)

| # | Contingut original | Indicació G3DT | Implementació actual | Estat | Motiu variació |
|---|-------------------|----------------|---------------------|-------|---------------|
| 224 | `G3 D T S.L. sol·licita que si es detectessin anomalies respecte les dades que s'exposen, durant l'execució de les obres, es contacti amb l'empresa per tal de consensuar una possible solució.` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 225 | `Informe geològic / geotècnic,` | Text fix (verd) | Template Jinja estàtic | ✅ | — |
| 226 | `Expedient Núm.: 4001612` | Nom carpeta → expedient | `project_extractor.py` → `expedient` | ✅ | — |
| 227 | `Els Omells de Na  Gaia, 27 d'octubre de 2025` | Lloc fix + data emissió | Template amb data actual | ⚠️ | "27 d'octubre de 2025" → "03 de February de 2026". Data del dia de generació (correcte). Mes en anglès (bug menor de locale) |

**Resum Secció 4:** 27 paràgrafs — ✅ 19 | ⚠️ 4 | ❌ 4

---

## RESUM GLOBAL PER ESTAT

| Secció | Total | ✅ Seguida | ⚠️ Modificada | ❌ No implementada |
|--------|-------|-----------|---------------|-------------------|
| TOC + Índex (PARAs 001-040) | 40 | 37 | 3 | 0 |
| **1. Presentació** | 22 | 17 | 2 | 3 |
| **2. Treballs de Camp** | 56 | 40 | 8 | 8 |
| **3. Geologia** | 82 | 58 | 6 | 18 |
| **4. Conclusions** | 27 | 19 | 4 | 4 |
| **TOTAL** | **227** | **171** | **23** | **33** |
| | | **75.3%** | **10.1%** | **14.5%** |

---

## CLASSIFICACIÓ D'ERRORS PER CAUSA

### 1. Bug: Municipi = Adreça (5 PARAs)
**PARAs afectats:** 49, 71, 77, 161, 200
**Causa:** El codi usa `street_address` (ex: "Carrer Antoni Bellet / Carrer Mestre Ramon Ortiz, Bell-Lloc d'Urgell") on hauria de dir només `municipality` (ex: "Bell-Lloc d'Urgell").
**Fix:** Revisar `report_generator.py` → `_build_template_context()` on `municipality` es mapeja.

### 2. Plantilles zona absents (11 PARAs)
**PARAs afectats:** 121-126, 132, 135, 137, 205
**Causa:** El text geològic regional detallat existeix en plantilles al servidor G3DT que no hem integrat. El codi `section3_geologia.py` té `REGIONAL_TEMPLATES` genèriques però no els textos complets.
**Fix:** Obtenir plantilles detallades del servidor G3DT per cada zona geològica.

### 3. Secció Sondeig no implementada (5 PARAs)
**PARAs afectats:** 102-106
**Causa:** Tot i que `has_sondeig` és un toggle al codi, el template Jinja no inclou el text descriptiu del sondeig (3 paràgrafs explicatius + foto).
**Fix:** Afegir text estàtic condicional al template per la subsecció 2.4.2.

### 4. Data treballs absent (2 PARAs)
**PARAs afectats:** 64, 83
**Causa:** La data dels treballs de camp no s'extreu del DPSH PDF ni de DADES PER ANAR A CAMP.xlsx.
**Fix:** Extreure data del header DPSH PDF o afegir camp a `user_data.json`.

### 5. Observacions camp manuals (3 PARAs)
**PARAs afectats:** 78, 157, 220
**Causa:** Paràgrafs que requereixen observació visual del tècnic al camp. No automatitzables directament.
**Fix:** Afegir camps d'entrada manual a `user_data.json` (descripció solar, accessibilitat, estat superficial).

### 6. Valor sísmic incorrecte (3 PARAs)
**PARAs afectats:** 161, 162, 163
**Causa:** `municipal_data.py` retorna ab=0,08 per Bell-Lloc quan hauria de ser <0,04. Possible error al JSON de dades o matching parcial del nom.
**Fix:** Verificar entrada "Bell-Lloc d'Urgell" a `municipal_data.json` (947 municipis).

### 7. Errors menors de format/redacció (4 PARAs)
**PARAs afectats:** 43, 130, 143, 227
**Causa:** Diferències de format ("S.L." vs "SL"), ordinals ("1er" vs "1"), redaccions alternatives equivalents, locale data en anglès.
**Fix:** Ajustar format al template Jinja; corregir locale per dates en català.
