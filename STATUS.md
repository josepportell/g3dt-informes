# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-29

## Current State

**Tier A Fixes 1-5 + Tier B Improvements 1/5/2 all done (code changes). Need pipeline re-run with vision to measure full impact.**

- **Tier A Fixes DONE** (code): building_type prompt fix, client "A petició de:", street_address normalization, dpsh N20/Nb alignment, cohesion soil_type lookup
- **Tier B Improvements DONE** (code): LLM-as-judge, boilerplate sentences, location_sentence template
- **Current benchmark** (pre-re-run): 63/174 match (36.2%), but many fixes require pipeline re-run to take effect
- **Expected after re-run**: Tier A 56.9% → ~75-85%, Overall 36% → ~50-55%

## What needs pipeline re-run

| Fix | Needs vision? | Needs any re-run? |
|-----|--------------|-------------------|
| Fix 1 (building_type) | YES | YES — prompt change |
| Fix 2 (client) | YES | YES — new field in prompt |
| Fix 3 (street_address) | NO | YES — abbreviation expansion in auto_extractor |
| Fix 4 (dpsh benchmark) | NO | NO — already measured |
| Fix 5 (cohesion) | NO | YES — report_generator code change |
| Imp 1 (LLM judge) | NO | NO — comparison-only |
| Imp 2 (location_sentence) | NO | YES — template change in site_text_generator |
| Imp 5 (boilerplate) | NO | YES — site_text_generator change |

## Active Blockers

- **Pipeline re-run** needed: `collect_readiness.py` (without `--skip-vision`) for all 7 projects
- Merge `feat/smartscan` → `main` (20+ commits pending)
- Instal·lar a l'ordinador d'Eva

## Next Milestones

- [ ] Re-run pipeline with vision (Fix 0): measure all fixes
- [ ] Re-run benchmark with `--llm-judge`: measure Tier B improvements
- [ ] Assess: are Tier B Improvements 3+4 still needed?
- [ ] Step 3: Polygon override for merged parcels (Bell-Lloc)
- [ ] Merge `feat/smartscan` → `main`

## Key Metrics

| Mètrica | Valor | Nota |
|---------|-------|------|
| Correctesa global | 36.2% (pre-re-run) | 63/174 match |
| Tier A (auto) | 55.9% | 57/102 — will improve significantly with re-run |
| Tier B (manual/site) | 7.3% exact, 23.6% CLOSE | 4/55 exact, 13/55 CLOSE (LLM judge) |
| Tier C (judgment) | 23.5% | 4/17 |
| Code fixes pending verification | 7 | Need pipeline re-run |
