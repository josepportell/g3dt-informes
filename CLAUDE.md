# G3DT - Automatització d'Informes Geotècnics

Client: G3 Geotècnia i Geologia SL
Projecte: Automatització de la generació d'informes geotècnics

## Resum

G3DT genera informes geotècnics per a projectes de construcció. Cada informe inclou:
- Dades de camp (DPSH, sondeigs)
- Anàlisi de sòls
- Càlculs de capacitat portant
- Recomanacions de fonamentació

## Skills Disponibles

### /g3dt-validar-penetros
Extreu i valida dades DPSH de fulls de camp escanejats comparant amb l'Excel.

```
/g3dt-validar-penetros reference-material/4001612-bell-lloc/PENETROS.pdf
```

**Què fa:**
1. Llegeix visualment el PDF de camp (escrit a mà)
2. Extreu valors N20 per a cada assaig
3. Compara amb les dades Excel existents
4. Genera JSON amb discrepàncies marcades
5. G3DT revisa només les diferències

### /g3dt-validar-sondeig
Extreu dades de sondeigs a rotació de fulls de camp escanejats.

```
/g3dt-validar-sondeig reference-material/4001612-bell-lloc/SONDEIG.pdf
```

**Què fa:**
1. Llegeix visualment el PDF de camp (escrit a mà)
2. Extreu capes de sòl amb descripcions
3. Extreu resultats SPT si n'hi ha
4. Genera JSON amb nivells de confiança
5. G3DT revisa valors amb baixa confiança

### /g3dt-extreure-planol
Extreu dades del plànol de l'arquitecte per a l'informe.

```
/g3dt-extreure-planol reference-material/4001612-bell-lloc/A.01.pdf
```

**Què fa:**
1. Llegeix visualment el PDF del plànol
2. Extreu: nom projecte, ubicació, promotor, arquitecte
3. Extreu dimensions: parcel·la, ocupació, plantes, alçada
4. Genera JSON amb nivells de confiança
5. G3DT revisa i corregeix si cal

### /g3dt-adjacents-visor
Agent visual per identificar parcel·les adjacents usant el visor cartogràfic del Cadastre.

```
/g3dt-adjacents-visor reference-material/4001612-bell-lloc
```

**Què fa:**
1. Obre el visor del Cadastre amb Playwright (per referència catastral)
2. Fa screenshot del mapa amb la parcel·la centrada
3. Analitza visualment els adjacents (carrers i parcel·les veïnes)
4. Genera JSON amb adjacents i nivells de confiança
5. Opcionalment actualitza user_data.json

**Prioritat al report_generator.py:**
1. user_data.json (camps ja omplerts)
2. validation/adjacents_visor.json (generat per aquest skill)
3. cadastre_adjacents.py API probes (fallback automàtic)

### /g3dt-geocodificar
Deriva coordenades UTM aproximades a partir de l'adreça del projecte quan no hi ha COORDENADES.txt (sense GPS de camp).

```
/g3dt-geocodificar reference-material/4001612 BELL-LLOC
```

**Què fa:**
1. Cerca l'adreça a Nominatim (OpenStreetMap) → lat/lon
2. Localitza la parcel·la al Cadastre (API OVC) → referència cadastral
3. Obté geometria parcel·la via WFS INSPIRE → polígon EPSG:25831
4. Distribueix punts d'investigació dins la parcel·la
5. Consulta elevacions ICGC MDT per cada punt
6. Genera COORDENADES.txt al format estàndard

### /g3dt-informe-geotecnic
Genera un informe geotècnic complet a partir de les dades del projecte.

### /g3dt-demo-informe
Demostra la generació d'informes amb dades de mostra.

## Pipeline de Generació d'Informes

```
Fase 0:   FileScanner         → file_mapping.json (classificació fitxers)
Fase 0.5: auto_extract()      → prefills automàtics (DPSH, Lab, ICGC, Cadastre)
Fase 2.5: geocode_project()   → UTM coords (fallback si no hi ha COORDENADES.txt)
Fase 1:   Validació visual    → planol/sondeig/dpsh_extracted.json (Claude vision)
Fase 2:   Wizard (web/CLI)    → user_data.json (Eva confirma/corregeix prefills)
Fase 3:   ReportGenerator     → {expedient}_generated.docx
```

**Fase 0.5** (`automation/auto_extractor.py`) executa en ~3s:
- Fase 1 local: FileScanner, DPSH Excel (N20, refús), dates de camp
- Fase 2 PDF: Lab results (sulfats mg/kg) via PyMuPDF
- Fase 2.5 geocode: Nominatim + Cadastre → UTM (si no hi ha COORDENADES.txt)
- Fase 3 HTTP: ICGC geologia/elevació/pendent + Cadastre adjacents (requereix UTM)

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
├── automation/               # Mòduls d'extracció i càlcul
│   ├── auto_extractor.py     # Fase 0.5: pre-omple camps automàticament
│   ├── dpsh_extractor.py     # Extracció de dades DPSH d'Excel
│   ├── geocode_coordinates.py # Geocodificació adreça → UTM (Nominatim+Cadastre)
│   ├── project_extractor.py  # Extracció de tot el projecte
│   ├── report_data.py        # Model de dades unificat
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
├── reference-material/       # Projectes de mostra (4 projectes)
└── tests/                    # Tests (geocode: 47 tests)
```

## Flux de Treball de Validació

```
┌─────────────────────────────────────────────────────────────┐
│ DPSH (PENETROS.pdf):                                        │
│ 1. G3DT fa treball de camp → PENETROS.pdf (escrit a mà)    │
│ 2. G3DT transcriu → DPSH.xls (Excel)                        │
│ 3. Claude llegeix PDF → extreu dades visualment             │
│ 4. Sistema compara PDF vs Excel → marca discrepàncies       │
│ 5. G3DT revisa NOMÉS discrepàncies (review.html → DPSH)     │
│ 6. Dades aprovades → informe final                          │
├─────────────────────────────────────────────────────────────┤
│ SONDEIG (SONDEIG.pdf):                                      │
│ 1. G3DT fa sondeig → SONDEIG.pdf (escrit a mà)             │
│ 2. Claude llegeix PDF → extreu capes i SPT                  │
│ 3. G3DT revisa valors baixa confiança (review.html → Sondeig)│
│ 4. Dades aprovades → informe final                          │
├─────────────────────────────────────────────────────────────┤
│ PLÀNOL (A.01.pdf):                                          │
│ 1. Arquitecte proporciona plànol → A.01.pdf                 │
│ 2. Claude llegeix PDF → extreu dimensions i dades           │
│ 3. G3DT revisa/corregeix (review.html → Plànol)             │
│ 4. Dades aprovades → informe final                          │
└─────────────────────────────────────────────────────────────┘
```

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

## Formulari de Revisió (review.html)

El formulari té quatre pestanyes per als diferents documents:

| Pestanya | Document | Comparació | Focus |
|----------|----------|------------|-------|
| DPSH | PENETROS.pdf | vs Excel | Discrepàncies |
| Sondeig | SONDEIG.pdf | Cap | Baixa confiança |
| Plànol | A.01.pdf | Cap | Tots els camps |
| Wizard | user_data.json | Prefills vs user | Tots els camps + UTM + overrides |

Per obrir: `cd templates/validation && python3 -m http.server 8765`

## Web Wizard (FastAPI)

Servidor web que substitueix el wizard CLI per una interfície de navegador.

```bash
# Iniciar servidor
uv run python -m web
# Obre http://localhost:8765/review.html
```

**Arquitectura:**
- `web/api.py` — 7 endpoints REST (`/api/projects`, `/api/prefills/{p}`, `/api/wizard/{p}`, `/api/generate/{p}`, `/api/report/{p}`, `/api/user-data/{p}`, `/api/geolocalitzar/{p}`)
- `web/wizard_service.py` — Capa de servei: auto_extract + wizard prefills + geocodificació + cache
- `templates/validation/review.html` — UI amb 4 pestanyes

**Pestanya Wizard:**
- Camps agrupats: Dades Projecte, Adjacents, Paràmetres, Coordenades UTM, Overrides Experts
- Source badges (blau=auto, verd=user_data, gris=defecte) per cada camp
- Botó "Geolocalitzar amb ICGC": geocodifica adreça → UTM via Nominatim+Cadastre
- Botó "Actualitzar prefills": re-executa Fase 3 amb noves coordenades UTM
- Validació límits Catalunya (X: 250000-550000, Y: 4450000-4750000)
- Guardar → user_data.json → Generar Informe → descarregar .docx

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
