# /g3dt-generar-informe

Genera un informe geotècnic complet: extracció de dades + wizard interactiu + generació de .docx.

<command-name>g3dt-generar-informe</command-name>

## Arguments

- `project_path` (required): Path a la carpeta del projecte (ex: `reference-material/4001612-bell-lloc`)

> project_path és relatiu al directori arrel del projecte G3DT: /home/josep/projects/claudecode-job/clients/g3dt/

## Exemples

```
/g3dt-generar-informe reference-material/4001612-bell-lloc
```

## Instruccions

Quan l'usuari invoca aquest skill:

### Fase 1: Extracció de dades (automàtica)

Busca els fitxers font al directori `{project_path}` i executa les extraccions corresponents. Cada extracció regenera el JSON per garantir dades fresques.

**1. Plànol** — Busca un fitxer `A.*.pdf` al directori. Si en troba un, usa'l. Si n'hi ha més d'un, usa `A.01.pdf` per defecte:
   - Si existeix: invoca el skill `/g3dt-extreure-planol {project_path}/{fitxer_trobat}`
   - Genera: `{project_path}/validation/planol_extracted.json`
   - Si no existeix: saltar (mostrar avís)

**2. Sondeig** — Busca `{project_path}/SONDEIG.pdf` (o `SONDEIG*.pdf`):
   - Si existeix: invoca el skill `/g3dt-validar-sondeig {project_path}/SONDEIG.pdf`
   - Genera: `{project_path}/validation/sondeig_extracted.json`
   - Si no existeix: saltar (mostrar avís)

**3. DPSH (Penetròmetres)** — Busca `{project_path}/PENETROS.pdf` (o `PENETROS*.pdf`):
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
