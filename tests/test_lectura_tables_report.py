"""Fase 8b — taules llegides -> files de l'informe.

Cobreix les tres peces de la cadena que la Fase 8 va deixar oberta (forat 6 de
`docs/wizard-headless/fase8-e2e/_RESULTATS.md`):

1. `automation.lectura.tables_report` — traduccio pura (cel·les de 3 estats ->
   files amb el format dels informes signats de l'Eva).
2. Les tries de l'Eva (`lecturaState.selections`) manen sobre la decisio.
3. `ReportGenerator` — bolcat al context de la plantilla, i **via B intacta**
   quan no hi ha lectura.

Els fixtures reals de `docs/golden-read-taules/` son read-only (evidencia
tancada): nomes es llegeixen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from automation.lectura.contract import adapt_legacy
from automation.lectura.tables_report import (
    build_report_tables,
    fmt_cota,
    fmt_depth,
    fmt_depth_range,
    fmt_n30,
    fmt_refusal,
    fmt_spt_ma,
    fmt_water,
    levels_by_number,
    load_project_tables,
    resolve_cell,
)

REPO = Path(__file__).resolve().parents[1]
GOLD_TAULES = REPO / "docs" / "golden-read-taules"


# --------------------------------------------------------------------- cel·les


def test_resolve_cell_plain_value():
    """Els identificadors de fila son text pla per contracte."""
    assert resolve_cell("P-1") == "P-1"
    assert resolve_cell(None) is None


def test_resolve_cell_segur_and_candidats():
    assert resolve_cell({"estat": "segur", "value": "-1,08 m"}) == "-1,08 m"
    cell = {"estat": "candidats", "value": None,
            "candidates": [{"value": "A"}, {"value": "B"}]}
    assert resolve_cell(cell) == "A"


def test_resolve_cell_no_trobat_never_writes_a_value():
    """Regla 4 del contracte: `no_trobat` mai aporta valor."""
    cell = {"estat": "no_trobat", "value": None, "candidates": [{"value": "X"}]}
    assert resolve_cell(cell) is None


def test_resolve_cell_spt_ma_counts_pass_through():
    counts = {"n_spt": 1, "n_tp": 0, "n_ma": 0}
    assert resolve_cell(counts) == counts


# --------------------------------------------------------------------- format


@pytest.mark.parametrize("raw,expected", [
    ("-4 m (respecte el carrer)", "-4.00"),
    ("-4,2 m", "-4.20"),
    ("570.90 msnm", "+570.90"),
    ("+199,50", "+199.50"),
])
def test_fmt_cota_keeps_sign_and_two_decimals(raw, expected):
    assert fmt_cota(raw) == expected


def test_fmt_cota_non_numeric_survives():
    assert fmt_cota("No indicat") == "No indicat"


@pytest.mark.parametrize("raw,expected", [
    ("1,20 m", "-1.20"),
    ("-1,08 m", "-1.08"),
    ("1.35", "-1.35"),
])
def test_fmt_depth_is_always_negative(raw, expected):
    assert fmt_depth(raw) == expected


def test_fmt_depth_range():
    assert fmt_depth_range("1,00 - 1,20 m") == "-1.00 a -1.20"
    assert fmt_depth_range("-1,00 a -1,60") == "-1.00 a -1.60"
    assert fmt_depth_range("1,00") == "-1.00"


@pytest.mark.parametrize("raw,expected", [
    ("Si", "Si"), ("sí", "Si"), ("no", "No"), (True, "Si"), (False, "No"),
])
def test_fmt_refusal(raw, expected):
    assert fmt_refusal(raw) == expected


def test_fmt_water_absent_marker_is_not_turned_into_no_detectat():
    """«no consta» vol dir que el document no ho diu — no que no hi hagi aigua."""
    assert fmt_water("no consta") == "No consta"
    assert fmt_water("no detectat") == "No detectat"


def test_fmt_water_numeric_becomes_a_depth():
    assert fmt_water("1,00 m") == "-1.00"


def test_fmt_spt_ma_pair_when_only_spt_triple_otherwise():
    assert fmt_spt_ma({"n_spt": 1, "n_tp": 0, "n_ma": 0}) == "1/0"
    assert fmt_spt_ma({"n_spt": 1, "n_tp": 0, "n_ma": 1}) == "1/0/1"
    assert fmt_spt_ma({"n_spt": 2, "n_tp": 1, "n_ma": 0}) == "2/1/0"


def test_fmt_n30_keeps_refusal_marker():
    assert fmt_n30("R") == "R"
    assert fmt_n30(62) == "62"


# --------------------------------------------------------------------- blocs


def _decisions_castellar() -> dict:
    path = REPO / "docs/wizard-headless/fase12-consolida/out/sonnet-v2-c3/_decisions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_report_tables_on_a_real_run():
    tables = build_report_tables(_decisions_castellar())
    dpsh = tables["dpsh_tests"]
    assert [r["test_id"] for r in dpsh] == ["P-1", "P-2", "P-3", "P-4"]
    # La cota es PER PUNT i relativa al carrer (regla d'or Pas 3b), no la
    # cota de referencia absoluta que la via B repetia a totes les files.
    assert [r["cota"] for r in dpsh] == ["-4.00", "-4.20", "-4.00", "-4.00"]
    # Fondaria del peu "Rebuig a", no l'ultima fila de la graella.
    assert [r["depth"] for r in dpsh] == ["-1.08", "-0.48", "-0.76", "-1.55"]
    assert {r["refusal"] for r in dpsh} == {"Si"}
    assert tables["sondeig_tests"][0]["spt_ma"] == "1/0"
    assert tables["spt_ma_tests"][0]["depth_range"] == "-1.00 a -1.20"
    assert tables["spt_ma_tests"][0]["n30"] == "R"
    assert tables["superficie_construida"] == "120"


def test_build_report_tables_empty_without_tables():
    assert build_report_tables({}) == {}
    assert build_report_tables(None) == {}
    assert build_report_tables({"fields": {}}) == {}


def test_selections_win_over_the_decision():
    decisions = _decisions_castellar()
    tables = build_report_tables(decisions, {"dpsh_tests.1.cota_inici": "-9,9 m"})
    assert tables["dpsh_tests"][1]["cota"] == "-9.90"
    assert tables["dpsh_tests"][0]["cota"] == "-4.00"  # la resta, intacta


def test_selection_of_a_lithology_reaches_the_row():
    decisions = _decisions_castellar()
    tables = build_report_tables(decisions, {"soil_levels.1.litologia": "Lutites vermelles"})
    assert tables["soil_levels"][1]["litologia"] == "Lutites vermelles"


def test_empty_selection_does_not_blank_the_decision():
    decisions = _decisions_castellar()
    tables = build_report_tables(decisions, {"dpsh_tests.0.cota_inici": ""})
    assert tables["dpsh_tests"][0]["cota"] == "-4.00"


def test_lab_header_comes_from_scalar_fields():
    """`lab_*` no te input al wizard: sense aquest pont no arriba a l'informe."""
    tables = build_report_tables({
        "tables": {"dpsh_tests": {"rows": [{"punt": "P-1"}]}},
        "fields": {
            "lab_sample_id": {"estat": "segur", "value": "SPT-1"},
            "lab_location": {"estat": "segur", "value": "S-1"},
            "lab_depth": {"estat": "candidats", "value": None,
                          "candidates": [{"value": "-1,00 a -1,20 m"}]},
        },
    })
    assert tables["lab"] == {
        "sample_id": "SPT-1", "location": "S-1", "depth": "-1,00 a -1,20 m",
    }


def test_all_golden_table_fixtures_translate_without_crashing():
    """Els 8 projectes de la lectura d'or de taules, en dialecte de fixture."""
    seen = 0
    for path in sorted(GOLD_TAULES.glob("*/_tables_decisions.json")):
        gold = adapt_legacy(json.loads(path.read_text(encoding="utf-8")))
        tables = build_report_tables(gold)
        assert isinstance(tables, dict)
        for row in tables.get("dpsh_tests", []):
            assert row["depth"] == "" or row["depth"].startswith("-"), path.parent.name
        seen += 1
    assert seen >= 6


# ------------------------------------------------------------- nivells


def test_levels_by_number_skips_the_cover_layer():
    """La capa vegetal no es el nivell 1 (lliso del comparador v2)."""
    by_number = levels_by_number([
        {"name": "Terreny Vegetal (sense número a la llegenda)", "litologia": "Llims"},
        {"name": "NIVELL 1", "litologia": "Bretxes"},
        {"name": "2n nivell", "litologia": "Gresos"},
    ])
    assert set(by_number) == {1, 2}
    assert by_number[1]["litologia"] == "Bretxes"


def test_levels_by_number_first_row_wins_on_duplicates():
    by_number = levels_by_number([
        {"name": "NIVELL 1", "litologia": "A"},
        {"name": "1er nivell", "litologia": "B"},
    ])
    assert by_number[1]["litologia"] == "A"


# ------------------------------------------------------------------- I/O


def test_load_project_tables_absent_file_is_via_b(tmp_path):
    assert load_project_tables(tmp_path) == {}


def test_load_project_tables_reads_the_project_decisions(tmp_path):
    out = tmp_path / "validation" / "lectura"
    out.mkdir(parents=True)
    (out / "_decisions.json").write_text(
        json.dumps(_decisions_castellar()), encoding="utf-8",
    )
    tables = load_project_tables(tmp_path)
    assert [r["test_id"] for r in tables["dpsh_tests"]] == ["P-1", "P-2", "P-3", "P-4"]


def test_load_project_tables_survives_a_corrupt_file(tmp_path):
    out = tmp_path / "validation" / "lectura"
    out.mkdir(parents=True)
    (out / "_decisions.json").write_text("{not json", encoding="utf-8")
    assert load_project_tables(tmp_path) == {}


# ------------------------------------------------- integracio amb el generador


class _FakeReportData:
    """Prou ReportData per a `_apply_lectura_soil_levels` (que nomes toca
    `soil_levels`); construir el dataclass sencer aqui seria soroll."""

    def __init__(self, levels):
        self.soil_levels = levels


class _FakeLevel:
    def __init__(self, number, description):
        self.level_number = number
        self.description = description
        self.description_verbatim = False


def _generator(tmp_path, user_data):
    from automation.report_generator import ReportGenerator
    return ReportGenerator(project_path=tmp_path, user_data=user_data)


def test_generator_context_untouched_without_lectura(tmp_path):
    gen = _generator(tmp_path, {})
    context = {"dpsh_tests": [{"test_id": "viaB"}], "spt_test_id": "X"}
    gen._apply_lectura_tables(context)
    assert context == {"dpsh_tests": [{"test_id": "viaB"}], "spt_test_id": "X"}


def test_generator_context_takes_the_read_tables(tmp_path):
    gen = _generator(tmp_path, {"lectura_tables": build_report_tables(_decisions_castellar())})
    context = {"dpsh_tests": [{"test_id": "viaB"}], "superficie_construida": ""}
    gen._apply_lectura_tables(context)
    assert [r["test_id"] for r in context["dpsh_tests"]] == ["P-1", "P-2", "P-3", "P-4"]
    assert context["spt_test_id"] == "SPT-1"
    assert context["superficie_construida"] == "120"


def test_generator_does_not_overwrite_a_filled_scalar(tmp_path):
    gen = _generator(tmp_path, {"lectura_tables": build_report_tables(_decisions_castellar())})
    context = {"superficie_construida": "999"}
    gen._apply_lectura_tables(context)
    assert context["superficie_construida"] == "999"


def test_generator_applies_lithology_by_level_number(tmp_path):
    gen = _generator(tmp_path, {"lectura_tables": {"soil_levels": [
        {"name": "Terreny vegetal", "litologia": "Llims amb arrels"},
        {"name": "NIVELL 1", "litologia": "Bretxes i lutites"},
    ]}})
    gen.report_data = _FakeReportData([_FakeLevel(1, "Roca / material dur")])
    gen._apply_lectura_soil_levels()
    assert gen.report_data.soil_levels[0].description == "Bretxes i lutites"
    assert gen.report_data.soil_levels[0].description_verbatim is True


def test_generator_warns_about_levels_without_read_lithology(tmp_path):
    gen = _generator(tmp_path, {"lectura_tables": {"soil_levels": [
        {"name": "NIVELL 1", "litologia": "Bretxes"},
    ]}})
    gen.report_data = _FakeReportData([_FakeLevel(1, "A"), _FakeLevel(2, "B")])
    gen._apply_lectura_soil_levels()
    assert gen.report_data.soil_levels[1].description == "B"
    assert any("sense litologia llegida" in w for w in gen.warnings)


def test_read_lithology_is_never_shortened():
    """Text ja triat per Eva: literal a la cel·la (`_shorten_material_desc` el
    tallaria pel primer punt)."""
    from automation.report_generator import _level_material, _shorten_material_desc
    text = "Substrat rocós. Bretxes amb intercalacions de lutites"
    auto = _FakeLevel(1, text)
    assert _level_material(auto) == _shorten_material_desc(text) == "Substrat rocós"
    read = _FakeLevel(1, text)
    read.description_verbatim = True
    assert _level_material(read) == text


# --------------------------------------------------- desat al wizard (backend)


def test_save_wizard_data_persists_the_lectura_block(tmp_path):
    from automation.wizard import save_wizard_data

    project = tmp_path / "demo"
    project.mkdir()
    block = {"lectura_tables": {"dpsh_tests": [{"test_id": "P-1"}]},
             "lectura_selections": {"dpsh_tests.0.cota_inici": "-4 m"}}
    path = save_wizard_data(project, {"client_name": "X"}, extra=block)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["lectura_tables"]["dpsh_tests"][0]["test_id"] == "P-1"
    assert saved["lectura_selections"]["dpsh_tests.0.cota_inici"] == "-4 m"
    assert saved["client_name"] == "X"


def test_save_wizard_data_without_extra_is_unchanged(tmp_path):
    """Via B: cap clau nova a `user_data.json`."""
    from automation.wizard import save_wizard_data

    project = tmp_path / "demo"
    project.mkdir()
    saved = json.loads(
        save_wizard_data(project, {"client_name": "X"}).read_text(encoding="utf-8")
    )
    assert "lectura_tables" not in saved
    assert "lectura_selections" not in saved


def test_build_lectura_block_is_empty_without_a_reading(tmp_path):
    from web.wizard_service import _build_lectura_block

    assert _build_lectura_block(tmp_path, {"dpsh_tests.0.punt": "P-9"}) == {}


def test_build_lectura_block_resolves_selections(tmp_path):
    from web.wizard_service import _build_lectura_block

    out = tmp_path / "validation" / "lectura"
    out.mkdir(parents=True)
    (out / "_decisions.json").write_text(
        json.dumps(_decisions_castellar()), encoding="utf-8",
    )
    block = _build_lectura_block(tmp_path, {"dpsh_tests.0.cota_inici": "-7,5 m"})
    assert block["lectura_tables"]["dpsh_tests"][0]["cota"] == "-7.50"
    assert block["lectura_selections"] == {"dpsh_tests.0.cota_inici": "-7,5 m"}


# ------------------------------------- neteja d'anotacions del lector


def test_fmt_n30_strips_the_readers_annotation():
    """El raonament va al popup (font/cita), no dins de la cel·la N30."""
    assert fmt_n30("R (rebuig)") == "R"
    assert fmt_n30("40 (suma dels trams centrals 20+20)") == "40"
    # Nomes quan el davanter es un N30 valid: si no, text intacte.
    assert fmt_n30("Graves (carbonatades)") == "Graves (carbonatades)"


def test_superficie_construida_is_a_number_not_prose():
    from automation.lectura.tables_report import _superficie

    block = {"total": "120 m² construïts (PB+1, sense soterrani) — PER HABITATGE",
             "components": ["120"]}
    assert _superficie(block, None) == "120"


def test_superficie_construida_falls_back_to_the_sum_of_components():
    from automation.lectura.tables_report import _superficie

    assert _superficie({"components": ["280", "86"]}, None) == "366"
    assert _superficie({}, None) == ""


def test_a_bare_candidate_list_never_reaches_the_docx():
    """Dialecte real (Bell-lloc): `litologia` es una llista de candidats."""
    tables = build_report_tables({"tables": {"soil_levels": {"rows": [{
        "nom": "NIVELL 1",
        "litologia": [{"value": "Graves amb sorres", "font": "tall.pdf"},
                      {"value": "Altres", "font": "annex"}],
    }]}}})
    assert tables["soil_levels"][0]["litologia"] == "Graves amb sorres"


def test_unknown_cell_shape_yields_an_empty_cell_not_a_dump():
    from automation.lectura.tables_report import fmt_text

    assert fmt_text({"forma": "desconeguda"}) == ""
    assert fmt_text([]) == ""
