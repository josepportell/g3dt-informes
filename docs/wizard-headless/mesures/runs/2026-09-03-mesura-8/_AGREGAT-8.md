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

---

## Agregat MECÀNIC (2026-09-05) — comparador v4 + fixes C, D2, D3, R3

**Què s'ha fet (decisió del Josep 2026-09-05: «endavant amb C, D2, D3, R3»):** `compare_consolida.py` v4 (codi C: els 18
falsos veredictes), `consolidate.py` D2 (dates sense dia no fan de pont; representant per autoritat; ISO només del propi
candidat), D3 (`municipality` = grafia oficial del padró quan totes les formes resolen al mateix registre) i R3 (guard
`"1 de N"` amb límit de paraula). Cada fix amb test (`tests/test_compare_consolida.py`, `tests/test_lectura_consolidate.py`).
**Agregador:** `docs/wizard-headless/mesures/agrega_mesura.py` (`ledger.py` no serveix: espera un run per carpeta amb
`meta.json`). **Reconsolidació** dels 7 amb el consolidador nou a partir de les lectures cachejades del run (+ la passada
LLM `_consolida_only.json` ja existent, mateixos conflictes): `{slug}/_reconsolida-2026-09-05/` — **cost 0, sense
re-run**. Els `_compare_*.txt` de `{slug}/` s'han regenerat amb el v4 sobre els `_decisions.json` ORIGINALS (consolidador
antic): aïllen l'efecte del comparador.

### Tres columnes: què mou cada cosa

| Escalars (147) | OK | CAND | ALERTA | Blanc | ERR |
|---|--:|--:|--:|--:|--:|
| comparador v3 · consolidador antic (cru, 09-04) | 86 | 46 | 11 | 1 | 3 |
| **comparador v4** · consolidador antic (`{slug}/_compare_*.txt`) | 90 | 46 | 8 | 1 | 2 |
| comparador v4 · **consolidador nou** (`_reconsolida-2026-09-05/`) | **93** | **45** | **8** | **1** | **0** |

| Taules (197 + 2 ABSENT Rubí + 11 NOMES-OR) | OK | CAND | ALERTA | Blanc | ERR |
|---|--:|--:|--:|--:|--:|
| comparador v3 · consolidador antic | 127 | 26 | 9 | 31 | 4 |
| **comparador v4** · consolidador antic | 136 | 21 | 9 | 31 | 0 |
| comparador v4 · consolidador nou | 136 | 21 | 9 | 31 | 0 |

- **C (comparador):** +4 OK escalars, +9 OK taules, −4 ERR taules (Vilanova SPT punt/profunditat ×4 = alineació per
  `punt` + unitat enganxada), −1 ERR escalars (Alcoletge adreça), −3 ALERTA (Linyola adreça; Anciles `building_type`
  ca/es i `client_name` telèfon), −5 CAUTELA falses (Rubí `num_floors` porxada; Alcoletge `nivell_freatic` ×3; Anciles
  `architect_name` col·legiat, `lab_testing_company`). Cap veredicte nou fals: les 6 cel·les que canvien a Vilanova/Anciles
  s'han contrastat una per una. Les 11 columnes només del fixture (`lab`, `nom`, `id_estat`, `litologia_del_nivell`,
  `assaig_encarregat`) surten com a `NOMES-OR` i no compten (abans ABSENT).
- **D2 + D3 + R3 (consolidador):** exactament 3 cel·les escalars canvien als 7 projectes, cap de taula: Linyola
  `field_date` 2025-10-10 → **2025-10-01** (segur, font fitxa F38, cita `datetime(2025, 10, 1)`), Vilanova
  `municipality` «del Segrià» → **«Vilanova de Segrià»** (INE 25251; la forma del document queda a la cita), Bell-lloc
  `num_floors` candidats → **segur «PB+PP»** (5 fonts; el guard ja no dispara amb «P1 de 86 m2»). **ERR de codi: 3 → 0.**

### Per projecte (comparador v4 · consolidador nou)

| Projecte | Escalars OK / CAND / ALERTA / Blanc / ERR | Taules OK / CAND / ALERTA / Blanc / ERR |
|---|---|---|
| Castellar | 16 / 5 / 0 / 0 / 0 | 28 / 1 / 0 / 0 / 0 |
| Bell-lloc | 12 / 9 / 0 / 0 / 0 | 17 / 3 / 0 / 1 / 0 |
| Rubí | 11 / 6 / 4 / 0 / 0 | 14 / 0 / 4 / 3 / 0 (+2 ABSENT: fila `soil_levels[1]` que prod no té) |
| Linyola | 13 / 8 / 0 / 0 / 0 | 16 / 4 / 1 / 4 / 0 |
| Alcoletge | 15 / 5 / 1 / 0 / 0 | 19 / 3 / 0 / 3 / 0 |
| Vilanova | 13 / 6 / 2 / 0 / 0 | 20 / 1 / 3 / 6 / 0 (+4 NOMES-OR) |
| Anciles | 13 / 6 / 1 / 1 / 0 | 22 / 9 / 1 / 14 / 0 (+7 NOMES-OR) |
| **Total** | **93 (63 %) / 45 (31 %) / 8 / 1 / 0** | **136 (69 %) / 21 / 9 / 31 / 0** |

### Com es llegeix respecte del titular contrastat a mà (§Titular)

El comparador mesura contra **l'or de lectura**; el titular del 09-04 mesura contra **el signat**. Les diferències són
les esperades i tenen nom:

1. **ALERTA = prod més confiat que l'or.** És on s'amaguen els ERR de veritat quan l'or era prudent: dels 9 ALERTA de
   taules, **2 són els ERR reals** que queden (Rubí cota P-2, F1; Vilanova `nivell_freatic` P-3, R6) i els altres 7 són OK
   o CAND sobre el signat (Rubí cota ×2 i `soil_levels[2].de`, Vilanova `id` ×2, Linyola msnm, Anciles `n30`). Dels 8
   ALERTA d'escalars, 3 serien OK-fora amb el `fora_carpeta` que falta a l'or (**G**: `superficie_parcela` de Rubí,
   Alcoletge i Vilanova) i 5 són CAND. **Amb G fet, l'agregat mecànic d'escalars seria 96 OK / 50 CAND / 1 / 0** = el
   titular del 09-04 (94/50/1/2) amb els dos ERR de codi passats a OK.
2. **CAND de taules 21 vs 33:** el recompte manual va comptar com a CAND cel·les on or i prod són tots dos `candidats`
   i solapen (Alcoletge `nivell_freatic` ×3, Vilanova `n30`/`litologia` ×4 amb el signat creuat, Anciles) perquè el
   signat hi té un valor únic; el comparador les compta OK (prod fa el que l'or diu). Cap de les dues és falsa: són
   dues preguntes («coincideix amb l'or?» / «l'Eva ho hauria de tocar?»). L'ERR de veritat no depèn d'aquesta
   diferència.
3. **±1 cel·la a Linyola, Vilanova i Anciles** entre el recompte manual i el mecànic (el diagnòstic de Linyola diu
   «ALERTA → CAND» a la taula i compta 13 OK al resum). **Des d'avui el mecànic mana**; el titular del 09-04 queda com
   a història amb els seus números.

### Què queda (fila 0b, ordre proposat, no decidit)

G (`fora_carpeta` a 3 ors: converteix 3 ALERTA en OK-fora) · R6 (`nivell_freatic` en taules: 1 ERR real) · I1 (`PDF_V0`:
9 blancs d'Anciles) · R1 (equivalències: 15 CAND) · D5 · D4/D6 · T1/T2 · S1. Els tres ERR sobre el signat que
quedaven (Rubí P-2 F1, Vilanova P-3 R6) són 2: el de Rubí és de la font d'Eva.

---

## Agregat MECÀNIC (2026-09-05, tarda) — resta de la fila 0b: G, R6, I1, R1, D5, D4, D6, T1, T2

**Decisió del Josep (2026-09-05):** «seguim amb la resta de la fila 0b, amb la teva proposta d'ordre tal qual» (G → R6 →
I1 → R1, després D5, D4/D6, T1/T2; S1 = disseny). Mateix mètode: cada fix es mesura reconsolidant els 7 amb les lectures
cachejades (`mesures/reconsolida_mesura.py <sub_nou> <sub_referència>`), cost 0, i es llisten TOTES les cel·les que
canvien. Subcarpetes: `_reconsolida-2026-09-05-r6` (R6), `-r1` (R1), `-r2` (D5). I1 necessita lectures noves (5 PDF de
`PDF_V0/ANEJOS` d'Anciles): run parcial `runs/2026-09-05-i1-anciles/` (vegeu §I1 més avall).

| Escalars (147) | OK | CAND | ALERTA | Blanc | ERR | Cel·les que mou |
|---|--:|--:|--:|--:|--:|---|
| matí (C + D2 + D3 + R3) | 93 | 45 | 8 | 1 | 0 | — |
| + **G** (3 `fora_carpeta` a l'or) | 96 | 45 | 5 | 1 | 0 | 3 ALERTA → OK-fora (`superficie_parcela` Rubí 951, Alcoletge 1167, Vilanova 406 = signat) |
| + **R6** (taules, no toca escalars) | 96 | 45 | 5 | 1 | 0 | 0 escalars; 1 taula (sota) |
| + **R1** (equivalències) | 103 | 38 | 5 | 1 | 0 | 7: `building_type` Castellar/Bell-lloc/Linyola → segur «Habitatge unifamiliar aïllat»; `lab_testing_company` Bell-lloc → segur TPS; `lab_location` Linyola → segur «P-3» (Rubí «P3» → «P-3»); `client_name` Vilanova → segur; `street_address` Anciles → segur |
| + **D5** (CTE per edifici) | 104 | 37 | 5 | 1 | 0 | 1: Anciles `cte_edificacio` C0 → **C1** (candidats; = or i signat) |

| Taules (197) | OK | CAND | ALERTA | Blanc | ERR | Cel·les que mou |
|---|--:|--:|--:|--:|--:|---|
| matí | 136 | 21 | 9 | 31 | 0 | — |
| + **R6** | 137 | 21 | 8 | 31 | 0 | 1: Vilanova `dpsh[P-3].nivell_freatic` segur «No detectat» → **candidats [Aigua (tall), No detectat, Humit (camp)]** (or: candidats, tall primer; signat «Humedad −1,00») — l'ERR de veritat R6 desapareix |
| + R1, D5 | 137 | 21 | 8 | 31 | 0 | 0 |

**Sobre el signat (lectura a mà de les 5 + 8 ALERTA):** escalars → 104 OK (71 %) / 42 CAND (29 %) / 1 blanc / **0 ERR**;
taules → els 8 ALERTA són 5 OK per veritat (Rubí cota P-1/P-3, Vilanova `id` ×2, Rubí `soil_levels[2].de`), 2 CAND (Linyola
msnm R2, Anciles `n30`) i **1 ERR real: Rubí cota P-2 (+212 literal de l'annex vs +212,50 del signat, F1 = font d'Eva)**.
Dels 4 ERR del titular del 09-04 en queda 1, i és de font, no de codi. Llindars: ERR 0 ✅ als escalars; OK 71 % (⏳ 80);
CAND 29 % (⏳ 20). El que queda en CAND té nom: R5 (font única, 19), R4 (CTE imprès, 9: pregunta a Eva), R2 (concepte
veí, 6), F1 (7), persona/despatx (pregunta a Eva).

**Regressions:** cap. Cada reconsolidació llista totes les cel·les que canvien d'estat o de valor; totes les llistades
van cap a l'or o al signat, i cap OK anterior s'ha perdut (les llistes de no-OK per projecte són a `_reconsolida-*/`).

### Runner i operació (D4, D6, T1, T2), sense efecte sobre l'agregat

- **D4:** `LecturaResult.docs_failed` + `degraded=True` quan un document acaba sense JSON vàlid després dels reintents
  (Vilanova run 1: 11/14 docs i `degraded=False`). Esdeveniment `lectura_fi` porta `docs_failed`.
- **D6:** `assign_doc_names`: dos fitxers de la cua amb el mateix `safe_doc_name` (`X.dwg`/`X.pdf`, Tulipa) reben
  `x_dwg.json`/`x_pdf.json`; el skill continua escrivint `x.json` i el runner el mou al nom esperat (cache intacta).
- **T1:** `G3DT_LECTURA_TIMEOUT_SLOW` (900 s) per als fulls de camp (`camp_penetros`, `full_camp_manuscrit`); `timeout_s`
  a la telemetria. La penjada no es pot detectar abans: el CLI no escriu res fins al final (`--output-format json`).
- **T2:** la passada LLM `--only-fields` rep només conflictes `fields.*` (als 7 runs cap `tables.*` s'ha aplicat mai) i
  s'omet per sobre de `G3DT_LECTURA_LLM_MAX_CONFLICTS` (8). **Observació per decidir:** la passada costa 200-290 s i
  14-23 torns fins i tot amb UN conflicte (Alcoletge 200 s, Bell-lloc 224 s, Rubí 206 s): mesurar si els valors que aplica
  són millors que els candidats Python abans de mantenir-la.
- **S1 (disseny, no implementat):** eix «casa» — l'inventari agrupa per subcarpeta de casa (`Casa 1 - Tulipa/`, `Casa 2 -
  Carrer Tosca/`), consolidació i `_decisions.json` per casa, taules per casa; l'or per casa ja existeix. Fins llavors,
  Tulipa queda fora del titular.

### I1 — resultat del run parcial d'Anciles (`runs/2026-09-05-i1-anciles/`)

Còpia del run d'Anciles (lectures cachejades) + inventari nou: **5 PDF de `PDF_V0/ANEJOS/` llegits** (DPSH 335 s,
corte de correlación 318 s, fotografías 109 s, sondeos **600 s timeout al 1r intent** → 414 s al 2n (T1 en viu),
plano de situación 354 s). **20,3 min, 5,87 USD**, 0 contaminació DNS, consolidació Python sense conflictes.
Reconsolidat amb el codi final a `_reconsolida-2026-09-05/` (script `measure_i1.py` de la sessió).

**Primera passada (V0 com a font A): 30 cel·les canvien, i apareix un ERR nou** — `soil_levels[0].mostra_del_nivell`
segur `True` (annex V0: les graves són «NIVEL 1, part inferior») contra l'or i el signat (`false`: al signat les graves
són el **2n nivell**, i la MA-1 hi és). És exactament el que vol dir «versió anterior»: les cotes no han canviat entre
V0 i signat, l'estructura de nivells sí. **Regla afegida (consolidador):** un document d'una carpeta V0 **proposa i
corrobora, mai és autoritat ni contradiu** (`is_a=False`, confiança < llindar de contradicció, nota «versió anterior»).

**Resultat final (V0 no-A): 21 cel·les canvien respecte de r2, cap ERR.** Anciles escalars 15 → **16 OK / 4 CAND /
1 ALERTA / 0 blanc** (`cota_referencia` no_trobat → candidats «+1106,42 msnm»); taules **blancs 14 → 3**: les 6
`cota_inici` DPSH (+1106,40/30/40/30/42/65 = signat) i les 2 `cota` de sondeig (+1106,65 / +1106,42 = signat) surten
com a **candidats amb el valor del signat primer** (CAUTELA «bo dins»), `soil_levels[0].de/a/mostra` omplerts com a
candidats, `mostra_del_nivell` del nivell 1 = **ALERTA** (proposta `True` de la V0 contra l'or `false`: és el dubte que
toca). Els 7 restants: **0 cel·les canvien** amb la regla V0 (no en tenen).

Amb I1, l'agregat mecànic d'escalars dels 7 és **105 OK / 37 CAND / 5 ALERTA / 0 blanc / 0 ERR** i el de taules
**137 OK / 37 CAND / 9 ALERTA / 20 blanc / 0 ERR** (Anciles: OK 22, CAND 9 → 19, blanc 14 → 3).
