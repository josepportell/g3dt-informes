# Criteris de la mesura dels 8 projectes (escrits ABANS d'executar-la)

**Data:** 2026-09-03 · **Codi:** branca `experiment/nivell-a-2026-08` INTACTA (cap P0–P4 aplicat — el
diagnòstic del 09-02 confirma que el càlcul no s'ha mogut, la línia base és vàlida).
**Config:** defaults de producció del runner (sonnet, `--effort xhigh`, concurrència 2, preext ON,
consolida `auto`), `G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache`. Projectes: `~/g3dt-e2e/projectes/`
(mai `/mnt/c`, mai `reference-material/`). Driver: `run_mesura.py` (aquí al costat, versionat).
Sortida: `runs/2026-09-03-mesura-8/{slug}/` — els `.png` NO es versionen (regla al `.gitignore`).

## Mètriques per projecte (lectura — `_decisions.json` vs veritat)

| Estat | Definició | Compta com |
|---|---|---|
| **OK** | decisió única confiada = veritat | bé |
| **CAND** | el sistema presenta candidats (popup), sense confirmar en fals | acceptable (Eva tria) |
| **Blanc/NT** | no trobat, sense candidats, amb motiu visible | permès (mai inventar) |
| **ERR** | decisió **confiada** ≠ veritat (erroni-amb-confiança) | l'única inacceptable |

**Llindars pactats:** OK ≥ 80 % · CAND ≤ 20 % · **ERR = 0** (mana sobre tota la resta). +minuts per projecte.

Veritats: camps de lectura → or transcrit (`docs/golden-read-taules/_eva_truth/`, 7 JSON) i or v2 del
comparador; taules de l'informe → `scripts/compare_tables_vs_eva.py` contra els `.docx`/`.pdf` signats.

## Casos especials (dir-los AL CAPDAVANT dels resultats, no a peu de pàgina)

- **Vilanova**: `_eva_truth/vilanova.json` és stub (el PDF signat no té el cos amb les taules; les cel·les
  vénen dels annexos = mateixa font que llegeix l'agent). **Circular → només consistència**, fora del
  denominador del titular. Pregunta a Eva pel `.doc` pendent.
- **Tulipa**: sense veritat (0 fitxer a `_eva_truth/`). Mesura **executabilitat + latència** només.
- **Titular comparable: 6 projectes.**

## Taules vs signats: MISMATCH de causa coneguda, marcats no re-diagnosticats

Les cel·les **Nb, N, E** (tots) i **γ/c/φ/material** (Rubí) tenen causes documentades a
`docs/ANALISI-CALCUL-N20-E-2026-09-02.md` §7 (P0–P4 pendents, a aplicar DESPRÉS d'aquesta línia base).
Al report: marcar-les «causa coneguda (P0/P1/P2/P3)» i donar el titular amb i sense elles.

## Procediment i higiene

1. Un projecte per run, **seqüencial** (no barrejar concurrència entre projectes amb la c2 interna).
2. Abans de citar cap número: `grep "name resolution\|Connection error"` als logs (contaminació DNS).
3. Comparar **flips per variable i per nom**, mai titulars d'un sol sweep (franja de soroll 2,8 pp).
4. Temps de referència pre-fixos (holdout-v16): Castellar **27,8 min**, Linyola **41,9 min**.
5. Re-consolidacions posteriors deterministes: `G3DT_LECTURA_HTTP_SOURCES=""`.
6. Sessió 2026-09-03 (finestra d'1 h): Castellar primer (té línia base de temps); segon projecte només si
   pot ACABAR abans del tall — un run matat a mitges embruta la mesura. La resta, en reprendre.

## Què mesura i què NO mesura aquesta passada

Mesura: **lectura nivell A** (OK/CAND/blanc/ERR/minuts) + **les 11 taules de l'informe generat** (inclou
grup B: geotècnica, sísmica, sulfats, permeabilitat…). **NO mesura** les 341 variables de l'informe sencer
(narrativa, adjacents, descripcions): això és la taula comparativa completa ajornada (sessió 2026-08-25),
a programar després d'aquesta mesura.
