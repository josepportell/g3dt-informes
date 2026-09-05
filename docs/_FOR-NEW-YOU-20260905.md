# FOR NEW YOU — 2026-09-05 — Fila 0b, primer paquet fet (C, D2, D3, R3); queda la resta de 0b

**Escrit:** 2026-09-05. Substitueix `_FOR-NEW-YOU-20260904.md` (conserva'l: hi ha les trampes i les decisions del Josep).
Branca `experiment/nivell-a-2026-08`, pushada al matí a `7bdbcde`; **els canvis d'avui poden estar sense commit**:
`git status` primer.

## Ordre de lectura (15 min)

1. Aquest document.
2. `docs/wizard-headless/mesures/runs/2026-09-03-mesura-8/_AGREGAT-8.md` **§Agregat mecànic (2026-09-05)** — les tres
   columnes (comparador v3/v4, consolidador antic/nou), per projecte, i com es llegeix respecte del titular manual.
3. `…/_DIAGNOSTICS-INDEX.md` §Estat dels fixes — què és ✅ i on, què és ⏳.
4. `docs/DECISION-LOG.md` entrada 2026-09-05 (7 decisions, dues marxes enrere).

## Actualització (tarda): fila 0b TANCADA

Josep ha dit «seguim amb la resta de la fila 0b, amb la teva proposta d'ordre tal qual»: G, R6, I1, R1, D5, D4, D6, T1,
T2 fets amb test i mesurats per reconsolidació (`mesures/reconsolida_mesura.py <sub_nou> <sub_ref>`); S1 en disseny.
Escalars sobre l'or 104 OK / 37 CAND / 5 ALERTA / 0 ERR; taules 137 / 21 / 8 / 0. Sobre el signat: 1 ERR real (Rubí
cota P-2, font d'Eva). Llegeix `_AGREGAT-8.md` §tarda i el DECISION-LOG 2026-09-05 (tarda). El que queda: preguntes a
Eva (R4, persona/despatx, SPT Vilanova, cota Rubí), R5/R2, decisió sobre la passada LLM (T2), S1.

## Estat en una frase

Els tres ERR de codi de la mesura (Linyola data, Vilanova municipi, Bell-lloc plantes) són OK amb el consolidador nou,
comprovat reconsolidant els 7 projectes a cost 0; el comparador ja no inventa 18 veredictes; l'agregat és un script.

## Com parlar amb el Josep (après avui)

**No parlis en codi.** «D2, D3, R6…» no li diu res encara que estigui documentat: tradueix cada codi a una frase (què
passa, on, què costa) i dona **rutes absolutes** dels fitxers clau perquè els obri a l'IDE. Va agrair explícitament la
traducció i la llista de rutes.

## Decisions que només pot prendre el Josep

1. **Commit** dels canvis d'avui (no s'ha fet: «commit only when the user asks»).
2. **Resta de la fila 0b**, en paraules: **G** = afegir a 3 fitxers d'or la nota «valor mesurat fora de la carpeta» per
   a la superfície de parcel·la (Rubí, Alcoletge, Vilanova): 3 ALERTA → OK, mitja hora. **R6** = a les taules, un
   document principal que no diu res del nivell freàtic guanya un document secundari que sí que diu «aigua» (Vilanova
   P-3, l'únic ERR de codi que queda). **I1** = la carpeta `PDF_V0` es descarta com a versió antiga encara que sigui
   l'única (Anciles, 9 cotes en blanc). **R1** = la mateixa cosa escrita de dues maneres es tracta com a contradicció
   (15 cel·les, la causa més gran). **D5** CTE amb N cases, **D4/D6** runner (docs perduts sense avís, DWG/PDF mateix
   nom), **T1/T2** temps, **S1** multi-casa (disseny). Proposta: G → R6 → I1 → R1.
3. **Paquet de preguntes a Eva** (sense canvis respecte del 09-04).

## Trampes noves

- **Reconsolidar, no re-run**, per mesurar canvis del consolidador: `consolidate_python(run_dir, project_path=…)` sobre les
  lectures cachejades + `merge_only_fields` amb el `_consolida_only.json` existent. No escriu res: l'artefacte es desa a
  `{slug}/_reconsolida-YYYY-MM-DD/`. `PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache` sempre.
- **Agregat:** `.venv/bin/python docs/wizard-headless/mesures/agrega_mesura.py [--sub _reconsolida-2026-09-05]`.
  `ledger.py` no serveix per a la mesura dels 8.
- **El comparador mesura contra l'or, no contra el signat.** Els ERR de veritat amb or prudent surten com a ALERTA:
  llegeix la columna ALERTA a mà (2 de 9 a taules són ERR reals: Rubí P-2, Vilanova P-3).
- **No afegir al comparador regles que perdonin el que ha de mesurar** (partícules, ca/es de litologies): la primera
  versió del v4 va amagar D3.
- Les d'ahir segueixen vigents (`_FOR-NEW-YOU-20260904.md` §Trampes).

## Decisions del Josep al tancament (2026-09-05, vespre) — ORDRE DE TREBALL DE LES SESSIONS SEGÜENTS

**Principi (Josep):** «encara tenim recorregut de millora de qualitat dels informes, que prioritzaria abans que
multi-casa». Primer TOTES les millores de lectura i decisió, després càlculs i informe (com a mínim P0, P2a, P2b i
M341), i només llavors el multi-casa (S1). Cada peça amb el mètode d'avui: test + reconsolidació dels 7 a cost 0
(`mesures/reconsolida_mesura.py <sub_nou> <sub_ref>`; referència actual: `_reconsolida-2026-09-05-r2`) i llista de
TOTES les cel·les que canvien. Punt de partida: escalars 105 OK / 37 CAND / 5 ALERTA / 0 ERR sobre l'or.

### Bloc 1 — Lectura i decisió (via A). Fer-les totes, en aquest ordre

| # | Peça | Què és, en paraules | Cel·les | Esforç | Necessita Eva? |
|---|---|---|---|---|---|
| 1.1 | **R5 font única del proveïdor** | El projecte de l'arquitecte o el correu del tècnic diuen la RC, la superfície o el nombre de plantes i el sistema no diu «segur» perquè cap lector sol arriba a 0,8. L'or aplica «el projecte de l'arquitecte mana»; també: ≥ 4 documents de ≥ 3 tipus coincidents amb conf ≥ 0,5 → segur; annex de sondeig com a A per als nivells | 19 | ½ dia | No |
| 1.2 | **R2 concepte veí** | La z GPS de `COORDENADES.txt` bloqueja la cota de l'annex (z de l'annex mana; la GPS va a `altres`); la data del sondeig bloqueja la de camp (regla d'Eva «1 i 6 d'octubre» o candidats amb nota: decisió Josep); nivells en msnm quan l'informe vol fondària (conversió determinista amb `cota_inici`, ja segura al mateix `_decisions.json`) | 6 (+3 taules) | 1 dia | Només la data doble |
| 1.3 | **F1 fonts d'Eva inconsistents** | Comanda 1,4 vs GTL 1,2; annex p.2 +212 vs p.1/p.3 +212,50; SPT creuats a Vilanova. Regla «qui mana» per parella de documents (el skill ja la descriu: GTL > comanda; capçalera coherent entre pàgines) | 7 | ½ dia | Sí per a Vilanova i Rubí (veure §Preguntes) |
| 1.4 | **Derivats del consolidador** | `a` del darrer nivell = «fins al fons d'investigació»; `mostra_del_nivell` = el nivell que conté `lab_depth`; litologia del nivell de la mostra | ~8 blancs de taula | ½ dia | No |
| 1.5 | **L1/L3 forats de lector** | El full SPT manuscrit (PENETROS p.3) no emet `n30` («R, 50 cops al primer tram»); telèfon enganxat a `client_name` (fitxa C6); N30 «2» en una MA. Toca el skill `g3dt-llegir-projecte` i els normalitzadors → cal re-llegir els docs afectats (cost: 1-2 lectures per projecte) | 4 | 1 dia | No |
| 1.6 | **T2 decisió sobre la passada LLM** | Costa 200-290 s i 14-23 torns fins i tot amb 1 conflicte. Mesurar, als 7 runs, si els valors que ha aplicat (`_consolida_only.json`) són millors que els candidats Python contra el signat. Si no: `G3DT_LECTURA_CONSOLIDA=python` per defecte | temps, no cel·les | 2 h | No |
| 1.7 | **R4 CTE imprès** i **persona/despatx** | `cte_*` mai segur encara que el pressupost imprimeixi C1/T1 (9 cel·les); `architect_name` persona vs despatx (Linyola: el signat escriu el despatx) | 9 + 2 | 2 h un cop respost | **Sí** (T del pressupost = T de l'informe? despatx o persona?) |

Bloc 1 sense Eva (1.1-1.6): estimació ≈ +25-30 cel·les → escalars ~85 % OK, CAND ~15 %: els dos llindars pactats.

### Bloc 2 — Càlculs i informe (el que l'Eva signa)

| # | Peça | Què és | Esforç | Necessita Eva? |
|---|---|---|---|---|
| 2.1 | **P0 columna N** | N = SPT, «--»/«R» segons R (repàs dels signats); regla N30 textual a Bell-lloc p.10 | 1 h | No |
| 2.2 | **P2a col·lapse de nivells** (Rubí) | mesura feta | 2 h | No |
| 2.3 | **P2b fondària de sabata** | decisió d'input (G.1); font nova: la frase del Qa del signat declara el nivell (encastament 20-40 cm) | ½ dia | No (decisió Josep) |
| 2.4 | **M341 mesura completa** | les 341 variables de l'informe generat vs signat (`scripts/compare_tables_vs_eva.py` + `_eva_truth`): «l'estat de tot». Últim global: 59 % del 23-ago, pre-correccions. **Abans, la línia base amb el codi actual** (memòria `feedback_measure_baseline_before_coding`) | 1-2 dies | No |
| 2.5 | P3 E per criteris, P4 regla N20 | després de M341 | 1 dia + 2 h | **Sí** (E; N20) |

Detall i estat de cada peça: `docs/PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md` §Ordre (files 2-8).

### Bloc 3 — Multi-casa (S1), NOMÉS després dels blocs 1 i 2

(a) **Capa intermèdia a la branca actual** (½ dia): detectar subcarpetes «CASA n» amb annexos propis, avís al wizard
(«2 cases: el sistema encara no les separa; revisa client, punts i nivells»), etiqueta de casa a cada fila i candidat.
És la salvaguarda: si l'Eva permet pull abans d'acabar S1, es fa pull d'aquesta branca. Es pot avançar en qualsevol
moment si un pull es fa imminent (decisió Josep). (b) **S1 sencer en una branca nova** des d'aquesta (3-4 dies):
inventari amb eix casa → selector al wizard → consolidació per casa (risc: repartir el full de camp manuscrit
compartit, cada casa té el seu P-1/S-1) → informe per casa → mesura contra l'or per casa de Tulipa. Si fa baixar la
qualitat, la branca actual queda intacta. Freqüència: 1 de 8 al corpus; cap als 16 projectes reals de maig-juliol.

### En paral·lel, sense esperar cap bloc

- **Preguntes a Eva** (`docs/PREGUNTES-EVA-PENDENTS.md` + d'aquesta setmana): T del pressupost = T de l'informe (R4),
  persona o despatx a `architect_name` (Linyola), SPT P-1/P-3 creuats a Vilanova (signat vs annex+tall), cota P-2 de
  Rubí (+212 vs +212,50), E (P3), regla N20 (P4), «`de` del nivell 1 = base de la capa vegetal». Sense elles, ~20
  cel·les no baixen de CAND.
- **Desplegament**: Claude Code a l'ordinador de l'Eva (via A com a lector de producció) i tier de subscripció
  (memòria `project_eva_subscription_model_tier`); merge cap a `production/g3dt-eva-v1` quan ella permeti pull.
  Via B: només confirmar amb l'Eva els 3 fixes pendents (Tulipa render, sondeig refús, None depth); no tocar-la més.
