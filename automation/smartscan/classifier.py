"""
SmartScan classifier orchestrator.

Runs 3-tier classification: filename → fingerprint → vision.
Each tier only processes files not yet classified by previous tiers.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .models import ClassificationTier, FileClassification, SmartScanResult
from .tier1_filename import classify_tier1
from .tier2_fingerprint import classify_tier2
from .tier3_vision import classify_tier3

logger = logging.getLogger(__name__)


# Directories whose contents are exported copies — files here are
# auto-marked "informative" unless they match a specific role pattern.
_EXPORT_DIRS = {
    'PDF', 'PDF-V0', 'PDF_V0', 'PDF V0',
    'PDF/LLETRA', 'PDF/LETRA',
    'PDF-V0/LLETRA', 'PDF_V0/LETRA',
}


def scan_project(
    project_path: str | Path,
    max_tier: int = 2,
    include_vision: bool = False,
) -> SmartScanResult:
    """
    Scan a project folder and classify every file.

    Args:
        project_path: Path to the project folder
        max_tier: Maximum tier to use (1=regex only, 2=+fingerprint, 3=+vision)
        include_vision: If True, run Tier 3 even if max_tier<3 (explicit override)

    Returns:
        SmartScanResult with all classifications, warnings, and timing.
    """
    project_path = Path(project_path)
    start = time.monotonic()

    if not project_path.exists():
        return SmartScanResult(
            project_path=str(project_path),
            warnings=[f"Project path not found: {project_path}"],
        )

    # ── Step 1: Enumerate all files ──────────────────────────
    entries = _enumerate_files(project_path)
    logger.info(f"SmartScan: {len(entries)} entries found in {project_path.name}")

    # ── Step 2: Tier 1 — Filename regex ──────────────────────
    tier1_results = classify_tier1(project_path, entries)
    classified_paths = {c.file_path for c in tier1_results if c.role or c.category == "informative"}

    all_classifications: list[FileClassification] = list(tier1_results)

    # ── Step 3: Tier 2 — Fingerprinting (if enabled) ─────────
    tier2_needs_vision: list[FileClassification] = []
    if max_tier >= 2:
        tier2_results = classify_tier2(project_path, entries, classified_paths)
        for clf in tier2_results:
            if clf.category == "needs_vision":
                # Don't mark as classified — let Tier 3 process these
                tier2_needs_vision.append(clf)
            else:
                classified_paths.add(clf.file_path)
        all_classifications.extend(tier2_results)

    # ── Step 4: Tier 3 — Vision (if enabled) ─────────────────
    if max_tier >= 3 or include_vision:
        tier3_results = classify_tier3(project_path, entries, classified_paths)
        for clf in tier3_results:
            classified_paths.add(clf.file_path)
        all_classifications.extend(tier3_results)
    else:
        # Tier 3 not running — needs_vision items stay as-is in results
        for clf in tier2_needs_vision:
            classified_paths.add(clf.file_path)

    # ── Step 5: Handle remaining unclassified files ──────────
    unclassified: list[FileClassification] = []
    for rel_path, is_dir in entries:
        if rel_path not in classified_paths:
            abs_path = project_path / rel_path
            summary = _describe_unclassified(abs_path, is_dir)
            unclassified.append(FileClassification(
                file_path=rel_path,
                role=None,
                confidence=0.0,
                tier=ClassificationTier.FILENAME,
                is_directory=is_dir,
                category="unknown",
                summary=summary,
            ))

    # ── Step 6: Resolve conflicts ────────────────────────────
    classified, warnings = _resolve_conflicts(all_classifications)

    # ── Step 7: Build result ─────────────────────────────────
    duration_ms = int((time.monotonic() - start) * 1000)

    return SmartScanResult(
        project_path=str(project_path),
        classifications=classified,
        unclassified=unclassified,
        warnings=warnings,
        scan_duration_ms=duration_ms,
    )


def _enumerate_files(project_path: Path) -> list[tuple[str, bool]]:
    """
    Enumerate ALL files and directories in a project, recursively.

    Every single file is listed so that SmartScan can account for it.
    Returns (relative_path, is_directory) tuples sorted by path.
    """
    entries: list[tuple[str, bool]] = []

    def _recurse(current: Path, prefix: str):
        if not current.is_dir():
            return
        for item in sorted(current.iterdir()):
            rel = f"{prefix}/{item.name}" if prefix else item.name
            entries.append((rel, item.is_dir()))
            if item.is_dir():
                _recurse(item, rel)

    _recurse(project_path, "")
    return entries


def _describe_unclassified(abs_path: Path, is_dir: bool) -> str:
    """Generate a human-readable summary for an unclassified file."""
    if is_dir:
        try:
            count = sum(1 for _ in abs_path.iterdir())
            return f"Directory with {count} items"
        except Exception:
            return "Directory"

    try:
        size = abs_path.stat().st_size
        ext = abs_path.suffix.lower()
        size_str = f"{size / 1024:.0f}KB" if size > 1024 else f"{size}B"

        if ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'):
            return f"Image ({size_str})"
        elif ext in ('.xls', '.xlsx'):
            return f"Excel ({size_str})"
        elif ext == '.pdf':
            return f"PDF ({size_str})"
        elif ext in ('.doc', '.docx'):
            return f"Word document ({size_str})"
        elif ext == '.msg':
            return f"Email ({size_str})"
        elif ext == '.txt':
            # Try to read first line
            try:
                first_line = abs_path.read_text(encoding='utf-8', errors='ignore')[:100]
                return f"Text: {first_line.strip()}"
            except Exception:
                return f"Text file ({size_str})"
        else:
            return f"{ext or 'no extension'} ({size_str})"
    except Exception:
        return "Unknown file"


def _resolve_conflicts(
    classifications: list[FileClassification],
) -> tuple[list[FileClassification], list[str]]:
    """
    Resolve conflicts when multiple classifications exist for the same role.

    Rules:
    1. Higher confidence wins
    2. Lower tier number wins on tie (Tier 1 > Tier 2 > Tier 3)
    3. Combined files can hold multiple roles
    4. Losers keep their alternate_roles info but role is cleared
    5. Warnings generated for close-confidence conflicts
    """
    warnings: list[str] = []

    # Group by role
    role_candidates: dict[str, list[FileClassification]] = {}
    non_role: list[FileClassification] = []

    for clf in classifications:
        if clf.role:
            role_candidates.setdefault(clf.role, []).append(clf)
        else:
            non_role.append(clf)

    # Pick best per role, track losers
    best: dict[str, FileClassification] = {}
    loser_paths: set[str] = set()  # Files that lost a role conflict

    for role, candidates in role_candidates.items():
        candidates.sort(key=lambda c: (-c.confidence, c.tier.value))
        winner = candidates[0]
        best[role] = winner

        if len(candidates) > 1 and candidates[1].confidence > winner.confidence - 0.15:
            warnings.append(
                f"Role '{role}': close match between "
                f"{winner.file_path} ({winner.confidence:.0%}) and "
                f"{candidates[1].file_path} ({candidates[1].confidence:.0%})"
            )

        # Losers: demote to non-role (keep fingerprint data for debug)
        for loser in candidates[1:]:
            if loser.file_path not in loser_paths:
                loser_paths.add(loser.file_path)
                non_role.append(FileClassification(
                    file_path=loser.file_path,
                    role=None,
                    confidence=loser.confidence,
                    tier=loser.tier,
                    alternate_roles=[{'role': loser.role, 'confidence': loser.confidence}],
                    fingerprint_data=loser.fingerprint_data,
                    category="suggestion" if loser.confidence >= 0.3 else "unknown",
                    summary=f"Also matches '{loser.role}' but {winner.file_path} is preferred",
                ))

    # Build final list: winning classifications + informative/unclassified + losers
    result: list[FileClassification] = list(best.values())

    # Add combined role entries
    for clf in best.values():
        for cr in clf.combined_roles:
            if cr not in best:
                combined_clf = FileClassification(
                    file_path=clf.file_path,
                    role=cr,
                    confidence=clf.confidence,
                    tier=clf.tier,
                    is_combined=True,
                    combined_roles=[],
                    category=clf.category,
                )
                result.append(combined_clf)

    result.extend(non_role)

    return result, warnings
