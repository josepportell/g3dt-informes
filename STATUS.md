# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-06-25

## Estat actual

**Branca dev:** `fix/pipeline-routing` (worktree `clients/g3dt-fix/`).
**Branca production:** `production/g3dt-eva-v1` — sincronitzada amb origin fins `d964729` (23 juny).

### Desplegat a Eva (2026-06-08 pull) ⏳ pendent confirmació
- Render-crash fix (`aa508c2`), SPT refusal fix (`7be711f`), geological-levels fix (`cbf5763`+`242228a`).

### A `fix/pipeline-routing`, NO pujat a production encara
| Commit | Contingut |
|--------|-----------|
| `ad3a369` (24 juny) | Exclou NIFs de proveïdor (G3 + laboratori) de `client_nif` (5/8→0/8) |
| `40c2d14` (24 juny) | Docs: correcció premissa §2.2 + DECISION-LOG fix NIF |
| `00c7def` (25 juny) | Via A: DPSH ES 7/7, building_category 5/7, sondeig sense espuris; refactor `_parse_docs_fields` + 17 tests |
| _(25 juny B, sense commit encara)_ | A3: GTL com a font de primer ordre (fix early-return) + registre NIF→lab defensiu; Vacarisses (GTL-only) ara identifica el lab + 11 tests |

Regressió: **32 failed / 1023 passed** (baseline 32-failed inalterat).

## Open items (per prioritat)

1. **A1 — validació de rol amb `doc_type`** (alt risc, fabricació): plano topogràfic
   classificat com a `architect_plan` → dimensions inventades (425×426m de cotes).
   Arrossega Error 2 (sondeig_annex rep el mateix fitxer equivocat). El concept_map
   ja té el senyal estructurat (`notes` prefix "map:"/"plan:"). Veure §9 A1 + §5.2.
2. **A4 / entity confusion**: `architect_company` etiqueta client/promotor com a
   arquitecte; el client pot ser un particular. Requereix lògica > regex. **Consultar
   Eva** sobre el mapatge architect_company vs client_name abans de tocar-ho (§4.3).
3. **StreetView adjacents** (Eva ho ha demanat): vista de carrer / Google Earth.
4. **A7 — Wizard UX**: desbloquejar entrada manual de nivells de sòl quan no hi ha
   sondeig_annex (canvi de wizard, separable del pipeline).
5. **Linyola**: pressupost `2_02B_DG_Silvia_Jaume.pdf` (nom no-estàndard); `_find_pressupost_pdf` no el descobreix.

### Resolt recentment
- ✅ A3 (25 juny B): GTL ara font de primer ordre (fix early-return); lab sempre TPS `B64803075` (hardcode correcte 7/7) + registre NIF→lab defensiu; Vacarisses (GTL-only) ja identifica el lab. Premissa "múltiples labs" del handoff §3 desmentida.
- ✅ Via A: `num_planned_dpsh` ES, `building_category` (apòstrof+ES), `num_planned_sondeig` (25 juny).
- ✅ A2 (ACCEPTACIO) — DESCARTAT: era un no-op (ACCEPTACIO no s'ignora; premissa desmentida 24 juny).
- ✅ A8 — superat (`num_dpsh_tests` ja ve de l'Excel, ja correcte).

## Blockers actius
- Confirmació d'Eva del pull de 2026-06-08 (bugs 1+2+render).

## Wizard
Producció: `http://localhost:8765` a `C:\g3dt-ia` (ordinador Eva).
Dev: worktree `clients/g3dt-fix/` — `fix/pipeline-routing`.

## Lectura per a la propera sessió
1. `docs/DECISION-LOG.md` — entrada 2026-06-25 (B) (A3 GTL/lab) + 2026-06-25 (Via A) + 2026-06-24 (fix NIF).
2. `docs/ANALISI-PIPELINE-DEBUG-VACARISSES.md §9` — accions A1, A4–A7 (A2/A3/A8 tancades).
   ⚠ §3/§7 deien "múltiples labs / hardcode incorrecte" → DESMENTIT: lab sempre TPS `B64803075`.
