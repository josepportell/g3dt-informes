# Pla: Enhanced Dev Tab + Pipeline Trace

**Data**: 2026-03-23
**Estat**: Aprovat, pendent d'implementació
**Prioritat**: Alta — diagnosticar per què 7/34 variables queden buides malgrat tantes etapes d'extracció

## Context

Malgrat tenir moltes etapes d'extracció (FileMiner regex, Groq LLM, Content Discovery, ICGC APIs, Vision), el projecte Castellar té 7/34 variables sense omplir. La pestanya Dev actual mostra QUÈ s'ha omplert però no PER QUÈ altres senyals s'han descartat ni COM el pipeline pren decisions.

**Causa arrel**: Les dades SÍ s'extreuen però es descarten silenciosament en diversos punts:
- Senyals amb `maps_to=None` es descarten a `resolve_competition()` (línia 82 de `competition.py`)
- Les alternatives s'emmagatzemen però només s'exposen parcialment (limit de 5, sense confiança)
- No hi ha visibilitat de quins fitxers aporten quins senyals
- No hi ha desglossament per etapa del que es troba vs el que sobreviu

## Arquitectura actual del pipeline

```
Fase 0:   SmartScan (tier1_filename.py)  → file_mapping.json
Fase 0.1: Content Discovery              → prefills (UTM, client, access)
Fase 0.3: FileMiner (regex, Excel, msg)  → Signal[] (112 senyals Castellar)
Fase 0.4: Groq LLM (gap-filling)         → Signal[] (16 senyals afegits)
Fase 0.5: Auto Extract (DPSH, Lab, ICGC) → prefills (coords, geologia, sulfats)
Fase 1:   Vision (planol, sondeig, dpsh) → *_extracted.json

Tots → resolve_competition() → ResolvedValue (guanyador + alternatives)
     → _merge_prefills() → prefills dict final → wizard UI
```

### Punts de pèrdua de dades identificats

| Punt | Ubicació | Què es perd |
|------|----------|-------------|
| `maps_to=None` | `competition.py:82` | Senyals que cap etiqueta mapeja a variable |
| Label no reconegut | `label_map.py` | "3 HAB" → no mapeja a `num_floors` |
| "Només omplir buits" | `auto_extractor.py:269` | Valor millor arriba tard, slot ja ple |
| Alternatives truncades | `api.py:583` | Només 5 alternatives, sense confiança |
| Cap etiqueta → cap senyal | miners de text | Si el document no té "ARQUITECTE:" no es crea senyal |

### Estructura de dades existent (ja implementada)

```python
# Signal (fileminer/models.py) — ja conté tota la proveniència
Signal(
    label="ADREÇA OBRA",           # Etiqueta original
    value="C/ Arbrells 18A",       # Valor extret
    maps_to="street_address",      # Variable destí (o None!)
    source_file="PRESSUPOST.pdf",  # Fitxer font
    extraction_method="groq_llm",  # Mètode
    confidence=0.95,               # Confiança
    priority=42,                   # Prioritat (menor guanya)
)

# ResolvedValue (fileminer/models.py) — guanyador + perdedors
ResolvedValue(
    variable="street_address",
    signal=<Signal guanyador>,
    alternatives=[<Signal perdedor 1>, <Signal perdedor 2>],
)

# AutoExtractionResult (auto_extractor.py) — preserva TOT
auto_result.mining_result.signals  # TOTS els senyals (incloent maps_to=None)
auto_result.mining_alternatives    # alternatives per variable (dict)
auto_result.prefills               # valors finals
auto_result.sources                # font per variable
```

## Part B: Enhanced Dev Tab

### Nou endpoint: `/api/dev-analysis-v2/{project_name}`

Retorna el traçat complet de senyals, reutilitzant dades existents:

```json
{
  "variables": {
    "street_address": {
      "winner": {
        "value": "C/ Arbrells 18A",
        "source_file": "PRESSUPOST.pdf",
        "extraction_method": "groq_llm",
        "confidence": 0.95,
        "priority": 42
      },
      "alternatives": [
        {"value": "Carrer Arbrells, 18A...", "source_file": "DADES.xlsx",
         "extraction_method": "cell_adjacent", "confidence": 0.85, "priority": 35}
      ]
    },
    "architect_name": null
  },
  "unmapped_signals": [
    {"label": "CLIENT", "value": "GRUP ALMA", "maps_to": null,
     "source_file": "PRESSUPOST.msg", "extraction_method": "label_value"}
  ],
  "files_summary": {
    "PRESSUPOST.pdf": {
      "source_type": "pressupost_pdf",
      "signals_total": 8, "signals_mapped": 5,
      "variables_won": ["client_address", "expedient"],
      "variables_lost": ["report_date"]
    }
  },
  "pipeline_stages": {
    "fileminer": {"signals": 112, "mapped": 45, "won": 22},
    "groq_llm": {"signals": 16, "mapped": 16, "won": 6},
    "content_discovery": {"signals": 6, "mapped": 6, "won": 5},
    "icgc": {"signals": 7, "mapped": 7, "won": 7}
  },
  "coverage": {"filled": 27, "unfilled": 7, "total": 34, "pct": 79.4}
}
```

**Font de dades**: `AutoExtractionResult.mining_result.signals` ja conté TOTS els senyals (incloent no mapejats). Només cal exposar-los correctament. **No cal canviar el pipeline d'extracció**.

### Frontend: Dev tab millorada a `review.html`

Substituir el renderitzat actual del Dev tab:

1. **Barra de cobertura** (mantenir existent)
2. **Etapes del pipeline** — targetes horitzontals: contribució de cada etapa (senyals trobats / mapejats / guanyadors)
3. **Taula de variables** — 34 files, una per variable objectiu:
   - Nom variable | Valor guanyador | Fitxer font | Mètode | Conf% | Nº alternatives
   - Clic a fila → expandir per veure tots els senyals competidors amb prioritat/confiança
   - Variables buides destacades en vermell
4. **Taula de contribució de fitxers** — una fila per fitxer minat:
   - Ruta fitxer | Tipus font | Total senyals | Mapejats | Variables guanyades
5. **Senyals no mapejats** — senyals amb `maps_to=None` (revela forats a label_map.py)

### Fitxers a modificar

| Fitxer | Canvi |
|--------|-------|
| `web/api.py` | Nou endpoint `/api/dev-analysis-v2/{project}` (~80 línies) |
| `web/wizard_service.py` | Cache `AutoExtractionResult` (no només prefills) per accedir a senyals crus |
| `templates/validation/review.html` | Nova funció `renderDevAnalysisV2()` (~200 línies) substituint Dev tab actual |

### Detalls d'implementació

**Endpoint** (`web/api.py`):
- Obtenir `AutoExtractionResult` cachejat de wizard_service
- De `mining_result.signals`: agrupar per `maps_to`, comptar mapejats/no mapejats per fitxer
- Re-executar `resolve_competition()` sobre senyals per obtenir guanyadors + alternatives amb objectes Signal complets
- No mapejats = senyals on `maps_to is None` i label no és trivial

**Reutilització** (no cal crear noves estructures):
- `competition.py:resolve_competition()` — ja retorna guanyadors + alternatives
- `models.py:Signal` — ja té tots els camps de proveniència
- `AutoExtractionResult.mining_result` — ja preservat pel pipeline

**Canvi al cache** (`web/wizard_service.py`):
- Actualment: `_prefill_cache[project] = merged_prefills`
- Canvi: `_prefill_cache[project] = (merged_prefills, auto_result)` — tupla amb ambdós
- L'endpoint v2 llegeix `auto_result.mining_result.signals` del cache

## Part C: Pipeline Streaming Log (després de B)

### Nou endpoint SSE: `/api/pipeline-log/{project_name}`

Emet events en temps real mentre cada fase s'executa:

```
event: phase_start     {"phase": "0.3", "name": "FileMiner", "files": 19}
event: file_mined      {"file": "PRESSUPOST.pdf", "signals": 8, "mapped": 5}
event: signal_resolved {"variable": "street_address", "winner": "PRESSUPOST.pdf", "alts": 2}
event: phase_complete  {"phase": "0.3", "signals": 112, "mapped": 45, "ms": 3100}
event: phase_start     {"phase": "0.4", "name": "Groq LLM", "missing": ["architect_name"...]}
event: groq_call       {"file": "PLAN_COST.xlsx", "found": {"num_floors": "3"}}
event: phase_complete  {"phase": "0.4", "signals": 16, "new_prefills": 5, "ms": 8200}
```

### Implementació

- Estendre el callback `on_progress` de `auto_extractor.py` per emetre events a nivell de senyal
- Nova pestanya al frontend amb visor de log amb auto-scroll, codificat per colors per fase
- Cada entrada expandible per mostrar detalls del senyal cru

### Fitxers a modificar (Part C)

| Fitxer | Canvi |
|--------|-------|
| `automation/auto_extractor.py` | Estendre callback `on_progress` amb events a nivell de senyal |
| `web/api.py` | Nou endpoint SSE `/api/pipeline-log/{project}` |
| `templates/validation/review.html` | Nova pestanya "Pipeline Log" |

## Ordre d'execució

1. **Part B backend**: Canvi al cache de wizard_service + nou endpoint v2 a api.py
2. **Part B frontend**: Nou renderDevAnalysisV2() substituint Dev tab actual
3. **Part C backend**: Events on_progress estesos + endpoint SSE
4. **Part C frontend**: Pestanya Pipeline Log

## Verificació

**Part B:**
1. Carregar Castellar → Dev tab mostra 34 variables amb detall guanyador/alternatives
2. Variables buides mostren "cap senyal" (confirma que les dades no s'extreuen, no es perden)
3. Variables plenes s'expandeixen per mostrar tots els senyals competidors amb prioritat/confiança
4. Secció "Fitxers" mostra que msg_attachments/PLAN_COST ara contribueix
5. "Senyals no mapejats" revela forats a label_map.py

**Part C:**
1. Seleccionar projecte → Pipeline Log emet fase per fase
2. Veure detall a nivell de fitxer: quins fitxers minats, senyals trobats
3. Veure extraccions Groq en temps real
4. Comparar log amb resultats del Dev tab

## Canvis ja implementats avui (2026-03-23)

### .msg Attachment Re-processing
- `automation/fileminer/__init__.py`: Second pass en mine_project() que re-mina fitxers extrets de .msg
- `automation/fileminer/__init__.py`: Groq també camina validation/msg_attachments/
- `automation/fileminer/__init__.py`: `.msg` → `content_email` a _EXT_TO_SOURCE
- `automation/smartscan/tier1_filename.py`: Rol `project_email` per fitxers .msg + scope wildcard `*`

### SmartScan UI fix
- `templates/validation/review.html`: Fix collapsed "Fitxers informatius" section (this.closest('tbody') vs this.parentElement)
