"""Unit tests for the shared G3 internal-address filter."""

from __future__ import annotations

import pytest

from automation.internal_addresses import (
    G3_ADDRESS_PATTERNS,
    NON_CLIENT_NIFS,
    is_g3_internal_address,
    is_non_client_nif,
)


class TestIsG3InternalAddress:
    def test_canonical_office_address_matches(self):
        assert is_g3_internal_address("C/ Vallbona, 22") is True

    def test_all_caps_matches(self):
        assert is_g3_internal_address("CARRER VALLBONA, 22") is True

    def test_loose_muni_match_is_true(self):
        """is_g3_internal_address is deliberately loose on municipality context.

        "Vallbona d'Anoia 22" is a legitimate non-G3 address in principle, but
        this filter errs on the side of over-filtering for safety: polluting a
        project's street_address with G3's office address is far more harmful
        than dropping a rare legitimate match.
        """
        assert is_g3_internal_address("Vallbona d'Anoia 22") is True

    def test_bare_street_plus_number(self):
        assert is_g3_internal_address("Vallbona 22 Rubi") is True

    def test_different_number_does_not_match(self):
        assert is_g3_internal_address("Vallbona 23") is False

    def test_different_street_does_not_match(self):
        assert is_g3_internal_address("Calle Mayor 22") is False

    def test_empty_string(self):
        assert is_g3_internal_address("") is False

    def test_non_string_returns_false(self):
        assert is_g3_internal_address(None) is False  # type: ignore[arg-type]
        assert is_g3_internal_address(22) is False  # type: ignore[arg-type]

    def test_patterns_constant_exported(self):
        assert isinstance(G3_ADDRESS_PATTERNS, list)
        assert len(G3_ADDRESS_PATTERNS) >= 1
        assert all(
            isinstance(p, tuple) and len(p) == 2 for p in G3_ADDRESS_PATTERNS
        )


class TestIsNonClientNif:
    def test_g3_own_cif_matches(self):
        # G3 Desenvolupament Territorial SL — the budget issuer.
        assert is_non_client_nif("B25461443") is True

    def test_lab_cif_matches(self):
        # Drilling/lab subcontractor — appears on every GTL report.
        assert is_non_client_nif("B64803075") is True

    def test_labelled_provider_cif_matches(self):
        assert is_non_client_nif("CIF: B25461443") is True
        assert is_non_client_nif("N.I.F./C.I.F.: B25461443") is True

    def test_real_client_nif_kept(self):
        # A genuine client NIF (varies per project) must never be filtered.
        assert is_non_client_nif("38112117J") is False        # Marc Vidal
        assert is_non_client_nif("47697437Z") is False        # Linyola
        assert is_non_client_nif("78058457E") is False        # Bell-lloc
        assert is_non_client_nif("B19935212") is False        # Grup Alma (Castellar)

    def test_labelled_client_nif_kept(self):
        # The label prefix from a vision preview must not cause a false match.
        assert is_non_client_nif("N.I.F./C.I.F.: 38112117J") is False

    def test_empty_string(self):
        assert is_non_client_nif("") is False

    def test_non_string_returns_false(self):
        assert is_non_client_nif(None) is False  # type: ignore[arg-type]
        assert is_non_client_nif(25461443) is False  # type: ignore[arg-type]

    def test_blocklist_constant_exported(self):
        assert isinstance(NON_CLIENT_NIFS, set)
        assert "B25461443" in NON_CLIENT_NIFS
        assert "B64803075" in NON_CLIENT_NIFS


class TestLegacyPrivateAlias:
    """auto_extractor re-exports the helper under private names for back-compat."""

    def test_auto_extractor_private_alias(self):
        from automation.auto_extractor import (
            _G3_ADDRESS_PATTERNS,
            _is_g3_internal_address,
        )
        assert _is_g3_internal_address("C/ Vallbona, 22") is True
        assert _is_g3_internal_address("Calle Mayor 22") is False
        assert _G3_ADDRESS_PATTERNS is G3_ADDRESS_PATTERNS or (
            _G3_ADDRESS_PATTERNS == G3_ADDRESS_PATTERNS
        )
