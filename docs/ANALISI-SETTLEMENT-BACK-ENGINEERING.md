# Anàlisi: Settlement Back-Engineering + E(Nb vs N20)

Data: 2026-02-26
Script: `proves-fase2/settlement_analysis.py`

## 0. Correccions crítiques

**Valors de referència anteriors (MEMORY.md / compare_4projects.py) tenien ERRORS:**

| Camp | Antic (incorrecte) | Correcte (PDF signat) |
|------|--------------------|-----------------------|
| Bell-Lloc E | 450 | **650** |
| Bell-Lloc settlement | 1.50 cm | **1.20 cm** |
| Rubí settlement | 0.72 cm | **1.50 cm** |
| Rubí N20 | 43 | **40** |
| Bell-Lloc N_taula | 40 | **54** (ambigüitat) |

Font: `PDF/LLETRA/{expedient}_informe.pdf` — Secció 4.1 (taula geomecànica) + Secció 4.3 (fonamentació)

## 1. Matriu de dades d'Eva (dels PDFs signats)

```
┌─────────────┬──────────┬──────┬──────┬─────┬──────┬──────┬──────┬──────┬──────┬─────────────────────────────┐
│ Project     │ Material │ N20  │  Nb  │gamma│  c   │ phi  │  E   │  Qa  │ s(cm)│ Notes                       │
├─────────────┼──────────┼──────┼──────┼─────┼──────┼──────┼──────┼──────┼──────┼─────────────────────────────┤
│ Bell-Lloc   │ Graves   │  40* │ 48.2 │ 2.0 │ 0.00 │  38  │  650 │ 3.0  │ 1.20 │ *N_taula=54, carbonatades  │
│ Rubí        │ Graves   │  40  │ 48.2 │ 2.0 │ 0.05 │  39  │  450 │ 3.50 │ 1.50 │ Qa>3.0 (c=0.05)           │
│ Linyola L1  │ Llims    │  13  │ 15.7 │1.90 │ 0.05 │  28  │  100 │  -   │  -   │ No és nivell fonamentació  │
│ Linyola L2  │ Lutites  │  R   │ 31-R │2.20 │ 1.00 │  30  │ >800 │ 3.0  │ ≤1.0 │ Roca. "menyspreables"      │
│ Castellar L1│ Llims    │  12  │ 14.5 │1.90 │ 0.00 │  28  │  -   │  -   │  -   │ No és nivell fonamentació  │
│ Castellar L2│ Roca     │  R   │  R   │2.20 │ 1.00 │  35  │  500 │ 5.0  │  -   │ Roca. Sense assentament    │
└─────────────┴──────────┴──────┴──────┴─────┴──────┴──────┴──────┴──────┴──────┴─────────────────────────────┘
```

Geometria: Df ≈ 0.35 m (30-40 cm), B ≈ 1.0 m (no especificat), sabates aïllades/corregudes.

## 2. E(Nb) vs E(N20) — Resultat clar

| Projecte | N20 | Nb | Bracket(N20) | Bracket(Nb) | E_CTE | E(Eva) | Veredicte |
|-----------|-----|----|-------------|------------|-------|--------|-----------|
| Bell-Lloc | 40 | 48.2 | [25,50) | [25,50) | 469 | 650 | **TIE** — mateixa bracket |
| Rubí | 40 | 48.2 | [25,50) | [25,50) | 469 | 450 | **TIE** — mateixa bracket |
| Linyola | 13 | 15.7 | [10,25) | [10,25) | 114 | 100 | **TIE** — mateixa bracket |

**Conclusió**: Per N20=40, Nb=48.2 cau a la MATEIXA bracket CTE [25,50). No hi ha bracket-crossing. Usar Nb o N20 per E dóna idèntic resultat amb CTE D.23. **Mantenir N20 per a E** (la implementació actual és correcta).

Nota: El cas Rubí antic (N20=43→Nb=51.8→bracket [50,999)) era degut a N20 incorrecte. Amb N20=40 corregit, no hi ha problema.

## 3. Hipòtesis Es per assentament — Top matches

### Bell-Lloc (Qa=3.0, s_target=1.20 cm)
| # | Hipòtesi | Es | s(sq) | dev(sq) | s(str) | dev(str) |
|---|----------|-----|-------|---------|--------|----------|
| D | Bowles(N20) STRIP | 275 | 0.57 | -53% | **1.19** | **-1%** |
| G | 2.5×Nb SQUARE | 120 | **1.29** | **+8%** | 1.93 | +61% |
| D' | Bowles(Nb) STRIP | 316 | 0.49 | -59% | 1.03 | -14% |
| B3 | Eva E/2 STRIP | 325 | 0.48 | -60% | 1.00 | -16% |

### Rubí (Qa=3.50, s_target=1.50 cm)
| # | Hipòtesi | Es | s(sq) | dev(sq) | s(str) | dev(str) |
|---|----------|-----|-------|---------|--------|----------|
| G | 2.5×Nb SQUARE | 120 | **1.51** | **+1%** | 2.26 | +51% |
| D | Bowles(N20) STRIP | 275 | 0.66 | -56% | 1.39 | -8% |
| B3 | Eva E/2 STRIP | 225 | 0.81 | -46% | 1.69 | +13% |

### Patró
- **2.5×Nb + SQUARE** dóna resultats molt propers per Rubí (+1%), acceptable per Bell-Lloc (+8%)
- **Bowles(N20) + STRIP** dóna resultat perfecte per Bell-Lloc (-1%), acceptable per Rubí (-8%)
- Cap fórmula única funciona perfectament per ambdós amb la mateixa forma

## 4. Back-engineering — Es implícit d'Eva

### Resolució inversa: Es = C1 × Qa × Iz_integral / s_target

| Projecte | Shape | Es_implied | Es/E(Eva) | qc/N20 | qc/Nb | k(N20) | k(Nb) |
|-----------|-------|-----------|-----------|--------|-------|--------|-------|
| Bell-Lloc | SQUARE | **130** | 0.200 | 1.30 | 1.08 | 3.24 | 2.69 |
| Bell-Lloc | STRIP | **272** | 0.418 | 1.94 | 1.61 | 6.79 | 5.64 |
| Rubí | SQUARE | **121** | 0.269 | 1.21 | 1.01 | 3.03 | 2.52 |
| Rubí | STRIP | **254** | 0.565 | 1.82 | 1.51 | 6.35 | 5.27 |

### Patrons de consistència

**Si SQUARE**: Es ≈ 125 per ambdós → **Es ≈ 2.5 × Nb** (qc/Nb ≈ 1.0)
- Bell-Lloc: 130 / (2.5×48.2) = 1.08
- Rubí: 121 / (2.5×48.2) = 1.01
- Consistència: excel·lent (8% diferència)

**Si STRIP**: Es ≈ 263 per ambdós → **Es ≈ Bowles(N20)** ó **Es ≈ E(Eva)/2**
- Bell-Lloc: 272/275(Bowles) = 0.99, 272/650(Eva) = 0.42
- Rubí: 254/275(Bowles) = 0.92, 254/450(Eva) = 0.56
- Consistència: bona per Bowles (7% diferència), variable per E/2

## 5. Anàlisi geotècnica professional

### Per què Bell-Lloc i Rubí són diferents?

| Factor | Bell-Lloc | Rubí | Implicació |
|--------|-----------|------|------------|
| Material | Graves matriu sorrenca **CARBONATADES** | Graves i sorres (estàndard) | Carbonatació = cimentació → +E |
| N20 (extret DPSH) | 40 | 40 | Idèntic |
| N (taula Eva) | 54 | 40 | Bell-Lloc +35% → més resistent? |
| E | **650** | 450 | Bell-Lloc +44% (cementation effect) |
| Qa | 3.0 | 3.50 | Rubí +17% (c=0.05 o T-P governs?) |
| s (cm) | 1.20 | 1.50 | Rubí +25% (Qa és major) |

**Clau**: La **carbonatació** de Bell-Lloc justifica E=650 vs 450. Eva puja E per cimentació natural del sòl. Això és criteri professional, no fórmula.

### Procés de decisió d'un enginyer geotècnic qualificat

1. **E (mòdul de deformació):**
   - Punt de partida: CTE D.23 bracket [25,50) → E=40-100 MN/m² → ~469 kg/cm² conservador
   - Ajust AMUNT per carbonatació/cimentació → 650 (Bell-Lloc)
   - Sense ajust per graves normals → 450 ≈ CTE conservador (Rubí)
   - Eva: "L'agafo com a criteri" — confirma que és judici professional

2. **Qa (capacitat portant admissible):**
   - Terzaghi teòric: dona Qa >> 3.0 per phi=38-39
   - Terzaghi-Peck empíric: Nb/12 × correccions
   - Cap professional: 3.0 sòl normal, 3.5-5.0 cimentat/roca
   - Rubí Qa=3.50: o bé T-P governs, o bé Eva puja el cap lleugerament

3. **Assentament:**
   - Propòsit: verificar < 2.54 cm (1 polzada, límit estàndard)
   - No intenta predir el valor exacte — verifica que sigui acceptable
   - 1.20 i 1.50 cm estan còmodament per sota del límit
   - Precisió millor que ±50% és il·lusòria en geotècnia

### La veritat pràctica

> L'assentament en geotècnia és una **verificació de servei**, no un càlcul d'enginyeria precís.
> El que importa és: "Està ben per sota del límit?" → SÍ per ambdós projectes.
> La fórmula exacta importa menys que l'ordre de magnitud.

## 6. Recomanació per a l'automatització

**No intentar replicar exactament la fórmula d'Eva per assentament.** En lloc d'això:

1. **Fórmula per defecte**: Schmertmann amb Es = 2.5 × Nb (SQUARE)
   - Dóna resultats en el rang correcte (+1% a +8% vs Eva)
   - Simple, consistent, i conservador

2. **Es ajustable**: Permetre que Eva modifiqui Es al wizard
   - Per materials cimentats: Eva pujarà Es → menor assentament
   - Per materials tous: Eva baixarà Es → major assentament

3. **Flagging**: Si s > 1.5 cm, mostrar alerta per revisió d'Eva

4. **Preguntes pendents per Eva**:
   - "N=54 a Bell-Lloc — és SPT o N20?" (clarifiquem la taula)
   - "Per l'assentament, quin Es uses? O és E directe?"
   - "Rubí Qa=3.50 — és per T-P o puges el cap per graves denses?"

## 7. Ambigüitat del N=54 a Bell-Lloc

La taula d'Eva mostra `Nb=25-R, N=54`. Interpretacions possibles:

| Interpretació | N20 | Nb | E_CTE | Plausibilitat |
|---------------|-----|-----|-------|---------------|
| N=54 és N20 | 54 | 65.1 | bracket [50,∞) = 1428 | Poc probable (E=1428 ≠ 650) |
| N=54 és Nb | 44.8 | 54 | bracket [25,50) = 469 | Possible (E=469 ≈ base per 650) |
| N=54 és SPT (sondeig) | 40 (DPSH) | 48.2 | bracket [25,50) = 469 | Probable — Bell-Lloc té SPT |

Bell-Lloc té sondeig a rotació + SPT (apartat 2.4.3 de l'informe). El N=54 podria ser el valor SPT del sondeig, mentre que N20=40 és la mitjana DPSH. **Recomanació: preguntar a Eva.**
