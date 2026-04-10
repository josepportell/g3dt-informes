# Anàlisi d'hipòtesis Settlement i K30

**Data:** 2026-04-10

---

## K30 — RESOLT

Només 2 projectes tenen K30 a la referència d'Eva:

| Projecte | Eva K30 | E | Fórmula | Calc | Dev |
|---|---|---|---|---|---|
| **Castellar** (roca) | 8.0 | 500 | E/60 | 8.33 | +4% ✓ |
| **Rubí** (granular) | 6.0 | 450 | E/75 | 6.00 | 0% ✓ |

**CONFIRMAT:** K30 = E/75 (granular), E/60 (roca). Ja implementat correctament.

---

## Settlement — Anàlisi parcial

### Projectes amb valor numèric precís
| Projecte | Eva s | Millor fit | Es usat | Dev |
|---|---|---|---|---|
| **Bell-Lloc** | 1.20 | ? | Cap fórmula encaixa bé | ? |
| **Rubí** | 1.50 | Es=3.5×Nb | 164 | -9% ✓ |
| **Anciles** | 1.50 | Es=E | 90 | -6% ✓ |

### Projectes amb frase genèrica ("menyspreables o inferiors a 1.0 cm")
| Projecte | Eva s | Interpretació |
|---|---|---|
| **Castellar** | ≤1.0 | Roca — assentaments trivials |
| **Linyola** | ≤1.0 | Frase estàndard |
| **Alcoletge** | ≤1.0 | Frase estàndard |
| **Vilanova** | ≤1.0 | Frase estàndard |

### Observacions

1. **La frase genèrica és la norma, no l'excepció.** 4 de 7 projectes usen la frase
   "menyspreables o inferiors a 1.0 cm" sense valor exacte. Això suggereix que Eva
   calcula, veu que és <1.0, i posa la frase estàndard.

2. **Quan Eva precisa un valor** (Bell-Lloc 1.20, Rubí 1.50, Anciles 1.50), ho fa
   perquè el settlement és >1.0 cm i cal informar-lo.

3. **No hi ha una sola fórmula d'Es** que funcioni per tots. L'Es depèn del criteri
   professional d'Eva (com ella mateixa va dir: "l'agafo com a criteri").

4. **Per al pipeline:** La comparació numèrica no té sentit per la frase genèrica.
   Cal que el diagnostic compari "≤1.0" com a MATCH quan el pipeline dóna <1.0.

### Implicació per al diagnostic

El MISMATCH de settlement ve de comparar un número (pipeline: "4.66") amb una frase
("Els assentaments...inferiors a 1.0 cm"). El LLM judge ja millora això (de MISMATCH
a CLOSE o MATCH), però seria millor:

1. Extreure el valor numèric de la frase d'Eva (parse "1.0" de "inferiors a 1.0 cm")
2. Comparar numèricament: si pipeline < valor_eva → MATCH (l'assentament és menys del llindar)

### Fórmula d'Es recomanada

Per al pre-fill del wizard, el millor approach és:
- **Es = 2.5 × Nb** com a default (ja implementat, doc Schmertmann)
- Eva ajusta al wizard si vol un altre valor
- El settlement és Tier C ("professional judgment") — no podem reproduir-lo automàticament
  amb precisió perquè Eva ajusta Es per experiència
