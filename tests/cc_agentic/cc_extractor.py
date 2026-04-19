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


def _build_variable_prompt(
    concepts: dict[str, dict],
    template_patterns: dict[str, str] | None = None,
) -> str:
    """Build the variable list section for the extraction prompt.

    If `template_patterns` is provided, each matching concept line is followed
    by a TEMPLATE hint so the model adapts facts into Eva's expected phrasing.
    """
    tp = template_patterns or {}
    lines = []
    for cid, cdef in concepts.items():
        desc = cdef.get('description_ca', cid)
        ctype = cdef.get('type', 'text')
        lines.append(f"- {cid} ({ctype}): {desc}")
        if cid in tp:
            lines.append(f"    TEMPLATE: {tp[cid]}")
    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# LLM JSON response parsing
# ---------------------------------------------------------------------------

def _extract_balanced_json_object(text: str) -> str | None:
    """Return the first balanced {...} block in text, respecting string literals.

    Walks the string once tracking brace depth, but ignoring braces that appear
    inside JSON string literals (so braces inside "value" strings don't throw
    off the count). Returns None if no balanced object is found.
    """
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _parse_llm_json(raw_text: str) -> dict:
    """Parse an LLM response that *should* be JSON, tolerating common deviations.

    Tries (in order): plain json.loads, markdown fence extraction anywhere in
    the string, balanced brace-matching. Returns {} on total failure after
    logging a WARNING with the first 400 chars of the raw response.

    Callers expect a dict (possibly empty) -- this function never raises.
    """
    if not raw_text:
        return {}

    text = raw_text.strip()

    # (a) Fast path: plain JSON.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # (b) Markdown fence anywhere (not just leading). Handles:
    #     "Here is the JSON:\n```json\n{...}\n```\nLet me know if..."
    fence_match = re.search(r'```(?:json)?\s*(.+?)\s*```', text, re.DOTALL)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # (c) Balanced {...} via bracket matching (respects string literals).
    #     Handles preamble ("Here is the JSON you requested:\n{...}") and
    #     trailing commentary ("{...}\nLet me know if you need more.").
    candidate = _extract_balanced_json_object(text)
    if candidate is not None:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # (d) Give up. Log a generous snippet to aid diagnosis.
    logger.warning("Failed to parse JSON from LLM response: %.400s", raw_text)
    return {}


# ---------------------------------------------------------------------------
# PDF / image rendering
# ---------------------------------------------------------------------------

_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'}


def _render_pdf_pages(pdf_path: Path, dpi: int = 200, max_pages: int = 10) -> list[str]:
    """Render PDF pages to base64 JPEG strings via PyMuPDF."""
    import fitz

    # Anthropic vision API rejects images with any dimension > 8000px.
    _MAX_PIXEL_DIM = 8000

    images: list[str] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Downscale if over 8000px on any dimension (API limit)
            max_dim = max(pix.width, pix.height)
            if max_dim > _MAX_PIXEL_DIM:
                scale = _MAX_PIXEL_DIM / max_dim
                zoom = (dpi / 72) * scale
                logger.info(
                    "Downscaling %s page %d: %dx%d -> target max %dpx (scale %.3f)",
                    pdf_path.name, page_num + 1, pix.width, pix.height,
                    _MAX_PIXEL_DIM, scale,
                )
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

            img_bytes = pix.tobytes(output='jpeg', jpg_quality=85)

            # Downscale if over 4 MB
            if len(img_bytes) > 4 * 1024 * 1024:
                zoom = 150 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                if max(pix.width, pix.height) > _MAX_PIXEL_DIM:
                    scale = _MAX_PIXEL_DIM / max(pix.width, pix.height)
                    zoom = (150 / 72) * scale
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
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
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
    results: dict[str, dict] = {}
    ext = path.suffix.lower()

    all_text_lines: list[str] = []

    if ext == '.xlsx':
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(path), data_only=True)
        except Exception as exc:
            logger.warning("Cannot open Excel %s: %s", path.name, exc)
            return results
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            for row in ws.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c is not None]
                line = ' | '.join(c for c in cells if c)
                if line:
                    all_text_lines.append(line)
        wb.close()
    else:
        try:
            import xlrd
            wb = xlrd.open_workbook(str(path))
        except Exception as exc:
            logger.warning("Cannot open Excel %s: %s", path.name, exc)
            return results
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
# Text-based LLM extraction (shared by .msg, .docx, .doc)
# ---------------------------------------------------------------------------

def _extract_from_text_via_llm(
    text: str,
    concepts: dict[str, dict],
    template_patterns: dict[str, str] | None = None,
) -> tuple[dict[str, dict], dict]:
    """Send plain text to Anthropic for variable extraction. Returns (vars, usage)."""
    if not text.strip() or len(text) < 20:
        return {}, {}

    if len(text) > 15000:
        text = text[:15000] + '\n...[truncated]...'

    import anthropic

    variable_list = _build_variable_prompt(concepts, template_patterns)
    prompt = f"{_EXTRACTION_PROMPT.format(variable_list=variable_list)}\n\nDocument text:\n{text}"

    t0 = time.monotonic()
    try:
        from automation.llm_client import get_anthropic_client
        client = get_anthropic_client()
        response = client.messages.create(
            model=_active_model(),
            max_tokens=4096,
            messages=[{'role': 'user', 'content': prompt}],
            timeout=120.0,
        )
    except Exception as exc:
        logger.warning("LLM text extraction failed: %s", exc)
        return {}, {}
    elapsed = time.monotonic() - t0

    raw_text = response.content[0].text

    usage = {
        'input_tokens': response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'elapsed_s': round(elapsed, 2),
    }

    parsed = _parse_llm_json(raw_text)
    if not parsed:
        return {}, usage

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
# .msg extraction (email body via extract_msg)
# ---------------------------------------------------------------------------

def _extract_msg(
    path: Path, concepts: dict[str, dict],
    template_patterns: dict[str, str] | None = None,
) -> tuple[dict[str, dict], dict]:
    """Extract variables from .msg email file. Returns (vars, usage)."""
    try:
        import extract_msg
        msg = extract_msg.Message(str(path))
        body = msg.body or ''
        subject = msg.subject or ''
        sender = msg.sender or ''
        msg.close()
    except Exception as exc:
        logger.warning("Cannot read .msg file %s: %s", path.name, exc)
        return {}, {}

    text = f"Email subject: {subject}\nFrom: {sender}\n\nBody:\n{body}"
    return _extract_from_text_via_llm(text, concepts, template_patterns)


# ---------------------------------------------------------------------------
# .docx extraction (python-docx)
# ---------------------------------------------------------------------------

def _extract_docx(
    path: Path, concepts: dict[str, dict],
    template_patterns: dict[str, str] | None = None,
) -> tuple[dict[str, dict], dict]:
    """Extract variables from .docx file. Returns (vars, usage)."""
    try:
        import docx
        doc = docx.Document(str(path))
        parts: list[str] = []
        for p in doc.paragraphs:
            if p.text.strip():
                parts.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                parts.append(' | '.join(cell.text.strip() for cell in row.cells))
    except Exception as exc:
        logger.warning("Cannot read .docx file %s: %s", path.name, exc)
        return {}, {}

    text = '\n'.join(parts)
    return _extract_from_text_via_llm(text, concepts, template_patterns)


# ---------------------------------------------------------------------------
# .doc extraction (libreoffice conversion)
# ---------------------------------------------------------------------------

def _extract_doc(
    path: Path, concepts: dict[str, dict],
    template_patterns: dict[str, str] | None = None,
) -> tuple[dict[str, dict], dict]:
    """Extract variables from .doc file via libreoffice text conversion. Returns (vars, usage)."""
    import subprocess
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ['libreoffice', '--headless', '--convert-to', 'txt:Text',
                 '--outdir', tmpdir, str(path)],
                capture_output=True, timeout=30,
            )
            txt_file = Path(tmpdir) / (path.stem + '.txt')
            if not txt_file.exists():
                logger.warning("libreoffice conversion produced no output for %s", path.name)
                return {}, {}
            text = txt_file.read_text(errors='replace')
    except FileNotFoundError:
        logger.warning("libreoffice not found, cannot convert .doc: %s", path.name)
        return {}, {}
    except subprocess.TimeoutExpired:
        logger.warning("libreoffice conversion timed out for %s", path.name)
        return {}, {}

    return _extract_from_text_via_llm(text, concepts, template_patterns)


# ---------------------------------------------------------------------------
# Anthropic vision API
# ---------------------------------------------------------------------------

def _active_model() -> str:
    """Resolve model id. Precedence: CC_AGENTIC_MODEL env > llm_client default."""
    explicit = os.environ.get('CC_AGENTIC_MODEL')
    if explicit:
        return explicit
    from automation.llm_client import get_cc_model
    return get_cc_model()


# Legacy module constant — kept for any callers that import it directly.
# Do NOT rely on this at import time if you want env-var overrides to stick;
# call _active_model() instead (it reads env each call).
_MODEL = os.environ.get('CC_AGENTIC_MODEL', 'claude-sonnet-4-6')


def _call_vision(
    images_b64: list[str],
    prompt: str,
    *,
    max_tokens: int = 4096,
) -> tuple[dict, dict]:
    """Call Anthropic vision API. Returns (parsed_json, usage_dict)."""
    from automation.llm_client import get_anthropic_client

    client = get_anthropic_client()

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

    raw_text = response.content[0].text

    usage = {
        'input_tokens': response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'elapsed_s': round(elapsed, 2),
    }

    parsed = _parse_llm_json(raw_text)
    return parsed, usage


_EXTRACTION_PROMPT = """\
Extract geotechnical project data from this document. Target variables:

{variable_list}

IMPORTANT: Return ONLY a JSON object. No preamble, no markdown fences, no explanation.
Format: {{"variable_name": {{"value": <extracted>, "confidence": 0.0-1.0}}, ...}}
Omit variables not found. confidence: 1.0=clear, 0.7=uncertain, <0.5=guessing.
If the image contains no relevant document data (logos, legends, backgrounds), return: {{}}"""


def _extract_via_vision(
    images_b64: list[str],
    concepts: dict[str, dict],
    template_patterns: dict[str, str] | None = None,
) -> tuple[dict[str, dict], dict]:
    """Send images to Anthropic and parse variable extractions.

    Returns (variables_dict, usage).
    """
    variable_list = _build_variable_prompt(concepts, template_patterns)
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
    concepts_override: dict[str, dict] | None = None,
    template_patterns: dict[str, str] | None = None,
) -> tuple[dict, list[dict]]:
    """Extract report variables from a list of project files via Anthropic API.

    Args:
        files: List of dicts with keys: path (str), role (str), origin (str).
        concept_schema_path: Path to schemas/concepts/report_variables.yaml.
        agentic_crops: If True, re-read low-confidence variables at 300 DPI.
        max_crops_per_file: Max crop re-reads per file.
        crop_confidence_threshold: Variables below this trigger a crop re-read.
        concepts_override: If provided, use this concepts dict directly instead
            of loading from schema path. Used by targeted extraction to restrict
            the prompt to a subset of concepts (cheaper, more accurate).
        template_patterns: Optional {concept_id: pattern_hint} map. When a
            concept has a pattern, the model is told how Eva's template wraps
            the value so it can adapt the extracted facts into matching prose.
            Used for narrative concepts (location_sentence, adjacent_*_fmt,
            site_description, building_structure_desc). See
            `automation/concept_templates.py` for the curated registry.

    Returns:
        (variables_dict, actions_trace)
        variables_dict: {var_name: {value, confidence, source_file, source_origin, extraction_method}}
        actions_trace: [{action_id, type, file, ...}]
    """
    concepts = concepts_override if concepts_override is not None else load_concept_schema(concept_schema_path)
    merged: dict[str, dict] = {}
    trace: list[dict] = []
    total_usage = {'input_tokens': 0, 'output_tokens': 0, 'api_calls': 0}

    # Junk file patterns to skip (logos, inline images, backgrounds)
    _SKIP_PATTERNS = {'image001', 'image005', 'image006', 'image008', 'image009',
                      'image011', 'image012', 'pie egt', 'Thumbs'}
    _MIN_IMAGE_SIZE = 15_000  # Skip images < 15KB (logos, icons)

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

        # Skip junk files
        if any(pat in fpath.stem for pat in _SKIP_PATTERNS):
            trace.append({'action_id': f'skip_{fpath.name}', 'type': 'file_skip',
                          'file': str(fpath.name), 'reason': 'junk_pattern'})
            continue
        if fpath.suffix.lower() in _IMAGE_EXTENSIONS and fpath.stat().st_size < _MIN_IMAGE_SIZE:
            trace.append({'action_id': f'skip_{fpath.name}', 'type': 'file_skip',
                          'file': str(fpath.name), 'reason': 'too_small'})
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
        elif ext == '.msg':
            file_results, file_usage = _extract_msg(fpath, concepts, template_patterns)
            total_usage['input_tokens'] += file_usage.get('input_tokens', 0)
            total_usage['output_tokens'] += file_usage.get('output_tokens', 0)
            total_usage['api_calls'] += 1
            method = 'msg_parse'
        elif ext == '.docx':
            file_results, file_usage = _extract_docx(fpath, concepts, template_patterns)
            total_usage['input_tokens'] += file_usage.get('input_tokens', 0)
            total_usage['output_tokens'] += file_usage.get('output_tokens', 0)
            total_usage['api_calls'] += 1
            method = 'docx_parse'
        elif ext == '.doc':
            file_results, file_usage = _extract_doc(fpath, concepts, template_patterns)
            total_usage['input_tokens'] += file_usage.get('input_tokens', 0)
            total_usage['output_tokens'] += file_usage.get('output_tokens', 0)
            total_usage['api_calls'] += 1
            method = 'doc_convert'
        elif ext == '.pdf':
            images = _render_pdf_pages(fpath, dpi=200, max_pages=10)
            if images:
                file_results, file_usage = _extract_via_vision(images, concepts, template_patterns)
                total_usage['input_tokens'] += file_usage.get('input_tokens', 0)
                total_usage['output_tokens'] += file_usage.get('output_tokens', 0)
                total_usage['api_calls'] += 1
            method = 'vision_pdf'
        elif ext in _IMAGE_EXTENSIONS:
            images = _read_image_b64(fpath)
            if images:
                file_results, file_usage = _extract_via_vision(images, concepts, template_patterns)
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
