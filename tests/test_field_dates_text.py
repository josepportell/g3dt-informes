"""Data doble de la campanya (Josep 2026-09-05): la primera ranura de l'informe porta el primer dia, la segona tots.

Signats: Bell-lloc «El dia 1 d'octubre de 2025, es va visitar l'obra» / «la campanya de camp, que s'ha realitzat el dia
1 i 6 d'octubre de 2025»; Linyola i Castellar (un sol dia) les dues iguals."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation.dpsh_extractor import first_field_day_text, format_dates_catalan  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("dates, text, expected", [
    (["2025-10-06", "2025-10-01"], "", "1 d'octubre de 2025"),
    (["2025-10-01"], "", "1 d'octubre de 2025"),
    ([], "1 i 6 d'octubre de 2025", "1 d'octubre de 2025"),
    ([], "1, 2 i 6 de març de 2026", "1 de març de 2026"),
    (None, "1 d'octubre i 15 de novembre de 2025", "1 d'octubre de 2025"),
    (None, "24 de octubre de 2025", "24 de octubre de 2025"),   # un sol dia (tal com l'escriu la via B): intacte
    (None, "", ""),
])
def test_first_field_day_text(dates, text, expected):
    assert first_field_day_text(dates, text) == expected


def test_format_dates_catalan_two_days_same_month():
    assert format_dates_catalan(["2025-10-01", "2025-10-06"]) == "1 i 6 d'octubre de 2025"


def test_template_has_one_slot_per_variable():
    """La plantilla: «El dia {{ data_camp_inici_text }}» (primer dia) i «el dia {{ data_camp_text }}» (tots els dies)."""
    xml = zipfile.ZipFile(ROOT / "templates" / "g3dt-jinja-template.docx").read("word/document.xml").decode("utf-8")
    assert xml.count("{{ data_camp_inici_text }}") == 1
    assert xml.count("{{ data_camp_text }}") == 1
    assert xml.index("{{ data_camp_inici_text }}") < xml.index("{{ data_camp_text }}")
