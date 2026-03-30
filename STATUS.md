# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-30

## Current State

**SmartScan + Groq activats per defecte. Overrides redesenyats amb recàlcul en viu. Focus: extracció imatges + instal·lació Eva.**

- **SmartScan ON**: 30+ rols (vs 15 FileScanner), variants CA/ES, imatges, .msg
- **Groq deep mine ON**: LLM gap-filling per fitxers on regex falla
- **Paràmetres Geomecànics**: Secció visible amb recàlcul dinàmic (Qa, K30, assentament)
- **feat/smartscan**: Mergejat a main, pushed to origin (2026-03-30)

## Done (2026-03-30)

- [x] Merge feat/smartscan → main (62 commits)
- [x] UX: Paràmetres geomecànics visibles + recàlcul dinàmic + flash
- [x] SmartScan activat per defecte (era implementat però mai activat)
- [x] Groq deep mine activat per defecte (idem)

## Active Blockers

- Extracció d'imatges (.jpg/.png) com a documents — SmartScan les classifica però no s'extreuen dades
- Preguntes pendents a Eva: N20 criteri, Qa cap, E carbonatades
- Instal·lació a l'ordinador d'Eva pendent

## Next Milestones

- [ ] Extracció imatges → vision pipeline (PENETROS.jpeg, plans .png)
- [ ] Test amb projecte nou real (validar SmartScan end-to-end)
- [ ] Instal·lació a Eva (git clone + uv sync + .env)
- [ ] Preguntar a Eva (N20, Qa caps, E carbonatades) — aprofitar visita

## Pendents menors (no bloquejants)

- [ ] Stepper cosmètic: Geocode/APIs HTTP es marquen tatxats però les dades arriben via merge posterior
- [ ] Lab PDF: `MULTICA_61.pdf` (Vilanova) no reconegut — cal afegir patró
- [ ] Dates camp: `field_date` extret per FileMiner no es promociona a `field_work_dates`
- [ ] `.xlsx` (nou format Excel): "not supported" — caldria migrar de xlrd a openpyxl

## Key Metrics

| Mètrica | Valor | Nota |
|---------|-------|------|
| Correctesa global | 35.8% (clean baseline) | 59/165 match (no user_data.json) |
| Tier A (auto) | 53.1% | 52/98 |
| Tier B (manual/site) | 4.0% | 2/50 (adjacents + site descriptions) |
| Tier C (judgment) | 23.5% | 4/17 — expert overrides panel ajuda Eva |

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`
