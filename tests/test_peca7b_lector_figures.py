"""Peça 7b del pas 3 d'imatges (2026-09-09): lector de figures amb Claude Code (`automation/imatges/lector_figures.py`) —
la part determinista (documents del projecte, inventari amb quadrícula, validació, retall amb marge blanc,
`figure_selection.json`, `apply_selection`) i la precedència al generador."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import fitz
from PIL import Image, ImageDraw

from automation.imatges import lector_figures as LG


def _pdf(path: Path, pages: int = 1, draw: bool = True, rotate: int = 0):
    doc = fitz.open()
    for k in range(pages):
        page = doc.new_page(width=842, height=595)
        if draw:
            sh = page.new_shape()
            sh.draw_rect(fitz.Rect(100 + 20 * k, 100, 500, 400)); sh.finish(color=(0, 0, 0), fill=(0.2, 0.4, 0.8), width=2)
            for i in range(8):
                sh.draw_line((100, 120 + i * 30), (500, 120 + i * 30)); sh.finish(color=(0, 0, 0), width=1)
            sh.commit()
        else:
            page.insert_text((72, 72), "memòria de text " * 20)
        if rotate:
            page.set_rotation(rotate)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


def _project(tmp_path):
    p = tmp_path / "4009999 PROVA"
    _pdf(p / "25.9999" / "PROJECTE.pdf", pages=3)
    _pdf(p / "25.9999" / "MEMORIA.pdf", pages=1, draw=False)
    _pdf(p / "25.9999" / "PRESSUPOST GEOTEC.PROVA.pdf")
    _pdf(p / "PDF" / "ANNEXES" / "4009999_plànol de situació.pdf")
    _pdf(p / "ACCEPTACIO" / "PRESSUPOST signat.pdf")
    _pdf(p / "Punts de Sondeig_arquitecte.pdf")
    (p / "ANNEXES" / "ALTRES").mkdir(parents=True)
    Image.new("RGB", (400, 300), (200, 220, 240)).save(p / "ANNEXES" / "ALTRES" / "F2 PUNTS.png")
    (p / "file_mapping.json").write_text(json.dumps({"roles": {"architect_project": {"path": "25.9999/PROJECTE.pdf"},
                                                                "architect_plan": {"path": "Punts de Sondeig_arquitecte.pdf"}}}))
    return p


def test_documents_del_projecte_sense_els_de_g3(tmp_path):
    p = _project(tmp_path)
    docs = {f.relative_to(p).as_posix(): k for f, k, r in LG.project_documents(p)}
    assert docs == {"25.9999/PROJECTE.pdf": "project_page", "25.9999/MEMORIA.pdf": "project_page",
                    "Punts de Sondeig_arquitecte.pdf": "project_page", "ANNEXES/ALTRES/F2 PUNTS.png": "eva_png"}


def test_inventari_salta_pagines_de_text_i_renderitza_amb_quadricula(tmp_path, monkeypatch):
    p = _project(tmp_path)
    monkeypatch.setattr(LG, "annex_drawing", lambda project: None)
    inv = LG.inventory(p, p / "validation" / LG.SUBDIR)
    rels = [(c["rel"], c["page"], c["kind"]) for c in inv["candidates"]]
    assert ("25.9999/MEMORIA.pdf", 1, "project_page") not in rels          # només text: cap candidat
    assert [r for r in rels if r[0] == "25.9999/PROJECTE.pdf"] == [("25.9999/PROJECTE.pdf", k, "project_page") for k in (1, 2, 3)]
    assert ("ANNEXES/ALTRES/F2 PUNTS.png", None, "eva_png") in rels
    assert all(Path(c["detail"]).exists() for c in inv["candidates"]) and "cap full" in inv["warnings"][0]
    sheet = LG.contact_sheet(inv, p / "validation" / LG.SUBDIR / "graella.jpg")
    assert sheet.exists()


def test_validacio_retalls_peus_i_repetits():
    cands = [{"idx": 1, "kind": "annex_crop", "rel": "plan.jpg", "page": None, "src": "/x/plan.jpg"},
             {"idx": 2, "kind": "project_page", "rel": "25.1/P.pdf", "page": 4, "src": "/x/p4.png"}]
    sel = {"assaigs": {"idx": 1, "crop": None},
           "projecte": [{"idx": 2, "crop": [0.05, 0.1, 0.95, 0.8], "caption": "Detall del perfil. Font: Projecte."},
                        {"idx": 2, "crop": [0.05, 0.1, 0.95, 0.8], "caption": "repetit"}],
           "situacio": {"idx": 2, "crops": [[0, 0, 0.5, 0.5]]}}
    clean, warns = LG.validate_selection(sel, cands)
    assert clean["assaigs"]["idx"] == 1 and clean["assaigs"]["crop"] is None
    assert len(clean["projecte"]) == 1 and clean["projecte"][0]["caption"].startswith("Detall")
    assert clean["situacio"] is None
    assert any("mateix retall" in w for w in warns) and any("DOS retalls" in w for w in warns)
    clean, warns = LG.validate_selection({"assaigs": {"idx": 9}, "projecte": [{"idx": 9, "caption": "no existeix"}]}, cands)
    assert clean["assaigs"] is None and clean["projecte"] == [] and sum("no és cap candidat" in w for w in warns) == 2
    # retall massa petit → sencer; figura del projecte sense peu → fora; més de 2 → avís
    clean, warns = LG.validate_selection({"assaigs": {"idx": 1, "crop": [0.1, 0.1, 0.12, 0.12]},
                                          "projecte": [{"idx": 2}, {"idx": 2, "caption": "a"}, {"idx": 2, "crop": [0, 0, 1, 0.5], "caption": "b"}]}, cands)
    assert clean["assaigs"]["crop"] is None and [e["caption"] for e in clean["projecte"]] == ["a"]
    assert any("sense peu" in w for w in warns) and any("només les 2" in w for w in warns)


def test_retall_en_fraccions_i_marge_blanc(tmp_path):
    p = tmp_path / "P"; _pdf(p / "25.1" / "A.pdf", pages=1)
    entry = {"kind": "project_page", "rel": "25.1/A.pdf", "page": 1, "src": "", "crop": [0.05, 0.1, 0.7, 0.8]}
    out = LG.render_entry(p, entry, tmp_path / "out.jpg", dpi=100)
    im = Image.open(out)
    # el dibuix ocupa 100-500 × 100-400 pt d'una pàgina 842×595: el retall + marge blanc fora deixa ≈ 400×300 pt a 100 dpi
    assert 520 <= im.width <= 600 and 390 <= im.height <= 450
    # imatge raster: retall per fraccions
    big = Image.new("RGB", (1000, 800), "white"); ImageDraw.Draw(big).rectangle([200, 200, 600, 500], fill="black")
    big.save(tmp_path / "r.png")
    out2 = LG.render_entry(p, {"kind": "eva_png", "rel": "r.png", "page": None, "src": str(tmp_path / "r.png"), "crop": [0.1, 0.1, 0.9, 0.9]}, tmp_path / "o2.jpg")
    w, h = Image.open(out2).size
    assert 400 <= w <= 430 and 300 <= h <= 330                                # el marge blanc del retall ha caigut


def test_trim_no_es_menja_una_imatge_quasi_blanca():
    im = Image.new("RGB", (500, 500), "white"); ImageDraw.Draw(im).rectangle([10, 10, 20, 20], fill="black")
    assert LG.trim_white(im).size == (500, 500)                               # un retall del 98 % no és un marge


def test_write_i_apply_selection(tmp_path):
    p = tmp_path / "4009999 PROVA"; _pdf(p / "25.9999" / "PROJECTE.pdf", pages=2)
    cache = tmp_path / "cache"; cache.mkdir()
    clean = {"assaigs": {"idx": 1, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 1, "src": str(p / "25.9999" / "PROJECTE.pdf"), "crop": None},
             "projecte": [{"idx": 2, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 2, "src": str(p / "25.9999" / "PROJECTE.pdf"),
                           "crop": [0.05, 0.1, 0.7, 0.8], "caption": "Detall del perfil. Font: Projecte."}],
             "situacio": {"idx": 2, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 2, "src": str(p / "25.9999" / "PROJECTE.pdf"),
                          "crops": [[0, 0, 0.5, 0.5], [0.5, 0, 1, 0.5]]}}
    path = LG.write_selection(p, clean, {"model": "test"})
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d["source"] == "lector" and d["projecte"][0]["caption"].startswith("Detall")
    out = LG.apply_selection(p, cache)
    # la situació doble del LECTOR no s'aplica (regla dels insets retirada 2026-09-09); la de l'Eva (`user`) sí.
    # Les ranures que la selecció no omple surten BUIDES (la selecció mana, també quan diu «cap»)
    assert set(out) == {"fig_assaigs_image", "fig_projecte_image_1", "fig_projecte_caption_1", "fig_projecte_image_2", "fig_projecte_caption_2"}
    assert out["fig_projecte_image_2"] == "" and out["fig_projecte_caption_2"] == ""
    assert all(Path(v).exists() for k, v in out.items() if "caption" not in k and v) and out["fig_projecte_caption_1"].endswith("Projecte.")
    assert len(list(cache.glob("figsel_*"))) == 2
    # una segona crida reaprofita la cau (mateixos noms)
    assert LG.apply_selection(p, cache) == out
    d["source"] = "user"; path.write_text(json.dumps(d), encoding="utf-8")
    out_user = LG.apply_selection(p, cache)
    assert {"fig_situacio_image_1", "fig_situacio_image_2"} <= set(out_user) and len(list(cache.glob("figsel_situacio*"))) == 2
    # cau IA antiga o sense `source` → res
    path.write_text(json.dumps({"assaigs": clean["assaigs"]}), encoding="utf-8")
    assert LG.apply_selection(p, cache) == {}


def test_image_manager_la_seleccio_mana_sobre_el_retall_determinista(tmp_path, monkeypatch):
    from automation import image_manager as IM
    p = tmp_path / "4009999 PROVA"; _pdf(p / "25.9999" / "PROJECTE.pdf", pages=2)
    mgr = IM.ImageManager(p, report_data=SimpleNamespace(has_sondeig=False), tpl=None)
    mgr._cache_dir = tmp_path / "cache"; mgr._cache_dir.mkdir()
    monkeypatch.setattr(mgr, "_download_icgc_images", lambda: {})
    monkeypatch.setattr(mgr, "_safe_inline_image", lambda path, **k: f"IMG:{Path(path).name}:{k.get('width')}")
    clean = {"assaigs": {"idx": 1, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 1, "src": str(p / "25.9999" / "PROJECTE.pdf"), "crop": None},
             "projecte": [{"idx": 2, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 2, "src": str(p / "25.9999" / "PROJECTE.pdf"),
                           "crop": None, "caption": "Secció. Font: Projecte."}], "situacio": None}
    LG.write_selection(p, clean, {})
    ctx = mgr.build_context()
    assert ctx["fig_assaigs_image"].startswith("IMG:figsel_assaigs_") and ctx["fig_projecte_image_1"].startswith("IMG:figsel_projecte1_")
    assert ctx["fig_projecte_caption_1"] == "Secció. Font: Projecte." and ctx["fig_projecte_image_2"] == ""
    assert ctx["has_plan_crops"] is True and ctx["fig_main_plan_image"] == ctx["fig_assaigs_image"]
    from automation.report_generator import figure_numbers_from_context
    n = figure_numbers_from_context(ctx)
    assert (n["fig_projecte_1_num"], n["fig_assaigs_num"], n["fig_spt_cullera_num"]) == (2, 3, 4)


def test_la_seleccio_amb_assaigs_null_buida_el_retall_determinista(tmp_path, monkeypatch):
    """Bell-lloc (2026-09-09): el lector posa el dibuix com a figura del projecte i diu «cap d'assaigs»; sense això
    l'informe imprimia el mateix dibuix dues vegades."""
    from automation import image_manager as IM
    p = tmp_path / "4009999 PROVA"; _pdf(p / "25.9999" / "PROJECTE.pdf", pages=1)
    mgr = IM.ImageManager(p, report_data=SimpleNamespace(has_sondeig=False), tpl=None)
    mgr._cache_dir = tmp_path / "cache"; mgr._cache_dir.mkdir()
    sheet = tmp_path / "4009999_plànol de situació.pdf"; sheet.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(mgr, "_download_icgc_images", lambda: {})
    monkeypatch.setattr(IM.ImageManager, "_situation_plan_candidates", lambda self, roles: [sheet])
    monkeypatch.setattr("automation.imatges.retall.crop_plan", lambda pdf, out, **k: (Path(out).write_bytes(b"x"), out)[1])
    monkeypatch.setattr("automation.imatges.retall.compose_situation", lambda pdf, out, **k: None)
    monkeypatch.setattr(mgr, "_safe_inline_image", lambda path, **k: f"IMG:{Path(path).name}")
    LG.write_selection(p, {"assaigs": None, "projecte": [{"idx": 1, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 1,
                                                          "src": str(p / "25.9999" / "PROJECTE.pdf"), "crop": None, "caption": "Ubicació. Font: Projecte."}],
                           "situacio": None}, {})
    ctx = mgr.build_context()
    assert ctx["fig_assaigs_image"] == "" and ctx["fig_projecte_image_1"].startswith("IMG:figsel_projecte1_")
    from automation.report_generator import figure_numbers_from_context
    assert figure_numbers_from_context(ctx)["fig_spt_cullera_num"] == 3        # situació 1 + projecte 1, cap d'assaigs


# --- 2026-09-09, acció 4: alternatives del lector per ranura ---

def test_alternatives_de_figures_es_validen_i_s_escriuen(tmp_path):
    cands = [{"idx": i, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": i, "src": "/x/PROJECTE.pdf"} for i in (1, 2, 3, 4)]
    sel = {"assaigs": {"idx": 1, "crop": None}, "projecte": [{"idx": 2, "crop": None, "caption": "Secció. Font: Projecte."}],
           "alternatives": {"assaigs": [{"idx": 1, "crop": None, "rao": "el triat"}, {"idx": 1, "crop": [0.1, 0.1, 0.9, 0.9], "rao": "més estret"},
                                        {"idx": 3, "rao": "el full de l'Eva"}, {"idx": 3, "crop": None}, {"idx": 42}],
                            "projecte": [{"idx": 4, "crop": [0, 0, 0.5, 0.5], "caption": "Planta. Font: Projecte.", "rao": "la planta"}],
                            "situacio": [{"idx": 2}]}}
    clean, w = LG.validate_selection(sel, cands)
    a = clean["alternatives"]
    assert [(e["idx"], e["crop"], e["rao"]) for e in a["assaigs"]] == [(1, [0.1, 0.1, 0.9, 0.9], "més estret"), (3, None, "el full de l'Eva")]
    assert a["projecte"][0]["caption"] == "Planta. Font: Projecte." and a["projecte"][0]["crop"] == [0.0, 0.0, 0.5, 0.5]
    assert "situacio" not in a and any("idx «42»" in x for x in w)
    p = tmp_path / "4009999 PROVA"; p.mkdir()
    d = json.loads(LG.write_selection(p, clean, {"model": "test"}).read_text(encoding="utf-8"))
    assert list(d)[:5] == ["source", "assaigs", "projecte", "situacio", "alternatives"] and d["alternatives"]["assaigs"][1]["rao"] == "el full de l'Eva"
    assert LG.apply_selection(p, tmp_path / "cache") is not None       # les alternatives no canvien el que s'aplica


def test_image_manager_les_pujades_de_l_eva_manen_sobre_les_figures_automatiques(tmp_path, monkeypatch):
    """2026-09-10: geològic, tall i cullera (i la situació d'una sola imatge) pujats des de la finestreta entren al
    context després del camí determinista de cadascuna, amb l'amplada de la figura que substitueixen."""
    from docx.shared import Mm
    from automation import image_manager as IM
    p = tmp_path / "4009999 PROVA"; up = p / "validation" / "uploads" / "imatges"; up.mkdir(parents=True)
    for n in ("20260910-100000-aa0001.png", "20260910-100001-aa0002.png", "20260910-100002-aa0003.png", "20260910-100003-aa0004.png"):
        Image.new("RGB", (80, 60), (200, 180, 120)).save(up / n)
    mgr = IM.ImageManager(p, report_data=SimpleNamespace(has_sondeig=False), tpl=None)
    mgr._cache_dir = tmp_path / "cache"; mgr._cache_dir.mkdir()
    monkeypatch.setattr(mgr, "_download_icgc_images", lambda: {})
    monkeypatch.setattr(mgr, "_safe_inline_image", lambda path, **k: f"IMG:{Path(path).name}:{k.get('width')}")
    e = lambda n: {"kind": "upload", "rel": f"validation/uploads/imatges/{n}"}
    (p / "validation" / "figure_selection.json").write_text(json.dumps({
        "source": "user", "assaigs": None, "projecte": [], "situacio": e("20260910-100003-aa0004.png"),
        "geologic": e("20260910-100000-aa0001.png"), "tall": e("20260910-100001-aa0002.png"), "cullera": e("20260910-100002-aa0003.png")}), encoding="utf-8")
    ctx = mgr.build_context()
    assert ctx["fig_geological_image"] == f"IMG:{Path(LG._out_name(mgr._cache_dir, 'geologic', e('20260910-100000-aa0001.png'), None)).name}:{Mm(IM.IMAGE_WIDTH_GEOLOGICAL)}"
    assert ctx["fig_correlation_image"].startswith("IMG:figsel_tall_") and ctx["fig_correlation_image"].endswith(f":{Mm(IM.IMAGE_WIDTH_LOCATION)}")
    assert ctx["fig_spt_cullera_image"].startswith("IMG:figsel_cullera_") and ctx["fig_spt_cullera_image"].endswith(f":{Mm(IM.IMAGE_WIDTH_SPT_CULLERA)}")
    assert ctx["fig_situacio_image_1"].startswith("IMG:figsel_situacio1_") and ctx["fig_situacio_image_1"].endswith(f":{Mm(IM.IMAGE_WIDTH_MAIN_PLAN)}")
    assert ctx["fig_situacio_image_2"] == "" and ctx["fig_assaigs_image"] == ""
    # sense pujades: el camí determinista de sempre (la cullera de la plantilla)
    (p / "validation" / "figure_selection.json").write_text(json.dumps({"source": "user", "assaigs": None, "projecte": [], "situacio": None}), encoding="utf-8")
    ctx = mgr.build_context()
    assert ctx["fig_spt_cullera_image"].startswith("IMG:cullera_spt") and ctx["fig_geological_image"] == IM.PLACEHOLDER_TEXT
