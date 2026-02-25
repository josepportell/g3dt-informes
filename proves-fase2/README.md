# Proves Fase 2 — Afinament d'Informes Geotècnics

## Objectiu

Cicle iteratiu de millora de la generació automàtica d'informes:
**generar → comparar amb referència → analitzar diferències → corregir → repetir**

Fins que els informes generats s'aproximin al màxim als de referència de G3DT.

## Metodologia

1. Generar informe amb el pipeline actual
2. Comparar secció per secció amb l'informe de referència (PDF de G3DT)
3. Documentar diferències amb causes arrel
4. Aplicar fixes al codi
5. Regenerar i documentar com a nova execució (run)

## Estructura de carpetes

```
proves-fase2/
├── README.md                          (aquest fitxer)
├── 3001621-castellar/
│   ├── run-001_2026-02-24.md          (anàlisi comparativa)
│   ├── run-001_3001621_generated.docx (còpia de l'informe generat)
│   └── run-002_...                    (execucions posteriors)
├── 3001631-rubi/
├── 4001607-linyola/
└── 4001612-bell-lloc/
```

## Convenció de noms

| Fitxer | Descripció |
|--------|-----------|
| `run-NNN_YYYY-MM-DD.md` | Document de comparació (anàlisi + causes + fixes) |
| `run-NNN_{expedient}_generated.docx` | Còpia de l'informe generat en aquella execució |

Numeració seqüencial per run dins cada projecte.

## Com executar una prova

**Directori de treball:** Sempre des de `clients/g3dt/`

```bash
# 1. Generar informe
cd clients/g3dt && .venv/bin/python -c "
from automation.report_generator import ReportGenerator
from pathlib import Path
project = Path('reference-material/{CARPETA}')
gen = ReportGenerator(str(project), str(project / 'user_data.json'))
result = gen.generate(str(project / '{EXPEDIENT}_generated.docx'))
print('Success:', result.success)
for w in result.warnings: print('WARNING:', w)
for e in result.errors: print('ERROR:', e)
"

# 2. Comparar amb referència
# Extreure text del .docx generat i del PDF referència
# Comparar secció per secció

# 3. Documentar a proves-fase2/{projecte}/run-NNN_YYYY-MM-DD.md
```

## Projectes de prova

| Expedient | Municipi | Referència |
|-----------|----------|-----------|
| 3001621 | Castellar del Vallès | `reference-material/3001621 CASTELLAR DEL VALLES/` |
| 3001631 | Rubí | `reference-material/3001631 RUBI/` |
| 4001607 | Linyola | `reference-material/4001607 LINYOLA/` |
| 4001612 | Bell-Lloc | `reference-material/4001612 BELL-LLOC/` |

## Pla de fixes

Veure `docs/PLA-FASE2-AFINAMENT-INFORMES.md` per al pla complet amb 9 fixes prioritzats.
