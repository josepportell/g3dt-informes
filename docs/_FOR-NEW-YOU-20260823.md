# FOR NEW YOU — 2026-08-23 — Diagnòstic detallat de producció G3DT (post-fixes F1-F4e, SENSE merge)

**Escrit:** 2026-08-22 (nit) · **Per a:** la sessió nova que farà el diagnòstic detallat que el Josep ha demanat.
**Recap d'ahir en una frase:** s'han executat els fixes F1-F4 del pla d'auditoria (+F4b-e trobats durant la verificació),
verificats end-to-end amb 3 projectes (Tulipa real: 708 → 273 s de prefills, DPSH via Anthropic 3/3 OK, 0 tracebacks),
tot a `review/prod-audit-2026-08`; **el Josep ha decidit NO fusionar ni fer pull a prod encara** i vol abans un diagnòstic
més detallat de la situació. Aquesta sessió és diagnòstic, no fixes.

## 1. Ordre de lectura (20 min)

1. Aquest document.
2. `STATUS.md` — bloc "Auditoria prod 2026-08" (taula de fixes + decisió del Josep).
3. `docs/audit/AUDIT-PROD-2026-08.md` — la fotografia original dels 14 dies de logs de l'Eva (T1-T5, §3 "què hem
   plantejat malament").
4. `docs/audit/VERIFICACIO-FIXES-2026-08.md` — què ha canviat amb els fixes i **§3: on van els 273 s que queden**.
5. `docs/DECISION-LOG.md` entrada `2026-08-22` — per què cada fix és com és, alternatives rebutjades, "Limitacions conegudes".
6. `docs/PLA-FIXES-PROD-2026-08.md` §7 — desviacions, "ja que hi som" NO fets, dubtes per al Josep.
7. `docs/audit/BENCH-DEEP-FOLDER-MODELS-2026-08-22.md` — benchmark de models (Sonnet 5 no compensa a deep_folder).
8. `docs/audit/eva-logs-profile-2026-08-22.md` — perfil dels logs reals (regenerable amb `scripts/profile_eva_logs.py`).
9. MEMORY.md (auto-memòria): `project_prod_audit_fixes_2026_08`, `groq_llama4_scout_deprecated`,
   `eva_prod_logs_scoreboard_2026-08`, `feedback_no_volume_reasoning`.

## 2. Què vol dir "diagnòstic més detallat" (interpretació — confirmar amb el Josep a la primera resposta)

El Josep no ha concretat. El que la sessió d'ahir ha deixat SENSE resposta, i que un diagnòstic hauria de cobrir:

- **Temps:** els 273 s de Tulipa són 145 s de visió en 5 tipus **en sèrie** + 52 s de 23 probes **en sèrie** + 27 s Tier 3 +
  20 s síntesi LLM. No són errors. Quant d'això és evitable (paral·lel), quant és latència de model irreductible, i quant
  aporta cada fase als camps de l'informe (AUDIT §3.2: "classificar-ho tot visualment abans de mostrar res").
- **Qualitat:** no s'ha mesurat. Ahir només comparacions ad hoc prefills-vs-Eva (Tulipa 10 MATCH / 13 DIFF, Rubí 13/25,
  Bell-lloc 20/23, amb molts "sense clau" per noms diferents). Rubí produeix **narrativa en castellà** i una adreça falsa
  perquè `vision_probe` (fotos) guanya a pressupost/plànol i alimenta el detector d'idioma.
- **Eva:** des del 25 de juny ha obert el wizard 2 dies. Sense el seu `g3dt.log.txt` actual no sabem si el pull del 23 jul
  va quedar bé (AUDIT §T5). Preguntes per a ella a AUDIT §6.
- **Models:** gpt-4.1-mini és vell (Josep). Sonnet 5 provat només a `deep_folder_classify` (empat, 2× lent). A/B pendent
  on importa: `dpsh`/`sondeig` amb ground truth (N20 de l'Excel).

## 3. Regles interpretatives (apreses ahir, no òbvies)

- **Els temps de prefills depenen del cache.** Un workspace + `G3DT_CACHE_DIR` nous = "primera obertura" (com l'Eva amb un
  projecte nou). Un segon run del mateix projecte reutilitza `validation/*_extracted.json`, `concept_probes/`, geocode →
  no és comparable. Ahir tots els números són en fred.
- **Contenció de CPU falseja ConceptScout** (23 → 64 s quan la suite de tests corria alhora). No executis pipeline i suite
  a la vegada si vols cronometrar.
- **`test_smartscan` és flaky** (18-20 fallades segons el run; depèn de xarxa). Baseline oficial: **32 failed / 1079 passed**;
  compara el CONJUNT de fallades (`grep ^FAILED | sort | diff`), no el recompte.
- **`groq_miner.TestCache.test_cache_hit`** falla al baseline; no és teu.
- **Groq `qwen/qwen3.6-27b` és un model de raonament.** Sense `reasoning_effort="none"` gasta 1.600-4.000 tokens pensant i
  Groq retorna 400 `json_validate_failed`. Límit **3 imatges** per crida, **16.384** tokens de sortida. Qualsevol crida nova a
  Groq ha de passar per `config.groq_payload_extras(model)` (hi ha un test estàtic que ho exigeix).
- **Anthropic directe des de dev: la clau del `.env` no té crèdit** (HTTP 400 "credit balance too low"). Per exercir la via
  "anthropic" usa `G3DT_LLM_PROVIDER=openrouter` (mateix `claude-sonnet-4-6`, SDK Anthropic amb `base_url`; `stop_reason` i
  `usage` arriben igual). OpenRouter té ~20 $ (Josep n'hi ha posat ahir; `GET /api/v1/credits`).
- **Prefill d'assistant `"{"` retorna 400 a claude-*-4-6 i 5.** No el reintroduexis (F2 ho documenta).
- **El `.env` és gitignored i el de l'Eva és del 4 de maig.** Fixa `GROQ_TEXT_MODEL=qwen/qwen3-32b` (retirat → 404). F4d
  (`config.RETIRED_GROQ_MODELS`) ho absorbeix; el `.env` d'aquest worktree s'ha deixat ANTIC a propòsit per verificar-ho.
- **`/api/projects` retorna `[]` en mode xarxa.** L'Eva selecciona via `POST /api/network/select {"path": "<carpeta>"}` i
  després `/api/prefills/<leaf>`. No és un bug nou.
- **Comparador prefills-vs-Eva:** `scripts/compare_eva_vs_pipeline.py` està cablejat a `reference-material/`; ahir es va
  fer servir un script ad hoc (scratchpad, perdut). Les claus d'Eva (`client`, `plantes`) ≠ claus de prefills
  (`client_name`, `num_floors`): un "MISSING" sovint és només nom diferent.
- **Eva és l'única usuària** — no justifiquis models més febles per cost ni per volum (memòria `feedback_no_volume_reasoning`).

## 4. Invariants estructurals que el treball d'ahir necessita (no desfer)

| On | Què | Per què |
|---|---|---|
| `web/wizard_service._read_file_mapping()` | llegeix `file_mapping.json` en UTF-8 i mai llança | cp1252 a Windows + `ensure_ascii=False` = crash de Can Mir Rubí; `tests/test_utf8_read_text.py` prohibeix `read_text()` sense encoding a `automation/` + `web/` |
| `web/vision_groq._parse_json_response()` | parser compartit pels 3 proveïdors; error amb els 200 primers caràcters | abans el log no deia què responia el model |
| `web/vision_groq.MAX_TOKENS_BY_TYPE` + `PROVIDER_MAX_OUTPUT_TOKENS` | dpsh 16k, clamp per proveïdor | Tulipa necessita 6.651 tokens de sortida reals; Groq màx 16.384 |
| `web/vision_groq.VisionTruncated` + `_call_backend_chain()` | truncament → no reintent, **la cadena s'atura** | el següent proveïdor amb el mateix pressupost truncaria igual; "mai 3 × 150 s pel mateix error" |
| `config.groq_payload_extras()` / `live_groq_model()` / `RETIRED_GROQ_MODELS` / `GROQ_MAX_IMAGES=3` | únic lloc del switch de raonament i del mapa de models retirats | 9 fitxers copien la mateixa crida httpx; test estàtic `test_every_groq_call_site_uses_payload_extras` |
| 4xx a Groq no es reintenta (vision_groq, groq_miner, ortho_vision, parcel_validator, mapillary_client) | només 5xx i xarxa | 400/404 són deterministes |
| `concept_scout/vision_probe.GROQ_PROBE_429_BUDGET=10` | passat el llindar, fitxers `notes="unprobed: …"` | 320 × 5 s de sleep en 14 dies; 0 = desactivat |
| `automation/validation/prompts.EXTRACTION_SYSTEM_PROMPT` acaba amb la clàusula OUTPUT JSON-only | afecta els 3 proveïdors | `test_system_prompt_demands_json_only` |

## 5. Procediments operatius

```bash
cd ~/projects/claudecode-job/clients/g3dt-prod
git branch --show-current            # review/prod-audit-2026-08 (esperat; CLAUDE.md §Excepció). production/g3dt-eva-v1 NO té res nou.
git status --short | grep -v '^ D'   # els " D reference-material/**/mined_images/*" són artefactes; ignorar
                                     # ?? docs/diagnostics/ai_pipeline_demo-project_*.md = la suite de tests els genera; ignorar
                                     # ?? reference-material/3001631 RUBI/validation/photo_selection.json = del 6 de juny, no tocar

# Tests (no hi ha pytest-timeout; ~3,5 min; NO alhora que un pipeline cronometrat)
.venv/bin/python -m pytest -q -p no:cacheprovider > /tmp/claude-1000/suite.log 2>&1; tail -1 /tmp/claude-1000/suite.log
grep '^FAILED' /tmp/claude-1000/suite.log | sed 's/ - .*//' | sort > /tmp/claude-1000/failed.txt   # compara amb el baseline

# Servidor com a producció (mode xarxa: sync → workspace → copy-back). Workspace i cache NOUS per cronometrar en fred.
S=/tmp/claude-1000/diag; mkdir -p $S/ws $S/cache
G3DT_LLM_PROVIDER=openrouter G3DT_NETWORK_PROJECTS=/mnt/c/claude/g3dt/projectes-debug \
  G3DT_LOCAL_WORKSPACE=$S/ws G3DT_CACHE_DIR=$S/cache G3DT_LOG_PATH=$S/run.log G3DT_REPORTS_DIR= \
  nohup .venv/bin/python -m web > $S/server.out 2>&1 &
curl -s -X POST localhost:8765/api/network/select -H 'Content-Type: application/json' -d '{"path": "3001706 C.TULIPA CERDANYOLA"}'
time curl -s "localhost:8765/api/prefills/3001706%20C.TULIPA%20CERDANYOLA" -o $S/prefills.json
curl -s -X POST "localhost:8765/api/generate/3001706%20C.TULIPA%20CERDANYOLA"
.venv/bin/python scripts/profile_eva_logs.py $S/run.log      # perfil per proveïdor/context
# Aturar: PID via `ss -ltnp | grep 8765`; kill $PID.  MAI `pkill -f 'python -m web'` (mata el teu propi shell).
```

- **Projectes:** Tulipa real → `/mnt/c/claude/g3dt/projectes-debug/3001706 C.TULIPA CERDANYOLA` (hi ha una 2a còpia a
  `/mnt/c/claude/g3dt/__PROD-DEBUG-TULIPA/3001706 C.TULIPA CERDANYOLA/3001706 C.TULIPA CERDANYOLA`, amb caches vells).
  7 antics → `/mnt/c/claude/g3dt/projectes/` (`G3DT_NETWORK_PROJECTS=/mnt/c/claude/g3dt/projectes`). Referència d'Eva:
  `reference-material/<p>/validation/eva_reference_values.json` (**només llegir**). Per a Tulipa, Eva té
  `3001706_TULIPA_INFORME_FIX.docx` a l'arrel: `python -m automation.reference_extractor "<ruta al docx>"` → 42 variables.
- **Logs de l'Eva:** `/mnt/c/claude/g3dt/dades-eva/` (zip + txt, fins 23 jul 17:51).
- **Marcadors del perfilador:** obertura = `SmartScan: N entries found`; fi prefills = `LLM synthesis:`; informe OK =
  `Copied report to network` (només en mode xarxa).
- **Quant costen les fases (Tulipa, run 3):** sync 4 s · SmartScan+Tier3 27 · FileMiner+groq_miner 5 · probes 52 (23 fitxers,
  ~2,2 s) · deep_folder 15 · **visió 145** (dpsh 77 · sondeig 20 · annex 32 · plànol 6 · projecte 4) · geocode ~5 · síntesi 20.

## 6. Seqüència d'obertura suggerida

1. `git branch --show-current` + `git log --oneline -12` — confirma `review/prod-audit-2026-08` a `be37c6f` i que
   `production/g3dt-eva-v1` segueix a `b579ef5`.
2. Llegeix §1 (20 min). No toquis codi.
3. Pregunta al Josep, en una sola resposta, què ha de cobrir el diagnòstic (les 4 dimensions de §2) i si té el
   `g3dt.log.txt` actual de l'Eva o noves carpetes de projecte (AUDIT §6).
4. Si vol temps: instrumenta **una** obertura freda de Tulipa amb timestamps per fase (el log ja els té) i construeix el
   Gantt de fases amb "quants camps de l'informe omple cada fase" (`prefills.json` porta `source` per camp).
5. Si vol qualitat: fes un comparador prefills-vs-Eva amb mapatge de claus (no el d'ahir) per a Tulipa, Rubí, Bell-lloc +
   els 4 altres de referència; classifica els DIFF per causa (font equivocada / format / càlcul / no extret).
6. Si vol models: A/B `dpsh` + `sondeig` Sonnet 5 vs 4.6 via OpenRouter amb ground truth N20 (Excel) i cotes de rebuig
   (`eva_reference_values.json`). Recorda: `thinking` desactivat o `effort` baix, mai sampling params a Sonnet 5.
7. Entrega: un sol document `docs/audit/DIAGNOSTIC-PROD-2026-08-2x.md` amb números, causes i opcions amb cost/benefici,
   **sense implementar res** tret que el Josep ho demani.

## 7. Què NO fer

- No fusionar a `production/g3dt-eva-v1` ni fer pull a l'ordinador de l'Eva (decisió explícita del Josep, 2026-08-22 nit).
- No escriure a `reference-material/` (ni caches ni `.docx`). Executa sempre sobre les còpies de `/mnt/c/claude/g3dt/`.
- No tocar `automation/ai_pipeline/` ni `experiment/ai-pipeline` (no és prod).
- No reordenar/paral·lelitzar fases "ja que hi som": és la decisió que el Josep vol prendre amb el diagnòstic a la mà.
- No canviar el model de `deep_folder_classify` (benchmark fet: empat de qualitat, 2× més lent).
- No afegir un "traductor" a la narrativa castellana: el detector `_get_project_language()` existeix i hi ha projectes
  realment en castellà; la causa és la font (`vision_probe`), no l'idioma.
- No cronometrar amb caches calents ni amb la suite de tests corrent.
- No usar `pkill -f` amb un patró que aparegui a la teva pròpia línia de comanda.
- No consultar models Groq de memòria: `GET https://api.groq.com/openai/v1/models` (es retiren sense avís).

## 8. Tasques obertes (snapshot)

- [ ] **Diagnòstic detallat** (aquesta sessió) — abast a confirmar amb el Josep (§2).
- [ ] Decisió Josep: fusió de `review/prod-audit-2026-08` (10 commits, suite idèntica al baseline) + pull a `C:\g3dt-ia` (F5).
- [ ] Decisió Josep: sessió de latència estructural (paral·lel visió/probes, prefills bàsics abans de la visió).
- [ ] A/B Sonnet 5 vs 4.6 a `dpsh`/`sondeig` amb ground truth (proposta al benchmark §4).
- [ ] F6 (proposat, no fet): `_get_project_language()` només amb fonts fiables + camp d'idioma al wizard; `vision_probe` no
  ha de guanyar a pressupost/plànol per `street_address`/`building_type`/`municipality`.
- [ ] Demanar a l'Eva: `C:\g3dt-ia\g3dt.log.txt` actual + 2-3 carpetes recents + `user_data.json` dels informes fets (AUDIT §6).
- [ ] "Ja que hi som" pendents (PLA §7): client Groq únic, picker de models a `web/api.py` amb ids retirats, `_validation/`
  minat com a dades, geocode amb nom de carpeta com a municipi, artefactes `docs/diagnostics/` de la suite.
- [ ] Confirmacions d'Eva encara pendents de juny/juliol (STATUS "Blockers actius").

## 9. Guanys que no surten als números

- **Per fi es veu què respon el model.** Abans, 29/29 fallades d'Anthropic eren "Expecting value" sense text; ara el WARNING
  porta `stop_reason` + 200 caràcters. Qualsevol fallada futura de visió és diagnosticable des del log de l'Eva.
- **El canvi de model del 23 jul era nociu i ningú ho sabia.** `qwen3.6-27b` pensava dins del pressupost i convertia cada
  probe en 3 × 10 s de 400s; el model de text estava retirat. Amb F4b-e, Groq torna a ser el camí barat i ràpid (22 probes,
  0 errors, ~2 s cada una).
- **Un `.env` antic ja no pot trencar res** (mapa de models retirats). Quan Groq retiri el següent model, serà una línia a
  `config.RETIRED_GROQ_MODELS`, no una visita presencial.
- **9 còpies de la crida Groq estan inventariades** i un test estàtic impedeix que la 10a oblidi el switch de raonament.
