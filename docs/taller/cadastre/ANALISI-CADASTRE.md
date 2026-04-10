# Taller: Component Cadastre — Analisi de Fallades

Data inici: 2026-04-08
Baseline: `docs/diagnostics/2026-04-08_CROSS_74a688.json`
Accuracy baseline: **8.3%** (2 match de 24 intents, 7 projectes)

## Resum del Problema

El component `cadastre` genera les descripcions dels adjacents (nord, sud, est, oest) de la parcel-la del projecte. Te la pitjor accuracy de tots els components del pipeline.

| Variable | Match | Close | Mismatch | Not_Extracted |
|----------|-------|-------|----------|---------------|
| adjacent_north_fmt | 1 | 0 | 5 | 1 |
| adjacent_south_fmt | 0 | 0 | 6 | 1 |
| adjacent_east_fmt | 1 | 0 | 5 | 1 |
| adjacent_west_fmt | 0 | 0 | 6 | 1 |
| **Total** | **2** | **0** | **22** | **4** |

## Cadena del Component

```
Adreça → Geocode → Coordenades → Geometria Parcel·la → Edge Probing → Deteccio Veins → Descripcio → Formatatge
         ^^^^^                                          ^^^^^^^^^^^^^   ^^^^^^^^^^^^^^   ^^^^^^^^^^
         pot errar                                      pot fallar      massa generic    OK
```

## Parts que Funcionen Be

| Part | Fitxer | Avaluacio |
|------|--------|-----------|
| Edge probing algorithm | `cadastre_adjacents.py:823-978` | Correcte: identifica aresta mes llarga per direccio, sondeja perpendicular |
| Traduccio de noms de carrer | `cadastre_adjacents.py:499-607` | Completa: 21 tipus de via, 28 noms propis, articles catalans |
| Formatatge de frases | `adjacent_formatter.py:28-120` | Correcte: articles (el/la/una/un), convencio "I finalment" per oest |
| Cache | `cadastre_adjacents.py:56-66` | TTL 90 dies, evita crides redundants |

## Fallades Identificades

### Fallada 1: Sondatge salta carrers estrets

**Evidencia** (Bell-Lloc deep trace `adjacent_south_fmt`):
```
Eva:      "Per la part sud amb el Carrer Antoni Bellet."
Pipeline: "Per la part sud amb una parcel·la buida."
```

La sonda va cap al sud amb pas de 2m. El Carrer Antoni Bellet (estret, ~6m) pot no registrar-se com a `ref=None` a l'API Cadastre, o la sonda salta del nostre parcel-la directament a la parcel-la buida de l'altre costat.

**Causa tecnica**: `STEP = 2.0m`, `MAX_PROBES = 8`. Si el carrer es molt estret i l'API no retorna `None` per aquella coordenada, la sonda no detecta el carrer.

**Fix potencial**: Reduir STEP a 1m, o afegir deteccio especifica de carrers (Nominatim reverse a cada punt de sondatge).

### Fallada 2: Descripcions generiques vs observacions d'Eva

**Evidencia** (Castellar):
```
Pipeline: "parcel·la amb construccio aillada de fins a dos plantes sobre rasant"
Eva:      "parcel·la construida amb piscina"
Eva:      "parcel·les sense construir, amb herbes altes i arbres"
```

L'API Cadastre DNPRC nomes retorna:
- Nombre de plantes (sobre/sota rasant)
- Superficie construida
- Us principal (residencial/industrial/agricola)

No retorna: piscines, vegetacio, estat del terreny, multiples parcel-les per direccio.

**Causa**: Limitacio intrinseca de l'API Cadastre. Eva utilitza observacions visuals de camp o Google Earth/Street View.

**Fix potencial**: Integracio Street View/ortofoto ICGC (al roadmap com a projecte futur). Sense dades visuals, aquesta fallada es irresoluble.

### Fallada 3: Coordenades geocodificades vs DPSH

**Evidencia** (Bell-Lloc log):
```
Adjacents: using geocoded address (314499, 4611198) instead of DPSH coords (314419, 4611118)
```

Diferencia de ~80m entre coordenades geocodificades (de l'adreça) i DPSH (GPS de camp). Si les coordenades geocodificades cauen en una parcel-la veina, tots quatre adjacents seran erronis.

**Causa tecnica**: `auto_extractor.py:1298-1340` prefereix l'adreça geocodificada per sobre de les coordenades DPSH. La geocodificacio pot retornar qualsevol parcel-la del carrer, no necessariament la del projecte.

**Fix potencial**: Quan hi ha coordenades DPSH disponibles (camp GPS), usar-les directament ja que son mes precises.

### Fallada 4: Eva agrupa multiples elements per direccio

**Evidencia** (Castellar nord):
```
Eva: "parcel·les sense construir, amb herbes altes i arbres, 
      aixi com una parcel·la amb planta baixa i una planta pis, 
      paral·lela al carrer Turo Roig"
```

Eva descriu: parcel-les buides + un edifici + referencia a un carrer, tot en una sola direccio. El nostre sondatge s'atura al primer vei que troba.

**Causa tecnica**: `_probe_from_edge` retorna el primer resultat no-propi. No continua sondejant per trobar mes elements.

**Fix potencial**: Continuar sondejant despres del primer vei per detectar mes elements (carrer + segona fila de parcel-les). Complexitat mitja.

## Comparacio Eva vs Pipeline (exemplars)

### Bell-Lloc (4001612)
| Direccio | Eva | Pipeline | Problema |
|----------|-----|----------|---------|
| Nord | parcel-la buida | parcel-la buida | MATCH |
| Sud | Carrer Antoni Bellet | parcel-la buida | Carrer no detectat |
| Est | Carrer Mestre Ramon Ortiz | Carrer Mestre Ramon Ortiz | MATCH |
| Oest | construccio aillada 2 plantes | parcel-la amb construccio | Descripcio incompleta |

### Castellar (3001621)
| Direccio | Eva | Pipeline | Problema |
|----------|-----|----------|---------|
| Nord | parcel-les sense construir + edifici | parcel-la amb construccio | Descripcio massa simple |
| Sud | carrer Arbrells | Carrer dels Arbrells | CLOSE (article) |
| Est | parcel-la amb piscina | parcel-la amb construccio | Piscina invisible per API |
| Oest | parcel-les sense construir | parcel-la amb construccio | Parcel-la equivocada |

## Pla d'Accio Proposat

### Prioritat 1: Quick wins (facils, impacte mig)
1. **Preferir coordenades DPSH** quan disponibles — `auto_extractor.py` ja les te, nomes cal canviar la preferencia
2. **Millorar normalitzadors de text** — tractats "parcel-la amb construccio" vs "parcel-la construida" com CLOSE, no MISMATCH
3. **Reduir STEP a 1m** — detecta carrers mes estrets, cost: mes crides API (mitigat pel cache)

### Prioritat 2: Millores mitjanes
4. **Multi-sonda per aresta** — 3 punts per direccio en lloc de 1, detecta carrers en cantonades
5. **Continuar sondatge despres del primer vei** — detecta carrer + segona fila
6. **Validacio creuada** — comparar RC geocodificat amb RC de COORDENADES.txt o file_scanner

### Prioritat 3: Millores majors (roadmap)
7. **Integracio Street View** — descripcions visuals reals (ja al roadmap: `project_streetview_adjacents.md`)
8. **Ortofoto ICGC** — detectar piscines, vegetacio, terreny buit des d'imatge aeria
9. **LLM descriptiu** — donar dades Cadastre + ortofoto a un LLM per generar text estil Eva

## Estimacio d'Impacte

| Fix | De → A (estimat) | Variables afectades |
|-----|-------------------|---------------------|
| Coordenades DPSH | 8% → ~25% | ~5-8 adjacents que fallen per coordenades errònies |
| Normalitzadors text | 8% → ~20% | ~3-5 adjacents que son CLOSE pero marquen MISMATCH |
| STEP 1m + multi-sonda | ~25% → ~40% | ~3-5 carrers estrets no detectats |
| Street View/ortofoto | ~40% → ~75%+ | Descripcions riques estil Eva |

## Fitxers Rellevants

| Fitxer | Funcio | Linies clau |
|--------|--------|-------------|
| `automation/cadastre_adjacents.py` | Sondatge + deteccio veins | 823-978 (probing), 440-494 (describe), 499-607 (translate) |
| `automation/auto_extractor.py` | Fase 3 adjacents | 1267-1358 (address selection, geocode, call) |
| `automation/adjacent_formatter.py` | Formatatge frases | 28-120 (templates CA/ES) |
| `automation/geocode_coordinates.py` | Geocodificacio adreça→UTM | Usat per resolver coordenades |
| `automation/parcel_resolver.py` | Merge parcel-les | Usat quan sup_parcela > sup_cadastral |

## Notes

- Els 2 matches (nord Bell-Lloc + est Bell-Lloc) son coincidencies: "parcel-la buida" i "Carrer Mestre Ramon Ortiz" son facils de detectar.
- Les 4 variables `not_extracted` corresponen a Vilanova de Segria, on la geocodificacio va fallar completament (municipi no trobat).
- L'accuracy de Castellar (0%) es especialment dolenta perque Eva descriu elements visuals que l'API no pot retornar.
