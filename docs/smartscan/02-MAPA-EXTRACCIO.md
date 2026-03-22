# Mapa d'Extracció — Qui processa què, i què falta
Data: 2026-03-22

## Pipeline Components (referència ràpida)

```
Component           | Fase  | Processa                    | Output
--------------------|-------|-----------------------------|-----------------
SmartScan           | 0     | Tots els fitxers (classifica)| file_mapping.json
FileMiner (regex)   | 0.3   | .xls .xlsx .pdf .txt .doc .docx | Signal objects
Groq LLM (text)     | 0.4   | Fitxers amb <3 signals      | Signal objects
auto_extractor      | 0.5   | DPSH.xls, Lab PDF, pressupost| prefills dict
Vision (Claude/Groq)| 1     | PDFs amb vision_type         | *_extracted.json
ICGC/Cadastre APIs  | 2-3   | UTM coordinates              | geology, adjacents
```

---

## Matriu d'Extracció per Tipus de Fitxer

### .pdf (126 fitxers)

| Subtipus | SmartScan | FileMiner | Groq | Vision | auto_extract | Estat |
|----------|-----------|-----------|------|--------|-------------|-------|
| PENETROS*.pdf | ROLE: dpsh_field_sheet | skip (ref report) | — | **YES: N20, refusal** | DPSH phase | OK |
| SONDEIG*.pdf | ROLE: sondeig_field_sheet | skip | — | **YES: soil layers, SPT** | — | OK |
| A.01*.pdf | ROLE: architect_plan | skip | — | **YES: building data** | — | OK |
| tall*.pdf | ROLE: correlation_section | skip | — | — | — | OK (no extraction needed) |
| pl*situaci*.pdf | ROLE: situation_plan | skip | — | (optional) | — | OK |
| LAB-SIG.pdf | ROLE: lab_results_pdf | skip | — | — | sulfate_mg_kg | OK |
| *GTL*.pdf | ROLE: gtl_report | text mine | Groq | — | — | OK |
| *_informe*.doc/pdf | ROLE: reference_report | text mine | Groq | — | — | OK |
| PRESSUPOST*.pdf | Classified | text mine | Groq | — | architect_company | OK |
| **Cadastral PDFs** (4613172*.pdf) | **unclassified** | **skip** | — | — | — | **GAP** |
| **Architect PDFs in numeric/** (A01_TIPOL, IV_PLANOS, SITE_prop) | **unclassified** | text mine | Groq | **NO** | — | **GAP: no vision** |
| **planol-1.pdf, PLANO 2.pdf, planol 3.pdf** (Alcoletge numeric/) | **unclassified** | text mine | Groq | **NO** | — | **GAP: no vision** |
| **1.0.pdf** (Vilanova numeric/) | **unclassified** | text mine | Groq | **NO** | — | **GAP: unknown** |
| **MULTICA_61.pdf** (Vilanova) | **unclassified** | text mine | Groq | — | — | **GAP: lab multi-test?** |
| Signed acceptance PDFs | classified: informative | skip | — | — | — | OK (low value) |
| PDF/ exports | classified: informative | skip | — | — | — | OK (duplicates) |

**Gaps**: 8+ PDFs in numeric folders with building data that never reach vision extraction.
**Fix**: SmartScan Tier 2 fingerprint identifies architect plans by content → assigns vision_type.

### .xls / .xlsx (29 fitxers)

| Subtipus | SmartScan | FileMiner | Groq | auto_extract | Estat |
|----------|-----------|-----------|------|-------------|-------|
| *_DPSH.xls | ROLE: dpsh_excel | mine labels | — | N20, refusal, Es | OK |
| comanda laboratori*.xls | ROLE: lab_order | mine labels | — | field_dates | OK |
| DADES PER ANAR A CAMP*.xlsx | classified (filename hint) | mine labels | Groq | client, address, municipality, building_type | OK |
| PLAN_COST*.xlsx | classified (filename hint) | mine labels | Groq | expedient, cost (filtered as G3 internal) | OK |
| **MULTICA_61.xls** (Vilanova) | **unclassified** | mine labels | Groq | — | **GAP: need to verify content** |

**Gaps**: 1 file (MULTICA_61.xls). FileMiner may already mine it — need to verify signal output.

### .doc / .docx (33 fitxers)

| Subtipus | SmartScan | FileMiner | Groq | Estat |
|----------|-----------|-----------|------|-------|
| *_informe*.doc | ROLE: reference_report | mine text | Groq | OK |
| *_PORTADA*.doc | classified: informative | skip | — | OK (cover only) |
| *_DETALLAT*.doc | classified: informative | skip | — | OK (our notes) |
| *_portada*.doc | classified: informative | skip | — | OK |
| *_generated*.docx | OUR output | skip | — | OK |
| *_test_*.docx | OUR output | skip | — | OK |
| EXPLICACIÓ*.docx | classified: informative | skip | — | OK (our notes) |
| *_AUDIT_VISUAL.docx | OUR output | skip | — | OK |

**Gaps**: 0. All handled correctly.

### .txt (12 fitxers)

| Subtipus | SmartScan | FileMiner | auto_extract | Estat |
|----------|-----------|-----------|-------------|-------|
| COORDENADES.txt (×5) | unclassified | mine: UTM | UTM phase | OK |
| DADES CLIENT.txt (×1) | unclassified | mine: client, NIF, phone, email | — | OK |
| **DTE.txt (×5)** | **unclassified** | **mine: detects nothing useful** | — | **GAP: invoice date+amount parseable** |
| **CONTACTE.txt (×1)** | **unclassified** | **mine: may detect phone** | — | **PARTIAL: phone detected, name not mapped** |

**Gaps**: DTE.txt has structured data ("EN DATA dd/mm TDTO ... IMPORT ... VCT: dd/mm/yy") that could yield report_date and billing. FileMiner text detectors don't have patterns for this format.
**Fix**: Add `detect_dte_invoice()` detector to FileMiner, or handle in auto_extractor.

### .jpg / .jpeg / .png (105 fitxers) — ALL SKIPPED

| Subtipus | Location | Count | Potential Role | Priority |
|----------|----------|-------|---------------|----------|
| Field photos (P1-P4, SPT, maquina...) | FOTOGRAFIES/ | ~55 | report_photo_* | Phase 6 |
| Geological map screenshots (M1-M12) | ANNEXES/ALTRES/, ANEXOS/OTROS/ | ~20 | figure_geological_map | Phase 6 |
| Situation/points maps (F1 SIT, F2 PUNTS) | ANNEXES/ALTRES/, ANEXOS/OTROS/ | ~5 | figure_situation_map, figure_test_points | Phase 6 |
| Correlation screenshots (F5 TALL) | ANNEXES/ALTRES/ | ~1 | figure_correlation | Phase 6 |
| **PENETROS.jpeg** | FOTOS DE CAMP/ | 1 | dpsh_field_sheet → VISION | **Phase 2 (CRITICAL)** |
| **CROQUIS.jpeg** | FOTOS DE CAMP/ | 1 | field_croquis → VISION | **Phase 2** |
| **ampliació habitatge v2.png** | FOTOS DE CAMP/ | 1 | architect_plan → VISION | **Phase 2** |
| spt alcoletge.png | FOTOS DE CAMP/ | 1 | photo_spt_sample | Phase 6 |
| WhatsApp images (numeric folders) | 25.0493/, 25.0794/ | ~4 | unknown → MUST VIEW | Phase 2 |
| WhatsApp images (FOTOGRAFIES/) | FOTOGRAFIES/ | ~8 | report_photo (field) | Phase 6 |
| WhatsApp image (ACCEPTACIO/) | ACCEPTACIO/ | 1 | unknown → MUST VIEW | Phase 2 |

**Fix**: Phase 2 (image processing) + Phase 6 (report figures/photos).

### .msg (20 fitxers) — ALL SKIPPED

| Subtipus | Location | Count | Size range | Likely content |
|----------|----------|-------|-----------|----------------|
| Pressupost/budget emails | numeric/, root, ACCEPTACIO/ | ~10 | 135KB-7.2MB | Address, architect, **PDF attachments** |
| Confirmation/visit emails | root | ~2 | 288-375KB | Location, **plano attachment** |
| Reply emails (RE_/RV_) | numeric/, ACCEPTACIO/ | ~8 | 135KB-896KB | Thread context, addresses |

**Fix**: Phase 3 (MsgMiner + attachment extraction).

### .FH11 (27 fitxers) — CORRECTLY SKIPPED

No Python reader. PDF exports exist for all (fotografies, plànol, sondeig, tall, mapa geol).

### .json (19 fitxers) — OUR OUTPUTS, CORRECTLY SKIPPED

file_mapping.json (×8), user_data.json (×4), *_extracted.json (×7).

### Thumbs.db (27 fitxers) — CORRECTLY SKIPPED

### .tmp (1 fitxer) — CORRECTLY SKIPPED

---

## Resum de Gaps Accionables

| # | Gap | Files affected | Impact | Fix Phase |
|---|-----|---------------|--------|-----------|
| 1 | Images skipped entirely | 105 files | CRITICAL (PENETROS.jpeg) + report figures | Phase 2 + 6 |
| 2 | .msg emails skipped | 20 files | HIGH (attachments with plans, addresses) | Phase 3 |
| 3 | Architect PDFs in numeric/ not sent to vision | ~6 files | HIGH (building data for 3+ projects) | Phase 2.4 |
| 4 | DTE.txt not parsed | 5 files | LOW (invoice date, billing amount) | Phase 4 |
| 5 | CONTACTE.txt partial | 1 file | LOW (contact name) | Phase 4 |
| 6 | MULTICA_61 unknown | 2 files | MEDIUM (lab data?) | Phase 1 (verify) |
| 7 | Vilanova dpsh_excel not assigned | 1 file | HIGH (N20 data path broken) | SmartScan bug fix |
| 8 | Additional planol PDFs in numeric/ | ~4 files (Alcoletge) | MEDIUM (extra floor plans) | Phase 2.4 |

---

## Pipeline Coverage Matrix (per project)

| Variable | CASTELLAR | RUBI | LINYOLA | BELL-LLOC | ALCOLETGE | VILANOVA | ANCILES |
|----------|-----------|------|---------|-----------|-----------|----------|---------|
| client_name | DADES CAMP | DADES CAMP | DADES CAMP | DADES CLIENT | DADES CAMP | DADES CAMP | DADES CAMP |
| client_nif | — | — | — | DADES CLIENT | — | — | — |
| client_phone | — | — | CONTACTE.txt | DADES CLIENT | — | — | — |
| street_address | DADES CAMP | DADES CAMP | DADES CAMP | DADES CAMP | DADES CAMP | DADES CAMP | DADES CAMP |
| municipality | folder+DADES | folder+DADES | folder+DADES | folder+DADES | folder+DADES | folder+DADES | folder+DADES |
| architect_name | pressupost? | pressupost? | planol vision | planol vision | planol vision | **MISSING** | **A01_TIPOL GAP** |
| building_type | DADES CAMP | DADES CAMP | DADES CAMP | planol vision | planol vision | **MISSING** | **A01_TIPOL GAP** |
| num_floors | DADES CAMP | DADES CAMP | DADES CAMP | planol vision | planol vision | **MISSING** | **A01_TIPOL GAP** |
| N20 data | DPSH.xls+vision | DPSH.xls+vision | DPSH.xls+vision | DPSH.xls+vision | DPSH.xls+vision | **DPSH.xls GAP** | DPSH.xls+vision |
| soil layers | sondeig vision | — | — | sondeig vision | — | — | sondeig vision |
| report photos | **GAP (all)** | **GAP (all)** | **GAP (all)** | **GAP (all)** | **GAP (all)** | **GAP (all)** | **GAP (all)** |
| report figures | **GAP (all)** | **GAP (all)** | **GAP** | **GAP** | **GAP** | **GAP (all)** | **GAP** |
