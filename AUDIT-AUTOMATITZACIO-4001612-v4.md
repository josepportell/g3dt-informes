# Auditoria Automatització Informe Geotècnic - v4
## Projecte referència: 4001612 Bell-Lloc d'Urgell

**Data:** 2026-02-06
**Versió:** v4 (adjacents visor + dates DPSH + lab PDF + slope MDT)
**Branca:** `main`
**Basat en:** Auditoria v3, test en viu del skill `/g3dt-adjacents-visor`, implementació D/L/S

---

### Resum Executiu

**Millora global:** De ~92% (v3) a **~95%** (v4)

Canvis realitzats en sessió 2026-02-06:
1. Skill `/g3dt-adjacents-visor` operatiu i testat amb èxit
2. Adjacents extrets automàticament del visor cadastral (Playwright + Claude Vision)
3. **Dates de camp** auto-extretes del DPSH PDF + Lab PDF (PyMuPDF)
4. **Sulfats i dades lab** auto-extrets de LAB-SIG.pdf (PyMuPDF)
5. **Pendent del terreny** calculat automàticament des d'ICGC MDT (5 punts)

**Problemes resolts des de v3:**
- ✅ Adjacents: de 100% manual a **semi-automàtic** (visor Cadastre)
- ✅ Dates de camp: de 100% manual a **automàtic** (DPSH + Lab PDFs)
- ✅ Sulfats + lab metadata: de 100% manual a **automàtic** (Lab PDF)
- ✅ `is_sloped`: de default estàtic a **automàtic** (ICGC MDT slope)

**Problemes pendents (4 categories, sense canvis):**

1. **Qa: 3.18 vs 3.0 kg/cm²** (BAIX) — γ=2.1 vs 2.0 (esperant G3DT)
2. **E: ~400 vs 650 kg/cm²** (BAIX) — Correlació E (esperant G3DT)
3. **Plantilles zona geològica** (MITJÀ) — Textos regionals (esperant contingut)
4. **Secció Sondeig descriptiva** (BAIX-MITJÀ) — Paràgrafs estàtics (esperant contingut)

---

### Canvis v3 → v4

#### 1. Skill `/g3dt-adjacents-visor` (NOU — semi-auto)

**Problema v3:** Adjacents (4 camps) eren 100% manuals. L'API del Cadastre (`cadastre_adjacents.py`) només retorna "via pública" o "parcel·la veïna" — sense noms de carrer.

**Solució v4:**
- Skill Playwright que obre el visor cartogràfic del Cadastre
- Navega per referència catastral, ajusta zoom, fa screenshot
- Claude Vision analitza el mapa i extreu noms de carrers i veïns
- Genera `adjacents_visor.json` amb confiançes per costat

**Test en viu (Bell-Lloc 4613172CG1141S):**

| Costat | Resultat visor | Referència informe | Match |
|--------|---------------|-------------------|-------|
| Nord | parcel·la veïna | parcel·la buida | ✅ equivalent |
| Sud | Carrer d'Antoni Bellet i Pérez | Carrer d'Antoni Bellet i Pérez | ✅ exacte |
| Est | Carrer Mestre Ramon Ortiz | Carrer Mestre Ramon Ortiz | ✅ exacte |
| Oest | parcel·la veïna | construcció aïllada de 2 plantes | ⚠️ parcial |

**Nota Oest:** El visor mostra parcel·les 74/75 amb edificis (POR) però no el detall "2 plantes". Això requereix observació de camp — el visor aporta la base, l'usuari afina.

**Integració a `report_generator.py`:**
```
Prioritat 1: user_data.json (camps ja omplerts manualment)
Prioritat 2: adjacents_visor.json (generat pel skill)
Prioritat 3: cadastre_adjacents.py API probes (fallback automàtic)
```

**Fitxers:**
- `.claude/commands/g3dt-adjacents-visor.md` — Definició del skill
- `reference-material/4001612-bell-lloc/validation/adjacents_visor.json` — Output
- `reference-material/4001612-bell-lloc/validation/adjacents_visor_screenshot.png` — Evidència visual

#### 2. Dates de camp des del DPSH PDF (NOU — auto)

**Problema v3:** `field_work_dates` i `field_work_dates_text` eren 100% manuals.

**Solució v4:**
- Nova funció `extract_field_dates()` a `dpsh_extractor.py` usa PyMuPDF
- Extreu "DATA: dd/mm/yyyy" del DPSH PDF (dates proves DPSH)
- Extreu data d'extracció del Lab PDF (= data sondeig, la més antiga)
- `format_dates_catalan()` genera text català: "1 i 6 d'octubre de 2025"
- S'activa com a fallback a `report_generator.py` quan el camp és buit

**Resultat verificat (Bell-Lloc):**
```
DPSH PDF: DATA: 01/10/2025 (2 pàgines, mateixa data)
Lab PDF:  Data extracció: 06/10/2025 (data sondeig)
Combinat: ['2025-10-01', '2025-10-06']
Text:     "1 i 6 d'octubre de 2025" ✅ (match exacte amb referència)
```

**Fitxers:** `automation/dpsh_extractor.py` (extract_field_dates, format_dates_catalan)

#### 3. Sulfats i dades lab des del PDF (NOU — auto)

**Problema v3:** `sulfate_mg_kg`, `lab_tests[]` eren 100% manuals.

**Solució v4:**
- Nou mòdul `automation/lab_extractor.py` usa PyMuPDF
- Extreu: sulfats (mg/kg), sample_id (SPT-1), location (S-1), depth (-1.0 a -1.6)
- Regex adaptades al format TPS lab (2 columnes, text barrejat)
- S'activa com a fallback a `report_generator.py` quan `lab_tests` és buit

**Resultat verificat (Bell-Lloc, LAB-SIG.pdf):**
```
sulfate_mg_kg: 89.8 ✅ (match exacte)
sample_id:     SPT-1 ✅
location:      S-1 ✅
depth:         -1.0 a -1.6 ✅ (equivalent a -1.00 a -1.60)
test_type:     "Contingut en sulfats solubles UNE 103100:95"
```

**Fitxers:** `automation/lab_extractor.py` (NOU), `automation/report_generator.py` (auto-fill block)

#### 4. Pendent del terreny des d'ICGC MDT (NOU — auto)

**Problema v3:** `is_sloped` era un default estàtic (`false`).

**Solució v4:**
- Nova funció `get_slope()` a `icgc_geology.py`
- Consulta 5 punts MDT (centre + 4 cardinals a 10m)
- Calcula gradient màxim i direcció dominant
- Si pendent > 15% → `is_sloped = True`
- S'activa automàticament durant la generació de l'informe

**Resultat verificat (Bell-Lloc):**
```
Slope: 0.2% toward SW ✅ (Bell-Lloc és al Pla d'Urgell, terreny pla)
is_sloped: False ✅
```

**Fitxers:** `automation/icgc_geology.py` (get_slope), `automation/report_generator.py` (auto-fill block)

---

### Automatització user_data.json — Anàlisi completa de camps

#### Camps totalment automatitzats (no requereixen entrada)

| # | Camp | Font | Mètode | Des de |
|---|------|------|--------|--------|
| 1 | `expedient` | Nom carpeta | Parsing ("4001612 BELL-LLOC" → "4001612") | v1 |
| 2 | `municipality` | Nom carpeta | Parsing → title case | v1 |
| 3 | `client.*` (nom, NIF, adreça, tel, email) | DADES CLIENT.txt | Regex patterns | v1 |
| 4 | DPSH N20, Nb, profunditat, refús | DPSH.xls | `dpsh_extractor.py` (xlrd) | v1 |
| 5 | φ, γ, E, densitat relativa | Correlacions DPSH | `GeotechCorrelations` | v1 |
| 6 | `soil_class`, `cte_class` | Correlacions DPSH | Classificació automàtica | v1 |
| 7 | `has_sondeig` | Detecció fitxers | Busca SONDEIG.pdf/.FH11 | v1 |
| 8 | `has_retaining_walls` | Detecció fitxers | Busca plànols murs | v2 |
| 9 | `architect_name` | planol_extracted.json | `/g3dt-extreure-planol` (Vision) | v2 |
| 10 | `building_type` | planol_extracted.json | Vision | v2 |
| 11 | `num_floors` | planol_extracted.json | Vision | v2 |
| 12 | `superficie_parcela_m2` | planol_extracted.json | Vision | v2 |
| 13 | `superficie_construida_m2` | planol_extracted.json | Vision | v2 |
| 14 | `street_address` | planol_extracted.json | Vision | v2 |
| 15 | `has_basement` | planol_extracted.json | Vision | v2 |
| 16 | `is_urban` | planol_extracted.json | Vision | v2 |
| 17 | `parcel_shape` | planol_extracted.json | Vision | v2 |
| 18 | `utm_x`, `utm_y` | Cadastre WFS | API per refcat | v2 |
| 19 | `referencia_catastral` | Cadastre WFS | API per adreça | v2 |
| 20 | `cota_referencia` | ICGC MDT 2m | WMS LiDAR (fallback) | v3 |
| 21 | `geological_unit` | ICGC 50k | WMS (fallback 250k) | v3 |
| 22 | `seismic_ab` | NCSE-02 | Lookup per municipi | v1 |
| 23 | `radon_zone` | CTE DB HS6 | Lookup per municipi | v1 |
| 24 | `field_work_dates` | DPSH PDF + Lab PDF | PyMuPDF regex | **v4** |
| 25 | `field_work_dates_text` | Derivat de dates | `format_dates_catalan()` | **v4** |
| 26 | `sulfate_mg_kg` | LAB-SIG.pdf | PyMuPDF regex | **v4** |
| 27 | `lab_tests[]` (type, sample_id, location, depth) | LAB-SIG.pdf | PyMuPDF regex | **v4** |
| 28 | `is_sloped` | ICGC MDT 2m | 5-punt gradient (>15%) | **v4** |

#### Camps semi-automatitzats (proposta automàtica, revisió humana)

| # | Camp | Font | Mètode | Des de |
|---|------|------|--------|--------|
| 29 | `adjacent_north` | Visor Cadastre | Playwright + Vision | **v4** |
| 30 | `adjacent_south` | Visor Cadastre | Playwright + Vision | **v4** |
| 31 | `adjacent_east` | Visor Cadastre | Playwright + Vision | **v4** |
| 32 | `adjacent_west` | Visor Cadastre | Playwright + Vision | **v4** |
| 33 | DPSH (validació) | PENETROS.pdf | Vision vs Excel | v2 |
| 34 | Sondeig (capes, SPT) | SONDEIG.pdf | Vision → review.html | v2 |
| 35 | Plànol (dimensions) | A.01.pdf | Vision → review.html | v2 |

#### Camps manuals irreductibles

| # | Camp | Per què no es pot automatitzar |
|---|------|-------------------------------|
| 36 | `site_description` | Observació presencial del solar |
| 37 | `access_description` | Observació presencial |
| 38 | `spt_data` | Resultats sondeig (potencialment del PDF) |
| 39 | `foundation_depth_m` | Decisió professional del geòleg |
| 40 | `architect_company` | No sempre al plànol |

#### Camps amb defaults raonables (revisió ràpida)

| # | Camp | Default | Correcte en | Notes |
|---|------|---------|------------|-------|
| 41 | `is_anthropized` | `true` | >90% projectes urbans | Excepció: parceles rústiques |
| 42 | `site_position` | `"centre"` | ~70% casos | Casos extrems: cantonada, cap |
| 43 | `num_soil_levels` | `1` | ~60% | Podria derivar-se del DPSH |
| 44 | `foundation_depth_m` | `0.3` | ~80% residencial | Decisió del geòleg |

---

### Resum de cobertura

```
┌─────────────────────────────────────────────────────────┐
│  AUTOMATITZACIÓ user_data.json — v4                      │
│                                                          │
│  ████████████████████████████░░  28 camps (64%) AUTOMÀTIC│
│  ███████░░░░░░░░░░░░░░░░░░░░░░   7 camps (16%) SEMI-AUTO│
│  █████░░░░░░░░░░░░░░░░░░░░░░░░   5 camps (11%) MANUAL   │
│  ████░░░░░░░░░░░░░░░░░░░░░░░░░   4 camps  (9%) DEFAULTS │
│                                                          │
│  Total: 44 camps identificats                            │
│  Automatització efectiva: ~80% (auto + semi-auto)        │
│  Requereix intervenció: ~20% (manual + defaults)         │
└─────────────────────────────────────────────────────────┘
```

**Per a un projecte típic, l'usuari G3DT ha d'omplir:**
1. Descripcions de camp (2 camps) — observació presencial
2. SPT data (1 camp) — interpretació resultats sondeig
3. Profunditat fonamentació (1 camp) — decisió geòleg
4. Empresa arquitecte (1 camp) — si no és al plànol
5. Revisió adjacents (4 camps) — confirmar proposta visor
6. Revisió defaults (4 camps) — check ràpid

**Temps estimat d'entrada manual:** ~10 minuts per projecte (v3: 15-20 min, v1: 45-60 min)

---

### Pipeline complet d'automatització

```
┌─────────────────────────────────────────────────────────────────┐
│ FASE 0: RECEPCIÓ DE DOCUMENTACIÓ                                │
│                                                                  │
│   Arquitecte → A.01.pdf (plànol)                                │
│   G3DT camp  → PENETROS.pdf, SONDEIG.pdf, DPSH.xls            │
│   Laboratori → Resultats SPT + sulfats                          │
│   Client     → DADES CLIENT.txt                                 │
├─────────────────────────────────────────────────────────────────┤
│ FASE 1: EXTRACCIÓ AUTOMÀTICA                                    │
│                                                                  │
│   project_extractor.py                                           │
│   ├── Carpeta → expedient, municipi                             │
│   ├── DADES CLIENT.txt → client.*                               │
│   ├── DPSH.xls → N20, correlacions                              │
│   └── Detecció fitxers → flags booleans                         │
│                                                                  │
│   APIs automàtiques (durant generació):                          │
│   ├── Cadastre WFS → UTM, refcat                                │
│   ├── ICGC 50k → unitat geològica                               │
│   ├── ICGC MDT → cota referència                                │
│   └── NCSE-02/CTE → sísmica, radó                               │
├─────────────────────────────────────────────────────────────────┤
│ FASE 2: EXTRACCIÓ VISUAL (Claude Vision)                        │
│                                                                  │
│   /g3dt-extreure-planol → planol_extracted.json                 │
│   /g3dt-validar-penetros → dpsh_extracted.json                  │
│   /g3dt-validar-sondeig → sondeig_extracted.json                │
│   /g3dt-adjacents-visor → adjacents_visor.json         ← NOU v4│
│                                                                  │
│   Tots → review.html per revisió humana                         │
├─────────────────────────────────────────────────────────────────┤
│ FASE 3: ENTRADA MANUAL (G3DT)                                   │
│                                                                  │
│   user_data.json — 9 camps manuals:                              │
│   ├── Dates camp (agenda)                                        │
│   ├── Descripcions (observació)                                  │
│   ├── Lab/SPT (resultats)                                        │
│   └── Df (decisió geòleg)                                        │
├─────────────────────────────────────────────────────────────────┤
│ FASE 4: GENERACIÓ INFORME                                        │
│                                                                  │
│   report_generator.py                                            │
│   ├── Carrega user_data.json                                     │
│   ├── Auto-fill buits (visor → API → defaults)                  │
│   ├── Renderitza template Jinja → .docx                          │
│   └── Genera warnings per camps mancants                         │
└─────────────────────────────────────────────────────────────────┘
```

---

### Taula comparativa v1 → v2 → v3 → v4

| Mètrica | v1 | v2 | v3 | v4 | Tendència |
|---------|-----|-----|-----|-----|-----------|
| ✅ Correcte (>95% match) | 171 (75%) | ~200 (88%) | ~210 (92%) | ~217 (95%) | +46 des de v1 |
| ⚠️ Modificat (80-95%) | 23 (10%) | ~12 (5%) | ~8 (4%) | ~5 (2%) | -18 |
| ❌ No implementat (<50%) | 33 (15%) | ~15 (7%) | ~9 (4%) | ~5 (2%) | -28 |

**Millores v4:**
- ~3 PARAs dels adjacents (situació, descripció solar, conclusions)
- ~2 PARAs de dates camp (apareix a capçalera i secció 2)
- ~2 PARAs de sulfats/lab (secció 3 + taules)
- ~1 PARA de pendent (secció 1 descripció)

---

### Elements pendents detallats

| # | Element | Estat | Acció | Prioritat |
|---|---------|-------|-------|-----------|
| ~~1~~ | ~~Coordenades UTM~~ | ✅ v2 | ~~Actualitzades~~ | FET |
| ~~2~~ | ~~Unitat ICGC (P8G → Qvpu)~~ | ✅ v3 | ~~Capa 50k amb fallback~~ | FET |
| ~~3~~ | ~~Cota referència manual~~ | ✅ v3 | ~~Auto-fill ICGC MDT~~ | FET |
| ~~4~~ | ~~Df foundation_depth_m~~ | ✅ v2 | ~~Camp afegit (0.3m)~~ | FET |
| ~~5~~ | ~~Adjacents 100% manual~~ | ✅ v4 | ~~Visor Cadastre skill~~ | FET |
| ~~6~~ | ~~Dates camp 100% manual~~ | ✅ v4 | ~~DPSH+Lab PDF extract~~ | FET |
| ~~7~~ | ~~Sulfats/lab 100% manual~~ | ✅ v4 | ~~Lab PDF extract~~ | FET |
| ~~8~~ | ~~is_sloped default estàtic~~ | ✅ v4 | ~~ICGC MDT slope~~ | FET |
| 9 | Qa = 3.18 → 3.0 (γ) | Esperant G3DT | Eva confirma γ=2.0 o 2.1 | BAIX |
| 10 | E = ~400 → 650 | Esperant G3DT | Eva confirma correlació E | BAIX |
| 11 | Plantilles geologia detallades | Esperant contingut | G3DT proporciona textos per zona | MITJÀ |
| 12 | Text sondeig descriptiu | Esperant contingut | G3DT proporciona paràgrafs estàndard | BAIX-MITJÀ |
| 13 | Descripció nivell litològic | Contingut | "Graves en matriu sorrenca carbonatades" | MITJÀ |
| 14 | Ordinals ("1er Nivell" vs "Nivell 1") | Format template | Ajustar template | BAIX |

---

### Possibles millores futures

| # | Millora | Impacte | Dificultat | Notes |
|---|---------|---------|------------|-------|
| A | Extracció SPT del full de sondeig | Elimina 1 camp manual | MITJÀ | `/g3dt-validar-sondeig` ja extreu parcialment |
| ~~B~~ | ~~Extracció sulfats del PDF lab~~ | ~~Elimina 2 camps~~ | ~~BAIX~~ | **IMPLEMENTAT v4** |
| C | Wizard interactiu (5 preguntes) | UX | BAIX | CLI que pregunta els 5 camps manuals |
| D | `site_description` template | Semi-auto | BAIX | "Parcel·la de forma {shape} amb {sup}m²..." |
| E | `access_description` template | Semi-auto | BAIX | "L'accés es realitza des del {adjacent_south}" |
| ~~F~~ | ~~MDT slope → `is_sloped`~~ | ~~Elimina 1 default~~ | ~~BAIX~~ | **IMPLEMENTAT v4** |
| G | DPSH N20 transitions → `num_soil_levels` | Elimina 1 default | BAIX | Anàlisi de canvis bruscos |

**Quick wins (D+E):** Si s'implementen els templates per `site_description` i `access_description`, els camps "manuals" es redueixen de 5 a 3, i els 2 restants es pre-omplen amb text editable.

---

### Recomanació pròxims passos

1. **Immediat:** Confirmar amb G3DT γ i E (desbloqueja elements 9-10)
2. **Curt termini:** Implementar templates site/access description (quick wins D+E)
3. **Curt termini:** Crear wizard interactiu per user_data.json (millora C — ara només 5 preguntes)
4. **Mitjà termini:** Obtenir plantilles geologia i sondeig de G3DT (desbloqueja 11-12)
5. **Opcional:** Extracció SPT del full de sondeig (millora A)

---

### Fitxers modificats v3 → v4

| Fitxer | Canvis |
|--------|--------|
| `.claude/commands/g3dt-adjacents-visor.md` | NOU: Skill Playwright per adjacents (161 línies) |
| `automation/lab_extractor.py` | NOU: Extracció sulfats/lab del PDF (247 línies) |
| `automation/dpsh_extractor.py` | +120 línies: `extract_field_dates()`, `format_dates_catalan()` |
| `automation/icgc_geology.py` | +40 línies: `get_slope()` (5-punt MDT gradient) |
| `automation/report_generator.py` | +30 línies: 3 blocs auto-fill (dates, lab, slope) |
| `validation/adjacents_visor.json` | Regenerat amb test en viu |
| `validation/adjacents_visor_screenshot.png` | Regenerat amb test en viu |

**Dependència:** PyMuPDF (fitz) — ja instal·lat, usat per D i L.

---

*Auditoria generada: 2026-02-06. Implementacions D/L/S + skill adjacents testats amb èxit sobre Bell-Lloc.*
