# FOR NEW YOU — 2026-09-06 — Bloc 1 (lectura i decisió): 1.1 R5, 1.2 R2, 1.3 F1 fets; llindars assolits; següent 1.4 derivats

**Escrit:** 2026-09-05 (nit). Per a la sessió següent. Substitueix `_FOR-NEW-YOU-20260905.md` com a punt d'entrada;
conserva'l: hi ha les **Decisions del Josep al tancament** (ordre de blocs) i les seves quatre actualitzacions de nit.
Branca `experiment/nivell-a-2026-08`, in-place a `g3dt-prod/` (estat esperat). **Tot commitejat**, no pushat:
`4001dde` (R5), `6fb47c6` (R2), `f678508` (F1 + data doble). `git status` net abans de començar.

**En una frase:** tres peces del bloc 1 fetes amb el mètode «test + reconsolidació dels 7 a cost 0 + llista de totes
les cel·les que canvien»; escalars sobre l'or **118 OK (80 %) / 23 CAND (16 %) / 5 ALERTA / 1 blanc / 0 ERR** (els tres
llindars pactats, per primer cop; el 05 al matí era 86/46/11/1/3); taules **139 / 21 / 6 / 31 / 0**; **0 ERR sobre el
signat** també a taules. Queda la peça 1.4 (derivats: la majoria dels 31 blancs de taula), després 1.5, 1.6, 1.7.

## Actualització (2026-09-05, nit, 8) — v1.9 validada; referència nova `_reconsolida-2026-09-05-v19`

- Annex DPSH de Linyola re-llegit amb el skill v1.9 (`runs/2026-09-05-v19-linyola-dpsh/`, 1,09 USD): `n30: "R"` imprès amb la
  nota «sense registre». Lectura copiada al run mare; la 1.6 a `…/_anterior-skill-1.6/`.
- El lector 1.9 emet `soil_levels` PER PUNT de la columna de colors «Nivells» de l'annex DPSH (6 files amb `punt`). Legítim (or
  d'Alcoletge des de l'Excel). Ha destapat dues febleses dels derivats, arreglades amb test: D3 «bases llegides = rebuigs →
  el fons primer» i D4 «afirmació d'un document no-A contradita per la geometria → derivat afegit». 3 cel·les de valor, 0 de
  veredicte (taules 144/28/6/19/0). Peça futura possible: la banda de color com a font explícita de la transició per punt.
- **Per a la propera reconsolidació, compara amb `_reconsolida-2026-09-05-v19`** (no l1). Cost de la nit: 2,72 USD.

## Actualització (2026-09-05, nit, 6) — Peça 1.5 FETA (L1 re-llegit amb permís del Josep); següent 1.6 T2

- **L1 fet:** run parcial `runs/2026-09-05-l1-linyola/` (1 document, 1,63 USD, 463 s). El lector 1.8 emet la fila SPT però
  amb `value_candidates` (clau nova) i `registre` [50, null, null, null]: el consolidador ara accepta els alies i deriva «R»
  quan un tram té ≥ 50 cops (`_cell_signals`, branca n30; `test_L1_*`). Lectura nova copiada al run mare
  (`linyola/penetros.json`, skill 1.8); la 1.6 a `…/_anterior-skill-1.6/`. **Referència nova per a la propera
  reconsolidació: `{slug}/_reconsolida-2026-09-05-l1/`.** Taules 144/28/6/19/0; escalars idèntics; conflictes idèntics.
- **Esmena (nit, 7), pregunta del Josep:** la «R» NO s'infereix: era impresa a l'annex DPSH p.3 («SPT-1 / 1,0 a 1,5 / R», el
  lector 1.6 la va deixar a la cita amb `n30: null` per «sempre registre»), al tall («N=R» al contacte, només a notes) i al
  manuscrit («50»). Skill **v1.9**: un N30 imprès sense registre s'escriu com a candidat «sense registre». DECISION-LOG (nit, 7).
- Lliçó: el lector és un productor cec també a `n30`; si estrena una altra clau, la cel·la tornarà a quedar en blanc
  (limitació apuntada al DECISION-LOG nit 6: estendre el rastre de dialectes de `notes_estructurals` a `n30`).
- Queden 19 blancs de taula: 8 cotes d'Anciles (I1, carpeta `runs/2026-09-05-i1-anciles/`) + 11 lectures gràfiques del tall.
- **Sense commit** (cap de les peces 1.4, 1.5). El Josep decideix quan.

## Actualització (2026-09-05, nit, 5) — Peça 1.5 a mig fer: L3 FET, L1 preparat (pendent del Josep)

- **L3 fet, cost 0:** `_strip_phone_tail` (telèfon darrere del nom → nota) i `_ma_sample_has_no_n30` (MA → `n30` no_trobat,
  colpeig al `registre`, lectura a `altres`; només si totes les etiquetes són MA — Castellar SPT-1/MA1 intacte). Referència
  per a la propera reconsolidació: **`{slug}/_reconsolida-2026-09-05-l3/`**. Taules 144/27/6/20/0; escalars idèntics.
- **L1 preparat, NO llançat:** skill v1.8 (el full d'assaig SPT p.3 del manuscrit emet sempre la fila amb `registre`);
  carpeta `docs/wizard-headless/mesures/runs/2026-09-05-l1-linyola/` = run mare de Linyola sense `penetros.json` → el runner
  només re-llegirà `PENETROS.pdf`. Comanda a la seva `_NOTES.md`. Cost ≈ 2 USD (al run mare 2,07 USD, 480 s), quota de la
  subscripció (`login`), no crèdits. Després: comparar `spt_ma_tests[0].n30` amb l'or («R»), copiar `penetros.json` al run
  mare si és bo, reconsolidar. Si el lector torna a no emetre la fila: `--only` sobre la p.3 o fallback (DECISION-LOG nit 5).
- Cost per document (Sonnet 5, xhigh): correu 0,6-0,7 · PDF senzill 0,8-0,9 · annex de diverses pàgines 1,2-1,5 · manuscrit
  PENETROS 1,5-2,1. Projecte sencer ≈ 18 USD; els 7 ≈ 125 USD.

## Actualització (2026-09-05, nit, 4) — Peça 1.4 FETA; següent 1.5

**Fet:** `_derive_soil_levels` a `consolidate.py` (post-procés rere `_depths_from_msnm`), 5 regles: D1 primer nivell a 0,00
per definició (segur, com E2b; també puja a segur un 0,00 llegit), D2 sostre = base de l'anterior (0 cel·les al corpus),
D3 base de l'últim nivell = fons d'investigació (omple; afegeix si el reconeixement passa de la base llegida), D4
`mostra_del_nivell` per interval al punt de la mostra (a cavall → dos candidats), D5 litologia del nivell a la mostra.
Referència nova per a la propera reconsolidació: **`{slug}/_reconsolida-2026-09-05-d14/`** (no `-06-d`: era dia 5).
Taules **143 / 27 / 7 / 20 / 0** (f1: 139/21/6/31/0); escalars idèntics. Tests `test_D14_*` ×6; consolidador 156.
DECISION-LOG (nit, 4); `_AGREGAT-8.md` §nit 4. **Sense commit.**

**Què queda de 1.4 A POSTA i per què no tornar-hi:**
- **11 blancs de lectura gràfica** (Vilanova `[0].a`/`[1].de` + 2 `mostra`, Anciles `[0].a`/`[1].de` + 2 `mostra`, Rubí
  franja superficial ×2, Bell-lloc base de la cobertura): cap número al `_decisions.json`; només un skill que llegeixi el
  tall calibrat els omple (candidat a 1.5 L3). Els 9 restants són I1 (8 cotes d'Anciles) i L1 (`n30` Linyola).
- **Alcoletge `soil_levels[1].a` = ALERTA formal:** l'or el té `no_trobat` («potència no determinada per cap document»),
  els altres 4 ors (Linyola segur, Vilanova/Rubí/Anciles candidats) i el signat (0,29* → −1,69) diuen «fins al fons».
  **No s'ha tocat l'or ni s'ha posat cap excepció al codi.** Decisió del Josep: alinear l'or d'Alcoletge o acceptar l'ALERTA.
- **Linyola `mostra_del_nivell`:** l'interval (1,0-1,15 dins del nivell 1 a P-3) i el material (lutita = nivell 2) es
  contradiuen; el derivat és per interval i queda en candidats. «Material vs interval» és feina futura (comparar litologies).
- El test R2 de msnm té 1 assert canviat (D1): no és una regressió de R2.

## Ordre de lectura (15 min)

1. Aquest document.
2. `STATUS.md` (capçalera «nit, 3»).
3. `docs/_FOR-NEW-YOU-20260905.md` §«Decisions del Josep al tancament» (taula del bloc 1, peces 1.4-1.7) i les
   tres §«Actualització (nit…)» — què queda de cada peça A POSTA i per què no tornar-hi.
4. `docs/DECISION-LOG.md`, tres entrades 2026-09-05 (nit), (nit, 2), (nit, 3): regles, alternatives rebutjades, marxes
   enrere en calent.
5. `docs/wizard-headless/mesures/runs/2026-09-03-mesura-8/_AGREGAT-8.md` §nit, §nit 2, §nit 3 (taules de cel·les
   mogudes) i `_DIAGNOSTICS-INDEX.md` §Estat dels fixes — nit.
6. Per a 1.4: `linyola/_DIAGNOSTIC.md` fila `soil_levels` i `L2`, `anciles/_DIAGNOSTIC.md` (mostra del nivell),
   `docs/golden-read-taules/{projecte}/_tables_decisions.json` (les regles de l'or, camp `rule`, dialecte
   `candidats`/`valor`).

## Estat exacte: què és cada cosa

- **Referència per a la propera reconsolidació:** `{slug}/_reconsolida-2026-09-05-f1/` (7 projectes). Cadena:
  `_reconsolida-2026-09-05` (matí) → `-r6` → `-r1` → `-r2` (D5, tarda) → `-r5` (R5) → `-vei` (R2) → `-f1` (F1).
- **Regles noves al consolidador** (`automation/lectura/consolidate.py`, 2578 línies):
  - `_FIELD_AUTHORITY` (l. ~102, R5): autoritat de camp = `context.authority_for` del lector + conf ≥ 0,5 + tipus de
    document que el skill reconeix (RC/superfície/plantes: correu, projecte, plànol; nivells: tall + annex, 2 tipus;
    client: formulari p.5 per `_P5_FORM_RE`). `Signal.declares`. Guards `cadastre` (`_RC_RE`, forma completa) i
    `parcela` (`_rc_parcels`, 14 caràcters).
  - `_FIELD_PRECEDENCE` (l. ~125, R2 + F1): nivells de «qui mana»; un clúster només contradiu si mana igual o més.
    `cota_referencia`: annexos; `lab_depth`: GTL > annex sondeig > comanda. `_precedence_tier`.
  - `field_date` (R2): `_is_other_field_day` → altre dia de camp = candidat anotat + `extra.dies_de_camp`.
  - Post-processos a `consolidate_python` després de `consolidate_tables`: `_cota_relative_system` (Castellar: annex
    DPSH relatiu → cota en candidats) i `_depths_from_msnm` (msnm → fondària amb la cota segura, un candidat per punt).
  - `_dpsh_cota_header_coherence` (F1, dins `consolidate_tables`, bloc `dpsh_tests`): capçalera sense decimals entre
    germanes amb decimals → candidats, coherent primer.
- **Data doble (decisió Josep, nit):** plantilla `templates/g3dt-jinja-template.docx` amb `{{ data_camp_inici_text }}`
  a la 1a ranura («El dia …, es va visitar l'obra») i `{{ data_camp_text }}` a la 2a («…s'ha realitzat el dia 1 i 6
  d'octubre»); `dpsh_extractor.first_field_day_text`; `report_generator._build_template_context`;
  `web/lectura_service._overlay_field_dates` (lectura segura → `field_work_dates` + frase; Eva mana). Render comprovat.
- **Skill** `.claude/commands/g3dt-llegir-projecte.md` v1.7: la RC completa declarada pel proveïdor és segura (Pas 3).
  La cache de lectures va per md5 del document: editar el skill no invalida res.
- **Tests:** consolidador 150 verds; `tests/test_field_dates_text.py` nou; suite 31 vermells / 2080 verds. Els 31
  noms són a `docs/wizard-headless/mesures/suite-vermells-esperats.txt`: **diffa per nom**, mai per recompte.

## Peça 1.4 — derivats del consolidador (la següent)

**Els 31 blancs de taula (f1), per cel·la:** `soil_levels[*].mostra_del_nivell` 8 · `soil_levels[*].a` 8 ·
`soil_levels[*].de` 6 · `dpsh_tests[*].cota_inici` 6 i `sondeig_tests[*].cota` 2 (tots d'Anciles: són I1, NO derivats;
vegeu trampa) · `spt_ma_tests[0].n30` 1 (Linyola, L1, peça 1.5). Per projecte: Anciles 14, Vilanova 6, Linyola 4,
Rubí 3, Alcoletge 3, Bell-lloc 1, Castellar 0.

**Regles de l'or que cal codificar (cita el camp `rule` de `_tables_decisions.json`):**
1. **`a` de l'ÚLTIM nivell = «fins al fons d'investigació»** (rebuig DPSH per punt / fondària del sondeig). L'or:
   Linyola `segur "fins al fons d'investigació (rebuig DPSH: -2,90/-2,15/-1,75 m per punt)"`; Vilanova `candidats`.
   Font: `dpsh_tests[*].profunditat_assolida` (ja al mateix `_decisions.json`) i `sondeig_tests[*].profunditat_assolida`.
   Avui el codi ja fa una cosa a prop: `consolidate_tables` l. ~1836 posa la `a` de l'últim nivell en candidats si era
   segura (Pas 3b) — cal OMPLIR-la quan és `no_trobat`, no només demotar-la.
2. **`de` del nivell N = `a` del nivell N−1** (Linyola `[1].de` diu literalment «mateix contacte que 'a' del Nivell 1»;
   Vilanova «la mateixa transició inclinada»). Amb R2 la `a` ja és per punt en fondària: copia els candidats amb font
   «(derivat: mateix contacte que 'a' del nivell N−1) ← …». **`de` del nivell 1 = 0,00 (o base de la cobertura)**:
   precedent E2b a l. ~1845 (`cover_de = "0,00" per definició`); Alcoletge/Vilanova or `segur "0,00 m (cota …)"`.
   Pregunta 3 a l'Eva (base de la capa vegetal) continua oberta: si hi ha cobertura amb `a`, el `de` del nivell 1 és
   aquesta `a`; si no, 0,00.
3. **`mostra_del_nivell` = el nivell que conté `lab_depth`** (fondària de la mostra, ja segura a `fields.lab_depth`
   després de F1) dins de [`de`, `a`] del nivell. L'or el posa `candidats` quan l'interval cau a cavall («possible»,
   «probable», «No (la mostra s'assigna al 2on nivell pel material)») i `segur` True/False quan és clar (Vilanova).
   Els documents no-A no afirmen `False` (`_cell_signals`: «'false' d'un document no-autoritat = no ho sé») — el derivat
   sí que pot dir False amb la font «(derivat: interval fora del nivell)».
4. **Litologia del nivell de la mostra** (`spt_ma_tests[*].litologia` = litologia del `soil_levels` que conté
   `profunditat`): l'or la té sempre `candidats` (l'Eva re-redacta); `_NEVER_SEGUR_CELLS` ja ho garanteix.

**On:** tot a `consolidate_tables` (l. 1752-1900) com a post-procés del bloc `soil_levels` (després de `_depths_from_msnm`,
perquè necessita les `a` en fondària: o bé mou la derivació a `consolidate_python` després dels dos post-processos
existents, que és el lloc natural: `_cota_relative_system` → `_depths_from_msnm` → `_derive_soil_levels`).
Fonts de derivació: sempre `font` que comença per `(derivat: …) ← ` i `note` amb la regla; **mai `segur` per a un derivat
llevat de les definicions geomètriques** (0,00 de la superfície, precedent E2b) — la resta candidats. Docstring del
mòdul, garantia 2.

**Comparador i per punt:** les `a`/`de` per punt («≈-1,4 m a P-1 (contacte ≈243,6 msnm)») igualen l'or de Linyola
(per punt) però no el d'Alcoletge (agrupat: «-1,4 m (P-1 i P-3) / -1,2 m (P-2)»): `parse_numbers` compara tuples de
nombres amb els «P-1» dins. És una limitació del comparador (C) apuntada al DECISION-LOG (nit, 2); no la «resolguis»
canviant el format dels derivats per igualar un or concret. Si toques el comparador, que sigui per treure les etiquetes
de punt del parseig (defecte real), amb test, i regenera els `_compare_*.txt` sobre els `_decisions.json` de f1 per
aïllar l'efecte (mateix mètode que el v4 del matí del 05).

**Estimació:** +6-8 blancs → OK/CAND (Linyola 3, Vilanova 4-5, Alcoletge 1-2, Rubí 1-2); Anciles no baixa dels 14 sense
copiar-hi la reconsolidació d'I1 (vegeu trampes).

## Regles d'interpretació (no òbvies)

- **El comparador mesura contra l'or de lectura, no contra el signat.** ALERTA = prod més confiat que l'or; dels 6
  ALERTA de taules que queden, tots són OK per veritat (Rubí cota P-1/P-3, Rubí `soil_levels[2].de`, Vilanova `id` ×2)
  o CAND (Anciles `n30`). Dels 5 ALERTA escalars, 5 CAND (persona/despatx, RC de Rubí «Polígon», …). Llegeix-los a mà
  una vegada més quan els toquis; no els comptis com a errors.
- **CAND «disjunts» amb contingut bo existeix:** Alcoletge `soil_levels[0].a`/`[1].de` (−1,4/−1,2 = or), Linyola
  `[1].de`. No són lectura dolenta.
- **Els llindars s'han assolit sobre l'or, escalars.** Taules: OK 71 %, amb 31 blancs. El següent salt és 1.4.
- **`authority_for` mana:** si el lector no llista el camp, no hi ha autoritat de camp encara que el tipus de document
  sigui el bo (R5, per disseny). No abaixis `FIELD_AUTHORITY_CONF` (0,5) a 0,3: Rubí `num_floors` (foto de catàleg,
  or candidats) pujaria a segur; Castellar/Vilanova `num_floors` queden CAND a posta.
- **`field_date` = primer dia.** El Josep vol «1 i 6 d'octubre» a l'INFORME, a la 2a ranura, i ja hi és pel generador;
  no canviïs el valor del camp.

## Trampes

- **Anciles té dues carpetes de run:** `runs/2026-09-03-mesura-8/anciles/` (sense les 5 lectures de `PDF_V0`) i
  `runs/2026-09-05-i1-anciles/` (amb elles, on les 8 cotes són candidats). `reconsolida_mesura.py` només mira la
  primera: els 8 blancs de cota d'Anciles a f1 són I1, no 1.4. Si vols l'agregat «amb I1», reconsolida també la carpeta
  i1 (l'script `measure_i1.py` del 05 tarda no és versionat; refés-lo en 20 línies a partir de `reconsolida_mesura.py`).
- **El `cd` dins d'una comanda Bash canvia el cwd de tota la sessió** (ha passat tres cops): fes `cd "$R" && …` amb
  `R=/home/josep/projects/claudecode-job/clients/g3dt-prod` a cada comanda que en necessiti.
- **La suite regenera `docs/diagnostics/ai_pipeline_demo-project_20260905.md`** (només el timestamp): `git checkout --`
  del fitxer després de córrer-la; no el commitegis.
- **`rtk` retalla sortides llargues** (`+N more in …log`): per a llistes completes (FAILED, diff) redirigeix a fitxer i
  llegeix-lo.
- **Els `_decisions.json` de l'or usen `decisions`/`status`; els de taules `candidats`/`valor`.** El comparador ja ho sap
  (`flat_gold_scalars`, `cand_values`); si hi llegeixes directament, no busquis `fields`/`estat`.
- **`git stash` compartit entre worktrees:** mai `git stash` pelat (commit WIP en lloc seu).

## Procediments

```bash
R=/home/josep/projects/claudecode-job/clients/g3dt-prod; cd "$R"
git branch --show-current            # experiment/nivell-a-2026-08 (in-place a g3dt-prod: esperat)
# tests del consolidador (4 s) i dels mòduls tocats avui
PYTHONPATH=$PWD .venv/bin/python -m pytest tests/test_lectura_consolidate.py tests/test_lectura_service.py tests/test_field_dates_text.py -q --no-header -p no:cacheprovider
# reconsolidació dels 7 a cost 0 (nou vs referència), llista TOTES les cel·les que canvien
PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache .venv/bin/python docs/wizard-headless/mesures/reconsolida_mesura.py _reconsolida-2026-09-06-d _reconsolida-2026-09-05-f1
# agregat mecànic + diff de veredictes + conflictes
PYTHONPATH=$PWD .venv/bin/python docs/wizard-headless/mesures/agrega_mesura.py --sub _reconsolida-2026-09-06-d
M=docs/wizard-headless/mesures/runs/2026-09-03-mesura-8; for s in castellar bell-lloc rubi linyola alcoletge vilanova anciles; do for k in escalars taules; do diff <(grep -v '^TOTALS' $M/$s/_reconsolida-2026-09-05-f1/_compare_$k.txt) <(grep -v '^TOTALS' $M/$s/_reconsolida-2026-09-06-d/_compare_$k.txt) | grep '^[<>]' | sed "s/^/$s $k: /"; done; done
grep -o '[0-9]* conflictes A-vs-A' $M/*/_reconsolida-2026-09-06-d/_decisions.json   # ha de ser idèntic a f1
# suite sencera (5 min) a fitxer, i diff de NOMS vermells
PYTHONPATH=$PWD .venv/bin/python -m pytest tests -q --no-header -p no:cacheprovider > /tmp/suite.txt 2>&1; diff <(grep '^FAILED' /tmp/suite.txt | sed 's/ - .*//' | sort) <(grep -v '^#' docs/wizard-headless/mesures/suite-vermells-esperats.txt)
git checkout -- docs/diagnostics/ai_pipeline_demo-project_20260905.md
```

Dades dels projectes: `~/g3dt-e2e/projectes/<NNNNNNN NOM>/` (signats: `<exp>_informe.docx`). Cache HTTP:
`/home/josep/g3dt-prod-cache` (no la netegis: la reconsolidació és a cost 0 gràcies a ella). Cap crida LLM en tot el
mètode; si una peça necessita re-llegir documents (1.5 L1/L3 toca el skill), és un run parcial real (5-6 USD, 20 min per
5 PDF, com I1) i cal dir-ho abans.

## Seqüència d'obertura suggerida

1. `git status` net + branca. Llegeix aquest doc i les tres entrades del DECISION-LOG (nit).
2. Reprodueix la línia base: agregat de `_reconsolida-2026-09-05-f1` = 118/23/5/1/0 i 139/21/6/31/0. Si no coincideix,
   atura't: alguna cosa ha canviat sota els peus.
3. Llista els 31 BUIT (`grep -h '^BUIT' $M/*/_reconsolida-2026-09-05-f1/_compare_taules.txt`) i, per a cada regla de
   1.4, quines cel·les toca i què diu l'or (`rule`). Escriu-ho abans de codificar.
4. Codifica les regles 1-3 en un post-procés `_derive_soil_levels(fields, tables)` a `consolidate_python`, una regla
   per test (`test_D14_*` o `test_DERIV_*`), fonts `(derivat: …) ← …`, mai segur llevat de 0,00.
5. Reconsolida, llista TOTES les cel·les que canvien, contrasta cada una amb l'or i, si l'or és cautelós, amb el signat.
   Qualsevol cel·la que empitjori és una marxa enrere, no una excepció.
6. Docs amb el mateix patró (DECISION-LOG entrada nova, `_AGREGAT-8.md` §, `_DIAGNOSTICS-INDEX.md` fila, STATUS, PLA
   fila 0b, sessió del dia, handoff). Suite a fitxer, diff de noms. Commit només si el Josep ho diu.

## Què NO fer

- No afegir al comparador regles que perdonin el que ha de mesurar (litologies ca/es, partícules): la primera versió
  del v4 va amagar D3. Un defecte de parseig (etiquetes de punt) sí que és arreglable, amb test i aïllant l'efecte.
- No re-run de lectures per mesurar un canvi del consolidador: reconsolida.
- No proposar mai pull/merge a l'Eva (memòria `feedback_no_pull_eva_success_criterion`). Via B intacta.
- No tocar `geocode_coordinates.py` (via B de producció).
- No omplir un derivat sense font: garantia 2 del docstring de `consolidate.py`.
- No parlar en codis al Josep («D2», «R5»): tradueix cada codi a què passa, on, què costa; dona rutes absolutes.

## Pendent fora de 1.4

- Preguntes a l'Eva: `docs/PREGUNTES-EVA-PENDENTS.md` (12 files; les 11 i 12 són d'avui: cota P-2 de Rubí, mostra
  MA-1/SPT-1 de Castellar) + les del handoff del 05 (T del pressupost R4, persona/despatx, SPT Vilanova, E, N20).
- 1.5 L1/L3 (skill + re-lectura parcial), 1.6 T2 (decidir si la passada LLM es manté: 200-290 s per passada),
  1.7 R4 + persona/despatx (amb l'Eva). Després bloc 2 (P0, P2a, P2b, M341) i bloc 3 (S1 multi-casa).
- **Dos pendents de revisió anotats (Josep, nit 4), detall complet a `STATUS.md` §«Pendents de revisió»:** (1) or d'Alcoletge
  `soil_levels[1].a` `no_trobat` vs «fins al fons» dels altres 4 ors i del signat (1 ALERTA formal; alinear l'or o acceptar-la);
  (2) Linyola `mostra_del_nivell`: interval → nivell 1, Eva → nivell 2 pel material (prod candidats en ordre contrari;
  «material vs interval» pendent; pregunta 13 a l'Eva).
- Commits fets, cap push. El Josep decideix quan.
