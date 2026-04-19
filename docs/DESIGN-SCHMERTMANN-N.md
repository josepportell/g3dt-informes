# G.2 Design — Schmertmann-(n) correlation for φ in silty/cohesive soils

**Status:** G.2a (Crespo/Hunt helpers) and G.2c (Meyerhof helpers + `schmertmann_n_phi`
dispatcher) both shipped. Pipeline wiring still deferred until Eva confirms per-project
n (task G.3). **Update 2026-04-17 (evening):** obtained the original Schmertmann 1975
paper figures; the n-factor chart Eva's doc references **does not exist as a single
chart in the 1975 paper** — it's a Spanish-engineering shorthand for the 2-step
Schmertmann procedure. See §10 below.

**Date:** 2026-04-17
**Related:** G.2a (Crespo & Hunt helpers — shipped), G.2c (Meyerhof helpers — shipped),
G.3 (Eva email — includes the question cluster surfaced here).

---

## 1. What Eva's method says (source: `docs/SPT-CORRELACIONS-EVA.md`)

Eva uses Schmertmann (1970) to correlate SPT-N → φ for non-rock soils.
The method takes a grain-size factor **n**:

| Tipus de sòl | Factor n |
|---|---|
| Sorres lleugerament llimoses *(slightly silty sands)* | 2.5 |
| Sorres llimoses *(silty sands)* | 2.0 |
| Llims sorrencs *(sandy silts)* | 1.25 |

Eva's doc notes: *"El document inclou un gràfic de Schmertmann (no reproduïble
en text) que relaciona NSPT amb l'angle de fricció interna segons el factor n."*

**The chart itself is not transcribed.** Without it, we know:
- φ monotonically increases with N
- Higher n → higher φ for the same N (coarser → more frictional strength)
- φ is ultimately read from a curve labeled by n

We do **not** know:
- The functional form of the curves (linear? logarithmic? piecewise?)
- Whether N is raw or overburden-corrected (N₁)
- Whether n values between the table's three points interpolate smoothly

## 2. Why this matters for G3DT

T3/T2 data showed Linyola (llim argilós, Nb=22.6, Eva φ=28°) is our biggest
φ miss — CTE 4.1 gives ~36° (+28%), Crespo pure-clay table gives ~17.5° (too
low). The correct answer lives in Eva's Schmertmann-(n) curve with n ≈ 1.25
for the sandy-silt classification. Without that curve, we can't reach 28°.

## 3. Candidate approximations (all unsatisfactory)

### A. Multiplicative correction on CTE 4.1
```python
phi_n = cte_41_phi(N) * (n / 2.5)   # 2.5 = baseline
```
**Linyola test:** 33.6° × (1.25/2.5) = 16.8°. **Too low.** Rejected.

### B. Blend CTE 4.1 (granular ceiling) with Crespo (cohesive floor)
```python
weight = (n - 1.0) / (2.5 - 1.0)                  # 0 at n=1, 1 at n=2.5
phi_n = crespo(N) + weight * (cte_41(N) - crespo(N))
```
**Linyola test:** 17.5 + 0.167·(33.6 − 17.5) = 20.2°. **Still too low.** Rejected.

### C. Offset scaling on CTE 4.1
```python
# Linear reduction of φ by (2.5 - n) × penalty
phi_n = cte_41(N) - (2.5 - n) * 4.0               # penalty tuned to Linyola
```
**Linyola test:** 33.6 − (2.5 − 1.25)·4 = 28.6°. **Matches Eva**, but the 4.0
coefficient is reverse-engineered from one data point. No independent
validation; risks overfitting.

### D. Modern modified Schmertmann (Abu-Farsakh 2024, LTRC)
The 2024 LTRC study developed regression models for silty/clayey sands with
explicit fines content and moisture parameters. Gives smaller φ than original
Schmertmann. Requires inputs we don't have (%fines, moisture content).

### E. Digitize the original chart from a published reproduction
Schmertmann (1970) is reproduced in multiple geotech textbooks (Bowles,
Coduto, Das). Manual curve digitization from a scan → piecewise function.
**Cleanest technical solution, most work.**

## 4. The real blocker

Even with the right formula, we don't know **which n Eva applied to each
project**. She presumably makes that call per project based on layer
descriptions + her judgment. Our soil_type detection is binary
(granular / cohesive) — we can't reliably distinguish n=2.5 from n=2.0 from
n=1.25 without more context.

**Two paths out:**

1. **Get the chart** (via a textbook reproduction or the original 1970
   paper) AND extend soil-type detection to classify at least three
   sub-types (slightly silty sand / silty sand / sandy silt) from layer
   descriptions. Med-to-hard work; auditable.

2. **Ask Eva** which n she used on the 7 reference projects. With 7 data
   points we could validate Option C (or fit a better blend) and have
   confidence the result matches her practice. This is already in the G.3
   email queue — just add "what n did you use on each project?" to the
   existing Nb + cemented-gravel questions.

## 5. Recommendation

**Do not implement in code yet.** Path 2 (ask Eva) is cheap and blocks a
confident implementation. Once we have her answers:
- If she used the same n for all llims/silts, a single constant works
  (trivial implementation).
- If n varies by project, we need soil-subtype detection from layer
  descriptions (moderate work).
- Either way, we'll have empirical ground-truth for 7 projects to validate
  the fit.

Meanwhile, G.2a (Crespo/Hunt helpers) is shipped and available as a
reference when we do wire things in.

## 6. Concrete acceptance criteria for a future G.2b implementation

When we do implement, the result should:
- Reproduce Eva's φ within ±2° on all 5 projects where she has implicit
  φ data (Castellar, Rubí, Linyola, Bell-Lloc, Alcoletge).
- Fall back gracefully when soil type is unknown (return CTE 4.1 with a
  logged warning, not a silent default).
- Be unit-tested with one parametrized case per project matching Eva's
  known values.
- Not regress the 3 currently-MATCH projects on Qa downstream.

## 7. References followed up

- Andersen & Schjetne (2013), *"Database of Friction Angles of Sand and
  Consolidation Characteristics"*, ISSMGE — notes Schmertmann's grain-size
  trend is **not fully supported** by their larger NGI dataset. Reason for
  caution in extrapolation.
- Abu-Farsakh (2024), *"Internal Friction Angle of Sands with High Fines
  Content"*, LTRC — modified Schmertmann for silty sands. Option D above.
- Cárdenas (2025), *"On the Lookout for a General Relationship..."*,
  Springer IJG&H — best-fit aggregated model for sandy soils, ignores
  grain size.

## 8. Pointer for the G.3 email to Eva

Add these bullet points to the email draft:

> - Per cada un dels 7 projectes de referència (Castellar, Rubí, Linyola,
>   Bell-Lloc, Alcoletge, Vilanova, Anciles), quin valor del factor **n**
>   de Schmertmann has utilitzat per determinar φ?
>     - n = 2.5 (sorres lleugerament llimoses)
>     - n = 2.0 (sorres llimoses)
>     - n = 1.25 (llims sorrencs)
> - En algun projecte has fet servir un valor intermedi (p.ex. n = 1.5) o
>   un valor diferent d'aquests tres? Com decideixes?
> - Apliques el mètode de 2 passos (N → Dr → φ mitjançant les Figs. 2 i 3
>   del paper de Schmertmann 1975), o una correlació directa N→φ? (El
>   teu document `Spt-correlacions.doc` cita "Schmertmann 1970" i el
>   factor n, però el paper de 1970 és exclusivament sobre CPT, i el de
>   1975 té el mètode en 2 passos — vegeu §10 d'aquest doc per detall).
> - Per sòls cohesius (argiles i llims), apliques la correcció addicional
>   de Fig. 4 del 1975 (N vs qu, amb diferents corbes per nivell de
>   plasticitat Ip)? I si és així, quina corba per Linyola (llim argilós)?

## 9. Paper figures obtained + archived

User sourced the original 1975 paper via Scribd (paywalled viewer) and
captured the following pages between pages 63–67 of *"Measurement of In Situ
Shear Strength"* (ASCE Specialty Conf., Vol. 2, pp. 57–138, June 1975):

Archived in `docs/research/schmertmann-1975/`:

| File | Paper reference | Relevance |
|---|---|---|
| `fig1-SPT-phi-deMello1971.png` | Fig. 1, p.63 | SPT N + σ'v → φ' contours 25°–50°. Granular baseline (single family, no grain-size separation). |
| `fig2-Gibbs-Holtz-Bazaraa-Dr.png` | Fig. 2, p.64 | N + σ'v → Dr% via two criteria (Gibbs-Holtz 1957 solid, Bazaraa 1967 dashed). **Step 1 of the 2-step method.** |
| `fig3-phi-Dr-quartz-sands.png` | Fig. 3, p.65 | Dr% → φ'. **Two curves: coarse-angular-well-graded (upper) vs fine-rounded-uniform (lower)**, ~4–6° apart. **Step 2 of the 2-step method.** |
| `fig4-N-qu-clays.png` | Fig. 4, p.66 | N → qu for clays, multiple lines by plasticity: low Ip, medium Ip, high Ip, Chicago clays, Houston USBR, Terzaghi-Peck. Cohesive complement to Hunt/Crespo. |
| `fig5-6-clay-sensitivity.png` | Figs. 5–6, p.66 | N decrease with clay sensitivity (Schmertmann 1971). Narrow use. |
| `fig17-Al-Awkati-PMT.png` | Fig. 17 | Pressuremeter-test correlation. **Not SPT; different in-situ method**. |
| `table3-pile-friction-end-bearing.png` | Table 3, p.67 | Pile side-friction and end-bearing vs N by SCS soil type. Different use case. |
| `meyerhof-1957-italian-reproduction.png` | — | Published reproduction of Meyerhof 1957 + Peck-Hanson-Thornburn curves (used by G.2c). |
| `deMello-1971-nomograph.png` | — | Same deMello 1971 chart as paper Fig. 1, different reproduction. |

## 10. Revised understanding — Eva's "n-factor" is a shorthand, not a chart

After reading Figs. 1–6 of the 1975 paper, **the n-factor table in Eva's
`Spt-correlacions.doc` is not sourced from a single chart in that paper.**
Schmertmann's formal method is a 2-step procedure:

```
Step 1:  N + σ'v   → Dr      (Fig. 2: Gibbs-Holtz 1957 or Bazaraa 1967)
Step 2:  Dr + grain shape/grading → φ'   (Fig. 3: pick upper or lower curve)
```

The single-chart "Schmertmann with n = 2.5 / 2.0 / 1.25" pattern Eva uses
is a **Spanish-engineering shorthand** — the three n-values likely encode
the combined effect of (a) which Dr criterion to read in Fig. 2, and
(b) which grain-shape curve to use in Fig. 3. Eva's doc attributes it to
"Schmertmann 1970" but the 1970 paper is exclusively about CPT-based
settlement (verified — we read it in full); the actual in-situ strength
methods are in the 1975 paper.

**Test against Eva's Linyola (Nb=22.6, Eva φ=28°):**
- Step 1 (Fig. 2, shallow σ'v ≈ 1 ksf): N=22.6 → **Dr ≈ 45%**
- Step 2 (Fig. 3, fine rounded curve for llim argilós): Dr=45% → **φ ≈ 34°**
- Eva's value: **28°**
- Gap: +6°

**The strict 1975 method overshoots Linyola by 6°.** Eva must apply an
additional plasticity / cohesive correction — possibly via Fig. 4 (N-qu
for clays, with Ip-dependent curves) — that isn't captured in her doc's
transcript. Our G.2c Meyerhof-based shortcut, empirically calibrated to
28° at n=1.25, reaches Eva within ±1° — so it's **closer to her real
practice than a literal Schmertmann 1975 implementation would be**.

### Implication for G.2c wiring

The helpers we shipped in G.2c (`schmertmann_n_phi(nspt, n_factor)` +
Meyerhof curves) are **more aligned with Eva's Spanish-tradition shortcut
than the original 1975 2-step procedure**. Keep them as-is; don't try to
re-engineer to the formal Schmertmann 1975 method — that would move φ
**further** from Eva's values, not closer.

The open questions remain (in G.3):

1. What n did Eva use per-project? Validates whether Linyola's 28°
   calibration generalises.
2. Does she apply a Fig. 4 plasticity correction for Linyola, or a
   different cohesive-soil branch we haven't modelled?
3. On her Spt-correlacions.doc: is the n-factor a direct chart read, or
   encoding of "pick Gibbs-Holtz or Bazaraa + coarse or fine Fig. 3 curve"?
