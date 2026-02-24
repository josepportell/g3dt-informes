# Sessió 2026-02-24 — Fase 2: Afinament d'Informes

## Resum

Primer cicle iteratiu de la Fase 2. Partint d'un informe generat amb ~60% de coincidència amb la referència G3DT (Castellar del Vallès), hem implementat 3 fixes que milloren substancialment la generació automàtica.

## Fixes implementats

### Fix 1: Normalització d'accents a `determine_region()` [CRÍTIC]

**Problema:** `parse_folder_name("3001621 CASTELLAR DEL VALLES")` produïa "Castellar Del Valles" (sense accent). El `REGION_MAPPING` conté "Castellar del Vallès" (amb accent). La comparació fallava → regió equivocada → tota la geologia de §3 incorrecta.

**Solució:** Afegit `_strip_accents()` amb `unicodedata.normalize('NFKD')` a `icgc_geology.py`. Normalitza accents tant del municipi d'entrada com dels de la llista.

**Impacte:** §3.1 ara mostra "fossa tectònica del Vallès-Penedès" (correcte) i §3.2 "coloracions marrons a vermelloses, composició silícia".

**Fitxer:** `automation/icgc_geology.py`
**Commit:** `f722f0a`

### Fix 2: Override manual de la unitat ICGC [CRÍTIC]

**Problema:** L'API ICGC WMS només ofereix la capa 1:50.000 (retorna PEcg). G3DT usa el mapa 1:25.000 manualment (que donaria ECbc o Tm2). La capa 25k existeix com a vector tiles (no WMS), amb cobertura parcial del 49%.

**Investigació:**
- WMS: Només 50k i 250k. No hi ha `unitats-geologiques-25000`.
- Vector tiles: `https://geoserveis.icgc.cat/servei/catalunya/infogeo/vt/{z}/{x}/{y}.pbf`
- Per Castellar: 50k=PEcg, 25k=Tm2 (Lutites i gresos vermells, Triàsic)

**Solució:** Camps `icgc_unit_code`, `icgc_unit_description`, `icgc_unit_epoch` a `user_data.json`. Si presents, s'usen en comptes de la query WMS. Si absents, funciona com abans.

```json
{
  "icgc_unit_code": "ECbc",
  "icgc_unit_description": "Bretxes calcàries amb intercalacions de lutites",
  "icgc_unit_epoch": "Eocè"
}
```

**Pendent futur:** Integració automàtica amb vector tiles ICGC 25k.

**Fitxers:** `automation/report_data.py`, `automation/sections/section3_geologia.py`
**Commit:** `f722f0a`

### Fix 4: Correlacions CTE DB SE-C + override manual de paràmetres geomecànics [CRÍTIC]

**Problema:** El pipeline usava correlacions Peck/Hanson (dissenyades per sorres). Castellar té roca (bretxes) → paràmetres completament equivocats.

**Solució en 3 capes:**

1. **Mòdul `cte_geomech.py`** — Taules del CTE DB SE-C digitalitzades:
   - Taula D.23: NSPT → E (mòdul deformació)
   - Taula D.27: tipus sòl → γ (densitat) i φ (angle fricció)
   - Taula D.28: tipus sòl → K (permeabilitat)
   - Taula 4.1: NSPT → φ (granulars, interpolació lineal)
   - Font: `https://www.codigotecnico.org/pdf/Documentos/SE/DBSE-C.pdf`

2. **Detecció automàtica de roca** — Si NSPT ≥ 100 (refús) o la litologia conté keywords (roca, bretxes, gres, substrat...) → aplica paràmetres de roca CTE.

3. **Override manual** via `user_data.json → geomech_params`:
```json
{
  "geomech_params": {
    "gamma": 2.20,
    "cohesion": 1.0,
    "phi": 35,
    "E": 500,
    "Nb": "17-R",
    "N": "R"
  }
}
```

**Cadena de prioritat:** override manual > detecció roca CTE > correlacions CTE > Peck/Hanson (fallback)

**Comparativa per Castellar (N=38):**

| Paràmetre | Peck/Hanson | CTE auto | CTE roca | Override | G3DT Ref |
|-----------|-------------|----------|----------|----------|----------|
| γ (g/cm³) | 2.10 | 2.17 | 2.20 | 2.20 | 2.20 |
| c (kg/cm²) | 0.00 | 0.00 | 1.00 | 1.00 | 1.0 |
| φ (°) | 38 | 38 | 35 | 35 | 35 |
| E (kg/cm²) | 381 | 729 | 500 | 500 | >500 |

**Fitxers:** `automation/cte_geomech.py` (nou), `automation/report_data.py`, `automation/report_generator.py`
**Commit:** `36b7db8`

### Fix 5: Cota relativa vs absoluta [SIGNIFICATIU]

**Problema:** El pipeline usava cota absoluta ICGC MDT (+569.50 msnm). G3DT a vegades usa cota relativa al carrer (-4.0 m).

**Anàlisi:** El mecanisme ja existia — `user_data.cota_referencia` té prioritat sobre l'auto-fill ICGC. Només faltava:
1. Clarificar al schema que accepta tant valors absoluts com relatius
2. Afegir el camp al wizard perquè G3DT el pugui omplir fàcilment

**Solució:**
- Actualitzat `user_data_schema.json`: descripció clarifica format (abs: +569.50, rel: -4.0, buit=ICGC)
- Afegit camp `cota_referencia` al wizard (camp 15)

**Fitxers:** `automation/user_data_schema.json`, `automation/wizard.py`

### Fix 6: §4.4/§4.5 no generades [SIGNIFICATIU]

**Problema:** Les seccions existien al codi però no s'activaven:
- §4.4 Empentes: requereix `has_retaining_walls=True` o `has_basement=True` → camps no al wizard
- §4.5 Estabilitat: requereix `is_sloped=True` → la detecció ICGC MDT no alimentava el flag

**Solució:**
1. **§4.5 auto-activació**: Si `get_slope()` ICGC detecta pendent > 15%, `include_slope_stability` s'activa automàticament a `report_generator.py`
2. **§4.4 camps al wizard**: Afegits `has_basement` (camp 16) i `has_retaining_walls` (camp 17) al wizard

**Fitxers:** `automation/report_generator.py`, `automation/wizard.py`

### Fix 7: CTE C-0 vs C-1 [SIGNIFICATIU]

**Problema:** Sense `num_floors` ni `superficie_construida_m2`, el classificador CTE assumia C-0 (mínim).

**Solució:** Afegits `num_floors` (camp 4) i `superficie_construida_m2` (camp 5) al wizard. Amb aquestes dades, `classify_building()` classifica correctament.

**Fitxers:** `automation/wizard.py`

### Fix 8: Dades client buides [MENOR]

**Problema:** El wizard no recollia totes les dades del projecte.

**Solució:** Integrat dins els fixes 5-7 — el wizard ara té 17 camps regulars + overrides experts opcionals (ICGC unit, geomech params). Camps nous: `num_floors`, `superficie_construida_m2`, `cota_referencia`, `has_basement`, `has_retaining_walls`.

**Fitxers:** `automation/wizard.py`, `automation/user_data_schema.json`

### Expert Overrides al wizard [NOU]

**Secció opcional** que pregunta "Afegir overrides?" (default: no). Si sí:
- **ICGC unit**: codi, descripció, època (camps 18-20) — bypass de la query WMS 50k
- **Geomech params**: γ, c, φ, E (camps 21-24) — bypass del càlcul CTE automàtic

Prefills es carreguen de `user_data.json` anterior si existeixen.

**Fitxers:** `automation/wizard.py`

## Infraestructura creada

- `proves-fase2/` — Carpeta amb subcarpetes per als 4 projectes de prova
- `proves-fase2/README.md` — Metodologia del cicle iteratiu
- `proves-fase2/3001621-castellar/run-001_2026-02-24.md` — Anàlisi comparativa inicial (~60-65%)
- `proves-fase2/3001621-castellar/run-002_2026-02-24.md` — Després de Fix 1 (~70-75%)
- `docs/PLA-FASE2-AFINAMENT-INFORMES.md` — Pla complet amb 9 fixes

## Fonts normatives guardades

- **CTE DB SE-C** (Cimientos): `https://www.codigotecnico.org/pdf/Documentos/SE/DBSE-C.pdf`
  - Taules implementades: D.23, D.27, D.28, 4.1
  - Taules pendents de revisar: D.25 (pressions admissibles), D.26 (densitats sat/sec), D.29 (K30), D.9 (classificació roca), D.24 (Poisson)
  - Tot digitalitzat a `automation/cte_geomech.py`

## Fixes pendents (per ordre del pla)

| # | Fix | Tipus | Estat |
|---|-----|-------|-------|
| 1 | Accents `determine_region()` | CRÍTIC | RESOLT |
| 2 | ICGC 25k override | CRÍTIC | RESOLT |
| 3 | Plantilla materials | CRÍTIC | RESOLT (cascada Fix 1) |
| 4 | Paràmetres geomecànics | CRÍTIC | RESOLT |
| 5 | Cota relativa vs absoluta | SIGNIFICATIU | RESOLT |
| 6 | §4.4/§4.5 no generades | SIGNIFICATIU | RESOLT |
| 7 | CTE C-0 vs C-1 | SIGNIFICATIU | RESOLT |
| 8 | Dades client buides | MENOR | RESOLT (integrat al wizard) |
| 9 | SPT i sulfats | MENOR | Pendent |
