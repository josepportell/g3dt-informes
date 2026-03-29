# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-29

## Current State

**P4 geocode fixes in progress. Address extraction + accent bugs fixed (Steps 0-1). Correctness 36.8% (174 vars). Next: direct Callejero path for exact parcel RC.**

- **Steps 0+1 DONE** (commit `448ed19`): G3 internal address filter, email body block, accent stripping in ConsultaMunicipio, village→municipality mapping, address municipality cleanup
- **Validated**: G3 filter catches Rubí/Alcoletge/Vilanova. Accent fix resolves Castellar/Vilanova municipalities. Linyola no longer geocodes email footer.
- **Step 2 next**: Direct Callejero lookup in `_geocode_for_adjacents()` — bypass complex fallback chain for exact cadastral reference
- **Benchmark**: 64/174 match (36.8%), Tier A 56.9%, Tier B 3.6% exact / 7.3% semantic, Tier C 23.5%
- **Readiness**: Bell-Lloc 100%, Castellar/Rubí/Linyola/Alcoletge ~90%, Vilanova 55%, Anciles 58%

## Active Blockers

- Step 2: direct Callejero → exact parcel RC (unblocks adjacents accuracy)
- Castellar: municipality found but error 42 (house number mismatch) — Callejero will fix
- Anciles: DNS resolution failures during last run (transient) — village mapping untested
- Merge `feat/smartscan` → `main` (20+ commits pending)
- Instal·lar a l'ordinador d'Eva

## Next Milestones

- [ ] Step 2: Direct Callejero path in `_geocode_for_adjacents()`
- [ ] Step 3: Polygon override for merged parcels (Bell-Lloc)
- [ ] Re-validate all 7 projects after Steps 2+3
- [ ] Executar pipeline complet amb visió (Groq) per tots 7 projectes
- [ ] Merge `feat/smartscan` → `main`

## Key Metrics

| Mètrica | Valor | Nota |
|---------|-------|------|
| Correctesa global | 36.8% | 64/174 match |
| Tier A (auto) | 56.9% | 58/102 |
| Tier B (manual/site) | 3.6% exact, 7.3% semantic | 2/55 exact, 4/55 semantic |
| Tier C (judgment) | 23.5% | 4/17 |
| Projectes a 100% readiness | 1/7 | Bell-Lloc |
| G3 filter activat | 3 projectes | Rubí, Alcoletge, Vilanova |
