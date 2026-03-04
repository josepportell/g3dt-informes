# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-03

## Current State

Pipeline complet operatiu. Claude Code és el runtime de producció — s'instal·la a l'ordinador d'Eva i serveix el wizard web en segon pla.

**Model d'operació:** Eva obre localhost:8765, selecciona projecte, el sistema pre-omple tot automàticament (Python + Claude vision), Eva revisa/ajusta, genera informe.

**Qualitat audit (Bell-Lloc):** 97.1% amb user_data complet, **94.9% des de zero** (sense cap intervenció humana)

### Components operatius

| Component | Estat | Notes |
|-----------|-------|-------|
| FileScanner (Fase 0) | ✅ | Classificació automàtica + `vision_type` per rol (v2.1) |
| auto_extract (Fase 0.5) | ✅ | DPSH, Lab, ICGC, Cadastre, geocode, historia geològica |
| Claude vision (Fase 1) | ✅ | Anthropic SDK (sonnet), VISION_REGISTRY genèric, cache JSON |
| Web Wizard (Fase 2) | ✅ | FastAPI + review.html, 4 pestanyes |
| ReportGenerator (Fase 3) | ✅ | .docx amb Jinja2, tots els annexos |
| Historia geològica | ✅ | 238 plantilles Eva, lookup jeràrquic municipi→comarca→region |
| Audit intel·ligent | ✅ | Semàntic per paràgraf + visual .docx |

### Visió: dues vies

- **Via SDK (Anthropic API):** Implementada, testejada, operativa. Pendent aprovació del client per activar-la en producció (implica cost API).
- **Via Claude Code nativa (Read tool):** Claude Code llegeix els PDFs directament, sense SDK ni api_key. S'activarà per demos i mentre no hi hagi aprovació de l'SDK. Implementació pendent (prevista 2026-03-04).

## Branques

`main` conté tot el codi. Merge fast-forward completat 2026-03-03 (`feat/historia-geologica` + `fix/report-quality-audit` → `main`). Branca `feat/historia-geologica` activa per desenvolupament.

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

## Audit Quality (2026-03-03)

### Amb user_data (dades prèvies d'Eva)

| Projecte | Score | Needs review | Missing |
|-----------|:---:|:---:|:---:|
| Bell-Lloc | **97.1%** | 10 | 10 |
| Rubí | 92.3% | 25 | 39 |
| Linyola | 91.0% | 29 | 71 |
| Castellar | 90.9% | 35 | 55 |

### Des de zero (sense user_data, només fitxers font)

| Projecte | Score | Needs review | Missing | Visió |
|-----------|:---:|:---:|:---:|---|
| Bell-Lloc2 | **94.9%** | 17 | 25 | 3/3 PDFs (A.01 + PENETROS + SONDEIG) |
| Linyola2 | 91.0% | 29 | 74 | 2/2 PDFs (PENETROS + pl situ) |

**Bell-Lloc2 a 94.9% sense cap intervenció humana.** La visió omple: arquitecte, empresa, tipus edificació, plantes, superfície construïda, nivells de sòl (sondeig). El 2.2% de diferència són overrides manuals d'Eva (adjacents detallats, E/phi ajustats, descripcions personalitzades).

### Temps de processament (des de zero)

| Projecte | Fase 0+0.5 (Python) | Fase 1 (visió) | Total |
|-----------|:---:|:---:|:---:|
| Bell-Lloc2 (3 PDFs) | ~5s | ~90s | ~95s |
| Linyola2 (2 PDFs) | ~5s | ~40s | ~45s |

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
- [x] Merge feat/historia-geologica → main (fast-forward, 0 conflictes)
- [x] Test full pipeline des de zero (Bell-Lloc2: 94.9%, Linyola2: 91.0%)
- [ ] Category C vocabulary (to d'Eva per secció Materials)
- [ ] Eva revisa index.json (duplicats, variants geològiques)
- [ ] Preguntar Eva: Rubí Qa=3.50, Bell-Lloc N=54
- [ ] Test multi-nivell amb Linyola (sòls expansius)
- [ ] Visió nativa Claude Code (Read tool directe) — per demos i ús interim mentre SDK pendent aprovació
- [ ] Validació amb Eva del flux complet (projecte nou de zero, amb Eva present)
