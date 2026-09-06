# Agregat mecànic — mesura d'informe `2026-09-06-informe-bloc2-base`

Informe generat (`ReportGenerator`, `reference-material/<projecte>` + `_user_data_prev.json`) vs informe signat (`_eva_truth/<slug>.json`), `scripts/compare_tables_vs_eva.py`, 11 taules. M = idèntica · C = propera · X = diferent · % = (M+C)/comparables. Variants: `8b` = or de taules + `geomech_params` manuals (rèplica Fase 8b); `calc` = or de taules SENSE `geomech_params` (cel·les de càlcul del codi); `t2` = lectura real `_reconsolida-2026-09-06-t2` sense `geomech_params`; `viab` = només via B (cap taula llegida, cap `geomech_params`).

## Titulars

| Projecte | 8b: M · C · X → % | calc: M · C · X → % | t2: M · C · X → % | viab: M · C · X → % |
|---|---|---|---|---|
| castellar | 39 · 12 · 14 → **78 %** | 42 · 13 · 10 → **85 %** | 42 · 13 · 10 → **85 %** | 29 · 10 · 26 → **60 %** |
| rubi | 37 · 8 · 10 → **82 %** | 38 · 8 · 9 → **84 %** | 39 · 7 · 9 → **84 %** | 30 · 4 · 21 → **62 %** |
| bell-lloc | 35 · 6 · 14 → **75 %** | 36 · 6 · 13 → **76 %** | 35 · 6 · 14 → **75 %** | 37 · 6 · 12 → **78 %** |
| **Total** | 111 · 26 · 38 → **78 %** | 116 · 27 · 32 → **82 %** | 116 · 26 · 33 → **81 %** | 96 · 20 · 59 → **66 %** |

## Per taula (M/C/X per variant)

### castellar

| taula | 8b | calc | t2 | viab |
|---|---|---|---|---|
| plantes | 2/2/2 | 2/2/2 | 2/2/2 | 2/1/3 |
| cte_edificacio | 3/0/1 | 3/0/1 | 3/0/1 | 3/0/1 |
| dpsh | 20/0/0 | 20/0/0 | 20/0/0 | 12/0/8 |
| sondeig | 4/0/1 | 4/0/1 | 4/0/1 | 3/0/2 |
| spt_ma | 4/0/1 | 4/0/1 | 4/0/1 | 0/0/5 |
| mostra_lab | 1/4/0 | 1/4/0 | 1/4/0 | 1/4/0 |
| soil_levels | 0/2/0 | 0/2/0 | 0/2/0 | 0/1/1 |
| permeabilitat | 1/1/1 | 1/1/1 | 1/1/1 | 1/0/2 |
| sulfats | 3/1/0 | 3/1/0 | 3/1/0 | 3/1/0 |
| sismica | 1/1/2 | 1/1/2 | 1/1/2 | 1/1/2 |
| geotecnica | 0/1/6 | 3/2/2 | 3/2/2 | 3/2/2 |

### rubi

| taula | 8b | calc | t2 | viab |
|---|---|---|---|---|
| plantes | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| cte_edificacio | 4/0/0 | 4/0/0 | 4/0/0 | 4/0/0 |
| dpsh | 14/0/1 | 14/0/1 | 15/0/0 | 9/0/6 |
| spt_ma | 4/1/0 | 4/1/0 | 4/0/1 | 3/0/2 |
| mostra_lab | 3/1/1 | 3/1/1 | 3/1/1 | 3/1/1 |
| soil_levels | 1/1/0 | 1/1/0 | 1/1/0 | 1/0/1 |
| permeabilitat | 1/2/0 | 1/2/0 | 1/2/0 | 1/1/1 |
| sulfats | 4/0/0 | 4/0/0 | 4/0/0 | 4/0/0 |
| sismica | 3/0/1 | 3/0/1 | 3/0/1 | 3/0/1 |
| geotecnica | 1/1/5 | 2/1/4 | 2/1/4 | 0/0/7 |

### bell-lloc

| taula | 8b | calc | t2 | viab |
|---|---|---|---|---|
| plantes | 3/0/3 | 3/0/3 | 3/0/3 | 3/0/3 |
| cte_edificacio | 2/0/2 | 2/0/2 | 2/0/2 | 2/0/2 |
| dpsh | 10/0/0 | 10/0/0 | 10/0/0 | 10/0/0 |
| sondeig | 4/0/1 | 4/0/1 | 4/0/1 | 5/0/0 |
| spt_ma | 3/0/2 | 3/0/2 | 2/2/1 | 3/0/2 |
| mostra_lab | 3/2/0 | 3/2/0 | 3/2/0 | 3/2/0 |
| soil_levels | 1/1/0 | 1/1/0 | 1/0/1 | 1/1/0 |
| permeabilitat | 1/2/0 | 1/2/0 | 1/1/1 | 1/2/0 |
| sulfats | 4/0/0 | 4/0/0 | 4/0/0 | 4/0/0 |
| sismica | 3/0/1 | 3/0/1 | 3/0/1 | 3/0/1 |
| geotecnica | 1/1/5 | 2/1/4 | 2/1/4 | 2/1/4 |

## Cel·les del bloc 2 que NO són MATCH (taules `geotecnica`, `soil_levels`, `sismica`, `spt_ma`, `sondeig`)

Per variant i projecte: `fila[col] ESTAT «generat» ↔ «Eva»`. Són les cel·les que P0 / P2a / P2b han de moure (o deixar quietes); després de cada peça, diff d'aquesta llista, no dels titulars.

### variant `8b`

**castellar** (14 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «1er nivell: Bretxes amb intercalacions de lutites i gresos»
- `geotecnica` 1r[1] **MISMATCH** «27-R» ↔ «17-R»
- `geotecnica` 1r[2] **MISMATCH** «22» ↔ «R»
- `geotecnica` 1r[3] **MISMATCH** «1.90» ↔ «2.20»
- `geotecnica` 1r[4] **MISMATCH** «0.05» ↔ «1.0»
- `geotecnica` 1r[5] **MISMATCH** «30°» ↔ «35º»
- `geotecnica` 1r[6] **MISMATCH** «114» ↔ «>500»
- `soil_levels` 1r[0] **CLOSE** «1er nivell.» ↔ «1er nivell»
- `soil_levels` 1r[1] **CLOSE** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.»
- `sismica` 1[1] **CLOSE** «Tipus III» ↔ «Tipus II»
- `sismica` 1[2] **MISMATCH** «1.60» ↔ «1.15*»
- `sismica` 1[3] **MISMATCH** «1.6» ↔ «1.3»
- `spt_ma` spt-1[4] **MISMATCH** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Limolites i bretxes»
- `sondeig` s-1[1] **MISMATCH** «-4.00» ↔ «-4.20»

**rubi** (9 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves i sorres. Carbonatat.» ↔ «1er nivell. Graves i sorres.»
- `geotecnica` 1r[1] **MISMATCH** «52-R» ↔ «47-R»
- `geotecnica` 1r[2] **MISMATCH** «43» ↔ «40»
- `geotecnica` 1r[4] **MISMATCH** «0.00» ↔ «0.05»
- `geotecnica` 1r[5] **MISMATCH** «37°» ↔ «39º»
- `geotecnica` 1r[6] **MISMATCH** «469» ↔ «450»
- `soil_levels` 1r[1] **CLOSE** «Graves i sorres. Carbonatat.» ↔ «Graves i sorres, carbonatades»
- `sismica` 1[2] **MISMATCH** «4.60» ↔ «4.55»
- `spt_ma` spt-1[4] **CLOSE** «Graves i sorres. Carbonatat. (Nivell 1)» ↔ «Graves i sorres»

**bell-lloc** (11 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares.» ↔ «1er nivell. Graves en matriu sorrenca»
- `geotecnica` 1r[1] **MISMATCH** «41» ↔ «25-R»
- `geotecnica` 1r[2] **MISMATCH** «34» ↔ «54»
- `geotecnica` 1r[4] **MISMATCH** «0.05» ↔ «0.0»
- `geotecnica` 1r[5] **MISMATCH** «35°» ↔ «38º»
- `geotecnica` 1r[6] **MISMATCH** «467» ↔ «650»
- `soil_levels` 1r[1] **CLOSE** «Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares» ↔ «Graves en matriu sorrenca carbonatades»
- `sismica` 1[2] **MISMATCH** «2.60» ↔ «2.45»
- `spt_ma` spt-1[3] **MISMATCH** «58» ↔ «54»
- `spt_ma` spt-1[4] **MISMATCH** «Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares» ↔ «Graves en matriu sorrenca»
- `sondeig` s-1[3] **MISMATCH** «1/0» ↔ «1/--»

### variant `calc`

**castellar** (11 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «1er nivell: Bretxes amb intercalacions de lutites i gresos»
- `geotecnica` 1r[1] **MISMATCH** «27-R» ↔ «17-R»
- `geotecnica` 1r[2] **MISMATCH** «22» ↔ «R»
- `geotecnica` 1r[6] **CLOSE** «500» ↔ «>500»
- `soil_levels` 1r[0] **CLOSE** «1er nivell.» ↔ «1er nivell»
- `soil_levels` 1r[1] **CLOSE** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.»
- `sismica` 1[1] **CLOSE** «Tipus III» ↔ «Tipus II»
- `sismica` 1[2] **MISMATCH** «1.60» ↔ «1.15*»
- `sismica` 1[3] **MISMATCH** «1.6» ↔ «1.3»
- `spt_ma` spt-1[4] **MISMATCH** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Limolites i bretxes»
- `sondeig` s-1[1] **MISMATCH** «-4.00» ↔ «-4.20»

**rubi** (8 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves i sorres. Carbonatat.» ↔ «1er nivell. Graves i sorres.»
- `geotecnica` 1r[1] **MISMATCH** «52-R» ↔ «47-R»
- `geotecnica` 1r[2] **MISMATCH** «43» ↔ «40»
- `geotecnica` 1r[4] **MISMATCH** «0.00» ↔ «0.05»
- `geotecnica` 1r[6] **MISMATCH** «469» ↔ «450»
- `soil_levels` 1r[1] **CLOSE** «Graves i sorres. Carbonatat.» ↔ «Graves i sorres, carbonatades»
- `sismica` 1[2] **MISMATCH** «4.60» ↔ «4.55»
- `spt_ma` spt-1[4] **CLOSE** «Graves i sorres. Carbonatat. (Nivell 1)» ↔ «Graves i sorres»

**bell-lloc** (10 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares.» ↔ «1er nivell. Graves en matriu sorrenca»
- `geotecnica` 1r[1] **MISMATCH** «41» ↔ «25-R»
- `geotecnica` 1r[2] **MISMATCH** «34» ↔ «54»
- `geotecnica` 1r[5] **MISMATCH** «37°» ↔ «38º»
- `geotecnica` 1r[6] **MISMATCH** «469» ↔ «650»
- `soil_levels` 1r[1] **CLOSE** «Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares» ↔ «Graves en matriu sorrenca carbonatades»
- `sismica` 1[2] **MISMATCH** «2.60» ↔ «2.45»
- `spt_ma` spt-1[3] **MISMATCH** «58» ↔ «54»
- `spt_ma` spt-1[4] **MISMATCH** «Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares» ↔ «Graves en matriu sorrenca»
- `sondeig` s-1[3] **MISMATCH** «1/0» ↔ «1/--»

### variant `t2`

**castellar** (11 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «1er nivell: Bretxes amb intercalacions de lutites i gresos»
- `geotecnica` 1r[1] **MISMATCH** «27-R» ↔ «17-R»
- `geotecnica` 1r[2] **MISMATCH** «22» ↔ «R»
- `geotecnica` 1r[6] **CLOSE** «500» ↔ «>500»
- `soil_levels` 1r[0] **CLOSE** «1er nivell.» ↔ «1er nivell»
- `soil_levels` 1r[1] **CLOSE** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.»
- `sismica` 1[1] **CLOSE** «Tipus III» ↔ «Tipus II»
- `sismica` 1[2] **MISMATCH** «1.60» ↔ «1.15*»
- `sismica` 1[3] **MISMATCH** «1.6» ↔ «1.3»
- `spt_ma` spt-1[4] **MISMATCH** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells. (NIVELL 1)» ↔ «Limolites i bretxes»
- `sondeig` s-1[1] **MISMATCH** «-4.00» ↔ «-4.20»

**rubi** (8 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves i sorres. Carbonatat.» ↔ «1er nivell. Graves i sorres.»
- `geotecnica` 1r[1] **MISMATCH** «52-R» ↔ «47-R»
- `geotecnica` 1r[2] **MISMATCH** «43» ↔ «40»
- `geotecnica` 1r[4] **MISMATCH** «0.00» ↔ «0.05»
- `geotecnica` 1r[6] **MISMATCH** «469» ↔ «450»
- `soil_levels` 1r[1] **CLOSE** «Graves i sorres. Carbonatat.» ↔ «Graves i sorres, carbonatades»
- `sismica` 1[2] **MISMATCH** «4.60» ↔ «4.55»
- `spt_ma` spt-1[4] **MISMATCH** «Sorres llimoses amb graves (classificació SUCS: SM, ASTM D 2487/06)» ↔ «Graves i sorres»

**bell-lloc** (11 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves amb sorres.» ↔ «1er nivell. Graves en matriu sorrenca»
- `geotecnica` 1r[1] **MISMATCH** «41» ↔ «25-R»
- `geotecnica` 1r[2] **MISMATCH** «34» ↔ «54»
- `geotecnica` 1r[5] **MISMATCH** «37°» ↔ «38º»
- `geotecnica` 1r[6] **MISMATCH** «469» ↔ «650»
- `soil_levels` 1r[1] **MISMATCH** «Graves amb sorres» ↔ «Graves en matriu sorrenca carbonatades»
- `sismica` 1[2] **MISMATCH** «2.60» ↔ «2.45»
- `spt_ma` fila0[0] **CLOSE** «SPT1 S1» ↔ «SPT-1»
- `spt_ma` fila0[3] **MISMATCH** «62» ↔ «54»
- `spt_ma` fila0[4] **CLOSE** «Grava amb matriu sorrenca» ↔ «Graves en matriu sorrenca»
- `sondeig` s-1[3] **MISMATCH** «1/0» ↔ «1/--»

### variant `viab`

**castellar** (16 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Roca / material dur (roca pochimada / fora pochimada).» ↔ «1er nivell: Bretxes amb intercalacions de lutites i gresos»
- `geotecnica` 1r[1] **MISMATCH** «27-R» ↔ «17-R»
- `geotecnica` 1r[2] **MISMATCH** «22» ↔ «R»
- `geotecnica` 1r[6] **CLOSE** «500» ↔ «>500»
- `soil_levels` 1r[0] **CLOSE** «1er nivell.» ↔ «1er nivell»
- `soil_levels` 1r[1] **MISMATCH** «Roca / material dur (roca pochimada / fora pochimada)» ↔ «Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.»
- `sismica` 1[1] **CLOSE** «Tipus III» ↔ «Tipus II»
- `sismica` 1[2] **MISMATCH** «1.60» ↔ «1.15*»
- `sismica` 1[3] **MISMATCH** «1.6» ↔ «1.3»
- `spt_ma` fila0[0] **MISMATCH** «» ↔ «SPT-1»
- `spt_ma` fila0[1] **MISMATCH** «» ↔ «S-1»
- `spt_ma` fila0[2] **MISMATCH** «» ↔ «-1.00 a -1.20»
- `spt_ma` fila0[3] **MISMATCH** «» ↔ «R»
- `spt_ma` fila0[4] **MISMATCH** «» ↔ «Limolites i bretxes»
- `sondeig` s-1[1] **MISMATCH** «+570.90» ↔ «-4.20»
- `sondeig` s-1[3] **MISMATCH** «0/--» ↔ «1/0»

**rubi** (11 cel·les no-MATCH)

- `geotecnica` 1r[0] **MISMATCH** «1er nivell. Gresos amb intercalacions de trams de lutites de color vermellós o gris i conglomerats polimíctics (Nivell 2).» ↔ «1er nivell. Graves i sorres.»
- `geotecnica` 1r[1] **MISMATCH** «52-R» ↔ «47-R»
- `geotecnica` 1r[2] **MISMATCH** «43» ↔ «40»
- `geotecnica` 1r[3] **MISMATCH** «2.20» ↔ «2.0»
- `geotecnica` 1r[4] **MISMATCH** «1.00» ↔ «0.05»
- `geotecnica` 1r[5] **MISMATCH** «35°» ↔ «39º»
- `geotecnica` 1r[6] **MISMATCH** «500» ↔ «450»
- `soil_levels` 1r[1] **MISMATCH** «Gresos amb intercalacions de trams de lutites de color vermellós o gris i conglomerats polimíctics (Nivell 2)» ↔ «Graves i sorres, carbonatades»
- `sismica` 1[2] **MISMATCH** «4.60» ↔ «4.55»
- `spt_ma` spt-1[3] **MISMATCH** «36» ↔ «40»
- `spt_ma` spt-1[4] **MISMATCH** «» ↔ «Graves i sorres»

**bell-lloc** (9 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves con arena carbonatada.» ↔ «1er nivell. Graves en matriu sorrenca»
- `geotecnica` 1r[1] **MISMATCH** «41» ↔ «25-R»
- `geotecnica` 1r[2] **MISMATCH** «34» ↔ «54»
- `geotecnica` 1r[5] **MISMATCH** «37°» ↔ «38º»
- `geotecnica` 1r[6] **MISMATCH** «469» ↔ «650»
- `soil_levels` 1r[1] **CLOSE** «Graves con arena carbonatada» ↔ «Graves en matriu sorrenca carbonatades»
- `sismica` 1[2] **MISMATCH** «2.60» ↔ «2.45»
- `spt_ma` spt-1[3] **MISMATCH** «58» ↔ «54»
- `spt_ma` spt-1[4] **MISMATCH** «Graves con arena carbonatada» ↔ «Graves en matriu sorrenca»

## Avisos del generador


