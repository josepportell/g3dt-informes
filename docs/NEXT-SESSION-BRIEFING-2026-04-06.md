# Next Session Briefing — Pipeline Improvement Continuation

**Data:** 2026-04-06
**Branca:** `feature/concept-format-separation`
**Sessio anterior:** Blocks 0-5 implemented + Block 6 audit + vision refresh
**Proper objectiu:** P1-P4 fixes (building_type, planol wiring, lab extraction, narrative templates)

---

## 1. On Som (Estat Actual)

### Blocks completats
- **Block 0:** Diagnostic instrumentation (phases, "correct exists?", calc trace, --classify)
- **Block 1:** Per-concept priorities in competition.py + FileMiner override logic
- **Block 2:** Adjacent formatting (bilingual CA/ES) — `automation/adjacent_formatter.py`
- **Block 3:** Geotech calc fix (N20→Nb for Terzaghi-Peck/Schmertmann)
- **Block 4:** Data mappings (SPT from sondeig, sulfate classification, num_floors)
- **Block 5:** Municipal lookups (CTE, seismic, radon) — `automation/municipal_lookups.py`
- **Block 6 parcial:** Audit + vision refresh for all 7 projects (2026-04-06)

### Blocks pendents
- **Block 6 resta:** Format-aware extraction (vision prompts, format variants, building_type post-processing)
- **Block 7:** Narrative templates + lab extraction

### Metriques actuals (post vision refresh)
```
Total: 281 var-comparisons
  51 match (18.1%)
  16 close (5.7%)
  88 mismatch (31.3%)
  126 not_extracted (44.8%)
Match+Close rate: 43.2% (of 155 compared)
```

### Evolucio
| Moment | Match+Close rate | MATCH | CLOSE | MISMATCH | NOT_EXT |
|--------|-----------------|-------|-------|----------|---------|
| Baseline (pre-blocks) | 29.3% | ~21 | ~8 | ~70 | ~182 |
| Post Blocks 0-5 | 41.5% | 46 | 15 | 86 | 134 |
| Post vision refresh | **43.2%** | **51** | **16** | **88** | **126** |

---

## 2. Prioritats (que fer ara)

| Priority | Issue | Count | Fix | Impact |
|----------|-------|-------|-----|--------|
| **P1** | building_type post-processing | 6 MISMATCH | Article + quantity from comanda_lab | Fixes 6 + cascades to 4 cte_edificacio |
| **P2** | Wire planol vision → pipeline | 5+4 MISMATCH | architect_name + client_name from planol JSONs | Fixes ~9 MISMATCH |
| **P3** | Lab report extraction | 63 NOT_EXT | Extract lab_* from GTL PDF (9 vars × 7 projects) | -63 NOT_EXTRACTED |
| **P4** | Narrative templates | 28 NOT_EXT | Build sentences from existing data | -28 NOT_EXTRACTED |
| **P5** | Adjacents enrichment | 26 MISMATCH | Street View / better Cadastre | Future |
| **P6** | Minor fixes | ~15 | Municipality normalization, dates, SPT edge cases | Incremental |
| -- | CALC (qa/settlement) | 15 MISMATCH | Needs wizard B/Df | Accept |
| -- | NARRATIVE (site_desc) | 7 MISMATCH | Needs field observation | Accept |

**Recomanacio:** Start amb P3 (lab extraction, 63 NOT_EXT — highest volume). P1+P2 son rapides i es poden llançar en paral·lel.

---

## 3. Detall per Prioritat

### P1: building_type post-processing (6 MISMATCH)

**Problema:** Pipeline extreu "habitatge unifamiliar aillat" pero Eva escriu "un habitatge unifamiliar" o "3 habitatges unifamiliars adossats".

**Causa:** Falta article ("un/una/l'"), quantitat (de comanda_lab "CONSTR 3 HAB UNIF"), i de vegades redaccio diferent.

**Fix:** Post-processament a `web/wizard_service.py` despres de resoldre building_type:
1. Extreure quantitat de comanda_lab (regex "CONSTR N HAB")
2. Afegir article catala/castella
3. Pluralitzar si quantitat > 1

**Cascada:** cte_edificacio falla per a 4 projectes perque building_type es incorrecte.

**Projectes afectats:** Castellar, Bell-Lloc, Linyola, Alcoletge, Vilanova, Anciles.

### P2: Wire planol vision data → pipeline (5+4 MISMATCH)

**Problema:** planol_extracted.json te promotor/architect/company pero no arriba als prefills per a tots els projectes.

**Causa probable:** El pipeline nomes llegeix planol_extracted.json a `_merge_prefills()` per a uns quants camps (street_address, num_floors, superficie). architect_name i client_name del planol no es mapegen.

**Fix:** A `web/wizard_service.py` `_merge_prefills()`, afegir mapping de:
- `planol.architect_data.architect` → `architect_name` (source: planol_vision)
- `planol.architect_data.architect_company` → `architect_company`
- `planol.architect_data.promotor` o `client_name` → `client_name` (source: planol_vision)

**Fitxers a revisar:**
- `web/wizard_service.py` — `_merge_prefills()` i `_load_planol()` (si existeix)
- Buscar: `planol_extracted` al codi per veure que es llegeix

### P3: Lab report extraction (63 NOT_EXTRACTED)

**Problema:** 9 variables lab_* (× 7 projectes = 63) mai s'extreuen. Tota la info es al GTL report PDF.

**Variables:**
- `lab_field_company` — nom de l'empresa de camp (ex: "TPS PROSPECCIÓ DEL SUBSÒL SL")
- `lab_testing_company` — nom del laboratori (pot ser el mateix)
- `lab_field_description` — descripcio del servei de camp
- `lab_testing_description` — descripcio del servei de laboratori
- `lab_location` — punt de mostreig (ex: "Punt: S-1")
- `lab_sample_id` — identificador de mostra (ex: "Mostra: SPT-1")
- `lab_depth` — profunditat de mostreig (ex: "-1.0 a -1.6")
- `lab_tests_text` — llistat d'assaigs (ex: "1 assaig de contingut en sulfats")
- `access_street` — carrer d'acces (narrativa composada)

**Font:** Informes GTL (ex: `4687-GTL-25 Castellar del Vallés.pdf`, `4677-GTL-25 Bell-Lloc d'Urgell.pdf`). Ja tenen rol `gtl_report` a SmartScan.

**Fix:** Crear extractor de text per a GTL PDFs (PyMuPDF text layer) o visio si cal. Les primeres pagines tenen portada amb empresa, adreça, i la pagina de resultats te punt, mostra, profunditat, assaigs.

**Possibles 2 formats:** TPS (laboratori de Lleida, usat a la majoria) i altres labs.

### P4: Narrative templates (28 NOT_EXTRACTED)

**Variables:**
- `building_structure_desc` — "en planta baixa" / "sense nivell de soterrani" → Template des de num_floors
- `location_sentence` — "entre el Carrer X i el Carrer Y" → Template des d'adjacents + street_address
- `num_dpsh_tests` — "2 assaigs de penetracio..." → Template des de dpsh_data.tests count
- `site_condition` — "Degut a que es tracta d'un solar pla..." → Template des de is_sloped + ICGC
- `table_dpsh_range` — "3, 4 i 5" → Llista de numeros de taula (convencio fixa)

**Fix:** Afegir templates a `web/wizard_service.py` que componguin frases des de dades existents.

---

## 4. MISMATCH Classification Detallada (88 total)

```
CALC         (15) — qa/settlement/k30 (necessita wizard B/Df)
EXTRACTION   (64) — cap senyal correcte (format/extraccio)
NARRATIVE    (7)  — site_description (Eva escriu del camp)
PRIORITY     (1)  — valor correcte existeix com a alternativa
FORMAT       (1)  — dada correcta, presentacio incorrecta
```

### Detall dels 64 EXTRACTION:
- 26 adjacents (Cadastre vs camp)
- 6 building_type (post-processing)
- 5 architect_name (planol wiring)
- 4 client_name (planol wiring)
- 4 cte_edificacio (cascada de building_type)
- 4 cte_sol (cascada de soil classification)
- 3 field_work_dates_text (format de dates)
- 3 superficie_construida_m2 (visio no extreu)
- 2 radon_zone (lookup data gap)
- 2 seismic_ab_text (format text)
- 2 spt_lithology (wording diferent)
- 1 spt_n30 (Bell-Lloc ambiguitat N=54)
- 1 num_floors (Anciles complex)
- 1 expedient (format)
- 1 municipality (normalization)
- 1 sulfate_level_name (Linyola "2on" vs default)
- 2 superficie_parcela_m2 (visio)
- 2 spt_depth_range (mapping)

---

## 5. Fitxers Clau per Llegir

### Diagnostic i metriques
- `docs/diagnostic-post-refresh-2026-04-06.txt` — Full diagnostic output (734 lines)
- `docs/AUDIT-FORMAT-COVERAGE-2026-04-06.md` — Format coverage audit
- `docs/VISION-REFRESH-2026-04-06.md` — Vision refresh results per project

### Plans i arquitectura
- `docs/PLA-DE-MILLORA-REVISED.md` — Pla amb 7 blocks (on som: Block 6)
- `docs/GUIA-SISTEMA-EXTRACCIO.md` — Com funciona el pipeline complet
- `docs/ARQUITECTURA-CONCEPT-FORMAT-SCHEMAS.md` — Separacio concepte-format
- `docs/smartscan/01-INVENTARI-FITXERS.md` — Inventari de fitxers per projecte

### Codi principal a tocar
- `web/wizard_service.py` — `_merge_prefills()`, `_compute_mapping_prefills()`, `_compute_lookup_prefills()`, `_compute_geotech_prefills()`. Aqui es on s'afegeixen els nous prefills (P1, P2, P4).
- `automation/auto_extractor.py` — Phase 0.3 FileMiner, Phase 0.5 extraction
- `automation/fileminer/competition.py` — Per-concept priorities (ja implementat Block 1)
- `automation/adjacent_formatter.py` — Adjacent sentence formatting (Block 2)
- `automation/municipal_lookups.py` — CTE/seismic/radon (Block 5)
- `scripts/diagnostic_trace.py` — Diagnostic amb instrumentacio (Block 0)

### Eva's reference values
- `reference-material/{project}/validation/eva_reference_values.json` — Ground truth per projecte
- `reference-material/{project}/validation/planol_extracted.json` — Vision cache planol (FRESH 2026-04-06)
- `reference-material/{project}/validation/dpsh_extracted.json` — Vision cache DPSH (FRESH)
- `reference-material/{project}/validation/sondeig_extracted.json` — Vision cache sondeig (FRESH)
- `reference-material/{project}/validation/docs_extracted.json` — Docs intel·ligent cache

### Schemas
- `schemas/concepts/report_variables.yaml` — 53 conceptes amb prioritats per-font
- `schemas/formats/*.yaml` — 8 formats del sistema
- `schemas/formats/learned/` — Formats apresos per Eva

### Tests
- `tests/` — 197 tests (tots passen). Executar amb: `.venv/bin/python -m pytest tests/ -x -q` (timeout 600s, tarden ~4min)

---

## 6. Projectes de Referencia

| ID | Nom | Planol? | Sondeig? | Lab? | Idioma |
|----|-----|---------|----------|------|--------|
| 4001612 | Bell-Lloc | SI (A.01, caixeti + taula) | SI (S-1) | SI (GTL) | CA |
| 3001621 | Castellar | NO | SI (S-1, roca) | SI (GTL) | CA |
| 3001631 | Rubi | SI (WhatsApp cataleg) | NO | SI (GTL) | CA |
| 4001607 | Linyola | SI (Bunyesc, caixeti) | NO | SI (GTL) | CA |
| 4001670 | Alcoletge | SI (2 Graus, situacio) | NO | NO (?) | CA |
| 4001671 | Vilanova | SI (Rocar, emplacament) | NO | SI (?) | CA |
| 4001679 | Anciles | SI (tipologia 7 vivendes) | SI (S-1, S-2) | SI (?) | **ES** |

---

## 7. Comandes Utils

```bash
# Diagnostic complet
.venv/bin/python scripts/diagnostic_trace.py --all --classify

# Diagnostic un projecte
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --all

# Tests (timeout 600s!)
.venv/bin/python -m pytest tests/ -x -q

# Refresh visio un projecte
/g3dt-visio-projecte reference-material/4001612 BELL-LLOC --force

# Refresh visio tots
/g3dt-dev-refresh-vision --all

# Eva vs pipeline comparison
/g3dt-dev-eva-vs-pipeline
```

---

## 8. Decisions Importants Preses

1. **Per-concept priorities** actives a competition.py (Block 1). client_name: content_pdf puja a 35, pressupost baixa a 50.
2. **Adjacent formatting** bilingue CA/ES (Block 2). Adjacents formatted at prefill time, not report time.
3. **Nb (not N20)** per Terzaghi-Peck i Schmertmann Es (Block 3 fix).
4. **SPT N30 = blows[1]+blows[2]** (standard: middle two 15cm intervals).
5. **SmartScan ja escaneja subcarpetes numeriques** — el problema NO era SmartScan sino caches obsolets.
6. **Vision generic prompts** son adequats per DPSH/sondeig (format estable d'Eva). Les variacions son als planols d'arquitecte.
7. **DPSH Excel sempre es mes fiable** que visio per a valors N20.
8. **Format-aware vision prompts (Block 6.3)** diferit fins despres de P1-P4 fixes.

---

## 9. Proper Pas Suggerit

1. **Llegir** aquest document + `CLAUDE.md` del projecte
2. **Començar per P3** (lab extraction) — major volum, independent dels altres
3. **En paral·lel P1+P2** si possible (building_type + planol wiring)
4. **Despres P4** (narrative templates)
5. **Re-executar diagnostic** despres de cada bloc
6. **Actualitzar** `docs/AUDIT-FORMAT-COVERAGE-2026-04-06.md` amb noves metriques

---

*Document per a handoff de sessio. Llegir sencer abans de començar a implementar.*
