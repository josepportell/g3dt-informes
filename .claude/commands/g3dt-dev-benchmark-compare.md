---
description: "Benchmark comparison: Eva's values vs pipeline"
---

# /g3dt-dev-benchmark-compare

Mostra la comparacio entre els valors de referencia d'Eva (benchmarks) i els valors del nostre pipeline.

## Instruccions

### Pas 1: Localitzar dades

Busca les dades en aquest ordre:

1. **`docs/benchmarks/_comparison.json`** — Fitxer generat per `scripts/compare_benchmarks.py`. Si existeix i te menys d'una setmana, utilitza'l.
2. Si no existeix o es antic, suggereix:
   ```
   Executa primer:
   python scripts/extract_reference_text.py    # Extreu text dels .docx
   python scripts/extract_benchmark_values.py  # Extreu valors estructurats (requereix API)
   python scripts/compare_benchmarks.py        # Genera la comparacio
   ```

### Pas 2: Taula de correctesa per projecte

Per cada projecte al JSON, mostra:

```markdown
## Benchmark Comparison -- {data}

### {expedient} {municipality} ({correctness_pct}% correct)

| Variable | Eva | Pipeline | Desv. | Status |
|----------|-----|----------|-------|--------|
| geotech_E | 650 | 469 | -27.8% | **MISMATCH** |
| qa_value | 2.98 | 2.40 | -19.5% | **MISMATCH** |
| geotech_phi | 39 | 35° | -10.3% | CLOSE |
| client | RAMON MITJANA S.L. | RAMON MITJANA S.L. | - | MATCH |
| ... | ... | ... | ... | ... |
```

**Regles de format:**
- **MISMATCH** en negreta vermell (usa `**MISMATCH**`)
- CLOSE en text normal
- MATCH en text normal (o ometre si `--verbose` no es demana)
- Ordena: MISMATCH primer, despres CLOSE, despres MATCH
- Per variables numeriques, mostra la desviacio %
- Per variables de text, mostra "-" a la columna desviacio

### Pas 3: Resum global

```markdown
## Resum Global

| Projecte | Correctesa | Match | Close | Mismatch | Missing |
|----------|------------|-------|-------|----------|---------|
| **Bell-Lloc** | **72.0%** | 18 | 3 | 4 | 5 |
| **Rubi** | **85.0%** | 20 | 2 | 2 | 1 |
| ... | ... | ... | ... | ... | ... |

**Total**: {N} variables comparades. {match} MATCH, {close} CLOSE, {mismatch} MISMATCH.
Correctesa global: {pct}%
```

### Pas 4: Analisi de gaps

```markdown
## Variables amb mes MISMATCH

1. **geotech_E** — MISMATCH a {N} projectes. Causa probable: Eva ajusta E per criteri professional (carbonatades, etc.)
2. **qa_value** — MISMATCH a {N} projectes. Causa: diferencia entre T-P auto i cap d'Eva.
3. ...

## Variables amb 100% MATCH

{Llista de variables que sempre coincideixen — indica que el pipeline es fiable per aquelles.}
```

### Pas 5: Readiness vs Correctness

Si existeix `docs/validation-latest/_summary.json`, creua les dades:

```markdown
## Readiness vs Correctness

| Projecte | Readiness | Correctesa | Gap |
|----------|-----------|------------|-----|
| Bell-Lloc | 100% | 72% | 28% |
| Rubi | 95% | 85% | 10% |

**Interpretacio**: Readiness = camp omplert. Correctesa = valor correcte.
Un projecte pot tenir 100% readiness pero baixa correctesa (camps plens amb valors erronis).
```

### Pas 6: Accions prioritzades

```markdown
## Accions per millorar correctesa

1. **{variable}** (desv. mitja {X}%, afecta {N} projectes): {accio suggerida}
2. ...
```

Exemples d'accions:
- `geotech_E`: "Eva ajusta E manualment. Auto-prefill es orientatiu. Considerar flag 'needs_review'."
- `qa_value`: "Revisar terzaghi_calculator.py — cap professional vs formula."
- `settlement`: "Revisar Es default (2.5*Nb). Eva pot usar diferent Es."
- Text mismatches: "Revisar prompt d'extraccio SmartScan per al camp afectat."

## Notes

- Aquesta skill NO executa scripts. Nomes llegeix dades ja generades.
- Benchmarks son els valors CORRECTES d'Eva (signed reports). Pipeline son els nostres valors auto-generats.
- La tolerancia per defecte es 5% per numerics. CLOSE es <= 15%.
- Variables d'array (dpsh_tests, sondeig_tests, etc.) no es comparen — massa complexes per comparacio escalar.
