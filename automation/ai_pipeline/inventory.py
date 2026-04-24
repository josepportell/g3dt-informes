"""Stage 1: inventory — walk a project folder and count files by folder.

Reuses:
- MsgMiner._save_attachments for .msg attachment materialization (sidecar per-msg folder, content-hash dedup)
- concept_scout.scanner.enumerate_project_files for the walk (skip rules, file typing)
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from automation.concept_scout.scanner import enumerate_project_files
from automation.fileminer.miners.msg_miner import MsgMiner

logger = logging.getLogger(__name__)

_MSG_ATTACHMENT_MARKER = ("validation", "msg_attachments")


class InventoryFile(BaseModel):
    """One file found during the walk."""

    path: str                    # relative to project root, POSIX style
    size_kb: int
    type: str                    # pdf_vector, pdf_scanned, excel, image, text, email, docx, other
    kind: str                    # "regular" | "email_attachment"
    parent_msg: str | None = None  # relative path of parent .msg, only for email_attachment


class FolderSummary(BaseModel):
    """File count for one folder (non-recursive — files directly inside it only)."""

    path: str          # "" = project root, else relative posix path of the folder
    file_count: int


class Inventory(BaseModel):
    """Full inventory of a project folder. Stage 1 output of the AI pipeline."""

    project_path: str
    scanned_at: str           # ISO 8601 UTC
    total_files: int
    root_file_count: int
    folders: list[FolderSummary] = Field(default_factory=list)
    files: list[InventoryFile] = Field(default_factory=list)
    msg_count: int = 0              # number of .msg files found
    extracted_attachments: int = 0  # number of files under validation/msg_attachments/

    # ── Query helpers ────────────────────────────────────────────────────
    def files_in_folder(self, folder: str) -> list[InventoryFile]:
        """Return files directly inside `folder` (non-recursive). `folder=""` = root."""
        norm = folder.strip("/")
        return [f for f in self.files if _parent_of(f.path) == norm]

    def find_by_name(self, substring: str) -> list[InventoryFile]:
        """Case-insensitive substring match on filename."""
        needle = substring.lower()
        return [f for f in self.files if needle in Path(f.path).name.lower()]

    def files_of_type(self, type_: str) -> list[InventoryFile]:
        return [f for f in self.files if f.type == type_]


# ─── Internal helpers ────────────────────────────────────────────────────


def _parent_of(rel_path: str) -> str:
    """Return the parent folder of a relative path in POSIX form, "" for root."""
    parent = Path(rel_path).parent
    s = parent.as_posix()
    return "" if s == "." else s


def _is_email_attachment(rel_parts: tuple[str, ...]) -> bool:
    return (
        len(rel_parts) >= 3
        and rel_parts[0] == _MSG_ATTACHMENT_MARKER[0]
        and rel_parts[1] == _MSG_ATTACHMENT_MARKER[1]
    )


def _materialize_msg_attachments(project_path: Path) -> None:
    """Extract attachments from every .msg in the project into validation/msg_attachments/{stem}/.

    Delegates to MsgMiner._save_attachments to reuse its dedup + sidecar logic. If extract_msg
    is not installed, logs a warning and returns — the walk still succeeds without attachments.
    """
    msg_files = [p for p in project_path.rglob("*.msg") if p.is_file()]
    if not msg_files:
        return

    try:
        import extract_msg  # noqa: F401
    except ImportError:
        logger.warning(
            "extract_msg not installed; skipping attachment extraction for %d .msg files",
            len(msg_files),
        )
        return

    import extract_msg as _em

    miner = MsgMiner(project_path=project_path, source_type="ai_pipeline_inventory")
    for msg_path in msg_files:
        try:
            msg = _em.Message(str(msg_path))
        except Exception as e:
            logger.warning("Cannot open %s: %s", msg_path.name, e)
            continue
        try:
            miner._save_attachments(msg, msg_path)
        except Exception as e:
            logger.warning("Attachment extraction failed for %s: %s", msg_path.name, e)
        finally:
            try:
                msg.close()
            except Exception:
                pass


def _parent_msg_for_attachment(rel_path: str) -> str | None:
    """Given validation/msg_attachments/{stem}/foo.pdf, return the likely .msg filename.

    Returns the {stem}.msg path relative to project root if we can find it, else the stem itself
    (so callers at least see which email-bucket the attachment came from).
    """
    parts = Path(rel_path).parts
    if len(parts) < 4:
        return None
    return f"{parts[2]}.msg"


# ─── Public API ──────────────────────────────────────────────────────────


def build_inventory(project_path: Path | str, *, extract_attachments: bool = True) -> Inventory:
    """Walk the project folder and return a full inventory.

    Args:
        project_path: Absolute or relative path to the project folder.
        extract_attachments: If True (default), materialize .msg attachments into
            validation/msg_attachments/{stem}/ before walking so they appear in the inventory.

    Returns:
        Inventory: pydantic model with counts + full file list + query helpers.
    """
    pp = Path(project_path).resolve()
    if not pp.is_dir():
        raise ValueError(f"Not a directory: {pp}")

    if extract_attachments:
        _materialize_msg_attachments(pp)

    entries = enumerate_project_files(pp)

    files: list[InventoryFile] = []
    folder_counts: Counter[str] = Counter()
    msg_count = 0
    extracted = 0

    for e in entries:
        rel = e.path.replace("\\", "/")
        parts = tuple(Path(rel).parts)
        is_att = _is_email_attachment(parts)
        if is_att:
            extracted += 1
            parent_msg = _parent_msg_for_attachment(rel)
            kind = "email_attachment"
        else:
            parent_msg = None
            kind = "regular"
        if e.type == "email":
            msg_count += 1

        files.append(
            InventoryFile(
                path=rel,
                size_kb=e.size_kb,
                type=e.type,
                kind=kind,
                parent_msg=parent_msg,
            )
        )
        folder_counts[_parent_of(rel)] += 1

    folders = [
        FolderSummary(path=p, file_count=c)
        for p, c in sorted(folder_counts.items(), key=lambda kv: kv[0])
    ]

    return Inventory(
        project_path=str(pp),
        scanned_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        total_files=len(files),
        root_file_count=folder_counts.get("", 0),
        folders=folders,
        files=files,
        msg_count=msg_count,
        extracted_attachments=extracted,
    )


def save_inventory(inv: Inventory, project_path: Path | str) -> Path:
    """Write inventory JSON to {project}/validation/ai_inventory.json. Returns the written path."""
    pp = Path(project_path).resolve()
    out_dir = pp / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ai_inventory.json"
    out_path.write_text(inv.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def load_inventory(project_path: Path | str) -> Inventory | None:
    """Load cached inventory from {project}/validation/ai_inventory.json, or None if absent."""
    pp = Path(project_path).resolve()
    p = pp / "validation" / "ai_inventory.json"
    if not p.is_file():
        return None
    return Inventory.model_validate_json(p.read_text(encoding="utf-8"))
