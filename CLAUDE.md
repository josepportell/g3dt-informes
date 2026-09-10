# G3DT - Automatització d'Informes Geotècnics

Client: G3 Geotècnia i Geologia SL
Projecte: Automatització de la generació d'informes geotècnics

## ⚠ Inici de sessió: comprovació de branca git

**Directiva (2026-05-04):** a l'inici de cada sessió de treball en aquest projecte, **abans de qualsevol altra acció**, executa `git branch --show-current` i comunica el resultat al Josep en una sola línia. Exemple:

> Branca actual: `production/g3dt-eva-v1` (worktree prod)
> Branca actual: `experiment/ai-pipeline` (worktree dev)

**Per què:** treballem amb dos worktrees actius — `clients/g3dt/` (dev, normalment `experiment/ai-pipeline`) i `clients/g3dt-prod/` (prod, `production/g3dt-eva-v1`). Si el dia anterior vam tancar a producció, ho hem de saber per no fer canvis a la branca incorrecta. La instal·lació a l'ordinador d'Eva (2026-05-04) depèn de la integritat de `production/g3dt-eva-v1`.

**Si l'estat detectat sembla incoherent** (per exemple, dins de `g3dt-prod/` però la branca no és `production/g3dt-eva-v1`, o canvis pendents inesperats), atura't i pregunta al Josep abans de continuar.

**Excepció (2026-08-22):** durant l'auditoria de producció treballem **in-place** a `g3dt-prod/` sobre la branca `review/prod-audit-2026-08` (sense worktree nou, per decisió del Josep). Trobar `review/*` dins de `g3dt-prod/` és l'estat esperat; `production/g3dt-eva-v1` no rep commits fins que el Josep decideixi fusionar.

**Excepció (2026-08-23):** la línia de treball "nivell A" (alternativa D de `docs/ANALISI-NIVELL-A-LECTURA-HUMANA-2026-08-23.md`) viu a la branca **`experiment/nivell-a-2026-08`**, creada des de `review/prod-audit-2026-08` (`b091f5e`), també in-place a `g3dt-prod/`. Trobar-la aquí és l'estat esperat. **Mai proposar pull/merge a l'Eva** (memòria `feedback_no_pull_eva_success_criterion`).

## Resum

G3DT genera informes geotècnics per a projectes de construcció. Cada informe inclou:
- Dades de camp (DPSH, sondeigs)
- Anàlisi de sòls
- Càlculs de capacitat portant
- Recomanacions de fonamentació

## Model d'Operació

**Estat real (verificat 2026-08-23 amb els logs de l'Eva i `docs/INSTALL-EVA-v1.md`):** a l'ordinador de l'Eva (`C:\g3dt-ia\app`, Python 3.12 Windows natiu, instal·lat 2026-05-04) **NO hi ha Claude Code**. La visió va per API (Anthropic/OpenAI/Groq SDK). Els `.bat` de `scripts/` (WSL + `claude`, març 2026) són el disseny anterior; el `G3DT-Wizard.bat` instal·lat és una versió Windows-nativa que només arrenca `python -m web`. La via subprocess `claude -p` existeix al codi (`web/vision_fast.py`, `wizard_service.start_vision_cli`) darrere de `G3DT_PROD_USE_CLAUDECODE_VISION=false`, mai executada a casa de l'Eva.

**Decisió 2026-08-23 (Josep, "via A"):** Claude Code tornarà a ser el lector de producció — instal·lat a l'ordinador de l'Eva (CLI Windows natiu, amb `ANTHROPIC_API_KEY` o subscripció) i cridat headless pel wizard amb un skill G3DT que llegeix cada document del projecte i escriu candidats del nivell A amb font i cita. Python conserva lectors deterministes de plantilles G3, Cadastre/ICGC, càlculs i informe. Vegeu `docs/ANALISI-NIVELL-A-LECTURA-HUMANA-2026-08-23.md` §10 i `docs/_FOR-NEW-YOU-20260823-1745.md`. El paràgraf següent descriu el flux *objectiu*, no l'actual.

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

**Clau (objectiu via A):** la lectura de documents la farà Claude Code headless (`claude -p`, cf. `web/vision_fast.py`) amb un skill, invocat automàticament pel wizard quan l'Eva selecciona un projecte. Avui (prod `1f1d7fd`) aquesta lectura la fan crides API per tipus de document (`web/vision_groq.py`).

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
Fase 0:    FileScanner         → file_mapping.json (classificació fitxers)
Fase 0.3:  FileMiner           → senyals text (regex miners per PDF, Excel, txt, msg, docx)
Fase 0.4:  Groq LLM            → senyals addicionals (gap-filling intel·ligent)
Fase 0.45: ConceptScout        → concept_map.json (mapa concepte→fitxer + vision probes)
Fase 0.5:  auto_extract()      → prefills automàtics (DPSH, Lab, ICGC, Cadastre, geocode)
Fase 1:    Claude vision       → planol/sondeig/dpsh_extracted.json (lectura PDFs)
           (amb fallback concept_map per quan SmartScan no troba el fitxer correcte)
Fase 2:    Wizard (web)        → Eva revisa prefills, ajusta camps → user_data.json
Fase 3:    ReportGenerator     → {expedient}_generated.docx
```

**Fase 0.3** (`automation/fileminer/`) — Python, ~1-2s:
- FileMiner: recorre TOTS els fitxers del projecte (incl. subcarpetes, .msg)
- Miners per tipus: Excel, PDF text, txt, docx, msg (cos + adjunts)
- Extreu senyals (Signal) amb label, valor, concept_id, confiança
- Competició: resol conflictes entre senyals del mateix concepte

**Fase 0.4** (`automation/fileminer/miners/groq_miner.py`) — Groq LLM:
- Objectiu: fitxers on Python miners troben <3 senyals mapejats
- Envia text a Groq per extracció profunda de variables que falten

**Fase 0.45** (`automation/concept_scout/`) — ConceptScout:
- Escaneig complet de fitxers (inclou carpetes que FileMiner omet: PDF/, FOTOGRAFIES/)
- Agrega senyals de FileMiner → mapa concepte→fitxer amb ranking de prioritat
- Vision probe (Groq primer, Claude fallback): classifica fitxers no-text (imatges, PDFs escanejats)
- Anota tipus de document, conceptes presents, i PÀGINA on apareixen
- Sortida: `validation/concept_map.json` (cacheada per projecte)
- Valor clau: quan SmartScan classifica malament o el fitxer esperat no existeix,
  concept_map proporciona rutes alternatives per a la fase de visió

**Fase 0.5** (`automation/auto_extractor.py`) — Python, ~3-5s:
- DPSH Excel: N20, refús, dates de camp
- Lab PDF: sulfats mg/kg via PyMuPDF
- Geocode: Nominatim + Cadastre → UTM (si no hi ha COORDENADES.txt)
- HTTP: ICGC geologia/elevació/pendent + Cadastre adjacents

**Fase 1** — Claude vision (integrada al pipeline):
- Plànol (A.01.pdf): arquitecte, promotor, dimensions, plantes, alçada
- Sondeig annex (ANNEXES/*_sondeig.pdf): nivells geològics, cota referència
- Penetros (PENETROS.pdf): validació N20 vs Excel, discrepàncies
- **Fallback concept_map**: si SmartScan no assigna fitxer a un vision_type,
  concept_map.json identifica el millor candidat alternatiu
- Normalitzadors: `normalize_planol()`, `normalize_sondeig()` — canonicalitzen claus variants
- Backend per defecte: Claude (més fiable que Groq per lectura de columnes)

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
│   ├── concept_scout/        # Fase 0.45: mapa concepte→fitxer (ConceptScout)
│   │   ├── __init__.py       # scout_project() — API pública
│   │   ├── models.py         # ConceptMap, FileEntry, ConceptSource
│   │   ├── scanner.py        # Enumeració completa de fitxers
│   │   ├── aggregator.py     # Agrupació senyals per concepte
│   │   └── vision_probe.py   # Classificació visual (Groq→Claude fallback)
│   ├── fileminer/            # Fase 0.3: extracció senyals text
│   ├── dpsh_extractor.py     # Extracció de dades DPSH d'Excel
│   ├── format_learner.py     # Detecció + aprenentatge de formats nous
│   ├── geocode_coordinates.py # Geocodificació adreça → UTM (Nominatim+Cadastre) — VIA B, no tocar
│   ├── municipis.py          # Padró de municipis de Catalunya (offline, sense xarxa)
│   ├── data/municipis_padro_cadastre.json  # 947 municipis: grafia INE + Cadastre + codis
│   ├── vision_normalizer.py  # Normalització claus vision (planol + sondeig)
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
│       └── review.html       # UI web: 5 pestanyes (DPSH, Sondeig, Plànol, Imatges, Wizard)
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

## Metodologia d'Eva (source-of-truth de càlculs)

`docs/METODOLOGIA-EVA.md` (2026-04-17) — síntesi dels 7 informes signats amb cites textuals: Crespo Villalaz (c/φ), Rodríguez Ortiz "Curso aplicado de cimentaciones" Cap. 2 (bicapa, Fig. 2.9), Schmertmann 1970 (E/assentaments, 2B/4B), Terzaghi-Peck (Qa granular). PDF d'Ortiz Cap. 2 arxivat a `docs/research/books/`. **Abans de modificar qualsevol càlcul geotècnic, consulta aquest document.**

**Regla d'or (2026-09-02): els geotècnics divergeixen de les fórmules amb criteris pactats — modela CRITERIS,
no fórmules.** Arrodoniment professional (Qa a 0,5; E a 10/50; φ enter), topalls Qa per règim (3,0 sòl / 3,5
granular dens / 3,0 roca mixta), ajust litològic (carbonatació→E↑), l'estrat que mana és **on recolza la
fonamentació** (la frase del Qa del signat el DECLARA: encastament 20-40 cm — repàs R 2026-09-03),
assentament = verificació de servei (±50 %).
La cadena Qa que ho implementa està validada **6/7 MATCH exacte**. Família de documents (tots a `docs/`):

| Document | Què hi ha |
|---|---|
| `CRITERIS-CALCUL-EVA.md` | cadena Qa reverse-engineered 6/7 exacte; topalls; arrodoniment confirmat amb 4 fonts externes; taula 9 nivells signats |
| `RECERCA-PRACTICA-GEOTECNICA-ESPANYA.md` | pràctica espanyola; cap correlació sola reprodueix l'E d'Eva; taules Crespo (apèndix) |
| `ANALISI-SETTLEMENT-BACK-ENGINEERING.md` §5 | procés de decisió del geotècnic; per què E=650 a Bell-lloc (carbonatades) |
| `CALCUL-E-MODUL-DEFORMACIO.md`, `CALCUL-K30-BALAST.md` | racional E v1 + proposta v2; K30=E/75 (E/60 roca) validat 2/2 |
| `RECERCA-CRITERIS-DESCRITS-ALS-INFORMES-2026-09-03.md` | tasca R: els criteris que Eva DESCRIU als informes (7/7, cites amb pàgina); resol P1, tanca P3 en negatiu, capgira Anciles |
| `ANALISI-CALCUL-N20-E-2026-09-02.md` | estat actual N20+E vs signats; forats coneguts (columna N, ferm, E per règims); pla: `PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md` |

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
| Imatges | Fotos del projecte + calaix de figures | Tria d'imatges de l'informe (2026-09-09/10): per ranura, «Alternatives (n)» obre la finestreta amb l'actual, les alternatives dels lectors, «Puja una imatge» (qualsevol ranura, també geològic/tall/cullera), el peu de les figures del projecte i la tornada a l'automàtic. La mateixa finestreta s'obre des de la secció «Imatges de l'informe» del Wizard. Res abans de llançar el pipeline. |
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
- `templates/validation/review.html` — UI amb 5 pestanyes (DPSH, Sondeig, Plànol, Imatges, Wizard)

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

## Interpretació d'adreces i municipi (via A)

Camí **independent** del de dalt: `geocode_coordinates.py` és **via B de producció** (es pot llegir, mai
modificar mentre l'Eva hi treballi). La via A resol l'adreça llegida cap a parcel·les cadastrals.

```
skill de lectura  →  street_address (text) + street_address_struct (objecte, a extra_concepts)
        ↓
portals_from_address()      regex determinista → (nom de via, [(núm, lletra)])
        ↓
municipis.lookup()          padró local, 947 municipis, SENSE xarxa; bucle en línia si no hi és
        ↓
resolve_via()               tria sobre la llista REAL de carrers del municipi, sense llindar de mida
        ↓
resolve_portal() (pnp, plp) EXACTES  →  WFS: àrea + polígon  →  contigüitat  →  senyals
```

**Les tres regles que no es toquen:**

1. **Alternatives sí a l'eix via/municipi, mai a l'eix portal.** Les variants de via i municipi són
   ortogràfiques (`11`↔`ONZE`, `GIRASSOLS`↔`GIRASOLS`, ca/es); 18A i 18B són **edificis diferents**.
2. **Cap nom acceptat surt del model.** Sempre de la llista real del municipi o del padró.
3. **Empat = blanc.** Val més cap parcel·la que la d'un altre carrer (ERR = 0 mana sobre la cobertura).

| Fitxer | Què |
|---|---|
| `automation/municipis.py` | padró (exacte / forma curta / preposicions), un sol guanyador |
| `automation/data/municipis_padro_cadastre.json` | 947 municipis: grafia INE + grafia i codis del Cadastre |
| `automation/lectura/address_struct.py` | valida `street_address_struct`; vocabulari d'adreces (`FLOOR_ORDINAL_RE`) |
| `automation/lectura/cadastre_reader.py` | `portals_from_address`, `resolve_via`, `resolve_portal`, senyals |

**Doc complet:** `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` (8 decisions, mesures, i el que queda obert).

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
