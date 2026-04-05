"""
Tests for the schema loading infrastructure (Phase 1).

Validates that YAML schemas load correctly and produce backward-compatible
results equivalent to the hardcoded LABEL_TO_VARIABLE and SOURCE_PRIORITY.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.schemas.loader import ConceptRegistry, FormatRegistry
from automation.fileminer.label_map import LABEL_TO_VARIABLE, SOURCE_PRIORITY


# ============================================================
# ConceptRegistry tests
# ============================================================

class TestConceptRegistry:

    @pytest.fixture(autouse=True)
    def fresh_registry(self):
        """Create a fresh registry for each test (not the singleton)."""
        self.cr = ConceptRegistry()

    def test_loads_without_error(self):
        self.cr._ensure_loaded()
        assert len(self.cr.all_concept_ids()) > 0

    def test_expected_concept_count(self):
        """Should have ~50+ concepts."""
        ids = self.cr.all_concept_ids()
        assert len(ids) >= 40, f"Only {len(ids)} concepts loaded"

    def test_core_concepts_exist(self):
        core = [
            "client_name", "street_address", "municipality",
            "architect_name", "building_type", "num_floors",
            "expedient", "field_date", "utm_x", "utm_y",
        ]
        ids = self.cr.all_concept_ids()
        for c in core:
            assert c in ids, f"Core concept '{c}' missing"

    def test_source_priority_matches_hardcoded(self):
        """For every source in SOURCE_PRIORITY, get_default_priority
        should return the same value."""
        for source_type, expected_priority in SOURCE_PRIORITY.items():
            actual = self.cr.get_default_priority(source_type)
            assert actual == expected_priority, (
                f"Source '{source_type}': expected {expected_priority}, got {actual}"
            )

    def test_user_always_priority_10(self):
        """'user' source should be priority 10 for all concepts that define it."""
        self.cr._ensure_loaded()
        for cid, concept in self.cr._concepts.items():
            if "user" in concept.source_priority:
                assert concept.source_priority["user"] == 10, (
                    f"Concept '{cid}' has user priority {concept.source_priority['user']}, expected 10"
                )

    def test_unknown_source_returns_50(self):
        assert self.cr.get_priority("street_address", "unknown_source") == 50

    def test_unknown_concept_returns_50(self):
        assert self.cr.get_priority("nonexistent_concept", "user") == 50

    def test_concept_has_required_fields(self):
        self.cr._ensure_loaded()
        for cid, concept in self.cr._concepts.items():
            assert concept.type, f"Concept '{cid}' missing type"
            assert concept.group, f"Concept '{cid}' missing group"
            assert concept.description_ca, f"Concept '{cid}' missing description_ca"


# ============================================================
# FormatRegistry tests
# ============================================================

class TestFormatRegistry:

    @pytest.fixture(autouse=True)
    def fresh_registry(self):
        self.fr = FormatRegistry()

    def test_loads_without_error(self):
        self.fr._ensure_loaded()
        assert len(self.fr._formats) > 0

    def test_expected_format_count(self):
        """Should have 8 seeded formats."""
        self.fr._ensure_loaded()
        assert len(self.fr._formats) >= 8

    def test_build_label_map_exact_match(self):
        """build_label_map() must produce the exact same dict as LABEL_TO_VARIABLE."""
        built = self.fr.build_label_map()
        # Every label in hardcoded must be in built
        for label, variable in LABEL_TO_VARIABLE.items():
            assert label in built, f"Label '{label}' missing from build_label_map()"
            assert built[label] == variable, (
                f"Label '{label}': expected '{variable}', got '{built[label]}'"
            )

    def test_label_to_concept_finds_known_labels(self):
        assert self.fr.label_to_concept("ADREÇA OBRA") == "street_address"
        assert self.fr.label_to_concept("CLIENT") == "client_name"
        assert self.fr.label_to_concept("ARQUITECTE") == "architect_name"

    def test_label_to_concept_case_insensitive(self):
        assert self.fr.label_to_concept("adreça obra") == "street_address"

    def test_label_to_concept_unknown_returns_none(self):
        assert self.fr.label_to_concept("XXXXXX") is None

    def test_formats_for_role(self):
        plan_formats = self.fr.formats_for_role("architect_plan")
        assert len(plan_formats) >= 1
        assert any(f.source_type == "planol_vision" for f in plan_formats)

    def test_concept_ids_in_formats_exist_in_concepts(self):
        """Every concept_id referenced in format schemas must exist in concept registry."""
        cr = ConceptRegistry()
        concept_ids = cr.all_concept_ids()
        self.fr._ensure_loaded()
        for fmt in self.fr._formats.values():
            for mapping in fmt.label_mappings:
                assert mapping.concept_id in concept_ids, (
                    f"Format '{fmt.format_id}' references concept '{mapping.concept_id}' "
                    f"which doesn't exist in concept registry"
                )
