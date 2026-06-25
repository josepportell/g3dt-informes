"""Unit tests for the lab extractor — GTL-as-first-class-source fix (A3).

All fixtures are inline string constants (real header/page TEXT), so these
tests do NO PDF/file IO and are safe to run in CI without the /mnt/c data.
"""

from __future__ import annotations

from automation.internal_addresses import resolve_lab_company
from automation.lab_extractor import LabResults, _build_lab_results


# Exact lab footer band present on EVERY page of a real GTL report. Spelled
# WITH commas; the registry canonicalizes it to Eva's no-comma spelling.
LAB_FOOTER = (
    "TPS, PROSPECCIÓ DEL SUBSÒL, SL    B64803075    "
    "Ins. Reg. Merc. de Barcelona Volum 40308, Foli 33, Full B 363136"
)

# The DADES DEL CLIENT / SOL.LICITANT block — carries G3's OWN NIF
# (B25364589) and the Vallbona office address. Must NOT be picked as the lab.
CLIENT_BLOCK = (
    "DADES DEL CLIENT:\n"
    "Nom:\n"
    "G3 Desenvolupament Territorial, SL\n"
    "NIF:\n"
    "B25364589\n"
    "Adreça:\n"
    "C/ Vallbona núm. 22  -  25268 Els Omells de Na Gaia (Lleida)\n"
)

CANONICAL_LAB = "TPS PROSPECCIÓ DEL SUBSÒL SL"


class TestResolveLabCompany:
    def test_real_footer_picks_lab_not_client(self):
        text = CLIENT_BLOCK + "\n" + LAB_FOOTER + "\n"
        name, nif = resolve_lab_company(text)
        # Must resolve to the canonical (no-comma) spelling, never G3's NIF.
        assert name == CANONICAL_LAB
        assert nif == "B64803075"
        assert nif != "B25364589"

    def test_unknown_lab_returns_parsed_name(self):
        text = (
            "ACME GEOTECNIA SL    B12345678    "
            "Ins. Reg. Merc. de Barcelona Volum 1, Foli 2, Full B 3\n"
        )
        name, nif = resolve_lab_company(text)
        assert name == "ACME GEOTECNIA SL"
        assert nif == "B12345678"

    def test_unknown_lab_name_not_polluted_by_prior_lines(self):
        # The line-start anchor must keep the captured name on its own line,
        # never absorbing leading tokens from preceding content.
        text = (
            "Polígon industrial Golparc, Avgda. Mediterrània  Tel: 973 60 47 00\n"
            "ACME GEOTECNIA SL    B12345678    Ins. Reg. Merc. de Barcelona\n"
        )
        name, nif = resolve_lab_company(text)
        assert name == "ACME GEOTECNIA SL"
        assert nif == "B12345678"

    def test_no_footer_returns_none(self):
        # B25364589 is present but with no "Ins. Reg" marker after it.
        text = "Some report text mentioning B25364589 but no registry marker."
        assert resolve_lab_company(text) == (None, None)

    def test_empty_string_returns_none(self):
        assert resolve_lab_company("") == (None, None)

    def test_non_string_returns_none(self):
        assert resolve_lab_company(None) == (None, None)  # type: ignore[arg-type]


# Minimal but faithful GTL page text (GTL-only project, no LAB*.pdf).
GTL_ONLY_TEXT = (
    CLIENT_BLOCK
    + "Mostra:\n"
    + "SPT2 P3\n"
    + "Cota d'extracció (m):\n"
    + "1,8 - 2,4\n"
    + "ASSAIGS REALITZATS:\n"
    + "Determinació del contingut en ió sulfat en sòls   -   UNE 83963 : 2008\n"
    + "g\n"
    + "204,7\n"
    + "mg/kg\n"
    + LAB_FOOTER + "\n"
)


class TestBuildLabResults:
    def test_gtl_only_populates_lab_company_and_sulfate(self):
        """Regression lock for the early-return bug: GTL-only must fully populate."""
        results = _build_lab_results(
            lab_text='',
            gtl_text=GTL_ONLY_TEXT,
            lab_path='',
            gtl_path='/proj/4849-GTL-26 Vacarisses.pdf',
        )
        assert results.lab_testing_company == CANONICAL_LAB
        assert results.lab_field_company == CANONICAL_LAB
        assert results.sulfate_mg_kg is not None
        assert abs(results.sulfate_mg_kg - 204.7) < 0.01
        assert results.lab_sample_id == "SPT-2"
        assert results.lab_location == "P-3"
        assert results.gtl_source_file.endswith("Vacarisses.pdf")
        assert results.source_file == ''

    def test_both_empty_returns_empty(self):
        results = _build_lab_results(lab_text='', gtl_text='')
        assert isinstance(results, LabResults)
        assert results.lab_testing_company == ''
        assert results.lab_field_company == ''
        assert results.sulfate_mg_kg is None
        assert results.tests == []

    def test_lab_pdf_keeps_sulfate_primacy(self):
        """Lab PDF present → sulfate comes from lab_text, company still TPS."""
        lab_text = (
            "Sulfats solubles UNE 83963:2008 ... 89,8 mg/kg\n"
            "Mostra:\nMA1 S1\n"
        )
        results = _build_lab_results(
            lab_text=lab_text,
            gtl_text=GTL_ONLY_TEXT,  # GTL carries 204,7 + footer
            lab_path='/proj/LAB.pdf',
            gtl_path='/proj/GTL.pdf',
        )
        assert results.lab_testing_company == CANONICAL_LAB
        # Sulfate MUST come from the lab PDF (89.8), not the GTL (204.7).
        assert results.sulfate_mg_kg is not None
        assert abs(results.sulfate_mg_kg - 89.8) < 0.01
        assert results.source_file == '/proj/LAB.pdf'
        assert results.gtl_source_file == '/proj/GTL.pdf'


class TestExtractLabResultsRouting:
    """Routing-level tests (IO seams monkeypatched, no real PDFs).

    These lock the A3 early-return bug at the routing boundary: reintroducing
    `if not lab_pdf: return LabResults()` would make these fail, whereas the
    pure-helper tests above would still pass green.
    """

    def test_extract_routes_to_gtl_when_no_lab_pdf(self, monkeypatch):
        import automation.lab_extractor as lx
        from pathlib import Path

        monkeypatch.setattr(lx, "_find_lab_pdf", lambda p: None)
        monkeypatch.setattr(lx, "_find_gtl_pdf", lambda p: Path("/proj/GTL.pdf"))
        monkeypatch.setattr(lx, "_read_pdf_text", lambda p: GTL_ONLY_TEXT)

        results = lx.extract_lab_results("/proj")
        assert results.lab_testing_company == CANONICAL_LAB
        assert results.sulfate_mg_kg is not None
        assert results.source_file == ''
        assert results.gtl_source_file.endswith("GTL.pdf")

    def test_extract_returns_empty_when_no_pdfs(self, monkeypatch):
        # Both finders return None → early empty return BEFORE any fitz use.
        import automation.lab_extractor as lx

        monkeypatch.setattr(lx, "_find_lab_pdf", lambda p: None)
        monkeypatch.setattr(lx, "_find_gtl_pdf", lambda p: None)

        results = lx.extract_lab_results("/proj")
        assert isinstance(results, LabResults)
        assert results.lab_testing_company == ''
        assert results.sulfate_mg_kg is None
        assert results.source_file == ''
        assert results.gtl_source_file == ''
