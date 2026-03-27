# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-26

## Current State

**Report Readiness panel + Cadastre robustness fixes.**

- **164/164 tests passen**
- **Report Readiness** (Dev tab): mostra 43 variables reals de l'informe amb % d'ompliment per categoria
  - Bell-Lloc: 100% (43/43), Castellar: 60.5%, Alcoletge: 58.5%
  - Executa pipeline complet (extract + sections + càlculs) sense generar .docx
  - 9 categories: Identificació, Ubicació, Edificació, Camp DPSH/Sondeig/Lab, Geologia, Geotècnia, Càlculs
- **Cadastre circuit breaker**: ConsultaVia HTTP 500 ja no bloqueja el servidor (abort immediat)
- **Address parsing**: `#7`, `nº7`, `Nº 12`, `núm. 5` ara es parsegen correctament

**Pipeline (actualitzat):**
```
Phase 0:    SmartScan v2   → file_mapping.json (3 tiers: regex, fingerprint, Groq vision)
Phase 0.3:  FileMiner      → signals (regex) + MsgMiner (emails + adjunts)
Phase 0.4:  GroqMiner      → signals (LLM, gap-filling, threshold adaptatiu)
Phase 0.5:  auto_extract   → prefills (DPSH, Lab, ICGC, Cadastre)
Phase 1:    Vision         → planol/sondeig/dpsh_extracted.json (PDFs + imatges)
Phase 2:    HTTP APIs      → geocode progressiu, adjacents, geologia
Phase 3:    Wizard         → Eva revisa + genera
Phase 4:    Report         → .docx amb figures/fotos per rol SmartScan
```

**Qualitat audit (Bell-Lloc):** 97.1% amb user_data

## Active Blockers

- Merge `feat/smartscan` → `main` (10+ commits pendents)
- Instal·lar a l'ordinador d'Eva
- Silvia: extensió 2 setmanes pendent d'aprovació

## Completed — SmartScan v2 (2026-03-22)

| Phase | Què | Impacte |
|-------|-----|---------|
| 1 | Inventari 375 fitxers + mapa d'extracció | 112 gaps identificats |
| 2.1 | Tier 1 patrons imatge | CROQUIS.jpeg, PENETROS.jpeg, figures (F1 SIT, F2 PUNTS...) |
| 2.2 | Tier 2 fingerprint imatge (Pillow) | Color/EXIF separa documents de fotos, cost $0 |
| 2.3 | Tier 3 Groq vision imatges | WhatsApp plànols → architect_plan (100% accuracy) |
| 2.4 | Vision pipeline routing | Imatges entren al pipeline d'extracció com PDFs |
| 3 | MsgMiner + adjunts | 20 emails processats, A01_TIPOL.pdf recuperat d'adjunts |
| 4.1 | FOTOGRAFIES desbloquejat | Fora de _SKIP_DIRS |
| 5 | Prompts resilients | Format-agnòstic, accepta 6 tipus de document |
| 6 | Figures/fotos per rol | F1 SIT → fig_cadastre, F4 MGEOL → fig_geological |

**Bugs resolts:** ANEXOS scope per dpsh_excel (Vilanova)

## Pending

### Bugs/verificacions
- [ ] **MULTICA_61.xls/pdf** (Vilanova) — Verificar contingut manualment
- [ ] Regenerar file_mapping.json per tots els projectes amb SmartScan v2

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
- [x] Geocodificació progressiva (7/7 projectes)
- [x] Test pipeline complet amb 7 projectes
- [x] **SmartScan v2 "Read First, Decide After" — Phase 1-6 complet**
- [ ] Testing end-to-end amb SmartScan v2 (regenerar file_mappings, verificar wizard)
- [ ] Merge `feat/smartscan` → `main`
- [ ] Instal·lar a l'ordinador d'Eva
