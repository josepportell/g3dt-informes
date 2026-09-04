# Mesura dels 8 — AGREGAT (2026-09-03 → 2026-09-04, codi intacte `experiment/nivell-a-2026-08`, pre P0-P4)

**Criteris:** `../../CRITERIS-MESURA-2026-09-03.md` (+ esmena 2026-09-04: Vilanova entra). **Titular: 7 comparables**
(Tulipa sense veritat). **Veritat = informe signat** (`_eva_truth/{slug}.json` + `eva_reference_values.json`); els
veredictes crus del comparador s'han **contrastat cel·la a cel·la** (vegeu `{slug}/_NOTES.md`): 18 falsos ERR/ALERTA
del comparador (adreces, ids duplicats, ca/es, columnes de fixture) NO compten. **Els números de sota són els
contrastats; l'agregat mecànic** (`ledger.py` sobre `_compare_*.txt`) **només tindrà sentit després d'arreglar
`compare_consolida.py`** (codi C de l'índex). Diagnòstics: `_DIAGNOSTICS-INDEX.md`.

## Titular (7 projectes, sobre el signat)

**Escalars — 21 camps amb or per projecte, 147 cel·les:**

| Projecte | OK | CAND | Blanc | **ERR** | OK % |
|---|---|---|---|---|---|
| Castellar | 16 (14 + 2 fora de carpeta ✓) | 5 | 0 | 0 | 76 % |
| Bell-lloc | 11 | 10 | 0 | 0 | 52 % |
| Rubí | 12 | 9 | 0 | 0 | 57 % |
| Linyola | 13 | 7 | 0 | **1** (`field_date`, D2) | 62 % |
| Alcoletge | 16 | 5 | 0 | 0 | 76 % |
| Vilanova | 14 | 6 | 0 | **1** (`municipality`, D3) | 67 % |
| Anciles | 12 | 8 | 1 (I1) | 0 | 57 % |
| **Total** | **94 (64 %)** | **50 (34 %)** | 1 | **2 (1,4 %)** | |

**Taules — 199 cel·les (excloses les columnes només del fixture):**

| Projecte | OK | CAND | Blanc | **ERR** |
|---|---|---|---|---|
| Castellar | 28 | 1 | 0 | 0 |
| Bell-lloc | 17 | 3 | 1 | 0 |
| Rubí | 17 | 2 | 3 | **1** (cota P-2, F1) |
| Linyola | 16 | 5 | 4 | 0 |
| Alcoletge | 16 | 6 | 3 | 0 |
| Vilanova | 17 | 6 | 6 | **1** (`nivell_freatic` P-3, R6) |
| Anciles | 22 | 10 | 14 (8 I1) | 0 |
| **Total** | **133 (67 %)** | **33 (17 %)** | **31 (16 %)** | **2 (1,0 %)** |

**Contra els llindars pactats:** OK ≥ 80 % → **NO** (64 % / 67 %) · CAND ≤ 20 % → **NO** als escalars (34 %), sí a
les taules (17 %) · **ERR = 0 → NO: 4** (1 de font d'Eva, **3 de consolidador**). Cap ERR és de lectura per document.

## Els 4 ERR

| # | On | Sistema diu | Veritat | Causa | Codi |
|---|---|---|---|---|---|
| 1 | Rubí `dpsh[P-2].cota_inici` | segur «+212 msnm» (literal annex p.2) | +212,50 (informe; p.1/p.3 de l'annex) | annex d'Eva inconsistent amb el seu informe | **F1** |
| 2 | Linyola `field_date` | segur 2025-10-10 | 2025-10-01 (7 fonts) | «Octubre 2025» fa de pont entre dies + representant per `len(str)` + `_iso_date` sobreescriu | **D2** |
| 3 | Vilanova `municipality` | segur «Vilanova **del** Segrià» | Vilanova de Segrià | forma visible per `len(v)` en lloc del `name_ine` del padró | **D3** |
| 4 | Vilanova `dpsh[P-3].nivell_freatic` | segur «No detectat» | −1,00 (humitat) | columna buida (A) tapa «Aigua» del tall i «Humit» del camp (no-A) | **R6** |

**Patró comú a 2, 3 i 4:** un desempat mecànic pren una decisió «segur» contra informació que el propi
`_decisions.json` ja conté (altres formes del cluster, `altres`, el padró). Cap dels 4 és un valor inventat.

## On es perd la confiança (cel·les correctes que queden en CAND) — recompte transversal

| Causa | Cel·les (7 proj.) | Descripció | Fix |
|---|---|---|---|
| **R5** | 19 | font única del proveïdor (projecte de l'arquitecte, correu, manuscrit) sense A ni convergència | regla «el projecte de l'arquitecte mana» (l'or ja l'aplica); annex de sondeig com a A |
| **R1** | 15 | mateixa entitat, formes diferents = «contradicció»: **abreviatures G3 a `building_type` 8/8**, persona/despatx, TPS curt/llarg, grafies, adreces amb/sense sufix | equivalència per camp a `value_key`; padró per al municipi |
| **R4** | 9 | `cte_*` mai segur, també quan el pressupost ho imprimeix | pregunta a Eva (T pressupost = T informe?) |
| **R2** | 6 | concepte veí bloqueja: z GPS a `cota_referencia` (3/3), data del sondeig a `field_date`, msnm vs fondària als nivells | per camp: z de l'annex mana; «dos dies»; conversió msnm→fondària |
| **F1** | 7 | fonts d'Eva inconsistents entre elles (comanda vs GTL, annex vs informe, **SPT P-1/P-3 creuats a Vilanova**) | regla «qui mana» del skill; coherència entre files; preguntes a Eva |
| R3 | 1 | guard `"1 de"` per substring | regex |
| D5 | 1 | CTE derivat amb la superfície d'una tipologia | factor N unitats |
| C | 18 | comparador (falsos ERR/ALERTA) | `compare_consolida.py` **abans d'agregar mecànicament** |
| G | 6 | or: `fora_carpeta` absent (3/3 amb Cadastre ON), esborranys, persona vs despatx | `golden-read*` |

**Estimació:** només **R1 + R3 + D3** (equivalències, sense tocar criteris d'Eva) pujarien ~17 cel·les → escalars
~75 % OK; amb **R5** (projecte de l'arquitecte = A) i **R2** → ~85 %. Per sobre del llindar sense preguntar res a Eva.

## Cobertura, operació, temps, cost

| Tema | Codi | Dades |
|---|---|---|
| **Cobertura** | **I1** | Anciles: `PDF_V0/` exclosa tot i ser l'única carpeta d'annexos → **9 cotes en blanc**. Alternativa provada: els `.FH11` es llegeixen via libfreehand (`docs/research/FH11-LIBFREEHAND-2026-09-04.md`) |
| Runner | **D4** | Vilanova: 3 docs perduts (tall de xarxa) i `degraded=False` amb 11/14 |
| Runner | **D6** | Tulipa: `X.dwg` i `X.pdf` → mateix JSON; una lectura sobreescriu l'altra (317 s + 1,25 USD) |
| Runner | **T1** | Alcoletge: `claude -p` penjat sense stdout fins als 600 s (PENETROS); reintent OK |
| Consolidador | **T2** | Tulipa: passada LLM de 523 s (28 % del run) per conflictes entre cases |
| Estructura | **S1** | Tulipa: multi-casa no modelat (un `_decisions.json`; 2 de 4 DPSH) |
| Lector | L1-L3 | `n30` del full SPT manuscrit absent; il·legibles honestos; telèfon dins del valor; N30 en una MA |

**Temps** (config prod: sonnet, xhigh, c2, preext, consolida auto):

| Projecte | Docs Claude | Minuts | Nota |
|---|---|---|---|
| Castellar | 13 | 33,4 | base 27,8; agent R en paral·lel |
| Bell-lloc | 18 | 34,9 + 13,1 | compost (run matat) |
| Rubí | 12 | 26,9 | net |
| Linyola | 20 | 42,9 | **base 41,9 → +2 %, dins del soroll** |
| Alcoletge | 13 | 41,0 | 10,0 de timeout (T1) → ~31 net |
| Vilanova | 14 | 22 + 9,5 | compost (tall de xarxa) → ~32 net |
| Anciles | 14 | 28,3 | net |
| Tulipa | 16 | 43,5 | 12,1 LLM (T2) + 5,3 D6 → ~26 net |

Franja neta: **26-43 min**, ~2-3 min per document Claude a c2; PENETROS és sempre el més lent (380-520 s).
**Cost API: 121,75 USD als 8** (11-19 USD/projecte; ~0,9 USD/doc) — tot en crides `claude -p` amb API key.

## Què queda per tancar la mesura

1. Arreglar el comparador (C) i regenerar `_compare_*.txt` → agregat mecànic amb `ledger.py` (ha de coincidir amb aquest).
2. Or: `fora_carpeta` a Rubí/Alcoletge/Vilanova; Castellar `utm` ja corregit.
3. Preguntes a Eva (STATUS): E, N20, T del pressupost, persona/despatx, **SPT Vilanova**.
4. Prioritzar la fila 0b del PLA (fixes de consolidador/inventari/runner) — decisió del Josep.
