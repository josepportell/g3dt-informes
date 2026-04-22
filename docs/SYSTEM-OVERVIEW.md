# G3DT System Overview

Development reference for the geotechnical report automation pipeline.
Last updated: 2026-04-22.

**Related docs** (where details live that this overview only summarizes):
- `docs/GUIA-DIAGNOSTICS.md` — how to interpret the benchmark + re-sweep procedure.
- `docs/PLA-PROXIMES-ACCIONS-POST-SWEEP-2026-04-22.md` — live action plan: 5 ranked fixes based on the Apr 22 sweep.
- `docs/_FOR-NEW-YOU-*.md` — handoff doc for fresh sessions (load-bearing assumptions, don'ts, opening sequence).
- `docs/ARQUITECTURA-CONCEPT-FORMAT-SCHEMAS.md` — concept/format schema design.

## 1. What G3DT Does

G3DT generates geotechnical reports (.docx) from project files. Eva (geologist at G3 Geotecnia) places field documents (DPSH Excel, borehole PDFs, architect plans) in a project folder, opens a web wizard at localhost:8765, selects the project, and gets a report pre-filled to ~95%. She reviews/adjusts for ~30 seconds, then downloads the final .docx. Claude Code is the production runtime -- it runs on Eva's machine and serves the wizard.

## 2. Pipeline Overview

```
Project folder (PDFs, Excel, .doc, .jpg, .msg)
    │
Phase 0:    SmartScan (Tier 1→2→3) → file_mapping.json (classify ALL files by role)
    │          Tier 1: Filename regex (30+ roles, CA/ES variants)
    │          Tier 2: Content fingerprint (PDF keywords, Excel depth, image EXIF)
    │          Tier 3: Groq Vision classification (Llama 4 Scout, ~$0.003/file)
    │
Phase 0.3:  FileMiner ──────────→ text signals (Python regex from all files, incl .msg)
    │          MsgMiner: extracts email body + saves attachments → re-mines them
    │          First resolve_competition() runs here.
    │
Phase 0.4:  Groq LLM Miner ────→ more text signals (gap-fill for files regex missed)
    │          Second resolve_competition() merges Groq signals with Phase 0.3 pool.
    │
Phase 0.45: ConceptScout ──────→ vision probe + concept_map.json (added 2026-04)
    │          scout_project() builds file→concept map + probes non-text-extractable
    │          files with Groq vision (fallback to Claude). After the probe:
    │          concept_sources_to_signals() converts vision probes into FileMiner
    │          Signals (planol_vision → prio 20, projecte_vision → prio 25). A THIRD
    │          resolve_competition() merges them with the Phase 0.3+0.4 pool so
    │          vision signals compete under schema-defined priorities.
    │          See: automation/concept_scout/__init__.py, _phase045_concept_scout.
    │          Applies these competition filters BEFORE ranking:
    │            - G3 internal address drop (any signal where the value looks like
    │              C/ Vallbona 22, G3's office) — see automation/internal_addresses.py
    │            - Hedged-preview drop ("appears to", "probably", "unclear", etc.)
    │            - Address-concept reliability floor: confidence≥0.9 AND NOT from
    │              handwritten field sheets (applies only to street/site_address)
    │
Phase 1:    auto_extract ──────→ prefills (DPSH Excel, Lab PDF, field dates)
    │          DPSH: file_mapping role → glob fallback → N20, refusal, Es_settlement
    │
Phase 1.5:  Vision (Groq) ─────→ planol/sondeig/dpsh_extracted.json
    │          Determined by file_mapping roles with vision_type.
    │          Supports PDFs AND images (.jpg/.png) natively.
    │          Auto_extractor also exposes _best_vision_address() so geocode
    │          phases can prefer a high-confidence architect-plan address over
    │          a raw prefill (defensive layer from #8).
    │
Phase 2:    HTTP APIs ──────────→ prefills (ICGC geology/elevation, Cadastre, geocode)
    │          geocode_project() is the sole entry point (Callejero fast-path
    │          removed #10). CartoCiudad is primary, ICGC Territorial is the
    │          Catalan fast path, Cadastre WFS-CP is fallback. See §10.
    │
Phase 2.5: Merge + Compute ───→ geomech params (gamma, phi, E, c → Qa, K30, settlement)
    │         _merge_prefills(): auto_extract + vision + user_data
    │         _compute_geotech_prefills(): Terzaghi, Schmertmann, CTE D.27
    │         _fill_missing_adjacents(): geocode from planol address if Phase 2 skipped
    │
Phase 3:   Wizard ─────────────→ user_data.json (Eva reviews, adjusts, confirms)
    │         Live recalculation: changing phi → Qa/K30/settlement update instantly
    │
Phase 4:   ReportGenerator ───→ {expedient}_generated.docx
```

## 3. Data Flow

Miners (Phase 0.3-0.4) produce `Signal` objects with five attributes:

- **label**: canonical variable name (e.g. `promotor`, `street_address`)
- **value**: extracted string
- **source**: origin file + source type
- **confidence**: 0.0-1.0 extraction confidence
- **priority**: integer from source type (lower = more trusted)

`resolve_competition()` picks one winner per label (grouped by `concept_id`):
1. Per-concept priority from `schemas/concepts/report_variables.yaml::source_priority` (lower = better, default 50 if source_type is unknown)
2. On equal priority, highest confidence wins
3. Special case: `report_date` — among same-priority signals, the most recent date wins

Before ranking, the resolver applies **structural filters** (shipped 2026-04):
- **G3 internal address drop** — signals for `{street,site,client}_address` whose value matches `automation/internal_addresses.py::is_g3_internal_address` are removed. Currently matches `C/ Vallbona, 22` (G3's Rubí office). The same filter ALSO runs as a belt-and-suspenders check inside `auto_extractor._phase25_geocode` + `_phase3_cadastre_adjacents` — deliberate double-layer because this class of bug bit us before.
- **Hedged-preview drop** — signals whose preview matches markers like "appears to", "probably", "unclear", "seems to" are dropped (prose, not value).
- **Address reliability floor** — `street_address` / `site_address` signals from vision probes require confidence ≥ 0.9 AND non-handwritten source (`doc_type != field_sheet`). The ConceptSource still appears in `concept_map.json` for audit; only the Signal is suppressed.

Groq miner additionally applies **source-context exclusions** before signals enter competition:
- G3 internal data (NIF, phone, email matching G3's own) is excluded.
- Cost/budget documents (`PLAN_COST`, `PRESSUPOST`, `COMANDA`) are excluded for `province`, `municipality`, and `architect_name` (these refer to G3's office, not the project).

Winners become wizard prefills. Losers become alternatives, shown as "+N" badges in the wizard UI. Eva can click an alternative to swap it in as the active value.

## 4. Source Priority Table

```
Priority | Source Type        | Description
---------|--------------------|-------------------------------------------
10       | user               | Eva's manual edit -- always wins
20       | planol_vision      | Vision-probe on architect plans (architect_plan doc_type)
20       | *_vision           | Vision-extracted JSONs (planol/sondeig/dpsh)
25       | coordenades_txt    | GPS field-measured coordinates
25       | projecte_vision    | Vision-probe on projecte PDFs (projecte doc_type)
30       | pressupost_pdf     | G3's own structured quote
30       | icgc_api           | ICGC geology, elevation, slope
30       | cadastre_api       | Cadastre adjacents, parcel geometry
35       | dades_camp_excel   | Client-provided prep sheet
35       | comanda_lab_excel  | Lab order sheet
40       | geocode_nominatim  | Nominatim-derived address/coords (Step 7 demoted it to tertiary fallback; CartoCiudad is primary inside geocode_project)
42       | groq_llm           | LLM extraction (Groq API)
45       | content_*          | Generic file text extraction (PDF, docx, Excel)
50       | vision_probe_other | Default for vision probe on unrecognized doc types
60       | folder_name        | Last resort: parse folder name
```

Unknown source types default to priority 50. Priority values live in `schemas/concepts/report_variables.yaml` per-concept (not in code), so a concept can override the default chain if it needs to.

## 5. Key Files

| File | Purpose |
|------|---------|
| `automation/auto_extractor.py` | Orchestrates phases 0-2 (SmartScan, FileMiner, Groq, auto_extract, HTTP APIs) |
| `automation/fileminer/__init__.py` | `mine_project()`, `mine_project_groq()`, signal collection |
| `automation/fileminer/competition.py` | `resolve_competition()` -- picks winners from signals (date-aware for report_date) |
| `automation/fileminer/label_map.py` | Label aliases, source priorities |
| `automation/fileminer/miners/groq_miner.py` | Phase 0.4: Groq LLM extraction with source-context exclusions |
| `automation/fileminer/miners/docx_miner.py` | Word extraction (.docx via python-docx, .doc via antiword/libreoffice) |
| `automation/internal_addresses.py` | Shared G3-office-address detector used by both `resolve_competition` and auto_extractor geocode phases (#8, 2026-04-22) |
| `automation/smartscan/` | Phase 0: file classification by role |
| `automation/concept_scout/__init__.py` | Phase 0.45: `scout_project()` + `concept_sources_to_signals()` converter that folds vision probes into the FileMiner Signal pool; applies reliability filters (address floor, hedged-preview drop, handwritten-source drop) |
| `automation/concept_scout/vision_probe.py` | Vision probe (Groq primary, Claude fallback) for non-text-extractable files; outputs ConceptSource entries into concept_map.json |
| `automation/icgc_territorial.py` | Catalan fast-path geocoder (Step 7 #3): single HTTPS call returns 4 GeoJSON layers (cadastre/municipis/sigpac/qualificacions-muc); `extract_refcadp()` cross-verifies vs CartoCiudad's RC |
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
# Required (in .env)
ANTHROPIC_API_KEY=sk-ant-...   # Claude API key (for vision_extractor.py Claude path)
GROQ_API_KEY=gsk_...           # Groq API key (vision + LLM miner)

# Feature toggles (all default to '1' = ON since 2026-03-30)
G3DT_USE_SMARTSCAN=1           # SmartScan vs legacy FileScanner (killswitch: =0)
G3DT_USE_GROQ=1                # Groq LLM miner Phase 0.4 (killswitch: =0)

# Optional
GROQ_MODEL=qwen/qwen3-32b     # Groq text model (default: qwen/qwen3-32b)
G3DT_NO_CACHE=1                # Bypass all caches (Groq, geocode, vision, prefill)
G3DT_PROJECTS_DIR=/path/...    # Project folder (default: reference-material/)
G3DT_CLAUDE_PATH=claude        # Claude CLI binary path
G3DT_VISION_TIMEOUT=600        # Vision timeout in seconds
```

**Important:** The web server does NOT auto-reload. After code changes, kill and restart `python -m web`.

## 7. SmartScan Deep Dive

SmartScan is a **superset of the legacy FileScanner**. It produces the same `FileMapping` → `file_mapping.json` format, so all downstream code (vision_groq, auto_extractor, report_generator) works unchanged.

### What SmartScan adds vs FileScanner

| Capability | FileScanner | SmartScan |
|------------|-------------|-----------|
| Directories scanned | Root + ANNEXES/ + PDF/ANNEXES/ (flat) | **Recursive** (entire project tree) |
| Roles assigned | 15 | **30+** (photos, figures, emails, croquis) |
| Folder name variants | ANNEXES only | **ANNEXES, ANEXOS, ANEJOS** + all CA/ES combos |
| Image classification | Ignored | Tier 1 (filename) + Tier 2 (EXIF, color, size) |
| Email processing | Ignored (.msg in IGNORE_PATTERNS) | **project_email** role, MsgMiner extracts body + attachments |
| Content analysis | No | Tier 2: PDF keywords, Excel depth patterns |
| LLM fallback | No | Tier 3: Groq Vision for unrecognized files |

### How vision_type flows through the pipeline

```
SmartScan assigns role (e.g. dpsh_field_sheet)
    ↓
models.py to_file_mapping() calls get_vision_type("dpsh_field_sheet") → "dpsh"
    ↓
Saves to file_mapping.json: {"dpsh_field_sheet": {"path": "PENETROS.pdf", "vision_type": "dpsh"}}
    ↓
vision_groq.py loads file_mapping.json via FileScanner.load()
    ↓
Creates vision task for each role with vision_type → calls Groq Llama 4 Scout
    ↓
Saves dpsh_extracted.json → consumed by _merge_prefills()
```

**Key insight (discovered 2026-03-30):** SmartScan was fully implemented but never activated because `G3DT_USE_SMARTSCAN` defaulted to empty string. Now defaults to `'1'`.

### Roles with vision_type (trigger vision extraction)

| Role | vision_type | What it extracts |
|------|-------------|-----------------|
| architect_plan | planol | Architect, promotor, dimensions, floors |
| architect_plan_with_points | planol | Same + test point locations |
| situation_plan | planol | Site location |
| field_croquis | planol | Test point positions on plot |
| dpsh_field_sheet | dpsh | N20 values, refusal, water table |
| sondeig_field_sheet | sondeig | Soil layers, SPT, descriptions |
| sondeig_annex | sondeig_annex | Formatted borehole log (vector PDF) |

**Image support:** vision_groq.py `_file_to_images()` handles `.jpg`, `.jpeg`, `.png` directly (no PDF rendering needed). If SmartScan assigns `dpsh_field_sheet` to `PENETROS.jpeg`, vision will extract N20 from it.

### Role conflict resolution

When multiple files match the same role (e.g. `PENETROS.pdf` and `PENETROS.jpeg` both match `dpsh_field_sheet`), `role_map` keeps the one with highest confidence. For Tier 1 exact matches, the one scanned first wins (typically root-level PDF over subfolder image). This is correct: PDFs are higher quality sources than photos of field sheets.

### Directories excluded from scanning

SmartScan's `_enumerate_files()` skips: `validation/`, `.git`, `__pycache__`, `.venv`, `node_modules`. This prevents re-scanning our own outputs (mined_images/, msg_attachments/, *_extracted.json).

## 8. Geomech Computation Chain

When Eva selects a project, the wizard computes geomech parameters automatically:

```
DPSH Excel → avg_n20 (bearing stratum only, see §8.1) → Nb (= N20/0.83)
    ↓
Sondeig description → soil_type (rock/cohesive/granular)
    ↓
CTE D.27: gamma (by soil_type)
Schmertmann / Crespo Tabla 11.2: phi (see §8.2)
CTE D.23: E (from N20, bracket lookup)
Crespo / Hunt: cohesion (by soil_type and N)
    ↓
Terzaghi (1943): qu = c·Nc·sc + γ·Df·Nq·sq + 0.5·γ·B·Nγ·sγ → Qa = qu/3
Terzaghi-Peck: qa_tp = Nb/12 / Fw × Fd (granular only)
Professional cap: 3.0 (soil) or 5.0 (rock, c≥0.5)
    ↓
K30 = E/75 (granular) or E/60 (rock)
Schmertmann settlement: C1 × Qa × Iz_integral / Es
```

**Live recalculation (since 2026-03-30):** The wizard recomputes Qa, K30, settlement in JavaScript on every keystroke. Shape factors match Python (SQUARE: sc=1.3, sq=1.0, sg=0.8). Flash animation highlights changed values.

**Key dependency:** If DPSH Excel extraction fails (`dpsh_data` is None), ALL geomech params stay empty. The `_compute_geotech_prefills()` function returns early at line 318-322.

### 8.1. Bearing-layer selection (G.5-wire, 2026-04-17)

Eva's convention: compute Qa on the **deepest competent layer** (the bearing stratum under the footing). If the top is fill / rebliment / very weak, skip it and use the next competent layer down. This is formalized in `automation/bicapa.py::select_bearing_layer` and wired into the pipeline via `automation/report_data.py::_select_bearing_layer_idx`. `_bearing_stratum_n20` then averages DPSH readings inside the chosen layer's depth range (with the `depth_to_m` cap gated off when bearing == deepest so the bearing zone below isn't truncated).

Reference: Rodríguez Ortiz §6.1 ("Curso aplicado de cimentaciones", book archived at `docs/research/books/`). Alcoletge is the calibration case: rebliment top (skipped) + lutites bottom (bearing). Bell-Lloc, Castellar, Rubí, Linyola all have "deepest == competent".

### 8.2. Friction angle φ helpers — Eva's authoritative tables

| Helper | Source | When used |
|--------|--------|-----------|
| `nspt_to_phi(Nb, soil_type)` | CTE Table 4.1 + Schmertmann n-factor | Default path for sands/gravels |
| `crespo_phi_cohesive(N)` | Crespo Villalaz §9.1 | Clays (arcilles); midpoint of consistency band |
| `crespo_phi_granular(N, fine_fraction)` | **Crespo Tabla 11.2 (p.175)** | Sands, with `"transitional"` clamp at 28° for llim argilós / sorres argiloses (Finding #10 anchor) |
| `hunt_cohesion_from_nspt(N)` | Hunt's consistency table | Cohesion midpoint by N |
| Meyerhof / Schmertmann qc chain | Schmertmann (1975) p.175 | qc = n·N → φ via Meyerhof curves; E = 2.5·qc (isolated) or 3.5·qc (strip) for Schmertmann settlement |

All tables tested with anchor-point fixtures against Eva's informes (Alcoletge, Bell-Lloc, Linyola, Rubí). Books archived at `docs/research/books/`: Rodríguez Ortiz, Crespo Villalaz, Schmertmann (1975), Hoek & Bray summary.

## 9. Wizard Tabs

| Tab | Purpose |
|-----|---------|
| **SmartScan** | File classification review -- shows detected roles per file |
| **Wizard** | Main form: all prefills, vision results, generate button |
| **Explicacio** | (Disabled) Future: explanation of extraction logic |
| **Dev** | Extraction analysis per subsystem -- debugging view |

## 10. Geocoding

**Single entry point:** `automation/geocode_coordinates.py::geocode_project`. The Callejero fast-path that used to live in `auto_extractor` was removed (#10, 2026-04-22) — it silently picked wrong parcels on noisy addresses.

### Resolution chain (current, post-Step 7 + #8-#12)

```
project address + municipality (from planol vision @ conf≥0.9, preferred over any text signal)
    │
    ▼
CartoCiudad (IGN) candidates endpoint  [Step 7 #1+#2+#11]
    ├─ no municipio_filter (accent-strict bug server-side; client-side filter handles muni)
    ├─ no_process=toponimo,municipio,comunidad autonoma,poblacion
    ├─ limit=5
    ├─ strips "Urb. …" / "Edifici …" / "Bloc …" trailing suffixes before query
    │
    ├─ portal match → authoritative refCatastral returned inline (skip RCCOOR)
    │     │
    │     ├─ Catalan project?  → ICGC API Territorial /elements/cadastre,municipis,sigpac,qualificacions-muc/{lng},{lat}  [Step 7 #3]
    │     │     └─ returns parcel polygon + refcadp (byte-identical to CartoCiudad RC — free cross-verification)
    │     │
    │     └─ non-Catalan → Cadastre WFS-CP GetFeature by RC → parcel polygon
    │
    └─ miss? → Cadastre progressive lookup (ConsultaMunicipio → ConsultaVia → Consulta_DNPLOC → Consulta_CPMRC)
          ├─ On Consulta_RCCOOR err-code 16 ("PARA ESAS COORDENADAS NO HAY REFERENCIA")  [Step 7 #5]
          │    → fall back to Consulta_RCCOOR_Distancia (nearest parcel within 50m)
          └─ On complete miss → Nominatim (tertiary safety net; weak for Catalan small towns)

UTM conversion: auto-detect zone 30 (lon < 0) vs zone 31 (lon >= 0)
ICGC elevation: Catalunya only; gracefully skipped elsewhere.
```

### Key flags and gotchas

- **`automation/icgc_territorial.py`** takes coordinates as `(lat, lng)` caller-friendly order and internally builds the URL with `{lng},{lat}` — wrong order silently returns 0 features.
- **CartoCiudad `municipio_filter` is deliberately NOT sent.** Server-side is accent-strict: `Vilanova+de+Segria` (no accent) returns 0 candidates, `Vilanova+de+Segrià` returns 4. G3DT derives muni names from folder names which typically lose diacritics. `_cartociudad_muni_matches` handles muni filtering client-side (accent- and case-insensitive).
- **Step 7 #4 (Catastro REST/JSON migration) is server-blocked** — their `COVCCoordenadas.svc/json` endpoint returns `cod=76 "LA COORDENADA X OBLIGATORIA"` regardless of param casing. Code scaffolded for drop-in flip (`_CADASTRE_REST_URL_BROKEN_SERVER_SIDE` constant with `TODO(step7-4)` pointer). Kept ASMX XML as the transport.
- **Step 7 #6 (INSPIRE WFS-CP for adjacents)** — optional, deferred. The ASMX adjacents probing still works.
- **Cache locations:** `~/.g3dt/cache/cartociudad/`, `~/.g3dt/cache/geocode/`, `~/.g3dt/cache/cadastre_adjacents/`, `~/.g3dt/cache/icgc_territorial/`. All bypassed with `G3DT_NO_CACHE=1`.

### Matching features (unchanged)

- Accent-insensitive comparison (Rubí = RUBI, Segrià = SEGRIA)
- Abbreviation expansion (Sta. → Santa, Gral. → General, Mn. → Mossen)
- Progressive hint shortening ("Clot de la Llacuna" → "Clot de la" → "Clot")
- Nearest-number recovery (if number 20 doesn't exist, picks nearest available)

### Coverage (live-verified 2026-04-22)

- CartoCiudad portal match: 5/7 reference projects (Bell-Lloc coverage gap is a known CartoCiudad data hole, not a bug — falls through to Cadastre).
- ICGC Territorial: Catalunya 6/7; Anciles (Aragón) correctly skipped.
- Cross-verification (CartoCiudad RC == ICGC refcadp): byte-identical for Vilanova; no false-positive disagreements recorded.

## 11. File Exclusions

FileMiner skips these files/directories:
- **Dirs**: `FOTOGRAFIES`, `PDF`, `PDF-V0`, `PDF_V0`, `validation`, `.git`, etc.
- **Extensions**: images (`.png`, `.jpg`...), design (`.fh11`, `.psd`), temp (`.db`, `.tmp`, `.msg`)
- **Patterns**: `{expedient}_informe*.doc(x)`, `{expedient}_portada*.doc(x)` — Eva's reference reports
- **Generated**: `file_mapping.json`, `user_data.json`

## 12. Groq Model Selection

The Groq text miner model is selectable at runtime:
- **ENV var**: `GROQ_MODEL=qwen/qwen3-32b` (default)
- **Wizard UI**: dropdown next to project selector, calls `POST /api/groq-model`
- **Available**: Llama 3.1 8B (fast), Qwen3 32B (default), Llama 3.3 70B (best), Llama 4 Scout 17Bx16E (MoE)
- Vision model (Llama 4 Scout) is separate and fixed — requires vision capability

## 13. Caching

Four cache layers, all bypassed with `G3DT_NO_CACHE=1`:
- **Groq text miner**: `~/.g3dt/cache/groq/` (SHA256 of file+model, 90-day TTL)
- **Geocode**: `~/.g3dt/cache/geocode/` (SHA256 of address+municipality, 90-day TTL)
- **Vision JSON**: `{project}/validation/*_extracted.json` (file-based, no TTL)
- **In-memory prefills**: process lifetime (cleared on project change or server restart)

## 14. Running

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

# Run benchmark comparison (all 7 projects)
.venv/bin/python scripts/compare_benchmarks.py
```

## 15. Correctness (as of 2026-04-22)

The canonical benchmark is `scripts/diagnostic_trace.py` (full-pipeline diagnostic with LLM judge). See `docs/GUIA-DIAGNOSTICS.md` for how to run, interpret, and compare sweeps.

### Variable Tiers (unchanged since 2026-03-30)

- **Tier A (auto-extractable):** Values the pipeline SHOULD get right automatically (client, address, N20, phi, E, Qa, dates, surfaces).
- **Tier B (manual/on-site):** Values requiring human observation or external sources (adjacents descriptions, site condition, access description).
- **Tier C (professional judgment):** Values Eva adjusts based on experience (E override, Qa cap override, Es settlement).

### Global Metrics (sweep 2026-04-22, CROSS_351d13.json)

| Metric | Value | Note |
|--------|-------|------|
| Match+Close | **64.1%** (139/217 compared) | Apr 19 judge-noise band: 62.4%-65.2% across three identical re-runs |
| MATCH | 105/217 | |
| CLOSE | 34/217 | |
| MISMATCH | 78/217 | Cluster into 4 structural modes + schema gaps — see Pla d'accions doc |
| NOT_EXTRACTED | 40/217 | Was 47 pre-#8; -7 var-comparisons extraction-frontier gain |
| PASS (not benchmarked for this project) | 24 | |

### Per-project

| Project | Rate | Δ vs Apr 21 |
|---|---:|---:|
| Bell-Lloc | 72.1% | flat |
| Castellar del Vallès | 77.4% | flat |
| Rubí | 63.9% | -3.7pp (precision cost of wider net, not quality regression) |
| Linyola | 73.7% | flat |
| Alcoletge | 47.8% | +2.3pp |
| **Vilanova de Segria** | **56.0%** | **+8.0pp** (Step 7 + #8-#12 chain end-to-end) |
| Anciles | 38.1% | DNS-contaminated this run (13 network errors) |

### Top failure modes (see `docs/PLA-PROXIMES-ACCIONS-POST-SWEEP-2026-04-22.md`)

| # | Mode | Vars | Est. recovery | Effort |
|---|---|---:|---:|---|
| A | Schema gaps (NOT_EXTRACTED) — 9 concepts missing from YAML | ~20 | +3-5pp | S |
| B | CTE classification threshold — single wrong-answer pattern across `cte_sol`/`cte_edificacio`/`qa_value` | 12 | +4pp | S |
| C | Settlement format — values correct, Eva's narrative wrapper missing | 6 | +6pp | S |
| D | Identity disambiguation — vendor-not-buyer, co-author-not-lead | 8 | +2-4pp | M |
| E | Adjacent/location narrative — Eva voice vs cadastre taxonomy | 12+ | +2-5pp | L |

Projected ceiling after A+B+C: ~77-80%.

### How to re-sweep (quick reference)

```bash
# Clear caches (prevents stale concept_map.json from masking changes)
for p in "4001612 BELL-LLOC" "3001621 CASTELLAR DEL VALLES" "3001631 RUBI" \
         "4001607 LINYOLA" "4001670 ALCOLETGE" "4001671 VILANOVA DE SEGRIA" \
         "4001679 ANCILES"; do
  rm -f "reference-material/$p/validation/concept_map.json"
done
rm -f ~/.g3dt/cache/cartociudad/*.json ~/.g3dt/cache/geocode/*.json

# Full sweep (~15 min wall-clock)
.venv/bin/python scripts/diagnostic_trace.py --save --components --ne-trace

# Grep the log for DNS failures BEFORE trusting per-project numbers
grep -c "name resolution\|Connection error" /tmp/claude-*/tasks/*.output

# Saved to docs/diagnostics/YYYY-MM-DD_CROSS_<runid>.json + per-project snapshots
```

**Don't over-interpret single-sweep deltas under 2.8pp** — that's the judge-noise band. For real signal, compare per-variable MISMATCH→MATCH flips across re-runs, not headline rates. Full interpretive rules in `docs/GUIA-DIAGNOSTICS.md` → "Com interpretar els resultats".

### Legacy benchmark scripts (still usable, lower fidelity)

```bash
# Tier-aware benchmark compare (LLM-as-judge for Tier B, deterministic for A/C)
.venv/bin/python scripts/compare_benchmarks.py

# Simple Eva vs pipeline dump (no signal trace)
.venv/bin/python scripts/compare_eva_vs_pipeline.py

# Extract reference values from Eva's signed .docx reports (run once, cached)
.venv/bin/python scripts/extract_benchmark_values.py
```

`diagnostic_trace.py` is the canonical modern entry point; the legacy scripts are useful for narrow investigations.
