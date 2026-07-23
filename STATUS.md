# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-07-23

## Estat actual

**Branca production:** `production/g3dt-eva-v1` — sincronitzada amb origin fins `04074c4` (26 juny).
`fix/pipeline-routing` fusionat (fast-forward) i pujat a origin el 2026-07-23. Worktree
`clients/g3dt-fix/` ja es pot esborrar (verificar amb Josep primer).

### Desplegat a Eva (2026-06-08 pull) ⏳ pendent confirmació
- Render-crash fix (`aa508c2`), SPT refusal fix (`7be711f`), geological-levels fix (`cbf5763`+`242228a`).

### Fusionat a production 2026-07-23 (pendent de pull físic a l'ordinador de l'Eva — Josep hi va avui)
| Commit | Contingut |
|--------|-----------|
| `b11043c`…`d964729` (23 juny) | site_address/municipality/client_name via Via A + Via B2 (pressupost vision) |
| `ad3a369` (24 juny) | Exclou NIFs de proveïdor (G3 + laboratori) de `client_nif` (5/8→0/8) |
| `40c2d14` (24 juny) | Docs: correcció premissa §2.2 + DECISION-LOG fix NIF |
| `00c7def` (25 juny) | Via A: DPSH ES 7/7, building_category 5/7, sondeig sense espuris; refactor `_parse_docs_fields` + 17 tests |
| `453436e` (25 juny) | A3: GTL com a font de primer ordre (fix early-return) + registre NIF→lab defensiu; Vacarisses (GTL-only) ara identifica el lab + 11 tests |
| `04074c4` (26 juny) | Docs: A1 investigat i tancat NO-FIX (verificat end-to-end) |

Regressió: **32 failed / 1023 passed** (baseline 32-failed inalterat — reverificat 2026-07-23 post-merge).

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
- Confirmació d'Eva del pull de 2026-06-08 (bugs 1+2+render) — encara pendent 2026-07-23.
- Pull físic a `C:\g3dt-ia` (ordinador Eva) del contingut fusionat avui (04074c4) — Josep hi va en persona 2026-07-23.

## Wizard
Producció: `http://localhost:8765` a `C:\g3dt-ia` (ordinador Eva).
Dev: worktree `clients/g3dt-fix/` — `fix/pipeline-routing`.

## Lectura per a la propera sessió
1. `docs/DECISION-LOG.md` — entrada 2026-06-25 (B) (A3 GTL/lab) + 2026-06-25 (Via A) + 2026-06-24 (fix NIF).
2. `docs/ANALISI-PIPELINE-DEBUG-VACARISSES.md §9` — accions A4–A7 (A1/A2/A3/A8 tancades).
   ⚠ L'anàlisi és STALE (artefactes de codi vell): §3/§7 "múltiples labs" DESMENTIT (lab sempre TPS `B64803075`);
   §5.3/§9 A1 "plano→architect_plan→425×426 fabricat" DESMENTIT (plano.pdf unassigned 8/8; visió retorna null). Re-executa `scan()` abans de confiar en cap artefacte.
