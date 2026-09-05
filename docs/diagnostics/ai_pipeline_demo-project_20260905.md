# AI Pipeline Trace — demo-project
Generated: 2026-09-05T12:11:56+00:00

## Executive summary
- **Stage 1**: 2 files, 0 .msg, 0 extracted attachments
- **Stage 2**: 2 useful, 0 skipped
- **Stage 3**: 2 artifacts, 0 skipped, 200 bytes
- **Stage 4**: 2 sources, 2 candidates, 0 failures, cost $0.0000
- **Stage 5**: 1 concepts, 0 conflicts, 0 Pass-C reorderings, 0 no-change guardrails, cost $0.0000
- **Eva ground truth**: 0 concepts compared, 0 exact, 0 substring, 0 mismatch — top-1 accuracy 0.0%

## Top issues to investigate
_No issues surfaced._

## Per-stage health
### Stage 1: Inventari
- `total_files`: 2
- `root_file_count`: 2
- `msg_count`: 0
- `extracted_attachments`: 0
- `types`: `pdf_vector`=2
- `scanned_at`: 2026-04-24T10:00:00+00:00

### Stage 2: Tipologia
- `total_files`: 2
- `useful`: 2
- `skipped`: 0
- `counts_by_category`: `pdf_text`=2
- `warnings`: []
- `classified_at`: 2026-04-24T10:01:00+00:00

### Stage 3: Conversió
- `total_artifacts`: 2
- `skipped`: 0
- `by_format`: `md`=2
- `total_bytes`: 200
- `warnings`: []
- `converted_at`: 2026-04-24T10:02:00+00:00
- `source_count`: 2

### Stage 4: Anàlisi
- `sources`: 2
- `failures`: 0
- `candidates`: 2
- `concepts_covered`: 1
- `estimated_cost_usd`: 0.0
- `input_tokens`: 0
- `output_tokens`: 0
- `cache_hits`: 0
- `doc_types`: `test_doc`=2
- `analyzed_at`: 2026-04-24T10:03:00+00:00
- `systemic_failure`: None

### Stage 5: Rànquing
- `concepts`: 1
- `status_counts`: `ranked`=1
- `conflicts`: 0
- `groups_audited`: 0
- `pass_c_reorderings`: 0
- `pass_c_no_change_guardrails`: 0
- `estimated_cost_usd`: 0.0
- `input_tokens`: 0
- `output_tokens`: 0
- `cache_hits`: 0
- `ranked_at`: 2026-04-24T10:04:00+00:00

## Concept journeys
### `demo_concept`  (group: —)
- **Status**: `ranked`  •  **Picker**: `auto_accept`  •  **Agreement**: `unanimous`
- _Acord unànime entre fonts amb confiança alta._

**Candidates**
| value | confidence | source |
|---|---|---|
| 'ACME Corp' | 0.95 | `file_a.pdf` |
| 'ACME Corp' | 0.85 | `file_b.pdf` |

**Pass A ranking**
| rank | value | conf | source | rationale |
|---|---|---|---|---|
| 1 | 'ACME Corp' | 0.95 | `file_a.pdf` | r0 |
| 2 | 'ACME Corp' | 0.85 | `file_b.pdf` | r1 |

## Source journeys
### `file_a.pdf`
- **Stage 2**: category=`pdf_text`, useful=`True`, strategy=`pdf_to_markdown`
- **Stage 3**: 1 artifacts
- **Stage 4 insight**: `test_doc` — synthetic test
- **Candidates emitted**: 1
| concept_id | value | conf |
|---|---|---|
| `demo_concept` | 'ACME Corp' | 0.95 |
- **Stage 5 contributions**:
  - `demo_concept`: rank 1/2

### `file_b.pdf`
- **Stage 2**: category=`pdf_text`, useful=`True`, strategy=`pdf_to_markdown`
- **Stage 3**: 1 artifacts
- **Stage 4 insight**: `test_doc` — synthetic test
- **Candidates emitted**: 1
| concept_id | value | conf |
|---|---|---|
| `demo_concept` | 'ACME Corp' | 0.85 |
- **Stage 5 contributions**:
  - `demo_concept`: rank 2/2

## Decision audit
### Stage 2 dev-only skips (0)

### Stage 2 logo skips (0)

### Stage 3 conversion failures (0)

### Stage 4 retried sources (0)

### Stage 4 failed sources (0)

### Stage 5 Pass A retries (0)

### Stage 5 Pass B revisions flagged per group: {}

### Stage 5 Pass C no-change guardrails (0)

### Stage 5 Pass C reorderings (0)

## Instrumentation gaps (v2 candidates)
- Stage 2 logo filter: pHash distance not stored in ai_typology.json (only the reference name + Hamming integer in `reason`).
- Stage 4 cache hits per source: not flagged per-source in ai_analysis.json — only project-level total `cache_hits` is available.
- Stage 4 trimmed-prompt retries: the schema-validation retry path isn't recorded distinctly from regular retries; both contribute to `attempts > 1`.
