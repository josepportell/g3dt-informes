"""Unit tests for the Via A pressupost parser (`_parse_docs_fields`).

These pin three field extractions that were fixed on 2026-06-25 after grounding
the regexes against the 7 real pressupostos in /mnt/c/claude/g3dt/projectes/:

  1. num_planned_dpsh — was Catalan-only ("assaigs de penetració dinàmica"),
     so the two Spanish projects (Vilanova, Anciles) returned nothing. Now the
     regex accepts the ES form ("ensayos de penetración dinámica") too. 5/7→7/7.
  2. building_category — the CA template writes "Tipus d'edifici:" with a
     U+2019 apostrophe (not ASCII '), and the ES template writes "Tipo de
     Edificio." with a period separator. The old regex matched neither. 0/7→5/7.
  3. num_planned_sondeig — the old whole-document regex matched the budget
     line-item table header ("SONDEIG A ROTACIO …"), which PDF column scrambling
     can prefix with a stray quantity → spurious counts. The fix scopes the
     search to the campaign-prose window, where only the genuine planned-test
     list lives. The budget table (~900 chars further down) can no longer leak.

The fixtures mirror the real documents' line structure (verbatim phrasings,
the same Unicode apostrophes, and a realistic far-down budget table) so the
tests fail if the anchoring logic regresses.
"""
from __future__ import annotations

from web.vision_fast import _parse_docs_fields


# --- realistic document fragments -------------------------------------------

# A budget line-item table, placed far below the campaign list in the real PDFs.
# The leading "1" before the SONDEIG header reproduces PDF column scrambling:
# the old regex matched it and emitted a spurious sondeig count.
_BUDGET_TABLE_CA = (
    "Els treballs es realitzaran sota la supervisió d'un geòleg col·legiat.\n"
    + ("Condicions generals del servei i clàusules de protecció de dades. " * 12)
    + "\nUNITATS D'ASSAIG DE PENETRACIO DINAMICA DPSH\n"
    "1\nSONDEIG A ROTACIO AMB BATERIA CONTINUA\n"
    "INCLOU DESPLAÇAMENT I ASSAIG SPT\n"
)

_CA_WITH_SONDEIG = (
    "OBRA:\n"
    "ESTUDI GEOTÈCNIC\n"
    "CARRER MAJOR 12\n"
    "CASTELLAR DEL VALLÈS\n"
    "CLIENT:\n"
    "Tipus d’edifici: C1\n"  # U+2019 apostrophe, colon separator
    "Sota aquestes premisses, s’ha previst la realització de la següent campanya de\n"
    "camp:\n"
    "4 assaigs de penetració dinàmica DPSH\n"
    "1Sondeig a rotació amb bateria continua, que inclou\n"
    "desplaçament, perforació i execució d’assaigs SPT’s\n"
    "Assaigs de laboratori\n"
    + _BUDGET_TABLE_CA
)

_ES_NO_SONDEIG = (
    "OBRA:\n"
    "ESTUDIO GEOTECNICO\n"
    "VILANOVA DE SEGRIA\n"
    "CLIENT:\n"
    "Tipo de Edificio. C0\n"  # period separator, ES
    "Bajo estas premisas, se ha previsto la realización de la siguiente campaña de\n"
    "campo:\n"
    "3 ensayos de penetración dinámica DPSH\n"
    "Ensayo SPT, con recuperación de muestra\n"
    "Ensayos de laboratorio\n"
    + ("Condiciones generales del servicio y cláusulas de protección de datos. " * 12)
    + "\nUNIDADES DE ENSAYO DE PENETRACION DINAMICA\n"
    "1\nSONDEO A ROTACION CON BATERIA CONTINUA\n"
)

_ES_WITH_SONDEIG = (
    "Bajo estas premisas, se ha previsto la realización de la siguiente campaña\n"
    "de campo:\n"
    "5 ensayos de penetración dinámica DPSH\n"
    "2 sondeo a rotación con batería continua, que\n"
    "ensayos SPT\n"
)

# Short-preamble document: the budget line-item table starts only a few lines
# after the campaign list, so the table's scrambled "1\nSONDEO A ROTACION …"
# header falls WITHIN the 600-char backstop window. The campaign list has NO
# sondeig, so the only way to emit a (wrong) count is to read the table — which
# the content-based cut at "UNIDADES DE ENSAYO …" must prevent. This is the
# regression the fixed-window-only version would fail.
_ES_SHORT_PREAMBLE_TABLE = (
    "Bajo estas premisas, se ha previsto la realización de la siguiente campaña\n"
    "de campo:\n"
    "3 ensayos de penetración dinámica DPSH\n"
    "Ensayos de laboratorio\n"
    "UNIDADES DE ENSAYO DE PENETRACION DINAMICA\n"
    "1\nSONDEO A ROTACION CON BATERIA CONTINUA\n"
)

# Campaign list HAS a sondeig and the budget header follows immediately. The
# content cut must not swallow the genuine count (it precedes the header).
_CA_SONDEIG_NEAR_BUDGET = (
    "Sota aquestes premisses, s’ha previst la realització de la següent campanya de\n"
    "camp:\n"
    "4 assaigs de penetració dinàmica DPSH\n"
    "2Sondeig a rotació amb bateria continua, que inclou\n"
    "UNITATS D'ASSAIG DE PENETRACIO DINAMICA DPSH\n"
    "1\nSONDEIG A ROTACIO AMB BATERIA CONTINUA\n"
)


# --- num_planned_dpsh --------------------------------------------------------

def test_dpsh_catalan():
    f = _parse_docs_fields(_CA_WITH_SONDEIG)
    assert f["num_planned_dpsh"]["value"] == 4


def test_dpsh_spanish():
    # Regression for the 5/7→7/7 fix: ES "ensayos de penetración dinámica".
    f = _parse_docs_fields(_ES_NO_SONDEIG)
    assert f["num_planned_dpsh"]["value"] == 3


def test_dpsh_prose_sentence_wins_over_later_text():
    f = _parse_docs_fields(_ES_WITH_SONDEIG + _ES_NO_SONDEIG)
    assert f["num_planned_dpsh"]["value"] == 5  # first prose sentence wins


def test_dpsh_budget_table_header_does_not_leak():
    # The real budget-section header "UNITATS D'ASSAIG DE PENETRACIO DINAMICA"
    # has no digit prefix (it is preceded by "UNITATS D'"), so the dpsh regex
    # — which requires `(\d+)\s+assaig…` — cannot match it. With no campaign
    # prose present, nothing is emitted.
    f = _parse_docs_fields(
        "UNITATS D'ASSAIG DE PENETRACIO DINAMICA DPSH\n"
        "SONDEIG A ROTACIO AMB BATERIA CONTINUA\n"
    )
    assert "num_planned_dpsh" not in f


# --- building_category -------------------------------------------------------

def test_category_catalan_unicode_apostrophe():
    # "Tipus d’edifici: C1" uses U+2019, which the old regex (d[\'e]) missed.
    f = _parse_docs_fields(_CA_WITH_SONDEIG)
    assert f["building_category"]["value"] == "C1"


def test_category_spanish_period_separator():
    # "Tipo de Edificio. C0" — ES template, period separator.
    f = _parse_docs_fields(_ES_NO_SONDEIG)
    assert f["building_category"]["value"] == "C0"


def test_category_legacy_categoria_template():
    f = _parse_docs_fields("Categoria de construcció: C2\n")
    assert f["building_category"]["value"] == "C2"


def test_category_absent_emits_nothing():
    # No value beats a wrong value.
    f = _parse_docs_fields(_ES_WITH_SONDEIG)
    assert "building_category" not in f


# --- num_planned_sondeig -----------------------------------------------------

def test_sondeig_catalan_from_campaign():
    f = _parse_docs_fields(_CA_WITH_SONDEIG)
    assert f["num_planned_sondeig"]["value"] == 1


def test_sondeig_spanish_from_campaign():
    f = _parse_docs_fields(_ES_WITH_SONDEIG)
    assert f["num_planned_sondeig"]["value"] == 2


def test_sondeig_table_header_does_not_leak():
    # The crux of the fix: campaign list has NO sondeig, but the budget table
    # below carries "1\nSONDEO A ROTACION …". The old regex emitted 1; the
    # window-scoped regex must emit nothing.
    f = _parse_docs_fields(_ES_NO_SONDEIG)
    assert "num_planned_sondeig" not in f


def test_sondeig_table_leak_blocked_by_content_cut_short_preamble():
    # Core of the 2026-06-25 hardening: the table sits WITHIN the window
    # (short preamble), so only the content cut at "UNIDADES DE ENSAYO …"
    # keeps the scrambled "1 SONDEO A ROTACION" header out. Campaign list has
    # no sondeig → must emit nothing. Fails if the guard is distance-only.
    f = _parse_docs_fields(_ES_SHORT_PREAMBLE_TABLE)
    assert "num_planned_sondeig" not in f


def test_sondeig_genuine_count_survives_nearby_budget_header():
    # The content cut must not swallow a real campaign sondeig that precedes
    # the budget header.
    f = _parse_docs_fields(_CA_SONDEIG_NEAR_BUDGET)
    assert f["num_planned_sondeig"]["value"] == 2


def test_sondeig_boilerplate_water_clause_ignored():
    # "…sondejos a rotació" in the water-supply clause has no count and a
    # different word form ("sondejos") → never matched.
    text = (
        "Sota aquestes premisses, s’ha previst la realització de la següent campanya de\n"
        "camp:\n"
        "3 assaigs de penetració dinàmica DPSH\n"
        "Es facilitarà aigua a peu d’obra, sondejos a rotació si cal.\n"
    )
    f = _parse_docs_fields(text)
    assert "num_planned_sondeig" not in f


# --- regression: unchanged fields still work --------------------------------

def test_site_address_from_obra_block():
    f = _parse_docs_fields(_CA_WITH_SONDEIG)
    assert f["site_address"]["value"] == "CARRER MAJOR 12, CASTELLAR DEL VALLÈS"


def test_architect_company_from_obra_field():
    text = "OBRA:\nESTUDI ARQUITECTURA SL\nESTUDI GEOTÈCNIC\n"
    f = _parse_docs_fields(text)
    assert f["architect_company"]["value"] == "ESTUDI ARQUITECTURA SL"


def test_empty_text_emits_nothing():
    assert _parse_docs_fields("") == {}
