"""Adjacents i accés per criteri (peça 2, 2026-09-06): referències del projecte, plantes del veí (DNPRC `pt`), vocabulari de
l'Eva amb agrupació de costats, carrer d'accés, frase d'ubicació i introducció; plantilla 2.1.1 arreglada."""
import re
import zipfile
from pathlib import Path

import pytest

from automation import cadastre_adjacents as CA
from automation.adjacent_formatter import (
    _norm_street, access_street_from_adjacents, format_all_adjacents, is_street, resolve_adjacent_fmt,
)
from automation.narrative_criteria import location_sentence_from_streets, municipality_proper
from automation.parcel_context import (
    adjacent_intro, centroid, parse_rc_list, position_in_municipality, shape_word, union_polygon,
)

REPO = Path(__file__).resolve().parents[1]
SQ = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0), (0.0, 0.0)]


def test_parse_rc_list_from_reading_values():
    assert parse_rc_list("3298012DG2039N+3298013DG2039N+3298014DG2039N") == ["3298012DG2039N", "3298013DG2039N", "3298014DG2039N"]
    assert parse_rc_list("4613173CG1141S0001ZU") == ["4613173CG1141S"]            # 20 → 14
    assert parse_rc_list("Polígon 6, Parcel·la 105-B") == []                        # rústica de Rubí: no és RC
    assert parse_rc_list(["8606709CG9280N", "8606709CG9280N"]) == ["8606709CG9280N"]
    assert parse_rc_list(None) == []


def test_union_centroid_and_shape():
    right = [(20.0, 0.0), (40.0, 0.0), (40.0, 20.0), (20.0, 20.0), (20.0, 0.0)]
    u = union_polygon([SQ, right])
    assert centroid(u) == pytest.approx((20.0, 10.0))
    assert shape_word(u) == "rectangular"
    lshape = [(0, 0), (30, 0), (30, 10), (10, 10), (10, 30), (0, 30), (0, 0)]
    assert shape_word(lshape) == "irregular"
    assert shape_word(None) == "rectangular"


def test_position_in_municipality_rose():
    c = (1000.0, 1000.0)
    assert position_in_municipality((1000.0, 2000.0), c) == "nord"
    assert position_in_municipality((300.0, 300.0), c) == "sud-oest"
    assert position_in_municipality((1050.0, 1050.0), c) == "centre"
    assert position_in_municipality((2000.0, 1000.0), c, "es") == "este"
    assert position_in_municipality(None, c) is None


def test_adjacent_intro_signed_formula():
    assert adjacent_intro("nord", "Castellar del Vallès", "quasi rectangular") == (
        "La parcel·la objecte d'estudi es situa al nord del municipi de Castellar del Vallès, pren una morfologia quasi rectangular i limita:")
    assert adjacent_intro(None, "Rubí").startswith("La parcel·la objecte d'estudi es situa al municipi de Rubí")
    assert adjacent_intro("norte", "Anciles", "rectangular", "es") == (
        "La parcela objeto de estudio se sitúa en el norte del municipio de Anciles, tiene una morfología rectangular y limita:")


_DNPRC = """<consulta_dnp><bico><bi><debi><luso>Residencial</luso></debi><lcons>
<cons><lcd>ALMACEN</lcd><dt><lourb><loint><es>1</es><pt>00</pt><pu>01</pu></loint></lourb></dt><dfcons><stl>15</stl></dfcons></cons>
<cons><lcd>VIVIENDA</lcd><dt><lourb><loint><es>1</es><pt>00</pt><pu>01</pu></loint></lourb></dt><dfcons><stl>162</stl></dfcons></cons>
<cons><lcd>VIVIENDA</lcd><dt><lourb><loint><es>1</es><pt>01</pt><pu>01</pu></loint></lourb></dt><dfcons><stl>80</stl></dfcons></cons>
<cons><lcd>ALMACEN</lcd><dt><lourb><loint><es>1</es><pt>-1</pt><pu>01</pu></loint></lourb></dt><dfcons><stl>40</stl></dfcons></cons>
<cons><lcd>DEPORTIVO</lcd><dt><lourb><loint><es>1</es><pt>00</pt><pu>01</pu></loint></lourb></dt><dfcons><stl>23</stl></dfcons></cons>
</lcons></bi></bico></consulta_dnp>"""


def test_dnprc_floors_come_from_pt_not_stl(monkeypatch):
    """Abans: `<stl>` (superfície) es llegia com a planta → 0 plantes sempre («parcel·la amb construcció»)."""
    monkeypatch.setattr(CA, "_fetch_xml", lambda url: _DNPRC)
    d = CA._query_building_data("4613144CG1141S")
    assert d["num_floors_above"] == 2 and d["num_floors_below"] == 1 and d["has_pool"] and d["total_built_m2"] == 320.0
    assert CA._describe_neighbor("4613144CG1141S") == (
        "parcel·la amb una construcció aïllada de fins a dos plantes sobre rasant, amb soterrani i piscina")
    monkeypatch.setattr(CA, "_query_building_data", lambda ref: {"num_floors_above": 1, "num_floors_below": 0,
                                                                  "total_built_m2": 90.0, "primary_use": "Residencial",
                                                                  "has_building": True, "has_pool": False})
    assert CA._describe_neighbor("x") == "parcel·la on existeix un edifici aïllat en planta baixa"     # Alcoletge sud


def test_is_ours_accepts_a_set_of_project_references():
    assert CA._is_ours("3298013DG2039N0001AA", {"3298012DG2039N", "3298013DG2039N"})
    assert not CA._is_ours("4613144CG1141S", "4613173CG1141S")
    assert not CA._is_ours(None, {"x"})


def test_format_all_adjacents_eva_vocabulary_grouping_and_last_sentence():
    fmt = format_all_adjacents({"north": "parcel·la buida", "south": "Carrer Antoni Bellet", "east": "parcel·la buida",
                                "west": "parcel·la amb una construcció aïllada de fins a dos plantes sobre rasant"})
    assert fmt["adjacent_north_fmt"] == "Per la part nord i est amb parcel·les buides."          # agrupats
    assert fmt["adjacent_east_fmt"] == ""                                                     # el paràgraf desapareix
    assert fmt["adjacent_south_fmt"] == "Per la part sud amb el Carrer Antoni Bellet."
    assert fmt["adjacent_west_fmt"] == ("I finalment, per la part oest, amb una parcel·la amb una construcció aïllada "
                                        "de fins a dos plantes sobre rasant.")                # Bell-lloc, literal
    # carrer com a última frase; costat buit → «sense informació»
    fmt = format_all_adjacents({"north": "camí d'accés", "south": "parcel·la on existeix un edifici aïllat en planta baixa",
                                "east": "", "west": "Carrer Clot de la Llacuna"})
    assert fmt["adjacent_north_fmt"] == "Per la part nord amb el camí d'accés."
    assert fmt["adjacent_south_fmt"] == "Per la part sud amb una parcel·la on existeix un edifici aïllat en planta baixa."
    assert fmt["adjacent_east_fmt"] == "Per la part est, sense informació."
    assert fmt["adjacent_west_fmt"] == "I finalment, per la part oest, amb el Carrer Clot de la Llacuna."


def test_format_all_adjacents_spanish():
    fmt = format_all_adjacents({"north": "parcel·la buida", "south": "parcel·la buida", "east": "Carrer Santa Gemma",
                                "west": "parcel·la amb una construcció aïllada de fins a quatre plantes sobre rasant"},
                               municipality="Anciles")
    assert fmt["adjacent_north_fmt"] == "Por la parte norte y sur, con parcelas sin edificaciones."
    assert fmt["adjacent_east_fmt"] == "Por la parte este, con la calle Santa Gemma."
    assert fmt["adjacent_west_fmt"] == "Y finalmente, por la parte oeste, con una parcela con un edificio de hasta 4 plantas sobre rasante."


def test_resolve_adjacent_fmt_user_precedence_kept():
    ud = {"adjacent_north_fmt": "Per la part nord amb una parcel·la ocupada per una habitatge unifamiliar.",
          "_sources": {"adjacent_north_fmt": "user"}}
    r = resolve_adjacent_fmt({"north": "parcel·la buida", "south": "parcel·la buida", "east": "x", "west": "y"}, ud)
    assert r["adjacent_north_fmt"].startswith("Per la part nord amb una parcel·la ocupada")
    assert r["adjacent_south_fmt"] == "Per la part sud amb una parcel·la buida."


def test_access_street_from_adjacents_default_and_candidates():
    adj = {"north": "parcel·la buida", "south": "Carrer dels Arbrells", "east": "parcel·la buida", "west": "parcel·la amb construcció"}
    default, cands = access_street_from_adjacents(adj, "Carrer Arbrells")
    assert default == "carrer adjacent situat al sud" and "Carrer existent al sud" in cands and "carrer dels Arbrells" in cands
    adj = {"north": "Carrer Antoni Bellet Pérez", "south": "Carrer Mestre Ramon Ortiz", "east": "", "west": ""}
    assert access_street_from_adjacents(adj, "Situat entre el carrer Mestre Ramon Ortiz i …")[0] == "carrer adjacent situat al sud"
    assert access_street_from_adjacents({"north": "parcel·la buida"}, "x") == ("", [])
    assert access_street_from_adjacents({"west": "Carrer Santa Gemma"}, None, "es")[0] == "calle situada al oeste"
    assert is_street("via pública") and is_street("Camí d'accés") and not is_street("parcel·la buida")


def test_norm_street_and_location_sentence():
    assert _norm_street("Carrer dels Arbrells") == _norm_street("carrer Arbrells") == "arbrells"
    assert _norm_street("C/ Clot de la Llacuna") == _norm_street("Carrer Clot de la Llacuna")
    assert location_sentence_from_streets("Situat entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz",
                                          "Carrer Antoni Bellet Pérez", "BELL.LLOC D'URGELL (Lleida)") == (
        "entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-lloc d'Urgell")           # signat (Bell-Lloc)
    assert location_sentence_from_streets("Carrer Arbrells", "Carrer dels Arbrells", "Castellar del Vallès") == (
        "al Carrer Arbrells de Castellar del Vallès")                                                   # abans: «entre el Carrer Arbrells i el Carrer dels Arbrells»
    assert location_sentence_from_streets("Carrer Girasols", "", "Alcoletge") == "al Carrer Girasols d'Alcoletge"
    assert location_sentence_from_streets("", "", "Alcoletge") == "al terme municipal d'Alcoletge"
    assert location_sentence_from_streets("Carrer Antoni Bellet", "Carrer Mestre Ramon Ortiz", "Bell-lloc d'Urgell") == (
        "entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-lloc d'Urgell")
    assert municipality_proper("BELL.LLOC D'URGELL (Lleida)") == "Bell-lloc d'Urgell" and municipality_proper("ANCILES") == "ANCILES"


def test_template_adjacents_block_fixed():
    """p111/p114 eren forats sobrers («est» abans de la capçalera 2.1.1, «sud» després): ara capçalera 2.1. i introducció;
    els 4 forats reals són paràgrafs condicionals (`{%p if %}`)."""
    xml = zipfile.ZipFile(REPO / "templates" / "g3dt-jinja-template.docx").read("word/document.xml").decode("utf8")
    paras = ["".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)) for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)]
    i = paras.index("2.1.1. Descripció de les parcel·les adjacents ")
    assert paras[i - 1].startswith("2.1. DESCRIPCIÓ DE LA ZONA D")
    assert paras[i + 2] == "{{ adjacent_intro }}"
    assert xml.count("{%p if adjacent_") == 4 and xml.count("{{ adjacent_east_fmt }}") == 1
