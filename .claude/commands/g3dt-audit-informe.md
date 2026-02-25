# /g3dt-audit-informe

Audita intel·ligentment un informe geotècnic generat comparant-lo amb la referència, usant anàlisi semàntica per paràgraf.

<command-name>g3dt-audit-informe</command-name>

## Arguments

- `project_path` (required): Path a la carpeta del projecte (ex: `reference-material/4001612-bell-lloc`)

> project_path és relatiu al directori arrel del projecte G3DT: /home/josep/projects/claudecode-job/clients/g3dt/

## Exemples

```
/g3dt-audit-informe reference-material/4001612-bell-lloc
```

## Instruccions

Quan l'usuari invoca aquest skill:

### Pas 1: Preparar dades (script Python)

Executa l'script que extreu i pre-classifica tots els paràgrafs:

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -m automation.intelligent_audit \
  {project_path}/*_generated.docx \
  {project_path}/*_informe.docx \
  --project-path {project_path}
```

**IMPORTANT**: Usa `.venv/bin/python` (no `python3`) perquè el venv té les dependències (python-docx, docxtpl, xlrd).

Si no existeix `*_generated.docx` o `*_informe.docx`, demana a l'usuari els paths exactes dels fitxers.

L'script genera: `{project_path}/validation/audit_intelligent.json`

Mostra les estadístiques que imprimeix l'script:
```
============================================================
Pas 1: Preparació de dades
============================================================
  [output de l'script]
============================================================
```

### Pas 2: Llegir el JSON de resultats

Llegeix el fitxer `{project_path}/validation/audit_intelligent.json` amb el Read tool.

Mostra un resum:
```
============================================================
Pas 2: Resum pre-classificació
============================================================
  Total paràgrafs:     {statistics.total_generated}
  Static match:        {statistics.static_match} (text fix plantilla)
  Likely correct:      {statistics.likely_correct} (variable values correctes)
  Needs LLM review:    {statistics.needs_review} (requereix avaluació semàntica)
  Missing in generated:{statistics.missing_in_generated}
  Auto-resolved:       {statistics.auto_resolved_pct}%
============================================================
```

### Pas 3: Avaluació semàntica dels paràgrafs `needs_review`

Per a cada paràgraf amb `classification: "needs_review"` dins `dynamic_paragraphs`, avalua'l semànticament:

**Per a cada paràgraf `needs_review`:**

Analitza el triple:
- **TEMPLATE**: `{template_text}` (amb variables Jinja originals)
- **VARIABLES**: `{variable_values}` (valors que s'haurien renderitzat)
- **GENERAT**: `{generated_text}` (text real al report generat)
- **REFERÈNCIA**: `{reference_text}` (text al report de referència)

Classifica com:
- **CORRECTE**: El generat és correcte donades les variables. La diferència amb la referència és perquè les dades d'entrada són diferents (no un bug).
- **DADES_ERRÒNIES**: Una variable té un valor incorrecte al `user_data.json` (ex: `architect_company` hauria de ser diferent).
- **TEMPLATE_ERROR**: El template Jinja no genera el text esperat (hi ha un bug al template).
- **FORMAT_DIFF**: Correcte funcionalment però diferent format (articles catalans, puntuació, ordre de paraules).
- **INCERT**: No es pot determinar sense més context. Marca per revisió manual.

**Criteris d'avaluació:**
1. Si el generat reflecteix correctament els valors de les variables → CORRECTE (encara que difereixi de la referència)
2. Si una variable té un valor que contradiu la referència i la referència és clarament el valor correcte → DADES_ERRÒNIES
3. Si la plantilla omet text que la referència inclou, o afegeix text incorrecte → TEMPLATE_ERROR
4. Si l'únic canvi és "de l'" vs "del" o puntuació → FORMAT_DIFF
5. En cas de dubte → INCERT

### Pas 4: Actualitzar el JSON amb els resultats

Actualitza el fitxer `{project_path}/validation/audit_intelligent.json`:

Per a cada paràgraf `needs_review` avaluat, afegeix els camps:
- `llm_classification`: CORRECTE | DADES_ERRÒNIES | TEMPLATE_ERROR | FORMAT_DIFF | INCERT
- `llm_explanation`: Breu explicació del perquè de la classificació
- `suggested_fix`: Només si és DADES_ERRÒNIES o TEMPLATE_ERROR — què caldria canviar

Escriu el JSON actualitzat amb el Write tool.

### Pas 5: Resum final

Mostra un resum de l'audit complet:

```
============================================================
AUDIT INTEL·LIGENT COMPLET
============================================================
Total paràgrafs analitzats:  {total}
  Static match (automàtic):   {static_match}
  Likely correct (automàtic): {likely_correct}
  LLM - CORRECTE:            {count}
  LLM - DADES_ERRÒNIES:      {count}
  LLM - TEMPLATE_ERROR:      {count}
  LLM - FORMAT_DIFF:         {count}
  LLM - INCERT:              {count}
  Missing in generated:       {missing}

Qualitat total: {pct}% (static + likely + CORRECTE + FORMAT_DIFF)

Accions necessàries:
  {llista de DADES_ERRÒNIES i TEMPLATE_ERROR amb detall}

Output: {project_path}/validation/audit_intelligent.json
============================================================
```

### Si hi ha DADES_ERRÒNIES o TEMPLATE_ERROR

Llista'ls amb detall:

```
PROBLEMES TROBATS:

1. [DADES_ERRÒNIES] Paràgraf {idx}:
   Variable: architect_company
   Valor actual: "MITJANA SL"
   Valor esperat: "ARQUITECTURA BOSCH NOVELL"
   Suggeriment: Actualitzar user_data.json

2. [TEMPLATE_ERROR] Paràgraf {idx}:
   Template: "... {{ variable }} ..."
   Problema: Falta article "l'" davant del nom de l'empresa
   Suggeriment: Corregir template a "... l'{{ variable }} ..."
```

Pregunta a l'usuari si vol aplicar les correccions automatitzables.

## Notes

- L'script Python fa el treball pesat d'extracció i alineació (ràpid, sense LLM)
- Claude Code fa l'avaluació semàntica (comprensió de context, català, geotecnia)
- Això combina el millor dels dos mons: velocitat computacional + comprensió lingüística
- `autojunk=False` al SequenceMatcher resol el bug de text català del `highlight_report.py`
