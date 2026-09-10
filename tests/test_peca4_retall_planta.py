"""Peça 4 del pas 3 d'imatges (2026-09-08): retall del dibuix AMB PUNTS del full de situació de l'Eva.

El full és sempre igual: dos mapes de situació petits a dalt, el plànol o l'ortofoto GRAN a sota amb els punts
d'assaig, la fletxa de nord, el logo i el caixetí. El que va a l'informe és la imatge gran amb les cotes i les
etiquetes que l'Eva hi dibuixa a sobre — i res més.
"""
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
from automation.imatges.retall import crop_plan, detect_plan_region  # noqa: E402


def _img(page, rect, color):
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40))
    pix.set_rect(pix.irect, color)
    page.insert_image(rect, pixmap=pix)


def _situation_sheet(path: Path, *, rotate: int = 0, big: bool = True):
    """Full de situació com els de l'Eva, en A3 vertical (com surten del FreeHand)."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=1191)
    _img(page, fitz.Rect(33, 37, 97, 101), (0, 130, 60))                 # logo G3
    _img(page, fitz.Rect(114, 41, 428, 357), (200, 200, 240))            # mapa de situació 1
    _img(page, fitz.Rect(436, 41, 787, 392), (180, 210, 180))            # mapa de situació 2
    _img(page, fitz.Rect(737, 348, 783, 385), (250, 250, 250))           # fletxa de nord
    if big:
        _img(page, fitz.Rect(150, 450, 750, 1000), (230, 230, 230))      # EL DIBUIX (43 % de la pàgina)
    else:                                                                 # export «imprimible»: raster en tires
        for i in range(20):
            _img(page, fitz.Rect(150, 450 + 27 * i, 750, 476 + 27 * i), (230, 230, 230))
    # el que l'Eva dibuixa a sobre i tocant el dibuix: cotes i etiquetes dels punts
    page.draw_line(fitz.Point(120, 700), fitz.Point(150, 700), color=(1, 0, 0))
    page.insert_text((118, 690), "5 m", fontsize=7)
    page.insert_text((300, 1010), "P-1", fontsize=8)
    page.draw_line(fitz.Point(40, 1100), fitz.Point(800, 1100))          # caixetí
    page.insert_text((60, 1120), "TÍTOL DEL PROJECTE", fontsize=8)
    page.insert_text((600, 1120), "Data: Octubre 2025", fontsize=8)
    page.insert_text((700, 1120), "Exp: 4001607", fontsize=8)
    page.set_rotation(rotate)
    doc.save(path)
    doc.close()
    return path


def test_el_retall_es_el_dibuix_amb_les_cotes_de_l_eva(tmp_path):
    pdf = _situation_sheet(tmp_path / "situacio.pdf")
    r = detect_plan_region(fitz.open(pdf)[0])
    assert r is not None
    assert r.y0 > 400 and r.y1 < 1100          # sota els mapes (y1=392) i sobre el caixetí (y=1100)
    assert r.x0 < 130 and r.y1 > 1000          # inclou la cota «5 m» de l'esquerra i l'etiqueta «P-1» de sota
    assert r.x1 < 800


def test_els_mapes_el_nord_i_el_logo_queden_fora(tmp_path):
    pdf = _situation_sheet(tmp_path / "situacio.pdf")
    r = detect_plan_region(fitz.open(pdf)[0])
    for zona in (fitz.Rect(114, 41, 428, 357), fitz.Rect(436, 41, 787, 392), fitz.Rect(33, 37, 97, 101)):
        assert not (r & zona).is_valid or abs((r & zona).get_area()) < 1e-6


def test_full_girat_270_el_retall_surt_en_coordenades_de_pantalla(tmp_path):
    """Els fulls de l'Eva són A3 vertical girats: `get_images` dona coordenades sense girar i `page.rect` girades."""
    dret = fitz.open(_situation_sheet(tmp_path / "dret.pdf"))[0]
    page = fitz.open(_situation_sheet(tmp_path / "girat.pdf", rotate=270))[0]
    r = detect_plan_region(page)
    assert r is not None
    assert r in page.rect + (-1, -1, 1, 1)     # dins la pàgina tal com es veu (1191 × 842)
    esperat = detect_plan_region(dret) * page.rotation_matrix      # el mateix dibuix, girat
    for a, b in zip(tuple(r), tuple(esperat)):
        assert abs(a - b) < 1.0


def test_export_amb_el_raster_en_tires_no_dona_retall(tmp_path):
    """El `pl situ.pdf` de l'arrel talla el raster en centenars de tires: cap nucli, i qui crida prova el següent."""
    pdf = _situation_sheet(tmp_path / "imprimible.pdf", big=False)
    assert detect_plan_region(fitz.open(pdf)[0]) is None
    assert crop_plan(pdf, tmp_path / "out.jpg") is None


def test_sense_imatges_no_hi_ha_retall(tmp_path):
    doc = fitz.open(); page = doc.new_page(width=842, height=1191)
    page.insert_text((100, 100), "només text", fontsize=10)
    p = tmp_path / "buit.pdf"; doc.save(p); doc.close()
    assert detect_plan_region(fitz.open(p)[0]) is None


def test_crop_plan_escriu_la_imatge(tmp_path):
    pdf = _situation_sheet(tmp_path / "situacio.pdf")
    out = crop_plan(pdf, tmp_path / "sub" / "plan_crop.jpg")
    assert out is not None and out.exists()
    from PIL import Image
    im = Image.open(out)
    assert im.width > 300 and im.height > 300


# --------------------------------------------------------------------------------------------------------------
# Precedència del tall de correlació (2026-09-08, mateixa sessió que la peça 4)

def test_el_rol_figure_correlation_no_passa_davant_del_tall_pdf():
    """El PNG compost d'`ALTRES` no ha de pre-empar el retall del `tall.pdf`.

    A Rubí el rol `figure_correlation` apunta a `ANNEXES/Altres/F5 TALL.png`, que és un dibuix DIFERENT del que ella
    va signar (dos nivells amb llegenda i escala, 204-212, contra el nivell únic amb la cota de fonamentació vermella,
    208-213). L'Eva retalla la secció del `tall.pdf` als 7 signats: mesurat, el PNG dona X (NCC 0,58) i el retall del
    `tall.pdf`, C (0,91).
    """
    from automation.image_manager import ROLE_TO_FIGURE_VAR
    assert 'figure_correlation' not in ROLE_TO_FIGURE_VAR
    assert ROLE_TO_FIGURE_VAR['figure_situation_map'] == 'fig_situacio_image_1'   # els altres rols no s'han tocat (peça 7a: nom nou)
    assert ROLE_TO_FIGURE_VAR['figure_geological_map'] == 'fig_geological_image'
