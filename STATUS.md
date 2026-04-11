# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-04-11

## Current State

**Visió exhaustiva implementada (4 fases). Pipeline processa TOTS els PDFs visuals multi-pàgina, no només primaris SmartScan. Experiment validat: superficie_construida MATCH, parcela MATCH, plantes MATCH, zero falsos positius. 203 tests.**

## Accuracy (diagnostic 2026-04-10, amb LLM judge)

| Mètrica | Valor |
|---------|-------|
| **Overall accuracy** | 60.9% |
| **Millora sessió 2026-04-10** | +23.2pp (37.7% → 60.9%) |

**Pendent re-diagnòstic** amb visió exhaustiva — esperat millora significativa en superficie_construida, building_height, num_floors.

## Done (2026-04-11, sessió 2)

- [x] **Experiment visió exhaustiva**: Linyola 11p ($0.013), Anciles 35p ($0.036), Castellar negatiu 0 falsos positius
- [x] **Nou prompt `PROJECTE_ARQUITECTE`**: extracció multi-pàgina (normativa, superfícies, alçades, plantes)
- [x] **`_discover_multipage_pdfs()`**: detecció per metadades PDF (creator=AutoCAD, pages>3, scoring)
- [x] **Merge al wizard**: `projecte_extracted.json` amb prioritat inferior a planol (omple camps buits)
- [x] **SmartScan fixes**: threshold 0.15→0.25, scopes subcarpetes, patrons espanyols (PLANOS, DG)
- [x] **Conceptes**: superficie_construida/parcela → numeric, `projecte_vision` source (25), qa_value/k30_value/settlement_cm nous
- [x] 203 tests (0 regressions)

## Done (2026-04-11, sessió 1)

- [x] **is_anthropized**: radio buttons buits + descripció visual terreny
- [x] **SmartScan multi-fitxer**: `role_files` amb TOTS els fitxers per rol
- [x] **WhatsApp photos**: nou rol `field_photo`

## Done (2026-04-10)

- [x] Qa variable cap + rounding 0.5 kg/cm2
- [x] site_condition auto des de ICGC slope (4 variants)
- [x] Cross-source lab deduction, coordinate validation
- [x] LLM judge, SmartScan Tier 3 multi-page, LLM synthesis priority

## Done (2026-04-05)

- [x] Arquitectura Concepte-Format: 53 conceptes + 8 formats + format learning
- [x] Reference Extractor: 7 informes Eva
- [x] Comparació Eva vs Pipeline, SmartScan Tier 2 .xlsx

## Active Blockers

- Instal·lació a l'ordinador d'Eva pendent
- Preguntes a Eva: N20 criteri, Qa cap, E carbonatades

## Next Milestones

- [ ] Re-diagnòstic amb visió exhaustiva (esperat +10-15pp accuracy)
- [ ] Provenance UI: badges valors competidors al wizard (quan conflictes reals)
- [ ] Settlement phrase parsing, seismic_ab, adjacents orientation
- [ ] Test amb projecte nou real
- [ ] Instal·lació a Eva

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`
