# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-14

## Current State

Pipeline complet operatiu i preparat per instal·lar a l'ordinador d'Eva. Wizard web integrat — Eva selecciona projecte, clica "Llegir PDFs de camp", revisa prefills, genera informe.

**Flux complet (wizard):**
1. Fase 0+0.5 (Python, ~5s): FileScanner v2.2, DPSH, Lab, ICGC, Cadastre, geocode
2. Fase 1 (Claude vision, ~5 min): botó al wizard invoca `claude -p` via subprocess
3. Fase 2: Eva revisa/ajusta camps pre-omplerts (~30s)
4. Fase 3: Genera .docx

**Qualitat audit (Bell-Lloc):** 97.1% amb user_data, 94.9% des de zero

## Active Blockers

Cap blocker actiu.

## Branques

- `main` — codi estable
- `feat/vision-wizard-integration` — botó visió + sondeig annex (pendent merge)

## Desplegament

- Guia d'instal·lació completa: `guides/GUIA-INSTALLACIO-EVA.md`
- Scripts escriptori: `scripts/G3DT-Wizard.bat` + `scripts/G3DT-Claude.bat`

## Next Milestones

- [ ] Instal·lar a l'ordinador d'Eva (seguint guia d'instal·lació)
- [ ] Validació amb Eva del flux complet (projecte nou de zero)
- [ ] Merge `feat/vision-wizard-integration` → `main`
- [ ] Category C vocabulary (text d'Eva per secció Materials)
- [ ] Test multi-nivell amb Linyola (sòls expansius)
