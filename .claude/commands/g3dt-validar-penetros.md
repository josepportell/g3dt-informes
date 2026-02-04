# /g3dt-validar-penetros

Extreu i valida dades DPSH de fulls de camp escanejats (PENETROS.pdf) comparant amb l'Excel existent.

<command-name>g3dt-validar-penetros</command-name>

## Arguments

- `pdf_path` (required): Path al fitxer PENETROS.pdf
- `excel_path` (optional): Path al fitxer DPSH.xls. Si no s'especifica, es busca a ANNEXES/{expedient}_DPSH.xls

## Exemples

```
/g3dt-validar-penetros reference-material/4001612-bell-lloc/PENETROS.pdf
/g3dt-validar-penetros reference-material/4001612-bell-lloc/PENETROS.pdf reference-material/4001612-bell-lloc/ANNEXES/4001612_DPSH.xls
```

## Instruccions

Quan l'usuari invoca aquest skill:

1. **Llegeix el PDF visualment** amb el Read tool
2. **Extreu les dades** de cada assaig (P-1, P-2, etc.):
   - Profunditat (columna esquerra)
   - Valors N20 (cops per 20cm)
   - Marcadors de refús (R)
   - Indicadors de nivell freàtic (N.F.)
3. **Carrega les dades Excel** per comparar
4. **Compara valor per valor** i identifica discrepàncies
5. **Genera JSON de validació** amb el format correcte
6. **Guarda el fitxer** a `{pdf_parent}/validation/dpsh_extracted.json`

## Format d'extracció del PDF

Quan llegeixis el PENETROS.pdf, busca:

### Pàgina de dades (Full de Camp Penetròmetre Dinàmic)
- **Capçalera**: Data, Adreça de l'obra
- **Columnes d'assaig**: P1, P2, etc. amb profunditats i valors N20
- **Profunditats**: -0.2, -0.4, -0.6, ... fins a refús o final
- **Valors N20**: Números escrits a mà a cada profunditat
- **Refús**: Marcat amb "R" i profunditat (ex: "R 1,35")
- **Nivell freàtic**: Marcat a la secció "NIVELL FREÀTIC"

### Format de sortida JSON

```json
{
  "source_file": "PENETROS.pdf",
  "extraction_date": "2026-02-04T14:30:00",
  "extraction_method": "claude_vision",
  "overall_confidence": 0.95,
  "status": "pending_review",
  "excel_comparison": {
    "has_excel": true,
    "excel_file": "4001612_DPSH.xls",
    "total_values": 18,
    "matches": 18,
    "discrepancies": 0
  },
  "dpsh_tests": [
    {
      "test_id": "P-1",
      "readings": [
        {
          "depth_m": 0.4,
          "n20": 20,
          "confidence": 1.0,
          "excel_value": 20,
          "has_discrepancy": false,
          "note": null
        }
      ],
      "refusal_depth_m": 1.35,
      "refusal_detected": true,
      "water_detected": false,
      "correction_factor": 0.83
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
- **0.7-0.8**: Llegible però amb possibles alternatives (ex: "7 o 1?")
- **0.5**: Difícil de llegir, interpretació necessària
- **0.0**: Il·legible - usa "??" com a valor

## Comparació amb Excel

Per cada valor:
1. Compara el teu valor extret amb l'Excel
2. Si coincideixen: `has_discrepancy: false`
3. Si difereixen: `has_discrepancy: true` i afegeix nota explicativa
4. Si és il·legible ("??"): `has_discrepancy: true`

## Després de l'extracció

1. Mostra resum: total valors, coincidències, discrepàncies
2. Llista les discrepàncies trobades amb detall
3. Indica el path del fitxer JSON generat
4. Recorda a l'usuari que pot revisar amb `templates/validation/review.html`

## Exemple de sortida

```
============================================================
Extracció DPSH: PENETROS.pdf (Bell-Lloc)
============================================================
Data del full: 1-10-25
Ubicació: Carrer Antoni Bellet

Assaigs detectats: P-1, P-2

P-1 (refús a 1.35m):
  0.4m: 20 ✓
  0.6m: 27 ✓
  0.8m: 16 ✓
  ...

P-2 (refús a 2.45m):
  0.4m: 17 ✓
  ...

Comparació amb Excel (4001612_DPSH.xls):
  Total valors: 18
  Coincidències: 18 ✓
  Discrepàncies: 0

Validació guardada a: reference-material/4001612-bell-lloc/validation/dpsh_extracted.json

Per revisar: obre templates/validation/review.html i carrega el JSON
```
