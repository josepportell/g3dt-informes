# /g3dt-extreure-planol

Extreu dades del plànol de l'arquitecte (A.01.pdf o similar) per a l'informe geotècnic.

<command-name>g3dt-extreure-planol</command-name>

> El path del projecte depèn de `G3DT_PROJECTS_DIR` (default: `reference-material/`).

## Arguments

- `pdf_path` (required): Path al fitxer del plànol (A.01.pdf, plànol situació, etc.) (ex: `reference-material/4001612-bell-lloc/A.01.pdf` o `/mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC/A.01.pdf`)

## Exemples

```
/g3dt-extreure-planol reference-material/4001612-bell-lloc/A.01.pdf
```

## Instruccions

Quan l'usuari invoca aquest skill:

1. **Llegeix el PDF visualment** amb el Read tool
2. **Extreu les dades** del projecte:
   - Nom del projecte / tipus d'edificació
   - Ubicació (carrer, número, municipi)
   - Promotor
   - Arquitecte
   - Dimensions de la parcel·la
   - Ocupació prevista de l'edifici
   - Número de plantes
   - Alçada màxima
   - Altres dimensions rellevants
3. **Genera JSON de validació** amb el format correcte
4. **Guarda el fitxer** a `{pdf_parent}/validation/planol_extracted.json`

## Format d'extracció del PDF

Quan llegeixis el plànol, busca:

### Caixetí / Cartutx (típicament a la cantonada inferior dreta)
- **Nom del projecte**: "Habitatge unifamiliar aïllat", "Nau industrial", etc.
- **Emplaçament**: Carrer, número, codi postal, població
- **Promotor**: Nom de l'empresa o particular
- **Arquitecte**: Nom i col·legiat
- **Escala**: 1:100, 1:200, etc.
- **Data**: Del projecte

### Plànol de situació / emplaçament
- **Superfície parcel·la**: En m²
- **Dimensions**: Longitud x Amplada
- **Ocupació edifici**: En m² o percentatge

### Secció / Alçat
- **Número de plantes**: PB+1, PB+2, Soterrani, etc.
- **Alçada màxima**: En metres

### Format de sortida JSON

```json
{
  "source_file": "A.01.pdf",
  "extraction_date": "2026-02-04T16:00:00",
  "extraction_method": "claude_vision",
  "overall_confidence": 0.95,
  "status": "pending_review",
  "architect_data": {
    "source_file": "A.01.pdf",
    "project_name": "Habitatge Unifamiliar Aïllat",
    "location": "C/ Mestre Ramon Ortiz, 25220 Bell-Lloc d'Urgell",
    "promotor": "Ramon Mitjana SL",
    "architect": "Jordi Bosch Novell",
    "dimensions": {
      "parcel_area_m2": {"pdf_value": 598.0, "confidence": 0.95},
      "building_footprint_m2": {"pdf_value": 296.88, "confidence": 0.90},
      "num_floors": {"pdf_value": "Pb+P1", "confidence": 1.0},
      "max_height_m": {"pdf_value": 8.38, "confidence": 0.85},
      "plot_length_m": {"pdf_value": 24.57, "confidence": 0.90},
      "plot_width_m": {"pdf_value": 24.72, "confidence": 0.90}
    }
  },
  "reviewer_notes": "",
  "approved_by": "",
  "approval_date": null
}
```

## Confiança d'extracció

Assigna nivells de confiança segons la claredat:
- **1.0**: Text imprès clar i inequívoc
- **0.9**: Llegible amb mínima incertesa
- **0.7-0.8**: Llegible però requeriria confirmació
- **0.5**: Difícil de llegir o interpretar
- **0.0**: No trobat - indica `null` i afegeix nota

## Nota Important

Els plànols d'arquitecte solen ser documents impresos/CAD, més clars que els fulls de camp escrits a mà.
Tot i així, algunes cotes poden ser petites o poc llegibles.

## Després de l'extracció

1. Mostra resum: dades del projecte extretes
2. Destaca camps no trobats o amb baixa confiança
3. Indica el path del fitxer JSON generat
4. Recorda a l'usuari que pot revisar amb `templates/validation/review.html` (pestanya Plànol)

## Exemple de sortida

```
============================================================
Extracció Plànol: A.01.pdf (Bell-Lloc)
============================================================
Projecte: Habitatge Unifamiliar Aïllat
Ubicació: C/ Mestre Ramon Ortiz, 25220 Bell-Lloc d'Urgell
Promotor: Ramon Mitjana SL
Arquitecte: Jordi Bosch Novell

Dimensions extretes:
  Superfície parcel·la: 598.00 m² (conf: 0.95)
  Ocupació edifici: 296.88 m² (conf: 0.90)
  Número de plantes: Pb+P1 (conf: 1.00)
  Alçada màxima: 8.38 m (conf: 0.85) ⚠️
  Longitud parcel·la: 24.57 m (conf: 0.90)
  Amplada parcel·la: 24.72 m (conf: 0.90)

⚠️ Valors amb baixa confiança que requereixen revisió:
  - Alçada màxima: 8.38 m (0.85) - cota petita al document

Validació guardada a: reference-material/4001612-bell-lloc/validation/planol_extracted.json

Per revisar: obre templates/validation/review.html i carrega el JSON (pestanya Plànol)
```
