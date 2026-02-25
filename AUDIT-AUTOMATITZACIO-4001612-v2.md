# Auditoria Automatització Informe Geotècnic - v2
## Projecte referència: 4001612 Bell-Lloc d'Urgell

**Data:** 2026-02-05
**Versió:** v2 (post-parametrització template)
**Commit:** `99572d9` (branch `fix/g3dt-template-parametrization`, merged to main)
**Basat en:** Comparació amb informe referència `4001612_informe.pdf` i auditoria v1

---

### Resum Executiu

**Millora global:** De 75.3% ✅ (v1) a ~88% ✅ (v2)

Canvis realitzats en 5 fases:
1. Parametritzar 8 taules del template .docx
2. Parametritzar ~20 paràgrafs del cos del template
3. Fix bugs: antropitzat condicional, data en català, valor sísmic ab
4. Afegir camps manuals (SPT, lab, sulfats, dates, descripció solar) a user_data.json i ReportData
5. Fix CTE classifier (PB+P1→C-1), format S.L., llindars CTE

**Problemes resolts:**
- ✅ Taules DPSH, SPT, Lab, Sulfats, Sísmica, Geotècnica ara parametritzades (25 PARAs corregits)
- ✅ Valor sísmic ab = 0.04 (era 0.08 hardcoded)
- ✅ "Antropitzat" condicional sobre flag `is_anthropized`
- ✅ Data en català ("febrer" no "February")
- ✅ Format empresa S.L. (era SL)
- ✅ CTE edificació C-1 (era C-0 per bug al parser PB+P1)
- ✅ Dates de camp, descripció solar, cota referència, SPT, laboratori ara injectats des de user_data.json

**Problemes pendents (5 categories):**

1. **Coordenades UTM incorrectes** (CRÍTIC) — Afecta unitat geològica ICGC sencera
2. **Valor Qa: 5.33 vs 3.0 kg/cm²** (ALT) — Paràmetres Terzaghi (Df, γ)
3. **Plantilles zona geològica** (MITJÀ) — Textos regionals simplificats
4. **Secció Sondeig descriptiva** (BAIX-MITJÀ) — Paràgrafs estàtics pendents
5. **Paràgrafs observació camp** (BAIX) — Requereixen entrada manual

---

### 1. Coordenades UTM incorrectes (CRÍTIC)

**Impacte:** Unitat geològica ICGC incorrecta (P8G vs Qvpu), afecta Secció 3.1 sencera

**Diagnòstic:**
Les coordenades actuals a `user_data.json` (X=315006.52, Y=4611117.49) van ser obtingudes per geocodificació de l'adreça. Estan **~500m desplaçades** en X.

**Coordenades correctes** (font: Cadastre, ref. catastral `4613172CG1141S`):
- Centroide parcel·la: **X=314508.67, Y=4611192.86** (ETRS89 UTM Huso 31)
- Vèrtexs: X range 314487-314518, Y range 4611186-4611205

**On es troben les coordenades als documents de referència:**
Les coordenades UTM **no apareixen explícitament** a cap document del projecte. L'informe de referència (pàg. 12) diu: "les coordenades del plànol topogràfic consultat a l'ICGC". Però els documents cadastrals (`25.0647/4613172CG1141S0001SU-15.pdf`) sí contenen referència UTM Huso 31 ETRS89, i la consulta WFS del Cadastre retorna els vèrtexs exactes.

**Estat actual (post-fix):**
Coordenades actualitzades a `user_data.json` (X=314508.67, Y=4611192.86) i afegit camp `referencia_catastral: "4613172CG1141S"`. Camp també afegit a `user_data_schema.json`.

**Problema residual:** Fins i tot amb coordenades correctes, ICGC retorna **P8G** (no Qvpu). Causa: la consulta WMS usa el mapa geològic 1:250.000 (roca mare), on tota la zona és P8G. A escala 1:50.000, els dipòsits quaternaris superficials (Qvpu) sí apareixerien.

**Acció pendent:**
1. ~~Actualitzar `user_data.json`~~ ✅ Fet
2. Canviar `icgc_geology.py` per consultar capa 1:50.000 en lloc de 1:250.000
3. Alternativament: permetre entrada manual de la unitat ICGC a `user_data.json` (`geological_unit: "Qvpu"`)

---

### 2. Valor Qa (capacitat portant): 5.33 vs 3.0 kg/cm² (ALT)

**Impacte:** PARA 222 — valor central de les conclusions

**Diagnòstic:**
La **fórmula de Terzaghi implementada és correcta**. La diferència ve dels **paràmetres d'entrada**, no del càlcul.

**Paràmetres de referència** (Taula 10, pàg. 21):

| Paràmetre | Referència | Automatitzat | Font referència | Font automatitzat |
|-----------|-----------|-------------|-----------------|-------------------|
| Nb (DPSH N20) | 25-R | 25-R | DPSH.xls | DPSH.xls (✅ idèntic) |
| N (SPT N30) | 54 | 54 | user_data.json | user_data.json (✅ idèntic) |
| γ (densitat) | 2.0 g/cm³ | 2.1 g/cm³ | Judici professional | Correlació N20≥30 → 2.1 |
| c (cohesió) | 0.0 | 0.0 | Material granular | Material granular (✅) |
| φ (fregament) | 38° | 38° | Correlació N20 | Correlació N20 (✅) |
| E (deformació) | 650 kg/cm² | ~350-400 | Judici professional | Correlació E=10×N20 |
| **Df (prof. fonament.)** | **~0.3 m** | **0.8 m** | Sanejament 30cm vegetals | Default codi |
| B (ample sabata) | 1.0 m | 1.0 m | Per defecte | Per defecte (✅) |
| F (seguretat) | 3 | 3 | NCSE-02 | NCSE-02 (✅) |

**Càlcul verificatiu amb paràmetres referència:**
Terzaghi sabata aïllada quadrada: Qd = 1.3·c·Nc + γ·Df·Nq + 0.4·γ·B·Nγ

Amb φ=38°: Nc=77.5, Nq=61.5, Nγ=67.4
Qd = 0 + 2000×0.3×61.5 + 0.4×2000×1.0×67.4 = 36900 + 53920 = 90820 kg/m²
Qa = 90820 / 3 = 30273 kg/m² = **3.03 kg/cm² ≈ 3.0** ✅

Amb γ=2.1, Df=0.8 (automatitzat):
Qd = 0 + 2100×0.8×61.5 + 0.4×2100×1.0×67.4 = 103320 + 56616 = 159936 kg/m²
Qa = 159936 / 3 = 53312 kg/m² = **5.33 kg/cm²**

**Conclusió:** La diferència és 100% atribuïble a:
1. **Df=0.8m vs 0.3m** (factor principal) — El geòleg sap que sanejaran ~30cm de vegetals, no 80cm
2. **γ=2.1 vs 2.0** (factor menor) — El geòleg ajusta la densitat per judici professional

**Estat actual (post-fix):**
Camp `foundation_depth_m: 0.3` afegit a `user_data.json` i a `user_data_schema.json`. Amb Df=0.3m, **Qa = 3.18 kg/cm²** (era 5.33).

**Diferència residual (3.18 vs 3.0):**
Causada per γ=2.1 (correlació automàtica N20≥30) vs γ=2.0 (judici professional G3DT). Diferència de 6% — acceptable per a la majoria de projectes.

**Acció pendent (si es vol exactitud):**
1. ~~Afegir `foundation_depth_m`~~ ✅ Fet
2. Considerar γ=2.0 com a default per materials granulars amb N20≥30 (reduiria Qa de 3.18 a 3.03)
3. El mòdul E no afecta Qa directament (s'usa per assentaments), però cal ajustar la correlació

---

### 3. Plantilles de zona geològica (MITJÀ)

**Impacte:** PARAs 121-126 (marc geològic), 132, 135, 205 — 9 paràgrafs

**Estat actual:**
`section3_geologia.py` genera text genèric per la "Depressió de l'Ebre" (zona correcta), però els paràgrafs no coincideixen amb el text detallat de la referència. La referència té 6 paràgrafs d'història geològica molt específics (evolució Eocè-Oligocè, conca endorreica, etc.).

**Causa:**
G3DT disposa de plantilles de text geològic regional al seu servidor intern, amb textos detallats per zona. El codi `REGIONAL_TEMPLATES` al `section3_geologia.py` és una versió simplificada.

**Acció requerida:**
1. Obtenir de G3DT les plantilles completes per zona geològica (mínim: Depressió Ebre, Vallès-Penedès)
2. Integrar-les com a fitxers a `templates/geological_regions/`
3. El selector de zona funciona correctament — només cal millorar el contingut

---

### 4. Secció Sondeig descriptiva (BAIX-MITJÀ)

**Impacte:** PARAs 102-106 — 5 paràgrafs de text descriptiu del sondeig a rotació

**Estat actual:**
El toggle `has_sondeig` funciona i afegeix la secció condicional, però no genera els paràgrafs descriptius de la tècnica del sondeig (text fix, verd a les indicacions G3DT).

**Acció requerida:**
Afegir 3 paràgrafs de text estàtic al template dins el bloc condicional `{% if has_sondeig %}`:
- Descripció tècnica del sondeig a rotació amb bateria contínua
- Característiques de l'equip
- Foto del sondeig

---

### 5. Paràgrafs d'observació de camp (BAIX)

**Impacte:** PARAs 78, 157, 220 — 3 paràgrafs

**Estat actual:**
Requereixen observacions visuals del tècnic al camp. PARA 78 (descripció solar) ara s'injecta parcialment via `site_description` de user_data.json, però el text exacte difereix.

**Acció requerida:**
Ampliar user_data.json amb camps descriptius addicionals o acceptar que requereixen edició manual post-generació.

---

### Taula comparativa v1 → v2

| Mètrica | v1 (pre-fix) | v2 (post-fix) | Millora |
|---------|-------------|--------------|---------|
| ✅ Correcte (>95% match) | 171 (75.3%) | ~200 (88%) | +29 PARAs |
| ⚠️ Modificat (80-95%) | 23 (10.1%) | ~12 (5%) | -11 PARAs |
| ❌ No implementat (<50%) | 33 (14.5%) | ~15 (7%) | -18 PARAs |

**Detall d'elements corregits per fase:**

| Fase | Elements corregits | Exemples |
|------|-------------------|----------|
| F1: Taules | ~15 cel·les de taula | DPSH 2 tests +199.50, SPT N30=54, Sulfats 89.8 |
| F2: Cos text | ~10 paràgrafs | Geologia Depressió Ebre, adjacents, adreça |
| F3: Bugs | 5 paràgrafs | ab=0.04, antropitzat correcte, data català |
| F4: Camps manuals | 3 paràgrafs | Dates camp, descripció solar, cota referència |
| F5: Polish | 2 elements | CTE C-1, format S.L. |

---

### Elements pendents detallats

| # | Element | Categoria | Acció | Prioritat |
|---|---------|-----------|-------|-----------|
| 1 | ~~Coordenades UTM~~ | ~~Dades~~ | ~~Actualitzar a X=314509, Y=4611193~~ | ✅ FET |
| 2 | Unitat ICGC (P8G → Qvpu) | Escala mapa | Canviar WMS de 1:250k a 1:50k, o entrada manual | ALT |
| 3 | Qa = 3.18 → 3.0 | γ correlació | Ajustar γ default de 2.1 a 2.0 per granulars densos | BAIX |
| 4 | E = ~400 → 650 | Paràmetres | Ajustar correlació E o afegir camp manual | ALT |
| 5 | Plantilles geologia detallades | Contingut G3DT | Obtenir textos originals de G3DT | MITJÀ |
| 6 | Text sondeig descriptiu | Template | Afegir paràgrafs estàtics al template | BAIX-MITJÀ |
| 7 | Descripció nivell litològic | Contingut | "Graves en matriu sorrenca carbonatades" vs genèric | MITJÀ |
| 8 | Paràgrafs observació camp | Manual | Ampliar user_data o acceptar edició manual | BAIX |
| 9 | Figures plànol arquitecte | No automatitzable | Requereix plànols originals | BAIX |
| 10 | Ordinals format ("1er Nivell" vs "Nivell 1") | Format | Ajustar template | BAIX |

---

### Fitxers modificats en aquest cicle

| Fitxer | Canvis |
|--------|--------|
| `automation/report_generator.py` | +344 línies: context Jinja expandit, data català, format S.L., regex |
| `automation/report_data.py` | +134 línies: nous camps ReportData, usa `classify_building()` |
| `automation/sections/section3_geologia.py` | +808 línies: condicional antropitzat, plantilles regionals millorades |
| `automation/cte_classifier.py` | +25 línies: fix `parse_floor_count` PB+P1, llindars CTE corregits |
| `automation/parametrize_template.py` | +437 línies: script per modificar template .docx programàticament |
| `templates/g3dt-jinja-template.docx` | 8 taules + 20 paràgrafs parametritzats |
| `reference-material/4001612-bell-lloc/user_data.json` | +80 línies: SPT, lab, sulfats, dates, descripció, adjacents |

---

### Recomanació pròxims passos

1. ~~**Immediat:** Actualitzar coordenades UTM~~ ✅ Fet (X=314508.67, Y=4611192.86 des de Cadastre WFS)
2. ~~**Curt termini:** Afegir `foundation_depth_m`~~ ✅ Fet (Df=0.3m, Qa=3.18)
3. **Curt termini:** Canviar consulta ICGC de 1:250k a 1:50k per obtenir Qvpu
4. **Mitjà termini:** Obtenir plantilles geologia detallades de G3DT
5. **Mitjà termini:** Automatitzar extracció coordenades des de referència catastral
6. **Nous camps afegits a `user_data_schema.json`:** `foundation_depth_m`, `referencia_catastral`, `is_anthropized`, `field_work_dates`, `site_description`, `access_description`, `cota_referencia`, `spt_data`, `lab_tests`, `sulfate_mg_kg`
