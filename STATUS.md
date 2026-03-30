# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-30

## Current State

**feat/smartscan mergejat a main (62 commits). Pla de delivery definit. Focus: UX overrides + projectes nous + instal·lació Eva.**

- **Merge completat**: feat/smartscan → main, pushed to origin (2026-03-30)
- **Photo picker**: 11 slots (figures + photos) en ordre de report. Eva selecciona fotos
- **Tier C transparency**: Expert overrides amb fórmules + rangs típics d'Eva
- **N20 averaging**: Exclude refusal + shallow weighting (RMSE 237% → ~35%)
- **Soil type inference**: Auto-classifica des de sondeig (rock/cohesive/granular)
- **Castellar verified**: 6/6 paràmetres geotècnics coincideixen amb Eva

## Active Blockers

- UX Expert Overrides massa amagats — cal redisseny (secció visible + recàlcul dinàmic)
- Projectes nous poden fallar amb noms de fitxer inesperats (preocupació Sílvia 23/3)
- 4/7 projects sense sondeig vision data → soil type inference incompleta
- Preguntes pendents a Eva: N20 criteri, Qa cap, E carbonatades
- Instal·lació a l'ordinador d'Eva pendent

## Next Milestones

- [ ] UX: Paràmetres geomecànics visibles + recàlcul dinàmic (Qa, K30, settlement)
- [ ] Test amb projecte nou real (validar SmartScan end-to-end)
- [ ] Instal·lació a Eva (git clone + uv sync + configurar paths)
- [ ] Preguntar a Eva (N20, Qa caps, E carbonatades) — aprofitar visita
- [ ] Extracció imatges/emails (112 fitxers GAP)

## Key Metrics

| Mètrica | Valor | Nota |
|---------|-------|------|
| Correctesa global | 35.8% (clean baseline) | 59/165 match (no user_data.json) |
| Tier A (auto) | 53.1% | 52/98 — expected +10-15% after N20+soil fixes |
| Tier B (manual/site) | 6.0% | 3/50 (adjacents + site descriptions) |
| Tier C (judgment) | 23.5% | 4/17 — expert overrides panel ajuda Eva |
| N20 RMSE | ~35% (was 237%) | After exclude-refusal + shallow weighting |
| Castellar geotech | 6/6 match | After rock classification fix |

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`
