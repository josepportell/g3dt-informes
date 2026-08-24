# Disseny (annex) — Tres botons, registre de jobs, taula d'estat i notificacions

**Data:** 2026-08-24 (nit) · **Branca:** `experiment/nivell-a-2026-08` · **Estat:** VALIDAT pel Josep en conversa (2026-08-24 nit); pendent de construir
**Annex de:** `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` (el disseny principal: contracte §4, mecànica §5, cache §6, fallback §7, UI §8, Fases 0-8 §9).
**Evidència de partida:** `docs/wizard-headless/fase8-e2e/_RESULTATS.md` (E2E real: 0 erroni-amb-confiança, paret 37-58 min) ·
`docs/audit/DIAGNOSTIC-PROD-2026-08-23.md` §2.1 (temps per fase de la via B) · micro-benchmark d'aquesta nit (§1).

---

## 0. Objectiu i abast

El wizard headless (Fases 0-8) llegeix bé (0 erroni-amb-confiança a Bell-lloc i Castellar) però triga 37-58 min el primer open.
Aquest annex **no intenta fer la lectura més ràpida a costa de la cura**: la treu del camí crític de l'Eva i li explica què passa.

Tres decisions del Josep que fixen el marc (2026-08-24 nit):

1. **La qualitat és el primer.** Cap palanca pot retallar el protocol del skill (Pas 0 context creuat, Pas 3 regles semàntiques, verificació).
2. **Només subscripció** de Claude (login del CLI), no clau API Anthropic. Volum esperat: **≤ 1 projecte/dia** (objectiu 10/mes → 20/mes).
   La capacitat multi-projecte/dia és un problema que voldríem tenir; no es dissenya ara.
3. **Tres botons** per a l'Eva: *Fer un informe des de zero* · *Preparar informe "per demà"* · *Enllestir informe preparat*, amb una
   **taula d'estat dels jobs** en llenguatge seu a sota, i **notificacions** (toast Windows + correu) quan un job acaba.

Fora d'abast: Tier B per nivell (Pendent A), Fase 8b (seleccions de taula → generador), forat 1 (fonts Python al consolidador),
multi-informe Tulipa. Tots segueixen al handoff `docs/_FOR-NEW-YOU-20260824-1910.md` §7.

## 1. Per què no s'ataca la latència retallant: descomposició mesurada (2026-08-24 nit)

`claude -p "Respon només amb la paraula: ok" --permission-mode bypassPermissions --output-format json`, 5 variants, WSL, claude 2.1.241:

| Variant | Paret | `duration_api_ms` | Context (cache create + read, tokens) | Cost |
|---|--:|--:|--:|--:|
| A · cwd = repo + 9 MCPs del Josep (com va córrer l'E2E) | 14,0 s | 3,0 s | 41k + 24k | $0,17 |
| B · cwd buit + MCPs | 8,0 s | 3,1 s | 18k + 24k | $0,08 |
| C · cwd buit + `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` | 4,8 s | 2,6 s | 12k + 30k | $0,05 |
| D · cwd = repo, sense MCPs | 4,2 s | 2,2 s | 33k + 32k | $0,14 |
| E · com C, tot cachejat | 3,9 s | 2,1 s | 0 + 42k | $0,009 |

**Lectura.** L'arrencada del CLI + una volta d'API són 4-14 s. Els ~110 s de "cost fix" d'un `.txt` de 3 línies (E2E) són el
**protocol del skill executat per Sonnet 5** (`"model": "sonnet"` als settings del Josep): llegir el skill (43 KB), l'inventari,
`_g3_templates.json`, el document, escriure el JSON atòmicament via Python, verificar — 6-10 turns × 10-15 s. La palanca
"prompt prim" (sense CLAUDE.md, sense MCPs) val 5-10 s i higiene de cost; **no és una palanca de latència**. A l'ordinador de
l'Eva (sense els MCPs del Josep) el cost fix ja serà el de la variant D.

Sumant totes les palanques que no toquen la cura (concurrència 3-4 amb un projecte sol, consolidació Python-first, no llegir
còpies Print-To-PDF), Castellar passaria de 37 min a **≈ 20-25 min** (estimat). No hi ha camí quality-preserving a "esperar
davant la pantalla". D'aquí els tres botons.

## 2. Els tres botons

M = mesurat · E = estimat a partir de mesures. Tots tres acaben igual: l'Eva revisa (30 s-uns minuts) i genera el `.docx` (2-35 s, M).

| Botó | Què fa la màquina | Avui | Amb les palanques d'aquest annex |
|---|---|---|---|
| **1 · Fer un informe des de zero** | sync xarxa→workspace + inventari + lectura `--only` per document + consolidació ‖ TEMPS 1 (Python + probes) → merge → **formulari** | 37-58 min (M, concurrència 2, dos projectes solapats) → 30-40 min sol (E) | 20-25 min (E) |
| **2 · Preparar informe "per demà"** | el mateix que 1 fins al merge, **tot escrit a disc**, ningú esperant; la pestanya es pot tancar; avís en acabar | 30-40 min (E) | 20-25 min (E) |
| **3a · Enllestir — res ha canviat a la xarxa** | delta-sync (s) + md5 local (s) + lectura 0 crides + consolidació cache + TEMPS 1 + merge → formulari | 1-3 min (E: TEMPS 1 es re-executa, cache només en memòria) | **≈ 30 s** (E, `auto_result` a disc) |
| **3b · Enllestir — K documents canviats/nous** | 3a + re-lectura només dels K (4-7 min cadascun, 2 en paral·lel) + **re-consolidació** | 15-20 min (E) | **6-9 min** (E, consolidació Python-first) |

Semàntica:

- **Botó 1** = botó 2 + botó 3 encadenats amb la pestanya oberta. Existeix perquè l'Eva ho demani així quan tingui pressa; no és
  un camí diferent.
- **Botó 2** és el mode per defecte que volem que faci servir: prem, tanca, torna quan li avisin (o l'endemà).
- **Botó 3** és l'únic que obre el formulari. Sempre comprova la xarxa abans (delta-sync, §4): amb gent tocant carpetes cada dia,
  el cas 3b serà el normal, no l'excepció. Per això la consolidació Python-first (§7.2) és la palanca que més importa.
- El botó 3 sobre un projecte **mai preparat** es comporta com el botó 1 (amb avís previ a la taula: "no està preparat — trigarà ≈ 30 min").

## 3. Registre de jobs (a disc, un per projecte)

### 3.1 Per què a disc

`_prefill_cache`/`_auto_result_cache` (`web/wizard_service.py:53-55`) són dicts en memòria: es perden quan l'Eva tanca la finestra
CMD del wizard (`docs/INSTALL-EVA-v1.md` §2.6, "no tanquis aquesta finestra"). La taula d'estat ha de dir "Preparat ahir 18:32 ✓"
l'endemà. I avui, reobrir un projecte mentre es llegeix llança un segon `run_lectura` (cap lock: `runner.py` només té
`_telemetry_lock`) → crides duplicades i cache en carrera (handoff §6).

### 3.2 Fitxer `validation/lectura/_job.json` (escriptura atòmica, com la resta de `--out`)

```json
{
  "schema_version": 1,
  "project": "3001621 CASTELLAR DEL VALLES",
  "button": "preparar",                       // desde_zero | preparar | enllestir
  "state": "reading",                         // §3.3
  "step": {"index": 2, "total": 4},
  "docs": {"total": 13, "done": 7, "cached": 0, "errors": 0, "current": ["PDF/ANNEXES/3001621_sondeig.pdf", "tall.pdf"]},
  "started_at": "2026-08-25T17:02:10", "updated_at": "2026-08-25T17:21:44", "finished_at": null,
  "estimate_s": {"remaining": 1500, "basis": "median_doc_s=264 from 13 local telemetry rows"},
  "result": null,                             // {"ok": true, "degraded": false, "fallback": null} en acabar
  "error": null,                              // {"code": "...", "detail": "..."} si state == error
  "pid": 12345, "claude_version": "2.1.241 (Claude Code)",
  "network_delta": null                       // {"changed": 2, "new": 1, "checked_at": "..."} (§4), omplert al carregar la taula
}
```

### 3.3 Estats màquina ↔ estats Eva

| `state` | Pas | Text a la taula (llenguatge Eva) | Estimació mostrada |
|---|---|---|---|
| `queued` | — | En cua | — |
| `syncing` | 1/4 | Copiant fitxers de la xarxa | < 1 min |
| `reading` | 2/4 | Llegint documents · **7/17** · ≈ 25 min restants | `⌈pendents / concurrència⌉ × mediana_doc` |
| `consolidating` | 3/4 | Consolidant el que ha llegit | ≈ 10 min (→ < 1 min amb §7.2) |
| `merging` | 4/4 | Preparant el formulari | < 1 min |
| `ready` | ✓ | Preparat (ahir 18:32) · *2 documents nous des de llavors → Enllestir ≈ 8 min* | del `network_delta` |
| `interrupted` | ⚠ | Interromput a 2/4 (12/17 llegits) · prem *Preparar* per continuar | resta = `total − done` |
| `error` | ✗ | No s'ha pogut preparar · avisat Eficients | — |
| `cancelled` | ⏹ | Aturat per tu | — |

Regles de redacció: arrodonir a 5 min ("≈ 25 min", mai "24 min 37 s"); sempre "restants", mai total; el comptador **7/17** va
en negreta perquè és el que més calma; **«Interromput» no és un error** — la cache per md5 fa que reprendre costi només els
documents que falten, i la taula ho ha de dir.

### 3.4 Transicions i garanties

- **Un job viu per projecte** (lock en memòria + `pid` al fitxer). Un segon *Preparar* o un *Enllestir* sobre un job `reading`
  **s'enganxa** a l'stream existent (§5.2), no en crea un altre. Cua serial entre projectes (concurrència de documents = 2 dins d'un job).
- **`interrupted`** es detecta en arrencar el servidor: `_job.json` amb `state` no terminal i `pid` que no existeix (o
  `updated_at` > 15 min enrere sense procés). No es reprèn sol: l'Eva prem *Preparar* i el runner recupera de la cache (§6 del disseny).
- **Cancel·lació** només explícita (`POST /api/cancel/{p}`, ja existeix a `web/api.py:209`): tancar la pestanya **no** cancel·la.
  Els fils del runner són `daemon` i els JSON de cache s'escriuen igualment (`web/lectura_service.py:338-341`).
- **Estimació autocalibrada**: mediana de `elapsed_s` de les files `mode == "only"`, `cached == false`, `rc == 0` de totes les
  `_telemetry.jsonl` **de l'ordinador de l'Eva** (`workspace_root()/*/validation/lectura/`). Amb < 5 files, defecte 270 s/doc i
  600 s de consolidació (mesurats aquí). Es recalcula en cada `lectura_doc`.

## 4. Delta-sync xarxa → workspace

Avui `sync_to_workspace` (`automation/sync_workspace.py:420-433`) copia un projecte **un sol cop**: si el workspace existeix,
`skipped (use force=True to re-sync)`. Amb carpetes compartides on gent hi toca cada dia, o el botó 3 treballa amb fitxers vells
(silenciós) o fa `force` i recopia tot per SMB (minuts, i deixa fitxers esborrats a la xarxa vius al workspace).

Nou `sync_delta(rel_path) -> {"new": [...], "changed": [...], "deleted": [...], "copied": n}`:

1. Recórrer la xarxa (`os.scandir` recursiu, mateixes exclusions que `copytree` + `validation/`).
2. Per fitxer: comparar **mida + mtime** amb el workspace; només si difereixen, md5 dels dos (evita llegir GB de fotos per SMB).
3. Copiar els `new`/`changed` (còpia a temporal + `os.replace`); els `deleted` de la xarxa → moure a `workspace/_esborrats/` (no perdre).
4. Retornar el delta. El runner ja invalida sol: `{doc}.json` amb `source_md5` diferent → re-lectura (`runner.py:389-392`);
   `_decisions.json` més antic que qualsevol `{doc}.json` → re-consolidació (`runner.py:453-463`).

Usos: botó 2 i 3 (pas 1/4); `GET /api/jobs` en mode `check=true` fa només els passos 1-2 (sense copiar) per omplir
`network_delta` a la taula ("2 documents nous → Enllestir ≈ 8 min"). Cost: segons (el punt 2 sense md5 és `stat` per fitxer).

Fitxers "tocats però iguals" (obrir i desar sense canviar bytes) → md5 idèntic → 0 re-lectures. `.msg`/`.docx` re-desats canvien
bytes → re-lectura d'aquell document. Acceptat.

## 5. UI: tres botons + taula d'estat

### 5.1 On

A la zona on avui hi ha "Començar amb aquesta carpeta" (`templates/validation/review.html:2310-2322`, estat IDLE `:4475`): el
navegador de xarxa es manté; el botó únic passa a ser tres. A sota, la taula. Bloc autocontingut com el de la Fase 7
(`/* === LECTURA HEADLESS (Fase 7) === */`), amb `G3DT_USE_LECTURA_HEADLESS=false` la UI actual no canvia.

### 5.2 Comportament

- **Preparar** → `POST /api/jobs/{p}?button=preparar` → 202 + `_job.json` inicial. La UI obre `GET /api/lectura-stream/{p}` només
  per pintar progrés; si l'Eva tanca la pestanya, el job segueix. En tornar, `GET /api/jobs` llegeix `_job.json`; si el job és viu
  i l'Eva clica la fila, la UI **s'enganxa** a l'stream (`?attach=true`: el servei re-emet l'estat actual i segueix).
- **Enllestir** → `POST /api/jobs/{p}?button=enllestir` → el servei fa delta-sync, `run_lectura` (que per cache fa 0 o K crides),
  TEMPS 1 (o `auto_result` a disc, §7.1), merge → i **només llavors** carrega el formulari (`prefills` com avui).
- **Des de zero** → `preparar` + `enllestir` encadenats amb la pestanya oberta.
- Taula: una fila per projecte amb `_job.json` als últims 30 dies (ordre: vius primer, després `updated_at` desc). Columnes:
  Projecte · Estat (text §3.3) · Progrés (7/17) · Temps restant · Preparat el · Acció (*Enllestir* / *Continuar* / *Veure error*).
  Refresc cada 5 s mentre hi hagi un job viu (`GET /api/jobs`), si no, en carregar.
- `GET /api/jobs` retorna també `network_delta` per als `ready` (§4 mode check), calculat com a molt un cop per minut.

### 5.3 Fora de la UI

Cap camp nou al formulari. Les seleccions de taula (Fase 8b) i els badges de 3 estats (Fase 7) no canvien.

## 6. Notificacions

### 6.1 Principi

**La taula és la veritat**; toast i correu són avisos. Cap canal és bloquejant: si falla, `logger.warning` i el job acaba igual.

### 6.2 Canals

| Canal | Quan | Contingut | Credencials |
|---|---|---|---|
| Taula (§5) | sempre | estat complet | cap |
| Toast Windows (`win11toast` o `powershell -c New-BurntToastNotification`; a WSL/dev, `notify-send` si hi és) | `ready`, `error` | «Projecte 3001621 preparat. Obre el wizard i prem Enllestir.» · clic → `http://localhost:8765/review.html` | cap |
| Correu a l'Eva | `ready`, `error` (un per job; **no** digest: ≤ 1 projecte/dia) | assumpte «G3DT · 3001621 llest per enllestir» · cos: carpeta + instrucció d'una línia | SMTP d'Eficients (§6.3) |
| Correu de telemetria a Eficients | `ready`, `error`, `interrupted` (detectat) | §6.4 | mateix |

Avisos només en acabar (o fallar), mai per pas: l'Eva "inquieta" ha de rebre **un** senyal per projecte.

### 6.3 SMTP d'Eficients (canal provisional)

- `eficients.cat` té MX propi (`mail.eficients.cat`) i SPF amb `include:spf.brevo.com` (verificat 2026-08-24). Preferència:
  **relay transaccional de Brevo** amb clau SMTP només d'enviament (revocable, no és cap contrasenya de bústia); si no hi ha compte
  Brevo actiu, bústia dedicada a `mail.eficients.cat`. **Remitent dedicat** (`g3dt@eficients.cat` o `notificacions@`), mai `josep@`.
- Config al `.env` del wizard: `G3DT_NOTIFY_SMTP_HOST/PORT/USER/PASS`, `G3DT_NOTIFY_FROM`, `G3DT_NOTIFY_TO_EVA`, `G3DT_NOTIFY_TO_EFICIENTS`
  (buit = canal desactivat). `G3DT_NOTIFY_TOAST=true|false`.
- **Provisionalitat explícita**, dita així a G3: «us deixem una bústia nostra; el dia que el vostre informàtic ens doni un SMTP, canviem
  4 línies del `.env`». Respecta el principi "el companion és seu, no una dependència nostra" (CLAUDE.md d'Eficients) sense bloquejar-nos.
- Lliurabilitat: 1-5 correus/dia amb SPF/DKIM alineats; el primer dia l'Eva marca el remitent com a segur a Outlook (hi treballa: 11 `.msg`
  als projectes de referència).
- Alternativa sense credencials, **experiment presencial de 10 min, no pla A**: enviar des del seu Outlook via COM (`win32com`),
  d'ella a ella. Incerteses: el "nou Outlook" no té COM; l'Outlook clàssic pot mostrar l'avís «un programa intenta enviar un
  correu», que mata el mode desatès.

### 6.4 Telemetria a Eficients: transparent, mínima, útil

El Josep no pot veure què passa a l'ordinador de l'Eva; l'única visibilitat fins ara ha estat demanar-li l'arxiu de logs
(`/mnt/c/claude/g3dt/dades-eva/`, agost). Aquest correu ho substitueix.

- **No BCC**: el BCC és la forma opaca. Un **correu propi** «Eficients · telemetria G3DT · 3001621 · OK» (o CC visible), que G3 sap que
  existeix.
- **Contingut** (minimització): expedient, nom de carpeta (als 8 de referència: expedient + municipi, sense persones), botó, estats i
  durades per pas, `n` documents per tipus (6 PDF, 1 xls, 2 msg…), files de `_telemetry.jsonl` **sense nom de fitxer** (índex, extensió,
  mida, `elapsed_s`, `rc`, `timeout`, `cached`), `claude_version`, versió del repo (`git describe` o fitxer `VERSION`), `degraded`/`fallback`.
  En `error`: el nom del fitxer que ha fallat i les últimes 30 línies del log del CLI amb rutes i noms de persona sanejats (regex sobre
  `[A-Z]{2,} [A-Z]{2,}` és insuficient — llista explícita: substituir noms de fitxer per `doc_{i}` abans d'incloure res).
  **Mai** valors de camps ni cites.
- **Base legal** (lectura no jurídica del RGPD/LOPDGDD, a confirmar si el Josep vol): manteniment del servei contractat / interès
  legítim amb dades mínimes; condicions: **transparència** (una línia a `docs/INSTALL-EVA-v1.md` i al document de servei signat amb G3:
  «el wizard envia a Eficients un avís tècnic per projecte —expedient, durades, errors— per al manteniment») i **encàrrec de
  tractament** (art. 28) amb G3 si no existeix — perquè ja tenim els seus 8 projectes reals al nostre disc, que pesa molt més que aquest correu.
- Si G3 no ho vol: `G3DT_NOTIFY_TO_EFICIENTS=` buit i el correu de l'Eva segueix igual.

## 7. Palanques que fan curt el botó 3 (sense tocar la lectura)

### 7.1 `auto_result` a disc

TEMPS 1 (FileMiner 5 s + groq_miner 10 s + probes ConceptScout 78 s + deep_folder 17 s + APIs HTTP 31 s, mitjanes del diagnòstic
23/08) es re-executa a cada arrencada del servidor. Persistir `AutoExtractionResult` a `validation/_auto_result.json` amb
`inputs_md5` (md5 dels fitxers d'entrada que ha fet servir) i TTL 30 dies per als HTTP (ICGC/Cadastre). Botó 3a: de 1-3 min a ≈ 30 s.

### 7.2 Consolidació Python-first

`merge_degradat` (`runner.py`) ja és una consolidació determinista. Invertir l'ordre: Python consolida **sempre**; només els
camps amb **conflicte real** entre fonts (valors diferents amb la mateixa autoritat) o amb regla semàntica no codificable
(cota relativa/absoluta, client supersedit) van a una crida `--consolida --only-fields a,b,c` curta. Sense conflictes → 0 crides.
Manté el validador tal qual (n30/litologia mai segurs; `segur` només amb 2 fonts o g3_templates ≥ 0,9). Re-consolidació de 10 min → < 1 min
(E) en el cas habitual. **Cal validar contra l'or** (`compare_consolida.py`, escalars i taules, 2 projectes) abans d'adoptar-la:
és l'única peça d'aquest annex que toca la qualitat, i només s'accepta amb 0 erroni-amb-confiança.

### 7.3 Runner: `--model` fixat i `--output-format json`

- `--model sonnet` explícit a `_run_claude` (`runner.py:225`): a l'ordinador de l'Eva el defecte del CLI pot ser un altre → velocitat, cost
  i comportament diferents dels mesurats.
- `--output-format json` → capturar `num_turns`, `duration_api_ms`, `total_cost_usd`, `modelUsage` a `_telemetry.jsonl`. Sense això,
  "on va el temps" per document és deducció. El `result` text del JSON es desa al log com fins ara.

### 7.4 No es fa

- No retallar documents per temps (fotografies, LAB-SIG): només duplicats per md5 (ja) i còpies Print-To-PDF quan hi ha el
  `PDF/ANNEXES/` equivalent (skill §Pas 2, línia 116), i només si el comparador d'or no perd cap camp.
- No "prompt prim" com a palanca de latència (§1); sí `--strict-mcp-config` per higiene quan es provi a Windows.

## 8. Subscripció pura: residus d'API a TEMPS 1 (decisió pendent)

Amb `skip_vision=True` (lectura OK) el merge salta la visió per tipus (Anthropic/OpenAI). Però `auto_extract` **encara crida Groq**:
probes ConceptScout, `groq_miner` (Fase 0.4), ortofoto (`auto_extract¹`). Per ser "només subscripció" cal decidir, per peça:

| Peça | Avui | Opcions |
|---|---|---|
| Probes ConceptScout (78 s, Groq) | classifica fitxers no-text per a la via B | amb la via A el consolidador ja llegeix tots els documents → **candidata a desactivar** quan la lectura és OK |
| `groq_miner` (10 s) | gap-filling de text | idem, redundant amb la lectura |
| Ortofoto (dins `auto_extract¹`, 5-6 crides Groq) | adjacents/entorn | enrutar a `claude -p` (barat: 1 crida) o mantenir Groq (clau gratuïta) |
| Visió per tipus (140 s) | saltada amb `skip_vision` | només en fallback de la lectura |

Decisió del Josep en construir la Fase 13. Criteri: cap d'elles pot **guanyar** un camp contra la lectura (memòria
`concept_format_per_concept_priority`); si no aporten camps que la lectura no tingui, fora.

## 9. Restriccions que es mantenen

- Via B intacta (`automation/ai_pipeline/`, `web/vision_groq.py`, `auto_extractor.py`, `web/vision_fast.py`): PROHIBIT editar-los.
  `auto_result` a disc (§7.1) es fa des de `lectura_service`/`wizard_service`, envoltant, no dins d'`auto_extractor.py`.
- Flag `G3DT_USE_LECTURA_HEADLESS=false` → prod actual idèntica (suite: 32 failed idèntics).
- Validador `contract.py` intacte. `merge_degradat`/Python-first no poden marcar `segur` fora de les regles actuals.
- Mai proposar pull/merge a l'Eva (memòria `feedback_no_pull_eva_success_criterion`). Aquest annex és feina de branca.
- No escriure a `/mnt/c`; E2E a `~/g3dt-e2e/projectes/`. No córrer dues lectures del mateix projecte (ara el lock ho impedeix).

## 10. Pla de construcció (continua la numeració del disseny principal)

Mateix mètode que les Fases 0-8: codi amb Sonnet 5 per fase, judici i E2E a la sessió principal; commit per peça (`feat(g3dt): …`);
suite completa abans de cada commit (no `| tail -1`).

| Fase | Peça | Fitxers | Tests / acceptació |
|---|---|---|---|
| **9** | Instrumentació runner: `--model sonnet`, `--output-format json` → telemetria amb turns/api_ms/cost. **Remesura Castellar sol** (`validation/lectura/` esborrat), concurrència 2 i 3. Addendum datat a `fase8-e2e/_RESULTATS.md`. | `automation/lectura/runner.py` | test que el JSON del CLI es parseja i cau bé si no és JSON; 2 runs reals; xifres a l'addendum |
| **10** | Registre de jobs: `automation/lectura/jobs.py` (`_job.json`, estats §3.3, lock per projecte, detecció `interrupted`, estimació autocalibrada), `GET /api/jobs`, `POST /api/jobs/{p}?button=`, `attach` a `lectura_service` | nou `jobs.py`, `web/lectura_service.py`, `web/api.py` | tests: transicions, lock (2n POST → 409 + attach), `interrupted` per pid mort, estimació amb 0/5/50 files; suite verda |
| **11** | Delta-sync (§4) + mode `check` | `automation/sync_workspace.py` (funció nova; `sync_to_workspace` intacta) | tests amb arbre temporal: new/changed/deleted, "tocat però igual" → 0 canvis; mida+mtime abans de md5 |
| **12** | Consolidació Python-first (§7.2) | `runner.py` (`merge_degradat` → `consolidate_python`), skill v1.4 (`--only-fields`) | **comparador d'or escalars + taules a Bell-lloc i Castellar: 0 ERR de fons**; test de conflicte sintètic → crida `--consolida` |
| **13** | `auto_result` a disc (§7.1) + decisió sobre residus Groq (§8) | `web/lectura_service.py`, `web/wizard_service.py` (envoltant) | test: 2a càrrega sense xarxa ni Groq → prefills iguals; invalidació per `inputs_md5` |
| **14** | UI: tres botons + taula (§5) | `templates/validation/review.html` (bloc autocontingut; Sonnet: grep + rangs, mai llegir-lo sencer) | Playwright: Preparar → fila `reading` amb 1/13 → tancar pestanya → reobrir → `attach`; `ready` amb delta → text "2 documents nous"; 0 errors de consola |
| **15** | Notificacions: `automation/lectura/notify.py` (toast, SMTP Eva, SMTP telemetria sanejada), config `.env` | nou `notify.py`, `web/lectura_service.py` (hooks a `ready`/`error`) | tests amb servidor SMTP fals (`aiosmtpd`/`smtpd` local): 2 correus, cap nom de fitxer a la telemetria, canal buit = res; toast simulat |
| **16** | E2E dels tres botons (Castellar sol, còpia local amb "xarxa" simulada = segona carpeta): botó 2, tocar 2 fitxers, botó 3 → temps de la taula §2 remesurats; addendum a `_RESULTATS.md`; entrada DECISION-LOG | docs | xifres reals per a 1, 2, 3a, 3b |
| **17** | Windows presencial: `claude` CLI natiu + login, `schtasks /sc onlogon` (servidor viu sense finestra), toast real, experiment Outlook COM, `--strict-mcp-config` | `docs/INSTALL-EVA-v1.md` (nova secció, línia de transparència §6.4) | checklist presencial; **cap pull a l'Eva fins que el Josep ho decideixi** |

Ordre justificat: 9 primer perquè totes les estimacions de la taula i de l'addendum depenen de mesures fiables; 10-11 són el fonament dels
tres botons; 12-13 fan curt el botó 3; 14-15 són el que veu l'Eva; 16 mesura; 17 és presencial.

## 11. Criteris d'acceptació de l'annex

- Botó 3a ≤ 1 min de màquina; botó 3b ≤ 10 min amb 2 documents canviats (Castellar, mesurat a la Fase 16).
- Tancar la pestanya durant *Preparar* no perd res: en reobrir, la fila mostra el progrés real i s'hi enganxa.
- Reiniciar el servidor a mig job → fila `interrupted` amb `done/total` correcte; *Preparar* reprèn amb 0 crides pels documents ja llegits.
- Mai dos `run_lectura` del mateix projecte alhora (test de lock).
- Consolidació Python-first: 0 erroni-amb-confiança contra l'or als 2 projectes (si no, es queda la crida `--consolida` sencera).
- Correu de telemetria: cap nom de persona ni valor de camp (test amb un projecte sintètic amb noms a tots els fitxers).
- Amb `G3DT_USE_LECTURA_HEADLESS=false`, cap canvi visible ni a la UI ni a la suite.

## 12. Decisions obertes per al Josep

1. **Sostre de la subscripció**: 1 projecte/dia ≈ 75 min de sessió Sonnet 5 — molt per sota del que ja s'ha fet aquí (2 projectes,
   ~150 min en 1 h de paret, 0 errors de límit). Prova barata quan es vulgui: encuar els 8 de referència una nit.
2. **Contingut del correu de l'Eva**: només expedient, o expedient + carpeta (porta municipi).
3. **Residus Groq a TEMPS 1** (§8): desactivar probes/groq_miner quan la lectura és OK, o mantenir-los.
4. **Encàrrec de tractament** amb G3 (§6.4) i la línia de transparència al document de servei.
5. **Servidor viu a Windows**: finestra CMD oberta (com avui) vs. tasca d'inici de sessió oculta (Fase 17, presencial).
6. **Brevo vs. bústia** a `mail.eficients.cat` per al remitent dedicat.

## 13. Riscos

- **Leakage**: tot valida re-execució; el test real segueix sent una carpeta nova de l'Eva. Els tres botons no ho canvien.
- **Python-first** és l'única peça que toca la qualitat; queda darrere del comparador d'or i es descarta si perd.
- **Delta-sync per SMB** amb carpetes grans (fotografies): `stat` de milers de fitxers pot trigar; si passa de 10 s, cache de l'arbre
  (mida+mtime) i comprovar només els directoris amb mtime canviat.
- **Toast a Windows** depèn de la sessió d'usuari activa; si el servidor corre com a tasca sense sessió, no es veu → el correu cobreix.
- **Correu = dependència d'Eficients** (provisional, §6.3); si cau, la taula segueix sent la veritat.

---
*Fi annex 2026-08-24. Tres botons + registre de jobs + taula d'estat + notificacions: la lectura no s'escurça, surt del camí crític.*
