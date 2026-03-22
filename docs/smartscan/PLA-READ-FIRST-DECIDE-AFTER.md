# Plan: "Read First, Decide After" — Universal File Processing for G3DT

## Context

G3DT's pipeline pre-filters files by extension and directory, **missing critical data**:
- **PENETROS.jpeg** (Alcoletge): DPSH field data exists ONLY as JPEG — system skips it entirely
- **ampliació habitatge v2.png** (Alcoletge): Floor plan with dimensions — skipped
- **CROQUIS.jpeg** (Alcoletge): Test point locations sketch — skipped
- **A01_TIPOL.pdf** (Anciles `24.0807/`): Full architect plan in numeric subfolder — not assigned a role
- **.msg emails** (~20 across projects): Project addresses, contacts, architect info — skipped
- **DADES CLIENT.txt** (ACCEPTACIO/): Client NIF, address, phone — partially reached

These are just the cases we KNOW about. With hundreds of future projects from different providers, surprises are guaranteed. The system must be **resilient to the unexpected**.

**New philosophy**: Only skip files that are technically unreadable or obviously system artifacts. Everything else gets read, classified, and explicitly accepted or dismissed with a reason.

## Pre-requisite: Commit current work — DONE (a8253ff)

---

## Phase 1: Complete File Inventory (research, no code)

**Goal**: Know every file across all 7 projects, what it contains, whether we extract from it.

### Step 1.1: Update `docs/smartscan/01-INVENTARI-FITXERS.md`

Add missing entries:
- **Numeric subfolder contents** (`25.0493/`, `26.0049/`, etc.) — DADES PER ANAR A CAMP, PLAN_COST, PRESSUPOST, architect PDFs, WhatsApp images, .msg emails, cadastral PDFs
- **All images** wherever they are (FOTOGRAFIES/, ANNEXES/ALTRES/, FOTOS DE CAMP/, numeric folders)
- **All .msg files**

### Step 1.2: Create file-type decision matrix

| Extension | Can read? | Tool | Currently processed? | Should process? | Reason |
|-----------|-----------|------|---------------------|-----------------|--------|
| `.pdf` | Yes | PyMuPDF + vision | Yes | Yes | Core data |
| `.xls/.xlsx` | Yes | xlrd/openpyxl | Yes | Yes | Core data |
| `.doc/.docx` | Yes | antiword/python-docx | Yes | Yes | Core data |
| `.txt` | Yes | text read | Yes | Yes | Coords, contacts |
| `.jpg/.jpeg` | Yes | Vision (Groq/Claude) | **NO** | **YES** | Field sheets, plans as photos |
| `.png` | Yes | Vision (Groq/Claude) | **NO** | **YES** | Floor plans, geological maps |
| `.msg` | Yes | extract-msg library | **NO** | **YES** | Addresses, contacts, project details, **attachments** |
| `.FH11` | No | No reader exists | No | No | PDF exports exist in PDF/ folder |
| `.psd/.ai` | No | No reader exists | No | No | Not found in projects anyway |
| `Thumbs.db` | Technically | - | No | No | Windows cache, zero project info |
| `.tmp` | No useful data | - | No | No | Temp files |
| `~$*` | No useful data | - | No | No | Word lock files |
| `.json` | Yes | json | Ours only | Skip ours | Our outputs (file_mapping, user_data) |

### Step 1.3: Create per-file extraction map

For each file across all 7 projects, document:
- Which pipeline component processes it (SmartScan role? FileMiner? Groq? Vision? None?)
- What signals it produces
- What signals it COULD produce but doesn't

This becomes `docs/smartscan/02-MAPA-EXTRACCIO.md`.

---

## Phase 2: Image Processing (highest impact)

### Step 2.1: SmartScan Tier 1 — Image-aware filename patterns

**File**: `automation/smartscan/tier1_filename.py`

**Changes**:
1. Extend role patterns to accept image extensions:
   - `dpsh_field_sheet`: add `.(jpg|jpeg|png)` alongside `.pdf`
   - `architect_plan`: add image extensions
   - New role `field_croquis`: `CROQUIS.(jpg|jpeg|png|pdf)`
2. Change FOTOGRAFIES/FOTOS handling from "blanket dismiss" to "selective classify":
   - Define `_PHOTO_NAME_PATTERNS` for obvious field photos (P1, P2, S1, SPT1, WhatsApp Image, IMG-*, Imagen de WhatsApp, DETALL, EMPL, ZONA, INTERIOR, DES DE/DEL, vista_general, maquina_*)
   - Files in content dirs matching photo patterns → `informative` (as today)
   - Files in content dirs NOT matching photo patterns → fall through to Tier 2/3 (new behavior)

### Step 2.2: SmartScan Tier 2 — Image pre-filter (cheap, no API)

**File**: `automation/smartscan/tier2_fingerprint.py`

**New function**: `_fingerprint_image(rel_path, abs_path)`

Uses Pillow (already available) for structural analysis:
- **Resolution**: < 500x500 → informative (thumbnail/icon)
- **Aspect ratio**: A4-like (1:1.41) or tall portrait → possible document
- **EXIF**: WhatsApp/phone camera metadata → likely field photo
- **Filename heuristics**: Already handled by Tier 1, this is the fallback

Cost: **Zero** (pure Python, no API calls).

### Step 2.3: SmartScan Tier 3 — Extend vision to images

**File**: `automation/smartscan/tier3_vision.py`

**Changes**:
1. Accept `.jpg`, `.jpeg`, `.png` alongside `.pdf`
2. For images: skip PDF-to-PNG rendering, send image directly
3. **Use Groq Llama 4 Scout** (multimodal, ~$0.11/M tokens) for classification
   - 27x cheaper than Claude ($3/M)
   - Already integrated: `web/vision_groq.py` has `_call_groq_vision()` function
   - Fallback to Claude if Groq unavailable
4. Add image-specific roles to classification prompt: `field_photo`, `field_croquis`, `floor_plan_image`
5. **Add `unclassified_readable`** role for files that pass all 3 tiers without a role but ARE readable (not system artifacts). These get flagged for human review in the wizard UI ("SmartScan found N unclassified files — review?"). This catches the future surprises we can't predict today.

**Groq Llama 4 Scout validation**: Must test before relying on it for classification. Create a small test set: 5 images (2 field photos, 1 floor plan, 1 field sheet, 1 croquis) → send to Groq → verify classification matches expectations. We already have `web/vision_groq.py` with `_call_groq_vision()` working for PDF extraction, but image classification is a different prompt that needs validation.

Cost per image: ~$0.003 (Groq) vs ~$0.08 (Claude). For ~30 images across 7 projects = ~$0.09 total.

### Step 2.4: Vision pipeline — Route classified images

**File**: `automation/auto_extractor.py` (or wherever vision_type mapping lives)

Ensure image-based role assignments carry `vision_type`:
- Image classified as `dpsh_field_sheet` → `vision_type: "dpsh"` (same as PDF)
- Image classified as `architect_plan` / `floor_plan_image` → `vision_type: "planol"`
- Image classified as `field_croquis` → `vision_type: "croquis"` (new, extracts point locations)

The vision extractor already handles images (Claude reads images natively). The only change is ensuring the routing works for non-PDF files.

---

## Phase 3: Email (.msg) Processing

### Step 3.1: Add dependency

**File**: `pyproject.toml`

Add `extract-msg` (Python library for Outlook .msg files).

### Step 3.2: SmartScan — Classify .msg files

**File**: `automation/smartscan/tier1_filename.py`

1. Remove `r'.*\.msg$'` from `IGNORE_PATTERNS`
2. Add role patterns for .msg:
   - `project_email` role for emails matching: pressupost, confirm, geotècnic, RE_, RV_
   - Non-matching .msg → leave for Tier 2 (text fingerprint on email subject/body)

### Step 3.3: New MsgMiner (with attachment processing)

**New file**: `automation/fileminer/miners/msg_miner.py`

- Uses `extract-msg` to read .msg files
- Extracts: subject, sender, recipients, body text
- Runs existing text detectors on body (phones, emails, NIF, addresses, label-values)
- **Attachment extraction**: `.msg` files up to 7.2MB — many contain attached PDFs, images, Excel.
  Evidence: `Presupuesto Parcela Anciles.msg` (5.8MB), `pressupost geotècnic.msg` (7.2MB), `Confirmación visita jueves 19 y plano.msg` (name literally says "plano")
  - Save attachments to `validation/msg_attachments/{msg_stem}/`
  - Each saved attachment re-enters the pipeline:
    - PDFs → SmartScan classification → FileMiner → possibly vision
    - Images → SmartScan classification → possibly vision
    - Excel/Word → FileMiner mining
  - Source type for attachment-derived signals: `content_email_attachment` (priority 44)
- Source type for body-derived signals: `content_email` (priority 43)

### Step 3.4: Register and enable

**Files**:
- `automation/fileminer/miners/__init__.py` — register MsgMiner for `.msg` extension
- `automation/fileminer/__init__.py` — remove `.msg` from `_SKIP_EXTENSIONS`
- `automation/fileminer/label_map.py` — add `"content_email": 43`, `"content_email_attachment": 44`

---

## Phase 4: Directory Re-evaluation

### Step 4.1: FOTOGRAFIES — Option B: remove from _SKIP_DIRS

**File**: `automation/fileminer/__init__.py`

Remove `FOTOGRAFIES` from `_SKIP_DIRS`. FileMiner naturally skips image extensions (which it can't text-mine via regex). Any `.txt` or other text files accidentally placed in FOTOGRAFIES would now be mined — this is correct behavior per "read first, decide after."

SmartScan handles image classification (Phase 2). Document-images in FOTOGRAFIES get classified and routed to vision. Field photos stay informative.

### Step 4.2: PDF/ directories — keep skipped

Keep `PDF` in `_SKIP_DIRS` for FileMiner. These ARE exported copies. SmartScan handles exceptions (sondeig_annex, lab_results_pdf).

### Step 4.3: ACCEPTACIO/ — already handled, no changes needed

---

## Phase 5: Provider-Variant Document Layouts

### Step 5.1: Flexible vision prompts

The current planol extraction prompt is tuned for one layout style. Different architects organize plans differently:
- Anciles A01_TIPOL.pdf: typologies table with areas per floor
- Bell-Lloc A.01.pdf: traditional caixetí (title block)
- Linyola: architect plan is a "Punts de Sondeig" PDF (informal)

**Current state**: Vision prompts already include geotechnical context ("You are classifying a document from a geotechnical engineering project" in Tier 3, "You are a geotechnical data extraction specialist" in extraction prompts). This helps, but prompts should also be resilient to layout variation:
- Extract what's available, don't require specific layout positions
- Return confidence per field (already done)
- Accept partial results — a plan with only dimensions but no architect name is still valuable

**Clarification on "Groq LLM extraction as backup"**:
- **Vision extraction** (Phase 1) uses either Claude CLI or Groq Llama 4 Scout to READ the document (convert PDF pages to images, send to multimodal LLM, get structured JSON). This is the primary extraction path.
- **Groq text miner** (Phase 0.4) is different: it sends TEXT content (not images) to Groq's text-only LLM (Qwen3 32B by default) for files where regex mining found < 3 signals. This fills gaps for unusual document structures.
- For this plan, image classification in SmartScan Tier 3 uses Groq Vision (Llama 4 Scout, multimodal). Data extraction from classified images uses the existing vision pipeline (Claude CLI or Groq Vision, Eva's choice via wizard button).

### Step 5.2: Groq text miner threshold

The current threshold "< 3 mapped signals" triggers Groq LLM mining. This may not be adequate 100% of times:
- A file with 3 low-confidence signals (0.3) shouldn't be considered "done"
- A file with 2 high-confidence signals from a reliable source might be "done"

**Improved heuristic**: Instead of raw signal count, use a weighted score:
- `coverage_score = sum(signal.confidence * priority_weight for signal in signals)`
- Groq triggers when `coverage_score < threshold` (calibrate on test data)
- OR: Groq triggers when any **target variable** for that file's source_type has zero signals (ensures no gaps in high-priority variables)

For now, keep "< 3 signals" but log cases where Groq finds new data from files with 3+ existing signals. This data will inform threshold tuning later.

---

## Phase 6: Report Figures & Photographs (NEW)

**Context**: The report contains images in two categories:
- **Figures** (Figures 1-N): situation map, geological map, test point plan, correlation section
- **Photographs** (Fotos 1-N): field photos of equipment, test points, site overview

Currently, the system picks images by position in a folder or by filename convention ("first image in FOTOGRAFIES/"). This is fragile — wrong image in wrong slot.

### Step 6.1: Image role taxonomy for report placement

Since SmartScan now classifies every image (Phase 2), extend the role vocabulary with report-placement roles:

**Figure roles** (go into specific figure slots in the report):
- `figure_situation_map` — F1 SIT.png, pl situació, situation plan
- `figure_geological_map` — M1.png through M12.png, mapa geol, MGEOL
- `figure_test_points` — F2 PUNTS.png, plànol punts, croquis with P1/P2/P3
- `figure_correlation` — F5 TALL.png, tall de correlació

**Photograph roles** (go into "Fotografies" section):
- `photo_dpsh_equipment` — maquina_dpsh, shows DPSH rig
- `photo_sondeig_equipment` — maquina_sondeig, shows borehole rig
- `photo_test_point` — P1.jpg, P2.jpg, shows individual test point
- `photo_spt_sample` — SPT1.jpg, DETALL SPT, soil sample
- `photo_site_overview` — vista_general, ZONA, site panorama

### Step 6.2: SmartScan patterns for report images

**File**: `automation/smartscan/tier1_filename.py`

Add filename patterns that map directly to report slots:
- `F\d+\s*(SIT|UBI)` → `figure_situation_map`
- `(M\d+|mapa.*geol|MGEOL)` → `figure_geological_map`
- `F\d+\s*(PUNTS|PUNT)` → `figure_test_points`
- `F\d+\s*TALL` → `figure_correlation`
- `(maquina|màquina).*dpsh` → `photo_dpsh_equipment`
- `(maquina|màquina).*sond` → `photo_sondeig_equipment`
- `^P\d+\.(jpg|jpeg)$` → `photo_test_point`
- `^SPT\d+` → `photo_spt_sample`
- `^(vista_general|ZONA|INTERIOR|DES DE|DES DEL|DARRER)` → `photo_site_overview`

For ambiguous images (WhatsApp photos, unnamed), Tier 3 vision classification determines the role.

### Step 6.3: Report generator integration

**File**: `automation/report_generator.py`

Instead of "pick first image from FOTOGRAFIES/", query `file_mapping.roles` for the specific figure/photo role needed at each report slot. Fallback to current behavior if no role match found.

This step depends on understanding the current figure placement logic (how `report_generator.py` currently selects images). Defer detailed implementation until Phase 2 image classification is working.

---

## Implementation Order (updated)

```
1. [PREREQUISITE] Commit current work — DONE (a8253ff)
2. [Phase 1] File inventory + extraction map (research doc, no code)
3. [Phase 2.1-2.2] SmartScan Tier 1+2 image support (pure Python, zero cost)
4. [Phase 3] MsgMiner + attachment extraction (pure Python, zero cost)
5. [Phase 2.3] SmartScan Tier 3 Groq vision for images (test Llama 4 Scout first)
6. [Phase 2.4] Vision pipeline routing for images
7. [Phase 4] Directory re-evaluation (logic changes)
8. [Phase 5] Provider-variant resilience (prompt tuning, threshold analysis)
9. [Phase 6] Report figures & photographs (image→report slot mapping)
```

Steps 2-4 can be tested with `pytest` at zero cost.
Step 5 requires Groq API validation test first.
Steps 6-8 are integration refinements.
Step 9 builds on all previous phases.

---

## Verification

### Per-phase tests

1. **Image classification**: Run SmartScan on Alcoletge → PENETROS.jpeg gets `dpsh_field_sheet`, CROQUIS.jpeg gets `field_croquis`, P1.jpeg stays `informative`
2. **MsgMiner**: Mine Anciles `Confirmación visita.msg` → extract address/contact signals + list attachments
3. **Groq Scout validation**: 5-image test set → verify classification accuracy before relying on it
4. **Unclassified readable**: Verify files that pass all tiers without a role get flagged (not silently dropped)
5. **End-to-end**: Run `auto_extract()` on Alcoletge → DPSH data extracted from JPEG → wizard pre-fills N20 values
6. **Report figures**: Correct image placed in correct report slot (Phase 6)

### Regression

- Run full test suite on all 7 projects
- Verify no existing classifications change (except images now classified where they were "unknown")
- Verify signal competition resolves correctly with new email/attachment signals

---

## Cost Analysis

| Component | Cost per project | Cost for 7 test projects |
|-----------|-----------------|-------------------------|
| Tier 2 image fingerprint (Pillow) | $0.00 | $0.00 |
| MsgMiner + attachments (extract-msg) | $0.00 | $0.00 |
| Tier 3 Groq vision classification | ~$0.01 (2-5 images) | ~$0.09 |
| Vision extraction of classified images | ~$0.05 (Claude, 1-2 images) | ~$0.35 |
| **Total incremental cost** | **~$0.06** | **~$0.44** |

Negligible compared to the data quality improvement.

---

## Critical Files

| File | Change |
|------|--------|
| `automation/smartscan/tier1_filename.py` | Image patterns, selective FOTOGRAFIES, report figure/photo roles |
| `automation/smartscan/tier2_fingerprint.py` | `_fingerprint_image()` function |
| `automation/smartscan/tier3_vision.py` | Accept images, Groq vision, `unclassified_readable` fallback |
| `automation/fileminer/__init__.py` | Remove `.msg` from _SKIP_EXTENSIONS, remove FOTOGRAFIES from _SKIP_DIRS |
| `automation/fileminer/miners/msg_miner.py` | **NEW**: MsgMiner class with attachment extraction |
| `automation/fileminer/miners/__init__.py` | Register MsgMiner |
| `automation/fileminer/label_map.py` | Add `content_email`, `content_email_attachment` priorities |
| `automation/auto_extractor.py` | Route image roles to vision pipeline |
| `automation/report_generator.py` | Use role-based image selection for figures/photos (Phase 6) |
| `pyproject.toml` | Add `extract-msg` dependency |
| `tests/test_smartscan.py` | Ground truth for images, .msg, report roles |
| `docs/smartscan/02-MAPA-EXTRACCIO.md` | **NEW**: Per-file extraction map |
