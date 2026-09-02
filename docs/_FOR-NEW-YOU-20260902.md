# FOR NEW YOU — 2026-09-02 — Adreces i municipi tancades i pujades; demà toca LA MESURA

**Escrit:** 2026-09-01, nit · **Per a:** la sessió que farà la **mesura de qualitat dels 8 projectes**.

**Recap:** la sessió d'ahir es va obrir per analitzar la proposta del Josep sobre adreces i municipi
(`docs/PROPOSTA-JOSEP-ADRECES-I-MUNICIPI-2026-09-01.md`, anotada literalment i deixada sense analitzar a
posta). En van sortir **8 decisions i 5 peces implementades** el mateix vespre, **7 commits** i el **primer
push d'aquesta branca** a `origin`. La mesura de qualitat —que era el motiu original de la sessió del matí— es
va posposar dues vegades a posta i **ara sí que és la feina**.

## 1. Ordre de lectura

1. Aquest document.
2. **`docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md`** — el disseny sencer: 8 decisions, les 5 peces amb les
   mesures abans/després, i §8 amb el que queda obert. És la font de veritat de tot el que es va tocar.
3. `STATUS.md`, punt `0e` — resum executable de les 5 peces.
4. `docs/DECISION-LOG.md`, entrada **2026-09-01 (nit)** — els «per què», les alternatives rebutjades i les
   limitacions conegudes.
5. `MEMORY.md`: `project_address_interpretation_llm_proposal` (actualitzada ahir),
   `feedback_measure_baseline_before_coding`, `feedback_full_report_341_variables_goal`,
   `feedback_no_pull_eva_success_criterion`, `reference_compare_tables_vs_eva_harness`,
   `project_judge_noise_band`.
6. `docs/_FOR-NEW-YOU-20260901-2000.md` (el d'abans-d'ahir) — §3 i §4 segueixen vigents.

## 2. Estat del repositori — llegeix això abans de tocar git

**L'arbre de treball és NET i la branca està pujada.** Res a recuperar, res pendent.

```
experiment/nivell-a-2026-08 → 6e1c624 = origin/experiment/nivell-a-2026-08 (upstream configurat)
```

Els 7 commits de la sessió (`git log --oneline 12328ae..HEAD`):

| SHA | Què |
|---|---|
| `49704d6` | lectura: padró, `resolve_via`, `address_struct`, veto geomètric |
| `6763bbf` | web/UI: avisos delta-sync, fuites entre projectes, motiu dels blancs al popup |
| `49dd283` | docs: disseny, DECISION-LOG, CLAUDE.md, skill, STATUS |
| `6386cf6` | reference-material: retira 119 `mined_images`, afegeix `photo_selection.json` de Rubí |
| `18311c4` | docs/diagnostics (9 informes de juny ençà) |
| `0e3c7df` | mesures: text del holdout-v16 (1,3 MB), renders de pàgina ignorats |
| `6e1c624` | gitignore: regla per defecte per als projectes de reference-material |

- **Mai `git stash`** — la pila és compartida amb els altres 5 worktrees.
- `main` i `production/g3dt-eva-v1` **no s'han tocat**. Cap merge fet.
- **Mai proposar pull/merge/desplegament a l'Eva** (`feedback_no_pull_eva_success_criterion`).

## 3. Regles interpretatives (no evidents llegint el codi)

- **La suite dona `2000 passed / 32 failed`** amb `.venv/bin/python -m pytest tests/ -q`. Les 32 són el baseline
  preexistent, però **NO totes tenen la mateixa causa**, i tractar-les com un bloc amaga coses:
  - **19 anomenen Anciles, Vilanova o Alcoletge** — els projectes el material dels quals no és a
    `reference-material/` (només hi ha `eva_reference_values.json`). Fallen per falta de fitxers.
  - **13 tenen causa pròpia.** Comprovades el 2026-09-01: `test_ai_pipeline_ranking_api` (7) i
    `test_ai_pipeline_trace` (1) donen **HTTP 404 «Not Found»** (la ruta no està registrada, res a veure amb
    fitxers); `test_bearing_stratum_n20_regression::test_bell_lloc_bearing_idx_and_n20` dona **N20=34,3 quan
    n'espera 49,8 en un projecte amb el material complet** — això és una discrepància de CÀLCUL i mereix
    mirada pròpia; `test_groq_miner::TestCache::test_cache_hit` és un miss de cache; i les tres
    `TestSmartScanRoleFiles` són genèriques.
  - **No diguis «les 32 preexistents» com si fossin inofensives.** Almenys una és un número geotècnic que no
    quadra i una altra és una ruta d'API trencada, tapades per anys d'agregar-les al mateix sac.
- **Corre pytest des de `tests/`, mai des de l'arrel** (13 errors de recol·lecció que no són tests reals).
- **`test_lectura_runner.py::test_telemetry_*` són inestables sota càrrega** (subprocessos amb timeout 2 s).
  Poden pujar el recompte a 34. No són regressió.
- **Compara SEMPRE els noms de test, no el recompte.** Ahir vaig capturar dues suites amb `| tail -N` i els
  fitxers van quedar truncats: el diff era inservible i vaig haver de repetir la suite. Fes
  `pytest tests/ -q --tb=no -rf > fitxer.txt` **sense pipe**, i després compara conjunts de noms.
- **Dos harnesses, no els confonguis** (`reference_compare_tables_vs_eva_harness`):
  - `scripts/compare_tables_vs_eva.py` = **qualitat de l'informe** (`.docx` generat vs el signat de l'Eva).
  - `docs/wizard-headless/fase0-acceptacio/compare_consolida.py` = **qualitat de la lectura**
    (`_decisions.json` vs l'or; l'objectiu que mana és **0 erronis-amb-confiança**).
- **La franja de soroll del jutge és de 2,8 pp** entre execucions idèntiques (`project_judge_noise_band`):
  compara **flips de variable**, mai el titular d'un sol sweep.
- **Abans de citar cap número, grep `name resolution` / `Connection error`** al log
  (`feedback_sweep_dns_contamination`): les fallades de DNS contaminen els resultats en silenci.

## 4. Supòsits estructurals que no s'han de desfer

| On | Què | Per què |
|---|---|---|
| `cadastre_reader.resolve_portal` | filtra `(pnp, plp)` **exactes**, mai el més proper | 18A i 18B són dos edificis amb dos propietaris. Delegar-hi reprodueix un bug conegut de la via B |
| `address_struct` (docstring, regla 1) | les alternatives valen a l'**eix via/municipi**, mai a l'eix **portal** | és el mecanisme concret que impedeix ressuscitar el bug de dalt. Hi ha test que ho fixa |
| `cadastre_reader.resolve_via` | totes les capes exigeixen **un sol guanyador**; empat = blanc | amb 835 carrers, triar el «millor» a l'atzar dona la parcel·la d'un altre |
| `municipis.lookup` | **sense capa difusa**, a posta | `CATELLAR` (errata real del corpus) ha de quedar sense confirmar, no acostar-se a `Castellar del Vallès` |
| `g3_templates._plan_cost_municipi_confianca` | el padró **només afegeix dubte, mai en treu**; i el padró i `_municipi_corroborat` són guardes **independents, mana la del context** | pujar confiances mouria decisions correctes als 9 corpus. I que «X» sigui un municipi de debò no vol dir que sigui el d'AQUEST projecte |
| `address_struct.FLOOR_ORDINAL_RE` | **única** definició; `cadastre_reader` la importa | duplicar vocabulari d'adreces ja va costar car amb `COMPONENT_VALUE_ALIASES` |
| `cadastre_reader._veto_signal` | emet `value=None` **amb nota**; `decide()` la recull a la cel·la `no_trobat` i `review.html` la pinta | sense el missatge, l'Eva veu un blanc sense explicació i la conclusió que en treu és sobre el sistema. Requisit explícit del Josep |
| `geocode_coordinates.py`, `parcel_resolver.py`, `cadastre_adjacents.py` | **via B de producció**: llegir sí, modificar mai | per això el llindar de 500 carrers es resol a la via A i no allà |
| `automation/ai_pipeline/__init__.py` | ha de seguir **buit** | re-exportar provoca una cursa d'importació circular |

Els supòsits de `_FOR-NEW-YOU-20260901-2000.md` §4 segueixen **tots** dempeus.

## 5. Procediments

```bash
git branch --show-current        # experiment/nivell-a-2026-08 (in-place a g3dt-prod/)
git status --porcelain | wc -l   # ha de donar 0

.venv/bin/python -m pytest tests/ -q --tb=no -rf > /tmp/suite.txt   # ~3 min, SENSE pipe
.venv/bin/python -m pytest tests/test_lectura_via_resolver.py -q    # dirigits, < 1 s

# Lectura d'un projecte (el patró; el driver d'ahir vivia al scratchpad i s'ha perdut):
#   automation.lectura.runner.run_lectura(project_path, out_dir=..., on_event=...)
#   config de producció: sonnet, --effort xhigh, concurrència 2, preext, consolida auto
```

- **`.venv/bin/python` sempre**; `cd` al worktree `g3dt-prod/` primer (el cwd fa ombra al `PYTHONPATH`).
- **Workspaces E2E: `~/g3dt-e2e/projectes/` té els 8 projectes.** `reference-material/` d'aquest worktree NO té
  els fitxers reals de tots (només artefactes `validation/`) — vegeu §3 sobre les 32 fallades.
- **Cache real: `/home/josep/g3dt-prod-cache/`** (`G3DT_CACHE_DIR`), 15 MB, **no** `~/.g3dt/cache/`. Hi ha
  cachejades les consultes noves de Cadastre (`vies_*`, `muni_*`, `dnploc_*`, `wfs_*`), TTL 90 dies.
- **Mai escriure a `/mnt/c`.**
- `rtk` reescriu `grep`/`find`: `find … -not` i `\|` fallen → `rtk proxy find …`. I `rtk grep` **trunca la
  sortida**: per a comptatges exactes, fes-ho amb Python.
- Determinisme en re-consolidacions: `G3DT_LECTURA_HTTP_SOURCES=""`.

## 6. Seqüència d'obertura suggerida

1. `git branch --show-current` + `git status --porcelain | wc -l` → branca correcta i **0 pendents**. Si hi ha
   canvis, algú ha treballat després; esbrina què abans de res.
2. `git log --oneline -1` → ha de ser `6e1c624`, i `git status -sb` ha de dir que està sincronitzat amb origin.
3. Suite completa → confirma `2000 passed / 32 failed` i que els **noms** són els de §3.
4. Llegeix `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md`, com a mínim §5.3, §4.1, §5.5 i §6.5 (les 5 peces) i
   §8 (el que queda obert).
5. **El N20 de Bell-lloc** (§8, tasca 0). És la primera feina per decisió del Josep, i abans de la mesura per
   un motiu pràctic: si el càlcul de la capacitat portant s'ha mogut, els números de la mesura naixerien
   caducats.
6. **Escriu els criteris de la mesura abans d'executar-la** (`feedback_measure_baseline_before_coding`): què
   compta com a OK, com a candidat i com a erroni-amb-confiança, i com es tracten Vilanova i Tulipa (§8).
7. Executa la mesura (§8, tasca 1).

## 7. Què NO fer

- **No et refiïs del recompte de fallades** d'una sola passada: compara noms, i recorda els 2 tests inestables.
- **No capturis la suite amb `| tail`**: el fitxer queda truncat i el diff és inservible.
- **No tornis a crear una llista local** de noms de camp, de tipus de via ni d'ordinals de pis: hi ha una sola
  definició de cadascuna i duplicar-les ja va costar un bug.
- **No posis normalització a `contract.py`** pensant que és la porta de producció. No ho és.
- **No toquis via B** (`geocode_coordinates`, `parcel_resolver`, `cadastre_adjacents`) mentre l'Eva hi treballi.
- **No proposis mai pull/merge/desplegament a l'Eva.**
- **No `git stash`**; **no `--model opus`** pensant que és Opus 4.8 (cal `claude-opus-4-8`).
- **No pugis els renders de pàgina** dels runs de mesura: ja hi ha regla al `.gitignore`
  (`docs/wizard-headless/mesures/runs/**/*.png`). Eren 97 dels 98 MB del holdout.

## 8. Tasques obertes, per ordre

0. **PRIMER DE TOT: el N20 de Bell-lloc.** Decisió del Josep en tancar la sessió del 2026-09-01.

   ```
   tests/test_bearing_stratum_n20_regression.py::test_bell_lloc_bearing_idx_and_n20
   → N20 = 34,3  quan n'espera ≈ 49,8   (−31 %, tolerància 1,0)
   ```

   **Per què no és «una de les 32 preexistents»:**
   - `_select_bearing_layer_idx(layers) == 1` **passa**. La divergència és dins de
     `automation/report_data.py::_bearing_stratum_n20` (l. 1064), no en la tria de capa (l. 968).
   - El test **no fa `skip`**: fa `pytest.skip` quan falten els fixtures, i Bell-lloc els té (93 fitxers al
     disc). O sigui que **s'executa de debò** i el número no quadra. No és un problema d'entorn.
   - El seu germà `test_alcoletge_bearing_idx_and_n20` **sí que fa skip** (falta el DPSH). Per tant Bell-lloc
     és **l'única cobertura viva d'aquest fitxer**, i és la que està vermella.
   - La seva pròpia capçalera explica per què existeix: *«the G.5-wire rollout almost shipped a −60 % N20
     regression on Bell-Lloc because the unit tests used synthetic profiles… so future refactors can't
     silently shift calibrated values that Eva's deviation matrix depends on.»* És a dir: **la guarda escrita
     per impedir exactament aquesta deriva és la que està fallant.**
   - N20 alimenta la capacitat portant, que és un número que **l'Eva signa**.

   **Per on començar:** `git log -L 1064,1120:automation/report_data.py` per veure quan es va moure;
   `docs/METODOLOGIA-EVA.md` és el source-of-truth dels càlculs (**consulta'l abans de tocar res**); la
   memòria `implementation_status_calcs` té la matriu de desviacions contra els informes de l'Eva.

   **No el reparis a corre-cuita.** Primer esbrina si el que ha canviat és el càlcul o el valor esperat, i
   compara contra l'informe signat de Bell-lloc, no contra el test.

1. **LA MESURA DE QUALITAT DELS 8 PROJECTES** — Hold-out headless sobre codi ja reparat:
   - per projecte: **% camps bé / % popup (candidats) / % blanc / erronis-amb-confiança / minuts**;
   - `scripts/compare_tables_vs_eva.py` contra els informes signats de l'Eva;
   - **llindars pactats: OK ≥ 80 %, candidats ≤ 20 %, ERR = 0.**
   - **Línia base de temps** (codi ANTERIOR a les correccions, per comparar): Castellar **27,8 min**,
     Linyola **41,9 min**, amb la config de producció.
   - Els artefactes del hold-out d'ahir són a `docs/wizard-headless/mesures/runs/2026-09-01-holdout-v16/`
     (text versionat; els PNG no).
   - **NO cal copiar cap material del Windows del Josep.** Comprovat el 2026-09-01:
     `~/g3dt-e2e/projectes/` ja té els **8 projectes complets** (Anciles 47 fitxers, Vilanova 47,
     Alcoletge 37), i la veritat d'Eva per al comparador ja és **versionada** a
     `docs/golden-read-taules/_eva_truth/` (7 JSON transcrits a mà, amb taules i files reals:
     alcoletge 10 taules/28 files, anciles 9/32, castellar 11/28, bell-lloc 11/26, linyola 10/28,
     rubi 10/24). `reference-material/` és una altra cosa: hi llegeixen els TESTS, no la mesura
     (`feedback_windows_folders`).
   - **Dos forats reals de veritat d'Eva, que copiar fitxers NO arregla:**
     - **Vilanova**: `_eva_truth/vilanova.json` és un stub amb `status: "n/a per a la metrica ERR"`. El PDF
       signat **no conté el cos amb les taules resum** (només caràtula, base de càlcul, fulls DPSH d'annex i
       figures FreeHand) i **no existeix cap `.doc`/`.docx`**. Les cel·les que hi ha vénen dels annexos, que
       és la mateixa font que llegeix l'agent: **circular, serveix per a consistència, no per validar**. Si
       l'Eva té el `.doc` d'aquest informe, això canvia — és una pregunta per a ella, no una còpia.
     - **Tulipa/Cerdanyola**: no té cap fitxer a `_eva_truth/` (7 JSON per a 8 projectes).
   - Per tant la mesura sortirà comparable per a **6 projectes**, amb Vilanova com a consistència i Tulipa
     sense veritat. **Digues-ho al capdavant dels resultats**, no com a nota al peu.
2. **Decisions obertes del disseny** (§8 del disseny), totes petites i totes del Josep:
   - afegir **Osca** al padró? Anciles és de Benasc (Osca) i avui cau al bucle en línia, que funciona.
   - emetre la **forma oficial llarga** del municipi com a candidat competidor, no només com a nota.
   - el **llindar de 10 m** del veto: criteri de judici, a revisar amb dades de més projectes.
   - **quants exemples** calen al prompt del skill perquè `street_address_struct` surti estable (n'hi ha 3).
   - el veto de punts, ¿també per a `referencia_catastral` o només per a `superficie_parcela`?
3. **38 sortides generades ja versionades** (`*_generated.docx`, `AUDIT_VISUAL`, còpies a `PDF/`). El
   `.gitignore` nou impedeix que n'entrin de noves, però aquestes hi segueixen. Treure-les és
   `git rm --cached`, i **abans cal comprovar** si `reference_extractor` o `compare_tables_vs_eva` depenen dels
   PDFs de `PDF/ANNEXES/`.
4. Deute P3 de `docs/audit/CODE-REVIEW-BRANCA-2026-09-01.md`, Fase 16 (E2E dels tres botons) i Fase 17
   (Windows presencial).

## 9. Guanys que no sortiran a cap mètrica

- **El cas emblemàtic del Josep es resol sense LLM.** «11 de Setembre» → `ONZE DE SETEMBRE` surt de
  canonicalitzar els nombres (ca/es, 1-31), que és determinista — i de propina dona el `tipus_via` correcte: a
  Bell-lloc és una **plaça**, no un carrer. Inventar variants del nom no ho hauria donat mai.
- **El llindar de 500 carrers tapava una capa perillosa, no només una de mancant.** A Castellar (per sota del
  llindar) la recuperació de via B tornava `POL 011 FABRICA NOVA` per «11 de Setembre»; només la guarda de 0,85
  ho aturava. A Rubí (per damunt) no hi havia ni recuperació ni error: silenci.
- **Anciles no és un municipi** — és un llogaret de Benasc (Osca), confirmat pel Josep. Fins ahir sortia de
  PLAN_COST amb la mateixa confiança que `Linyola`.
- **136 municipis catalans porten l'article a l'altra banda** entre INE (`Ametlla del Vallès, L'`) i Cadastre
  (`L' AMETLLA DEL VALLES`). Sense tractar-ho, un de cada set hauria fallat en silenci.
- **Tres de les vuit decisions van néixer d'un error propi que va caçar un test** (el `11` de dos caràcters que
  passava per abreviatura; el marge difús arbitrari; el padró posat per davant de la corroboració pel context).
  En aquest projecte, la bateria negativa val més que la positiva.
- **El `.gitignore` no tenia cap regla per defecte per a `reference-material/`** i les úniques que hi havia
  apuntaven a carpetes renombrades feia mesos. Per això quatre projectes tenien 227 fitxers de material de
  client versionats sense que ningú ho hagués decidit. Ara un projecte nou entra ignorat excepte `validation/`.
