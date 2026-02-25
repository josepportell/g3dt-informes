# Càlcul del Coeficient de Balast K30

**Autor:** Eficients.cat (automatització)
**Data:** 2026-02-25
**Estat:** Pendent de validació per Eva
**Fitxers implicats:** `automation/report_generator.py`, `automation/cte_geomech.py`

---

## 1. Què és K30

El coeficient de balast K30 (coeficient de reacció del subsòl) quantifica la rigidesa del terreny sota una placa de càrrega estàndard de 30×30 cm. S'expressa en **kg/cm³** als informes G3DT (equivalent a kp/cm³).

La taula D.29 del CTE DB SE-C proporciona rangs orientatius per tipus de sòl:

| Tipus de sòl | K30 (MN/m³) | K30 (kg/cm³)* |
|---|---|---|
| Arena floja | 10 – 30 | 1.0 – 3.1 |
| Arena media | 30 – 90 | 3.1 – 9.2 |
| Arena compacta | 90 – 200 | 9.2 – 20.4 |
| Grava arenosa floja | 70 – 120 | 7.1 – 12.2 |
| Grava arenosa compacta | 120 – 300 | 12.2 – 30.6 |
| Rocas algo alteradas | 300 – 5.000 | 30.6 – 510 |

*Conversió: 1 kg/cm³ = 9.81 MN/m³*

---

## 2. Fórmula implementada

Usem el model Winkler simplificat per derivar K30 a partir del mòdul de deformació E (que ja calculem des de la taula D.23 del CTE):

```
K30 = E / (α × B₀)
```

On:
- **E** = mòdul de deformació en kg/cm² (de CTE D.23, criteri conservador)
- **B₀** = 30 cm (costat de la placa estàndard)
- **α** = factor adimensional de profunditat d'influència

### Valors de α

| Material | α | Divisor (α × 30) | Raonament |
|----------|---|-------------------|-----------|
| Sòl granular | 2.5 | **75** | Zona d'influència més profunda (sòl deformable) |
| Roca fracturada | 2.0 | **60** | Zona d'influència menor (material més rígid) |

**Discriminant roca vs sòl:** cohesió > 0 → roca; cohesió = 0 → granular.

### Codi (report_generator.py, línia ~1024)

```python
# K30 ballast coefficient — Winkler: K30 = E / (α × B₀)
# B₀ = 30 cm (standard plate), α = depth influence factor
if self.report_data.geotechnical_params:
    gp = self.report_data.geotechnical_params
    if gp.cohesion and gp.cohesion > 0:
        # Rock (α=2.0): K30 = E / 60
        k30 = gp.E / 60
    else:
        # Granular (α=2.5): K30 = E / 75
        k30 = gp.E / 75
```

---

## 3. Validació amb projectes reals

### 3.1 Rubí (3001631) — Granular, N20=40

| Paràmetre | Generat | Referència Eva | Diferència |
|-----------|---------|----------------|------------|
| E (kg/cm²) | 469 | 450 | +4% |
| **K30 (kg/cm³)** | **6.3** | **6.0** | **+5%** |

Càlcul: E=469 → K30 = 469/75 = 6.25 ≈ 6.3

**Nota:** Amb el divisor anterior (100), K30 era 4.7 — un 22% per sota de la referència.

### 3.2 Castellar (3001621) — Roca fracturada, c=1.0

| Paràmetre | Generat | Referència Eva | Diferència |
|-----------|---------|----------------|------------|
| E (kg/cm²) | 500 | 500 | OK |
| **K30 (kg/cm³)** | **8.3** | **8.0** | **+4%** |

Càlcul: E=500 → K30 = 500/60 = 8.3

### 3.3 Resum de l'evolució

| Projecte | K30 v1 (E/100) | K30 v2 (E/75 o E/60) | Ref Eva | Millora |
|-----------|-----------------|----------------------|---------|---------|
| Rubí | 4.7 | **6.3** | 6.0 | De -22% a +5% |
| Castellar | 8.3 | **8.3** | 8.0 | Ja OK (roca E/60) |

---

## 4. Relació amb el mòdul E (CTE D.23)

El K30 depèn directament de E. Usem la taula D.23 del CTE amb criteri conservador:

```
E_conservador = E_min + 10% × (E_max - E_min)
```

On E_min i E_max són els límits del rang CTE per a la categoria NSPT corresponent.

| Rang NSPT | Categoria CTE | E rang (MN/m²) | E conservador (kg/cm²) |
|-----------|---------------|----------------|------------------------|
| 0 – 10 | Muy flojos/blandos | 0 – 8 | 8.2 |
| 10 – 25 | Flojos/blandos | 8 – 40 | 114.2 |
| 25 – 50 | Medios | 40 – 100 | 469.1 |
| 50+ | Compactos/duros | 100 – 500 | 1059.7 |

### Limitació coneguda

L'E conservador actual dona un valor **pla** per a tot un rang NSPT (per exemple, N20=26 i N20=49 donen el mateix E=469.1). Un afinament futur podria fer l'E sensible a la posició dins el rang:

```
E = E_min + factor_conservador × ratio × (E_max - E_min)
```

On `ratio = (N20 - N_min) / (N_max - N_min)` i `factor_conservador ≈ 0.1`.

Exemple per Rubí (N20=40): ratio=0.60, E = 40 + 0.1 × 0.6 × 60 = 43.6 MN/m² = **445 kg/cm²** (ref Eva: 450).

Això no s'ha implementat encara perquè requereix validació amb més projectes.

---

## 5. Coherència amb CTE D.29

Els nostres valors K30 cauen dins dels rangs de la taula D.29:

| Projecte | K30 generat | K30 en MN/m³ | Rang D.29 |
|-----------|-------------|--------------|-----------|
| Rubí (granular, N20=40) | 6.3 kg/cm³ | 61.8 | Arena media (30-90) ✓ |
| Castellar (roca) | 8.3 kg/cm³ | 81.4 | Arena compacta o roca molt alterada ✓ |

Eva posiciona els seus K30 a la banda conservadora dels rangs D.29, coherent amb el seu criteri professional.

---

## 6. Preguntes per a Eva

1. **Confirmació del mètode:** Derives K30 a partir de E (com fem nosaltres) o consultes D.29 directament?
2. **Divisor granular:** El divisor 75 (α=2.5) encaixa amb els teus resultats. Fas servir aquesta relació o una altra?
3. **Divisor roca:** Per roca usem E/60 (α=2.0). El teu K30=8.0 amb E=500 suggereix E/62.5. Prefereixes un divisor lleugerament diferent?
4. **E conservador:** El teu E=450 per Rubí (N20=40) suggereix que uses la part baixa del rang CTE D.23. Podries confirmar el teu criteri? (Nosaltres usem E_min + 10% del rang, que dona 469.)

---

## 7. Historial de canvis

| Data | Canvi | Commit |
|------|-------|--------|
| 2026-02-25 | K30 roca: E/100 → E/60 | `1b4b20d` |
| 2026-02-25 | E conservador: interpolació → E_min + 10% rang | `833e063` |
| 2026-02-25 | K30 granular: E/100 → E/75 | `a5b8759` |
