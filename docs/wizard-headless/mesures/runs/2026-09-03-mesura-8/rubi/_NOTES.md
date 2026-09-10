# Rubí — mesura 2026-09-04 (codi intacte, pre P0-P4) — 3/8

- **Temps: 26,9 min** (sense línia base; run net, `setsid nohup`, PID 825027). degraded=False, 12 docs (13 crides
  Claude, 1 Python), cost 11,42 USD, **0 contaminació DNS** (13 logs per doc + stdout). Docs més lents: PENETROS 382 s,
  annex tall 314 s, DPSH.xls 230 s.
- **Escalars** (`_compare_escalars.txt`, cru): **10 OK / 7 CAUTELA / 4 ALERTA / 1 NOU / 0 ERR**.
  Les 4 ALERTA, contrastades amb el **signat** (`_eva_truth/rubi.json`):
  - `num_soil_levels` prod **segur 1** — el signat té 1 nivell («1er nivell. Graves i sorres, carbonatades»). L'or
    duia candidats [1, 2] per l'esborrany `F5 TALL.png` (N2). **Prod correcte i més confiat que l'or.**
  - `superficie_parcela` prod candidats **951** (Cadastre, 39 = 8259027DF1985N) — el signat diu 951. **Correcte fora
    de carpeta**; l'or no porta `fora_carpeta` → ALERTA en lloc de FORA. *Pendent: anotar-ho a l'or.*
  - `architect_name` prod candidats [client «Joana Martínez» (pràctica Eva), «Albert Coll»] vs or no_trobat. CAND.
  - `referencia_catastral` prod candidats «Polígon 6, Parcel·la 105-B» (×3 formes, identificador d'urbanització, NO
    RC de 20 caràcters — la nota del propi sistema ho diu). CAND, però **defecte D1**: la RC real (8259027DF1985N) el
    sistema la coneix (surt a la font de `superficie_parcela`) i no l'ofereix, perquè el Cadastre només es consulta
    «als forats» (`consolidate.py` ~1788) i aquí els documents omplen el forat amb un valor del tipus equivocat.
  **Sobre la veritat signada: 12 OK / 9 CAND / 0 ERR** (21 amb or) → OK 57 %, CAND 43 %, **ERR 0 ✓**.
- **Taules** (`_compare_taules.txt`, cru): **14 OK / 4 ALERTA / 3 BUIT / 2 ABSENT / 0 ERR**. Contrastat amb el signat:
  - `dpsh_tests[1].cota_inici` (**P-2**) prod **segur «+212 msnm»**; el signat diu **+212,50** als 3 punts. L'annex
    DPSH p.2 imprimeix literalment «+212 msnm» (P-1 i P-3: «+212,50») — **inconsistència interna d'Eva** (annex vs
    informe); el sistema transcriu fidelment l'annex. **Compta com a 1 ERR** per la definició pactada (decisió
    confiada ≠ veritat), causa: font d'Eva inconsistent. L'or ho tenia a candidats. Regla candidata: si el mateix
    document dona cotes d'inici diferents per punt amb superfície uniforme al tall → candidats.
  - P-1 i P-3 prod segur +212,50 = signat ✓ (l'or era candidats per l'esborrany). El «valor fora dels candidats d'or»
    de P-3 és un **fals negatiu del comparador** (`close()` text: «plànol en el ICGC» vs «plànol de l'ICGC», mateix
    número 212,50).
  - `soil_levels[2].de` prod segur «0,00» = or «0 (superfície)» ✓, més confiat.
  - 2 ABSENT = el «2on nivell» de l'esborrany, que el signat NO té → prod correcte en no crear-lo.
  - 3 BUIT = `de`/`a` del nivell 1 i `a` de la cobertura: blancs honestos (el tall és gràfic; cas obert capa vegetal).
  **Sobre la veritat signada: 17 OK / 1 ERR / 3 BUIT** — **ERR de sistema = 1** (P-2 cota, causa font).
- **Recurrència del diagnòstic de Bell-lloc:** `building_type` cau per **R1** (abreviatures G3 `CONSTR HABITATGE UNI` /
  `EG HAB UNIF RUBI`) → **3/3 projectes**; `cte_*` per **R4** (pressupost imprimeix C0/T1) → 2/3. `lab_depth`
  (comanda 1,4 vs GTL+manuscrit 1,2) i `num_floors` (1 sola font, foto WhatsApp) són CAND legítims. `street_address`
  candidats per la grafia «Moranda» de l'albarà (eix via, per disseny); el Cadastre ha resolt bé (951 ✓).
- **Comparador (D2):** `num_floors` «candidats disjunts» entre or «1 (planta baixa)» i prod «PB + porxada» (signat:
  «PB + Porxo») és un forat de `norm_floors`; i el text de P-3 de dalt.
- **Veredicte Rubí: ERR de sistema = 1 (taula, cota P-2, causa: annex d'Eva inconsistent amb el seu informe).**
