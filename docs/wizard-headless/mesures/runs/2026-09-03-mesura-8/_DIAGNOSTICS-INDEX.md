# Mesura dels 8 — índex de diagnòstics per projecte (per contrastar-los quan els 8 estiguin fets)

Criteris: `../../CRITERIS-MESURA-2026-09-03.md`. Cada projecte té `_NOTES.md` (números i veredicte) i, quan s'ha fet,
un diagnòstic de causes arrel de tot el que no és OK. **Sempre contrastar els ALERTA/CAUTELA amb el signat**
(`docs/golden-read-taules/_eva_truth/{slug}.json`) abans de comptar-los: l'or de lectura pot ser més cautelós
(esborranys) o menys anotat (`fora_carpeta`) que la veritat.

## Taxonomia de causes (creix amb cada projecte)

| Codi | Causa | On es corregeix |
|---|---|---|
| **R1** | Mateixa entitat, formes diferents, tractades com a contradicció (abreviatures G3, persona/despatx, raó social curta/llarga, grafies de municipi) | `consolidate.value_key` / `cluster_signals` |
| **R2** | Un concepte veí entra com a bloquejador (data del sondeig a `field_date`, datum relatiu / z GPS a `cota_referencia`) | `decide()` per camp; les notes del lector ja ho diuen |
| **R3** | Guard `"1 de"` de `num_floors` per substring («P1 de 86 m2») | `_guard_for_field.num_floors` (regex) |
| **R4** | `_NEVER_SEGUR_FIELDS` (`cte_*`) aplicat també quan el pressupost imprimeix la línia CTE | `consolidate.py:82` + pregunta a Eva (T del pressupost = T de l'informe?) |
| **R5** | Convergència inassolible amb lectors humils (5 docs coincidents, cap ≥ 0,8, 2 ≥ 0,6) | llindars `CONV_*` / autoritat del tall per nivells |
| **F1** | Font d'Eva inconsistent amb ella mateixa (comanda 1,4 vs GTL 1,2; annex p.2 +212 vs +212,50) | regla «qui mana» del skill al consolidador; coherència entre files |
| **D1** | Cadastre només «als forats»: un valor del tipus equivocat (Polígon/Parcel·la) tapa el forat de la RC; i a l'inrevés, una RC declarada d'una sola font no es creua amb el Cadastre | `consolidate.py` ~1788 (gate per format de RC) |
| **D2** | **Bug de dates al consolidador**: una data sense dia («Octubre 2025») fa de pont transitiu entre dies diferents (`keys_compatible` + union-find), el representant es tria per `len(str(k))` i `_iso_date` sobreescriu el valor del candidat 0 → una lectura de conf 0,35 surt «segur» (Linyola `field_date` 10/10 per 01/10) | `consolidate.py` l. 266-275, 364, 502-506 |
| **L1** | Forat de lector: el full SPT manuscrit (PENETROS p.3) no emet `n30` | skill / lector de PENETROS |
| **C** | Comparador: `close()` text («en el» vs «de l'»), `norm_floors` (porxada/porxo), candidats de `cte` compartits entre subclaus | `compare_consolida.py` |
| **G** | Or: sense `fora_carpeta` (Rubí superfície), utm S-1 en lloc de P-1 (Castellar, corregit), candidats per esborranys (Rubí) | `docs/golden-read*/` |

## Projectes

| # | Projecte | Notes | Diagnòstic | ERR sistema | Causes vistes |
|---|---|---|---|---|---|
| 1 | Castellar | `castellar/_NOTES.md` | — (14/5/2/1; els 5 CAUTELA classificats només per la `rule`, sense doc propi) | 0 | R1 ×2 (`building_type` abreviatures G3; `street_address` formes amb/sense municipi, mateixos portals), R5 (`num_floors`: 1 sola font, pressupost), F1 (`lab_sample_id`: annex «SPT-1» vs GTL «MA1 S1»; or = MA-1), C (`cte_sol`: or nul, candidats compartits), G (utm S-1→P-1, corregit) |
| 2 | Bell-lloc | `bell-lloc/_NOTES.md` | `bell-lloc/_DIAGNOSTIC-INFRACONFIANCA.md` | 0 | R1 ×4, R2 ×2, R3, R4 ×2, R5 |
| 3 | Rubí | `rubi/_NOTES.md` | `rubi/_DIAGNOSTIC.md` | **1** (cota P-2, F1) | R1, R4 ×2, R5, F1 ×2, D1, C ×2, G ×2 |
| 4 | Linyola | `linyola/_NOTES.md` | `linyola/_DIAGNOSTIC.md` | **1** (`field_date`, **D2 bug**) | D2, R1 ×4 (`building_type`, `architect_name` persona/despatx, `lab_location`, `street_address`), R2 ×2 (z GPS a cota; msnm vs fondària als nivells), R5 ×2 (RC i superfície del projecte de l'arquitecte, font única), F1 ×2 (`lab_depth` camp vs lab; errata «argilsoso»), C ×3, G (or persona vs signat despatx), L1 (`n30`) |
| 5 | Alcoletge | | | | |
| 6 | Vilanova | | | | (circular: només consistència) |
| 7 | Anciles | | | | |
| 8 | Tulipa | | | | (sense veritat: executabilitat + latència) |

## Recompte transversal (actualitzar a cada projecte)

| Causa | Castellar | Bell-lloc | Rubí | Linyola | Total |
|---|---|---|---|---|---|
| R1 | 2 | 4 | 1 (+1 eix via, per disseny) | 4 | 11 |
| R2 | 0 | 2 | 0 | 2 | 4 |
| R3 | 0 (legítim) | 1 | 0 | 0 | 1 |
| R4 | 0 (derivat) | 2 | 2 | 0 (sense línia CTE) | 4 |
| R5 | 1 | 1 | 1 | 2 | 5 |
| F1 | 1 | 0 | 2 | 2 | 5 |
| D1 | 0 | 0 | 1 | (1, cara inversa) | 1 |
| D2 | 0 | 0 | 0 | **1 (ERR)** | 1 |
| L1 | 0 | 0 | 0 | 1 | 1 |

**ERR de sistema acumulat (4/8): 2** — Rubí cota P-2 (F1, font d'Eva) i Linyola `field_date` (D2, bug).
