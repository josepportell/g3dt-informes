# Pla D1#1 — pre-Stage 4 logo filter per perceptual hash

**Data:** 2026-04-25
**Branca:** `experiment/ai-pipeline`
**Referència:** `docs/AI-PIPELINE-DEFERRED.md` entrada D1 · `docs/ARQUITECTURA-AI-PIPELINE.md` §5.6

---

## 1. Motivació

L'extracció d'imatges de la Fase 2 produeix molts logos i banners corporatius
(G3DT, "25 anys", signatures) incrustats dins de PDFs, Excels i DOCXs. Encara
que D1#2 ja els ha regroupat sota el document pare (un sol LLM call per font),
aquestes imatges continuen consumint tokens del vision budget i ocupen espai
dels 16 image slots màxims per font. Exemples concrets a Alcoletge:

- `PRESSUPOST_GEOTEC.ALCOLETGE` extreu 5 imatges, **totes G3 logo**.
- `4001670_generated_*/img_008.jpeg` — logo circular G3 medium size.
- `RE_ .../image001.jpg`, `image008.jpg`, `image012.png` — signatures d'email.

Volem descartar-les **abans** que arribin a l'artefacte de Fase 3, sense cridar
l'LLM: marcar `useful=False` a Fase 2 és el punt més alt on això és possible
perquè la cadena `source_chain` i el `parent_path` ja hi són.

---

## 2. Alternatives considerades

| Tècnica | Cost per imatge | Determinista | Dep. nova |
|---------|-----------------|--------------|-----------|
| **Perceptual hash (pHash)** | 0 (CPU local) | Sí | `imagehash` |
| Cheap vision LLM (`gpt-4.1-mini`) | ~$0.0006 | No | cap (`openai` ja hi és) |
| Sonnet amb `is_logo?` tool | ~$0.005 | No | cap |
| Mida/dimensions heuristic | 0 | Sí | cap |

pHash guanya per: sense cost, deterministic per tests, i la biblioteca
`imagehash` és petita (pip install pesa ~200 KB, més `scipy` ja present a
sistema). La visió cheap és una opció de back-off per casos ambigus a v1.1 si
pHash no basta.

Mida/dimensions heuristic no basta perquè els logos G3 apareixen en mides molt
variades (32×32 fins a 512×512 com a watermark).

---

## 3. Experiment manual (2026-04-25)

Abans d'implementar, hem validat pHash sobre els 51 imatges extretes del
projecte Alcoletge (`validation/ai_pipeline/extracted/` +
`validation/msg_attachments/`). Dos passos:

### Pass 1 — 2 references (G3-tight, 25anys-banner)
Objectiu: trobar un threshold Hamming que separi logos de contingut.

Resultat: logos idèntics a ≤6, mateix logo escalat a 14–16, i una zona
ambigua 20–24 on hi havia barreja (G3 logos amb padding diferent + un parell
d'imatges composite amb logo a la cantonada).

### Pass 2 — 4 references, threshold Hamming ≤ 6
References seleccionades per cobrir les 4 variants visuals observades:

1. **G3-tight** — crop cenyit del logo circular (33×33 px típic).
2. **G3-large-circle** — mateix logo amb padding generós.
3. **G3-watermark** — G3 emprat com a watermark de fons (tonalitat clara).
4. **25anys-banner** — banner "25 anys / Compromesos amb el teu projecte".

Distàncies entre references (sanity): 16, 24, 26, 30, 30, 32 — prou
distintes perquè el threshold ≤ 6 no generi falsos positius mutus.

### Dades del Pass 2

| Bucket Hamming | Comptes | Tipus |
|----------------|---------|-------|
| 0–6 (flagged) | **11** | ✅ Tots verificats visualment com a logos |
| 7–21 | **0** | (buit — decisió cristall·lina) |
| 22+ | **46** | Contingut: plànols, albarans DPSH, fotos, mapes |

Imatges flagged (amb la reference més propera):

| Hamming | Reference | Fitxer |
|---------|-----------|--------|
| 0 | G3-tight | `mined_images/PLAN_COST_ALCOLETGE_img0.png` |
| 0 | G3-large-circle | `geotècnic.../image001.jpg` |
| 2 | 25anys-banner | `RE_ .../image012.png` |
| 2 | 25anys-banner | `geotècnic.../image005.png` |
| 4 | G3-tight | `4001670_generated_1/img_008.jpeg` |
| 4 | G3-tight | `4001670_generated_utms/img_008.jpeg` |
| 4 | G3-tight | `PRESSUPOST/img_002.jpeg` |
| 4 | G3-tight | `PRESSUPOST/img_003.jpeg` |
| 6 | G3-large-circle | `PRESSUPOST/img_001.jpeg` |
| 6 | G3-large-circle | `PRESSUPOST/img_004.jpeg` |
| 6 | G3-large-circle | `tall/img_000.jpeg` |

### Casos de risc verificats com a contingut (no flagged)

- `4001670_generated_1/img_011.jpg` (Hamming 22) — mapa + satèl·lit amb un
  petit G3 a la cantonada inferior. **Contingut dominant**, correctament
  conservat.
- `PRESSUPOST_GEOTEC.ALCOLETGE_SIGNAT-SCAN/img_001.jpeg` (Hamming 24) —
  pàgina de pressupost amb logo a la cantonada i text real del proposal.
  Contingut, conservat.
- `PENETROS/img_000.jpeg` (Hamming 22) — fitxa d'albarà TPS amb dades de
  camp (adreça, dates, tipus d'assaig). Contingut, conservat.

---

## 4. Disseny de la implementació

### 4.1 Biblioteca de references

Ubicació: `schemas/ai_pipeline/logo_references/`. Cada imatge és una còpia
de la variant seleccionada; README descriu l'origen. Els fitxers són petits
(~15 KB totals) i es commit al repo.

Estructura:
```
schemas/ai_pipeline/logo_references/
├── README.md
├── g3_tight.png              # 33×33 circular G3, tight crop
├── g3_large_circle.jpg       # ~180×180 circular G3 amb padding
├── g3_watermark.jpg          # G3 full-bleed, tons clars
└── 25anys_banner.jpg         # banner "25 anys" small
```

### 4.2 Punt d'integració

**Fase 2** (`automation/ai_pipeline/typology.py`), dins el bloc d'extracció
d'imatges. Per cada imatge extreta:

1. Calcular `imagehash.phash(img)`.
2. Per cada reference de la library, calcular distància Hamming.
3. Si `min_distance <= LOGO_PHASH_THRESHOLD`:
   - `category = "logo_image"` (nova entrada taxonomia §5.4 arch doc)
   - `useful = False`
   - `conversion_strategy = "skip"`
   - `reason = f"matches G3DT logo reference '{best_ref}' (Hamming {d})"`

### 4.3 Constants

```python
# In typology.py
LOGO_PHASH_THRESHOLD: int = 6
_LOGO_REFERENCES_DIR = Path(__file__).parent.parent.parent / "schemas" / "ai_pipeline" / "logo_references"
```

Carreguem i hashejem les references una vegada al primer ús; cachem a nivell
de mòdul. Reload manual via `importlib.reload` per tests.

### 4.4 Nova categoria

Afegir `"logo_image"` a l'enumeració de categories de §5.4 del doc
d'arquitectura. Motiu: distingir clarament de `reference_output` (= output
d'Eva). Un logo és *present* a la carpeta del client; no és un deliverable
anterior.

### 4.5 Fallback quan la library no existeix

Si `schemas/ai_pipeline/logo_references/` està buit o no existeix,
l'extracció funciona exactament com avui (sense filtre). Cap error; un
`logger.info("no logo references loaded, skipping logo filter")` explícit.

### 4.6 Tests

1. **`test_logo_filter_flags_identical_match`** — crear un fitxer igual a una
   reference, extreure, assertir `category=="logo_image"` i `useful=False`.
2. **`test_logo_filter_ignores_random_noise`** — PNG amb soroll aleatori
   (generat amb el `_noisy_png_bytes` existent), NO flagged.
3. **`test_logo_filter_threshold_boundary`** — imatge amb Hamming 6 = flagged;
   amb Hamming 7 = not flagged.
4. **`test_logo_filter_degrades_gracefully_without_references`** —
   monkeypatch del directori references a una ubicació buida, extracció funciona
   sense errors.
5. **`test_reference_library_self_matches`** — les 4 references haurien de
   auto-coincidir amb Hamming 0 (guardrail contra corrupció dels fitxers de
   reference).

### 4.7 Dependències

- **Noves:** `imagehash>=4.3` (pyproject.toml).
- **Transitives:** `scipy` (requerit per imagehash per operacions DCT). Ja
  s'instal·la com a efecte col·lateral.

---

## 5. Impacte esperat

**Alcoletge:** 11 imatges filtrades → 11 image slots/blocks menys dins dels
parent-group calls (post-D1#2 no són 11 LLM calls menys, però sí menys tokens
de visió i menys pressió sobre el límit de 16 imatges per font).

**Projectes futurs amb PDFs watermark-only:** si un pressupost conté 5 pàgines
amb només el watermark G3, aquelles imatges s'eliminen i el parent group
pot esdevenir text-only (cost visió = 0 per aquella font).

**Risc de falsos positius a projectes amb empresa diferent:** la library és
G3DT-específica. Per altres clients caldrà estendre-la. El threshold ≤ 6 és
conservador, de manera que references d'una empresa no discriminaran contra
logos d'una altra.

---

## 6. Futur / v1.1

1. **Multi-client library** — `schemas/ai_pipeline/logo_references/{client}/`
   si Eficients arriba a servir més clients. Selecció de library segons
   `project.client_id`.
2. **Cheap-vision fallback** — per imatges a Hamming 7–20 (la "zona grisa" que
   avui està buida per Alcoletge però podria aparèixer a altres projectes),
   fer una crida `gpt-4.1-mini` amb prompt "is_logo?" per decidir. ~$0.0006
   per imatge ambigua.
3. **Logo learning** — quan Eva marca manualment una imatge com a logo al
   wizard, afegir-la a la library. Sistema auto-creixent.
4. **Per-client threshold tuning** — si un client tingués logos molt similars
   a contingut legítim, baixar el threshold a ≤4 per aquell client.

---

## 7. Comandaments útils

Re-executar l'experiment manual amb una config diferent:

```bash
# Modificar /tmp/phash_test_alcoletge_v2.py amb noves references/threshold
.venv/bin/python /tmp/phash_test_alcoletge_v2.py
```

Afegir una reference nova:
```bash
cp <source-logo> schemas/ai_pipeline/logo_references/<name>.<ext>
# Re-córrer els tests — la test de self-match captura qualsevol problema.
```
