# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-08-23 nit (via A en curs: lectura d'or Bell-lloc + Tulipa, 0 ERR; skill v0.2)

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

## Via A en curs (2026-08-23 nit): lectura d'or dels 8 projectes → skill `g3dt-llegir-projecte`

Branca `experiment/nivell-a-2026-08`. Claude Code en sessió llegeix cada carpeta amb el procediment del futur skill headless
(0 $ API). Sortida: `docs/golden-read/{exp}/` (1 JSON per font + `_decisions.json` 3 estats + comparació) i `_LESSONS.md`.
| Projecte | OK | CAND | NT | N/A | ERR | Commit |
|---|---|---|---|---|---|---|
| 4001612 BELL-LLOC | 12 | 2 | 0 | 1 | **0** | `dffb82d` |
| 3001706 C.TULIPA (casa 1) | 7 | 2 | 3 | 4 | **0** (1 cond. DWG) | `fe13aec` |
Pendents: Rubí, Castellar, Linyola, Alcoletge, Vilanova, Anciles · conversor DWG · `tier_a_truth_map.py` amb `\b` · §11 anàlisi.
Skill v0.2 amb Pas 0 (context del document abans de llegir-lo). Tulipa: un expedient = 2 informes (el wizard no ho contempla).

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
