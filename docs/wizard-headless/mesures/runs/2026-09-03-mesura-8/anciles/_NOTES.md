# Anciles — mesura 2026-09-04 (codi intacte, pre P0-P4) — 7/8

- **Temps: 28,3 min**, run net (`setsid nohup`, PID 5402), sense reintents ni timeouts, degraded=False, 14 docs (14 crides
  Claude, 1 Python), cost 12,12 USD, **0 contaminació DNS** (14 logs per doc + stdout). Sense línia base. Docs més lents:
  «PENETROS + SONDEIGS.pdf» 443 s, IV_PLANOS 389 s.
- **Escalars** (`_compare_escalars.txt`, cru): **11 OK / 6 CAUTELA / 3 ALERTA / 1 BUIT / 1 NOU / 0 ERR**.
  - **BUIT `cota_referencia`** (or «+1106,40 (P-1)», signat +1106.40): **cap document llegit porta cap cota.** Causa
    **I1 (inventari):** a Anciles els annexos DPSH/sondeos només existeixen a `PDF_V0/ANEJOS/` (no hi ha `PDF/`), i la
    regla «`PDF V0` = versió anterior → `exclos_carpeta`» els salta; el `.FH11` és il·legible. L'or els va llegir
    («capçalera de cada pàgina de l'annex DPSH: +1106,40 / +1106,30 / … segons topogràfic del client»). Mateixa causa
    dels **8 BUIT de cota a les taules** (6 DPSH + 2 sondeig): **9 blancs d'una sola regla d'inventari.**
  - ALERTA `num_soil_levels` prod **segur 2** (tall, LEYENDA) = signat 2 nivells ✓ (or candidats). ALERTA `building_type`
    i `client_name`: valor bo dins (candidat 1) — el comparador no iguala «vivienda adosada (7 unitats)» amb «7
    habitatges unifamiliars adossats» (ca/es) ni «MARIA ALBA BARRAU CASTÁN 616523792» amb «Alba Maria Barrau Castán»
    (telèfon enganxat + ordre de noms) → **C**. Signat: «7 viviendas unifamiliares adosadas», «SRA. ALBA MARIA BARRAU
    CASTÁN» ✓.
  - CAUTELA «disjunts»: `architect_name` (mateixes 2 arquitectes, format diferent → C), `lab_testing_company` (prod
    «TPS, Prospecció del Subsòl, SL» ✓; l'or hi té «MA (S-2) 2,8-3,0» per candidats compartits del camp niuat `lab` →
    C), **`cte_edificacio` prod «C0» vs or «C-1»**: la derivació ha usat la superfície **d'una tipologia** (A01_TIPOL,
    186,18 m²) en lloc del **total de les 7 cases** (1.264 m² > 300 → C1). **D5.** CAND, però candidat equivocat.
  - CAUTELA bo dins: `referencia_catastral`, `street_address` («C/ General Ferraz, 20»), `superficie_parcela`
    («1.655,01 m²») — font única del projecte de l'arquitecte (R5, com Linyola/Alcoletge).
  **Sobre el signat: 12 OK / 8 CAND / 1 blanc (I1) / 0 ERR** (21 amb or) → OK 57 %, CAND 38 %, **ERR 0 ✓**.
- **Taules** (`_compare_taules.txt`, cru): **22 OK / 9 CAUTELA / 14 BUIT / 7 ABSENT / 1 ALERTA / 0 ERR**.
  - 14 BUIT = **8 de cota (I1)** + 6 de `soil_levels` de/a/mostra (coneguts, derivats). 7 ABSENT = columnes només del
    fixture (`id_estat`, `litologia_del_nivell`, `assaig_encarregat`) → C.
  - 9 CAUTELA bo dins: les 6 cel·les dels 2 sondeigs (`profunditat_assolida`, `spt_ma`, `nivell_freatic`) en candidats
    perquè l'única font és el full manuscrit «PENETROS + SONDEIGS» (conf < 0,8) → **R5**; signat S-1 −2.40 / 1/0/0 ✓,
    S-2 −3.00 / 1/0/1 ✓. `spt_ma_tests[*].profunditat` ×3 idem (signat −1.00 a −1.60 ✓, −2.80 a −3.00 ✓).
  - ALERTA `spt_ma_tests[2].n30` (MA-1): prod candidat **2**; signat «--» (una MA no té N30) → candidat espuri, **L3**.
  - `litologia` dels 2 SPT no_trobat (signat «Arcilla arenosa con gravitas»): manuscrit → blanc honest.
  **Sobre el signat: 22 OK / 0 ERR / 14 blancs (8 I1) / 10 CAND.**
- **Veredicte Anciles: ERR de sistema = 0 ✓**, però **9 blancs de cota per una regla d'inventari** (I1) — el forat de
  cobertura més gran de la mesura.
