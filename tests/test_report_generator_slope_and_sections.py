"""Fixes C i D (2026-09-17) a `automation/report_generator.py`.

Cas real (Rubí): l'informe generat deia «Com que es tracta d'un solar pla…» a §3.3.1 i alhora portava
«4.4 EMPENTES DE TERRES» / «4.5 ESTABILITAT DE VESSANT» completament buides sobre la signatura de l'Eva
(pendent real ICGC 21,6 %). Causa arrel: dues consultes ICGC mal ordenades (una massa tard per activar les
seccions, `_build_template_context`; una altra que mai es feia abans, `generate()` pas 2b) i cap invariant que
impedís imprimir una capçalera sense contingut.

- C: `context['site_condition']`/`site_description` només manen si `_sources` diu `'user'` de debò.
- D1: `_resolve_slope()` consulta l'ICGC ABANS de `generate_sections()`, una sola vegada.
- D2: cap `include_earth_pressure`/`include_slope_stability` a True amb el paràgraf corresponent buit.
"""

from __future__ import annotations

import datetime
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from automation.report_data import ClientData, ReportData
from automation.report_generator import ReportGenerator


def _minimal_report_data(**overrides) -> ReportData:
    defaults = dict(
        expedient="X", municipality="Rubí", report_date=datetime.date.today(),
        client=ClientData(company_name="Test SL"),
        architect_name="", architect_company="", building_type="habitatge", num_floors="PB",
        superficie_parcela="500", superficie_cadastral="500", superficie_construida="100",
        has_basement=False, has_retaining_walls=False, street_address="Carrer Test 1",
    )
    defaults.update(overrides)
    return ReportData(**defaults)


def _generator(user_data: dict | None = None, tmp_path: Path | None = None) -> ReportGenerator:
    project_path = tmp_path if tmp_path is not None else Path(tempfile.mkdtemp())
    return ReportGenerator(project_path=project_path, user_data=user_data or {})


# --- Fix C: la provinença mana, no el recompte de paraules -----------------------------------------------------

def test_site_condition_user_source_wins_even_without_utm(tmp_path):
    """`_sources['site_condition'] == 'user'` → el text de l'Eva mana."""
    gen = _generator({
        "_sources": {"site_condition": "user"},
        "site_condition": "Text sencer que ha escrit l'Eva de debò",
    }, tmp_path)
    gen.report_data = _minimal_report_data()
    ctx = gen._build_template_context({})
    assert ctx["site_condition"] == "Text sencer que ha escrit l'Eva de debò"


def test_site_condition_computed_source_never_wins_even_with_4_words(tmp_path):
    """Fix C: abans, `computed (slope 0%)` amb ≥ 4 paraules es confonia amb text de l'Eva. Ara no."""
    gen = _generator({
        "_sources": {"site_condition": "computed (slope 0%)"},
        "site_condition": "Com que es tracta d'un solar pla",
    }, tmp_path)
    gen.report_data = _minimal_report_data()
    ctx = gen._build_template_context({})
    # Sense UTM ni antropització coneguda, el recalculat és la capçalera neutra — MAI el valor «pla» estancat.
    assert ctx["site_condition"].startswith("Al solar,")


def test_site_condition_no_sources_key_falls_back_to_word_count(tmp_path):
    """Informes antics sense `_sources`: es manté el criteri d'abans (recompte de paraules) com a reserva."""
    gen = _generator({"site_condition": "Text llarg que ve d'algun lloc antic sense font"}, tmp_path)
    gen.report_data = _minimal_report_data()
    ctx = gen._build_template_context({})
    assert ctx["site_condition"] == "Text llarg que ve d'algun lloc antic sense font"


# --- Fix D1: una sola resolució del pendent, ABANS de generar les seccions -------------------------------------

def test_resolve_slope_queries_icgc_once_and_caches(tmp_path):
    gen = _generator(tmp_path=tmp_path)
    gen.report_data = _minimal_report_data(utm_x=311000.0, utm_y=4604000.0)
    calls = []

    def fake_get_slope(x, y, *a, **kw):
        calls.append((x, y))
        return 21.6, "N"

    with patch("automation.icgc_geology.get_slope", fake_get_slope):
        gen._resolve_slope()
        gen._resolve_slope()  # segona crida: no ha de tornar a consultar

    assert calls == [(311000.0, 4604000.0)]
    assert gen.report_data.slope_percent == 21.6
    assert gen.report_data.is_sloped is True
    assert gen._slope_resolved is True


def test_resolve_slope_never_forces_flat_on_failure(tmp_path):
    gen = _generator(tmp_path=tmp_path)
    gen.report_data = _minimal_report_data(utm_x=311000.0, utm_y=4604000.0)

    def boom(*a, **kw):
        raise RuntimeError("xarxa caiguda")

    with patch("automation.icgc_geology.get_slope", boom):
        gen._resolve_slope()

    assert gen.report_data.slope_percent is None
    assert gen.report_data.is_sloped is False
    assert any("ICGC" in w for w in gen.warnings)


def test_resolve_slope_skips_when_already_known(tmp_path):
    gen = _generator(tmp_path=tmp_path)
    gen.report_data = _minimal_report_data(utm_x=311000.0, utm_y=4604000.0, slope_percent=0.0)
    called = []
    with patch("automation.icgc_geology.get_slope", lambda *a, **kw: called.append(1) or (99.0, "N")):
        gen._resolve_slope()
    assert not called
    assert gen.report_data.slope_percent == 0.0


def test_slope_resolved_before_sections_activates_real_content(tmp_path):
    """Cas Rubí reproduït: pendent real (ICGC) resolt ABANS de `generate_sections()` → les seccions 4.4/4.5
    porten contingut de debò, no capçaleres buides. UNA sola consulta ICGC per a tot el flux."""
    gen = _generator(tmp_path=tmp_path)
    gen.report_data = _minimal_report_data(utm_x=311000.0, utm_y=4604000.0)
    calls = []

    def fake_get_slope(x, y, *a, **kw):
        calls.append((x, y))
        return 21.6, "N"

    with patch("automation.icgc_geology.get_slope", fake_get_slope):
        gen._resolve_slope()
        if getattr(gen.report_data, "is_sloped", False):
            gen.report_data.include_slope_stability = True
            gen.report_data.include_earth_pressure = True
        sections = gen.generate_sections()
        ctx = gen._build_template_context(sections)

    assert calls == [(311000.0, 4604000.0)], "una sola crida ICGC per a tot el flux (D1 evita la duplicada)"
    assert ctx["include_earth_pressure"] is True
    assert ctx["include_slope_stability"] is True
    assert ctx["empentes_paragraph"], "capçalera activada AMB contingut"
    assert ctx["estabilitat_paragraph"], "capçalera activada AMB contingut"
    assert ctx["section_empentes_num"] == "4.4"
    assert ctx["section_estabilitat_num"] == "4.5"


# --- Fix D2: mai una capçalera activada sense contingut ---------------------------------------------------------

def test_include_flags_demoted_when_paragraph_ends_up_empty(tmp_path):
    """Invariant dur: encara que `report_data.include_*` fossin True, si el paràgraf queda buit (per qualsevol
    motiu), `context['include_*']` ha de quedar False i la numeració buida — mai una capçalera nua."""
    gen = _generator(tmp_path=tmp_path)
    gen.report_data = _minimal_report_data(include_earth_pressure=True, include_slope_stability=True)

    class FakeSection4:
        empentes_paragraph = ""
        estabilitat_paragraph = ""
        ka_value = None
        kp_value = None
        expansivitat_paragraph = ""
        geologia_summary = ""
        water_statement = ""
        aggressivity_statement = ""

    ctx = gen._build_template_context({"section4": FakeSection4()})
    assert ctx["include_earth_pressure"] is False
    assert ctx["include_slope_stability"] is False
    assert ctx["section_empentes_num"] == ""
    assert ctx["section_estabilitat_num"] == ""


def test_include_flags_true_when_paragraph_present(tmp_path):
    gen = _generator(tmp_path=tmp_path)
    gen.report_data = _minimal_report_data()

    class FakeSection4:
        empentes_paragraph = "text real"
        estabilitat_paragraph = ""
        ka_value = None
        kp_value = None
        expansivitat_paragraph = ""
        geologia_summary = ""
        water_statement = ""
        aggressivity_statement = ""

    ctx = gen._build_template_context({"section4": FakeSection4()})
    assert ctx["include_earth_pressure"] is True
    assert ctx["include_slope_stability"] is False
    assert ctx["section_empentes_num"] == "4.4"
    assert ctx["section_estabilitat_num"] == ""


# --- Punt 4 (2026-09-17): «el sistema proposa, no decideix» — la tria de l'Eva mana sobre l'auto-activació
#     del pas 2b de `generate()`/`build_context_preview()`, encara que `is_sloped` sigui `True` (cas Rubí:
#     pendent ICGC 21,6 %, «la zona de treball es mostra totalment plana») ------------------------------------

def test_include_flags_user_decided_reads_sources(tmp_path):
    gen = _generator({
        "_sources": {"include_earth_pressure": "user", "include_slope_stability": "revisar"},
    }, tmp_path)
    assert gen._include_flags_user_decided() == (True, False)


def test_include_flags_user_decided_defaults_false_without_sources(tmp_path):
    gen = _generator(tmp_path=tmp_path)
    assert gen._include_flags_user_decided() == (False, False)


def test_generate_step2b_respects_eva_explicit_no(tmp_path):
    """L'Eva ha dit «no calen» (`_sources` == 'user', valor False) tot i que `is_sloped=True` — `generate()`
    NO li ha de trepitjar la decisió amb l'auto-activació derivada del pendent mitjà."""
    gen = _generator({
        "is_sloped": True,
        "include_earth_pressure": False,
        "include_slope_stability": False,
        "_sources": {"include_earth_pressure": "user", "include_slope_stability": "user"},
    }, tmp_path)
    gen.extract_project_data = lambda: None
    gen.build_report_data = lambda: setattr(
        gen, "report_data",
        _minimal_report_data(is_sloped=True, include_earth_pressure=False, include_slope_stability=False),
    )
    gen.generate_sections = lambda: {}
    gen.render_template = lambda context, output_path: None

    result = gen.generate(tmp_path / "out.docx")

    assert result.success is True
    assert gen.report_data.include_earth_pressure is False
    assert gen.report_data.include_slope_stability is False


def test_generate_step2b_still_auto_activates_without_eva_decision(tmp_path):
    """Regressió: sense cap decisió de l'Eva (`_sources` absent), es manté el comportament d'abans — el
    pendent `is_sloped=True` segueix activant les dues seccions."""
    gen = _generator({"is_sloped": True}, tmp_path)
    gen.extract_project_data = lambda: None
    gen.build_report_data = lambda: setattr(
        gen, "report_data", _minimal_report_data(is_sloped=True),
    )
    gen.generate_sections = lambda: {}
    gen.render_template = lambda context, output_path: None

    result = gen.generate(tmp_path / "out.docx")

    assert result.success is True
    assert gen.report_data.include_earth_pressure is True
    assert gen.report_data.include_slope_stability is True
