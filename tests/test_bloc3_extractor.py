"""Bloc 3 del PLA (2026-09-07): deriva de l'extractor de referència. La veritat surt del signat amb regles que es poden
llegir: la fila portant és la que la frase de la tensió DECLARA, la taula SPT és un bucle, les taules s'aparellen per
etiqueta i per puntuació global, les capçaleres castellanes són capçaleres, i l'àncora pot ser un paràgraf amb forat."""

import pytest

from automation import reference_extractor as RE


# --- fila portant pel que diu el signat ---------------------------------------------------------------------------

SENTENCES = {   # frase de la tensió dels 7 signats (soffice → txt, 2026-09-07) → fila 0-based, files de la taula
    "castellar": ("Per una fonamentació superficial mitjançant sabates, ja sigui aïllades com corregudes, encastada entre "
                  "20-30 cm en els materials de substrat, un cop superats els materials superficials, es podrà adoptar una "
                  "tensió de treball de:", 0, 1),
    "rubi": ("Per una fonamentació mitjançant sabates o bé llosa, encastada entre 30-40 cm en els materials del primer "
             "nivell sanejat un cop extret el tram superficial, es podrà adoptar una tensió admissible de:", 0, 1),
    "bell-lloc": ("Per una fonamentació superficial mitjançant sabates, ja sigui aïllades com corregudes, o bé llosa, "
                  "recolzada en els materials del primer nivell un cop sanejat el tram superficial, es podrà adoptar una "
                  "tensió admissible de:", 0, 1),
    "linyola": ("Per una fonamentació combinada entre sabates i pous reomplerts de formigó pobre, encastats entre 30-40 cm "
                "els materials del segon nivell sanejat, es podrà adoptar una tensió de treball de:", 1, 2),
    "alcoletge": ("Així, es realitza una valoració per a la realització d'una fonamentació superficial mitjançant sabates, "
                  "ja siguin aïllades com corregudes, recolzada sobre els materials del segon nivell sanejat, es podrà "
                  "adoptar una tensió de treball de:", 1, 2),
    "vilanova": ("Así, para una cimentación superficial mediante zapatas ya sean aisladas o corridas, combinada con pozos "
                 "de cimentación, apoyada en los materiales del 2do nivel saneado, se podrá adoptar una tensión de trabajo "
                 "de:", 1, 2),
    "anciles": ("Así, para una cimentación mediante pozos de cimentación rellenados con hormigón pobre, empotrados un mínimo "
                "de 20-40 cm de los materiales del segundo nivel saneado, se podrá adoptar una tensión de trabajo de:", 1, 2),
}


@pytest.mark.parametrize("slug", sorted(SENTENCES))
def test_bearing_row_from_signed_sentence(slug):
    sent, idx, n_rows = SENTENCES[slug]
    paras = ["Un paràgraf anterior amb el primer nivell descrit.", "", sent, "Qa= 3.0 Kg/cm2"]
    assert RE.bearing_row_from_text(paras, n_rows) == idx


def test_bearing_row_last_ordinal_wins_and_never_out_of_range():
    sent = ("un cop superats els materials del primer nivell, recolzada sobre els materials del segon nivell sanejat, "
            "es podrà adoptar una tensió de treball de:")
    assert RE.bearing_row_from_text([sent], 2) == 1
    assert RE.bearing_row_from_text([sent], 1) is None          # l'ordinal no cap a la taula: mai s'inventa
    assert RE.bearing_row_from_text(["cap frase de tensió"], 2) is None
    assert RE.bearing_row_from_text([], 2) is None


# --- taules: capçaleres, ids i notacions de l'Eva --------------------------------------------------------------------

class _Cell:
    def __init__(self, t): self.text = t
class _Row:
    def __init__(self, cells): self.cells = [_Cell(c) for c in cells]
class _Table:
    def __init__(self, rows): self.rows = [_Row(r) for r in rows]


GEOTECH_COLS = RE.LOOP_TABLES[12]["cols"]


def test_header_rows_geotech_anciles_notation():
    """«15-R», «--», «38º», «>350» són dades: abans la 2a fila d'Anciles comptava 2/7 numèrics i la taula perdia el 1er nivell."""
    t = _Table([["Nivel", "Nb", "N", "Densidad (1)", "Cohesión (2)", "Ángulo de fricción interna (3)", "E (4)"],
                ["1er nivel. Arcillas arenosas", "5", "6", "1.90", "0.10", "28º", "90"],
                ["2do nivel. Bolos y gravas", "15-R", "--", "2.00", "0.00", "38º", ">350"]])
    assert RE._detect_header_rows(t, GEOTECH_COLS) == 1


def test_header_rows_spt_es_n30_is_not_an_id():
    """La capçalera «Nº ensayo | Punto | Prof. extracción (m) | N30 | Litología» no és una fila de dades («N30» no és un id)."""
    cols = RE.LOOP_TABLES[6]["cols"]
    t = _Table([["Ensayos SPT/TP/MA"] * 5,
                ["Nº ensayo", "Punto", "Prof. extracción (m)", "N30", "Litología"],
                ["SPT-1", "P-1", "-0.80 a -1.40", "10", "Arcilla limosa"],
                ["SPT-1", "P-3", "-0.80 a -1.40", "24", "Arena fina-media"]])
    assert RE._detect_header_rows(t, cols) == 2
    assert RE._is_table_header_row(dict(zip(cols, ["Nº ensayo", "Punto", "Prof. extracción (m)", "N30", "Litología"])))
    assert not RE._is_table_header_row(dict(zip(cols, ["SPT-1", "P-1", "-0.80 a -1.40", "10", "Arcilla limosa"])))


def test_spt_table_is_a_loop_table():
    assert RE.LOOP_TABLES[6]["name"] == "spt_ma_tests"
    assert RE.LOOP_TABLES[6]["cols"] == ["test_id", "location", "depth_range", "n30", "lithology"]


def test_label_fingerprint_ignores_values():
    t = _Table([["N.º de plantas previstas", "5 viviendas con Pb + 1Pp + Bc"],
                ["Superficie de la parcela (m2)", "1655.01"], ["Superficie construida total (m2)", "1273.79"]])
    assert RE._table_label_fingerprint(t) == ("n.º de plantas previstas | superficie de la parcela (m2) | "
                                              "superficie construida total (m2)")


class _Doc:
    def __init__(self, tables): self.tables = tables


def test_match_tables_global_best_not_greedy():
    """t0 «sondeig» (sense equivalent) no s'ha d'endur la taula SPT que t1 «spt» aparella a 1,0; la resta queda sense."""
    tmpl = _Doc([_Table([["Sondeig a rotació amb bateria continua"] * 5, ["Sondeig", "Cota", "Prof.", "SPT/MA", "N.F."]]),
                 _Table([["Assaigs SPT / MA"] * 5, ["Nº assaig", "Punt", "Prof. Extracció (m)", "N30", "Litologia"]])])
    ref = _Doc([_Table([["Assaigs SPT / MA"] * 5, ["Nº assaig", "Punt", "Prof. Extracció (m)", "N30", "Litologia"],
                        ["SPT-1", "P-3", "-0.60 a -1.20", "40", "Graves i sorres"]]),
                _Table([["Eva Vázquez Marcet Geòloga col 4302", ""]])])
    assert RE.match_tables(tmpl, ref) == {1: 0}


def test_match_tables_anciles_plantes_by_label():
    """Anciles: la fila sencera «n.º de plantas previstas | 5 viviendas…» s'assemblava més a la taula CTE; per etiqueta no."""
    tmpl = _Doc([_Table([["Nº de plantes per habitatge", "{{ plantes }}"], ["Superfície de la parcel·la segons plànols cadastrals  (m2)", "{{ superficie_parcela }}"], ["Superfície construïda total (m2)", "{{ superficie_construida }}"]]),
                 _Table([["Tipus d'edificació considerada:", "{{ cte_edificacio }}"], ["Tipus de sòl considerat:", "{{ cte_sol }}"]])])
    ref = _Doc([_Table([["N.º de plantas previstas", "5 viviendas con Pb + 1Pp + Bc 2 viviendas con Ss + Pb"], ["Superficie de la parcela (m2)", "1655.01"], ["Superficie construida total (m2)", "1273.79"]]),
                _Table([["Tipo de edificación considerada:", "C-1"], ["Tipo de suelo considerado:", "T-1"]])])
    assert RE.match_tables(tmpl, ref) == {0: 0, 1: 1}


# --- àncora amb forat ----------------------------------------------------------------------------------------------

def _tp(idx, text, variables=(), is_static=None):
    from automation.intelligent_audit import TemplateParagraph
    return TemplateParagraph(idx=idx, text=text, variables=list(variables),
                             is_static=(not variables) if is_static is None else is_static)


def test_anchor_accepts_paragraph_with_hole_but_not_heading():
    qa = "Qa= {{ qa_value }} Kg/cm2  amb un factor de seguretat inclòs de F=3"
    tmpl = [_tp(0, qa, ["qa_value"]), _tp(1, ""), _tp(2, "{{ settlement_sentence }}", ["settlement_sentence"])]
    ref = ["Qa= 3.0 Kg/cm2  amb un factor de seguretat inclòs de F=3", "",
           "Els assentaments màxims previstos per la càrrega recomanada anteriorment seran inferiors a 1.20 cm."]
    assert RE._anchor_paragraph(tmpl[2], tmpl, ref, 3) == 2
    head = [_tp(0, "{{ section_empentes_num }}. EMPENTES DE TERRES", ["section_empentes_num"]),
            _tp(1, "{{ empentes_paragraph }}", ["empentes_paragraph"])]
    assert RE._anchor_paragraph(head[1], head, ["5. EMPENTES DE TERRES", "Pel dimensionament dels murs…"], 2) is None


# --- comparadors: claus noves de la veritat ------------------------------------------------------------------------

def test_status_for_new_truth_keys():
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("cpe", pathlib.Path("scripts/compare_prefills_vs_eva.py"))
    cpe = importlib.util.module_from_spec(spec); spec.loader.exec_module(cpe)
    assert cpe.status_for("data_camp_inici_text", "24 de octubre de 2025", "24 d'octubre de 2025") == "MATCH"
    assert cpe.status_for("bearing_layer_idx", 1, "1") == "MATCH" and cpe.status_for("bearing_layer_idx", 1, 0) == "MISMATCH"
    # `settlement_sentence` es puntua pel número (com `settlement`): frases quasi iguals amb 1,80 i 1,50 són una X
    assert cpe.status_for("settlement", "…seran iguals o inferiors a 1.50 cm, immediats…", "…seran iguals o inferiors a 1.80 cm, immediats…") == "MISMATCH"
