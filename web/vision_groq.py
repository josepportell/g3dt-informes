"""
Groq Vision extraction: sends PDF pages as images to Llama 4 Scout
for structured data extraction. Runs in parallel, ~2-5s per PDF.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)

GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

_groq_status: dict[str, dict] = {}
_groq_lock = threading.Lock()


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
        }
        output_map = {
            "planol": "planol_extracted.json",
            "dpsh": "dpsh_extracted.json",
            "sondeig": "sondeig_extracted.json",
            "sondeig_annex": "sondeig_annex_extracted.json",
        }

        vision_tasks = {}
        seen_types: set[str] = set()
        for role_name, role in mapping.roles.items():
            vtype = role.vision_type
            if vtype and vtype in prompt_map and vtype not in seen_types:
                seen_types.add(vtype)
                output_path = project_path / "validation" / output_map[vtype]
                if not force and os.environ.get("G3DT_NO_CACHE") != "1" and output_path.exists():
                    _log_step(project_name, f"cache:{vtype}", "skipped (exists)")
                    continue
                vision_tasks[vtype] = {
                    "role": role_name,
                    "path": role.path,
                    "prompt": prompt_map[vtype],
                    "output": output_map[vtype],
                }

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
                images = _file_to_images(file_path)
                if not images:
                    return vtype, False, "no images from file"

                _log_step(
                    project_name,
                    f"render:{vtype}",
                    f"{len(images)} image(s) ({file_path.name})",
                )

                result = _call_groq_vision(prompt, images, EXTRACTION_SYSTEM_PROMPT)
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
    """Convert a file (PDF or image) to base64-encoded images for Groq vision.

    For PDFs: renders pages as JPEG via PyMuPDF.
    For images: reads directly and encodes as base64.

    Returns list of base64 strings.
    """
    ext = file_path.suffix.lower()

    if ext in _IMAGE_EXTENSIONS:
        return _read_image_as_b64(file_path)

    if ext == '.pdf':
        return _render_pdf_to_images(file_path, dpi, max_pages)

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
) -> dict | None:
    """Call Groq Vision API with images and extraction prompt.

    Returns parsed JSON dict or None on failure.
    """
    import httpx

    api_key = os.environ.get("GROQ_API_KEY")
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
        "model": GROQ_VISION_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
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


def _load_env():
    """Load .env file from project root if not already loaded."""
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())


def _call_openai_vision(
    extraction_prompt: str,
    images: list[str],
    system_prompt: str,
    max_retries: int = 2,
) -> dict | None:
    """Call OpenAI Vision API (gpt-4.1-mini) with images and extraction prompt.

    Uses the same OpenAI-compatible format as Groq. Returns parsed JSON dict or None.
    """
    import httpx

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OpenAI Vision: no API key")
        return None

    model = os.environ.get("OPENAI_VISION_MODEL", "gpt-4.1-mini")

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
        "max_tokens": 4096,
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
) -> dict | None:
    """Call Anthropic Claude API with images and extraction prompt.

    More capable than Groq for small text and complex layouts (~27x more expensive).
    Returns parsed JSON dict or None on failure.
    """
    _load_env()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("Anthropic Vision: no API key")
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning("Anthropic Vision: anthropic package not installed")
        return None

    content: list[dict] = []
    for b64_img in images:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_img},
        })
    content.append({"type": "text", "text": extraction_prompt})

    client = anthropic.Anthropic(api_key=api_key)
    t0 = time.monotonic()
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
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


def groq_available() -> bool:
    """Check if any vision API key is configured (Claude preferred, OpenAI/Groq fallback)."""
    _load_env()
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY"))


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

        if not force_refresh and os.environ.get("G3DT_NO_CACHE") != "1" and output_path.exists():
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
                        "claude" (claude-sonnet-4), or "groq" (fastest, cheapest).

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
    }
    output_map = {
        "planol": "planol_extracted.json",
        "dpsh": "dpsh_extracted.json",
        "sondeig": "sondeig_extracted.json",
        "sondeig_annex": "sondeig_annex_extracted.json",
    }

    # For planol vision_type, prefer architect_plan over architect_plan_with_points
    # (the "amb punts" version is Eva's annotated copy, often missing the normativa table)
    _PLANOL_ROLE_PRIORITY = [
        'architect_plan', 'architect_project', 'architect_plan_with_points',
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
        if not force_refresh and os.environ.get("G3DT_NO_CACHE") != "1" and output_path.exists():
            logger.info("vision_groq_sync cache:%s skipped (exists)", vtype)
            continue
        vision_tasks[vtype] = {
            "role": role_name,
            "path": role.path,
            "prompt": prompt_map[vtype],
            "output": output_map[vtype],
        }

    # Concept map fallback: when SmartScan has no role for a vision type,
    # check if concept_map.json identifies a file with relevant concepts
    _supplement_from_concept_map(vision_tasks, seen_types, prompt_map, output_map, project_path, force_refresh)

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
            images = _file_to_images(file_path)
            if not images:
                _emit(vtype, "error", message="no images from file")
                results[vtype] = {"success": False, "message": "no images from file"}
                continue

            logger.info(
                "vision_groq_sync render:%s %d image(s) (%s)",
                vtype, len(images), file_path.name,
            )

            # Vision backend chain: preferred → fallbacks
            result = None
            if vision_backend == "claude":
                result = _call_anthropic_vision(prompt, images, EXTRACTION_SYSTEM_PROMPT)
                if result is None:
                    result = _call_openai_vision(prompt, images, EXTRACTION_SYSTEM_PROMPT)
                if result is None:
                    result = _call_groq_vision(prompt, images, EXTRACTION_SYSTEM_PROMPT)
            elif vision_backend == "openai":
                result = _call_openai_vision(prompt, images, EXTRACTION_SYSTEM_PROMPT)
                if result is None:
                    result = _call_groq_vision(prompt, images, EXTRACTION_SYSTEM_PROMPT)
            else:  # groq
                result = _call_groq_vision(prompt, images, EXTRACTION_SYSTEM_PROMPT)
                if result is None:
                    result = _call_openai_vision(prompt, images, EXTRACTION_SYSTEM_PROMPT)
            if result is None:
                _emit(vtype, "error", message=f"API call failed (all backends)")
                results[vtype] = {"success": False, "message": f"API call failed ({vision_backend})"}
                continue

            output_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            _emit(vtype, "done")
            results[vtype] = {"success": True, "message": "ok"}
            logger.info("vision_groq_sync done:%s saved to %s", vtype, task_info["output"])

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
