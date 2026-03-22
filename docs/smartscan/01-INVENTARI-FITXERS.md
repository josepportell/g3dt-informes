# Inventari Complet de Fitxers — SmartScan v2
Data: 2026-03-22

## Llegenda d'estat

- **ROLE** = SmartScan role assigned, processed by pipeline
- **MINED** = FileMiner extracts signals (text/regex)
- **VISION** = Claude/Groq vision extracts structured data
- **GAP** = File has useful data but system does NOT process it
- **SKIP** = Correctly ignored (system artifact, unreadable, or duplicate)
- **OUR** = Our generated output

## Resum global

| Projecte | Total fitxers | Processed | Gap | Skip |
|----------|--------------|-----------|-----|------|
| CASTELLAR | 76 | 18 | 21 | 37 |
| RUBI | 53 | 14 | 15 | 24 |
| LINYOLA | 43 | 15 | 12 | 16 |
| LINYOLA2 | 2 | 0 | 0 | 2 |
| BELL-LLOC | 68 | 21 | 13 | 34 |
| ALCOLETGE | 42 | 11 | 16 | 15 |
| VILANOVA | 46 | 9 | 20 | 17 |
| ANCILES | 45 | 13 | 15 | 17 |
| **TOTAL** | **375** | **101** | **112** | **162** |

**112 files with potential data are NOT being processed.**

---

## 3001621 CASTELLAR DEL VALLES

### Numeric folder: 25.0493/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| DADES PER ANAR A CAMP_v1.xlsx | MINED | FileMiner(Excel) | client, address, municipality, contact, building_type |
| PLAN_COST_CATELLAR DEL VALLÈS.xlsx | MINED | FileMiner(Excel) | expedient, cost (G3 internal → filtered) |
| PRESSUPOST GEOTEC.CASTELLAR DEL VALLES.pdf | MINED | FileMiner(PDF)+Groq | architect_company, project address |
| PRESSUPOST GEOTEC.MODF.CASTELLAR DEL VALLES.pdf | MINED | FileMiner(PDF)+Groq | architect_company (modified version) |
| PRESSUPOST 3 HAB CASTELLAR DEL VALLÈS.msg | **GAP** | — | May contain project address, contact, architect in body/attachments |
| WhatsApp Image 2025-10-20 at 13.00.25.jpeg | **GAP** | — | Site photo (confirmed: terrain view, LOW value) |
| WhatsApp Image 2025-10-20 at 13.00.25 (1).jpeg | **GAP** | — | Site photo (likely same scene, LOW value) |
| Thumbs.db | SKIP | — | Windows cache |

### Root

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| PENETROS + SONDEIG.pdf | ROLE | dpsh_field_sheet + sondeig_field_sheet → VISION | N20, refusal, soil layers |
| tall.pdf | ROLE | correlation_section | Geological correlation |
| 4687-GTL-25 Castellar del Vallés.pdf | ROLE | gtl_report → MINED | Lab results |
| comanda laboratori_3001621_CASTELLAR DEL VALLÈS.xls | ROLE | lab_order → MINED | Lab data, field dates |
| 3001621_informe_v0.doc | ROLE | reference_report → MINED | Reference values for comparison |
| DTE.txt | **GAP** | — | Invoice: "EN DATA 27/10 TDTO AQUEST INFORME PER UN IMPORT DE 1548,80€ - VCT: 01/12/25" → report_date, billing |
| Re_ ESTUDI GEOTÈCNIC VERSIÓ CASTELLAR DEL VALLES.msg | **GAP** | — | Email: may contain corrections, project details |
| 3001621_PORTADA_25.doc | SKIP | Informative (cover) | Only title page |
| 3001621_generated.docx | OUR | — | Our output |
| 3001621_test_*.docx (×4) | OUR | — | Our test outputs |
| file_mapping.json | OUR | — | Our output |

### ANNEXES/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| 3001621_DPSH.xls | ROLE | dpsh_excel → auto_extractor | N20, refusal, Es_settlement |
| ALTRES/COORDENADES.txt | MINED | FileMiner(Txt) | UTM coordinates |
| ALTRES/M1-M12.png (×12) | **GAP** | — | Geological maps for report figures (figure_geological_map) |
| ALTRES/6_mapa Geologic_CAT_VS.FH11 | SKIP | Unreadable (FreeHand) | PDF export exists |
| *.FH11 (×4) | SKIP | Unreadable (FreeHand) | PDF exports exist in PDF/ |
| ALTRES/Thumbs.db | SKIP | Windows cache | — |
| EF7DB361.tmp | SKIP | Temp file | — |

### FOTOGRAFIES/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| P1.jpg, P2.jpg, P3.jpg, P4.jpg | **GAP** | — | report_photo: photo_test_point |
| DPSH/maquina_dpsh.jpg (×3) | **GAP** | — | report_photo: photo_dpsh_equipment |
| SONDEIG/maquina_sondeig.jpg | **GAP** | — | report_photo: photo_sondeig_equipment |
| vista_general_1.jpg | **GAP** | — | report_photo: photo_site_overview |
| detall_materials.jpg (×2) | **GAP** | — | report_photo: photo_spt_sample |
| Imagen de WhatsApp *.jpg (×2) | **GAP** | — | report_photo: probably site overview |
| S1/Imagen de WhatsApp *.jpg (×3) | **GAP** | — | report_photo: sondeig equipment |
| Thumbs.db (×2) | SKIP | Windows cache | — |

### ACCEPTACIO/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| PRESSUPOST GEOTEC CASTELLAR DEL.....pdf | MINED | auto_extractor(pressupost) | architect_company |
| Thumbs.db | SKIP | Windows cache | — |

### PDF/, PDF-V0/ (exported copies)

All 16 files → SKIP (exported duplicates). Exceptions already handled:
- PDF/ANNEXES/LAB-SIG.pdf → ROLE: lab_results_pdf
- PDF/ANNEXES/3001621_sondeig.pdf → ROLE: sondeig_annex (via SmartScan)

### validation/

| dpsh_extracted.json, sondeig_extracted.json | OUR | Vision cache | — |

---

## 3001631 RUBI

### Numeric folder: 25.0794/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| DADES PER ANAR A CAMP_v1.xlsx | MINED | FileMiner(Excel) | client, address, municipality |
| PLAN_COST_RUBI.xlsx | MINED | FileMiner(Excel) | expedient, cost |
| PRESSUPOST GEOTEC.RUBI.pdf | MINED | FileMiner(PDF)+Groq | architect_company |
| IMG-20251104-WA0015.jpg | **GAP** | — | WhatsApp image. Could be site plan or photo. MUST VIEW |
| IMG-20251104-WA0016.jpg | **GAP** | — | WhatsApp image. Could be site plan or photo. MUST VIEW |
| PRESSU.msg | **GAP** | — | Budget email: address, contact, architect |
| RE_ PRESSU.msg | **GAP** | — | Reply email: address, contact |
| Thumbs.db | SKIP | Windows cache | — |

### Root

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| 3001631 - PENETROS.pdf | ROLE | dpsh_field_sheet → VISION | N20, refusal |
| tall.pdf | ROLE | correlation_section | — |
| 4703-GTL-25 Rubí.pdf | ROLE | gtl_report → MINED | Lab results |
| comanda laboratori_3001631_RUBI.xls | ROLE | lab_order → MINED | Lab data |
| 3001631_informe.doc | ROLE | reference_report → MINED | Reference values |
| Thumbs.db | SKIP | Windows cache | — |
| 3001631_PORTADA_25.doc | SKIP | Cover | — |
| 3001631_generated.docx | OUR | — | — |
| 3001631_test_validation.docx | OUR | — | — |
| file_mapping.json, user_data.json | OUR | — | — |

### ANNEXES/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| 3001631_DPSH.xls | ROLE | dpsh_excel | N20, refusal |
| ALTRES/COORDENADES.txt | MINED | FileMiner(Txt) | UTM coordinates |
| Altres/F1 UBI.png | **GAP** | — | figure_situation_map |
| Altres/F2 UBI PUNTS.png | **GAP** | — | figure_test_points |
| Altres/F3 VG.png | **GAP** | — | figure (vista general?) |
| Altres/F4 MGEOL.png | **GAP** | — | figure_geological_map |
| Altres/F5 TALL.png | **GAP** | — | figure_correlation |
| Altres/m1-m5.png (×5) | **GAP** | — | figure_geological_map (map screenshots) |
| *.FH11 (×4) | SKIP | Unreadable | PDF exports exist |
| Altres/Thumbs.db | SKIP | Windows cache | — |

### FOTOGRAFIES/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| P1.jpg, P2.jpg, P3.jpg | **GAP** | — | photo_test_point |
| SPT1.jpg | **GAP** | — | photo_spt_sample |
| Imatge de WhatsApp *.jpg (×2) | **GAP** | — | photo (field) |
| Thumbs.db | SKIP | — | — |

### ACCEPTACIO/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| WhatsApp Image 2025-11-13 at 11.55.57.jpeg | **GAP** | — | Acceptance signature? MUST VIEW |
| Thumbs.db | SKIP | — | — |

### PDF/ (exported) — 8 files SKIP. Exception: LAB-SIG.pdf → ROLE, plànol de situació → ROLE

---

## 4001607 LINYOLA

### Numeric folder: 25.0616/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| DADES PER ANAR A CAMP_v1.xlsx | MINED | FileMiner(Excel) | client, address, municipality |
| PLAN_COST_LINYOLA.xlsx | MINED | FileMiner(Excel) | expedient, cost |
| Punts de Sondeig_Silvia_Jaume.pdf | **GAP** | — | Architect plan (original, before redraw). Address, promotor, architect |
| 2_02B_DG_Silvia_Jaume.pdf | **GAP** | — | Architect document. MUST VIEW — may have building details |
| 25·0616.pdf | **GAP** | — | Unknown PDF. MUST VIEW |
| pressupost geotècnic.msg | **GAP** | — | Budget email (7.2MB!) — likely has PDF attachments |
| RV_ pressupost geotècnic.msg | **GAP** | — | Forward of budget (7.2MB) — attachments |
| RE_ pressupost geotècnic.msg | **GAP** | — | Reply email |

### Root

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| PENETROS.pdf | ROLE | dpsh_field_sheet → VISION | N20 |
| tall.pdf | ROLE | correlation_section | — |
| pl situ.pdf | ROLE | situation_plan | — |
| 4672-GTL-25 Linyola.pdf | ROLE | gtl_report → MINED | Lab |
| comanda laboratori_4001607_LINYOLA.xls | ROLE | lab_order → MINED | Lab data |
| 4001607_informe.doc | ROLE | reference_report → MINED | Reference |
| Punts de Sondeig_Silvia_Jaume (1).pdf | ROLE | architect_plan → VISION | Building data |
| Punts de Sondeig_Silvia_Jaume (1)_REDIBUIX.pdf | **GAP** | — | Redraw of architect plan (may have cleaner data) |
| DTE.txt | **GAP** | — | Invoice data: date, amount |
| CONTACTE.txt | **GAP** | — | "Sílvia Eroles Balagueró telf: 618 10 86 12" → client_phone, contact_name |
| RV_ Realització geotècnic.msg | **GAP** | — | Email: project confirmation |
| 4001607_PORTADA_25.doc | SKIP | Cover | — |
| 4001607_test_validation.docx | OUR | — | — |
| Thumbs.db | SKIP | — | — |
| file_mapping.json | OUR | — | — |

### ANNEXES/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| 4001607_DPSH.xls | ROLE | dpsh_excel | N20 |
| ALTRES/COORDENADES.txt | MINED | FileMiner(Txt) | UTM |
| *.FH11 (×3) | SKIP | Unreadable | — |

### FOTOGRAFIES/ — 7 files: P1-P3.jpg (GAP: photo_test_point), WhatsApp ×3 (GAP: photo), Thumbs.db (SKIP)

### ACCEPTACIO/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| G3DT_Silvia_Jaume signat.pdf | **GAP** | — | Signed acceptance. May have client data |
| RV_ Realització geotècnic.msg | **GAP** | — | Email forward |

### PDF/ — 9 files SKIP (exports). Exception: lab-sig.pdf → ROLE

---

## 4001612 BELL-LLOC

### Numeric folder: 25.0647/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| DADES PER ANAR A CAMP_v1.xlsx | MINED | FileMiner(Excel) | client, address |
| PLAN_COST_BELL-LLOC.xlsx | MINED | FileMiner(Excel) | cost |
| PRESSUPOST GEOTEC.BELL-LLOC.pdf | MINED | auto_extractor(pressupost) | architect_company |
| A.01.pdf | **GAP** | — | DUPLICATE of root A.01.pdf (architect plan). Lower priority |
| 4613172CG1141S0001SU-15.pdf | **GAP** | — | Cadastral reference PDF. May have parcel data, address |
| 4613173CG1141S0001ZU-13.pdf | **GAP** | — | Cadastral reference PDF. Same |
| Pressupost C1 - Bell-lloc *.msg | **GAP** | — | Budget email (1.2MB) — likely attachments |
| RE_ Pressupost C1 - Bell-lloc *.msg | **GAP** | — | Reply (896KB) — attachments |
| Thumbs.db | SKIP | — | — |

### Root

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| A.01.pdf | ROLE | architect_plan → VISION | All building data |
| A.01 amb punts.pdf | ROLE | architect_plan_with_points → VISION | Test point locations |
| PENETROS.pdf | ROLE | dpsh_field_sheet → VISION | N20 |
| SONDEIG.pdf | ROLE | sondeig_field_sheet → VISION | Soil layers, SPT |
| tall.pdf | ROLE | correlation_section | — |
| pl. situaci.pdf | ROLE | situation_plan | — |
| 4677-GTL-25 Bell-Lloc d'Urgell.pdf | ROLE | gtl_report → MINED | Lab |
| comanda laboratori_4001612_BELL-LLOC.xls | ROLE | lab_order → MINED | Lab data |
| 4001612_informe.doc | ROLE | reference_report → MINED | Reference |
| EXPLICACIÓ DETALLS.docx | SKIP | Informative (explanation) | Project explanation (our dev notes) |
| 4001612_PORTADA_25.doc | SKIP | Cover | — |
| 4001612_informe_DETALLAT*.doc (×2) | SKIP | Informative (detailed) | — |
| 4001612_AUDIT_VISUAL.docx | OUR | — | — |
| 4001612_generated.docx | OUR | — | — |
| 4001612_test_fase2.docx | OUR | — | — |
| Thumbs.db | SKIP | — | — |
| ~$01612_*.doc (×2) | SKIP | Word lock file | — |
| file_mapping.json, user_data.json | OUR | — | — |

### ANNEXES/ — DPSH.xls (ROLE), COORDENADES.txt (MINED), *.FH11 ×4 (SKIP)

### ACCEPTACIO/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| DADES CLIENT.txt | MINED | FileMiner(Txt) | client_name, client_nif, client_address, client_phone, client_email |
| PRESSUPOST GEOTEC.BELL-LLOCsgtJBN.pdf | MINED | auto_extractor | architect_company |

### FOTOGRAFIES/ — 13 files: DPSH/P1-P2, WhatsApp×5, SONDEIG/WhatsApp×4 (all GAP: report photos), Thumbs.db×3 (SKIP)

### PDF/, PDF V0/ — 18 files SKIP (exports). Exceptions: LAB-SIG.pdf (ROLE), sondeig.pdf (ROLE: sondeig_annex)

### validation/ — 3 JSON files (OUR)

---

## 4001670 ALCOLETGE

### Numeric folder: 26.0049/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| DADES PER ANAR A CAMP_v1.xlsx | MINED | FileMiner(Excel) | client, address |
| PLAN_COST_ALCOLETGE.xlsx | MINED | FileMiner(Excel) | cost |
| PRESSUPOST GEOTEC.ALCOLETGE.pdf | MINED | auto_extractor | architect_company |
| A.01.pdf | **GAP** | — | DUPLICATE of root A.01.pdf |
| planol-1.pdf | **GAP** | — | Additional floor plan from architect. MUST VIEW |
| PLANO 2.pdf | **GAP** | — | Additional floor plan from architect. MUST VIEW |
| planol 3.pdf | **GAP** | — | Additional floor plan from architect. MUST VIEW |
| geotècnic Ampliació Albert Sans *.msg | **GAP** | — | Email (532KB) — project details |
| RE_ geotècnic Ampliació *.msg | **GAP** | — | Reply email (360KB) |

### Root

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| A.01.pdf | ROLE | architect_plan → VISION | Building data |
| PENETROS.pdf | ROLE | dpsh_field_sheet → VISION | N20 |
| tall.pdf | ROLE | correlation_section | — |
| comanda laboratori_4001670_ALCOLETGE.xls | ROLE | lab_order → MINED | Lab data |
| 4001670_informe.doc | ROLE | reference_report → MINED | Reference |
| DTE.txt | **GAP** | — | Invoice: date, amount |
| 4001670_portada.doc | SKIP | Cover | — |
| 4001670_generated*.docx (×3) | OUR | — | — |
| file_mapping.json, user_data.json | OUR | — | — |

### FOTOS DE CAMP + PLANOL PUNTS/ (= FOTOGRAFIES equivalent)

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| **PENETROS.jpeg** | **GAP** | — | **CRITICAL: DPSH field sheet as image. N20 values. Only source of DPSH data if PENETROS.pdf is incomplete** |
| **CROQUIS.jpeg** | **GAP** | — | **HIGH: Field croquis with P1, P2, P3 positions on plot** |
| **ampliació habitatge v2.png** | **GAP** | — | **HIGH: Floor plan with dimensions, test point positions** |
| spt alcoletge.png | **GAP** | — | SPT soil sample photo (LOW: informative only) |
| P1 - ALCOLETGE.jpeg | **GAP** | — | photo_test_point |
| P2 - ALCOLETGE.jpeg | **GAP** | — | photo_test_point |
| P3 - ALCOLETGE.jpeg | **GAP** | — | photo_test_point |
| Thumbs.db | SKIP | — | — |

### ANNEXES/ — DPSH.xls (ROLE), COORDENADES.txt (MINED), *.FH11 ×3 (SKIP)

### ACCEPTACIO/ — PRESSUPOST SIGNAT.pdf (MINED), Thumbs.db (SKIP)

### PDF/ — 6 files SKIP (exports). No exceptions: no LAB-SIG, no sondeig_annex for this project.

### validation/ — 3 JSON files (OUR)

---

## 4001671 VILANOVA DE SEGRIA

### Numeric folder: 26.0050/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| DADES PER ANAR A CAMP_v1.xlsx | MINED | FileMiner(Excel) | client, address |
| PLAN_COST_VILANOVA DE SEGRIÀ.xlsx | MINED | FileMiner(Excel) | cost |
| PRESUPUESTO GEOTEC.VILANOVA DE SEGRIA.pdf | MINED | FileMiner(PDF) | architect_company |
| 1.0.pdf | **GAP** | — | Possibly architect plan (name suggests page 1). MUST VIEW |
| PRESSUPOST LLEIDA.msg | **GAP** | — | Budget email (294KB) |
| RE_ PRESSUPOST LLEIDA.msg | **GAP** | — | Reply (256KB) |
| Thumbs.db | SKIP | — | — |

### Root

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| PENETROS.pdf | ROLE | dpsh_field_sheet → VISION | N20 |
| tall.pdf | ROLE | correlation_section | — |
| pl situació.pdf | ROLE | situation_plan | — |
| comanda laboratori_4001671_VILANOVA DE SEGRIÀ.xls | ROLE | lab_order → MINED | Lab data |
| MULTICA_61.pdf | **GAP** | — | Multi-test lab report? MUST VIEW |
| MULTICA_61.xls | **GAP** | — | Multi-test lab data? MUST VIEW |
| DTE.txt | **GAP** | — | Invoice data |
| 4001671_informe.docx | ROLE | reference_report → MINED | Reference |
| 4001671_portada.doc | SKIP | Cover | — |
| file_mapping.json | OUR | — | — |

### ANEXOS/ (Spanish variant)

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| 4001671_DPSH.xls | **GAP** | — | **NOTE: SmartScan found no dpsh_excel role for this project!** N20 data |
| OTROS/F1 SIT.png | **GAP** | — | figure_situation_map |
| OTROS/F2 PUNTS.png | **GAP** | — | figure_test_points |
| OTROS/F4 MGEOL.png | **GAP** | — | figure_geological_map |
| OTROS/M1.png, M2.png, M22.png, M3.png, m4.png | **GAP** | — | figure_geological_map (×5) |
| OTROS/6_mapa Geol_CAT_ - CAST.FH11 | SKIP | Unreadable | — |
| *.FH11 (×3) | SKIP | Unreadable | — |
| OTROS/Thumbs.db | SKIP | — | — |

### FOTOGRAFIES/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| P1.jpeg, P2.jpeg, P3.jpeg | **GAP** | — | photo_test_point |
| SPT 1 P-1.jpeg, SPT A P3.jpeg | **GAP** | — | photo_spt_sample |
| DES DE DARRERA.jpeg | **GAP** | — | photo_site_overview |
| DES DEL CARRER.jpeg | **GAP** | — | photo_site_overview |
| INTERIOR.jpeg | **GAP** | — | photo_site_overview |
| ZONA P3.jpeg | **GAP** | — | photo_test_point |
| WhatsApp Image 2026-02-19 at 10.28.45.jpeg | **GAP** | — | photo (field) |
| Thumbs.db | SKIP | — | — |

### ACEPTACION CASTELLANO/ — PRESUPUESTO SIGNED.pdf (MINED), Thumbs.db (SKIP)

### PDF/ — 6 files SKIP (exports). Note: no LAB-SIG for this project

---

## 4001679 ANCILES

### Numeric folder: 24.0807/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| DADES PER ANAR A CAMP_v1.xlsx | MINED | FileMiner(Excel) | client, address |
| PLAN_COST_V03. ReV_ANCILES.xlsx | MINED | FileMiner(Excel) | cost |
| PRESUPUESTO GEOTEC.ANCILES.pdf | MINED | FileMiner(PDF) | architect_company |
| **A01_TIPOL.pdf** | **GAP** | — | **CRITICAL: Full architect plan — typologies, areas/floor, heights, architect names. NOT assigned role because it's in numeric subfolder** |
| **IV_PLANOS.pdf** | **GAP** | — | **HIGH: Multiple floor plans. MUST VIEW** |
| **SITE_prop A.pdf** | **GAP** | — | **HIGH: Site proposal plan. May have building layout** |
| Presupuesto Parcela Anciles.msg | **GAP** | — | Budget email (5.8MB!) — very likely has PDF attachments |
| RE_ Presupuesto Parcela Anciles.msg | **GAP** | — | Reply (179KB) |
| Re_ PRESUPUESTO GEOTECNICO ANCILES.msg | **GAP** | — | Reply (152KB) |

### Root

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| PENETROS + SONDEIGS.pdf | ROLE | dpsh_field_sheet + sondeig_field_sheet → VISION | N20, soil layers |
| tall.pdf | ROLE | correlation_section | — |
| pl situ.pdf | ROLE | situation_plan | — |
| comanda laboratori_4001679_ANCILES.xls | ROLE | lab_order → MINED | Lab data |
| 4001679_informe_V0.doc | ROLE | reference_report → MINED | Reference |
| Confirmación visita jueves 19 y plano.msg | **GAP** | — | **HIGH: "plano" in name — likely has architect plan attached (375KB)** |
| DTE.txt | **GAP** | — | Invoice data |
| 4001679_portada_V0.doc | SKIP | Cover | — |
| file_mapping.json | OUR | — | — |

### ANEJOS/ (Spanish variant)

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| 4001679_DPSH.xls | ROLE | dpsh_excel | N20 |
| *.FH11 (×4) | SKIP | Unreadable | — |

### FOTOGRAFIES/

| Fitxer | Estat | Component | Dades potencials |
|--------|-------|-----------|------------------|
| P1-P4.jpeg (×4) | **GAP** | — | photo_test_point |
| S1.jpeg, S2.jpeg | **GAP** | — | photo_sondeig_equipment |
| S2_0-3.jpeg | **GAP** | — | photo (sondeig detail) |
| DETALL SPT1 S1.jpeg, DETALL SPT1 S2.jpeg | **GAP** | — | photo_spt_sample |
| EMPL S1.jpeg, EMPL S2.jpeg | **GAP** | — | photo (emplacement) |
| SPT1 S1.jpeg, SPT1 S2.jpeg | **GAP** | — | photo_spt_sample |
| WhatsApp Image *.jpeg (×2) | **GAP** | — | photo (field) |
| Thumbs.db | SKIP | — | — |

### ACCEPTACIO/ — PRESUPUESTO G3.ANCILES.pdf (MINED), Re_ *.msg (GAP: email)

### PDF_V0/ — 8 files SKIP (exports). Exception: sondeos.pdf → ROLE: sondeig_annex

---

## Anàlisi de Gaps per Tipus

### 1. IMATGES (.jpg, .jpeg, .png) — 105 fitxers, 0 processats

| Subtipus | Quantitat | Valor | Acció |
|----------|-----------|-------|-------|
| Field photos (P1, P2, SPT, maquina, vista, WhatsApp...) | ~75 | Report photos (Phase 6) | Classify → report slot |
| Geological maps (M1-M12, F4 MGEOL) | ~20 | Report figures | Classify → figure slot |
| Situation/points maps (F1 SIT, F2 PUNTS) | ~5 | Report figures | Classify → figure slot |
| **Document-images (PENETROS.jpeg, CROQUIS, ampliació)** | **~5** | **CRITICAL: data extraction** | **Classify → VISION extraction** |
| WhatsApp in numeric folders | ~4 | Unknown — must view | Classify → decide |

### 2. EMAILS (.msg) — 20 fitxers, 0 processats

| Subtipus | Quantitat | Valor | Acció |
|----------|-----------|-------|-------|
| Large (>500KB, likely attachments) | ~8 | HIGH: attached PDFs/plans | MsgMiner → extract attachments → re-process |
| Medium (200-500KB) | ~6 | MEDIUM: body text has addresses | MsgMiner → text detectors |
| Small (<200KB) | ~6 | LOW-MEDIUM: replies, short exchanges | MsgMiner → text detectors |

### 3. TXT files — 12 fitxers, ~5 processats

| Fitxer | Projectes | Processat? | Valor |
|--------|-----------|-----------|-------|
| COORDENADES.txt | 5 | YES (FileMiner) | UTM coordinates |
| DTE.txt | 5 | **NO** | Invoice date, amount, due date |
| CONTACTE.txt | 1 (Linyola) | **NO** | Contact name, phone |
| DADES CLIENT.txt | 1 (Bell-Lloc) | YES (FileMiner) | Full client data |

### 4. PDFs in numeric folders — ~15 fitxers, ~7 processats (via FileMiner/Groq)

| Subtipus | Quantitat | Processat? | Valor |
|----------|-----------|-----------|-------|
| PRESSUPOST *.pdf | 7 | YES (auto_extractor) | architect_company |
| Architect plans (A01_TIPOL, IV_PLANOS, SITE_prop, 1.0.pdf, planol-*.pdf) | ~6 | **NO** | **CRITICAL: building data** |
| Cadastral references (4613172*.pdf) | 2 | **NO** | Parcel data |
| Other (25·0616.pdf, 2_02B_DG*.pdf) | ~2 | **NO** | Unknown |

### 5. MULTICA_61 (Vilanova only) — 2 fitxers, 0 processats

Lab multi-test report (PDF + Excel). Likely contains soil analysis results.
