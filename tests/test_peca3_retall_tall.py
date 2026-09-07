"""Peça 3 del pas 3 d'imatges (2026-09-07): retall del dibuix del tall de correlació (`automation/imatges/retall.py`)."""
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
from automation.imatges.retall import crop_drawing, detect_section_region  # noqa: E402


def _plan_page(path: Path, *, with_legend=True, with_title_block=True, with_map=True):
    """Full com els de l'Eva: mapa i llegenda a dalt, secció al mig, caixetí a baix."""
    doc = fitz.open(); page = doc.new_page(width=842, height=595)
    if with_map:
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60)); pix.set_rect(pix.irect, (120, 160, 90))
        page.insert_image(fitz.Rect(40, 30, 240, 200), pixmap=pix)
    if with_legend:
        page.draw_rect(fitz.Rect(280, 40, 700, 120), color=(0, 0, 0), fill=(1, 1, 1))
        page.insert_text((300, 70), "LLEGENDA", fontsize=9)
        page.insert_text((300, 95), "Nivell 1: Llims argilosos", fontsize=8)
    # secció: dos estrats amples + eix + etiquetes
    page.draw_rect(fitz.Rect(200, 300, 700, 340), color=None, fill=(0.55, 0.35, 0.15))
    page.draw_rect(fitz.Rect(200, 340, 700, 430), color=None, fill=(0.95, 0.7, 0.35))
    page.insert_text((150, 300), "(msnm)", fontsize=7)
    for i, y in enumerate((310, 350, 390, 425)):
        page.insert_text((165, y), f"{213 - i}", fontsize=7)
    for x, lab in ((260, "P-1"), (430, "P-2"), (620, "P-3")):
        page.draw_line(fitz.Point(x, 270), fitz.Point(x, 305), color=(0, 0, 1))
        page.insert_text((x - 8, 265), lab, fontsize=8)
    page.insert_text((300, 415), "Nb=R", fontsize=7)          # els «Nb=» van dins la secció, com als talls de l'Eva
    if with_title_block:
        page.draw_line(fitz.Point(40, 520), fitz.Point(800, 520))
        page.insert_text((60, 540), "TÍTOL DEL PROJECTE", fontsize=8)
        page.insert_text((600, 540), "Data: Octubre 2025", fontsize=8)
        page.insert_text((720, 540), "Exp: 4001612", fontsize=8)
    doc.save(path); doc.close()
    return path


def test_el_retall_deixa_fora_llegenda_mapa_i_caixeti(tmp_path):
    pdf = _plan_page(tmp_path / "tall.pdf")
    page = fitz.open(pdf)[0]
    r = detect_section_region(page)
    assert r is not None
    assert r.y0 > 200 and r.y1 < 520                 # sota la llegenda (y1=120) i sobre el caixetí (y=520)
    assert r.x0 < 200 and r.x1 > 690                 # inclou l'eix de cotes i arriba al final dels estrats
    assert r.y0 < 270                                # inclou les etiquetes «P-n» (i la seva línia), que són a sobre
    assert r.x0 > 40 and r.y0 > 200                  # el mapa (x 40-240, y 30-200) queda fora


def test_sense_estrats_no_hi_ha_retall(tmp_path):
    doc = fitz.open(); page = doc.new_page(width=842, height=595)
    page.insert_text((100, 100), "només text, cap dibuix", fontsize=10)
    p = tmp_path / "buit.pdf"; doc.save(p); doc.close()
    assert detect_section_region(fitz.open(p)[0]) is None
    assert crop_drawing(p, tmp_path / "out.jpg") is None


def test_crop_drawing_escriu_la_imatge(tmp_path):
    pdf = _plan_page(tmp_path / "tall.pdf")
    out = crop_drawing(pdf, tmp_path / "sub" / "tall_crop.jpg")
    assert out is not None and out.exists()
    from PIL import Image
    im = Image.open(out)
    assert im.width > 400 and im.height > 150
    assert im.width / im.height > 1.5                # la secció és apaïsada


def test_funciona_sense_caixeti_ni_llegenda(tmp_path):
    pdf = _plan_page(tmp_path / "net.pdf", with_legend=False, with_title_block=False, with_map=False)
    r = detect_section_region(fitz.open(pdf)[0])
    assert r is not None and r.y0 < 270 and r.x1 > 690
