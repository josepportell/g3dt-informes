"""Narrativa per CRITERI (2026-09-06): les fórmules literals dels signats, els forats per criteri i la plantilla."""
import re
import zipfile
from pathlib import Path

from automation.narrative_criteria import (
    SITE_CONDITION_ES, aggressivity_class_from_sulfate, aggressivity_sentence, building_structure_clause,
    de_municipality, empentes_paragraph, language_for, levels_detected, materials_intro, most_unfavourable_level,
    municipality_upper, radon_sentence, site_condition_sentence,
)

REPO = Path(__file__).resolve().parents[1]


def test_materials_intro_signed_formula_ca_and_es():
    assert materials_intro(1) == ("A partir dels assaigs in situ realitzats, s'ha establert un sol nivell de materials des del punt "
                                  "de vista geològic - geotècnic: (veure annex “Registre assaigs mecànics”):")
    assert "s'ha establert dos nivells de materials" in materials_intro(2)
    assert materials_intro(2, "es").startswith("A partir de todos los ensayos realizados en el solar, se puede describir dos niveles")


def test_levels_detected_signed_formula():
    assert levels_detected(1) == ("Es detecta un sol nivell de materials des del punt de vista geològic/geotècnic en el subsòl "
                                  "del solar en estudi.")
    assert levels_detected(2).startswith("Es detecta dos nivells")           # l'Eva: «Es detecta», singular (Linyola, Alcoletge)
    assert levels_detected(2, "es").startswith("A partir de los ensayos realizados se puede describir en el solar en estudio dos niveles")


def test_aggressivity_signed_formula_and_classes():
    assert aggressivity_sentence("Qa") == ("A partir dels resultats dels assaigs de laboratori realitzats, els materials del subsòl "
                                           "on es preveu armar la fonamentació, a priori, es presenten NO AGRESSIUS al formigó.")
    assert "AGRESSIUS (agressivitat FEBLE)" in aggressivity_sentence("Qb")
    assert aggressivity_sentence("").startswith("No s'han realitzat assaigs de laboratori")
    assert aggressivity_sentence("Qa", "es", 2) == ("A partir de los ensayos realizados se determina que los materiales del 2do nivel "
                                                   "descrito se presentan, a priori NO AGRESIVOS al hormigón.")   # Anciles («xxxxxxx» omplert)
    assert aggressivity_class_from_sulfate(89.8) == "Qa" and aggressivity_class_from_sulfate(2500) == "Qb"
    assert aggressivity_class_from_sulfate(None) == ""


def test_radon_sentence_zone_1_0_2_and_municipality_article():
    r = radon_sentence(1, "Castellar del Vallès")
    assert r.value == ("La parcel·la concreta d'estudi es localitza al terme municipal de CASTELLAR DEL VALLÈS i, segons la taula "
                       "existent a l'apèndix B del RD 732/2019, pertany a la ZONA 1.")
    assert any("municipi amb concentracions inadequades" in c.value for c in r.candidates), "variant de Rubí com a candidat"
    assert radon_sentence(0, "Linyola").value.endswith(
        "no pertany a cap municipi amb concentracions inadequades de gas radó en edificis tancats.")
    assert "terme municipal d'ALCOLETGE i" in radon_sentence(1, "Alcoletge").value
    assert "de BELL-LLOC D'URGELL i" in radon_sentence("1", "BELL.LLOC D'URGELL (Lleida)").value   # nom llegit brut → padró
    assert radon_sentence(2, "ANCILES", "es").value.endswith("apéndice B del RD 732/2019, pertenece a ZONA 2.")
    assert "pertenece a Municipios ZONA 1, con concentraciones inadecuadas" in radon_sentence(1, "Vilanova de Segrià", "es").value


def test_municipality_helpers():
    assert municipality_upper("Rubí") == "RUBÍ" and municipality_upper("Anciles (Huesca)") == "ANCILES"
    assert de_municipality("ALCOLETGE") == "d'ALCOLETGE" and de_municipality("RUBÍ") == "de RUBÍ"


def test_site_condition_criterion_matches_the_five_signed_heads():
    tail = ", no s'han detectat marques i/o indicis de processos d'erosió relacionats amb l'escolament hídric superficial, ni es preveu que apareguin."
    assert site_condition_sentence(0.4, None).value == "Com que es tracta d'un solar pla" + tail          # Linyola
    assert site_condition_sentence(4.5, "false").value == "Com que es tracta d'un solar pla" + tail       # Alcoletge
    assert site_condition_sentence(33.6, None).value == "Tot i no ser un solar pla" + tail                 # Castellar
    assert site_condition_sentence(3.3, True).value == "Degut a que es tracta d'un solar antropitzat" + tail   # Bell-lloc
    assert site_condition_sentence(13.2, False).value == "Es tracta d'un solar no antropitzat" + tail      # Rubí
    r = site_condition_sentence(0.4, None)
    assert len(r.candidates) == 4 and r.candidates[0].value == r.value and r.notes, "els altres tres caps com a candidats; antropitzat sense font → nota"
    assert site_condition_sentence(None, None, "es").value == SITE_CONDITION_ES


def test_building_structure_clause_variants_and_legacy_values():
    a = building_structure_clause("PB (planta baixa, 1 nivell)").value
    assert a == ("en planta baixa, i per tant, no es preveu cap excavació important, únicament l'excavació pel sanejament, "
                 "anivellació, i per a la implantació dels elements de fonamentació.")               # Bell-lloc (signat)
    assert building_structure_clause("PB (planta baixa)+porxada, sense pis superior").value.startswith("en planta baixa i porxo, i per tant")   # Rubí
    b = building_structure_clause("Pb+1").value
    assert b == ("sense nivell de soterrani, i per tant, únicament es preveu el sanejament, anivellació, i l'excavació fins a la "
                 "cota de fonamentació.")                                                              # Castellar (signat)
    assert building_structure_clause("").value == b, "plantes desconegudes → (b)"
    assert building_structure_clause("Pb+1PP amb dos semisòtans").value.startswith("amb nivell de soterrani")
    r = building_structure_clause("Pb+1Pp", current="en planta baixa")
    assert r.value == a and "valor curt del wizard" in r.source, "valor curt antic → clàusula sencera"
    eva = "en planta baixa i porxo, i per tant, no es preveu cap excavació important."
    assert building_structure_clause("Pb", current=eva).value == eva, "text de l'Eva: tal qual"
    assert building_structure_clause("PB (planta baixa, 1 planta)", lang="es").value.startswith("de planta baja, y por tanto no se prevé")  # Vilanova
    assert len(r.alternatives) == 2


def test_empentes_and_most_unfavourable_level():
    assert most_unfavourable_level([{"phi": 35, "cohesion": 1.0}, {"phi": 30, "cohesion": 0.5}]) == 2
    assert most_unfavourable_level([]) == 1
    p = empentes_paragraph(1)
    assert p.startswith("Pel dimensionament dels murs que es projectin i pel càlcul de les empentes de terres")
    assert "del 1er nivell que es considera el més desfavorable." in p and "trasdós" in p
    assert empentes_paragraph(1, "es").startswith("Para el dimensionado de los muros del sótano")


def test_language_detection():
    assert language_for("ANCILES") == "es" and language_for("Anciles (Huesca)") == "es"
    assert language_for("Rubí", "habitatge unifamiliar") == "ca"
    assert language_for("Rubí", "vivienda adosada (7 unitats)") == "es"


def test_template_slots_are_whole_sentence_variables():
    """Plantilla (2026-09-06): `site_condition` i `radon_sentence` són paràgrafs sols; `building_structure_desc` només porta
    la capçalera fixa; `csn_radon_text` i `radon_zone_description` han desaparegut."""
    xml = zipfile.ZipFile(REPO / "templates" / "g3dt-jinja-template.docx").read("word/document.xml").decode("utf8")
    paras = ["".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)) for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)]
    assert paras.count("{{ site_condition }}") == 2
    assert paras.count("{{ radon_sentence }}") == 1
    assert sum(p.endswith("estructura {{ building_structure_desc }}") for p in paras) == 2
    assert "csn_radon_text" not in xml and "radon_zone_description" not in xml
    assert not any("Degut a que es tracta d'un solar {{" in p or "Degut a que es tracta d’un solar {{" in p for p in paras)


# --- Peça 3 (2026-09-07): estat del solar, assaigs del GTL, peu de les vistes generals ---------------------------

def test_site_description_criterion_built_sloped_flat_and_eva_text():
    from automation.narrative_criteria import site_description_sentence
    flat = site_description_sentence(3.3, {"has_building": False, "num_floors_above": 0})
    assert flat.value == "El solar es localitza sense construccions ni pavimentacions, anivellat a la rasant del carrer."
    assert any("vegetació de petita alçada" in c.value for c in flat.candidates)          # Bell-lloc / Linyola
    sloped = site_description_sentence("33.6", {"has_building": False, "num_floors_above": 0})
    assert sloped.value.endswith("Topogràficament, el solar presenta pendent.")            # Castellar
    assert any("lleugera baixada" in c.value for c in sloped.candidates)                 # Rubí
    built = site_description_sentence(4.5, {"has_building": True, "num_floors_above": 1})
    assert built.value == "El solar està actualment ocupat per una zona explanada i un edifici en planta baixa."   # Alcoletge
    assert "dues plantes" in site_description_sentence(0, {"has_building": True, "num_floors_above": 2}).value
    unknown = site_description_sentence(None, None)                                       # Rubí: sense UTM ni RC
    assert unknown.value == "El solar es localitza sense construccions ni pavimentacions."
    assert any("sense font" in n for n in unknown.notes) and any(c.value == flat.value for c in unknown.candidates)
    eva = site_description_sentence(0, None, current="La parcel·la es troba uns 15 cm per sota del nivell del carrer.")
    assert eva.value.startswith("La parcel·la es troba") and eva.candidates[1].value == flat.value
    assert site_description_sentence(0, None, lang="es").value.startswith("La parcela se localiza sin construcciones")


def test_lab_tests_lines_eva_vocabulary_from_gtl_block():
    from automation.narrative_criteria import lab_tests_lines, parse_gtl_tests
    only = "Determinació del contingut en ió sulfat en sòls   UNE 83963 / 08PROSPECCIÓ\nTPS,"
    assert lab_tests_lines(only).value == "1 assaig de contingut en sulfats UNE 83963 : 2008"       # Castellar, Bell-lloc
    rubi = ("Anàlisi granulomètrica d'un sòl per tamissat    UNE 103101 / 95\n"
            "   Determinació del límit líquid d'un sòl    UNE 103103 / 94PROSPECCIÓ\n"
            "   Determinació del límit plàstic d'un sòl    UNE 103104 / 93\n"
            "TPS,   Determinació del contingut en ió sulfat en sòls   UNE 83963 / 08")
    r = lab_tests_lines(rubi)
    assert r.value.split("\n") == ["Anàlisi granulomètrica d'un sòl per tamissat UNE 103101/95",
                                   "Assaig de Límits d'Atterberg UNE 103103/94 – 104/93",
                                   "Assaig de contingut en sulfats UNE 83963 : 2008"]
    assert "Determinació de Límits d'Atterberg d'un sòl UNE 103103/94-104/93" in r.candidates[1].value   # forma de Rubí
    assert r.candidates[2].value.count("\n") == 3                                                     # 4 línies literals
    linyola = ("Determinació del límit líquid d'un sòl    UNE 103103 / 94\nDeterminació del límit plàstic d'un sòl    UNE 103104 / 93\n"
               "Determinació del contingut en ió sulfat en sòls   UNE 83963 / 08\nAssaig Lambe    UNE 103600 / 96")
    ly = lab_tests_lines(linyola)
    assert ly.value.split("\n")[1] == "Assaig d'expansivitat Lambe UNE 103600/96" and ly.value.endswith("UNE 83963 : 2008")
    assert [t["kind"] for t in parse_gtl_tests(linyola)] == ["atterberg", "lambe", "sulfats"]         # ordre canònic
    assert lab_tests_lines("").value == "" and not lab_tests_lines(None).candidates
    assert lab_tests_lines(only, "es").value == "Determinación del contenido en ión sulfato en suelos UNE 83963 / 08"


def test_photo_site_caption_conditional():
    from automation.narrative_criteria import photo_site_caption
    assert photo_site_caption(0) == "" and photo_site_caption(None) == ""
    assert photo_site_caption(2) == "Fotografia 1 i Fotografia 2. Vistes generals de la zona d'estudi."   # Bell-lloc
    assert photo_site_caption(1) == "Fotografia 1. Vista general de la zona d'estudi."                  # Rubí (sense «Google Earth»)
    assert photo_site_caption(1, "es") == "Fotografía 1. Vista general de la zona de estudio."


def test_template_site_photo_block_is_conditional():
    xml = zipfile.ZipFile(REPO / "templates" / "g3dt-jinja-template.docx").read("word/document.xml").decode("utf8")
    assert xml.count("{%p if photo_site_text %}") == 1 and xml.count("{{ photo_site_text }}") == 1
    assert "{{ photo_site_text }}. Vistes generals" not in xml
    i, j = xml.index("{%p if photo_site_text %}"), xml.index("{{ photo_site_text }}")
    assert "photo_site_image_1" in xml[i:j] and "{%p endif %}" in xml[j:j + 4000]
