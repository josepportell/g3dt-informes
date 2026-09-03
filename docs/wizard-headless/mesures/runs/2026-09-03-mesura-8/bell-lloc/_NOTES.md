# Bell-lloc — mesura 2026-09-03 (codi intacte, pre P0-P4) — 2/8

- **Temps: COMPOST, no comparable.** Run 1 (20:11) **matat als 34,9 min** per causa externa (el Josep no l'ha aturat;
  probable tall de connexió) amb 16/18 docs Claude desats. Run 2 (`setsid nohup`, cache per md5) llegeix els 2 que
  faltaven (`SONDEIG.pdf` 484 s, plànol de situació 311 s) + Python + consolidació: **13,1 min**. Total 48,0 min;
  en un run net el SONDEIG s'hauria solapat amb altres docs → estimació neta ~40 min (suma de docs 78,3 min / c2).
  Bell-lloc no té línia base de temps (holdout-v16 només Castellar i Linyola). degraded=False, 19 docs (20 crides
  Claude, 1 Python), cost 19,45 USD, **0 contaminació DNS** (20 logs per doc del run + 2 stdout).
- **Escalars** (`_compare_escalars.txt`): **11 OK / 10 CAUTELA / 1 NOU / 0 ERR** (22 camps; 21 amb or).
  OK 52 % · CAND 48 % · **ERR 0 ✓**. Sota el llindar OK ≥ 80 %: el sistema **es queda en candidats amb el bo dins**
  en 10 camps on l'or és segur — inclosos camps «fàcils» (`municipality`, `field_date`, `lab_testing_company`,
  `cte_sol`, `num_soil_levels`). Patró = **infraconfiança**, no error; pendent de diagnosticar per què Bell-lloc no
  confirma (Castellar sí: 14/5). No diagnosticat avui (sessió tallada per bateria).
- **Taules** (`_compare_taules.txt`): **17 OK / 3 CAUTELA / 1 BUIT / 0 ERR**. El BUIT (`soil_levels[0].a`) i la
  CAUTELA `soil_levels[1].de` (or `-0,30 (±0,05)`/`-0,4` vs prod `0,00`) són la capa vegetal / cota d'inici del
  nivell 1 — mateix cas obert que `project_soil_levels_gold_vs_pas3b_open` (ALERTA Bell-lloc, Fix E cover row).
- **Veredicte Bell-lloc: ERR de sistema = 0 ✓** (l'objectiu que mana); OK sota llindar per infraconfiança.
- Evidència del tall: `_events_run1_matat.jsonl` (últim event t=2093,6 `lectura_doc_inici SONDEIG.pdf`) i
  `_events_run2_cache.jsonl`.
