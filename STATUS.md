# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-28

## Current State

**Benchmark layer complet + full_prepare pipeline implementat. Comparació correctesa 23.8% (dades parcials — pendent executar pipeline complet amb visió).**

- **Benchmark layer**: 7 informes signats d'Eva extrets, valors verificats manualment projecte per projecte
- **full_prepare pipeline**: `auto_extract` + Groq vision s'executen automàticament quan l'usuari selecciona projecte al wizard
- **Wizard simplificat**: mode producció (2 accions: seleccionar projecte + generar informe), mode dev amb `?dev=1`
- **collect_readiness.py**: pipeline complet per defecte, `--project bell-lloc` per un sol projecte, `--skip-vision` opcional
- **Readiness**: 12/15 Tier 1 (>=90%), 5 a 100%
- **Correctesa**: 23.8% global — però 6/7 projectes mai van passar Phase 1 (visió). Pendent re-executar amb pipeline complet

## Active Blockers

- Executar pipeline complet per als 7 projectes benchmark (requereix Groq credits, ~20 API calls)
- Merge `feat/smartscan` → `main` (15+ commits pendents)
- Instal·lar a l'ordinador d'Eva
- Silvia: extensió 2 setmanes pendent d'aprovació

## Next Milestones

- [ ] Executar `collect_readiness.py --project bell-lloc` per validar pipeline complet
- [ ] Executar pipeline complet per 7 projectes benchmark, re-comparar correctesa
- [ ] Produir resum combinat readiness + correctesa
- [ ] Fix DPSH extraction per Vilanova + Anciles (~58% → ~90%)
- [ ] Merge `feat/smartscan` → `main`

## Key Metrics

| Mètrica | Valor | Nota |
|---------|-------|------|
| Projectes a 100% readiness | 5/15 | Bell-Lloc, BL3-5, Linyola3 |
| Readiness mitjà | 89.3% | Excloent Bell-Lloc-WIN (error) |
| Correctesa benchmark | 23.8% | 42/181 match — pendent pipeline complet |
| Variables sempre correctes | 5 | municipality, num_dpsh_tests, sulfate_value, geotech_density, cota_referencia |
| Variables sempre errònies | 8 | data_signatura, adjacents(4), site_condition, site_description, location_sentence |
