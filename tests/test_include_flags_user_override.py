"""Punt 2/4 (2026-09-17): «el sistema proposa, no decideix» — `build_report_data()` ha de llegir
`include_earth_pressure`/`include_slope_stability` quan l'Eva els ha decidit de debò
(`user_data['_sources'][camp] == 'user'`), en lloc de recalcular-los sempre des de
`has_basement`/`has_retaining_walls`/`is_sloped`.

Abans, `build_report_data()` ignorava per complet aquests dos camps del wizard: encara que
`web/wizard_service.py` ja els proposava (D3/D4) i el wizard els desés a `user_data.json` amb
`source='user'`, l'informe seguia sortint amb la mateixa activació derivada del pendent (cas
Rubí: 21,6 % ICGC → seccions actives igualment, encara que l'Eva digués que no calien)."""

from __future__ import annotations

from automation.report_data import build_report_data


def test_derived_when_no_user_decision():
    """Sense decisió de l'Eva: comportament d'abans (derivat de `is_sloped`/`has_basement`/etc.)."""
    rd = build_report_data(project_data={}, user_data={"is_sloped": True})
    assert rd.include_slope_stability is True
    assert rd.include_earth_pressure is False


def test_eva_explicit_no_wins_over_sloped():
    """L'Eva ha dit «no calen» — mana per damunt de `is_sloped=True` (cas Rubí)."""
    rd = build_report_data(project_data={}, user_data={
        "is_sloped": True,
        "include_slope_stability": False,
        "include_earth_pressure": False,
        "_sources": {"include_slope_stability": "user", "include_earth_pressure": "user"},
    })
    assert rd.include_slope_stability is False
    assert rd.include_earth_pressure is False


def test_eva_explicit_yes_wins_even_when_flat():
    """L'Eva ha dit «sí calen» tot i que el sistema no ho hauria proposat (`is_sloped=False`)."""
    rd = build_report_data(project_data={}, user_data={
        "is_sloped": False,
        "has_basement": False,
        "has_retaining_walls": False,
        "include_slope_stability": True,
        "include_earth_pressure": True,
        "_sources": {"include_slope_stability": "user", "include_earth_pressure": "user"},
    })
    assert rd.include_slope_stability is True
    assert rd.include_earth_pressure is True


def test_revisar_source_is_not_a_user_decision():
    """`source == 'revisar'` (proposta encara no confirmada) NO és una decisió de l'Eva — es manté el
    càlcul derivat, no el valor proposat literal."""
    rd = build_report_data(project_data={}, user_data={
        "has_basement": True,
        "include_earth_pressure": False,
        "_sources": {"include_earth_pressure": "revisar"},
    })
    assert rd.include_earth_pressure is True, "has_basement=True mana; 'revisar' no és decisió de l'Eva"


def test_has_basement_and_retaining_walls_still_derive_earth_pressure():
    """Regressió: sense cap camp `include_*` a `user_data`, el càlcul de sempre (soterrani/murs) segueix
    funcionant intacte."""
    rd = build_report_data(project_data={}, user_data={"has_retaining_walls": True})
    assert rd.include_earth_pressure is True
