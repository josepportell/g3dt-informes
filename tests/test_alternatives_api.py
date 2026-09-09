"""Acció 4 (2026-09-09): les alternatives dels lectors al wizard. `GET /api/alternatives/{p}` (tria actual + alternatives
amb miniatura i raó, fotos i figures), `POST …/choose` (desa la tria de l'Eva amb `source: user`, conserva la resta),
i el calaix de figures (`/api/photos`) que llegeix `figure_selection.json`."""
import json

import fitz
from fastapi.testclient import TestClient
from PIL import Image

from web import api as API
from web import wizard_service
from web.server import app


def _project(tmp_path, monkeypatch):
    ref = tmp_path / "refs"; p = ref / "4009999 PROVA"
    (p / "FOTOGRAFIES").mkdir(parents=True); (p / "validation").mkdir(); (p / "25.9999").mkdir()
    for n, col in (("P1.jpg", (200, 100, 50)), ("P2.jpg", (50, 100, 200)), ("SPT1.jpg", (50, 200, 100))):
        Image.new("RGB", (64, 48), col).save(p / "FOTOGRAFIES" / n)
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page(width=300, height=200); page.draw_rect(fitz.Rect(20 + 40 * i, 20, 200, 150), color=(0, 0, 0), fill=(0.8, 0.5, 0.2))
    doc.save(p / "25.9999" / "PROJECTE.pdf"); doc.close()
    pdf = str(p / "25.9999" / "PROJECTE.pdf")
    (p / "validation" / "photo_selection.json").write_text(json.dumps({
        "source": "lector", "site_1": None, "site_2": None, "dpsh": "FOTOGRAFIES/P1.jpg", "sondeig": None, "materials": "FOTOGRAFIES/SPT1.jpg",
        "alternatives": {"dpsh": [{"rel": "FOTOGRAFIES/P2.jpg", "rao": "P-2, equivalent"}, {"rel": "FOTOGRAFIES/NO.jpg", "rao": "no existeix"}]},
        "_lector": {"raons": {"dpsh": "la primera de l'annex"}, "confianca": {"dpsh": 0.8}, "cap_font": ["site_1", "site_2"]}}), encoding="utf-8")
    (p / "validation" / "figure_selection.json").write_text(json.dumps({
        "source": "lector",
        "assaigs": {"idx": 1, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 1, "src": pdf, "crop": None},
        "projecte": [{"idx": 2, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 2, "src": pdf, "crop": [0, 0, 0.6, 0.8], "caption": "Secció. Font: Projecte."}],
        "situacio": {"idx": 2, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 2, "src": pdf, "crops": [[0, 0, 0.5, 0.5], [0.5, 0, 1, 0.5]]},
        "alternatives": {"assaigs": [{"idx": 2, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 2, "src": pdf, "crop": [0.1, 0.1, 0.9, 0.9], "rao": "retall estret"},
                                     {"idx": 3, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 2, "src": "/etc/passwd", "crop": None, "rao": "camí dolent"}],
                         "projecte": [{"idx": 1, "kind": "project_page", "rel": "25.9999/PROJECTE.pdf", "page": 1, "src": pdf, "crop": None, "caption": "Planta. Font: Projecte.", "rao": "la planta"}]},
        "_lector": {"raons": {"assaigs": "el full de l'Eva", "projecte": "la secció"}, "confianca": {"assaigs": 0.9}, "cap_font": []}}), encoding="utf-8")
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref)
    cache = tmp_path / "cache"; cache.mkdir(); monkeypatch.setattr(API, "_FIGURE_CACHE_DIR", cache)
    return p, cache


def test_list_alternatives_fotos_i_figures(tmp_path, monkeypatch):
    p, cache = _project(tmp_path, monkeypatch)
    r = TestClient(app).get("/api/alternatives/4009999%20PROVA"); assert r.status_code == 200, r.text
    d = r.json(); s = d["slots"]
    assert d["photo_source"] == "lector" and d["figure_source"] == "lector"
    assert s["dpsh"]["current"]["rel"] == "FOTOGRAFIES/P1.jpg" and s["dpsh"]["rao"] == "la primera de l'annex" and s["dpsh"]["confianca"] == 0.8
    assert [a["rel"] for a in s["dpsh"]["alternatives"]] == ["FOTOGRAFIES/P2.jpg"]          # la que no existeix, fora
    assert s["dpsh"]["alternatives"][0]["thumbnail_url"].endswith("?file=FOTOGRAFIES/P2.jpg") and s["dpsh"]["alternatives"][0]["rao"] == "P-2, equivalent"
    assert s["site_1"]["current"] is None and s["site_1"]["cap_font"] is True and s["materials"]["alternatives"] == []
    fa = s["fig_assaigs"]; assert fa["current"]["entry"]["page"] == 1 and fa["current"]["thumbnail_url"].startswith("/api/figure-preview/") and fa["rao"] == "el full de l'Eva"
    assert len(fa["alternatives"]) == 1 and fa["alternatives"][0]["rao"] == "retall estret"     # el `src` fora del projecte i de la cau, fora
    assert fa["alternatives"][0]["thumbnail_url"] and len(list(cache.glob("figsel_alt_*"))) == 2   # assaigs p2 + projecte p1
    p1 = s["fig_projecte_1"]; assert p1["current"]["caption"] == "Secció. Font: Projecte." and [a["rao"] for a in p1["alternatives"]] == ["la planta"]
    p2 = s["fig_projecte_2"]; assert p2["current"] is None and [a.get("caption") for a in p2["alternatives"]] == ["Planta. Font: Projecte."]   # la de projecte 1 no s'ofereix: intercanviar no té sentit amb la 2 buida
    sit = s["fig_situacio"]; assert sit["is_default"] is True and sit["current"] is None and len(sit["alternatives"]) == 1
    assert sit["alternatives"][0]["thumbnail_url"] and sit["alternatives"][0]["thumbnail_url_2"]
    # les miniatures de figura es serveixen des de la cau
    url = fa["current"]["thumbnail_url"]
    assert TestClient(app).get(url).status_code == 200


def test_choose_foto_desa_user_i_conserva_la_resta(tmp_path, monkeypatch):
    p, _ = _project(tmp_path, monkeypatch); c = TestClient(app)
    r = c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "dpsh", "rel": "FOTOGRAFIES/P2.jpg"}); assert r.status_code == 200, r.text
    d = json.loads((p / "validation" / "photo_selection.json").read_text(encoding="utf-8"))
    assert d["source"] == "user" and d["dpsh"] == "FOTOGRAFIES/P2.jpg" and d["materials"] == "FOTOGRAFIES/SPT1.jpg"
    assert d["alternatives"]["dpsh"][0]["rel"] == "FOTOGRAFIES/P2.jpg" and d["_lector"]["raons"]["dpsh"] and d["_lector_selection"]["dpsh"] == "FOTOGRAFIES/P1.jpg"
    # la mateixa foto no pot ser a dos forats: si va a `site_1`, surt de `dpsh` (i la resposta ho diu)
    assert c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "site_1", "rel": "FOTOGRAFIES/P2.jpg"}).json()["cleared"] == ["dpsh"]
    d = json.loads((p / "validation" / "photo_selection.json").read_text(encoding="utf-8"))
    assert d["site_1"] == "FOTOGRAFIES/P2.jpg" and d["dpsh"] is None
    # la tria del lector (P1) torna com a primera alternativa de `dpsh`, i la raó del lector ja no es mostra sota l'actual
    s = c.get("/api/alternatives/4009999%20PROVA").json()["slots"]
    assert s["dpsh"]["current"] is None and s["dpsh"]["rao"] is None and s["dpsh"]["cap_font"] is False
    assert s["dpsh"]["alternatives"][0]["rel"] == "FOTOGRAFIES/P1.jpg" and s["dpsh"]["alternatives"][0]["rao"].startswith("la tria del lector: la primera")
    assert [a["rel"] for a in s["site_1"]["alternatives"]] == []          # P2 hi és l'actual; el lector no en tenia cap
    # la font és PER RANURA: només les que l'Eva ha canviat són «user»; materials continua sent del lector
    assert s["site_1"]["source"] == "user" and s["dpsh"]["source"] == "user" and s["materials"]["source"] == "lector" and s["sondeig"]["source"] == "lector"
    assert c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "dpsh", "rel": "../../etc/passwd"}).status_code == 403
    assert c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "dpsh", "rel": "FOTOGRAFIES/NO.jpg"}).status_code == 404
    assert c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "dpsh", "rel": None}).status_code == 200
    assert json.loads((p / "validation" / "photo_selection.json").read_text(encoding="utf-8"))["dpsh"] is None
    # el generador accepta la tria
    from automation.image_manager import ImageManager
    im = ImageManager.__new__(ImageManager); im.project_path = p
    assert [x.name for x in im._load_user_photo_selection()["site"]] == ["P2.jpg"]


def test_choose_figura_ranura_canviable_i_situacio_doble(tmp_path, monkeypatch):
    p, cache = _project(tmp_path, monkeypatch); c = TestClient(app)
    alts = c.get("/api/alternatives/4009999%20PROVA").json()["slots"]
    alt = alts["fig_assaigs"]["alternatives"][0]["entry"]
    # el retall estret, com a figura del projecte 2 (ranura canviable)
    r = c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_projecte_2", "entry": alt}); assert r.status_code == 200, r.text
    assert r.json()["placed"] == "fig_projecte_2"
    d = json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8"))
    assert d["source"] == "user" and len(d["projecte"]) == 2 and d["projecte"][1]["crop"] == [0.1, 0.1, 0.9, 0.9]
    # amb les dues plenes, la figura 2 s'ofereix a la 1 (intercanvi) i triar-la les reordena
    s2 = c.get("/api/alternatives/4009999%20PROVA").json()["slots"]
    assert s2["fig_projecte_1"]["alternatives"][0]["entry"]["crop"] == [0.1, 0.1, 0.9, 0.9]
    r = c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_projecte_1", "entry": s2["fig_projecte_1"]["alternatives"][0]["entry"]})
    assert r.json()["placed"] == "fig_projecte_1"
    d = json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8"))
    assert d["projecte"][0]["crop"] == [0.1, 0.1, 0.9, 0.9] and d["projecte"][1]["caption"].startswith("Secció")
    r = c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_projecte_2", "entry": d["projecte"][0]})   # i a l'inrevés
    d = json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8"))
    assert r.json()["placed"] == "fig_projecte_2" and d["projecte"][1]["crop"] == [0.1, 0.1, 0.9, 0.9]
    assert d["projecte"][1]["caption"] == "Detall del projecte. Font: Projecte." and d["_lector_selection"]["projecte"][0]["caption"].startswith("Secció")
    assert d["assaigs"]["page"] == 1 and d["alternatives"]["assaigs"][0]["rao"] == "retall estret"        # la resta es conserva
    # el mateix retall com a assaigs: surt del projecte (no s'imprimeix dues vegades)
    c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_assaigs", "entry": alt})
    d = json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8"))
    assert d["assaigs"]["crop"] == [0.1, 0.1, 0.9, 0.9] and len(d["projecte"]) == 1
    # situació doble: la proposta del lector passa a manar quan la tria l'Eva
    sit = alts["fig_situacio"]["alternatives"][0]["entry"]
    c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_situacio", "entry": sit})
    d = json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8"))
    assert len(d["situacio"]["crops"]) == 2
    s2all = c.get("/api/alternatives/4009999%20PROVA").json()["slots"]; s2 = s2all["fig_situacio"]
    assert s2["is_default"] is False and s2["current"]["thumbnail_url_2"] and s2["alternatives"] == []
    assert s2["source"] == "user" and s2all["fig_assaigs"]["source"] == "user"                 # les dues canviades per l'Eva
    assert s2all["fig_projecte_1"]["source"] == "lector" and s2all["fig_projecte_1"]["rao"] == "la secció"   # intacta
    from automation.imatges.lector_figures import apply_selection
    out = apply_selection(p, cache)
    assert out["fig_situacio_image_1"] and out["fig_situacio_image_2"] and out["fig_assaigs_image"]
    # tornar a l'automàtic
    c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_situacio", "entry": None})
    assert json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8"))["situacio"] is None
    # projecte 2 amb la 1 buida: queda a la 1 i la resposta ho diu
    c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_projecte_1", "entry": None})
    c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_projecte_1", "entry": None})
    assert json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8"))["projecte"] == []
    planta = c.get("/api/alternatives/4009999%20PROVA").json()["slots"]["fig_projecte_2"]["alternatives"][0]["entry"]
    r = c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_projecte_2", "entry": planta})
    assert r.json()["placed"] == "fig_projecte_1" and len(json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8"))["projecte"]) == 1
    # cap figura d'assaigs
    c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_assaigs", "entry": None})
    assert json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8"))["assaigs"] is None
    assert c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_assaigs", "entry": {"kind": "img", "rel": "../x.png"}}).status_code == 400
    assert c.post("/api/alternatives/4009999%20PROVA/choose", json={"slot": "fig_x", "rel": None}).status_code == 400


def test_calaix_de_figures_llegeix_la_seleccio(tmp_path, monkeypatch):
    p, cache = _project(tmp_path, monkeypatch)
    (cache / "plan_crop_x.jpg").write_bytes(b"")                                        # prefix antic a la cau: NO ha de manar
    d = TestClient(app).get("/api/photos/4009999%20PROVA").json()
    f = d["figures"]
    assert f["fig_assaigs"]["source"] == "Tria del lector de figures" and f["fig_assaigs"]["filename"].startswith("figsel_assaigs")
    assert f["fig_projecte_1"]["filename"].startswith("figsel_projecte1") and f["fig_projecte_2"]["thumbnail_url"] == ""
    assert f["fig_projecte_2"]["source"].endswith("cap figura")
    assert "fig_situacio" not in f or not f["fig_situacio"]["filename"].startswith("figsel")   # la del lector no s'aplica
    sel = json.loads((p / "validation" / "figure_selection.json").read_text(encoding="utf-8")); sel["source"] = "user"
    (p / "validation" / "figure_selection.json").write_text(json.dumps(sel), encoding="utf-8")
    f = TestClient(app).get("/api/photos/4009999%20PROVA").json()["figures"]
    assert f["fig_situacio"]["filename"].startswith("figsel_situacio1") and f["fig_situacio_2"]["filename"].startswith("figsel_situacio2")
    assert f["fig_assaigs"]["source"] == "Tria de l'Eva"


def test_list_photos_troba_la_carpeta_fotografia_en_singular(tmp_path, monkeypatch):
    ref = tmp_path / "refs"; p = ref / "4009998 PROVA"; (p / "FOTOGRAFIA").mkdir(parents=True)
    Image.new("RGB", (64, 48), (200, 100, 50)).save(p / "FOTOGRAFIA" / "P1.jpeg")
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref); monkeypatch.setattr(API, "_FIGURE_CACHE_DIR", tmp_path / "cache")
    d = TestClient(app).get("/api/photos/4009998%20PROVA").json()
    assert [x["relative_path"] for x in d["photos"]] == ["FOTOGRAFIA/P1.jpeg"]


def test_calaix_nomes_mostra_imatges_de_la_cau_d_aquest_projecte(tmp_path, monkeypatch):
    """La cau d'imatges és global: el calaix mostrava «el més recent» del prefix, que podia ser d'un altre projecte."""
    import hashlib
    ref = tmp_path / "refs"; p = ref / "4009997 PROVA"; (p / "validation").mkdir(parents=True)
    doc = fitz.open(); doc.new_page(width=200, height=100); doc.save(p / "tall.pdf"); doc.close()
    h = hashlib.md5((p / "tall.pdf").read_bytes()).hexdigest()[:10]
    (p / "validation" / "_auto_result.json").write_text(json.dumps({"utm": {"utm_x": 300000.4, "utm_y": 4600000.2}}), encoding="utf-8")
    cache = tmp_path / "cache"; cache.mkdir()
    for n in (f"tall_crop2_tall_{h}.jpg", "tall_crop2_tall_0123456789.jpg", "geological_composite_300000_4600000.png",
              "geological_composite_1_2.png", "plan_crop_altre_projecte_abcdef0123.jpg"):
        Image.new("RGB", (20, 10), (1, 2, 3)).save(cache / n)
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref); monkeypatch.setattr(API, "_FIGURE_CACHE_DIR", cache)
    f = TestClient(app).get("/api/photos/4009997%20PROVA").json()["figures"]
    assert f["fig_correlation"]["filename"] == f"tall_crop2_tall_{h}.jpg"
    assert f["fig_geological"]["filename"] == "geological_composite_300000_4600000.png"
    assert "fig_assaigs" not in f                                   # el retall d'un altre projecte no surt
