# Vilanova de Segrià — mesura 2026-09-04 (codi intacte, pre P0-P4) — 6/8

**Cas especial resolt:** avui el Josep ha trobat l'informe signat (`.docx` original de G3, en castellà) → `_eva_truth/vilanova.json`
ja NO és stub. Vilanova **entra al titular** (7 comparables). Contrast fet contra el signat.

- **Temps: COMPOST, no comparable.** Run 1 (16:36): 11 docs llegits bé en 22 min; a partir de 16:58 **tall de connexió**
  (3 docs amb `rc=1`, 1 torn, cost 0 als 2 intents; LLM de `street_address` també) i el runner va tancar a 100,3 min amb
  **11/14 docs i `degraded=False`** (→ **D4**: cap flag de degradació amb 3 docs perduts). Reinici del sistema; el log
  stdout del run 1 s'ha perdut (`/tmp`), la telemetria no (`_telemetry_run1.jsonl`). Run 2 (`setsid nohup`, cache md5):
  els 3 docs que faltaven + Python + LLM `building_type`/`street_address` = **9,5 min**, 0 DNS (4 logs + stdout).
  Estimació neta ~32 min. Cost 12,86 USD (0,42 llençats al run 1). `_decisions_run1_incomplet_11docs.json` conservat.
- **Escalars** (`_compare_escalars.txt`, cru): **12 OK / 6 CAUTELA / 1 ERR / 2 ALERTA / 1 NOU**.
  - **ERR `municipality`: segur «Vilanova del Segrià»** (or i signat: «Vilanova de Segrià»). 15 senyals, tots al mateix
    cluster (`value_key` treu «de/del» → `vilanovasegria`), sense contradicció; la **forma visible** la tria
    `_prefer_form` (A, conf 0,9 empatada entre 3 fonts claude, …, **`len(v)`**) → «del» (19 car.) guanya a «de» (18).
    El padró resol les dues formes al mateix registre amb `name_ine='Vilanova de Segrià'` i el consolidador **no usa la
    grafia oficial**. **Bug D3** (mateixa família que D2: «el més llarg guanya»). ERR de sistema.
  - ALERTA `superficie_parcela` **406** i `referencia_catastral` 8606709CG9280N (Cadastre, portal 4): el signat diu
    **406 «según catastro»** → correcte fora de carpeta; l'or no ho tenia (estimava ≈405-410 del plànol) → **G**.
  - 6 CAUTELA amb el bo dins: `client_name` (R1: «SL»/«SL.»/«Grupo CUENCA GUERRERO»), `street_address` (R1 formes:
    «C. Santa Gemma, 4 Urb. La Serra» / «C/ STA. GEMMA 4, URB.LA SERRA» / «CALLE SANTA GEMMA Nº4»; signat «Calle STA.
    GEMMA nº 4, URB. LA SERRA» ✓, Cadastre resolt ✓), `building_type` (consolidat per LLM, «habitatge unifamiliar aïllat
    (vivienda unifamiliar)» ✓), `num_floors` («PB (~100 m²)» ✓ signat Pb/100), `cte_*` ×2 (R4; signat C-0/T-1 ✓).
  **Sobre el signat: 14 OK / 6 CAND / 1 ERR** (21 amb or) → OK 67 %, CAND 29 %, **ERR 1 (D3)**.
- **Taules** (`_compare_taules.txt`, cru): 14 OK / 3 ALERTA / 4 ERR / 3 CAUTELA / 4 ABSENT / 6 BUIT. Sobre el signat:
  - **ERR real: `dpsh_tests[P-3].nivell_freatic` segur «No detectat»**; signat «Humedad (m): -1.00» a P-3. Les fonts A
    de la cel·la (Excel DPSH columna buida, annex DPSH p.3) diuen «no»; el **tall** marca «Aigua» a P-3 (~321 msnm) i el
    **full de camp** «Humit» a P3 — tots dos a `altres`, perquè a les cel·les de taula només bloquegen els docs A (Pas 3b).
    **R6 (nou):** l'absència (columna buida) guanya a l'evidència positiva d'un document no-A. L'or ho tenia a candidats
    (tall primer). ERR de sistema. (Alcoletge va bé perquè la humitat era a l'Excel, cel·les blaves.)
  - Els 4 «ERR» crus de `spt_ma_tests` són del **comparador (C)**: els 2 SPT es diuen tots dos «SPT-1» (F1 del signat)
    → alineació creuada per índex (`punt` P-1↔P-3); i `profunditat` «0,80-1,40m» (sense espais) no es parseja.
  - **F1 gros:** prod (= annex + tall) diu SPT P-1 → N30 **24**, sorra; P-3 → N30 **10**, argila. El **signat** diu P-1 →
    10/argila, P-3 → 24/sorra: **creuat**. El tall dona la transició argila/sorra a −0,85 m (P-1) i −2,4 m (P-3): la
    mostra 0,8-1,4 és sorra a P-1 i argila a P-3 → **l'annex i el tall són coherents, la taula del signat no.**
    `n30`/`litologia` són candidats (mai segur) → CAND vs signat, però **pregunta a Eva** obligada.
  - 2 ALERTA `id` («SPT1»/«SPT-1» segur vs or candidats): mateix valor. `lab` ABSENT ×2 i `nom` ABSENT ×2: dialecte
    del fixture (C). BUIT ×6: `de`/`a`/`mostra_del_nivell` (transició inclinada, gràfica) — blancs honestos coneguts.
  - `soil_levels` litologies en castellà de l'annex («Arenas finas-medias, carbonatadas») vs signat «Areniscas, arenas,
    sustrato» → F1 (Eva re-redacta); N1 idèntic.
  **Sobre el signat: 17 OK / 1 ERR (R6) / 6 blancs / ~5 CAND.**
- **Veredicte Vilanova: ERR de sistema = 2** (`municipality` D3; `nivell_freatic` P-3 R6). Primer projecte amb 2.
