# Guia de Diagnostics del Pipeline G3DT

Eina principal: `scripts/diagnostic_trace.py`
Compara la sortida del pipeline complet contra els valors de referencia d'Eva per cada projecte.

## Execucio rapida

```bash
# Un projecte, nomes mismatches (us per defecte)
.venv/bin/python scripts/diagnostic_trace.py --project 4001612

# Un projecte, totes les variables (incl. MATCH i CLOSE)
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --all

# Tots els projectes amb matriu cross-project
.venv/bin/python scripts/diagnostic_trace.py

# Tots els projectes amb classificacio de mismatches
.venv/bin/python scripts/diagnostic_trace.py --classify
```

## Funcionalitats principals

### 1. Component Scorecard (`--components`)

Mostra quins components del pipeline produeixen cada valor i la seva precisio.

```bash
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --components
```

Sortida:
```
Component              Produced   Match   Close  Mismatch  Accuracy
---------------------- -------- ------- ------- --------- ---------
fileminer_regex               2       0       2         0    100.0%
groq_llm                      3       1       1         1     66.7%
vision_planol                 4       1       1         2     50.0%
llm_synthesis                 4       2       1         1     75.0%
computed                     11       6       0         5     54.5%
...
```

Components rastrejats:
- `fileminer_regex` -- Miners Python (regex, cell_adjacent, label_value)
- `groq_llm` -- Extraccio profunda amb Groq LLM
- `vision_planol` -- Lectura visual del planol A.01.pdf
- `vision_sondeig` -- Lectura visual del sondeig
- `vision_dpsh` -- Lectura visual del DPSH
- `llm_synthesis` -- Sintesi Claude (building_type, architect, client, location)
- `cadastre` -- API Cadastre (adjacents, geometria parcel-la)
- `icgc` -- API ICGC (geologia, elevacio, pendent)
- `geocode` -- Geocodificacio (Nominatim + Cadastre)
- `dpsh_extractor` -- Extraccio Excel DPSH
- `lab_extractor` -- Extraccio PDF laboratori
- `computed` -- Variables calculades (Terzaghi, Schmertmann, CTE, etc.)
- `constant` -- Constants fixes
- `template_generated` -- Text generat per plantilla
- `content_discovery` -- Descobriment de contingut (pressupostos, emails)

### 2. Snapshot JSON (`--save`)

Desa un fitxer JSON amb tots els resultats, metadata operacional i senyals per variable.

```bash
# Un projecte
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --save

# Tots els projectes (genera snapshots individuals + resum cross-project)
.venv/bin/python scripts/diagnostic_trace.py --save
```

Snapshots desats a: `docs/diagnostics/`
- Per projecte: `2026-04-08_4001612_BELL-LLOC_a3f7c2.json`
- Cross-project: `2026-04-08_CROSS_b4e8d3.json`

Contingut del snapshot:
- **metadata**: timestamp, models LLM (.env), fases executades/cached, duracio
- **summary**: match/close/mismatch/not_extracted amb percentatge
- **tier_summary**: resultats per tier (A=auto, B=manual, C=judici professional)
- **component_summary**: precisio per component
- **variables**: per cada variable: valor Eva, valor pipeline, source, component, tier, estat, llista completa de senyals, classificacio del mismatch
- **format_learning**: cobertura d'extraccio per document, camps que falten

### 3. Deep Trace (`--concept X --deep`)

Mostra el viatge complet d'una variable pel pipeline: des de l'extraccio fins a la comparacio amb Eva.

```bash
# Investigar per que client_name no es correcte
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --concept client_name --deep

# Investigar una variable calculada
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --concept qa_value --deep

# Investigar una variable que funciona (verificar robustesa)
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --concept municipality --deep
```

Seccions del deep trace:

1. **EVA REFERENCE** -- Valor de referencia d'Eva
2. **DOCUMENT SOURCES** -- Cobertura format de cada document (camps esperats vs extrets)
3. **ALL SIGNALS** -- Tots els senyals trobats per tots els components, amb prioritat, confianca i si coincideixen amb Eva
4. **COMPETITION RESOLUTION** -- Quin senyal va guanyar i per que (prioritat o confianca)
5. **FINAL COMPARISON** -- Valor pipeline vs Eva, estat, desviacio
6. **ROBUSTNESS** -- Quants senyals confirmen el valor d'Eva, que passa si el guanyador desapareix

Per variables calculades (qa_value, settlement, k30_value), la seccio 3 mostra les entrades del calcul (Nb, B, Df, cohesio, phi) en lloc de senyals.

### 4. Cross-Run Diff (`--diff`)

Compara dos snapshots desats per detectar millores i regressions.

```bash
.venv/bin/python scripts/diagnostic_trace.py \
    --diff docs/diagnostics/run1.json docs/diagnostics/run2.json
```

Sortida:
```
Variable           Run A        Run B        Change
client_name        MATCH        CLOSE        REGRESSION
building_type      MISMATCH     MATCH        IMPROVEMENT
qa_value           CLOSE        CLOSE        = (value changed) (2.85 -> 2.90)

Summary: 2 improvements, 1 regression, 30 unchanged
Component accuracy delta:
  groq_llm: 75.0% -> 62.5% (-12.5%)
```

Us tipic: canviar un model LLM a `.env`, re-executar `--save`, comparar amb `--diff`.

## Cas d'us: Investigar per que un valor es incorrecte

```bash
# 1. Executar diagnostic per veure quines variables fallen
.venv/bin/python scripts/diagnostic_trace.py --project 4001612

# 2. Investigar una variable concreta
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --concept building_type --deep

# 3. El deep trace mostra:
#    - Si algun senyal tenia el valor correcte (PRIORITY issue: arreglar prioritats)
#    - Si cap senyal tenia el valor correcte (EXTRACTION issue: millorar miner/vision)
#    - Si el valor es calculat (CALC issue: revisar formula)
#    - Si el format del document no es conegut (FORMAT issue: afegir labels al schema)
```

## Cas d'us: Comparar models LLM

```bash
# 1. Desar snapshot amb model actual
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --save

# 2. Canviar model a .env (ex: GROQ_TEXT_MODEL=llama-4-scout...)
# 3. Netejar cache si cal (G3DT_NO_CACHE=1)
# 4. Desar segon snapshot
.venv/bin/python scripts/diagnostic_trace.py --project 4001612 --save

# 5. Comparar
.venv/bin/python scripts/diagnostic_trace.py \
    --diff docs/diagnostics/2026-04-08_..._first.json \
           docs/diagnostics/2026-04-08_..._second.json
```

## Cas d'us: Avaluar estabilitat d'un component

```bash
# Executar tots els projectes amb scorecard
.venv/bin/python scripts/diagnostic_trace.py --components --save

# Mirar la taula de components: si un component te >90% accuracy
# en tots els projectes, es pot considerar estable.
# Si un component te <70%, necessita investigacio.
```

## Classificacio de Mismatches

Quan `--classify` es actiu, els mismatches es classifiquen en:

| Classificacio | Significat | Accio |
|---------------|-----------|-------|
| **PRIORITY** | El valor correcte existeix com a senyal alternatiu | Ajustar prioritats al schema de conceptes |
| **EXTRACTION** | Cap senyal te el valor correcte | Millorar miner, vision o afegir nova font |
| **FORMAT** | Diferencia de format/presentacio | Millorar normalitzador o template |
| **CALC** | Variable calculada (qa, settlement, k30) | Revisar formula o entrades del calcul |
| **NARRATIVE** | Text descriptiu (site_description, etc.) | Requereix vocabulari d'Eva o LLM de text |

## Tiers de Variables

| Tier | Descripcio | Objectiu |
|------|-----------|----------|
| **A** | Auto-extractable (municipi, carrer, sulfats, radon...) | ~95% accuracy |
| **B** | Manual/observacio (adjacents, descripcio solar, acces) | Millora amb Street View, ortho |
| **C** | Judici professional (E, Qa, assentament, K30) | Correcte si formules i entrades son correctes |

## Relacio amb Slash Commands existents

| Comanda | Script | Us |
|---------|--------|---|
| `/g3dt-dev-eva-vs-pipeline` | `scripts/compare_eva_vs_pipeline.py` | Comparacio simple Eva vs pipeline (sense signal trace) |
| `/g3dt-dev-benchmark-compare` | `scripts/compare_benchmarks.py` | Comparacio tiered (A/B/C) amb LLM-as-judge per Tier B |
| `/g3dt-dev-readiness-summary` | `scripts/collect_readiness.py` | Resum de readiness per projecte (camps omplerts vs total) |
| `/g3dt-dev-refresh-vision` | (invoca `/g3dt-visio-projecte --force`) | Regenerar caches de visio (planol, DPSH, sondeig) |

**`diagnostic_trace.py` es l'eina principal** que integra la comparacio amb Eva + signal trace + component attribution + snapshots. Les slash commands existents son utils per tasques mes lleugeres o especifiques.

## Referencia rapida de flags

```
--project NUM      Filtrar per expedient (ex: 4001612)
--concept VAR      Filtrar per variable (substring match)
--all              Mostrar totes les variables (incl. MATCH/CLOSE)
--tolerance PCT    Tolerancia numerica (default: 5%)
--classify         Mostrar classificacio de mismatches al final
--components       Mostrar scorecard per component
--save             Desar snapshot JSON a docs/diagnostics/
--deep             Deep trace (requereix --concept)
--diff A.json B.json  Comparar dos snapshots
```

## Notes tecniques

- El diagnostic executa el pipeline complet via `get_prefills(force_refresh=True)`. Triga ~20-30s per projecte.
- El log level de `.env` (`G3DT_LOG_LEVEL`) no afecta el diagnostic. El diagnostic obte les dades directament dels resultats del pipeline, no dels logs del servidor.
- Per forcar extraccions fresques (sense cache), activar `G3DT_NO_CACHE=1` a `.env` abans d'executar.
- Els snapshots inclouen els models LLM actius al moment de l'execucio (llegits de `.env` via `automation.config`).
