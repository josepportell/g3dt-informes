"""Peça 0 del pas 3 d'imatges (2026-09-07): mesura per figura «mateixa font que l'Eva» (`docs/wizard-headless/mesures/imatges_font.py`)."""
import importlib.util
import json
import os
import random
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "docs" / "wizard-headless" / "mesures" / "imatges_font.py"
spec = importlib.util.spec_from_file_location("imatges_font", MOD)
IF = importlib.util.module_from_spec(spec); spec.loader.exec_module(IF)


def _structured(seed: int, size: int = 512):
    """Imatge amb estructura gran (8×8 aleatori ampliat) + soroll fi: phash estable al reescalat, NCC amb pic singular."""
    from PIL import Image
    import numpy as np
    rng = np.random.default_rng(seed)
    coarse = rng.integers(0, 256, size=(8, 8, 3), dtype=np.uint8)
    big = Image.fromarray(coarse, "RGB").resize((size, size), Image.BICUBIC)
    a = np.asarray(big).astype(np.int16) + rng.integers(-20, 21, size=(size, size, 3), dtype=np.int16)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def _truth(tmp_path, slug, figs):
    """figs: llista de (n, slot, PIL) → index.json + fitxers a mida real, com el pas 1."""
    idx = tmp_path / "idx" / slug; img = tmp_path / "img" / slug
    idx.mkdir(parents=True); img.mkdir(parents=True)
    images = []
    for n, slot, im in figs:
        f = f"{n:02d}_{slot}.png"; im.save(img / f)
        images.append({"n": n, "file": f, "media": f"image{n}.png", "md5": f"md5-{n}", "dims": list(im.size), "slot": slot,
                       "static_of": None, "caption": f"Figura {n}. {slot}"})
    (idx / "index.json").write_text(json.dumps({"slug": slug, "images": images}), encoding="utf-8")
    return idx.parent, img.parent


def _ours(tmp_path, name, im):
    p = tmp_path / "ours" / name; p.parent.mkdir(exist_ok=True); im.save(p); return str(p)


def test_mateixa_imatge_reescalada_es_match(tmp_path):
    im = _structured(1)
    idx, img = _truth(tmp_path, "p", [(1, "foto_dpsh", im)])
    ours = {"photo_dpsh_image": _ours(tmp_path, "dpsh.png", im.resize((256, 256)))}
    res = IF.compare_images(IF.truth_figures("p", idx, img), ours)
    assert res["rows"][0]["status"] == "MATCH" and res["rows"][0]["phash_d"] <= IF.PHASH_MAX
    assert res["totals"] == {"MATCH": 1, "CLOSE": 0, "MISMATCH": 0, "NO_DATA": 0} and res["sobrants_n"] == 0


def test_retall_de_la_mateixa_font_es_close(tmp_path):
    """L'Eva posa un retall (el tall de correlació); nosaltres la pàgina sencera: mateixa font, altre retall."""
    full = _structured(2)
    crop = full.crop((60, 90, 300, 330))
    idx, img = _truth(tmp_path, "p", [(1, "fig_tall", crop)])
    ours = {"fig_correlation_image": _ours(tmp_path, "tall.png", full)}
    r = IF.compare_images(IF.truth_figures("p", idx, img), ours)["rows"][0]
    assert r["status"] == "CLOSE" and r["ncc"] >= IF.NCC_MIN and r["dir"] == "veritat dins nostra"


def test_font_diferent_es_mismatch_i_res_es_no_data(tmp_path):
    idx, img = _truth(tmp_path, "p", [(1, "fig_geologic", _structured(3)), (2, "foto_materials", _structured(4))])
    ours = {"fig_geological_image": _ours(tmp_path, "geo.png", _structured(5))}   # materials: no posem res
    res = IF.compare_images(IF.truth_figures("p", idx, img), ours)
    st = {r["slot_eva"]: r["status"] for r in res["rows"]}
    assert st == {"fig_geologic": "MISMATCH", "foto_materials": "NO_DATA"}


def test_assignacio_un_a_un_i_sobrants(tmp_path):
    """Dues fotos de materials de l'Eva i una nostra → una puntuada, l'altra ND; figura del projecte sense figura de l'Eva → sobrant."""
    a, b = _structured(6), _structured(7)
    idx, img = _truth(tmp_path, "p", [(1, "foto_materials", a), (2, "foto_materials", b)])
    ours = {"photo_materials_image": _ours(tmp_path, "mat.png", b), "fig_projecte_image_1": _ours(tmp_path, "proj.png", _structured(8))}
    res = IF.compare_images(IF.truth_figures("p", idx, img), ours)
    by_n = {r["n"]: r["status"] for r in res["rows"]}
    assert by_n == {1: "NO_DATA", 2: "MATCH"}
    assert res["sobrants_n"] == 1 and res["sobrants"][0]["ours_slot"] == "fig_projecte_image_1"


def test_our_images_respecta_condicionals_i_pendents():
    class Inline:  # com docxtpl.InlineImage: el camí és a `image_descriptor`
        def __init__(self, p): self.image_descriptor = p
    here = str(MOD)
    ctx = {"photo_dpsh_image": Inline(here), "photo_sondeig_image": Inline(here), "has_sondeig": False,
           "photo_site_image_1": Inline(here), "photo_site_text": "", "fig_main_plan_image": "[Imatge pendent]",
           "fig_geological_image": "", "fig_correlation_image": Inline("/no/existeix.jpg")}
    assert IF.our_images(ctx) == {"photo_dpsh_image": here}


def test_veritat_exclou_estatiques_extra_i_duplicats(tmp_path):
    im = _structured(9)
    idx, img = _truth(tmp_path, "p", [(1, "fig_situacio", im), (2, "fig_spt_cullera", im), (3, "fig_extra_estabilitat", im),
                                      (4, "foto_materials", im), (5, "foto_materials", im)])
    d = json.loads((idx / "p" / "index.json").read_text()); d["images"][4]["md5"] = d["images"][3]["md5"]   # mateix media
    (idx / "p" / "index.json").write_text(json.dumps(d))
    assert [t["n"] for t in IF.truth_figures("p", idx, img)] == [1, 4]


@pytest.mark.skipif(not (IF.TRUTH_IMG / "castellar").exists(), reason="veritat a mida real fora del repo")
def test_veritat_real_contra_ella_mateixa_es_match():
    """Cada figura de l'Eva (Castellar) posada al nostre forat corresponent ha de donar MATCH: valida càrrega, mapa i llindar."""
    truths = IF.truth_figures("castellar")
    inv = {v: k for k, vs in IF.SLOT_MAP.items() for v in vs if not k.endswith("_2")}   # un forat per ranura de l'Eva
    ours = {inv[t["slot"]]: str(t["path"]) for t in truths if t["slot"] in inv}
    res = IF.compare_images(truths, ours)
    assert res["totals"]["MATCH"] == len(ours) and res["totals"]["MISMATCH"] == 0


def test_mateixa_foto_girada_es_close_rotada(tmp_path):
    im = _structured(10)
    idx, img = _truth(tmp_path, "p", [(1, "foto_materials", im)])
    ours = {"photo_materials_image": _ours(tmp_path, "mat.png", im.rotate(90, expand=True))}
    r = IF.compare_images(IF.truth_figures("p", idx, img), ours)["rows"][0]
    assert r["status"] == "CLOSE" and r["dir"].startswith("rotada") and r["phash_rot"] <= IF.PHASH_MAX


def test_orientacio_exif_del_fitxer_de_camp_es_match(tmp_path):
    """El fitxer de camp porta Orientation=6 (gira 90° en mostrar-se); el signat porta la foto ja girada: mateixa imatge."""
    from PIL import Image
    im = _structured(11, 384)
    shown = im.rotate(-90, expand=True)                 # el que es veu amb Orientation=6
    idx, img = _truth(tmp_path, "p", [(1, "foto_dpsh", shown)])
    p = tmp_path / "ours" / "camp.jpg"; p.parent.mkdir(exist_ok=True)
    exif = Image.Exif(); exif[0x0112] = 6
    im.save(p, exif=exif, quality=95)
    r = IF.compare_images(IF.truth_figures("p", idx, img), {"photo_dpsh_image": str(p)})["rows"][0]
    assert r["status"] == "MATCH"
