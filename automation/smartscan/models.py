"""
SmartScan data models.

Pydantic models for file classification results, scan outcomes,
and compatibility bridge to the existing FileMapping structure.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ClassificationTier(str, Enum):
    FILENAME = "filename"        # Tier 1: regex match on filename
    FINGERPRINT = "fingerprint"  # Tier 2: structural analysis of content
    VISION = "vision"            # Tier 3: Claude vision classification
    MANUAL = "manual"            # Eva's manual override


class FileClassification(BaseModel):
    """Classification result for a single file."""

    file_path: str                            # Relative to project root
    role: str | None = None                   # Assigned role (None = unclassified)
    confidence: float = 0.0                   # 0.0-1.0
    tier: ClassificationTier = ClassificationTier.FILENAME
    alternate_roles: list[dict[str, Any]] = Field(default_factory=list)
    fingerprint_data: dict[str, Any] | None = None
    is_directory: bool = False
    is_combined: bool = False
    combined_roles: list[str] = Field(default_factory=list)
    category: str = "classified"              # classified | suggestion | informative | unknown
    summary: str = ""                         # Human-readable summary for unclassified files


class SmartScanResult(BaseModel):
    """Complete scan result for a project."""

    project_path: str
    classifications: list[FileClassification] = Field(default_factory=list)
    unclassified: list[FileClassification] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    scan_duration_ms: int = 0

    @property
    def role_map(self) -> dict[str, FileClassification]:
        """Map role -> best classification (highest confidence)."""
        result: dict[str, FileClassification] = {}
        for c in self.classifications:
            if c.role and (c.role not in result or c.confidence > result[c.role].confidence):
                result[c.role] = c
        return result

    def to_file_mapping(self) -> dict:
        """
        Bridge to FileMapping JSON format for backward compatibility.

        Returns dict matching file_mapping.json structure so downstream
        code (auto_extractor, wizard_service, report_generator) works
        without changes.
        """
        from datetime import datetime, timezone

        confidence_str = lambda c: "high" if c >= 0.85 else ("medium" if c >= 0.6 else "low")
        tier_to_detection = {
            ClassificationTier.FILENAME: "filename_pattern",
            ClassificationTier.FINGERPRINT: "fingerprint",
            ClassificationTier.VISION: "vision_classification",
            ClassificationTier.MANUAL: "manual_override",
        }

        # Import role definitions from file_scanner for vision_type
        from automation.file_scanner import get_vision_type, ROLE_DEFINITIONS

        roles: dict[str, dict] = {}
        ignored: list[dict] = []
        unassigned: list[str] = []

        role_best = self.role_map
        classified_paths: set[str] = set()

        for role_name, clf in role_best.items():
            vt = get_vision_type(role_name)
            roles[role_name] = {
                "path": clf.file_path,
                "confidence": confidence_str(clf.confidence),
                "detection": tier_to_detection.get(clf.tier, "unknown"),
                "vision_type": vt,
            }
            if clf.is_combined:
                roles[role_name]["is_combined"] = True
            classified_paths.add(clf.file_path)

            # Handle combined roles
            for cr in clf.combined_roles:
                if cr not in roles:
                    roles[cr] = {
                        "path": clf.file_path,
                        "confidence": confidence_str(clf.confidence),
                        "detection": "combined_file",
                        "is_combined": True,
                        "vision_type": get_vision_type(cr),
                    }

        # If sondeig_annex detected, suppress vision_type on sondeig_field_sheet
        if "sondeig_annex" in roles and "sondeig_field_sheet" in roles:
            roles["sondeig_field_sheet"]["vision_type"] = None

        for clf in self.unclassified:
            if clf.category == "informative":
                ignored.append({"path": clf.file_path, "reason": clf.summary or "informative"})
            else:
                unassigned.append(clf.file_path)

        # Also add classified files without roles to appropriate lists
        for clf in self.classifications:
            if clf.file_path in classified_paths:
                continue
            if clf.role is None:
                if clf.category == "informative":
                    ignored.append({"path": clf.file_path, "reason": clf.summary or "informative"})
                else:
                    unassigned.append(clf.file_path)

        return {
            "roles": roles,
            "ignored": ignored,
            "unassigned": unassigned,
            "_metadata": {
                "scanned_at": datetime.now(timezone.utc).isoformat(),
                "confirmed_by_user": False,
                "scanner_version": "smartscan-1.0",
                "scan_duration_ms": self.scan_duration_ms,
            },
        }
