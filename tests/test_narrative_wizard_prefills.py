"""Peça 3 (2026-09-07): els candidats narratius arriben al wizard com a «+N» (`_alternatives`) i els camps es desen."""
from pathlib import Path
from types import SimpleNamespace

from automation.wizard import WIZARD_FIELDS
from web.wizard_service import _compute_narrative_prefills, _generate_template_prefills_from_merged


def test_wizard_fields_include_narrative_pieces():
    for k in ("site_condition", "building_structure_desc", "access_street", "lab_tests_text", "num_site_photos"):
        assert k in WIZARD_FIELDS


def test_narrative_prefills_alternatives_and_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("automation.parcel_context.own_parcel_buildings", lambda rcs: {"has_building": False, "num_floors_above": 0})
    merged = {
        "num_floors": {"value": "PB", "source": "planol"},
        "street_address": {"value": "Carrer dels Arbrells, 25130 Linyola", "source": "planol"},
        "adjacent_north": {"value": "parcel·la buida", "source": "Cadastre"},
        "adjacent_west": {"value": "Carrer dels Arbrells", "source": "Cadastre"},
        "lab_tests_text": {"value": "Determinació del contingut en ió sulfat en sòls   UNE 83963 / 08\nAssaig Lambe    UNE 103600 / 96",
                           "source": "4672-GTL-25 Linyola.pdf"},
        "slope_percent": {"value": "0.4", "source": "ICGC"},
    }
    _generate_template_prefills_from_merged(merged)
    _compute_narrative_prefills(merged, SimpleNamespace(dpsh_data=None), tmp_path)
    assert merged["access_street"]["value"] == "carrer adjacent situat al oest"
    assert merged["lab_tests_text"]["value"].split("\n") == ["Assaig d'expansivitat Lambe UNE 103600/96",
                                                            "Assaig de contingut en sulfats UNE 83963 : 2008"]
    assert merged["num_site_photos"]["value"] == 0 and "default" in merged["num_site_photos"]["source"]
    assert merged["site_description"]["value"].startswith("El solar es localitza sense construccions")
    alts = merged["_alternatives"]["value"]
    for k in ("site_condition", "building_structure_desc", "access_street", "lab_tests_text", "site_description"):
        assert alts.get(k), k
        assert all(a["value"] != merged[k]["value"] for a in alts[k])
    assert any(a["value"] == "carrer dels Arbrells" for a in alts["access_street"])
    # l'Eva ha editat: cap candidat li trepitja el valor
    merged["site_condition"] = {"value": "Al solar, no s'han detectat marques.", "source": "user"}
    _compute_narrative_prefills(merged, SimpleNamespace(dpsh_data=None), tmp_path)
    assert merged["site_condition"]["value"].startswith("Al solar")


def test_num_site_photos_follows_eva_photo_selection(tmp_path: Path):
    (tmp_path / "validation").mkdir()
    (tmp_path / "validation" / "photo_selection.json").write_text(
        '{"source": "user", "site_1": "FOTOGRAFIES/a.jpg", "site_2": null, "dpsh": "FOTOGRAFIES/b.jpg"}', encoding="utf8")
    merged = {"num_floors": {"value": "PB", "source": "planol"}}
    _compute_narrative_prefills(merged, SimpleNamespace(dpsh_data=None), tmp_path)
    assert merged["num_site_photos"]["value"] == 1
