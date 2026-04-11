# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-04-11

## Current State

**Accuracy 60.9%. is_anthropized amb observació visual implementat. SmartScan multi-fitxer implementat (role_files). 203 tests. Pendent: instal·lació Eva, settlement, seismic_ab.**

## Accuracy (diagnostic 2026-04-10, amb LLM judge)

| Mètrica | Valor |
|---------|-------|
| **Overall accuracy** | 60.9% |
| **Millora sessió 2026-04-10** | +23.2pp (37.7% → 60.9%) |

## Done (2026-04-11)

- [x] **is_anthropized**: radio buttons buits (no switch amb default True) + descripció visual terreny des de fotos de camp (gpt-4.1-mini, ~$0.01/projecte). None propagat per backend.
- [x] **SmartScan multi-fitxer**: `role_files` secció amb TOTS els fitxers per rol (additivament, `roles` intacte). Impacte: Alcoletge 16→10 unassigned, Bell-Lloc 21→15 unassigned + 8 WhatsApp recuperats.
- [x] **WhatsApp photos**: nou rol `field_photo` (abans IGNORED com "photo_or_acceptance")
- [x] **Consumers actualitzats**: image_manager (multi-photo discovery), fileminer (role_files fallback)
- [x] 203 tests (197 + 6 nous role_files)

## Done (2026-04-10)

- [x] Qa variable cap + rounding 0.5 kg/cm2
- [x] site_condition auto des de ICGC slope (4 variants)
- [x] Cross-source lab deduction, coordinate validation
- [x] LLM judge, SmartScan Tier 3 multi-page, LLM synthesis priority, PASS category

## Done (2026-04-05)

- [x] Arquitectura Concepte-Format: 53 conceptes + 8 formats + format learning
- [x] Reference Extractor: 7 informes Eva
- [x] Comparació Eva vs Pipeline, SmartScan Tier 2 .xlsx

## Active Blockers

- Instal·lació a l'ordinador d'Eva pendent
- Preguntes a Eva: N20 criteri, Qa cap, E carbonatades

## Next Milestones

- [ ] Settlement phrase parsing, seismic_ab, adjacents orientation
- [ ] Test amb projecte nou real
- [ ] Instal·lació a Eva

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`
