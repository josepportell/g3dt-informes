# Anciles — diagnòstic de tot el que no és OK contra el signat

**Data:** 2026-09-04 · **Mètode:** JSON del run, `_inventory.json`, `_eva_truth/anciles.json` (PDF amb capa de text,
transcrit), `eva_reference_values.json`, ors, `consolidate.derived_field_signals`, `inventory.py`. Cap re-run.
Taxonomia: `../_DIAGNOSTICS-INDEX.md`.

## I1 — la regla «`PDF V0` = versió anterior» deixa Anciles sense cap cota

`inventory.py` (l. 12-17, 150) exclou `PDF-V0/`, `PDF V0/`, `PDF_V0/`, `LLETRA/`, `*.FH11`… com a «versions
anteriors / no llegibles». A Bell-lloc o Linyola és correcte (hi ha `PDF/ANNEXES/` vigent). A Anciles **no hi ha `PDF/`**:
els annexos DPSH i sondeos només són a `PDF_V0/ANEJOS/` (`route=skip, exclos_carpeta`), i l'original és `.FH11`
(FreeHand, `annex_freehand_no_llegible`). Resultat: cap senyal de `cota_referencia` ni de `cota_inici`/`cota` a cap
document → **9 cel·les en blanc** (1 escalar + 6 DPSH + 2 sondeig) que l'or omple des d'aquests mateixos PDF
(«+1106,40 / +1106,30 / +1106,40 / +1106,30 / +1106,42 / +1106,65; S-1 +1106,65; S-2 +1106,42; origen: topogràfic del
client»). Signat: idèntic. Fix: si no existeix `PDF/` (o cap annex vigent del mateix tipus), llegir `PDF_V0/` amb
`doc_type_hint=annex_v0` i nota «versió 0» al senyal. Blanc honest, però evitable.

## D5 — la derivació CTE usa la superfície d'UNA tipologia, no del total

`derived_field_signals("cte_edificacio")` (l. 1008-1018): `C1 si total > 300 m²`. `_superficie_construida(corpus)` ha
agafat **186,18 m²** de `A01_TIPOL.pdf` (una tipologia de les 7 cases adossades) → «C0». El skill diu «superfície
construïda TOTAL de l'encàrrec»; l'or: 1.264 m² > 300 → **C-1**. Cap senyal `superficie_construida` a `fields` (null),
la derivació ha agafat un senyal de tipologia. Cal el factor «N unitats» (el mateix concepte que el guard `num_floors`
«1 de N») abans de derivar. Candidats (guard R4), però candidat equivocat.

## Escalars — 11 cel·les no-OK (de 22)

| Camp | Cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `cota_referencia` | BUIT | Vegeu I1. | **I1** |
| `cte_edificacio` | CAUTELA «disjunts» → CAND (equivocat) | Vegeu D5. | **D5** (+R4) |
| `num_soil_levels` | ALERTA → **OK** | Prod segur 2 (tall LEYENDA, A); signat 2 nivells («1er nivel… / 2do nivel…»). L'or era candidats. | — |
| `building_type` | ALERTA → CAND | Candidats: «vivienda adosada (7 unitats)» (tall) / «7 adosados (residencial), PB+1PP+BC» / `CONSTR GRUPO DE VIVIENDAS` + `EG 7 VIVIENDAS ANCILES` (G3). Signat «7 viviendas unifamiliares adosadas». Bloqueig per abreviatures G3 (**R1, 7/7**); el comparador no iguala ca/es («adosada»/«adossats»). | **R1** + C |
| `client_name` | ALERTA → CAND | Candidat 1 «MARIA ALBA BARRAU CASTÁN 616523792» (fitxa C6, **amb el telèfon enganxat**), sol·licitant al pressupost, promotor del plànol «ANDRÉS AMAT y ENRIQUE M. GARDETA» (estudi de detall, no aquest encàrrec). Signat «SRA. ALBA MARIA BARRAU CASTÁN». Sense A (fitxa C6 = sol·licitant, regla G3). | R5 + **L3** (brossa al valor) + C |
| `architect_name` | CAUTELA «disjunts» → CAND | «ALBA BARRAU, nºCol. 6.408 / MIRIAM CASTEL, nºCol. 6.703» = or «ALBA BARRAU (nºCol. 6.408) i MIRIAM CASTEL (nºCol. 6.703)». Format. | C |
| `lab_testing_company` | CAUTELA «disjunts» → CAND (correcte) | Prod «TPS, Prospecció del Subsòl, SL». L'or mostra «MA (S-2) 2,8-3,0» com a candidat: candidats compartits del camp niuat `lab` (`flat_gold_scalars`). | C |
| `referencia_catastral` / `superficie_parcela` / `street_address` | CAUTELA → CAND | Font única: projecte de l'arquitecte (RC 6184504BH9158N0000SS, 1.655,01 m², C/ General Ferraz, 20). Or segur («el projecte mana»). | **R5** |
| `architect_company` | NOU | Sense or. | — |

**Sobre el signat: 12 OK / 8 CAND / 1 blanc / 0 ERR** (21 amb or).

## Taules — no-OK contra el signat

| Cel·la | Cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `dpsh_tests[*].cota_inici` ×6, `sondeig_tests[*].cota` ×2 | BUIT | Vegeu I1. Signat: +1106.40/.30/.40/.30/.42/.65; S-1 +1106.65, S-2 +1106.42. | **I1** |
| `sondeig_tests[*].profunditat_assolida/.spt_ma/.nivell_freatic` ×6 | CAUTELA → CAND (correctes) | Única font: full manuscrit «PENETROS + SONDEIGS.pdf» (conf < 0,8, sense annex de sondeig llegible — vegeu I1). Valors = signat (−2,40 / 1/0 / No detectat; −3,00 / 1/1 / No detectat). | **R5** (+I1) |
| `spt_ma_tests[*].profunditat` ×3 | CAUTELA → CAND (correctes) | Mateixa font única. | R5 |
| `spt_ma_tests[2].n30` (MA-1) | ALERTA → CAND (espuri) | Prod candidat «2» per a una mostra alterada; signat «--». Una MA no té N30: el lector ha pres un número del full (cops?) com a N30. | **L3** |
| `spt_ma_tests[*].litologia` ×2 | (no_trobat) | Manuscrit; signat «Arcilla arenosa con gravitas». Blanc honest. | L2 |
| `spt_ma_tests[*].id_estat/.litologia_del_nivell/.assaig_encarregat` ×7 | ABSENT | Columnes només del fixture de l'or. | C |
| `soil_levels[*].de/.a/.mostra_del_nivell` ×6 | BUIT | Derivats no implementats (transició ~−2,55 m a S-2). | conegut |

**Sobre el signat: 22 OK / 0 ERR / 14 blancs (8 I1 + 6 coneguts) / 10 CAND.**

## Què aporta Anciles al quadre dels 8

1. **I1 és el forat de cobertura més gran de la mesura** (9 blancs) i és d'una línia d'inventari: una regla pensada
   per a carpetes amb `PDF/` vigent fa que el projecte sense `PDF/` perdi tots els annexos. Detectable en sec
   (inventari), sense cap crida.
2. **D5**: la derivació CTE necessita el nombre d'unitats; a Castellar (3 cases) i Anciles (7) la superfície per
   tipologia enganya. Mateix concepte «1 de N» que el guard de `num_floors`.
3. **R5 dominant**: 9 cel·les de taula i 3 escalars en candidats correctes per «font única / manuscrit». Amb l'annex
   de sondeig (I1) la meitat pujarien a A.
4. **R1 7/7** a `building_type`. **L3** nou: brossa dins del valor (telèfon a `client_name`, N30 a una MA).
5. Cap ERR: quan el sistema no té la font, es queda en blanc o en candidats — el comportament pactat.
