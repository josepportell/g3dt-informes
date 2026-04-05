Executa la comparació Eva vs Pipeline per veure com de bé el pipeline reprodueix els valors dels informes reals d'Eva.

Executa:
```bash
.venv/bin/python scripts/compare_eva_vs_pipeline.py
```

Analitza els resultats i reporta:
1. Quantes variables coincideixen (MATCH), s'apropen (CLOSE) o fallen (MISMATCH)
2. Per als MISMATCH: explica per què difereixen i si el valor d'Eva es troba en algun candidat alternatiu
3. Suggereix accions concretes per millorar les variables amb MISMATCH

Si l'usuari demana `--verbose`, executa amb el flag per veure totes les variables (incloses les MATCH).
