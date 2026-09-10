"""Bloc 2 del PLA (2026-09-07): la cua del grup A és FORMAT, no lectura. Cada funció és la forma impresa d'un valor
llegit, idempotent, i no inventa: el que no reconeix surt tal qual. Casos = els 7 signats + vores."""

import pytest

from automation.formatting import format_area, format_cota, format_floor_notation, format_spt_id
from automation.honorifics import de_party, first_name_gender, honorific, is_company, with_honorific
from automation.narrative_criteria import building_type_with_article, de_building_type, municipality_de


# --- plantes -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("read, eva", [
    ("PB+1", "Pb+1Pp"),                                              # Castellar: signat «Pb+1Pp»
    ("PB+PP", "Pb+1Pp"),                                             # Bell-lloc
    ("PB (planta baixa, 1 nivell)", "Pb"),                           # Linyola: signat «Pb»
    ("PB (planta baixa, 1 planta)", "Pb"),                           # Vilanova
    ("PB (planta baixa) + porxada, sense pis superior", "Pb+Porxo"), # Rubí: signat «PB + Porxo»
    ("PB+1PP amb dos semisòtans", "2Ps+Pb+1Pp"),                     # Anciles (veritat de l'extractor errònia: «C-1»)
    ("SÓTANO, PLANTA BAJA y PLANTA 1", "Ps+Pb+1Pp"),
    ("Ps+PB+P1+P2", "Ps+Pb+2Pp"),                                    # notació d'arquitecte, com abans
    ("Pb+1Pp", "Pb+1Pp"),                                            # idempotent
    ("PB + Porxo", "Pb+Porxo"),
])
def test_floor_notation_from_read_text(read, eva):
    assert format_floor_notation(read) == eva


@pytest.mark.parametrize("raw", ["3", "1 (PB)", "", "Pis d'Eva"])
def test_floor_notation_unknown_stays_raw(raw):
    """Cap component reconegut → tal qual (mai un «Pb» inventat)."""
    assert format_floor_notation(raw) == raw


def test_floor_notation_cte_count_unchanged():
    """`parse_floor_count` treballa sobre el text del wizard, no sobre la forma impresa; totes dues diuen el mateix."""
    from automation.cte_classifier import parse_floor_count
    for read in ("PB+1", "PB (planta baixa, 1 nivell)", "PB (planta baixa) + porxada, sense pis superior", "PB+PP"):
        assert parse_floor_count(format_floor_notation(read)) == parse_floor_count(read)


# --- superfícies i cota --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value, printed", [
    ("1284.0", "1.284"),      # Castellar signat «1.284»
    (1167.0, "1.167"),
    ("951.0", "951"), ("571", "571"), (995, "995"),
    ("250.91", "250,91"), ("1655.01", "1.655,01"),
    ("1.284", "1.284"), ("1.655,01", "1.655,01"),     # ja formatat
    ("280+86", "280+86"), ("120 m2", "120 m2"),        # no numèric: tal qual
    ("", ""), (None, ""),
])
def test_format_area(value, printed):
    assert format_area(value) == printed


@pytest.mark.parametrize("value, printed", [
    ("+188,20 msnm", "+188.20"),                                                # Alcoletge signat «+188.20»
    ("199,50 m", "+199.50"),                                                    # Bell-lloc
    ("+245 msnm segons plànol topogràfic del ICGC (-0,15m carrer)", "+245.00"), # Linyola signat «+245.0»
    ("570,90 msnm (segons el plànol ICGC)", "+570.90"),
    ("-4,0 m (respecte el carrer)", "-4.00"),                                   # sistema relatiu (pregunta 2)
    ("+1106,40 (P-1)", "+1106.40"),
    ("+199.50", "+199.50"), ("", ""), (None, ""), ("sense cota", "sense cota"),
])
def test_format_cota(value, printed):
    assert format_cota(value) == printed


def test_comparator_reads_thousands_as_thousands():
    """«1.284» del signat és 1284 m² (abans es llegia 1,284 → MISMATCH contra 1284.0)."""
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("cpe", pathlib.Path("scripts/compare_prefills_vs_eva.py"))
    cpe = importlib.util.module_from_spec(spec); spec.loader.exec_module(cpe)
    assert cpe.status_for("superficie_parcela", "1.284", "1284.0") == "MATCH"
    assert cpe.status_for("superficie_parcela", "1.284", "1.284") == "MATCH"
    assert cpe.status_for("superficie_parcela", "1167", "1.167") == "MATCH"     # Alcoletge (signat sense punt)
    assert cpe.status_for("superficie_construida", "250.91", "250,91") == "MATCH"
    assert cpe.status_for("superficie_parcela", "100", "406") == "MISMATCH"     # Vilanova (pregunta 9)


def test_table_comparator_reads_thousands_as_thousands():
    """`compare_tables_vs_eva` (11 taules): «1.167» imprès = «1167» signat (Alcoletge); «1.414» ≠ «951» (Rubí)."""
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("ctv", pathlib.Path("scripts/compare_tables_vs_eva.py"))
    ctv = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctv)
    assert ctv.classify_cell("1.167", "1167") == "MATCH"
    assert ctv.classify_cell("1.284", "1.284") == "MATCH"
    assert ctv.classify_cell("1.414", "951") == "MISMATCH"
    assert ctv.classify_cell("250,91", "250.91") == "MATCH"
    assert ctv.classify_cell("1.50", "1,50") == "MATCH"      # dos decimals: no és un grup de milers


# --- SPT -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("read, eva", [
    ("SPT1 S1", "SPT-1"), ("SPT1 P3", "SPT-1"), ("SPT1", "SPT-1"), ("spt-1", "SPT-1"), ("MA1 S1", "MA-1"),
    ("SPT-1", "SPT-1"), ("MA-1", "MA-1"), ("", ""), ("S-1", "S-1"),
])
def test_format_spt_id(read, eva):
    assert format_spt_id(read) == eva


def test_tables_report_spt_id_formatted():
    from automation.lectura.tables_report import build_report_tables
    decisions = {"tables": {"spt_ma_tests": {"rows": [
        {"id": {"estat": "segur", "value": "SPT1 S1"}, "punt": {"estat": "segur", "value": "S-1"},
         "profunditat": {"estat": "segur", "value": "-1.00 a -1.60"}, "n30": {"estat": "segur", "value": "62"},
         "litologia": {"estat": "segur", "value": "Grava amb matriu sorrenca"}}]}}}
    rows = build_report_tables(decisions)["spt_ma_tests"]
    assert rows[0]["test_id"] == "SPT-1" and rows[0]["location"] == "S-1"


# --- client: honorífic ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, cover", [
    ("JOANA MARTÍNEZ", "SRA. JOANA MARTÍNEZ"),                         # Rubí (signat sense accent: cel·la X per l'Eva)
    ("SÍLVIA EROLES BALAGUERÓ", "SRA. SÍLVIA EROLES BALAGUERÓ"),      # Linyola
    ("ALBERT SANS BONVEHÍ", "SR. ALBERT SANS BONVEHÍ"),                # Alcoletge
    ("MARIA ALBA BARRAU CASTÁN", "SRA. MARIA ALBA BARRAU CASTÁN"),    # Anciles
    ("WOOD COMFORT PROMOCIONS S.L.U.", "WOOD COMFORT PROMOCIONS S.L.U."),
    ("RAMON MITJANA S.L.", "RAMON MITJANA S.L."),
    ("GRUPO CUENCA GUERRERO S.L.", "GRUPO CUENCA GUERRERO S.L."),
    ("SRA. JOANA MARTINEZ", "SRA. JOANA MARTINEZ"),                    # idempotent
    ("JOSEP MARIA PUIG", "SR. JOSEP MARIA PUIG"), ("MARIA JOSEP PUIG", "SRA. MARIA JOSEP PUIG"),
    ("SÍLVIA EROLES BALAGUERÓ i JAUME NADAL ANDREU", "SÍLVIA EROLES BALAGUERÓ i JAUME NADAL ANDREU"),  # dues persones
    ("XXXQ PUIG", "XXXQ PUIG"),                                        # nom desconegut sense «-a»: cap tractament
    ("", ""),
])
def test_with_honorific(name, cover):
    assert with_honorific(name) == cover


def test_is_company_and_gender():
    assert is_company("ABN ARQUITECTURA BOSCH NOVELL") and is_company("2 GRAUS") and not is_company("ROC CLUSA")
    assert first_name_gender("Roc Clusa") == "m" and first_name_gender("Andrea Rossi") == "f"
    assert honorific("Ajuntament de Linyola") == ""


@pytest.mark.parametrize("name, lang, de", [
    ("SÍLVIA EROLES BALAGUERÓ", "ca", "de la SRA. SÍLVIA EROLES BALAGUERÓ"),   # Linyola signat «en nom de la SRA. …»
    ("ALBERT SANS BONVEHÍ", "ca", "del SR. ALBERT SANS BONVEHÍ"),
    ("RAMON MITJANA S.L.", "ca", "de RAMON MITJANA S.L."),                      # Bell-lloc signat
    ("ABN ARQUITECTURA BOSCH NOVELL", "ca", "d'ABN ARQUITECTURA BOSCH NOVELL"),
    ("ABN ARQUITECTURA BOSCH NOVELL", "es", "de ABN ARQUITECTURA BOSCH NOVELL"),
    ("GRUPO CUENCA GUERRERO S.L.", "es", "de GRUPO CUENCA GUERRERO S.L."),     # Vilanova «en nombre de GRUPO …»
    ("", "ca", ""),
])
def test_de_party(name, lang, de):
    assert de_party(name, lang) == de


# --- tipus d'edificació amb article i municipi amb «de/d'» ---------------------------------------------------------

@pytest.mark.parametrize("bt, lang, article, de", [
    ("habitatge unifamiliar aïllat", "ca", "un habitatge unifamiliar aïllat", "d'un habitatge unifamiliar aïllat"),
    ("3 habitatges unifamiliars d'estructura lleugera, fusta", "ca", "3 habitatges unifamiliars d'estructura lleugera, fusta",
     "de 3 habitatges unifamiliars d'estructura lleugera, fusta"),                                   # Castellar signat
    ("ampliació d'un edifici en planta baixa", "ca", "l'ampliació d'un edifici en planta baixa",
     "de l'ampliació d'un edifici en planta baixa"),                                                 # Alcoletge signat
    ("tancament de porxo en casa unifamiliar", "ca", "el tancament de porxo en casa unifamiliar",
     "del tancament de porxo en casa unifamiliar"),
    ("casa modular", "ca", "una casa modular", "d'una casa modular"),
    ("un nou habitatge unifamiliar", "ca", "un nou habitatge unifamiliar", "d'un nou habitatge unifamiliar"),
    ("vivienda unifamiliar aislada", "es", "una vivienda unifamiliar aislada", "de una vivienda unifamiliar aislada"),
    ("7 viviendas unifamiliares adosadas", "es", "7 viviendas unifamiliares adosadas", "de 7 viviendas unifamiliares adosadas"),
    ("", "ca", "", ""),
])
def test_building_type_article(bt, lang, article, de):
    assert building_type_with_article(bt, lang) == article
    assert de_building_type(bt, lang) == de


@pytest.mark.parametrize("muni, de", [
    ("Alcoletge", "d'Alcoletge"),                         # signat «en el municipi d'Alcoletge» (abans «de Alcoletge»)
    ("BELL.LLOC D'URGELL (Lleida)", "de Bell-lloc d'Urgell"),
    ("Rubí", "de Rubí"), ("Castellar del Vallès", "de Castellar del Vallès"), ("", ""), (None, ""),
])
def test_municipality_de(muni, de):
    assert municipality_de(muni) == de


def test_template_slots_carry_the_preposition():
    """Els tres forats que ara porten l'article dins el valor (plantilla del repo, no la de producció)."""
    from docx import Document
    full = "\n".join(p.text for p in Document("templates/g3dt-jinja-template.docx").paragraphs)
    assert "en nom {{ client_de }}" in full and "en nom de {{ client }}" not in full
    assert "la construcció {{ building_type_de }}." in full and "d'un {{ building_type_lower }}" not in full
    assert "en el municipi {{ municipality_de }}," in full and "de {{ municipality }}" not in full
    assert "{{ architect_name_upper }}{{ architect_company_de }}, en nom" in full and "de l'{{ architect_company }}" not in full


@pytest.mark.parametrize("company, lang, de", [
    ("ABN Arquitectura Bosch Novell", "ca", ", d'ABN Arquitectura Bosch Novell"),
    ("2 Graus", "ca", ", de 2 Graus"),                                       # abans «de l'2 Graus»
    ("BUNYESC ARQUITECTURA EFICIENT, S.L.P", "ca", ", de BUNYESC ARQUITECTURA EFICIENT, S.L.P"),
    ("", "ca", ""),                                                         # abans «de l', en nom»
])
def test_architect_company_de(company, lang, de):
    d = de_party(company, lang)
    assert (f", {d}" if d else "") == de
