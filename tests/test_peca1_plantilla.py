"""Peça 1 del pas 3 d'imatges (2026-09-07): plantilla petita — `fig_aerea` fora, foto de materials una vegada (1r nivell),
pastís de Rubí i media morts fora, numeració sense l'aèria."""
import re
import zipfile
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
TPL = REPO / "templates" / "g3dt-jinja-template.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _paras():
    from lxml import etree
    root = etree.fromstring(zipfile.ZipFile(TPL).read("word/document.xml"))
    return ["".join(t.text or "" for t in p.iter(W + "t")) for p in root.find(W + "body").iter(W + "p")]


def test_plantilla_sense_aerea_ni_media_morts():
    z = zipfile.ZipFile(TPL)
    media = sorted(n for n in z.namelist() if n.startswith("word/media/"))
    assert media == ["word/media/image10.jpeg", "word/media/image11.jpeg"]      # segell G3 + logo de capçalera
    doc = z.read("word/document.xml").decode()
    assert "fig_aerea" not in doc and "NO PLÀSTICS" not in doc
    rels = z.read("word/_rels/document.xml.rels").decode()
    assert "media/image8.png" not in rels and "media/image10.jpeg" in rels
    assert TPL.stat().st_size < 1_000_000                                       # abans 7,4 MB


def test_situacio_un_sol_paragraf_i_peu():
    ps = _paras()
    i = ps.index("{{ fig_cadastre_image }}")
    assert ps[i + 1] == "Figura {{ fig_cadastre_num }}. Situació de la zona d'estudi."
    assert "{{ fig_aerea_image }}" not in ps


def test_foto_de_materials_una_vegada_dins_el_primer_nivell():
    ps = _paras()
    i = ps.index("{{ photo_materials_image }}")
    assert ps[i - 1] == "{%p if loop.first %}" and ps[i + 2] == "{%p endif %}"
    assert ps[i + 1] == "Fotografia {{ photo_materials_num }}. Detall dels materials recuperats durant la realització {{ photo_materials_source }}."
    loop_start = max(k for k, s in enumerate(ps[:i]) if s == "{%p for level in soil_levels %}")
    loop_end = min(k for k, s in enumerate(ps) if k > i and s == "{%p endfor %}")
    assert loop_start < i < loop_end                                            # posició de l'Eva: dins el 1r nivell


def test_bloc_granulometric_per_dades_del_projecte():
    ps = _paras()
    i = ps.index("{%p if show_granulometric %}")
    block = ps[i:ps.index("{%p endif %}", i) + 1]
    assert any(s.startswith("{{ level.granulometric_chart") for s in block)
    assert any(s.startswith("{{ level.granulometric_text") for s in block)
    assert not any("SUCS" in s or "SM" in s.split() for s in block)


def _numbering(has_sondeig, lang=None, user_data=None):
    from automation.report_generator import ReportGenerator
    g = ReportGenerator.__new__(ReportGenerator)
    g.report_data = SimpleNamespace(has_sondeig=has_sondeig, num_dpsh_tests=3, report_language=lang, municipality="Lleida",
                                    building_type=None, street_address=None)
    g.user_data = dict(user_data or {})
    g._site_photos_from_user_selection = lambda: 0
    return g._build_numbering_context()


def test_numeracio_sense_aerea():
    n = _numbering(True)
    assert "fig_aerea_num" not in n
    assert [n[k] for k in ("fig_cadastre_num", "fig_main_plan_num", "fig_spt_cullera_num", "fig_geological_num", "fig_correlation_num")] == [1, 2, 3, 4, 5]
    assert (n["photo_dpsh_num"], n["photo_sondeig_num"], n["photo_materials_num"]) == (1, 2, 3)
    assert n["photo_materials_source"] == "del sondeig"
    assert _numbering(False)["photo_materials_source"] == "de l'assaig SPT"
    assert _numbering(True, "es")["photo_materials_source"] == "del sondeo"
    assert _numbering(False, "es")["photo_materials_source"] == "del ensayo SPT"
