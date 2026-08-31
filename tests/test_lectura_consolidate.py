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
         md5: str | None = None, not_present: list[str] | None = None, skill_version: str = "1.4") -> None:
    payload = {
        "source_path": source_path, "source_md5": md5 or f"md5-{name}", "skill_version": skill_version,
        "schema_version": 1, "document_type": doc_type, "context": {"authority_for": []},
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
    (out / "_inventory.json").write_text(json.dumps({"generated": "now", "project": proj.name, "files": [
        {"path": "A.01.pdf", "md5": "md5-planol", "route": "claude"},
        {"path": "PDF/ANNEXES/3009999_DPSH.pdf", "md5": "md5-annex_dpsh", "route": "claude"},
        {"path": "PDF/ANNEXES/3009999_fotografies.pdf", "md5": "md5-fotos", "route": "claude"},  # sense JSON: lectura fallida
        {"path": "comanda.xls", "md5": "md5-comanda", "route": "python"},
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
    assert f["referencia_catastral"]["estat"] == "candidats"  # sense consulta del Cadastre: mai segur
    assert f["superficie_parcela"]["estat"] == "segur"  # unica font, 1 RC
    assert f["cte_edificacio"]["estat"] == "no_trobat" and f["cte_sol"]["estat"] == "candidats"
    assert f["cte_sol"]["candidates"][0]["font"].startswith("(coneixement previ")
    # UTM: COORDENADES P-1 (python, A) vs annex sondeig S-1 (0.6) → candidats amb P-1 primer
    assert f["utm_x"]["estat"] == "candidats" and f["utm_x"]["value"] == "300000.0"
    assert "COORDENADES.txt" in f["utm_x"]["candidates"][0]["font"]
    # cota_referencia: annex DPSH +250,00 (A) = sondeig 250.00 = COORDENADES z 250.5? no: 250.5 ≠ 250.0 → contradiccio B (0.5) → candidats
    assert f["cota_referencia"]["estat"] == "candidats"
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


def test_cadastre_is_off_by_default(tmp_path: Path, monkeypatch):
    """Mesurat 2026-08-26: a Castellar el Cadastre respon 441 m² i l'informe
    signat de l'Eva diu 1.284; encendre'l passa el comparador d'or de
    14 OK / 7 CAUTELA a 12 OK / 7 CAUTELA / 2 ALERTA."""
    monkeypatch.delenv("G3DT_LECTURA_HTTP_SOURCES", raising=False)
    proj, out_dir = _project_with_auto_result(
        tmp_path,
        {"cadastral_ref": "3298012DG2039N", "superficie_cadastral_m2": 441},
        {"cadastral_ref": "Cadastre API (ortho)", "superficie_cadastral_m2": "Cadastre WFS (geocode)"})
    _doc(out_dir, "d1", "PENETROS.pdf", "camp_penetros", [_ta("municipality", "Castellar", 0.9)])

    fields = C.consolidate_python(out_dir, project_path=proj)["fields"]
    assert fields["referencia_catastral"]["estat"] == "no_trobat"
    assert fields["superficie_parcela"]["estat"] == "no_trobat"


def test_cadastre_can_be_switched_on(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("G3DT_LECTURA_HTTP_SOURCES", "icgc,geocodificacio,cadastre")
    proj, out_dir = _project_with_auto_result(
        tmp_path,
        {"cadastral_ref": "3298012DG2039N", "superficie_cadastral_m2": 441},
        {"cadastral_ref": "Cadastre API (ortho)", "superficie_cadastral_m2": "Cadastre WFS (geocode)"})
    _doc(out_dir, "d1", "PENETROS.pdf", "camp_penetros", [_ta("municipality", "Castellar", 0.9)])

    fields = C.consolidate_python(out_dir, project_path=proj)["fields"]
    assert fields["referencia_catastral"]["estat"] == "candidats"
    assert fields["referencia_catastral"]["value"] == "3298012DG2039N"
    assert fields["superficie_parcela"]["estat"] == "candidats"
    assert "parcel·la equivocada" in (fields["superficie_parcela"].get("note") or "")


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
    vegetal: una fila fonda es una altra cosa."""
    out = tmp_path / "lectura"
    out.mkdir()
    _doc(out, "tall", "tall.pdf", "annex_tall", [], tables={"soil_levels": [
        {"nom": "Terreny vegetal", "litologia": "Llims", "de": None, "a": None, "mostra_del_nivell": False}]})
    _doc(out, "manuscrit", "PENETROS.pdf", "full_camp_manuscrit", [], tables={"soil_levels": [
        {"nom": "1er nivell", "litologia": "Graves", "de": "2,00", "a": "3,50", "mostra_del_nivell": False}]})

    rows = _soil_rows(C.consolidate_python(out, project_path=None))
    cover = next(r for nom, r in rows.items() if "vegetal" in nom.lower())
    assert cover["de"]["estat"] == "no_trobat"
    assert len(rows) == 2
