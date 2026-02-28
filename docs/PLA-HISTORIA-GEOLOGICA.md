# Pla: Integració de plantilles d'Història Geològica

Data: 2026-02-28
Branca: `feat/historia-geologica`

## Context

Eva ha enviat 238 plantilles .docx d'història geològica organitzades per municipis i regions.
Ubicació: `templates/historia-geologica/HISTORIA GEOLÒGICA/`

## Fases

### Fase 1 — Generar índex automàtic (avui)
- Script Python que parseja els 238 noms de fitxer
- Extreu: municipi, comarca/zona, tier de jerarquia
- Genera un JSON revisable per Eva
- Identifica duplicats i variants geològiques

### Fase 2 — Eva valida l'índex
- Eva revisa el JSON (~30 min)
- Corregeix assignacions, resol duplicats
- Anota variants geològiques (ex: Castellar eocè → quan aplica?)
- Pregunta clau: com tria Eva la plantilla? Només per municipi o també mira geologia ICGC?

### Fase 3 — Lògica de lookup al runtime
- Input: municipi del projecte + (opcionalment) geologia ICGC
- Jerarquia: municipi exacte → fuzzy → zona → regional
- Extreu text del .docx seleccionat

### Fase 4 — Inserció al report_generator
- Injecta el text d'història geològica a la secció corresponent del .docx generat
- Mínim canvi al codi existent (merge net amb altres branques)

## Jerarquia de matching

```
1. Municipi exacte a +Situacions/     (prioritat màxima)
2. Municipi a fitxers arrel o zones/
3. Zona/comarca (Zona Vallès, Zona Penedès...)
4. Regional genèric (marc geològic de Lleida...)
```

## Complexitats identificades

- Variants geològiques: "Castellar del Vallès" vs "Castellar del Vallès eocè"
- Duplicats: Pallejà a +Situacions/ i Zona Llobregat/
- Naming: "St."/"Sant"/"Santa", accents, "i rodalies"
- Cobertura desigual: Barcelona extens, Lleida/Tarragona escàs

## Fitxers clau

- `templates/historia-geologica/` — plantilles .docx
- `templates/historia-geologica/index.json` — índex generat (Fase 1)
- `docs/PLA-HISTORIA-GEOLOGICA.md` — aquest document
