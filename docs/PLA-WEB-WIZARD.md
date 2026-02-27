# G3DT Web Wizard — Implementation Plan

## Context

Eva (G3DT's geotechnical engineer) currently uses a CLI wizard (`automation/wizard.py`) to fill project data, then runs report generation from terminal. The existing `templates/validation/review.html` already provides a browser-based 3-tab validation UI (DPSH, Sondeig, Planol) that Eva knows.

**Goal**: Extend review.html with a 4th "Wizard" tab + add a FastAPI backend, so Eva can do the full flow (validate extractions → fill wizard → generate report) from one browser tab, never touching the terminal.

## Architecture

```
Browser (review.html)
  ├── Tabs 1-3: DPSH/Sondeig/Planol (unchanged, file picker)
  ├── Project selector dropdown (NEW)
  └── Tab 4: Wizard (NEW, API-driven)
        ├── Prefilled form fields with source badges
        ├── Dynamic soil type selectors per level
        ├── Collapsible expert overrides
        ├── "Guardar Dades" + "Generar Informe" buttons
        └── Download link for generated .docx

FastAPI server (NEW: web/server.py, port 8765)
  ├── GET  /api/projects           → list reference-material/ folders
  ├── GET  /api/prefills/{project} → auto_extractor + wizard prefill chain
  ├── GET  /api/user-data/{project}→ read user_data.json
  ├── POST /api/wizard/{project}   → save wizard data to user_data.json
  ├── POST /api/generate/{project} → run ReportGenerator
  ├── GET  /api/report/{project}   → download .docx
  └── Static mount → templates/validation/ (serves review.html)
```

## Files to Create

| File | Lines | Purpose |
|------|-------|---------|
| `pyproject.toml` | ~20 | Dependencies (fastapi, uvicorn) + project metadata |
| `web/__init__.py` | 1 | Package marker |
| `web/server.py` | ~30 | FastAPI app, static mount, main entry point |
| `web/api.py` | ~180 | All API endpoints |
| `web/wizard_service.py` | ~120 | Service layer bridging automation modules to API |

## Files to Modify

| File | Changes |
|------|---------|
| `automation/wizard.py` | Extract `save_wizard_data()` as standalone function (~30 lines). Existing CLI `save()` calls it internally. |
| `templates/validation/review.html` | Add: project selector, wizard tab HTML, ~150 lines CSS, ~300 lines JS |

## Implementation Steps

### Step 1: pyproject.toml
Create project config declaring fastapi + uvicorn as new dependencies, alongside existing deps.

### Step 2: Refactor wizard.py save logic
Extract the merge-and-save logic from `UserDataWizard.save()` into a standalone `save_wizard_data(project_path, wizard_fields, expert_overrides)` function. The CLI `save()` method then delegates to it. No behavior change.

Key reusable constants from wizard.py:
- `WIZARD_FIELDS` (line 38)
- `EXPERT_ICGC_FIELDS`, `EXPERT_GEOMECH_FIELDS`, `EXPERT_SETTLEMENT_FIELDS` (lines 48-50)
- `BUILDING_TYPES` (from `data_schema.py`)

### Step 3: web/ package (server + service + API)

**web/wizard_service.py** — Service functions:
- `list_projects(ref_dir)` → scan reference-material/ for project folders
- `get_prefills(project_path)` → call `auto_extract()` + `UserDataWizard.load_prefills()` (non-interactive)
- `load_user_data(project_path)` → read user_data.json
- `save_wizard(project_path, fields, overrides)` → call extracted `save_wizard_data()`
- `generate_report(project_path)` → call `ReportGenerator.generate()`
- `find_report(project_path)` → locate `*_generated.docx`

**web/api.py** — FastAPI router with endpoints listed above. Each endpoint delegates to wizard_service.

**web/server.py** — FastAPI app:
- Include API router at `/api`
- Mount static files at `/` (serves review.html)
- `main()` runs uvicorn on port 8765

### Step 4: review.html — CSS additions (~150 lines)
- `.project-selector` — dropdown bar at top
- `.wizard-group`, `.wizard-field`, `.wizard-input` — form field styles
- `.source-badge` — colored labels showing prefill source
- `.toggle-switch` — boolean fields
- `.wizard-loading`, `.spinner` — loading state
- `.wizard-actions` — button row

### Step 5: review.html — HTML additions
- Project selector dropdown (above tabs, between header and file controls)
- Wizard tab button in `.tabs` nav
- `#wizard-content` div with 4 form groups:
  1. Dades del Projecte (architect, building type, floors, area, descriptions)
  2. Adjacents (N/S/E/W)
  3. Parametres (anthropized, soil levels, soil types, foundation depth, elevation, basement, walls)
  4. Overrides Experts (collapsible: ICGC unit, geomech params, Es_settlement)
- Action buttons (Guardar + Generar)
- Generation result area with download link

### Step 6: review.html — JavaScript additions (~300 lines)
- `loadProjects()` → populates dropdown on page load
- Project change handler → enables/disables wizard tab
- `loadWizardData()` → parallel fetch of prefills + existing user_data
- `renderWizardForm()` → populates all fields with priority: user_data > prefill > empty
- `renderSoilTypes(n)` → dynamic soil type dropdowns based on num_soil_levels
- `setSourceBadge(field, source)` → colored source indicators
- `collectWizardFields()` / `collectExpertOverrides()` → gather form values
- `saveWizard()` → POST to API
- `generateReport()` → save first, then POST generate, show result + download
- Override `switchTab()` to lazy-load wizard data on first tab switch
- `beforeunload` guard for unsaved changes

### Step 7: End-to-end test
1. `uv sync` to install FastAPI + uvicorn
2. `uv run python -m web.server` (or `uv run uvicorn web.server:app --port 8765`)
3. Open `http://localhost:8765`
4. Select project "4001612 BELL-LLOC"
5. Switch to Wizard tab → verify prefills load with source badges
6. Modify a field → verify "has-value" styling
7. Click "Guardar Dades" → verify user_data.json updated
8. Click "Generar Informe" → verify .docx generated + download works
9. Verify DPSH/Sondeig/Planol tabs still work with file picker

## Key Design Decisions

- **Port 8765**: Matches existing `python3 -m http.server 8765` documented in CLAUDE.md
- **Vanilla JS**: No React/Vue — matches review.html's existing approach
- **Prefill caching**: Cache auto_extract result in memory per project, refresh on explicit request
- **Lazy load**: Wizard data fetched only when tab is first selected
- **Save-before-generate**: Generate button always saves first, avoiding stale data
- **Non-breaking**: Validation tabs work exactly as before (file picker). Wizard tab only appears when project selected.

## Eva's UX

- All text in Catalan
- Source badges on every prefilled field (blue=auto, green=user_data, gray=default)
- Expert overrides hidden by default (collapsible)
- Spinner during prefill loading (~3s) and report generation (~10-15s)
- Unsaved changes warning before navigation
- Download button appears inline after successful generation
