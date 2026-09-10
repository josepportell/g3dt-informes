# 2026-09-06-m341 — M341 v1: mesura COMPLETA (context de plantilla vs signat) dels 7 projectes, cost 0

**Referència viva de M341.** Script: `docs/wizard-headless/mesures/mesura_341.py` (docstring = manual). Lectura `_reconsolida-2026-09-06-pend`.

| variant | escalars + narrativa M · C · X · ND → % | taules M · C · X → % |
|---|---|---|
| `viaA` (7 projectes: lectura + via B + Df del signat) | 156 · 38 · 141 · 47 → **58 %** | 265 · 98 · 100 → **78 %** |
| `t2` (3 amb `_user_data_prev.json` d'abril) | 90 · 9 · 64 · 10 → 61 % | 123 · 24 · 28 → 84 % |

Per grup `viaA`: A 69 % · calc 66 % · narrativa 30 % · resta 65 %. Per projecte (escalars / taules): Castellar 68 / 88, Rubí 60 / 89,
Bell-lloc 68 / 82, Linyola 68 / 88, Alcoletge 52 / 73, Vilanova 40 / 64, Anciles 40 / 74.

**Com llegir-ho:** `<slug>/viaA/_compare_341.txt` (per grup + les cel·les no-MATCH), `_compare_informe.txt` (11 taules), `_calc.json`
(nivell portant, Nb, γ/c/φ/E, Qa, assentament, Es i candidats), `_context_usat.json` (tot el context, sense imatges),
`_user_data_usat.json` (el que «l'Eva hauria escrit»: només Df). Compara runs amb `diff` dels `_compare_341.txt`, mai titulars.

**Assumpcions:** `DF_SIGNAT` (Castellar 0,3 · Rubí 1,0 · Bell-lloc 0,3 · Linyola 1,7 pous · Alcoletge 1,0 · Vilanova 0,3 · Anciles 2,9 pous).
Carpeta: `reference-material/` on té `file_mapping.json` (4: visió inclosa), si no `~/g3dt-e2e/projectes/` amb SmartScan nivell 1
(Vilanova `ANEXOS/`, Anciles `ANEJOS/`: el `file_mapping.json` queda escrit al costat del projecte, fora del repositori).

**Troballes (DECISION-LOG 2026-09-06 (vespre) §Validació):** P5 geometria des de la lectura sense sondeig; P6 classificador de sòl
i topall 3,5; 6 variables NO_DATA sistemàtiques de cablejat; narrativa 30 %. Dos bugs arreglats en aquest run: capa oberta `None`
(Alcoletge) i «1/1/1/1» pres com a N30 (Anciles: 57 cm → 2,20).
