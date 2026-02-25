# Pla Detallat: Fase 2 — Afinament Informe Castellar

**Data creació:** 2026-02-25
**Estat:** IMPLEMENTAT
**Sessió implementació:** 2026-02-25

## Context

Tots els fixes de la sessió anterior (6+3) estaven implementats. L'informe generat de Castellar ja detectava roca, usava Hoek & Bray, i calculava empentes correctament. Quedaven 4 gaps menors que afinaven la fidelitat respecte l'informe real de referència.

Referència: `reference-material/3001621 CASTELLAR DEL VALLES/`

---

## A. K30 per roca: 5.0 → ~8.3 kg/cm³

### Problema detectat
`report_generator.py:1026` calculava `K30 = E / 100`. Per roca (E=500) donava 5.0. L'informe real diu 8.0.

### Raonament tècnic
El divisor 100 és correcte per sòls granulars (CTE D.29, relació empírica K30 ≈ E/100 per sorres i graves).

Per roca fracturada, la rigidesa del llit de reacció és superior perquè:
- La roca, encara que fracturada, té major rigidesa volumètrica
- El CTE D.29 per "rocas algo alteradas" dona un rang de K30 que, amb E=500 kg/cm², resulta en divisors de 50-70
- Divisor 60 → K30 = 500/60 = 8.3, molt proper al 8.0 real

### Discriminant roca vs sòl
Es va decidir usar la **cohesió (c > 0)** com a discriminant perquè:
- Els sòls granulars tenen c=0 (sense cohesió)
- La roca fracturada sempre té c > 0 (en el cas de Castellar, c=1.0 kg/cm²)
- Ja existia a `cte_geomech.py` la funció `is_rock()` però el discriminant per cohesió és més directe i no requereix passar per la descripció litològica

### Implementació
```python
# Fitxer: automation/report_generator.py (~línia 1024)
gp = self.report_data.geotechnical_params
if gp.cohesion and gp.cohesion > 0:
    k30 = gp.E / 60   # Roca: CTE D.29
else:
    k30 = gp.E / 100  # Sòl granular
```

### Validació
- Castellar (E=500, c=1.0): 500/60 = **8.3** (real = 8.0, diferència < 4%)
- Bell-Lloc (E=694.8, c=0.0): 694.8/100 = **6.9** (no canvia)

---

## B. §4.5 referencia nivell correcte

### Problema detectat
`section4_conclusions.py:516-518` sempre escrivia "1r nivell (Llims argilosos)" però els paràmetres geomecànics phi=35, c=1.0 corresponen al 2n nivell (Roca fracturada).

### Raonament
El `geotechnical_params` del `report_data` és global (no per-nivell). S'usava `soil_levels[0]` hardcodejat. Però quan hi ha roca, els paràmetres d'estabilitat es calculen amb els paràmetres de la roca (que és el nivell portant), no del primer nivell superficial.

### Lògica de matching
```
SI cohesion > 0 (paràmetres de roca):
    → Buscar el nivell que sigui roca (via is_rock)
    → Mostrar "2n nivell (Roca fracturada)"
SI NO:
    → Usar primer nivell (default anterior)
    → Mostrar "1r nivell (Llims argilosos)"
```

S'usa la funció `is_rock()` de `cte_geomech.py` que detecta roca per:
- N20 >= 100 (refús)
- Descripció amb keywords: "roca", "roche", "calcària", "grès", etc.

### Implementació
```python
# Fitxer: automation/sections/section4_conclusions.py (~línia 515)
level_desc = "terreny"
if self.data.soil_levels:
    matched = self.data.soil_levels[0]
    if params.cohesion > 0:
        from ..cte_geomech import is_rock
        for lvl in self.data.soil_levels:
            if is_rock(lvl.n20_average or 0, lvl.description):
                matched = lvl
                break
    idx = self.data.soil_levels.index(matched)
    ordinals = ["1r", "2n", "3r", "4t"]
    ordinal = ordinals[idx] if idx < len(ordinals) else f"{idx+1}è"
    level_desc = f"{ordinal} nivell ({matched.description})"
```

### Validació
- Castellar: **"2n nivell (Roca fracturada)"** amb phi=35, c=1.0
- Bell-Lloc: sense §4.5 (no sloped) → no afecta

---

## C. FS display: truncar a ">3.5"

### Problema detectat
FS=10.47 és matemàticament correcte (Hoek & Bray amb c=1.0, H=4m, beta=20°) però G3DT escriu "superiors a 3.5" als informes. Valors molt alts no aporten informació addicional i poden generar confusió.

### Raonament
- FS > 3.5 és tan sobradament complidor que el valor exacte és irrellevant
- G3DT segueix la convenció professional de truncar a ">3.5"
- El llindar 3.5 és > 2× el mínim exigit (F=1.5), indicant compliment "amb escreix"

### Implementació (doble canvi)
1. **Línia de càlcul:** Si FS > 3.5, mostrar "FS > 3.5" en lloc de "FS = 10.47"
2. **Conclusió:** Si FS > 3.5, text especial: "superiors a 3.5, complint amb escreix les premisses del CTE"

```python
# Display
fs_display = "FS > 3.5" if result.safety_factor > 3.5 else f"FS = {result.safety_factor:.2f}"

# Conclusió
if result.safety_factor > 3.5:
    "Els factors de seguretat obtinguts son superiors a 3.5,
     complint amb escreix les premisses del CTE (minim exigit F=1.5)."
elif result.compliant:
    # Text normal amb valor exacte
```

### Validació
- Castellar (FS=10.47): **"FS > 3.5" + "superiors a 3.5, complint amb escreix"**
- Un cas hipotètic amb FS=1.8: mostraria "FS = 1.80" + text normal

---

## D. §4.2 drenatge — template fix

### Problema detectat
El codi a `generate_water_statement()` ja afegia la recomanació de drenatge quan `is_sloped=True`:
```
"Amb tot, donada la pendent de la zona, es recomana dimensionar
una correcta xarxa de recollida d'aigües..."
```

Però la plantilla `.docx` tenia el text de §4.2 **hardcodejat** (paràgraf 443), no usava la variable Jinja `{{ conclusions_water_statement }}`. Per tant el text generat pel codi no apareixia mai.

### Investigació
- `report_generator.py:1053` sí que assignava `context['conclusions_water_statement']`
- Però `templates/g3dt-jinja-template.docx` paràgraf 443 tenia text estàtic
- Idem per agressivitat (paràgraf 445)

### Solució
1. Substituir paràgraf 443 del template per `{{ conclusions_water_statement }}`
2. Substituir paràgraf 445 del template per `{{ conclusions_aggressivity_statement }}`
3. Actualitzar `WATER_NOT_DETECTED_TEXT` per coincidir amb l'estil G3DT original

### Detall del canvi al text
```
# ABANS (codi):
"Durant l'execució dels treballs de camp no s'ha detectat presència
de nivell freàtic dins la fondària investigada."

# DESPRÉS (alineat amb estil G3DT):
"En data de la realització dels treballs de camp, i fins la cota estudiada,
no es va detectar presència de nivell freàtic en cap dels punts estudiats."
```

### Validació
- Castellar (sloped): text estàndard + **paràgraf de drenatge afegit**
- Bell-Lloc (pla): text estàndard, **sense drenatge**

---

## DESCARTAT: Fusió de nivells (1 vs 2)

### Raonament
L'informe de referència de Castellar mostra 2 nivells (llims + roca). La decisió de si fusionar en 1 nivell o mantenir 2 és **criteri geològic d'Eva**, basat en:
- Potència del nivell superficial (si < 0.5m, pot ser "terra vegetal" i no un nivell real)
- Continuïtat lateral
- Significació per a la fonamentació

L'informe amb 2 nivells és tècnicament correcte. Automatitzar la fusió podria:
- Eliminar informació rellevant
- Contradir el criteri professional del geòleg
- Crear problemes en casos on els 2 nivells sí són significatius

**Decisió:** No automatitzar. Eva decideix cas per cas.

---

## Fitxers modificats

| Fitxer | Canvi | Línies aprox. |
|--------|-------|---------------|
| `automation/report_generator.py:1024` | K30 rock divisor (A) | ~5 |
| `automation/sections/section4_conclusions.py:515` | Ref nivell §4.5 (B) | ~12 |
| `automation/sections/section4_conclusions.py:556` | FS truncat (C) | ~20 |
| `automation/sections/section4_conclusions.py:80` | Water text alineat (D) | ~2 |
| `templates/g3dt-jinja-template.docx:443,445` | Jinja vars water+agressivitat (D) | 2 paràgrafs |

## Resultat de verificació

| Verificació | Resultat |
|-------------|----------|
| Castellar K30 | 8.3 (abans 5.0) ✅ |
| Castellar §4.5 nivell | "2n nivell (Roca fracturada)" ✅ |
| Castellar FS | "FS > 3.5, superiors a 3.5" ✅ |
| Castellar §4.2 drenatge | Text present ✅ |
| Bell-Lloc K30 | 6.9 (no canvia) ✅ |
| Bell-Lloc §4.5 | Absent (no sloped) ✅ |
| Bell-Lloc §4.2 | Text estàndard, sense drenatge ✅ |
