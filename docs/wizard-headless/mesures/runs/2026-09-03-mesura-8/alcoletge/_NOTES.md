# Alcoletge — mesura 2026-09-04 (codi intacte, pre P0-P4) — 5/8

- **Temps: 41,0 min**, dels quals **10,0 min són un timeout**: `PENETROS.pdf` intent 1 mor als 600 s
  (`G3DT_LECTURA_TIMEOUT`) **sense cap stdout** (el CLI no ha tret res en 10 min: penjada, no lentitud); intent 2
  OK en 511 s / 42 torns. Temps net estimat ~31 min. Sense línia base. Run net (`setsid nohup`, PID 850356),
  degraded=False, 15 docs (15 crides Claude, 1 Python), cost 12,64 USD, **0 contaminació DNS**. PENETROS és el doc
  més lent a 4/5 projectes (382-511 s): el topall de 600 s hi queda a tocar → **T1** a l'índex.
- **Escalars** (`_compare_escalars.txt`, cru): **14 OK / 5 CAUTELA / 1 «ERR» / 1 ALERTA / 1 NOU**.
  - **L'«ERR» de `street_address` és del comparador, no del sistema.** Or «Carrer Girasols, 7 (Urb. El Roser)», prod
    segur «Carrer Girasols, Nº7, Urbanització el Roser»: mateixa via, mateix portal 7, mateixa urbanització.
    `parse_address` posa «urbanitzacio roser» dins dels tokens de la via (prod) i no a l'or (parèntesi) → vies
    «diferents». Prova externa: el Cadastre ha resolt aquesta adreça a 8841701CG0184S, **1167 m² = el signat**.
    Codi **C** (via + sufix d'urbanització). Cal arreglar el comparador abans d'agregar.
  - ALERTA `superficie_parcela`: prod **1167** (Cadastre) = signat 1167. Correcte fora de carpeta; l'or no porta
    `fora_carpeta` (com Rubí) → **G**.
  - 5 CAUTELA amb el bo dins: `building_type` (R1: 3 redaccions del títol + `CONSTR HA…` G3), `cota_referencia`
    (R2: la z GPS **198,9** bloqueja +188,20 — aquí el GPS està 10,7 m malament; signat +188,20), `cte_*` ×2 (R4),
    `referencia_catastral` (R5: correu del tècnic, font única; el Cadastre n'ha calculat la mateixa RC de 14 caràcters
    per a la superfície i no s'ha creuat → cara inversa de D1).
  **Sobre el signat: 16 OK / 5 CAND / 0 ERR** (21 amb or) → OK 76 %, CAND 24 %, **ERR 0 ✓**.
- **Taules** (`_compare_taules.txt`, cru): **16 OK / 6 CAUTELA / 3 BUIT / 0 ERR**.
  - `nivell_freatic` ×3 «disjunts»: prod «Humitat … primera aparició **-1,00 m**; abast pintat fins a -1,40» vs or
    «-1,00 m (humitat)»; signat «Humitat (m): -1.00» ×3. **Mateix contingut**, el comparador no iguala el text llarg
    (C). Els candidats alternatius en msnm són R2 (sistema).
  - `soil_levels[0].a` / `[1].de`: contactes en **msnm** (≈186,8-187,0) vs or en fondària (-1,4 / -1,2): 188,2 − 1,4 =
    186,8 ✓. **R2 (sistema), 2/2 projectes amb escala msnm al tall** (Linyola igual).
  - `spt_ma_tests[0].litologia`: prod «[primera paraula il·legible] marró» (full manuscrit); or «Lutites (Nivell 2)»;
    signat «Llims compactes, lutites alterades». Lector honest davant d'un manuscrit il·legible → **L2**.
  - BUIT ×3: `soil_levels[0].de` (or «0,00 m»: el nivell 1 arrenca a superfície quan no hi ha cobertura — regla
    derivable no implementada; a Rubí la cobertura sí que rep 0,00), `mostra_del_nivell` ×2 (derivat). Blancs honestos.
  **Sobre el signat: 16 OK / 0 ERR / 3 blancs / 6 CAND (5 amb contingut correcte).**
- **Veredicte Alcoletge: ERR de sistema = 0 ✓** (l'ERR cru és del comparador, demostrat pel Cadastre = signat).
