# Pla: portar el codi als criteris de càlcul professionals (P0–P4)

**Data:** 2026-09-03 · **Branca:** `experiment/nivell-a-2026-08` · **Origen:**
`ANALISI-CALCUL-N20-E-2026-09-02.md` (v2) + família de criteris (vegeu `METODOLOGIA-EVA.md` §0).
**Estat:** proposta — cap peça implementada.

## Què NO es toca

- **La cadena Qa** (Nb=N20/0,83 → φ → Terzaghi + topalls 3,0/3,5 + arrodoniment 0,5): validada **6/7 MATCH
  exacte** (`CRITERIS-CALCUL-EVA.md`). Els canvis de sota són de *concepte de cel·la*, *tria d'estrat* i
  *criteri de l'E* — no de la cadena.
- **Es = 2,5×Nb** (assentament) i **K30 = E/75 | E/60**: validats (±8 % i 2/2).
- **Via B de producció** (`geocode_coordinates.py`, `parcel_resolver.py`, `cadastre_adjacents.py`): com sempre.

## Seqüenciació respecte de la MESURA (tasca 1 del handoff)

**La mesura dels 8 projectes va PRIMER, sobre codi intacte** (`feedback_measure_baseline_before_coding`):
el diagnòstic del test vermell va confirmar que el càlcul no s'ha mogut, per tant la mesura no neix caducada.
Els P0–P2 canvien cel·les que `compare_tables_vs_eva.py` puntua: fer-los abans destruiria la línia base.
Després de cada peça: re-run dirigit del comparador i **delta per cel·la**, no titulars de sweep
(`project_judge_noise_band`).
**Comandament (2026-09-06):** `PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache .venv/bin/python
docs/wizard-headless/mesures/mesura_informe.py <run>` i `diff` dels `_compare_informe.txt` per projecte i variant contra
`runs/2026-09-06-informe-p0` (recepta al capçal del script).

## Les peces

### P0 — Columna «N» = N30 de l'SPT *(trivial, ~1 h, cap risc de càlcul)*

- **Què:** `report_generator.py:1469` imprimeix `int(avg_n20)` del DPSH; Eva hi posa l'**N30 de l'assaig
  SPT** del projecte. Verificat als signats: Bell-lloc 54, Rubí 40 (SPT-1 a P-3!), Anciles 6, Alcoletge L2 20,
  Castellar «R» (SPT rebutja), Linyola/Vilanova «--» (sense SPT).
- **Com:** llegir `spt_results[].n_spt` del sondeig (ja extret); regles: sense SPT → «--»; SPT amb rebuig →
  «R»; mai el DPSH. Al nivell que no correspon a l'SPT (fondària fora del tram), «--».
- **Validació:** test unitari amb els 5 casos signats; delta al comparador (cel·la N passa de MISMATCH a OK
  on hi ha SPT).

### P1 — Cel·la «Nb» sense inflar per 0,83 — **RESOLTA 2026-09-03 pel repàs R: DESCARTADA, cap canvi de codi**

- El repàs R ho contradiu amb evidència forta: els fulls DPSH dels annexos imprimeixen el factor **«0,83»**
  entre les columnes «Colpeig DPSH» i «Colpeig NB» (verificat també al preext de Castellar), l'aritmètica
  NB=N20/0,83 quadra fila a fila, i la narrativa en diu «**Nb mig**». La cel·la Nb del codi
  (`report_generator.py:1434`) és **correcta en concepte**.
- La discrepància de valors (nostre «41-R» vs «25-R» signat a Bell-lloc) NO és el factor: és **quines lectures
  entren a la mitjana** — s'ha mogut sencera a P4. Vegeu `RECERCA-CRITERIS-DESCRITS-ALS-INFORMES-2026-09-03.md`
  §P1 i la postil·la de l'anàlisi.

### P2 — L'estrat que mana és on RECOLZA la fonamentació *(mitjà, ~½ dia + decisió d'input)*

Dues sub-peces amb el mateix criteri. **Correcció del repàs R (2026-09-03):** el cas Anciles que fonamentava
part d'aquest raonament estava mal llegit a `CRITERIS-CALCUL-EVA.md` §1 — el signat diu pous «empotrados un
mínimo de 20-40 cm de los materiales del **segundo nivel** saneado» (fonamenta a L2, no a L1). El principi
«on recolza» es MANTÉ (Rubí el sosté: la taula parametritza les graves, no el substrat), i surt reforçat per
una troballa nova: **la frase del Qa de l'informe signat DECLARA el nivell portant** (encastament 20-40 cm,
sistemàtic a 5 projectes) — font de veritat directa per a la tria d'estrat.

- **P2a — col·lapse a 1 nivell** (`report_data.py:1168-1194`): avui pren descripció i paràmetres de
  `sondeig_layers[-1]` (la més profunda) → **Rubí queda vestit de roca** (φ35/E500/γ2,2/c1,0 vs signat
  granular 39/450/2,0/0,05). Ha de prendre el nivell **on recolza la sabata**.
- **P2b — `_select_bearing_layer_idx`** (`report_data.py:968`): «competent més profund» amb
  `foundation_depth=0.8` fix. Anciles signat el desmenteix (Eva usa L1 feble perquè la sabata no arriba a
  L2). Cal la **fondària de fonamentació real** com a input — connecta amb el fil G.1 «calc input plumbing»
  (memòria `project_ccagentic_paused`). Mentre no hi sigui: heurística explícita + camp al wizard
  (override expert), mai un valor silenciós.
- **Validació:** Rubí (6 cel·les), Anciles (quan hi hagi fixtures), Alcoletge (skip-rebliment ha de seguir
  funcionant — el cas que bicapa ja resol bé). Delta al comparador per cel·la.

### P3 — E per criteris i candidats *(disseny + ~1 dia; l'única peça de criteri nou)*

- **Què:** substituir el punt únic «E_min+10 %» per el criteri real observat als 9 nivells signats:
  1. règim fluix (N<10): **sòl mínim ~50–100 segons litologia** (Eva escriu 50–90, fins per SOBRE del rang
     CTE; el nostre 8 és inimprimible);
  2. trams mitjos: banda baixa (l'actual va bé: +4/+14 %);
  3. **ajust ↑ per «carbonatad-/cimentad-»** a la descripció (Bell-lloc 650 vs 469);
  4. roca: mantenir 500 de base però **imprimir «>»** i permetre judici per projecte;
  5. **arrodonir sempre a 10/50**.
- **Com:** millor com a **candidats amb procedència** (valor de taula + valor ajustat per litologia, amb
  font) que com a fórmula nova — coherent amb el nivell A i amb l'override expert que ja existeix. L'E és
  la variable que Eva mateixa declara de judici («agafa la taula, ja ho ajustarem»).
- **Dependència:** les 4 preguntes d'E ja redactades (`CALCUL-E-MODUL-DEFORMACIO.md` §8) — sumar-les al
  paquet de preguntes pendents a Eva (`PREGUNTES-EVA-PENDENTS.md`) quan toqui.
- **Resultat del repàs R (2026-09-03): negatiu amb valor** — als 6 informes amb lletra, cap frase justifica
  cap E (la llegenda «(4)» de la taula només dona unitats; la font declarada, Crespo, cobreix NOMÉS c i φ).
  **La pregunta a Eva és imprescindible**: els informes no ho descriuen.
- **La proposta v2 del febrer (escalar dins del rang) NO és el camí**: empitjora el règim fluix (N=5 → 4).

### P4 — Regla N20 global/ferm + re-ancorar el test vermell *(bloquejat per decisió)*

- **Què:** amb perfil d'un sol nivell real, ¿N20 de tot el perfil o del tram on recolza? Evidència signada
  2-de-3 vs 1-de-3 — no es pot decidir des del corpus. Pregunta per a Eva redactada a l'anàlisi §4.
- **Aportació del repàs R (2026-09-03), parcial:** patró compatible amb «la cel·la Nb representa el tram on
  treballarà la fonamentació; quan tot el perfil és aquest tram, mitjana global» (Bell-lloc 25 i Castellar 17
  només s'expliquen amb els trams superficials pre-rebuig; Rubí 47 només amb tot el perfil). I una dada que
  acota l'ambició: **la mateixa Eva té 4 discrepàncies internes narrativa↔taula** (N 54/58, Nb 48/47, 11/13,
  44/17) — el test re-ancorat necessita **banda de tolerància**, no igualtat exacta.
- **En resoldre's:** fixar el valor esperat del test de Bell-lloc i **congelar la geometria de capes dins
  del test** (literal, no `validation/`) perquè torni a ser una guarda de càlcul. Fins llavors, el test es
  queda vermell (decisió Josep 2026-09-02) i el seu significat està documentat a l'anàlisi §1.

### R — Repàs dels informes signats buscant els criteris que l'Eva hi DESCRIU *(pendent per encàrrec del Josep, 2026-09-03)*

- **Per què:** durant la investigació dels criteris (feb–abr) es va descobrir que **l'Eva descriu alguns dels
  seus criteris dins dels propis informes** (a la narrativa — «Base de Càlcul» i altres seccions) — i que
  havíem investigat pertot arreu MENYS als informes mateixos. El repàs d'abril (G.6, `METODOLOGIA-EVA.md`
  §1 i §5) va mirar fórmules i fonts; aquest ha de buscar específicament **enunciats de criteri** (per què
  tria un E, com compta nivells, quan aplica topalls, rangs de K, quan un valor és «de taula» vs judici).
- **Com:** llegir els 7 informes signats sencers (PDF amb capa de text a `reference-material/*/PDF/`;
  Anciles en castellà) caçant frases de criteri; bolcar-les amb cita textual a `METODOLOGIA-EVA.md`.
- **Valor:** pot resoldre **P3 (E) i P4 (regla N20) sense preguntar a l'Eva** — si ho va deixar escrit, la
  resposta és als informes. Fer-lo ABANS d'enviar-li el paquet de preguntes.
- **Esforç:** ~½ dia. **Bloquejada per:** res (només lectura; pot fer-se en paral·lel a la mesura).
- **FETA 2026-09-03** (agent en paral·lel amb la mesura de Castellar): 7/7 informes, resultat a
  `RECERCA-CRITERIS-DESCRITS-ALS-INFORMES-2026-09-03.md`. P1 resolta (descartada), P3 negativa (cal Eva),
  P4 parcial, cas Anciles capgirat, 2 contradiccions a `CRITERIS-CALCUL-EVA.md` documentades.

### M341 — MESURA COMPLETA de l'informe (les 341 variables) *(programada: després de la mesura dels 8 + fixos no bloquejats)*

- **Què:** la «taula comparativa prod vs via A» ajornada el 2026-08-25 — informe generat COMPLET vs informes
  signats, **totes** les variables (taules + narrativa + escalars), no només nivell A ni les 11 taules.
  És la mètrica que correspon a l'objectiu declarat (`feedback_full_report_341_variables_goal`).
- **Quan:** després de (a) la mesura dels 8 (línia base) i (b) els fixos NO bloquejats — P0, P1 (amb OK),
  P2a. **No esperar P2b–P4** (bloquejats per decisions/Eva): la mesura completa els destaparà amb números.
- **Prerequisit tècnic** (el motiu de l'ajornament d'agost): unificar veritat, camps i semàntica entre
  `reference_extractor`/`eva_reference_values.json` (~30-37 vars/projecte), `_eva_truth` (taules) i les
  decisions de la via A — vegeu sessió 2026-08-25.
- **Sortida:** taula per GRUP (nivell A / grup B / resta) × projecte, amb OK/CAND/ERR — «l'estat de tot»,
  que des del 59 % global del diagnòstic 2026-08-23 (pre-correccions) ningú ha re-mesurat.
- **Esforç:** ~1-2 dies (el gruix és la unificació de semàntica, no l'execució).

## Ordre i esforç

**Decisió Josep 2026-09-03: el repàs R va ABANS de tots els P0–P4** — el que l'Eva hagi deixat escrit als
informes pot revisar els fixos mateixos (la interpretació de la cel·la Nb de P1, el criteri d'E de P3, la
regla N20 de P4), i val més llegir-ho abans de tocar res.

| Ordre | Peça | Esforç | Estat / bloquejada per |
|---|---|---|---|
| 0 | **Mesura dels 8** (tasca 1 handoff) | — | **7/8 FETS** (2026-09-04); queda Tulipa. ERR sistema 4 (1 font, 3 consolidador). Vilanova al titular (signat trobat) |
| 0b | **Fixes de consolidador/inventari sortits de la mesura** — ✅ **FETA 2026-09-05** (matí: C, D2, D3, R3; tarda: G, R6, I1, R1, D5, D4, D6, T1, T2; S1 = disseny). Escalars sobre l'or 86 → 104 OK, ERR 3 → 0; taules ERR 4 → 0; l'únic ERR real que queda sobre el signat és de font (Rubí cota P-2). Queden R4 (pregunta a Eva), persona/despatx (pregunta a Eva), S1; **R5 ✅ 2026-09-05 nit** (bloc 1.1: 8 cel·les → OK, escalars 112/29/5/1/0); **R2 ✅ 2026-09-05 nit** (bloc 1.2: 9 cel·les, escalars 116/25/5/1/0, taules 138/21/7/31/0); **F1 ✅ 2026-09-05 nit** (bloc 1.3: 3 cel·les, escalars 118/23/5/1/0 = OK 80 %, taules 139/21/6/31/0, 0 ERR sobre el signat); **1.4 derivats ✅ 2026-09-05 nit** (13 cel·les, taules 143/27/7/20/0, blancs 31 → 20; 1 ALERTA formal: or d'Alcoletge `[1].a`); **1.5 L3 + L1 ✅ 2026-09-05 nit** (Anciles MA n30 → or; Linyola n30 «R» amb re-lectura d'1 doc, 1,63 USD; taules 144/28/6/19/0); **1.6 T2 ✅ 2026-09-06** (regles `utm`/`lab_sample_id` en Python, passada LLM apagada: escalars 119/22/5/1/0, conflictes 7 → 3, −1 USD i −4 min per projecte) | — | ✅ vegeu `_DIAGNOSTICS-INDEX.md` §Estat dels fixes i `_AGREGAT-8.md` §Agregat mecànic (matí i tarda) |
| 0c | **Línia base d'INFORME** (`mesura_informe.py`: 3 projectes × 4 variants, `compare_tables_vs_eva.py`) | — | ✅ **FETA 2026-09-06** (`runs/2026-09-06-informe-bloc2-base`; referència viva `-p0`). La `8b` replica la Fase 8b exacta; `calc` és la columna del bloc 2 |
| 1 | **R** repàs criteris als informes | ~½ dia | **FETA 2026-09-03** |
| 2 | P0 columna N | ~1 h | ✅ **FETA 2026-09-06** (`automation/spt_n_column.py`, 33 tests): N = N30 de l'SPT del nivell tal com surt a la taula SPT/MA del mateix informe; litologia → fondària → «--». Castellar «22»→«R», Rubí «43»→«40» (MATCH), Bell-lloc «34»→«58» (signat 54, pregunta 1); cap altra cel·la moguda. DECISION-LOG 2026-09-06 (tarda) |
| 3 | ~~P1 cel·la Nb~~ | — | **DESCARTADA per R** (el /0,83 és correcte; la qüestió viva és P4) |
| 4 | P2a col·lapse (Rubí) | ~2 h | ✅ **implementada i mesurada 2026-09-06 (tarda, 2), GO pendent:** el col·lapse pren el nivell portant (Rubí Qa 3,0 → 3,5 = signat; `viab` 62 → 69 %). Abans: visible NOMÉS a la variant `viab` (sense lectura): 7/7 cel·les (nom «Gresos… (Nivell 2)», γ 2,20 / c 1,00 / φ 35 / E 500). Amb lectura, `_apply_lectura_soil_levels` tapa la descripció abans d'`is_rock` i només queden Nb «52-R» i E 469. **Acoblada a P2b** (mateixa regla) |
| 5 | **M341** mesura completa (341 vars) | ~1-2 dies | mesura dels 8 + P0/P2a |
| 6 | P2b fondària sabata | ~½ dia | ✅ **càlcul fet 2026-09-06 (tarda, 2), GO pendent:** Df del wizard arriba a la tria d'estrat; regla «primer competent a Df + 0,2»; 7/7 signats als tests amb la Df de cada informe. Queda la UI (nivell portant i Df visibles, avís si Df és el prefill) i Linyola/Anciles depenen de la Df dels pous. Bell-lloc Qa 2,5 → 1,5 destapa P3. Abans: `foundation_depth_m` JA és al wizard (prefill 0,3) però `report_data.py:468` passa el 0,8 fix a `_select_bearing_layer_idx`, que tria «el competent més profund». Proposta: «el primer competent que la sabata assoleix (Df + 0,2-0,4)», mai més profund; mesurar Qa abans/després |
| 7 | P3 E per criteris | ~1 dia | **pregunta a Eva imprescindible** (R negatiu) |
| 8 | P4 regla N20 + test | ~2 h | pregunta a Eva o decisió Josep (R dona patró parcial + exigeix tolerància) |

Després de cada peça: suite dirigida + delta de `compare_tables_vs_eva` **per cel·la i per nom**, mai
recomptes (`feedback_compare_test_names_not_counts`).

---
*Fi pla 2026-09-03 (v2). Vuit peces: dues mesures (8 + 341), un repàs d'informes, tres fixos de concepte,
un criteri nou (E), una decisió (N20).*
