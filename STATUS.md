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
- [ ] Valorar capa "LLM de síntesi" per inferir camps buits a partir de dades ja extretes
- [ ] Millorar prompt visió plànol: extreure taula JUSTIFICACIÓ PLANEJAMENT (sup, alçada, plantes)
- [ ] Prioritzar ACCEPTACIO/ per client name (pressupost signat té promotor clar)

## Key Metrics (benchmark 2026-03-30, amb avaluació semàntica Tier B)

| Mètrica | Valor | Detall |
|---------|-------|--------|
| **Correct** (MATCH + SEMANTIC_MATCH) | 44.8% (74/165) | Semànticament correcte |
| **Acceptable** (+ PARTIAL) | 56.4% (93/165) | Direcció correcta, menys detall |
| **Wrong** (MISMATCH) | 35.2% (58/165) | Factual error |
| **Tier A** (auto-extractable) | 53% (52/98) acceptable | 37 wrong |
| **Tier B** (manual/site) | 74% (37/50) acceptable | 13 wrong (Cadastre vs camp) |
| **Tier C** (judici expert) | 24% (4/17) acceptable | 8 wrong (esperat: Eva ajusta) |

### Camps buits al wizard (19% = 35/182)

| Camp | Buits | Causa |
|------|-------|-------|
| superficie_construida | 7/7 | No s'extreu (taula JUSTIFICACIÓ al plànol) |
| building_height_m | 7/7 | Idem |
| superficie_parcela_m2 | 5/7 | Cadastre dóna valor diferent |
| num_floors | 4/7 | Difícil extreure (varia format) |
| cota_referencia | 2/7 | Sense sondeig o ICGC |

### Tier A MISMATCH principals (37 errors)

| Categoria | Count | Causa | Fix |
|-----------|-------|-------|-----|
| dpsh_avg_n20 / geotech_nb | 10 | Refús inclòs en mitjana | Preguntar Eva criteri N20 |
| building_type | 4 | Terminologia parcial vs Eva | Vocabulari |
| superficie_parcela | 3 | Cadastre vs Eva (fonts diferents) | Investigar |
| client | 3 | Nom amb soroll (telèfon, empresa arquitecte) | Prioritzar ACCEPTACIO |
| street_address | 3 | Format lleugerament diferent | Normalització |
| municipality | 2 | Alcoletge→Alella, Anciles→Arciles | Geocode bug |
| seismic_ab | 2 | Font NCSE-02 vs Eva | Investigar |
| Altres | 10 | Varis (num_floors, cohesion, dates) | Cas per cas |

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`
