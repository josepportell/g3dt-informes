#!/usr/bin/env python3
"""
File Scanner for G3DT Report Generation (Fase 0)

Scans a project folder, classifies each file by its role in the report
generation pipeline, and saves a file_mapping.json that downstream tools read.

Usage:
    from automation.file_scanner import FileScanner

    scanner = FileScanner('reference-material/4001612-bell-lloc')
    mapping = scanner.scan()
    print(scanner.summary(mapping))
    scanner.save(mapping)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCANNER_VERSION = "2.2"

# Role definitions: description + optional vision_type for Claude API extraction.
# vision_type maps to extraction prompts: "planol", "dpsh", "sondeig"
# First role with a given vision_type wins (order matters).
ROLE_DEFINITIONS = {
    'architect_plan':       {"desc": "Planol de l'arquitecte",                   "vision_type": "planol"},
    'architect_plan_with_points': {"desc": "Planol de l'arquitecte amb punts d'assaig", "vision_type": "planol"},
    'architect_project':    {"desc": "Projecte basic de l'arquitecte (normativa + planol)", "vision_type": "projecte_arquitecte"},
    'dpsh_field_sheet':     {"desc": "Full de camp DPSH (penetrometres)",         "vision_type": "dpsh"},
    'dpsh_excel':           {"desc": "Excel DPSH amb dades transcrites"},
    'sondeig_annex':        {"desc": "Annex formatat del sondeig (PDF vectorial)",   "vision_type": "sondeig_annex"},
    'sondeig_field_sheet':  {"desc": "Full de camp sondeig a rotacio",            "vision_type": "sondeig"},
    'correlation_section':  {"desc": "Tall de correlacio"},
    'lab_order':            {"desc": "Comanda de laboratori"},
    'situation_plan':       {"desc": "Planol de situacio",                        "vision_type": "planol"},
    'photos_dir':           {"desc": "Carpeta de fotografies de camp"},
    'reference_report':     {"desc": "Informe .doc de referencia"},
    'lab_results_pdf':      {"desc": "Resultats de laboratori (PDF)"},
    'gtl_report':           {"desc": "Informe GTL del laboratori"},
    # ── New roles from SmartScan v2 (image classification + report figures) ──
    'field_croquis':        {"desc": "Croquis de camp amb punts d'assaig",       "vision_type": "planol"},
    'figure_situation_map': {"desc": "Imatge mapa de situacio (per informe)"},
    'figure_test_points':   {"desc": "Imatge mapa de punts d'assaig (per informe)"},
    'figure_geological_map': {"desc": "Imatge mapa geologic (per informe)"},
    'figure_correlation':   {"desc": "Imatge tall de correlacio (per informe)"},
    'photo_test_point':     {"desc": "Foto punt d'assaig"},
    'photo_dpsh_equipment': {"desc": "Foto equip DPSH"},
    'photo_sondeig_equipment': {"desc": "Foto equip sondeig"},
    'photo_spt_sample':     {"desc": "Foto mostra SPT"},
    'photo_site_overview':  {"desc": "Foto vista general de l'obra"},
    'field_photo':          {"desc": "Foto de camp generica (WhatsApp/mobil)"},
    'project_email':        {"desc": "Correu del projecte (.msg)"},
}

def _role_desc(role_name: str) -> str:
    """Get description string from a role definition (supports old str and new dict format)."""
    defn = ROLE_DEFINITIONS.get(role_name, {})
    if isinstance(defn, str):
        return defn
    return defn.get('desc', role_name)

def get_vision_type(role_name: str) -> str | None:
    """Get the vision extraction type for a role, or None if no vision needed."""
    defn = ROLE_DEFINITIONS.get(role_name, {})
    if isinstance(defn, dict):
        return defn.get('vision_type')
    return None

REQUIRED_ROLES = [
    'architect_plan',
    'dpsh_field_sheet',
    'sondeig_field_sheet',
    'correlation_section',
]

# Patterns for combined files that fill multiple roles.
# Key = primary role matched, value = list of secondary roles to also assign.
COMBINED_ROLES = {
    'dpsh_field_sheet': {
        'patterns': [r'(?i)^PENETROS\s*\+\s*SONDEIG.*\.pdf$'],
        'also_assigns': ['sondeig_field_sheet'],
    },
}

ROLE_PATTERNS = {
    # architect_project FIRST — Eva renames the architect's multi-page
    # project PDF to "PROJECTE_BASIC*.pdf" for easy identification.
    'architect_project': {
        'patterns': [r'(?i)^PROJECTE[_\s]*BASIC.*\.pdf$'],
        'search_in': '',
    },
    # architect_plan_with_points BEFORE architect_plan so the more
    # specific "amb punts" pattern wins over the broad A.XX pattern.
    'architect_plan_with_points': {
        'patterns': [r'(?i)^A\.\d+\s*amb\s*punts.*\.pdf$'],
        'search_in': '',
    },
    'architect_plan': {
        'patterns': [r'^A\.\d+\.pdf$', r'^A\.\d+\s.*\.pdf$'],
        'search_in': '',
        'prefer': r'^A\.\d+\.pdf$',
    },
    'dpsh_field_sheet': {
        'patterns': [
            r'^PENETROS.*\.pdf$',
            r'(?i)^\d+\s*-?\s*PENETROS.*\.pdf$',
            r'(?i)^PENETROS\s*\+\s*SONDEIG.*\.pdf$',
        ],
        'search_in': '',
    },
    'dpsh_excel': {
        'patterns': [r'(?i).*dpsh.*\.xls'],
        'search_in': 'ANNEXES',
    },
    'sondeig_annex': {
        'patterns': [r'(?i)\d+_sondeig\.pdf$'],
        'search_in': ['PDF/ANNEXES', 'ANNEXES', 'PDF-V0/ANNEXES'],
    },
    'sondeig_field_sheet': {
        'patterns': [
            r'^SONDEIG.*\.pdf$',
            r'(?i)^PENETROS\s*\+\s*SONDEIG.*\.pdf$',
        ],
        'search_in': '',
    },
    'correlation_section': {
        'patterns': [r'(?i)^tall.*\.pdf$'],
        'search_in': '',
    },
    'lab_order': {
        'patterns': [r'(?i)^comanda\s*laboratori.*\.xls'],
        'search_in': '',
    },
    'situation_plan': {
        'patterns': [
            r'(?i)^pl.*situaci.*\.pdf$',
            r'(?i)^pl[\.\s]?\s*situ.*\.pdf$',
            r'(?i)^\d+[_\s]pl[àa]n[oò]l.*situaci[oó].*\.pdf$',
        ],
        'search_in': ['', 'PDF/ANNEXES'],
    },
    'photos_dir': {
        'patterns': ['FOTOGRAFIES'],
        'search_in': '',
        'is_directory': True,
    },
    'reference_report': {
        'patterns': [r'(?i)^\d+_informe(_v\d+)?\.doc$'],
        'search_in': '',
    },
    'lab_results_pdf': {
        'patterns': [r'(?i)^lab[_-]?sig\.pdf$'],
        'search_in': 'PDF/ANNEXES',
    },
    'gtl_report': {
        'patterns': [r'(?i)^\d+-GTL-\d+\s.*\.pdf$'],
        'search_in': '',
    },
}

# Ignore patterns — checked AFTER role patterns so that roles take priority.
# Specific .doc patterns replace the old blanket .*\.doc$ rule.
IGNORE_PATTERNS = [
    (r'^validation/?$', 'output_dir'),
    (r'^user_data\.json$', 'our_output'),
    (r'.*_generated\.docx$', 'our_output'),
    (r'^file_mapping\.json$', 'our_output'),
    (r'^PDF/?$', 'exported_pdf_dir'),
    (r'^PDF V0/?$', 'exported_pdf_dir'),
    (r'(?i)^PDF-V0/?$', 'exported_pdf_dir'),
    (r'^ACCEPTACIO/?$', 'acceptance_dir'),
    (r'.*\.FH11$', 'freehand_file'),
    (r'(?i).*_PORTADA.*\.doc$', 'cover_doc'),
    (r'(?i).*_DETALLAT.*\.doc$', 'detailed_doc'),
    (r'(?i).*EXPLICACI[OÓ].*\.docx?$', 'explanation_doc'),
    (r'.*\.docx$', 'legacy_word'),
    (r'.*\.msg$', 'email_file'),
    (r'^~\$', 'temp_file'),
    (r'^Thumbs\.db$', 'temp_file'),
    (r'.*\.tmp$', 'temp_file'),
    (r'.*\.txt$', 'text_file'),
    (r'(?i)^ALTRES/?$', 'misc_subdir'),
]

CONFIDENCE_MAP = {'high': 'alta', 'medium': 'mitjana', 'low': 'baixa'}


@dataclass
class FileRole:
    path: str
    confidence: str
    detection: str
    is_combined: bool = False
    vision_type: str | None = None


@dataclass
class IgnoredFile:
    path: str
    reason: str


@dataclass
class FileMapping:
    roles: dict[str, FileRole] = field(default_factory=dict)
    ignored: list[IgnoredFile] = field(default_factory=list)
    unassigned: list[str] = field(default_factory=list)
    # Provenance for attachments extracted from .msg files
    # (populated by email_attachment_classifier, persisted in file_mapping.json)
    email_attachments: dict[str, dict] = field(default_factory=dict)

    @property
    def needs_confirmation(self) -> bool:
        """True if there are ambiguities or required roles missing."""
        missing_required = [r for r in REQUIRED_ROLES if r not in self.roles]
        return bool(missing_required) or bool(self.unassigned)


class FileScanner:
    """Scans a project folder and classifies files for report generation."""

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path)

    def scan(self) -> FileMapping:
        """
        Scan project folder and classify files.

        Lists root, ANNEXES/, and PDF/ANNEXES/ non-recursively, then classifies
        each entry against role patterns first, then ignore patterns, or marks
        it unassigned.
        """
        mapping = FileMapping()
        classified_paths: set[str] = set()

        entries = self._list_entries()

        for rel_path, is_dir, auxiliary in entries:
            name = rel_path.split('/')[-1]
            display = rel_path + '/' if is_dir else rel_path

            # Phase 1: Check role patterns FIRST (before ignores)
            matched_role = self._match_role(rel_path, name, is_dir)
            if matched_role:
                role_name, confidence = matched_role
                if role_name not in mapping.roles:
                    detection = 'directory_name' if is_dir else 'filename_pattern'
                    mapping.roles[role_name] = FileRole(
                        path=rel_path,
                        confidence=confidence,
                        detection=detection,
                        vision_type=get_vision_type(role_name),
                    )
                    classified_paths.add(rel_path)

                    # Handle combined files: auto-assign secondary roles
                    self._assign_combined_roles(
                        mapping, role_name, rel_path, name, classified_paths,
                    )
                else:
                    mapping.unassigned.append(rel_path)
                    classified_paths.add(rel_path)
                continue

            # Auxiliary entries (e.g. PDF/ANNEXES) that don't match a role
            # are silently ignored — they're exported copies, not inputs.
            if auxiliary:
                mapping.ignored.append(IgnoredFile(path=display, reason='exported_annex_pdf'))
                classified_paths.add(rel_path)
                continue

            # Phase 2: Check ignore patterns
            check_name = name + '/' if is_dir else name
            ignored = False
            for pattern, reason in IGNORE_PATTERNS:
                if re.match(pattern, check_name):
                    mapping.ignored.append(IgnoredFile(path=display, reason=reason))
                    classified_paths.add(rel_path)
                    ignored = True
                    break
            if ignored:
                continue

            # Phase 3: Not matched, not ignored
            if rel_path not in classified_paths:
                if is_dir and name in ('ANNEXES', 'PDF'):
                    classified_paths.add(rel_path)
                    continue
                mapping.unassigned.append(rel_path)
                classified_paths.add(rel_path)

        # Both sondeig_field_sheet and sondeig_annex run vision when present.
        # They produce different outputs (field-sheet -> sondeig_extracted.json
        # for layers/SPT/depths; annex -> sondeig_annex_extracted.json for the
        # authoritative `num_geological_levels` from "Unitat litològica").
        # `vision_normalizer.load_sondeig_merged()` merges both, with the
        # annex's geological_levels overriding when present.

        # Phase 4: handle roles with 'prefer' -- demote non-preferred candidates
        self._apply_preferences(mapping)

        logger.info(
            f"File scan: {len(mapping.roles)} roles, "
            f"{len(mapping.ignored)} ignored, "
            f"{len(mapping.unassigned)} unassigned"
        )
        return mapping

    def save(self, mapping: FileMapping) -> Path:
        """Save mapping to file_mapping.json in project folder."""
        data = {
            'roles': {
                name: {
                    'path': role.path,
                    'confidence': role.confidence,
                    'detection': role.detection,
                    **(({'is_combined': True} if role.is_combined else {})),
                    'vision_type': role.vision_type,
                }
                for name, role in mapping.roles.items()
            },
            'ignored': [
                {'path': ig.path, 'reason': ig.reason}
                for ig in mapping.ignored
            ],
            'unassigned': mapping.unassigned,
            'email_attachments': mapping.email_attachments,
            '_metadata': {
                'scanned_at': datetime.now(timezone.utc).isoformat(),
                'confirmed_by_user': False,
                'scanner_version': SCANNER_VERSION,
            },
        }
        out_path = self.project_path / 'file_mapping.json'
        out_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        logger.info(f"Saved file mapping to {out_path}")
        return out_path

    def load(self) -> FileMapping | None:
        """Load existing file_mapping.json, return None if not found or invalid."""
        json_path = self.project_path / 'file_mapping.json'
        if not json_path.exists():
            return None
        try:
            data = json.loads(json_path.read_text(encoding='utf-8'))
            mapping = FileMapping()
            for name, role_data in data.get('roles', {}).items():
                # vision_type: use JSON value if key present (even if None = suppressed),
                # only fall back to ROLE_DEFINITIONS for legacy files without the key
                vt = role_data.get('vision_type') if 'vision_type' in role_data else get_vision_type(name)
                # Migration: legacy mappings suppressed sondeig_field_sheet's
                # vision_type when sondeig_annex coexisted. Restore the default
                # so both extractions run (annex + field sheet are merged later).
                if name == 'sondeig_field_sheet' and vt is None:
                    vt = get_vision_type(name)
                mapping.roles[name] = FileRole(
                    path=role_data['path'],
                    confidence=role_data['confidence'],
                    detection=role_data['detection'],
                    is_combined=role_data.get('is_combined', False),
                    vision_type=vt,
                )
            for ig_data in data.get('ignored', []):
                mapping.ignored.append(IgnoredFile(
                    path=ig_data['path'],
                    reason=ig_data['reason'],
                ))
            mapping.unassigned = list(data.get('unassigned', []))
            mapping.email_attachments = dict(data.get('email_attachments', {}))
            return mapping
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning(f"Could not load file_mapping.json: {exc}")
            return None

    def summary(self, mapping: FileMapping) -> str:
        """Human-readable summary in Catalan."""
        sep = '=' * 60
        lines = [sep, 'Fase 0: Mapeig de fitxers', sep]

        for role_name in ROLE_DEFINITIONS:
            if role_name in mapping.roles:
                role = mapping.roles[role_name]
                conf = CONFIDENCE_MAP.get(role.confidence, role.confidence)
                combined = ' [combinat]' if role.is_combined else ''
                lines.append(
                    f"  \u2713 {role_name + ':':<24s} {role.path} "
                    f"({conf} confian\u00e7a){combined}"
                )
            else:
                lines.append(f"  \u2717 {role_name + ':':<24s} -")

        lines.append('')
        lines.append(f"Fitxers ignorats: {len(mapping.ignored)}")
        lines.append(f"Fitxers sense assignar: {len(mapping.unassigned)}")
        if mapping.unassigned:
            for path in mapping.unassigned:
                lines.append(f"  - {path}")

        missing = [r for r in REQUIRED_ROLES if r not in mapping.roles]
        if missing:
            lines.append('')
            lines.append(f"[\u26a0 Rols obligatoris pendents: {', '.join(missing)}]")

        lines.append(sep)
        return '\n'.join(lines)

    # -- private helpers -------------------------------------------------------

    # Directories where unmatched files are silently ignored (not flagged
    # as unassigned).  We scan these for specific roles only.
    _AUXILIARY_SCOPES = {'PDF/ANNEXES', 'PDF-V0/ANNEXES'}

    def _list_entries(self) -> list[tuple[str, bool, bool]]:
        """
        List files and directories in project root (non-recursive)
        plus contents of ANNEXES/ and PDF/ANNEXES/ if they exist.

        Returns list of (relative_path, is_directory, auxiliary) tuples.
        ``auxiliary`` is True for entries from scopes where unmatched
        files should be auto-ignored rather than flagged as unassigned.
        """
        entries: list[tuple[str, bool, bool]] = []
        if not self.project_path.exists():
            logger.warning(f"Project path not found: {self.project_path}")
            return entries

        for item in sorted(self.project_path.iterdir()):
            entries.append((item.name, item.is_dir(), False))

        annexes = self.project_path / 'ANNEXES'
        if annexes.is_dir():
            for item in sorted(annexes.iterdir()):
                entries.append((f"ANNEXES/{item.name}", item.is_dir(), False))

        pdf_annexes = self.project_path / 'PDF' / 'ANNEXES'
        if pdf_annexes.is_dir():
            for item in sorted(pdf_annexes.iterdir()):
                entries.append((f"PDF/ANNEXES/{item.name}", item.is_dir(), True))

        pdf_v0_annexes = self.project_path / 'PDF-V0' / 'ANNEXES'
        if pdf_v0_annexes.is_dir():
            for item in sorted(pdf_v0_annexes.iterdir()):
                entries.append((f"PDF-V0/ANNEXES/{item.name}", item.is_dir(), True))

        return entries

    def _match_role(
        self, rel_path: str, name: str, is_dir: bool,
    ) -> tuple[str, str] | None:
        """
        Try to match an entry against role patterns.

        Returns (role_name, confidence) or None.
        """
        for role_name, config in ROLE_PATTERNS.items():
            search_in = config.get('search_in', '')
            expects_dir = config.get('is_directory', False)

            # Directory role (photos_dir)
            if expects_dir:
                if is_dir and name == config['patterns'][0] and self._in_scope(rel_path, search_in):
                    return role_name, 'high'
                continue

            # File role -- skip directories
            if is_dir:
                continue

            if not self._in_scope(rel_path, search_in):
                continue

            for pattern in config['patterns']:
                if re.match(pattern, name):
                    return role_name, 'high'

        return None

    def _in_scope(self, rel_path: str, search_in: str | list[str]) -> bool:
        """Check whether rel_path is within the expected search scope."""
        # Support list of scopes (e.g. ['', 'PDF/ANNEXES'])
        if isinstance(search_in, list):
            return any(self._in_scope(rel_path, s) for s in search_in)
        if not search_in:
            return '/' not in rel_path
        parent = rel_path.rsplit('/', 1)[0] if '/' in rel_path else ''
        return parent == search_in

    def _assign_combined_roles(
        self,
        mapping: FileMapping,
        primary_role: str,
        rel_path: str,
        name: str,
        classified_paths: set[str],
    ) -> None:
        """If a file matches a combined-role pattern, assign secondary roles too."""
        combined_config = COMBINED_ROLES.get(primary_role)
        if not combined_config:
            return

        for pattern in combined_config['patterns']:
            if re.match(pattern, name):
                for secondary_role in combined_config['also_assigns']:
                    if secondary_role not in mapping.roles:
                        mapping.roles[secondary_role] = FileRole(
                            path=rel_path,
                            confidence='high',
                            detection='combined_file',
                            is_combined=True,
                            vision_type=get_vision_type(secondary_role),
                        )
                break

    def _apply_preferences(self, mapping: FileMapping) -> None:
        """
        For roles with a 'prefer' pattern, ensure the preferred candidate
        holds the role and demote others. Adjust confidence to 'medium'
        when multiple candidates were found.
        """
        for role_name, config in ROLE_PATTERNS.items():
            prefer = config.get('prefer')
            if not prefer or role_name not in mapping.roles:
                continue

            current = mapping.roles[role_name]
            current_name = current.path.split('/')[-1]

            # Check if any unassigned entry also matched this role's patterns
            competing: list[str] = []
            for upath in list(mapping.unassigned):
                uname = upath.split('/')[-1]
                for pat in config['patterns']:
                    if re.match(pat, uname):
                        competing.append(upath)
                        break

            if not competing:
                continue

            # Multiple candidates exist -- pick preferred
            all_candidates = [current.path] + competing
            preferred = None
            for cpath in all_candidates:
                cname = cpath.split('/')[-1]
                if re.match(prefer, cname):
                    preferred = cpath
                    break

            if preferred and preferred != current.path:
                # Swap: preferred takes the role, current goes to unassigned
                mapping.unassigned.remove(preferred)
                mapping.unassigned.append(current.path)
                mapping.roles[role_name] = FileRole(
                    path=preferred,
                    confidence='medium',
                    detection=current.detection,
                    vision_type=get_vision_type(role_name),
                )
            else:
                # Current is already preferred, just lower confidence
                mapping.roles[role_name] = FileRole(
                    path=current.path,
                    confidence='medium',
                    detection=current.detection,
                    vision_type=get_vision_type(role_name),
                )
