# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-08-24 tarda (via A: wizard headless CONSTRUÏT i validat E2E — 0 erroni-amb-confiança; latència 35-60 min = bloquejant)

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
meitats només per a pàgines sense text + `text_ok` per producer; remesura `preext-v2-c3`. Suite lectura 123 passed. Següent: v2 → Fase 11 → Fase 12.

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
