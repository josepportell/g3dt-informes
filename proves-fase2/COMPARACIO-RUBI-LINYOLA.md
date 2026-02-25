# Comparació: Informes Generats vs Referència G3DT

**Data:** 2026-02-25
**Projectes validats:** Rubí (3001631), Linyola (4001607)
**Projectes anteriors:** Bell-Lloc (4001612), Castellar (3001621)

---

## Resum Executiu

| Projecte | Generació | Nivells | Qa match | K30 match | Sulfats | Gaps principals |
|-----------|-----------|---------|----------|-----------|---------|-----------------|
| Bell-Lloc | OK | 1/1 | ~OK | OK (6.9) | 89.8 mg/kg | Sense sondeig de referència |
| Castellar | OK | 2/2 | OK (3.18) | OK (8.3) | 0.0 mg/kg | Roca + pendent: resolt |
| **Rubí** | OK | 1/1 | **3.18 vs 3.50** | **7.6 vs 6.0** | 632.3 mg/kg | E massa alt, params desviats |
| **Linyola** | OK | **1 vs 2** | **4.95 vs 3.0** | **5.1 vs ?** | 0.0 mg/kg | Sense sondeig → 1 nivell, falta §4.3 expansivitat |

---

## 1. RUBÍ (3001631) — Solar pla, granular, 1 nivell

### Dades de generació
```
Municipality: Rubi
is_sloped: False
sulfate_mg_kg: 632.3
soil_levels: 1 (Nivell principal, n20=40)
gamma=2.18, phi=38.8, c=0.0, E=763
Qa=3.18, settlement=0.72, K30=7.6
```

### Comparació amb referència G3DT

| Paràmetre | Generat | Referència | Diferència |
|-----------|---------|------------|------------|
| Nivells | 1 | 1 | OK |
| Descripció | "Nivell principal" | "Graves i sorres, marró clar" | Generic vs específic |
| Nb | — | 47-R | No mostrat |
| N | — | 40 | N20 coincideix |
| **Densitat (gamma)** | **2.18** | **2.0** | +9% |
| **Cohesió** | **0.0** | **0.05** | Eva afegeix cohesió mínima |
| Angle fregament (phi) | 38.8 | 39 | ~OK |
| **Mòdul E** | **763** | **450** | **+70% — CRÍTIC** |
| **Qa** | **3.18** | **3.50** | -9% |
| **Assentament** | **0.72 cm** | **1.50 cm** | **-52% — CRÍTIC** |
| **K30** | **7.6** | **6.0** | +27% |
| Sulfats | 632 mg/kg (Qa) | "no agressius" | OK (mateixa conclusió) |
| Antropitzat | "antropitzat" | "**no** antropitzat" | Invertit |
| Aigua freàtica | No | No | OK |

### Diagnòstic Rubí

**Problema principal: E massa alt (763 vs 450)**

L'E es calcula amb les taules CTE D.23 a partir del N20 mitjà. Amb N20=40:
- CTE D.23 rang "medios" (25-50): E = 40-100 MN/m² = 400-1000 kg/cm²
- La fórmula interpola linealment → 763 kg/cm²
- Eva usa 450 (rang inferior, criteri conservador)

**Impacte en cascada:**
- E alt → K30 alt (E/100 = 7.6 vs 4.5 amb E=450)
- E alt → assentament baix (0.72 vs 1.50 — Eva calcula amb E més realista)
- Qa difereix menys (-9%) perquè depèn més de phi que d'E

**Altres gaps:**
- `is_anthropized` no pobla correctament (user_data.json)
- Descripció genèrica "Nivell principal" → necessita sondeig o user_data.description
- Cohesió 0.05 d'Eva → criteri professional (no pure zero per materials naturals)

---

## 2. LINYOLA (4001607) — Solar pla, 2 nivells amb expansivitat

### Dades de generació
```
Municipality: Linyola
is_sloped: False
sulfate_mg_kg: 0.0
soil_levels: 1 (Nivell principal, n20=29)
gamma=2.12, phi=35.8, c=0.0, E=510
Qa=4.95, settlement=1.13, K30=5.1
```

### Comparació amb referència G3DT

| Paràmetre | Generat | Referència | Diferència |
|-----------|---------|------------|------------|
| **Nivells** | **1** | **2** | **CRÍTIC — sense sondeig** |
| L1 desc | "Nivell principal" | "Llims argilosos i sorrencs" | Generic |
| L1 Nb | — | 13 | — |
| L1 gamma | — | 1.90 | — |
| L1 c | — | 0.05 | — |
| L1 phi | — | 28 | — |
| L1 E | — | 100 | — |
| L2 desc | — | "Lutites i sorrenques" | — |
| L2 Nb | — | 31-R | — |
| L2 gamma | — | 2.20 | — |
| L2 c | — | 1.0 | — |
| L2 phi | — | 30 | — |
| L2 E | — | >800 | — |
| **Qa** | **4.95** | **3.0** | **+65% — CRÍTIC** |
| **Assentament** | **1.13 cm** | **<1.0 cm** | Desviació menor |
| K30 | 5.1 | (no indicat) | — |
| Sulfats | 0.0 mg/kg | "no agressius" | OK |
| **§4.3 Expansivitat** | **ABSENT** | **Present (LL=41.7)** | **CRÍTIC** |
| Fonamentació tipus | Sabates | **Pous + sabates combinada** | Diferent solució |

### Diagnòstic Linyola

**Problema 1: 1 nivell vs 2 nivells**

Sense dades de sondeig (`has_sondeig: False`, no hi ha `sondeig_extracted.json`), el generador fa:
- Totes les lectures DPSH → 1 sol nivell amb N20 mitjana = 29
- Però el real té L1 (feble, N20~13) i L2 (competent, N20~31+R)
- La separació requereix sondeig o que Eva indiqui els nivells a user_data

**Problema 2: Qa molt diferent (4.95 vs 3.0)**

- Generat: calcula amb N20=29 global → phi=35.8, Qa=4.95
- Referència: Eva calcula amb L2 (on recolza fons) → phi=30, E>800, Qa=3.0
- La diferència és perquè Eva usa paràmetres del nivell de fonamentació (L2), no la mitjana global

**Problema 3: Falta §4.3 Expansivitat**

Linyola té materials argilosos amb LL=41.7 (>35 → potencialment expansius). La referència inclou:
- Secció 4.3 completa amb anàlisi d'expansivitat
- Pressió d'inflament: 0.82 kg/cm²
- Classificació Lambe: MARGINAL
- Recomanacions de drenatge

El template actual no té secció d'expansivitat condicional (com sí té empentes i estabilitat).

**Problema 4: Fonamentació combinada**

Eva recomana "fonamentació combinada entre sabates i pous reomplerts de formigó pobre" perquè L1 és feble. El generador recomana sabates estàndard perquè veu N20=29 (acceptable).

---

## 3. Patrons Comuns Detectats

### A. E (Mòdul de deformació) — Sistemàticament alt

| Projecte | E generat | E referència | Ràtio |
|-----------|-----------|-------------|-------|
| Castellar | 500 | 500 | 1.0x (roca, OK) |
| Rubí | 763 | 450 | 1.7x |
| Linyola | 510 | 100-800 | Variable |

**Causa:** La interpolació CTE D.23 usa el rang complet. Eva aplica criteri conservador (rang inferior).
**Solució possible:** Paràmetre `E_conservative_factor` o lookup que retorni rang inferior per defecte.

### B. Nivells — Requereix sondeig o input manual

Sense sondeig_extracted.json, el generador crea 1 sol nivell. Eva sempre fa >= 1 nivell per capa identificada.
**Solució:** Wizard (Fase 2) ha de preguntar nivells quan no hi ha sondeig. O Eva omple user_data.

### C. Descripcions genèriques

"Nivell principal" no aporta res. Eva escriu "Graves i sorres" o "Llims argilosos".
**Solució:** Ja resolt si hi ha sondeig_extracted. Si no, user_data.soil_level_descriptions.

### D. Seccions condicionals pendents

| Secció | Castellar | Rubí | Linyola | Implementat? |
|--------|-----------|------|---------|-------------|
| §4.4 Empentes | SI | NO | NO | SI |
| §4.5 Estabilitat | SI | NO | NO | SI |
| §4.3 Expansivitat | NO | NO | SI | **NO** |

L'expansivitat és condicional: apareix quan LL > 35 (límit líquid alt). Requereix:
- Dades de laboratori (LL, LP, IP)
- Càlcul de pressió d'inflament
- Classificació Lambe

---

## 4. Prioritats de Millora

### Alta prioritat (afecta Qa/K30/assentament)
1. **E conservador** — Aplicar rang inferior CTE D.23 per defecte
2. **Nivells sense sondeig** — Permetre definició manual a user_data
3. **Paràmetres per nivell** — GeotechnicalParams hauria de ser per-level (ara és global)

### Mitjana prioritat (completesa)
4. **§4.3 Expansivitat** — Secció condicional nova (LL > 35)
5. **Fonamentació combinada** — Suport per "pous + sabates" (quan L1 és feble)
6. **is_anthropized** — Auto-detectar o assegurar que user_data el defineix

### Baixa prioritat (cosmètic)
7. **Descripcions nivell** — Fallback a user_data si no hi ha sondeig
8. **Cohesió mínima** — Eva posa c=0.05 en materials naturals (no zero pur)

---

## 5. Conclusions

- **Castellar i Bell-Lloc** funcionen bé perquè tenen sondeig_extracted i/o user_data complert
- **Rubí** genera correctament però els paràmetres E i derivats són massa alts (criteri CTE vs Eva)
- **Linyola** és el cas més complex: 2 nivells no detectats, expansivitat absent, fonamentació combinada
- El **bottleneck principal** és la qualitat de les dades d'entrada (sondeig + user_data), no el generador en si
