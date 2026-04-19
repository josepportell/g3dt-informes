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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation import config

logger = logging.getLogger(__name__)

__all__ = ['run_vision_extraction', 'extract_from_planol', 'extract_from_penetros', 'extract_from_sondeig', 'extract_from_sondeig_annex', 'attach_source_metadata']


def attach_source_metadata(
    data: dict,
    source_path: Path,
    project_path: Path | None = None,
    extraction_method: str | None = None,
) -> dict:
    """Stamp a `_metadata` block on an extracted JSON dict.

    Records which input artifact produced this extraction so inspection
    tools can trace vision fields back to the PDF (or image) they came from.

    - `source_file` is project-relative when `project_path` is supplied and
      `source_path` lives inside it; otherwise falls back to the basename.
    - `extracted_at` is an ISO-8601 timestamp in UTC (timezone-aware).
    - `extraction_method` is optional (e.g. 'claude_vision', 'groq_vision',
      'python_regex'); stamped when provided.

    The block is additive only — existing keys on `data` are preserved. If
    a `_metadata` dict already exists, missing keys are filled in.
    """
    meta = data.setdefault('_metadata', {})

    if 'source_file' not in meta:
        if project_path is not None:
            try:
                meta['source_file'] = str(Path(source_path).resolve().relative_to(Path(project_path).resolve()))
            except ValueError:
                meta['source_file'] = Path(source_path).name
        else:
            meta['source_file'] = Path(source_path).name

    meta.setdefault('extracted_at', datetime.now(timezone.utc).isoformat())

    if extraction_method:
        meta.setdefault('extraction_method', extraction_method)

    return data


MAX_TOKENS = 4096
# DPI for PDF rendering (150 is sufficient for text, keeps image size low)
RENDER_DPI = 150


# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------

def _get_client():
    """Get Anthropic-format client via the LLM factory (supports OpenRouter)."""
    try:
        from automation.llm_client import get_anthropic_client
    except ImportError:
        raise ImportError(
            "anthropic package not installed. Run: uv pip install anthropic"
        )
    return get_anthropic_client()


# ---------------------------------------------------------------------------
# File → images (PDF rendering or direct image read)
# ---------------------------------------------------------------------------

_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'}


def _file_to_images(file_path: Path, dpi: int = RENDER_DPI) -> list[tuple[bytes, str]]:
    """Convert a file (PDF or image) to image data for Claude vision.

    For PDFs: renders pages as PNG via PyMuPDF.
    For images: reads directly.

    Returns list of (image_bytes, media_type) tuples.
    """
    ext = file_path.suffix.lower()

    if ext in _IMAGE_EXTENSIONS:
        img_bytes = file_path.read_bytes()
        media_type = 'image/png' if ext == '.png' else 'image/jpeg'
        return [(img_bytes, media_type)]

    if ext == '.pdf':
        return _pdf_to_images(file_path, dpi)

    logger.warning("Unsupported file type for vision: %s", file_path.name)
    return []


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

    # Route model id through llm_client factory so OpenRouter gets the
    # namespaced model slug (anthropic/claude-sonnet-4.6) automatically.
    from automation.llm_client import get_cc_model
    kwargs: dict[str, Any] = {
        "model": get_cc_model(),
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

    images = _file_to_images(pdf_path)
    logger.info("Plànol: sending %d page(s) to Claude API", len(images))
    text = _call_vision(images, PLANOL_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT)
    data = _extract_json(text)

    # Ensure required metadata
    data.setdefault('source_file', pdf_path.name)
    data.setdefault('extraction_date', datetime.now(timezone.utc).isoformat())
    data.setdefault('extraction_method', 'claude_vision')
    data.setdefault('status', 'pending_review')
    attach_source_metadata(data, pdf_path, extraction_method='claude_vision')

    return data


def extract_from_penetros(pdf_path: Path) -> dict:
    """Read PENETROS.pdf and extract DPSH N20 values."""
    from .validation.prompts import DPSH_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT

    images = _file_to_images(pdf_path)
    logger.info("Penetros: sending %d page(s) to Claude API", len(images))
    text = _call_vision(images, DPSH_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT)
    data = _extract_json(text)

    data.setdefault('source_file', pdf_path.name)
    data.setdefault('extraction_date', datetime.now(timezone.utc).isoformat())
    data.setdefault('extraction_method', 'claude_vision')
    data.setdefault('status', 'pending_review')
    attach_source_metadata(data, pdf_path, extraction_method='claude_vision')

    return data


def extract_from_sondeig(pdf_path: Path) -> dict:
    """Read SONDEIG.pdf and extract soil layers."""
    from .validation.prompts import SONDEIG_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT

    images = _file_to_images(pdf_path)
    logger.info("Sondeig: sending %d page(s) to Claude API", len(images))
    text = _call_vision(images, SONDEIG_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT)
    data = _extract_json(text)

    data.setdefault('source_file', pdf_path.name)
    data.setdefault('extraction_date', datetime.now(timezone.utc).isoformat())
    data.setdefault('extraction_method', 'claude_vision')
    data.setdefault('status', 'pending_review')
    attach_source_metadata(data, pdf_path, extraction_method='claude_vision')

    return data


def extract_from_sondeig_annex(pdf_path: Path) -> dict:
    """Read formatted sondeig annex PDF and extract soil layers with geological levels."""
    from .validation.prompts import SONDEIG_ANNEX_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT

    images = _file_to_images(pdf_path)
    logger.info("Sondeig annex: sending %d page(s) to Claude API", len(images))
    text = _call_vision(images, SONDEIG_ANNEX_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT)
    data = _extract_json(text)

    data.setdefault('source_file', pdf_path.name)
    data.setdefault('extraction_date', datetime.now(timezone.utc).isoformat())
    data.setdefault('extraction_method', 'claude_vision')
    data.setdefault('status', 'pending_review')
    attach_source_metadata(data, pdf_path, extraction_method='claude_vision')

    return data


# ---------------------------------------------------------------------------
# Vision type registry: maps vision_type → (extract_fn, cache_filename)
# ---------------------------------------------------------------------------

VISION_REGISTRY: dict[str, tuple[Any, str]] = {
    'planol':        (extract_from_planol,        'planol_extracted.json'),
    'dpsh':          (extract_from_penetros,       'dpsh_extracted.json'),
    'sondeig':       (extract_from_sondeig,        'sondeig_extracted.json'),
    'sondeig_annex': (extract_from_sondeig_annex,  'sondeig_annex_extracted.json'),
}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_vision_extraction(
    project_path: Path,
    *,
    force_refresh: bool = False,
) -> dict[str, dict | None]:
    """Run all available vision extractions for a project.

    Iterates file_scanner roles, checks vision_type on each, and extracts
    the first match per vision_type. Saves results to validation/.
    Skips extraction if cached JSON already exists (unless force_refresh).

    Returns dict keyed by vision_type (e.g., planol, dpsh, sondeig).
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

    # Collect first role per vision_type (order in ROLE_DEFINITIONS = priority)
    vision_sources: dict[str, tuple[str, str]] = {}  # vision_type → (role_name, path)
    for role_name, role in mapping.roles.items():
        vt = role.vision_type
        if vt and vt in VISION_REGISTRY and vt not in vision_sources:
            vision_sources[vt] = (role_name, role.path)

    # Extract each vision type
    for vt, (role_name, rel_path) in vision_sources.items():
        extract_fn, cache_filename = VISION_REGISTRY[vt]
        cache_path = validation_dir / cache_filename
        pdf_path = project_path / rel_path

        results[vt] = _extract_or_cache(
            vt, role_name, pdf_path, cache_path, extract_fn, force_refresh,
            project_path=project_path,
        )

    # Mark missing vision types
    for vt in VISION_REGISTRY:
        if vt not in results:
            results[vt] = None
            logger.info("%s: no PDF with vision_type=%s in file mapping", vt, vt)

    elapsed = time.monotonic() - t0
    n_extracted = sum(1 for v in results.values() if v is not None)
    n_total = len(VISION_REGISTRY)
    logger.info("Vision extraction: %d/%d types in %.1fs", n_extracted, n_total, elapsed)

    return results


def _extract_or_cache(
    vision_type: str,
    role_name: str,
    pdf_path: Path,
    cache_path: Path,
    extract_fn,
    force_refresh: bool,
    project_path: Path | None = None,
) -> dict | None:
    """Extract from PDF or use cached JSON."""
    label = f"{vision_type} ({role_name})"

    # Check cache
    if cache_path.exists() and not force_refresh:
        try:
            cached = json.loads(cache_path.read_text(encoding='utf-8'))
            # Invalidate cache if source_file changed (e.g., switched from
            # field sheet to formatted annex for the same vision type)
            cached_source = cached.get('source_file', '')
            if cached_source and cached_source != pdf_path.name:
                logger.info(
                    "%s: cache source_file mismatch (%s != %s), re-extracting",
                    label, cached_source, pdf_path.name,
                )
            else:
                logger.info("%s: using cached %s", label, cache_path.name)
                return cached
        except (json.JSONDecodeError, OSError):
            pass  # Fall through to re-extract

    if not pdf_path.exists():
        logger.warning("%s: PDF %s does not exist", label, pdf_path)
        return None

    try:
        logger.info("%s: extracting from %s", label, pdf_path.name)
        data = extract_fn(pdf_path)
        attach_source_metadata(
            data, pdf_path, project_path=project_path,
            extraction_method='claude_vision',
        )
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
