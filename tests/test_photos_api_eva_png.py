"""2026-09-09 (acció 1 de l'anàlisi de discrepàncies d'imatges): la pestanya de fotos del wizard (`GET /api/photos/{p}`)
veu els mateixos candidats que el lector de fotos, PNG d'`ALTRES`/`OTROS` de l'Eva inclosos (marcats `kind: eva_png`),
perquè la tria del lector (p. ex. una vista del solar de Google Earth) es pugui veure i canviar."""
import json

from fastapi.testclient import TestClient
from PIL import Image

from web import wizard_service
from web.server import app


def test_list_photos_inclou_els_png_d_altres_marcats(tmp_path, monkeypatch):
    ref = tmp_path / "refs"; p = ref / "4009999 PROVA"
    (p / "FOTOGRAFIES").mkdir(parents=True); (p / "ANNEXES" / "Altres").mkdir(parents=True); (p / "validation").mkdir()
    Image.new("RGB", (64, 48), (200, 100, 50)).save(p / "FOTOGRAFIES" / "P1.jpg")
    Image.new("RGB", (64, 48), (50, 100, 200)).save(p / "ANNEXES" / "Altres" / "F3 VG.png")
    Image.new("RGB", (64, 48), (50, 200, 100)).save(p / "validation" / "retall.png")          # mai
    (p / "validation" / "photo_selection.json").write_text(json.dumps({"source": "lector", "site_1": "ANNEXES/Altres/F3 VG.png"}))
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref)
    r = TestClient(app).get("/api/photos/4009999%20PROVA")
    assert r.status_code == 200, r.text
    d = r.json()
    assert [(x["relative_path"], x["kind"]) for x in d["photos"]] == [("FOTOGRAFIES/P1.jpg", "foto"), ("ANNEXES/Altres/F3 VG.png", "eva_png")]
    assert d["photos"][1]["thumbnail_url"].endswith("?file=ANNEXES/Altres/F3%20VG.png")
    assert d["current_selection"]["site_1"] == "ANNEXES/Altres/F3 VG.png"
