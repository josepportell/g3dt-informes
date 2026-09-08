"""Peça 5 del pas 3 d'imatges (2026-09-08): la figura de situació són els dos mapes del full de l'Eva, de costat.

Substitueix el retall del 38 % esquerre del full, que no coincidia amb cap dels 7 signats.
"""
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from automation.image_manager import ImageManager  # noqa: E402
from automation.imatges.retall import compose_situation, detect_situation_maps  # noqa: E402


def _img(page, rect, color):
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40))
    pix.set_rect(pix.irect, color)
    page.insert_image(rect, pixmap=pix)


def _sheet(path: Path, *, rotate: int = 270, big: bool = True, second_map: bool = True):
    """Full de situació de l'Eva: dos mapes a dalt, el dibuix gran a sota, nord, logo i caixetí."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=1191)
    _img(page, fitz.Rect(33, 37, 97, 101), (0, 130, 60))              # logo
    _img(page, fitz.Rect(114, 41, 428, 357), (200, 200, 240))         # mapa ESQUERRE un cop girat 270°
    if second_map:
        _img(page, fitz.Rect(436, 41, 787, 392), (180, 210, 180))     # mapa DRET
    _img(page, fitz.Rect(737, 348, 783, 385), (250, 250, 250))        # fletxa de nord
    if big:
        _img(page, fitz.Rect(150, 450, 750, 1000), (230, 230, 230))   # el dibuix (43 % de la pàgina)
    page.draw_line(fitz.Point(40, 1100), fitz.Point(800, 1100))
    page.insert_text((60, 1120), "TÍTOL DEL PROJECTE", fontsize=8)
    page.insert_text((700, 1120), "Exp: 4001607", fontsize=8)
    page.set_rotation(rotate)
    doc.save(path)
    doc.close()
    return path


def test_troba_els_dos_mapes_i_deixa_fora_el_dibuix_el_nord_i_el_logo(tmp_path):
    page = fitz.open(_sheet(tmp_path / "situacio.pdf"))[0]
    clips = detect_situation_maps(page)
    assert clips is not None and len(clips) == 2
    dibuix = (fitz.Rect(150, 450, 750, 1000) * page.rotation_matrix)
    for c in clips:
        assert abs((c & dibuix).get_area()) < 1e-6
        assert c in page.rect + (-1, -1, 1, 1)


def test_l_ordre_es_el_de_lectura_del_full_un_cop_girat(tmp_path):
    """Els fulls van girats 270°: l'ordre es decideix a l'espai de pantalla, no al del PDF.

    Amb la geometria de Castellar i Alcoletge els dos mapes queden l'un SOBRE l'altre al full (mateixa columna), i
    l'Eva els posa de costat amb el de dalt a l'esquerra: esquerra→dreta i, en empat, dalt→baix.
    """
    page = fitz.open(_sheet(tmp_path / "situacio.pdf"))[0]
    a, b = detect_situation_maps(page)
    assert (round(a.x0, 1), round(a.y0, 1)) < (round(b.x0, 1), round(b.y0, 1))
    assert a.y0 < b.y0                               # aquest full els té a la mateixa columna


def test_sense_el_segon_mapa_no_hi_ha_figura(tmp_path):
    page = fitz.open(_sheet(tmp_path / "un.pdf", second_map=False))[0]
    assert detect_situation_maps(page) is None
    assert compose_situation(tmp_path / "un.pdf", tmp_path / "out.png") is None


def test_sense_dibuix_gran_no_es_el_full_net(tmp_path):
    """L'export «imprimible» del FreeHand porta el raster en tires; algunes passen del 3 % i es farien passar per
    mapes. Sense cap imatge gran no es compon res: qui crida prova el candidat següent."""
    page = fitz.open(_sheet(tmp_path / "imprimible.pdf", big=False))[0]
    assert detect_situation_maps(page) is None


def test_compose_situation_posa_els_dos_de_costat_a_la_mateixa_alcada(tmp_path):
    out = compose_situation(_sheet(tmp_path / "situacio.pdf"), tmp_path / "sub" / "situacio.png")
    assert out is not None and out.exists()
    im = Image.open(out)
    assert im.width > im.height                      # apaïsada: dos mapes de costat
    assert im.width / im.height > 1.5


def test_is_wide_image(tmp_path):
    ample = tmp_path / "F1 UBI.png"; Image.new("RGB", (1595, 795)).save(ample)
    quadrat = tmp_path / "F2 UBI PUNTS.png"; Image.new("RGB", (847, 838)).save(quadrat)
    m = ImageManager.__new__(ImageManager); m.project_path = tmp_path
    assert m._is_wide_image(ample)
    assert not m._is_wide_image(quadrat)             # el guard del rol: una figura de situació són dos mapes
    assert not m._is_wide_image(tmp_path / "no-hi-es.png")


def test_el_retall_del_38_per_cent_ja_no_hi_es():
    """`_render_situation_plan_left` no coincidia amb cap dels 7 signats (7 X): fora, i no es reintrodueix."""
    assert not hasattr(ImageManager, "_render_situation_plan_left")
