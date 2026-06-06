# Anàlisi — Bug #2: el report col·lapsa els nivells geològics a 1

**Data:** 2026-06-06 · **Branca:** `production/g3dt-eva-v1` · **Estat:** anàlisi tancada, implementació pendent d'aprovació.

> Document de descoberta + disseny de la correcció. Conservat perquè el "per què"
> del codi actual i el raonament del fix no es perdin (i per poder ajustar-lo si cal).
> ⚠ Eva NO corre `experiment/ai-pipeline` (experiment v2 congelat); corre prod amb
> `G3DT_ENABLE_AI_PIPELINE=false`, però SÍ usa visió via API → el normalitzador i
> `_generate_soil_levels` s'exerciten igualment.

---

## 1. Símptoma

Eva: l'automatització detecta **menys nivells geològics dels reals** ("1 quan n'hi ha 2/3"), a **tots els projectes**. Cas testimoni: `3001706 C.TULIPA CERDANYOLA` (2 cases, 4 DPSH + 1 sondeig). Veritat-terreny (tall de correlació de l'annex): **3 nivells** — Nivell 1 sorres llimoses, Nivell 2 llims argilosos, Nivell 3 substrat alterat.

## 2. Dos bugs encadenats (no confondre'ls)

| | Bug #1 (RESOLT) | Bug #2 (AQUEST DOC) |
|---|---|---|
| On | `vision_normalizer.py` + `wizard_service.py` | `report_data.py::_generate_soil_levels` |
| Què | Crash a cop de rebuig "50R" empassat per `except: pass` → annex descartat → `num_soil_levels` cau al default 1 | El report **col·lapsa a 1 nivell** encara que `num_soil_levels=3`, ignorant `geological_level` |
| Efecte | El **wizard** prefilla 1 en lloc de 3 | El **`.docx`** narra "1 nivell" i descriu només el ferm |
| Estat | Arreglat `7be711f`, desplegament dilluns 2026-06-08 | Documentat, implementació pendent |

El bug #2 es va descobrir **generant el `.docx`** amb el fix #1 ja aplicat: el wizard ja deia 3, però el report seguia dient 1. **Lliçó:** generar el `.docx` real és el test end-to-end definitiu d'un fix de nivells.

## 3. La funció afectada

`automation/report_data.py::_generate_soil_levels(dpsh_data, num_levels, sondeig_layers, soil_types)` (línies 1112-1218). `num_levels` = `user_data['num_soil_levels']`.

Estructura actual:
```python
if sondeig_layers and len(sondeig_layers) > 1:
    if num_levels < len(sondeig_layers):           # ← branca 1137 (el bug)
        # ... col·lapsa a EXACTAMENT 1 nivell fusionat ...
        return [SoilLevel(level_number=1, ...)]
    levels = []
    for i, layer in enumerate(sondeig_layers):     # ← un nivell per material
        ...
    return levels
# fallback (línia 1202): 1 nivell amb mitjana global
```

**L'assumpció de disseny heretada: «1 SoilLevel = 1 material del sondeig».** Tota la lògica gira sobre `len(sondeig_layers)` (nº de materials), i `num_soil_levels` només és un **interruptor binari**:
- `num_soil_levels >= len(sondeig_layers)` → un nivell per material.
- `num_soil_levels < len(sondeig_layers)` → **TOT col·lapsat a exactament 1**.

No existeix camí que doni un recompte **intermedi**.

## 4. Arqueologia: d'on ve la branca 1137

- **Commit `57c9bd3`** (2026-03-03, "fix(g3dt): audit critical bugs — dynamic geology, sondeig filter, material desc"). Bug original (Bell-Lloc, vegeu `docs/ANALISI-ERRORS-AUDIT-2026-03-02.md`):
  - Bell-Lloc té **2 materials** però Eva fa **1 sol nivell geològic**.
  - Codi *previ* (`baacdaa`): construïa 2 nivells i després `_merge_soil_levels` si `num_levels < len(levels)`. En fusionar, el Nivell 1 filtrava el N20 a la capa superficial (0–1.0m) → **perdia el ferm**: N20 **18.8** vs 36.7 real, c **1.6** vs 1.30 d'Eva, tipus sísmic III vs II.
  - **Fix**: sortida anticipada amb 1 nivell que usa **totes** les lectures + descripció de la capa **més profunda** (el ferm) + N20 de ferm via `_bearing_stratum_n20`.
- **Per què va "funcionar":** pur cas degenerat. Bell-Lloc volia 1 nivell, i col·lapsar SEMPRE dona 1. La heurística `num < len` era un *proxy* de "Eva vol menys nivells que materials → fusiona'ls tots a un".
- **`geological_level` mai s'ha llegit dins `report_data.py`** (`git log -S "geological_level" -- automation/report_data.py` → buit).

## 5. El defecte conceptual

La funció **confon dos conceptes diferents**:

| Concepte | Què és | Origen | Tulipa |
|---|---|---|---|
| `len(sondeig_layers)` | nº de **materials** (granular) | descripcions de capa | **5** |
| nº de **nivells geològics** | agrupació d'Eva | columna "Unitat litològica" → `geological_level` per capa | **3** (`1,1,2,3,3`) |

La funció tracta `len(sondeig_layers)` com si fos el nº de nivells geològics. Funciona quan **coincideixen** (1 material=1 nivell, o cada material el seu nivell). Falla quan **diversos materials comparteixen nivell** (Tulipa: 5 materials → 3 nivells): `num_soil_levels=3 < 5` → dispara col·lapse-a-1.

Criteri canònic d'Eva (confirmat 2026-03-13): **els nivells surten de la columna "Unitat litològica" de l'annex formatat, no del nombre de materials.**

## 6. Hi ha DOS camins a "1 nivell" (no confondre)

1. **`merge_to_single_level`** (`report_data.py:521`) — camí **PREVIST i explícit**. Eva marca que vol fusionar → el caller crida `_merge_soil_levels` sobre el resultat. **Correcte, no es toca.**
2. **Branca 1137** — camí **IMPLÍCIT** que es dispara sol sempre que `num < len`. **Aquest és el bug #2.**

## 7. Traça de dades completa (verificada)

### `sondeig_layers` (els dicts de capa) — `report_data.py:423-440`
```python
sondeig_layers = user_data.get('sondeig_layers') or []          # 1r: wizard/user_data
if not sondeig_layers and project_path:                          # 2n: annex
    sdata = load_sondeig_merged(Path(project_path)/'validation')
    sondeig_layers = sdata['sondeig_tests'][0]['layers']
if not sondeig_layers:                                           # 3r: sintètic
    sondeig_layers = segment_by_n20_step(dpsh_data)              #     (NO té geological_level)
```
Cada dict de capa conté: `depth_from_m`, `depth_to_m`, `description`, **`geological_level`** (int, de "Unitat litològica"), i opcionals (`uscs_classification`, `color`, ...). Les capes es passen **en brut** → `geological_level` HI ÉS PRESENT; simplement no es llegeix. **Excepció:** `segment_by_n20_step` (sintètic des de DPSH) i fulls de camp sense columna "Unitat litològica" → **no** tenen `geological_level`.

### `num_soil_levels` — `report_generator.py:312-323`, `wizard.py:211-224`
```python
geo_levels = sondeig_tests[0].get('num_geological_levels')   # de l'annex
num_levels = geo_levels if geo_levels is not None else len(layers)
user_data.setdefault('num_soil_levels', num_levels)
```
Precedència: (1) valor d'Eva al wizard → (2) `num_geological_levels` de l'annex → (3) `len(layers)` → (4) default 1.

> **Clau:** en el pipeline normal, `num_soil_levels` ja s'omple de `num_geological_levels`, que ve de la **MATEIXA columna** que dona els `geological_level` per capa. Per tant **el recompte correcte JA és a `num_soil_levels`**; l'únic error és que `_generate_soil_levels` el compara contra `len(sondeig_layers)` (materials) en lloc d'**agrupar per `geological_level`**.

### `geological_level` — schema `automation/validation/prompts.py:172-173, 245`
"For each layer, set `geological_level` to the NIVELL number from the «Unitat litològica» column; set `num_geological_levels` to the count of DISTINCT values." L'annex (`load_sondeig_merged`, `vision_normalizer.py:411-430`) és autoritatiu per `num_geological_levels`.

### Narració del recompte — usa `len(soil_levels)`
- `sections/section3_geologia.py:704-710`: `num_levels = len(self.data.soil_levels)`.
- `sections/section4_conclusions.py:126-153`: `len(soil_levels)==1` → "un únic nivell geotècnic"; si no, "s'han identificat {N} nivells geotècnics diferenciats".

## 8. Conclusió de l'anàlisi

No és un bug de càlcul: és un **bug conceptual heretat**. La funció va néixer assumint «1 material = 1 nivell» i la branca 1137 va ser un pedaç per al cas degenerat de Bell-Lloc que casualment només sap produir 1. La correcció natural: **agrupar `sondeig_layers` per `geological_level`** (1 SoilLevel per grup), amb fallback a la lògica actual quan el camp no hi és.

---

## 9. La correcció proposada

### 9.1 Decisió de disseny (confirmada amb Josep — **Opció A**)

`geological_level` és la veritat-terreny del recompte. `num_soil_levels` només actua com a override **a la baixa**:
```
n_grups = runs consecutius de geological_level       # Tulipa [1,1],[2],[3,3] → 3
if merge_to_single_level:            -> 1            # ja ho fa el caller (línia 521)
elif num_soil_levels < n_grups  or  n_grups == 1: -> 1
else:                                -> 1 SoilLevel per grup   # ex: 3
```

**Opcions rebutjades (per si cal reconsiderar):**
- **B — `num_soil_levels` sempre mana com a objectiu exacte** (fusiona/divideix grups fins a N): fusionar grups geològics arbitraris és ambigu i, en el pipeline normal, `num_soil_levels` ja == n_grups (només divergeixen si Eva sobreescriu). Més complexitat sense guany.
- **C — ignorar del tot `num_soil_levels` al recompte**: Eva perdria l'override de col·lapsar a 1.

### 9.2 Canvi 1 — helper d'agrupació (`report_data.py`)
```python
def _group_layers_by_geological_level(sondeig_layers: list[dict]) -> list[list[int]] | None:
    """Agrupa ÍNDEXS de capa per runs consecutius de 'geological_level'.
    [1,1,2,3,3] -> [[0,1],[2],[3,4]].  Retorna None si el camp falta/és None a
    QUALSEVOL capa (el caller cau a la lògica actual)."""
```
- Runs **consecutius** (els nivells són ordenats per profunditat).
- Índexs **globals** → per mapejar `soil_types[i]`.
- `None` si algun `geological_level` és absent/None (cas sintètic o full sense columna).

### 9.3 Canvi 2 — usar grups dins `_generate_soil_levels`

Dins el bloc existent `if sondeig_layers and len(sondeig_layers) > 1:`:
```python
groups = _group_layers_by_geological_level(sondeig_layers)
if groups is not None:
    n_groups = len(groups)
    if num_levels < n_groups or n_groups == 1:
        <REUTILITZA el bloc de col·lapse actual (1137-1163) TAL QUAL>
    levels = []
    for gi, idxs in enumerate(groups):
        is_last = gi == n_groups - 1
        first, last = sondeig_layers[idxs[0]], sondeig_layers[idxs[-1]]
        depth_from   = first.get('depth_from_m', 0.0)
        depth_to     = last.get('depth_to_m', 0.0)
        bearing_from = last.get('depth_from_m', depth_from)   # ferm del grup = capa més profunda
        # N20 al sub-rang de ferm del grup; per a l'ÚLTIM grup treu el límit
        # superior (DPSH va més profund que el sondeig) — mateix principi que el
        # bloc de col·lapse / _bearing_stratum_n20
        layer_n20 = [r.n20 for r in all_readings
                     if abs(r.depth_m) >= bearing_from
                     and (is_last or abs(r.depth_m) <= depth_to)
                     and r.n20 < 100]
        avg = sum(layer_n20)/len(layer_n20) if layer_n20 else dpsh_data.overall_average_n20
        desc = last.get('description', f'Nivell {gi+1}')      # ferm = capa més profunda
        st = soil_types[idxs[-1]] if soil_types and idxs[-1] < len(soil_types) else detect_soil_type(desc)
        levels.append(SoilLevel(level_number=gi+1, description=desc,
                      thickness_m=(depth_to-depth_from) or None, n20_average=avg,
                      depth_from_m=depth_from, depth_to_m=depth_to or None,
                      n20_min=(min(layer_n20) if layer_n20 else None),
                      n20_max=(max(layer_n20) if layer_n20 else None), soil_type=st))
    return levels
# groups is None -> CAU a la lògica actual (branca 1137 + loop per-material), SENSE canvis
```

### 9.4 Per què aquest disseny minimitza regressions (anàlisi per projecte)

| Cas | `geological_level` | Resultat NOU | vs avui |
|---|---|---|---|
| **Bell-Lloc** (2 mat., tots `gl=1`) | `[1,1]` → 1 grup | `n_groups==1` → **reutilitza bloc de col·lapse actual** | **IDÈNTIC** (N20≈40, c=1.30) |
| **Tulipa** (5 mat.) | `[1,1,2,3,3]` → 3 grups | loop per-grup → **3 nivells** | bug resolt (era 1) |
| **Multi-material, gl tots distints** | `[1,2,3]` → grups mida 1 | equival al loop per-material; únic canvi: l'últim nivell treu límit superior (captura DPSH profund) | canvi menor a validar |
| **Sintètic / full sense columna** | absent | `groups=None` → **lògica actual intacta** | IDÈNTIC |
| **Override Eva a la baixa** | p.ex. 3 grups, `num_levels=1` | `1 < 3` → col·lapse a 1 | preserva control d'Eva |

> El truc anti-regressió: per al cas **1 grup** (Bell-Lloc i similars) **reutilitzem literalment el bloc de col·lapse ja validat** → sortida igual. Només els projectes amb `geological_level` realment multi-grup canvien (que és el que volem).

### 9.5 Tests — NOU `tests/test_soil_levels_grouping.py`
- `_group_layers_by_geological_level`: `[1,1,2,3,3]`→3; tot `gl=1`→1; algun `None`→`None`; defensa gl no-consecutiu.
- `_generate_soil_levels` estil-Tulipa (5 capes, gl `[1,1,2,3,3]`, `num_levels=3`) → **3 SoilLevels** amb desc/profunditat del ferm de cada grup.
- estil-Bell-Lloc (2 capes `gl=1`, `num_levels=1`) → **1 SoilLevel**, N20 de ferm (= avui).
- override `num_levels=1` amb 3 grups → 1 nivell.

---

## 10. Verificació (full fidelity, sense saltar fases)

1. **Suite completa:** `cd clients/g3dt-prod && .venv/bin/python -m pytest -q`, **timeout 10 min**. Base prod: **974 passed** + 31 fallades pre-existents (9 ai-pipeline 404, 18 smartscan fixtures, 3 fileminer, 1 bearing) idèntiques (`git stash` per comparar) → **0 regressions**.
2. **Tulipa end-to-end:** regenerar `.docx` des de `/mnt/c/claude/g3dt/projectes-debug/3001706 C.TULIPA CERDANYOLA` → ha de narrar **"3 nivells geotècnics diferenciats"** i descriure els 3.
3. **Gate de regressió (crític):** regenerar/comparar `soil_levels` dels 7 projectes de referència. **Bell-Lloc = 1 nivell, N20≈40, c=1.30 inalterats.** Cap altre projecte canvia el recompte tret que tingui de debò `geological_level` multi-grup.

## 11. Limitacions / fora d'abast
- **Misclassificació full de sondeig de camp** (Tulipa: Albarà vs full real) — gap separat, crític per a projectes sense annex formatat.
- **Annex amb `num_geological_levels` None** (Linyola: `[None,None,None]`) → `groups=None` → fallback actual. Gap d'extracció separat.
- **Regla canònica de Nb a rebuig** — blocker obert amb Eva, independent del recompte.
- Reconciliar amb Eva si Tulipa són 2 o 3 nivells (els docs diuen 3) — no canvia el fix.

---
*Anàlisi tancada 2026-06-06. Implementació pendent d'aprovació del Josep. Decisió de disseny: Opció A (geological_level = veritat-terreny del recompte; num_soil_levels override a la baixa).*
