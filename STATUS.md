# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-07-23 (visita presencial a l'ordinador de l'Eva)

## ⚠ Auditoria interna en curs (2026-08-22)

Branca `review/prod-audit-2026-08` **in-place** a `g3dt-prod/` (sense worktree). Prod intacte.
Evidència: 14 dies de logs reals de l'Eva → `docs/audit/AUDIT-PROD-2026-08.md`.
Resum: 19 projectes reals, 14 informes OK; espera prefills mediana 7,1 min (tot LLM);
visió DPSH trencada (Anthropic 92% FAIL per parser, OpenAI 43% per `max_tokens`); crash
Unicode cp1252 a `wizard_service.py:2172` **no fixat**; estat post-visita 23 jul no verificat.
**Pla d'execució per a sessió nova:** `docs/PLA-FIXES-PROD-2026-08.md` (F1-F4 + verificació
Tulipa + documentació, ~4,5 h, guardarails inclosos). F5 (estat ordinador Eva) = Josep.

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
