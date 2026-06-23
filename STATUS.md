# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-06-23

## Estat actual

**Branca production:** `production/g3dt-eva-v1` — net, sincronitzat amb origin.

### Desplegat a Eva (2026-06-08 pull) ⏳ pendent confirmació
- Render-crash fix (`aa508c2`): filtre d'extensió + validació imatge.
- SPT refusal fix (`7be711f`): `coerce_blow_int()` evita col·lapse a 1 nivell.
- Geological-levels fix (`cbf5763` + `242228a`): agrupa per `geological_level`.

### Shippat avui (2026-06-23) — `fix/pipeline-routing`
Quatre commits (fast-forward a production):

| Commit | Contingut |
|--------|-----------|
| `b11043c` | Via A: parser OBRA per `site_address`; glob ES `PRESUPUESTO*.pdf` |
| `3c87cc6` | Via B2: visió Claude dedicada al pressupost → `pressupost_extracted.json` |
| `995783b` | Docs: DECISION-LOG + ANALISI §4.5 + artefactes JSON dels 7 projectes |
| `d964729` | Consumers: B2 → `site_municipality` (fallback) + `client_name` (fallback) |

Resultats (7 projectes): `site_address` 6/7 Via A, 7/7 B2; `municipality` 7/7 B2;
`client_name` 7/7 B2. Regressió: 32 failed / 981 passed (baseline).

## Open items (per prioritat)

1. **A2 — ACCEPTACIO folder silenciada** (1 línia, alt valor): el scanner ignora
   la carpeta `ACCEPTACIO/` → client, adreça, NIF, contacte arquitecte mai
   arriben al pipeline. `git grep acceptance_dir web/vision_fast.py`.
2. **Via A lacunes menors** (~30 min cada una):
   - `num_planned_dpsh` per PDFs ES (regex `ensayos de penetración dinámica`)
   - `building_category` apostrofació Unicode (`'` → `[''']`)
   - `num_planned_sondeig` spurious matches (Castellar/Bell-lloc)
3. **StreetView adjacents** (Eva ho ha demanat explícitament): vista de carrer
   i Google Earth per a la descripció d'adjacents.
4. **A3 — GTL report extractor**: company del laboratori acaba a `client_nif`.
5. **Linyola**: pressupost `2_02B_DG_Silvia_Jaume.pdf` (nom no-estàndard);
   `_find_pressupost_pdf` no el descobreix.

## Blockers actius
- Confirmació d'Eva del pull de 2026-06-08 (bugs 1+2+render).

## Wizard
Producció: `http://localhost:8765` a `C:\g3dt-ia` (ordinador Eva).
Dev: worktree `clients/g3dt-fix/` — `fix/pipeline-routing` merged, esborrar worktree.

## Lectura per a la propera sessió
1. `.claude/sessions/2026-06-23-1830-handoff.md` — detall de la sessió d'avui.
2. `docs/ANALISI-PIPELINE-DEBUG-VACARISSES.md §9` — accions proposades (A1–A6).
3. `docs/DECISION-LOG.md` — entrada 2026-06-23 (champion-challenger Via A vs B2).
