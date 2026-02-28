# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-02-27

## Current State

Pipeline complet operatiu amb web wizard i geocodificació integrada.

**Qualitat (audit visual):** Plantilla 84.0% | Contingut 79.8%

### Components operatius

| Component | Estat | Notes |
|-----------|-------|-------|
| FileScanner (Fase 0) | ✅ | Classificació automàtica de fitxers |
| auto_extract (Fase 0.5) | ✅ | DPSH, Lab, ICGC, Cadastre, geocode |
| Geocodificació UTM (Fase 2.5) | ✅ | Nominatim + Cadastre + WFS (47 tests) |
| Validació visual (Fase 1) | ✅ | DPSH, Sondeig, Plànol via Claude vision |
| Web Wizard (Fase 2) | ✅ | FastAPI + review.html, 4 pestanyes |
| ReportGenerator (Fase 3) | ✅ | .docx amb Jinja2, tots els annexos |
| Audit visual | ✅ | Split plantilla vs contingut |

### Web Wizard — Funcionalitats

- Selector de projecte amb 4 pestanyes (DPSH, Sondeig, Plànol, Wizard)
- Source badges per camp (auto/user_data/defecte)
- Coordenades UTM amb geocodificació en viu (botó "Geolocalitzar amb ICGC")
- Actualitzar prefills (re-executa Fase 3 amb UTM actualitzades)
- Expert overrides (ICGC, geomech, Es settlement)
- Generar informe + descarregar .docx

### Desviacions actuals (4 projectes)

| Paràmetre | Bell-Lloc | Rubí | Castellar | Linyola |
|-----------|-----------|------|-----------|---------|
| gamma | 0% | 0% | 0% | 0% |
| phi | +1.5% | -1.1% | 0% | +4.0% |
| E | -27.8%* | +4.2% | 0% | +14.2% |
| Qa | -0.2% | -14.4%** | 0% | +3.1% |
| settlement | +27.9%* | +2.3% | - | - |
| K30 | +4.2% | +4.2% | +4.1% | - |

\* Bell-Lloc E=650 (carbonatades, Eva ajusta manualment)
\*\* Rubí Qa=3.50 supera cap 3.0 — pendent preguntar a Eva

## Active Blockers

Cap blocker crític.

## Next Milestones

- [x] Pipeline complet: FileScanner → auto_extract → wizard → report
- [x] Web wizard amb FastAPI (substitueix wizard CLI)
- [x] Geocodificació UTM (Nominatim + Cadastre + WFS INSPIRE)
- [x] UTM al wizard web (camps, source badges, geocode button, refresh prefills)
- [x] Audit visual split: plantilla 84.0% + contingut 79.8%
- [x] Settlement calibrat: Es = 2.5×Nb
- [ ] Preguntar Eva: Rubí Qa=3.50, Bell-Lloc N=54
- [ ] Test multi-nivell amb Linyola (sòls expansius)
- [ ] Validació amb Eva del flux complet web (extracció → wizard → informe → audit)
- [ ] Millorar precisió geocodificació (~100m actual → parcel·la exacta)
