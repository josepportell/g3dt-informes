# G3DT - Automatització d'Informes Geotècnics

Client: G3 Geotècnia i Geologia SL
Projecte: Automatització de la generació d'informes geotècnics

## Resum

G3DT genera informes geotècnics per a projectes de construcció. Cada informe inclou:
- Dades de camp (DPSH, sondeigs)
- Anàlisi de sòls
- Càlculs de capacitat portant
- Recomanacions de fonamentació

## Model d'Operació

**Claude Code és el runtime de producció**, no una eina de desenvolupament. S'instal·la a l'ordinador d'Eva i s'executa en segon pla. Eva interactua amb el sistema a través del wizard web (localhost).

```
Eva obre localhost:8765 al navegador
         ↓
Wizard mostra dropdown amb projectes (escaneja reference-material/)
         ↓
Eva selecciona el projecte que vol generar
         ↓
Fases 0 + 0.5 + 1 s'executen automàticament:
  - Python: FileScanner, DPSH Excel, Lab, ICGC, Cadastre
  - Claude vision: plànol, sondeig PDF, penetros PDF
         ↓
Wizard es pobla amb tots els prefills (~95% camps omplerts)
         ↓
Eva revisa i ajusta els camps que cregui convenient (~30s)
         ↓
Eva prem "Generar Informe" → .docx descarregable
```

**Clau:** La visió de Claude (lectura de PDFs de camp i plànols) s'integra directament al pipeline perquè Claude Code és present al runtime. No cal invocar skills manualment — tot és automàtic quan Eva selecciona un projecte.

## Skills Disponibles

Skills per a desenvolupament, testing i invocació manual. En producció, la majoria s'integren automàticament al pipeline via el wizard.

### Pipeline (integrats al wizard)
- `/g3dt-validar-penetros` — Extreu/valida N20 de PENETROS.pdf vs Excel (Claude vision)
- `/g3dt-validar-sondeig` — Extreu capes de sòl de SONDEIG.pdf (Claude vision)
- `/g3dt-extreure-planol` — Extreu dades del plànol A.01.pdf (Claude vision)
- `/g3dt-geocodificar` — Adreça → UTM via Nominatim + Cadastre + WFS INSPIRE
- `/g3dt-adjacents-visor` — Identifica adjacents via visor cartogràfic Cadastre (Playwright)
- `/g3dt-generar-informe` — Genera informe .docx complet

### Utilitats
- `/g3dt-audit-informe` — Audit intel·ligent: compara generat vs referència, genera visual .docx
- `/g3dt-editar-informe` — Edita un informe generat existent

### Desenvolupament
- `/g3dt-dev-eva-vs-pipeline` — Compara valors d'Eva vs pipeline (per refinar extraccions)
- `/g3dt-dev-benchmark-compare` — Benchmark tiered (auto/manual/judici)

## Pipeline de Generació d'Informes

Activat quan Eva selecciona un projecte al wizard web. Tot és automàtic.

```
Fase 0:   FileScanner         → file_mapping.json (classificació fitxers)
Fase 0.5: auto_extract()      → prefills automàtics (DPSH, Lab, ICGC, Cadastre, geocode)
Fase 1:   Claude vision       → planol/sondeig/dpsh_extracted.json (lectura PDFs)
Fase 2:   Wizard (web)        → Eva revisa prefills, ajusta camps → user_data.json
Fase 3:   ReportGenerator     → {expedient}_generated.docx
```

**Fase 0.5** (`automation/auto_extractor.py`) — Python, ~3-5s:
- FileScanner: classifica fitxers del projecte
- DPSH Excel: N20, refús, dates de camp
- Lab PDF: sulfats mg/kg via PyMuPDF
- Geocode: Nominatim + Cadastre → UTM (si no hi ha COORDENADES.txt)
- HTTP: ICGC geologia/elevació/pendent + Cadastre adjacents

**Fase 1** — Claude vision (integrada al pipeline):
- Plànol (A.01.pdf): arquitecte, promotor, dimensions, plantes, alçada
- Sondeig (SONDEIG.pdf): capes de sòl, descripcions, SPT
- Penetros (PENETROS.pdf): validació N20 vs Excel, discrepàncies
- S'executa automàticament perquè Claude Code és el runtime de producció

## Estructura de Carpetes

```
clients/g3dt/
├── .claude/
│   └── commands/             # Skills específics G3DT
│       ├── g3dt-validar-penetros.md
│       ├── g3dt-validar-sondeig.md
│       ├── g3dt-extreure-planol.md
│       ├── g3dt-adjacents-visor.md
│       └── g3dt-geocodificar.md
├── schemas/                  # Schemas YAML (conceptes + formats)
│   ├── concepts/
│   │   └── report_variables.yaml  # 53 conceptes, prioritats per font
│   └── formats/
│       ├── *.yaml            # 8 formats del sistema
│       └── learned/          # Formats apresos per Eva (auto-generats)
├── automation/               # Mòduls d'extracció i càlcul
│   ├── auto_extractor.py     # Fase 0.5: pre-omple camps automàticament
│   ├── dpsh_extractor.py     # Extracció de dades DPSH d'Excel
│   ├── format_learner.py     # Detecció + aprenentatge de formats nous
│   ├── geocode_coordinates.py # Geocodificació adreça → UTM (Nominatim+Cadastre)
│   ├── project_extractor.py  # Extracció de tot el projecte
│   ├── report_data.py        # Model de dades unificat
│   ├── schemas/              # Carregadors Python per schemas YAML
│   │   ├── models.py         # ConceptDefinition, FormatSchema, LabelMapping
│   │   └── loader.py         # ConceptRegistry + FormatRegistry (singletons)
│   ├── terzaghi_calculator.py # Càlcul de capacitat portant
│   └── validation/           # Capa de validació de dades de camp
│       ├── schemas.py        # Models Pydantic
│       ├── prompts.py        # Prompts d'extracció
│       └── extractor.py      # Lògica de comparació
├── web/                      # Servidor web wizard
│   ├── __init__.py           # App FastAPI + static files
│   ├── api.py                # Endpoints REST (7 rutes)
│   └── wizard_service.py     # Capa de servei (prefills, save, geocode)
├── templates/
│   ├── g3dt-jinja-template.docx  # Plantilla Word principal
│   └── validation/
│       └── review.html       # UI web: 4 pestanyes (DPSH, Sondeig, Plànol, Wizard)
├── docs/                     # Documentació tècnica
│   ├── ARQUITECTURA-CONCEPT-FORMAT-SCHEMAS.md  # Disseny concepte/format
│   └── REFERENCE-EXTRACTOR.md                  # Enginyeria inversa informes Eva
├── reference-material/       # Projectes de mostra (7 projectes)
│   └── {project}/validation/eva_reference_values.json  # Valors extrets d'Eva
└── tests/                    # Tests (197 tests)
```

## Flux de Treball d'Eva (producció)

```
┌─────────────────────────────────────────────────────────────┐
│ PREPARACIÓ (Eva, al camp/oficina):                          │
│ 1. Eva fa treball de camp → PDFs (PENETROS, SONDEIG)        │
│ 2. Eva transcriu DPSH → Excel (.xls)                        │
│ 3. Arquitecte envia plànol → A.01.pdf                       │
│ 4. Eva deixa tot a la carpeta del projecte (com sempre)     │
├─────────────────────────────────────────────────────────────┤
│ GENERACIÓ (Eva, al wizard):                                 │
│ 1. Eva obre localhost:8765 al navegador                     │
│ 2. Selecciona projecte del dropdown                         │
│ 3. Sistema executa automàticament:                          │
│    - Python: Excel, Lab, ICGC, Cadastre, geocode (~5s)      │
│    - Claude vision: plànol, sondeig, penetros (~30s)         │
│ 4. Wizard mostra camps pre-omplerts (~95%)                  │
│ 5. Eva revisa, ajusta el que cal (~30s)                     │
│ 6. Eva prem "Generar Informe" → descarrega .docx            │
└─────────────────────────────────────────────────────────────┘
```

## Arquitectura Concepte-Format

El sistema separa **conceptes** (què significa cada dada) de **formats** (on la trobem al document):

- **Schema de Conceptes** (`schemas/concepts/report_variables.yaml`): 53 variables de l'informe amb tipus, grup, i prioritats de font per concepte
- **Schemas de Format** (`schemas/formats/*.yaml`): 8 formats del sistema que mapegen etiquetes → concept_ids
- **Format Learning**: quan un document té un format desconegut (<60% camps extrets), el wizard mostra un banner ambar. Eva omple els camps que falten, desa, i el sistema genera un format schema YAML a `schemas/formats/learned/` per a futures extraccions automàtiques

**Doc complet:** `docs/ARQUITECTURA-CONCEPT-FORMAT-SCHEMAS.md`

## Reference Extractor (Enginyeria Inversa)

Extreu ~30-37 variables amb posició exacta dels informes reals d'Eva (`.doc`/`.docx`) via alineació amb la plantilla Jinja. Resultats a `validation/eva_reference_values.json` per projecte. Permet comparar el pipeline amb els valors reals d'Eva.

```bash
.venv/bin/python -m automation.reference_extractor                    # tots 7 projectes
.venv/bin/python -m automation.reference_extractor "reference-material/4001612 BELL-LLOC"  # un sol
```

**Doc complet:** `docs/REFERENCE-EXTRACTOR.md`

## Documents de Camp

### PENETROS.pdf (DPSH)
Full de camp amb valors N20 escrits a mà. Claude pot llegir-lo visualment:
- Profunditats cada 20cm
- Cops per 20cm (N20)
- Marcadors de refús (R)
- Nivell freàtic (N.F.)

**Excel associat:** `DPSH.xls` - Transcripció manual dels valors de camp.

### SONDEIG.pdf
Full de camp del sondeig a rotació escrit a mà:
- Capes de sòl amb descripcions
- Profunditats de transició
- Resultats SPT (si n'hi ha)
- Nivell freàtic
- Profunditat de roca

**Sense Excel** - Totes les dades s'extreuen visualment.

### A.01.pdf (Plànol)
Plànol de l'arquitecte amb dades del projecte:
- Nom i tipus de projecte
- Ubicació, promotor, arquitecte
- Dimensions de parcel·la i edifici
- Número de plantes i alçada

**Sense Excel** - Dades del caixetí i cotes del plànol.

## Pestanyes del Wizard

| Pestanya | Font | Funció |
|----------|------|--------|
| DPSH | PENETROS.pdf vs Excel | Revisar discrepàncies N20 |
| Sondeig | SONDEIG.pdf | Revisar capes sòl (baixa confiança) |
| Plànol | A.01.pdf | Revisar dades extretes del plànol |
| Wizard | Tots els prefills | Revisar/ajustar tots els camps + generar |

## Web Wizard (FastAPI)

Interfície principal d'Eva. Claude Code serveix el wizard en segon pla.

```bash
# Iniciar (Claude Code ho fa automàticament)
.venv/bin/python -m web
# Eva obre http://localhost:8765/review.html
```

**Arquitectura:**
- `web/api.py` — Endpoints REST (`/api/projects`, `/api/prefills/{p}`, `/api/wizard/{p}`, `/api/generate/{p}`, `/api/report/{p}`, `/api/user-data/{p}`, `/api/geolocalitzar/{p}`)
- `web/wizard_service.py` — Capa de servei: auto_extract + wizard prefills + geocodificació + cache
- `templates/validation/review.html` — UI amb 4 pestanyes

**Flux al seleccionar projecte:**
1. Eva selecciona projecte → crida `/api/prefills/{p}`
2. Backend executa Fase 0 + 0.5 (Python, ~5s)
3. Backend invoca Claude vision per Fase 1 (PDFs, ~30s)
4. Wizard es pobla amb tots els prefills
5. Source badges: blau=auto, verd=user_data, gris=defecte
6. Eva ajusta → Guardar → Generar Informe → descarregar .docx

**Camps:** Dades Projecte, Adjacents, Paràmetres, Coordenades UTM, Overrides Experts

## Geocodificació UTM

Quan un projecte no té COORDENADES.txt (GPS de camp), el sistema deriva coordenades UTM aproximades.

**Pipeline** (`automation/geocode_coordinates.py`):
1. Nominatim (OpenStreetMap) → lat/lon (~50-200m precisió)
2. Cadastre OVC API → referència cadastral + adreça verificada
3. Cadastre WFS INSPIRE → geometria parcel·la EPSG:25831
4. Distribució punts dins parcel·la (centroide o eix major)
5. ICGC MDT → elevacions per punt

**Integració:**
- `auto_extractor.py` Fase 2.5: s'executa automàticament si no hi ha UTM
- Wizard web: botó "Geolocalitzar amb ICGC" (`POST /api/geolocalitzar/{p}`)
- Skill: `/g3dt-geocodificar reference-material/{projecte}`
- Cache: 90 dies a `~/.g3dt/cache/geocode/`

**Fonts d'adreça** (prioritat): `street_address` > `site_address` > `adjacent_south`

## Comandaments Útils

```bash
# Executar extracció simulada (per testing)
uv run --with xlrd,pydantic python3 -m automation.validation.extractor \
    reference-material/4001612-bell-lloc/PENETROS.pdf \
    reference-material/4001612-bell-lloc/ANNEXES/4001612_DPSH.xls

# Servir review.html localment
cd templates/validation && python3 -m http.server 8765
```

## Contacte

Eficients.cat - Automatització amb Claude Code
