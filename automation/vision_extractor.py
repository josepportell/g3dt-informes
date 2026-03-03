#!/usr/bin/env python3
"""
G3DT Vision Extractor (Fase 1)

Reads PDFs using Claude API (Anthropic) vision to extract structured data.
Converts PDF pages to images via PyMuPDF, sends to Claude API.

Three extraction types:
- Plànol (A.01.pdf): architect data, dimensions
- Penetros (PENETROS.pdf): N20 values for validation
- Sondeig (SONDEIG.pdf): soil layers

Usage:
    from automation.vision_extractor import run_vision_extraction
    result = run_vision_extraction(Path('reference-material/4001612 BELL-LLOC'))

    # Or standalone test:
    python -m automation.vision_extractor "reference-material/4001612 BELL-LLOC"

Author: Eficients.cat
Date: 2026-03-03
"""

from __future__ import annotations

import base64
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ['run_vision_extraction', 'extract_from_planol', 'extract_from_penetros', 'extract_from_sondeig']

# Model: sonnet for cost/quality balance (~$0.03-0.10 per project)
VISION_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
# DPI for PDF rendering (150 is sufficient for text, keeps image size low)
RENDER_DPI = 150


# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------

def _load_env():
    """Load .env file from project root if it exists."""
    import os
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())


def _get_client():
    """Get Anthropic client. Reads ANTHROPIC_API_KEY from environment or .env."""
    _load_env()
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic package not installed. Run: uv pip install anthropic"
        )
    return anthropic.Anthropic()


# ---------------------------------------------------------------------------
# PDF → images
# ---------------------------------------------------------------------------

def _pdf_to_images(pdf_path: Path, dpi: int = RENDER_DPI) -> list[tuple[bytes, str]]:
    """Convert PDF pages to PNG images using PyMuPDF.

    Returns list of (image_bytes, media_type) tuples.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    images = []
    zoom = dpi / 72  # default PDF resolution is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)

    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("png")
        images.append((img_bytes, "image/png"))

    doc.close()
    return images


# ---------------------------------------------------------------------------
# Claude API call
# ---------------------------------------------------------------------------

def _call_vision(
    images: list[tuple[bytes, str]],
    prompt: str,
    system: str | None = None,
) -> str:
    """Send images to Claude API with vision and return text response."""
    client = _get_client()

    content: list[dict[str, Any]] = []
    for img_bytes, media_type in images:
        b64 = base64.standard_b64encode(img_bytes).decode("ascii")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64,
            }
        })
    content.append({"type": "text", "text": prompt})

    kwargs: dict[str, Any] = {
        "model": VISION_MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return response.content[0].text


# ---------------------------------------------------------------------------
# JSON extraction from response
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Extract JSON from model response, handling markdown code blocks."""
    # Try to find JSON in code blocks
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    # Fall back: find first { ... last }
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError(f"No JSON found in response: {text[:200]}")


# ---------------------------------------------------------------------------
# Individual extractors
# ---------------------------------------------------------------------------

def extract_from_planol(pdf_path: Path) -> dict:
    """Read A.01.pdf and extract architect data + dimensions."""
    from .validation.prompts import PLANOL_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT

    images = _pdf_to_images(pdf_path)
    logger.info("Plànol: sending %d page(s) to Claude API", len(images))
    text = _call_vision(images, PLANOL_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT)
    data = _extract_json(text)

    # Ensure required metadata
    data.setdefault('source_file', pdf_path.name)
    data.setdefault('extraction_date', datetime.now().isoformat())
    data.setdefault('extraction_method', 'claude_vision')
    data.setdefault('status', 'pending_review')

    return data


def extract_from_penetros(pdf_path: Path) -> dict:
    """Read PENETROS.pdf and extract DPSH N20 values."""
    from .validation.prompts import DPSH_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT

    images = _pdf_to_images(pdf_path)
    logger.info("Penetros: sending %d page(s) to Claude API", len(images))
    text = _call_vision(images, DPSH_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT)
    data = _extract_json(text)

    data.setdefault('source_file', pdf_path.name)
    data.setdefault('extraction_date', datetime.now().isoformat())
    data.setdefault('extraction_method', 'claude_vision')
    data.setdefault('status', 'pending_review')

    return data


def extract_from_sondeig(pdf_path: Path) -> dict:
    """Read SONDEIG.pdf and extract soil layers."""
    from .validation.prompts import SONDEIG_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT

    images = _pdf_to_images(pdf_path)
    logger.info("Sondeig: sending %d page(s) to Claude API", len(images))
    text = _call_vision(images, SONDEIG_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT)
    data = _extract_json(text)

    data.setdefault('source_file', pdf_path.name)
    data.setdefault('extraction_date', datetime.now().isoformat())
    data.setdefault('extraction_method', 'claude_vision')
    data.setdefault('status', 'pending_review')

    return data


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_vision_extraction(
    project_path: Path,
    *,
    force_refresh: bool = False,
) -> dict[str, dict | None]:
    """Run all available vision extractions for a project.

    Uses FileScanner to find PDFs, extracts data, saves to validation/.
    Skips extraction if cached JSON already exists (unless force_refresh).

    Returns dict with keys: planol, penetros, sondeig (each a dict or None).
    """
    from .file_scanner import FileScanner

    t0 = time.monotonic()
    results: dict[str, dict | None] = {}
    validation_dir = project_path / 'validation'
    validation_dir.mkdir(exist_ok=True)

    # Load file mapping to find PDFs
    scanner = FileScanner(project_path)
    mapping = scanner.load()
    if mapping is None:
        mapping = scanner.scan()
        scanner.save(mapping)

    # --- Plànol ---
    results['planol'] = _extract_or_cache(
        project_path, mapping, 'architect_plan',
        validation_dir / 'planol_extracted.json',
        extract_from_planol, force_refresh,
    )

    # --- Penetros (DPSH) ---
    results['penetros'] = _extract_or_cache(
        project_path, mapping, 'dpsh_field_sheet',
        validation_dir / 'dpsh_extracted.json',
        extract_from_penetros, force_refresh,
    )

    # --- Sondeig ---
    results['sondeig'] = _extract_or_cache(
        project_path, mapping, 'sondeig_field_sheet',
        validation_dir / 'sondeig_extracted.json',
        extract_from_sondeig, force_refresh,
    )

    elapsed = time.monotonic() - t0
    n_extracted = sum(1 for v in results.values() if v is not None)
    logger.info("Vision extraction: %d/3 types in %.1fs", n_extracted, elapsed)

    return results


def _extract_or_cache(
    project_path: Path,
    mapping,
    role_name: str,
    cache_path: Path,
    extract_fn,
    force_refresh: bool,
) -> dict | None:
    """Extract from PDF or use cached JSON."""
    label = role_name.replace('_', ' ').title()

    # Check cache
    if cache_path.exists() and not force_refresh:
        logger.info("%s: using cached %s", label, cache_path.name)
        try:
            return json.loads(cache_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            pass  # Fall through to re-extract

    # Find PDF via file mapping
    role = mapping.roles.get(role_name)
    if not role:
        logger.info("%s: no PDF found in file mapping", label)
        return None

    pdf_path = project_path / role.path
    if not pdf_path.exists():
        logger.warning("%s: PDF path %s does not exist", label, role.path)
        return None

    try:
        logger.info("%s: extracting from %s", label, pdf_path.name)
        data = extract_fn(pdf_path)
        cache_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        logger.info("%s: saved to %s", label, cache_path.name)
        return data
    except Exception as e:
        logger.warning("%s extraction failed: %s", label, e)
        return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for testing."""
    if len(sys.argv) < 2:
        print("Ús: python -m automation.vision_extractor <project_path> [--force]")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    project_path = Path(sys.argv[1])
    force = '--force' in sys.argv

    print(f"Vision extraction: {project_path}")
    print("=" * 60)

    results = run_vision_extraction(project_path, force_refresh=force)

    for key, data in results.items():
        if data:
            print(f"\n  {key}: OK")
            if key == 'planol' and 'architect_data' in data:
                arch = data['architect_data']
                print(f"    Projecte: {arch.get('project_name', '?')}")
                print(f"    Ubicació: {arch.get('location', '?')}")
                print(f"    Arquitecte: {arch.get('architect', '?')}")
                print(f"    Promotor: {arch.get('promotor', '?')}")
            elif key == 'penetros' and 'dpsh_tests' in data:
                n = len(data['dpsh_tests'])
                print(f"    {n} assaig(s) extrets")
            elif key == 'sondeig' and 'sondeig_tests' in data:
                n = len(data['sondeig_tests'])
                print(f"    {n} sondeig(s) extrets")
        else:
            print(f"\n  {key}: -")

    print()


if __name__ == '__main__':
    main()
