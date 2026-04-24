"""Stage 2: typology — classify each file by technical type, extract embedded images.

Consumes the Stage 1 inventory and produces a ProjectTypology:
- FileClass per file (category, useful flag, conversion strategy, structural metadata)
- FolderClass per folder (roll-up, dev-only flag)
- Extracted images become their own FileClass entries under validation/ai_pipeline/extracted/

Design doc: docs/ARQUITECTURA-AI-PIPELINE.md §5
"""

from __future__ import annotations

import hashlib
import logging
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .inventory import Inventory, InventoryFile, build_inventory

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────

# Top-level folders whose contents are Eva's prior deliverables and won't exist
# in a new production project. Hard-coded for now (single-client scope).
# ACCEPTACIO is NOT included — it's the invoice-signing folder (client inputs).
DEV_ONLY_TOPLEVEL_DIRS: frozenset[str] = frozenset({"PDF", "PDF V0", "PDF-V0"})

# Image extraction thresholds — aligned with msg_miner._MIN_ATTACHMENT_BYTES.
MIN_IMAGE_BYTES: int = 5_000
MIN_IMAGE_DIM: int = 32  # pixels, each side

# Sidecar directory where Stage 2 writes extracted images.
_EXTRACTED_ROOT = Path("validation") / "ai_pipeline" / "extracted"


# ─── Models ────────────────────────────────────────────────────────────


class FileClass(BaseModel):
    """Per-file typology record. Primary ID is `path`."""

    path: str                    # relative POSIX, unique within project
    format: str                  # normalized extension: pdf, xlsx, docx, msg, jpg, …
    category: str                # typology bucket (see §5.4 of arch doc)

    # Structural introspection (deterministic Python)
    has_text: bool = False
    has_images: bool = False
    image_count: int = 0
    page_count: int = 0
    sheet_count: int = 0
    sheet_names: list[str] = Field(default_factory=list)

    # Provenance
    source_chain: list[str] = Field(default_factory=list)
    is_attachment: bool = False
    parent_path: str | None = None

    # Stage 3 guidance
    useful: bool = True
    reason: str = ""
    conversion_strategy: str = ""

    # Artifacts
    extracted_images_dir: str | None = None


class FolderClass(BaseModel):
    """Per-folder roll-up. `path=""` for root, `parent=None` only for root."""

    path: str
    parent: str | None
    file_count: int                               # direct files, non-recursive
    useful_count: int
    category_counts: dict[str, int] = Field(default_factory=dict)
    is_dev_only: bool = False


class ProjectTypology(BaseModel):
    """Stage 2 output: full typology of a project + query helpers."""

    project_path: str
    classified_at: str                            # ISO 8601 UTC
    files: list[FileClass] = Field(default_factory=list)
    folders: list[FolderClass] = Field(default_factory=list)
    counts_by_category: dict[str, int] = Field(default_factory=dict)
    useful_count: int = 0
    skipped_count: int = 0
    eva_summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # ── Query helpers ─────────────────────────────────────────────────

    def children_of(self, parent_path: str) -> list[FileClass]:
        """Files extracted from `parent_path` (e.g. images pulled from a PDF)."""
        return [f for f in self.files if f.parent_path == parent_path]

    def subfolders_of(self, parent_path: str) -> list[FolderClass]:
        """Immediate subfolders of `parent_path`. `parent_path=""` for root.

        Root itself (parent=None) is never returned — subfolders of root are the
        entries whose parent equals the empty string "" (i.e., top-level dirs).
        """
        norm = parent_path.strip("/")
        return [f for f in self.folders if f.parent == norm]

    def folder_tree(self) -> dict[str, list[str]]:
        """Adjacency list of the folder tree. Key is parent path ('' for root)."""
        tree: dict[str, list[str]] = {}
        for f in self.folders:
            key = "" if f.parent is None else f.parent
            tree.setdefault(key, []).append(f.path)
        for children in tree.values():
            children.sort()
        return tree

    def lineage_of(self, path: str) -> list[str]:
        """Source chain for a given file path (empty if file unknown)."""
        for f in self.files:
            if f.path == path:
                return list(f.source_chain)
        return []


# ─── Internal helpers ──────────────────────────────────────────────────


_FORMAT_BY_EXT: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx", ".doc": "doc",
    ".xlsx": "xlsx", ".xls": "xls",
    ".msg": "msg",
    ".txt": "txt", ".csv": "csv",
    ".jpg": "jpg", ".jpeg": "jpg", ".png": "png",
    ".bmp": "bmp", ".tif": "tif", ".tiff": "tif", ".gif": "gif",
    ".fh11": "fh11", ".psd": "psd", ".ai": "ai",
    ".json": "json",
}

_IMAGE_FORMATS = frozenset({"jpg", "png", "bmp", "tif", "gif"})
_SYSTEM_FILENAMES = frozenset({"Thumbs.db", ".DS_Store"})
_SYSTEM_FILENAME_PATTERNS = (
    re.compile(r"^~\$"),
    re.compile(r"\.tmp$", re.IGNORECASE),
)
_PIPELINE_ARTIFACT_NAMES = frozenset({
    "file_mapping.json", "user_data.json", "concept_map.json",
    "ai_inventory.json", "ai_typology.json",
})


def _normalize_format(path: str) -> str:
    return _FORMAT_BY_EXT.get(Path(path).suffix.lower(), "other")


def _is_system_file(path: str) -> bool:
    name = Path(path).name
    if name in _SYSTEM_FILENAMES:
        return True
    return any(p.search(name) for p in _SYSTEM_FILENAME_PATTERNS)


def _is_pipeline_artifact(path: str) -> bool:
    return Path(path).name in _PIPELINE_ARTIFACT_NAMES


def _top_level_dir(rel_path: str) -> str:
    parts = Path(rel_path).parts
    return parts[0] if parts else ""


def _is_dev_only(rel_path: str) -> bool:
    return _top_level_dir(rel_path) in DEV_ONLY_TOPLEVEL_DIRS


# ─── PDF introspection + image extraction ──────────────────────────────


def _introspect_pdf(abs_path: Path, extract_to: Path | None) -> tuple[dict, list[Path]]:
    """Return (metadata, list of extracted image paths).

    Metadata keys: has_text, page_count, image_count.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ({"has_text": False, "page_count": 0, "image_count": 0}, [])

    extracted: list[Path] = []
    try:
        doc = fitz.open(str(abs_path))
    except Exception as e:
        logger.warning("Cannot open PDF %s: %s", abs_path.name, e)
        return ({"has_text": False, "page_count": 0, "image_count": 0}, [])

    try:
        page_count = doc.page_count
        total_text = 0
        seen_xrefs: set[int] = set()
        image_index = 0

        for page_idx in range(page_count):
            page = doc[page_idx]
            total_text += len(page.get_text().strip())

            for img_info in page.get_images(full=True):
                xref = img_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                if extract_to is None:
                    image_index += 1
                    continue
                try:
                    img = doc.extract_image(xref)
                except Exception as e:
                    logger.debug("Cannot extract image xref=%s from %s: %s", xref, abs_path.name, e)
                    continue
                ext = img.get("ext", "png")
                data = img.get("image", b"")
                width = img.get("width", 0)
                height = img.get("height", 0)
                if (
                    len(data) < MIN_IMAGE_BYTES
                    or width < MIN_IMAGE_DIM
                    or height < MIN_IMAGE_DIM
                ):
                    continue
                out_path = extract_to / f"img_{image_index:03d}.{ext}"
                _write_dedup(out_path, data)
                extracted.append(out_path)
                image_index += 1

        return (
            {
                "has_text": total_text > 50,
                "page_count": page_count,
                "image_count": image_index if extract_to is None else len(extracted),
            },
            extracted,
        )
    finally:
        doc.close()


# ─── Excel introspection + image extraction ────────────────────────────


def _introspect_xlsx(abs_path: Path, extract_to: Path | None) -> tuple[dict, list[Path]]:
    """Return (metadata, list of extracted image paths) for .xlsx.

    Metadata keys: has_text, sheet_count, sheet_names, image_count.
    """
    extracted: list[Path] = []
    try:
        import openpyxl
    except ImportError:
        return ({"has_text": True, "sheet_count": 0, "sheet_names": [], "image_count": 0}, [])

    try:
        wb = openpyxl.load_workbook(str(abs_path), read_only=False, data_only=True)
    except Exception as e:
        logger.warning("Cannot open xlsx %s: %s", abs_path.name, e)
        return ({"has_text": False, "sheet_count": 0, "sheet_names": [], "image_count": 0}, [])

    try:
        sheet_names = list(wb.sheetnames)
        image_index = 0
        total_images_found = 0
        for sheet in wb.worksheets:
            images = getattr(sheet, "_images", []) or []
            for img in images:
                total_images_found += 1
                if extract_to is None:
                    image_index += 1
                    continue
                data, ext = _openpyxl_image_bytes(img)
                if data is None:
                    continue
                width, height = _openpyxl_image_size(img)
                if (
                    len(data) < MIN_IMAGE_BYTES
                    or (width and width < MIN_IMAGE_DIM)
                    or (height and height < MIN_IMAGE_DIM)
                ):
                    continue
                out_path = extract_to / f"img_{image_index:03d}.{ext}"
                _write_dedup(out_path, data)
                extracted.append(out_path)
                image_index += 1

        return (
            {
                "has_text": True,
                "sheet_count": len(sheet_names),
                "sheet_names": sheet_names,
                "image_count": total_images_found if extract_to is None else len(extracted),
            },
            extracted,
        )
    finally:
        wb.close()


def _openpyxl_image_bytes(img) -> tuple[bytes | None, str]:
    """Pull raw bytes + extension out of an openpyxl Image object."""
    try:
        ref = img.ref
        if hasattr(ref, "read"):
            ref.seek(0)
            data = ref.read()
        elif isinstance(ref, (bytes, bytearray)):
            data = bytes(ref)
        else:
            return (None, "png")
    except Exception:
        return (None, "png")
    ext = getattr(img, "format", None) or "png"
    return (data, str(ext).lower())


def _openpyxl_image_size(img) -> tuple[int, int]:
    width = getattr(img, "width", 0) or 0
    height = getattr(img, "height", 0) or 0
    try:
        return (int(width), int(height))
    except (TypeError, ValueError):
        return (0, 0)


def _introspect_xls(abs_path: Path) -> dict:
    """Legacy .xls — no image extraction (format doesn't cleanly support it).

    Returns metadata only (sheet_count/names via xlrd fallback if installed).
    """
    try:
        import xlrd  # type: ignore
        book = xlrd.open_workbook(str(abs_path), on_demand=True)
        sheet_names = list(book.sheet_names())
        book.release_resources()
        return {
            "has_text": True,
            "sheet_count": len(sheet_names),
            "sheet_names": sheet_names,
            "image_count": 0,
        }
    except Exception:
        return {"has_text": True, "sheet_count": 0, "sheet_names": [], "image_count": 0}


# ─── DOCX introspection + media extraction ─────────────────────────────


def _introspect_docx(abs_path: Path, extract_to: Path | None) -> tuple[dict, list[Path]]:
    """Return (metadata, list of extracted image paths) for .docx.

    DOCX is a ZIP with media in word/media/*. We extract those directly — no
    need for python-docx since the files are already images.
    """
    extracted: list[Path] = []
    try:
        with zipfile.ZipFile(str(abs_path)) as zf:
            members = zf.namelist()
            media_files = [m for m in members if m.startswith("word/media/")]
            has_text = any(m == "word/document.xml" for m in members)
            image_index = 0
            total_media = len(media_files)

            if extract_to is not None:
                for m in media_files:
                    data = zf.read(m)
                    ext = Path(m).suffix.lstrip(".").lower() or "png"
                    if len(data) < MIN_IMAGE_BYTES:
                        continue
                    out_path = extract_to / f"img_{image_index:03d}.{ext}"
                    _write_dedup(out_path, data)
                    extracted.append(out_path)
                    image_index += 1

            return (
                {
                    "has_text": has_text,
                    "image_count": total_media if extract_to is None else len(extracted),
                },
                extracted,
            )
    except zipfile.BadZipFile:
        logger.warning("Not a valid DOCX zip: %s", abs_path.name)
        return ({"has_text": False, "image_count": 0}, [])


# ─── Shared I/O utilities ──────────────────────────────────────────────


def _write_dedup(out_path: Path, data: bytes) -> None:
    """Write bytes to out_path. If the file exists with identical SHA256 content, skip.

    Used during the dev-time "re-extract always" policy: running Stage 2 multiple
    times on the same project doesn't duplicate disk writes when content is unchanged.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.is_file():
        existing = hashlib.sha256(out_path.read_bytes()).hexdigest()
        incoming = hashlib.sha256(data).hexdigest()
        if existing == incoming:
            return
    out_path.write_bytes(data)


# ─── Category classification ───────────────────────────────────────────


def _classify_file(
    inv_file: InventoryFile,
    fmt: str,
    has_text: bool,
    has_images: bool,
    path: str,
) -> tuple[str, bool, str, str]:
    """Return (category, useful, reason, conversion_strategy)."""

    # Dev-only gate first — overrides format-based category
    if _is_dev_only(path):
        top = _top_level_dir(path)
        return (
            "reference_output",
            False,
            f"inside {top}/ — prior-run deliverables, absent in production",
            "skip",
        )

    # System noise
    if _is_system_file(path):
        return ("system_file", False, "system noise", "skip")

    # Our own pipeline outputs
    if _is_pipeline_artifact(path):
        return ("pipeline_artifact", False, "AI pipeline output", "skip")

    # Format-driven buckets
    if fmt == "pdf":
        if not has_text:
            return ("pdf_scanned", True, "", "pdf_pages_to_images")
        if has_images:
            return ("pdf_mixed", True, "", "pdf_to_markdown_plus_images")
        return ("pdf_text", True, "", "pdf_to_markdown")

    if fmt == "docx":
        return ("docx", True, "", "docx_to_markdown_plus_media")
    if fmt == "doc":
        return ("doc", True, "", "docx_to_markdown_plus_media")

    if fmt in ("xlsx", "xls"):
        if has_images:
            return ("spreadsheet_mixed", True, "", "excel_per_sheet_to_csv_plus_images")
        return ("spreadsheet", True, "", "excel_per_sheet_to_csv")

    if fmt == "msg":
        return ("email_msg", True, "", "msg_body_to_markdown")

    if fmt in ("txt", "csv"):
        return ("text", True, "", "text_passthrough")

    if fmt in _IMAGE_FORMATS:
        return ("image", True, "", "image_passthrough")

    if fmt in ("fh11", "psd", "ai"):
        return ("binary_unreadable", False, f".{fmt} not readable", "skip")

    if fmt == "json":
        # Non-pipeline JSON (e.g., user drops in a reference) — mark useful, text passthrough.
        return ("text", True, "", "text_passthrough")

    return ("unknown", False, f"unhandled extension: {fmt}", "skip")


# ─── Source chain construction ─────────────────────────────────────────


def _build_source_chain(inv_file: InventoryFile) -> list[str]:
    """Build the provenance chain for a file from Stage 1 inventory."""
    chain: list[str] = []
    if inv_file.kind == "email_attachment" and inv_file.parent_msg:
        chain.append(inv_file.parent_msg)
        chain.append(f"attachment:{Path(inv_file.path).name}")
    return chain


def _build_extracted_chain(parent_chain: list[str], parent_path: str, image_name: str) -> list[str]:
    """Build provenance for an image extracted from a parent file."""
    chain = list(parent_chain) if parent_chain else [Path(parent_path).name]
    chain.append(f"img:{image_name}")
    return chain


# ─── Folder roll-up ────────────────────────────────────────────────────


def _parent_of(rel_path: str) -> str:
    parent = Path(rel_path).parent
    s = parent.as_posix()
    return "" if s == "." else s


def _build_folders(files: list[FileClass]) -> list[FolderClass]:
    direct_counts: Counter[str] = Counter()
    useful_counts: Counter[str] = Counter()
    cat_counts: dict[str, Counter[str]] = {}
    all_paths: set[str] = set()

    for f in files:
        parent = _parent_of(f.path)
        direct_counts[parent] += 1
        if f.useful:
            useful_counts[parent] += 1
        cat_counts.setdefault(parent, Counter())[f.category] += 1
        # Register every ancestor folder, even if empty of direct files
        p = parent
        while True:
            all_paths.add(p)
            if p == "":
                break
            p = _parent_of(p)

    folders: list[FolderClass] = []
    for path in sorted(all_paths):
        parent = None if path == "" else _parent_of(path)
        top = _top_level_dir(path) if path else ""
        folders.append(
            FolderClass(
                path=path,
                parent=parent,
                file_count=direct_counts.get(path, 0),
                useful_count=useful_counts.get(path, 0),
                category_counts=dict(cat_counts.get(path, {})),
                is_dev_only=top in DEV_ONLY_TOPLEVEL_DIRS and path != "",
            )
        )
    return folders


# ─── Eva summary ───────────────────────────────────────────────────────


def _build_eva_summary(
    total_files: int,
    total_folders: int,
    counts: dict[str, int],
    useful_count: int,
    dev_only_count: int,
    extracted_count: int,
    msg_count: int,
    msg_attachment_count: int,
) -> list[str]:
    """Short Catalan summary Eva can read in the wizard."""
    lines = [
        f"Heu aportat {total_files} fitxers en {total_folders} carpetes.",
    ]

    doc_cats = ("pdf_text", "pdf_mixed", "pdf_scanned", "docx", "doc", "text")
    sheet_cats = ("spreadsheet", "spreadsheet_mixed")
    img_cats = ("image",)

    doc_count = sum(counts.get(c, 0) for c in doc_cats)
    sheet_count = sum(counts.get(c, 0) for c in sheet_cats)
    image_count = sum(counts.get(c, 0) for c in img_cats)

    extras = []
    if msg_count:
        extras.append(f"{msg_count} email{'s' if msg_count != 1 else ''} amb {msg_attachment_count} adjunts extrets")
    if extracted_count:
        extras.append(f"{extracted_count} imatges embegudes extretes de documents")

    breakdown = f"{doc_count} documents, {sheet_count} fulls de càlcul, {image_count} imatges"
    if extras:
        breakdown += " (" + "; ".join(extras) + ")"
    lines.append(f"• {useful_count} fitxers útils per generar l'informe — {breakdown}.")

    if dev_only_count:
        lines.append(
            f"• {dev_only_count} fitxers dins de carpetes d'outputs anteriors ({', '.join(sorted(DEV_ONLY_TOPLEVEL_DIRS))}) — "
            f"es salten perquè no existiran a un projecte nou."
        )

    system_count = counts.get("system_file", 0) + counts.get("binary_unreadable", 0) + counts.get("unknown", 0)
    if system_count:
        lines.append(f"• {system_count} fitxers de sistema o format no llegible — es salten.")

    return lines


# ─── Public API ────────────────────────────────────────────────────────


def classify_project(
    project_path: Path | str,
    *,
    extract_images: bool = True,
    inventory: Inventory | None = None,
) -> ProjectTypology:
    """Classify every file in a project by technical type + extract embedded images.

    Args:
        project_path: Project folder (absolute or relative).
        extract_images: If True (default), extract embedded images to sidecar folder.
        inventory: Optionally reuse an existing Stage 1 inventory. If None, built fresh.

    Returns:
        ProjectTypology with files + folders + eva_summary + counts.
    """
    pp = Path(project_path).resolve()
    if not pp.is_dir():
        raise ValueError(f"Not a directory: {pp}")

    inv = inventory if inventory is not None else build_inventory(pp)

    warnings: list[str] = []
    files: list[FileClass] = []

    for inv_file in inv.files:
        abs_path = pp / inv_file.path
        fmt = _normalize_format(inv_file.path)
        source_chain = _build_source_chain(inv_file)

        # Introspect + optionally extract images
        meta: dict = {}
        extracted: list[Path] = []
        extract_dir: Path | None = None

        if extract_images and not _is_dev_only(inv_file.path):
            # Dev-only files: don't waste work extracting from them
            stem_slug = _slugify(Path(inv_file.path).stem)
            extract_dir = pp / _EXTRACTED_ROOT / stem_slug

        if fmt == "pdf":
            meta, extracted = _introspect_pdf(abs_path, extract_dir if extract_images else None)
        elif fmt == "xlsx":
            meta, extracted = _introspect_xlsx(abs_path, extract_dir if extract_images else None)
        elif fmt == "xls":
            meta = _introspect_xls(abs_path)
        elif fmt == "docx":
            meta, extracted = _introspect_docx(abs_path, extract_dir if extract_images else None)
        elif fmt in _IMAGE_FORMATS:
            meta = {"has_text": False, "has_images": True, "image_count": 1}
        elif fmt in ("txt", "csv", "json"):
            meta = {"has_text": True}
        elif fmt == "msg":
            meta = {"has_text": True}
        elif fmt == "doc":
            meta = {"has_text": True}  # we trust LibreOffice conversion in Stage 3
        else:
            meta = {}

        has_text = bool(meta.get("has_text", False))
        has_images = bool(meta.get("image_count", 0) > 0) or bool(meta.get("has_images", False))

        category, useful, reason, conv = _classify_file(
            inv_file, fmt, has_text, has_images, inv_file.path
        )

        fc = FileClass(
            path=inv_file.path,
            format=fmt,
            category=category,
            has_text=has_text,
            has_images=has_images,
            image_count=int(meta.get("image_count", 0)),
            page_count=int(meta.get("page_count", 0)),
            sheet_count=int(meta.get("sheet_count", 0)),
            sheet_names=list(meta.get("sheet_names", [])),
            source_chain=source_chain,
            is_attachment=(inv_file.kind == "email_attachment"),
            parent_path=None,
            useful=useful,
            reason=reason,
            conversion_strategy=conv,
            extracted_images_dir=(
                str(extract_dir.relative_to(pp)) if extract_dir and extracted else None
            ),
        )
        files.append(fc)

        # Materialize extracted images as FileClass entries of their own
        if extracted and extract_dir is not None:
            for img_path in extracted:
                rel = img_path.relative_to(pp).as_posix()
                img_fmt = _normalize_format(rel)
                chain = _build_extracted_chain(source_chain, inv_file.path, img_path.name)
                files.append(
                    FileClass(
                        path=rel,
                        format=img_fmt,
                        category="image",
                        has_text=False,
                        has_images=True,
                        image_count=1,
                        source_chain=chain,
                        is_attachment=inv_file.kind == "email_attachment",
                        parent_path=inv_file.path,
                        useful=True,
                        reason="",
                        conversion_strategy="image_passthrough",
                    )
                )

        if category == "unknown":
            warnings.append(f"unknown format: {inv_file.path}")

    # Aggregate
    counts: dict[str, int] = dict(Counter(f.category for f in files))
    useful_count = sum(1 for f in files if f.useful)
    skipped_count = len(files) - useful_count
    dev_only_count = sum(1 for f in files if f.category == "reference_output")
    extracted_count = sum(1 for f in files if f.parent_path is not None)

    folders = _build_folders(files)

    eva_summary = _build_eva_summary(
        total_files=len(files),
        total_folders=len([f for f in folders if f.path != ""]),
        counts=counts,
        useful_count=useful_count,
        dev_only_count=dev_only_count,
        extracted_count=extracted_count,
        msg_count=inv.msg_count,
        msg_attachment_count=inv.extracted_attachments,
    )

    return ProjectTypology(
        project_path=str(pp),
        classified_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        files=files,
        folders=folders,
        counts_by_category=counts,
        useful_count=useful_count,
        skipped_count=skipped_count,
        eva_summary=eva_summary,
        warnings=warnings,
    )


def save_typology(typ: ProjectTypology, project_path: Path | str) -> Path:
    """Write typology to {project}/validation/ai_typology.json."""
    pp = Path(project_path).resolve()
    out_dir = pp / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ai_typology.json"
    out_path.write_text(typ.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def load_typology(project_path: Path | str) -> ProjectTypology | None:
    pp = Path(project_path).resolve()
    p = pp / "validation" / "ai_typology.json"
    if not p.is_file():
        return None
    return ProjectTypology.model_validate_json(p.read_text(encoding="utf-8"))


# ─── Small helpers ─────────────────────────────────────────────────────


def _slugify(s: str) -> str:
    """Safe folder-name slug: keep alnum + dot/dash/underscore, collapse rest."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._-")
    return cleaned or "unnamed"
