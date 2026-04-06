# /g3dt-dev-refresh-vision

Refreshes vision caches (planol, DPSH, sondeig) for one or all reference projects. Runs the full vision pipeline with --force to regenerate all extracted JSON files.

<command-name>g3dt-dev-refresh-vision</command-name>

## Arguments

`$ARGUMENTS` = project filter (optional), `--all` for all 7 reference projects

Examples:
```
/g3dt-dev-refresh-vision 4001612              # One project (Bell-Lloc)
/g3dt-dev-refresh-vision --all                # All 7 reference projects
/g3dt-dev-refresh-vision 3001621 3001631      # Multiple by expedient
```

## Instruccions

### Pas 1: Determinar projectes

Reference projects:
```
4001612 BELL-LLOC
3001621 CASTELLAR DEL VALLES
3001631 RUBI
4001607 LINYOLA
4001670 ALCOLETGE
4001671 VILANOVA DE SEGRIA
4001679 ANCILES
```

- Si `$ARGUMENTS` conté `--all`: processa tots 7
- Si conté números d'expedient (4001612, 3001621...): filtra per aquells
- Si buit: demana a l'usuari quin projecte vol

### Pas 2: Per cada projecte, executar /g3dt-visio-projecte --force

Per cada projecte seleccionat, executa:
```
/g3dt-visio-projecte reference-material/{project_folder} --force
```

Això regenera:
- `validation/planol_extracted.json` (si té architect_plan)
- `validation/dpsh_extracted.json` (si té dpsh_field_sheet)
- `validation/sondeig_extracted.json` (si té sondeig_field_sheet)
- `validation/docs_extracted.json` (documents de text)

### Pas 3: Després de cada projecte, mostrar resum parcial

```
[1/7] 4001612 BELL-LLOC ✓
  planol: A.01.pdf → planol_extracted.json (conf: 0.92)
  dpsh: PENETROS.pdf → dpsh_extracted.json (conf: 0.95)
  sondeig: SONDEIG.pdf → sondeig_extracted.json (conf: 0.88)
  docs: 3 files → docs_extracted.json

[2/7] 3001621 CASTELLAR DEL VALLES ✓
  planol: (no architect_plan role)
  dpsh: PENETROS + SONDEIG.pdf → dpsh_extracted.json (conf: 0.90)
  ...
```

### Pas 4: Resum final

```
============================================================
Vision Refresh Complete
============================================================
  Projects processed: 7/7
  Vision files regenerated: 24
  Errors: 0

  Next step: run diagnostic
    .venv/bin/python scripts/diagnostic_trace.py --all --classify
============================================================
```

### Pas 5: Si l'usuari vol, executar diagnostic

Pregunta: "Vols executar el diagnostic ara per mesurar l'impacte?"

Si sí:
```bash
cd /home/Josep/projects/claudecode-job/clients/g3dt && .venv/bin/python scripts/diagnostic_trace.py --all --classify 2>&1
```

## Notes

- Cada projecte tarda ~25-40s (3 PDFs per visió)
- Total per 7 projectes: ~3-5 minuts
- Usa --force per ignorar caches existents
- Els JSONs generats son compatibles amb el wizard
- Recomanat: executar un projecte primer per verificar, després la resta
