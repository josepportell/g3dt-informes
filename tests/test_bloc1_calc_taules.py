"""Bloc 1 (2026-09-07) — càlcul i taules dels projectes SENSE sondeig: P5, P6, CTE, rang de taules, data, assentament.

Evidència: `docs/PLA-QUE-QUEDA-DESPRES-DE-A-B-I-NARRATIVA-2026-09-07.md` §Bloc 1 i DECISION-LOG 2026-09-06 (vespre),
«Troballes de M341» 1-3. Cap crida externa.
"""
from __future__ import annotations

import pytest

from automation.cte_classifier import classify_soil, parse_floor_count
from automation.cte_geomech import detect_soil_type, is_rock
from automation.dpsh_extractor import DPSHData, DPSHReading, DPSHTest, format_dates_catalan
from automation.lectura.tables_report import depth_from_cell, sondeig_layers_from_levels
from automation.report_data import (
    _determine_soil_class, _generate_soil_levels, _select_bearing_layer_idx, lectura_sondeig_layers,
)
from automation.report_generator import ReportGenerator, insitu_table_range
from automation.settlement_criteria import SENTENCE_GRANULAR_ALT, settlement_by_criteria
from automation.terzaghi_calculator import FootingShape, TerzaghiCalculator


def _dpsh(pairs, test_id="P-1"):
    return DPSHData(expedient="T", tests=[DPSHTest(test_id=test_id, readings=[
        DPSHReading(depth_m=-d, n20=int(n), nb=n / 0.83) for d, n in pairs])])


# ------------------------------------------------------------------ P6: un sol classificador de sòl


@pytest.mark.parametrize("description, expected", [
    # els 4 projectes sense sondeig, tal com ho llegeix la via A
    ("Llims argilsoso i sorrencs", "limo"),                          # Linyola 1 (abans: limo)
    ("Lutites i sorrenques, Substrat", "rock"),                      # Linyola 2 (abans: arena!)
    ("Rebliment antròpic", "granular"),                               # Alcoletge 1
    ("Lutites, substrat", "rock"),                                    # Alcoletge 2 (abans: granular!)
    ("Arcilla limosa y arenosa con algunas gravas.", "arcilla"),      # Vilanova 1 (abans: grava!)
    ("Arenas finas-medias, carbonatadas.", "arena"),                  # Vilanova 2
    ("Arcillas arenosas con puntualmente bolos", "arcilla"),          # Anciles 1 (abans: granular!)
    ("Bolos y gravas en matriz arenosa y arcillosa", "grava"),        # Anciles 2
    # els 3 amb sondeig i el vocabulari de sempre
    ("Graves i sorres", "grava"), ("Graves en matriu sorrenca", "grava"), ("Graves carbonatades", "grava"),
    ("Substrat rocós. Bretxes amb intercalacions de lutites i gresos vermells.", "rock"),
    ("Sorra fina-mitja, compacta", "arena"), ("Sorra limosa", "arena_limosa"),
    ("Sorres argiloses", "arena_limosa"),   # l'àncora de 28° de l'Eva (transicional), no «arena» neta
    ("Sorres argiloses de rebliment", "arena"),   # rebliment: el material del rebliment
    ("Terra vegetal", "granular"), ("", "granular"),
    ("marga tova", "limo"), ("Margues", "rock"), ("Areniscas, arenas, sustrato", "rock"),
])
def test_detect_soil_type_delegates_to_the_criteria_classifier(description, expected):
    assert detect_soil_type(description) == expected


def test_is_rock_reads_spanish_and_spares_soft_marls():
    assert is_rock(10, "Areniscas, arenas, sustrato")
    assert is_rock(10, "Brecha con matriz arenosa") and is_rock(10, "Lutitas alteradas")
    assert not is_rock(10, "margues toves") and not is_rock(10, "margas blandas")
    assert is_rock(100, "el que sigui")  # el rebuig continua sent roca


@pytest.mark.parametrize("soil_type, fires", [("granular", True), ("grava", True), ("arena", True),
                                              ("arena_limosa", False), ("limo", False), ("cohesive", False), (None, False)])
def test_dense_granular_cap_fires_for_every_granular_type(soil_type, fires):
    """Rubí: el detector diu «grava» a «Graves i sorres» i el topall 3,5 no disparava (3,0; signat 3,5)."""
    r = TerzaghiCalculator(phi=39, cohesion=0.05, gamma=2.0).calculate_qa(
        B=1.0, Df=1.0, shape=FootingShape.SQUARE, nspt=47, is_granular=True, soil_type=soil_type)
    assert r.Qa == pytest.approx(3.5 if fires else 3.0)


# ------------------------------------------------------------------ P5: geometria des de la lectura

LINYOLA = [
    {"name": "Nivell 1", "litologia": "Llims argilsoso i sorrencs", "de": "0,00",
     "a": "≈-1,4 m a P-1 (contacte ≈243,6 msnm)"},
    {"name": "Nivell 2", "litologia": "Lutites i sorrenques, Substrat",
     "de": "mateix contacte que 'a' del Nivell 1 (≈-1,4 m a ≈-0,3 m segons el punt) (cota 243,6, 244,7 msnm)",
     "a": "fins al fons d'investigació (rebuig DPSH: -2,90/-2,15/-1,75 m per punt)"},
]
VILANOVA = [
    {"name": "1er nivell", "litologia": "Arcilla limosa y arenosa con algunas gravas.", "de": "0,00", "a": None},
    {"name": "2on nivell", "litologia": "Arenas finas-medias, carbonatadas.", "de": None,
     "a": "fins al fons d'investigació (rebuig DPSH: -1,48/-2,18/-3,78 m per punt)"},
]


@pytest.mark.parametrize("cell, expected", [
    ("0,00", 0.0), ("≈-1,4 m a P-1 (contacte ≈243,6 msnm)", 1.4), (1.4, 1.4), (None, None), ("Si", None),
    ("fins al fons d'investigació (rebuig DPSH: -2,90/-2,15 m)", None), ("243,6 msnm", None),
])
def test_depth_from_cell(cell, expected):
    assert depth_from_cell(cell) == expected


def test_linyola_levels_give_two_layers_with_one_contact_and_an_open_bottom():
    layers = sondeig_layers_from_levels(LINYOLA)
    assert [(l["depth_from_m"], l["depth_to_m"]) for l in layers] == [(0.0, 1.4), (1.4, None)]
    assert [l["description"] for l in layers] == ["Llims argilsoso i sorrencs", "Lutites i sorrenques, Substrat"]
    assert all(l["source"] == "lectura" and l["soil_type"] is None for l in layers)


def test_missing_contact_is_never_invented():
    """Vilanova/Anciles: el tall no imprimeix el contacte → cap geometria (el segmentador continua manant)."""
    assert sondeig_layers_from_levels(VILANOVA) == []
    assert sondeig_layers_from_levels(LINYOLA[:1]) == []          # un sol nivell: res a geometritzar
    assert sondeig_layers_from_levels([LINYOLA[1]]) == []          # numeració amb forat (només el 2)
    assert sondeig_layers_from_levels(None) == []
    bad = [dict(LINYOLA[0], a="2,0"), dict(LINYOLA[1], de="1,0", a="1,5")]   # base ≤ sostre → invàlid
    assert sondeig_layers_from_levels(bad) == []


def test_next_level_top_follows_the_previous_bottom_when_they_disagree():
    rows = [dict(LINYOLA[0], a="1,4"), dict(LINYOLA[1], de="1,2")]
    layers = sondeig_layers_from_levels(rows)
    assert layers[1]["depth_from_m"] == 1.4
    rows = [dict(LINYOLA[0], a=None), dict(LINYOLA[1], de="1,2")]   # base absent → sostre del següent
    assert sondeig_layers_from_levels(rows)[0]["depth_to_m"] == 1.2


def test_lectura_layers_carry_the_dpsh_n20_and_pick_the_lutites_at_the_signed_df():
    """Linyola: pous a 1,7 → el portant és el 2n nivell (lutites, roca), no un «Llims» 0-3,0 col·lapsat."""
    dpsh = _dpsh([(0.4, 8), (0.8, 10), (1.2, 12), (1.6, 25), (2.0, 30), (2.4, 40), (2.8, 110)])
    ud = {"lectura_tables": {"soil_levels": LINYOLA}, "num_soil_levels": 2}
    layers = lectura_sondeig_layers(ud, None, dpsh)
    assert layers[0]["n20_average"] == pytest.approx(10.0) and layers[1]["n20_average"] == pytest.approx(31.6667, abs=1e-3)
    assert _select_bearing_layer_idx(layers, [detect_soil_type(l["description"]) for l in layers], foundation_depth=1.7) == 1
    assert detect_soil_type(layers[1]["description"]) == "rock"
    assert lectura_sondeig_layers({}, None, dpsh) == []   # sense taula, sense projecte: res


def test_last_open_level_thickness_is_the_investigated_depth_with_a_star():
    """Linyola signat: 1 | Tipus IV | 1.60 | 2.0 · 2 | Tipus II | 1.30* | 1.3 (2,90 − 1,60). Aquí 2,8 − 1,4."""
    dpsh = _dpsh([(0.4, 8), (0.8, 10), (1.2, 12), (1.6, 25), (2.0, 30), (2.4, 40), (2.8, 110)])
    layers = sondeig_layers_from_levels(LINYOLA)
    levels = _generate_soil_levels(dpsh, 2, layers, ["limo", "rock"], foundation_depth=1.7)
    assert levels[0].thickness_m == pytest.approx(1.4) and levels[0].thickness_open is False
    assert levels[1].thickness_m == pytest.approx(1.4) and levels[1].thickness_open is True
    assert levels[1].depth_to_m is None


# ------------------------------------------------------------------ CTE, rang de taules, data, assentament


def test_cte_soil_is_t1_by_default_everywhere():
    """6/6 signats amb taula CTE escriuen T-1, també amb rebliment (Alcoletge) i N20 < 10."""
    assert classify_soil() == "T-1" and classify_soil(has_fill=True) == "T-1" and classify_soil(average_n20=3) == "T-1"
    assert _determine_soil_class(None) == "T-1"
    assert _determine_soil_class(_dpsh([(0.2, 2), (0.4, 3)])) == "T-1"


@pytest.mark.parametrize("floors, count", [("PB+1", 2), ("Pb + 1", 2), ("Pb+1Pp", 2), ("PB (planta baixa, 1 nivell)", 1),
                                           ("PB + Porxo", 1), ("PB+1PP amb dos semisòtans", 2), ("Pb", 1)])
def test_floor_count_reads_the_bare_plus_number(floors, count):
    """Castellar: el plànol llegit diu «PB+1» on l'Eva escriu «Pb+1Pp» → 2 plantes → C-1 (signat)."""
    assert parse_floor_count(floors) == count


@pytest.mark.parametrize("has_sondeig, lang, expected", [(False, "ca", "3 i 4"), (True, "ca", "3, 4 i 5"),
                                                         (False, "es", "3 y 4"), (True, "es", "3, 4 y 5")])
def test_insitu_table_range_counts_tables_not_tests(has_sondeig, lang, expected):
    """7/7 signats: «Taula 3 i 4» sense sondeig (Rubí amb 3 DPSH), «3, 4 i 5» amb sondeig (Bell-lloc amb 2 DPSH)."""
    text, last = insitu_table_range(has_sondeig, lang=lang)
    assert text == expected and last == (5 if has_sondeig else 4)
    assert insitu_table_range(False, has_spt_table=False) == ("3", 3)


def _gen(user_data):
    g = object.__new__(ReportGenerator)
    g.user_data, g.warnings, g.report_data = user_data, [], None
    return g


def test_signature_date_comes_from_the_wizard_in_the_field_date_format():
    from datetime import date
    assert _gen({"data_signatura": "2025-10-29"})._signature_date() == date(2025, 10, 29)
    assert _gen({"data_signatura": "17/12/2025"})._signature_date() == date(2025, 12, 17)
    g = _gen({"data_signatura": "ahir"})
    assert g._signature_date() == date.today() and g.warnings
    assert _gen({})._signature_date() == date.today()
    assert format_dates_catalan(["2025-10-29"]) == "29 d'octubre de 2025"   # com la signa l'Eva, no «29 de octubre»


def test_settlement_keeps_the_bell_lloc_wording_as_a_candidate():
    sc = settlement_by_criteria(q_net=3.0, B=1.0, Df=0.3, gamma=2.0, nb=25, n_spt=54, regime="granular")
    assert not sc.generic and len(sc.sentence_candidates) == 2
    assert sc.sentence_candidates[0] == sc.sentence
    assert sc.sentence_candidates[1] == SENTENCE_GRANULAR_ALT.format(s=f"{sc.settlement_cm:.2f}")
    assert "inferiors a" in sc.sentence_candidates[1] and "iguals o" not in sc.sentence_candidates[1]
    generic = settlement_by_criteria(q_net=3.0, B=1.0, Df=0.3, gamma=2.2, nb=20, regime="roca")
    assert generic.sentence_candidates == [generic.sentence]


# ------------------------------------------------------------------ arranjaments de la primera mesura (bloc1a → bloc1b)


def test_a_fill_is_never_dense_because_of_a_refusal_at_the_contact():
    """Alcoletge P-2 rebutja a 1,30 amb el contacte rebliment/lutites a 1,2-1,4 segons el punt: signat Tipus IV, «5-0»."""
    from automation.geotech_criteria import geotech_by_criteria
    crit = geotech_by_criteria(5.9, 4.9, "granular", "Rebliment antròpic", refusal=True)
    assert crit.klass == "rebliment" and crit.regime == "fluix" and crit.seismic_type == "Tipus IV"
    assert any("rebliment" in n for n in crit.notes)
    gravel = geotech_by_criteria(26.3, 21.8, "grava", "Bolos y gravas en matriz arenosa", refusal=True)
    assert gravel.klass == "grava" and gravel.regime == "dens" and gravel.seismic_type == "Tipus II"


def test_open_thickness_is_refreshed_with_the_printed_refusal_depth(tmp_path):
    """Alcoletge: l'Excel arriba a 1,80 (tram de 0,20) però la fila DPSH impresa diu −1,69 → 1,69 − 1,40 = 0,29* (signat)."""
    from automation.report_data import SoilLevel
    g = ReportGenerator(project_path=tmp_path, user_data={"lectura_tables": {"dpsh_tests": [
        {"test_id": "P-1", "depth": "-1.60"}, {"test_id": "P-3", "depth": "-1.69"}]}})
    lv1 = SoilLevel(1, "Rebliment antròpic", 1.4, 4.9, 0.0, 1.4)
    lv2 = SoilLevel(2, "Lutites, substrat", 0.4, 20.0, 1.4, None, thickness_open=True)

    class _RD:
        soil_levels = [lv1, lv2]
        dpsh = None
    g.report_data = _RD()
    g._refresh_open_thickness()
    assert lv2.thickness_m == pytest.approx(0.29) and lv1.thickness_m == pytest.approx(1.4)


def test_segmenter_layers_take_the_read_lithology_when_level_counts_match():
    """Vilanova: el segmentador no sap litologies (descripció buida → cap senyal «llim» → φ 28 en lloc de 25)."""
    from automation.report_data import _annotate_layers_with_lectura_lithology
    layers = [{"depth_from_m": 0.0, "depth_to_m": 0.8, "description": ""}, {"depth_from_m": 0.8, "depth_to_m": None, "description": ""}]
    _annotate_layers_with_lectura_lithology(layers, {"lectura_tables": {"soil_levels": VILANOVA}}, None)
    assert [l["description"] for l in layers] == ["Arcilla limosa y arenosa con algunas gravas.", "Arenas finas-medias, carbonatadas."]
    three = layers + [{"depth_from_m": 3.0, "depth_to_m": None, "description": ""}]
    _annotate_layers_with_lectura_lithology(three, {"lectura_tables": {"soil_levels": VILANOVA}}, None)
    assert three[2]["description"] == ""   # 3 capes ↔ 2 nivells: no s'alinea res


def test_section3_survives_an_open_bottom_last_level():
    """bloc1a: «unsupported format string passed to NoneType.__format__» a 4/7 projectes (gruix conegut, base None)."""
    from automation.report_data import SoilLevel
    from automation.sections.section3_geologia import Section3Generator
    levels = [SoilLevel(1, "Llims argilosos", 1.4, 10.0, 0.0, 1.4, soil_type="limo"),
              SoilLevel(2, "Lutites, substrat", 1.5, 30.0, 1.4, None, soil_type="rock", thickness_open=True)]

    class _RD:
        soil_levels = levels
        dpsh = _dpsh([(0.4, 8), (1.6, 25), (2.8, 110)])
        municipality = "Linyola"
    gen = Section3Generator.__new__(Section3Generator)
    gen.data = _RD()
    texts = gen.generate_depth_texts()
    assert len(texts) == 2 and "com a mínim 1.50 metres" in texts[1] and "1.40 metres" in texts[0]
