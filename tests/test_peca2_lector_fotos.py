"""Peça 2 del pas 3 d'imatges (2026-09-07): lector de fotos amb Claude Code (`automation/imatges/lector_fotos.py`) — la part
determinista (inventari, aparellament amb l'annex, fulls, prompt, validació, escriptura) i la precedència Eva > lector."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from automation.imatges import lector_fotos as LF


def _structured(seed: int, size: int = 320):
    import numpy as np
    rng = np.random.default_rng(seed)
    coarse = rng.integers(0, 256, size=(8, 8, 3), dtype=np.uint8)
    big = Image.fromarray(coarse, "RGB").resize((size, size), Image.BICUBIC)
    a = np.asarray(big).astype(np.int16) + rng.integers(-15, 16, size=(size, size, 3), dtype=np.int16)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def _project(tmp_path, with_annex=True):
    p = tmp_path / "4009999 PROVA"; (p / "FOTOGRAFIES").mkdir(parents=True); (p / "ANNEXES").mkdir()
    ims = {n: _structured(k) for k, n in enumerate(["P1.jpg", "P2.jpg", "SPT1.jpg", "PENETROS.jpg"], 1)}
    for n, im in ims.items():
        im.save(p / "FOTOGRAFIES" / n, quality=92)
    (p / "file_mapping.json").write_text(json.dumps({"roles": {"photos_dir": {"path": "FOTOGRAFIES"},
                                                                "dpsh_field_sheet": {"path": "FOTOGRAFIES/PENETROS.jpg"}}}))
    if with_annex:
        import fitz
        doc = fitz.open(); page = doc.new_page(width=595, height=842)
        logo = Image.new("RGB", (138, 138), (0, 120, 0)); lp = tmp_path / "logo.png"; logo.save(lp)
        page.insert_image(fitz.Rect(20, 20, 80, 80), filename=str(lp))
        page.insert_image(fitz.Rect(60, 120, 540, 420), filename=str(p / "FOTOGRAFIES" / "P2.jpg"))       # foto #1 (dalt)
        page.insert_image(fitz.Rect(60, 460, 540, 760), filename=str(p / "FOTOGRAFIES" / "SPT1.jpg"))     # foto #2 (baix)
        doc.save(p / "ANNEXES" / "4009999_fotografies.pdf")
    return p


def test_inventari_aparella_les_fotos_amb_l_annex(tmp_path):
    p = _project(tmp_path); work = p / "validation" / LF.SUBDIR
    inv = LF.inventory(p, work)
    rels = [c["rel"] for c in inv["candidates"]]
    assert rels == ["FOTOGRAFIES/P1.jpg", "FOTOGRAFIES/P2.jpg", "FOTOGRAFIES/PENETROS.jpg", "FOTOGRAFIES/SPT1.jpg"]
    by = {c["rel"]: c for c in inv["candidates"]}
    assert by["FOTOGRAFIES/P2.jpg"]["annex"]["ordinal"] == 1 and by["FOTOGRAFIES/SPT1.jpg"]["annex"]["ordinal"] == 2
    assert by["FOTOGRAFIES/P1.jpg"]["annex"] is None and by["FOTOGRAFIES/PENETROS.jpg"]["roles"] == ["dpsh_field_sheet"]
    assert len(inv["annex_images"]) == 2 and len(inv["annex_pages"]) == 1 and Path(inv["annex_pages"][0]).exists()


def test_full_de_contacte_i_prompt(tmp_path):
    p = _project(tmp_path, with_annex=False); work = p / "validation" / LF.SUBDIR
    inv = LF.inventory(p, work); sheet = LF.contact_sheet(inv, work / "graella.jpg")
    assert sheet.exists() and Image.open(sheet).width > 1000
    prompt = LF.build_prompt(inv, sheet, {}, work / LF.RESULT, has_sondeig=False)
    assert "/g3dt-llegir-fotos" in prompt and "1. `FOTOGRAFIES/P1.jpg`" in prompt and str(sheet) in prompt
    assert "Annex de fotografies de l'Eva: cap" in prompt and "Sondeig a rotació al projecte: no" in prompt
    assert str(work / LF.RESULT) in prompt


def test_validacio_index_o_cami_i_una_foto_per_forat():
    cands = [{"idx": 1, "rel": "FOTOGRAFIES/P1.jpg"}, {"idx": 2, "rel": "FOTOGRAFIES/P2.jpg"}, {"idx": 3, "rel": "FOTOGRAFIES/SPT1.jpg"}]
    clean, w = LF.validate_selection({"site_1": 1, "site_2": "1", "dpsh": "FOTOGRAFIES/P2.jpg", "sondeig": None, "materials": "SPT1.jpg",
                                      "materials_per_punt": [{"punt": "P-1", "idx": 3}, {"punt": "P-2", "idx": 9}]}, cands)
    assert clean["site_1"] == "FOTOGRAFIES/P1.jpg" and clean["site_2"] is None and clean["dpsh"] == "FOTOGRAFIES/P2.jpg"
    assert clean["sondeig"] is None and clean["materials"] == "FOTOGRAFIES/SPT1.jpg"
    assert clean["materials_per_punt"] == [{"punt": "P-1", "rel": "FOTOGRAFIES/SPT1.jpg"}]
    assert any("ja assignada" in x for x in w)
    clean2, w2 = LF.validate_selection({"dpsh": 42}, cands)
    assert clean2["dpsh"] is None and any("no és cap candidat" in x for x in w2)


def test_escriptura_amb_copia_de_seguretat_i_source_lector(tmp_path):
    p = _project(tmp_path, with_annex=False); v = p / "validation"; v.mkdir()
    (v / LF.SELECTION).write_text(json.dumps({"site_1": 1, "dpsh": 2}))                   # cau IA antiga
    out = LF.write_selection(p, {"site_1": None, "site_2": None, "dpsh": "FOTOGRAFIES/P2.jpg", "sondeig": None,
                                 "materials": "FOTOGRAFIES/SPT1.jpg"}, {"model": "sonnet"})
    d = json.loads(out.read_text()); assert d["source"] == "lector" and d["dpsh"] == "FOTOGRAFIES/P2.jpg" and d["_lector"]["model"] == "sonnet"
    assert json.loads((v / LF.BACKUP).read_text()) == {"site_1": 1, "dpsh": 2}
    LF.write_selection(p, {"dpsh": "FOTOGRAFIES/P1.jpg"}, {})
    assert json.loads((v / LF.BACKUP).read_text()) == {"site_1": 1, "dpsh": 2}          # la còpia no es sobreescriu


def test_image_manager_accepta_lector_i_no_la_cau_ia(tmp_path):
    from automation.image_manager import ImageManager
    p = _project(tmp_path, with_annex=False); v = p / "validation"; v.mkdir()
    im = ImageManager.__new__(ImageManager); im.project_path = p
    (v / LF.SELECTION).write_text(json.dumps({"source": "lector", "dpsh": "FOTOGRAFIES/P2.jpg", "materials": "FOTOGRAFIES/SPT1.jpg", "site_1": None}))
    sel = im._load_user_photo_selection()
    assert [x.name for x in sel["dpsh"]] == ["P2.jpg"] and [x.name for x in sel["materials"]] == ["SPT1.jpg"] and sel["site"] == []
    (v / LF.SELECTION).write_text(json.dumps({"dpsh": 2, "materials": 3}))                 # cau IA: índexs, sense source
    assert im._load_user_photo_selection() is None


def test_vistes_generals_compten_amb_el_lector(tmp_path):
    from automation.report_generator import ReportGenerator
    p = _project(tmp_path, with_annex=False); v = p / "validation"; v.mkdir()
    g = ReportGenerator.__new__(ReportGenerator); g.project_path = p
    (v / LF.SELECTION).write_text(json.dumps({"source": "lector", "site_1": "FOTOGRAFIES/P1.jpg", "site_2": None}))
    assert g._site_photos_from_user_selection() == 1
    (v / LF.SELECTION).write_text(json.dumps({"site_1": 1, "site_2": 2}))
    assert g._site_photos_from_user_selection() == 0


@pytest.mark.skipif(not (LF.TRUTH_IMG / "castellar").exists(), reason="veritat a mida real fora del repo")
def test_exemplars_leave_one_out(tmp_path):
    ex = LF.exemplar_sheets("castellar", tmp_path)
    assert set(ex) == {"dpsh", "sondeig", "materials", "vistes"}
    for e in ex.values():
        assert "castellar" not in e["slugs"] and Path(e["path"]).exists() and e["n"] >= 1
    assert ex["dpsh"]["n"] == 6 and ex["sondeig"]["n"] == 2          # 7 DPSH menys Castellar; sondeig a Bell-lloc i Anciles


def test_inventari_deduplica_per_md5_i_la_validacio_resol_el_duplicat(tmp_path):
    p = _project(tmp_path, with_annex=False)
    (p / "FOTOGRAFIES" / "DPSH").mkdir(); (p / "FOTOGRAFIES" / "DPSH" / "maquina_dpsh.jpg").write_bytes((p / "FOTOGRAFIES" / "P1.jpg").read_bytes())
    inv = LF.inventory(p, p / "validation" / LF.SUBDIR)
    rels = [c["rel"] for c in inv["candidates"]]
    assert "FOTOGRAFIES/DPSH/maquina_dpsh.jpg" in rels and "FOTOGRAFIES/P1.jpg" not in rels      # un sol candidat: el de la subcarpeta
    c = next(c for c in inv["candidates"] if c["rel"] == "FOTOGRAFIES/DPSH/maquina_dpsh.jpg")
    assert c["duplicates"] == ["FOTOGRAFIES/P1.jpg"] and [x["idx"] for x in inv["candidates"]] == [1, 2, 3, 4]
    clean, _ = LF.validate_selection({"dpsh": "FOTOGRAFIES/P1.jpg"}, inv["candidates"])
    assert clean["dpsh"] == "FOTOGRAFIES/DPSH/maquina_dpsh.jpg"
    prompt = LF.build_prompt(inv, p / "x.jpg", {}, p / "o.json", True)
    assert "el mateix fitxer també com a `FOTOGRAFIES/P1.jpg`" in prompt and "Sondeig a rotació al projecte: sí" in prompt
