# Run parcial v1.9 — Linyola, annex DPSH imprès (2026-09-05, nit, 8; permís del Josep)

Còpia de `2026-09-03-mesura-8/linyola/` (lectures cachejades per md5, `penetros.json` ja de la v1.8) SENSE
`pdf_annexes_4001607_dpsh.json` → el runner només re-llegeix `PDF/ANNEXES/4001607_DPSH.pdf` (3 pàgines impreses).
Objectiu: validar la regla v1.9 del skill («un N30 imprès sense registre és una lectura → candidat amb nota "sense registre"»):
a la lectura 1.6 el lector va escriure la cita «SPT-1 / 1,0 a 1,5 / R» i va deixar `n30: null`. Cost de la lectura 1.6: 0,97 USD,
261 s. La cel·la de Linyola ja diu «R» pel manuscrit (v1.8): aquest run no mou el comparador; mesura el text del skill.

## Resultat (2026-09-05, nit, 8)
- 5,3 min totals; `PDF/ANNEXES/4001607_DPSH.pdf` 281 s, 16 torns, **1,09 USD**; 19 documents en cache; consolidació Python 0,05 s.
- **v1.9 ✅:** `spt_ma_tests[0].n30 = "R"`, nota «N30 imprès directament com a 'R' sense colpeig per trams — sense registre (regla
  v1.9); candidat, mai segur».
- Col·lateral: la lectura emet `soil_levels` per punt de la columna de colors «Nivells» (P-1 0,00-1,60 / 1,80-2,90; P-2 0,00-0,00 /
  0,20-2,15; P-3 0,00-1,00 / 1,20-1,75) i `mostra_del_nivell: true` al nivell 2 de P-3 («cavalca la transició», amb el tram nominal
  1,0-1,5). Consolidador ajustat (D3, D4): DECISION-LOG (nit, 8).
- Lectura copiada al run mare (`2026-09-03-mesura-8/linyola/pdf_annexes_4001607_dpsh.json`); la 1.6 a `_anterior-skill-1.6/`.
  `_decisions.json` d'aquesta carpeta és el del runner (codi ANTERIOR a l'ajust D3/D4); la mesura bona és
  `2026-09-03-mesura-8/linyola/_reconsolida-2026-09-05-v19/`.
