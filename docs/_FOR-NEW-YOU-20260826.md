# FOR NEW YOU — 2026-08-26 — Comparador d'or v2 FET i revisat; preguntes a l'Eva consolidades; taula fases→Eva amb priorització per trams; següent: tram 1 (8b → 13 → capa vegetal → 14a → 15) quan el Josep ho digui

**Escrit:** 2026-08-26, 00:05 (final de la sessió del 25 nit) · **Per a:** la sessió del 26 d'agost o la següent.
**Recap:** el punt 1 del handoff 22:00 (normalitzadors del comparador d'or) s'ha fet sencer: `compare_consolida.py` v2 amb 95 tests, revisió
adversària Sonnet (7 troballes, 6 corregides, 1 decisió del Josep), fixture de Castellar revisat, llibre regenerat amb traçabilitat v1→v2 —
i el comparador nou ha destapat 2 erroni-amb-confiança reals que l'alineació per índex amagava. Després, a petició del Josep: registre únic de
preguntes a l'Eva, taula de treball «fases → què milloren → tipus de dada → què notaria l'Eva» i proposta de priorització per trams amb data de
reunió desconeguda. Commits sobre `7ae3065`: `dcda24f 4d135cd e315b64 0774416 6dfb634 71cef4f 8bcd77b` (+ aquest). Res pujat. Fases 11/13-17 NO començades.

## 1. Ordre de lectura (15 min)
1. Aquest document. 2. `docs/_TAULA-FASES-VS-EVA-2026-08-25.md` — resum compacte + **proposta de priorització per trams** (§«Proposta»): és el pla
de treball si el Josep diu «arrenca el tram 1». 3. `STATUS.md` (bloc «2026-08-25 nit (2)» i la línia de preguntes a l'Eva).
4. `docs/PREGUNTES-EVA-PENDENTS.md` (6 preguntes; sap què està bloquejat per ella). 5. `docs/DECISION-LOG.md` entrada «2026-08-25 (nit, 2)».
6. `docs/_FOR-NEW-YOU-20260825-2300.md` §3-§4 (regles i supòsits del comparador v2, vigents) i `_FOR-NEW-YOU-20260825-2200.md` §3-§6 (Fase 12, vigents).
7. `docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` §10 (fila 8b no hi és: viu a `fase8-e2e/_RESULTATS.md` punt 6) abans de tocar 13/14/15.
8. MEMORY.md: `project_via_a_claude_code_reader` (paràgraf «night, 2»), `feedback_building_type_close_match` (confirmació del 25), `feedback_no_pull_eva_success_criterion`.

## 2. Marc fixat pel Josep (25 nit) — no re-litigar
- **`building_type`: treure «entre mitgeres» (o «aïllat», o un article) = CLOSE.** Un revisor ho va marcar com a afluixament; el Josep ho confirma. No endurir-ho.
- La taula fases→Eva és **de treball, orientativa, no font de veritat**. No convertir-la en STATUS ni en pla formal; sí actualitzar-la si canvia l'ordre.
- Les urgències de la taula es donen per bones. Objectiu: **completar el màxim de fases abans que l'Eva torni de vacances** (data de reunió desconeguda: demà / setmana / la següent), **sense** esperar respostes seves.
- Vigents: no pull/merge a l'Eva; qualitat primer; objectiu 341 variables; Fable @xhigh quan el pla ho permeti (defecte codificat segueix `sonnet`).

## 3. Regles interpretatives noves (comparador v2)
- **Llegir el llibre amb el v2:** `LEDGER.md` porta 0 ERR de format; els ERR que queden són reals (`soil_levels[1].de` = 0,00 segur a `e2e-tarda-c2-solapat`
  i `sonnet-c3`, capa vegetal absorbida al nivell 1 → fons 0→1, `erroni_amb_confianca_fons_v1` conservat al `meta.json`) o vocabulari (`No indicat`, estricte a posta).
- **Files de taula per clau, no per índex.** Si un run té una sola fila de `soil_levels`, la capa vegetal de l'or surt ABSENT ×2-3 (honest) i el nivell 1 es compara amb el nivell 1.
- **Patró «nivell 1 des de 0,00»**: els perdoc v1.2/v1.3 i els runs LLM del 24-08 el tenen; els jocs v2 (Sonnet/Fable/Opus 4.8) no. Candidat a regla del Pas 3b
  (pregunta 3 a l'Eva); no codificar-la a `consolidate.py` sense resposta. Forat separat i codificable: Python deixa `no_trobat` les fondàries de la capa vegetal al joc Sonnet v2.
- **Fase 12 sota v2:** 0 erroni de fons als 3 jocs v2; el joc v1.3 en té 1 heretat de la lectura (la referència LLM el té igual, no és «per sota»).
- **Or de Castellar `sondeig_tests[0].cota` = `candidats`** [`-4 m` manuscrit | `570,90` | `570,9`]; −4,20 (informe Eva) no és a cap document → mai al fixture.
- **Sonnet com a revisor adversari funciona** (encàrrec: «troba parells que ara passin; executa cada cas»); com a dissenyador de normalitzadors o revisor d'or, no.

## 4. Supòsits que aguanten el pes (nous; els del 2300 §4 segueixen)
| On | Què | No desfer |
|---|---|---|
| `compare_consolida.py::row_key` | capa vegetal: senyal fort (`vegetal`, `no numerat`…) abans del número de nivell; `reblert/relleno/cobertura` només si no hi ha número | «Nivell 2 - Reblert» és n2, no capa; sense això `align_rows` aparella malament en silenci |
| `norm_floors` | retorna (nucli, indicador amb/sense soterrani llegit a TOTA la cadena) | `PB+2, amb soterrani` ≠ `PB+2 (sense soterrani)`; `PB + 1, sense soterrani` = `PB+1 (sense soterrani)` |
| `parse_numbers` | `_THOUSANDS_RE` `1.655,01` → 1655,01 (fixture real d'Anciles) | sense això, dos nombres → ERR fals |
| `strip_annot` | només ` -- nota` (doble guió) és anotació | ` - text` és contingut (`Refús - trencament de vareta`) |
| `close()` adreces | un costat amb portals i l'altre sense = False; cap portal als dos costats = igualtat sense contenció; vies `poligon/nau/partida/urb.` | `C/ Arbrells` vs `C/ Arbrells 18A-18B-20` era close per contenció |
| `_expand_de_a` | separa ` a ` només entre nombres | «Terra vegetal a la superfície a -1,20» no inventa cel·les |
| `meta.json` ×8 | `comparator_revision` (v1/v2) + `erroni_amb_confianca_fons_v1`; `annotate_meta.py` (scratchpad del 25, no versionat) era idempotent | `ledger.py` mostra els totals v1 a «Condicions»; si canvies el comparador, regenera TOT i anota |

## 5. Procediments
```bash
git branch --show-current            # → experiment/nivell-a-2026-08 (in-place a g3dt-prod/; esperat)
.venv/bin/python -m pytest tests/test_compare_consolida.py -q -p no:cacheprovider                    # 95, 0,2 s
.venv/bin/python -m pytest tests/test_lectura_runner.py tests/test_lectura_preext.py tests/test_lectura_service.py tests/test_lectura_jobs.py tests/test_lectura_contract.py tests/test_lectura_inventory.py tests/test_lectura_consolidate.py tests/test_compare_consolida.py -q -p no:cacheprovider   # 283 passed / 2 skipped, 35 s
# Regenerar el llibre després de tocar el comparador (ordre: txt dels runs → harness --write → restaurar out/*/_decisions.json → meta → ledger)
for d in docs/wizard-headless/mesures/runs/*/ docs/wizard-headless/mesures/runs/2026-08-25-preext-v2-c3/consolida2/; do for k in escalars taules; do .venv/bin/python docs/wizard-headless/fase0-acceptacio/compare_consolida.py $k "$d/_decisions.json" "3001621 CASTELLAR DEL VALLES" > "$d/$k.txt" 2>&1; done; done
.venv/bin/python docs/wizard-headless/fase12-consolida/harness.py --write docs/wizard-headless/fase12-consolida/out && git checkout -- docs/wizard-headless/fase12-consolida/out/*/_decisions.json   # només canvia elapsed_s
python3 docs/wizard-headless/mesures/ledger.py
# Sonda d'un parell: importlib sobre compare_consolida.py → cc.close(A, B, FIELD). Mirar un annex: scripts/render_clip.py PDF --page N --clip 0,0,1,1 --dpi 110 --out /tmp/x.png
```
- `unzip` no existeix a la màquina: variables de la plantilla amb `zipfile` (114 `{{ }}` a `templates/g3dt-jinja-template.docx`).
- `rtk` reescriu `grep`/`find`: `find … -not` i patrons amb `\|` dins de `grep` fallen → `rtk proxy find …` o patrons simples.
- Fitxers de treball del 25 a l'scratchpad de sessió (baseline v1, `annotate_meta.py`, `table.md`): no versionats, reconstruïbles.

## 6. Seqüència d'obertura suggerida
1. `git branch --show-current`, `git log --oneline -9` (ha d'acabar a `8bcd77b` + el commit d'aquest handoff), suite del comparador (95).
2. Llegir la §«Proposta de priorització» de `_TAULA-FASES-VS-EVA-2026-08-25.md` i esperar la resposta del Josep a les 3 preguntes que li vam deixar:
   (a) enviar o no les preguntes/carpetes a l'Eva en vacances; (b) pla/model; (c) arrencar el tram 1 començant per **8b**.
3. Si diu «tram 1»: 8b = seleccions de taula de la UI (`lecturaState.selections`, `review.html`) → backend → generador (`fase8-e2e/_RESULTATS.md` punt 6).
   Abans de codificar, mapa: on s'escriuen les seleccions, quin endpoint desa `user_data.json`, com el `ReportGenerator` consumeix `dpsh_tests`/`sondeig_tests`/`soil_levels`.
   Acceptació: informe generat des de `_decisions.json` de Castellar amb les taules de l'or (comparador docx `scripts/compare_tables_vs_eva.py` + `golden-read-taules/_eva_truth/`).
4. Després 13 (`auto_result` a disc + Cadastre/ICGC al consolidador + residus Groq; annex §7.1/§8) — envoltant a `wizard_service`, mai reescriptura de la via B.
5. Forat capa vegetal a `consolidate.py` (per què `de`/`a` de la capa surten `no_trobat` al joc `sonnet-v2-c3` quan `consolida2` les tenia): `harness.py --only sonnet-v2-c3` + `dbg` de senyals.
6. 14a (Preparar/Obrir + taula d'estat + attach) i 15 (toast + correu) — implementers Sonnet amb brief tancat; prohibició de `git stash` **amb el motiu**; revisar `.claude/sessions/` després.
7. Cada peça: suite completa (`tests/ -q`, línia base 32 failed coneguts, cap a lectura/preext/jobs), commit per peça, fila al llibre si toca temps.

## 7. Què NO fer
- No començar 11/13-17 sense el «sí» del Josep al tram 1 (ho va dir explícitament el 25).
- No afegir regles semàntiques a `consolidate.py` «a ull» (la del `de` del nivell 1 espera l'Eva); sí es pot arreglar el forat de la capa vegetal (és un senyal perdut, no una regla).
- No importar `consolidate.value_key` al comparador; no afluixar `building_type` més enllà del subconjunt ni endurir-lo (decisió Josep).
- No editar `.txt`/`LEDGER.md`/`meta.json` a mà; no tocar `erroni_amb_confianca_fons` sense conservar `_v1`.
- No posar −4,20 al fixture de Castellar. No reescriure `docs/golden-read*` (revisions puntuals només amb evidència + clau `revisio` + registre).
- Vigents: no pull/merge/desplegar a l'Eva; no `git stash`; no `docs/diagnostics/ai_pipeline_demo-*.md` ni `photo_selection.json` als commits; no `--model opus` pensant que és 4.8 (`claude-opus-4-8`).

## 8. Tasques obertes (ordre de la proposta de priorització)
1. **Decisions Josep:** enviar preguntes/carpetes a l'Eva; pla/model; arrencar tram 1.
2. **Tram 1:** 8b → 13 → forat capa vegetal → 14a → 15. Tall «aquesta setmana»: demo «Preparar, tanco, correu, obro, informe sencer amb les meves taules».
3. **Tram 2:** 11 + 14b (Actualitzar) → 16 (mesures per a la taula abans/després) → 17 preparat en sec al Windows del Josep (CLI natiu + login, checklist, neteja `_preext/` 72 MB/projecte, `--strict-mcp-config`).
4. **Tram 3 (quan l'Eva respongui):** càlculs (v4: Nb 0,83, n carbonatades, Qa topall, φ 28°) → regla `de` nivell 1 → multi-informe → narrativa (mesurar què reescriu) → fotos.
5. Hold-out amb carpetes noves de l'Eva quan arribin (només tenim Tulipa + logs; el 0 erroni és sobre el corpus 2025 que el skill anomena pel nom).
6. Pendents tècnics menors: `consolidate.value_key("1,5-1,75")` → data (latent); Bell-lloc complet al llibre; files d'effort; decisió `auto` vs `python` (2-3 projectes amb conflictes).

## 9. Guanys ocults
- L'instrument d'acceptació ja no fa soroll: a partir d'ara un ERR al llibre és un error de veritat (o vocabulari) — el criteri «erroni-amb-confiança de fons = 0» és mesurable sense llegir línia a línia.
- El v2 ha demostrat que l'alineació per índex podia amagar errors reals (2 runs) i forats del consolidador (capa vegetal): el que semblava «0 erroni» als runs antics no ho era del tot; els jocs v2 sí.
- `PREGUNTES-EVA-PENDENTS.md` fa visible que dos blocs sencers (càlculs, multi-informe) estan bloquejats per respostes, no per codi: la tasca més barata amb més palanca és enviar-les.
- La taula fases→Eva dona al Josep una manera de llegir «on som» en termes de què notaria ella, no de fases: cada tall del calendari té un estat demostrable definit.
