"""
Tests for the format learning engine.

Validates format detection, coverage thresholds, mapping confirmation,
and serialization of FormatDetectionResult.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.format_learner import (
    EXPECTED_FIELDS,
    LEARNING_THRESHOLD,
    FormatDetectionResult,
    FormatLearner,
    ProposedMapping,
)
from automation.fileminer.models import Signal, SignalType, MiningResult


# ============================================================
# Helpers
# ============================================================

def _make_signal(
    label: str,
    value: str = "test",
    concept_id: str | None = None,
    maps_to: str | None = None,
    source_file: str = "A.01.pdf",
    confidence: float = 0.8,
) -> Signal:
    return Signal(
        type=SignalType.TEXT,
        label=label,
        value=value,
        source_file=source_file,
        concept_id=concept_id,
        maps_to=maps_to,
        confidence=confidence,
    )


# ============================================================
# 1. Detection triggers when coverage < 60%
# ============================================================

class TestDetectionTriggersLowCoverage:

    def test_new_format_detected_below_threshold(self):
        """With only 2/10 expected fields, coverage=0.2 < 0.6 => is_new=True."""
        learner = FormatLearner()
        signals = [
            _make_signal("ARQUITECTE", concept_id="architect_name", source_file="A.01.pdf"),
            _make_signal("CLIENT", concept_id="client_name", source_file="A.01.pdf"),
        ]
        result = learner.detect_format(
            file_path=Path("/project/A.01.pdf"),
            role="architect_plan",
            signals=signals,
        )
        assert result.is_new is True
        assert result.extraction_coverage < LEARNING_THRESHOLD
        assert "architect_name" in result.extracted_fields
        assert "client_name" in result.extracted_fields
        assert len(result.missing_fields) == 8  # 10 expected - 2 found

    def test_zero_signals_triggers_detection(self):
        """No signals at all => coverage=0 => is_new=True."""
        learner = FormatLearner()
        result = learner.detect_format(
            file_path=Path("/project/PLAN_WEIRD.pdf"),
            role="architect_plan",
            signals=[],
        )
        assert result.is_new is True
        assert result.extraction_coverage == 0.0
        assert len(result.missing_fields) == len(EXPECTED_FIELDS["architect_plan"])

    def test_unmapped_signals_become_proposed_mappings(self):
        """Unmapped signals (no concept_id, no maps_to) become proposals."""
        learner = FormatLearner()
        signals = [
            _make_signal("UNKNOWN_LABEL", source_file="A.01.pdf"),
            _make_signal("OTRO_CAMPO", source_file="A.01.pdf"),
        ]
        result = learner.detect_format(
            file_path=Path("/project/A.01.pdf"),
            role="architect_plan",
            signals=signals,
        )
        assert result.is_new is True
        assert len(result.proposed_mappings) == 2
        labels = {pm.label for pm in result.proposed_mappings}
        assert "UNKNOWN_LABEL" in labels
        assert "OTRO_CAMPO" in labels


# ============================================================
# 2. Detection does NOT trigger when coverage >= 60%
# ============================================================

class TestDetectionNoTriggerHighCoverage:

    def test_known_format_above_threshold(self):
        """With 7/10 expected fields, coverage=0.7 >= 0.6 => is_new=False."""
        learner = FormatLearner()
        expected = EXPECTED_FIELDS["architect_plan"]
        signals = [
            _make_signal(f.upper(), concept_id=f, source_file="A.01.pdf")
            for f in expected[:7]
        ]
        result = learner.detect_format(
            file_path=Path("/project/A.01.pdf"),
            role="architect_plan",
            signals=signals,
        )
        assert result.is_new is False
        assert result.extraction_coverage >= LEARNING_THRESHOLD
        assert len(result.missing_fields) == 3

    def test_full_coverage(self):
        """All expected fields extracted => is_new=False, coverage=1.0."""
        learner = FormatLearner()
        expected = EXPECTED_FIELDS["architect_plan"]
        signals = [
            _make_signal(f.upper(), concept_id=f, source_file="A.01.pdf")
            for f in expected
        ]
        result = learner.detect_format(
            file_path=Path("/project/A.01.pdf"),
            role="architect_plan",
            signals=signals,
        )
        assert result.is_new is False
        assert result.extraction_coverage == 1.0
        assert result.missing_fields == []

    def test_exact_threshold_boundary(self):
        """Exactly at threshold (6/10 = 0.6) => is_new=False (< is strict)."""
        learner = FormatLearner()
        expected = EXPECTED_FIELDS["architect_plan"]
        signals = [
            _make_signal(f.upper(), concept_id=f, source_file="A.01.pdf")
            for f in expected[:6]
        ]
        result = learner.detect_format(
            file_path=Path("/project/A.01.pdf"),
            role="architect_plan",
            signals=signals,
        )
        assert result.is_new is False
        assert result.extraction_coverage == 0.6

    def test_unknown_role_skips_detection(self):
        """Role with no expected fields => is_new=False, coverage=1.0."""
        learner = FormatLearner()
        result = learner.detect_format(
            file_path=Path("/project/random.pdf"),
            role="unknown_role",
            signals=[],
        )
        assert result.is_new is False
        assert result.extraction_coverage == 1.0

    def test_no_proposed_mappings_when_known(self):
        """When format is known, proposed_mappings should be empty."""
        learner = FormatLearner()
        expected = EXPECTED_FIELDS["dpsh_excel"]
        signals = [
            _make_signal(f.upper(), concept_id=f, source_file="DPSH.xls")
            for f in expected
        ]
        result = learner.detect_format(
            file_path=Path("/project/DPSH.xls"),
            role="dpsh_excel",
            signals=signals,
        )
        assert result.is_new is False
        assert result.proposed_mappings == []


# ============================================================
# 3. confirm_mappings generates valid YAML
# ============================================================

class TestConfirmMappings:

    def test_writes_valid_yaml(self, tmp_path, monkeypatch):
        """confirm_mappings should produce a loadable YAML file."""
        # Redirect the project root so YAML goes into tmp_path
        monkeypatch.setattr(
            "automation.schemas.format_writer._find_project_root",
            lambda: tmp_path,
        )
        learner = FormatLearner()
        mappings = [
            {"label": "ARQUITECTE TÈCNIC", "concept_id": "architect_name"},
            {"label": "PROMOTOR", "concept_id": "client_name"},
            {"label": "ADREÇA", "concept_id": "street_address"},
        ]
        result_path = learner.confirm_mappings(
            role="architect_plan",
            source_file="WEIRD_PLAN.pdf",
            confirmed_mappings=mappings,
        )
        assert result_path is not None
        assert result_path.exists()
        assert result_path.suffix == ".yaml"

        content = yaml.safe_load(result_path.read_text(encoding="utf-8"))
        assert content["document_roles"] == ["architect_plan"]
        assert content["created_by"] == "eva"
        assert content["source_type"] == "planol_vision"
        assert len(content["label_mappings"]) == 3

        # All concept_ids present
        cids = {lm["concept_id"] for lm in content["label_mappings"]}
        assert cids == {"architect_name", "client_name", "street_address"}

    def test_labels_uppercased_in_yaml(self, tmp_path, monkeypatch):
        """Labels in the YAML should always be uppercase."""
        monkeypatch.setattr(
            "automation.schemas.format_writer._find_project_root",
            lambda: tmp_path,
        )
        learner = FormatLearner()
        mappings = [
            {"label": "lower case label", "concept_id": "client_name"},
        ]
        result_path = learner.confirm_mappings(
            role="dpsh_excel",
            source_file="test.xls",
            confirmed_mappings=mappings,
        )
        content = yaml.safe_load(result_path.read_text(encoding="utf-8"))
        labels = content["label_mappings"][0]["labels"]
        assert labels == ["LOWER CASE LABEL"]

    def test_empty_mappings_returns_none(self):
        """No mappings => returns None, no file written."""
        learner = FormatLearner()
        result = learner.confirm_mappings(
            role="architect_plan",
            source_file="test.pdf",
            confirmed_mappings=[],
        )
        assert result is None

    def test_duplicate_labels_same_concept_deduplicated(self, tmp_path, monkeypatch):
        """Same label mapped to same concept should not duplicate."""
        monkeypatch.setattr(
            "automation.schemas.format_writer._find_project_root",
            lambda: tmp_path,
        )
        learner = FormatLearner()
        mappings = [
            {"label": "CLIENT", "concept_id": "client_name"},
            {"label": "Client", "concept_id": "client_name"},
        ]
        result_path = learner.confirm_mappings(
            role="dpsh_excel",
            source_file="test.xls",
            confirmed_mappings=mappings,
        )
        content = yaml.safe_load(result_path.read_text(encoding="utf-8"))
        assert len(content["label_mappings"]) == 1
        assert content["label_mappings"][0]["labels"] == ["CLIENT"]

    def test_yaml_saved_under_learned_role_dir(self, tmp_path, monkeypatch):
        """YAML should be saved under schemas/formats/learned/{role}/."""
        monkeypatch.setattr(
            "automation.schemas.format_writer._find_project_root",
            lambda: tmp_path,
        )
        learner = FormatLearner()
        mappings = [{"label": "TEST", "concept_id": "client_name"}]
        result_path = learner.confirm_mappings(
            role="pressupost_pdf",
            source_file="pressu.pdf",
            confirmed_mappings=mappings,
        )
        expected_dir = tmp_path / "schemas" / "formats" / "learned" / "pressupost_pdf"
        assert result_path.parent == expected_dir


# ============================================================
# 4. FormatDetectionResult serialization
# ============================================================

class TestSerialization:

    def test_format_detection_result_to_dict(self):
        """FormatDetectionResult should serialize to a clean dict."""
        result = FormatDetectionResult(
            file_path="A.01.pdf",
            role="architect_plan",
            is_new=True,
            extraction_coverage=0.3,
            expected_fields=["architect_name", "client_name"],
            extracted_fields=["architect_name"],
            missing_fields=["client_name"],
            proposed_mappings=[
                ProposedMapping(
                    label="PROMOTOR",
                    value="Test SL",
                    proposed_concept_id="client_name",
                    confidence=0.7,
                    source_file="A.01.pdf",
                ),
            ],
            raw_extractions=[{"label": "PROMOTOR", "value": "Test SL"}],
        )
        d = result.model_dump()
        assert d["file_path"] == "A.01.pdf"
        assert d["is_new"] is True
        assert d["extraction_coverage"] == 0.3
        assert len(d["proposed_mappings"]) == 1
        assert d["proposed_mappings"][0]["label"] == "PROMOTOR"

    def test_format_detection_result_json_roundtrip(self):
        """JSON serialization and deserialization should be lossless."""
        original = FormatDetectionResult(
            file_path="test.pdf",
            role="dpsh_excel",
            is_new=False,
            extraction_coverage=0.8,
            expected_fields=["a", "b", "c"],
            extracted_fields=["a", "b"],
            missing_fields=["c"],
        )
        json_str = original.model_dump_json()
        restored = FormatDetectionResult.model_validate_json(json_str)
        assert restored == original

    def test_mining_result_includes_format_detections(self):
        """MiningResult.format_detections should accept FormatDetectionResult objects."""
        detection = FormatDetectionResult(
            file_path="A.01.pdf",
            role="architect_plan",
            is_new=True,
            extraction_coverage=0.2,
        )
        mining_result = MiningResult(
            project_path="/test/project",
            format_detections=[detection],
        )
        assert len(mining_result.format_detections) == 1
        assert mining_result.format_detections[0].is_new is True

    def test_maps_to_fallback_for_coverage(self):
        """Signals with maps_to (no concept_id) should still count for coverage."""
        learner = FormatLearner()
        signals = [
            _make_signal("ADDR", maps_to="street_address", source_file="A.01.pdf"),
            _make_signal("CLIENT", maps_to="client_name", source_file="A.01.pdf"),
            _make_signal("ARCHITECT", maps_to="architect_name", source_file="A.01.pdf"),
            _make_signal("COMPANY", maps_to="architect_company", source_file="A.01.pdf"),
            _make_signal("TOWN", maps_to="municipality", source_file="A.01.pdf"),
            _make_signal("TYPE", maps_to="building_type", source_file="A.01.pdf"),
            _make_signal("FLOORS", maps_to="num_floors", source_file="A.01.pdf"),
        ]
        result = learner.detect_format(
            file_path=Path("/project/A.01.pdf"),
            role="architect_plan",
            signals=signals,
        )
        assert result.extraction_coverage == 0.7
        assert result.is_new is False
