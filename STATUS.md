# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-21

## Current State

**FileMiner v1.0 implementat i verificat** — extreu dades de dins els fitxers (no només classifica).

- **106/106 tests passen** (50 FileMiner + 56 SmartScan)
- 4 miners: Excel, PDF, Text, Docx — amb extracció d'imatges
- 67 etiquetes CA+ES mapeades a variables d'informe
- Competició de senyals: la font més fiable guanya, Eva veu alternatives
- Integrat a auto_extractor.py (Phase 0.3) i wizard UI (+N badges)
- 7-9 prefills nous per projecte (client, adreça, NIF, telèfon, municipi...)

**SmartScan v1.0 implementat** — classificació en 3 tiers (regex, fingerprint, vision).

- Tier 1 detecta 95%+ dels fitxers pel nom (CA + ES)
- Feature flag `G3DT_USE_SMARTSCAN=1`
- Backward compatible amb FileMapping

**Pipeline complet:**
```
Phase 0:    SmartScan     → file_mapping.json
Phase 0.3:  FileMiner     → signals + alternatives
Phase 0.5:  auto_extract  → prefills (DPSH, Lab, ICGC, Cadastre)
Phase 1:    Claude vision → planol/sondeig/penetros
Phase 2:    Wizard        → Eva revisa + genera
```

**Qualitat audit (Bell-Lloc):** 97.1% amb user_data

## Active Blockers

- Confirmació formal de Sílvia per l'ampliació de 2 setmanes
- Merge branques pendents → `main`

## Next Milestones

- [x] SmartScan: classificació per contingut + pestanya wizard
- [x] FileMiner: extracció de dades dels fitxers + wizard alternatives
- [ ] Phase G: Groq LLM miner per casos edge (layouts no estàndard)
- [ ] Activar SmartScan per defecte (treure feature flag)
- [ ] Suport castellà per informes
- [ ] Merge branques pendents → `main`
- [ ] Test pipeline complet amb 3 projectes nous (Alcoletge, Vilanova, Anciles)
- [ ] Instal·lar a l'ordinador d'Eva
