# /g3dt-visio-projecte

Executa totes les extraccions visuals (planol, DPSH, sondeig) per a un projecte sencer amb una sola comanda.

<command-name>g3dt-visio-projecte</command-name>

## Arguments

> El path del projecte depèn de `G3DT_PROJECTS_DIR` (default: `reference-material/`).

`$ARGUMENTS` = path del projecte (requerit), opcionalment seguit de `--force`

Exemples:
```
/g3dt-visio-projecte reference-material/3001621 CASTELLAR DEL VALLES
/g3dt-visio-projecte /mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC
/g3dt-visio-projecte reference-material/4001612 BELL-LLOC --force
```

## Instruccions

Quan l'usuari invoca aquest skill, segueix EXACTAMENT aquests passos:

### Pas 1: Parsejar arguments

Dels `$ARGUMENTS`:
- El **path del projecte** és tot menys `--force` (si hi és)
- `--force` és opcional: si present, ignora cache i re-extreu tot

### Pas 2: Obtenir file_mapping.json

1. Llegeix `{project_path}/file_mapping.json` amb el Read tool
2. Si NO existeix:
   - Executa FileScanner per generar-lo:
     ```bash
     cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -c "
     from automation.file_scanner import FileScanner
     s = FileScanner('{project_path}')
     m = s.scan()
     s.save(m)
     print(s.summary(m))
     "
     ```
   - Després llegeix el `file_mapping.json` generat

### Pas 3: Identificar PDFs amb visió

Del `file_mapping.json`, busca rols amb `vision_type`:

| Rol al mapping | vision_type | PDF típic | JSON sortida |
|----------------|-------------|-----------|--------------|
| `architect_plan` | `planol` | A.01.pdf | `validation/planol_extracted.json` |
| `architect_plan_with_points` | `planol` | A.01 amb punts.pdf | `validation/planol_extracted.json` |
| `situation_plan` | `planol` | Pl. situacio.pdf | `validation/planol_extracted.json` |
| `dpsh_field_sheet` | `dpsh` | PENETROS.pdf | `validation/dpsh_extracted.json` |
| `sondeig_field_sheet` | `sondeig` | SONDEIG.pdf | `validation/sondeig_extracted.json` |

**Regles:**
- Si múltiples rols tenen el MATEIX `vision_type`, processa només el PRIMER trobat (ex: si hi ha `architect_plan` i `situation_plan`, ambdós `planol`, processa només `architect_plan`)
- Ignora rols sense `vision_type` (ex: `dpsh_excel`, `correlation_section`)

### Pas 4: Comprovar cache

Per a cada `vision_type` trobat:
- Si `{project_path}/validation/{vision_type}_extracted.json` existeix I `--force` NO s'ha passat → **SKIP** (mostra "cache hit")
- Si no existeix O `--force` s'ha passat → processa

Crea el directori `validation/` si no existeix:
```bash
mkdir -p "{project_path}/validation"
```

### Pas 5: Extreure dades visualment

Per a cada PDF que cal processar:

1. **Llegeix el PDF** amb el Read tool (lectura visual nativa de Claude Code)
2. **Aplica el prompt d'extracció** corresponent (veure secció Prompts)
3. **Genera el JSON** amb el format exacte (veure secció Formats JSON)
4. **Guarda** a `{project_path}/validation/{vision_type}_extracted.json`

**IMPORTANT:** Cada extracció és independent. Si una falla, continua amb les altres.

### Pas 5.5: Lectura intel·ligent de documents

Després de les extraccions visuals, llegeix documents de text del projecte per extreure metadades que Python regex i visió no han obtingut.

**Cache:** Si `{project_path}/validation/docs_extracted.json` existeix I `--force` NO s'ha passat → **SKIP** (mostra "cache hit").

**Passos:**

1. **Identificar fitxers llegibles** al directori del projecte:
   - `ACCEPTACIO/PRESSUPOST*.pdf` — pressupostos amb capa de text
   - `ACCEPTACIO/DADES CLIENT.txt` — dades del client
   - Fitxers `.msg` — només el nom del fitxer (conté info de l'arquitecte)
   - `comanda laboratori*.xls` — només el nom del fitxer
   - Qualsevol `.txt` al directori arrel o subdirectoris
   - Noms de subcarpetes com `25.0647/` (contenen pressupostos numerats)

2. **Extreure text** de cada fitxer:
   - Per PDFs, usa Bash amb PyMuPDF:
     ```bash
     cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -c "
     import fitz
     doc = fitz.open('{pdf_path}')
     for page in doc:
         print(page.get_text())
     doc.close()
     "
     ```
   - Per fitxers `.txt`, usa el Read tool directament.
   - Per fitxers `.msg`, anota només el nom del fitxer (conté metadades útils).

3. **Analitzar el text combinat** i extreure camps estructurats:
   - `architect_company` — de "OBRA:" al pressupost o del nom del fitxer .msg
   - `building_category` — C0/C1/C2 del text del pressupost
   - `num_planned_dpsh` — nombre d'assaigs DPSH al pressupost
   - `num_planned_sondeig` — nombre de sondeigs al pressupost
   - `num_planned_spt` — assaigs SPT mencionats al pressupost
   - Qualsevol altra metadada rellevant del projecte

4. **Guardar** a `{project_path}/validation/docs_extracted.json` amb el format especificat (veure secció Formats JSON).

**IMPORTANT:** Noms de camps com `architect_company` han de ser en MAJÚSCULES per a noms propis.

### Pas 6: Resum final

Mostra un resum com:
```
============================================================
Visio Projecte: {project_name}
============================================================
  planol:  A.01.pdf → planol_extracted.json ✓ (conf: 0.92)
  dpsh:    PENETROS.pdf → dpsh_extracted.json ✓ (conf: 0.95)
  sondeig: SONDEIG.pdf → sondeig_extracted.json ✓ (conf: 0.88)
  docs:    PRESSUPOST*.pdf + DADES CLIENT.txt → docs_extracted.json ✓

  Temps total: ~40s
  Fitxers generats: 4/4

Per continuar: Eva obre localhost:8765, selecciona el projecte al wizard.
============================================================
```

Per extraccions saltades (cache):
```
  planol:  planol_extracted.json ja existeix (cache hit, usa --force per re-extreure)
```

---

## Prompts d'Extracció

### Rol: Especialista Geotecnic

Aplica SEMPRE aquest context abans de cada extracció:

> Ets un especialista en extracció de dades geotecniques. La teva tasca es extreure acuradament dades de documents de camp escrits a ma i convertir-los a JSON estructurat.
>
> PRINCIPIS CLAU:
> 1. PRECISIO: Nomes extreu el que pots veure clarament. Mai inventis ni fabriquis valors.
> 2. INCERTESA: Marca valors incerts amb puntuacions de confianca mes baixes.
> 3. COMPLETESA: Extreu TOTES les dades visibles al document.
> 4. ESTRUCTURA: Segueix EXACTAMENT el format JSON especificat.
>
> Quan un valor no es clar:
> - Si es parcialment llegible, extreu la teva millor interpretacio i nota confianca < 1.0
> - Si es completament illegible, usa "??" i confianca = 0.0
> - Sempre afegeix una nota explicant el problema
>
> La sortida sera revisada per humans, aixi que marcar la incertesa es essencial.

### Prompt: Planol (architect_plan, situation_plan)

Analitza aquest planol arquitectonic d'un projecte de construccio.

**TASCA:** Extreu dades del projecte i l'edifici en JSON estructurat.

**ESTRUCTURA DEL DOCUMENT:**
- Caixeti/cartutx (tipicament cantonada inferior dreta):
  - Nom/tipus del projecte (ex: "Habitatge Unifamiliar Aillat", "Nau Industrial")
  - Ubicacio: carrer, numero, codi postal, municipi
  - Promotor: empresa o particular
  - Arquitecte: nom i numero de collegiat
  - Empresa d'arquitectura: SLP o nom de firma (pot ser separat del nom de l'arquitecte)
  - Escala, data
- Planol de situacio / emplacament:
  - Superficie parcella en m2
  - Dimensions parcella (longitud x amplada)
  - Ocupacio edifici en m2 o percentatge
- Superficies per planta (pot apareixer en taula, quadre de superficies, o anotacions):
  - Superficie de cada planta individualment (PB: 280m2, P1: 86m2, Ps: 120m2)
  - Pot etiquetar-se "sup. util", "sup. construida", "ocupacio", "m2 construits", etc.
  - Busca a: quadres de superficies, taules, llegendes, anotacions al planol
- Taula JUSTIFICACIO PLANEJAMENT (si existeix):
  - Taula amb dues columnes: "Planejament" (norma urbanistica) i "Projecte" (valor real del projecte)
  - Fila "Parcel·la mínima": la columna "Projecte" conte la **superficie total de la parcella** (ex: 995,00m2)
  - IMPORTANT: extreu el valor de la columna "Projecte", NO de "Planejament" (que es el minim urbanistic)
  - Aquest valor es la "superficie de la parcella segons planols cadastrals" per Taula 1 de l'informe
- Seccio / alcat:
  - Numero de plantes (PB, PB+1, Ps+PB+2Pp, etc.)
  - Alcada maxima de l'edifici en metres

**REGLES D'EXTRACCIO:**
1. Extreu text EXACTAMENT com esta escrit (catala/castella)
2. Per dimensions, prefereix valors amb unitats explicites (m, m2)
3. Numero de plantes: usa el format tal com esta escrit (ex: "Pb+P1", "Ps+Pb+2Pp")
4. Si un valor te multiples interpretacions, usa el mes especific
5. Posa null per camps no trobats
6. L'ocupacio pot etiquetar-se "ocupacio", "superficie construida", o similar
7. Si architect_company no esta llistat separadament, posa null (no inventis del nom de l'arquitecte)
8. Busca superficies per planta individualment — si el planol mostra un quadre de superficies o anotacions amb m2 per planta, extreu-les a `floor_surfaces` (array d'objectes amb `floor` i `area_m2`). Si nomes hi ha una superficie total, posa-la com a unic element.
9. Si hi ha taula JUSTIFICACIO PLANEJAMENT, extreu la superficie de la parcella de la columna "Projecte" de la fila "Parcel·la mínima" (o similar) com a `parcela_projecte_m2`. NO confondre amb el valor de "Planejament" (minim urbanistic).

**CONFIANCA:**
- 1.0: Text impres clar, inequivoc
- 0.9: Llegible amb minima incertesa
- 0.7-0.8: Llegible pero text petit o requereix interpretacio
- 0.5: Dificil de llegir o ambigu
- Usa null per valors no trobats

### Prompt: DPSH (dpsh_field_sheet)

Analitza aquest full de camp DPSH (Dynamic Probing Super Heavy).

**TASCA:** Extreu totes les dades en format JSON estructurat.

**ESTRUCTURA DEL DOCUMENT:**
- El document mostra resultats de penetracio per a un o mes punts d'assaig (P-1, P-2, etc.)
- Cada assaig te una columna amb profunditat (en metres) i valors N20 corresponents (cops per 20cm)
- Pot incloure: valors de parell (PAR/torque), indicadors de nivell freatic (N.F.), marcadors de nivell de sol
- Un factor de correccio (tipicament 0.83) pot apareixer a la part superior
- El refus s'indica amb "R" o valors molt alts (>=100)

**REGLES D'EXTRACCIO:**
1. Per cada punt d'assaig, extreu TOTS els parells profunditat/N20
2. Les profunditats son tipicament en increments de 20cm: 0.20, 0.40, 0.60, etc.
3. Els valors N20 son enters (cops)
4. Marca valors illegibles o incerts amb confianca < 1.0
5. Usa "??" per valors N20 completament illegibles (confianca 0.0)
6. Nota qualsevol refus (marcador R o N20 >= 100)
7. Nota nivell freatic si s'indica

**COMPARACIO AMB EXCEL:**
- Si hi ha `dpsh_excel` al file_mapping.json, carrega l'Excel amb:
  ```bash
  cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -c "
  from automation.dpsh_extractor import DPSHExtractor
  ext = DPSHExtractor('{excel_path}')
  data = ext.extract()
  import json; print(json.dumps(data, indent=2, default=str))
  "
  ```
- Compara cada valor N20 extret visualment amb l'Excel
- Si coincideixen: `has_discrepancy: false`
- Si difereixen: `has_discrepancy: true` amb nota

**CONFIANCA:**
- 1.0: Valor clar i inequivoc
- 0.7-0.9: Llegible pero amb certa incertesa (ratllat, descolorit)
- 0.5-0.7: Parcialment llegible, requereix interpretacio
- <0.5: Incert, requereix verificacio
- 0.0: Illegible, usa "??" pel valor

### Prompt: Sondeig (sondeig_field_sheet)

Analitza aquest full de camp de Sondeig (perforacio a rotacio).

**TASCA:** Extreu totes les dades de capes de sol en format JSON estructurat.

**ESTRUCTURA DEL DOCUMENT:**
- El document mostra un registre de perforacio per a un o mes sondeigs (S-1, S-2, etc.)
- Cada sondeig te una columna grafica mostrant capes de sol
- Per cada capa: rang de profunditat, descripcio del sol, color, humitat, consistencia/densitat
- Pot incloure classificacio USCS (CL, SM, SP, GW, etc.)
- El nivell freatic (N.F.) pot estar indicat
- Roca o refus pot estar notat al fons

**REGLES D'EXTRACCIO:**
1. Per cada sondeig, extreu TOTES les capes de sol de superficie a profunditat final
2. Les profunditats han de ser continues (depth_to_m d'una capa = depth_from_m de la seguent)
3. Extreu descripcions del sol en catala/castella tal com estan escrites
4. Nota classificacio USCS si es visible (tipicament en columna separada)
5. Estats d'humitat: sec, humit, saturat
6. Consistencia (sols cohesius): tova, ferma, dura
7. Densitat (sols granulars): fluixa, mitja, densa
8. Marca valors incerts amb puntuacions de confianca apropiades
9. Extreu resultats SPT si hi ha columna SPT (N1, N2, N3, Ntotal)

**CONFIANCA:**
- 1.0: Descripcio clara i inequivoca
- 0.7-0.9: Llegible pero amb certa incertesa
- 0.5-0.7: Parcialment llegible
- <0.5: Incert
- 0.0: Illegible

---

## Formats JSON de Sortida

### planol_extracted.json

```json
{
  "source_file": "A.01.pdf",
  "extraction_date": "2026-03-04T14:00:00",
  "extraction_method": "claude_vision",
  "overall_confidence": 0.90,
  "status": "pending_review",
  "architect_data": {
    "source_file": "A.01.pdf",
    "project_name": "Habitatge Unifamiliar Aillat",
    "location": "C/ Mestre Ramon Ortiz, 25220 Bell-Lloc d'Urgell",
    "promotor": "Ramon Mitjana SL",
    "architect": "Jordi Bosch Novell",
    "architect_company": null,
    "dimensions": {
      "parcel_area_m2": {"pdf_value": 598.0, "confidence": 0.95},
      "parcela_projecte_m2": {"pdf_value": 995.0, "confidence": 1.0},
      "building_footprint_m2": {"pdf_value": 296.88, "confidence": 0.90},
      "num_floors": {"pdf_value": "Pb+P1", "confidence": 1.0},
      "max_height_m": {"pdf_value": 8.38, "confidence": 0.85},
      "plot_length_m": {"pdf_value": 24.57, "confidence": 0.90},
      "plot_width_m": {"pdf_value": 24.72, "confidence": 0.90},
      "floor_surfaces": [
        {"floor": "PB", "area_m2": 280.0, "confidence": 0.90},
        {"floor": "P1", "area_m2": 86.0, "confidence": 0.85}
      ]
    }
  },
  "extraction_notes": "Caixeti clear, dimensions from site plan",
  "reviewer_notes": "",
  "approved_by": "",
  "approval_date": null
}
```

**Camps obligatoris de `architect_data`:** `source_file`, `project_name`, `location`, `promotor`, `architect`, `architect_company`, `dimensions`
**Camps obligatoris de `dimensions`:** `parcel_area_m2`, `building_footprint_m2`, `num_floors`, `max_height_m`, `plot_length_m`, `plot_width_m`
**Camps opcionals:**
- `floor_surfaces` — array d'objectes `{"floor": "PB", "area_m2": 280.0, "confidence": 0.90}`. Si no es troben superficies per planta, ometre o posar array buit `[]`.
- `parcela_projecte_m2` — superficie total de la parcella del projecte, extreta de la columna "Projecte" de la taula JUSTIFICACIO PLANEJAMENT (fila "Parcel·la mínima" o similar). Es la superficie cadastral real, diferent de `parcel_area_m2` (que es la del planol de situacio).
**Cada dimensio** es un objecte `{"pdf_value": <number|string|null>, "confidence": <float>}` o `null` si no trobat.

### dpsh_extracted.json

```json
{
  "source_file": "PENETROS.pdf",
  "extraction_date": "2026-03-04T14:00:00",
  "extraction_method": "claude_vision",
  "overall_confidence": 0.95,
  "status": "pending_review",
  "excel_comparison": {
    "has_excel": true,
    "excel_file": "4001612_DPSH.xls",
    "total_values": 18,
    "matches": 18,
    "discrepancies": 0
  },
  "dpsh_tests": [
    {
      "test_id": "P-1",
      "readings": [
        {
          "depth_m": 0.20,
          "n20": 15,
          "confidence": 1.0,
          "excel_value": 15,
          "has_discrepancy": false,
          "note": null,
          "torque": null,
          "water_indicator": false
        }
      ],
      "refusal_depth_m": 1.40,
      "refusal_detected": true,
      "water_detected": false,
      "water_depth_m": null,
      "correction_factor": 0.83,
      "extraction_notes": "Test completed normally"
    }
  ],
  "reviewer_notes": "",
  "approved_by": "",
  "approval_date": null
}
```

**Si NO hi ha Excel** de comparacio, posa `excel_comparison.has_excel: false` i omit `excel_value`/`has_discrepancy` dels readings.

### sondeig_extracted.json

```json
{
  "source_file": "SONDEIG.pdf",
  "extraction_date": "2026-03-04T14:00:00",
  "extraction_method": "claude_vision",
  "overall_confidence": 0.92,
  "status": "pending_review",
  "metadata": {
    "date": "6-10-2025",
    "location": "Bell-Lloc",
    "address": "C/Antoni Bellet",
    "operator": "Daniel Fernandez",
    "equipment": "ML76A",
    "client": "G3",
    "responsible": "Eva"
  },
  "sondeig_tests": [
    {
      "test_id": "S-1",
      "total_depth_m": 1.80,
      "layers": [
        {
          "depth_from_m": 0.0,
          "depth_to_m": 1.0,
          "description": "Grava con arenas",
          "uscs_classification": null,
          "color": null,
          "moisture": null,
          "consistency": null,
          "density": null,
          "confidence": 0.95,
          "note": null
        }
      ],
      "spt_results": [],
      "water_level_m": null,
      "rock_detected": false,
      "rock_depth_m": null,
      "extraction_notes": null
    }
  ],
  "reviewer_notes": "",
  "approved_by": "",
  "approval_date": null
}
```

### docs_extracted.json

```json
{
  "source_files": ["PRESSUPOST GEOTEC.BELL-LLOCsgtJBN.pdf", "DADES CLIENT.txt"],
  "extraction_date": "2026-03-14T10:00:00",
  "extraction_method": "claude_docs_intel",
  "fields": {
    "architect_company": {"value": "ARQUITECTURA BOSCH NOVELL", "source": "PRESSUPOST p.1 OBRA field", "confidence": 0.95},
    "building_category": {"value": "C1", "source": "PRESSUPOST p.2 'Tipus d'edifici: C1'", "confidence": 1.0},
    "num_planned_dpsh": {"value": 2, "source": "PRESSUPOST p.4 '2,00 UNITATS D'ASSAIG'", "confidence": 1.0},
    "num_planned_sondeig": {"value": 1, "source": "PRESSUPOST p.4 'SONDEIG A ROTACIO'", "confidence": 1.0},
    "num_planned_spt": {"value": null, "source": null, "confidence": null}
  },
  "extraction_notes": "Pressupost PDF had clear text layer. DADES CLIENT.txt confirmed client info."
}
```

**Camps opcionals de `fields`:** Qualsevol camp rellevant trobat als documents. Cada camp és un objecte `{"value": <any|null>, "source": <string|null>, "confidence": <float|null>}`.

---

## Errors i Fallback

- **PDF no trobat:** Mostra warning i continua amb els altres tipus
- **Extracció falla:** Mostra error, NO crea JSON buit, continua amb els altres
- **file_mapping.json no te rols amb visio:** Mostra "Cap PDF amb visio trobat" i surt
- **Directori validation/ no existeix:** Crea'l amb `mkdir -p`

## Notes de Producció

- Aquesta comanda substitueix les 3 comandes individuals (`g3dt-extreure-planol`, `g3dt-validar-penetros`, `g3dt-validar-sondeig`) per a us en batch
- Les comandes individuals segueixen disponibles per a extraccions especifiques o debugging
- Els JSONs generats son identics als que produiria l'SDK d'Anthropic — el wizard els llegeix sense saber l'origen
- Temps estimat: ~10-15s per PDF, ~25-40s total per projecte amb 3 PDFs
