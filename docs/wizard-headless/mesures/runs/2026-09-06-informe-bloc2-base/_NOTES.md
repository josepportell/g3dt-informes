# Línia base de QUALITAT D'INFORME per al bloc 2 — 2026-09-06, codi intacte (`4a7e4b0`)

Generada amb `docs/wizard-headless/mesures/mesura_informe.py 2026-09-06-informe-bloc2-base` (recepta al capçal del script).
Harness: `scripts/compare_tables_vs_eva.py` (11 taules, informe generat vs `_eva_truth/<slug>.json`). Cost: 0.
**No confondre** amb la mesura de lectura (`runs/2026-09-03-mesura-8/…/_reconsolida-*`, comparador d'or).

## Què hi ha

- 3 projectes (Castellar, Rubí, Bell-lloc): els únics amb `_user_data_prev.json` reutilitzable. Els altres 4 esperen M341.
- 4 variants per projecte: `8b` (rèplica de la Fase 8b: quadra exacta 78/82/75 %), `calc` (sense els `geomech_params`
  manuals de l'Eva: les cel·les γ/c/φ/E/N/Nb surten del codi), `t2` (lectura real `_reconsolida-2026-09-06-t2` en lloc de
  l'or), `viab` (cap taula llegida: només via B).
- Per variant: `_compare_informe.txt` (taula del harness, diffable), `_compare_informe.json` (cel·les), `_user_data_usat.json`.
- `_AGREGAT.md`: titulars, M/C/X per taula, i la llista de cel·les no-MATCH de les taules del bloc 2.

## Què diu (abans de tocar res)

1. **Els `_user_data_prev.json` tapaven el càlcul.** Castellar `8b` té γ 1,90 / c 0,05 / φ 30° / E 114 (els manuals de
   l'abril) i `calc` té els del codi (roca: 2,20 / 1,00 / 35° / 500, tots MATCH amb el signat menys E «500» vs «>500»).
   La mesura del 26 d'agost mesurava lectura + format, no càlcul. **La columna del bloc 2 és `calc`.**
2. **P2a (Rubí «vestit de roca») només es veu a `viab`**: 7/7 cel·les de la taula geotècnica malament (nom «Gresos…
   (Nivell 2)», γ 2,20, c 1,00, φ 35°, E 500). Amb lectura, la litologia llegida substitueix `level.description` abans
   d'`is_rock` → paràmetres de sòl granular; φ 39° i γ 2,0 coincideixen amb el signat; queden Nb «52-R» (47-R) i E 469 (450).
3. **Columna N (P0) a les 3**: «22» (Castellar, signat «R»), «43» (Rubí, 40), «34» (Bell-lloc, 54): era la mitjana N20 del
   DPSH. Corregit el mateix dia (`runs/2026-09-06-informe-p0`).
4. **Bell-lloc, fila SPT/MA:** or 58, lectura t2 62, via B 58, signat 54. Tres sumes d'un mateix registre (24/34/28/30):
   pregunta 1 de `PREGUNTES-EVA-PENDENTS.md`. No és de càlcul.
5. `viab` a Castellar: la via B no llegeix l'SPT del full manuscrit (fila SPT/MA buida) i posa la cota absoluta «+570.90» al
   sondeig on l'Eva escriu «-4.20»: el que la Fase 8b va arreglar amb la lectura.
6. Observació de pas: Castellar sísmica «Tipus III / 1,60 / 1,6» vs «Tipus II / 1,15* / 1,3» (gruix i N20 del nivell únic).
