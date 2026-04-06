# Audit: Format Coverage Across 7 Projects

**Data:** 2026-04-06
**Post:** Blocks 0-5 implemented
**Executat amb:** `diagnostic_trace.py --all --classify`
**Branca:** `feature/concept-format-separation`

---

## 1. Nota sobre dades cached

Les extraccions de visio (planol, sondeig, dpsh) utilitzen **fitxers JSON cached** a `validation/`. El diagnostic NO re-executa Claude vision — usa els `planol_extracted.json`, `sondeig_extracted.json` i `dpsh_extracted.json` que ja existeixen. Les dates d'aquests caches son desconegudes (possiblement setmanes/mesos antics). Cal refrescar-los amb els prompts millorats.

| Projecte | planol_extracted | sondeig_extracted | dpsh_extracted |
|----------|-----------------|-------------------|----------------|
| Bell-Lloc | SI | SI | SI |
| Castellar | SI | SI | SI |
| Rubi | SI | NO | SI |
| Linyola | SI (parcial) | SI | SI |
| Alcoletge | NO | NO | NO |
| Vilanova | NO | NO | NO |
| Anciles | NO | SI | NO |

**Accio necessaria:** Refrescar TOTS els caches de visio despres de millorar els prompts (Block 6).

---

## 2. Metriques Globals

### Comparacio amb baseline

| Metrica | Baseline (pre-Blocks) | Post Blocks 0-5 | Delta |
|---------|----------------------|------------------|-------|
| MATCH | ~21 | 46 | +25 |
| CLOSE | ~8 | 15 | +7 |
| MISMATCH | ~70 | 86 | +16 (mes vars comparades) |
| NOT_EXTRACTED | ~182 | 134 | -48 |
| Match+Close rate | 29.3% | **41.5%** | +12.2 pp |
| Total comparades | 99 | 147 | +48 (Blocks 4-5 afegeixen vars) |

### Distribucio global

```
Total: 281 var-comparisons
  46 match (16.4%)
  15 close (5.3%)
  86 mismatch (30.6%)
  134 not_extracted (47.7%)
Match+Close rate: 41.5% (de 147 comparades)
```

---

## 3. Per-Project Breakdown

| Projecte | Match | Close | Mismatch | Not_Ext | Total | Rate | Vision cache |
|----------|-------|-------|----------|---------|-------|------|-------------|
| Bell-Lloc | 17 | 3 | 10 | 14 | 44 | **66.7%** | planol+sondeig+dpsh |
| Castellar | 7 | 2 | 12 | 22 | 43 | 42.9% | planol+sondeig+dpsh |
| Rubi | 9 | 1 | 11 | 18 | 39 | 47.6% | planol+dpsh |
| Linyola | 4 | 3 | 10 | 17 | 34 | 41.2% | planol (parcial) |
| Alcoletge | 2 | 2 | 11 | 20 | 35 | 26.7% | **cap** |
| Vilanova | 4 | 2 | 14 | 16 | 36 | 33.3% | **cap** |
| Anciles | 3 | 2 | 18 | 17 | 40 | 21.7% | sondeig nomes |

**Observacio clau:** Bell-Lloc (66.7%) te TOTES les visions cached. Projectes sense vision (Alcoletge 26.7%, Anciles 21.7%) son els pitjors. La visio es el factor diferencial mes gran.

---

## 4. Classificacio MISMATCH (86 total)

| Tipus | Quantitat | Descripcio |
|-------|-----------|------------|
| **EXTRACTION** | 63 | Cap senyal correcte existeix — problema de format/extraccio |
| **CALC** | 15 | qa_value/settlement/k30 — inputs de calcul (B, Df defaults) |
| **NARRATIVE** | 7 | site_description — Eva escriu text personalitzat del camp |
| **PRIORITY** | 1 | El valor correcte existeix pero el guanyador es un altre |

---

## 5. Variables "ALL wrong" (7/7 MISMATCH)

| Variable | Causa arrel | Tipus |
|----------|------------|-------|
| adjacent_south_fmt | Cadastre retorna descripcions de parcel·la diferents del que Eva veu al camp | EXTRACTION |
| adjacent_west_fmt | Idem — dades del Cadastre vs observacio de camp d'Eva | EXTRACTION |
| qa_value | B=1.0, Df=0.8 son defaults — sense wizard, Terzaghi-Peck divergeix | CALC |
| settlement | Depent de qa_value incorrecte | CALC |
| site_description | Narrativa — Eva descriu el camp amb les seves paraules | NARRATIVE |

---

## 6. Variables "never extracted" (13 variables, 7/7 NOT_EXTRACTED)

### Lab report variables (9)
| Variable | Font esperada | Accio |
|----------|--------------|-------|
| lab_depth | GTL report PDF | Extreure de lab PDF |
| lab_field_company | GTL report PDF | Extreure de lab PDF |
| lab_field_description | GTL report PDF | Extreure de lab PDF |
| lab_location | GTL report PDF | Extreure de lab PDF |
| lab_sample_id | GTL report PDF | Extreure de lab PDF |
| lab_testing_company | GTL report PDF | Extreure de lab PDF |
| lab_testing_description | GTL report PDF | Extreure de lab PDF |
| lab_tests_text | GTL report PDF | Extreure de lab PDF |
| access_street | Narrativa composada | Template des d'adjacents |

### Narrative/template variables (4)
| Variable | Font esperada | Accio |
|----------|--------------|-------|
| building_structure_desc | Planol (num_floors + tipus) | Template des de building_type |
| location_sentence | Composat d'adreça + adjacents | Template |
| num_dpsh_tests | DPSH data (ja tenim el comptatge) | Formatear frase |
| site_condition | Composat de slope, ICGC data | Template |
| table_dpsh_range | DPSH data | Formatear referencies de taules |

---

## 7. Cross-Project Variable Matrix

### Variables amb MISMATCH

| Variable | MATCH | CLOSE | MISMATCH | NOT_EXT | Nota |
|----------|-------|-------|----------|---------|------|
| adjacent_south_fmt | - | - | 7 | - | ALL wrong (Cadastre vs camp) |
| adjacent_west_fmt | - | - | 7 | - | ALL wrong |
| qa_value | - | - | 7 | - | ALL wrong (defaults B, Df) |
| settlement | - | - | 7 | - | ALL wrong |
| site_description | - | - | 7 | - | ALL wrong (narrativa) |
| adjacent_east_fmt | 1 | - | 6 | - | Bell-Lloc OK, resta wrong |
| adjacent_north_fmt | 1 | - | 6 | - | Bell-Lloc OK, resta wrong |
| architect_name | 1 | - | 5 | - | Nomes Bell-Lloc (planol vision) |
| client_name | - | 1 | 4 | 2 | 4 wrong, 2 missing |
| building_type | - | 3 | 4 | - | 3 CLOSE (parcial), 4 wrong |
| cte_edificacio | 2 | - | 4 | - | Falla perque building_type falla |
| cte_sol | 2 | - | 4 | - | Falla per N20/soil classification |
| field_work_dates_text | 2 | - | 3 | 2 | Format de dates diferent |
| spt_lithology | - | - | 2 | 2 | Visio diferent o sense cache |
| spt_n30 | - | - | 2 | 2 | Bell-Lloc=62 (hauria ser 54), Anciles wrong |
| seismic_ab_text | 3 | 2 | 2 | - | Format text diferent |
| num_floors | 2 | - | 1 | 4 | 4 missing = sense vision cache |
| superficie_construida_m2 | - | - | 1 | 5 | 5 missing = sense vision cache |
| superficie_parcela_m2 | 1 | - | 1 | 5 | 5 missing = sense vision cache |
| expedient | 3 | 3 | 1 | - | |
| municipality | 2 | 4 | 1 | - | Normalitzacio (caps, provincia) |
| radon_zone | 6 | - | 1 | - | Alcoletge: wrong |

### Variables completament OK

| Variable | MATCH | CLOSE | Nota |
|----------|-------|-------|------|
| sulfate_classification | 4 | - | +1 NOT_EXT (sense lab) |
| sulfate_mg_kg | 4 | - | +1 NOT_EXT |
| sulfate_baumann | 2 | 2 | +3 NOT_EXT |
| sulfate_level_name | 3 | - | +1 MISMATCH (Linyola "2on" vs default "1er") |
| spt_test_id | 2 | - | +2 NOT_EXT |
| spt_location | 2 | - | +2 NOT_EXT |
| spt_depth_range | 1 | - | +1 MISMATCH, +2 NOT_EXT |
| radon_zone | 6 | - | 1 MISMATCH |
| cte_edificacio | 2 | - | (quan building_type es correcte) |

---

## 8. Analisi per Font de Document

### 8.1 Planol (architect_plan) — IMPACTE MAXIM

**Variables que depenen del planol:** architect_name, building_type, num_floors, superficie_parcela_m2, superficie_construida_m2, building_height_m, client_name (promotor al caixeti)

| Projecte | Planol? | Vision cache? | architect_name | building_type | num_floors | superficie |
|----------|---------|--------------|----------------|---------------|------------|-----------|
| Bell-Lloc | A.01.pdf | SI | MATCH | MISMATCH (article) | MATCH | MATCH |
| Castellar | pla.pdf | SI | NOT_EXT | MISMATCH | NOT_EXT | NOT_EXT |
| Rubi | ? | SI | MISMATCH | CLOSE | NOT_EXT | NOT_EXT |
| Linyola | Punts Sondeig.pdf | SI (parcial) | NOT_EXT | CLOSE | NOT_EXT | NOT_EXT |
| Alcoletge | A.01.pdf | **NO** | NOT_EXT | MISMATCH | NOT_EXT | NOT_EXT |
| Vilanova | 1.0.pdf (GAP) | **NO** | NOT_EXT | CLOSE | NOT_EXT | NOT_EXT |
| Anciles | A01_TIPOL.pdf (GAP) | **NO** | NOT_EXT | MISMATCH | MISMATCH | NOT_EXT |

**Conclusio:** Bell-Lloc es l'unic projecte on la visio del planol funciona be (te cache recent i planol estandard amb caixeti). Per la resta, o no hi ha cache, o el planol te un format diferent que la visio no extreu.

**Variacions de format detectades:**
- Bell-Lloc: A.01.pdf amb caixeti estandard → vision v1 funciona
- Castellar: "pla.pdf" — format diferent, vision extreu poc
- Linyola: "Punts de Sondeig_Silvia_Jaume" — no es un planol tradicional, es un esbos de punts
- Alcoletge: A.01.pdf pero sense cache (cal executar vision)
- Vilanova: "1.0.pdf" en subcarpeta numerica (SmartScan no l'arriba)
- Anciles: "A01_TIPOL.pdf" en subcarpeta numerica (GAP)

### 8.2 DADES.xls (dades_camp_excel) — FORMAT ESTABLE

G3 usa la mateixa plantilla per a tots els projectes. L'extraccio funciona be per a contacte/adreça pero el camp "CLIENT" sol tenir el contacte (arquitecte), no el promotor.

**Problema:** No es de format — es que el camp "CLIENT" de DADES.xls NO conte el client real en molts casos.

### 8.3 Lab reports (GTL) — 9 VARIABLES NEVER EXTRACTED

Els informes de laboratori (4687-GTL-25.pdf, 4672-GTL-25.pdf, etc.) contenen totes les variables lab_*. Actualment nomes s'extreu sulfate_mg_kg via PyMuPDF. Cal:
- Extreure company, depth, sample, tests de la portada del GTL
- Possiblement 2 formats: TPS (Lleida) i altres labs

### 8.4 Sondeig (vision) — FORMAT ESTABLE

Eva fa les fitxes de camp a ma. El format es consistent (es la seva lletra). Les variacions son menors. La visio funciona quan hi ha cache.

### 8.5 DPSH (vision) — FORMAT ESTABLE

Igual que sondeig, fitxa de camp d'Eva. Format consistent.

### 8.6 Emails (.msg) — NO FORMAT-ABLE

Cada email es diferent. L'extraccio LLM (Groq) es l'eina correcta aqui, no formats.

---

## 9. Cascades de Fallada

```
Planol vision falla (5/7 projectes)
    ↓
building_type falla (4/7)
    ↓
cte_edificacio falla (4/7)
    ↓
(building_type incorrecte → CTE classificacio incorrecta)

Planol vision falla
    ↓
num_floors NOT_EXTRACTED (4/7)
    ↓
cte_edificacio potencialment incorrecte

Planol vision falla
    ↓
superficie NOT_EXTRACTED (5/7)
    ↓
(no impacte directe en altres variables)

B, Df = defaults (sense wizard)
    ↓
qa_value MISMATCH (7/7)
    ↓
settlement MISMATCH (7/7)
```

---

## 10. Prioritats per Block 6

### Alta prioritat (impacte en cascada)

1. **Refrescar vision caches** per als 7 projectes (prerequisit)
2. **Planol vision prompts** — adaptar per format variant (Bell-Lloc funciona, la resta no)
3. **Lab report extraction** — 9 variables "never extracted" per a tots els projectes

### Mitjana prioritat

4. **client_name** — identificar font correcta (email? planol? acceptacio?)
5. **building_type post-processing** — afegir article, quantitat, pluralitzar
6. **municipality normalization** — title case, strip provincia

### Baixa prioritat (limitacions del sistema)

7. **adjacent_*_fmt** — Cadastre vs camp (no es pot resoldre sense Street View)
8. **qa_value/settlement** — necessita B, Df del wizard (no automatitzable)
9. **site_description** — narrativa d'Eva (no automatitzable)

---

## 11. Accions Immediates

1. **Refrescar vision caches** — Executar vision per als 7 projectes amb prompts actuals
2. **Re-executar diagnostic** — Mesurar impacte del refresh
3. **Analitzar variacions de planol** — Documentar format variants per projecte
4. **Crear format_v2 si necessari** — Per a planols que no s'extreuen be
5. **Extreure lab_* variables** — Del GTL report PDF

---

*Document generat automaticament. Re-executar diagnostic per actualitzar metriques.*
