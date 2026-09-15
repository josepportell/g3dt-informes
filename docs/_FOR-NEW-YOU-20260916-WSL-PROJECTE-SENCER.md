# FOR NEW YOU — 2026-09-16: passada al clon WSL amb la UX nova del wizard i un projecte sencer de cap a cap

**Escrit:** 2026-09-15 (nit). **Per a:** la sessió de demà, 16-09-2026. Visita a l'Eva: **divendres 18-09** (cita de confirmació dilluns 14-09; pla viu `docs/PLA-RELEASE-2026-09.md`).
**Recap d'una frase:** ahir i avui s'ha fet la capa de confiança del wizard (pla A-G, 13 commits `5c63287..3c9328c` a `experiment/nivell-a-2026-08`, loop implementer→reviewer→tester complet, suite 31 vermells = esperats); **cap d'aquests commits és encara a `release/2026-09`** ni s'ha provat amb un job de lectura real. Demà: portar-ho a release, passar-ho al clon WSL com ho tindrà l'Eva i fer Bell-lloc (o Alcoletge) de cap a cap amb Claude Code llegint.

## 1. Ordre de lectura

1. Aquest document.
2. `STATUS.md` (primer paràgraf: estat A-G) i `docs/PLA-UX-WIZARD-2026-09.md` (què s'ha fet, SHA per bloc, què queda «després del 18-09», què s'ha descartat i per què).
3. `docs/PLA-RELEASE-2026-09.md` §4.2 (procediment exacte del pas 2 a WSL, ja fet una vegada el 10-09) i §5 (full de ruta presencial).
4. `docs/_FOR-NEW-YOU-20260911.md` §2-§4 (invariants de la lectura i de les imatges; M341 de referència) i `docs/_FOR-NEW-YOU-PREPARACIO-RELEASE-20260910-2000.md` §10-§11 (decisions del Josep: WSL2+Ubuntu, Max 5x, cap clau API, 18-09).
5. `.claude/sessions/2026-09-15-session.md` (entrades dels agents i de l'orquestrador: on ha caigut cada bug).
6. Memòries: `feedback_no_pull_eva_success_criterion`, `feedback_no_rm_test_state_you_did_not_create`, `feedback_wizard_ui_rules_josep`, `feedback_compare_test_names_not_counts`, `feedback_rtk_git_show_compressed`.
7. Per a l'Eva: `docs/COM-FUNCIONA-EVA-2026-09.html` (el Josep encara l'ha de llegir; còpia a `C:\claude\g3dt\`).

## 2. Estat de les branques (verificat 2026-09-15 21:00)

| on | branca | HEAD | notes |
|---|---|---|---|
| `clients/g3dt-prod/` (aquest worktree) | `experiment/nivell-a-2026-08` | `3c9328c` | els 13 commits d'UX; **no pujat** a origin des de `c258907` |
| `clients/g3dt-release/` (worktree) | `release/2026-09` | `b7decee` | 13 commits per darrere d'experiment; té 6 propis (pillow, egg-info, CLAUDE.md, M341 release…) que experiment no té → **merge, no ff** |
| `~/g3dt-release-wsl-test/app` (clon net) | `release/2026-09` | `95e669b` | és el clon de la prova del 10-09; té fitxers no versionats de la prova (runs, `learned/*`); `.env` sense cap clau API (noms de variables al §5) |
| `production/g3dt-eva-v1` | — | `123b4f2` | **no tocar** fins al dia de la visita |

Els 13 commits d'UX només toquen `templates/validation/review.html`, `automation/lectura/inventory.py`, `automation/sync_workspace.py`, `web/lectura_service.py`, `web/api.py`, `web/wizard_service.py` i tests. Cap canvi al generador ni als lectors → M341 no s'ha de moure.

## 3. Regles d'interpretació (no òbvies)

- **Els dos modes del wizard.** Amb `/api/jobs` a 404 (via clàssica: el servidor del Josep al 8765) es veu «Començar amb aquesta carpeta» i el panell «Visió IA»; amb `G3DT_USE_LECTURA_HEADLESS=true` es veu el panell de jobs amb UN botó «Començar»/«Continuar», l'enllaç «Fer un informe des de zero», «Actualitzar» i la taula. Tot el que s'ha verificat al navegador ahir i avui és en via clàssica (Bell-lloc al 8765) més el panell nou en un servidor temporal al 8796 **sense llançar cap job**. Un job real amb Claude Code + la UX nova encara no s'ha vist mai.
- **L'estimació abans del clic és conservadora, no exacta.** Bell-lloc diu «19 documents · uns 55 min» i la realitat del 10-09 va ser 18 documents i 45,7 min: sense md5 el duplicat compta, i `estimate_for_documents` usa les medianes de la telemetria (`docs/wizard-headless/mesures/*/telemetry*`). Si demà el job real triga menys que l'estimació, és el comportament esperat. Si triga MÉS, mira la concurrència (`G3DT_LECTURA_CONCURRENCY=2` al clon) i la telemetria que l'estimador llegeix.
- **«Queden N camps a revisar»** compta camps amb badge «revisar» o estat candidats/no trobat, deduplicat per camp i **excloent la llegenda** (`.source-legend` és dins de `#wizardForm`; el bug de +1 es va veure al navegador, no als tests). A Bell-lloc via clàssica el correcte és «Tots els camps revisats». Amb lectura activa hi haurà CAUTELA/candidats → un N > 0 és normal.
- **La suite té 31 vermells esperats** (`docs/wizard-headless/mesures/suite-vermells-esperats.txt`, per classe). Compara NOMS (les capçaleres `___ nom ___`, no `grep ^FAILED`, que es trunca als parametritzats llargs). Un implementer va citar «13 errors» que dues passades netes no han reproduït: eren passades concurrents.
- **`_sources: user` a `user_data.json` = camp canviat per l'Eva respecte del prefill** (verificat a `save_wizard`). Amb això es va comptar 33 camps canviats a Vacarisses (juny, via B). El bloc G escriu ara una línia per desat amb els noms; el «ja era de l'Eva» surt d'aquest fitxer, no de la cache.
- **`DEV_MODE` del frontend és `?dev=1` a la URL**, no `G3DT_DEV_MODE`. Les pestanyes Dev/Pipeline no es veuen sense això; el que s'ha amagat al bloc A no estava darrere de cap flag.

## 4. Invariants estructurals (no desfer)

- `templates/validation/review.html` `_wizardBarPendingBadges()`: única font de veritat del comptador i del «Revisar primer»; filtra `.source-legend` i dedueix per camp. Test `tests/test_wizard_bar_pending_count.py`.
- `_wizardSourceLabel()`: mapa determinista cadena→etiqueta; la cadena original SEMPRE al `title`. `plantilla generada` és «calculat» (frase per patró), `Eva template` és «el teu informe anterior», `user` i `user_data.json anterior` són «tu». 26 casos a `tests/test_review_html_source_label.py`: si afegeixes una font nova a `wizard_service`, afegeix-la aquí.
- `saveWizard()` retorna `true` o un string d'error; `generateReport()` NO genera si el desat falla (era el CRITICAL de la primera revisió). `_wizardBarSoftGateShown` es reinicia al `finally` i al retorn anticipat.
- `#wizardBar` només visible amb `wizardDataLoaded === true` i sense `#evaPreQuestions` obert; `wizardDataLoaded` es reinicia a `onProjectChange` i `nbAfterCancel`. El `padding-bottom` del formulari el posa un `ResizeObserver` sobre la barra (84 px sol, 147 px amb el resultat obert).
- `_jobsUpdateComencarButton()`: `data.partial` es mira ABANS de `!data.n_docs` (test `tests/test_review_html_jobs_comencar_partial.py`); el botó es desactiva mentre «calculant la durada…»; `_jobsEstimateSeq` + `AbortController` descarten respostes velles.
- `web/wizard_service.py::_persisted_user_fields(project_path)`: l'`_already_user` del bloc G llegeix `user_data.json → _sources` abans d'escriure. No tornar a la `_prefill_cache` (la mateixa funció la buida al final).
- `automation/sync_workspace.py::resolve_workspace_leaf()` és l'embolcall públic; `lectura_service` no ha de tornar a cridar la privada.
- `count_claude_documents()` no fa md5 ni obre fitxers (és el que la fa apta per a la xarxa a cada canvi de carpeta). No la substitueixis per `build_inventory`.

## 5. Procediments

**Suite (10 min de marge; comparar noms):**
```bash
cd /home/josep/projects/claudecode-job/clients/g3dt-prod
timeout 600 .venv/bin/python -m pytest tests -q -p no:cacheprovider > /tmp/suite.txt 2>&1; tail -1 /tmp/suite.txt
awk '/^_+ .* _+$/' /tmp/suite.txt | sort   # noms dels vermells
```
Tests ràpids de l'HTML i dels blocs E/G (uns 20 s):
```bash
.venv/bin/python -m pytest tests/test_review_html_*.py tests/test_wizard_bar_pending_count.py tests/test_lectura_estimate.py tests/test_lectura_inventory.py tests/test_save_wizard_changed_fields_log.py tests/test_lectura_jobs.py tests/test_lectura_job_text.py -q
```

**Servidor temporal amb lectura activa sense tocar el 8765** (només per veure el panell; NO premis «Començar» aquí si no vols un job real al workspace del Josep):
```bash
G3DT_USE_LECTURA_HEADLESS=true .venv/bin/python -m uvicorn web.server:app --host 127.0.0.1 --port 8796
```
El del 8765 (`python -m web`, pid antic) serveix l'HTML en viu però el Python carregat és d'abans d'E/G: per a canvis de backend cal reiniciar-lo (és del Josep: pregunta abans).

**Clon WSL de la prova del 10-09** (`docs/PLA-RELEASE-2026-09.md` §4.2 té el procediment complet):
- App: `~/g3dt-release-wsl-test/app` (branca `release/2026-09` @ `95e669b`, venv propi amb el lock). Per portar-hi la UX: primer merge a `release/2026-09` al worktree `clients/g3dt-release/` (vegeu §6), push, i al clon `git pull` (és un clon d'origin, no un worktree).
- `.env` del clon: cap clau API (les variables `*_API_KEY` hi són amb valor buit), `G3DT_USE_LECTURA_HEADLESS=true`, `G3DT_LECTURA_MODEL=sonnet`, `G3DT_LECTURA_EFFORT=xhigh`, `G3DT_LECTURA_AUTH=login`, `G3DT_LECTURA_CONCURRENCY=2`, `G3DT_LECTURA_IMATGES=true`, `G3DT_USE_GROQ=0`, `G3DT_ORTHO_ENRICHMENT=0`, `G3DT_NETWORK_PROJECTS=/mnt/c/claude/g3dt/xarxa-simulada` (Bell-lloc és a `grup-carpetes-L1-01/grup-carpetes-L2-03/4001612 BELL-LLOC`), workspace/reports/cache propis del clon (mira els valors: `sed -n '/G3DT_/p' ~/g3dt-release-wsl-test/app/.env`).
- HOME net: `~/g3dt-release-wsl-test/home` (té `.claude/.credentials.json` del Josep i ja un `.claude.json` de la prova anterior). Llança el servidor amb `HOME=/home/josep/g3dt-release-wsl-test/home` perquè `claude` no vegi la memòria del Josep.
- Port de la prova anterior: 8766. Playwright: les captures només es poden desar dins del projecte (`.playwright-mcp/`); esborra les teves en acabar, no les del 10-09.
- El job de Bell-lloc a c2 va trigar 45,7 min. «Enllestir» l'endemà 2 s, «Generar» 4 s. Amb la UX nova el botó dirà «Continuar» si el job queda `ready`.

**Caus:** `G3DT_CACHE_DIR` del clon és propi (no barrejar amb `~/g3dt-prod-cache`). Els documents llegits es cachegen per md5: repetir Bell-lloc al mateix clon després d'un job complet és quasi instantani (bé per a provar la UX, inútil per a mesurar temps). Per a un temps real cal un projecte no llegit en aquest clon (Alcoletge) o esborrar només la cau de lectura del clon.

**`schemas/formats/learned/*`** es reescriuen a cada «Generar»: no es committen (`git checkout --` del tracked, `rm` del nou, sempre comprovant `ls -la --time-style` que són d'avui).

**rtk:** `git show`/`git diff` surten comprimits al hook; per llegir un diff sencer, redirigeix a fitxer i llegeix-lo.

## 6. Seqüència d'obertura suggerida

1. `git branch --show-current` a `g3dt-prod/` (= `experiment/nivell-a-2026-08`, HEAD `3c9328c`) i `git status --short`: només `STATUS.md` modificat i els docs sense seguiment d'ahir (`COM-FUNCIONA-EVA`, `PLA-UX-WIZARD`, sessió, `docs/diagnostics/…20260915.md` generat per la suite). Demana al Josep si vol commitejar els docs.
2. Push d'experiment (`git push origin experiment/nivell-a-2026-08`): els 13 commits només són locals.
3. Al worktree `clients/g3dt-release/`: `git merge --no-ff experiment/nivell-a-2026-08` (no hauria de conflictar: release només té docs, pillow, egg-info i CLAUDE.md propis; si `review.html` conflicta, la d'experiment). Suite curta (§5) + `tests/test_image_cache_name.py`. Push de `release/2026-09`.
4. Al clon `~/g3dt-release-wsl-test/app`: `git pull`, `pip install -e . -c requirements-lock.txt` (no hi ha deps noves, però costa poc), comprova `.env` (§5) i que `claude --version` funciona amb el HOME net.
5. Servidor al 8766 amb el HOME net → navegador de Windows o Playwright → navegador de xarxa 3 nivells → Bell-lloc: comprova el botó «Començar · N documents · uns X min», prem-lo, tanca la pestanya, torna: la taula ha de dir «Llegint documents 7/18 · ≈ 25 min restants». Cronometra.
6. En acabar: «Continuar» (o la fila «Enllestir») → formulari: comprova la barra («Queden N camps a revisar» ha de ser coherent amb els badges CAUTELA/candidats), la llegenda, cap fuita de desenvolupador, «Visió IA» absent (només s'amaga amb el panell de jobs actiu: és l'única cosa del bloc A que NO s'ha vist al navegador), Imatges (alternatives del lector, pujada, peu, tornada), «Generar informe» → docx a la xarxa. Mira el log del clon: una línia `wizard desat … camps canviats per l'Eva:` per desat.
7. Escriu el run a `docs/wizard-headless/mesures/runs/2026-09-16-…/meta.json` amb el patró del 10-09 (temps, vs or, M341 si toca), DECISION-LOG, STATUS.

## 7. Què NO fer

- No avançar `production/g3dt-eva-v1` ni fer `--force`/`reset` de res pujat. No proposar pull/merge a l'Eva.
- No fer el merge in-place a `g3dt-prod/` (és experiment i on el Josep prova el wizard); el merge va al worktree `g3dt-release/`.
- No provar al clon amb claus API «per anar més ràpid»: la decisió és cap clau; si falta alguna cosa sense claus, és una troballa, no un obstacle.
- No prémer «Començar» al servidor temporal del 8796 sobre el worktree d'experiment: dispararia un job real de Claude Code contra el workspace del Josep amb el seu HOME.
- No esborrar `.playwright-mcp/` sencer (hi ha captures del 10-09 del Josep) ni res del clon que no hagis creat (`feedback_no_rm_test_state_you_did_not_create`).
- No committejar `schemas/formats/learned/*` ni `docs/diagnostics/*` generats.
- No fer servir `window.confirm`/`alert` a la UI (bloqueja Playwright i és lleig per a l'Eva): la porta suau és inline.
- No tocar `automation/geocode_coordinates.py` (via B de producció).

## 8. Tasques obertes

- [ ] Commit dels docs d'ahir/avui (decisió del Josep): `PLA-UX-WIZARD`, `COM-FUNCIONA-EVA`, `STATUS`, sessió.
- [ ] Push d'experiment; merge a `release/2026-09`; push.
- [ ] Pas 2 repetit al clon WSL amb la UX nova: Bell-lloc (cau ja llegida → temps no representatiu) o Alcoletge (temps real), un job de cap a cap, docx, log de G.
- [ ] Veure amb els propis ulls: «Visió IA» amagat amb jobs actiu; «Queden N» coherent amb la lectura; «Continuar» després d'un job `ready`; text «no he pogut mirar tota la carpeta» si cal simular un `partial`.
- [ ] `docs/GUIA-EVA-WIZARD.md` està desfasada (descriu «Llegir PDFs de camp» de la via B): actualitzar-la o substituir-la pel doc HTML abans del 18-09.
- [ ] Preguntar al Josep si vol la llista densa de camps segurs (§«Després del 18-09» del pla) abans o després de la visita.
- [ ] Els 4 defectes menors del run del 10-09 (19/18, «Visió IA (0/4)» — ja resolt pel bloc A quan el panell és actiu —, `G3DT_REPORTS_DIR`, capa d'observacions a cada obertura) continuen al pla «després del 18-09».

## 9. Guanys que no surten a cap mètrica

- El wizard ja no parla en idioma de desenvolupador: sense Groq, ConceptScout, «FileMiner regex», «Lectura headless» ni cadenes `groq:…v0.pdf`; les etiquetes diuen «tu», «plànol», «assaigs de camp», «el teu informe anterior»…
- Els errors ja no s'esvaeixen als 5 segons dalt de tot d'una pàgina de 6.000 px: viuen a la barra fins que l'Eva els tanca. Un desat fallit ja no genera un informe sobre dades velles.
- El botó d'inici diu la veritat abans que ella el premi («19 documents · uns 55 min · pots tancar la pestanya i tornar») en lloc de «per demà».
- A partir d'ara cada desat deixa al log quins camps toca l'Eva: en 3-4 projectes tindrem dades per decidir què plegar, en lloc d'opinar.
- Crítica UX (17/40 Nielsen) i pla d'accions queden documentats amb els descartats i el perquè: si algú proposa checkmarks de secció o GSAP, la resposta ja és escrita.

*Fi. Handoff 2026-09-16: la UX A-G és a experiment; demà release + clon WSL + un projecte sencer amb Claude Code llegint.*
