# FOR NEW YOU — 19-09-2026: tres feines obertes i dos defectes veïns anotats

**Escrit:** 2026-09-18. **Per a:** la sessió següent.
**Recap d'una frase:** el pendent ha deixat de decidir-se sol — el wizard el proposa amb la raó escrita i l'Eva hi diu la seva (`7624629`); pel camí van caure les capçaleres buides de 4.4/4.5 i un text sense accents dins un informe signat (`6b0a6af`), i queden **tres feines** i **dos defectes veïns** sense tocar.

**La visita a l'Eva: objectiu 26-09-2026, sense confirmar.** No hi ha pressa de vigília.

## 1. Ordre de lectura

1. Aquest document.
2. `STATUS.md` — primer paràgraf, i el **punt 0a** de «Open items» (repàs d'accents: hi ha la mesura feta).
3. `docs/DECISION-LOG.md`, entrades **2026-09-17 (4)** i **2026-09-18** — el «per què» de cada decisió amb les alternatives rebutjades.
4. `docs/troballes/TROBALLA-SOLAR-PLA-VS-VESSANT-2026-09-17.md` — llegeix **l'ADDENDA i la §8**: el cos original del document té el diagnòstic **equivocat** i l'addenda el corregeix.
5. `docs/PREGUNTES-EVA-PENDENTS.md` — preguntes **17** (ampliada) i **40** (nova).
6. `MEMORY.md` del projecte, sobretot `feedback_wizard_ui_rules_josep`, `feedback_reference_projects_are_situations_not_targets`, `feedback_check_signed_phrasing_before_template_change`, `feedback_measure_baseline_before_coding`, `feedback_no_pull_eva_success_criterion`.
7. `docs/_FOR-NEW-YOU-20260917-1900.md` §3, §6 i §7 — el patró de fons i els invariants del 17-09 segueixen tots vigents.

## 2. Estat de les branques (verificat 2026-09-18)

| on | branca | HEAD |
|---|---|---|
| `clients/g3dt-prod/` (worktree de treball) | `experiment/nivell-a-2026-08` | `7624629` — **no pujat** |
| `clients/g3dt-release/` | `release/2026-09` | `d80633e` |
| `~/g3dt-release-wsl-test/app` (clon net) | `release/2026-09` | `37c8c93` — li falta el merge de les UTM i tot el d'aquests dos dies |
| `production/g3dt-eva-v1` | — | `123b4f2`, **intacta** |

Commits d'aquests dos dies: `6b0a6af` (pendent desconegut + seccions buides + accents del 4.5), `7624629` (el wizard proposa i l'Eva decideix).

## 3. EL PATRÓ DE FONS (llegeix això abans de res)

Totes les avaries d'aquests dos dies són **la mateixa**, i cada arranjament ha destapat la següent:

- Les UTM es perdien per una coma decimal → tapaven que el pendent no es consultava mai.
- El pendent desconegut es tractava com a 0 % → l'informe deia «es tracta d'un solar pla».
- Arreglar això va destapar que 4.4 i 4.5 sortien com a **capçaleres buides** damunt la signatura de l'Eva — i no només a Rubí: **Castellar també**, des de sempre.
- Omplir-les va destapar que el text del 4.5 estava escrit **sense accents**, dins un informe signat.
- I la revisió de la UI va destapar que la raó de `site_condition` **desapareixia al segon autosave**, una regressió que havíem introduït nosaltres el mateix dia.

**Una avaria silenciosa fa d'ombra a la següent.** Quan tanquis un forat, torna a mirar: probablement n'hi ha un a sota. I la pregunta bona mai és «quin valor hi posem» sinó **«com distingim "no ho sé" de "ho sé i és això"»** — i, quan no ho sabem, com ho portem davant de l'Eva en comptes de decidir-ho sols.

## 4. FEINA 1 — preguntes 17 i 40 a l'Eva (visita del 26-09)

`docs/PREGUNTES-EVA-PENDENTS.md`. Les dues estan escrites i llestes; el que falta és **fer-les**.

- **17** (ampliada el 17-09): quan un solar és «antropitzat» i quan no; si el pendent decideix «Tot i no ser un solar pla» i amb quin llindar. **L'evidència nova**: Rubí és l'ÚNIC projecte on §3.3.1 i §4.2 duen capçalera diferent, i la de §3.3.1 és **«Al solar,»** — una capçalera neutra que no afirma res. `ANALISI-NARRATIVA-2026-09-06.md` §4 no la va registrar. El sistema ja l'adopta com a defecte honest quan no sap el pendent; cal que ella ho confirmi.
- **40** (nova): quin pendent justifica 4.4/4.5; si mana el pendent d'on es fonamenta en comptes de la mitjana de la parcel·la; si la 4.4 pot anar sola; i **(c-bis) el mètode**: nosaltres escrivim la fórmula inline (`FS = tan(φ)/tan(β)`) amb F=1,5 del CTE, i ella redacta en prosa remetent als **àbacs de Hoek & Bray** amb **F=1,8 com a factor del vessant actual**. D'on surt aquest 1,8 no és deduïble: cal preguntar-ho.

**L'evidència dura, per si la necessites a la conversa:** Castellar (pendent ICGC 33 %) porta 4.4 i 4.5 amb l'anàlisi sencera; Rubí (21,6 %) no en porta cap, i al §2.1.2 ella escriu «13,20 metres… **tot i que la zona de treball es mostra totalment plana. La pendent comença la zona posterior**». Cap llindar sobre la mitjana separa els dos casos.

## 5. FEINA 2 — repàs d'accents (`STATUS.md` punt 0a)

**No comencis accentuant literals.** La mesura ja està feta (2026-09-17): **393 coincidències en 55 fitxers** d'`automation/`, però **la majoria NO arriben al `.docx`**.

Verificat: cap de les frases de `section1_presentacio.py`, `section2_treballs.py` ni `section3_geologia.py` («condicions hidrologiques», «posicio del nivell freatic», «caracteristiques geotecniques», «fonamentacio mes adequat») apareix a cap informe generat ni a cap signat de l'Eva. La plantilla porta el seu propi text fix i aquesta prosa no s'hi enganxa.

**Ordre correcte:**
1. Per cada mòdul de secció, establir **si el seu text arriba de debò al `.docx`** — la prova és generar i cercar-hi la frase. Sense aquest pas es repassa prosa morta i es deixa la viva.
2. Accentuar només el que hi arriba, comparant abans amb el text signat (memòria `feedback_check_signed_phrasing_before_template_change`).
3. Anotar què resulta ser codi mort: si sections 1/2/3 generen prosa que la plantilla no fa servir, és una pregunta pròpia — la plantilla la va substituir i ningú ho va netejar?

El 4.5 (`automation/sections/section4_conclusions.py`) **ja està fet** a `6b0a6af`, inclòs `paral·leles` amb ela geminada.

## 6. FEINA 3 — decisió 2: els 18 camps de 64

Mesurat sobre els prefills reals de Rubí: **64 camps** de cara a l'Eva, **18** amb valor generat/plantilla/per defecte presentat com a automàtic, i fins fa dos dies **cap** comptava a «Queden N camps a revisar».

- **Derivacions legítimes** (no toquis): `num_dpsh_tests`, `table_dpsh_range`, `num_site_photos`, `utm_x`/`utm_y`.
- **Escriuen prosa a l'informe**: `site_condition` (**ja resolt**), `site_description`, `access_description`, `settlement_sentence`, `access_street`, `lab_tests_text`.
- **Defectes estàndard sobre l'edifici**: `foundation_depth_m=0,3`, `has_basement=False`, `has_retaining_walls=False`, `num_soil_levels=1`, `sulfate_level_name='1er nivell'`, `data_signatura`.

**La bona notícia: la peça que faltava ja està feta i és genèrica.** El botó «D'acord, així» (`CONFIRMABLE_PROPOSAL_FIELDS` a `review.html`, `_FORCEABLE_USER_FIELDS` a `wizard_service.py`) es va construir a posta per reaprofitar-lo. Per a cada camp nou: fer que el backend l'enviï amb `source: 'revisar'` + `note`, afegir-lo a les dues llistes, i posar-hi el botó.

**El que NO pots fer sense resoldre abans el comptador:** treure la capa «Observacions de camp» (`#evaPreQuestions`, `review.html:2706`), que s'obre sola i incompleix la regla 2 del Josep. `PRE_QUESTION_FIELDS` és **l'únic lloc del codi** que tracta «font ≠ user» com a senyal de «cal revisar» per a `site_description`, `access_description` i `is_anthropized`. Treure-la sense res més enviaria tres camps a l'informe amb text que l'Eva no ha vist mai, i el comptador diria «tots revisats». La solució ha de fer les dues coses alhora.

**Nota del Josep (2026-09-18):** el comptador puja **+3 per projecte** i li va bé — és el disseny que va demanar. No ho «optimitzis» cap enrere.

## 7. Els dos defectes veïns, anotats i NO tocats

Tots dos són de la mateixa família i viuen documentats a la **§8 de la troballa**.

### (a) Vilanova es genera en CATALÀ un informe que l'Eva signa en CASTELLÀ

El `.docx` signat de Vilanova és sencer en castellà: §3.3.1 hi diu «En la zona de estudio no se han detectado marcas de inicios de procesos de erosión relacionados con la escorrentía hídrica superficial» — que és literalment `SITE_CONDITION_ES`, la branca de sortida ràpida de `site_condition_sentence`.

Però la mesura M341 del 10-09 (`runs/2026-09-10-m341-pujada/vilanova/viaA/_context_usat.json`) mostra `report_language: 'ca'` i un `site_condition` en català.

**Això no és una frase mal triada: és tot el document en la llengua equivocada**, i és més gros que el que perseguíem. Anciles (l'altre projecte ES) sí que es detecta bé, o sigui que la detecció existeix i falla només aquí. Comença per `_get_project_language()` i per què Anciles encerta i Vilanova no.

### (b) `wizard_service.py:369` converteix un «no antropitzat» conegut en «no ho sé»

```python
is_anthro = None if 'default' in anthro_source else (_get_val('is_anthropized') or None)
```

`_get_val` retorna `entry.get('value','') or ''`. Si `is_anthropized` val **`False` de debò** (llegit, no per defecte), `_get_val` dona `''`, i `'' or None` → `None`. Un fet conegut es presenta com a desconegut, i `site_condition_sentence` tria una altra branca.

És la **imatge especular** del defecte que hem passat dos dies tancant: allà un desconegut es tornava afirmació; aquí una afirmació es torna desconegut. Detectat per revisió, **no verificat amb dades reals, no arreglat**. Hi ha precedent de com fer-ho bé al mateix fitxer: el bloc de `site_condition` llegeix el valor **cru** de `merged` en comptes de passar per `_get_val`, precisament per no amagar un `0,0` explícit.

## 8. Invariants estructurals (no desfacis això)

- **`_applyFieldNote` (`review.html`) assigna SEMPRE, buit inclòs.** Els nodes del formulari són estàtics i compartits entre projectes: una nota que només s'escriu quan n'hi ha es queda enganxada sobre el projecte següent. Mateixa lliçó que `_updateUtmWarning` (que per això també assigna sempre).
- **`_FORCEABLE_USER_FIELDS` (`wizard_service.py:60`) és una allowlist, no una comoditat.** El servidor no es pot refiar de qualsevol nom que arribi a `forced_user_fields`: marcar `'user'` un camp que l'Eva no ha tocat trencaria la precedència Eva > lector. El comentari hi diu quan ampliar-la.
- **La guarda de `site_condition` mira `source == 'user'`, NO `if not _get_val(...)`.** Amb la guarda antiga la `note` desapareixia al segon autosave, perquè el `<textarea>` viatja sempre a `collectWizardFields()` i `_load_existing_user_data()` no persisteix mai `note`.
- **Les guardes dels dos camps de secció són independents** (`if not _iep_is_user` / `if not _iss_is_user`, no un `and` conjunt): amb la guarda tot-o-res, decidir un deixava l'altre sense raó.
- **Cap `include_*` a True amb el paràgraf corresponent buit** (`report_generator.py`). Tota la resta de condicionals de la plantilla ja es guarden sobre el propi contingut; aquests dos eren els únics amb «capçalera + variable a part».
- **El pendent es resol ABANS de `generate_sections()`.** Si ho mous després, tornen les capçaleres buides: el pas 2b activa els flags des de `report_data`, i `_build_template_context` només activa els de plantilla.
- **`site_condition_sentence(None)` i `site_condition_sentence(0.0)` HAN de diferir.** Hi ha test que ho clava. Un pendent desconegut no és un pendent de zero.
- **`automation/geocode_coordinates.py` és via B de producció**: es llegeix, mai es modifica.

## 9. Procediments

**Suite (compara per NOM, mai per recompte):**
```bash
cd /home/josep/projects/claudecode-job/clients/g3dt-prod
timeout 900 .venv/bin/python -m pytest tests -q -p no:cacheprovider > /tmp/suite.txt 2>&1; tail -2 /tmp/suite.txt
awk '/^_+ .* _+$/' /tmp/suite.txt | sed -E 's/^_+ +//; s/ +_+$//' | sort > /tmp/v1.txt
grep -v '^#' docs/wizard-headless/mesures/suite-vermells-esperats.txt | grep -v '^[[:space:]]*$' \
  | sed -E 's/^FAILED +[^:]+:://; s/::/./g' | sort > /tmp/v2.txt
comm -23 /tmp/v1.txt /tmp/v2.txt   # regressions
comm -13 /tmp/v1.txt /tmp/v2.txt   # desapareguts
```
Estat actual: **31 vermells esperats, coincidència exacta, 0 errors, 2702 passats.**

**`pytest tests`, MAI `pytest` des de l'arrel.** Des de l'arrel recull `automation/test_data_schema.py` i `templates/test_template.py` i dona **13 errors de recol·lecció preexistents** que no tenen res a veure amb res. Un agent hi va perdre temps i els va reportar com a normals.

**Servidor per a comprovacions visuals** (el del Josep al 8765 és seu i no recarrega Python: **no el matis**):
```bash
.venv/bin/python -m uvicorn web.server:app --host 127.0.0.1 --port 8768 --log-level warning
```
És `web.server:app`, **no** `web:app`.

**Injectar prefills de prova des de Playwright:** `wizardPrefills` és un `let` de nivell superior, **no** una propietat de `window`. Cal `Object.assign(wizardPrefills, {...})` amb l'identificador nu; fer-ho a `window.wizardPrefills` crea un objecte a part, els camps surten sense nota i sembla un defecte del codi.

**Línia base de M341** (per comparar abans de tocar): `docs/wizard-headless/mesures/runs/2026-09-10-m341-pujada/*/viaA/_context_usat.json`. Pendents resolts: Alcoletge 4,5 · Bell-lloc 3,3 · Linyola 0,4 · Castellar 33,6 · Rubí, Vilanova i Anciles cap.

## 10. Seqüència d'obertura suggerida

1. `git branch --show-current` a `g3dt-prod/` i comunica-ho al Josep en una línia (directiva del CLAUDE.md del projecte).
2. Comprova els quatre HEAD de §2 i que `production/g3dt-eva-v1` segueix a `123b4f2`.
3. Llegeix `STATUS.md` i l'**addenda** de la troballa (no el cos original: té el diagnòstic equivocat).
4. **Pregunta al Josep per quina de les tres feines vol començar.** Totes tres estan investigades; el que falta és la seva tria.
5. Abans de tocar codi, mesura la línia base (memòria `feedback_measure_baseline_before_coding`).
6. Segueix el bucle implementer → reviewer → tester (`~/T4/agents-teams/IMPLEMENTER-REVIEWER-TESTER-PATTERN.md`): el main orquestra i **no arregla codi ell mateix**. Aquests dos dies el bucle ha tombat tres solucions que semblaven bones i ha destapat una regressió del mateix dia.

## 11. Què NO fer

- **No proposar mai un `pull` o un `merge` a l'Eva** (memòria `feedback_no_pull_eva_success_criterion`).
- **No avançar `production/g3dt-eva-v1`** ni fer `--force`/`reset` de res pujat.
- **No matar el servidor del 8765**: és del Josep, fa dos dies que corre.
- **No treure la capa «Observacions de camp»** sense resoldre abans el comptador (§6).
- **No fer servir `window.confirm`/`alert`** a la UI: bloqueja Playwright i és lleig per a l'Eva. (Un `beforeunload` del propi formulari ja va deixar Playwright penjat una vegada: si `browser_navigate` fa timeout repetidament, és això.)
- **No fer que «vist» equivalgui a «decidit».** El botó «D'acord» l'ha de prémer l'Eva; res de marcar-ho per focus, per estar a pantalla o per un autodesat.
- **No committejar** `schemas/formats/learned/*` ni `docs/diagnostics/*` (els genera la suite).
- **No esborrar estat de proves que no hagis creat tu** (memòria `feedback_no_rm_test_state_you_did_not_create`). El projecte `9999999 PROVA-AUTH-EFICIENTS` és del Josep: pregunta abans.
- **`git checkout -- <fitxer>` per desfer una prova temporal s'endú la feina no committejada.** Fes un commit de treball abans. I **mai `git stash` pelat**: la pila és compartida entre worktrees.
- **No et refiïs dels recomptes de tests que reportin els subagents.** Aquests dos dies n'han fallat tres vegades (errors fantasma, comparacions truncades). Corre la suite tu i compara per nom.

## 12. Tasques obertes

- [ ] **Feina 1:** preguntes 17 i 40 a l'Eva (visita 26-09, sense confirmar).
- [ ] **Feina 2:** repàs d'accents, començant per quines seccions arriben al `.docx` (`STATUS.md` 0a).
- [ ] **Feina 3:** decisió 2 — els 18 camps; el botó «D'acord» ja és genèric.
- [ ] **Defecte (a):** Vilanova en català havent de ser en castellà.
- [ ] **Defecte (b):** `is_anthropized=False` conegut que es torna `None` (`wizard_service.py:369`).
- [ ] Actualitzar el clon WSL i `release/2026-09` amb `6b0a6af` i `7624629` quan el Josep ho decideixi.
- [ ] Icona «Tornar a entrar a Claude» a l'escriptori de l'Eva: únic pendent **manual** del dia de la visita (`scripts/G3DT-Tornar-a-entrar-a-Claude.bat` existeix, la lògica està verificada, el `.bat` mai s'ha executat).
- [ ] Decidir si es conserva el projecte de prova `9999999 PROVA-AUTH-EFICIENTS`.
- [ ] `docs/GUIA-EVA-WIZARD.md` desfasada (descriu la via B): substituir-la per `docs/COM-FUNCIONA-EVA-2026-09.html`.
- [ ] Defectes menors pendents: «Figura - Projecte 2» repeteix la raó de la figura 1; el comptador de la barra no baixa fins al desat.

## 13. Guanys que no surten a cap mètrica

- **Castellar també tenia les capçaleres buides**, i des de sempre. O sigui que **tot informe que hagi activat mai 4.4/4.5 ha sortit amb dos títols nus** damunt la signatura d'una col·legiada. Ningú ho havia vist perquè les mesures comparen variables, i una variable buida amb la capçalera renderitzada no la distingeix cap mètrica de les que tenim. Val la pena pensar si hi ha altres seccions que es mesuren així.
- **La capçalera «Al solar,» és de l'Eva, no una invenció nostra** — idèntica caràcter a caràcter al signat. És el defecte honest quan no sabem el pendent, i va sortir de mirar els `.docx` signats un per un en comptes de fiar-se de l'anàlisi narrativa, que no l'havia registrat.
- **La regressió de la `note` la vam introduir i la vam trobar el mateix dia.** Movent la raó del `source` (que es persisteix) a `note` (que no), la informació passava de congelada a perduda. Sense la revisió hauria arribat a l'Eva com «el sistema ha deixat d'explicar-me per què».
- **El botó «D'acord» és una peça de la decisió 2 pagada per avançat.** Es va fer genèric a posta: quan s'ataquin els 18 camps, són dues llistes i un botó per camp.
