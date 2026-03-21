"""
FileMiner data models.

Pydantic models for extracted signals, mining results,
and resolved competition winners.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SignalType(str, Enum):
    TEXT = "text"
    NUMERIC = "numeric"
    DATE = "date"
    IMAGE = "image"
    COORDS = "coords"
    URL = "url"


class Signal(BaseModel):
    """A single piece of data extracted from a file, with full provenance."""

    # What was found
    type: SignalType
    label: str                          # Original label from file: "ADREÇA OBRA"
    value: Any                          # The extracted value
    raw_value: str = ""                 # Before normalization

    # Where it maps
    maps_to: str | None = None          # Report variable: "street_address"

    # Provenance
    source_file: str                    # Relative path within project
    source_location: str = ""           # "Sheet 'fitxa', cell B3"
    extraction_method: str = ""         # "cell_adjacent", "regex", "embedded_image"

    # Quality
    confidence: float = 0.5             # 0.0-1.0
    priority: int = 50                  # Lower = wins in conflicts


class MiningResult(BaseModel):
    """Result of mining a project's files."""

    project_path: str
    signals: list[Signal] = Field(default_factory=list)
    files_mined: int = 0
    files_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_ms: int = 0


class ResolvedValue(BaseModel):
    """Winner of signal competition for a single report variable."""

    variable: str                       # "street_address"
    value: Any
    source: str                         # "dades_camp_excel"
    confidence: float
    signal: Signal                      # The winning signal
    alternatives: list[Signal] = Field(default_factory=list)  # Losers, for wizard display
