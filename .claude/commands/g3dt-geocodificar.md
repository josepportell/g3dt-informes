# /g3dt-geocodificar

Geocodifica l'adreça d'un projecte per obtenir coordenades UTM aproximades quan no hi ha COORDENADES.txt (sense GPS de camp).

<command-name>g3dt-geocodificar</command-name>

> El path del projecte depèn de `G3DT_PROJECTS_DIR` (default: `reference-material/`).

## Arguments

- `project_path` (required): Path a la carpeta del projecte (ex: `reference-material/4001612 BELL-LLOC` o `/mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC`)

## Exemples

```
/g3dt-geocodificar reference-material/4001612 BELL-LLOC
/g3dt-geocodificar reference-material/4001607 LINYOLA
```

## Instruccions

Quan l'usuari invoca aquest skill:

1. **Verifica prerequisits**:
   - Comprova si ja existeix `ANNEXES/ALTRES/COORDENADES.txt` al projecte
   - Si existeix, mostra les coordenades actuals i pregunta si vol re-geocodificar
   - Busca `user_data.json` per `street_address` o `site_address`
   - Si no hi ha adreça, demana-la a l'usuari

2. **Executa la geocodificació**:
   ```python
   import logging
   logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

   from automation.geocode_coordinates import geocode_project
   from automation.auto_extractor import _extract_municipality
   from pathlib import Path

   project_path = Path("$ARGUMENTS")
   municipality = _extract_municipality(project_path)

   # Obtenir point_ids del DPSH si disponible
   point_ids = ['P-1']
   try:
       from automation.dpsh_extractor import DPSHExtractor
       # Buscar DPSH Excel
       for p in project_path.glob('ANNEXES/*DPSH*.xls'):
           ext = DPSHExtractor(str(p))
           data = ext.extract_all()
           if data and data.test_ids:
               point_ids = data.test_ids
           break
   except Exception:
       pass

   result = geocode_project(address, municipality, point_ids, output_dir=None)
   ```

3. **Mostra resultats** en format taula:

   ```
   ============================================================
   Geocodificació: {project_name}
   ============================================================
   Adreça:     {address}
   Municipi:   {municipality}

   Coordenades UTM (EPSG:25831):
     Centroide:  ({utm_x:.1f}, {utm_y:.1f})
     Ref. cadastral: {rc}

   Punts d'assaig:
     P-1: ({x:.1f}, {y:.1f}, z={z:.1f})
     P-2: ({x:.1f}, {y:.1f}, z={z:.1f})
     S-1: ({x:.1f}, {y:.1f}, z={z:.1f})

   Font: {source}
   ============================================================
   ```

4. **Si existeix COORDENADES.txt amb GPS**, compara:

   ```
   Comparació GPS vs Geocodificat:
     GPS centroide:    (314508.67, 4611192.86)
     Geocodificat:     (314507.8, 4611179.1)
     Diferència:       dX=0.9m, dY=13.8m (total: 13.8m)
   ```

5. **Pregunta a l'usuari** si vol:
   - Guardar el COORDENADES.txt generat (si no n'existeix un)
   - Actualitzar `user_data.json` amb les coordenades UTM
   - No fer res (només informatiu)

## Notes

- **Precisió**: La geocodificació per adreça té una precisió de ~50-200m (dependent de Nominatim + Cadastre).
- **No substitueix GPS**: Les coordenades són aproximades. Per a projectes definitius, cal GPS de camp.
- **Requereix xarxa**: Fa peticions a Nominatim (OSM), Cadastre (OVC) i ICGC (MDT).
- **Cache**: Els resultats es guarden a `~/.g3dt/cache/geocode/` durant 90 dies.
- **Fase 2.5**: Quan s'executa `auto_extract()` sense COORDENADES.txt, la geocodificació es fa automàticament si hi ha adreça disponible.
