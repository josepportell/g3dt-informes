from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConceptDefinition(BaseModel):
    """A single report variable (concept), independent of any document format."""

    concept_id: str
    type: str  # text, numeric, date, boolean, list, integer, url, coords
    group: str  # client, architect, location, building, project, field_work, parcel, geotechnical, lab, geology, coordinates
    required: bool = False
    description_ca: str = ""
    source_priority: dict[str, int] = {}  # source_type -> priority (lower wins)
    wizard_field: str | None = None  # if wizard field name differs from concept_id
    default: Any = None


class LabelMapping(BaseModel):
    """Maps one or more uppercase labels to a concept_id."""

    labels: list[str]  # uppercase labels that map to this concept
    concept_id: str
    confidence: float = 0.90


class FormatSchema(BaseModel):
    """Describes a specific document format and its label-to-concept mappings."""

    format_id: str
    name: str
    description: str = ""
    document_roles: list[str] = []  # SmartScan roles this format applies to
    source_type: str = ""  # SOURCE_PRIORITY key
    created_by: str = "system"  # "system" or "eva"
    label_mappings: list[LabelMapping] = []
