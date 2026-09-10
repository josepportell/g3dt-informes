# Pla d'execució — Fixes de producció G3DT (agost 2026)

**Per a:** una sessió nova de Claude Code a `clients/g3dt-prod/`, amb tota la finestra de context.
**Origen:** `docs/audit/AUDIT-PROD-2026-08.md` (llegir-lo primer, 5 min). Aquest pla no repeteix
l'anàlisi: diu què tocar, on, com provar-ho i quan parar.
**Estat en escriure'l (2026-08-22):** branca `review/prod-audit-2026-08`, commit `1e7d561`.

---

## 0. Arrencada de la sessió nova (5 min)

```bash
cd ~/projects/claudecode-job/clients/g3dt-prod
git branch --show-current        # ha de dir: review/prod-audit-2026-08  (si no → STOP, preguntar al Josep)
git status --short | grep -v '^ D' # els " D reference-material/**/mined_images/*" són artefactes; ignorar-los
```

Llegir, en aquest ordre: `docs/audit/AUDIT-PROD-2026-08.md` → aquest pla → §Guardarails.
No cal rellegir els logs de l'Eva: el perfil ja és a `docs/audit/eva-logs-profile-2026-08-22.md`
(regenerable amb `scripts/profile_eva_logs.py`).

## 1. Guardarails (no negociables)

1. **`production/g3dt-eva-v1` no rep cap commit.** Tot va a `review/prod-audit-2026-08`.
   Fusionar a prod i fer pull a l'ordinador de l'Eva és decisió i acció del Josep.
2. **Sense worktree nou.** Treball in-place (decisió del Josep 2026-08-22, CLAUDE.md §Excepció).
3. **No escriure a `reference-material/`.** Qualsevol execució del pipeline apunta a còpies:
   `G3DT_PROJECTS_DIR=/mnt/c/claude/g3dt/projectes` (7 antics) o
   `G3DT_PROJECTS_DIR=/mnt/c/claude/g3dt/projectes-debug` (Tulipa, projecte real).
4. **No tocar `experiment/ai-pipeline`** ni `automation/ai_pipeline/`. No és a prod.
5. **No refactors de fases** (SmartScan, FileMiner, ConceptScout, ordre del pipeline). Només els
   fixes d'aquest pla. Si durant un fix apareix "ja que hi som…", anotar-ho a §7 i seguir.
6. **Tests:** `.venv/bin/python -m pytest -q -x --timeout=600` — durada ~4 min, **timeout 10 min**.
   Baseline conegut: **32 failed / 1023 passed** (2026-07-23). Un fix no pot empitjorar el baseline;
   els 32 no s'han d'arreglar en aquest pla.
7. **Un commit per fix**, missatge `fix(g3dt): F<n> — <què>`, amb el test inclòs. Trailer
   `Co-Authored-By` + `Claude-Session` com als commits recents (`git log -3`).
8. **Zero fabricació:** si un criteri d'acceptació no es pot verificar, dir-ho al STATUS, no marcar ✅.

## 2. Ordre d'execució i temps previst

| Pas | Què | Temps | Depèn de |
|---|---|---|---|
| F1 | Encoding UTF-8 als `read_text()` | 30 min | — |
| F2 | Anthropic: JSON-only + parser robust | 1 h | — |
| F3 | `max_tokens` per tipus + `stop_reason` + no reintentar truncaments | 1 h | F2 (mateix fitxer) |
| F4 | Groq: ≤5 imatges/crida + backoff real al 429 | 45 min | — |
| V | Verificació end-to-end amb Tulipa + 2 projectes antics, amb cronòmetre | 45 min | F1-F4 |
| D | Documentació: DECISION-LOG, STATUS, sessió | 20 min | V |

Total ≈ 4,5 h. Si s'acaba el context abans de V: commit del que hi hagi, STATUS amb "F<n> fet, V pendent".

---

## 3. Fixes

### F1 — `read_text()` sense encoding (crash cp1252 a Windows)

**Problema.** `Path.read_text()` sense `encoding` usa cp1252 a Windows; els JSON del pipeline
s'escriuen en UTF-8 (`ensure_ascii=False`). Un nom de fitxer amb un caràcter fora de cp1252 →
`UnicodeDecodeError` a `_merge_prefills` → wizard buit. Evidència: Can Mir Rubí 4/4 intents
(AUDIT §T2).

**Fitxers i línies (verificar amb grep abans d'editar, poden haver-se mogut):**
```bash
/usr/bin/grep -rn 'read_text()' --include=*.py automation web | /usr/bin/grep -v test
```
Esperats (11): `automation/image_manager.py:661,677` · `automation/mapillary_client.py:539` ·
`automation/config.py:73` · `automation/validation/schemas.py:15,218,325` ·
`automation/fix_template_and_image_width.py:52` · `automation/google_satellite.py:55` ·
`web/wizard_service.py:2151,2172` (← el crash real).

**Canvi.** `read_text()` → `read_text(encoding='utf-8')` als 11. Per a `config.py:73` i
`google_satellite.py:55` (lectura de `.env`): `encoding='utf-8', errors='replace'` — un `.env`
escrit amb Notepad pot ser cp1252 i no ha de petar l'arrencada.
Comprovar també `write_text(` sense encoding al mateix grep (`write_text(` + `-v encoding`); si n'hi
ha, mateix tractament.

**Test nou** `tests/test_utf8_read_text.py`:
1. Escriure un `file_mapping.json` temporal amb `json.dumps({'roles': {'x': {'path': 'Nº 5 · Rubí.pdf'}}}, ensure_ascii=False)` en UTF-8.
2. Amb `monkeypatch` de `locale.getpreferredencoding` → `'cp1252'` (o `Path.read_text` per defecte), cridar la funció de `wizard_service` que llegeix `fm_path` (localitzar la funció exacta: `_merge_prefills` o l'helper que extregui) i assertar que no llança.
3. Test de regressió estàtic: grep programàtic que **cap** `read_text()`/`write_text(` sense `encoding` existeixi a `automation/` + `web/` (exclou tests). Així el bug no torna.

**Acceptació.** Test nou verd · baseline intacte · `grep` del punt 3 retorna 0.

**Commit.** `fix(g3dt): F1 — encoding='utf-8' als 11 read_text() (crash cp1252 Can Mir Rubí)`

---

### F2 — Anthropic Vision: resposta amb prosa → `json.loads` falla (92% FAIL en DPSH)

**Problema.** `web/vision_groq.py::_call_anthropic_vision` (def a l. 584; parseig a ~626-640):
si el text no té ``` fa `json.loads(text)` directe; si en té però cap bloc parseja, fallback
`json.loads(text)` de tot. Claude sovint respon "Here is the extracted data:\n{…}" →
`Expecting value: line 1 column 1`. 29/29 fallades idèntiques (AUDIT §T1.1). El
`EXTRACTION_SYSTEM_PROMPT` (`automation/validation/prompts.py:474`) no exigeix JSON pur.

**Canvi (dues capes, les dues):**
1. **Prompt.** Afegir al final de `EXTRACTION_SYSTEM_PROMPT`:
   `OUTPUT: respond with a single JSON object and nothing else — no preamble, no explanation, no markdown fences.`
   (afecta els 3 proveïdors; OpenAI/Groq ja usen `response_format=json_object`, no els molesta).
2. **Prefill d'assistant** a la crida Anthropic: `messages=[{"role":"user",…}, {"role":"assistant","content":"{"}]`
   i reconstruir `text = "{" + response.content[0].text`. Això força JSON des del primer caràcter.
   ⚠ Comprovar a la docs de l'SDK `anthropic` instal·lat (`.venv/bin/pip show anthropic`) que el
   model `claude-sonnet-4-6` accepta prefill; si no, ometre el prefill i confiar en 1+3.
3. **Parser robust** — extreure a un helper `_parse_json_response(text: str) -> dict` reutilitzat pels
   3 proveïdors: (a) strip; (b) si conté ```, provar cada bloc; (c) si no, provar `text` sencer;
   (d) últim recurs: substring entre el primer `{` i l'últim `}`. Si tot falla, llançar
   `json.JSONDecodeError` amb els primers 200 caràcters del text al missatge (ara el log no diu
   què ha respost el model — és per això que ha calgut 3 mesos per veure'l).
4. **Log de diagnòstic:** al `except` de `_call_anthropic_vision`, loggar `stop_reason` i
   `text[:200]` a nivell WARNING.

**Test nou** `tests/test_vision_json_parse.py` (sense xarxa; `_parse_json_response` és pur):
- `'{"a":1}'` → ok · `'Here is the data:\n{"a":1}'` → ok · '```json\n{"a":1}\n```' → ok ·
  `'Sure!\n```json\n{"a": 1}\n```\nDone.'` → ok · `'{"a": [1, 2'` (truncat) → `JSONDecodeError`
  amb el text al missatge · `''` → `JSONDecodeError`.
- Test de `_call_anthropic_vision` amb client mockejat (`monkeypatch` de
  `automation.llm_client.get_anthropic_client`) que retorna `content[0].text = 'Here you go:\n{"tests": []}'`
  → resultat dict, no `None`.

**Acceptació.** Tests nous verds · baseline intacte · en V (Tulipa), `VISION OK provider=anthropic type=dpsh`
al log o, si falla, el WARNING mostra el text real del model.

**Commit.** `fix(g3dt): F2 — Anthropic vision: JSON-only + parser robust (92% FAIL DPSH)`

---

### F3 — `max_tokens=4096` trunca el DPSH; el truncament es reintenta i es fa fallback

**Problema.** `web/vision_groq.py` l. 233 i 1168: `tok_limit = 8192 if vtype == 'projecte_arquitecte' else 4096`.
Schema DPSH (`prompts.py:23-26`) ≈ 30 tokens/lectura; 4 penetros × 40 lectures ≈ 4.800 > 4.096.
`_call_openai_vision` (l. 494) reintenta `max_retries=2` (+1) el mateix truncament (~150 s cada
un) i després la cadena prova el següent proveïdor amb el mateix límit. Cap proveïdor comprova
`finish_reason`/`stop_reason`. Evidència: 10 FAIL OpenAI tots de JSON truncat; obertures de 13-16 min
(AUDIT §T1.2-3).

**Canvi.**
1. **Límit per tipus**, en una sola constant a dalt del fitxer:
   ```python
   MAX_TOKENS_BY_TYPE = {"dpsh": 16384, "projecte_arquitecte": 8192}   # default 4096
   ```
   i `tok_limit = MAX_TOKENS_BY_TYPE.get(vtype, 4096)` als dos llocs (l. 233 i 1168).
   ⚠ Verificar el màxim de sortida de cada model (`claude-sonnet-4-6`, `gpt-4.1-mini`,
   `qwen/qwen3.6-27b`) a la docs oficial o amb una crida de prova; si algun no arriba a 16k,
   ajustar el dict per proveïdor, no a ull.
2. **Detectar truncament** abans de parsejar:
   - OpenAI/Groq: `data["choices"][0].get("finish_reason") == "length"`
   - Anthropic: `response.stop_reason == "max_tokens"`
   → loggar `WARNING "… truncated at max_tokens=%d (finish_reason=length)"` i retornar un
   sentinel (p. ex. llançar `VisionTruncated(Exception)`) **sense reintentar**.
3. **Cadena de fallback:** a la iteració sobre `chain` (l. ~1184-1200), si el proveïdor ha
   retornat truncat, **no** provar el següent amb el mateix `tok_limit` — o bé aturar la cadena,
   o bé reintentar un sol cop amb `tok_limit * 2` si el model ho admet. Decidir i documentar al
   DECISION-LOG; la regla és "mai 3 × 150 s pel mateix error".
4. Els reintents de `_call_openai_vision` queden només per a 429 i errors de xarxa, no per a
   `JSONDecodeError`.

**Test nou** `tests/test_vision_truncation.py` (mock `httpx.Client.post`):
- Resposta OpenAI amb `finish_reason: "length"` i contingut `'{"tests": [{"a": 1'` → una sola
  crida HTTP (comptador al mock), retorn `None`/`VisionTruncated`, cap `sleep`.
- `tok_limit` per `dpsh` = 16384; per `planol` = 4096.

**Acceptació.** Tests verds · baseline intacte · en V, cap `Unterminated string`/`Expecting ','`
al log de Tulipa; temps de visió DPSH < 90 s.

**Commit.** `fix(g3dt): F3 — max_tokens per tipus (dpsh 16k) + stop_reason, sense reintents de truncament`

---

### F4 — Groq: "Too many images" + rate-limit sense backoff

**Problema.** `_call_groq_vision` (l. 395): envia totes les imatges (27× `Too many images
provided. This model supports up to 5 images`) i al 429 dorm 5 s fix fins a 3 intents (320
rate-limits en 14 dies = 14 min de sleep). Qui més ho pateix: `automation/concept_scout/vision_probe.py`
(301 crides OK + la majoria dels 429), en sèrie, una imatge per fitxer.

**Canvi.**
1. A `_call_groq_vision`: si `len(images) > 5`, loggar i **retornar `None` immediatament** (que la
   cadena passi a OpenAI/Anthropic) — no gastar una crida per rebre un 400 conegut. Constant
   `GROQ_MAX_IMAGES = 5`.
2. Al 429: respectar `Retry-After` si ve a la capçalera; si no, backoff exponencial 2-4-8 s amb
   jitter; màxim 3 intents (ja hi és).
3. **Pressupost global per obertura** a `vision_probe`: si acumula ≥ N rate-limits (p. ex. 10) en
   una obertura, deixar de sondejar imatges amb Groq i marcar-les `unprobed` al `concept_map`
   (el wizard ja té fallback quan un concepte no té font). Loggar una sola línia resum.
   ⚠ Això és l'únic canvi de comportament de pipeline del pla; és acotat (només Groq probes) i
   reversible per constant. Si el Josep no el vol, fer només 1+2.

**Test nou** `tests/test_groq_vision_limits.py` (mock `httpx`): 6 imatges → 0 crides HTTP,
retorn `None` · 429 amb `Retry-After: 1` → espera ≥1 s i ≤2 s (mock de `time.sleep` amb captura).

**Acceptació.** Tests verds · baseline intacte · en V, cap `Too many images` al log; `rate limited`
≤ 10 per obertura.

**Commit.** `fix(g3dt): F4 — Groq vision: ≤5 imatges, backoff amb Retry-After, pressupost de 429 per obertura`

---

## 4. V — Verificació end-to-end amb cronòmetre

Objectiu: confirmar que els fixes canvien el que l'Eva viu, i obtenir el primer cronòmetre
per fase sobre un projecte **real** (Tulipa). Sense wizard visual, tot headless.

```bash
# 1. Tulipa (projecte real, 0/3 informes OK a l'Eva). Neteja de caches de visió prèvies:
ls "/mnt/c/claude/g3dt/projectes-debug/3001706 C.TULIPA CERDANYOLA/validation/"   # mirar què hi ha
#    → esborrar només *_extracted.json / concept_map.json / file_mapping.json d'aquesta CÒPIA (no reference-material)
# 2. Servidor apuntant a la còpia, log a fitxer:
G3DT_PROJECTS_DIR=/mnt/c/claude/g3dt/projectes-debug .venv/bin/python -m web > /tmp/claude-1000/tulipa-run.log 2>&1 &
# 3. Disparar prefills (verificar ruta exacta a web/api.py: /api/prefills/{project})
time curl -s "http://localhost:8765/api/prefills/3001706%20C.TULIPA%20CERDANYOLA" > /tmp/claude-1000/tulipa-prefills.json
# 4. Generar informe:
curl -s -X POST "http://localhost:8765/api/generate/3001706%20C.TULIPA%20CERDANYOLA"
# 5. Perfil del log d'aquesta execució:
python3 scripts/profile_eva_logs.py /tmp/claude-1000/tulipa-run.log
```

Repetir amb 2 projectes antics que tinguin DPSH gran (Rubí: 4 penetros; Bell-lloc) a
`G3DT_PROJECTS_DIR=/mnt/c/claude/g3dt/projectes` i comparar els prefills amb
`reference-material/<p>/validation/eva_reference_values.json` (compte: llegir-los des de
`reference-material/` està bé; escriure-hi, no).

**Registrar a `docs/audit/VERIFICACIO-FIXES-2026-08.md`:**

| Projecte | Abans (logs Eva) | Després: temps prefills | Visió DPSH (prov./OK) | Informe generat | Camps vs Eva |
|---|---|---|---|---|---|
| Tulipa | 7,7 / 8,7 min, 0/3 OK | | | | (sense referència) |
| Rubí | — | | | | |
| Bell-lloc | — | | | | |

Criteri global: **prefills < 3 min** en els tres, **DPSH via Anthropic OK** en almenys 2/3,
**0 tracebacks**. Si no s'assoleix, dir quin i per què; no ajustar el criteri.

## 5. D — Documentació de tancament

1. `docs/DECISION-LOG.md`: una entrada `## 2026-08-XX — Fixes F1-F4 post-auditoria prod` amb
   les seccions habituals (Context, Decisions amb alternatives rebutjades, Validació empírica =
   taula de §4, Tests nous + total, GO/NO-GO).
2. `STATUS.md`: substituir el bloc "Auditoria interna en curs" per l'estat real (quins F fets,
   V resultat, pendent de fusió a prod per decisió del Josep).
3. `.claude/sessions/YYYY-MM-DD-session.md`.
4. Commit `docs(g3dt): tancament fixes F1-F4 + verificació`.

## 6. Fora d'abast d'aquesta sessió (no fer-ho, anotar-ho)

- F5 (verificar l'ordinador de l'Eva): només el Josep, presencialment o amb el log que l'Eva enviï.
- Reordenar fases perquè el wizard mostri prefills bàsics abans de la visió (AUDIT §3.2-3): és la
  millora gran; requereix decisió del Josep i possiblement dades de més projectes de l'Eva.
- Telemetria "camps corregits per l'Eva" (AUDIT §3.4).
- Els 32 tests del baseline.
- StreetView adjacents, A4 entity confusion, Linyola pressupost (STATUS "Open items").

## 7. Notes de la sessió executora (2026-08-22, omplert)

**Estat:** F1-F4 fets i commitats (`89f34b5`, `cac6ba6`, `992c13c`, `ec44b20`) + F4b-F4e (`c339f1f`, `af1a6e0`,
`ed42221`, `6a6f780`) + V + D. Resultat de V: `docs/audit/VERIFICACIO-FIXES-2026-08.md`. DECISION-LOG entrada 2026-08-22.

- **Desviacions del pla i per què:**
  - F2 sense prefill d'assistant `"{"`: retorna HTTP 400 a claude-*-4-6 (opció prevista al pla: "ometre i confiar en 1+3").
  - F3: en truncament la cadena **s'atura** (no ×2); motiu al DECISION-LOG §3.
  - F4 ampliat (F4b-e) perquè V ha demostrat que el model Groq del 23 jul (`qwen3.6-27b`, raonament) era la causa dominant
    del temps: `reasoning_effort=none`, cap 3 imatges, 4xx sense reintent, model de text retirat (404), mapa de models
    retirats, helper únic als 9 camins Groq. Cada pas té mesura al DECISION-LOG. Són fixes, no refactors de fase.
  - `--timeout=600` de pytest no existeix (no hi ha `pytest-timeout`); s'ha usat el timeout de la crida.
  - Anthropic verificat via OpenRouter (clau del `.env` de dev sense crèdit); mateix model.
  - Tests de V concurrents amb la suite final a Bell-lloc run 2 (valor pessimista, anotat).
- **"Ja que hi som" detectats (NO fets):**
  - Centralitzar la crida httpx a Groq en un client únic (9 còpies). Ara hi ha un helper de payload + test estàtic.
  - Paral·lelitzar els 5 tipus de visió i les 23 probes (145 + 52 s en sèrie) → Tulipa ≈ 2 min. És AUDIT §3.2.
  - `web/api.py` picker Groq llista models retirats (UI).
  - `vision_probe` imposa `street_address`/`municipality` llegits d'una foto WhatsApp (Rubí → narrativa en castellà).
  - Geocode usa el nom de carpeta com a municipi (`C.Tulipa Cerdanyola`) → warnings sísmic/radó.
  - Carpetes `_validation/` (artefactes de debug) es minen com a dades del projecte.
  - La suite de tests deixa `docs/diagnostics/ai_pipeline_demo-project_<data>.md` sense versionar.
- **Dubtes per al Josep:**
  1. Fusionar `review/prod-audit-2026-08` a `production/g3dt-eva-v1` i pull a l'Eva? (8 commits, suite idèntica al baseline).
  2. Atacar la latència estructural (paral·lel + prefills bàsics primer) en una sessió pròpia?
  3. `gpt-4.1-mini` → GPT-5.6 Luna? Més barat i 128k de sortida, però p50 4,1 s i raonament: cal provar-lo al
     `deep_folder_classify` (5-14 crides en sèrie) abans de canviar res.
  4. La clau Anthropic del `.env` de dev no té crèdit — vols recarregar-la o passem dev a OpenRouter per defecte?
