# Càlcul del Mòdul de Deformació E

**Autor:** Eficients.cat (automatització)
**Data:** 2026-02-25
**Estat:** Pendent de validació per Eva
**Fitxers implicats:** `automation/cte_geomech.py` (funció `nspt_to_E_kg_cm2`)

---

## 1. Què és E

El mòdul de deformació E (o mòdul d'elasticitat del sòl) quantifica la rigidesa del terreny sota càrrega. S'expressa en **kg/cm²** als informes G3DT.

És un paràmetre fonamental perquè d'ell es deriven:
- **Assentament** de la fonamentació (inversament proporcional a E)
- **K30** coeficient de balast (directament proporcional a E — veure `docs/CALCUL-K30-BALAST.md`)
- Influeix en la **rigidesa de la llosa** i el dimensionament estructural

---

## 2. Font: Taula D.23 del CTE DB SE-C

La taula D.23 ("Valores orientativos de qu y E en función de NSPT") proporciona rangs d'E per a cada categoria de compacitat:

| Rang NSPT | Categoria CTE | E (MN/m²) | E (kg/cm²) |
|-----------|---------------|-----------|------------|
| 0 – 10 | Muy flojos / muy blandos | 0 – 8 | 0 – 82 |
| 10 – 25 | Flojos / blandos | 8 – 40 | 82 – 408 |
| 25 – 50 | Medios | 40 – 100 | 408 – 1.020 |
| 50+ | Compactos / duros | 100 – 500 | 1.020 – 5.098 |

*Conversió: 1 MN/m² = 10,197 kg/cm²*

**Observació clau:** Els rangs són molt amplis. Per exemple, un sòl "medio" (N20 entre 25 i 50) pot tenir E entre 408 i 1.020 kg/cm². On es posiciona dins el rang és una decisió d'enginyeria.

---

## 3. Criteri d'Eva: banda conservadora

De la comparació amb informes de referència, hem observat que Eva usa consistentment la **banda baixa** del rang CTE:

| Projecte | N20 | Rang CTE (kg/cm²) | E d'Eva | Posició dins rang |
|-----------|-----|-------------------|---------|-------------------|
| Rubí | 40 | 408 – 1.020 | **450** | 7% del rang |
| Castellar | roca | — | **500** | Override manual |

Eva no interpola linealment dins el rang (cosa que donaria valors molt alts), sinó que es queda a la part baixa. Això és criteri professional de seguretat: un E conservador produeix assentaments més grans (pitjor cas) i per tant dissenys més segurs.

---

## 4. Implementació actual

### Fórmula (v1 — implementada)

```
E_conservador = E_min + 10% × (E_max - E_min)
```

Dona un valor fix per a tot el rang NSPT. Exemple: qualsevol N20 entre 25 i 50 dona E = 469,1 kg/cm².

### Codi (cte_geomech.py, línia ~140)

```python
if conservative:
    # Conservative: E_min + 10% of range (matches Eva's practice)
    E_MN = E_min + 0.1 * (E_max - E_min)
```

### Limitació: valor pla

L'E actual no distingeix dins el rang. N20=26 i N20=49 donen el mateix E:

| N20 | Posició dins rang | E interp. completa | E conservador actual | E ref Eva |
|-----|-------------------|-------------------|---------------------|-----------|
| 26 | 4% | 432 kg/cm² | 469 kg/cm² | — |
| 30 | 20% | 530 kg/cm² | 469 kg/cm² | — |
| 35 | 40% | 653 kg/cm² | 469 kg/cm² | — |
| **40** | **60%** | **775 kg/cm²** | **469 kg/cm²** | **450** |
| 45 | 80% | 897 kg/cm² | 469 kg/cm² | — |
| 49 | 96% | 995 kg/cm² | 469 kg/cm² | — |

Per a Rubí (N20=40), el valor pla (469) és acceptable (+4% respecte Eva). Però per a N20 extrems dins el rang (26 o 49) podria ser massa alt o massa baix.

---

## 5. Proposta de millora (v2 — pendent)

### Fórmula millorada

```
E_conservador = E_min + 10% × ratio × (E_max - E_min)
```

On `ratio = (N20 - N_min) / (N_max - N_min)` és la posició relativa dins el rang CTE.

### Diferència conceptual

| Mètode | Què fa | Resultat |
|--------|--------|----------|
| **Interpolació completa** | E = E_min + ratio × rang | Usa tot el rang (massa alt) |
| **Conservador v1 (actual)** | E = E_min + 10% × rang | Fix, ignora posició dins rang |
| **Conservador v2 (proposta)** | E = E_min + 10% × ratio × rang | Escala amb N20, però comprimit al 10% |

### Comparació per a la banda medios (N20 = 25–50)

| N20 | E interp. completa | E cons. v1 (actual) | E cons. v2 (proposta) |
|-----|-------------------|--------------------|-----------------------|
| 26 | 432 | 469 | **410** |
| 30 | 530 | 469 | **420** |
| 35 | 653 | 469 | **432** |
| **40** | **775** | **469** | **445** |
| 45 | 897 | 469 | **457** |
| 49 | 995 | 469 | **467** |

### Validació amb Rubí (N20=40)

| Paràmetre | v1 (actual) | v2 (proposta) | Ref Eva |
|-----------|-------------|---------------|---------|
| E (kg/cm²) | 469 | **445** | **450** |
| K30 (E/75) | 6,3 | **5,9** | **6,0** |
| Diferència E | +4,2% | **-1,1%** | — |
| Diferència K30 | +5,0% | **-1,7%** | — |

La v2 acosta E de 469→445 (ref 450) i K30 de 6,3→5,9 (ref 6,0).

---

## 6. Per què no hem implementat v2 encara

1. **Només tenim 1 cas de referència granular** (Rubí). Necessitem validar amb més projectes.
2. **Castellar** usa override manual (roca, E=500 via `geomech_params`) → no valida la fórmula.
3. **Bell-Lloc i Linyola** no tenen informe de referència complet per comparar.
4. La v1 ja dona resultats acceptables (error < 5% a K30).

**Quan implementar v2:** Quan tinguem 2-3 projectes granulars més amb referència d'Eva. Si el patró "banda baixa del rang CTE" es confirma, la v2 és una millora clara.

---

## 7. Altres paràmetres derivats de CTE

Per context, així és com es calculen els altres paràmetres geomecànics:

| Paràmetre | Taula CTE | Mètode | Fitxer |
|-----------|-----------|--------|--------|
| **phi** (angle fregament) | 4.1 | Interpolació lineal N20→phi | `cte_geomech.py:96` |
| **E** (mòdul deformació) | D.23 | Banda conservadora (10% rang) | `cte_geomech.py:122` |
| **gamma** (densitat) | D.27 | Interpolació dins rang per tipus sòl | `cte_geomech.py:156` |
| **K** (permeabilitat) | D.28 | Classificació per descripció | `cte_geomech.py:240` |
| **K30** (balast) | — | E / (α × 30) | `report_generator.py:1024` |
| **Qa** (cap. portant) | — | Terzaghi amb phi, gamma, c | `terzaghi_calculator.py` |

**Nota:** phi (taula 4.1) usa interpolació lineal directa perquè la taula dóna parelles discretes N20→phi, no rangs amplis. Això funciona bé i no requereix criteri conservador.

---

## 8. Preguntes per a Eva

1. **Confirmació del criteri conservador:** Quan mires la taula D.23 per a un N20 de, per exemple, 40 (rang "medios", E = 40–100 MN/m²), on et posiciones dins el rang? Sempre la part baixa?

2. **Sensibilitat a N20:** Si tens dos projectes, un amb N20=26 i un altre amb N20=49, ambdós "medios" al CTE, els donaries E diferent? O un valor similar perquè estan al mateix rang?

3. **Roca:** Per Castellar (roca fracturada), el teu E=500 kg/cm² ≈ 49 MN/m². Això cau a la part molt baixa de "rocas blandas" (500–8.000 MN/m²). Hi ha algun criteri específic per roca que segueixis?

4. **Relació E↔K30:** Derives K30 directament d'E (com fem nosaltres), o consultes la taula D.29 de manera independent?

---

## 9. Historial de canvis

| Data | Canvi | Commit |
|------|-------|--------|
| 2026-02-25 | E conservador: interpolació lineal → E_min + 10% rang | `833e063` |
| — | E conservador v2: E_min + 10% × ratio × rang | Pendent de validació |
