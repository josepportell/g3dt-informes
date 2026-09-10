"""Peça 6 del pas 3 d'imatges (2026-09-08): el mapa geològic que l'Eva ja ha compost va abans que la recepta ICGC.

A Castellar, Rubí i Vilanova l'Eva desa el mapa geològic amb la llegenda de les unitats com a PNG al costat dels
annexos, i és **la mateixa imatge** que surt al signat (phash 0). Als altres quatre no n'hi ha cap i es fa servir la
recepta ICGC de sempre, que no es toca.
"""
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from automation.image_manager import ImageManager  # noqa: E402


def _manager(root: Path) -> ImageManager:
    m = ImageManager.__new__(ImageManager)
    m.project_path = root
    return m


def _png(path: Path, color=(200, 210, 160)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 30), color).save(path)
    return path


def test_troba_el_png_compost_pel_nom(tmp_path):
    _png(tmp_path / "ANNEXES" / "ALTRES" / "m12 mgeol.png")
    _png(tmp_path / "ANNEXES" / "ALTRES" / "M1.png")              # el rol de SmartScan hi apunta a Castellar: no és
    assert _manager(tmp_path)._find_composed_geological_map().name == "m12 mgeol.png"


def test_reconeix_les_variants_de_grafia_i_de_carpeta(tmp_path):
    _png(tmp_path / "ANEXOS" / "OTROS" / "F4 MGEOL.png")
    assert _manager(tmp_path)._find_composed_geological_map().name == "F4 MGEOL.png"


def test_sense_cap_fitxer_geol_no_hi_ha_candidat(tmp_path):
    """Bell-lloc, Linyola, Alcoletge i Anciles: cap fitxer amb «geol» → recepta ICGC."""
    _png(tmp_path / "ANNEXES" / "ALTRES" / "M1.png")
    _png(tmp_path / "validation" / "mined_images" / "2_02B_DG_Silvia_Jaume_img0.jpeg")
    assert _manager(tmp_path)._find_composed_geological_map() is None


def test_el_fh11_no_compta(tmp_path):
    """El FreeHand és la font del PNG, no una imatge que puguem inserir (calen `soffice` i una conversió)."""
    (tmp_path / "ANNEXES" / "ALTRES").mkdir(parents=True)
    (tmp_path / "ANNEXES" / "ALTRES" / "6_mapa Geologic_CAT_VS.FH11").write_bytes(b"x")
    assert _manager(tmp_path)._find_composed_geological_map() is None


def test_la_carpeta_altres_mana_sobre_la_resta(tmp_path):
    _png(tmp_path / "correu" / "mapa geologic.png")
    _png(tmp_path / "ANNEXES" / "Altres" / "F4 MGEOL.png")
    assert _manager(tmp_path)._find_composed_geological_map().parent.name == "Altres"


def test_les_pujades_i_l_evidencia_de_validation_no_compten(tmp_path):
    """2026-09-10: `validation/` és nostre (pujades de l'Eva, evidència HITL); un fitxer «…geol…» que hi visqui no és
    el mapa de l'informe. La pujada ja es desa amb un nom que és un ID, però l'evidència HITL conserva el nom."""
    _png(tmp_path / "validation" / "uploads" / "imatges" / "mapa geol.png")
    _png(tmp_path / "validation" / "uploads" / "20260910-101010_a1b2c3_informe_geol.jpg")
    assert _manager(tmp_path)._find_composed_geological_map() is None
    _png(tmp_path / "ANNEXES" / "ALTRES" / "m12 mgeol.png")
    assert _manager(tmp_path)._find_composed_geological_map().name == "m12 mgeol.png"
