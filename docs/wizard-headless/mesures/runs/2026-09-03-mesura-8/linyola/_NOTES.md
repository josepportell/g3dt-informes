# Linyola — mesura 2026-09-04 (codi intacte, pre P0-P4) — 4/8

- **Temps: 42,9 min** (línia base holdout-v16: **41,9** → +1,0 min, 2 %, dins del soroll; el +5,6 de Castellar era
  l'agent R en paral·lel). Run net (`setsid nohup`, PID 836005), degraded=False, 21 docs (20 crides Claude, 1 Python),
  cost 18,44 USD, **0 contaminació DNS** (20 logs per doc + stdout). Docs més lents: PENETROS 480 s, lab-sig 339 s,
  tall 309 s.
- **Escalars** (`_compare_escalars.txt`, cru): **12 OK / 7 CAUTELA / 1 ERR / 1 ALERTA / 1 NOU**.
  - **ERR `field_date`: segur `2025-10-10`, veritat `2025-10-01`** (7 fonts unànimes a l'or; fitxa F38 = 01/10).
    **Bug del consolidador (D2), no de lectura ni de font:** (1) `keys_compatible` fa compatible una data sense dia
    («Octubre 2025», plànol) amb QUALSEVOL dia del mes, i el union-find és transitiu → 01/10 (F38 A 0,95 + 6 docs) i
    10/10 (lab-sig, 0,35, etiqueta mal aparellada: és la data de sol·licitud del lab, `comanda!AH23`) cauen al
    **mateix cluster** → «1 font A sense contradicció»; (2) la clau representant del cluster es tria per
    `len(str(k))` → `('date', 2025, 10, 10)` guanya a `('date', 2025, 10, 1)` per un caràcter; (3) `_iso_date(top.key)`
    **sobreescriu** `candidates[0]["value"]` amb la ISO de la clau → el candidat conserva font F38 i cita
    `datetime(2025, 10, 1)` però diu 2025-10-10. Comentari del codi: «canonicalització de FORMAT, no de contingut» —
    aquí canvia el contingut. Vegeu `_DIAGNOSTIC.md` §D2.
  - ALERTA `street_address`: valor correcte («Clot de la Llacuna, 16»); el comparador no iguala «…, 16, Linyola
    (25240)» (el CP compta com a portal) ni «C. Clot…» (abreviatura no reconeguda). **C**.
  - 7 CAUTELA amb el bo dins: `building_type` (R1, 4/4), `architect_name` (R1 persona/despatx + «Laia Alarcón»;
    **el signat escriu el DESPATX «Bunyesc Arquitectura Eficient», l'or diu la persona** → G + pregunta a Eva),
    `cota_referencia` (R2: z GPS 244,9 bloqueja +245 de l'annex; signat +245,0), `lab_depth` (F1: DPSH.xls «1,0 a
    1,5» i PENETROS «1,00 a 1,75» vs GTL «1,0-1,15»; signat -1,00 a -1,15), `lab_location` (R1: «SPT1 P3» vs
    «P-3»), `referencia_catastral` i `superficie_parcela` (R5: una sola font, el projecte de l'arquitecte, conf < 0,8;
    signat 571 ✓).
  **Sobre el signat: 13 OK / 7 CAND / 1 ERR** (21 amb or) → OK 62 %, CAND 33 %, **ERR 1 (D2)**.
- **Taules** (`_compare_taules.txt`, cru): **16 OK / 4 CAUTELA / 4 BUIT / 1 ALERTA / 0 ERR**.
  - ALERTA `soil_levels[0].de` i CAUTELA `[0].a`/`[1].de`: prod dona el contacte en **msnm** («≈243,6 msnm a P-1»)
    i l'or/l'informe en **fondària** («~-1,4 m a P-1»): 245 − 1,4 = 243,6 → mateixos valors, sistema de referència
    diferent (R2, sistema) + el comparador no els pot igualar (C). CAND.
  - CAUTELA `litologia` «Llims argil**soso**»: **errata del tall d'Eva** (transcrita fidelment); el signat diu
    «argilosos». F1-lleu; comparador estricte (C).
  - BUIT ×4: `n30` de l'SPT (or: «R, 50 cops al primer tram»; cap lector emet n30 del full SPT manuscrit de
    PENETROS p.3 → **forat de lector L1**), `soil_levels[1].a` («fins al fons d'investigació», derivat) i
    `mostra_del_nivell` ×2 (assignació de la mostra al nivell, derivat). Blancs honestos.
  **Sobre el signat: 16 OK / 0 ERR / 4 blancs / 3 CAND.**
- **Veredicte Linyola: ERR de sistema = 1 (`field_date`, bug D2 del consolidador — el primer ERR de codi dels 4).**
