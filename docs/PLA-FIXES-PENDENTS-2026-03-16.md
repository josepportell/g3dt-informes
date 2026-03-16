# Pla de Fixes Pendents — 2026-03-16

## Fix A: Cota referencia no agafa elevation_z del sondeig

**Símptoma:** Wizard mostra `+199.00` (ICGC MDT) en lloc de `+199.50` (sondeig camp).

**Causa:** `wizard_service.py` cerca `elevation_z` a `metadata` i `sondeig_tests[0]`, però la visió pot posar-ho amb claus diferents. El fix anterior només afegeix un path, però hi ha més variants possibles.

**Fix:** Llistar TOTES les claus possibles on `elevation_z` pot aparèixer al JSON del sondeig (vision no-determinista), i buscar-les totes. Revisar el `vision_normalizer.py` — potser hauria de normalitzar `elevation_z` a un lloc canònic.

**Fitxers:** `web/wizard_service.py` (2 llocs), `automation/vision_normalizer.py`

**Prioritat:** Alta — afecta Taula 3 i Taula 4 del informe.

---

## Fix B: Noms de carrer bruts (municipi dins el nom)

**Símptoma:** "Carrer Antoni Bellet i Perez Bell-Lloc d'Urgell" en lloc de "Carrer Antoni Bellet i Perez".

**Causa:** `_translate_street_name()` rep `municipality` del nom de carpeta ("Bell-Lloc") que no coincideix amb el LDT ("BELL-LLOC D'URGELL"). El fix de `site_municipality` des de `existing_user_data` no funciona al primer run (no hi ha `user_data.json`).

**Fix:** Al `report_generator.py`, netejar els noms de carrers adjacents eliminant el municipi (`report_data.municipality`) abans de posar-los al context de la plantilla. Això és un cleanup downstream fiable que no depèn del primer/segon run.

**Fitxers:** `automation/report_generator.py`

**Prioritat:** Alta — afecta la frase de ubicació i la secció 2.1.1.

---

## Fix C: Frase de ubicació (P66) — variables confuses i gramàtica

**Símptoma:** `"es situarà entre el Carrer X i el Carrer Y Bell-Lloc d'Urgell de Bell-Lloc d'Urgell."`

**Plantilla docx actual:**
```
entre el {{ street_1 }}{% if adjacent_south_street %} i el {{ adjacent_south_street }}{% endif %} de {{ street_2 }}.
```

**Problemes:**
1. `street_2` conté el municipi, però es diu "street" → confús
2. `adjacent_south_street` NO és "south" — el codi ja busca en TOTES les direccions (sud→est→oest→nord), el nom és legacy
3. Carrers no netejats (Fix B)
4. Cas d'un sol carrer: "entre el Carrer X de Z" → gramaticalment incorrecte ("entre" necessita dos elements)

**Fix:**
1. Renombrar variables internes (no les claus del template — el docx les usa):
   - `street_2` → poblar des de `municipality` directament (ja fet)
   - `adjacent_south_street` → afegir comentari que busca en totes les direccions
2. Netejar `adjacent_south_street` eliminant el municipi (Fix B)
3. Cas d'un sol carrer: canviar la plantilla docx per usar una sola variable `{{ location_sentence }}` construïda en Python amb gramàtica correcta:
   - 2 carrers: "entre el Carrer X i el Carrer Y de Municipi"
   - 1 carrer: "al Carrer X de Municipi"
   - 0 carrers: "al terme municipal de Municipi"

**Fitxers:** `automation/report_generator.py`, `automation/parametrize_template.py`, `templates/g3dt-jinja-template.docx` (re-parametritzar)

**Prioritat:** Mitjana — funciona prou bé per a parcel·les cantoneres (2 carrers).

---

## Ordre recomanat

```
Fix A (Cota)        → Ràpid, impacte alt, independent
    ↓
Fix B (Noms bruts)  → Ràpid, necessari per Fix C
    ↓
Fix C (Frase P66)   → Més complex, depèn de Fix B
```
