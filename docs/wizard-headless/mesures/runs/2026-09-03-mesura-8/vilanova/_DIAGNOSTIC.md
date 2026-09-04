# Vilanova — diagnòstic de tot el que no és OK contra el signat

**Data:** 2026-09-04 · **Mètode:** JSON dels 2 runs, `_telemetry_run1.jsonl`, `_eva_truth/vilanova.json` (signat, castellà),
ors, `consolidate.py` (`value_key`, `_prefer_form`, `decide` table_cell), `municipis.lookup`. Cap re-run addicional.
Taxonomia: `../_DIAGNOSTICS-INDEX.md`.

## D3 — la forma visible del municipi es tria per longitud, no pel padró (l'ERR de `municipality`)

1. `value_key("…", field_name="municipality")` treu les stopwords → «Vilanova del Segrià», «Vilanova de Segrià»,
   «VILANOVA DE SEGRIA», «VILANOVA SEGRIÀ» donen totes `('text', 'vilanovasegria')` → un sol cluster de 15 senyals,
   cap contradicció → «1 font A sense contradicció» → **segur**. (Correcte: és el mateix municipi.)
2. `_distinct_candidates` → `ordered_forms` → `_prefer_form(s)` = `(is_a, no derivat, confidence, no MAJÚSCULES,
   has_unit, origin claude, len(v))`. Tres senyals A claude a 0,90: 1.0.pdf «Vilanova **del** Segrià», pl situació
   «Vilanova de Segrià», acceptació «Vilanova de Segria». Desempat final: **`len(v)`** → «del» (19) > «de» (18).
3. `municipis.lookup()` resol les dues formes (capes `preposicions` / `exacte`) al registre INE 25251 amb
   `name_ine = 'Vilanova de Segrià'`. El consolidador té la grafia oficial a l'abast i **no la fa servir per al valor**.

Fix (després de la mesura): per a `municipality`, si totes les formes del cluster guanyador resolen al mateix registre
del padró, el valor visible és `name_ine` (la forma del document queda a la cita). No és «treure dubte»: el dubte sobre
QUIN municipi ja no existia; és no imprimir una errata de l'arquitecte a l'informe. Mateixa família que D2: dos cops
en dos projectes el desempat per `len(str)` ha convertit una forma minoritària en «segur».

## R6 — a les taules, l'absència guanya l'evidència positiva (l'ERR de `nivell_freatic` P-3)

`decide(table_cell=True)`: «només els documents d'autoritat A de la cel·la contradiuen; la resta són corroboració».
Per a `dpsh_tests[*].nivell_freatic` els A són l'Excel DPSH i l'annex DPSH; tots dos tenen la columna N.F. **buida** →
«No detectat» (A). El tall (`corte de correlación`, síntesi d'Eva) marca **«Aigua» a P-3 (~321 msnm)** i el full de camp
(PENETROS p.2) escriu **«Humit»** a P3: tots dos a `altres`. Signat: «P-3 Humedad -1.00». Una columna buida és
absència d'anotació, no una mesura de «no»; una marca dibuixada al tall és evidència positiva. Regla candidata: a
`nivell_freatic`, un senyal positiu de qualsevol document bloqueja el «No detectat» → candidats [positiu, No detectat].
L'or ja ho feia així (tall primer).

## D4 — `degraded=False` amb 3 documents perduts

Run 1: `RE_ PRESSUPOST LLEIDA.msg`, `plano de situación.pdf` i `pl situació.pdf` fallen als 2 intents (`rc=1`, 1 torn,
cost 0: error de connexió) i la passada LLM de `street_address` també (`rc=1`). El runner consolida amb **11/14 docs**
i tanca amb `degraded=False`, `decisions=OK`. La `_decisions.json` resultant tenia forats invisibles (adreça sense
l'annex de situació). El flag només reflecteix la consolidació LLM (`merge_degradat`), no les lectures perdudes.
Fix: `degraded=True` (o un `docs_failed` explícit) quan un doc acaba sense JSON vàlid després dels reintents.

## Escalars — 10 cel·les no-OK (de 22)

| Camp | Cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `municipality` | ERR → **ERR** | Vegeu D3. | **D3** |
| `superficie_parcela` | ALERTA → **OK fora** | Cadastre portal 4 → 8606709CG9280N, **406 m²**; signat «406 según catastro». Or no_trobat (estimava ≈405-410 del plànol) sense `fora_carpeta`. | **G** |
| `referencia_catastral` | ALERTA → CAND (correcta) | 8606709CG9280N del Cadastre (conf 0,5, mai segur per disseny). Or no_trobat. | — |
| `client_name` | CAUTELA → CAND | «Grupo Cuenca Guerrero SL» / «SL.» / «Grupo CUENCA GUERRERO»: formes A. Signat «GRUPO CUENCA GUERRERO, S.L.». | **R1** |
| `street_address` | CAUTELA → CAND | «C. Santa Gemma, 4 Urb. La Serra» (caixetí) / «C/ STA. GEMMA 4, URB.LA SERRA» (G3) / «CALLE SANTA GEMMA Nº4» (annex): formes A, mateix portal 4. Signat ✓. Cadastre ✓. | **R1** |
| `building_type` | CAUTELA → CAND | Consolidat per LLM («habitatge unifamiliar aïllat (vivienda unifamiliar)»); signat «vivienda unifamiliar aislada». | — |
| `num_floors` | CAUTELA → CAND | «PB (~100 m²)» d'una sola font; signat Pb / 100 m². | R5 |
| `cte_edificacio` / `cte_sol` | CAUTELA → CAND | Pressupost imprimeix C0/T1; signat C-0/T-1. | **R4** |
| `architect_company` | NOU | Sense or. | — |

**Sobre el signat: 14 OK / 6 CAND / 1 ERR** (21 amb or).

## Taules — no-OK contra el signat

| Cel·la | Cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `dpsh_tests[P-3].nivell_freatic` | ALERTA → **ERR** | Vegeu R6. | **R6** |
| `spt_ma_tests[*].punt` ×2 | ERR → OK | Els dos SPT es diuen «SPT-1» (F1 del signat i de l'annex) → el comparador alinea per índex i creua P-1/P-3. Prod té les files (SPT1, P-1) i (SPT-1, P-3), les mateixes del signat. | **C** |
| `spt_ma_tests[*].profunditat` ×2 | ERR → OK | «0,80-1,40m» / «0.80-1,40m» (sense espais, separadors mixtos) no es parsegen; signat «-0.80 a -1.40» = mateix. | **C** |
| `spt_ma_tests[*].n30` / `.litologia` | CAUTELA → CAND (valors de l'annex ≠ signat) | Prod: P-1 → 24 (registre 13/10/14/24), sorra; P-3 → 10 (3/4/6/5), argila = **annex DPSH i tall**. Signat: P-1 → 10/argila, P-3 → 24/sorra. La transició argila→sorra del tall (−0,85 m a P-1, −2,4 m a P-3) fa coherent l'annex i incoherent la taula del signat. Candidats, mai segur → CAND. | **F1** (signat creuat) + pregunta Eva |
| `spt_ma_tests[*].id` | ALERTA → OK | «SPT1»/«SPT-1» segur = or candidats, mateix valor. | — |
| `spt_ma_tests[*].lab`, `soil_levels[*].nom` | ABSENT | Dialecte del fixture (columnes que prod no emet / `nom` pla). | C |
| `soil_levels[1].litologia` | (OK cru) → CAND | Annex «Arenas finas-medias, carbonatadas» vs signat «Areniscas, arenas, sustrato»: Eva re-redacta. | F1 |
| `soil_levels[*].de/.a/.mostra_del_nivell` | BUIT ×6 | Transició inclinada per punt (gràfica), derivats no implementats. Blancs honestos. | conegut |

**Sobre el signat: 17 OK / 1 ERR / 6 blancs / ~5 CAND.**

## Què aporta Vilanova al quadre dels 8

1. **Dos ERR de sistema nous, tots dos de política/bug del consolidador**, no de lectura: D3 (forma visible per longitud
   en lloc del padró) i R6 (absència A > evidència positiva no-A a les taules). Amb D2 (Linyola), **3 dels 4 ERR de codi
   de la mesura surten del mateix patró: un desempat mecànic (`len(str)`, «només A bloqueja») pren una decisió que el
   propi `_decisions.json` ja tenia informació per no prendre.**
2. **D4:** el runner pot tancar «OK» amb documents perduts. Un tall de xarxa ho ha fet visible; a casa d'Eva passaria
   en silenci.
3. **F1 sever al signat de Vilanova** (SPT P-1/P-3 creuats respecte de l'annex i el tall): és el cas on el sistema
   *hauria* de discrepar de l'informe signat, i on cal la pregunta a Eva abans de decidir qui té raó a la veritat.
4. **R1 (adreça i client) 6/6, R4 4/4, G (`fora_carpeta`) 3/3, C (adreces/SPT) 4 projectes seguits.**
5. Informe en castellà: la lectura no se n'ha ressentit (litologies transcrites en castellà de l'annex; el comparador
   d'or les accepta). Cal que `compare_tables_vs_eva.classify_table` reconegui capçaleres castellanes si es vol
   mesurar-hi la qualitat de l'informe generat.
