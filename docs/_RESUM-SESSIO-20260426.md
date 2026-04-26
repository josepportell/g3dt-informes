# Resum sessió 2026-04-26 — canvis al pipeline IA des de l'últim run

**Branca:** `experiment/ai-pipeline`
**Últim run live:** 2026-04-24 (Alcoletge Stage 4 + Stage 5, $4.06 + $4.63 = $8.69 gastat aleshores)
**Aquesta sessió:** **0 € gastats en API.** Tots els canvis són offline (codi, dades manuals, principis, investigacions).

---

## 1. Bugs corregits (dades)

### Bearing-stratum extraction (CRÍTIC) — `e0579be`

`reference_extractor.py:_flatten_loop_table_concepts` llegia `geotech_rows[0]` (estrat superior) en lloc de `geotech_rows[-1]` (estrat de recolzament). Per projectes multi-capa això produïa valors dramàticament equivocats:

- Alcoletge: E = 50 → **>400**, cohesió = 0.00 → **1.0**
- Linyola: E = 100 → **>800**
- Vilanova: E = 50 → **550**

Eva sempre reporta `geomech_*` del bearing stratum, no del superficial. Investigació completa a `docs/INVESTIGACIO-GEOMECH-STRATUM.md`.

### Merge de `eva_reference_values.json` — `a3bbfc7`

Una re-extracció anterior va destruir silenciosament ~125 entrades `intelligent_analysis` (text extret per LLMs externs en passades anteriors sobre conceptes que un extractor posicional no recupera: `client`, `radon_zone`, `adjacent_*_fmt`, `site_description`, `geo_p`, `materials_intro`, `conclusions_*`...). La nova lògica de merge (`_merge_with_prior`) preserva entrades amb `extraction_method` no produït pel codi actual.

### Header-row contamination

Rubí, Linyola, Alcoletge tenien la fila 0 de `sondeig_tests` amb text de capçalera (`"Nº assaig"`, `"Punt"`, `"Prof. Extracció (m)"`). Filtre nou `_is_table_header_row` els elimina.

---

## 2. Ground truth manual afegida (sense API)

- **UTM x/y/z** per 5 de 7 projectes des d'`ANNEXES/COORDENADES.txt` (Castellar, Rubí, Linyola, Bell-Lloc, Alcoletge). Vilanova i Anciles no tenen el fitxer.
- **Alcoletge `architect_name`**: corregit de `"ALBERT SANS BONVEHI"` (promotor) a `"DAVID GRAUS ROBINAT"` (caixetí del plànol). Investigació a `docs/INVESTIGACIO-ARCHITECT-NAME.md`.
- **Linyola `architect_name`**: corregit de `"SÍLVIA EROLES BALAGUERÓ"` (client) a `"BUNYESC ARQUITECTURA EFICIENT"` (firm-led pattern). El `architect_company` ja era correcte.

Totes les correccions són `extraction_method: intelligent_analysis` → preservades pel merge.

---

## 3. Mejoras del pipeline (codi)

| Fix | Impacte | Commit |
|---|---|---|
| **D18 prompt-cache fix** | El bloc cached inclou ara el YAML complet de conceptes (~3.5k tokens) → supera el mínim de 1024 tokens d'Anthropic → ~30% estalvi en input cost al pròxim run | `47b657e` |
| **Phase 1 calculator delegation** (Stage 4.5) | Nova passada entre Stage 4 i Stage 5 que delega `qa_value` + `settlement_cm` als calculadors legacy de Terzaghi/Schmertmann. Detrás de feature flag `G3DT_ENABLE_CALCULATOR_DELEGATION` (default OFF) | `f32eadc` |
| **Pre-skips de Stage 2** (A3) | DTE.txt, COORDENADES.txt, PRESSUPOST early-images ja no arriben a Stage 4. Estalvi ~$0.20/projecte | `f32eadc` |
| **Parser determinista de COORDENADES.txt** | Nou `automation/ai_pipeline/coordinates_parser.py`. Parses 6/7-digit integer UTMs amb format `X ; Y ; Z`. Tolera comma decimals (espanyol) i missing Z | `f32eadc` |
| **Disambiguation YAML** | Nou concepte `commercial_code` (format YY.NNNN). Descripcions de `architect_name` / `client_name` / `expedient` molt més estrictes | `47b657e` |
| **Architect/client conflation guard** | `_guard_architect_client_conflation` detecta auto-promoció + body-sentence patterns "Sr./Sra. X en nom propi"; abaixa la confiança a 0.0 quan dispara | `47b657e` |
| **Trimmed-prompt retry (D5)** | Quan Stage 4 falla schema validation, el retry desplega el bloc de principis (estalvi de tokens en re-attempts) | `47b657e` |
| **`G3DT_AI_SKIP_GROUPS` env var** | Permet saltar Pass B per a grups específics. Per al re-run: `G3DT_AI_SKIP_GROUPS=coordinates` per eliminar el verdict de corrupció UTM (-2 a Alcoletge) | `82b45c8` |

---

## 4. Authority principles file (`schemas/ai_pipeline/authority_principles.md`)

Reestructurat amb **TOC + 10 seccions numerades**. Noves regles concretes:

| § | Tema | Regla principal |
|---|---|---|
| §1 | Principis generals | + nova: "Quan dubtis, deixa l'ordenació de Pass A intacta" |
| §2 | Per concepte (regles ràpides) | + apuntadors a seccions detallades |
| §3 | Resolució de conflictes | Unificada amb regla d'override per regles específiques |
| §4 | **Coordenades UTM** (NOU) | Format estricte 6/7-dígits enters EPSG:25831; demote explícit per lat/lon decimals |
| §5 | **expedient vs commercial_code** (NOU) | Identificadors diferents, mai intercanviables |
| §6 | **Identificació de persones** (NOU) | 4 patrons del cos de l'informe documentats (estàndard / truncat / auto-promogut / firm-led) |
| §7 | **Bearing stratum** (NOU) | Cita textual d'Alcoletge: *"...es descarta totalment per a recolzar-hi qualsevol element de fonamentació..."* |
| §8 | **Noms d'empreses/persones** (NOU) | Preferir forma completa registrada sobre alias comercials |
| §9 | **Prior outputs vs documents signats** (matís) | `*_informe*` autoritatius per identificació, NO per valors derivats |
| §10 | **Calculator candidates** (NOU) | Regles per als candidats sintètics de Phase 1 |

Aclariment §9: el pipeline IA NO consumeix `_informe*` files en runtime normal (D17 els filtra a Stage 2). §9 és defensa en profunditat per al cas en què la cache de Stage 2 sigui stale o si arriben fitxers d'altres projectes per error.

---

## 5. Eines noves de diagnòstic

- **`scripts/ai_pipeline_trace.py`** — anàlisi completa per projecte: concept journey, source journey, decision audit, top-30 issues ranked, Pass C diff integration. **Tot offline, zero API.** (`b1e0080`)
- **`scripts/ai_pipeline_pass_c_diff.py`** — verdicts better / worse / neutral / no_eva_ref per cada concepte que Pass C va re-ordenar. (`47b657e`)
- **`scripts/ai_pipeline_calculator_pass.py`** — CLI per a la Phase 1 calculator delegation. (`f32eadc`)

---

## 6. Documents d'investigació generats

A `docs/`:

- **`INVESTIGACIO-GEOMECH-STRATUM.md`** (A1) — descobriment del bug bearing-stratum.
- **`INVESTIGACIO-SILENT-SOURCES.md`** (A3) — anàlisi de les 8 fonts silencioses.
- **`INVESTIGACIO-ARCHITECT-NAME.md`** (B2) — root cause de la conflation arquitecte/promotor.
- **`INVESTIGACIO-PASS-BC-EFFECTIVENESS.md`** (B1) — auditoria cost vs benefici de Pass B/C (coordinates group net-negative).
- **`INVESTIGACIO-ENGINEERING-DELEGATION.md`** (B3) — recomanació GO per Phase 1.

---

## 7. Mètriques d'Alcoletge (sense gastar API)

| Mètrica | Inicial (post-run 2026-04-24) | Després de tots els canvis |
|---|---|---|
| `compared` (Eva refs visibles al trace) | 34 | **47** |
| `exact` matches | 5 | **13** |
| `top1_accuracy` | 14.7% | **27.66%** |
| Pass C verdicts (better/worse/neutral/no_eva_ref) | 3/1/1/9 | **5/3/1/5** |

Bona part del salt en `top1_accuracy` ve de mesurament més honest (el name-alias map + UTM ground truth + bearing-stratum fix permeten al trace tool comparar conceptes que abans semblaven `no_eva_ref`). El que mesurem ara és una imatge molt més fidel de la qualitat real del pipeline.

---

## 8. Tests + commits

- **Tests**: 884 (baseline) → **984** passing. +100 tests nous (gairebé tots són mocked, zero API calls).
- **Commits** aquesta sessió (8 a `experiment/ai-pipeline`):
  ```
  82b45c8  C1 polish + G3DT_AI_SKIP_GROUPS env-var
  f32eadc  Phase 1 calculator delegation + A3 silent-source rules
  15505ac  B3 investigation doc
  6d706f2  B1 audit + UTM/full-name principles
  93e6fe6  A3 silent sources + B2 architect_name investigation docs
  e0579be  geomech bearing-stratum fix
  a3bbfc7  reference_extractor merge prior IA + flatten table rows
  15c2263  iteration 2 — eva-comparison name aliases
  ```

---

## 9. Què falta abans del re-run live (D1)

### Decisió pendent: Phase 1 feature flag ON/OFF al re-run

Tres opcions:

| Opció | Pre-run env | Cost re-run | Què mesurem |
|---|---|---|---|
| **A** | `G3DT_AI_SKIP_GROUPS=coordinates` (només) | ~$2.50 | Pures millores de principis + extractor + UTM corruption eliminada. Calculator delegation NO mesurada |
| **B** | A + `G3DT_ENABLE_CALCULATOR_DELEGATION=true` | ~$2.55 | Ambdues millores mesurades juntes. Risc: el calculador emet `qa=3.0` vs Eva `3.50` → podria rankejar top-1 sobre LLM i produir `worse` |
| **C** | Re-run amb A; després post-run flip flag ON localment | ~$2.55 | Millor higiene del senyal. Run amb calculator OFF, després mesura offline amb flag ON. Costs igual a B |

### Procediment de re-run (qualsevol opció)

1. Invalidar caches d'Alcoletge:
   ```bash
   rm -f reference-material/4001670\ ALCOLETGE/validation/{ai_typology,ai_conversion,ai_analysis,ai_ranking}.json
   rm -rf reference-material/4001670\ ALCOLETGE/validation/ai_pipeline/{analysis,ranking,calculations}/
   ```

2. Configurar env vars:
   ```bash
   export G3DT_AI_SKIP_GROUPS=coordinates
   # (opcional per opció B/C)
   export G3DT_ENABLE_CALCULATOR_DELEGATION=true
   ```

3. Executar el pipeline complet:
   ```bash
   .venv/bin/python scripts/ai_pipeline_typology.py --project 4001670 --save
   .venv/bin/python scripts/ai_pipeline_conversion.py --project 4001670 --save
   .venv/bin/python scripts/ai_pipeline_analysis.py --project 4001670 --save  # Stage 4
   # (opcional per Phase 1)
   .venv/bin/python scripts/ai_pipeline_calculator_pass.py --project 4001670 --save
   .venv/bin/python scripts/ai_pipeline_ranking.py --project 4001670 --save  # Stage 5
   ```

4. Mesurar:
   ```bash
   .venv/bin/python scripts/ai_pipeline_trace.py --project 4001670 --save --report markdown
   .venv/bin/python scripts/ai_pipeline_pass_c_diff.py --project 4001670 --save
   ```

### Pressupost

- Pressupost total: **$5.00**
- Estimació re-run: **~$2.50–2.55**
- Marge per iteració post-run: **~$2.45**

---

## 10. Coses obertes per a Eva

1. **`QA_CAP_ROCK` constant**: el codi legacy té `QA_CAP_ROCK = 3.0`, però MEMORY documenta caps de 4.0–4.5 per roca. Calculator output a Alcoletge: qa = 3.0 vs Eva = 3.50. Pregunta: per `lutites alterades` amb `Nb = R`, quin cap aplica Eva?
2. **Refusal handling**: quan DPSH arriba a refús a depth N, quin valor `Nb` usa Eva al càlcul? Algunes projectes mostren `R` (tractat com ≥50?), altres `47-R` (usar 47). Cal una regla canònica.
3. **PLAN_COST_ALCOLETGE/img_000.png paradox**: byte-identic a `g3_tight.png` ja al library, però el pHash filter no el detecta. Hipòtesi: PyMuPDF re-encoda imatges en alguns paths d'extracció. Investigar si recurrent.

---

*Resum guardat 2026-04-26.*
