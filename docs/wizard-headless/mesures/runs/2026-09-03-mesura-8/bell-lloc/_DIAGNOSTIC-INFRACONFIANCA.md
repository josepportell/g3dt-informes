# Bell-lloc — diagnòstic de la infraconfiança (10 CAUTELA «or segur, prod candidats amb el bo dins»)

**Data:** 2026-09-04 · **Mètode:** només lectura dels JSON del run (`tier_a` per document + `_decisions.json`) i del
codi de `automation/lectura/consolidate.py` (`decide()`, `_guard_for_field()`, constants). Cap crida, cap re-run.

## Troballa principal

**Cap dels 10 és un error de lectura.** En els 10 camps el valor correcte és `value` (el primer candidat) i els
lectors per document l'han trobat amb la font i la cita correctes. La confiança es perd **tota a la consolidació**:
la política de `decide()` converteix en «candidats» cel·les on totes les fonts diuen el mateix. Cinc causes arrel:

| # | Camp | Motiu de `decide()` | Causa arrel | Tipus |
|---|---|---|---|---|
| 1 | `architect_name` | contradicció: `ARQ BOSCH NOVELL` (1 doc, 0,50) | 6 docs diuen «Jordi Bosch Novell» (4 d'autoritat A); el caixetí del sondeig escriu el **despatx abreujat** i, amb conf 0,50 ≥ 0,40, bloqueja. El propi lector anota que és l'arquitecte. (Doble pany: el guard «persona i despatx a la vegada» també saltaria.) | R1 |
| 2 | `lab_testing_company` | contradicció: `TPS, S.L.` (1 doc, 0,60) | 2 GTL (A, 0,90) «TPS, Prospecció del Subsòl, SL (B64803075)» vs la **forma curta** de la casella «Empresa» del sondeig. Mateixa entitat (memòria `gtl_lab_identity`: el lab és sempre TPS). | R1 |
| 3 | `building_type` | contradicció: `CONSTR HABITATGE` (0,70); `EG HAB UNIF BELL-LLOC` (0,60) | 8 docs «habitatge unifamiliar aïllat» (3 A). Els bloquejadors són les **abreviatures de plantilla G3** (comanda lab N18, PLAN_COST E9) que el consolidador no expandeix. **Sistemàtic: Castellar cau igual** (`CONSTR 3 HAB UNIF` / `EG 3 HAB UNIF CASTELLAR…`). | R1 |
| 4 | `municipality` | formes diferents entre fonts A (compatibles per prefix) | Tres formes A del mateix municipi: `BELL.LLOC D'URGELL (Lleida)` (A.01, punt en lloc de guionet), `Bell-lloc d'Urgell`, `Bell-lloc`. El padró (`municipis.lookup`) resol les dues últimes al mateix registre; el consolidador **no canonicalitza abans de comptar `a_keys`**. | R1 |
| 5 | `field_date` | contradicció: `2025-10-06` (5 doc, 0,70) | Campanya de **dos dies**: DPSH 01/10 (fitxa F38 = A, annex DPSH, PENETROS) i sondeig 06/10 (comanda «DATA DE PRESA» 0,70, annex sondeig 0,50, GTL 0,30). Els lectors ja anoten «dia del sondeig, no necessàriament el primer dia de camp», però la conf ≥ 0,40 bloqueja. Regla d'Eva (EXPLICACIÓ DETALLS, citada a l'or): «si la data del sondeig no és igual, posar els dos dies». Castellar (un sol dia) no ho pateix. | R2 |
| 6 | `cota_referencia` | contradicció: `±0,00 respecte C/Antoni Bellet` (0,60); `198.9` (0,50) | Annex sondeig z=199,50 (A, 0,85) + annex DPSH «+199.50 msnm segons ICGC» (0,75). Bloquegen **dos conceptes diferents**: la declaració de datum relatiu del full de camp i la z GPS de COORDENADES.txt (que el lector Python ja anota «Eva no l'usa»). Cadena de prioritat coneguda: usuari > z annex sondeig > ICGC (memòria `vision_normalizer_and_cota_referencia`). | R2 |
| 7 | `num_floors` | guard: descripció d'una sola unitat de N | **Fals positiu de substring**: el guard busca `"1 de"` a la nota i l'ha trobat dins de «PB de 280 m2 + **P1 de** 86 m2». Cinc fonts (3 A) diuen PB+PP/PB+1. A Castellar el mateix guard és legítim (3 habitatges). | R3 |
| 8 | `cte_edificacio` | guard: mai segur per a aquesta cel·la | `_NEVER_SEGUR_FIELDS` aplica a TOTS els casos la regla del skill que és **només per a derivacions** («quan el pressupost no porta la línia CTE… sempre candidats, mai segur»). Aquí el pressupost G3 imprimeix «Tipus d'edifici: C1» (0,80) + correu «És un C1» (0,90). Or: segur. | R4 |
| 9 | `cte_sol` | guard: mai segur per a aquesta cel·la | Idem: pressupost «Tipus de Terreny: T1». **Però** el T del pressupost és una hipòtesi prèvia a l'estudi; el T de l'informe el decideix l'estudi. Bell-lloc coincideix (T-1); no sabem si sempre. | R4 |
| 10 | `num_soil_levels` | cap font A (< 0,8) i sense convergència de 3 docs | 5 documents diuen «1» amb 0 contradiccions (tall 0,75, annex tall 0,70, annex sondeig 0,55, DPSH xls 0,30, annex DPSH 0,20). Cap arriba a 0,8 perquè cada lector, sol, diu «creuar amb els altres»; només 2 passen el 0,6 de `CONV_CONF`. Humilitat individual + llindar = ningú confirma. | R5 |

## Causes arrel i què caldria

| Causa | Camps | Fix | Risc per a ERR = 0 |
|---|---|---|---|
| **R1 — mateixa entitat, formes diferents** tractades com a contradicció | 1, 2, 3, 4 (+ Castellar 3) | Equivalència per camp a `value_key`/`cluster_signals`: persona ⊂ despatx (cognoms compartits), raó social curta ⊂ llarga (`TPS`), expansió de les abreviatures G3 (`EG HAB UNIF`, `CONSTR HABITATGE` → tokens de `building_type`), canonicalització de municipi via padró abans de `a_keys` (només quan TOTES les formes A resolen al mateix registre; `BELL.LLOC` → normalitzar `.`→`-` i treure «(Província)» és ortogràfic, no difús) | Baix si l'equivalència exigeix contenció real de tokens; **mai** «el més semblant». Els casos que van motivar la cautela (18A/18B, CATELLAR) són d'un altre eix i queden intactes |
| **R2 — un concepte veí entra com a bloquejador** | 5, 6 | `field_date`: senyals anotats «sondeig» no bloquegen; si DPSH ≠ sondeig, **valor = «1 i 6 d'octubre»** (regla d'Eva) o candidats [DPSH, sondeig] amb nota — a decidir. `cota_referencia`: z de l'annex de sondeig (A) mana; datum relatiu i z GPS van a `altres` | Mitjà: toca criteris d'Eva (data doble; sistema relatiu de Castellar). Decisió del Josep / pregunta a Eva |
| **R3 — bug del guard `"1 de"`** | 7 | Regex amb límit de paraula (`(?<![a-z0-9])1 de \d`), o buscar «1 de N» amb N ≥ 2 | Nul |
| **R4 — «mai segur» sobregeneralitzat** | 8, 9 | Treure `cte_*` de `_NEVER_SEGUR_FIELDS` (les derivacions ja queden a candidats per `is_derived_only`) **només si** Eva confirma que el T del pressupost és el de l'informe; si no, `cte_edificacio` sí i `cte_sol` no | Depèn d'Eva (pregunta al paquet `PREGUNTES-EVA-PENDENTS`) |
| **R5 — convergència amb lectors humils** | 10 | Regla addicional: ≥ 4 documents de ≥ 3 tipus diferents coincidents amb conf ≥ 0,5 i cap contradicció → segur; o el tall (autoritat pel nombre de nivells, Pas 3b) puja a A quan la llegenda numera els nivells | Baix-mitjà: cal mesurar-ho als 8 (Rubí té col·lapse de nivells, P2a) |

**Si només s'apliquessin R1 + R3** (sense tocar criteris d'Eva): Bell-lloc passaria de 11/21 OK (52 %) a **16/21 (76 %)**;
amb R2 també, 18/21 (86 %) ≥ llindar. Res d'això s'aplica ara: la mesura dels 8 es fa amb el codi intacte.

## Notes laterals

- **Castellar `cte_sol` «candidats disjunts»** (or `C0 (…)` vs prod `T-1`) és un artefacte del comparador: la llista
  de candidats del camp niuat `cte` es comparteix entre `cte_edificacio` i `cte_sol` (`flat_gold_scalars`, comentari
  al codi), així que el candidat d'edificació apareix com a or de sòl. No és ni error del sistema ni de l'or.
- `architect_name` a Castellar és «només candidats derivats» (no hi ha arquitecte als documents) — cas diferent.
- Els lectors per document fan bé la seva part: en els 10 casos la nota del senyal bloquejador ja diu per què NO
  hauria de bloquejar. El consolidador no llegeix les notes (només conf i forma). És la pista de per on obrir R1/R2.
