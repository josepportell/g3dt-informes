# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-01

## Current State

Pipeline complet operatiu. Història geològica integrada amb plantilles d'Eva.

**Qualitat (audit visual):** Plantilla 84.0% | Contingut 79.8%

### Components operatius

| Component | Estat | Notes |
|-----------|-------|-------|
| FileScanner (Fase 0) | ✅ | Classificació automàtica de fitxers |
| auto_extract (Fase 0.5) | ✅ | DPSH, Lab, ICGC, Cadastre, geocode, **historia geològica** |
| Geocodificació UTM (Fase 2.5) | ✅ | Nominatim + Cadastre + WFS (47 tests) |
| Validació visual (Fase 1) | ✅ | DPSH, Sondeig, Plànol via Claude vision |
| Web Wizard (Fase 2) | ✅ | FastAPI + review.html, 4 pestanyes |
| ReportGenerator (Fase 3) | ✅ | .docx amb Jinja2, tots els annexos |
| Historia geològica | ✅ | 238 plantilles Eva, lookup jeràrquic municipi→comarca→region |
| Audit visual | ✅ | Split plantilla vs contingut |

## Branques actives

| Branca | Base | Contingut | Estat |
|--------|------|-----------|-------|
| `main` | — | Pipeline base fins a settlement calibrat | Estable |
| `fix/report-quality-audit` | `main` | Audit 100%, Cadastre lookup, image fallbacks, CE-21 | En curs |
| `feat/historia-geologica` | `main` | Plantilles regionals + lookup jeràrquic | **Funcional** |

**IMPORTANT per merge:** `feat/historia-geologica` surt de `main`, NO de `fix/report-quality-audit`.
Primer merge `fix/report-quality-audit` → `main`, després `feat/historia-geologica` → `main`.

### feat/historia-geologica (2026-03-01)
- 238 .docx plantilles d'Eva, `index.json` amb 240 entrades
- `historia_geologica.py`: lookup fuzzy + fallback jeràrquic (municipi→comarca→region)
- `comarques.json`: 42 comarques, ~908 municipis → mapa comarca→plantilla
- Integrat a: auto_extractor (prefill), wizard (override), section3 (genera §3.1)
- **Testat:** Rubí→tier1, Castellar→tier1, Bell-Lloc→Lleida(comarca), Linyola→Lleida(comarca), Sant Cugat→vallès(comarca), 19 municipis verificats

## Desviacions actuals (4 projectes)

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
- [x] Plantilles història geològica extretes + index.json generat
- [x] Lògica lookup municipi → plantilla (fuzzy match + jerarquia comarca)
- [x] Extracció text .docx → inserció al report (§3.1 MARC GEOLÒGIC)
- [ ] Eva revisa index.json (duplicats, variants geològiques)
- [ ] Preguntar Eva: Rubí Qa=3.50, Bell-Lloc N=54
- [ ] Test multi-nivell amb Linyola (sòls expansius)
- [ ] Validació amb Eva del flux complet web (extracció → wizard → informe → audit)
