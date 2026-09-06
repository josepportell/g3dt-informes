"""P2b UI (2026-09-06): la nota del nivell portant i de la Df que el wizard mostra sota «Profunditat fonamentacio»."""
from web.wizard_service import bearing_note


def test_bearing_note_names_level_and_df():
    txt = bearing_note(0, "Graves incloses en matriu sorrenca d'aspectes carbonatats", 2, 0.3, "user_data.json anterior")
    assert txt.startswith("Nivell portant: 1/2 «Graves incloses en matriu sorrenca d'aspectes carbonatats» · Df = 0,30 m")
    assert "⚠" not in txt and "Df + 0,2 m" in txt


def test_bearing_note_warns_when_df_is_the_default_prefill():
    for src in (None, "", "default", "estandard G3", "valor per defecte"):
        assert "⚠ Df per defecte" in bearing_note(1, "Gresos", 2, 0.8, src), src
    assert "⚠" not in bearing_note(1, "Gresos", 2, 1.0, "user")


def test_bearing_note_truncates_long_descriptions_and_handles_no_layers():
    long = "x" * 100
    txt = bearing_note(2, long, 3, 1.4, "user")
    assert "«" + "x" * 70 + "…»" in txt and "3/3" in txt and "Df = 1,40 m" in txt
    assert bearing_note(None, "", 0, 0.8, "user").startswith("Nivell portant: únic")
