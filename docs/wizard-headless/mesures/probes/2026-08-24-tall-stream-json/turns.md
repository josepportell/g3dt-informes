# Sonda de turns — `tall.pdf` (Castellar), `claude -p … --output-format stream-json --verbose`, 2026-08-24 23:03-23:08

Resultat del CLI: **20 turns · 293 s d'API · 25.812 tokens de sortida** · cost equiv. $1,09. Sortida `tall.json` idèntica en estructura a la del run 2.
Stream cru (2,7 MB, amb imatges) a `~/g3dt-e2e/fase9/probe-tall/stream.jsonl` (fora del repo).

**Del que el model escriu visible** (9 Bash + 5 Read + 1 Write ≈ 15,5k caràcters ≈ 5k tokens + 2k caràcters de text) als 25,8k tokens de sortida
hi ha ~19k tokens (≈ 75 %) que no apareixen al stream: **raonament (thinking)**. La generació — no el context — és el temps.

| # | eina | què fa | classe |
|--:|---|---|---|
| 1 | Bash | `ls` de la carpeta del projecte + `find tall.pdf` | orientació (redundant amb l'inventari) |
| 2 | Read | `_inventory.json` (17 KB) | context creuat (Pas 0) — necessari |
| 3 | Bash | `fitz`: comptar pàgines, mida | **construir-se l'eina** |
| 4 | Bash | `fitz`: extreure text de la pàgina | **construir-se l'eina** |
| 5 | Bash | `fitz`: renderitzar pàgina sencera a PNG | **construir-se l'eina** |
| 6 | Read | PNG pàgina sencera | lectura visual — necessària |
| 7 | Bash | `fitz`: renderitzar meitat esquerra/dreta | **construir-se l'eina** |
| 8-9 | Read | PNG meitats | lectura visual — necessària |
| 10 | Bash | `fitz`: retall localitzador | **construir-se l'eina** |
| 11 | Read | PNG localitzador | lectura visual — necessària |
| 12 | Bash | `md5sum tall.pdf` | redundant (l'inventari porta el md5) |
| 13 | Write | payload JSON (11,5 KB) a un temporal | sortida |
| 14 | Bash | python: `os.replace` atòmic al nom canònic | **cerimònia d'escriptura** |
| 15 | Bash | python: rellegir i verificar el JSON | **cerimònia d'escriptura** |

**Lectura:** de 15 usos d'eina, **5 són construir-se l'eina** (3, 4, 5, 7, 10), **2 redundants** (1, 12) i **2 de cerimònia** (14, 15). Només 6
(2, 6, 8, 9, 11, 13) són llegir i escriure. Una pre-extracció determinista (per cada document de l'inventari: text per pàgina, PNG de pàgina
sencera i meitats a 100-150 dpi; Excel → CSV per full; .msg → cos + adjunts) més un `scripts/write_doc_json.py` (payload per stdin →
validació + escriptura atòmica al nom canònic) deixaria el document en ~7-8 usos d'eina **mirant exactament les mateixes imatges i el mateix
text**. El raonament per turn també baixa perquè hi ha menys turns. Estimació: −35-45 % de temps per document. A mesurar com a fila del llibre.
