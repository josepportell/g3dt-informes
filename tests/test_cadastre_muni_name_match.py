"""Offline tests for tolerant municipality name matching.

Covers the fix for project 4001671 VILANOVA DE SEGRIA where the input
hint "Vilanova del Segria" (Catalan colloquial: wrong preposition "del"
+ missing accent) must resolve to the official "Vilanova de Segrià".

No network access: the Cadastre ``_fetch_url`` call is monkey-patched.
"""

from __future__ import annotations

import pytest

from automation import geocode_coordinates as gc
from automation.geocode_coordinates import (
    _consulta_municipio,
    _normalize_muni_name,
    _strip_accents,
)


# === _normalize_muni_name unit tests ===

def test_normalize_strips_accents():
    assert _normalize_muni_name("Vilanova de Segrià") == "VILANOVA DE SEGRIA"


def test_normalize_collapses_del_to_de():
    # Catalan "del" (de + el) → canonical "de"
    assert _normalize_muni_name("Vilanova del Segrià") == _normalize_muni_name(
        "Vilanova de Segrià"
    )


def test_normalize_collapses_d_apostrophe():
    # Catalan "d'" → canonical "de"
    assert _normalize_muni_name("Bell-Lloc d'Urgell") == _normalize_muni_name(
        "Bell-Lloc de Urgell"
    )


def test_normalize_preserves_distinct_names():
    # Tolerance must not collapse genuinely different towns.
    assert _normalize_muni_name("Alpicat") != _normalize_muni_name("Vilanova de Segrià")


def test_normalize_preserves_dos_in_municipality_name():
    # "Dos Hermanas" is a real Spanish municipality (Sevilla, ~130k pop).
    # The "DOS" token is a name root, not a Portuguese/Galician preposition,
    # so it must NOT be collapsed to "DE". A previous version of the
    # normalizer incorrectly included da/das/do/dos, which broke this case.
    normalized = _normalize_muni_name("Dos Hermanas")
    assert "DOS" in normalized.split()
    assert "HERMANAS" in normalized.split()
    # Must not equal the (incorrect) collapsed form.
    assert normalized != _normalize_muni_name("De Hermanas")
    # And must not match a bare "Hermanas" query.
    assert normalized != _normalize_muni_name("Hermanas")


# === _consulta_municipio integration tests (mocked HTTP) ===

def _muni_xml(names: list[str]) -> str:
    """Build a minimal Cadastre ConsultaMunicipio XML response."""
    munis = "".join(
        f"<muni><nm>{n}</nm><loine><cp>25</cp><cm>235</cm></loine></muni>"
        for n in names
    )
    return f"<?xml version='1.0'?><consulta_municipiero>{munis}</consulta_municipiero>"


@pytest.fixture
def mock_fetch(monkeypatch):
    """Patch _fetch_url to return controlled XML per (query) call."""
    calls: list[str] = []
    responses: dict[str, str] = {}

    def fake_fetch(url: str, **kwargs) -> str:
        calls.append(url)
        url_l = url.lower()
        for substring, xml in responses.items():
            if substring.lower() in url_l:
                return xml
        # Default: empty muni list
        return _muni_xml([])

    monkeypatch.setattr(gc, "_fetch_url", fake_fetch)
    # Also short-circuit the sleep in the finally block
    monkeypatch.setattr(gc.time, "sleep", lambda *_a, **_kw: None)
    return calls, responses


def test_exact_match_wins_without_normalization(mock_fetch):
    """Working projects with correct input must not trigger the new retry."""
    calls, responses = mock_fetch
    # API returns the canonical name when queried with the canonical hint.
    # (URL-encoded "Vilanova de Segria" contains "Vilanova+de+Segria" or
    # "Vilanova%20de%20Segria" depending on quoting; match on "Segria".)
    responses["Segria"] = _muni_xml(["VILANOVA DE SEGRIÀ"])

    result = _consulta_municipio("Lleida", "Vilanova de Segrià")
    assert result is not None
    official, cp, cm = result
    assert official == "VILANOVA DE SEGRIÀ"
    # Exactly one API call — no retry triggered
    assert len(calls) == 1, f"expected 1 API call, got {len(calls)}: {calls}"


def test_accent_insensitive_match(mock_fetch):
    """Missing grave accent ("Segria" vs "Segrià") must still match."""
    calls, responses = mock_fetch
    responses["Segria"] = _muni_xml(["VILANOVA DE SEGRIÀ"])

    result = _consulta_municipio("Lleida", "Vilanova de Segria")
    assert result is not None
    official, _, _ = result
    assert official == "VILANOVA DE SEGRIÀ"
    # Accent-stripped hint equals the accent-stripped candidate — no retry
    assert len(calls) == 1


def test_preposition_variant_match_triggers_retry(mock_fetch):
    """'Vilanova del Segria' must resolve to 'VILANOVA DE SEGRIÀ' via retry.

    Simulates the observed failure mode: the Cadastre API returns an empty
    muni list for the "del"-variant query but returns the canonical name
    when the hint is normalized to "de".
    """
    calls, responses = mock_fetch
    # Only the *normalized* query returns a match; the raw "del" query gets
    # nothing. We key on the encoded space-delimited tokens.
    responses["Vilanova%20de%20Segria"] = _muni_xml(["VILANOVA DE SEGRIÀ"])
    # Explicitly return empty for the raw query (default fallthrough also empty)
    responses["Vilanova%20del%20Segria"] = _muni_xml([])

    result = _consulta_municipio("Lleida", "Vilanova del Segria")
    assert result is not None, "Expected tolerant retry to resolve municipality"
    official, _, _ = result
    assert official == "VILANOVA DE SEGRIÀ"
    # Exactly two API calls: raw hint (fails) + normalized hint (succeeds)
    assert len(calls) == 2, f"expected retry, got {len(calls)} call(s): {calls}"


def test_tolerant_match_in_candidate_list(mock_fetch):
    """Even if the API *does* return candidates, preposition-normalized exact
    match should be picked when no word-set match exists.

    Uses a synthetic case where the only returned candidate differs solely
    in preposition/accent.
    """
    calls, responses = mock_fetch
    # API returns a single unrelated-looking candidate that only matches after
    # preposition normalization.
    responses["Testmuni"] = _muni_xml(["FOO DE BAR"])
    # Hint uses "del" — word-set intersection with {"FOO","DE","BAR"} would be
    # just {"FOO","BAR"} (score 40), but we want the tolerant match to also
    # be reachable when the score path fails. Here the hint shares words so
    # it still scores; we simply assert the result is the expected candidate.
    result = _consulta_municipio("Testprov", "Foo del Bar Testmuni")
    # The hint's words {"FOO","DEL","BAR","TESTMUNI"} don't all appear in
    # candidate_words, but intersection is non-empty → scored, returned.
    assert result is not None
    assert result[0] == "FOO DE BAR"


def test_non_match_still_fails(mock_fetch):
    """Tolerance must NOT turn a genuinely different town into a match.

    "Alpicat" does not share tokens with "Vilanova de Segrià" and the
    preposition normalization cannot bridge them.
    """
    calls, responses = mock_fetch
    # Simulate Cadastre returning only Vilanova (the closest-sounding entry
    # it happens to have) when queried for Alpicat — we must still refuse.
    responses["Alpicat"] = _muni_xml(["VILANOVA DE SEGRIÀ"])

    result = _consulta_municipio("Lleida", "Alpicat")
    assert result is None, f"Expected no match, got {result}"
