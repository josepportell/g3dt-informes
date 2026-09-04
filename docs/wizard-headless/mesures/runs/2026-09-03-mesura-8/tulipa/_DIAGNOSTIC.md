# Tulipa — diagnòstic (executabilitat, latència, estructura)

**Data:** 2026-09-04 · Sense veritat signada. Taxonomia: `../_DIAGNOSTICS-INDEX.md`.

| Codi | Què | Evidència | On |
|---|---|---|---|
| **S1** (estructura) | Un expedient amb N informes es consolida com UN projecte: la casa 1 mana, la casa 2 queda en contradiccions/candidats; 2 de 4 punts DPSH a la taula | `street_address` [Tulipà 3 \| Tosca 16 ×5 docs]; `expedient` «3001706» vs «3001706_CASA 1»; `num_dpsh_tests` [2\|2\|4]; `dpsh_tests` = P-1.1, P-2.1 | disseny: `_decisions.json` per casa (l'or ja ho fa: `casa_1_*` / `casa_2_*`); `runner`/`consolidate` amb clau de casa; wizard |
| **T2** (latència) | Passada LLM de consolidació de 523 s (28 % del run) per 6 conflictes A-vs-A, 3 aplicats | `consolidation.llm_only_fields` | `consolidate` → limitar la passada LLM a camps amb conflicte real; T2 creix amb S1 (els conflictes són entre cases) |
| **D6** (runner) | Col·lisió de nom de JSON entre `X.dwg` i `X.pdf` (mateix stem): una lectura sobreescriu l'altra; 317 s + 1,25 USD perduts; nota «lectura fallida» | `casa_2_carrer_tosca_planta_i_seccio.json`, `notes_estructurals`, telemetria | `runner.py` l. 112 (`stem` sense sufix → incloure l'extensió al nom) |
| R1 (8/8) | `building_type` bloquejat per `EG HAB UNIF CERDANYOLA` / `CONSTR DO…` | rule | `consolidate` |
| R4 | `cte_*` mai segur | rule | `consolidate` |
| — | `lab_depth` «contradicció» −1,00/−1,60 vs −3,00/−3,54: són **dos SPT reals** (SPT1, SPT2) del mateix sondeig; el camp escalar només en pot dur un | candidats | model: `lab_*` per mostra (taula), no escalar |

**Què aporta Tulipa:** el multi-casa és un cas de disseny obert (S1), no un bug de lectura: els lectors per document
han llegit bé les dues cases (les contradiccions ho demostren); és el consolidador que no té l'eix «casa». La passada
LLM (T2) és cara justament quan hi ha aquest eix. D6 és un bug independent, trivial.
