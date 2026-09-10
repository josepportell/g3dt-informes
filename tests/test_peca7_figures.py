"""Peça 7a del pas 3 d'imatges (2026-09-08): la ranura única de figura es parteix en tres blocs amb peu propi
(situació 1-2 a l'1.1, projecte 0-2 a l'1.1, assaigs 0-1 al 2.2) i la numeració de les figures va per presència."""
from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace

from lxml import etree

REPO = Path(__file__).resolve().parents[1]
TPL = REPO / "templates" / "g3dt-jinja-template.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _paras():
    root = etree.fromstring(zipfile.ZipFile(TPL).read("word/document.xml"))
    return ["".join(t.text or "" for t in p.iter(W + "t")) for p in root.find(W + "body").iter(W + "p")]


# ── plantilla ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_situacio_dos_blocs_condicionals_amb_peu_propi():
    ps = _paras()
    i = ps.index("{%p if not fig_situacio_image_2 %}")
    assert ps[i + 1:i + 4] == ["{{ fig_situacio_image_1 }}", "Figura {{ fig_situacio_num }}. Situació de la zona d'estudi.",
                               "{%p endif %}"]
    # les dues imatges van EN LÍNIA en un sol paràgraf: cap taula nova (l'extractor les aparella per ordre)
    assert ps[i + 4:i + 8] == ["{%p if fig_situacio_image_2 %}", "{{ fig_situacio_image_1 }}  {{ fig_situacio_image_2 }}",
                               "Figura {{ fig_situacio_num }} i Figura {{ fig_situacio_2_num }}. Detall de la ubicació de la "
                               "parcel·la en estudi. Font: Projecte.", "{%p endif %}"]


def test_cap_taula_nova_a_la_plantilla():
    """L'extractor de referència aparella les taules del signat amb les de la plantilla per ORDRE: una taula més mou
    totes les veritats que surten de taules (mesurat 2026-09-08: 23-28 claus per projecte)."""
    root = etree.fromstring(zipfile.ZipFile(TPL).read("word/document.xml"))
    assert len(list(root.find(W + "body").iter(W + "tbl"))) == 14


def test_figures_del_projecte_zero_a_dues_a_l_1_1():
    ps = _paras()
    for n in (1, 2):
        i = ps.index(f"{{%p if fig_projecte_image_{n} %}}")
        assert ps[i + 1:i + 4] == [f"{{{{ fig_projecte_image_{n} }}}}",
                                   f"Figura {{{{ fig_projecte_{n}_num }}}}. {{{{ fig_projecte_caption_{n} }}}}", "{%p endif %}"]
    assert ps.index("{%p if fig_projecte_image_2 %}") < ps.index("1.2. CLASSIFICACIÓ DE L’OBRA SEGONS EL CTE")


def test_figura_d_assaigs_al_2_2_amb_el_peu_de_rubi():
    ps = _paras()
    i = ps.index("{%p if fig_assaigs_image %}")
    assert ps[i + 1:i + 4] == ["{{ fig_assaigs_image }}",
                               "Figura {{ fig_assaigs_num }}. Situació de l'estructura projectada i els assaigs realitzats.",
                               "{%p endif %}"]
    assert ps.index("2.2. RECONEIXEMENT DEL TERRENY") < i < ps.index("2.3. JUSTIFICACIÓ DE COMPLIMENT DE CTE")
    assert ps[i - 1].startswith("Els assaigs in situ han estat realitzats per {{ lab_field_company }}")   # posició de Rubí


def test_els_noms_antics_ja_no_son_a_la_plantilla():
    doc = zipfile.ZipFile(TPL).read("word/document.xml").decode()
    for old in ("fig_cadastre_image", "fig_cadastre_num", "fig_main_plan_image", "fig_main_plan_num", "fig_aerea"):
        assert old not in doc, old


# ── numeració per presència ────────────────────────────────────────────────────────────────────────────────────

def _nums(**kw):
    from automation.report_generator import figure_numbers
    n = figure_numbers(**kw)
    return [n[k] for k in ("fig_situacio_num", "fig_situacio_2_num", "fig_projecte_1_num", "fig_projecte_2_num",
                           "fig_assaigs_num", "fig_spt_cullera_num", "fig_geological_num", "fig_correlation_num")]


def test_numeracio_per_presencia_com_als_signats():
    assert _nums() == [1, "", "", "", 2, 3, 4, 5]                                    # Castellar, Rubí, Alcoletge
    assert _nums(n_situacio=2, n_projecte=1, has_assaigs=False) == [1, 2, 3, "", "", 4, 5, 6]   # Bell-lloc
    assert _nums(n_projecte=1) == [1, "", 2, "", 3, 4, 5, 6]                          # Vilanova (i Linyola, creuada)
    assert _nums(n_projecte=2) == [1, "", 2, 3, 4, 5, 6, 7]                           # Anciles
    assert _nums(n_situacio=5, n_projecte=9, has_assaigs=True)[:5] == [1, 2, 3, 4, 5]  # topalls 2 / 2
    assert _nums(has_assaigs=False) == [1, "", "", "", "", 2, 3, 4]                    # cap figura d'assaigs


def test_alies_antics_de_la_numeracio():
    from automation.report_generator import figure_numbers
    n = figure_numbers(n_projecte=1)
    assert (n["fig_cadastre_num"], n["fig_location_num"]) == (1, 1)
    assert (n["fig_main_plan_num"], n["fig_building_num"]) == (3, 3)      # = assaigs
    n = figure_numbers(n_projecte=1, has_assaigs=False)
    assert n["fig_main_plan_num"] == 2                                     # sense assaigs: la del projecte


def test_numeracio_des_del_context_ignora_buits_i_pendents():
    from automation.report_generator import figure_numbers_from_context

    class Img:  # com docxtpl.InlineImage
        pass

    ctx = {"fig_situacio_image_1": Img(), "fig_situacio_image_2": "", "fig_projecte_image_1": "[Imatge pendent]",
           "fig_projecte_image_2": Img(), "fig_assaigs_image": Img()}
    n = figure_numbers_from_context(ctx)
    assert (n["fig_situacio_2_num"], n["fig_projecte_1_num"], n["fig_assaigs_num"], n["fig_spt_cullera_num"]) == ("", 2, 3, 4)
    n = figure_numbers_from_context({})                                    # cap imatge: situació + cullera + geol + tall
    assert (n["fig_assaigs_num"], n["fig_spt_cullera_num"]) == ("", 2)


def test_render_template_renumera_despres_de_les_imatges(monkeypatch, tmp_path):
    """El context surt amb la numeració per defecte (assaigs = 2) i `render_template` la refà amb les imatges reals."""
    from automation import report_generator as RG

    class Img:
        pass

    class FakeMgr:
        def __init__(self, *a, **k): pass
        def build_context(self):
            return {"fig_situacio_image_1": Img(), "fig_situacio_image_2": Img(), "fig_projecte_image_1": Img(),
                    "fig_projecte_image_2": "", "fig_assaigs_image": ""}

    class FakeDoc:
        def __init__(self, *a, **k): self.ctx = None
        def render(self, ctx): self.ctx = dict(ctx)
        def save(self, p): Path(p).write_text("x")

    import docxtpl
    monkeypatch.setattr(docxtpl, "DocxTemplate", FakeDoc)
    import automation.image_manager as IM
    monkeypatch.setattr(IM, "ImageManager", FakeMgr)
    g = RG.ReportGenerator.__new__(RG.ReportGenerator)
    g.template_path = TPL
    g.project_path = tmp_path
    g.report_data = None
    g.warnings = []
    g.errors = []
    ctx = dict(RG.figure_numbers(), _num_site_photos=0)
    assert ctx["fig_assaigs_num"] == 2
    g.render_template(ctx, tmp_path / "out.docx")
    assert (ctx["fig_situacio_2_num"], ctx["fig_projecte_1_num"], ctx["fig_assaigs_num"], ctx["fig_spt_cullera_num"]) == (2, 3, "", 4)


# ── extractor de referència: dos peus amb el mateix forat ──────────────────────────────────────────────────────

def _extract(ref_body):
    from automation import reference_extractor as RE
    from automation.intelligent_audit import TemplateParagraph
    tpl = [
        TemplateParagraph(idx=76, text="Figura {{ fig_situacio_num }}. Situació de la zona d'estudi.",
                          variables=["fig_situacio_num"], is_static=False),
        TemplateParagraph(idx=81, text="Figura {{ fig_situacio_num }} i Figura {{ fig_situacio_2_num }}. Detall de la ubicació "
                          "de la parcel·la en estudi. Font: Projecte.", variables=["fig_situacio_num", "fig_situacio_2_num"],
                          is_static=False),
        TemplateParagraph(idx=85, text="Figura {{ fig_projecte_1_num }}. {{ fig_projecte_caption_1 }}",
                          variables=["fig_projecte_1_num", "fig_projecte_caption_1"], is_static=False),
        TemplateParagraph(idx=172, text="Figura {{ fig_assaigs_num }}. Situació de l'estructura projectada i els assaigs realitzats.",
                          variables=["fig_assaigs_num"], is_static=False),
        TemplateParagraph(idx=203, text="Figura {{ fig_spt_cullera_num }}. Cullera normalitzada. Gràfic extret de “Geotécnia y cimientos II”.",
                          variables=["fig_spt_cullera_num"], is_static=False),
    ]
    v, warns = RE.extract_numbering_variables(tpl, ref_body, tmpl_body_count=500, ref_body_count=len(ref_body))
    return {k: x.value for k, x in v.items()}, warns


def test_bell_lloc_dos_peus_de_situacio_i_cap_d_assaigs():
    v, _ = _extract(["Figura 1 i Figura 2. Detall de la ubicació de la parcel·la en estudi. Font: Projecte.",
                     "Figura 3. Ubicació de l’habitatge a l’interior de la parcel·la. Font: Projecte.",
                     "Figura 4. Cullera normalitzada. Gràfic extret de “Geotécnia y cimientos II”."])
    assert (v["fig_situacio_num"], v["fig_situacio_2_num"], v["fig_spt_cullera_num"]) == ("1", "2", "4")
    assert "fig_assaigs_num" not in v and "fig_projecte_1_num" not in v     # el peu del projecte és del lector: sense text fix


def test_alcoletge_un_peu_de_situacio_i_assaigs_al_2_2():
    v, _ = _extract(["Figura 1. Situació de la zona d’estudi.",
                     "Figura 2. Situació de l’estructura projectada i els assaigs realitzats.",
                     "Figura 3. Cullera normalitzada. Gràfic extret de “Geotécnia y cimientos II”."])
    assert (v["fig_situacio_num"], v["fig_assaigs_num"], v["fig_spt_cullera_num"]) == ("1", "2", "3")
    assert "fig_situacio_2_num" not in v


def test_dos_peus_amb_el_mateix_forat_mana_el_de_mes_puntuacio():
    from automation import reference_extractor as RE
    from automation.intelligent_audit import TemplateParagraph
    tpl = [TemplateParagraph(idx=1, text="Figura {{ x_num }}. Situació de la zona d'estudi.", variables=["x_num"], is_static=False),
           TemplateParagraph(idx=2, text="Figura {{ x_num }}. Situació de la zona d'estudi, amb color taronja.", variables=["x_num"],
                             is_static=False)]
    ref = ["Figura 7. Situació de la zona d’estudi, amb color taronja.", "Figura 9. Situació de la zona d’estudi."]
    v, warns = RE.extract_numbering_variables(tpl, ref, tmpl_body_count=10, ref_body_count=2)
    assert v["x_num"].value in ("7", "9") and any("ja assignat" in w for w in warns)
    # l'índex i la capçalera amb el mateix forat segueixen entrant una sola vegada
    tpl = [TemplateParagraph(idx=1, text="{{ s_num }}. EXCAVABILITAT", variables=["s_num"], is_static=False),
           TemplateParagraph(idx=2, text="{{ s_num }}. EXCAVABILITAT", variables=["s_num"], is_static=False)]
    v, warns = RE.extract_numbering_variables(tpl, ["3.5. EXCAVABILITAT"], tmpl_body_count=10, ref_body_count=1)
    assert v["s_num"].value == "3.5" and not warns


# ── image_manager: claus noves i àlies ─────────────────────────────────────────────────────────────────────────

def test_image_manager_context_porta_les_claus_noves_i_els_alies(tmp_path, monkeypatch):
    from automation.image_manager import ImageManager, PLACEHOLDER_TEXT
    mgr = ImageManager(tmp_path, report_data=SimpleNamespace(has_sondeig=False), tpl=None)
    mgr._cache_dir = tmp_path / "cache"
    mgr._cache_dir.mkdir()
    monkeypatch.setattr(mgr, "_download_icgc_images", lambda: {})
    ctx = mgr.build_context()
    assert ctx["fig_situacio_image_1"] == PLACEHOLDER_TEXT and ctx["fig_situacio_image_2"] == ""
    assert ctx["fig_assaigs_image"] == "" and ctx["fig_projecte_image_1"] == "" and ctx["fig_projecte_caption_2"] == ""
    assert ctx["fig_cadastre_image"] == PLACEHOLDER_TEXT and ctx["fig_main_plan_image"] == PLACEHOLDER_TEXT
    assert ctx["has_plan_crops"] is False


def test_el_retall_amb_punts_va_a_la_ranura_d_assaigs(tmp_path, monkeypatch):
    from automation import image_manager as IM
    mgr = IM.ImageManager(tmp_path, report_data=SimpleNamespace(has_sondeig=False), tpl=None)
    mgr._cache_dir = tmp_path / "cache"                                   # mai la cau real
    mgr._cache_dir.mkdir()
    sheet = tmp_path / "4001670_plànol de situació.pdf"
    sheet.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(mgr, "_download_icgc_images", lambda: {})
    monkeypatch.setattr(IM.ImageManager, "_situation_plan_candidates", lambda self, roles: [sheet])
    calls = []

    def fake_crop(pdf, out, **k):
        calls.append(("plan", pdf.name)); Path(out).write_bytes(b"x"); return out

    monkeypatch.setattr("automation.imatges.retall.crop_plan", fake_crop)
    monkeypatch.setattr("automation.imatges.retall.compose_situation", lambda pdf, out, **k: None)
    monkeypatch.setattr(mgr, "_safe_inline_image", lambda path, **k: f"IMG:{Path(path).name}")
    ctx = mgr.build_context()
    assert ctx["fig_assaigs_image"].startswith("IMG:plan_crop_") and calls == [("plan", sheet.name)]
    assert ctx["fig_main_plan_image"] == ctx["fig_assaigs_image"]            # àlies
    assert ctx["fig_situacio_image_1"] == IM.PLACEHOLDER_TEXT               # sense els dos mapes: pendent, no placeholder callat
    assert ctx["has_plan_crops"] is True
