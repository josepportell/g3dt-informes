# 2026-09-06-informe-assent — peça D: assentament per CRITERI (`automation/settlement_criteria.py`)

**Què canvia respecte de `-repro`/`-p3`:** cap de les 11 taules es mou (`diff` buit a les 12 comparacions). Canvia la FRASE
d'assentament del §4 (narrativa, fora del comparador de taules; la mesura la veu M341) i la columna «imprès» / «Es» de la
taula «Càlcul» de l'`_AGREGAT.md`:

| projecte | signat | abans (2,5×Nb global desat al user_data) | ara (`calc`) | per què |
|---|---|---|---|---|
| Castellar | «<1,0» (roca) | 2,80 cm, «inferiors a 2.80 cm» | **frase genèrica ✓** | règim roca → Schmertmann no s'aplica (7/7 signats) |
| Rubí | 1,50 | 1,70 | 1,80 (Es 100 = 2,5 × N SPT 40); amb Nb 47 → 1,52 | quin N entra a l'Es: pregunta 15 |
| Bell-lloc | 1,20 | 2,10 | 1,10 (`calc`, N 58) / 1,00 (`t2`, N 62); amb N 54 → 1,16 → 1,20 | l'N de l'SPT: 54 signat / 58 tall / 62 lectura (pregunta 1) |

- La plantilla tenia la frase FIXA («seran iguals o inferiors a {{ settlement }} cm, immediats… granular»): ara imprimeix
  `{{ settlement_sentence }}` (genèrica en roca/cohesiu o < 1,0 cm; valor precís en granular).
- Variants `calc`/`t2`/`viab`: el harness treu ara també `Es_settlement` del `user_data` d'abril (era el 2,5×Nb global desat
  pel wizard: 76/104/56, no un judici de l'Eva). La `8b` el conserva (rèplica).
- Candidats d'Es (badge «+N» al wizard, camp «Es assentament»): 2,5×N SPT del nivell → 2,5×Nb del nivell → E del criteri.
