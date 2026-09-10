"""P2a + P2b — el nivell portant és el que la sabata ASSOLEIX a Df (+ encastament), mai més profund.

Evidència: la frase del Qa dels 7 informes signats (`docs/RECERCA-CRITERIS-DESCRITS-ALS-INFORMES-2026-09-03.md`):
  Bell-lloc, Rubí, Castellar, Vilanova → primer nivell («un cop sanejat el tram superficial»);
  Linyola, Anciles → segon nivell amb POUS («encastats 20-40 cm en els materials del segon nivell sanejat»);
  Alcoletge → segon nivell (el primer és rebliment).
Quan la fonamentació baixa a un segon nivell és una decisió de l'Eva: entra per `foundation_depth_m`.
Geometria de capes: `sondeig_extracted.json` (Castellar, Rubí, Bell-lloc) i or de taules (la resta).
"""

from __future__ import annotations

import pytest

from automation.dpsh_extractor import DPSHData, DPSHReading, DPSHTest
from automation.report_data import (
    DEFAULT_FOUNDATION_DEPTH_M, EMBEDMENT_MIN_M, _bearing_stratum_n20, _generate_soil_levels,
    _select_bearing_layer_idx, foundation_depth_from_user_data,
)


def _dpsh(pairs):
    return DPSHData(expedient="T", tests=[DPSHTest(test_id="P-1", readings=[
        DPSHReading(depth_m=-d, n20=int(n), nb=n / 0.83) for d, n in pairs])])


def _L(d_from, d_to, desc, n20=None, gl=None):
    d = {"depth_from_m": d_from, "depth_to_m": d_to, "description": desc}
    if n20 is not None:
        d["n20_average"] = n20
    if gl is not None:
        d["geological_level"] = gl
    return d


# ------------------------------------------------------------------ Df del wizard


@pytest.mark.parametrize("raw, expected", [
    (None, (DEFAULT_FOUNDATION_DEPTH_M, True)), ("", (DEFAULT_FOUNDATION_DEPTH_M, True)),
    (0, (DEFAULT_FOUNDATION_DEPTH_M, True)), ("abc", (DEFAULT_FOUNDATION_DEPTH_M, True)),
    (0.3, (0.3, False)), ("1,0", (1.0, False)), ("0.3 m", (0.3, False)), (2, (2.0, False)),
])
def test_foundation_depth_from_user_data(raw, expected):
    assert foundation_depth_from_user_data({"foundation_depth_m": raw}) == expected


def test_embedment_is_the_signed_minimum():
    assert EMBEDMENT_MIN_M == 0.2  # «encastada entre 20-40 cm»


# ------------------------------------------------------------------ els 7 signats

RUBI = [_L(0.0, 3.35, "Graves i sorres (Nivell 1)", 40, 1),
        _L(3.35, 4.55, "Gresos amb intercalacions de trams de lutites de color vermellós", 45, 2)]
CASTELLAR = [_L(0.0, 0.5, "Terra argilosa amb llims sense graves", 10, 1),
             _L(0.5, 1.2, "Roca / material dur (roca pochimada)", 30, 1)]
BELL_LLOC = [_L(0.0, 1.0, "Graves carbonatades", 30, 1), _L(1.0, 1.8, "Graves con arena carbonatada", 50, 1)]
LINYOLA = [_L(0.0, 1.4, "Llims argilosos i sorrencs", 11, 1), _L(1.4, 2.9, "Lutites i sorrenques, substrat", 30, 2)]
ALCOLETGE = [_L(0.0, 1.4, "Rebliment antròpic", 3, 1), _L(1.4, None, "Lutites, substrat", 20, 2)]
ANCILES = [_L(0.0, 2.6, "Arcillas limosas y arenosas con puntualmente gravitas", 4, 1),
           _L(2.6, 5.9, "Bolos y gravas de granito en matriz arenosa y arcillosa", 12, 2)]
VILANOVA = [_L(0.0, 0.85, "Arcilla limosa y arenosa con algunas gravas", 8, 1),
            _L(0.85, 3.78, "Arenas finas-medias, carbonatadas", 45, 2)]


def test_rubi_footing_at_1m_rests_on_the_gravels_not_the_sandstone():
    """Signat: «encastada entre 30-40 cm en els materials del primer nivell sanejat» → graves."""
    assert _select_bearing_layer_idx(RUBI, foundation_depth=1.0) == 0
    # només amb pous fins al substrat (Df ≥ 3,15) el portant són els gresos
    assert _select_bearing_layer_idx(RUBI, foundation_depth=3.2) == 1


def test_castellar_cover_is_skipped_and_the_rock_bears():
    """Sabata a 0,3 m: la capa 0-0,5 acaba a 0,5 ≤ 0,3 + 0,2 → no carrega; roca."""
    assert _select_bearing_layer_idx(CASTELLAR, foundation_depth=0.3) == 1


def test_bell_lloc_single_geological_level_first_layer_bears():
    assert _select_bearing_layer_idx(BELL_LLOC, foundation_depth=0.3) == 0


def test_vilanova_footing_rests_on_the_clay_not_the_sandstone_below():
    """Signat: primer nivell (argila llimosa, φ 25°, Qa 2,5): «el competent més profund» ho trencava."""
    assert _select_bearing_layer_idx(VILANOVA, foundation_depth=0.3) == 0


def test_alcoletge_fill_is_skipped_whatever_df():
    assert _select_bearing_layer_idx(ALCOLETGE, foundation_depth=0.3) == 1
    assert _select_bearing_layer_idx(ALCOLETGE, foundation_depth=1.0) == 1


def test_linyola_and_anciles_need_the_pile_depth_from_eva():
    """Amb pous el signat va al segon nivell; sense la Df dels pous el codi es queda al primer.
    No és un error del codi: la decisió (pous vs sabates) és de l'Eva i entra per `foundation_depth_m`."""
    assert _select_bearing_layer_idx(LINYOLA, foundation_depth=0.3) == 0
    assert _select_bearing_layer_idx(LINYOLA, foundation_depth=1.7) == 1   # pous 20-40 cm dins L2
    assert _select_bearing_layer_idx(ANCILES, foundation_depth=0.3) == 0
    assert _select_bearing_layer_idx(ANCILES, foundation_depth=2.9) == 1


# ------------------------------------------------------------------ col·lapse i N20 del portant


def test_collapse_to_single_level_describes_and_measures_the_bearing_layer():
    """Rubí amb num_soil_levels=1: descripció, tipus i N20 de les graves (0-3,35), no dels gresos."""
    dpsh = _dpsh([(d / 10, 35) for d in range(2, 34, 2)] + [(d / 10, 60) for d in range(34, 46, 2)])
    levels = _generate_soil_levels(dpsh, 1, RUBI, ["granular"], foundation_depth=1.0)
    assert len(levels) == 1
    assert levels[0].description.startswith("Graves i sorres")
    assert levels[0].soil_type == "granular"
    assert abs(levels[0].n20_average - 35.0) < 0.01      # només lectures 0-3,35 (límit superior aplicat)
    assert levels[0].n20_max == 35
    # abans (capa més profunda): «Gresos…», N20 60
    deep = _generate_soil_levels(dpsh, 1, RUBI, ["granular"], foundation_depth=3.2)
    assert deep[0].description.startswith("Gresos")
    assert abs(deep[0].n20_average - 60.0) < 0.01


def test_bearing_stratum_n20_uses_only_the_bearing_layer_when_it_is_not_the_deepest():
    dpsh = _dpsh([(0.5, 20), (1.5, 30), (2.5, 40), (3.5, 90), (4.0, 95)])
    assert abs(_bearing_stratum_n20(dpsh, RUBI, None, foundation_depth=1.0) - 30.0) < 0.01
    # portant = capa més profunda → sense límit superior (comportament de sempre)
    assert abs(_bearing_stratum_n20(dpsh, RUBI, None, foundation_depth=3.2) - 92.5) < 0.01


def test_default_df_keeps_legacy_behaviour_when_wizard_is_silent():
    """Sense Df: 0,8 + 0,2 = 1,0 → una capa que acaba a 1,0 no carrega (com la regressió de Bell-lloc real)."""
    assert _select_bearing_layer_idx(BELL_LLOC) == 1
    assert _select_bearing_layer_idx(BELL_LLOC, foundation_depth=DEFAULT_FOUNDATION_DEPTH_M) == 1


def test_all_layers_above_df_fall_back_to_deepest():
    assert _select_bearing_layer_idx(CASTELLAR, foundation_depth=5.0) == 1
