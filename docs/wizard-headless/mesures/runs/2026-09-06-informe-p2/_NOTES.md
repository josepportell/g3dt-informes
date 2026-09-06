# Mesura d'informe DESPRÉS de P2a+P2b (nivell portant = on recolza la sabata) — 2026-09-06 (tarda, 2)

Codi: P0 + regla del nivell portant (`_select_bearing_layer_idx` en ordre directe amb `Df + 0,2`, Df del wizard; col·lapse al
portant; `soil_types` per nivell de l'informe). Referència anterior: `../2026-09-06-informe-p0` (P0 sol). Comparar:

```bash
M=docs/wizard-headless/mesures/runs; for s in castellar rubi bell-lloc; do for v in 8b calc t2 viab; do diff <(grep -v '^\*\*' $M/2026-09-06-informe-p0/$s/$v/_compare_informe.txt) <(grep -v '^\*\*' $M/2026-09-06-informe-p2/$s/$v/_compare_informe.txt) | grep '^[<>]' | sed "s/^/$s $v: /"; done; done
diff <(python3 -m json.tool $M/2026-09-06-informe-p0/rubi/calc/_calc.json) <(python3 -m json.tool $M/2026-09-06-informe-p2/rubi/calc/_calc.json)
```

## Qa i paràmetres (variant `calc`), abans ⇒ després (signat)

| | Castellar | Rubí | Bell-lloc |
|---|---|---|---|
| nivell portant | roca 0,5-1,2 (igual) | gresos ⇒ **graves 0-3,35** | graves 1,0-1,8 ⇒ **graves carbonatades 0-1,0** |
| Nb | 27,2 (17-R) | 52,2 ⇒ 41,9 (47-R) | 41,3 ⇒ 22,6 (25-R) |
| φ / γ / c / E | 35 / 2,2 / 1,0 / 500 (35 / 2,2 / 1,0 / >500) | 35 / 2,2 / 1,0 / 500 ⇒ 37 / 2,0 / 0,0 / 469 (39 / 2,0 / 0,05 / 450) | 37 / 2,0 / 0,0 / 469 ⇒ 33 / 2,0 / 0,0 / 114 (38 / 2,0 / 0,0 / 650) |
| **Qa** | 3,0 ✅ | 3,0 ⇒ **3,5 ✅** | 2,5 ⇒ **1,5 ❌** (3,0) |
| assentament (cm) | 2,80 (<1,0) | 1,50 ⇒ 1,70 (1,50) | 1,70 ⇒ 1,00 (<1,20) |

## Lectura

- **Rubí** és el cas que la regla havia de resoldre: descrit i parametritzat com a graves, topall granular dens → 3,5.
- **Castellar** no es mou: la cobertura (0-0,5) se salta per fondària (0,3 + 0,2) i, si ve de l'or, pel nom («Terreny Vegetal»).
- **Bell-lloc** empitjora el Qa però per la raó bona: la capa és la que l'Eva usa (Nb 23 ≈ 25-R; assentament 1,0 ≈ «<1,20»),
  i el que no quadra és φ (33 per correlació, 38 signat) i E (114 per correlació, 650 signat: «carbonatades»). Són criteris
  litològics de l'Eva (P3), no descrits als informes. El 2,5 d'abans venia de lectures de la zona de rebuig (N20 34) que no
  són les de la sabata.
- **Taules:** Castellar idèntic; Rubí `calc` φ «39°» → «37°» (l'únic canvi d'estat, M → X: el 39 era casualitat); Rubí `viab`
  62 → 69 %; Bell-lloc −2 pp a totes les variants (sísmica Tipus II → III per N20 < 30).
- **P4, només anàlisi:** comptar les lectures des de la base de la sabata (no des del sostre de la capa) mou Rubí Nb
  41,9 → 44,3 (P-3 sol 51,6), Bell-lloc i Castellar no. El 17-R de Castellar no surt de cap subconjunt (P-1 20,3 / P-4 19,2 /
  P-3 46 amb una lectura).

## Trobada de camí

`_user_data_prev.json` de Bell-lloc porta `soil_types = ["limo", "grava"]` (dos nivells de l'abril) i el codi indexava per capa
de sondeig: amb el portant a l'índex 0 aplicava «limo» a les graves (Qa 2,0, φ 30,5). Corregit amb `_bearing_soil_type` (els
tipus del wizard s'apliquen per nivell de l'informe i només si n'hi ha tants com nivells generats).
