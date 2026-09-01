# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-08-31 (nit) — `PLA-PENDENTS-0B-0C-0D-2026-08-26.md` TANCAT: sis fixos (comparador v3, `value_key`,
or Castellar v2, residus Groq a l'origen, Cadastre multi-portal ON per defecte, Bell-lloc via mínima) implementats,
mesurats i commitejats (`3694694`→`2486a53`). Suite 1640 passed / 32 failed. Detall: `docs/DECISION-LOG.md`
entrada 2026-08-31. Pendents reals: preguntes 3+8+9+10 a l'Eva (`docs/PREGUNTES-EVA-PENDENTS.md`), Fase 16 (E2E
remesurat amb Cadastre ON).

Last updated 2026-08-26 (TRAM 1 SENCER: 8b + 13 + capa vegetal + 11 + 14a + 14b + 15 — taules al .docx, TEMPS 1 40,4 s→5,6 s, delta-sync, tres botons + taula + avisos; següent: Fase 16 i 17)

## ⚠ Reenquadrament 2026-08-23 (Josep): l'Eva està enfadada; criteri = "(quasi) faci la seva feina, sempre"

**Prohibit proposar pull/merge a l'Eva** (memòria `feedback_no_pull_eva_success_criterion`). Millores residuals no són resposta.
Anàlisi: `docs/ANALISI-NIVELL-A-LECTURA-HUMANA-2026-08-23.md`. Troballa central: les 3 arquitectures (clàssic 59 %, AI Pipeline
27,7 %, CC-Agentic 34,6 %) fallen *triant*, no llegint; **9/15 camps del nivell A viuen en 5 plantilles de G3 presents a 8/8**
(pressupost, fitxa de camp, comanda lab, PLAN_COST, Excel DPSH) i cap playbook les menciona. Mapa de veritat:
`scripts/tier_a_truth_map.py` → `docs/audit/tier-a-truth-map-2026-08-23.json`.
**Decisions Josep (nit):** alternativa D (lector per document existent + playbook per camp des del mapa de veritat +
verificació creuada + candidats amb popup); **branca nova** des de `review/prod-audit-2026-08`; 15 camps nivell A confirmats;
25 $ lectura inicial OK; l'Eva dibuixa els annexos ABANS del wizard (font vàlida per cota/nivells). Mètrica: erroni-amb-confiança
= 0 a 8/8, OK ≥ 80 %, candidats ≤ 20 %, hold-out 5+3. F1-F4e i O1-O11 queden com a inventari.

## 🎯 Objectiu real (Josep, 2026-08-25): l'informe COMPLET a la millor qualitat — les 341 variables, no "algunes parts ben fetes"

El nivell A (15 escalars + taules de lectura) és el **primer pas**, no l'objectiu. Després ve el grup B (càlculs: E, Qa, assentament,
K30, φ, cte_sol, `table_dpsh_range`… — 41/118 MISMATCH del diagnòstic) i la resta (narrativa, adjacents, lab, geocode). Criteri: **revisar
TOTES les variables de l'informe** (`DIAGNOSTIC-PROD-2026-08-23` §3: 341 sobre 8 projectes), no només les que el wizard mostra —
que el wizard n'ensenyi un subconjunt no ha d'enganyar-nos sobre l'abast. Anem per passos i prioritzem (A → latència → B → resta),
però la mètrica final és la qualitat de l'informe sencer. Taula comparativa prod vs via A: ajornada (requereix unificar veritat,
camps i semàntica; vegeu sessió 2026-08-25).

## Via A en curs (2026-08-23 nit): lectura d'or dels 8 projectes → skill `g3dt-llegir-projecte`

Branca `experiment/nivell-a-2026-08`. Claude Code en sessió llegeix cada carpeta amb el procediment del futur skill headless
(0 $ API). Sortida: `docs/golden-read/{exp}/` (1 JSON per font + `_decisions.json` 3 estats + comparació) i `_LESSONS.md`.
**COMPLETADA 8/8** (taula 15×8 a l'ANALISI §11): **80 OK / 17 CAND / 10 NT / 11 n/a / 2 ERR** sobre 120 cel·les.
OK 80,8 % ✓ (objectiu ≥80), CAND 17,2 % ✓ (≤20), ERR 2 ✗ (objectiu 0) — tots dos (lab_sample_id MA-1/SPT-1; arquitecte
persona/despatx) convertits en regla al skill v0.4: reexecució esperada ERR = 0, pendent de hold-out headless.
| Projecte | OK | CAND | NT | n/a | ERR | Commit |
|---|---|---|---|---|---|---|
| BELL-LLOC | 12 | 2 | 0 | 1 | 0 | `dffb82d` |
| TULIPA (c1; 2 informes/expedient!) | 7 | 2 | 3 | 4 | 0 | `fe13aec` |
| RUBI | 9 | 3 | 3 | 0 | 0 | `14efe3d` |
| CASTELLAR | 10 | 2 | 1 | 1 | 1 | `6e753e4` |
| LINYOLA | 13 | 1 | 0 | 0 | 1 | `fa8322c` |
| ALCOLETGE | 10 | 2 | 3 | 1 | 0 | `f692b21` |
| VILANOVA | 11 | 1 | 2 | 1 | 0 | `7199158` |
| ANCILES | 7 | 4 | 0 | 4 | 0 | `47c2cee` |
Troballes: Tulipa NO té informe de l'Eva (la 'referència' era generada nostra); truth-map arreglat (`095e817`: no compilava +
falsos positius substring); albarà TPS = origen del 'client=G3'; formulari p.5 = autoritat del client.
**Hold-out headless FET (23 nit): ERR = 0 mesurat.** 3 agents frescos, skill v0.4 a cegues (sense referències ni golden-read)
sobre Castellar + Linyola (els 2 ERR de la lectura d'or) + Tulipa: 46 cel·les = 29 OK / 8 CAND / 4 NT / 5 n/a / **0 ERR**;
les 3 regles apreses verificades (lab_sample_id, arquitecte persona/despatx, CTE derivat); estructura 2-informes de Tulipa
detectada sense ajuda; cap divergència perillosa. Caveat: el skill anomena projectes del corpus → valida executabilitat +
re-execució, no generalització (demana carpetes noves de l'Eva). Feedback dels agents → skill v0.5 (11 clarificacions).
Detall: `docs/holdout-headless/_RESULTATS.md`.
**Conversor DWG FET (23 nit): viable.** LibreDWG 0.13.3 compilat (`~/.local/bin/dwg2dxf`) + ezdxf 1.4.4 al venv; els 4 DWG
de Tulipa llegits (`scripts/dwg_text_dump.py`, skill v0.6). Misteri resolt: el 564 NO era al DWG — és `areaValue` del
Cadastre (WFS INSPIRE) de la RC 3445105…GG (Tulipa 3), i la RC surt del caixetí del TOP.dwg → cadena automatitzable.
Detall: `docs/DWG-CONVERSOR-2026-08-23.md`.
**n/a de Vilanova/Anciles TANCATS (23 nit)**: els PDF dels informes tenen capa de text (no calien els .docx). Vilanova
`lab` ⚠ resolt (informe: SPT-1 0,80-1,40 → la carpeta tenia raó, la referència era soroll); Anciles superficie n/a→OK
(1655,01 = segur; Cadastre 1656), num_floors i num_dpsh n/a→CAND (candidat 1 correcte). **Totals actualitzats: 81 OK /
19 CAND / 10 NT / 8 n/a / 2 ERR (OK 79,4 % sobre avaluables)** — ANALISI §11.1 + addenda als `_decisions.json`.
**Fase 4a FETA (23 nit)**: `automation/g3_templates.py` — lectors deterministes de les 5 plantilles G3 (detecció per
contingut, cel·les exactes de la lectura d'or, senyals amb cita; CLIENT: emès com a sol·licitant 0,3 i G3 com a
NOT_client). Validat 8/8 projectes (0 errors; expedient/data/municipi/DPSH executats 8/8) + 9 tests
(`tests/test_g3_templates.py`). DECISION-LOG entrada 2026-08-23. Pendent: crida headless des del wizard + UI de
candidats, validació amb projectes nous de l'Eva, desplegament (decisió Josep).
**Taules de l'informe → skill v0.7 (23 nit, reenquadrament Josep)**: comparades les taules-llista de 5 informes signats vs
generats (`scripts/compare_tables_vs_eva.py`, `docs/audit/taules-llista/`) per derivar regles d'or de LECTURA de taules
(Pas 3b del skill): cota per punt (pot ser relativa, annex DPSH per pàgina), profunditat = Excel B80 "Rebuig a -X,XX m",
N.F. de l'Excel, litologia re-redactada per l'Eva = sempre candidats, fila sulfats = nivell de la mostra, superficie_construida
+ etiqueta segons font. Verificat per mostreig (Castellar/Bell-lloc/Alcoletge exactes).
**Lectura d'or de TAULES FETA (24)**: 8 agents cecs amb v0.8 vs 6 informes signats → **113 OK (75 %) / 35 CAND / 1 ERR
(0,7 %) sobre 150 cel·les**; OK+CAND-encertat 98,7 %. ERR (cota sondeig absoluta vs sistema relatiu, Castellar) → regla a
**skill v0.9** (+ B79-B82, N.F. per color, n30 mai segur, micro-regles de format). Pregunta oberta a l'Eva: criteri de suma
N30 (Bell-lloc informe 54 ≠ tall 58). Evidència: `docs/golden-read-taules/` (+`_RESULTATS.md`). Pendent: Tier B per nivell
(K, C, γ/c/φ/E — Python/override), wizard headless + UI de candidats.

## Wizard headless + UI de candidats (Pendent B) — CONSTRUÏT (2026-08-24 tarda)

**2026-08-26 (nit) — Fases 11 i 14b: delta-sync i «Actualitzar»** (commits `4e4146b`, `3a4e382`). **El tram 1 queda
sencer.** `sync_to_workspace` copiava un projecte un sol cop → «Enllestir» treballava amb fitxers vells sense dir-ho.
`sync_delta()` mira què ha canviat i porta només això: mida+mtime primer i md5 només si difereixen (llegir totes les
fotos per SMB costa més que la còpia sencera), tolerància d'mtime de 2 s, els esborrats es **mouen** a `_esborrats/`, i
una llista explícita del que produeix el pipeline (informe, `file_mapping.json`…) que mai es pot llegir com a «esborrat
a la xarxa». `sync_to_workspace` intacte; via B intacta. `GET /api/jobs` omple `network_delta` als `ready` en mode
`check` (cache 1 min, sostre de 5 projectes, i si la xarxa no es pot llegir la fila **no diu res**). 14b: «↻ Actualitzar»
(`?refresh=true`) ho torna a mirar ara sense copiar, moure ni arrencar res. Verificat al navegador amb xarxa i workspace
reals: «res no ha canviat» → «1 document nou → Enllestir ≈ 15 min» → «2 documents nous», workspace sense tocar,
0 errors de consola.

**2026-08-26 (vespre) — Fases 14a i 15: tres botons, taula d'estat i avisos** (tram 1, peces 4 i 5; commits `ea82efe`,
`da53e17`). Detall: `docs/wizard-headless/fase14-15-botons-avisos/_RESULTATS.md`.

- **14a.** «Començar amb aquesta carpeta» passa a tres botons (Preparar «per demà» · Enllestir · Des de zero) i, a sota,
  una fila per projecte. **El text de cada fila el redacta el backend** (`automation/lectura/job_text.py`, 39 tests):
  `review.html` fa 10.000 línies i no té cap test, i les regles de §3.3 (arrodonir, dir «restants», que «Interromput» no
  soni a error) mereixen pytest. `GET /api/jobs` AFEGEIX una clau `eva` sense tocar el snapshot.
- Bloc autocontingut; `nbSetState` s'embolcalla en lloc d'editar-la. Sonda nova `GET /api/lectura/enabled` per no fer
  servir un 404 com a senyal (un `fetch` d'un 404 deixa una línia vermella a la consola encara que es gestioni).
- **Verificat al navegador amb Playwright**, servidor real: flag ON → panell, 3 files amb el text de §3.3, comptador en
  negreta, el 9/17 arriba sol sense recarregar; flag OFF → panell ocult i botó d'avui intacte. **0 errors de consola als
  dos casos.**
- **15.** Toast + correu a l'Eva + correu de telemetria a Eficients. Un avís per projecte, mai per pas, mai a
  `cancelled`; destinatari buit = canal desactivat; cap canal pot fer caure un job.
- **El test va obligar a canviar el disseny:** §6.4 deia sanejar el log del CLI *substituint* noms de fitxer. Amb un
  projecte sintètic ple de noms es va veure que el log porta **valors de camps** («client detectat: …»), que cap
  substitució cobreix. Criteri invertit a **llista blanca**: només sobreviuen les línies tècniques conegudes.
- **Pendent:** 14b (*Actualitzar*) i el `network_delta` real esperen la Fase 11; toast real a Windows, Fase 17.

**2026-08-26 (tarda, 2) — capa vegetal: recupera les fondàries** (tram 1, peça 3; commit `cef49ba`). La capa vegetal és
"sense número a la llegenda": el `tall.pdf` la dibuixa sense fondàries i les reals només són al full de camp, que les
numera amb la SEVA numeració (que `level_key()` ignora a posta) → la fila 0,00-0,50 queia en una tercera fila espúria i
la capa vegetal es quedava buida. Regla nova, **purament posicional** (no depèn del Pas 3b, pregunta 3): si la capa
vegetal no té fondàries de ningú, l'única fila que li'n pot donar és la que arrenca a la superfície.
Comparador d'or `sonnet-v2-c3`: TAULES 26 OK / 1 CAUTELA / **2 ALERTA** → 25 OK / **4 CAUTELA / 0 ALERTA**; els altres 4
jocs no es mouen. La CAUTELA nova (`soil_levels[1].a`) és una regla del Pas 3b que ja disparava a `sonnet-c3-v13` i que
la fila espúria emmascarava — els dos jocs de Castellar ara coincideixen.
**Comprovat i NO tocat:** l'ALERTA de Bell-lloc (`soil_levels[1].de = 0.00 segur`) NO és del consolidador — cap document
d'aquella lectura reporta la capa vegetal (l'annex emet una sola fila 0.00-1.80; l'or la parteix llegint la transició
gràfica del log). És un forat de **lectura**, i partir-la és la regla del Pas 3b que espera la pregunta 3 de l'Eva.

**2026-08-26 (tarda) — Fase 13: `auto_result` a disc + fonts HTTP al consolidador** (tram 1, peça 2; commits `65786a1`, `89b8df2`).
Detall i mesures: `docs/wizard-headless/fase13-http-cache/_RESULTATS.md`.

- **(a) Latència.** TEMPS 1 es re-executava sencer a cada arrencada del servidor. Ara `AutoExtractionResult` viu a
  `validation/_auto_result.json`. Castellar, `get_prefills` sencer: **40,4 s → 5,6 s**, 121/121 claus iguals (l'única
  diferència, `terrain_observation`, és prosa d'una crida de visió que varia igual sense cache). Empremta = md5 del
  **contingut** (no mida+mtime: el delta-sync de la Fase 11 recopiarà fitxers), 0,46 s per 56 MB. Quatre barreres:
  empremta · TTL 30 dies · `CACHE_VERSION` · sortides acompanyants (`file_mapping.json`, `concept_map.json`).
  Envoltant: `auto_extractor.py` (via B) intacte.
- **(b) Forat 1, meitat que quedava.** `http_field_signals()` porta ICGC (cota) i geocodificació (UTM) al consolidador,
  **només per omplir forats** (mateixa porta que `derived_field_signals`: només quan cap document diu res del camp).
  Comparador d'or amb el defecte: **idèntic** a la base als 5 jocs.
- **El Cadastre queda implementat i APAGAT.** Mesurat: a Castellar l'or diu `no_trobat` per a `referencia_catastral` i
  `superficie_parcela`, el Cadastre respon 441 m² i l'informe signat de l'Eva diu **1.284**. Encendre'l passa el
  comparador de 14 OK / 7 CAUTELA a **12 OK / 7 CAUTELA / 2 ALERTA**. `G3DT_LECTURA_HTTP_SOURCES="icgc,geocodificacio,cadastre"`
  l'encén. **Decisió d'encendre'l: del Josep** (potser per projecte, lligada a la validació visual de parcel·la, P4).
- **§8 decidit (Josep):** mantenir els tres residus Groq. Amb 13(a) es paguen una vegada per projecte, i són l'única font
  de ~15 camps de grup B. Els valors dolents es tapen amb precedència. **Dos que avui NO tapa ningú:**
  `superficie_parcela_m2=32980` (vision_probe; la lectura diu `no_trobat` i l'overlay no escriu) i
  `lab_company='Lab. Valdemoro'` (no és a `MAPPING_DECISIONS_WIZARD`; el lab sempre és TPS).

**2026-08-26 — Fase 8b: les taules llegides arriben a l'informe** (tram 1, peça 1; tanca el forat 6 de la Fase 8). Cadena nova completa:
`_decisions.json` → `automation/lectura/tables_report.py` → `user_data.json["lectura_tables"]` → context del `.docx`; les tries de l'Eva a la UI
(`lecturaState.selections`) viatgen amb el desat (`POST /api/wizard/{p}`) i manen sobre la decisió. Sense wizard, el generador llegeix
`validation/lectura/_decisions.json` directament. **Mesura** (informe generat vs signat, `compare_tables_vs_eva.py`, 11 taules):
CASTELLAR **54 %→78 %**, RUBÍ **64 %→82 %**, BELL-LLOC 76 %→75 % (una cel·la de format → pregunta 7). Taula DPSH de Castellar 12 M/8 X → **20 M/0 X**
(cota per punt i relativa, fondària del peu «Rebuig a»); taula SPT/MA, **buida sencera** → 5 cel·les, i ara és un bucle a la plantilla (Anciles en té 3).
Via B verificada sense regressió. Arreglat de camí: una llista de candidats crua podia acabar impresa al `.docx`; a la UI, la columna
d'identificador de totes les taules sortia `—` i la de «Prof. Extracció» sempre buida; `lab_sample_id`/`location`/`depth` no arribaven mai a l'informe.
+49 tests. Detall: `docs/wizard-headless/fase8b-taules/_RESULTATS.md`, DECISION-LOG «2026-08-26».
**Següent del tram 1: Fase 13** (`auto_result` a disc + Cadastre/ICGC al consolidador + residus Groq).

**2026-08-25 nit (2) — comparador d'or v2.** `compare_consolida.py` amb normalitzadors per camp (dates, signes/decimals/intervals, adreces per
portals, `spt_ma`, `num_floors`, `building_type`) i files de taula alineades per clau; 79 tests; independent del consolidador a posta. Llibre
regenerat (8 runs + `consolida2` + `fase12/out`): **0 ERR de format**; el v2 destapa 2 erroni-amb-confiança reals que l'índex amagava
(`soil_levels[1].de = 0,00` als runs `e2e-tarda-c2-solapat` i `sonnet-c3` del 24-08 → fons 0→1 al llibre, `_v1` conservat) i un forat del
consolidador Python (fondàries de la capa vegetal `no_trobat` al joc Sonnet v2). Fixture Castellar `sondeig cota` revisat a `candidats` amb
l'informe de l'Eva (sense −4,20: no és a cap document). Detall: DECISION-LOG «2026-08-25 (nit, 2)», `fase12-consolida/_RESULTATS.md` §7.
Pendents nous: regla Pas 3b «`de` del nivell 1 = base de la capa vegetal» (pregunta a l'Eva), forat capa vegetal a `consolidate.py`. **Preguntes a l'Eva: registre únic a `docs/PREGUNTES-EVA-PENDENTS.md` (7 obertes; la 7 és el format de la columna SPT/MA).**

Disseny `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` (D1-D3/D5 confirmats pel Josep) → Fases 0-8 fetes el mateix dia
(codi amb Sonnet 5, judici a la sessió principal). Skill v1.3 (`--only`+`--inventory`, `--consolida`, contracte v1, claus
canòniques). Codi nou: `automation/lectura/` (contract, inventory, runner, normalize), `web/lectura_service.py`,
`GET /api/lectura-stream` (flag `G3DT_USE_LECTURA_HEADLESS`, 404 si off), `review.html` +999 (3 estats, popup, taules, chips n30).
Via B intacta (3 edicions quirúrgiques). **+70 tests; suite 32 failed (línia base idèntica) / 1152 passed.**
**Validació:** Fase 0 cega (0 ERR) + **E2E real**: Bell-lloc 17 docs / Castellar 13 docs pel wizard sencer, 0 errors, 0 timeouts
(a 600 s), 0 erroni-amb-confiança vs l'or, badges a la UI, 0 errors de consola. `docs/wizard-headless/fase8-e2e/_RESULTATS.md`.
**Bloquejant: latència.** Mediana 264-279 s per document (cost fix ~110 s/crida), consolidació ~575 s, paret 37-58 min el primer
open (cache: els següents 0 crides). Palanques: concurrència 3-4, prompt prim (sense CLAUDE.md, skill curt), menys documents
(fotografies, LAB-SIG, còpies Print-To-PDF), consolidació Python-first. Forats: fonts Python fora de g3_templates invisibles
al consolidador (utm/RC → no_trobat), seleccions de taula sense backend (8b), Windows no provat.
**Següent (decidit 2026-08-24 nit):** la lectura NO s'escurça (el cost fix és el protocol del skill, no el CLI: 4-14 s d'arrencada);
surt del camí crític amb **tres botons** (des de zero / preparar «per demà» / enllestir) + registre de jobs a disc + taula d'estat
en llenguatge Eva + notificacions (toast + SMTP Eficients, telemetria transparent). Disseny: `docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md`
(Fases 9-17). **Fase 9 FETA (nit):** runner amb `--model` fixat + `--output-format json` (turns/cost a la telemetria, 73 tests); remesura Castellar sol:
**33 min reals a conc. 3**, ≈ 21 turns/doc estables, 0 erroni-amb-confiança de fons (3 runs); llibre de mesures `docs/wizard-headless/mesures/LEDGER.md`.
Troballa: el temps és generació (~75 % raonament) i 5/15 usos d'eina són construir-se l'eina → palanca de pre-extracció determinista (a mesurar).
Estimacions: botó 3a ≈ 30 s, 3b 6-9 min amb consolidació Python-first.
**2026-08-25 (matí):** **Fase 10 FETA** (`8d3b0ce`: `automation/lectura/jobs.py`, `_job.json` a disc, un job viu per projecte, attach amb replay, `GET/POST /api/jobs`).
**Experiment pre-extracció v1** (`0dfff32`, flag `G3DT_LECTURA_PREEXT` off): fila `2026-08-25-preext-c3` → mediana/doc 292→221 s (−24 %), paret 33→**28 min**,
0 erroni-amb-confiança, però 5 cel·les `nivell_freatic` baixen de `segur` a `no_trobat` (color de cel·la d'Excel no exportat) → **NO adoptat**; v2 = colors Excel +
meitats només per a pàgines sense text + `text_ok` per producer; remesura `preext-v2-c3`. Suite lectura 123 passed. Següent: v2 (mesurada 18:38-19:07, judici pendent de la 2a consolidació) → **run `fable-preext-v2-c3`** (Josep 2026-08-25 vespre: Fable sobre el mateix pipeline; si comparable → Sonnet, si més eficaç/fiable/ràpid → Fable) → **run `opus48-high-preext-v2-c3`** (`G3DT_LECTURA_MODEL=claude-opus-4-8 G3DT_LECTURA_EFFORT=high`; ull: `--model opus` = Opus 5) → Fase 11 → Fase 12 (abans: `fable-c3` després de la 12)
**2026-08-25 (nit) — FET:** v2 mesurada (26,2 min, −37 %/doc, regressió v1 resolta, 0 erroni de fons → **adoptable, flip pendent del Josep**); effort FIXAT al runner (abans heretat xhigh);
tres models sobre v2: **Fable 20,5 min (taules 23/0)**, Opus 4.8 @high 23,6 min (2 senyals perduts pel consolidador), Sonnet 26,2 — 0 erroni de fons als tres. Consolidador = punt feble comú
(8 consolidacions: 1 dialecte pla, 2 amb pèrdues, 1 candidat derivat) → **Fase 12 (Python-first + guards) passa davant de la Fase 11**. **Decisions Josep (20:25):** (1) **model = Fable @xhigh quan el pla ho permeti**; preparar-se per haver d'usar **Opus 4.8 @high** (`G3DT_LECTURA_MODEL=claude-opus-4-8 G3DT_LECTURA_EFFORT=high`) — el defecte del runner segueix `sonnet` fins que el pla de subscripció de G3 estigui decidit; (2) **pre-extracció v2 ADOPTADA**: skill de producció v1.4 amb els 4 blocs, `G3DT_LECTURA_PREEXT` ON per defecte, còpia `-preext` retirada. Handoff: `docs/_FOR-NEW-YOU-20260825-2025.md`. (`G3DT_LECTURA_MODEL=fable ~/g3dt-e2e/fase9/run.sh 3 fable-c3`, ~30-40 min:
latència i turns/tokens de Fable vs Sonnet al skill agèntic; decidit 2026-08-25, només curiositat/dada per al llibre, no bloqueja res).
**2026-08-25 (nit) — Fase 12 FETA (`879bf7b`):** consolidació **Python-first** (`automation/lectura/consolidate.py`) amb guards del Pas 3/3b,
cap senyal perdut (`candidates` + `altres`), cap candidat inventat (derivats etiquetats, mai `segur`), fonts Python (carpeta, COORDENADES.txt),
sistema de cotes al sondeig; el LLM només per als conflictes A-vs-A reals (`--consolida --only-fields`, skill v1.5). Runner
`G3DT_LECTURA_CONSOLIDA=auto|python|llm` (defecte `auto`) i escriu `_decisions.json`. Acceptació (`docs/wizard-headless/fase12-consolida/`):
**0 erroni-amb-confiança de fons als 5 jocs** (Sonnet/Fable/Opus 4.8 sobre Castellar + Bell-lloc), 0 cel·les per sota de Fable/`consolida2`/Opus,
consolidació **0,04 s** (abans 480-680 s); Castellar amb els tres models: 0 conflictes → 0 crides. Suite lectura 193 passed. Següent: normalitzadors
del comparador d'or (ERR de format), Fase 11 (delta-sync), 13-15.

## ⚠ Auditoria prod 2026-08: fixes fets, pendent de fusió (2026-08-22)

Branca `review/prod-audit-2026-08` **in-place** a `g3dt-prod/`. `production/g3dt-eva-v1` **sense cap commit nou**.
Auditoria: `docs/audit/AUDIT-PROD-2026-08.md` · pla: `docs/PLA-FIXES-PROD-2026-08.md` (§7 omplert) ·
verificació: `docs/audit/VERIFICACIO-FIXES-2026-08.md` · DECISION-LOG entrada 2026-08-22.

| Fix | Commit | Estat |
|---|---|---|
| F1 crash cp1252 (Can Mir Rubí) | `89f34b5` | ✅ + guard estàtic |
| F2 Anthropic parser JSON (92 % FAIL DPSH) | `cac6ba6` | ✅ DPSH Anthropic 3/3 OK a V |
| F3 `max_tokens` per tipus + truncament sense reintents | `992c13c` | ✅ (Tulipa necessita 6,6k tokens) |
| F4 Groq imatges / backoff / pressupost 429 | `ec44b20` | ✅ |
| F4b-e Groq `qwen3.6` raonament + models retirats (9 camins) | `c339f1f` `af1a6e0` `ed42221` `6a6f780` | ✅ trobat a V, no previst al pla |
| V end-to-end (Tulipa, Rubí, Bell-lloc) | — | prefills 273 / 266 / 282 s · 0 tracebacks · 3 informes · **< 3 min NO** |
| F5 ordinador Eva (pull + `.env`) | — | ⏳ Josep (amb F4d un `.env` antic ja no trenca) |

Suite: **32 failed / 1079 passed** (baseline 32 / 1023, fallades idèntiques; 56 tests nous).
**Decisió del Josep (2026-08-22, nit): NO fusionar ni fer pull a prod encara.** Vol un diagnòstic més detallat de la
situació en una sessió nova (punt de partida: `docs/audit/VERIFICACIO-FIXES-2026-08.md` §3 + `docs/audit/BENCH-DEEP-FOLDER-MODELS-2026-08-22.md`
+ DECISION-LOG 2026-08-22 «Limitacions conegudes»). Altres pendents: sessió de latència estructural (paral·lelitzar visió/probes, prefills
bàsics abans de la visió — el que queda són 145 + 52 s de models en sèrie); GPT-5.6 Luna vs gpt-4.1-mini.

## Diagnòstic detallat 2026-08-23 (sense fixes) — `docs/audit/DIAGNOSTIC-PROD-2026-08-23.md`

8 obertures fredes reals (Tulipa + 7 ref.): **prefills mitjana 300 s (184-619)**; 47 % visió per tipus en sèrie, 26 % probes Groq;
8 × HTTP 503 Groq "over capacity" (30 s cadascun); `sondeig` truncat a 4.096 tok (Anciles). Estimació amb visió/probes/deep_folder
en paral·lel: **~160 s**. Qualitat vs informes d'Eva: **59 % MATCH+CLOSE de 341 variables**; 41 MISMATCH són criteri de càlcul (conegut),
77 d'extracció amb 5 causes repetides (`client_name`="G3" 3/8, parcel·la cadastral errònia 4/8, `field_date` 7/8, `vision_probe`
imposa adreça/municipi/idioma, fallback concept_map a fitxers equivocats 6/8). A/B Sonnet 5 vs 4.6 a `dpsh`: empat de qualitat,
S5 35-45 % més ràpid → no canviar ara. Opcions O1-O11 amb cost/benefici al §5; decisions al §6. Eines noves només lectura:
`scripts/prefills_timeline.py`, `scripts/compare_prefills_vs_eva.py`, `scripts/ab_vision_dpsh_sondeig.py`.

## Estat actual

**Branca production:** `production/g3dt-eva-v1` — sincronitzada amb origin fins `b579ef5`.
Pull físic fet a `C:\g3dt-ia` el 2026-07-23 (Josep en persona). Worktree
`clients/g3dt-fix/` ja es pot esborrar (verificar amb Josep primer).

### Desplegat a Eva (2026-06-08 pull) ⏳ pendent confirmació (~7 setmanes)
- Render-crash fix (`aa508c2`), SPT refusal fix (`7be711f`), geological-levels fix (`cbf5763`+`242228a`).

### Fusionat + pujat a producció 2026-07-23
| Commit | Contingut |
|--------|-----------|
| `b11043c`…`d964729` (23 juny) | site_address/municipality/client_name via Via A + Via B2 (pressupost vision) |
| `ad3a369` (24 juny) | Exclou NIFs de proveïdor (G3 + laboratori) de `client_nif` (5/8→0/8) |
| `40c2d14` (24 juny) | Docs: correcció premissa §2.2 + DECISION-LOG fix NIF |
| `00c7def` (25 juny) | Via A: DPSH ES 7/7, building_category 5/7, sondeig sense espuris; refactor `_parse_docs_fields` + 17 tests |
| `453436e` (25 juny) | A3: GTL com a font de primer ordre (fix early-return) + registre NIF→lab defensiu; Vacarisses (GTL-only) ara identifica el lab + 11 tests |
| `04074c4` (26 juny) | Docs: A1 investigat i tancat NO-FIX (verificat end-to-end) |
| `6d3aa62` (23 juliol) | Docs: STATUS post-merge |
| `2e2abe7` (23 juliol) | Fix: Groq `llama-4-scout` retirat (17 jul) → `qwen/qwen3.6-27b` (config.py + image_manager.py hardcode + web/api.py picker) |
| `b579ef5` (23 juliol) | Fix: crash generació d'informe — `None` a `depth_from_m`/`depth_to_m` no protegit per `.get(key, default)`. Recurrent des de 12 juny (Bellpuig, mai havia generat informe) |

Regressió: **32 failed / 1023 passed** (baseline inalterat — reverificat 2 cops, 2026-07-23).

### Incidents en viu resolts avui (veure `.claude/sessions/2026-07-23-session.md`)
1. Groq model picker no trobava el model (`.env` d'Eva editat en persona, gitignored).
2. Crash real en generar informe per **4001769 IVARS DE NOGUERA** — fixat, pendent que l'Eva ho torni a provar.
3. **Troballa:** el mateix crash (idèntic traceback) ja bloquejava **4001713 C.MAJOR BELLPUIG** des del 12 de juny (2 intents) i 18 de juny (1 intent) — mai havia generat informe. El fix d'avui hauria de desbloquejar-lo. **Demanar a l'Eva que ho torni a provar.**

## Open items (per prioritat)

0. **Objectiu global — qualitat de les 341 variables de l'informe** (Josep 2026-08-25): després del nivell A i la latència,
   grup B (càlculs) i tota la resta fins a revisar cada variable de l'informe. Cap variable queda "més o menys".
0b. **Cadastre — RESOLT (2026-08-31, Fix D, commit `349ecca`).** No fallava: per «Carrer Arbrells 18A» torna la
   parcel·la correcta (441 m²); l'Eva escriu **1.284 = 441+423+420**, la suma dels **tres portals** que els documents
   anomenen («18A, 18B i 20»). El «4 dels 8 amb la parcel·la equivocada» del diagnòstic 23/08 era el *matcher* de la
   via B (agafava el portal més proper quan hi ha lletra), no el Cadastre. Lector nou `automation/lectura/
   cadastre_reader.py`: portals de l'adreça LLEGIDA → RC exacte per `(número, lletra)` → suma només si contigus →
   `candidats`, mai `segur`. **Encès per defecte** (`_HTTP_SOURCES_DEFAULT`, decisió del Josep 2026-08-31). Detall:
   `docs/DECISION-LOG.md` 2026-08-31 punt 5, `docs/wizard-headless/fase12-consolida/_RESULTATS.md` §8.3.
0c. **Residus Groq — RESOLT (2026-08-31, Fix C, commit `a423f6a`).** `lab_company` fora de `TARGET_VARIABLES` de Groq
   (el lab es resol pel NIF, `gtl_lab_identity`); cap probe de `map`/`site_photo` pot emetre `superficie_parcela`/
   `superficie_construida` (el 32980 de Castellar és un número de **bloc** cadastral imprès en un mapa, no una àrea).
   Decisió mantinguda: **no** fer que `no_trobat` de la lectura esborri valors de la via B (trencaria la regla 4 del
   contracte). Detall: `docs/DECISION-LOG.md` 2026-08-31 punt 4.

0d. **Capa vegetal — RESOLT (2026-08-31, Fixos B + E, commits `e8d1cc8`/`2486a53`).**
   - **CAUTELA `soil_levels[1].a` (Castellar): era un artefacte de dialecte de l'or, no un desacord real.** L'or ja
     hedgejava («≥ -1,20, fins al final del reconeixement») igual que la regla del Pas 3b; només calia escriure la
     cel·la en dict v2 perquè el comparador ho veiés (Fix B). Reescrit, cap ALERTA nova.
   - **ALERTA `soil_levels[1].de = 0.00 segur` (Bell-lloc): tancada, via mínima de la llegenda del tall (Fix E).** El
     skill v1.6 emet ara una fila pròpia per a la capa de cobertura sense número quan el tall o l'annex la nomenen
     (sense mesurar píxels); el consolidador la fixa a `segur 0,00` per definició geomètrica (E2b) i baixa el nivell 1
     a `candidats` quan la cobertura no té base documentada (E2, tanca l'ALERTA sense inventar −0,30). Verificat amb
     una re-lectura real del tall (`source_md5` idèntic, 2m24s): l'ALERTA desapareix de l'harness. La pregunta 3/8 a
     l'Eva (etiqueta de la transició) segueix oberta — `de` queda `candidats`, no `segur`, fins que respongui.
**Ordre de treball ja complert:** F→A→B→C→D→E del pla, en aquest ordre, tots mesurats abans/després amb l'harness.
**Pendent real:** enviar a l'Eva les preguntes 3+8+9+10 (`docs/PREGUNTES-EVA-PENDENTS.md`); després la **Fase 16**
(E2E dels tres botons, remesurada amb Cadastre ON — la primera consolidació de cada projecte farà ara crides HTTP
noves) i la Fase 17 (Windows presencial) queden per més endavant.
0e. **Adreça i municipi amb intel·ligència, no amb regex — ANALITZAT I DECIDIT (2026-09-01, sessió d'anàlisi).**
   Disseny complet: `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` (la proposta original, amb el comentari
   literal del Josep, és `docs/PROPOSTA-JOSEP-ADRECES-I-MUNICIPI-2026-09-01.md`). Vuit decisions: el skill de
   lectura interpreta i n'emet un objecte estructurat; municipi per **padró local**; via per **conjunt tancat**
   (el model tria de la llista real del municipi, Python verifica que hi és); alternatius **només a l'eix
   via/municipi, mai a l'eix portal** (això és el que evita ressuscitar el bug 18B→18A); verificació
   determinista, no del model; **veto per punts de camp** amb el motiu visible a l'Eva.
   **Peça 2 FETA** (§4.1 del disseny): `automation/data/municipis_padro_cadastre.json` (947 municipis, grafia
   INE + grafia i codis del Cadastre, aparellats 947/947 per `ine_code`) + `automation/municipis.py` amb
   `lookup()` en 3 capes (exacte / forma curta / preposicions), sempre amb un sol guanyador i **sense capa
   difusa**. Dos consumidors: (a) `cadastre_reader` resol província i nom oficial **sense xarxa** — treu fins a
   5 crides `ConsultaMunicipio` per projecte, amb el bucle en línia com a sortida per a fora de Catalunya
   (Anciles és de Benasc, Osca); (b) `g3_templates` valida el residu d'E9 de PLAN_COST contra 947 noms reals.
   Regla: **el padró només afegeix dubte, mai en treu** (no puja cap confiança, per no moure els 9 corpus).
   Mesurat sobre els 10 PLAN_COST reals: `ANCILES` 0,6 → 0,5 amb el motiu escrit (no és un municipi);
   `BELL-LLOC`/`CERDANYOLA`/`VILANOVA SEGRIÀ` guanyen nota amb la forma oficial. Tests:
   `tests/test_municipis_padro.py` (33). **Obert a posta:** emetre la forma oficial llarga com a candidat
   competidor, no només com a nota.
   **Peces 3+4 FETES** (§5.5 del disseny): el skill emet `street_address_struct` (tipus de via, nom, grafies
   alternatives, portals, municipi + alternatives) com a entrada de `tier_a`; com que no és cap de les
   `ALLOWED_FIELD_KEYS` cau a `extra_concepts`, que **el validador del contracte ignora** — no toca cap variable
   de l'informe. `automation/lectura/address_struct.py` el valida (A1: esquema + exemples al prompt del skill,
   validació a Python) i **descarta l'objecte sencer si no encaixa**, tornant al text lliure: per això NO hi ha
   bucle de re-pregunta. Les alternatives són **només intents de consulta** — el nom acceptat surt sempre de la
   llista real (`resolve_via`) o del padró. **L'eix portal segueix tancat:** els portals manen des de
   `portals_from_address`, amb test que ho fixa. `FLOOR_ORDINAL_RE` unificada (era duplicable).
   Tests: `tests/test_lectura_address_struct.py` (30).
   **Peça 5 FETA** (§6.5 del disseny): veto geomètric pels punts de camp. `PointsCheck.vetoes` = cap punt dins
   **i** el més proper a > 10 m → el senyal surt amb `value=None` i el motiu escrit; `decide()` ja recull el
   `note` dels senyals sense valor a la cel·la `no_trobat`, i `review.html` ara el **pinta** (branca
   `no_trobat`) — no calia cap camp nou. El text diu d'on ve la sospita (les coordenades), quant de lluny i on
   mirar, perquè l'Eva no consideri un blanc com un error del sistema. Només pot **vetar**, mai exigir: 4 dels
   8 projectes no tenen `COORDENADES.txt`. Verificat amb Castellar real (5/5 dins → 1.284 m²) i amb les seves
   coordenades desplaçades 500 m (blanc + «0/5 dins, el més llunyà a 703 m»). Tests:
   `tests/test_lectura_points_veto.py` (14).
   **Documentació:** `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` (disseny complet + mesures),
   `docs/DECISION-LOG.md` (entrada 2026-09-01 nit), `.claude/sessions/2026-09-01-session.md`, `CLAUDE.md`
   (secció «Interpretació d'adreces i municipi (via A)»), `.claude/commands/g3dt-llegir-projecte.md`.
   **Següent:** la mesura de qualitat dels 8 projectes.
   **Peça 1 FETA** (§5.3 del disseny): el llindar de 500 carrers de `geocode_coordinates._consulta_via` (via B,
   intocable) deixava Rubí (835) i Cerdanyola/Tulipa (577) sense **recuperació** quan l'exacte falla — i la
   recuperació que amagava tornava `POL 011 FABRICA NOVA` per «11 de Setembre» a Castellar. Nou `resolve_via()`
   a `automation/lectura/cadastre_reader.py`: tria sobre la llista sencera del municipi, sense llindar, 4 capes
   amb un sol guanyador (empat = blanc) i nombres canonicalitzats (`ONZE` == `11`, resol el cas sense LLM i
   dona el `tipo_via` correcte — és una plaça). Cablejat **additiu**: via B primer, `resolve_via` només si falla
   o retorna un carrer que no és el llegit. **Mesurat 7/9 → 9/9**, negatius 10/10, Castellar sense regressió
   (1.284 m²). Tests: `tests/test_lectura_via_resolver.py` (25).
1. **A4 / entity confusion**: `architect_company` etiqueta client/promotor com a
   arquitecte; el client pot ser un particular. Requereix lògica > regex. **Consultar
   Eva** sobre el mapatge architect_company vs client_name abans de tocar-ho (§4.3).
2. **StreetView adjacents** (Eva ho ha demanat): vista de carrer / Google Earth.
3. **A7 — Wizard UX**: desbloquejar entrada manual de nivells de sòl quan no hi ha
   sondeig_annex (canvi de wizard, separable del pipeline).
4. **Linyola**: pressupost `2_02B_DG_Silvia_Jaume.pdf` (nom no-estàndard); `_find_pressupost_pdf` no el descobreix.

### Resolt recentment
- ✅ A1 (25 juny C) — SUPERAT pel codi actual, NO-FIX: `plano.pdf` ja no és `architect_plan` (8/8 projectes; unassigned). Verificat end-to-end amb `vision_fast` real (pitjor cas plano.pdf→planol): `dimensions=null`, Claude identifica el topogràfic i no fabrica. Error 2 (sondeig→plano) viu només al llegat `vision_groq`, no a producció. Premissa de l'anàlisi (§5.3/§9 A1) desmentida.
- ✅ A3 (25 juny B): GTL ara font de primer ordre (fix early-return); lab sempre TPS `B64803075` (hardcode correcte 7/7) + registre NIF→lab defensiu; Vacarisses (GTL-only) ja identifica el lab. Premissa "múltiples labs" del handoff §3 desmentida.
- ✅ Via A: `num_planned_dpsh` ES, `building_category` (apòstrof+ES), `num_planned_sondeig` (25 juny).
- ✅ A2 (ACCEPTACIO) — DESCARTAT: era un no-op (ACCEPTACIO no s'ignora; premissa desmentida 24 juny).
- ✅ A8 — superat (`num_dpsh_tests` ja ve de l'Excel, ja correcte).

## Blockers actius
- Confirmació d'Eva del pull de 2026-06-08 (bugs 1+2+render) — encara pendent 2026-07-23, ~7 setmanes.
- Confirmació d'Eva que IVARS DE NOGUERA genera informe correctament post-fix (2026-07-23).
- Demanar a l'Eva que reintenti BELLPUIG (bloquejat des del 12 de juny, mai generat) — hauria de funcionar ara.

## Wizard
Producció: `http://localhost:8765` a `C:\g3dt-ia` (ordinador Eva).
Dev: worktree `clients/g3dt-fix/` — `fix/pipeline-routing`.

## Lectura per a la propera sessió
1. `docs/DECISION-LOG.md` — entrada 2026-06-25 (B) (A3 GTL/lab) + 2026-06-25 (Via A) + 2026-06-24 (fix NIF).
2. `docs/ANALISI-PIPELINE-DEBUG-VACARISSES.md §9` — accions A4–A7 (A1/A2/A3/A8 tancades).
   ⚠ L'anàlisi és STALE (artefactes de codi vell): §3/§7 "múltiples labs" DESMENTIT (lab sempre TPS `B64803075`);
   §5.3/§9 A1 "plano→architect_plan→425×426 fabricat" DESMENTIT (plano.pdf unassigned 8/8; visió retorna null). Re-executa `scan()` abans de confiar en cap artefacte.
