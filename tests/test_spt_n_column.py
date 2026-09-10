"""P0 — columna «N» de la taula geotècnica = N30 de l'SPT del nivell (mai la mitjana N20 del DPSH).

Els 7 casos són les taules SIGNADES de l'Eva (`docs/golden-read-taules/_eva_truth/<slug>.json`):
files de la taula «Assaigs SPT / MA» com a entrada, columna N de la taula de característiques
geotècniques com a resultat esperat. Les descripcions de nivell són les de la mateixa taula
signada (i, on difereixen, també les de la taula de nivells de sòl).
"""

from __future__ import annotations

import pytest

from automation.spt_n_column import (
    NO_SPT, assign_spt_n30, lithology_overlap, n30_display, parse_depth_range,
)


def _lv(number, description, d_from=0.0, d_to=None):
    return {"level_number": number, "description": description, "depth_from_m": d_from, "depth_to_m": d_to}


def _spt(test_id, location, depth_range, n30, lithology):
    return {"test_id": test_id, "location": location, "depth_range": depth_range, "n30": n30, "lithology": lithology}


def _column(levels, rows):
    got, _ = assign_spt_n30(rows, levels)
    return [got.get(l["level_number"], NO_SPT) for l in levels]


# ------------------------------------------------------------------ helpers


@pytest.mark.parametrize("raw, expected", [
    ("54", "54"), (54, "54"), ("R", "R"), ("r", "R"), ("R (rebuig)", "R"),
    ("40 (suma dels trams centrals 20+20)", "40"), ("--", None), ("", None), (None, None),
    ("MA", None), ("sense registre", None), ("007", "7"),
        ("1/1/1/1", None),   # recompte per tram (MA-1 Anciles), no un N30
        ("30 (12/14/16)", "30"),
    ])
def test_n30_display(raw, expected):
    assert n30_display(raw) == expected


@pytest.mark.parametrize("text, expected", [
    ("-1.00 a -1.20", (1.0, 1.2)), ("-1.00 a 1.60", (1.0, 1.6)), ("-0,80 a -1,40", (0.8, 1.4)),
    ("1.00", (1.0, 1.0)), ("", None), (None, None), ("sense fondària", None),
])
def test_parse_depth_range(text, expected):
    assert parse_depth_range(text) == expected


def test_lithology_overlap_uses_stems_across_gender_and_plural():
    assert lithology_overlap("Arcilla arenosa con gravitas", "Arcillas arenosas con gravitas y bolos") == 3
    assert lithology_overlap("Arena fina-media", "Areniscas, arenas, sustrato") == 1
    assert lithology_overlap("Arena fina-media", "Arcilla limosa y arenosa con algunas gravas") == 0
    assert lithology_overlap("Lutites", "Llims argilosos i sorrencs") == 0


# ------------------------------------------------------------------ els 7 signats


def test_castellar_spt_refuses_column_prints_R():
    levels = [_lv(1, "Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.", 0.0, 1.2)]
    rows = [_spt("SPT-1", "S-1", "-1.00 a -1.20", "R", "Limolites i bretxes")]
    assert _column(levels, rows) == ["R"]


def test_rubi_single_level_takes_the_spt_even_from_another_point():
    levels = [_lv(1, "Graves i sorres, carbonatades", 0.0, 4.55)]
    rows = [_spt("SPT-1", "P-3", "-0.60 a -1.20", "40", "Graves i sorres")]
    assert _column(levels, rows) == ["40"]


def test_bell_lloc_prints_the_spt_n30_not_the_dpsh_average():
    levels = [_lv(1, "Graves en matriu sorrenca carbonatades", 0.0, 1.8)]
    rows = [_spt("SPT-1", "S-1", "-1.00 a 1.60", "54", "Graves en matriu sorrenca")]
    assert _column(levels, rows) == ["54"]


def test_linyola_spt_in_second_level_first_level_blank():
    levels = [_lv(1, "Llims argilosos i sorrencs.", 0.0, 0.9),
              _lv(2, "Lutites i sorrenques alterades, substrat.", 0.9, None)]
    rows = [_spt("SPT-1", "P-3", "-1.00 a -1.15", "R", "Lutites")]
    assert _column(levels, rows) == ["--", "R"]


def test_alcoletge_lithology_sends_the_spt_to_the_second_level():
    # descripcions de la taula geotècnica signada
    levels = [_lv(1, "Sorres argiloses de rebliment", 0.0, 0.5),
              _lv(2, "Lutites i sorrenques alterades", 0.5, None)]
    rows = [_spt("SPT-1", "P-3", "-0.80 a -1.40", "20", "Llims compactes, lutites alterades")]
    assert _column(levels, rows) == ["--", "20"]
    # i amb les de la taula de nivells de sòl (litologia llegida)
    levels2 = [_lv(1, "Reblert superficial", 0.0, 0.5), _lv(2, "Lutites amb intercalacions de sorrenca.", 0.5, None)]
    assert _column(levels2, rows) == ["--", "20"]


def test_anciles_two_equal_spts_in_level_one_and_the_MA_does_not_count():
    levels = [_lv(1, "Arcillas arenosas con gravitas y puntualmente bolos de granito, de coloraciones marrones", 0.0, 2.6),
              _lv(2, "Bolos y gravas de granito en matriz arenosa y arcillosa, de coloraciones grisáceos", 2.6, None)]
    rows = [
        _spt("SPT-1", "S-1", "-1.00 a -1.60", "6", "Arcilla arenosa con gravitas"),
        _spt("SPT-1", "S-2", "-1.00 a -1.60", "6", "Arcilla arenosa con gravitas"),
        _spt("MA-1", "S-2", "-2.80 a -3.00", "--", "Bolos y gravas en matriz arenosa arcillosa"),
    ]
    got, notes = assign_spt_n30(rows, levels)
    assert [got.get(1, NO_SPT), got.get(2, NO_SPT)] == ["6", "--"]
    assert notes == []


def test_vilanova_same_depth_two_points_split_by_lithology():
    """Els dos SPT són a -0,80 a -1,40: la fondària sola els posaria tots dos al nivell 1."""
    levels = [_lv(1, "Arcilla limosa y arenosa con algunas gravas", 0.0, 2.0),
              _lv(2, "Areniscas, arenas, sustrato", 2.0, None)]
    rows = [
        _spt("SPT-1", "P-1", "-0.80 a -1.40", "10", "Arcilla limosa y arenosa con algunas gravas"),
        _spt("SPT-1", "P-3", "-0.80 a -1.40", "24", "Arena fina-media"),
    ]
    assert _column(levels, rows) == ["10", "24"]


# ------------------------------------------------------------------ regles de contorn


def test_no_spt_rows_means_dashes_everywhere():
    levels = [_lv(1, "Llims", 0.0, 1.0), _lv(2, "Graves", 1.0, None)]
    assert _column(levels, []) == ["--", "--"]
    # la fila única buida de la via B (sense SPT al projecte)
    assert _column(levels, [_spt("", "", "", "", "")]) == ["--", "--"]


def test_depth_decides_when_lithology_ties():
    levels = [_lv(1, "Graves amb sorres", 0.0, 1.0), _lv(2, "Graves amb sorres cimentades", 1.0, None)]
    rows = [_spt("SPT-1", "S-1", "-1.40 a -2.00", "31", "Graves amb sorres")]
    assert _column(levels, rows) == ["--", "31"]


def test_unassignable_spt_is_reported_not_guessed():
    levels = [_lv(1, "Llims", 0.0, 1.0), _lv(2, "Argiles", 1.0, None)]
    rows = [_spt("SPT-1", "S-1", "", "18", "Graves")]  # ni litologia ni fondària
    got, notes = assign_spt_n30(rows, levels)
    assert got == {}
    assert len(notes) == 1 and "18" in notes[0]


def test_two_spts_with_different_values_print_first_and_note():
    levels = [_lv(1, "Graves", 0.0, None)]
    rows = [_spt("SPT-1", "S-1", "-1.00 a -1.60", "12", "Graves"),
            _spt("SPT-2", "S-2", "-1.00 a -1.60", "19", "Graves")]
    got, notes = assign_spt_n30(rows, levels)
    assert got == {1: "12"}
    assert len(notes) == 1 and "19" in notes[0]


def test_numeric_depths_from_via_b_row_are_accepted():
    levels = [_lv(1, "Llims", 0.0, 1.0), _lv(2, "Lutites", 1.0, None)]
    rows = [{"test_id": "SPT-1", "location": "S-1", "depth_from_m": 1.0, "depth_to_m": 1.6, "n30": 20, "lithology": ""}]
    assert _column(levels, rows) == ["--", "20"]


def test_levels_as_objects_with_attributes():
    class L:
        def __init__(self, n, d, a, b):
            self.level_number, self.description, self.depth_from_m, self.depth_to_m = n, d, a, b
    levels = [L(1, "Graves i sorres", 0.0, None)]
    got, _ = assign_spt_n30([_spt("SPT-1", "P-3", "-0.60 a -1.20", "40", "Graves i sorres")], levels)
    assert got == {1: "40"}
