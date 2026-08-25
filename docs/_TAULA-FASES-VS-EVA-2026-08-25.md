# Taula de treball — què queda per fer, què millora i quin tipus de dada toca (vista «què diria l'Eva»)

**Orientativa, no font de veritat** (Josep, 2026-08-25 nit). Serveix per prioritzar; les xifres són les mesurades on hi ha font, i les valoracions de l'Eva són **inferències** marcades com a tals.
Fonts: `DIAGNOSTIC-PROD-2026-08-23.md` §3 (341 variables, 59 % d'encert a prod; 118 MISMATCH per causa), `DISSENY-ANNEX-TRES-BOTONS…` §10 (Fases 9-17), `LEDGER.md`, memòries `eva_prod_logs_scoreboard_2026-08` (el que l'Eva viu: 6-10 min d'espera, 4+4 crashes en 14 dies), `feedback_no_pull_eva_success_criterion`.

## Resum compacte (tal com es va presentar al Josep el 2026-08-25, 23:40 — «em diu on estem»)

### Tipus de dada de l'informe (per llegir la taula)

| Tipus | Què hi ha | Avui a prod (diagnòstic 23-08, 341 vars, 59 %) |
|---|---|---|
| **A** identitat i camp | expedient, client, adreça, municipi, arquitecte, tipus edifici, plantes, sup. parcel·la, data camp, cota ref., nivells, UTM, RC, lab, CTE | client «G3» 3/8, parcel·la equivocada 4/8, data de camp 7/8 malament |
| **T** taules de lectura | DPSH, sondeig, SPT/MA, nivells (de/a, litologia) | no mesurat; cadena DPSH trencada a casa seva (92 % FAIL) |
| **C** càlculs | γ, Nb, φ, c, E, Qa, assentament, K30, cte_sol, files geotècnica/perm./sísmica | 41/118 MISMATCH (E 6/8, Qa 6/8, assent. 7/8) — criteri ≠ Eva |
| **N** narrativa | site_description, adjacents, soterrani, empentes, conclusions | 7/8 diferent; adjacents en castellà (Rubí) |
| **B** biblioteca | textos estàndard per material/zona (radó, sísmica, sulfats, geomech) | bé si els inputs ho són (6/8) |
| **I** imatges | cadastre, aèria, A.01, tall, geològica, fotos | 2-4 placeholders quan falla parcel·la/UTM |
| **P** peus i numeració | fig/table/section nums | automàtics, cap queixa |

### Fases i blocs pendents → què milloren → què notaria l'Eva

| Bloc | Millora | Tipus | Si demà ho tingués (inferència) | Urgència |
|---|---|---|---|---|
| **0 Desplegament** (Fase 17 Windows + pla/model) | tot: sense això **res** li arriba | tots | Res. Avui viu la via B: petades + 6-10 min | **Condicionant** |
| **0b Hold-out amb carpetes noves seves** | confiança real | A, T | El 0 erroni és sobre 8 projectes que el skill anomena pel nom | **Molt alta** |
| **1 Nivell A** (fet: Fases 0-12) | encerts A: 59 % → 0 erroni de fons, ~80 % OK + candidats amb cita | A, T (+I, N per arrossegament) | Client/adreça/parcel·la/data correctes; el dubtós surt com a tria, no com a valor fals | fet |
| **1b Fase 8b** taules UI → generador | que T **arribi al .docx** | T (i C) | Sense 8b, llegim bé però l'informe surt amb les taules velles | **Alta** (petita) |
| **1c Fase 13** auto_result + Cadastre/ICGC al consolidador | reobertura instant; parcel·la validada | A, I | Ortofoto/cadastre de la seva parcel·la, cap imatge buida | **Alta** |
| **1d** regla `de` nivell 1 + forat capa vegetal | T | T, B | nivell 1 com ella el posa | mitjana (depèn de pregunta 3) |
| **2 Fase 14** tres botons | espera → segon pla | UX | «Ho preparo i faig una altra cosa» (avui mira una barra 6-16 min) | **Alta** — fa acceptables els 20-26 min |
| **2b Fase 15** notificacions | tanca l'espera | UX | «M'arriba un correu i obro» | **Alta** amb 14 |
| **2c Fases 11 + 16** delta-sync, E2E | re-lectures parcials ≤ 10 min; mesures | UX | només rellegeix el que ha afegit | mitjana |
| **3 Càlculs** (correu v4 → ajustar codi) | 41 MISMATCH, el bloc més gran | C, B | Si els números no són els seus, refà la secció i no es fia de la resta | **alta en valor, bloquejada per les seves respostes** |
| **4 Narrativa** (adjacents/Street View, site_description, soterrani) | N | N | No sabem quant reescriu; castellà/«G3» ja tancats per la via A | mitjana; mesurar primer |
| **5 Biblioteca i peus** | derivades | B, P | només si nivell/terreny és erroni | baixa (cau sola) |
| **6 Imatges** (fotos, A.01, Street View) | cap placeholder | I | requadres buits = «no serveix» a la vista | alta la part de 1c; mitjana la resta |
| **7 Expedients amb 2 informes** (Tulipa) | robustesa | tots | si li passa sovint, no li serveix en aquests | desconeguda (pregunta 5) |

### Lectura per prioritzar

1. **Sense 0 + 0b l'Eva no nota res**: el seu judici avui es forma sobre la via B. Tot el que segueix compta només si arriba al seu ordinador i aguanta un projecte nou seu.
2. Ordre de valor percebut inferit: **(a)** dades A i taules correctes que *arribin a l'informe* sense imatges buides (1 + 8b + 13) → **(b)** espera invisible (14 + 15) → **(c)** càlculs amb el seu criteri (3) → (d) narrativa → (e) biblioteca/peus.
3. Els blocs 3 i 7 estan bloquejats per **respostes seves**, no per codi: enviar `PREGUNTES-EVA-PENDENTS.md` (o el correu v4, preparat des de l'abril i no consta enviat) és la tasca més barata amb més palanca.
4. Tot el que diu «què notaria» és inferència; el que sabem del cert és el que diuen els seus logs (espera, petades) i la frase «no va bé» sense detall.

## Proposta de priorització (2026-08-25, 23:50) — data de reunió desconeguda, sense respostes de l'Eva

Principi: **cada tall del calendari ha de deixar un estat coherent i demostrable** (al portàtil del Josep, amb Castellar/Bell-lloc, i amb carpetes noves si arriben), i tot el que depèn de l'Eva (respostes, ordinador) es prepara però no bloqueja. Ritme de referència: Fases 0-8 en un dia, 9-12 en un dia (24-25 d'agost).

| Tram | Què | Per què en aquest ordre | Tall: «si l'Eva diu…» |
|---|---|---|---|
| **Avui/demà, 0 codi** | Enviar-li per correu les 6 preguntes (`PREGUNTES-EVA-PENDENTS.md`) + demanar 2-3 carpetes recents de projectes seus. Decisió del Josep: pla/model (Fable @xhigh o Opus 4.8 @high) — condiciona la instal·lació. | Palanca màxima per cost zero; les respostes arriben quan torni; les carpetes permeten el hold-out (0b) abans de la reunió. | **demà**: demo al portàtil amb el que hi ha (lectura + consolidació Python, wizard headless E2E amb la pestanya oberta 20-26 min); no s'instal·la res. |
| **Tram 1 (≈1-2 dies)** | **8b** (seleccions de taula → generador) → **13** (`auto_result` a disc + Cadastre/ICGC al consolidador + residus Groq) → **forat capa vegetal** a `consolidate.py` (sense la regla del Pas 3b, que espera la pregunta 3) → **14a** (botons *Preparar*/*Obrir* + taula d'estat + `attach`; *Actualitzar* espera l'11) → **15** (toast + correu «expedient llest»; SMTP configurable, telemetria sanejada). | Tanca la cadena **lectura → informe complet** (A + T + figures de la parcel·la correcta) i converteix l'espera en segon pla. Són les dues coses que, segons la taula, l'Eva notaria primer. 14a abans de l'11 perquè els dos primers botons no necessiten delta-sync. | **aquesta setmana**: demo «premo Preparar, tanco, m'arriba un correu, obro i l'informe surt sencer amb les meves taules». |
| **Tram 2 (≈1-2 dies)** | **11** (delta-sync) + **14b** (*Actualitzar*) → **16** (E2E dels tres botons: xifres reals per a la taula abans/després que vol el Josep) → **17 preparat en sec**: `claude` CLI Windows natiu + login provat al Windows del Josep (`/mnt/c`), script/checklist d'instal·lació, política de neteja `_preext/` (72 MB/projecte), `--strict-mcp-config`. | La reunió amb l'Eva **és** el dia d'instal·lació (Fase 17 és presencial): tot el que es pugui provar abans al Windows del Josep treu risc d'aquell dia. | **la setmana que ve**: instal·lació el dia de la reunió amb checklist provat; taula abans/després amb mesures; hold-out fet si han arribat carpetes. |
| **Tram 3 (quan respongui / després)** | **3 càlculs** (segons respostes v4 → `terzaghi_calculator`/`report_data`, amb comparador contra els 6 informes signats) → **1d** regla `de` nivell 1 → **7** multi-informe si diu que és freqüent → **4** narrativa (mesurar primer què reescriu; Street View per adjacents) → **6** selecció de fotos → **5** cau sol. | Tot bloquejat per ella o de valor incert fins que la vegem treballar amb la via A. | després de la reunió, amb les seves respostes i el que hàgim vist. |

Riscos d'aquest ordre: (1) si la reunió és **demà**, la demo mostra 20-26 min d'espera visible — dir-ho com a decisió («ho fem en segon pla, ve al tram 1»), no amagar-ho; (2) 13 toca `wizard_service` (via B) — envoltant, no reescriptura, i suite completa abans de cada commit; (3) 17 en sec al Windows del Josep no és l'ordinador de l'Eva (Python 3.12 natiu, `C:\g3dt-ia\app`): la checklist ha de preveure diferències.

---
## Detall (versió llarga, mateixes conclusions)
## Tipus de dada de l'informe (114 variables de plantilla + files de taules; agrupades)
| Tipus | Què hi ha | Avui a prod (diagnòstic 23-08) |
|---|---|---|
| **A · identitat i camp** | expedient, client, adreça, municipi, arquitecte, tipus d'edifici, plantes, superfície parcel·la, data de camp, cota de referència, nivells, nº DPSH, UTM, RC, lab (empresa, mostra, fondària), CTE | client = «G3» 3/8, parcel·la equivocada 4/8, data de camp mai la de camp 7/8, tipus d'edifici 7/8, municipi 5/8 |
| **T · taules de lectura** | DPSH (cota, fondària, rebuig, N.F.), sondeig, SPT/MA (N30, litologia), nivells (de/a, litologia) | no mesurat a prod (§3.4); cadena DPSH trencada a casa de l'Eva (92 % FAIL) |
| **C · càlculs (grup B)** | γ, Nb, φ, c, E, Qa, assentament, K30, cte_sol, `table_dpsh_range`, files geotècnica/permeabilitat/sísmica, qualificació de sulfats | 41/118 MISMATCH: E 6/8, Qa 6/8, assentament 7/8, K30 3/3, φ 3/8 — criteri ≠ Eva |
| **N · narrativa** | `site_description`, `location_sentence`, 4 adjacents, `building_structure_desc` (soterrani), empentes, estabilitat, conclusions, `materials_intro`, text de fotos | `site_description` 7/8, `building_structure_desc` 7/8, adjacents en **castellà** (Rubí), redacció ≠ Eva (similitud < 0,6) |
| **B · biblioteca** | textos estàndard per material/zona: `materials_text`, `geomech_text`, `terrain_type`, radó, sísmica (`seismic_ab_text`), CSN, classificació de sulfats, descripcions de lab | correctes si els inputs ho són: radó 6/8, sísmica 6/8; litologia re-redactada per l'Eva = sempre candidats |
| **I · imatges** | fig. cadastre (retall plànol situació), aèria (ICGC + parcel·la), plànol A.01, tall, geològica, cullera SPT; fotos DPSH/materials/emplaçament/sondeig | 2-4 **placeholders** quan la parcel·la/UTM falla o es genera sense desar; selecció de fotos per tipus |
| **P · peus i numeració** | `fig_*_num`, `photo_*_num`, `section_*_num`, `table_*_num`, `data_signatura_text` | automàtics; cap problema reportat |

## Fases i blocs pendents
| Bloc / fase | Què és | Què millora | Tipus | Si **demà** ho tingués, què notaria l'Eva (inferència) | Urgència (proposta) |
|---|---|---|---|---|---|
| **0. Desplegament** — Fase 17 (Windows: `claude` CLI natiu + login, servidor viu, `--strict-mcp-config`) + decisió de pla/model (Fable @xhigh o Opus 4.8 @high) + política `_preext/` | Portar la via A al seu ordinador | Tot: sense això **cap** fase arriba a l'Eva | tots | Res — avui viu amb la via B (`1f1d7fd`): cadena DPSH trencada, crash Unicode als prefills, 6-10 min d'espera. Els fixes F1-F4e són a `review/prod-audit`, no fusionats (i no proposem pull) | **Condicionant.** Sense això la resta és invisible |
| **0b. Hold-out amb carpetes NOVES de l'Eva** (`\\192.168.1.11\geologia\`, 19 projectes 2026) | Provar la via A fora del corpus 2025 | Confiança real en el 0 erroni de fons | A, T | El que ella jutja és el seu projecte d'ara, no Castellar. Avui: 0 erroni de fons **només** sobre 8 projectes que el skill anomena | **Molt alta** abans de prometre res |
| **1. Nivell A ja fet a la branca** (Fases 0-12: lectura headless + consolidació Python, 0,04 s) | Lectura per document amb candidats + font + cita | Encerts A: prod 59 % → via A 0 erroni-amb-confiança, ~80 % OK + candidats amb el bo dins | A, T, i per arrossegament I (parcel·la correcta → figures) i N (idioma, client) | Client ja no és «G3», adreça/parcel·la/data de camp correctes, cota relativa respectada, taules iguals als seus annexos; el que no és segur li surt com a tria amb la cita, no com a valor fals | Fet; valor només quan 0 i 0b |
| **1b. Fase 8b** — seleccions de taula de la UI → generador | Que les taules llegides (T) viatgin al `.docx` | Sense ella, T es llegeix bé però **no arriba a l'informe** | T (i C, que en depèn) | La part més visible del seu treball de camp; sense 8b, l'informe surt amb les taules de la via B | **Alta** (petita, tanca la cadena A→informe) |
| **1c. Fase 13** — `auto_result` a disc + Cadastre/ICGC al consolidador (forat 1) + residus Groq | Reobertura sense xarxa; superfície/UTM/RC amb la parcel·la validada | Latència 2a obertura (instant), A (parcel·la 4/8 equivocada avui), I (figures buides quan la parcel·la falla) | A, I | Ortofoto i cadastre de la **seva** parcel·la; cap placeholder d'imatge per UTM absent | **Alta** (tanca Q2/Q9 del diagnòstic) |
| **1d. Regla Pas 3b «de del nivell 1» + forat capa vegetal a `consolidate.py`** (+ pregunta 3 a l'Eva) | Taula de nivells | T (files de nivells) | T, B (textos per nivell) | Nivell 1 amb la fondària que ella posa; la capa vegetal com ella la tracta | Mitjana (petita; depèn de la resposta) |
| **2. Fase 14** — UI tres botons + taula d'estat (Preparar / Obrir / Actualitzar; `attach` en reobrir) | L'espera deixa de ser una espera | UX + latència percebuda: prem *Preparar*, tanca la pestanya, torna quan és llest (lectura 20-26 min en segon pla) | cap dada; experiència | Avui: mira una barra 6-10 min (16 min pitjor) i li peta. Demà: «ho preparo i faig una altra cosa» | **Alta** (és el que fa acceptables els 20-26 min) |
| **2b. Fase 15** — notificacions (toast + correu «expedient llest»; telemetria sanejada a Eficients) | Tancar el cicle de l'espera | UX; per a nosaltres, saber si va bé sense demanar-li logs | experiència | «M'arriba un correu i obro» — avui no sap quan pot tornar | **Alta** amb la 14 (petita) |
| **2c. Fase 11** — delta-sync xarxa→workspace + Fase 16 E2E dels tres botons | Botó 3b (2 documents canviats) ≤ 10 min | Latència en re-lectures parcials; mesures reals per a la seva taula abans/després | experiència | Quan afegeix l'annex o el GTL després, només es rellegeix això | Mitjana (11 és fonament tècnic de 14; 16 és mesura) |
| **3. Càlculs (grup B)** — correu v4 (Nb 0,83; n carbonatades; Qa topall; φ 28°) → ajustar `terzaghi_calculator`/`report_data` | Que E, Qa, assentament, K30, φ surtin amb el **seu** criteri | Encerts C: 41 MISMATCH (el bloc més gran del diagnòstic) | C, B (textos que depenen del nivell/tipus de terreny), files derivades | Si els números no són els seus, refà la secció geotècnica sencera i no es fia de la resta. Avui: γ/Nb/Terzaghi/K30/Schmertmann implementats segons `METODOLOGIA-EVA`, però desvien | **Alta en valor, bloquejada per les seves respostes** (enviar el correu v4 costa 0) |
| **4. Narrativa** — adjacents (Cadastre → prosa; Street View pendent), `site_description`, soterrani (`building_structure_desc`), idioma, conclusions | Text que s'assembli al seu | Encerts N (7/8 MISMATCH però part és redacció lliure) | N | No sabem quant reescriu ni si li molesta (§3.4: caldria judici humà / LLM-jutge). Segur que **castellà** i «G3» li molesten — ja tancat per la via A (fonts) | Mitjana; primer mesurar amb ella què reescriu |
| **5. Biblioteca i peus** — textos estàndard per material/zona, numeració, `data_signatura` | Segueixen les dades A/T/C | Cap acció pròpia: milloren quan A/T/C milloren | B, P | Els nota només si el nivell/tipus de terreny és equivocat (llavors el text estàndard també) | Baixa (derivada) |
| **6. Imatges** — selecció de fotos per tipus (memòria fotos), plànol A.01 sense punts, cullera SPT; Street View/Google Earth (memòria) | Cap placeholder; fotos correctes | I | I, P | Un informe amb requadres buits «no serveix» a la vista, encara que els números siguin bons | Alta la part que depèn de 1c (parcel·la/UTM); mitjana la selecció de fotos |
| **7. Estructura** — expedients amb 2 informes (Tulipa), pregunta 5 | 1 projecte = 1 informe avui | Robustesa en casos que no sabem quant freqüents són | tots | Si li passa sovint, el wizard no li serveix en aquests | Desconeguda (preguntar) |
| **8. Objectiu 341 variables** — registre d'abast per variable (A / T / C / N / B / I / P) i mesura per tipus | Saber què està cobert i què no | Evita «més o menys» | tots | — | Instrument per a nosaltres; barat |

## Lectura ràpida (inferència, per prioritzar si cal triar)
1. **Sense 0 + 0b, l'Eva no nota res** i el seu judici es forma sobre la via B que té avui (petades + espera). Tot el que segueix és «demà» només si arriba al seu ordinador i funciona amb els seus projectes nous.
2. El que més li canviaria el dia, per ordre: (a) **dades A i taules correctes que arribin a l'informe** (1 + 8b + 13: identitat, parcel·la, camp, cap imatge buida); (b) **l'espera invisible** (14 + 15; 11 al darrere); (c) **càlculs amb el seu criteri** (3 — depèn del correu v4); (d) narrativa; (e) biblioteca/peus (cauen sols).
3. Els blocs 3 i 7 estan **bloquejats per respostes de l'Eva** (`PREGUNTES-EVA-PENDENTS.md`), no per codi: enviar les preguntes és la tasca més barata amb més palanca.
4. Risc que no surt a cap fase: el 0 erroni de fons és sobre el corpus 2025 que el skill anomena pel nom; el primer projecte nou de l'Eva és el test real.
