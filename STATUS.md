# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-02-27

## Current State
**Audit visual split: plantilla vs contingut** — highlight_report.py ara separa QUALITAT PLANTILLA (84.0%) de QUALITAT CONTINGUT (79.8%). Nova categoria "verd clar" (darkGreen) per plantilla <100% match.

Pipeline complet: FileScanner → auto_extract → validació visual → wizard → report_generator.

### Desviacions actuals (4 projectes)

| Paràmetre | Bell-Lloc | Rubí | Castellar | Linyola |
|-----------|-----------|------|-----------|---------|
| gamma | 0% | 0% | 0% | 0% |
| phi | +1.5% | -1.1% | 0% | +4.0% |
| E | -27.8%* | +4.2% | 0% | +14.2% |
| Qa | -0.2% | -14.4%** | 0% | +3.1% |
| settlement | +27.9%* | +2.3% | - | - |
| K30 | +4.2% | +4.2% | +4.1% | - |

\* Bell-Lloc E=650 (carbonatades, Eva ajusta manualment) → settlement segueix el gap d'E
\*\* Rubí Qa=3.50 supera cap 3.0 — pendent preguntar a Eva

### Canvis sessió 2026-02-27

| # | Canvi | Fitxer | Impacte |
|---|-------|--------|---------|
| 1 | Split audit: plantilla vs contingut | `highlight_report.py` | Dues mètriques separades |
| 2 | CAT_YELLOW_IMPERFECT (darkGreen) | `highlight_report.py` | Plantilla 95-99.5% match |
| 3 | Section headers amb ratio | `highlight_report.py` | Capçaleres checked via best_match() |
| 4 | highlight_paragraph() raw XML | `highlight_report.py` | Suporta string colors (darkGreen) |

### Canvis sessió 2026-02-26

| # | Canvi | Fitxer | Impacte |
|---|-------|--------|---------|
| 1 | Es = 2.5×Nb (square), 3.5×Nb (strip) | `terzaghi_calculator.py` | Reemplaça Robertson qc path |
| 2 | `Es_override` param | `terzaghi_calculator.py` | Wizard Es té prioritat |
| 3 | Es_settlement prefill | `auto_extractor.py` | 2.5×Nb des de DPSH avg |
| 4 | Es_settlement al wizard | `wizard.py` | Eva pot ajustar Es |
| 5 | Pass-through Es_settlement | `report_generator.py` | user_data → calculate_qa() |
| 6 | Referència comparació corregida | `compare_4projects.py` | BL E=650/s=1.20, Rubí N20=40/s=1.50 |

### Gaps pendents

| Gap | Descripció | Prioritat |
|-----|-----------|-----------|
| Bell-Lloc E | Eva puja E a 650 per "carbonatades" — criteri professional, no fórmula | Baixa (wizard override) |
| Rubí Qa=3.50 | Supera cap 3.0. T-P governs? Cap més alt per graves denses? | Mitjana (preguntar Eva) |
| Linyola E +14% | E=114 vs 100. CTE formula dóna lleugerament per sobre | Baixa |
| K30 | Castellar: real=8.0 vs generat=8.33 (+4.1%) | Baixa |
| Bell-Lloc N=54 | És SPT (sondeig) o N20? Ambigüitat a la taula d'Eva | Baixa (preguntar Eva) |

## Active Blockers
- Cap blocker crític.

## Next Milestones
- [x] Fase 0.5: auto_extractor.py (DPSH, Lab, ICGC, Cadastre)
- [x] Fixes post-comparació Castellar (6 fixes + 3 correccions)
- [x] Metodologia Eva confirmada (Nb, T-P, Qa cap, gamma D.27)
- [x] Settlement calibrat: Es = 2.5×Nb (+2.3% Rubí, +27.9% Bell-Lloc per E gap)
- [x] Audit visual split: plantilla 84.0% + contingut 79.8%
- [ ] Preguntar Eva: Rubí Qa=3.50, Bell-Lloc N=54
- [ ] Test multi-nivell amb Linyola (sòls expansius)
- [ ] Validació amb G3DT del flux complet (extracció → wizard → informe → audit)
- [ ] v2: Lectura portada .doc, geocodificació adreça→UTM, ref cadastral→UTM via WFS
