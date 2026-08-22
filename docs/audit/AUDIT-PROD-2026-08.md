# Auditoria interna de producció — G3DT (agost 2026)

**Data:** 2026-08-22 · **Branca:** `review/prod-audit-2026-08` (in-place a `g3dt-prod/`, prod intacte)
**Evidència:** logs reals de l'ordinador de l'Eva, 14 dies (2026-05-04 → 2026-07-23), 8.953 línies.
Font: `/mnt/c/claude/g3dt/dades-eva/g3dt.log.batch.zip` + `g3dt.log.txt`.
Perfil reproduïble: `scripts/profile_eva_logs.py` → `docs/audit/eva-logs-profile-2026-08-22.md`.

**Per què aquesta auditoria:** l'Eva diu que "no va bé" però no concreta, no dona hora ni contracta
manteniment. Els logs són l'única veritat disponible. Tot el que segueix surt d'allà i del codi
de `production/g3dt-eva-v1` (commit `1f1d7fd`), no de suposicions.

---

## 1. Què ha passat de veritat (quadre)

| Mètrica | Valor |
|---|--:|
| Projectes reals oberts | **19** — cap és dels 7 de `reference-material/` |
| Obertures al wizard | 31 |
| Informes generats i copiats a la xarxa | **14** |
| Crash en generar informe | 4 (Bellpuig ×3, Ivars ×1) — `None depth`, fixat `b579ef5` (23 jul) |
| Crash en carregar prefills | **4** (Can Mir Rubí, 23+25 jun) — `UnicodeDecodeError cp1252` — **NO fixat** |
| Espera dels prefills | **mediana 7,1 min, màxim 15,9 min**; ≥5 min en 21 de 28 obertures |
| Projectes sense cap informe | Tulipa (0/3), Bellpuig (0/2), Can Mir Rubí (0/4), Montardit (0/1), Ivars (0/1) |

Els 14 dies de logs són els dies que l'Eva ha obert el wizard. Entre el 4 de maig i el 23 de juliol
ha fet servir el sistema **14 dies de ~55 laborables**; després del 25 de juny, només 2 dies (8 i 23 jul).

---

## 2. Troballes (per impacte)

### T1. La lectura visual del PENETROS.pdf (DPSH) falla a tota la cadena

| Proveïdor (tipus `dpsh`) | OK | FAIL | % FAIL |
|---|--:|--:|--:|
| Anthropic `claude-sonnet-4-6` (backend per defecte per a `dpsh`) | 2 | 23 | **92%** |
| OpenAI `gpt-4.1-mini` (fallback 1) | 13 | 10 | 43% |
| Groq (fallback 2) | 2 | 8 | 80% |

Plànol, projecte d'arquitecte i sondeig: 0% FAIL. El problema és específic del DPSH i té **tres
causes de codi, totes a `web/vision_groq.py`**:

1. **Anthropic: parser fràgil.** 29/29 fallades són `Expecting value: line 1 column 1 (char 0)`
   després d'un `200 OK`: Claude respon amb una frase de text abans del JSON (o sense ``` fences)
   i el codi fa `json.loads(text)` directe (`_call_anthropic_vision`, l. ~626-640). El system
   prompt (`EXTRACTION_SYSTEM_PROMPT`) no diu mai "només JSON, sense text previ". No es fa servir
   prefill d'assistant ni extracció `{…}`. Cada fallada costa ~55-65 s (la resposta sencera) i 0 valor.
2. **`max_tokens=4096` no hi cap.** El schema demanat (`prompts.py` l. 23-26) ocupa ~30 tokens per
   lectura; 4 penetros × 40 lectures ≈ 4.800 tokens. Les fallades d'OpenAI són totes de JSON
   truncat (`Unterminated string`, `Expecting ',' delimiter`, `Expecting property name`). No es
   comprova `stop_reason`/`finish_reason`; el truncament es tracta com a error de parseig.
3. **Reintent d'un error determinista.** OpenAI reintenta 2-3 cops el mateix truncament
   (~150 s cada un). Una obertura amb DPSH gran pot perdre **1 min (Anthropic) + 5-8 min (OpenAI)**
   i acabar sense resultat. Les obertures de 13-16 min del 23 de juliol són exactament això.

Groq: el model `llama-4-scout` mort (162 errors HTTP) + `Too many images provided` (27×, el model
només accepta 5 imatges i se li envien més). El fix `2e2abe7` (→ `qwen/qwen3.6-27b`) **no està
verificat**: a les 17:49 del 23 jul el log encara mostra `llama-4-scout`; la còpia del log acaba
a les 17:51, abans del darrer commit (17:59).

**Valor en joc:** el DPSH ja ve de l'Excel (`dpsh_extractor`). La visió del PENETROS només aporta
validació N20 vs Excel i les cotes de rebuig anotades a mà ("R 1,35"). Quan falla, l'informe surt
igualment — però l'Eva ha esperat 8 minuts per res.

### T2. Crash de prefills per encoding Windows (NO fixat)

`web/wizard_service.py:2172` (`_merge_prefills`): `json.loads(fm_path.read_text())` sense
`encoding`. A Windows, `read_text()` usa cp1252; `file_mapping.json` s'escriu en UTF-8
(`file_scanner.py`, `api.py`, `ensure_ascii=False`). Qualsevol nom de fitxer amb un caràcter fora
de cp1252 (byte `0x8d`) fa petar la càrrega de prefills **abans de mostrar res** — el wizard
queda buit. Can Mir Rubí: 4 intents en 2 dies, 0 èxit. Hi ha **11** `read_text()` sense encoding
a `automation/` + `web/` (llista a §5). La sessió del 23 jul va concloure "única modalitat de
crash": era fals.

### T3. L'espera és LLM, no Python

Atribució dels ~180 min d'espera HTTP en 28 obertures (mediana 7,1 min/obertura):

| Proveïdor | Minuts | Crides | On van |
|---|--:|--:|---|
| Groq | 72 | 1.472 | 301 OK (`concept_scout.vision_probe`, 24 min) · **320 rate-limited (14 min de sleep)** · 189 errors HTTP (6 min) · `groq_miner` rate-limited (4 min) |
| OpenAI | 59 | 438 | 129 visió OK (24 min) · **22 min en DPSH truncat + reintents** · 265 `deep_folder_classify` (9 min) |
| Anthropic | 49 | 132 | **28 min en 29 fallades de parseig** · 13 min en 20 OK · Tier 3 fotos · LLM synthesis (2 min) |

Tot el Python (SmartScan, FileMiner, ConceptScout, geocode, Cadastre, ICGC) suma **< 30 s per
obertura**. "Trobar les dades a la documentació" no és car: el que és car és (a) una cadena de
visió DPSH trencada i (b) classificar visualment cada foto/imatge del projecte amb Groq en
règim de rate-limit (320 esperes de 5 s).

### T4. Hem validat sobre un corpus que l'Eva no fa servir

Tota la mètrica d'extracció (benchmarks, `eva_reference_values.json`, 1.023 tests) viu sobre 7
projectes de 2025. Els 19 reals venen de `\\192.168.1.11\geologia\{INFORMES GEOTÈCNICS BCN,
Informes geotècnics-LLEIDA, INFORMES FETS LLEIDA NOVA NOMENGLATURA 2014}`. Només en tenim una
còpia completa: **Tulipa** (`/mnt/c/claude/g3dt/projectes-debug/`, 0/3 informes OK).

### T5. Estat post-visita (23 jul) sense verificar

Cap log posterior a les 17:51 del 23 jul. No sabem si el pull final (`b579ef5`) es va fer, si el
servidor es va reiniciar, ni si Ivars/Bellpuig han generat mai informe. Des del 25 de juny l'Eva
ha obert el wizard 2 dies.

---

## 3. Què hem plantejat malament (diagnòstic, pendent de confirmar amb Tulipa)

1. **Visió DPSH com a pas del camí crític.** L'Excel ja té els N20. La visió del PENETROS hauria
   de ser (a) opcional/en segon pla, o (b) com a mínim robusta: prompt JSON-only, `max_tokens`
   dimensionat (8-16k) o sortida compacta (`[[0.2,15],[0.4,18],…]`), sense reintents del mateix
   error, i aturada de la cadena de fallbacks quan el primer ja ha retornat JSON truncat.
2. **Classificar-ho tot visualment abans de mostrar res.** `concept_scout.vision_probe` passa
   cada imatge per Groq (i Tier 3 per Claude) en sèrie, amb rate-limit. És la fase més cara en
   temps i la que menys camps de l'informe omple. Candidata a executar-se *després* de mostrar els
   prefills bàsics, o només sota demanda.
3. **Cap guardarail de temps.** No hi ha pressupost de temps per obertura ni "mostra el que
   tens" als 60 s. L'Eva espera 7 min mirant un spinner.
4. **Sense telemetria d'èxit.** No sabem quants camps ha corregit l'Eva a cada projecte
   (`user_data.json` vs prefills). És la mètrica que diria si el sistema "va bé".

---

## 4. Pla de fixes (proposta, pendent de decisió del Josep)

| # | Fix | Fitxer | Esforç | Impacte |
|---|---|---|---|---|
| F1 | `encoding='utf-8'` als 11 `read_text()` + test cp1252 | `wizard_service.py`, `image_manager.py`, `config.py`, `validation/schemas.py`, … | 30 min | desbloqueja Can Mir Rubí i qualsevol projecte amb noms "rars" |
| F2 | Anthropic: system prompt JSON-only + prefill `{` / extracció `{…}` robusta | `vision_groq.py`, `prompts.py` | 1 h | DPSH via Claude de 8% → ~100% OK; −1 min/obertura |
| F3 | `max_tokens` per tipus (`dpsh` 16k) + detectar `stop_reason=max_tokens` → no reintentar, no fer fallback | `vision_groq.py` | 1 h | −5-8 min en projectes grans; elimina el 43% FAIL d'OpenAI |
| F4 | Groq: limitar a 5 imatges/crida; backoff real al rate-limit (o desactivar `vision_probe` per defecte) | `vision_groq.py`, `concept_scout/vision_probe.py` | 1 h | −20 min/14 dies; menys soroll |
| F5 | Verificar a l'ordinador de l'Eva: pull `b579ef5`, `.env` Groq, reinici servidor | presencial / remot | — | T5 |

F1-F4 són canvis acotats, testejables amb els 7 projectes + Tulipa, sense tocar el pipeline.
**No** proposo tocar `experiment/ai-pipeline` ni refactors de fases fins tenir el cronòmetre de
Tulipa (§3 punt 2) i, si dilluns hi ha sort, 2-3 carpetes més de l'Eva.

---

## 5. Annex — `read_text()` sense encoding (prod)

```
automation/image_manager.py:661, 677
automation/mapillary_client.py:539
automation/config.py:73
automation/validation/schemas.py:15, 218, 325
automation/fix_template_and_image_width.py:52
automation/google_satellite.py:55
web/wizard_service.py:2151, 2172   ← crash real (4×)
```

## 6. Annex — Preguntes per a l'Eva (quan sigui possible)

1. Envia'ns el `C:\g3dt-ia\g3dt.log.txt` actual (1 fitxer, 1 minut) — ens diu si el 23 jul va quedar bé.
2. 2-3 carpetes de projecte recents en zip (les que t'hagin donat més feina).
3. De cada informe generat: quants camps vas haver de canviar al wizard? (o millor: `user_data.json` de la carpeta `validation/`).
