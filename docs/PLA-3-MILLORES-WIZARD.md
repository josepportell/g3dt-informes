# Pla: 3 Millores al Wizard G3DT

Data: 2026-03-04

## Context

Preparant la demo per G3DT. Tres millores per fer que el wizard sigui més real i proper al flux de treball d'Eva:
1. Mostrar quins fitxers del projecte s'han analitzat
2. Moure la carpeta de projectes a Windows (`C:/claude/g3dt/`)
3. Mostrar la font real de cada camp (fitxer concret, no "user_data")

## 1. Llista de fitxers analitzats al wizard

**Problema:** Eva no sap quins fitxers ha trobat el sistema a la carpeta del projecte.

**Approach:** Afegir `_file_mapping` al prefills response i renderitzar-lo al banner d'instruccions (ja existent).

### Backend: `web/wizard_service.py` — `get_prefills()`

`auto_result` ja conté `file_mapping` (diccionari de rols). Afegir-lo al merged:

```python
merged['_file_mapping'] = {'value': auto_result.file_mapping, 'source': 'system'}
```

### Frontend: `templates/validation/review.html`

Afegir una secció "Fitxers detectats" al banner d'instruccions (`renderInstructions()`), sota els badges de visió:

- Llista cada rol del file_mapping amb el path del fitxer
- Icona verda si el fitxer existeix, gris si no
- Agrupar per tipus: Camp (DPSH, sondeig), Plànol, Lab, Altres
- Collapsable per defecte si hi ha >5 fitxers

## 2. Carpeta de projectes a Windows

**Problema:** `_REF_DIR` apunta a `reference-material/` dins Ubuntu. Per la demo i futura producció, ha de ser una carpeta Windows que Eva/G3DT controlin.

**Approach:** Variable d'entorn `G3DT_PROJECTS_DIR` amb fallback.

### `web/wizard_service.py` (línia 19)

```python
import os
_REF_DIR = Path(os.getenv('G3DT_PROJECTS_DIR', str(_PROJECT_ROOT / 'reference-material')))
```

Per la demo, Eva arrencaria amb:
```bash
export G3DT_PROJECTS_DIR="/mnt/c/claude/g3dt/projectes"
```

### Fitxers afectats

| Fitxer | Canvi |
|--------|-------|
| `web/wizard_service.py` | `_REF_DIR` → env var o nou default |
| `.claude/commands/*.md` | Actualitzar exemples de path en documentació (cosmètic) |
| `automation/auto_extractor.py` | Res — rep `project_path` com a argument |
| `automation/file_scanner.py` | Res — rep path com a argument |
| `automation/wizard.py` | Res — rep path com a argument |

Tot el pipeline rep `project_path` per paràmetre, no hardcodeja `reference-material/`. Només cal canviar `_REF_DIR`.

### Preparació

Copiar els 4 projectes de referència a la nova carpeta Windows:
```bash
mkdir -p /mnt/c/claude/g3dt/projectes
cp -r reference-material/* /mnt/c/claude/g3dt/projectes/
```

### Comanda del banner d'instruccions

El banner ara mostra `/g3dt-visio-projecte reference-material/{project}`. Cal canviar-lo perquè mostri el path real. El backend inclou el base path al prefills:

```python
merged['_projects_base'] = {'value': str(_REF_DIR), 'source': 'system'}
```

I el frontend construeix la comanda amb el path real.

## 3. Fonts específiques als badges dels camps

**Problema:** Molts camps mostren "auto" com a font. Eva vol saber d'on ve cada dada (quin fitxer o API concretament).

**Situació actual:** El backend JA envia fonts específiques! `auto_extractor.py` usa fonts com `"DPSH Excel"`, `"ICGC WMS 1:50k"`, `"LAB PDF"`, `"Cadastre API"`. El JS `setSourceBadge()` ja les mostra, truncant a 20 chars.

**Problema real:** El `setSourceBadge()` converteix `"user"` i `"user_data.json anterior"` a `"user_data"` (badge verd). Quan Eva guarda i recarrega, TOTS els camps passen a `"user_data"` perquè `wizard.py` els marca amb source `"user_data.json anterior"`.

**Approach:** Preservar la font original quan es guarda a `user_data.json`, i restaurar-la en recarregar.

### `automation/wizard.py` — `save_wizard_data()`

Quan es guarda `user_data.json`, afegir un camp `_sources` que mapeja cada camp a la seva font original:

```python
# A user_data.json:
{
    "architect_name": "Jordi Bosch",
    "site_municipality": "Bell-Lloc",
    "_sources": {
        "architect_name": "planol A.01.pdf",
        "site_municipality": "ICGC WMS 1:50k"
    }
}
```

### `automation/wizard.py` — `_load_existing_user_data()`

Quan carrega `user_data.json`, si existeix `_sources`, usar la font original en lloc de `"user_data.json anterior"`:

```python
for key, value in user_data.items():
    if key.startswith('_'): continue
    original_source = user_data.get('_sources', {}).get(key, 'user_data.json anterior')
    self.prefills[key] = {'value': value, 'source': original_source}
```

### `web/wizard_service.py` — `save_wizard()`

Passar les fonts actuals al `save_wizard_data()`:

```python
# Recollir fonts del prefill cache actual
current_sources = {}
if project_name in _prefill_cache:
    for k, v in _prefill_cache[project_name].items():
        if isinstance(v, dict) and 'source' in v:
            current_sources[k] = v['source']
```

### Frontend: `templates/validation/review.html`

El `setSourceBadge()` actual ja funciona bé per fonts específiques. Només cal:
- Canviar el label de `"user_data.json anterior"` per mostrar la font original (que ara vindrà del backend)
- Potser afegir tooltip amb la font completa si es trunca

## Fitxers a modificar (total)

| Fitxer | Canvi 1 (fitxers) | Canvi 2 (path) | Canvi 3 (fonts) |
|--------|-------------------|----------------|-----------------|
| `web/wizard_service.py` | `_file_mapping` al prefills | `_REF_DIR` env var + `_projects_base` | Passar fonts al save |
| `templates/validation/review.html` | Renderitzar fitxers al banner | Path dinàmic al command | - |
| `automation/wizard.py` | - | - | Guardar/restaurar `_sources` |

## Verificació

1. **Fitxers:** Seleccionar projecte → banner mostra llista de fitxers detectats (DPSH.xls, PENETROS.pdf, etc.)
2. **Path:** Amb `G3DT_PROJECTS_DIR=/mnt/c/claude/g3dt/projectes`, wizard llista projectes des de Windows
3. **Fonts:** Seleccionar Bell-Lloc → camp "Arquitecte" mostra "planol A.01.pdf" (no "auto"). Guardar → recarregar → segueix mostrant "planol A.01.pdf" (no "user_data")
