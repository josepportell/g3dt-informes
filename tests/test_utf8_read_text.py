"""
F1 (2026-08) — UTF-8 encoding on every ``Path.read_text()`` / ``write_text()``.

Production bug (AUDIT-PROD-2026-08 §T2): on Windows ``Path.read_text()`` without
``encoding`` decodes as cp1252, but the pipeline writes its JSON as UTF-8 with
``ensure_ascii=False``. A file name containing a byte undefined in cp1252 (``Í``
→ 0xC3 0x8D) raised ``UnicodeDecodeError`` in ``wizard_service._merge_prefills``
and left the wizard empty (Can Mir Rubí, 4/4 attempts, 0 reports).

Three layers:
1. A fixture that makes ``Path.read_text()`` / ``write_text()`` default to cp1252
   (what Windows does), and a sanity test proving it reproduces the crash.
2. The real readers (wizard_service, image_manager, validation schemas) must
   survive that fixture.
3. A static scan: no ``.read_text(`` / ``.write_text(`` call without ``encoding=``
   may exist in ``automation/`` or ``web/`` (tests excluded). Keeps the bug out.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 'Í' encodes to 0xC3 0x8D and 0x8D is undefined in cp1252 → decode crashes.
RUBI_NAME = "Nº 5 · RUBÍ.pdf"


@pytest.fixture
def windows_cp1252(monkeypatch):
    """Simulate Windows: bare read_text()/write_text() default to cp1252."""
    orig_read = Path.read_text
    orig_write = Path.write_text

    def read_text(self, encoding=None, errors=None):
        return orig_read(self, encoding=encoding or "cp1252", errors=errors)

    def write_text(self, data, encoding=None, errors=None, newline=None):
        return orig_write(self, data, encoding=encoding or "cp1252", errors=errors, newline=newline)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(Path, "write_text", write_text)


def _write_file_mapping(project_path: Path) -> Path:
    """Write file_mapping.json exactly as file_scanner does (UTF-8, ensure_ascii=False)."""
    fm = {
        "roles": {"penetros": {"path": RUBI_NAME, "confidence": 0.9}},
        "role_files": {"penetros": [{"path": RUBI_NAME, "confidence": 0.9, "detection": "tier1"}]},
    }
    fm_path = project_path / "file_mapping.json"
    fm_path.write_bytes(json.dumps(fm, indent=2, ensure_ascii=False).encode("utf-8"))
    return fm_path


# ---------------------------------------------------------------------------
# 1. The fixture reproduces the Windows crash
# ---------------------------------------------------------------------------

def test_fixture_reproduces_windows_crash(tmp_path, windows_cp1252):
    fm_path = _write_file_mapping(tmp_path)
    with pytest.raises(UnicodeDecodeError):
        fm_path.read_text()  # the pre-F1 call shape
    # and the fixed call shape works
    assert RUBI_NAME in fm_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 2. Real readers survive cp1252 default
# ---------------------------------------------------------------------------

def test_wizard_service_read_file_mapping_under_cp1252(tmp_path, windows_cp1252):
    from web.wizard_service import _read_file_mapping

    _write_file_mapping(tmp_path)
    fm = _read_file_mapping(tmp_path)
    assert fm is not None, "file_mapping.json must load under a cp1252 default (the Can Mir Rubí crash)"
    assert fm["roles"]["penetros"]["path"] == RUBI_NAME


def test_wizard_service_read_file_mapping_missing_or_corrupt(tmp_path):
    from web.wizard_service import _read_file_mapping

    assert _read_file_mapping(tmp_path) is None  # missing
    (tmp_path / "file_mapping.json").write_bytes(b"{not json")
    assert _read_file_mapping(tmp_path) is None  # corrupt → never raises


def test_image_manager_file_mapping_under_cp1252(tmp_path, windows_cp1252):
    from automation.image_manager import ImageManager

    _write_file_mapping(tmp_path)
    mgr = ImageManager(tmp_path, report_data=object(), tpl=None)
    roles = mgr._load_file_mapping()
    assert roles is not None and roles["penetros"]["path"] == RUBI_NAME
    role_files = mgr._load_role_files()
    assert role_files is not None and role_files["penetros"][0]["path"] == RUBI_NAME


def test_validation_schemas_roundtrip_under_cp1252(tmp_path, windows_cp1252):
    from automation.validation.schemas import DPSHValidationFile, SondeigValidationFile

    p = tmp_path / "dpsh_extracted.json"
    DPSHValidationFile(source_file=RUBI_NAME).save(p)
    assert DPSHValidationFile.load(p).source_file == RUBI_NAME

    p2 = tmp_path / "sondeig_extracted.json"
    SondeigValidationFile(source_file=RUBI_NAME).save(p2)
    assert SondeigValidationFile.load(p2).source_file == RUBI_NAME


# ---------------------------------------------------------------------------
# 3. Static regression: no bare read_text()/write_text() in production code
# ---------------------------------------------------------------------------

_CALL_RE = re.compile(r"\.(read_text|write_text)\(")


def _call_arg_text(src: str, open_paren_idx: int) -> str:
    """Return the text between the call's parentheses (handles nesting)."""
    depth = 0
    for i in range(open_paren_idx, len(src)):
        ch = src[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return src[open_paren_idx + 1:i]
    return src[open_paren_idx + 1:]


def _bare_text_io_calls(root: Path) -> list[str]:
    offenders: list[str] = []
    for py in sorted(root.rglob("*.py")):
        if "test" in py.name or "__pycache__" in py.parts:
            continue
        src = py.read_text(encoding="utf-8")
        for m in _CALL_RE.finditer(src):
            args = _call_arg_text(src, m.end() - 1)
            if "encoding" not in args:
                line = src.count("\n", 0, m.start()) + 1
                offenders.append(f"{py.relative_to(PROJECT_ROOT)}:{line}: {m.group(0)}{args[:60]!r}")
    return offenders


def test_no_bare_read_text_or_write_text_in_prod_code():
    offenders = []
    for sub in ("automation", "web"):
        offenders += _bare_text_io_calls(PROJECT_ROOT / sub)
    assert not offenders, (
        "Path.read_text()/write_text() without encoding= (cp1252 on Windows, see F1):\n"
        + "\n".join(offenders)
    )
