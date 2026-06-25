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
    PRESSUPOST_EXTRACTION_PROMPT,
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

        # Step 2b: inject pressupost vision task (Via B2 — champion-challenger).
        # The output (pressupost_extracted.json) is written for A-vs-B comparison.
        # No consumer reads it yet; wizard_service still uses docs_extracted.json.
        if "pressupost" not in seen_types:
            pressupost_pdf = _find_pressupost_pdf(project_path)
            if pressupost_pdf:
                pressupost_out = project_path / "validation" / "pressupost_extracted.json"
                if force or not pressupost_out.exists():
                    vision_tasks["pressupost"] = {
                        "role": "budget",
                        "path": str(pressupost_pdf.relative_to(project_path)),
                    }
                    _log_step(project_name, "pressupost_found", pressupost_pdf.name)
                else:
                    _log_step(project_name, "cache_hit:pressupost", "skipped")

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
        "pressupost": PRESSUPOST_EXTRACTION_PROMPT,
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
            candidates.extend(subdir.glob("PRESUPUESTO*.pdf"))
    for child in project_path.iterdir():
        if child.is_dir() and re.match(r"^\d", child.name):
            candidates.extend(child.glob("PRESSUPOST*.pdf"))
            candidates.extend(child.glob("PRESUPUESTO*.pdf"))

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
    fields = _parse_docs_fields(combined_text)

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


def _parse_docs_fields(combined_text: str) -> dict[str, dict]:
    """Parse project metadata fields from concatenated pressupost text.

    Pure function (no IO) so the regex logic is unit-testable. Each emitted
    field is a dict with ``value`` / ``source`` / ``confidence``. The guiding
    rule throughout is "no value beats a wrong value": when the canonical
    anchor is absent we emit nothing rather than guess from the scrambled
    budget line-item table.
    """
    fields: dict[str, dict] = {}

    # architect_company — first non-empty line after the "OBRA:" header.
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

    # building_category (C0–C3). Templates vary by language and punctuation:
    #   CA "Tipus d'edifici: C1"  — apostrophe is U+2019 (not ASCII '), colon sep
    #   ES "Tipo de Edificio. C0" — no apostrophe, period separator
    #   "Categoria de construcció/edifici: Cx" — older template
    # The separator class accepts ":" / "." / whitespace. Validated 5/7
    # (Rubí/Bell-lloc/Alcoletge/Vilanova present; Castellar/Anciles absent).
    cat_patterns = (
        r"[Cc]ategori[ea]\s*(?:d['’‘e]\s*)?(?:construcci[oó]|edifici)"
        r"[:.\s]+(C[0-3])",
        r"Tip(?:us|o)\s+(?:d['’‘]\s*|de\s+)?edifici[o]?[:.\s]+(C[0-3])",
    )
    for pat in cat_patterns:
        cat_match = re.search(pat, combined_text, re.IGNORECASE)
        if cat_match:
            fields["building_category"] = {
                "value": cat_match.group(1),
                "source": "PRESSUPOST text",
                "confidence": 1.0,
            }
            break

    # num_planned_dpsh — the canonical campaign sentence, CA + ES:
    #   CA "4 assaigs de penetració dinàmica DPSH"
    #   ES "5 ensayos de penetración dinámica DPSH"
    # We deliberately avoid the budget line-item table: PDF text extraction
    # scrambles its columns, so a stray quantity from an adjacent row binds to
    # the "ASSAIGS DPSH" header. The prose sentence is a single contiguous
    # line, so it is reliable. Absent → emit nothing. Validated 7/7.
    dpsh_match = re.search(
        r"(\d+)\s+(?:assaigs?|ensayos?)\s+de\s+penetraci[oó]n?\s+din[aàá]mica",
        combined_text,
        re.IGNORECASE,
    )
    if dpsh_match:
        fields["num_planned_dpsh"] = {
            "value": int(dpsh_match.group(1)),
            "source": "PRESSUPOST campaign sentence",
            "confidence": 1.0,
        }

    # num_planned_sondeig — only from the campaign prose list, never the budget
    # table. The table repeats "SONDEIG A ROTACIO …" as a line-item header and,
    # with column scrambling, a stray quantity binds to it → spurious counts
    # (the old whole-document regex did exactly this for Castellar/Bell-lloc).
    # The inner regex CANNOT distinguish that table header from the genuine
    # prose ("1Sondeig a rotació …" / "2 sondeo a rotación …") — both yield a
    # count — so we must keep the table out of scope. Two guards, content-first:
    #   1. Anchor a window right after the campaign trigger ("…s'ha previst …
    #      campanya …" / "…se ha previsto … campaña …"); the planned-test list
    #      sits at the top of it.
    #   2. Hard-cut that window at the budget line-item section header
    #      ("UNITATS D'ASSAIG …" / "UNIDADES DE ENSAYO …"), which always
    #      precedes the table's SONDEIG row. This is the real guard: it does
    #      not depend on the table happening to sit far enough away (in the 7
    #      current docs it is ~900 chars down, but a shorter preamble must not
    #      reintroduce the spurious count). The 600-char cap is only a backstop.
    #   CA "1Sondeig a rotació …"   ES "2 sondeo a rotación …"
    # Validated: Castellar=1, Bell-lloc=1, Anciles=2; absent elsewhere.
    camp_match = re.search(
        r"(?:s['’‘]ha\s+previst|se\s+ha\s+previsto)\b.{0,80}?"
        r"(?:campanya|campaña)\b(.{0,600})",
        combined_text,
        re.IGNORECASE | re.DOTALL,
    )
    if camp_match:
        window = camp_match.group(1)
        budget_hdr = re.search(
            r"UNITATS?\s+D['’‘]ASSAIG|UNIDADES?\s+DE\s+ENSAYO",
            window,
            re.IGNORECASE,
        )
        if budget_hdr:
            window = window[: budget_hdr.start()]
        sond_match = re.search(
            r"(\d+)\s*(?:sondeigs?|sondeos?)\s+a\s+rotaci[oó]n?",
            window,
            re.IGNORECASE,
        )
        if sond_match:
            fields["num_planned_sondeig"] = {
                "value": int(sond_match.group(1)),
                "source": "PRESSUPOST campaign sentence",
                "confidence": 1.0,
            }

    # site_address from the OBRA block. The EMPLAÇAMENT anchor hit the
    # "emplaçament de la màquina de penetració" boilerplate and returned
    # garbage. The OBRA block extracts in reading order (unlike the line-item
    # table), so a line-based parser is reliable.
    # Structure: OBRA: / [client?] / ESTUDI[O] GEO… / [street?] / municipality / CLIENT:
    # Post-ESTUDI: last = municipality, penultimate = street (when present).
    # No street (e.g. Rubí): emit nothing — "no value beats a wrong value."
    # Linyola (no ESTUDI line, single combined line): known limitation.
    obra_lines = combined_text.split("\n")
    obra_street = None
    obra_muni = None
    for obra_i, obra_raw in enumerate(obra_lines):
        if re.match(r"^OBRA\s*:?\s*$", obra_raw.strip(), re.IGNORECASE):
            obra_block: list[str] = []
            for obra_r in obra_lines[obra_i + 1 :]:
                obra_s = obra_r.strip()
                if not obra_s:
                    continue
                if obra_s.endswith(":") or re.match(r"^\d+[·.]\d", obra_s):
                    break
                obra_block.append(obra_s)
            for obra_bi, obra_bl in enumerate(obra_block):
                if re.match(r"^ESTUDI[O]?\s+GEO", obra_bl, re.IGNORECASE):
                    obra_after = obra_block[obra_bi + 1 :]
                    if len(obra_after) >= 2:
                        obra_street, obra_muni = obra_after[-2], obra_after[-1]
                    elif len(obra_after) == 1:
                        obra_muni = obra_after[0]  # municipality only (e.g. Rubí)
                    break
            break  # process first OBRA block only
    if obra_street and obra_muni:
        fields["site_address"] = {
            "value": f"{obra_street}, {obra_muni}",
            "source": "PRESSUPOST OBRA block",
            "confidence": 0.95,
        }

    return fields


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


def _find_pressupost_pdf(project_path: Path) -> "Path | None":
    """Find the primary budget PDF (PRESSUPOST*.pdf or PRESUPUESTO*.pdf).

    Prefers the vectorial original in a numbered subdir over the scanned
    acceptance copy in ACCEPTACIO/, which is lower quality for vision.
    Mirrors the discovery logic in _extract_docs_python.
    """
    # Numbered subdirs first (vectorial originals, e.g. 25.0493/)
    for child in sorted(project_path.iterdir()):
        if child.is_dir() and re.match(r"^\d", child.name):
            for pat in ("PRESSUPOST*.pdf", "PRESUPUESTO*.pdf"):
                hits = sorted(child.glob(pat))
                if hits:
                    return hits[0]
    # Root level
    for pat in ("PRESSUPOST*.pdf", "PRESUPUESTO*.pdf"):
        hits = sorted(project_path.glob(pat))
        if hits:
            return hits[0]
    # ACCEPTACIO fallback (scanned signed version, lower quality)
    acceptacio = project_path / "ACCEPTACIO"
    if acceptacio.is_dir():
        for pat in ("PRESSUPOST*.pdf", "PRESUPUESTO*.pdf"):
            hits = sorted(acceptacio.glob(pat))
            if hits:
                return hits[0]
    return None


def _output_filename(vision_type: str) -> str:
    """Map vision_type to output filename."""
    return {
        "planol": "planol_extracted.json",
        "dpsh": "dpsh_extracted.json",
        "sondeig": "sondeig_extracted.json",
        "sondeig_annex": "sondeig_annex_extracted.json",
    }.get(vision_type, f"{vision_type}_extracted.json")
