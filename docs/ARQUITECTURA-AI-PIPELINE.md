# Arquitectura: AI Pipeline

**Data:** 2026-04-24
**Branca:** `experiment/ai-pipeline`
**Autor:** Josep Portell + Claude Code
**Estat:** Fase 1 implementada. Fases 2–7 pendents de disseny i implementació.

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
| 2 | **Classificació**         | Determinar què és cada fitxer (plànol? PENETROS? SONDEIG? email? factura?). |
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

## 5. Arquitectura tècnica

```
automation/ai_pipeline/
├── __init__.py           # exporta API pública
└── inventory.py          # Fase 1

scripts/
└── ai_pipeline_inventory.py    # CLI per Fase 1

web/
└── api.py                 # endpoint GET /api/ai-pipeline/inventory/{project}

templates/validation/
└── review.html            # pestanya "AI Pipeline"

tests/
└── test_ai_pipeline_inventory.py   # 14 tests
```

Dependències externes (ja presents al projecte):
- `pydantic` (models de dades)
- `extract_msg` (lectura .msg)
- `PyMuPDF` (classificació PDF vectorial vs escanejat, via concept_scout)

---

## 6. Roadmap de fases 2–7

Cada fase es dissenyarà abans d'implementar. No es comprometen detalls aquí; aquest llistat és la intenció.

### Fase 2 — Classificació
Donat l'inventari de la Fase 1, decidir què és cada fitxer: plànol arquitectònic, fitxa DPSH escrita a mà, Excel transcrit, email de pressupost, factura, certificat, etc. Probable ús: LLM amb mostreig del contingut (primera pàgina de PDF, primeres cel·les d'Excel) + vision per fitxers escanejats. Candidat a reutilitzar `SmartScan` si la seva sortida ja es pot interpretar com una classificació.

### Fase 3 — Conversió
Normalitzar cada fitxer a un format que l'LLM pot consumir eficientment:
- PDFs vectorials → markdown (via pdfplumber o similar)
- PDFs escanejats → imatges paginades
- Excel → CSV (amb metadades de full)
- .msg → markdown (cos + metadades)
- .docx → markdown

### Fase 4 — Anàlisi
Per cada fitxer convertit, extreure senyals: valors numèrics, noms, dates, adreces, unitats geotècniques, capes de sòl, etc. Diferent de la Fase 2 (classificació): aquí es llegeix el contingut, no només la forma.

### Fase 5 — Source of truth
Resoldre conflictes entre senyals competidors. Exemple: l'adreça pot aparèixer al plànol, al email del client, i a l'Excel — quina és la bona? Aquí es decideix, amb regles de prioritat i/o raonament LLM.

### Fase 6 — Assignació a variables
Mapejar els valors resolts a les ~53 variables de `schemas/concepts/report_variables.yaml`. Marcar les que no s'han pogut omplir — aquestes passen al wizard perquè Eva les aprovi, editi, o ompli manualment.

### Fase 7 — Generació de l'informe
Produir el .docx final. Opcions: reutilitzar `ReportGenerator` amb les noves dades, o construir una cadena de raonament que compongui les seccions una a una.

---

## 7. Relació amb el pipeline existent

| Aspecte                 | Pipeline existent                          | AI Pipeline                                 |
|-------------------------|--------------------------------------------|---------------------------------------------|
| Filosofia               | Regles + regex + LLM com a fallback        | LLM com a primari + regles com a fallback   |
| Punt d'entrada          | `auto_extractor.auto_extract()`            | `automation/ai_pipeline/` stage-by-stage    |
| Branca                  | `feature/action-2-deterministic`           | `experiment/ai-pipeline`                    |
| Wizard                  | Pestanyes SmartScan, Wizard, Dev, Pipeline | Pestanya AI Pipeline (nova)                 |
| Artefactes              | `file_mapping.json`, `concept_map.json`, etc. | `validation/ai_inventory.json` i futurs     |
| Estat                   | Producció                                  | Experimental — Fase 1 funcional             |

**Decisió d'adopció:** quan l'AI Pipeline complet demostri millor qualitat i/o menor intervenció manual que el pipeline existent sobre els 7 projectes de referència, es considerarà fusió a `main`. No abans.

---

## 8. Com estendre

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

## 9. Referències

- `automation/fileminer/miners/msg_miner.py` — extracció adjunts .msg
- `automation/concept_scout/scanner.py` — walk + skip rules
- `automation/concept_scout/models.py` — `FileEntry` model
- `docs/ARQUITECTURA-CONCEPT-FORMAT-SCHEMAS.md` — arquitectura concept/format actual
- `CLAUDE.md` (arrel g3dt) — model d'operació general del projecte
