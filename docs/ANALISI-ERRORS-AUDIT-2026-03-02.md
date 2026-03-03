# Anàlisi d'Errors — Audit Bell-Lloc 2026-03-02

## Resum

L'audit de Bell-Lloc (98.8% qualitat, 4 DADES_ERRÒNIES, 16 missing) va revelar **2 bugs crítics** que afecten la majoria de reports generats.

---

## Bug 1: Truncament de Paràgrafs de la Història Geològica (CRÍTIC)

### Símptoma
L'audit marca com a "missing" 4 paràgrafs de la secció geològica:
- ref_idx 192: "A partir de finals de l'Eocè i durant tot l'Oligocè..."
- ref_idx 194: "Des de finals de L'Oligocè fins a l'actualitat..."
- ref_idx 196: "En concret, i segons l'ICGC, afloren els materials de la unitat Qvpu..."
- ref_idx (extra): "El present estudi s'ha realitzat principalment sobre ventalls..."

### Causa Arrel Confirmada

El template `.docx` només té **6 slots fixos** per paràgrafs de geologia:
```
geology_para_1, geology_para_2, ..., geology_para_6
```

El flux del codi:
1. `_build_marc_geologic_from_eva()` intenta fusionar paràgrafs extra amb `'\n\n'.join()` (MAX_SLOTS=5)
2. Retorna un string unit amb `'\n\n'` com a separador
3. `report_generator.py` fa `split('\n\n')` → **desfà la fusió**
4. Només els primers 6 paràgrafs es mapen als slots del template
5. **Paràgrafs 7+ es perden silenciosament**

### Impacte

```
Distribució de paràgrafs als 238 templates d'Eva:
  1-6 paràgrafs:   64 templates (27%)  → OK
  7-10 paràgrafs: 124 templates (52%)  → TRUNCATS
  11-15 paràgrafs: 33 templates (14%)  → TRUNCATS
  16-20 paràgrafs:  8 templates (3%)   → TRUNCATS
  21+ paràgrafs:    9 templates (4%)   → TRUNCATS

  Mediana: 8 paràgrafs
  P95: 17 paràgrafs
  Max: 344 paràgrafs
```

**El 73% dels templates d'Eva perden contingut.** El template de Lleida (usat per Bell-Lloc/Linyola) té 9 paràgrafs → 3 es perden + el paràgraf ICGC (4 total).

### Simulació

```
Template Lleida: 9 paràgrafs
Merge + ICGC: 6 ítems (correcte)
Split per \n\n: 10 paràgrafs (la fusió es desfà!)

geology_para_1 [RENDERITZAT]: En primer lloc s'ha procedit...
geology_para_2 [RENDERITZAT]: Full 33: Segrià...
geology_para_3 [RENDERITZAT]: Hoja 388: Lleida...
geology_para_4 [RENDERITZAT]: La zona que engloba...
geology_para_5 [RENDERITZAT]: La conca de l'Ebre...
geology_para_6 [RENDERITZAT]: Durant l'Eocè...
geology_para_7 [PERDUT!]:     A partir de finals de l'Eocè...  ← ref_idx 192
geology_para_8 [PERDUT!]:     Des de finals de L'Oligocè...    ← ref_idx 194
geology_para_9 [PERDUT!]:     El present estudi s'ha realitzat...
geology_para_10 [PERDUT!]:    En concret, i segons l'ICGC...   ← ref_idx 196
```

### Solució

Reemplaçar els 6 slots fixos amb un for-loop Jinja al template docx:
```
{%p for p in geology_paragraphs %}{{ p }}{%p endfor %}
```

Canvis:
- `section3_geologia.py`: Retornar llista de paràgrafs (sense fusió MAX_SLOTS)
- `report_generator.py`: Passar `geology_paragraphs` com a llista
- `g3dt-jinja-template.docx`: For-loop al lloc dels 6 variables fixes

---

## Bug 2: Filtre de Capes Sondeig (CRÍTIC)

### Símptoma
- Material description: "Llims argilosos amb graves" vs Eva's "Graves en matriu sorrenca carbonatades"
- c_coeff: 1.6 vs Eva's 1.30
- Valors incorrectes de phi, E a la taula de paràmetres

### Causa Arrel Confirmada

Quan `num_soil_levels=1` (l'usuari indica 1 nivell) però `sondeig_layers` té 2 capes, el codi filtra les lectures DPSH per la profunditat de la primera capa del sondeig.

```python
# report_generator.py, línies 1034-1040
sondeig_layers = self.user_data.get('sondeig_layers', [])
if sondeig_layers and level.level_number <= len(sondeig_layers):
    sl = sondeig_layers[level.level_number - 1]  # layer[0] = 0.0-1.0m!
    d_from = sl.get('depth_from_m', 0)
    d_to = sl.get('depth_to_m', 999)
    level_readings = [r for r in all_readings if d_from <= abs(r.depth_m) <= d_to]
```

Amb `num_soil_levels=1`, Level 1 agafa `sondeig_layers[0]` (profunditat 0.0-1.0m).

### Impacte numèric (Bell-Lloc)

| Mètrica | Filtrat (0-1.0m) | Totes les lectures | Eva |
|---------|-------------------|-------------------|----|
| Lectures DPSH | 8 de 18 | 18 de 18 | 18 |
| N20 mitjana | 18.8 | 36.7 | ~40 |
| Tipus sísmic | Tipus III | Tipus II | Tipus II |
| c_coeff | **1.6** | **1.3** | **1.30** |

El sondeig (forat amb rotació) arriba fins a 1.8m.
Els penetròmetres DPSH arriben fins a 4-6m amb N20 molt més alts.
Filtrar per la profunditat del sondeig exclou les lectures profundes dels penetròmetres.

### Efecte cascada

El filtre incorrecte causa:
- **Material desc incorrecte**: Usa la desc de la capa superficial (0-1.0m): "Llims argilosos amb graves" en lloc de la capa dominant (1.0-1.8m): "Graves en matriu sorrenca carbonatades"
- **c_coeff 1.6**: Tipus III (N20<30) en lloc de Tipus II (N20≥30)
- **phi incorrecte**: Calculat amb N20=18.8 en lloc de 36.7
- **E incorrecte**: Calculat amb N20=18.8 en lloc de 36.7
- **Nb range incorrecte**: Només lectures superficials
- **Valors taula missing** (ref_idx 515-520): "25-R", "54", "38°", "650" no es generen correctament

### Solució

Només aplicar el filtre de profunditat quan el nombre de nivells de l'usuari coincideix amb el nombre de capes del sondeig:

```python
num_user_levels = self.user_data.get('num_soil_levels', 1)
if sondeig_layers and num_user_levels == len(sondeig_layers) and level.level_number <= len(sondeig_layers):
    # Filtra per profunditat
    ...
# Si no coincideixen → usa TOTES les lectures per cada nivell
```

---

## Bug 3: Descripció de Material per Projectes d'1 Nivell

### Símptoma
El report genera "Llims argilosos amb graves" quan hauria de dir "Graves en matriu sorrenca carbonatades".

### Causa Arrel
Quan `num_soil_levels=1` i `sondeig_layers` té 2 capes:
- El codi agafa la descripció de `sondeig_layers[0]` (la capa superficial, 0-1.0m)
- Eva utilitza la capa dominant/profunda per descriure tot el nivell
- Bell-Lloc: capa 0 = "Llims argilosos amb graves" (0-1.0m), capa 1 = "Graves incloses en matriu sorrenca d'aspectes carbonatats" (1.0-1.8m)

### Solució
Quan `num_soil_levels=1` i hi ha múltiples `sondeig_layers`:
- Utilitzar la descripció de la capa més gruixuda (o la més profunda)
- Alternativa: combinar les descripcions
- Fallback: ICGC unit description

---

## Altres Findings (prioritat baixa)

### "280+86" (superfície per planta)
- Feature no implementada. `superficie_construida_m2` és un valor únic (366)
- Caldria un camp `superficie_breakdown` al wizard
- **Prioritat: BAIXA** — cosmètic, no funcional

### Nota d'exempció sísmica (ref_idx 284)
- "Cal indicar que l'aplicació de la norma resistent no és obligatòria..."
- Paràgraf condicional que hauria d'aparèixer per edificis d'importància baixa
- Verificar si el template el genera

### Entrades de laboratori (ref_idx 475, 480, 481, 489)
- Valors de la taula de resultats de laboratori ("Graves en matriu sorrenca", sulfats)
- Possiblement afectat pel Bug 3 (desc material incorrecta)

---

## Pla de Verificació

### Pas 1: Aplicar fixes (Bugs 1, 2, 3)
Modificar: `section3_geologia.py`, `report_generator.py`, `report_data.py`, `g3dt-jinja-template.docx`

### Pas 2: Convertir .doc → .docx (per auditoria)
```bash
libreoffice --headless --convert-to docx "reference-material/3001621.../3001621_informe_v0.doc"
libreoffice --headless --convert-to docx "reference-material/3001631.../3001631_informe.doc"
libreoffice --headless --convert-to docx "reference-material/4001607.../4001607_informe.doc"
```

### Pas 3: Regenerar i auditar els 4 projectes
| Projecte | Comarca | Template historia | Capes sondeig |
|----------|---------|-------------------|---------------|
| Bell-Lloc | Pla d'Urgell | Lleida (Tier 3, 9 paras) | 2 → 1 nivell |
| Castellar | Vallès Occidental | Castellar (Tier 1, 13 paras) | 2+ → ? nivells |
| Rubí | Vallès Occidental | Rubí (Tier 1, 8 paras) | ? |
| Linyola | Pla d'Urgell | Lleida (Tier 3, 9 paras) | ? |

### Pas 4: Comparar patrons d'error
Objectiu: 0 DADES_ERRÒNIES per bugs corregits, identificar errors projecte-específics.

---

## Fitxers a Modificar

| Fitxer | Canvi | Línies |
|--------|-------|--------|
| `automation/sections/section3_geologia.py` | Eliminar MAX_SLOTS merge, afegir llista paràgrafs | ~569-589 |
| `automation/report_generator.py` | Usar llista paràgrafs, fix filtre sondeig | ~882-891, 1034-1040 |
| `automation/report_data.py` | Fix desc SoilLevel per single-level | construcció soil levels |
| `templates/g3dt-jinja-template.docx` | Reemplaçar 6 slots fixes amb for-loop | secció geologia |

---

*Anàlisi generada: 2026-03-02*
*Basada en: audit_intelligent.json de Bell-Lloc + simulació de codi*
