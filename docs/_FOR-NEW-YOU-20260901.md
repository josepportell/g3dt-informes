# FOR NEW YOU — 2026-09-01 — `PLA-PENDENTS-0B-0C-0D` tancat; següent és Fase 16 + preguntes a l'Eva

**Escrit:** 2026-08-31, nit · **Per a:** la sessió que continua després del tancament del pla 0b/0c/0d.
**Recap:** aquesta sessió (continuació de dues anteriors del mateix dia) va implementar Fix D (Cadastre
multi-portal, commit `349ecca`) i Fix E (Bell-lloc, capa de cobertura, commit `2486a53`), verificar totes dues amb
dades reals (API del Cadastre en viu, re-lectura LLM real del tall de Bell-lloc) i escriure tota la documentació de
tancament (commit `c2bef1e`). **El pla sencer (F/A/B/C/D/E + docs) està tancat.** No queda cap fix pendent d'aquest
pla — el que ve ara és treball nou (Fase 16, preguntes a l'Eva), no continuació d'aquest.

## 1. Ordre de lectura

1. Aquest document.
2. `docs/DECISION-LOG.md`, entrada **`## 2026-08-31 — PLA-PENDENTS-0B-0C-0D tancat`** (l'última del fitxer): les 7
   decisions arquitectòniques amb el "per què" complet — llegeix-la abans de tocar `cadastre_reader.py` o el bloc
   `soil_levels` de `consolidate.py` una altra vegada.
3. `STATUS.md` L.259-289 (0b/0c/0d, ara "RESOLT") i la capçalera (L.2-6).
4. `docs/PREGUNTES-EVA-PENDENTS.md` — 4 preguntes noves/actualitzades (3, 8, 9, 10) que cal enviar a l'Eva.
5. `MEMORY.md`: `project_pla_0b0c0d_not_implemented_decisions_2026-08-31` (ara marcada CLOSED),
   `reference_cadastre_not_truth_for_parcel_area`, `project_groq_residues_wrong_values_pending`,
   `project_soil_levels_gold_vs_pas3b_open` — totes quatre actualitzades avui amb l'estat final.
6. Si continues cap a la Fase 16: `docs/PLA-PENDENTS-0B-0C-0D-2026-08-26.md` §10 (acceptació) ja complerta; la Fase
   16 pròpiament no té doc propi encara — mira l'últim handoff previ al pla (`docs/_FOR-NEW-YOU-20260826-2005.md` o
   similar) per context de "els tres botons".

## 2. Fet en aquesta sessió (i les dues anteriors del mateix dia)

| Fix | Què | Commit |
|---|---|---|
| F | Comparador d'or v3: verdictes `BUIT`, `CAUTELA candidats disjunts`, `FORA` | `3694694` |
| A | `value_key`: dates amb `fullmatch`, guió entre dígits = interval | `d6aa855` |
| B | Or de Castellar `soil_levels[1].a` en dialecte v2 | `e8d1cc8` |
| C | Groq: `lab_company` fora + cap probe de mapa/foto emet superfícies | `a423f6a` |
| D | Lector Cadastre multi-portal (`automation/lectura/cadastre_reader.py`, nou) | `349ecca` |
| E | Bell-lloc: capa de cobertura des de la llegenda del tall (skill v1.6 + E2/E2b) | `2486a53` |
| Docs | DECISION-LOG, STATUS, PREGUNTES-EVA, `_RESULTATS.md` ×2, session log | `c2bef1e` |

Suite: **1640 passed / 32 failed** (els mateixos 32 coneguts: SmartScan, ai_pipeline, fileminer Anciles,
`test_groq_miner::TestCache::test_cache_hit`).

## 3. Regles interpretatives noves (apreses avui)

- **`RANK["ERR"] == RANK["ALERTA"] == 2`** al harness (`fase12-consolida/harness.py`): si un fix relabel·la un `ERR`
  com a `ALERTA` (o viceversa), NO és una regressió — és la mateixa severitat. Comprova sempre el diff línia a línia
  abans de concloure que un fix n'ha trencat un altre (així es va descobrir que `sonnet-c3-v13` no havia empitjorat
  amb Fix E: `ERR`→`ALERTA` en una cel·la, `BUIT`→`OK` en una altra, net positiu).
- **`_row_sort_key("soil_levels")` sempre posa `"cover"` primer** (`(0,0,"")`), abans de `nivell1`, `nivell2`, etc.
  Per això `rows_out[0]` és sempre la fila de cobertura quan n'hi ha una, i `rows_out[1]` és sempre el primer nivell
  numerat — el bloc E2/E2b de `consolidate.py` en depèn directament (`keys[0] == "cover"`).
- **El Cadastre real distingeix `lrcdnp.rcdnp[]` (llista) de `bico.bi` (objecte)** segons si hi ha 1 o >1 portal amb
  el mateix número — apreso al Fix D, documentat a `cadastre_reader._extract_hits()`. Si un portal sol sembla no
  trobar resposta, comprova primer si el codi mira `lrcdnp` quan la resposta real ve com a `bico`.
- **`claude -p` amb `--effort xhigh` (el defecte del runner) sobre un sol document triga ~2-4 min**, no segons.
  L'estimació del pla (2-4 min) va encertar (2m24s real). No confonguis això amb un penjament.

## 4. Supòsits que aguanten el pes (no desfer)

| On | Què | Per què |
|---|---|---|
| `cadastre_reader.py::resolve_portal` | filtra `(pnp, plp)` EXACTES, mai delega al més proper | `geocode_coordinates._pick_nearest_rc_from_numerero` (18B→18A) és un bug conegut de la via B; delegar-hi el reproduiria |
| `cadastre_reader.py::parcel_area_and_polygon` | usa `cp:areaValue` oficial del WFS, mai `shapely.Polygon.area` | shapely arrodoneix 441→440,75…; l'oficial suma exacte a 1284 |
| `consolidate.py` bloc `soil_levels` | E2b fixa la cobertura a `segur "0,00"` (no `candidats`) | decisió explícita del Josep, preguntada en viu amb `AskUserQuestion` — no la tornis a preguntar |
| `consolidate.py` bloc `soil_levels` | E2 només dispara si `keys[0]=="cover"` I `cover.a` és `no_trobat` I el nivell 1 arrenca a `segur` ≤0,05 | evita disparar sobre Castellar (cobertura ja té `a`) o sobre files profundes sense relació amb la superfície |
| `consolidate.py` `order` | `referencia_catastral`/`superficie_parcela` són SEMPRE els 2 últims camps processats | `cadastre_portal_signals` llegeix `decided["street_address"]`/`["municipality"]`, que han d'existir ja |
| `docs/golden-read/.../_decisions.json` Castellar | `fora_carpeta` és una ANOTACIÓ, no canvia `status`/`value` | el comparador (`compare_consolida.verdict()`) el llegeix per emetre `FORA` en comptes d'`ALERTA` |
| via B (`automation/ai_pipeline/`, `web/vision_groq.py`, `automation/auto_extractor.py`, `web/vision_fast.py`, `automation/geocode_coordinates.py`, `automation/parcel_resolver.py`, `automation/cadastre_adjacents.py`) | es pot importar, mai modificar | codi de producció que l'Eva fa servir cada dia; verificat `git diff --stat` buit després de tot el pla |

## 5. Procediments

```bash
git branch --show-current      # experiment/nivell-a-2026-08 (in-place a g3dt-prod/)
git log --oneline -3           # c2bef1e (docs) ha de ser HEAD

.venv/bin/python -m pytest tests/ -q -p no:cacheprovider          # ~4 min → 1640 passed / 32 failed
.venv/bin/python docs/wizard-headless/fase12-consolida/harness.py --write /tmp/.../scratchpad/base
# Castellar (4 jocs): FORA x2 (referencia_catastral, superficie_parcela); Bell-lloc: 0 ALERTA

# Cache del Cadastre (Fix D) — TTL 90 dies, no cal netejar-la sovint:
.venv/bin/python -c "from automation import config; print(config.cache_dir('cadastre_portals'))"

# Re-llegir un sol document amb el skill (com es va fer per a Fix E §8.4):
claude -p "/g3dt-llegir-projecte \"<projecte>\" --only \"<path relatiu>\" --inventory \"<inventory.json>\" --out \"<out_dir>\"" \
  --permission-mode bypassPermissions --model sonnet --effort xhigh --output-format json
```

- `.venv/bin/python` sempre; `cd` al worktree `g3dt-prod/` (el cwd fa ombra al `PYTHONPATH`).
- `rtk` reescriu `grep`/`find`: `find … -not` i `\|` fallen → `rtk proxy find …`. `unzip` no existeix.
- Cache dir real d'aquest entorn: `/home/josep/g3dt-prod-cache/` (`G3DT_CACHE_DIR`), NOT `~/.g3dt/cache/`.
- Workspace E2E: `~/g3dt-e2e/projectes/` (Castellar i Bell-lloc). **Mai** escriure a `/mnt/c`.

## 6. Seqüència d'obertura suggerida

1. `git branch --show-current` + `git log --oneline -3` + suite completa → confirma `1640 passed / 32 failed`
   sobre `c2bef1e`. Si no quadra, atura't i esbrina per què.
2. Llegeix `docs/DECISION-LOG.md` entrada 2026-08-31 sencera (és llarga però és la font de veritat de per què cada
   decisió del pla és com és).
3. Decideix amb el Josep: **enviar les preguntes 3+8+9+10 a l'Eva ara**, o esperar a tenir més preguntes acumulades?
   (`docs/PREGUNTES-EVA-PENDENTS.md` ja les té redactades, només falta enviar-les.)
4. Si toca Fase 16: revisa l'última mesura de temps coneguda (`docs/DECISION-LOG.md` 2026-08-26) i re-mesura amb
   Cadastre ON per defecte — anota que la primera consolidació de cada projecte farà ara crides HTTP noves
   (DNPLOC+WFS) que no hi eren abans del Fix D.
5. Si es reprèn l'objectiu de fons (grup B + resta de les 341 variables, `feedback_full_report_341_variables_goal`):
   no hi ha pla escrit encara per a això — caldrà escriure'n un abans d'implementar.

## 7. Què NO fer

- **No tornar a preguntar l'E2b** (segur vs candidats) — ja decidit, és `segur`, documentat a 3 llocs (DECISION-LOG,
  memòria, `consolidate.py` mateix).
- **No reescriure `_HTTP_FIELD_SOURCES` per tornar-hi `referencia_catastral`/`superficie_parcela`** — aquell
  mecanisme (via `_auto_result.json`) queda deliberadament eliminat per a aquests dos camps.
- **No canviar l'ordre de `order` a `consolidate_python`** perquè els dos camps de Cadastre deixin de ser els
  últims — trencaria la lectura de `decided["street_address"]`/`["municipality"]`.
- **No editar l'or de Bell-lloc a mà** (les cel·les gràfiques −0,30/−0,4 són lectura humana legítima; la pregunta
  3/8 decideix, no un edit directe).
- **No `git stash`** (pila compartida entre worktrees); **no `--model opus`** pensant que és Opus 4.8 (és Opus 5,
  cal `claude-opus-4-8`).
- **Mai proposar pull/merge/desplegament a l'Eva** (memòria `feedback_no_pull_eva_success_criterion`).
- **No confondre `RANK["ERR"]`/`RANK["ALERTA"]`** com a coses diferents en severitat — són iguals (2) al harness.

## 8. Tasques obertes (per ordre)

1. Enviar a l'Eva les preguntes 3+8+9+10 (`docs/PREGUNTES-EVA-PENDENTS.md`) — decisió del Josep sobre quan.
2. **Fase 16** — E2E dels tres botons amb temps remesurats, ara amb Cadastre ON per defecte (primera consolidació
   de cada projecte farà crides HTTP noves; anotar-ho si es mesura).
3. Fase 17 (Windows presencial), sense canvis respecte als handoffs anteriors.
4. Objectiu de fons: grup B (càlculs) i la resta de les 341 variables de l'informe — sense pla escrit encara.

## 9. Guanys ocults d'aquesta sessió

- La verificació en viu de Fix D (API real del Cadastre) i de Fix E (re-lectura LLM real, no només el corpus
  sintètic) va confirmar que els dos fixos funcionen amb dades reals, no només amb els tests. Això és més fort que
  "els tests passen": el `source_md5` idèntic de la re-lectura de Bell-lloc demostra que el mateix document, llegit
  amb el skill v1.6, canvia de comportament exactament com preveia el pla.
- El descobriment que `sonnet-c3-v13` (dataset de 2026-08-24) ja tenia un `ERR` pre-existent abans de tocar Fix E
  evita que una futura sessió es preocupi en veure "ALERTA" en aquell dataset concret — ja està explicat i no és
  una regressió.
