"""Bloc 4 (2026-09-07): la NUMERACIÓ del signat (peus i capçaleres) entra a la veritat.

Els textos són els dels 7 signats (soffice → txt, 2026-09-07). Cap conversió: `TemplateParagraph` i llistes de
paràgrafs sintètiques amb els mateixos peus.
"""
from __future__ import annotations

import pytest

from automation import reference_extractor as RE
from automation.intelligent_audit import TemplateParagraph

# Paràgrafs de la plantilla amb numeració (índexs reals de `g3dt-jinja-template.docx`, 2026-09-07).
TEMPLATE = [
    (35, "{{ section_empentes_num }}. EMPENTES DE TERRES", ["section_empentes_num"]),
    (38, "{{ section_estabilitat_num }}. ESTABILITAT DE VESSANT", ["section_estabilitat_num"]),
    (68, "Figura {{ fig_cadastre_num }} i Figura {{ fig_aerea_num }}. Detall de la ubicació de la parcel·la en estudi. "
         "Font: Projecte.", ["fig_cadastre_num", "fig_aerea_num"]),
    (70, "Figura {{ fig_main_plan_num }}. Ubicació de l'habitatge a l'interior de la parcel·la. Font: Projecte.",
     ["fig_main_plan_num"]),
    (170, "Fotografia {{ photo_dpsh_num }}. Vista de la màquina utilitzada en un dels assaigs de penetració dinàmica DPSH.",
     ["photo_dpsh_num"]),
    (175, "{{ section_sondeig_num }}. Sondeig a rotació amb bateria continua", ["section_sondeig_num"]),
    (183, "Fotografia {{ photo_sondeig_num }}. Vista de la màquina utilitzada per a la realització del sondeig a rotació.",
     ["photo_sondeig_num"]),
    (186, "{{ section_spt_num }}. Assaig tipus S.P.T. (“Standard Penetration Test”)", ["section_spt_num"]),
    (194, "{{ section_resum_num }}. Resum dels assaigs in-situ realitzats", ["section_resum_num"]),
    (212, "Taula {{ table_lab_num }}. Resum dels assaigs de laboratori realitzats.", ["table_lab_num"]),
    (262, "Fotografia {{ photo_materials_num }}. Detall dels materials del {{ level.ordinal }} nivell.",
     ["photo_materials_num", "level.ordinal"]),
    (333, "{{ section_excavabilitat_num }}. EXCAVABILITAT", ["section_excavabilitat_num"]),
    (429, "Figura {{ fig_correlation_num }}. Detall del tall de correlació que s’adjunta als annexes.",
     ["fig_correlation_num"]),
    (471, "{{ section_empentes_num }}. EMPENTES DE TERRES", ["section_empentes_num"]),
]


def _tmpl() -> list[TemplateParagraph]:
    return [TemplateParagraph(idx=i, text=t, variables=v, is_static=False) for i, t, v in TEMPLATE]


def _extract(ref_body: list[str]):
    tp = _tmpl()
    return RE.extract_numbering_variables(tp, ref_body, tmpl_body_count=500, ref_body_count=len(ref_body))


def _values(ref_body: list[str]) -> dict[str, str]:
    v, _ = _extract(ref_body)
    return {k: x.value for k, x in v.items()}


# ---------------------------------------------------------------------------------------------------------------
# Signats
# ---------------------------------------------------------------------------------------------------------------

RUBI = [   # sense sondeig, sense empentes; Fotografia 1 = vista general (Google Earth)
    "2.2. RECONEIXEMENT DEL TERRENY",
    "2.4.1. Assaigs de penetració tipus “DPSH”",
    "Fotografia 1. Vista general de la zona d’estudi (Google Earth, Agost 2024).",
    "Figura 2. Situació de l’estructura projectada i els assaigs realitzats.",
    "Fotografia 2. Vista de la màquina utilitzada en un dels assaigs de penetració dinàmica DPSH.",
    "2.4.2. Assaig tipus S.P.T. (“Standard Penetration Test”)",
    "2.4.3. Resum dels assaigs in-situ realitzats",
    "Taula 3 i 4. Resum dels assaigs in situ realitzat. *msnm: metres sobre el nivell del mar.",
    "Taula 5. Resum dels assaigs de laboratori realitzats.",
    "Fotografia 3. Detall dels materials del primer nivell.",
    "3.3.3. Permeabilitat dels materials",
    "3.4. AGRESSIVITAT DEL MEDI",
    "3.5. EXCAVABILITAT",
    "Figura 5. Detall del tall de correlació que s’adjunta als annexes.",
    "4.3. FONAMENTACIÓ",
]

CASTELLAR = [   # amb sondeig, empentes i estabilitat; salta la Fotografia 3; el tall és «Figura 5. Tall de correlació.»
    "Figura 1. Situació de la zona d’estudi, amb color taronja. (mapes topogràfic i ortofoto, ICGC 2025, modificat).",
    "Figura 2. Emplaçament de l’habitatge projecte i els assaigs realitzats.",
    "Fotografia 1. Vista de la màquina utilitzada en un dels assaigs de penetració dinàmica realitzats.",
    "2.4.2. Sondeig a Rotació amb Bateria Contínua",
    "Fotografia 2. Vista de la màquina utilitzada per a la realització del sondeig a rotació.",
    "2.4.3. Assaig tipus S.P.T. (“Standard Penetration Test”)",
    "2.4.4. Resum dels assaigs in-situ realitzats",
    "Taula 6. Resum dels assaigs de laboratori realitzats.",
    "Fotografia 4. Detall dels materials recuperats durant la realització del sondeig S-1.",
    "3.5. EXCAVABILITAT",
    "Figura 5. Tall de correlació.",
    "4.4. EMPENTES DE TERRES",
    "4.5. ESTABILITAT DEL VESSANT",
]


def test_rubi_sense_sondeig_ni_empentes_queden_en_blanc():
    """La foto del sondeig NO pren la de la DPSH (ratio 0,59 però contenció 0,5) ni la secció 4.4 la 2.2
    («RECONEIXEMENT DEL TERRENY», 0,65 < 0,70); la Fotografia 1 (vista general) no és cap forat de la plantilla."""
    v = _values(RUBI)
    assert v["photo_dpsh_num"] == "2"
    assert v["photo_materials_num"] == "3"
    assert v["table_lab_num"] == "5"
    assert v["fig_correlation_num"] == "5"
    assert v["section_spt_num"] == "2.4.2"
    assert v["section_resum_num"] == "2.4.3"
    assert v["section_excavabilitat_num"] == "3.5"
    for absent in ("photo_sondeig_num", "section_sondeig_num", "section_empentes_num", "section_estabilitat_num",
                   "fig_cadastre_num", "fig_aerea_num", "fig_main_plan_num"):
        assert absent not in v, absent


def test_castellar_amb_sondeig_i_empentes():
    v = _values(CASTELLAR)
    assert v["photo_dpsh_num"] == "1"
    assert v["photo_sondeig_num"] == "2"
    assert v["photo_materials_num"] == "4"           # l'Eva salta la 3: la veritat és el que DIU el signat
    assert v["section_sondeig_num"] == "2.4.2"
    assert v["section_spt_num"] == "2.4.3"
    assert v["section_resum_num"] == "2.4.4"
    assert v["section_empentes_num"] == "4.4"
    assert v["section_estabilitat_num"] == "4.5"     # «DEL VESSANT» ↔ «DE VESSANT»: 0,98
    assert v["fig_correlation_num"] == "5"           # «Tall de correlació.»: ratio 0,51, contenció 1,0
    assert "fig_cadastre_num" not in v and "fig_aerea_num" not in v   # el signat porta UNA figura, la plantilla dues


def test_peu_de_dues_figures_nomes_amb_dos_numeros():
    v = _values(["Figura 1 i Figura 2. Detall de la ubicació de la parcel·la en estudi. Font: Projecte."])
    assert (v["fig_cadastre_num"], v["fig_aerea_num"]) == ("1", "2")
    v = _values(["Figura 1. Detall de la ubicació de la parcel·la en estudi. Font: Projecte."])
    assert "fig_cadastre_num" not in v and "fig_aerea_num" not in v


def test_index_i_capçalera_amb_el_mateix_numero_no_es_empat():
    v = _values(["3.5. EXCAVABILITAT\t19", "3.5. EXCAVABILITAT"])
    assert v["section_excavabilitat_num"] == "3.5"


def test_empat_amb_numeros_diferents_es_blanc():
    """Vilanova: tres «Detalle de los materiales…» al mateix ratio → cap; aquí, dues capçaleres iguals amb números
    diferents (el signat s'equivoca) → en blanc, mai «la primera»."""
    v, warns = _extract(["3.5. EXCAVABILITAT", "3.6. EXCAVABILITAT"])
    assert "section_excavabilitat_num" not in v
    assert any("empat" in w for w in warns)


def test_un_a_un_per_tipus():
    """El peu de la DPSH (1,00) s'enduu la seva foto; el del sondeig no pot reutilitzar-la."""
    v = _values(["Fotografia 1. Vista de la màquina utilitzada en un dels assaigs de penetració dinàmica DPSH."])
    assert v == {"photo_dpsh_num": "1"}


def test_tipus_no_es_barregen():
    """Una «Taula 6. Resum dels assaigs de laboratori…» mai omple un forat «Figura»; «Taula 3 i 4. Resum dels assaigs
    in situ» (rang, no `_num`) no omple `table_lab_num` (contenció 0,5)."""
    v = _values(["Figura 6. Resum dels assaigs de laboratori realitzats.",
                 "Taula 3 i 4. Resum dels assaigs in situ realitzat. *msnm: metres sobre el nivell del mar."])
    assert "table_lab_num" not in v


def test_capçaleres_en_castella_passen_el_llindar_i_els_peus_no():
    """Anciles: «EMPUJE DE TIERRAS» 0,74 ≥ 0,70; «Fotografía 1. Detalle del emplazamiento de la máquina…» no arriba
    (contenció CA/ES) → en blanc fins al bloc 5."""
    v = _values(["4.4. EMPUJE DE TIERRAS", "2.4.2. Sondeo a rotación con batería continua",
                 "Fotografía 1. Detalle del emplazamiento de la máquina realizando uno de los ensayos de penetración dinámica DPSH.",
                 "2.2. RECONOCIMIENTO DEL TERRENO"])
    assert v["section_empentes_num"] == "4.4"
    assert v["section_sondeig_num"] == "2.4.2"
    assert "photo_dpsh_num" not in v


@pytest.mark.parametrize("text,expected", [
    ("3. Vista de la màquina", "3"), ("Fotografia 4. Detall", "4"), ("3.5. EXCAVABILITAT", "3.5"),
    ("4.4. EMPENTES DE TERRES\t45", "4.4"), ("Tabla 6. Detalle", "6"), ("3, 4 i 5", None), ("abc", None), ("", None),
])
def test_numbering_token(text, expected):
    assert RE._numbering_token(text) == expected


def test_should_skip_deixa_passar_la_numeracio_i_no_les_imatges():
    assert not RE._should_skip_variable("fig_aerea_num")
    assert not RE._should_skip_variable("section_spt_num")
    assert RE._should_skip_variable("photo_dpsh_image")
    assert RE._should_skip_variable("photo_site_text")
    assert RE._should_skip_variable("level.num")
    assert RE._is_numbering("table_lab_num") and not RE._is_numbering("table_dpsh_range")


def test_mesura_fix_es_text_exacte_i_buit_es_x():
    import importlib.util, sys
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "docs" / "wizard-headless" / "mesures" / "mesura_341.py"
    spec = importlib.util.spec_from_file_location("mesura_341", path)
    M = importlib.util.module_from_spec(spec)
    sys.modules["mesura_341"] = M
    spec.loader.exec_module(M)
    eva = {"section_resum_num": {"value": "2.4.4"}, "photo_materials_num": {"value": "4"},
           "section_empentes_num": {"value": "4.4"}, "table_lab_num": {"value": "6"}}
    ctx = {"section_resum_num": "2.4.4", "photo_materials_num": 3, "section_empentes_num": "", "table_lab_num": 6}
    rows = {r["var"]: r["status"] for r in M.compare_scalars(eva, ctx, {}, {})}
    assert rows == {"section_resum_num": "MATCH", "photo_materials_num": "MISMATCH",
                    "section_empentes_num": "MISMATCH", "table_lab_num": "MATCH"}
    assert all(M.group_of(k) == "fix" for k in eva)


# ---------------------------------------------------------------------------------------------------------------
# Imatges (bloc 4): clau de la memòria cau amb hash del contingut, i test de presència
# ---------------------------------------------------------------------------------------------------------------

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


def test_image_presence_amb_inline_image_viu():
    import importlib.util, sys
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "docs" / "wizard-headless" / "mesures" / "mesura_341.py"
    spec = importlib.util.spec_from_file_location("mesura_341", path)
    M = importlib.util.module_from_spec(spec); sys.modules["mesura_341"] = M; spec.loader.exec_module(M)

    class InlineImage:            # mateix nom de classe que docxtpl; `str()` hi petaria
        def __str__(self): raise AssertionError("str() sobre InlineImage")
    # peça 7a: situació 1-2, projecte 0-2 i assaigs 0-1 en blocs condicionals (buit = absent, no pendent)
    ctx = {"fig_situacio_image_1": InlineImage(), "fig_situacio_image_2": "", "fig_projecte_image_1": "",
           "fig_projecte_image_2": "", "fig_assaigs_image": "[Imatge pendent]",
           "fig_spt_cullera_image": InlineImage(), "fig_geological_image": InlineImage(), "fig_correlation_image": InlineImage(),
           "photo_dpsh_image": InlineImage(), "photo_sondeig_image": "[Imatge pendent]", "photo_materials_image": InlineImage(),
           "photo_site_image_1": "", "photo_site_image_2": "", "has_sondeig": False}
    p = M.image_presence(ctx)
    assert p["pendent"] == ["fig_assaigs_image"]
    assert p["absent"] == ["fig_situacio_image_2", "fig_projecte_image_1", "fig_projecte_image_2",
                           "photo_sondeig_image", "photo_site_image_1", "photo_site_image_2"]
    assert len(p["present"]) == 6
