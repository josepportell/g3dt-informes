# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-14

## Current State

Pipeline complet operatiu i preparat per instal·lar a l'ordinador d'Eva. Wizard web integrat — Eva selecciona projecte, clica "Llegir PDFs de camp", revisa prefills, genera informe.

**Flux complet (wizard):**
1. Fase 0+0.5 (Python, ~5s): FileScanner v2.2, DPSH, Lab, ICGC, Cadastre, geocode, pressupost PDF
2. Fase 1 (Claude vision, ~30s): botó al wizard invoca `claude -p` via subprocess
3. **Fase 1.5 (Claude docs intel, ~10s): lectura intel·ligent de documents de text** ← NOU
4. Fase 2: Eva revisa/ajusta camps pre-omplerts (~30s)
5. Fase 3: Genera .docx

**Fase 1.5 — Lectura intel·ligent de documents:**
Claude Code llegeix fitxers de text del projecte (pressupostos PDF, DADES CLIENT.txt, noms .msg) per extreure metadades que Python regex i visió no capturen. Actua com a "gap filler" — només omple camps que les fases anteriors no han trobat. Resultat a `validation/docs_extracted.json`. Camps actuals: `architect_company`, `building_category`, `num_planned_dpsh`, `num_planned_sondeig`, `num_planned_spt`.

**Qualitat audit (Bell-Lloc):** 97.1% amb user_data, 94.9% des de zero

## Active Blockers

Cap blocker actiu.

## Branques

- `main` — codi estable
- `fix/report-small-fixes` — uppercase noms, pressupost PDF extraction, Phase 1.5 docs intel
- `feat/vision-wizard-integration` — botó visió + sondeig annex (pendent merge)

## Desplegament

- Guia d'instal·lació completa: `guides/GUIA-INSTALLACIO-EVA.md`
- Scripts escriptori: `scripts/G3DT-Wizard.bat` + `scripts/G3DT-Claude.bat`

## Next Milestones

- [ ] Merge `fix/report-small-fixes` → `main`
- [ ] Instal·lar a l'ordinador d'Eva (seguint guia d'instal·lació)
- [ ] Validació amb Eva del flux complet (projecte nou de zero)
- [ ] Merge `feat/vision-wizard-integration` → `main`
- [ ] Ampliar Phase 1.5 amb més camps (segons necessitats d'Eva)
- [ ] Category C vocabulary (text d'Eva per secció Materials)
- [ ] Test multi-nivell amb Linyola (sòls expansius)
