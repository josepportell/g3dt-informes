"""Assentament per CRITERI (2026-09-06): frase per règim, valor < 1,0 → genèrica, Es amb candidats (SPT → Nb → E)."""
import zipfile
from pathlib import Path

import pytest

from automation.settlement_criteria import (
    SENTENCE_GENERIC, alternatives_for_wizard, calc_note, parse_spt_n, round_settlement, settlement_by_criteria,
    settlement_regime,
)

REPO = Path(__file__).resolve().parents[1]


def test_regime_from_class_cohesion_and_criteria_regime():
    assert settlement_regime("grava", 0.0, "dens") == "granular"
    assert settlement_regime("sorra", 0.05, "mitja") == "granular"
    assert settlement_regime("bolos" if False else "grava", 0.0, None) == "granular"
    assert settlement_regime("transicional", 0.05, "mitja") == "cohesiu"     # Vilanova: llims argilosos → genèrica
    assert settlement_regime("argila", 0.10, "fluix") == "cohesiu"           # Anciles L1
    assert settlement_regime("roca", 1.0, "roca") == "roca"                  # Castellar
    assert settlement_regime("grava", 1.0, "dens") == "roca", "c ≥ 0,5 mana"
    assert settlement_regime(None, None, None) == "granular"


def test_bell_lloc_signed_form_with_spt_n_of_the_level():
    """Bell-lloc signat: Nb 25-R, N (SPT) 54, Qa 3,0, Df 0,3, γ 2,0 → «iguals o inferiors a 1.20 cm, immediats…»."""
    sc = settlement_by_criteria(q_net=3.0, B=1.0, Df=0.3, gamma=2.0, nb=25.0, n_spt=54, E=650, regime="granular")
    assert sc.regime == "granular" and not sc.generic
    assert sc.Es == 135.0 and sc.Es_source.startswith("2,5 × colpeig (Nspt")
    assert sc.settlement_cm == 1.2
    assert sc.sentence == ("Els assentaments màxims previstos per la càrrega recomanada anteriorment seran iguals o inferiors "
                           "a 1.20 cm, immediats en el temps donat el comportament granular dels materials.")
    assert [c.display for c in sc.candidates] == ["Es=135 (2.5×N SPT 54)", "Es=62 (2.5×Nb 25.0)", "Es=650 (E del criteri)"]
    assert [c.settlement_cm for c in sc.candidates] == [1.2, 2.5, 0.2]
    alts = alternatives_for_wizard(sc)
    assert [a["value"] for a in alts] == [62, 650] and "→ 2.50 cm" in alts[0]["source"]


def test_rubi_without_spt_uses_nb_and_castellar_rock_is_generic():
    rubi = settlement_by_criteria(q_net=3.5, B=1.0, Df=1.0, gamma=2.0, nb=47.0, n_spt=None, E=450, regime="granular")
    assert rubi.Es == pytest.approx(117.5) and rubi.settlement_cm == 1.5 and "1.50 cm" in rubi.sentence
    cast = settlement_by_criteria(q_net=3.0, B=1.0, Df=0.3, gamma=2.2, nb=27.2, n_spt=None, E=500, regime="roca")
    assert cast.generic and cast.sentence == SENTENCE_GENERIC and cast.settlement_cm is not None
    assert cast.notes[0].startswith("nivell portant roca")
    coh = settlement_by_criteria(q_net=2.5, B=1.0, Df=0.5, gamma=1.9, nb=15.0, n_spt=None, E=100, regime="cohesiu")
    assert coh.generic and coh.regime == "cohesiu"


def test_small_settlement_is_generic_and_large_one_warns():
    small = settlement_by_criteria(q_net=3.0, B=1.0, Df=0.3, gamma=2.0, nb=80.0, n_spt=None, E=500, regime="granular")
    assert small.settlement_cm < 1.0 and small.generic and small.sentence == SENTENCE_GENERIC
    big = settlement_by_criteria(q_net=3.0, B=1.0, Df=0.3, gamma=2.0, nb=10.0, n_spt=None, E=100, regime="granular")
    assert big.settlement_cm > 2.54 and any(n.startswith("⚠") and "2.54" in n for n in big.notes)


def test_wizard_override_wins_and_duplicates_collapse():
    sc = settlement_by_criteria(q_net=3.0, B=1.0, Df=0.3, gamma=2.0, nb=54.0, n_spt=54, E=450, regime="granular", Es_override=200)
    assert sc.Es == 200 and sc.Es_source == "wizard: Es assentament"
    assert [c.display for c in sc.candidates] == ["Es=200 (escrit al wizard)", "Es=135 (2.5×N SPT 54)", "Es=450 (E del criteri)"]
    none = settlement_by_criteria(q_net=3.0, B=1.0, Df=0.3, gamma=2.0, nb=None, n_spt=None, E=None, regime="granular")
    assert none.Es is None and none.settlement_cm is None and none.generic and none.sentence == SENTENCE_GENERIC


def test_helpers_and_notes():
    assert parse_spt_n("54") == 54 and parse_spt_n("R") is None and parse_spt_n("--") is None and parse_spt_n(None) is None
    assert round_settlement(1.15) == 1.2 and round_settlement(1.075) == 1.1 and round_settlement(2.78) == 2.8
    sc = settlement_by_criteria(q_net=3.0, B=1.0, Df=0.3, gamma=2.0, nb=25.0, n_spt=54, E=650, regime="granular")
    s_note, es_note = calc_note(sc, 1.0)
    assert s_note.startswith("Schmertmann Es=135 (2.5×N SPT 54), B=1 m → 1.20 cm · règim granular → «iguals o inferiors a 1.20 cm»")
    assert "alt: Es=62 (2.5×Nb 25.0) → 2.50 cm, Es=650 (E del criteri) → 0.20 cm" in s_note
    assert es_note.startswith("Es=135 (2.5×N SPT 54) · 2,5 × colpeig")


def test_template_prints_the_sentence_variable_not_a_fixed_phrase():
    xml = zipfile.ZipFile(REPO / "templates" / "g3dt-jinja-template.docx").read("word/document.xml").decode("utf-8")
    assert xml.count("{{ settlement_sentence }}") == 1
    assert "{{ settlement }}" not in xml and "immediats en el temps donat el comportament granular" not in xml


def test_result_dataclass_formats_the_criteria_sentence():
    from automation.terzaghi_calculator import BearingCapacityResult, FootingShape
    r = BearingCapacityResult(phi=38, cohesion=0.0, gamma=2.0, B=1.0, Df=0.3, L=None, shape=FootingShape.SQUARE,
                              Nc=1, Nq=1, Ngamma=1, sc=1, sq=1, sgamma=1, qu=9.0, safety_factor=3.0, Qa=3.0,
                              settlement_cm=1.2, settlement_sentence=SENTENCE_GENERIC)
    assert r.format_settlement_for_report() == SENTENCE_GENERIC
    r.settlement_sentence = ""
    assert r.format_settlement_for_report().endswith("inferiors a 1.20 cm, immediats en el temps")
