# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-03-14

## Current State

Pipeline complet operatiu. Branca `fix/report-small-fixes` conté 14 millores de polishing (UX wizard + extracció dades + format informe). Pendent merge a main i instal·lació a Eva.

**Flux complet (wizard):**
1. Fase 0+0.5 (Python, ~5s): FileScanner, DPSH, Lab, ICGC, Cadastre, geocode, pressupost PDF
2. Fase 1 (Claude vision, ~30s): plànol, sondeig, penetros via `claude -p` subprocess
3. Fase 1.5 (Claude docs intel, ~10s): pressupostos, DADES CLIENT, noms .msg
4. Fase 2: Eva revisa/ajusta camps pre-omplerts (~30s) — auto-save cada 2s
5. Fase 3: Genera .docx amb auto-scroll al link de descàrrega

**Millores 2026-03-14 (fix/report-small-fixes):**
- Format plantes: "PB+P1" → "Pb+1Pp", superfícies arrodonides a enters
- Docs badge: llindar dinàmic (visionKeys.length) + cache refresh per nous fitxers
- SDK vision desactivat (sense API key pròpia G3DT, evita 2s delay)
- `parcela_projecte_m2`: extracció de JUSTIFICACIO PLANEJAMENT (architect PDF)
- RC cadastral via API Cadastre des de coordenades UTM
- Auto-save wizard (debounced 2s), auto-scroll post-generació
- Tipus edificació: select + input editable
- Noms client/arquitecte en MAJÚSCULES als paràgrafs p047/p054
- Fix stepper duplicat: llista fitxers es doblava després de visió
- Source badges: verd immediat quan Eva canvia un camp + persisit a `_sources`
- `street_address` i `site_municipality` afegits a WIZARD_FIELDS (es perdien al guardar)

**Qualitat audit (Bell-Lloc):** 97.1% amb user_data, 94.9% des de zero

## Active Blockers

Cap.

## Next Milestones

- [ ] Test `parcela_projecte_m2` amb Bell-Lloc4 (re-run visió)
- [x] Crear guia nomenclatura fitxers per Eva (`guides/GUIA-NOMS-FITXERS-EVA.md`)
- [ ] Merge `fix/report-small-fixes` → `main`
- [ ] Test amb projectes restants (Linyola, Castellar, Rubí)
- [ ] Instal·lar a l'ordinador d'Eva
- [ ] Validació amb Eva del flux complet (projecte nou de zero)
- [ ] Category C vocabulary (text secció Materials)
