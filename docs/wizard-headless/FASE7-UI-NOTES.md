# Fase 7 — UI (review.html) — notes d'implementació

Implementa `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` §8 + §9 Fase 7 sobre
`templates/validation/review.html` (9002 → 10000 línies). Cap fitxer Python tocat. Sense commit
(fet pel Josep).

## Blocs inserits (línies aproximades, POST-edició)

| Bloc | Línies | Contingut |
|---|---|---|
| CSS | 1621-1817 | `.estat-badge` (3 estats + `.mini` + `.degraded`), `.lectura-degraded-banner`, `#lectura-progress`, `#lectura-extra-fields` + `.lectura-extra-row`, `.lectura-table*`, `.n30-chip*`, `.lectura-select-lit`, `.lectura-popup*` |
| HTML — progrés/extra | 2490-2492 | `#lectura-progress` + `#lectura-extra-fields` al principi de `wizardForm` |
| HTML — taules | 2660-2670 | Grup `#lectura-tables-group` amb `#lectura-dpsh-tables` + `#lectura-sondeig-tables`, abans de "Group 3: Parametres" |
| Hook (a) | ~4835-4841 | `loadProjectData()`: `if (await openLecturaStream(selectedProject)) return;` abans del `new EventSource(prefills-stream)` |
| Hook (b) | ~4893-4900 | Handler `prefills` **existent** (via B): crida defensiva `_lecturaUnwrap` + `applyLecturaDecisions` després de `showWizardContent()` |
| JS nou | 9225-9996 | Bloc autocontingut `/* === LECTURA HEADLESS (Fase 7) === */` |

## Funcions definides (bloc nou)

- `LECTURA_MAPPING` — 12 claus escalars → id de camp del wizard (§8.3, confirmat amb grep `id="src-…"`)
- `LECTURA_EXTRA_KEYS` — 10 claus sense camp (expedient, field_date, lab_*, cte_*, referencia_catastral, num_dpsh_tests) → etiqueta per a `#lectura-extra-fields`
- `lecturaState` = `{decisions, degraded, selections}`
- `applyTemplatesFields(payload)` — TEMPS 1a, badge segur provisional
- `applyLecturaDecisions(decisions, degraded)` — escalars + dispara taules + extra-fields + banner degradat
- `showLecturaPopup(key, cell, anchor)` — extensió de `showAlternatives` (valor+font+cita+peu `rule`, o `sources_checked` si `no_trobat`)
- `renderLecturaTables(tables)` — dpsh_tests, sondeig_tests, soil_levels (litologia `<select>`), spt_ma_tests (n30 chips), superficie_construida (badge al camp existent)
- `updateLecturaProgress(evt, payload)` — text a `#lectura-progress`
- `getLecturaSelections()` — accessor de `lecturaState.selections` (consum previst Fase 8)
- `openLecturaStream(project)` — `Promise<boolean>`; obre `/api/lectura-stream/{p}`, escolta tot el vocabulari nou + reutilitza el vocabulari existent (`step`/`file`/`source`/`groq`/`prefills`/`cancelled`/`error_event`); `true` si l'endpoint ha respost (≥1 event), `false` si cal caure al camí existent
- Helpers privats `_lectura*` (unwrap, truncate, cell display, badge class/label, table builder, litologia select, n30 cell)

## Contracte real vs. instruccions originals (verificat consultant `web/lectura_service.py` en LECTURA, no edició)

- L'event `prefills` porta `_lectura` **embolcallat**: `{value: {decisions, degraded, per_doc}, source: "system"}`,
  no pla com deia el prompt inicial. `_lecturaUnwrap()` gestiona les dues formes (`raw.value || raw`).
  Confirmat pel coordinador a mig treball; ja implementat així.
- L'event `decisions` del stream arriba **pla**: `{decisions, degraded, per_doc}`.
- `spt_ma_tests.rows[i]` té `registre` i `n30` com a **claus germanes** (no `n30.registre` niuat) — verificat
  amb el fixture real `docs/wizard-headless/fase0-acceptacio/taules_decisions.json`. `_lecturaN30Cell(rowKey, row)`
  llegeix `row.registre` i `row.n30` per separat.
- El backend (`web/lectura_service.py::MAPPING_DECISIONS_WIZARD`) ja mapeja **també** `lab_testing_company`,
  `lab_sample_id`, `lab_depth`, `lab_location`, `cte_edificacio`, `cte_sol` a camps reals de `merged` (badge
  estàndard `source-badge` ja els mostraria com a "lectura"). El contracte fixat per a aquesta fase els posa a
  `LECTURA_EXTRA_KEYS` (llista compacta, sense id de camp). **Redundància cosmètica coneguda, no bloquejant**:
  si el backend ja escriu aquests camps a `merged[wizard_key]`, sortiran DUES vegades (source-badge estàndard +
  fila a `#lectura-extra-fields`). No corregit aquí perquè el contracte de la Fase 7 estava fixat explícitament
  i no s'havia de tocar `web/*.py`. **A reconciliar a la Fase 8**: si `MAPPING_DECISIONS_WIZARD` es manté així,
  moure `lab_*`/`cte_*` de `LECTURA_EXTRA_KEYS` a `LECTURA_MAPPING`.

## Decisió d'UI no coberta pel disseny: pestanyes DPSH/Sondeig

El disseny (§8.2) i el prompt original assumeixen pestanyes `tab-dpsh` / `tab-sondeig` existents. **No existeixen**
a `review.html` actual: `availableTabs` només conté `smartscan, wizard, photos, explicacio, ai-pipeline` (+ `dev`,
`pipeline` en DEV_MODE). Hi ha branques mortes `currentTab === 'dpsh'|'sondeig'|'planol'` (~línia 3207) que fan
referència a un `dpshTestsContainer` que tampoc existeix a l'HTML — vestigis d'una UI anterior, mai netejats.
`ai-pipeline-content` és una pista *diferent* (Stage 1-5, ranking amb LLM) no relacionada amb aquesta feature.

**Decisió presa:** `#lectura-dpsh-tables` i `#lectura-sondeig-tables` viuen dins la pestanya **Wizard**, en un grup
nou "Lectura headless — assaigs de camp (DPSH / Sondeig)" abans del grup "Parametres". Documentat amb comentari
HTML al mateix punt d'inserció. **Pendent decisió Josep:** si val la pena netejar el codi mort `dpsh`/`sondeig`/
`planol` de `switchTab`/`renderCurrentTab`/`updateStatsForTab`, o crear pestanyes reals en una fase futura.

## Verificació de sintaxi

```
node --check <script extret> → SYNTAX OK
```
Extracció: únic bloc `<script>...</script>` del fitxer (337.957 caràcters), sense `src=`, cap a
`/tmp/.../scratchpad/review_main.js`, `node --check` net. Balanç `<div>`/`</div>` de tot el fitxer: 455/455.
Comprovat que no hi ha declaracions duplicades (`LECTURA_MAPPING`, `lecturaState`, cada funció nova, cada id
nou) amb `grep -c`.

## Checklist manual pendent (servidor dev + Bell-lloc)

- [ ] Amb `G3DT_USE_LECTURA_HEADLESS=false` (o endpoint inexistent): confirmar que `openLecturaStream` fa
      `bail()` en <2.5s i el flux legacy (`prefills-stream`) carrega igual que avui, 0 errors a consola.
- [ ] Amb el flag ON i un backend real/mock: `templates_fields` pinta camps blaus "lectura" abans que
      `decisions` arribi (badge amb títol "Provisional…").
- [ ] Event `decisions` (fixture `escalars_decisions.json` + `taules_decisions.json` combinats a mà si cal):
      camp `segur` → badge blau, popup amb 1+ candidats i `rule` al peu.
- [ ] Camp `candidats` (p.ex. `street_address`) → pre-omplert amb `candidates[0].value`, badge ambre "N
      candidats"; seleccionar un altre candidat al popup → camp queda verd (`source-badge.user`), input amb
      el valor triat.
- [ ] Camp `no_trobat` (si n'hi ha al fixture de prova) → buit, badge gris, popup amb `sources_checked` +
      missatge d'acció, sense cap ítem clicable de valor.
- [ ] `degraded: true` → tots els badges canvien a `.degraded` (ambre) + apareix banner sota `#lectura-progress`.
- [ ] Taula DPSH (`dpsh_tests`): una fila per punt, 5 columnes, mini-badge per cel·la, click obre popup.
- [ ] Taula Sondeig (`sondeig_tests`): columna SPT/TP/MA mostra comptes formatats (`"1 SPT / 0 MA"`).
- [ ] `soil_levels`: dropdown de litologia amb 2-3 opcions + "altre…" → mostra input de text lliure en
      seleccionar-lo; `lecturaState.selections['soil_levels.N.litologia']` s'actualitza.
- [ ] `spt_ma_tests.n30`: registre en monospace ("24/34/28/30"), chips ambre per cada candidat de suma, CAP
      chip pre-seleccionat; click marca `.selected` (verd) i escriu `lecturaState.selections['spt_ma_tests.N.n30']`.
- [ ] `superficie_construida`: badge nou al costat de `src-superficie_construida_m2`, popup amb
      `components`+`total` com a candidat.
- [ ] Event `cancelled` a mig stream nou: stepper s'amaga, cap error, `nbAfterCancel()` es crida si existeix.
- [ ] Tallar la xarxa a mig stream nou (ja `succeeded=true`): cau a `loadProjectDataFallback()` (fetch pla),
      igual que fa avui la via B.
- [ ] Reobrir un projecte ja carregat (re-selecció): cap badge duplicat (comprovar que
      `_lecturaRenderFieldBadge` reutilitza `[data-lectura-key]` en lloc d'afegir-ne un altre).
- [ ] Comprovar visualment que `#lectura-tables-group` no trenca el grid de la pestanya Wizard (classe
      `single-col` aplicada).

## Decisions d'UI preses sense confirmació explícita (per revisar)

1. Placement de les taules DPSH/Sondeig dins la pestanya Wizard (no hi ha pestanyes dedicades — veure secció
   anterior).
2. Timeout de detecció "stream nou no disponible" fixat a 2500 ms (heurística; no hi ha manera neta de llegir
   l'status HTTP d'un `EventSource` fallit). Si el TEMPS 1 real triga més de 2.5s a emetre el primer `step`,
   caurà erròniament al camí legacy — a validar amb temps reals a la Fase 8.
3. Mini-badges de taula usen etiquetes d'una lletra (`S`/`Nc`/`?`/`!`) per espai; el detall queda al `title`
   (hover) i al popup.
4. `lecturaState.selections` és només client-side (cap POST al backend) — explícitament "TODO backend a la
   Fase 8" per contracte.
5. superficie_construida mostra el badge nou però NO substitueix el valor del camp (el generador ja decideix
   format `components+total`, disseny §8.2) — només transparència via popup.
