# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-16

## Current State

Pipeline complet operatiu. Branca `improve/adjacents-section-2.1.1` amb fixes consolidats.

**`improve/adjacents-section-2.1.1`** (10 commits):
- Sondeig adjacents per geometria WFS (arestes reals del polígon, no centroide)
- Neteja noms carrers castellà→català (ANTONIO→Antoni, Y→i, cognoms escurçats)
- Enriquiment veïns via DNPRC ("parcel·la buida" / "construcció de 2 plantes" vs genèric)
- Geocodificació des d'adreça plànol (coords DPSH poden ser en parcel·la veïna)
- Fix elevation_z: normalitzador centralitzat (prompt + regex fallback). Testejat Bell-Lloc4 ✓
- Fix noms carrers bruts: neteja municipi trailing als adjacents (wizard + report)
- Fix frase P66: `location_sentence` amb gramàtica catalana correcta (entre/al/a la/a l')
- Rename `adjacent_south_street` → `adjacent_nearest_street` (cerca totes direccions)
- Carpeta numèrica (25.0647/) ja no s'exclou del scanner

**`fix/report-small-fixes`** (pendent merge anterior):
- Vision normalizer, refusal exact, cota sondeig > ICGC, prompts endurit

**Qualitat audit (Bell-Lloc):** 97.1% amb user_data
**Test Bell-Lloc4:** elevation_z=199.50 ✓, location_sentence ✓

## Active Blockers

Cap blocker actiu.

## Next Milestones

- [ ] Merge `improve/adjacents-section-2.1.1` → `main`
- [ ] Merge `fix/report-small-fixes` → `main`
- [ ] Test amb projectes restants (Linyola, Castellar, Rubí)
- [ ] Instal·lar a l'ordinador d'Eva
