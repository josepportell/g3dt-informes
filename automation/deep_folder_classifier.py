"""Unified deep-folder file classifier.

Generalizes the email-attachment classifier to cover every file ConceptScout
discovered but FileScanner/SmartScan didn't role-assign. This includes
`validation/msg_attachments/` (email attachments) plus deep subdirectories
like `ANNEXES/ALTRES/`, `ANEXOS/OTROS/`, `FOTOGRAFIES/S1/`, etc.

Layers (in order):
  0. Probe-cache lookup — read cached doc_type from ConceptScout probes
                          (FREE, ~95% hit rate when ConceptScout has run)
  1. Filename match — SmartScan ROLE_PATTERNS (ignore scope)
  2. Vision probe — unprobed images + 1-page PDFs (CAPPED)
  3. Provenance entry — record verdict regardless

Empty-role promotion: files only take a role if `mapping.roles` has no
existing entry for it. Existing roles are NEVER overridden; the file is
recorded with a `role_candidate` instead.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
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

# Top-level directories that contain Eva's EXPORTED reports (not inputs).
# Files here must NEVER be promoted to input roles — they're outputs that
# duplicate inputs. ConceptScout walks them; we filter them out here.
_OUTPUT_DIR_PREFIXES = (
    "PDF/", "PDF-V0/", "PDF_V0/", "PDF V0/",
    "ACCEPTACIÓ/", "ACCEPTACIO/",
    "ACEPTACIÓN/", "ACEPTACION/", "ACEPTACIÓN CASTELLANO/",
)

# `validation/` subdirectories that hold ConceptScout/pipeline artifacts
# (not input files). `validation/msg_attachments/` is the one exception.
_VALIDATION_ARTIFACT_PREFIXES = (
    "validation/concept_probes/",
    "validation/mined_images/",
    "validation/logs/",
)

# Cap to prevent runaway OpenAI vision spend on pathological inputs.
# Each call ~$0.0007; 100 calls caps a single run at ~$0.07.
MAX_VISION_CALLS_PER_RUN: int = int(
    os.environ.get("G3DT_DEEP_CLASSIFIER_MAX_VISION", "100")
)

# File extensions processable by the vision layer
_VISION_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
_VISION_PDF_EXT = ".pdf"

# Confidence values for each layer
CONFIDENCE_PROBE_CACHE = 0.85
CONFIDENCE_FILENAME = 0.9
CONFIDENCE_VISION = 0.7

# Map ConceptScout vision-probe doc_type categories → FileMapping role names.
# Source: automation/concept_scout/vision_probe.py _PROBE_PROMPT categories.
# `None` means "doc_type alone is ambiguous — consult DOC_TYPE_DISAMBIGUATION
# or skip".
DOC_TYPE_TO_ROLE: dict[str, str | None] = {
    "architect_plan":    "architect_plan",
    "architect_project": "architect_project",
    "field_sheet":       None,  # ambiguous — disambiguate by filename/desc
    "site_photo":        "field_photo",
    "catalog":           None,  # vendor catalogs — no useful role
    "budget":            None,  # vendor budgets — no role (pressupost handled by FileScanner)
    "lab_report":        "gtl_report",
    "map":               None,  # ambiguous — disambiguate by description
    "email":             None,
    "other":             None,
}

# When doc_type alone is ambiguous, use description keywords (or filename) to
# refine. Checked in insertion order; first match wins.
DOC_TYPE_DISAMBIGUATION: dict[str, dict[str, str]] = {
    "map": {
        "aerial":       "field_photo",
        "topographic":  "figure_geological_map",
        "geologic":     "figure_geological_map",
        "geològic":     "figure_geological_map",
        "situation":    "situation_plan",
        "situació":     "situation_plan",
        "ubicació":     "situation_plan",
        "ubicacion":    "situation_plan",
    },
    "field_sheet": {
        "dpsh":      "dpsh_field_sheet",
        "penetro":   "dpsh_field_sheet",
        "sondeig":   "sondeig_field_sheet",
        "sondeo":    "sondeig_field_sheet",
        "spt":       "sondeig_field_sheet",
    },
}

# Our own Layer 2 vision prompt: split `field_sheet` into DPSH vs sondeig
# (W2 fix — previously a single `field_sheet` category collapsed both, and
# filename-only disambiguation misclassified generic image001.jpg uploads).
_CATEGORY_TO_ROLE: dict[str, str | None] = {
    "architect_plan":    "architect_plan",
    "architect_project": "architect_project",
    "situation_plan":    "situation_plan",
    "field_photo":       "field_photo",
    "dpsh_sheet":        "dpsh_field_sheet",
    "sondeig_sheet":     "sondeig_field_sheet",
    "lab_cover":         "gtl_report",
    "signature_image":   None,
    "planning_chart":    None,
    "other":             None,
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
    "- dpsh_sheet: handwritten penetrometer readings table (N20 cops/20cm columns)\n"
    "- sondeig_sheet: handwritten borehole log (soil layer descriptions + depths)\n"
    "- signature_image: company logo, email signature, or decorative image\n"
    "- lab_cover: laboratory report cover page\n"
    "- planning_chart: planning/normativa table or chart (no drawing)\n"
    "- other: anything else\n\n"
    "Reply with ONLY the category name, nothing else."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_unclassified_files(
    project_path: Path,
    mapping: FileMapping,
    concept_map_path: Path | None = None,
    probes_cache_dir: Path | None = None,
    vision_client: Any | None = None,
) -> dict[str, dict]:
    """Classify every file ConceptScout discovered that is NOT in mapping.roles.

    Layers apply in order: probe-cache → filename → vision → provenance.
    Empty `mapping.roles` slots may be promoted from any layer; filled slots
    get a `role_candidate` entry in provenance for auditing.

    Args:
        project_path: Absolute path to the project folder.
        mapping: The FileMapping to update (mutated in place).
        concept_map_path: Optional path to `validation/concept_map.json`.
            When provided, its `file_inventory` seeds the candidate set.
        probes_cache_dir: Optional path to `validation/concept_probes/`.
            When provided, cached ConceptScout probe results are read to
            shortcut the vision layer (Layer 0).
        vision_client: Optional callable (or "auto"/True) for Layer 2
            vision probes. When None, Layer 2 is skipped (filename-only).

    Returns:
        Provenance dict (same object as `mapping.deep_folder_files`) keyed
        by relative path. Each entry has: source_origin, classifier_used,
        role_assigned, role_candidate, probe_status, probe_detail,
        confidence, doc_type, concepts_extracted, signals_emitted.
    """
    # Normalize vision_client
    if vision_client == "auto" or vision_client is True:
        vision_client = _openai_category_probe

    # Default the probes cache dir to the conventional location
    if probes_cache_dir is None:
        default_cache = project_path / "validation" / "concept_probes"
        if default_cache.is_dir():
            probes_cache_dir = default_cache

    # Default concept_map to the conventional location
    if concept_map_path is None:
        default_cm = project_path / "validation" / "concept_map.json"
        if default_cm.is_file():
            concept_map_path = default_cm

    # Load concept_map once
    concept_map_data = None
    if concept_map_path and concept_map_path.is_file():
        try:
            concept_map_data = json.loads(
                concept_map_path.read_text(encoding="utf-8"),
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug(
                "concept_map load failed for %s: %s",
                project_path.name, exc,
            )

    candidates = _enumerate_candidates(project_path, mapping, concept_map_data)
    logger.info(
        "deep_folder_classifier: %d candidates in %s",
        len(candidates), project_path.name,
    )

    vision_calls_made = 0
    cap_warned = False
    for file_path in candidates:
        rel_path = str(file_path.relative_to(project_path))
        source_origin = _infer_source_origin(rel_path, project_path)

        # Layer 0: probe cache (ConceptScout already classified this file)
        probe_data = _layer0_probe_cache(file_path, probes_cache_dir)
        doc_type: str | None = None
        concepts_extracted: list[str] = []
        role_name: str | None = None
        classifier_used = "unclassified"
        confidence = 0.0
        probe_status = "skipped"
        probe_detail = ""

        if probe_data is not None:
            doc_type = probe_data.get("document_type") or "other"
            doc_desc = probe_data.get("document_description", "") or ""
            concepts_extracted = [
                c.get("concept_id", "")
                for c in probe_data.get("concepts_found", [])
                if isinstance(c, dict) and c.get("concept_id")
            ]
            mapped_role = _doc_type_to_role(doc_type, doc_desc, file_path)
            if mapped_role:
                role_name = mapped_role
                classifier_used = "probe_cache"
                confidence = CONFIDENCE_PROBE_CACHE
                probe_status = "ok"
                probe_detail = f"doc_type={doc_type}"
            # else: probe cache hit but no role mapping (e.g. doc_type="other"
            # or ambiguous with no disambiguation hit) — fall through to
            # Layer 1 filename as a best-effort recovery.

        # Layer 1: filename (when Layer 0 produced no role)
        if role_name is None:
            role_match = _layer1_filename(file_path)
            if role_match is not None:
                role_name = role_match
                classifier_used = "filename"
                confidence = CONFIDENCE_FILENAME
                probe_status = "skipped"
                probe_detail = ""
            elif vision_client is not None and _is_vision_eligible(file_path):
                # Layer 2: vision (capped). Skip if probe-cache already
                # gave us a vision-based answer — re-asking is wasteful.
                already_asked_vision = probe_data is not None
                if already_asked_vision:
                    probe_status = "skipped"
                    probe_detail = f"doc_type={doc_type or 'other'} unmapped"
                elif vision_calls_made >= MAX_VISION_CALLS_PER_RUN:
                    if not cap_warned:
                        logger.warning(
                            "deep_folder_classifier: MAX_VISION_CALLS_PER_RUN"
                            " (%d) reached in %s — later files skip vision",
                            MAX_VISION_CALLS_PER_RUN, project_path.name,
                        )
                        cap_warned = True
                    classifier_used = "unclassified"
                    probe_status = "skipped"
                    probe_detail = f"vision_cap_reached({MAX_VISION_CALLS_PER_RUN})"
                else:
                    category, probe_status, probe_detail = _layer2_vision(
                        file_path, vision_client,
                    )
                    role_name = _category_to_role(category)
                    classifier_used = (
                        "vision" if probe_status == "ok" else "unclassified"
                    )
                    confidence = CONFIDENCE_VISION if role_name else 0.0
                    vision_calls_made += 1
            elif probe_data is None:
                # No probe, no filename match, no vision — unclassified
                probe_status = "skipped"
                probe_detail = (
                    "no_vision_client" if vision_client is None
                    else f"not_vision_eligible({file_path.suffix.lower()})"
                )

        # Layer 3: provenance + empty-role promotion
        promoted = False
        if role_name and role_name not in mapping.roles:
            mapping.roles[role_name] = FileRole(
                path=rel_path,
                confidence=_confidence_label(confidence),
                detection=f"deep_folder:{classifier_used}",
                vision_type=get_vision_type(role_name),
            )
            promoted = True
            logger.info(
                "deep_folder_classifier: promoted %s -> %s (via %s)",
                rel_path, role_name, classifier_used,
            )

        mapping.deep_folder_files[rel_path] = {
            "source_origin": source_origin,
            "classifier_used": classifier_used,
            "role_assigned": role_name if promoted else None,
            "role_candidate": role_name if (role_name and not promoted) else None,
            "probe_status": probe_status,
            "probe_detail": probe_detail,
            "confidence": round(confidence, 2),
            "doc_type": doc_type,
            "concepts_extracted": concepts_extracted,
            "signals_emitted": 0,
        }

    return mapping.deep_folder_files


# Backward-compat wrapper — retained so older call sites still work while
# we migrate them. New code should call `classify_unclassified_files`.
def classify_email_attachments(
    project_path: Path,
    mapping: FileMapping,
    vision_client: Any | None = None,
) -> dict[str, dict]:
    """DEPRECATED — use classify_unclassified_files instead."""
    return classify_unclassified_files(
        project_path, mapping, vision_client=vision_client,
    )


# ---------------------------------------------------------------------------
# Candidate enumeration
# ---------------------------------------------------------------------------

def _enumerate_candidates(
    project_path: Path,
    mapping: FileMapping,
    concept_map_data: dict | None,
) -> list[Path]:
    """Collect every file that deserves classification.

    Sources (union):
      - concept_map.file_inventory — anything ConceptScout saw, not already
        role-assigned
      - validation/msg_attachments/ — always walked (in case ConceptScout
        wasn't run yet)

    Filters out Eva's exported reports (PDF/, PDF-V0/, etc.), validation/
    pipeline artifacts, and files already assigned to a role.
    """
    candidates: set[Path] = set()
    assigned_paths = {role.path for role in mapping.roles.values() if role.path}
    # Normalize ignored paths: strip trailing slashes, collect into a set
    ignored_paths = {
        ig.path.rstrip("/") for ig in mapping.ignored if ig.path
    }

    def _is_output_or_artifact(rel_path: str) -> bool:
        # Normalize: use forward slashes for cross-platform safety
        norm = rel_path.replace("\\", "/")
        for prefix in _OUTPUT_DIR_PREFIXES:
            if norm.startswith(prefix):
                return True
        for prefix in _VALIDATION_ARTIFACT_PREFIXES:
            if norm.startswith(prefix):
                return True
        return False

    # Source A: concept_map.file_inventory
    if concept_map_data:
        for entry in concept_map_data.get("file_inventory", []):
            path_str = entry.get("path", "") if isinstance(entry, dict) else ""
            if not path_str or path_str in assigned_paths:
                continue
            if path_str in ignored_paths:
                continue
            if _is_output_or_artifact(path_str):
                continue
            fp = project_path / path_str
            if not fp.is_file():
                continue
            candidates.add(fp)

    # Source B: msg_attachments/ (always walk, even without concept_map)
    att_root = project_path / ATTACHMENTS_SUBDIR
    if att_root.is_dir():
        for item in att_root.rglob("*"):
            if not item.is_file():
                continue
            try:
                rel_parts = item.relative_to(project_path).parts
            except ValueError:
                continue
            # Skip artifacts under validation/msg_attachments/*/validation/mined_images/
            if "mined_images" in rel_parts:
                continue
            if len(rel_parts) > 3 and "validation" in rel_parts[3:]:
                continue
            rel_str = str(item.relative_to(project_path))
            if rel_str in assigned_paths or rel_str in ignored_paths:
                continue
            candidates.add(item)

    return sorted(candidates)


def _infer_source_origin(rel_path: str, project_path: Path) -> str:
    """Return a short label describing where the file comes from."""
    parts = Path(rel_path).parts
    # msg_attachments case: validation/msg_attachments/{msg_stem}/...
    if len(parts) >= 3 and parts[0] == "validation" and parts[1] == "msg_attachments":
        msg_stem = parts[2]
        for msg in project_path.rglob(f"{msg_stem}.msg"):
            try:
                return f"msg:{msg.relative_to(project_path)}"
            except ValueError:
                return f"msg:{msg_stem}.msg"
        return f"msg:{msg_stem}.msg (not found)"
    # Deep folder: first 1-2 path components
    if len(parts) >= 2:
        return f"deep_folder:{parts[0]}/{parts[1]}"
    if parts:
        return f"deep_folder:{parts[0]}"
    return "unknown"


# ---------------------------------------------------------------------------
# Layer 0 — probe cache
# ---------------------------------------------------------------------------

def _layer0_probe_cache(
    file_path: Path,
    probes_dir: Path | None,
) -> dict | None:
    """Read cached ConceptScout probe result for file_path, if present."""
    if not probes_dir or not probes_dir.is_dir():
        return None
    try:
        stat = file_path.stat()
        raw = f"{file_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
        key = hashlib.md5(raw.encode()).hexdigest()[:12]
        cache_file = probes_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("probe cache read failed for %s: %s", file_path.name, exc)
        return None


def _doc_type_to_role(
    doc_type: str,
    doc_desc: str,
    file_path: Path,
) -> str | None:
    """Map ConceptScout's doc_type (+ description + filename) to a role."""
    # Ambiguous doc_types: check disambiguation keywords first
    if doc_type in DOC_TYPE_DISAMBIGUATION:
        desc_lower = (doc_desc or "").lower()
        name_lower = file_path.name.lower()
        for keyword, role in DOC_TYPE_DISAMBIGUATION[doc_type].items():
            if keyword in desc_lower or keyword in name_lower:
                return role
        # No disambiguation hit — fall through to base mapping (likely None)
    return DOC_TYPE_TO_ROLE.get(doc_type)


# ---------------------------------------------------------------------------
# Layer 1 — filename
# ---------------------------------------------------------------------------

def _layer1_filename(att_path: Path) -> str | None:
    """Match filename against SmartScan ROLE_PATTERNS (ignoring scope)."""
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
    """Image or 1-page PDF — things cheap enough to send to vision."""
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
            logger.debug(
                "pdf page count failed for %s: %s", att_path.name, exc,
            )
            return False
    return False


def _layer2_vision(
    att_path: Path, vision_client: Any,
) -> tuple[str | None, str, str]:
    """Run the vision probe; return (category, probe_status, probe_detail)."""
    try:
        category = vision_client(att_path)
    except Exception as exc:
        logger.warning("vision probe failed for %s: %s", att_path.name, exc)
        return None, "failed", f"exception: {exc}"

    if not category:
        return None, "failed", "empty_response"

    normalized = str(category).strip().lower()
    token = re.split(r"[\s,;.]+", normalized, maxsplit=1)[0] if normalized else ""

    if token in _VALID_CATEGORIES:
        return token, "ok", token

    # Model may have over-answered — try substring match as a fallback
    for cat in _VALID_CATEGORIES:
        if cat in normalized:
            return cat, "ok", f"fuzzy:{cat}"

    return None, "failed", f"unknown_category:{normalized[:40]}"


def _category_to_role(category: str | None) -> str | None:
    """Map Layer 2 vision category to a FileMapping role."""
    if not category:
        return None
    return _CATEGORY_TO_ROLE.get(category)


# ---------------------------------------------------------------------------
# OpenAI built-in vision probe
# ---------------------------------------------------------------------------

def _openai_category_probe(att_path: Path) -> str | None:
    """Default vision client: OpenAI gpt-4.1-mini, returns raw category string."""
    try:
        import httpx

        from . import config
        from .log_setup import log_vision_call
    except ImportError:
        logger.warning("openai_category_probe: httpx/config/log_setup missing")
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
                    file_name=att_path.name, vtype="deep_folder_classify",
                    success=False, elapsed_ms=elapsed_ms,
                )
            except Exception:
                pass
            return None

        data = resp.json()
        reply = data["choices"][0]["message"]["content"]

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
                file_name=att_path.name, vtype="deep_folder_classify",
                success=True, elapsed_ms=elapsed_ms,
            )
        except Exception:
            pass
        return reply

    except (httpx.HTTPError, KeyError, IndexError) as exc:
        logger.warning("openai_category_probe: %s", exc)
        return None


def _attachment_to_images(att_path: Path) -> list[str]:
    """Convert a file (image or 1-page PDF) to base64 JPEG(s)."""
    suffix = att_path.suffix.lower()
    if suffix in _VISION_IMAGE_EXTS:
        return _image_to_b64(att_path)
    if suffix == _VISION_PDF_EXT:
        return _pdf_page1_to_b64(att_path)
    return []


def _image_to_b64(image_path: Path) -> list[str]:
    """Read image, convert to JPEG (base64). Mirrors web.vision_groq helper."""
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

def _confidence_label(confidence: float) -> str:
    """Map numeric confidence to FileRole string label."""
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"
