"""Tests de la Fase 12 — `automation/lectura/consolidate.py` (consolidacio Python-first)
i la reparacio (d) de `normalize.py` (embolcall determinista de cel·les planes).

Dos tipus de fixtures:
- sintetics (escrits aqui, a `tmp_path`): proven cada regla aïlladament;
- reals (perdoc dels runs del llibre, `docs/wizard-headless/mesures/runs/*/perdoc`, i
  els fixtures d'or): proven que la sortida passa el contracte NETA i que cap senyal
  emes es perd. Cap crida LLM, cap fitxer fora del repo/tmp.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.lectura import consolidate as C  # noqa: E402
from automation.lectura.contract import ALLOWED_FIELD_KEYS, validate_decisions  # noqa: E402
from automation.lectura.normalize import soft_normalize, wrap_flat_cells  # noqa: E402

RUNS = PROJECT_ROOT / "docs/wizard-headless/mesures/runs"
PERDOC_SETS = [p for p in sorted(RUNS.glob("*/perdoc")) if any(p.glob("*.json"))]


# ---------------------------------------------------------------------------
# Helpers sintetics
# ---------------------------------------------------------------------------


def _doc(out_dir: Path, name: str, source_path: str, doc_type: str, tier_a: list[dict], *, tables: dict | None = None,
         md5: str | None = None, not_present: list[str] | None = None, skill_version: str = "1.4",
         authority_for: list[str] | None = None) -> None:
    payload = {
        "source_path": source_path, "source_md5": md5 or f"md5-{name}", "skill_version": skill_version,
        "schema_version": 1, "document_type": doc_type, "context": {"authority_for": list(authority_for or [])},
        "tier_a": tier_a, "not_present": not_present or [],
    }
    if tables:
        payload["tables"] = tables
    (out_dir / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _ta(concept: str, value, conf: float, location: str = "p.1", quote: str = "", note: str | None = None) -> dict:
    e = {"concept_id": concept, "value": value, "location": location, "quote": quote or str(value), "confidence": conf}
    if note:
        e["note"] = note
    return e


def _g3(out_dir: Path, concepts: dict[str, list[tuple]]) -> None:
    payload = {"project": "X", "read_on": "now", "reader": "test", "documents": [],
               "concepts": {cid: [{"concept_id": cid, "value": v, "location": "N19", "quote": str(v), "confidence": c,
                                   "source": src, "document_type": dt} for (v, c, src, dt) in cands]
                            for cid, cands in concepts.items()}}
    (out_dir / "_g3_templates.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _all_signal_values(dec: dict) -> set[str]:
    """Tots els valors presents a candidates/altres/descartats de fields i tables (per a 'cap senyal perdut')."""
    out: set[str] = set()

    def walk(cell):
        if not isinstance(cell, dict):
            return
        for k in ("candidates", "altres", "descartats"):
            for c in cell.get(k) or []:
                if isinstance(c, dict) and c.get("value") is not None:
                    out.add(json.dumps(c["value"], ensure_ascii=False, sort_keys=True))
        reg = cell.get("registre")
        if isinstance(reg, dict):
            walk(reg)

    for cell in dec["fields"].values():
        walk(cell)
    for blk, val in dec["tables"].items():
        if isinstance(val, dict) and isinstance(val.get("rows"), list):
            for row in val["rows"]:
                for cell in row.values():
                    walk(cell)
        else:
            walk(val)
    for cands in (dec.get("extra_concepts") or {}).values():
        for c in cands:
            out.add(json.dumps(c.get("value"), ensure_ascii=False, sort_keys=True))
    return out


# ---------------------------------------------------------------------------
# value_key / compatibilitat
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("a,b", [
    ("2025-10-24", "24/10/2025"), ("2025-10-24", "24-10-25"), ("2025-10-24", "Octubre 2025"),
    ("4", 4), ("-4 m (respecte el carrer)", "-4,0 m"), ("570.90 msnm (segons el plànol ICGC)", "570,9"),
    ("S-1", "S1"), ("Castellar del Vallès", "CASTELLAR DEL VALLES"), ("C/ARBRELLS 18A-18B-20", "Carrer Arbrells 18A, 18B i 20"),
    ("C/ ARBRELLS 18 A", "C/ARBRELLS 18A-18B-20"), ("MA-1 (S1)", "MA1 S1"), ("PB+PP", "PB+1 (2 plantes)"),
    ("HAB UNIF CASTELLAR DEL VALLÈS", "Castellar del Vallès"), ("TPS", "TPS, Prospecció del Subsòl, SL"),
])
def test_keys_compatible(a, b):
    assert C.keys_compatible(C.value_key(a, field_name="num_floors"), C.value_key(b, field_name="num_floors"))


@pytest.mark.parametrize("a,b", [
    ("-4 m", "570.90 msnm"), ("2025-10-24", "2025-10-06"), ("1", "2"), ("carrer Antoni Bellet", "carrer Mestre Ramon Ortiz"),
    ("Situat entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz", "carrer Antoni Bellet"),
    ("WOOD COMFORT PROMOCIONS SLU", "GRUP ALMA"), ("4613172CG1141S0001SU", "4613173CG1141S0001ZU"),
])
def test_keys_incompatible(a, b):
    assert not C.keys_compatible(C.value_key(a), C.value_key(b))


def test_abs_numbers_makes_depth_signs_compatible():
    assert C.keys_compatible(C.value_key("1,0 - 1,2 m", abs_numbers=True), C.value_key("-1,00 a -1,20 m", abs_numbers=True))
    assert not C.keys_compatible(C.value_key("1,0 - 1,2 m"), C.value_key("-1,00 a -1,20 m"))


# Fix A (2026-08-31): `value_key` llegia dates amb un fragment numèric ("1.5-1.75" → 2075-01-05, `_DATE_DMY_RE.search`
# trobava "5-1.75") i no reconeixia un guió entre dígits com a separador d'interval ("0,50-1,20" es llegia amb signe).
@pytest.mark.parametrize("s,expected", [
    ("1.5-1.75", ("num", (1.5, 1.75))),
    ("1,5-1,75", ("num", (1.5, 1.75))),
    ("0,50-1,20", ("num", (0.5, 1.2))),
    ("1,20 - 1,75", ("num", (1.2, 1.75))),
    ("-1,20", ("num", (-1.2,))),
    ("2025-01-05", ("date", 2025, 1, 5)),
    ("Febrer 2026", ("date", 2026, 2, None)),
    ("7 de maig de 2025", ("date", 2025, 5, 7)),
    ("1.20 m (aprox.)", ("num", (1.2,))),
])
def test_value_key_dates_anchored_and_dash_is_interval(s, expected):
    assert C.value_key(s) == expected


def test_value_key_same_interval_regardless_of_spacing_around_dash():
    assert C.keys_compatible(C.value_key("0,50-1,20"), C.value_key("0,50 - 1,20")) is True


# ---------------------------------------------------------------------------
# decide(): regles del Pas 5
# ---------------------------------------------------------------------------


def _sig(concept, value, conf, doc="d1", doc_type="altre", origin="claude", is_a=None, note=None):
    return C.Signal(concept, value, f"{doc} p.1", str(value), conf, doc, doc_type, origin, note,
                    C._is_a(origin, conf, is_a))


def test_segur_needs_one_A_source_without_contradiction():
    cell = C.decide([_sig("expedient", "3001621", 0.9), _sig("expedient", "3001621", 0.5, doc="d2")], sources_checked=["d1"])
    assert cell["estat"] == "segur" and cell["value"] == "3001621"
    assert cell["candidates"][0]["font"].startswith("d1")


def test_B_only_sources_never_segur():
    cell = C.decide([_sig("x", "v", 0.7), _sig("x", "v", 0.7, doc="d2")], sources_checked=["d1"])
    assert cell["estat"] == "candidats"


def test_convergence_of_three_independent_docs_is_segur():
    cell = C.decide([_sig("x", "S-1", 0.75, doc="gtl"), _sig("x", "S1", 0.7, doc="comanda"), _sig("x", "S-1", 0.6, doc="annex")],
                    sources_checked=["gtl"])
    assert cell["estat"] == "segur"


def test_contradiction_from_weak_signal_blocks_segur_in_fields():
    cell = C.decide([_sig("num_soil_levels", "1", 0.85, doc="annex", doc_type="annex_sondeig"),
                     _sig("num_soil_levels", "2", 0.45, doc="manuscrit", doc_type="full_camp_manuscrit")],
                    sources_checked=["annex"], field_name="num_soil_levels")
    assert cell["estat"] == "candidats"
    assert [c["value"] for c in cell["candidates"]] == ["1", "2"]


def test_contradiction_below_threshold_does_not_block_but_is_kept_in_altres():
    cell = C.decide([_sig("client_name", "WOOD COMFORT", 0.92, doc="acceptacio"), _sig("client_name", "GRUP ALMA", 0.4, doc="correu")],
                    sources_checked=["acceptacio"], field_name="client_name")
    assert cell["estat"] == "segur"
    assert any(c["value"] == "GRUP ALMA" for c in cell["altres"])


def test_table_cell_only_A_doc_types_contradict():
    # manuscrit (no A per a cota_inici) diu una cota local; l'annex DPSH (A) mana
    sigs = [C.Signal("cota_inici", "199.50", "annex p.1", "", 0.8, "annex", "annex_dpsh", "claude", None, True),
            C.Signal("cota_inici", "-0,15", "manuscrit p.2", "", 0.3, "manuscrit", "full_camp_manuscrit", "claude", None, False)]
    cell = C.decide(sigs, sources_checked=["annex"], field_name="cota_inici", table_cell=True)
    assert cell["estat"] == "segur" and cell["value"] == "199.50"
    assert any(c["value"] == "-0,15" for c in cell["altres"])


def test_two_A_sources_different_documents_is_conflict_and_candidats():
    conflicts: list[dict] = []
    cell = C.decide([_sig("expedient", "4001612", 0.9, doc="comanda"), _sig("expedient", "4001621", 0.9, doc="annex")],
                    sources_checked=["comanda"], conflicts=conflicts, path="fields.expedient")
    assert cell["estat"] == "candidats"
    assert conflicts and conflicts[0]["path"] == "fields.expedient"


def test_two_alternatives_from_same_document_are_not_a_conflict():
    conflicts: list[dict] = []
    cell = C.decide([_sig("p", "1.80", 0.8, doc="annex"), _sig("p", "8.0", 0.8, doc="annex")],
                    sources_checked=["annex"], conflicts=conflicts, path="x")
    assert cell["estat"] == "candidats" and conflicts == []


def test_A_forms_with_different_keys_prefix_compatible_are_candidats_with_all_forms():
    cell = C.decide([_sig("street_address", "C/ARBRELLS 18A-18B-20", 0.9, doc="pressupost"),
                     _sig("street_address", "C/ ARBRELLS 18 A", 0.85, doc="annex"),
                     _sig("street_address", "Carrer Arbrells 18A, 18B i 20", 0.7, doc="correu")],
                    sources_checked=["pressupost"], field_name="street_address")
    assert cell["estat"] == "candidats"
    vals = [c["value"] for c in cell["candidates"]]
    assert vals[0] == "C/ARBRELLS 18A-18B-20"
    assert "Carrer Arbrells 18A, 18B i 20" in vals and "C/ ARBRELLS 18 A" in vals


def test_never_segur_flag_and_derived_only():
    cell = C.decide([_sig("n30", "40", 0.9)], sources_checked=["d"], never_segur=True)
    assert cell["estat"] == "candidats"
    derived = C.Signal("cte_sol", "T-1", "(coneixement previ: …)", "", 0.3, "(coneixement previ)", "derivat", "derivat")
    cell = C.decide([derived], sources_checked=["d"])
    assert cell["estat"] == "candidats" and cell["candidates"][0]["font"].startswith("(coneixement previ")


def test_no_signals_is_no_trobat_with_sources_checked():
    cell = C.decide([], sources_checked=["a.pdf", "b.pdf"])
    assert cell == {"estat": "no_trobat", "value": None, "sources_checked": ["a.pdf", "b.pdf"]}


def test_segur_date_is_canonical_iso_but_quote_keeps_original():
    cell = C.decide([_sig("field_date", "24/10/2025", 0.9, doc="fitxa"), _sig("field_date", "Octubre 2025", 0.25, doc="tall")],
                    sources_checked=["fitxa"], field_name="field_date")
    assert cell["estat"] == "segur" and cell["value"] == "2025-10-24"
    assert cell["candidates"][0]["quote"] == "24/10/2025"


# --- D2 / D3 / R3 (2026-09-05, fila 0b de la mesura dels 8) ------------------------------------------------------

def test_D2_month_only_date_does_not_bridge_two_different_days():
    """Linyola `field_date`: «Octubre 2025» (planol, 0,25) feia de pont entre 01/10 (fitxa A 0,95 + 6 docs) i 10/10
    (lab-sig 0,35, etiqueta mal aparellada) → un sol cluster «sense contradiccio», representant per `len(str)` → segur
    2025-10-10 amb la font i la cita del 01/10. Ara: segur 2025-10-01, el 10/10 queda a `altres` (conf < 0,4)."""
    sigs = [_sig("field_date", "2025-10-01", 0.95, doc="fitxa"), _sig("field_date", "01/10/2025", 0.8, doc="annex_dpsh"),
            _sig("field_date", "10/10/2025", 0.35, doc="lab-sig"), _sig("field_date", "Octubre 2025", 0.25, doc="planol")]
    cell = C.decide(sigs, sources_checked=["fitxa"], field_name="field_date")
    assert cell["estat"] == "segur" and cell["value"] == "2025-10-01"
    assert cell["candidates"][0]["value"] == "2025-10-01" and cell["candidates"][0]["font"].startswith("fitxa")
    assert "10/10/2025" in [c["value"] for c in cell["altres"]]
    clusters = C.cluster_signals(sigs, field_name="field_date")
    assert [c.key for c in clusters][:2] == [("date", 2025, 10, 1), ("date", 2025, 10, 10)]
    assert {s.value for s in clusters[0].signals} == {"2025-10-01", "01/10/2025", "Octubre 2025"}


def test_D2_month_only_date_with_A_confidence_still_blocks_a_different_day_as_contradiction():
    """Un 10/10 a 0,6 (≥ llindar 0,4) es una contradiccio real: candidats, no segur."""
    sigs = [_sig("field_date", "01/10/2025", 0.9, doc="fitxa"), _sig("field_date", "10/10/2025", 0.6, doc="lab"),
            _sig("field_date", "Octubre 2025", 0.85, doc="planol")]
    cell = C.decide(sigs, sources_checked=["fitxa"], field_name="field_date")
    assert cell["estat"] == "candidats"
    # forma amb dia primer (no «Octubre 2025» per ser A); sense ISO perque nomes es canonicalitza el `segur`
    assert cell["candidates"][0]["value"] == "01/10/2025" and cell["candidates"][0]["quote"] == "01/10/2025"
    assert [c["value"] for c in cell["candidates"]][1:] == ["10/10/2025", "Octubre 2025"]


def test_D2_month_only_dates_alone_stay_month_only_and_are_not_rewritten():
    cell = C.decide([_sig("field_date", "Octubre 2025", 0.9, doc="planol"), _sig("field_date", "octubre de 2025", 0.5, doc="tall")],
                    sources_checked=["planol"], field_name="field_date")
    assert cell["estat"] == "segur" and cell["value"] == "Octubre 2025"


def test_R3_num_floors_guard_needs_word_boundary_before_1_de_N():
    guard = C._guard_for_field("num_floors", {})
    top = C.Cluster(key=("text", "pb1"), signals=[
        _sig("num_floors", "PB+1 (2 plantes)", 0.7, doc="correu", note="PB de 280 m2 + P1 de 86 m2; citat de l'email")])
    assert guard(top) is True                                     # Bell-lloc: «P1 de 86» no es «1 de N»
    top = C.Cluster(key=("text", "pb1"), signals=[_sig("num_floors", "PB+1", 0.7, doc="pressupost", note="1 de 3 habitatges")])
    assert isinstance(guard(top), str)                            # Castellar: una unitat de N
    top = C.Cluster(key=("text", "pb1"), signals=[_sig("num_floors", "PB+1", 0.7, doc="p", note="descriu 1 dels 3 habitatges")])
    assert isinstance(guard(top), str)
    top = C.Cluster(key=("text", "pb1"), signals=[_sig("num_floors", "PB+1", 0.7, doc="p", note="una unitat del conjunt")])
    assert isinstance(guard(top), str)


def test_D3_municipality_visible_form_is_padro_official_spelling():
    """Vilanova: tres fonts A a 0,90 amb «Vilanova del Segrià» / «Vilanova de Segria» / «Vilanova de Segrià» (mateix
    cluster); `_prefer_form` triava «del» per longitud. Ara: `name_ine` del padro; la forma del document, a la cita."""
    cell = C.decide([_sig("municipality", "Vilanova del Segrià", 0.9, doc="planol"),
                     _sig("municipality", "Vilanova de Segria", 0.9, doc="acceptacio"),
                     _sig("municipality", "Vilanova de Segrià", 0.9, doc="pl_situacio"),
                     _sig("municipality", "VILANOVA SEGRIÀ", 0.7, doc="g3", origin="g3_templates")],
                    sources_checked=["planol"], field_name="municipality")
    assert cell["estat"] == "segur" and cell["value"] == "Vilanova del Segrià"
    C._canonical_municipality(cell)
    assert cell["value"] == "Vilanova de Segrià" and cell["candidates"][0]["value"] == "Vilanova de Segrià"
    assert cell["candidates"][0]["quote"] == "Vilanova del Segrià" and "D3" in cell["rule"]


def test_D3_municipality_untouched_when_a_form_is_not_in_padro_or_forms_disagree():
    cell = C.decide([_sig("municipality", "Anciles", 0.9, doc="planol")], sources_checked=["planol"], field_name="municipality")
    before = json.dumps(cell, sort_keys=True)
    C._canonical_municipality(cell)
    assert json.dumps(cell, sort_keys=True) == before          # fora de Catalunya: el padro no hi diu res
    cell = C.decide([_sig("municipality", "Linyola", 0.9, doc="a"), _sig("municipality", "Bellpuig", 0.9, doc="b")],
                    sources_checked=["a"], field_name="municipality")
    assert cell["estat"] == "candidats"
    before = json.dumps(cell, sort_keys=True)
    C._canonical_municipality(cell)
    assert json.dumps(cell, sort_keys=True) == before          # dos municipis diferents: no es tria


def test_R6_nivell_freatic_positive_non_A_signal_blocks_absence():
    """Vilanova P-3: Excel i annex DPSH (A) amb la columna N.F. buida → «No detectat»; el tall diu «Aigua» i el full de
    camp «Humit» (no-A). Abans: segur «No detectat» (nomes els A contradiuen a les taules). Ara: candidats, tall primer."""
    def absent(doc, dtype, conf, is_a):
        s = _sig("nivell_freatic", "No detectat", conf, doc=doc, doc_type=dtype, is_a=is_a)
        s.extra["absent_literal"] = None
        return s
    sigs = [absent("DPSH.xls", "dpsh_excel", 0.8, True), absent("annex_DPSH.pdf", "annex_dpsh", 0.8, True),
            _sig("nivell_freatic", "Humit", 0.3, doc="PENETROS.pdf", doc_type="camp_penetros", is_a=False),
            _sig("nivell_freatic", "Aigua", 0.3, doc="tall.pdf", doc_type="annex_tall", is_a=False)]
    cell = C.decide(sigs, sources_checked=["DPSH.xls"], field_name="nivell_freatic", table_cell=True)
    assert cell["estat"] == "segur" and cell["value"] == "No detectat"      # el que feia abans de R6
    C._nf_positive_over_absence(cell, sigs)
    assert cell["estat"] == "candidats" and cell["value"] == "Aigua" and "R6" in cell["rule"]
    assert [c["value"] for c in cell["candidates"]] == ["Aigua", "No detectat", "Humit"]
    assert cell["candidates"][0]["font"].startswith("tall.pdf")
    # absencia unanime: no es toca
    sigs = [absent("DPSH.xls", "dpsh_excel", 0.8, True), absent("tall.pdf", "annex_tall", 0.3, False)]
    cell = C.decide(sigs, sources_checked=["DPSH.xls"], field_name="nivell_freatic", table_cell=True)
    C._nf_positive_over_absence(cell, sigs)
    assert cell["estat"] == "segur" and cell["value"] == "No detectat" and "R6" not in cell["rule"]
    # positiu ja guanyador (Excel amb color, A): no es toca
    sigs = [_sig("nivell_freatic", "-1,00 m (humitat)", 0.8, doc="DPSH.xls", doc_type="dpsh_excel", is_a=True),
            absent("annex_DPSH.pdf", "annex_dpsh", 0.8, True)]
    cell = C.decide(sigs, sources_checked=["DPSH.xls"], field_name="nivell_freatic", table_cell=True)
    before = json.dumps(cell, sort_keys=True)
    C._nf_positive_over_absence(cell, sigs)
    assert json.dumps(cell, sort_keys=True) == before


# --- R1 (2026-09-05): mateixa entitat, formes diferents ------------------------------------------------------------

def test_R1_building_type_g3_abbreviations_join_the_A_reading():
    """Bell-lloc/Rubi/Linyola/Vilanova: «EG HAB UNIF <municipi>» (PLAN_COST, 0,6) i «CONSTR HAB UNIF» (comanda, 0,7)
    bloquejaven «Habitatge unifamiliar aillat» (caixeti A 0,85) a 8/8 projectes. Son la mateixa cosa, abreujada."""
    cell = C.decide([_sig("building_type", "Habitatge unifamiliar aïllat", 0.85, doc="caixeti"),
                     _sig("building_type", "EG HAB UNIF BELL-LLOC", 0.6, doc="plan_cost", origin="g3_templates"),
                     _sig("building_type", "CONSTR HABITATGE UNI", 0.7, doc="comanda", origin="g3_templates"),
                     _sig("building_type", "habitatge unifamiliar", 0.65, doc="correu")],
                    sources_checked=["caixeti"], field_name="building_type")
    assert cell["estat"] == "segur" and cell["value"] == "Habitatge unifamiliar aïllat"
    assert cell["candidates"][0]["font"].startswith("caixeti")


def test_R1_building_type_subset_does_not_bridge_two_real_alternatives():
    """«habitatge unifamiliar» (parcial) NO ha d'unir «aillat» amb «entre mitgeres»: son dues lectures diferents."""
    cell = C.decide([_sig("building_type", "Habitatge unifamiliar aïllat", 0.85, doc="caixeti"),
                     _sig("building_type", "habitatge unifamiliar entre mitgeres", 0.7, doc="correu"),
                     _sig("building_type", "HAB UNIF", 0.6, doc="comanda", origin="g3_templates")],
                    sources_checked=["caixeti"], field_name="building_type")
    assert cell["estat"] == "candidats" and cell["rule"].startswith("contradiccio")
    clusters = C.cluster_signals([_sig("building_type", "HAB UNIF", 0.9, doc="a"),
                                  _sig("building_type", "Habitatge unifamiliar aïllat", 0.85, doc="b"),
                                  _sig("building_type", "habitatge unifamiliar entre mitgeres", 0.8, doc="c")], field_name="building_type")
    assert len(clusters) == 2   # el parcial s'adjunta a un, no fa de pont


def test_R1_street_address_same_via_and_portals_is_one_key_regardless_of_suffix():
    """Linyola: tres fonts A amb el mateix portal 16 i sufixos de municipi/CP diferents → «formes diferents entre fonts
    A» → candidats. Ara: una sola clau (via + portals) → segur."""
    cell = C.decide([_sig("street_address", "C/ Clot de la Llacuna, 16, Linyola (25240)", 0.85, doc="projecte"),
                     _sig("street_address", "Clot de la Llacuna, 16, Linyola (CP 25240)", 0.85, doc="acceptacio"),
                     _sig("street_address", "C. Clot de la Llacuna, 16", 0.8, doc="punts")],
                    sources_checked=["projecte"], field_name="street_address")
    assert cell["estat"] == "segur" and cell["value"] == "C/ Clot de la Llacuna, 16, Linyola (25240)"
    # portals diferents = adreces diferents (mai equivalents a l'eix portal)
    assert not C.keys_compatible(C.value_key("Carrer Clot de la Llacuna, 16", field_name="street_address"),
                                 C.value_key("Carrer Clot de la Llacuna, 18", field_name="street_address"))


def test_R1_street_address_without_portal_is_partial_and_keeps_candidats():
    """Rubi: «C/ DE LA MIRANDA» (A, sense portal) i «Carrer de la Miranda, 39» (A): lectura parcial → candidats
    (regla «formes diferents entre fonts A» de sempre), sense conflicte A-vs-A ni pont entre portals."""
    conflicts: list[dict] = []
    cell = C.decide([_sig("street_address", "Carrer de la Miranda, 39", 0.8, doc="planol"),
                     _sig("street_address", "C/ DE LA MIRANDA", 0.8, doc="acceptacio"),
                     _sig("street_address", "Carrer de la Miranda", 0.8, doc="tall"),
                     _sig("street_address", "Carrer de la Moranda", 0.3, doc="albara")],
                    sources_checked=["planol"], field_name="street_address", conflicts=conflicts, path="x")
    assert cell["estat"] == "candidats" and "formes diferents entre fonts A" in cell["rule"] and conflicts == []
    assert cell["candidates"][0]["value"] == "Carrer de la Miranda, 39"
    clusters = C.cluster_signals([_sig("street_address", "Carrer de la Miranda, 39", 0.8, doc="a"),
                                  _sig("street_address", "Carrer de la Miranda", 0.8, doc="b"),
                                  _sig("street_address", "Carrer de la Miranda, 41", 0.8, doc="c")], field_name="street_address")
    assert len(clusters) == 2   # el sense portal s'adjunta al 39, no uneix 39 amb 41


def test_R1_legal_form_suffix_and_lab_point_are_equivalent_forms():
    cell = C.decide([_sig("lab_testing_company", "TPS, Prospecció del Subsòl, SL (NIF B64803075)", 0.9, doc="gtl"),
                     _sig("lab_testing_company", "TPS, S.L.", 0.6, doc="annex_sondeig")],
                    sources_checked=["gtl"], field_name="lab_testing_company")
    assert cell["estat"] == "segur" and cell["value"].startswith("TPS, Prospecció")
    cell = C.decide([_sig("client_name", "Grupo Cuenca Guerrero SL", 0.85, doc="acceptacio"),
                     _sig("client_name", "Grupo Cuenca Guerrero SL.", 0.85, doc="pressupost"),
                     _sig("client_name", "Grupo CUENCA GUERRERO", 0.85, doc="caixeti")],
                    sources_checked=["acceptacio"], field_name="client_name")
    assert cell["estat"] == "segur" and cell["value"].startswith("Grupo Cuenca Guerrero SL")
    cell = C.decide([_sig("lab_location", "P-3", 0.9, doc="gtl"), _sig("lab_location", "SPT1 P3", 0.75, doc="lab-sig"),
                     _sig("lab_location", "P3", 0.7, doc="comanda", origin="g3_templates")],
                    sources_checked=["gtl"], field_name="lab_location")
    assert cell["estat"] == "segur" and cell["value"] == "P-3"
    # Linyola real: cap font A, convergencia de 3 docs a 0,7-0,75 → segur; la forma visible es la canonica «P-3»,
    # no la mes llarga («SPT1 P3»); la cita conserva l'original
    cell = C.decide([_sig("lab_location", "SPT1 P3", 0.75, doc="lab-sig"), _sig("lab_location", "P-3", 0.75, doc="gtl"),
                     _sig("lab_location", "P3", 0.7, doc="comanda", origin="g3_templates")],
                    sources_checked=["gtl"], field_name="lab_location")
    assert cell["estat"] == "segur" and cell["value"] == "P-3" and cell["candidates"][0]["value"] == "P-3"
    assert cell["candidates"][0]["quote"] == "SPT1 P3"
    assert not C.keys_compatible(C.value_key("P-3", field_name="lab_location"), C.value_key("S-2", field_name="lab_location"))
    assert not C.keys_compatible(C.value_key("WOOD COMFORT SLU", field_name="client_name"), C.value_key("GRUP ALMA SL", field_name="client_name"))


# --- D5 (2026-09-05): CTE amb la superficie del conjunt quan l'edificacio es adossada ------------------------------

def _sc_cell(*totals):
    cands = [{"value": v, "font": f} for v, f in totals]
    return {"estat": "candidats", "value": totals[0][0], "candidates": cands[:3], "altres": cands[3:]}


def test_D5_attached_dwellings_derive_cte_from_project_total():
    """Anciles: 7 adossats; la taula de superficie te 7 tipologies (169-199 m²) primer i el total d'IV_PLANOS
    (1.165,84 m²) al final → abans C0 (186 m²), l'or i el signat diuen C-1 (1.264 m² > 300)."""
    sc = _sc_cell((186.18, "A01_TIPOL p.1"), (187.37, "A01_TIPOL p.2"), (169.5, "A01_TIPOL p.3"), (1165.84, "IV_PLANOS resum"))
    decided = {"building_type": {"estat": "candidats", "value": "vivienda adosada (7 unitats)",
                                 "candidates": [{"value": "vivienda adosada (7 unitats)"}, {"value": "7 adosados (residencial), PB+1PP+BC"}]}}
    sigs = C.derived_field_signals("cte_edificacio", decided, sc)
    assert len(sigs) == 1 and sigs[0].value == "C1" and "D5" in (sigs[0].note or "") and "1165.84" in sigs[0].font
    # sense cap total del conjunt a la carpeta: N unitats × tipologia
    sc = _sc_cell((186.18, "A01_TIPOL p.1"), (187.37, "A01_TIPOL p.2"))
    sigs = C.derived_field_signals("cte_edificacio", decided, sc)
    assert sigs[0].value == "C1" and "7 unitats × 186.18" in (sigs[0].note or "")


def test_D5_detached_dwellings_keep_per_unit_surface():
    """Castellar: 3 habitatges aillats de 120 m² son 3 edificis → C0 per unitat (com l'Eva)."""
    sc = _sc_cell((120, "correu"), (360, "suma de 3"))
    decided = {"building_type": {"estat": "segur", "value": "habitatges unifamiliars aïllats (grup de 3)",
                                 "candidates": [{"value": "habitatges unifamiliars aïllats (grup de 3)"}]}}
    sigs = C.derived_field_signals("cte_edificacio", decided, sc)
    assert sigs[0].value == "C0" and "D5" not in (sigs[0].note or "")
    assert C.derived_field_signals("cte_edificacio", {}, None) == []


# ---------------------------------------------------------------------------
# R5 (2026-09-05, mesura dels 8): autoritat de camp — «font unica del proveidor» (19 cel·les en CAND, 8 escalars)
# ---------------------------------------------------------------------------


def _decl(concept, value, conf, doc="d1", doc_type="correu", font=None):
    """Senyal que el lector ha marcat a `context.authority_for` del document (R5)."""
    s = _sig(concept, value, conf, doc=doc, doc_type=doc_type)
    s.declares = True
    if font:
        s.font = font
    return s


def test_R5_provider_declaration_is_field_authority_only_when_declared_and_confident():
    """Linyola: la RC impresa al projecte de l'arquitecte (0,6, `authority_for`) → segur (l'or: «el projecte mana»).
    Sense `authority_for`, o amb la confianca per sota de 0,5 (el lector mateix dubta: Castellar/Vilanova «informacio
    verbal», Rubi «derivat estructuralment» d'una foto de cataleg), es queda en candidats."""
    guard = C._guard_for_field("referencia_catastral", {})
    cell = C.decide([_decl("referencia_catastral", "5098344CG2159N0000US", 0.6, doc="projecte", doc_type="projecte_arquitecte")],
                    sources_checked=["projecte"], field_name="referencia_catastral", segur_requires=guard)
    assert cell["estat"] == "segur" and cell["rule"].startswith("autoritat de camp (R5): projecte_arquitecte")
    undeclared = C.decide([_sig("referencia_catastral", "5098344CG2159N0000US", 0.6, doc="projecte", doc_type="projecte_arquitecte")],
                          sources_checked=["projecte"], field_name="referencia_catastral", segur_requires=guard)
    assert undeclared["estat"] == "candidats"
    doubtful = C.decide([_decl("num_floors", "PB+1", 0.4, doc="correu")], sources_checked=["correu"], field_name="num_floors")
    assert doubtful["estat"] == "candidats"
    declared = C.decide([_decl("num_floors", "PB+1", 0.6, doc="correu")], sources_checked=["correu"], field_name="num_floors")
    assert declared["estat"] == "segur"
    # un tipus de document que no declara el camp (albara TPS, fitxa) no hi entra encara que el lector ho marqui
    other = C.decide([_decl("num_floors", "PB+1", 0.7, doc="albara", doc_type="full_camp_manuscrit")],
                     sources_checked=["albara"], field_name="num_floors")
    assert other["estat"] == "candidats"


def test_R5_declared_rc_must_be_complete_poligon_parcela_or_map_fragment_never_segur():
    """Rubi: «Poligon 6, Parcel·la 105-B» (annex, 0,85 = A) no es una referencia cadastral; Alcoletge: el fragment
    «98417» d'un mapa tampoc. Anciles: la RC sencera del correu d'encarrec (0,85) sense consulta del Cadastre → segur
    (or: «regla Alcoletge»); el fragment «61845» al costat no la contradiu (conf 0,2)."""
    guard = C._guard_for_field("referencia_catastral", {})
    rubi = C.decide([_sig("referencia_catastral", "Polígon 6, Parcel·la 105-B", 0.85, doc="pl_situ", doc_type="annex_planol_situacio")],
                    sources_checked=["pl_situ"], field_name="referencia_catastral", segur_requires=guard)
    assert rubi["estat"] == "candidats" and "forma de referencia completa" in rubi["rule"]
    frag = C.decide([_decl("referencia_catastral", "98417", 0.9, doc="planol", doc_type="planol")],
                    sources_checked=["planol"], field_name="referencia_catastral", segur_requires=guard)
    assert frag["estat"] == "candidats"
    anciles = C.decide([_sig("referencia_catastral", "6184504BH9158N0000SS", 0.85, doc="correu", doc_type="correu"),
                        _sig("referencia_catastral", "61845", 0.2, doc="pl_situ", doc_type="annex_planol_situacio")],
                       sources_checked=["correu"], field_name="referencia_catastral", segur_requires=guard)
    assert anciles["estat"] == "segur" and anciles["value"] == "6184504BH9158N0000SS"


def test_R5_parcela_guard_counts_complete_cadastral_references_only():
    """Anciles: RC sencera + fragment «61845» d'un mapa = UNA parcel·la → la superficie del projecte (A) es segur;
    Bell-lloc: dues RC senceres = dues parcel·les → candidats (regla Pas 3 de sempre). Els «…N+…N+…N» del Cadastre
    compten com a tres."""
    guard_one = C._guard_for_field("superficie_parcela", {"referencia_catastral": {"candidates": [
        {"value": "6184504BH9158N0000SS"}, {"value": "61845"}]}})
    one = C.decide([_sig("superficie_parcela", "1655.01 m²", 0.8, doc="iv_planos", doc_type="projecte_arquitecte")],
                   sources_checked=["iv_planos"], field_name="superficie_parcela", segur_requires=guard_one)
    assert one["estat"] == "segur"
    guard_two = C._guard_for_field("superficie_parcela", {"referencia_catastral": {"candidates": [
        {"value": "4613172CG1141S0001SU (núm. 15)"}, {"value": "4613173CG1141S0001ZU"}]}})
    two = C.decide([_sig("superficie_parcela", "995,00 m2", 0.85, doc="a01", doc_type="planol")],
                   sources_checked=["a01"], field_name="superficie_parcela", segur_requires=guard_two)
    assert two["estat"] == "candidats" and "2+ referencies" in two["rule"]
    assert C._rc_parcels(["3298012DG2039N+3298013DG2039N+3298014DG2039N"]) == {"3298012DG2039N", "3298013DG2039N", "3298014DG2039N"}
    assert C._rc_parcels(["25120A002000340000XX"]) == {"25120A00200034"}   # rustica


def test_R5_num_soil_levels_needs_two_eva_syntheses_tall_and_annex_sondeig():
    """Bell-lloc: tall 0,75 + tall annex 0,70 + annex sondeig 0,55, tots «1», cap contradiccio: cap arriba a 0,8
    perque cada lector diu «creuar amb l'altre». Els dos TIPUS (tall + sondeig) coincidint = segur. Dos talls sols
    (el mateix dibuix imprès dues vegades) no en son dos."""
    guard = C._guard_for_field("num_soil_levels", {})
    both = C.decide([_decl("num_soil_levels", 1, 0.75, doc="tall.pdf", doc_type="annex_tall"),
                     _decl("num_soil_levels", 1, 0.7, doc="PDF/ANNEXES/tall.pdf", doc_type="annex_tall"),
                     _decl("num_soil_levels", "1", 0.55, doc="PDF/ANNEXES/sondeig.pdf", doc_type="annex_sondeig"),
                     _sig("num_soil_levels", 1, 0.3, doc="DPSH.xls", doc_type="dpsh_excel")],
                    sources_checked=["tall.pdf"], field_name="num_soil_levels", segur_requires=guard)
    assert both["estat"] == "segur" and both["value"] == 1 and "annex_sondeig + annex_tall" in both["rule"]
    tall_only = C.decide([_decl("num_soil_levels", 1, 0.75, doc="tall.pdf", doc_type="annex_tall"),
                          _decl("num_soil_levels", 1, 0.7, doc="PDF/ANNEXES/tall.pdf", doc_type="annex_tall")],
                         sources_checked=["tall.pdf"], field_name="num_soil_levels", segur_requires=guard)
    assert tall_only["estat"] == "candidats"


def test_R5_two_declared_rcs_stay_candidats_without_llm_conflict():
    """Bell-lloc: el correu d'encarrec porta DUES RC (dues parcel·les), totes dues declarades a 0,6: contradiccio
    → candidats, i cap conflicte A-vs-A (una declaracio a 0,6 no ha de disparar la passada LLM)."""
    conflicts: list[dict] = []
    cell = C.decide([_decl("referencia_catastral", "4613173CG1141S0001ZU", 0.6, doc="correu"),
                     _decl("referencia_catastral", "4613172CG1141S0001SU", 0.6, doc="correu")],
                    sources_checked=["correu"], field_name="referencia_catastral", conflicts=conflicts,
                    path="fields.referencia_catastral", segur_requires=C._guard_for_field("referencia_catastral", {}))
    assert cell["estat"] == "candidats" and cell["rule"].startswith("contradiccio") and conflicts == []


def test_R5_client_name_p5_form_is_authority_and_its_form_is_the_visible_value():
    """Rubi/Anciles: el formulari p.5 («DADES QUE HAN DE CONSTAR EN LA FACTURA I EN L'INFORME») llegit a 0,75 (foto
    WhatsApp; castella) es autoritat A pel skill. La seva forma es la visible, no la de la fitxa amb el telefon
    enganxat (L3). El bloc CLIENT de la p.1 del mateix pressupost NO declara el client (sol·licitant, Pas 3)."""
    p5 = _decl("client_name", "Maria Alba Barrau Castán", 0.75, doc="pressupost", doc_type="pressupost_g3",
               font="ACCEPTACIO/PRESUPUESTO.pdf p.5 bloc 'DATOS QUE HAN DE CONSTAR EN LA FACTURA Y EN EL INFORME'")
    fitxa = _sig("client_name", "MARIA ALBA BARRAU CASTÁN 616523792", 0.3, doc="fitxa", doc_type="fitxa_camp_g3", origin="g3_templates")
    cell = C.decide([fitxa, p5], sources_checked=["pressupost"], field_name="client_name",
                    segur_requires=C._guard_for_field("client_name", {}))
    assert cell["estat"] == "segur" and cell["value"] == "Maria Alba Barrau Castán"
    assert cell["candidates"][0]["font"].startswith("ACCEPTACIO/PRESUPUESTO.pdf p.5")
    p1 = _decl("client_name", "RETRATERIA, ALBA BARRAU, ARQUITECTA", 0.7, doc="pressupost", doc_type="pressupost_g3",
               font="PRESUPUESTO.pdf p.1 bloc CLIENT")
    cell = C.decide([p1], sources_checked=["pressupost"], field_name="client_name", segur_requires=C._guard_for_field("client_name", {}))
    assert cell["estat"] == "candidats"


def test_R5_authority_for_from_the_document_context_reaches_the_consolidator(tmp_path: Path):
    """El cablatge: `context.authority_for` del `{doc}.json` → `Signal.declares`. Linyola en miniatura: projecte de
    l'arquitecte a 0,6/0,75 amb `authority_for` → RC i superficie segur. Un document V0 mai declara (I1): un
    annex de sondeig V0 no fa de segon tipus per als nivells."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "projecte", "25.0616/2_02B.pdf", "projecte_arquitecte",
         [_ta("referencia_catastral", "5098344CG2159N0000US", 0.6), _ta("superficie_parcela", "571 m²", 0.75)],
         authority_for=["referencia_catastral", "superficie_parcela"])
    dec = C.consolidate_python(out, None, project_name="X")
    assert dec["fields"]["referencia_catastral"]["estat"] == "segur"
    assert dec["fields"]["superficie_parcela"]["estat"] == "segur"
    _doc(out, "v0", "PDF_V0/ANEJOS/x_sondeos.pdf", "annex_sondeig", [_ta("num_soil_levels", "3", 0.9)], authority_for=["num_soil_levels"])
    _doc(out, "tall", "tall.pdf", "annex_tall", [_ta("num_soil_levels", "3", 0.7)], authority_for=["num_soil_levels"])
    dec = C.consolidate_python(out, None, project_name="X")
    assert dec["fields"]["num_soil_levels"]["estat"] == "candidats"


# ---------------------------------------------------------------------------
# R2 (2026-09-05, mesura dels 8): «un concepte vei entra com a bloquejador» — cota, data de camp, msnm → fondaria
# ---------------------------------------------------------------------------


def test_R2_gps_z_and_relative_datum_do_not_block_the_annex_cota():
    """Bell-lloc: annex sondeig «199,50 m» (A) + annex DPSH «+199,50 msnm segons el planol topografic ICGC» (0,75, mateix
    valor, forma diferent) eren dos clusters, i la z GPS 198,9 (0,5) i el datum relatiu del full de camp (0,6) bloquejaven.
    Ara: mateixa clau numerica, i nomes els annexos contradiuen → segur; GPS i datum a `altres`."""
    assert C.value_key("+199,50 msnm segons el plànol topogràfic ICGC (-0,15 carrer)", field_name="cota_referencia") == \
        C.value_key("199,50 m", field_name="cota_referencia") == ("num", (199.5,))
    cell = C.decide([_sig("cota_referencia", "199,50 m", 0.85, doc="sondeig", doc_type="annex_sondeig"),
                     _sig("cota_referencia", "+199,50 msnm segons el plànol topogràfic ICGC (-0,15 carrer)", 0.75, doc="dpsh", doc_type="annex_dpsh"),
                     _sig("cota_referencia", "+/-0,00 respecte C/Antoni Bellet (cota relativa)", 0.6, doc="SONDEIG.pdf", doc_type="full_camp_manuscrit"),
                     C.Signal("cota_referencia", "198.9", "COORDENADES.txt (P-1 z)", "", 0.5, "COORDENADES.txt", "coordenades_gps", "python")],
                    sources_checked=["sondeig"], field_name="cota_referencia")
    assert cell["estat"] == "segur" and cell["value"] == "199,50 m"
    assert {str(c["value"])[:5] for c in cell["altres"]} >= {"198.9", "+/-0,"}
    # Rubi: dues capçaleres de l'annex DPSH discrepen (+212,50 vs +212): l'annex SI que contradiu → candidats (F1, no R2)
    rubi = C.decide([_sig("cota_referencia", "+212,50 msnm", 0.75, doc="dpsh", doc_type="annex_dpsh"),
                     _sig("cota_referencia", "+212 msnm", 0.7, doc="dpsh", doc_type="annex_dpsh")],
                    sources_checked=["dpsh"], field_name="cota_referencia")
    assert rubi["estat"] == "candidats" and rubi["rule"].startswith("contradiccio")


def test_R2_second_field_day_from_campaign_documents_is_a_candidate_not_a_contradiction():
    """Bell-lloc: DPSH l'1/10 (fitxa F38 = A) i sondeig el 6/10 (comanda DATA DE PRESA 0,7, annex sondeig 0,5). Regla
    d'Eva: «si la data del sondeig no es igual, posar els dos dies» → segur el primer dia, l'altre dia com a candidat
    anotat i a `extra.dies_de_camp`. Una data d'un document que NO es de la campanya, o massa lluny, continua bloquejant."""
    cell = C.decide([_sig("field_date", "2025-10-01", 0.95, doc="fitxa", doc_type="fitxa_camp_g3", origin="g3_templates"),
                     _sig("field_date", "2025-10-06", 0.7, doc="comanda", doc_type="comanda_lab_g3", origin="g3_templates"),
                     _sig("field_date", "6/10/2025", 0.5, doc="sondeig", doc_type="annex_sondeig")],
                    sources_checked=["fitxa"], field_name="field_date")
    assert cell["estat"] == "segur" and cell["value"] == "2025-10-01"
    assert cell["extra"] == {"dies_de_camp": ["2025-10-01", "2025-10-06"]}
    assert any(c["value"] == "2025-10-06" and "altre dia de camp" in c.get("note", "") for c in cell["candidates"])
    assert "campanya de 2 dies" in cell["rule"]
    planol = C.decide([_sig("field_date", "2025-10-01", 0.95, doc="fitxa", doc_type="fitxa_camp_g3", origin="g3_templates"),
                       _sig("field_date", "2025-10-06", 0.5, doc="planol", doc_type="planol")],
                      sources_checked=["fitxa"], field_name="field_date")
    assert planol["estat"] == "candidats"
    far = C.decide([_sig("field_date", "2025-10-01", 0.95, doc="fitxa", doc_type="fitxa_camp_g3", origin="g3_templates"),
                    _sig("field_date", "2025-12-15", 0.5, doc="sondeig", doc_type="annex_sondeig")],
                   sources_checked=["fitxa"], field_name="field_date")
    assert far["estat"] == "candidats"


def test_R2_relative_dpsh_system_keeps_the_absolute_cota_in_candidats(tmp_path: Path):
    """Castellar: annex sondeig «570,90 msnm» (A, sola) seria segur, pero l'annex DPSH treballa «respecte el carrer»
    (-4,0): dues sortides de l'Eva amb sistemes diferents → candidats [absoluta, relativa] (or; el signat va usar -4,0).
    Amb l'annex DPSH en absolut, no es toca res."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "sondeig", "PDF/ANNEXES/x_sondeig.pdf", "annex_sondeig", [_ta("cota_referencia", "570,90 msnm (segons el plànol ICGC)", 0.9)])
    _doc(out, "dpsh", "PDF/ANNEXES/x_DPSH.pdf", "annex_dpsh", [], tables={"dpsh_tests": [
        {"punt": "P-1", "cota_inici": "-4,0 m (respecte el carrer)", "profunditat_assolida": "-1,35 m", "rebuig": "Si", "nivell_freatic": None, "location": "p.1", "quote": "Cota inici: -4 m"}]})
    dec = C.consolidate_python(out, None, project_name="X")
    c = dec["fields"]["cota_referencia"]
    assert c["estat"] == "candidats" and c["value"].startswith("570,90") and "sistema relatiu" in c["candidates"][1]["value"]
    assert validate_decisions(dec) == []
    _doc(out, "dpsh", "PDF/ANNEXES/x_DPSH.pdf", "annex_dpsh", [], tables={"dpsh_tests": [
        {"punt": "P-1", "cota_inici": "+570,90 msnm", "profunditat_assolida": "-1,35 m", "rebuig": "Si", "nivell_freatic": None, "location": "p.1", "quote": ""}]})
    dec = C.consolidate_python(out, None, project_name="X")
    assert dec["fields"]["cota_referencia"]["estat"] == "segur"


def test_R2_msnm_levels_and_water_table_are_converted_to_depth_with_the_secure_cota(tmp_path: Path):
    """Linyola/Alcoletge: el lector copia l'escala msnm del tall («≈243,6 msnm a P-1/P-3; ≈244,6-244,7 msnm a P-2»);
    l'informe vol fondaries. Amb la cota de referencia segura (+245) es converteix: un candidat per punt, la lectura
    original a la nota. Sense cota segura, no es toca res; les fondaries («-1,80») tampoc."""
    assert C._depth_candidates("245 msnm (superfície, escala del tall)", 245.0, "+245") == \
        [("0,0 m (superfície, escala del tall) (cota 245 msnm)", "245")]
    assert [v for v, _ in C._depth_candidates("≈243,6 msnm a P-1/P-3; ≈244,6-244,7 msnm a P-2 (contacte)", 245.0, "+245")] == \
        ["≈-1,4 m a P-1 (contacte ≈243,6 msnm)", "≈-1,4 m a P-3 (contacte ≈243,6 msnm)", "≈-0,4/-0,3 m a P-2 (contacte ≈244,6-244,7 msnm)"]
    assert C._depth_candidates("~187,2 msnm (matís: humitat)", 188.2, "+188,20")[0][0].startswith("~-1,0 m (matís: humitat)")
    assert C._depth_candidates("-1,80", 245.0, "+245") == [] and C._depth_candidates("0,00", 245.0, "+245") == []
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "dpsh", "PDF/ANNEXES/x_DPSH.pdf", "annex_dpsh", [_ta("cota_referencia", "+245 msnm segons plànol topogràfic del ICGC", 0.85)],
         tables={"dpsh_tests": [{"punt": "P-1", "cota_inici": "+245 msnm", "profunditat_assolida": "-2,90 m", "rebuig": "Si",
                                 "nivell_freatic": "~244,0 msnm (humitat)", "matis": "humitat", "location": "p.1", "quote": ""}]})
    _doc(out, "tall", "tall.pdf", "annex_tall", [], tables={"soil_levels": [
        {"nom": "Nivell 1", "litologia": "Llims", "de": "245 msnm (superfície, escala del tall)", "a": "≈243,6 msnm a P-1/P-3; ≈244,6-244,7 msnm a P-2", "mostra_del_nivell": None},
        {"nom": "Nivell 2", "litologia": "Lutites", "de": "≈243,6 a ≈244,7 msnm segons el punt", "a": None, "mostra_del_nivell": None}]})
    dec = C.consolidate_python(out, None, project_name="X")
    assert dec["fields"]["cota_referencia"]["estat"] == "segur"
    rows = dec["tables"]["soil_levels"]["rows"]
    a0 = rows[0]["a"]
    assert a0["value"] == "≈-1,4 m a P-1 (contacte ≈243,6 msnm)" and len(a0["candidates"]) == 3
    assert a0["candidates"][0]["font"].startswith("(derivat: fondaria = cota +245 − 243,6 msnm)") and "msnm" in a0["candidates"][0]["note"]
    assert rows[0]["de"]["value"].startswith("0,0 m") and rows[1]["de"]["value"].startswith("≈-1,4 m a ≈-0,3 m")
    nf = dec["tables"]["dpsh_tests"]["rows"][0]["nivell_freatic"]
    assert nf["value"].startswith("~-1,0 m") and nf["matis"] == "humitat"
    assert validate_decisions(dec) == []
    # sense cota segura (dues cotes que discrepen als annexos) no es converteix res
    _doc(out, "dpsh2", "PDF/ANNEXES/y_DPSH.pdf", "annex_dpsh", [_ta("cota_referencia", "+247 msnm", 0.8)])
    dec = C.consolidate_python(out, None, project_name="X")
    assert dec["fields"]["cota_referencia"]["estat"] == "candidats"
    assert dec["tables"]["soil_levels"]["rows"][0]["a"]["value"].startswith("≈243,6 msnm")


def test_I1_v0_documents_propose_but_never_rule_nor_contradict(tmp_path: Path):
    """Anciles: sense `PDF/`, l'inventari llegeix `PDF_V0/ANEJOS/*.pdf`. A la V0 les graves eren NIVEL 1; al signat son
    el 2n nivell. Un senyal de V0: mai A, confianca sota el llindar de contradiccio, nota «versio anterior»."""
    out = tmp_path / "out"; out.mkdir()
    _doc(out, "v0_sondeos", "PDF_V0/ANEJOS/4001679_sondeos.pdf", "annex_sondeig",
         [_ta("num_soil_levels", 1, 0.9), _ta("cota_referencia", "+1106,42 msnm", 0.9)],
         tables={"soil_levels": [{"nom": "1er nivell", "mostra_del_nivell": True, "de": "0,00", "confidence": 0.9}]})
    _doc(out, "tall", "tall.pdf", "annex_tall", [_ta("num_soil_levels", 2, 0.85)])   # A: la V0 (0,9 → 0,39) no la contradiu
    d = C.consolidate_python(out, project_path=None)
    f = d["fields"]
    assert f["num_soil_levels"]["estat"] == "segur" and f["num_soil_levels"]["value"] == 2   # la V0 no contradiu
    assert f["cota_referencia"]["estat"] == "candidats" and f["cota_referencia"]["value"] == "+1106,42 msnm"   # proposa, mai segur
    assert C._V0_NOTE in (f["cota_referencia"]["candidates"][0].get("note") or "")
    rows = d["tables"]["soil_levels"]["rows"]
    cell = rows[0]["mostra_del_nivell"]
    assert cell["estat"] == "candidats" and cell["value"] is True and C._V0_NOTE in (cell["candidates"][0].get("note") or "")
    assert not C._is_v0_source("PDF/ANNEXES/4001612_DPSH.pdf") and C._is_v0_source("PDF V0/ANEJOS/x.pdf")


def test_candidates_capped_at_three_rest_in_altres_nothing_lost():
    sigs = [_sig("x", f"v{i}", 0.5, doc=f"d{i}") for i in range(6)]
    cell = C.decide(sigs, sources_checked=["d"])
    assert len(cell["candidates"]) == 3
    got = {c["value"] for c in cell["candidates"]} | {c["value"] for c in cell["altres"]}
    assert got == {f"v{i}" for i in range(6)}


# ---------------------------------------------------------------------------
# consolidate_python sobre un projecte sintetic
# ---------------------------------------------------------------------------


@pytest.fixture
def synth(tmp_path: Path) -> tuple[Path, Path]:
    proj = tmp_path / "3009999 SINTETIC"
    (proj / "ANNEXES" / "ALTRES").mkdir(parents=True)
    (proj / "ANNEXES" / "ALTRES" / "COORDENADES.txt").write_text(
        "Coordenades UTM (X);(Y);(Z);\nP-1\n300000.0 ; 4600000.0 ; 250.5\n\nS-1\n300010.0 ; 4600010.0 ; 250.0\n", encoding="utf-8")
    out = proj / "validation" / "lectura"
    out.mkdir(parents=True)
    _g3(out, {
        "expedient": [("3009999", 0.95, "comanda.xls", "comanda_lab_g3")],
        "municipality": [("VILA", 0.9, "comanda.xls", "comanda_lab_g3"), ("VILA", 0.85, "pressupost.pdf", "pressupost_g3")],
        "client_name": [("ARQUITECTURA X", 0.3, "pressupost.pdf", "pressupost_g3")],
        "num_dpsh_tests": [(2, 0.95, "ANNEXES/DPSH.xls", "dpsh_excel")],
        "lab_location": [("S1", 0.7, "comanda.xls", "comanda_lab_g3")],
    })
    _doc(out, "planol", "A.01.pdf", "planol", [
        _ta("client_name", "PROMOTOR SL", 0.95, "caixetí Promotor"), _ta("architect_name", "Nom Cognom", 0.95, "caixetí"),
        _ta("architect_company", "Despatx SLP", 0.6), _ta("num_floors", "PB+1", 0.85), _ta("superficie_parcela", "500 m2", 0.85),
        _ta("referencia_catastral", "1234567CG1234S0001XX", 0.6, note="impresa al plànol"),
    ], not_present=["field_date"])
    _doc(out, "annex_dpsh", "PDF/ANNEXES/3009999_DPSH.pdf", "annex_dpsh", [
        _ta("expedient", "3009999", 0.9), _ta("field_date", "01/10/2025", 0.8), _ta("cota_referencia", "+250,00 msnm", 0.85),
        _ta("utm_x_utm_y", "300010.0 E(x) / 4600010.0 N(y)", 0.6),
    ], tables={"dpsh_tests": [
        {"punt": "P-1", "cota_inici": "+250,00 msnm", "profunditat_assolida": "-1,35 m", "rebuig": "Si", "nivell_freatic": None, "location": "p.1", "quote": "Rebuig a -1,35 m"},
        {"punt": "P-2", "cota_inici": "+250,00 msnm", "profunditat_assolida": "-2,45 m", "rebuig": "Si", "nivell_freatic": "no consta (columna buida)", "location": "p.2", "quote": "Rebuig a -2,45 m"},
    ]})
    _doc(out, "excel", "ANNEXES/DPSH.xls", "dpsh_excel", [_ta("num_dpsh_tests", 2, 0.9)], tables={"dpsh_tests": [
        {"punt": "P-1", "cota_inici": None, "profunditat_assolida": "-1.35", "rebuig": "Si", "nivell_freatic": None, "location": "P-1!B80", "quote": "Rebuig  a -1,35 m"},
        {"punt": "P-2", "cota_inici": None, "profunditat_assolida": "-2.45", "rebuig": "Si", "nivell_freatic": "-1,00 (humitat)", "matis": "humitat", "location": "P-2!B80", "quote": "Rebuig  a -2,45 m"},
    ]})
    _doc(out, "manuscrit", "PENETROS.pdf", "full_camp_manuscrit", [_ta("field_date", "1-10-2025", 0.75), _ta("num_soil_levels", "2", 0.45)],
         tables={"dpsh_tests": [{"punt": "P1", "cota_inici": "-0,15", "profunditat_assolida": "-1,35", "rebuig": "Si", "nivell_freatic": "No", "location": "p.2", "quote": "R:1,35"}]})
    _doc(out, "sondeig", "PDF/ANNEXES/3009999_sondeig.pdf", "annex_sondeig", [
        _ta("num_soil_levels", "1", 0.85), _ta("lab_sample_id", "SPT-1", 0.75), _ta("lab_depth", "-1,00 a -1,60 m", 0.7), _ta("lab_location", "S-1", 0.6),
    ], tables={
        "sondeig_tests": [{"sondeig": "S-1", "cota": "250.00 msnm", "profunditat_assolida": "1.80 m", "spt_ma": {"n_spt": 1, "n_tp": 0, "n_ma": 0}, "nivell_freatic": None, "location": "p.1", "quote": "S-1"}],
        "spt_ma_tests": [{"id": "SPT-1", "punt": "S-1", "profunditat": "-1,00 a -1,60 m", "litologia": "Graves en matriu sorrenca", "n30": {"registre": [24, 34, 28, 30], "candidats_suma": [62]}, "location": "p.1", "quote": "SPT-1 24/34/28/30"}],
        "soil_levels": [{"nom": "NIVELL 1", "litologia_candidats": ["Graves en matriu sorrenca carbonatada"], "de": "0.30", "a": "1.80", "mostra_del_nivell": True, "location": "p.1", "quote": "NIVELL 1"}],
    })
    _doc(out, "gtl", "4699-GTL-25.pdf", "informe_laboratori", [
        _ta("lab_testing_company", "TPS, Prospecció del Subsòl, SL", 0.95), _ta("lab_sample_id", "MA1 S1", 0.8), _ta("lab_depth", "1,0 - 1,6 m", 0.9),
        _ta("lab_location", "S1", 0.75), _ta("NOT_client_name", "G3 Desenvolupament Territorial, SL", 0.0, note="G3 mai és client"),
        _ta("report_title", "Informe de laboratori", 0.5),
    ], tables={"spt_ma_tests": [{"id": "MA1", "punt": "S1", "profunditat": "1,0 - 1,6 m", "litologia": "Grava amb llims", "n30": None, "location": "p.2", "quote": "MA1 S1"}]})
    _doc(out, "tall", "tall.pdf", "annex_tall", [_ta("num_soil_levels", "1", 0.6)], tables={
        "soil_levels": [{"nom": "Terreny vegetal", "litologia": "Llims marrons", "de": "0,00", "a": "0,30", "mostra_del_nivell": False},
                        {"nom": "Nivell 1", "litologia": "Graves amb sorres", "de": None, "a": None, "mostra_del_nivell": False}],
        "spt_ma_tests": [{"id": None, "punt": "S-1", "profunditat": "≈0,8 a 1,3 m (gràfic)", "litologia": None, "n30": None, "n30_candidat_tall": 58, "location": "tall", "quote": "N=58"}],
    })
    _doc(out, "comanda_dup", "comanda copia.xls", "comanda_lab_g3", [_ta("expedient", "3009999", 0.9)], md5="md5-annex_dpsh")  # duplicat md5
    # Inventari COMPLET, com el que escriu el runner: hi ha d'haver una entrada per cada
    # `{doc}.json` (un JSON sense entrada es una lectura orfe i `load_corpus` la descarta).
    (out / "_inventory.json").write_text(json.dumps({"generated": "now", "project": proj.name, "files": [
        {"path": "A.01.pdf", "md5": "md5-planol", "route": "claude"},
        {"path": "PDF/ANNEXES/3009999_DPSH.pdf", "md5": "md5-annex_dpsh", "route": "claude"},
        {"path": "PDF/ANNEXES/3009999_fotografies.pdf", "md5": "md5-fotos", "route": "claude"},  # sense JSON: lectura fallida
        {"path": "comanda.xls", "md5": "md5-comanda", "route": "python"},
        {"path": "ANNEXES/DPSH.xls", "md5": "md5-excel", "route": "python"},
        {"path": "PENETROS.pdf", "md5": "md5-manuscrit", "route": "claude"},
        {"path": "PDF/ANNEXES/3009999_sondeig.pdf", "md5": "md5-sondeig", "route": "claude"},
        {"path": "4699-GTL-25.pdf", "md5": "md5-gtl", "route": "claude"},
        {"path": "tall.pdf", "md5": "md5-tall", "route": "claude"},
        {"path": "comanda copia.xls", "md5": "md5-annex_dpsh", "route": "claude"},
    ], "duplicates": {}}, ensure_ascii=False), encoding="utf-8")
    return proj, out


def test_synthetic_project_contract_clean_and_fields(synth):
    proj, out = synth
    dec = C.consolidate_python(out, proj)
    assert validate_decisions(dec) == []
    f = dec["fields"]
    assert set(f) == ALLOWED_FIELD_KEYS
    assert f["expedient"]["estat"] == "segur" and f["expedient"]["value"] == "3009999"
    assert any(c["font"] == "nom de la carpeta del projecte" for c in f["expedient"]["candidates"] + f["expedient"].get("altres", []))
    assert f["client_name"]["estat"] == "segur" and f["client_name"]["value"] == "PROMOTOR SL"
    assert f["client_name"]["descartats"][0]["value"].startswith("G3")
    assert f["municipality"]["estat"] == "segur"
    assert f["architect_name"]["estat"] == "segur" and f["architect_name"]["value"] == "Nom Cognom"
    assert f["field_date"]["estat"] == "segur" and f["field_date"]["value"] == "2025-10-01"
    assert f["num_dpsh_tests"]["estat"] == "segur" and str(f["num_dpsh_tests"]["value"]) == "2"
    assert f["lab_depth"]["estat"] == "segur" and f["lab_depth"]["value"] == "1,0 - 1,6 m"  # GTL (A 0.9) mana sobre l'annex
    assert f["lab_testing_company"]["estat"] == "segur"
    assert f["lab_sample_id"]["estat"] == "candidats"  # annex SPT-1 vs GTL MA1 S1 → candidats (Pas 3)
    assert f["lab_location"]["estat"] == "segur"  # convergencia GTL + annex + ... (S1 == S-1)
    assert f["num_soil_levels"]["estat"] == "candidats"  # manuscrit diu 2 (0.45)
    assert f["referencia_catastral"]["estat"] == "candidats"  # 0,6 sense `authority_for`: cap autoritat de camp (R5)
    assert f["superficie_parcela"]["estat"] == "segur"  # unica font, 1 RC
    assert f["cte_edificacio"]["estat"] == "no_trobat" and f["cte_sol"]["estat"] == "candidats"
    assert f["cte_sol"]["candidates"][0]["font"].startswith("(coneixement previ")
    # UTM: COORDENADES P-1 (python, A) vs annex sondeig S-1 (0.6) → candidats amb P-1 primer
    assert f["utm_x"]["estat"] == "candidats" and f["utm_x"]["value"] == "300000.0"
    assert "COORDENADES.txt" in f["utm_x"]["candidates"][0]["font"]
    # cota_referencia: annex DPSH +250,00 (A) = sondeig 250.00; la z GPS 250.5 de COORDENADES es un concepte vei (R2):
    # corrobora o fa de recanvi, mai bloqueja → segur, i la z queda a `altres`
    assert f["cota_referencia"]["estat"] == "segur"
    assert any("COORDENADES" in c["font"] for c in f["cota_referencia"].get("altres", []))
    # lectura fallida i duplicats anotats
    assert any("lectura fallida" in s for s in f["field_date"]["sources_checked"])
    assert "comanda copia.xls" in dec["notes_estructurals"][1]
    assert "report_title" in dec["extra_concepts"]


def test_synthetic_project_tables(synth):
    proj, out = synth
    dec = C.consolidate_python(out, proj)
    t = dec["tables"]
    dpsh = t["dpsh_tests"]["rows"]
    assert [r["punt"] for r in dpsh] == ["P-1", "P-2"]
    assert dpsh[0]["cota_inici"]["estat"] == "segur" and dpsh[0]["cota_inici"]["value"] == "+250,00 msnm"
    assert dpsh[0]["profunditat_assolida"]["estat"] == "segur"
    assert dpsh[0]["nivell_freatic"]["estat"] == "segur" and dpsh[0]["nivell_freatic"]["value"] == "No detectat"
    assert dpsh[0]["nivell_freatic"]["matis"] is None
    # P-2: Excel (A) diu humitat a -1,00; annex (A) diu 'no consta' → dues fonts A discrepen → candidats + conflicte
    assert dpsh[1]["nivell_freatic"]["estat"] == "candidats"
    assert any(c["path"] == "tables.dpsh_tests[P-2].nivell_freatic" for c in dec["conflicts"])
    # manuscrit '-0,15' (no A) no bloqueja, pero es conserva
    assert any(c["value"] == "-0,15" for c in dpsh[0]["cota_inici"].get("altres", []))
    son = t["sondeig_tests"]["rows"][0]
    assert son["sondeig"] == "S-1"
    assert son["cota"]["estat"] == "segur"  # sistema absolut: cap cota DPSH relativa
    assert son["spt_ma"]["estat"] == "candidats" and son["spt_ma"]["value"] == "1/0" and son["spt_ma"]["counts"]["n_spt"] == 1
    spt = t["spt_ma_tests"]["rows"]
    assert len(spt) == 1  # annex + GTL + tall (≈0,8-1,3 grafic) = la mateixa fila
    assert spt[0]["punt"]["estat"] == "segur"
    assert spt[0]["id"]["estat"] == "candidats"  # SPT-1 vs MA1: regla coneguda, sense conflicte LLM
    assert not any("spt_ma_tests" in c["path"] and c["path"].endswith(".id") for c in dec["conflicts"])
    assert spt[0]["profunditat"]["estat"] == "segur"
    assert spt[0]["n30"]["estat"] == "candidats" and spt[0]["n30"]["registre"]["value"] == [24, 34, 28, 30]
    assert spt[0]["litologia"]["estat"] == "candidats"
    soil = t["soil_levels"]["rows"]
    assert [r["nom"] for r in soil][0].lower().startswith("terreny vegetal")
    assert len(soil) == 2
    assert soil[1]["litologia"]["estat"] == "candidats"
    assert soil[1]["a"]["estat"] == "candidats"  # ultim nivell: final del reconeixement
    assert soil[1]["mostra_del_nivell"]["value"] is True
    assert validate_decisions(dec) == []


def test_relative_cota_system_makes_sondeig_cota_relative_and_never_segur(tmp_path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "annex_dpsh", "PDF/ANNEXES/X_DPSH.pdf", "annex_dpsh", [], tables={"dpsh_tests": [
        {"punt": "P-1", "cota_inici": "-4 m (respecte el carrer)", "profunditat_assolida": "-1,08 m", "rebuig": "Si", "nivell_freatic": None, "location": "p.1", "quote": "q"}]})
    _doc(out, "sondeig", "PDF/ANNEXES/X_sondeig.pdf", "annex_sondeig", [], tables={"sondeig_tests": [
        {"sondeig": "S-1", "cota": "570.90 msnm", "profunditat_assolida": "1.20 m", "spt_ma": None, "nivell_freatic": None, "location": "p.1", "quote": "q"}]})
    _doc(out, "manuscrit", "PENETROS.pdf", "full_camp_manuscrit", [], tables={"sondeig_tests": [
        {"sondeig": "S-1", "cota": "-4 m (relativa)", "profunditat_assolida": None, "spt_ma": None, "nivell_freatic": None, "location": "p.5", "quote": "C/ -4 m"}]})
    dec = C.consolidate_python(out, None, project_name="X")
    cota = dec["tables"]["sondeig_tests"]["rows"][0]["cota"]
    assert cota["estat"] == "candidats"
    assert cota["value"] == "-4 m (relativa)"
    assert [c["value"] for c in cota["candidates"]][1] == "570.90 msnm"
    assert dec["conflicts"] == []  # relativa documentada per al sondeig → cap crida LLM
    assert validate_decisions(dec) == []


def test_relative_system_without_documented_sondeig_cota_borrows_dpsh_and_flags_conflict(tmp_path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "annex_dpsh", "PDF/ANNEXES/X_DPSH.pdf", "annex_dpsh", [], tables={"dpsh_tests": [
        {"punt": "P-1", "cota_inici": "-4 m (respecte el carrer)", "profunditat_assolida": "-1,08 m", "rebuig": "Si", "nivell_freatic": None, "location": "p.1", "quote": "q"}]})
    _doc(out, "sondeig", "PDF/ANNEXES/X_sondeig.pdf", "annex_sondeig", [], tables={"sondeig_tests": [
        {"sondeig": "S-1", "cota": "570.90 msnm", "profunditat_assolida": "1.20 m", "spt_ma": None, "nivell_freatic": None, "location": "p.1", "quote": "q"}]})
    dec = C.consolidate_python(out, None, project_name="X")
    cota = dec["tables"]["sondeig_tests"]["rows"][0]["cota"]
    assert cota["estat"] == "candidats"
    assert cota["candidates"][0]["font"].startswith("(sistema relatiu del projecte: cota DPSH)")
    assert cota["candidates"][0]["value"] == "-4 m (respecte el carrer)"
    assert any(c["path"] == "tables.sondeig_tests[S-1].cota" for c in dec["conflicts"])


def test_architect_absent_uses_client_as_practica_eva_candidate(tmp_path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "acc", "ACCEPTACIO/DADES CLIENT.txt", "altre", [_ta("client_name", "Maria Client", 0.9)])
    dec = C.consolidate_python(out, None, project_name="X")
    arch = dec["fields"]["architect_name"]
    assert arch["estat"] == "candidats" and arch["value"] == "Maria Client"
    assert arch["candidates"][0]["font"].startswith("(practica Eva")


def test_architect_equal_to_client_or_person_and_company_never_segur(tmp_path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "a", "A.01.pdf", "planol", [_ta("client_name", "Pere Autopromotor", 0.95), _ta("architect_name", "Pere Autopromotor", 0.95)])
    dec = C.consolidate_python(out, None, project_name="X")
    assert dec["fields"]["architect_name"]["estat"] == "candidats"
    out2 = tmp_path / "l2"
    out2.mkdir()
    _doc(out2, "a", "A.01.pdf", "planol", [_ta("architect_name", "Jordi Bosch Novell", 0.95), _ta("architect_name", "ARQUITECTURA BOSCH NOVELL", 0.85)])
    dec2 = C.consolidate_python(out2, None, project_name="X")
    assert dec2["fields"]["architect_name"]["estat"] == "candidats"


def test_two_cadastral_refs_make_superficie_parcela_candidats(tmp_path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "a", "A.01.pdf", "planol", [_ta("superficie_parcela", "995,00 m2", 0.85)])
    _doc(out, "c", "correu.msg", "correu", [_ta("referencia_catastral", "4613172CG1141S0001SU", 0.45), _ta("referencia_catastral", "4613173CG1141S0001ZU", 0.45)])
    dec = C.consolidate_python(out, None, project_name="X")
    assert dec["fields"]["superficie_parcela"]["estat"] == "candidats"


def test_entre_el_carrer_phrase_from_annex_is_first_candidate(tmp_path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "p", "pressupost.pdf", "pressupost_g3", [_ta("street_address", "C/MESTRE RAMON ORTIZ 15", 0.9)])
    _doc(out, "s", "PDF/ANNEXES/X_pl situació.pdf", "annex_planol_situacio", [_ta("street_address", "Situat entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz", 0.85)])
    dec = C.consolidate_python(out, None, project_name="X")
    sa = dec["fields"]["street_address"]
    assert sa["estat"] == "candidats" and sa["value"].startswith("Situat entre")


def test_utm_pair_split_and_lab_cte_nested_flattened(tmp_path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "s", "PDF/ANNEXES/X_sondeig.pdf", "annex_sondeig", [
        _ta("utm_x_utm_y", "X 314418.9 ; Y 4611117.6", 0.9),
        _ta("lab", {"lab_testing_company": "TPS", "lab_sample_id": "SPT-1", "lab_depth": None, "lab_location": "S-1"}, 0.9),
        _ta("cte", {"cte_edificacio": "C1", "cte_sol": "T1"}, 0.9),
    ])
    dec = C.consolidate_python(out, None, project_name="X")
    f = dec["fields"]
    assert f["utm_x"]["value"] == "314418.9" and f["utm_y"]["value"] == "4611117.6"
    assert f["lab_sample_id"]["value"] == "SPT-1" and f["lab_depth"]["estat"] == "no_trobat"
    assert f["cte_edificacio"]["estat"] == "candidats" and f["cte_edificacio"]["value"] == "C1"  # cte mai segur


def test_parse_coordenades():
    pts = C.parse_coordenades("Coordenades UTM (X);(Y);(Z);\nP-1\n423167.0 ; 4609608.0 ; 571.5\n\nS-1\n423182.0 ; 4609623.0 ; 570.9\n")
    assert [p["punt"] for p in pts] == ["P-1", "S-1"]
    assert pts[0]["x"] == "423167.0" and pts[1]["z"] == "570.9"


# ---------------------------------------------------------------------------
# Fixtures reals: perdoc dels runs del llibre
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("perdoc", PERDOC_SETS, ids=[p.parent.name for p in PERDOC_SETS])
def test_real_perdoc_sets_contract_clean_and_no_signal_lost(perdoc: Path, tmp_path: Path):
    out = tmp_path / "lectura"
    out.mkdir()
    for p in perdoc.glob("*.json"):
        if p.name not in ("_decisions.json", "_job.json", "_consolida_only.json"):
            (out / p.name).write_bytes(p.read_bytes())
    dec = C.consolidate_python(out, None, project_name="3001621 CASTELLAR DEL VALLES")
    assert validate_decisions(dec) == []
    assert dec["consolidation"]["elapsed_s"] < 2.0
    present = _all_signal_values(dec)
    corpus = C.load_corpus(out)
    for d in corpus.docs:
        for e in d.get("tier_a") or []:
            cid = e.get("concept_id") or ""
            if cid.startswith("NOT_") or cid in ("utm_x_utm_y", "lab", "cte") or e.get("value") is None:
                continue
            key = json.dumps(e["value"], ensure_ascii=False, sort_keys=True)
            assert key in present, f"senyal perdut: {d['source_path']} {cid}={e['value']!r}"
    # cap cel·la n30/litologia segur; cap candidat derivat com a segur
    for row in dec["tables"]["spt_ma_tests"]["rows"]:
        assert row["n30"]["estat"] != "segur" and row["litologia"]["estat"] != "segur"
    for cell in dec["fields"].values():
        if cell["estat"] == "segur":
            assert not cell["candidates"][0]["font"].startswith("("), cell


# ---------------------------------------------------------------------------
# normalize.wrap_flat_cells (reparacio d)
# ---------------------------------------------------------------------------


def test_wrap_flat_cells_wraps_sonnet_flat_dialect_and_validates():
    flat = {"schema_version": 1, "project": "X", "generated": "now", "skill_version": "1.3", "fields": {},
            "tables": {"dpsh_tests": {"estat_bloc": "segur", "rows": [
                {"punt": "P-1", "cota_inici": "-4 m", "profunditat_assolida": "-1,08 m", "rebuig": "Si", "nivell_freatic": None, "matis": None}]},
                "spt_ma_tests": {"estat_bloc": "candidats", "rows": [
                    {"id": "SPT-1", "punt": "S-1", "profunditat": "1,00 - 1,20 m", "litologia": "Substrat rocós",
                     "n30": {"registre": "R", "candidats_suma": None}}]},
                "soil_levels": {"estat_bloc": "segur", "rows": [{"nom": "Nivell 1", "litologia": "Bretxes", "de": "0,50", "a": "1,20", "mostra_del_nivell": True}]}}}
    out = soft_normalize(flat)
    assert validate_decisions(out) == []
    r = out["tables"]["dpsh_tests"]["rows"][0]
    assert r["punt"] == "P-1"  # identificador: text pla
    assert r["cota_inici"] == {"estat": "segur", "value": "-4 m", "candidates": [{"value": "-4 m", "font": "(adaptat)", "quote": "-4 m"}],
                               "rule": "(adaptat: cel·la plana embolcallada de forma determinista, Fase 12)"}
    assert r["nivell_freatic"]["estat"] == "no_trobat"
    spt = out["tables"]["spt_ma_tests"]["rows"][0]
    assert spt["n30"]["estat"] == "candidats" and spt["n30"]["value"] == "R" and spt["n30"]["registre"]["value"] == "R"
    assert spt["litologia"]["estat"] == "candidats"  # mai segur
    assert out["tables"]["soil_levels"]["rows"][0]["litologia"]["estat"] == "candidats"


def test_wrap_flat_cells_leaves_proper_cells_untouched():
    proper = {"tables": {"dpsh_tests": {"estat_bloc": "segur", "rows": [
        {"punt": "P-1", "cota_inici": {"estat": "segur", "value": "-4 m", "candidates": [{"value": "-4 m", "font": "f", "quote": "q"}]}}]}}}
    out = wrap_flat_cells(proper)
    assert out == proper


# ---------------------------------------------------------------------------
# merge_only_fields
# ---------------------------------------------------------------------------


def test_merge_only_fields_applies_only_requested_valid_cells_and_keeps_guards():
    base = {"fields": {"expedient": {"estat": "candidats", "value": "A", "candidates": [{"value": "A", "font": "f", "quote": "q"}], "altres": [{"value": "Z", "font": "f", "quote": "q"}]},
                       "client_name": {"estat": "candidats", "value": "C", "candidates": [{"value": "C", "font": "f", "quote": "q"}]},
                       "cte_sol": {"estat": "candidats", "value": "T-1", "candidates": [{"value": "T-1", "font": "f", "quote": "q"}]}},
            "tables": {"spt_ma_tests": {"estat_bloc": "candidats", "rows": [{"id": "SPT-1", "punt": "S-1",
                       "n30": {"estat": "candidats", "value": "R", "candidates": [{"value": "R", "font": "f", "quote": "q"}], "registre": {"estat": "segur", "value": "R", "candidates": [{"value": "R", "font": "f", "quote": "q"}]}}}]}}}
    llm = {"fields": {"expedient": {"estat": "segur", "value": "B", "candidates": [{"value": "B", "font": "llm", "quote": "q"}]},
                      "client_name": {"estat": "segur", "value": "X", "candidates": [{"value": "X", "font": "llm", "quote": "q"}]},  # no demanat
                      "cte_sol": {"estat": "segur", "value": "T-1", "candidates": [{"value": "T-1", "font": "llm", "quote": "q"}]},  # guard
                      "municipality": {"estat": "segur"}},  # invalid
           "tables": {"spt_ma_tests": {"rows": [{"id": "SPT-1", "n30": {"estat": "segur", "value": "40", "candidates": [{"value": "40", "font": "llm", "quote": "q"}]}}]}}}
    merged, applied = C.merge_only_fields(base, llm, ["fields.expedient", "fields.cte_sol", "fields.municipality", "tables.spt_ma_tests[S-1].n30"])
    assert applied == ["fields.expedient"]
    assert merged["fields"]["expedient"]["value"] == "B" and merged["fields"]["expedient"]["llm_only_fields"] is True
    assert merged["fields"]["expedient"]["altres"][0]["value"] == "Z"  # res es perd
    assert merged["fields"]["client_name"]["value"] == "C"
    assert merged["fields"]["cte_sol"]["estat"] == "candidats"
    assert merged["tables"]["spt_ma_tests"]["rows"][0]["n30"]["value"] == "R"


def test_merge_only_fields_needs_two_readable_ids_to_match_a_row():
    """Dos identificadors il·legibles donen `_point_key(...) is None` a totes dues bandes:
    si nomes es compara `!=`, `None == None` fa que la cel·la de l'LLM caigui a QUALSEVOL
    fila. Ha de casar per igualtat literal o per clau de punt LLEGIBLE."""
    def _c(v):
        return {"estat": "candidats", "value": v, "candidates": [{"value": v, "font": "f", "quote": "q"}]}

    base = {"fields": {}, "tables": {"spt_ma_tests": {"estat_bloc": "candidats", "rows": [
        {"id": "MA1", "punt": "S-1", "profunditat": _c("-1,00 a -1,20")}]}}}
    llm = {"fields": {}, "tables": {"spt_ma_tests": {"rows": [
        {"id": "MA9", "profunditat": _c("-9,00 a -9,20")}]}}}

    merged, applied = C.merge_only_fields(base, llm, ["tables.spt_ma_tests[MA9].profunditat"])
    assert applied == []
    assert merged["tables"]["spt_ma_tests"]["rows"][0]["profunditat"]["value"] == "-1,00 a -1,20"

    # amb el mateix identificador literal si que hi ha d'entrar
    llm["tables"]["spt_ma_tests"]["rows"][0]["id"] = "MA1"
    merged, applied = C.merge_only_fields(base, llm, ["tables.spt_ma_tests[MA1].profunditat"])
    assert applied == ["tables.spt_ma_tests[MA1].profunditat"]
    assert merged["tables"]["spt_ma_tests"]["rows"][0]["profunditat"]["value"] == "-9,00 a -9,20"


# ---------------------------------------------------------------------------
# Fase 13(b): fonts HTTP (Cadastre / ICGC / geocodificacio) al consolidador
# ---------------------------------------------------------------------------


def _project_with_auto_result(tmp_path: Path, prefills: dict, sources: dict | None = None) -> tuple[Path, Path]:
    """Carpeta de projecte amb `validation/_auto_result.json` valid + `out_dir` de lectura."""
    from automation import auto_result_cache as arc
    from automation.auto_extractor import AutoExtractionResult

    proj = tmp_path / "3001621 CASTELLAR"
    out_dir = proj / "validation" / "lectura"
    out_dir.mkdir(parents=True)
    (proj / "PENETROS.pdf").write_bytes(b"%PDF entrada")
    (proj / "file_mapping.json").write_text('{"roles": {}}', encoding="utf-8")
    arc.save(proj, AutoExtractionResult(prefills=prefills, sources=sources or {}))
    C._auto_result_memo.clear()
    return proj, out_dir


def test_http_signals_fill_a_field_no_document_mentions(tmp_path: Path, monkeypatch):
    """Forat 1: `auto_extract` ja consultava l'ICGC, pero el consolidador no ho veia."""
    monkeypatch.setenv("G3DT_LECTURA_HTTP_SOURCES", "icgc")
    proj, out_dir = _project_with_auto_result(
        tmp_path, {"cota_referencia": "+569.50"}, {"cota_referencia": "ICGC MDT 2m"})
    _doc(out_dir, "d1", "PENETROS.pdf", "camp_penetros", [_ta("municipality", "Castellar", 0.9)])

    dec = C.consolidate_python(out_dir, project_path=proj)
    cell = dec["fields"]["cota_referencia"]
    assert cell["estat"] == "candidats", "una consulta HTTP tota sola mai no fa `segur`"
    assert cell["value"] == "+569.50"
    assert "ICGC MDT 2m" in cell["candidates"][0]["font"]
    assert "annex" in (cell.get("note") or "")


def test_http_signals_never_displace_a_document(tmp_path: Path, monkeypatch):
    """La regla del disseny: cap font Python pot GUANYAR un camp contra la
    lectura. La porta es la mateixa que la dels derivats: nomes forats."""
    monkeypatch.setenv("G3DT_LECTURA_HTTP_SOURCES", "icgc")
    proj, out_dir = _project_with_auto_result(
        tmp_path, {"cota_referencia": "+569.50"}, {"cota_referencia": "ICGC MDT 2m"})
    _doc(out_dir, "d1", "ANNEXES/x_sondeig.pdf", "annex_sondeig", [_ta("cota_referencia", "+570,90", 0.9)])

    cell = C.consolidate_python(out_dir, project_path=proj)["fields"]["cota_referencia"]
    assert cell["value"] == "+570,90"
    fonts = " ".join(c.get("font", "") for c in cell["candidates"] + cell.get("altres", []))
    assert "ICGC" not in fonts, "amb un document que ho diu, la consulta HTTP ni tan sols s'emet"


def _cadastre_project(tmp_path: Path) -> tuple[Path, Path]:
    """Projecte sintetic amb `street_address`/`municipality` ja llegits (font A, 0.9): el
    lector nou (`cadastre_reader.cadastre_portal_signals`) llegeix `decided[...]`, no
    `_auto_result.json`."""
    proj = tmp_path / "3001621 CASTELLAR"
    out_dir = proj / "validation" / "lectura"
    out_dir.mkdir(parents=True)
    _doc(out_dir, "d1", "PENETROS.pdf", "camp_penetros", [
        _ta("municipality", "Castellar del Valles", 0.9),
        _ta("street_address", "Carrer Arbrells, 18A, 18B i 20", 0.9),
    ])
    return proj, out_dir


def _fake_cadastre_signal(key: str, value: str, note: str = "") -> "C.Signal":
    return C.Signal(key, value, "(Cadastre: test)", "", 0.5, C._HTTP_DOC, "consulta_http", "python", note or None)


def test_cadastre_default_is_on_and_calls_the_new_reader(tmp_path: Path, monkeypatch):
    """Decisio del Josep 2026-08-31 (Fix D, `PLA-PENDENTS-0B-0C-0D` §7.9/§11): Cadastre
    encès per defecte. El vell mecanisme via `_auto_result.json` ja no existeix per a
    aquests dos camps (vegeu `_HTTP_FIELD_SOURCES`): els omple `cadastre_reader`."""
    monkeypatch.delenv("G3DT_LECTURA_HTTP_SOURCES", raising=False)
    proj, out_dir = _cadastre_project(tmp_path)

    calls: list[str] = []

    def fake(key, decided, project_path, extra_concepts=None):
        calls.append(key)
        if key == "superficie_parcela":
            return [_fake_cadastre_signal("superficie_parcela", "1284", "3/3 parcel·les contigues")]
        return [_fake_cadastre_signal("referencia_catastral", "3298012DG2039N+3298013DG2039N+3298014DG2039N")]
    monkeypatch.setattr("automation.lectura.cadastre_reader.cadastre_portal_signals", fake)

    fields = C.consolidate_python(out_dir, project_path=proj)["fields"]
    assert set(calls) == {"referencia_catastral", "superficie_parcela"}
    assert fields["superficie_parcela"]["estat"] == "candidats"
    assert fields["superficie_parcela"]["value"] == "1284"
    assert fields["referencia_catastral"]["value"] == "3298012DG2039N+3298013DG2039N+3298014DG2039N"


def test_cadastre_can_be_turned_off(tmp_path: Path, monkeypatch):
    """(h) commutador OFF -> el lector nou no es crida."""
    monkeypatch.setenv("G3DT_LECTURA_HTTP_SOURCES", "icgc,geocodificacio")
    proj, out_dir = _cadastre_project(tmp_path)

    def boom(*a, **k):
        raise AssertionError("cadastre_portal_signals no s'hauria de cridar amb el commutador OFF")
    monkeypatch.setattr("automation.lectura.cadastre_reader.cadastre_portal_signals", boom)

    fields = C.consolidate_python(out_dir, project_path=proj)["fields"]
    assert fields["referencia_catastral"]["estat"] == "no_trobat"
    assert fields["superficie_parcela"]["estat"] == "no_trobat"


def test_cadastre_reader_not_called_when_a_document_already_answers(tmp_path: Path, monkeypatch):
    """(g) porta tancada: Bell-lloc ja diu `superficie_parcela` (995) en un document ->
    el lector nou no es crida (cap font Python pot guanyar contra la lectura)."""
    monkeypatch.delenv("G3DT_LECTURA_HTTP_SOURCES", raising=False)
    proj = tmp_path / "4001612 BELL-LLOC"
    out_dir = proj / "validation" / "lectura"
    out_dir.mkdir(parents=True)
    _doc(out_dir, "d1", "ANNEXES/fitxa_cadastral.pdf", "fitxa_cadastral", [
        _ta("municipality", "Bell-lloc d'Urgell", 0.9),
        _ta("street_address", "C/ Mestre Ramon Ortiz 15", 0.9),
        _ta("superficie_parcela", "995", 0.9),
        _ta("referencia_catastral", "4613172CG1141S", 0.9),
    ])

    def boom(*a, **k):
        raise AssertionError("porta tancada: no s'hauria de cridar")
    monkeypatch.setattr("automation.lectura.cadastre_reader.cadastre_portal_signals", boom)

    fields = C.consolidate_python(out_dir, project_path=proj)["fields"]
    assert fields["superficie_parcela"]["value"] == "995"
    assert fields["referencia_catastral"]["value"] == "4613172CG1141S"


def test_cadastre_reader_receives_already_decided_street_and_municipality(tmp_path: Path, monkeypatch):
    """(i) `order` acaba amb `referencia_catastral`, `superficie_parcela`: quan es crida
    el lector, `street_address`/`municipality` ja son al dict `decided`."""
    monkeypatch.delenv("G3DT_LECTURA_HTTP_SOURCES", raising=False)
    proj, out_dir = _cadastre_project(tmp_path)

    seen: dict[str, tuple[str | None, str | None]] = {}
    seen_extra: dict[str, bool] = {}

    def fake(key, decided, project_path, extra_concepts=None):
        seen[key] = (decided.get("street_address", {}).get("estat"), decided.get("municipality", {}).get("estat"))
        seen_extra["vist"] = extra_concepts is not None
        return []
    monkeypatch.setattr("automation.lectura.cadastre_reader.cadastre_portal_signals", fake)

    C.consolidate_python(out_dir, project_path=proj)
    assert seen["referencia_catastral"] == ("segur", "segur")
    assert seen["superficie_parcela"] == ("segur", "segur")
    # peces 3+4: el lector rep també `extra_concepts`, d'on treu `street_address_struct`
    # (grafies alternatives). Vegeu `automation/lectura/address_struct.py`.
    assert seen_extra["vist"] is True


@pytest.mark.network
def test_cadastre_reader_import_is_lazy_and_module_wiring_works_end_to_end(tmp_path: Path):
    """Sense monkeypatch, contra l'API real del Cadastre (xarxa; els altres tests d'aquest
    fitxer no en necessiten): confirma el cablejat sencer `consolidate.py` ->
    `cadastre_reader` amb el projecte real de Castellar (441+423+420 = 1.284, com l'Eva)."""
    pytest.importorskip("shapely")
    proj, out_dir = _cadastre_project(tmp_path)
    try:
        fields = C.consolidate_python(out_dir, project_path=proj)["fields"]
    except Exception as e:  # xarxa no disponible en aquest entorn: no bloquejar la suite
        pytest.skip(f"Cadastre no accessible: {e}")
    if fields["superficie_parcela"]["estat"] == "no_trobat":
        pytest.skip("Cadastre no ha respost (xarxa no disponible en aquest entorn)")
    assert fields["superficie_parcela"]["value"] == "1284"
    assert "3298012DG2039N" in fields["referencia_catastral"]["value"]


def test_geocoded_utm_only_fills_in_when_there_is_no_coordenades_txt(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("G3DT_LECTURA_HTTP_SOURCES", "geocodificacio")
    proj, out_dir = _project_with_auto_result(
        tmp_path, {"_resolved_utm_x": 423191.06, "_resolved_utm_y": 4609628.49},
        {"_resolved_utm_x": "geocode (address resolution)", "_resolved_utm_y": "geocode (address resolution)"})
    _doc(out_dir, "d1", "PENETROS.pdf", "camp_penetros", [_ta("municipality", "Castellar", 0.9)])

    cell = C.consolidate_python(out_dir, project_path=proj)["fields"]["utm_x"]
    assert cell["estat"] == "candidats" and str(cell["value"]).startswith("423191")

    # Amb COORDENADES.txt, `python_signals` ja omple el camp i la porta es tanca.
    (proj / "COORDENADES.txt").write_text("P-1\n423167 ; 4609608 ; 571.5\n", encoding="utf-8")
    C._auto_result_memo.clear()
    cell = C.consolidate_python(out_dir, project_path=proj)["fields"]["utm_x"]
    assert cell["value"] == "423167"


def test_no_auto_result_means_no_http_signals(tmp_path: Path, monkeypatch):
    """Primera lectura d'un projecte que no ha passat mai pel wizard."""
    monkeypatch.setenv("G3DT_LECTURA_HTTP_SOURCES", "icgc,geocodificacio,cadastre")
    proj = tmp_path / "3001621 CASTELLAR"
    out_dir = proj / "validation" / "lectura"
    out_dir.mkdir(parents=True)
    _doc(out_dir, "d1", "PENETROS.pdf", "camp_penetros", [_ta("municipality", "Castellar", 0.9)])
    C._auto_result_memo.clear()

    fields = C.consolidate_python(out_dir, project_path=proj)["fields"]
    assert fields["cota_referencia"]["estat"] == "no_trobat"
    assert fields["referencia_catastral"]["estat"] == "no_trobat"


def test_stale_auto_result_is_not_used(tmp_path: Path, monkeypatch):
    """Es llegeix amb `auto_result_cache.load()`: si els fitxers del projecte han
    canviat des de la consulta, no se serveix una resposta HTTP vella."""
    monkeypatch.setenv("G3DT_LECTURA_HTTP_SOURCES", "icgc")
    proj, out_dir = _project_with_auto_result(
        tmp_path, {"cota_referencia": "+569.50"}, {"cota_referencia": "ICGC MDT 2m"})
    _doc(out_dir, "d1", "PENETROS.pdf", "camp_penetros", [_ta("municipality", "Castellar", 0.9)])
    (proj / "PENETROS.pdf").write_bytes(b"%PDF una altra carpeta")
    C._auto_result_memo.clear()

    assert C.consolidate_python(out_dir, project_path=proj)["fields"]["cota_referencia"]["estat"] == "no_trobat"


def test_http_sources_can_be_disabled_entirely(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("G3DT_LECTURA_HTTP_SOURCES", "")
    proj, out_dir = _project_with_auto_result(
        tmp_path, {"cota_referencia": "+569.50"}, {"cota_referencia": "ICGC MDT 2m"})
    _doc(out_dir, "d1", "PENETROS.pdf", "camp_penetros", [_ta("municipality", "Castellar", 0.9)])

    assert C.consolidate_python(out_dir, project_path=proj)["fields"]["cota_referencia"]["estat"] == "no_trobat"


# ---------------------------------------------------------------------------
# Capa vegetal: fondaries que venien del full de camp no arribaven a la fila
# ---------------------------------------------------------------------------


def _castellar_soil_corpus(out_dir: Path, *, cover_depths: tuple[str, str] | None = None,
                           cover_row: bool = True) -> None:
    """La forma real de Castellar: el tall dibuixa la capa vegetal SENSE fondaries,
    l'annex de sondeig numera nomes el substrat, i el full de camp te les
    fondaries pero amb la seva propia numeracio (compta la capa vegetal com a
    "1er nivell")."""
    cover = {"nom": "Terreny Vegetal (sense número a la llegenda)",
             "litologia": "Llims argilosos de color marró fosc amb graves i algunes arrels.",
             "de": None, "a": None, "mostra_del_nivell": False}
    if cover_depths:
        cover["de"], cover["a"] = cover_depths
    tall_rows = ([cover] if cover_row else []) + [
        {"nom": "Nivell 1", "litologia": "Substrat rocós. Bretxes amb intercalacions de lutites.",
         "de": None, "a": None, "mostra_del_nivell": False}]
    _doc(out_dir, "tall", "tall.pdf", "annex_tall", [], tables={"soil_levels": tall_rows})
    _doc(out_dir, "annex", "PDF/ANNEXES/3001621_sondeig.pdf", "annex_sondeig", [], tables={"soil_levels": [
        {"nom": "NIVELL 1", "litologia_candidats": ["Substrat rocós. Bretxes amb intercalacions de lutites."],
         "de": "0.50", "a": "1.20", "mostra_del_nivell": True, "location": "p.1", "quote": "0.50-1.20"}]})
    _doc(out_dir, "manuscrit", "PENETROS + SONDEIG.pdf", "full_camp_manuscrit", [], tables={"soil_levels": [
        {"nom": "1er nivell", "litologia": "Llims argilosos amb graves", "de": "0,00", "a": "0,50",
         "mostra_del_nivell": False, "location": "p.5", "quote": "de 0,00 a 0,50"},
        {"nom": "2on nivell", "litologia": "Roca fracturada", "de": "0,50", "a": "1,20",
         "mostra_del_nivell": True, "location": "p.5", "quote": "de 0,50 a 1,20"}]})


def _soil_rows(dec: dict) -> dict[str, dict]:
    return {str(r.get("nom")): r for r in dec["tables"]["soil_levels"]["rows"]}


def test_cover_layer_gets_its_depths_from_the_field_sheet(tmp_path: Path):
    """Abans: 3 files (capa vegetal amb `de`/`a` `no_trobat` + una fila espuria
    amb 0,00-0,50). El tall no li dona fondaries i la numeracio del full de camp
    s'ignora a posta, aixi que la fila 0,00-0,50 no trobava on anar."""
    out = tmp_path / "lectura"
    out.mkdir()
    _castellar_soil_corpus(out)

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    assert len(rows) == 2, "la capa vegetal i el nivell 1, no una tercera fila espuria"
    cover = next(r for nom, r in rows.items() if "Vegetal" in nom)
    assert cover["de"]["value"] == "0,00"
    assert cover["a"]["value"] == "0,50"
    assert cover["de"]["estat"] == "candidats", "el full de camp no es autoritat A per a `de`/`a`"


def test_cover_layer_with_its_own_depths_is_not_touched(tmp_path: Path):
    """Si un annex ja li dona fondaries, mana el solapament d'interval de sempre."""
    out = tmp_path / "lectura"
    out.mkdir()
    _castellar_soil_corpus(out, cover_depths=("0,00", "0,60"))

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    assert len(rows) == 2
    cover = next(r for nom, r in rows.items() if "Vegetal" in nom)
    assert cover["de"]["value"] == "0,00"


def test_surface_row_keeps_its_own_row_when_there_is_no_cover_layer(tmp_path: Path):
    """Sense capa vegetal la regla no dispara: el comportament no canvia."""
    out = tmp_path / "lectura"
    out.mkdir()
    _castellar_soil_corpus(out, cover_row=False)

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    assert len(rows) == 2
    assert not any("Vegetal" in nom for nom in rows)
    assert any(r.get("de", {}).get("value") == "0,00" for r in rows.values())


def test_a_deep_row_never_lands_on_the_cover_layer(tmp_path: Path):
    """Nomes la fila que arrenca a la superficie pot donar fondaries a la capa
    vegetal via solapament d'interval: una fila fonda es una altra cosa i queda en
    fila propia (`de`/`a` de la vegetal segueixen sense la SEVA fondaria real
    llegida; des de Fix E, `de` es "segur 0,00" per definicio geometrica, no per
    haver-la trobat en cap document -- vegeu E2b)."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "tall", "tall.pdf", "annex_tall", [], tables={"soil_levels": [
        {"nom": "Terreny vegetal", "litologia": "Llims", "de": None, "a": None, "mostra_del_nivell": False}]})
    _doc(out, "manuscrit", "PENETROS.pdf", "full_camp_manuscrit", [], tables={"soil_levels": [
        {"nom": "1er nivell", "litologia": "Graves", "de": "2,00", "a": "3,50", "mostra_del_nivell": False}]})

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    cover = next(r for nom, r in rows.items() if "vegetal" in nom.lower())
    assert cover["de"]["estat"] == "segur"
    assert cover["de"]["value"] == "0,00"
    assert cover["a"]["estat"] == "no_trobat", "la BASE de la vegetal segueix sense documentar (E2b nomes decideix el `de`)"
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Fix E — Bell-lloc: capa de cobertura des de la llegenda del tall, sense fondaries
# ---------------------------------------------------------------------------


def _belloc_soil_corpus(out_dir: Path, *, cover_a: str | None = None) -> None:
    """La forma real de Bell-lloc: el tall dibuixa "Sols vegetals" com a banda sense
    xifres i l'annex de sondeig nomes numera el substrat des de la superficie
    (NIVELL 1 0,00-1,80), sense fila de cobertura propia enlloc."""
    cover = {"nom": "Sòls vegetals (cobertura, sense número)", "litologia": "Terra vegetal.",
              "de": None, "a": cover_a, "mostra_del_nivell": False}
    _doc(out_dir, "tall", "tall.pdf", "annex_tall", [], tables={"soil_levels": [
        cover, {"nom": "1er nivell", "litologia": "Graves amb sorres", "de": None, "a": None,
                "mostra_del_nivell": False}]})
    _doc(out_dir, "annex", "PDF/ANNEXES/4001612_sondeig.pdf", "annex_sondeig", [], tables={"soil_levels": [
        {"nom": "NIVELL 1", "litologia_candidats": ["Graves amb sorres"], "de": "0.00", "a": "1.80",
         "mostra_del_nivell": False, "location": "p.1", "quote": "0.00-1.80"}]})


def test_cover_layer_without_depths_starts_at_zero_by_definition(tmp_path: Path):
    """E2b: la cobertura sense fondaries llegides arrenca a 0,00 per definicio (regla
    geometrica, no una lectura ambigua d'un document)."""
    out = tmp_path / "lectura"
    out.mkdir()
    _belloc_soil_corpus(out)

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    cover = next(r for nom, r in rows.items() if "vegetal" in nom.lower())
    assert cover["de"]["estat"] == "segur"
    assert cover["de"]["value"] == "0,00"
    assert cover["a"]["estat"] == "no_trobat"


def test_first_level_depth_downgrades_to_candidats_when_cover_has_no_base(tmp_path: Path):
    """E2: sense fondaria de la cobertura, la transicio cobertura/nivell 1 no esta
    documentada numericament -> candidats (tanca l'ALERTA de Bell-lloc)."""
    out = tmp_path / "lectura"
    out.mkdir()
    _belloc_soil_corpus(out)

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    nivell1 = rows["NIVELL 1"]
    assert nivell1["de"]["estat"] == "candidats"
    assert "cobertura" in nivell1["de"]["rule"]
    assert nivell1["a"]["estat"] == "candidats"  # regla existent de la base de l'ultim nivell


def test_first_level_depth_stays_segur_when_cover_has_a_base(tmp_path: Path):
    """Si la cobertura ja te `a`, la regla E2 no dispara (nomes falta quan la base de
    la cobertura no esta documentada enlloc)."""
    out = tmp_path / "lectura"
    out.mkdir()
    _belloc_soil_corpus(out, cover_a="0.30")

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    nivell1 = rows["NIVELL 1"]
    assert nivell1["de"]["estat"] == "segur"


def test_castellar_soil_corpus_unaffected_by_e2_rules(tmp_path: Path):
    """Castellar: la cobertura ja te fondaries del full de camp -> les regles E2/E2b
    no hi disparen (regressio)."""
    out = tmp_path / "lectura"
    out.mkdir()
    _castellar_soil_corpus(out)

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    cover = next(r for nom, r in rows.items() if "Vegetal" in nom)
    assert cover["de"]["estat"] == "candidats"
    assert cover["de"].get("rule") != "Pas 3b: la capa de cobertura comença a 0,00 per definició"
    nivell = next(r for nom, r in rows.items() if nom != cover.get("nom") and "Vegetal" not in nom)
    assert "no està documentada numèricament" not in str(nivell.get("de", {}).get("rule", ""))


def test_corpus_without_cover_layer_unaffected_by_e2_rules(tmp_path: Path):
    """Sense capa de cobertura, les regles E2/E2b no tenen res a fer."""
    out = tmp_path / "lectura"
    out.mkdir()
    _castellar_soil_corpus(out, cover_row=False)

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    assert not any("vegetal" in nom.lower() for nom in rows)


# ---------------------------------------------------------------------------
# `_point_key`: el recurs a `default_letter` (files que es perdien pel cami)
# ---------------------------------------------------------------------------


def test_point_key_falls_back_to_the_block_letter():
    assert C._point_key("P-1") == "P-1"
    assert C._point_key("s 2") == "S-2"
    # Sense lletra a l'identificador mana la del bloc: `"3"` es el punt 3 del bloc, no res.
    assert C._point_key("3", "P") == "P-3"
    assert C._point_key("3", "S") == "S-3"
    assert C._point_key("núm. 4", "S") == "S-4"
    assert C._point_key("sense numero", "S") is None
    assert C._point_key(None, "S") is None


@pytest.mark.parametrize("value", ["SPT-2", "MA1", "03/09/2025", "1,20 m", "Mostra 2 (bossa)"])
def test_point_key_does_not_invent_a_point_out_of_any_number(value: str):
    """El recurs a la lletra del bloc nomes val si el text es NOMES el numero: `"SPT-2"` es
    el 2n assaig i `"MA1"` la mostra 1, no els sondeigs 2 i 1. Un identificador inventat es
    pitjor que cap: el que no es llegeix ha d'anar al cistell `"S-?"`."""
    assert C._point_key(value, "S") is None
    assert C._point_key(value, "P") is None


def test_spt_rows_without_a_point_do_not_borrow_the_number_of_the_test(tmp_path: Path):
    """`id` es l'etiqueta de l'assaig, no el sondeig: una fila amb `id="SPT-2"` i sense
    `punt` NO es del sondeig S-2 — va al cistell dels inclassificables."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "annex", "PDF/ANNEXES/3009999_sondeig.pdf", "annex_sondeig", [], tables={
        "spt_ma_tests": [{"id": "SPT-1", "punt": "S-2", "profunditat": "-3,00 a -3,20 m",
                          "litologia": "Graves", "n30": "R", "location": "p.1", "quote": "SPT-1"}]})
    _doc(out, "gtl", "4700-GTL-25.pdf", "informe_laboratori", [], tables={
        "spt_ma_tests": [{"id": "SPT-2", "punt": None, "profunditat": "3,0 - 3,2 m",
                          "litologia": None, "n30": None, "location": "p.1", "quote": "SPT-2"}]})

    groups = C._group_spt_rows(C.load_corpus(out))
    assert sorted(k.split("@")[0] for k in groups) == ["S-2", "S-?"]


def test_rows_identified_only_by_a_number_are_not_dropped(tmp_path: Path):
    """Abans, `_point_key("3","P")` tornava `None` i la guarda `if k:` descartava la fila
    sencera: no arribava ni al `_decisions.json`."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "annex", "PDF/ANNEXES/3009999_DPSH.pdf", "annex_dpsh", [], tables={
        "dpsh_tests": [{"punt": "3", "cota_inici": "+250,00 msnm", "profunditat_assolida": "-1,35 m",
                        "rebuig": "Si", "nivell_freatic": None, "location": "p.1", "quote": "3"}],
        "sondeig_tests": [{"sondeig": "2", "cota": "+250,00 msnm", "profunditat_assolida": "1,80 m",
                           "spt_ma": {"n_spt": 1, "n_tp": 0, "n_ma": 0}, "nivell_freatic": None,
                           "location": "p.2", "quote": "2"}]})

    dec = C.consolidate_python(out, project_path=None)
    assert [r["punt"] for r in dec["tables"]["dpsh_tests"]["rows"]] == ["3"]
    assert [r["sondeig"] for r in dec["tables"]["sondeig_tests"]["rows"]] == ["2"]


def test_unidentifiable_spt_rows_do_not_merge_into_a_real_sounding(tmp_path: Path):
    """El cistell `S-?` (cap identificador llegible) no es un comodi: fusionar-lo amb el
    primer grup d'interval compatible enganxava la fila al sondeig equivocat."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "annex", "PDF/ANNEXES/3009999_sondeig.pdf", "annex_sondeig", [], tables={
        "spt_ma_tests": [{"id": "SPT-1", "punt": "S-1", "profunditat": "-1,00 a -1,20 m",
                          "litologia": "Graves", "n30": None, "location": "p.1", "quote": "SPT-1"}]})
    _doc(out, "tall", "tall.pdf", "annex_tall", [], tables={
        "spt_ma_tests": [{"id": None, "punt": "assaig sense identificar", "profunditat": "≈1,0 a 1,2 m (gràfic)",
                          "litologia": None, "n30": None, "location": "tall", "quote": "N=58"}]})

    groups = C._group_spt_rows(C.load_corpus(out))
    assert sorted(k.split("@")[0] for k in groups) == ["S-1", "S-?"]


# ---------------------------------------------------------------------------
# `_superficie_construida`: pura i idempotent sobre el corpus
# ---------------------------------------------------------------------------


def _superficie_corpus(out_dir: Path) -> None:
    _doc(out_dir, "projecte", "25.0493/projecte.pdf", "projecte_arquitecte", [], tables={
        "superficie_construida": [{"rows": [
            {"total": "280+86", "components": ["280 m2 (habitatge)", "86 m2 (garatge)"],
             "location": "p.3", "quote": "280 + 86"}]}]})


def _superficie_components(out_dir: Path, components: list) -> dict:
    _doc(out_dir, "projecte", "projecte.pdf", "projecte_arquitecte", [], tables={
        "superficie_construida": [{"components": components, "location": "p.3", "quote": "quadre de superficies"}]})
    return C._superficie_construida(C.load_corpus(out_dir))


def test_synthesised_total_reads_the_summand_with_the_unit_not_the_label(tmp_path: Path):
    """El total sintetic (`"85+120"`) arriba a l'informe per `tables_report._sum_total`.
    Amb el PRIMER numero del sumand agafava el de l'etiqueta (`"P1: 85 m2"` -> 1) i el
    .docx deia `121`."""
    out = tmp_path / "lectura"
    out.mkdir()
    assert _superficie_components(out, ["P1: 85 m2", "PB: 120 m2"])["value"] == "85+120"


def test_no_total_is_synthesised_when_a_summand_is_unreadable(tmp_path: Path):
    """Sumar nomes els sumands llegibles dona una superficie incompleta amb aparenca de
    total: sense total sintetic, la cel·la queda en blanc (i el matis viatja a la font)."""
    out = tmp_path / "lectura"
    out.mkdir()
    cell = _superficie_components(out, ["120 m2", "planta baixa"])
    assert cell["estat"] == "no_trobat" and cell["value"] in (None, "")


# --- Reparacio (e) de `normalize.py`: dialecte dels sumands (una sola llista de claus) ---


@pytest.mark.parametrize("component,expected_figure", [
    # alies observats: la xifra passa a la clau canonica
    ({"concepte": "HABITATGE", "valor": "56.75 m²"}, "56.75 m²"),
    ({"concepte": "GARATGE", "superficie_m2": 85}, 85),
    ({"superficie": "120 m2"}, "120 m2"),
    # la clau canonica ja hi es amb xifra: no es toca res
    ({"concepte": "PB", "value": "280 m2", "valor": "no consta"}, "280 m2"),
    # clau DESCONEGUDA amb xifra ancorada a unitat: xarxa de seguretat per FORMA
    ({"concepte": "PORXO", "sup_construida_planta": "28,55 m²"}, "28,55 m²"),
])
def test_a_summand_ends_with_its_figure_in_the_canonical_key(component, expected_figure):
    from automation.lectura.normalize import COMPONENT_VALUE_KEY, canonicalize_component
    out = canonicalize_component(component)
    assert out[COMPONENT_VALUE_KEY] == expected_figure
    assert canonicalize_component(out) == out, "idempotent"
    assert component == dict(component), "no muta l'entrada"


@pytest.mark.parametrize("component", [
    # cap xifra enlloc
    {"concepte": "planta baixa", "observacions": "no consta"},
    # xifra sense unitat a una clau desconeguda: no es pot distingir d'un numero d'etiqueta
    {"concepte": "PB", "sup_construida_planta": "280"},
    # dues claus desconegudes amb xifra ancorada: triar-ne una seria endevinar
    {"a": "85 m2", "b": "120 m2"},
])
def test_an_unreadable_summand_is_left_alone_instead_of_guessed(component):
    from automation.lectura.normalize import COMPONENT_VALUE_KEY, canonicalize_component
    out = canonicalize_component(component)
    assert out == component
    assert COMPONENT_VALUE_KEY not in out


def test_a_text_summand_keeps_its_shape():
    from automation.lectura.normalize import canonicalize_component
    assert canonicalize_component("120 m2 (Arbrells 18A)") == "120 m2 (Arbrells 18A)"


def test_the_label_is_not_lost_when_the_canonical_key_held_it():
    """`value` sense xifra es una etiqueta: es queda a la clau que hem buidat (intercanvi)."""
    from automation.lectura.normalize import canonicalize_component
    assert canonicalize_component({"value": "HABITATGE", "valor": "85 m2"}) == \
        {"value": "85 m2", "valor": "HABITATGE"}


def test_the_dialect_valor_reaches_the_synthesised_total(tmp_path: Path):
    """Dialecte real de Linyola (`{"concepte", "valor"}`) SENSE total al document: abans
    `_component_m2` nomes mirava `value`/`superficie_m2`, la suma no es sintetitzava i la
    cel·la de l'informe quedava en blanc."""
    out = tmp_path / "lectura"
    out.mkdir()
    cell = _superficie_components(out, [{"concepte": "GARATGE", "valor": "56.75 m²"},
                                        {"concepte": "HABITATGE", "valor": "165.61 m²"}])
    assert cell["value"] == "56.75+165.61"


def test_an_unknown_summand_key_is_read_by_shape_and_traced_in_the_notes(tmp_path: Path):
    """El lector es un productor cec: pot estrenar un nom de camp a qualsevol execucio. Es
    llegeix per FORMA (xifra ancorada a m²) i el nom queda al rastre de `notes_estructurals`
    per poder-lo afegir als alies quan es repeteixi."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "projecte", "projecte.pdf", "projecte_arquitecte", [], tables={
        "superficie_construida": [{"components": [{"concepte": "PB", "sup_planta": "280 m2"},
                                                  {"concepte": "P1", "sup_planta": "86 m2"}],
                                   "location": "p.3", "quote": "quadre de superficies"}]})
    dec = C.consolidate_python(out, project_path=None)
    assert dec["tables"]["superficie_construida"]["value"] == "280+86"
    assert any("sup_planta" in n and "COMPONENT_VALUE_ALIASES" in n for n in dec["notes_estructurals"])


def test_an_unresolvable_summand_traces_its_keys_and_leaves_a_blank(tmp_path: Path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "projecte", "projecte.pdf", "projecte_arquitecte", [], tables={
        "superficie_construida": [{"components": [{"concepte": "PB", "sup_planta": "sense xifra"}],
                                   "location": "p.3", "quote": "quadre de superficies"}]})
    dec = C.consolidate_python(out, project_path=None)
    assert dec["tables"]["superficie_construida"]["estat"] == "no_trobat"
    assert any("sup_planta" in n and "concepte" in n for n in dec["notes_estructurals"])


def test_no_dialect_note_when_every_summand_key_is_known(tmp_path: Path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "projecte", "projecte.pdf", "projecte_arquitecte", [], tables={
        "superficie_construida": [{"components": [{"concepte": "PB", "valor": "280 m2"}],
                                   "location": "p.3", "quote": "q"}]})
    dec = C.consolidate_python(out, project_path=None)
    assert not any("COMPONENT_VALUE_ALIASES" in n for n in dec["notes_estructurals"])


def test_superficie_construida_does_not_mutate_the_corpus_and_is_idempotent(tmp_path: Path):
    """Abans `entries` era un ALIES de la llista del document i s'estenia mentre es
    recorria: la llista del corpus creixia a cada crida i la segona crida (la que
    s'envia) duplicava components i senyals."""
    out = tmp_path / "lectura"
    out.mkdir()
    _superficie_corpus(out)
    corpus = C.load_corpus(out)
    raw = corpus.docs[0]["tables"]["superficie_construida"]

    first = C._superficie_construida(corpus)
    second = C._superficie_construida(corpus)
    assert len(raw) == 1, "el corpus no es toca"
    assert len(first["components"]) == 1
    assert first == second


def test_superficie_construida_is_decided_once_per_consolidation(tmp_path: Path):
    """`consolidate_python` (derivats) i `consolidate_tables` (taula) han de compartir la
    MATEIXA decisio: una sola per consolidacio, sense components duplicats."""
    out = tmp_path / "lectura"
    out.mkdir()
    _superficie_corpus(out)

    calls = {"n": 0}
    original = C._superficie_construida

    def counting(corpus):
        calls["n"] += 1
        return original(corpus)
    C._superficie_construida = counting
    try:
        dec = C.consolidate_python(out, project_path=None)
    finally:
        C._superficie_construida = original

    assert calls["n"] == 1
    assert len(dec["tables"]["superficie_construida"]["components"]) == 1


# ---------------------------------------------------------------------------
# `load_corpus`: JSON orfes (el fitxer font ja no es a l'inventari)
# ---------------------------------------------------------------------------


def _inventory(out_dir: Path, files: list[tuple[str, str]], skip: tuple[str, ...] = ()) -> None:
    (out_dir / "_inventory.json").write_text(json.dumps({
        "generated": "now", "project": "X", "duplicates": {},
        "files": [{"path": p, "md5": m, "route": "skip" if p in skip else "claude"} for p, m in files]},
        ensure_ascii=False), encoding="utf-8")


def test_orphan_json_does_not_win_over_the_live_file(tmp_path: Path):
    """El document es va reanomenar: el `{doc}.json` vell segueix a `out_dir` amb el mateix
    md5. Sense filtre, el dedup md5 el feia canonic (guanya el primer per ordre alfabetic)
    i deixava el fitxer VIU marcat de duplicat."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "a_orfe", "tall VELL.pdf", "annex_tall", [_ta("num_soil_levels", "1", 0.6)], md5="md5-tall")
    _doc(out, "z_viu", "tall.pdf", "annex_tall", [_ta("num_soil_levels", "1", 0.6)], md5="md5-tall")
    _inventory(out, [("tall.pdf", "md5-tall")])

    corpus = C.load_corpus(out)
    assert [d["source_path"] for d in corpus.docs] == ["tall.pdf"]
    assert corpus.orfes == ["tall VELL.pdf"]
    assert "tall.pdf" not in corpus.duplicates
    assert "tall VELL.pdf" not in corpus.lectura_fallida


def test_orphan_json_is_reported_in_the_structural_notes(tmp_path: Path):
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "viu", "tall.pdf", "annex_tall", [], md5="md5-viu")
    _doc(out, "orfe", "PENETROS VELL.pdf", "full_camp_manuscrit", [_ta("field_date", "01/10/2025", 0.8)], md5="md5-orfe")
    _inventory(out, [("tall.pdf", "md5-viu")])

    dec = C.consolidate_python(out, project_path=None)
    assert any("orfes" in n and "PENETROS VELL.pdf" in n for n in dec["notes_estructurals"])
    assert dec["fields"]["field_date"]["estat"] == "no_trobat", "l'orfe no aporta senyals"


def test_load_corpus_without_inventory_keeps_every_json(tmp_path: Path):
    """Directoris sintetics sense `_inventory.json`: comportament de sempre."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "a", "tall.pdf", "annex_tall", [])
    _doc(out, "b", "PENETROS.pdf", "full_camp_manuscrit", [])

    corpus = C.load_corpus(out)
    assert sorted(d["source_path"] for d in corpus.docs) == ["PENETROS.pdf", "tall.pdf"]
    assert corpus.orfes == []


def test_incomparable_inventory_does_not_drop_everything(tmp_path: Path):
    """Inventari d'un altre projecte (o amb un altre format de ruta): si NO casa amb cap
    JSON no es pot fer servir com a filtre — millor no filtrar que buidar el corpus."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "a", "tall.pdf", "annex_tall", [])
    _doc(out, "b", "PENETROS.pdf", "full_camp_manuscrit", [])
    _inventory(out, [("un/altre/projecte.pdf", "md5-x")])

    corpus = C.load_corpus(out)
    assert sorted(d["source_path"] for d in corpus.docs) == ["PENETROS.pdf", "tall.pdf"]
    assert corpus.orfes == []


def test_quarantined_file_is_an_orphan_and_stops_competing(tmp_path: Path):
    """L'Eva mou la versio vella del plànol a `_esborrats/`: `build_inventory` la deixa a
    `files` amb `route="skip"`. Comptant-la com a ruta viva, el `{doc}.json` mort NO era
    orfe, tornava a competir amb el viu i convertia un `segur` en `candidats` amb el
    promotor caducat al costat."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "old", "_esborrats/A.01 v1.pdf", "projecte_arquitecte",
         [_ta("client_name", "PROMOTOR VELL SL", 0.9)], md5="md5-old")
    _doc(out, "new", "A.01 v2.pdf", "projecte_arquitecte",
         [_ta("client_name", "PROMOTOR NOU SL", 0.9)], md5="md5-new")
    _inventory(out, [("_esborrats/A.01 v1.pdf", "md5-old"), ("A.01 v2.pdf", "md5-new")],
               skip=("_esborrats/A.01 v1.pdf",))

    corpus = C.load_corpus(out)
    assert corpus.orfes == ["_esborrats/A.01 v1.pdf"]
    assert [d["source_path"] for d in corpus.docs] == ["A.01 v2.pdf"]
    assert "_esborrats/A.01 v1.pdf" not in corpus.lectura_fallida, "route skip no es una lectura fallida"
    cell = C.consolidate_python(out, project_path=None)["fields"]["client_name"]
    assert cell["value"] == "PROMOTOR NOU SL"
    assert "PROMOTOR VELL SL" not in json.dumps(cell, ensure_ascii=False)


def test_a_skip_route_never_rescues_a_json_of_a_deleted_file(tmp_path: Path):
    """Mateix criteri que `runner.py::_consolida_fingerprint`: `route == "skip"` no compta.
    Cap lectura legitima se'n va: el runner nomes encua `route == "claude"`."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "viu", "tall.pdf", "annex_tall", [], md5="md5-viu")
    _doc(out, "foto", "FOTOGRAFIES/obra.jpg", "fotografia", [], md5="md5-foto")
    _inventory(out, [("tall.pdf", "md5-viu"), ("FOTOGRAFIES/obra.jpg", "md5-foto")],
               skip=("FOTOGRAFIES/obra.jpg",))

    assert C.load_corpus(out).orfes == ["FOTOGRAFIES/obra.jpg"]


def test_every_json_from_the_quarantine_stays_an_orphan(tmp_path: Path):
    """L'escapatoria "tots orfes" (inventari incomparable) NO pot disparar quan l'inventari
    SI que coneix les rutes pero les te en quarantena: son orfes SABUTS. Amb la comparacio
    contra les rutes VIVES, "tots els documents llegits son a `_esborrats/`" desactivava el
    filtre sencer i un document mort decidia un camp a `segur`."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "a", "_esborrats/A.01.pdf", "projecte_arquitecte",
         [_ta("municipality", "MUNICIPI MORT", 0.95)], md5="md5-a")
    _doc(out, "b", "_esborrats/PENETROS.pdf", "full_camp_manuscrit",
         [_ta("municipality", "MUNICIPI MORT", 0.95)], md5="md5-b")
    _inventory(out, [("_esborrats/A.01.pdf", "md5-a"), ("_esborrats/PENETROS.pdf", "md5-b")],
               skip=("_esborrats/A.01.pdf", "_esborrats/PENETROS.pdf"))
    # una entrada VIVA que no pot tenir `{doc}.json` (route python): l'inventari no es "buit"
    inv = json.loads((out / "_inventory.json").read_text(encoding="utf-8"))
    inv["files"].append({"path": "COORDENADES.txt", "md5": "md5-c", "route": "python"})
    (out / "_inventory.json").write_text(json.dumps(inv, ensure_ascii=False), encoding="utf-8")

    corpus = C.load_corpus(out)
    assert corpus.docs == []
    assert corpus.orfes == ["_esborrats/A.01.pdf", "_esborrats/PENETROS.pdf"]
    cell = C.consolidate_python(out, project_path=None)["fields"]["municipality"]
    assert cell["estat"] == "no_trobat"
    assert "MUNICIPI MORT" not in json.dumps(cell, ensure_ascii=False)


def test_an_inventory_of_only_skipped_routes_still_makes_orphans(tmp_path: Path):
    """Mateix criteri sense cap entrada viva: l'inventari existeix i coneix les rutes, o
    sigui que es comparable. Cap `{doc}.json` en quarantena no pot decidir res."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "a", "_esborrats/A.01.pdf", "projecte_arquitecte",
         [_ta("client_name", "PROMOTOR MORT SL", 0.95)], md5="md5-a")
    _inventory(out, [("_esborrats/A.01.pdf", "md5-a")], skip=("_esborrats/A.01.pdf",))

    corpus = C.load_corpus(out)
    assert corpus.docs == [] and corpus.orfes == ["_esborrats/A.01.pdf"]


def test_inventory_path_separator_and_case_do_not_make_an_orphan(tmp_path: Path):
    """L'inventari el pot haver escrit una altra maquina (Windows): `\\` vs `/` i la caixa
    no poden convertir un document viu en orfe."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "a", "PDF/ANNEXES/3009999_sondeig.pdf", "annex_sondeig", [])
    _inventory(out, [("PDF\\Annexes\\3009999_SONDEIG.pdf", "md5-a")])

    corpus = C.load_corpus(out)
    assert [d["source_path"] for d in corpus.docs] == ["PDF/ANNEXES/3009999_sondeig.pdf"]
    assert corpus.orfes == []
