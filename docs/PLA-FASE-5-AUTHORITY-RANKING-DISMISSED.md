# Pla Fase 5 — Authority ranking per concepte

**Data:** 2026-04-25
**Branca:** `experiment/ai-pipeline`
**Referència:** `docs/ARQUITECTURA-AI-PIPELINE.md` §9 Fase 5 · `docs/AI-PIPELINE-DEFERRED.md` D4, D11, D12, D13
**Dades de validació:** `reference-material/4001670 ALCOLETGE/validation/ai_analysis.json`
(620 candidats, 72 fonts, 77/88 conceptes coberts).

---

## 1. Resum

**Fase 5 produeix, per cada concept_id de l'informe, una llista ordenada de
candidats (de més fiable a menys), aplicant regles d'autoritat codificades a
les `SourceInsight` + `Candidate` de Fase 4.**

Clau: **rank, NO reduce**. El valor final el tria Fase 6 (top-1 per defecte,
amb alternatives visibles a Eva al wizard). Aquesta separació permet a Eva
corregir regles *una vegada* ("plànol caixetí > email body per dimensions de
parcel·la") en comptes de re-decidir cada projecte.

Sortida canònica: `validation/ai_ranking.json` amb `{concept_id: [ranked_candidate, ...]}` + flags de conflicte per cada concepte multi-candidat.

---

## 2. Posicionament vs Fase 4 i Fase 6

| Què fa... | Fase 4 | **Fase 5** | Fase 6 |
|-----------|--------|------------|--------|
| Extreure valors | ✓ | — | — |
| Descriure la font | ✓ | — | — |
| Assignar confiança local | ✓ | — | — |
| **Ordenar candidats entre fonts** | — | ✓ | — |
| **Detectar conflictes** | — | ✓ | — |
| Triar valor final | — | — | ✓ |
| Mostrar alternatives a Eva | — | — | ✓ |

Fase 5 **no fa cap crida LLM**: és pura lògica determinista que consumeix
el `ProjectAnalysis` de Fase 4 i emet un `ProjectRanking` amb regles
configurables. Avantatge: testable end-to-end contra el manifest d'Alcoletge
sense credits.

---

## 3. Exploració de les dades (Alcoletge)

### 3.1 Document types emesos per Fase 4

Fase 4 emet `document_type` com a **string lliure** — 50+ valors distints
per 72 fonts al manifest d'Alcoletge. Exemples:

- `pressupost_pdf` · `planol_vision` · `field_photo` (categories curtes)
- `Informe geotècnic (geotechnical report)` · `Architectural plan (plànol de situació)` · `Company stamp / seal` (descripcions llargues)
- `empty_or_unreadable` · `logo_image` · `lab_granulometry_chart` (etiquetes específiques)

**Implicació:** les regles d'Eva no poden referir-se a aquests strings
directament. Fase 5 necessita una **capa de normalització** que mapa lliure →
canonical.

### 3.2 Canonical document categories (proposta)

Conjunt tancat de ~12 valors que el rule DSL pot referenciar:

| Canonical | Free-text observat |
|-----------|---------------------|
| `architect_plan` | `planol_vision`, `planol_arquitecte`, `Architectural plan (plànol)`, `architectural floor plan / site plan`, `Location map / situació i emplaçament`, `Plànol de situació ...` |
| `dpsh_field_sheet` | `Full de Camp Penetròmetre ...`, `Handwritten field sheet — Penetròmetre Dinàmic`, `Albarà de camp`, `Field work delivery note` |
| `sondeig_annex` | `Geotechnical cross-section`, `Tall de correlació`, `Plànol geotècnic - Perfil estratigràfic` |
| `spt_field_sheet` | `Full de assaig SPT/MI`, `Field photograph — SPT sample label sheet`, `SPT core sample with identification label` |
| `client_email` | `email`, `email_chain`, `Internal G3DT project briefing email ...` |
| `budget_excel` | `pressupost_pdf`, `Internal cost planning spreadsheet (Plan Cost / Pressupost)`, `Field preparation checklist` |
| `prior_report` | `Informe geotècnic (geotechnical report)` (quan és un informe previ, no el nostre output) |
| `project_coversheet` | `Project cover sheet (portada)` |
| `lab_report` | `Lab test request form`, `lab_granulometry_chart` |
| `site_photo` | `field_photo`, `site_photo`, `street-level site photograph`, `Field photograph` (quan no és SPT) |
| `geological_map` | `geological map extract`, `geological_map_extract`, `aerial_orthophoto`, `Location map / plànol de situació` |
| `coordinates_file` | `coordinates text file` |
| `logo` | `logo_image`, `Logo image`, `Company stamp / seal`, `Logo / Brand image`, `company_stamp` |
| `unreadable` | `empty_or_unreadable` |
| `other` | fallback |

La taula viurà a `schemas/ai_pipeline/document_categories.yaml` amb patrons
(lowercase substring + regex opcional) per cada canonical. Extensible sense
tocar codi.

### 3.3 Conflict surface

43 fonts emeten un candidat per `municipality`, 28 per `street_address`, 20
per `building_type`. La majoria coincidiran, però Fase 5 ha de marcar
explícitament els casos on top-1 i top-2 tenen valors distints amb confiança
comparable. Això és el senyal que Fase 6 mostra a Eva.

---

## 4. Models pydantic

```python
class RankedCandidate(BaseModel):
    """One candidate with its Fase 5-computed authority position."""
    candidate: Candidate          # el Candidate original de Fase 4
    rank: int                     # 1-based, més baix = més autoritatiu
    rank_reason: str              # "architect_plan wins over client_email for plot_area"
    canonical_doc_type: str       # "architect_plan", "client_email", etc.
    authority_score: float        # [0, 1], combinació de rule + confidence

class ConceptRanking(BaseModel):
    concept_id: str
    ranked: list[RankedCandidate] = Field(default_factory=list)
    has_conflict: bool = False
    conflict_reason: str = ""      # "top-2 values differ with confidence >= 0.8"

class ProjectRanking(BaseModel):
    project_path: str
    ranked_at: str
    rankings: dict[str, ConceptRanking] = Field(default_factory=dict)
    uncovered_concepts: list[str] = Field(default_factory=list)  # 0 candidats
    eva_summary: list[str] = Field(default_factory=list)
    schema_version: str = "1.0"
```

Rational: un `ConceptRanking` per concept_id amb la llista completa (no sols
top-N) perquè Fase 6 pot decidir quants mostrar; `has_conflict` precomputat
perquè la UI el llegeix directament sense recomputar.

---

## 5. Normalization layer

### 5.1 Config: `document_categories.yaml`

```yaml
version: "1.0"
categories:
  architect_plan:
    substrings:     # any match (lowercase) → this canonical
      - "planol"
      - "arquitect"
      - "architectural plan"
      - "site plan"
      - "planta"
      - "emplaçament"
      - "situació en la parcel"
    regex:          # optional
      - "planol[_\\- ]?arquitect"

  logo:
    substrings:
      - "logo"
      - "brand image"
      - "company stamp"
      - "seal"

  # ... remaining ~12 entries
```

### 5.2 API

```python
def canonicalize(doc_type: str) -> str:
    """Map a free-text Fase 4 document_type to a canonical category.
    First substring OR regex match wins. Falls back to 'other'.
    """
```

### 5.3 Testing

- Every observed Alcoletge `document_type` must resolve to a non-`other`
  canonical (except truly unclassifiable like `"other"` itself).
- No canonical-to-doc_type should be ambiguous: a given free-text string
  should canonicalize to exactly one value.

---

## 6. Rule DSL — `authority_rules.yaml`

### 6.1 Shape

Per-concept rule = ordered list of `document_category` preferences. First
match wins. Candidates whose canonical category is *not* mentioned drop to
the end (ordered by Fase 4 confidence).

```yaml
version: "1.0"
default_rule:
  # Applied to any concept without an explicit rule. Confidence-first,
  # with a small bias against logo/unreadable sources.
  prefer_categories: []
  demote_categories: [logo, unreadable]

rules:
  architect_name:
    prefer_categories:
      - architect_plan         # caixetí del plànol
      - client_email           # firma de l'arquitecte
      - budget_excel           # referencia al contracte
    demote_categories: [logo, unreadable]

  street_address:
    prefer_categories:
      - architect_plan         # caixetí del plànol = source of truth
      - client_email
      - coordinates_file
      - budget_excel
    # Email sender domain is a weak signal — rule #4 (D4)

  building_type:
    prefer_categories:
      - architect_plan
      - prior_report           # si Eva ja va escriure això abans, hi confia
      - client_email

  utm_x:
  utm_y:
    prefer_categories:
      - coordinates_file       # GPS de camp, màxima precisió
      - architect_plan         # si porta cotes
      - dpsh_field_sheet       # croquis amb coordenades
    demote_categories: [geological_map, site_photo]

  num_floors:
    prefer_categories:
      - architect_plan
      - prior_report

  # ... 45 concepts més
```

### 6.2 Semantics

Per cada candidat `c` d'un concepte amb regla `r`:

```
canonical = canonicalize(c.source_insight.document_type)

if canonical in r.prefer_categories:
    authority_score = (len(r.prefer_categories) - r.prefer_categories.index(canonical)) / len(r.prefer_categories)
    authority_score *= c.confidence
elif canonical in r.demote_categories:
    authority_score = 0.1 * c.confidence
else:
    authority_score = 0.5 * c.confidence  # neutral
```

Ordena descendent per `authority_score`. Desempat: `Candidate.confidence`,
després `source_path` (alfabètic, determinista).

### 6.3 Per què YAML en comptes de Python?

- Eva pot llegir/editar (en castellà/català ens-com-cat) una taula plana.
- Afegir un concepte nou o canviar una prioritat és un commit trivial, no
  un canvi de codi.
- Testable independentment: YAML → regles → comparació amb `eva_reference_values.json`.

### 6.4 Per què default_rule + per-concept?

Els 53 concepts tenen patrons que es repeteixen (plànol > email > budget per
quasi tot el que és descriptiu del projecte). Tenir un `default_rule` evita
haver d'enumerar els 53 conceptes quan la majoria segueixen el mateix patró.

---

## 7. Default rules seed — per cada concept_id

Llavor inicial basada en la metodologia d'Eva i les pistes que hem vist als
`authority_hints` d'Alcoletge. Subjecte a revisió per Eva abans de
congelar-se.

Grups:

**Identificació del projecte** (source-of-truth = plànol caixetí)
- `architect_name`, `architect_company`, `client_name`, `building_type`,
  `street_address`, `municipality`, `postal_code`, `expedient`, `num_floors`,
  `plot_area_m2`, `building_area_m2`:
  `[architect_plan, client_email, prior_report, budget_excel]`

**Dades de camp** (source-of-truth = fitxes DPSH/SPT)
- `num_dpsh_tests`, `field_date`, `dpsh_*_n20`, `spt_test_id`, `spt_n30`,
  `spt_location`, `refusal_depth`, `water_table_depth`:
  `[dpsh_field_sheet, spt_field_sheet, sondeig_annex, prior_report]`

**Laboratori** (source-of-truth = lab report)
- `lab_sulfates`, `lab_granulometry`, `lab_humidity`, `lab_field_company`:
  `[lab_report, dpsh_field_sheet, budget_excel]`

**Cota i coordenades**
- `utm_x`, `utm_y`, `cota_referencia`, `elevation_m`:
  `[coordinates_file, architect_plan, sondeig_annex, dpsh_field_sheet]`

**Visual / context** (Fase 4 candidats de `*_visual` vénen d'imatges)
- `is_anthropized_visual`, `site_slope_visual`, `site_vegetation_visual`,
  `access_road_visual`, `building_to_demolish_visual`,
  `surrounding_context_visual`, `is_urban`, `site_position`:
  `[site_photo, architect_plan, geological_map]`

**Context geològic**
- `geological_context`, `litology`, `soil_type`:
  `[sondeig_annex, dpsh_field_sheet, geological_map, prior_report]`

**Contacte / administratiu**
- `contact_name`, `contact_phone`:
  `[client_email, architect_plan, budget_excel]`

**Global demote**: tot aplica `demote_categories: [logo, unreadable]`.

---

## 8. Conflict detection

### 8.1 Quan hi ha conflicte?

`has_conflict = True` si:

1. Almenys 2 `RankedCandidate` comparteixen el mateix concept_id.
2. Els seus `candidate.value` són diferents (amb normalització: strip de
   whitespace, lowercase per strings; tolerància ε per floats).
3. La top-2 té `authority_score >= 0.4` — és a dir, no només és el fallback
   neutral d'un candidat sense regla match.

### 8.2 Què fa Fase 5 amb el conflicte?

Només el **marca**. `conflict_reason` explica per què:

- "Top-2 differ: 'Habitatge unifamiliar' (architect_plan, 1.0) vs 'Edifici plurifamiliar' (prior_report, 0.9)"

Fase 6 decideix com mostrar-ho a Eva (banner groc al camp, etc.).

### 8.3 Què NO fa Fase 5

- NO triar un valor final (això és Fase 6).
- NO intentar resoldre el conflicte amb una crida LLM (això seria una capa nova, v1.1).
- NO alertar per conflictes visuals (dos `site_photo` amb veredictes
  `is_urban: true` vs `false` — Eva veurà ambdues al wizard).

---

## 9. Tiebreaking (ordre dins del mateix authority_score)

Quan dos candidats tenen el mateix `authority_score` (típicament: mateixa
canonical category, mateixa confiança):

1. `SourceInsight.version_info` — si un diu "v2" i l'altre "v1", v2 guanya.
2. `SourceInsight.date_info` — data més recent guanya, parseada segons pugui.
3. `len(source_chain)` — cadenes més curtes (més directes) guanyen.
4. `source_path` alfabètic — desempat final determinista perquè el ranking
   sigui reproduïble.

Tots aquests tiebreaks són **deterministes**. No hi ha randomness enlloc.

---

## 10. Algoritme complet

```python
def rank_project(analysis: ProjectAnalysis) -> ProjectRanking:
    rules = load_rules()        # YAML
    categories = load_categories()  # YAML
    rankings: dict[str, ConceptRanking] = {}

    # Group Candidates by concept_id
    by_concept: dict[str, list[Candidate]] = defaultdict(list)
    source_insights = {s.source_path: s.insight for s in analysis.sources}
    for s in analysis.sources:
        for c in s.candidates:
            by_concept[c.concept_id].append(c)

    for concept_id, candidates in by_concept.items():
        rule = rules.for_concept(concept_id)  # falls back to default
        ranked: list[RankedCandidate] = []
        for c in candidates:
            canonical = canonicalize(source_insights[c.source_path].document_type)
            score = rule.score(canonical, c.confidence)
            reason = rule.explain(canonical)
            ranked.append(RankedCandidate(
                candidate=c, rank=0, rank_reason=reason,
                canonical_doc_type=canonical, authority_score=score,
            ))
        # Sort descending; tiebreak by version_info, date, chain, path
        ranked.sort(key=lambda r: tiebreak_key(r, source_insights), reverse=True)
        for i, r in enumerate(ranked, 1):
            r.rank = i

        # Conflict detection
        conflict = detect_conflict(ranked)
        rankings[concept_id] = ConceptRanking(
            concept_id=concept_id, ranked=ranked,
            has_conflict=conflict.is_conflict, conflict_reason=conflict.reason,
        )

    # Concepts with zero candidates
    all_concepts = set(load_concept_ids())
    uncovered = sorted(all_concepts - by_concept.keys())

    return ProjectRanking(
        project_path=analysis.project_path,
        ranked_at=now_iso(),
        rankings=rankings,
        uncovered_concepts=uncovered,
        eva_summary=build_eva_summary(rankings, uncovered),
    )
```

Aproximadament O(N log N) on N = nombre total de candidats (620 a Alcoletge
→ qüestió de mil·lisegons).

---

## 11. CLI + API + Wizard

### 11.1 CLI

```bash
.venv/bin/python scripts/ai_pipeline_ranking.py --project 4001670
.venv/bin/python scripts/ai_pipeline_ranking.py --project 4001670 --save
.venv/bin/python scripts/ai_pipeline_ranking.py --project 4001670 --concept architect_name
```

### 11.2 API

```
GET /api/ai-pipeline/ranking/{project}?refresh=true
GET /api/ai-pipeline/ranking/{project}/concept/{concept_id}
```

### 11.3 Wizard

Nova secció "Stage 5: Ranking" sota Stage 4:
- Per cada concepte amb candidats, mostrar el top-1 + botó "veure alternatives".
- Banner "⚠ conflict" quan `has_conflict=True`.
- Llista de `uncovered_concepts` amb badge "pendent per Eva".

---

## 12. Tests + benchmarking

### 12.1 Unitats

1. **Canonicalization:** every Alcoletge free-text `document_type` → non-`other` canonical (except the genuinely unknown ones).
2. **Rule scoring:** explicit test per concept — given fake candidates with various canonicals, expected rank order.
3. **Tiebreak:** two candidates with same canonical + confidence, different version_info → v2 > v1.
4. **Conflict detection:** two candidates agreeing → `has_conflict=False`. Two disagreeing with high confidence → `True`. One high + one low confidence → depends on the 0.4 threshold.
5. **Default rule fallback:** a concept without a rule uses `default_rule`.
6. **Zero-candidate concepts:** appear in `uncovered_concepts`.

### 12.2 End-to-end contra Alcoletge (D12 + D13)

```bash
.venv/bin/python scripts/benchmark_ranking.py --project 4001670
```

Compara top-1 de Fase 5 contra `eva_reference_values.json` per cada concept_id
que Eva va omplir manualment. Mètriques:

- **Coverage:** % de concepts amb almenys un candidat.
- **Top-1 accuracy:** % de concepts on top-1 ≡ valor d'Eva (amb tolerància
  per strings: case-insensitive, whitespace-normalized).
- **Top-3 accuracy:** % on el valor d'Eva apareix en el top-3.
- **Conflict precision:** quan `has_conflict=True`, quantes vegades el
  valor d'Eva coincideix amb el top-1 vs el top-2? (Ens dirà si les regles
  tenen el ordre correcte).

Objectiu adopció: **Top-1 accuracy ≥ 80%** sobre els 7 projectes de referència.
Si no, refinar les regles YAML.

### 12.3 Benchmark cross-project

Repetir el benchmark sobre els 7 projectes → comparar % top-1 accuracy. Si
un projecte destaca negativament (p.ex. Alcoletge 85% però Linyola 60%),
inspeccionar els casos discrepants per trobar regles que falten.

---

## 13. Dependencies + schema versioning

**Cap nova dependència.** Tot es pot fer amb `yaml` + `pydantic` (ja
presents). Sense LLM calls, sense `imagehash`, sense `openai`.

**Schema version** inicial: `ProjectRanking.schema_version = "1.0"`.

Quan canviïn:
- Shape de `ConceptRanking` / `RankedCandidate` → bump.
- `authority_rules.yaml` canvis no requereixen bump (són config, no schema).
- `document_categories.yaml` canvis tampoc.

**Cache de Fase 5:** `validation/ai_ranking.json` a disk. Hash key =
SHA256(ai_analysis.json + authority_rules.yaml + document_categories.yaml +
schema_version). Canviar qualsevol dels quatre invalida la cache automàticament.

---

## 14. Arquitectura tècnica (pla d'implementació)

```
automation/ai_pipeline/
└── ranking.py                      # Fase 5 — nou

schemas/ai_pipeline/
├── authority_rules.yaml            # nou
└── document_categories.yaml        # nou

scripts/
├── ai_pipeline_ranking.py          # nou — CLI
└── benchmark_ranking.py            # nou — benchmarking contra eva_reference_values

web/
└── api.py                          # afegir endpoints /api/ai-pipeline/ranking/*

templates/validation/
└── review.html                     # afegir secció "Stage 5"

tests/
└── test_ai_pipeline_ranking.py     # ~30 tests (units + integration contra Alcoletge)
```

---

## 15. Passos d'implementació proposats

**Ordre cronològic (cadascun commit independent):**

1. **docs/PLA-FASE-5-AUTHORITY-RANKING.md** ← aquest doc, commit ara.
2. **`document_categories.yaml`** + `canonicalize()` + unit tests.
3. **Models pydantic** (`RankedCandidate`, `ConceptRanking`, `ProjectRanking`) amb save/load.
4. **`authority_rules.yaml`** amb llavor inicial + loader.
5. **Algoritme de ranking** + unit tests.
6. **Conflict detection** + tiebreak + tests.
7. **CLI `ai_pipeline_ranking.py`** + smoke test sobre Alcoletge.
8. **Benchmark script + run contra els 7 projectes** → ajustar regles segons resultats.
9. **API + wizard section.**
10. **Update arch doc §7 Fase 5 dissenyada → implementada.**

---

## 16. Decisions de disseny obertes

Per validar amb Josep/Eva abans d'implementar:

1. **Confidence threshold per al conflicte** — el paper diu 0.4 per al
   top-2 abans de marcar conflicte. És massa laxe? Massa estricte? La
   resposta haurà de venir del benchmark contra Alcoletge.
2. **Tolerància de string per igualtat de valors** — case-insensitive +
   whitespace és clar; però "Habitatge unifamiliar" vs "habitatge
   unifamiliar aïllat" són el mateix per Eva? Probablement sí, però no
   obvi. Necessitem una funció `values_equivalent(a, b, concept_id)` amb
   regles per concepte.
3. **Value normalization abans de conflict detection** — normalitzar
   coordinates UTM a 2 decimals abans de comparar, strip d'unitats a
   numeric strings, etc. Scope per a v1.1 o s'inclou a MVP?
4. **LLM tiebreak opt-in** — quan hi ha conflict irresoluble amb alta
   confiança, demanar a Claude "which is more likely correct?" amb els
   quotes verbatims. Pay-per-use, explícitament opt-in via
   `G3DT_AI_RANKING_LLM_TIEBREAK=1`. Clarament v1.1.
5. **Multi-value concepts** — alguns concepts (e.g., `sondeig_layers`,
   `dpsh_n20_values`) tenen llista com a valor. El ranking per llista té
   sentit? O es deixa a Fase 6 per mergir?

---

## 17. Referències

- `docs/ARQUITECTURA-AI-PIPELINE.md` — arquitectura base
- `docs/AI-PIPELINE-DEFERRED.md` — D4 (rule per archit_name), D11 (authority DSL), D12 (proto Fase 6), D13 (benchmark)
- `schemas/concepts/report_variables.yaml` — 53 concepts
- `reference-material/4001670 ALCOLETGE/validation/ai_analysis.json` — test bench
- `reference-material/*/validation/eva_reference_values.json` — ground truth per benchmark
