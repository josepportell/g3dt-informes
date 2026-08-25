# Lectura d'or de TAULES — resultats (2026-08-24)

**Què:** 8 agents frescos i cecs (1 per projecte, skill `g3dt-llegir-projecte` v0.8 com a únic playbook, prohibit obrir
informes/generated/validation/golden-read), llegint els blocs de taules del Pas 3b: `dpsh_tests[]`, `sondeig_tests[]`,
`spt_ma_tests[]`, `soil_levels[]`, `superficie_construida`. Comparació feta per la sessió principal contra els informes
signats de l'Eva (5 .docx + Alcoletge .doc convertit + Anciles PDF V0 transcrit; veritat a `_eva_truth/`).
Vilanova (el PDF no porta el cos amb taules) i Tulipa (sense informe d'Eva) = n/a, només consistència.

## Totals per cel·la (6 projectes comparables)

| Projecte | OK | CAND (bo entre candidats) | ERR | NT | n/a | notes |
|---|--:|--:|--:|--:|--:|---|
| BELL-LLOC | 14 | 4 (+1 CAND* fora) | 0 | 0 | 0 | n30: informe 54 ≠ tall 58 de la mateixa Eva — incoherència interna, pregunta oberta |
| CASTELLAR | 23 | 5 | **1** | 0 | 0 | ERR: cota sondeig absoluta (570,90) vs relativa d'Eva (-4,20) → regla v0.9 |
| RUBI | 14 | 7 | 0 | 0 | 0 | criteri N30 trams centrals confirmat (40) |
| LINYOLA | 18 | 4 | 0 | 0 | 0 | prof. SPT corregida sobre l'Excel per la cadena GTL>camp>comanda |
| ALCOLETGE | 13 | 8 | 0 | 1 | 0 | B81; N.F./Nivells per COLOR de cel·la; columna 'Humitat' d'Eva |
| ANCILES | 31 | 7 | 0 | 0 | 1 | 6 cotes per punt exactes; format triple SPT/TP/MA |
| **total** | **113** | **35 (+1\*)** | **1** | 1 | 1 | |

Sobre 150 cel·les comparables: **OK 75 %, OK+CAND-encertat 98,7 %, ERR 1 (0,7 %)**.
VILANOVA: n/a (consistència amb annexos 100 %). TULIPA: n/a (estructura 2 cases correcta en re-execució).

## L'ERR i les regles noves (→ skill v0.9)

1. **ERR (Castellar): la cota del sondeig a la taula segueix el SISTEMA de cotes del projecte** — si els DPSH van en relatiu,
   el sondeig també; el `z:` absolut de l'annex és `cota_referencia`, no la cel·la de la taula. Sistema mixt → candidats.
2. **El peu "Rebuig a -X,XX m" no és sempre B80**: zona B79-B82 (B81 a Alcoletge i Tulipa).
3. **N.F. i Nivells de l'Excel poden ser COLORS de cel·la** (llegenda files 79-80; cal `formatting_info=True`); i la llegenda
   pot ser només plantilla (Tulipa) — una llegenda no és una transició.
4. **n30 MAI segur**: registre segur + candidats de la suma. El criteri d'Eva no és estable (3 projectes = trams centrals;
   Bell-lloc informe 54 ≠ tall 58 ≠ centrals 62). **Pregunta per a l'Eva.**
5. **Micro-regles de format** (el generador formata, el lector emet dades): spt_ma per comptes ("1/--" vs "1/0" vs "1/0/0");
   superficie_construida amb components i total ("72+20"→"92"); capçaleres adaptatives de l'Eva ("Humitat (m)" vs "Nivell
   freàtic"; "(m*)" vs "(msnm*)"; etiqueta de parcel·la segons font — 3a variant vista: "segons informació aportada").

## Validacions positives (regles v0.7/v0.8 que han funcionat en cec)

- Cotes per punt i RELATIVES (Castellar -4,0/-4,2 = informe; Anciles 6 cotes diferents = informe exactes).
- Profunditat = peu "Rebuig a" exacte: 23/23 cel·les de profunditat DPSH idèntiques a l'informe en els 6 projectes.
- Litologia annex-sondeig-primer: candidat 1 quasi literal a Bell-lloc, Castellar, Anciles.
- lab_sample_id (l'ERR històric d'escalars): Castellar re-executat en cec → candidats amb SPT-1 primer = informe.
- Fila de sulfats = nivell de la mostra (Anciles nivell 2 = informe).
- Blocs de sondeig buits amb evidència (Rubí, Linyola, Alcoletge) = els informes no tenen la taula.
- Deteccions espontànies: full de camp de LINYOLA dins del PENETROS de BELL-LLOC (escaneig barrejat); p.2 de l'annex de
  Castellar era de Bell-lloc; esborranys F5 vs annex PDF a Rubí; P-5/P-6 dins dels forats S-2/S-1 a Anciles.

## Caveats (honestedat)

- **Leakage**: com a la lectura d'or d'escalars, el skill anomena projectes del corpus; això valida executabilitat i
  re-execució, NO generalització. El test real seran carpetes noves de l'Eva.
- La veritat d'Anciles és un V0 (esborrany amb placeholders); la fila de sulfats no era llegible.
- El comparador docx (`scripts/compare_tables_vs_eva.py` + `_eva_truth/`) queda com a arnès per re-validar quan l'agent
  generi taules dins del wizard.

## Pregunta oberta per a l'Eva

Criteri de suma de l'N30 des del registre de camp (4 trams de 15 cm): els informes de Rubí/Alcoletge/Anciles usen els 2 trams
centrals; el de Bell-lloc diu 54 (que no és cap suma estàndard del registre 24/34/28/30) i el seu propi tall diu 58. Quin és
el criteri, i és 54 un error d'informe?

## Revisions de fixtures (registre explícit; els fixtures NO es reescriuen per fer quadrar el comparador)

### 2026-08-25 — Castellar `sondeig_tests[0].cota`: `segur 570,90 msnm` → `candidats` [relativa `-4 m` | absoluta `570,90`]
- **Per què:** era exactament l'ERR d'aquesta lectura d'or («L'ERR i les regles noves» §1): l'informe signat de l'Eva
  (`_eva_truth/castellar.json`, taula sondeig) posa S-1 a **-4.20** (relatiu al carrer), i la regla v0.9/3b del skill diu que la cota
  del sondeig a la taula segueix el sistema de cotes del projecte (DPSH relatius → relativa primer, absoluta segona, mai segur l'absoluta).
  El fixture havia quedat amb el veredicte del lector cec (absoluta, 2 fonts) i contradeia la regla que ell mateix havia generat.
- **Què s'ha posat com a candidat 1:** `-4 m (respecte el carrer)` amb font i cita reals del full de camp manuscrit
  (`PENETROS + SONDEIG.pdf` p.5, «Decriure cota 0 o cota referència»: `C/Arbrells   -4 m`; ja citat a `golden-read/…/camp_16_penetros_sondeig_manuscrit.json`).
  **NO** s'hi ha posat `-4,20`: cap document de la carpeta ho diu per a S-1 (−4,2 és la cota DPSH de P-2). Que un lector emeti `-4,20` per a
  S-1 continua sent una invenció (cas anotat al llibre, run `opus48-high-preext-v2-c3`). **Pregunta oberta a l'Eva:** d'on surt −4,20 per a S-1.
- Cel·la amb clau `revisio` dins del fixture (grep-able). Efecte al comparador: els runs amb `candidats` [relativa | absoluta] passen d'ALERTA/CAUTELA a OK;
  un run que posi `segur` l'absoluta surt ALERTA («prod puja a segur»).

### 2026-08-25 — Castellar `soil_levels[*].de_a_estat`: dialecte del fixture, NO revisat (l'absorbeix el comparador)
El lector cec va escriure `de`/`a` plans i una cel·la `de_a_estat` amb l'estat del parell (només en aquest fixture). El comparador v2
(`_expand_de_a`) les converteix en cel·les `de` i `a` amb aquell estat; el fixture queda tal com es va llegir.
Conseqüència: les cel·les `de`/`a` de `soil_levels` ara es comparen (abans sortien 2 ABSENT a tots els runs) i, amb les files alineades
per clau (capa vegetal / nivell N, no per índex), han aflorat lectures «nivell 1 des de 0,00» (capa vegetal absorbida) que l'índex amagava —
vegeu `docs/wizard-headless/fase12-consolida/_RESULTATS.md` §7 i `mesures/LEDGER.md`.
