"""
Fast vision extraction: spawns `claude -p` from /tmp to avoid loading
CLAUDE.md, MCP servers, and hooks on every round trip.

Python pre-processing first (file scan, Excel extraction, doc parsing),
then ONE `claude -p` call with a self-contained prompt for all PDF tasks.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from automation.file_scanner import FileScanner
from automation.dpsh_extractor import DPSHExtractor
from automation.validation.prompts import (
    DPSH_EXTRACTION_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    PLANOL_EXTRACTION_PROMPT,
    SONDEIG_ANNEX_EXTRACTION_PROMPT,
    SONDEIG_EXTRACTION_PROMPT,
)

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_fast_status: dict[str, dict] = {}  # project_name -> status dict
_fast_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_vision_fast(
    project_name: str,
    project_path: Path,
    project_root: Path,
    force: bool = False,
) -> dict:
    """Entry point. Returns immediately with status."""
    with _fast_lock:
        status = _fast_status.get(project_name)
        if status and status.get("status") == "running":
            return {"status": "already_running"}

    try:
        with _fast_lock:
            _fast_status[project_name] = {
                "status": "running",
                "steps": [],
                "start_time": time.time(),
            }
        t = threading.Thread(
            target=_run_vision_fast,
            args=(project_name, project_path, project_root, force),
            daemon=True,
        )
        t.start()
        return {"status": "started"}
    except Exception as e:
        logger.exception("vision_fast start failed for %s", project_name)
        return {"status": "error", "message": str(e)}


def get_fast_status(project_name: str) -> dict:
    """Return current status for a project (shallow copy)."""
    with _fast_lock:
        status = _fast_status.get(project_name)
        if not status:
            return {"status": "idle"}
        return dict(status)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_vision_fast(
    project_name: str,
    project_path: Path,
    project_root: Path,
    force: bool,
) -> None:
    """Background thread: file scan, Excel extraction, doc parsing, claude -p."""
    try:
        # Step 1: file_mapping
        scanner = FileScanner(project_path)
        mapping = scanner.load()
        if not mapping:
            mapping = scanner.scan()
            scanner.save(mapping)
        _log_step(project_name, "file_mapping", "loaded" if mapping else "scanned")

        # Step 2: identify_tasks
        vision_tasks: dict[str, dict] = {}
        seen_types: set[str] = set()
        for role_name, role in mapping.roles.items():
            if role.vision_type and role.vision_type not in seen_types:
                seen_types.add(role.vision_type)
                output_file = _output_filename(role.vision_type)
                output_path = project_path / "validation" / output_file
                if not force and output_path.exists():
                    _log_step(project_name, f"cache_hit:{role.vision_type}", "skipped")
                    continue
                vision_tasks[role.vision_type] = {
                    "role": role_name,
                    "path": role.path,
                }
        _log_step(project_name, "identify_tasks", f"{len(vision_tasks)} tasks")

        # Step 3: extract_excel (for DPSH comparison)
        excel_data = None
        if "dpsh" in vision_tasks:
            excel_role = mapping.roles.get("dpsh_excel")
            if excel_role:
                try:
                    ext = DPSHExtractor(str(project_path / excel_role.path))
                    dpsh_data = ext.extract_all()
                    excel_data = dpsh_data.to_dict()
                    _log_step(project_name, "extract_excel", "ok")
                except Exception as e:
                    _log_step(project_name, "extract_excel", f"error: {e}")

        # Step 4: extract_docs (Python regex, no Claude)
        _extract_docs_python(project_path, mapping.roles, force)
        _log_step(project_name, "extract_docs", "done")

        # If nothing to do, complete early
        if not vision_tasks:
            _log_step(project_name, "complete", "all cached, nothing to do")
            with _fast_lock:
                _fast_status[project_name]["status"] = "completed"
                _fast_status[project_name]["elapsed"] = (
                    time.time() - _fast_status[project_name]["start_time"]
                )
            return

        # Step 5: build_prompt
        combined_prompt = _build_combined_prompt(
            project_path, vision_tasks, excel_data,
        )
        _log_step(project_name, "build_prompt", f"{len(combined_prompt)} chars")

        # Step 6: claude_spawn
        claude_path = os.getenv("G3DT_CLAUDE_PATH", "claude")
        (project_path / "validation").mkdir(exist_ok=True)

        log_path = (
            Path("/tmp")
            / f"claude-vision-fast-{project_name.replace('/', '_')}.log"
        )

        shell_cmd = (
            f"{shlex.quote(claude_path)} -p {shlex.quote(combined_prompt)}"
            f" --permission-mode bypassPermissions"
            f" < /dev/null > {shlex.quote(str(log_path))} 2>&1"
        )

        proc = subprocess.Popen(
            shell_cmd,
            shell=True,
            cwd="/tmp",  # KEY: run from /tmp to avoid loading CLAUDE.md
            start_new_session=True,
        )
        _log_step(project_name, "claude_spawn", f"pid={proc.pid}")

        # Step 7: wait
        timeout = int(os.getenv("G3DT_VISION_TIMEOUT", "600"))
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            _log_step(project_name, "timeout", f"killed after {timeout}s")
            with _fast_lock:
                _fast_status[project_name]["status"] = "error"
            return

        # Step 8: complete
        elapsed = time.time() - _fast_status[project_name]["start_time"]
        rc = proc.returncode
        _log_step(project_name, "complete", f"rc={rc}, total={elapsed:.1f}s")
        with _fast_lock:
            _fast_status[project_name]["status"] = (
                "completed" if rc == 0 else "error"
            )
            _fast_status[project_name]["returncode"] = rc
            _fast_status[project_name]["elapsed"] = elapsed

    except Exception:
        logger.exception("vision_fast failed for %s", project_name)
        with _fast_lock:
            if project_name in _fast_status:
                _fast_status[project_name]["status"] = "error"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_combined_prompt(
    project_path: Path,
    vision_tasks: dict[str, dict],
    excel_data: dict | None,
) -> str:
    """Build ONE combined prompt for all vision PDF tasks."""
    prompt_map = {
        "planol": PLANOL_EXTRACTION_PROMPT,
        "dpsh": DPSH_EXTRACTION_PROMPT,
        "sondeig": SONDEIG_EXTRACTION_PROMPT,
        "sondeig_annex": SONDEIG_ANNEX_EXTRACTION_PROMPT,
    }

    parts: list[str] = []
    parts.append(EXTRACTION_SYSTEM_PROMPT)
    parts.append("")
    parts.append(
        f"You have {len(vision_tasks)} PDF extraction task(s). For each task:"
    )
    parts.append("1. Read the PDF file using the Read tool")
    parts.append("2. Extract data following the specific instructions")
    parts.append(
        "3. Write the JSON output to the specified path using the Write tool"
    )
    parts.append("")
    parts.append(
        "IMPORTANT: Complete ALL tasks. Each task is independent"
        " - if one fails, continue with the others."
    )

    for idx, (vtype, task_info) in enumerate(vision_tasks.items(), 1):
        pdf_path = (project_path / task_info["path"]).resolve()
        output_file = _output_filename(vtype)
        output_path = (project_path / "validation" / output_file).resolve()

        extraction_prompt = prompt_map.get(vtype, "")

        parts.append("")
        parts.append(f"=== TASK {idx}: {vtype} ===")
        parts.append(f"PDF: {pdf_path}")
        parts.append(f"Output: {output_path}")
        parts.append("")
        parts.append(extraction_prompt)

        if vtype == "dpsh" and excel_data:
            parts.append("")
            parts.append("EXCEL COMPARISON DATA:")
            parts.append(json.dumps(excel_data, indent=2, ensure_ascii=False))
            parts.append(
                "Compare each N20 value you extract with the Excel values above."
            )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Python doc extraction (replaces Claude-based docs extraction)
# ---------------------------------------------------------------------------

def _extract_docs_python(
    project_path: Path,
    roles: dict,
    force: bool,
) -> None:
    """Extract docs using PyMuPDF + regex. Writes docs_extracted.json."""
    try:
        import fitz  # noqa: F811 – PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not installed, skipping docs extraction")
        return

    output_path = project_path / "validation" / "docs_extracted.json"
    if not force and output_path.exists():
        return

    # Collect candidate pressupost PDFs
    candidates: list[Path] = []
    for subdir in (project_path / "ACCEPTACIO", project_path):
        if subdir.is_dir():
            candidates.extend(subdir.glob("PRESSUPOST*.pdf"))
    for child in project_path.iterdir():
        if child.is_dir() and re.match(r"^\d", child.name):
            candidates.extend(child.glob("PRESSUPOST*.pdf"))

    texts: list[str] = []
    source_files: list[str] = []
    for pdf_path in candidates[:3]:
        try:
            doc = fitz.open(str(pdf_path))
            for page in doc:
                texts.append(page.get_text())
            doc.close()
            source_files.append(pdf_path.name)
        except Exception:
            pass

    # Also read DADES CLIENT.txt
    for txt_path in project_path.rglob("DADES CLIENT*.txt"):
        try:
            texts.append(txt_path.read_text(encoding="utf-8", errors="replace"))
            source_files.append(txt_path.name)
        except Exception:
            pass

    combined_text = "\n".join(texts)
    fields: dict[str, dict] = {}

    # Parse architect_company (line after "OBRA:")
    for line in combined_text.split("\n"):
        line_stripped = line.strip()
        if re.match(r"^OBRA\s*:?\s*$", line_stripped, re.IGNORECASE):
            idx = combined_text.index(line) + len(line)
            remaining = combined_text[idx:].strip().split("\n")
            for next_line in remaining:
                next_line = next_line.strip()
                if next_line and not re.match(
                    r"^ESTUDI\s+GEO", next_line, re.IGNORECASE
                ):
                    fields["architect_company"] = {
                        "value": next_line,
                        "source": "PRESSUPOST p.1 OBRA field",
                        "confidence": 0.9,
                    }
                    break
            break

    # Parse building_category
    cat_match = re.search(
        r"[Cc]ategori[ea]\s*(?:d[\'e]\s*)?(?:construcci[oó]|edifici)"
        r"\s*[:\s]*\s*(C[0-3])",
        combined_text,
    )
    if not cat_match:
        cat_match = re.search(
            r"Tipus\s*(?:d[\'e]\s*)?edifici\s*[:\s]*\s*(C[0-3])",
            combined_text,
            re.IGNORECASE,
        )
    if cat_match:
        fields["building_category"] = {
            "value": cat_match.group(1),
            "source": "PRESSUPOST text",
            "confidence": 1.0,
        }

    # Parse num_planned_dpsh
    dpsh_match = re.search(
        r"(\d+)[,.]?\d*\s*(?:UNITATS?\s*D[\'E]\s*ASSAI"
        r"|assaigs?\s*DPSH|DPSH|penetr[oò]metres?)",
        combined_text,
        re.IGNORECASE,
    )
    if dpsh_match:
        fields["num_planned_dpsh"] = {
            "value": int(dpsh_match.group(1)),
            "source": "PRESSUPOST text",
            "confidence": 1.0,
        }

    # Parse num_planned_sondeig
    sond_match = re.search(
        r"(\d+)[,.]?\d*\s*(?:SONDEIG|sondeig)",
        combined_text,
    )
    if sond_match:
        fields["num_planned_sondeig"] = {
            "value": int(sond_match.group(1)),
            "source": "PRESSUPOST text",
            "confidence": 1.0,
        }

    # Parse site_address
    addr_match = re.search(
        r"(?:EMPLA[CÇ]AMENT|SITUACI[OÓ]|Adre[çc]a)\s*[:\s]\s*(.+)",
        combined_text,
        re.IGNORECASE,
    )
    if addr_match:
        addr_val = addr_match.group(1).strip().rstrip(".")
        if addr_val and len(addr_val) > 5:
            fields["site_address"] = {
                "value": addr_val,
                "source": "PRESSUPOST text",
                "confidence": 0.85,
            }

    result = {
        "source_files": source_files,
        "extraction_date": datetime.now(timezone.utc).isoformat(),
        "extraction_method": "python_regex",
        "fields": fields,
        "extraction_notes": (
            f"Python regex extraction from {len(source_files)} files"
        ),
    }

    # Backlink: _metadata.source_file records the primary input artifact so
    # inspection tooling can trace extracted fields back to their origin.
    # docs_extracted.json aggregates multiple sources; the list is preserved
    # in `source_files`, and `_metadata.source_file` points at the first one
    # (or an empty string if no files were read).
    result["_metadata"] = {
        "source_file": source_files[0] if source_files else "",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": "python_regex",
    }

    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_step(project_name: str, step: str, note: str = "") -> None:
    """Log a timing step to the in-memory status dict."""
    with _fast_lock:
        status = _fast_status.get(project_name)
        if not status:
            return
        elapsed = time.time() - status["start_time"]
        entry = {"step": step, "elapsed": round(elapsed, 1), "note": note}
        status["steps"].append(entry)
    logger.info(
        "vision_fast [%s] %s: %s (%.1fs)", project_name, step, note, elapsed,
    )


def _output_filename(vision_type: str) -> str:
    """Map vision_type to output filename."""
    return {
        "planol": "planol_extracted.json",
        "dpsh": "dpsh_extracted.json",
        "sondeig": "sondeig_extracted.json",
        "sondeig_annex": "sondeig_annex_extracted.json",
    }.get(vision_type, f"{vision_type}_extracted.json")
