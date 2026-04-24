# Arquitectura: AI Pipeline

**Data:** 2026-04-24
**Branca:** `experiment/ai-pipeline`
**Autor:** Josep Portell + Claude Code
**Estat:** Fases 1, 2 i 3 implementades. Fase 4 dissenyada (pendent d'implementació). Fases 5–7 pendents de disseny.

---

## 1. Resum executiu

**AI Pipeline** és un pipeline alternatiu de generació d'informes geotècnics, dissenyat per substituir — a llarg termini — el pipeline determinista actual (`FileScanner` / `FileMiner` / `ConceptScout` / `auto_extractor`). Es construeix en una branca experimental i **coexisteix** amb el pipeline existent: no el modifica, no el reemplaça fins que no demostri paritat i millora.

La motivació és una línia de progressió natural:
- El pipeline actual depèn de regles, regex, classificadors per rol, i punts fixos on es crida a Claude per visió.
- L'AI Pipeline inverteix el ordre: llegeix primer, raona després. Cada fase assumeix que la següent tindrà més context, no menys.
- Stage per stage, l'LLM passa de ser "consumidor d'inputs estructurats" a ser "intèrpret del projecte sencer".

**Estat actual:** Fase 1 (Inventari) funcionant end-to-end (CLI + API + pestanya del wizard).

---

## 2. Visió: les 7 fases

| # | Fase                      | Responsabilitat                                                            |
|---|---------------------------|-----------------------------------------------------------------------------|
| 1 | **Inventari**             | Enumerar tots els fitxers del projecte (incloent adjunts de .msg).          |
| 2 | **Tipologia**             | Classificar cada fitxer pel seu **tipus tècnic** (PDF text, PDF scanned, Excel amb imatges, etc.), marcar els inútils, i extreure imatges embegudes com a fitxers propis. |
| 3 | **Conversió**             | Produir artefactes LLM-ready per cada fitxer útil: markdown per pàgina de PDF, CSV per full d'Excel, PNG per pàgina escanejada, markdown per cos .msg/DOCX. |
| 4 | **Anàlisi**               | Per cada font, l'LLM llegeix els artefactes i emet (a) un `SourceInsight` (què és el document) i (b) `Candidate` values per les 53 variables de l'informe. |
| 5 | **Source of truth**       | Resoldre conflictes entre fonts — triar valor autoritatiu per cada concepte. |
| 6 | **Assignació a variables**| Mapejar valors a les ~53 variables de l'informe. Marcar els buits per Eva. |
| 7 | **Generació de l'informe**| Produir el .docx final (reutilitzant `ReportGenerator` o substituint-lo).   |

Cada fase produeix un artefacte JSON persistent dins `{projecte}/validation/` que la fase següent consumeix. Això permet:

- **Diagnòstic fàcil:** cada stage es pot executar i inspeccionar de manera aïllada.
- **Reproducibilitat:** un bug a la Fase 4 no obliga a re-executar la Fase 1.
- **Hibridació futura:** una fase pot quedar-se al pipeline determinista si demostra ser superior.

---

## 3. Principis de disseny

### 3.1 Coexistència amb el pipeline actual
Res del pipeline determinista (FileScanner, FileMiner, ConceptScout, auto_extractor) es modifica. L'AI Pipeline viu íntegrament a `automation/ai_pipeline/`. El wizard manté totes les pestanyes existents i n'afegeix una de nova ("AI Pipeline").

### 3.2 Reutilització, no reimplementació
Quan una funció existent ja fa bé una subtasca, la reutilitzem directament. Exemple a la Fase 1:
- `MsgMiner._save_attachments` ja materialitza adjunts de .msg amb dedupe per hash SHA256 i carpeta sidecar per email. Reutilitzat íntegrament.
- `concept_scout.scanner.enumerate_project_files` ja enumera amb les regles correctes de skip i tipifica fitxers. Reutilitzat íntegrament.

No reescriurem la roda per cada fase; identificarem els trossos reutilitzables abans d'escriure codi nou.

### 3.3 Accessible per 3 vies
Cada fase ha de ser consultable de tres maneres:
- **(a) Conversacional:** Claude pot llegir el JSON i respondre preguntes.
- **(b) Programàtica:** funcions Python exposen l'objecte pydantic amb mètodes de consulta.
- **(c) Estàtica:** JSON persistit al disc que qualsevol eina pot llegir (jq, grep, frontend).

### 3.4 Cache explícit, refresh opcional
Tots els artefactes són cacheats per defecte. Eva veu dades instantànies al wizard. Un botó "Refresh" força re-execució. El CLI té `--save` (escriu cache) i bandera per saltar sub-fases costoses.

---

## 4. Fase 1: Inventari (implementada)

### 4.1 Què fa
Donat un projecte, produeix un `Inventory` amb:
- Comptatge total de fitxers
- Comptatge a l'arrel
- Comptatge per cada subcarpeta (no recursiu)
- Llista plana de tots els fitxers amb: ruta relativa, mida KB, tipus (pdf_vector / pdf_scanned / excel / image / text / email / docx / other), origen (`regular` vs `email_attachment`), i si és adjunt, el `.msg` pare.

Abans del walk, extreu tots els adjunts dels fitxers `.msg` del projecte a `{project}/validation/msg_attachments/{email_stem}/`. Si l'extracció ja s'ha fet en una execució anterior, el dedupe per content-hash evita reescritures.

### 4.2 Com s'utilitza

**CLI** (per desenvolupament, diagnòstic, batch):
```bash
.venv/bin/python scripts/ai_pipeline_inventory.py --project 4001612
.venv/bin/python scripts/ai_pipeline_inventory.py --project 4001612 --save
.venv/bin/python scripts/ai_pipeline_inventory.py --project 4001612 --json
.venv/bin/python scripts/ai_pipeline_inventory.py --project-path "reference-material/4001612 BELL-LLOC"
.venv/bin/python scripts/ai_pipeline_inventory.py --project 4001612 --no-extract
```

**API HTTP** (via wizard o qualsevol client):
```
GET /api/ai-pipeline/inventory/{project_name}
GET /api/ai-pipeline/inventory/{project_name}?refresh=true
```
Retorna `{"inventory": {...}, "cached": bool}`.

**Python** (accés programàtic):
```python
from automation.ai_pipeline.inventory import build_inventory, load_inventory

inv = build_inventory("reference-material/4001612 BELL-LLOC")
print(inv.total_files, inv.msg_count, inv.extracted_attachments)

# Mètodes de consulta
inv.files_in_folder("ANNEXES")                  # fitxers directament dins ANNEXES/
inv.find_by_name("penetros")                     # substring case-insensitive
inv.files_of_type("excel")                       # tots els Excel

# Cache (llegir sense re-executar)
inv_cached = load_inventory("reference-material/4001612 BELL-LLOC")
```

**Wizard** (producció per Eva):
- Pestanya "AI Pipeline" → 4 targetes de resum + taula de carpetes + taula de fitxers amb filtre per nom + botó Refresh.

### 4.3 Sortida canònica
Fitxer: `{projecte}/validation/ai_inventory.json`

Esquema (pydantic `Inventory`):
```
project_path          : str  (absolute resolved path)
scanned_at            : str  (ISO-8601 UTC)
total_files           : int
root_file_count       : int
folders               : [FolderSummary]  — sorted by path
files                 : [InventoryFile]
msg_count             : int
extracted_attachments : int
```

`InventoryFile`: `path` (relative POSIX), `size_kb`, `type`, `kind` (`regular` | `email_attachment`), `parent_msg` (relative path del .msg pare, només si `kind=email_attachment`).

`FolderSummary`: `path` (""  = arrel), `file_count` (no recursiu — només fitxers directes).

### 4.4 Codi reutilitzat

| Funció reutilitzada                                  | Font                                             | Per què                                      |
|------------------------------------------------------|--------------------------------------------------|----------------------------------------------|
| `MsgMiner._save_attachments`                         | `automation/fileminer/miners/msg_miner.py`       | Dedupe per hash + sidecar per email          |
| `concept_scout.scanner.enumerate_project_files`      | `automation/concept_scout/scanner.py`            | Walk + skip rules + tipificació              |

L'inventari **no re-implementa** el walk, ni la tipificació de PDFs vectorials vs escanejats, ni la gestió de `validation/msg_attachments/`. Tot ve via aquests dos mòduls.

---

## 5. Fase 2: Tipologia (implementada)

### 5.1 Què fa i què NO fa

**Fa:**
- Classifica cada fitxer de l'inventari pel seu **tipus tècnic** (no pel seu rol semàntic).
- Decideix si és útil per generar l'informe o no (`useful: bool`), amb motiu explícit.
- Introspecciona l'estructura: pàgines de PDF, fulls d'Excel, nombre d'imatges embegudes, text extraïble.
- Extreu totes les imatges embegudes de PDFs, Excels i DOCXs a fitxers propis al disc.
- Proposa una estratègia de conversió per a la Fase 3 (`conversion_strategy`).
- Produeix un resum per Eva: "això és el que has aportat".

**NO fa:**
- No decideix què representa el fitxer (plànol arquitectònic? fitxa DPSH? email de pressupost?). Això és contingut, s'aborda a Fase 4+.
- No reutilitza `SmartScan`. `SmartScan` classifica per **rol semàntic** (25 rols com `architect_plan`, `dpsh_excel`); Fase 2 classifica per **tipus tècnic** (com `pdf_text`, `pdf_mixed`, `spreadsheet_mixed`). Són capes diferents.
- No interpreta imatges (logo? foto? plànol?). Això és Fase 4 (vision).

### 5.2 Filosofia: transparència davant d'Eva

Citació d'Alfonso: *"No estem construint un enginyer geotècnic AI. Estem construint un assistent intel·ligent de redacció d'informes a partir del contingut que ens proporcionen."*

Fase 2 materialitza aquest principi. Eva ha de poder veure, en ordre:
1. **"Això és el que has aportat"** (Fase 2 — tipologia).
2. *"Això és el que hem entès del que has aportat"* (Fases 3–5).
3. *"Aquest és l'informe que podem escriure a partir d'això"* (Fases 6–7).

Si la qualitat d'un informe és baixa, Eva ha de poder recórrer la cadena cap enrere i veure que a Fase 2 hi havia poc input útil, no que la màquina ha fet magia negra. La traçabilitat per `source_chain` (vegeu 5.5) permet això.

### 5.3 Models de dades

```python
class FileClass(BaseModel):
    path: str                       # ID primari, ruta relativa POSIX
    format: str                     # extensió normalitzada: pdf, xlsx, docx, msg, jpg, …
    category: str                   # bucket tipològic (vegeu 5.4)

    # Introspecció estructural (tot determinista, Python)
    has_text: bool
    has_images: bool
    image_count: int = 0            # imatges extretes a disc
    page_count: int = 0             # pàgines de PDF
    sheet_count: int = 0            # tabs d'Excel
    sheet_names: list[str] = []     # noms de tabs en ordre

    # Procedència — la cadena de fonts, per traçabilitat
    source_chain: list[str] = []    # p.ex. ["email-abc.msg", "attachment:budget.xlsx", "sheet:Costs"]
    is_attachment: bool = False     # si ve d'un .msg
    parent_path: str | None = None  # si l'hem extret d'un altre fitxer

    # Guia per Fase 3
    useful: bool
    reason: str = ""                # si s'ignora, per què
    conversion_strategy: str        # hint de dispatch per Fase 3

    # Artefactes creats per Fase 2
    extracted_images_dir: str | None = None  # on hem desat les imatges filles

class FolderClass(BaseModel):
    path: str                       # "" = arrel
    parent: str | None              # None per l'arrel; camí immediat en cas contrari
    file_count: int                 # total de fitxers directes (sense recursió)
    useful_count: int               # fitxers útils directes
    category_counts: dict[str, int] # recompte per categoria
    is_dev_only: bool = False       # si és dins d'un dir top-level dev-only

class ProjectTypology(BaseModel):
    project_path: str
    classified_at: str
    files: list[FileClass]          # plana — inclou fills extrets
    folders: list[FolderClass]      # roll-up amb estructura arbre via `parent`
    counts_by_category: dict[str, int]
    useful_count: int
    skipped_count: int
    eva_summary: list[str]          # línies llegibles per Eva
    warnings: list[str] = []        # p.ex. "extensió desconeguda: .abc"

    # Query helpers
    def children_of(self, parent_path: str) -> list[FileClass]: ...  # fills extrets
    def subfolders_of(self, parent_path: str) -> list[FolderClass]: ...
    def folder_tree(self) -> dict[str, list[str]]: ...  # adjacency list per UI
    def lineage_of(self, path: str) -> list[str]: ...  # retorna source_chain
```

### 5.4 Taxonomia de categories (tipus tècnic, no rol semàntic)

| category             | Coincidència                                               | útil? | conversion_strategy (Fase 3)         |
|----------------------|------------------------------------------------------------|-------|--------------------------------------|
| `pdf_text`           | PDF vectorial, text extraïble, 0 imatges embegudes         | ✓     | `pdf_to_markdown`                    |
| `pdf_mixed`          | PDF vectorial + ≥1 imatge embeguda                         | ✓     | `pdf_to_markdown_plus_images`        |
| `pdf_scanned`        | PDF sense text extraïble (pàgines imatge)                  | ✓     | `pdf_pages_to_images`                |
| `docx` / `doc`       | Word (`.doc` via LibreOffice)                              | ✓     | `docx_to_markdown_plus_media`        |
| `spreadsheet`        | `.xls` / `.xlsx`, sense imatges embegudes                  | ✓     | `excel_per_sheet_to_csv`             |
| `spreadsheet_mixed`  | `.xls` / `.xlsx` amb imatges embegudes                     | ✓     | `excel_per_sheet_to_csv_plus_images` |
| `email_msg`          | cos del `.msg` (els adjunts ja són fitxers separats a F1)  | ✓     | `msg_body_to_markdown`               |
| `text`               | `.txt`, `.csv`                                             | ✓     | `text_passthrough`                   |
| `image`              | `.jpg`, `.png`, `.bmp`, `.tiff` (tant Eva com extretes)    | ✓     | `image_passthrough`                  |
| `reference_output`   | Dins de `PDF/`, `PDF V0/`, `PDF-V0/` (només)               | ✗     | `skip` — dev-only, absent en prod    |
| `pipeline_artifact`  | Els nostres JSONs (`ai_inventory.json`, etc.)              | ✗     | `skip`                               |
| `binary_unreadable`  | `.fh11`, `.psd`                                            | ✗     | `skip`                               |
| `system_file`        | `Thumbs.db`, `~$*`, `*.tmp`                                | ✗     | `skip`                               |
| `unknown`            | extensió no gestionada                                     | ✗     | `skip` amb avís                      |

**Nota:** `ACCEPTACIO/` NO és dev-only. És la carpeta on el client signa la factura del projecte — conté inputs potencialment útils (correus, signatures).

### 5.5 Provenance: `source_chain`

Cada `FileClass` porta una llista ordenada que reconstrueix la seva història completa:

```
"email-abc.msg"
  → "attachment:budget.xlsx"
    → "sheet:Costs"
      → "img:2"          # imatge extreta de la fulla "Costs"
```

Per qualsevol fitxer — Eva-provided o extret per nosaltres — un Stage posterior pot respondre "d'on ha vingut això?" sense haver de recuperar metadata de múltiples llocs. Stage 4 (vision sobre una imatge) rebrà al prompt la cadena completa: *"aquesta imatge ve d'un Excel anomenat 'budget.xlsx', adjunt a un email amb subject 'Pressupost' enviat per client@..."*.

### 5.6 Extracció d'imatges embegudes

**On es desen:** `{projecte}/validation/ai_pipeline/extracted/{source_file_stem}/img_001.png` (mateixa convenció que `msg_attachments/{stem}/` de Fase 1).

**Cada imatge extreta esdevé un `FileClass` propi** amb:
- `category = image`, `useful = True`
- `parent_path` apuntant al fitxer origen
- `source_chain` amb el rastre complet

**Llibreries d'extracció:**
- PDF: `PyMuPDF` via `page.get_images()` + `doc.extract_image()`
- DOCX: descomprimir com a ZIP i copiar `word/media/*`
- Excel: `openpyxl` via `sheet._images`
- `.msg`: ja gestionat per Fase 1 (adjunts = fitxers propis del projecte)

**Filtre de mida mínima:** s'ignoren imatges amb dimensió < 32×32 px o mida < 5 KB. Alineat amb la convenció de `MsgMiner._MIN_ATTACHMENT_BYTES`; evita soroll de logos/icones petites.

**Política de re-execució (fase de desenvolupament):** la re-execució sempre re-extreu amb dedupe per hash SHA256 de contingut (com fa `msg_miner._save_attachments`). Quan confiem en les extraccions prèvies, es podrà canviar a "skip if exists". Registrat al CHANGELOG.

**TODO v1.1 — detecció de logos per descartar:** pendent de construir una biblioteca de referència de logos G3DT. Llavors s'afegirà filtre per similitud (perceptual hash o ImageMagick compare) per marcar imatges logo amb `useful = False`, `reason = "matches G3DT logo"`.

### 5.7 Detecció dev-only

**Hard-codeat** (promoció a config YAML quan tinguem un segon client):

```python
DEV_ONLY_TOPLEVEL_DIRS = {"PDF", "PDF V0", "PDF-V0"}
```

Qualsevol fitxer amb un primer component de la ruta relativa dins d'aquest conjunt → `category = reference_output`, `useful = False`, `reason = "dins de {dir} — output de runs anteriors d'Eva, absent en producció"`.

### 5.8 Estructura interna: pàgines i fulls com a **metadades**, no entrades

Pàgines de PDF i fulls d'Excel **NO esdevenen `FileClass` propis.** Queden com a metadades del pare (`page_count`, `sheet_names`). Raons:
- No són fitxers al disc — són estructura interna.
- Fase 3 paginarà internament quan produeixi el CSV per full o la imatge per pàgina escanejada.
- Bloatar la tipologia amb una entrada per pàgina faria els resums per a Eva il·legibles.

Excepció: **imatges extretes SÍ esdevenen `FileClass` propis** perquè són fitxers a disc que Fases 4+ processaran com a fitxers (vision).

### 5.9 Resum per Eva (`eva_summary`)

`ProjectTypology.eva_summary` és una llista de línies en català, dissenyada per mostrar a Eva al wizard:

```
Heu aportat 68 fitxers en 16 carpetes.
• 48 fitxers són inputs útils (32 documents, 11 imatges, 5 emails amb 13 adjunts extrets).
• 13 fitxers són deliverables de runs anteriors (es salten — no existiran en producció).
• 7 fitxers són soroll del sistema (es salten).
```

Aquest text és el bridge cap a la pregunta pràctica d'Eva: *"si vull millor qualitat d'informe, què puc aportar millor?"*. El `source_chain` i els comptes per categoria li donen la resposta.

### 5.10 Dependències noves

- `PyMuPDF` (ja present) — extracció d'imatges PDF
- `openpyxl` (ja present) — introspecció Excel + extracció d'imatges
- `python-docx` (a verificar disponibilitat) — introspecció DOCX

### 5.11 Com s'utilitzarà

Seguint el patró de Fase 1:

- **CLI:** `scripts/ai_pipeline_typology.py --project {id} [--save] [--json]`
- **API:** `GET /api/ai-pipeline/typology/{project}?refresh=true`
- **Wizard:** la pestanya "AI Pipeline" mostrarà Fase 1 + Fase 2 com a seccions apilades (no una pestanya nova per fase — la relació Fase 1 → Fase 2 és seqüencial).
- **Python:** `from automation.ai_pipeline.typology import classify_project`

### 5.12 Sortida canònica

Fitxer: `{projecte}/validation/ai_typology.json`

---

## 6. Fase 3: Conversió (implementada)

### 6.1 Què fa i què NO fa

**Fa:**
- Consumeix el `ProjectTypology` de Fase 2 i processa només fitxers amb `useful=True`.
- Per cada fitxer útil, executa el convertidor indicat per `conversion_strategy` i produeix un o més artefactes LLM-ready al directori `{projecte}/validation/ai_pipeline/converted/{source_stem}/`.
- Manté el rastre de provenance: cada artefacte porta `source_path` i `source_chain` heretats del FileClass original.
- Embedeix referències `![](ruta)` a les imatges ja extretes per Fase 2 dins del markdown, a la posició aproximada on apareixen.
- Produeix un manifest (`ai_conversion.json`) amb la llista completa d'artefactes, agrupats per font.

**NO fa:**
- No interpreta contingut. No classifica. No respon preguntes sobre el que hi ha dins dels fitxers — això és Fase 4.
- No fa OCR sobre PDFs escanejats. Els converteix a imatges per pàgina i les passa a Fase 4 perquè usi visió. OCR és un candidat per v1.1.
- No re-extreu imatges embegudes — Fase 2 ja ho ha fet; Fase 3 només les referencia.
- No genera cap `conversion` per fitxers amb `useful=False` o `conversion_strategy=skip` (incloent `reference_output`, `binary_unreadable`, `pipeline_artifact`, `system_file`, `unknown`).

### 6.2 Filosofia: alimentació per Fase 4

Fase 3 és un **pipeline de normalització**: agafa inputs heterogenis (PDF vectorial, PDF escanejat, DOCX, Excel multi-full, .msg, text, imatge) i en treu artefactes uniformes que Fase 4 pot consumir amb la mateixa lògica. El valor és:

1. **Fase 4 no ha de saber d'on ve la dada.** Un markdown és un markdown, tant si ve d'un Excel com d'un PDF. Un PNG per pàgina funciona igual per un plànol escanejat que per una fotografia.
2. **Re-processabilitat granular.** Si una pàgina concreta d'un PDF té mal format, Fase 3 pot re-processar aquella pàgina sense tornar-ho a fer tot.
3. **Debuggable per humans.** Eva pot obrir qualsevol `.md` o `.csv` del directori `converted/` i veure exactament què llegirà l'LLM. Zero caixa negra.

### 6.3 Convertidors per estratègia

| `conversion_strategy` (de Fase 2)      | Convertidor Fase 3                                             | Sortides                                                     |
|----------------------------------------|----------------------------------------------------------------|--------------------------------------------------------------|
| `pdf_to_markdown`                      | `pymupdf4llm.to_markdown()` per pàgina                         | `page_001.md`, `page_002.md`, …                              |
| `pdf_to_markdown_plus_images`          | `pymupdf4llm` per pàgina + `![]()` refs a `extracted/{stem}/…` | `page_NNN.md` amb imatges embegudes                          |
| `pdf_pages_to_images`                  | `PyMuPDF page.get_pixmap(dpi=200)`                             | `page_001.png`, `page_002.png`, …                            |
| `docx_to_markdown_plus_media`          | `pypandoc.convert_file(..., to='gfm')`                         | `body.md` + refs a `extracted/{stem}/…`                      |
| `excel_per_sheet_to_csv`               | `openpyxl` → CSV per `sheet_name`                              | `sheet_<sanitized_name>.csv` per full                        |
| `excel_per_sheet_to_csv_plus_images`   | igual + referències a imatges de Fase 2                        | CSVs + un `images.md` amb refs                               |
| `msg_body_to_markdown`                 | `extract_msg` → markdown amb frontmatter (from/to/date/subject)| `body.md`                                                    |
| `image_passthrough`                    | cap — es referencia el fitxer original                         | (artefacte virtual al manifest)                              |
| `text_passthrough`                     | còpia literal com a `.md` o `.csv`                             | `content.md` o `content.csv`                                 |
| `skip`                                 | cap                                                            | (no apareix al manifest)                                     |

**Llibreria PDF:** `pymupdf4llm` (purpose-built per LLM, gestiona taules i headings amb ordre de lectura correcte). Ja present a les deps.

**Llibreria DOCX:** `pypandoc` → pandoc (binari ja present al sistema). Sortida en `gfm` (GitHub-flavored markdown) per millor suport de taules.

**`.doc` legacy:** Fase 3 invoca `libreoffice --headless --convert-to docx` per produir un `.docx` temporal, després l'alimenta al convertidor pypandoc. Si `libreoffice` no està disponible, marca l'artefacte amb `reason="legacy .doc, LibreOffice absent"` i salta. LibreOffice ja està present al sistema de desenvolupament (`/usr/bin/libreoffice`).

### 6.4 Models de dades

```python
class ConvertedArtifact(BaseModel):
    path: str                       # ruta relativa POSIX de l'artefacte (dins validation/ai_pipeline/converted/)
    format: str                     # "md", "csv", "png", "jpg"
    source_path: str                # ruta del FileClass origen
    source_chain: list[str]         # heretat del FileClass origen
    strategy_used: str              # el conversion_strategy aplicat
    page: int | None = None         # 1-based si s'aplica (PDFs)
    sheet: str | None = None        # nom del full si s'aplica (Excel)
    bytes_written: int = 0          # mida de l'artefacte
    skipped: bool = False           # si no s'ha pogut convertir
    skip_reason: str = ""           # motiu del skip (dep absent, error de format…)

class ProjectConversion(BaseModel):
    project_path: str
    converted_at: str
    artifacts: list[ConvertedArtifact] = Field(default_factory=list)
    per_source: dict[str, list[str]] = Field(default_factory=dict)
        # source_path → llista d'artefactes produïts per aquell fitxer
    total_bytes: int = 0
    warnings: list[str] = Field(default_factory=list)
    eva_summary: list[str] = Field(default_factory=list)

    # Query helpers
    def artifacts_of(self, source_path: str) -> list[ConvertedArtifact]: ...
    def artifacts_by_format(self, fmt: str) -> list[ConvertedArtifact]: ...
```

### 6.5 Granularitat: per-pàgina per defecte

**PDFs** produeixen un fitxer per pàgina (`page_001.md`, `page_002.md`, …). Raons:
- Fase 4 sovint pregunta "què hi ha a la pàgina X?" — accés directe sense parsear delimiters.
- Si una pàgina falla (layout estrany, encriptada), no contamina les altres.
- Els fitxers grans són cars de passar a un prompt; unitats petites donen flexibilitat.

**Excel** produeix un CSV per full. Mateixa raó: Fase 4 pot apuntar al full concret.

**DOCX** produeix un sol `body.md` perquè la divisió per pàgina no és robusta a DOCX (pàgines depenen de renderitzat). Els headings dins del markdown ja serveixen de divisors lògics.

**.msg** produeix un sol `body.md` amb frontmatter YAML (from, to, date, subject, attachments).

### 6.6 Imatges embegudes inline al markdown

Per PDFs i DOCXs amb imatges, Fase 3 embedeix referències al markdown:

```markdown
# Plànol de situació

El projecte es localitza a Alcoletge...

![](../extracted/A.01/img_000.png)

Superfície: 518 m²
```

**Resolució d'ubicació:**
- **PDF:** `pymupdf4llm` pot retornar la posició (bounding box) de cada imatge detectada; les assignem a la pàgina corresponent.
- **DOCX:** `pypandoc` amb `--extract-media` extreu les imatges, però ja les tenim extretes per Fase 2. Post-processem el markdown per fer apuntar les refs a `extracted/{stem}/`.

Els MLMs multimodals actuals (Claude Sonnet 4.6, GPT-4o) accepten markdown amb image refs. Provarem casos amb 16+ imatges (plànols grans) per validar els límits de context — si cal, Fase 4 decidirà pàgina-a-pàgina.

### 6.7 Política de re-execució

Igual que Fase 2: **re-conversió sempre amb dedupe per SHA256 de contingut**. Si un artefacte ja existeix amb el mateix hash que el nou contingut, no reescrivim. Cost afegit mínim. Quan confiem en conversions prèvies, canviarem a "skip-if-exists". Registrat al CHANGELOG.

### 6.8 Resum per Eva (`eva_summary`)

```
Hem convertit 48 fitxers útils a 247 artefactes llegibles per la IA:
• 134 pàgines de PDF convertides a markdown (24 documents).
• 45 pàgines de PDFs escanejats desades com a imatges.
• 15 fulls d'Excel exportats a CSV.
• 2 cossos d'email desats com a markdown.
• 17 imatges estan referenciades com estan (no cal conversió).
```

Aquest resum tanca la primera línia de transparència d'Alfonso: *"això és el que has aportat" → "i això és el que hem pogut llegir d'això"*.

### 6.9 Dependències noves

- **`pymupdf4llm`** (Python, PyPI — ja instal·lat) — PDF → markdown LLM-ready
- **`pypandoc`** (Python, PyPI — ja instal·lat) — wrapper sobre pandoc
- **pandoc** (binari — ja present a `/home/josep/.local/bin/pandoc`)
- **LibreOffice** (binari — ja present a `/usr/bin/libreoffice`) — `.doc` → `.docx` headless

### 6.10 Com s'utilitzarà

- **CLI:** `scripts/ai_pipeline_conversion.py --project {id} [--save] [--json] [--strategy pdf_to_markdown]` (el flag `--strategy` per filtrar un subset durant diagnòstic)
- **API:** `GET /api/ai-pipeline/conversion/{project}?refresh=true`
- **Wizard:** secció "Stage 3: Conversió" sota Stage 2 a la pestanya AI Pipeline, amb llista d'artefactes agrupats per font i botó de preview per cada `.md`/`.csv`
- **Python:** `from automation.ai_pipeline.conversion import convert_project`

### 6.11 Sortida canònica

Fitxer: `{projecte}/validation/ai_conversion.json`
Artefactes a disc: `{projecte}/validation/ai_pipeline/converted/{source_stem}/*`

### 6.12 V1.1 candidats (fora de MVP)

- **OCR per PDFs escanejats** (Tesseract). Avui Fase 3 només els passa a imatges i delega a Fase 4 vision. OCR afegiria un canal deterministic addicional.
- **Previsualització de l'artefacte al wizard** — renderitzar el markdown/CSV in-place per verificació ràpida.
- **Conversion caching per-pàgina en disc** — saltar pàgines ja convertides fins i tot quan re-corrents el projecte sencer.

---

## 7. Fase 4: Anàlisi (dissenyada)

### 7.1 Què fa i què NO fa

**Fa:**
- Agrupa els artefactes de Fase 3 per `source_path` (p.ex. totes les pàgines d'un PDF + els seus artefactes embeguts són una unitat).
- Per cada font, fa **una** crida multimodal a l'LLM amb prompt estructurat que demana dues coses: (a) un `SourceInsight` (què és aquest document), (b) tots els `Candidate`s de valors per les 53 variables de l'informe que siguin extreïbles d'aquest document.
- Recull i desa els resultats a `validation/ai_analysis.json` més artefactes per-font a `validation/ai_pipeline/analysis/{source_stem}/insight.json` + `candidates.json`.
- Produeix un resum per Eva de què s'ha entès del projecte.

**NO fa:**
- No resol conflictes entre candidats (Fase 5).
- No pica valors finals per cada variable (Fase 6).
- No tradueix signals a unitats, no fa càlculs geotècnics, no interpreta — només extreu amb justificació.

### 7.2 Filosofia: "què entén l'LLM d'aquest document"

Alfonso: *no estem construint un enginyer geotècnic, estem construint un assistent de redacció intel·ligent*. Fase 4 encarna això:

- Cada font es llegeix **en context complet** (totes les seves pàgines/fulls junts, més imatges), no pàgina per pàgina. Així l'LLM pot concloure "això és un plànol v2 amb el caixetí a la pàgina 1 i les cotes repartides a les pàgines 2-3" en comptes d'emetre 3 opinions inconsistents.
- Abans d'extreure cap valor, l'LLM descriu la font. El `SourceInsight` recull: tipus de document, propòsit, autor, data, versió, enllaços a altres fonts, suggeriments d'autoritat. Aquesta és la matèria primera de Fase 5.
- Cada valor extret ve amb `quote` verbatim (ancorant el senyal al text de l'artefacte) i `reasoning` (una frase que justifica la inferència). Auditable per construcció.

### 7.3 Models de dades

```python
class SourceInsight(BaseModel):
    """LLM's understanding of what a source document IS, independent of values extracted."""
    source_path: str               # file (or virtual email+attachments group) described
    document_type: str             # "architect_plan" | "dpsh_field_sheet" | "client_email" | "budget_excel" | …
    purpose: str                   # one-sentence plain-language description
    author: str = ""               # "Joan Vidal" if inferable
    date_info: str = ""            # "sent 2025-04-15", "signed 2025-05-20", "undated"
    version_info: str = ""         # "v2; modifies v1"
    related_sources: list[str] = []  # other source_paths this document references
    authority_hints: list[str] = []  # e.g. "best source for parcel dimensions"
    confidence: float              # 0-1 on the insight overall
    notes: str = ""

class Candidate(BaseModel):
    """One candidate value for one concept, extracted from one source."""
    concept_id: str                # e.g., "architect_name", "utm_x", "num_floors"
    value: Any                     # string, number, list, dict — type determined by the concept
    confidence: float              # 0-1
    quote: str                     # verbatim snippet from the artifact
    artifact_path: str             # which specific Stage 3 artifact carried this value
    source_path: str               # the FileClass origin (same as SourceInsight.source_path)
    source_chain: list[str]        # inherited provenance
    extractor: str                 # model id used
    reasoning: str                 # one-sentence justification

class SourceAnalysis(BaseModel):
    """Everything Stage 4 emits for one source."""
    source_path: str
    insight: SourceInsight
    candidates: list[Candidate]
    attempts: int                  # how many LLM attempts before success
    elapsed_ms: int
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

class SourceFailure(BaseModel):
    """A source Stage 4 could not analyze."""
    source_path: str
    error_type: str                # "schema_validation" | "api_error" | "timeout" | "empty_response"
    attempts: int
    last_error: str
    raw_response: str = ""         # stashed for debugging, capped at 8 KB

class ProjectAnalysis(BaseModel):
    project_path: str
    analyzed_at: str
    sources: list[SourceAnalysis] = Field(default_factory=list)
    failures: list[SourceFailure] = Field(default_factory=list)
    candidates_by_concept: dict[str, list[str]] = Field(default_factory=dict)
        # concept_id → list of source_paths that produced candidates; pre-computed index
    eva_summary: list[str] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
```

### 7.4 Call shape per source

**Input to the LLM** (per-source call):
- System prompt: overall role + output contract + concept glossary (hand-tuned per tricky concept)
- User content blocks, in order:
  1. YAML: ALL 53 concepts from `schemas/concepts/report_variables.yaml` (id, type, group, description) — so the LLM sees the full target space
  2. For each artifact of this source (in deterministic order):
     - Text (markdown/CSV): inline as a text block
     - Image (PNG/JPG): attached as an image block
  3. An imperative footer: *"Return a single tool call `SourceAnalysis` with (insight, candidates)."*
- Anthropic `tools` with a strict JSON schema matching `{insight: SourceInsight, candidates: list[Candidate]}`.

**Output:** one tool_use block conforming to the schema. Parsed into `SourceAnalysis`.

### 7.5 Model selection

**Default:** `claude-sonnet-4-6` for **all** sources, both text and multimodal. Highest practical quality-cost in our workload class.

**Env-var upgrade paths (no code change):**
- `G3DT_AI_MODEL_GEOTECH=claude-opus-4-7` → route sources whose `SourceInsight.document_type` ∈ {`sondeig_annex`, `dpsh_field_sheet`, `laboratory_report`} to Opus on a *second* analysis pass. Disabled by default.
- `G3DT_AI_MODEL_VISION=gpt-4.1-mini` → route sources with 0 text artifacts (only PNG/JPG) through OpenAI. Disabled by default.

MVP path: Sonnet for everything. We turn the knobs only when we observe Sonnet misjudging on a concrete concept.

### 7.6 Error handling: systemic vs per-source

Errors split in two classes, handled very differently:

**Systemic errors** (fail-fast, project-wide):
- HTTP 401 (invalid API key), 402 / `insufficient_credits`, 403 (blocked account)
- `model_not_found` (bad env-var override)
- Missing `ANTHROPIC_API_KEY` in environment

When the first source call returns any of these, Stage 4 **aborts the entire project analysis** with one clear error in `ProjectAnalysis.failures` like:

```
{
  "error_type": "insufficient_credits",
  "message": "Anthropic API returned 402 insufficient_credits. All 96 sources skipped.
  Action: add credits, or set G3DT_AI_MODEL_VISION=gpt-4.1-mini for image-only sources.",
  "sources_skipped": 96
}
```

No point listing the same error per source — the wizard shows one banner, Eva acts once.

**Per-source errors** (isolated, continue with others):
- Schema validation (rare) → one automatic retry with trimmed prompt; if still fails, source recorded in `failures`, remaining sources continue.
- Transient API errors (429, 5xx, network timeout) → exponential backoff up to 3 attempts per source; if still fails, source recorded in `failures`, remaining sources continue.
- Oversized input (context window exceeded) → source recorded in `failures` with hint to trim the Stage 3 output (rare edge case).

**Circuit breaker:** even for per-source errors, if 3 consecutive non-systemic failures occur, abort the project analysis (likely a new systemic issue we haven't classified). Saves runaway cost when something is genuinely wrong.

**Top-level reporting:** `ProjectAnalysis.failures` surfaces everything. On a healthy run it's empty. On any systemic abort it has one entry with the action to take. On per-source failures it lists them for retry.

**Never silent fallback:** we do NOT auto-switch models on failure (e.g., Sonnet → Haiku). Quality would change without Eva knowing. The env-var upgrade paths (§7.5) are opt-in; degradation fallbacks are off.

### 7.7 Caching

Cache key per source = SHA256 of:
- The full per-source prompt (concept YAML + glossary + each artifact's bytes read from disk)
- Model id
- Schema version (bumped when we change `SourceInsight` / `Candidate` shape)

Cache lives at `{project}/validation/ai_pipeline/analysis/{source_stem}/_cache.json`. Hit → return cached `SourceAnalysis` instantly (0 cost). Miss → LLM call, persist. `refresh=true` forces re-analysis.

Per-source granularity means: if Eva edits one file and re-runs, only that source pays the LLM; the rest are free.

### 7.8 Context packed into the prompt

1. **Full concept schema** (`schemas/concepts/report_variables.yaml`): identity + type + group + short description. ~53 concepts × ~40 tokens = ~2.1 k tokens. Sent once per call.
2. **Eva's glossary** (hand-curated, new file `schemas/ai_pipeline/concept_glossary.yaml`): notes on ambiguous cases. Examples:
   - `num_floors`: *Planta baixa + 1 pis = 2 floors (CTE counting). Basement doesn't count unless it's a habitable ground floor. Distinct from 'building_height_m'.*
   - `Nb` vs `N20`: *Nb = dynamic penetration, Eva's primary correlation variable. N20 = SPT/DPSH blows per 20 cm. When Eva says "N = 45", she usually means Nb unless the source is a field sheet.*
   - `cota_referencia`: *Absolute elevation (m.s.n.m.) of the reference point — usually the plànol's top-of-slab. NOT depth from surface.*
- ~15 of the 53 concepts warrant an explicit glossary entry; the rest the YAML describes sufficiently.

### 7.9 Resum per Eva (`eva_summary`)

```
Hem analitzat 18 fonts i n'hem extret 247 candidats de valor:
• 6 fonts classificades com a plànols arquitectònics (2 versions d'A.01).
• 4 fonts són fitxes de camp (DPSH + sondeig).
• 3 fonts són emails amb adjunts del client i de l'arquitecte.
• 43 variables de l'informe tenen candidats; 10 no s'han pogut trobar en cap font.
• 2 fonts no s'han pogut analitzar — fes "Refresh" per tornar-ho a intentar.
```

Aquesta és la segona línia de transparència: *"això és el que hem entès del que has aportat"*.

### 7.10 Dependències

- **`anthropic`** (ja present) — API per Claude
- **`openai`** (opcional, només si `G3DT_AI_MODEL_VISION=gpt-4.1-mini`) — ja present
- Cap binari nou

### 7.11 Com s'utilitzarà

- **CLI:** `scripts/ai_pipeline_analysis.py --project {id} [--save] [--json] [--source {substring}]`
- **API:** `GET /api/ai-pipeline/analysis/{project}?refresh=true`
- **Wizard:** secció "Stage 4: Anàlisi" sota Stage 3 amb SourceInsights col·lapsables + candidats per concepte + banner de fallides + cost estimat
- **Python:** `from automation.ai_pipeline.analysis import analyze_project`

### 7.12 Sortida canònica

Manifest: `{projecte}/validation/ai_analysis.json`
Cache + artefactes per font: `{projecte}/validation/ai_pipeline/analysis/{source_stem}/*`

### 7.13 V1.1 candidats (fora de MVP)

- Routing Opus/4.1-mini per concept-class o source-type (avui només per env var).
- Second-pass self-consistency: re-analitzar els concepts on Sonnet ha donat `confidence < 0.5` amb Opus, comparar, marcar disagreement.
- Token-usage caps per project amb stop-and-report si es sobrepassen.
- Tool calls de visió auxiliars (zoom-in en parts específiques d'un plànol).

---

## 8. Arquitectura tècnica

```
automation/ai_pipeline/
├── __init__.py           # buit (import directe des de submòduls)
├── inventory.py          # Fase 1 (implementada)
├── typology.py           # Fase 2 (implementada)
├── conversion.py         # Fase 3 (implementada)
└── analysis.py           # Fase 4 (pendent)

scripts/
├── ai_pipeline_inventory.py     # CLI Fase 1
├── ai_pipeline_typology.py      # CLI Fase 2
├── ai_pipeline_conversion.py    # CLI Fase 3
└── ai_pipeline_analysis.py      # CLI Fase 4 (pendent)

schemas/ai_pipeline/
└── concept_glossary.yaml        # hand-tuned notes per ambiguous concept (pendent)

web/
└── api.py                 # endpoints /api/ai-pipeline/{inventory,typology,conversion,analysis,artifact}/{project}

templates/validation/
└── review.html            # pestanya "AI Pipeline" (Stage 1 + 2 + 3 + preview modals; Stage 4 pendent)

tests/
├── test_ai_pipeline_inventory.py   # 14 tests
├── test_ai_pipeline_typology.py    # 30 tests
├── test_ai_pipeline_conversion.py  # 21 tests
└── test_ai_pipeline_analysis.py    # (pendent)
```

Dependències externes:
- **Ja presents al projecte:** `pydantic`, `extract_msg`, `PyMuPDF`, `openpyxl`, `python-docx`, `anthropic`, `openai`
- **Afegides per Fase 3:** `pymupdf4llm`, `pypandoc` (wrapper sobre `pandoc` binari), `LibreOffice` (binari de sistema, usat per `.doc` legacy)
- **Afegides per Fase 4:** cap dep nova — s'usa `anthropic` (ja present). `openai` només s'usa si `G3DT_AI_MODEL_VISION=gpt-4.1-mini` està activat.

---

## 9. Roadmap de fases 5–7

Cada fase es dissenyarà abans d'implementar. No es comprometen detalls aquí; aquest llistat és la intenció.

### Fase 5 — Authority ranking (font autoritativa per concepte)
Per cada variable de l'informe (dels 53 conceptes), produir una llista **ordenada** de candidats (del més fiable al menys) segons:
- Els `SourceInsight` de Fase 4 (tipus de document, autor, data, enllaços).
- Regles d'autoritat d'Eva codificades (p.ex. *"per plot dimensions, el plànol arquitectònic guanya sempre sobre l'email"*).
- Pistes de `authority_hints` que l'LLM hagi emès.

**No** resol a un valor final; només ordena. Fase 6 agafa el top-1, mostra el top-N com a alternatives.

### Fase 6 — Proposta + validació per Eva
Per cada concepte, pren el candidat top-1 de Fase 5 com a valor proposat. El wizard mostra:
- Valor proposat
- Quote verbatim de l'origen
- Alternatives ordenades per Fase 5
- Botons: *confirmar* / *editar* / *usar alternativa N* / *marcar no trobat*

Eva revisa, edita, omple buits. La seva decisió s'afegeix als artefactes persistits (p.ex. `user_data.json`). Concepts sense cap candidat passen directament a "pendent d'omplir per Eva".

### Fase 7 — Generació de l'informe
Produir el .docx final. Opcions: reutilitzar `ReportGenerator` amb les noves dades, o construir una cadena de raonament que compongui les seccions una a una.

---

## 10. Relació amb el pipeline existent

| Aspecte                 | Pipeline existent                          | AI Pipeline                                 |
|-------------------------|--------------------------------------------|---------------------------------------------|
| Filosofia               | Regles + regex + LLM com a fallback        | LLM com a primari + regles com a fallback   |
| Punt d'entrada          | `auto_extractor.auto_extract()`            | `automation/ai_pipeline/` stage-by-stage    |
| Branca                  | `feature/action-2-deterministic`           | `experiment/ai-pipeline`                    |
| Wizard                  | Pestanyes SmartScan, Wizard, Dev, Pipeline | Pestanya AI Pipeline (nova)                 |
| Artefactes              | `file_mapping.json`, `concept_map.json`, etc. | `validation/ai_inventory.json`, `ai_typology.json`, `ai_conversion.json`, `ai_analysis.json` i futurs |
| Estat                   | Producció                                  | Experimental — Fases 1, 2 i 3 funcionals; Fase 4 dissenyada |

**Decisió d'adopció:** quan l'AI Pipeline complet demostri millor qualitat i/o menor intervenció manual que el pipeline existent sobre els 7 projectes de referència, es considerarà fusió a `main`. No abans.

---

## 11. Com estendre

Per afegir una nova fase:

1. **Dissenyar:** escriure la secció corresponent a aquest document.
2. **Identificar reutilització:** passar un agent Explore per mapejar què ja existeix.
3. **Crear mòdul:** `automation/ai_pipeline/stageN.py` amb funció pública + model pydantic de sortida.
4. **CLI:** `scripts/ai_pipeline_stageN.py` amb `--project` i `--save`.
5. **Endpoint:** `GET /api/ai-pipeline/stageN/{project}?refresh=true`.
6. **Wizard:** ampliar la pestanya "AI Pipeline" (no afegir-ne una per cada fase).
7. **Tests:** unitaris amb `tmp_path`.
8. **Document:** actualitzar Fase N en aquest doc.

---

## 12. Referències

- `automation/fileminer/miners/msg_miner.py` — extracció adjunts .msg
- `automation/concept_scout/scanner.py` — walk + skip rules
- `automation/concept_scout/models.py` — `FileEntry` model
- `docs/ARQUITECTURA-CONCEPT-FORMAT-SCHEMAS.md` — arquitectura concept/format actual
- `CLAUDE.md` (arrel g3dt) — model d'operació general del projecte
