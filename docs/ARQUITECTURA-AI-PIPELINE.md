# Arquitectura: AI Pipeline

**Data:** 2026-04-24
**Branca:** `experiment/ai-pipeline`
**Autor:** Josep Portell + Claude Code
**Estat:** Fase 1 implementada. Fase 2 dissenyada (pendent d'implementació). Fases 3–7 pendents de disseny.

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
| 3 | **Conversió**             | Passar cada fitxer a un format que l'LLM pugui llegir (markdown, CSV, imatge). |
| 4 | **Anàlisi**               | Extreure informació de cada fitxer (LLM + OCR + vision).                    |
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

## 5. Fase 2: Tipologia (dissenyada)

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

## 6. Arquitectura tècnica

```
automation/ai_pipeline/
├── __init__.py           # exporta API pública
├── inventory.py          # Fase 1
└── typology.py           # Fase 2 (pendent)

scripts/
├── ai_pipeline_inventory.py    # CLI per Fase 1
└── ai_pipeline_typology.py     # CLI per Fase 2 (pendent)

web/
└── api.py                 # endpoints GET /api/ai-pipeline/{inventory,typology}/{project}

templates/validation/
└── review.html            # pestanya "AI Pipeline"

tests/
├── test_ai_pipeline_inventory.py   # 14 tests
└── test_ai_pipeline_typology.py    # (pendent)
```

Dependències externes (ja presents al projecte):
- `pydantic` (models de dades)
- `extract_msg` (lectura .msg)
- `PyMuPDF` (classificació PDF vectorial vs escanejat + extracció d'imatges)
- `openpyxl` (introspecció Excel + extracció d'imatges)
- `python-docx` (introspecció DOCX — a verificar)

---

## 7. Roadmap de fases 3–7

Cada fase es dissenyarà abans d'implementar. No es comprometen detalls aquí; aquest llistat és la intenció.

### Fase 3 — Conversió
Per cada `FileClass` amb `useful=True`, produir un artefacte LLM-ready segons el `conversion_strategy` proposat per Fase 2:
- `pdf_to_markdown` → pdfplumber/PyMuPDF → markdown per pàgina
- `pdf_to_markdown_plus_images` → markdown + fitxers d'imatge ja extrets per Fase 2
- `pdf_pages_to_images` → una imatge PNG per pàgina (per Fase 4 vision)
- `excel_per_sheet_to_csv` → un CSV per full (iterant `sheet_names`)
- `excel_per_sheet_to_csv_plus_images` → CSV + imatges (ja extretes)
- `docx_to_markdown_plus_media` → markdown + media extreta
- `msg_body_to_markdown` → cos del missatge amb metadades
- `image_passthrough`, `text_passthrough` → directament
- `skip` → nop

La Fase 3 consumeix `ai_typology.json` i produeix artefactes a `{projecte}/validation/ai_pipeline/converted/`.

### Fase 4 — Anàlisi
Per cada fitxer convertit, extreure senyals: valors numèrics, noms, dates, adreces, unitats geotècniques, capes de sòl, etc. Diferent de la Fase 2 (classificació): aquí es llegeix el contingut, no només la forma.

### Fase 5 — Source of truth
Resoldre conflictes entre senyals competidors. Exemple: l'adreça pot aparèixer al plànol, al email del client, i a l'Excel — quina és la bona? Aquí es decideix, amb regles de prioritat i/o raonament LLM.

### Fase 6 — Assignació a variables
Mapejar els valors resolts a les ~53 variables de `schemas/concepts/report_variables.yaml`. Marcar les que no s'han pogut omplir — aquestes passen al wizard perquè Eva les aprovi, editi, o ompli manualment.

### Fase 7 — Generació de l'informe
Produir el .docx final. Opcions: reutilitzar `ReportGenerator` amb les noves dades, o construir una cadena de raonament que compongui les seccions una a una.

---

## 8. Relació amb el pipeline existent

| Aspecte                 | Pipeline existent                          | AI Pipeline                                 |
|-------------------------|--------------------------------------------|---------------------------------------------|
| Filosofia               | Regles + regex + LLM com a fallback        | LLM com a primari + regles com a fallback   |
| Punt d'entrada          | `auto_extractor.auto_extract()`            | `automation/ai_pipeline/` stage-by-stage    |
| Branca                  | `feature/action-2-deterministic`           | `experiment/ai-pipeline`                    |
| Wizard                  | Pestanyes SmartScan, Wizard, Dev, Pipeline | Pestanya AI Pipeline (nova)                 |
| Artefactes              | `file_mapping.json`, `concept_map.json`, etc. | `validation/ai_inventory.json`, `ai_typology.json`, i futurs |
| Estat                   | Producció                                  | Experimental — Fase 1 funcional, Fase 2 dissenyada |

**Decisió d'adopció:** quan l'AI Pipeline complet demostri millor qualitat i/o menor intervenció manual que el pipeline existent sobre els 7 projectes de referència, es considerarà fusió a `main`. No abans.

---

## 9. Com estendre

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

## 10. Referències

- `automation/fileminer/miners/msg_miner.py` — extracció adjunts .msg
- `automation/concept_scout/scanner.py` — walk + skip rules
- `automation/concept_scout/models.py` — `FileEntry` model
- `docs/ARQUITECTURA-CONCEPT-FORMAT-SCHEMAS.md` — arquitectura concept/format actual
- `CLAUDE.md` (arrel g3dt) — model d'operació general del projecte
