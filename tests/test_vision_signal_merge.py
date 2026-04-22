"""Tests for ConceptScout vision-signal → FileMiner Signal conversion
and the re-competition merge path in auto_extractor."""

from __future__ import annotations

from automation.concept_scout import (
    ConceptMap,
    ConceptSource,
    concept_sources_to_signals,
)
from automation.fileminer.models import MiningResult, Signal, SignalType


class TestConceptSourcesToSignals:
    def test_architect_plan_maps_to_planol_vision(self):
        sources = {
            "street_address": [
                ConceptSource(
                    file="A.01.pdf",
                    confidence=1.0,
                    signal_preview="C. Santa Gemma, 4 Urb. La Serra",
                    extraction_method="vision_probe:architect_plan",
                    page=1,
                ),
            ],
        }
        signals = concept_sources_to_signals(sources)
        assert len(signals) == 1
        s = signals[0]
        assert s.concept_id == "street_address"
        assert s.maps_to == "street_address"
        assert s.value == "C. Santa Gemma, 4 Urb. La Serra"
        assert s.source_type == "planol_vision"
        assert s.source_file == "A.01.pdf"
        assert s.confidence == 1.0

    def test_projecte_maps_to_projecte_vision(self):
        sources = {
            "municipality": [
                ConceptSource(
                    file="MEMORIA.pdf",
                    confidence=0.8,
                    signal_preview="Vilanova",
                    extraction_method="vision_probe:projecte",
                ),
            ],
        }
        signals = concept_sources_to_signals(sources)
        assert len(signals) == 1
        assert signals[0].source_type == "projecte_vision"

    def test_unknown_doc_type_falls_back(self):
        sources = {
            "street_address": [
                ConceptSource(
                    file="x.pdf",
                    confidence=0.7,
                    signal_preview="Some address",
                    extraction_method="vision_probe:mystery_doc",
                ),
            ],
        }
        signals = concept_sources_to_signals(sources)
        assert len(signals) == 1
        assert signals[0].source_type == "vision_probe_other"

    def test_non_vision_sources_skipped(self):
        sources = {
            "street_address": [
                ConceptSource(
                    file="fitxa.xls",
                    confidence=0.8,
                    signal_preview="Some address",
                    extraction_method="content_excel",  # not vision_probe
                ),
            ],
        }
        signals = concept_sources_to_signals(sources)
        assert signals == []

    def test_empty_preview_skipped(self):
        sources = {
            "street_address": [
                ConceptSource(
                    file="A.01.pdf",
                    confidence=1.0,
                    signal_preview="",
                    extraction_method="vision_probe:architect_plan",
                ),
            ],
        }
        signals = concept_sources_to_signals(sources)
        assert signals == []

    def test_empty_input_no_op(self):
        assert concept_sources_to_signals({}) == []


class TestReCompetitionMerge:
    def test_vision_wins_over_excel_for_street_address(self, tmp_path):
        """Minimal integration: text signal from Excel loses to planol vision."""
        from automation.auto_extractor import (
            AutoExtractionResult,
            _merge_vision_signals_into_competition,
        )

        # Text pool: Excel-originated G3-like address (but not matching the
        # filter; we want the vision signal to win on priority, not on filter).
        text_signal = Signal(
            type=SignalType.TEXT,
            label="ADRECA OBRA",
            value="C/ Antiga 10",
            maps_to="street_address",
            concept_id="street_address",
            source_file="comanda_lab.xls",
            extraction_method="cell_adjacent",
            confidence=0.7,
            source_type="dades_camp_excel",
        )
        vision_source = ConceptSource(
            file="A.01.pdf",
            confidence=1.0,
            signal_preview="C. Santa Gemma, 4 Urb. La Serra",
            extraction_method="vision_probe:architect_plan",
            page=1,
        )
        concept_map = ConceptMap(
            concept_sources={"street_address": [vision_source]},
        )

        result = AutoExtractionResult()
        result.mining_result = MiningResult(
            project_path=str(tmp_path),
            signals=[text_signal],
        )
        result.concept_map = concept_map
        # Seed prefill as if the initial competition picked the text signal.
        result.prefills["street_address"] = "C/ Antiga 10"
        result.sources["street_address"] = "fileminer:comanda_lab.xls"

        _merge_vision_signals_into_competition(result)

        assert result.prefills["street_address"] == "C. Santa Gemma, 4 Urb. La Serra"
        assert result.sources["street_address"].startswith("vision_probe:")

    def test_empty_vision_is_no_op(self, tmp_path):
        from automation.auto_extractor import (
            AutoExtractionResult,
            _merge_vision_signals_into_competition,
        )

        text_signal = Signal(
            type=SignalType.TEXT,
            label="ADRECA OBRA",
            value="C/ Antiga 10",
            maps_to="street_address",
            concept_id="street_address",
            source_file="fitxa.xls",
            extraction_method="cell_adjacent",
            confidence=0.7,
            source_type="dades_camp_excel",
        )
        result = AutoExtractionResult()
        result.mining_result = MiningResult(
            project_path=str(tmp_path),
            signals=[text_signal],
        )
        result.concept_map = ConceptMap(concept_sources={})
        result.prefills["street_address"] = "C/ Antiga 10"
        result.sources["street_address"] = "fileminer:fitxa.xls"

        _merge_vision_signals_into_competition(result)

        assert result.prefills["street_address"] == "C/ Antiga 10"
        assert result.sources["street_address"] == "fileminer:fitxa.xls"

    def test_merge_skips_g3_vision_defensively(self, tmp_path):
        """Even if somehow a vision signal matches G3's office, the merge
        must not promote it. (Belt-and-suspenders with the competition
        pre-filter.)"""
        from automation.auto_extractor import (
            AutoExtractionResult,
            _merge_vision_signals_into_competition,
        )

        text_signal = Signal(
            type=SignalType.TEXT,
            label="ADRECA OBRA",
            value="C/ Antiga 10",
            maps_to="street_address",
            concept_id="street_address",
            source_file="fitxa.xls",
            extraction_method="cell_adjacent",
            confidence=0.7,
            source_type="dades_camp_excel",
        )
        # Hypothetical malicious vision value (e.g. if architect plan itself
        # mistakenly showed G3's return address).
        vision_source = ConceptSource(
            file="A.01.pdf",
            confidence=1.0,
            signal_preview="C/ Vallbona, 22",
            extraction_method="vision_probe:architect_plan",
        )
        result = AutoExtractionResult()
        result.mining_result = MiningResult(
            project_path=str(tmp_path),
            signals=[text_signal],
        )
        result.concept_map = ConceptMap(
            concept_sources={"street_address": [vision_source]},
        )
        result.prefills["street_address"] = "C/ Antiga 10"
        result.sources["street_address"] = "fileminer:fitxa.xls"

        _merge_vision_signals_into_competition(result)

        assert result.prefills["street_address"] == "C/ Antiga 10"
