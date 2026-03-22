# G3DT System Overview

Development reference for the geotechnical report automation pipeline.

## 1. What G3DT Does

G3DT generates geotechnical reports (.docx) from project files. Eva (geologist at G3 Geotecnia) places field documents (DPSH Excel, borehole PDFs, architect plans) in a project folder, opens a web wizard at localhost:8765, selects the project, and gets a report pre-filled to ~95%. She reviews/adjusts for ~30 seconds, then downloads the final .docx. Claude Code is the production runtime -- it runs on Eva's machine and serves the wizard.

## 2. Pipeline Overview

```
Project folder (PDFs, Excel, .doc)
    |
Phase 0:   SmartScan -----------> file_mapping.json (classify files by role)
    |
Phase 0.3: FileMiner -----------> signals (Python regex extraction from all files)
    |
Phase 0.4: Groq LLM Miner -----> signals (LLM extraction from underperforming files)
    |
Phase 0.5: auto_extract --------> prefills (DPSH Excel, Lab PDF, field dates)
    |
Phase 1:   Vision ---------------> planol/sondeig/dpsh_extracted.json
    |          Options: Claude CLI | Claude Fast | Groq Vision (Llama 4 Scout)
    |
Phase 2:   HTTP APIs ------------> prefills (ICGC geology/elevation, Cadastre, geocode)
    |
Phase 3:   Wizard ---------------> user_data.json (Eva reviews, adjusts, confirms)
    |
Phase 4:   ReportGenerator ------> {expedient}_generated.docx
```

## 3. Data Flow

Miners (Phase 0.3-0.4) produce `Signal` objects with five attributes:

- **label**: canonical variable name (e.g. `promotor`, `street_address`)
- **value**: extracted string
- **source**: origin file + source type
- **confidence**: 0.0-1.0 extraction confidence
- **priority**: integer from source type (lower = more trusted)

`resolve_competition()` picks one winner per label:
1. Lowest priority number wins (user > vision > geocode > content)
2. On equal priority, highest confidence wins
3. Special case: `report_date` — among same-priority signals, the most recent date wins

Winners become wizard prefills. Losers become alternatives, shown as "+N" badges in the wizard UI. Eva can click an alternative to swap it in as the active value.

Groq miner applies source-context exclusions before signals enter competition:
- G3 internal data (NIF, phone, email matching G3's own) is excluded
- Cost/budget documents (`PLAN_COST`, `PRESSUPOST`, `COMANDA`) are excluded for `province`, `municipality`, and `architect_name` (these refer to G3's office, not the project)

## 4. Source Priority Table

```
Priority | Source Type       | Description
---------|-------------------|-------------------------------------------
10       | user              | Eva's manual edit -- always wins
20       | *_vision          | Claude/Groq reads PDFs (planol, sondeig, dpsh)
25       | coordenades_txt   | GPS field-measured coordinates
30       | pressupost_pdf    | G3's own structured quote
30       | icgc_api          | ICGC geology, elevation, slope
30       | cadastre_api      | Cadastre adjacents, parcel geometry
35       | dades_camp_excel  | Client-provided prep sheet
35       | comanda_lab_excel | Lab order sheet
40       | geocode_nominatim | Nominatim-derived address/coords
42       | groq_llm          | LLM extraction (Groq API)
45       | content_*         | Generic file text extraction (PDF, docx, Excel)
60       | folder_name       | Last resort: parse folder name
```

Unknown source types default to priority 50.

## 5. Key Files

| File | Purpose |
|------|---------|
| `automation/auto_extractor.py` | Orchestrates phases 0-2 (SmartScan, FileMiner, Groq, auto_extract, HTTP APIs) |
| `automation/fileminer/__init__.py` | `mine_project()`, `mine_project_groq()`, signal collection |
| `automation/fileminer/competition.py` | `resolve_competition()` -- picks winners from signals (date-aware for report_date) |
| `automation/fileminer/label_map.py` | Label aliases, source priorities |
| `automation/fileminer/miners/groq_miner.py` | Phase 0.4: Groq LLM extraction with source-context exclusions |
| `automation/fileminer/miners/docx_miner.py` | Word extraction (.docx via python-docx, .doc via antiword/libreoffice) |
| `automation/smartscan/` | Phase 0: file classification by role |
| `automation/validation/prompts.py` | Vision extraction prompts (planol, sondeig, DPSH) |
| `automation/report_generator.py` | Phase 4: builds .docx from Jinja template |
| `automation/terzaghi_calculator.py` | Bearing capacity, settlement, K30 calculations |
| `automation/vision_normalizer.py` | Normalizes non-deterministic vision JSON to canonical schema |
| `web/api.py` | FastAPI endpoints (projects, prefills, generate, geocode) |
| `web/wizard_service.py` | Business logic: prefill merging, vision orchestration, caching |
| `web/vision_fast.py` | Claude CLI vision (calls claude binary) |
| `automation/geocode_coordinates.py` | Geocoding: Cadastre + Nominatim, UTM zone 30/31 auto-detect, multi-province |
| `web/vision_groq.py` | Groq vision (Llama 4 Scout for PDF reading) |
| `templates/validation/review.html` | Wizard UI: tabs, forms, signal badges |
| `templates/g3dt-jinja-template.docx` | Word template with Jinja2 placeholders |

## 6. Environment Variables

```bash
G3DT_USE_SMARTSCAN=1           # Enable SmartScan (vs legacy FileScanner)
G3DT_USE_GROQ=1                # Enable Groq LLM miner (Phase 0.4)
GROQ_API_KEY=gsk_...           # Groq API key (required if G3DT_USE_GROQ=1)
GROQ_MODEL=qwen/qwen3-32b     # Groq text model (default: qwen/qwen3-32b)
G3DT_NO_CACHE=1                # Bypass all caches (Groq, geocode, vision, prefill) — for testing
G3DT_PROJECTS_DIR=/path/to/projects  # Project folder (default: reference-material/)
G3DT_CLAUDE_PATH=claude        # Claude CLI binary path
G3DT_VISION_TIMEOUT=600        # Vision timeout in seconds
```

## 7. Wizard Tabs

| Tab | Purpose |
|-----|---------|
| **SmartScan** | File classification review -- shows detected roles per file |
| **Wizard** | Main form: all prefills, vision results, generate button |
| **Explicacio** | (Disabled) Future: explanation of extraction logic |
| **Dev** | Extraction analysis per subsystem -- debugging view |

## 8. Geocoding

Geocoding supports all Spanish provinces (not just Catalunya). The pipeline uses a **progressive resolution chain**:

1. **ConsultaMunicipio** — fuzzy-match municipality from hint (e.g., "Bell-Lloc" → "BELL-LLOC D'URGELL")
2. **ConsultaVia** — fuzzy-match street from hint (e.g., "Ferraz" → "GRAL. FERRAZ AG ANCILES")
3. **Consulta_DNPLOC** — lookup with resolved names → cadastral reference (RC)
4. **Consulta_CPMRC** — RC → UTM coordinates
5. **Nominatim** fallback — if progressive chain fails, geocodes via OpenStreetMap
6. **UTM conversion** — auto-detects zone 30 (lon < 0) vs zone 31 (lon >= 0)
7. **ICGC elevation** — Catalunya only; gracefully skipped for other provinces

Matching features:
- Accent-insensitive comparison (Rubí = RUBI, Segrià = SEGRIA)
- Abbreviation expansion (Sta. → Santa, Gral. → General, Mn. → Mossen)
- Progressive hint shortening ("Clot de la Llacuna" → "Clot de la" → "Clot")
- Nearest-number recovery (if number 20 doesn't exist, picks nearest available)

Tested: 7/7 projects resolve to valid cadastral references via progressive lookup.

## 9. File Exclusions

FileMiner skips these files/directories:
- **Dirs**: `FOTOGRAFIES`, `PDF`, `PDF-V0`, `PDF_V0`, `validation`, `.git`, etc.
- **Extensions**: images (`.png`, `.jpg`...), design (`.fh11`, `.psd`), temp (`.db`, `.tmp`, `.msg`)
- **Patterns**: `{expedient}_informe*.doc(x)`, `{expedient}_portada*.doc(x)` — Eva's reference reports
- **Generated**: `file_mapping.json`, `user_data.json`

## 10. Groq Model Selection

The Groq text miner model is selectable at runtime:
- **ENV var**: `GROQ_MODEL=qwen/qwen3-32b` (default)
- **Wizard UI**: dropdown next to project selector, calls `POST /api/groq-model`
- **Available**: Llama 3.1 8B (fast), Qwen3 32B (default), Llama 3.3 70B (best), Llama 4 Scout 17Bx16E (MoE)
- Vision model (Llama 4 Scout) is separate and fixed — requires vision capability

## 11. Caching

Four cache layers, all bypassed with `G3DT_NO_CACHE=1`:
- **Groq text miner**: `~/.g3dt/cache/groq/` (SHA256 of file+model, 90-day TTL)
- **Geocode**: `~/.g3dt/cache/geocode/` (SHA256 of address+municipality, 90-day TTL)
- **Vision JSON**: `{project}/validation/*_extracted.json` (file-based, no TTL)
- **In-memory prefills**: process lifetime (cleared on project change or server restart)

## 12. Running

```bash
# Start wizard server
.venv/bin/python -m web
# Open http://localhost:8765/review.html

# Start with all caches bypassed (for testing)
G3DT_NO_CACHE=1 G3DT_USE_GROQ=1 .venv/bin/python -m web

# Run extraction without wizard
.venv/bin/python -m automation.auto_extractor "reference-material/PROJECT_NAME"

# Run tests
.venv/bin/python -m pytest tests/ -v
```
