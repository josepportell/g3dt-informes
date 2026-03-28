# Correctness Tracker — Deviations from Eva's Reference Reports

Created: 2026-03-28
Last updated: 2026-03-28

## Overview

Compares our pipeline output against Eva's 7 signed reports. Each variable is classified into a tier and tracked through investigation → fix → verification.

**Current state:**
| Tier | Description | Match | Total | Correctness |
|------|-------------|-------|-------|-------------|
| A | Auto-extractable | 40/103 | **38.8%** | Target: 95% |
| B | Manual/on-site | 0/54 | **0.0%** | Target: best effort |
| C | Professional judgment | 3/17 | **17.6%** | Target: transparency |

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

## Tier B — Manual/on-site (0/54 match)

These variables describe what Eva physically observes at the site. The pipeline cannot know this from documents alone.

| Variable | Count | Current source | Possible improvements |
|----------|-------|---------------|----------------------|
| `adjacent_north/south/east/west` | 0/28 | Cadastre API: "parcel·la amb construcció", "via pública", etc. | [ ] **Google Street View API**: if available at coordinates, describe what's visible in each direction. Won't work for rural parcels but urban projects would benefit. [ ] **Google Earth satellite**: visible land use (constructed, empty, vegetation). [ ] **LLM description from Cadastre + satellite**: combine Cadastre classification with visual data for richer descriptions. [ ] **Minimum**: improve Cadastre labels with more detail (building type, street name when adjacent to street). |
| `site_condition` | 0/7 | Hardcoded "antropitzat" | [ ] **Satellite/Street View**: detect if parcel is paved, vegetated, empty. [ ] **Cadastre land use**: may indicate urbanized vs rural. [ ] At minimum, stop hardcoding "antropitzat" — it's wrong for most parcels. |
| `site_description` | 0/7 | Template: "El terreny es presenta antropitzat" | [ ] Same as site_condition — derive from visual/satellite data. [ ] Include parcel shape and dimensions from Cadastre geometry. |
| `access_description` | 0/5 | Template: "El dia dels treballs de camp..." | [ ] **Street View**: identify access road/street. [ ] Use adjacent street info from geocoding to construct description. |
| `location_sentence` | 0/7 | Template: "entre el {street} i el {street2}" | [ ] Improve template with municipality context and project description. Eva writes: "L'edificació que es preveu construir es situarà en..." — our template is too formulaic. |

**Street View / Google Earth investigation needed:**
- [ ] Check Google Street View Static API: given UTM coordinates, can we get images in 4 cardinal directions?
- [ ] Check Google Earth Engine API: can we get satellite imagery of a parcel?
- [ ] Cost analysis: per-image pricing for 7+ projects
- [ ] Coverage: test with all 7 benchmark project coordinates — how many have Street View?
- [ ] Eva has explicitly requested this capability multiple times

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
1. `radon_zone` format: store "ZONA {n}" not just "{n}"
2. `seismic_ab_text` format: store "AB {op} {value} g" not just "{value}"
3. `dpsh_test_ids` format: normalize comma spacing
4. `municipality` format: strip province suffix
5. Investigate wrong values: Rubí seismic (0.08 vs 0.04), Anciles radon ("ZONA 2" vs "0")

### P1 — Investigation (understand root cause before fixing)
6. `client` extraction chain: why does FileMiner pick "INTECSON"?
7. `building_type` extraction: where does the value come from?
8. `geotech_nb` representation: how to compute representative Nb from DPSH data
9. `dpsh_avg_n20` metric alignment: compare N20 or Nb?
10. `superficie_parcela` source: why large deviations in 3 projects?
11. `cota_referencia` Rubí: why 129 instead of 212.5?
12. Multi-level selection: why does pipeline pick wrong geological level for Alcoletge/Linyola?

### P2 — Tier C transparency
13. Add formula explanations to wizard for E, Qa, settlement, K30
14. Investigate Rubí K30 calculation anomaly
15. Investigate qa_value cap logic (why 5.0 for Castellar?)

### P3 — Tier B best effort
16. Google Street View API feasibility study
17. Google Earth / satellite imagery feasibility
18. Improve Cadastre adjacent labels (add street names, building types)
19. Improve location_sentence template
20. Stop hardcoding site_condition = "antropitzat"

---

## Change log

| Date | Change | Impact |
|------|--------|--------|
| 2026-03-28 | Initial creation. Benchmark layer complete, 7 projects verified. | Baseline: A=38.8%, B=0%, C=17.6% |
