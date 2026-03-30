# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-30

## Current State

**SmartScan + Groq + Tier 3 activats. Overrides redesenyats. Pipeline funcional end-to-end per a imatges i emails. Pendent: instal·lació Eva + test projecte nou.**

## Done (2026-03-30)

- [x] Merge feat/smartscan → main (62 commits, pushed to origin)
- [x] UX: "Paràmetres Geomecànics" visibles amb recàlcul dinàmic (Qa, K30, assentament)
- [x] SmartScan activat per defecte (era implementat però mai activat)
- [x] Groq deep mine activat per defecte (idem)
- [x] SmartScan Tier 3 (visió LLM) activat per classificar fitxers amb noms inesperats
- [x] SmartScan exclou `validation/` (eliminat soroll de 49+ imatges pròpies)
- [x] Suggestions passen a Tier 3 (no es queden com "classified" prematurament)

## Active Blockers

- Instal·lació a l'ordinador d'Eva pendent
- Preguntes a Eva: N20 criteri, Qa cap, E carbonatades
- N20 averaging: 5/7 projectes tenen dpsh_avg_n20 MISMATCH (inclou refús en la mitjana)

## Next Milestones

- [ ] Test amb projecte nou real (Eva proporciona carpeta desconeguda)
- [ ] Instal·lació a Eva (git clone + uv sync + .env)
- [ ] Preguntar a Eva (N20, Qa caps, E carbonatades) — aprofitar visita
- [ ] Merge feat/delivery → main + push

## Pendents menors (no bloquejants)

- [ ] Stepper cosmètic: Geocode/APIs HTTP tatxats però dades arriben via merge
- [ ] Lab PDF: `MULTICA_61.pdf` (Vilanova) no reconegut — afegir patró
- [ ] Dates camp: `field_date` de FileMiner no es promociona a `field_work_dates`
- [ ] `.xlsx` format: xlrd no llegeix .xlsx — migrar a openpyxl
- [ ] Client name cleanup: strip telèfon/email del nom (Anciles, Alcoletge)
- [ ] Selector max_tier al wizard (futur)

## Key Metrics (benchmark 2026-03-30)

| Mètrica | Valor | Detall |
|---------|-------|--------|
| **Correctesa global** | 35.2% (58/165 match) | Clean baseline, no user_data.json |
| **Match+Close** | 43.6% (72/165) | Close = dins tolerància 5% |
| **Tier A** (auto-extractable) | 53.1% (52/98) | 37 MISMATCH, 9 CLOSE |
| **Tier B** (manual/site) | 4.0% (2/50) | Adjacents, site descriptions |
| **Tier C** (judici expert) | 23.5% (4/17) | Expert overrides panel ajuda Eva |

### Tier A MISMATCH principals (37 errors)

| Categoria | Count | Causa | Fix |
|-----------|-------|-------|-----|
| dpsh_avg_n20 / geotech_nb | 10 | Refús inclòs en mitjana | Preguntar Eva criteri N20 |
| superficie_parcela | 3 | Cadastre vs Eva (fonts diferents) | Investigar |
| client | 3 | Nom amb soroll (telèfon, empresa arquitecte) | Client name cleanup |
| building_type | 4 | Terminologia parcial vs Eva | Vocabulari |
| street_address | 3 | Format lleugerament diferent | Normalització |
| municipality | 2 | Alcoletge→Alella, Anciles→Arciles | Geocode bug |
| seismic_ab | 2 | Font NCSE-02 vs Eva | Investigar |
| Altres | 10 | Varis (num_floors, cohesion, dates) | Cas per cas |

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`
