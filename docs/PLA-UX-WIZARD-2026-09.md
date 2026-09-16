# Pla UX del wizard abans del 18-09-2026 — capa de confiança, no cosmètica

**Escrit:** 2026-09-14 (vespre). **Origen:** crítica dual-agent del wizard (17/40 Nielsen; veredicte «intercanviable per
categoria») i les decisions del Josep del mateix vespre: «Començar» amb durada real en lloc de «Preparar per demà»;
plegar per estat del camp, mai per secció ni amb bloqueig; «Guardar Dades» fora.

**Evidència que mana:** `dades-eva/_DEBUG PRODUCCIO/…/user_data.json` (Vacarisses, juny, via B): **33 camps canviats
per l'Eva** en un sol projecte (`_sources: user` = canviat respecte del prefill, verificat a `save_wizard`). No tenim
dades de quines seccions no toca mai → no es plega res per costum.

**On es fa:** `experiment/nivell-a-2026-08` (worktree `g3dt-prod/`), tot dins `templates/validation/review.html` llevat
d'E i G. Cap canvi al generador → M341 no es mou. Després, merge a `release/2026-09` i prova al clon WSL sense claus
(`PLA-RELEASE-2026-09.md` §4.2) abans d'avançar `production/g3dt-eva-v1`.

## Ordre (efecte / esforç)

| # | Canvi | Toca | Esforç | Estat |
|---|---|---|---|---|
| A | **Amagar fuites de desenvolupador**: `#groqModelSelectNB` (l. 2390), `#conceptCoverageBanner` (l. 2606), subetiquetes `.step-files` («FileMiner regex», «Groq: +9 prefills», «ICGC ortho+visió»), capçalera «Lectura headless — assaigs de camp» (l. 2774), «Visió IA (0/4)» amb lectura activa (defecte 2 del run 09-10). | CSS + 3 condicions JS | 30 min | ✅ `5c63287` |
| B | **«Format nou detectat» neutre**: `renderFormatLearning` (l. 6842) sense ambre ni «revisar» als camps que ja tenen valor; text «Del plànol A.01 n'he llegit 1 dada; les altres surten d'altres fonts». | JS | 1 h | ✅ `983145c` |
| C | **Barra inferior fixa**: «Generar informe» + resultat/error persistent fins que ella el tanqui (substitueix `showMessage` 5 s l. 3460 i `#wizardResult` l. 2980) + «Desat automàticament · hh:mm» (treu `#btnSaveWizard` l. 2974; l'autosave l. 7259 ja hi és) + comptador «Queden N camps a revisar» amb porta suau (confirm, mai bloqueig). | HTML + CSS + JS | 2-3 h | ✅ `4115340` |
| D | **Badges en llenguatge d'Eva**: `setSourceBadge` (l. 5989, 14 crides) → 5 etiquetes («plànol», «el teu informe anterior», «tu», «per defecte», «llegit») amb el fitxer al `title`; llegenda d'una línia sobre el formulari. | JS | 1-2 h | ✅ `648f213` |
| E | **Un sol botó «Començar» amb durada abans del clic**: subtítol «18 documents · uns 40 min · pots tancar la pestanya». Backend: `/api/jobs` retorna `n_docs` estimat per a projectes sense job (inventari ràpid de la xarxa, sense copiar) i `estimate_for_documents()` (`jobs.py` l. 424). Frontend: fusiona Preparar/Enllestir/Des de zero en «Començar» / «Continuar» (segons `_ACTION`); «des de zero» com a enllaç petit; amaga «Començar amb aquesta carpeta» quan el panell de jobs és actiu. | Python + JS | 3-4 h | ✅ `4e5b755` |
| F | **Tancar l'stepper**: acabat → una línia «Llegits 18 documents · avui 18:32»; títol «G3DT · Informe geotècnic»; estat buit sense «desplegable». | JS + text | 1 h | ✅ `b965024` |
| G | **Instrumentar el desat**: `save_wizard` ja calcula `_is_changed`; escriure una línia INFO amb la llista de camps canviats. En 3-4 projectes amb via A sabrem què no toca mai. | Python | 30 min | ✅ `3577b9c` |

**Fet 2026-09-15 (A-D, F):** 5 commits + 3 d'esmenes (`8bacc4e` revisió: desat fallit no genera, mapa d'etiquetes, padding dinàmic, contrast, barra només amb formulari, concordança, botó únic; `6ea44e9` el comptador no compta la mostra de la llegenda; `c6f82d0` «plantilla generada» = calculat). 28 tests nous (`test_review_html_source_label.py` 26, `test_wizard_bar_pending_count.py` 2). Suite: 31 vermells = els esperats, 0 nous. Verificat al navegador sobre Bell-lloc (via clàssica, jobs 404): pendent la mateixa passada al clon WSL amb lectura activa. E i G queden ⏳.

**Fet 2026-09-15 (E, G):** `4e5b755` (E: `count_claude_documents` per nom sense md5, `estimate_for_project` + `GET /api/jobs/estimate/{p}`, un sol botó «Començar»/«Continuar» amb la durada al subtítol, «des de zero» com a enllaç), `3577b9c` (G: una línia INFO per desat amb els noms dels camps canviats), esmenes `327e620` (el «ja era de l'Eva» surt de `user_data.json`, no de la cache volàtil; `resolve_workspace_leaf` públic; botó desactivat mentre calcula; text honest si el recompte és parcial; `AbortController`), `1e72a34` + `3c9328c` (recompte parcial amb 0 documents mostra el text informatiu). 51 tests nous. Suite: 31 vermells = els esperats, 0 errors. Verificat al 8796 amb lectura activa: arrel → «Tria la carpeta del projecte» (desactivat); Bell-lloc → «19 documents · uns 55 min · pots tancar la pestanya i tornar»; Alcoletge → «15 documents · uns 45 min». L'estimació és conservadora (Bell-lloc real: 18 documents, 45,7 min; el duplicat no es detecta sense md5 i l'estimador usa les medianes de telemetria). Pendent: la mateixa passada al clon WSL (`PLA-RELEASE-2026-09.md` §4.2) abans del merge a `release/2026-09`.

Total A-G: ~10-12 h. A-D són la capa de confiança (5-7 h) i van primer; E és el que més canvia la primera pantalla;
F-G si hi ha temps. Cada bloc = commit propi + captura abans/després.

## Després del 18-09 (només si l'Eva torna a fer servir el wizard sola)

- Camps segurs en **llista densa de lectura** (etiqueta · valor en una línia, clic per editar); els «candidats / revisar
  / no trobat» sempre desplegats. Res darrere d'un clic.
- Capa «Observacions de camp» només si no està contestada (defecte 4); comptador 19/18 (defecte 1); `G3DT_REPORTS_DIR`
  (defecte 3).
- Accents a les etiquetes visibles; paleta amb variables CSS; tipografia de les notes de càlcul (11 px gris → llegible).
- «Alternatives (cap)» no clicable; tres patrons de booleà → un.

## Descartat (i per què)

- **Checkmarks de secció amb bloqueig de «Generar»**: rígid al vintè informe; la revisió és per camp, no per secció.
- **Desplegar amb scroll (GSAP ScrollTrigger)**: és animació, no atenció; afegeix una llibreria a una pàgina sense cap.
- **Canviar l'etiqueta del botó després del clic**: l'expectativa de durada es forma abans de prémer.
- **Redisseny visual ara**: l'Eva no abandona pel Flat UI; abandona pel vocabulari aliè i pels avisos que no veu.

*Fi. Pla UX wizard 2026-09: A-G abans de la visita, la resta després.*
