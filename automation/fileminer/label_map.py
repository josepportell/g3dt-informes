"""
Label-to-variable mapping dictionary and source priorities.

Canonical source: YAML schemas in schemas/concepts/ and schemas/formats/.
This module loads from YAML and exposes the same LABEL_TO_VARIABLE and
SOURCE_PRIORITY dicts that the rest of the codebase imports.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


def _load_label_map() -> dict[str, str]:
    """Load label map from YAML format schemas."""
    try:
        from automation.schemas.loader import FormatRegistry
        fr = FormatRegistry()
        result = fr.build_label_map()
        if result:
            return result
    except Exception:
        _logger.warning(
            "Failed to load label map from YAML schemas — "
            "check schemas/formats/*.yaml exist and are valid",
            exc_info=True,
        )
    return {}


def _load_source_priority() -> dict[str, int]:
    """Load source priorities from YAML concept schemas."""
    # Known source types — if YAML loading fails, these get default priority 50
    _KNOWN_SOURCES = [
        "user", "planol_vision", "sondeig_vision", "dpsh_vision",
        "coordenades_txt", "pressupost_pdf", "icgc_api", "cadastre_api",
        "dades_camp_excel", "comanda_lab_excel", "geocode_nominatim",
        "groq_llm", "content_email", "content_email_attachment",
        "content_pdf", "content_docx", "content_excel", "content_text",
        "folder_name",
    ]
    try:
        from automation.schemas.loader import ConceptRegistry
        cr = ConceptRegistry()
        result = {}
        for source_type in _KNOWN_SOURCES:
            result[source_type] = cr.get_default_priority(source_type)
        if result:
            return result
    except Exception:
        _logger.warning(
            "Failed to load source priorities from YAML schemas — "
            "check schemas/concepts/report_variables.yaml exists and is valid",
            exc_info=True,
        )
    return {}


# Maps raw labels (uppercased) -> concept/report variable name
LABEL_TO_VARIABLE: dict[str, str] = _load_label_map()

# Source priority: lower number = more reliable = wins in competition
SOURCE_PRIORITY: dict[str, int] = _load_source_priority()


def get_priority(source_type: str) -> int:
    """Get priority for a source type. Unknown sources get 50."""
    return SOURCE_PRIORITY.get(source_type, 50)
