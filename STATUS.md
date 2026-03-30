# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-29

## Current State

**Major improvements implemented: photo picker, Tier C transparency, N20 fix, soil type inference. Need full benchmark re-run to measure combined impact.**

- **Photo picker**: Fotografies tab shows all 11 report images (figures + photos) in report order. Eva can swap photo selections.
- **Tier C transparency**: Expert overrides panel shows formula breakdowns + Eva's typical ranges
- **N20 averaging**: Exclude refusal + shallow weighting (RMSE 237% → ~35%)
- **Soil type inference**: Auto-classifies from sondeig descriptions (rock/cohesive/granular)
- **Castellar verified**: gamma=2.2, c=1.0, phi=35, E=500, K30=8.3 — all match Eva after soil type fix

## Active Blockers

- 4/7 projects lack sondeig vision data → soil type inference incomplete
- Need Eva's answers: N20 methodology, Qa cap rules, soil classification criteria
- Merge `feat/smartscan` → `main` (30+ commits pending)
- Instal·lar a l'ordinador d'Eva

## Next Milestones

- [ ] Ask Eva 3 specific questions (N20, Qa caps, soil types)
- [ ] Full benchmark re-run to measure N20 + soil type fixes
- [ ] Client name cleanup (strip phone/email, prefer promotor)
- [ ] Surface area investigation (Cadastre vs Eva's values)
- [ ] Merge `feat/smartscan` → `main`

## Key Metrics

| Mètrica | Valor | Nota |
|---------|-------|------|
| Correctesa global | 35.8% (clean baseline) | 59/165 match (no user_data.json) |
| Tier A (auto) | 53.1% | 52/98 — expected +10-15% after N20+soil fixes |
| Tier B (manual/site) | 6.0% | 3/50 (adjacents + site descriptions are hard) |
| Tier C (judgment) | 23.5% | 4/17 — expert overrides panel now helps Eva |
| N20 RMSE | ~35% (was 237%) | After exclude-refusal + shallow weighting |
| Castellar geotech | 6/6 match | After rock classification fix |
