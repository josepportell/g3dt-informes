# FOR NEW YOU — PREPARACIÓ DEL LLANÇAMENT (release) — decidit el 2026-09-10 a les 20:00: portar la branca experimental a l'ordinador de l'Eva en tres passos (branca `release/…` + merge, prova en Windows natiu al PC del Josep, instal·lació presencial)

**Escrit:** 2026-09-10 (vespre). **Per a:** la sessió que prepari el llançament (sessió nova, dedicada).
**Recap d'una frase:** tot el que s'ha construït des de l'agost (nivell A, criteris de càlcul, narrativa, taules, numeració,
imatges, finestreta d'alternatives, pujada d'imatges) viu a `experiment/nivell-a-2026-08`, **253 commits** per davant de
`production/g3dt-eva-v1`, que és el que l'Eva té a `C:\g3dt-ia\app`; un `git pull` allà només li portaria 2 commits.
El Josep ha decidit fer-ne un **llançament** en tres passos, i aquesta sessió el prepara (passos 1 i 2); el pas 3 és presencial.

Aquest doc és el de la **tasca**; l'estat de la línia de treball (invariants de la pujada, mesures) és a
`_FOR-NEW-YOU-20260911.md`. Tots dos són vigents.

## 1. Ordre de lectura

1. Aquest document.
2. `docs/INSTALL-EVA-v1.md` — l'entorn REAL de l'Eva (Python 3.12 natiu, `C:\g3dt-ia\app`, venv, `pip install -e .`, `.env`
   amb tots els flags `G3DT_*` a `false`, `G3DT-Wizard.bat` Windows natiu que només fa `python -m web`). És la referència
   del que ha de continuar funcionant.
3. `docs/PLA-DEPLOYMENT-EVA-2026-05-04.md` — com es va fer l'última instal·lació (llista de comprovació reutilitzable).
4. `STATUS.md` (primers paràgrafs) i `_FOR-NEW-YOU-20260911.md` §2-§4 (mesures de referència, invariants que el merge no pot trencar).
5. Memòries: `project_g3dt_deployed_2026-05-04` (dos worktrees, pipeline IA NO a prod), `eva_prod_logs_scoreboard_2026-08`
   (ús real maig-juliol: 19 projectes, 14 OK, 6-10 min de prefills, crash Unicode arreglat a la branca de revisió),
   `project_prod_audit_fixes_2026_08` (F1-F4e), `feedback_no_pull_eva_success_criterion` (el llistó del Josep: no
   millores incrementals, un sistema que li faci la feina), `project_eva_subscription_model_tier`.
6. `docs/wizard-headless/mesures/suite-vermells-esperats.txt` (els 31 vermells de la suite: capçalera amb el perquè).

## 2. Fets verificats avui (no cal tornar-los a derivar)

**Branques i remot** (`origin` = `https://github.com/josepportell/g3dt-informes.git`; tots els worktrees comparteixen el `.git`):

| branca | local | remot | notes |
|---|---|---|---|
| `production/g3dt-eva-v1` | `123b4f2` | `123b4f2` (pujat avui) | el que té l'Eva és `1f1d7fd` (24-07) + potser cap dels 2 commits nous |
| `experiment/nivell-a-2026-08` | `bf007ee` | `bf007ee` (pujat avui) | in-place al worktree `g3dt-prod/` (nom enganyós) |
| base comuna | `1f1d7fd` (2026-07-24) | | |

- Experiment té **253 commits** que producció no té; producció en té **2** que experiment no té:
  `c46bc69` (plantilla, bloc 2.1.1: canvi d'1 byte al `.docx`) i `123b4f2` (`_cache_name` per md5 + `tests/test_image_cache_name.py`).
- **Conflictes del merge (assaig en sec amb `git merge-tree`): exactament dos fitxers.**
  - `templates/g3dt-jinja-template.docx` (binari): experiment l'ha tocat en 8 commits (peça 1, bloc 2, peça 7a…) i ja
    porta l'arranjament del 2.1.1 (fet a les dues branques el 06-09). **Resolució: la d'experiment** (`--theirs` si el
    merge es fa des de la branca de producció).
  - `automation/image_manager.py`: `_cache_name` és **IDÈNTIC** a les dues branques (era un cherry-pick). El resultat
    del merge ha de ser igual al fitxer d'experiment; comprovar-ho amb `git diff experiment/nivell-a-2026-08 -- automation/image_manager.py` = buit.
  - `tests/test_image_cache_name.py` només és a producció: **es queda** (ha de passar contra el codi d'experiment).
- `review/prod-audit-2026-08` (F1-F4e, crash Unicode inclòs) **és avantpassat d'experiment**: el merge ho porta tot.
- 66 fitxers de codi canviats respecte producció (`automation`, `web`, `templates`, `schemas`): +30.068 / −1.232 línies.

**Dependències** (verificat contra `pyproject.toml`, idèntic a les dues branques):
- Imports de tercers nous respecte producció: només **`PIL`** (Pillow). `imagehash>=4.3` és a `dependencies` des del
  **2026-04-24**, abans de la instal·lació del 05-04: el venv de l'Eva el té i, amb ell, Pillow com a dependència
  transitiva. Tot i així, **afegir `pillow>=10.0` a `dependencies`** (avui només és a `[tool.uv] dev-dependencies`):
  el codi l'importa directament (`web/api.py`, `image_manager`, `imatges/*`).
- `[tool.setuptools.packages.find] include = ["automation*", "web*"]`: els subpaquets nous (`automation.imatges`,
  `automation.lectura`, `automation.concept_scout`…) entren sols. Cal igualment **`pip install -e .`** de nou a l'ordinador
  de l'Eva (per si de cas i per Pillow explícit).
- `pypandoc` i `soffice`: només al pipeline IA (`G3DT_ENABLE_AI_PIPELINE=false`), a la conversió `.doc → .docx` de
  `wizard_service` (avisa i segueix si falta) i als lectors de fotos/figures (passades manuals). **No calen** amb els flags de l'Eva.
- `claude` (CLI): `vision_fast` darrere `G3DT_PROD_USE_CLAUDECODE_VISION=false`; el panell de jobs de lectura
  (`#jobsPanel`, botons «Preparar / Enllestir / Des de zero») darrere `G3DT_USE_LECTURA_HEADLESS=false` (404 → ocult).
  **Amb els flags de l'Eva, res no crida `claude`.**
- `python-multipart` ja hi era (l'evidència HITL el feia servir): la pujada no afegeix res.

**Abast honest del llançament amb els flags de l'Eva (tots `false`):** rep tot el pipeline clàssic millorat (SmartScan,
FileMiner, auto-extract, visió per API), el generador nou (criteris de càlcul, narrativa per criteri, taules, numeració
per presència, figures des dels seus annexos: assaigs, situació, tall retallat, geològic compost), la pestanya
«Imatges» amb la finestreta i la pujada. **No rep** la lectura de nivell A per Claude Code ni els lectors de fotos/figures
(a la finestreta hi haurà les tries deterministes i les seves pujades, sense «alternatives del lector»), ni la
conversió FH11. Posar Claude Code al seu ordinador (decisió «via A» del 23-08) és un pas a part, no aquest.

**Windows al PC del Josep** (per al pas 2):
- `py -0p` (via `cmd.exe`) dona **`-V:3.12 * C:\Program Files\Python312\python.exe`** i 3.11 a `C:\py311`. Prova en 3.12.
- `/mnt/c/claude/g3dt/projectes/` té els **7 projectes reals** (Castellar, Rubí, Linyola, Bell-lloc, Alcoletge, Vilanova,
  Anciles); `/mnt/c/claude/g3dt/xarxa-simulada/grup-carpetes-L1-0{1,2,3}/` simula la xarxa niada de l'Eva
  (`G3DT_NETWORK_PROJECTS`); `/mnt/c/claude/g3dt/env.txt` (271 B) sembla un `.env` de mostra: mirar-lo sense imprimir claus;
  `dades-eva/` té els seus logs reals (per saber quins flags i claus té ella).
- La versió instal·lada de `G3DT-Wizard.bat` és la **Windows nativa** de `INSTALL-EVA-v1.md` §2.6, NO la de `scripts/`
  (que crida WSL + `claude`). No substituir-la.

**Suite:** 31 vermells esperats = 17 `test_smartscan.py`, 7 `test_ai_pipeline_ranking_api.py`, 3 `test_fileminer.py`,
2 `test_ai_pipeline_trace.py`, 1 `test_bearing_stratum_n20_regression.py` (drift de fixture), 1 `test_groq_miner.py`.
**SmartScan és ON a producció**: la sessió de release ha de mirar la capçalera del fitxer i decidir si els 17 de
`test_smartscan` són fixtures antigues o defectes que l'Eva veuria. No donar-ho per fet.

## 3. Pas 1 — branca `release/…` (procediment proposat)

Fer-ho en un **worktree nou**, no in-place a `g3dt-prod/` (que és on el Josep prova el wizard i on viu experiment):

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt-prod && git fetch origin && git status --short   # net
git worktree add ../g3dt-release -b release/2026-09 production/g3dt-eva-v1
cd ../g3dt-release
git merge --no-ff experiment/nivell-a-2026-08              # esperats: 2 conflictes
git checkout --theirs templates/g3dt-jinja-template.docx && git add templates/g3dt-jinja-template.docx
# image_manager.py: resoldre a mà; el resultat ha de ser el d'experiment
git checkout --theirs automation/image_manager.py && git add automation/image_manager.py
git diff --cached experiment/nivell-a-2026-08 --stat        # només tests/test_image_cache_name.py i docs de producció
git commit                                                  # missatge: merge d'experiment a release/2026-09 + què s'ha resolt
# pyproject: pillow>=10.0 a dependencies (commit propi)
# CLAUDE.md «Inici de sessió»: afegir l'excepció del worktree g3dt-release / branca release/*
python -m venv .venv (o copiar el de g3dt-prod) ; pip install -e . ; suite sencera; tests/test_image_cache_name.py verd
# M341 des del worktree release (G3DT_CACHE_DIR propi per no barrejar caus): esperat idèntic a 2026-09-09-m341-nit
git push -u origin release/2026-09
```

`production/g3dt-eva-v1` **no s'avança fins al dia de la visita** (`git merge --ff-only release/2026-09` i push, just
abans del pull presencial): així el que l'Eva rep és el SHA provat, i mentrestant producció continua sent el que ella té.
Cap `--force` enlloc (les dues branques ja són al remot).

## 4. Pas 2 — prova en Windows natiu al PC del Josep (llista mínima)

Tot des de `cmd.exe`/PowerShell amb el Python de Windows, mai des de WSL:

1. `git clone` (o `git worktree` no: clon net) de `release/2026-09` a una ruta Windows, p. ex. `C:\claude\g3dt\app-release`.
2. `py -3.12 -m venv .venv` · `.venv\Scripts\activate` · `pip install --upgrade pip` · `pip install -e .` → anotar la
   llista `pip freeze` (és el que caldrà comparar amb el venv de l'Eva).
3. `.env` **calcat al de l'Eva** (claus i flags reals; `dades-eva/` i `INSTALL-EVA-v1.md` §2.5): tots els `G3DT_*` a
   `false`, `G3DT_NETWORK_PROJECTS` apuntant a `C:\claude\g3dt\xarxa-simulada` (o `projectes`). No «provar» amb flags de dev.
4. `python -m web` → `http://localhost:8765/review.html`: navegador de xarxa → Bell-lloc → **Començar** → cronometrar els
   prefills (referència real de l'Eva: 6-10 min; diagnòstic 23-08: 300 s de mitjana) → stepper «Llest».
5. Pestanya «Imatges» i secció «Imatges de l'informe»: alternatives, **pujar una foto** (JPG de mòbil amb EXIF) i una
   figura, peu, «Tornar a l'automàtic». Mirar que la pujada queda a `…\validation\uploads\imatges\` amb nom ID i que la
   miniatura surt (camins Windows: la pujada guarda `rel` en posix; `project_path / rel` funciona, però comprovar-ho).
6. **Generar informe** → obrir el `.docx` amb Word: imatges al seu lloc, numeració, cap resta de Jinja, mida del fitxer.
7. Un segon projecte (Alcoletge o Vilanova) de cap a cap, i un de nou de `dades-eva/` si n'hi ha cap de disponible.
8. Logs (`G3DT_LOG_*`): cap `Traceback`; anotar avisos de `soffice`/`pandoc` absents (esperats i inofensius).
9. Punt de retorn per a l'Eva: com desfer (`git checkout 1f1d7fd` o el SHA que tingui) si el dia de la visita falla res.

## 5. Pas 3 — presencial (el que aquesta sessió només ha de deixar preparat)

Full de ruta d'un full: còpia de seguretat de `C:\g3dt-ia\app` (i del seu `.env`), `git pull` (o `git fetch` +
`checkout` del SHA), `pip install -e .`, `python -m web`, un projecte seu de cap a cap amb ella al costat, punt de retorn.
Res en remot; res «per correu»; res que ella hagi de fer sola.

## 6. Seqüència d'obertura suggerida

1. `git branch --show-current` a `g3dt-prod/` (= experiment) i `git status --short` (net); `git fetch origin`.
2. Llegir `INSTALL-EVA-v1.md` sencer i els logs de `dades-eva/` per saber flags i claus reals (sense imprimir claus).
3. Decidir amb el Josep tres coses abans de tocar res: nom de la branca (`release/2026-09`?), data de la visita, i si el
   llançament inclou posar Claude Code a l'ordinador de l'Eva (proposta: no; és un altre pas).
4. Pas 1 sencer (merge, pillow, suite, M341, push de `release/…`).
5. Pas 2 en Windows amb `.env` calcat al de l'Eva.
6. Escriure `docs/PLA-RELEASE-2026-09.md` (o el nom que el Josep vulgui) amb el full de ruta del pas 3 i els resultats
   del pas 2; DECISION-LOG; handoff.

## 7. Què NO fer

- No avançar ni pujar `production/g3dt-eva-v1` abans de la visita; no `--force`; no `git reset` de branques pujades.
- No fer el merge in-place a `g3dt-prod/` (el Josep hi prova el wizard; i l'excepció del CLAUDE.md és per a experiment).
- No provar en Windows amb flags de desenvolupament («per veure-ho»): el que es prova és el que l'Eva tindrà.
- No barrejar la cau d'imatges de la release amb la de dev (`G3DT_CACHE_DIR` propi) ni la còpia de proves de Bell-lloc
  del Josep (`~/g3dt-prod-workspace`: compartida; no esborrar-hi res que no hagis creat).
- No commitejar `schemas/formats/learned/*` generats durant les proves.
- No tocar `geocode_coordinates.py` (via B de producció) ni la recepta ICGC.
- No demanar res a l'Eva (ni pull, ni proves, ni preguntes) sense el Josep.
- No presentar-li com a «millores» el que no s'hagi provat en Windows: el llistó del 23-08 és un sistema que li faci la feina.

## 8. Preguntes obertes per a la sessió (a decidir amb el Josep)

- Nom de la branca de release i data de la visita.
- Claude Code a l'ordinador de l'Eva: ara o després? (condiciona `G3DT_USE_LECTURA_HEADLESS` i els lectors).
- Els 17 vermells de `test_smartscan` amb SmartScan ON a producció: fixtures o defectes?
- Què fer amb `schemas/formats/learned/` de l'ordinador de l'Eva si divergeix del repo (el format learner escriu allà).
- Els `.env` de l'Eva: quines claus té avui (Anthropic, Groq, OpenAI?) i quin model de visió; sense OpenAI el
  `deep_folder_classify` salta (documentat a INSTALL §1) — cal saber-ho per interpretar els temps de prefills.
- Punt de retorn: quin SHA té ella ara mateix (`git log -1` al seu PC el dia de la visita) — anotar-lo abans del pull.

## 9. Per què això i no un pull directe (per si algú ho torna a preguntar)

El worktree es diu `g3dt-prod` però hi ha experiment; l'Eva segueix producció, que és del juliol. Entre les dues hi ha
253 commits, dos fitxers en conflicte, una dependència que cal declarar, i zero hores d'execució en Windows natiu.
Un pull li portaria 2 commits i cap millora visible; un merge sense prova en Windows li podria portar una arrencada que no
funciona i un abandó. Els tres passos existeixen per això.

## 10. CORRECCIÓ DEL JOSEP (2026-09-10, 20:30) — el llançament INCLOU Claude Code: l'Eva ha d'obtenir la mateixa qualitat que nosaltres

> «Tot el que hem fet parteix de la base que instal·larem Claude Code a l'ordinador de l'Eva, i se subscriurà a un pla
> que li doni accés a models suficientment bons. I si cal fer que corri a Linux (Ubuntu) a través de WSL, ho farem.
> No ho hem desenvolupat perquè jo obtingui bons resultats i ella no.»

Això **anul·la** l'«abast honest» del §2 i la pregunta 2 del §8: la mesura (M341 75 % / 69 % / 82 %) és amb Claude Code
llegint, i el que l'Eva ha de rebre és aquest procés. El que cal, verificat al codi el mateix vespre:

1. **Entorn: WSL2 + Ubuntu, no Windows natiu.** `automation/lectura/runner.py` fa `os.killpg`, `signal.SIGKILL` i
   `start_new_session=True` (POSIX: en Windows natiu la lectura no arrenca sense adaptar-la); `claude` i `soffice` en
   Linux són els binaris amb què s'ha mesurat tot. Al maig es va triar natiu per simplicitat («Windows natiu primer;
   Pla B: WSL», `PLA-DEPLOYMENT-EVA-2026-05-04.md` §1 i §10), no per cap impossibilitat, i el Pla B ja té els
   `scripts/*.bat` que assumeixen WSL. Cal: `wsl --install` (admin + reinici), unitat de xarxa muntada dins WSL
   (`/mnt/<lletra>` o `drvfs` per a l'UNC de `192.168.1.x`), navegador de Windows a `localhost:8765` (WSL2 ho reenvia).
2. **Claude Code + pla.** CLI a WSL amb el compte de l'Eva. Dimensionar el pla amb dades, no a ull:
   `docs/wizard-headless/mesures/ledger.py` (registre de consum per model) → tokens per projecte i per etapa. La lectura
   va amb `G3DT_LECTURA_EFFORT=xhigh` per defecte i topalls de 600/900 s per document; els lectors de fotos i figures
   són 2 crides més per projecte. Pro té finestres de 5 h amb límit: un projecte sencer pot exhaurir-lo → probablement
   Max. **El model NO es fixa amb `--model` ni al runner ni als lectors** (grep 2026-09-10): cal veure com es tria avui i
   fixar model i esforç a la config perquè no depenguin del defecte del compte. Gestió del límit d'ús (HTTP 400 «usage
   limits», memòria `reference_anthropic_usage_cap_error_shape`): el job s'ha d'aturar i dir-ho, no fallar en silenci.
3. **Que el pipeline sigui el mesurat.** (a) `G3DT_USE_LECTURA_HEADLESS=true` (botons Preparar / Enllestir / Des de
   zero; els tres executen `run_lectura_job`). (b) **Els lectors de fotos i de figures NO són al job**: es passen a mà
   (`lector_fotos.run`, `lector_figures.run`); cal integrar-los (una passada de cadascun per projecte, després de la
   lectura, abans dels prefills) — és feina de codi, amb test. (c) LibreOffice a WSL (`apt`) per als FH11 i els `.doc`.
   (d) Inventari de les claus API que encara calen a les fases clàssiques (visió per API, Groq, OpenAI classify): els
   logs d'avui no ho registren; derivar-lo d'una execució completa amb `G3DT_LOG_PATH`. Decidir: mantenir claus (cost
   petit per projecte) o passar la visió a Claude Code (`G3DT_PROD_USE_CLAUDECODE_VISION`) per a zero cost API.
4. **Prova de reproductibilitat en net (la porta GO/NO-GO real).** Tot s'ha mesurat al compte del Josep, amb el seu
   `~/.claude` (memòria automàtica del projecte, CLAUDE.md global). Els skills de lectura no usen cap MCP i no hi ha
   `.mcp.json` (verificat): bé. Però cal executar lectura + lectors + informe des d'un **perfil net** (HOME nou, sense
   memòria ni configuració del Josep, amb el model i l'esforç del pla de l'Eva) sobre 2-3 projectes del corpus i
   comparar amb la referència (M341, `compare_consolida`). Si coincideix, el resultat és del sistema, no de l'entorn.
5. **Els tres passos** es mantenen, amb el pas 2 fet a WSL amb perfil net, i el pas 3 amb: WSL, Claude Code, login,
   pla contractat, LibreOffice, `.env` amb els flags de lectura, i un projecte real d'ella de cap a cap («Preparar per
   demà» inclòs, cronometrat). El temps per projecte amb `xhigh` s'ha de mesurar i explicar-li (el botó ja diu «per demà»).

Preguntes obertes que substitueixen les del §8: pla (Pro vs Max) segons el ledger; com es fixa el model avui; ordre
d'integració dels lectors al job; claus API sí/no; data.

## 11. ESTAT DESPRÉS DE LA SESSIÓ DEL VESPRE (2026-09-10, 21:30) — llegiu `docs/PLA-RELEASE-2026-09.md`, que és el pla viu

Fet: pas 1 sencer (branca `release/2026-09` al worktree `clients/g3dt-release/`, merge net, M341 idèntic, venv net), el codi
que el §10 demanava (lectors al job, aturada per límit d'ús, pins + `requirements-lock.txt`), i la prova del §10.4 llançada.
Correccions al §10 fetes amb el codi a la mà: el runner **sí** fixa `--model` i `--effort` (i ja té branca Windows); el que no
és Windows-capable són els skills (ordres POSIX dins Claude Code) — la recomanació WSL es manté per això. Suite a release amb
el venv del lock i prova en perfil net: en curs (resultats a STATUS / DECISION-LOG 2026-09-10 (3) / sessió). `release/2026-09` (`e047ce6`) i experiment (`483cd48`) pujats a origin després de la suite del lock; cap canvi a
`production/g3dt-eva-v1`. Les preguntes que queden són les del §3 del pla (entorn, pla, claus, data).

**Nit (23:10):** el Josep ha decidit (WSL2 + Ubuntu; Max 5x; cap clau API; divendres 18-09-2026) i el **pas 2 està fet a WSL
com ho tindrà l'Eva** (clon net, lock, `.env` sense claus, Bell-lloc pel navegador: GO; DECISION-LOG 2026-09-10 (4), run
`2026-09-10-wsl-sense-claus-bell-lloc`). Queda el pas 3 presencial (`PLA-RELEASE-2026-09.md` §5) i, com a feina a part, un
projecte en castellà sense claus i els 4 defectes menors del `meta.json` del run.
