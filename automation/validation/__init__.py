"""
G3DT Field Data Validation Layer

This module provides tools for extracting, validating, and correcting
data from handwritten field documents (PENETROS.pdf, SONDEIG.pdf, etc.)

Components:
- schemas.py: Pydantic models for validation data
- prompts.py: Extraction prompt templates for Claude vision
- extractor.py: PDF → JSON orchestration

Workflow:
1. Extract data from field PDFs using Claude vision
2. Save to validation/dpsh_extracted.json with confidence scores
3. G3DT reviews and corrects via HTML form
4. Save approved data to validation/dpsh_approved.json
5. Report generation uses approved data when available

Author: Eficients.cat
Date: 2026-02-04
"""

from .schemas import (
    ValidationStatus,
    ExtractionMethod,
    DPSHReadingExtracted,
    DPSHTestExtracted,
    DPSHValidationFile,
    SondeigLayerExtracted,
    SondeigTestExtracted,
    SondeigValidationFile,
)
from .extractor import (
    create_validation_folder,
    parse_dpsh_extraction_response,
    parse_sondeig_extraction_response,
    save_extraction_result,
    compare_with_excel,
    create_from_excel,
    load_validation_file,
)
from .prompts import (
    DPSH_EXTRACTION_PROMPT,
    SONDEIG_EXTRACTION_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
)

__all__ = [
    # Schemas
    "ValidationStatus",
    "ExtractionMethod",
    "DPSHReadingExtracted",
    "DPSHTestExtracted",
    "DPSHValidationFile",
    "SondeigLayerExtracted",
    "SondeigTestExtracted",
    "SondeigValidationFile",
    # Extractor
    "create_validation_folder",
    "parse_dpsh_extraction_response",
    "parse_sondeig_extraction_response",
    "save_extraction_result",
    "compare_with_excel",
    "create_from_excel",
    "load_validation_file",
    # Prompts
    "DPSH_EXTRACTION_PROMPT",
    "SONDEIG_EXTRACTION_PROMPT",
    "EXTRACTION_SYSTEM_PROMPT",
]
