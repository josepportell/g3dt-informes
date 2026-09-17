# La coma decimal de les UTM fa desaparèixer les coordenades en silenci

**Trobat:** 2026-09-17, investigant el defecte menor «"No UTM coordinates" en generar Alcoletge tot
i que Cadastre havia trobat la referència».
**Gravetat:** pèrdua silenciosa de dades. No és cosmètic.

## La cadena, verificada pas a pas

1. **L'origen és el fitxer de camp de la mateixa G3DT.** `ANNEXES/COORDENADES.txt` d'Alcoletge
   conté literalment:
   ```
   Coordenades UTM (X);(Y);(Z);
   P-1
   308781,86 ; 4613950.63 ; 198.9
   ```
   Coma a la X, punt a la Y i la Z, **al mateix fitxer i a la mateixa línia**. No és cosa del
   lector ni de l'LLM: ve de l'equip de camp, o sigui que tornarà a passar.
2. El regex de parelles UTM accepta les comes sense queixar-se.
3. El partidor desa els dos trossos **tal qual, com a cadenes**, sense normalitzar el separador.

   **CORRECCIÓ (17-09, durant la implementació):** la primera versió d'aquest document citava
   `automation/lectura/contract.py:371` com la via de producció. **És fals.** `contract.py`
   només s'usa per adaptar fixtures d'or als tests (`adapt_legacy`). La via real de producció és
   `automation/lectura/consolidate.py:1082` (`_UTM_PAIR_RE`, cridada per `consolidate_python` →
   `runner.py`). S'han normalitzat totes dues, amb la lògica compartida.
4. `templates/validation/review.html:3180-3184` pinta els dos camps com a
   `<input type="number" step="0.01">`.
5. **Un `input type="number"` no pot contenir `308781,86`**: assignar-hi un valor invàlid deixa
   `.value` a cadena buida. Verificat al navegador el 17-09:
   ```
   inp.value = '308781,86'   →  ""              (descartat en silenci)
   inp.value = '4613950.63'  →  "4613950.63"    (sobreviu)
   ```
6. L'Eva veu la X buida al wizard. En desar, `utm_x` queda buit → `None`.
7. En generar, `automation/sections/section3_geologia.py:542` entra per
   `if not self.data.utm_x or not self.data.utm_y` i escriu
   **«No UTM coordinates and no manual ICGC override»**; el text de l'informe cau al fallback
   «No es disposa de coordenades UTM per consultar l'ICGC».
   `automation/image_manager.py:915` també salta la descàrrega del mapa geològic de l'ICGC.

## Per què només es veia a Alcoletge

Depèn de si el lector va escriure coma o punt aquell dia. Comprovat als tres projectes del clon:

| projecte | utm_x | utm_y | resultat |
|---|---|---|---|
| 4001670 ALCOLETGE | `'308781,86'` (**coma**) | `'4613950.63'` (punt) | X perduda → avís |
| 4001612 BELL-LLOC | `'314418.9'` (punt) | `'4611117.6'` (punt) | correcte |
| 3001631 RUBI | cap (van per geocodificació) | cap | correcte (ICGC va detectar el pendent 21,6%) |

O sigui que **no és un defecte d'Alcoletge: és una loteria del separador decimal**, i qualsevol
projecte futur hi pot caure. El cost és que la secció geològica de l'informe perd la consulta a
l'ICGC sense que res falli de manera visible.

## Què caldria (a decidir amb el Josep)

- **Normalitzar a l'origen**, als dos `_split_utm()` (el de producció a `consolidate.py` i el de
  fixtures a `contract.py`): convertir la coma decimal a punt en partir `utm_x_utm_y`.
- **Compte amb el separador de milers**: `308.781,86` (punt = milers, coma = decimals) i
  `308781,86` s'han de resoldre tots dos a `308781.86`, i `4613950.63` no s'ha de tocar. Cal una
  regla explícita, no un `replace(',', '.')` a cegues.
- **Xarxa de seguretat al formulari**: en poblar `wiz-utm_x`/`wiz-utm_y`, normalitzar abans
  d'assignar, perquè un valor amb coma que vingui d'un altre camí no torni a desaparèixer.
- Valdria la pena mirar si hi ha **altres camps numèrics** pintats com `type="number"` que rebin
  valors del lector amb coma: el mateix mecanisme els afectaria igual i igual de silenciosament.
