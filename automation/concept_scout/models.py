"""ConceptScout data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConceptSource(BaseModel):
    """A file that provides evidence for a specific concept."""

    file: str                    # relative path within project
    confidence: float            # 0.0-1.0
    signal_preview: str = ""     # e.g. "JORDI BOSCH NOVELL"
    extraction_method: str = ""  # e.g. "planol_vision", "content_pdf"


class FileEntry(BaseModel):
    """Inventory entry for a single project file."""

    path: str
    type: str                    # "pdf_vector", "pdf_scanned", "excel", "image", "text", "email", "docx", "other"
    size_kb: int = 0
    text_extractable: bool = True
    concepts_detected: list[str] = Field(default_factory=list)
    concept_confidence: dict[str, float] = Field(default_factory=dict)
    notes: str = ""


class ConceptMap(BaseModel):
    """Full concept-to-file mapping for a project."""

    metadata: dict = Field(default_factory=dict)    # project, scanned_at, totals
    file_inventory: list[FileEntry] = Field(default_factory=list)
    concept_sources: dict[str, list[ConceptSource]] = Field(default_factory=dict)
    unresolved: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
