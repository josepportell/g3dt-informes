# Comparació Sistemàtica: Automatització vs Referència Eva

**Data:** 2026-02-25
**Projectes:** Bell-Lloc (4001612), Castellar (3001621), Rubí (3001631), Linyola (4001607)
**Objectiu:** Identificar patrons de desviació per calibrar l'automatització

---

## 1. Matriu Comparativa Completa

### Paràmetres geomecànics (Taula 9 de cada informe)

| Paràmetre | | Bell-Lloc | | | Castellar | | | Rubí | | | Linyola | |
|-----------|---|-----------|---|---|-----------|---|---|------|---|---|---------|---|
| | **Gen** | **Eva** | **Δ%** | **Gen** | **Eva** | **Δ%** | **Gen** | **Eva** | **Δ%** | **Gen** | **Eva** | **Δ%** |
| Nivells | 1 | 1 | OK | 2 | 1 | +1 | 1 | 1 | OK | 1 | 2 | -1 |
| gamma (g/cm³) | 2.16 | 2.0 | +8% | 2.20 | 2.20 | 0% | 2.18 | 2.0 | +9% | 2.12 | 1.90 | +12% |
| c (kg/cm²) | 0.0 | 0.0 | OK | 1.0 | 1.0 | OK | 0.0 | 0.05 | — | 0.0 | 0.05 | — |
| phi (°) | 38.2 | 38 | +0.5% | 35.0 | 35 | 0% | 38.8 | 39 | -0.5% | 35.8 | 28 | +28% |
| E (kg/cm²) | 469 | 650 | -28% | 500 | 500 | 0% | 469 | 450 | +4% | 469 | 100 | +369% |

### Resultats de càlcul (Secció 4.3)

| Paràmetre | | Bell-Lloc | | | Castellar | | | Rubí | | | Linyola | |
|-----------|---|-----------|---|---|-----------|---|---|------|---|---|---------|---|
| | **Gen** | **Eva** | **Δ%** | **Gen** | **Eva** | **Δ%** | **Gen** | **Eva** | **Δ%** | **Gen** | **Eva** | **Δ%** |
| Qa (kg/cm²) | 5.33 | 3.0 | +78% | 3.18 | 3.0 | +6% | 3.18 | 3.50 | -9% | 4.95 | 3.0 | +65% |
| Assent. (cm) | 1.21 | 1.20 | +1% | 0.72 | 1.0 | -28% | 0.72 | 1.50 | -52% | 1.13 | 1.0 | +13% |
| K30 (kg/cm³) | 6.3 | — | — | 8.3 | 8.0 | +4% | 6.3 | 6.0 | +5% | 6.3 | — | — |

### Altres dades

| Paràmetre | Bell-Lloc | Castellar | Rubí | Linyola |
|-----------|-----------|-----------|------|---------|
| N20 mitjà | 36.7 | 38.1 | 39.5 | 29.2 |
| SPT (N30) | 54 | R (refús) | 40 | — / R |
| Sulfats | 89.8 ✓ | 0.0 ✓ | 632.3 ✓ | 0.0 ✓ |
| Aigua | No ✓ | No ✓ | No ✓ | No ✓ |
| Pendent | No | Sí | No | No |

---

## 2. Anàlisi de Desviacions per Paràmetre

### ✅ K30 — Resolt (biaix +4.4%, dispersió 1pp)

| Projecte | Generat | Eva | Δ% |
|-----------|---------|-----|-----|
| Castellar (roca) | 8.3 | 8.0 | +4% |
| Rubí (granular) | 6.3 | 6.0 | +5% |

**Fórmula:** K30 = E / (α × 30), on α=2.5 (granular) i α=2.0 (roca).

**Conclusió:** Desviació mínima i consistent. No cal ajustar.

---

### ✅ phi — Funciona bé per granulars (±0.5%)

| Projecte | Generat | Eva | Δ% | Observació |
|-----------|---------|-----|-----|------------|
| Bell-Lloc | 38.2 | 38 | +0.5% | Granular ✓ |
| Castellar | 35.0 | 35 | 0% | Roca (manual) ✓ |
| Rubí | 38.8 | 39 | -0.5% | Granular ✓ |
| **Linyola** | **35.8** | **28** | **+28%** | **Cohesiu!** ❌ |

**Causa Linyola:** Usem la taula CTE 4.1 (N20→phi), que és per a sòls **granulars**. Linyola L1 és "llims argilosos" — material **cohesiu** on la taula 4.1 no aplica. Eva assigna phi=28° per criteri de sòl cohesiu (taula D.27: limo phi=25-32°, argila phi=16-28°).

**Pregunta per Eva:** Quan tens un material cohesiu (llims, argiles), d'on treus phi? Directament de D.27 per tipus de sòl? O uses una altra correlació?

---

### ⚠️ gamma — Biaix sistemàtic +7%

| Projecte | Generat | Eva | Δ% |
|-----------|---------|-----|-----|
| Bell-Lloc | 2.16 | 2.0 | +8% |
| Castellar | 2.20 | 2.20 | 0% (manual) |
| Rubí | 2.18 | 2.0 | +9% |
| Linyola | 2.12 | 1.90 | +12% |

**Patró:** En tots els granulars, el nostre gamma és un 7-12% superior al d'Eva. L'únic cas correcte és Castellar (roca, valor introduït manualment).

**Fórmula actual:** CTE D.27 interpolat amb posició N20 dins el rang gamma. Exemple per Rubí: grava gamma=19-22 kN/m³, N20=40 → ratio=40/50=0.8, gamma=21.4 kN/m³ = 2.18 g/cm³.

**Observació:** Eva usa valors arrodonits: 2.0, 1.90, 2.20. Podria ser que:
- a) Arrodoneix a la baixa per seguretat (gamma més baix → Qa més conservadora)
- b) Usa un criteri diferent de D.27 (per exemple, valors típics per litologia)
- c) No interpola dins el rang sinó que agafa el valor inferior o mig

**Pregunta per Eva:** Com determines la densitat? Interpoles dins D.27 segons N20, o assignes un valor típic per la litologia que observes?

---

### ⚠️⚠️ E — Dispersió extrema (397pp)

| Projecte | Generat | Eva | Δ% | Observació |
|-----------|---------|-----|-----|------------|
| Castellar | 500 | 500 | 0% | Roca (manual) ✓ |
| Rubí | 469 | 450 | +4% | Conservador funciona |
| **Bell-Lloc** | **469** | **650** | **-28%** | **Eva posa E alt!** |
| **Linyola** | **469** | **100** | **+369%** | **Nivells incorrectes** |

**Anàlisi cas per cas:**

**Rubí (N20=40, SPT=40):** El nostre E conservador (E_min + 10% del rang CTE D.23) dona 469. Eva posa 450. Encaixa bé.

**Bell-Lloc (N20=36.7, SPT=54):** El nostre E conservador dona 469 (rang "medios" 25-50). Però Eva posa **650**. Això és sorprenent perquè:
- 650 kg/cm² = 63.7 MN/m², que cau dins el rang "medios" del CTE (40-100 MN/m²)
- Però Bell-Lloc té SPT=54, que és rang "compactos" (50+)
- Eva podria basar-se en l'SPT (no el N20 DPSH) per determinar E
- O bé el material carbonatat de Bell-Lloc justifica un E superior

**Linyola (N20=29, sense SPT L1):** El nostre generador fa 1 sol nivell amb N20=29 → E=469. Eva fa 2 nivells: L1 (llims, E=100) i L2 (lutites, E>800). El problema no és la fórmula d'E sinó la manca de 2 nivells.

**Hipòtesi invalidada:** Amb Rubí semblava que "Eva usa banda baixa CTE D.23". Bell-Lloc demostra que no és mecànic — Eva adapta E cas per cas.

**Pregunta per Eva:** Per a Bell-Lloc, l'E=650 es basa en l'SPT=54? O en la litologia (material carbonatat competent)? Tens una correlació SPT→E preferida?

---

### ⚠️⚠️ Qa — Dispersió alta (87pp)

| Projecte | Generat | Eva | Δ% | Observació |
|-----------|---------|-----|-----|------------|
| Castellar | 3.18 | 3.0 | +6% | Acceptable |
| Rubí | 3.18 | 3.50 | -9% | Acceptable |
| **Bell-Lloc** | **5.33** | **3.0** | **+78%** | **Crític** |
| **Linyola** | **4.95** | **3.0** | **+65%** | **Crític** |

**Observació important:** Eva posa Qa=3.0 en 3 de 4 projectes, i 3.50 a Rubí. Podria ser que:
- a) Eva calcula amb Terzaghi i obté valors propers als nostres, però **arrodoneix a la baixa** per seguretat
- b) Eva usa un mètode diferent (Terzaghi-Peck amb N/12?)
- c) Eva **limita** Qa a un màxim pràctic (3.0-3.5 kg/cm² per habitatges)

La base de càlcul adjunta als informes d'Eva cita Terzaghi-Peck per granulars: `Qa = N/12 × [(B+0.3)/B]²`. Per Bell-Lloc (N=54, B=1m): Qa = 54/12 × (1.3/1)² = 7.6. Tampoc coincideix amb 3.0.

**Possibilitat més probable:** Eva obté un valor de càlcul i l'**arrodoneix a la baixa** fins a un valor conservador que considera adequat per la tipologia d'obra. Qa=3.0 és un valor "segur i pràctic" per habitatges.

**Pregunta per Eva:** Quan calcules Qa, poses el valor exacte del càlcul o l'arrodoneix a la baixa? Tens un màxim pràctic per tipologia d'obra (ex: 3.0-3.5 per habitatges)?

---

### ⚠️ Assentament — Dispersió alta (65pp)

| Projecte | Generat | Eva | Δ% | Observació |
|-----------|---------|-----|-----|------------|
| Bell-Lloc | 1.21 | 1.20 | +1% | Perfecte! |
| Linyola | 1.13 | 1.0 | +13% | Acceptable |
| Castellar | 0.72 | 1.0 | -28% | Baix |
| Rubí | 0.72 | 1.50 | -52% | Molt baix |

**Patró:** Eva expressa assentaments en valors arrodonits: 1.0, 1.20, 1.50. Podria ser que:
- Calcula i arrodoneix a l'alça (per seguretat)
- Usa un mètode diferent al nostre (elasticitat vs Schmertmann?)
- El nostre assentament és massa baix perquè l'E és massa alt (Rubí: E=469 nostre vs 450 Eva, però assentament 0.72 vs 1.50)

**Nota:** L'assentament és inversament proporcional a E. Però a Rubí, encara que E és similar (469 vs 450), l'assentament difereix molt. Això suggereix que Eva usa una **fórmula d'assentament diferent**, no simplement Qa×B/E.

**Pregunta per Eva:** Quin mètode uses per calcular assentaments? Elasticitat amb E directament? Schmertmann? Terzaghi-Peck amb N?

---

### Cohesió mínima (c=0.05)

| Projecte | Generat | Eva | Material |
|-----------|---------|-----|----------|
| Castellar | 1.0 | 1.0 | Roca ✓ |
| Bell-Lloc | 0.0 | 0.0 | Granular pur ✓ |
| Rubí | 0.0 | 0.05 | Granular natural |
| Linyola L1 | 0.0 | 0.05 | Cohesiu |

**Observació:** Eva afegeix c=0.05 kg/cm² als materials naturals que no són purament granulars. "Graves i sorres" de Rubí i "Llims argilosos" de Linyola reben c=0.05. "Graves en matriu sorrenca" de Bell-Lloc rep c=0.0 (potser perquè és més netament granular?).

**Pregunta per Eva:** El c=0.05, és un valor estàndard que poses als materials naturals no granulars purs? O depèn del material?

---

## 3. Classificació dels Gaps

### Per causa

| Tipus | Paràmetres | Fix |
|-------|-----------|-----|
| **Biaix sistemàtic** | gamma (+7%) | Ajustar fórmula D.27 o arrodonir |
| **Criteri professional** | E (cas per cas), Qa (arrodoniment), c (0.05) | Preguntar Eva, implementar regles |
| **Dada d'entrada** | Nivells (Castellar/Linyola), phi Linyola | Wizard / user_data |
| **Mètode de càlcul** | Assentament (fórmula diferent?) | Investigar |
| **Resolt** | K30 (+4%), phi granular (±0.5%) | — |

### Per impacte a l'informe final

| Prioritat | Gap | Impacte |
|-----------|-----|---------|
| 🔴 Crític | Qa 2/4 projectes >60% | Valor clau de l'informe |
| 🔴 Crític | E Bell-Lloc -28% | Afecta K30, assentament |
| 🟡 Alt | gamma +7% sistemàtic | Afecta Qa, Terzaghi |
| 🟡 Alt | Assentament mètode | 2/4 projectes >28% desviació |
| 🟢 Mitjà | c=0.05 granulars naturals | Afecta Qa lleugerament |
| 🟢 Mitjà | Nivells (input) | Depèn de dades camp |
| ✅ Resolt | K30 | +4.4% consistent |
| ✅ Resolt | phi granular | ±0.5% |

---

## 4. Preguntes Resumides per a Eva

1. **E (mòdul deformació):** Com determina E? Usa D.23 directament, o adapta segons SPT i litologia? Per què E=650 a Bell-Lloc (N20=37, SPT=54)?

2. **gamma (densitat):** Interpola dins D.27 o assigna valors típics per litologia? Per què sempre arrodoneix a la baixa?

3. **Qa (capacitat portant):** Posa el valor exacte de Terzaghi o arrodoneix? Té un límit pràctic per tipologia (3.0-3.5)?

4. **Assentament:** Quin mètode usa? Elasticitat amb E? Terzaghi-Peck amb N? Per què Rubí=1.50 amb E=450?

5. **Cohesió mínima:** El c=0.05 és estàndard per materials naturals?

6. **phi cohesiu:** Per llims/argiles (Linyola), d'on treu phi=28? De D.27 directament?

---

## 5. Annexos Tècnics

### Taules CTE usades

| Taula | Ús | Estat |
|-------|-----|-------|
| D.23 | N20 → E | Funciona per Rubí, falla per Bell-Lloc |
| D.27 | Tipus sòl → gamma, phi | gamma +7% alt; phi OK granulars |
| D.29 | Tipus sòl → K30 | No usada directament (derivem de E) |
| 4.1 | N20 → phi (granulars) | ✅ Funciona bé (±0.5%) |

### Fórmules implementades

```
phi     = Interpolació CTE 4.1 (N20→phi)           [granulars]
gamma   = Interpolació CTE D.27 (N20/50 dins rang)  [tots]
E       = E_min + 10% rang CTE D.23                 [conservador]
K30     = E / 75 (granular) o E / 60 (roca)          [Winkler]
Qa      = Terzaghi (phi, gamma, c, B, Df, FS=3)     [clàssic]
Assent. = Qa × B / E                                 [elàstic simplificat]
```

### Historial de commits

| Data | Canvi | Commit |
|------|-------|--------|
| 2026-02-25 | K30 roca E/60 | `1b4b20d` |
| 2026-02-25 | E conservador (E_min + 10%) | `833e063` |
| 2026-02-25 | K30 granular E/75 | `a5b8759` |
| 2026-02-25 | Docs K30 + E per Eva | `c02ca07`, `40560b4` |
