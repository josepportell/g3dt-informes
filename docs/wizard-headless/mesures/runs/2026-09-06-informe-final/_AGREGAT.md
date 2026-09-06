# Agregat mecànic — mesura d'informe `2026-09-06-informe-final`

Informe generat (`ReportGenerator`, `reference-material/<projecte>` + `_user_data_prev.json`) vs informe signat (`_eva_truth/<slug>.json`), `scripts/compare_tables_vs_eva.py`, 11 taules. M = idèntica · C = propera · X = diferent · % = (M+C)/comparables. Variants: `8b` = or de taules + `geomech_params` manuals (rèplica Fase 8b); `calc` = or de taules SENSE `geomech_params` (cel·les de càlcul del codi); `t2` = lectura real `_reconsolida-2026-09-06-t2` sense `geomech_params`; `viab` = només via B (cap taula llegida, cap `geomech_params`).

## Titulars

| Projecte | 8b: M · C · X → % | calc: M · C · X → % | t2: M · C · X → % | viab: M · C · X → % |
|---|---|---|---|---|
| castellar | 42 · 11 · 12 → **82 %** | 46 · 11 · 8 → **88 %** | 46 · 11 · 8 → **88 %** | 32 · 8 · 25 → **62 %** |
| rubi | 38 · 8 · 9 → **84 %** | 40 · 8 · 7 → **87 %** | 41 · 7 · 7 → **87 %** | 33 · 7 · 15 → **73 %** |
| bell-lloc | 35 · 6 · 14 → **75 %** | 37 · 6 · 12 → **78 %** | 36 · 6 · 13 → **76 %** | 38 · 6 · 11 → **80 %** |
| **Total** | 115 · 25 · 35 → **80 %** | 123 · 25 · 27 → **85 %** | 123 · 24 · 28 → **84 %** | 103 · 21 · 51 → **71 %** |

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
| sismica | 3/0/1 | 3/0/1 | 3/0/1 | 3/0/1 |
| geotecnica | 1/1/5 | 5/1/1 | 5/1/1 | 4/1/2 |

### rubi

| taula | 8b | calc | t2 | viab |
|---|---|---|---|---|
| plantes | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| cte_edificacio | 4/0/0 | 4/0/0 | 4/0/0 | 4/0/0 |
| dpsh | 14/0/1 | 14/0/1 | 15/0/0 | 9/0/6 |
| spt_ma | 4/1/0 | 4/1/0 | 4/0/1 | 3/0/2 |
| mostra_lab | 3/1/1 | 3/1/1 | 3/1/1 | 3/1/1 |
| soil_levels | 1/1/0 | 1/1/0 | 1/1/0 | 1/1/0 |
| permeabilitat | 1/2/0 | 1/2/0 | 1/2/0 | 1/2/0 |
| sulfats | 4/0/0 | 4/0/0 | 4/0/0 | 4/0/0 |
| sismica | 3/0/1 | 3/0/1 | 3/0/1 | 3/0/1 |
| geotecnica | 2/1/4 | 4/1/2 | 4/1/2 | 3/1/3 |

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
| geotecnica | 1/1/5 | 3/1/3 | 3/1/3 | 3/1/3 |

## Cel·les del bloc 2 que NO són MATCH (taules `geotecnica`, `soil_levels`, `sismica`, `spt_ma`, `sondeig`)

Per variant i projecte: `fila[col] ESTAT «generat» ↔ «Eva»`. Són les cel·les que P0 / P2a / P2b han de moure (o deixar quietes); després de cada peça, diff d'aquesta llista, no dels titulars.

### variant `8b`

**castellar** (11 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «1er nivell: Bretxes amb intercalacions de lutites i gresos»
- `geotecnica` 1r[1] **MISMATCH** «27-R» ↔ «17-R»
- `geotecnica` 1r[3] **MISMATCH** «1.90» ↔ «2.20»
- `geotecnica` 1r[4] **MISMATCH** «0.05» ↔ «1.0»
- `geotecnica` 1r[5] **MISMATCH** «30°» ↔ «35º»
- `geotecnica` 1r[6] **MISMATCH** «114» ↔ «>500»
- `soil_levels` 1r[0] **CLOSE** «1er nivell.» ↔ «1er nivell»
- `soil_levels` 1r[1] **CLOSE** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.»
- `sismica` 1[2] **MISMATCH** «1.60» ↔ «1.15*»
- `spt_ma` spt-1[4] **MISMATCH** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Limolites i bretxes»
- `sondeig` s-1[1] **MISMATCH** «-4.00» ↔ «-4.20»

**rubi** (8 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves i sorres. Carbonatat.» ↔ «1er nivell. Graves i sorres.»
- `geotecnica` 1r[1] **MISMATCH** «42-R» ↔ «47-R»
- `geotecnica` 1r[4] **MISMATCH** «0.00» ↔ «0.05»
- `geotecnica` 1r[5] **MISMATCH** «37°» ↔ «39º»
- `geotecnica` 1r[6] **MISMATCH** «469» ↔ «450»
- `soil_levels` 1r[1] **CLOSE** «Graves i sorres. Carbonatat.» ↔ «Graves i sorres, carbonatades»
- `sismica` 1[2] **MISMATCH** «4.60» ↔ «4.55»
- `spt_ma` spt-1[4] **CLOSE** «Graves i sorres. Carbonatat. (Nivell 1)» ↔ «Graves i sorres»

**bell-lloc** (11 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares.» ↔ «1er nivell. Graves en matriu sorrenca»
- `geotecnica` 1r[1] **MISMATCH** «23-R» ↔ «25-R»
- `geotecnica` 1r[2] **MISMATCH** «58» ↔ «54»
- `geotecnica` 1r[4] **MISMATCH** «0.05» ↔ «0.0»
- `geotecnica` 1r[5] **MISMATCH** «35°» ↔ «38º»
- `geotecnica` 1r[6] **MISMATCH** «467» ↔ «650»
- `soil_levels` 1r[1] **CLOSE** «Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares» ↔ «Graves en matriu sorrenca carbonatades»
- `sismica` 1[2] **MISMATCH** «2.60» ↔ «2.45»
- `spt_ma` spt-1[3] **MISMATCH** «58» ↔ «54»
- `spt_ma` spt-1[4] **MISMATCH** «Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares» ↔ «Graves en matriu sorrenca»
- `sondeig` s-1[3] **MISMATCH** «1/0» ↔ «1/--»

### variant `calc`

**castellar** (7 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «1er nivell: Bretxes amb intercalacions de lutites i gresos»
- `geotecnica` 1r[1] **MISMATCH** «27-R» ↔ «17-R»
- `soil_levels` 1r[0] **CLOSE** «1er nivell.» ↔ «1er nivell»
- `soil_levels` 1r[1] **CLOSE** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.»
- `sismica` 1[2] **MISMATCH** «1.60» ↔ «1.15*»
- `spt_ma` spt-1[4] **MISMATCH** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Limolites i bretxes»
- `sondeig` s-1[1] **MISMATCH** «-4.00» ↔ «-4.20»

**rubi** (6 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves i sorres. Carbonatat.» ↔ «1er nivell. Graves i sorres.»
- `geotecnica` 1r[1] **MISMATCH** «42-R» ↔ «47-R»
- `geotecnica` 1r[4] **MISMATCH** «0.00» ↔ «0.05»
- `soil_levels` 1r[1] **CLOSE** «Graves i sorres. Carbonatat.» ↔ «Graves i sorres, carbonatades»
- `sismica` 1[2] **MISMATCH** «4.60» ↔ «4.55»
- `spt_ma` spt-1[4] **CLOSE** «Graves i sorres. Carbonatat. (Nivell 1)» ↔ «Graves i sorres»

**bell-lloc** (9 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares.» ↔ «1er nivell. Graves en matriu sorrenca»
- `geotecnica` 1r[1] **MISMATCH** «23-R» ↔ «25-R»
- `geotecnica` 1r[2] **MISMATCH** «58» ↔ «54»
- `geotecnica` 1r[6] **MISMATCH** «450» ↔ «650»
- `soil_levels` 1r[1] **CLOSE** «Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares» ↔ «Graves en matriu sorrenca carbonatades»
- `sismica` 1[2] **MISMATCH** «2.60» ↔ «2.45»
- `spt_ma` spt-1[3] **MISMATCH** «58» ↔ «54»
- `spt_ma` spt-1[4] **MISMATCH** «Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clares» ↔ «Graves en matriu sorrenca»
- `sondeig` s-1[3] **MISMATCH** «1/0» ↔ «1/--»

### variant `t2`

**castellar** (7 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «1er nivell: Bretxes amb intercalacions de lutites i gresos»
- `geotecnica` 1r[1] **MISMATCH** «27-R» ↔ «17-R»
- `soil_levels` 1r[0] **CLOSE** «1er nivell.» ↔ «1er nivell»
- `soil_levels` 1r[1] **CLOSE** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.» ↔ «Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.»
- `sismica` 1[2] **MISMATCH** «1.60» ↔ «1.15*»
- `spt_ma` spt-1[4] **MISMATCH** «Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells. (NIVELL 1)» ↔ «Limolites i bretxes»
- `sondeig` s-1[1] **MISMATCH** «-4.00» ↔ «-4.20»

**rubi** (6 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves i sorres. Carbonatat.» ↔ «1er nivell. Graves i sorres.»
- `geotecnica` 1r[1] **MISMATCH** «42-R» ↔ «47-R»
- `geotecnica` 1r[4] **MISMATCH** «0.00» ↔ «0.05»
- `soil_levels` 1r[1] **CLOSE** «Graves i sorres. Carbonatat.» ↔ «Graves i sorres, carbonatades»
- `sismica` 1[2] **MISMATCH** «4.60» ↔ «4.55»
- `spt_ma` spt-1[4] **MISMATCH** «Sorres llimoses amb graves (classificació SUCS: SM, ASTM D 2487/06)» ↔ «Graves i sorres»

**bell-lloc** (10 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves amb sorres.» ↔ «1er nivell. Graves en matriu sorrenca»
- `geotecnica` 1r[1] **MISMATCH** «23-R» ↔ «25-R»
- `geotecnica` 1r[2] **MISMATCH** «62» ↔ «54»
- `geotecnica` 1r[6] **MISMATCH** «450» ↔ «650»
- `soil_levels` 1r[1] **MISMATCH** «Graves amb sorres» ↔ «Graves en matriu sorrenca carbonatades»
- `sismica` 1[2] **MISMATCH** «2.60» ↔ «2.45»
- `spt_ma` fila0[0] **CLOSE** «SPT1 S1» ↔ «SPT-1»
- `spt_ma` fila0[3] **MISMATCH** «62» ↔ «54»
- `spt_ma` fila0[4] **CLOSE** «Grava amb matriu sorrenca» ↔ «Graves en matriu sorrenca»
- `sondeig` s-1[3] **MISMATCH** «1/0» ↔ «1/--»

### variant `viab`

**castellar** (13 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Roca / material dur (roca pochimada / fora pochimada).» ↔ «1er nivell: Bretxes amb intercalacions de lutites i gresos»
- `geotecnica` 1r[1] **MISMATCH** «27-R» ↔ «17-R»
- `geotecnica` 1r[2] **MISMATCH** «--» ↔ «R»
- `soil_levels` 1r[0] **CLOSE** «1er nivell.» ↔ «1er nivell»
- `soil_levels` 1r[1] **MISMATCH** «Roca / material dur (roca pochimada / fora pochimada)» ↔ «Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.»
- `sismica` 1[2] **MISMATCH** «1.60» ↔ «1.15*»
- `spt_ma` fila0[0] **MISMATCH** «» ↔ «SPT-1»
- `spt_ma` fila0[1] **MISMATCH** «» ↔ «S-1»
- `spt_ma` fila0[2] **MISMATCH** «» ↔ «-1.00 a -1.20»
- `spt_ma` fila0[3] **MISMATCH** «» ↔ «R»
- `spt_ma` fila0[4] **MISMATCH** «» ↔ «Limolites i bretxes»
- `sondeig` s-1[1] **MISMATCH** «+570.90» ↔ «-4.20»
- `sondeig` s-1[3] **MISMATCH** «0/--» ↔ «1/0»

**rubi** (8 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves i sorres (Nivell 1).» ↔ «1er nivell. Graves i sorres.»
- `geotecnica` 1r[1] **MISMATCH** «42-R» ↔ «47-R»
- `geotecnica` 1r[2] **MISMATCH** «36» ↔ «40»
- `geotecnica` 1r[4] **MISMATCH** «0.00» ↔ «0.05»
- `soil_levels` 1r[1] **CLOSE** «Graves i sorres (Nivell 1)» ↔ «Graves i sorres, carbonatades»
- `sismica` 1[2] **MISMATCH** «4.60» ↔ «4.55»
- `spt_ma` spt-1[3] **MISMATCH** «36» ↔ «40»
- `spt_ma` spt-1[4] **MISMATCH** «» ↔ «Graves i sorres»

**bell-lloc** (8 cel·les no-MATCH)

- `geotecnica` 1r[0] **CLOSE** «1er nivell. Graves carbonatades.» ↔ «1er nivell. Graves en matriu sorrenca»
- `geotecnica` 1r[1] **MISMATCH** «23-R» ↔ «25-R»
- `geotecnica` 1r[2] **MISMATCH** «58» ↔ «54»
- `geotecnica` 1r[6] **MISMATCH** «450» ↔ «650»
- `soil_levels` 1r[1] **CLOSE** «Graves carbonatades» ↔ «Graves en matriu sorrenca carbonatades»
- `sismica` 1[2] **MISMATCH** «2.60» ↔ «2.45»
- `spt_ma` spt-1[3] **MISMATCH** «58» ↔ «54»
- `spt_ma` spt-1[4] **MISMATCH** «Graves con arena carbonatada» ↔ «Graves en matriu sorrenca»

## Càlcul (no és a cap de les 11 taules): nivell portant, Nb, φ, γ, c, E, Qa — per variant vs signat

Nb = N20 mitjà del nivell únic / 0,83 (el que imprimeix la cel·la, sense la «-R»). Qa = Terzaghi amb topalls; `gov` = qui mana (terzaghi / terzaghi-peck / cap). Signat: `docs/CRITERIS-CALCUL-EVA.md` §5.

Assent.: valor calculat i com s'imprimeix (frase genèrica «<1,0» en roca/cohesiu o < 1,0 cm; ✓ = mateixa forma que el signat); `Es` = defecte (2,5×N SPT del nivell → 2,5×Nb → E) + nombre de candidats.

| projecte | variant | Df | nivell portant (idx: descripció) | N20 | Nb | φ | γ | c | E | Qa (uncapped, gov) | assent. cm | imprès | Es |
|---|---|--:|---|--:|--:|--:|--:|--:|--:|---|--:|---|---|
| **castellar** | *signat* | | | | 17-R | 35 | 2.2 | 1.0 | >500 | **3.0** | | **<1,0** | |
| castellar | `8b` | 0.3 | 1: Roca / material dur (roca pochimada / fora po | 22.56 | 27.2 | 30.5 | 1.9 | 0.05 | 114 | 2.00 (1.84, terzaghi) | 1.80 | <1,0 ✓ | 56 (3 cand.) |
| castellar | `calc` | 0.3 | 1: Roca / material dur (roca pochimada / fora po | 22.56 | 27.2 | 35 | 2.2 | 1.0 | 500 | 3.00 (27.20, cap) | 2.30 | <1,0 ✓ | 68 (2 cand.) |
| castellar | `t2` | 0.3 | 1: Roca / material dur (roca pochimada / fora po | 22.56 | 27.2 | 35 | 2.2 | 1.0 | 500 | 3.00 (27.20, cap) | 2.30 | <1,0 ✓ | 68 (2 cand.) |
| castellar | `viab` | 0.3 | 1: Roca / material dur (roca pochimada / fora po | 22.56 | 27.2 | 35 | 2.2 | 1.0 | 500 | 3.00 (27.20, cap) | 2.30 | <1,0 ✓ | 68 (2 cand.) |
| **rubi** | *signat* | | | | 47-R | 39 | 2.0 | 0.05 | 450 | **3.5** | | **1,50** | |
| rubi | `8b` | 1 | 0: Graves i sorres (Nivell 1) | 34.8 | 41.9 | 37.1 | 2 | 0 | 469 | 3.50 (5.25, cap) | 1.70 | 1,70 ✗ | 104 (4 cand.) |
| rubi | `calc` | 1 | 0: Graves i sorres (Nivell 1) | 34.8 | 41.9 | 39 | 2.0 | 0.0 | 450 | 3.50 (7.00, cap) | 1.80 | 1,80 ✗ | 100 (3 cand.) |
| rubi | `t2` | 1 | 0: Graves i sorres (Nivell 1) | 34.8 | 41.9 | 39 | 2.0 | 0.0 | 450 | 3.50 (7.00, cap) | 1.80 | 1,80 ✗ | 100 (3 cand.) |
| rubi | `viab` | 1 | 0: Graves i sorres (Nivell 1) | 34.8 | 41.9 | 39 | 2.0 | 0.0 | 450 | 3.50 (7.00, cap) | 2.00 | 2,00 ✗ | 90 (3 cand.) |
| **bell-lloc** | *signat* | | | | 25-R | 38 | 2.0 | 0.0 | 650 | **3.0** | | **<1,20** | |
| bell-lloc | `8b` | 0.3 | 0: Graves carbonatades | 18.75 | 22.6 | 34.6 | 2 | 0.05 | 467 | 3.00 (3.06, cap) | 2.10 | 2,10 ✗ | 76 (4 cand.) |
| bell-lloc | `calc` | 0.3 | 0: Graves carbonatades | 18.75 | 22.6 | 38 | 2.0 | 0.0 | 450 | 3.00 (3.03, cap) | 1.10 | 1,10 ✗ | 145 (3 cand.) |
| bell-lloc | `t2` | 0.3 | 0: Graves carbonatades | 18.75 | 22.6 | 38 | 2.0 | 0.0 | 450 | 3.00 (3.03, cap) | 1.00 | 1,00 ✗ | 155 (3 cand.) |
| bell-lloc | `viab` | 0.3 | 0: Graves carbonatades | 18.75 | 22.6 | 38 | 2.0 | 0.0 | 450 | 3.00 (3.03, cap) | 1.10 | 1,10 ✗ | 145 (3 cand.) |

## Avisos del generador


