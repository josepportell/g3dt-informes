# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-22

## Current State

**Pipeline complet amb suport multi-província i geocodificació progressiva.**

- **156/156 tests passen** (29 Groq + 50 FileMiner + 56 SmartScan + 21 Cadastre progressiu)
- Testat amb 7 projectes reals: Bell-Lloc (32/34), Anciles (31/34), Castellar (26/34), Linyola (26/34), Vilanova (21/34), Rubí (22/34), Alcoletge
- Geocodificació progressiva: ConsultaMunicipio → ConsultaVia → DNPLOC (7/7 projectes resolts)
- Multi-província: Huesca, Barcelona, Lleida — tot funciona
- Cache bypass: `G3DT_NO_CACHE=1` per testing
- Selector de model Groq al wizard UI

**Pipeline:**
```
Phase 0:    SmartScan      → file_mapping.json
Phase 0.3:  FileMiner      → signals + alternatives (regex)
Phase 0.4:  GroqMiner      → signals (LLM, gap-filling)
Phase 0.5:  auto_extract   → prefills (DPSH, Lab, ICGC, Cadastre)
Phase 1:    Groq Vision    → planol/sondeig/dpsh_extracted.json
Phase 2:    HTTP APIs      → geocode progressiu, adjacents, geologia
Phase 3:    Wizard         → Eva revisa + genera
```

**Qualitat audit (Bell-Lloc):** 97.1% amb user_data

## Active Blockers

- Confirmació formal de Sílvia per l'ampliació
- Merge branques pendents → `main`

## Pending (to implement)

- [ ] **Imatges standalone com a font de visió** — WhatsApp photos de plànols (IMG-*.jpg) no es processen; FileMiner les ignora. Rubí té plànols de planta com a .jpg sense PDF equivalent → superficie_construida queda buida. Cal: classificació d'imatges per contingut (SmartScan), Groq Vision acceptant paths d'imatge directament, prompt per "floor plan image"
- [ ] **`cadastre_address` variable Groq** — extracció estructurada d'adreça pel LLM (street_name, house_number, municipality, province per separat). Defer — el lookup progressiu ja funciona bé amb `_parse_address()`
- [ ] Groq Developer plan (elimina rate limit waits)
- [ ] Activar SmartScan per defecte (treure feature flag)
- [ ] Suport castellà per informes
- [ ] Merge branques pendents → `main`
- [ ] Instal·lar a l'ordinador d'Eva

## Next Milestones

- [x] SmartScan: classificació per contingut + pestanya wizard
- [x] FileMiner: extracció de dades dels fitxers + wizard alternatives
- [x] Phase G: Groq LLM miner per casos edge
- [x] Post-Anciles: multi-província, cache bypass, variable mapping, .doc support
- [x] Geocodificació progressiva (ConsultaMunicipio → ConsultaVia → DNPLOC)
- [x] Test pipeline complet amb 7 projectes (Bell-Lloc, Anciles, Castellar, Rubí, Linyola, Alcoletge, Vilanova)
- [ ] Imatges standalone com a font de visió (WhatsApp floor plans)
- [ ] Instal·lar a l'ordinador d'Eva
