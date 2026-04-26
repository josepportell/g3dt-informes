# Investigation — `architect_name` extraction across projects

**Data:** 2026-04-26
**Branca:** `experiment/ai-pipeline`
**Trigger:** trace tool flagged Alcoletge's `architect_name = "ALBERT SANS BONVEHI"` as `eva_reference_suspect` — Albert is the project promoter (owner), not the architect (David Graus Robinat per the plànol caixetí).
**Goal:** is the reference_extractor misaligned, or is Eva's writing convention inconsistent across projects?

---

## Verdict: **Decision C — Eva's writing convention is inconsistent**

The extractor positional alignment is working correctly. It faithfully extracts whatever fills template paragraph p060 in each project's signed informe. The issue is upstream: Eva varies her writing depending on project context (owner-built vs architect-led), and the template's three-placeholder sentence (`SR. {architect}, de l'{company}, en nom de {client}`) doesn't always get filled the same way.

The confidence-zeroing guard added in iteration 1 (`_guard_architect_client_conflation` + `_BODY_SR_PATTERN`) already detects this and lowers confidence when the body-sentence shape is suspicious. So the data is correctly flagged for human review on extraction. The remaining gap is providing the CORRECT architect name for the affected projects so the trace tool can grade the pipeline against ground truth.

---

## Per-project paragraph patterns (verbatim from signed informes)

| Project | Body paragraph (verbatim) | Pattern | architect_name_upper extracted | Actual architect |
|---|---|---|---|---|
| **Bell-Lloc** | *"Segons ens indica el sol·licitant, el SR. JORDI BOSCH NOVELL, de l'ARQUITECTURA BOSCH NOVELL, en nom de RAMON MITJANA S.L, ..."* | full template | JORDI BOSCH NOVELL ✓ | JORDI BOSCH NOVELL |
| **Alcoletge** | *"Segons ens indica el sol·licitant, el SR. ALBERT SANS BONVEHI, es vol valorar..."* | truncated (no `de l'X, en nom de Y`) | ALBERT SANS BONVEHI ✗ | David Graus Robinat (only on plànol caixetí) |
| **Rubí** | *"Segons ens indica el sol·licitant, la SRA. JOANA MARTINEZ, es vol valorar..."* | truncated, owner-architect | JOANA MARTINEZ ✓ (≡ owner) | JOANA MARTINEZ |
| **Linyola** | *"Segons ens indica el sol·licitant, BUNYESC ARQUITECTURA EFICIENT, en nom de la SRA. SÍLVIA EROLES BALAGUERÓ, ..."* | firm-led (no SR. prefix) | SÍLVIA EROLES BALAGUERÓ ✗ | BUNYESC ARQUITECTURA EFICIENT (firm) |

---

## Three classes of writing convention

1. **Standard** (Bell-Lloc): individual architect → company → client, all three slots filled cleanly.
2. **Owner-built / truncated** (Alcoletge, Rubí): only `SR./SRA. X` is given, no architect company, no separate client. In Rubí, X is both owner and architect (legitimate). In Alcoletge, X is the owner only — the architect is on the plànol caixetí instead.
3. **Firm-led** (Linyola): the architect is the firm name (no individual), the owner is the client. Eva writes `FIRM_NAME, en nom de SRA. X`, which the positional extractor mis-aligns: it grabs `SRA. X` as architect_name.

---

## Why iteration 1's guard catches Alcoletge but not Linyola

The guard fires when:
- (a) `architect_name == client_name` — owner-built case
- (b) value matches `_BODY_SR_PATTERN = r"^(?:Sr|Sra|D|Dna)\.\s+\S+"` or contains "en nom propi"

Alcoletge: pattern (b) fires → confidence zeroed. Working correctly.

Linyola: the extracted value is `SÍLVIA EROLES BALAGUERÓ` (no Sr./Sra. prefix because the prefix is on the OTHER name in the sentence). Neither (a) nor (b) fires. The pipeline silently accepts an incorrect value.

---

## Recommendations

### R1 — Manual ground-truth annotations for the 2 misaligned projects (~5 min, free)

Add `architect_name` and `architect_name_upper` to `eva_reference_values.json` for Alcoletge and Linyola via `intelligent_analysis` entries (preserved by merge):

**Alcoletge** — architect is on the `26.0049/A.01.pdf` and `26.0049/planol-1.pdf` caixetí:
- `architect_name` = "David Graus Robinat" (col·legiat 699)
- `architect_company` = "2 GRAUS PROJECTES" (or whatever the caixetí block reads)

**Linyola** — architect is the firm:
- `architect_name` = (firm name as primary architect — but the concept is for a person)
- `architect_company` = "BUNYESC ARQUITECTURA EFICIENT"
- `client_name` = "SÍLVIA EROLES BALAGUERÓ" (already in eva_reference, may need correction)

### R2 — Extend the body-sentence guard (1-line fix)

Add a third trigger to `_guard_architect_client_conflation` in `automation/reference_extractor.py`: when the extracted `architect_name` value matches the same value as `client_name` after case-normalization (already covered by trigger a), OR when the body paragraph for p060 contains `"en nom de"` AND the value extracted looks like a "Sr./Sra. X" person rather than a firm — flag as suspect.

The simpler implementation: detect when the original paragraph text contained `, en nom de ` AND `architect_name` ends with the part AFTER `en nom de`, that's the firm-led pattern → swap: `architect_name` should be what's BEFORE `en nom de`, and the current value should move to `client_name`.

This is a more complex code change — defer until there's a 3rd project showing the pattern, or land R1 (manual ground truth) and tackle R2 if/when more firm-led projects emerge.

### R3 — Add explicit rule to `authority_principles.md`

Append to the "Identificació de persones" section:

```markdown
- **Patró firm-led**: si la frase del cos diu *"X ARQUITECTURA, en nom de
  Sra/Sr Y"*, llavors X és l'arquitecte (típicament un despatx) i Y és el
  client. NO confonguis l'individu darrere de "en nom de" amb
  l'arquitecte; aquesta posició és reservada al client.
- **Patró truncat (Alcoletge / Rubí)**: si la frase del cos només dóna
  "el SR./SRA. X" sense `de l'EMPRESA` ni `en nom de Y`, X pot ser
  client i arquitecte alhora (auto-promoció: cas Rubí), o pot ser
  només client (cas Alcoletge — l'arquitecte real és al caixetí del
  plànol). En tots dos casos, **prefereix el caixetí del plànol** per
  a `architect_name`. La frase del cos només és autoritativa quan té
  el patró complet "Sr. X, de l'EMPRESA, en nom de Y".
```

The AI pipeline's Stage 4 / Stage 5 LLM will then have explicit guidance to deprioritize body-sentence extractions in favor of caixetí extractions for `architect_name`.

---

## Conclusions

1. The extractor is **not broken**. It's faithfully extracting what's in Eva's signed reports, position-by-position.

2. The data quality issue is **upstream**: Eva's writing convention varies, and the template's expected three-placeholder pattern is sometimes truncated or rearranged.

3. **Iteration 1's confidence-zeroing guard already catches Alcoletge** (Sr. X without company info → confidence 0.0). This means the trace tool's `eva_reference_suspect` classification (signal 0.50) was correct — the extractor itself flagged the issue.

4. **Linyola escapes the guard** because the misaligned value doesn't match `_BODY_SR_PATTERN`. R2 would fix this with a more sophisticated heuristic.

5. **Lowest-effort, highest-impact action**: R1 — manually add the correct architect names from the plànol caixetí to `eva_reference_values.json`. This unlocks honest measurement of the AI pipeline's `architect_name` accuracy on the next run.

6. **Land R3** to give the AI pipeline LLM explicit rules so it ranks caixetí extractions above body-sentence extractions for owner-built and firm-led projects.

---

*Investigation report — 2026-04-26.*
