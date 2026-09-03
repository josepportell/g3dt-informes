# Castellar — mesura 2026-09-03 (codi intacte, pre P0-P4)

- **Temps: 33,4 min** (línia base pre-fixos: 27,8) — degraded=False, 13 docs Claude + 6 Python, 0 contaminació DNS.
  Possible causa del +5,6: agent R en paral·lel (repàs informes) i/o camí nou d'adreces; no concloure amb n=1.
- **Escalars** (`_compare_escalars.txt`): 12 OK / 5 CAUTELA / 2 FORA / 1 NOU / 2 «ERR».
- **Taules** (`_compare_taules.txt`): 28 OK / 1 CAUTELA / 0 ERR.
- **Els 2 «ERR» (utm_x/utm_y) són ERRORS DE L'OR, no del sistema**: l'or (golden-read) va transcriure l'S-1
  del caixetí de l'annex de sondeig (423182/4609623); l'informe SIGNAT d'Eva porta el P-1 de COORDENADES.txt
  (`423167.0 ; 4609608.0` — verificat a `eva_reference_values.json` utm_x/utm_y). El sistema ha triat P-1 amb
  la regla «UTM de l'informe = P-1 de COORDENADES.txt» i cita correcta. **Pendent: corregir l'or de Castellar**
  (docs/golden-read/3001621…/_decisions.json) abans d'agregar els 8.
- Els 2 FORA són el Cadastre multi-portal fent la seva feina (RC 3 parcel·les + superfície 1284).
- **Veredicte Castellar: ERR de sistema = 0 ✓** (l'objectiu que mana), pendent de recomptar OK/CAND amb l'or corregit.
- **Or corregit (2026-09-03, sessió 2):** `utm_x_utm_y` de l'or passa a P-1 (`X 423167.0 ; Y 4609608.0`), com ja
  feien els ors de Linyola/Bell-lloc/Alcoletge («Regla Castellar: l'informe usa P-1»). Recompte definitiu
  (`_compare_escalars.txt` regenerat): **14 OK / 5 CAUTELA / 2 FORA / 1 NOU / 0 ERR** (22 camps). Sobre els
  21 amb or: OK 67 % (14/21), CAND 24 % (5/21), FORA 10 % (2/21, correctes fora de carpeta), ERR 0.
