# Pla: Canonical Vision JSON Schemas + Normalizer

Data: 2026-03-15

## Context

Claude vision extraction (via `/g3dt-visio-projecte`) produeix noms de claus JSON no-deterministes entre execucions. Les dades SPT son el pitjor cas — hem vist `spt_results`, `spt_tests`, `spt_data`, `spt_test`, `document_metadata.spt_test`, tots amb noms de camps interns diferents (`blows` vs `blows_15_30_45_60`, `depth_from_m` vs `cota_from`, etc.).

El fix actual es whack-a-mole: afegir claus variant cada cop que una falla. Aquest pla ho fa robust.

## Estrategia: Defensa en dos fronts

1. **Endurir prompts** — afegir exemples JSON SPT explicits al skill perque Claude segueixi noms canonics ~99% del temps
2. **Normalitzar en lectura** — un normalitzador Python captura el 1% restant i qualsevol variant de backward-compat

## Schema SPT Canonic

### A `dpsh_extracted.json` (SPT fet al punt DPSH):
```json
"spt_in_dpsh": {
    "test_id": "SPT-1",
    "location": "P-3",
    "depth_from_m": 0.60,
    "depth_to_m": 1.20,
    "blows": [16, 20, 20, 24],
    "n_spt": 40,
    "confidence": 0.90
}
```
`null` si no hi ha SPT al DPSH.

### A `sondeig_extracted.json` (SPT al sondeig):
```json
"spt_results": [{
    "test_id": "SPT-1",
    "depth_from_m": 1.00,
    "depth_to_m": 1.60,
    "blows": [24, 14, 28, 30],
    "n_spt": 42,
    "confidence": 0.85
}]
```

## Canvis

### 1. Nou fitxer: `automation/vision_normalizer.py`

Dues funcions publiques:
- `load_dpsh_json(path)` — carrega + normalitza dpsh_extracted.json
- `load_sondeig_json(path)` — carrega + normalitza sondeig_extracted.json

Regles de normalitzacio:
- **DPSH SPT ubicacio**: check `spt_data`, `spt_test`, `document_metadata.spt_test` → mou a `spt_in_dpsh`
- **DPSH SPT camps**: `cota_from` → `depth_from_m`, `blows_15_30_45_60` → `blows`, `reference` → `location`, computa `n_spt` de `blows[1]+blows[2]` si falta
- **Sondeig SPT array**: `spt_tests` → `spt_results`
- **Sondeig SPT camps**: `test_name` → `test_id`, `blow_counts` → `blows`, computa `n_spt` si falta

### 2. Actualitzar consumidors (substituir json.load directe + fallbacks multi-clau)

| Fitxer | Funcio | Canvi |
|--------|--------|-------|
| `report_generator.py` | `_extract_spt_data()` | Usa normalitzador; elimina `_find_spt_in_dpsh()`, simplifica a acces per clau canonica |
| `report_generator.py` | `build_report_data()` | Usa `load_sondeig_json()` i `load_dpsh_json()` per capes sondeig + profunditats refus |
| `report_data.py` | `_detect_spt()` | Usa normalitzador; simplifica a comprovar `spt_in_dpsh` i `spt_results` |
| `sections/section2_treballs.py` | `generate_taula4_sondeig()` | Rep dades ja normalitzades d'upstream; usa `spt_results` |
| `wizard.py` | `_load_dpsh()`, `_load_sondeig()` | Usa normalitzador |

### 3. Actualitzar prompt del skill: `g3dt-visio-projecte.md`

- Afegir `spt_in_dpsh` a l'exemple de format dpsh_extracted.json (amb dades + "posa null si no hi ha SPT")
- Expandir `spt_results: []` al format sondeig per mostrar una entrada poblada
- Afegir regla d'extraccio al prompt DPSH: "Si el full de camp inclou un assaig SPT, extreu-lo a `spt_in_dpsh`"

### 4. Actualitzar prompts SDK: `validation/prompts.py`

- Afegir SPT a `DPSH_JSON_EXAMPLE`
- Expandir SPT a `SONDEIG_JSON_EXAMPLE`
- Replicar canvis del skill prompt per us futur via API

## Ordre d'implementacio

1. Crear `vision_normalizer.py` (autocontingut, sense deps)
2. Substituir json.load als consumidors pel normalitzador
3. Eliminar `_find_spt_in_dpsh()` i simplificar fallbacks multi-clau
4. Actualitzar prompt del skill (`g3dt-visio-projecte.md`)
5. Actualitzar prompts SDK (`prompts.py`)

## Verificacio

1. Unit test: `load_dpsh_json()` amb les 3 variants DPSH conegudes (Bell-Lloc old, Rubi run A, Rubi run B)
2. Unit test: `load_sondeig_json()` amb variants `spt_results` i `spt_tests`
3. End-to-end: generar informe per Bell-Lloc4 i Rubi1 des de paths de produccio → taula SPT poblada
4. Re-executar visio en un projecte amb `--force` per verificar millores del prompt

## Fitxers tocats

- `automation/vision_normalizer.py` — **NOU**
- `automation/report_generator.py` — simplificar extraccio SPT
- `automation/report_data.py` — simplificar `_detect_spt()`
- `automation/sections/section2_treballs.py` — menor (ja quasi OK)
- `automation/wizard.py` — usar normalitzador per carregues JSON
- `.claude/commands/g3dt-visio-projecte.md` — afegir SPT als exemples JSON
- `automation/validation/prompts.py` — afegir SPT als exemples JSON
