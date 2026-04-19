"""
Groq Vision extraction: sends PDF pages as images to Llama 4 Scout
for structured data extraction. Runs in parallel, ~2-5s per PDF.
"""

from __future__ import annotations

import base64
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from automation import config
from automation.log_setup import log_vision_call

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

_groq_status: dict[str, dict] = {}
_groq_lock = threading.Lock()

# OpenAI vision usage accumulator (drained per diagnostic run).
# Tracks calls, tokens, and the model used so cost summaries can include
# OpenAI alongside Groq + Anthropic.
_OPENAI_USAGE: dict = {
    "api_calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "model": "",
}
_openai_usage_lock = threading.Lock()


def pop_openai_usage() -> dict:
    """Drain and return accumulated OpenAI vision usage since the last call."""
    with _openai_usage_lock:
        snapshot = dict(_OPENAI_USAGE)
        _OPENAI_USAGE["api_calls"] = 0
        _OPENAI_USAGE["input_tokens"] = 0
        _OPENAI_USAGE["output_tokens"] = 0
        _OPENAI_USAGE["model"] = ""
    return snapshot


def _record_openai_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    with _openai_usage_lock:
        _OPENAI_USAGE["api_calls"] += 1
        _OPENAI_USAGE["input_tokens"] += int(prompt_tokens or 0)
        _OPENAI_USAGE["output_tokens"] += int(completion_tokens or 0)
        if model:
            _OPENAI_USAGE["model"] = model


def start_vision_groq(
    project_name: str,
    project_path: Path,
    force: bool = False,
) -> dict:
    """Start Groq vision extraction. Returns immediately with status."""
    with _groq_lock:
        existing = _groq_status.get(project_name, {})
        if existing.get("status") == "running":
            return {"status": "already_running", "started": existing.get("start_time")}

        _groq_status[project_name] = {
            "status": "running",
            "start_time": time.time(),
            "tasks": {},
            "log": [],
        }

    thread = threading.Thread(
        target=_run_vision_groq,
        args=(project_name, project_path, force),
        daemon=True,
    )
    thread.start()
    return {"status": "started"}


def get_groq_vision_status(project_name: str) -> dict:
    """Get current status of Groq vision extraction."""
    with _groq_lock:
        return dict(_groq_status.get(project_name, {"status": "not_started"}))


def _log_step(project_name: str, step: str, note: str):
    start = _groq_status.get(project_name, {}).get("start_time", time.time())
    elapsed = time.time() - start
    with _groq_lock:
        if project_name in _groq_status:
            _groq_status[project_name]["log"].append(
                f"[{elapsed:.1f}s] {step}: {note}"
            )
    logger.info("vision_groq [%s] %s: %s (%.1fs)", project_name, step, note, elapsed)


def _run_vision_groq(project_name: str, project_path: Path, force: bool):
    """Background thread: render PDFs, send to Groq in parallel."""
    try:
        from automation.file_scanner import FileScanner
        from automation.validation.prompts import (
            DPSH_EXTRACTION_PROMPT,
            EXTRACTION_SYSTEM_PROMPT,
            PLANOL_EXTRACTION_PROMPT,
            PROJECTE_ARQUITECTE_EXTRACTION_PROMPT,
            SONDEIG_ANNEX_EXTRACTION_PROMPT,
            SONDEIG_EXTRACTION_PROMPT,
        )

        # Step 1: Load file mapping
        scanner = FileScanner(project_path)
        mapping = scanner.load()
        if not mapping:
            mapping = scanner.scan()
            scanner.save(mapping)
        _log_step(project_name, "file_mapping", "loaded")

        # Step 2: Identify vision tasks
        prompt_map = {
            "planol": PLANOL_EXTRACTION_PROMPT,
            "dpsh": DPSH_EXTRACTION_PROMPT,
            "sondeig": SONDEIG_EXTRACTION_PROMPT,
            "sondeig_annex": SONDEIG_ANNEX_EXTRACTION_PROMPT,
            "projecte_arquitecte": PROJECTE_ARQUITECTE_EXTRACTION_PROMPT,
        }
        output_map = {
            "planol": "planol_extracted.json",
            "dpsh": "dpsh_extracted.json",
            "sondeig": "sondeig_extracted.json",
            "sondeig_annex": "sondeig_annex_extracted.json",
            "projecte_arquitecte": "projecte_extracted.json",
        }

        vision_tasks = {}
        seen_types: set[str] = set()
        for role_name, role in mapping.roles.items():
            vtype = role.vision_type
            if vtype and vtype in prompt_map and vtype not in seen_types:
                seen_types.add(vtype)
                output_path = project_path / "validation" / output_map[vtype]
                if not force and not config.G3DT_NO_CACHE and output_path.exists():
                    _log_step(project_name, f"cache:{vtype}", "skipped (exists)")
                    continue
                vision_tasks[vtype] = {
                    "role": role_name,
                    "path": role.path,
                    "prompt": prompt_map[vtype],
                    "output": output_map[vtype],
                }

        # Upgrade: multi-page planol → also run as projecte_arquitecte
        if 'planol' in vision_tasks and 'projecte_arquitecte' not in seen_types:
            planol_file = project_path / vision_tasks['planol']['path']
            if planol_file.exists() and planol_file.suffix.lower() == '.pdf':
                try:
                    import fitz
                    doc = fitz.open(str(planol_file))
                    page_count = len(doc)
                    doc.close()
                    if page_count > 5:
                        pa_output = project_path / 'validation' / output_map['projecte_arquitecte']
                        if force or config.G3DT_NO_CACHE or not pa_output.exists():
                            vision_tasks['projecte_arquitecte'] = {
                                'role': f'upgraded_planol:{vision_tasks["planol"]["role"]}',
                                'path': vision_tasks['planol']['path'],
                                'prompt': prompt_map['projecte_arquitecte'],
                                'output': output_map['projecte_arquitecte'],
                            }
                            seen_types.add('projecte_arquitecte')
                except ImportError:
                    pass

        # Discover multi-page PDFs not assigned by SmartScan
        _discover_multipage_pdfs(vision_tasks, project_path, prompt_map, output_map, force)

        _log_step(project_name, "identify_tasks", f"{len(vision_tasks)} tasks")

        if not vision_tasks:
            _log_step(project_name, "complete", "all cached")
            with _groq_lock:
                _groq_status[project_name]["status"] = "completed"
                _groq_status[project_name]["elapsed"] = (
                    time.time() - _groq_status[project_name]["start_time"]
                )
            return

        # Step 3: Add DPSH Excel data if needed (for comparison)
        excel_context = ""
        if "dpsh" in vision_tasks:
            try:
                from automation.dpsh_extractor import DPSHExtractor

                excel_role = mapping.roles.get("dpsh_excel")
                if excel_role:
                    ext = DPSHExtractor(str(project_path / excel_role.path))
                    dpsh_data = ext.extract_all()
                    excel_context = (
                        "\n\nEXCEL COMPARISON DATA:\n"
                        + json.dumps(dpsh_data.to_dict(), indent=2, ensure_ascii=False)
                        + "\nCompare each N20 value you extract with the Excel values above."
                    )
            except Exception as e:
                _log_step(project_name, "excel_extract", f"error: {e}")

        # Step 4: Run all tasks in parallel
        (project_path / "validation").mkdir(exist_ok=True)

        def process_task(vtype: str, task_info: dict) -> tuple[str, bool, str]:
            file_path = project_path / task_info["path"]
            output_path = project_path / "validation" / task_info["output"]
            prompt = task_info["prompt"]

            if vtype == "dpsh" and excel_context:
                prompt = prompt + excel_context

            try:
                pages_limit = 50 if vtype == 'projecte_arquitecte' else 5
                images = _file_to_images(file_path, max_pages=pages_limit)
                if not images:
                    return vtype, False, "no images from file"

                _log_step(
                    project_name,
                    f"render:{vtype}",
                    f"{len(images)} image(s) ({file_path.name})",
                )

                tok_limit = 8192 if vtype == 'projecte_arquitecte' else 4096
                result = _call_groq_vision(prompt, images, EXTRACTION_SYSTEM_PROMPT, max_tokens=tok_limit)
                if result is None:
                    return vtype, False, "API call failed"

                output_path.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                _log_step(project_name, f"done:{vtype}", f"saved to {task_info['output']}")
                return vtype, True, "ok"

            except Exception as e:
                _log_step(project_name, f"error:{vtype}", str(e))
                return vtype, False, str(e)

        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(process_task, vtype, info): vtype
                for vtype, info in vision_tasks.items()
            }
            for future in as_completed(futures):
                vtype = futures[future]
                try:
                    vtype, success, msg = future.result()
                    results[vtype] = {"success": success, "message": msg}
                except Exception as e:
                    results[vtype] = {"success": False, "message": str(e)}

        elapsed = time.time() - _groq_status[project_name]["start_time"]
        ok_count = sum(1 for r in results.values() if r["success"])
        _log_step(project_name, "complete", f"{ok_count}/{len(results)} ok in {elapsed:.1f}s")

        with _groq_lock:
            _groq_status[project_name]["status"] = "completed"
            _groq_status[project_name]["elapsed"] = elapsed
            _groq_status[project_name]["tasks"] = results

    except Exception:
        logger.exception("vision_groq failed for %s", project_name)
        with _groq_lock:
            if project_name in _groq_status:
                _groq_status[project_name]["status"] = "error"


_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'}


def _file_to_images(
    file_path: Path, dpi: int = 200, max_pages: int = 5
) -> list[str]:
    """Convert a file (PDF or image) to base64-encoded images for vision API.

    For PDFs: renders pages as JPEG via PyMuPDF at full DPI (200 default).
    Large documents (>5 pages) are chunked at the caller level, not here.
    For images: reads directly and encodes as base64.

    Returns list of base64 strings.
    """
    ext = file_path.suffix.lower()

    if ext in _IMAGE_EXTENSIONS:
        return _read_image_as_b64(file_path)

    if ext == '.pdf':
        images = _render_pdf_to_images(file_path, dpi, max_pages)
        # Estimate decoded size from base64 length (avoids allocating decoded copies)
        total_size = sum(len(img) * 3 // 4 for img in images) if images else 0
        logger.info("Vision payload: %d images, %.1f MB total for %s",
                     len(images), total_size / (1024 * 1024), file_path.name)
        return images

    logger.warning("Unsupported file type for vision: %s", file_path.name)
    return []


def _read_image_as_b64(image_path: Path) -> list[str]:
    """Read an image file and return as single-element base64 JPEG list.

    Always converts to JPEG to match the hardcoded 'image/jpeg' media type
    in API calls. Handles .png files masquerading as .jpg and oversized images.
    """
    try:
        img_bytes = image_path.read_bytes()

        # Detect actual format and convert to JPEG if needed
        # (some .jpg files are actually PNGs — Anthropic API rejects mismatched media types)
        is_png = img_bytes[:4] == b'\x89PNG'
        is_too_large = len(img_bytes) > 4 * 1024 * 1024

        if is_png or is_too_large:
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
                if is_too_large:
                    logger.warning("Image too large and Pillow not available: %s", image_path.name)
                    return []
                # PNG without Pillow: can't convert, skip
                logger.warning("PNG image needs Pillow for JPEG conversion: %s", image_path.name)
                return []

        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return [b64]
    except Exception as e:
        logger.warning("Cannot read image %s: %s", image_path.name, e)
        return []


def _render_pdf_to_images(
    pdf_path: Path, dpi: int = 200, max_pages: int = 5
) -> list[str]:
    """Render PDF pages to base64 JPEG images.

    Returns list of base64-encoded JPEG strings.
    DPI 200 gives good quality while keeping under 4MB per image.
    """
    import fitz  # PyMuPDF

    images = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            img_bytes = pix.tobytes(output="jpeg", jpg_quality=85)

            # Check 4MB limit for Groq
            if len(img_bytes) > 4 * 1024 * 1024:
                zoom = 150 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes(output="jpeg", jpg_quality=75)

            b64 = base64.b64encode(img_bytes).decode("utf-8")
            images.append(b64)
            logger.debug("Rendered page %d: %d bytes", page_num + 1, len(img_bytes))
    finally:
        doc.close()

    return images


def _call_groq_vision(
    extraction_prompt: str,
    images: list[str],
    system_prompt: str,
    max_retries: int = 3,
    max_tokens: int = 4096,
) -> dict | None:
    """Call Groq Vision API with images and extraction prompt.

    Returns parsed JSON dict or None on failure.
    """
    import httpx

    api_key = config.GROQ_API_KEY
    if not api_key:
        logger.warning("Groq Vision: no API key")
        return None

    content: list[dict] = [{"type": "text", "text": extraction_prompt}]
    for b64_img in images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
            }
        )

    payload = {
        "model": config.VISION_MODEL_GROQ,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    for attempt in range(1, max_retries + 1):
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=60.0) as client:
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
                logger.warning(
                    "Groq Vision: rate limited (attempt %d/%d)", attempt, max_retries
                )
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                return None

            if resp.status_code != 200:
                logger.warning(
                    "Groq Vision: HTTP %d %s (attempt %d/%d)",
                    resp.status_code,
                    resp.text[:200],
                    attempt,
                    max_retries,
                )
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None

            data = resp.json()
            content_str = data["choices"][0]["message"]["content"]
            result = json.loads(content_str)

            usage = data.get("usage", {})
            logger.info(
                "Groq Vision: ok in %dms (%d in + %d out tokens)",
                elapsed_ms,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            return result

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning(
                "Groq Vision: %s (attempt %d/%d)", exc, attempt, max_retries
            )
            if attempt < max_retries:
                time.sleep(2)
                continue
            return None

    return None


def _call_openai_vision(
    extraction_prompt: str,
    images: list[str],
    system_prompt: str,
    max_retries: int = 2,
    max_tokens: int = 4096,
) -> dict | None:
    """Call OpenAI Vision API (gpt-4.1-mini) with images and extraction prompt.

    Uses the same OpenAI-compatible format as Groq. Returns parsed JSON dict or None.
    """
    import httpx

    api_key = config.OPENAI_API_KEY
    if not api_key:
        logger.warning("OpenAI Vision: no API key")
        return None

    model = config.VISION_MODEL_OPENAI

    content: list[dict] = [{"type": "text", "text": extraction_prompt}]
    for b64_img in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
        })

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    for attempt in range(1, max_retries + 1):
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            if resp.status_code == 429:
                logger.warning("OpenAI Vision: rate limited (attempt %d/%d)", attempt, max_retries)
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                return None

            if resp.status_code != 200:
                logger.warning("OpenAI Vision: HTTP %d %s", resp.status_code, resp.text[:200])
                return None

            data = resp.json()
            content_str = data["choices"][0]["message"]["content"]
            result = json.loads(content_str)

            usage = data.get("usage", {})
            _record_openai_usage(
                model,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            logger.info(
                "OpenAI Vision: ok in %dms (%d in + %d out tokens, model=%s)",
                elapsed_ms,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                model,
            )
            return result

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning("OpenAI Vision: %s (attempt %d/%d)", exc, attempt, max_retries)
            if attempt < max_retries:
                time.sleep(2)
                continue
            return None


def _call_anthropic_vision(
    extraction_prompt: str,
    images: list[str],
    system_prompt: str,
    max_tokens: int = 4096,
) -> dict | None:
    """Call Anthropic Claude API with images and extraction prompt.

    More capable than Groq for small text and complex layouts (~27x more expensive).
    Returns parsed JSON dict or None on failure.
    """
    try:
        from automation.llm_client import get_anthropic_client, get_cc_model
    except ImportError:
        logger.warning("Anthropic Vision: llm_client not importable")
        return None

    content: list[dict] = []
    for b64_img in images:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_img},
        })
    content.append({"type": "text", "text": extraction_prompt})

    try:
        client = get_anthropic_client()
    except RuntimeError as exc:
        logger.warning("Anthropic Vision: %s", exc)
        return None
    t0 = time.monotonic()
    try:
        response = client.messages.create(
            model=get_cc_model(),
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        text = response.content[0].text
        # Claude returns reasoning + JSON in markdown code block — extract the JSON
        if "```" in text:
            parts = text.split("```")
            for part in parts[1::2]:  # odd-indexed parts are inside code blocks
                cleaned = part.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                try:
                    result = json.loads(cleaned)
                    break
                except json.JSONDecodeError:
                    continue
            else:
                result = json.loads(text)  # fallback: try the whole thing
        else:
            result = json.loads(text)

        logger.info(
            "Anthropic Vision: ok in %dms (%d in + %d out tokens)",
            elapsed_ms,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return result

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("Anthropic Vision: %s (%dms)", exc, elapsed_ms)
        return None


def _extract_chunked(
    all_images: list[str],
    prompt: str,
    system_prompt: str,
    backend_chain: list[str],
    call_map: dict,
    max_tokens: int,
    chunk_size: int,
    file_name: str,
    vtype: str,
) -> dict | None:
    """Extract from a large PDF by splitting into chunks and merging results.

    Sends chunks of `chunk_size` pages each to the vision API, then merges
    all partial results into a single coherent extraction. Each chunk includes
    a note about which pages it contains so the LLM can report page numbers.

    This preserves full DPI quality while keeping payload under API limits.
    """
    chunks = []
    for i in range(0, len(all_images), chunk_size):
        chunks.append(all_images[i:i + chunk_size])

    logger.info(
        "Chunked extraction: %d pages -> %d chunks of %d for %s",
        len(all_images), len(chunks), chunk_size, file_name,
    )

    partial_results = []
    for chunk_idx, chunk_images in enumerate(chunks):
        page_start = chunk_idx * chunk_size + 1
        page_end = page_start + len(chunk_images) - 1
        chunk_prompt = (
            f"NOTE: You are seeing pages {page_start}-{page_end} of a {len(all_images)}-page document. "
            f"Report page numbers relative to the full document (first image = page {page_start}).\n\n"
            + prompt
        )

        result = None
        for backend_name in backend_chain:
            if not config.has_provider(backend_name):
                continue
            entry = call_map.get(backend_name)
            if not entry:
                continue
            call_fn, model_name = entry
            t_call = time.monotonic()
            result = call_fn(chunk_prompt, chunk_images, system_prompt, max_tokens=max_tokens)
            elapsed_ms = int((time.monotonic() - t_call) * 1000)
            log_vision_call(
                provider=backend_name,
                model=model_name,
                file_name=f"{file_name}[p{page_start}-{page_end}]",
                vtype=vtype,
                success=result is not None,
                elapsed_ms=elapsed_ms,
            )
            if result is not None:
                break

        if result:
            partial_results.append(result)
            logger.info("Chunk %d/%d (p%d-%d): ok", chunk_idx + 1, len(chunks), page_start, page_end)
        else:
            logger.warning("Chunk %d/%d (p%d-%d): failed", chunk_idx + 1, len(chunks), page_start, page_end)

        # Rate limit between chunks
        if chunk_idx < len(chunks) - 1:
            time.sleep(1)

    if not partial_results:
        return None

    # Merge: combine all partial extractions into one
    return _merge_chunk_results(partial_results)


def _merge_chunk_results(partials: list[dict]) -> dict:
    """Merge multiple chunk extraction results into a single result.

    Strategy: first non-null value wins for scalar fields.
    For pages_inventory and planning_table_raw, merge all entries.
    For dimensions, pick the value with highest confidence.
    """
    merged: dict = {
        "pages_inventory": {},
        "planning_table_raw": {},
        "architect_data": {},
        "dimensions": {},
        "overall_confidence": 0.0,
        "extraction_notes": "",
    }

    notes_parts = []

    for partial in partials:
        # pages_inventory: merge all
        for pg, desc in (partial.get("pages_inventory") or {}).items():
            if pg not in merged["pages_inventory"]:
                merged["pages_inventory"][pg] = desc

        # planning_table_raw: prefer the most complete version
        pt = partial.get("planning_table_raw") or {}
        if pt:
            existing = merged["planning_table_raw"]
            for col in ("planejament", "projecte"):
                existing_col = existing.get(col) or {}
                new_col = pt.get(col) or {}
                if len(new_col) > len(existing_col):
                    existing[col] = new_col

        # architect_data: first non-null value wins
        for key, val in (partial.get("architect_data") or {}).items():
            if val and not merged["architect_data"].get(key):
                merged["architect_data"][key] = val

        # dimensions: highest confidence wins
        for key, val in (partial.get("dimensions") or {}).items():
            if val is None:
                continue
            existing = merged["dimensions"].get(key)
            if isinstance(val, dict):
                new_conf = val.get("confidence", 0) or 0
                old_conf = (existing.get("confidence", 0) or 0) if isinstance(existing, dict) else 0
                if new_conf > old_conf:
                    merged["dimensions"][key] = val
            elif isinstance(val, list):
                # floor_surfaces: merge, dedup by floor name
                if not existing or (isinstance(existing, list) and len(val) > len(existing)):
                    merged["dimensions"][key] = val
            elif existing is None:
                merged["dimensions"][key] = val

        # overall_confidence: take max
        conf = partial.get("overall_confidence", 0) or 0
        if conf > merged["overall_confidence"]:
            merged["overall_confidence"] = conf

        # notes
        note = partial.get("extraction_notes", "")
        if note:
            notes_parts.append(note)

    merged["extraction_notes"] = " | ".join(notes_parts) if notes_parts else ""
    return merged


def groq_available() -> bool:
    """Check if any vision API key is configured."""
    return bool(config.available_vision_backends())


def _supplement_from_concept_map(
    vision_tasks: dict, seen_types: set, prompt_map: dict,
    output_map: dict, project_path: Path, force_refresh: bool,
) -> None:
    """Add vision tasks from concept_map.json when SmartScan missed files."""
    concept_map_path = project_path / 'validation' / 'concept_map.json'
    if not concept_map_path.exists():
        return

    try:
        concept_map = json.loads(concept_map_path.read_text(encoding='utf-8'))
    except Exception:
        logger.warning("Failed to load concept_map.json for vision fallback")
        return

    concept_sources = concept_map.get('concept_sources', {})

    # Map vision types to the concepts they extract
    VISION_TYPE_CONCEPTS = {
        'planol': {'architect_name', 'architect_company', 'client_name', 'building_type',
                   'num_floors', 'building_height_m', 'superficie_construida_m2',
                   'superficie_parcela_m2', 'street_address', 'municipality'},
        'sondeig_annex': {'num_soil_levels', 'cota_referencia'},
        'projecte_arquitecte': {'architect_name', 'architect_company', 'client_name', 'building_type',
                                'num_floors', 'building_height_m', 'superficie_construida_m2',
                                'superficie_parcela_m2', 'street_address', 'municipality'},
    }

    for vtype, concepts in VISION_TYPE_CONCEPTS.items():
        if vtype in seen_types:
            continue  # SmartScan already assigned a file for this type
        if vtype not in prompt_map:
            continue

        # Find the best file from concept_map that contains these concepts
        file_scores: dict[str, float] = {}
        for cid in concepts:
            for src in concept_sources.get(cid, []):
                f = src.get('file', '')
                # Only consider files that are visually processable (PDF, image)
                if f.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                    file_scores[f] = file_scores.get(f, 0) + src.get('confidence', 0.5)

        if not file_scores:
            continue

        # Pick the file with highest aggregate score
        best_file = max(file_scores, key=file_scores.get)
        output_path = project_path / 'validation' / output_map[vtype]

        if not force_refresh and not config.G3DT_NO_CACHE and output_path.exists():
            logger.info("concept_map fallback cache:%s skipped (exists)", vtype)
            continue

        vision_tasks[vtype] = {
            'role': f'concept_map_fallback:{vtype}',
            'path': best_file,
            'prompt': prompt_map[vtype],
            'output': output_map[vtype],
        }
        seen_types.add(vtype)
        logger.info("concept_map fallback: %s -> %s (score=%.1f)", vtype, best_file, file_scores[best_file])


def _discover_multipage_pdfs(
    vision_tasks: dict, project_path: Path, prompt_map: dict, output_map: dict,
    force_refresh: bool,
) -> None:
    """Discover multi-page PDFs that may contain architect project data.

    Uses PDF metadata (creator=AutoCAD, pages>3) to find rich documents
    that SmartScan may have missed or misclassified.
    """
    vtype = 'projecte_arquitecte'
    if vtype in vision_tasks:
        return  # already assigned
    if vtype not in prompt_map:
        return

    output_path = project_path / 'validation' / output_map[vtype]
    if not force_refresh and not config.G3DT_NO_CACHE and output_path.exists():
        return

    # Collect files already assigned to vision tasks
    assigned_files = set()
    for task_info in vision_tasks.values():
        assigned_files.add(task_info['path'])

    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF not available for multipage PDF discovery")
        return

    best_candidate = None
    best_score = 0

    # Directories containing G3DT's own generated reports — never architect projects
    _SKIP_DIRS = {'pdf', 'pdf-v0', 'pdf_v0', 'lletra', 'letra', 'annexes',
                  'anejos', 'fotografies', 'fotografías', 'validation'}

    # Scan all PDFs in project (recursively)
    for pdf_path in sorted(project_path.rglob('*.pdf')):
        rel_path = str(pdf_path.relative_to(project_path))

        # Skip already assigned files
        if rel_path in assigned_files:
            continue
        # Skip G3DT output directories and validation
        rel_parts = pdf_path.relative_to(project_path).parts[:-1]  # directory components
        if any(part.lower() in _SKIP_DIRS for part in rel_parts):
            continue

        try:
            doc = fitz.open(str(pdf_path))
            pages = len(doc)
            meta = doc.metadata or {}
            creator = (meta.get('creator') or '').lower()
            doc.close()
        except Exception:
            continue

        # Skip small PDFs (likely single-page plans or forms)
        if pages < 4:
            continue

        # Score based on indicators
        score = 0
        # CAD-exported PDFs are likely architect projects
        if any(kw in creator for kw in ('autocad', 'revit', 'archicad', 'dwg')):
            score += 5
        # Word-generated PDFs are G3DT's own reports, not architect documents
        if any(kw in creator for kw in ('word', 'writer', 'pdfmaker')):
            score -= 5
        # Multi-page bonus
        score += min(pages, 20) * 0.2
        # File size bonus (larger = more content)
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if size_mb > 2:
            score += 2
        # Name hints
        name_lower = pdf_path.name.lower()
        if any(kw in name_lower for kw in ('plano', 'proyecto', 'projecte', 'dg_', 'basico', 'executiu')):
            score += 3
        # Negative name hints (G3DT reports, budgets)
        if any(kw in name_lower for kw in ('informe', 'pressupost', 'presupuesto', 'acceptacio', 'aceptacion')):
            score -= 3

        if score > best_score:
            best_score = score
            best_candidate = rel_path

    if best_candidate and best_score >= 3:
        vision_tasks[vtype] = {
            'role': 'discovered:projecte_arquitecte',
            'path': best_candidate,
            'prompt': prompt_map[vtype],
            'output': output_map[vtype],
        }
        logger.info("discovered multipage PDF: %s -> %s (score=%.1f)", vtype, best_candidate, best_score)


def run_vision_groq_sync(
    project_path: Path,
    *,
    force_refresh: bool = False,
    on_progress: callable | None = None,
    vision_backend: str = "openai",
) -> dict[str, dict]:
    """Run vision extraction synchronously (blocking).

    Args:
        vision_backend: "openai" (default, gpt-4.1-mini — best accuracy/cost),
                        "claude" (claude-sonnet-4-6), or "groq" (fastest, cheapest).

    Same logic as _run_vision_groq() but runs inline (not threaded) and
    emits progress via on_progress callback instead of _groq_status dict.

    on_progress signature: (event_type: str, detail: dict) -> None
    Events emitted: ('vision', {'step': vtype, 'status': 'active'|'done'|'error', 'message': ...})
    """
    def _emit(step: str, status: str, message: str = ""):
        if on_progress:
            detail = {"step": step, "status": status}
            if message:
                detail["message"] = message
            on_progress("vision", detail)

    from automation.file_scanner import FileScanner
    from automation.validation.prompts import (
        DPSH_EXTRACTION_PROMPT,
        EXTRACTION_SYSTEM_PROMPT,
        PLANOL_EXTRACTION_PROMPT,
        PROJECTE_ARQUITECTE_EXTRACTION_PROMPT,
        SONDEIG_ANNEX_EXTRACTION_PROMPT,
        SONDEIG_EXTRACTION_PROMPT,
    )

    # Step 1: Load file mapping
    scanner = FileScanner(project_path)
    mapping = scanner.load()
    if not mapping:
        mapping = scanner.scan()
        scanner.save(mapping)

    # Step 2: Identify vision tasks
    prompt_map = {
        "planol": PLANOL_EXTRACTION_PROMPT,
        "dpsh": DPSH_EXTRACTION_PROMPT,
        "sondeig": SONDEIG_EXTRACTION_PROMPT,
        "sondeig_annex": SONDEIG_ANNEX_EXTRACTION_PROMPT,
        "projecte_arquitecte": PROJECTE_ARQUITECTE_EXTRACTION_PROMPT,
    }
    output_map = {
        "planol": "planol_extracted.json",
        "dpsh": "dpsh_extracted.json",
        "sondeig": "sondeig_extracted.json",
        "sondeig_annex": "sondeig_annex_extracted.json",
        "projecte_arquitecte": "projecte_extracted.json",
    }

    # For planol vision_type, prefer architect_plan over architect_plan_with_points
    # (the "amb punts" version is Eva's annotated copy, often missing the normativa table)
    _PLANOL_ROLE_PRIORITY = [
        'architect_plan', 'architect_plan_with_points',
        'situation_plan', 'field_croquis',
    ]

    vision_tasks = {}
    seen_types: set[str] = set()

    # First pass: collect all candidates per vision_type
    candidates: dict[str, list[tuple[str, Any]]] = {}
    for role_name, role in mapping.roles.items():
        vtype = role.vision_type
        if vtype and vtype in prompt_map:
            candidates.setdefault(vtype, []).append((role_name, role))

    # Second pass: pick best candidate per vision_type
    for vtype, cands in candidates.items():
        if vtype == 'planol' and len(cands) > 1:
            # Sort by priority order
            cands.sort(key=lambda x: (
                _PLANOL_ROLE_PRIORITY.index(x[0]) if x[0] in _PLANOL_ROLE_PRIORITY else 99
            ))
        role_name, role = cands[0]
        seen_types.add(vtype)
        output_path = project_path / "validation" / output_map[vtype]
        if not force_refresh and not config.G3DT_NO_CACHE and output_path.exists():
            logger.info("vision_groq_sync cache:%s skipped (exists)", vtype)
            continue
        vision_tasks[vtype] = {
            "role": role_name,
            "path": role.path,
            "prompt": prompt_map[vtype],
            "output": output_map[vtype],
        }

    # Upgrade: if planol candidate is a multi-page PDF (>5 pages), also run as
    # projecte_arquitecte — the planol prompt only reads 5 pages and misses
    # normativa tables, area breakdowns, and sections on later pages.
    if 'planol' in vision_tasks and 'projecte_arquitecte' not in seen_types:
        planol_file = project_path / vision_tasks['planol']['path']
        if planol_file.exists() and planol_file.suffix.lower() == '.pdf':
            try:
                import fitz
                doc = fitz.open(str(planol_file))
                page_count = len(doc)
                doc.close()
                if page_count > 5:
                    pa_output = project_path / 'validation' / output_map['projecte_arquitecte']
                    if force_refresh or config.G3DT_NO_CACHE or not pa_output.exists():
                        vision_tasks['projecte_arquitecte'] = {
                            'role': f'upgraded_planol:{vision_tasks["planol"]["role"]}',
                            'path': vision_tasks['planol']['path'],
                            'prompt': prompt_map['projecte_arquitecte'],
                            'output': output_map['projecte_arquitecte'],
                        }
                        seen_types.add('projecte_arquitecte')
                        logger.info(
                            "Upgraded planol to also run as projecte_arquitecte (%d pages): %s",
                            page_count, vision_tasks['planol']['path'],
                        )
            except ImportError:
                pass

    # Concept map fallback: when SmartScan has no role for a vision type,
    # check if concept_map.json identifies a file with relevant concepts
    _supplement_from_concept_map(vision_tasks, seen_types, prompt_map, output_map, project_path, force_refresh)

    # Discover multi-page PDFs not assigned by SmartScan
    _discover_multipage_pdfs(vision_tasks, project_path, prompt_map, output_map, force_refresh)

    logger.info("vision_groq_sync: %d tasks identified", len(vision_tasks))

    if not vision_tasks:
        return {}

    # Step 3: Add DPSH Excel data if needed (for comparison)
    excel_context = ""
    if "dpsh" in vision_tasks:
        try:
            from automation.dpsh_extractor import DPSHExtractor

            excel_role = mapping.roles.get("dpsh_excel")
            if excel_role:
                ext = DPSHExtractor(str(project_path / excel_role.path))
                dpsh_data = ext.extract_all()
                excel_context = (
                    "\n\nEXCEL COMPARISON DATA:\n"
                    + json.dumps(dpsh_data.to_dict(), indent=2, ensure_ascii=False)
                    + "\nCompare each N20 value you extract with the Excel values above."
                )
        except Exception as e:
            logger.warning("vision_groq_sync excel_extract error: %s", e)

    # Step 4: Run tasks sequentially (better for progress tracking and rate limits)
    (project_path / "validation").mkdir(exist_ok=True)
    results: dict[str, dict] = {}

    for vtype, task_info in vision_tasks.items():
        file_path = project_path / task_info["path"]
        output_path = project_path / "validation" / task_info["output"]
        prompt = task_info["prompt"]

        if vtype == "dpsh" and excel_context:
            prompt = prompt + excel_context

        _emit(vtype, "active")

        try:
            pages_limit = 50 if vtype == 'projecte_arquitecte' else 5
            images = _file_to_images(file_path, max_pages=pages_limit)
            if not images:
                _emit(vtype, "error", message="no images from file")
                results[vtype] = {"success": False, "message": "no images from file"}
                continue

            logger.info(
                "vision_groq_sync render:%s %d image(s) (%s)",
                vtype, len(images), file_path.name,
            )

            # Vision backend chain: preferred → fallbacks
            _CALL_MAP = {
                "openai": (_call_openai_vision, config.VISION_MODEL_OPENAI),
                "anthropic": (_call_anthropic_vision, config.VISION_MODEL_ANTHROPIC),
                "groq": (_call_groq_vision, config.VISION_MODEL_GROQ),
            }
            # Per-vision-type backend override. Falls back to run-level vision_backend if no map entry.
            type_pref = config.VISION_BACKEND_BY_TYPE.get(vtype, vision_backend)
            # "claude" is a backward-compatible synonym for "anthropic"
            preferred = "anthropic" if type_pref == "claude" else type_pref
            chain = [preferred]
            for fb in config.VISION_FALLBACK_ORDER:
                if fb not in chain:
                    chain.append(fb)
            if type_pref != vision_backend:
                logger.info("vision_groq_sync per-type:%s using %s (run default: %s)", vtype, type_pref, vision_backend)

            tok_limit = 8192 if vtype == 'projecte_arquitecte' else 4096

            # Chunked extraction for large documents: split into batches of
            # CHUNK_SIZE pages, extract each batch, then merge results.
            # Keeps payload under API limits while maintaining full DPI quality.
            CHUNK_SIZE = 5
            if vtype == 'projecte_arquitecte' and len(images) > CHUNK_SIZE:
                result = _extract_chunked(
                    images, prompt, EXTRACTION_SYSTEM_PROMPT,
                    chain, _CALL_MAP, tok_limit, CHUNK_SIZE,
                    file_path.name, vtype,
                )
                used_backend = "chunked"
            else:
                result = None
                used_backend = None
                for backend_name in chain:
                    if not config.has_provider(backend_name):
                        continue
                    entry = _CALL_MAP.get(backend_name)
                    if not entry:
                        continue
                    call_fn, model_name = entry
                    t_call = time.monotonic()
                    result = call_fn(prompt, images, EXTRACTION_SYSTEM_PROMPT, max_tokens=tok_limit)
                    elapsed_call_ms = int((time.monotonic() - t_call) * 1000)
                    log_vision_call(
                        provider=backend_name,
                        model=model_name,
                        file_name=file_path.name,
                        vtype=vtype,
                        success=result is not None,
                        elapsed_ms=elapsed_call_ms,
                    )
                    if result is not None:
                        used_backend = backend_name
                        break

            if result is None:
                _emit(vtype, "error", message="API call failed (all backends)")
                results[vtype] = {"success": False, "message": f"API call failed ({vision_backend})"}
                continue

            output_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            _emit(vtype, "done")
            results[vtype] = {"success": True, "message": "ok"}
            logger.info("vision_groq_sync done:%s saved to %s (backend=%s)", vtype, task_info["output"], used_backend)

        except Exception as e:
            _emit(vtype, "error", message=str(e))
            results[vtype] = {"success": False, "message": str(e)}
            logger.warning("vision_groq_sync error:%s %s", vtype, e)

        # Rate limit: 1s between API calls
        time.sleep(1)

    # Step 5: Run Python docs extraction if available (no API call)
    try:
        from .vision_fast import _extract_docs_python
        _extract_docs_python(project_path, mapping.roles, force_refresh)
        logger.info("vision_groq_sync: docs_extracted.json done (Python regex)")
    except ImportError:
        pass
    except Exception as e:
        logger.warning("vision_groq_sync: docs extraction failed: %s", e)

    return results
