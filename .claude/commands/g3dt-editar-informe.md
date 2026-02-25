# /g3dt-editar-informe

Revisa i corregeix automàticament un informe geotècnic generat: gramàtica catalana, articles, format, completitud.

<command-name>g3dt-editar-informe</command-name>

## Arguments

- `generated_path` (required): Path al fitxer .docx generat (ex: `reference-material/4001612-bell-lloc/4001612_generated.docx`)
- `--reference` (optional): Path al .docx de referència (activa Mode B — només per Bell-Lloc/testing)

> Paths relatius al directori arrel G3DT: /home/josep/projects/claudecode-job/clients/g3dt/

## Exemples

```
# Mode A: Producció (sense referència — s'usa per a cada informe generat)
/g3dt-editar-informe reference-material/4001612-bell-lloc/4001612_generated.docx

# Mode B: Desenvolupament (amb referència — només per testing)
/g3dt-editar-informe reference-material/4001612-bell-lloc/4001612_generated.docx --reference reference-material/4001612-bell-lloc/4001612_informe.docx
```

## Instruccions

Quan l'usuari invoca aquest skill:

### Pas 1: Executar checks automàtics (script Python)

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -m automation.report_editor \
  {generated_path} \
  --project-path {directori_del_projecte}
```

Si l'usuari ha proporcionat `--reference`:
```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -m automation.report_editor \
  {generated_path} \
  --reference {reference_path} \
  --project-path {directori_del_projecte}
```

L'script genera: `{project_path}/validation/edit_checks.json`

Mostra les estadístiques:
```
============================================================
Pas 1: Checks automàtics
============================================================
  [output de l'script]
============================================================
```

### Pas 2: Llegir i revisar els issues trobats

Llegeix `{project_path}/validation/edit_checks.json` amb el Read tool.

Per a cada issue:
- **Auto-fixable** (gramàtica, format): Mostra'l per informació, s'aplicarà automàticament
- **Needs review** (completitud, audit): Avalua semànticament

### Pas 3: Avaluació semàntica dels issues no auto-fixables

Per als issues de tipus `completeness` o `audit`:

Analitza el context del paràgraf i determina:
- Si és un fals positiu (el text és correcte en context)
- Si és un problema real que requereix correcció
- Si requereix acció de l'usuari (dades que falten a user_data.json)

### Pas 4: Preguntar a l'usuari

Mostra un resum dels issues trobats:

```
============================================================
ISSUES TROBATS
============================================================

Auto-fixables (s'aplicaran automàticament):
  1. [grammar] "de el subsòl" → "del subsòl" (paràgraf 23)
  2. [format] "la  cota" → "la cota" (paràgraf 45)
  ...

Requereixen revisió:
  1. [completeness] Paràgraf 67: Article sense nom — possible variable buida
  2. [completeness] Paràgraf 120: Tag Jinja no renderitzat: {{ variable }}
  ...
============================================================
```

Pregunta a l'usuari: "Vols aplicar les correccions auto-fixables?" amb AskUserQuestion.

### Pas 5: Aplicar correccions (si l'usuari ho aprova)

```bash
cd /home/josep/projects/claudecode-job/clients/g3dt && .venv/bin/python -m automation.report_editor \
  {generated_path} \
  --project-path {directori_del_projecte} \
  --apply
```

Mostra el resultat:
```
============================================================
CORRECCIONS APLICADES
============================================================
  Fixes aplicats: {n}
  Output: {path_al_docx_editat}
  Changelog: {path_al_changelog_json}
============================================================
```

### Restriccions Zero Fabrication

L'editor NOMÉS pot:
- Corregir articles catalans (el/la/l'/els/les, del/de la/de l')
- Corregir contraccions (a el → al, per el → pel)
- Eliminar espais dobles
- Corregir puntuació (espais abans/després de punts i comes)

L'editor NO pot:
- Inventar dades tècniques
- Afegir contingut geològic no present a les fonts
- Canviar valors numèrics
- Substituir noms de carrers, empreses o persones
- Modificar cap dada que provingui de variables del template

## Integració amb el pipeline

Aquest skill s'ha de poder cridar automàticament com a últim pas de `/g3dt-generar-informe` (Mode A).
Per fer-ho, al final de la Fase 3 de `g3dt-generar-informe`, afegir:

```
# Post-generació: checks de qualitat
.venv/bin/python -m automation.report_editor {output_docx} --project-path {project_path} --apply
```

## Notes

- Mode A (producció): S'executa per a CADA informe generat. No necessita referència.
- Mode B (desenvolupament): Afegeix comprovacions basades en la referència. Només disponible per projectes amb informe de referència (Bell-Lloc).
- Les correccions de gramàtica són deterministes (regex). Claude Code avalua els casos ambigus.
