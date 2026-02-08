# Disseny: Fase 0 — Descobriment i Mapeig de Fitxers

## Problema

El pipeline actual assumeix noms de fitxer hardcoded (`A.01.pdf`, `PENETROS.pdf`, `SONDEIG.pdf`, `tall.pdf`). Si Eva rep fitxers amb noms diferents, el sistema no els troba i genera placeholders silenciosament. No hi ha verificació humana de quins fitxers s'estan usant.

## Solució

Nova Fase 0 al principi del `/g3dt-generar-informe` que:
1. Escaneja tots els fitxers de la carpeta del projecte
2. Assigna un **rol** a cada fitxer (o el marca com "no necessari")
3. Presenta el mapeig a l'usuari per validar
4. Guarda el mapeig confirmat a `file_mapping.json`
5. Tot el pipeline posterior llegeix d'aquest JSON en lloc d'endevinar noms

## Rols de fitxers

Fitxers que el report necessita:

| Rol | Descripció | Com s'usa | Patterns típics |
|-----|-----------|-----------|-----------------|
| `architect_plan` | Plànol de l'arquitecte | Extracció dades + imatge renderitzada | `A.01*.pdf`, `A.*.pdf`, `planol*.pdf` |
| `dpsh_field_sheet` | Full de camp DPSH (escrit a mà) | Extracció visual N20 | `PENETROS*.pdf`, `DPSH*.pdf` |
| `dpsh_excel` | Transcripció Excel DPSH | Validació creuada amb PDF | `*DPSH*.xls`, `*dpsh*.xlsx` |
| `sondeig_field_sheet` | Full de camp sondeig (escrit a mà) | Extracció capes sòl + SPT | `SONDEIG*.pdf` |
| `correlation_section` | Tall de correlació (dibuix) | Imatge renderitzada | `tall*.pdf`, `*correlaci*.pdf` |
| `photos_dir` | Carpeta de fotografies | Fotos de camp per l'informe | `FOTOGRAFIES/` |
| `budget` | Pressupost | Ref. cadastral, info client | `*PRESSUPOST*.pdf`, `*pressupost*.pdf` |
| `lab_order` | Comanda de laboratori | Assaigs sol·licitats | `*comanda*laboratori*.xls` |
| `situation_plan` | Plànol de situació | Context geogràfic (referència) | `*situaci*.pdf`, `pl.*situaci*.pdf` |

Fitxers ignorats (no usats pel report):

| Categoria | Exemples | Per què s'ignoren |
|-----------|----------|-------------------|
| `cover_page` | `*PORTADA*.doc` | Eva fa la portada manualment |
| `freehand_source` | `*.FH11` | Fitxers font FreeHand, no es poden processar |
| `derived_pdf` | `PDF/`, `PDF V0/` | Exports generats d'altres fonts |
| `acceptance` | `ACCEPTACIO/` | Documents contractuals, no tècnics |
| `email` | `*.msg` | Correspondència |
| `temp_files` | `~$*`, `Thumbs.db` | Temporals del sistema |
| `previous_versions` | `*_informe*.doc`, `*_DETALLAT*.doc` | Versions anteriors de l'informe |
| `our_outputs` | `*_generated.docx`, `*_AUDIT*.docx`, `validation/`, `user_data.json` | Generats per nosaltres |

## Estratègia de detecció

### Nivell 1: Per nom/extensió (alta confiança, instantani)

```
Fitxer                              → Rol assignat          Confiança
─────────────────────────────────────────────────────────────────────
A.01.pdf                            → architect_plan        ALTA
PENETROS.pdf                        → dpsh_field_sheet      ALTA
SONDEIG.pdf                         → sondeig_field_sheet   ALTA
ANNEXES/4001612_DPSH.xls            → dpsh_excel            ALTA
tall.pdf                            → correlation_section   ALTA
FOTOGRAFIES/                        → photos_dir            ALTA
comanda laboratori_4001612.xls      → lab_order             ALTA
*PRESSUPOST*.pdf                    → budget                ALTA
*PORTADA*.doc                       → cover_page (ignorat)  ALTA
*.FH11                              → freehand (ignorat)    ALTA
~$*, Thumbs.db                      → temp (ignorat)        ALTA
PDF/, PDF V0/                       → derived (ignorat)     ALTA
ACCEPTACIO/                         → acceptance (ignorat)  ALTA
```

### Nivell 2: Per inspecció visual (només si hi ha fitxers sense assignar + rols buits)

Si un PDF no coincideix amb cap pattern I falten rols al mapeig:
- Claude llegeix la primera pàgina del PDF
- Classifica: és un plànol? un full de camp? un tall?
- Assigna el rol o el marca com "no necessari"

Això cobreix el cas d'Eva rebent fitxers amb noms no estàndard.

### Nivell 3: Preguntar a l'usuari (només per ambigüitats)

Si hi ha múltiples candidats per un rol:
- "He trobat 2 plànols: `A.01.pdf` i `A.01 amb punts.pdf`. Quin és el definitiu?"

## Format de `file_mapping.json`

```json
{
  "roles": {
    "architect_plan": {
      "path": "A.01.pdf",
      "confidence": "high",
      "detection": "filename_pattern"
    },
    "dpsh_field_sheet": {
      "path": "PENETROS.pdf",
      "confidence": "high",
      "detection": "filename_pattern"
    },
    "dpsh_excel": {
      "path": "ANNEXES/4001612_DPSH.xls",
      "confidence": "high",
      "detection": "filename_pattern"
    },
    "sondeig_field_sheet": {
      "path": "SONDEIG.pdf",
      "confidence": "high",
      "detection": "filename_pattern"
    },
    "correlation_section": {
      "path": "tall.pdf",
      "confidence": "high",
      "detection": "filename_pattern"
    },
    "photos_dir": {
      "path": "FOTOGRAFIES",
      "confidence": "high",
      "detection": "directory_name"
    },
    "budget": {
      "path": "25.0647/PRESSUPOST GEOTEC.BELL-LLOC.pdf",
      "confidence": "medium",
      "detection": "filename_pattern"
    }
  },
  "ignored": [
    {"path": "4001612_PORTADA_25.doc", "reason": "cover_page"},
    {"path": "ANNEXES/4001612_sondeig.FH11", "reason": "freehand_source"},
    {"path": "PDF/", "reason": "derived_pdf"},
    {"path": "ACCEPTACIO/", "reason": "acceptance"}
  ],
  "unassigned": [],
  "_metadata": {
    "scanned_at": "2026-02-07T10:30:00",
    "total_files": 78,
    "confirmed_by_user": true,
    "project_path": "reference-material/4001612-bell-lloc"
  }
}
```

## Presentació a l'usuari

Fase 0 mostra el mapeig amb format clar i demana confirmació:

```
============================================================
Fase 0: Mapeig de fitxers del projecte
============================================================

FITXERS IDENTIFICATS PER L'INFORME:
  ✓ Plànol arquitecte:     A.01.pdf
  ✓ Full de camp DPSH:     PENETROS.pdf
  ✓ Excel DPSH:            ANNEXES/4001612_DPSH.xls
  ✓ Full de camp sondeig:  SONDEIG.pdf
  ✓ Tall de correlació:    tall.pdf
  ✓ Fotografies:           FOTOGRAFIES/ (10 fotos)
  ✓ Pressupost:            25.0647/PRESSUPOST GEOTEC.BELL-LLOC.pdf

NO TROBATS (l'informe usarà placeholders):
  (cap — tots els rols coberts)

FITXERS IGNORATS: 15 (portada, FreeHand, PDFs exportats, emails)

============================================================
```

Llavors pregunta amb AskUserQuestion:

**Pregunta 1** (si tot és clar):
"El mapeig de fitxers és correcte?"
- "Sí, continuar" (Recommended)
- "No, necessito corregir alguna cosa"

**Pregunta 2** (si hi ha fitxers sense assignar):
"He trobat fitxers que no sé classificar. Quin és el seu rol?"
- [opcions per a cada fitxer sense assignar]

**Pregunta 3** (si falten rols):
"Falta el [tall de correlació]. Algun d'aquests fitxers podria ser-ho?"
- [llista de PDFs no assignats]
- "No existeix encara"

## Flux complet revisat

```
/g3dt-generar-informe {project_path}
│
├── Fase 0: Descobriment de fitxers
│   ├── Escanejar carpeta
│   ├── Assignar rols (patterns → alta confiança)
│   ├── Inspecció visual (si cal, per PDFs ambigus)
│   ├── Presentar mapeig a l'usuari
│   ├── Usuari confirma o corregeix
│   └── Guardar file_mapping.json
│
├── Fase 1: Extracció de dades (llegeix file_mapping.json)
│   ├── Plànol → planol_extracted.json
│   ├── Sondeig → sondeig_extracted.json
│   ├── DPSH → dpsh_extracted.json
│   └── Adjacents → adjacents_visor.json
│
├── Fase 1b: Classificació de fotografies
│   ├── Escanejar FOTOGRAFIES/ (path de file_mapping)
│   ├── Classificar fotos sense slug
│   └── Reanomenar amb convenció de slugs
│
├── Fase 2: Wizard interactiu
│   ├── Pre-fill des dels JSONs d'extracció
│   ├── Usuari confirma/corregeix camps manuals
│   └── Guardar user_data.json
│
└── Fase 3: Generació de l'informe
    ├── report_generator.py (usa user_data.json + extraction JSONs)
    ├── image_manager.py (usa file_mapping.json per trobar PDFs)
    └── Generar .docx final
```

## Mòduls a crear/modificar

| Fitxer | Acció | Línies estimades |
|--------|-------|-----------------|
| `automation/file_scanner.py` | **NOU** — Escaneig + classificació + file_mapping.json | ~200 |
| `.claude/commands/g3dt-generar-informe.md` | Afegir Fase 0 al skill | ~50 |
| `automation/image_manager.py` | Llegir `architect_plan` i `correlation_section` de file_mapping | ~15 |

### `file_scanner.py` — Estructura

```python
@dataclass
class FileRole:
    path: str                    # Relatiu al project_path
    confidence: str              # "high", "medium", "low"
    detection: str               # "filename_pattern", "visual_inspection", "user_assigned"

@dataclass
class FileMapping:
    roles: dict[str, FileRole]   # role_name → FileRole
    ignored: list[dict]          # [{"path": "...", "reason": "..."}]
    unassigned: list[str]        # Fitxers que no sabem classificar

class FileScanner:
    def __init__(self, project_path):
        ...

    def scan(self) -> FileMapping:
        """Escaneja i classifica tots els fitxers."""
        ...

    def save_mapping(self, mapping: FileMapping):
        """Guarda file_mapping.json."""
        ...

    def load_mapping(self) -> FileMapping | None:
        """Carrega file_mapping.json existent."""
        ...

    def summary(self, mapping: FileMapping) -> str:
        """Resum llegible per mostrar a l'usuari."""
        ...
```

### Integració a `image_manager.py`

```python
def _find_pdf_from_mapping(self, role: str) -> Path | None:
    """Find PDF path from file_mapping.json, fallback to glob patterns."""
    mapping_path = self.project_path / 'file_mapping.json'
    if mapping_path.exists():
        import json
        mapping = json.loads(mapping_path.read_text())
        role_data = mapping.get('roles', {}).get(role)
        if role_data:
            pdf_path = self.project_path / role_data['path']
            if pdf_path.exists():
                return pdf_path
    return None  # Fallback to existing glob behavior
```

## Casos especials

### Projecte sense DPSH (només sondeig)
- `dpsh_field_sheet` i `dpsh_excel` no existeixen → rols buits
- L'informe adapta el contingut (ja ho fa amb `has_dpsh`)

### Múltiples sondeigs
- Futura extensió: `sondeig_field_sheet_1`, `sondeig_field_sheet_2`
- Per ara: un sol sondeig per projecte

### Fitxer afegit posteriorment
- Eva afegeix `tall.pdf` després de la primera generació
- Re-executar Fase 0 detecta el nou fitxer i actualitza el mapeig
- L'informe es regenera amb la imatge del tall

### Projecte amb estructura diferent
- Si Eva posa tot al root sense subcarpetes → funciona igualment
- La detecció és per nom, no per ubicació (excepte FOTOGRAFIES/)

## Riscos i mitigacions

| Risc | Probabilitat | Impacte | Mitigació |
|------|-------------|---------|-----------|
| Eva no confirma correctament | Baix | Mig | Mostrar resum clar, preguntar explícitament |
| Fitxer amb nom completament inesperat | Mig | Baix | Inspecció visual + "unassigned" category |
| Múltiples candidats per un rol | Baix | Mig | Preguntar a Eva, no assumir |
| pymupdf no pot renderitzar un PDF | Baix | Baix | Fallback a placeholder (comportament actual) |

## Beneficis

1. **Robustesa**: No depèn de noms de fitxer hardcoded
2. **Transparència**: L'usuari veu exactament què s'usa i què no
3. **Auditabilitat**: `file_mapping.json` documenta les fonts
4. **Adaptabilitat**: Nous formats/rols fàcils d'afegir
5. **Idempotència**: Re-executar Fase 0 actualitza sense perdre confirmacions
