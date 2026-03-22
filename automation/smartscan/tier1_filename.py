"""
SmartScan Tier 1: Expanded filename/path regex classification.

Port and expansion of file_scanner.py patterns to support both
Catalan (CA) and Spanish (ES) naming conventions, plus common
non-standard variants observed across 7 test projects.
"""

from __future__ import annotations

import re
from pathlib import Path

from .confidence import tier1_confidence
from .models import ClassificationTier, FileClassification

# ──────────────────────────────────────────────────────────────
# Informative file patterns (not project documents)
# ──────────────────────────────────────────────────────────────
INFORMATIVE_PATTERNS = [
    (r'^Thumbs\.db$', "Windows thumbnail cache"),
    (r'^~\$', "Word temp file"),
    (r'.*\.tmp$', "Temporary file"),
    (r'.*\.lnk$', "Windows shortcut"),
    (r'^desktop\.ini$', "Windows folder config"),
    (r'.*\.bak$', "Backup file"),
    (r'.*\.lock$', "Lock file"),
]

# ──────────────────────────────────────────────────────────────
# Ignore patterns — exported PDFs, cover docs, etc.
# These are recognized but not assigned a pipeline role.
# ──────────────────────────────────────────────────────────────
IGNORE_PATTERNS = [
    (r'^validation/?$', "output_dir"),
    (r'^user_data\.json$', "our_output"),
    (r'.*_generated.*\.docx$', "our_output"),
    (r'^file_mapping\.json$', "our_output"),
    (r'(?i)^PDF/?$', "exported_pdf_dir"),
    (r'(?i)^PDF[\s_-]?V\d+/?$', "exported_pdf_dir"),
    (r'^ACCEPTACI[OÓ]/?$', "acceptance_dir"),
    (r'(?i)^ACEPTACI[OÓ]N(\s+CASTELLANO)?/?$', "acceptance_dir"),
    (r'.*\.FH\d+$', "freehand_file"),
    (r'(?i).*_PORTADA.*\.doc[x]?$', "cover_doc"),
    (r'(?i).*_portada.*\.doc[x]?$', "cover_doc"),
    (r'(?i).*_DETALLAT.*\.doc$', "detailed_doc"),
    (r'(?i).*EXPLICACI[OÓ].*\.docx?$', "explanation_doc"),
    (r'.*\.msg$', "email_file"),
    (r'(?i)^LLETRA/?$', "letter_dir"),
    (r'(?i)^LETRA/?$', "letter_dir"),
]

# ──────────────────────────────────────────────────────────────
# Role patterns — expanded for CA + ES + common variants
# ──────────────────────────────────────────────────────────────
# Each role has:
#   patterns: list of regex (matched against filename)
#   scopes: list of parent-dir prefixes where the file may live
#           '' = project root, 'ANNEXES' = project/ANNEXES/, etc.
#   is_directory: True for directory roles (photos_dir)
#   prefer: regex for preferred candidate when multiple match
#   combined: dict mapping pattern -> list of secondary roles

ROLE_PATTERNS: dict[str, dict] = {
    # ── Architect plans ──────────────────────────────────────
    'architect_project': {
        'patterns': [r'(?i)^PROJECTE[_\s]*BASIC.*\.pdf$'],
        'scopes': [''],
    },
    'architect_plan_with_points': {
        'patterns': [r'(?i)^A\.\d+\s*amb\s*punts.*\.pdf$'],
        'scopes': [''],
    },
    'architect_plan': {
        'patterns': [
            r'^A\.\d+\.pdf$',
            r'^A\.\d+\s.*\.pdf$',
            r'(?i)^ampliaci[oó].*\.(png|jpe?g|pdf)$',
        ],
        'scopes': [''],
        'prefer': r'^A\.\d+\.pdf$',
    },
    'field_croquis': {
        'patterns': [r'(?i)^CROQUIS\.(jpe?g|png|pdf)$'],
        'scopes': [''],
    },

    # ── DPSH field sheet (PENETROS) ──────────────────────────
    'dpsh_field_sheet': {
        'patterns': [
            r'^PENETROS.*\.pdf$',
            r'(?i)^\d+\s*-?\s*PENETROS.*\.pdf$',
            r'(?i)^PENETROS\s*\+\s*SONDEIG.*\.pdf$',
            # ES variants
            r'(?i)^PENETR[OÓ]METRO.*\.pdf$',
            # Image variants (phone photos of field sheets)
            r'^PENETROS.*\.(jpe?g|png)$',
            r'(?i)^\d+\s*-?\s*PENETROS.*\.(jpe?g|png)$',
        ],
        'scopes': [''],
        'combined': {
            r'(?i)^PENETROS\s*\+\s*SONDEIG.*\.pdf$': ['sondeig_field_sheet'],
        },
    },

    # ── DPSH Excel ───────────────────────────────────────────
    'dpsh_excel': {
        'patterns': [r'(?i).*dpsh.*\.xls[x]?$'],
        'scopes': ['ANNEXES', 'ANEXOS', 'ANEJOS'],
    },

    # ── Sondeig annex (formatted PDF, vectorial) ─────────────
    'sondeig_annex': {
        'patterns': [
            r'(?i)\d+_sondeig\.pdf$',
            r'(?i)\d+_sondeos?\.pdf$',
        ],
        'scopes': [
            'PDF/ANNEXES', 'ANNEXES',
            'PDF-V0/ANNEXES',
            'PDF/ANEJOS', 'ANEJOS',
            'PDF/ANEXOS', 'ANEXOS',
            'PDF_V0/ANEJOS', 'PDF_V0/ANEXOS',
        ],
    },

    # ── Sondeig field sheet ──────────────────────────────────
    'sondeig_field_sheet': {
        'patterns': [
            r'^SONDEIG.*\.pdf$',
            r'(?i)^PENETROS\s*\+\s*SONDEIG.*\.pdf$',
            # ES variants
            r'(?i)^SONDEO[S]?\.pdf$',
        ],
        'scopes': [''],
    },

    # ── Correlation section (tall) ───────────────────────────
    'correlation_section': {
        'patterns': [
            r'(?i)^tall.*\.pdf$',
            # ES variants
            r'(?i)^corte.*correlaci[oó]n.*\.pdf$',
            r'(?i)^secci[oó]n.*\.pdf$',
        ],
        'scopes': [''],
    },

    # ── Lab order ────────────────────────────────────────────
    'lab_order': {
        'patterns': [r'(?i)^comanda\s*laboratori.*\.xls[x]?$'],
        'scopes': [''],
    },

    # ── Situation plan ───────────────────────────────────────
    'situation_plan': {
        'patterns': [
            r'(?i)^pl.*situaci.*\.pdf$',
            r'(?i)^pl[\.\s]?\s*situ.*\.pdf$',
            r'(?i)^\d+[_\s]pl[àa]n[oò]l.*situaci[oó].*\.pdf$',
            # ES variants
            r'(?i)^plano.*situaci[oó]n.*\.pdf$',
        ],
        'scopes': ['', 'PDF/ANNEXES'],
    },

    # ── Photos directory ─────────────────────────────────────
    'photos_dir': {
        'patterns': [
            r'^FOTOGRAFIES$',
            r'(?i)^FOTOS.*$',
            r'(?i)^FOTOGRAF[IÍ]AS$',
        ],
        'scopes': [''],
        'is_directory': True,
    },

    # ── Reference report ─────────────────────────────────────
    'reference_report': {
        'patterns': [
            r'(?i)^\d+_informe(_v\d+)?\.doc$',
            r'(?i)^\d+_informe(_v\d+)?\.docx$',
        ],
        'scopes': [''],
    },

    # ── Lab results PDF ──────────────────────────────────────
    'lab_results_pdf': {
        'patterns': [r'(?i)^lab[_-]?sig\.pdf$'],
        'scopes': ['PDF/ANNEXES'],
    },

    # ── GTL report ───────────────────────────────────────────
    'gtl_report': {
        'patterns': [r'(?i)^\d+-GTL-\d+\s.*\.pdf$'],
        'scopes': [''],
    },

    # ── Report figures (images for specific report slots) ────
    'figure_situation_map': {
        'patterns': [
            r'(?i)^F\d+[\s_]*(SIT|UBI).*\.(png|jpe?g|pdf)$',
        ],
        'scopes': ['ANNEXES/ALTRES', 'ANNEXES/Altres', 'ANEXOS/OTROS'],
    },
    'figure_test_points': {
        'patterns': [
            r'(?i)^F\d+[\s_]*(PUNTS?|PUNT).*\.(png|jpe?g|pdf)$',
        ],
        'scopes': ['ANNEXES/ALTRES', 'ANNEXES/Altres', 'ANEXOS/OTROS'],
    },
    'figure_geological_map': {
        'patterns': [
            r'(?i)^(M\d+|F\d+[\s_]*MGEOL).*\.(png|jpe?g)$',
        ],
        'scopes': ['ANNEXES/ALTRES', 'ANNEXES/Altres', 'ANEXOS/OTROS'],
    },
    'figure_correlation': {
        'patterns': [
            r'(?i)^F\d+[\s_]*TALL.*\.(png|jpe?g)$',
        ],
        'scopes': ['ANNEXES/ALTRES', 'ANNEXES/Altres', 'ANEXOS/OTROS'],
    },
}


# Directories whose contents are exported copies (not source data).
# Files inside are auto-marked "informative" unless they match a role.
_EXPORT_DIR_PATTERNS = [
    re.compile(r'(?i)^PDF(/|$)'),
    re.compile(r'(?i)^PDF[\s_-]?V\d+(/|$)'),
]

# Directories whose contents are photos/acceptance — informative.
_CONTENT_DIR_PATTERNS = [
    re.compile(r'(?i)^FOTOGRAFIES(/|$)'),
    re.compile(r'(?i)^FOTOS[^/]*(/|$)'),
    re.compile(r'(?i)^FOTOGRAF[IÍ]AS(/|$)'),
    re.compile(r'(?i)^ACCEPTACI[OÓ](/|$)'),
    re.compile(r'(?i)^ACEPTACI[OÓ]N[^/]*(/|$)'),
]


def _is_inside_export_dir(rel_path: str) -> bool:
    """Check if a path is inside an exported PDF directory."""
    return any(p.match(rel_path) for p in _EXPORT_DIR_PATTERNS)


def _is_inside_content_dir(rel_path: str) -> bool:
    """Check if a path is inside a photos/acceptance directory."""
    return any(p.match(rel_path) for p in _CONTENT_DIR_PATTERNS)


# Known field photo filename patterns — files matching these in FOTOGRAFIES
# are definitely photos, not documents. Everything else falls through to Tier 2/3.
_PHOTO_NAME_PATTERNS = [
    re.compile(r'^P\d+', re.IGNORECASE),
    re.compile(r'^S\d+', re.IGNORECASE),
    re.compile(r'^SPT', re.IGNORECASE),
    re.compile(r'^DETALL', re.IGNORECASE),
    re.compile(r'^EMPL\s', re.IGNORECASE),
    re.compile(r'^ZONA\s', re.IGNORECASE),
    re.compile(r'^INTERIOR', re.IGNORECASE),
    re.compile(r'(?i)^DES\s+(DE|DEL)\s'),
    re.compile(r'^vista[_\s]general', re.IGNORECASE),
    re.compile(r'^maquina[_\s]', re.IGNORECASE),
    re.compile(r'^m[àa]quina[_\s]', re.IGNORECASE),
    re.compile(r'^Imag[eo]n?\s+de\s+WhatsApp', re.IGNORECASE),
    re.compile(r'^Imatge\s+de\s+WhatsApp', re.IGNORECASE),
    re.compile(r'^WhatsApp\s+Image', re.IGNORECASE),
    re.compile(r'^IMG-\d{8}', re.IGNORECASE),
    re.compile(r'^detall[_\s]material', re.IGNORECASE),
    re.compile(r'^Thumbs\.db$'),
    re.compile(r'^spt\s', re.IGNORECASE),
]


def _is_known_photo(name: str) -> bool:
    """Check if filename matches known field photo patterns."""
    return any(p.match(name) for p in _PHOTO_NAME_PATTERNS)


def classify_tier1(
    project_path: Path,
    entries: list[tuple[str, bool]],
) -> list[FileClassification]:
    """
    Classify files using Tier 1 (filename/path regex).

    Handles fully recursive file trees. Files inside export dirs
    (PDF/, PDF-V0/) and content dirs (FOTOGRAFIES/, ACCEPTACIO/)
    are auto-marked informative unless they match a specific role.

    Args:
        project_path: Absolute path to the project folder
        entries: List of (relative_path, is_directory) tuples

    Returns:
        List of FileClassification for ALL entries that matched
        a pattern (role, informative, or ignore). Files that don't
        match anything are NOT returned here (handled by classifier).
    """
    results: list[FileClassification] = []

    for rel_path, is_dir in entries:
        name = rel_path.split('/')[-1]
        parent = rel_path.rsplit('/', 1)[0] if '/' in rel_path else ''

        # ── 1. Check informative filename patterns (Thumbs.db, ~$, etc.)
        if not is_dir:
            matched_info = False
            for pattern, desc in INFORMATIVE_PATTERNS:
                if re.match(pattern, name):
                    results.append(FileClassification(
                        file_path=rel_path,
                        role=None,
                        confidence=1.0,
                        tier=ClassificationTier.FILENAME,
                        category="informative",
                        summary=desc,
                        is_directory=False,
                    ))
                    matched_info = True
                    break
            if matched_info:
                continue

        # ── 2. Check ignore patterns on filename
        check_name = name + '/' if is_dir else name
        matched_ignore = False
        for pattern, reason in IGNORE_PATTERNS:
            if re.match(pattern, check_name):
                results.append(FileClassification(
                    file_path=rel_path,
                    role=None,
                    confidence=1.0,
                    tier=ClassificationTier.FILENAME,
                    category="informative",
                    summary=reason,
                    is_directory=is_dir,
                ))
                matched_ignore = True
                break
        if matched_ignore:
            continue

        # ── 3. Files inside export dirs → informative (exported copy)
        # Must check BEFORE role patterns so exported copies don't steal roles
        # from source files. Exception: sondeig_annex lives in PDF/ANNEXES.
        in_export = _is_inside_export_dir(rel_path)
        if in_export and not is_dir:
            # Allow specific roles that legitimately live in export dirs
            clf = _match_role(rel_path, name, parent, is_dir,
                              restrict_roles={'sondeig_annex', 'lab_results_pdf'})
            if clf:
                results.append(clf)
                continue
            results.append(FileClassification(
                file_path=rel_path,
                role=None,
                confidence=1.0,
                tier=ClassificationTier.FILENAME,
                category="informative",
                summary="exported_pdf_copy",
                is_directory=False,
            ))
            continue

        # ── 4. Files inside content dirs → selective handling
        if not is_dir and _is_inside_content_dir(rel_path):
            # Check if filename looks like a known field photo
            if _is_known_photo(name):
                results.append(FileClassification(
                    file_path=rel_path,
                    role=None,
                    confidence=1.0,
                    tier=ClassificationTier.FILENAME,
                    category="informative",
                    summary="photo_or_acceptance",
                    is_directory=False,
                ))
                continue
            # Not a known photo — try role matching with root scope
            # (content dir files like PENETROS.jpeg have non-standard parents)
            clf = _match_role(rel_path, name, '', is_dir)
            if clf:
                # Slightly lower confidence: secondary copy in photos dir
                clf.confidence = max(clf.confidence - 0.05, 0.5)
                results.append(clf)
                continue
            # Unknown file in content dir — leave for Tier 2/3
            continue

        # ── 5. Try role patterns (scoped matching)
        clf = _match_role(rel_path, name, parent, is_dir)
        if clf:
            results.append(clf)
            continue

        # Not matched — leave for Tier 2 or unclassified handling

    return results


def _match_role(
    rel_path: str,
    name: str,
    parent: str,
    is_dir: bool,
    restrict_roles: set[str] | None = None,
) -> FileClassification | None:
    """Try to match a single entry against role patterns.

    Args:
        restrict_roles: If set, only try these specific roles (for export dirs).
    """
    for role_name, config in ROLE_PATTERNS.items():
        if restrict_roles and role_name not in restrict_roles:
            continue
        expects_dir = config.get('is_directory', False)
        scopes = config.get('scopes', [''])

        if expects_dir != is_dir:
            continue

        if not _in_scope(parent, scopes):
            continue

        for pattern in config['patterns']:
            if re.match(pattern, name):
                # Check if this is a combined file
                combined_roles: list[str] = []
                combined_config = config.get('combined', {})
                for comb_pattern, secondary_roles in combined_config.items():
                    if re.match(comb_pattern, name):
                        combined_roles = secondary_roles
                        break

                return FileClassification(
                    file_path=rel_path,
                    role=role_name,
                    confidence=tier1_confidence(exact_match=True),
                    tier=ClassificationTier.FILENAME,
                    is_directory=is_dir,
                    is_combined=bool(combined_roles),
                    combined_roles=combined_roles,
                    category="classified",
                )

    return None


def _in_scope(parent: str, scopes: list[str]) -> bool:
    """Check if the parent directory matches any of the allowed scopes."""
    for scope in scopes:
        if not scope and not parent:
            return True
        if scope and parent == scope:
            return True
    return False
