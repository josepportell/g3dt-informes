"""3-layer email attachment classifier.

Runs AFTER MsgMiner has extracted attachments into
`validation/msg_attachments/{email_subject}/{file}`.

Layer 1 (filename) — reuses `ROLE_PATTERNS` from SmartScan's tier1_filename but
                     ignores the scope constraint (attachments live 3 levels deep).
Layer 2 (vision)   — for unclassified images + single-page PDFs, asks a cheap
                     vision model (gpt-4.1-mini via OpenAI) to pick a document
                     category, then maps category→role.
Layer 3 (provenance) — every attachment ends up with a provenance entry in
                       FileMapping.email_attachments (even "other"), so the
                       diagnostic can surface unclassified files.

Empty-role promotion: attachments only take a role if the mapping has no
existing file for it. Existing roles are never overridden; candidates are
recorded in the provenance dict for auditing.
"""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path
from typing import Any

from .file_scanner import FileMapping, FileRole, get_vision_type
from .smartscan.tier1_filename import ROLE_PATTERNS as _TIER1_ROLE_PATTERNS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

ATTACHMENTS_SUBDIR = Path("validation") / "msg_attachments"

# File extensions processable by the vision layer
_VISION_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
_VISION_PDF_EXT = ".pdf"

# Min confidence values
CONFIDENCE_FILENAME = 0.9
CONFIDENCE_VISION = 0.7

# Vision category → role mapping
_CATEGORY_TO_ROLE: dict[str, str | None] = {
    "architect_plan": "architect_plan",
    "architect_project": "architect_project",
    "situation_plan": "situation_plan",
    "field_photo": "field_photo",
    "field_sheet": "dpsh_field_sheet",  # disambiguated below by filename
    "lab_cover": "gtl_report",
    "signature_image": None,
    "planning_chart": None,
    "other": None,
}

_VALID_CATEGORIES = set(_CATEGORY_TO_ROLE.keys())

_VISION_SYSTEM_PROMPT = (
    "You are a document type classifier for a geotechnical engineering firm."
)

_VISION_USER_PROMPT = (
    "Given this image, reply with exactly one of these categories:\n"
    "- architect_plan: architectural plan (floor plan, elevations, dimensioned drawings)\n"
    "- architect_project: multi-page architectural project (normativa + planol)\n"
    "- situation_plan: location/situation map\n"
    "- field_photo: photo of a construction site, terrain, or field work\n"
    "- field_sheet: handwritten field notes (DPSH, sondeig, penetrometer readings)\n"
    "- signature_image: company logo, email signature, or decorative image\n"
    "- lab_cover: laboratory report cover page\n"
    "- planning_chart: planning/normativa table or chart (no drawing)\n"
    "- other: anything else\n\n"
    "Reply with ONLY the category name, nothing else."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_email_attachments(
    project_path: Path,
    mapping: FileMapping,
    vision_client: Any | None = None,
) -> dict[str, dict]:
    """Classify every file under `validation/msg_attachments/*` and mutate mapping.

    Mutates ``mapping.roles`` in place: attachments matching an empty role
    slot are promoted; existing roles are NEVER overridden. Also writes
    `mapping.email_attachments[rel_path] = {...provenance...}` for every
    discovered attachment.

    Args:
        project_path: Absolute path to the project folder.
        mapping: The FileMapping to update.
        vision_client: Optional callable returning a category string for a
            given image path. When None, Layer 2 is skipped. Default: None.
            If set to the string "auto", uses the built-in OpenAI client.

    Returns:
        Provenance dict (same object as mapping.email_attachments).
    """
    att_root = project_path / ATTACHMENTS_SUBDIR
    if not att_root.is_dir():
        return mapping.email_attachments

    # When caller passes "auto" or True, use the built-in OpenAI client
    if vision_client == "auto" or vision_client is True:
        vision_client = _openai_category_probe

    # Enumerate all files under msg_attachments/, excluding our own mined_images
    attachments = _enumerate_attachments(att_root, project_path)
    logger.info(
        "email_attachment_classifier: %d attachments found in %s",
        len(attachments), project_path.name,
    )

    for att_path in attachments:
        rel_path = str(att_path.relative_to(project_path))
        source_msg = _source_msg_for(att_path, project_path)

        # Layer 1: filename
        role_match = _layer1_filename(att_path)
        if role_match is not None:
            role_name = role_match
            classifier_used = "filename"
            confidence = CONFIDENCE_FILENAME
            probe_status = "skipped"
            probe_detail = ""
        else:
            # Layer 2: vision (images + 1-page PDFs only; skip XLSX/DOCX/TXT)
            if vision_client is not None and _is_vision_eligible(att_path):
                category, probe_status, probe_detail = _layer2_vision(
                    att_path, vision_client,
                )
                role_name = _category_to_role(category, att_path)
                classifier_used = "vision" if probe_status == "ok" else "unclassified"
                confidence = CONFIDENCE_VISION if role_name else 0.0
            else:
                role_name = None
                classifier_used = "unclassified"
                confidence = 0.0
                probe_status = "skipped"
                probe_detail = (
                    "no_vision_client" if vision_client is None
                    else f"not_vision_eligible({att_path.suffix.lower()})"
                )

        # Layer 3: provenance + empty-role promotion
        promoted = False
        if role_name and role_name not in mapping.roles:
            mapping.roles[role_name] = FileRole(
                path=rel_path,
                confidence=_confidence_label(confidence),
                detection=f"email_attachment:{classifier_used}",
                vision_type=get_vision_type(role_name),
            )
            promoted = True
            logger.info(
                "email_attachment_classifier: promoted %s -> %s (via %s)",
                rel_path, role_name, classifier_used,
            )

        mapping.email_attachments[rel_path] = {
            "source_msg": source_msg,
            "classifier_used": classifier_used,
            "role_assigned": role_name if promoted else None,
            "role_candidate": role_name if (role_name and not promoted) else None,
            "probe_status": probe_status,
            "probe_detail": probe_detail,
            "confidence": round(confidence, 2),
            "concepts_extracted": [],
            "signals_emitted": 0,
        }

    return mapping.email_attachments


# ---------------------------------------------------------------------------
# Layer 1 — filename
# ---------------------------------------------------------------------------

def _layer1_filename(att_path: Path) -> str | None:
    """Match attachment filename against SmartScan ROLE_PATTERNS.

    Scope is ignored: attachments live deep under msg_attachments/, which is
    out of any normal project scope.
    """
    name = att_path.name
    is_dir = att_path.is_dir()
    for role_name, config in _TIER1_ROLE_PATTERNS.items():
        expects_dir = config.get("is_directory", False)
        if expects_dir != is_dir:
            continue
        for pattern in config.get("patterns", []):
            if re.match(pattern, name):
                return role_name
    return None


# ---------------------------------------------------------------------------
# Layer 2 — vision
# ---------------------------------------------------------------------------

def _is_vision_eligible(att_path: Path) -> bool:
    """Return True if the file is an image or a single-page PDF."""
    suffix = att_path.suffix.lower()
    if suffix in _VISION_IMAGE_EXTS:
        return True
    if suffix == _VISION_PDF_EXT:
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(att_path))
            pages = len(doc)
            doc.close()
            return pages == 1
        except Exception as exc:
            logger.debug("pdf page count failed for %s: %s", att_path.name, exc)
            return False
    return False


def _layer2_vision(
    att_path: Path, vision_client: Any,
) -> tuple[str | None, str, str]:
    """Run the vision probe and return (category, probe_status, probe_detail).

    probe_status is "ok" on a valid category reply, "failed" otherwise.
    category is the lowercased normalized category or None on failure.
    """
    try:
        category = vision_client(att_path)
    except Exception as exc:
        logger.warning("vision probe failed for %s: %s", att_path.name, exc)
        return None, "failed", f"exception: {exc}"

    if not category:
        return None, "failed", "empty_response"

    normalized = str(category).strip().lower()
    # Grab the first word/token in case the model over-answered
    token = re.split(r"[\s,;.]+", normalized, maxsplit=1)[0] if normalized else ""

    if token in _VALID_CATEGORIES:
        return token, "ok", token

    # Sometimes the model prefixes with "category:" or similar — try substring
    for cat in _VALID_CATEGORIES:
        if cat in normalized:
            return cat, "ok", f"fuzzy:{cat}"

    return None, "failed", f"unknown_category:{normalized[:40]}"


def _category_to_role(category: str | None, att_path: Path) -> str | None:
    """Map a vision category to a role, with filename hints for field_sheet."""
    if not category:
        return None
    role = _CATEGORY_TO_ROLE.get(category)
    if role == "dpsh_field_sheet":
        # Disambiguate field sheets by filename hint
        name_lower = att_path.name.lower()
        if "sondeig" in name_lower or "sondeo" in name_lower:
            return "sondeig_field_sheet"
    return role


# ---------------------------------------------------------------------------
# OpenAI built-in vision probe
# ---------------------------------------------------------------------------

def _openai_category_probe(att_path: Path) -> str | None:
    """Default vision client: calls OpenAI gpt-4.1-mini and returns a category.

    Mirrors the pattern in web.vision_groq._call_openai_vision. Returns the
    raw string reply or None on failure.
    """
    try:
        import httpx

        from . import config
        from .log_setup import log_vision_call
    except ImportError:
        logger.warning("openai_category_probe: httpx/config/log_setup not importable")
        return None

    api_key = config.OPENAI_API_KEY
    if not api_key:
        logger.warning("openai_category_probe: no OPENAI_API_KEY")
        return None

    images = _attachment_to_images(att_path)
    if not images:
        return None

    content: list[dict] = [{"type": "text", "text": _VISION_USER_PROMPT}]
    for b64 in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    payload = {
        "model": config.VISION_MODEL_OPENAI,
        "messages": [
            {"role": "system", "content": _VISION_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "temperature": 0.0,
        "max_tokens": 20,
    }

    import time as _time
    t0 = _time.monotonic()
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
        elapsed_ms = int((_time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            logger.warning(
                "openai_category_probe: HTTP %d %s",
                resp.status_code, resp.text[:200],
            )
            try:
                log_vision_call(
                    provider="openai", model=config.VISION_MODEL_OPENAI,
                    file_name=att_path.name, vtype="attachment_classify",
                    success=False, elapsed_ms=elapsed_ms,
                )
            except Exception:
                pass
            return None

        data = resp.json()
        reply = data["choices"][0]["message"]["content"]

        # Record usage via vision_groq accumulator so cost summaries include it
        try:
            from web.vision_groq import _record_openai_usage
            usage = data.get("usage", {})
            _record_openai_usage(
                config.VISION_MODEL_OPENAI,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
        except Exception:
            pass

        try:
            log_vision_call(
                provider="openai", model=config.VISION_MODEL_OPENAI,
                file_name=att_path.name, vtype="attachment_classify",
                success=True, elapsed_ms=elapsed_ms,
            )
        except Exception:
            pass
        return reply

    except (httpx.HTTPError, KeyError, IndexError) as exc:
        logger.warning("openai_category_probe: %s", exc)
        return None


def _attachment_to_images(att_path: Path) -> list[str]:
    """Convert an attachment (image or 1-page PDF) to base64 JPEG(s)."""
    suffix = att_path.suffix.lower()
    if suffix in _VISION_IMAGE_EXTS:
        return _image_to_b64(att_path)
    if suffix == _VISION_PDF_EXT:
        return _pdf_page1_to_b64(att_path)
    return []


def _image_to_b64(image_path: Path) -> list[str]:
    """Read image, convert to JPEG (base64). Adapted from web.vision_groq."""
    try:
        img_bytes = image_path.read_bytes()
        is_png = img_bytes[:4] == b"\x89PNG"
        is_large = len(img_bytes) > 4 * 1024 * 1024
        if is_png or is_large:
            try:
                import io
                from PIL import Image
                img = Image.open(io.BytesIO(img_bytes))
                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                if is_large:
                    img.thumbnail((2000, 2000))
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                img_bytes = buf.getvalue()
                img.close()
            except ImportError:
                logger.warning("Pillow missing for conversion: %s", image_path.name)
                return []
        return [base64.b64encode(img_bytes).decode("utf-8")]
    except Exception as exc:
        logger.warning("image read failed for %s: %s", image_path.name, exc)
        return []


def _pdf_page1_to_b64(pdf_path: Path) -> list[str]:
    """Render page 1 of a PDF as a base64 JPEG."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        try:
            page = doc[0]
            zoom = 200 / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes(output="jpeg", jpg_quality=85)
            if len(img_bytes) > 4 * 1024 * 1024:
                mat = fitz.Matrix(150 / 72, 150 / 72)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes(output="jpeg", jpg_quality=75)
            return [base64.b64encode(img_bytes).decode("utf-8")]
        finally:
            doc.close()
    except Exception as exc:
        logger.warning("pdf render failed for %s: %s", pdf_path.name, exc)
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enumerate_attachments(att_root: Path, project_path: Path) -> list[Path]:
    """List every file directly under each email-subject dir.

    Excludes nested `validation/mined_images/` subtrees (those are artifacts
    produced by FileMiner's PDF image extractor, not original attachments).
    """
    results: list[Path] = []
    for item in sorted(att_root.rglob("*")):
        if not item.is_file():
            continue
        rel_parts = item.relative_to(project_path).parts
        # Skip artifacts under validation/msg_attachments/*/validation/mined_images/
        if "mined_images" in rel_parts:
            continue
        if "validation" in rel_parts[3:]:  # nested validation/ inside subject dir
            continue
        results.append(item)
    return results


def _source_msg_for(att_path: Path, project_path: Path) -> str:
    """Return a best-effort relative pointer to the .msg that produced the file.

    MsgMiner saves attachments to `validation/msg_attachments/{msg.stem}/*`,
    so the directory name matches a .msg file stem somewhere in the project.
    """
    try:
        rel = att_path.relative_to(project_path)
    except ValueError:
        return str(att_path)
    # rel is validation/msg_attachments/{msg_stem}/...
    parts = rel.parts
    if len(parts) >= 3:
        msg_stem = parts[2]
        # Search project for matching .msg file
        for msg in project_path.rglob(f"{msg_stem}.msg"):
            try:
                return str(msg.relative_to(project_path))
            except ValueError:
                return str(msg)
        return f"{msg_stem}.msg (not found)"
    return str(rel)


def _confidence_label(confidence: float) -> str:
    """Map a numeric confidence to the string label used by FileRole."""
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"
