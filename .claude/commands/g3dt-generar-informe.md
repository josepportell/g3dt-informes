# /g3dt-generar-informe

Genera un informe geotècnic complet: extracció de dades + wizard interactiu + generació de .docx.

<command-name>g3dt-generar-informe</command-name>

> El path del projecte depèn de `G3DT_PROJECTS_DIR` (default: `reference-material/`).

## Arguments

- `project_path` (required): Path a la carpeta del projecte (ex: `reference-material/4001612-bell-lloc` o `/mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC`)

## Exemples

```
/g3dt-generar-informe reference-material/4001612-bell-lloc
```

## Instruccions

Quan l'usuari invoca aquest skill:

### Fase 0: Descobriment de fitxers

Escaneja la carpeta del projecte, classifica cada fitxer pel seu rol, i genera un `file_mapping.json` que tot el pipeline llegeix.

**1. Comprovar si ja existeix file_mapping.json:**

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -c "
from automation.file_scanner import FileScanner
s = FileScanner('{project_path}')
existing = s.load()
if existing:
    print('file_mapping.json existent trobat')
    print(s.summary(existing))
else:
    print('Cap file_mapping.json trobat')
"
```

**2. Si ja existeix:** Re-escanejar per detectar canvis i mostrar diferències. Si no hi ha canvis, mostrar "Mapeig actualitzat, sense canvis" i continuar a Fase 1.

**3. Si NO existeix o hi ha canvis:** Executar escaneig complet:

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -c "
from automation.file_scanner import FileScanner
s = FileScanner('{project_path}')
m = s.scan()
print(s.summary(m))
"
```

**4. Si `needs_confirmation` és True** (hi ha fitxers sense assignar O rols obligatoris buits):

   **4a. Resolució semàntica (Claude llegeix fitxers no assignats):**
   - Per a cada fitxer `unassigned` que sigui un PDF, llegeix visualment la primera pàgina amb el Read tool
   - Determina el rol pel contingut visual:
     - Gràfiques de penetració amb valors N20 → `dpsh_field_sheet`
     - Columnes litològiques / capes de sòl → `sondeig_field_sheet`
     - Plànol amb caixetí d'arquitecte → `architect_plan`
     - Mapa topogràfic amb ubicació → `situation_plan`
     - Taules de resultats de laboratori → `lab_results_pdf`
     - Secció transversal del terreny → `correlation_section`
   - Si es detecta un rol, actualitza el mapping:
   ```bash
   cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -c "
   from automation.file_scanner import FileScanner, FileRole
   s = FileScanner('{project_path}')
   m = s.load() or s.scan()
   m.roles['NOM_DEL_ROL'] = FileRole(path='FITXER.pdf', confidence='high', detection='semantic_claude')
   if 'FITXER.pdf' in m.unassigned:
       m.unassigned.remove('FITXER.pdf')
   s.save(m)
   "
   ```

   **4b. Si múltiples candidats pel mateix rol** → preguntar a l'usuari amb AskUserQuestion

   **4c. Mostrar mapeig final** → confirmar amb AskUserQuestion ("Confirmeu el mapeig de fitxers?")

**5. Guardar el mapeig:**

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -c "
from automation.file_scanner import FileScanner
s = FileScanner('{project_path}')
m = s.scan()
path = s.save(m)
print(f'Guardat: {path}')
"
```

**Nota:** Si l'usuari confirma el mapeig, actualitzar `confirmed_by_user: true` al JSON:

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -c "
import json
from pathlib import Path
p = Path('{project_path}') / 'file_mapping.json'
data = json.loads(p.read_text())
data['_metadata']['confirmed_by_user'] = True
p.write_text(json.dumps(data, indent=2, ensure_ascii=False))
print('Confirmat per usuari')
"
```

Mostrar resum:

```
============================================================
Fase 0: Descobriment de fitxers
============================================================
  [output del summary()]
============================================================
```

### Fase 1: Extracció de dades (automàtica)

Busca els fitxers font al directori `{project_path}` i executa les extraccions corresponents. Cada extracció regenera el JSON per garantir dades fresques.

**1. Plànol** — Llegeix `file_mapping.json` → `architect_plan`. Fallback: busca `A.*.pdf` al directori. Si n'hi ha més d'un, usa `A.01.pdf` per defecte:
   - Si existeix: invoca el skill `/g3dt-extreure-planol {project_path}/{fitxer_trobat}`
   - Genera: `{project_path}/validation/planol_extracted.json`
   - Si no existeix: saltar (mostrar avís)

**2. Sondeig** — Llegeix `file_mapping.json` → `sondeig_field_sheet`. Fallback: busca `SONDEIG.pdf` (o `SONDEIG*.pdf`):
   - Si existeix: invoca el skill `/g3dt-validar-sondeig {project_path}/SONDEIG.pdf`
   - Genera: `{project_path}/validation/sondeig_extracted.json`
   - Si no existeix: saltar (mostrar avís)

**3. DPSH (Penetròmetres)** — Llegeix `file_mapping.json` → `dpsh_field_sheet`. Fallback: busca `PENETROS.pdf` (o `PENETROS*.pdf`):
   - Si existeix: invoca el skill `/g3dt-validar-penetros {project_path}/PENETROS.pdf`
   - Genera: `{project_path}/validation/dpsh_extracted.json`
   - Si no existeix: saltar (mostrar avís)

**4. Adjacents (visor Cadastre)** — S'executa si `user_data.json` existeix i conté `referencia_catastral` o `utm_x`/`utm_y`. Si no, saltar (mostrar avís):
   - Invoca el skill `/g3dt-adjacents-visor {project_path}`
   - Genera: `{project_path}/validation/adjacents_visor.json`
   - Nota: Usa Playwright (navegador), pot trigar 30-60s

Després de les extraccions, mostra un resum:

```
============================================================
Fase 1: Extracció de dades
============================================================
  Plànol (A.01.pdf):     [EXECUTAT / SALTAT - fitxer no trobat / ERROR - descripció]
  Sondeig (SONDEIG.pdf): [EXECUTAT / SALTAT - fitxer no trobat / ERROR - descripció]
  DPSH (PENETROS.pdf):   [EXECUTAT / SALTAT - fitxer no trobat / ERROR - descripció]
  Adjacents (visor):     [EXECUTAT / SALTAT - prerequisits no trobats / ERROR - descripció]
============================================================
```

Si una extracció falla, mostra l'error però continua amb les següents. Les extraccions són independents.

### Fase 1b: Classificació de fotografies

Classifica automàticament les fotos de camp perquè el template les insereixi correctament.

**1. Escanejar** — Executa el classificador per veure l'estat actual:

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -c "
from automation.photo_classifier import PhotoClassifier
c = PhotoClassifier('{project_path}')
print(c.summary())
"
```

**2. Si `needs_classification` és True** (hi ha fotos sense classificar I categories buides):

Per a cada foto no classificada, llegeix el fitxer d'imatge amb el Read tool (Claude pot veure imatges). Classifica cada foto en una d'aquestes categories:

| Categoria | Slug | Què buscar a la foto |
|-----------|------|----------------------|
| `site` | `vista_general` | Vista general del solar, parcel·la buida, terreny |
| `dpsh` | `maquina_dpsh` | Màquina de penetròmetre DPSH (aparell mecànic amb barres al terra) |
| `sondeig` | `maquina_sondeig` | Màquina de sondeig a rotació (perforadora gran, camió-grua) |
| `materials` | `detall_materials` | Caixes de testimoni, mostres de sòl, detall de materials extrets |
| `skip` | — | Documents de camp, etiquetes, fotos borroses, duplicats |

**Criteris de classificació:**
- Si la foto mostra una màquina amb barres clavant-se al terra → `dpsh`
- Si la foto mostra una perforadora gran o camió amb torre → `sondeig`
- Si la foto mostra caixes amb columnes de sòl o mostres → `materials`
- Si la foto mostra el terreny/solar sense maquinària prominent → `site`
- Si la foto és un document, etiqueta o closeup d'una mostra individual → `skip`
- Si no estàs segur, pregunta a l'usuari amb AskUserQuestion mostrant la imatge

**3. Aplicar classificació** — Després de classificar, aplica els resultats:

```python
from automation.photo_classifier import PhotoClassifier
c = PhotoClassifier('{project_path}')
c.apply_classification({
    '/path/absolut/foto1.jpg': 'dpsh',
    '/path/absolut/foto2.jpg': 'sondeig',
    '/path/absolut/foto3.jpg': 'site',
    '/path/absolut/foto4.jpg': 'materials',
    # No incloure les 'skip'
})
```

**4. Mostrar resum** dels reanomenaments:

```
============================================================
Fase 1b: Classificació de fotografies
============================================================
  vista_general: 2 foto(s) ✓
  maquina_dpsh:  1 foto    ✓
  maquina_sondeig: 1 foto  ✓
  detall_materials: 1 foto ✓
  Saltades: 3 fotos (documents, duplicats)
============================================================
```

**Nota sobre re-execucions:** `apply_classification()` copia les fotos (no les mou), per tant els originals romanen. En re-execucions, `needs_classification` retornarà False perquè les categories ja estan cobertes -- les fotos originals apareixeran al `summary()` com "sense classificar" però això és esperat.

**5. Si `needs_classification` és False** (totes les categories ja estan cobertes o no hi ha FOTOGRAFIES/):
   - Mostra l'estat actual i continua directament a la Fase 2
   - Si no existeix `FOTOGRAFIES/`, mostra avís: "Carpeta FOTOGRAFIES/ no trobada. Les imatges de camp no s'inclouran a l'informe."

### Fase 2: Wizard interactiu

1. **Executa el wizard interactiu** al terminal de l'usuari:

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -m automation.wizard {project_path}
```

**IMPORTANT**: Usa `.venv/bin/python` (no `python3`) perquè el venv té les dependències instal·lades (shapely, docxtpl, xlrd).

2. **El wizard fa tot sol:**
   - Carrega prefills dels JSONs generats a la Fase 1: `planol_extracted.json`, `adjacents_visor.json`, `sondeig_extracted.json`, i `user_data.json` existent. Nota: `dpsh_extracted.json` s'usa pel `report_generator` directament, no pel wizard.
   - Mostra 12 camps en 3 grups (Dades del Projecte, Adjacents, Paràmetres)
   - L'usuari confirma amb Enter o corregeix escrivint
   - Guarda `user_data.json` al directori del projecte
   - Pregunta si generar l'informe → si diu sí, llança el `report_generator`
   - Genera el `.docx` al directori del projecte

### Fase 3: Post-generació

Després de l'execució, mostra:
   - Resum dels fitxers generats (JSONs d'extracció + user_data.json + informe .docx)
   - Avisos si hi ha hagut errors en alguna fase
   - Recordatori de revisar valors amb baixa confiança: obrir `templates/validation/review.html` al navegador i carregar els JSONs generats des de `{project_path}/validation/`

## Nota

El wizard (Fase 2) és interactiu — necessita input de l'usuari al terminal. No es pot executar amb input simulat en producció.
