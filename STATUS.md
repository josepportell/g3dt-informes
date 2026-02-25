# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-02-25

## Current State
**Post-comparació Castellar completada** — 6 fixes implementats + 3 correccions addicionals trobades durant la validació. L'informe generat de Castellar (3001621) s'aproxima significativament al real de G3DT.

Pipeline complet: FileScanner → auto_extract → validació visual → wizard → report_generator.

### Fixes implementats (sessió 2026-02-25)

| # | Fix | Fitxer | Impacte |
|---|-----|--------|---------|
| 1 | Sulfats 0.0 acceptats | `lab_extractor.py:130` | `0 <` → `0 <=` |
| 2 | Rock detection amb descripció | `report_data.py:~370` | `is_rock(n20, description)` detecta roca per keywords |
| 3 | Drenatge §4.2 per pendents | `section4_conclusions.py` | Text recomanació xarxa d'aigües |
| 4 | Àbac Hoek & Bray (NOU) | `hoek_bray.py` | Taylor stability + bisecció solver per ruptura circular |
| 5 | Integració Hoek & Bray | `slope_calculator.py` + `section4_conclusions.py` | Routing c>0 → circular, text §4.5 |
| 6 | slope_height_m camp | `data_schema.py` + `report_data.py` | Alçada talús per H&B |
| + | user_data.json auto-discovery | `report_generator.py:_load_user_data` | Auto-carrega user_data.json del projecte |
| + | Sulfats 0.0 al template | `report_generator.py:890` | `if x` → `if x is not None` |
| + | sondeig_layers sempre poblat | `report_generator.py:214` | Necessari per rock detection |

### Comparació Castellar: Generat vs Real

| Secció | Real (G3DT) | Generat | Estat |
|--------|-------------|---------|-------|
| Taula 10 - Rock params | phi=35°, c=1.0, E>500 | L2: phi=35°, c=1.00, E=500 | **Correcte** |
| §4.5 Estabilitat | Hoek & Bray, FS>3.5 | Hoek & Bray àbac nº1, FS=10.47 | **Funcional** (FS alt) |
| §4.4 Empentes | Ka=0.271, Kp=3.690 | Ka=0.271, Kp=3.690 | **Exacte** |
| §4.3 Qa | 3.0 kg/cm² | 3.18 kg/cm² | **~6% diff** |
| Sulfats | 0.0 → No agressius | 0.0 → No Agressius | **Resolt** |

### Gaps pendents (Fase 2)

| Gap | Descripció | Prioritat |
|-----|-----------|-----------|
| K30 | Real=8.0 vs Generat=5.0 kg/cm³ (no usa rock params) | Mitjana |
| 1 vs 2 nivells | G3DT fusiona en 1 nivell per roca, generat mostra 2 | Baixa |
| FS=10.47 | Correcte numèricament, real diu ">3.5". Truncar? | Baixa |
| §4.5 text nivell | Referencia "1r nivell" però usa params del 2n | Mitjana |
| §4.2 drenatge | Fix implementat, verificar apareix al template | Baixa |

## Active Blockers
- Cap blocker crític.

## Next Milestones
- [x] Fase 0.5: auto_extractor.py (DPSH, Lab, ICGC, Cadastre)
- [x] Fixes post-comparació Castellar (6 fixes + 3 correccions)
- [x] Test end-to-end generació Castellar (§4.4 Empentes + §4.5 Estabilitat)
- [ ] Afinament Fase 2: K30 amb rock params, fusió nivells, truncar FS
- [ ] Test multi-nivell amb Linyola (sòls expansius, reordenament seccions)
- [ ] Validació amb G3DT del flux complet (extracció → wizard → informe → audit)
- [ ] v2: Lectura portada .doc, geocodificació adreça→UTM, ref cadastral→UTM via WFS
