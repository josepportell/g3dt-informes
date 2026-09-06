"""M341 (2026-09-06): una última capa SENSE base (`depth_to_m: None`, segmentador DPSH / lectura «fins al fons») no ha de
fer caure `_generate_soil_levels` (Alcoletge: TypeError '<=' entre float i None) i compta les lectures fins al fons."""
from automation.dpsh_extractor import DPSHData, DPSHReading, DPSHTest
from automation.report_data import _generate_soil_levels


def _dpsh(pairs):
    return DPSHData(expedient="T", tests=[DPSHTest(test_id="P-1", readings=[
        DPSHReading(depth_m=-d, n20=int(n), nb=n / 0.83) for d, n in pairs])])


def test_open_bottom_last_layer_is_counted_to_the_end_and_does_not_crash():
    layers = [{"depth_from_m": 0.0, "depth_to_m": 1.4, "description": "Rebliment antròpic"},
              {"depth_from_m": 1.4, "depth_to_m": None, "description": "Lutites, substrat"}]
    dpsh = _dpsh([(0.4, 3), (0.8, 4), (1.2, 5), (1.6, 20), (2.0, 30), (2.4, 110)])
    levels = _generate_soil_levels(dpsh, 2, layers, ["granular", "granular"], foundation_depth=1.0)
    assert [l.level_number for l in levels] == [1, 2]
    assert levels[1].depth_to_m is None and levels[1].thickness_m is None
    assert abs(levels[1].n20_average - 25.0) < 0.01, "lectures 1,6-2,0 (el rebuig 110 exclòs), fins al fons"
    assert levels[0].depth_to_m == 1.4 and abs(levels[0].n20_average - 4.0) < 0.01
