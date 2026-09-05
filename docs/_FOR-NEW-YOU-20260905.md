# FOR NEW YOU — 2026-09-05 — Fila 0b, primer paquet fet (C, D2, D3, R3); queda la resta de 0b

**Escrit:** 2026-09-05. Substitueix `_FOR-NEW-YOU-20260904.md` (conserva'l: hi ha les trampes i les decisions del Josep).
Branca `experiment/nivell-a-2026-08`, pushada al matí a `7bdbcde`; **els canvis d'avui poden estar sense commit**:
`git status` primer.

## Ordre de lectura (15 min)

1. Aquest document.
2. `docs/wizard-headless/mesures/runs/2026-09-03-mesura-8/_AGREGAT-8.md` **§Agregat mecànic (2026-09-05)** — les tres
   columnes (comparador v3/v4, consolidador antic/nou), per projecte, i com es llegeix respecte del titular manual.
3. `…/_DIAGNOSTICS-INDEX.md` §Estat dels fixes — què és ✅ i on, què és ⏳.
4. `docs/DECISION-LOG.md` entrada 2026-09-05 (7 decisions, dues marxes enrere).

## Actualització (tarda): fila 0b TANCADA

Josep ha dit «seguim amb la resta de la fila 0b, amb la teva proposta d'ordre tal qual»: G, R6, I1, R1, D5, D4, D6, T1,
T2 fets amb test i mesurats per reconsolidació (`mesures/reconsolida_mesura.py <sub_nou> <sub_ref>`); S1 en disseny.
Escalars sobre l'or 104 OK / 37 CAND / 5 ALERTA / 0 ERR; taules 137 / 21 / 8 / 0. Sobre el signat: 1 ERR real (Rubí
cota P-2, font d'Eva). Llegeix `_AGREGAT-8.md` §tarda i el DECISION-LOG 2026-09-05 (tarda). El que queda: preguntes a
Eva (R4, persona/despatx, SPT Vilanova, cota Rubí), R5/R2, decisió sobre la passada LLM (T2), S1.

## Estat en una frase

Els tres ERR de codi de la mesura (Linyola data, Vilanova municipi, Bell-lloc plantes) són OK amb el consolidador nou,
comprovat reconsolidant els 7 projectes a cost 0; el comparador ja no inventa 18 veredictes; l'agregat és un script.

## Com parlar amb el Josep (après avui)

**No parlis en codi.** «D2, D3, R6…» no li diu res encara que estigui documentat: tradueix cada codi a una frase (què
passa, on, què costa) i dona **rutes absolutes** dels fitxers clau perquè els obri a l'IDE. Va agrair explícitament la
traducció i la llista de rutes.

## Decisions que només pot prendre el Josep

1. **Commit** dels canvis d'avui (no s'ha fet: «commit only when the user asks»).
2. **Resta de la fila 0b**, en paraules: **G** = afegir a 3 fitxers d'or la nota «valor mesurat fora de la carpeta» per
   a la superfície de parcel·la (Rubí, Alcoletge, Vilanova): 3 ALERTA → OK, mitja hora. **R6** = a les taules, un
   document principal que no diu res del nivell freàtic guanya un document secundari que sí que diu «aigua» (Vilanova
   P-3, l'únic ERR de codi que queda). **I1** = la carpeta `PDF_V0` es descarta com a versió antiga encara que sigui
   l'única (Anciles, 9 cotes en blanc). **R1** = la mateixa cosa escrita de dues maneres es tracta com a contradicció
   (15 cel·les, la causa més gran). **D5** CTE amb N cases, **D4/D6** runner (docs perduts sense avís, DWG/PDF mateix
   nom), **T1/T2** temps, **S1** multi-casa (disseny). Proposta: G → R6 → I1 → R1.
3. **Paquet de preguntes a Eva** (sense canvis respecte del 09-04).

## Trampes noves

- **Reconsolidar, no re-run**, per mesurar canvis del consolidador: `consolidate_python(run_dir, project_path=…)` sobre les
  lectures cachejades + `merge_only_fields` amb el `_consolida_only.json` existent. No escriu res: l'artefacte es desa a
  `{slug}/_reconsolida-YYYY-MM-DD/`. `PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache` sempre.
- **Agregat:** `.venv/bin/python docs/wizard-headless/mesures/agrega_mesura.py [--sub _reconsolida-2026-09-05]`.
  `ledger.py` no serveix per a la mesura dels 8.
- **El comparador mesura contra l'or, no contra el signat.** Els ERR de veritat amb or prudent surten com a ALERTA:
  llegeix la columna ALERTA a mà (2 de 9 a taules són ERR reals: Rubí P-2, Vilanova P-3).
- **No afegir al comparador regles que perdonin el que ha de mesurar** (partícules, ca/es de litologies): la primera
  versió del v4 va amagar D3.
- Les d'ahir segueixen vigents (`_FOR-NEW-YOU-20260904.md` §Trampes).
