# Fase 0 — Acceptació del mode `--consolida` (skill v1.0) — 2026-08-24

**Exercici:** 2 agents cecs (sessions fresques, sense accés a `docs/golden-read*` ni informes) executant el Pas 5b
(`--consolida`) del skill v1.0 sobre els JSON per-document d'or de BELL-LLOC + `_g3_templates.json` real, sense
`_inventory.json` (tolerància verificada). Comparació amb `compare_consolida.py` (adapter de dialecte inclòs).

## Escalars (input: 26 per-doc de `docs/golden-read/4001612 BELL-LLOC/` + g3_templates)

19/22 OK exactes (estat + valor). Cap error real:
- `architect_name` or=segur, produït=candidats [persona|despatx] → l'or és pre-v0.5; la regla ACTUAL mana candidats. Correcte.
- `lab_depth` "1,00 - 1,60 m" vs or "1,0 - 1,6 m" → mateix valor, format (el lector emet dades, el generador formata).
- `architect_company` clau nova v1, sense or per comparar.

## Taules (input: 10 per-doc de `docs/golden-read-taules/4001612 BELL-LLOC/` + g3_templates)

20/21 cel·les OK exactes. Cap error real:
- `sondeig_tests[0].spt_ma` or="1/0" (cadena), produït = `n_spt:1, n_tp:0, n_ma:0` → la regla v1.0 mana COMPTES. Correcte.
- Restriccions dures respectades en cec: n30=candidats [62 trams centrals | 58 tall] amb registre segur [24,34,28,30];
  litologia sempre candidats; blocs buits amb forma canònica.

**Veredicte: erroni-amb-confiança = 0 als dos exercicis. Fase 0 ACCEPTADA.**

## Lliçons incorporades al skill v1.0 abans del commit (feedback dels agents)

1. Pas 5b: normalització explícita `tier_a` → `candidates` (els per-doc no parlen el dialecte de sortida).
2. Pas 5: forma canònica del bloc de taula buit (`estat_bloc: no_trobat, rows: [], sources_checked`).
3. Pas 4: tot camp d'`authority_for` ha de tenir entrada `tier_a` amb quote (el promotor d'A.01 s'havia quedat al `context`).
4. Pas 3b: el check de colors N.F. s'anota a `reading_notes` perquè el consolidador cec el pugui verificar.

## Pendents que l'acceptació confirma per a les fases següents

- `_inventory.json` és imprescindible per detectar documents NO llegits (Cadastre no llegit → utm/RC no_trobat) — Fase 2/3.
- `_g3_templates.json` pot portar el mateix document per duplicat (2 carpetes): el consolidador dedupe per llinatge — vigilar a Fase 4.
- Caveat de leakage habitual: valida executabilitat del Pas 5b, no generalització.

## Addendum 2026-08-25 (nit, 2) — comparador v2: normalitzadors de format + files de taula per clau

`compare_consolida.py` passa a v2 (mateixa CLI, mateix format de sortida): `close(a, b, field)` conscient del camp — dates, nombres i
intervals (fondàries en valor absolut), adreces per conjunt de portals, `spt_ma` per comptes, `num_floors`, `building_type` per tokens,
anotacions `(...)`/` -- nota` fora — i files de taula alineades per clau (punt / sondeig / capa vegetal / nivell N) en lloc de per índex,
més l'expansió del dialecte `de_a_estat` del fixture de Castellar. Independent del consolidador a posta (no comparteix codi amb
`consolidate.py`). Tests: `tests/test_compare_consolida.py` (79). Els `escalars.txt`/`taules.txt` de tots els runs del llibre i de
`fase12-consolida/out/` s'han regenerat; els totals v1 queden a `meta.json` → `comparator_revision`. Detall i lectura dels canvis:
`docs/DECISION-LOG.md` entrada «2026-08-25 (nit, 2)» i `fase12-consolida/_RESULTATS.md` §7.
