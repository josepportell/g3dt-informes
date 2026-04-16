#!/usr/bin/env python3
"""CC-Agentic extractor: reproducible Anthropic vision extraction for testing.

Sends project files to the Anthropic API with the concept schema as context,
producing structured variable extractions with confidence scores and provenance.

NOT interactive Claude Code -- this is a deterministic Python module for
benchmarking insertion points.

Usage:
    from tests.cc_agentic.cc_extractor import extract_from_files

    variables, trace = extract_from_files(files, schema_path)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Env
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """Load .env from project root if present."""
    env_path = _PROJECT_ROOT / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())


_load_env()

# ---------------------------------------------------------------------------
# Schema loader
# ---------------------------------------------------------------------------

def load_concept_schema(schema_path: str | Path) -> dict[str, dict]:
    """Load report_variables.yaml and return {concept_id: {type, group, description_ca, ...}}."""
    data = yaml.safe_load(Path(schema_path).read_text(encoding='utf-8'))
    return data.get('concepts', {})


def _build_variable_prompt(concepts: dict[str, dict]) -> str:
    """Build the variable list section for the extraction prompt."""
    lines = []
    for cid, cdef in concepts.items():
        desc = cdef.get('description_ca', cid)
        ctype = cdef.get('type', 'text')
        lines.append(f"- {cid} ({ctype}): {desc}")
    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# PDF / image rendering
# ---------------------------------------------------------------------------

_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'}


def _render_pdf_pages(pdf_path: Path, dpi: int = 200, max_pages: int = 10) -> list[str]:
    """Render PDF pages to base64 JPEG strings via PyMuPDF."""
    import fitz

    images: list[str] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes(output='jpeg', jpg_quality=85)

            # Downscale if over 4 MB
            if len(img_bytes) > 4 * 1024 * 1024:
                zoom = 150 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes(output='jpeg', jpg_quality=75)

            images.append(base64.b64encode(img_bytes).decode('utf-8'))
    finally:
        doc.close()
    return images


def _read_image_b64(image_path: Path) -> list[str]:
    """Read an image file and return as base64 JPEG list."""
    img_bytes = image_path.read_bytes()
    is_jpeg = img_bytes[:2] == b'\xff\xd8'
    is_too_large = len(img_bytes) > 4 * 1024 * 1024
    if not is_jpeg or is_too_large:
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(img_bytes))
            if is_too_large:
                img.thumbnail((2000, 2000))
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            img_bytes = buf.getvalue()
            img.close()
        except ImportError:
            logger.warning("Pillow not available for image conversion: %s", image_path.name)
            return []
    return [base64.b64encode(img_bytes).decode('utf-8')]


# ---------------------------------------------------------------------------
# Excel extraction (no API call)
# ---------------------------------------------------------------------------

def _extract_excel(path: Path, target_vars: dict[str, dict]) -> dict[str, dict]:
    """Parse Excel file locally and extract signals. Returns {var: {value, confidence}}."""
    import xlrd

    results: dict[str, dict] = {}
    try:
        wb = xlrd.open_workbook(str(path))
    except Exception as exc:
        logger.warning("Cannot open Excel %s: %s", path.name, exc)
        return results

    all_text_lines: list[str] = []
    for sheet in wb.sheets():
        for row_idx in range(sheet.nrows):
            cells = [str(sheet.cell_value(row_idx, c)).strip() for c in range(sheet.ncols)]
            line = ' | '.join(c for c in cells if c)
            if line:
                all_text_lines.append(line)

    text_blob = '\n'.join(all_text_lines)

    _patterns: list[tuple[str, str, float]] = [
        ('expedient', r'(?:expedient|ref(?:erencia)?)\s*[:\-]?\s*(\S+)', 0.6),
        ('client_name', r'(?:client|promotor)\s*[:\-]?\s*(.+)', 0.5),
        ('municipality', r'(?:municipi|poblaci[oó])\s*[:\-]?\s*(.+)', 0.6),
        ('street_address', r'(?:adre[cç]a|situaci[oó]|empla[cç]ament)\s*[:\-]?\s*(.+)', 0.5),
    ]
    for var, pattern, conf in _patterns:
        if var not in target_vars:
            continue
        m = re.search(pattern, text_blob, re.IGNORECASE)
        if m:
            results[var] = {'value': m.group(1).strip(), 'confidence': conf}

    return results


# ---------------------------------------------------------------------------
# Text file extraction (no API call)
# ---------------------------------------------------------------------------

def _extract_text(path: Path, target_vars: dict[str, dict]) -> dict[str, dict]:
    """Parse a text file for coordinate data and simple signals."""
    results: dict[str, dict] = {}
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return results

    utm_pattern = re.compile(r'(\d{6}[.,]\d+)\s+(\d{7}[.,]\d+)', re.MULTILINE)
    m = utm_pattern.search(text)
    if m:
        results['utm_x'] = {'value': m.group(1).replace(',', '.'), 'confidence': 0.9}
        results['utm_y'] = {'value': m.group(2).replace(',', '.'), 'confidence': 0.9}

    return results


# ---------------------------------------------------------------------------
# Anthropic vision API
# ---------------------------------------------------------------------------

_MODEL = 'claude-sonnet-4-5-20250514'


def _call_vision(
    images_b64: list[str],
    prompt: str,
    *,
    max_tokens: int = 4096,
) -> tuple[dict, dict]:
    """Call Anthropic vision API. Returns (parsed_json, usage_dict)."""
    import anthropic

    client = anthropic.Anthropic()

    content: list[dict] = []
    for img in images_b64:
        content.append({
            'type': 'image',
            'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': img},
        })
    content.append({'type': 'text', 'text': prompt})

    t0 = time.monotonic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        messages=[{'role': 'user', 'content': content}],
        timeout=120.0,
    )
    elapsed = time.monotonic() - t0

    raw_text = response.content[0].text.strip()
    if raw_text.startswith('```'):
        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
        raw_text = re.sub(r'\s*```$', '', raw_text)

    usage = {
        'input_tokens': response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'elapsed_s': round(elapsed, 2),
    }

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON from vision response: %.200s", raw_text)
        parsed = {}

    return parsed, usage


_EXTRACTION_PROMPT = """\
You are extracting data from a geotechnical project document.
Extract all values you can identify for these variables:

{variable_list}

Return JSON: {{"variable_name": {{"value": <extracted>, "confidence": 0.0-1.0}}, ...}}
Set null for variables not present in this document.
Only include variables you can actually find evidence for -- omit others entirely.
For confidence: 1.0 = clearly legible, 0.7 = readable but uncertain, <0.5 = guessing."""


def _extract_via_vision(
    images_b64: list[str],
    concepts: dict[str, dict],
) -> tuple[dict[str, dict], dict]:
    """Send images to Anthropic and parse variable extractions.

    Returns (variables_dict, usage).
    """
    variable_list = _build_variable_prompt(concepts)
    prompt = _EXTRACTION_PROMPT.format(variable_list=variable_list)

    parsed, usage = _call_vision(images_b64, prompt)

    results: dict[str, dict] = {}
    for var_name, entry in parsed.items():
        if var_name not in concepts:
            continue
        if entry is None:
            continue
        if isinstance(entry, dict):
            val = entry.get('value')
            conf = entry.get('confidence', 0.5)
        else:
            val = entry
            conf = 0.5
        if val is not None:
            results[var_name] = {'value': val, 'confidence': float(conf)}

    return results, usage


# ---------------------------------------------------------------------------
# Agentic crop re-read
# ---------------------------------------------------------------------------

def _agentic_crop_reread(
    low_confidence_vars: dict[str, dict],
    file_path: Path,
    concepts: dict[str, dict],
    max_crops: int = 3,
) -> tuple[dict[str, dict], list[dict]]:
    """Re-read low-confidence variables at higher DPI with a targeted prompt.

    Re-sends first 3 pages at 300 DPI asking only for the problem variables.
    """
    crop_results: dict[str, dict] = {}
    crop_trace: list[dict] = []

    if file_path.suffix.lower() != '.pdf':
        return crop_results, crop_trace

    sorted_vars = sorted(low_confidence_vars.items(), key=lambda kv: kv[1].get('confidence', 0))
    target_vars = dict(sorted_vars[:max_crops])

    if not target_vars:
        return crop_results, crop_trace

    images = _render_pdf_pages(file_path, dpi=300, max_pages=3)
    if not images:
        return crop_results, crop_trace

    subset_concepts = {k: concepts[k] for k in target_vars if k in concepts}
    variable_list = _build_variable_prompt(subset_concepts)
    prompt = (
        "Look very carefully at this document. I need you to re-examine these "
        "specific variables that were hard to read on the first pass. "
        "Focus especially on handwritten text, stamps, and small print.\n\n"
        f"{variable_list}\n\n"
        'Return JSON: {"variable_name": {"value": <extracted>, "confidence": 0.0-1.0}, ...}'
    )

    parsed, usage = _call_vision(images, prompt)

    for var_name, entry in parsed.items():
        if var_name not in subset_concepts:
            continue
        if entry is None or not isinstance(entry, dict):
            continue
        val = entry.get('value')
        conf = entry.get('confidence', 0.5)
        if val is not None and float(conf) > low_confidence_vars.get(var_name, {}).get('confidence', 0):
            crop_results[var_name] = {'value': val, 'confidence': float(conf)}

    crop_trace.append({
        'action_id': f'crop_reread_{file_path.name}',
        'type': 'agentic_crop',
        'file': str(file_path.name),
        'target_vars': list(target_vars.keys()),
        'improved_vars': list(crop_results.keys()),
        'usage': usage,
    })

    return crop_results, crop_trace


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def extract_from_files(
    files: list[dict],
    concept_schema_path: str | Path,
    *,
    agentic_crops: bool = True,
    max_crops_per_file: int = 3,
    crop_confidence_threshold: float = 0.7,
) -> tuple[dict, list[dict]]:
    """Extract report variables from a list of project files via Anthropic API.

    Args:
        files: List of dicts with keys: path (str), role (str), origin (str).
        concept_schema_path: Path to schemas/concepts/report_variables.yaml.
        agentic_crops: If True, re-read low-confidence variables at 300 DPI.
        max_crops_per_file: Max crop re-reads per file.
        crop_confidence_threshold: Variables below this trigger a crop re-read.

    Returns:
        (variables_dict, actions_trace)
        variables_dict: {var_name: {value, confidence, source_file, source_origin, extraction_method}}
        actions_trace: [{action_id, type, file, ...}]
    """
    concepts = load_concept_schema(concept_schema_path)
    merged: dict[str, dict] = {}
    trace: list[dict] = []
    total_usage = {'input_tokens': 0, 'output_tokens': 0, 'api_calls': 0}

    for finfo in files:
        fpath = Path(finfo['path'])
        role = finfo.get('role', 'unknown')
        origin = finfo.get('origin', 'project')

        if not fpath.exists():
            logger.warning("File not found: %s", fpath)
            trace.append({
                'action_id': f'skip_{fpath.name}',
                'type': 'file_skip',
                'file': str(fpath.name),
                'reason': 'not_found',
            })
            continue

        ext = fpath.suffix.lower()
        t0 = time.monotonic()
        file_results: dict[str, dict] = {}
        file_usage: dict = {}

        if ext in ('.xls', '.xlsx'):
            file_results = _extract_excel(fpath, concepts)
            method = 'excel_parse'
        elif ext == '.txt':
            file_results = _extract_text(fpath, concepts)
            method = 'text_parse'
        elif ext == '.pdf':
            images = _render_pdf_pages(fpath, dpi=200, max_pages=10)
            if images:
                file_results, file_usage = _extract_via_vision(images, concepts)
                total_usage['input_tokens'] += file_usage.get('input_tokens', 0)
                total_usage['output_tokens'] += file_usage.get('output_tokens', 0)
                total_usage['api_calls'] += 1
            method = 'vision_pdf'
        elif ext in _IMAGE_EXTENSIONS:
            images = _read_image_b64(fpath)
            if images:
                file_results, file_usage = _extract_via_vision(images, concepts)
                total_usage['input_tokens'] += file_usage.get('input_tokens', 0)
                total_usage['output_tokens'] += file_usage.get('output_tokens', 0)
                total_usage['api_calls'] += 1
            method = 'vision_image'
        else:
            method = 'unsupported'
            logger.debug("Skipping unsupported file type: %s", fpath.name)

        elapsed = time.monotonic() - t0

        # Agentic crop re-read for low-confidence PDF extractions
        crop_trace: list[dict] = []
        if agentic_crops and ext == '.pdf' and file_results:
            low_conf = {
                k: v for k, v in file_results.items()
                if v.get('confidence', 1.0) < crop_confidence_threshold
            }
            if low_conf:
                crop_results, crop_trace = _agentic_crop_reread(
                    low_conf, fpath, concepts, max_crops=max_crops_per_file,
                )
                for var, val in crop_results.items():
                    file_results[var] = val
                for ct in crop_trace:
                    total_usage['input_tokens'] += ct.get('usage', {}).get('input_tokens', 0)
                    total_usage['output_tokens'] += ct.get('usage', {}).get('output_tokens', 0)
                    total_usage['api_calls'] += 1

        trace.append({
            'action_id': f'extract_{fpath.name}',
            'type': 'file_extraction',
            'file': str(fpath.name),
            'role': role,
            'origin': origin,
            'method': method,
            'vars_extracted': len(file_results),
            'elapsed_s': round(elapsed, 2),
            'usage': file_usage,
        })
        trace.extend(crop_trace)

        # Merge: highest confidence wins
        for var, val in file_results.items():
            existing = merged.get(var)
            if existing is None or val.get('confidence', 0) > existing.get('confidence', 0):
                merged[var] = {
                    'value': val['value'],
                    'confidence': val.get('confidence', 0.5),
                    'source_file': fpath.name,
                    'source_origin': origin,
                    'extraction_method': method,
                }

    trace.append({
        'action_id': 'usage_summary',
        'type': 'summary',
        'total_usage': total_usage,
    })

    return merged, trace
