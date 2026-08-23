# Hold-out headless del skill `g3dt-llegir-projecte` — Resultats

**Data:** 2026-08-23 (nit) · **Skill provat:** v0.4 · **Veredicte: ERR = 0 mesurat (3/3 projectes)** — les 3 regles
apreses a la lectura d'or (2 ERR + 1 CAND−) han evitat l'error en re-execució cega.

## 1. Metodologia

3 subagents frescos (un per projecte, sense cap context de la sessió), amb el skill v0.4 com a únic playbook, sobre les
còpies de Windows (`/mnt/c/claude/g3dt/projectes{,-debug}/`). Prohibicions explícites: `validation/`, `docs/golden-read/`
(inclòs `_LESSONS.md`), `reference-material/`, qualsevol `*informe*`/`*_generated*`/`eva_reference_values*`/`_user_data_prev*`,
memòria del projecte. Pas 6 (comparació amb l'Eva) exclòs de l'encàrrec: l'últim pas de l'agent és `_decisions.json`.
La comparació d'aquest document l'ha fet l'orquestrador a posteriori, contra els `_decisions.json` d'or i els veredictes
per camp contra l'Eva ja registrats a `docs/golden-read/`.

Projectes triats: **Castellar** i **Linyola** (on van sortir els 2 ERR de la lectura d'or — el hold-out havia de demostrar
que les regles v0.4 els eviten) i **Tulipa** (el cas estructural: 1 expedient, 2 informes, DWG dins de zip).

Execució: ~205-214k tokens i ~19-21 min per agent; 0 $ d'API (subscripció). Sortides: 18+20+21 JSON de font +
3 `_decisions.json`, tots vàlids, a `docs/holdout-headless/{expedient}/`. Cap escriptura a les carpetes de projecte.

## 2. Les 3 regles apreses, verificades

| Regla (origen) | Lectura d'or | Hold-out v0.4 | Verificat |
|---|---|---|---|
| `lab_sample_id`: annex de l'Eva > GTL > comanda (ERR #1, Castellar) | "MA-1" **segur** → ERR | `candidats` [**SPT-1** ▸ MA1 ▸ MA] — l'informe de l'Eva diu SPT-1 | ✅ ERR→CAND, correcte 1r |
| `architect_name` persona vs despatx = candidats (ERR #2, Linyola) | "Josep Bunyesc" **segur** → ERR | `candidats` [persona ▸ **despatx** ▸ Laia Alarcón] — l'informe diu el despatx | ✅ ERR→CAND |
| CTE derivat amb superfície TOTAL de l'encàrrec (CAND−, Castellar) | C-0 sol → correcte fora de llista | `candidats` [**C-1** (360 m²) ▸ C-0] — l'informe diu C-1 | ✅ CAND−→CAND, correcte 1r |

## 3. Taula per camp (vs informe de l'Eva, criteris ANALISI §7.1)

### Castellar (15 cel·les): 8 OK / 5 CAND / 1 NT / 1 n/a / 0 ERR — or: 10 OK / 2 CAND(1−) / 1 NT / 1 n/a / **1 ERR**

| Camp | Hold-out | vs Eva | vs or |
|---|---|---|---|
| expedient, client_name, street_address, municipality, field_date, num_soil_levels, num_dpsh_tests | segur | OK ×7 | = |
| utm+rc | segur **P-1** 423167/4609608 (rc: NT, Eva no en té) | OK | millor (l'or havia triat S-1; regla "UTM informe = P-1" aplicada) |
| cota_referencia | candidats [−4,0 relatiu 1r] | CAND (correcte 1r) | millor ordenació |
| lab | company/depth segur; sample_id candidats [SPT-1 1r]; location S-1 | CAND | **era l'ERR #1** |
| cte | candidats [C-1 1r, T-1] | CAND | **era el CAND−** |
| building_type | candidats (or: segur) | CAND | ↓ prudent |
| num_floors | candidats [PB+1] (or: segur) | CAND | ↓ prudent (descripció d'1 unitat, obra de 3) |
| superficie_parcela | no_trobat (Eva: 1.284 del visor, a cap fitxer) | NT | = |
| architect_name | candidats [client, pràctica Eva] | n/a (absent a la ref.) | = |

### Linyola (15 cel·les): 13 OK / 2 CAND / 0 ERR — or: 13 OK / 1 CAND / **1 ERR**

| Camp | Hold-out | vs Eva | vs or |
|---|---|---|---|
| expedient, client, street, municipality, building_type, num_floors, superficie, field_date, cota, soil, dpsh, lab | segur | OK ×12 | = (client per "qui signa l'acceptació"; lab SPT-1/P-3/1,00-1,15 complet) |
| utm+rc | utm segur P-1; rc `candidats` amb el valor correcte únic (or: segur) | OK | ↓ prudent en rc (només impresa al plànol de l'arquitecte) |
| architect_name | candidats [persona ▸ despatx ▸ Laia] | CAND (Eva = despatx, a la llista) | **era l'ERR #2** |
| cte | candidats [C-0 1r, T-1] | CAND (correcte 1r) | = |

### Tulipa casa 1 (16 files, convenció de l'or): 8 OK / 1 CAND / 3 NT / 4 n/a / 0 ERR — or: 7 OK / 2 CAND / 3 NT / 4 n/a / 0 ERR

Diferència: `num_floors` **segur** PSOT+PB+1PP pel correu de VUA amb superfícies per planta (regla DWG explícita del skill)
— coincideix amb l'Eva (S+Pb+Pp): CAND→OK legítim. La resta idèntic a l'or (client Aleix Subirà p.5 signat, 2 informes
detectats, cota candidats 198/199, superficie NT* condicionada al conversor DWG, utm/rc NT). `architect_name` baixat a
candidats per la regla persona/despatx nova (l'or el tenia segur, pre-regla): n/a a la referència, direcció correcta.
Nota cte: segur C-1/**T-1** (línia del pressupost); el pipeline computa T-2 des dels N20 — la T del pressupost és previsió,
no terreny mesurat (referència de Tulipa = informe generat, no de l'Eva → n/a; matís anotat).

### Tulipa casa 2 (sense referència de l'Eva): consistent amb l'or en 15/15 camps

2 divergències d'estat, totes prudents: `architect_name` FACTORIA segur→candidats; `client_name` "Jordi Gené"
no_trobat→candidats a 0,25 (mateix nom, mateixa font: metadades /Title). Situació estructural (2 informes, sondeig
compartit, MODF -2CASES) detectada i aplicada per l'agent sense ajuda.

## 4. Totals

| | OK | CAND | NT | n/a | **ERR** |
|---|---|---|---|---|---|
| **Hold-out (46 cel·les)** | 29 | 8 | 4 | 5 | **0** |
| Or, mateixos 3 projectes | 30 | 5 (1 era CAND−) | 4 | 5 | **2** |

Sobre cel·les puntuables (OK+CAND+ERR = 37): **OK 78,4 % / CAND 21,6 % / ERR 0 %**. L'OK% queda 2 punts sota l'objectiu
del 80 % pel preu de 3 rebaixes prudents segur→candidats (building_type i num_floors de Castellar, rc de Linyola) — el
tracte correcte segons la mètrica que mana (ERR=0). **Cap divergència en direcció perillosa**: ni un candidats→segur
equivocat, ni un segur incorrecte, ni un no_trobat amb el valor present.

## 5. Caveat honest: leakage del skill (detectat per l'agent de Linyola)

El skill v0.4 anomena explícitament BUNYESC/Linyola, Castellar, Anciles i Tulipa en regles concretes (persona/despatx,
"qui signa l'acceptació" amb 2 promotors, derivació CTE, multi-informe). Per a aquests projectes el hold-out **no** mesura
generalització: mesura (a) que un agent fresc pot executar el skill de cap a cap sense context ni preguntes, i (b) que les
regles, aplicades cegament, reprodueixen les decisions correctes amb ERR=0. La generalització real només es podrà mesurar
amb carpetes noves de l'Eva (ANALISI §7.4: les plantilles G3 són el seu procés; si no hi són, el sistema degrada a
candidats, no a errors — comportament desitjat).

## 6. Feedback dels 3 agents sobre el skill (or per a la v0.5)

Regles que els han semblat poc clares o insuficients, per ordre d'impacte:

1. **`lab_location` no definit** (Castellar): el skill el llista però no diu què és ni d'on surt.
2. **CTE multi-casa amb línia única** (Tulipa): la línia C-1 del pressupost cobreix N cases de superfícies desconegudes.
3. **Cotes per punt sense cota única** (Tulipa casa 2): 201,25/202,85 i cap és "la" referència.
4. **Instrucció del client posterior als annexos** (Castellar): el títol dictat el 18/11 contradiu la redacció dels annexos del 03/11.
5. **Descripció d'1 unitat en obra de N** (Castellar): el WhatsApp descriu 1 dels 3 habitatges → num_floors.
6. **RC impresa al plànol de l'arquitecte** (Linyola): no és cap font canònica del skill.
7. **Col·legiació a la signatura de correu** (Tulipa): font potent d'architect_name que la prioritat no llista.
8. **num_floors derivat del projecte sencer** sense taula de planejament (Linyola: "tot el programa és PB").
9. **lab compartit entre cases** (Tulipa): l'informe de la casa sense sondeig, porta el bloc lab de l'altra?
10. Menors: client=arquitecte coincident (no descartar el nom per ser sol·licitant); albarà "SPT: No" amb SPT documentat;
    superficie amb única font (segur admès, anotar "única font"); cantonada sense segona adreça documentada (nota, no candidats).

## 7. Conclusió

**GO de la via A pel que fa al lector**: el skill és executable headless per un agent sense context, amb ERR = 0 en
re-execució i degradació sempre en direcció prudent. Queda fora d'aquest hold-out (i segueix pendent): conversor DWG,
n/a de referències (Vilanova/Anciles), Fase 4a, crida des del wizard i UI de candidats, i la validació amb projectes
nous de l'Eva.
