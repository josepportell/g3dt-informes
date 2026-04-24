# Pla Fase 5 — Authority ranking per concepte (LLM-based)

**Data:** 2026-04-25
**Branca:** `experiment/ai-pipeline`
**Supersedes:** `docs/PLA-FASE-5-AUTHORITY-RANKING-DISMISSED.md` (enfoc determinista amb DSL YAML, descartat).
**Referència:** `docs/ARQUITECTURA-AI-PIPELINE.md` §9 · `docs/AI-PIPELINE-DEFERRED.md` D4, D11, D12, D13
**Dades de validació:** `reference-material/4001670 ALCOLETGE/validation/ai_analysis.json`
(620 candidats, 72 fonts, 77/88 conceptes coberts).

---

## 1. Resum

**Fase 5 produeix, per cada `concept_id` de l'informe, una llista ordenada de
candidats (de més fiable a menys), aplicant els principis d'autoritat d'Eva
sobre els `SourceInsight` + `Candidate` de Fase 4 — amb un LLM com a raonador.**

Clau: **rank, NO reduce**. El valor final el tria Fase 6 (top-1 per defecte,
amb alternatives visibles a Eva al wizard). Aquesta separació permet a Eva
corregir principis *una vegada* ("plànol caixetí > email body per dimensions
de parcel·la") en comptes de re-decidir cada projecte.

**Per què LLM en comptes de regles deterministes.** El `document_type` que
emet Fase 4 és text lliure — 49 valors distints a Alcoletge ("planol_vision",
"Architectural plan (plànol de situació)", "Plànol de situació en la
parcel·la"…). L'enfoc determinista hauria necessitat una capa de normalització
(~14 categories canòniques) + un DSL YAML per-concepte. L'LLM salta aquesta
capa: llegeix els `SourceInsight` directament i els principis d'Eva en prosa.
A més, raona sobre dimensions que un DSL no captura: *"aquest plànol diu v2 i
hi ha correu de l'arquitecte dient que la v1 és obsoleta — trust v2 per
dimensions"*.

**Alfonso check:** *"no estem construint un enginyer geotècnic, un assistent
intel·ligent de redacció"*. Fase 5 decideix quina font trustes per una dada,
no què és veritat enginyerilment. ✓

Sortida canònica: `validation/ai_ranking.json` amb `ProjectRanking`:
`{concept_id: ConceptRanking}` amb candidats ordenats, flags de conflicte, i
estat explícit per conceptes sense candidats.

---

## 2. Posicionament vs Fase 4 i Fase 6

| Què fa... | Fase 4 | **Fase 5** | Fase 6 |
|-----------|--------|------------|--------|
| Extreure valors d'una font | ✓ | — | — |
| Descriure la font (SourceInsight) | ✓ | — | — |
| Assignar confiança local | ✓ | — | — |
| **Ordenar candidats entre fonts** | — | ✓ | — |
| **Detectar conflictes inter-fonts** | — | ✓ | — |
| Triar valor final | — | — | ✓ |
| Mostrar alternatives a Eva | — | — | ✓ |
| Permetre override d'Eva | — | — | ✓ |

Fase 5 consumeix `ProjectAnalysis` (Fase 4) i emet `ProjectRanking`. No toca
els `Candidate` individuals — només els referencia en l'ordre produït.

---

## 3. Arquitectura: 3 passades

```
Fase 4: ProjectAnalysis (72 sources, 620 candidates, 77 concepts w/ candidates)
         │
         ▼
┌─── PASSADA A — Per-concept ranker (71 calls) ──────────────┐
│ Per cada concept amb ≥2 candidats:                         │
│   input  = concept def + glossari + principis d'Eva +      │
│            candidats + SourceInsight de cada font          │
│   output = [ranked_candidate_ids] + has_conflict + rationale│
│ Concepts amb 1 candidat    → passthrough (no LLM call)     │
│ Concepts amb 0 candidats   → explicit "no_candidates"      │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─── PASSADA B — Per-group auditor (13 calls) ───────────────┐
│ Per cada group (parcel, lab, field_work, …):                │
│   input  = group description + principis d'Eva +           │
│            resultats de Passada A per tots els concepts    │
│            del grup + SourceInsight de totes les fonts     │
│            que van aportar candidats al grup               │
│   output = llista de "decision-changing factors" observats │
│            + per cada concept del grup: flag revise (bool) │
│            + rationale (per què cal revisar o no)          │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─── PASSADA C — Targeted revision (0..N calls) ─────────────┐
│ Només per conceptes marcats revise=True a la Passada B:    │
│   input  = mateix que Passada A + els factors detectats    │
│            a Passada B com a context addicional            │
│   output = nova ordenació + rationale actualitzada         │
│ Si no es marca cap revise a Passada B → 0 calls.           │
└────────────────────────────┬────────────────────────────────┘
                             ▼
        ProjectRanking → validation/ai_ranking.json
```

**Per què tres passades i no dues.** Una sola passada per-concepte no veu
senyals cross-concept (*"un email revela que el projecte s'ha canviat de v1 a
v2 — revisa tots els candidats dimensionals que venen del plànol v1"*). Una
sola passada per-group perd la profunditat del raonament per-concept. La
combinació: per-concept fa el treball fi, per-group és un auditor que pot
senyalar casos, targeted revision només s'executa quan cal. En projectes
"nets" (la majoria), Passada C no fa cap crida.

**Cost estimat per Alcoletge:**
- Passada A: ~71 calls × ~$0.010–0.015 = ~$0.70–1.10
- Passada B: 13 calls × ~$0.030 (context més gran) = ~$0.40
- Passada C: típicament 0–5 calls × ~$0.015 = ≤$0.08

Total ~**$1.10–1.60/projecte**, cacheable per concept. Molt per sota del $4
de Fase 4.

---

## 4. Principis d'autoritat d'Eva (input humà, no DSL)

**Ubicació:** `schemas/ai_pipeline/authority_principles.md` — un fitxer Markdown
en català que Eva (o nosaltres amb ella) editem directament. Carregat *verbatim*
a cada crida A i B.

**Per què Markdown en comptes de YAML:** el lector és un LLM. Entén prosa amb
més matisos que llistes tancades. Eva pot escriure excepcions i motivacions
("confia el plànol caixetí però si és signat ≥6 mesos abans del correu més
recent, valora el correu més"). Un DSL YAML hauria d'encapsular això en
estructures rígides que o bé no existeixen o bé requereixen código nou.

**Esquelet inicial** (per omplir amb Eva — v0 pot ser mínim):

```markdown
# Principis d'autoritat — Eva G3 Geotècnia

## Principis generals
- Font signada per l'arquitecte (plànol, memòria) > correu informal.
- Plànol caixetí (secció de dades) > cotes interiors del dibuix per
  identificació de projecte, client, arquitecte.
- Dada manuscrita de camp > dada transcrita (Excel) en cas de discrepància
  numèrica: la manuscrita és primària.
- Informe previ d'Eva (`prior_report`) NO és autoritatiu — és un output, no
  una font.

## Per concepte
- `architect_name`: caixetí del plànol > domini del remitent de l'email > nom
  de fitxer.
- `num_floors`: plànol > memòria escrita > email.
- `utm_x`, `utm_y`: COORDENADES.txt de camp > plànol > geocodificació.
- `sulfates_mg_kg`: informe de laboratori > fitxa de camp > estimació.
- `municipality`: plànol caixetí > cadastre > adreça textual.

## Resolució de conflictes
- Entre dues versions de plànol, la més recent (`version_info` posterior o
  `date_info` més gran) guanya.
- Si un correu posterior contradiu un plànol anterior, pregunta: el correu
  anuncia un canvi? Si sí, correu guanya. Si no (és comentari), plànol guanya.
```

**Gestió:** arxiu versiontat amb el codi. Qualsevol canvi invalida les caches
de Passada A i B (via hash del contingut dins la cache key).

---

## 5. Call shapes

### 5.1 Passada A — Per-concept ranker

**System prompt** (fixe):
> Ets un assistent de redacció d'informes geotècnics treballant per Eva (G3
> Geotècnia). Per un `concept_id` concret, ordenes els candidats de valor
> extrets de diverses fonts, del més fiable al menys, segons els principis
> d'autoritat d'Eva. **No pots inventar candidats nous ni alterar els seus
> valors.** Retornes una tool call `ConceptRanking` amb l'ordenació i una
> rationale concisa. Si detectes que dos candidats estan en conflicte
> (valors significativament diferents, els dos amb confiança raonable),
> marca `has_conflict=true`.

**User content blocks** (en ordre):
1. **Concept definition** (extret de `report_variables.yaml`): id, type,
   group, `description_ca`.
2. **Glossary entry** si existeix a `schemas/ai_pipeline/concept_glossary.yaml`
   (no sempre present).
3. **Authority principles** — contingut *verbatim* de
   `authority_principles.md` (marcat amb `cache_control: {"type":
   "ephemeral"}` per aprofitar prompt caching, igual que D16).
4. **Candidates block** — JSON amb una llista de candidats, cadascun amb:
   ```json
   {
     "candidate_id": "cand_0",   // estable dins la crida
     "value": ...,
     "confidence": 0.85,
     "quote": "…",
     "reasoning": "…",
     "source": {
       "path": "...",
       "document_type": "Architectural plan (plànol)",
       "purpose": "…",
       "author": "…",
       "date_info": "…",
       "version_info": "…",
       "authority_hints": [...],
       "source_chain": [...]
     }
   }
   ```
5. **Imperative footer:** *"Retorna una única tool call `ConceptRanking` amb
   `ranked`, `has_conflict`, `conflict_note`."*

**Tool schema:**
```python
{
  "name": "ConceptRanking",
  "input_schema": {
    "type": "object",
    "required": ["ranked", "has_conflict"],
    "properties": {
      "ranked": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["candidate_id", "rationale"],
          "properties": {
            "candidate_id": {"type": "string"},
            "rationale": {"type": "string"}  # ≤1 frase
          }
        }
      },
      "has_conflict": {"type": "boolean"},
      "conflict_note": {"type": "string"}  # requerit si has_conflict=true
    }
  }
}
```

### 5.2 Passada B — Per-group auditor

**System prompt** (fixe):
> Revises l'ordenació ja feta d'un grup de conceptes (p.ex. `parcel`,
> `lab`). Busques **senyals cross-concept que puguin canviar l'ordenació
> d'algun concept individual** — per exemple, un document que apareix en
> diversos candidats del grup amb una version_info que suggereix invalidar
> fonts més antigues. No re-ordenes tu — **senyales** quins conceptes
> mereixen ser revisats i per què. Retornes una tool call `GroupAudit`.

**User content blocks:**
1. Group name + descripció curta + llista de concept_ids del grup.
2. Authority principles (cached block — mateix que Passada A).
3. **Current rankings** — resultat de Passada A per cada concept del grup:
   ```json
   [{"concept_id": "...", "ranked": [...], "has_conflict": bool}, ...]
   ```
4. **Unique sources involved** — SourceInsight (dedupat) de totes les fonts
   que han aportat algun candidat al grup.
5. Imperative footer: *"Retorna `GroupAudit` amb `factors` (llista de
   decision-changing factors detectats, ≤3) i `revisions` (per cada
   concept_id del grup: revise:bool + reason)."*

**Tool schema:**
```python
{
  "name": "GroupAudit",
  "input_schema": {
    "type": "object",
    "required": ["factors", "revisions"],
    "properties": {
      "factors": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["description", "affects"],
          "properties": {
            "description": {"type": "string"},  # la pista
            "affects": {"type": "array", "items": {"type": "string"}}  # concept_ids
          }
        }
      },
      "revisions": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["concept_id", "revise"],
          "properties": {
            "concept_id": {"type": "string"},
            "revise": {"type": "boolean"},
            "reason": {"type": "string"}
          }
        }
      }
    }
  }
}
```

### 5.3 Passada C — Targeted revision

Per cada concept marcat `revise=true` a Passada B, una sola crida amb:
- Mateix prompt que Passada A, però afegint un bloc extra a l'inici:
  > **Senyal del grup:** {description del factor corresponent}
- Tool call és la mateixa (`ConceptRanking`). El resultat substitueix el de
  Passada A.

**Guardràil:** si Passada C produeix la mateixa ordenació que Passada A (cap
canvi), es descarta el resultat revisat i es deixa el de Passada A — però es
registra el factor a `ConceptRanking.group_factor_considered` per traçabilitat.

---

## 6. Output schema

```python
class RankedCandidate(BaseModel):
    candidate_id: str           # id estable dins ProjectAnalysis.sources[...].candidates
    source_path: str            # rescatat per a consum directe
    value: Any                  # copiat del Candidate (Fase 6 no ha de re-buscar)
    confidence: float           # confiança local de Fase 4
    rationale: str              # ≤1 frase — per què va aquí a l'ordenació

class ConceptRanking(BaseModel):
    concept_id: str
    status: Literal["ranked", "single", "no_candidates"]
        # ranked         → passes A (+B+C) aplicades
        # single         → 1 candidat, passthrough sense LLM
        # no_candidates  → cap font ha aportat valor; EXPLÍCIT, no null
    ranked: list[RankedCandidate] = Field(default_factory=list)
    has_conflict: bool = False
    conflict_note: str = ""
    group_factor_considered: str = ""
        # populat si Passada B va senyalar un factor per aquest concept
    revised_by_group_pass: bool = False
        # True si Passada C ha canviat l'ordre vs Passada A
    attempts: int = 0
    elapsed_ms: int = 0
    model: str = ""

class GroupAuditResult(BaseModel):
    group: str
    factors: list[dict]          # verbatim de la tool call B
    revisions: list[dict]        # verbatim de la tool call B
    attempts: int = 0
    elapsed_ms: int = 0
    model: str = ""

class ProjectRanking(BaseModel):
    project_path: str
    ranked_at: str
    concepts: dict[str, ConceptRanking]      # indexat per concept_id
    groups: dict[str, GroupAuditResult]      # indexat per group name
    eva_summary: list[str] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    failures: list[dict] = Field(default_factory=list)  # errors per-concept o per-group
```

**Estatus de "no_candidates" explícit** (punt 3 acordat amb Josep): distingim
*"Fase 4 no va trobar cap font per aquest concept"* de *"Fase 5 ha fallat o
no s'ha executat"*. Fase 6 veu `status="no_candidates"` → passa directament
a "pendent d'omplir per Eva" sense ambigüitat.

---

## 7. Caching i re-execució

**Per-concept cache** (Passada A i C):
- Path: `{project}/validation/ai_pipeline/ranking/{concept_id}_cache.json`
- Key = SHA256 de:
  - `concept_id`
  - JSON canonical dels candidats (ordenat per candidate_id)
  - Contingut de `authority_principles.md`
  - Model id
  - `_RANKING_SCHEMA_VERSION` (nou constant)
  - Per Passada C: el `group_factor` addicional

**Per-group cache** (Passada B):
- Path: `{project}/validation/ai_pipeline/ranking/_group_{group}_cache.json`
- Key = SHA256 de les mateixes coses + resultats de Passada A pels concepts
  del grup (ordenats).

**Invalidation natural:**
- Eva edita `authority_principles.md` → tota la cache invalida.
- Fase 4 re-analitza una font i emet nous candidats → només els concepts
  afectats re-corren (Passada A), el grup de pertinença re-corre (Passada
  B), i potser Passada C.

**Refresh explícit:** `?refresh=true` a l'API i `--force` al CLI.

---

## 8. Resum per Eva (`eva_summary`)

```
Hem ordenat candidats per 88 variables de l'informe:
• 71 variables tenen múltiples candidats — ordenats segons els teus principis.
• 6 variables tenen un únic candidat — sense ordenació necessària.
• 11 variables no tenen cap candidat — hauràs d'omplir-les manualment.
• 4 conflictes detectats: revisa `architect_name`, `num_floors`, ...
• El grup `parcel` ha detectat 1 factor transversal que ha canviat l'ordre
  de `parcel_area_m2` (versió v2 del plànol superseia v1).
```

Aquesta és la tercera línia de transparència d'Alfonso: *"això és el que hem
entès del que has aportat" → "aquestes són les fonts més fiables per cada
cosa"*.

---

## 9. Error handling

Classes d'errors igual que Fase 4 (systemic vs per-concept):

**Systemic** (aborta Fase 5 sencera):
- Credits, 401, 403, model_not_found → es registra a `ProjectRanking.failures`
  com una sola entrada. Concepts sense rankejar queden `status="ranked"` amb
  `ranked=[]` + missatge d'error? → no; millor `status="pending_fase5"` —
  afegeix aquest estat al Literal. Fase 6 sap no mostrar alternatives llavors.

**Per-concept** (transient):
- Schema validation → retry 1 cop amb prompt retallat (només principis +
  candidats, sense glossary) — reutilitza pattern D5 de Fase 4.
- Timeout 60s (D7 pattern).
- 5xx / 429 → backoff exponencial, 3 intents.

**Circuit breaker:** 3 fallades consecutives no-systemic → aborta i marca els
pendents com `status="pending_fase5"`.

**Passada B failure:** si la crida de grup falla, Passada A ja té rankings
vàlids. La Passada C no s'executa per aquell grup, però els rankings de
Passada A es mantenen. `GroupAuditResult.failures` registra l'error.

---

## 10. Model selection

**Default:** `claude-sonnet-4-6` per totes les passades — mateixa classe
quality-cost que Fase 4. Les tres passades fan raonament (no extracció pura),
la fidelitat importa.

**Env-var upgrade paths** (consistent amb Fase 4 §7.5):
- `G3DT_AI_MODEL_RANKER=claude-opus-4-7` → ruta només les crides on
  `has_conflict=true` a Passada A per una segona opinió amb Opus. Opt-in.
- No hi ha path a gpt-4.1-mini — Fase 5 no és vision, no hi ha estalvi
  quality-cost rellevant.

---

## 11. Benchmarking (D13)

**Gate d'adopció** — Fase 5 no substitueix el ranking implícit de Fase 4 fins
que demostri paritat sobre els 7 projectes de referència.

**Mètrica principal:** top-1 accuracy — per cada concept amb ≥1 candidat i
amb un valor a `eva_reference_values.json`, el primer candidat de la Fase 5
coincideix amb el valor d'Eva?

**Target:** ≥80% top-1 accuracy abans d'adopció. Mesurat per `scripts/
ai_pipeline_ranking_benchmark.py` a crear (Passada 7 del pla d'implementació).

**Métriques secundàries:**
- Top-3 accuracy (Fase 6 mostrarà alternatives; top-3 ≥95% seria bon senyal)
- Conflict precision: si Fase 5 marca `has_conflict=true`, hi ha efectivament
  discrepància entre top-1 i el valor d'Eva? Mesura de "Eva, mira això".
- Revision effectiveness: quan Passada C canvia l'ordre, el top-1 nou és
  més sovint correcte que el de Passada A? Si no, desactivem Passada C.

**Dades:** `reference-material/*/validation/eva_reference_values.json` — ja
present per tots 7 projectes via `reference_extractor`. No calen crides LLM
noves per al benchmark.

---

## 12. Dependències

- `anthropic` (ja present) — cap dep nova
- `pydantic`, `pyyaml` — ja presents
- Cap binari nou

---

## 13. Com s'utilitzarà

- **CLI:** `scripts/ai_pipeline_ranking.py --project {id} [--save] [--json]
  [--concept {concept_id}] [--group {group}] [--no-group-pass]
  [--force]`
- **API:** `GET /api/ai-pipeline/ranking/{project}?refresh=true`
- **Wizard:** secció "Stage 5: Rànquing" sota Stage 4. Per cada concept:
  badge amb font top-1 + ring amb nombre d'alternatives + icona de
  conflicte si `has_conflict=true`. Click → drawer amb top-N + rationale
  per cada candidat + botó "Acceptar top-1" (precedent per Fase 6).
- **Python:** `from automation.ai_pipeline.ranking import rank_project`

---

## 14. Arquitectura de fitxers

```
automation/ai_pipeline/
└── ranking.py                      # Fase 5

scripts/
└── ai_pipeline_ranking.py          # CLI Fase 5
└── ai_pipeline_ranking_benchmark.py # D13 benchmark

schemas/ai_pipeline/
└── authority_principles.md         # NOU — editat per Eva / amb Eva

web/
└── api.py                          # endpoint /api/ai-pipeline/ranking/{project}

templates/validation/
└── review.html                     # secció Stage 5 dins pestanya AI Pipeline

tests/
└── test_ai_pipeline_ranking.py
```

---

## 15. Pla d'implementació (commits atòmics)

1. **Pydantic models** (`ProjectRanking`, `ConceptRanking`, `GroupAuditResult`,
   `RankedCandidate`) + loader/writer JSON. Sense LLM.
2. **Passthrough paths** — concepts amb 0 o 1 candidats. Tests amb manifest
   mocat. No LLM call.
3. **Authority principles file** — escrivim l'esquelet inicial de §4 a
   `schemas/ai_pipeline/authority_principles.md`. Validar amb Eva al final.
4. **Passada A — per-concept ranker** — una funció `_rank_concept()` amb
   mock client. Tests d'schema, retry, cache. ZERO crides reals a Anthropic
   en tests (mock obligat — feedback `feedback_no_volume_reasoning` no
   s'aplica aquí, però els tests han de ser deterministes).
5. **Cache layer per Passada A** — slug per concept, hash dels inputs,
   invalidation via principis. Test d'hit/miss.
6. **Passada B — per-group auditor** — `_audit_group()`. Construcció de
   prompt + tool. Tests. Cas especial: grup amb cap concept rankejat (tots
   single o no_candidates) → skip, no LLM call.
7. **Passada C — targeted revision** — `_revise_concept()`. Orchestració
   A→B→C. Tests del no-change guardrail (si C produeix igual, descarta).
8. **CLI** — `scripts/ai_pipeline_ranking.py` amb `--save`, `--json`,
   `--concept`, `--group`, `--no-group-pass`, `--force`. Loading `.env` com
   Fase 4.
9. **API endpoint** — `/api/ai-pipeline/ranking/{project}`. Cache-first,
   `refresh` query param.
10. **Wizard UI** — secció Stage 5 amb drawers per concept.
11. **Benchmark script** — `scripts/ai_pipeline_ranking_benchmark.py` que
    recorre els 7 reference projects, calcula top-1/top-3 accuracy,
    conflict precision, revision effectiveness. Llegeix
    `eva_reference_values.json` + `ai_ranking.json` (requereix rankings
    pre-calculats, no re-genera). Sortida: taula + `docs/benchmarks/
    fase5_ranking_{date}.md`.
12. **Doc refresh** — actualitzar `ARQUITECTURA-AI-PIPELINE.md` §9 (Fase 5 passa
    de "pendent de disseny" a "implementada"). Remoure `PLA-FASE-5-...-DISMISSED.md`.

**Gate abans d'adopció:** pas 11 mostra ≥80% top-1 accuracy sobre els 7
projectes. Si no s'arriba, analitzem fallades i potser:
- Afinem `authority_principles.md` amb Eva.
- Afegim glossary entries específiques per concepts problemàtics.
- Considerem `G3DT_AI_MODEL_RANKER=claude-opus-4-7` només per conflicts.

---

## 16. Preguntes obertes

1. **Terminologia del "candidate_id"** — dins `ProjectAnalysis` de Fase 4 els
   `Candidate`s no tenen id. Proposta: `f"{source_path}::{concept_id}::{idx}"`
   — estable i reconstruïble. Validar a la passada 1.

2. **Conflict threshold** — quan dos valors són "significativament diferents"?
   Per números: tolerància relativa 5%? Per text: igualtat exacta vs
   normalitzada (case/accents)? De moment deixar-ho al LLM; afegir
   guardrails només si el benchmark mostra soroll.

3. **Multi-value concepts** — `sondeig_layers`, `spt_tests` són llistes. El
   rànquing aquí és per un "candidat complet" (tota la llista d'una font)
   vs pot haver-hi fusió entre fonts? MVP: ranking sobre candidats
   complets; fusió és Fase 6 si cal.

4. **Passada C cost ceiling** — si un group flagueja tots els seus
   concepts per revisar (improbable però possible), Passada C podria
   doblar el cost. Afegir `max_revisions_per_group=5` com a guardrail
   defensiu?

5. **Passada B groups buits/petits** — grups com `architect` (2 concepts)
   no tenen gaire material per cross-concept auditing. Skipable per
   threshold `min_group_size=3`? O executar-los igualment ja que 13 calls
   totals són barats?

Aquestes es resoldran durant la implementació; no bloquejants per
començar.

---

## 17. Relació amb D-items

- **D4** (architect vs email sender) → absorbida: és exactament el tipus de
  raonament que el LLM ranker fa amb principis d'Eva.
- **D11** (DSL d'autoritat) → substituïda per la decisió LLM + prosa.
- **D12** (endpoint de proposta) → Fase 5 + Fase 6 junts ja ho cobreixen;
  tanquem D12 quan Fase 6 landeja.
- **D13** (benchmark) → cobert pel pas 11 d'implementació.

---

*Doc v1.0 — pendent de walkthrough amb Josep abans d'iniciar implementació.*
