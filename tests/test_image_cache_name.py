"""Cau d'imatges: la clau porta el hash del contingut del PDF (portat d'`experiment/nivell-a-2026-08`, commit 4afcc80)."""


def test_cache_name_separa_projectes_amb_el_mateix_nom_de_fitxer(tmp_path):
    """`tall.pdf` de dos projectes → dues imatges; el mateix PDF → la mateixa; el PDF canvia → clau nova."""
    from automation.image_manager import ImageManager
    a = tmp_path / "p1" / "tall.pdf"; b = tmp_path / "p2" / "tall.pdf"
    a.parent.mkdir(); b.parent.mkdir()
    a.write_bytes(b"%PDF-1 projecte 1"); b.write_bytes(b"%PDF-1 projecte 2")
    im = ImageManager.__new__(ImageManager)
    im._cache_dir = tmp_path / "cache"
    ka, kb = im._cache_name("tall", a), im._cache_name("tall", b)
    assert ka != kb and ka.name.startswith("tall_tall_") and ka.suffix == ".jpg"
    assert im._cache_name("tall", a) == ka
    a.write_bytes(b"%PDF-1 projecte 1 v2")
    assert im._cache_name("tall", a) != ka
