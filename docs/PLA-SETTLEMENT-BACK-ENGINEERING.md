# Pla: Settlement back-engineering + E(Nb vs N20)

Data: 2026-02-26

## Context

Després de fixar Castellar Qa (3→5) i Rubí E (1428→469), l'assentament és el gap més gran. La implementació actual de Schmertmann usa Robertson (1983) qc/N=4.5 per sòls granulars, donant Es=2.5×qc=542 kg/cm². Això produeix assentaments 50-77% per sota de les referències d'Eva:

| Projecte | N20 | Nb | s nostre (cm) | s Eva (cm) | Dev |
|-----------|-----|----|---------------|------------|-----|
| Bell-Lloc | 40 | 48.2 | 0.34 | 1.50 | -77% |
| Rubí | 43 | 51.8 | 0.32 | 0.72 | -56% |

L'usuari també vol veure què passa si usem Nb (en lloc de N20) per al càlcul de E als 4 projectes.

## Enfocament: Script diagnòstic de comparació

Fitxer: `proves-fase2/settlement_analysis.py`

### Part 1: Hipòtesis Es per assentament (Bell-Lloc + Rubí)

Per cada projecte, calcular assentament Schmertmann amb:

| # | Hipòtesi Es | Fórmula | Font |
|---|-------------|---------|------|
| A | Robertson qc (actual) | Es = 2.5 × Nb × 4.5 | Robertson (1983) |
| B | CTE D.23 E directe | Es = nspt_to_E_kg_cm2(N20) | Taula CTE |
| C/C' | Beguemann E | Es = 40+12(N-6) per N>15 | Spt-correlacions.doc |
| D/D' | Bowles E | Es = 10(7.5+0.5N) | Spt-correlacions.doc |
| E/E' | D'Apolonia NC | Es = 215+10.6N | Spt-correlacions.doc |
| F | Es = 2.5 × N20 | N cru com proxy qc | Simplificació |
| G | Es = 2.5 × Nb | Nb com proxy qc | Simplificació |

C/C', D/D', E/E' es proven amb N20 i Nb. Cada hipòtesi × {square, strip} = matriu 2×.

### Part 2: E(Nb) vs E(N20) (4 projectes)

Per cada projecte, calcular:
- E de CTE D.23 usant N20
- E de CTE D.23 usant Nb
- E referència d'Eva
- Desviació per cadascun + bracket CTE

### Part 3: Back-engineering (resolució inversa)

Per cada projecte amb dades d'assentament:
1. Resoldre inversament Es: `Es = C1 × Qa × Iz_integral / s_target`
2. Mostrar què implica per cada hipòtesi (qc/N, escala vs CTE, etc.)
3. Comprovar consistència entre projectes

## Verificació

```bash
python3 proves-fase2/settlement_analysis.py
```

Tot l'output són taules impreses. Cap codi de producció modificat.
