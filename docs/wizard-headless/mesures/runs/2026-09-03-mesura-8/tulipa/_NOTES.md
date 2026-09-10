# Tulipa (2 cases) — mesura 2026-09-04 (codi intacte, pre P0-P4) — 8/8

**Cas especial (criteris):** sense informe signat d'Eva → **executabilitat + latència + estructura**, fora del titular.
El comparador no s'hi pot aplicar: l'or de lectura i el de taules estan **per casa** (`casa_1_tulipa_3` /
`casa_2_tosca_16`, `casa_1_tables` / `casa_2_tables`) i `_decisions.json` és d'un sol projecte → `KeyError`.

- **Executabilitat: OK.** 43,5 min, degraded=False, 16 docs (17 crides Claude, 1 Python), **0 reintents, 0 timeouts,
  0 DNS** (16 logs + stdout), cost 15,48 USD. `decisions=OK`.
- **Latència: 43,5 min, dels quals 12,1 min (28 %) són la passada LLM de consolidació** (`consolida_only`: 6 cel·les
  demanades per 6 conflictes A-vs-A, 30 torns, 523 s, 1,95 USD; només 3 aplicades) → **T2**. I **5,3 min + 1,25 USD
  llençats** per **D6**: `PLANTA I SECCIO.dwg` i `PLANTA I SECCIO.pdf` (mateix stem) van al **mateix JSON**
  (`casa_2_carrer_tosca_planta_i_seccio.json`); el PDF sobreescriu la lectura del DWG i el consolidador anota
  «lectura fallida (sense .json)» per al DWG. Net sense T2/D6: ~26 min.
- **Estructura (el que Tulipa mesura de debò):** un expedient, **dos informes** (casa 1 = C/ Tulipà 3, casa 2 = C/ Tosca 16;
  sondeig S-1 compartit; 2 DPSH per casa). El sistema produeix **un sol `_decisions.json`** on la casa 1 domina i la
  casa 2 apareix com a **contradiccions**: `street_address` candidats [Tulipà 3 | Tosca 16 (5 docs)], `expedient`
  conflicte «3001706» vs «3001706_CASA 1», `num_dpsh_tests` [2 | 2 | 4], i **només 2 de 4 punts DPSH** a la taula
  (P-1.1, P-2.1: un per casa, els P-x.2 col·lapsats o no llegits). `client_name` segur «Aleix Subirà Felip» (casa 1;
  l'or: casa 2 sense client). L'or ja ho deia: «El nivell A es resol PER CASA. El wizard actual no ho contempla.» → **S1**.
- Consistència amb l'or (només orientativa): `num_soil_levels` segur 3 = or 3 ✓; `cota_referencia` candidats «198 msnm
  ICGC» = or candidats 198 ✓; `municipality` segur Cerdanyola del Vallès ✓; `building_type` R1 (`EG HAB UNIF
  CERDANYOLA`, `CONSTR DO…`) — **8/8**; `cte_*` R4; `lab_depth` contradicció -1,00/-1,60 vs -3,00/-3,54 (dos SPT reals
  del mateix sondeig, SPT1 i SPT2 → no és error, és una fila per SPT que el camp escalar no pot expressar).
- Fields: 6 segur / 14 candidats / 2 no_trobat (utm: sense COORDENADES.txt). Taules: DPSH 2, sondeig 1, SPT 2, nivells 4.
- **Veredicte Tulipa: executable, sense ERR mesurable; l'estructura multi-casa NO està modelada (S1).** Latència
  inflada per T2 (12 min) i D6 (5 min).
