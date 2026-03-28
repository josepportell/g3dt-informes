# Pla de Millores del Geocoding per Adjacents

Data: 2026-03-27
Estat: EN IMPLEMENTACIÓ

## Context

El pipeline d'adjacents funciona bé per projectes amb COORDENADES.txt (GPS de camp),
però falla per projectes que depenen de geocodificació d'adreces (Alcoletge, Vilanova, Anciles).

**Cas de referència — Alcoletge:**
- Groq extreu `client_address='Carrer Girasols nº7'` (correcte)
- Visió Claude extreu `street_address='Carrer Girassols #7'` (doble 's' — error OCR)
- Cadastre ConsultaVia no troba "Girassols" (no té tolerància a typos)
- Nominatim tampoc troba "Girassols" en un poble petit
- Resultat: 0 adjacents, Eva ha d'omplir manualment

## Principi Arquitectural Clau

**Totes les millores són FALLBACK-ONLY.** Només s'executen quan el camí actual ja ha fallat.
Per projectes que ja funcionen (Bell-Lloc, Castellar, Rubí, Linyola), el codi nou MAI s'executa.

## Etapes d'Implementació

### Etapa 1: SEGURA (risc zero de regressió i fals positiu)

**P1b — Nominatim structured query**
- Fitxer: `automation/geocode_coordinates.py`
- Canvi: Afegir `nominatim_geocode_structured()` que usa paràmetres separats
  (`street=`, `city=`, `state=`, `country=`) en lloc de free-text `?q=`
- Integració: Cridar ABANS del `nominatim_geocode()` existent en `geocode_project()`
- Risc: ZERO — additive, si falla es passa al free-text existent

**P1 — Afegir client_address com a últim candidat**
- Fitxers: `automation/auto_extractor.py`, `web/wizard_service.py`
- Canvi: Afegir `client_address` a `address_candidates` en ÚLTIMA posició
- Filtre: Només si conté un dígit AND longitud > 10 (evita "LLEIDA" com a adreça)
- Risc: ZERO — només es prova si street_address i site_address ja han fallat

### Etapa 2: SEGURA amb logging clar

**P0 — Levenshtein fallback a ConsultaVia**
- Fitxer: `automation/geocode_coordinates.py`
- Canvi: Quan `_consulta_via()` falla amb tots els hints progressius:
  1. Cridar ConsultaVia amb NombreVia buit → obtenir TOTES les vies del municipi
  2. Usar `difflib.get_close_matches()` amb cutoff=0.8
  3. Si hi ha match, usar-lo per al DNPLOC
- Log: `"Progressive cadastre: fuzzy match 'Girassols' → 'GIRASOLS' (ratio=0.94)"`
- Risc: ZERO regressió. Baix fals positiu (cutoff 0.8 és conservador)
- Nota: Per municipis grans (>500 vies), saltar fuzzy per evitar XML enorme

### Etapa 2b: LLM Street Picker (Layer 3) — AFEGIT 2026-03-27

**Motivació:** difflib + article stripping cobreixen molts casos, però cada cas nou
requereix noves regles (articles, abreviatures, urbanitzacions, partides...).
Eva no funciona així — ella mira la llista i entén semànticament quin és el correcte.

**Implementació:** `_llm_pick_street()` a `geocode_coordinates.py`
- S'activa NOMÉS quan difflib (Fase 1 + Fase 2) ha fallat
- Envia el hint + llista de vies del municipi a Groq (qwen3-32b)
- Prompt de closed-choice: el LLM HA de triar de la llista o dir "NONE"
- Validació estricta: la resposta es compara contra la llista real
- Si no coincideix → rebutjat (no pot al·lucinar un carrer inexistent)
- Context extra: full_address_context ("Urbanització El Roser") ajuda el LLM
- Cost: ~$0.001 per crida, ~0.5-1.5s, només quan cal
- Log: `"LLM street picker: 'Girassols' → 'DELS GIRASOLS' (CL) in ALCOLETGE"`

**Resultat real (Alcoletge):**
- difflib no podia: "GIRASSOLS" vs "DELS GIRASOLS" = 0.73 (sota cutoff)
- LLM: entén que "Girassols" = "DELS GIRASOLS" → match correcte

**Risc:** ZERO regressió (fallback de fallback de fallback). El LLM no pot inventar
carrers perquè la resposta es valida contra la llista real del Cadastre.

### Etapa 3: Amb guardrails

**P3 — Cerca cross-province (només províncies veïnes)**
- Fitxer: `automation/geocode_coordinates.py`
- Canvi: Si ConsultaMunicipio falla per la província especificada, provar veïnes
- Mapa de veïnatge:
  - LLEIDA → [HUESCA, BARCELONA, TARRAGONA]
  - BARCELONA → [LLEIDA, GIRONA, TARRAGONA]
  - GIRONA → [BARCELONA]
  - TARRAGONA → [LLEIDA, BARCELONA]
  - HUESCA → [LLEIDA]
- Log: `"Progressive cadastre: cross-province 'Anciles' found in HUESCA (was LLEIDA)"`
- Risc: ZERO regressió. Mig fals positiu per municipis amb nom genèric (mitigat per limitar a veïnes)

### P0b — Fuzzy word-level match (articles Cadastre) — AFEGIT 2026-03-27

**Descobert durant testing real amb Alcoletge:**
El Cadastre registra `"DELS GIRASOLS"`, no `"GIRASOLS"`. El Levenshtein de P0
compara cadenes completes: `"GIRASSOLS"` vs `"DELS GIRASOLS"` = ratio 0.73 (sota 0.8).

**Solució:** Fase 2 dins el fuzzy: si la Fase 1 (full-string) falla, treure articles
comuns (DE, DEL, DELS, DE LA, EL, LA, etc.) dels noms de via multi-paraula i
comparar la part significant contra el hint. `"GIRASSOLS"` vs `"GIRASOLS"` = 0.94.

**Risc:** Molt baix — només actua en noms multi-paraula amb article, i el cutoff 0.8
segueix actiu. ZERO regressió (fallback de fallback).

### DESCARTADA: P2 — Normalització ortogràfica

- Redundant amb P0+P0b (Levenshtein + word-level ja cobreix ss↔s, rr↔r, articles)
- P0 compara contra la llista REAL de vies, P2 generaria variants a cegues
- Més risc de fals positius sense benefici addicional

## Salvaguarda Transversal: Source Logging

Per qualsevol match no-exacte, el badge de font al wizard mostra el camí:
- `"Cadastre (fuzzy: Girassols → GIRASOLS)"`
- `"Nominatim structured"`
- `"Cadastre cross-province: HUESCA"`

Això permet a Eva verificar quan l'adreça s'ha resolt via un camí no-exacte.

## Matriu de Risc

| Millora | Trenca existent? | Risc fals positiu | Pitjor cas |
|---------|------------------|--------------------|------------|
| P1b: Nominatim structured | ZERO | ZERO | Falla → cau al free-text |
| P1: client_address | ZERO (últim) | BAIX-MIG | Adreça parcial geocodifica al centre ciutat |
| P0: Levenshtein | ZERO | BAIX | Carrer similar-però-diferent al mateix municipi |
| P3: Cross-province | ZERO | MIG | "Vilanova" al província equivocada |

## Impacte Esperat

- Projectes amb GPS (4/7): sense canvi (ja funcionen)
- Projectes sense GPS (3/7): de ~0% èxit a ~90%+ èxit
- Cas Alcoletge: P0 sol ja el resol (Girassols→Girasols, ratio 0.94)
