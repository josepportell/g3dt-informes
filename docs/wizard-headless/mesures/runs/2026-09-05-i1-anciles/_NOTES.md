# Run parcial I1 — Anciles (2026-09-05)

Còpia de `2026-09-03-mesura-8/anciles/` (lectures cachejades per md5; sense `_decisions.json`, `_elapsed.txt`,
`_consolida_cache.json`) + inventari nou (I1: `PDF_V0/ANEJOS/` llegida perquè no hi ha `PDF/`). El runner ha llegit
**només els 5 PDF de `PDF_V0/ANEJOS/`** (14 de cache): 20,3 min, 5,87 USD, un timeout de 600 s al 1r intent de
`sondeos.pdf` (T1 en viu; 414 s al 2n). `_preext/` no es versiona (regenerable; és el mateix que el del run mare més els
5 nous). `_reconsolida-2026-09-05/` = consolidació amb el codi final (regla «V0 mai autoritat») + `_compare_*.txt`.
Resultat i lectura: `../2026-09-03-mesura-8/_AGREGAT-8.md` §I1. Driver: `measure_i1.py` (scratchpad de la sessió; la
lògica és la de `mesures/reconsolida_mesura.py` sobre aquesta carpeta).
