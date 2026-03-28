---
description: "Benchmark comparison: Eva's values vs pipeline (tiered)"
---

# /g3dt-dev-benchmark-compare

Mostra la comparacio entre els valors de referencia d'Eva (benchmarks) i els valors del nostre pipeline, organitzada per tiers.

## Instruccions

### Pas 1: Localitzar dades

1. **`docs/benchmarks/_comparison.json`** — generat per `scripts/compare_benchmarks.py`.
2. **`docs/CORRECTNESS-TRACKER.md`** — document viu amb analisi de cada desviacio.
3. Si _comparison.json no existeix o es antic (>1 setmana):
   ```
   python scripts/compare_benchmarks.py
   ```

### Pas 2: Resum per projecte amb tiers

```markdown
## Benchmark — {data}

| Projecte | Readiness | Tier A | Tier B | Tier C | Overall |
|----------|-----------|--------|--------|--------|---------|
| **Bell-Lloc** | 100% | 12/21 (57%) | 0/8 (0%) | 0/3 (0%) | 12/32 (38%) |
```

**Tiers:**
- **A (Auto-extractable)**: pipeline hauria de fer-ho be. Objectiu: 95%.
- **B (Manual/on-site)**: requereix input d'Eva o dades externes (Street View). Objectiu: best effort.
- **C (Criteri professional)**: Eva ajusta per experiencia. Objectiu: transparencia.
- **Exclòs**: `data_signatura_text` (correcte per disseny — sempre data actual).

### Pas 3: Detall per tier

#### Tier A

Agrupa les variables per status:

```markdown
### Tier A — Auto-extractable (objectiu: 95%)

**OK (100% match):** `num_dpsh_tests`, `sulfate_value`, `architect_company`

**Format mismatch (quick fix):**
- `radon_zone`: "ZONA 1" vs "1" — pipeline guarda nomes el numero
- `seismic_ab_text`: "AB < 0,04 g" vs "0,04" — pipeline guarda nomes el valor
- `dpsh_test_ids`: "P-1,P-2" vs "P-1, P-2" — espais

**Metric mismatch (redesign):**
- `dpsh_avg_n20`: Eva diu Nb, pipeline calcula N20 — metriques diferents
- `geotech_nb`: Eva diu Nb numeric, pipeline mostra notacio de refus ("12-R")

**Partial (investigar per projecte):**
- `client`: 1/7 — pipeline pilla "INTECSON" (laboratori, no client)
- `building_type`: 0/7 — pipeline mostra titol del projecte, no tipus edifici
- etc.
```

Per cada variable PARTIAL o WRONG, consulta `docs/CORRECTNESS-TRACKER.md` per la causa arrel i accions pendents.

#### Tier B

```markdown
### Tier B — Manual/on-site (0/54)

| Variable | Problema | Millora proposada |
|----------|----------|-------------------|
| `adjacent_*` | Cadastre labels vs prosa d'Eva | Street View API, satellite |
| `site_condition` | Hardcoded "antropitzat" | Street View, classificacio satellit |
| `location_sentence` | Template formulaic | Millorar template amb context |
```

#### Tier C

```markdown
### Tier C — Criteri professional (3/17)

| Variable | Pipeline | Eva | Formula | Nota |
|----------|----------|-----|---------|------|
| `geotech_E` | 469 | 650 | CTE D.23 | Eva ajusta per carbonatades |
| `qa_value` | 2.40 | 3.0 | Terzaghi-Peck | Eva aplica topall |
```

Mostrar les formules que apliquem i per que el resultat difereix. Objectiu: Eva veu que entenem el calcul i pot dir-nos si hem de canviar algo.

### Pas 4: Prioritats d'accio

Consulta `docs/CORRECTNESS-TRACKER.md` seccio "Action priority" i mostra:

```markdown
### Accions prioritzades

**P0 (quick wins):** format fixes que donen millora immediata
**P1 (investigacio):** entendre causa arrel abans de tocar codi
**P2 (transparencia):** mostrar formules al wizard per Tier C
**P3 (best effort):** Street View, satellite, millorar Tier B
```

### Pas 5: Historial de canvis

Mostra les ultimes entrades del Change log de `docs/CORRECTNESS-TRACKER.md`.

## Notes

- Aquesta skill NO executa scripts. Nomes llegeix dades ja generades.
- El document `docs/CORRECTNESS-TRACKER.md` es el document viu — actualitzar-lo a cada fix.
- Cada fix hauria de: (1) actualitzar codi, (2) re-executar `compare_benchmarks.py`, (3) actualitzar CORRECTNESS-TRACKER.md amb el nou resultat.
