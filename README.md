# G3DT - Client Overview

**Status:** PILOT CONFIRMED (January 2026 start)
**Type:** First paying customer
**Last Updated:** 2026-01-01

---

## Company Information

| Field | Value |
|-------|-------|
| **Company** | G3 Desenvolupament Territorial S.L. |
| **Industry** | Geotechnical & Environmental Engineering |
| **Website** | www.g3dt.com |
| **Location** | Els Omells de na Gaia (HQ), offices in Lleida |
| **Employees** | ~5-7 |
| **Core Service** | Informes geotècnics (geotechnical reports) |

---

## Key Contacts

| Name | Role | Contact |
|------|------|---------|
| **Silvia Albaladejo Garau** | Gerente G3DT + TüvSüd department | Awaiting email (sample materials) |
| **Eva Vázquez Marcet** | Technical Head | Awaiting email (sample materials) |

**Contact method:** Waiting for sample materials to be sent to josep@eficients.cat (expected this week Dec 2-6, 2025)

---

## Strategic Context

### TüvSüd Connection (Important)

- Silvia is gerente of BOTH G3DT AND a TüvSüd department
- TüvSüd = very large German certification company
- If G3DT pilot succeeds → TüvSüd department will want Claude Code Professional
- Eva mentioned other TüvSüd departments may follow
- **Approach:** Step-by-step. First make G3DT pilot work, then expand.

### Why This Matters

G3DT is both:
1. **First paying customer** - validation of Eficients business model
2. **Gateway to TüvSüd** - potentially much larger engagement

---

## Pilot Agreement

### Terms (Agreed Dec 2025)

| Item | Value |
|------|-------|
| **Type** | Pilot ("sensatament" - cautious start) |
| **Duration** | 4 weeks (possibly 4-6, not finalized) |
| **Price** | €1,200 for 4 weeks (€300/week) |
| **Start** | January 2026 (after winter holidays) |
| **Payment** | TBD (proposal to be sent after receiving sample materials) |

### Scope

**Primary deliverable:** Reproduce ONE sample report automatically

**Success criteria:** Report quality is "good enough" (their words)

**Technical challenges:**
1. **Standard report automation** - 80-300 page geotechnical reports
2. **Handwritten OCR** - Field reports with handwritten measurements (mostly numbers)
   - Josep warned them this is "not as advanced"
   - They want to test anyway - high value if it works (avoid retyping field data)

### What They'll Provide

- [x] Sample geotechnical reports (4 received, analyzed)
- [ ] Handwritten field reports (for OCR testing) - still pending

---

## G3DT Business Context

### What They Do

- Geotechnical studies/reports (informes geotècnics)
- Their approval enables/blocks construction and infrastructure projects
- Process:
  1. Go to field
  2. Take measurements at multiple depths
  3. Produce handwritten field reports
  4. Add external data (some from internet)
  5. Generate final reports (80 pages + 300 pages annexes)

### Pain Points (Validated Nov 12 meeting)

1. **Report time:** ~4 days per report, 30 reports/month
2. **Data entry:** Retyping handwritten field notes (error-prone, tedious)
3. **Compliance:** Data table errors = liability risk
4. **Volume:** High report volume relative to team size

---

## Sales History Summary

| Date | Event | Outcome |
|------|-------|---------|
| ~Nov 8-10 | Initial contact | Meeting scheduled |
| Nov 12 | Discovery meeting (2h) | Very positive ("wish come true" demo reaction) |
| Nov 12-20 | Follow-up attempts | WhatsApp + LinkedIn (limited response) |
| Dec 4 | Meeting with G3DT + TüvSüd | **PILOT AGREED** - €1,200/4 weeks, Jan 2026 start |

**Full sales history:** `../eficients-business-system/sales/prospects/g3dt/CONTACT-LOG.md`

---

## Progress

### Completed (Jan 7, 2026) - MVP READY

- [x] **Received 4 sample reports** (PDF + Word formats from Eva)
- [x] **Created template specification v1.5** - comprehensive analysis of report structure
- [x] **Documented decision trees** - explains WHY sections vary
- [x] **Built report automation MVP:**
  - [x] Created Jinja2 template from Rubí sample (10 variable fields)
  - [x] Built `generate_from_template.py` - working generator
  - [x] Test scripts verify output matches original styling
  - [x] Documentation complete in `templates/README.md`

### Template Variables (MVP)
```
{{ client }}           {{ expedient }}        {{ location }}
{{ data_camp_text }}   {{ data_signatura_text }}
{{ plantes }}          {{ superficie_parcela }}  {{ superficie_construida }}
{{ cte_edificacio }}   {{ cte_sol }}
```

### Next Steps

1. **Test with G3DT** - generate sample report for Eva to review
2. **Expand template** - add more variable sections:
   - [ ] DPSH test results table (for loop)
   - [ ] Geotechnical parameters
   - [ ] Conclusions section (Qa, foundation type)
3. **Await handwritten field reports** - for OCR testing
4. **Handle complex reports** - Castellar (slope stability, earth pressure)

---

## Files in This Folder

```
clients/g3dt/
├── README.md (this file)
├── analysis/
│   └── REPORT-TEMPLATE-SPEC.md   # v1.5 - Complete template specification
├── templates/                     # Report generation system
│   ├── g3dt-jinja-template.docx  # Main Jinja2 template (10 variables)
│   ├── generate_from_template.py # Report generator
│   ├── data_schema.json          # Data structure reference
│   └── README.md                 # Usage documentation
└── samples/                      # Original PDF samples
    ├── 3001621_informe.pdf       # Castellar del Vallès (49 pages)
    ├── 3001631_informe.pdf       # Rubí (46 pages)
    ├── 4001607_informe.pdf       # Linyola (48 pages)
    └── 4001612_informe.pdf       # Bell-Lloc d'Urgell (45 pages)
```

**Word samples from Eva:** `/mnt/c/claude/g3dt/mostres/docx/`

### Template Spec Highlights

The `REPORT-TEMPLATE-SPEC.md` documents:
- **Document structure** - cover, sections 1-4, annexes
- **Decision trees** - why sections vary by project
- **Typography** - fonts, colors, heading styles
- **Tables & figures** - formatting specifications
- **Variable fields** - what changes per report
- **Automation considerations** - static vs dynamic content

---

## Links to Related Files

- **Prospect research:** `eficients-business-system/sales/prospects/g3dt/`
- **Previous proposal:** `eficients-business-system/sales/prospects/g3dt/sales-pipeline/05-negotiation/PROPOSTA-G3DT-CATALA.md`
- **Company research:** `eficients-business-system/sales/prospects/companies-researched/g3dt.md`
- **Demo scripts:** `eficients-business-system/sales/prospects/g3dt/DEMO-SCRIPT-informe-geotecnic-complet.md`

---

*First paying customer. Gateway to TüvSüd. Make this pilot succeed.*
