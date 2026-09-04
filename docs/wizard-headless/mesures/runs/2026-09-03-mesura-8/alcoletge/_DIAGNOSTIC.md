# Alcoletge — diagnòstic de tot el que no és OK contra el signat

**Data:** 2026-09-04 · **Mètode:** JSON del run, `_eva_truth/alcoletge.json`, ors, `compare_consolida.parse_address`,
`_telemetry.jsonl`. Cap re-run. Taxonomia: `../_DIAGNOSTICS-INDEX.md`.

## Escalars — 8 cel·les no-OK (de 22)

| Camp | Cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `street_address` | «ERR» → **OK** | Prod segur «Carrer Girasols, Nº7, Urbanització el Roser» (A.01 Situació A; annex DPSH; pressupost OBRA «C/GIRASOLS 7, URB.EL ROSER»). Or «Carrer Girasols, 7 (Urb. El Roser)». `parse_address(prod)` = via `('girasols','urbanitzacio','roser')`, portals `{7}`; `parse_address(or)` = via `('girasols',)`, portals `{7}` → «vies diferents». El sufix d'urbanització sense parèntesi entra als tokens de la via. Prova: Cadastre → 8841701CG0184S, 1167 m² = signat. **Fals ERR del comparador.** | **C** |
| `superficie_parcela` | ALERTA → **OK fora** | Prod 1167 (Cadastre, portal 7). Signat «Superfície de la parcel·la segons cadastre: 1167». Or no_trobat sense `fora_carpeta` (proposava exactament aquesta consulta). | **G** |
| `building_type` | CAUTELA → CAND | «Tancament de porxo en casa unifamiliar (ampliació…)» (planol-1), «Ampliació d'habitatge unifamiliar» (correu ×3, 0,75), «Ampliació d'un edifici (habitatge)» (annexos ×3, 0,75) + `CONSTR HA…` (comanda G3). Tres redaccions del mateix títol + abreviatura G3. L'or tria «ampliació d'un edifici (habitatge unifamiliar)». Eva re-redacta: CAND raonable, però el bloqueig per l'abreviatura és R1 (**5/5**). | **R1** |
| `cota_referencia` | CAUTELA → CAND | Annex DPSH «+188,20 msnm segons ICGC» (A, p.1-3) bloquejat per la z GPS de COORDENADES.txt **198,9** (0,50) — que aquí és una anomalia de 10,7 m (l'or la descarta). Signat +188,20. **3/3 projectes amb COORDENADES.txt + annex** (Bell-lloc, Linyola, Alcoletge). | **R2** |
| `cte_edificacio` / `cte_sol` | CAUTELA → CAND | Pressupost imprimeix C0 / T1; signat C-0 / T-1. `_NEVER_SEGUR_FIELDS`. | **R4** |
| `referencia_catastral` | CAUTELA → CAND | «8841701CG0184S0001HH» d'una sola font (correu del tècnic, conf < 0,8) + «98417» (plànol cadastral, fragment). L'or l'accepta com a A del proveïdor. El Cadastre ha calculat **la mateixa RC** (8841701CG0184S) per a la superfície i no s'ha creuat amb la declarada: amb el creuament seria segur. | **R5** (+D1 inversa) |
| `architect_company` | NOU | Sense or. «2 Graus» / «GRAUS (David Graus Robinat)» — persona/despatx (R1) si mai té or. | — |

**Sobre el signat: 16 OK / 5 CAND / 0 ERR** (21 amb or).

## Taules — 9 cel·les no-OK (de 25)

| Cel·la | Cru → sobre signat | Causa | Codi |
|---|---|---|---|
| `dpsh_tests[*].nivell_freatic` ×3 | CAUTELA «disjunts» → CAND (contingut correcte) | Prod candidat 1: «Humitat (…cel·les F22-F24 pintades de blau…) — fondària de primera aparició -1,00 m; abast fins a -1,40 m» (lector de l'Excel DPSH: llegeix el **color de cel·la**, sense text); candidat 2: «~187,2 msnm (humitat)» del tall; candidat 3: «No detectat». Or «-1,00 m (humitat)»; signat «Humitat (m): -1.00» ×3. Mateix valor, text llarg que el comparador no iguala; el candidat en msnm és R2. | **C** + R2 |
| `soil_levels[0].a` / `[1].de` | CAUTELA «disjunts» → CAND | Contactes en **msnm** llegits de l'eix del tall («~186,8 a P-1, ~187,0 a P-3»); or en fondària («-1,4 m P-1/P-3, -1,2 m P-2»). 188,2 − 1,4 = 186,8. Mateix cas que Linyola: quan el tall porta escala msnm, el lector la copia i l'informe vol fondàries. | **R2** (sistema) + C |
| `spt_ma_tests[0].litologia` | CAUTELA → CAND (feble) | Full SPT manuscrit: «[primera paraula il·legible] marró». Or «Lutites (Nivell 2)» (per fondària); signat «Llims compactes, lutites alterades» (Eva redacta). El lector no inventa: bé. Pista per a un derivat: litologia del nivell on cau la mostra (0,8-1,4 m dins N1/N2). | **L2** (manuscrit il·legible) |
| `soil_levels[0].de` | BUIT | Or «0,00 m (+188,20)». Sense fila de cobertura, el nivell 1 arrenca a superfície; a Rubí la regla `cover_de` posa 0,00 només a la cobertura. Derivat no implementat per al nivell 1. | conegut (derivat) |
| `mostra_del_nivell` ×2 | BUIT | Assignació mostra ↔ nivell per fondària (SPT 0,8-1,4 vs contacte -1,2/-1,4): derivat no implementat. | conegut (derivat) |

**Sobre el signat: 16 OK / 0 ERR / 3 blancs / 6 CAND.**

## Operació — T1: timeout de 600 s a PENETROS

`PENETROS.pdf` intent 1: 600 s, **cap stdout** (log de 27 bytes: «--- stdout (no JSON) ---»), `rc=None` → el CLI
no ha respost en 10 min (penjada, no lentitud: l'intent 2 fa 42 torns en 511 s). Cost: +10 min i 1 crida perduda.
PENETROS és el document més lent a 4/5 projectes (Bell-lloc 449, Rubí 382, Linyola 480, Alcoletge 511 s): el
topall `G3DT_LECTURA_TIMEOUT=600` hi queda a tocar. Dues coses a mirar després de la mesura: (a) detectar la
penjada abans (sense cap byte de stdout als 120 s → matar i reintentar); (b) o pujar el topall només per a
PENETROS. No és un defecte de lectura: el resultat final és correcte (taula DPSH 100 % OK).

## Què aporta Alcoletge al quadre dels 8

1. **Cap ERR de sistema.** L'ERR cru és el 3r fals positiu del comparador en adreces (Linyola CP com a portal i
   «C.»; Alcoletge sufix d'urbanització): **abans d'agregar els 8 cal arreglar `parse_address`**, si no el titular
   surt amb ERR que no existeixen.
2. **R1 5/5, R2 (z GPS) 3/3, R4 (CTE imprès) 3/3, R5 (font única del proveïdor) 3/3, G (`fora_carpeta` absent) 2/2**
   des que el Cadastre multi-portal està ON: les causes ja no són d'un projecte, són del consolidador.
3. **T1**: penjada del CLI sense stdout, recuperada pel reintent. Mesurar quantes vegades passa als 3 que queden.
4. **L2**: manuscrit il·legible tractat honestament («[il·legible] marró»). És el comportament desitjat (mai inventar);
   el que falta és el derivat «litologia del nivell on cau la mostra».
