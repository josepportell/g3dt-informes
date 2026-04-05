"""
Format Learning Engine.

Detects new document formats and lets Eva confirm/correct mappings.
When a file's format is unfamiliar (low extraction coverage), the engine
proposes mappings for Eva to review in the wizard.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Expected fields per document role
EXPECTED_FIELDS: dict[str, list[str]] = {
    "architect_plan": [
        "architect_name", "architect_company", "client_name",
        "street_address", "municipality", "building_type",
        "num_floors", "superficie_parcela", "superficie_construida",
        "building_height_m",
    ],
    "dpsh_excel": [
        "client_name", "street_address", "municipality",
        "architect_name", "field_date", "expedient",
    ],
    "pressupost_pdf": [
        "client_name", "street_address", "municipality",
        "architect_name", "building_type",
    ],
}

# If less than this fraction of expected fields are mapped, trigger learning
LEARNING_THRESHOLD = 0.6


class ProposedMapping(BaseModel):
    """A label->concept mapping proposed by the system for Eva to confirm."""

    label: str
    value: str
    proposed_concept_id: str | None = None
    confidence: float = 0.5
    source_file: str = ""
    confirmed: bool = False
    corrected_concept_id: str | None = None


class FormatDetectionResult(BaseModel):
    """Result of checking whether a file matches a known format."""

    file_path: str
    role: str
    is_new: bool = False
    format_id: str | None = None
    extraction_coverage: float = 1.0
    expected_fields: list[str] = Field(default_factory=list)
    extracted_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    proposed_mappings: list[ProposedMapping] = Field(default_factory=list)
    raw_extractions: list[dict[str, Any]] = Field(default_factory=list)


class FormatLearner:
    """Detects new document formats and proposes mappings for Eva to confirm."""

    def detect_format(
        self,
        file_path: Path,
        role: str,
        signals: list,  # list[Signal]
        *,
        file_mapping: dict | None = None,
    ) -> FormatDetectionResult:
        """Check if file matches a known format or is new.

        Args:
            file_path: Absolute path to file
            role: SmartScan role (architect_plan, dpsh_excel, etc.)
            signals: Signals extracted from this file
            file_mapping: SmartScan file_mapping dict

        Returns:
            FormatDetectionResult with is_new=True if format unrecognized
        """
        rel_path = file_path.name

        expected = EXPECTED_FIELDS.get(role, [])
        if not expected:
            return FormatDetectionResult(file_path=rel_path, role=role)

        # What concept_ids did we actually extract from this file?
        extracted = set()
        for s in signals:
            if s.source_file == rel_path or str(file_path).endswith(s.source_file):
                if s.concept_id:
                    extracted.add(s.concept_id)
                elif s.maps_to:
                    extracted.add(s.maps_to)

        extracted_list = sorted(extracted & set(expected))
        missing_list = sorted(set(expected) - extracted)
        coverage = len(extracted_list) / len(expected) if expected else 1.0

        is_new = coverage < LEARNING_THRESHOLD

        # Build raw_extractions for UI (signals from this file)
        raw = []
        for s in signals:
            if s.source_file == rel_path or str(file_path).endswith(s.source_file):
                raw.append({
                    "label": s.label,
                    "value": str(s.value) if s.value else "",
                    "maps_to": s.maps_to,
                    "concept_id": s.concept_id,
                    "confidence": s.confidence,
                })

        # Build proposed mappings for unmapped signals that might fill gaps
        proposed = []
        if is_new:
            for r in raw:
                if r["concept_id"] is None and r["maps_to"] is None:
                    proposed.append(ProposedMapping(
                        label=r["label"],
                        value=r["value"],
                        proposed_concept_id=None,
                        confidence=r["confidence"],
                        source_file=rel_path,
                    ))

        return FormatDetectionResult(
            file_path=rel_path,
            role=role,
            is_new=is_new,
            extraction_coverage=round(coverage, 2),
            expected_fields=sorted(expected),
            extracted_fields=extracted_list,
            missing_fields=missing_list,
            proposed_mappings=proposed,
            raw_extractions=raw,
        )

    def confirm_mappings(
        self,
        role: str,
        source_file: str,
        confirmed_mappings: list[dict],
        *,
        format_name: str | None = None,
    ) -> Path | None:
        """Save confirmed mappings as a new format schema YAML.

        Args:
            role: SmartScan role
            source_file: Original file that triggered learning
            confirmed_mappings: List of {label, concept_id} pairs confirmed by Eva
            format_name: Optional human-readable name for the format

        Returns:
            Path to saved YAML, or None if nothing to save
        """
        if not confirmed_mappings:
            return None

        from automation.schemas.format_writer import write_learned_format
        return write_learned_format(
            role=role,
            source_file=source_file,
            confirmed_mappings=confirmed_mappings,
            format_name=format_name,
        )
