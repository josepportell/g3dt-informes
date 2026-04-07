"""
SmartScan Tier 3: Vision classification (Groq Llama 4 Scout + Claude fallback).

Last resort for files that escape Tier 1 (filename) and Tier 2
(fingerprint). Sends the first page of a PDF or an image directly
to a multimodal LLM for classification.

Supports both PDFs (rendered to image) and images (.jpg/.jpeg/.png).
Uses Groq Llama 4 Scout by default (~$0.003/image), falls back to
Claude if Groq unavailable.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path

from .confidence import TIER3_BASE, classify_category
from .models import ClassificationTier, FileClassification

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}

VISION_CLASSIFICATION_PROMPT = """You are classifying a file from a geotechnical engineering project folder.
This could be a PDF document or a photograph/screenshot. Determine its role.

Possible roles:
1. dpsh_field_sheet - Handwritten DPSH/penetrometer field sheet (N20 values, depth readings)
2. sondeig_field_sheet - Handwritten borehole/sondeig field sheet (soil layers, SPT)
3. architect_plan - Architect's building plan (floor plan, elevations, sections, dimensions)
4. sondeig_annex - Formatted borehole log (vector PDF, columns with soil descriptions)
5. correlation_section - Geological correlation section (cross-section between test points)
6. situation_plan - Site location plan (map showing where the project is)
7. reference_report - Geotechnical report document (text-heavy, multiple pages)
8. lab_results_pdf - Laboratory test results (sulfates, soil classification)
9. gtl_report - GTL laboratory report (accreditation, test results)
10. architect_project - Architect's basic project (multi-page, regulations + plans)
11. lab_order - Laboratory order form
12. field_croquis - Hand-drawn sketch of test point locations on a plot
13. figure_situation_map - Situation/location map screenshot or image
14. figure_geological_map - Geological map screenshot or image
15. figure_test_points - Map/sketch showing test point positions
16. figure_correlation - Correlation section image
17. photo_test_point - Photograph of a field test point (P1, P2, etc.)
18. photo_dpsh_equipment - Photograph of DPSH penetrometer equipment
19. photo_sondeig_equipment - Photograph of borehole/sondeig equipment
20. photo_spt_sample - Photograph of SPT soil sample
21. photo_site_overview - Photograph of the construction site overview
22. field_photo - Generic field photograph (not classifiable as above)
23. unknown - Cannot determine the role

Respond in JSON format:
{"role": "<role_name>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}
"""


def classify_tier3(
    project_path: Path,
    entries: list[tuple[str, bool]],
    already_classified: set[str],
) -> list[FileClassification]:
    """
    Classify remaining files using vision (Groq or Claude).

    Processes PDFs and images not yet classified by Tier 1 or Tier 2.
    Tries Groq Llama 4 Scout first (cheap), falls back to Claude.

    Args:
        project_path: Absolute path to the project folder
        entries: All (relative_path, is_directory) tuples
        already_classified: Set of relative paths already classified

    Returns:
        List of FileClassification for files classified by vision.
    """
    results: list[FileClassification] = []

    # Collect files that need vision classification
    pending: list[tuple[str, Path]] = []
    for rel_path, is_dir in entries:
        if rel_path in already_classified or is_dir:
            continue
        abs_path = project_path / rel_path
        ext = abs_path.suffix.lower()
        if ext == '.pdf' or ext in _IMAGE_EXTENSIONS:
            pending.append((rel_path, abs_path))

    if not pending:
        return results

    # Determine which vision backend to use
    groq_available = bool(os.environ.get("GROQ_API_KEY"))
    claude_available = _check_claude_available()

    if not groq_available and not claude_available:
        logger.info("No vision API available for Tier 3 (need GROQ_API_KEY or ANTHROPIC_API_KEY)")
        # Mark all pending as unclassified_readable
        for rel_path, abs_path in pending:
            results.append(_make_unclassified_readable(rel_path))
        return results

    for rel_path, abs_path in pending:
        try:
            clf = None

            # Try Groq first (27x cheaper than Claude)
            if groq_available:
                clf = _classify_with_groq(rel_path, abs_path)

            # Fall back to Claude if Groq failed or unavailable
            if clf is None and claude_available:
                clf = _classify_with_claude(rel_path, abs_path)

            if clf:
                results.append(clf)
            else:
                # Vision tried but couldn't classify → unclassified_readable
                results.append(_make_unclassified_readable(rel_path))

        except Exception as e:
            logger.warning(f"Tier 3 vision failed for {rel_path}: {e}")
            results.append(_make_unclassified_readable(rel_path))

    return results


def _make_unclassified_readable(rel_path: str) -> FileClassification:
    """Create an unclassified_readable entry for files vision couldn't classify."""
    return FileClassification(
        file_path=rel_path,
        role=None,
        confidence=0.0,
        tier=ClassificationTier.VISION,
        category="unclassified_readable",
        summary="Readable file, not classified after all 3 tiers. Review manually.",
    )


# ──────────────────────────────────────────────────────────────
# Groq Vision (Llama 4 Scout)
# ──────────────────────────────────────────────────────────────

GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _classify_with_groq(
    rel_path: str,
    abs_path: Path,
) -> FileClassification | None:
    """Classify a file using Groq Llama 4 Scout vision."""
    img_b64, media_type = _get_image_b64(abs_path)
    if not img_b64:
        return None

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not available for Groq vision")
        return None

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_CLASSIFICATION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{img_b64}"},
                    },
                ],
            },
        ],
        "temperature": 0.0,
        "max_tokens": 256,
        "response_format": {"type": "json_object"},
    }

    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                GROQ_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code == 429:
            logger.warning("Groq Tier 3: rate limited for %s", rel_path)
            return None

        if resp.status_code != 200:
            logger.warning("Groq Tier 3: HTTP %d for %s", resp.status_code, rel_path)
            return None

        data = resp.json()
        content_str = data["choices"][0]["message"]["content"]
        result = json.loads(content_str)

        usage = data.get("usage", {})
        logger.info(
            "Groq Tier 3: %s → %s (%.0f%%) in %dms (%d tokens)",
            rel_path, result.get("role"), result.get("confidence", 0) * 100,
            elapsed_ms, usage.get("prompt_tokens", 0),
        )

        return _parse_vision_result(rel_path, result)

    except Exception as e:
        logger.warning("Groq Tier 3 error for %s: %s", rel_path, e)
        return None


# ──────────────────────────────────────────────────────────────
# Claude Vision (fallback)
# ──────────────────────────────────────────────────────────────

def _classify_with_claude(
    rel_path: str,
    abs_path: Path,
) -> FileClassification | None:
    """Classify a file using Claude vision (fallback)."""
    img_b64, media_type = _get_image_b64(abs_path)
    if not img_b64:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception:
        return None

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
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

        text = response.content[0].text
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(text[json_start:json_end])
            logger.info("Claude Tier 3: %s → %s (%.0f%%)",
                        rel_path, result.get("role"), result.get("confidence", 0) * 100)
            return _parse_vision_result(rel_path, result)

    except Exception as e:
        logger.warning("Claude Tier 3 error for %s: %s", rel_path, e)

    return None


# ──────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────

def _get_image_b64(abs_path: Path) -> tuple[str | None, str]:
    """Get base64-encoded image from a file (PDF or image).

    For PDFs: renders first page at 150 DPI.
    For images: reads directly.

    Returns (base64_string, media_type) or (None, "") on failure.
    """
    ext = abs_path.suffix.lower()

    if ext in _IMAGE_EXTENSIONS:
        try:
            img_bytes = abs_path.read_bytes()
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            media_type = 'image/png' if ext == '.png' else 'image/jpeg'
            return img_b64, media_type
        except Exception as e:
            logger.warning("Cannot read image %s: %s", abs_path.name, e)
            return None, ""

    if ext == '.pdf':
        try:
            import fitz
            doc = fitz.open(str(abs_path))
            if len(doc) == 0:
                doc.close()
                return None, ""
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            doc.close()
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            return img_b64, "image/png"
        except Exception as e:
            logger.warning("Cannot render PDF %s: %s", abs_path.name, e)
            return None, ""

    return None, ""


def _parse_vision_result(rel_path: str, result: dict) -> FileClassification | None:
    """Parse the JSON result from vision classification into a FileClassification."""
    role = result.get('role')
    confidence = float(result.get('confidence', 0.5))
    reasoning = result.get('reasoning', '')

    # Photo roles → informative (useful for report but no data extraction)
    photo_roles = {
        'photo_test_point', 'photo_dpsh_equipment', 'photo_sondeig_equipment',
        'photo_spt_sample', 'photo_site_overview', 'field_photo',
    }

    if role == 'unknown' or not role:
        return FileClassification(
            file_path=rel_path,
            role=None,
            confidence=0.0,
            tier=ClassificationTier.VISION,
            category="unclassified_readable",
            summary=reasoning or 'Vision could not classify',
        )

    # Scale confidence with tier base
    final_confidence = min(confidence * TIER3_BASE / 0.8, 0.95)

    if role in photo_roles:
        # Photos are informative — useful for report figure/photo placement
        # but don't need data extraction
        return FileClassification(
            file_path=rel_path,
            role=role,
            confidence=final_confidence,
            tier=ClassificationTier.VISION,
            category="informative",
            summary=reasoning,
        )

    return FileClassification(
        file_path=rel_path,
        role=role,
        confidence=final_confidence,
        tier=ClassificationTier.VISION,
        category=classify_category(final_confidence, role),
        summary=reasoning,
    )


def _check_claude_available() -> bool:
    """Check if Claude API is available."""
    try:
        import anthropic
        anthropic.Anthropic()
        return True
    except Exception:
        return False
