# PLA DE LLANÇAMENT 2026-09 — portar `experiment/nivell-a-2026-08` a l'ordinador de l'Eva amb Claude Code

**Escrit:** 2026-09-10 (vespre), sessió dedicada de preparació. **Manen:** `docs/_FOR-NEW-YOU-PREPARACIO-RELEASE-20260910-2000.md`
(§10 sobre §2-§4) i les decisions del Josep que hi consten. **Abast:** els tres passos (branca de release + prova en perfil net +
instal·lació presencial). Aquest document és el full de ruta viu; l'evidència és als commits de `release/2026-09` i als runs de
`docs/wizard-headless/mesures/runs/`.

## 0. On som (2026-09-10, 21:30)

| pas | estat | evidència |
|---|---|---|
| 1. Branca `release/2026-09` (worktree `clients/g3dt-release/`) | **FET** | merge `590ab0f` (2 conflictes, resolts amb experiment; índex = experiment + `tests/test_image_cache_name.py`), `pillow` declarat `ad18837`, CLAUDE.md `a1bf349`, `.gitignore` egg-info `50129fa`, M341 `fd118ac`, segon merge `d042362` (codi del §10) |
| 1b. M341 des del worktree release, venv net, cau pròpia | **IDÈNTIC** a `2026-09-09-m341-nit` | `runs/2026-09-10-m341-release/_AGREGAT-341.md` (escalars 315·44·120·31 → 75 %, taules 82 %, imatges 31·3·15·7 → 69 %, fix 81 M · 21 X) |
| 1c. Suite a release (venv del lock) | **11 vermells / 2579 verds / 4 omesos (209 s)** — exactament els 11 esperats-amb-dades, cap de nou | DECISION-LOG 2026-09-10 (3) |
| 1d. Codi que el §10 demanava | **FET** (experiment `caf2b1e`, `f985936`, `6fbdc85`; fusionat a release `d042362`) | lectors d'imatges dins el job; aturada per límit d'ús; pins `pymupdf`; `requirements-lock.txt` |
| 2. Prova en perfil net | **en curs** sobre Castellar (HOME nou amb només `.credentials.json`, sonnet@xhigh, 2 en paral·lel, lectors @medium) | `scratchpad/clean-run/run.log`; resultat al DECISION-LOG quan acabi |
| 2b. Prova a WSL al PC del Josep amb els flags de l'Eva | pendent de la decisió §3.1 | — |
| 3. Presencial | pendent de data | §6 |
| push `release/2026-09` a origin | després de la suite (§2.4) | `git push -u origin release/2026-09` |

`production/g3dt-eva-v1` **no s'ha tocat** (`123b4f2`, el que té l'Eva és `1f1d7fd` + potser cap dels 2). S'avança només el dia de
la visita: `git merge --ff-only release/2026-09` + push, just abans del pull presencial.

## 1. Fets verificats aquesta sessió (correccions al handoff §10)

1. **El runner JA fixa el model i l'esforç.** `automation/lectura/runner.py` passa `--model` (`G3DT_LECTURA_MODEL`, defecte
   `sonnet`) i `--effort` (`G3DT_LECTURA_EFFORT`, defecte `xhigh`) a cada `claude -p`, treu `CLAUDE_EFFORT` de l'entorn del fill
   i, amb `G3DT_LECTURA_AUTH=login` (defecte), també `ANTHROPIC_API_KEY`/`AUTH_TOKEN` perquè el fill faci servir la sessió de
   claude.ai. Els dos lectors d'imatges llegeixen el mateix `G3DT_LECTURA_MODEL` i van sempre a `medium` (com es van mesurar:
   runs `2026-09-09-lector-*`, 37-80 s per crida). El §10.2 («el model NO es fixa») era fals.
2. **El runner JA té branca Windows** (`proc.kill()` + `CREATE_NEW_PROCESS_GROUP`, resolució de `claude.cmd` amb
   `shutil.which`). El que NO és Windows-capable és `wizard_service.start_vision_cli` (només amb
   `G3DT_PROD_USE_CLAUDECODE_VISION=true`, que no cal) i, sobretot, **els skills**: `g3dt-llegir-projecte` fa córrer
   `python3 docs/wizard-headless/...` i ordres de shell POSIX des de dins de Claude Code; a Windows natiu Claude Code les
   executaria en PowerShell. Tot s'ha mesurat en Linux. → §3.1.
3. **Un venv nou NO reprodueix l'entorn mesurat.** `pip install -e .` en un venv net (2026-09-10) porta `pymupdf` 1.28.2,
   `pillow` 12.3, `numpy` 2.5.3, `anthropic` 1.5, `fastapi` 0.141; el venv mesurat (`g3dt-prod/.venv`) té 1.27.1, 12.2, 2.4.3,
   0.84, 0.133. Efecte comprovat: `pymupdf` 1.28 escriu «warning: The `fitz` API is deprecated…» a **stdout** i trenca el
   contracte `OK PNG …` de `render_clip.py` (el skill el llegeix), i `pymupdf4llm` 1.28 retorna text buit; 3 tests vermells
   nous que passen amb 1.27.1 sobre el mateix codi. Resolt amb `pymupdf>=1.27.1,<1.28`, `pymupdf4llm<1.0` al `pyproject` i
   **`requirements-lock.txt`** (versions exactes del venv mesurat): la instal·lació és `pip install -e . -c requirements-lock.txt`.
   Migrar `import fitz` → `import pymupdf` és feina futura, no del llançament.
4. **Els 17 vermells de `test_smartscan` (i 3 de `test_fileminer` Anciles) són fixtures absents, no defectes:** amb els fitxers
   crus dels 7 projectes a `reference-material/` (ignorats per git; copiats del worktree dev) els 20 passen. Queden 11 vermells
   esperats amb dades (7 `ranking_api`, 2 `ai_pipeline_trace`, 1 `bearing_stratum` drift, 1 `groq_miner` cache), tots de
   pipeline IA / fixtures, cap del camí de l'Eva. `suite-vermells-esperats.txt` ho diu a la capçalera.
5. **M341 mesura una BARREJA de carpetes** (`_project_path` de `mesura_341.py`): Castellar, Rubí, Bell-lloc i Linyola des de
   `reference-material/<P>` si hi ha `file_mapping.json` (Fase 0 feta; al worktree `g3dt-prod` hi és, ignorat per git), la
   resta des de `~/g3dt-e2e/projectes`. Reproduir la referència des d'un altre worktree vol la mateixa barreja (còpia de les 4
   carpetes de `g3dt-prod`). Amb els 7 des de `g3dt-e2e` o els 7 des de la còpia del dev, mouen 1 cel·la de narrativa i unes
   quantes d'imatges — per l'estat de `validation/` de cada còpia, no pel codi (comprovat 4 vegades, dues amb el venv de prod).
6. **L'Eva té tres claus** (logs maig-juliol): Anthropic, Groq i OpenAI (`run default: openai` a la visió; 88 crides OpenAI
   200). El `env.txt` de `/mnt/c/claude/g3dt/` NO és el seu `.env` (només Google Maps + Anthropic, mostra antiga).
7. **`claude -p` funciona amb un HOME net que només té `.claude/.credentials.json`** (sessió OK, `is_error false`, models
   sonnet-5 + haiku): és la manera de provar «sense memòria ni configuració del Josep» (§10.4) sense un compte nou.

## 2. Pas 1 — què hi ha a `release/2026-09` que no hi havia a experiment el matí

### 2.1 Lectors d'imatges dins el job (`caf2b1e`)
`web/lectura_service._run_image_lectors`: després de la consolidació i abans del merge, `lector_fotos.run` i `lector_figures.run`,
una crida cadascun, sonnet@medium, topalls 420/600 s, `should_cancel` del job. **Eva mana** (`source: user` → salta). **Empremta**
del projecte (camí + mida, sense `validation/`) a `_lector.fingerprint`: mateix contingut → salta (Preparar avui, Enllestir demà
= una sola passada; un fitxer nou de l'Eva → torna). Un lector que falla és `status: error` i el generador cau a la tria
determinista. Estat nou del job **`imatges`** (pas 4 de 5, «Triant les imatges de l'informe», ~90 s per lector a l'estimació),
`merge_inici` passa a `merging` (5). Flag `G3DT_LECTURA_IMATGES` (defecte true). 6 tests nous.

### 2.2 Aturada per límit d'ús (`f985936`)
`runner.systemic_reason`: amb rc ≠ 0 o `is_error`, si el text final del CLI o l'stderr diu «usage limit / hit your limit / resets
at / credit balance / not logged in / invalid api key…» → cap reintent, senyal compartit, els documents pendents surten
`skipped_systemic` sense spawn, cap consolidació, `LecturaResult.systemic`. El servei NO cau a via B: `error_event {code:
usage_limit, reason, message}`; la taula diu «Aturat: el compte de Claude ha arribat al límit d'ús — els documents ja llegits es
conserven, prem Preparar quan el pla torni a estar disponible» (cau per md5). 5 tests.

### 2.3 Dependències (`ad18837`, `6fbdc85`)
`pillow>=10.0` a `dependencies`; `pymupdf<1.28`, `pymupdf4llm<1.0`; `requirements-lock.txt` (73 paquets, versions exactes del
venv mesurat). `.env.example` documenta per primer cop el bloc de la lectura headless (`G3DT_USE_LECTURA_HEADLESS`, `MODEL`,
`EFFORT`, `AUTH`, `CLAUDE_PATH`, `CONCURRENCY`, `IMATGES`).

### 2.4 Suite i mesura
- Suite a release, venv net sense lock: 14 vermells / 2564 verds = 11 esperats-amb-dades + 3 de `pymupdf` 1.28.
- Suite a release, venv del lock (recreat de zero amb `-c requirements-lock.txt`): **11 vermells / 2579 verds / 4 omesos (209 s)**, els 11 esperats-amb-dades i cap més: el lock reprodueix l'entorn mesurat.
- M341 des de release: idèntic a la referència (§0).

## 3. Decisions que són del Josep (no s'ha assumit res)

### 3.1 Entorn a l'ordinador de l'Eva: WSL2 + Ubuntu (recomanat) o Windows natiu
**Recomanació: WSL2 + Ubuntu**, tot dins WSL (wizard, Python, `claude`, `soffice`), navegador de Windows a `localhost:8765`.
Per què: és exactament l'entorn mesurat (M341, ledger, suite); els skills executen ordres POSIX des de Claude Code; `soffice`
d'`apt` és el que converteix FH11/`.doc`; els `scripts/*.bat` (WSL) ja existeixen (`G3DT-Wizard.bat`, `G3DT-config.bat`).
Cost: `wsl --install` (admin + reinici), Ubuntu, `apt install python3-venv libreoffice-core`, Node + `npm i -g
@anthropic-ai/claude-code`, muntar la unitat de xarxa (`/mnt/<lletra>` si és una unitat mapada; si no, `sudo mount -t drvfs
'\\192.168.1.x\geologia' /mnt/geologia` i entrada a `/etc/fstab`), `G3DT_NETWORK_PROJECTS=/mnt/geologia/...`,
`G3DT_LOCAL_WORKSPACE=/home/eva/g3dt/workspace`, etc. La instal·lació nativa de maig (`C:\g3dt-ia\app`) queda com a punt de
retorn (§7) sense tocar-la.
Windows natiu voldria: provar els skills sota PowerShell, `claude.cmd`, `render_clip.py`/`write_doc_json.py` amb camins Windows,
LibreOffice per a Windows — una remesura sencera. No és impossible; és una altra feina.

### 3.2 Pla d'Anthropic per a l'Eva (dades del ledger, Castellar 13 documents, `docs/wizard-headless/mesures/LEDGER.md`)

| model @ esforç | tokens de sortida (docs) | turns/doc | paret | cost equivalent |
|---|--:|--:|--:|--:|
| sonnet @ xhigh (defecte del codi) | 212-306 k | 15-21 | 26-33 min | 13-17 $ |
| fable @ xhigh | 164 k | 10 | 20 min | 48 $ |
| opus 4.8 @ high (pla econòmic) | 186 k | 11 | 24 min | 26 $ |

Més els dos lectors (@medium, ~1-2 min, pocs tokens) i la consolidació Python (0). Un projecte són **13-15 crides `claude -p`
d'una quinzena de turns** i 200-300 k tokens de sortida. **No sé les quotes exactes de cada pla** (canvien); el que se sap:
Pro té finestres de 5 h que un projecte sencer pot exhaurir (per això el §2.2 existeix); Max 5x/20x hi caben. Amb ≤ 1 projecte al
dia (disseny §0), la hipòtesi de treball és **Max 5x**, i la prova real és el primer projecte de l'Eva al seu compte el dia de la
visita, cronometrat i amb el ledger. Decisió del Josep (memòria `project_eva_subscription_model_tier`: Fable si el pla ho permet,
si no Opus 4.8; Sonnet és el defecte codificat).

### 3.3 Claus API a les fases clàssiques (§10.3d)
Amb la lectura activa i decisions vàlides, `_merge_prefills(skip_vision=True)` **no crida la visió per API**. Encara criden API:
FileMiner Groq (`G3DT_USE_GROQ=1` + `GROQ_API_KEY`), sonda visual de ConceptScout (si `ANTHROPIC_API_KEY`),
`deep_folder_classify` (si `OPENAI_API_KEY`), SmartScan nivell 3 (Groq → Claude), ortofoto (`G3DT_ORTHO_ENRICHMENT=1`) i
`_synthesize_with_llm` (Anthropic). El corpus mesurat (`~/g3dt-e2e`, «Fase 0 feta amb els JSON de visió de producció») les
inclou. **Recomanació: mantenir les tres claus que ja té** (cost petit per projecte) per no canviar el procés mesurat; passar les
sondes a Claude Code és feina d'una altra sessió. Risc conegut: Groq 503 «over capacity» (diagnòstic 23-08).

### 3.4 Data de la visita i punt de retorn — §6 i §7.

## 4. Pas 2 — prova en perfil net (§10.4)

### 4.1 En curs ara (WSL del Josep, sense la seva memòria ni configuració)
`HOME=<net>` amb només `.claude/.credentials.json`; còpia de Castellar sense `validation/`; `G3DT_LECTURA_MODEL=sonnet`,
`EFFORT=xhigh`, `CONCURRENCY=2`, `AUTH=login`, `G3DT_CACHE_DIR` propi; `run_lectura` + `lector_fotos.run` + `lector_figures.run`
(driver al scratchpad, `clean-run/driver.py`). Comparació en acabar: `compare_consolida.py escalars|taules` contra l'or, i
`_decisions.json` contra `~/g3dt-e2e/projectes/…/validation/lectura/_reconsolida-2026-09-06-pend/_decisions.json`; les tries
dels lectors contra `photo_selection.json`/`figure_selection.json` del corpus. Criteri: 0 erroni-amb-confiança i mateixes
cel·les segures que la referència → el resultat és del sistema, no de l'entorn.

### 4.2 A WSL, com ho tindrà l'Eva (pendent §3.1)
Clon net de `release/2026-09` a una ruta Linux nova (no un worktree); `python3 -m venv .venv && pip install -e . -c
requirements-lock.txt`; `.env` **calcat al de l'Eva** (tres claus, `G3DT_*` de producció a `false`) **+** el bloc de lectura
(`G3DT_USE_LECTURA_HEADLESS=true`, `MODEL`, `EFFORT`, `AUTH=login`, `IMATGES=true`), `G3DT_NETWORK_PROJECTS` a
`/mnt/c/claude/g3dt/xarxa-simulada`; `claude` amb un HOME net; `python -m web` → navegador de Windows → Bell-lloc →
«Preparar» (cronometrar) → pestanya Imatges (alternatives del lector, pujada, peu, «Tornar a l'automàtic») → «Generar informe»
→ Word: imatges, numeració, cap resta de Jinja. Un segon projecte (Alcoletge) i un de `dades-eva/` si n'hi ha. Logs: cap
`Traceback`; avisos de `soffice` absent només si no és instal·lat.

## 5. Pas 3 — full de ruta presencial (una pàgina)

1. **Abans de sortir:** `git merge --ff-only release/2026-09` a `production/g3dt-eva-v1` + push; `git bundle` al pendrive;
   `requirements-lock.txt` inclòs; les claus del Josep en paper (pla B).
2. **Punt de retorn (5 min):** `git -C C:\g3dt-ia\app log -1` (anotar el SHA), còpia de `C:\g3dt-ia\` sencera (app + .env + cache)
   a `C:\g3dt-ia.backup-<data>\`. Res de la instal·lació de maig es toca: WSL és una instal·lació NOVA al costat.
3. **WSL:** `wsl --install` (admin, reinici), Ubuntu, usuari `eva`; `apt install python3.12-venv libreoffice-core git`; Node
   LTS + `npm i -g @anthropic-ai/claude-code`; `claude` → login amb el compte de l'Eva (pla contractat abans, §3.2).
4. **Unitat de xarxa dins WSL** (drvfs + fstab) i comprovar `ls` de la carpeta de projectes.
5. **App:** `git clone --branch production/g3dt-eva-v1 …` a `/home/eva/g3dt/app`; venv + `pip install -e . -c
   requirements-lock.txt`; `.env` (copiar el seu, camins Linux, bloc de lectura); carpetes workspace/reports/cache/logs.
6. **Icona:** `scripts/G3DT-Wizard.bat` + `G3DT-config.bat` (`G3DT_PATH=/home/eva/g3dt/app`) a l'escriptori; la de maig es
   reanomena «(antic)».
7. **Un projecte seu de cap a cap amb ella al costat:** «Preparar» (cronometrar; dir-li el temps per endavant), Imatges,
   Generar, Word. Si el compte diu prou: la taula ho dirà (§2.2); anotar l'hora.
8. **Tornar enrere si cal:** la icona antiga segueix funcionant (Windows natiu, `1f1d7fd`); res no s'ha esborrat.

## 6. Preguntes obertes (per al Josep)

- §3.1 WSL o natiu (recomanat WSL). · §3.2 pla (hipòtesi Max 5x; model Fable/Opus 4.8/Sonnet). · §3.3 claus (recomanat mantenir).
- Data de la visita. · Qui contracta el pla (G3 amb targeta pròpia, com les claus del maig).
- `schemas/formats/learned/` de l'ordinador de l'Eva si divergeix del repo (el format learner hi escriu): la instal·lació WSL és
  nova, així que no hi ha conflicte; els seus formats apresos de maig es poden copiar a mà si en té.

## 7. Punt de retorn (resum)
La instal·lació de maig (`C:\g3dt-ia\app`, Windows natiu, `production/g3dt-eva-v1` @ `1f1d7fd`) no es modifica ni s'esborra:
WSL s'instal·la al costat. Si el dia de la visita res no va, l'Eva obre la icona de sempre i té el que tenia.
