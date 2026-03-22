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

## Pre-requisite: Commit current work

There are uncommitted changes (SmartScan v1, label_map, scripts, new reference projects, tests). Commit those first on `feat/smartscan` before starting.

---

## Phase 1: Complete File Inventory (research, no code)

**Goal**: Know every file across all 7 projects, what it contains, whether we extract from it.

### Step 1.1: Update `docs/smartscan/01-INVENTARI-FITXERS.md`

Add missing entries:
- **Numeric subfolder contents** (`25.0493/`, `26.0049/`, etc.) — DADES PER ANAR A CAMP, PLAN_COST, PRESSUPOST, architect PDFs, WhatsApp images, .msg emails, cadastral PDFs
- **All images** wherever they are (FOTOGRAFIES/, ANNEXES/ALTRES/, FOTOS DE CAMP/, numeric folders)
- **All .msg files**

### Step 1.2: Create file-type decision matrix

For EVERY file type found, document:

| Extension | Can read? | Tool | Currently processed? | Should process? | Reason |
|-----------|-----------|------|---------------------|-----------------|--------|
| `.pdf` | Yes | PyMuPDF + vision | Yes | Yes | Core data |
| `.xls/.xlsx` | Yes | xlrd/openpyxl | Yes | Yes | Core data |
| `.doc/.docx` | Yes | antiword/python-docx | Yes | Yes | Core data |
| `.txt` | Yes | text read | Yes | Yes | Coords, contacts |
| `.jpg/.jpeg` | Yes | Vision (Groq/Claude) | **NO** | **YES** | Field sheets, plans as photos |
| `.png` | Yes | Vision (Groq/Claude) | **NO** | **YES** | Floor plans, geological maps |
| `.msg` | Yes | extract-msg library | **NO** | **YES** | Addresses, contacts, project details |
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
3. **Use Groq Llama 4 Scout** (multimodal, ~$0.11/M tokens) instead of Claude ($3/M) for classification
   - 27x cheaper
   - Already have Groq API integration (`web/vision_groq.py`)
   - Fallback to Claude if Groq unavailable
4. Add image-specific roles to classification prompt: `field_photo`, `field_croquis`, `floor_plan_image`

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

### Step 3.3: New MsgMiner

**New file**: `automation/fileminer/miners/msg_miner.py`

- Uses `extract-msg` to read .msg files
- Extracts: subject, sender, recipients, body text
- Runs existing text detectors on body (phones, emails, NIF, addresses, label-values)
- Source type: `content_email` (priority 43, between groq_llm 42 and content_pdf 45)

### Step 3.4: Register and enable

**Files**:
- `automation/fileminer/miners/__init__.py` — register MsgMiner for `.msg` extension
- `automation/fileminer/__init__.py` — remove `.msg` from `_SKIP_EXTENSIONS`
- `automation/fileminer/label_map.py` — add `"content_email": 43` to SOURCE_PRIORITY

---

## Phase 4: Directory Re-evaluation

### Step 4.1: FOTOGRAFIES — selective, not wholesale skip

**File**: `automation/fileminer/__init__.py`

Option A (simpler): Keep `FOTOGRAFIES` in `_SKIP_DIRS` for FileMiner (text mining photos is useless), but let SmartScan handle classification. Images identified as documents by SmartScan go through vision pipeline, not FileMiner.

Option B (thorough): Remove `FOTOGRAFIES` from `_SKIP_DIRS`, but FileMiner naturally skips image extensions (which it can't text-mine). Only `.txt` or other text files accidentally in FOTOGRAFIES would be mined.

**Recommendation**: Option A. FileMiner can't extract text from images anyway. The key fix is in SmartScan (Phase 2) ensuring document-images in FOTOGRAFIES get classified and routed to vision.

### Step 4.2: PDF/ directories

Keep `PDF` in `_SKIP_DIRS` for FileMiner. These ARE exported copies — mining them would create duplicate signals. SmartScan already correctly handles the exceptions (sondeig_annex, lab_results_pdf live in PDF/ANNEXES/ and are role-assigned).

### Step 4.3: ACCEPTACIO/ — already handled

SmartScan walks ACCEPTACIO/. FileMiner processes files there (it's NOT in `_SKIP_DIRS`). The pressupost_pdf extractor specifically looks there. `DADES CLIENT.txt` is mined by TextMiner. No changes needed.

---

## Phase 5: Provider-Variant Document Layouts

### Step 5.1: Flexible vision prompts

The current planol extraction prompt is tuned for one layout style. Different architects organize plans differently:
- Anciles A01_TIPOL.pdf: typologies table with areas per floor
- Bell-Lloc A.01.pdf: traditional caixetí (title block)
- Linyola: architect plan is a "Punts de Sondeig" PDF (informal)

**Solution**: Vision prompts should be resilient:
- Extract what's available, don't require specific layout
- Return confidence per field (already done)
- Groq LLM extraction as backup for unusual layouts

### Step 5.2: Groq for "difficult" files

Files with < 3 signals after Python mining already go through Groq LLM. This naturally handles provider variants because LLM reads the actual content, not a regex pattern. **No changes needed** — this already works.

---

## Implementation Order

```
1. [PREREQUISITE] Commit current uncommitted work on feat/smartscan
2. [Phase 1] File inventory + extraction map (research doc, no code)
3. [Phase 2.1-2.2] SmartScan Tier 1+2 image support (pure Python, zero cost)
4. [Phase 3] MsgMiner (pure Python, zero cost)
5. [Phase 2.3] SmartScan Tier 3 Groq vision for images (~$0.09 for all test projects)
6. [Phase 2.4] Vision pipeline routing for images
7. [Phase 4] Directory re-evaluation (logic changes)
8. [Phase 5] Provider-variant resilience (prompt tuning)
```

Steps 2-4 can be tested with `pytest` at zero cost.
Steps 5-6 require Groq API (already configured).
Step 7-8 are refinements.

---

## Verification

### Per-phase tests

1. **Image classification**: Run SmartScan on Alcoletge → PENETROS.jpeg gets `dpsh_field_sheet`, CROQUIS.jpeg gets `field_croquis`, P1.jpeg stays `informative`
2. **MsgMiner**: Mine Anciles `Confirmación visita.msg` → extract address/contact signals
3. **End-to-end**: Run `auto_extract()` on Alcoletge → DPSH data extracted from JPEG → wizard pre-fills N20 values

### Regression

- Run full test suite on all 7 projects
- Verify no existing classifications change (except images now classified where they were "unknown")
- Verify signal competition resolves correctly with new email signals

---

## Cost Analysis

| Component | Cost per project | Cost for 7 test projects |
|-----------|-----------------|-------------------------|
| Tier 2 image fingerprint (Pillow) | $0.00 | $0.00 |
| MsgMiner (extract-msg) | $0.00 | $0.00 |
| Tier 3 Groq vision classification | ~$0.01 (2-5 images) | ~$0.09 |
| Vision extraction of classified images | ~$0.05 (Claude, 1-2 images) | ~$0.35 |
| **Total incremental cost** | **~$0.06** | **~$0.44** |

Negligible compared to the data quality improvement.

---

## Critical Files

| File | Change |
|------|--------|
| `automation/smartscan/tier1_filename.py` | Image patterns, selective FOTOGRAFIES handling |
| `automation/smartscan/tier2_fingerprint.py` | `_fingerprint_image()` function |
| `automation/smartscan/tier3_vision.py` | Accept images, Groq vision classification |
| `automation/fileminer/__init__.py` | Remove `.msg` from _SKIP_EXTENSIONS |
| `automation/fileminer/miners/msg_miner.py` | **NEW**: MsgMiner class |
| `automation/fileminer/miners/__init__.py` | Register MsgMiner |
| `automation/fileminer/label_map.py` | Add `content_email` priority |
| `automation/auto_extractor.py` | Route image roles to vision pipeline |
| `pyproject.toml` | Add `extract-msg` dependency |
| `tests/test_smartscan.py` | Ground truth for images, .msg |
| `docs/smartscan/02-MAPA-EXTRACCIO.md` | **NEW**: Per-file extraction map |
