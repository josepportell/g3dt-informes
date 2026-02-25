# /g3dt-adjacents-visor

Agent visual per identificar parcel·les adjacents usant el visor cartogràfic del Cadastre (Playwright).

<command-name>g3dt-adjacents-visor</command-name>

## Arguments

- `project_path` (required): Path a la carpeta del projecte (ex: `reference-material/4001612-bell-lloc`)

## Exemples

```
/g3dt-adjacents-visor reference-material/4001612-bell-lloc
```

## Instruccions

Quan l'usuari invoca aquest skill:

### Fase 1 — Obtenir referència catastral

1. Llegeix `{project_path}/user_data.json`
2. Extreu `referencia_catastral` (ex: `"4613172CG1141S"`)
3. Si no hi és, usa `utm_x`/`utm_y` per consultar l'API de Cadastre:
   - URL: `https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCoordenadas.asmx/Consulta_RCCOOR?SRS=EPSG:25831&Coordenada_X={utm_x}&Coordenada_Y={utm_y}`
   - Extreu la referència catastral de la resposta XML
4. Si cap de les dues funciona: avorta amb error clar

### Fase 2 — Navegar al Cadastre

1. `browser_resize` a 1280×960
2. `browser_navigate` a `https://www1.sedecatastro.gob.es/Cartografia/mapa.aspx?refcat={REFCAT}` (usa els primers 14 caràcters de la refcat)
3. `browser_wait_for` que desaparegui "Cargando" (o esperar 4s)
4. Si apareix diàleg de cookies: clicar "Aceptar" o similar per tancar-lo
5. Ajusta el zoom fins que es vegin clarament els carrers adjacents a tots 4 costats de la parcel·la:
   - **Controls de zoom**: Usar `browser_run_code` per clicar `i.fa-minus` (zoom out) o `i.fa-plus` (zoom in). NO usar mouse wheel — no funciona fiablement en aquest visor.
     ```javascript
     // Zoom out example:
     const btn = page.locator('i.fa-minus').first();
     await btn.click();
     await page.waitForTimeout(1500);
     ```
   - Fes screenshot inicial per avaluar el nivell de zoom
   - **Criteri**: Han de ser visibles els noms dels carrers que envolten la parcel·la
   - Si no es veuen carrers o noms → zoom out (clicar `i.fa-minus`, esperar 1.5s per tiles)
   - Si la parcel·la és massa petita per identificar-la → zoom in (clicar `i.fa-plus`, esperar 1.5s)
   - Repetir fins que el nivell sigui adequat
   - **Referència**: El visor obre a escala ~2m. Per parcel·les de ~600m² calen ~6 clics de zoom out (fins ~20m). Parcel·les més grans en necessitaran més.
   - Es poden fer múltiples clics en un sol `browser_run_code` amb un loop.
6. `browser_take_screenshot` → guardar a `{project_path}/validation/adjacents_visor_screenshot.png`

### Fase 3 — Anàlisi visual

Analitza el screenshot i identifica:

- **La parcel·la objectiu**: Contorn blau discontinu, amb número de parcel·la
- Per cada costat (N=dalt, S=baix, E=dreta, O=esquerra):
  - **Carrer**: Franja blanca/gris amb text del nom → extreure nom
  - **Parcel·la veïna**: Altra parcel·la compartint mitgera → "parcel·la veïna"

**Regles d'extracció:**
- Si el nom és en castellà, traduir: CALLE→Carrer, AVENIDA→Avinguda, PLAZA→Plaça, PASEO→Passeig, CAMINO→Camí, TRAVESÍA→Travessia, RONDA→Ronda, PARTIDA→Partida
- Normalitzar a title case: "CARRER MESTRE RAMON ORTIZ" → "Carrer Mestre Ramon Ortiz"
- Si hi ha carrer I parcel·la més enllà → reportar el carrer (adjacent immediat)
- Si no es pot llegir clarament → marcar confiança baixa (0.5-0.7)

### Fase 4 — Generar JSON

Assegura't que existeix el directori `{project_path}/validation/`.
Guardar a `{project_path}/validation/adjacents_visor.json`:

```json
{
  "source": "cadastre_visor",
  "refcat": "4613172CG1141S",
  "extraction_date": "2026-02-06T12:00:00",
  "extraction_method": "claude_vision_playwright",
  "overall_confidence": 0.90,
  "status": "pending_review",
  "adjacents": {
    "north": "parcel·la veïna",
    "south": "Carrer Antoni Bellet",
    "east": "Carrer Mestre Ramon Ortiz",
    "west": "parcel·la veïna"
  },
  "confidence": {
    "north": 0.95,
    "south": 0.90,
    "east": 0.95,
    "west": 0.90
  },
  "notes": {
    "north": "Parcel·la 71, SUELO, mitgera directa",
    "south": "Carrer visible E-O sota la parcel·la",
    "east": "MESTRE RAMON ORTIZ visible en vertical",
    "west": "Parcel·la 74 amb edificis, mitgera directa"
  },
  "screenshot_file": "adjacents_visor_screenshot.png"
}
```

**Notes sobre el JSON:**
- `extraction_date`: usar data/hora actual ISO 8601
- `overall_confidence`: mitjana ponderada de les confiançes individuals
- `status`: sempre "pending_review" fins que l'usuari confirmi
- Valors de `adjacents`: text descriptiu en català
- `screenshot_file`: nom relatiu del screenshot (no path absolut)

### Fase 5 — Resum i confirmació

Mostra el resum en format clar:

```
============================================================
Adjacents Visor: {REFCAT} ({municipi})
============================================================
Nord:  {adjacents.north} (conf: {confidence.north}) - {notes.north}
Sud:   {adjacents.south} (conf: {confidence.south}) - {notes.south}
Est:   {adjacents.east} (conf: {confidence.east}) - {notes.east}
Oest:  {adjacents.west} (conf: {confidence.west}) - {notes.west}

JSON: {project_path}/validation/adjacents_visor.json
Screenshot: {project_path}/validation/adjacents_visor_screenshot.png

Vols actualitzar user_data.json amb aquests adjacents? (només camps buits)
```

### Fase 6 — Actualitzar user_data.json

Si l'usuari confirma:
1. Llegir `{project_path}/user_data.json`
2. Només actualitzar camps d'adjacents buits (on el valor sigui `""`, `null`, o tingui `source: "default"`)
3. Mapeig de camps:
   - `adjacents.north` → `adjacent_north`
   - `adjacents.south` → `adjacent_south`
   - `adjacents.east` → `adjacent_east`
   - `adjacents.west` → `adjacent_west`
4. Actualitzar `_metadata.field_sources` per cada camp actualitzat → `"cadastre_visor"`
5. Guardar el JSON amb format `indent=2`

## Confiança d'extracció

Assigna nivells de confiança segons la claredat visual:
- **0.95-1.0**: Text clar i inequívoc al mapa, nom complet visible
- **0.85-0.95**: Text llegible amb mínima incertesa
- **0.70-0.85**: Text parcialment visible o tallat, requereix interpretació
- **0.50-0.70**: Difícil de llegir, podria estar mal interpretat
- **< 0.50**: No es pot determinar - posar `"no determinat"` com a valor

## Notes Importants

- **Zoom**: Usar `i.fa-minus` / `i.fa-plus` via `browser_run_code`. El mouse wheel NO funciona fiablement al visor del Cadastre (OpenLayers).
- **Botó fullscreen**: El botó `ol-full-screen-false` (ref e44 al snapshot) NO és zoom out — és pantalla completa. No usar-lo per fer zoom.
- El visor del Cadastre pot trigar a carregar els tiles. Si la captura mostra àrees en blanc, espera més temps (1.5-2s entre clics de zoom).
- Si el mapa no centra bé la parcel·la, prova a navegar manualment amb les eines del visor.
- La URL usa els primers 14 caràcters de la refcat (sense lletra de control) per a la cerca.
- Si la captura no és prou clara, fes zoom in en comptes de zoom out i pren múltiples captures.
- Els noms de carrer al Cadastre solen estar en castellà — traduir sempre al català.
- Els noms de carrer al visor poden aparèixer partits en diverses línies (ex: "D'ANTONI" + "BELLET" + "PÉREZ" repartits per la franja del carrer). Cal reconstruir el nom complet.
