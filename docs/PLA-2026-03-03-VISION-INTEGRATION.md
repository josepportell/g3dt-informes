# Pla de Treball — 2026-03-03
# Integrar Claude Vision al Pipeline Automàtic (Path A: Anthropic API)

## Context Ràpid (per arrencar sense memòria prèvia)

### On som
- **Branca:** `feat/historia-geologica`
- **Últim commit:** `520d52e` (merge fix/report-quality-audit)
- **Canvis NO commitejats** (6 fitxers core + 4 generated docs):
  - `automation/sections/section3_geologia.py` — Geologia dinàmica (for-loop, sense límit 6 slots)
  - `automation/report_generator.py` — Filtre sondeig fix, material short, Nb range, auto-fill
  - `automation/report_data.py` — Deepest layer description, merged level early return
  - `automation/intelligent_audit.py` — For-loop alignment pre-pass
  - `templates/g3dt-jinja-template.docx` — For-loop Jinja al lloc de 6 slots fixos
  - `CLAUDE.md`, `STATUS.md` — Documentació actualitzada (model d'operació)
- **Web server:** `.venv/bin/python -m web` (localhost:8765)
- **Audit Bell-Lloc:** 97.1% auto-resolved

### Què falta
1. **Commit + merge** dels canvis d'ahir
2. **Integrar Claude vision (Fase 1) al pipeline automàtic del wizard** ← PRINCIPAL
3. Items menors (Category C vocabulary, Eva questions, multi-level test)

### Arquitectura decidida
**Path A: Anthropic API des de Python.** El backend FastAPI crida l'API de Claude directament per llegir PDFs amb visió. No depèn de que Claude Code estigui corrent per la visió.

---

## Pas 1: Commit + Merge (15 min)

### 1.1 Commit canvis pendents
```bash
cd /home/josep/projects/claudecode-job/clients/g3dt
git add automation/sections/section3_geologia.py \
      automation/report_generator.py \
      automation/report_data.py \
      automation/intelligent_audit.py \
      templates/g3dt-jinja-template.docx \
      CLAUDE.md STATUS.md
git commit -m "fix(g3dt): audit critical bugs — dynamic geology, sondeig filter, material desc

- Bug 1: Replace 6 fixed geology_para slots with Jinja for-loop (73% of templates were truncated)
- Bug 2: Guard sondeig layer filter with num_user_levels == len(sondeig_layers)
- Bug 3: Use deepest layer (bearing stratum) description for merged single-level projects
- Fix A: Audit alignment pre-pass for for-loop generated paragraphs
- Fix B: Short material descriptions for table cells
- Fix D: Nb range excludes shallow layer readings for merged levels
- Fix: Empty sondeig_layers [] no longer blocks auto-fill
- Update CLAUDE.md and STATUS.md with production operation model

Bell-Lloc audit: 97.1% auto-resolved (was ~84%)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

### 1.2 Merge fix/report-quality-audit → main (si no s'ha fet)
```bash
git checkout main
git merge fix/report-quality-audit
git checkout feat/historia-geologica
git merge main  # Rebase si cal
```

**Nota:** Revisar si `fix/report-quality-audit` ja està mergejat (commit `520d52e` diu "merge: integrate fix/report-quality-audit into feat/historia-geologica").

---

## Pas 2: Implementar Vision Extractor (Path A) — PRINCIPAL (~2-3h)

### 2.1 Instal·lar dependències
```bash
cd /home/josep/projects/claudecode-job/clients/g3dt
uv pip install anthropic
```

La clau API va a variable d'entorn `ANTHROPIC_API_KEY` o a un fitxer `.env`.

### 2.2 Crear `automation/vision_extractor.py`

**Responsabilitat:** Llegir PDFs amb l'API de Claude i extreure dades estructurades.

**Funcions principals:**
```python
async def extract_from_planol(pdf_path: Path) -> dict:
    """Llegeix A.01.pdf → architect_data JSON"""

async def extract_from_penetros(pdf_path: Path) -> dict:
    """Llegeix PENETROS.pdf → dpsh_extracted JSON"""

async def extract_from_sondeig(pdf_path: Path) -> dict:
    """Llegeix SONDEIG.pdf → sondeig_extracted JSON"""

async def run_vision_extraction(project_path: Path) -> dict:
    """Executa totes les extraccions disponibles per un projecte.
    Usa file_scanner per trobar els PDFs correctes.
    Retorna dict amb resultats + guarda JSONs a validation/"""
```

**Detalls tècnics:**
- Convertir PDF → imatges amb **PyMuPDF** (`fitz`): ja al projecte per lab extraction
- Enviar imatges com a base64 a l'API de Claude (model: `claude-sonnet-4-6` per cost/qualitat)
- Prompts: reutilitzar `automation/validation/prompts.py` (DPSH, SONDEIG ja existeixen)
- **Crear prompt per PLÀNOL** — no existeix a prompts.py, però sí al skill `.claude/commands/g3dt-extreure-planol.md` (copiar format JSON de allà)
- Output: guardar JSONs a `{project_path}/validation/`
- Cost estimat: ~$0.03-0.10 per projecte (3-5 pàgines de PDF)

**Mapeig de camps extrets → prefills wizard:**

| Font vision | Camp wizard | Ja prefillat per auto_extract? |
|-------------|-------------|-------------------------------|
| Plànol → project_name | `project_description` | No |
| Plànol → location | `street_address` | No |
| Plànol → promotor | `promoter_name` | No |
| Plànol → architect | `architect_name` | No |
| Plànol → architect company | `architect_company` | No |
| Plànol → parcel_area | `superficie_parcela_m2` | No |
| Plànol → footprint | `superficie_construida_m2` | No |
| Plànol → num_floors | `num_floors_str` | No |
| Plànol → max_height | `building_height_m` | No |
| Penetros → N20 validation | `dpsh_extracted.json` | Parcialment (Excel sí, PDF no) |
| Sondeig → soil layers | `sondeig_extracted.json` | No |

### 2.3 Integrar a `web/wizard_service.py`

Modificar `get_prefills()` per executar la visió després d'`auto_extract`:

```python
def get_prefills(project_name: str, *, force_refresh: bool = False) -> dict:
    # ... existing auto_extract ...

    # Phase 1: Claude vision (if not cached)
    vision_cache = project_path / 'validation' / 'planol_extracted.json'
    if not vision_cache.exists() or force_refresh:
        try:
            vision_results = run_vision_extraction(project_path)
            # Merge vision prefills with auto_extract prefills
            merge_vision_prefills(prefills, vision_results)
        except Exception as e:
            logger.warning(f"Vision extraction failed: {e}")
            # Non-fatal: wizard works without vision, just fewer prefills

    return prefills
```

**Important:** La visió ha de ser **no-bloquejant per l'UX**. Opcions:
- **Opció A (simple):** Sincrona, ~30s d'espera. Mostrar "loading..." al wizard.
- **Opció B (millor UX):** Retornar prefills bàsics immediatament, llançar visió en background, frontend fa polling fins que arriba.

Recomanació: **Opció A per ara** (simple), iterar a Opció B si Eva ho demana.

### 2.4 Afegir prompt de plànol a `prompts.py`

Basat en el skill `/g3dt-extreure-planol` (`.claude/commands/g3dt-extreure-planol.md`), crear:

```python
PLANOL_EXTRACTION_PROMPT = """Analyze this architectural plan (plànol)...
[Caixetí: nom projecte, ubicació, promotor, arquitecte]
[Dimensions: parcel·la, ocupació, plantes, alçada]
OUTPUT FORMAT (JSON): { ... }
"""
```

El format JSON ja està definit al skill: `planol_extracted.json` amb `architect_data.dimensions.*`.

### 2.5 Cache i re-execució

- Guardar resultats vision a `{project_path}/validation/{type}_extracted.json`
- Si el JSON ja existeix i `force_refresh=False`, no re-executar (cache)
- Botó "Actualitzar prefills" al wizard → `force_refresh=True` → re-executa tot incloent visió
- Funcions de la visió no necessiten saber res del wizard, es testen de forma independent

---

## Pas 3: Test End-to-End (~1h)

### 3.1 Test unitari vision_extractor
```bash
# Test amb Bell-Lloc (projecte referència amb tots els PDFs)
.venv/bin/python -c "
from automation.vision_extractor import run_vision_extraction
from pathlib import Path
result = run_vision_extraction(Path('reference-material/4001612 BELL-LLOC'))
print(result)
"
```

Verificar:
- [ ] Plànol: architect_name, promoter_name, dimensions extretes
- [ ] Penetros: N20 values extretes i comparades amb Excel
- [ ] Sondeig: soil layers extretes

### 3.2 Test wizard integration
```bash
.venv/bin/python -m web
# Obre localhost:8765
# Selecciona Bell-Lloc
# Verificar que wizard mostra camps plànol pre-omplerts
# Comparar amb user_data.json actual (que vam omplir manualment)
```

### 3.3 Test projecte "buit" (Linyola)
- Linyola té user_data.json mínim (4 camps)
- Executar wizard → visió hauria d'omplir architect, dimensions, etc.
- Verificar que els prefills nous són correctes

---

## Pas 4: Commit Final (~15 min)

```bash
git add automation/vision_extractor.py \
      automation/validation/prompts.py \
      web/wizard_service.py
git commit -m "feat(g3dt): integrate Claude vision into wizard pipeline (Anthropic API)

- New vision_extractor.py: reads PDFs via Claude API for plànol, penetros, sondeig
- Add PLANOL_EXTRACTION_PROMPT to prompts.py
- wizard_service.py runs vision after auto_extract
- Cache: results saved to validation/*.json, skip if cached
- Cost: ~$0.05/project (3-5 PDF pages via claude-sonnet-4-6)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Fitxers a Crear/Modificar

| Fitxer | Acció | Descripció |
|--------|-------|------------|
| `automation/vision_extractor.py` | **NOU** | Core vision extraction via Anthropic API |
| `automation/validation/prompts.py` | Modificar | Afegir PLANOL_EXTRACTION_PROMPT |
| `web/wizard_service.py` | Modificar | Integrar vision a get_prefills() |
| `pyproject.toml` o reqs | Modificar | Afegir `anthropic` com a dependència |

---

## Dependències Existents Aprofitables

| Mòdul | Què aporta | Ja existeix? |
|-------|-----------|-------------|
| `automation/validation/prompts.py` | Prompts DPSH + SONDEIG | ✅ Sí |
| `automation/validation/schemas.py` | Models Pydantic per output | ✅ Sí |
| `automation/file_scanner.py` | Classifica PDFs per tipus | ✅ Sí |
| `automation/auto_extractor.py` | Pipeline d'extracció Python | ✅ Sí |
| PyMuPDF (`fitz`) | PDF → imatges | ✅ Ja usat per lab extraction |
| `.claude/commands/g3dt-extreure-planol.md` | Format JSON plànol | ✅ Referència |

---

## Riscos i Mitigacions

| Risc | Mitigació |
|------|-----------|
| API key no disponible a l'ordinador d'Eva | `.env` file o variable d'entorn. Documentar setup. |
| PDFs molt grans (plànols CAD) | Limitar resolució d'imatge (150 DPI suficient per text) |
| Vision falla (PDF corrupte, format estrany) | try/except, wizard funciona sense vision (menys prefills) |
| Cost API acumulat | claude-sonnet-4-6 és econòmic (~$0.03-0.10/projecte), monitoritzar |
| Latència 30s per visió | Loading indicator al wizard, cache per no repetir |

---

## Estat de les Branques (referència)

```
main
  └── fix/report-quality-audit (pendent merge a main? revisar commit 520d52e)
  └── feat/historia-geologica (branca activa, tots els canvis aquí)
        └── HEAD: 520d52e + canvis uncommitted
```

Els canvis uncommitted inclouen:
- 6 bugs fixats (geologia, sondeig, material, audit, template)
- CLAUDE.md i STATUS.md actualitzats
- Bell-Lloc audit: 97.1%

---

## Appendix A: Path B — Claude Code com a Orquestrador (referència futura)

### Concepte
En lloc de cridar l'Anthropic API des de Python, Claude Code (que ja corre a l'ordinador d'Eva) fa la visió directament. Eva interactua amb Claude Code, que orquestra tot.

### Com funcionaria

**Opció B1: Eva usa el terminal de Claude Code**
```
Eva: /g3dt-generar-informe reference-material/NOU-PROJECTE
Claude Code:
  1. Executa auto_extract (Python) → prefills bàsics
  2. Llegeix PDFs directament (visió) → prefills complerts
  3. Obre/refresca wizard amb tot pre-omplert
  4. Eva revisa al navegador, ajusta, genera
```
- Pro: Sense cost API addicional (usa Pro subscription)
- Con: Eva ha d'usar el terminal, no és 100% self-service

**Opció B2: Wizard amb webhook a Claude Code**
```
1. Eva selecciona projecte al wizard
2. Wizard crida endpoint /api/prefills/{p} → auto_extract (ràpid)
3. Wizard mostra prefills parcials + botó "Enriquir amb visió"
4. Eva prem botó → backend escriu fitxer .vision_request
5. Claude Code (monitoritzant) detecta el fitxer → executa visió
6. Claude Code escriu JSONs a validation/
7. Frontend polling detecta nous JSONs → actualitza wizard
```
- Pro: Wizard-first UX, sense cost API
- Con: Complex, polling, depèn de que Claude Code monitoritzi

**Opció B3: MCP Server bridge**
```
1. Crear un MCP server que exposa la funció vision_extract
2. El wizard crida un endpoint que invoca l'MCP tool
3. Claude Code (que té l'MCP server registrat) processa la petició
```
- Pro: Elegant, usa infraestructura existent
- Con: MCP no està dissenyat per ser cridat des de Python cap a Claude Code

### Per què vam triar Path A
1. **Simplicitat:** Un sol mòdul Python, testable independentment
2. **Fiabilitat:** No depèn de l'estat de Claude Code
3. **UX:** Wizard 100% self-service (Eva no toca terminal)
4. **Cost acceptable:** ~$0.05/projecte, són informes de pagament
5. **Path B queda obert:** Si el cost acumulat és problema, es pot migrar

### Migració A→B
Si en el futur volem Path B, el refactor és mínim:
- `vision_extractor.py` canvia de cridar Anthropic API a escriure fitxers de petició
- Es crea un watcher a Claude Code que processa les peticions
- Les interfícies (entrada PDF, sortida JSON) són idèntiques

---

## Appendix B: Camps wizard i fonts de dades (referència completa)

### Camps que s'ompliran automàticament amb visió (nous)

| Camp wizard | Font | Fase |
|------------|------|------|
| `project_description` | Plànol caixetí | 1 (vision) |
| `street_address` | Plànol caixetí | 1 (vision) |
| `promoter_name` | Plànol caixetí | 1 (vision) |
| `architect_name` | Plànol caixetí | 1 (vision) |
| `architect_company` | Plànol caixetí | 1 (vision) |
| `superficie_parcela_m2` | Plànol cotes | 1 (vision) |
| `superficie_construida_m2` | Plànol cotes | 1 (vision) |
| `num_floors_str` | Plànol secció | 1 (vision) |
| `building_height_m` | Plànol secció | 1 (vision) |
| `sondeig_layers` | Sondeig PDF | 1 (vision) |

### Camps que ja s'ompleixen automàticament (existents)

| Camp wizard | Font | Fase |
|------------|------|------|
| `dpsh_readings` | DPSH.xls | 0.5 (auto_extract) |
| `field_dates` | DPSH.xls | 0.5 (auto_extract) |
| `lab_sulfates` | Lab PDF | 0.5 (auto_extract) |
| `utm_coordinates` | Nominatim + Cadastre | 0.5 (geocode) |
| `icgc_geology` | ICGC API | 0.5 (HTTP) |
| `icgc_elevation` | ICGC MDT | 0.5 (HTTP) |
| `icgc_slope` | ICGC API | 0.5 (HTTP) |
| `adjacent_*` | Cadastre API | 0.5 (HTTP) |
| `marc_geologic` | Eva templates | 0.5 (auto_extract) |

### Camps que Eva sempre haurà d'omplir/confirmar

| Camp | Per què |
|------|---------|
| `num_soil_levels` | Decisió professional |
| `foundation_type` | Decisió professional |
| `foundation_depth_m` | Decisió professional |
| `geomech_overrides` | Ajustos d'Eva (E, phi, c) |
| `Es_settlement` | Criteri professional |
| `project_type` | Pot diferir del plànol |

---

*Pla creat: 2026-03-02*
*Per al dia: 2026-03-03*
*Branca: feat/historia-geologica*
*Objectiu: Wizard self-service amb ~95% camps pre-omplerts automàticament*
