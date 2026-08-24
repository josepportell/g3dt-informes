# FOR NEW YOU — 2026-08-25 — Fase 9 feta (latència mesurada de veritat: 33 min reals, ~21 turns/doc); següent: Fase 10 (jobs) + experiment pre-extracció

**Escrit:** 2026-08-24, 23:30 · **Per a:** la sessió del 2026-08-25 (o la següent) que construeix els tres botons i prova la palanca de pre-extracció.
**Recap de la sessió:** del handoff de les 19:10 ("atacar la latència") s'ha passat a: diagnòstic amb dades (el cost fix NO és el CLI, és el
protocol del skill), decisió del Josep de **no escurçar la lectura sinó treure-la del camí crític** (tres botons), annex de disseny escrit,
runner instrumentat (`--model` + `--output-format json`), dues remesures de Castellar sol, llibre de mesures, i una sonda de turns que
assenyala la palanca següent. Commits: `2f4e3fd` (runner) → `5f324bc` (docs) sobre `1dab01d`.

## 1. Ordre de lectura (25 min)

1. Aquest document.
2. `STATUS.md` § "Wizard headless + UI de candidats" (paràgraf **Següent (decidit 2026-08-24 nit)** i **Fase 9 FETA**).
3. `docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` — el pla (§2 botons, §3 jobs, §4 delta-sync, §5 UI, §6 notificacions,
   §7 palanques, §8 residus Groq, §10 Fases 9-17, §12 decisions obertes). És el document de treball de les properes sessions.
4. `docs/wizard-headless/mesures/LEDGER.md` — la taula de mesures (3 runs) i `runs/*/meta.json` amb el judici ERR per ERR.
5. `docs/wizard-headless/fase8-e2e/_RESULTATS.md` § "Addendum 2026-08-24 (nit)" — xifres, qualitat, sonda, palanques.
6. `docs/wizard-headless/mesures/probes/2026-08-24-tall-stream-json/turns.md` — què fan els 20 turns d'un document.
7. `docs/DECISION-LOG.md` entrada "2026-08-24 (nit)".
8. `docs/_FOR-NEW-YOU-20260824-1910.md` §3 (supòsits estructurals de les Fases 0-8, tots vigents) i §7 (tasques que segueixen obertes).
9. MEMORY.md (memòria auto): `project_via_a_claude_code_reader` (actualitzada amb la descomposició de latència i la Fase 9).

## 2. Marc fixat pel Josep (2026-08-24 nit) — no re-litigar

- **La qualitat és el primer.** Cap palanca pot retallar el protocol del skill (Pas 0 context creuat, Pas 3 regles, verificació). Les palanques
  admissibles són les que canvien *quan* corre la lectura o *com d'eficient és el camí*, no *què mira* el model.
- **Només subscripció** (login del CLI). Cap clau API Anthropic a producció. El runner ja treu `ANTHROPIC_API_KEY` de l'entorn del fill.
- **≤ 1 projecte/dia** (objectiu 10/mes → 20/mes). No dissenyar per multi-projecte/dia; cua serial, concurrència 2-3 dins d'un job.
- **Tres botons**: *Fer un informe des de zero* · *Preparar informe "per demà"* · *Enllestir informe preparat* + taula d'estat dels jobs en
  llenguatge Eva (1/4 copiant… 2/4 llegint 7/17 ≈ 25 min restants… 3/4 consolidant… ✓ Preparat ahir 18:32 · 2 documents nous → Enllestir ≈ 8 min)
  + notificacions (toast Windows + correu).
- **Correu**: SMTP d'Eficients (l'SPF d'`eficients.cat` ja inclou Brevo; MX `mail.eficients.cat`), remitent dedicat (`g3dt@eficients.cat`), canal
  provisional fins que G3 doni un SMTP. **Telemetria a Eficients explícita (no BCC)**, mínima (expedient, durades, rc; noms de fitxer només en error),
  escrita al document de servei. Revisar encàrrec de tractament art. 28 amb G3.
- **Fable com a defecte només si la qualitat ho demana.** No ho demana (0 erroni-amb-confiança de fons a 3 runs amb Sonnet 5). Si es vol
  mesurar: `G3DT_LECTURA_MODEL=fable ~/g3dt-e2e/fase9/run.sh 3 fable-c3` → nova carpeta al llibre.
- **Guardar TOTES les mesures**: el Josep vol acabar amb una taula abans/després per a l'Eva. Cada canvi = una fila més al llibre, mai una xifra solta en un xat.

## 3. Regles interpretatives crítiques

- **El cost fix per document NO és arrencar el CLI.** Benchmark `claude -p "ok" --output-format json`: 4-14 s de paret, 2-3 s d'API (14 s = cwd repo
  + els 9 MCPs del Josep; 4,8 s = cwd buit + `--strict-mcp-config`). Els ~290 s de mediana per document són **≈ 21 turns** de Sonnet 5 (protocol
  del skill). "Prompt prim" val 5-10 s: no la venguis com a palanca de latència.
- **Els turns són estables entre runs (269 / 268)**; el que varia és el temps per turn i la consolidació (474-677 s, 49-72k tokens de sortida).
- **El temps és generació**: 306-342k tokens de sortida per projecte per 13 JSON de ~2k tokens. La sonda de `tall.pdf` (20 turns, 25,8k tokens)
  mostra ~75 % de raonament no visible i **5/15 usos d'eina construint-se l'eina** (`fitz`: pàgines, text, render sencer, meitats, localitzador),
  2 redundants (`ls/find`, `md5sum` que l'inventari ja té) i 2 de cerimònia d'escriptura (`os.replace`, rellegir). D'aquí la palanca de
  pre-extracció (§7 de sota).
- **La paret reconstruïda per planificació de llista és fiable** (`ledger.py::_wall_reconstructed`; run 2: 32 predits vs 33 reals). Amb la
  consolidació actual: conc. 2 ≈ 43 min, conc. 3 = 33 (mesurat), conc. 4 ≈ 26. No cal córrer conc. 4 per saber-ho.
- **Qualitat: erroni-amb-confiança de fons = 0 és l'única mètrica que mana**; els totals del comparador (`OK/CAUTELA/ALERTA/ERR/ABSENT`) es llegeixen
  línia per línia (`runs/*/escalars.txt`, `taules.txt`) i el judici va a `meta.json` → `quality_judgement.notes`. Tots els ERR dels 3 runs són format
  (`-4,0` vs `-4`; `1,0 - 1,2 m` vs `-1,00 a -1,20 m`; variants del mateix carrer).
- **Excés de confiança reproduïble (2/2 runs de la Fase 9):** `cota_referencia` puja a `segur` '570.90 msnm' amb una sola font (valor = preferit
  de l'or `+570,90`). Causa: el lector cec de l'annex DPSH no emet el "-4 m (respecte el carrer)" com a candidat escalar (només com a `cota_inici`
  de taula) → el consolidador veu 1 font i tanca. **Es resol amb guard determinista a `soft_normalize`** (segur amb 1 font i sense g3_templates
  ≥ 0,9 → candidats), no amb més model. També: `spt_ma_tests` amb 2 files (SPT-1 + MA1, mateix punt i fondària) = mateixa mostra amb 2 ids → fusió
  determinista punt+fondària. Totes dues a la Fase 12.
- **Conflicte skill vs or (pendent Josep/Eva):** cel·la `sondeig_tests[0].cota` — el skill (Pas 3b) diu relativa "-4 m", l'or
  (`docs/golden-read/3001621 CASTELLAR DEL VALLES/_decisions.json`) diu `segur` '570,90 msnm'. No és error del model; no toquis ni skill ni or
  sense decisió.
- **`elapsed_s` és `time.monotonic()`**: no compta suspensions de la màquina. Si el rellotge de paret (`ts_start`/`ts_end`) diu 78 min i
  `elapsed_s` 131 s, hi ha hagut suspensió/tall: marca el document a `meta.json` → `contaminated_docs` i la paret com a invàlida (run 1).
- **Subscripció**: 2 runs + sonda (~2,2 h de sessió Sonnet 5 en 2,5 h de paret) sense cap error de límit. El sostre real del pla no es coneix.

## 4. Supòsits estructurals que aguanten el pes (nous; els del handoff 19:10 §3 segueixen vigents)

| On | Què | No desfer |
|---|---|---|
| `runner.py::_load_config` `"model"` | `G3DT_LECTURA_MODEL`, defecte `sonnet` | a l'ordinador de l'Eva el defecte del CLI pot ser un altre; les mesures són amb `sonnet` |
| `runner.py::_run_claude` argv | `… --permission-mode bypassPermissions --model MODEL --output-format json` | el mock dels tests (`_MOCK_CLAUDE_TEMPLATE`) parseja `argv[1]` com a prompt: les flags van DESPRÉS del prompt |
| `runner.py::_run_claude` sidecar | stdout → `Path(str(log_path)+".out")`, stderr → `log_path`; **no PIPE** | el bucle de cancel·lació fa `proc.wait(0.2)`; un PIPE sense lector bloqueja. El sidecar s'esborra a `_parse_cli_output` |
| `runner.py::_parse_cli_output` | mai llença; JSON → mètriques + `--- result ---` al log; no-JSON → `{"cli_json_ok": False}` + `--- stdout (no JSON) ---` | els tests antics (mock sense JSON) depenen del camí no-JSON |
| Telemetria | cada fila porta `model` + `cli_json_ok`, `num_turns`, `duration_ms`, `duration_api_ms`, `cost_usd`, `is_error`, `subtype`, `usage{…}`, `models[]` | `ledger.py` i l'estimació autocalibrada de la Fase 10 en llegeixen `elapsed_s`/`num_turns`/`usage.output_tokens` |
| `docs/wizard-headless/mesures/ledger.py` | regenera `LEDGER.md` de `runs/*/meta.json` + telemetria + `TOTALS:` del comparador | **no editar `LEDGER.md` a mà**; afegir un run = carpeta + `meta.json` + `python3 ledger.py` |
| `docs/DISSENY-ANNEX-…` §9 | via B intacta (`automation/ai_pipeline/`, `web/vision_groq.py`, `auto_extractor.py`, `web/vision_fast.py`) | `auto_result` a disc (Fase 13) es fa envoltant des de `lectura_service`/`wizard_service`, no dins d'`auto_extractor.py` |

Nit conegut (per a l'implementador, no urgent): si `claude` no existeix (`FileNotFoundError`), el sidecar `.out` buit queda a `/tmp` (els handles sí que es tanquen).

## 5. Procediments operatius

```bash
# Estat esperat
git branch --show-current      # → experiment/nivell-a-2026-08 (in-place a g3dt-prod/)
git log --oneline -3           # → 5f324bc 2f4e3fd 1dab01d (+ el commit d'aquest handoff)

# Suite de lectura (16 s, 73 passed) i completa (2,5 min; línia base 32 failed IDÈNTICS / 1152+ passed)
.venv/bin/python -m pytest tests/test_lectura_runner.py tests/test_lectura_service.py tests/test_lectura_contract.py tests/test_lectura_inventory.py tests/test_utf8_read_text.py -q -p no:cacheprovider
.venv/bin/python -m pytest tests/ -q -p no:cacheprovider   # mai decidir un commit amb `| tail -1`

# Remesura completa de Castellar SOL (esborra validation/lectura/, força, i passa el comparador d'or) — ~33 min a conc. 3
~/g3dt-e2e/fase9/run.sh 3 <etiqueta>        # → ~/g3dt-e2e/fase9/<etiqueta>/{run.log,_telemetry.jsonl,_decisions.json,escalars.txt,taules.txt}
G3DT_LECTURA_MODEL=fable ~/g3dt-e2e/fase9/run.sh 3 fable-c3   # variant de model
# Llançar-lo desatès i vigilar-lo: setsid nohup … &  + Monitor sobre run.log (patró 'lectura_doc \{|lectura_doc_error|decisions|TOTAL_ELAPSED|Traceback|DONE')

# Ingerir un run al llibre
D=docs/wizard-headless/mesures/runs/<etiqueta>; mkdir -p $D/perdoc
cp ~/g3dt-e2e/fase9/<etiqueta>/{_telemetry.jsonl,_decisions.json,escalars.txt,taules.txt,run.log} $D/
cp "/tmp/g3dt-lectura-3001621 CASTELLAR DEL VALLES-consolida.log" $D/consolida.log
cp "$HOME/g3dt-e2e/projectes/3001621 CASTELLAR DEL VALLES/validation/lectura/"*.json $D/perdoc/
cp docs/wizard-headless/mesures/runs/2026-08-24-sonnet-c3/meta.json $D/   # i edita label/concurrency/changes/contaminated/quality_judgement
python3 docs/wizard-headless/mesures/ledger.py

# Comparador d'or a mà (llegeix cada ERR: molts són format)
.venv/bin/python docs/wizard-headless/fase0-acceptacio/compare_consolida.py escalars PATH/_decisions.json "3001621 CASTELLAR DEL VALLES"
.venv/bin/python docs/wizard-headless/fase0-acceptacio/compare_consolida.py taules   PATH/_decisions.json "3001621 CASTELLAR DEL VALLES"

# Sonda de turns d'UN document (out dir a part; cap altra lectura del mateix projecte viva)
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN claude -p "/g3dt-llegir-projecte PROJ --only tall.pdf --inventory INV --out OUTDIR" \
  --permission-mode bypassPermissions --model sonnet --output-format stream-json --verbose > stream.jsonl
# (el stream inclou les imatges en base64: 2,7 MB; l'anàlisi de turns és l'script inline de la sessió — vegeu turns.md per la taula)

# Telemetria d'un run, ràpid
python3 -c "import json;[print(json.loads(l)['mode'],round(json.loads(l)['elapsed_s']),json.loads(l).get('num_turns')) for l in open('PATH/_telemetry.jsonl')]"
```

- Còpies locals dels projectes: `~/g3dt-e2e/projectes/` (Bell-lloc i Castellar). `validation/lectura/` de Castellar té ara la cache del run 2 (conc. 3).
- Artefactes de la Fase 9 fora del repo: `~/g3dt-e2e/fase9/{baseline-e2e,sonnet-c2,sonnet-c3,probe-tall}/`.
- Logs de cada crida: `/tmp/g3dt-lectura-{projecte}-{doc}-{intent}.log` (stderr + `--- result ---`); el sidecar `.out` només existeix mentre la crida és viva.
- Els events del runner (`on_event`): `lectura_inventari`, `templates_fields`, `lectura_inici {n_claude,n_python,docs}`, `lectura_doc_inici`,
  `lectura_doc {cached|attempt|skipped_duplicate}`, `lectura_doc_error`, `decisions {cached}`, `consolidacio_fallback`, `lectura_fi`, `cancelled`.
  La Fase 10 els mapeja als estats de la taula (annex §3.3).
- `pkill -f PATRÓ` es mata a si mateix si el patró surt a la línia d'ordres: `"[c]laude -p /g3dt"`, `"[d]river.py"`. `sleep N` sol està bloquejat:
  `run_in_background` + `until`, o Monitor.

## 6. Seqüència d'obertura suggerida

1. `git branch --show-current`, `git log --oneline -3`, suite de lectura verda (73).
2. Llegeix l'annex §3 (jobs) i §10 (Fase 10) i decideix amb el Josep si la Fase 10 la fa Sonnet (com les Fases 1-7 i la 9) amb un brief tancat.
   Brief mínim: `automation/lectura/jobs.py` (`_job.json`, estats, lock per projecte, `interrupted` per pid mort, estimació autocalibrada de
   `_telemetry.jsonl` de `workspace_root()/*/validation/lectura/`), `GET /api/jobs`, `POST /api/jobs/{p}?button=`, `attach` a
   `lectura_service.get_lectura_streaming`. Tests: transicions, 2n POST → 409+attach, pid mort, estimació amb 0/5/50 files.
3. **Experiment de pre-extracció** (barat, 1 run de 30 min, no toca el skill de producció): còpia del skill a `.claude/commands/g3dt-llegir-projecte-preext.md`
   que llegeixi `text_path`/`pages_png` de l'inventari en comptes d'obrir el fitxer; `inventory.py` (o un pas previ al runner) que generi
   `validation/lectura/_preext/{safe_name}/page-N.txt|png` (+ meitats a 100-150 dpi; xls → csv per full; msg → cos + adjunts) i
   `scripts/write_doc_json.py` (payload per stdin → validació + escriptura atòmica al nom canònic). Run `preext-c3` al llibre + comparador d'or.
   Adoptar només si erroni-amb-confiança de fons = 0 i els candidats no empitjoren (compara `escalars.txt`/`taules.txt` línia a línia amb `sonnet-c3`).
4. Fase 11 (delta-sync) — independent de la 10; també delegable.
5. Pregunta al Josep les decisions obertes de l'annex §12 que bloquegin: contingut del correu (expedient sol o + carpeta), residus Groq (§8),
   conflicte skill/or de la cel·la `cota`.
6. Commit per peça; fila nova al llibre per cada canvi que toqui temps o qualitat; addendum datat a `_RESULTATS.md`; entrada DECISION-LOG quan hi hagi mesura.

## 7. Què NO fer

- No proposar pull/merge/desplegar a l'Eva (memòria `feedback_no_pull_eva_success_criterion`). Amb 33 min tampoc.
- No retallar el protocol del skill (Pas 0/3/verificació) per guanyar temps. No "prompt prim" com a palanca de latència.
- No canviar el model per defecte a Fable sense una fila al llibre que ho justifiqui per qualitat.
- No córrer dues lectures del MATEIX projecte alhora (cap lock fins a la Fase 10). Un sol `run.sh` a la vegada.
- No editar `LEDGER.md` a mà; no reescriure `docs/golden-read*` ni `docs/wizard-headless/fase*` (addendums datats).
- No editar els 4 fitxers de la via B. No afluixar el validador (`contract.py`): n30 i litologia mai `segur`.
- No confiar en la paret d'un run si `ts_end - ts_start` ≠ `elapsed_s` (suspensió/tall) — marca'l contaminat.
- No escriure a `/mnt/c`; E2E a `~/g3dt-e2e/projectes/`. No llançar E2E amb `G3DT_LECTURA_AUTH=api_key`.
- No usar `--output-format stream-json` al runner de producció (el sidecar seria enorme per les imatges); només a sondes manuals.

## 8. Tasques obertes (ordre)

1. Fase 10: registre de jobs + lock + `GET/POST /api/jobs` + attach (annex §3, §10).
2. Experiment pre-extracció + `write_doc_json.py` → fila `preext-c3` al llibre (§6.3 de dalt).
3. Fase 11: delta-sync xarxa→workspace (annex §4).
4. Fase 12: consolidació Python-first + guard de confiança (segur amb 1 font → candidats) + fusió punt+fondària a `spt_ma_tests`; validar amb el comparador d'or.
5. Fase 13: `auto_result` a disc + decisió residus Groq (annex §8).
6. Fase 14-15: UI tres botons + taula; `notify.py` (toast, SMTP Eficients, telemetria).
7. Decisions Josep (annex §12): sostre de subscripció, contingut del correu, art. 28, servidor viu a Windows, Brevo vs bústia.
8. Pendents anteriors intactes (handoff 19:10 §7): forat 1 (fonts Python al consolidador), Fase 8b (seleccions de taula → generador), Windows,
   Pendent A (Tier B), preguntes a l'Eva (criteri N30, sulfats d'Anciles), multi-informe Tulipa.

## 9. Guanys ocults

- **Ara es pot raonar sobre la latència sense córrer res**: `ledger.py::_wall_reconstructed` prediu la paret a 1 min; la telemetria porta turns i tokens
  per document. Qualsevol palanca es pot estimar i després verificar amb una fila.
- **La qualitat ha aguantat tres runs cegs** amb 0 erroni-amb-confiança de fons, i els dos únics defectes de confiança tenen guard determinista: el
  sistema de qualitat segueix autoalimentant-se (Fase 0 → E2E → Fase 9).
- **El disseny dels tres botons converteix la latència en un no-problema per a l'Eva** sense tocar la lectura: la decisió estratègica de la nit.
- La sonda ha trobat que 5 de cada 15 usos d'eina són el model construint-se `fitz` cada vegada: la palanca de pre-extracció és la primera que pot
  baixar el temps per document de manera substancial **sense canviar què mira**.
