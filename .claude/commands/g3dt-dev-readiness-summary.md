---
description: "Report readiness summary across all projects"
---

# /g3dt-dev-readiness-summary

Genera un resum formatat del readiness de tots els projectes, llegint dades recollides prèviament.

## Instruccions

Quan l'usuari invoca aquest skill:

### Pas 1: Localitzar dades

Busca les dades en aquest ordre de prioritat:

1. **`docs/validation-latest/_summary.json`** — Fitxer resum generat per `scripts/collect_readiness.py`. Si existeix, utilitza'l directament.
2. **`docs/validation-latest/*.json`** (excloent `_summary.json`) — Fitxers individuals per projecte. Si el directori existeix amb JSONs, llegeix-los tots.
3. **`docs/validation-adjacents-2026-03-27/*-wizard.txt`** — Fitxers de text cru del wizard. Si ni `validation-latest/` ni els JSONs existeixen, parseja aquests fitxers manualment (format descrit a Pas 1b).

Si cap font existeix, mostra:

```
No s'han trobat dades de readiness.
Executa primer: python scripts/collect_readiness.py
O bé: recull els resultats manualment a docs/validation-latest/
```

I atura l'execució.

### Pas 1b: Parseig de fitxers wizard text (fallback)

Els fitxers `*-wizard.txt` tenen aquest format (una variable per línia):

```
90%
36 / 40 variables
Identificacio
83.3%
5/6
Ubicacio
100%
7/7
...
```

El patró és: nom de categoria, percentatge, fração `filled/total`, repetit per cada categoria. La primera línia és el percentatge global, la segona el recompte global.

### Pas 2: Generar taula resum

Mostra la taula amb el format exacte. Ordena per readiness % descendent.

```markdown
## Report Readiness -- {data}

| Projecte | Readiness | Variables | Identif. | Ubicacio | Edifici. | DPSH | Sondeig | Lab | Geologia | Geotecnia | Calculs | Warns |
|-----------|-----------|-----------|----------|----------|----------|------|---------|-----|----------|-----------|---------|-------|
| **Bell-Lloc** | **100%** | 41/41 | 6/6 | 7/7 | 8/8 | 4/4 | 1/1 | 1/1 | 4/4 | 7/7 | 3/3 | 0 |
| **Linyola** | **95%** | 38/40 | 5/6 | 7/7 | 7/8 | 4/4 | 0/0 | 1/1 | 4/4 | 7/7 | 3/3 | 2 |
| Anciles | 82% | 33/40 | 4/6 | 7/7 | 5/8 | 4/4 | 0/0 | 1/1 | 4/4 | 5/7 | 3/3 | 5 |
```

**Regles de format:**
- **Nom del projecte en negreta** sempre.
- **Readiness en negreta** si >= 90%.
- Categories amb **0 filled** (0/N on N>0): marca amb `**0/N**` per destacar-les.
- Si `Sondeig` es mostra com `0/0`, significa que el projecte no te sondeig (no es un gap).
- La columna `Warns` compta els warnings del terminal log (si es disposa de la informacio).

### Pas 3: Analisi per tiers

Despres de la taula, genera l'analisi:

```markdown
### Tier 1 (>= 90% readiness)
- **Bell-Lloc** (100%): Complet. Cap gap.
- **Linyola** (95%): Falta `data_signatura_text`, `superficie_construida`.

### Tier 2 (< 90% readiness)
- **Anciles** (82%): Gaps a Identificacio (4/6) i Edificacio (5/8). Falta architect_company, data_signatura_text, cota_referencia, access_description.

### Ubicacio health
{Tots els projectes 100%? -> "Pipeline de geocodificacio OK: tots 7/7."}
{Algun < 100%? -> "ATENCIO: {projecte} te ubicacio incompleta ({filled}/{total}). Revisar geocode pipeline."}

### Common gaps
Variables mes frequentment buides (ordenades per frequencia):
1. `data_signatura_text` -- absent a {N} projectes (no extret automaticament)
2. `architect_company` -- absent a {N} projectes
3. ...
```

### Pas 4: Accions rapides

```markdown
### Quick actions
1. **{variable}** (afecta {N} projectes): {que fer per resoldre-ho}
2. ...
```

Exemples d'accions:
- `data_signatura_text` absent: "Eva ho posa manualment. No cal accio de codi."
- `architect_company` absent: "SmartScan hauria d'extreure-ho del planol. Revisar prompt."
- Ubicacio incompleta: "Revisar geocode_coordinates.py per al municipi afectat."
- Sondeig 0/0: "Projecte sense sondeig -- normal, no cal accio."
- Edificacio gaps: "Verificar que SmartScan mina el planol correctament."

### Pas 5: Resum final

Tanca amb una linia de resum:

```
---
**Resum**: {N} projectes analitzats. {T1} a Tier 1 (>=90%), {T2} a Tier 2 (<90%).
Readiness mitja: {avg}%. Gap mes comu: `{variable}` ({N} projectes).
```

## Notes

- Aquesta skill NO fa peticions HTTP ni executa el pipeline. Nomes llegeix dades ja recollides.
- Si les dades son antigues (mes d'una setmana), suggereix tornar a executar `scripts/collect_readiness.py`.
- Les categories del readiness corresponen a `READINESS_VARIABLES` definit a `web/api.py`.
- El Sondeig es condicional (`has_sondeig`): 0/0 indica que no aplica, no que falta.
