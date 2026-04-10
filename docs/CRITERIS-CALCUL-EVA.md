# Criteris de càlcul de l'Eva — Reverse-engineered

**Data:** 2026-04-10
**Mètode:** Bateria de tests sistemàtica sobre 7 projectes amb paràmetres reals
extrets dels PDFs signats d'Eva via PyMuPDF.
**Resultat:** 6/7 projectes MATCH exacte.

---

## 1. Cadena de càlcul Qa (capacitat portant admissible)

```
N20 camp (DPSH)
  → Nb = N20 / 0.83  (arrodonit a enter — Dapena, Lacasa & García, 2000)
  → phi des de taula CTE/Schmertmann (arrodonit a enter)
  → Calcular:
      a) Terzaghi-Peck: Nb/12 × Fd  (Fd = 1 + D/(3B))
      b) Full Terzaghi: qu/F=3  (qu = c·Nc·sc + γ·Df·Nq·sq + 0.5·γ·B·Nγ·sγ)
  → Qa_raw = max(a, b)
  → Aplicar cap segons classificació del sòl
  → Qa = round_to_0.5(min(Qa_raw, cap))
```

### Classificació del sòl (per determinar el cap)

Basada en les dades del DPSH (Nb) i la cohesió (c):

| Classificació | Criteri | Cap Qa (kg/cm²) | Projectes verificats |
|---|---|---|---|
| **ROCK** | c ≥ 0.5 | 3.0 | Castellar (c=1.0), Linyola L2 (c=1.0) |
| **DENSE** | Nb ≥ 25 i c < 0.5 | 3.5 | Rubí (Nb=47), Alcoletge (Nb=30), Bell-Lloc (Nb=25) |
| **SOFT** | Nb < 25 i c < 0.5 | 3.0 (o Terzaghi si menor) | Vilanova (Nb=15), Anciles (Nb=5) |

**Nota sobre roca:** Eva va dir "3.0 topall per sòl, en roca clara 4.0-4.50". Per roca
mixta (bretxes amb lutites, com Castellar), aplica 3.0. El cap 4.0-4.5 seria per
roca massissa sana — no tenim cap projecte d'aquest tipus entre els 7.

### Arrodoniment intermedi

Eva arrodoneix phi al bracket de la taula CTE **ABANS** de calcular Terzaghi.
Verificat: Vilanova amb phi=28 (taula Eva) → Terzaghi = 2.0. Amb phi=30 (bracket CTE
per Nb=15) → Terzaghi = 2.5 = Eva. La diferència de 2° canvia el resultat en 0.5.

### Estrat de fonamentació

Per projectes multi-nivell, Eva calcula amb l'**estrat portant** (el més profund on
es recolza la fonamentació), no amb el primer nivell.
- Linyola: usa L2 (lutites, Nb=31) no L1 (llims, Nb=13)
- Anciles: usa L1 (argiles, Nb=5) no L2 (bolos, Nb=15) — perquè la fonamentació
  es recolza en L1 (les argiles), no arriba a L2

---

## 2. Settlement (assentaments)

```
Es = 2.5 × Nb  (Schmertmann, default per sabata quadrada)
Settlement = Schmertmann simplificat amb Es
→ round_to_0.1 cm
```

### Comportament d'Eva

- Si settlement < 1.0 cm → frase genèrica: "menyspreables o inferiors a 1.0 cm"
- Si settlement ≥ 1.0 cm → valor precís arrodonit a 0.1: "inferiors a 1.20 cm"
- Es és **judici professional** — Eva va dir: "l'agafo com a criteri després de molts estudis"
- Pipeline usa Es=2.5×Nb com a default, Eva ajusta al wizard si cal

### Referència de valors d'Eva

| Projecte | Eva settlement | Tipus |
|---|---|---|
| Bell-Lloc | 1.20 cm | Valor precís (granular, immediat) |
| Rubí | 1.50 cm | Valor precís |
| Anciles | 1.5 cm | Valor precís |
| Castellar | ≤1.0 cm | Frase genèrica (roca) |
| Linyola | ≤1.0 cm | Frase genèrica |
| Alcoletge | ≤1.0 cm | Frase genèrica |
| Vilanova | ≤1.0 cm | Frase genèrica |

---

## 3. K30 (coeficient de balast)

```
K30 = round_to_int(E / 75)  si sòl granular
K30 = round_to_int(E / 60)  si roca
```

**Verificat 2/2 projectes amb K30:**
- Castellar (roca, E=500): 500/60 = 8.33 → **8** = Eva 8.0 ✓
- Rubí (granular, E=450): 450/75 = 6.00 → **6** = Eva 6.0 ✓

---

## 4. Arrodoniment professional (confirmat com a pràctica estàndard)

| Paràmetre | Arrodoniment | Evidència |
|---|---|---|
| **Qa** | 0.5 kg/cm² | 7/7 projectes: 2.0, 2.5, 3.0, 3.5 |
| **K30** | Enter kg/cm³ | 2/2: 6, 8 |
| **Settlement** | 0.1 cm | 3/3: 1.0, 1.2, 1.5 |
| **E** | 10 o 50 kg/cm² | 7/7: 80, 90, 100, 350, 450, 500, 650, 800 |
| **phi** | Enter graus | 7/7: 25, 28, 30, 35, 38, 39 |
| **gamma** | 0.1 g/cm³ | 7/7: 1.90, 2.00, 2.20 |
| **c** | 0.05 kg/cm² | 7/7: 0.00, 0.05, 0.10, 1.00 |

### Confirmació externa (recerca Exa, 2026-04-10)

**Font: inforcivil.com** — "Capacidad Portante de Suelos: Tabla Valores Referenciales":
> "Los valores de tensión admisible que se suelen encontrar en los suelos
> oscilan entre los 0,5 y 3 Kg/cm²"

Taula de referència estàndard:
| Material | Qa referència (kg/cm²) |
|---|---|
| Roca dura sana (granit, basalt) | 40 |
| Roca mig dura (pissarres) | 20 |
| Roca tova o fissurada | 7 |
| Conglomerat compacte | 4 |
| Graves, mescla arena i grava | 2 |
| Arena grossa | 2 |
| Arena fina a mitja | 1.5 |
| Argila inorgànica firme | 1.5 |
| Argila inorgànica tova | 0.5 |
| Llim inorgànic | 0.25 |

Tots valors rodons (0.25, 0.5, 1.5, 2.0, 4.0...) — confirma que l'arrodoniment
és pràctica estàndard, no un caprici d'Eva.

**Font: geotecniafacil.com** — Càlcul online tensió admissible CTE-SEC:
Mètode simplificat per sòls granulars basat en SPT, limitat a 25mm d'assentament.
Coincideix amb el mètode Terzaghi-Peck que Eva utilitza.

**Font: verificacioncte.es** — Comparativa cimentació superficial vs profunda:
> "Estratos resistentes qa > 150 kPa [≈1.5 kg/cm²]" per cimentació superficial.
> "SPT N > 15 en primeros 3 m" com a criteri mínim.
Coincideix amb els llindars d'Eva (Nb ≥ 15 → sòl acceptable).

**Font: oa.upm.es** — PFC Belén Polo (2013), comparativa normatives:
CTE usa `N_SPT` per correlacions, amb correccions per profunditat i ample.
Confirma el mètode Terzaghi-Peck com a pràctica estàndard al CTE-SEC.

---

## 5. Paràmetres d'Eva per projecte (extrets dels PDFs signats)

| Projecte | Nivell | Material | Nb | N | γ | c | φ | E | Qa |
|---|---|---|---|---|---|---|---|---|---|
| Bell-Lloc | 1 | Graves en matriu sorrenca | 25 | 54 | 2.0 | 0.0 | 38 | 650 | 3.0 |
| Castellar | 1 | Bretxes amb lutites i gresos | 17 | R | 2.20 | 1.0 | 35 | >500 | 3.0 |
| Rubí | 1 | Graves i sorres | 47 | 40 | 2.0 | 0.05 | 39 | 450 | 3.5 |
| Linyola | 1 | Llims argilosos sorrencs | 13 | -- | 1.90 | 0.05 | 28 | 100 | 3.0 |
| Linyola | 2 | Lutites i sorrenques | 31 | R | 2.20 | 1.0 | 30 | >800 | — |
| Alcoletge | 1 | Graves carbonatades | 30 | ? | 2.0 | 0.05 | 37 | 500 | 3.5 |
| Vilanova | 1 | Llims argilosos | 15 | -- | 1.90 | 0.05 | 28 | 100 | 2.5 |
| Anciles | 1 | Arcillas arenosas | 5 | 6 | 1.90 | 0.10 | 28 | 90 | 2.0 |
| Anciles | 2 | Bolos y gravas en matriz | 15 | -- | 2.00 | 0.00 | 38 | >350 | — |

---

## 6. Outlier: Anciles (Qa=2.0)

Únic projecte on la fórmula no encaixa exactament.
- Full Terzaghi (phi=28, c=0.10) = 2.50 → round = 2.5
- Eva diu 2.0

Hipòtesis:
1. Eva usa phi=25-26 (Schmertmann amb n baix per argiles) → Full = 2.0
2. Eva aplica el valor de referència de taula per "argila arenosa" (2.0)
3. Eva arrodoneix cap avall per precaució en argiles febles (Nb=5)

Qualsevol de les tres dóna 2.0. És el projecte on el judici professional
d'Eva pesa més que la fórmula.
