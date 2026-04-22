"""Unit tests for the shared G3 internal-address filter."""

from __future__ import annotations

import pytest

from automation.internal_addresses import G3_ADDRESS_PATTERNS, is_g3_internal_address


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
