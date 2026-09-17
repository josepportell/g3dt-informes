# L'informe de Rubí diu «solar pla» i alhora porta una secció d'estabilitat de vessant

**Trobat:** 2026-09-17, investigant quants camps arriben amb valor generat i font «automàtica»
sense que l'Eva els hagi confirmat mai.
**Gravetat:** contradicció interna en un informe que l'Eva signa. Visible per a qualsevol
enginyer que el llegeixi.

## El que hi ha al `.docx` generat avui

- **3.3.1 Hidrogeologia superficial:** «Com que es tracta d'**un solar pla**, no s'han detectat
  marques i/o indicis de processos d'erosió relacionats amb l'escolament hídric superficial…»
- **Índex, 4.5:** «**ESTABILITAT DE VESSANT**» (i 4.4 «EMPENTES DE TERRES»)

Les dues coses, al mateix document.

## Per què passa (cadena verificada)

1. Rubí no té `COORDENADES.txt` i la lectura no dona UTM. Al moment de calcular els prefills
   **no hi ha coordenades**.
2. `automation/auto_extractor.py:311` (`_phase3_slope(utm_x, utm_y, …)`) necessita les UTM per
   consultar el pendent a l'ICGC. Sense UTM, **no s'omple mai `slope_percent`**.
3. `web/wizard_service.py:558`: `slope_pct = _get_val('slope_percent')` → `None` →
   ```python
   slope_val = float(slope_pct) if slope_pct else 0.0   # ← el «no ho sé» es torna 0,0
   ```
   i `site_condition_sentence(0.0, …)` escriu la frase del **solar pla**, amb font
   `'computed (slope 0%)'`.
4. Més tard, `web/wizard_service.py:333` obté les UTM per la via de reserva dels adjacents
   (`geocode:adjacents_fallback`) — **després** que la Fase 3 hagi passat de llarg.
5. En generar, `automation/report_generator.py:1195-1205` ja té UTM, crida `get_slope()` i obté
   **21,6 %**:
   ```
   14:57:30 icgc_geology:754  Slope at (418109.66, 4595666.83): 21.6% toward W
   14:57:30 report_generator:1203  Auto-set is_sloped=True (slope=21.6% W)
   14:57:30 report_generator:1271  Auto-activated slope stability
   14:57:30 report_generator:1274  Auto-activated earth pressure
   ```
6. **Ningú recalcula `site_condition`.** La frase del «solar pla», congelada d'un 0 % que mai va
   ser cert (només era desconegut), viatja a l'informe al costat de les seccions de vessant.

## És el mateix error que hem corregit aquest matí

És exactament la forma del defecte T1 del rellotge: **un zero que vol dir «encara no ho sé»
tractat com un zero de debò.** Allà eren minuts a la pantalla; aquí és una frase dins d'un
informe signat.

## Per què no s'havia vist a Alcoletge

A Alcoletge les UTM es perdien per la coma decimal
(`TROBALLA-UTM-COMA-DECIMAL-2026-09-17.md`), o sigui que `get_slope()` no s'arribava a cridar
mai en generar. **Un defecte n'amagava l'altre:** l'informe sortia «pla» i sense seccions de
vessant, coherent però igualment basat en un pendent desconegut.

## Camins possibles (a decidir amb el Josep)

- **Que el pendent es consulti quan ja hi ha UTM**, encara que arribin per la via de reserva
  dels adjacents: avui la Fase 3 passa abans i no s'hi torna.
- **Que `site_condition` no es decideixi amb un pendent desconegut**: si no hi ha `slope_percent`,
  el camp hauria de quedar per revisar (i comptar a «Queden N camps a revisar»), no resoldre's
  com a «pla» per defecte.
- **Que el generador recalculi la frase** si acaba sabent un pendent que contradiu el que es va
  suposar, o com a mínim que avisi.
- Convé repassar si hi ha **altres frases narratives** decidides amb un valor per defecte que
  després es contradiu amb dades obtingudes més tard.

## Context de la mesura

A Rubí, dels **64 camps de cara a l'Eva**, **18 arriben amb valor generat/plantilla/per defecte**
presentat com a automàtic. Alguns són derivacions legítimes de dades reals (`num_dpsh_tests`,
`table_dpsh_range`, `num_site_photos`). Els que mereixen mirada són els que **escriuen prosa a
l'informe** (`site_condition`, `site_description`, `access_description`, `settlement_sentence`,
`access_street`, `lab_tests_text`) i els **defectes estàndard** sobre l'edifici
(`foundation_depth_m=0,3`, `has_basement=False`, `has_retaining_walls=False`,
`num_soil_levels=1`, `sulfate_level_name='1er nivell'`).
