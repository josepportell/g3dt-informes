# Disseny — Crida headless des del wizard + UI de candidats (Pendent B via A)

**Data:** 2026-08-24 · **Branca:** `experiment/nivell-a-2026-08` · **Estat:** PROPOSTA (pendent de validació del Josep)
**Prerequisits llegits:** skill `g3dt-llegir-projecte` v0.9 · `docs/golden-read-taules/_RESULTATS.md` ·
`docs/_FOR-NEW-YOU-20260824-1500.md` §2B · patró `claude -p` de `web/vision_fast.py:172-196` i `wizard_service.start_vision_cli`.

---

## 0. Objectiu i abast

Quan l'Eva selecciona un projecte al wizard, el sistema:

1. Omple **a l'instant** (< 5 s, 0 $) els camps segurs de les 5 plantilles G3 (`automation/g3_templates.py`).
2. Llança **Claude Code headless** (`claude -p` + skill v1.0) — una crida per document — que llegeix els documents
   no-deterministes i escriu candidats amb font i cita.
3. Consolida tot en un `_decisions.json` (15 escalars + bloc `tables`) amb **3 estats**: `segur` / `candidats` / `no_trobat`.
4. La UI mostra cada camp amb el seu estat, un popup amb candidats (valor + font + cita + regla), i el mateix per a
   **files de taula** (n30 amb registre, litologies amb 2-3 redaccions, N.F. humitat|aigua).

**Fora d'abast (explícit):**
- **Tier B per nivell** (K, C sísmic, γ/c/φ/E) — Pendent A; només s'hi reserva lloc al contracte (§4.5).
- **Multi-informe (Tulipa, 2 informes/expedient)** — canvi de model de dades del wizard NO dissenyat; decisió explícita
  amb el Josep abans (handoff 24 §2B).
- **Desplegament a casa l'Eva** — decisió del Josep, presencial. MAI proposar pull/merge a l'Eva.

**Criteri únic que mana:** erroni-amb-confiança = 0. Davant del dubte, el sistema baixa d'estat, mai omple "perquè segur que és això".

---

## 1. Restriccions dures (no negociables)

| Restricció | Font |
|---|---|
| PROHIBIT editar `automation/ai_pipeline/`, `web/vision_groq.py`, `automation/auto_extractor.py`, `web/vision_fast.py` (llegir-ne patrons, sí) | handoff 24 §4 |
| La via B (Groq/Anthropic API) queda intacta com a fallback quan `claude -p` falla o no hi és | handoff 24 §2B |
| `read_text`/`write_text` sempre amb `encoding="utf-8"` (guard F1 suspèn la suite) | handoff 24 §7 |
| n30 MAI `segur`; litologia MAI `segur` per a la cadena literal | skill v0.9 Pas 3b |
| Skill: si es toca, +0.1 de versió i una línia de changelog | handoff 24 §4 |
| `docs/golden-read*` són evidència tancada: es fan servir com a FIXTURES de test, mai es reescriuen | handoff 24 §4 |
| Dades reals a `/mnt/c/claude/g3dt/projectes/` (mai escriure a /mnt/c); `reference-material/` només com a fixtures de tests | handoff 24 §5 |

---

## 2. Arquitectura de la seqüència (SSE en 2 temps + consolidació)

Nou endpoint SSE `GET /api/lectura-stream/{p}` (el `/api/prefills-stream` existent NO es toca — és la via B).
La UI tria l'endpoint segons el flag `G3DT_USE_LECTURA_HEADLESS`.

```
Eva selecciona projecte
        │
        ▼
┌─ TEMPS 1 (paral·lel, ~5 s) ──────────────────────────────────────────┐
│  a) g3_templates.read_project()  → event `templates_fields`          │
│     (camps segurs de les 5 plantilles G3, amb cel·la + cita, 0 $)    │
│  b) auto_extract() [INTACTE]     → events `step` existents           │
│     (ICGC, Cadastre, geocode, adjacents, lab sulfats, DPSH escalars) │
│     ⚠ amb lectura headless activa, la fase de VISIÓ API se salta     │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ TEMPS 2 (headless, incremental) ────────────────────────────────────┐
│  c) Inventari Python → cua prioritzada de documents (§3.1)           │
│     event `lectura_inici` {n_claude, n_python, docs[]}               │
│  d) Per document (concurrència 2, cua per prioritat):                │
│       claude -p "/g3dt-llegir-projecte PATH --only DOC               │
│                  --inventory validation/lectura/_inventory.json      │
│                  --out validation/lectura"                           │
│       → escriu {doc}.json → event `lectura_doc` {doc, n_signals}     │
│     timeout/retry/telemetria per crida (§5); cache per md5 (§6)      │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ CONSOLIDACIÓ (1 crida) ─────────────────────────────────────────────┐
│  e) claude -p "/g3dt-llegir-projecte PATH --consolida"               │
│     llegeix validation/lectura/*.json (inclòs _g3_templates.json)    │
│     aplica el Pas 5 (independència de fonts, autoritat, duplicats)   │
│     → escriu _decisions.json → event `decisions` (payload sencer)    │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
  f) merge final (Python): user_data > lectura segur > lectura candidat-1
     > via B/auto > defecte  → event `prefills` (nom existent)
```

**Per què crida-per-document i no una crida per projecte?** El skill ho preveu així («una crida per document = forma
headless de producció», Arguments del skill). Guanys: SSE incremental (l'Eva veu camps aparèixer), timeout petit per
crida, un document que falla no perd la resta, telemetria per document, paral·lelitzable. Cost: la consolidació es fa
en una crida final NOVA (no validada per la lectura d'or, que era mono-agent) → mitigació al §9 Fase 8 (re-validació
contra `_decisions.json` d'or). **Alternativa validada de reserva:** mode `G3DT_LECTURA_MODE=projecte` = una sola crida
sense `--only` (la forma exacta de la lectura d'or); es manté implementat com a camí B del runner perquè costa 10 línies.

**Cancel·lació:** reutilitza `mark_cancelled`/`is_cancelled` existents. El runner comprova la flag abans de cada spawn
i mata els processos vius en cancel·lar (Windows: `proc.kill()`; POSIX: `killpg`). Checkpoints: post-inventari,
entre documents, pre-consolidació, pre-merge.

---

## 3. Inventari i enrutament de documents (Python, determinista)

### 3.1 Qui llegeix què

Regla de la via A: **Claude només llegeix els documents que Python no llegeix deterministament.**

| Grup | Documents | Lector | Prioritat cua |
|---|---|---|---|
| Plantilles G3 | pressupost PDF, fitxa camp, comanda lab, PLAN_COST | `g3_templates.py` (0 $) | — (instantani) |
| Excel DPSH | `ANNEXES/*_DPSH.xls` | g3_templates (escalars + peu B79-B82) **i** claude `--only` (N.F./Nivells per COLOR files 79-80, `formatting_info=True`) | 3 |
| Annexos Eva | `{exp}_sondeig.pdf`, `tall.pdf`, `{exp}_DPSH.pdf` (cotes per punt), `pl. situació` | claude `--only` (lectura visual) | 1, 4, 2, 9 |
| Camp | `PENETROS.pdf` (manuscrit + albarà TPS), full de camp manuscrit | claude `--only` | 7, 10 |
| Laboratori | GTL PDF (`*-GTL-*.pdf`) | claude `--only` | 5 |
| Arquitecte | `A.01.pdf` / plànols, projecte/memòria | claude `--only` | 6 |
| Correus | `*.msg` (cos + adjunts nous) | claude `--only` | 8 |
| Cadastre / coordenades | consultes cadastrals PDF, `COORDENADES.txt` | auto_extract existent (Python); claude només si l'inventari no hi troba lector | 11 |
| Fotos | `FOTOGRAFIES/` | fora de la lectura (photo selection existent) | — |

Volum esperat per projecte (calibrat amb `docs/golden-read/`: Bell-lloc 27 fonts, Rubí 19, Alcoletge 20): **~8-14
crides claude** un cop descomptats plantilles G3, cadastre, coordenades i fotos.

### 3.2 `_inventory.json` (nou, escrit per Python abans de cap crida)

Conserva el context creuat que el mode `--only` perdria (duplicats, relacions entre documents — les deteccions
espontànies de la lectura d'or com el full de camp de Linyola dins del PENETROS de Bell-lloc necessiten saber què més
hi ha a la carpeta):

```json
{"generated": "...", "project": "...",
 "files": [{"path": "PENETROS.pdf", "size": 12345, "md5": "…", "mtime": "…",
            "route": "claude|python|skip", "doc_type_hint": "camp_penetros", "priority": 7}],
 "duplicates": [["a.pdf", "a amb punts.pdf"]]}
```

Els md5 permeten: detecció de duplicats abans de gastar crides, i la cache del §6.

---

## 4. Contracte de dades — `_decisions.json` schema v1

### 4.1 Problema a resoldre: dos dialectes als fixtures d'or

- Escalars (`docs/golden-read/*/_decisions.json`): `status` / `source`.
- Taules (`docs/golden-read-taules/*/_tables_decisions.json`): `estat` / `font`.

**Decisió: es normalitza al dialecte català `estat` / `font` / `quote`** (coherent amb la prosa del skill: "3 estats",
"font i cita"). El skill v1.0 emet NOMÉS aquest dialecte. Els fixtures d'or NO es reescriuen: un adapter de test
(`tests/…/adapter`) mapeja el dialecte antic al nou per fer-los servir com a fixtures.

### 4.2 Escalars — claus PLANES (22)

`lab` i `cte` (niuats als fixtures d'or) s'aplanen, perquè el wizard és pla:

`expedient, client_name, street_address, municipality, architect_name, architect_company, building_type, num_floors,
superficie_parcela, field_date, cota_referencia, num_soil_levels, num_dpsh_tests, utm_x, utm_y, referencia_catastral,
lab_testing_company, lab_sample_id, lab_depth, lab_location, cte_edificacio, cte_sol`

(`superficie_construida` NO és una clau de `fields`: viu a `tables` amb components+total, com als fixtures d'or —
correcció Fase 0 sobre la primera redacció d'aquest document.)

### 4.3 Estructura

```json
{
  "schema_version": 1,
  "project": "4001612 BELL-LLOC",
  "generated": "2026-08-24T12:00:00",
  "skill_version": "1.0",
  "fields": {
    "expedient": {
      "estat": "segur",
      "value": "4001612",
      "candidates": [{"value": "4001612", "font": "comanda laboratori Hoja1!N19",
                      "quote": "NÚM. D'EXPEDIENT | 4001612"}],
      "rule": "nom de carpeta = comanda N19 = annex DPSH = GTL (4 fonts)",
      "sources_checked": ["carpeta", "g3_06", "annex_11", "lab_07"],
      "note": null
    }
  },
  "tables": {
    "dpsh_tests":  {"estat_bloc": "segur", "rows": [
        {"punt": "P-1", "estat": "segur",
         "cota_inici":           {"estat": "segur", "value": "+199,50 msnm", "candidates": ["…"], "rule": "…"},
         "profunditat_assolida": {"estat": "segur", "value": "-1,35 m", "candidates": ["…"], "rule": "…"},
         "rebuig":               {"estat": "segur", "value": "Si", "candidates": ["…"], "rule": "…"},
         "nivell_freatic":       {"estat": "segur", "value": "No detectat", "matis": null, "candidates": ["…"], "rule": "…"}}]},
    "sondeig_tests": {"estat_bloc": "…", "rows": ["… cota (sistema de cotes!), profunditat, spt_ma {n_spt,n_tp,n_ma}, nivell_freatic"]},
    "spt_ma_tests":  {"estat_bloc": "…", "rows": ["… id, punt, fondaria, litologia (candidats), n30 {registre[4] segur, estat: candidats, candidates: [suma_centrals|N_del_tall|R]}"]},
    "soil_levels":   {"estat_bloc": "…", "rows": ["… nom, litologia_candidats[2-3 redaccions], de, a, mostra_del_nivell"]},
    "superficie_construida": {"estat": "…", "components": ["280", "86"], "total": "366", "etiqueta_font": "segons projecte", "candidates": ["…"]}
  },
  "sources_read": ["…"],
  "notes_estructurals": ["p.ex.: full de camp dins del PENETROS és d'un altre projecte"]
}
```

Regles del contracte (validades pel validador de la Fase 1):

1. `estat` ∈ {`segur`, `candidats`, `no_trobat`} — cap altre valor.
2. `segur` i `candidats` porten SEMPRE `candidates[]` no buit (≤ 3, ordenats) amb `value`+`font`+`quote` — fins i tot
   `segur` mostra d'on surt (Pas 5 del skill).
3. `candidats` → `value` = `candidates[0].value` (el que la UI pre-omple en ambre).
4. `no_trobat` → `value` = null i `sources_checked[]` no buit.
5. `n30` mai `estat: segur`; `litologia` de `soil_levels` mai `segur` (el validador ho REBUTJA — regla d'or codificada).
6. `nivell_freatic` porta `matis` ∈ {null, `humitat`, `aigua`} (Alcoletge: columna "Humitat (m)").
7. `spt_ma` emet comptes (`n_spt`,`n_tp`,`n_ma`), mai cadena formatada ("1/--"): el generador formata.
8. `superficie_construida` emet `components[]` + `total` + `etiqueta_font`: el generador tria la forma.

### 4.4 Per-document `{doc}.json`

El del Pas 4 del skill (sense canvis de fons), + 3 claus noves de la v1.0: `source_md5`, `skill_version`,
`schema_version`. Escriptura ATÒMICA (tmp + `os.replace`) perquè el watcher del wizard mai llegeixi JSON a mig escriure.
`g3_templates` escriu la seva sortida com un document més: `validation/lectura/_g3_templates.json` (mateix format de
senyals que ja emet, amb cel·la + cita) — la consolidació el tracta com una font d'autoritat A.

### 4.5 Reserva per a Tier B (Pendent A)

`tables` admet en el futur blocs `permeabilitat`, `sismica`, `geotecnica`, `sulfats_qualificacio` amb el MATEIX format
de fila 3-estats, generats per Python (`automation/tier_b_levels.py`) a partir de `soil_levels` + Nb — mai pel skill.
Cap camp d'aquests blocs podrà ser `segur` (candidats + override, per definició de Tier B). Res més a fer ara.

---

## 5. Mecànica de la crida headless

Patró de referència: `web/vision_fast.py:172-196` i `wizard_service.start_vision_cli` (NO s'editen; se'n copia el patró
al mòdul nou `automation/lectura/runner.py`).

```
claude -p "/g3dt-llegir-projecte {PROJECT_PATH} --only {DOC} --inventory {INV} --out {OUT}"
       --permission-mode bypassPermissions   < /dev/null  > {LOG} 2>&1
```

| Aspecte | Decisió | Motiu |
|---|---|---|
| `cwd` | **arrel del repo** (com `start_vision_cli`), NO `/tmp` | el skill és un project command (`.claude/commands/`): amb cwd=/tmp no es troba. Cost: carrega CLAUDE.md (~3k tokens) — acceptable |
| Binari | `G3DT_CLAUDE_PATH` (existent, defecte `claude`) | mateix mecanisme que la via CLI antiga |
| Timeout per document | `G3DT_LECTURA_TIMEOUT` = 240 s | un document, no un projecte; el global de 600 s era per la crida única |
| Timeout consolidació | `G3DT_LECTURA_CONSOLIDA_TIMEOUT` = 360 s | llegeix ~10-15 JSON petits + escriu 1 |
| Concurrència | `G3DT_LECTURA_CONCURRENCY` = 2 | l'ordinador de l'Eva no és un servidor; 2 solapa lectura visual amb I/O |
| Retry | 1 reintent si rc≠0 o JSON invàlid/absent; després `doc_failed` i es continua | un document no pot bloquejar el projecte |
| Èxit d'una crida | el fitxer `{doc}.json` existeix + parseja + `schema_version`+`source_md5` correctes | el rc de `claude -p` no és prou senyal |
| Windows | `subprocess` amb llista d'args (no shell string), `CREATE_NEW_PROCESS_GROUP`, kill amb `proc.kill()`; POSIX manté `start_new_session`+`killpg` | el codi actual és POSIX-only (`os.killpg`, `< /dev/null`) i a casa l'Eva és Python Windows natiu |
| Flag d'activació | **`G3DT_USE_LECTURA_HEADLESS`** (nou, defecte `false`) | independent de `G3DT_PROD_USE_CLAUDECODE_VISION` (semàntica vella de visió); prod actual no canvia de comportament |

---

## 6. Cache i re-execució

- Cache per document: `validation/lectura/{safe_name}.json` és vàlid si `source_md5` coincideix amb el fitxer actual
  **i** `skill_version` coincideix → la crida se salta (event `lectura_doc` amb `cached: true`).
- `_decisions.json` es regenera (crida `--consolida`) si qualsevol `{doc}.json` és més nou que ell, o si no existeix.
- Segona obertura d'un projecte sense canvis: 0 crides claude, tot de cache, < 10 s total.
- Eva afegeix/canvia UN document: 1 crida de lectura + 1 de consolidació.
- `?refresh=true` (paràmetre existent al wizard) → ignora cache de lectura (esborra `validation/lectura/` excepte
  `_telemetry.jsonl`).

---

## 7. Fallback i telemetria

**Cadena de fallback** (l'Eva mai es queda sense wizard):

1. `claude` no trobat / flag off → via B sencera tal com avui (`/api/prefills-stream` o fase de visió API dins del
   stream nou), event `lectura_fallback {reason}`.
2. Crida d'un document falla 2 cops → aquell document queda `no_trobat` amb nota "lectura fallida" a la consolidació;
   la resta continua.
3. Consolidació falla → el wizard fa servir `templates_fields` + auto_extract + un merge Python simple dels per-doc
   JSON vàlids (grau degradat, `estat` ambre per tot el que no sigui de g3_templates), event `consolidacio_fallback`.
4. Tot el temps 2 falla → el wizard té igualment els camps de g3_templates + via B (estat actual de prod, cap regressió).

**Telemetria** — `validation/lectura/_telemetry.jsonl`, una línia per crida:

```json
{"ts_start": "…", "ts_end": "…", "doc": "PENETROS.pdf", "mode": "only|consolida",
 "rc": 0, "timeout": false, "json_valid": true, "attempt": 1, "cached": false,
 "elapsed_s": 74.2, "log_path": "/tmp/…", "claude_version": "x.y.z"}
```

Agregat a la UI (event `lectura_fi`): n crides, n cache, n errors, temps total. Serveix per mesurar el cost/temps real
del primer open (avui és una ESTIMACIÓ: ~8-14 crides × 40-120 s amb concurrència 2 ≈ **5-12 min el primer cop, < 10 s
els següents** — xifra a verificar a la Fase 8, no prometre-la a ningú abans).

---

## 8. UI — 3 estats sobre la review.html existent (adaptar, no reescriure)

Es reutilitza la infraestructura existent: `source-badge` per camp (`review.html:1305-1380`), `alt-badge` "+N" +
popup `showAlternatives` (`review.html:5589-5605`). El canvi conceptual: el badge actual no té senyal de dubte; el nou
sí.

### 8.1 Badges per camp escalar

| Estat | Aspecte | Comportament del camp |
|---|---|---|
| `segur` | badge blau «lectura» | pre-omplert amb `value`; clic al badge → popup amb la font + cita (transparència, no dubte) |
| `candidats` | badge AMBRE «N candidats» | pre-omplert amb candidat 1; clic → popup de selecció; triar → el camp passa a font `user` (badge verd existent) |
| `no_trobat` | badge gris «no trobat» | camp buit; clic → popup amb `sources_checked` + proposta d'acció ("Afegeix el pressupost a la carpeta / omple'l a mà") |

El popup és una extensió de `showAlternatives`: per candidat, fila amb **valor** (clicable → escriu al camp),
**font** (document + posició) i **cita** en cursiva; peu amb la `rule` del skill. Els camps SENSE entrada al
`_decisions.json` conserven els badges actuals (auto/user/defecte) — les dues capes conviuen.

### 8.2 Taules (pestanyes existents, no pestanya nova)

- **Pestanya DPSH** (existent): s'hi afegeix la graella `dpsh_tests` — una fila per punt amb cel·les
  cota inici / profunditat / rebuig / N.F., cada cel·la amb el seu mini-badge d'estat i popup. El matís
  `humitat|aigua` del N.F. es mostra com a etiqueta al costat del valor.
- **Pestanya Sondeig** (existent): `sondeig_tests` (amb la cota segons el SISTEMA de cotes — l'ERR de Castellar) +
  `soil_levels`: per nivell, dropdown de litologia amb les 2-3 redaccions candidates + opció text lliure; `de`/`a`
  editables amb badge.
- **SPT/MA**: dins Sondeig — per assaig: id, punt, fondària, litologia (candidats), i **n30 = registre (segur, només
  lectura: "24/34/28/30") + chips de candidats de la suma** («62 (trams centrals)» | «58 (tall)» | «R»). MAI
  pre-seleccionat un valor únic com a definitiu: chip ambre fins que l'Eva en cliqui un. És la materialització de la
  pregunta oberta del criteri N30.
- **superficie_construida**: al camp existent `superficie_construida_m2`, popup que ofereix `components` ("280+86") i
  `total` ("366") com a candidats separats + `etiqueta_font`.

### 8.3 Mapping `_decisions.json` → camps del wizard

| decisions (v1) | id del wizard | nota |
|---|---|---|
| client_name | `client_name` | |
| street_address | `street_address` | |
| municipality | `site_municipality` | |
| architect_name / architect_company | `architect_name` / `architect_company` | regla persona/despatx del skill |
| building_type | `building_type` | |
| num_floors | `num_floors` | |
| superficie_parcela | `superficie_parcela_m2` | etiqueta_font → text de la fila de l'informe |
| superficie_construida | `superficie_construida_m2` | components+total al popup |
| cota_referencia | `cota_referencia` | |
| num_soil_levels | `num_soil_levels` | |
| utm_x / utm_y | `utm_x` / `utm_y` | |
| field_date, expedient, num_dpsh_tests, referencia_catastral, lab_*, cte_* | ids a confirmar durant la Fase 6 (grep dels ids reals) | cap camp nou inventat: si el wizard no té el camp, el valor viatja igualment a `user_data` per al generador |
| tables.* | pestanyes DPSH/Sondeig (§8.2) | |

**Precedència del merge final:** `user_data` (Eva mana sempre) > lectura `segur` > lectura candidat-1 (marcat ambre) >
via B/auto_extract > defecte. Font nova als badges: `lectura` i `lectura_candidats`.

---

## 9. Pla de construcció per fases

**Estratègia de models:** les fases de codi (1-7) estan especificades per ser implementades amb **Sonnet 5** (fitxers
exactes, contractes tancats, fixtures reals, criteris d'acceptació mecànics). Les DUES peces amb judici es reserven a
la sessió principal: la **Fase 0 (skill v1.0)** — toca l'actiu validat per la lectura d'or — i la **Fase 8 (E2E +
veredicte)**. Regla de treball per a cada fase: tests primer amb fixtures, cap crida API als tests (mock claude), commit
per fase.

### Fase 0 — Skill v1.0 (sessió principal, NO Sonnet)
- Afegir `--inventory FILE` (context creuat en mode `--only`), `--consolida` (llegeix `validation/lectura/*.json` +
  `_inventory.json` + `_g3_templates.json`, aplica Pas 5, escriu `_decisions.json` schema v1), dialecte normalitzat
  (`estat`/`font`, claus planes §4.2), escriptura atòmica, capçalera `source_md5`+`skill_version`+`schema_version`.
- Header: v0.9 → v1.0 + línia de changelog.
- **Acceptació:** re-run manual del mode `--consolida` sobre els per-doc JSON d'or de Bell-lloc → `_decisions.json`
  equivalent al d'or (mateixos estats per camp; adapter de dialecte per comparar).

### Fase 1 — Contracte + validador (Sonnet 5)
- **Nou:** `automation/lectura/__init__.py` (buit), `automation/lectura/contract.py`: dataclasses + `validate_decisions(dict) -> list[str]`
  (les 8 regles del §4.3, incloent el rebuig de n30/litologia `segur`), `adapt_legacy(dict) -> dict` (dialecte
  `status`/`source` i niuats `lab`/`cte` → v1).
- **Tests:** `tests/test_lectura_contract.py` amb fixtures reals: `docs/golden-read/4001612 BELL-LLOC/_decisions.json`
  (via adapter) i `docs/golden-read-taules/4001612 BELL-LLOC/_tables_decisions.json`; casos negatius sintètics (n30
  segur → error; candidats sense candidates → error).
- **Acceptació:** fixtures d'or adaptats validen net; suite verda.

### Fase 2 — Inventari + enrutament (Sonnet 5)
- **Nou:** `automation/lectura/inventory.py`: `build_inventory(project_path) -> dict` segons §3 (md5, route, priority,
  duplicats per md5; EXCLUDE de `g3_templates.py` com a referència de patrons). Escriu `_inventory.json` atòmic.
- **Tests:** sobre 2-3 projectes de `reference-material/` (excepció pactada per a tests): Bell-lloc ha de donar ~9-13
  `route: claude`, plantilles G3 `route: python`, fotos `route: skip`, duplicats detectats.
- **Acceptació:** cap fitxer del projecte sense route; determinista (2 runs = mateix JSON llevat de timestamps).

### Fase 3 — Runner subprocess (Sonnet 5)
- **Nou:** `automation/lectura/runner.py`: `run_lectura(project_path, on_event, mode) -> LecturaResult`. Cua per
  prioritat, concurrència N, timeout, retry, kill en cancel·lació, cache per md5 (§6), telemetria JSONL (§7),
  branques POSIX/Windows (§5). Mode `projecte` (crida única) inclòs.
- **Tests:** `tests/test_lectura_runner.py` amb un **mock `claude`** (script al scratchpad de test que copia el fixture
  JSON d'or corresponent al `--only` demanat, amb retards configurables): happy path, timeout (mock que dorm), rc≠0 +
  retry, JSON invàlid, cache hit, cancel·lació. CAP crida real.
- **Acceptació:** telemetria completa a cada escenari; cap procés zombi (comprovar als tests).

### Fase 4 — Consolidació + fallback degradat (Sonnet 5)
- A `runner.py`: pas `--consolida` + validació amb `contract.validate_decisions`; si falla → `merge_degradat()` Python
  (per-doc JSONs + g3_templates, tot `candidats` excepte g3_templates que manté el seu estat).
- **Normalització suau abans de declarar invàlid** (lliçó del creuament Fase 0: el productor cec desvia en forma, no en
  fons): arreglades deterministament i re-validat — (a) `estat: candidats` amb `value != candidates[0].value` →
  `value := candidates[0].value`; (b) cel·la amb `font`/`quote` al nivell superior i sense `candidates` → embolcallar
  com a `candidates[0]`. Cap altra reparació: si després d'això encara falla, degradat.
- **Tests:** mock consolidació OK / mock que escriu JSON invàlid → degradat; validador rebutja n30 segur injectat.

### Fase 5 — Servei + endpoint SSE (Sonnet 5)
- **Nou:** `web/lectura_service.py`: `get_lectura_streaming(project_name)` — orquestra §2 (g3_templates + auto_extract
  en paral·lel, runner, consolidació, merge). Reutilitza `queue.Queue` + generator com `get_prefills_streaming`
  (mateix patró; NO es toca la funció vella). Merge final amb la precedència del §8.3.
- **Edita:** `web/api.py` — `GET /api/lectura-stream/{p}` (gated per `G3DT_USE_LECTURA_HEADLESS`, 404 si off, com
  `_require_ai_pipeline_enabled`), `automation/config.py` — les 4 variables noves del §5.
- **Tests:** endpoint amb mock runner: seqüència d'events correcta; flag off → 404; cancel·lació a mig stream.

### Fase 6 — Merge → camps wizard (Sonnet 5)
- A `lectura_service.py`: taula de mapping §8.3 (completar els "ids a confirmar" amb grep de `review.html` — cap camp
  nou a la UI sense confirmar que existeix); fonts `lectura`/`lectura_candidats`; `_decisions` sencer adjuntat a
  l'event `prefills` sota la clau `_lectura` (la UI en necessita candidates/quotes/tables).
- **Tests:** merge amb user_data existent (Eva mana), amb via B solapada (lectura segur mana), amb no_trobat (cau a via B).

### Fase 7 — UI (Sonnet 5)
- **Edita:** `templates/validation/review.html` — CSS `.estat-badge` (3 variants), extensió del popup
  `showAlternatives` (valor + font + cita + rule, selecció → user), graelles de taules a les pestanyes DPSH/Sondeig
  (§8.2), chips n30, panell no_trobat. Consumeix `_lectura` de l'event `prefills` + events SSE incrementals
  (`templates_fields`, `lectura_doc`, `decisions`).
- **Acceptació manual (checklist):** amb el server en dev i Bell-lloc de fixture: camps segurs blaus amb popup; camp
  candidats ambre pre-omplert amb candidat 1; seleccionar un candidat → verd user; no_trobat buit amb proposta; n30 mai
  amb valor únic pre-tancat; taules DPSH/Sondeig poblades amb badges per cel·la.

### Fase 8 — E2E real + veredicte (sessió principal)
- 2 projectes (`Bell-lloc`, `Castellar`) end-to-end amb `claude -p` real des del wizard local.
- Comparar: escalars vs `_decisions.json` d'or (mateixos estats), taules del docx generat vs
  `docs/golden-read-taules/_eva_truth/` amb `scripts/compare_tables_vs_eva.py`.
- Mesurar telemetria real (crides, minuts, cache) i substituir l'estimació del §7.
- **GO/NO-GO:** erroni-amb-confiança = 0; cap regressió del flux via B amb flag off; latència primer open publicada
  amb xifres reals. → entrada al DECISION-LOG + STATUS.

---

## 10. Decisions obertes per al Josep

| # | Decisió | Recomanació |
|---|---|---|
| D1 | Forma de la crida: per-document + consolidació (incremental, no validada) vs crida única per projecte (validada per la lectura d'or, sense incrementalitat) | per-document, amb mode `projecte` de reserva implementat (§2) |
| D2 | Latència primer open estimada 5-12 min (cache: segünts opens < 10 s). Acceptable per a l'Eva? | sí amb SSE incremental (els camps van apareixent); mesurar a Fase 8 abans de cap promesa |
| D3 | Camp `candidats`: pre-omplir amb candidat 1 (ambre) vs deixar buit fins que l'Eva triï | pre-omplir ambre — mai en blanc, mai fals-segur; EXCEPCIÓ: n30 sense pre-tancar (chips) |
| D4 | Sonnet 5 per a les fases 1-7 | sí — el pla està escrit per a això; Fases 0 i 8 les faig jo (skill + veredicte) |
| D5 | `cwd` de la crida = arrel del repo (carrega CLAUDE.md, ~3k tokens/crida) vs instal·lar el skill com a user-command | arrel del repo (simplicitat; el skill viu al repo i es versiona amb ell) |

## 11. Riscos coneguts

- **Consolidació per crida separada no validada** — mitigada per l'acceptació de la Fase 0 (equivalència amb l'or de
  Bell-lloc) i la Fase 8; si decep, mode `projecte` (crida única validada).
- **Windows**: el patró subprocess actual és POSIX; el runner el reescriu amb branques. No es podrà validar del tot
  fins a tenir un Windows amb Claude Code CLI (pre-desplegament, decisió Josep).
- **Leakage**: tot el que validem amb els 8 projectes valida re-execució, no generalització. El primer projecte NOU de
  l'Eva és el test real (tasca oberta #4 del handoff).
- **Deriva de versions del CLI `claude`** a casa l'Eva — la telemetria registra `claude --version` per diagnosticar.

---

*Fi del disseny. Pendent B: contracte v1 + runner headless + UI 3 estats, construïble per fases amb Sonnet 5.*
