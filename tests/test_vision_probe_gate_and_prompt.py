"""Tests for knob fixes #2 (probe gate widening) and #4 (probe prompt).

Stream B of the 2026-04-19 knob-fixes effort. See
`docs/knob-fixes-2026-04-19/STATUS.md` for scope.

These tests are hermetic — no LLM calls, no reference-material fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


# ---------------------------------------------------------------------------
# Prompt round-trip: abstention + map-subject scoping clauses are present.
# ---------------------------------------------------------------------------

def test_probe_prompt_contains_abstention_clause():
    """Probe prompt instructs model to abstain when subject is ambiguous."""
    from automation.concept_scout.vision_probe import _PROBE_PROMPT

    lower = _PROBE_PROMPT.lower()
    # Section marker
    assert "abstention" in lower, "prompt missing ABSTENTION section"
    # Core instruction words
    assert "abstain" in lower, "prompt missing 'abstain' verb"
    # Explicit abstention target: empty concepts_found on ambiguity
    assert "concepts_found = []" in _PROBE_PROMPT or \
           "concepts_found=[]" in _PROBE_PROMPT.replace(" ", ""), \
        "prompt missing explicit empty-concepts_found abstention target"
    # Examples of incidental content the model should ignore
    assert "frame edges" in lower, "prompt missing 'frame edges' incidental-content example"


def test_probe_prompt_contains_map_subject_scoping():
    """Probe prompt tells model how to scope municipality/province on maps."""
    from automation.concept_scout.vision_probe import _PROBE_PROMPT

    lower = _PROBE_PROMPT.lower()
    assert "map-subject" in lower or "map subject" in lower, \
        "prompt missing MAP-SUBJECT section"
    # The rule must mention the document_type trigger
    assert 'document_type = "map"' in _PROBE_PROMPT or \
           "document_type=map" in _PROBE_PROMPT.replace(" ", "").replace('"', ''), \
        "prompt missing document_type=map trigger"
    # Must explicitly forbid neighbouring-town labels
    assert "neighbour" in lower or "neighbor" in lower, \
        "prompt missing guidance on neighbour-town labels"
    # Must tell the model to look at subject indicators (polygon/marker/centre)
    assert "polygon" in lower or "marker" in lower or "center" in lower or "centre" in lower, \
        "prompt missing subject-indicator guidance"


# ---------------------------------------------------------------------------
# Widened-gate helper: `_should_probe_text_pdf`.
# ---------------------------------------------------------------------------

def test_should_probe_text_pdf_skips_when_concepts_already_detected(tmp_path):
    """If text miners already mapped concepts, don't waste a probe."""
    from automation.concept_scout import vision_probe

    # Monkeypatch the text extractor so we don't need a real PDF.
    original = vision_probe._extract_page1_text
    vision_probe._extract_page1_text = lambda p: "small"  # triggers short-text branch

    try:
        fake_pdf = tmp_path / "x.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        assert vision_probe._should_probe_text_pdf(
            fake_pdf, concepts_detected=["architect_name"],
        ) is False
    finally:
        vision_probe._extract_page1_text = original


def test_should_probe_text_pdf_fires_on_short_text(tmp_path):
    """Short page-1 text with no concepts detected → probe."""
    from automation.concept_scout import vision_probe

    original = vision_probe._extract_page1_text
    vision_probe._extract_page1_text = lambda p: "t"  # very short

    try:
        fake_pdf = tmp_path / "x.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        assert vision_probe._should_probe_text_pdf(
            fake_pdf, concepts_detected=[],
        ) is True
    finally:
        vision_probe._extract_page1_text = original


def test_should_probe_text_pdf_fires_on_layout_heavy_titleblock(tmp_path):
    """Modest-length layout-heavy text with no concepts detected → probe.

    This is the central acceptance case for knob #2: architect plans whose
    page-1 text is a CAD title block (short tokens, mostly numbers) get
    routed to vision even though `text_extractable=True`.
    """
    from automation.concept_scout import vision_probe

    titleblock = (
        "Promotor\nData\nEscala\n1.0\n1/200\n"
        "E2557\nEmplaçament\nC. X 4\n"
        "AVANTPROJECTE\nPb+1Pp\n7.5m\n"
        "arquitecte\nnom\ntel\nweb\n"
    )
    original = vision_probe._extract_page1_text
    vision_probe._extract_page1_text = lambda p: titleblock

    try:
        fake_pdf = tmp_path / "1.0.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        assert vision_probe._should_probe_text_pdf(
            fake_pdf, concepts_detected=[],
        ) is True
    finally:
        vision_probe._extract_page1_text = original


def test_should_probe_text_pdf_skips_long_prose_with_no_concepts(tmp_path):
    """Long prose pages (e.g. budgets, lab reports) are NOT probed even if
    the aggregator found zero mapped concepts — probing would be wasteful."""
    from automation.concept_scout import vision_probe

    long_prose = (
        "El present document descriu en detall el procediment a seguir "
        "per a la realització de les proves de laboratori en mostres de "
        "sòl procedents del sondeig manual. "
    ) * 20  # > 2000 chars
    assert len(long_prose) > 2000

    original = vision_probe._extract_page1_text
    vision_probe._extract_page1_text = lambda p: long_prose

    try:
        fake_pdf = tmp_path / "budget.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        assert vision_probe._should_probe_text_pdf(
            fake_pdf, concepts_detected=[],
        ) is False
    finally:
        vision_probe._extract_page1_text = original


# ---------------------------------------------------------------------------
# probe_unreadable_files gate: integration with FileEntry list.
# ---------------------------------------------------------------------------

def test_probe_gate_includes_layout_heavy_vector_pdf(tmp_path, monkeypatch):
    """End-to-end: a layout-heavy pdf_vector FileEntry with empty
    concepts_detected gets added to the probe work list."""
    from automation.concept_scout import vision_probe
    from automation.concept_scout.models import FileEntry

    # Build a fake project dir + FileEntry.
    (tmp_path / "26.0050").mkdir()
    fake_pdf = tmp_path / "26.0050" / "1.0.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    fe = FileEntry(
        path="26.0050/1.0.pdf",
        type="pdf_vector",
        size_kb=200,
        text_extractable=True,
        concepts_detected=[],
    )

    # Stub text extraction to return layout-heavy content.
    titleblock = "1.0\n1/200\nE2557\nPb+1Pp\n7.5m\nA B C\n" * 3
    monkeypatch.setattr(vision_probe, "_extract_page1_text", lambda p: titleblock)

    # Stub the actual probe call so we don't hit a vision model.
    calls: list[str] = []

    def fake_run(file_path: Path) -> dict:
        calls.append(str(file_path))
        return {"document_type": "architect_plan", "document_description": "test",
                "concepts_found": []}

    monkeypatch.setattr(vision_probe, "_run_probe", fake_run)

    vision_probe.probe_unreadable_files([fe], tmp_path)

    assert any("1.0.pdf" in c for c in calls), (
        "layout-heavy vector PDF should have been probed; "
        f"probe calls: {calls}"
    )


def test_probe_gate_skips_legacy_pdf_output_dir(tmp_path, monkeypatch):
    """Files inside legacy Eva-output dirs (PDF/, PDF-V0/, PDF V0/, PDF_V0/)
    are NOT probed even if they otherwise meet the widened gate."""
    from automation.concept_scout import vision_probe
    from automation.concept_scout.models import FileEntry

    for legacy_dir in ("PDF", "PDF-V0", "PDF_V0", "PDF V0"):
        (tmp_path / legacy_dir).mkdir(exist_ok=True)
        fake = tmp_path / legacy_dir / "informe.pdf"
        fake.write_bytes(b"%PDF-1.4\n%%EOF\n")

    entries = [
        FileEntry(
            path=f"{d}/informe.pdf",
            type="pdf_vector",
            size_kb=100,
            text_extractable=True,
            concepts_detected=[],
        )
        for d in ("PDF", "PDF-V0", "PDF_V0", "PDF V0")
    ]

    # If these were probed, the extractor would be called. Stub it to detect calls.
    monkeypatch.setattr(vision_probe, "_extract_page1_text", lambda p: "tiny")
    calls: list[str] = []

    def fake_run(file_path: Path) -> dict:
        calls.append(str(file_path))
        return None

    monkeypatch.setattr(vision_probe, "_run_probe", fake_run)

    vision_probe.probe_unreadable_files(entries, tmp_path)

    assert calls == [], f"legacy-output files should not be probed; got {calls}"


def test_probe_gate_keeps_classic_behavior_for_images(tmp_path, monkeypatch):
    """Regression guard: images with text_extractable=False still routed to probe."""
    from automation.concept_scout import vision_probe
    from automation.concept_scout.models import FileEntry

    fake_img = tmp_path / "ANEXOS" / "F1 SIT.png"
    fake_img.parent.mkdir(parents=True)
    fake_img.write_bytes(b"\x89PNG\r\n\x1a\n")

    fe = FileEntry(
        path="ANEXOS/F1 SIT.png",
        type="image",
        size_kb=1810,
        text_extractable=False,
        concepts_detected=[],
    )

    calls: list[str] = []

    def fake_run(file_path: Path) -> dict:
        calls.append(str(file_path))
        return {"document_type": "map", "document_description": "test",
                "concepts_found": []}

    monkeypatch.setattr(vision_probe, "_run_probe", fake_run)

    vision_probe.probe_unreadable_files([fe], tmp_path)

    assert any("F1 SIT.png" in c for c in calls), \
        f"classic gate for images broke; probe calls: {calls}"


def test_probe_gate_legacy_dir_match_is_case_insensitive(tmp_path, monkeypatch):
    """`PDF/`, `pdf/`, `Pdf-V0/` all count as legacy-output dirs.

    Mirrors the case-insensitive regex matching in
    `automation/file_scanner.py` so a lower-case folder spelling on a
    client's disk doesn't silently re-enable probes on our own outputs.
    """
    from automation.concept_scout import vision_probe
    from automation.concept_scout.models import FileEntry

    for legacy_dir in ("pdf", "Pdf-V0", "PDF v0"):
        (tmp_path / legacy_dir).mkdir(exist_ok=True)
        (tmp_path / legacy_dir / "informe.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")

    entries = [
        FileEntry(
            path=f"{d}/informe.pdf",
            type="pdf_vector",
            size_kb=100,
            text_extractable=True,
            concepts_detected=[],
        )
        for d in ("pdf", "Pdf-V0", "PDF v0")
    ]

    monkeypatch.setattr(vision_probe, "_extract_page1_text", lambda p: "tiny")
    calls: list[str] = []
    monkeypatch.setattr(
        vision_probe, "_run_probe", lambda fp: calls.append(str(fp)) or None,
    )

    vision_probe.probe_unreadable_files(entries, tmp_path)

    assert calls == [], (
        f"case-insensitive legacy match failed; unexpected probes: {calls}"
    )


def test_should_probe_text_pdf_truth_table(tmp_path, monkeypatch):
    """Regression sweep: `_should_probe_text_pdf` reflects the documented
    gate (replaces the three dead-heuristic unit tests).

    Gate fires iff `concepts_detected == []` AND page-1 text length <=
    `_LAYOUT_MAX_TEXT_LEN`. Legacy-dir exclusion lives in the caller
    (`probe_unreadable_files`), so it is exercised in the separate
    `test_probe_gate_skips_legacy_pdf_output_dir` test, not here.
    """
    from automation.concept_scout import vision_probe

    fake_pdf = tmp_path / "x.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    short_text = "titleblock 1/200 Pb+1Pp 7.5m"
    long_text = "El present document descriu en detall el procediment. " * 50
    assert len(long_text) > vision_probe._LAYOUT_MAX_TEXT_LEN

    # (concepts_detected, page1_text, expected)
    cases = [
        ([], short_text, True),                  # fires
        (["architect_name"], short_text, False),  # concepts already found → skip
        ([], long_text, False),                  # prose-heavy → skip
        (["architect_name"], long_text, False),   # both blockers → skip
    ]
    for concepts, text, expected in cases:
        monkeypatch.setattr(vision_probe, "_extract_page1_text", lambda p, _t=text: _t)
        actual = vision_probe._should_probe_text_pdf(fake_pdf, concepts)
        assert actual is expected, (
            f"gate truth-table violation: concepts={concepts!r}, "
            f"text_len={len(text)}, expected={expected}, got={actual}"
        )


# ---------------------------------------------------------------------------
# Regression guard: every vision-detectable concept must exist in the
# concept registry, so signals promoted via `concept_sources_to_signals`
# compete against text signals under a real `source_priority` chain rather
# than landing in phantom groups with the default priority of 50.
# Pre-existing drift (2026-04-22) had vision emit `superficie_*_m2` while
# the YAML defined `superficie_*` — the signals never met their text peers.
# ---------------------------------------------------------------------------

def test_all_vision_detectable_concepts_exist_in_registry():
    from automation.concept_scout.vision_probe import _VISION_DETECTABLE_CONCEPTS
    from automation.schemas.loader import ConceptRegistry

    registry_ids = set(ConceptRegistry().all_concept_ids())
    missing = _VISION_DETECTABLE_CONCEPTS - registry_ids
    assert not missing, (
        f"vision probe emits concept_ids not defined in the registry: "
        f"{sorted(missing)}. Either add them to "
        f"schemas/concepts/report_variables.yaml or rename the vision "
        f"concept_id to match."
    )
