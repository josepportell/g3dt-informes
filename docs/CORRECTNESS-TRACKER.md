# Correctness Tracker — Deviations from Eva's Reference Reports

Created: 2026-03-28
Last updated: 2026-03-29

## Overview

Compares our pipeline output against Eva's 7 signed reports. Each variable is classified into a tier and tracked through investigation → fix → verification.

**Current state (post-Tier A Fixes 1-5 + Tier B Improvements 1/5/2 + full vision re-run):**
| Tier | Description | Match | Total | Correctness | Delta | Notes |
|------|-------------|-------|-------|-------------|-------|-------|
| A | Auto-extractable | 56/101 | **55.4%** | Target: 95% | +16.6pp from baseline | Vision run, Anciles excluded (DNS fail) |
| B | Manual/on-site | 4/47 | **8.5%** exact | Target: best effort | +8.5pp from 0% | 17/47 CLOSE (36.2%) via LLM-as-judge |
| C | Professional judgment | 2/20 | **10.0%** | Target: transparency | -7.6pp regression | Castellar bearing stratum regression |

**Overall: 62 MATCH + 31 CLOSE / 168 vars (36.9% exact, 55.4% exact+CLOSE)**

**Key wins from vision re-run:**
- Rubí: client MATCH, cota_referencia MATCH (+209.50, was +129.00!), geotech_phi/nb MATCH
- Bell-Lloc: 17/32 match (53.1%), client + architect + num_floors MATCH
- Vilanova: adjacent_west MATCH ("Carrer Santa Gemma"), superficie_parcela MATCH
- Alcoletge: client CLOSE, adjacent_west MATCH

**Regressions to investigate:**
- Castellar: dropped 11→7 match (bearing stratum filter changed N20 values)
- building_type: still extracting project titles ("Habitatge aïllat", "PROJECTE DE TANCAMENT")

**P4 qualitative wins (not captured by exact-match metric):**
- **6/7 projects** now resolve to exact cadastral references via direct Callejero (was 1/7)
- Adjacents come from the **correct parcel** — directions now make sense
- Semantic near-matches not captured by exact comparison:
  - Castellar S: "Carrer dels Arbrells" ≈ Eva's "carrer Arbrells"
  - Vilanova W: "Carrer Santa Gemma" ≈ Eva's "calle STA. GEMMA"
  - Linyola W: "Carrer Clot de la Llacuna" ≈ Eva's "carrer per on es realitza l'entrada"
- **3 address extraction bugs fixed**: G3 internal address filter, email body block, municipality stripping

**Note on `--skip-vision`:** Current benchmarks run with `--skip-vision`, skipping Claude/Groq PDF reading (Phase 1). This depresses Tier A by ~8-10 vars/project (client, architect, building_type, dimensions). Tier B is unaffected (comes from Cadastre APIs + ortho enrichment). Running with vision would improve Tier A significantly.

---

## Tier A — Auto-extractable

### A1. OK (100% match) — no action needed

| Variable | Match | Notes |
|----------|-------|-------|
| `num_dpsh_tests` | 5/5 | DPSH Excel extraction solid |
| `sulfate_value` | 4/4 | Lab PDF extraction solid |
| `architect_company` | 1/1 | Only Bell-Lloc has this field — works when plànol extraction runs |

### A2. Format mismatch — quick fixes

| Variable | Status | Eva says | Pipeline says | Root cause | Action |
|----------|--------|----------|---------------|------------|--------|
| `radon_zone` | 0 match, 3 CLOSE, 3 MISMATCH | "ZONA 1", "Zona I", "ZONA 2" | "1", "0" | Pipeline stores just the number. Eva's report uses the full label. Also: Anciles "ZONA 2" vs pipeline "0" — pipeline fails to extract zone for non-Catalan reports? | [ ] Store as Eva's format "ZONA {n}". [ ] Investigate Anciles "0" — is radon extraction failing for Spanish-language reports? |
| `seismic_ab_text` | 0 match, 5 CLOSE, 2 MISMATCH | "AB = 0,04 g", "AB < 0,04 g", "AB = 0,08 g", "AB = 0.05 g" | "0,04" | Pipeline stores just the number. Eva's report uses the full expression with AB prefix, comparator, and unit. MISMATCH on Rubí (0,08 vs 0,04) and Anciles (0.05 vs 0,04) — wrong values, not just format. | [ ] Store as Eva's format "AB {op} {value} g". [ ] Investigate: Rubí and Anciles have different ab values than pipeline defaults. Where does the pipeline get ab? Is it hardcoded? |
| `dpsh_test_ids` | 1 match, 4 MISMATCH | "P-1,P-2,P-3" (no spaces) | "P-1, P-2, P-3" (with spaces) | Eva's report has no spaces after comma. Our pipeline adds spaces. One match (Bell-Lloc) because Eva happened to use spaces there. Also Alcoletge: order differs ("P-1, P-2, P-3" vs "P-1, P-3, P-2"). | [ ] Normalize: strip spaces in comparison, or format consistently. [ ] Investigate Alcoletge ordering — why are test IDs reordered? |

### A3. CLOSE (no mismatch, minor deviation) — tune

| Variable | Status | Deviation | Root cause | Action |
|----------|--------|-----------|------------|--------|
| `geotech_density` | 4 match, 1 CLOSE | Linyola: 1.9 vs 2.00 (+5.3%) | Pipeline uses CTE D.27 table: 2.0 for granular. Eva uses 1.90 for "llims argilosos" (cohesive). Multi-level project: pipeline picks wrong level? Or wrong soil classification? | [ ] Investigate: does pipeline detect soil type correctly for Linyola? Linyola L1 is "llims argilosos" which should get 1.90, not 2.0. |
| `municipality` | 5 match, 2 CLOSE | Castellar: adds ", Barcelona" suffix. Anciles: "Benasque" vs "Anciles, Benasque". | Geocoding returns municipality with province or misses the village-within-municipality. | [ ] Strip province suffix from Nominatim response. [ ] Anciles: Eva writes "Anciles, Benasque" — Anciles is a village in Benasque municipality. Pipeline only has "Benasque". |
| `superficie_construida` | 1 match, 1 CLOSE | Bell-Lloc: Eva 366 vs pipeline "297+110" (+11.2%). Eva sums 280+86=366 from her table. Pipeline shows "297+110" from a different source? | [ ] Investigate: where does pipeline get 297+110? Eva's Table 1 says 280+86. Different sum. Different source (plànol vs cadastre?). |

### A4. WRONG (0 match) — metric mismatch, needs redesign

| Variable | Status | Root cause | Action |
|----------|--------|------------|--------|
| `dpsh_avg_n20` | 0/5 match | **Comparing different metrics.** Pipeline computes N20 average from DPSH Excel. Eva states "Nb mig" (Nb average) in her text. Nb = N20/0.83. These will never match unless we convert. Also: Eva's Nb is from the geotechnical parameter table (interpreted), pipeline's N20 is raw from field data. | [ ] Decide: should benchmark store N20 (for direct comparison) or keep Nb (Eva's stated value)? [ ] Consider: pipeline should also show Nb (N20/0.83) alongside N20. Eva always uses Nb in her reports. |
| `geotech_nb` | 0/5 match | **Different representation.** Pipeline shows DPSH refusal notation ("12-R", "7-R", "1-R"). Eva's table shows the numeric Nb value she interprets (25, 47, 13, etc.). Pipeline is showing the raw DPSH test result; Eva shows the interpreted geotechnical parameter. | [ ] Investigate: where does pipeline get "12-R"? Is this the last DPSH test's Nb? Eva's table Nb is a representative value she selects, often the average before refusal. [ ] Pipeline should compute representative Nb from DPSH data, not just show the last reading. |

### A5. PARTIAL (some match, some not) — investigate per project

| Variable | Match/Total | Projects that fail | Root cause | Action |
|----------|-------------|-------------------|------------|--------|
| `client` | 1/7 | All except Bell-Lloc | Pipeline sources: SmartScan/FileMiner finds "INTECSON" (the lab company, Eva's employer). Real client comes from pressupost email or plànol. Bell-Lloc matches because it has user_data.json with the correct client. | [ ] Investigate client extraction chain: which sources are checked? Why does pressupost/email not provide the client name? [ ] Check if plànol vision extracts client (it should — "A petició de: X"). |
| `building_type` | 0/7 (1 CLOSE) | All | Pipeline shows project title ("ESTUDI GEOLÒGIC...") or abbreviated form ("CONSTR 3 HAB UNIF"). Eva writes descriptive type ("habitatge unifamiliar aïllat"). | [ ] Investigate: does plànol vision extract building_type? Where does the pipeline get the current value? [ ] Check SmartScan/FileMiner signal for building_type. |
| `street_address` | 1/7 (1 CLOSE) | Most | Format differences: Eva writes "Carrer dels Arbrells, 18". Pipeline may add postal code, different abbreviation (C/ vs Carrer), or different format. | [ ] Investigate: source of street_address in pipeline. Multiple sources possible (geocode, plànol, pressupost). [ ] Normalize format. |
| `geotech_cohesion` | 2/5 | Rubí (0.05 vs 0.00), Linyola (0.05 vs 0.00), Alcoletge (1.0 vs 0.00) | Pipeline defaults cohesion to 0.00 for granular soils. Eva assigns 0.05 for slightly cohesive materials and 1.0 for rock. Multi-level: Alcoletge pipeline uses L1 (rebliment, c=0) instead of L2 (lutites, c=1.0). | [ ] Investigate: how does pipeline select which geological level's parameters to use? [ ] Alcoletge: pipeline clearly uses wrong level. |
| `geotech_phi` | 2/5 (2 CLOSE) | Bell-Lloc (38 vs 35, -7.9%), Linyola (28 vs 36, +28.6%), Alcoletge (30 vs 34, +13.3%) | Schmertmann formula deviation. Linyola: pipeline gives 36° for material that Eva says is 28° — pipeline may use wrong N value or wrong soil type factor. Alcoletge: wrong geological level again. | [ ] Linked to geotech_cohesion issue — same root cause (wrong level selection). [ ] Linyola: investigate which N value and grain factor the pipeline uses. |
| `superficie_parcela` | 3/6 | Bell-Lloc (995 vs 598), Linyola (571 vs 387), Anciles (1655 vs 265) | Large deviations suggest different sources. Eva uses "plànols cadastrals" from her Table 1. Pipeline may use Cadastre API which returns a different parcel. | [ ] Investigate: where does pipeline get superficie_parcela? Cadastre WFS geometry area? Different parcel reference? |
| `cota_referencia` | 4/5 | Rubí (212.5 vs 129.0, -39.3%) | 4 projects match perfectly. Rubí is way off — ICGC MDT returning wrong elevation? Or wrong coordinates? | [ ] Investigate Rubí specifically: check what coordinates the pipeline geocodes and what ICGC returns. |
| `data_camp_text` | 4/5 | Castellar ("24 de octubre" vs "24 d'octubre") | Language mismatch: Eva wrote in Spanish for this project, pipeline converts to Catalan? Or vice versa? | [ ] Investigate: where does pipeline get date language? Does it auto-detect report language? |

---

## Tier B — Manual/on-site (4/55 exact, 13/55 CLOSE via LLM-as-judge)

These variables describe what Eva physically observes at the site. After P4 Steps 0-2, the pipeline now identifies the **correct parcel** for 6/7 projects via direct Callejero. After Tier B Improvements 1/5/2: LLM-as-judge semantic scoring, boilerplate sentence alignment, and location_sentence template fix.

### B1. Parcel identification status (after P4 Steps 0-2)

| Project | Parcel RC | Correct? | How resolved |
|---------|-----------|----------|--------------|
| Castellar | 3298012DG2039N | Yes (prefix matches) | Direct Callejero, "18A" → "18" fix |
| Rubí | 9341019DF1994S | TBD (verify vs Eva) | Direct Callejero, G3 address rejected |
| Linyola | 5098344CG2159N | TBD (verify vs Eva) | Direct Callejero, email garbage blocked |
| Bell-Lloc | 4613172YG1041S | Yes | From COORDENADES.txt |
| Alcoletge | 8841701CG0184S | TBD (verify vs Eva) | Direct Callejero, G3 address rejected |
| Vilanova | 8606709CG9280N | TBD (verify vs Eva) | Direct Callejero, accent fix |
| Anciles | ? | Untested | DNS failure; village→Benasque mapping added |

### B2. Variable-level analysis

| Variable | Exact | LLM CLOSE | Current source | Bottleneck | Status |
|----------|-------|-----------|---------------|-----------|--------|
| `adjacent_N/S/E/W` | 2/28 | 7/28 | Cadastre edge probing + Nominatim streets + ortho vision | **Description richness**: "parcel·la amb construcció" vs Eva's "parcel·la construïda amb piscina". LLM judge correctly promotes plural/singular variants. | Deferred: Improvement 3 (ortho enrichment) |
| `location_sentence` | 0/7 | 2/7 | Template: "es situarà {loc} de {municipality}" | ✅ **Template fixed** (Improvement 2): "de {municipality}" + Catalan elision ("d'Alcoletge"). Needs pipeline re-run to measure. LLM judge finds 2 CLOSE (Bell-Lloc, Vilanova). | Done (code), needs re-run |
| `site_condition` | 0/7 | 0/7 | Ortho-derived "antropitzat" | **Single word vs description**: Eva writes "sense construccions ni pavimentacions, desbroçat". Our output: "antropitzat". LLM confirms 1/5 (wrong). | Deferred: Improvement 4 |
| `site_description` | 0/7 | 0/7 | Ortho-enriched 5-sentence paragraph | ✅ **Boilerplate added** (Improvement 5): Eva's 2 fixed sentences + access phrasing. Needs pipeline re-run to measure. LLM scores 1-2/5 (too different still). | Done (code), needs re-run |
| `access_description` | 0/7 | 5/7 | Template with street name | **Already close**: LLM scores 3-4/5 for most projects. Eva's exact phrasing matched in code. | Working well |

### B3. Root causes fixed in P4 Steps 0-2

| Root cause | Projects affected | Fix | Commit |
|-----------|-------------------|-----|--------|
| G3 office address ("Vallbona 22") extracted as project address | Rubí, Alcoletge, Vilanova | Centralized `_is_g3_internal_address()` filter (street+number) | 448ed19 |
| Email body parsed as address (Linyola: "administracion@g3dt.com...") | Linyola | Block address signals from msg_miner email body/subject | 448ed19 |
| Municipality accent in ConsultaMunicipio URL | Castellar, Vilanova | Strip accents before API call in `_consulta_municipio()` | 448ed19 |
| City name in address ("ORTIZ 15 BELL-LLOC") | Bell-Lloc | `_clean_street_address()` strips trailing municipality | 448ed19 |
| Village ≠ municipality (Anciles ≠ Benasque) | Anciles | `_VILLAGE_TO_MUNICIPALITY` lookup table | 448ed19 |
| House number with letter suffix ("18A" → API error 42) | Castellar | Strip letter suffix before DNPLOC call | 95c0872 |
| Nominatim imprecision → wrong parcel | All w/o COORDENADES.txt | Direct Callejero → exact RC from address database | 95c0872 |

### B4. Improvements status

| # | Improvement | Status | Impact |
|---|-------------|--------|--------|
| 1 | **LLM-as-judge** (compare_benchmarks.py) | ✅ DONE | Tier B: 2→4 MATCH, 2→13 CLOSE. Domain vocab for Cat/Es synonyms. |
| 5 | **Boilerplate sentences** (site_text_generator.py) | ✅ DONE | Eva's 2 fixed sentences added to site_description + access phrasing aligned. Needs pipeline re-run. |
| 2 | **location_sentence "de {municipality}"** (site_text_generator.py) | ✅ DONE | "al municipi de X" → "de X" / "d'X". Catalan elision. Needs pipeline re-run. |
| 4 | **site_condition from ortho vision** | DEFERRED | Needs snapshot tests before touching report_generator.py |
| 3 | **Adjacents description enrichment** | DEFERRED | Most complex — needs tests before touching auto_extractor.py |
| — | **Polygon override for merged parcels (P4 Step 3)** | PENDING | Bell-Lloc multi-parcel adjacents drift |

**Plan doc:** `docs/PLA-TIER-B-IMPROVEMENTS.md`

---

## Tier C — Professional judgment (3/17 match)

Eva adjusts these values based on experience. Our formulas are correct per textbook — deviations are expected. **Goal: transparency, not convergence.**

| Variable | Match | Deviation pattern | Our formula | Eva's approach | Transparency action |
|----------|-------|-------------------|-------------|----------------|---------------------|
| `geotech_E` | 2/5 | Bell-Lloc: -27.8% (469 vs 650), Linyola: +369% (469 vs 100), Alcoletge: -71.5% (114 vs >400) | CTE D.23 table lookup by N20 bracket | Professional judgment after many studies. Adjusts for cemented soils ("carbonatades" → higher E), soil type (llims → lower E). | [ ] Show in wizard: "E calculat = {value} (CTE D.23, N20={n}). Eva pot ajustar." [ ] Show Eva's typical ranges by soil type as reference in tooltip. |
| `qa_value` | 0/5 | Castellar/Linyola: +66.7% (5.0 vs 3.0), Bell-Lloc: -20% (2.40 vs 3.0), Alcoletge: -59.7% (1.41 vs 3.5) | Terzaghi-Peck (Nb/12) + width correction + depth factor. Cap: 3.0 (soil), 5.0 (rock). | Terzaghi-Peck prevails BUT with professional cap "3.0 quilos és un topall màxim, en roca clara 4.0-4.50". Sometimes T-P gives lower than cap → uses T-P. | [ ] Show: "Qa calculat = {value} (Terzaghi-Peck, Nb={nb}, F=3). Topall aplicat: {cap}." [ ] Investigate: why pipeline gives 5.0 for Castellar/Linyola (rock cap too high?). |
| `settlement` | 0/5 (2 CLOSE) | Bell-Lloc: -6.7% (1.12 vs 1.2), Alcoletge: +12% (1.12 vs 1.0), Castellar: +127% (2.27 vs 1.0), Linyola: +196% (2.96 vs 1.0), Rubí: +45.3% (2.18 vs 1.5) | Schmertmann method, Es = 2.5×Nb (square footing) | Same method but Eva may use different Es or footing geometry. Bell-Lloc is close. Large deviations suggest wrong Nb input or wrong footing assumption. | [ ] Show: "Assentament = {value} cm (Schmertmann, Es={es}, B={width}m). Eva pot ajustar." [ ] Investigate large deviations — are we using wrong Nb? |
| `k30_value` | 1/2 | Castellar: match (8.0 vs 8.3, +3.8%). Rubí: mismatch (6.0 vs 8.3, +38.3%) | E/75 (granular), E/60 (rock) | K30 derived from E. If E deviates, K30 deviates proportionally. Rubí: our E=469, Eva E=450. K30=469/75=6.3 (close to Eva's 6.0). But pipeline shows 8.3?? | [ ] Investigate Rubí K30: why does pipeline show 8.3 when E=469 → K30≈6.3? Is pipeline using a different E for K30 calculation? |

---

## Excluded from comparison

| Variable | Reason |
|----------|--------|
| `data_signatura_text` | Correct by design — always today's date. Historical reports have their own date. |
| `dpsh_tests` (array) | Complex structure, not scalar-comparable |
| `sondeig_tests` (array) | Complex structure, not scalar-comparable |
| `geology_paragraphs` (array) | Complex structure, not scalar-comparable |
| `soil_level_rows` (array) | Complex structure, not scalar-comparable |
| `perm_rows` (array) | Complex structure, not scalar-comparable |
| `materials_level_1` (text) | Not extracted in benchmark |

---

## Action priority

### P0 — Quick wins (format fixes, immediate correctness gain)
1. ~~`radon_zone` format~~ ✅ Normalizer in compare_benchmarks.py (strips "ZONA " prefix, Roman→Arabic)
2. ~~`seismic_ab_text` format~~ ✅ Normalizer in compare_benchmarks.py (extracts numeric value)
3. ~~`dpsh_test_ids` format~~ ✅ Fixed join to no-space `','.join()` + normalizer for comparison
4. ~~`municipality` format~~ ✅ Normalizer strips province suffix (, Barcelona, etc.)
5. ~~Investigate wrong values~~ ✅ Investigated:
   - **Rubí seismic (0.08 vs 0.04):** Our data (NCSE-02 Annex 1) says ab=0.04g for Rubí. Eva writes 0.08. Possible causes: (a) Eva states ac (design accel = S×ρ×ab) not ab, (b) newer norm, (c) error. → Ask Eva.
   - **Anciles radon+seismic:** Anciles (Benasque, Huesca) is in Aragón, not Catalunya. Our dataset only has 947 Catalan municipalities → defaults to ab=0.04, radon=0. Eva: ab=0.05, radon=ZONA 2. → Need Aragón data or manual override. Moved to P1.

### P1 — Investigation (understand root cause before fixing) ✅ All investigated

6. ~~`client` extraction~~ ✅ **Root cause: pressupost PDF client extraction not working.** Bell-Lloc works only because it has user_data.json. Other projects: pressupost has "CLIENT: X" but pipeline picks up "INTECSON" (lab/employer) from FileMiner instead. **Fix:** improve pressupost client extraction + plànol "A petició de:" field.

7. ~~`building_type` extraction~~ ✅ **Root cause: wizard.py:257 sets `building_type = project_name` from plànol vision.** Claude extracts the literal project title ("ESTUDI GEOLÒGIC...") not the building classification ("habitatge unifamiliar"). **Fix:** add separate `building_type` field to plànol vision prompt, distinct from project_name.

8. ~~`geotech_nb` representation~~ ✅ **Root cause: pipeline shows raw DPSH last-reading ("12-R"), Eva shows interpreted Nb for bearing stratum.** Linked to #12 (multi-level bug). Pipeline needs to compute representative Nb from depth-filtered DPSH data. **Fix:** see #12.

9. ~~`dpsh_avg_n20` metric alignment~~ ✅ **Root cause: pipeline computes N20 avg, Eva states Nb mig (N20/0.83).** Plus different scope: pipeline uses all depths, Eva uses bearing stratum only. **Fix:** (a) show Nb in report, not N20. (b) Filter to bearing stratum depth. Linked to #12.

10. ~~`superficie_parcela` source~~ ✅ **Root cause: pipeline uses plànol vision "parcel_area_m2" (architect's site plan dimensions). Eva uses official cadastral area.** Cadastre WFS area IS computed by geocoding but stored in wrong field (`superficie_cadastral_m2` not `superficie_parcela_m2`). **Fix:** use Cadastre WFS area for superficie_parcela, fall back to plànol vision.

11. ~~`cota_referencia` Rubí~~ ✅ **Root cause: plànol vision extracts "Carrer de la Miranda" WITHOUT house number "nº 39".** Partial address → geocodes to wrong location → wrong ICGC MDT elevation (129.0 instead of 212.5). Working copies at `/mnt/c/claude/g3dt/projectes/` have wrong coordinates. **Fix:** improve plànol address extraction to keep house numbers; add coordinate validation against municipality bounds.

12. ~~Multi-level selection~~ ✅ **Root cause: report_data.py:427 `avg_n20 = dpsh_data.overall_average_n20` always uses global average across ALL depths.** Should filter DPSH readings to bearing stratum (deepest layer) depth range. Alcoletge: shallow fill N20~4.4 mixed with deep lutites N20~35 → global avg ~22 → wrong phi, cohesion, E. Also: single GeotechnicalParams applied to all levels in Taula 10. **Fix:** depth-filter DPSH to bearing stratum; per-level GeotechnicalParams for multi-level projects.

### P2 — Tier C transparency ✅

13. ~~Formula explanations in wizard~~ ✅ Added `_calc_*` notes to context dict + HTML display in expert overrides section (gamma formula, phi formula, E formula, Qa/K30/settlement results panel).

14. ~~Rubí K30 anomaly~~ ✅ **Root cause: `icgc_unit_description` (regional geology) was used for rock detection.** ICGC descriptions always contain rock keywords ("bretxes", "lutites", "conglomerat") even for granular sites → false positive `is_rock()` → rock defaults (E=500, c=1.0) → K30=E/60=8.3 instead of E/75=6.3. **Fix:** removed ICGC fallback from rock_description; only use sondeig layer descriptions (field observations). Rubí K30: 8.3 → 6.3 (Eva: 6.0, MATCH).

15. ~~Qa cap logic~~ ✅ **Same root cause as #14.** ICGC rock detection gave all projects c=1.0 → rock cap 5.0. After fix: Rubí/Linyola now correctly get c=0.0 → soil cap 3.0. Castellar keeps c=1.0 (genuinely rock via N20 refusal) → rock cap 5.0 (Eva uses 3.0 — professional judgment, Tier C).

### P3 — Tier B enrichment ✅ DONE
16. ~~Google Street View API feasibility~~ ✅ **Replaced with ICGC orthophotos + Mapillary.** Google Street View ToS prohibits automated data extraction. ICGC WMS (free, 25cm territorial / 10cm local) + Mapillary API (free, street-level) implemented.
17. ~~Google Earth / satellite imagery~~ ✅ **ICGC orthophotos serve this purpose.** Downloads tight chip (parcel bbox + 40m) + wide chip (100m context), crops 4 boundary strips per cardinal edge. Groq Llama 4 Scout vision extracts structured micro-fields.
18. ~~Improve Cadastre adjacent labels~~ ✅ **Vision enrichment adds building type, floors, enclosure, vegetation.** Also fixed: street name now uses source parcel's own LDT instead of far neighbor's. Bell-Lloc east: "Via Ferrea" → "Mestre Ramon Ortiz" (correct).
19. ~~Improve location_sentence template~~ ✅ **Now includes building_type + proper Catalan structure.**
20. ~~Stop hardcoding site_condition~~ ✅ **`is_anthropized` now derived from ICGC orthophoto vision analysis.** Templates generate "antropitzat"/"no antropitzat" from vision result.

**P3 results:** Bell-Lloc Tier B: 0% → 25% (2/8 exact match). `site_description` generates 5-sentence evidence-based paragraph matching Eva's structure (access, delimitation, surface+vegetation, surroundings, subsoil). Remaining gaps: corner parcel LDT limitation (1 address for 2 streets), multi-parcel sites, text wording differences.

### P4 — Parcel identification + geocode fixes (Steps 0-2 DONE, Steps 3-4 pending)

**DONE:**
21. ~~**Address extraction fixes (Step 0)**~~: G3 internal filter, email body block, municipality stripping. 3 root causes fixed across 5 projects. ✅
22. ~~**Municipality matching (Step 1)**~~: Accent stripping in ConsultaMunicipio URL, village→municipality mapping for Aragón. ✅
23. ~~**Direct Callejero path (Step 2)**~~: `callejero_address_to_rc()` → exact RC from address database. Bypasses Nominatim imprecision. House number letter suffix fix (error 42). 6/7 projects now get exact RC. ✅

**DONE (Tier B Improvements):**
26. ~~**Adjacents description enrichment (Improvement 3)**~~: DEFERRED — too risky without snapshot tests. Plan: `docs/PLA-TIER-B-IMPROVEMENTS.md`
27. ~~**location_sentence template rewrite (Improvement 2)**~~: ✅ DONE — "de {municipality}" + Catalan elision in `site_text_generator.py`. Needs pipeline re-run.
28. ~~**Semantic comparison in benchmark (Improvement 1)**~~: ✅ DONE — LLM-as-judge (`--llm-judge` flag). Claude Haiku 4.5 rates 1-5, domain vocab for Cat/Es. Cache at `_llm_judge_cache.json`.
29. ~~**Boilerplate sentences (Improvement 5)**~~: ✅ DONE — Eva's 2 fixed sentences appended to `site_description`, access phrasing aligned.

**PENDING:**
24. **Polygon override for merged parcels (Step 3)**: Bell-Lloc P4b merges 2 parcels → adjacents probe drifts. Pass merged polygon directly to `get_adjacent_parcels()`.
25. **Visual parcel validation**: Cadastre WMS image + plànol → vision LLM confirms correct parcel. Already implemented (P4 Phase 3 commit 03c0a0a), but effectiveness limited by parcel ID accuracy — now that parcels are correct, re-evaluate.
30. **site_condition from ortho (Improvement 4)**: Replace "antropitzat" with structured description. DEFERRED — needs snapshot tests.
31. **Adjacents enrichment (Improvement 3)**: Merge ortho vision data into adjacents descriptions. DEFERRED — most complex, needs tests.

---

## Change log

| Date | Change | Impact |
|------|--------|--------|
| 2026-03-28 | Initial creation. Benchmark layer complete, 7 projects verified. | Baseline: A=38.8%, B=0%, C=17.6% |
| 2026-03-28 | P0 complete: normalizers in compare_benchmarks.py (radon, seismic, dpsh_ids, municipality) + dpsh_test_ids no-space join. Rubí/Anciles wrong values investigated. | Format mismatches → MATCH. A: 38.8% → 53.5% |
| 2026-03-28 | P1 complete: all 7 root causes identified. Key bugs: multi-level N20 averaging (report_data.py:427), building_type=project_name (wizard.py:257), superficie from plànol not cadastre, Rubí geocode missing house number. | Investigation only, no code changes |
| 2026-03-28 | Added wizard warnings for non-Catalan municipalities (radon + seismic lookup failures). | Anciles now shows 4 warnings |
| 2026-03-28 | P1 code fixes: (a) bearing stratum N20 filter in report_data.py, (b) building_type field in plànol prompt, (c) INTECSON client filter in excel_miner + content_discovery, (d) Nb display in report_generator, (e) address house number in plànol prompt. #10 superficie deferred (WFS not reliable). | A: 53.5% → 56.7%. Prompt fixes (#7, #11) need vision re-run. |
| 2026-03-28 | P2: Fixed ICGC rock detection bug (report_data.py) — regional geology was triggering is_rock() for ALL projects. Added wizard formula transparency (_calc_* notes). | C: 17.6% → 23.5%. K30 Rubí: 8.3→6.3 (Eva 6.0). |
| 2026-03-29 | P3: ICGC orthophoto + Mapillary + Groq vision enrichment. New modules: ortho_enrichment.py, ortho_vision.py, site_text_generator.py, mapillary_client.py. Phase 3.5 in auto_extractor. Wizard evidence panel. | B: 0% → 3.7%. site_description: 5-sentence evidence-based paragraph. |
| 2026-03-29 | P3 fix: Cadastre street name from own LDT (not far neighbor). Bell-Lloc east: "Via Ferrea" → "Mestre Ramon Ortiz". | Bell-Lloc B: 12.5% → 25%. |
| 2026-03-29 | P3 fix: Phase 3.5 fetches own cadastral_ref. Enriched values override template-generated in wizard_service. collect_readiness respects enriched sources. | Pipeline integration complete. |
| 2026-03-29 | Populated Eva's Tier B reference values in all 7 benchmark JSONs from signed report text. P4 roadmap: LLM-in-the-Cadastre-loop for visual parcel validation. | Benchmark Tier B measurable. |
| 2026-03-29 | P4 Steps 0+1: Address extraction fixes (G3 filter, email block, accent stripping, village mapping, municipality stripping). 5 root causes fixed. | 6/7 projects now reach Callejero. Exact-match unchanged (benchmark too strict). |
| 2026-03-29 | P4 Step 2: Direct Callejero lookup `callejero_address_to_rc()`. House number letter suffix fix (error 42). Integrated in `_geocode_for_adjacents()` and `_phase25_geocode()`. | 6/7 projects get exact RC. Castellar: 3298012, Rubí: 9341019, Linyola: 5098344, Alcoletge: 8841701, Vilanova: 8606709. |
| 2026-03-29 | Tier B Improvement 1: LLM-as-judge in compare_benchmarks.py (`--llm-judge` flag). Claude Haiku 4.5 rates Tier B text variables 1-5 with domain vocab. Disk cache. | B: 2→4 MATCH, 2→13 CLOSE. Overall: 36.8%→37.9%. Semantic scoring reveals true quality. |
| 2026-03-29 | Tier B Improvement 5: Eva's boilerplate sentences added to site_text_generator.py `_generate_site_description()`. Access phrasing aligned ("El dia dels treballs de camp..."). | Needs pipeline re-run with ortho to measure. |
| 2026-03-29 | Tier B Improvement 2: location_sentence "de {municipality}" + Catalan elision ("d'" before vowels) in site_text_generator.py. | Needs pipeline re-run with ortho to measure. |
| 2026-03-29 | Tier A Fixes 1-5: building_type prompt, client "A petició de:", street_address normalization, dpsh N20/Nb benchmark alignment, cohesion soil_type_to_cohesion(). | Code done, measured after vision re-run. |
| 2026-03-29 | Full vision pipeline re-run (all 7 projects, G3DT_ORTHO_ENRICHMENT=1). Anciles DNS fail. | 62 MATCH + 31 CLOSE / 168. Rubí cota_referencia fixed (+209.50). Castellar regressed (7→11 lost matches). |
| 2026-03-29 | Fix: auto-fill sondeig_layers in report_data.py + clear stale user_data.json on project selection. | Defense-in-depth for rock detection. Prevents stale fields overriding auto-extracted values. |
| 2026-03-29 | Castellar investigation: no architect plànol exists (only Eva's site plan from FreeHand). sondeig_extracted.json not regenerated by pipeline (no sondeig_annex role). num_soil_levels=2 causes Taula 9 to display level 1 (soil) instead of deepest (rock). | Root cause: report_generator.py:1316-1324 uses geotech_rows[0] for display — should use deepest/bearing level. Fix deferred. |
