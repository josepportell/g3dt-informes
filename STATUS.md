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

### "Read First, Decide After" — SmartScan v2 (feat/smartscan)
Pla complet: `docs/smartscan/PLA-READ-FIRST-DECIDE-AFTER.md`
Inventari: `docs/smartscan/01-INVENTARI-FITXERS.md` (375 fitxers, 112 gaps)
Mapa: `docs/smartscan/02-MAPA-EXTRACCIO.md`

- [ ] **Phase 2: Imatges** — 105 imatges ignorades. PENETROS.jpeg (Alcoletge) = DPSH data ONLY as JPEG. Tier 1 patterns + Tier 2 fingerprint + Tier 3 Groq vision
- [ ] **Phase 3: Emails .msg** — 20 emails ignorats, alguns amb 5-7MB (adjunts PDF/plànols). MsgMiner + extracció d'adjunts
- [ ] **Phase 4: Directoris** — FOTOGRAFIES/ fora de _SKIP_DIRS, PDF/ segueix skip
- [ ] **Phase 5: Layouts variant** — prompts vision resilients a formats d'arquitecte diferents
- [ ] **Phase 6: Figures i fotos** — 0% cobertura actual. Classificar imatges per slot de l'informe (figure_situation_map, photo_dpsh_equipment, etc.)

### Bugs trobats a l'inventari
- [ ] **ANEXOS no reconegut com a scope per dpsh_excel** — Vilanova (4001671) té DPSH.xls a ANEXOS/ però SmartScan només reconeix ANNEXES/ANEJOS. Cal afegir ANEXOS a scopes
- [ ] **MULTICA_61.xls/pdf** (Vilanova) — Fitxer desconegut, potser resultats multi-assaig de laboratori. Verificar contingut manualment

### Altres pendents
- [ ] **`cadastre_address` variable Groq** — defer, lookup progressiu funciona bé
- [ ] Groq Developer plan (elimina rate limit waits)
- [ ] Activar SmartScan per defecte (treure feature flag)
- [ ] Suport castellà per informes
- [ ] Merge branques pendents → `main`
- [ ] Instal·lar a l'ordinador d'Eva

## Next Milestones

- [x] SmartScan v1: classificació per contingut + pestanya wizard
- [x] FileMiner: extracció de dades dels fitxers + wizard alternatives
- [x] Phase G: Groq LLM miner per casos edge
- [x] Post-Anciles: multi-província, cache bypass, variable mapping, .doc support
- [x] Geocodificació progressiva (ConsultaMunicipio → ConsultaVia → DNPLOC)
- [x] Test pipeline complet amb 7 projectes
- [x] Phase 1: Inventari complet 375 fitxers + mapa d'extracció (112 gaps identificats)
- [ ] Phase 2-6: "Read First, Decide After" (imatges, emails, figures)
- [ ] Instal·lar a l'ordinador d'Eva
