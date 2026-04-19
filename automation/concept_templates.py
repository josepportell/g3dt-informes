"""Template-pattern hints for narrative concepts.

Eva's Jinja template (`templates/g3dt-jinja-template.docx`) wraps certain
concepts in fixed prose scaffolding. T2 (2026-04-17) showed CC reliably
extracts the *facts* for these concepts but produces different prose than
Eva, so the naive scorer marks them MISS. Feeding the template pattern as
context lets Sonnet 4.6 adapt facts into Eva's phrasing.

Patterns were extracted directly from the Jinja template with `python-docx`
(see docs/G1-calc-findings — inline text around each placeholder). Eva's
reference values across 7 projects were used to confirm the pattern
consistency and to capture the expected opening phrase for concepts that
appear standalone in the template (no surrounding prose).

Scope: narrative concepts where T2 had <33% hit rate. Identity/numeric
concepts (architect_name, num_floors, superficie_*) don't need this — CC
already extracts them correctly and the naive scorer handles format diffs.
"""
from __future__ import annotations


# Pattern strings use {VALUE} as the slot CC should produce. The surrounding
# prose is Eva's template scaffolding; CC should NOT repeat it in its output.
TEMPLATE_PATTERNS: dict[str, str] = {
    "location_sentence": (
        "The template reads: \"L'edificació que es preveu construir es situarà {VALUE}.\" "
        "Produce only the {VALUE} span (no leading \"L'edificació...\" prose). "
        "Typical form: \"entre el Carrer X i el Carrer Y de MUNICIPALITY\" "
        "or \"a una parcel·la ubicada al carrer X nº N, (PARC. codi), MUNICIPALITY, PROVÍNCIA\"."
    ),
    "access_street": (
        "The template reads: \"El dia dels treballs de camp es realitza l'entrada "
        "a la zona d'estudi a través del {VALUE}.\" Produce only the {VALUE} span "
        "(a street name or short access path phrase; no leading \"El dia...\")."
    ),
    "site_description": (
        "Full sentence paragraph, standalone in the template. "
        "Starts with \"El dia dels treballs de camp es realitza l'entrada...\" "
        "and describes site access, cleared/unpaved conditions, visible "
        "topography, surface materials, and nearby constructions. "
        "Match Eva's Catalan professional voice; include the observable facts "
        "from the document plus any planol/site photos data passed in context."
    ),
    "building_structure_desc": (
        "The template reads: \"Segons el projecte executiu es preveu la "
        "construcció d'una estructura {VALUE}, i per tant, no es preveu cap "
        "excavació important...\". Produce only the {VALUE} span (no leading "
        "\"Segons el projecte...\"). Typical form: \"en planta baixa\", "
        "\"de planta baixa + 1 planta\", \"de planta baixa + 2 plantes\" etc."
    ),
    "adjacent_north_fmt": (
        "Single sentence starting with \"Per la part nord, amb {CONTENT}.\" or "
        "\"Per la part nord amb {CONTENT}.\" CONTENT describes what's on the "
        "north side (parcel·la buida, el Carrer X, construccions similars, etc.). "
        "Return the complete single-sentence form with the \"Per la part nord\" prefix."
    ),
    "adjacent_south_fmt": (
        "Single sentence starting with \"Per la part sud, amb {CONTENT}.\" or "
        "\"Per la part sud amb {CONTENT}.\" Return the complete sentence."
    ),
    "adjacent_east_fmt": (
        "Single sentence starting with \"Per la part est, amb {CONTENT}.\" "
        "Sometimes Eva combines east+west into one sentence "
        "(\"Per la part est i oest, amb ...\"). Return the complete sentence."
    ),
    "adjacent_west_fmt": (
        "Single sentence, usually starting with \"I finalment, per la part oest, "
        "amb {CONTENT}.\" or \"Finalment, per la part oest amb {CONTENT}.\" "
        "Return the complete sentence."
    ),
}


def get_template_patterns(concept_ids: list[str]) -> dict[str, str]:
    """Return patterns for the subset of concept_ids that have one registered.

    Concepts without a registered pattern are omitted — callers should treat
    absence as \"CC extracts directly, no template adaptation needed\".
    """
    return {cid: TEMPLATE_PATTERNS[cid] for cid in concept_ids if cid in TEMPLATE_PATTERNS}
