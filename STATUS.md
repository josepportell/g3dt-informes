# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-03

## Current State

Pipeline complet operatiu. Claude Code és el runtime de producció — s'instal·la a l'ordinador d'Eva i serveix el wizard web en segon pla.

**Model d'operació:** Eva obre localhost:8765, selecciona projecte, el sistema pre-omple tot automàticament (Python + Claude vision), Eva revisa/ajusta, genera informe.

**Qualitat (audit Bell-Lloc):** 97.1% auto-resolved (post-fixes 2026-03-02)

### Components operatius

| Component | Estat | Notes |
|-----------|-------|-------|
| FileScanner (Fase 0) | ✅ | Classificació automàtica + `vision_type` per rol (v2.1) |
| auto_extract (Fase 0.5) | ✅ | DPSH, Lab, ICGC, Cadastre, geocode, historia geològica |
| Claude vision (Fase 1) | ✅ | Anthropic API (sonnet), VISION_REGISTRY genèric, cache JSON |
| Web Wizard (Fase 2) | ✅ | FastAPI + review.html, 4 pestanyes |
| ReportGenerator (Fase 3) | ✅ | .docx amb Jinja2, tots els annexos |
| Historia geològica | ✅ | 238 plantilles Eva, lookup jeràrquic municipi→comarca→region |
| Audit intel·ligent | ✅ | Semàntic per paràgraf + visual .docx |

## Branques actives

| Branca | Base | Contingut | Estat |
|--------|------|-----------|-------|
| `main` | — | Pipeline base fins a settlement calibrat | Estable |
| `fix/report-quality-audit` | `main` | Audit 100%, Cadastre lookup, image fallbacks, CE-21 | Pendent merge |
| `feat/historia-geologica` | `main` | Plantilles regionals + lookup jeràrquic + fixes audit | **Activa** |

**IMPORTANT per merge:** `feat/historia-geologica` surt de `main`, NO de `fix/report-quality-audit`.
Primer merge `fix/report-quality-audit` → `main`, després `feat/historia-geologica` → `main`.

### feat/historia-geologica (2026-03-03)
- 238 .docx plantilles d'Eva, `index.json` amb 240 entrades
- `historia_geologica.py`: lookup fuzzy + fallback jeràrquic (municipi→comarca→region)
- `comarques.json`: 42 comarques, ~908 municipis → mapa comarca→plantilla
- Integrat a: auto_extractor (prefill), wizard (override), section3 (genera §3.1)
- **Fixes audit (2026-03-02):** Historia dinàmica (for-loop), filtre sondeig, desc material deepest layer, short material tables, Nb range
- **Vision integration (2026-03-03):** `vision_extractor.py` (Anthropic API), `vision_type` al file_scanner, prompts plànol, wizard prefills visió

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

### Fixes recents (branca fix/report-quality-audit)

| Fix | Descripció | Commit |
|-----|-----------|--------|
| Taula 4 sondeig | Columnes alineades amb Eva: Punt, SPT/MA, N.F. | baacdaa |
| Nivells Bell-Lloc | 2→1 nivell: respecta num_levels del wizard | baacdaa |
| Profunditat refús DPSH | Usa anotació manuscrita "R:" (1.35/2.45) vs última fila Excel | baacdaa |
| Fórmula sísmica | A<sub>b</sub> amb subíndex, "<" en lloc de "=", coma decimal | 892a5f5 |
| Mapa geològic transparent | Topo base + geologia al 35% opacitat + punt vermell ubicació | a5eff89 |

## Active Blockers

Cap blocker crític.

## Commits recents (2026-03-03)

| Commit | Descripció |
|--------|-----------|
| `57c9bd3` | fix: audit critical bugs (geologia dinàmica, filtre sondeig, material desc) |
| `348fe88` | feat: integrate Claude vision into wizard pipeline (Anthropic API) |
| `401838b` | refactor: file_scanner declares vision_type, vision_extractor genèric |

## Audit Quality (2026-03-02)

| Projecte | Score | Notes |
|-----------|-------|-------|
| Bell-Lloc | 97.1% | Projecte referència, user_data complet |
| Castellar | 87.5% | user_data parcial (79% camps crítics) |
| Rubí | 89.8% | user_data parcial (37% camps crítics), sense sondeig |
| Linyola | 89.0% | user_data mínim (5% camps crítics) |

Scores baixos de Castellar/Rubí/Linyola són per **dades d'entrada incompletes**, no bugs. Amb el pipeline complet (Claude vision Fase 1) es pre-ompliran automàticament.

## Next Milestones

- [x] Pipeline complet: FileScanner → auto_extract → wizard → report
- [x] Web wizard amb FastAPI
- [x] Geocodificació UTM (Nominatim + Cadastre + WFS INSPIRE)
- [x] Settlement calibrat: Es = 2.5×Nb
- [x] Plantilles història geològica (238 templates, lookup jeràrquic)
- [x] Audit intel·ligent (semàntic per paràgraf, Bell-Lloc 97.1%)
- [x] Fix: historia dinàmica (for-loop, sense límit 6 slots)
- [x] Fix: filtre sondeig (num_levels vs sondeig_layers)
- [x] Fix: descripció material (deepest layer = bearing stratum)
- [x] Integrar Claude vision (Fase 1) al pipeline automàtic del wizard
- [x] `vision_type` al file_scanner (desacoblament vision_extractor ↔ nomenclatura rols)
- [ ] Category C vocabulary (to d'Eva per secció Materials)
- [ ] Eva revisa index.json (duplicats, variants geològiques)
- [ ] Preguntar Eva: Rubí Qa=3.50, Bell-Lloc N=54
- [ ] Test multi-nivell amb Linyola (sòls expansius)
- [ ] Validació amb Eva del flux complet (projecte nou de zero)
- [ ] Merge feat/historia-geologica → main (quan validat amb Eva)
