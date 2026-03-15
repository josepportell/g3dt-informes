# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-15

## Current State

Pipeline complet operatiu. Branca `fix/report-small-fixes` conté millores de polishing (UX wizard + extracció dades + format informe + normalitzador visió). Pendent merge a main i instal·lació a Eva.

**Flux complet (wizard):**
1. Fase 0+0.5 (Python, ~5s): FileScanner, DPSH, Lab, ICGC, Cadastre, geocode, pressupost PDF
2. Fase 1 (Claude vision, ~30s): plànol, sondeig, penetros via `claude -p` subprocess
3. Fase 1.5 (Claude docs intel, ~10s): pressupostos, DADES CLIENT, noms .msg
4. Fase 2: Eva revisa/ajusta camps pre-omplerts (~30s) — auto-save cada 2s
5. Fase 3: Genera .docx amb auto-scroll al link de descàrrega

**Millores 2026-03-15 (fix/report-small-fixes):**
- **Vision normalizer** (`automation/vision_normalizer.py`): normalitza claus SPT no-deterministes de Claude vision (spt_data/spt_test → spt_in_dpsh; spt_tests → spt_results; test_name → test_id)
- **Refusal exact**: normalitzador prefereix `refusal_exact_m` sobre `refusal_depth_m` (Rubí: 4.55/3.58/3.13 vs 4.60/3.60/3.20)
- **Cota d'inici**: sondeig `elevation_z` (camp) té prioritat sobre ICGC MDT (satèl·lit). Bell-Lloc: +199.50 vs +199.00
- **Prompts endurit**: exemples SPT explícits a skill + SDK prompts per guiar visió ~99%
- Tots els consumidors de dpsh/sondeig JSON usen normalitzador (report_generator, report_data, wizard, section2)

**Qualitat audit (Bell-Lloc):** 97.1% amb user_data, 94.9% des de zero

## Active Blockers

Cap.

## Next Milestones

- [ ] Merge `fix/report-small-fixes` → `main`
- [ ] Test amb projectes restants (Linyola, Castellar, Rubí)
- [ ] Instal·lar a l'ordinador d'Eva
- [ ] Validació amb Eva del flux complet (projecte nou de zero)
- [ ] Category C vocabulary (text secció Materials)
