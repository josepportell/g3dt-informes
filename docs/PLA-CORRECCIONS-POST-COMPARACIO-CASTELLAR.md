# Pla: Correccions post-comparacio Castellar + Abac Hoek & Bray

## Context

Despres de comparar l'informe generat de Castellar amb l'informe real de G3DT, s'han identificat 5 gaps. El mes impactant: el sistema tracta el terreny com a sol granular (c=0, phi=38) quan G3DT el classifica com a roca (c=1.0, phi=35, E>500). Aixo afecta en cascada: Qa, K30, i sobretot el FS del vessant (2.21 vs >3.5).

A mes, el metode de talus infinit es una simplificacio. G3DT usa l'abac n1 de Hoek & Bray (1977) per ruptura circular, que es digitalitzable.

## Canvis implementats (per prioritat)

### Fix 1: Sulfats = 0.0 rebutjat pel lab_extractor (1 linia)

**Problema:** `lab_extractor.py:130` te `if 0 < value < 100000:` que rebutja el valor 0.0 mg/kg. Castellar te sulfats = 0.0 -> el sistema diu "No s'han realitzat assaigs".

**Fitxer:** `automation/lab_extractor.py` linia 130
```python
# ABANS:
if 0 < value < 100000:
# DESPRES:
if 0 <= value < 100000:
```

### Fix 2: Rock detection sense descripcio a build_report_data() (~10 linies)

**Problema:** `build_report_data()` crida `is_rock(avg_n20)` SENSE descripcio. Castellar avg_n20=38 (< 100) -> no detecta roca. Pero `is_rock(38, "bretxes amb intercalacions...")` retornaria True perque "bretxes" i "gresos" son keywords de roca.

**Fitxer:** `automation/report_data.py` ~ linia 373

Canviar la deteccio de roca per incloure la descripcio disponible de les capes del sondeig o la unitat ICGC:

```python
# Construir description per a rock detection
rock_description = ""
sondeig_layers = user_data.get('sondeig_layers', [])
if sondeig_layers:
    rock_description = " ".join(l.get('description', '') for l in sondeig_layers)
if not rock_description:
    rock_description = user_data.get('icgc_unit_description', '')

if geomech.get('gamma') or geomech.get('phi') or geomech.get('E'):
    # PATH 1: Manual override (sense canvi)
    ...
elif is_rock(avg_n20, rock_description):
    # PATH 2: Rock detection AMB descripcio
    ...
```

**Efecte Castellar:** `is_rock(38, "Conglomerats heterometrics")` -> "conglomerat" es keyword -> True -> usa `rock_params_default()` -> c=1.0, phi=35, gamma=2.20, E=500. Exactament igual que l'informe real.

### Fix 3: §4.2 -- Afegir recomanacio de drenatge per terrenys amb pendent (~5 linies)

**Problema:** L'informe real diu "es recomana dimensionar una correcta xarxa de recollida d'aigues" per terrenys amb pendent. El generat no ho menciona.

**Fitxer:** `automation/sections/section4_conclusions.py` metode `generate_water_statement()`

Afegir al final del paragraf d'hidrogeologia, si `is_sloped`:
```
Amb tot, donada la pendent de la zona, es recomana dimensionar una correcta
xarxa de recollida d'aigues per a que no circuli lliurement damunt de la
superficie del solar.
```

### Fix 4: Implementar abac Hoek & Bray (Chart n1) -- NOU MODUL

**Que es l'abac n1:** Grafic per ruptura circular en talussos secs (Hoek & Bray, 1977/1981).

**Eixos:**
- X: `c / (gamma*H*F)` -- cohesio normalitzada
- Y: `tan(phi) / F` -- fregament normalitzat
- Corbes: angles de talus beta (10 a 90)

**5 abacs** per diferents saturacions: 0% (sec), 25%, 50%, 75%, 100%.

**Diferencia vs talus infinit:**

| Aspecte | Talus infinit (actual) | Hoek & Bray circular |
|---------|----------------------|---------------------|
| Superficie de ruptura | Plana | Circular |
| Efecte de l'alcada H | No en depen | Si (via c/gammaH) |
| Efecte de la cohesio | Lineal | No-lineal (mes fort) |
| Precisio amb roca (c>0) | Baixa | Alta |

**Per que importa:** Amb c=1.0 (roca), la formula del talus infinit subestima FS. L'abac de Hoek & Bray amb c=1.0, phi=35, H~4m, beta=20 dona FS>3.5, que coincideix amb l'informe real.

**Implementacio:** Modul `automation/hoek_bray.py` amb:
- Taula de Taylor stability numbers Ns(beta, phi) per ruptura circular
- Interpolacio bilineal entre punts de la taula
- Solver per biseccio per trobar FS
- Resultat dataclass HoekBrayResult

### Fix 5: Integrar Hoek & Bray a generate_estabilitat()

**Fitxer:** `automation/slope_calculator.py`

Actualitzar `calculate_slope_stability()` per:
1. Si `cohesion > 0` i `slope_height_m` disponible -> usar Hoek & Bray
2. Si `cohesion ~ 0` (granular) -> usar talus infinit (actual)
3. Fallback: talus infinit sempre

**Fitxer:** `automation/sections/section4_conclusions.py`

Actualitzar `_format_estabilitat_calculated()` per mostrar:
- Referencia a l'abac usat ("abac n1, talus sec")
- Mencio de la condicio de saturacio escollida
- Si c>0: text del metode circular en comptes del talus infinit

### Fix 6: slope_height_m -- camp nou per a l'abac

**Problema:** L'abac Hoek & Bray requereix l'alcada del talus (H). Castellar te "plataforma de treball 4.0 metres respecte el carrer".

**Fitxer:** `automation/data_schema.py`
```python
'slope_height_m': FieldDefinition(
    field_type='float',
    required=False,
    description="Alcada del talus en metres (necessari per Hoek & Bray)",
    example="4.0"
),
```

**Fitxer:** `automation/report_data.py` -- afegir `slope_height_m: float | None = None`

**Auto-estimacio fallback:** Si no es proporciona, estimar de la diferencia d'elevacio entre punts UTM (dades DPSH), o usar un conservador H=5m.

## Fitxers modificats

| Fitxer | Canvi | Esforc |
|--------|-------|--------|
| `automation/lab_extractor.py` | Fix `0 <` -> `0 <=` | 1 linia |
| `automation/report_data.py` | Rock detection + description, +slope_height_m | ~15 linies |
| `automation/sections/section4_conclusions.py` | Drenatge §4.2 + Hoek & Bray text §4.5 | ~20 linies |
| `automation/hoek_bray.py` | **NOU** -- Taylor stability numbers + interpolacio + FS solver | ~200 linies |
| `automation/slope_calculator.py` | Integrar Hoek & Bray quan c>0 | ~20 linies |
| `automation/data_schema.py` | +slope_height_m | ~5 linies |
| `automation/test_data_schema.py` | Actualitzar tests | ~2 linies |

## Estrategia de digitalitzacio dels abacs

**Fase 1 (ara):** Digitalitzar Chart 1 (sec) -- cobreix Castellar i majoria de casos.
- Taula Taylor stability numbers per grid (beta, phi)
- Validar amb Castellar: c=1.0, phi=35, gamma=2.20, H=4m, beta=20 -> esperar FS>3.5

**Fase 2 (futur):** Charts 2-5 (saturats) -- quan aparegui un cas amb NF.

## Verificacio

1. `python3 -m automation.lab_extractor "reference-material/3001621 CASTELLAR DEL VALLES"` -> sulfats=0.0, no None
2. Regenerar Castellar -> §4.1: phi=35, c=1.0, E=500 (rock params)
3. Regenerar Castellar -> §4.2: mencio drenatge
4. Regenerar Castellar -> §4.5: metode Hoek & Bray abac n1, FS>3.5
5. Regenerar Bell-Lloc (pla) -> §4.5 NO apareix
6. `python3 -m automation.hoek_bray` -> tests unitaris de l'abac
