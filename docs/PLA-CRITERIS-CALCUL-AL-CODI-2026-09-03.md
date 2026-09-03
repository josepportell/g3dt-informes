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

## Les peces

### P0 — Columna «N» = N30 de l'SPT *(trivial, ~1 h, cap risc de càlcul)*

- **Què:** `report_generator.py:1469` imprimeix `int(avg_n20)` del DPSH; Eva hi posa l'**N30 de l'assaig
  SPT** del projecte. Verificat als signats: Bell-lloc 54, Rubí 40 (SPT-1 a P-3!), Anciles 6, Alcoletge L2 20,
  Castellar «R» (SPT rebutja), Linyola/Vilanova «--» (sense SPT).
- **Com:** llegir `spt_results[].n_spt` del sondeig (ja extret); regles: sense SPT → «--»; SPT amb rebuig →
  «R»; mai el DPSH. Al nivell que no correspon a l'SPT (fondària fora del tram), «--».
- **Validació:** test unitari amb els 5 casos signats; delta al comparador (cel·la N passa de MISMATCH a OK
  on hi ha SPT).

### P1 — Cel·la «Nb» sense inflar per 0,83 *(petit, ~1 h; cal OK del Josep — canvia un número visible)*

- **Què:** `report_generator.py:1434-1436` mostra `N20/0,83`; l'Nb signat d'Eva segueix el **N20 cru** del
  full de camp (els Excel ja porten la columna Nb; la relació ×0,83 va d'Nb→N). Evidència 3/3: Bell-lloc
  «25» vs 25,1 cru (clavat) contra el nostre «41-R»; Castellar «17» vs 18,7 contra «27-R»; Rubí «47» vs 43,3
  contra «52-R».
- **Com:** display only — `nb_display` a partir del N20 del nivell, sufix «-R» com ara. **La conversió /0,83
  del càlcul de φ no es toca.**
- **Risc:** si Eva llegís el canvi com a «número diferent del meu» — però l'evidència diu justament que ara
  ens hi acostem. Validar la interpretació amb el Josep abans (i si cal, pregunta a Eva).

### P2 — L'estrat que mana és on RECOLZA la fonamentació *(mitjà, ~½ dia + decisió d'input)*

Dues sub-peces amb el mateix criteri (`CRITERIS-CALCUL-EVA.md` §1, cas Anciles):

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
- **La proposta v2 del febrer (escalar dins del rang) NO és el camí**: empitjora el règim fluix (N=5 → 4).

### P4 — Regla N20 global/ferm + re-ancorar el test vermell *(bloquejat per decisió)*

- **Què:** amb perfil d'un sol nivell real, ¿N20 de tot el perfil o del tram on recolza? Evidència signada
  2-de-3 vs 1-de-3 — no es pot decidir des del corpus. Pregunta per a Eva redactada a l'anàlisi §4.
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

| Ordre | Peça | Esforç | Bloquejada per |
|---|---|---|---|
| 0 | **Mesura dels 8** (tasca 1 handoff) | — | en curs (Castellar 2026-09-03) |
| 1 | **R** repàs criteris als informes | ~½ dia | res (paral·lelitzable amb la mesura) |
| 2 | P0 columna N | ~1 h | mesura + R |
| 3 | P1 cel·la Nb | ~1 h | R + OK Josep |
| 4 | P2a col·lapse (Rubí) | ~2 h | mesura + R |
| 5 | **M341** mesura completa (341 vars) | ~1-2 dies | mesura dels 8 + P0/P1/P2a |
| 6 | P2b fondària sabata | ~½ dia | R + decisió input (G.1) |
| 7 | P3 E per criteris | ~1 dia | R; si no en surt, pregunta a Eva |
| 8 | P4 regla N20 + test | ~2 h | R; si no en surt, Eva o decisió Josep |

Després de cada peça: suite dirigida + delta de `compare_tables_vs_eva` **per cel·la i per nom**, mai
recomptes (`feedback_compare_test_names_not_counts`).

---
*Fi pla 2026-09-03 (v2). Vuit peces: dues mesures (8 + 341), un repàs d'informes, tres fixos de concepte,
un criteri nou (E), una decisió (N20).*
