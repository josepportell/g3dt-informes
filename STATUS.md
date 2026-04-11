# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-04-11

## Current State

**Accuracy 61.6% (+1.1pp). Visió exhaustiva operativa: pipeline processa PDFs multi-pàgina d'arquitecte amb chunking (lots de 5p a 200 DPI). Linyola superficie_parcela MATCH, num_floors MATCH des de document que abans s'ignorava. 203 tests.**

## Accuracy (diagnostic 2026-04-11)

| Mètrica | Valor |
|---------|-------|
| **Overall accuracy** | 61.6% |
| **Millora sessió 2026-04-11** | +1.1pp (60.5% → 61.6%) |
| **Millora acumulada** | +23.9pp (37.7% → 61.6%) |

Linyola: 63.2% → 70.6% (+7.4pp). Anciles: dades riques extretes (1655m², 6.5m height) però Eva refs són codis CTE.

## Done (2026-04-11, sessió 2)

- [x] **Experiment visió exhaustiva**: Linyola 11p ($0.013), Anciles 35p ($0.036), Castellar negatiu 0 falsos positius
- [x] **Nou prompt `PROJECTE_ARQUITECTE`**: page-by-page scan + regles explícites Planejament vs Projecte
- [x] **`_discover_multipage_pdfs()`**: detecció per metadades PDF (creator=AutoCAD, pages>3, scoring)
- [x] **Chunking**: PDFs >5p es divideixen en lots de 5p a 200 DPI, merge per confiança
- [x] **Auto-upgrade**: planol amb >5p genera tasca projecte_arquitecte automàticament
- [x] **vision_type fix**: architect_project planol → projecte_arquitecte
- [x] **max_tokens=8192** per projecte_arquitecte (vs 4096 default)
- [x] **Merge al wizard**: projecte_extracted.json omple camps buits (prioritat < planol)
- [x] **SmartScan fixes**: threshold 0.15→0.25, scopes subcarpetes, patrons espanyols
- [x] **Conceptes**: superficie types → numeric, projecte_vision source, qa/k30/settlement nous
- [x] 203 tests (0 regressions), 5 commits

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

- [ ] Refinar prompt projecte_arquitecte (superficie_construida confon ocupació% amb m²)
- [ ] Investigar merge wizard per Anciles (projecte_extracted ric però no arriba al diagnòstic)
- [ ] Provenance UI: badges valors competidors al wizard
- [ ] Settlement phrase parsing, seismic_ab, adjacents orientation
- [ ] Test amb projecte nou real
- [ ] Instal·lació a Eva

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`
