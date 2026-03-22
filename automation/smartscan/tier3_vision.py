"""
SmartScan Tier 3: Claude vision classification.

Last resort for files that escape Tier 1 (filename) and Tier 2
(fingerprint). Renders the first page of a PDF as an image and
sends it to Claude for classification.

Only called for truly ambiguous files. Most projects should
classify 100% at Tier 1+2.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .confidence import TIER3_BASE, classify_category
from .models import ClassificationTier, FileClassification

logger = logging.getLogger(__name__)


VISION_CLASSIFICATION_PROMPT = """You are classifying a document from a geotechnical engineering project.
Look at this first page and determine which role it plays.

Possible roles:
1. dpsh_field_sheet - Handwritten DPSH/penetrometer field sheet (N20 values, depth readings)
2. sondeig_field_sheet - Handwritten borehole/sondeig field sheet (soil layers, SPT)
3. architect_plan - Architect's building plan (floor plan, elevations, sections)
4. sondeig_annex - Formatted borehole log (vector PDF, columns with soil descriptions)
5. correlation_section - Geological correlation section (cross-section between test points)
6. situation_plan - Site location plan (map showing where the project is)
7. reference_report - Geotechnical report document (text-heavy, multiple pages)
8. lab_results_pdf - Laboratory test results (sulfates, soil classification)
9. gtl_report - GTL laboratory report (accreditation, test results)
10. architect_project - Architect's basic project (multi-page, regulations + plans)
11. lab_order - Laboratory order form
12. unknown - Cannot determine the role

Respond in JSON format:
{"role": "<role_name>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}
"""


def classify_tier3(
    project_path: Path,
    entries: list[tuple[str, bool]],
    already_classified: set[str],
) -> list[FileClassification]:
    """
    Classify remaining files using Claude vision.

    Only processes PDF files not yet classified by Tier 1 or Tier 2.
    Requires the anthropic SDK and a valid API key.

    Args:
        project_path: Absolute path to the project folder
        entries: All (relative_path, is_directory) tuples
        already_classified: Set of relative paths already classified

    Returns:
        List of FileClassification for files classified by vision.
    """
    results: list[FileClassification] = []

    # Collect PDFs that need vision classification
    pending_pdfs: list[tuple[str, Path]] = []
    for rel_path, is_dir in entries:
        if rel_path in already_classified or is_dir:
            continue
        abs_path = project_path / rel_path
        if abs_path.suffix.lower() == '.pdf':
            pending_pdfs.append((rel_path, abs_path))

    if not pending_pdfs:
        return results

    # Check if we can use Claude API
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception as e:
        logger.info(f"Claude API not available for Tier 3: {e}")
        return results

    try:
        import fitz  # For rendering PDF to image
    except ImportError:
        logger.warning("PyMuPDF not available for Tier 3 rendering")
        return results

    for rel_path, abs_path in pending_pdfs:
        try:
            clf = _classify_with_vision(rel_path, abs_path, client)
            if clf:
                results.append(clf)
        except Exception as e:
            logger.warning(f"Tier 3 vision failed for {rel_path}: {e}")

    return results


def _classify_with_vision(
    rel_path: str,
    abs_path: Path,
    client,
) -> FileClassification | None:
    """Render first page and classify with Claude vision."""
    import base64
    import fitz

    try:
        doc = fitz.open(str(abs_path))
        if len(doc) == 0:
            doc.close()
            return None

        # Render first page at 150 DPI
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        doc.close()

        img_b64 = base64.b64encode(img_bytes).decode('utf-8')

        # Call Claude API
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": VISION_CLASSIFICATION_PROMPT,
                    },
                ],
            }],
        )

        # Parse response
        text = response.content[0].text
        # Extract JSON from response
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(text[json_start:json_end])
            role = result.get('role')
            confidence = float(result.get('confidence', 0.5))

            if role == 'unknown' or not role:
                return FileClassification(
                    file_path=rel_path,
                    role=None,
                    confidence=0.0,
                    tier=ClassificationTier.VISION,
                    category="unknown",
                    summary=result.get('reasoning', 'Vision could not classify'),
                )

            # Scale confidence with tier base
            final_confidence = min(confidence * TIER3_BASE / 0.8, 0.95)

            return FileClassification(
                file_path=rel_path,
                role=role,
                confidence=final_confidence,
                tier=ClassificationTier.VISION,
                category=classify_category(final_confidence, role),
                summary=result.get('reasoning', ''),
            )

    except Exception as e:
        logger.warning(f"Vision classification error for {rel_path}: {e}")

    return None
