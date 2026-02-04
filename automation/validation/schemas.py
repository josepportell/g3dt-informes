#!/usr/bin/env python3
"""
G3DT Validation Schemas

Pydantic models for field document extraction and validation.
These schemas define the structure for:
- Extracted data from handwritten PDFs
- Confidence scores for uncertain values
- Approval workflow metadata

Usage:
    from validation.schemas import DPSHValidationFile, SondeigValidationFile

    # Load extracted data
    validation = DPSHValidationFile.model_validate_json(path.read_text())

    # Check status
    if validation.status == ValidationStatus.APPROVED:
        # Use data in report
        ...

Author: Eficients.cat
Date: 2026-02-04
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ValidationStatus(str, Enum):
    """Status of a validation file in the review workflow."""
    PENDING = "pending_review"      # Extracted, awaiting human review
    IN_REVIEW = "in_review"         # Being reviewed
    APPROVED = "approved"           # Reviewed and approved
    REJECTED = "rejected"           # Rejected, needs re-extraction


class ExtractionMethod(str, Enum):
    """How the data was extracted from the source document."""
    CLAUDE_VISION = "claude_vision"  # Claude's native vision/PDF reading
    MANUAL = "manual"                # Manually entered
    EXCEL_IMPORT = "excel_import"    # Imported from digitized Excel


# ============================================================================
# DPSH (PENETROS.pdf) Validation Models
# ============================================================================

class DPSHReadingExtracted(BaseModel):
    """
    Single depth reading extracted from a DPSH test sheet.

    Confidence scoring:
    - 1.0: Clear, unambiguous value
    - 0.7-0.9: Readable but some uncertainty
    - 0.5-0.7: Partially legible, interpretation required
    - <0.5: Uncertain, marked for review
    - 0.0: Illegible, requires human entry
    """
    depth_m: float = Field(..., description="Depth in meters (positive value)")
    n20: int | str = Field(
        ...,
        description="Blow count per 20cm. Use '??' for illegible values"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence (0.0-1.0)"
    )
    note: str | None = Field(
        default=None,
        description="Note about extraction issues (e.g., 'illegible', 'smudged')"
    )
    torque: float | None = Field(
        default=None,
        description="PAR measurement if recorded"
    )
    water_indicator: bool = Field(
        default=False,
        description="Water level indicator present"
    )
    excel_value: int | None = Field(
        default=None,
        description="Corresponding value from Excel for comparison"
    )
    has_discrepancy: bool = Field(
        default=False,
        description="Whether PDF and Excel values differ"
    )

    @field_validator('n20')
    @classmethod
    def validate_n20(cls, v: int | str) -> int | str:
        """Allow integer or '??' for illegible values."""
        if isinstance(v, str):
            if v == '??' or v.startswith('?'):
                return v
            try:
                return int(v)
            except ValueError:
                return '??'
        return v


class DPSHTestExtracted(BaseModel):
    """
    Complete extracted data for one DPSH test point (e.g., P-1).
    """
    test_id: str = Field(..., description="Test identifier (e.g., 'P-1')")
    readings: list[DPSHReadingExtracted] = Field(default_factory=list)
    refusal_depth_m: float | None = Field(
        default=None,
        description="Depth at which refusal occurred"
    )
    refusal_detected: bool = Field(
        default=False,
        description="Whether test ended in refusal (R marker)"
    )
    water_detected: bool = Field(
        default=False,
        description="Whether water level was encountered"
    )
    water_depth_m: float | None = Field(
        default=None,
        description="Depth at which water was first detected"
    )
    correction_factor: float = Field(
        default=0.83,
        description="Energy correction factor"
    )
    extraction_notes: str | None = Field(
        default=None,
        description="General notes about this test's extraction"
    )

    @property
    def has_uncertain_values(self) -> bool:
        """Check if any readings have low confidence or unknown values."""
        return any(
            r.confidence < 0.9 or r.n20 == '??' or r.note
            for r in self.readings
        )

    @property
    def uncertain_count(self) -> int:
        """Count of values needing review."""
        return sum(
            1 for r in self.readings
            if r.confidence < 0.9 or r.n20 == '??'
        )


class DPSHValidationFile(BaseModel):
    """
    Complete validation file for DPSH data extracted from PENETROS.pdf.

    This file is the intermediate step between raw PDF extraction
    and approved data for report generation.
    """
    # Metadata
    source_file: str = Field(..., description="Original PDF filename")
    extraction_date: datetime = Field(default_factory=datetime.now)
    extraction_method: ExtractionMethod = ExtractionMethod.CLAUDE_VISION
    overall_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall extraction confidence"
    )
    status: ValidationStatus = ValidationStatus.PENDING

    # Extracted data
    dpsh_tests: list[DPSHTestExtracted] = Field(default_factory=list)

    # Review workflow
    reviewer_notes: str = Field(
        default="",
        description="Notes from human reviewer"
    )
    approved_by: str = Field(
        default="",
        description="Name of person who approved"
    )
    approval_date: datetime | None = None

    # Cross-reference
    excel_comparison: dict[str, Any] = Field(
        default_factory=dict,
        description="Comparison with Excel data if available"
    )

    @property
    def needs_review(self) -> bool:
        """Check if any tests have uncertain values needing review."""
        return any(t.has_uncertain_values for t in self.dpsh_tests)

    @property
    def total_uncertain_values(self) -> int:
        """Total count of values needing human verification."""
        return sum(t.uncertain_count for t in self.dpsh_tests)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=indent)

    def save(self, path: Path) -> None:
        """Save to file."""
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> "DPSHValidationFile":
        """Load from file."""
        return cls.model_validate_json(path.read_text())


# ============================================================================
# Sondeig (SONDEIG.pdf) Validation Models
# ============================================================================

class SondeigLayerExtracted(BaseModel):
    """
    Single soil layer description from a Sondeig drilling log.
    """
    depth_from_m: float = Field(..., description="Top of layer (meters)")
    depth_to_m: float | None = Field(
        default=None,
        description="Bottom of layer (None if continues)"
    )
    description: str = Field(
        ...,
        description="Soil description (e.g., 'Argila marró compacta')"
    )
    uscs_classification: str | None = Field(
        default=None,
        description="USCS soil classification (e.g., 'CL', 'SP-SM')"
    )
    color: str | None = Field(
        default=None,
        description="Soil color description"
    )
    moisture: str | None = Field(
        default=None,
        description="Moisture condition (sec, humit, saturat)"
    )
    consistency: str | None = Field(
        default=None,
        description="For cohesive: tova, ferma, dura"
    )
    density: str | None = Field(
        default=None,
        description="For granular: fluixa, mitja, densa"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence"
    )
    note: str | None = None


class SondeigTestExtracted(BaseModel):
    """
    Complete extracted data for one Sondeig (drilling) test point.
    """
    test_id: str = Field(..., description="Test identifier (e.g., 'S-1')")
    total_depth_m: float = Field(..., description="Total drilling depth")
    layers: list[SondeigLayerExtracted] = Field(default_factory=list)
    water_level_m: float | None = Field(
        default=None,
        description="Water table depth if encountered"
    )
    rock_detected: bool = Field(
        default=False,
        description="Whether bedrock was reached"
    )
    rock_depth_m: float | None = Field(
        default=None,
        description="Depth at which rock was encountered"
    )
    extraction_notes: str | None = None

    @property
    def has_uncertain_values(self) -> bool:
        """Check if any layers have low confidence."""
        return any(layer.confidence < 0.9 for layer in self.layers)


class SondeigValidationFile(BaseModel):
    """
    Complete validation file for Sondeig data extracted from SONDEIG.pdf.
    """
    # Metadata
    source_file: str = Field(..., description="Original PDF filename")
    extraction_date: datetime = Field(default_factory=datetime.now)
    extraction_method: ExtractionMethod = ExtractionMethod.CLAUDE_VISION
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: ValidationStatus = ValidationStatus.PENDING

    # Extracted data
    sondeig_tests: list[SondeigTestExtracted] = Field(default_factory=list)

    # Review workflow
    reviewer_notes: str = ""
    approved_by: str = ""
    approval_date: datetime | None = None

    @property
    def needs_review(self) -> bool:
        return any(t.has_uncertain_values for t in self.sondeig_tests)

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> "SondeigValidationFile":
        return cls.model_validate_json(path.read_text())


# ============================================================================
# Site Observations Validation (Future)
# ============================================================================

class SiteObservationsExtracted(BaseModel):
    """
    Placeholder for site observations extraction.
    Will include: field photos annotations, site sketches, etc.
    """
    source_files: list[str] = Field(default_factory=list)
    extraction_date: datetime = Field(default_factory=datetime.now)
    status: ValidationStatus = ValidationStatus.PENDING

    # Observations
    surface_conditions: str = ""
    vegetation: str = ""
    drainage: str = ""
    access_conditions: str = ""
    nearby_structures: list[str] = Field(default_factory=list)

    # Notes
    extraction_notes: str = ""
    reviewer_notes: str = ""


# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == '__main__':
    import json

    print("=== G3DT Validation Schemas ===\n")

    # Create example DPSH validation file
    example = DPSHValidationFile(
        source_file="PENETROS.pdf",
        dpsh_tests=[
            DPSHTestExtracted(
                test_id="P-1",
                readings=[
                    DPSHReadingExtracted(depth_m=0.20, n20=15, confidence=0.95),
                    DPSHReadingExtracted(depth_m=0.40, n20=18, confidence=0.90),
                    DPSHReadingExtracted(depth_m=0.60, n20='??', confidence=0.0,
                                        note="illegible - ink smudged"),
                    DPSHReadingExtracted(depth_m=0.80, n20=25, confidence=1.0),
                ],
                refusal_detected=True,
                refusal_depth_m=1.40,
            ),
        ],
    )

    print("Example DPSHValidationFile:")
    print(f"  Status: {example.status.value}")
    print(f"  Needs review: {example.needs_review}")
    print(f"  Total uncertain values: {example.total_uncertain_values}")
    print(f"\nJSON output:")
    print(example.to_json())
