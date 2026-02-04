# /g3dt-validar-sondeig

Extreu dades de sondeigs a rotació de fulls de camp escanejats (SONDEIG.pdf).

<command-name>g3dt-validar-sondeig</command-name>

## Arguments

- `pdf_path` (required): Path al fitxer SONDEIG.pdf

## Exemples

```
/g3dt-validar-sondeig reference-material/4001612-bell-lloc/SONDEIG.pdf
```

## Instruccions

Quan l'usuari invoca aquest skill:

1. **Llegeix el PDF visualment** amb el Read tool
2. **Extreu les dades** de cada sondeig (S-1, S-2, etc.):
   - Profunditats de les capes
   - Descripcions del sòl (tipus de material)
   - Resultats SPT si n'hi ha (N1, N2, N3, Ntotal)
   - Nivell freàtic si es detecta
   - Profunditat de roca si es detecta
3. **Genera JSON de validació** amb el format correcte
4. **Guarda el fitxer** a `{pdf_parent}/validation/sondeig_extracted.json`

## Format d'extracció del PDF

Quan llegeixis el SONDEIG.pdf, busca:

### Full de Camp Sondeig a Rotació
- **Capçalera**: Data, Adreça, Operari, Equip, Client
- **Columna Profunditat**: De/A (metres)
- **Columna Descripció**: Tipus de sòl (escrit a mà)
- **Columna SPT** (si n'hi ha): N1, N2, N3, Ntotal
- **Nivell freàtic**: Si s'indica amb N.F. o símbol d'aigua
- **Roca**: Si s'indica amb símbol o nota

### Format de sortida JSON

```json
{
  "source_file": "SONDEIG.pdf",
  "extraction_date": "2026-02-04T15:30:00",
  "extraction_method": "claude_vision",
  "overall_confidence": 0.92,
  "status": "pending_review",
  "metadata": {
    "date": "6-10-2025",
    "location": "Bell-Lloc",
    "address": "C/Antoni Bellet",
    "operator": "Daniel Fernández",
    "equipment": "ML76A",
    "client": "G3",
    "responsible": "Eva"
  },
  "sondeig_tests": [
    {
      "test_id": "S-1",
      "total_depth_m": 1.80,
      "layers": [
        {
          "depth_from_m": 0.0,
          "depth_to_m": 1.0,
          "description": "Grava con arenas",
          "confidence": 0.95,
          "note": null
        },
        {
          "depth_from_m": 1.0,
          "depth_to_m": 1.80,
          "description": "Grava cementada",
          "confidence": 0.85,
          "note": "handwriting slightly unclear"
        }
      ],
      "spt_results": [
        {
          "depth_m": 1.0,
          "n1": 24,
          "n2": 34,
          "n3": 28,
          "n_total": 30,
          "confidence": 0.90,
          "note": "SPT-1"
        }
      ],
      "water_level_m": null,
      "rock_depth_m": null,
      "extraction_notes": "Single drilling test, clear field sheet"
    }
  ],
  "reviewer_notes": "",
  "approved_by": "",
  "approval_date": null
}
```

## Confiança d'extracció

Assigna nivells de confiança segons la llegibilitat:
- **1.0**: Valor clar i inequívoc
- **0.9**: Llegible amb mínima incertesa
- **0.7-0.8**: Llegible però amb possibles alternatives
- **0.5**: Difícil de llegir, interpretació necessària
- **0.0**: Il·legible - indica "??" i afegeix nota

## Nota Important

A diferència de DPSH, **no hi ha Excel de comparació** per als sondeigs.
Tots els valors s'extreuen visualment del PDF i es marquen per revisió humana.
La confiança és especialment important aquí.

## Després de l'extracció

1. Mostra resum: sondeigs trobats, capes per sondeig, SPTs
2. Destaca valors amb baixa confiança (< 0.9)
3. Indica el path del fitxer JSON generat
4. Recorda a l'usuari que pot revisar amb `templates/validation/review.html` (pestanya Sondeig)

## Exemple de sortida

```
============================================================
Extracció Sondeig: SONDEIG.pdf (Bell-Lloc)
============================================================
Data del full: 6-10-25
Ubicació: C/Antoni Bellet
Operari: Daniel Fernández

Sondeigs detectats: S-1

S-1 (profunditat total: 1.80m):
  Capes:
    0.00-1.00m: Grava con arenas (conf: 0.95)
    1.00-1.80m: Grava cementada (conf: 0.85) ⚠️
  SPT:
    1.0m: 24|34|28 = 30 (conf: 0.90)
  Nivell freàtic: No detectat
  Roca: No detectada

⚠️ Valors amb baixa confiança que requereixen revisió:
  - S-1 capa 1.00-1.80m: "Grava cementada" (0.85)

Validació guardada a: reference-material/4001612-bell-lloc/validation/sondeig_extracted.json

Per revisar: obre templates/validation/review.html i carrega el JSON (pestanya Sondeig)
```
