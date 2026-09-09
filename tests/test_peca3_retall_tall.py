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


# --- 2026-09-09, acció 3 (estudi del retall del tall als 7 signats) ---

def test_un_trac_de_rectangles_separats_no_fa_de_pont_amb_la_llegenda(tmp_path):
    """Linyola i Vilanova: el FreeHand exporta en UN traç la línia de la caixa de la llegenda i la del terreny; la caixa
    del traç abastava l'espai entre elles i entrava al nucli com un «estrat» (49-73 mm de llegenda a sobre de la secció)."""
    pdf = _plan_page(tmp_path / "tall.pdf")
    doc = fitz.open(pdf); page = doc[0]
    sh = page.new_shape()
    sh.draw_rect(fitz.Rect(280, 119, 700, 120.5))                 # línia inferior de la caixa de la llegenda
    sh.draw_rect(fitz.Rect(200, 298.5, 700, 300))                 # línia del terreny, tocant el primer estrat
    sh.finish(color=None, fill=(0, 0, 0), even_odd=True)          # un sol traç amb dos rectangles
    sh.commit()
    p2 = tmp_path / "tall2.pdf"; doc.save(p2); doc.close()
    d = [x for x in fitz.open(p2)[0].get_drawings() if x.get("fill") == (0.0, 0.0, 0.0)]
    assert any(len(x["items"]) == 2 and all(it[0] == "re" for it in x["items"]) for x in d)   # el fixture reprodueix el traç
    r = detect_section_region(fitz.open(p2)[0])
    assert r is not None and 200 < r.y0 < 270                    # la llegenda continua fora; les etiquetes «P-n» dins
    assert r.y0 <= 298.5 and r.x1 > 690                          # la línia del terreny sí que hi és


def test_els_numeros_de_l_eix_a_menys_de_5_mm_hi_entren_i_el_que_es_a_mes_no(tmp_path):
    """Bell-lloc: els números de l'eix són a 3,7 mm de la barra i quedaven fora (tolerància del 5 % de l'alçada del
    nucli = 2 mm); als 7 signats són a 0,4-3,7 mm i la llegenda mai a menys de 16 mm. «Blanc» = 5 mm."""
    doc = fitz.open(); page = doc.new_page(width=842, height=595)
    page.draw_rect(fitz.Rect(200, 300, 700, 340), color=None, fill=(0.55, 0.35, 0.15))
    page.draw_rect(fitz.Rect(200, 340, 700, 430), color=None, fill=(0.95, 0.7, 0.35))
    page.draw_rect(fitz.Rect(196, 300, 200, 430), color=None, fill=(0, 0, 0))       # barra de l'eix, enganxada
    for i, y in enumerate((310, 350, 390, 425)):
        page.insert_text((172, y), f"{213 - i}", fontsize=7)                          # números: acaben a ~185 → 11 pt ≈ 3,9 mm
    page.insert_text((110, 310), "ESCALA", fontsize=7)                                # a ~50 pt ≈ 18 mm: fora
    p = tmp_path / "eix.pdf"; doc.save(p); doc.close()
    page = fitz.open(p)[0]
    nums = [w for w in page.get_text("words") if w[4].isdigit()]
    assert 8 < 196 - max(w[2] for w in nums) < 14.2                                   # el salt del fixture és de 3-5 mm
    r = detect_section_region(page)
    assert r is not None and r.x0 <= min(w[0] for w in nums) and r.x0 > 130


def test_una_seccio_curta_arriba_a_les_etiquetes_que_pengen_30_mm_a_sobre(tmp_path):
    """Alcoletge: amb el nucli net (només estrats, 30 mm d'alçada) la finestra del 75 % no arribava a «(msnm)» ni a
    «A»/«A'», 32 mm a sobre. Als 7 signats les etiquetes pengen 15-32 mm sobre els estrats: mínim 40 mm."""
    doc = fitz.open(); page = doc.new_page(width=842, height=595)
    page.draw_rect(fitz.Rect(200, 300, 700, 330), color=None, fill=(0.55, 0.35, 0.15))     # secció de 85 pt = 30 mm
    page.draw_rect(fitz.Rect(200, 330, 700, 385), color=None, fill=(0.95, 0.7, 0.35))
    page.insert_text((200, 213), "A", fontsize=8); page.insert_text((690, 213), "A'", fontsize=8)   # 32 mm a sobre, als extrems
    for x, lab in ((260, "P-1"), (620, "P-2")):
        page.draw_line(fitz.Point(x, 232), fitz.Point(x, 300), color=(0, 0, 1))              # línia fins a l'estrat
        page.insert_text((x - 8, 228), lab, fontsize=8)
    p = tmp_path / "curta.pdf"; doc.save(p); doc.close()
    r = detect_section_region(fitz.open(p)[0])
    assert r is not None and r.y0 < 204 and r.x0 <= 200 and r.x1 > 697          # «A», «A'» i les etiquetes dins
